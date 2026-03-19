use std::time::{Duration, Instant};

use tokio::sync::mpsc;
use tokio::task::JoinHandle;

use crate::agent::{self, AgentResult, AgentRole};
use crate::complexity::{self, TaskComplexity};
use crate::config::Config;
use crate::{
    git, patterns, prompts,
    task::{self, Task},
};

use std::collections::HashMap;
use std::path::PathBuf;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use super::context::{RunContext, StageResult, FailureType};
use super::state::DualSelection;
use super::{review, AppEvent, LoopEvent};
use crate::extensions;
use crate::utils::atomic_write_file;

// ─── Crash Recovery Checkpoint ───────────────────────────────
// Write partial progress to checkpoint.json after each SPID stage.
// On restart, detect checkpoint and resume from last completed step.

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
struct Checkpoint {
    task_id: String,
    task_desc: String,
    completed_stage: String, // "scout", "planner", "builder", "done"
    timestamp: String,
}

fn write_checkpoint(buildloop_dir: &std::path::Path, task_id: &str, task_desc: &str, stage: &str) {
    let checkpoint = Checkpoint {
        task_id: task_id.to_string(),
        task_desc: task_desc.to_string(),
        completed_stage: stage.to_string(),
        timestamp: chrono::Utc::now().to_rfc3339(),
    };
    let path = buildloop_dir.join("checkpoint.json");
    if let Ok(json) = serde_json::to_string_pretty(&checkpoint) {
        let _ = std::fs::write(&path, json);
    }
}

fn read_checkpoint(buildloop_dir: &std::path::Path) -> Option<Checkpoint> {
    let path = buildloop_dir.join("checkpoint.json");
    let content = std::fs::read_to_string(&path).ok()?;
    serde_json::from_str(&content).ok()
}

fn clear_checkpoint(buildloop_dir: &std::path::Path) {
    let _ = std::fs::remove_file(buildloop_dir.join("checkpoint.json"));
}

// ─── Prerequisite Gates ──────────────────────────────────────
// Programmatic checks that block a pipeline stage from running
// if its preconditions aren't met. This is deterministic enforcement
// -- prompts have a non-zero failure rate, gates have zero.

enum GateResult {
    Pass,
    Fail(String),
}

/// Check that the plan file exists and contains required sections
/// before allowing the builder to run.
fn gate_builder(ctx: &RunContext) -> GateResult {
    let plan = &ctx.current_plan;
    if !plan.exists() {
        return GateResult::Fail("current-plan.md does not exist -- planner may have failed".into());
    }
    match std::fs::read_to_string(plan) {
        Ok(content) if content.trim().is_empty() => {
            GateResult::Fail("current-plan.md is empty -- planner produced no output".into())
        }
        Ok(content) => {
            if !content.contains("## File Operations") || !content.contains("## Verification") {
                GateResult::Fail(
                    "current-plan.md missing required sections (File Operations, Verification)".into(),
                )
            } else {
                GateResult::Pass
            }
        }
        Err(e) => GateResult::Fail(format!("Failed to read current-plan.md: {}", e)),
    }
}

/// Check that the builder produced claims before allowing the reviewer to run.
fn gate_reviewer(ctx: &RunContext) -> GateResult {
    let claims = ctx.buildloop_dir.join("build-claims.md");
    if !claims.exists() {
        return GateResult::Fail("build-claims.md does not exist -- builder may have failed".into());
    }
    match std::fs::metadata(&claims) {
        Ok(meta) if meta.len() < 10 => {
            GateResult::Fail("build-claims.md is effectively empty (<10 bytes)".into())
        }
        Ok(_) => GateResult::Pass,
        Err(e) => GateResult::Fail(format!("Failed to stat build-claims.md: {}", e)),
    }
}

// ─── Planner Look-Ahead ────────────────────────────────────────

/// Build the plan filename for a look-ahead task: `plan-{task_id}.md`.
fn lookahead_plan_filename(task_id: &str) -> String {
    format!("plan-{}.md", task_id)
}

/// Full path to a look-ahead plan file inside `.buildloop/`.
fn lookahead_plan_path(ctx: &RunContext, task_id: &str) -> PathBuf {
    ctx.buildloop_dir.join(lookahead_plan_filename(task_id))
}

/// Tracks an in-flight look-ahead planner task.
struct LookaheadHandle {
    task_id: String,
    handle: JoinHandle<()>,
}

/// Spawn a look-ahead planner for `next_task` in the background.
/// Returns a [`LookaheadHandle`] the caller can use to cancel or wait.
fn spawn_lookahead_planner(
    next_task: &Task,
    ctx: &RunContext,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> LookaheadHandle {
    let task_id = next_task.id.clone();
    let task_desc = next_task.description.clone();
    let ctx = ctx.clone();
    let tx = tx.clone();

    let handle = tokio::spawn(async move {
        let plan_file = lookahead_plan_filename(&task_id);
        let plan_path = ctx.buildloop_dir.join(&plan_file);

        // If the plan already exists (from a previous look-ahead), skip.
        if plan_path.exists() {
            return;
        }

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Look-ahead: planning {} in background",
            task_id
        ))));

        // Match patterns for the look-ahead task.
        let patterns_dir = patterns::resolve_patterns_dir(&ctx.config.patterns_dir);
        let all_patterns = patterns::load_patterns(&patterns_dir);

        let matched = if ctx.config.semantic_match_enabled {
            let keyword_scores = patterns::keyword_scores(&all_patterns, &task_desc);
            let (scored, _result) = crate::embeddings::match_patterns_semantic(
                &all_patterns,
                &task_desc,
                &ctx.config.embedding_model,
                ctx.config.embedding_timeout_ms,
                &keyword_scores,
                &ctx.config.ollama_url,
            )
            .await;
            scored.into_iter().map(|(p, _)| p).collect::<Vec<_>>()
        } else {
            patterns::match_patterns(&all_patterns, &task_desc)
        };

        let pattern_context =
            patterns::format_patterns_for_prompt(&matched, "planner", ctx.config.max_pattern_injection);

        let prompt = prompts::planner_lookahead_prompt(
            &task_id,
            &task_desc,
            &pattern_context,
            &ctx.spec_file_name(),
            &ctx.tasks_file_name(),
            &plan_file,
        );
        // Lookahead planner writes plans, not code -- skip extension context.

        let (agent_tx, _agent_rx) = mpsc::unbounded_channel();
        let result = agent::run_agent(
            &AgentRole::Planner,
            Config::parse_provider(&ctx.config.planner_provider),
            &ctx.config.planner_model,
            &prompt,
            &ctx.project_dir,
            agent_tx,
            &ctx.log_dir,
            None,
            ctx.config.agent_timeout_secs,
            Some(ctx.shutdown.clone()),
        )
        .await;

        let ok = result.map(|r| r.success).unwrap_or(false);
        if ok && plan_path.exists() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Look-ahead: plan ready for {}",
                task_id
            ))));
        } else {
            // Clean up partial plan file on failure.
            let _ = std::fs::remove_file(&plan_path);
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Look-ahead: planning failed for {} (will plan normally)",
                task_id
            ))));
        }
    });

    LookaheadHandle {
        task_id: next_task.id.clone(),
        handle,
    }
}

// ─── State File Backup/Restore ───────────────────────────────
// Scaffold tools (e.g. `npm create vite --overwrite`) can delete
// SPEC.md, TASKS.md, and .buildloop/ during a build. We back up
// critical files before each task and restore them if missing.

struct StateBackup {
    files: HashMap<PathBuf, Vec<u8>>,
}

fn backup_state_files(ctx: &RunContext) -> StateBackup {
    // Critical state files: task queue, spec, build plan, and project conventions.
    // CLAUDE.md is read by every agent; its deletion degrades all agent behavior.
    let critical = [
        ctx.plan_path.clone(),
        ctx.spec_path.clone(),
        ctx.current_plan.clone(),
        ctx.project_dir.join("CLAUDE.md"),
    ];

    let mut files = HashMap::new();
    for path in &critical {
        if let Ok(content) = std::fs::read(path) {
            files.insert(path.clone(), content);
        }
    }
    files.insert(
        ctx.buildloop_dir.clone(),
        Vec::new(), // marker: directory existed
    );
    StateBackup { files }
}

fn restore_state_files(
    ctx: &RunContext,
    backup: &StateBackup,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> usize {
    let mut restored = 0;

    // Ensure .buildloop dir exists
    if !ctx.buildloop_dir.exists() {
        let _ = std::fs::create_dir_all(&ctx.buildloop_dir);
        let _ = std::fs::create_dir_all(&ctx.log_dir);
    }

    // Files where truncation (exists but empty/tiny) should also trigger restore.
    // Excludes current_plan which is legitimately deleted and rewritten each task.
    let truncation_protected = [&ctx.plan_path, &ctx.spec_path];

    for (path, content) in &backup.files {
        // Skip the directory marker and empty backups
        if *path == ctx.buildloop_dir || content.is_empty() {
            continue;
        }

        let needs_restore = if !path.exists() {
            true
        } else if truncation_protected.contains(&path) {
            // Detect truncation: file exists but is much smaller than backup
            let current_size = std::fs::metadata(path).map(|m| m.len()).unwrap_or(0);
            current_size < 10 && content.len() > 10
        } else {
            false
        };

        if needs_restore {
            if let Some(parent) = path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            match atomic_write_file(path, content) {
                Ok(()) => restored += 1,
                Err(e) => {
                    let name = path.file_name().unwrap_or_default().to_string_lossy();
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Warning: failed to restore {}: {}",
                        name, e
                    ))));
                }
            }
        }
    }

    restored
}

// ─── Adaptive Pause Helpers ──────────────────────────────────
// When adaptive_pauses is enabled, skip the full inter-agent sleep
// unless the last agent run encountered rate limiting. A minimal
// 100ms pause is still applied to avoid hammering the API.

// Near-zero pause when not rate-limited. Back-to-back API calls benefit
// from prompt caching -- pausing actively hurts cache hit rates.
const ADAPTIVE_PAUSE_MIN_MS: u64 = 100;

/// Check whether an agent result indicates rate limiting occurred.
fn was_rate_limited(result: &anyhow::Result<AgentResult>) -> bool {
    match result {
        Ok(r) => {
            if let Some(ref msg) = r.failure_message {
                let lower = msg.to_ascii_lowercase();
                lower.contains("rate") || lower.contains("limit")
            } else {
                false
            }
        }
        Err(_) => false,
    }
}

/// Sleep adaptively: use the full configured pause when rate-limited or
/// when adaptive_pauses is disabled; otherwise use a minimal 100ms pause.
async fn adaptive_sleep(config: &Config, rate_limited: bool, full_secs: u64) {
    if !config.adaptive_pauses || rate_limited {
        tokio::time::sleep(Duration::from_secs(full_secs)).await;
    } else {
        tokio::time::sleep(Duration::from_millis(ADAPTIVE_PAUSE_MIN_MS)).await;
    }
}

// ─── Dual Pipeline ──────────────────────────────────────────

/// Run two complete SPID pipelines in parallel, each in its own git worktree.
/// Each pipeline runs Scout, Plan, Implement, and Doubt independently.
/// The human evaluates both results -- no automated winner selection.
fn run_dual_pipelines<'a>(
    task_info: &'a Task,
    ctx: &'a RunContext,
    tx: &'a mpsc::UnboundedSender<AppEvent>,
    skip_scout: bool,
    cached_patterns: &'a [patterns::Pattern],
    patterns_dir: &'a std::path::Path,
    extension_context: &'a str,
    specs: &'a [String; 2],
) -> std::pin::Pin<Box<dyn std::future::Future<Output = (bool, bool)> + Send + 'a>> {
    Box::pin(async move {
    // Build display labels
    let labels: [String; 2] = [
        {
            let (p, m) = Config::parse_model_spec(&specs[0]);
            Config::display_provider_model(&p, &m)
        },
        {
            let (p, m) = Config::parse_model_spec(&specs[1]);
            Config::display_provider_model(&p, &m)
        },
    ];

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStarted {
        models: labels.clone(),
    }));

    let arena_dir = ctx.buildloop_dir.join("arena");
    let _ = std::fs::create_dir_all(&arena_dir);

    // Create worktrees and RunContexts for each pipeline
    let mut wt_contexts: Vec<(PathBuf, RunContext)> = Vec::new();

    for idx in 0..2 {
        let (provider, _) = Config::parse_model_spec(&specs[idx]);
        let wt_path = arena_dir.join(format!("pipeline-{}-{}", idx, provider));

        // Remove stale worktree
        if wt_path.exists() {
            let _ = std::process::Command::new("git")
                .args(["worktree", "remove", "--force"])
                .arg(&wt_path)
                .current_dir(&ctx.project_dir)
                .output();
        }

        // Create worktree
        let wt_result = std::process::Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&wt_path)
            .arg("HEAD")
            .current_dir(&ctx.project_dir)
            .output();

        match wt_result {
            Ok(output) if output.status.success() => {}
            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Dual pipeline: failed to create worktree {}: {}", labels[idx], stderr.trim()
                ))));
                // Clean up any previously created worktrees
                for (_p, prev_ctx) in &wt_contexts {
                    let _ = std::process::Command::new("git")
                        .args(["worktree", "remove", "--force"])
                        .arg(&prev_ctx.project_dir)
                        .current_dir(&ctx.project_dir)
                        .output();
                }
                return (false, false);
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Dual pipeline: git worktree command failed: {}", e
                ))));
                for (_p, prev_ctx) in &wt_contexts {
                    let _ = std::process::Command::new("git")
                        .args(["worktree", "remove", "--force"])
                        .arg(&prev_ctx.project_dir)
                        .current_dir(&ctx.project_dir)
                        .output();
                }
                return (false, false);
            }
        }

        // Copy state files into worktree
        // SPEC and TASKS at their relative paths
        if let Ok(rel) = ctx.spec_path.strip_prefix(&ctx.project_dir) {
            let dest = wt_path.join(rel);
            if let Some(parent) = dest.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            let _ = std::fs::copy(&ctx.spec_path, &dest);
        }
        if let Ok(rel) = ctx.plan_path.strip_prefix(&ctx.project_dir) {
            let dest = wt_path.join(rel);
            if let Some(parent) = dest.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            let _ = std::fs::copy(&ctx.plan_path, &dest);
        }
        // CLAUDE.md (may be untracked/gitignored)
        let claude_md_src = ctx.project_dir.join("CLAUDE.md");
        if claude_md_src.exists() {
            let _ = std::fs::copy(&claude_md_src, wt_path.join("CLAUDE.md"));
        }

        // Create pipeline-specific config with all roles using this provider/model
        let pipeline_config = ctx.config.for_pipeline(&specs[idx]);

        // Create RunContext for this worktree
        let wt_ctx = RunContext::new(
            &wt_path,
            pipeline_config,
            ctx.shutdown.clone(),
            ctx.tasks_file_lock.clone(),
            ctx.review_gate.clone(),
        );

        wt_contexts.push((wt_path, wt_ctx));
    }

    // Run both pipelines concurrently with forwarding channels.
    // Use tokio::join! (not spawn) since process_task borrows are not 'static.
    let ((_wt0, wt_ctx0), (_wt1, wt_ctx1)) = (
        wt_contexts.remove(0),
        wt_contexts.remove(0),
    );

    // Pipeline 0 forwarding channel
    let (tx0, mut rx0) = mpsc::unbounded_channel::<AppEvent>();
    let fwd0 = tx.clone();
    tokio::spawn(async move {
        while let Some(event) = rx0.recv().await {
            let _ = fwd0.send(AppEvent::DualPipelineEvent(0, Box::new(event)));
        }
    });

    // Pipeline 1 forwarding channel
    let (tx1, mut rx1) = mpsc::unbounded_channel::<AppEvent>();
    let fwd1 = tx.clone();
    tokio::spawn(async move {
        while let Some(event) = rx1.recv().await {
            let _ = fwd1.send(AppEvent::DualPipelineEvent(1, Box::new(event)));
        }
    });

    let patterns0 = cached_patterns.to_vec();
    let patterns1 = cached_patterns.to_vec();
    let ext0 = extension_context.to_string();
    let ext1 = extension_context.to_string();
    let pdir0 = patterns_dir.to_path_buf();
    let pdir1 = patterns_dir.to_path_buf();

    let (result0, result1) = tokio::join!(
        async {
            let r = process_task(task_info, &wt_ctx0, &tx0, skip_scout, &patterns0, &pdir0, &ext0).await;
            let _ = tx0.send(AppEvent::LoopEvent(LoopEvent::TaskCompleted(task_info.id.clone(), r.0)));
            r
        },
        async {
            let r = process_task(task_info, &wt_ctx1, &tx1, skip_scout, &patterns1, &pdir1, &ext1).await;
            let _ = tx1.send(AppEvent::LoopEvent(LoopEvent::TaskCompleted(task_info.id.clone(), r.0)));
            r
        }
    );

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStreamDone(0, result0.0)));
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStreamDone(1, result1.0)));

    let any_success = result0.0 || result1.0;
    let any_rate_limited = result0.1 || result1.1;

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Both pipelines complete. Results in .buildloop/arena/ -- evaluate and merge manually."
    ))));

    // Do NOT clean up worktrees -- human evaluates results

    (any_success, any_rate_limited)
    }) // end Box::pin
}

/// Background task that polls `gh pr view` for review status and sends
/// events when the PR is approved, merged, or closed.
async fn poll_pr_review(
    pr_number: u64,
    project_dir: PathBuf,
    poll_interval_secs: u64,
    tx: mpsc::UnboundedSender<AppEvent>,
    review_gate: Arc<AtomicBool>,
) {
    let mut last_decision = String::new();
    loop {
        // Check gate FIRST (before sleeping), so first poll is immediate
        if !review_gate.load(Ordering::Relaxed) {
            return;
        }

        let result = tokio::process::Command::new("gh")
            .args([
                "pr", "view",
                &pr_number.to_string(),
                "--json", "reviewDecision,state",
            ])
            .current_dir(&project_dir)
            .output()
            .await;

        // Always update the poll timestamp
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PrPollChecked));

        match result {
            Ok(output) if output.status.success() => {
                if let Ok(json) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                    let review_decision = json["reviewDecision"].as_str().unwrap_or("");
                    let state = json["state"].as_str().unwrap_or("");

                    if review_decision == "APPROVED" || state == "MERGED" {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PrApproved(pr_number)));
                        return;
                    }
                    if state == "CLOSED" {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PrClosed(pr_number)));
                        return;
                    }
                    if review_decision == "CHANGES_REQUESTED" && review_decision != last_decision {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
                            format!(
                                "PR #{}: changes requested -- update the code or press Enter to skip",
                                pr_number
                            ),
                        )));
                    }
                    last_decision = review_decision.to_string();
                }
                // Still open/in review -- continue polling
            }
            _ => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
                    format!("gh pr view {} failed -- will retry", pr_number),
                )));
            }
        }

        // Sleep AFTER polling, so the first check is immediate
        tokio::time::sleep(Duration::from_secs(poll_interval_secs)).await;
    }
}

/// Check if the last git commit touched any structural project files
/// that would invalidate the scout report.
fn last_commit_touched_structural(project_dir: &std::path::Path) -> bool {
    let output = std::process::Command::new("git")
        .args(["diff", "--name-only", "HEAD~1", "HEAD"])
        .current_dir(project_dir)
        .output();
    match output {
        Ok(o) if o.status.success() => {
            let files = String::from_utf8_lossy(&o.stdout);
            const STRUCTURAL: &[&str] = &[
                "SPEC.md",
                "CLAUDE.md",
                "Cargo.toml",
                "package.json",
                "pyproject.toml",
                "project.yml",
                "tsconfig.json",
            ];
            files
                .lines()
                .any(|f| STRUCTURAL.iter().any(|s| f.ends_with(s)))
        }
        _ => true, // If git fails, re-scout to be safe
    }
}

fn emit_extension_injections(
    tx: &mpsc::UnboundedSender<AppEvent>,
    extensions: &[String],
    extension_context: &str,
    agent_role: &AgentRole,
    task_id: &str,
) {
    if !extension_context.is_empty() {
        for ext_name in extensions {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ExtensionInjected {
                name: ext_name.clone(),
                agent_role: agent_role.to_string(),
                task_id: task_id.to_string(),
            }));
        }
    }
}

pub(super) async fn build_loop(ctx: RunContext, tx: mpsc::UnboundedSender<AppEvent>) {
    ctx.ensure_runtime_dirs();

    // ─── Extension Contract Loading ─────────────────────────────
    let discovered_extensions = extensions::discover_extensions(&ctx.project_dir);
    let extension_context = extensions::load_extension_context(
        &discovered_extensions,
        &ctx.config.extensions,
    );
    if !ctx.config.extensions.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Extensions active: {}",
            ctx.config.extensions.join(", ")
        ))));
    }

    // Extract and send extension keywords for reference detection
    {
        let mut kw_map: HashMap<String, Vec<String>> = HashMap::new();
        for ext_name in &ctx.config.extensions {
            if let Some(ext) = discovered_extensions.iter().find(|e| e.name == *ext_name) {
                let keywords = extensions::extract_keywords(&ext.claude_md_path);
                if !keywords.is_empty() {
                    kw_map.insert(ext_name.clone(), keywords);
                }
            }
        }
        if !kw_map.is_empty() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ExtensionKeywordsLoaded {
                keywords: kw_map,
            }));
        }
    }

    let mut discovery_round: usize = task::highest_discovery_round(&ctx.plan_path);

    // ─── Discovery Cooldown State ────────────────────────────────
    // After a human-injected (H-prefix) task completes, delay discovery
    // to give the user time to inject more tasks manually.
    let mut last_h_task_completion: Option<Instant> = None;
    let mut effective_cooldown_minutes: u64 = ctx.config.discovery_cooldown_minutes;
    const MAX_COOLDOWN_MINUTES: u64 = 30;

    // ─── Planner Look-Ahead State ────────────────────────────────
    let mut lookahead: Option<LookaheadHandle> = None;

    // ─── Pattern Cache ─────────────────────────────────────────────
    let patterns_dir = patterns::resolve_patterns_dir(&ctx.config.patterns_dir);
    let mut cached_patterns = patterns::load_patterns(&patterns_dir);

    // Merge extension patterns into the pool
    let ext_patterns = extensions::load_extension_patterns(
        &discovered_extensions,
        &ctx.config.extensions,
    );
    if !ext_patterns.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Loaded {} extension patterns",
            ext_patterns.len()
        ))));
        cached_patterns.extend(ext_patterns);
    }

    // ─── Crash Recovery ───────────────────────────────────────────
    // If a previous run crashed mid-task, detect the checkpoint and
    // log it so the user knows we're aware. The task will be re-processed
    // from scratch (it's still pending in TASKS.md), but at least we
    // don't lose awareness of what happened.
    if let Some(checkpoint) = read_checkpoint(&ctx.buildloop_dir) {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Crash recovery: found checkpoint for {} at stage '{}' ({}). Resuming from task queue.",
            checkpoint.task_id, checkpoint.completed_stage, checkpoint.timestamp,
        ))));

        // If the builder completed but the task wasn't marked done (crash during doubt/commit),
        // and build-claims.md exists, we can skip straight to doubt on the next process_task run.
        // The scout report and plan are also likely still on disk.
        if checkpoint.completed_stage == "builder" {
            let claims_exist = ctx.buildloop_dir.join("build-claims.md").exists();
            if claims_exist {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Builder had completed — build-claims.md found, will attempt to resume at doubt stage".to_string(),
                )));
            }
        }
        clear_checkpoint(&ctx.buildloop_dir);
    }

    // ─── Scout State ──────────────────────────────────────────────
    // Scout runs once at session start, then reuses the report for
    // subsequent tasks unless the previous commit touched structural files.
    // If a recent scout-report exists on disk (< 10 min old), reuse it
    // across Foundry restarts to avoid re-scouting the same codebase.
    let scout_report_path = ctx.buildloop_dir.join("scout-report.md");
    let mut scout_has_run = scout_report_path.exists()
        && std::fs::metadata(&scout_report_path)
            .and_then(|m| m.modified())
            .map(|mtime| mtime.elapsed().map(|d| d.as_secs() < 600).unwrap_or(false))
            .unwrap_or(false);

    // ─── Bootstrap Scout ──────────────────────────────────────────
    // If TASKS.md has no pending tasks, run a bootstrap scout that
    // investigates the codebase and creates the initial task queue.
    // This replaces the separate gap analysis planner.
    {
        let tasks = task::parse_tasks(&ctx.plan_path).unwrap_or_default();
        if task::count_pending(&tasks) == 0 {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "No pending tasks -- running bootstrap scout to create task queue".to_string(),
            )));

            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            let fwd_handle = tokio::spawn(async move {
                while let Some(evt) = agent_rx.recv().await {
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Scout,
                Config::display_provider_model(
                    &ctx.config.scout_provider,
                    &ctx.config.scout_model,
                ),
            )));

            // Read SPEC.md for user intent if it exists
            let user_intent = std::fs::read_to_string(&ctx.spec_path)
                .ok()
                .filter(|s| !s.trim().is_empty());

            let prompt = prompts::bootstrap_scout_prompt(
                user_intent.as_deref(),
                &ctx.spec_file_name(),
                &ctx.tasks_file_name(),
            );
            // Scout is read-only investigation -- skip extension context to save tokens.
            let scout_result = agent::run_agent(
                &AgentRole::Scout,
                Config::parse_provider(&ctx.config.scout_provider),
                &ctx.config.scout_model,
                &prompt,
                &ctx.project_dir,
                agent_tx,
                &ctx.log_dir,
                None, // full tool access for task creation (needs Write)
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
            )
            .await;

            let _ = fwd_handle.await;
            let _ = tx.send(AppEvent::AgentDone(
                scout_result.as_ref().map(|r| r.success).unwrap_or(false),
            ));
            scout_has_run = true;

            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }
        }
    }

    // Accumulate build claims across the session for targeted discovery.
    let mut session_build_claims: Vec<String> = Vec::new();

    loop {
        let tasks = match task::parse_tasks(&ctx.plan_path) {
            Ok(t) => t,
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Failed to parse {}: {}",
                    ctx.tasks_file_name(),
                    e
                ))));
                tokio::time::sleep(Duration::from_secs(5)).await;
                continue;
            }
        };

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
            task::count_completed(&tasks),
            tasks.len(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::QueueUpdated(tasks.clone())));

        let next = task::next_pending(&tasks).cloned();

        if let Some(task_info) = next {
            let queue_next = task::nth_pending(&tasks, 1)
                .map(|task| format!("{} — {}", task.id, task.short_desc(72)));
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::NextTaskUpdated(queue_next)));

            // ─── Spawn Look-Ahead Planner ────────────────────────
            // While processing task N, pre-plan task N+1 in the background.
            // Only if: look-ahead enabled, next task exists, and it's not Simple.
            if ctx.config.planner_lookahead {
                // Cancel stale look-ahead if the target task changed (queue reordered).
                // But preserve the plan file if the look-ahead produced a plan for the
                // current task -- process_task will consume it.
                if let Some(ref la) = lookahead {
                    let next_next_id = task::nth_pending(&tasks, 1).map(|t| t.id.as_str());
                    if next_next_id != Some(la.task_id.as_str()) {
                        la.handle.abort();
                        // Only delete the plan file if it was NOT for the current task.
                        if la.task_id != task_info.id {
                            let _ = std::fs::remove_file(lookahead_plan_path(&ctx, &la.task_id));
                        }
                        lookahead = None;
                    }
                }

            }

            // Backup state files before the builder runs -- scaffold tools
            // with --overwrite can delete everything in the project root.
            let state_backup = backup_state_files(&ctx);

            // Skip scout if it already ran this session AND the last commit
            // didn't touch any structural files (SPEC.md, Cargo.toml, etc.)
            let skip_scout = scout_has_run && !last_commit_touched_structural(&ctx.project_dir);
            let (success, task_rate_limited) = process_task(&task_info, &ctx, &tx, skip_scout, &cached_patterns, &patterns_dir, &extension_context).await;
            scout_has_run = true;

            // Restore state files if the builder deleted or truncated them
            let restored = restore_state_files(&ctx, &state_backup, &tx);
            if restored > 0 {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Restored {} state file(s) deleted during build",
                    restored
                ))));
            }

            // mark_done is now called inside process_task, right before
            // commit_and_push, so the commit includes both the [x] mark
            // and the [SPID] indicator in one atomic operation.

            // Track when H-prefixed (human-injected) tasks complete for discovery cooldown
            if task_info.id.starts_with('H') {
                last_h_task_completion = Some(Instant::now());
                effective_cooldown_minutes = ctx.config.discovery_cooldown_minutes;
            }

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskCompleted(
                task_info.id.clone(),
                success,
            )));

            // Collect build claims for targeted discovery
            if success {
                if let Ok(claims) = std::fs::read_to_string(ctx.buildloop_dir.join("build-claims.md")) {
                    session_build_claims.push(format!("## {}\n{}", task_info.id, claims));
                }
            }

            // Reload patterns cache if extraction may have added new ones
            let refreshed = patterns::load_patterns(&patterns_dir);
            if refreshed.len() != cached_patterns.len() {
                cached_patterns = refreshed;
            }

            // Spawn look-ahead planner for the next task now that the scout
            // report from the current task is written to disk.
            if ctx.config.planner_lookahead && lookahead.is_none() {
                let fresh_tasks = task::parse_tasks(&ctx.plan_path).unwrap_or_default();
                if let Some(next_task) = task::nth_pending(&fresh_tasks, 0) {
                    let next_complexity = complexity::classify_task(&next_task.description);
                    if next_complexity != TaskComplexity::Simple {
                        lookahead = Some(spawn_lookahead_planner(next_task, &ctx, &tx));
                    }
                }
            }

            if let Ok(tasks) = task::parse_tasks(&ctx.plan_path) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
                    task::count_completed(&tasks),
                    tasks.len(),
                )));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::QueueUpdated(tasks)));
            }

            // Check cost limit
            if ctx.config.cost_limit > 0.0 {
                let cost_millicents = ctx.session_cost_millicents.load(std::sync::atomic::Ordering::Relaxed);
                let cost_usd = cost_millicents as f64 / 100_000.0;
                if cost_usd >= ctx.config.cost_limit {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Cost limit reached: ${:.2} >= ${:.2} — pausing loop",
                        cost_usd, ctx.config.cost_limit
                    ))));
                    if let Some(la) = lookahead.take() {
                        la.handle.abort();
                        let _ = std::fs::remove_file(lookahead_plan_path(&ctx, &la.task_id));
                    }
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                    return;
                }
            }

            let stop_file = ctx.stop_file();
            if stop_file.exists() {
                // Cancel any in-flight look-ahead before exiting.
                if let Some(la) = lookahead.take() {
                    la.handle.abort();
                    let _ = std::fs::remove_file(lookahead_plan_path(&ctx, &la.task_id));
                }
                let _ = std::fs::remove_file(stop_file);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            adaptive_sleep(&ctx.config, task_rate_limited, ctx.config.pause_between_tasks_secs).await;
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::NextTaskUpdated(None)));

            // ─── Sprint Mode: Stop when queue empties ────────────────
            if ctx.config.run_mode == "sprint" {
                let done_count = task::count_completed(&tasks);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    format!("Sprint complete -- all {} tasks done", done_count),
                )));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            // ─── Review Mode: Stop when queue empties ────────────────
            if ctx.config.run_mode == "review" {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Review mode: task queue complete -- stopping".to_string(),
                )));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            // ─── Discovery Cooldown Check ────────────────────────
            // Skip discovery if an H-prefixed task completed recently.
            if let Some(completed_at) = last_h_task_completion {
                let elapsed = completed_at.elapsed();
                let cooldown = Duration::from_secs(effective_cooldown_minutes * 60);
                if elapsed < cooldown {
                    let remaining_secs = (cooldown - elapsed).as_secs();
                    let remaining_mins = remaining_secs.div_ceil(60);
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Skipping discovery (cooldown: {} minutes remaining)",
                        remaining_mins
                    ))));
                    tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_cycles_secs)).await;
                    if ctx.is_stop_requested() {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                            "Stop requested during discovery cooldown -- shutting down".to_string(),
                        )));
                        let stop_file = ctx.stop_file();
                        if stop_file.exists() {
                            let _ = std::fs::remove_file(stop_file);
                        }
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                        return;
                    }
                    continue;
                }
            }

            discovery_round += 1;

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryStarted(discovery_round)));

            let pre_count = tasks.len();

            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            let fwd_handle = tokio::spawn(async move {
                while let Some(evt) = agent_rx.recv().await {
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Discovery,
                Config::display_provider_model(
                    &ctx.config.discovery_provider,
                    &ctx.config.discovery_model,
                ),
            )));

            let build_history = if session_build_claims.is_empty() {
                None
            } else {
                Some(session_build_claims.join("\n\n"))
            };
            let prompt = prompts::discovery_prompt(
                discovery_round,
                &ctx.spec_file_name(),
                &ctx.tasks_file_name(),
                build_history.as_deref(),
            );
            // Discovery finds new work -- skip extension context to save tokens.
            let result = agent::run_agent(
                &AgentRole::Discovery,
                Config::parse_provider(&ctx.config.discovery_provider),
                &ctx.config.discovery_model,
                &prompt,
                &ctx.project_dir,
                agent_tx,
                &ctx.log_dir,
                None,
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
            )
            .await;

            let _ = fwd_handle.await;
            let _ = tx.send(AppEvent::AgentDone(
                result.as_ref().map(|r| r.success).unwrap_or(false),
            ));

            // Check stop after discovery agent completion
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Stop requested after DISCOVERY agent — shutting down".to_string(),
                )));
                let stop_file = ctx.stop_file();
                if stop_file.exists() {
                    let _ = std::fs::remove_file(stop_file);
                }
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            let new_tasks = match task::parse_tasks(&ctx.plan_path) {
                Ok(t) => t.len().saturating_sub(pre_count),
                Err(_) => 0,
            };

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryCompleted(
                new_tasks,
            )));

            if new_tasks == 0 {
                // Double the discovery cooldown (up to 30 min) when discovery finds nothing
                effective_cooldown_minutes = (effective_cooldown_minutes * 2).min(MAX_COOLDOWN_MINUTES);

                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "No new tasks found — waiting before next scan...".to_string(),
                )));
                tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_cycles_secs)).await;
                // Check stop after inter-cycle sleep
                if ctx.is_stop_requested() {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        "Stop requested during discovery pause — shutting down".to_string(),
                    )));
                    let stop_file = ctx.stop_file();
                    if stop_file.exists() {
                        let _ = std::fs::remove_file(stop_file);
                    }
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                    return;
                }
            } else {
                let _ = git::commit_and_push(
                    &ctx.project_dir,
                    &ctx.config,
                    &format!("D{}", discovery_round),
                    &format!(
                        "Discovery round {} — {} new tasks",
                        discovery_round, new_tasks
                    ),
                    false,
                );
            }

            // Check stop after discovery commit
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Stop requested after discovery commit — shutting down".to_string(),
                )));
                let stop_file = ctx.stop_file();
                if stop_file.exists() {
                    let _ = std::fs::remove_file(stop_file);
                }
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            if let Ok(tasks) = task::parse_tasks(&ctx.plan_path) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
                    task::count_completed(&tasks),
                    tasks.len(),
                )));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::QueueUpdated(tasks)));
            }
        }
    }
}

/// Route WIP commits to the correct function based on run_mode.
/// In review mode, use commit_task_pr (feature branch isolation).
/// Otherwise, use commit_and_push (base branch).
fn commit_wip_for_mode(ctx: &RunContext, task_id: &str, task_desc: &str) -> bool {
    if ctx.config.run_mode == "review" {
        git::commit_task_pr(
            &ctx.project_dir,
            &ctx.config,
            task_id,
            task_desc,
            &ctx.plan_path,
            true,
        )
        .map(|(c, _)| c)
        .unwrap_or_else(|e| {
            eprintln!(
                "[foundry] WARNING: WIP commit_task_pr failed for {}: {} -- falling back to base-branch commit (feature branch isolation bypassed)",
                task_id, e
            );
            git::commit_and_push(&ctx.project_dir, &ctx.config, task_id, task_desc, true)
                .unwrap_or_else(|e2| {
                    eprintln!(
                        "[foundry] WARNING: WIP commit_and_push fallback also failed for {}: {} -- changes may be lost",
                        task_id, e2
                    );
                    false
                })
        })
    } else {
        git::commit_and_push(&ctx.project_dir, &ctx.config, task_id, task_desc, true)
            .unwrap_or_else(|e| {
                eprintln!("[foundry] WARNING: WIP commit_and_push failed for {}: {} -- changes may be lost", task_id, e);
                false
            })
    }
}

// ─── Trim Verbose Build Output ──────────────────────────────

/// Parse build-claims.md content, find the `## Verification Results` section,
/// and trim it if it exceeds 100 lines. Returns the (possibly trimmed) full
/// file content and optionally (original_lines, trimmed_lines).
fn trim_verification_section(content: &str) -> (String, Option<(usize, usize)>) {
    let all_lines: Vec<&str> = content.lines().collect();

    // Find the start of ## Verification Results
    let section_start = match all_lines.iter().position(|line| line.starts_with("## Verification Results")) {
        Some(idx) => idx,
        None => return (content.to_string(), None),
    };

    // Find the end: next ## heading or end of file
    let section_end = all_lines[section_start + 1..]
        .iter()
        .position(|line| line.starts_with("## "))
        .map(|offset| section_start + 1 + offset)
        .unwrap_or(all_lines.len());

    let section_lines = &all_lines[section_start..section_end];
    let original_count = section_lines.len();

    if original_count <= 100 {
        return (content.to_string(), None);
    }

    // Build trimmed section
    let head: Vec<&str> = section_lines[..20].to_vec();
    let tail_start = original_count.saturating_sub(10);
    let middle = &section_lines[20..tail_start];
    let matched: Vec<&str> = middle
        .iter()
        .filter(|line| {
            let lower = line.to_lowercase();
            lower.contains("failed")
                || lower.contains("error")
                || lower.contains("panic")
                || lower.contains("assert")
        })
        .copied()
        .collect();
    let tail: Vec<&str> = section_lines[tail_start..].to_vec();

    let omitted = middle.len() - matched.len();
    let mut trimmed_section: Vec<&str> = Vec::new();
    trimmed_section.extend_from_slice(&head);

    let separator = format!("... [trimmed: {} lines of output removed] ...", omitted);
    // We need owned strings for the separator lines, so we'll build the final output directly
    let mut result_lines: Vec<String> = Vec::new();
    // Lines before the section
    for line in &all_lines[..section_start] {
        result_lines.push(line.to_string());
    }
    // Head
    for line in &head {
        result_lines.push(line.to_string());
    }
    // Separator
    result_lines.push(separator);
    // Matched error lines
    for line in &matched {
        result_lines.push(line.to_string());
    }
    // Blank separator before tail
    result_lines.push(String::new());
    // Tail
    for line in &tail {
        result_lines.push(line.to_string());
    }
    // Lines after the section
    for line in &all_lines[section_end..] {
        result_lines.push(line.to_string());
    }

    let trimmed_count = head.len() + 1 + matched.len() + 1 + tail.len();
    let reconstructed = result_lines.join("\n");
    // Preserve trailing newline if original had one
    let reconstructed = if content.ends_with('\n') && !reconstructed.ends_with('\n') {
        reconstructed + "\n"
    } else {
        reconstructed
    };

    (reconstructed, Some((original_count, trimmed_count)))
}

/// Read build-claims.md, trim verbose Verification Results section, write back.
/// Returns (original, trimmed) line counts if trimming occurred.
fn trim_build_claims(ctx: &RunContext) -> Option<(usize, usize)> {
    let claims_path = ctx.buildloop_dir.join("build-claims.md");
    let content = std::fs::read_to_string(&claims_path).ok()?;
    let (new_content, stats) = trim_verification_section(&content);
    if let Some((orig, trimmed)) = stats {
        atomic_write_file(&claims_path, new_content.as_bytes()).ok()?;
        Some((orig, trimmed))
    } else {
        None
    }
}

/// Returns (success, rate_limited) so the caller can decide on adaptive pauses.
async fn process_task(
    task_info: &Task,
    ctx: &RunContext,
    tx: &mpsc::UnboundedSender<AppEvent>,
    skip_scout: bool,
    cached_patterns: &[patterns::Pattern],
    patterns_dir: &std::path::Path,
    extension_context: &str,
) -> (bool, bool) {
    // Handle dual selection: Both forks two pipelines, First/Second override provider
    let dual_sel = DualSelection::from_str(&ctx.config.dual_selection);
    if ctx.config.builder_models.len() >= 2 {
        match dual_sel {
            DualSelection::Both => {
                let specs = [
                    ctx.config.builder_models[0].clone(),
                    ctx.config.builder_models[1].clone(),
                ];
                return run_dual_pipelines(
                    task_info, ctx, tx, skip_scout, cached_patterns, patterns_dir, extension_context, &specs,
                ).await;
            }
            DualSelection::First | DualSelection::Second => {
                let spec_idx = if dual_sel == DualSelection::First { 0 } else { 1 };
                let pipeline_config = ctx.config.for_pipeline(&ctx.config.builder_models[spec_idx]);
                let override_ctx = RunContext::new(
                    &ctx.project_dir,
                    pipeline_config,
                    ctx.shutdown.clone(),
                    ctx.tasks_file_lock.clone(),
                    ctx.review_gate.clone(),
                );
                // Box::pin to break async recursion (override_ctx has dual_selection cleared)
                return Box::pin(process_task(
                    task_info, &override_ctx, tx, skip_scout, cached_patterns, patterns_dir, extension_context,
                )).await;
            }
            DualSelection::Off => {} // fall through to normal pipeline
        }
    }

    let task_id = &task_info.id;
    let task_desc = &task_info.description;
    let mut stage_results: Vec<StageResult> = Vec::new();
    let patterns_extracted = ctx.buildloop_dir.join("patterns-extracted.json");

    // Clean up stale dual-build worktrees from previous sessions
    let arena_dir = ctx.buildloop_dir.join("arena");
    if arena_dir.exists() {
        if let Ok(entries) = std::fs::read_dir(&arena_dir) {
            for entry in entries.flatten() {
                let wt = entry.path();
                if wt.is_dir() {
                    let _ = std::process::Command::new("git")
                        .args(["worktree", "remove", "--force"])
                        .arg(&wt)
                        .current_dir(&ctx.project_dir)
                        .output();
                }
            }
        }
        let _ = std::fs::remove_dir_all(&arena_dir);
    }

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskStarted(
        task_info.clone(),
    )));

    let scout_report = ctx.buildloop_dir.join("scout-report.md");
    let build_claims = ctx.buildloop_dir.join("build-claims.md");
    if !skip_scout {
        let _ = std::fs::remove_file(&scout_report);
    }
    let _ = std::fs::remove_file(&build_claims);
    let _ = std::fs::remove_file(&ctx.current_plan);
    let _ = std::fs::remove_file(&ctx.review_report);
    let _ = std::fs::remove_file(&patterns_extracted);

    let matched = if ctx.config.semantic_match_enabled {
        let keyword_scores = patterns::keyword_scores(cached_patterns, task_desc);
        let (scored, result) = crate::embeddings::match_patterns_semantic(
            cached_patterns,
            task_desc,
            &ctx.config.embedding_model,
            ctx.config.embedding_timeout_ms,
            &keyword_scores,
            &ctx.config.ollama_url,
        )
        .await;
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Pattern matching ({}): cache {}/{} hit",
            result.mode, result.cache_hits, result.cache_hits + result.cache_misses
        ))));
        scored.into_iter().map(|(p, _)| p).collect::<Vec<_>>()
    } else {
        patterns::match_patterns(cached_patterns, task_desc)
    };

    let pattern_context =
        patterns::format_patterns_for_prompt(&matched, "planner", ctx.config.max_pattern_injection);
    let reviewer_pattern_context =
        patterns::format_patterns_for_prompt(&matched, "reviewer", ctx.config.max_pattern_injection);

    if !matched.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Matched {} patterns for task",
            matched.len()
        ))));
        let titles: Vec<String> = matched.iter().map(|p| p.title.clone()).collect();
        let keywords_by_title: HashMap<String, Vec<String>> = matched
            .iter()
            .filter(|p| !p.keywords.is_empty())
            .map(|p| (p.title.clone(), p.keywords.iter().map(|k| k.to_lowercase()).collect()))
            .collect();
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PatternsUsed { titles, keywords_by_title }));
    }

    // Classify task complexity to decide whether to skip the planner.
    // Skip for simple tasks (existing behavior) AND for medium tasks with
    // detailed descriptions (80+ chars). Detailed task descriptions from the
    // upgraded describe-work agent are already comprehensive plans.
    let task_complexity = complexity::classify_task(task_desc);
    let skip_planner = ctx.config.skip_planner_for_simple
        && (task_complexity == TaskComplexity::Simple
            || (task_complexity == TaskComplexity::Medium && task_desc.len() >= 80));

    // Track rate limiting across agents; starts false when planner is skipped.
    #[allow(unused_assignments)]
    let mut last_rate_limited = false;

    // ─── Run Scout (skip if recent report exists and codebase hasn't changed much) ───
    if skip_scout {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Reusing scout report from previous task".to_string(),
        )));
    } else {
        let scout_tools: &[&str] = &["Read", "Write", "Glob", "Grep", "Bash"];

        let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
        let fwd_tx = tx.clone();
        let fwd_handle = tokio::spawn(async move {
            while let Some(evt) = agent_rx.recv().await {
                let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
            }
        });

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
            AgentRole::Scout,
            Config::display_provider_model(
                &ctx.config.scout_provider,
                &ctx.config.scout_model,
            ),
        )));

        let scout_prompt_text = prompts::scout_prompt(
            task_id,
            task_desc,
            &ctx.spec_file_name(),
            &ctx.tasks_file_name(),
        );
        // Scout is read-only investigation -- skip extension context to save tokens.
        let scout_result = agent::run_agent(
            &AgentRole::Scout,
            Config::parse_provider(&ctx.config.scout_provider),
            &ctx.config.scout_model,
            &scout_prompt_text,
            &ctx.project_dir,
            agent_tx,
            &ctx.log_dir,
            Some(scout_tools),
            ctx.config.agent_timeout_secs,
            Some(ctx.shutdown.clone()),
        )
        .await;

        let _ = fwd_handle.await;
        last_rate_limited = was_rate_limited(&scout_result);
        let scout_ok = scout_result.map(|r| r.success).unwrap_or(false);
        let _ = tx.send(AppEvent::AgentDone(scout_ok));

        if !scout_ok {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                format!("Scout failed for {} — continuing without report", task_id),
            )));
            stage_results.push(StageResult::failure(
                "Scout",
                &format!("Investigate codebase for {}", task_id),
                FailureType::Crash,
                vec!["Scout is non-blocking -- pipeline continues without report".to_string()],
            ));
        }

        adaptive_sleep(
            &ctx.config,
            last_rate_limited,
            ctx.config.pause_between_agents_secs,
        )
        .await;

        if ctx.is_stop_requested() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Stop requested after SCOUT for {} — skipping remaining stages",
                task_id
            ))));
            return (false, last_rate_limited);
        }
    }

    if !skip_scout
        && stage_results.last().map(|r| r.stage.as_str()) != Some("Scout")
    {
        let mut result = StageResult::success("Scout", &format!("Investigate codebase for {}", task_id));
        if ctx.buildloop_dir.join("scout-report.md").exists() {
            result.partial_results.push("scout-report.md".to_string());
        }
        stage_results.push(result);
    }

    // Checkpoint: scout completed
    write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "scout");

    // Helper: progress indicator characters.
    let scout_char = if skip_scout { "-" } else { "S" };
    let planner_char = if skip_planner { "-" } else { "P" };

    if skip_planner {
        let reason = if task_complexity == TaskComplexity::Simple {
            "simple task"
        } else {
            "detailed medium task (>= 80 chars)"
        };
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            format!("Skipping planner for {}", reason),
        )));
    } else {
        // ─── Check for Look-Ahead Plan ───────────────────────────
        let la_plan = lookahead_plan_path(ctx, task_id);
        if la_plan.exists() {
            // A look-ahead planner already produced a plan for this task.
            // Promote it to current-plan.md and skip the planner stage.
            if std::fs::rename(&la_plan, &ctx.current_plan).is_ok() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Using pre-planned plan for {}",
                    task_id
                ))));
            } else {
                // rename failed (cross-device?), try copy+delete
                let _ = std::fs::copy(&la_plan, &ctx.current_plan);
                let _ = std::fs::remove_file(&la_plan);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Using pre-planned plan for {}",
                    task_id
                ))));
            }
        } else {
            // ─── Run Planner ─────────────────────────────────────────
            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            let fwd_handle = tokio::spawn(async move {
                while let Some(evt) = agent_rx.recv().await {
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Planner,
                Config::display_provider_model(
                    &ctx.config.planner_provider,
                    &ctx.config.planner_model,
                ),
            )));

            let prompt = prompts::planner_prompt(
                task_id,
                task_desc,
                &pattern_context,
                &ctx.spec_file_name(),
                &ctx.tasks_file_name(),
            );
            // Planner writes plans, not code -- skip extension context to save tokens.
            let plan_result = agent::run_agent(
                &AgentRole::Planner,
                Config::parse_provider(&ctx.config.planner_provider),
                &ctx.config.planner_model,
                &prompt,
                &ctx.project_dir,
                agent_tx,
                &ctx.log_dir,
                None,
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
            )
            .await;

            let _ = fwd_handle.await;
            last_rate_limited = was_rate_limited(&plan_result);
            let plan_ok = plan_result.map(|r| r.success).unwrap_or(false);
            let _ = tx.send(AppEvent::AgentDone(plan_ok));

            if !plan_ok || !ctx.current_plan.exists() {
                {
                    let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(&ctx.plan_path, task_id, &format!("{}P--!", scout_char));
                }
                stage_results.push(StageResult::failure(
                    "Planner",
                    &format!("Create implementation plan for {}", task_id),
                    FailureType::Crash,
                    vec!["Retry with a simpler task description".to_string(), "Check if SPEC.md has enough context".to_string()],
                ));
                let committed = commit_wip_for_mode(ctx, task_id, task_desc);
                let message = if committed {
                    format!("PLANNER failed for {} -- committed WIP changes", task_id)
                } else {
                    format!(
                        "PLANNER failed for {} -- no repository changes to commit",
                        task_id
                    )
                };
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(message)));
                return (false, last_rate_limited);
            }

            adaptive_sleep(
                &ctx.config,
                last_rate_limited,
                ctx.config.pause_between_agents_secs,
            )
            .await;

            // Check stop between planner and builder
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Stop requested after PLANNER for {} -- skipping remaining stages",
                    task_id
                ))));
                {
                    let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(&ctx.plan_path, task_id, &format!("{}P..", scout_char));
                }
                stage_results.push(StageResult::failure(
                    "Planner",
                    &format!("Create implementation plan for {}", task_id),
                    FailureType::StopRequested,
                    vec![],
                ));
                let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                return (false, last_rate_limited);
            }
        }

        // Planner completed -- persist progress indicator.
        {
            let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
            let _ = task::update_task_progress(&ctx.plan_path, task_id, &format!("{}{}..", scout_char, planner_char));
        }
    }

    if !skip_planner {
        let mut result = StageResult::success("Planner", &format!("Create implementation plan for {}", task_id));
        if ctx.current_plan.exists() {
            result.partial_results.push("current-plan.md".to_string());
        }
        stage_results.push(result);
    }

    // Checkpoint: planner completed
    write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "planner");

    // ─── Gate: Extension Contracts ──────────────────────────────
    if !ctx.config.extensions.is_empty() {
        let discovered = extensions::discover_extensions(&ctx.project_dir);
        if let Err(errors) = extensions::validate_extensions(&discovered, &ctx.config.extensions) {
            for err in &errors {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "GATE BLOCKED: {}", err
                ))));
            }
            {
                let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
                let _ = task::update_task_progress(
                    &ctx.plan_path, task_id,
                    &format!("{}{}--!", scout_char, planner_char),
                );
            }
            stage_results.push(StageResult::failure(
                "ExtensionGate",
                "Validate extension contracts",
                FailureType::GateFail,
                vec!["Ensure all configured extensions have CLAUDE.md files".to_string()],
            ));
            let _ = commit_wip_for_mode(ctx, task_id, task_desc);
            return (false, last_rate_limited);
        }
    }

    // ─── Gate: Builder Prerequisites (with retry-on-validation-failure) ──
    if !skip_planner {
        if let GateResult::Fail(reason) = gate_builder(ctx) {
            // Retry-with-error-feedback: append the validation error to the
            // original prompt and re-run the planner once. This is more
            // effective than blind retry because the agent gets specific
            // feedback about what's wrong with its output.
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "GATE: plan validation failed for {} -- retrying planner with feedback: {}",
                task_id, reason
            ))));

            let failed_output = std::fs::read_to_string(&ctx.current_plan).unwrap_or_default();
            let retry_prompt = format!(
                "{}\n\n--- VALIDATION ERROR (your previous output failed these checks) ---\n\
                 Error: {}\n\
                 Your previous output:\n```\n{}\n```\n\
                 Fix these specific issues. The plan MUST contain '## File Operations' and '## Verification' sections.\n\
                 --- END VALIDATION ERROR ---",
                prompts::planner_prompt(
                    task_id, task_desc, &pattern_context,
                    &ctx.spec_file_name(), &ctx.tasks_file_name(),
                ),
                reason,
                crate::utils::truncate_str(&failed_output, 500),
            );
            // Planner retry -- skip extension context to save tokens.

            let (agent_tx2, mut agent_rx2) = mpsc::unbounded_channel();
            let fwd_tx2 = tx.clone();
            let fwd_handle2 = tokio::spawn(async move {
                while let Some(evt) = agent_rx2.recv().await {
                    let _ = fwd_tx2.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Planner,
                Config::display_provider_model(
                    &ctx.config.planner_provider, &ctx.config.planner_model,
                ),
            )));

            let retry_result = agent::run_agent(
                &AgentRole::Planner,
                Config::parse_provider(&ctx.config.planner_provider),
                &ctx.config.planner_model,
                &retry_prompt,
                &ctx.project_dir,
                agent_tx2,
                &ctx.log_dir,
                None,
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
            ).await;

            let _ = fwd_handle2.await;
            last_rate_limited = was_rate_limited(&retry_result);
            let _ = tx.send(AppEvent::AgentDone(
                retry_result.as_ref().map(|r| r.success).unwrap_or(false),
            ));

            // Check gate again after retry
            if let GateResult::Fail(reason2) = gate_builder(ctx) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "GATE BLOCKED builder for {} after retry: {}", task_id, reason2
                ))));
                {
                    let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(&ctx.plan_path, task_id, &format!("{}{}--!", scout_char, planner_char));
                }
                stage_results.push(StageResult::failure(
                    "BuilderGate",
                    "Validate plan structure (File Operations + Verification sections)",
                    FailureType::GateFail,
                    vec!["Planner failed to produce valid plan after retry".to_string(), format!("Gate reason: {}", reason2)],
                ));
                let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                return (false, last_rate_limited);
            }

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Planner retry succeeded for {}", task_id
            ))));
        }
    }

    // ─── Run Builder ────────────────────────────────────────
    emit_extension_injections(tx, &ctx.config.extensions, extension_context, &AgentRole::Builder, task_id);
    let (build_ok, builder_rate_limited) = {
        // Original single-builder path
        let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
        let fwd_tx = tx.clone();
        let fwd_handle = tokio::spawn(async move {
            while let Some(evt) = agent_rx.recv().await {
                let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
            }
        });

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
            AgentRole::Builder,
            Config::display_provider_model(&ctx.config.builder_provider, &ctx.config.builder_model),
        )));

        let prompt = if skip_planner {
            prompts::builder_direct_prompt(
                task_id,
                task_desc,
                &ctx.spec_file_name(),
                &ctx.tasks_file_name(),
            )
        } else {
            prompts::builder_prompt(
                task_id,
                task_desc,
                &ctx.spec_file_name(),
                &ctx.tasks_file_name(),
            )
        };
        let prompt = prompts::wrap_with_extensions(&prompt, extension_context);
        let build_result = agent::run_agent(
            &AgentRole::Builder,
            Config::parse_provider(&ctx.config.builder_provider),
            &ctx.config.builder_model,
            &prompt,
            &ctx.project_dir,
            agent_tx,
            &ctx.log_dir,
            None,
            ctx.config.agent_timeout_secs,
            Some(ctx.shutdown.clone()),
        )
        .await;

        let _ = fwd_handle.await;
        let rl = was_rate_limited(&build_result);
        let ok = build_result.map(|r| r.success).unwrap_or(false);
        let _ = tx.send(AppEvent::AgentDone(ok));
        (ok, rl)
    };
    last_rate_limited = builder_rate_limited;

    if !build_ok {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "BUILDER failed for {} — committing WIP",
            task_id
        ))));
        {
            let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
            let _ = task::update_task_progress(&ctx.plan_path, task_id, &format!("{}{}I-!", scout_char, planner_char));
        }
        stage_results.push(StageResult::failure(
            "Builder",
            &format!("Implement changes for {}", task_id),
            FailureType::Crash,
            vec!["Check build-claims.md for partial progress".to_string(), "Review the plan for overly ambitious scope".to_string()],
        ));
        let _ = commit_wip_for_mode(ctx, task_id, task_desc);
        return (false, last_rate_limited);
    }

    // Builder completed -- persist progress indicator.
    {
        let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
        let _ = task::update_task_progress(&ctx.plan_path, task_id, &format!("{}{}I.", scout_char, planner_char));
    }

    {
        let mut result = StageResult::success("Builder", &format!("Implement changes for {}", task_id));
        if ctx.buildloop_dir.join("build-claims.md").exists() {
            result.partial_results.push("build-claims.md".to_string());
        }
        stage_results.push(result);
    }

    // Checkpoint: builder completed
    write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "builder");

    // ─── Gate: Build/Compile Verification ──────────────────────
    if let Some(ref build_cmd) = ctx.config.build_command {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Running build command: {}", build_cmd
        ))));
        let build_output = std::process::Command::new(if cfg!(target_os = "windows") { "cmd" } else { "sh" })
            .args(if cfg!(target_os = "windows") { vec!["/C", build_cmd] } else { vec!["-c", build_cmd] })
            .current_dir(&ctx.project_dir)
            .output();

        match build_output {
            Ok(output) if !output.status.success() => {
                let stderr = String::from_utf8_lossy(&output.stderr);
                let stdout = String::from_utf8_lossy(&output.stdout);
                let combined = format!("{}\n{}", stdout, stderr);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "BUILD GATE FAILED for {} — build command exited {}: {}",
                    task_id,
                    output.status,
                    crate::utils::truncate_str(combined.trim(), 500),
                ))));
                {
                    let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(&ctx.plan_path, task_id, &format!("{}{}I-!", scout_char, planner_char));
                }
                stage_results.push(StageResult::failure(
                    "BuildGate",
                    &format!("Run build command: {}", build_cmd),
                    FailureType::GateFail,
                    vec!["Build command failed -- check compiler errors".to_string()],
                ));
                let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                return (false, last_rate_limited);
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Build command failed to execute: {} — skipping gate", e
                ))));
            }
            Ok(_) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Build gate passed".to_string(),
                )));
            }
        }
    }

    // ─── Trim Verbose Build Output ──────────────────────────────
    if let Some((orig, trimmed)) = trim_build_claims(ctx) {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            format!("Trimmed test output from {} to {} lines", orig, trimmed),
        )));
    }

    adaptive_sleep(&ctx.config, last_rate_limited, ctx.config.pause_between_agents_secs).await;

    // Check stop between builder and reviewer
    if ctx.is_stop_requested() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Stop requested after BUILDER for {} — skipping review",
            task_id
        ))));
        stage_results.push(StageResult::failure(
            "Builder",
            &format!("Implement changes for {}", task_id),
            FailureType::StopRequested,
            vec![],
        ));
        // Progress indicator already written at [SPI.] above; commit preserves it.
        let _ = commit_wip_for_mode(ctx, task_id, task_desc);
        return (false, last_rate_limited);
    }

    // Batch doubt: skip for all tasks except the last pending one
    let pending_count = task::count_pending(
        &task::parse_tasks(&ctx.plan_path).unwrap_or_default(),
    );
    let skip_for_batch = ctx.config.batch_doubt && pending_count > 1;

    // Skip verify for simple tasks when the builder's own checks passed.
    // The builder already ran build/test/lint -- verify adds a fresh-context
    // audit which is most valuable for complex tasks with blind spots.
    let skip_verify = (task_complexity == TaskComplexity::Simple
        && build_ok
        && !ctx.config.backpressure_only)
        || skip_for_batch;

    let (validated, _fix_passes) = if ctx.config.backpressure_only {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Backpressure-only mode: skipping LLM review (builder verification passed)".to_string(),
        )));
        (true, 0usize)
    } else if skip_for_batch {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            format!("Batch doubt: deferring review ({} tasks remaining)", pending_count),
        )));
        (true, 0usize)
    } else if skip_verify {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Simple task with clean build -- skipping verify".to_string(),
        )));
        (true, 0usize)
    } else {
        // ─── Gate: Reviewer Prerequisites ─────────────────────
        match gate_reviewer(ctx) {
            GateResult::Fail(reason) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "GATE WARNING for reviewer on {}: {} -- reviewing without claims",
                    task_id, reason
                ))));
                // Don't block -- reviewer can fall back to reading changed files.
                // But log it clearly so we know the builder didn't produce claims.
                review::run_review_loop(task_id, task_desc, ctx, &reviewer_pattern_context, extension_context, tx).await
            }
            GateResult::Pass => {
                review::run_review_loop(task_id, task_desc, ctx, &reviewer_pattern_context, extension_context, tx).await
            }
        }
    };

    if validated {
        let mut result = StageResult::success("Reviewer", &format!("Validate changes for {}", task_id));
        if ctx.review_report.exists() {
            result.partial_results.push("review-report.md".to_string());
        }
        stage_results.push(result);
    } else if !skip_verify && !ctx.config.backpressure_only && !skip_for_batch {
        stage_results.push(StageResult::failure(
            "Reviewer",
            &format!("Validate changes for {}", task_id),
            FailureType::ReviewFail,
            vec!["Review found HIGH/MEDIUM issues that were not fixed".to_string(), "Check review-report.md for specific findings".to_string()],
        ));
    }

    // Persist final pipeline progress indicator and mark done BEFORE committing.
    // Both writes must happen before git add -A so the commit captures them.
    // Agents may overwrite TASKS.md during their run, stripping intermediate
    // indicators, so the final write must be the last mutation before commit.
    {
        let doubt_char = if skip_verify || ctx.config.backpressure_only { "-" } else { "D" };
        let fail_char = if !validated { "!" } else { "" };
        let progress = format!("{}{}I{}{}", scout_char, planner_char, doubt_char, fail_char);
        let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
        let _ = task::update_task_progress(&ctx.plan_path, task_id, &progress);
        if validated {
            let _ = task::mark_done(&ctx.plan_path, task_info.line_number);
        }
    }

    let _committed = if ctx.config.run_mode == "review" {
        // Review mode: branch, commit, push, create PR, return to base
        match git::commit_task_pr(&ctx.project_dir, &ctx.config, task_id, task_desc, &ctx.plan_path, !validated) {
            Ok((committed, pr_num)) => {
                if committed {
                    let prefix = if validated { "feat" } else { "WIP" };
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Committed {}({})", prefix, task_id
                    ))));
                }
                if let Some(pr) = pr_num {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        format!("PR #{} created for {}", pr, task_id),
                    )));
                }

                // Create GitHub issue for WIP commits in review mode
                if committed && !validated && ctx.config.create_issue_on_wip {
                    let stage_ctx = prompts::format_stage_results_for_prompt(
                        &stage_results.iter().map(|r| (
                            r.stage.clone(),
                            r.success,
                            r.failure_type.as_ref().map(|f| format!("{:?}", f)),
                            r.attempted_action.clone(),
                            r.partial_results.clone(),
                            r.suggestions.clone(),
                        )).collect::<Vec<_>>(),
                    );
                    match git::create_wip_issue(
                        &ctx.project_dir,
                        task_id,
                        task_desc,
                        &ctx.review_report,
                        &stage_ctx,
                    ) {
                        Ok(Some(issue_num)) => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                                format!("Issue #{} created for WIP({})", issue_num, task_id),
                            )));
                        }
                        Ok(None) => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                                format!("Issue created for WIP({}) but could not parse issue number", task_id),
                            )));
                        }
                        Err(e) => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                                format!("Failed to create issue for WIP({}): {}", task_id, e),
                            )));
                        }
                    }
                }

                // Pause: signal TUI and wait for user to press Enter or PR approval
                ctx.review_gate.store(true, Ordering::Relaxed);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::WaitingForReview(pr_num)));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Waiting for PR review -- press Enter to continue or wait for approval".to_string(),
                )));

                // Spawn background PR poller if we have a PR number
                let poll_handle = if let Some(pr_number) = pr_num {
                    let tx_poll = tx.clone();
                    let project_dir = ctx.project_dir.clone();
                    let poll_interval = ctx.config.pr_poll_interval_secs;
                    let review_gate_clone = ctx.review_gate.clone();
                    Some(tokio::spawn(async move {
                        poll_pr_review(pr_number, project_dir, poll_interval, tx_poll, review_gate_clone).await;
                    }))
                } else {
                    None
                };

                while ctx.review_gate.load(Ordering::Relaxed) {
                    if ctx.is_stop_requested() {
                        if let Some(h) = poll_handle {
                            h.abort();
                        }
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                        return (false, false);
                    }
                    tokio::time::sleep(Duration::from_millis(200)).await;
                }

                // Cancel polling task if still running
                if let Some(h) = poll_handle {
                    h.abort();
                }

                committed
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    format!("WARNING: Per-task PR failed: {} -- falling back to base-branch commit (feature branch isolation bypassed)", e),
                )));
                let committed = git::commit_and_push(&ctx.project_dir, &ctx.config, task_id, task_desc, !validated)
                    .unwrap_or(false);

                // Still pause after fallback commit in review mode
                if committed {
                    ctx.review_gate.store(true, Ordering::Relaxed);
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::WaitingForReview(None)));
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        "Waiting for review -- press Enter to continue to next task".to_string(),
                    )));
                    while ctx.review_gate.load(Ordering::Relaxed) {
                        if ctx.is_stop_requested() {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                            return (false, false);
                        }
                        tokio::time::sleep(Duration::from_millis(200)).await;
                    }
                }

                committed
            }
        }
    } else {
        let committed = git::commit_and_push(
            &ctx.project_dir,
            &ctx.config,
            task_id,
            task_desc,
            !validated,
        )
        .unwrap_or(false);

        if committed {
            let prefix = if validated { "feat" } else { "WIP" };
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Committed {}({})",
                prefix, task_id
            ))));
        }
        if committed && !validated && ctx.config.create_issue_on_wip {
            let stage_ctx = prompts::format_stage_results_for_prompt(
                &stage_results.iter().map(|r| (
                    r.stage.clone(),
                    r.success,
                    r.failure_type.as_ref().map(|f| format!("{:?}", f)),
                    r.attempted_action.clone(),
                    r.partial_results.clone(),
                    r.suggestions.clone(),
                )).collect::<Vec<_>>(),
            );
            match git::create_wip_issue(
                &ctx.project_dir,
                task_id,
                task_desc,
                &ctx.review_report,
                &stage_ctx,
            ) {
                Ok(Some(issue_num)) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        format!("Issue #{} created for WIP({})", issue_num, task_id),
                    )));
                }
                Ok(None) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        format!("Issue created for WIP({}) but could not parse issue number", task_id),
                    )));
                }
                Err(e) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        format!("Failed to create issue for WIP({}): {}", task_id, e),
                    )));
                }
            }
        }
        committed
    };

    // Skip pattern extraction for trivial tasks (< 3 files changed or
    // reviewer found no issues). These tasks rarely produce interesting patterns.
    // Use HEAD~1..HEAD because this runs AFTER the commit, so unstaged diff is empty.
    let changed_file_count = std::process::Command::new("git")
        .args(["diff", "--name-only", "HEAD~1", "HEAD"])
        .current_dir(&ctx.project_dir)
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).lines().count())
        .unwrap_or(0);

    if validated && changed_file_count >= 3 {
        // Fire-and-forget: pattern extraction runs in the background so the
        // loop can start the next task immediately.  It writes to a separate
        // patterns directory, not to the source tree, so there is no conflict.
        let bg_task_id = task_id.to_string();
        let bg_task_desc = task_desc.to_string();
        let bg_ctx = ctx.clone();
        let bg_patterns_dir = patterns_dir.to_path_buf();
        let bg_patterns_extracted = patterns_extracted.clone();
        let bg_tx = tx.clone();
        tokio::spawn(async move {
            tokio::time::sleep(Duration::from_secs(bg_ctx.config.pause_between_agents_secs)).await;
            run_pattern_extraction(
                &bg_task_id,
                &bg_task_desc,
                &bg_ctx,
                &bg_patterns_dir,
                &bg_patterns_extracted,
                &bg_tx,
            )
            .await;
            let _ = std::fs::remove_file(&bg_patterns_extracted);
        });
    }

    if should_restart_docker(task_desc) {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Restarting Docker services...".to_string(),
        )));
        let _ = std::process::Command::new("docker")
            .args(["compose", "down"])
            .current_dir(&ctx.project_dir)
            .output();
        let _ = std::process::Command::new("docker")
            .args(["compose", "up", "-d", "--build"])
            .current_dir(&ctx.project_dir)
            .output();
    }

    // Clear checkpoint — task completed successfully (committed or WIP)
    clear_checkpoint(&ctx.buildloop_dir);

    (validated, last_rate_limited)
}

async fn run_pattern_extraction(
    task_id: &str,
    task_desc: &str,
    ctx: &RunContext,
    patterns_dir: &std::path::Path,
    patterns_extracted: &std::path::Path,
    tx: &mpsc::UnboundedSender<AppEvent>,
) {
    let (agent_tx, _agent_rx) = mpsc::unbounded_channel();

    let model = &ctx.config.pattern_extraction_model;
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
        format!(
            "Background pattern extraction started (Claude {})",
            model,
        ),
    )));
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
        "Extracting patterns from build artifacts...".to_string(),
    )));

    let prompt = prompts::pattern_extraction_prompt(task_id, task_desc);
    // Note: pattern extraction doesn't get extension context -- it's a lightweight
    // JSON extraction task that doesn't benefit from domain-specific instructions.
    let result = agent::run_agent(
        &AgentRole::Discovery,
        agent::ModelProvider::Claude,
        model,
        &prompt,
        &ctx.project_dir,
        agent_tx,
        &ctx.log_dir,
        Some(&["Read", "Write"]),
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
    )
    .await;

    let success = result.as_ref().map(|r| r.success).unwrap_or(false);
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
        format!(
            "Background pattern extraction {}",
            if success { "completed" } else { "failed" },
        ),
    )));

    if patterns_extracted.exists() {
        match patterns::extract_patterns_from_file(patterns_extracted) {
            Ok(new_patterns) if !new_patterns.is_empty() => {
                // Capture titles before merge (merge consumes the vec)
                let titles: Vec<String> = new_patterns.iter().map(|p| p.title.clone()).collect();
                match patterns::merge_patterns(patterns_dir, new_patterns) {
                    Ok(added) => {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                            "Merged patterns: {} new added to {}",
                            added,
                            patterns_dir.display()
                        ))));
                        // Send individual pattern titles for session tracking
                        for title in &titles {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
                                format!("Pattern learned: {}", title),
                            )));
                        }
                    }
                    Err(e) => {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                            "Failed to merge patterns: {}",
                            e
                        ))));
                    }
                }
            }
            Ok(_) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
                    "No patterns extracted for this task".to_string(),
                )));
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                    "Failed to parse extracted patterns: {}",
                    e
                ))));
            }
        }
    }
}

fn should_restart_docker(task_desc: &str) -> bool {
    let lower = task_desc.to_lowercase();
    let has_docker_word = lower.contains("docker")
        || lower.contains("dockerfile")
        || lower.contains("caddy");
    if has_docker_word {
        return true;
    }
    let infra_qualifiers = ["docker", "container", "service", "environment"];
    let broad_keywords = ["integration", "scaffold", "compose"];
    for kw in &broad_keywords {
        if lower.contains(kw) {
            for qual in &infra_qualifiers {
                if lower.contains(qual) {
                    return true;
                }
            }
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::should_restart_docker;
    use super::{backup_state_files, restore_state_files};
    use crate::app::context::RunContext;
    use crate::app::state::{AppEvent, LoopEvent};
    use crate::config::Config;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::{Arc, Mutex};
    use tokio::sync::mpsc;

    #[test]
    fn should_restart_docker_matches_expected_keywords() {
        // Primary Docker keywords -- always trigger
        assert!(should_restart_docker("Update docker compose stack"));
        assert!(should_restart_docker("Fix Dockerfile build stage"));
        assert!(should_restart_docker("Update caddy reverse proxy"));

        // Broad keywords WITH infrastructure qualifier -- trigger
        assert!(should_restart_docker("Fix caddy integration issue"));
        assert!(should_restart_docker("Scaffold docker environment"));
        assert!(should_restart_docker("Scaffold container setup"));
        assert!(should_restart_docker("Integration service config"));
        assert!(should_restart_docker("Rebuild compose services"));
        assert!(should_restart_docker("Compose container networking"));
        assert!(should_restart_docker("Update compose docker config"));

        // Broad keywords WITHOUT infrastructure qualifier -- do NOT trigger
        assert!(!should_restart_docker("Add integration tests"));
        assert!(!should_restart_docker("Scaffold test fixtures"));
        assert!(!should_restart_docker("Scaffold auth module"));
        assert!(!should_restart_docker("Fix integration callback parser"));
        assert!(!should_restart_docker("Compose validation error messages"));
        assert!(!should_restart_docker("Compose a response template"));

        // Unrelated tasks -- do NOT trigger
        assert!(!should_restart_docker("Refactor auth callback parser"));
        assert!(!should_restart_docker("Add unit tests for parser"));
    }

    fn make_test_ctx(name: &str) -> (RunContext, PathBuf) {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("foundry-backup-{}-{}", name, unique));
        std::fs::create_dir_all(&dir).expect("create temp dir");
        std::fs::write(
            dir.join("TASKS.md"),
            "- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n",
        )
        .expect("write TASKS.md");
        std::fs::write(
            dir.join("SPEC.md"),
            "# Test Spec\n\nThis is the spec.\n",
        )
        .expect("write SPEC.md");
        std::fs::write(
            dir.join("CLAUDE.md"),
            "# CLAUDE.md\n\nProject instructions.\n",
        )
        .expect("write CLAUDE.md");
        std::fs::create_dir_all(dir.join(".buildloop")).expect("create .buildloop");
        std::fs::write(
            dir.join(".buildloop/current-plan.md"),
            "# Plan: T1.1\n\n## Steps\n1. Do the thing\n",
        )
        .expect("write current-plan.md");
        let ctx = RunContext::new(&dir, Config::default(), Arc::new(AtomicBool::new(false)), Arc::new(Mutex::new(())), Arc::new(AtomicBool::new(false)));
        (ctx, dir)
    }

    fn drain_events(rx: &mut mpsc::UnboundedReceiver<AppEvent>) -> Vec<String> {
        let mut msgs = Vec::new();
        while let Ok(evt) = rx.try_recv() {
            if let AppEvent::LoopEvent(LoopEvent::Log(msg)) = evt {
                msgs.push(msg);
            }
        }
        msgs
    }

    #[test]
    fn test_backup_captures_all_state_files() {
        let (ctx, dir) = make_test_ctx("capture");
        let backup = backup_state_files(&ctx);

        assert!(backup.files.contains_key(&ctx.plan_path));
        assert!(backup.files.contains_key(&ctx.spec_path));
        assert!(backup.files.contains_key(&ctx.current_plan));
        assert!(backup.files.contains_key(&ctx.project_dir.join("CLAUDE.md")));
        assert_eq!(
            backup.files.get(&ctx.plan_path).unwrap(),
            b"- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n"
        );
        assert_eq!(
            backup.files.get(&ctx.spec_path).unwrap(),
            b"# Test Spec\n\nThis is the spec.\n"
        );
        assert!(backup.files.contains_key(&ctx.buildloop_dir));
        assert!(backup.files.get(&ctx.buildloop_dir).unwrap().is_empty());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_recovers_deleted_files() {
        let (ctx, dir) = make_test_ctx("restore-deleted");
        let backup = backup_state_files(&ctx);

        std::fs::remove_file(&ctx.plan_path).unwrap();
        std::fs::remove_file(&ctx.spec_path).unwrap();
        std::fs::remove_file(ctx.project_dir.join("CLAUDE.md")).unwrap();

        assert!(!ctx.plan_path.exists());
        assert!(!ctx.spec_path.exists());

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 3);
        assert!(ctx.plan_path.exists());
        assert!(ctx.spec_path.exists());
        assert!(ctx.project_dir.join("CLAUDE.md").exists());
        assert_eq!(
            std::fs::read_to_string(&ctx.plan_path).unwrap(),
            "- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_recovers_truncated_files() {
        let (ctx, dir) = make_test_ctx("restore-truncated");
        let backup = backup_state_files(&ctx);

        std::fs::write(&ctx.plan_path, "").unwrap();
        std::fs::write(&ctx.spec_path, "short").unwrap();

        assert!(ctx.plan_path.exists());
        assert!(ctx.spec_path.exists());

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 2);
        assert_eq!(
            std::fs::read_to_string(&ctx.plan_path).unwrap(),
            "- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n"
        );
        assert_eq!(
            std::fs::read_to_string(&ctx.spec_path).unwrap(),
            "# Test Spec\n\nThis is the spec.\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_does_not_overwrite_rewritten_current_plan() {
        let (ctx, dir) = make_test_ctx("no-overwrite-plan");
        let backup = backup_state_files(&ctx);

        std::fs::write(
            &ctx.current_plan,
            "# Plan: T1.2\n\nNew plan content written by planner.\n",
        )
        .unwrap();

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 0);
        assert_eq!(
            std::fs::read_to_string(&ctx.current_plan).unwrap(),
            "# Plan: T1.2\n\nNew plan content written by planner.\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_recovers_deleted_current_plan() {
        let (ctx, dir) = make_test_ctx("deleted-plan");
        let backup = backup_state_files(&ctx);

        std::fs::remove_file(&ctx.current_plan).unwrap();
        assert!(!ctx.current_plan.exists());

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 1);
        assert!(ctx.current_plan.exists());
        assert_eq!(
            std::fs::read_to_string(&ctx.current_plan).unwrap(),
            "# Plan: T1.1\n\n## Steps\n1. Do the thing\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[cfg(unix)]
    #[test]
    fn test_restore_write_failure_produces_warning_log() {
        use std::os::unix::fs::PermissionsExt;

        let (ctx, dir) = make_test_ctx("write-fail");
        let backup = backup_state_files(&ctx);

        std::fs::remove_file(&ctx.plan_path).unwrap();
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o444)).unwrap();

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 0);

        let msgs = drain_events(&mut rx);
        assert!(msgs.len() >= 1);
        assert!(msgs.iter().any(|m| m.contains("Warning") && m.contains("TASKS.md")));

        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o755)).unwrap();
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_is_stop_requested_detects_stop_file() {
        let (ctx, dir) = make_test_ctx("stop-file");
        assert!(!ctx.is_stop_requested());
        std::fs::write(ctx.stop_file(), "").unwrap();
        assert!(ctx.is_stop_requested());
        std::fs::remove_file(ctx.stop_file()).unwrap();
        assert!(!ctx.is_stop_requested());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_is_stop_requested_detects_shutdown_flag() {
        let (ctx, dir) = make_test_ctx("shutdown-flag");
        assert!(!ctx.is_stop_requested());
        ctx.shutdown.store(true, Ordering::Relaxed);
        assert!(ctx.is_stop_requested());
        let _ = std::fs::remove_dir_all(&dir);
    }

    // ─── Trim Verification Section Tests ────────────────────────

    use super::trim_verification_section;

    #[test]
    fn test_trim_verification_section_no_section() {
        let content = "# Build Claims\n\n## Files Changed\n- file.rs\n\n## Claims\n- claim 1\n";
        let (result, stats) = trim_verification_section(content);
        assert_eq!(result, content);
        assert!(stats.is_none());
    }

    #[test]
    fn test_trim_verification_section_under_threshold() {
        let mut content = String::from("## Verification Results\n");
        for i in 0..50 {
            content.push_str(&format!("line {}\n", i));
        }
        let (result, stats) = trim_verification_section(&content);
        assert_eq!(result, content);
        assert!(stats.is_none());
    }

    #[test]
    fn test_trim_verification_section_over_threshold() {
        let mut content = String::from("## Verification Results\n");
        for i in 0..200 {
            if i == 50 {
                content.push_str("test result: FAILED\n");
            } else if i == 100 {
                content.push_str("thread panicked at: assertion error\n");
            } else {
                content.push_str(&format!("ok line {}\n", i));
            }
        }
        let original_content = content.clone();
        let (result, stats) = trim_verification_section(&content);
        assert!(stats.is_some());
        let (orig, trimmed) = stats.unwrap();
        // Section is 201 lines (heading + 200 content lines)
        assert_eq!(orig, 201);
        assert!(trimmed < orig);
        // Should contain the heading
        assert!(result.contains("## Verification Results"));
        // Should contain the trimmed marker
        assert!(result.contains("[trimmed:"));
        // Should contain the error lines
        assert!(result.contains("FAILED"));
        assert!(result.contains("panic"));
        // Should NOT be identical to the original
        assert_ne!(result, original_content);
    }

    #[test]
    fn test_trim_verification_section_preserves_other_sections() {
        let mut content = String::from("## Files Changed\n- MODIFY src/app/build.rs\n\n## Verification Results\n");
        for i in 0..150 {
            content.push_str(&format!("output line {}\n", i));
        }
        content.push_str("## Claims\n- [ ] Claim 1\n- [ ] Claim 2\n");
        let (result, stats) = trim_verification_section(&content);
        assert!(stats.is_some());
        // Files Changed section preserved
        assert!(result.contains("## Files Changed"));
        assert!(result.contains("- MODIFY src/app/build.rs"));
        // Claims section preserved
        assert!(result.contains("## Claims"));
        assert!(result.contains("- [ ] Claim 1"));
        assert!(result.contains("- [ ] Claim 2"));
        // Trimmed marker present
        assert!(result.contains("[trimmed:"));
    }
}

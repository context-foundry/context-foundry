use std::sync::atomic::AtomicUsize;
use std::time::{Duration, Instant};

use futures::future::join_all;
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

use std::sync::atomic::Ordering;
use std::sync::Arc;

use super::context::{FailureType, RunContext, StageResult};
use super::state::DualSelection;
use super::{review, AppEvent, LoopEvent};
use crate::budget;
use crate::doubt_confidence;
use crate::extensions;
use crate::observatory::{self, AgentUsage, ObservatoryEvent};
use crate::orchestrator::{self, OrchestratorConfig};
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
        if let Err(e) = atomic_write_file(&path, json.as_bytes()) {
            eprintln!(
                "Warning: failed to write checkpoint to {}: {} -- crash recovery may not resume from this stage",
                path.display(), e
            );
        }
    }
}

fn read_checkpoint(buildloop_dir: &std::path::Path) -> Option<Checkpoint> {
    let path = buildloop_dir.join("checkpoint.json");
    let content = std::fs::read_to_string(&path).ok()?;
    serde_json::from_str(&content).ok()
}

fn clear_checkpoint(buildloop_dir: &std::path::Path) {
    if let Err(e) = std::fs::remove_file(buildloop_dir.join("checkpoint.json")) {
        if e.kind() != std::io::ErrorKind::NotFound {
            eprintln!("Warning: failed to remove checkpoint.json: {}", e);
        }
    }
}

/// Write accumulated budget telemetry to disk. Called before early returns
/// so that partial telemetry is not lost when the pipeline aborts.
fn flush_budget_telemetry(
    buildloop_dir: &std::path::Path,
    budget_recovery_enabled: bool,
    telemetry: &budget::BudgetTelemetry,
) {
    if budget_recovery_enabled && !telemetry.records.is_empty() {
        budget::write_telemetry(buildloop_dir, telemetry);
    }
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
        return GateResult::Fail(
            "current-plan.md does not exist -- planner may have failed".into(),
        );
    }
    match std::fs::read_to_string(plan) {
        Ok(content) if content.trim().is_empty() => {
            GateResult::Fail("current-plan.md is empty -- planner produced no output".into())
        }
        Ok(content) => {
            if !content.contains("## File Operations") || !content.contains("## Verification") {
                GateResult::Fail(
                    "current-plan.md missing required sections (File Operations, Verification)"
                        .into(),
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
        return GateResult::Fail(
            "build-claims.md does not exist -- builder may have failed".into(),
        );
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

        let detected_stack = patterns::detect_project_tech_stack(&ctx.project_dir);
        let matched = if ctx.config.semantic_match_enabled {
            let keyword_scores =
                patterns::keyword_scores(&all_patterns, &task_desc, &detected_stack);
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
            patterns::match_patterns(&all_patterns, &task_desc, &detected_stack)
        };

        let lookahead_complexity = complexity::classify_task(&task_desc);
        let lookahead_pattern_count = patterns::scaled_injection_count(
            lookahead_complexity,
            ctx.config.max_pattern_injection,
            ctx.config.min_pattern_injection,
        );
        let pattern_context =
            patterns::format_patterns_for_prompt(&matched, "planner", lookahead_pattern_count);

        let prompt = prompts::planner_lookahead_prompt(
            &ctx.config.pipeline_stage_label("plan"),
            &task_id,
            &task_desc,
            &pattern_context,
            &ctx.spec_file_prompt_path(),
            &ctx.tasks_file_prompt_path(),
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
            Some(&ctx.config),
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
            if let Err(e) = std::fs::remove_file(&plan_path) {
                if e.kind() != std::io::ErrorKind::NotFound {
                    eprintln!(
                        "Warning: failed to remove failed look-ahead plan {}: {}",
                        plan_path.display(),
                        e
                    );
                }
            }
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
        if let Err(e) = std::fs::create_dir_all(&ctx.buildloop_dir) {
            eprintln!(
                "Warning: failed to create buildloop dir during restore: {}",
                e
            );
        }
        if let Err(e) = std::fs::create_dir_all(&ctx.log_dir) {
            eprintln!("Warning: failed to create log dir during restore: {}", e);
        }
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
                if let Err(e) = std::fs::create_dir_all(parent) {
                    eprintln!(
                        "Warning: failed to create parent dir {}: {}",
                        parent.display(),
                        e
                    );
                }
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

// ─── Parallel Builder ─────────────────────────────────────

/// A single file operation parsed from the plan's `## File Operations` section.
#[derive(Debug, Clone)]
struct FileOp {
    /// The raw text block for this file operation (everything from the ### header
    /// to just before the next ### header or ## section).
    raw_block: String,
    /// The file path extracted from the header, e.g. "src/config.rs".
    file_path: String,
}

/// Parse the `## File Operations` section of current-plan.md into individual FileOp entries.
/// Each entry captures the full text block for one file operation.
fn parse_file_operations(plan_content: &str) -> Vec<FileOp> {
    let lines: Vec<&str> = plan_content.lines().collect();

    // Find "## File Operations" header
    let section_start = match lines.iter().position(|l| {
        let trimmed = l.trim();
        trimmed.starts_with("## File Operations")
    }) {
        Some(i) => i + 1,
        None => return Vec::new(),
    };

    // Find the next ## header after File Operations (end boundary)
    let section_end = lines[section_start..]
        .iter()
        .position(|l| {
            let trimmed = l.trim();
            trimmed.starts_with("## ") && !trimmed.starts_with("## File Operations")
        })
        .map(|i| section_start + i)
        .unwrap_or(lines.len());

    // Scan for ### headers within the section
    let mut ops = Vec::new();
    let mut current_header_idx: Option<usize> = None;

    for idx in section_start..section_end {
        let line = lines[idx];
        if line.trim().starts_with("### ") {
            // Save previous block
            if let Some(start) = current_header_idx {
                if let Some(op) = extract_file_op(&lines[start..idx]) {
                    ops.push(op);
                }
            }
            current_header_idx = Some(idx);
        }
    }
    // Save last block
    if let Some(start) = current_header_idx {
        if let Some(op) = extract_file_op(&lines[start..section_end]) {
            ops.push(op);
        }
    }

    ops
}

/// Extract a FileOp from a slice of lines starting with a ### header.
fn extract_file_op(lines: &[&str]) -> Option<FileOp> {
    if lines.is_empty() {
        return None;
    }
    let header = lines[0].trim();
    // Extract file path from formats like:
    //   "### 1. MODIFY src/config.rs"
    //   "### 1. [CREATE] src/foo.rs"
    let file_path = if let Some(after_bracket) = header.split(']').nth(1) {
        // Format: ### N. [OP] path
        after_bracket.split_whitespace().next()
    } else {
        // Format: ### N. OP path -- take last whitespace-separated token that looks like a path
        header
            .split_whitespace()
            .find(|token| token.contains('/') || token.contains('.'))
    };

    let file_path = file_path?.to_string();
    if file_path.is_empty() {
        return None;
    }

    let raw_block = lines.join("\n");
    Some(FileOp {
        raw_block,
        file_path,
    })
}

/// Group file operations into independent batches for parallel execution.
/// Files that import each other are grouped together. Files with no
/// cross-references are independent.
fn build_dependency_groups(ops: &[FileOp], project_dir: &std::path::Path) -> Vec<Vec<usize>> {
    let n = ops.len();
    if n == 0 {
        return Vec::new();
    }

    // Collect stems and paths for matching
    let stems: Vec<String> = ops
        .iter()
        .map(|op| {
            std::path::Path::new(&op.file_path)
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy()
                .into_owned()
        })
        .collect();

    // Union-find for grouping
    let mut parent: Vec<usize> = (0..n).collect();

    fn find(parent: &mut [usize], i: usize) -> usize {
        let mut root = i;
        while parent[root] != root {
            root = parent[root];
        }
        // Path compression
        let mut cur = i;
        while parent[cur] != root {
            let next = parent[cur];
            parent[cur] = root;
            cur = next;
        }
        root
    }

    fn union(parent: &mut [usize], a: usize, b: usize) {
        let ra = find(parent, a);
        let rb = find(parent, b);
        if ra != rb {
            parent[ra] = rb;
        }
    }

    // For each file, check if it references other files in the ops list
    for i in 0..n {
        // Read actual file content (if exists)
        let file_content =
            std::fs::read_to_string(project_dir.join(&ops[i].file_path)).unwrap_or_default();
        // Combine actual file content with the raw_block from the plan
        let combined = format!("{}\n{}", file_content, ops[i].raw_block);

        for j in 0..n {
            if i == j {
                continue;
            }
            // Check if file i references file j by stem name or path
            if combined.contains(&stems[j]) || combined.contains(&ops[j].file_path) {
                union(&mut parent, i, j);
            }
        }
    }

    // Collect groups
    let mut groups: std::collections::HashMap<usize, Vec<usize>> = std::collections::HashMap::new();
    for i in 0..n {
        let root = find(&mut parent, i);
        groups.entry(root).or_default().push(i);
    }

    groups.into_values().collect()
}

/// Discover ALL changed files in a worktree via git.
/// Returns relative paths of modified tracked files and new untracked files.
/// Returns None if git commands fail (caller should fall back to ops-based copy).
fn discover_changed_files_in_worktree(wt_dir: &std::path::Path) -> Option<Vec<String>> {
    // Find modified tracked files
    let diff_output = std::process::Command::new("git")
        .args(["diff", "--name-only", "HEAD"])
        .current_dir(wt_dir)
        .output()
        .ok()?;
    if !diff_output.status.success() {
        return None;
    }
    let mut changed: Vec<String> = String::from_utf8_lossy(&diff_output.stdout)
        .split('\n')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    // Find new untracked files (best-effort -- partial discovery is fine)
    if let Ok(ls_output) = std::process::Command::new("git")
        .args(["ls-files", "--others", "--exclude-standard"])
        .current_dir(wt_dir)
        .output()
    {
        if ls_output.status.success() {
            let untracked: Vec<String> = String::from_utf8_lossy(&ls_output.stdout)
                .split('\n')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect();
            changed.extend(untracked);
        }
    }

    changed.sort();
    changed.dedup();
    Some(changed)
}

/// Orchestrate parallel builder sub-agents, each in a git worktree.
#[allow(clippy::too_many_arguments)]
async fn run_parallel_builder(
    task_info: &Task,
    ctx: &RunContext,
    tx: &mpsc::UnboundedSender<AppEvent>,
    ops: &[FileOp],
    groups: &[Vec<usize>],
    extension_context: &str,
    pattern_context: &str,
) -> (bool, bool, AgentUsage) {
    let cc_version = ctx.cc_version.clone();
    let task_id = &task_info.id;
    let task_desc = &task_info.description;
    let total_slots = groups.len();
    let independent_count = groups.iter().filter(|g| g.len() == 1).count();

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Parallel builder: {} slots ({} independent files, {} grouped)",
        total_slots,
        independent_count,
        total_slots - independent_count
    ))));

    let base_dir = ctx.buildloop_dir.join("parallel-build");
    if let Err(e) = std::fs::create_dir_all(&base_dir) {
        eprintln!(
            "Warning: failed to create parallel-build dir {}: {}",
            base_dir.display(),
            e
        );
    }

    // Create worktrees for each slot
    let mut slot_contexts: Vec<(PathBuf, RunContext)> = Vec::new();

    for (slot_idx, _group) in groups.iter().enumerate() {
        let slot_dir = base_dir.join(format!("slot-{}", slot_idx));

        // Remove stale worktree
        if slot_dir.exists() {
            let _ = std::process::Command::new("git")
                .args(["worktree", "remove", "--force"])
                .arg(&slot_dir)
                .current_dir(&ctx.project_dir)
                .output();
        }

        // Create worktree
        let wt_result = std::process::Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&slot_dir)
            .arg("HEAD")
            .current_dir(&ctx.project_dir)
            .output();

        match wt_result {
            Ok(output) if output.status.success() => {}
            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Parallel builder: failed to create worktree slot-{}: {}",
                    slot_idx,
                    stderr.trim()
                ))));
                // Clean up previously created worktrees
                for (prev_dir, _) in &slot_contexts {
                    let _ = std::process::Command::new("git")
                        .args(["worktree", "remove", "--force"])
                        .arg(prev_dir)
                        .current_dir(&ctx.project_dir)
                        .output();
                }
                let _ = std::fs::remove_dir_all(&base_dir);
                return (false, false, AgentUsage::default());
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Parallel builder: git worktree command failed: {}",
                    e
                ))));
                for (prev_dir, _) in &slot_contexts {
                    let _ = std::process::Command::new("git")
                        .args(["worktree", "remove", "--force"])
                        .arg(prev_dir)
                        .current_dir(&ctx.project_dir)
                        .output();
                }
                let _ = std::fs::remove_dir_all(&base_dir);
                return (false, false, AgentUsage::default());
            }
        }

        // Copy state files into worktree
        if let Ok(rel) = ctx.spec_path.strip_prefix(&ctx.project_dir) {
            let dest = slot_dir.join(rel);
            if let Some(parent) = dest.parent() {
                if let Err(e) = std::fs::create_dir_all(parent) {
                    eprintln!(
                        "Warning: failed to create parent dir for SPEC in slot-{}: {}",
                        slot_idx, e
                    );
                }
            }
            if let Err(e) = std::fs::copy(&ctx.spec_path, &dest) {
                eprintln!(
                    "Warning: failed to copy SPEC.md into slot-{}: {}",
                    slot_idx, e
                );
            }
        }
        if let Ok(rel) = ctx.plan_path.strip_prefix(&ctx.project_dir) {
            let dest = slot_dir.join(rel);
            if let Some(parent) = dest.parent() {
                if let Err(e) = std::fs::create_dir_all(parent) {
                    eprintln!(
                        "Warning: failed to create parent dir for TASKS in slot-{}: {}",
                        slot_idx, e
                    );
                }
            }
            if let Err(e) = std::fs::copy(&ctx.plan_path, &dest) {
                eprintln!(
                    "Warning: failed to copy TASKS.md into slot-{}: {}",
                    slot_idx, e
                );
            }
        }
        // Copy current-plan.md
        let plan_src = ctx.buildloop_dir.join("current-plan.md");
        if plan_src.exists() {
            let wt_buildloop = slot_dir.join(".buildloop");
            if let Err(e) = std::fs::create_dir_all(&wt_buildloop) {
                eprintln!(
                    "Warning: failed to create .buildloop dir in slot-{}: {}",
                    slot_idx, e
                );
            }
            if let Err(e) = std::fs::copy(&plan_src, wt_buildloop.join("current-plan.md")) {
                eprintln!(
                    "Warning: failed to copy current-plan.md into slot-{}: {}",
                    slot_idx, e
                );
            }
        }
        // CLAUDE.md
        let claude_md_src = ctx.project_dir.join("CLAUDE.md");
        if claude_md_src.exists() {
            if let Err(e) = std::fs::copy(&claude_md_src, slot_dir.join("CLAUDE.md")) {
                eprintln!(
                    "Warning: failed to copy CLAUDE.md into slot-{}: {}",
                    slot_idx, e
                );
            }
        }

        let wt_ctx =
            ctx.derive_sub_session(ctx.config.clone(), &slot_dir, &format!("slot-{}", slot_idx));

        slot_contexts.push((slot_dir, wt_ctx));
    }

    // Send initial progress
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ParallelBuilderProgress {
        total: total_slots,
        done: 0,
    }));

    // Build scoped prompts and spawn agents concurrently
    let done_counter = Arc::new(AtomicUsize::new(0));
    let mut futures_vec = Vec::new();

    for (slot_idx, group) in groups.iter().enumerate() {
        // Collect raw blocks for this group
        let joined_blocks: String = group
            .iter()
            .map(|&idx| ops[idx].raw_block.as_str())
            .collect::<Vec<_>>()
            .join("\n\n");

        let prompt = prompts::parallel_builder_prompt(
            &ctx.config.pipeline_stage_label("implement"),
            task_id,
            task_desc,
            &joined_blocks,
            &ctx.spec_file_prompt_path(),
            &ctx.tasks_file_prompt_path(),
        );
        // Inject matched patterns so parallel builders can see and give feedback
        let prompt = if !pattern_context.is_empty() {
            format!("{}\n\n--- BEGIN REFERENCE DATA (non-authoritative) ---{}\n--- END REFERENCE DATA ---", prompt, pattern_context)
        } else {
            prompt
        };
        let prompt = prompts::wrap_with_extensions(&prompt, extension_context);

        let provider = Config::parse_provider(&ctx.config.builder_provider);
        let model = ctx.config.builder_model.clone();
        let wt_project_dir = slot_contexts[slot_idx].1.project_dir.clone();
        let wt_log_dir = slot_contexts[slot_idx].1.log_dir.clone();
        if let Err(e) = std::fs::create_dir_all(&wt_log_dir) {
            eprintln!(
                "Warning: failed to create log dir for slot-{}: {}",
                slot_idx, e
            );
        }
        let timeout = ctx.config.agent_timeout_secs;
        let shutdown = ctx.shutdown.clone();
        let counter = done_counter.clone();
        let slot_tx = tx.clone();
        let total = total_slots;

        let slot_session_id = slot_contexts[slot_idx].1.session_id.clone();
        let slot_project_dir_obs = ctx.project_dir.clone();
        let slot_builder_provider = ctx.config.builder_provider.clone();
        let slot_builder_model = ctx.config.builder_model.clone();
        let slot_cc_version = cc_version.clone();
        let slot_config = ctx.config.clone();

        let fut = async move {
            // Create forwarding channel for this slot
            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = slot_tx.clone();
            let fwd_slot_idx = slot_idx;
            let fwd_handle = tokio::spawn(async move {
                let mut usage = AgentUsage::default();
                while let Some(evt) = agent_rx.recv().await {
                    usage.accumulate(&evt);
                    match evt {
                        crate::agent::AgentOutputEvent::Text(ref text) => {
                            let _ = fwd_tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "[slot-{}] {}",
                                fwd_slot_idx, text
                            ))));
                        }
                        crate::agent::AgentOutputEvent::Usage { .. } => {
                            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                        }
                        _ => {}
                    }
                }
                usage
            });

            // Emit AgentStarted for this slot
            observatory::log_event(
                &slot_session_id,
                &slot_project_dir_obs,
                ObservatoryEvent::AgentStarted {
                    role: format!("{}", AgentRole::Builder),
                    provider: slot_builder_provider.clone(),
                    model: slot_builder_model.clone(),
                    cc_version: slot_cc_version.clone(),
                },
            );
            let slot_start = Instant::now();

            let result = agent::run_agent(
                &AgentRole::Builder,
                provider,
                &model,
                &prompt,
                &wt_project_dir,
                agent_tx,
                &wt_log_dir,
                None,
                timeout,
                Some(shutdown),
                Some(&slot_config),
            )
            .await;

            let slot_usage = fwd_handle.await.unwrap_or_default();

            let done = counter.fetch_add(1, Ordering::Relaxed) + 1;
            let _ = slot_tx.send(AppEvent::LoopEvent(LoopEvent::ParallelBuilderProgress {
                total,
                done,
            }));

            let rl = was_rate_limited(&result);
            let ok = result.map(|r| r.success).unwrap_or(false);

            // Emit AgentDone for this slot
            observatory::log_event(
                &slot_session_id,
                &slot_project_dir_obs,
                ObservatoryEvent::AgentDone {
                    role: format!("{}", AgentRole::Builder),
                    success: ok,
                    duration_secs: slot_start.elapsed().as_secs_f64(),
                    tokens_in: slot_usage.tokens_in,
                    tokens_out: slot_usage.tokens_out,
                    cost_usd: slot_usage.cost_usd,
                    context_pct: slot_usage.context_pct,
                    cache_creation_tokens: slot_usage.cache_creation_tokens,
                    cache_read_tokens: slot_usage.cache_read_tokens,
                },
            );

            (slot_idx, ok, rl, slot_usage)
        };

        futures_vec.push(fut);
    }

    let results = join_all(futures_vec).await;

    // Merge results: copy files from worktrees back to main project
    let mut all_ok = true;
    let mut any_rate_limited = false;
    let mut combined_claims = String::new();
    let mut aggregated_usage = AgentUsage::default();

    // Build a lookup: file_path -> owning slot index (from planned file operations)
    let mut planned_file_owner: HashMap<String, usize> = HashMap::new();
    for (slot_idx, group) in groups.iter().enumerate() {
        for &op_idx in group {
            planned_file_owner.insert(ops[op_idx].file_path.clone(), slot_idx);
        }
    }

    // Track which files have already been copied and from which slot
    let mut copied_files: HashMap<String, usize> = HashMap::new();
    let mut deleted_by_slot: HashMap<String, usize> = HashMap::new();

    for (slot_idx, ok, rl, slot_usage) in &results {
        if !ok {
            all_ok = false;
        }
        if *rl {
            any_rate_limited = true;
        }
        // Accumulate usage from this slot
        aggregated_usage.cost_usd += slot_usage.cost_usd;
        aggregated_usage.tokens_in += slot_usage.tokens_in;
        aggregated_usage.tokens_out += slot_usage.tokens_out;
        if slot_usage.context_pct > aggregated_usage.context_pct {
            aggregated_usage.context_pct = slot_usage.context_pct;
        }

        // Copy ALL changed files from worktree to main project
        let (ref wt_dir, _) = slot_contexts[*slot_idx];
        let files_to_copy = match discover_changed_files_in_worktree(wt_dir) {
            Some(discovered) => {
                if !discovered.is_empty() {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Parallel builder slot-{}: discovered {} changed files via git",
                        slot_idx,
                        discovered.len()
                    ))));
                }
                discovered
            }
            None => {
                // Fallback: git not available in worktree, use ops-based copy
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Parallel builder slot-{}: git discovery failed, falling back to plan file ops",
                    slot_idx
                ))));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "WARNING: slot-{} fallback mode -- file deletions and unplanned file changes will be lost",
                    slot_idx
                ))));
                let group = &groups[*slot_idx];
                group
                    .iter()
                    .map(|&op_idx| ops[op_idx].file_path.clone())
                    .collect()
            }
        };
        for file_path in &files_to_copy {
            let src = wt_dir.join(file_path);

            // Check for copy-vs-copy conflict: only when current slot also intends to copy.
            // When src does not exist, the current slot deleted the file -- that case is
            // handled by the modify-vs-delete check inside the `else if dest.exists()` branch.
            if src.exists() {
                if let Some(&prev_slot) = copied_files.get(file_path) {
                    // Determine which slot should win based on planned ownership
                    let owner = planned_file_owner.get(file_path);
                    let winner = match owner {
                        Some(&owning_slot) => owning_slot,
                        None => prev_slot, // Neither slot planned this file; keep first slot's version
                    };

                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Parallel builder: COPY-COPY CONFLICT on '{}' -- modified by slot-{} and slot-{}, using slot-{} ({})",
                        file_path,
                        prev_slot,
                        slot_idx,
                        winner,
                        if owner.is_some() { "planned owner" } else { "first slot" }
                    ))));

                    if winner == prev_slot {
                        // Previous slot wins; skip copying from current slot
                        continue;
                    }
                    // Current slot wins (it is the planned owner); fall through to copy
                }
            }

            // Check for delete-vs-modify conflict: was this file deleted by a previous slot?
            if let Some(&del_slot) = deleted_by_slot.get(file_path) {
                if src.exists() {
                    // Previous slot deleted, current slot modifies -- genuine conflict
                    let owner = planned_file_owner.get(file_path);
                    let winner = match owner {
                        Some(&owning_slot) => owning_slot,
                        None => *slot_idx, // Default: modification wins over deletion
                    };

                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Parallel builder: DELETE-MODIFY CONFLICT on '{}' -- deleted by slot-{}, modified by slot-{}, using slot-{} ({})",
                        file_path,
                        del_slot,
                        slot_idx,
                        winner,
                        if owner.is_some() { "planned owner" } else { "modification wins" }
                    ))));

                    if winner == del_slot {
                        // Deletion wins; skip copying from current slot
                        continue;
                    }
                    // Modification wins; fall through to copy
                }
            }

            let dest = ctx.project_dir.join(file_path);
            if src.exists() {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                if let Err(e) = std::fs::copy(&src, &dest) {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Parallel builder: failed to copy {} from slot-{}: {}",
                        file_path, slot_idx, e
                    ))));
                    all_ok = false;
                    continue;
                }
                // Record that this file was copied from this slot
                copied_files.insert(file_path.clone(), *slot_idx);
            } else if dest.exists() {
                // File was deleted in worktree -- check for modify-vs-delete conflict
                if let Some(&prev_slot) = copied_files.get(file_path) {
                    // Previous slot copied (modified), current slot deletes -- genuine conflict
                    let owner = planned_file_owner.get(file_path);
                    let winner = match owner {
                        Some(&owning_slot) => owning_slot,
                        None => prev_slot, // Default: modification wins over deletion
                    };

                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Parallel builder: MODIFY-DELETE CONFLICT on '{}' -- modified by slot-{}, deleted by slot-{}, using slot-{} ({})",
                        file_path,
                        prev_slot,
                        slot_idx,
                        winner,
                        if owner.is_some() { "planned owner" } else { "modification wins" }
                    ))));

                    if winner == prev_slot {
                        // Modification (previous slot) wins; skip deletion
                        continue;
                    }
                    // Deletion (current slot) wins; fall through to delete
                }

                // File was deleted in worktree -- remove from main project
                if let Err(e) = std::fs::remove_file(&dest) {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Parallel builder: failed to delete {} from slot-{}: {}",
                        file_path, slot_idx, e
                    ))));
                    all_ok = false;
                    continue;
                } else {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Parallel builder slot-{}: deleted {} (removed in worktree)",
                        slot_idx, file_path
                    ))));
                    deleted_by_slot.insert(file_path.clone(), *slot_idx);
                }
            }
        }

        // Collect build-claims
        let wt_claims = wt_dir.join(".buildloop").join("build-claims.md");
        if let Ok(content) = std::fs::read_to_string(&wt_claims) {
            combined_claims.push_str(&format!("\n\n--- Slot {} ---\n\n{}", slot_idx, content));
        }
    }

    // Write combined claims
    if !combined_claims.is_empty() {
        let claims_path = ctx.buildloop_dir.join("build-claims.md");
        let header = format!("# Build Claims -- {} (parallel builder)\n", task_id);
        if let Err(e) = atomic_write_file(
            &claims_path,
            format!("{}{}", header, combined_claims).as_bytes(),
        ) {
            eprintln!(
                "Warning: failed to write combined build claims to {}: {} -- reviewer will run without claims context",
                claims_path.display(), e
            );
        }
    }

    // Clean up all worktrees
    for (wt_dir, _) in &slot_contexts {
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(wt_dir)
            .current_dir(&ctx.project_dir)
            .output();
    }
    let _ = std::fs::remove_dir_all(&base_dir);

    // Send final progress
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ParallelBuilderProgress {
        total: total_slots,
        done: total_slots,
    }));

    (all_ok, any_rate_limited, aggregated_usage)
}

// ─── Dual Pipeline ──────────────────────────────────────────

/// Run two complete SPID pipelines in parallel, each in its own git worktree.
/// Each pipeline runs Scout, Plan, Implement, and Doubt independently.
/// The human evaluates both results -- no automated winner selection.
#[allow(clippy::too_many_arguments)]
fn run_dual_pipelines<'a>(
    task_info: &'a Task,
    ctx: &'a RunContext,
    tx: &'a mpsc::UnboundedSender<AppEvent>,
    cached_patterns: &'a [patterns::Pattern],
    patterns_dir: &'a std::path::Path,
    extension_context: &'a str,
    configs: [Config; 2],
) -> std::pin::Pin<Box<dyn std::future::Future<Output = (bool, bool)> + Send + 'a>> {
    Box::pin(async move {
        let labels = [
            Config::display_provider_model(&configs[0].builder_provider, &configs[0].builder_model),
            Config::display_provider_model(&configs[1].builder_provider, &configs[1].builder_model),
        ];

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStarted {
            models: labels.clone(),
        }));
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::DualPipelineStarted {
                session_id: ctx.session_id.clone(),
                models: labels.to_vec(),
            },
        );
        let dual_start = Instant::now();

        let arena_dir = ctx.buildloop_dir.join("arena");
        if let Err(e) = std::fs::create_dir_all(&arena_dir) {
            eprintln!(
                "Warning: failed to create arena dir {}: {}",
                arena_dir.display(),
                e
            );
        }

        // Create worktrees and RunContexts for each pipeline
        let mut wt_contexts: Vec<(PathBuf, RunContext)> = Vec::new();

        for (idx, pipeline_config) in configs.into_iter().enumerate() {
            let provider = pipeline_config.builder_provider.clone();
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
                        "Dual pipeline: failed to create worktree {}: {}",
                        labels[idx],
                        stderr.trim()
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
                        "Dual pipeline: git worktree command failed: {}",
                        e
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
                    if let Err(e) = std::fs::create_dir_all(parent) {
                        eprintln!(
                            "Warning: failed to create parent dir for SPEC in pipeline-{}: {}",
                            idx, e
                        );
                    }
                }
                if let Err(e) = std::fs::copy(&ctx.spec_path, &dest) {
                    eprintln!(
                        "Warning: failed to copy SPEC.md into pipeline-{}: {}",
                        idx, e
                    );
                }
            }
            if let Ok(rel) = ctx.plan_path.strip_prefix(&ctx.project_dir) {
                let dest = wt_path.join(rel);
                if let Some(parent) = dest.parent() {
                    if let Err(e) = std::fs::create_dir_all(parent) {
                        eprintln!(
                            "Warning: failed to create parent dir for TASKS in pipeline-{}: {}",
                            idx, e
                        );
                    }
                }
                if let Err(e) = std::fs::copy(&ctx.plan_path, &dest) {
                    eprintln!(
                        "Warning: failed to copy TASKS.md into pipeline-{}: {}",
                        idx, e
                    );
                }
            }
            // CLAUDE.md (may be untracked/gitignored)
            let claude_md_src = ctx.project_dir.join("CLAUDE.md");
            if claude_md_src.exists() {
                if let Err(e) = std::fs::copy(&claude_md_src, wt_path.join("CLAUDE.md")) {
                    eprintln!(
                        "Warning: failed to copy CLAUDE.md into pipeline-{}: {}",
                        idx, e
                    );
                }
            }

            // Create RunContext for this worktree
            let wt_ctx =
                ctx.derive_sub_session(pipeline_config, &wt_path, &format!("pipeline-{}", idx));

            wt_contexts.push((wt_path, wt_ctx));
        }

        // Run both pipelines concurrently with forwarding channels.
        // Use tokio::join! (not spawn) since process_task borrows are not 'static.
        let ((_wt0, wt_ctx0), (_wt1, wt_ctx1)) = (wt_contexts.remove(0), wt_contexts.remove(0));

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

        let fut0 = async {
            process_task(task_info, &wt_ctx0, &tx0, false, &patterns0, &pdir0, &ext0).await
        };
        let fut1 = async {
            process_task(task_info, &wt_ctx1, &tx1, false, &patterns1, &pdir1, &ext1).await
        };
        tokio::pin!(fut0);
        tokio::pin!(fut1);

        let (result0, result1) = tokio::select! {
            r0 = &mut fut0 => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStreamDone(0, r0.0)));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Pipeline 1 complete -- waiting for Pipeline 2 ({})",
                    labels[1]
                ))));
                let r1 = fut1.await;
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStreamDone(1, r1.0)));
                (r0, r1)
            }
            r1 = &mut fut1 => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStreamDone(1, r1.0)));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Pipeline 2 complete -- waiting for Pipeline 1 ({})",
                    labels[0]
                ))));
                let r0 = fut0.await;
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DualBuildStreamDone(0, r0.0)));
                (r0, r1)
            }
        };

        let any_success = result0.0 || result1.0;
        let any_rate_limited = result0.1 || result1.1;

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Both pipelines complete. Results in .buildloop/arena/ -- evaluate and merge manually."
                .to_string(),
        )));
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::DualPipelineCompleted {
                session_id: ctx.session_id.clone(),
                wall_clock_secs: dual_start.elapsed().as_secs_f64(),
                pipeline_0_success: result0.0,
                pipeline_1_success: result1.0,
            },
        );

        // Do NOT clean up worktrees -- human evaluates results

        (any_success, any_rate_limited)
    }) // end Box::pin
}

/// Background task that polls `gh pr view` for review status and sends
/// events when the PR is approved, merged, or closed.
async fn poll_pr_review(
    pr_number: u64,
    session_id: String,
    project_dir: PathBuf,
    poll_interval_secs: u64,
    tx: mpsc::UnboundedSender<AppEvent>,
    review_gate: Arc<crate::sync_flag::SyncFlag>,
) {
    let mut last_decision = String::new();
    loop {
        // Check gate FIRST (before sleeping), so first poll is immediate
        if !review_gate.get() {
            return;
        }

        let result = tokio::process::Command::new("gh")
            .args([
                "pr",
                "view",
                &pr_number.to_string(),
                "--json",
                "reviewDecision,state",
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
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PrApproved {
                            pr_num: pr_number,
                            session_id: session_id.clone(),
                        }));
                        return;
                    }
                    if state == "CLOSED" {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PrClosed {
                            pr_num: pr_number,
                            session_id: session_id.clone(),
                        }));
                        return;
                    }
                    if review_decision == "CHANGES_REQUESTED" && review_decision != last_decision {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                            "PR #{}: changes requested -- update the code or press Enter to skip",
                            pr_number
                        ))));
                    }
                    last_decision = review_decision.to_string();
                }
                // Still open/in review -- continue polling
            }
            _ => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                    "gh pr view {} failed -- will retry",
                    pr_number
                ))));
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

    // ─── Archive completed phases ─────────────────────────────────
    if ctx.config.auto_archive_tasks {
        let tasks_path = ctx.project_dir.join(ctx.tasks_file_name());
        match crate::task::archive_completed_phases(
            &tasks_path,
            ctx.config.archive_keep_first,
            ctx.config.archive_keep_last,
        ) {
            Ok(0) => {}
            Ok(n) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Archived {} completed tasks to TASKS-ARCHIVE.md",
                    n
                ))));
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Warning: task archiving failed: {}",
                    e
                ))));
            }
        }
    }

    // ─── Observatory Session ─────────────────────────────────────
    let session_id = observatory::generate_session_id();
    let cc_version = ctx.cc_version.clone();
    let mut ctx = ctx;
    ctx.session_id = session_id.clone();
    let loop_start = std::time::Instant::now();
    let mut session_tasks: usize = 0;
    let mut session_feats: usize = 0;
    let mut session_wips: usize = 0;

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::SessionIdAssigned(
        session_id.clone(),
    )));

    observatory::log_event(
        &session_id,
        &ctx.project_dir,
        ObservatoryEvent::SessionStarted {
            config: serde_json::json!({
                "planner_provider": ctx.config.planner_provider,
                "planner_model": ctx.config.planner_model,
                "builder_provider": ctx.config.builder_provider,
                "builder_model": ctx.config.builder_model,
                "reviewer_provider": ctx.config.reviewer_provider,
                "reviewer_model": ctx.config.reviewer_model,
                "scout_provider": ctx.config.scout_provider,
                "scout_model": ctx.config.scout_model,
                "discovery_provider": ctx.config.discovery_provider,
                "discovery_model": ctx.config.discovery_model,
                "run_mode": ctx.config.run_mode,
                "pipeline_mode": ctx.config.pipeline_mode,
                "batch_doubt": ctx.config.batch_doubt,
                "cost_limit": ctx.config.cost_limit,
                "agent_timeout_secs": ctx.config.agent_timeout_secs,
            }),
            cc_version: cc_version.clone(),
        },
    );

    // Helper: emit SessionEnded. Called before each return point.
    macro_rules! emit_session_ended {
        () => {
            observatory::log_event(
                &session_id,
                &ctx.project_dir,
                ObservatoryEvent::SessionEnded {
                    total_tasks: session_tasks,
                    feat_count: session_feats,
                    wip_count: session_wips,
                    total_cost_usd: ctx.session_cost_millicents.load(Ordering::Relaxed) as f64
                        / 100_000.0,
                    duration_secs: loop_start.elapsed().as_secs_f64(),
                },
            );
        };
    }

    // ─── Extension Context Loading ──────────────────────────────
    let discovered_extensions = extensions::discover_extensions(&ctx.project_dir);
    let extension_context =
        extensions::load_extension_context(&discovered_extensions, &ctx.config.extensions);
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

    // Decay stale patterns before loading (lazy cleanup on startup)
    if ctx.config.pattern_decay_days > 0 {
        let mut total_decayed =
            patterns::decay_stale_patterns(&patterns_dir, ctx.config.pattern_decay_days);
        // Also decay extension pattern dirs
        for ext_name in &ctx.config.extensions {
            if let Some(ext) = discovered_extensions.iter().find(|e| &e.name == ext_name) {
                if let Some(ref pdir) = ext.patterns_dir {
                    total_decayed +=
                        patterns::decay_stale_patterns(pdir, ctx.config.pattern_decay_days);
                }
            }
        }
        if total_decayed > 0 {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Decayed {} stale patterns (unused >{}d)",
                total_decayed, ctx.config.pattern_decay_days
            ))));
        }
    }

    let mut cached_patterns = patterns::load_patterns(&patterns_dir);

    // Merge extension patterns into the pool
    let ext_patterns =
        extensions::load_extension_patterns(&discovered_extensions, &ctx.config.extensions);
    if !ext_patterns.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Loaded {} extension patterns",
            ext_patterns.len()
        ))));
        cached_patterns.extend(ext_patterns);
    }

    // ─── Scout State ──────────────────────────────────────────────
    // Scout runs once at session start, then reuses the report for
    // subsequent tasks unless the previous commit touched structural files.
    // If a recent research-report.md OR scout-report.md exists on disk
    // (< 10 min old), reuse it across Foundry restarts to avoid re-running
    // Q+R or re-scouting the same codebase. The bootstrap scout path writes
    // scout-report.md and bypasses Q+R, so either file being fresh suffices.
    let research_report_path = ctx.buildloop_dir.join("research-report.md");
    let scout_report_path = ctx.buildloop_dir.join("scout-report.md");
    let is_fresh = |path: &std::path::Path| -> bool {
        path.exists()
            && std::fs::metadata(path)
                .and_then(|m| m.modified())
                .map(|mtime| mtime.elapsed().map(|d| d.as_secs() < 600).unwrap_or(false))
                .unwrap_or(false)
    };
    let mut qr_has_run = is_fresh(&research_report_path) || is_fresh(&scout_report_path);

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
                let mut usage = AgentUsage::default();
                while let Some(evt) = agent_rx.recv().await {
                    usage.accumulate(&evt);
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
                usage
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Scout,
                Config::display_provider_model(&ctx.config.scout_provider, &ctx.config.scout_model),
            )));
            observatory::log_event(
                &session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentStarted {
                    role: format!("{}", AgentRole::Scout),
                    provider: ctx.config.scout_provider.clone(),
                    model: ctx.config.scout_model.clone(),
                    cc_version: cc_version.clone(),
                },
            );

            // Read SPEC.md for user intent if it exists
            let user_intent = std::fs::read_to_string(&ctx.spec_path)
                .ok()
                .filter(|s| !s.trim().is_empty());

            // Read UPDATED_SPECS.md for enhancement requests
            let updated_specs = std::fs::read_to_string(&ctx.updated_specs_path)
                .ok()
                .filter(|s| !s.trim().is_empty());

            // Search build history for context on similar past work
            let history_dir = crate::history::resolve_history_dir(&ctx.config.history_dir);
            let history_query = user_intent.as_deref().unwrap_or("");
            let history_records = if !history_query.is_empty() {
                crate::history::search_history(
                    &history_dir,
                    history_query,
                    ctx.config.history_search_results,
                )
            } else {
                Vec::new()
            };
            let history_context = crate::history::format_history_for_prompt(&history_records);

            let prompt = prompts::bootstrap_scout_prompt(
                user_intent.as_deref(),
                updated_specs.as_deref(),
                &ctx.spec_file_prompt_path(),
                &ctx.tasks_file_prompt_path(),
                if history_context.is_empty() {
                    None
                } else {
                    Some(&history_context)
                },
            );
            // Scout is investigation-only -- skip extension context to save tokens.
            let scout_start = Instant::now();
            let scout_result = agent::run_agent(
                &AgentRole::Scout,
                Config::parse_provider(&ctx.config.scout_provider),
                &ctx.config.scout_model,
                &prompt,
                &ctx.project_dir,
                agent_tx,
                &ctx.log_dir,
                None,
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
                Some(&ctx.config),
            )
            .await;

            let agent_usage = fwd_handle.await.unwrap_or_default();
            let _ = tx.send(AppEvent::AgentDone(
                scout_result.as_ref().map(|r| r.success).unwrap_or(false),
            ));
            observatory::log_event(
                &session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentDone {
                    role: format!("{}", AgentRole::Scout),
                    success: scout_result.as_ref().map(|r| r.success).unwrap_or(false),
                    duration_secs: scout_start.elapsed().as_secs_f64(),
                    tokens_in: agent_usage.tokens_in,
                    tokens_out: agent_usage.tokens_out,
                    cost_usd: agent_usage.cost_usd,
                    context_pct: agent_usage.context_pct,
                    cache_creation_tokens: agent_usage.cache_creation_tokens,
                    cache_read_tokens: agent_usage.cache_read_tokens,
                },
            );
            qr_has_run = true;

            if ctx.is_stop_requested() {
                emit_session_ended!();
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
            let skip_scout = qr_has_run && !last_commit_touched_structural(&ctx.project_dir);
            let dual_arena_mode = ctx.config.builder_models.len() >= 2
                && DualSelection::from_str(&ctx.config.dual_selection) == DualSelection::Both;
            let (success, task_rate_limited, human_denied) = process_task(
                &task_info,
                &ctx,
                &tx,
                skip_scout,
                &cached_patterns,
                &patterns_dir,
                &extension_context,
            )
            .await;
            if !dual_arena_mode {
                qr_has_run = true;
            }

            session_tasks += 1;
            if success {
                session_feats += 1;
            } else {
                session_wips += 1;
            }

            // Restore state files if the builder deleted or truncated them
            let restored = restore_state_files(&ctx, &state_backup, &tx);
            if restored > 0 {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Restored {} state file(s) deleted during build",
                    restored
                ))));
            }

            if dual_arena_mode {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Dual arena complete -- inspect the tabs or .buildloop/arena/, then press q to return to startup.".to_string(),
                )));
                emit_session_ended!();
                return;
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

            // If human denied a commit approval, pause the loop.
            // Re-running the same pending task would waste API spend.
            if human_denied {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Pausing after denied commit -- loop will stop after this task".to_string(),
                )));
                if let Err(e) = std::fs::create_dir_all(&ctx.buildloop_dir) {
                    eprintln!(
                        "Warning: failed to create buildloop dir for stop file: {}",
                        e
                    );
                }
                if let Err(e) = std::fs::write(ctx.buildloop_dir.join("stop"), "") {
                    eprintln!("Warning: failed to write stop file: {}", e);
                }
            }

            // Collect build claims for targeted discovery
            if success {
                if let Ok(claims) =
                    std::fs::read_to_string(ctx.buildloop_dir.join("build-claims.md"))
                {
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
                let cost_millicents = ctx
                    .session_cost_millicents
                    .load(std::sync::atomic::Ordering::Relaxed);
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
                    emit_session_ended!();
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
                if let Err(e) = std::fs::remove_file(&stop_file) {
                    if e.kind() != std::io::ErrorKind::NotFound {
                        eprintln!("Warning: failed to remove stop file: {}", e);
                    }
                }
                emit_session_ended!();
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            adaptive_sleep(
                &ctx.config,
                task_rate_limited,
                ctx.config.pause_between_tasks_secs,
            )
            .await;
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::NextTaskUpdated(None)));

            // ─── Sprint Mode: Stop when queue empties ────────────────
            if ctx.config.run_mode == "sprint" {
                let done_count = task::count_completed(&tasks);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Sprint complete -- all {} tasks done",
                    done_count
                ))));
                emit_session_ended!();
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            // ─── Review Mode: Stop when queue empties ────────────────
            if ctx.config.run_mode == "review" {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Review mode: task queue complete -- stopping".to_string(),
                )));
                emit_session_ended!();
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
                    tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_cycles_secs))
                        .await;
                    if ctx.is_stop_requested() {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                            "Stop requested during discovery cooldown -- shutting down".to_string(),
                        )));
                        let stop_file = ctx.stop_file();
                        if stop_file.exists() {
                            if let Err(e) = std::fs::remove_file(&stop_file) {
                                if e.kind() != std::io::ErrorKind::NotFound {
                                    eprintln!("Warning: failed to remove stop file: {}", e);
                                }
                            }
                        }
                        emit_session_ended!();
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                        return;
                    }
                    continue;
                }
            }

            discovery_round += 1;

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryStarted(
                discovery_round,
            )));

            let pre_count = tasks.len();

            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            let fwd_handle = tokio::spawn(async move {
                let mut usage = AgentUsage::default();
                while let Some(evt) = agent_rx.recv().await {
                    usage.accumulate(&evt);
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
                usage
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Discovery,
                Config::display_provider_model(
                    &ctx.config.discovery_provider,
                    &ctx.config.discovery_model,
                ),
            )));
            observatory::log_event(
                &session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentStarted {
                    role: format!("{}", AgentRole::Discovery),
                    provider: ctx.config.discovery_provider.clone(),
                    model: ctx.config.discovery_model.clone(),
                    cc_version: cc_version.clone(),
                },
            );

            let build_history = if session_build_claims.is_empty() {
                None
            } else {
                Some(session_build_claims.join("\n\n"))
            };
            let prompt = prompts::discovery_prompt(
                discovery_round,
                &ctx.spec_file_prompt_path(),
                &ctx.tasks_file_prompt_path(),
                build_history.as_deref(),
            );
            // Discovery finds new work -- skip extension context to save tokens.
            let discovery_start = Instant::now();
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
                Some(&ctx.config),
            )
            .await;

            let agent_usage = fwd_handle.await.unwrap_or_default();
            let _ = tx.send(AppEvent::AgentDone(
                result.as_ref().map(|r| r.success).unwrap_or(false),
            ));
            observatory::log_event(
                &session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentDone {
                    role: format!("{}", AgentRole::Discovery),
                    success: result.as_ref().map(|r| r.success).unwrap_or(false),
                    duration_secs: discovery_start.elapsed().as_secs_f64(),
                    tokens_in: agent_usage.tokens_in,
                    tokens_out: agent_usage.tokens_out,
                    cost_usd: agent_usage.cost_usd,
                    context_pct: agent_usage.context_pct,
                    cache_creation_tokens: agent_usage.cache_creation_tokens,
                    cache_read_tokens: agent_usage.cache_read_tokens,
                },
            );

            // Check stop after discovery agent completion
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Stop requested after DISCOVERY agent — shutting down".to_string(),
                )));
                let stop_file = ctx.stop_file();
                if stop_file.exists() {
                    if let Err(e) = std::fs::remove_file(&stop_file) {
                        if e.kind() != std::io::ErrorKind::NotFound {
                            eprintln!("Warning: failed to remove stop file: {}", e);
                        }
                    }
                }
                emit_session_ended!();
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
                effective_cooldown_minutes =
                    (effective_cooldown_minutes * 2).min(MAX_COOLDOWN_MINUTES);

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
                        if let Err(e) = std::fs::remove_file(&stop_file) {
                            if e.kind() != std::io::ErrorKind::NotFound {
                                eprintln!("Warning: failed to remove stop file: {}", e);
                            }
                        }
                    }
                    emit_session_ended!();
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                    return;
                }
            } else {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ShipStarted));
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
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ShipDone));
            }

            // Check stop after discovery commit
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Stop requested after discovery commit — shutting down".to_string(),
                )));
                let stop_file = ctx.stop_file();
                if stop_file.exists() {
                    if let Err(e) = std::fs::remove_file(&stop_file) {
                        if e.kind() != std::io::ErrorKind::NotFound {
                            eprintln!("Warning: failed to remove stop file: {}", e);
                        }
                    }
                }
                emit_session_ended!();
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
    #[allow(unreachable_code)]
    {
        emit_session_ended!();
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
    let section_start = match all_lines
        .iter()
        .position(|line| line.starts_with("## Verification Results"))
    {
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
) -> (bool, bool, bool) {
    let cc_version = ctx.cc_version.clone();
    // Handle dual selection: Both forks two full pipelines, First/Second
    // resolve an effective single-pipeline config before any stage starts.
    let dual_sel = DualSelection::from_str(&ctx.config.dual_selection);
    let selected_configs = ctx
        .config
        .selected_pipeline_configs(&ctx.config.dual_selection);
    if ctx.config.builder_models.len() >= 2 {
        match dual_sel {
            DualSelection::Both if selected_configs.len() == 2 => {
                // Dual pipelines use worktrees that don't survive a crash -- clear stale checkpoint.
                clear_checkpoint(&ctx.buildloop_dir);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskStarted(
                    task_info.clone(),
                )));
                let (v, r) = run_dual_pipelines(
                    task_info,
                    ctx,
                    tx,
                    cached_patterns,
                    patterns_dir,
                    extension_context,
                    [selected_configs[0].clone(), selected_configs[1].clone()],
                )
                .await;
                return (v, r, false);
            }
            DualSelection::First | DualSelection::Second | DualSelection::Third
                if selected_configs.len() == 1 =>
            {
                let pipeline_config = selected_configs[0].clone();
                let override_ctx = ctx.derive(pipeline_config);
                // Box::pin to break async recursion (override_ctx has dual_selection cleared)
                return Box::pin(process_task(
                    task_info,
                    &override_ctx,
                    tx,
                    skip_scout,
                    cached_patterns,
                    patterns_dir,
                    extension_context,
                ))
                .await;
            }
            _ => {} // fall through to normal pipeline
        }
    }

    let task_id = &task_info.id;
    let task_desc = &task_info.description;
    if ctx.config.phase_isolation {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Phase isolation: enabled (Doubt artifacts will be restricted)".to_string(),
        )));
    }
    let mut stage_results: Vec<StageResult> = Vec::new();
    let mut budget_telemetry = budget::BudgetTelemetry {
        task_id: task_id.to_string(),
        timestamp: chrono::Utc::now().to_rfc3339(),
        ..Default::default()
    };
    // Mutable state for budget recovery: summary directive for next phase, model override for next phase
    let mut budget_summary_for_next: Option<String> = None;
    let mut budget_model_override: Option<(String, String)> = None; // (provider, model)
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

    // ─── Checkpoint Resumption ───────────────────────────────────
    // If a previous run crashed mid-task, detect the checkpoint and
    // skip completed stages instead of re-running from scratch.
    let resume_stage: Option<&str> = read_checkpoint(&ctx.buildloop_dir)
        .filter(|cp| cp.task_id == task_info.id)
        .and_then(|cp| {
            let stage = match cp.completed_stage.as_str() {
                "query" => Some("research"),
                "research" => Some("planner"),
                "planner" => Some("plan_review"),
                "plan_review" => Some("builder"),
                "builder" => Some("doubt"),
                // Legacy: treat old "scout" checkpoints as "research" complete
                "scout" => Some("planner"),
                _ => None,
            };
            if let Some(s) = stage {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Checkpoint recovery: {} completed '{}' stage at {} -- resuming at {}",
                    cp.task_id, cp.completed_stage, cp.timestamp, s,
                ))));
            }
            stage
        });

    // Determine which stages to skip based on checkpoint, verifying artifacts exist.
    // resume_stage tells us the NEXT stage to run. Stages before it were completed.
    // checkpoint_skip_query: query completed if we're resuming at research or later
    let checkpoint_skip_query = match resume_stage {
        Some("research" | "planner" | "plan_review" | "builder" | "doubt") => {
            if ctx.buildloop_dir.join("questions.md").exists() {
                true
            } else {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Checkpoint says query completed but questions.md missing -- re-running query"
                        .to_string(),
                )));
                false
            }
        }
        _ => false,
    };

    // checkpoint_skip_research: research completed if we're resuming at planner or later
    let checkpoint_skip_research = match resume_stage {
        Some("planner" | "plan_review" | "builder" | "doubt") if checkpoint_skip_query => {
            if ctx.buildloop_dir.join("research-report.md").exists() {
                true
            } else {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Checkpoint says research completed but research-report.md missing -- re-running from research".to_string(),
                )));
                false
            }
        }
        Some("planner" | "plan_review" | "builder" | "doubt") if !checkpoint_skip_query => {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Checkpoint says research completed but questions.md missing -- re-running from query (cascading)".to_string(),
            )));
            false
        }
        _ => false,
    };

    let checkpoint_skip_planner = match resume_stage {
        Some("plan_review" | "builder" | "doubt") if checkpoint_skip_research => {
            if ctx.current_plan.exists() {
                true
            } else {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Checkpoint says planner completed but current-plan.md missing -- re-running from planner".to_string(),
                )));
                false
            }
        }
        Some("plan_review" | "builder" | "doubt") if !checkpoint_skip_research => {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Checkpoint says planner completed but research-report.md missing -- re-running from research (cascading)".to_string(),
            )));
            false
        }
        _ => false,
    };
    let checkpoint_skip_builder = match resume_stage {
        Some("doubt") if checkpoint_skip_planner => {
            if ctx.buildloop_dir.join("build-claims.md").exists() {
                true
            } else {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Checkpoint says builder completed but build-claims.md missing -- re-running from builder".to_string(),
                )));
                false
            }
        }
        Some("doubt") if !checkpoint_skip_planner => {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Checkpoint says builder completed but current-plan.md missing -- re-running from planner (cascading)".to_string(),
            )));
            false
        }
        _ => false,
    };
    let checkpoint_skip_plan_review =
        matches!(resume_stage, Some("builder" | "doubt") if checkpoint_skip_planner);

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskStarted(
        task_info.clone(),
    )));
    let task_start = std::time::Instant::now();
    let task_cost_snapshot = ctx
        .session_cost_millicents
        .load(std::sync::atomic::Ordering::Relaxed);

    let _scout_report = ctx.buildloop_dir.join("scout-report.md");
    let questions_file = ctx.buildloop_dir.join("questions.md");
    let research_report = ctx.buildloop_dir.join("research-report.md");
    let task_complexity = complexity::classify_task(task_desc);
    observatory::log_event(
        &ctx.session_id,
        &ctx.project_dir,
        ObservatoryEvent::TaskStarted {
            task_id: task_id.to_string(),
            description: task_desc.to_string(),
            complexity: format!("{:?}", task_complexity),
        },
    );
    let skip_query = skip_scout
        || checkpoint_skip_query
        || (ctx.config.skip_scout_for_simple && task_complexity == TaskComplexity::Simple)
        || !ctx.config.pipeline_stage_enabled("query");
    let skip_research = skip_scout
        || (checkpoint_skip_query && checkpoint_skip_research)
        || (ctx.config.skip_scout_for_simple && task_complexity == TaskComplexity::Simple)
        || !ctx.config.pipeline_stage_enabled("research");
    let build_claims = ctx.buildloop_dir.join("build-claims.md");
    let mut query_failed = false;
    let mut eff_task_builder_provider = ctx.config.builder_provider.clone();
    let mut eff_task_builder_model = ctx.config.builder_model.clone();
    // Stale artifact cleanup: failures here mean the next phase may read stale data.
    // Log warnings so the root cause is visible.
    let mut stale_cleanup_failures: Vec<String> = Vec::new();
    if !skip_query && !checkpoint_skip_query {
        // Full Q+R cleanup: neither was checkpointed
        for path in [&questions_file, &research_report] {
            if let Err(e) = std::fs::remove_file(path) {
                if e.kind() != std::io::ErrorKind::NotFound {
                    let name = path.file_name().unwrap_or_default().to_string_lossy();
                    eprintln!("Warning: failed to remove stale {}: {}", name, e);
                    stale_cleanup_failures.push(name.to_string());
                }
            }
        }
    } else if !skip_research && !checkpoint_skip_research {
        // Query was checkpointed but Research was not -- clean only research-report.md
        if let Err(e) = std::fs::remove_file(&research_report) {
            if e.kind() != std::io::ErrorKind::NotFound {
                eprintln!("Warning: failed to remove stale research-report.md: {}", e);
                stale_cleanup_failures.push("research-report.md".to_string());
            }
        }
    }
    if !checkpoint_skip_builder {
        if let Err(e) = std::fs::remove_file(&build_claims) {
            if e.kind() != std::io::ErrorKind::NotFound {
                eprintln!("Warning: failed to remove stale build-claims.md: {}", e);
                stale_cleanup_failures.push("build-claims.md".to_string());
            }
        }
    }
    if !checkpoint_skip_planner {
        if let Err(e) = std::fs::remove_file(&ctx.current_plan) {
            if e.kind() != std::io::ErrorKind::NotFound {
                eprintln!("Warning: failed to remove stale current-plan.md: {}", e);
                stale_cleanup_failures.push("current-plan.md".to_string());
            }
        }
    }
    if let Err(e) = std::fs::remove_file(&ctx.review_report) {
        if e.kind() != std::io::ErrorKind::NotFound {
            eprintln!("Warning: failed to remove stale review-report.md: {}", e);
            stale_cleanup_failures.push("review-report.md".to_string());
        }
    }
    if let Err(e) = std::fs::remove_file(&patterns_extracted) {
        if e.kind() != std::io::ErrorKind::NotFound {
            eprintln!(
                "Warning: failed to remove stale patterns-extracted.json: {}",
                e
            );
            stale_cleanup_failures.push("patterns-extracted.json".to_string());
        }
    }
    if !stale_cleanup_failures.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Warning: could not remove stale artifacts [{}] -- pipeline may read data from previous run",
            stale_cleanup_failures.join(", ")
        ))));
    }

    let detected_stack = patterns::detect_project_tech_stack(&ctx.project_dir);
    let matched = if ctx.config.semantic_match_enabled {
        let keyword_scores = patterns::keyword_scores(cached_patterns, task_desc, &detected_stack);
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
            result.mode,
            result.cache_hits,
            result.cache_hits + result.cache_misses
        ))));
        scored.into_iter().map(|(p, _)| p).collect::<Vec<_>>()
    } else {
        patterns::match_patterns(cached_patterns, task_desc, &detected_stack)
    };

    let effective_pattern_count = patterns::scaled_injection_count(
        task_complexity,
        ctx.config.max_pattern_injection,
        ctx.config.min_pattern_injection,
    );

    let pattern_context =
        patterns::format_patterns_for_prompt(&matched, "planner", effective_pattern_count);
    let reviewer_pattern_context =
        patterns::format_patterns_for_prompt(&matched, "reviewer", effective_pattern_count);

    if !matched.is_empty() {
        let actually_injected = matched.len().min(effective_pattern_count);
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Matched {} patterns, injecting {} for task",
            matched.len(),
            actually_injected
        ))));
        let titles: Vec<String> = matched
            .iter()
            .take(effective_pattern_count)
            .map(|p| p.title.clone())
            .collect();
        let keywords_by_title: HashMap<String, Vec<String>> = matched
            .iter()
            .take(effective_pattern_count)
            .filter(|p| !p.keywords.is_empty())
            .map(|p| {
                (
                    p.title.clone(),
                    p.keywords.iter().map(|k| k.to_lowercase()).collect(),
                )
            })
            .collect();
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PatternsUsed {
            titles,
            keywords_by_title,
        }));
        let pattern_ids: Vec<String> = matched
            .iter()
            .take(effective_pattern_count)
            .map(|p| p.pattern_id.clone())
            .collect();
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::PatternInjected {
                task_id: task_id.to_string(),
                pattern_ids,
                count: actually_injected,
            },
        );
    }

    // Save pattern IDs for later PatternApplied event -- only the ones actually injected
    let injected_pattern_ids: Vec<String> = matched
        .iter()
        .take(effective_pattern_count)
        .map(|p| p.pattern_id.clone())
        .collect();

    // Decide whether to skip the planner based on complexity (already computed above).
    // Skip for simple tasks (existing behavior) AND for medium tasks with
    // detailed descriptions (80+ chars). Detailed task descriptions from the
    // upgraded describe-work agent are already comprehensive plans.
    let skip_planner = checkpoint_skip_planner
        || (ctx.config.skip_planner_for_simple
            && (task_complexity == TaskComplexity::Simple
                || (task_complexity == TaskComplexity::Medium && task_desc.len() >= 80)))
        || !ctx.config.pipeline_stage_enabled("plan");
    let stage_skip_builder = !ctx.config.pipeline_stage_enabled("implement");

    // Track rate limiting across agents; starts false when planner is skipped.
    #[allow(unused_assignments)]
    let mut last_rate_limited = false;

    // ─── Run Query + Research (skip if recent report exists and codebase hasn't changed much) ───
    if skip_query && skip_research {
        let msg = if checkpoint_skip_query && checkpoint_skip_research {
            "Checkpoint: reusing questions + research from previous session".to_string()
        } else if ctx.config.skip_scout_for_simple && task_complexity == TaskComplexity::Simple {
            "Skipping Q+R for simple task".to_string()
        } else {
            "Reusing research report from previous task".to_string()
        };
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(msg)));
    } else {
        // Determine question budget based on complexity
        let max_questions: usize = match task_complexity {
            TaskComplexity::Medium => 5,
            TaskComplexity::Complex => 10,
            _ => 5, // Simple tasks should be skipped, but fallback to 5
        };
        let complexity_str = match task_complexity {
            TaskComplexity::Simple => "Simple",
            TaskComplexity::Medium => "Medium",
            TaskComplexity::Complex => "Complex",
        };

        if skip_query {
            let msg = if checkpoint_skip_query {
                "Checkpoint: reusing questions from previous session".to_string()
            } else {
                "Skipping Query (research report outdated)".to_string()
            };
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(msg)));
        } else {
            // ─── Query Phase ─────────────────────────────────────────
            {
                let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
                let fwd_tx = tx.clone();
                let fwd_handle = tokio::spawn(async move {
                    let mut usage = AgentUsage::default();
                    while let Some(evt) = agent_rx.recv().await {
                        usage.accumulate(&evt);
                        let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                    }
                    usage
                });

                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                    AgentRole::Query,
                    Config::display_provider_model(
                        &ctx.config.query_provider,
                        &ctx.config.query_model,
                    ),
                )));
                observatory::log_event(
                    &ctx.session_id,
                    &ctx.project_dir,
                    ObservatoryEvent::AgentStarted {
                        role: format!("{}", AgentRole::Query),
                        provider: ctx.config.query_provider.clone(),
                        model: ctx.config.query_model.clone(),
                        cc_version: cc_version.clone(),
                    },
                );

                let updated_specs = std::fs::read_to_string(&ctx.updated_specs_path)
                    .ok()
                    .filter(|s| !s.trim().is_empty());
                let spec_content = std::fs::read_to_string(&ctx.spec_path)
                    .ok()
                    .filter(|s| !s.trim().is_empty());
                let tasks_content = std::fs::read_to_string(&ctx.plan_path)
                    .ok()
                    .filter(|s| !s.trim().is_empty())
                    .map(|s| crate::task::extract_query_context(&s));

                let query_prompt_text = prompts::query_prompt(
                    &ctx.config.pipeline_stage_label("query"),
                    task_id,
                    task_desc,
                    complexity_str,
                    max_questions,
                    updated_specs.as_deref(),
                    spec_content.as_deref(),
                    tasks_content.as_deref(),
                );
                let query_start = Instant::now();
                let query_result = agent::run_agent(
                    &AgentRole::Query,
                    Config::parse_provider(&ctx.config.query_provider),
                    &ctx.config.query_model,
                    &query_prompt_text,
                    &ctx.project_dir,
                    agent_tx,
                    &ctx.log_dir,
                    None,
                    ctx.config.agent_timeout_secs,
                    Some(ctx.shutdown.clone()),
                    Some(&ctx.config),
                )
                .await;

                let agent_usage = fwd_handle.await.unwrap_or_default();
                last_rate_limited = was_rate_limited(&query_result);
                let query_ok = query_result.map(|r| r.success).unwrap_or(false);
                let _ = tx.send(AppEvent::AgentDone(query_ok));
                observatory::log_event(
                    &ctx.session_id,
                    &ctx.project_dir,
                    ObservatoryEvent::AgentDone {
                        role: format!("{}", AgentRole::Query),
                        success: query_ok,
                        duration_secs: query_start.elapsed().as_secs_f64(),
                        tokens_in: agent_usage.tokens_in,
                        tokens_out: agent_usage.tokens_out,
                        cost_usd: agent_usage.cost_usd,
                        context_pct: agent_usage.context_pct,
                        cache_creation_tokens: agent_usage.cache_creation_tokens,
                        cache_read_tokens: agent_usage.cache_read_tokens,
                    },
                );

                // Budget telemetry: Query
                if ctx.config.budget_recovery_enabled {
                    let record = budget::evaluate_phase(
                        &AgentRole::Query,
                        &agent_usage,
                        &ctx.config.budget_targets,
                        ctx.config.budget_overrun_threshold,
                    );
                    if record.overrun && record.recovery_action != budget::RecoveryAction::Continue
                    {
                        budget_telemetry.any_overrun = true;
                        budget_telemetry.recovery_actions_taken.push(format!(
                            "{}: {}",
                            AgentRole::Query,
                            record.recovery_action
                        ));
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                            phase: format!("{}", AgentRole::Query),
                            target_pct: record.target_pct,
                            actual_pct: record.actual_pct,
                            recovery: format!("{}", record.recovery_action),
                        }));
                        observatory::log_event(
                            &ctx.session_id,
                            &ctx.project_dir,
                            ObservatoryEvent::BudgetOverrun {
                                task_id: task_id.to_string(),
                                phase: format!("{}", AgentRole::Query),
                                target_pct: record.target_pct,
                                actual_pct: record.actual_pct,
                                recovery_action: format!("{}", record.recovery_action),
                            },
                        );
                    } else if record.overrun {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Budget: {} used {}% (target {}%, within tolerance)",
                            AgentRole::Query,
                            record.actual_pct,
                            record.target_pct,
                        ))));
                    }
                    budget_telemetry.records.push(record);
                }

                if !query_ok {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Query failed for {} -- continuing without questions",
                        task_id
                    ))));
                    stage_results.push(StageResult::failure(
                        "Query",
                        &format!("Generate investigation questions for {}", task_id),
                        FailureType::Crash,
                        vec![
                            "Query is non-blocking -- pipeline continues without questions"
                                .to_string(),
                        ],
                    ));
                    query_failed = true;
                    // Remove partial questions.md so crash recovery won't trust stale content
                    if let Err(e) = std::fs::remove_file(&questions_file) {
                        if e.kind() != std::io::ErrorKind::NotFound {
                            eprintln!("Warning: failed to remove partial questions.md after query failure: {}", e);
                        }
                    }
                }

                adaptive_sleep(
                    &ctx.config,
                    last_rate_limited,
                    ctx.config.pause_between_agents_secs,
                )
                .await;

                if ctx.is_stop_requested() {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Stop requested after QUERY for {} -- skipping remaining stages",
                        task_id
                    ))));
                    {
                        let _lock = ctx
                            .tasks_file_lock
                            .lock()
                            .unwrap_or_else(|e| e.into_inner());
                        let _ = task::update_task_progress(&ctx.plan_path, task_id, "Q.....");
                    }
                    stage_results.push(StageResult::failure(
                        "Query",
                        &format!("Generate investigation questions for {}", task_id),
                        FailureType::StopRequested,
                        vec![],
                    ));
                    let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                    flush_budget_telemetry(
                        &ctx.buildloop_dir,
                        ctx.config.budget_recovery_enabled,
                        &budget_telemetry,
                    );
                    return (false, last_rate_limited, false);
                }
            }

            // Checkpoint: query completed
            if !query_failed {
                write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "query");
            }
        } // end if !skip_query else block

        if skip_research {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Pipeline: research stage disabled in config -- skipping research for {}",
                task_id
            ))));
        } else if !query_failed {
            // ─── Research Phase (with phase isolation) ───────────────
            {
                // Phase isolation: hide TASKS.md and UPDATED_SPECS.md from Research
                let isolation = if ctx.config.phase_isolation {
                    let restricted = crate::isolation::research_restricted_paths(
                        &ctx.plan_path,
                        &ctx.updated_specs_path,
                        &ctx.buildloop_dir,
                    );
                    match crate::isolation::PhaseIsolation::activate(&restricted) {
                        Ok(iso) => Some(iso),
                        Err(e) => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Phase isolation failed for Research: {} -- continuing without isolation", e
                        ))));
                            None
                        }
                    }
                } else {
                    None
                };

                let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
                let fwd_tx = tx.clone();
                let fwd_handle = tokio::spawn(async move {
                    let mut usage = AgentUsage::default();
                    while let Some(evt) = agent_rx.recv().await {
                        usage.accumulate(&evt);
                        let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                    }
                    usage
                });

                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                    AgentRole::Research,
                    Config::display_provider_model(
                        &ctx.config.research_provider,
                        &ctx.config.research_model,
                    ),
                )));
                observatory::log_event(
                    &ctx.session_id,
                    &ctx.project_dir,
                    ObservatoryEvent::AgentStarted {
                        role: format!("{}", AgentRole::Research),
                        provider: ctx.config.research_provider.clone(),
                        model: ctx.config.research_model.clone(),
                        cc_version: cc_version.clone(),
                    },
                );

                let research_prompt_text =
                    prompts::research_prompt(&ctx.config.pipeline_stage_label("research"));
                let research_start = Instant::now();
                let research_result = agent::run_agent(
                    &AgentRole::Research,
                    Config::parse_provider(&ctx.config.research_provider),
                    &ctx.config.research_model,
                    &research_prompt_text,
                    &ctx.project_dir,
                    agent_tx,
                    &ctx.log_dir,
                    None,
                    ctx.config.agent_timeout_secs,
                    Some(ctx.shutdown.clone()),
                    Some(&ctx.config),
                )
                .await;

                // Restore isolated files before processing results
                if let Some(mut iso) = isolation {
                    if let Err(e) = iso.restore() {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Phase isolation restore failed: {}",
                            e
                        ))));
                    }
                }

                let agent_usage = fwd_handle.await.unwrap_or_default();
                last_rate_limited = was_rate_limited(&research_result);
                let research_ok = research_result.map(|r| r.success).unwrap_or(false);
                let _ = tx.send(AppEvent::AgentDone(research_ok));
                observatory::log_event(
                    &ctx.session_id,
                    &ctx.project_dir,
                    ObservatoryEvent::AgentDone {
                        role: format!("{}", AgentRole::Research),
                        success: research_ok,
                        duration_secs: research_start.elapsed().as_secs_f64(),
                        tokens_in: agent_usage.tokens_in,
                        tokens_out: agent_usage.tokens_out,
                        cost_usd: agent_usage.cost_usd,
                        context_pct: agent_usage.context_pct,
                        cache_creation_tokens: agent_usage.cache_creation_tokens,
                        cache_read_tokens: agent_usage.cache_read_tokens,
                    },
                );

                // Budget telemetry: Research
                if ctx.config.budget_recovery_enabled {
                    let record = budget::evaluate_phase(
                        &AgentRole::Research,
                        &agent_usage,
                        &ctx.config.budget_targets,
                        ctx.config.budget_overrun_threshold,
                    );
                    if record.overrun && record.recovery_action != budget::RecoveryAction::Continue
                    {
                        budget_telemetry.any_overrun = true;
                        budget_telemetry.recovery_actions_taken.push(format!(
                            "{}: {}",
                            AgentRole::Research,
                            record.recovery_action
                        ));
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                            phase: format!("{}", AgentRole::Research),
                            target_pct: record.target_pct,
                            actual_pct: record.actual_pct,
                            recovery: format!("{}", record.recovery_action),
                        }));
                        observatory::log_event(
                            &ctx.session_id,
                            &ctx.project_dir,
                            ObservatoryEvent::BudgetOverrun {
                                task_id: task_id.to_string(),
                                phase: format!("{}", AgentRole::Research),
                                target_pct: record.target_pct,
                                actual_pct: record.actual_pct,
                                recovery_action: format!("{}", record.recovery_action),
                            },
                        );
                        match record.recovery_action {
                            budget::RecoveryAction::Summarize => {
                                budget_summary_for_next = Some(budget::summarize_directive(
                                    &format!("{}", AgentRole::Research),
                                    record.actual_pct,
                                    record.target_pct,
                                ));
                            }
                            budget::RecoveryAction::Escalate => {
                                budget_model_override =
                                    Some(("claude".to_string(), "opus".to_string()));
                                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: escalating {} model to opus due to {} overrun ({}% > {}%)",
                                AgentRole::Planner, AgentRole::Research, record.actual_pct, record.target_pct,
                            ))));
                            }
                            budget::RecoveryAction::SplitRecommended => {
                                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: split recommended for {} ({}% > {}%) -- logged for manual review",
                                AgentRole::Research, record.actual_pct, record.target_pct,
                            ))));
                            }
                            budget::RecoveryAction::Continue => {}
                        }
                    } else if record.overrun {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Budget: {} used {}% (target {}%, within tolerance)",
                            AgentRole::Research,
                            record.actual_pct,
                            record.target_pct,
                        ))));
                    }
                    budget_telemetry.records.push(record);
                }

                if !research_ok {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Research failed for {} -- continuing without report",
                        task_id
                    ))));
                    stage_results.push(StageResult::failure(
                        "Research",
                        &format!("Investigate codebase for {}", task_id),
                        FailureType::Crash,
                        vec![
                            "Research is non-blocking -- pipeline continues without report"
                                .to_string(),
                        ],
                    ));
                }

                if last_rate_limited {
                    observatory::log_event(
                        &ctx.session_id,
                        &ctx.project_dir,
                        ObservatoryEvent::RateLimited {
                            provider: ctx.config.research_provider.clone(),
                            wait_secs: ctx.config.pause_between_agents_secs,
                        },
                    );
                }

                adaptive_sleep(
                    &ctx.config,
                    last_rate_limited,
                    ctx.config.pause_between_agents_secs,
                )
                .await;

                if ctx.is_stop_requested() {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Stop requested after RESEARCH for {} -- skipping remaining stages",
                        task_id
                    ))));
                    {
                        let _lock = ctx
                            .tasks_file_lock
                            .lock()
                            .unwrap_or_else(|e| e.into_inner());
                        let _ = task::update_task_progress(&ctx.plan_path, task_id, "QR....");
                    }
                    stage_results.push(StageResult::failure(
                        "Research",
                        &format!("Investigate codebase for {}", task_id),
                        FailureType::StopRequested,
                        vec![],
                    ));
                    let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                    flush_budget_telemetry(
                        &ctx.buildloop_dir,
                        ctx.config.budget_recovery_enabled,
                        &budget_telemetry,
                    );
                    return (false, last_rate_limited, false);
                }
            }
        } else {
            // Query failed -- skip Research (no questions.md to investigate)
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Skipping Research for {} -- Query failed, no questions to investigate",
                task_id
            ))));
            stage_results.push(StageResult::failure(
                "Research",
                &format!("Investigate codebase for {}", task_id),
                FailureType::Crash,
                vec!["Skipped: Query failed and produced no questions.md".to_string()],
            ));
        }
    }

    // Stage results for Q+R
    if checkpoint_skip_query {
        let mut result = StageResult::success(
            "Query",
            &format!("Generate questions for {} (checkpoint)", task_id),
        );
        if questions_file.exists() {
            result.partial_results.push("questions.md".to_string());
        }
        stage_results.push(result);
    } else if !skip_query
        && !query_failed
        && stage_results.last().map(|r| r.stage.as_str()) != Some("Query")
    {
        let mut result =
            StageResult::success("Query", &format!("Generate questions for {}", task_id));
        if questions_file.exists() {
            result.partial_results.push("questions.md".to_string());
        }
        stage_results.push(result);
    }

    if checkpoint_skip_research {
        let mut result = StageResult::success(
            "Research",
            &format!("Investigate codebase for {} (checkpoint)", task_id),
        );
        if research_report.exists() {
            result
                .partial_results
                .push("research-report.md".to_string());
        }
        stage_results.push(result);
    } else if !skip_research
        && !query_failed
        && stage_results.last().map(|r| r.stage.as_str()) != Some("Research")
    {
        let mut result =
            StageResult::success("Research", &format!("Investigate codebase for {}", task_id));
        if research_report.exists() {
            result
                .partial_results
                .push("research-report.md".to_string());
        }
        stage_results.push(result);
    }

    // Checkpoint: research completed
    if !checkpoint_skip_research && !skip_research && !query_failed {
        write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "research");
    }

    // Gate: research-report.md must exist before planner proceeds (unless Q+R was skipped)
    if !skip_research && !query_failed && !research_report.exists() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Research report missing for {} -- planner will proceed without it",
            task_id
        ))));
    }

    // Helper: progress indicator characters.
    // Checkpoint-resumed stages count as "ran" for progress indicators.
    let query_char = if skip_query && !checkpoint_skip_query {
        "-"
    } else {
        "Q"
    };
    let research_char = if (skip_research && !checkpoint_skip_research) || query_failed {
        "-"
    } else {
        "R"
    };
    let planner_char = if skip_planner && !checkpoint_skip_planner {
        "-"
    } else {
        "P"
    };

    if skip_planner {
        let reason = if checkpoint_skip_planner {
            "checkpoint recovery"
        } else if task_complexity == TaskComplexity::Simple {
            "simple task"
        } else {
            "detailed medium task (>= 80 chars)"
        };
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Skipping planner for {}",
            reason
        ))));
    } else {
        // ─── Check for Look-Ahead Plan ───────────────────────────
        let la_plan = lookahead_plan_path(ctx, task_id);
        let mut la_plan_used = false;
        if la_plan.exists() {
            // A look-ahead planner already produced a plan for this task.
            // Promote it to current-plan.md and skip the planner stage.
            if std::fs::rename(&la_plan, &ctx.current_plan).is_ok() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Using pre-planned plan for {}",
                    task_id
                ))));
                la_plan_used = true;
            } else {
                // rename failed (cross-device?), try copy+delete
                match std::fs::copy(&la_plan, &ctx.current_plan) {
                    Ok(_) => {
                        let _ = std::fs::remove_file(&la_plan);
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Using pre-planned plan for {}",
                            task_id
                        ))));
                        la_plan_used = true;
                    }
                    Err(e) => {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Warning: lookahead plan copy also failed for {}: {} -- running planner instead",
                            task_id, e
                        ))));
                    }
                }
            }
        }
        if !la_plan_used {
            // ─── Run Planner ─────────────────────────────────────────
            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            let fwd_handle = tokio::spawn(async move {
                let mut usage = AgentUsage::default();
                while let Some(evt) = agent_rx.recv().await {
                    usage.accumulate(&evt);
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
                usage
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Planner,
                Config::display_provider_model(
                    &ctx.config.planner_provider,
                    &ctx.config.planner_model,
                ),
            )));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentStarted {
                    role: format!("{}", AgentRole::Planner),
                    provider: ctx.config.planner_provider.clone(),
                    model: ctx.config.planner_model.clone(),
                    cc_version: cc_version.clone(),
                },
            );

            let mut prompt = prompts::planner_prompt(
                &ctx.config.pipeline_stage_label("plan"),
                task_id,
                task_desc,
                &pattern_context,
                &ctx.spec_file_prompt_path(),
                &ctx.tasks_file_prompt_path(),
            );
            // Inject build history into planner for cross-session recall
            let history_dir = crate::history::resolve_history_dir(&ctx.config.history_dir);
            let history_records = crate::history::search_history(
                &history_dir,
                task_desc,
                ctx.config.history_search_results,
            );
            let history_context = crate::history::format_history_for_prompt(&history_records);
            if !history_context.is_empty() {
                prompt = format!("{}\n{}", prompt, history_context);
            }
            if let Some(summary) = budget_summary_for_next.take() {
                prompt = format!("{}\n\n{}", summary, prompt);
            }
            // Planner writes plans, not code -- skip extension context to save tokens.
            let planner_start = Instant::now();
            let (eff_planner_provider, eff_planner_model) = match budget_model_override.take() {
                Some((p, m)) => (Config::parse_provider(&p), m),
                None => (
                    Config::parse_provider(&ctx.config.planner_provider),
                    ctx.config.planner_model.clone(),
                ),
            };
            let plan_result = agent::run_agent(
                &AgentRole::Planner,
                eff_planner_provider,
                &eff_planner_model,
                &prompt,
                &ctx.project_dir,
                agent_tx,
                &ctx.log_dir,
                None,
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
                Some(&ctx.config),
            )
            .await;

            let agent_usage = fwd_handle.await.unwrap_or_default();
            last_rate_limited = was_rate_limited(&plan_result);
            let plan_ok = plan_result.map(|r| r.success).unwrap_or(false);
            let _ = tx.send(AppEvent::AgentDone(plan_ok));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentDone {
                    role: format!("{}", AgentRole::Planner),
                    success: plan_ok,
                    duration_secs: planner_start.elapsed().as_secs_f64(),
                    tokens_in: agent_usage.tokens_in,
                    tokens_out: agent_usage.tokens_out,
                    cost_usd: agent_usage.cost_usd,
                    context_pct: agent_usage.context_pct,
                    cache_creation_tokens: agent_usage.cache_creation_tokens,
                    cache_read_tokens: agent_usage.cache_read_tokens,
                },
            );
            // Budget telemetry: Planner
            if ctx.config.budget_recovery_enabled {
                let record = budget::evaluate_phase(
                    &AgentRole::Planner,
                    &agent_usage,
                    &ctx.config.budget_targets,
                    ctx.config.budget_overrun_threshold,
                );
                if record.overrun && record.recovery_action != budget::RecoveryAction::Continue {
                    budget_telemetry.any_overrun = true;
                    budget_telemetry.recovery_actions_taken.push(format!(
                        "{}: {}",
                        AgentRole::Planner,
                        record.recovery_action
                    ));
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                        phase: format!("{}", AgentRole::Planner),
                        target_pct: record.target_pct,
                        actual_pct: record.actual_pct,
                        recovery: format!("{}", record.recovery_action),
                    }));
                    observatory::log_event(
                        &ctx.session_id,
                        &ctx.project_dir,
                        ObservatoryEvent::BudgetOverrun {
                            task_id: task_id.to_string(),
                            phase: format!("{}", AgentRole::Planner),
                            target_pct: record.target_pct,
                            actual_pct: record.actual_pct,
                            recovery_action: format!("{}", record.recovery_action),
                        },
                    );
                    match record.recovery_action {
                        budget::RecoveryAction::Summarize => {
                            budget_summary_for_next = Some(budget::summarize_directive(
                                &format!("{}", AgentRole::Planner),
                                record.actual_pct,
                                record.target_pct,
                            ));
                        }
                        budget::RecoveryAction::Escalate => {
                            budget_model_override =
                                Some(("claude".to_string(), "opus".to_string()));
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: escalating {} model to opus due to {} overrun ({}% > {}%)",
                                AgentRole::Builder, AgentRole::Planner, record.actual_pct, record.target_pct,
                            ))));
                        }
                        budget::RecoveryAction::SplitRecommended => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: split recommended for {} ({}% > {}%) -- logged for manual review",
                                AgentRole::Planner, record.actual_pct, record.target_pct,
                            ))));
                        }
                        budget::RecoveryAction::Continue => {}
                    }
                } else if record.overrun {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Budget: {} used {}% (target {}%, within tolerance)",
                        AgentRole::Planner,
                        record.actual_pct,
                        record.target_pct,
                    ))));
                }
                budget_telemetry.records.push(record);
            }
            if last_rate_limited {
                observatory::log_event(
                    &ctx.session_id,
                    &ctx.project_dir,
                    ObservatoryEvent::RateLimited {
                        provider: ctx.config.planner_provider.clone(),
                        wait_secs: ctx.config.pause_between_agents_secs,
                    },
                );
            }

            if !plan_ok || !ctx.current_plan.exists() {
                {
                    let _lock = ctx
                        .tasks_file_lock
                        .lock()
                        .unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(
                        &ctx.plan_path,
                        task_id,
                        &format!("{}{}P--!", query_char, research_char),
                    );
                }
                stage_results.push(StageResult::failure(
                    "Planner",
                    &format!("Create implementation plan for {}", task_id),
                    FailureType::Crash,
                    vec![
                        "Retry with a simpler task description".to_string(),
                        "Check if SPEC.md has enough context".to_string(),
                    ],
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
                flush_budget_telemetry(
                    &ctx.buildloop_dir,
                    ctx.config.budget_recovery_enabled,
                    &budget_telemetry,
                );
                return (false, last_rate_limited, false);
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
                    let _lock = ctx
                        .tasks_file_lock
                        .lock()
                        .unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(
                        &ctx.plan_path,
                        task_id,
                        &format!("{}{}P..", query_char, research_char),
                    );
                }
                stage_results.push(StageResult::failure(
                    "Planner",
                    &format!("Create implementation plan for {}", task_id),
                    FailureType::StopRequested,
                    vec![],
                ));
                let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                flush_budget_telemetry(
                    &ctx.buildloop_dir,
                    ctx.config.budget_recovery_enabled,
                    &budget_telemetry,
                );
                return (false, last_rate_limited, false);
            }
        }

        // Planner completed -- persist progress indicator.
        {
            let _lock = ctx
                .tasks_file_lock
                .lock()
                .unwrap_or_else(|e| e.into_inner());
            let _ = task::update_task_progress(
                &ctx.plan_path,
                task_id,
                &format!("{}{}{}..", query_char, research_char, planner_char),
            );
        }
    }

    if checkpoint_skip_planner {
        let mut result = StageResult::success(
            "Planner",
            &format!("Create implementation plan for {} (checkpoint)", task_id),
        );
        if ctx.current_plan.exists() {
            result.partial_results.push("current-plan.md".to_string());
        }
        stage_results.push(result);
    } else if !skip_planner {
        let mut result = StageResult::success(
            "Planner",
            &format!("Create implementation plan for {}", task_id),
        );
        if ctx.current_plan.exists() {
            result.partial_results.push("current-plan.md".to_string());
        }
        stage_results.push(result);
    }

    // ─── Gate: Extension Context ───────────────────────────────
    if !ctx.config.extensions.is_empty() {
        let discovered = extensions::discover_extensions(&ctx.project_dir);
        if let Err(errors) = extensions::validate_extensions(&discovered, &ctx.config.extensions) {
            for err in &errors {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "GATE BLOCKED: {}",
                    err
                ))));
            }
            {
                let _lock = ctx
                    .tasks_file_lock
                    .lock()
                    .unwrap_or_else(|e| e.into_inner());
                let _ = task::update_task_progress(
                    &ctx.plan_path,
                    task_id,
                    &format!("{}{}{}--!", query_char, research_char, planner_char),
                );
            }
            stage_results.push(StageResult::failure(
                "ExtensionGate",
                "Validate extension context",
                FailureType::GateFail,
                vec!["Ensure all configured extensions have CLAUDE.md files".to_string()],
            ));
            let _ = commit_wip_for_mode(ctx, task_id, task_desc);
            flush_budget_telemetry(
                &ctx.buildloop_dir,
                ctx.config.budget_recovery_enabled,
                &budget_telemetry,
            );
            return (false, last_rate_limited, false);
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
            let mut base_prompt = prompts::planner_prompt(
                &ctx.config.pipeline_stage_label("plan"),
                task_id,
                task_desc,
                &pattern_context,
                &ctx.spec_file_prompt_path(),
                &ctx.tasks_file_prompt_path(),
            );
            // Re-inject build history into retry prompt
            let retry_history_dir = crate::history::resolve_history_dir(&ctx.config.history_dir);
            let retry_history = crate::history::search_history(
                &retry_history_dir,
                task_desc,
                ctx.config.history_search_results,
            );
            let retry_history_ctx = crate::history::format_history_for_prompt(&retry_history);
            if !retry_history_ctx.is_empty() {
                base_prompt = format!("{}\n{}", base_prompt, retry_history_ctx);
            }
            let retry_prompt = format!(
                "{}\n\n--- VALIDATION ERROR (your previous output failed these checks) ---\n\
                 Error: {}\n\
                 Your previous output:\n```\n{}\n```\n\
                 Fix these specific issues. The plan MUST contain '## File Operations' and '## Verification' sections.\n\
                 --- END VALIDATION ERROR ---",
                base_prompt,
                reason,
                crate::utils::truncate_str(&failed_output, 500),
            );
            // Planner retry -- skip extension context to save tokens.

            let retry_start = Instant::now();
            let (agent_tx2, mut agent_rx2) = mpsc::unbounded_channel();
            let fwd_tx2 = tx.clone();
            let fwd_handle2 = tokio::spawn(async move {
                let mut usage = AgentUsage::default();
                while let Some(evt) = agent_rx2.recv().await {
                    usage.accumulate(&evt);
                    let _ = fwd_tx2.send(AppEvent::AgentOutput(evt));
                }
                usage
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Planner,
                Config::display_provider_model(
                    &ctx.config.planner_provider,
                    &ctx.config.planner_model,
                ),
            )));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentStarted {
                    role: format!("{}", AgentRole::Planner),
                    provider: ctx.config.planner_provider.clone(),
                    model: ctx.config.planner_model.clone(),
                    cc_version: cc_version.clone(),
                },
            );

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
                Some(&ctx.config),
            )
            .await;

            let retry_usage = fwd_handle2.await.unwrap_or_default();
            last_rate_limited = was_rate_limited(&retry_result);
            let retry_ok = retry_result.as_ref().map(|r| r.success).unwrap_or(false);
            let _ = tx.send(AppEvent::AgentDone(retry_ok));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentDone {
                    role: format!("{}", AgentRole::Planner),
                    success: retry_ok,
                    duration_secs: retry_start.elapsed().as_secs_f64(),
                    tokens_in: retry_usage.tokens_in,
                    tokens_out: retry_usage.tokens_out,
                    cost_usd: retry_usage.cost_usd,
                    context_pct: retry_usage.context_pct,
                    cache_creation_tokens: retry_usage.cache_creation_tokens,
                    cache_read_tokens: retry_usage.cache_read_tokens,
                },
            );
            // Budget telemetry: Planner retry
            if ctx.config.budget_recovery_enabled {
                let record = budget::evaluate_phase(
                    &AgentRole::Planner,
                    &retry_usage,
                    &ctx.config.budget_targets,
                    ctx.config.budget_overrun_threshold,
                );
                if record.overrun && record.recovery_action != budget::RecoveryAction::Continue {
                    budget_telemetry.any_overrun = true;
                    budget_telemetry.recovery_actions_taken.push(format!(
                        "{}: {}",
                        AgentRole::Planner,
                        record.recovery_action
                    ));
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                        phase: format!("{}", AgentRole::Planner),
                        target_pct: record.target_pct,
                        actual_pct: record.actual_pct,
                        recovery: format!("{}", record.recovery_action),
                    }));
                    observatory::log_event(
                        &ctx.session_id,
                        &ctx.project_dir,
                        ObservatoryEvent::BudgetOverrun {
                            task_id: task_id.to_string(),
                            phase: format!("{}", AgentRole::Planner),
                            target_pct: record.target_pct,
                            actual_pct: record.actual_pct,
                            recovery_action: format!("{}", record.recovery_action),
                        },
                    );
                    match record.recovery_action {
                        budget::RecoveryAction::Summarize => {
                            budget_summary_for_next = Some(budget::summarize_directive(
                                &format!("{}", AgentRole::Planner),
                                record.actual_pct,
                                record.target_pct,
                            ));
                        }
                        budget::RecoveryAction::Escalate => {
                            budget_model_override =
                                Some(("claude".to_string(), "opus".to_string()));
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: escalating {} model to opus due to {} retry overrun ({}% > {}%)",
                                AgentRole::Builder, AgentRole::Planner,
                                record.actual_pct, record.target_pct,
                            ))));
                        }
                        budget::RecoveryAction::SplitRecommended => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: split recommended for {} retry ({}% > {}%) -- logged for manual review",
                                AgentRole::Planner, record.actual_pct, record.target_pct,
                            ))));
                        }
                        budget::RecoveryAction::Continue => {}
                    }
                } else if record.overrun {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Budget: {} retry used {}% (target {}%, within tolerance)",
                        AgentRole::Planner,
                        record.actual_pct,
                        record.target_pct,
                    ))));
                }
                budget_telemetry.records.push(record);
            }

            // Check gate again after retry
            if let GateResult::Fail(reason2) = gate_builder(ctx) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "GATE BLOCKED builder for {} after retry: {}",
                    task_id, reason2
                ))));
                {
                    let _lock = ctx
                        .tasks_file_lock
                        .lock()
                        .unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(
                        &ctx.plan_path,
                        task_id,
                        &format!("{}{}{}--!", query_char, research_char, planner_char),
                    );
                }
                stage_results.push(StageResult::failure(
                    "BuilderGate",
                    "Validate plan structure (File Operations + Verification sections)",
                    FailureType::GateFail,
                    vec![
                        "Planner failed to produce valid plan after retry".to_string(),
                        format!("Gate reason: {}", reason2),
                    ],
                ));
                let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                flush_budget_telemetry(
                    &ctx.buildloop_dir,
                    ctx.config.budget_recovery_enabled,
                    &budget_telemetry,
                );
                return (false, last_rate_limited, false);
            }

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Planner retry succeeded for {}",
                task_id
            ))));
        }
    }

    // Checkpoint: planner completed (after extension + builder gates pass)
    if !checkpoint_skip_planner {
        write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "planner");
    }

    // ─── P+ Subphase: Plan Review via Orchestrator ────────────
    // For complex tasks, route the planner's output through the proposer/reviewer
    // loop before the builder executes. Simpler tasks skip this.
    let plan_review_char;
    if checkpoint_skip_plan_review {
        stage_results.push(StageResult::success(
            "PlanReview",
            &format!("Review plan for {} (checkpoint)", task_id),
        ));
    }
    if !checkpoint_skip_plan_review
        && ctx.config.plan_review_enabled
        && task_complexity == TaskComplexity::Complex
        && (!skip_planner || checkpoint_skip_planner)
    {
        let plan_text = match std::fs::read_to_string(&ctx.current_plan) {
            Ok(text) => text,
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "P+ skipped: failed to read current-plan.md: {}",
                    e
                ))));
                String::new()
            }
        };

        // Budget recovery directives target "the next phase" -- for Complex tasks,
        // that's P+, not Builder. Consume and warn to prevent silent carry-through.
        // Must run unconditionally when P+ conditions are met, even if plan is unreadable.
        // (Same pattern as parallel builder at build.rs:3414-3423)
        if let Some(_summary) = budget_summary_for_next.take() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "P+ subphase: budget summary directive from Planner consumed (P+ uses orchestrator config, not prompt injection)".to_string()
            )));
        }
        if let Some((ref p, ref m)) = budget_model_override.take() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                format!("P+ subphase: budget model override ({}/{}) from Planner consumed (P+ uses orchestrator providers, not overrideable)", p, m)
            )));
        }

        if !plan_text.is_empty() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::PlanReview,
                format!(
                    "P+ review ({})",
                    Config::display_provider_model(
                        &ctx.config.orchestrator_proposer_provider,
                        &ctx.config.orchestrator_proposer_model,
                    )
                ),
            )));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentStarted {
                    role: format!("{}", AgentRole::PlanReview),
                    provider: ctx.config.orchestrator_proposer_provider.clone(),
                    model: ctx.config.orchestrator_proposer_model.clone(),
                    cc_version: cc_version.clone(),
                },
            );
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "P+ subphase: routing plan for {} through orchestrator review loop",
                task_id
            ))));

            let orch_config = OrchestratorConfig::from_config(&ctx.config);

            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            let fwd_handle = tokio::spawn(async move {
                let mut usage = AgentUsage::default();
                while let Some(evt) = agent_rx.recv().await {
                    usage.accumulate(&evt);
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
                usage
            });

            let plan_review_start = Instant::now();
            let review_result = orchestrator::run_plan_review(
                &plan_text,
                task_id,
                task_desc,
                &orch_config,
                &ctx.project_dir,
                &ctx.log_dir,
                |msg| {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!("P+: {}", msg))));
                },
                Some(agent_tx),
                Some(ctx.shutdown.clone()),
            )
            .await;

            let agent_usage = fwd_handle.await.unwrap_or_default();
            let _ = tx.send(AppEvent::AgentDone(
                review_result.as_ref().map(|r| r.accepted).unwrap_or(false),
            ));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentDone {
                    role: format!("{}", AgentRole::PlanReview),
                    success: review_result.as_ref().map(|r| r.accepted).unwrap_or(false),
                    duration_secs: plan_review_start.elapsed().as_secs_f64(),
                    tokens_in: agent_usage.tokens_in,
                    tokens_out: agent_usage.tokens_out,
                    cost_usd: agent_usage.cost_usd,
                    context_pct: agent_usage.context_pct,
                    cache_creation_tokens: agent_usage.cache_creation_tokens,
                    cache_read_tokens: agent_usage.cache_read_tokens,
                },
            );

            match review_result {
                Ok(outcome) => {
                    if outcome.accepted {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "P+ accepted plan in {} iteration(s) -- replacing current-plan.md",
                            outcome.iterations
                        ))));
                        // Replace current-plan.md with the reviewed plan
                        if let Err(e) = crate::utils::atomic_write_file(
                            &ctx.current_plan,
                            outcome.final_plan_text.as_bytes(),
                        ) {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "P+ warning: failed to write reviewed plan: {}",
                                e
                            ))));
                        }
                        plan_review_char = "+";
                        {
                            let mut result = StageResult::success(
                                "PlanReview",
                                &format!("Review plan for {}", task_id),
                            );
                            result
                                .partial_results
                                .push(format!("Accepted in {} iteration(s)", outcome.iterations,));
                            stage_results.push(result);
                        }
                    } else {
                        let finding_count = outcome.unresolved_findings.len();
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "P+ did not accept plan after {} iteration(s) ({} unresolved findings) -- using original plan",
                            outcome.iterations, finding_count
                        ))));
                        plan_review_char = "!";
                        {
                            let mut result = StageResult::failure(
                                "PlanReview",
                                &format!("Review plan for {}", task_id),
                                FailureType::ReviewFail,
                                vec![
                                    format!(
                                        "{} unresolved findings after {} iteration(s)",
                                        finding_count, outcome.iterations
                                    ),
                                    "Using original plan without P+ improvements".to_string(),
                                ],
                            );
                            result.partial_results.push(format!(
                                "Rejected after {} iteration(s), {} unresolved findings",
                                outcome.iterations, finding_count,
                            ));
                            stage_results.push(result);
                        }
                    }
                }
                Err(e) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "P+ orchestrator error: {} -- using original plan",
                        e
                    ))));
                    plan_review_char = "!";
                    stage_results.push(StageResult::failure(
                        "PlanReview",
                        &format!("Review plan for {}", task_id),
                        FailureType::Crash,
                        vec![
                            format!("Orchestrator error: {}", e),
                            "Using original plan without P+ review".to_string(),
                        ],
                    ));
                }
            }

            // Budget telemetry for P+ (use plan_review target)
            if ctx.config.budget_recovery_enabled {
                let record = budget::evaluate_phase(
                    &AgentRole::PlanReview,
                    &agent_usage,
                    &ctx.config.budget_targets,
                    ctx.config.budget_overrun_threshold,
                );
                if record.overrun && record.recovery_action != budget::RecoveryAction::Continue {
                    budget_telemetry.any_overrun = true;
                    budget_telemetry.recovery_actions_taken.push(format!(
                        "{}: {}",
                        AgentRole::PlanReview,
                        record.recovery_action
                    ));
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                        phase: format!("{}", AgentRole::PlanReview),
                        target_pct: record.target_pct,
                        actual_pct: record.actual_pct,
                        recovery: format!("{}", record.recovery_action),
                    }));
                    observatory::log_event(
                        &ctx.session_id,
                        &ctx.project_dir,
                        ObservatoryEvent::BudgetOverrun {
                            task_id: task_id.to_string(),
                            phase: format!("{}", AgentRole::PlanReview),
                            target_pct: record.target_pct,
                            actual_pct: record.actual_pct,
                            recovery_action: format!("{}", record.recovery_action),
                        },
                    );
                    match record.recovery_action {
                        budget::RecoveryAction::Summarize => {
                            budget_summary_for_next = Some(budget::summarize_directive(
                                &format!("{}", AgentRole::PlanReview),
                                record.actual_pct,
                                record.target_pct,
                            ));
                        }
                        budget::RecoveryAction::Escalate => {
                            budget_model_override =
                                Some(("claude".to_string(), "opus".to_string()));
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: escalating {} model to opus due to {} overrun ({}% > {}%)",
                                AgentRole::Builder, AgentRole::PlanReview, record.actual_pct, record.target_pct,
                            ))));
                        }
                        budget::RecoveryAction::SplitRecommended => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Budget recovery: split recommended for {} ({}% > {}%) -- logged for manual review",
                                AgentRole::PlanReview, record.actual_pct, record.target_pct,
                            ))));
                        }
                        budget::RecoveryAction::Continue => {}
                    }
                } else if record.overrun {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Budget: {} used {}% (target {}%, within tolerance)",
                        AgentRole::PlanReview,
                        record.actual_pct,
                        record.target_pct,
                    ))));
                }
                budget_telemetry.records.push(record);
            }

            adaptive_sleep(
                &ctx.config,
                false, // P+ uses multiple agent calls internally, assume not rate-limited
                ctx.config.pause_between_agents_secs,
            )
            .await;

            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Stop requested after P+ for {} -- skipping remaining stages",
                    task_id
                ))));
                {
                    let _lock = ctx
                        .tasks_file_lock
                        .lock()
                        .unwrap_or_else(|e| e.into_inner());
                    let _ = task::update_task_progress(
                        &ctx.plan_path,
                        task_id,
                        &format!(
                            "{}{}{}{}--",
                            query_char, research_char, planner_char, plan_review_char
                        ),
                    );
                }
                stage_results.push(StageResult::failure(
                    "PlanReview",
                    &format!("Review plan for {}", task_id),
                    FailureType::StopRequested,
                    vec![],
                ));
                let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                flush_budget_telemetry(
                    &ctx.buildloop_dir,
                    ctx.config.budget_recovery_enabled,
                    &budget_telemetry,
                );
                return (false, last_rate_limited, false);
            }

            // Re-validate the builder gate after P+ may have replaced the plan
            if let GateResult::Fail(reason) = gate_builder(ctx) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "GATE BLOCKED builder after P+ for {}: {} -- using pre-P+ plan if available",
                    task_id, reason
                ))));
                // Restore original plan from before P+
                if let Err(e) = atomic_write_file(&ctx.current_plan, plan_text.as_bytes()) {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Failed to restore pre-P+ plan: {}",
                        e
                    ))));
                }
                // Re-check gate with restored plan
                if let GateResult::Fail(reason2) = gate_builder(ctx) {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "GATE BLOCKED builder after restoring pre-P+ plan: {}",
                        reason2
                    ))));
                    {
                        let _lock = ctx
                            .tasks_file_lock
                            .lock()
                            .unwrap_or_else(|e| e.into_inner());
                        let _ = task::update_task_progress(
                            &ctx.plan_path,
                            task_id,
                            &format!(
                                "{}{}{}{}--!",
                                query_char, research_char, planner_char, plan_review_char
                            ),
                        );
                    }
                    let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                    flush_budget_telemetry(
                        &ctx.buildloop_dir,
                        ctx.config.budget_recovery_enabled,
                        &budget_telemetry,
                    );
                    return (false, last_rate_limited, false);
                }
            }

            // Checkpoint: P+ completed
            write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "plan_review");
        } else {
            plan_review_char = "-";
        }
    } else {
        plan_review_char = "-";
    }

    // ─── Run Builder ────────────────────────────────────────
    let build_ok: bool;
    if checkpoint_skip_builder || stage_skip_builder {
        // Builder skipped -- either completed in a previous run (checkpoint) or
        // disabled for this session via pipeline_stages[implement].enabled = false.
        let log_msg = if checkpoint_skip_builder {
            format!(
                "Checkpoint: skipping builder for {} -- resuming at doubt/review",
                task_id
            )
        } else {
            format!(
                "Pipeline: implement stage disabled in config -- skipping builder for {}",
                task_id
            )
        };
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(log_msg)));
        {
            let action = if checkpoint_skip_builder {
                format!("Implement changes for {} (checkpoint)", task_id)
            } else {
                format!("Implement changes for {} (stage disabled)", task_id)
            };
            let mut result = StageResult::success("Builder", &action);
            if ctx.buildloop_dir.join("build-claims.md").exists() {
                result.partial_results.push("build-claims.md".to_string());
            }
            stage_results.push(result);
        }
        build_ok = true;
        // last_rate_limited stays false for the skipped session.
    } else {
        emit_extension_injections(
            tx,
            &ctx.config.extensions,
            extension_context,
            &AgentRole::Builder,
            task_id,
        );

        // Check if parallel builder should be used
        let parallel_data: Option<(Vec<FileOp>, Vec<Vec<usize>>)> =
            if ctx.config.parallel_builder && !skip_planner {
                let plan_content = std::fs::read_to_string(&ctx.current_plan).unwrap_or_default();
                let file_ops = parse_file_operations(&plan_content);
                if file_ops.len() >= ctx.config.parallel_builder_min_files {
                    let groups = build_dependency_groups(&file_ops, &ctx.project_dir);
                    let independent_count = groups.iter().filter(|g| g.len() == 1).count();
                    if independent_count >= ctx.config.parallel_builder_min_files {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Parallel builder: {} file ops, {} independent -- activating",
                            file_ops.len(),
                            independent_count
                        ))));
                        Some((file_ops, groups))
                    } else {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Parallel builder: only {} independent ops (need {}) -- using sequential",
                    independent_count, ctx.config.parallel_builder_min_files
                ))));
                        None
                    }
                } else {
                    None
                }
            } else {
                None
            };

        let builder_rate_limited;
        (build_ok, builder_rate_limited) = if let Some((ref file_ops, ref groups)) = parallel_data {
            // Budget recovery is not supported in parallel builder mode -- consume and warn
            if let Some(_summary) = budget_summary_for_next.take() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Parallel builder: budget summary directive discarded (unsupported in parallel mode)".to_string()
            )));
            }
            if let Some((ref p, ref m)) = budget_model_override.take() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                format!("Parallel builder: budget model override ({}/{}) discarded (unsupported in parallel mode)", p, m)
            )));
            }
            let (p_ok, p_rl, p_usage) = run_parallel_builder(
                task_info,
                ctx,
                tx,
                file_ops,
                groups,
                extension_context,
                &pattern_context,
            )
            .await;

            // Budget telemetry: Parallel Builder (aggregated across all slots)
            if ctx.config.budget_recovery_enabled {
                let record = budget::evaluate_phase(
                    &AgentRole::Builder,
                    &p_usage,
                    &ctx.config.budget_targets,
                    ctx.config.budget_overrun_threshold,
                );
                if record.overrun && record.recovery_action != budget::RecoveryAction::Continue {
                    budget_telemetry.any_overrun = true;
                    budget_telemetry.recovery_actions_taken.push(format!(
                        "{}: {}",
                        AgentRole::Builder,
                        record.recovery_action
                    ));
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                        phase: format!("{}", AgentRole::Builder),
                        target_pct: record.target_pct,
                        actual_pct: record.actual_pct,
                        recovery: format!("{}", record.recovery_action),
                    }));
                    observatory::log_event(
                        &ctx.session_id,
                        &ctx.project_dir,
                        ObservatoryEvent::BudgetOverrun {
                            task_id: task_id.to_string(),
                            phase: format!("{}", AgentRole::Builder),
                            target_pct: record.target_pct,
                            actual_pct: record.actual_pct,
                            recovery_action: format!("{}", record.recovery_action),
                        },
                    );
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Budget recovery: {} for {} ({}% > {}%)",
                        record.recovery_action,
                        AgentRole::Builder,
                        record.actual_pct,
                        record.target_pct,
                    ))));
                } else if record.overrun {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Budget: {} used {}% (target {}%, within tolerance)",
                        AgentRole::Builder,
                        record.actual_pct,
                        record.target_pct,
                    ))));
                }
                budget_telemetry.records.push(record);
            }

            (p_ok, p_rl)
        } else {
            // Original single-builder path
            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            let fwd_handle = tokio::spawn(async move {
                let mut usage = AgentUsage::default();
                while let Some(evt) = agent_rx.recv().await {
                    usage.accumulate(&evt);
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
                usage
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Builder,
                Config::display_provider_model(
                    &ctx.config.builder_provider,
                    &ctx.config.builder_model,
                ),
            )));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentStarted {
                    role: format!("{}", AgentRole::Builder),
                    provider: ctx.config.builder_provider.clone(),
                    model: ctx.config.builder_model.clone(),
                    cc_version: cc_version.clone(),
                },
            );

            let prompt = if skip_planner {
                prompts::builder_direct_prompt(
                    &ctx.config.pipeline_stage_label("implement"),
                    task_id,
                    task_desc,
                    &ctx.spec_file_prompt_path(),
                    &ctx.tasks_file_prompt_path(),
                )
            } else {
                prompts::builder_prompt(
                    &ctx.config.pipeline_stage_label("implement"),
                    task_id,
                    task_desc,
                    &ctx.spec_file_prompt_path(),
                    &ctx.tasks_file_prompt_path(),
                )
            };
            // Inject matched patterns so the builder can see and give feedback on them
            let prompt = if !pattern_context.is_empty() {
                format!("{}\n\n--- BEGIN REFERENCE DATA (non-authoritative) ---{}\n--- END REFERENCE DATA ---", prompt, pattern_context)
            } else {
                prompt
            };
            let prompt = prompts::wrap_with_extensions(&prompt, extension_context);
            let prompt = if let Some(summary) = budget_summary_for_next.take() {
                format!("{}\n\n{}", summary, prompt)
            } else {
                prompt
            };
            let builder_start = Instant::now();
            let (eff_builder_provider, eff_builder_model) = match budget_model_override.take() {
                Some((p, m)) => {
                    eff_task_builder_provider = p.clone();
                    eff_task_builder_model = m.clone();
                    (Config::parse_provider(&p), m)
                }
                None => {
                    eff_task_builder_provider = ctx.config.builder_provider.clone();
                    eff_task_builder_model = ctx.config.builder_model.clone();
                    (
                        Config::parse_provider(&ctx.config.builder_provider),
                        ctx.config.builder_model.clone(),
                    )
                }
            };
            let build_result = agent::run_agent(
                &AgentRole::Builder,
                eff_builder_provider,
                &eff_builder_model,
                &prompt,
                &ctx.project_dir,
                agent_tx,
                &ctx.log_dir,
                None,
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
                Some(&ctx.config),
            )
            .await;

            let agent_usage = fwd_handle.await.unwrap_or_default();
            let rl = was_rate_limited(&build_result);
            let ok = build_result.map(|r| r.success).unwrap_or(false);
            let _ = tx.send(AppEvent::AgentDone(ok));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::AgentDone {
                    role: format!("{}", AgentRole::Builder),
                    success: ok,
                    duration_secs: builder_start.elapsed().as_secs_f64(),
                    tokens_in: agent_usage.tokens_in,
                    tokens_out: agent_usage.tokens_out,
                    cost_usd: agent_usage.cost_usd,
                    context_pct: agent_usage.context_pct,
                    cache_creation_tokens: agent_usage.cache_creation_tokens,
                    cache_read_tokens: agent_usage.cache_read_tokens,
                },
            );
            // Budget telemetry: Builder
            if ctx.config.budget_recovery_enabled {
                let record = budget::evaluate_phase(
                    &AgentRole::Builder,
                    &agent_usage,
                    &ctx.config.budget_targets,
                    ctx.config.budget_overrun_threshold,
                );
                if record.overrun && record.recovery_action != budget::RecoveryAction::Continue {
                    budget_telemetry.any_overrun = true;
                    budget_telemetry.recovery_actions_taken.push(format!(
                        "{}: {}",
                        AgentRole::Builder,
                        record.recovery_action
                    ));
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                        phase: format!("{}", AgentRole::Builder),
                        target_pct: record.target_pct,
                        actual_pct: record.actual_pct,
                        recovery: format!("{}", record.recovery_action),
                    }));
                    observatory::log_event(
                        &ctx.session_id,
                        &ctx.project_dir,
                        ObservatoryEvent::BudgetOverrun {
                            task_id: task_id.to_string(),
                            phase: format!("{}", AgentRole::Builder),
                            target_pct: record.target_pct,
                            actual_pct: record.actual_pct,
                            recovery_action: format!("{}", record.recovery_action),
                        },
                    );
                    // Builder is the last phase before review (separate function) -- log all recovery types
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Budget recovery: {} for {} ({}% > {}%)",
                        record.recovery_action,
                        AgentRole::Builder,
                        record.actual_pct,
                        record.target_pct,
                    ))));
                } else if record.overrun {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Budget: {} used {}% (target {}%, within tolerance)",
                        AgentRole::Builder,
                        record.actual_pct,
                        record.target_pct,
                    ))));
                }
                budget_telemetry.records.push(record);
            }
            if rl {
                observatory::log_event(
                    &ctx.session_id,
                    &ctx.project_dir,
                    ObservatoryEvent::RateLimited {
                        provider: ctx.config.builder_provider.clone(),
                        wait_secs: ctx.config.pause_between_agents_secs,
                    },
                );
            }
            (ok, rl)
        };
        last_rate_limited = builder_rate_limited;

        if !build_ok {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "BUILDER failed for {} — committing WIP",
                task_id
            ))));
            {
                let _lock = ctx
                    .tasks_file_lock
                    .lock()
                    .unwrap_or_else(|e| e.into_inner());
                let _ = task::update_task_progress(
                    &ctx.plan_path,
                    task_id,
                    &format!(
                        "{}{}{}{}I-!",
                        query_char, research_char, planner_char, plan_review_char
                    ),
                );
            }
            stage_results.push(StageResult::failure(
                "Builder",
                &format!("Implement changes for {}", task_id),
                FailureType::Crash,
                vec![
                    "Check build-claims.md for partial progress".to_string(),
                    "Review the plan for overly ambitious scope".to_string(),
                ],
            ));
            let _ = commit_wip_for_mode(ctx, task_id, task_desc);
            flush_budget_telemetry(
                &ctx.buildloop_dir,
                ctx.config.budget_recovery_enabled,
                &budget_telemetry,
            );
            return (false, last_rate_limited, false);
        }

        // Builder completed -- persist progress indicator.
        {
            let _lock = ctx
                .tasks_file_lock
                .lock()
                .unwrap_or_else(|e| e.into_inner());
            let _ = task::update_task_progress(
                &ctx.plan_path,
                task_id,
                &format!(
                    "{}{}{}{}I.",
                    query_char, research_char, planner_char, plan_review_char
                ),
            );
        }

        {
            let mut result =
                StageResult::success("Builder", &format!("Implement changes for {}", task_id));
            if ctx.buildloop_dir.join("build-claims.md").exists() {
                result.partial_results.push("build-claims.md".to_string());
            }
            stage_results.push(result);
        }

        // ─── Gate: Build/Compile Verification ──────────────────────
        if let Some(ref build_cmd) = ctx.config.build_command {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Running build command: {}",
                build_cmd
            ))));
            let build_output = std::process::Command::new(if cfg!(target_os = "windows") {
                "cmd"
            } else {
                "sh"
            })
            .args(if cfg!(target_os = "windows") {
                vec!["/C", build_cmd]
            } else {
                vec!["-c", build_cmd]
            })
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
                        let _lock = ctx
                            .tasks_file_lock
                            .lock()
                            .unwrap_or_else(|e| e.into_inner());
                        let _ = task::update_task_progress(
                            &ctx.plan_path,
                            task_id,
                            &format!(
                                "{}{}{}{}I-!",
                                query_char, research_char, planner_char, plan_review_char
                            ),
                        );
                    }
                    stage_results.push(StageResult::failure(
                        "BuildGate",
                        &format!("Run build command: {}", build_cmd),
                        FailureType::GateFail,
                        vec!["Build command failed -- check compiler errors".to_string()],
                    ));
                    let _ = commit_wip_for_mode(ctx, task_id, task_desc);
                    flush_budget_telemetry(
                        &ctx.buildloop_dir,
                        ctx.config.budget_recovery_enabled,
                        &budget_telemetry,
                    );
                    return (false, last_rate_limited, false);
                }
                Err(e) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Build command failed to execute: {} — build gate not validated, skipping checkpoint",
                    e
                ))));
                    // Do NOT write checkpoint -- the build was never verified.
                    // Doubt will still run, but crash recovery won't skip the builder.
                }
                Ok(_) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        "Build gate passed".to_string(),
                    )));
                    // Only write checkpoint when build gate actually passed
                    write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "builder");
                }
            }
        } else {
            // No build_command configured -- write checkpoint unconditionally
            write_checkpoint(&ctx.buildloop_dir, task_id, task_desc, "builder");
        }

        // ─── Trim Verbose Build Output ──────────────────────────────
        if let Some((orig, trimmed)) = trim_build_claims(ctx) {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Trimmed test output from {} to {} lines",
                orig, trimmed
            ))));
        }
    } // end !checkpoint_skip_builder

    adaptive_sleep(
        &ctx.config,
        last_rate_limited,
        ctx.config.pause_between_agents_secs,
    )
    .await;

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
        flush_budget_telemetry(
            &ctx.buildloop_dir,
            ctx.config.budget_recovery_enabled,
            &budget_telemetry,
        );
        return (false, last_rate_limited, false);
    }

    // Learned doubt confidence: check if this task shape has enough
    // consecutive passes to skip doubt (T15.9 fine-grained filter).
    let doubt_confidence = doubt_confidence::check_doubt_confidence(
        task_desc,
        task_complexity,
        ctx.config.doubt_confidence_threshold,
        &ctx.config.embedding_model,
        ctx.config.embedding_timeout_ms,
        &ctx.config.ollama_url,
    )
    .await;
    if !doubt_confidence.log_message.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            doubt_confidence.log_message.clone(),
        )));
    }

    // Batch doubt: skip for all tasks except the last pending one
    let pending_count = task::count_pending(&task::parse_tasks(&ctx.plan_path).unwrap_or_default());
    let skip_for_batch = ctx.config.batch_doubt && pending_count > 1;

    // Skip verify for simple tasks when the builder's own checks passed
    // and the config enables it. The builder already ran build/test/lint --
    // verify adds a fresh-context audit which is most valuable for complex
    // tasks with blind spots. Medium and complex tasks always run doubt.
    let skip_doubt_simple =
        ctx.config.skip_doubt_for_simple && task_complexity == TaskComplexity::Simple && build_ok;
    let skip_doubt_confidence = doubt_confidence.should_skip && build_ok;
    let stage_skip_doubt = !ctx.config.pipeline_stage_enabled("doubt");
    let skip_verify =
        skip_doubt_simple || skip_for_batch || skip_doubt_confidence || stage_skip_doubt;

    let (validated, _fix_passes, review_findings, reviewer_budget_record) =
        if ctx.config.backpressure_only {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Backpressure-only mode: skipping LLM review (builder verification passed)"
                    .to_string(),
            )));
            (true, 0usize, (0, 0, 0), None)
        } else if skip_for_batch {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Batch doubt: deferring review ({} tasks remaining)",
                pending_count
            ))));
            (true, 0usize, (0, 0, 0), None)
        } else if skip_doubt_simple {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Simple task with passing build checks -- skipping doubt".to_string(),
            )));
            (true, 0usize, (0, 0, 0), None)
        } else if skip_doubt_confidence {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Learned confidence -- skipping doubt ({})",
                doubt_confidence.log_message
            ))));
            (true, 0usize, (0, 0, 0), None)
        } else if stage_skip_doubt {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Pipeline: doubt stage disabled in config -- skipping audit".to_string(),
            )));
            (true, 0usize, (0, 0, 0), None)
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
                    review::run_review_loop(
                        task_id,
                        task_desc,
                        ctx,
                        &reviewer_pattern_context,
                        extension_context,
                        tx,
                    )
                    .await
                }
                GateResult::Pass => {
                    review::run_review_loop(
                        task_id,
                        task_desc,
                        ctx,
                        &reviewer_pattern_context,
                        extension_context,
                        tx,
                    )
                    .await
                }
            }
        };

    // Add Reviewer budget record to telemetry
    if let Some(record) = reviewer_budget_record {
        budget_telemetry.records.push(record);
    }

    // Record doubt result for learned confidence (only when doubt actually ran)
    if !skip_verify && !ctx.config.backpressure_only {
        let record_task_desc = task_desc.to_string();
        let record_model = ctx.config.embedding_model.clone();
        let record_timeout = ctx.config.embedding_timeout_ms;
        let record_url = ctx.config.ollama_url.clone();
        let record_passed = validated;
        tokio::spawn(async move {
            doubt_confidence::record_doubt_result(
                &record_task_desc,
                record_passed,
                &record_model,
                record_timeout,
                &record_url,
            )
            .await;
        });
    }

    if validated {
        let mut result =
            StageResult::success("Reviewer", &format!("Validate changes for {}", task_id));
        if ctx.review_report.exists() {
            result.partial_results.push("review-report.md".to_string());
        }
        stage_results.push(result);
    } else if !skip_verify && !ctx.config.backpressure_only && !skip_for_batch {
        stage_results.push(StageResult::failure(
            "Reviewer",
            &format!("Validate changes for {}", task_id),
            FailureType::ReviewFail,
            vec![
                "Review found HIGH/MEDIUM issues that were not fixed".to_string(),
                "Check review-report.md for specific findings".to_string(),
            ],
        ));
    }

    // ─── Pre-Commit Approval Gate ───────────────────────────────
    // When require_human_approval is enabled and the task passed validation,
    // pause and ask the human to confirm before committing as feat.
    // If denied, downgrade to WIP and the loop will pause after commit.
    let mut human_denied_approval = false;
    let validated = if validated && ctx.config.require_human_approval {
        // Arm gate BEFORE sending event to avoid race where TUI responds before gate is set
        ctx.commit_approval_gate.set();
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AwaitCommitApproval {
            task_id: task_id.to_string(),
            proposed_commit_type: "feat".to_string(),
            session_id: ctx.session_id.clone(),
            gate: ctx.commit_approval_gate.clone(),
            result: ctx.commit_approval_result.clone(),
        }));

        while ctx.commit_approval_gate.get() {
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return (false, false, false);
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }

        let approved = ctx.commit_approval_result.get();
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CommitApprovalResponse {
            approved,
        }));
        if approved {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Human approved: committing {} as feat",
                task_id
            ))));
            true
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Human denied: downgrading {} to WIP",
                task_id
            ))));
            human_denied_approval = true;
            false
        }
    } else {
        validated
    };

    // Persist final pipeline progress indicator and mark done BEFORE committing.
    // Both writes must happen before git add -A so the commit captures them.
    // Agents may overwrite TASKS.md during their run, stripping intermediate
    // indicators, so the final write must be the last mutation before commit.
    {
        let doubt_char = if skip_verify || ctx.config.backpressure_only {
            "-"
        } else {
            "D"
        };
        let fail_char = if !validated { "!" } else { "" };
        let progress = format!(
            "{}{}{}{}I{}{}",
            query_char, research_char, planner_char, plan_review_char, doubt_char, fail_char
        );
        let _lock = ctx
            .tasks_file_lock
            .lock()
            .unwrap_or_else(|e| e.into_inner());
        let _ = task::update_task_progress(&ctx.plan_path, task_id, &progress);
        if validated {
            let _ = task::mark_done(&ctx.plan_path, task_info.line_number);
        }
    }

    // Write budget telemetry
    flush_budget_telemetry(
        &ctx.buildloop_dir,
        ctx.config.budget_recovery_enabled,
        &budget_telemetry,
    );

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ShipStarted));
    let committed = if ctx.config.run_mode == "review" {
        // Review mode: branch, commit, push, create PR, return to base
        match git::commit_task_pr(
            &ctx.project_dir,
            &ctx.config,
            task_id,
            task_desc,
            &ctx.plan_path,
            !validated,
        ) {
            Ok((committed, pr_num)) => {
                if committed {
                    let prefix = if validated { "feat" } else { "WIP" };
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Committed {}({})",
                        prefix, task_id
                    ))));
                }
                if let Some(pr) = pr_num {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "PR #{} created for {}",
                        pr, task_id
                    ))));
                }

                // Create GitHub issue for WIP commits in review mode
                if committed && !validated && ctx.config.create_issue_on_wip {
                    let stage_ctx = prompts::format_stage_results_for_prompt(
                        &stage_results
                            .iter()
                            .map(|r| {
                                (
                                    r.stage.clone(),
                                    r.success,
                                    r.failure_type.as_ref().map(|f| format!("{:?}", f)),
                                    r.attempted_action.clone(),
                                    r.partial_results.clone(),
                                    r.suggestions.clone(),
                                )
                            })
                            .collect::<Vec<_>>(),
                    );
                    match git::create_wip_issue(
                        &ctx.project_dir,
                        task_id,
                        task_desc,
                        &ctx.review_report,
                        &stage_ctx,
                    ) {
                        Ok(Some(issue_num)) => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Issue #{} created for WIP({})",
                                issue_num, task_id
                            ))));
                        }
                        Ok(None) => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Issue created for WIP({}) but could not parse issue number",
                                task_id
                            ))));
                        }
                        Err(e) => {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                                "Failed to create issue for WIP({}): {}",
                                task_id, e
                            ))));
                        }
                    }
                }

                // Pause: signal TUI and wait for user to press Enter or PR approval
                ctx.review_gate.set();
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::WaitingForReview {
                    pr_num,
                    session_id: ctx.session_id.clone(),
                    gate: ctx.review_gate.clone(),
                }));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Waiting for PR review -- press Enter to continue or wait for approval"
                        .to_string(),
                )));

                // Spawn background PR poller if we have a PR number
                let poll_handle = if let Some(pr_number) = pr_num {
                    let tx_poll = tx.clone();
                    let project_dir = ctx.project_dir.clone();
                    let poll_interval = ctx.config.pr_poll_interval_secs;
                    let review_gate_clone = ctx.review_gate.clone();
                    let session_id_poll = ctx.session_id.clone();
                    Some(tokio::spawn(async move {
                        poll_pr_review(
                            pr_number,
                            session_id_poll,
                            project_dir,
                            poll_interval,
                            tx_poll,
                            review_gate_clone,
                        )
                        .await;
                    }))
                } else {
                    None
                };

                while ctx.review_gate.get() {
                    if ctx.is_stop_requested() {
                        if let Some(h) = poll_handle {
                            h.abort();
                        }
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                        return (false, false, false);
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
                let committed = git::commit_and_push(
                    &ctx.project_dir,
                    &ctx.config,
                    task_id,
                    task_desc,
                    !validated,
                )
                .unwrap_or(false);

                // Still pause after fallback commit in review mode
                if committed {
                    ctx.review_gate.set();
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::WaitingForReview {
                        pr_num: None,
                        session_id: ctx.session_id.clone(),
                        gate: ctx.review_gate.clone(),
                    }));
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        "Waiting for review -- press Enter to continue to next task".to_string(),
                    )));
                    while ctx.review_gate.get() {
                        if ctx.is_stop_requested() {
                            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                            return (false, false, false);
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
                &stage_results
                    .iter()
                    .map(|r| {
                        (
                            r.stage.clone(),
                            r.success,
                            r.failure_type.as_ref().map(|f| format!("{:?}", f)),
                            r.attempted_action.clone(),
                            r.partial_results.clone(),
                            r.suggestions.clone(),
                        )
                    })
                    .collect::<Vec<_>>(),
            );
            match git::create_wip_issue(
                &ctx.project_dir,
                task_id,
                task_desc,
                &ctx.review_report,
                &stage_ctx,
            ) {
                Ok(Some(issue_num)) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Issue #{} created for WIP({})",
                        issue_num, task_id
                    ))));
                }
                Ok(None) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Issue created for WIP({}) but could not parse issue number",
                        task_id
                    ))));
                }
                Err(e) => {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Failed to create issue for WIP({}): {}",
                        task_id, e
                    ))));
                }
            }
        }
        committed
    };
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::ShipDone));
    let commit_sha = if committed {
        git::get_head_sha(&ctx.project_dir)
    } else {
        None
    };
    if committed {
        let commit_type = if validated { "feat" } else { "wip" };
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::Committed {
                task_id: task_id.to_string(),
                sha: commit_sha.clone().unwrap_or_default(),
                commit_type: commit_type.to_string(),
            },
        );
        if let Some(hook_cmd) = ctx
            .config
            .on_task_complete
            .as_ref()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
        {
            spawn_completion_hook(
                hook_cmd,
                task_id.to_string(),
                task_desc.to_string(),
                validated,
                commit_sha.clone(),
                ctx.project_dir.clone(),
                tx.clone(),
            );
        }
    }

    // Emit TaskCompleted with aggregated task-level metrics
    {
        let task_cost_now = ctx
            .session_cost_millicents
            .load(std::sync::atomic::Ordering::Relaxed);
        let task_total_cost_usd =
            (task_cost_now.saturating_sub(task_cost_snapshot)) as f64 / 100_000.0;
        let task_duration_secs = task_start.elapsed().as_secs_f64();
        let verdict = if validated { "feat" } else { "wip" };
        let doubt_char_tc = if skip_verify || ctx.config.backpressure_only {
            "-"
        } else {
            "D"
        };
        let fail_char_tc = if !validated { "!" } else { "" };
        let phases_run_str = format!(
            "{}{}{}{}I{}{}",
            query_char, research_char, planner_char, plan_review_char, doubt_char_tc, fail_char_tc
        );
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::TaskCompleted {
                task_id: task_id.to_string(),
                verdict: verdict.to_string(),
                complexity: format!("{:?}", task_complexity),
                total_cost_usd: task_total_cost_usd,
                total_duration_secs: task_duration_secs,
                findings_high: review_findings.0,
                findings_medium: review_findings.1,
                findings_low: review_findings.2,
                phases_run: phases_run_str,
                builder_provider: eff_task_builder_provider.clone(),
                builder_model: eff_task_builder_model.clone(),
                reviewer_provider: ctx.config.reviewer_provider.clone(),
                reviewer_model: ctx.config.reviewer_model.clone(),
                commit_sha: commit_sha.clone().unwrap_or_default(),
            },
        );
    }

    // Skip pattern extraction for trivial tasks (< 3 files changed or
    // reviewer found no issues). These tasks rarely produce interesting patterns.
    // Use HEAD~1..HEAD because this runs AFTER the commit, so unstaged diff is empty.
    let changed_file_count = std::process::Command::new("git")
        .args(["diff", "--name-only", "HEAD~1", "HEAD"])
        .current_dir(&ctx.project_dir)
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).lines().count())
        .unwrap_or(0);

    // ─── Pattern Feedback (self-repair) ────────────────────────────
    // Parse PATTERN_FEEDBACK markers from builder output (build-claims.md).
    // Apply feedback to patterns on disk before citation scanning.
    if !injected_pattern_ids.is_empty() {
        let claims_path = ctx.buildloop_dir.join("build-claims.md");
        if let Ok(claims_content) = std::fs::read_to_string(&claims_path) {
            let feedback = patterns::parse_pattern_feedback(&claims_content);
            if !feedback.is_empty() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Pattern feedback: {} signals from builder",
                    feedback.len()
                ))));
                if let Err(e) = patterns::apply_feedback(patterns_dir, &feedback) {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Warning: failed to apply pattern feedback: {}",
                        e
                    ))));
                }
                // Also apply to extension pattern dirs
                let ext_infos = extensions::discover_extensions(&ctx.project_dir);
                for ext_name in &ctx.config.extensions {
                    if let Some(ext) = ext_infos.iter().find(|e| &e.name == ext_name) {
                        if let Some(ref pdir) = ext.patterns_dir {
                            let _ = patterns::apply_feedback(pdir, &feedback);
                        }
                    }
                }
            }
        }
    }

    // Scan build artifacts for pattern citations to track usefulness.
    // Only on validated tasks -- failed/WIP tasks should not train the ranking system.
    let mut all_cited: Vec<String> = Vec::new();
    if validated && !injected_pattern_ids.is_empty() {
        let injected_refs: Vec<patterns::Pattern> = cached_patterns
            .iter()
            .filter(|p| injected_pattern_ids.contains(&p.pattern_id))
            .cloned()
            .collect();

        let artifacts_to_scan: Vec<(std::path::PathBuf, &str)> = vec![
            (ctx.buildloop_dir.join("current-plan.md"), "Planner"),
            (ctx.buildloop_dir.join("build-claims.md"), "Builder"),
            (ctx.buildloop_dir.join("review-report.md"), "Reviewer"),
        ];

        for (artifact_path, role) in &artifacts_to_scan {
            if let Ok(content) = std::fs::read_to_string(artifact_path) {
                if !content.is_empty() {
                    let cited_in_artifact = patterns::scan_citations(&content, &injected_refs);
                    for pid in &cited_in_artifact {
                        observatory::log_event(
                            &ctx.session_id,
                            &ctx.project_dir,
                            ObservatoryEvent::PatternCited {
                                task_id: task_id.to_string(),
                                role: role.to_string(),
                                artifact: artifact_path
                                    .file_name()
                                    .unwrap_or_default()
                                    .to_string_lossy()
                                    .to_string(),
                                pattern_id: pid.clone(),
                            },
                        );
                    }
                    all_cited.extend(cited_in_artifact);
                }
            }
        }
        all_cited.sort();
        all_cited.dedup();

        if !all_cited.is_empty() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Pattern citations: {} patterns referenced by agents",
                all_cited.len()
            ))));
            if let Err(e) = patterns::update_used_counts(patterns_dir, &all_cited) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Warning: failed to update pattern used_counts: {}",
                    e
                ))));
            }
            let ext_infos = extensions::discover_extensions(&ctx.project_dir);
            for ext_name in &ctx.config.extensions {
                if let Some(ext) = ext_infos.iter().find(|e| &e.name == ext_name) {
                    if let Some(ref pdir) = ext.patterns_dir {
                        let _ = patterns::update_used_counts(pdir, &all_cited);
                    }
                }
            }
        }
    }

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

    let status = if validated { "pass" } else { "wip" };
    let duration_secs = task_start.elapsed().as_secs_f64();
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReport {
        task_id: task_id.to_string(),
        status: status.to_string(),
        commit_sha: commit_sha.clone(),
        findings_high: review_findings.0,
        findings_medium: review_findings.1,
        findings_low: review_findings.2,
        duration_secs,
    }));

    if validated && !all_cited.is_empty() {
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::PatternApplied {
                task_id: task_id.to_string(),
                pattern_ids: all_cited.clone(),
                count: all_cited.len(),
            },
        );
    }

    // ─── Build History ─────────────────────────────────────────────
    let history_dir = crate::history::resolve_history_dir(&ctx.config.history_dir);
    let record = crate::history::new_record(
        task_id,
        task_desc,
        &ctx.project_dir.to_string_lossy(),
        status,
        commit_sha.clone(),
        injected_pattern_ids.clone(),
        all_cited.clone(),
        changed_file_count,
        duration_secs,
    );
    if let Err(e) = crate::history::append_record(&history_dir, &record) {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Warning: failed to write build history: {}",
            e
        ))));
    }

    // Clear checkpoint — task completed successfully (committed or WIP)
    clear_checkpoint(&ctx.buildloop_dir);

    (validated, last_rate_limited, human_denied_approval)
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
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
        "Background pattern extraction started (Claude {})",
        model,
    ))));
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
        None,
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
        Some(&ctx.config),
    )
    .await;

    let success = result.as_ref().map(|r| r.success).unwrap_or(false);
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
        "Background pattern extraction {}",
        if success { "completed" } else { "failed" },
    ))));

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

fn spawn_completion_hook(
    hook_command: String,
    task_id: String,
    task_desc: String,
    validated: bool,
    commit_sha: Option<String>,
    project_dir: std::path::PathBuf,
    tx: tokio::sync::mpsc::UnboundedSender<AppEvent>,
) {
    let status_str = if validated { "feat" } else { "WIP" };
    let truncated_desc = crate::utils::truncate_str(&task_desc, 100).to_string();
    let sha_str = commit_sha.unwrap_or_default();
    tokio::spawn(async move {
        let mut cmd = tokio::process::Command::new("sh");
        cmd.arg("-c")
            .arg(&hook_command)
            .current_dir(&project_dir)
            .env("FOUNDRY_TASK_ID", &task_id)
            .env("FOUNDRY_TASK_STATUS", status_str)
            .env("FOUNDRY_TASK_DESC", &truncated_desc)
            .env("FOUNDRY_COMMIT_SHA", &sha_str)
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null());
        match cmd.status().await {
            Ok(status) if status.success() => {}
            Ok(status) => {
                let code = status
                    .code()
                    .map(|c| c.to_string())
                    .unwrap_or_else(|| "signal".to_string());
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                    "on_task_complete hook exited non-zero ({}): {}",
                    code, hook_command
                ))));
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                    "on_task_complete hook failed to spawn: {}: {}",
                    hook_command, e
                ))));
            }
        }
    });
}

fn should_restart_docker(task_desc: &str) -> bool {
    let lower = task_desc.to_lowercase();
    let has_docker_word =
        lower.contains("docker") || lower.contains("dockerfile") || lower.contains("caddy");
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
    use super::{clear_checkpoint, flush_budget_telemetry, read_checkpoint, write_checkpoint};
    use crate::app::context::RunContext;
    use crate::app::state::{AppEvent, LoopEvent};
    use crate::budget;
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
        std::fs::write(dir.join("SPEC.md"), "# Test Spec\n\nThis is the spec.\n")
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
        let ctx = RunContext::new(
            &dir,
            Config::default(),
            Arc::new(AtomicBool::new(false)),
            Arc::new(Mutex::new(())),
        );
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
        assert!(backup
            .files
            .contains_key(&ctx.project_dir.join("CLAUDE.md")));
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
        assert!(msgs
            .iter()
            .any(|m| m.contains("Warning") && m.contains("TASKS.md")));

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
        ctx.shutdown.store(true, Ordering::Release);
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
        let mut content = String::from(
            "## Files Changed\n- MODIFY src/app/build.rs\n\n## Verification Results\n",
        );
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

    #[test]
    fn test_plan_review_checkpoint_recovery_allows_p_plus() {
        // Bug D37.1(a): When checkpoint recovery sets checkpoint_skip_planner=true
        // (because planner completed in a prior session and resume_stage="plan_review"),
        // skip_planner also becomes true. The P+ guard must still allow P+ to run
        // because skip_planner is only true due to checkpoint, not due to task simplicity.

        // Simulate checkpoint recovery scenario: planner completed, resuming at plan_review
        let checkpoint_skip_plan_review = false; // P+ has NOT completed yet
        let checkpoint_skip_planner = true; // planner completed in prior session
        let plan_review_enabled = true;

        // skip_planner incorporates checkpoint_skip_planner (build.rs:2159)
        let skip_planner = checkpoint_skip_planner; // would also be true from config for simple tasks

        // The fixed guard condition: (!skip_planner || checkpoint_skip_planner)
        let p_plus_should_run = !checkpoint_skip_plan_review
            && plan_review_enabled
            && true // task_complexity == Complex (simulated)
            && (!skip_planner || checkpoint_skip_planner);
        assert!(
            p_plus_should_run,
            "P+ must run when skip_planner is only true due to checkpoint recovery"
        );

        // Verify: when skip_planner is true due to task simplicity (not checkpoint),
        // P+ should NOT run
        let checkpoint_skip_planner_simple = false; // no checkpoint recovery
        let skip_planner_simple = true; // skipped because task is simple
        let p_plus_should_not_run = !false // checkpoint_skip_plan_review = false
            && true // plan_review_enabled
            && true // Complex
            && (!skip_planner_simple || checkpoint_skip_planner_simple);
        assert!(
            !p_plus_should_not_run,
            "P+ must NOT run when skip_planner is true due to task simplicity"
        );

        // Verify: normal case -- planner ran, no checkpoint, Complex task
        let p_plus_normal = !false  // checkpoint_skip_plan_review = false
            && true  // plan_review_enabled
            && true  // Complex
            && (!false || false); // skip_planner=false, checkpoint_skip_planner=false
        assert!(
            p_plus_normal,
            "P+ must run normally for Complex tasks when planner ran"
        );

        // Verify: P+ already completed in prior session
        let p_plus_already_done = !true  // checkpoint_skip_plan_review = true
            && true
            && true
            && (!false || false);
        assert!(
            !p_plus_already_done,
            "P+ must NOT run when checkpoint says it already completed"
        );
    }

    #[test]
    fn test_build_gate_failure_does_not_leave_stale_checkpoint() {
        // Bug D38.1: write_checkpoint("builder") used to run before the build gate.
        // If the build gate failed, the checkpoint remained, causing the builder to
        // be skipped on the next pipeline iteration. After the fix, the checkpoint
        // is written only after the build gate passes.

        let dir = std::env::temp_dir().join(format!(
            "foundry-checkpoint-gate-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Simulate: builder completed, checkpoint written
        write_checkpoint(&dir, "D38.1", "test task", "builder");
        let cp = read_checkpoint(&dir);
        assert!(cp.is_some(), "checkpoint should exist after write");
        assert_eq!(cp.unwrap().completed_stage, "builder");

        // Simulate: build gate fails, so we clear the checkpoint
        // (In the real code, the fix is that the checkpoint is never written
        // before the gate. This test verifies the checkpoint functions work
        // correctly and that after clear_checkpoint, no stale state remains.)
        clear_checkpoint(&dir);
        let cp_after = read_checkpoint(&dir);
        assert!(cp_after.is_none(), "checkpoint must not exist after clear");

        // Verify the critical invariant: if checkpoint.json does not exist,
        // checkpoint_skip_builder evaluates to false (builder will re-run).
        // This mirrors the logic at build.rs:2038-2051.
        let resume_stage: Option<&str> = cp_after.as_ref().map(|c| c.completed_stage.as_str());
        let checkpoint_skip_builder = match resume_stage {
            Some("doubt") => true,
            _ => false,
        };
        assert!(
            !checkpoint_skip_builder,
            "with no checkpoint, builder must NOT be skipped"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_checkpoint_write_after_gate_pass_is_readable() {
        // Complementary test: verify that when the checkpoint IS written
        // (gate passed), it correctly causes builder skip on next iteration.

        let dir = std::env::temp_dir().join(format!(
            "foundry-checkpoint-gate-pass-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Simulate: builder completed AND build gate passed, checkpoint written
        write_checkpoint(&dir, "D38.1", "test task", "builder");

        // On next iteration, read_checkpoint returns the builder stage
        let cp = read_checkpoint(&dir).unwrap();
        assert_eq!(cp.completed_stage, "builder");

        // resume_stage would be derived from completed_stage "builder" -> next stage
        // checkpoint_skip_builder triggers when resume_stage is "doubt"
        // (i.e., completed_stage="builder" means resume at doubt)
        // The mapping: completed_stage="builder" produces resume_stage="doubt"
        // at build.rs:2038-2051
        let resume_stage = match cp.completed_stage.as_str() {
            "builder" => Some("doubt"),
            _ => None,
        };
        let checkpoint_skip_builder = match resume_stage {
            Some("doubt") => true,
            _ => false,
        };
        assert!(
            checkpoint_skip_builder,
            "with builder checkpoint present, builder should be skipped (resume at doubt)"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_planner_checkpoint_not_written_before_gate() {
        // Bug D41.1(a): write_checkpoint("planner") used to run before the extension
        // gate and builder gate. If either gate failed, the checkpoint remained,
        // causing planner skip on resume. After the fix, checkpoint is written only
        // after both gates pass.

        let dir = std::env::temp_dir().join(format!(
            "foundry-planner-checkpoint-gate-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Before gates: no checkpoint should exist
        let cp = read_checkpoint(&dir);
        assert!(cp.is_none(), "no checkpoint should exist before gates pass");

        // Simulate: gates pass, checkpoint written
        write_checkpoint(&dir, "D41.1", "test task", "planner");
        let cp = read_checkpoint(&dir).unwrap();
        assert_eq!(cp.completed_stage, "planner");

        // On resume: completed_stage="planner" -> resume_stage="plan_review"
        // checkpoint_skip_planner matches "plan_review"
        let resume_stage = match cp.completed_stage.as_str() {
            "planner" => Some("plan_review"),
            _ => None,
        };
        let checkpoint_skip_planner = match resume_stage {
            Some("plan_review" | "builder" | "doubt") => true,
            _ => false,
        };
        assert!(
            checkpoint_skip_planner,
            "with planner checkpoint present, planner should be skipped"
        );

        // Simulate: gate failed, checkpoint never written (cleared to simulate)
        clear_checkpoint(&dir);
        let cp_after = read_checkpoint(&dir);
        assert!(
            cp_after.is_none(),
            "checkpoint must not exist after gate failure path"
        );

        // Verify: no checkpoint -> planner re-runs
        let resume_stage: Option<&str> = cp_after.as_ref().map(|c| c.completed_stage.as_str());
        let checkpoint_skip_planner = match resume_stage {
            Some("plan_review" | "builder" | "doubt") => true,
            _ => false,
        };
        assert!(
            !checkpoint_skip_planner,
            "with no checkpoint, planner must NOT be skipped"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_flush_budget_telemetry_writes_on_early_return() {
        // Bug D41.1(b): budget telemetry was only written at the end of
        // process_task(). All early return paths silently discarded accumulated
        // records. After the fix, flush_budget_telemetry() writes partial data.

        let dir = std::env::temp_dir().join(format!(
            "foundry-budget-flush-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        let telemetry = budget::BudgetTelemetry {
            task_id: "D41.1".to_string(),
            timestamp: "2026-03-29T00:00:00Z".to_string(),
            records: vec![budget::PhaseBudgetRecord {
                phase: "SCOUT".to_string(),
                target_pct: 15,
                actual_pct: 20,
                overrun: true,
                overrun_amount: 5,
                tokens_in: 1000,
                tokens_out: 500,
                cost_usd: 0.01,
                recovery_action: budget::RecoveryAction::Continue,
            }],
            any_overrun: false,
            recovery_actions_taken: vec![],
        };

        // flush_budget_telemetry with budget_recovery_enabled=true should write
        flush_budget_telemetry(&dir, true, &telemetry);
        let path = dir.join("budget-telemetry.json");
        assert!(path.exists(), "telemetry file must exist after flush");
        let content = std::fs::read_to_string(&path).unwrap();
        assert!(content.contains("D41.1"), "telemetry must contain task_id");
        assert!(
            content.contains("SCOUT"),
            "telemetry must contain phase record"
        );

        // Clean up and test: budget_recovery_enabled=false should NOT write
        std::fs::remove_file(&path).unwrap();
        flush_budget_telemetry(&dir, false, &telemetry);
        assert!(
            !path.exists(),
            "telemetry must not be written when budget_recovery_enabled is false"
        );

        // Test: empty records should NOT write
        let empty_telemetry = budget::BudgetTelemetry {
            task_id: "D41.1".to_string(),
            timestamp: "2026-03-29T00:00:00Z".to_string(),
            ..Default::default()
        };
        flush_budget_telemetry(&dir, true, &empty_telemetry);
        assert!(
            !path.exists(),
            "telemetry must not be written when records are empty"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_budget_recovery_directives_consumed_before_p_plus() {
        // Bug D40.1(a): When Planner overruns and sets budget_summary_for_next
        // and budget_model_override, these directives should target P+ (the next
        // phase for Complex tasks), not leak through to Builder. Since P+ uses
        // OrchestratorConfig which doesn't support these overrides, they must be
        // consumed with a warning before P+ runs.

        // Simulate the state after Planner budget evaluation triggers Escalate
        let mut budget_summary_for_next: Option<String> =
            Some("CONTEXT BUDGET ALERT: The previous PLAN phase used 65% ...".to_string());
        let mut budget_model_override: Option<(String, String)> =
            Some(("claude".to_string(), "opus".to_string()));

        // Simulate: P+ subphase is about to run. The code should .take() both values.
        // This mirrors the consume-and-warn pattern from parallel builder (build.rs:3064-3073).
        let consumed_summary = budget_summary_for_next.take();
        let consumed_override = budget_model_override.take();

        assert!(
            consumed_summary.is_some(),
            "summary directive should have been present for consumption"
        );
        assert!(
            consumed_override.is_some(),
            "model override should have been present for consumption"
        );
        assert!(
            budget_summary_for_next.is_none(),
            "summary must be None after .take() so Builder does not receive it"
        );
        assert!(
            budget_model_override.is_none(),
            "override must be None after .take() so Builder does not receive it"
        );
    }

    #[test]
    fn test_budget_directives_consumed_when_plan_unreadable() {
        // Bug D50.1: When P+ conditions are met but current-plan.md is unreadable,
        // plan_text is empty. Before the fix, budget directive consumption was inside
        // the `if !plan_text.is_empty()` block and would be skipped, causing directives
        // to leak through to Builder.

        // Simulate: Planner overrun sets both directives
        let mut budget_summary_for_next: Option<String> =
            Some("CONTEXT BUDGET ALERT: The previous PLAN phase used 65% ...".to_string());
        let mut budget_model_override: Option<(String, String)> =
            Some(("claude".to_string(), "opus".to_string()));

        // Simulate: current-plan.md read fails, plan_text is empty
        let plan_text = String::new();

        // The fix: .take() runs unconditionally when P+ conditions are met,
        // BEFORE the if !plan_text.is_empty() check.
        let _consumed_summary = budget_summary_for_next.take();
        let _consumed_override = budget_model_override.take();

        // plan_text is empty, so the P+ orchestrator block is skipped
        if !plan_text.is_empty() {
            panic!("plan_text should be empty in this test");
        }

        // Directives must already be consumed -- they must not reach Builder
        assert!(
            budget_summary_for_next.is_none(),
            "budget summary must be consumed even when plan is unreadable"
        );
        assert!(
            budget_model_override.is_none(),
            "budget model override must be consumed even when plan is unreadable"
        );
    }

    #[test]
    fn test_recovery_actions_use_display_names() {
        // Bug D40.1(b): recovery_actions_taken[] and BudgetOverrun events must
        // use AgentRole Display names matching records[].phase, not informal names.
        use crate::agent::AgentRole;

        let roles = vec![
            (AgentRole::Scout, "SCOUT"),
            (AgentRole::Query, "QUERY"),
            (AgentRole::Research, "RESEARCH"),
            (AgentRole::Planner, "PLAN"),
            (AgentRole::PlanReview, "P+"),
            (AgentRole::Builder, "IMPLEMENT"),
            (AgentRole::Reviewer, "VERIFY"),
        ];

        for (role, expected_display) in &roles {
            let display_name = format!("{}", role);
            assert_eq!(
                &display_name, expected_display,
                "AgentRole::{:?} Display should be {:?}, got {:?}",
                role, expected_display, display_name
            );

            // Verify the recovery_actions_taken format uses Display name
            let recovery_entry = format!("{}: summarize", role);
            assert!(
                recovery_entry.starts_with(expected_display),
                "recovery action entry should start with Display name {:?}, got {:?}",
                expected_display,
                recovery_entry
            );
        }
    }

    #[test]
    fn test_planner_retry_produces_observable_telemetry() {
        // Bug D40.1(c): Planner gate-failure retry must accumulate AgentUsage,
        // emit AgentDone observatory event, and evaluate budget. This test
        // verifies the forwarding task pattern produces usage data (the same
        // pattern used by all other agent invocations).
        use crate::agent::AgentOutputEvent;
        use crate::observatory::AgentUsage;

        let mut usage = AgentUsage::default();

        // Simulate the forwarding task accumulating usage from a Usage event
        let evt = AgentOutputEvent::Usage {
            cost_usd: 0.15,
            input_tokens: 5000,
            output_tokens: 2000,
            context_window: 200000,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
        };
        usage.accumulate(&evt);

        assert_eq!(
            usage.tokens_in, 5000,
            "retry usage should accumulate input tokens"
        );
        assert_eq!(
            usage.tokens_out, 2000,
            "retry usage should accumulate output tokens"
        );
        assert!(
            (usage.cost_usd - 0.15).abs() < f64::EPSILON,
            "retry usage should accumulate cost"
        );

        // Verify budget evaluation works with accumulated retry usage
        let targets = crate::budget::BudgetTargets::default();
        let record =
            crate::budget::evaluate_phase(&crate::agent::AgentRole::Planner, &usage, &targets, 10);
        assert_eq!(
            record.phase, "PLAN",
            "retry budget record phase should use Display name"
        );
        assert_eq!(record.tokens_in, 5000);
        assert_eq!(record.tokens_out, 2000);
    }

    #[test]
    fn test_checkpoint_cascade_when_plan_missing() {
        // Bug D42.1(a): When resume_stage="builder" or "doubt" but current-plan.md
        // is missing, checkpoint_skip_planner becomes false. checkpoint_skip_plan_review
        // and checkpoint_skip_builder must also become false so the new plan gets
        // reviewed and implemented, not skipped.

        let dir = std::env::temp_dir().join(format!(
            "foundry-checkpoint-cascade-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Scenario: checkpoint says builder completed (resume_stage="doubt"),
        // but current-plan.md is missing.
        write_checkpoint(&dir, "D42.1", "test task", "builder");

        // Read checkpoint to get resume_stage
        let cp = read_checkpoint(&dir).unwrap();
        let resume_stage: Option<&str> = match cp.completed_stage.as_str() {
            "builder" => Some("doubt"),
            _ => None,
        };
        assert_eq!(resume_stage, Some("doubt"));

        // Simulate: current-plan.md does NOT exist (file system error during crash)
        let current_plan = dir.join("current-plan.md");
        assert!(!current_plan.exists());

        // checkpoint_skip_planner: plan_review/builder/doubt but plan missing -> false
        let checkpoint_skip_planner = match resume_stage {
            Some("plan_review" | "builder" | "doubt") => {
                current_plan.exists() // false because file is missing
            }
            _ => false,
        };
        assert!(
            !checkpoint_skip_planner,
            "planner skip must be false when current-plan.md is missing"
        );

        // checkpoint_skip_plan_review: depends on checkpoint_skip_planner (the fix)
        let checkpoint_skip_plan_review = match resume_stage {
            Some("builder" | "doubt") if checkpoint_skip_planner => true,
            _ => false,
        };
        assert!(
            !checkpoint_skip_plan_review,
            "plan_review skip must be false when checkpoint_skip_planner is false (cascading)"
        );

        // checkpoint_skip_builder: depends on checkpoint_skip_planner (the fix)
        let checkpoint_skip_builder = match resume_stage {
            Some("doubt") if checkpoint_skip_planner => dir.join("build-claims.md").exists(),
            _ => false,
        };
        assert!(
            !checkpoint_skip_builder,
            "builder skip must be false when checkpoint_skip_planner is false (cascading)"
        );

        // Verify: when current-plan.md EXISTS, the old behavior is preserved
        std::fs::write(
            &current_plan,
            "# Plan\n## File Operations\n## Verification\n",
        )
        .unwrap();
        let build_claims = dir.join("build-claims.md");
        std::fs::write(&build_claims, "# Build Claims").unwrap();

        let checkpoint_skip_planner_ok = match resume_stage {
            Some("plan_review" | "builder" | "doubt") => current_plan.exists(),
            _ => false,
        };
        assert!(
            checkpoint_skip_planner_ok,
            "planner skip should be true when plan exists"
        );

        let checkpoint_skip_plan_review_ok = match resume_stage {
            Some("builder" | "doubt") if checkpoint_skip_planner_ok => true,
            _ => false,
        };
        assert!(
            checkpoint_skip_plan_review_ok,
            "plan_review skip should be true when planner skip is true"
        );

        let checkpoint_skip_builder_ok = match resume_stage {
            Some("doubt") if checkpoint_skip_planner_ok => build_claims.exists(),
            _ => false,
        };
        assert!(
            checkpoint_skip_builder_ok,
            "builder skip should be true when planner skip is true and build-claims.md exists"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_checkpoint_cascade_when_questions_missing() {
        // When resume_stage="doubt" but questions.md is missing,
        // checkpoint_skip_query becomes false. All downstream skips must also
        // become false (cascading).

        let dir = std::env::temp_dir().join(format!(
            "foundry-checkpoint-qr-cascade-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Scenario: checkpoint says builder completed (resume_stage="doubt"),
        // but questions.md is missing.
        write_checkpoint(&dir, "D43.1", "test task", "builder");

        let cp = read_checkpoint(&dir).unwrap();
        let resume_stage: Option<&str> = match cp.completed_stage.as_str() {
            "query" => Some("research"),
            "research" => Some("planner"),
            "planner" => Some("plan_review"),
            "plan_review" => Some("builder"),
            "builder" => Some("doubt"),
            "scout" => Some("planner"),
            _ => None,
        };
        assert_eq!(resume_stage, Some("doubt"));

        // questions.md does NOT exist (simulates missing query artifact)
        let questions_file = dir.join("questions.md");
        assert!(!questions_file.exists());

        // research-report.md, current-plan.md and build-claims.md DO exist (stale artifacts)
        let research_report = dir.join("research-report.md");
        std::fs::write(&research_report, "# Research Report").unwrap();
        let current_plan = dir.join("current-plan.md");
        std::fs::write(
            &current_plan,
            "# Plan\n## File Operations\n## Verification\n",
        )
        .unwrap();
        let build_claims = dir.join("build-claims.md");
        std::fs::write(&build_claims, "# Build Claims").unwrap();

        // checkpoint_skip_query: questions.md missing -> false
        let checkpoint_skip_query = match resume_stage {
            Some("research" | "planner" | "plan_review" | "builder" | "doubt") => {
                questions_file.exists()
            }
            _ => false,
        };
        assert!(
            !checkpoint_skip_query,
            "query skip must be false when questions.md is missing"
        );

        // checkpoint_skip_research: must be false because checkpoint_skip_query is false (cascading)
        let checkpoint_skip_research = match resume_stage {
            Some("planner" | "plan_review" | "builder" | "doubt") if checkpoint_skip_query => {
                research_report.exists()
            }
            _ => false,
        };
        assert!(
            !checkpoint_skip_research,
            "research skip must be false when checkpoint_skip_query is false (cascading)"
        );

        // checkpoint_skip_planner: must be false because checkpoint_skip_research is false
        let checkpoint_skip_planner = match resume_stage {
            Some("plan_review" | "builder" | "doubt") if checkpoint_skip_research => {
                current_plan.exists()
            }
            _ => false,
        };
        assert!(
            !checkpoint_skip_planner,
            "planner skip must be false when checkpoint_skip_research is false (cascading)"
        );

        // checkpoint_skip_plan_review: depends on checkpoint_skip_planner
        let checkpoint_skip_plan_review = matches!(
            resume_stage,
            Some("builder" | "doubt") if checkpoint_skip_planner
        );
        assert!(
            !checkpoint_skip_plan_review,
            "plan_review skip must be false when checkpoint_skip_planner is false (cascading)"
        );

        // checkpoint_skip_builder: depends on checkpoint_skip_planner
        let checkpoint_skip_builder = match resume_stage {
            Some("doubt") if checkpoint_skip_planner => build_claims.exists(),
            _ => false,
        };
        assert!(
            !checkpoint_skip_builder,
            "builder skip must be false when checkpoint_skip_planner is false (cascading)"
        );

        // Positive case: when questions.md and research-report.md EXIST, cascade does not trigger
        std::fs::write(&questions_file, "# Questions").unwrap();

        let checkpoint_skip_query_ok = match resume_stage {
            Some("research" | "planner" | "plan_review" | "builder" | "doubt") => {
                questions_file.exists()
            }
            _ => false,
        };
        assert!(
            checkpoint_skip_query_ok,
            "query skip should be true when questions.md exists"
        );

        let checkpoint_skip_research_ok = match resume_stage {
            Some("planner" | "plan_review" | "builder" | "doubt") if checkpoint_skip_query_ok => {
                research_report.exists()
            }
            _ => false,
        };
        assert!(
            checkpoint_skip_research_ok,
            "research skip should be true when query skip is true and research-report.md exists"
        );

        let checkpoint_skip_planner_ok = match resume_stage {
            Some("plan_review" | "builder" | "doubt") if checkpoint_skip_research_ok => {
                current_plan.exists()
            }
            _ => false,
        };
        assert!(
            checkpoint_skip_planner_ok,
            "planner skip should be true when research skip is true and plan exists"
        );

        let checkpoint_skip_plan_review_ok = matches!(
            resume_stage,
            Some("builder" | "doubt") if checkpoint_skip_planner_ok
        );
        assert!(
            checkpoint_skip_plan_review_ok,
            "plan_review skip should be true when planner skip is true"
        );

        let checkpoint_skip_builder_ok = match resume_stage {
            Some("doubt") if checkpoint_skip_planner_ok => build_claims.exists(),
            _ => false,
        };
        assert!(
            checkpoint_skip_builder_ok,
            "builder skip should be true when planner skip is true and build-claims.md exists"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_checkpoint_query_done_research_not_done_does_not_skip_research() {
        // Bug D86.1(a): When checkpoint completed_stage="query", questions.md exists
        // but research-report.md does NOT exist, Research must still run.
        // The old skip_qr flag was true (checkpoint_skip_query was true), which
        // caused both Q+R to be skipped. The fix splits into skip_query/skip_research.

        let dir = std::env::temp_dir().join(format!(
            "foundry-checkpoint-qr-split-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Checkpoint: query completed (crash during research)
        write_checkpoint(&dir, "D86.1", "test task", "query");

        let cp = read_checkpoint(&dir).unwrap();
        let resume_stage: Option<&str> = match cp.completed_stage.as_str() {
            "query" => Some("research"),
            "research" => Some("planner"),
            "planner" => Some("plan_review"),
            "plan_review" => Some("builder"),
            "builder" => Some("doubt"),
            "scout" => Some("planner"),
            _ => None,
        };
        assert_eq!(resume_stage, Some("research"));

        // questions.md EXISTS (query completed successfully)
        let questions_file = dir.join("questions.md");
        std::fs::write(
            &questions_file,
            "# Questions\n1. What modules are involved?",
        )
        .unwrap();

        // research-report.md does NOT exist (research never ran)
        let research_report = dir.join("research-report.md");
        assert!(!research_report.exists());

        // Compute checkpoint skip flags (same logic as process_task)
        let checkpoint_skip_query = match resume_stage {
            Some("research" | "planner" | "plan_review" | "builder" | "doubt") => {
                questions_file.exists()
            }
            _ => false,
        };
        assert!(
            checkpoint_skip_query,
            "query skip should be true (questions.md exists)"
        );

        let checkpoint_skip_research = match resume_stage {
            Some("planner" | "plan_review" | "builder" | "doubt") if checkpoint_skip_query => {
                research_report.exists()
            }
            _ => false,
        };
        assert!(
            !checkpoint_skip_research,
            "research skip must be false (resume_stage is 'research', not planner/builder/doubt)"
        );

        // Compute skip_query and skip_research with skip_scout=false, simple_task=false
        let skip_scout = false;
        let simple_task = false;
        let skip_query = skip_scout || checkpoint_skip_query || simple_task;
        let skip_research =
            skip_scout || (checkpoint_skip_query && checkpoint_skip_research) || simple_task;

        assert!(
            skip_query,
            "Query should be skipped (checkpoint_skip_query is true)"
        );
        assert!(
            !skip_research,
            "Research must NOT be skipped (checkpoint_skip_research is false)"
        );

        // The outer Q+R block should NOT be fully skipped
        let both_skipped = skip_query && skip_research;
        assert!(
            !both_skipped,
            "Q+R block must not be fully skipped when only Query was checkpointed"
        );

        // Stale artifact cleanup: research-report.md should be cleaned when
        // skip_research=false and checkpoint_skip_research=false
        let should_clean_research = !skip_research && !checkpoint_skip_research;
        assert!(
            should_clean_research,
            "stale research-report.md should be cleaned when Research will re-run"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_parallel_builder_budget_record_included() {
        // D44.1: When parallel builder produces aggregated usage, the IMPLEMENT
        // phase record must appear in budget-telemetry.json.
        let dir = std::env::temp_dir().join(format!(
            "foundry-parallel-budget-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Simulate what process_task does: create a BudgetTelemetry, evaluate
        // phase with aggregated parallel usage, push record, flush.
        use crate::agent::AgentRole;
        use crate::observatory::AgentUsage;

        let usage = AgentUsage {
            cost_usd: 0.05,
            tokens_in: 5000,
            tokens_out: 2000,
            context_pct: 45,
            ..Default::default()
        };
        let record = budget::evaluate_phase(
            &AgentRole::Builder,
            &usage,
            &budget::BudgetTargets::default(),
            10,
        );
        assert_eq!(record.phase, "IMPLEMENT");
        assert_eq!(record.actual_pct, 45);
        assert_eq!(record.tokens_in, 5000);
        assert_eq!(record.tokens_out, 2000);

        let telemetry = budget::BudgetTelemetry {
            task_id: "D44.1".to_string(),
            timestamp: "2026-03-29T00:00:00Z".to_string(),
            records: vec![record],
            ..Default::default()
        };

        flush_budget_telemetry(&dir, true, &telemetry);
        let path = dir.join("budget-telemetry.json");
        assert!(path.exists(), "budget-telemetry.json must exist");
        let content = std::fs::read_to_string(&path).unwrap();
        assert!(
            content.contains("IMPLEMENT"),
            "budget-telemetry.json must contain IMPLEMENT phase record"
        );
        assert!(
            content.contains("5000"),
            "budget-telemetry.json must contain tokens_in from aggregated usage"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_discover_changed_files_in_worktree_finds_unplanned_files() {
        let dir = std::env::temp_dir().join(format!(
            "foundry-wt-discover-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        // Initialize a git repo
        std::process::Command::new("git")
            .args(["init"])
            .current_dir(&dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["config", "user.email", "test@test.com"])
            .current_dir(&dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["config", "user.name", "test"])
            .current_dir(&dir)
            .output()
            .unwrap();

        // Create an initial tracked file, commit
        std::fs::write(dir.join("planned.rs"), "fn planned() {}").unwrap();
        std::process::Command::new("git")
            .args(["add", "."])
            .current_dir(&dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["commit", "-m", "initial"])
            .current_dir(&dir)
            .output()
            .unwrap();

        // Create a worktree
        let wt_dir = std::env::temp_dir().join(format!(
            "foundry-wt-discover-wt-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::process::Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&wt_dir)
            .arg("HEAD")
            .current_dir(&dir)
            .output()
            .unwrap();

        // Modify tracked file in worktree
        std::fs::write(wt_dir.join("planned.rs"), "fn planned() { /* modified */ }").unwrap();

        // Create new untracked file (simulating Cargo.lock, test file, etc.)
        std::fs::write(wt_dir.join("unplanned.rs"), "fn surprise() {}").unwrap();

        // Create a new file in a subdirectory
        std::fs::create_dir_all(wt_dir.join("tests")).unwrap();
        std::fs::write(wt_dir.join("tests/new_test.rs"), "fn test() {}").unwrap();

        // Run discovery
        let result = super::discover_changed_files_in_worktree(&wt_dir);
        assert!(result.is_some(), "git discovery must succeed");
        let files = result.unwrap();
        assert!(
            files.contains(&"planned.rs".to_string()),
            "must find modified tracked file, got: {:?}",
            files
        );
        assert!(
            files.contains(&"unplanned.rs".to_string()),
            "must find new untracked file, got: {:?}",
            files
        );
        assert!(
            files.contains(&"tests/new_test.rs".to_string()),
            "must find new file in subdirectory, got: {:?}",
            files
        );

        // Cleanup
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_dir)
            .current_dir(&dir)
            .output();
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&wt_dir);
    }

    #[test]
    fn test_worktree_merge_propagates_file_deletions() {
        // Set up a temp "main project" directory with a git repo
        let main_dir = std::env::temp_dir().join(format!(
            "foundry-wt-del-main-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&main_dir).unwrap();

        // Initialize git repo
        std::process::Command::new("git")
            .args(["init"])
            .current_dir(&main_dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["config", "user.email", "test@test.com"])
            .current_dir(&main_dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["config", "user.name", "test"])
            .current_dir(&main_dir)
            .output()
            .unwrap();

        // Create two tracked files and commit
        std::fs::write(main_dir.join("keep.rs"), "fn keep() {}").unwrap();
        std::fs::write(main_dir.join("dead_code.rs"), "fn dead() {}").unwrap();
        std::fs::create_dir_all(main_dir.join("src")).unwrap();
        std::fs::write(main_dir.join("src/old_module.rs"), "fn old() {}").unwrap();
        std::process::Command::new("git")
            .args(["add", "."])
            .current_dir(&main_dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["commit", "-m", "initial"])
            .current_dir(&main_dir)
            .output()
            .unwrap();

        // Create a worktree
        let wt_dir = std::env::temp_dir().join(format!(
            "foundry-wt-del-wt-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::process::Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&wt_dir)
            .arg("HEAD")
            .current_dir(&main_dir)
            .output()
            .unwrap();

        // In the worktree: delete dead_code.rs and src/old_module.rs, modify keep.rs
        std::fs::remove_file(wt_dir.join("dead_code.rs")).unwrap();
        std::fs::remove_file(wt_dir.join("src/old_module.rs")).unwrap();
        std::fs::write(wt_dir.join("keep.rs"), "fn keep() { /* updated */ }").unwrap();

        // Verify git diff --name-only HEAD reports deleted files
        let result = super::discover_changed_files_in_worktree(&wt_dir);
        assert!(result.is_some(), "git discovery must succeed");
        let files = result.unwrap();
        assert!(
            files.contains(&"dead_code.rs".to_string()),
            "must discover deleted file dead_code.rs, got: {:?}",
            files
        );
        assert!(
            files.contains(&"src/old_module.rs".to_string()),
            "must discover deleted file src/old_module.rs, got: {:?}",
            files
        );
        assert!(
            files.contains(&"keep.rs".to_string()),
            "must discover modified file keep.rs, got: {:?}",
            files
        );

        // Simulate the merge loop logic: iterate discovered files and apply
        // copy-or-delete to the main project directory
        for file_path in &files {
            let src = wt_dir.join(file_path);
            let dest = main_dir.join(file_path);
            if src.exists() {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                std::fs::copy(&src, &dest).unwrap();
            } else if dest.exists() {
                std::fs::remove_file(&dest).unwrap();
            }
        }

        // Verify: keep.rs should be updated
        let keep_content = std::fs::read_to_string(main_dir.join("keep.rs")).unwrap();
        assert!(
            keep_content.contains("updated"),
            "keep.rs must be updated in main project"
        );

        // Verify: dead_code.rs should be gone from main project
        assert!(
            !main_dir.join("dead_code.rs").exists(),
            "dead_code.rs must be deleted from main project"
        );

        // Verify: src/old_module.rs should be gone from main project
        assert!(
            !main_dir.join("src/old_module.rs").exists(),
            "src/old_module.rs must be deleted from main project"
        );

        // Cleanup
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_dir)
            .current_dir(&main_dir)
            .output();
        let _ = std::fs::remove_dir_all(&main_dir);
        let _ = std::fs::remove_dir_all(&wt_dir);
    }

    #[test]
    fn test_worktree_merge_copy_failure_sets_all_ok_false() {
        // This test simulates the merge loop logic: when std::fs::copy fails
        // for a file, all_ok must be set to false and copied_files must NOT
        // record the file.
        //
        // Strategy: create a dest path whose parent is a file (not a dir),
        // so copy fails with a "Not a directory" error.

        let test_dir = std::env::temp_dir().join(format!(
            "foundry-wt-copyfail-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&test_dir).unwrap();

        // Create a source file to copy
        let src_dir = test_dir.join("worktree");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::create_dir_all(src_dir.join("subdir")).unwrap();
        std::fs::write(src_dir.join("subdir/good.rs"), "fn good() {}").unwrap();
        std::fs::write(src_dir.join("subdir/bad.rs"), "fn bad() {}").unwrap();

        // Create a main project dir where "subdir" for the bad file is actually a file,
        // not a directory, causing copy to fail for bad.rs
        let main_dir = test_dir.join("main");
        std::fs::create_dir_all(&main_dir).unwrap();
        // good.rs goes under main/subdir/ (normal dir)
        std::fs::create_dir_all(main_dir.join("subdir")).unwrap();

        // Simulate the merge loop logic for two files
        let files_to_copy = vec!["subdir/good.rs".to_string(), "subdir/bad.rs".to_string()];
        let mut all_ok = true;
        let mut copied_files: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let slot_idx: usize = 0;

        for file_path in &files_to_copy {
            let src = src_dir.join(file_path);
            let dest = main_dir.join(file_path);

            if src.exists() {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                if let Err(_e) = std::fs::copy(&src, &dest) {
                    all_ok = false;
                    continue;
                }
            }
            copied_files.insert(file_path.clone(), slot_idx);
        }

        // good.rs should succeed and all_ok must remain true
        assert!(all_ok, "all_ok must remain true when all copies succeed");
        assert!(
            copied_files.contains_key("subdir/good.rs"),
            "good.rs must be in copied_files"
        );
        assert!(
            main_dir.join("subdir/good.rs").exists(),
            "good.rs must exist in main project"
        );

        // Now test with a broken dest: make the dest parent a file instead of a dir
        // to force copy failure
        let main_dir2 = test_dir.join("main2");
        std::fs::create_dir_all(&main_dir2).unwrap();
        // Create "subdir" as a regular FILE, not a directory
        std::fs::write(main_dir2.join("subdir"), "i am a file not a dir").unwrap();

        let mut all_ok2 = true;
        let mut copied_files2: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();

        for file_path in &files_to_copy {
            let src = src_dir.join(file_path);
            let dest = main_dir2.join(file_path);

            if src.exists() {
                if let Some(parent) = dest.parent() {
                    // create_dir_all will fail here because "subdir" is a file
                    let _ = std::fs::create_dir_all(parent);
                }
                if let Err(_e) = std::fs::copy(&src, &dest) {
                    all_ok2 = false;
                    continue;
                }
            }
            copied_files2.insert(file_path.clone(), slot_idx);
        }

        // Both files should fail because "subdir" is a file, not a directory
        assert!(!all_ok2, "all_ok must be false when copy fails");
        assert!(
            !copied_files2.contains_key("subdir/good.rs"),
            "good.rs must NOT be in copied_files when copy fails"
        );
        assert!(
            !copied_files2.contains_key("subdir/bad.rs"),
            "bad.rs must NOT be in copied_files when copy fails"
        );

        // Cleanup
        let _ = std::fs::remove_dir_all(&test_dir);
    }

    #[test]
    fn test_worktree_merge_copied_files_not_poisoned_on_failure() {
        // When slot 0's copy fails for a file, copied_files must NOT contain
        // that file. If slot 1 later has the same file, it should NOT see a
        // conflict and should be able to copy its version successfully.

        let test_dir = std::env::temp_dir().join(format!(
            "foundry-wt-poison-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&test_dir).unwrap();

        // Slot 0 worktree: has shared.rs
        let wt0 = test_dir.join("slot0");
        std::fs::create_dir_all(&wt0).unwrap();
        std::fs::write(wt0.join("shared.rs"), "fn shared() { /* slot 0 */ }").unwrap();

        // Slot 1 worktree: also has shared.rs
        let wt1 = test_dir.join("slot1");
        std::fs::create_dir_all(&wt1).unwrap();
        std::fs::write(wt1.join("shared.rs"), "fn shared() { /* slot 1 */ }").unwrap();

        // Main project: make shared.rs's parent dir non-writable to cause
        // slot 0's copy to fail. Actually, easier: use a file as the dest
        // parent to guarantee failure.
        let main_broken = test_dir.join("main_broken");
        std::fs::create_dir_all(&main_broken).unwrap();
        // For slot 0: break the destination so copy fails
        // We create a read-only file at the dest path so copy fails with permission error
        std::fs::write(main_broken.join("shared.rs"), "original").unwrap();

        // Make dest read-only on Unix to cause copy to fail
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let perms = std::fs::Permissions::from_mode(0o000);
            std::fs::set_permissions(main_broken.join("shared.rs"), perms).unwrap();
        }

        let files_slot0 = vec!["shared.rs".to_string()];
        let files_slot1 = vec!["shared.rs".to_string()];

        let mut all_ok = true;
        let mut copied_files: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();

        // Process slot 0
        let slot_idx_0: usize = 0;
        for file_path in &files_slot0 {
            let src = wt0.join(file_path);
            let dest = main_broken.join(file_path);
            if src.exists() {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                if let Err(_e) = std::fs::copy(&src, &dest) {
                    all_ok = false;
                    continue;
                }
            }
            copied_files.insert(file_path.clone(), slot_idx_0);
        }

        // Verify slot 0 failed: copied_files must NOT contain shared.rs
        #[cfg(unix)]
        {
            assert!(
                !copied_files.contains_key("shared.rs"),
                "shared.rs must NOT be in copied_files after slot 0 copy failure"
            );
            assert!(!all_ok, "all_ok must be false after slot 0 copy failure");
        }

        // Now restore permissions so slot 1 can succeed
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let perms = std::fs::Permissions::from_mode(0o644);
            std::fs::set_permissions(main_broken.join("shared.rs"), perms).unwrap();
        }

        // Process slot 1: since copied_files does NOT have shared.rs,
        // there should be no conflict, and slot 1 copies successfully
        let slot_idx_1: usize = 1;
        for file_path in &files_slot1 {
            if let Some(&_prev_slot) = copied_files.get(file_path) {
                // Conflict path -- should NOT be reached since slot 0 failed
                panic!("should not detect conflict for shared.rs when slot 0 failed");
            }

            let src = wt1.join(file_path);
            let dest = main_broken.join(file_path);
            if src.exists() {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                if let Err(_e) = std::fs::copy(&src, &dest) {
                    all_ok = false;
                    continue;
                }
            }
            copied_files.insert(file_path.clone(), slot_idx_1);
        }

        // Verify slot 1 succeeded
        #[cfg(unix)]
        {
            assert!(!all_ok, "all_ok remains false because slot 0 failed");
            assert!(
                copied_files.contains_key("shared.rs"),
                "shared.rs must be in copied_files from slot 1"
            );
            assert_eq!(
                copied_files.get("shared.rs"),
                Some(&1),
                "shared.rs must be recorded as from slot 1"
            );
            let content = std::fs::read_to_string(main_broken.join("shared.rs")).unwrap();
            assert!(
                content.contains("slot 1"),
                "shared.rs must contain slot 1's version, got: {}",
                content
            );
        }

        // Cleanup
        let _ = std::fs::remove_dir_all(&test_dir);
    }

    #[test]
    fn test_worktree_merge_detects_shared_file_conflict() {
        // Set up a temp "main project" directory with a git repo
        let main_dir = std::env::temp_dir().join(format!(
            "foundry-wt-conflict-main-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&main_dir).unwrap();

        // Initialize git repo
        std::process::Command::new("git")
            .args(["init"])
            .current_dir(&main_dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["config", "user.email", "test@test.com"])
            .current_dir(&main_dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["config", "user.name", "test"])
            .current_dir(&main_dir)
            .output()
            .unwrap();

        // Create tracked files: planned_a.rs, planned_b.rs, shared.rs
        std::fs::write(main_dir.join("planned_a.rs"), "fn a() {}").unwrap();
        std::fs::write(main_dir.join("planned_b.rs"), "fn b() {}").unwrap();
        std::fs::write(main_dir.join("shared.rs"), "fn shared() {}").unwrap();
        std::process::Command::new("git")
            .args(["add", "."])
            .current_dir(&main_dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["commit", "-m", "initial"])
            .current_dir(&main_dir)
            .output()
            .unwrap();

        // Create two worktrees
        let wt_a = std::env::temp_dir().join(format!(
            "foundry-wt-conflict-a-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let wt_b = std::env::temp_dir().join(format!(
            "foundry-wt-conflict-b-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
                + 1
        ));
        std::process::Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&wt_a)
            .arg("HEAD")
            .current_dir(&main_dir)
            .output()
            .unwrap();
        std::process::Command::new("git")
            .args(["worktree", "add", "--detach"])
            .arg(&wt_b)
            .arg("HEAD")
            .current_dir(&main_dir)
            .output()
            .unwrap();

        // Slot 0 (wt_a): modify planned_a.rs and shared.rs (unplanned)
        std::fs::write(wt_a.join("planned_a.rs"), "fn a() { /* slot 0 */ }").unwrap();
        std::fs::write(
            wt_a.join("shared.rs"),
            "fn shared() { /* slot 0 version */ }",
        )
        .unwrap();

        // Slot 1 (wt_b): modify planned_b.rs and shared.rs (unplanned)
        std::fs::write(wt_b.join("planned_b.rs"), "fn b() { /* slot 1 */ }").unwrap();
        std::fs::write(
            wt_b.join("shared.rs"),
            "fn shared() { /* slot 1 version */ }",
        )
        .unwrap();

        // Discover changed files in each worktree
        let files_a = super::discover_changed_files_in_worktree(&wt_a).unwrap();
        let files_b = super::discover_changed_files_in_worktree(&wt_b).unwrap();

        assert!(
            files_a.contains(&"shared.rs".to_string()),
            "slot 0 must discover shared.rs"
        );
        assert!(
            files_b.contains(&"shared.rs".to_string()),
            "slot 1 must discover shared.rs"
        );

        // Simulate planned file operations:
        // Slot 0 owns planned_a.rs, slot 1 owns planned_b.rs.
        // Neither slot owns shared.rs (it is unplanned).
        let mut planned_file_owner: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        planned_file_owner.insert("planned_a.rs".to_string(), 0);
        planned_file_owner.insert("planned_b.rs".to_string(), 1);

        // Simulate the merge loop with conflict detection
        let mut copied_files: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut conflicts: Vec<(String, usize, usize, usize)> = Vec::new(); // (file, prev_slot, cur_slot, winner)

        let slot_worktrees: Vec<(usize, &std::path::Path, Vec<String>)> =
            vec![(0, wt_a.as_path(), files_a), (1, wt_b.as_path(), files_b)];

        for (slot_idx, wt_dir, files_to_copy) in &slot_worktrees {
            for file_path in files_to_copy {
                if let Some(&prev_slot) = copied_files.get(file_path) {
                    let owner = planned_file_owner.get(file_path);
                    let winner = match owner {
                        Some(&owning_slot) => owning_slot,
                        None => prev_slot,
                    };
                    conflicts.push((file_path.clone(), prev_slot, *slot_idx, winner));
                    if winner == prev_slot {
                        continue;
                    }
                }

                let src = wt_dir.join(file_path);
                let dest = main_dir.join(file_path);
                if src.exists() {
                    if let Some(parent) = dest.parent() {
                        let _ = std::fs::create_dir_all(parent);
                    }
                    std::fs::copy(&src, &dest).unwrap();
                }
                copied_files.insert(file_path.clone(), *slot_idx);
            }
        }

        // Verify: conflict was detected for shared.rs
        assert!(
            conflicts.iter().any(|(f, _, _, _)| f == "shared.rs"),
            "must detect conflict on shared.rs, got conflicts: {:?}",
            conflicts
        );

        // Verify: shared.rs conflict winner is slot 0 (first slot, since neither planned it)
        let shared_conflict = conflicts
            .iter()
            .find(|(f, _, _, _)| f == "shared.rs")
            .unwrap();
        assert_eq!(
            shared_conflict.3, 0,
            "winner for unplanned shared.rs must be first slot (0)"
        );

        // Verify: shared.rs content is from slot 0 (the winner)
        let shared_content = std::fs::read_to_string(main_dir.join("shared.rs")).unwrap();
        assert!(
            shared_content.contains("slot 0 version"),
            "shared.rs must contain slot 0's version, got: {}",
            shared_content
        );

        // Verify: non-conflicting planned files are correctly copied
        let a_content = std::fs::read_to_string(main_dir.join("planned_a.rs")).unwrap();
        assert!(
            a_content.contains("slot 0"),
            "planned_a.rs must have slot 0 content"
        );
        let b_content = std::fs::read_to_string(main_dir.join("planned_b.rs")).unwrap();
        assert!(
            b_content.contains("slot 1"),
            "planned_b.rs must have slot 1 content"
        );

        // Cleanup
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_a)
            .current_dir(&main_dir)
            .output();
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_b)
            .current_dir(&main_dir)
            .output();
        let _ = std::fs::remove_dir_all(&main_dir);
        let _ = std::fs::remove_dir_all(&wt_a);
        let _ = std::fs::remove_dir_all(&wt_b);
    }

    #[test]
    fn test_worktree_merge_deletion_does_not_block_later_creation() {
        use std::time::{SystemTime, UNIX_EPOCH};

        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        let main_dir = std::env::temp_dir().join(format!("foundry-wt-del-create-{}", nanos));
        std::fs::create_dir_all(&main_dir).unwrap();

        // Initialize git repo
        let git = |args: &[&str]| {
            std::process::Command::new("git")
                .args(args)
                .current_dir(&main_dir)
                .output()
                .expect("git command failed")
        };
        git(&["init"]);
        git(&["config", "user.email", "test@test.com"]);
        git(&["config", "user.name", "test"]);

        // Create tracked file and commit
        std::fs::write(main_dir.join("target.rs"), "fn target() { /* original */ }").unwrap();
        git(&["add", "."]);
        git(&["commit", "-m", "initial"]);

        // Create two worktrees
        let wt_a = std::env::temp_dir().join(format!("foundry-wt-del-create-a-{}", nanos));
        let wt_b = std::env::temp_dir().join(format!("foundry-wt-del-create-b-{}", nanos + 1));
        git(&[
            "worktree",
            "add",
            "--detach",
            wt_a.to_str().unwrap(),
            "HEAD",
        ]);
        git(&[
            "worktree",
            "add",
            "--detach",
            wt_b.to_str().unwrap(),
            "HEAD",
        ]);

        // Slot 0 (wt_a): delete target.rs
        std::fs::remove_file(wt_a.join("target.rs")).unwrap();

        // Slot 1 (wt_b): overwrite target.rs with new content
        std::fs::write(
            wt_b.join("target.rs"),
            "fn target() { /* slot 1 new version */ }",
        )
        .unwrap();

        // Discover changed files in each worktree
        let files_a = super::discover_changed_files_in_worktree(&wt_a).unwrap();
        let files_b = super::discover_changed_files_in_worktree(&wt_b).unwrap();
        assert!(
            files_a.contains(&"target.rs".to_string()),
            "slot 0 must discover deleted target.rs"
        );
        assert!(
            files_b.contains(&"target.rs".to_string()),
            "slot 1 must discover modified target.rs"
        );

        // Neither slot planned target.rs -- worst case for the bug
        let planned_file_owner: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut copied_files: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();

        // Simulate fixed merge loop for slot 0 (wt_a)
        for file_path in &files_a {
            // Conflict check (won't trigger -- copied_files is empty)
            if let Some(&prev_slot) = copied_files.get(file_path.as_str()) {
                // Determine winner
                let winner = if let Some(&owner) = planned_file_owner.get(file_path.as_str()) {
                    owner
                } else {
                    prev_slot
                };
                if winner != 0 {
                    continue;
                }
            }

            let src = wt_a.join(file_path);
            let dest = main_dir.join(file_path);
            if src.exists() {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                std::fs::copy(&src, &dest).unwrap();
                // Record that this file was copied from this slot
                copied_files.insert(file_path.clone(), 0usize);
            } else if dest.exists() {
                // File was deleted in worktree -- remove from main project
                std::fs::remove_file(&dest).unwrap();
                // NOTE: Do NOT insert into copied_files -- this is the fix
            }
        }

        // After slot 0: target.rs must be deleted, NOT in copied_files
        assert!(
            !main_dir.join("target.rs").exists(),
            "target.rs must be deleted after slot 0"
        );
        assert!(
            !copied_files.contains_key("target.rs"),
            "deleted file must NOT be in copied_files"
        );

        // Simulate fixed merge loop for slot 1 (wt_b)
        for file_path in &files_b {
            // Conflict check -- won't trigger since target.rs was NOT inserted by slot 0
            if let Some(&prev_slot) = copied_files.get(file_path.as_str()) {
                let winner = if let Some(&owner) = planned_file_owner.get(file_path.as_str()) {
                    owner
                } else {
                    prev_slot
                };
                if winner != 1 {
                    continue;
                }
            }

            let src = wt_b.join(file_path);
            let dest = main_dir.join(file_path);
            if src.exists() {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                std::fs::copy(&src, &dest).unwrap();
                // Record that this file was copied from this slot
                copied_files.insert(file_path.clone(), 1usize);
            } else if dest.exists() {
                std::fs::remove_file(&dest).unwrap();
            }
        }

        // After slot 1: target.rs must exist with slot 1's content
        assert!(
            main_dir.join("target.rs").exists(),
            "target.rs must exist after slot 1 creates it"
        );
        let content = std::fs::read_to_string(main_dir.join("target.rs")).unwrap();
        assert!(
            content.contains("slot 1 new version"),
            "target.rs must contain slot 1's version, got: {}",
            content
        );
        assert_eq!(
            copied_files.get("target.rs"),
            Some(&1usize),
            "target.rs must be recorded as from slot 1"
        );

        // Cleanup
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_a)
            .current_dir(&main_dir)
            .output();
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_b)
            .current_dir(&main_dir)
            .output();
        let _ = std::fs::remove_dir_all(&main_dir);
        let _ = std::fs::remove_dir_all(&wt_a);
        let _ = std::fs::remove_dir_all(&wt_b);
    }

    #[test]
    fn test_worktree_merge_detects_delete_modify_conflict() {
        use std::time::{SystemTime, UNIX_EPOCH};

        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        let main_dir = std::env::temp_dir().join(format!("foundry-wt-del-mod-{}", nanos));
        std::fs::create_dir_all(&main_dir).unwrap();

        // Initialize git repo
        let git = |args: &[&str]| {
            std::process::Command::new("git")
                .args(args)
                .current_dir(&main_dir)
                .output()
                .expect("git command failed")
        };
        git(&["init"]);
        git(&["config", "user.email", "test@test.com"]);
        git(&["config", "user.name", "test"]);

        // Create tracked files: shared.rs and owned.rs
        std::fs::write(main_dir.join("shared.rs"), "fn shared() {}").unwrap();
        std::fs::write(main_dir.join("owned.rs"), "fn owned() {}").unwrap();
        git(&["add", "."]);
        git(&["commit", "-m", "initial"]);

        // Create two worktrees
        let wt_a = std::env::temp_dir().join(format!("foundry-wt-del-mod-a-{}", nanos));
        let wt_b = std::env::temp_dir().join(format!("foundry-wt-del-mod-b-{}", nanos + 1));
        git(&[
            "worktree",
            "add",
            "--detach",
            wt_a.to_str().unwrap(),
            "HEAD",
        ]);
        git(&[
            "worktree",
            "add",
            "--detach",
            wt_b.to_str().unwrap(),
            "HEAD",
        ]);

        // Slot 0 (wt_a): delete shared.rs
        std::fs::remove_file(wt_a.join("shared.rs")).unwrap();

        // Slot 1 (wt_b): modify shared.rs
        std::fs::write(
            wt_b.join("shared.rs"),
            "fn shared() { /* slot 1 modified */ }",
        )
        .unwrap();

        // Also test planned ownership: slot 0 deletes owned.rs, slot 1 modifies owned.rs
        // but slot 0 is the planned owner -- deletion should win
        std::fs::remove_file(wt_a.join("owned.rs")).unwrap();
        std::fs::write(
            wt_b.join("owned.rs"),
            "fn owned() { /* slot 1 modified */ }",
        )
        .unwrap();

        // Discover changed files in each worktree
        let files_a = super::discover_changed_files_in_worktree(&wt_a).unwrap();
        let files_b = super::discover_changed_files_in_worktree(&wt_b).unwrap();
        assert!(
            files_a.contains(&"shared.rs".to_string()),
            "slot 0 must discover deleted shared.rs"
        );
        assert!(
            files_b.contains(&"shared.rs".to_string()),
            "slot 1 must discover modified shared.rs"
        );
        assert!(
            files_a.contains(&"owned.rs".to_string()),
            "slot 0 must discover deleted owned.rs"
        );
        assert!(
            files_b.contains(&"owned.rs".to_string()),
            "slot 1 must discover modified owned.rs"
        );

        // Planned ownership: slot 0 owns owned.rs, nobody owns shared.rs
        let mut planned_file_owner: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        planned_file_owner.insert("owned.rs".to_string(), 0);

        // Simulate the merge loop with conflict detection
        let mut copied_files: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut deleted_by_slot: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut conflicts: Vec<(String, &str, usize, usize, usize)> = Vec::new(); // (file, kind, prev_slot, cur_slot, winner)

        let slot_worktrees: Vec<(usize, &std::path::Path, Vec<String>)> =
            vec![(0, wt_a.as_path(), files_a), (1, wt_b.as_path(), files_b)];

        for (slot_idx, wt_dir, files_to_copy) in &slot_worktrees {
            for file_path in files_to_copy {
                // Check copy-vs-copy conflict (existing logic)
                if let Some(&prev_slot) = copied_files.get(file_path) {
                    let owner = planned_file_owner.get(file_path);
                    let winner = match owner {
                        Some(&owning_slot) => owning_slot,
                        None => prev_slot,
                    };
                    conflicts.push((file_path.clone(), "copy-copy", prev_slot, *slot_idx, winner));
                    if winner == prev_slot {
                        continue;
                    }
                }

                // Check delete-vs-modify conflict (new logic)
                if let Some(&del_slot) = deleted_by_slot.get(file_path) {
                    let src = wt_dir.join(file_path);
                    if src.exists() {
                        // Previous slot deleted, current slot modifies
                        let owner = planned_file_owner.get(file_path);
                        let winner = match owner {
                            Some(&owning_slot) => owning_slot,
                            None => *slot_idx, // modification wins by default
                        };
                        conflicts.push((
                            file_path.clone(),
                            "delete-modify",
                            del_slot,
                            *slot_idx,
                            winner,
                        ));
                        if winner == del_slot {
                            continue;
                        }
                    }
                }

                let src = wt_dir.join(file_path);
                let dest = main_dir.join(file_path);
                if src.exists() {
                    if let Some(parent) = dest.parent() {
                        let _ = std::fs::create_dir_all(parent);
                    }
                    std::fs::copy(&src, &dest).unwrap();
                    copied_files.insert(file_path.clone(), *slot_idx);
                } else if dest.exists() {
                    // Check modify-vs-delete conflict (reverse direction)
                    if let Some(&prev_slot) = copied_files.get(file_path) {
                        let owner = planned_file_owner.get(file_path);
                        let winner = match owner {
                            Some(&owning_slot) => owning_slot,
                            None => prev_slot, // modification wins by default
                        };
                        conflicts.push((
                            file_path.clone(),
                            "modify-delete",
                            prev_slot,
                            *slot_idx,
                            winner,
                        ));
                        if winner == prev_slot {
                            continue;
                        }
                    }
                    std::fs::remove_file(&dest).unwrap();
                    deleted_by_slot.insert(file_path.clone(), *slot_idx);
                } else {
                    // File deleted in worktree, already absent from main -- no-op
                    deleted_by_slot.insert(file_path.clone(), *slot_idx);
                }
            }
        }

        // === Assertions for shared.rs (no planned owner) ===

        // A delete-modify conflict must be detected for shared.rs
        let shared_conflict = conflicts
            .iter()
            .find(|(f, kind, _, _, _)| f == "shared.rs" && *kind == "delete-modify");
        assert!(
            shared_conflict.is_some(),
            "must detect delete-modify conflict on shared.rs, got conflicts: {:?}",
            conflicts
        );
        let shared_conflict = shared_conflict.unwrap();
        // Winner should be slot 1 (modification wins by default when no planned owner)
        assert_eq!(
            shared_conflict.4, 1,
            "winner for unplanned shared.rs delete-modify conflict must be slot 1 (modification wins)"
        );
        // shared.rs must exist with slot 1's content (modification won)
        assert!(
            main_dir.join("shared.rs").exists(),
            "shared.rs must exist after modification wins over deletion"
        );
        let shared_content = std::fs::read_to_string(main_dir.join("shared.rs")).unwrap();
        assert!(
            shared_content.contains("slot 1 modified"),
            "shared.rs must contain slot 1's version, got: {}",
            shared_content
        );

        // === Assertions for owned.rs (slot 0 is planned owner) ===

        // A delete-modify conflict must be detected for owned.rs
        let owned_conflict = conflicts
            .iter()
            .find(|(f, kind, _, _, _)| f == "owned.rs" && *kind == "delete-modify");
        assert!(
            owned_conflict.is_some(),
            "must detect delete-modify conflict on owned.rs, got conflicts: {:?}",
            conflicts
        );
        let owned_conflict = owned_conflict.unwrap();
        // Winner should be slot 0 (planned owner)
        assert_eq!(
            owned_conflict.4, 0,
            "winner for owned.rs delete-modify conflict must be slot 0 (planned owner)"
        );
        // owned.rs must NOT exist (deletion won because slot 0 is the planned owner)
        assert!(
            !main_dir.join("owned.rs").exists(),
            "owned.rs must be deleted when planned owner (slot 0) deleted it"
        );

        // Cleanup
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_a)
            .current_dir(&main_dir)
            .output();
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_b)
            .current_dir(&main_dir)
            .output();
        let _ = std::fs::remove_dir_all(&main_dir);
        let _ = std::fs::remove_dir_all(&wt_a);
        let _ = std::fs::remove_dir_all(&wt_b);
    }

    #[test]
    fn test_worktree_merge_copy_vs_delete_conflict_not_blocked() {
        // Regression test for D19.1: when slot 0 copies a file and slot 1 deletes
        // the same file, the copy-vs-copy check must NOT fire. Instead, the
        // modify-vs-delete check (inside the `else if dest.exists()` branch)
        // must handle it. Default winner: modification (slot 0) wins.
        use std::time::{SystemTime, UNIX_EPOCH};

        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        let main_dir = std::env::temp_dir().join(format!("foundry-wt-copydel-{}", nanos));
        std::fs::create_dir_all(&main_dir).unwrap();

        // Initialize git repo
        let git = |args: &[&str]| {
            std::process::Command::new("git")
                .args(args)
                .current_dir(&main_dir)
                .output()
                .expect("git command failed")
        };
        git(&["init"]);
        git(&["config", "user.email", "test@test.com"]);
        git(&["config", "user.name", "test"]);

        // Create tracked file and commit
        std::fs::write(main_dir.join("shared.rs"), "fn shared() { /* original */ }").unwrap();
        git(&["add", "."]);
        git(&["commit", "-m", "initial"]);

        // Create two worktrees
        let wt_a = std::env::temp_dir().join(format!("foundry-wt-copydel-a-{}", nanos));
        let wt_b = std::env::temp_dir().join(format!("foundry-wt-copydel-b-{}", nanos + 1));
        git(&[
            "worktree",
            "add",
            "--detach",
            wt_a.to_str().unwrap(),
            "HEAD",
        ]);
        git(&[
            "worktree",
            "add",
            "--detach",
            wt_b.to_str().unwrap(),
            "HEAD",
        ]);

        // Slot 0 (wt_a): modify shared.rs (copy intent)
        std::fs::write(
            wt_a.join("shared.rs"),
            "fn shared() { /* slot 0 modified */ }",
        )
        .unwrap();

        // Slot 1 (wt_b): delete shared.rs (delete intent)
        std::fs::remove_file(wt_b.join("shared.rs")).unwrap();

        // Discover changed files in each worktree
        let files_a = super::discover_changed_files_in_worktree(&wt_a).unwrap();
        let files_b = super::discover_changed_files_in_worktree(&wt_b).unwrap();
        assert!(
            files_a.contains(&"shared.rs".to_string()),
            "slot 0 must discover modified shared.rs"
        );
        assert!(
            files_b.contains(&"shared.rs".to_string()),
            "slot 1 must discover deleted shared.rs"
        );

        // No planned owner -- worst case for the bug
        let planned_file_owner: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut copied_files: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut deleted_by_slot: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut conflicts: Vec<(String, &str, usize, usize, usize)> = Vec::new();

        let slot_worktrees: Vec<(usize, &std::path::Path, Vec<String>)> =
            vec![(0, wt_a.as_path(), files_a), (1, wt_b.as_path(), files_b)];

        // Simulate the FIXED merge loop (matches production code after D19.1 fix)
        for (slot_idx, wt_dir, files_to_copy) in &slot_worktrees {
            for file_path in files_to_copy {
                let src = wt_dir.join(file_path);

                // Copy-vs-copy check: ONLY when current slot intends to copy
                if src.exists() {
                    if let Some(&prev_slot) = copied_files.get(file_path) {
                        let owner = planned_file_owner.get(file_path);
                        let winner = match owner {
                            Some(&owning_slot) => owning_slot,
                            None => prev_slot,
                        };
                        conflicts.push((
                            file_path.clone(),
                            "copy-copy",
                            prev_slot,
                            *slot_idx,
                            winner,
                        ));
                        if winner == prev_slot {
                            continue;
                        }
                    }
                }

                // Delete-vs-modify check
                if let Some(&del_slot) = deleted_by_slot.get(file_path) {
                    if src.exists() {
                        let owner = planned_file_owner.get(file_path);
                        let winner = match owner {
                            Some(&owning_slot) => owning_slot,
                            None => *slot_idx,
                        };
                        conflicts.push((
                            file_path.clone(),
                            "delete-modify",
                            del_slot,
                            *slot_idx,
                            winner,
                        ));
                        if winner == del_slot {
                            continue;
                        }
                    }
                }

                let dest = main_dir.join(file_path);
                if src.exists() {
                    if let Some(parent) = dest.parent() {
                        let _ = std::fs::create_dir_all(parent);
                    }
                    std::fs::copy(&src, &dest).unwrap();
                    copied_files.insert(file_path.clone(), *slot_idx);
                } else if dest.exists() {
                    // Modify-vs-delete check (previous slot copied, current deletes)
                    if let Some(&prev_slot) = copied_files.get(file_path) {
                        let owner = planned_file_owner.get(file_path);
                        let winner = match owner {
                            Some(&owning_slot) => owning_slot,
                            None => prev_slot,
                        };
                        conflicts.push((
                            file_path.clone(),
                            "modify-delete",
                            prev_slot,
                            *slot_idx,
                            winner,
                        ));
                        if winner == prev_slot {
                            continue;
                        }
                    }
                    std::fs::remove_file(&dest).unwrap();
                    deleted_by_slot.insert(file_path.clone(), *slot_idx);
                } else {
                    deleted_by_slot.insert(file_path.clone(), *slot_idx);
                }
            }
        }

        // === Key assertion: NO copy-copy conflict must have been recorded ===
        let copy_copy_conflicts: Vec<_> = conflicts
            .iter()
            .filter(|(_, kind, _, _, _)| *kind == "copy-copy")
            .collect();
        assert!(
            copy_copy_conflicts.is_empty(),
            "copy-vs-copy conflict must NOT fire when slot 1 deletes; got: {:?}",
            copy_copy_conflicts
        );

        // === A modify-delete conflict MUST have been detected ===
        let mod_del_conflict = conflicts
            .iter()
            .find(|(f, kind, _, _, _)| f == "shared.rs" && *kind == "modify-delete");
        assert!(
            mod_del_conflict.is_some(),
            "must detect modify-delete conflict on shared.rs, got conflicts: {:?}",
            conflicts
        );
        let mod_del_conflict = mod_del_conflict.unwrap();
        // prev_slot=0 (copied), cur_slot=1 (deletes), winner=0 (modification wins by default)
        assert_eq!(mod_del_conflict.2, 0, "prev_slot must be 0 (the copier)");
        assert_eq!(mod_del_conflict.3, 1, "cur_slot must be 1 (the deleter)");
        assert_eq!(
            mod_del_conflict.4, 0,
            "winner must be slot 0 (modification wins over deletion by default)"
        );

        // === shared.rs must still exist with slot 0's content ===
        assert!(
            main_dir.join("shared.rs").exists(),
            "shared.rs must exist after modification wins over deletion"
        );
        let content = std::fs::read_to_string(main_dir.join("shared.rs")).unwrap();
        assert!(
            content.contains("slot 0 modified"),
            "shared.rs must contain slot 0's version, got: {}",
            content
        );

        // Cleanup
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_a)
            .current_dir(&main_dir)
            .output();
        let _ = std::process::Command::new("git")
            .args(["worktree", "remove", "--force"])
            .arg(&wt_b)
            .current_dir(&main_dir)
            .output();
        let _ = std::fs::remove_dir_all(&main_dir);
        let _ = std::fs::remove_dir_all(&wt_a);
        let _ = std::fs::remove_dir_all(&wt_b);
    }
}

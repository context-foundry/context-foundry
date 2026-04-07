use std::collections::{BTreeMap, HashMap};
use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::Ordering;
use std::time::Duration;

use anyhow::{Context, Result};
use chrono::Utc;
use serde::Serialize;
use tokio::sync::mpsc;

use crate::agent::{AgentOutputEvent, ModelProvider};
use crate::config::Config;
use crate::patterns;
use crate::patterns::Pattern;
use crate::task::{self, Task};
use crate::update;
use crate::utils::atomic_write_file;

use super::build;
use super::context::RunContext;
use super::contract::ContractPaths;
use super::{AppEvent, LoopEvent};

#[derive(Serialize)]
struct TaskResult {
    id: String,
    description: String,
    status: String,
    commit_sha: Option<String>,
    findings: FindingCounts,
    duration_secs: f64,
}

#[derive(Serialize)]
struct FindingCounts {
    high: usize,
    medium: usize,
    low: usize,
}

#[derive(Serialize)]
struct SessionStats {
    total_duration_secs: f64,
    patterns_injected: usize,
    patterns_learned: usize,
    feat_commits: usize,
    wip_commits: usize,
}

#[derive(Serialize)]
struct ConfigSnapshot {
    run_mode: String,
    builder_provider: String,
    builder_model: String,
    reviewer_provider: String,
    reviewer_model: String,
}

#[derive(Serialize)]
struct SessionReport {
    tasks: Vec<TaskResult>,
    session: SessionStats,
    config: ConfigSnapshot,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ProviderCommandMode {
    Run,
    Plan,
    Design,
}

pub(crate) fn ensure_required_providers_available(
    config: &Config,
    mode: ProviderCommandMode,
) -> Result<()> {
    let missing = missing_provider_commands(config, mode, provider_binary_is_available);
    if missing.is_empty() {
        return Ok(());
    }

    let details = missing
        .into_iter()
        .map(|(provider, roles)| format!("{provider} ({})", roles.join(", ")))
        .collect::<Vec<_>>()
        .join("; ");

    anyhow::bail!(
        "required provider CLI not found: {}. Install the missing CLI(s) or change the corresponding *.provider setting in .foundry.json",
        details
    );
}

pub(crate) fn provider_binary_is_available(provider: ModelProvider) -> bool {
    let lookup_cmd = if cfg!(target_os = "windows") {
        "where"
    } else {
        "which"
    };
    std::process::Command::new(lookup_cmd)
        .arg(provider.slug())
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

pub(crate) fn docker_is_available() -> bool {
    let lookup_cmd = if cfg!(target_os = "windows") {
        "where"
    } else {
        "which"
    };
    std::process::Command::new(lookup_cmd)
        .arg("docker")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

pub(crate) fn semgrep_is_available() -> bool {
    let lookup_cmd = if cfg!(target_os = "windows") {
        "where"
    } else {
        "which"
    };
    std::process::Command::new(lookup_cmd)
        .arg("semgrep")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

/// Run semgrep against changed files and return findings as a string.
/// Returns empty string if semgrep is not available or produces no output.
pub(crate) fn run_semgrep(project_dir: &Path, rulesets: &[String], changed_files: &[String]) -> String {
    if changed_files.is_empty() || !semgrep_is_available() {
        return String::new();
    }

    let mut cmd = std::process::Command::new("semgrep");
    cmd.arg("--json")
        .arg("--quiet")
        .arg("--no-git-ignore")
        .current_dir(project_dir);

    if rulesets.is_empty() {
        cmd.arg("--config=auto");
    } else {
        for ruleset in rulesets {
            cmd.args(["--config", ruleset]);
        }
    }

    for f in changed_files {
        cmd.arg(f);
    }

    let output = match cmd.output() {
        Ok(o) => o,
        Err(_) => return String::new(),
    };

    let raw = String::from_utf8_lossy(&output.stdout);
    let json: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(_) => return String::new(),
    };

    let results = match json.get("results").and_then(|r| r.as_array()) {
        Some(arr) if !arr.is_empty() => arr,
        _ => return String::new(),
    };

    let mut summary = String::from("SEMGREP STATIC ANALYSIS FINDINGS:\n");
    for result in results {
        let check_id = result.get("check_id").and_then(|v| v.as_str()).unwrap_or("unknown");
        let message = result.get("extra")
            .and_then(|e| e.get("message"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let severity = result.get("extra")
            .and_then(|e| e.get("severity"))
            .and_then(|v| v.as_str())
            .unwrap_or("INFO");
        let path = result.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let start_line = result.get("start")
            .and_then(|s| s.get("line"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0);

        summary.push_str(&format!(
            "- [{severity}] {path}:{start_line} -- {check_id}: {message}\n"
        ));
    }
    summary.push_str(&format!("\nTotal: {} finding(s)\n", results.len()));
    summary
}

pub(crate) fn sandbox_image_exists(image: &str) -> bool {
    std::process::Command::new("docker")
        .args(["image", "inspect", image])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

fn missing_provider_commands<F>(
    config: &Config,
    mode: ProviderCommandMode,
    is_available: F,
) -> BTreeMap<&'static str, Vec<&'static str>>
where
    F: Fn(ModelProvider) -> bool,
{
    let mut missing = BTreeMap::<&'static str, Vec<&'static str>>::new();
    for (role, provider) in required_providers(config, mode) {
        if !is_available(provider) {
            missing.entry(provider.slug()).or_default().push(role);
        }
    }

    missing
}

fn required_providers(
    config: &Config,
    mode: ProviderCommandMode,
) -> Vec<(&'static str, ModelProvider)> {
    let mut providers = match mode {
        ProviderCommandMode::Plan => {
            vec![("planner", Config::parse_provider(&config.planner_provider))]
        }
        ProviderCommandMode::Run => {
            let mut v = vec![
                ("scout", Config::parse_provider(&config.scout_provider)),
                ("planner", Config::parse_provider(&config.planner_provider)),
                ("builder", Config::parse_provider(&config.builder_provider)),
                (
                    "discovery",
                    Config::parse_provider(&config.discovery_provider),
                ),
            ];
            if config.plan_review_enabled {
                v.push((
                    "orchestrator-proposer",
                    Config::parse_provider(&config.orchestrator_proposer_provider),
                ));
                v.push((
                    "orchestrator-reviewer",
                    Config::parse_provider(&config.orchestrator_reviewer_provider),
                ));
            }
            if config.builder_models.len() >= 2 {
                for spec in config.builder_models.iter().take(2) {
                    let (provider_str, _model) = Config::parse_model_spec(spec);
                    v.push(("builder (dual)", Config::parse_provider(&provider_str)));
                }
            }
            v
        }
        ProviderCommandMode::Design => vec![
            (
                "orchestrator-proposer",
                Config::parse_provider(&config.orchestrator_proposer_provider),
            ),
            (
                "orchestrator-reviewer",
                Config::parse_provider(&config.orchestrator_reviewer_provider),
            ),
        ],
    };

    if matches!(mode, ProviderCommandMode::Run) && !config.backpressure_only {
        providers.push((
            "reviewer",
            Config::parse_provider(&config.reviewer_provider),
        ));
        providers.push(("fixer", Config::parse_provider(&config.fixer_provider)));
    }

    providers
}

pub(super) async fn run_headless(project_dir: &Path, output_format: Option<String>) -> Result<()> {
    let contract_paths = ContractPaths::resolve(project_dir);
    let mut config = Config::load(project_dir);
    if config.run_mode == "review" {
        eprintln!(
            "[foundry] review mode is not supported in headless mode -- falling back to auto"
        );
        config.run_mode = "auto".to_string();
    }
    let config_snapshot_data = (
        config.run_mode.clone(),
        config.builder_provider.clone(),
        config.builder_model.clone(),
        config.reviewer_provider.clone(),
        config.reviewer_model.clone(),
    );
    let run_context = RunContext::new(
        project_dir,
        config,
        std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
        std::sync::Arc::new(std::sync::Mutex::new(())),
    );
    let shutdown_signal = run_context.shutdown.clone();
    tokio::spawn(async move {
        let _ = tokio::signal::ctrl_c().await;
        shutdown_signal.store(true, Ordering::Release);
    });

    for message in contract_paths.warnings() {
        eprintln!("[warn] {}", message);
    }
    if !run_context.plan_path.exists() {
        anyhow::bail!(
            "{} not found -- create one manually or run 'foundry plan' to generate it from {}",
            run_context.tasks_file_name(),
            run_context.spec_file_name()
        );
    }

    ensure_required_providers_available(&run_context.config, ProviderCommandMode::Run)?;

    // Sandbox detection (headless)
    let sandbox_cfg = run_context.config.sandbox_config();
    match sandbox_cfg.status() {
        crate::sandbox::SandboxStatus::Active => {
            sandbox_cfg.ensure_credentials_for_container();
            eprintln!("[foundry] sandbox active: image={}", sandbox_cfg.image);
        }
        crate::sandbox::SandboxStatus::DockerNotFound => {
            eprintln!("[foundry] warning: sandbox enabled but Docker not found; agents unsandboxed");
        }
        crate::sandbox::SandboxStatus::ImageNotFound => {
            eprintln!(
                "[foundry] warning: sandbox image '{}' not found; agents unsandboxed",
                sandbox_cfg.image
            );
        }
        crate::sandbox::SandboxStatus::Disabled => {
            eprintln!("[foundry] sandbox disabled");
        }
    }

    let (tx, mut rx) = mpsc::unbounded_channel::<AppEvent>();

    let loop_tx = tx.clone();
    tokio::spawn(async move {
        build::build_loop(run_context, loop_tx).await;
    });

    let update_tx = tx;
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_secs(2)).await;
        let result = tokio::task::spawn_blocking(update::check_for_update).await;
        if let Ok(Ok(Some(version))) = result {
            let _ = update_tx.send(AppEvent::UpdateAvailable(version));
        }
    });

    let mut update_version: Option<String> = None;
    let json_output = output_format.as_deref() == Some("json");
    let session_start = std::time::Instant::now();
    let mut task_results: Vec<TaskResult> = Vec::new();
    let mut task_descriptions: std::collections::HashMap<String, String> =
        std::collections::HashMap::new();
    let mut patterns_injected: usize = 0;
    let mut feat_commits: usize = 0;
    let mut wip_commits: usize = 0;
    let mut observatory_session_id: Option<String> = None;

    while let Some(evt) = rx.recv().await {
        match evt {
            AppEvent::AgentOutput(AgentOutputEvent::Text(text)) => {
                if json_output {
                    eprintln!("{}", text);
                } else {
                    println!("{}", text);
                }
            }
            AppEvent::AgentOutput(AgentOutputEvent::ToolUse {
                tool,
                input_preview,
            }) => {
                eprintln!("[tool] {} {}", tool, input_preview);
            }
            AppEvent::AgentOutput(AgentOutputEvent::ToolResult { output_preview }) => {
                if !output_preview.is_empty() {
                    let first = output_preview.lines().next().unwrap_or("");
                    eprintln!("[result] {}", first);
                }
            }
            AppEvent::AgentOutput(AgentOutputEvent::Stderr(line)) => {
                eprintln!("[stderr] {}", line);
            }
            AppEvent::AgentOutput(AgentOutputEvent::Result(text)) => {
                if json_output {
                    eprintln!("{}", text);
                } else {
                    println!("{}", text);
                }
            }
            AppEvent::AgentOutput(AgentOutputEvent::Usage { cost_usd, .. }) => {
                eprintln!("[cost] ${:.2}", cost_usd);
            }
            AppEvent::LoopEvent(loop_event) => match loop_event {
                LoopEvent::TaskStarted(task) => {
                    eprintln!("\n=== TASK: {} — {} ===", task.id, task.short_desc(80));
                    task_descriptions.insert(task.id.clone(), task.description.clone());
                }
                LoopEvent::AgentStarted(role, model) => {
                    eprintln!("--- {} ({}) ---", role, model);
                }
                LoopEvent::TaskCompleted(id, ok) => {
                    let status = if ok { "DONE" } else { "WIP" };
                    eprintln!("=== {} {} ===\n", id, status);
                    if ok {
                        feat_commits += 1;
                    } else {
                        wip_commits += 1;
                    }
                }
                LoopEvent::DiscoveryStarted(round) => {
                    eprintln!("\n=== DISCOVERY ROUND {} ===", round);
                }
                LoopEvent::DiscoveryCompleted(new_tasks) => {
                    eprintln!("=== Discovery found {} new tasks ===\n", new_tasks);
                }
                LoopEvent::Log(message) | LoopEvent::BackgroundLog(message) => {
                    eprintln!("[log] {}", message);
                }
                LoopEvent::Finished => break,
                LoopEvent::PatternsUsed { titles, .. } => {
                    patterns_injected += titles.len();
                }
                LoopEvent::TaskReport {
                    task_id,
                    status,
                    commit_sha,
                    findings_high,
                    findings_medium,
                    findings_low,
                    duration_secs,
                } => {
                    let description = task_descriptions.get(&task_id).cloned().unwrap_or_default();
                    task_results.push(TaskResult {
                        id: task_id,
                        description,
                        status,
                        commit_sha,
                        findings: FindingCounts {
                            high: findings_high,
                            medium: findings_medium,
                            low: findings_low,
                        },
                        duration_secs,
                    });
                }
                LoopEvent::SessionIdAssigned(sid) => {
                    observatory_session_id = Some(sid);
                }
                LoopEvent::CountsUpdated(_, _)
                | LoopEvent::NextTaskUpdated(_)
                | LoopEvent::QueueUpdated(_)
                | LoopEvent::TaskReviewResult { .. }
                | LoopEvent::ExtensionInjected { .. }
                | LoopEvent::ExtensionKeywordsLoaded { .. }
                | LoopEvent::PrPollChecked
                | LoopEvent::ShipStarted
                | LoopEvent::ShipDone
                | LoopEvent::DualBuildStarted { .. }
                | LoopEvent::DualBuildStreamDone(_, _)
                | LoopEvent::ParallelBuilderProgress { .. }
                | LoopEvent::TmuxSessionStarted(_)
                | LoopEvent::BudgetOverrun { .. } => {}
                LoopEvent::PrApproved { pr_num, .. } => {
                    eprintln!("[log] PR #{} approved -- resuming pipeline", pr_num);
                }
                LoopEvent::PrClosed { pr_num, .. } => {
                    eprintln!("[log] PR #{} was closed without merge -- stopping", pr_num);
                }
                LoopEvent::AwaitCommitApproval { ref task_id, ref gate, ref result, .. } => {
                    eprintln!(
                        "[foundry] WARNING: require_human_approval is TUI-only -- auto-approving {} in headless mode",
                        task_id
                    );
                    // Auto-approve: set result to true, then clear the gate
                    result.store(true);
                    gate.clear();
                }
                LoopEvent::CommitApprovalResponse { .. } => {}
                LoopEvent::WaitingForReview { ref gate, .. } => {
                    // In headless mode there is no TUI to clear the gate; auto-clear it so
                    // the build loop continues instead of hanging forever.
                    gate.clear();
                }
            },
            AppEvent::UpdateAvailable(version) => {
                update_version = Some(version);
            }
            AppEvent::AgentDone(_)
            | AppEvent::DualPipelineEvent(_, _)
            | AppEvent::PlanningFinished(_)
            | AppEvent::OrchestratorFinished(_)
            | AppEvent::Key(_)
            | AppEvent::Mouse(_)
            | AppEvent::Paste(_)
            | AppEvent::OllamaStatus(_)
            | AppEvent::Tick => {}
        }
    }

    if json_output {
        let report = SessionReport {
            tasks: task_results,
            session: SessionStats {
                total_duration_secs: session_start.elapsed().as_secs_f64(),
                patterns_injected,
                patterns_learned: 0,
                feat_commits,
                wip_commits,
            },
            config: ConfigSnapshot {
                run_mode: config_snapshot_data.0.clone(),
                builder_provider: config_snapshot_data.1.clone(),
                builder_model: config_snapshot_data.2.clone(),
                reviewer_provider: config_snapshot_data.3.clone(),
                reviewer_model: config_snapshot_data.4.clone(),
            },
        };
        println!(
            "{}",
            serde_json::to_string_pretty(&report)
                .unwrap_or_else(|e| format!("{{\"error\": \"{}\"}}", e))
        );
    }

    if !json_output {
        if let Some(ref sid) = observatory_session_id {
            let project_dir_canonical = dunce::canonicalize(project_dir)
                .unwrap_or_else(|_| project_dir.to_path_buf());
            if let Err(e) = crate::stats::print_session_summary(sid, &project_dir_canonical) {
                eprintln!("[warn] could not print session summary: {}", e);
            }
        }
    }

    if let Some(version) = update_version {
        eprintln!(
            "\nUpdate available: v{} → v{}. Run `foundry update` to upgrade.",
            update::current_version(),
            version
        );
    }

    Ok(())
}

pub(super) fn show_status(project_dir: &Path) -> Result<()> {
    let tasks = load_tasks(project_dir)?;
    print!("{}", format_status_output(project_dir, &tasks));
    Ok(())
}

pub(super) fn show_tasks(project_dir: &Path) -> Result<()> {
    let tasks = load_tasks(project_dir)?;
    print!("{}", format_tasks_output(&tasks));
    Ok(())
}

pub(super) fn run_extract(project_dir: &Path) -> Result<()> {
    let buildloop_dir = project_dir.join(".buildloop");
    let filenames = ["build-claims.md", "review-report.md"];
    let mut all_patterns = Vec::new();

    for name in &filenames {
        let path = buildloop_dir.join(name);
        if !path.exists() {
            continue;
        }
        if let Ok(mut extracted) = patterns::extract_patterns_from_file(&path) {
            all_patterns.append(&mut extracted);
        }
    }

    if all_patterns.is_empty() {
        return Ok(());
    }

    let config = crate::config::Config::load(project_dir);
    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    let added = patterns::merge_patterns(&patterns_dir, all_patterns)?;

    if added > 0 {
        println!(
            "foundry extract: {} new pattern(s) merged into {}",
            added,
            patterns_dir.display()
        );
    }

    Ok(())
}

pub(super) fn run_patterns_prune(yes: bool) -> Result<()> {
    let home = std::env::var("HOME").context("HOME not set")?;
    let obs_dir = PathBuf::from(&home).join(".foundry").join("observatory");

    let (events, _skipped) = crate::stats::load_events(&obs_dir, 30, None)?;
    if events.is_empty() {
        println!("No observatory events found in last 30 days.");
        return Ok(());
    }

    // Count injections and citations per pattern
    let mut injection_counts: HashMap<String, usize> = HashMap::new();
    let mut citation_counts: HashMap<String, usize> = HashMap::new();

    for ev in &events {
        if ev.event_type == "pattern_injected" {
            if let Some(ids) = ev.payload.get("pattern_ids").and_then(|v| v.as_array()) {
                for id_val in ids {
                    if let Some(id) = id_val.as_str() {
                        *injection_counts.entry(id.to_string()).or_insert(0) += 1;
                    }
                }
            }
        } else if ev.event_type == "pattern_cited" {
            if let Some(id) = ev.payload.get("pattern_id").and_then(|v| v.as_str()) {
                *citation_counts.entry(id.to_string()).or_insert(0) += 1;
            }
        }
    }

    // Find prune candidates: injected >= 10 times, cited 0 times
    let prune_candidates: Vec<String> = injection_counts
        .iter()
        .filter(|(id, count)| **count >= 10 && citation_counts.get(*id).copied().unwrap_or(0) == 0)
        .map(|(id, _)| id.clone())
        .collect();

    if prune_candidates.is_empty() {
        println!("No patterns qualify for pruning (need injection_count >= 10 and citation_count == 0).");
        return Ok(());
    }

    // Resolve patterns directory
    let config = Config::load(&PathBuf::from("."));
    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);

    // Build source map: pattern_id -> source file path
    let mut source_map: HashMap<String, PathBuf> = HashMap::new();
    if let Ok(entries) = std::fs::read_dir(&patterns_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("json") {
                continue;
            }
            let content = match std::fs::read_to_string(&path) {
                Ok(c) => c,
                Err(_) => continue,
            };
            // Try array format
            if let Ok(arr) = serde_json::from_str::<Vec<Pattern>>(&content) {
                for p in &arr {
                    source_map.insert(p.pattern_id.clone(), path.clone());
                }
            } else if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(pats) = val.get("patterns").and_then(|v| v.as_array()) {
                    for pv in pats {
                        if let Some(id) = pv.get("pattern_id").and_then(|v| v.as_str()) {
                            source_map.insert(id.to_string(), path.clone());
                        }
                    }
                }
            } else if let Ok(p) = serde_json::from_str::<Pattern>(&content) {
                source_map.insert(p.pattern_id.clone(), path.clone());
            }
        }
    }

    // Filter to actionable: exists in source map AND not already archived
    let archived_dir = patterns_dir.join("archived");
    let actionable: Vec<String> = prune_candidates
        .into_iter()
        .filter(|id| {
            source_map.contains_key(id)
                && !archived_dir.join(format!("{}.json", id)).exists()
        })
        .collect();

    if actionable.is_empty() {
        println!("All qualifying patterns are already archived.");
        return Ok(());
    }

    println!("Patterns to prune ({} total):", actionable.len());
    for id in &actionable {
        println!(
            "  {} (injected {}x, cited 0x, source: {})",
            id,
            injection_counts[id],
            source_map[id].display()
        );
    }

    if !yes {
        eprint!("\nProceed? [y/N] ");
        io::stderr().flush()?;
        let mut line = String::new();
        io::stdin().lock().read_line(&mut line)?;
        if !line.trim().starts_with('y') && !line.trim().starts_with('Y') {
            println!("Aborted.");
            return Ok(());
        }
    }

    std::fs::create_dir_all(&archived_dir)?;

    // Group actionable by source file
    let mut by_source: HashMap<PathBuf, Vec<String>> = HashMap::new();
    for id in &actionable {
        by_source
            .entry(source_map[id].clone())
            .or_default()
            .push(id.clone());
    }

    let mut total_pruned = 0usize;

    for (source_path, ids_to_remove) in &by_source {
        let content = match std::fs::read_to_string(source_path) {
            Ok(c) => c,
            Err(e) => {
                eprintln!("warning: failed to read {}: {}", source_path.display(), e);
                continue;
            }
        };

        let removal_set: std::collections::HashSet<&str> =
            ids_to_remove.iter().map(|s| s.as_str()).collect();

        // Try array format
        if let Ok(arr) = serde_json::from_str::<Vec<Pattern>>(&content) {
            let mut keep = Vec::new();
            let mut prune = Vec::new();
            for p in arr {
                if removal_set.contains(p.pattern_id.as_str()) {
                    prune.push(p);
                } else {
                    keep.push(p);
                }
            }
            for p in &prune {
                let json = serde_json::to_string_pretty(p)?;
                let dest = archived_dir.join(format!("{}.json", p.pattern_id));
                atomic_write_file(&dest, json.as_bytes())?;
                total_pruned += 1;
            }
            if keep.is_empty() {
                std::fs::remove_file(source_path)?;
            } else {
                let json = serde_json::to_string_pretty(&keep)?;
                atomic_write_file(source_path, json.as_bytes())?;
            }
            continue;
        }

        // Try wrapper format
        if let Ok(mut val) = serde_json::from_str::<serde_json::Value>(&content) {
            if val.get("patterns").and_then(|v| v.as_array()).is_some() {
                let pats_arr = val["patterns"].as_array().unwrap().clone();
                let mut keep_vals = Vec::new();
                for pv in &pats_arr {
                    let pid = pv.get("pattern_id").and_then(|v| v.as_str()).unwrap_or("");
                    if removal_set.contains(pid) {
                        // Archive this pattern
                        if let Ok(p) = serde_json::from_value::<Pattern>(pv.clone()) {
                            let json = serde_json::to_string_pretty(&p)?;
                            let dest = archived_dir.join(format!("{}.json", p.pattern_id));
                            atomic_write_file(&dest, json.as_bytes())?;
                            total_pruned += 1;
                        }
                    } else {
                        keep_vals.push(pv.clone());
                    }
                }
                if keep_vals.is_empty() {
                    std::fs::remove_file(source_path)?;
                } else {
                    val["patterns"] = serde_json::Value::Array(keep_vals);
                    let json = serde_json::to_string_pretty(&val)?;
                    atomic_write_file(source_path, json.as_bytes())?;
                }
                continue;
            }
        }

        // Try single pattern
        if let Ok(p) = serde_json::from_str::<Pattern>(&content) {
            if removal_set.contains(p.pattern_id.as_str()) {
                let dest = archived_dir.join(format!("{}.json", p.pattern_id));
                std::fs::rename(source_path, &dest)?;
                total_pruned += 1;
            }
        }
    }

    // Write prune log
    let log_path = archived_dir.join("prune-log.jsonl");
    let mut log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .context("failed to open prune-log.jsonl")?;
    let now = Utc::now().to_rfc3339();
    for id in &actionable {
        let entry = serde_json::json!({
            "pattern_id": id,
            "pruned_at": now,
            "reason": "injection_count >= 10, citation_count == 0 over 30 days",
            "injection_count": injection_counts[id],
        });
        writeln!(log_file, "{}", entry)?;
    }

    println!(
        "Pruned {} pattern(s) to {}",
        total_pruned,
        archived_dir.display()
    );

    Ok(())
}

pub(super) fn run_patterns_promote(apply: bool, days: u32) -> Result<()> {
    let home = std::env::var("HOME").context("HOME not set")?;
    let obs_dir = PathBuf::from(&home).join(".foundry").join("observatory");

    let (events, _skipped) = crate::stats::load_events(&obs_dir, days, None)?;
    if events.is_empty() {
        println!("No observatory events found in last {} days.", days);
        return Ok(());
    }

    // Count injections and citations per pattern
    let mut injection_counts: HashMap<String, usize> = HashMap::new();
    let mut citation_counts: HashMap<String, usize> = HashMap::new();

    for ev in &events {
        if ev.event_type == "pattern_injected" {
            if let Some(ids) = ev.payload.get("pattern_ids").and_then(|v| v.as_array()) {
                for id_val in ids {
                    if let Some(id) = id_val.as_str() {
                        *injection_counts.entry(id.to_string()).or_insert(0) += 1;
                    }
                }
            }
        } else if ev.event_type == "pattern_cited" {
            if let Some(id) = ev.payload.get("pattern_id").and_then(|v| v.as_str()) {
                *citation_counts.entry(id.to_string()).or_insert(0) += 1;
            }
        }
    }

    // Find qualifying patterns: injection_count >= 5 and citation_rate >= 0.3
    let qualifying_ids: Vec<String> = injection_counts
        .iter()
        .filter(|(id, &inj_count)| {
            if inj_count < 5 {
                return false;
            }
            let cit_count = citation_counts.get(*id).copied().unwrap_or(0);
            let rate = cit_count as f64 / inj_count as f64;
            rate >= 0.3
        })
        .map(|(id, _)| id.clone())
        .collect();

    if qualifying_ids.is_empty() {
        println!("No patterns qualify for promotion (need injection_count >= 5 and citation_rate >= 0.3).");
        return Ok(());
    }

    // Load all patterns with source file tracking
    let config = Config::load(&PathBuf::from("."));
    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    let patterns_with_sources = patterns::load_patterns_with_sources(&patterns_dir);

    let pattern_map: HashMap<String, (Pattern, PathBuf)> = patterns_with_sources
        .into_iter()
        .map(|(p, path)| (p.pattern_id.clone(), (p, path)))
        .collect();

    // Filter to patterns that exist and are not already promoted
    let promotable: Vec<&String> = qualifying_ids
        .iter()
        .filter(|id| {
            pattern_map.get(*id).is_some_and(|(p, _)| p.promoted_to.is_empty())
        })
        .collect();

    if promotable.is_empty() {
        println!("All qualifying patterns are already promoted.");
        return Ok(());
    }

    // Group promotable patterns by their primary tech stack (extension target)
    let home_path = PathBuf::from(&home);
    let ext_dir = home_path.join(".foundry").join("extensions");

    let mut by_extension: BTreeMap<String, Vec<&String>> = BTreeMap::new();
    for id in &promotable {
        let (pattern, _) = &pattern_map[*id];
        let ext_name = pattern.tech_stack.first()
            .map(|s| s.to_lowercase())
            .unwrap_or_else(|| "general".to_string());
        by_extension.entry(ext_name).or_default().push(id);
    }

    let today = Utc::now().format("%Y-%m-%d").to_string();
    // (pattern_id, ext_name, relative_path)
    let mut promotion_log: Vec<(String, String, String)> = Vec::new();

    for (ext_name, pattern_ids) in &by_extension {
        let target_dir = ext_dir.join(ext_name);
        let target_claude_md = target_dir.join("CLAUDE.md");
        let relative_path = format!("extensions/{}/CLAUDE.md", ext_name);

        let mut prose_blocks = String::new();
        for id in pattern_ids {
            let (pattern, _) = &pattern_map[*id];
            let inj = injection_counts.get(*id).copied().unwrap_or(0);
            let cit = citation_counts.get(*id).copied().unwrap_or(0);
            let rate = if inj > 0 { cit as f64 / inj as f64 } else { 0.0 };

            let block = generate_prose_block(pattern, inj, cit, rate);
            prose_blocks.push_str(&block);
            prose_blocks.push('\n');

            promotion_log.push(((*id).clone(), ext_name.clone(), relative_path.clone()));
        }

        if apply {
            // Create extension directory and patterns/ subdirectory
            std::fs::create_dir_all(&target_dir)?;
            std::fs::create_dir_all(target_dir.join("patterns"))?;

            let content = if target_claude_md.exists() {
                let existing = std::fs::read_to_string(&target_claude_md)
                    .context("failed to read existing CLAUDE.md")?;
                if existing.contains("## Promoted Patterns") {
                    format!("{}\n{}", existing.trim_end(), prose_blocks)
                } else {
                    format!("{}\n\n## Promoted Patterns\n\n{}", existing.trim_end(), prose_blocks)
                }
            } else {
                let title = ext_name.chars().next().map(|c| c.to_uppercase().to_string()).unwrap_or_default()
                    + &ext_name[1..];
                format!("# Context Foundry - {} Extension\n\n## Promoted Patterns\n\n{}", title, prose_blocks)
            };

            atomic_write_file(&target_claude_md, content.as_bytes())?;
        } else {
            // Dry-run: print what would be promoted
            println!("--- Extension: {} ({})", ext_name, target_dir.display());
            for id in pattern_ids {
                let (pattern, _) = &pattern_map[*id];
                let inj = injection_counts.get(*id).copied().unwrap_or(0);
                let cit = citation_counts.get(*id).copied().unwrap_or(0);
                let rate = if inj > 0 { cit as f64 / inj as f64 * 100.0 } else { 0.0 };
                println!("  {} - \"{}\" (injected {}x, cited {}x, {:.0}% citation rate)",
                    id, pattern.title, inj, cit, rate);
            }
            let block_preview = &prose_blocks;
            println!("\n  Generated prose:\n");
            for line in block_preview.lines() {
                println!("    {}", line);
            }
            println!();
        }
    }

    if apply {
        // Mark promoted patterns in their source JSON files using serde_json::Value
        let mut by_source: HashMap<PathBuf, Vec<(String, String, String)>> = HashMap::new();
        for (pattern_id, _ext_name, rel_path) in &promotion_log {
            let (_, source_path) = &pattern_map[pattern_id];
            by_source
                .entry(source_path.clone())
                .or_default()
                .push((pattern_id.clone(), rel_path.clone(), today.clone()));
        }

        for (source_path, promotions) in &by_source {
            let content = match std::fs::read_to_string(source_path) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("warning: failed to read {}: {}", source_path.display(), e);
                    continue;
                }
            };

            let promoted_ids: HashMap<&str, (&str, &str)> = promotions
                .iter()
                .map(|(id, path, date)| (id.as_str(), (path.as_str(), date.as_str())))
                .collect();

            // Try array format
            if let Ok(mut arr) = serde_json::from_str::<Vec<serde_json::Value>>(&content) {
                let mut modified = false;
                for val in &mut arr {
                    if let Some(id) = val.get("pattern_id").and_then(|v| v.as_str()) {
                        if let Some((path, date)) = promoted_ids.get(id) {
                            if let Some(obj) = val.as_object_mut() {
                                obj.insert("promoted_to".to_string(), serde_json::Value::String(path.to_string()));
                                obj.insert("promoted_at".to_string(), serde_json::Value::String(date.to_string()));
                            }
                            modified = true;
                        }
                    }
                }
                if modified {
                    let json = serde_json::to_string_pretty(&arr)?;
                    atomic_write_file(source_path, json.as_bytes())?;
                }
                continue;
            }

            // Try wrapper format
            if let Ok(mut val) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(pats) = val.get_mut("patterns").and_then(|v| v.as_array_mut()) {
                    let mut modified = false;
                    for pv in pats.iter_mut() {
                        if let Some(id) = pv.get("pattern_id").and_then(|v| v.as_str()) {
                            if let Some((path, date)) = promoted_ids.get(id) {
                                if let Some(obj) = pv.as_object_mut() {
                                    obj.insert("promoted_to".to_string(), serde_json::Value::String(path.to_string()));
                                    obj.insert("promoted_at".to_string(), serde_json::Value::String(date.to_string()));
                                }
                                modified = true;
                            }
                        }
                    }
                    if modified {
                        let json = serde_json::to_string_pretty(&val)?;
                        atomic_write_file(source_path, json.as_bytes())?;
                    }
                    continue;
                }
            }

            // Try single pattern format
            if let Ok(mut val) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(id) = val.get("pattern_id").and_then(|v| v.as_str()) {
                    if let Some((path, date)) = promoted_ids.get(id) {
                        if let Some(obj) = val.as_object_mut() {
                            obj.insert("promoted_to".to_string(), serde_json::Value::String(path.to_string()));
                            obj.insert("promoted_at".to_string(), serde_json::Value::String(date.to_string()));
                        }
                        let json = serde_json::to_string_pretty(&val)?;
                        atomic_write_file(source_path, json.as_bytes())?;
                    }
                }
            }
        }

        let ext_count = by_extension.len();
        println!(
            "Promoted {} pattern(s) to {} extension(s).",
            promotion_log.len(),
            ext_count,
        );
        for (ext_name, pattern_ids) in &by_extension {
            println!("  {} ({} pattern(s)):", ext_name, pattern_ids.len());
            for id in pattern_ids {
                println!("    - {}", id);
            }
        }
    } else {
        println!("Dry-run complete. Use --apply to write files.");
    }

    Ok(())
}

fn generate_prose_block(pattern: &Pattern, injection_count: usize, citation_count: usize, citation_rate: f64) -> String {
    let mut out = String::new();

    out.push_str(&format!("### {}\n\n", pattern.title));

    let issue_text = pattern.issue.as_deref().unwrap_or("(no issue description)");
    out.push_str(&format!("**Problem:** {}\n\n", issue_text));

    if let Some(ref sol) = pattern.solution {
        let mut parts = Vec::new();
        if !sol.planner.is_empty() {
            parts.push(sol.planner.as_str());
        }
        if !sol.reviewer.is_empty() {
            parts.push(sol.reviewer.as_str());
        }
        let combined = parts.join(" ");
        if !combined.is_empty() {
            out.push_str(&format!("**Solution:** {}\n\n", combined));
        }
    }

    let rate_pct = citation_rate * 100.0;
    out.push_str(&format!(
        "**Why:** Promoted from pattern `{}` -- cited {} times across {} injections ({:.0}% citation rate).\n",
        pattern.pattern_id, citation_count, injection_count, rate_pct,
    ));

    out
}

fn load_tasks(project_dir: &Path) -> Result<Vec<Task>> {
    let contract_paths = ContractPaths::resolve(project_dir);
    task::parse_tasks(&contract_paths.tasks_path)
}

fn format_status_output(project_dir: &Path, tasks: &[Task]) -> String {
    let completed = task::count_completed(tasks);
    let pending = task::count_pending(tasks);
    let total = tasks.len();
    let pct = if total > 0 {
        (completed as f64 / total as f64) * 100.0
    } else {
        0.0
    };

    let mut output = String::new();
    output.push_str(&format!("Foundry Status — {}\n", project_dir.display()));
    output.push_str("─────────────────────────────────────\n");
    output.push_str(&format!(
        "Progress: {}/{} ({:.0}%) — {} pending\n",
        completed, total, pct, pending
    ));

    if let Some(next) = task::next_pending(tasks) {
        output.push_str(&format!(
            "Next task: {} — {}\n",
            next.id,
            next.short_desc(60)
        ));
    } else {
        output.push_str("All tasks complete — discovery mode\n");
    }

    output
}

fn format_tasks_output(tasks: &[Task]) -> String {
    let mut output = String::new();
    for task in tasks {
        let check = if task.completed { "x" } else { " " };
        output.push_str(&format!(
            "[{}] {} — {}\n",
            check,
            task.id,
            task.short_desc(70)
        ));
    }

    output.push_str(&format!(
        "\n{} done, {} pending\n",
        task::count_completed(tasks),
        task::count_pending(tasks)
    ));

    output
}

#[cfg(test)]
mod tests {
    use std::path::{Path, PathBuf};
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::{
        format_status_output, format_tasks_output, missing_provider_commands, ProviderCommandMode,
    };
    use crate::agent::ModelProvider;
    use crate::config::Config;
    use crate::task;

    fn temp_dir(name: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("{}-{}", name, unique));
        std::fs::create_dir_all(&dir).expect("failed to create temp dir");
        dir
    }

    fn write_plan(dir: &Path, contents: &str) -> Vec<task::Task> {
        let path = dir.join("TASKS.md");
        std::fs::write(&path, contents).expect("failed to write plan");
        task::parse_tasks(&path).expect("failed to parse tasks")
    }

    #[test]
    fn status_output_includes_progress_and_next_task() {
        let dir = temp_dir("foundry-commands-status");
        let tasks = write_plan(
            &dir,
            "# Plan\n\n- [x] T1.1: finished task\n- [ ] T1.2: wire auth callbacks\n",
        );

        let output = format_status_output(&dir, &tasks);

        assert!(output.contains("Foundry Status"));
        assert!(output.contains("Progress: 1/2 (50%) — 1 pending"));
        assert!(output.contains("Next task: T1.2 — wire auth callbacks"));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn tasks_output_lists_each_task_and_summary() {
        let dir = temp_dir("foundry-commands-tasks");
        let tasks = write_plan(
            &dir,
            "# Plan\n\n- [x] T1.1: finished task\n- [ ] T1.2: wire auth callbacks\n",
        );

        let output = format_tasks_output(&tasks);

        assert!(output.contains("[x] T1.1 — finished task"));
        assert!(output.contains("[ ] T1.2 — wire auth callbacks"));
        assert!(output.contains("1 done, 1 pending"));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn run_mode_requires_codex_for_builder_and_fixer_when_configured() {
        let config = Config {
            builder_provider: "codex".into(),
            fixer_provider: "codex".into(),
            backpressure_only: false,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert_eq!(missing.get("codex"), Some(&vec!["builder", "fixer"]));
    }

    #[test]
    fn run_mode_skips_reviewer_and_fixer_in_backpressure_only_mode() {
        let config = Config {
            backpressure_only: true,
            planner_provider: "claude".into(),
            builder_provider: "claude".into(),
            reviewer_provider: "codex".into(),
            fixer_provider: "codex".into(),
            discovery_provider: "claude".into(),
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |_| false);

        assert!(!missing.values().flatten().any(|role| *role == "reviewer"));
        assert!(!missing.values().flatten().any(|role| *role == "fixer"));
    }

    #[test]
    fn plan_mode_only_requires_planner_provider() {
        let config = Config {
            planner_provider: "codex".into(),
            builder_provider: "codex".into(),
            reviewer_provider: "codex".into(),
            fixer_provider: "codex".into(),
            discovery_provider: "codex".into(),
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Plan, |_| false);

        assert_eq!(missing.get("codex"), Some(&vec!["planner"]));
        assert_eq!(missing.len(), 1);
    }

    #[test]
    fn design_mode_requires_orchestrator_proposer_and_reviewer() {
        let config = Config {
            orchestrator_proposer_provider: "codex".into(),
            orchestrator_reviewer_provider: "claude".into(),
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Design, |provider| {
            provider == ModelProvider::Claude
        });

        assert_eq!(missing.get("codex"), Some(&vec!["orchestrator-proposer"]));
        assert!(!missing.contains_key("claude"));
    }

    #[test]
    fn design_mode_does_not_check_builder_or_planner() {
        let config = Config {
            planner_provider: "codex".into(),
            builder_provider: "codex".into(),
            orchestrator_proposer_provider: "claude".into(),
            orchestrator_reviewer_provider: "claude".into(),
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Design, |_| true);

        assert!(missing.is_empty());
    }

    #[test]
    fn docker_is_available_returns_bool() {
        // Just verify it doesn't panic -- actual result depends on host
        let _ = super::docker_is_available();
    }

    #[test]
    fn sandbox_image_exists_returns_false_for_nonexistent() {
        assert!(!super::sandbox_image_exists("foundry-nonexistent-image-abc123:latest"));
    }

    #[test]
    fn run_mode_requires_scout_provider() {
        let config = Config {
            scout_provider: "codex".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(missing
            .values()
            .flatten()
            .any(|role| *role == "scout"));
    }

    #[test]
    fn run_mode_requires_orchestrator_providers_when_plan_review_enabled() {
        let config = Config {
            plan_review_enabled: true,
            orchestrator_proposer_provider: "codex".into(),
            orchestrator_reviewer_provider: "codex".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(missing
            .values()
            .flatten()
            .any(|role| *role == "orchestrator-proposer"));
        assert!(missing
            .values()
            .flatten()
            .any(|role| *role == "orchestrator-reviewer"));
    }

    #[test]
    fn run_mode_omits_orchestrator_providers_when_plan_review_disabled() {
        let config = Config {
            plan_review_enabled: false,
            orchestrator_proposer_provider: "codex".into(),
            orchestrator_reviewer_provider: "codex".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(!missing
            .values()
            .flatten()
            .any(|role| *role == "orchestrator-proposer"));
        assert!(!missing
            .values()
            .flatten()
            .any(|role| *role == "orchestrator-reviewer"));
    }
}

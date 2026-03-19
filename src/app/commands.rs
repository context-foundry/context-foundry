use std::collections::BTreeMap;
use std::path::Path;
use std::sync::atomic::Ordering;
use std::time::Duration;

use anyhow::Result;
use serde::Serialize;
use tokio::sync::mpsc;

use crate::agent::{AgentOutputEvent, ModelProvider};
use crate::config::Config;
use crate::task::{self, Task};
use crate::update;

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
                ("planner", Config::parse_provider(&config.planner_provider)),
                ("builder", Config::parse_provider(&config.builder_provider)),
                (
                    "discovery",
                    Config::parse_provider(&config.discovery_provider),
                ),
            ];
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
    let headless_review_gate = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
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
        headless_review_gate.clone(),
    );

    let shutdown_signal = run_context.shutdown.clone();
    tokio::spawn(async move {
        let _ = tokio::signal::ctrl_c().await;
        shutdown_signal.store(true, Ordering::Relaxed);
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
                | LoopEvent::DualBuildStreamDone(_, _) => {}
                LoopEvent::PrApproved(pr_num) => {
                    eprintln!("[log] PR #{} approved -- resuming pipeline", pr_num);
                }
                LoopEvent::PrClosed(pr_num) => {
                    eprintln!("[log] PR #{} was closed without merge -- stopping", pr_num);
                }
                LoopEvent::WaitingForReview(_) => {
                    // In headless mode there is no TUI to clear the gate; auto-clear it so
                    // the build loop continues instead of hanging forever.
                    headless_review_gate.store(false, Ordering::Relaxed);
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
}

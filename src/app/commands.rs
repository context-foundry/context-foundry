use std::collections::{BTreeMap, HashMap};
use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::Ordering;
use std::time::Duration;

use anyhow::{Context, Result};
use chrono::Utc;
use serde::Serialize;
use tokio::sync::mpsc;

use crate::agent::{AgentErrorKind, AgentOutputEvent, ModelProvider};
use crate::config::Config;
use crate::patterns;
use crate::patterns::Pattern;
use crate::skills;
use crate::task::{self, Task};
use crate::task_eval;
use crate::update;
use crate::utils::atomic_write_file;

use super::build;
use super::context::RunContext;
use super::contract::ContractPaths;
use super::{AppEvent, LoopEvent};

/// Schema version of the JSON report emitted by 'foundry run --no-tui --output-format json'.
/// Increment when fields are renamed, removed, or when a new top-level field is added.
/// v2 (D1.3): added `typed_error` top-level field of type Option<TypedErrorReport>.
pub(crate) const HEADLESS_REPORT_SCHEMA_VERSION: u32 = 2;

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
struct TypedErrorReport {
    kind: String,
    message: String,
    raw: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    tokens: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    ctx_size: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    model: Option<String>,
}

fn typed_error_report_from(kind: &AgentErrorKind, raw: &str) -> TypedErrorReport {
    let (kind_str, tokens, ctx_size, url, model) = match kind {
        AgentErrorKind::ContextOverflow { tokens, ctx_size } => (
            "ContextOverflow".to_string(),
            *tokens,
            *ctx_size,
            None,
            None,
        ),
        AgentErrorKind::ProviderUnreachable { url } => (
            "ProviderUnreachable".to_string(),
            None,
            None,
            url.clone(),
            None,
        ),
        AgentErrorKind::ModelNotLoaded { model } => (
            "ModelNotLoaded".to_string(),
            None,
            None,
            None,
            model.clone(),
        ),
    };
    let message = format_agent_error_message(kind);
    TypedErrorReport {
        kind: kind_str,
        message,
        raw: raw.to_string(),
        tokens,
        ctx_size,
        url,
        model,
    }
}

/// Mirror of src/app.rs::format_agent_error -- duplicated here to avoid
/// pulling app.rs internals into commands.rs. Keep these two functions in
/// sync if the typed-error catalog grows.
fn format_agent_error_message(kind: &AgentErrorKind) -> String {
    match kind {
        AgentErrorKind::ContextOverflow { tokens, ctx_size } => match (tokens, ctx_size) {
            (Some(t), Some(c)) => format!(
                "LM Studio context overflow: prompt was {} tokens but the loaded model has only n_ctx={}. Reload the model in LM Studio with a larger context size.",
                t, c
            ),
            _ => "LM Studio context overflow: the prompt exceeded the loaded model's n_ctx. Reload the model with a larger context size in LM Studio.".to_string(),
        },
        AgentErrorKind::ProviderUnreachable { url } => match url {
            Some(u) => format!(
                "Provider unreachable at {}. Confirm LM Studio is running and listening on the expected port.",
                u
            ),
            None => "Provider unreachable: failed to connect. Confirm LM Studio is running and listening on the expected port (default 127.0.0.1:1234).".to_string(),
        },
        AgentErrorKind::ModelNotLoaded { model } => match model {
            Some(m) => format!(
                "Model not loaded: '{}'. Load this model in LM Studio (or pick a different one in foundry settings).",
                m
            ),
            None => "Model not loaded: the requested model is not available in LM Studio. Load it (or pick a different one in foundry settings).".to_string(),
        },
    }
}

#[derive(Serialize)]
struct SessionReport {
    schema_version: u32,
    tasks: Vec<TaskResult>,
    session: SessionStats,
    config: ConfigSnapshot,
    #[serde(skip_serializing_if = "Option::is_none")]
    typed_error: Option<TypedErrorReport>,
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
    // Native HTTP providers have no CLI binary — they are always "available".
    if !provider.uses_pty() {
        return true;
    }
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
pub(crate) fn run_semgrep(
    project_dir: &Path,
    rulesets: &[String],
    changed_files: &[String],
) -> String {
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
        let check_id = result
            .get("check_id")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        let message = result
            .get("extra")
            .and_then(|e| e.get("message"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let severity = result
            .get("extra")
            .and_then(|e| e.get("severity"))
            .and_then(|v| v.as_str())
            .unwrap_or("INFO");
        let path = result.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let start_line = result
            .get("start")
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
            // Arena dual mode clears legacy builder_models at runtime, so skip
            // that validation path entirely when arena_mode == "dual".
            if config.arena_mode == "dual" {
                v.push(("builder", Config::parse_provider(&config.builder_provider)));
            } else if config.builder_models.is_empty() {
                v.push(("builder", Config::parse_provider(&config.builder_provider)));
            } else {
                let specs_to_check: Vec<&str> = match config.dual_selection.as_str() {
                    "first" => config
                        .builder_models
                        .first()
                        .map(|spec| vec![spec.as_str()])
                        .unwrap_or_default(),
                    "second" if config.builder_models.len() >= 2 => {
                        vec![config.builder_models[1].as_str()]
                    }
                    "third" if config.builder_models.len() >= 3 => {
                        vec![config.builder_models[2].as_str()]
                    }
                    "both" if config.builder_models.len() >= 2 => vec![
                        config.builder_models[0].as_str(),
                        config.builder_models[1].as_str(),
                    ],
                    _ => {
                        v.push(("builder", Config::parse_provider(&config.builder_provider)));
                        Vec::new()
                    }
                };
                for spec in specs_to_check {
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

    if matches!(mode, ProviderCommandMode::Run) && config.arena_mode == "dual" {
        // Only validate B providers for per-pipeline stages.
        // Excluded: scout (outer loop), discovery (outer loop), fixer (unused),
        // pr_review (not in build loop), patterns (hardcodes Claude).
        let mut b_providers: Vec<(&str, &str)> = vec![
            ("query (B)", &config.b_query_provider),
            ("research (B)", &config.b_research_provider),
            ("planner (B)", &config.b_planner_provider),
            ("builder (B)", &config.b_builder_provider),
        ];
        if !config.backpressure_only {
            b_providers.push(("reviewer (B)", &config.b_reviewer_provider));
        }
        for (role, prov) in b_providers {
            if !prov.is_empty() {
                providers.push((role, Config::parse_provider(prov)));
            }
        }
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

    // D1.3: keep a clone of the shutdown flag inside the event loop so the
    // typed-error circuit breaker can abort the build before the next stage
    // spawns. This must be cloned BEFORE run_context is moved into
    // tokio::spawn(build_loop).
    let abort_signal = run_context.shutdown.clone();

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
            eprintln!(
                "[foundry] warning: sandbox enabled but Docker not found; agents unsandboxed"
            );
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
    // D1.3: typed-error capture for the JSON report's `typed_error` field.
    let mut typed_error_record: Option<TypedErrorReport> = None;
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
            AppEvent::AgentOutput(AgentOutputEvent::TextDelta(text)) => {
                use std::io::Write;
                if json_output {
                    eprint!("{}", text);
                    let _ = std::io::stderr().flush();
                } else {
                    print!("{}", text);
                    let _ = std::io::stdout().flush();
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
            AppEvent::AgentOutput(AgentOutputEvent::Error { kind, raw }) => {
                eprintln!("[error/{:?}] {}", kind, raw);
                // D1.3: circuit breaker. Record the first typed error and signal
                // the build loop to abort so subsequent stages do not spawn and
                // re-emit the same failure. Keep the receive loop alive so any
                // already-queued events drain cleanly before LoopEvent::Finished.
                if typed_error_record.is_none() {
                    typed_error_record = Some(typed_error_report_from(&kind, &raw));
                    abort_signal.store(true, Ordering::Release);
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
                LoopEvent::AgentStageStarted {
                    role,
                    stage_id,
                    model,
                } => {
                    eprintln!("--- {} [{}] ({}) ---", role, stage_id, model);
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
                | LoopEvent::BudgetOverrun { .. }
                | LoopEvent::StatsReady(_)
                | LoopEvent::StatsLoadFailed => {}
                LoopEvent::PrApproved { pr_num, .. } => {
                    eprintln!("[log] PR #{} approved -- resuming pipeline", pr_num);
                }
                LoopEvent::PrClosed { pr_num, .. } => {
                    eprintln!("[log] PR #{} was closed without merge -- stopping", pr_num);
                }
                LoopEvent::AwaitCommitApproval {
                    ref task_id,
                    ref gate,
                    ref result,
                    ..
                } => {
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
            | AppEvent::CatalogRefreshed(_)
            | AppEvent::LocalModels { .. }
            | AppEvent::WelcomeMessage(_)
            | AppEvent::NarrativeRefresh(_)
            | AppEvent::Tick => {}
        }
    }

    // D1.3: capture whether the run was aborted before the report literal
    // moves typed_error_record via .take().
    let aborted_by_typed_error = typed_error_record.is_some();

    if json_output {
        let report = SessionReport {
            schema_version: HEADLESS_REPORT_SCHEMA_VERSION,
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
            typed_error: typed_error_record.take(),
        };
        println!(
            "{}",
            serde_json::to_string_pretty(&report)
                .unwrap_or_else(|e| format!("{{\"error\": \"{}\"}}", e))
        );
    }

    if !json_output {
        if let Some(ref sid) = observatory_session_id {
            let project_dir_canonical =
                dunce::canonicalize(project_dir).unwrap_or_else(|_| project_dir.to_path_buf());
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

    if aborted_by_typed_error {
        anyhow::bail!(
            "run aborted by typed agent error -- see [error/...] line on stderr (or 'typed_error' field in the JSON report)"
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

pub(super) fn show_task_evaluation(project_dir: &Path) -> Result<()> {
    let contract_paths = ContractPaths::resolve(project_dir);
    let eval = task_eval::evaluate_tasks_file(&contract_paths.tasks_path)?;
    print!("{}", task_eval::format_task_queue_evaluation(&eval));
    if !eval.ok() {
        anyhow::bail!("TASKS.md evaluation failed");
    }
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
    let obs_dir = crate::stats::observatory_dir()?;

    let (events, _skipped) = crate::stats::load_events(&obs_dir, 30, None)?;
    if events.is_empty() {
        println!("No observatory events found in last 30 days.");
        return Ok(());
    }

    // Count injections and citations per pattern
    let mut injection_counts: HashMap<String, usize> = HashMap::new();
    let mut citation_counts: HashMap<String, usize> = HashMap::new();

    for ev in &events {
        if crate::stats::is_pr_review_session(&ev.session_id) {
            continue;
        }
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
        println!(
            "No patterns qualify for pruning (need injection_count >= 10 and citation_count == 0)."
        );
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
            source_map.contains_key(id) && !archived_dir.join(format!("{}.json", id)).exists()
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
    let mut successfully_pruned: Vec<String> = Vec::new();

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
                successfully_pruned.push(p.pattern_id.clone());
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
                            successfully_pruned.push(p.pattern_id.clone());
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
                successfully_pruned.push(p.pattern_id.clone());
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
    for id in &successfully_pruned {
        let entry = serde_json::json!({
            "pattern_id": id,
            "pruned_at": now,
            "reason": "injection_count >= 10, citation_count == 0 over 30 days",
            "injection_count": injection_counts.get(id).copied().unwrap_or(0),
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

pub(super) fn run_patterns_prune_stale(yes: bool, dry_run: bool) -> Result<()> {
    let config = Config::load(&PathBuf::from("."));
    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    prune_stale_in_dir(&patterns_dir, yes, dry_run)
}

/// Pure inner function for the one-time prune-stale migration. Reads
/// `<patterns_dir>/common-issues.json`, partitions entries by the predicate
/// `cited_in_pass==0 AND cited_in_wip==0 AND frequency==1`, and archives
/// pruned entries to `<patterns_dir>/pruned-pre-migration-2026-05.json`.
///
/// The archive is written as a top-level JSON array of `serde_json::Value`,
/// so every field of every entry round-trips losslessly. The survivor file
/// is rewritten in its original outer shape (array stays array; wrapper
/// object retains all top-level keys with `patterns` replaced).
fn prune_stale_in_dir(patterns_dir: &Path, yes: bool, dry_run: bool) -> Result<()> {
    let source_path = patterns_dir.join("common-issues.json");
    let archive_path = patterns_dir.join("pruned-pre-migration-2026-05.json");

    if !source_path.exists() {
        println!(
            "common-issues.json not found at {}; nothing to prune.",
            source_path.display()
        );
        return Ok(());
    }

    if archive_path.exists() && !dry_run {
        anyhow::bail!(
            "archive file already exists at {}; remove it before re-running prune-stale (this is a one-time migration)",
            archive_path.display()
        );
    }

    let content = std::fs::read_to_string(&source_path)
        .with_context(|| format!("failed to read {}", source_path.display()))?;
    let mut root: serde_json::Value = serde_json::from_str(&content)
        .with_context(|| format!("failed to parse {} as JSON", source_path.display()))?;

    let (is_wrapper, items): (bool, Vec<serde_json::Value>) = if root.is_array() {
        (false, root.as_array().unwrap().clone())
    } else if root.is_object() && root.get("patterns").and_then(|v| v.as_array()).is_some() {
        (true, root["patterns"].as_array().unwrap().clone())
    } else {
        anyhow::bail!(
            "unrecognized format in {}: expected a top-level JSON array or an object with a \"patterns\" array",
            source_path.display()
        );
    };

    let total = items.len();
    let mut keep: Vec<serde_json::Value> = Vec::new();
    let mut prune: Vec<serde_json::Value> = Vec::new();
    for v in items {
        let cited_pass = v.get("cited_in_pass").and_then(|x| x.as_u64()).unwrap_or(0);
        let cited_wip = v.get("cited_in_wip").and_then(|x| x.as_u64()).unwrap_or(0);
        let frequency = v.get("frequency").and_then(|x| x.as_u64()).unwrap_or(0);
        if cited_pass == 0 && cited_wip == 0 && frequency == 1 {
            prune.push(v);
        } else {
            keep.push(v);
        }
    }

    let keep_count = keep.len();
    let prune_count = prune.len();

    println!(
        "common-issues.json: {} total | {} keep | {} prune",
        total, keep_count, prune_count
    );
    println!("Predicate: cited_in_pass==0 AND cited_in_wip==0 AND frequency==1");
    println!("Archive: {}", archive_path.display());

    if prune.is_empty() {
        println!("No patterns match the prune predicate; nothing to do.");
        return Ok(());
    }

    if dry_run {
        println!("Dry-run: no files written.");
        return Ok(());
    }

    if !yes {
        eprint!("\nProceed? [y/N] ");
        io::stderr().flush()?;
        let mut line = String::new();
        io::stdin().lock().read_line(&mut line)?;
        let trimmed = line.trim();
        if !trimmed.starts_with('y') && !trimmed.starts_with('Y') {
            println!("Aborted.");
            return Ok(());
        }
    }

    let archive_json = serde_json::to_string_pretty(&prune)?;
    atomic_write_file(&archive_path, archive_json.as_bytes())?;

    // Always re-write rather than delete: this is a one-time migration
    // and the survivor file's continued existence is meaningful.
    let new_json = if is_wrapper {
        root["patterns"] = serde_json::Value::Array(keep);
        serde_json::to_string_pretty(&root)?
    } else {
        serde_json::to_string_pretty(&serde_json::Value::Array(keep))?
    };
    atomic_write_file(&source_path, new_json.as_bytes())?;

    println!(
        "Pruned {} pattern(s); archived to {}. Survivors in common-issues.json: {}.",
        prune_count,
        archive_path.display(),
        keep_count
    );

    Ok(())
}

pub(super) fn run_patterns_migrate_to_skills(yes: bool, dry_run: bool) -> Result<()> {
    let config = Config::load(&PathBuf::from("."));
    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    let skills_dir = skills::resolve_skills_dir("~/.foundry/skills");
    migrate_to_skills_in_dir(&patterns_dir, &skills_dir, yes, dry_run)
}

/// Pure inner function for the one-time skills migration. Reads
/// `<patterns_dir>/common-issues.json`, walks each surviving pattern, and
/// writes one or two SKILL.md files per pattern under `<skills_dir>/`.
/// Refuses to overwrite existing skill SKILL.md files.
fn migrate_to_skills_in_dir(
    patterns_dir: &Path,
    skills_dir: &Path,
    yes: bool,
    dry_run: bool,
) -> Result<()> {
    let source_path = patterns_dir.join("common-issues.json");

    if !source_path.exists() {
        println!(
            "common-issues.json not found at {}; nothing to migrate.",
            source_path.display()
        );
        return Ok(());
    }

    let content = std::fs::read_to_string(&source_path)
        .with_context(|| format!("failed to read {}", source_path.display()))?;
    let root: serde_json::Value = serde_json::from_str(&content)
        .with_context(|| format!("failed to parse {} as JSON", source_path.display()))?;

    let items: Vec<serde_json::Value> = if root.is_array() {
        root.as_array().unwrap().clone()
    } else if root.is_object() && root.get("patterns").and_then(|v| v.as_array()).is_some() {
        root["patterns"].as_array().unwrap().clone()
    } else {
        anyhow::bail!(
            "unrecognized format in {}: expected a top-level JSON array or an object with a \"patterns\" array",
            source_path.display()
        );
    };

    let total_patterns = items.len();
    let mut warnings: Vec<String> = Vec::new();
    let mut skipped: Vec<String> = Vec::new();
    let mut planned: Vec<(String, String)> = Vec::new();

    for v in items {
        let id_for_warn = v
            .get("pattern_id")
            .and_then(|x| x.as_str())
            .unwrap_or("(unknown)")
            .to_string();
        let p: Pattern = match serde_json::from_value::<Pattern>(v) {
            Ok(p) => p,
            Err(e) => {
                warnings.push(format!("failed to deserialize pattern {}: {}", id_for_warn, e));
                continue;
            }
        };
        let files = skills::pattern_to_skill_files(&p);
        if files.is_empty() {
            skipped.push(format!("skipped {} (no solution)", p.pattern_id));
        } else {
            for (dir_name, contents) in files {
                planned.push((dir_name, contents));
            }
        }
    }

    let planned_files = planned.len();
    let skipped_count = skipped.len();

    println!(
        "common-issues.json: {} pattern(s) loaded",
        total_patterns
    );
    println!(
        "Planned: {} skill file(s); skipped {} pattern(s) with no solution",
        planned_files, skipped_count
    );
    println!("Target: {}", skills_dir.display());
    for line in &warnings {
        eprintln!("warning: {}", line);
    }

    if dry_run {
        println!("Dry-run: no files written.");
        return Ok(());
    }

    if !yes {
        eprint!("\nProceed? [y/N] ");
        io::stderr().flush()?;
        let mut line = String::new();
        io::stdin().lock().read_line(&mut line)?;
        let trimmed = line.trim();
        if !trimmed.starts_with('y') && !trimmed.starts_with('Y') {
            println!("Aborted.");
            return Ok(());
        }
    }

    let mut existing: Vec<String> = Vec::new();
    for (dir_name, _) in &planned {
        let target = skills_dir.join(dir_name).join("SKILL.md");
        if target.exists() {
            existing.push(dir_name.clone());
        }
    }
    if !existing.is_empty() {
        anyhow::bail!(
            "{} skill file(s) already exist (e.g. {}); remove the conflicting directories under {} before re-running migrate-to-skills (this is a one-time migration)",
            existing.len(),
            existing.first().unwrap(),
            skills_dir.display()
        );
    }

    std::fs::create_dir_all(skills_dir)
        .with_context(|| format!("failed to create {}", skills_dir.display()))?;

    for (dir_name, contents) in &planned {
        let dir = skills_dir.join(dir_name);
        std::fs::create_dir_all(&dir)
            .with_context(|| format!("failed to create {}", dir.display()))?;
        let target = dir.join("SKILL.md");
        atomic_write_file(&target, contents.as_bytes())
            .with_context(|| format!("failed to write {}", target.display()))?;
    }

    println!(
        "Migrated {} skill file(s) to {}.",
        planned_files,
        skills_dir.display()
    );

    Ok(())
}

pub(super) fn run_patterns_promote(apply: bool, days: u32) -> Result<()> {
    let obs_dir = crate::stats::observatory_dir()?;

    let (events, _skipped) = crate::stats::load_events(&obs_dir, days, None)?;
    if events.is_empty() {
        println!("No observatory events found in last {} days.", days);
        return Ok(());
    }

    // Count injections and citations per pattern
    let mut injection_counts: HashMap<String, usize> = HashMap::new();
    let mut citation_counts: HashMap<String, usize> = HashMap::new();

    for ev in &events {
        if crate::stats::is_pr_review_session(&ev.session_id) {
            continue;
        }
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
            pattern_map
                .get(*id)
                .is_some_and(|(p, _)| p.promoted_to.is_empty())
        })
        .collect();

    if promotable.is_empty() {
        println!("All qualifying patterns are already promoted.");
        return Ok(());
    }

    // Group promotable patterns by their primary tech stack (extension target)
    let home_path = crate::utils::home_dir().context("HOME or USERPROFILE not set")?;
    let ext_dir = home_path.join(".foundry").join("extensions");

    let mut by_extension: BTreeMap<String, Vec<&String>> = BTreeMap::new();
    for id in &promotable {
        let (pattern, _) = &pattern_map[*id];
        let ext_name = pattern
            .tech_stack
            .first()
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

        // Read existing CLAUDE.md content for deduplication
        let existing_content = if target_claude_md.exists() {
            std::fs::read_to_string(&target_claude_md).unwrap_or_default()
        } else {
            String::new()
        };

        let mut prose_blocks = String::new();
        for id in pattern_ids {
            // Skip patterns already present in CLAUDE.md (idempotency for partial-failure re-runs)
            if existing_content.contains(&format!("`{}`", *id)) {
                continue;
            }

            let (pattern, _) = &pattern_map[*id];
            let inj = injection_counts.get(*id).copied().unwrap_or(0);
            let cit = citation_counts.get(*id).copied().unwrap_or(0);
            let rate = if inj > 0 {
                cit as f64 / inj as f64
            } else {
                0.0
            };

            let block = generate_prose_block(pattern, inj, cit, rate);
            prose_blocks.push_str(&block);
            prose_blocks.push('\n');

            promotion_log.push(((*id).clone(), ext_name.clone(), relative_path.clone()));
        }

        if apply && !prose_blocks.is_empty() {
            // Create extension directory and patterns/ subdirectory
            std::fs::create_dir_all(&target_dir)?;
            std::fs::create_dir_all(target_dir.join("patterns"))?;

            let content = if !existing_content.is_empty() {
                if existing_content.contains("## Promoted Patterns") {
                    format!("{}\n{}", existing_content.trim_end(), prose_blocks)
                } else {
                    format!(
                        "{}\n\n## Promoted Patterns\n\n{}",
                        existing_content.trim_end(),
                        prose_blocks
                    )
                }
            } else {
                let title = {
                    let mut chars = ext_name.chars();
                    match chars.next() {
                        Some(c) => {
                            let upper = c.to_uppercase().to_string();
                            upper + chars.as_str()
                        }
                        None => String::new(),
                    }
                };
                format!(
                    "# Context Foundry - {} Extension\n\n## Promoted Patterns\n\n{}",
                    title, prose_blocks
                )
            };

            atomic_write_file(&target_claude_md, content.as_bytes())?;
        } else if !apply {
            // Dry-run: print what would be promoted
            println!("--- Extension: {} ({})", ext_name, target_dir.display());
            for id in pattern_ids {
                // Skip already-promoted patterns in dry-run output too
                if existing_content.contains(&format!("`{}`", *id)) {
                    continue;
                }
                let (pattern, _) = &pattern_map[*id];
                let inj = injection_counts.get(*id).copied().unwrap_or(0);
                let cit = citation_counts.get(*id).copied().unwrap_or(0);
                let rate = if inj > 0 {
                    cit as f64 / inj as f64 * 100.0
                } else {
                    0.0
                };
                println!(
                    "  {} - \"{}\" (injected {}x, cited {}x, {:.0}% citation rate)",
                    id, pattern.title, inj, cit, rate
                );
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
            by_source.entry(source_path.clone()).or_default().push((
                pattern_id.clone(),
                rel_path.clone(),
                today.clone(),
            ));
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
                                obj.insert(
                                    "promoted_to".to_string(),
                                    serde_json::Value::String(path.to_string()),
                                );
                                obj.insert(
                                    "promoted_at".to_string(),
                                    serde_json::Value::String(date.to_string()),
                                );
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
                                    obj.insert(
                                        "promoted_to".to_string(),
                                        serde_json::Value::String(path.to_string()),
                                    );
                                    obj.insert(
                                        "promoted_at".to_string(),
                                        serde_json::Value::String(date.to_string()),
                                    );
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
                            obj.insert(
                                "promoted_to".to_string(),
                                serde_json::Value::String(path.to_string()),
                            );
                            obj.insert(
                                "promoted_at".to_string(),
                                serde_json::Value::String(date.to_string()),
                            );
                        }
                        let json = serde_json::to_string_pretty(&val)?;
                        atomic_write_file(source_path, json.as_bytes())?;
                    }
                }
            }
        }

        // Build summary from promotion_log (only newly-promoted patterns)
        let mut promoted_by_ext: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
        for (pattern_id, ext_name, _) in &promotion_log {
            promoted_by_ext
                .entry(ext_name.as_str())
                .or_default()
                .push(pattern_id.as_str());
        }
        println!(
            "Promoted {} pattern(s) to {} extension(s).",
            promotion_log.len(),
            promoted_by_ext.len(),
        );
        for (ext_name, pattern_ids) in &promoted_by_ext {
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

fn generate_prose_block(
    pattern: &Pattern,
    injection_count: usize,
    citation_count: usize,
    citation_rate: f64,
) -> String {
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

    use std::collections::BTreeSet;

    use super::{
        format_status_output, format_tasks_output, migrate_to_skills_in_dir,
        missing_provider_commands, prune_stale_in_dir, ProviderCommandMode,
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
        assert!(!super::sandbox_image_exists(
            "foundry-nonexistent-image-abc123:latest"
        ));
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

        assert!(missing.values().flatten().any(|role| *role == "scout"));
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

    // dual_selection provider validation tests

    #[test]
    fn dual_first_only_validates_first_builder_model_provider() {
        // "first" selected, second entry uses codex (not installed) -- should not appear
        let config = Config {
            builder_models: vec!["claude:opus".into(), "codex:".into()],
            dual_selection: "first".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(
            !missing
                .values()
                .flatten()
                .any(|role| *role == "builder (dual)"),
            "codex (second slot) should not be required when dual_selection=first"
        );
    }

    #[test]
    fn dual_second_only_validates_second_builder_model_provider() {
        // "second" selected, first entry uses claude (available) -- should not flag it
        // second entry uses codex (not installed) -- should appear
        let config = Config {
            builder_models: vec!["claude:opus".into(), "codex:".into()],
            dual_selection: "second".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(
            missing
                .values()
                .flatten()
                .any(|role| *role == "builder (dual)"),
            "codex (second slot) should be required when dual_selection=second"
        );
    }

    #[test]
    fn dual_third_only_validates_third_builder_model_provider() {
        let config = Config {
            builder_models: vec![
                "claude:opus".into(),
                "claude:sonnet".into(),
                "codex:".into(),
            ],
            dual_selection: "third".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(
            missing
                .values()
                .flatten()
                .any(|role| *role == "builder (dual)"),
            "codex (third slot) should be required when dual_selection=third"
        );
    }

    #[test]
    fn dual_both_validates_both_builder_model_providers() {
        let config = Config {
            builder_models: vec!["claude:opus".into(), "codex:".into()],
            dual_selection: "both".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(
            missing
                .values()
                .flatten()
                .any(|role| *role == "builder (dual)"),
            "codex should be required when dual_selection=both"
        );
    }

    #[test]
    fn dual_unknown_selection_validates_no_builder_model_providers() {
        let config = Config {
            builder_models: vec!["codex:".into(), "codex:".into()],
            dual_selection: "off".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(
            !missing
                .values()
                .flatten()
                .any(|role| *role == "builder (dual)"),
            "unknown dual_selection should not validate any builder_models entries"
        );
    }

    #[test]
    fn dual_first_ignores_base_builder_provider_when_unused() {
        let config = Config {
            builder_provider: "codex".into(),
            builder_models: vec!["claude:opus".into(), "claude:sonnet".into()],
            dual_selection: "first".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(
            !missing.values().flatten().any(|role| *role == "builder"),
            "base builder_provider should not be required when dual_selection=first uses builder_models[0]"
        );
    }

    #[test]
    fn dual_both_ignores_base_builder_provider_when_unused() {
        let config = Config {
            builder_provider: "codex".into(),
            builder_models: vec!["claude:opus".into(), "claude:sonnet".into()],
            dual_selection: "both".into(),
            backpressure_only: true,
            ..Config::default()
        };

        let missing = missing_provider_commands(&config, ProviderCommandMode::Run, |provider| {
            provider == ModelProvider::Claude
        });

        assert!(
            !missing.values().flatten().any(|role| *role == "builder"),
            "base builder_provider should not be required when dual_selection=both uses only builder_models"
        );
    }

    fn read_ids_array(path: &Path) -> BTreeSet<String> {
        let content = std::fs::read_to_string(path).expect("read file");
        let arr: Vec<serde_json::Value> = serde_json::from_str(&content).expect("parse array");
        arr.iter()
            .filter_map(|v| v.get("pattern_id").and_then(|x| x.as_str()).map(String::from))
            .collect()
    }

    #[test]
    fn prune_stale_in_dir_array_format_partitions_correctly() {
        let dir = temp_dir("foundry-prune-stale-array");
        let source = dir.join("common-issues.json");
        let body = serde_json::json!([
            {"pattern_id":"keep-cited","frequency":1,"cited_in_pass":1,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""},
            {"pattern_id":"keep-freq","frequency":3,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""},
            {"pattern_id":"keep-freq2","frequency":2,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""},
            {"pattern_id":"prune-1","frequency":1,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""},
            {"pattern_id":"prune-2","frequency":1,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""}
        ]);
        std::fs::write(&source, serde_json::to_string_pretty(&body).unwrap())
            .expect("write source");

        prune_stale_in_dir(&dir, true, false).unwrap();

        let kept = read_ids_array(&source);
        assert_eq!(kept.len(), 3);
        let expected_keep: BTreeSet<String> = ["keep-cited", "keep-freq", "keep-freq2"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        assert_eq!(kept, expected_keep);

        let archive = dir.join("pruned-pre-migration-2026-05.json");
        let pruned = read_ids_array(&archive);
        assert_eq!(pruned.len(), 2);
        let expected_prune: BTreeSet<String> = ["prune-1", "prune-2"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        assert_eq!(pruned, expected_prune);

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn prune_stale_in_dir_wrapper_format_preserves_outer_keys() {
        let dir = temp_dir("foundry-prune-stale-wrapper");
        let source = dir.join("common-issues.json");
        let body = serde_json::json!({
            "pattern_type": "common-issues",
            "domain": "global",
            "version": "1.0.0",
            "patterns": [
                {"pattern_id":"keep-1","frequency":3,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""},
                {"pattern_id":"prune-1","frequency":1,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""}
            ]
        });
        std::fs::write(&source, serde_json::to_string_pretty(&body).unwrap())
            .expect("write source");

        prune_stale_in_dir(&dir, true, false).unwrap();

        let content = std::fs::read_to_string(&source).expect("read source");
        let val: serde_json::Value = serde_json::from_str(&content).expect("parse");
        assert_eq!(val["pattern_type"], "common-issues");
        assert_eq!(val["domain"], "global");
        assert_eq!(val["version"], "1.0.0");
        let pats = val["patterns"].as_array().expect("patterns array");
        assert_eq!(pats.len(), 1);
        assert_eq!(pats[0]["pattern_id"], "keep-1");

        let archive = dir.join("pruned-pre-migration-2026-05.json");
        let pruned = read_ids_array(&archive);
        assert_eq!(pruned.len(), 1);
        assert!(pruned.contains("prune-1"));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn prune_stale_in_dir_missing_source_is_noop() {
        let dir = temp_dir("foundry-prune-stale-missing");

        prune_stale_in_dir(&dir, true, false).unwrap();

        assert!(!dir.join("pruned-pre-migration-2026-05.json").exists());

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn prune_stale_in_dir_existing_archive_errors() {
        let dir = temp_dir("foundry-prune-stale-existing-archive");
        let source = dir.join("common-issues.json");
        let archive = dir.join("pruned-pre-migration-2026-05.json");
        std::fs::write(&source, "[]").expect("write source");
        std::fs::write(&archive, "[]").expect("write archive");

        let err = prune_stale_in_dir(&dir, true, false).unwrap_err();
        assert!(format!("{:?}", err).contains("archive file already exists"));

        let content = std::fs::read_to_string(&source).expect("read source");
        assert_eq!(content, "[]");

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn prune_stale_in_dir_no_matches_is_noop() {
        let dir = temp_dir("foundry-prune-stale-no-matches");
        let source = dir.join("common-issues.json");
        let body = serde_json::json!([
            {"pattern_id":"keep-1","frequency":2,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""}
        ]);
        std::fs::write(&source, serde_json::to_string_pretty(&body).unwrap())
            .expect("write source");

        prune_stale_in_dir(&dir, true, false).unwrap();

        assert!(!dir.join("pruned-pre-migration-2026-05.json").exists());
        let kept = read_ids_array(&source);
        assert_eq!(kept.len(), 1);

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn prune_stale_in_dir_all_pruned_writes_empty_array_keeps_file() {
        let dir = temp_dir("foundry-prune-stale-all");
        let source = dir.join("common-issues.json");
        let body = serde_json::json!([
            {"pattern_id":"prune-1","frequency":1,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""},
            {"pattern_id":"prune-2","frequency":1,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""}
        ]);
        std::fs::write(&source, serde_json::to_string_pretty(&body).unwrap())
            .expect("write source");

        prune_stale_in_dir(&dir, true, false).unwrap();

        assert!(source.exists(), "common-issues.json should still exist");
        let content = std::fs::read_to_string(&source).expect("read source");
        let arr: Vec<serde_json::Value> = serde_json::from_str(&content).expect("parse");
        assert!(arr.is_empty());

        let archive = dir.join("pruned-pre-migration-2026-05.json");
        let pruned = read_ids_array(&archive);
        assert_eq!(pruned.len(), 2);

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn prune_stale_in_dir_unrecognized_format_errors() {
        let dir = temp_dir("foundry-prune-stale-bad-format");
        let source = dir.join("common-issues.json");
        std::fs::write(&source, "{\"foo\": 1}").expect("write source");

        let err = prune_stale_in_dir(&dir, true, false).unwrap_err();
        assert!(format!("{:?}", err).contains("unrecognized format"));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn prune_stale_in_dir_dry_run_writes_nothing() {
        let dir = temp_dir("foundry-prune-stale-dry");
        let source = dir.join("common-issues.json");
        let body = serde_json::json!([
            {"pattern_id":"keep-1","frequency":3,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""},
            {"pattern_id":"prune-1","frequency":1,"cited_in_pass":0,"cited_in_wip":0,"title":"t","first_seen":"","last_seen":""}
        ]);
        let original = serde_json::to_string_pretty(&body).unwrap();
        std::fs::write(&source, &original).expect("write source");

        prune_stale_in_dir(&dir, false, true).unwrap();

        assert!(!dir.join("pruned-pre-migration-2026-05.json").exists());
        let after = std::fs::read_to_string(&source).expect("read source");
        let arr: Vec<serde_json::Value> = serde_json::from_str(&after).expect("parse");
        assert_eq!(arr.len(), 2);

        let _ = std::fs::remove_dir_all(dir);
    }

    fn write_migration_source(patterns_dir: &Path, body: &serde_json::Value) {
        std::fs::create_dir_all(patterns_dir).expect("create patterns dir");
        let source = patterns_dir.join("common-issues.json");
        std::fs::write(&source, serde_json::to_string_pretty(body).unwrap())
            .expect("write source");
    }

    #[test]
    fn migrate_to_skills_in_dir_writes_one_file_for_planner_only() {
        let root = temp_dir("foundry-migrate-skills-planner-only");
        let patterns_dir = root.join("patterns");
        let skills_dir = root.join("skills");
        write_migration_source(
            &patterns_dir,
            &serde_json::json!([{
                "pattern_id": "p1",
                "title": "Title",
                "frequency": 1,
                "keywords": ["alpha"],
                "tech_stack": ["rust"],
                "issue": "Bad thing",
                "solution": {"planner": "Do X", "reviewer": ""}
            }]),
        );

        migrate_to_skills_in_dir(&patterns_dir, &skills_dir, true, false).unwrap();

        let p1_skill = skills_dir.join("p1").join("SKILL.md");
        assert!(p1_skill.exists());
        let contents = std::fs::read_to_string(&p1_skill).unwrap();
        assert!(contents.contains("cf-stage: planner"));
        assert!(contents.contains("Do X"));
        assert!(!skills_dir.join("p1-reviewer").exists());

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn migrate_to_skills_in_dir_writes_two_files_for_both_stages() {
        let root = temp_dir("foundry-migrate-skills-both");
        let patterns_dir = root.join("patterns");
        let skills_dir = root.join("skills");
        write_migration_source(
            &patterns_dir,
            &serde_json::json!([{
                "pattern_id": "p2",
                "title": "Title",
                "frequency": 2,
                "keywords": [],
                "tech_stack": [],
                "issue": "Bad",
                "solution": {"planner": "Plan it", "reviewer": "Check it"}
            }]),
        );

        migrate_to_skills_in_dir(&patterns_dir, &skills_dir, true, false).unwrap();

        let planner = skills_dir.join("p2-planner").join("SKILL.md");
        let reviewer = skills_dir.join("p2-reviewer").join("SKILL.md");
        assert!(planner.exists());
        assert!(reviewer.exists());
        assert!(std::fs::read_to_string(&planner)
            .unwrap()
            .contains("cf-stage: planner"));
        assert!(std::fs::read_to_string(&reviewer)
            .unwrap()
            .contains("cf-stage: reviewer"));

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn migrate_to_skills_in_dir_handles_wrapper_format_input() {
        let root = temp_dir("foundry-migrate-skills-wrapper");
        let patterns_dir = root.join("patterns");
        let skills_dir = root.join("skills");
        write_migration_source(
            &patterns_dir,
            &serde_json::json!({
                "pattern_type": "common-issues",
                "domain": "global",
                "patterns": [{
                    "pattern_id": "wp1",
                    "title": "Wrapped",
                    "frequency": 3,
                    "keywords": [],
                    "tech_stack": [],
                    "issue": "Bad",
                    "solution": {"planner": "Plan", "reviewer": ""}
                }]
            }),
        );

        migrate_to_skills_in_dir(&patterns_dir, &skills_dir, true, false).unwrap();

        assert!(skills_dir.join("wp1").join("SKILL.md").exists());

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn migrate_to_skills_in_dir_dry_run_writes_nothing() {
        let root = temp_dir("foundry-migrate-skills-dry");
        let patterns_dir = root.join("patterns");
        let skills_dir = root.join("skills");
        write_migration_source(
            &patterns_dir,
            &serde_json::json!([{
                "pattern_id": "drypid",
                "title": "Dry",
                "frequency": 1,
                "keywords": [],
                "tech_stack": [],
                "issue": "Bad",
                "solution": {"planner": "Plan", "reviewer": ""}
            }]),
        );

        migrate_to_skills_in_dir(&patterns_dir, &skills_dir, false, true).unwrap();

        let no_files = !skills_dir.exists()
            || std::fs::read_dir(&skills_dir)
                .map(|mut e| e.next().is_none())
                .unwrap_or(true);
        assert!(no_files, "skills_dir must not contain files after dry-run");

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn migrate_to_skills_in_dir_skips_patterns_with_no_solution() {
        let root = temp_dir("foundry-migrate-skills-no-solution");
        let patterns_dir = root.join("patterns");
        let skills_dir = root.join("skills");
        write_migration_source(
            &patterns_dir,
            &serde_json::json!([{
                "pattern_id": "nosol",
                "title": "No",
                "frequency": 1,
                "keywords": [],
                "tech_stack": [],
                "issue": "Bad",
                "solution": null
            }]),
        );

        migrate_to_skills_in_dir(&patterns_dir, &skills_dir, true, false).unwrap();

        assert!(!skills_dir.join("nosol").exists());

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn migrate_to_skills_in_dir_errors_on_collision() {
        let root = temp_dir("foundry-migrate-skills-collision");
        let patterns_dir = root.join("patterns");
        let skills_dir = root.join("skills");
        let collision_dir = skills_dir.join("colpid");
        std::fs::create_dir_all(&collision_dir).expect("mkdir collision");
        let collision_file = collision_dir.join("SKILL.md");
        std::fs::write(&collision_file, "PRE-EXISTING").expect("write collision");
        write_migration_source(
            &patterns_dir,
            &serde_json::json!([{
                "pattern_id": "colpid",
                "title": "Coll",
                "frequency": 1,
                "keywords": [],
                "tech_stack": [],
                "issue": "Bad",
                "solution": {"planner": "Plan", "reviewer": ""}
            }]),
        );

        let err = migrate_to_skills_in_dir(&patterns_dir, &skills_dir, true, false).unwrap_err();
        assert!(format!("{:?}", err).contains("already exist"));
        let unchanged = std::fs::read_to_string(&collision_file).unwrap();
        assert_eq!(unchanged, "PRE-EXISTING");

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn migrate_to_skills_in_dir_missing_source_is_noop() {
        let root = temp_dir("foundry-migrate-skills-missing");
        let patterns_dir = root.join("patterns");
        let skills_dir = root.join("skills");
        std::fs::create_dir_all(&patterns_dir).expect("mkdir");

        migrate_to_skills_in_dir(&patterns_dir, &skills_dir, true, false).unwrap();

        assert!(!skills_dir.exists());

        let _ = std::fs::remove_dir_all(root);
    }
}

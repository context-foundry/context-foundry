use std::path::Path;
use std::sync::atomic::Ordering;
use std::time::Duration;

use anyhow::Result;
use tokio::sync::mpsc;

use crate::agent::{self, AgentOutputEvent, AgentRole};
use crate::config::Config;
use crate::{patterns, prompts, task};

use super::context::RunContext;
use super::state::LoopEvent;
use super::{AppEvent, PlanningOutcome};

pub(super) async fn spawn_inline_planning_task(
    ctx: RunContext,
    event_tx: mpsc::UnboundedSender<AppEvent>,
    user_intent: Option<String>,
) {
    ctx.ensure_runtime_dirs();
    let pattern_context = load_gap_analysis_pattern_context(&ctx);

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let forward_tx = event_tx.clone();
    let fwd_handle = tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = forward_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let outcome =
        run_gap_analysis_iteration(&ctx, 1, &pattern_context, user_intent.as_deref(), agent_tx)
            .await;

    // Wait for the forwarding task to drain all agent events (including Usage)
    // before signaling completion. Without this, PlanningFinished can arrive
    // before the Usage event, causing per-stage context percentages to stay blank.
    let _ = fwd_handle.await;

    let _ = event_tx.send(AppEvent::PlanningFinished(outcome));
}

pub(super) async fn run_append_tasks(
    ctx: RunContext,
    event_tx: mpsc::UnboundedSender<AppEvent>,
    description: String,
) {
    ctx.ensure_runtime_dirs();

    // Ensure the task queue file exists
    if !ctx.plan_path.exists() {
        if let Err(e) = std::fs::write(&ctx.plan_path, "# Task Queue\n\n") {
            let _ = event_tx.send(AppEvent::PlanningFinished(PlanningOutcome {
                success: false,
                total_tasks: 0,
                pending_tasks: 0,
                completed_tasks: 0,
                new_tasks: 0,
                error: Some(format!("failed to create {}: {}", ctx.tasks_file_name(), e)),
                return_to_startup: true,
            }));
            return;
        }
    }

    let pre_count = task::parse_tasks(&ctx.plan_path)
        .map(|tasks| tasks.len())
        .unwrap_or(0);

    // ─── Coach Pre-Flight (run_mode == "coach") ──────────────
    // When the user has opted into Coach mode, run a Coach turn before
    // the planner appends tasks. Coach reads SPEC.md and writes
    // .buildloop/intake-brief.md; the planner's prompt then prepends
    // the brief so it bases its task decomposition on a clarified
    // outline rather than the raw spec. Idempotent: skipped when
    // intake-brief.md already exists.
    let intake_brief_path = ctx.buildloop_dir.join("intake-brief.md");
    if ctx.config.run_mode == "coach" && !intake_brief_path.exists() {
        run_coach_preflight(&ctx, &event_tx).await;
        // Parity with build.rs Coach block: honor both the atomic shutdown
        // signal AND the .buildloop/stop sentinel file.
        if ctx.is_stop_requested() {
            let _ = event_tx.send(AppEvent::PlanningFinished(PlanningOutcome {
                success: false,
                total_tasks: 0,
                pending_tasks: 0,
                completed_tasks: 0,
                new_tasks: 0,
                error: Some("Cancelled during Coach pre-flight".to_string()),
                return_to_startup: true,
            }));
            return;
        }
    }
    let intake_brief = std::fs::read_to_string(&intake_brief_path)
        .ok()
        .filter(|s| !s.trim().is_empty());

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let forward_tx = event_tx.clone();
    let fwd_handle = tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = forward_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let prompt = prompts::append_tasks_prompt(
        &description,
        &ctx.tasks_file_prompt_path(),
        &ctx.spec_file_prompt_path(),
        intake_brief.as_deref(),
    );
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

    let (success, error) = match result {
        Ok(result) => (result.success, None),
        Err(e) => (false, Some(e.to_string())),
    };

    let outcome = match task::parse_tasks(&ctx.plan_path) {
        Ok(tasks) => PlanningOutcome {
            success,
            total_tasks: tasks.len(),
            pending_tasks: task::count_pending(&tasks),
            completed_tasks: task::count_completed(&tasks),
            new_tasks: tasks.len().saturating_sub(pre_count),
            error,
            return_to_startup: true,
        },
        Err(e) => PlanningOutcome {
            success: false,
            total_tasks: 0,
            pending_tasks: 0,
            completed_tasks: 0,
            new_tasks: 0,
            error: Some(format!(
                "failed to parse {} after appending tasks: {}",
                ctx.tasks_file_name(),
                e
            )),
            return_to_startup: true,
        },
    };

    let _ = fwd_handle.await;
    let _ = event_tx.send(AppEvent::PlanningFinished(outcome));
}

/// Run a single Coach turn before the planner appends tasks. Reads SPEC.md
/// and any existing intake-thread.md, invokes the Coach agent with the
/// configured scout provider/model, and lets the agent write
/// .buildloop/intake-brief.md as a side effect. Errors are best-effort:
/// if Coach fails or times out, the caller proceeds without an intake
/// brief and the planner runs against SPEC.md alone (the same behavior
/// as auto/sprint/review modes).
async fn run_coach_preflight(
    ctx: &RunContext,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
) {
    let _ = event_tx.send(AppEvent::LoopEvent(LoopEvent::Log(
        "Coach mode: running pre-flight intake before task creation".to_string(),
    )));

    let intake_thread_path = ctx.buildloop_dir.join("intake-thread.md");
    let coach_thread = std::fs::read_to_string(&intake_thread_path).unwrap_or_default();
    let coach_spec_content = std::fs::read_to_string(&ctx.spec_path).ok();
    let coach_prompt = prompts::coach_intake_prompt(
        "",
        coach_spec_content.as_deref(),
        &coach_thread,
        1,
    );

    let (coach_tx, mut coach_rx) = mpsc::unbounded_channel();
    let coach_fwd_tx = event_tx.clone();
    let coach_fwd_handle = tokio::spawn(async move {
        while let Some(evt) = coach_rx.recv().await {
            let _ = coach_fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let _ = event_tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Coach,
        Config::display_provider_model(&ctx.config.scout_provider, &ctx.config.scout_model),
    )));

    let coach_result = agent::run_agent(
        &AgentRole::Coach,
        Config::parse_provider(&ctx.config.scout_provider),
        &ctx.config.scout_model,
        &coach_prompt,
        &ctx.project_dir,
        coach_tx,
        &ctx.log_dir,
        None,
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
        Some(&ctx.config),
    )
    .await;

    let _ = coach_fwd_handle.await;
    let success = coach_result.as_ref().map(|r| r.success).unwrap_or(false);
    let _ = event_tx.send(AppEvent::AgentDone(success));
}

pub(super) async fn run_plan_mode(project_dir: &Path, max_iterations: u64) -> Result<()> {
    let ctx = RunContext::new(
        project_dir,
        crate::config::Config::load(project_dir),
        std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
        std::sync::Arc::new(std::sync::Mutex::new(())),
    );

    let shutdown_signal = ctx.shutdown.clone();
    tokio::spawn(async move {
        let _ = tokio::signal::ctrl_c().await;
        shutdown_signal.store(true, Ordering::Release);
    });

    super::commands::ensure_required_providers_available(
        &ctx.config,
        super::commands::ProviderCommandMode::Plan,
    )?;
    if !ctx.plan_path.exists() {
        std::fs::write(&ctx.plan_path, "# Task Queue\n\n")?;
    }
    ctx.ensure_runtime_dirs();

    let iterations = if max_iterations > 0 {
        max_iterations
    } else if ctx.config.planning_iterations > 0 {
        ctx.config.planning_iterations
    } else {
        u64::MAX
    };

    eprintln!("Foundry plan mode — analyzing project for gaps and tasks");
    if iterations < u64::MAX {
        eprintln!("Max iterations: {}", iterations);
    }

    let pattern_context = load_gap_analysis_pattern_context(&ctx);

    for i in 1..=iterations {
        eprintln!(
            "\n=== Planning iteration {}{} ===",
            i,
            if iterations < u64::MAX {
                format!("/{}", iterations)
            } else {
                String::new()
            }
        );

        let stop_file = ctx.stop_file();
        if stop_file.exists() {
            if let Err(e) = std::fs::remove_file(&stop_file) {
                eprintln!(
                    "Warning: failed to remove stop file {}: {}",
                    stop_file.display(),
                    e
                );
            }
            eprintln!("Stop signal received");
            break;
        }

        if ctx.shutdown.load(Ordering::Acquire) {
            eprintln!("Shutdown signal received");
            break;
        }

        let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
        let abort_signal = ctx.shutdown.clone();
        tokio::spawn(async move {
            while let Some(evt) = agent_rx.recv().await {
                match evt {
                    AgentOutputEvent::TextDelta(text) => {
                        use std::io::Write;
                        print!("{}", text);
                        let _ = std::io::stdout().flush();
                    }
                    AgentOutputEvent::Text(text) => println!("{}", text),
                    AgentOutputEvent::ToolUse {
                        tool,
                        input_preview,
                    } => {
                        eprintln!("[tool] {} {}", tool, input_preview);
                    }
                    AgentOutputEvent::ToolResult { output_preview } => {
                        if !output_preview.is_empty() {
                            let first = output_preview.lines().next().unwrap_or("");
                            eprintln!("[result] {}", first);
                        }
                    }
                    AgentOutputEvent::Stderr(line) => eprintln!("[stderr] {}", line),
                    AgentOutputEvent::Result(text) => println!("{}", text),
                    AgentOutputEvent::Error { kind, raw } => {
                        eprintln!("[error/{:?}] {}", kind, raw);
                        // D1.3: circuit breaker for `foundry plan` headless. Signal
                        // the outer iteration loop to break instead of spawning the
                        // next gap-analysis iteration that would hit the same
                        // condition.
                        abort_signal.store(true, Ordering::Release);
                    }
                    AgentOutputEvent::Usage { .. } => {}
                }
            }
        });

        let outcome =
            run_gap_analysis_iteration(&ctx, i as usize, &pattern_context, None, agent_tx).await;

        let status = if outcome.success {
            "completed"
        } else {
            "FAILED"
        };
        eprintln!("--- Planner {} ---", status);
        if let Some(error) = outcome.error.as_ref() {
            eprintln!("[error] {}", error);
        }

        eprintln!(
            "Tasks: {} total ({} new this iteration)",
            outcome.total_tasks, outcome.new_tasks
        );

        if outcome.new_tasks == 0 && outcome.success {
            eprintln!("\nPlan is stable — no new tasks discovered. Stopping.");
            break;
        }

        if i < iterations {
            tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_agents_secs)).await;
        }
    }

    if let Ok(tasks) = task::parse_tasks(&ctx.plan_path) {
        let pending = task::count_pending(&tasks);
        let completed = task::count_completed(&tasks);
        eprintln!(
            "\nPlanning complete. {} tasks total ({} pending, {} completed).",
            tasks.len(),
            pending,
            completed
        );
        eprintln!("Run `foundry run` to start building.");
    }

    Ok(())
}

fn load_gap_analysis_pattern_context(ctx: &RunContext) -> String {
    let patterns_dir = patterns::resolve_patterns_dir(&ctx.config.patterns_dir);
    let all_patterns = patterns::load_patterns(&patterns_dir);
    if all_patterns.is_empty() {
        String::new()
    } else {
        let refs: Vec<&patterns::Pattern> = all_patterns.iter().collect();
        patterns::format_patterns_for_prompt(&refs, "planner", ctx.config.max_pattern_injection)
    }
}

async fn run_gap_analysis_iteration(
    ctx: &RunContext,
    iteration: usize,
    pattern_context: &str,
    user_intent: Option<&str>,
    agent_tx: mpsc::UnboundedSender<AgentOutputEvent>,
) -> PlanningOutcome {
    if !ctx.plan_path.exists() {
        if let Err(e) = std::fs::write(&ctx.plan_path, "# Task Queue\n\n") {
            return PlanningOutcome {
                success: false,
                total_tasks: 0,
                pending_tasks: 0,
                completed_tasks: 0,
                new_tasks: 0,
                error: Some(format!("failed to create {}: {}", ctx.tasks_file_name(), e)),
                return_to_startup: false,
            };
        }
    }

    let pre_count = task::parse_tasks(&ctx.plan_path)
        .map(|tasks| tasks.len())
        .unwrap_or(0);

    let prompt = prompts::gap_analysis_prompt(
        iteration,
        pattern_context,
        user_intent,
        &ctx.spec_file_prompt_path(),
        &ctx.tasks_file_prompt_path(),
    );
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

    let (success, error) = match result {
        Ok(result) => (result.success, None),
        Err(e) => (false, Some(e.to_string())),
    };

    match task::parse_tasks(&ctx.plan_path) {
        Ok(tasks) => PlanningOutcome {
            success,
            total_tasks: tasks.len(),
            pending_tasks: task::count_pending(&tasks),
            completed_tasks: task::count_completed(&tasks),
            new_tasks: tasks.len().saturating_sub(pre_count),
            error,
            return_to_startup: false,
        },
        Err(e) => PlanningOutcome {
            success: false,
            total_tasks: 0,
            pending_tasks: 0,
            completed_tasks: 0,
            new_tasks: 0,
            error: Some(format!(
                "failed to parse {} after planning: {}",
                ctx.tasks_file_name(),
                e
            )),
            return_to_startup: false,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("{}-{}", name, unique));
        std::fs::create_dir_all(&dir).expect("failed to create temp dir");
        dir
    }

    #[test]
    fn gap_analysis_pattern_context_is_empty_without_pattern_files() {
        let dir = temp_dir("foundry-planning-empty-patterns");
        let config = crate::config::Config {
            patterns_dir: dir.display().to_string(),
            ..crate::config::Config::default()
        };
        let ctx = RunContext::new(
            &dir,
            config,
            std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
            std::sync::Arc::new(std::sync::Mutex::new(())),
        );

        assert_eq!(load_gap_analysis_pattern_context(&ctx), "");

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn gap_analysis_pattern_context_includes_loaded_patterns() {
        let dir = temp_dir("foundry-planning-patterns");
        let patterns_dir = dir.join("patterns");
        std::fs::create_dir_all(&patterns_dir).expect("failed to create patterns dir");
        std::fs::write(
            patterns_dir.join("sample.json"),
            r#"[
  {
    "pattern_id": "auth-1",
    "title": "Auth callback mismatch",
    "frequency": 2,
    "keywords": ["auth"],
    "solution": { "planner": "Verify callback URLs." }
  }
]"#,
        )
        .expect("failed to write pattern");

        let config = crate::config::Config {
            patterns_dir: patterns_dir.display().to_string(),
            ..crate::config::Config::default()
        };
        let ctx = RunContext::new(
            &dir,
            config,
            std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
            std::sync::Arc::new(std::sync::Mutex::new(())),
        );
        let context = load_gap_analysis_pattern_context(&ctx);

        assert!(context.contains("Auth callback mismatch"));
        assert!(context.contains("Verify callback URLs."));

        let _ = std::fs::remove_dir_all(dir);
    }
}

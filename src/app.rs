use anyhow::{Context, Result};
use crossterm::event::{self, Event, KeyCode, KeyModifiers};
use futures::StreamExt;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;

mod build;
pub(crate) mod commands;
mod context;
mod contract;
mod planning;
mod review;
mod startup;
mod state;

use self::context::RunContext;
use self::contract::ContractPaths;
use self::startup::{
    enter_home_surface, enter_startup_surface, handle_startup_event, load_pending_task_at,
};
use self::state::{AppEvent, AppendTasksRequest, LoopEvent, PendingTransition, PlanningOutcome};
pub use self::state::{
    AppPhase, AppState, PlanStatus, PlanningState, StartupAction, StartupScenario, StartupState,
};
use crate::agent::{AgentOutputEvent, AgentRole};
use crate::config::Config;
use crate::git;
use crate::orchestrator::{self, OrchestratorConfig, OrchestratorOutcome};
use crate::task;
use crate::tui;
use crate::update;
use crate::utils::{atomic_write_file, truncate_str};

// ─── TUI Mode ────────────────────────────────────────────────

pub async fn run_tui(project_dir: &Path) -> Result<()> {
    let config = Config::load(project_dir);
    commands::ensure_required_providers_available(&config, commands::ProviderCommandMode::Run)?;
    let buildloop_dir = project_dir.join(".buildloop");
    let _ = std::fs::create_dir_all(&buildloop_dir);
    let _ = std::fs::remove_file(buildloop_dir.join("stop"));
    let shutdown = Arc::new(AtomicBool::new(false));
    let mut state = AppState::new(buildloop_dir);
    state.run_mode = config.mode.clone();

    // Git/GH readiness checks (advisory, non-blocking)
    for msg in git::check_git_readiness(project_dir) {
        state.log(msg);
    }
    for msg in ContractPaths::resolve(project_dir).warnings() {
        state.log(msg);
    }

    // Ollama status is checked by the background health checker (every 10s)

    enter_home_surface(project_dir, &mut state, None);

    // Setup terminal
    let mut terminal = tui::setup_terminal()?;

    // Event channels
    let (event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();

    // Spawn tick timer (10 fps)
    let tick_tx = event_tx.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_millis(100));
        loop {
            interval.tick().await;
            if tick_tx.send(AppEvent::Tick).is_err() {
                break;
            }
        }
    });

    // Background Ollama health check (every 10 seconds)
    if config.semantic_match_enabled {
        let ollama_tx = event_tx.clone();
        let ollama_url = config.ollama_url.clone();
        tokio::spawn(async move {
            loop {
                let url = format!("{}/api/tags", ollama_url);
                let connected = tokio::task::spawn_blocking(move || {
                    std::process::Command::new("curl")
                        .args(["-s", "--max-time", "2", &url])
                        .output()
                        .map(|o| o.status.success())
                        .unwrap_or(false)
                })
                .await
                .unwrap_or(false);
                if ollama_tx.send(AppEvent::OllamaStatus(connected)).is_err() {
                    break;
                }
                tokio::time::sleep(Duration::from_secs(10)).await;
            }
        });
    }

    // Spawn keyboard reader (keep handle so we can abort it for external editors)
    let mut terminal_reader_handle = spawn_terminal_event_reader(event_tx.clone());

    // Background update check (non-blocking, delayed)
    let update_tx = event_tx.clone();
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_secs(2)).await;
        let result = tokio::task::spawn_blocking(update::check_for_update).await;
        if let Ok(Ok(Some(version))) = result {
            let _ = update_tx.send(AppEvent::UpdateAvailable(version));
        }
    });

    // Main render loop
    loop {
        // Draw based on phase
        terminal.draw(|frame| match state.phase {
            AppPhase::Startup => {
                if state.show_findings {
                    tui::render_findings(frame, &state);
                } else if state.show_run_view {
                    tui::render(frame, &state, &config);
                } else {
                    tui::render_startup(frame, &state);
                }
            }
            AppPhase::Planning | AppPhase::Running => {
                if state.show_findings {
                    tui::render_findings(frame, &state);
                } else if state.show_patterns {
                    tui::render_patterns(frame, &state, &config);
                } else {
                    tui::render(frame, &state, &config);
                }
            }
        })?;

        // Process events
        match event_rx.recv().await {
            Some(evt) => process_received_event(&mut state, evt, &mut event_rx),
            None => break,
        }

        if let Some(editor_path) =
            apply_pending_transition(project_dir, &config, &event_tx, &mut state, &shutdown)
        {
            // Abort the terminal event reader so it stops competing for input
            terminal_reader_handle.abort();
            tui::restore_terminal(&mut terminal)?;
            let editor_result = launch_external_editor(&editor_path);
            terminal = tui::setup_terminal()?;
            // Respawn the terminal event reader
            terminal_reader_handle = spawn_terminal_event_reader(event_tx.clone());
            let message = match editor_result {
                Ok(()) => {
                    let name = editor_path
                        .file_name()
                        .unwrap_or_default()
                        .to_string_lossy();
                    Some(format!("{} saved. Changes apply on the next run.", name))
                }
                Err(e) => Some(format!("Editor failed: {}", e)),
            };
            enter_home_surface(project_dir, &mut state, message);
        }

        if state.should_quit {
            break;
        }
    }

    // Signal all spawned agent processes to terminate so spawn_blocking
    // threads exit promptly instead of blocking tokio runtime shutdown.
    shutdown.store(true, Ordering::Relaxed);
    terminal_reader_handle.abort();

    // Restore terminal
    tui::restore_terminal(&mut terminal)?;

    println!(
        "\nFoundry stopped. {} tasks completed.",
        state.completed_count
    );
    Ok(())
}

fn spawn_terminal_event_reader(
    event_tx: mpsc::UnboundedSender<AppEvent>,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut reader = crossterm::event::EventStream::new();
        loop {
            if let Some(evt) = reader.next().await {
                let Ok(evt) = evt else {
                    break;
                };
                let app_event = match evt {
                    Event::Key(key) if key.kind == event::KeyEventKind::Press => Some(AppEvent::Key(key)),
                    Event::Key(_) => None, // Ignore Release/Repeat (Windows fires both)
                    Event::Mouse(mouse) => Some(AppEvent::Mouse(mouse)),
                    Event::Paste(text) => Some(AppEvent::Paste(text)),
                    _ => None,
                };
                if let Some(app_event) = app_event {
                    if event_tx.send(app_event).is_err() {
                        break;
                    }
                }
            }
        }
    })
}

fn dispatch_event(state: &mut AppState, event: AppEvent) {
    match state.phase {
        AppPhase::Startup => handle_startup_event(state, event),
        AppPhase::Planning => handle_planning_event(state, event),
        AppPhase::Running => handle_event(state, event),
    }
}

fn process_received_event(
    state: &mut AppState,
    event: AppEvent,
    event_rx: &mut mpsc::UnboundedReceiver<AppEvent>,
) {
    let should_drain = matches!(event, AppEvent::Tick);
    dispatch_event(state, event);

    if !should_drain {
        return;
    }

    // Keep the UI responsive by draining any events that piled up since the last frame.
    while let Ok(evt) = event_rx.try_recv() {
        dispatch_event(state, evt);
        if state.should_quit {
            break;
        }
    }
}

fn apply_pending_transition(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    shutdown: &Arc<AtomicBool>,
) -> Option<std::path::PathBuf> {
    while let Some(transition) = state.pending_transition.take() {
        match transition {
            PendingTransition::StartBuild => {
                if let Err(e) = spawn_build_loop(project_dir, config, event_tx, state, shutdown) {
                    let message = format!("Cannot start loop: {}", e);
                    state.log(message.clone());
                    enter_home_surface(project_dir, state, Some(message));
                } else {
                    state.phase = AppPhase::Running;
                    state.startup = None;
                    state.planning = None;
                }
            }
            PendingTransition::StartPlanning { user_intent, label } => {
                spawn_inline_planning(
                    project_dir,
                    config,
                    event_tx,
                    state,
                    user_intent,
                    label,
                    shutdown,
                );
            }
            PendingTransition::StartDesign { user_intent } => {
                spawn_design_loop(project_dir, config, event_tx, state, user_intent, shutdown);
            }
            PendingTransition::AppendTasks(request) => {
                spawn_append_tasks(project_dir, config, event_tx, state, request, shutdown);
            }
            PendingTransition::OpenExternalEditor { file_path } => {
                return Some(file_path);
            }
            PendingTransition::ShowStartup { message } => {
                enter_startup_surface(project_dir, state, message);
            }
        }
    }
    None
}

fn launch_external_editor(file_path: &Path) -> Result<()> {
    // Ensure the file exists (create with minimal content if new)
    if !file_path.exists() {
        if let Some(parent) = file_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let name = file_path.file_name().unwrap_or_default().to_string_lossy();
        let header = if name.contains("TASKS") || name.contains("IMPL_PLAN") {
            "# Task Queue\n\n"
        } else {
            "# Specification\n\n"
        };
        std::fs::write(file_path, header)?;
    }

    let editor = std::env::var("EDITOR")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .unwrap_or_else(|| "nano".to_string());

    let status = if cfg!(target_os = "windows") {
        std::process::Command::new("cmd")
            .arg("/C")
            .arg(&editor)
            .arg(file_path)
            .status()
            .context("failed to launch editor")?
    } else {
        std::process::Command::new("sh")
            .arg("-c")
            .arg(format!("{} \"$FOUNDRY_TARGET_FILE\"", editor))
            .env("FOUNDRY_TARGET_FILE", file_path)
            .status()
            .context("failed to launch editor")?
    };

    if !status.success() {
        anyhow::bail!("editor exited with status {}", status);
    }

    Ok(())
}

fn spawn_build_loop(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    shutdown: &Arc<AtomicBool>,
) -> Result<()> {
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;
    if !plan_path.exists() {
        anyhow::bail!(
            "{} not found — describe work or scan the project from startup first",
            plan_path.file_name().unwrap_or_default().to_string_lossy()
        );
    }

    let tasks = task::parse_tasks(&plan_path)?;
    state.update_counts(&tasks);
    state.task_queue = tasks.clone();
    state.current_task = None;
    state.next_task_hint = load_pending_task_at(project_dir, 0);
    state.log(format!(
        "Loop started -- {} tasks ({} done, {} pending)",
        state.total_count,
        state.completed_count,
        task::count_pending(&tasks)
    ));

    // Apply runtime mode toggle (user may have toggled auto/review on startup screen)
    let mut loop_config = config.clone();
    loop_config.mode = state.run_mode.clone();

    let run_context = RunContext::new(project_dir, loop_config, shutdown.clone(), state.tasks_file_lock.clone());
    let loop_tx = event_tx.clone();
    tokio::spawn(async move {
        build::build_loop(run_context, loop_tx).await;
    });

    Ok(())
}

fn spawn_inline_planning(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    user_intent: Option<String>,
    label: String,
    shutdown: &Arc<AtomicBool>,
) {
    state.phase = AppPhase::Planning;
    state.startup = None;
    state.planning = Some(PlanningState {
        label: label.clone(),
        user_intent: user_intent.clone(),
        orchestrator_mode: false,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;
    state.set_agent(
        AgentRole::Planner,
        &Config::display_provider_model(&config.planner_provider, &config.planner_model),
    );
    state.log(format!("Planning started — {}", label));

    let run_context = RunContext::new(project_dir, config.clone(), shutdown.clone(), state.tasks_file_lock.clone());
    let event_tx = event_tx.clone();
    tokio::spawn(async move {
        planning::spawn_inline_planning_task(run_context, event_tx, user_intent).await;
    });
}

fn spawn_append_tasks(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    request: AppendTasksRequest,
    shutdown: &Arc<AtomicBool>,
) {
    if !prepare_append_tasks_start(
        project_dir,
        state,
        &request,
        commands::provider_binary_is_available(crate::agent::ModelProvider::Claude),
    ) {
        return;
    }

    // run_append_tasks always uses Claude sonnet regardless of planner config.
    let actual_model = "sonnet";

    state.phase = AppPhase::Planning;
    state.startup = None;
    state.planning = Some(PlanningState {
        label: request.label.clone(),
        user_intent: Some(request.description.clone()),
        orchestrator_mode: false,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;
    state.set_agent(AgentRole::Planner, &Config::display_provider_model("claude", actual_model));
    state.log(format!("Planning started — {}", request.label));

    let run_context = RunContext::new(project_dir, config.clone(), shutdown.clone(), state.tasks_file_lock.clone());
    let event_tx = event_tx.clone();
    tokio::spawn(async move {
        planning::run_append_tasks(run_context, event_tx, request.description).await;
    });
}

fn prepare_append_tasks_start(
    project_dir: &Path,
    state: &mut AppState,
    request: &AppendTasksRequest,
    claude_available: bool,
) -> bool {
    // Describe-work always uses Claude (Codex has no tool restriction support).
    // Fail fast before writing any files if claude CLI is not installed.
    if !claude_available {
        let message =
            "Describe work requires the claude CLI, but it was not found on PATH.".to_string();
        state.log(message.clone());
        enter_startup_surface(project_dir, state, Some(message));
        return false;
    }

    if request.seed_spec_from_description {
        if let Err(e) = seed_spec_from_brief(project_dir, &request.description) {
            let message = format!(
                "Cannot save {}: {}",
                ContractPaths::resolve(project_dir).spec_file_name(),
                e
            );
            state.log(message.clone());
            enter_startup_surface(project_dir, state, Some(message));
            return false;
        }
        state.log(format!(
            "Saved {} from the startup brief",
            ContractPaths::resolve(project_dir).spec_file_name()
        ));
    }

    true
}

pub(super) fn seed_spec_from_brief(project_dir: &Path, description: &str) -> Result<()> {
    let contract_paths = ContractPaths::resolve(project_dir);
    if contract_paths.spec_path.exists() {
        return Ok(());
    }

    if let Some(parent) = contract_paths.spec_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let project_name = project_dir
        .file_name()
        .unwrap_or_default()
        .to_string_lossy();
    let spec = format!("# Specification: {project_name}\n\n## Project Brief\n{description}\n");
    atomic_write_file(&contract_paths.spec_path, spec.as_bytes())?;
    Ok(())
}

fn handle_planning_event(state: &mut AppState, event: AppEvent) {
    match event {
        AppEvent::AgentOutput(output) => {
            handle_agent_output(state, output);
            if let Some(ref mut planning) = state.planning {
                if planning.orchestrator_mode {
                    if let Some(last_line) = state.agent_output.last() {
                        if let Some(rest) = last_line.strip_prefix("[orchestrator] Iteration ") {
                            if let Some(slash_pos) = rest.find('/') {
                                if let Ok(iter_num) = rest[..slash_pos].parse::<usize>() {
                                    planning.orchestrator_iteration = iter_num;
                                }
                            }
                            if rest.contains("proposer") {
                                planning.orchestrator_role_label =
                                    Some("Proposing".to_string());
                                if let Some(paren_open) = rest.find('(') {
                                    if let Some(paren_close) = rest.find(')') {
                                        if paren_close > paren_open + 1 {
                                            planning.orchestrator_role_model =
                                                Some(rest[paren_open + 1..paren_close].to_string());
                                        }
                                    }
                                }
                            }
                        }
                        if let Some(rest) = last_line.strip_prefix("[orchestrator] Reviewing with ") {
                            planning.orchestrator_role_label = Some("Reviewing".to_string());
                            let model_str = rest.trim_end_matches("...");
                            if !model_str.is_empty() {
                                planning.orchestrator_role_model = Some(model_str.to_string());
                            }
                        }
                        if let Some(rest) =
                            last_line.strip_prefix("[orchestrator] Review: ")
                        {
                            if let Some(paren_start) = rest.find('(') {
                                let after_paren = &rest[paren_start + 1..];
                                if let Some(space) = after_paren.find(' ') {
                                    if let Ok(count) =
                                        after_paren[..space].parse::<usize>()
                                    {
                                        planning.orchestrator_finding_count = count;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        AppEvent::AgentDone(success) => handle_agent_done(state, success),
        AppEvent::PlanningFinished(outcome) => apply_planning_outcome(state, outcome),
        AppEvent::OrchestratorFinished(outcome) => apply_orchestrator_outcome(state, outcome),
        AppEvent::Key(key) => handle_planning_key(state, key),
        AppEvent::Mouse(_) | AppEvent::Paste(_) => {}
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
        AppEvent::OllamaStatus(connected) => {
            state.last_pattern_match_mode = Some(
                if connected { "semantic" } else { "keyword-only" }.to_string(),
            );
        }
        AppEvent::LoopEvent(_) => {}
    }
}

fn handle_planning_key(state: &mut AppState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Char('q') | KeyCode::Esc => {
            state.should_quit = true;
        }
        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.should_quit = true;
        }
        KeyCode::Char('f') => {
            if state.last_orchestrator_outcome.is_some() {
                state.show_findings = !state.show_findings;
                state.findings_scroll = 0;
            }
        }
        KeyCode::Char('p') => {
            state.show_patterns = !state.show_patterns;
        }
        KeyCode::Up => {
            if state.show_findings {
                state.findings_scroll = state.findings_scroll.saturating_sub(3);
            } else if state.show_patterns {
                state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
            } else {
                // Cap scroll at total content length so we can't scroll into nothingness
                let max = state.agent_output.len().saturating_sub(1);
                state.scroll_offset = state.scroll_offset.saturating_add(3).min(max);
            }
        }
        KeyCode::Down => {
            if state.show_findings {
                state.findings_scroll = state.findings_scroll.saturating_add(3);
            } else if state.show_patterns {
                state.patterns_scroll = state.patterns_scroll.saturating_add(3);
            } else {
                state.scroll_offset = state.scroll_offset.saturating_sub(3);
            }
        }
        KeyCode::PageUp => {
            let max = state.task_queue.len().saturating_sub(1);
            state.task_queue_scroll = state.task_queue_scroll.saturating_add(3).min(max);
        }
        KeyCode::PageDown => {
            state.task_queue_scroll = state.task_queue_scroll.saturating_sub(3);
        }
        _ => {}
    }
}

fn handle_event(state: &mut AppState, event: AppEvent) {
    match event {
        AppEvent::AgentOutput(output) => handle_agent_output(state, output),
        AppEvent::AgentDone(success) => handle_agent_done(state, success),
        AppEvent::LoopEvent(le) => match le {
            LoopEvent::TaskStarted(task) => {
                state.log(format!("Task {} started", task.id));
                state.current_task = Some(task);
                state.task_start = Some(chrono::Utc::now());
                state.task_stages_seen.clear();
                state.clear_agent();
            }
            LoopEvent::AgentStarted(role, model) => {
                state.log(format!("{} spawned ({})", role, model));
                if !state.task_stages_seen.contains(&role) {
                    state.task_stages_seen.push(role.clone());
                }
                state.set_agent(role, &model);
            }
            LoopEvent::TaskCompleted(id, success) => {
                let status = if success { "done" } else { "WIP" };
                state.log(format!("Task {} — {}", id, status));
                // Git commit counts are refreshed from git history when
                // returning to startup -- no need to increment here.
                // Save stages into history (review result may arrive separately)
                if !state.task_history.contains_key(&id) {
                    state.task_history_order.push(id.clone());
                }
                let history = state.task_history.entry(id.clone()).or_default();
                history.stages_seen = state.task_stages_seen.clone();
                // If task succeeded and no TaskReviewResult arrived yet,
                // mark as passed so the icon shows green (not default false)
                if success && history.fix_passes == 0 {
                    history.passed_review = true;
                }
                state.cap_task_history();
                state.current_task = None;
                state.task_start = None;
                state.task_stages_seen.clear();
                state.clear_agent();
            }
            LoopEvent::NextTaskUpdated(next_task) => {
                state.next_task_hint = next_task;
            }
            LoopEvent::DiscoveryStarted(round) => {
                state.is_discovering = true;
                state.discovery_round = round;
                state.log(format!("Discovery round {} started", round));
                state.clear_agent();
            }
            LoopEvent::DiscoveryCompleted(new_count) => {
                state.is_discovering = false;
                state.log(format!("Discovery found {} new tasks", new_count));
            }
            LoopEvent::Log(ref msg) => {
                // Track patterns learned from "Merged patterns: N new added" messages
                if msg.starts_with("Merged patterns:") {
                    if let Some(count_str) = msg
                        .strip_prefix("Merged patterns: ")
                        .and_then(|s| s.split_whitespace().next())
                    {
                        if let Ok(n) = count_str.parse::<usize>() {
                            state.session_patterns_learned += n;
                        }
                    }
                }
                // Track review findings from "Review pass N/2: verdict=X, N high, N medium findings"
                if msg.starts_with("Review pass ") {
                    if let Some(rest) = msg.split("verdict=").nth(1) {
                        // Parse "FAIL, 2 high, 1 medium findings"
                        for part in rest.split(',') {
                            let trimmed = part.trim();
                            if trimmed.ends_with("high") {
                                if let Ok(n) = trimmed.split_whitespace().next().unwrap_or("0").parse::<usize>() {
                                    state.session_review_high += n;
                                }
                            } else if trimmed.ends_with("medium") {
                                if let Ok(n) = trimmed.split_whitespace().next().unwrap_or("0").parse::<usize>() {
                                    state.session_review_medium += n;
                                }
                            }
                        }
                    }
                }
                // Track pattern matching mode for dashboard
                if msg.starts_with("Pattern matching (") {
                    if let Some(mode) = msg
                        .strip_prefix("Pattern matching (")
                        .and_then(|s| s.split(')').next())
                    {
                        state.last_pattern_match_mode = Some(mode.to_string());
                    }
                }
                state.log(msg.clone());
            }
            LoopEvent::BackgroundLog(ref msg) => {
                // Track patterns learned from "Merged patterns: N new added" messages
                if msg.starts_with("Merged patterns:") {
                    if let Some(count_str) = msg
                        .strip_prefix("Merged patterns: ")
                        .and_then(|s| s.split_whitespace().next())
                    {
                        if let Ok(n) = count_str.parse::<usize>() {
                            state.session_patterns_learned += n;
                        }
                    }
                }
                state.log(msg.clone());
            }
            LoopEvent::CountsUpdated(completed, total) => {
                state.completed_count = completed;
                state.total_count = total;
            }
            LoopEvent::QueueUpdated(tasks) => {
                state.task_queue = tasks;
            }
            LoopEvent::TaskReviewResult {
                task_id,
                fix_passes,
                passed,
            } => {
                if !state.task_history.contains_key(&task_id) {
                    state.task_history_order.push(task_id.clone());
                }
                let history = state.task_history.entry(task_id).or_default();
                history.fix_passes = fix_passes;
                history.passed_review = passed;
                state.cap_task_history();
            }
            LoopEvent::Finished => {
                state.log("All work complete — loop finished");
                let project_dir = state.buildloop_dir.parent().unwrap_or(std::path::Path::new(".")).to_path_buf();
                enter_home_surface(&project_dir, state, Some("Build loop finished.".to_string()));
            }
        },
        AppEvent::Key(key) => {
            if state.inject_input.is_some() {
                handle_inject_key(state, key);
            } else {
                match key.code {
                    KeyCode::Char('q') => {
                        if state.stop_after_task {
                            // Cancel stop -- resume running
                            state.stop_after_task = false;
                            let _ = std::fs::remove_file(state.buildloop_dir.join("stop"));
                            state.log("Stop cancelled -- resuming build");
                        } else {
                            // Request stop after current task
                            state.stop_after_task = true;
                            let _ = std::fs::create_dir_all(&state.buildloop_dir);
                            let _ = std::fs::write(state.buildloop_dir.join("stop"), "");
                            state.log("Stopping after current task (q again to cancel, Ctrl+C to force quit)");
                        }
                    }
                    KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                        if state.stop_after_task {
                            // Second Ctrl+C: quit immediately
                            let _ = std::fs::remove_file(state.buildloop_dir.join("stop"));
                            state.should_quit = true;
                        } else {
                            state.stop_after_task = true;
                            let _ = std::fs::create_dir_all(&state.buildloop_dir);
                            let _ = std::fs::write(state.buildloop_dir.join("stop"), "");
                            state.log(
                                "Will stop after current task completes (Ctrl+C again to force quit)",
                            );
                        }
                    }
                    KeyCode::Char('f') => {
                        if state.last_orchestrator_outcome.is_some() {
                            state.show_findings = !state.show_findings;
                            state.findings_scroll = 0;
                        }
                    }
                    KeyCode::Char('p') => {
                        if state.show_patterns {
                            // Return to whatever view was active before patterns
                            state.show_patterns = false;
                        } else {
                            state.show_patterns = true;
                            // p toggles the patterns overlay on/off
                        }
                    }
                    KeyCode::Char('i') => {
                        state.inject_input = Some(String::new());
                    }
                    KeyCode::Up => {
                        if state.show_findings {
                            state.findings_scroll = state.findings_scroll.saturating_sub(3);
                        } else if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
                        } else {
                            let max = state.agent_output.len().saturating_sub(1);
                            state.scroll_offset = state.scroll_offset.saturating_add(3).min(max);
                        }
                    }
                    KeyCode::Down => {
                        if state.show_findings {
                            state.findings_scroll = state.findings_scroll.saturating_add(3);
                        } else if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_add(3);
                        } else {
                            state.scroll_offset = state.scroll_offset.saturating_sub(3);
                        }
                    }
                    KeyCode::PageUp => {
                        let max = state.task_queue.len().saturating_sub(1);
                        state.task_queue_scroll = state.task_queue_scroll.saturating_add(3).min(max);
                    }
                    KeyCode::PageDown => {
                        state.task_queue_scroll = state.task_queue_scroll.saturating_sub(3);
                    }
                    _ => {}
                }
            }
        }
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
        AppEvent::OllamaStatus(connected) => {
            state.last_pattern_match_mode = Some(
                if connected { "semantic" } else { "keyword-only" }.to_string(),
            );
        }
        AppEvent::Mouse(mouse) => {
            use crossterm::event::{MouseButton, MouseEventKind};
            match mouse.kind {
                MouseEventKind::ScrollUp => {
                    state.task_queue_scroll = state.task_queue_scroll.saturating_add(3);
                }
                MouseEventKind::ScrollDown => {
                    state.task_queue_scroll = state.task_queue_scroll.saturating_sub(3);
                }
                MouseEventKind::Down(MouseButton::Left) => {
                    // Clicks in running mode are no-ops for now
                }
                _ => {}
            }
        }
        AppEvent::Paste(text) => {
            if let Some(ref mut buf) = state.inject_input {
                buf.push_str(&text);
            }
        }
        AppEvent::PlanningFinished(outcome) => {
            let message = if let Some(error) = outcome.error {
                format!("Ignoring late planning result while running: {}", error)
            } else {
                format!(
                    "Ignoring late planning result while running ({} total tasks, {} pending)",
                    outcome.total_tasks, outcome.pending_tasks
                )
            };
            state.log(message);
        }
        AppEvent::OrchestratorFinished(_) => {
            state.log("Ignoring late orchestrator result while running");
        }
    }
}

fn handle_inject_key(state: &mut AppState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Char(c) => {
            if let Some(ref mut buf) = state.inject_input {
                buf.push(c);
            }
        }
        KeyCode::Backspace => {
            if let Some(ref mut buf) = state.inject_input {
                buf.pop();
            }
        }
        KeyCode::Esc => {
            state.inject_input = None;
        }
        KeyCode::Enter => {
            let text = state.inject_input.take().unwrap_or_default();
            let text = text.trim().to_string();
            if text.is_empty() {
                return;
            }
            // "!" prefix = run next (insert after current task)
            let (run_next, description) = if let Some(rest) = text.strip_prefix('!') {
                (true, rest.trim().to_string())
            } else {
                (false, text)
            };
            if description.is_empty() {
                return;
            }
            commit_inject_task(state, &description, run_next);
        }
        _ => {}
    }
}

fn commit_inject_task(state: &mut AppState, description: &str, run_next: bool) {
    let lock = state.tasks_file_lock.clone();
    let _lock = lock.lock().unwrap_or_else(|e| e.into_inner());
    let project_dir = state.buildloop_dir.parent().unwrap_or(Path::new("."));
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;

    // Read existing plan to find highest H-group number (H{N}.{M} format).
    // The task parser regex requires `[A-Za-z]?\d+\.\d+:` so we must use
    // dot-separated IDs like H1.1, H2.1, etc.
    let content = std::fs::read_to_string(&plan_path).unwrap_or_default();
    let mut max_h_group: usize = 0;
    for line in content.lines() {
        let trimmed = line.trim_start();
        let rest = trimmed
            .strip_prefix("- [ ] H")
            .or_else(|| trimmed.strip_prefix("- [x] H"));
        if let Some(rest) = rest {
            // Parse the group number before the dot (e.g. "3" from "H3.1: desc")
            if let Some(num_str) = rest.split('.').next() {
                if let Ok(n) = num_str.trim().parse::<usize>() {
                    max_h_group = max_h_group.max(n);
                }
            }
        }
    }

    let next_group = max_h_group + 1;
    let task_id = format!("H{}.1", next_group);
    let new_task_line = format!("- [ ] {}: {}", task_id, description);

    if run_next {
        // Insert right after the current task's line in the file.
        // Find the first unchecked task line and insert before it.
        let current_line = state
            .current_task
            .as_ref()
            .map(|t| t.line_number)
            .unwrap_or(0);
        let lines: Vec<&str> = content.lines().collect();
        let mut insert_at = None;

        // Find the first pending task after the current one
        for (i, line) in lines.iter().enumerate() {
            let trimmed = line.trim_start();
            if trimmed.starts_with("- [ ] ") && i + 1 > current_line {
                insert_at = Some(i);
                break;
            }
        }

        let mut new_content = String::new();
        match insert_at {
            Some(pos) => {
                for (i, line) in lines.iter().enumerate() {
                    if i == pos {
                        new_content.push_str(&new_task_line);
                        new_content.push('\n');
                    }
                    new_content.push_str(line);
                    new_content.push('\n');
                }
            }
            None => {
                // No pending task found after current -- append
                new_content = content.clone();
                if !new_content.ends_with('\n') {
                    new_content.push('\n');
                }
                new_content.push_str(&new_task_line);
                new_content.push('\n');
            }
        }

        if let Err(e) = atomic_write_file(&plan_path, new_content.as_bytes()) {
            state.log(format!("Failed to inject task: {}", e));
            return;
        }
    } else {
        // Append to end (default) -- read + atomic write for crash safety
        let mut full_content = content.clone();
        if !full_content.ends_with('\n') {
            full_content.push('\n');
        }
        full_content.push_str(&new_task_line);
        full_content.push('\n');
        if let Err(e) = atomic_write_file(&plan_path, full_content.as_bytes()) {
            state.log(format!("Failed to inject task: {}", e));
            return;
        }
    }

    let placement = if run_next { " (run next)" } else { "" };
    state.agent_output.push(format!(
        "[injected] {}: {}{}",
        task_id, description, placement
    ));
    state.log(format!("Injected task {}{}", task_id, placement));
    state.total_count += 1;
}

const AGENT_OUTPUT_CAP: usize = 2000;

fn handle_agent_output(state: &mut AppState, output: AgentOutputEvent) {
    state.events_received += 1;
    match output {
        AgentOutputEvent::Text(text) => {
            state.agent_output.push(text);
        }
        AgentOutputEvent::ToolUse {
            tool,
            input_preview,
        } => {
            let msg = if input_preview.is_empty() {
                format!("[tool] {}", tool)
            } else {
                format!("[tool] {} — {}", tool, input_preview)
            };
            state.agent_output.push(msg);
        }
        AgentOutputEvent::ToolResult { output_preview } => {
            if !output_preview.is_empty() {
                let first_line = output_preview.lines().next().unwrap_or("");
                let display = if first_line.len() > 100 {
                    format!("[result] {}...", truncate_str(first_line, 100))
                } else {
                    format!("[result] {}", first_line)
                };
                state.agent_output.push(display);
            }
        }
        AgentOutputEvent::Stderr(line) => {
            state.agent_output.push(format!("[stderr] {}", line));
        }
        AgentOutputEvent::Result(text) => {
            state.agent_output.push(String::new());
            for line in text.lines().take(10) {
                state.agent_output.push(line.to_string());
            }
        }
        AgentOutputEvent::Usage {
            cost_usd,
            input_tokens,
            output_tokens,
            context_window,
        } => {
            state.session_cost_usd += cost_usd;
            let total_tokens = input_tokens + output_tokens;
            if context_window > 0 {
                let pct = ((total_tokens as f64 / context_window as f64) * 100.0).min(100.0) as u8;
                state.agent_context_pct = Some(pct);
            }
        }
    }
    if state.agent_output.len() > AGENT_OUTPUT_CAP {
        let excess = state.agent_output.len() - AGENT_OUTPUT_CAP;
        state.agent_output.drain(..excess);
        if state.scroll_offset >= excess {
            state.scroll_offset -= excess;
        } else {
            state.scroll_offset = 0;
        }
    }
}

fn handle_agent_done(state: &mut AppState, success: bool) {
    if let Some((ref role, _)) = state.current_agent {
        let status = if success { "completed" } else { "FAILED" };
        state.log(format!("{} {}", role, status));
    }
}

fn apply_planning_outcome(state: &mut AppState, outcome: PlanningOutcome) {
    state.clear_agent();
    state.planning = None;
    state.total_count = outcome.total_tasks;
    state.completed_count = outcome.completed_tasks;

    if let Some(error) = outcome.error {
        let message = format!("Planning failed: {}", error);
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
        return;
    }

    if !outcome.success {
        let message = "Planning failed — review planner output and try again".to_string();
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
        return;
    }

    if outcome.pending_tasks > 0 && outcome.return_to_startup {
        let message = format!(
            "Added {} task(s) — {} pending. Review the queue, then Continue when ready.",
            outcome.new_tasks, outcome.pending_tasks
        );
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
    } else if outcome.pending_tasks > 0 {
        state.log(format!(
            "Queue ready — {} total tasks ({} new, {} pending)",
            outcome.total_tasks, outcome.new_tasks, outcome.pending_tasks
        ));
        state.pending_transition = Some(PendingTransition::StartBuild);
    } else {
        let message = if outcome.total_tasks == 0 {
            "Planning complete — no tasks found".to_string()
        } else {
            "Planning complete — no pending tasks found".to_string()
        };
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
    }
}

fn spawn_design_loop(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    user_intent: String,
    shutdown: &Arc<AtomicBool>,
) {
    let orch_config = OrchestratorConfig::from_config(config);
    let label = format!("Design: {}", truncate_str(&user_intent, 48));
    state.phase = AppPhase::Planning;
    state.startup = None;
    state.planning = Some(PlanningState {
        label: label.clone(),
        user_intent: Some(user_intent.clone()),
        orchestrator_mode: true,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: orch_config.max_iterations,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;
    state.set_agent(
        AgentRole::Planner,
        &format!("{} {}", orch_config.proposer_provider, {
            let m = orch_config.proposer_model.trim();
            let mut chars = m.chars();
            match chars.next() {
                Some(c) => format!("{}{}", c.to_uppercase(), chars.as_str()),
                None => String::new(),
            }
        }),
    );
    state.log(format!("Design started — {}", label));

    let project_dir = project_dir.to_path_buf();
    let event_tx = event_tx.clone();
    let user_intent_clone = user_intent;
    let shutdown_clone = Some(shutdown.clone());

    // Create a channel to forward agent output events from the orchestrator to the TUI
    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel::<AgentOutputEvent>();
    let forward_tx = event_tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = forward_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    tokio::spawn(async move {
        let buildloop_dir = project_dir.join(".buildloop");
        let log_dir = buildloop_dir.join("logs");
        let _ = std::fs::create_dir_all(&log_dir);

        let tx = event_tx.clone();
        let result = orchestrator::orchestrate(
            &user_intent_clone,
            &orch_config,
            &project_dir,
            &log_dir,
            |msg| {
                let _ = tx.send(AppEvent::AgentOutput(AgentOutputEvent::Text(format!(
                    "[orchestrator] {}",
                    msg
                ))));
            },
            Some(agent_tx),
            shutdown_clone,
        )
        .await;

        match result {
            Ok(outcome) => {
                let _ = orchestrator::write_orchestrator_output(&buildloop_dir, &outcome);
                let _ = event_tx.send(AppEvent::OrchestratorFinished(outcome));
            }
            Err(e) => {
                let fallback = OrchestratorOutcome {
                    artifact: orchestrator::ProposerOutput {
                        artifact_type: "analysis".to_string(),
                        artifact_text: format!("Orchestrator error: {}", e),
                        rationale: String::new(),
                        claims: Vec::new(),
                    },
                    final_review: orchestrator::ReviewerOutput {
                        status: "findings".to_string(),
                        findings: Vec::new(),
                        validated: Vec::new(),
                    },
                    iterations: 0,
                    accepted: false,
                };
                let _ = event_tx.send(AppEvent::OrchestratorFinished(fallback));
            }
        }
    });
}

fn apply_orchestrator_outcome(state: &mut AppState, outcome: OrchestratorOutcome) {
    state.clear_agent();
    state.planning = None;

    let has_unresolved = !outcome.accepted && !outcome.final_review.findings.is_empty();

    let message = if outcome.accepted {
        format!(
            "Design accepted after {} iteration(s). Output in .buildloop/orchestrator-output.md",
            outcome.iterations
        )
    } else {
        format!(
            "Design completed with unresolved findings after {} iteration(s). Output in .buildloop/orchestrator-output.md",
            outcome.iterations
        )
    };
    state.log(message.clone());

    state.last_orchestrator_outcome = Some(outcome);

    if has_unresolved {
        state.show_findings = true;
        state.findings_scroll = 0;
    }

    state.pending_transition = Some(PendingTransition::ShowStartup {
        message: Some(message),
    });
}

// ─── Plan Mode (gap analysis, no building) ───────────────────

pub async fn run_plan_mode(project_dir: &Path, max_iterations: u64) -> Result<()> {
    planning::run_plan_mode(project_dir, max_iterations).await
}

// ─── Headless Mode ───────────────────────────────────────────

pub async fn run_headless(project_dir: &Path) -> Result<()> {
    commands::run_headless(project_dir).await
}

// ─── Status & Tasks Commands ─────────────────────────────────

pub fn show_status(project_dir: &Path) -> Result<()> {
    commands::show_status(project_dir)
}

pub fn show_tasks(project_dir: &Path) -> Result<()> {
    commands::show_tasks(project_dir)
}

#[cfg(test)]
mod tests;

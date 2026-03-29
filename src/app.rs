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
    classify_plan_status, detect_startup_scenario, enter_home_surface, enter_startup_surface,
    handle_startup_event, load_pending_task_at,
};
pub use self::state::FileEntry;
use self::state::{AppEvent, AppendTasksRequest, LoopEvent, PendingTransition, PlanningOutcome};
pub use self::state::{
    AppPhase, AppState, DualSelection, ExtensionDisplayInfo, PatternEventKind, PlanStatus,
    PlanningState, StartupAction, StartupScenario, StartupState, TuiPane,
};
use crate::agent::{AgentOutputEvent, AgentRole};
use crate::config::Config;
use crate::git;
use crate::orchestrator::{self, OrchestratorConfig, OrchestratorOutcome};
use crate::task;
use crate::tmux;
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
    state.run_mode = config.run_mode.clone();
    state.builder_model_specs = config.builder_models.clone();
    if config.builder_models.len() >= 2 {
        state.dual_selection = state::DualSelection::from_str(&config.dual_selection);
    }
    if let Some(tc) = config.truecolor {
        crate::tui::theme::set_truecolor_override(tc);
    }
    state.tui_theme = crate::tui::theme::from_name(&config.theme);

    // Sandbox detection
    let sandbox_cfg = config.sandbox_config();
    let sandbox_status = sandbox_cfg.status();
    state.sandbox_active = sandbox_cfg.is_active();
    state.sandbox_enabled = config.sandbox;
    state.sandbox_status_label = format!("{}", sandbox_status);
    match sandbox_status {
        crate::sandbox::SandboxStatus::Active => {
            sandbox_cfg.ensure_credentials_for_container();
            state.log(format!(
                "Sandbox active: image={}, mounts={}",
                sandbox_cfg.image,
                1 + sandbox_cfg.extra_mounts.len()
            ));
        }
        crate::sandbox::SandboxStatus::DockerNotFound => {
            state.log("Warning: sandbox enabled but Docker not found; agents will run unsandboxed".to_string());
        }
        crate::sandbox::SandboxStatus::ImageNotFound => {
            state.log(format!(
                "Warning: sandbox image '{}' not found; agents will run unsandboxed. Run: docker/build-sandbox.sh",
                sandbox_cfg.image
            ));
        }
        crate::sandbox::SandboxStatus::Disabled => {
            state.log("Warning: sandbox disabled by config override -- agents will run unsandboxed".to_string());
        }
    }

    // Tmux backend validation and stale session cleanup
    if config.agent_backend == "tmux" {
        if tmux::tmux_binary_available() {
            let stale = tmux::cleanup_stale_sessions(&config.tmux_session_prefix);
            for name in &stale {
                state.log(format!("Cleaned up stale tmux session: {}", name));
            }
        } else {
            state.log("Warning: tmux backend configured but tmux binary not found; falling back to PTY".to_string());
        }
    }

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
                } else if state.show_running_explorer && matches!(state.phase, AppPhase::Running) {
                    tui::render_running_explorer(frame, &state, &config);
                } else {
                    tui::render(frame, &state, &config);
                }
            }
        })?;

        // Process events
        match event_rx.recv().await {
            Some(evt) => process_received_event(&mut state, evt, &mut event_rx, &config),
            None => break,
        }

        // When user requests stop, kill the running agent immediately.
        // Discovery and other read-only agents have nothing critical to preserve.
        if state.stop_after_task {
            shutdown.store(true, Ordering::Relaxed);
        } else {
            shutdown.store(false, Ordering::Relaxed);
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
                    Event::Key(key) if key.kind == event::KeyEventKind::Press => {
                        Some(AppEvent::Key(key))
                    }
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

fn dispatch_event(state: &mut AppState, event: AppEvent, config: &Config) {
    match state.phase {
        AppPhase::Startup => handle_startup_event(state, event),
        AppPhase::Planning => handle_planning_event(state, event, config),
        AppPhase::Running => handle_event(state, event, config),
    }
}

fn process_received_event(
    state: &mut AppState,
    event: AppEvent,
    event_rx: &mut mpsc::UnboundedReceiver<AppEvent>,
    config: &Config,
) {
    let should_drain = matches!(event, AppEvent::Tick);
    dispatch_event(state, event, config);

    if !should_drain {
        return;
    }

    // Keep the UI responsive by draining any events that piled up since the last frame.
    while let Ok(evt) = event_rx.try_recv() {
        dispatch_event(state, evt, config);
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
                    state.focused_pane = state::TuiPane::AgentOutput;
                    state.show_running_explorer = false;
                    state.running_explorer = None;
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
                state.focused_pane = state::TuiPane::Explorer;
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

    // Apply runtime toggles (user may have toggled mode/dual-build on startup screen)
    let mut loop_config = config.clone();
    loop_config.run_mode = state.run_mode.clone();
    loop_config.dual_selection = state.dual_selection.as_str().to_string();
    loop_config.builder_models = state.builder_model_specs.clone();

    let review_gate = Arc::new(AtomicBool::new(false));
    state.review_gate = Some(review_gate.clone());
    state.awaiting_review = false;
    state.awaiting_pr = None;
    state.pr_poll_last_check = None;

    let mut run_context = RunContext::new(
        project_dir,
        loop_config,
        shutdown.clone(),
        state.tasks_file_lock.clone(),
        review_gate,
    );
    run_context.session_cost_millicents = state.session_cost_millicents.clone();
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

    let run_context = RunContext::new(
        project_dir,
        config.clone(),
        shutdown.clone(),
        state.tasks_file_lock.clone(),
        Arc::new(AtomicBool::new(false)),
    );
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

    let run_context = RunContext::new(
        project_dir,
        config.clone(),
        shutdown.clone(),
        state.tasks_file_lock.clone(),
        Arc::new(AtomicBool::new(false)),
    );
    let event_tx = event_tx.clone();
    tokio::spawn(async move {
        planning::run_append_tasks(run_context, event_tx, request.description).await;
    });
}

fn prepare_append_tasks_start(
    project_dir: &Path,
    state: &mut AppState,
    request: &AppendTasksRequest,
    _claude_available: bool,
) -> bool {
    // Task append uses an LLM to expand descriptions but works without
    // claude CLI (falls back gracefully). Check removed for simplicity.

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

fn handle_planning_event(state: &mut AppState, event: AppEvent, config: &Config) {
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
                                planning.orchestrator_role_label = Some("Proposing".to_string());
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
                        if let Some(rest) = last_line.strip_prefix("[orchestrator] Reviewing with ")
                        {
                            planning.orchestrator_role_label = Some("Reviewing".to_string());
                            let model_str = rest.trim_end_matches("...");
                            if !model_str.is_empty() {
                                planning.orchestrator_role_model = Some(model_str.to_string());
                            }
                        }
                        if let Some(rest) = last_line.strip_prefix("[orchestrator] Review: ") {
                            if let Some(paren_start) = rest.find('(') {
                                let after_paren = &rest[paren_start + 1..];
                                if let Some(space) = after_paren.find(' ') {
                                    if let Ok(count) = after_paren[..space].parse::<usize>() {
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

        AppEvent::DualPipelineEvent(idx, inner) => {
            handle_dual_pipeline_event(state, idx, *inner, config)
        }
        AppEvent::PlanningFinished(outcome) => apply_planning_outcome(state, outcome),
        AppEvent::OrchestratorFinished(outcome) => apply_orchestrator_outcome(state, outcome),
        AppEvent::Key(key) => handle_planning_key(state, key, config),
        AppEvent::Mouse(_) | AppEvent::Paste(_) => {}
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
        AppEvent::OllamaStatus(connected) => {
            state.last_pattern_match_mode = Some(
                if connected {
                    "semantic"
                } else {
                    "keyword-only"
                }
                .to_string(),
            );
        }
        AppEvent::LoopEvent(_) => {}
    }
}

fn handle_planning_key(state: &mut AppState, key: event::KeyEvent, config: &Config) {
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
            if state.show_patterns {
                refresh_patterns_cache(state, config);
            }
        }
        // Sandbox toggle removed -- config-only override for implementers.
        KeyCode::Char('s') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.log("Sandbox toggle disabled -- override via .foundry.json only".to_string());
        }
        KeyCode::Char('t') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
            state.tui_theme = new_theme;
            state.log(format!("Theme: {}", name));
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

fn handle_event(state: &mut AppState, event: AppEvent, config: &Config) {
    match event {
        AppEvent::AgentOutput(output) => handle_agent_output(state, output),

        AppEvent::DualPipelineEvent(idx, inner) => {
            handle_dual_pipeline_event(state, idx, *inner, config)
        }
        AppEvent::AgentDone(success) => handle_agent_done(state, success),
        AppEvent::LoopEvent(le) => match le {
            LoopEvent::TaskStarted(task) => {
                state.log(format!("Task {} started", task.id));
                state.current_task = Some(task);
                state.task_start = Some(chrono::Utc::now());
                state.task_stages_seen.clear();
                state.active_pattern_keywords.clear();
                state.spid_context_pcts = [None; 4];
                state.clear_agent();
            }
            LoopEvent::AgentStarted(role, model) => {
                state.log(format!("{} spawned ({})", role, model));
                if !state.task_stages_seen.contains(&role) {
                    state.task_stages_seen.push(role.clone());
                }
                state.set_agent(role, &model);
            }
            LoopEvent::DualBuildStarted { models } => {
                state.dual_build = state::DualBuildState {
                    active: true,
                    streams: [Vec::new(), Vec::new()],
                    event_counts: [0, 0],
                    models: models.clone(),
                    tab: 0,
                    cost_usd: [0.0, 0.0],
                    input_tokens: [0, 0],
                    output_tokens: [0, 0],
                    context_pcts: [[None; 4]; 2],
                    finished: [false, false],
                    stages: [None, None],
                    stage_models: [String::new(), String::new()],
                };
                state.log(format!(
                    "Dual pipeline started: {} vs {}",
                    models[0], models[1]
                ));
            }
            LoopEvent::DualBuildStreamDone(idx, success) => {
                if idx < 2 {
                    state.dual_build.finished[idx] = true;
                    let status = if success { "completed" } else { "failed" };
                    state.log(format!(
                        "Pipeline {} ({}): {}",
                        idx + 1,
                        state.dual_build.models[idx],
                        status
                    ));
                }
            }
            LoopEvent::TaskCompleted(id, success) => {
                state.reset_dual_build();
                let status = if success { "done" } else { "WIP" };
                if success {
                    state.session_feat_commits += 1;
                } else {
                    state.session_wip_commits += 1;
                }
                state.log(format!("Task {} — {}", id, status));
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
                state.ship_active = false;
            }
            LoopEvent::TaskReport { .. } => {
                // TaskReport is consumed by headless mode only; TUI ignores it.
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
            LoopEvent::ExtensionKeywordsLoaded { ref keywords } => {
                state.extension_keywords = keywords.clone();
            }
            LoopEvent::ExtensionInjected {
                ref name,
                ref agent_role,
                ref task_id,
            } => {
                state.session_extensions_used.push(state::ExtensionEvent {
                    name: name.clone(),
                    agent_role: agent_role.clone(),
                    task_id: task_id.clone(),
                });
                *state
                    .extension_inject_count
                    .entry(name.clone())
                    .or_insert(0) += 1;
            }
            LoopEvent::PatternsUsed {
                ref titles,
                ref keywords_by_title,
            } => {
                for title in titles {
                    state.session_patterns.push(state::PatternEvent {
                        title: title.clone(),
                        kind: state::PatternEventKind::Used,
                    });
                }
                state.pattern_inject_count += titles.len();
                state.active_pattern_keywords = keywords_by_title.clone();
            }
            LoopEvent::BudgetOverrun { phase, target_pct, actual_pct, recovery } => {
                state.log(format!(
                    "BUDGET OVERRUN: {} used {}% (target {}%) -- recovery: {}",
                    phase, actual_pct, target_pct, recovery,
                ));
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
                                if let Ok(n) = trimmed
                                    .split_whitespace()
                                    .next()
                                    .unwrap_or("0")
                                    .parse::<usize>()
                                {
                                    state.session_review_high += n;
                                }
                            } else if trimmed.ends_with("medium") {
                                if let Ok(n) = trimmed
                                    .split_whitespace()
                                    .next()
                                    .unwrap_or("0")
                                    .parse::<usize>()
                                {
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
                if let Some(title) = msg.strip_prefix("Pattern learned: ") {
                    state.session_patterns.push(state::PatternEvent {
                        title: title.to_string(),
                        kind: state::PatternEventKind::Learned,
                    });
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
            LoopEvent::WaitingForReview(pr_num) => {
                state.awaiting_review = true;
                state.awaiting_pr = pr_num;
                state.pr_poll_last_check = None;
                if let Some(num) = pr_num {
                    state.log(format!(
                        "Awaiting PR #{} review -- press Enter to skip or wait for approval",
                        num
                    ));
                } else {
                    state.log("Awaiting review -- press Enter or 'c' to continue");
                }
            }
            LoopEvent::PrApproved(pr_num) => {
                state.awaiting_review = false;
                state.awaiting_pr = None;
                state.pr_poll_last_check = None;
                if let Some(ref gate) = state.review_gate {
                    gate.store(false, Ordering::Relaxed);
                }
                state.log(format!("PR #{} approved -- resuming pipeline", pr_num));
            }
            LoopEvent::PrClosed(pr_num) => {
                state.awaiting_review = false;
                state.awaiting_pr = None;
                state.pr_poll_last_check = None;
                if let Some(ref gate) = state.review_gate {
                    gate.store(false, Ordering::Relaxed);
                }
                // Create stop file to halt the build loop
                let _ = std::fs::create_dir_all(&state.buildloop_dir);
                let _ = std::fs::write(state.buildloop_dir.join("stop"), "");
                state.stop_after_task = true;
                state.log(format!(
                    "PR #{} was closed without merge -- stopping",
                    pr_num
                ));
            }
            LoopEvent::ShipStarted => {
                state.ship_active = true;
                state.log("Ship: committing changes".to_string());
            }
            LoopEvent::ShipDone => {
                state.ship_active = false;
            }
            LoopEvent::ParallelBuilderProgress { total, done } => {
                state.parallel_builder_progress = if done >= total {
                    None // Clear when all done
                } else {
                    Some((total, done))
                };
                state.log(format!("Parallel builder: {}/{} slots complete", done, total));
            }
            LoopEvent::TmuxSessionStarted(name) => {
                state.tmux_session_names.push(name);
            }
            LoopEvent::PrPollChecked => {
                state.pr_poll_last_check = Some(std::time::Instant::now());
            }
            LoopEvent::Finished => {
                // Emit warnings for injected-but-never-referenced extensions
                let warnings: Vec<String> = state.extension_inject_count
                    .iter()
                    .filter_map(|(ext_name, inject_count)| {
                        let ref_count = state.extension_reference_count.get(ext_name).copied().unwrap_or(0);
                        if *inject_count > 0 && ref_count == 0 {
                            Some(format!(
                                "Warning: Extension '{}' was injected {} times but never referenced -- check if the extension content is relevant to this task.",
                                ext_name, inject_count
                            ))
                        } else {
                            None
                        }
                    })
                    .collect();
                for warning in warnings {
                    state.log(warning);
                }
                state.log("All work complete — loop finished");
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."))
                    .to_path_buf();
                enter_home_surface(
                    &project_dir,
                    state,
                    Some("Build loop finished.".to_string()),
                );
            }
        },
        AppEvent::Key(key) => {
            if state.inject_input.is_some() {
                handle_inject_key(state, key);
            } else if state.dual_arena_ready()
                && matches!(key.code, KeyCode::Char('q') | KeyCode::Esc)
            {
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."))
                    .to_path_buf();
                enter_home_surface(
                    &project_dir,
                    state,
                    Some("Arena results preserved in .buildloop/arena/".to_string()),
                );
            } else if state.show_running_explorer {
                // Review gate: Enter/c clears the review pause (must be before other handlers)
                if state.awaiting_review && matches!(key.code, KeyCode::Enter | KeyCode::Char('c'))
                {
                    state.awaiting_review = false;
                    if let Some(ref gate) = state.review_gate {
                        gate.store(false, Ordering::Relaxed);
                    }
                    state.log("Continuing to next task");
                    state.awaiting_pr = None;
                    state.pr_poll_last_check = None;
                } else {
                    match key.code {
                        KeyCode::Char('q') => {
                            if state.stop_after_task {
                                state.stop_after_task = false;
                                let _ = std::fs::remove_file(state.buildloop_dir.join("stop"));
                                state.log("Stop cancelled -- resuming build");
                            } else {
                                state.stop_after_task = true;
                                let _ = std::fs::create_dir_all(&state.buildloop_dir);
                                let _ = std::fs::write(state.buildloop_dir.join("stop"), "");
                                state.log("Stopping after current task (q again to cancel, Ctrl+C to force quit)");
                            }
                        }
                        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            if state.stop_after_task {
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
                        KeyCode::Tab | KeyCode::BackTab => {
                            state.show_running_explorer = false;
                            state.focused_pane = state::TuiPane::AgentOutput;
                        }
                        KeyCode::Up => {
                            move_running_explorer_selection(state, -1);
                        }
                        KeyCode::Down => {
                            move_running_explorer_selection(state, 1);
                        }
                        KeyCode::PageUp => {
                            move_running_explorer_selection(state, -10);
                        }
                        KeyCode::PageDown => {
                            move_running_explorer_selection(state, 10);
                        }
                        KeyCode::Enter => {
                            handle_running_explorer_enter(state);
                        }
                        KeyCode::Char('a') => {
                            if let Some(ref mut explorer) = state.running_explorer {
                                startup::toggle_expand_all(explorer);
                            }
                        }
                        KeyCode::Char('w') => {
                            let project_dir = state
                                .buildloop_dir
                                .parent()
                                .unwrap_or(std::path::Path::new("."));
                            if let Some(ref mut explorer) = state.running_explorer {
                                startup::toggle_preview_wrap(explorer, project_dir);
                            }
                        }
                        _ => {}
                    }
                } // close review-gate else
            } else {
                // Review gate: Enter/c clears the review pause (must be before other handlers)
                if state.awaiting_review && matches!(key.code, KeyCode::Enter | KeyCode::Char('c'))
                {
                    state.awaiting_review = false;
                    if let Some(ref gate) = state.review_gate {
                        gate.store(false, Ordering::Relaxed);
                    }
                    state.log("Continuing to next task");
                    state.awaiting_pr = None;
                    state.pr_poll_last_check = None;
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
                                state.show_patterns = false;
                            } else {
                                state.show_patterns = true;
                                refresh_patterns_cache(state, config);
                            }
                        }
                        // Sandbox toggle removed -- config-only override for implementers.
                        KeyCode::Char('s') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            state.log("Sandbox toggle disabled -- override via .foundry.json only".to_string());
                        }
                        KeyCode::Char('i') => {
                            state.inject_input = Some(String::new());
                        }
                        KeyCode::Char('t') => {
                            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
                            state.tui_theme = new_theme;
                            state.log(format!("Theme: {}", name));
                        }
                        KeyCode::Char('1') => {
                            if state.dual_build.active {
                                state.dual_build.tab = 0;
                            }
                        }
                        KeyCode::Char('2') => {
                            if state.dual_build.active {
                                state.dual_build.tab = 1;
                            }
                        }
                        KeyCode::Up => {
                            if state.show_findings {
                                state.findings_scroll = state.findings_scroll.saturating_sub(3);
                            } else if state.show_patterns {
                                state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
                            } else {
                                let max = state.agent_output.len().saturating_sub(1);
                                state.scroll_offset =
                                    state.scroll_offset.saturating_add(3).min(max);
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
                            state.task_queue_scroll =
                                state.task_queue_scroll.saturating_add(3).min(max);
                        }
                        KeyCode::PageDown => {
                            state.task_queue_scroll = state.task_queue_scroll.saturating_sub(3);
                        }
                        KeyCode::Tab | KeyCode::BackTab => {
                            if state.show_running_explorer {
                                // Return to dashboard
                                state.show_running_explorer = false;
                                state.focused_pane = state::TuiPane::AgentOutput;
                            } else {
                                // Enter explorer view -- lazily populate running_explorer
                                if state.running_explorer.is_none() {
                                    let project_dir = state
                                        .buildloop_dir
                                        .parent()
                                        .unwrap_or(std::path::Path::new("."));
                                    let scenario = detect_startup_scenario(project_dir);
                                    let plan_status = classify_plan_status(
                                        &self::contract::ContractPaths::resolve(project_dir)
                                            .tasks_path,
                                    );
                                    state.running_explorer = Some(StartupState::new(
                                        project_dir,
                                        scenario,
                                        plan_status,
                                        None,
                                    ));
                                }
                                state.show_running_explorer = true;
                                state.focused_pane = state::TuiPane::Explorer;
                            }
                        }
                        _ => {}
                    }
                } // close review-gate else
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
                if connected {
                    "semantic"
                } else {
                    "keyword-only"
                }
                .to_string(),
            );
        }
        AppEvent::Mouse(mouse) => {
            use crossterm::event::{MouseButton, MouseEventKind};
            if state.show_running_explorer {
                // Delegate to running explorer mouse handler
                let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                handle_startup_mouse_at_for_running(state, mouse, terminal_size);
            } else {
                match mouse.kind {
                    MouseEventKind::ScrollUp => {
                        if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
                        } else if state.show_findings {
                            state.findings_scroll = state.findings_scroll.saturating_sub(3);
                        } else {
                            let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                            let area =
                                ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                            let has_ext = state.available_extensions.iter().any(|e| e.selected)
                                || !state.session_extensions_used.is_empty();
                            let panes = tui::running_layout(area, has_ext);
                            if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::AgentOutput;
                                let max = state.agent_output.len().saturating_sub(1);
                                state.scroll_offset =
                                    state.scroll_offset.saturating_add(3).min(max);
                            } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row)
                            {
                                state.focused_pane = state::TuiPane::TaskQueue;
                                let max = state.task_queue.len().saturating_sub(1);
                                state.task_queue_scroll =
                                    state.task_queue_scroll.saturating_add(3).min(max);
                            } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::PatternsLearned;
                                state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
                            } else if panes
                                .extensions_used
                                .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                            {
                                state.focused_pane = state::TuiPane::Extensions;
                            }
                        }
                    }
                    MouseEventKind::ScrollDown => {
                        if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_add(3);
                        } else if state.show_findings {
                            state.findings_scroll = state.findings_scroll.saturating_add(3);
                        } else {
                            let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                            let area =
                                ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                            let has_ext = state.available_extensions.iter().any(|e| e.selected)
                                || !state.session_extensions_used.is_empty();
                            let panes = tui::running_layout(area, has_ext);
                            if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::AgentOutput;
                                state.scroll_offset = state.scroll_offset.saturating_sub(3);
                            } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row)
                            {
                                state.focused_pane = state::TuiPane::TaskQueue;
                                state.task_queue_scroll = state.task_queue_scroll.saturating_sub(3);
                            } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::PatternsLearned;
                                state.patterns_scroll = state.patterns_scroll.saturating_add(3);
                            } else if panes
                                .extensions_used
                                .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                            {
                                state.focused_pane = state::TuiPane::Extensions;
                            }
                        }
                    }
                    MouseEventKind::Down(MouseButton::Left) => {
                        let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                        let area =
                            ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                        let has_ext = state.available_extensions.iter().any(|e| e.selected)
                            || !state.session_extensions_used.is_empty();
                        let panes = tui::running_layout(area, has_ext);
                        if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::AgentOutput;
                        } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::TaskQueue;
                        } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::PatternsLearned;
                        } else if panes
                            .extensions_used
                            .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                        {
                            state.focused_pane = state::TuiPane::Extensions;
                        }
                    }
                    _ => {}
                }
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

fn refresh_patterns_cache(state: &mut AppState, config: &Config) {
    use crate::patterns;
    let dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    state.patterns_cache = Some(patterns::load_patterns(&dir));
    state.patterns_dir_cache = Some(dir);
}

fn handle_agent_output(state: &mut AppState, output: AgentOutputEvent) {
    state.events_received += 1;
    match output {
        AgentOutputEvent::Text(ref text) => {
            if text.starts_with("[rate limited]") {
                // Show in status bar only -- don't pollute the output panel
                state.status_summary = "Waiting for API retry".to_string();
            } else {
                state.agent_output.push(text.clone());
            }
        }
        AgentOutputEvent::ToolUse {
            ref tool,
            ref input_preview,
        } => {
            let msg = if input_preview.is_empty() {
                format!("[tool] {}", tool)
            } else {
                format!("[tool] {} — {}", tool, input_preview)
            };
            state.agent_output.push(msg);

            // Derive human-readable status summary from tool call
            let basename = Path::new(input_preview.as_str())
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or(input_preview.as_str());
            state.status_summary = match tool.as_str() {
                "Read" => format!("Reading {}", basename),
                "Glob" => format!("Exploring {}", truncate_str(input_preview, 40)),
                "Grep" => format!("Searching for {}", truncate_str(input_preview, 40)),
                "Bash" => format!("Running {}", truncate_str(input_preview, 40)),
                "Edit" | "Write" => {
                    if input_preview.contains("scout-report") {
                        "Writing scout report".to_string()
                    } else if input_preview.contains("current-plan") {
                        "Writing plan".to_string()
                    } else if input_preview.contains("build-claims") {
                        "Writing build claims".to_string()
                    } else {
                        format!("Editing {}", basename)
                    }
                }
                _ => state.status_summary.clone(),
            };
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
            // Track tmux session names from "[foundry] tmux session: ..." messages
            if let Some(rest) = line.strip_prefix("[foundry] tmux session: ") {
                if let Some(name) = rest.split_whitespace().next() {
                    state.tmux_session_names.push(name.to_string());
                }
            }
            // Downgrade expected operational messages from [stderr] to [info]
            if line.contains("exceeds maximum allowed tokens")
                || line.contains("File does not exist")
            {
                state.agent_output.push(format!("[info] {}", line));
            } else {
                state.agent_output.push(format!("[stderr] {}", line));
            }
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
            state.session_input_tokens += input_tokens;
            state.session_output_tokens += output_tokens;
            // Update shared atomic for build loop cost-limit check
            let millicents = (cost_usd * 100_000.0) as u64;
            state
                .session_cost_millicents
                .fetch_add(millicents, std::sync::atomic::Ordering::Relaxed);
            let total_tokens = input_tokens + output_tokens;
            if context_window > 0 {
                let pct = ((total_tokens as f64 / context_window as f64) * 100.0).min(100.0) as u8;
                state.agent_context_pct = Some(pct);
                // Save to SPID slot immediately (set_agent resets agent_context_pct
                // when the next stage starts, so we must capture it here)
                if let Some((ref role, _)) = state.current_agent {
                    let slot = match role {
                        AgentRole::Scout => Some(0),
                        AgentRole::Planner => Some(1),
                        AgentRole::Builder => Some(2),
                        AgentRole::Reviewer => Some(3),
                        _ => None,
                    };
                    if let Some(i) = slot {
                        state.spid_context_pcts[i] = Some(pct);
                    }
                }
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

fn handle_dual_build_output(state: &mut AppState, idx: usize, output: AgentOutputEvent) {
    if idx >= 2 {
        return;
    }
    state.dual_build.event_counts[idx] += 1;

    match &output {
        AgentOutputEvent::Text(text) => {
            state.dual_build.streams[idx].push(text.clone());
        }
        AgentOutputEvent::ToolUse {
            tool,
            input_preview,
        } => {
            let msg = if input_preview.is_empty() {
                format!("[tool] {}", tool)
            } else {
                format!("[tool] {} -- {}", tool, input_preview)
            };
            state.dual_build.streams[idx].push(msg);
        }
        AgentOutputEvent::ToolResult { output_preview } => {
            if !output_preview.is_empty() {
                let first_line = output_preview.lines().next().unwrap_or("");
                let display = if first_line.len() > 100 {
                    format!("[result] {}...", truncate_str(first_line, 100))
                } else {
                    format!("[result] {}", first_line)
                };
                state.dual_build.streams[idx].push(display);
            }
        }
        AgentOutputEvent::Stderr(line) => {
            state.dual_build.streams[idx].push(format!("[stderr] {}", line));
        }
        AgentOutputEvent::Result(text) => {
            state.dual_build.streams[idx].push(String::new());
            for line in text.lines().take(10) {
                state.dual_build.streams[idx].push(line.to_string());
            }
        }
        AgentOutputEvent::Usage {
            cost_usd,
            input_tokens,
            output_tokens,
            context_window,
        } => {
            state.session_cost_usd += cost_usd;
            state.session_input_tokens += input_tokens;
            state.session_output_tokens += output_tokens;
            let millicents = (cost_usd * 100_000.0) as u64;
            state
                .session_cost_millicents
                .fetch_add(millicents, std::sync::atomic::Ordering::Relaxed);
            state.dual_build.cost_usd[idx] += cost_usd;
            state.dual_build.input_tokens[idx] += input_tokens;
            state.dual_build.output_tokens[idx] += output_tokens;
            let total_tokens = input_tokens + output_tokens;
            if *context_window > 0 {
                let pct = ((total_tokens as f64 / *context_window as f64) * 100.0).min(100.0) as u8;
                let slot = match state.dual_build.stages[idx].as_ref() {
                    Some(AgentRole::Scout) => Some(0),
                    Some(AgentRole::Planner) => Some(1),
                    Some(AgentRole::Builder) => Some(2),
                    Some(AgentRole::Reviewer) => Some(3),
                    _ => None,
                };
                if let Some(slot) = slot {
                    state.dual_build.context_pcts[idx][slot] = Some(pct);
                }
            }
        }
    }

    // Cap stream buffer
    let cap = AGENT_OUTPUT_CAP;
    if state.dual_build.streams[idx].len() > cap {
        let excess = state.dual_build.streams[idx].len() - cap;
        state.dual_build.streams[idx].drain(..excess);
    }
}

fn handle_dual_pipeline_event(state: &mut AppState, idx: usize, event: AppEvent, _config: &Config) {
    if idx >= 2 {
        return;
    }
    match event {
        AppEvent::AgentOutput(output) => {
            handle_dual_build_output(state, idx, output);
        }
        AppEvent::AgentDone(_success) => {
            // Individual agent done within a pipeline -- not the whole pipeline
        }
        AppEvent::LoopEvent(le) => match le {
            LoopEvent::AgentStarted(role, model) => {
                state.dual_build.stages[idx] = Some(role);
                state.dual_build.stage_models[idx] = model;
            }
            LoopEvent::Log(msg) => {
                state.dual_build.streams[idx].push(format!("[log] {}", msg));
                state.dual_build.event_counts[idx] += 1;
            }
            LoopEvent::TaskCompleted(_id, _success) => {
                // Pipeline finished
                state.dual_build.finished[idx] = true;
            }
            _ => {
                // Other loop events from the pipeline -- ignore at top level
            }
        },
        _ => {}
    }
}

pub(super) fn handle_agent_done(state: &mut AppState, success: bool) {
    // ─── Extension & Pattern Reference Detection ───
    if !state.agent_output.is_empty() {
        let agent_role_str = state
            .current_agent
            .as_ref()
            .map(|(role, _)| role.to_string())
            .unwrap_or_else(|| "unknown".to_string());

        // Build lowercased output for keyword matching (join last 200 lines to bound scan cost)
        let scan_lines = state.agent_output.len().min(200);
        let output_text: String = state.agent_output[state.agent_output.len() - scan_lines..]
            .iter()
            .fold(String::new(), |mut acc, line| {
                acc.push(' ');
                acc.push_str(line);
                acc
            })
            .to_lowercase();

        // Check extension keywords (clone to avoid borrow conflict with state.log)
        let ext_kw_snapshot: Vec<(String, Vec<String>)> = state
            .extension_keywords
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        for (ext_name, keywords) in &ext_kw_snapshot {
            let matched: Vec<String> = keywords
                .iter()
                .filter(|kw| kw.len() >= 4 && output_text.contains(kw.as_str()))
                .take(5)
                .cloned()
                .collect();
            if !matched.is_empty() {
                *state
                    .extension_reference_count
                    .entry(ext_name.clone())
                    .or_insert(0) += 1;
                state.log(format!(
                    "Extension '{}' referenced by {} (keywords: {})",
                    ext_name,
                    agent_role_str,
                    matched.join(", ")
                ));
            }
        }

        // Check pattern keywords (clone to avoid borrow conflict with state.log)
        let pat_kw_snapshot: Vec<(String, Vec<String>)> = state
            .active_pattern_keywords
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        for (title, keywords) in &pat_kw_snapshot {
            let has_match = keywords
                .iter()
                .any(|kw| kw.len() >= 4 && output_text.contains(kw.as_str()));
            if has_match {
                state.pattern_apply_count += 1;
                state.log(format!("Pattern '{}' applied by {}", title, agent_role_str));
            }
        }
    }

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
                        design_assertions: Vec::new(),
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

pub async fn run_headless(project_dir: &Path, output_format: Option<String>) -> Result<()> {
    commands::run_headless(project_dir, output_format).await
}

// ─── Status & Tasks Commands ─────────────────────────────────

pub fn show_status(project_dir: &Path) -> Result<()> {
    commands::show_status(project_dir)
}

pub fn show_tasks(project_dir: &Path) -> Result<()> {
    commands::show_tasks(project_dir)
}

// ─── Extract Patterns Command ─────────────────────────────────

pub fn run_extract(project_dir: &Path) -> Result<()> {
    commands::run_extract(project_dir)
}

// ─── Running Explorer Helpers ─────────────────────────────────

fn move_running_explorer_selection(state: &mut AppState, delta: isize) {
    let Some(explorer) = state.running_explorer.as_mut() else {
        return;
    };
    let vis = explorer.visible_indices();
    if vis.is_empty() {
        return;
    }
    let cur_pos = vis
        .iter()
        .position(|&i| i == explorer.explorer_selected)
        .unwrap_or(0);
    let max_pos = vis.len() - 1;
    let new_pos = (cur_pos as isize + delta).clamp(0, max_pos as isize) as usize;
    let new_index = vis[new_pos];
    if new_index == explorer.explorer_selected {
        return;
    }
    explorer.explorer_selected = new_index;
    let visible_estimate: usize = 20;
    if new_pos < explorer.explorer_scroll {
        explorer.explorer_scroll = new_pos;
    } else if new_pos >= explorer.explorer_scroll + visible_estimate {
        explorer.explorer_scroll = new_pos.saturating_sub(visible_estimate) + 1;
    }
    // Load preview for new selection
    let entry = &explorer.file_tree[new_index];
    explorer.file_preview_content = if entry.is_dir {
        vec!["<directory>".to_string()]
    } else {
        load_file_preview_for_running(&entry.path)
    };
    explorer.file_preview_scroll = 0;
}

fn handle_running_explorer_enter(state: &mut AppState) {
    let Some(explorer) = state.running_explorer.as_mut() else {
        return;
    };
    let selected = explorer.explorer_selected;
    if selected >= explorer.file_tree.len() {
        return;
    }
    if explorer.file_tree[selected].is_dir {
        explorer.file_tree[selected].expanded = !explorer.file_tree[selected].expanded;
        if !explorer.file_tree[selected].expanded {
            let vis = explorer.visible_indices();
            if !vis.contains(&explorer.explorer_selected) {
                explorer.explorer_selected = selected;
            }
        }
    } else {
        let file_path = explorer.file_tree[selected].path.clone();
        state.pending_transition = Some(state::PendingTransition::OpenExternalEditor { file_path });
    }
}

fn load_file_preview_for_running(path: &std::path::Path) -> Vec<String> {
    if path.is_dir() {
        return vec!["<directory>".to_string()];
    }
    match std::fs::read_to_string(path) {
        Ok(content) => content.lines().take(500).map(|l| l.to_string()).collect(),
        Err(_) => vec!["<binary or unreadable file>".to_string()],
    }
}

fn handle_startup_mouse_at_for_running(
    state: &mut AppState,
    mouse: crossterm::event::MouseEvent,
    terminal_size: (u16, u16),
) {
    use crossterm::event::{MouseButton, MouseEventKind};
    // Running explorer uses the same 36/64 split for the middle section
    let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
    let chunks = ratatui::layout::Layout::default()
        .direction(ratatui::layout::Direction::Vertical)
        .constraints([
            ratatui::layout::Constraint::Length(5),
            ratatui::layout::Constraint::Length(7),
            ratatui::layout::Constraint::Min(10),
            ratatui::layout::Constraint::Length(6),
            ratatui::layout::Constraint::Length(1),
        ])
        .split(area);
    let middle_cols = ratatui::layout::Layout::default()
        .direction(ratatui::layout::Direction::Horizontal)
        .constraints([
            ratatui::layout::Constraint::Percentage(36),
            ratatui::layout::Constraint::Percentage(64),
        ])
        .split(chunks[2]);
    let explorer_area = middle_cols[0];
    let preview_area = middle_cols[1];

    match mouse.kind {
        MouseEventKind::Down(MouseButton::Left) => {
            // Check toggle buttons first (border row)
            if let Some(ref explorer) = state.running_explorer {
                if let Some(tui::StartupMouseTarget::ExpandAllToggle) =
                    tui::explorer_toggle_hit_test(
                        explorer_area,
                        mouse.column,
                        mouse.row,
                        &explorer.file_tree,
                    )
                {
                    state.focused_pane = state::TuiPane::Explorer;
                    if let Some(ref mut ex) = state.running_explorer {
                        startup::toggle_expand_all(ex);
                    }
                    return;
                }
                if let Some(tui::StartupMouseTarget::WrapToggle) = tui::preview_toggle_hit_test(
                    preview_area,
                    mouse.column,
                    mouse.row,
                    explorer.preview_wrap,
                ) {
                    state.focused_pane = state::TuiPane::Preview;
                    let project_dir = state
                        .buildloop_dir
                        .parent()
                        .unwrap_or(std::path::Path::new("."));
                    if let Some(ref mut ex) = state.running_explorer {
                        startup::toggle_preview_wrap(ex, project_dir);
                    }
                    return;
                }
            }

            if tui::rect_contains(explorer_area, mouse.column, mouse.row) {
                state.focused_pane = state::TuiPane::Explorer;
                // Hit-test to select file entry
                let inner_top = explorer_area.y + 1;
                let inner_bottom = explorer_area.y + explorer_area.height.saturating_sub(1);
                if mouse.row >= inner_top && mouse.row < inner_bottom {
                    if let Some(ref mut explorer) = state.running_explorer {
                        let relative_row = (mouse.row - inner_top) as usize;
                        let vis = explorer.visible_indices();
                        let vis_index = explorer.explorer_scroll + relative_row;
                        if vis_index < vis.len() {
                            let tree_idx = vis[vis_index];
                            explorer.explorer_selected = tree_idx;
                            let vis_pos = vis.iter().position(|&i| i == tree_idx).unwrap_or(0);
                            let visible_estimate: usize = 20;
                            if vis_pos < explorer.explorer_scroll {
                                explorer.explorer_scroll = vis_pos;
                            } else if vis_pos >= explorer.explorer_scroll + visible_estimate {
                                explorer.explorer_scroll =
                                    vis_pos.saturating_sub(visible_estimate) + 1;
                            }
                            // Toggle folder expanded/collapsed on click
                            if explorer.file_tree[tree_idx].is_dir {
                                explorer.file_tree[tree_idx].expanded =
                                    !explorer.file_tree[tree_idx].expanded;
                                explorer.file_preview_content = vec!["<directory>".to_string()];
                            } else {
                                explorer.file_preview_content = load_file_preview_for_running(
                                    &explorer.file_tree[tree_idx].path,
                                );
                            }
                            explorer.file_preview_scroll = 0;
                        }
                    }
                }
            } else if tui::rect_contains(preview_area, mouse.column, mouse.row) {
                state.focused_pane = state::TuiPane::Preview;
            }
        }
        MouseEventKind::ScrollUp => match state.focused_pane {
            state::TuiPane::Preview => {
                if let Some(ref mut explorer) = state.running_explorer {
                    explorer.file_preview_scroll = explorer.file_preview_scroll.saturating_sub(3);
                }
            }
            _ => {
                move_running_explorer_selection(state, -3);
            }
        },
        MouseEventKind::ScrollDown => match state.focused_pane {
            state::TuiPane::Preview => {
                if let Some(ref mut explorer) = state.running_explorer {
                    let max_scroll = explorer.file_preview_content.len().saturating_sub(1);
                    explorer.file_preview_scroll =
                        (explorer.file_preview_scroll + 3).min(max_scroll);
                }
            }
            _ => {
                move_running_explorer_selection(state, 3);
            }
        },
        _ => {}
    }
}

#[cfg(test)]
mod tests;

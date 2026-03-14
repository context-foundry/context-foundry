use anyhow::{Context, Result};
use crossterm::event::{self, Event, KeyCode, KeyModifiers};
use futures::StreamExt;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;

mod build;
mod commands;
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
use crate::task;
use crate::tui;
use crate::update;
use crate::utils::truncate_str;

// ─── TUI Mode ────────────────────────────────────────────────

pub async fn run_tui(project_dir: &Path) -> Result<()> {
    let config = Config::load(project_dir);
    commands::ensure_required_providers_available(&config, commands::ProviderCommandMode::Run)?;
    let buildloop_dir = project_dir.join(".buildloop");
    let _ = std::fs::create_dir_all(&buildloop_dir);
    let _ = std::fs::remove_file(buildloop_dir.join("stop"));
    let shutdown = Arc::new(AtomicBool::new(false));
    let mut state = AppState::new(buildloop_dir);

    // Git/GH readiness checks (advisory, non-blocking)
    for msg in git::check_git_readiness(project_dir) {
        state.log(msg);
    }
    for msg in ContractPaths::resolve(project_dir).warnings() {
        state.log(msg);
    }

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
            AppPhase::Startup => tui::render_startup(frame, &state),
            AppPhase::Planning | AppPhase::Running => {
                if state.show_patterns {
                    tui::render_patterns(frame, &state, &config);
                } else if state.show_dashboard {
                    tui::render_dashboard(frame, &state, &config);
                } else {
                    tui::render(frame, &state);
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
                    Event::Key(key) => Some(AppEvent::Key(key)),
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

    let status = std::process::Command::new("sh")
        .arg("-c")
        .arg("$FOUNDRY_EDITOR \"$FOUNDRY_TARGET_FILE\"")
        .env("FOUNDRY_EDITOR", &editor)
        .env("FOUNDRY_TARGET_FILE", file_path)
        .status()
        .context("failed to launch editor")?;

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

    let run_context = RunContext::new(project_dir, config.clone(), shutdown.clone());
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
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;
    state.set_agent(
        AgentRole::Planner,
        &Config::display_provider_model(&config.planner_provider, &config.planner_model),
    );
    state.log(format!("Planning started — {}", label));

    let run_context = RunContext::new(project_dir, config.clone(), shutdown.clone());
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

    // Compute the actual model that run_append_tasks will use.
    let actual_model = if Config::parse_provider(&config.planner_provider)
        == crate::agent::ModelProvider::Claude
    {
        config.planner_model.as_str()
    } else {
        "opus"
    };

    state.phase = AppPhase::Planning;
    state.startup = None;
    state.planning = Some(PlanningState {
        label: request.label.clone(),
        user_intent: Some(request.description.clone()),
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;
    state.set_agent(AgentRole::Planner, &format!("Claude {}", actual_model));
    state.log(format!("Planning started — {}", request.label));

    let run_context = RunContext::new(project_dir, config.clone(), shutdown.clone());
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
    std::fs::write(contract_paths.spec_path, spec)?;
    Ok(())
}

fn handle_planning_event(state: &mut AppState, event: AppEvent) {
    match event {
        AppEvent::AgentOutput(output) => handle_agent_output(state, output),
        AppEvent::AgentDone(success) => handle_agent_done(state, success),
        AppEvent::PlanningFinished(outcome) => apply_planning_outcome(state, outcome),
        AppEvent::Key(key) => handle_planning_key(state, key),
        AppEvent::Mouse(_) | AppEvent::Paste(_) => {}
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
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
        KeyCode::Char('d') => {
            state.show_dashboard = !state.show_dashboard;
            state.show_patterns = false;
        }
        KeyCode::Char('p') => {
            state.show_patterns = !state.show_patterns;
        }
        KeyCode::Up => {
            if state.show_patterns {
                state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
            } else {
                state.scroll_offset = state.scroll_offset.saturating_add(3);
            }
        }
        KeyCode::Down => {
            if state.show_patterns {
                state.patterns_scroll = state.patterns_scroll.saturating_add(3);
            } else {
                state.scroll_offset = state.scroll_offset.saturating_sub(3);
            }
        }
        KeyCode::PageUp => {
            state.task_queue_scroll = state.task_queue_scroll.saturating_add(3);
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
                if success {
                    state.session_feat_commits += 1;
                } else {
                    state.session_wip_commits += 1;
                }
                // Save stages into history (review result may arrive separately)
                let history = state.task_history.entry(id.clone()).or_default();
                history.stages_seen = state.task_stages_seen.clone();
                state.current_task = None;
                state.task_start = None;
                state.task_stages_seen.clear();
                state.clear_agent();
            }
            LoopEvent::NextTaskUpdated(next_task) => {
                state.next_task_hint = next_task;
            }
            LoopEvent::DiscoveryStarted => {
                state.is_discovering = true;
                state.discovery_round += 1;
                state.log(format!("Discovery round {} started", state.discovery_round));
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
                let history = state.task_history.entry(task_id).or_default();
                history.fix_passes = fix_passes;
                history.passed_review = passed;
            }
            LoopEvent::Finished => {
                state.log("All work complete — loop finished");
                state.should_quit = true;
            }
        },
        AppEvent::Key(key) => {
            if state.inject_input.is_some() {
                handle_inject_key(state, key);
            } else {
                match key.code {
                    KeyCode::Char('q') => {
                        let _ = std::fs::remove_file(state.buildloop_dir.join("stop"));
                        state.should_quit = true;
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
                    KeyCode::Char('d') => {
                        state.show_dashboard = !state.show_dashboard;
                        state.show_patterns = false;
                    }
                    KeyCode::Char('p') => {
                        if state.show_patterns {
                            // Return to whatever view was active before patterns
                            state.show_patterns = false;
                        } else {
                            state.show_patterns = true;
                            // Don't clear show_dashboard -- it's restored when p toggles off
                        }
                    }
                    KeyCode::Char('i') => {
                        state.inject_input = Some(String::new());
                    }
                    KeyCode::Up => {
                        if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
                        } else {
                            state.scroll_offset = state.scroll_offset.saturating_add(3);
                        }
                    }
                    KeyCode::Down => {
                        if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_add(3);
                        } else {
                            state.scroll_offset = state.scroll_offset.saturating_sub(3);
                        }
                    }
                    KeyCode::PageUp => {
                        state.task_queue_scroll = state.task_queue_scroll.saturating_add(3);
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

        if let Err(e) = std::fs::write(&plan_path, new_content) {
            state.log(format!("Failed to inject task: {}", e));
            return;
        }
    } else {
        // Append to end (default)
        let append_line = format!("\n{}\n", new_task_line);
        if let Err(e) = std::fs::OpenOptions::new()
            .append(true)
            .create(true)
            .open(&plan_path)
            .and_then(|mut f| {
                use std::io::Write;
                f.write_all(append_line.as_bytes())
            })
        {
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

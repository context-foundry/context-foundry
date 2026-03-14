use crossterm::event::{self, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use std::path::Path;

use crate::utils::truncate_str;
use crate::{task, tui};

use super::contract::ContractPaths;
use super::{
    AppEvent, AppPhase, AppState, AppendTasksRequest, PendingTransition, PlanStatus, StartupAction,
    StartupScenario, StartupState,
};

const CLICK_SCROLL_DEBOUNCE_TICKS: u8 = 2;

impl StartupState {
    pub(crate) fn new(
        project_dir: &Path,
        scenario: StartupScenario,
        plan_status: PlanStatus,
        status_message: Option<String>,
    ) -> Self {
        let contract_paths = ContractPaths::resolve(project_dir);
        let actions = match scenario {
            StartupScenario::EmptyProject => {
                vec![StartupAction::DescribeWork, StartupAction::EditSpec]
            }
            StartupScenario::NeedsQueue => vec![
                StartupAction::DescribeWork,
                StartupAction::DesignWithReview,
                StartupAction::ScanProject,
                StartupAction::EditSpec,
            ],
            StartupScenario::QueueReady => vec![
                StartupAction::Continue,
                StartupAction::DescribeWork,
                StartupAction::DesignWithReview,
                StartupAction::ViewTasks,
                StartupAction::EditSpec,
            ],
            StartupScenario::QueueComplete => vec![
                StartupAction::DescribeWork,
                StartupAction::DesignWithReview,
                StartupAction::ScanProject,
                StartupAction::ViewTasks,
                StartupAction::EditSpec,
            ],
        };
        let primary = actions[0];

        Self {
            scenario,
            plan_status,
            has_spec: contract_paths.spec_path.exists(),
            selected_action: 0,
            actions,
            entering_intent: startup_action_uses_intent(primary),
            intent_input: String::new(),
            status_message,
            git_context: crate::git::gather_git_context(project_dir),
            tasks_file_name: contract_paths.tasks_file_name(),
            plan_preview_lines: load_plan_preview_lines(project_dir),
            plan_scroll_offset: 0,
            next_pending_task: load_next_pending_task(project_dir),
            spec_file_name: contract_paths.spec_file_name(),
            spec_preview_lines: load_spec_preview_lines(project_dir),
            spec_scroll_offset: 0,
        }
    }

    pub fn action_label(&self, action: StartupAction) -> String {
        match action {
            StartupAction::Continue => "Continue".to_string(),
            StartupAction::DescribeWork => match self.scenario {
                StartupScenario::EmptyProject => "Describe project".to_string(),
                StartupScenario::NeedsQueue => "Describe work".to_string(),
                StartupScenario::QueueReady => "Describe more work".to_string(),
                StartupScenario::QueueComplete => "Describe next work".to_string(),
            },
            StartupAction::DesignWithReview => "Design with review".to_string(),
            StartupAction::ScanProject => "Scan project".to_string(),
            StartupAction::ViewTasks => self.tasks_file_name.clone(),
            StartupAction::EditSpec => self.spec_file_name.clone(),
        }
    }

    pub fn action_description(&self, action: StartupAction) -> String {
        match action {
            StartupAction::Continue => {
                "Resume the build loop from the next pending task.".to_string()
            }
            StartupAction::DescribeWork => match self.scenario {
                StartupScenario::EmptyProject => format!(
                    "Start with a brief. Foundry saves it to {}, creates {}, then starts building.",
                    self.spec_file_name, self.tasks_file_name
                ),
                StartupScenario::NeedsQueue => format!(
                    "Describe what you want done. Foundry creates {} and starts building.",
                    self.tasks_file_name
                ),
                StartupScenario::QueueReady => format!(
                    "Append work to {}, then resume the build loop.",
                    self.tasks_file_name
                ),
                StartupScenario::QueueComplete => format!(
                    "Describe what should happen next. Foundry turns it into tasks in {}.",
                    self.tasks_file_name
                ),
            },
            StartupAction::DesignWithReview => {
                "Cross-model design loop. Proposer drafts, reviewer validates, iterates until accepted.".to_string()
            }
            StartupAction::ScanProject => format!(
                "Inspect the codebase and append tasks to {}. {} is optional context.",
                self.tasks_file_name, self.spec_file_name
            ),
            StartupAction::ViewTasks => {
                "Browse the task queue. Scroll to review all tasks.".to_string()
            }
            StartupAction::EditSpec => {
                "Optional advanced context. Edit the project spec used for future scans."
                    .to_string()
            }
        }
    }

    pub fn summary_headline(&self) -> &'static str {
        match self.scenario {
            StartupScenario::EmptyProject => "Start a new project.",
            StartupScenario::NeedsQueue => "Code found, but no task queue exists yet.",
            StartupScenario::QueueReady => "Work is ready to continue.",
            StartupScenario::QueueComplete => "Current task queue is complete.",
        }
    }

    pub fn summary_detail(&self) -> &'static str {
        match self.scenario {
            StartupScenario::EmptyProject => {
                "Describe what you want to build. Foundry will turn that into the first task queue."
            }
            StartupScenario::NeedsQueue => {
                "Describe the next job or scan the repo to let Foundry propose work."
            }
            StartupScenario::QueueReady => {
                "Continue the queue, or add more work before the loop starts."
            }
            StartupScenario::QueueComplete => {
                "Describe what should happen next, or scan the project for gaps."
            }
        }
    }

    pub fn plan_status_label(&self) -> String {
        match self.plan_status {
            PlanStatus::Missing => "missing".to_string(),
            PlanStatus::Invalid => "invalid".to_string(),
            PlanStatus::Empty => "empty".to_string(),
            PlanStatus::Pending(count) => format!("pending ({count})"),
            PlanStatus::Complete => "complete".to_string(),
        }
    }

    pub fn has_plan_preview(&self) -> bool {
        !self.plan_preview_lines.is_empty()
    }
}

fn startup_action_uses_intent(action: StartupAction) -> bool {
    matches!(
        action,
        StartupAction::DescribeWork | StartupAction::ScanProject | StartupAction::DesignWithReview
    )
}

fn describe_work_empty_message(scenario: StartupScenario) -> &'static str {
    match scenario {
        StartupScenario::EmptyProject => "Describe what you want to build first.",
        StartupScenario::QueueReady => "Describe what should be added to the queue first.",
        StartupScenario::NeedsQueue | StartupScenario::QueueComplete => {
            "Describe what you want Foundry to do first."
        }
    }
}

pub(super) fn handle_startup_event(state: &mut AppState, event: AppEvent) {
    match event {
        AppEvent::Key(key) => handle_startup_key(state, key),
        AppEvent::Mouse(mouse) => handle_startup_mouse(state, mouse),
        AppEvent::Paste(text) => handle_startup_paste(state, text),
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
            state.startup_scroll_debounce_ticks =
                state.startup_scroll_debounce_ticks.saturating_sub(1);
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
        _ => {}
    }
}

fn handle_startup_paste(state: &mut AppState, text: String) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    if startup.entering_intent {
        startup.intent_input.push_str(&text);
    }
}

pub(super) fn handle_startup_key(state: &mut AppState, key: event::KeyEvent) {
    let action_count = state
        .startup
        .as_ref()
        .map(|startup| startup.actions.len())
        .unwrap_or(0);
    if action_count == 0 {
        return;
    }

    if selected_startup_action(state)
        .map(startup_action_uses_intent)
        .unwrap_or(false)
        && startup_intent_captures_key(key)
    {
        handle_startup_intent_input(state, key);
        return;
    }

    match key.code {
        KeyCode::Char('f') if state.last_orchestrator_outcome.is_some() => {
            state.show_findings = !state.show_findings;
            state.findings_scroll = 0;
        }
        KeyCode::Esc | KeyCode::Char('q') => {
            state.should_quit = true;
        }
        KeyCode::Left => move_startup_selection(state, -1),
        KeyCode::Right => move_startup_selection(state, 1),
        KeyCode::Up => scroll_startup_content(state, -1),
        KeyCode::Down => scroll_startup_content(state, 1),
        KeyCode::PageUp => scroll_startup_content(state, -8),
        KeyCode::PageDown => scroll_startup_content(state, 8),
        KeyCode::Enter => {
            let action = state
                .startup
                .as_ref()
                .and_then(|startup| startup.actions.get(startup.selected_action))
                .copied();
            if let Some(action) = action {
                activate_startup_action(state, action);
            }
        }
        KeyCode::Char(c) if c.is_ascii_digit() => {
            if let Some(index) = c
                .to_digit(10)
                .and_then(|n| n.checked_sub(1))
                .map(|n| n as usize)
            {
                set_startup_selected_action(state, index);
            }
        }
        _ => {
            if selected_startup_action(state)
                .map(startup_action_uses_intent)
                .unwrap_or(false)
            {
                handle_startup_intent_input(state, key);
            }
        }
    }
}

fn startup_intent_captures_key(key: event::KeyEvent) -> bool {
    match key.code {
        KeyCode::Enter | KeyCode::Backspace => true,
        KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => true,
        KeyCode::Char(_) if !key.modifiers.contains(KeyModifiers::CONTROL) => true,
        _ => false,
    }
}

pub(super) fn handle_startup_mouse(state: &mut AppState, mouse: MouseEvent) {
    handle_startup_mouse_at(state, mouse, current_terminal_size());
}

pub(super) fn handle_startup_mouse_at(
    state: &mut AppState,
    mouse: MouseEvent,
    terminal_size: (u16, u16),
) {
    match mouse.kind {
        MouseEventKind::Down(MouseButton::Left) => {
            // Primary fix: clicks inside the preview are read-only no-ops.
            // Secondary guard: some trackpads emit a tiny wheel event as part of
            // a tap/click gesture, so suppress startup scrolling briefly after a click.
            state.startup_scroll_debounce_ticks = CLICK_SCROLL_DEBOUNCE_TICKS;
            if let Some(target) =
                tui::startup_hit_test(terminal_size, state, mouse.column, mouse.row)
            {
                match target {
                    tui::StartupMouseTarget::Action(index) => {
                        set_startup_selected_action(state, index);
                    }
                    tui::StartupMouseTarget::PreviewLine => {}
                }
            }
        }
        MouseEventKind::ScrollUp => {
            if state.startup_scroll_debounce_ticks == 0 {
                scroll_startup_content(state, -3)
            }
        }
        MouseEventKind::ScrollDown => {
            if state.startup_scroll_debounce_ticks == 0 {
                scroll_startup_content(state, 3)
            }
        }
        _ => {}
    }
}

pub(super) fn handle_startup_intent_input(state: &mut AppState, key: event::KeyEvent) {
    let current_action = selected_startup_action(state);
    let Some(startup) = state.startup.as_mut() else {
        return;
    };

    match key.code {
        KeyCode::Enter => {
            let text = startup.intent_input.trim().to_string();

            match current_action {
                Some(StartupAction::DescribeWork) => {
                    if text.is_empty() {
                        startup.status_message =
                            Some(describe_work_empty_message(startup.scenario).to_string());
                        return;
                    }
                    startup.entering_intent = false;
                    startup.status_message = None;
                    startup.intent_input.clear();
                    let action_label = startup.action_label(StartupAction::DescribeWork);
                    let label = format!("{action_label}: {}", truncate_str(&text, 48));
                    state.pending_transition =
                        Some(PendingTransition::AppendTasks(AppendTasksRequest {
                            description: text,
                            label,
                            seed_spec_from_description: matches!(
                                startup.scenario,
                                StartupScenario::EmptyProject
                            ),
                        }));
                }
                Some(StartupAction::ScanProject) => {
                    startup.entering_intent = false;
                    startup.status_message = None;
                    let user_intent = if text.is_empty() {
                        None
                    } else {
                        Some(text.clone())
                    };
                    startup.intent_input.clear();
                    let action_label = startup.action_label(StartupAction::ScanProject);
                    let label = if let Some(ref intent) = user_intent {
                        format!("{action_label}: {}", truncate_str(intent, 48))
                    } else {
                        action_label.to_string()
                    };
                    state.pending_transition =
                        Some(PendingTransition::StartPlanning { user_intent, label });
                }
                Some(StartupAction::DesignWithReview) => {
                    if text.is_empty() {
                        startup.status_message =
                            Some("Describe what you want designed first.".to_string());
                        return;
                    }
                    startup.entering_intent = false;
                    startup.status_message = None;
                    startup.intent_input.clear();
                    state.pending_transition = Some(PendingTransition::StartDesign {
                        user_intent: text,
                    });
                }
                _ => {}
            }
        }
        KeyCode::Backspace => {
            startup.intent_input.pop();
        }
        KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            startup.intent_input.clear();
        }
        KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
            startup.intent_input.push(c);
        }
        _ => {}
    }
}

pub(super) fn move_startup_selection(state: &mut AppState, delta: isize) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    let max_index = startup.actions.len().saturating_sub(1) as isize;
    let next = (startup.selected_action as isize + delta).clamp(0, max_index) as usize;
    set_startup_selected_action(state, next);
}

pub(super) fn set_startup_selected_action(state: &mut AppState, index: usize) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    if index >= startup.actions.len() {
        return;
    }
    startup.selected_action = index;
    startup.entering_intent = startup_action_uses_intent(startup.actions[index]);
    startup.status_message = None;
}

pub(super) fn scroll_startup_content(state: &mut AppState, delta: isize) {
    let action = selected_startup_action(state);
    let Some(startup) = state.startup.as_mut() else {
        return;
    };

    match action {
        Some(StartupAction::DescribeWork)
        | Some(StartupAction::ScanProject)
        | Some(StartupAction::DesignWithReview) => {}
        Some(StartupAction::EditSpec) => {
            adjust_scroll_offset(&mut startup.spec_scroll_offset, delta);
        }
        Some(StartupAction::ViewTasks) | Some(StartupAction::Continue) | None => {
            adjust_scroll_offset(&mut startup.plan_scroll_offset, delta);
        }
    }
}

pub(super) fn adjust_scroll_offset(offset: &mut usize, delta: isize) {
    if delta < 0 {
        *offset = offset.saturating_sub(delta.unsigned_abs());
    } else {
        *offset = offset.saturating_add(delta as usize);
    }
}

pub(super) fn selected_startup_action(state: &AppState) -> Option<StartupAction> {
    state
        .startup
        .as_ref()
        .and_then(|startup| startup.actions.get(startup.selected_action))
        .copied()
}

pub(super) fn activate_startup_action(state: &mut AppState, action: StartupAction) {
    match action {
        StartupAction::Continue => {
            state.pending_transition = Some(PendingTransition::StartBuild);
        }
        StartupAction::ScanProject => {
            if let Some(startup) = state.startup.as_mut() {
                let text = startup.intent_input.trim().to_string();
                let user_intent = if text.is_empty() {
                    None
                } else {
                    Some(text.clone())
                };
                startup.entering_intent = false;
                startup.status_message = None;
                startup.intent_input.clear();
                let action_label = startup.action_label(StartupAction::ScanProject);
                let label = if let Some(ref intent) = user_intent {
                    format!("{action_label}: {}", truncate_str(intent, 48))
                } else {
                    action_label.to_string()
                };
                state.pending_transition =
                    Some(PendingTransition::StartPlanning { user_intent, label });
            }
        }
        StartupAction::DescribeWork => {
            if let Some(startup) = state.startup.as_mut() {
                let text = startup.intent_input.trim().to_string();
                if text.is_empty() {
                    startup.entering_intent = true;
                    startup.status_message =
                        Some(describe_work_empty_message(startup.scenario).to_string());
                    return;
                }
                startup.entering_intent = false;
                startup.status_message = None;
                startup.intent_input.clear();
                let action_label = startup.action_label(StartupAction::DescribeWork);
                let label = format!("{action_label}: {}", truncate_str(&text, 48));
                state.pending_transition =
                    Some(PendingTransition::AppendTasks(AppendTasksRequest {
                        description: text,
                        label,
                        seed_spec_from_description: matches!(
                            startup.scenario,
                            StartupScenario::EmptyProject
                        ),
                    }));
            }
        }
        StartupAction::DesignWithReview => {
            if let Some(startup) = state.startup.as_mut() {
                let text = startup.intent_input.trim().to_string();
                if text.is_empty() {
                    startup.entering_intent = true;
                    startup.status_message =
                        Some("Describe what you want designed first.".to_string());
                    return;
                }
                startup.entering_intent = false;
                startup.status_message = None;
                startup.intent_input.clear();
                state.pending_transition = Some(PendingTransition::StartDesign {
                    user_intent: text,
                });
            }
        }
        StartupAction::ViewTasks => {
            let tasks_path =
                ContractPaths::resolve(state.buildloop_dir.parent().unwrap_or(Path::new(".")))
                    .tasks_path;
            state.pending_transition = Some(PendingTransition::OpenExternalEditor {
                file_path: tasks_path,
            });
        }
        StartupAction::EditSpec => {
            let spec_path =
                ContractPaths::resolve(state.buildloop_dir.parent().unwrap_or(Path::new(".")))
                    .spec_path;
            state.pending_transition = Some(PendingTransition::OpenExternalEditor {
                file_path: spec_path,
            });
        }
    }
}

pub(super) fn enter_home_surface(
    project_dir: &Path,
    state: &mut AppState,
    status_message: Option<String>,
) {
    refresh_plan_counts(project_dir, state);
    state.project_name = resolve_project_name(project_dir);
    state.clear_agent();
    state.current_task = None;
    state.is_discovering = false;
    state.stop_after_task = false;
    state.planning = None;

    let scenario = detect_startup_scenario(project_dir);
    enter_startup_surface_for_scenario(project_dir, state, scenario, status_message);
}

fn resolve_project_name(project_dir: &Path) -> String {
    let contract_paths = ContractPaths::resolve(project_dir);

    // Try to extract name from SPEC.md header: "# Specification: <name>"
    if let Ok(content) = std::fs::read_to_string(&contract_paths.spec_path) {
        for line in content.lines().take(5) {
            let trimmed = line.trim();
            if let Some(rest) = trimmed
                .strip_prefix("# Specification:")
                .or_else(|| trimmed.strip_prefix("# Architecture:"))
                .or_else(|| trimmed.strip_prefix("#"))
            {
                let name = rest.trim();
                if !name.is_empty() {
                    return name.to_string();
                }
            }
        }
    }

    // Fall back to directory name
    project_dir
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .into_owned()
}

pub(super) fn enter_startup_surface(
    project_dir: &Path,
    state: &mut AppState,
    status_message: Option<String>,
) {
    refresh_plan_counts(project_dir, state);
    state.project_name = resolve_project_name(project_dir);
    state.clear_agent();
    state.current_task = None;
    state.is_discovering = false;
    state.stop_after_task = false;
    state.planning = None;

    let scenario = detect_startup_scenario(project_dir);
    enter_startup_surface_for_scenario(project_dir, state, scenario, status_message);
}

pub(super) fn enter_startup_surface_for_scenario(
    project_dir: &Path,
    state: &mut AppState,
    scenario: StartupScenario,
    status_message: Option<String>,
) {
    let plan_status = classify_plan_status(&ContractPaths::resolve(project_dir).tasks_path);
    state.phase = AppPhase::Startup;
    state.startup = Some(StartupState::new(
        project_dir,
        scenario,
        plan_status,
        status_message,
    ));
    state.current_task = None;
    state.next_task_hint = None;
    state.startup_scroll_debounce_ticks = 0;
}

fn refresh_plan_counts(project_dir: &Path, state: &mut AppState) {
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;
    match task::parse_tasks(&plan_path) {
        Ok(tasks) => state.update_counts(&tasks),
        Err(_) => {
            state.total_count = 0;
            state.completed_count = 0;
        }
    }
}

fn load_plan_preview_lines(project_dir: &Path) -> Vec<String> {
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;
    std::fs::read_to_string(plan_path)
        .map(|content| content.lines().map(|line| line.to_string()).collect())
        .unwrap_or_default()
}

fn load_spec_preview_lines(project_dir: &Path) -> Vec<String> {
    let spec_path = ContractPaths::resolve(project_dir).spec_path;
    std::fs::read_to_string(spec_path)
        .map(|content| content.lines().map(|line| line.to_string()).collect())
        .unwrap_or_default()
}

fn load_next_pending_task(project_dir: &Path) -> Option<String> {
    load_pending_task_at(project_dir, 0)
}

pub(super) fn load_pending_task_at(project_dir: &Path, pending_index: usize) -> Option<String> {
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;
    task::parse_tasks(&plan_path)
        .ok()
        .and_then(|tasks| task::nth_pending(&tasks, pending_index).cloned())
        .map(|task| format!("{} — {}", task.id, task.short_desc(72)))
}

fn current_terminal_size() -> (u16, u16) {
    crossterm::terminal::size().unwrap_or((120, 40))
}

pub(super) fn classify_plan_status(plan_path: &Path) -> PlanStatus {
    if !plan_path.exists() {
        return PlanStatus::Missing;
    }

    match task::parse_tasks(plan_path) {
        Err(_) => PlanStatus::Invalid,
        Ok(tasks) if tasks.is_empty() => PlanStatus::Empty,
        Ok(tasks) => {
            let pending = task::count_pending(&tasks);
            if pending > 0 {
                PlanStatus::Pending(pending)
            } else {
                PlanStatus::Complete
            }
        }
    }
}

pub(super) fn detect_startup_scenario(project_dir: &Path) -> StartupScenario {
    if !has_meaningful_project_files(project_dir) {
        return StartupScenario::EmptyProject;
    }

    match classify_plan_status(&ContractPaths::resolve(project_dir).tasks_path) {
        PlanStatus::Pending(_) => StartupScenario::QueueReady,
        PlanStatus::Complete => StartupScenario::QueueComplete,
        PlanStatus::Missing | PlanStatus::Invalid | PlanStatus::Empty => {
            StartupScenario::NeedsQueue
        }
    }
}

fn has_meaningful_project_files(project_dir: &Path) -> bool {
    scan_for_meaningful_files(project_dir, 0)
}

fn scan_for_meaningful_files(dir: &Path, depth: usize) -> bool {
    if depth > 3 {
        return false;
    }

    let read_dir = match std::fs::read_dir(dir) {
        Ok(read_dir) => read_dir,
        Err(_) => return false,
    };

    for entry in read_dir.flatten() {
        let path = entry.path();
        let file_name = entry.file_name();
        let name = file_name.to_string_lossy();

        if path.is_dir() {
            if should_skip_project_dir(&name) {
                continue;
            }
            if scan_for_meaningful_files(&path, depth + 1) {
                return true;
            }
            continue;
        }

        if is_meaningful_project_file(&name) {
            return true;
        }
    }

    false
}

fn should_skip_project_dir(name: &str) -> bool {
    matches!(
        name,
        ".git"
            | ".buildloop"
            | ".foundry"
            | "target"
            | "node_modules"
            | ".venv"
            | "venv"
            | "__pycache__"
            | ".pytest_cache"
            | ".ruff_cache"
            | ".build-venv"
            | "dist"
            | "build"
            | ".next"
            | ".turbo"
            | "coverage"
            | "vendor"
    )
}

fn is_meaningful_project_file(name: &str) -> bool {
    if matches!(
        name,
        "SPEC.md" | "TASKS.md" | "ARCHITECTURE.md" | "IMPL_PLAN.md"
    ) {
        return true;
    }

    if matches!(name, "README.md" | "CLAUDE.md" | ".gitignore" | ".DS_Store") {
        return false;
    }

    if matches!(
        name,
        "Cargo.toml"
            | "Cargo.lock"
            | "package.json"
            | "package-lock.json"
            | "pnpm-lock.yaml"
            | "yarn.lock"
            | "tsconfig.json"
            | "pyproject.toml"
            | "requirements.txt"
            | "go.mod"
            | "go.sum"
            | "pom.xml"
            | "build.gradle"
            | "build.gradle.kts"
            | "Gemfile"
            | "composer.json"
            | "Dockerfile"
            | "docker-compose.yml"
            | "docker-compose.yaml"
            | "Makefile"
            | "justfile"
    ) {
        return true;
    }

    Path::new(name)
        .extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| {
            matches!(
                ext,
                "rs" | "js"
                    | "jsx"
                    | "ts"
                    | "tsx"
                    | "py"
                    | "go"
                    | "java"
                    | "kt"
                    | "rb"
                    | "php"
                    | "c"
                    | "h"
                    | "cc"
                    | "cpp"
                    | "cs"
                    | "swift"
                    | "scala"
                    | "ex"
                    | "exs"
                    | "sh"
                    | "sql"
            )
        })
        .unwrap_or(false)
}

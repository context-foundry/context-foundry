use crossterm::event::{self, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use std::path::Path;

use crate::agent::AgentRole;
use crate::utils::truncate_str;
use crate::{task, tui};

use super::contract::ContractPaths;
use super::state::{FileEntry, TaskPipelineHistory};
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
        // Vestigial actions vec -- kept for struct compatibility, no longer rendered
        let actions = vec![StartupAction::ScanProject];

        let file_tree = build_file_tree(project_dir);
        let file_preview_content = if let Some(first) = file_tree.first() {
            if !first.is_dir {
                load_file_preview(&first.path)
            } else {
                Vec::new()
            }
        } else {
            Vec::new()
        };

        Self {
            scenario,
            plan_status,
            has_spec: contract_paths.spec_path.exists(),
            selected_action: 0,
            actions,
            entering_intent: true, // always show input
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
            file_tree,
            explorer_selected: 0,
            explorer_scroll: 0,
            file_preview_content,
            placeholder_tick: 0,
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
}

// ─── File Tree ───────────────────────────────────────────────

fn build_file_tree(project_dir: &Path) -> Vec<FileEntry> {
    let mut entries = Vec::new();
    build_file_tree_recursive(project_dir, project_dir, 0, &mut entries);
    entries
}

fn build_file_tree_recursive(
    base_dir: &Path,
    dir: &Path,
    depth: usize,
    entries: &mut Vec<FileEntry>,
) {
    if depth > 3 {
        return;
    }

    let read_dir = match std::fs::read_dir(dir) {
        Ok(rd) => rd,
        Err(_) => return,
    };

    let mut items: Vec<_> = read_dir.flatten().collect();
    items.sort_by(|a, b| {
        let a_dir = a.path().is_dir();
        let b_dir = b.path().is_dir();
        b_dir.cmp(&a_dir).then_with(|| {
            a.file_name()
                .to_string_lossy()
                .to_lowercase()
                .cmp(&b.file_name().to_string_lossy().to_lowercase())
        })
    });

    for item in &items {
        let file_name = item.file_name().to_string_lossy().to_string();
        let path = item.path();
        let is_dir = path.is_dir();

        if is_dir && should_skip_project_dir(&file_name) {
            continue;
        }

        let is_cf_highlight = is_context_foundry_file(&file_name, &path, base_dir);
        entries.push(FileEntry {
            path: path.clone(),
            name: file_name,
            depth,
            is_dir,
            is_cf_highlight,
        });

        if is_dir {
            build_file_tree_recursive(base_dir, &path, depth + 1, entries);
        }
    }
}

fn is_context_foundry_file(name: &str, path: &Path, base_dir: &Path) -> bool {
    if matches!(name, "TASKS.md" | "SPEC.md" | "CLAUDE.md") {
        return true;
    }
    let relative = path.strip_prefix(base_dir).unwrap_or(path);
    relative
        .components()
        .any(|c| c.as_os_str() == ".buildloop")
}

fn load_file_preview(path: &Path) -> Vec<String> {
    if path.is_dir() {
        return vec!["<directory>".to_string()];
    }
    match std::fs::read_to_string(path) {
        Ok(content) => content.lines().take(500).map(|l| l.to_string()).collect(),
        Err(_) => vec!["<binary or unreadable file>".to_string()],
    }
}

// ─── Event Handling ──────────────────────────────────────────

pub(super) fn handle_startup_event(state: &mut AppState, event: AppEvent) {
    match event {
        AppEvent::Key(key) => handle_startup_key(state, key),
        AppEvent::Mouse(mouse) => handle_startup_mouse(state, mouse),
        AppEvent::Paste(text) => handle_startup_paste(state, text),
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
            state.startup_scroll_debounce_ticks =
                state.startup_scroll_debounce_ticks.saturating_sub(1);
            if let Some(startup) = state.startup.as_mut() {
                startup.placeholder_tick = startup.placeholder_tick.wrapping_add(1);
            }
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
        AppEvent::OllamaStatus(connected) => {
            state.last_pattern_match_mode = Some(
                if connected { "semantic" } else { "keyword-only" }.to_string(),
            );
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
    let Some(_startup) = state.startup.as_ref() else {
        return;
    };

    // Check if the intent input should capture this key
    let is_typing_key = match key.code {
        KeyCode::Char(_) if !key.modifiers.contains(KeyModifiers::CONTROL) => true,
        KeyCode::Backspace => true,
        KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => true,
        _ => false,
    };

    if is_typing_key {
        handle_startup_intent_input(state, key);
        return;
    }

    match key.code {
        KeyCode::Tab | KeyCode::BackTab => {
            state.show_run_view = !state.show_run_view;
        }
        KeyCode::Char('m') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.run_mode = if state.run_mode == "hil" {
                "loop".into()
            } else {
                "hil".into()
            };
        }
        KeyCode::Char('f')
            if key.modifiers.contains(KeyModifiers::CONTROL)
                && state.last_orchestrator_outcome.is_some() =>
        {
            state.show_findings = !state.show_findings;
            state.findings_scroll = 0;
        }
        KeyCode::Esc => {
            state.should_quit = true;
        }
        KeyCode::Up => {
            move_explorer_selection(state, -1);
        }
        KeyCode::Down => {
            move_explorer_selection(state, 1);
        }
        KeyCode::PageUp => {
            move_explorer_selection(state, -10);
        }
        KeyCode::PageDown => {
            move_explorer_selection(state, 10);
        }
        KeyCode::Enter => {
            handle_startup_submit(state);
        }
        _ => {}
    }
}

pub(super) fn handle_startup_intent_input(state: &mut AppState, key: event::KeyEvent) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };

    match key.code {
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

// ─── Explorer Navigation ─────────────────────────────────────

fn move_explorer_selection(state: &mut AppState, delta: isize) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    if startup.file_tree.is_empty() {
        return;
    }
    let max_index = startup.file_tree.len() - 1;
    let new_index =
        (startup.explorer_selected as isize + delta).clamp(0, max_index as isize) as usize;
    if new_index == startup.explorer_selected {
        return;
    }
    startup.explorer_selected = new_index;
    // Adjust scroll to keep selection visible (estimate 20 visible rows)
    let visible_estimate: usize = 20;
    if new_index < startup.explorer_scroll {
        startup.explorer_scroll = new_index;
    } else if new_index >= startup.explorer_scroll + visible_estimate {
        startup.explorer_scroll = new_index.saturating_sub(visible_estimate) + 1;
    }
    // Load preview
    let entry = &startup.file_tree[new_index];
    startup.file_preview_content = if entry.is_dir {
        vec!["<directory>".to_string()]
    } else {
        load_file_preview(&entry.path)
    };
}

fn set_explorer_selection(state: &mut AppState, index: usize) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    if index >= startup.file_tree.len() {
        return;
    }
    startup.explorer_selected = index;
    let visible_estimate: usize = 20;
    if index < startup.explorer_scroll {
        startup.explorer_scroll = index;
    } else if index >= startup.explorer_scroll + visible_estimate {
        startup.explorer_scroll = index.saturating_sub(visible_estimate) + 1;
    }
    let entry = &startup.file_tree[index];
    startup.file_preview_content = if entry.is_dir {
        vec!["<directory>".to_string()]
    } else {
        load_file_preview(&entry.path)
    };
}

// ─── Submit Handling ─────────────────────────────────────────

fn handle_startup_submit(state: &mut AppState) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    let text = startup.intent_input.trim().to_string();
    let scenario = startup.scenario;
    startup.intent_input.clear();
    startup.status_message = None;

    match scenario {
        StartupScenario::QueueReady => {
            if text.is_empty() {
                // Resume building the existing queue
                state.pending_transition = Some(PendingTransition::StartBuild);
            } else {
                let label = format!("Add: {}", truncate_str(&text, 48));
                state.pending_transition =
                    Some(PendingTransition::AppendTasks(AppendTasksRequest {
                        description: text,
                        label,
                        seed_spec_from_description: false,
                    }));
            }
        }
        StartupScenario::QueueComplete => {
            if text.is_empty() {
                // Scan for new work
                state.pending_transition = Some(PendingTransition::StartPlanning {
                    user_intent: None,
                    label: "Scan project".to_string(),
                });
            } else {
                let label = format!("Add: {}", truncate_str(&text, 48));
                state.pending_transition =
                    Some(PendingTransition::AppendTasks(AppendTasksRequest {
                        description: text,
                        label,
                        seed_spec_from_description: false,
                    }));
            }
        }
        StartupScenario::EmptyProject | StartupScenario::NeedsQueue => {
            if !text.is_empty() {
                // Save user's description as SPEC.md so the bootstrap scout has context.
                // This applies to both EmptyProject and NeedsQueue -- the user typed
                // something they want built, and the scout needs to read it.
                let project_dir = state.buildloop_dir.parent()
                    .unwrap_or(std::path::Path::new("."))
                    .to_path_buf();
                let spec_path = super::contract::ContractPaths::resolve(&project_dir).spec_path;
                let _ = crate::utils::atomic_write_file(
                    &spec_path,
                    format!("# Project Brief\n\n{}\n", text).as_bytes(),
                );
                // Return to startup so the user can review SPEC.md before starting.
                // The scenario will re-detect as NeedsQueue (spec exists, no tasks yet).
                state.pending_transition = Some(PendingTransition::ShowStartup {
                    message: Some("SPEC.md created -- review it, then press Enter to start.".to_string()),
                });
            } else if matches!(scenario, StartupScenario::EmptyProject) {
                // Empty project with no description -- nudge the user to type something
                if let Some(ref mut s) = state.startup {
                    s.status_message = Some(
                        "Describe what you want to build -- an empty project needs direction.".to_string(),
                    );
                }
            } else {
                // NeedsQueue with empty input -- check if SPEC.md has content
                let project_dir = state.buildloop_dir.parent()
                    .unwrap_or(std::path::Path::new("."));
                let spec_path = super::contract::ContractPaths::resolve(project_dir).spec_path;
                let spec_has_content = std::fs::read_to_string(&spec_path)
                    .map(|c| c.lines().any(|l| !l.starts_with('#') && !l.trim().is_empty()))
                    .unwrap_or(false);
                if !spec_has_content {
                    if let Some(ref mut s) = state.startup {
                        s.status_message = Some(
                            "SPEC.md is empty -- describe what to build, or it will just scan the codebase.".to_string(),
                        );
                    }
                    return;
                }
                // SPEC.md has content -- proceed with bootstrap
                let description = "Scan the project and create an initial task queue".to_string();
                let label = format!("Bootstrap: {}", truncate_str(&description, 48));
                state.pending_transition =
                    Some(PendingTransition::AppendTasks(AppendTasksRequest {
                        description,
                        label,
                        seed_spec_from_description: false,
                    }));
            }
        }
    }
}

// ─── Mouse Handling ──────────────────────────────────────────

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
            state.startup_scroll_debounce_ticks = CLICK_SCROLL_DEBOUNCE_TICKS;
            if let Some(target) =
                tui::startup_hit_test(terminal_size, state, mouse.column, mouse.row)
            {
                match target {
                    tui::StartupMouseTarget::FileEntry(index) => {
                        set_explorer_selection(state, index);
                    }
                    tui::StartupMouseTarget::PreviewLine => {}
                }
            }
        }
        MouseEventKind::ScrollUp => {
            if state.startup_scroll_debounce_ticks == 0 {
                move_explorer_selection(state, -3);
            }
        }
        MouseEventKind::ScrollDown => {
            if state.startup_scroll_debounce_ticks == 0 {
                move_explorer_selection(state, 3);
            }
        }
        _ => {}
    }
}

// ─── Startup Surface Entry ───────────────────────────────────

pub(super) fn enter_home_surface(
    project_dir: &Path,
    state: &mut AppState,
    status_message: Option<String>,
) {
    refresh_plan_counts(project_dir, state);
    refresh_git_commit_counts(project_dir, state);
    populate_task_history_from_progress(project_dir, state);
    state.project_name = resolve_project_name(project_dir);
    state.clear_agent();
    state.current_task = None;
    state.is_discovering = false;
    state.stop_after_task = false;
    state.planning = None;

    let scenario = detect_startup_scenario(project_dir);
    enter_startup_surface_for_scenario(project_dir, state, scenario, status_message);
}

/// Populate `state.task_history` from `pipeline_progress` fields parsed from TASKS.md.
/// This restores the pipeline indicators (SPID / legacy PBRF) across session restarts.
fn populate_task_history_from_progress(project_dir: &Path, state: &mut AppState) {
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;
    let tasks = match task::parse_tasks(&plan_path) {
        Ok(t) => t,
        Err(_) => return,
    };

    for t in &tasks {
        let Some(ref progress) = t.pipeline_progress else {
            continue;
        };

        // Skip tasks that already have live history from the current session.
        if state.task_history.contains_key(&t.id) {
            continue;
        }

        let chars: Vec<char> = progress.chars().collect();

        // Detect SPID format (starts with S) vs legacy PBRF format (starts with P or -)
        let is_spid = chars.first() == Some(&'S');
        let mut stages_seen = Vec::new();

        if is_spid {
            // SPID format: Scout, Plan, Implement, Verify
            if chars.first() == Some(&'S') {
                stages_seen.push(AgentRole::Scout);
            }
            if chars.get(1) == Some(&'P') {
                stages_seen.push(AgentRole::Planner);
            }
            if chars.get(2) == Some(&'I') {
                stages_seen.push(AgentRole::Builder);
            }
            if chars.get(3) == Some(&'D') || chars.get(3) == Some(&'V') {
                stages_seen.push(AgentRole::Reviewer);
            }
        } else {
            // Legacy PBRF format: Planner, Builder, Reviewer, Fixer
            if chars.first() == Some(&'P') {
                stages_seen.push(AgentRole::Planner);
            }
            if chars.get(1) == Some(&'B') {
                stages_seen.push(AgentRole::Builder);
            }
            if chars.get(2) == Some(&'R') {
                stages_seen.push(AgentRole::Reviewer);
            }
            if chars.get(3) == Some(&'F') {
                stages_seen.push(AgentRole::Fixer);
            }
        }

        let fix_passes = if is_spid {
            0
        } else if chars.get(3) == Some(&'F') {
            1
        } else {
            0
        };
        let has_bang = progress.contains('!');
        let passed_review = if has_bang { false } else { t.completed };

        let history = TaskPipelineHistory {
            fix_passes,
            passed_review,
            stages_seen,
        };

        state.task_history_order.push(t.id.clone());
        state.task_history.insert(t.id.clone(), history);
    }

    state.cap_task_history();
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

// ─── Helpers ─────────────────────────────────────────────────

fn refresh_git_commit_counts(project_dir: &Path, state: &mut AppState) {
    let output = std::process::Command::new("git")
        .args(["log", "--oneline", "--format=%s", "--", "."])
        .current_dir(project_dir)
        .output();
    if let Ok(output) = output {
        if output.status.success() {
            let log = String::from_utf8_lossy(&output.stdout);
            let mut feat = 0usize;
            let mut wip = 0usize;
            for line in log.lines() {
                if line.starts_with("feat(") {
                    feat += 1;
                } else if line.starts_with("WIP(") {
                    wip += 1;
                }
            }
            state.session_feat_commits = feat;
            state.session_wip_commits = wip;
        }
    }
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
        .map(|task| format!("{} \u{2014} {}", task.id, task.short_desc(72)))
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

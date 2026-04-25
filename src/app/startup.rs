use crossterm::event::{self, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use std::path::Path;

use crate::agent::AgentRole;
use crate::config::Config;
use crate::extensions;
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

        // Auto-select the most relevant CF file: TASKS.md > SPEC.md > UPDATED_SPECS.md > CLAUDE.md
        let priority_files = ["TASKS.md", "SPEC.md", "UPDATED_SPECS.md", "CLAUDE.md"];
        let initial_selected = priority_files
            .iter()
            .find_map(|name| {
                file_tree
                    .iter()
                    .position(|e| e.name == *name && e.is_cf_highlight)
            })
            .unwrap_or(0);

        let file_preview_content = if let Some(entry) = file_tree.get(initial_selected) {
            if !entry.is_dir {
                load_file_preview(&entry.path)
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
            explorer_selected: initial_selected,
            explorer_scroll: 0,
            file_preview_content,
            file_preview_scroll: 0,
            placeholder_tick: 0,
            preview_wrap: Config::load(project_dir).preview_wrap,
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
        let is_hidden = file_name.starts_with('.');
        let is_skipped_dir = is_dir && should_skip_dir_in_context(&file_name, dir);

        let is_cf_highlight = is_context_foundry_file(&file_name, &path, base_dir);
        let (file_size, modified) = match std::fs::metadata(&path) {
            Ok(meta) => {
                let size = meta.len();
                let mtime = meta.modified().ok();
                (size, mtime)
            }
            Err(_) => (0, None),
        };
        entries.push(FileEntry {
            path: path.clone(),
            name: file_name,
            depth,
            is_dir,
            is_cf_highlight,
            is_hidden,
            expanded: false,
            file_size: if is_dir { 0 } else { file_size },
            modified,
        });

        // Still recurse into hidden dirs (e.g. .buildloop) but not into
        // large generated dirs like node_modules, target, .git
        if is_dir && !is_skipped_dir {
            build_file_tree_recursive(base_dir, &path, depth + 1, entries);
        }
    }
}

fn is_context_foundry_file(name: &str, path: &Path, base_dir: &Path) -> bool {
    if matches!(
        name,
        "TASKS.md" | "SPEC.md" | "UPDATED_SPECS.md" | "CLAUDE.md"
    ) {
        return true;
    }
    let relative = path.strip_prefix(base_dir).unwrap_or(path);
    relative.components().any(|c| c.as_os_str() == ".buildloop")
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

pub(super) fn handle_startup_event(state: &mut AppState, event: AppEvent, config: &Config) {
    match event {
        AppEvent::Key(key) => handle_startup_key(state, key, config),
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
                if connected {
                    "semantic"
                } else {
                    "keyword-only"
                }
                .to_string(),
            );
        }
        AppEvent::LocalModels {
            lmstudio,
            ollama,
            lmstudio_opencode_map,
            opencode_warning,
        } => {
            let prev = state.selected_local_model.clone();
            let mut merged: Vec<String> = Vec::with_capacity(lmstudio.len() + ollama.len());
            for m in lmstudio.iter().chain(ollama.iter()) {
                if !merged.contains(m) {
                    merged.push(m.clone());
                }
            }
            state.lmstudio_models = lmstudio;
            state.ollama_models = ollama;
            state.local_models = merged;
            state.lmstudio_id_to_opencode_path = lmstudio_opencode_map;
            if let Some(msg) = opencode_warning {
                state.log(msg);
            }
            if let Some(idx) = state.local_models.iter().position(|m| m == &prev) {
                state.local_model_cursor = idx;
            } else {
                state.local_model_cursor = 0;
            }
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

pub(super) fn handle_startup_key(state: &mut AppState, key: event::KeyEvent, config: &Config) {
    let Some(_startup) = state.startup.as_ref() else {
        return;
    };

    // Extension panel navigation (when focused on extensions pane)
    if state.focused_pane == crate::app::state::TuiPane::Extensions
        && !state.available_extensions.is_empty()
    {
        match key.code {
            KeyCode::Up => {
                if state.extensions_cursor > 0 {
                    state.extensions_cursor -= 1;
                }
                return;
            }
            KeyCode::Down => {
                if state.extensions_cursor + 1 < state.available_extensions.len() {
                    state.extensions_cursor += 1;
                }
                return;
            }
            KeyCode::Char(' ') => {
                // Toggle selection
                if let Some(ext) = state.available_extensions.get_mut(state.extensions_cursor) {
                    ext.selected = !ext.selected;
                }
                // Persist to .foundry.json
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."));
                let selected: Vec<String> = state
                    .available_extensions
                    .iter()
                    .filter(|e| e.selected)
                    .map(|e| e.name.clone())
                    .collect();
                Config::save_extensions(project_dir, &selected);
                return;
            }
            KeyCode::Enter => {
                // Toggle if input is empty; otherwise fall through to submit
                let input_empty = state
                    .startup
                    .as_ref()
                    .is_none_or(|s| s.intent_input.is_empty());
                if input_empty {
                    if let Some(ext) = state.available_extensions.get_mut(state.extensions_cursor) {
                        ext.selected = !ext.selected;
                    }
                    let project_dir = state
                        .buildloop_dir
                        .parent()
                        .unwrap_or(std::path::Path::new("."));
                    let selected: Vec<String> = state
                        .available_extensions
                        .iter()
                        .filter(|e| e.selected)
                        .map(|e| e.name.clone())
                        .collect();
                    Config::save_extensions(project_dir, &selected);
                    return;
                }
                // Fall through to normal Enter handling
            }
            KeyCode::Esc => {
                state.focused_pane = crate::app::state::TuiPane::Explorer;
                return;
            }
            KeyCode::Char('e') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                state.focused_pane = crate::app::state::TuiPane::Explorer;
                return;
            }
            _ => {
                // Fall through to normal key handling
            }
        }
    }

    // Settings overlay intercept -- must be before is_typing_key so '?' is not
    // consumed as intent input and Up/Down/Enter/Space navigate the overlay.
    if key.code == KeyCode::Char('?') && !key.modifiers.contains(KeyModifiers::CONTROL) {
        let was_open = state.show_settings_overlay;
        state.show_settings_overlay = !state.show_settings_overlay;
        state.settings_overlay_cursor = 0;
        if !was_open {
            if let Some(tx) = state.event_tx.clone() {
                let ollama_url = config.ollama_url.clone();
                tokio::spawn(async move {
                    let discovery = super::fetch_local_models(ollama_url).await;
                    let _ = tx.send(AppEvent::LocalModels {
                        lmstudio: discovery.lmstudio,
                        ollama: discovery.ollama,
                        lmstudio_opencode_map: discovery.lmstudio_opencode_map,
                        opencode_warning: discovery.opencode_warning,
                    });
                });
            }
        }
        return;
    }
    if state.show_settings_overlay {
        match key.code {
            KeyCode::Esc | KeyCode::Char('q') => {
                state.show_settings_overlay = false;
                return;
            }
            KeyCode::Up => {
                state.settings_overlay_cursor =
                    state.settings_overlay_cursor.saturating_sub(1);
                return;
            }
            KeyCode::Down => {
                state.settings_overlay_cursor =
                    (state.settings_overlay_cursor + 1).min(2);
                return;
            }
            KeyCode::Enter | KeyCode::Char(' ') => {
                super::cycle_settings_cursor_startup(state);
                return;
            }
            KeyCode::Left => {
                super::cycle_settings_left_startup(state);
                return;
            }
            KeyCode::Right => {
                super::cycle_settings_right_startup(state);
                return;
            }
            _ => {
                // All other keys are swallowed while overlay is open.
                return;
            }
        }
    }

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
        KeyCode::Char('e') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            if !state.available_extensions.is_empty() {
                if state.focused_pane == crate::app::state::TuiPane::Extensions {
                    state.focused_pane = crate::app::state::TuiPane::Explorer;
                } else {
                    state.focused_pane = crate::app::state::TuiPane::Extensions;
                    state.extensions_cursor = 0;
                }
            }
        }
        KeyCode::Tab | KeyCode::BackTab => {
            state.show_run_view = !state.show_run_view;
        }
        KeyCode::Char('m') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.run_mode = match state.run_mode.as_str() {
                "auto" => "sprint".into(),
                "sprint" => "review".into(),
                _ => "auto".into(),
            };
            let project_dir = state
                .buildloop_dir
                .parent()
                .unwrap_or(std::path::Path::new("."));
            Config::save_run_mode(project_dir, &state.run_mode);
            // Warn if gh CLI not available when switching to review mode
            if state.run_mode == "review" {
                if !crate::git::is_gh_authenticated() {
                    if let Some(ref mut s) = state.startup {
                        s.status_message = Some(
                            "Warning: gh CLI not installed or not authenticated -- PR auto-resume won't work in Review mode".into(),
                        );
                    }
                }
            } else {
                // Clear any previous gh warning when switching away from review
                if let Some(ref mut s) = state.startup {
                    if s.status_message
                        .as_ref()
                        .is_some_and(|m| m.contains("gh CLI"))
                    {
                        s.status_message = None;
                    }
                }
            }
        }
        // Sandbox toggle removed -- sandbox is always on, only configurable
        // via .foundry.json (reserved for implementers).
        KeyCode::Char('s') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            if let Some(ref mut s) = state.startup {
                s.status_message =
                    Some("Sandbox toggle disabled -- override via .foundry.json only".into());
            }
        }
        KeyCode::Char('d') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            if state.builder_model_specs.len() >= 2 {
                use crate::app::state::DualSelection;
                let specs_len = state.builder_model_specs.len();
                let next = state.dual_selection.next_for(specs_len);
                state.dual_selection = next;
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."));
                Config::save_dual_selection(project_dir, next.as_str());
                // Show label for current selection
                let label = match next {
                    DualSelection::First => {
                        let (p, m) = Config::parse_model_spec(&state.builder_model_specs[0]);
                        format!("Pipeline: {} only", Config::display_provider_model(&p, &m))
                    }
                    DualSelection::Second => {
                        let (p, m) = Config::parse_model_spec(&state.builder_model_specs[1]);
                        format!("Pipeline: {} only", Config::display_provider_model(&p, &m))
                    }
                    DualSelection::Third => {
                        let (p, m) = Config::parse_model_spec(&state.builder_model_specs[2]);
                        format!("Pipeline: {} only", Config::display_provider_model(&p, &m))
                    }
                    DualSelection::Both => {
                        let (p0, m0) = Config::parse_model_spec(&state.builder_model_specs[0]);
                        let (p1, m1) = Config::parse_model_spec(&state.builder_model_specs[1]);
                        format!(
                            "Pipeline: {} + {}",
                            Config::display_provider_model(&p0, &m0),
                            Config::display_provider_model(&p1, &m1)
                        )
                    }
                    DualSelection::Off => "Pipeline: default (single)".into(),
                };
                if let Some(ref mut s) = state.startup {
                    s.status_message = Some(label);
                }
            } else if let Some(ref mut s) = state.startup {
                s.status_message = Some(
                    "Dual-build requires builder_models with 2+ entries in .foundry.json".into(),
                );
            }
        }
        KeyCode::Char('t') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
            state.tui_theme = new_theme;
            state.log(format!("Theme: {}", name));
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
        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
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
            let input_empty = state
                .startup
                .as_ref()
                .is_none_or(|s| s.intent_input.is_empty());
            // QueueReady and QueueComplete have meaningful empty-Enter actions
            // (start build / scan), so prioritize submit over explorer toggle.
            let scenario_has_empty_action = state.startup.as_ref().is_some_and(|s| {
                matches!(
                    s.scenario,
                    StartupScenario::QueueReady | StartupScenario::QueueComplete
                )
            });
            let on_file_pane = matches!(
                state.focused_pane,
                crate::app::state::TuiPane::Explorer | crate::app::state::TuiPane::Preview
            );
            if input_empty && on_file_pane && !scenario_has_empty_action {
                handle_explorer_enter(state);
            } else {
                handle_startup_submit(state);
            }
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
        KeyCode::Char('n') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            // Clear input and delete UPDATED_SPECS.md so next startup is fresh
            startup.intent_input.clear();
            let project_dir = state
                .buildloop_dir
                .parent()
                .unwrap_or(std::path::Path::new("."));
            let updated_specs = super::contract::ContractPaths::resolve(project_dir)
                .updated_specs_path
                .clone();
            if let Err(e) = std::fs::remove_file(&updated_specs) {
                if e.kind() != std::io::ErrorKind::NotFound {
                    eprintln!(
                        "Warning: failed to remove {}: {}",
                        updated_specs.display(),
                        e
                    );
                }
            }
        }
        KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
            startup.intent_input.push(c);
        }
        _ => {}
    }
}

pub(super) fn toggle_expand_all(startup: &mut StartupState) {
    let any_collapsed = startup.file_tree.iter().any(|e| e.is_dir && !e.expanded);
    let new_state = any_collapsed;
    for entry in startup.file_tree.iter_mut() {
        if entry.is_dir {
            entry.expanded = new_state;
        }
    }
    let vis = startup.visible_indices();
    if vis.is_empty() {
        startup.explorer_selected = 0;
        startup.explorer_scroll = 0;
        return;
    }
    if !vis.contains(&startup.explorer_selected) {
        startup.explorer_selected = vis[0];
    }
    let vis_pos = vis
        .iter()
        .position(|&i| i == startup.explorer_selected)
        .unwrap_or(0);
    if vis_pos < startup.explorer_scroll {
        startup.explorer_scroll = vis_pos;
    }
}

pub(super) fn toggle_preview_wrap(startup: &mut StartupState, project_dir: &Path) {
    startup.preview_wrap = !startup.preview_wrap;
    Config::save_preview_wrap(project_dir, startup.preview_wrap);
}

// ─── Explorer Navigation ─────────────────────────────────────

fn move_explorer_selection(state: &mut AppState, delta: isize) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    let vis = startup.visible_indices();
    if vis.is_empty() {
        return;
    }
    // Find current position in visible list
    let cur_pos = vis
        .iter()
        .position(|&i| i == startup.explorer_selected)
        .unwrap_or(0);
    let max_pos = vis.len() - 1;
    let new_pos = (cur_pos as isize + delta).clamp(0, max_pos as isize) as usize;
    let new_index = vis[new_pos];
    if new_index == startup.explorer_selected {
        return;
    }
    startup.explorer_selected = new_index;
    // Adjust scroll to keep selection visible (estimate 20 visible rows)
    let visible_estimate: usize = 20;
    if new_pos < startup.explorer_scroll {
        startup.explorer_scroll = new_pos;
    } else if new_pos >= startup.explorer_scroll + visible_estimate {
        startup.explorer_scroll = new_pos.saturating_sub(visible_estimate) + 1;
    }
    // Load preview
    let entry = &startup.file_tree[new_index];
    startup.file_preview_content = if entry.is_dir {
        vec!["<directory>".to_string()]
    } else {
        load_file_preview(&entry.path)
    };
    startup.file_preview_scroll = 0;
}

fn set_explorer_selection(state: &mut AppState, index: usize) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    if index >= startup.file_tree.len() {
        return;
    }
    startup.explorer_selected = index;
    let vis = startup.visible_indices();
    let vis_pos = vis.iter().position(|&i| i == index).unwrap_or(0);
    let visible_estimate: usize = 20;
    if vis_pos < startup.explorer_scroll {
        startup.explorer_scroll = vis_pos;
    } else if vis_pos >= startup.explorer_scroll + visible_estimate {
        startup.explorer_scroll = vis_pos.saturating_sub(visible_estimate) + 1;
    }
    let entry = &startup.file_tree[index];
    startup.file_preview_content = if entry.is_dir {
        vec!["<directory>".to_string()]
    } else {
        load_file_preview(&entry.path)
    };
    startup.file_preview_scroll = 0;
}

fn handle_explorer_enter(state: &mut AppState) {
    let Some(startup) = state.startup.as_mut() else {
        return;
    };
    let selected = startup.explorer_selected;
    if selected >= startup.file_tree.len() {
        return;
    }
    if startup.file_tree[selected].is_dir {
        // Toggle expanded/collapsed
        startup.file_tree[selected].expanded = !startup.file_tree[selected].expanded;
        // If collapsing, check if explorer_selected is now invisible
        if !startup.file_tree[selected].expanded {
            let vis = startup.visible_indices();
            if !vis.contains(&startup.explorer_selected) {
                startup.explorer_selected = selected;
            }
        }
    } else {
        // Open file in external editor
        let file_path = startup.file_tree[selected].path.clone();
        state.pending_transition = Some(PendingTransition::OpenExternalEditor { file_path });
    }
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

    // Persist enhancement description to UPDATED_SPECS.md (not for new projects)
    if !text.is_empty() && scenario != StartupScenario::EmptyProject {
        let project_dir = state
            .buildloop_dir
            .parent()
            .unwrap_or(std::path::Path::new("."));
        let updated_specs = super::contract::ContractPaths::resolve(project_dir)
            .updated_specs_path
            .clone();
        if let Err(e) = crate::utils::atomic_write_file(&updated_specs, text.as_bytes()) {
            eprintln!(
                "Warning: failed to write UPDATED_SPECS to {}: {} -- enhancement request may be lost",
                updated_specs.display(), e
            );
        }
    }

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
        StartupScenario::EmptyProject => {
            if !text.is_empty() {
                // Save user's description as SPEC.md so the bootstrap scout has context.
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."))
                    .to_path_buf();
                let spec_path = super::contract::ContractPaths::resolve(&project_dir).spec_path;
                if let Err(e) = crate::utils::atomic_write_file(
                    &spec_path,
                    format!("# Project Brief\n\n{}\n", text).as_bytes(),
                ) {
                    eprintln!(
                        "Warning: failed to write SPEC.md to {}: {} -- project brief was not saved",
                        spec_path.display(),
                        e
                    );
                }
                // Return to startup so the user can review SPEC.md before starting.
                // The scenario will re-detect as NeedsQueue (spec exists, no tasks yet).
                state.pending_transition = Some(PendingTransition::ShowStartup {
                    message: Some(
                        "SPEC.md created -- review it, then press Enter to start.".to_string(),
                    ),
                });
            } else {
                // Empty project with no description -- nudge the user to type something
                if let Some(ref mut s) = state.startup {
                    s.status_message = Some(
                        "Describe what you want to build -- an empty project needs direction."
                            .to_string(),
                    );
                }
            }
        }
        StartupScenario::NeedsQueue => {
            if !text.is_empty() {
                // Spec already exists -- treat user text as a task description
                let label = format!("Bootstrap: {}", truncate_str(&text, 48));
                state.pending_transition =
                    Some(PendingTransition::AppendTasks(AppendTasksRequest {
                        description: text,
                        label,
                        seed_spec_from_description: false,
                    }));
            } else {
                // NeedsQueue with empty input -- check if SPEC.md has content
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."));
                let spec_path = super::contract::ContractPaths::resolve(project_dir).spec_path;
                let spec_has_content = std::fs::read_to_string(&spec_path)
                    .map(|c| {
                        c.lines()
                            .any(|l| !l.starts_with('#') && !l.trim().is_empty())
                    })
                    .unwrap_or(false);
                if !spec_has_content {
                    if let Some(ref mut s) = state.startup {
                        s.status_message = Some(
                            "SPEC.md is empty -- describe what you want to build first."
                                .to_string(),
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
                        state.focused_pane = crate::app::state::TuiPane::Explorer;
                        set_explorer_selection(state, index);
                        // Toggle folder expanded/collapsed on click
                        if let Some(startup) = state.startup.as_mut() {
                            if index < startup.file_tree.len() && startup.file_tree[index].is_dir {
                                startup.file_tree[index].expanded =
                                    !startup.file_tree[index].expanded;
                            }
                        }
                    }
                    tui::StartupMouseTarget::PreviewLine => {
                        state.focused_pane = crate::app::state::TuiPane::Preview;
                    }
                    tui::StartupMouseTarget::ExtensionEntry(index) => {
                        state.focused_pane = crate::app::state::TuiPane::Extensions;
                        state.extensions_cursor = index;
                        // Toggle the clicked extension
                        if let Some(ext) = state.available_extensions.get_mut(index) {
                            ext.selected = !ext.selected;
                        }
                        let project_dir = state
                            .buildloop_dir
                            .parent()
                            .unwrap_or(std::path::Path::new("."));
                        let selected: Vec<String> = state
                            .available_extensions
                            .iter()
                            .filter(|e| e.selected)
                            .map(|e| e.name.clone())
                            .collect();
                        Config::save_extensions(project_dir, &selected);
                    }
                    tui::StartupMouseTarget::ExpandAllToggle => {
                        state.focused_pane = crate::app::state::TuiPane::Explorer;
                        if let Some(startup) = state.startup.as_mut() {
                            toggle_expand_all(startup);
                        }
                    }
                    tui::StartupMouseTarget::WrapToggle => {
                        state.focused_pane = crate::app::state::TuiPane::Preview;
                        let project_dir = state
                            .buildloop_dir
                            .parent()
                            .unwrap_or(std::path::Path::new("."));
                        if let Some(startup) = state.startup.as_mut() {
                            toggle_preview_wrap(startup, project_dir);
                        }
                    }
                }
            } else {
                // Clicked outside file/preview/extension panes (e.g. input area)
                // Reset focus so Enter submits instead of opening editor
                state.focused_pane = crate::app::state::TuiPane::AgentOutput;
            }
        }
        MouseEventKind::ScrollUp => {
            if state.startup_scroll_debounce_ticks == 0 {
                match state.focused_pane {
                    crate::app::state::TuiPane::Preview => {
                        if let Some(startup) = state.startup.as_mut() {
                            startup.file_preview_scroll =
                                startup.file_preview_scroll.saturating_sub(3);
                        }
                    }
                    _ => {
                        move_explorer_selection(state, -3);
                    }
                }
            }
        }
        MouseEventKind::ScrollDown => {
            if state.startup_scroll_debounce_ticks == 0 {
                match state.focused_pane {
                    crate::app::state::TuiPane::Preview => {
                        if let Some(startup) = state.startup.as_mut() {
                            let max_scroll = startup.file_preview_content.len().saturating_sub(1);
                            startup.file_preview_scroll =
                                (startup.file_preview_scroll + 3).min(max_scroll);
                        }
                    }
                    _ => {
                        move_explorer_selection(state, 3);
                    }
                }
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
    populate_task_history_from_progress(project_dir, state);
    state.project_name = resolve_project_name(project_dir);
    state.clear_agent();
    state.reset_dual_build();
    state.current_task = None;
    state.is_discovering = false;
    state.stop_after_task = false;
    state.awaiting_commit_approval = false;
    state.approval_task_id = None;
    state.approval_proposed_type = None;
    state.approval_session_id = None;
    state.commit_approval_gates.clear();
    state.commit_approval_results.clear();
    state.pending_approvals.clear();
    state.awaiting_review = false;
    state.review_gates.clear();
    state.review_session_id = None;
    state.pending_reviews.clear();
    state.awaiting_pr = None;
    state.pr_poll_last_check = None;
    state.planning = None;

    let scenario = detect_startup_scenario(project_dir);
    enter_startup_surface_for_scenario(project_dir, state, scenario, status_message);

    // Discover extensions and merge with config selection
    let discovered = extensions::discover_extensions(project_dir);
    let config = Config::load(project_dir);
    state.available_extensions = discovered
        .iter()
        .map(|ext| {
            let selected = config.extensions.contains(&ext.name);
            let description = extensions::extract_description(&ext.claude_md_path);
            let pattern_count = extensions::count_extension_patterns(&ext.patterns_dir);
            crate::app::state::ExtensionDisplayInfo {
                name: ext.name.clone(),
                selected,
                description,
                pattern_count,
            }
        })
        .collect();
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
                // Skip generic placeholder headers -- fall through to directory name
                if !name.is_empty()
                    && name != "Project Brief"
                    && name != "Specification"
                    && name != "Architecture"
                {
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
    populate_task_history_from_progress(project_dir, state);
    state.project_name = resolve_project_name(project_dir);
    state.clear_agent();
    state.reset_dual_build();
    state.current_task = None;
    state.is_discovering = false;
    state.stop_after_task = false;
    state.awaiting_commit_approval = false;
    state.approval_task_id = None;
    state.approval_proposed_type = None;
    state.approval_session_id = None;
    state.commit_approval_gates.clear();
    state.commit_approval_results.clear();
    state.pending_approvals.clear();
    state.awaiting_review = false;
    state.review_gates.clear();
    state.review_session_id = None;
    state.pending_reviews.clear();
    state.awaiting_pr = None;
    state.pr_poll_last_check = None;
    state.planning = None;

    let scenario = detect_startup_scenario(project_dir);
    enter_startup_surface_for_scenario(project_dir, state, scenario, status_message);

    // Discover extensions and merge with config selection
    let discovered = extensions::discover_extensions(project_dir);
    let config = Config::load(project_dir);
    state.available_extensions = discovered
        .iter()
        .map(|ext| {
            let selected = config.extensions.contains(&ext.name);
            let description = extensions::extract_description(&ext.claude_md_path);
            let pattern_count = extensions::count_extension_patterns(&ext.patterns_dir);
            crate::app::state::ExtensionDisplayInfo {
                name: ext.name.clone(),
                selected,
                description,
                pattern_count,
            }
        })
        .collect();
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
    if let Some(ref startup) = state.startup {
        if let Some(ref ctx) = startup.git_context {
            state.git_initialized = true;
            state.git_branch = ctx.branch.clone();
            state.git_remote = ctx.remote.clone();
            state.git_dirty_count = ctx.dirty_count;
        } else {
            state.git_initialized = false;
            state.git_branch.clear();
            state.git_remote = None;
            state.git_dirty_count = 0;
        }
    }
    state.startup_scroll_debounce_ticks = 0;
}

// ─── Helpers ─────────────────────────────────────────────────

fn refresh_plan_counts(project_dir: &Path, state: &mut AppState) {
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;
    match task::parse_tasks(&plan_path) {
        Ok(tasks) => {
            state.update_counts(&tasks);
            state.task_queue = tasks;
        }
        Err(_) => {
            state.total_count = 0;
            state.completed_count = 0;
            state.task_queue.clear();
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

pub(crate) fn classify_plan_status(plan_path: &Path) -> PlanStatus {
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

pub(crate) fn detect_startup_scenario(project_dir: &Path) -> StartupScenario {
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

/// Check if a directory should be skipped based on its name and parent path.
/// Filters `.buildloop/logs/` while allowing `logs/` in user project directories.
fn should_skip_dir_in_context(name: &str, parent_dir: &Path) -> bool {
    if should_skip_project_dir(name) {
        return true;
    }
    // Filter .buildloop/logs/ — these are internal JSONL agent log files
    if name == "logs" {
        if let Some(parent_name) = parent_dir.file_name() {
            return parent_name == ".buildloop";
        }
    }
    false
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

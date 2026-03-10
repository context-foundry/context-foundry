use anyhow::{Context, Result};
use chrono::Utc;
use crossterm::event::{self, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use ratatui::layout::Rect;
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::Ordering,
};
use tokio::{sync::mpsc, task::JoinHandle};

use crate::{agent::AgentOutputEvent, tui};

use super::{
    super::{
        app::spawn_terminal_event_reader,
        attachments::{
            append_attachment_specs_for_paths, cycle_attachment_manager_selection,
            infer_attachment_spec_from_selected_path, open_attachment_manager,
            pick_attachment_paths, queue_selected_execution_contract_attachment_action,
            remove_selected_execution_contract_attachments, toggle_selected_attachment_mark,
        },
        contracts::{
            create_execution_contract, cycle_execution_contract,
            delete_selected_execution_contract, edit_selected_execution_contract,
            persist_selected_execution_contract,
        },
        model::{
            DeleteConfirmationState, EditorChoice, EditorGuideState, FocusedPane,
            PendingStudioAction, SessionStatus, SessionStopConfirmationState, StudioEvent,
            MAX_PROMPT_BYTES, STUDIO_ROOT_DIR, STUDIO_SELECTED_EDITOR_FILE,
        },
        providers::display_model_name,
        scan::scan_project,
        session::start_sessions,
        state::{append_prompt_text, cycle_theme, format_byte_count, StudioState},
    },
    layout::{
        apply_resize_drag, current_studio_layout, pane_at_position, prompt_pane_layout,
        resize_handle_at, wrap_text_lines, ResizeDragState, StudioLayout,
    },
};

pub(in crate::studio) fn handle_event(
    state: &mut StudioState,
    event: StudioEvent,
    tx: &mpsc::UnboundedSender<StudioEvent>,
) {
    match event {
        StudioEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
        }
        StudioEvent::Key(key) => {
            if state.session_stop_confirmation.is_some() {
                handle_session_stop_confirmation_key(state, key);
            } else if state.delete_confirmation.is_some() {
                handle_delete_confirmation_key(state, key);
            } else if state.editor_guide.is_some() {
                handle_editor_guide_key(state, key);
            } else if state.attachment_manager.is_some() {
                handle_attachment_manager_key(state, key);
            } else if is_quit_key(key) {
                request_quit(state);
            } else if state.is_editing_prompt {
                handle_prompt_edit_key(state, key);
            } else {
                handle_global_key(state, key, tx);
            }
        }
        StudioEvent::Mouse(mouse) => {
            if state.editor_guide.is_none()
                && state.delete_confirmation.is_none()
                && state.session_stop_confirmation.is_none()
                && state.attachment_manager.is_none()
            {
                handle_mouse_event(state, mouse)
            }
        }
        StudioEvent::Paste(text) => {
            if state.editor_guide.is_none()
                && state.delete_confirmation.is_none()
                && state.session_stop_confirmation.is_none()
                && state.attachment_manager.is_none()
            {
                if !state.is_editing_prompt {
                    set_focused_pane(state, FocusedPane::Prompt);
                    state.is_editing_prompt = true;
                    state.log("prompt edit mode on");
                }

                let outcome = append_prompt_text(state, &text);
                if outcome.truncated_bytes > 0 {
                    state.log(format!(
                        "prompt truncated after paste; kept {} KB, dropped {}",
                        MAX_PROMPT_BYTES / 1024,
                        format_byte_count(outcome.truncated_bytes)
                    ));
                }
            }
        }
        StudioEvent::Quit => {
            request_quit(state);
        }
        StudioEvent::SessionOutput { session_id, event } => {
            if let Some(session) = state.sessions.iter_mut().find(|s| s.id == session_id) {
                session.event_count += 1;
                session.last_event_at = Some(Utc::now());
                match event {
                    AgentOutputEvent::Text(text) => session.output.push(text),
                    AgentOutputEvent::ToolUse {
                        tool,
                        input_preview,
                    } => {
                        if input_preview.is_empty() {
                            session.output.push(format!("[tool] {}", tool));
                        } else {
                            session
                                .output
                                .push(format!("[tool] {} — {}", tool, input_preview));
                        }
                    }
                    AgentOutputEvent::ToolResult { output_preview } => {
                        if !output_preview.is_empty() {
                            session.output.push(format!("[result] {}", output_preview));
                        }
                    }
                    AgentOutputEvent::Stderr(line) => {
                        session.output.push(format!("[stderr] {}", line));
                    }
                    AgentOutputEvent::Result(text) => {
                        session.output.push(String::new());
                        for line in text.lines().take(24) {
                            session.output.push(line.to_string());
                        }
                    }
                }
            }
        }
        StudioEvent::SessionFinished {
            session_id,
            success,
            artifacts,
            error,
        } => {
            let mut completion_log: Option<(String, usize)> = None;
            state.session_controls.remove(&session_id);
            if let Some(session) = state.sessions.iter_mut().find(|s| s.id == session_id) {
                session.status = if success {
                    SessionStatus::Succeeded
                } else if session.stop_requested {
                    SessionStatus::Stopped
                } else {
                    SessionStatus::Failed
                };
                session.finished_at = Some(Utc::now());
                session.artifacts = artifacts;
                session.error = if session.stop_requested { None } else { error };
                completion_log = Some((
                    format!(
                        "{} session {} ({})",
                        session.provider,
                        session.status.label(),
                        display_model_name(&session.model)
                    ),
                    session.artifacts.len(),
                ));
            }
            if let Some((message, artifact_count)) = completion_log {
                state.log(message);
                if artifact_count > 0 {
                    state.log(format!("{} artifact(s) captured", artifact_count));
                }
            }
        }
    }
}

fn handle_editor_guide_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Enter => {
            if let Some(guide) = state.editor_guide.take() {
                state.pending_action = Some(guide.action);
            }
        }
        KeyCode::Char('v') => {
            cycle_editor_choice(state);
        }
        KeyCode::Esc | KeyCode::Char('q') => {
            state.editor_guide = None;
            state.log("editor launch canceled");
        }
        _ => {}
    }
}

fn handle_delete_confirmation_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Char(c) if c.eq_ignore_ascii_case(&'y') => {
            state.delete_confirmation = None;
            if let Err(err) = delete_selected_execution_contract(state) {
                state.log(format!("contract delete failed: {}", err));
            }
        }
        KeyCode::Char(c) if c.eq_ignore_ascii_case(&'n') => {
            state.delete_confirmation = None;
            state.log("contract delete canceled");
        }
        KeyCode::Esc => {
            state.delete_confirmation = None;
            state.log("contract delete canceled");
        }
        _ => {}
    }
}

fn handle_session_stop_confirmation_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Char(c) if c.eq_ignore_ascii_case(&'y') => {
            confirm_stop_selected_session(state);
        }
        KeyCode::Char(c) if c.eq_ignore_ascii_case(&'n') => {
            state.session_stop_confirmation = None;
            state.log("session stop canceled");
        }
        KeyCode::Esc => {
            state.session_stop_confirmation = None;
            state.log("session stop canceled");
        }
        _ => {}
    }
}

fn handle_attachment_manager_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Esc | KeyCode::Enter | KeyCode::Char('q') => {
            state.attachment_manager = None;
        }
        KeyCode::Char('a') => {
            if let Err(err) = queue_selected_execution_contract_attachment_action(state) {
                state.log(format!("contract attachment edit failed: {}", err));
            }
        }
        KeyCode::Char('d') => {
            if let Err(err) = remove_selected_execution_contract_attachments(state) {
                state.log(format!("attachment delete failed: {}", err));
            }
        }
        KeyCode::Char(' ') => toggle_selected_attachment_mark(state),
        KeyCode::Up => cycle_attachment_manager_selection(state, false),
        KeyCode::Down => cycle_attachment_manager_selection(state, true),
        _ => {}
    }
}

fn request_quit(state: &mut StudioState) {
    if state.shutdown_initiated {
        state.should_quit = true;
        return;
    }

    state.shutdown_initiated = true;
    if state.has_running_sessions() {
        state.log(format!(
            "shutting down {} active session(s)",
            state.session_controls.len()
        ));
        cancel_running_sessions(state);
    }
    state.should_quit = true;
}

pub(in crate::studio) fn cancel_running_sessions(state: &mut StudioState) {
    for control in state.session_controls.values() {
        control.cancel_flag.store(true, Ordering::Relaxed);
    }
}

pub(in crate::studio) fn can_stop_selected_session(state: &StudioState) -> bool {
    let Some(session) = state.selected_session() else {
        return false;
    };
    session.status == SessionStatus::Running
        && !session.stop_requested
        && state.session_controls.contains_key(&session.id)
}

fn request_stop_selected_session(state: &mut StudioState) {
    let Some(session) = state.selected_session() else {
        state.log("select a running session to stop");
        return;
    };
    let session_id = session.id.clone();
    let provider = session.provider;

    if session.status != SessionStatus::Running {
        state.log("selected session is not running");
        return;
    }

    if session.stop_requested {
        state.log("stop already requested for the selected session");
        return;
    }

    if !state.session_controls.contains_key(&session_id) {
        state.log("selected session can no longer be stopped");
        return;
    }

    state.session_stop_confirmation = Some(SessionStopConfirmationState {
        session_id,
        provider,
    });
}

fn confirm_stop_selected_session(state: &mut StudioState) {
    let Some(confirm) = state.session_stop_confirmation.take() else {
        return;
    };

    let Some(control) = state.session_controls.get(&confirm.session_id) else {
        state.log("selected session can no longer be stopped");
        return;
    };
    if control.cancel_flag.load(Ordering::Relaxed) {
        state.log("stop already requested for the selected session");
        return;
    }
    control.cancel_flag.store(true, Ordering::Relaxed);

    if let Some(session) = state
        .sessions
        .iter_mut()
        .find(|session| session.id == confirm.session_id)
    {
        session.stop_requested = true;
        session.last_event_at = Some(Utc::now());
        session.output.push("[studio] stop requested".to_string());
    }

    state.log(format!(
        "stop requested for {} session; other sessions keep running",
        confirm.provider
    ));
}

fn is_quit_key(key: event::KeyEvent) -> bool {
    key.code == KeyCode::Char('q')
        || (key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL))
}

fn set_focused_pane(state: &mut StudioState, pane: FocusedPane) {
    if state.focused_pane != pane && state.is_editing_prompt && pane != FocusedPane::Prompt {
        state.is_editing_prompt = false;
        state.log("prompt edit mode off");
    }
    state.focused_pane = pane;
}

fn handle_prompt_edit_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Esc => {
            state.is_editing_prompt = false;
            state.log("prompt edit mode off");
        }
        KeyCode::Backspace => {
            state.prompt.pop();
            state.invalidate_preview_cache();
        }
        KeyCode::Enter => {
            let _ = append_prompt_text(state, "\n");
        }
        KeyCode::Tab => {
            let _ = append_prompt_text(state, "    ");
        }
        KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.prompt.clear();
            state.invalidate_preview_cache();
        }
        KeyCode::Char(c) if key.modifiers.is_empty() || key.modifiers == KeyModifiers::SHIFT => {
            let mut utf8 = [0u8; 4];
            let _ = append_prompt_text(state, c.encode_utf8(&mut utf8));
        }
        _ => {}
    }
}

fn handle_global_key(
    state: &mut StudioState,
    key: event::KeyEvent,
    tx: &mpsc::UnboundedSender<StudioEvent>,
) {
    match key.code {
        KeyCode::Enter => {
            if state.focused_pane == FocusedPane::Contracts {
                edit_selected_execution_contract(state);
            }
        }
        KeyCode::Char('e') => {
            set_focused_pane(state, FocusedPane::Prompt);
            state.is_editing_prompt = true;
            state.log("prompt edit mode on");
        }
        KeyCode::Char('c') => {
            cycle_execution_contract(state, true);
        }
        KeyCode::Char('a') => {
            if let Err(err) = create_execution_contract(state) {
                state.log(format!("contract creation failed: {}", err));
            }
        }
        KeyCode::Char('x') => {
            request_stop_selected_session(state);
        }
        KeyCode::Char('d') => {
            request_delete_selected_execution_contract(state);
        }
        KeyCode::Char('t') => {
            if state.focused_pane == FocusedPane::Contracts {
                open_attachment_manager(state);
            }
        }
        KeyCode::Char('v') => {
            cycle_editor_choice(state);
        }
        KeyCode::Char('m') => {
            cycle_theme(state, false);
        }
        KeyCode::Char('M') => {
            cycle_theme(state, true);
        }
        KeyCode::Tab => {
            let next_pane = state.focused_pane.next();
            set_focused_pane(state, next_pane);
        }
        KeyCode::BackTab => {
            let previous_pane = state.focused_pane.previous();
            set_focused_pane(state, previous_pane);
        }
        KeyCode::Char('p') => {
            state.provider_mode = state.provider_mode.next();
            state.invalidate_preview_cache();
            state.log(format!("provider mode: {}", state.provider_mode));
        }
        KeyCode::Char('w') => {
            state.workspace_mode = state.workspace_mode.next();
            state.invalidate_preview_cache();
            state.log(format!("workspace mode: {}", state.workspace_mode));
        }
        KeyCode::Char('r') => match scan_project(&state.project_dir) {
            Ok(scan) => {
                state.scan = scan;
                match state.refresh_execution_contracts() {
                    Ok(()) => {
                        state.invalidate_preview_cache();
                        state.log("project scan refreshed");
                    }
                    Err(err) => state.log(format!(
                        "project scan refreshed, but contract reload failed: {}",
                        err
                    )),
                }
            }
            Err(err) => state.log(format!("scan refresh failed: {}", err)),
        },
        KeyCode::Char('s') => {
            start_sessions(state, tx.clone(), false);
        }
        KeyCode::Char('f') => {
            start_sessions(state, tx.clone(), true);
        }
        KeyCode::Char('j') => {
            if !state.sessions.is_empty() {
                state.selected_session = (state.selected_session + 1) % state.sessions.len();
                state.output_scroll = 0;
            }
        }
        KeyCode::Char('k') => {
            if !state.sessions.is_empty() {
                state.selected_session = state
                    .selected_session
                    .checked_sub(1)
                    .unwrap_or_else(|| state.sessions.len().saturating_sub(1));
                state.output_scroll = 0;
            }
        }
        KeyCode::Up => match state.focused_pane {
            FocusedPane::Contracts => cycle_execution_contract(state, false),
            FocusedPane::Prompt => {
                move_prompt_history_selection(state, false);
            }
            FocusedPane::Output => {
                state.output_scroll = state.output_scroll.saturating_add(3);
            }
            _ => {}
        },
        KeyCode::Down => match state.focused_pane {
            FocusedPane::Contracts => cycle_execution_contract(state, true),
            FocusedPane::Prompt => {
                move_prompt_history_selection(state, true);
            }
            FocusedPane::Output => {
                state.output_scroll = state.output_scroll.saturating_sub(3);
            }
            _ => {}
        },
        _ => {}
    }
}

fn handle_mouse_event(state: &mut StudioState, mouse: MouseEvent) {
    let Some(layout) = current_studio_layout(state) else {
        return;
    };

    match mouse.kind {
        MouseEventKind::Down(MouseButton::Left) => {
            if let Some(handle) = resize_handle_at(&layout, mouse.column, mouse.row) {
                state.active_resize = Some(ResizeDragState {
                    handle,
                    start_column: mouse.column,
                    start_row: mouse.row,
                    initial_layout: state.layout_config,
                });
                return;
            }
            if let Some(pane) = pane_at_position(&layout, mouse.column, mouse.row) {
                if pane == FocusedPane::Prompt {
                    activate_prompt_from_click(state, layout.prompt, mouse.column, mouse.row);
                } else {
                    activate_pane_from_click(
                        state,
                        pane,
                        layout.sessions,
                        layout.contracts,
                        mouse.row,
                    );
                }
            }
        }
        MouseEventKind::Drag(MouseButton::Left) => {
            if let Some(drag) = state.active_resize {
                apply_resize_drag(state, &layout, drag, mouse.column, mouse.row);
            }
        }
        MouseEventKind::Up(MouseButton::Left) => {
            state.active_resize = None;
        }
        MouseEventKind::ScrollUp => {
            if let Some(pane) = pane_at_position(&layout, mouse.column, mouse.row) {
                scroll_pane_by_mouse(state, pane, &layout, mouse.column, mouse.row, true);
            }
        }
        MouseEventKind::ScrollDown => {
            if let Some(pane) = pane_at_position(&layout, mouse.column, mouse.row) {
                scroll_pane_by_mouse(state, pane, &layout, mouse.column, mouse.row, false);
            }
        }
        _ => {}
    }
}

fn activate_pane_from_click(
    state: &mut StudioState,
    pane: FocusedPane,
    sessions_area: Rect,
    contracts_area: Rect,
    row: u16,
) {
    if pane == FocusedPane::Sessions {
        select_session_from_click(state, sessions_area, row);
    }
    if pane == FocusedPane::Contracts {
        select_execution_contract_from_click(state, contracts_area, row);
    }
    set_focused_pane(state, pane);
    if pane == FocusedPane::Prompt && !state.is_editing_prompt {
        state.is_editing_prompt = true;
        state.log("prompt edit mode on");
    }
}

fn activate_prompt_from_click(state: &mut StudioState, area: Rect, column: u16, row: u16) {
    set_focused_pane(state, FocusedPane::Prompt);
    if select_prompt_history_from_click(state, area, column, row) {
        if state.is_editing_prompt {
            state.is_editing_prompt = false;
            state.log("prompt edit mode off");
        }
        let _ = state.load_selected_prompt_history_into_prompt();
        state.log("loaded prompt from history");
        return;
    }

    if !state.is_editing_prompt {
        state.is_editing_prompt = true;
        state.log("prompt edit mode on");
    }
}

fn scroll_pane_by_mouse(
    state: &mut StudioState,
    pane: FocusedPane,
    layout: &StudioLayout,
    column: u16,
    row: u16,
    scroll_up: bool,
) {
    match pane {
        FocusedPane::Prompt => {
            let prompt_layout = prompt_pane_layout(layout.prompt, !state.prompt_history.is_empty());
            if prompt_layout.history_list.height == 0
                || row < prompt_layout.history_list.y
                || row
                    >= prompt_layout
                        .history_list
                        .y
                        .saturating_add(prompt_layout.history_list.height)
                || column < prompt_layout.history_list.x
                || column
                    >= prompt_layout
                        .history_list
                        .x
                        .saturating_add(prompt_layout.history_list.width)
            {
                return;
            }
            set_focused_pane(state, FocusedPane::Prompt);
            let delta = if scroll_up { -3 } else { 3 };
            state.scroll_prompt_history(delta, prompt_layout.history_list.height as usize);
        }
        FocusedPane::ExecutionBrief => {
            set_focused_pane(state, FocusedPane::ExecutionBrief);
            let delta = if scroll_up { -3 } else { 3 };
            scroll_preview(state, layout.execution_brief, delta);
        }
        FocusedPane::Output => {
            set_focused_pane(state, FocusedPane::Output);
            if scroll_up {
                state.output_scroll = state.output_scroll.saturating_add(3);
            } else {
                state.output_scroll = state.output_scroll.saturating_sub(3);
            }
        }
        _ => {}
    }
}

fn scroll_preview(state: &mut StudioState, area: Rect, delta: i32) {
    let wrapped = wrap_text_lines(
        state.preview_display(),
        area.width.saturating_sub(2) as usize,
    );
    let max_lines = area.height.saturating_sub(2) as usize;
    let max_scroll = wrapped.len().saturating_sub(max_lines);
    let next = (state.preview_scroll as i32 + delta).clamp(0, max_scroll as i32);
    state.preview_scroll = next as usize;
}

fn resolve_system_editor_command() -> String {
    std::env::var("VISUAL")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .or_else(|| {
            std::env::var("EDITOR")
                .ok()
                .filter(|value| !value.trim().is_empty())
        })
        .unwrap_or_else(|| "vi".to_string())
}

pub(in crate::studio) fn resolve_editor_command(choice: EditorChoice) -> String {
    match choice {
        EditorChoice::System => resolve_system_editor_command(),
        EditorChoice::Vi => "vi".to_string(),
        EditorChoice::Nano => "nano".to_string(),
        EditorChoice::CodeWait => "code --wait".to_string(),
    }
}

pub(in crate::studio) fn editor_choice_summary(choice: EditorChoice) -> String {
    match choice {
        EditorChoice::System => format!("system -> {}", resolve_editor_command(choice)),
        _ => resolve_editor_command(choice),
    }
}

pub(in crate::studio) fn editor_command_name(editor_command: &str) -> String {
    let first = editor_command
        .split_whitespace()
        .next()
        .unwrap_or(editor_command);
    Path::new(first)
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or(first)
        .to_string()
}

pub(in crate::studio) fn editor_help_lines(editor_name: &str) -> Vec<&'static str> {
    match editor_name {
        "vi" | "vim" | "nvim" => vec![
            "Press `i` to enter insert mode.",
            "Press `Esc`, then type `:wq` and press Enter to save and exit.",
            "Press `Esc`, then type `:q!` and press Enter to discard changes.",
        ],
        "nano" => vec![
            "Edit directly in the buffer.",
            "Press `Ctrl+O`, then Enter to save.",
            "Press `Ctrl+X` to exit.",
        ],
        "emacs" => vec![
            "Edit directly in the buffer.",
            "Press `Ctrl+X Ctrl+S` to save.",
            "Press `Ctrl+X Ctrl+C` to exit.",
        ],
        "code" | "code-insiders" => vec![
            "Edit the file in VS Code.",
            "Save in the editor, then close the editor window/tab when done.",
            "If VS Code was launched with `--wait`, Studio will resume after close.",
        ],
        _ => vec![
            "Edit the file in your configured editor.",
            "Save and close the editor to return to Studio.",
            "If you want different behavior, set `$VISUAL` or `$EDITOR`.",
        ],
    }
}

fn editor_selection_path(project_dir: &Path) -> PathBuf {
    project_dir
        .join(STUDIO_ROOT_DIR)
        .join(STUDIO_SELECTED_EDITOR_FILE)
}

pub(in crate::studio) fn load_editor_choice(project_dir: &Path) -> EditorChoice {
    fs::read_to_string(editor_selection_path(project_dir))
        .ok()
        .map(|value| value.trim().to_string())
        .as_deref()
        .and_then(EditorChoice::from_persisted)
        .unwrap_or(EditorChoice::System)
}

fn persist_editor_choice(project_dir: &Path, choice: EditorChoice) -> Result<()> {
    let path = editor_selection_path(project_dir);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, choice.persist_value())?;
    Ok(())
}

fn cycle_editor_choice(state: &mut StudioState) {
    state.editor_choice = state.editor_choice.next();
    if let Err(err) = persist_editor_choice(&state.project_dir, state.editor_choice) {
        state.log(format!("failed to persist editor choice: {}", err));
    } else {
        state.log(format!(
            "editor: {}",
            editor_choice_summary(state.editor_choice)
        ));
    }
}

fn request_delete_selected_execution_contract(state: &mut StudioState) {
    if state.execution_contracts.len() <= 1 {
        state.log("contract delete failed: cannot delete the last execution contract");
        return;
    }

    state.delete_confirmation = Some(DeleteConfirmationState {
        contract_name: state.selected_execution_contract().name.clone(),
    });
}

pub(in crate::studio) fn queue_editor_action(state: &mut StudioState, action: PendingStudioAction) {
    state.editor_guide = Some(EditorGuideState { action });
}

pub(in crate::studio) fn pending_action_label(action: &PendingStudioAction) -> &'static str {
    match action {
        PendingStudioAction::EditExecutionContract { action_label, .. } => action_label,
        PendingStudioAction::PickExecutionContractAttachment { .. } => "contract attachment",
    }
}

pub(in crate::studio) fn handle_pending_action(
    terminal: &mut tui::Tui,
    state: &mut StudioState,
    action: PendingStudioAction,
    event_tx: &mpsc::UnboundedSender<StudioEvent>,
    terminal_event_reader: &mut JoinHandle<()>,
) -> Result<()> {
    match action {
        PendingStudioAction::EditExecutionContract { path, action_label } => {
            terminal_event_reader.abort();
            tui::restore_terminal(terminal)?;
            let editor_result =
                open_file_in_editor(&path, &resolve_editor_command(state.editor_choice));
            *terminal = tui::setup_terminal()?;
            *terminal_event_reader = spawn_terminal_event_reader(event_tx.clone());
            match editor_result {
                Ok(()) => {
                    state.refresh_execution_contracts()?;
                    state.log(format!("updated {}", action_label));
                }
                Err(err) => {
                    state.log(format!("failed to edit {}: {}", action_label, err));
                }
            }
        }
        PendingStudioAction::PickExecutionContractAttachment { contract_path } => {
            terminal_event_reader.abort();
            tui::restore_terminal(terminal)?;
            let picker_result = pick_attachment_paths(&state.project_dir);
            *terminal = tui::setup_terminal()?;
            *terminal_event_reader = spawn_terminal_event_reader(event_tx.clone());
            match picker_result {
                Ok(paths) if paths.is_empty() => {
                    state.log("attachment picker canceled");
                }
                Ok(paths) => match append_attachment_specs_for_paths(
                    &contract_path,
                    &state.project_dir,
                    &paths,
                ) {
                    Ok(specs) => {
                        state.refresh_execution_contracts()?;
                        let selected_paths = paths
                            .iter()
                            .filter_map(|path| {
                                infer_attachment_spec_from_selected_path(path, &state.project_dir)
                                    .ok()
                                    .map(|spec| spec.path)
                            })
                            .collect::<Vec<_>>();
                        state.log(format!(
                            "attached {} item(s) to contract{}",
                            selected_paths.len(),
                            if selected_paths.is_empty() {
                                "".to_string()
                            } else {
                                format!(": {}", selected_paths.join(", "))
                            }
                        ));
                        if specs.is_empty() {
                            state.log("contract has no attachments");
                        }
                    }
                    Err(err) => {
                        state.log(format!("failed to add attachment: {}", err));
                    }
                },
                Err(err) => {
                    state.log(format!("attachment picker failed: {}", err));
                }
            }
        }
    }
    Ok(())
}

fn open_file_in_editor(path: &Path, editor: &str) -> Result<()> {
    let status = Command::new("sh")
        .arg("-c")
        .arg("$FOUNDRY_EDITOR \"$FOUNDRY_TARGET_FILE\"")
        .env("FOUNDRY_EDITOR", editor)
        .env("FOUNDRY_TARGET_FILE", path)
        .status()
        .context("failed to launch editor")?;
    if !status.success() {
        anyhow::bail!("editor exited with status {}", status);
    }
    Ok(())
}

fn select_session_from_click(state: &mut StudioState, area: Rect, row: u16) {
    if state.sessions.is_empty()
        || row <= area.y
        || row >= area.y.saturating_add(area.height).saturating_sub(1)
    {
        return;
    }

    let index = row.saturating_sub(area.y.saturating_add(1)) as usize;
    if index < state.sessions.len() {
        state.selected_session = index;
        state.output_scroll = 0;
    }
}

fn select_execution_contract_from_click(state: &mut StudioState, area: Rect, row: u16) {
    if state.execution_contracts.is_empty()
        || row <= area.y + 1
        || row >= area.y.saturating_add(area.height).saturating_sub(1)
    {
        return;
    }

    let index = row.saturating_sub(area.y.saturating_add(2)) as usize;
    if index < state.execution_contracts.len() {
        state.set_selected_execution_contract_index(index);
        if let Err(err) = persist_selected_execution_contract(
            &state.project_dir,
            &state.selected_execution_contract().file_name,
        ) {
            state.log(format!("failed to persist selected contract: {}", err));
        }
    }
}

fn prompt_history_visible_rows(state: &StudioState) -> usize {
    current_studio_layout(state)
        .map(|layout| prompt_pane_layout(layout.prompt, !state.prompt_history.is_empty()))
        .map(|layout| layout.history_list.height as usize)
        .unwrap_or(0)
}

fn move_prompt_history_selection(state: &mut StudioState, toward_older: bool) {
    if state.prompt_history.is_empty() {
        return;
    }

    let current_index = state.selected_prompt_history_index().unwrap_or(0);
    let next_index = if toward_older {
        current_index.saturating_add(1)
    } else {
        current_index.saturating_sub(1)
    }
    .min(state.prompt_history.len().saturating_sub(1));

    state.set_selected_prompt_history_index(next_index);
    state.ensure_selected_prompt_history_visible(prompt_history_visible_rows(state));
    let _ = state.load_selected_prompt_history_into_prompt();
}

fn select_prompt_history_from_click(
    state: &mut StudioState,
    area: Rect,
    column: u16,
    row: u16,
) -> bool {
    let layout = prompt_pane_layout(area, !state.prompt_history.is_empty());
    if layout.history_list.height == 0
        || column < layout.history_list.x
        || column
            >= layout
                .history_list
                .x
                .saturating_add(layout.history_list.width)
        || row < layout.history_list.y
        || row
            >= layout
                .history_list
                .y
                .saturating_add(layout.history_list.height)
    {
        return false;
    }

    let visible_rows = layout.history_list.height as usize;
    let max_scroll = state.prompt_history.len().saturating_sub(visible_rows);
    let scroll = state.prompt_history_scroll.min(max_scroll);
    let index = scroll + row.saturating_sub(layout.history_list.y) as usize;
    if index >= state.prompt_history.len() {
        return false;
    }

    state.set_selected_prompt_history_index(index);
    state.ensure_selected_prompt_history_visible(visible_rows);
    true
}

#[cfg(test)]
mod tests {
    use std::{
        sync::{
            atomic::{AtomicBool, Ordering},
            Arc,
        },
        time::{SystemTime, UNIX_EPOCH},
    };

    use chrono::Utc;
    use crossterm::event::{self, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
    use ratatui::layout::Rect;
    use tokio::sync::mpsc;

    use crate::agent::ModelProvider;

    use super::super::super::{
        app::shutdown_active_sessions,
        contracts::{load_execution_contracts, load_execution_contracts_with_selection},
        model::{
            DeleteConfirmationState, EditorChoice, EditorGuideState, ExecutionContract,
            FocusedPane, PendingStudioAction, PromptHistoryEntry, SessionStatus,
            SessionStopConfirmationState, StudioEvent, STUDIO_CONTRACTS_DIR, STUDIO_ROOT_DIR,
        },
        state::SessionControl,
        test_helpers::{temp_test_dir, test_session, test_state},
    };
    use super::super::render::header_keybinding_text;
    use super::*;

    #[test]
    fn quit_key_supports_q_and_ctrl_c() {
        let plain_q = event::KeyEvent::new(KeyCode::Char('q'), KeyModifiers::NONE);
        let ctrl_c = event::KeyEvent::new(KeyCode::Char('c'), KeyModifiers::CONTROL);
        let plain_c = event::KeyEvent::new(KeyCode::Char('c'), KeyModifiers::NONE);

        assert!(is_quit_key(plain_q));
        assert!(is_quit_key(ctrl_c));
        assert!(!is_quit_key(plain_c));
    }

    #[test]
    fn clicking_prompt_enters_prompt_edit_mode() {
        let mut state = test_state();

        activate_pane_from_click(
            &mut state,
            FocusedPane::Prompt,
            Rect::default(),
            Rect::default(),
            0,
        );

        assert_eq!(state.focused_pane, FocusedPane::Prompt);
        assert!(state.is_editing_prompt);
    }

    #[test]
    fn clicking_prompt_history_row_loads_prompt_and_exits_edit_mode() {
        let mut state = test_state();
        state.is_editing_prompt = true;
        state.prompt = "current prompt".into();
        state.prompt_history = vec![
            PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: "newest prompt".into(),
                provider_mode: "both".into(),
                workspace_mode: "isolated".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: false,
            },
            PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: "older prompt".into(),
                provider_mode: "claude".into(),
                workspace_mode: "shared".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: true,
            },
        ];
        let area = Rect::new(0, 0, 48, 8);
        let prompt_layout = prompt_pane_layout(area, true);

        activate_prompt_from_click(
            &mut state,
            area,
            prompt_layout.history_list.x,
            prompt_layout.history_list.y.saturating_add(1),
        );

        assert_eq!(state.prompt, "older prompt");
        assert_eq!(state.selected_prompt_history, 1);
        assert!(!state.is_editing_prompt);
    }

    #[test]
    fn handle_event_dispatches_prompt_history_clicks() {
        let mut state = test_state();
        let (tx, _rx) = mpsc::unbounded_channel();
        state.is_editing_prompt = true;
        state.prompt = "current prompt".into();
        state.prompt_history = vec![
            PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: "newest prompt".into(),
                provider_mode: "both".into(),
                workspace_mode: "isolated".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: false,
            },
            PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: "older prompt".into(),
                provider_mode: "claude".into(),
                workspace_mode: "shared".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: true,
            },
        ];
        let layout = current_studio_layout(&state).expect("test layout");
        let prompt_layout = prompt_pane_layout(layout.prompt, true);

        handle_event(
            &mut state,
            StudioEvent::Mouse(MouseEvent {
                kind: MouseEventKind::Down(MouseButton::Left),
                column: prompt_layout.history_list.x,
                row: prompt_layout.history_list.y.saturating_add(1),
                modifiers: KeyModifiers::NONE,
            }),
            &tx,
        );

        assert_eq!(state.prompt, "older prompt");
        assert_eq!(state.selected_prompt_history, 1);
        assert!(!state.is_editing_prompt);
    }

    #[test]
    fn handle_event_blocks_prompt_history_clicks_while_modal_is_open() {
        let mut state = test_state();
        let (tx, _rx) = mpsc::unbounded_channel();
        state.prompt = "current prompt".into();
        state.prompt_history = vec![PromptHistoryEntry {
            created_at: Utc::now(),
            prompt: "history prompt".into(),
            provider_mode: "both".into(),
            workspace_mode: "isolated".into(),
            contract_name: "Standard Build Contract".into(),
            follow_up: false,
        }];
        state.editor_guide = Some(EditorGuideState {
            action: PendingStudioAction::EditExecutionContract {
                path: PathBuf::from("/tmp/contract.md"),
                action_label: "contract",
            },
        });
        let layout = current_studio_layout(&state).expect("test layout");
        let prompt_layout = prompt_pane_layout(layout.prompt, true);

        handle_event(
            &mut state,
            StudioEvent::Mouse(MouseEvent {
                kind: MouseEventKind::Down(MouseButton::Left),
                column: prompt_layout.history_list.x,
                row: prompt_layout.history_list.y,
                modifiers: KeyModifiers::NONE,
            }),
            &tx,
        );

        assert_eq!(state.prompt, "current prompt");
        assert_eq!(state.selected_prompt_history, 0);
        assert!(state.editor_guide.is_some());
    }

    #[test]
    fn queue_editor_action_opens_guide_instead_of_immediate_launch() {
        let mut state = test_state();

        queue_editor_action(
            &mut state,
            PendingStudioAction::EditExecutionContract {
                path: PathBuf::from("/tmp/contract.md"),
                action_label: "contract",
            },
        );

        assert!(state.editor_guide.is_some());
        assert!(state.pending_action.is_none());
    }

    #[test]
    fn editor_guide_can_cycle_editor_choice() {
        let mut state = test_state();

        queue_editor_action(
            &mut state,
            PendingStudioAction::EditExecutionContract {
                path: PathBuf::from("/tmp/contract.md"),
                action_label: "contract",
            },
        );

        handle_editor_guide_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('v'), KeyModifiers::NONE),
        );

        assert_eq!(state.editor_choice, EditorChoice::Nano);
        assert!(state.editor_guide.is_some());
    }

    #[test]
    fn request_delete_opens_confirmation() {
        let mut state = test_state();
        state.execution_contracts.push(ExecutionContract {
            file_name: "reporting.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/reporting.md"),
            name: "Reporting Contract".into(),
            body: "# Reporting Contract".into(),
            attachments: Vec::new(),
        });
        state.selected_execution_contract = 1;

        request_delete_selected_execution_contract(&mut state);

        assert!(state.delete_confirmation.is_some());
    }

    #[test]
    fn scrolling_preview_updates_preview_scroll() {
        let mut state = test_state();
        state.prompt = (0..40)
            .map(|idx| format!("line {}", idx))
            .collect::<Vec<_>>()
            .join("\n");
        let area = Rect::new(0, 0, 30, 8);

        scroll_preview(&mut state, area, 3);
        assert!(state.preview_scroll > 0);

        scroll_preview(&mut state, area, -3);
        assert_eq!(state.preview_scroll, 0);
    }

    #[test]
    fn prompt_history_scrolls_with_mouse_wheel() {
        let mut state = test_state();
        state.prompt_history = (0..8)
            .map(|idx| PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: format!("prompt {}", idx),
                provider_mode: "both".into(),
                workspace_mode: "isolated".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: false,
            })
            .collect();
        let layout = StudioLayout {
            header: Rect::default(),
            body: Rect::default(),
            left_body: Rect::default(),
            right_body: Rect::default(),
            column_split: Rect::default(),
            left_scan_prompt_split: Rect::default(),
            left_prompt_contracts_split: Rect::default(),
            left_contracts_brief_split: Rect::default(),
            right_sessions_output_split: Rect::default(),
            right_output_activity_split: Rect::default(),
            scan: Rect::default(),
            prompt: Rect::new(0, 0, 48, 8),
            contracts: Rect::default(),
            execution_brief: Rect::default(),
            sessions: Rect::default(),
            output: Rect::default(),
            activity: Rect::default(),
            status: Rect::default(),
        };
        let prompt_layout = prompt_pane_layout(layout.prompt, true);

        scroll_pane_by_mouse(
            &mut state,
            FocusedPane::Prompt,
            &layout,
            prompt_layout.history_list.x,
            prompt_layout.history_list.y,
            false,
        );

        assert!(state.prompt_history_scroll > 0);
    }

    #[test]
    fn prompt_history_arrow_keys_load_selected_entry() {
        let mut state = test_state();
        let (tx, _rx) = mpsc::unbounded_channel();
        state.focused_pane = FocusedPane::Prompt;
        state.prompt = "current prompt".into();
        state.prompt_history = vec![
            PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: "newest prompt".into(),
                provider_mode: "both".into(),
                workspace_mode: "isolated".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: false,
            },
            PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: "older prompt".into(),
                provider_mode: "claude".into(),
                workspace_mode: "shared".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: true,
            },
        ];

        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
            &tx,
        );

        assert_eq!(state.selected_prompt_history, 1);
        assert_eq!(state.prompt, "older prompt");
    }

    #[test]
    fn prompt_history_arrow_keys_scroll_selection_into_view() {
        let mut state = test_state();
        let (tx, _rx) = mpsc::unbounded_channel();
        state.focused_pane = FocusedPane::Prompt;
        state.prompt_history = (0..8)
            .map(|idx| PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: format!("prompt {}", idx),
                provider_mode: "both".into(),
                workspace_mode: "isolated".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: false,
            })
            .collect();

        for _ in 0..6 {
            handle_global_key(
                &mut state,
                event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
                &tx,
            );
        }

        assert_eq!(state.selected_prompt_history, 6);
        assert_eq!(state.prompt_history_scroll, 5);
        assert_eq!(state.prompt, "prompt 6");
    }

    #[test]
    fn arrow_keys_move_contract_selection_when_contracts_pane_is_focused() {
        let mut state = test_state();
        state.focused_pane = FocusedPane::Contracts;
        state.execution_contracts.push(ExecutionContract {
            file_name: "reporting.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/reporting.md"),
            name: "Reporting Contract".into(),
            body: "# Reporting Contract".into(),
            attachments: Vec::new(),
        });

        let (tx, _rx) = mpsc::unbounded_channel();
        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
            &tx,
        );
        assert_eq!(state.selected_execution_contract, 1);

        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Up, KeyModifiers::NONE),
            &tx,
        );
        assert_eq!(state.selected_execution_contract, 0);
    }

    #[test]
    fn enter_edits_selected_contract_when_contracts_pane_is_focused() {
        let mut state = test_state();
        state.focused_pane = FocusedPane::Contracts;

        let (tx, _rx) = mpsc::unbounded_channel();
        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
            &tx,
        );

        assert!(state.editor_guide.is_some());
        assert_eq!(state.focused_pane, FocusedPane::Contracts);
    }

    #[test]
    fn t_opens_attachment_manager_when_contracts_pane_is_focused() -> Result<()> {
        let project_dir = temp_test_dir("foundry-edit-attachments-keybind");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.focused_pane = FocusedPane::Contracts;

        let (tx, _rx) = mpsc::unbounded_channel();
        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('t'), KeyModifiers::NONE),
            &tx,
        );

        assert!(state.attachment_manager.is_some());
        assert!(state.pending_action.is_none());
        assert!(state.editor_guide.is_none());
        assert_eq!(state.focused_pane, FocusedPane::Contracts);

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn delete_confirmation_can_cancel() {
        let mut state = test_state();
        state.delete_confirmation = Some(DeleteConfirmationState {
            contract_name: "Standard Build Contract".into(),
        });

        handle_delete_confirmation_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('n'), KeyModifiers::NONE),
        );

        assert!(state.delete_confirmation.is_none());
    }

    #[test]
    fn session_stop_confirmation_can_cancel() {
        let mut state = test_state();
        state.session_stop_confirmation = Some(SessionStopConfirmationState {
            session_id: "session".into(),
            provider: ModelProvider::Claude,
        });

        handle_session_stop_confirmation_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('n'), KeyModifiers::NONE),
        );

        assert!(state.session_stop_confirmation.is_none());
    }

    #[tokio::test]
    async fn x_key_opens_stop_confirmation_for_selected_running_session() {
        let mut state = test_state();
        let mut session = test_session(SessionStatus::Running);
        session.id = "session-1".into();
        state.sessions.push(session);
        state.selected_session = 0;
        let task = tokio::spawn(async {});
        state.session_controls.insert(
            "session-1".into(),
            SessionControl {
                cancel_flag: Arc::new(AtomicBool::new(false)),
                task,
            },
        );

        let (tx, _rx) = mpsc::unbounded_channel();
        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('x'), KeyModifiers::NONE),
            &tx,
        );

        assert!(state.session_stop_confirmation.is_some());
    }

    #[tokio::test]
    async fn stop_selected_session_only_cancels_selected_control() {
        let mut state = test_state();
        let first_flag = Arc::new(AtomicBool::new(false));
        let first_task_flag = first_flag.clone();
        let first_task = tokio::spawn(async move {
            while !first_task_flag.load(Ordering::Relaxed) {
                tokio::task::yield_now().await;
            }
        });
        let second_flag = Arc::new(AtomicBool::new(false));
        let second_task_flag = second_flag.clone();
        let second_task = tokio::spawn(async move {
            while !second_task_flag.load(Ordering::Relaxed) {
                tokio::task::yield_now().await;
            }
        });

        let mut first = test_session(SessionStatus::Running);
        first.id = "session-1".into();
        let mut second = test_session(SessionStatus::Running);
        second.id = "session-2".into();
        second.provider = ModelProvider::Codex;
        state.sessions = vec![first, second];
        state.selected_session = 1;
        state.session_controls.insert(
            "session-1".into(),
            SessionControl {
                cancel_flag: first_flag.clone(),
                task: first_task,
            },
        );
        state.session_controls.insert(
            "session-2".into(),
            SessionControl {
                cancel_flag: second_flag.clone(),
                task: second_task,
            },
        );

        assert!(header_keybinding_text(&state).contains("x stop"));

        request_stop_selected_session(&mut state);
        assert!(state.session_stop_confirmation.is_some());

        handle_session_stop_confirmation_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('y'), KeyModifiers::NONE),
        );

        assert!(!first_flag.load(Ordering::Relaxed));
        assert!(second_flag.load(Ordering::Relaxed));
        assert!(state.sessions[1].stop_requested);
        assert!(!header_keybinding_text(&state).contains("x stop"));

        first_flag.store(true, Ordering::Relaxed);
        shutdown_active_sessions(&mut state).await;
    }

    #[test]
    fn editor_choice_persists_round_trip() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir = std::env::temp_dir().join(format!("foundry-studio-editor-{}", unique));
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        persist_editor_choice(&project_dir, EditorChoice::Nano)?;
        let loaded = load_editor_choice(&project_dir);
        fs::remove_dir_all(&project_dir)?;

        assert_eq!(loaded, EditorChoice::Nano);
        Ok(())
    }

    #[test]
    fn delete_confirmation_yes_deletes_selected_contract() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir =
            std::env::temp_dir().join(format!("foundry-studio-delete-confirm-{}", unique));
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        fs::write(
            contracts_dir.join("standard.md"),
            "# Standard Build Contract\n",
        )?;
        fs::write(contracts_dir.join("reporting.md"), "# Reporting Contract\n")?;
        fs::write(
            contracts_dir.join("reporting.attachments.json"),
            r#"[{"path":"docs/report.md","mode":"inline_file"}]"#,
        )?;

        let (contracts, selected_index) =
            load_execution_contracts_with_selection(&project_dir, Some("reporting.md"))?;
        let mut state = test_state();
        state.project_dir = project_dir.clone();
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.delete_confirmation = Some(DeleteConfirmationState {
            contract_name: "Reporting Contract".into(),
        });

        handle_delete_confirmation_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('y'), KeyModifiers::NONE),
        );

        assert!(state.delete_confirmation.is_none());
        assert_eq!(state.execution_contracts.len(), 1);
        assert_eq!(state.execution_contracts[0].file_name, "standard.md");
        assert!(contracts_dir.join(".trash").exists());
        assert!(!contracts_dir.join("reporting.attachments.json").exists());
        let trashed_entries = fs::read_dir(contracts_dir.join(".trash"))?
            .filter_map(|entry| entry.ok())
            .map(|entry| entry.file_name().to_string_lossy().to_string())
            .collect::<Vec<_>>();
        assert!(trashed_entries
            .iter()
            .any(|name| name.ends_with("reporting.attachments.json")));

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn clicking_contract_row_selects_it() {
        let mut state = test_state();
        state.execution_contracts.push(ExecutionContract {
            file_name: "reporting.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/reporting.md"),
            name: "Reporting Contract".into(),
            body: "# Reporting Contract".into(),
            attachments: Vec::new(),
        });
        let area = Rect::new(0, 0, 40, 8);

        select_execution_contract_from_click(&mut state, area, area.y + 3);

        assert_eq!(state.selected_execution_contract, 1);
    }

    #[test]
    fn quit_event_sets_should_quit() {
        let mut state = test_state();
        let (tx, _rx) = mpsc::unbounded_channel();

        handle_event(&mut state, StudioEvent::Quit, &tx);

        assert!(state.should_quit);
    }

    #[test]
    fn paste_event_truncates_prompt_at_limit() {
        let mut state = test_state();
        state.is_editing_prompt = true;
        let (tx, _rx) = mpsc::unbounded_channel();

        handle_event(
            &mut state,
            StudioEvent::Paste("x".repeat(MAX_PROMPT_BYTES + 128)),
            &tx,
        );

        assert_eq!(state.prompt.len(), MAX_PROMPT_BYTES);
        assert!(state
            .logs
            .iter()
            .any(|(_, message)| message.contains("prompt truncated after paste;")));
    }

    #[test]
    fn paste_event_enters_prompt_edit_mode_when_needed() {
        let mut state = test_state();
        state.focused_pane = FocusedPane::Contracts;
        state.is_editing_prompt = false;
        let (tx, _rx) = mpsc::unbounded_channel();

        handle_event(&mut state, StudioEvent::Paste("hello world".into()), &tx);

        assert_eq!(state.focused_pane, FocusedPane::Prompt);
        assert!(state.is_editing_prompt);
        assert_eq!(state.prompt, "hello world");
        assert!(state
            .logs
            .iter()
            .any(|(_, message)| message == "prompt edit mode on"));
    }

    #[tokio::test]
    async fn request_quit_cancels_running_sessions_and_drains_handles() {
        let mut state = test_state();
        let cancel_flag = Arc::new(AtomicBool::new(false));
        let task_flag = cancel_flag.clone();
        let task = tokio::spawn(async move {
            while !task_flag.load(Ordering::Relaxed) {
                tokio::task::yield_now().await;
            }
        });
        state.session_controls.insert(
            "session".into(),
            SessionControl {
                cancel_flag: cancel_flag.clone(),
                task,
            },
        );
        state.sessions.push(test_session(SessionStatus::Running));

        request_quit(&mut state);

        assert!(state.should_quit);
        assert!(state.shutdown_initiated);
        assert!(cancel_flag.load(Ordering::Relaxed));

        shutdown_active_sessions(&mut state).await;
        assert!(state.session_controls.is_empty());
    }
}

use chrono::{DateTime, Utc};
use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, List, ListItem, Paragraph, Wrap},
    Frame,
};

use crate::{
    agent::ModelProvider,
    utils::{truncate_str, truncate_str_from_end},
};

use super::{
    super::attachments::external_attachment_count,
    super::contracts::execution_contract_list_label,
    super::model::{
        panel_style, root_style, FocusedPane, PromptHistoryEntry, SessionState, SessionStatus,
        StudioTheme, MAX_PREVIEW_RENDER_BYTES, MAX_PROMPT_RENDER_BYTES,
    },
    super::providers::{display_model_name, header_readiness_label, readiness_summary},
    super::state::StudioState,
    input::{can_stop_selected_session, editor_choice_summary},
    layout::{
        output_style, pane_border_style, pane_border_type, pane_title_style, prompt_pane_layout,
        provider_color, studio_layout, studio_spinner, truncate_display_path, wrap_text_lines,
        ResizeHandle, StudioLayout,
    },
    modals::{
        render_attachment_manager, render_delete_confirmation, render_editor_guide,
        render_session_stop_confirmation,
    },
};

pub(in crate::studio) fn render(frame: &mut Frame, state: &mut StudioState) {
    frame.render_widget(
        Block::default().style(root_style(&state.theme)),
        frame.area(),
    );
    let layout = studio_layout(frame.area(), state.layout_config);

    render_header(frame, layout.header, state);
    render_scan(frame, layout.scan, state);
    render_prompt(frame, layout.prompt, state);
    render_contracts(frame, layout.contracts, state);
    render_preview(frame, layout.execution_brief, state);
    render_sessions(frame, layout.sessions, state);
    render_output(frame, layout.output, state);
    render_activity(frame, layout.activity, state);
    render_status(frame, layout.status, state);
    render_resize_handles(frame, &layout, state);
    render_editor_guide(frame, state);
    render_delete_confirmation(frame, state);
    render_session_stop_confirmation(frame, state);
    render_attachment_manager(frame, state);
}

fn render_resize_handles(frame: &mut Frame, layout: &StudioLayout, state: &StudioState) {
    render_resize_handle(
        frame,
        layout.column_split,
        state,
        ResizeHandle::ColumnSplit,
        '│',
    );
    render_resize_handle(
        frame,
        layout.left_scan_prompt_split,
        state,
        ResizeHandle::LeftScanPrompt,
        '─',
    );
    render_resize_handle(
        frame,
        layout.left_prompt_contracts_split,
        state,
        ResizeHandle::LeftPromptContracts,
        '─',
    );
    render_resize_handle(
        frame,
        layout.left_contracts_brief_split,
        state,
        ResizeHandle::LeftContractsBrief,
        '─',
    );
    render_resize_handle(
        frame,
        layout.right_sessions_output_split,
        state,
        ResizeHandle::RightSessionsOutput,
        '─',
    );
    render_resize_handle(
        frame,
        layout.right_output_activity_split,
        state,
        ResizeHandle::RightOutputActivity,
        '─',
    );
}

fn render_resize_handle(
    frame: &mut Frame,
    area: Rect,
    state: &StudioState,
    handle: ResizeHandle,
    fill: char,
) {
    if area.width == 0 || area.height == 0 {
        return;
    }

    let is_active = state
        .active_resize
        .map(|drag| drag.handle == handle)
        .unwrap_or(false);
    let style = if is_active {
        Style::default()
            .fg(state.theme.output)
            .add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(state.theme.border)
    };
    let row = std::iter::repeat_n(fill, area.width as usize).collect::<String>();
    let lines = (0..area.height)
        .map(|_| Line::from(Span::styled(row.clone(), style)))
        .collect::<Vec<_>>();

    frame.render_widget(Paragraph::new(lines), area);
}

pub(in crate::studio) fn header_keybinding_text(state: &StudioState) -> String {
    let mut keys = vec![
        "e edit".to_string(),
        "c cycle contract".to_string(),
        "v cycle editor".to_string(),
        "m theme".to_string(),
        "a add".to_string(),
        "d delete".to_string(),
        "s start".to_string(),
        "f follow-up".to_string(),
    ];
    if can_stop_selected_session(state) {
        keys.push("x stop".to_string());
    }
    keys.extend([
        "p provider".to_string(),
        "w workspace".to_string(),
        "r rescan".to_string(),
        "q/ctrl-c quit".to_string(),
    ]);
    format!("keys: {}", keys.join("  "))
}

fn render_header(frame: &mut Frame, area: Rect, state: &StudioState) {
    let theme = &state.theme;
    let mut lines = Vec::new();
    lines.push(Line::from(vec![
        Span::styled(
            " STUDIO ",
            Style::default()
                .fg(theme.badge_fg)
                .bg(theme.badge_bg)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(
            truncate_display_path(&state.project_dir, 72),
            Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
        ),
    ]));
    lines.push(Line::from(vec![
        Span::styled(
            format!("providers={} ", state.provider_mode),
            Style::default().fg(theme.warning),
        ),
        Span::styled(
            format!("workspace={} ", state.workspace_mode),
            Style::default().fg(theme.info),
        ),
        Span::styled(
            format!("contract={} ", state.selected_execution_contract().name),
            Style::default().fg(theme.contracts),
        ),
        Span::styled(
            format!("editor={} ", editor_choice_summary(state.editor_choice)),
            Style::default().fg(theme.info),
        ),
        Span::styled(
            format!("theme={} ", state.theme.name),
            Style::default().fg(theme.output),
        ),
        Span::styled(
            format!(
                "claude={} ({}) ",
                display_model_name(&state.claude_model),
                header_readiness_label(&state.claude_readiness)
            ),
            Style::default().fg(provider_color(theme, ModelProvider::Claude)),
        ),
        Span::styled(
            format!(
                "codex={} ({})",
                display_model_name(&state.codex_model),
                header_readiness_label(&state.codex_readiness)
            ),
            Style::default().fg(provider_color(theme, ModelProvider::Codex)),
        ),
    ]));
    lines.push(Line::from(Span::styled(
        header_keybinding_text(state),
        Style::default().fg(theme.text_muted),
    )));

    let header = Paragraph::new(lines).style(root_style(theme)).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(theme.border).bg(theme.background)),
    );
    frame.render_widget(header, area);
}

fn render_scan(frame: &mut Frame, area: Rect, state: &StudioState) {
    let theme = &state.theme;
    let items: Vec<ListItem> = state
        .scan
        .summary_lines()
        .into_iter()
        .map(|line| ListItem::new(Span::styled(line, Style::default().fg(theme.text))))
        .collect();

    let list = List::new(items).style(panel_style(theme)).block(
        Block::default()
            .style(panel_style(theme))
            .title(Span::styled(
                " Project Scan ",
                pane_title_style(state, FocusedPane::Scan, theme.scan),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(state, FocusedPane::Scan, theme.scan))
            .border_type(pane_border_type(state, FocusedPane::Scan)),
    );
    frame.render_widget(list, area);
}

fn render_prompt(frame: &mut Frame, area: Rect, state: &StudioState) {
    let theme = &state.theme;
    let prompt_text = prompt_text_for_display(&state.prompt, state.is_editing_prompt);

    let title = if state.is_editing_prompt {
        " Prompt (editing) "
    } else {
        " Prompt "
    };

    let block = Block::default()
        .style(panel_style(theme))
        .title(Span::styled(
            title,
            pane_title_style(state, FocusedPane::Prompt, theme.prompt),
        ))
        .borders(Borders::ALL)
        .border_style(if state.is_editing_prompt {
            Style::default()
                .fg(theme.prompt)
                .add_modifier(Modifier::BOLD)
        } else {
            pane_border_style(state, FocusedPane::Prompt, theme.prompt)
        })
        .border_type(if state.is_editing_prompt {
            BorderType::Thick
        } else {
            pane_border_type(state, FocusedPane::Prompt)
        });
    frame.render_widget(block, area);

    let prompt_layout = prompt_pane_layout(area, !state.prompt_history.is_empty());
    if prompt_layout.editor.height > 0 {
        frame.render_widget(
            Paragraph::new(prompt_text)
                .style(panel_style(theme))
                .wrap(Wrap { trim: false }),
            prompt_layout.editor,
        );
    }

    if prompt_layout.history_label.height > 0 {
        frame.render_widget(
            Paragraph::new(Line::from(vec![
                Span::styled("Recent prompts", Style::default().fg(theme.text_muted)),
                Span::styled(
                    format!(" ({})", state.prompt_history.len()),
                    Style::default().fg(theme.text_muted),
                ),
            ]))
            .style(panel_style(theme)),
            prompt_layout.history_label,
        );
    }

    if prompt_layout.history_list.height > 0 {
        let width = prompt_layout.history_list.width as usize;
        let visible_rows = prompt_layout.history_list.height as usize;
        let max_scroll = state.prompt_history.len().saturating_sub(visible_rows);
        let start = state.prompt_history_scroll.min(max_scroll);
        let end = (start + visible_rows).min(state.prompt_history.len());
        let selected_history_index = state.selected_prompt_history_index();
        let items = if state.prompt_history.is_empty() {
            vec![ListItem::new(Span::styled(
                "No prompt history yet.",
                Style::default().fg(theme.text_muted),
            ))]
        } else {
            state.prompt_history[start..end]
                .iter()
                .enumerate()
                .map(|(offset, entry)| {
                    let index = start + offset;
                    let is_selected = selected_history_index == Some(index);
                    let style = if is_selected {
                        Style::default()
                            .fg(theme.prompt)
                            .add_modifier(Modifier::BOLD)
                    } else if entry.follow_up {
                        Style::default().fg(theme.info)
                    } else {
                        Style::default().fg(theme.text_dim)
                    };
                    ListItem::new(Span::styled(
                        format_prompt_history_line(entry, is_selected, width),
                        style,
                    ))
                })
                .collect()
        };
        frame.render_widget(
            List::new(items).style(panel_style(theme)),
            prompt_layout.history_list,
        );
    }
}

fn render_contracts(frame: &mut Frame, area: Rect, state: &StudioState) {
    let theme = &state.theme;
    let selected = state.selected_execution_contract();
    let mut lines = vec![Line::from(Span::styled(
        format!("selected: {}", execution_contract_list_label(selected)),
        Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
    ))];

    for (idx, contract) in state.execution_contracts.iter().enumerate() {
        let prefix = if idx == state.selected_execution_contract {
            ">"
        } else {
            " "
        };
        let contract_label = execution_contract_list_label(contract);
        lines.push(Line::from(Span::styled(
            format!(
                "{} {}",
                prefix,
                truncate_str(&contract_label, area.width.saturating_sub(6) as usize)
            ),
            if idx == state.selected_execution_contract {
                Style::default().fg(theme.text).add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme.text_dim)
            },
        )));
    }

    lines.push(Line::from(Span::styled(
        "vars: {{workspace_dir}} {{artifact_dir}} {{provider_label}}",
        Style::default().fg(theme.text_muted),
    )));
    lines.push(Line::from(Span::styled(
        format!(
            "editor: {} (press v to change)",
            editor_choice_summary(state.editor_choice)
        ),
        Style::default().fg(theme.info),
    )));
    let external_count = external_attachment_count(&selected.attachments);
    if external_count > 0 {
        lines.push(Line::from(Span::styled(
            format!(
                "warning: {} external attachment(s) outside project root",
                external_count
            ),
            Style::default().fg(theme.warning),
        )));
    }
    lines.push(Line::from(Span::styled(
        "actions: enter edit contract  t manage attachments",
        Style::default().fg(theme.text_muted),
    )));

    let paragraph = Paragraph::new(lines)
        .style(panel_style(theme))
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .style(panel_style(theme))
                .title(Span::styled(
                    " Execution Contracts ",
                    pane_title_style(state, FocusedPane::Contracts, theme.contracts),
                ))
                .borders(Borders::ALL)
                .border_style(pane_border_style(
                    state,
                    FocusedPane::Contracts,
                    theme.contracts,
                ))
                .border_type(pane_border_type(state, FocusedPane::Contracts)),
        );
    frame.render_widget(paragraph, area);
}

fn render_preview(frame: &mut Frame, area: Rect, state: &mut StudioState) {
    let theme = state.theme.clone();
    let preview = state.preview_display();
    let wrapped = wrap_text_lines(preview, area.width.saturating_sub(2) as usize);
    let max_lines = area.height.saturating_sub(2) as usize;
    let max_scroll = wrapped.len().saturating_sub(max_lines);
    let start = state.preview_scroll.min(max_scroll);
    let end = (start + max_lines).min(wrapped.len());
    let items: Vec<ListItem> = wrapped[start..end]
        .iter()
        .cloned()
        .map(|line| ListItem::new(Span::styled(line, Style::default().fg(theme.text_dim))))
        .collect();

    let list = List::new(items).style(panel_style(&theme)).block(
        Block::default()
            .style(panel_style(&theme))
            .title(Span::styled(
                " Execution Brief ",
                pane_title_style(state, FocusedPane::ExecutionBrief, theme.brief),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::ExecutionBrief,
                theme.brief,
            ))
            .border_type(pane_border_type(state, FocusedPane::ExecutionBrief)),
    );
    frame.render_widget(list, area);
}

fn render_sessions(frame: &mut Frame, area: Rect, state: &StudioState) {
    let theme = &state.theme;
    let now = Utc::now();
    let items: Vec<ListItem> = if state.sessions.is_empty() {
        vec![ListItem::new(Span::styled(
            "No sessions yet. Press `s` to launch.",
            Style::default().fg(theme.text_muted),
        ))]
    } else {
        state
            .sessions
            .iter()
            .enumerate()
            .map(|(idx, session)| {
                let line = format_session_list_line(
                    session,
                    idx == state.selected_session,
                    state.tick_count,
                    now,
                );
                ListItem::new(Span::styled(
                    line,
                    Style::default()
                        .fg(if idx == state.selected_session {
                            theme.text
                        } else if session.stop_requested {
                            theme.warning
                        } else {
                            session_status_color(session.status, theme)
                        })
                        .add_modifier(if idx == state.selected_session {
                            Modifier::BOLD
                        } else {
                            Modifier::empty()
                        }),
                ))
            })
            .collect()
    };

    let list = List::new(items).style(panel_style(theme)).block(
        Block::default()
            .style(panel_style(theme))
            .title(Span::styled(
                " Sessions ",
                pane_title_style(state, FocusedPane::Sessions, theme.sessions),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::Sessions,
                theme.sessions,
            ))
            .border_type(pane_border_type(state, FocusedPane::Sessions)),
    );
    frame.render_widget(list, area);
}

fn format_session_list_line(
    session: &SessionState,
    is_selected: bool,
    tick_count: usize,
    now: DateTime<Utc>,
) -> String {
    let prefix = if is_selected { ">" } else { " " };
    let running_marker = if session.status == SessionStatus::Running {
        studio_spinner(tick_count)
    } else {
        ' '
    };
    let elapsed = session_elapsed_seconds(session, now);
    format!(
        "{}{} {} {} {}ev {}s",
        prefix,
        running_marker,
        session.provider,
        session.status.label(),
        session.event_count,
        elapsed
    )
}

fn session_elapsed_seconds(session: &SessionState, now: DateTime<Utc>) -> i64 {
    session
        .finished_at
        .unwrap_or(now)
        .signed_duration_since(session.started_at)
        .num_seconds()
        .max(0)
}

fn render_output(frame: &mut Frame, area: Rect, state: &StudioState) {
    let theme = &state.theme;
    let width = area.width.saturating_sub(2) as usize;
    let mut lines = Vec::new();
    if let Some(session) = state.selected_session() {
        if session.output.is_empty() {
            lines.push(ListItem::new(Span::styled(
                "Waiting for output...",
                Style::default().fg(theme.text_muted),
            )));
        } else {
            let wrapped: Vec<(String, Style)> = session
                .output
                .iter()
                .flat_map(|line| {
                    let style = output_style(line, theme);
                    wrap_text_lines(line, width)
                        .into_iter()
                        .map(move |chunk| (chunk, style))
                })
                .collect();
            let max_lines = area.height.saturating_sub(2) as usize;
            let total = wrapped.len();
            let start = total.saturating_sub(max_lines + state.output_scroll);
            let end = total.saturating_sub(state.output_scroll);
            for (text, style) in wrapped[start..end].iter() {
                lines.push(ListItem::new(Span::styled(text.clone(), *style)));
            }
        }
    } else {
        lines.push(ListItem::new(Span::styled(
            "Select or start a session to see output.",
            Style::default().fg(theme.text_muted),
        )));
    }

    let title = if let Some(session) = state.selected_session() {
        format!(" Output [{}] ", session.provider)
    } else {
        " Output ".to_string()
    };

    let list = List::new(lines).style(panel_style(theme)).block(
        Block::default()
            .style(panel_style(theme))
            .title(Span::styled(
                title,
                pane_title_style(state, FocusedPane::Output, theme.output),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(state, FocusedPane::Output, theme.output))
            .border_type(pane_border_type(state, FocusedPane::Output)),
    );
    frame.render_widget(list, area);
}

fn render_activity(frame: &mut Frame, area: Rect, state: &StudioState) {
    let theme = &state.theme;
    let mut lines: Vec<ListItem> = Vec::new();

    lines.push(ListItem::new(Span::styled(
        format!("Claude: {}", readiness_summary(&state.claude_readiness)),
        Style::default().fg(provider_color(theme, ModelProvider::Claude)),
    )));
    lines.push(ListItem::new(Span::styled(
        format!("Codex: {}", readiness_summary(&state.codex_readiness)),
        Style::default().fg(provider_color(theme, ModelProvider::Codex)),
    )));

    if let Some(session) = state.selected_session() {
        lines.push(ListItem::new(Span::styled(
            format!("contract: {}", state.selected_execution_contract().name),
            Style::default().fg(theme.text_muted),
        )));
        lines.push(ListItem::new(Span::styled(
            format!(
                "workspace: {}",
                truncate_display_path(&session.workspace_dir, 72)
            ),
            Style::default().fg(theme.text_muted),
        )));
        if let Some(prompt_path) = &session.prompt_path {
            lines.push(ListItem::new(Span::styled(
                format!("brief: {}", truncate_display_path(prompt_path, 72)),
                Style::default().fg(theme.text_muted),
            )));
        }
        lines.push(ListItem::new(Span::styled(
            format!(
                "artifacts: {}",
                truncate_display_path(&session.artifact_dir, 72)
            ),
            Style::default().fg(theme.text_muted),
        )));
        lines.push(ListItem::new(Span::styled(
            format!("started: {}", session.started_at.format("%H:%M:%S UTC")),
            Style::default().fg(theme.text_muted),
        )));
        lines.push(ListItem::new(Span::styled(
            format!(
                "activity: {} events{}",
                session.event_count,
                session
                    .last_event_at
                    .map(|ts| format!("; last {}", ts.format("%H:%M:%S")))
                    .unwrap_or_default()
            ),
            Style::default().fg(theme.text_muted),
        )));

        if let Some(error) = &session.error {
            lines.push(ListItem::new(Span::styled(
                format!("error: {}", truncate_str(error, 80)),
                Style::default().fg(theme.error),
            )));
        }

        for artifact in session.artifacts.iter().take(4) {
            lines.push(ListItem::new(Span::styled(
                format!("open: {}", truncate_display_path(artifact, 72)),
                Style::default().fg(theme.success),
            )));
        }
    }

    for (ts, message) in state.logs.iter().rev().take(4).rev() {
        lines.push(ListItem::new(Line::from(vec![
            Span::styled(
                format!("{} ", ts.format("%H:%M:%S")),
                Style::default().fg(theme.text_muted),
            ),
            Span::styled(message.clone(), Style::default().fg(theme.text_dim)),
        ])));
    }

    let list = List::new(lines).style(panel_style(theme)).block(
        Block::default()
            .style(panel_style(theme))
            .title(Span::styled(
                " Artifacts + Log ",
                pane_title_style(state, FocusedPane::Activity, theme.activity),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::Activity,
                theme.activity,
            ))
            .border_type(pane_border_type(state, FocusedPane::Activity)),
    );
    frame.render_widget(list, area);
}

fn render_status(frame: &mut Frame, area: Rect, state: &StudioState) {
    let status = if state.is_editing_prompt {
        "editing prompt"
    } else if state.has_running_sessions() {
        "sessions running"
    } else {
        "ready"
    };
    let text = format!(
        " {} | focus={} | prompt={} chars | sessions={} | theme={} ",
        status,
        state.focused_pane.label(),
        state.prompt.len(),
        state.sessions.len(),
        state.theme.name
    );
    let paragraph = Paragraph::new(text).style(
        Style::default()
            .fg(state.theme.status_fg)
            .bg(state.theme.status_bg),
    );
    frame.render_widget(paragraph, area);
}

fn session_status_color(status: SessionStatus, theme: &StudioTheme) -> Color {
    match status {
        SessionStatus::Running => theme.warning,
        SessionStatus::Stopped => theme.info,
        SessionStatus::Succeeded => theme.success,
        SessionStatus::Failed => theme.error,
    }
}

fn prompt_text_for_display(prompt: &str, is_editing_prompt: bool) -> String {
    let mut text = if prompt.len() <= MAX_PROMPT_RENDER_BYTES {
        prompt.to_string()
    } else {
        let tail = truncate_str_from_end(prompt, MAX_PROMPT_RENDER_BYTES);
        format!(
            "[prompt truncated in Studio; showing last {} KB of {} KB]\n{}",
            MAX_PROMPT_RENDER_BYTES / 1024,
            prompt.len() / 1024,
            tail
        )
    };

    if is_editing_prompt {
        text.push('█');
    }
    text
}

fn format_prompt_history_line(
    entry: &PromptHistoryEntry,
    is_selected: bool,
    width: usize,
) -> String {
    let prefix = if is_selected { ">" } else { " " };
    let kind = if entry.follow_up { "fup" } else { "run" };
    let summary = prompt_history_summary(&entry.prompt, width.saturating_sub(18));
    truncate_str(
        &format!(
            "{} {} {} {}",
            prefix,
            entry.created_at.format("%m-%d %H:%M"),
            kind,
            summary
        ),
        width.max(1),
    )
    .to_string()
}

fn prompt_history_summary(prompt: &str, max_len: usize) -> String {
    let compact = prompt
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .collect::<Vec<_>>()
        .join(" / ");
    if compact.is_empty() {
        "<empty prompt>".to_string()
    } else {
        truncate_str(&compact, max_len.max(1)).to_string()
    }
}

pub(in crate::studio) fn preview_text_for_display(preview: &str) -> String {
    if preview.len() <= MAX_PREVIEW_RENDER_BYTES {
        return preview.to_string();
    }

    let head_budget = MAX_PREVIEW_RENDER_BYTES / 2;
    let tail_budget = MAX_PREVIEW_RENDER_BYTES.saturating_sub(head_budget);
    let head = truncate_str(preview, head_budget);
    let tail = truncate_str_from_end(preview, tail_budget);
    let omitted = preview
        .len()
        .saturating_sub(head.len())
        .saturating_sub(tail.len());

    format!(
        "{}\n\n[preview truncated in Studio; {} KB omitted]\n\n{}",
        head,
        omitted / 1024,
        tail
    )
}

#[cfg(test)]
mod tests {
    use chrono::Utc;

    use super::super::super::{
        model::{
            PromptHistoryEntry, SessionStatus, MAX_PREVIEW_RENDER_BYTES, MAX_PROMPT_RENDER_BYTES,
        },
        test_helpers::test_session,
    };
    use super::{
        format_prompt_history_line, format_session_list_line, preview_text_for_display,
        prompt_text_for_display,
    };

    #[test]
    fn prompt_text_for_display_truncates_large_prompts() {
        let prompt = format!(
            "{}{}",
            "header\n",
            "x".repeat(MAX_PROMPT_RENDER_BYTES + 2048)
        );

        let display = prompt_text_for_display(&prompt, false);

        assert!(display.contains("[prompt truncated in Studio;"));
        assert!(display.ends_with(&"x".repeat(64)));
    }

    #[test]
    fn preview_text_for_display_truncates_large_previews() {
        let preview = format!(
            "{}{}",
            "header\n",
            "x".repeat(MAX_PREVIEW_RENDER_BYTES + 2048)
        );

        let display = preview_text_for_display(&preview);

        assert!(display.contains("[preview truncated in Studio;"));
        assert!(display.starts_with("header\n"));
    }

    #[test]
    fn completed_session_elapsed_time_is_frozen() {
        let started_at = Utc::now() - chrono::Duration::seconds(1272);
        let finished_at = started_at + chrono::Duration::seconds(12);
        let mut session = test_session(SessionStatus::Succeeded);
        session.started_at = started_at;
        session.finished_at = Some(finished_at);
        session.event_count = 3;

        let line = format_session_list_line(
            &session,
            true,
            0,
            finished_at + chrono::Duration::seconds(1260),
        );

        assert!(line.contains("done 3ev 12s"));
    }

    #[test]
    fn prompt_history_lines_include_kind_and_summary() {
        let entry = PromptHistoryEntry {
            created_at: Utc::now(),
            prompt: "Build dashboard\nwith reusable cards".into(),
            provider_mode: "both".into(),
            workspace_mode: "isolated".into(),
            contract_name: "Standard Build Contract".into(),
            follow_up: true,
        };

        let line = format_prompt_history_line(&entry, true, 80);

        assert!(line.starts_with("> "));
        assert!(line.contains("fup"));
        assert!(line.contains("Build dashboard / with reusable cards"));
    }
}

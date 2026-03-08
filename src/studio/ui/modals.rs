use ratatui::{
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, Paragraph, Wrap},
    Frame,
};

use crate::utils::truncate_str;

use super::{
    super::attachments::{attachment_mode_summary, external_attachment_count},
    super::{model::panel_style, state::StudioState},
    input::{
        editor_choice_summary, editor_command_name, editor_help_lines, pending_action_label,
        resolve_editor_command,
    },
    layout::centered_rect,
};

pub(in crate::studio) fn render_editor_guide(frame: &mut Frame, state: &StudioState) {
    let Some(guide) = &state.editor_guide else {
        return;
    };

    let theme = &state.theme;
    let editor_command = resolve_editor_command(state.editor_choice);
    let editor_name = editor_command_name(&editor_command);
    let action_label = pending_action_label(&guide.action);
    let area = centered_rect(68, 14, frame.area());
    let mut lines = vec![
        Line::from(Span::styled(
            format!("Editor: {}", editor_choice_summary(state.editor_choice)),
            Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            format!("Target: {}", action_label),
            Style::default().fg(theme.info),
        )),
        Line::from(Span::styled(
            "Studio will temporarily leave the TUI while the editor is open.",
            Style::default().fg(theme.text_dim),
        )),
        Line::from(""),
    ];

    for tip in editor_help_lines(&editor_name) {
        lines.push(Line::from(Span::styled(
            tip,
            Style::default().fg(theme.text),
        )));
    }

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "V cycle editor  Enter open editor  Esc cancel",
        Style::default().fg(theme.success),
    )));

    frame.render_widget(Clear, area);
    let paragraph = Paragraph::new(lines)
        .style(panel_style(theme))
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .style(panel_style(theme))
                .title(Span::styled(
                    " Open Editor ",
                    Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
                ))
                .borders(Borders::ALL)
                .border_type(BorderType::Thick)
                .border_style(Style::default().fg(theme.info).bg(theme.surface)),
        );
    frame.render_widget(paragraph, area);
}

pub(in crate::studio) fn render_delete_confirmation(frame: &mut Frame, state: &StudioState) {
    let Some(confirm) = &state.delete_confirmation else {
        return;
    };

    let theme = &state.theme;
    let area = centered_rect(60, 8, frame.area());
    let lines = vec![
        Line::from(Span::styled(
            format!("Delete contract: {}", confirm.contract_name),
            Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
        )),
        Line::from(""),
        Line::from(Span::styled(
            "Are you sure? Y/N",
            Style::default()
                .fg(theme.error)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(""),
        Line::from(Span::styled(
            "Y delete permanently (moved to .trash)  N cancel",
            Style::default().fg(theme.text_dim),
        )),
    ];

    frame.render_widget(Clear, area);
    let paragraph = Paragraph::new(lines)
        .style(panel_style(theme))
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .style(panel_style(theme))
                .title(Span::styled(
                    " Confirm Delete ",
                    Style::default()
                        .fg(theme.error)
                        .add_modifier(Modifier::BOLD),
                ))
                .borders(Borders::ALL)
                .border_type(BorderType::Thick)
                .border_style(Style::default().fg(theme.error).bg(theme.surface)),
        );
    frame.render_widget(paragraph, area);
}

pub(in crate::studio) fn render_session_stop_confirmation(frame: &mut Frame, state: &StudioState) {
    let Some(confirm) = &state.session_stop_confirmation else {
        return;
    };

    let theme = &state.theme;
    let area = centered_rect(64, 8, frame.area());
    let lines = vec![
        Line::from(Span::styled(
            format!("Stop {} session?", confirm.provider),
            Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
        )),
        Line::from(""),
        Line::from(Span::styled(
            "Only the selected session will stop. Other running sessions keep going.",
            Style::default().fg(theme.text_dim),
        )),
        Line::from(""),
        Line::from(Span::styled(
            "Y stop selected session  N cancel",
            Style::default()
                .fg(theme.warning)
                .add_modifier(Modifier::BOLD),
        )),
    ];

    frame.render_widget(Clear, area);
    let paragraph = Paragraph::new(lines)
        .style(panel_style(theme))
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .style(panel_style(theme))
                .title(Span::styled(
                    " Stop Session ",
                    Style::default()
                        .fg(theme.warning)
                        .add_modifier(Modifier::BOLD),
                ))
                .borders(Borders::ALL)
                .border_type(BorderType::Thick)
                .border_style(Style::default().fg(theme.warning).bg(theme.surface)),
        );
    frame.render_widget(paragraph, area);
}

pub(in crate::studio) fn render_attachment_manager(frame: &mut Frame, state: &StudioState) {
    let Some(manager) = &state.attachment_manager else {
        return;
    };

    let theme = &state.theme;
    let contract = state.selected_execution_contract();
    let area = centered_rect(76, 18, frame.area());
    let mut lines = vec![
        Line::from(Span::styled(
            format!("Contract: {}", contract.name),
            Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            format!(
                "{} attachment(s){}",
                contract.attachments.len(),
                match external_attachment_count(&contract.attachments) {
                    0 => String::new(),
                    count => format!("; {} external", count),
                }
            ),
            Style::default().fg(theme.info),
        )),
        Line::from(""),
    ];

    if contract.attachments.is_empty() {
        lines.push(Line::from(Span::styled(
            "No attachments yet. Press `a` to add file(s) or folder(s).",
            Style::default().fg(theme.text_dim),
        )));
    } else {
        for (idx, attachment) in contract.attachments.iter().enumerate() {
            let prefix = if idx == manager.selected_attachment {
                ">"
            } else {
                " "
            };
            let marked = if manager.marked_attachments.contains(&idx) {
                "[x]"
            } else {
                "[ ]"
            };
            let style = if idx == manager.selected_attachment {
                Style::default().fg(theme.text).add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme.text_dim)
            };
            let mode_style = Style::default().fg(theme.contracts);
            let path_width = area.width.saturating_sub(20) as usize;
            lines.push(Line::from(vec![
                Span::styled(format!("{} {} ", prefix, marked), style),
                Span::styled(truncate_str(&attachment.path, path_width), style),
                Span::styled(
                    format!(" ({})", attachment_mode_summary(attachment.mode)),
                    mode_style,
                ),
            ]));
        }

        let selected = &contract.attachments[manager
            .selected_attachment
            .min(contract.attachments.len().saturating_sub(1))];
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            format!("selected: {}", selected.path),
            Style::default().fg(theme.info),
        )));
        lines.push(Line::from(Span::styled(
            format!("type: {}", attachment_mode_summary(selected.mode)),
            Style::default().fg(theme.text_dim),
        )));
        if let Some(label) = &selected.label {
            lines.push(Line::from(Span::styled(
                format!("label: {}", label),
                Style::default().fg(theme.text_dim),
            )));
        }
    }

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "a add  d delete marked, else selected  space mark  ↑/↓ move  enter/esc close",
        Style::default().fg(theme.text_muted),
    )));

    frame.render_widget(Clear, area);
    let paragraph = Paragraph::new(lines)
        .style(panel_style(theme))
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .style(panel_style(theme))
                .title(Span::styled(
                    " Manage Attachments ",
                    Style::default()
                        .fg(theme.contracts)
                        .add_modifier(Modifier::BOLD),
                ))
                .borders(Borders::ALL)
                .border_type(BorderType::Thick)
                .border_style(Style::default().fg(theme.contracts).bg(theme.surface)),
        );
    frame.render_widget(paragraph, area);
}

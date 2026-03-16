use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
    Frame,
};

use crate::app::AppState;
use crate::utils::truncate_str;

const PLACEHOLDER_SUGGESTIONS: &[&str] = &[
    "Scan this codebase and find improvements...",
    "Add authentication with JWT tokens...",
    "Create a REST API for...",
    "Fix the failing tests in...",
    "Add Docker Compose setup...",
    "Refactor the frontend to use...",
    "Add CI/CD pipeline with GitHub Actions...",
    "Improve error handling across...",
    "Add real-time updates with WebSockets...",
    "Write comprehensive tests for...",
];

pub enum StartupMouseTarget {
    FileEntry(usize),
    PreviewLine,
}

pub(super) struct StartupLayout {
    pub(super) summary: Rect,
    pub(super) status: Rect,
    pub(super) explorer: Rect,
    pub(super) preview: Rect,
    pub(super) input: Rect,
}

pub(super) fn render_startup(frame: &mut Frame, state: &AppState) {
    let layout = startup_layout(frame.area());

    render_startup_summary(frame, layout.summary, state);
    render_file_explorer(frame, layout.explorer, state);
    render_file_preview(frame, layout.preview, state);
    render_input_prompt(frame, layout.input, state);
    render_startup_status_bar(frame, layout.status, state);
}

pub(super) fn startup_hit_test(
    terminal_size: (u16, u16),
    state: &AppState,
    column: u16,
    row: u16,
) -> Option<StartupMouseTarget> {
    let area = Rect::new(0, 0, terminal_size.0, terminal_size.1);
    let layout = startup_layout(area);

    if let Some(target) = file_explorer_hit_test(layout.explorer, state, column, row) {
        return Some(target);
    }

    startup_preview_hit_test(layout.preview, state, column, row)
}

pub(super) fn startup_layout(area: Rect) -> StartupLayout {
    let vertical = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(8),  // summary
            Constraint::Min(8),    // body
            Constraint::Length(5), // input prompt (borders + 3 content lines for wrapping)
            Constraint::Length(1), // status bar
        ])
        .split(area);

    let columns = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(36), Constraint::Percentage(64)])
        .split(vertical[1]);

    StartupLayout {
        summary: vertical[0],
        status: vertical[3],
        explorer: columns[0],
        preview: columns[1],
        input: vertical[2],
    }
}

fn file_explorer_hit_test(
    area: Rect,
    state: &AppState,
    column: u16,
    row: u16,
) -> Option<StartupMouseTarget> {
    let startup = state.startup.as_ref()?;
    if !rect_contains(area, column, row) {
        return None;
    }

    let inner_top = area.y + 1;
    let inner_bottom = area.y + area.height.saturating_sub(1);
    if row < inner_top || row >= inner_bottom {
        return None;
    }

    let relative_row = (row - inner_top) as usize;
    let index = startup.explorer_scroll + relative_row;
    if index < startup.file_tree.len() {
        Some(StartupMouseTarget::FileEntry(index))
    } else {
        None
    }
}

fn startup_preview_hit_test(
    area: Rect,
    state: &AppState,
    column: u16,
    row: u16,
) -> Option<StartupMouseTarget> {
    if !rect_contains(area, column, row) {
        return None;
    }
    let startup = state.startup.as_ref()?;
    if startup.file_preview_content.is_empty() {
        return None;
    }

    let inner_top = area.y.saturating_add(1);
    let inner_bottom = area.y + area.height.saturating_sub(1);
    if row < inner_top || row >= inner_bottom {
        return None;
    }

    Some(StartupMouseTarget::PreviewLine)
}

fn rect_contains(area: Rect, column: u16, row: u16) -> bool {
    column >= area.x
        && column < area.x.saturating_add(area.width)
        && row >= area.y
        && row < area.y.saturating_add(area.height)
}

fn render_startup_summary(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let git_summary = startup
        .git_context
        .as_ref()
        .map(|ctx| format!("branch {} | {} dirty", ctx.branch, ctx.dirty_count))
        .unwrap_or_else(|| "git summary unavailable".to_string());

    let mut lines = vec![
        Line::from(vec![
            Span::styled(
                if state.project_name.is_empty() {
                    "  FOUNDRY ".to_string()
                } else {
                    format!("  {} ", state.project_name)
                },
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw(" "),
            Span::styled(
                " STOPPED ",
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::DarkGray)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw("  "),
            Span::styled(
                if state.run_mode == "hil" { " Review " } else { " Auto " },
                Style::default()
                    .fg(Color::Black)
                    .bg(if state.run_mode == "hil" {
                        Color::Yellow
                    } else {
                        Color::Green
                    })
                    .add_modifier(Modifier::BOLD),
            ),
        ]),
        Line::from(Span::styled(
            format!(
                "  Project: spec {} | task queue {}",
                if startup.has_spec { "yes" } else { "no" },
                startup.plan_status_label()
            ),
            Style::default().fg(Color::Gray),
        )),
        Line::from(Span::styled(
            format!(
                "  Tasks: {}/{} complete",
                state.completed_count, state.total_count
            ),
            Style::default().fg(Color::Gray),
        )),
        Line::from(Span::styled(
            format!("  Git: {}", git_summary),
            Style::default().fg(Color::Gray),
        )),
        Line::from(Span::styled(
            format!("  {}", startup.summary_headline()),
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            format!("  {}", startup.summary_detail()),
            Style::default().fg(Color::Gray),
        )),
    ];

    if let Some(commit) = startup
        .git_context
        .as_ref()
        .and_then(|ctx| ctx.recent_commits.first())
    {
        lines.push(Line::from(Span::styled(
            format!(
                "  Recent: {}",
                truncate_str(commit, area.width.saturating_sub(12) as usize)
            ),
            Style::default().fg(Color::DarkGray),
        )));
    }

    if let Some(next_task) = startup.next_pending_task.as_ref() {
        lines.push(Line::from(Span::styled(
            format!(
                "  Next: {}",
                truncate_str(next_task, area.width.saturating_sub(10) as usize)
            ),
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )));
    }

    if let Some(message) = startup.status_message.as_ref() {
        lines.push(Line::from(Span::styled(
            format!(
                "  {}",
                truncate_str(message, area.width.saturating_sub(4) as usize)
            ),
            Style::default().fg(Color::Yellow),
        )));
    }

    let summary = Paragraph::new(lines).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(Color::DarkGray)),
    );
    frame.render_widget(summary, area);
}

fn render_file_explorer(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let visible_height = area.height.saturating_sub(2) as usize;

    // Compute display scroll from explorer_selected, clamped for safety
    let scroll = if startup.explorer_selected < startup.explorer_scroll {
        startup.explorer_selected
    } else if visible_height > 0
        && startup.explorer_selected >= startup.explorer_scroll + visible_height
    {
        startup.explorer_selected.saturating_sub(visible_height) + 1
    } else {
        startup.explorer_scroll
    };

    let items: Vec<ListItem> = startup
        .file_tree
        .iter()
        .enumerate()
        .skip(scroll)
        .take(visible_height)
        .map(|(idx, entry)| {
            let indent = "  ".repeat(entry.depth);
            let prefix = if entry.is_dir { "\u{25B8} " } else { "  " };
            let display_name = format!("{}{}{}", indent, prefix, entry.name);
            let is_selected = idx == startup.explorer_selected;
            let fg_color = if entry.is_hidden {
                Color::DarkGray
            } else if entry.is_cf_highlight {
                Color::Rgb(227, 115, 75) // CF orange
            } else if entry.is_dir {
                Color::Cyan
            } else {
                Color::White
            };
            let style = if is_selected {
                Style::default()
                    .fg(Color::Black)
                    .bg(fg_color)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(fg_color)
            };
            ListItem::new(Line::from(Span::styled(display_name, style)))
        })
        .collect();

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " Files ",
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(list, area);
}

fn render_file_preview(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let title = startup
        .file_tree
        .get(startup.explorer_selected)
        .map(|e| e.name.clone())
        .unwrap_or_else(|| "Preview".to_string());

    if startup.file_preview_content.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " Select a file to preview",
            Style::default().fg(Color::DarkGray),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    format!(" {} ", title),
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let inner_height = area.height.saturating_sub(2) as usize;
    let lines: Vec<Line> = startup
        .file_preview_content
        .iter()
        .enumerate()
        .take(inner_height)
        .map(|(i, line)| {
            Line::from(vec![
                Span::styled(
                    format!("{:>4} ", i + 1),
                    Style::default().fg(Color::DarkGray),
                ),
                Span::styled(line.as_str(), Style::default().fg(Color::White)),
            ])
        })
        .collect();

    let paragraph = Paragraph::new(lines)
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    format!(" {} ", title),
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
    frame.render_widget(paragraph, area);
}

fn render_input_prompt(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let placeholder_idx = (startup.placeholder_tick / 30) % PLACEHOLDER_SUGGESTIONS.len();
    let placeholder = PLACEHOLDER_SUGGESTIONS[placeholder_idx];

    let input_line = if startup.intent_input.is_empty() {
        Line::from(vec![
            Span::styled(
                " > ",
                Style::default()
                    .fg(Color::Rgb(227, 115, 75))
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(placeholder, Style::default().fg(Color::DarkGray)),
        ])
    } else {
        Line::from(vec![
            Span::styled(
                " > ",
                Style::default()
                    .fg(Color::Rgb(227, 115, 75))
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(
                startup.intent_input.as_str(),
                Style::default().fg(Color::White),
            ),
            Span::styled("\u{2588}", Style::default().fg(Color::White)),
        ])
    };

    let prompt = Paragraph::new(vec![input_line])
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Rgb(227, 115, 75)))
                .title(Span::styled(
                    " What do you want to do? ",
                    Style::default()
                        .fg(Color::Rgb(227, 115, 75))
                        .add_modifier(Modifier::BOLD),
                )),
        );
    frame.render_widget(prompt, area);
}

pub(super) fn render_startup_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut spans = vec![
        Span::styled(
            " \u{2191}\u{2193} ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" navigate  "),
        Span::styled(
            " Enter ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" submit  "),
        Span::styled(
            " Ctrl+U ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" clear  "),
        Span::styled(
            " Esc ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit"),
    ];

    spans.push(Span::styled(
        "  Tab ",
        Style::default()
            .fg(Color::Black)
            .bg(Color::Rgb(227, 115, 75))
            .add_modifier(Modifier::BOLD),
    ));
    spans.push(Span::raw(if state.show_run_view {
        " actions"
    } else {
        " dashboard"
    }));
    spans.push(Span::styled(
        "  ^M ",
        Style::default()
            .fg(Color::Black)
            .bg(if state.run_mode == "hil" {
                Color::Yellow
            } else {
                Color::Green
            })
            .add_modifier(Modifier::BOLD),
    ));
    spans.push(Span::raw(if state.run_mode == "hil" {
        " review"
    } else {
        " auto"
    }));

    if state.last_orchestrator_outcome.is_some() {
        spans.push(Span::styled(
            "  ^F ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw(" findings"));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available", version),
            Style::default()
                .fg(Color::Green)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::app::{PlanStatus, StartupScenario, StartupState};
    use crate::tui::running::style_for_line;
    use ratatui::style::Color;
    use std::path::PathBuf;

    #[test]
    fn style_for_line_uses_expected_semantic_colors() {
        assert_eq!(style_for_line("[stderr] boom").fg, Some(Color::Red));
        assert_eq!(style_for_line("[tool] read").fg, Some(Color::Cyan));
        assert_eq!(style_for_line("[result] ok").fg, Some(Color::DarkGray));
        assert_eq!(
            style_for_line("[rate limited] wait").fg,
            Some(Color::Yellow)
        );
        assert_eq!(style_for_line("[studio] note").fg, Some(Color::Cyan));
        assert_eq!(style_for_line("plain text").fg, Some(Color::White));
    }

    #[test]
    fn startup_hit_test_detects_file_entry_and_preview_regions() {
        let mut state = AppState::new("/tmp/.buildloop".into());
        let startup = StartupState {
            scenario: StartupScenario::QueueReady,
            plan_status: PlanStatus::Pending(1),
            has_spec: false,
            selected_action: 0,
            actions: vec![crate::app::StartupAction::ScanProject],
            entering_intent: true,
            intent_input: String::new(),
            status_message: None,
            git_context: None,
            tasks_file_name: "TASKS.md".to_string(),
            plan_preview_lines: vec!["# Plan".to_string()],
            plan_scroll_offset: 0,
            next_pending_task: None,
            spec_file_name: "SPEC.md".to_string(),
            spec_preview_lines: Vec::new(),
            spec_scroll_offset: 0,
            file_tree: vec![
                crate::app::FileEntry {
                    path: PathBuf::from("/tmp/src"),
                    name: "src".to_string(),
                    depth: 0,
                    is_dir: true,
                    is_cf_highlight: false,
                    is_hidden: false,
                },
                crate::app::FileEntry {
                    path: PathBuf::from("/tmp/TASKS.md"),
                    name: "TASKS.md".to_string(),
                    depth: 0,
                    is_dir: false,
                    is_cf_highlight: true,
                    is_hidden: false,
                },
            ],
            explorer_selected: 0,
            explorer_scroll: 0,
            file_preview_content: vec!["content line".to_string()],
            placeholder_tick: 0,
        };
        state.startup = Some(startup);

        // File explorer is in the left column (36% of 140 = ~50 cols), starting at row 8 (after summary)
        // Row 9 = first item inside border, row 10 = second item
        assert!(matches!(
            startup_hit_test((140, 40), &state, 2, 9),
            Some(StartupMouseTarget::FileEntry(0))
        ));
        assert!(matches!(
            startup_hit_test((140, 40), &state, 2, 10),
            Some(StartupMouseTarget::FileEntry(1))
        ));
        // Preview is in the right column
        assert!(matches!(
            startup_hit_test((140, 40), &state, 80, 10),
            Some(StartupMouseTarget::PreviewLine)
        ));
    }
}

use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
    Frame,
};

use crate::app::{AppState, StartupAction, StartupScenario};
use crate::utils::truncate_str;

pub enum StartupMouseTarget {
    Action(usize),
    PreviewLine,
}

pub(super) struct StartupLayout {
    pub(super) summary: Rect,
    pub(super) status: Rect,
    pub(super) actions: Rect,
    pub(super) flow: Option<Rect>,
    pub(super) content: Rect,
}

pub(super) fn render_startup(frame: &mut Frame, state: &AppState) {
    let layout = startup_layout(frame.area(), state);

    render_startup_summary(frame, layout.summary, state);
    render_startup_actions(frame, layout.actions, state);
    if let Some(flow_area) = layout.flow {
        render_startup_flow(frame, flow_area, state);
    }
    render_startup_content(frame, layout.content, state);
    render_startup_status_bar(frame, layout.status, state);
}

pub(super) fn startup_hit_test(
    terminal_size: (u16, u16),
    state: &AppState,
    column: u16,
    row: u16,
) -> Option<StartupMouseTarget> {
    let area = Rect::new(0, 0, terminal_size.0, terminal_size.1);
    let layout = startup_layout(area, state);

    if let Some(target) = startup_action_hit_test(layout.actions, state, column, row) {
        return Some(target);
    }

    startup_preview_hit_test(layout.content, state, column, row)
}

pub(super) fn startup_layout(area: Rect, _state: &AppState) -> StartupLayout {
    let vertical = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(8),
            Constraint::Min(8),
            Constraint::Length(1),
        ])
        .split(area);

    let body = vertical[1];

    let (actions, flow, content) = if area.width >= 110 {
        let columns = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Percentage(36), Constraint::Percentage(64)])
            .split(body);

        // Split the left column: actions on top, flow diagram below
        let left_col = columns[0];
        let (actions_area, flow_area) = if left_col.height >= 18 {
            let left_rows = Layout::default()
                .direction(Direction::Vertical)
                .constraints([Constraint::Min(8), Constraint::Length(9)])
                .split(left_col);
            (left_rows[0], Some(left_rows[1]))
        } else {
            (left_col, None)
        };

        (actions_area, flow_area, columns[1])
    } else {
        let rows = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Length(8), Constraint::Min(10)])
            .split(body);
        (rows[0], None, rows[1])
    };

    StartupLayout {
        summary: vertical[0],
        status: vertical[2],
        actions,
        flow,
        content,
    }
}

// Flow diagram is now rendered in the left column via layout.flow, not in the content area.

fn startup_action_hit_test(
    area: Rect,
    state: &AppState,
    column: u16,
    row: u16,
) -> Option<StartupMouseTarget> {
    let startup = state.startup.as_ref()?;
    if !rect_contains(area, column, row) {
        return None;
    }
    if column <= area.x || column >= area.x + area.width.saturating_sub(1) {
        return None;
    }

    let inner_top = area.y.saturating_add(1);
    let inner_bottom = area.y + area.height.saturating_sub(1);
    if row < inner_top || row >= inner_bottom {
        return None;
    }

    let item_height = 2u16;
    let relative_row = row.saturating_sub(inner_top);
    let index = (relative_row / item_height) as usize;
    if index < startup.actions.len() {
        Some(StartupMouseTarget::Action(index))
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
    let _startup = state.startup.as_ref()?;
    let preview_lines = startup_preview_lines(state)?;
    if preview_lines.is_empty() {
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

fn selected_startup_action(state: &AppState) -> Option<StartupAction> {
    state
        .startup
        .as_ref()
        .and_then(|startup| startup.actions.get(startup.selected_action))
        .copied()
}

fn startup_preview_lines(state: &AppState) -> Option<&[String]> {
    let startup = state.startup.as_ref()?;
    match selected_startup_action(state) {
        Some(StartupAction::DescribeWork) | Some(StartupAction::ScanProject) => None,
        Some(StartupAction::EditSpec) => Some(&startup.spec_preview_lines),
        _ => Some(&startup.plan_preview_lines),
    }
}

fn startup_flow_next_label<'a>(state: &'a AppState, fallback: &'a str) -> String {
    state
        .startup
        .as_ref()
        .and_then(|startup| startup.next_pending_task.clone())
        .unwrap_or_else(|| fallback.to_string())
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

fn render_startup_actions(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let items: Vec<ListItem> = startup
        .actions
        .iter()
        .enumerate()
        .map(|(idx, action)| {
            let selected = idx == startup.selected_action;
            let number_style = if selected {
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Cyan)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::DarkGray)
                    .add_modifier(Modifier::BOLD)
            };
            let label_style = if selected {
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(Color::White)
            };
            let desc_style = if selected {
                Style::default().fg(Color::Cyan)
            } else {
                Style::default().fg(Color::DarkGray)
            };

            ListItem::new(vec![
                Line::from(vec![
                    Span::styled(format!(" {} ", idx + 1), number_style),
                    Span::raw(" "),
                    Span::styled(startup.action_label(*action), label_style),
                ]),
                Line::from(Span::styled(
                    format!("   {}", startup.action_description(*action)),
                    desc_style,
                )),
            ])
        })
        .collect();

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " Actions ",
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(list, area);
}

fn render_startup_content(frame: &mut Frame, area: Rect, state: &AppState) {
    let action = selected_startup_action(state);
    let is_edit_tasks_intent = action == Some(StartupAction::EditTasks)
        && state.startup.as_ref().map(|s| s.entering_intent).unwrap_or(false);

    match action {
        Some(StartupAction::EditTasks) if is_edit_tasks_intent => {
            render_startup_intent(frame, area, state)
        }
        Some(StartupAction::EditTasks) | Some(StartupAction::ViewTasks) | Some(StartupAction::Continue) => {
            render_startup_tasks(frame, area, state)
        }
        Some(StartupAction::DescribeWork) | Some(StartupAction::ScanProject) => {
            render_startup_intent(frame, area, state)
        }
        Some(StartupAction::EditSpec) => render_startup_spec(frame, area, state),
        _ => render_startup_plan(frame, area, state),
    }
}

fn render_startup_tasks(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    if startup.plan_preview_lines.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " No tasks in queue yet.",
            Style::default().fg(Color::DarkGray),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    format!(" {} ", startup.tasks_file_name),
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let max_lines = area.height.saturating_sub(2) as usize;
    let inner_width = area.width.saturating_sub(4) as usize;

    // Parse task lines with status indicators
    let display_lines: Vec<Line> = startup
        .plan_preview_lines
        .iter()
        .map(|line| {
            let trimmed = line.trim_start();
            if trimmed.starts_with("- [x]") {
                Line::from(vec![
                    Span::styled(" \u{25cf} ", Style::default().fg(Color::Green)),
                    Span::styled(
                        truncate_str(
                            trimmed.strip_prefix("- [x] ").unwrap_or(trimmed),
                            inner_width.saturating_sub(3),
                        ),
                        Style::default().fg(Color::Green),
                    ),
                ])
            } else if trimmed.starts_with("- [ ]") {
                let task_text = trimmed.strip_prefix("- [ ] ").unwrap_or(trimmed);
                let prefix_color = if task_text.starts_with('H') {
                    Color::Yellow
                } else if task_text.starts_with('D') {
                    Color::Blue
                } else {
                    Color::White
                };
                Line::from(vec![
                    Span::styled(" \u{25cb} ", Style::default().fg(Color::Gray)),
                    Span::styled(
                        truncate_str(task_text, inner_width.saturating_sub(3)),
                        Style::default().fg(prefix_color),
                    ),
                ])
            } else if trimmed.starts_with('#') {
                Line::from(Span::styled(
                    line.as_str(),
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                ))
            } else {
                Line::from(Span::styled(
                    line.as_str(),
                    Style::default().fg(Color::Gray),
                ))
            }
        })
        .collect();

    let total = display_lines.len();
    let scroll = startup
        .plan_scroll_offset
        .min(total.saturating_sub(max_lines));
    let visible: Vec<Line> = display_lines
        .into_iter()
        .skip(scroll)
        .take(max_lines)
        .collect();

    let pending = state.total_count.saturating_sub(state.completed_count);
    let title = format!(
        " {} [{}/{} done | {} left] ",
        startup.tasks_file_name, state.completed_count, state.total_count, pending
    );

    let paragraph = Paragraph::new(visible).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(paragraph, area);
}

fn render_startup_plan(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let pending = state.total_count.saturating_sub(state.completed_count);
    let title = format!(
        " {} [{}/{} complete | {} remaining] ",
        startup.tasks_file_name, state.completed_count, state.total_count, pending
    );

    render_preview_block(
        frame,
        area,
        title,
        &startup.plan_preview_lines,
        startup.plan_scroll_offset,
        &format!(
            " No {} content yet. Describe work or scan the project first. ",
            startup.tasks_file_name
        ),
    );
}

fn render_startup_spec(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    render_preview_block(
        frame,
        area,
        format!(" {} Preview ", startup.spec_file_name),
        &startup.spec_preview_lines,
        startup.spec_scroll_offset,
        &format!(
            " No {} found yet. Press Enter to create or edit it. ",
            startup.spec_file_name
        ),
    );
}

fn render_startup_intent(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let action = selected_startup_action(state);
    let (title, prompt_text, helper_text, enter_hint) = match action {
        Some(StartupAction::DescribeWork) => match startup.scenario {
            StartupScenario::EmptyProject => (
                " Add ".to_string(),
                "What do you want to build?".to_string(),
                format!(
                    "Foundry scans your project, understands your intent, and creates comprehensive tasks in {}.",
                    startup.tasks_file_name
                ),
                "Press Enter to start.".to_string(),
            ),
            _ => (
                " Add ".to_string(),
                "What should Foundry work on next?".to_string(),
                format!(
                    "Foundry scans your project, understands your intent, and creates comprehensive tasks in {}.",
                    startup.tasks_file_name
                ),
                "Press Enter to add and start.".to_string(),
            ),
        },
        Some(StartupAction::EditTasks) => match startup.scenario {
            StartupScenario::EmptyProject | StartupScenario::NeedsQueue => (
                " What do you want to build? ".to_string(),
                "Describe what you want Foundry to build:".to_string(),
                format!(
                    "Foundry scans your project, understands your intent, and creates comprehensive tasks in {}.",
                    startup.tasks_file_name
                ),
                "Press Enter to start.".to_string(),
            ),
            _ => (
                " Add with AI ".to_string(),
                "What should Foundry work on next?".to_string(),
                format!(
                    "Foundry scans your project, understands your intent, and creates comprehensive tasks in {}.",
                    startup.tasks_file_name
                ),
                "Press Enter to add. Press Esc to go back to viewing tasks.".to_string(),
            ),
        },
        Some(StartupAction::ScanProject) => (
            " Scan Project ".to_string(),
            "Optional: focus the scan on a bug, area, or goal:".to_string(),
            format!(
                "Foundry will inspect the codebase, use {} if present, append tasks to {}, then start building.",
                startup.spec_file_name, startup.tasks_file_name
            ),
            "Press Enter to scan and start. Leave empty for a general scan.".to_string(),
        ),
        _ => return,
    };

    let prompt = vec![
        Line::from(Span::styled(
            format!(" {}", prompt_text),
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(""),
        Line::from(format!(" {}\u{2588}", startup.intent_input)),
        Line::from(""),
        Line::from(Span::styled(
            format!(" {}", helper_text),
            Style::default().fg(Color::DarkGray),
        )),
        Line::from(""),
        Line::from(Span::styled(
            format!(" {}", enter_hint),
            Style::default().fg(Color::Gray),
        )),
    ];

    let input = Paragraph::new(prompt)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Cyan))
                .title(Span::styled(
                    title.as_str(),
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(input, area);
}

fn render_startup_flow(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let lines = match selected_startup_action(state) {
        Some(StartupAction::DescribeWork) => {
            let mut lines = vec![Line::from(Span::styled(
                " You describe what should happen next:",
                Style::default().fg(Color::DarkGray),
            ))];

            if matches!(startup.scenario, StartupScenario::EmptyProject) {
                lines.push(Line::from(Span::styled(
                    " your brief",
                    Style::default().fg(Color::Cyan),
                )));
                lines.push(Line::from("        |"));
                lines.push(Line::from(Span::styled(
                    format!("        v  Foundry seeds {}", startup.spec_file_name),
                    Style::default().fg(Color::Yellow),
                )));
                lines.push(Line::from("        |"));
                lines.push(Line::from(Span::styled(
                    format!("        v  Foundry creates {}", startup.tasks_file_name),
                    Style::default().fg(Color::Yellow),
                )));
            } else {
                lines.push(Line::from(Span::styled(
                    " your description",
                    Style::default().fg(Color::Cyan),
                )));
                lines.push(Line::from("        |"));
                lines.push(Line::from(Span::styled(
                    format!("        v  Foundry updates {}", startup.tasks_file_name),
                    Style::default().fg(Color::Yellow),
                )));
            }

            lines.push(Line::from("        |"));
            lines.push(Line::from(Span::styled(
                format!(
                    "        v  autonomous build runs: {}",
                    startup_flow_next_label(state, "next pending task")
                ),
                Style::default().fg(Color::Green),
            )));
            lines.push(Line::from(Span::styled(
                " No repo scan. Existing completed tasks stay untouched.",
                Style::default().fg(Color::DarkGray),
            )));
            lines
        }
        Some(StartupAction::ScanProject) => vec![
            Line::from(Span::styled(
                " Foundry scans the repo for gaps and missing work:",
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                format!(" codebase + optional {}", startup.spec_file_name),
                Style::default().fg(Color::White),
            )),
            Line::from("        |"),
            Line::from(Span::styled(
                format!(
                    "        v  Foundry appends tasks to {}",
                    startup.tasks_file_name
                ),
                Style::default().fg(Color::Yellow),
            )),
            Line::from(Span::styled(
                format!(
                    "        v  autonomous build runs: {}",
                    startup_flow_next_label(state, "next pending task")
                ),
                Style::default().fg(Color::Green),
            )),
            Line::from(Span::styled(
                " Existing tasks stay for continuity. New work is appended.",
                Style::default().fg(Color::DarkGray),
            )),
        ],
        Some(StartupAction::ViewTasks) => vec![
            Line::from(Span::styled(
                format!(" Opens {} in your editor.", startup.tasks_file_name),
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                " Add, remove, or reorder tasks, then save and quit.",
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                " Changes take effect on the next Continue.",
                Style::default().fg(Color::Gray),
            )),
        ],
        Some(StartupAction::EditSpec) => vec![
            Line::from(Span::styled(
                format!(" Opens {} in your editor.", startup.spec_file_name),
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                " The spec gives context to Scan project and the planner.",
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                " Changes apply on the next Scan or build run.",
                Style::default().fg(Color::Gray),
            )),
        ],
        _ => vec![
            Line::from(Span::styled(
                " Run the existing task queue:",
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                format!(" {} (existing tasks)", startup.tasks_file_name),
                Style::default().fg(Color::Yellow),
            )),
            Line::from(Span::styled(
                format!(
                    "        v  autonomous build runs: {}",
                    startup_flow_next_label(state, "first pending task")
                ),
                Style::default().fg(Color::Green),
            )),
            Line::from(Span::styled(
                " Existing tasks run as-is.",
                Style::default().fg(Color::DarkGray),
            )),
        ],
    };

    let block = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    " How This Works ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(block, area);
}

fn render_preview_block(
    frame: &mut Frame,
    area: Rect,
    title: String,
    lines: &[String],
    scroll_offset: usize,
    empty_message: &str,
) {
    let content: Vec<Line> = if lines.is_empty() {
        vec![Line::from(Span::styled(
            empty_message,
            Style::default().fg(Color::DarkGray),
        ))]
    } else {
        lines
            .iter()
            .map(|line| {
                let style = if line.trim_start().starts_with("- [x]") {
                    Style::default().fg(Color::Green)
                } else if line.trim_start().starts_with("- [ ]") {
                    Style::default()
                        .fg(Color::Yellow)
                        .add_modifier(Modifier::BOLD)
                } else if line.trim_start().starts_with('#') {
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(Color::Gray)
                };
                Line::from(Span::styled(line.as_str(), style))
            })
            .collect()
    };

    let preview = Paragraph::new(content)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    title,
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false })
        .scroll((scroll_offset as u16, 0));

    frame.render_widget(preview, area);
}

pub(super) fn render_startup_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let is_intent_active = matches!(
        selected_startup_action(state),
        Some(StartupAction::DescribeWork) | Some(StartupAction::ScanProject)
    ) || (matches!(selected_startup_action(state), Some(StartupAction::EditTasks))
        && startup.entering_intent);

    let mut spans = if is_intent_active {
        vec![
            Span::styled(
                " click ",
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::DarkGray)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw(" switch action  "),
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
        ]
    } else {
        {
            let mut spans = vec![
                Span::styled(
                    format!(" 1-{} ", startup.actions.len()),
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::DarkGray)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::raw(" select action  "),
                Span::styled(
                    " Enter ",
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::DarkGray)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::raw(" activate  "),
                Span::styled(
                    " ←→ ",
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::DarkGray)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::raw(" actions  "),
            ];

            if matches!(selected_startup_action(state), Some(StartupAction::EditTasks)) {
                spans.push(Span::styled(
                    " a ",
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                ));
                spans.push(Span::raw(" add with AI  "));
                spans.push(Span::styled(
                    " e ",
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                ));
                spans.push(Span::raw(" edit manually  "));
            }

            if startup.has_plan_preview()
                || !startup.spec_preview_lines.is_empty()
                || matches!(
                    selected_startup_action(state),
                    Some(StartupAction::EditSpec)
                )
            {
                spans.push(Span::styled(
                    " ↑↓ ",
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::DarkGray)
                        .add_modifier(Modifier::BOLD),
                ));
                spans.push(Span::raw(" preview scroll  "));
                spans.push(Span::styled(
                    " click ",
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::DarkGray)
                        .add_modifier(Modifier::BOLD),
                ));
                spans.push(Span::raw(" jump  "));
            }

            spans.push(Span::styled(
                " Esc ",
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::DarkGray)
                    .add_modifier(Modifier::BOLD),
            ));
            spans.push(Span::raw(" quit"));
            if state.last_orchestrator_outcome.is_some() {
                spans.push(Span::styled(
                    "  f ",
                    Style::default()
                        .fg(Color::Black)
                        .bg(Color::DarkGray)
                        .add_modifier(Modifier::BOLD),
                ));
                spans.push(Span::raw(" findings"));
            }
            spans
        }
    };

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
        "  m ",
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
    use crate::app::{PlanStatus, StartupState};
    use crate::tui::running::style_for_line;
    use ratatui::style::Color;
    use std::path::Path;

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
    fn startup_hit_test_detects_action_and_plan_preview_regions() {
        let mut state = AppState::new("/tmp/.buildloop".into());
        let mut startup = StartupState::new(
            Path::new("/tmp"),
            StartupScenario::QueueReady,
            PlanStatus::Pending(1),
            None,
        );
        startup.plan_preview_lines =
            vec!["# Plan".to_string(), "- [ ] T1.1: Pending task".to_string()];
        // Select ViewTasks (index 0) so the plan preview is shown in the content area
        startup.selected_action = 0;
        state.startup = Some(startup);

        assert!(matches!(
            startup_hit_test((140, 40), &state, 2, 10),
            Some(StartupMouseTarget::Action(0))
        ));
        assert!(matches!(
            startup_hit_test((140, 40), &state, 80, 11),
            Some(StartupMouseTarget::PreviewLine)
        ));
    }
}

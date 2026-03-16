use std::time::SystemTime;

use chrono::{DateTime, Utc};
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
    Frame,
};

use crate::app::{AppState, ExtensionDisplayInfo, FileEntry, StartupState, TuiPane};
use super::{pane_border_style, pane_border_type};
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
    ExtensionEntry(usize),
    ExpandAllToggle,
    WrapToggle,
}

fn is_all_expanded(file_tree: &[FileEntry]) -> bool {
    file_tree.iter().filter(|e| e.is_dir).all(|e| e.expanded)
}

pub(super) struct StartupLayout {
    pub(super) summary: Rect,
    pub(super) status: Rect,
    pub(super) explorer: Rect,
    pub(super) extensions: Rect,
    pub(super) preview: Rect,
    pub(super) input: Rect,
}

pub(super) fn render_startup(frame: &mut Frame, state: &AppState) {
    let ext_count = state.available_extensions.len();
    let layout = startup_layout(frame.area(), ext_count);

    render_startup_summary(frame, layout.summary, state);
    render_file_explorer(frame, layout.explorer, state);
    render_extensions_panel(frame, layout.extensions, state);
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
    let ext_count = state.available_extensions.len();
    let layout = startup_layout(area, ext_count);

    // Check toggle buttons first (they occupy the border row that inner hit-tests skip)
    if let Some(startup) = state.startup.as_ref() {
        if let Some(target) = explorer_toggle_hit_test(layout.explorer, column, row, &startup.file_tree) {
            return Some(target);
        }
        if let Some(target) = preview_toggle_hit_test(layout.preview, column, row, startup.preview_wrap) {
            return Some(target);
        }
    }

    if let Some(target) = file_explorer_hit_test(layout.explorer, state, column, row) {
        return Some(target);
    }

    if let Some(target) = extensions_panel_hit_test(layout.extensions, state, column, row) {
        return Some(target);
    }

    startup_preview_hit_test(layout.preview, state, column, row)
}

pub(super) fn startup_layout(area: Rect, extension_count: usize) -> StartupLayout {
    let ext_panel_height = if extension_count == 0 {
        4u16 // "No extensions found" + borders
    } else {
        (extension_count as u16 + 2).min(8) // rows + borders, capped at 8
    };

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

    // Split left column: file explorer (top) + extensions panel (bottom)
    let left_split = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(5),                    // file explorer (flexible)
            Constraint::Length(ext_panel_height),   // extensions panel (fixed)
        ])
        .split(columns[0]);

    StartupLayout {
        summary: vertical[0],
        status: vertical[3],
        explorer: left_split[0],
        extensions: left_split[1],
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
    let vis = startup.visible_indices();
    let vis_index = startup.explorer_scroll + relative_row;
    if vis_index < vis.len() {
        Some(StartupMouseTarget::FileEntry(vis[vis_index]))
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

fn extensions_panel_hit_test(
    area: Rect,
    state: &AppState,
    column: u16,
    row: u16,
) -> Option<StartupMouseTarget> {
    if !rect_contains(area, column, row) {
        return None;
    }
    if state.available_extensions.is_empty() {
        return None;
    }
    let inner_top = area.y + 1;
    let inner_bottom = area.y + area.height.saturating_sub(1);
    if row < inner_top || row >= inner_bottom {
        return None;
    }
    let relative_row = (row - inner_top) as usize;
    if relative_row < state.available_extensions.len() {
        Some(StartupMouseTarget::ExtensionEntry(relative_row))
    } else {
        None
    }
}

fn rect_contains(area: Rect, column: u16, row: u16) -> bool {
    column >= area.x
        && column < area.x.saturating_add(area.width)
        && row >= area.y
        && row < area.y.saturating_add(area.height)
}

pub(super) fn explorer_toggle_hit_test(
    area: Rect,
    column: u16,
    row: u16,
    file_tree: &[FileEntry],
) -> Option<StartupMouseTarget> {
    if row != area.y {
        return None;
    }
    if file_tree.iter().all(|e| !e.is_dir) {
        return None;
    }
    // Toggle occupies 7 chars: "[+all] " or "[-all] ", right-aligned before the border corner
    if column >= area.x + area.width.saturating_sub(8)
        && column < area.x + area.width.saturating_sub(1)
    {
        return Some(StartupMouseTarget::ExpandAllToggle);
    }
    None
}

pub(super) fn preview_toggle_hit_test(
    area: Rect,
    column: u16,
    row: u16,
    preview_wrap: bool,
) -> Option<StartupMouseTarget> {
    if row != area.y {
        return None;
    }
    let label_len: u16 = if preview_wrap { 7 } else { 10 };
    if column >= area.x + area.width.saturating_sub(label_len + 1)
        && column < area.x + area.width.saturating_sub(1)
    {
        return Some(StartupMouseTarget::WrapToggle);
    }
    None
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
            Span::raw("  "),
            Span::styled(
                if state.show_run_view { " Dashboard " } else { " Explore " },
                Style::default()
                    .fg(Color::White)
                    .bg(Color::Rgb(60, 60, 80))
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

fn format_file_size(bytes: u64) -> String {
    if bytes < 1024 {
        format!("{:>5}", bytes)
    } else if bytes < 1024 * 1024 {
        format!("{:>4.1}K", bytes as f64 / 1024.0)
    } else if bytes < 1024 * 1024 * 1024 {
        format!("{:>4.1}M", bytes as f64 / (1024.0 * 1024.0))
    } else {
        format!("{:>4.1}G", bytes as f64 / (1024.0 * 1024.0 * 1024.0))
    }
}

fn format_modified(t: Option<SystemTime>) -> String {
    match t {
        Some(st) => {
            let dt: DateTime<Utc> = st.into();
            dt.format("%Y-%m-%d").to_string()
        }
        None => String::new(),
    }
}

fn render_file_explorer(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let visible_height = area.height.saturating_sub(2) as usize;
    let vis = startup.visible_indices();

    // Find position of explorer_selected in visible list
    let selected_vis_pos = vis
        .iter()
        .position(|&i| i == startup.explorer_selected)
        .unwrap_or(0);

    // Compute scroll in visible-index space
    let scroll = if selected_vis_pos < startup.explorer_scroll {
        selected_vis_pos
    } else if visible_height > 0
        && selected_vis_pos >= startup.explorer_scroll + visible_height
    {
        selected_vis_pos.saturating_sub(visible_height) + 1
    } else {
        startup.explorer_scroll
    };

    // Determine if we have room for detail columns
    let inner_width = area.width.saturating_sub(2) as usize; // minus borders
    let show_details = inner_width > 40;
    let size_col_width: usize = 6;
    let date_col_width: usize = 11; // "2025-12-29 " with trailing space
    let detail_width = if show_details {
        size_col_width + date_col_width
    } else {
        0
    };

    let items: Vec<ListItem> = vis
        .iter()
        .skip(scroll)
        .take(visible_height)
        .map(|&tree_idx| {
            let entry = &startup.file_tree[tree_idx];
            let indent = "  ".repeat(entry.depth);
            let prefix = if entry.is_dir {
                if entry.expanded { "\u{25BC} " } else { "\u{25B6} " }
            } else {
                "  "
            };

            let is_selected = tree_idx == startup.explorer_selected;
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

            if show_details {
                // Name column: fill remaining width
                let name_str = format!("{}{}{}", indent, prefix, entry.name);
                let name_max = inner_width.saturating_sub(detail_width);
                let truncated_name = if name_str.len() > name_max {
                    truncate_str(&name_str, name_max).to_string()
                } else {
                    format!("{:<width$}", name_str, width = name_max)
                };

                let size_str = if entry.is_dir {
                    format!("{:>width$}", "", width = size_col_width)
                } else {
                    format!(
                        "{:>width$}",
                        format_file_size(entry.file_size),
                        width = size_col_width
                    )
                };

                let date_str = format!(" {:<10}", format_modified(entry.modified));

                let detail_style = if is_selected {
                    Style::default().fg(Color::Black).bg(fg_color)
                } else {
                    Style::default().fg(Color::DarkGray)
                };

                ListItem::new(Line::from(vec![
                    Span::styled(truncated_name, style),
                    Span::styled(size_str, detail_style),
                    Span::styled(date_str, detail_style),
                ]))
            } else {
                let display_name = format!("{}{}{}", indent, prefix, entry.name);
                ListItem::new(Line::from(Span::styled(display_name, style)))
            }
        })
        .collect();

    let expand_label = if is_all_expanded(&startup.file_tree) {
        "[-all] "
    } else {
        "[+all] "
    };
    let has_dirs = startup.file_tree.iter().any(|e| e.is_dir);
    let mut block = Block::default()
        .borders(Borders::ALL)
        .border_style(pane_border_style(state.focused_pane, TuiPane::Explorer))
        .border_type(pane_border_type(state.focused_pane, TuiPane::Explorer))
        .title(Span::styled(
            " Files ",
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ));
    if has_dirs {
        block = block.title_top(
            Line::from(Span::styled(
                expand_label,
                Style::default().fg(Color::DarkGray),
            ))
            .right_aligned(),
        );
    }
    let list = List::new(items).block(block);
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

    let wrap_label = if startup.preview_wrap { "[wrap] " } else { "[no-wrap] " };

    if startup.file_preview_content.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " Select a file to preview",
            Style::default().fg(Color::DarkGray),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(pane_border_style(state.focused_pane, TuiPane::Preview))
                .border_type(pane_border_type(state.focused_pane, TuiPane::Preview))
                .title(Span::styled(
                    format!(" {} ", title),
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                ))
                .title_top(
                    Line::from(Span::styled(
                        wrap_label,
                        Style::default().fg(Color::DarkGray),
                    ))
                    .right_aligned(),
                ),
        );
        frame.render_widget(empty, area);
        return;
    }

    let inner_height = area.height.saturating_sub(2) as usize;
    let scroll = startup.file_preview_scroll;
    let lines: Vec<Line> = startup
        .file_preview_content
        .iter()
        .enumerate()
        .skip(scroll)
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

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(pane_border_style(state.focused_pane, TuiPane::Preview))
        .border_type(pane_border_type(state.focused_pane, TuiPane::Preview))
        .title(Span::styled(
            format!(" {} ", title),
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ))
        .title_top(
            Line::from(Span::styled(
                wrap_label,
                Style::default().fg(Color::DarkGray),
            ))
            .right_aligned(),
        );
    let mut paragraph = Paragraph::new(lines).block(block);
    if startup.preview_wrap {
        paragraph = paragraph.wrap(Wrap { trim: false });
    }
    frame.render_widget(paragraph, area);
}

pub(super) fn render_file_explorer_from(
    frame: &mut Frame,
    area: Rect,
    startup: &StartupState,
    focused: TuiPane,
) {
    let visible_height = area.height.saturating_sub(2) as usize;
    let vis = startup.visible_indices();

    let selected_vis_pos = vis
        .iter()
        .position(|&i| i == startup.explorer_selected)
        .unwrap_or(0);

    let scroll = if selected_vis_pos < startup.explorer_scroll {
        selected_vis_pos
    } else if visible_height > 0
        && selected_vis_pos >= startup.explorer_scroll + visible_height
    {
        selected_vis_pos.saturating_sub(visible_height) + 1
    } else {
        startup.explorer_scroll
    };

    let inner_width = area.width.saturating_sub(2) as usize;
    let show_details = inner_width > 40;
    let size_col_width: usize = 6;
    let date_col_width: usize = 11;
    let detail_width = if show_details {
        size_col_width + date_col_width
    } else {
        0
    };

    let items: Vec<ListItem> = vis
        .iter()
        .skip(scroll)
        .take(visible_height)
        .map(|&tree_idx| {
            let entry = &startup.file_tree[tree_idx];
            let indent = "  ".repeat(entry.depth);
            let prefix = if entry.is_dir {
                if entry.expanded { "\u{25BC} " } else { "\u{25B6} " }
            } else {
                "  "
            };

            let is_selected = tree_idx == startup.explorer_selected;
            let fg_color = if entry.is_hidden {
                Color::DarkGray
            } else if entry.is_cf_highlight {
                Color::Rgb(227, 115, 75)
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

            if show_details {
                let name_str = format!("{}{}{}", indent, prefix, entry.name);
                let name_max = inner_width.saturating_sub(detail_width);
                let truncated_name = if name_str.len() > name_max {
                    truncate_str(&name_str, name_max).to_string()
                } else {
                    format!("{:<width$}", name_str, width = name_max)
                };

                let size_str = if entry.is_dir {
                    format!("{:>width$}", "", width = size_col_width)
                } else {
                    format!(
                        "{:>width$}",
                        format_file_size(entry.file_size),
                        width = size_col_width
                    )
                };

                let date_str = format!(" {:<10}", format_modified(entry.modified));

                let detail_style = if is_selected {
                    Style::default().fg(Color::Black).bg(fg_color)
                } else {
                    Style::default().fg(Color::DarkGray)
                };

                ListItem::new(Line::from(vec![
                    Span::styled(truncated_name, style),
                    Span::styled(size_str, detail_style),
                    Span::styled(date_str, detail_style),
                ]))
            } else {
                let display_name = format!("{}{}{}", indent, prefix, entry.name);
                ListItem::new(Line::from(Span::styled(display_name, style)))
            }
        })
        .collect();

    let expand_label = if is_all_expanded(&startup.file_tree) {
        "[-all] "
    } else {
        "[+all] "
    };
    let has_dirs = startup.file_tree.iter().any(|e| e.is_dir);
    let mut block = Block::default()
        .borders(Borders::ALL)
        .border_style(pane_border_style(focused, TuiPane::Explorer))
        .border_type(pane_border_type(focused, TuiPane::Explorer))
        .title(Span::styled(
            " Files ",
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ));
    if has_dirs {
        block = block.title_top(
            Line::from(Span::styled(
                expand_label,
                Style::default().fg(Color::DarkGray),
            ))
            .right_aligned(),
        );
    }
    let list = List::new(items).block(block);
    frame.render_widget(list, area);
}

pub(super) fn render_file_preview_from(
    frame: &mut Frame,
    area: Rect,
    startup: &StartupState,
    focused: TuiPane,
) {
    let title = startup
        .file_tree
        .get(startup.explorer_selected)
        .map(|e| e.name.clone())
        .unwrap_or_else(|| "Preview".to_string());

    let border_style = pane_border_style(focused, TuiPane::Preview);
    let border_type = pane_border_type(focused, TuiPane::Preview);
    let wrap_label = if startup.preview_wrap { "[wrap] " } else { "[no-wrap] " };

    if startup.file_preview_content.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " Select a file to preview",
            Style::default().fg(Color::DarkGray),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(border_style)
                .border_type(border_type)
                .title(Span::styled(
                    format!(" {} ", title),
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                ))
                .title_top(
                    Line::from(Span::styled(
                        wrap_label,
                        Style::default().fg(Color::DarkGray),
                    ))
                    .right_aligned(),
                ),
        );
        frame.render_widget(empty, area);
        return;
    }

    let inner_height = area.height.saturating_sub(2) as usize;
    let scroll = startup.file_preview_scroll;
    let lines: Vec<Line> = startup
        .file_preview_content
        .iter()
        .enumerate()
        .skip(scroll)
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

    let total = startup.file_preview_content.len();
    let scroll_indicator = if total > inner_height {
        format!(" {} [{}/{}] ", title, scroll + 1, total)
    } else {
        format!(" {} ", title)
    };

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(border_style)
        .border_type(border_type)
        .title(Span::styled(
            scroll_indicator,
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ))
        .title_top(
            Line::from(Span::styled(
                wrap_label,
                Style::default().fg(Color::DarkGray),
            ))
            .right_aligned(),
        );
    let mut paragraph = Paragraph::new(lines).block(block);
    if startup.preview_wrap {
        paragraph = paragraph.wrap(Wrap { trim: false });
    }
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

    // Extensions indicator (always shown)
    let ext_status = format_extensions_status(&state.available_extensions);
    spans.push(Span::styled(
        format!("  {} ", ext_status),
        Style::default().fg(Color::Rgb(227, 115, 75)),
    ));
    if !state.available_extensions.is_empty() {
        spans.push(Span::styled(
            " ^E ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw("focus"));
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

fn render_extensions_panel(frame: &mut Frame, area: Rect, state: &AppState) {
    let border_style = pane_border_style(state.focused_pane, TuiPane::Extensions);
    let border_type = pane_border_type(state.focused_pane, TuiPane::Extensions);
    let title_span = Span::styled(
        " Extensions ",
        Style::default()
            .fg(Color::Rgb(227, 115, 75))
            .add_modifier(Modifier::BOLD),
    );

    if state.available_extensions.is_empty() {
        let paragraph = Paragraph::new(vec![
            Line::from(Span::styled(
                "  No extensions found.",
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                "  Add to ~/.foundry/extensions/",
                Style::default().fg(Color::DarkGray),
            )),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(border_style)
                .border_type(border_type)
                .title(title_span),
        );
        frame.render_widget(paragraph, area);
        return;
    }

    let inner_width = area.width.saturating_sub(2) as usize;
    let lines: Vec<Line> = state
        .available_extensions
        .iter()
        .enumerate()
        .map(|(i, ext)| {
            let checkbox = if ext.selected { "[x]" } else { "[ ]" };
            let is_cursor =
                i == state.extensions_cursor && state.focused_pane == TuiPane::Extensions;
            let pattern_label = if ext.pattern_count > 0 {
                format!(" ({}p)", ext.pattern_count)
            } else {
                String::new()
            };
            let name_and_meta = format!("{} {}{}", checkbox, ext.name, pattern_label);
            let desc_width = inner_width.saturating_sub(name_and_meta.len() + 3);
            let desc = truncate_str(&ext.description, desc_width);

            let name_style = if is_cursor {
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Rgb(227, 115, 75))
                    .add_modifier(Modifier::BOLD)
            } else if ext.selected {
                Style::default().fg(Color::Green)
            } else {
                Style::default().fg(Color::White)
            };

            let desc_style = if is_cursor {
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Rgb(227, 115, 75))
            } else {
                Style::default().fg(Color::DarkGray)
            };

            Line::from(vec![
                Span::styled(format!(" {} ", name_and_meta), name_style),
                Span::styled(desc.to_string(), desc_style),
            ])
        })
        .collect();

    let paragraph = Paragraph::new(lines).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(border_style)
            .border_type(border_type)
            .title(title_span),
    );
    frame.render_widget(paragraph, area);
}

fn format_extensions_status(extensions: &[ExtensionDisplayInfo]) -> String {
    if extensions.is_empty() {
        return "Ext: none".to_string();
    }
    let active: Vec<&str> = extensions
        .iter()
        .filter(|e| e.selected)
        .map(|e| e.name.as_str())
        .collect();
    if active.is_empty() {
        return format!("Ext: none ({} avail)", extensions.len());
    }
    let names = active.join(", ");
    format!("Ext: {} ({} active)", names, active.len())
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
                    expanded: true,
                    file_size: 0,
                    modified: None,
                },
                crate::app::FileEntry {
                    path: PathBuf::from("/tmp/TASKS.md"),
                    name: "TASKS.md".to_string(),
                    depth: 0,
                    is_dir: false,
                    is_cf_highlight: true,
                    is_hidden: false,
                    expanded: true,
                    file_size: 0,
                    modified: None,
                },
            ],
            explorer_selected: 0,
            explorer_scroll: 0,
            file_preview_content: vec!["content line".to_string()],
            file_preview_scroll: 0,
            placeholder_tick: 0,
            preview_wrap: true,
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

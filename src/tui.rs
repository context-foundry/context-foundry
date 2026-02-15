use crossterm::{
    event::{DisableMouseCapture, EnableMouseCapture},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Frame, Terminal,
};
use std::io;

use crate::utils::truncate_str;

use crate::agent::AgentRole;
use crate::app::AppState;

pub type Tui = Terminal<ratatui::backend::CrosstermBackend<io::Stdout>>;

pub fn setup_terminal() -> anyhow::Result<Tui> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = ratatui::backend::CrosstermBackend::new(stdout);
    let terminal = Terminal::new(backend)?;
    Ok(terminal)
}

pub fn restore_terminal(terminal: &mut Tui) -> anyhow::Result<()> {
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;
    Ok(())
}

pub fn render(frame: &mut Frame, state: &AppState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(4),  // Header: task + progress
            Constraint::Min(10),   // Agent output
            Constraint::Length(8), // Log
            Constraint::Length(1), // Status bar
        ])
        .split(frame.area());

    render_header(frame, chunks[0], state);
    render_agent_output(frame, chunks[1], state);
    render_log(frame, chunks[2], state);
    render_status_bar(frame, chunks[3], state);
}

fn render_header(frame: &mut Frame, area: Rect, state: &AppState) {
    let completed = state.completed_count;
    let total = state.total_count;
    let pct = if total > 0 {
        (completed as f64 / total as f64) * 100.0
    } else {
        0.0
    };

    let task_line = if let Some(ref task) = state.current_task {
        format!("  {} — {}", task.id, task.short_desc(60))
    } else if state.is_discovering {
        "  Discovery — scanning for new work...".to_string()
    } else {
        "  Waiting...".to_string()
    };

    let agent_line = if let Some((ref role, ref started)) = state.current_agent {
        let elapsed = chrono::Utc::now().signed_duration_since(*started);
        let mins = elapsed.num_minutes();
        let secs = elapsed.num_seconds() % 60;
        let model = state.current_agent_model.as_deref().unwrap_or("?");

        // Spinner animation while waiting for output
        let spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
        let spinner = spinner_chars[state.tick_count % spinner_chars.len()];

        let activity = if state.agent_output.is_empty() {
            format!("{} thinking...", spinner)
        } else {
            format!("{} {} events", spinner, state.events_received)
        };

        format!(
            "    {} ({}) | {}m {}s | {}",
            role, model, mins, secs, activity
        )
    } else {
        String::new()
    };

    let header_text = vec![
        Line::from(vec![
            Span::styled("  FOUNDRY ", Style::default().fg(Color::Black).bg(Color::Cyan).add_modifier(Modifier::BOLD)),
            Span::raw("  "),
            Span::styled(
                format!("[{}/{}] {:.0}%", completed, total, pct),
                Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD),
            ),
        ]),
        Line::from(Span::styled(
            task_line,
            Style::default().fg(Color::White).add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            agent_line,
            Style::default().fg(Color::DarkGray),
        )),
    ];

    let header = Paragraph::new(header_text)
        .block(Block::default().borders(Borders::BOTTOM).border_style(Style::default().fg(Color::DarkGray)));
    frame.render_widget(header, area);
}

fn wrap_line(line: &str, width: usize) -> Vec<String> {
    if width == 0 || line.len() <= width {
        return vec![line.to_string()];
    }
    let mut result = Vec::new();
    let mut remaining = line;
    while !remaining.is_empty() {
        if remaining.len() <= width {
            result.push(remaining.to_string());
            break;
        }
        // Find a safe char boundary at or before `width`
        let safe_width = truncate_str(remaining, width).len();
        // Guarantee forward progress: if we can't fit even one char,
        // push the first character and advance past it.
        if safe_width == 0 {
            let first_char_len = remaining
                .chars()
                .next()
                .map(|c| c.len_utf8())
                .unwrap_or(1);
            result.push(remaining[..first_char_len].to_string());
            remaining = &remaining[first_char_len..];
            continue;
        }
        // Try to break at a space within the safe range
        let split_at = remaining[..safe_width]
            .rfind(' ')
            .map(|p| p + 1)
            .unwrap_or(safe_width);
        result.push(remaining[..split_at].to_string());
        remaining = &remaining[split_at..];
    }
    result
}

fn style_for_line(line: &str) -> Style {
    if line.starts_with("[stderr]") {
        Style::default().fg(Color::Red)
    } else if line.starts_with("[tool]") {
        Style::default().fg(Color::Yellow)
    } else if line.starts_with("[result]") {
        Style::default().fg(Color::DarkGray)
    } else {
        Style::default().fg(Color::White)
    }
}

fn render_agent_output(frame: &mut Frame, area: Rect, state: &AppState) {
    let inner_width = area.width.saturating_sub(2) as usize;

    // Pre-wrap all lines, preserving style
    let wrapped: Vec<(String, Style)> = state
        .agent_output
        .iter()
        .flat_map(|line| {
            let style = style_for_line(line);
            wrap_line(line, inner_width)
                .into_iter()
                .map(move |chunk| (chunk, style))
        })
        .collect();

    let max_lines = area.height.saturating_sub(2) as usize;
    let total_lines = wrapped.len();
    let start = total_lines.saturating_sub(max_lines + state.scroll_offset);
    let end = total_lines.saturating_sub(state.scroll_offset);

    let items: Vec<ListItem> = wrapped[start..end]
        .iter()
        .map(|(text, style)| ListItem::new(Span::styled(text.as_str(), *style)))
        .collect();

    let title = if let Some((ref role, _)) = state.current_agent {
        let color = match role {
            AgentRole::Planner => Color::Magenta,
            AgentRole::Builder => Color::Green,
            AgentRole::Validator => Color::Cyan,
            AgentRole::Fixer => Color::Yellow,
            AgentRole::Discovery => Color::Blue,
            AgentRole::Auditor => Color::Red,
        };
        Span::styled(
            format!(" {} Output ", role),
            Style::default().fg(color).add_modifier(Modifier::BOLD),
        )
    } else {
        Span::styled(" Output ", Style::default().fg(Color::DarkGray))
    };

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(title),
    );

    frame.render_widget(list, area);
}

fn render_log(frame: &mut Frame, area: Rect, state: &AppState) {
    let max_lines = area.height.saturating_sub(2) as usize;
    let start = state.log_messages.len().saturating_sub(max_lines);

    let items: Vec<ListItem> = state.log_messages[start..]
        .iter()
        .map(|(ts, msg)| {
            let time = ts.format("%H:%M:%S").to_string();
            ListItem::new(Line::from(vec![
                Span::styled(
                    format!(" {} ", time),
                    Style::default().fg(Color::DarkGray),
                ),
                Span::styled(msg.as_str(), Style::default().fg(Color::Gray)),
            ]))
        })
        .collect();

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " Log ",
                Style::default().fg(Color::DarkGray),
            )),
    );

    frame.render_widget(list, area);
}

fn render_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let discovery_info = if state.discovery_round > 0 {
        format!(" | discovery round {} ", state.discovery_round)
    } else {
        String::new()
    };

    let status = Line::from(vec![
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit  "),
        Span::styled(
            " Ctrl+C ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" stop after current task  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll"),
        Span::styled(discovery_info, Style::default().fg(Color::DarkGray)),
    ]);

    let bar = Paragraph::new(status);
    frame.render_widget(bar, area);
}

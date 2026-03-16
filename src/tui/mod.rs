mod overlays;
mod pipeline;
mod running;
mod startup;
mod stats;

use crossterm::{
    event::{DisableBracketedPaste, DisableMouseCapture, EnableBracketedPaste, EnableMouseCapture},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{BorderType, Paragraph},
    Frame, Terminal,
};
use std::io;

use crate::app::{AppPhase, AppState, TuiPane};
use crate::config::Config;
use crate::utils::truncate_str_from_end;

pub use startup::StartupMouseTarget;

pub type Tui = Terminal<ratatui::backend::CrosstermBackend<io::Stdout>>;

pub fn setup_terminal() -> anyhow::Result<Tui> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(
        stdout,
        EnterAlternateScreen,
        EnableMouseCapture,
        EnableBracketedPaste
    )?;
    let backend = ratatui::backend::CrosstermBackend::new(stdout);
    let terminal = Terminal::new(backend)?;
    Ok(terminal)
}

pub fn restore_terminal(terminal: &mut Tui) -> anyhow::Result<()> {
    execute!(
        terminal.backend_mut(),
        DisableBracketedPaste,
        DisableMouseCapture,
        LeaveAlternateScreen,
    )?;
    disable_raw_mode()?;
    terminal.show_cursor()?;
    Ok(())
}

pub fn pane_border_style(focused: TuiPane, this_pane: TuiPane) -> Style {
    if focused == this_pane {
        Style::default()
            .fg(Color::Rgb(227, 115, 75))
            .add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(Color::DarkGray)
    }
}

pub fn pane_border_type(focused: TuiPane, this_pane: TuiPane) -> BorderType {
    if focused == this_pane {
        BorderType::Thick
    } else {
        BorderType::Plain
    }
}

pub fn rect_contains(area: Rect, column: u16, row: u16) -> bool {
    column >= area.x
        && column < area.x.saturating_add(area.width)
        && row >= area.y
        && row < area.y.saturating_add(area.height)
}

pub struct RunningPaneRects {
    pub agent_output: Rect,
    pub task_queue: Rect,
    pub patterns: Rect,
    pub extensions_used: Rect,
}

pub fn running_layout(area: Rect) -> RunningPaneRects {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5),
            Constraint::Length(7),
            Constraint::Min(10),
            Constraint::Length(6),
            Constraint::Length(1),
        ])
        .split(area);

    let middle_cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(chunks[2]);

    let right_panel = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(6),
            Constraint::Length(6),
            Constraint::Length(6),
        ])
        .split(middle_cols[1]);

    RunningPaneRects {
        agent_output: middle_cols[0],
        task_queue: right_panel[0],
        patterns: right_panel[1],
        extensions_used: right_panel[2],
    }
}

pub fn render(frame: &mut Frame, state: &AppState, config: &Config) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5),  // Header
            Constraint::Length(7),  // Pipeline map (3 lines inside box + borders)
            Constraint::Min(10),   // Middle: agent output + task queue
            Constraint::Length(6), // Bottom: stats (progress bar + 3 content rows + borders)
            Constraint::Length(1), // Status bar
        ])
        .split(frame.area());

    running::render_header(frame, chunks[0], state);
    pipeline::render_pipeline_map(frame, chunks[1], state, config);

    // Middle: split horizontally 60/40
    let middle_cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(chunks[2]);
    running::render_agent_output(frame, middle_cols[0], state, state.focused_pane);

    // Right panel: task queue + patterns + extensions used
    let right_panel = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(6),      // Task queue (fills remaining space)
            Constraint::Length(6),   // Patterns (4 content lines + 2 border)
            Constraint::Length(6),   // Extensions Used (4 content lines + 2 border)
        ])
        .split(middle_cols[1]);
    running::render_task_queue(frame, right_panel[0], state, state.focused_pane);
    running::render_patterns(frame, right_panel[1], state, config, state.focused_pane);
    running::render_extensions_used(frame, right_panel[2], state, state.focused_pane);

    // Bottom: stats panel (full width)
    stats::render_dashboard_stats(frame, chunks[3], state, config);

    // Use startup status bar when viewing dashboard from startup (Tab toggle)
    if matches!(state.phase, AppPhase::Startup) {
        startup::render_startup_status_bar(frame, chunks[4], state);
    } else {
        running::render_status_bar(frame, chunks[4], state);
    }

    // Overlay inject input bar at bottom of agent output area
    if let Some(ref input) = state.inject_input {
        let output_area = middle_cols[0];
        if output_area.height >= 3 {
            // Hint line above the input
            let hint_area = Rect::new(
                output_area.x,
                output_area.y + output_area.height - 2,
                output_area.width,
                1,
            );
            let hint = Paragraph::new(Line::from(vec![
                Span::styled(" Enter ", Style::default().fg(Color::DarkGray)),
                Span::styled("add to end  ", Style::default().fg(Color::DarkGray)),
                Span::styled(" !text ", Style::default().fg(Color::Yellow)),
                Span::styled("run next  ", Style::default().fg(Color::DarkGray)),
                Span::styled(" Esc ", Style::default().fg(Color::DarkGray)),
                Span::styled("cancel", Style::default().fg(Color::DarkGray)),
            ]))
            .style(Style::default().bg(Color::DarkGray));
            frame.render_widget(hint, hint_area);

            // Input line
            let inject_area = Rect::new(
                output_area.x,
                output_area.y + output_area.height - 1,
                output_area.width,
                1,
            );
            let prompt_label = if input.starts_with('!') {
                " next> "
            } else {
                " task> "
            };
            let max_text = inject_area.width.saturating_sub(10) as usize;
            let display = truncate_str_from_end(input, max_text);
            let bar = Paragraph::new(Line::from(vec![
                Span::styled(
                    prompt_label,
                    Style::default()
                        .fg(Color::Yellow)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::styled(display, Style::default().fg(Color::White)),
                Span::styled(
                    "\u{2588}",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::SLOW_BLINK),
                ),
            ]))
            .style(Style::default().bg(Color::DarkGray));
            frame.render_widget(bar, inject_area);
        }
    }
}

pub fn render_patterns(frame: &mut Frame, state: &AppState, config: &Config) {
    overlays::render_patterns(frame, state, config);
}

pub fn render_findings(frame: &mut Frame, state: &AppState) {
    overlays::render_findings(frame, state);
}

pub fn render_running_explorer(frame: &mut Frame, state: &AppState, config: &Config) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5),
            Constraint::Length(7),
            Constraint::Min(10),
            Constraint::Length(6),
            Constraint::Length(1),
        ])
        .split(frame.area());

    running::render_header(frame, chunks[0], state);
    pipeline::render_pipeline_map(frame, chunks[1], state, config);

    // Middle: explorer + preview (same as startup layout)
    let middle_cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(36), Constraint::Percentage(64)])
        .split(chunks[2]);

    if let Some(ref explorer_state) = state.running_explorer {
        startup::render_file_explorer_from(frame, middle_cols[0], explorer_state, state.focused_pane);
        startup::render_file_preview_from(frame, middle_cols[1], explorer_state, state.focused_pane);
    }

    stats::render_dashboard_stats(frame, chunks[3], state, config);
    running::render_running_explorer_status_bar(frame, chunks[4], state);
}

pub fn render_startup(frame: &mut Frame, state: &AppState) {
    startup::render_startup(frame, state);
}

pub fn startup_hit_test(
    terminal_size: (u16, u16),
    state: &AppState,
    column: u16,
    row: u16,
) -> Option<StartupMouseTarget> {
    startup::startup_hit_test(terminal_size, state, column, row)
}

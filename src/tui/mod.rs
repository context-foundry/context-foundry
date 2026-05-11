mod narrative;
mod overlays;
mod pipeline;
mod running;
mod startup;
mod stats;
pub mod theme;
mod welcome;

use crossterm::{
    event::{DisableBracketedPaste, DisableMouseCapture, EnableBracketedPaste, EnableMouseCapture},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{BorderType, Paragraph},
    Frame, Terminal,
};
use std::io;

use crate::app::{AppPhase, AppState, TuiPane};
use crate::config::Config;
use crate::utils::truncate_str_from_end;

pub use overlays::{
    close_btn_rect, confirm_banner_hit_test, context_menu_hit_test, git_init_offer_hit_test,
    model_picker_hit_test, quit_confirm_hit_test, render_git_init_offer,
    render_no_tasks_warning, render_quit_confirm, render_running_modal, settings_modal_rect,
    settings_overlay_row_hit_test, summary_modal_hit_test, ConfirmBannerAction, ContextMenuHit,
    GitInitOfferAction, ModelPickerMouseTarget, QuitConfirmAction, SummaryModalAction,
};
pub fn render_surface_summary_overlay(frame: &mut Frame, state: &AppState) {
    if let Some(overlay) = state.surface_summary_overlay.as_ref() {
        overlays::render_surface_summary_overlay(frame, &state.tui_theme, overlay);
    }
}
pub use pipeline::{pipeline_click, PipelineClick};
pub use running::{
    running_header_tab_hit_test, running_status_bar_hit_test, RunningHeaderTab,
    RunningStatusBarAction,
};
pub use startup::{startup_status_bar_hit_test, StartupMouseTarget, StatusBarAction};
pub use welcome::{random_fallback_message, render_welcome};

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

pub fn pane_border_style(focused: TuiPane, this_pane: TuiPane, theme: &theme::TuiTheme) -> Style {
    if focused == this_pane {
        Style::default()
            .fg(theme.accent)
            .add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(theme.border)
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
    #[allow(dead_code)]
    pub narrative: Rect,
    pub patterns: Rect,
    pub extensions_used: Option<Rect>,
    /// Terminal column of the vertical separator between agent and task-queue panes.
    pub separator_col: u16,
}

pub fn running_layout(area: Rect, has_extensions: bool, split_pct: u16) -> RunningPaneRects {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5),
            Constraint::Length(6),
            Constraint::Min(8),
            Constraint::Length(8),
            Constraint::Length(1),
        ])
        .split(area);

    let left_pct = split_pct.clamp(20, 80);
    let right_pct = 100 - left_pct;
    let middle_cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(left_pct),
            Constraint::Percentage(right_pct),
        ])
        .split(chunks[2]);

    let sep = middle_cols[1].x;
    if has_extensions {
        let right_panel = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Min(6),
                Constraint::Length(6),  // narrative
                Constraint::Length(6),  // patterns
                Constraint::Length(6),  // extensions used
            ])
            .split(middle_cols[1]);
        RunningPaneRects {
            agent_output: middle_cols[0],
            task_queue: right_panel[0],
            narrative: right_panel[1],
            patterns: right_panel[2],
            extensions_used: Some(right_panel[3]),
            separator_col: sep,
        }
    } else {
        let right_panel = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Min(6),
                Constraint::Length(6),  // narrative
                Constraint::Length(6),  // patterns
            ])
            .split(middle_cols[1]);
        RunningPaneRects {
            agent_output: middle_cols[0],
            task_queue: right_panel[0],
            narrative: right_panel[1],
            patterns: right_panel[2],
            extensions_used: None,
            separator_col: sep,
        }
    }
}

pub fn render(frame: &mut Frame, state: &AppState, config: &Config) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5), // Header
            Constraint::Length(6), // Pipeline map (5 box lines + bottom border)
            Constraint::Min(8),    // Middle: agent output + task queue
            Constraint::Length(8), // Bottom: stats (progress bar + 5 content rows + borders)
            Constraint::Length(1), // Status bar
        ])
        .split(frame.area());

    running::render_header(frame, chunks[0], state);
    pipeline::render_pipeline_map(frame, chunks[1], state, config);

    // Middle: split horizontally per user-adjustable split percentage
    let left_pct = state.agent_pane_split.clamp(20, 80);
    let middle_cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(left_pct),
            Constraint::Percentage(100 - left_pct),
        ])
        .split(chunks[2]);
    running::render_agent_output(frame, middle_cols[0], state, state.focused_pane);

    // Right panel: task queue + patterns (+ extensions used if any selected)
    let has_extensions = !state.available_extensions.iter().all(|e| !e.selected)
        || !state.session_extensions_used.is_empty();
    let _right_panel = if has_extensions {
        let panel = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Min(6),    // Task queue (fills remaining space)
                Constraint::Length(6), // Narrative (3 content lines + 2 border)
                Constraint::Length(6), // Patterns (4 content lines + 2 border)
                Constraint::Length(6), // Extensions Used (4 content lines + 2 border)
            ])
            .split(middle_cols[1]);
        running::render_task_queue(frame, panel[0], state, state.focused_pane);
        narrative::render_narrative(frame, panel[1], state, state.focused_pane);
        running::render_skill_citations(frame, panel[2], state, config, state.focused_pane);
        running::render_extensions_used(frame, panel[3], state, state.focused_pane);
        panel
    } else {
        let panel = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Min(6),    // Task queue (fills remaining space)
                Constraint::Length(6), // Narrative (3 content lines + 2 border)
                Constraint::Length(6), // Patterns (4 content lines + 2 border)
            ])
            .split(middle_cols[1]);
        running::render_task_queue(frame, panel[0], state, state.focused_pane);
        narrative::render_narrative(frame, panel[1], state, state.focused_pane);
        running::render_skill_citations(frame, panel[2], state, config, state.focused_pane);
        panel
    };

    // Bottom: stats panel (full width)
    stats::render_dashboard_stats(frame, chunks[3], state, config, state.focused_pane);

    // Use startup status bar when viewing dashboard from startup (Tab toggle)
    if matches!(state.phase, AppPhase::Startup) {
        startup::render_startup_status_bar(frame, chunks[4], state);
    } else {
        running::render_status_bar(frame, chunks[4], state);
    }

    // Two-arrow resize indicator on the vertical separator when mouse is hovering.
    if state.mouse_over_separator {
        let middle = chunks[2];
        let sep_col = middle_cols[1].x;
        let row = middle.y + middle.height / 2;
        if sep_col < frame.area().width && row < frame.area().height {
            let buf = frame.buffer_mut();
            let arrow_style = Style::default()
                .fg(state.tui_theme.warning)
                .add_modifier(Modifier::BOLD);
            buf[(sep_col, row)]
                .set_char('\u{2194}')
                .set_style(arrow_style);
        }
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
                Span::styled(" Enter ", Style::default().fg(state.tui_theme.muted)),
                Span::styled("add to end  ", Style::default().fg(state.tui_theme.muted)),
                Span::styled(" !text ", Style::default().fg(state.tui_theme.warning)),
                Span::styled("run next  ", Style::default().fg(state.tui_theme.muted)),
                Span::styled(" Esc ", Style::default().fg(state.tui_theme.muted)),
                Span::styled("cancel", Style::default().fg(state.tui_theme.muted)),
            ]))
            .style(Style::default().bg(state.tui_theme.muted));
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
                        .fg(state.tui_theme.warning)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::styled(display, Style::default().fg(state.tui_theme.text)),
                Span::styled(
                    "\u{2588}",
                    Style::default()
                        .fg(state.tui_theme.text)
                        .add_modifier(Modifier::SLOW_BLINK),
                ),
            ]))
            .style(Style::default().bg(state.tui_theme.muted));
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

pub fn render_stats_overlay(frame: &mut Frame, state: &AppState) {
    overlays::render_stats_overlay(frame, state);
}

pub fn render_settings_overlay(frame: &mut Frame, state: &AppState) {
    overlays::render_settings_overlay(frame, state);
}

pub fn render_running_explorer(frame: &mut Frame, state: &AppState, config: &Config) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5),
            Constraint::Length(6),
            Constraint::Min(8),
            Constraint::Length(8),
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
        let project_dir = state
            .buildloop_dir
            .parent()
            .unwrap_or(std::path::Path::new("."));
        let dir_label = format!(" {} ", startup::project_dir_label(project_dir));
        startup::render_file_explorer_from(
            frame,
            middle_cols[0],
            explorer_state,
            &dir_label,
            state.focused_pane,
            &state.tui_theme,
        );
        startup::render_file_preview_from(
            frame,
            middle_cols[1],
            explorer_state,
            state.focused_pane,
            &state.tui_theme,
        );
    }

    stats::render_dashboard_stats(frame, chunks[3], state, config, state.focused_pane);
    running::render_running_explorer_status_bar(frame, chunks[4], state);

    if let Some(ref menu) = state.explorer_context_menu {
        overlays::render_explorer_context_menu(frame, &state.tui_theme, menu);
    }
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

pub fn explorer_toggle_hit_test(
    area: ratatui::layout::Rect,
    column: u16,
    row: u16,
    file_tree: &[crate::app::FileEntry],
) -> Option<StartupMouseTarget> {
    startup::explorer_toggle_hit_test(area, column, row, file_tree)
}

pub fn preview_toggle_hit_test(
    area: ratatui::layout::Rect,
    column: u16,
    row: u16,
    preview_wrap: bool,
) -> Option<StartupMouseTarget> {
    startup::preview_toggle_hit_test(area, column, row, preview_wrap)
}

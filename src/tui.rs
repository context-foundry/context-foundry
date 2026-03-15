use crossterm::{
    event::{DisableBracketedPaste, DisableMouseCapture, EnableBracketedPaste, EnableMouseCapture},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Cell, List, ListItem, Paragraph, Row, Table, Wrap},
    Frame, Terminal,
};
use std::io;

use crate::config::Config;
use crate::utils::{truncate_str, truncate_str_from_end};

use crate::agent::AgentRole;
use crate::app::{AppPhase, AppState, StartupAction, StartupScenario};

pub enum StartupMouseTarget {
    Action(usize),
    PreviewLine,
}

struct StartupLayout {
    summary: Rect,
    status: Rect,
    actions: Rect,
    flow: Option<Rect>,
    content: Rect,
}

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

pub fn render(frame: &mut Frame, state: &AppState, config: &Config) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(5),  // Header
            Constraint::Length(6),  // Pipeline map
            Constraint::Min(10),   // Middle: agent output + task queue
            Constraint::Length(9), // Bottom: build config + stats + doubt config
            Constraint::Length(1), // Status bar
        ])
        .split(frame.area());

    render_header(frame, chunks[0], state);
    render_pipeline_map(frame, chunks[1], state, config);

    // Middle: split horizontally 60/40
    let middle_cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(chunks[2]);
    render_agent_output(frame, middle_cols[0], state);
    render_task_queue(frame, middle_cols[1], state);

    // Bottom: split into 3 columns
    let bottom_cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(35),
            Constraint::Percentage(30),
            Constraint::Percentage(35),
        ])
        .split(chunks[3]);
    render_session_config(frame, bottom_cols[0], config);
    render_dashboard_stats(frame, bottom_cols[1], state, config);
    render_orchestrator_config(frame, bottom_cols[2], config);

    // Use startup status bar when viewing dashboard from startup (Tab toggle)
    if matches!(state.phase, AppPhase::Startup) {
        render_startup_status_bar(frame, chunks[4], state);
    } else {
        render_status_bar(frame, chunks[4], state);
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

// ─── Pipeline & Dashboard Widgets ─────────────────────────────

fn render_pipeline_map(frame: &mut Frame, area: Rect, state: &AppState, config: &Config) {
    let active_role = state.current_agent.as_ref().map(|(role, _)| role.clone());

    // Map any active role to its pipeline box index.
    // Builder, Reviewer, and Fixer all map to IMPLEMENT (index 2).
    let active_index = active_role
        .as_ref()
        .and_then(|role| match role {
            AgentRole::Scout => Some(0),
            AgentRole::Planner => Some(1),
            AgentRole::Builder | AgentRole::Reviewer | AgentRole::Fixer => Some(2),
            _ => None,
        });

    let roles = config.role_configs();

    struct StageInfo {
        label: &'static str,
        model_label: String,
        style: Style,
    }

    let stages: Vec<StageInfo> = [
        ("SCOUT", Some(0)),
        ("PLAN", Some(1)),
        ("IMPLEMENT", Some(2)),
        ("SHIP", None), // ship it Ralph
    ]
    .iter()
    .enumerate()
    .map(|(i, (label, role_idx))| {
        let model_label = if let Some(ri) = role_idx {
            if *ri < roles.len() {
                let (_name, provider, model) = roles[*ri];
                let p = Config::parse_provider(provider);
                let m = model.trim();
                let display = if m.is_empty() {
                    format!("{}", p)
                } else {
                    format!("{} {}", p, m)
                };
                truncate_str(&display, 14).to_string()
            } else {
                String::new()
            }
        } else {
            String::new()
        };

        let style = match active_index {
            Some(ai) if i == ai => Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
            Some(ai) if i < ai => {
                // Completed stage (stages always run in strict order)
                Style::default().fg(Color::Green)
            }
            _ => Style::default().fg(Color::DarkGray),
        };

        StageInfo {
            label,
            model_label,
            style,
        }
    })
    .collect();

    // Build styled lines for the subway map
    let box_width = 14usize; // Fits "Claude sonnet" (13 chars) with padding

    let pipe_color = Color::Rgb(227, 115, 75); // Claude Code orange (#E3734B)

    // Per-stage border color: active stage gets orange highlight, completed green, rest dim.
    let border_colors: Vec<Color> = stages
        .iter()
        .enumerate()
        .map(|(i, _)| match active_index {
            Some(ai) if i == ai => pipe_color,     // Orange for active
            Some(ai) if i < ai => Color::Green,
            _ => Color::DarkGray,
        })
        .collect();

    // Top border line
    let top_spans: Vec<Span> = {
        let mut s = vec![Span::raw("  ")];
        for (i, _stage) in stages.iter().enumerate() {
            s.push(Span::styled(
                format!("\u{256d}{}\u{256e}", "\u{2500}".repeat(box_width)),
                Style::default().fg(border_colors[i]),
            ));
            if i < stages.len() - 1 {
                s.push(Span::raw("    "));
            }
        }
        s
    };

    // Middle line (labels)
    let mid_spans: Vec<Span> = {
        let mut s = vec![Span::raw("  ")];
        for (i, stage) in stages.iter().enumerate() {
            let pad_total = box_width.saturating_sub(stage.label.len());
            let left = pad_total / 2;
            let right = pad_total - left;
            s.push(Span::styled(
                "\u{2502}",
                Style::default().fg(border_colors[i]),
            ));
            s.push(Span::styled(
                format!("{}{}{}", " ".repeat(left), stage.label, " ".repeat(right)),
                stage.style,
            ));
            s.push(Span::styled(
                "\u{2502}",
                Style::default().fg(border_colors[i]),
            ));
            if i < stages.len() - 1 {
                s.push(Span::styled(
                    "\u{2500}\u{2500}\u{25b6}\u{2500}",
                    Style::default().fg(pipe_color),
                ));
            }
        }
        s
    };

    // Model label line
    let model_spans: Vec<Span> = {
        let mut s = vec![Span::raw("  ")];
        for (i, stage) in stages.iter().enumerate() {
            let pad_total = box_width.saturating_sub(stage.model_label.len());
            let left = pad_total / 2;
            let right = pad_total - left;
            s.push(Span::styled(
                "\u{2502}",
                Style::default().fg(border_colors[i]),
            ));
            s.push(Span::styled(
                format!(
                    "{}{}{}",
                    " ".repeat(left),
                    stage.model_label,
                    " ".repeat(right)
                ),
                Style::default().fg(Color::DarkGray),
            ));
            s.push(Span::styled(
                "\u{2502}",
                Style::default().fg(border_colors[i]),
            ));
            if i < stages.len() - 1 {
                s.push(Span::raw("    "));
            }
        }
        s
    };

    // Bottom border line
    let bot_spans: Vec<Span> = {
        let mut s = vec![Span::raw("  ")];
        for (i, _stage) in stages.iter().enumerate() {
            s.push(Span::styled(
                format!("\u{2570}{}\u{256f}", "\u{2500}".repeat(box_width)),
                Style::default().fg(border_colors[i]),
            ));
            if i < stages.len() - 1 {
                s.push(Span::raw("    "));
            }
        }
        s
    };

    let lines = vec![
        Line::from(""),
        Line::from(top_spans),
        Line::from(mid_spans),
        Line::from(model_spans),
        Line::from(bot_spans),
    ];

    let pipeline = Paragraph::new(lines).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " Pipeline ",
                Style::default()
                    .fg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(pipeline, area);
}

fn render_dashboard_stats(frame: &mut Frame, area: Rect, state: &AppState, _config: &Config) {
    let mut lines = Vec::new();

    // Progress bar
    let completed = state.completed_count;
    let total = state.total_count;
    let bar_width = area.width.saturating_sub(6) as usize; // leave room for borders + label
    let filled = if total > 0 {
        (completed as f64 / total as f64 * bar_width as f64) as usize
    } else {
        0
    };
    let empty = bar_width.saturating_sub(filled);
    let pct = if total > 0 { completed * 100 / total } else { 0 };
    lines.push(Line::from(vec![
        Span::styled(
            "\u{2588}".repeat(filled),
            Style::default().fg(Color::Green),
        ),
        Span::styled(
            "\u{2591}".repeat(empty),
            Style::default().fg(Color::DarkGray),
        ),
        Span::styled(
            format!(" {}%", pct),
            Style::default().fg(Color::White),
        ),
    ]));

    // Git stats
    lines.push(Line::from(vec![
        Span::styled("  Git      ", Style::default().fg(Color::Cyan)),
        Span::styled("feat: ", Style::default().fg(Color::DarkGray)),
        Span::styled(
            format!("{}", state.session_feat_commits),
            Style::default().fg(Color::Green),
        ),
        Span::styled("  WIP: ", Style::default().fg(Color::DarkGray)),
        Span::styled(
            format!("{}", state.session_wip_commits),
            Style::default().fg(Color::Yellow),
        ),
    ]));

    lines.push(Line::from(""));

    // Patterns + Ollama status
    let (ollama_label, ollama_color) = match state.last_pattern_match_mode.as_deref() {
        Some("semantic") => ("Ollama: connected", Color::Green),
        Some("cooldown") => ("Ollama: down", Color::Red),
        Some("keyword-only") => ("Ollama: off", Color::Yellow),
        _ => ("Ollama: --", Color::DarkGray),
    };
    lines.push(Line::from(vec![
        Span::styled("  Patterns ", Style::default().fg(Color::Cyan)),
        Span::styled("learned: ", Style::default().fg(Color::DarkGray)),
        Span::styled(
            format!("{}", state.session_patterns_learned),
            Style::default().fg(Color::White),
        ),
    ]));
    lines.push(Line::from(vec![
        Span::styled("           ", Style::default()),
        Span::styled(ollama_label, Style::default().fg(ollama_color)),
    ]));

    // Review findings
    if state.session_review_high > 0 || state.session_review_medium > 0 || state.session_review_low > 0 {
        lines.push(Line::from(vec![
            Span::styled("  Review   ", Style::default().fg(Color::Cyan)),
            Span::styled(
                format!("{}", state.session_review_high),
                Style::default().fg(if state.session_review_high > 0 { Color::Red } else { Color::DarkGray }),
            ),
            Span::styled(" high  ", Style::default().fg(Color::DarkGray)),
            Span::styled(
                format!("{}", state.session_review_medium),
                Style::default().fg(if state.session_review_medium > 0 { Color::Yellow } else { Color::DarkGray }),
            ),
            Span::styled(" med", Style::default().fg(Color::DarkGray)),
        ]));
    }

    // Timing
    let now = chrono::Utc::now();
    let session_elapsed = now.signed_duration_since(state.session_start);
    let session_str = format_duration_hms(session_elapsed);

    let task_str = state
        .task_start
        .map(|ts| format_duration_hms(now.signed_duration_since(ts)))
        .unwrap_or_else(|| "--:--".to_string());

    let agent_str = state
        .current_agent
        .as_ref()
        .map(|(_, started)| format_duration_hms(now.signed_duration_since(*started)))
        .unwrap_or_else(|| "--:--".to_string());

    lines.push(Line::from(vec![
        Span::styled("  Timing   ", Style::default().fg(Color::Cyan)),
        Span::styled("session: ", Style::default().fg(Color::DarkGray)),
        Span::styled(&session_str, Style::default().fg(Color::White)),
    ]));
    lines.push(Line::from(vec![
        Span::styled("           ", Style::default().fg(Color::Cyan)),
        Span::styled("task: ", Style::default().fg(Color::DarkGray)),
        Span::styled(&task_str, Style::default().fg(Color::White)),
        Span::styled("  agent: ", Style::default().fg(Color::DarkGray)),
        Span::styled(&agent_str, Style::default().fg(Color::White)),
    ]));

    lines.push(Line::from(""));

    // Agent status
    let agent_label = state
        .current_agent
        .as_ref()
        .map(|(role, _)| {
            let model = state.current_agent_model.as_deref().unwrap_or("?");
            format!("{} ({})", role, model)
        })
        .unwrap_or_else(|| "idle".to_string());

    lines.push(Line::from(vec![
        Span::styled("  Agent    ", Style::default().fg(Color::Cyan)),
        Span::styled(
            agent_label,
            if state.current_agent.is_some() {
                Style::default()
                    .fg(Color::Yellow)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(Color::DarkGray)
            },
        ),
    ]));

    if state.current_agent.is_some() {
        let spinner_chars = ['|', '/', '-', '\\'];
        let spinner = spinner_chars[state.tick_count % spinner_chars.len()];
        let activity = if state.agent_output.is_empty() {
            format!("  {} thinking...", spinner)
        } else {
            format!("  {} {} events", spinner, state.events_received)
        };
        lines.push(Line::from(Span::styled(
            format!("           {}", activity),
            Style::default().fg(Color::DarkGray),
        )));
    }

    let stats_block = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    " Stats ",
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(stats_block, area);
}

fn render_session_config(frame: &mut Frame, area: Rect, config: &Config) {
    let header = Row::new(vec![
        Cell::from(Span::styled(
            "Role",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Provider",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Model",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Timeout",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Pause",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
    ]);

    let rows: Vec<Row> = config
        .role_configs()
        .iter()
        .map(|(role, provider, model)| {
            Row::new(vec![
                Cell::from(Span::styled(*role, Style::default().fg(Color::White))),
                Cell::from(Span::styled(
                    Config::parse_provider(provider).to_string(),
                    Style::default().fg(Color::Gray),
                )),
                Cell::from(Span::styled(
                    if model.is_empty() { "(default)" } else { model },
                    Style::default().fg(Color::Gray),
                )),
                Cell::from(Span::styled(
                    format!("{}s", config.agent_timeout_secs),
                    Style::default().fg(Color::DarkGray),
                )),
                Cell::from(Span::styled(
                    format!(
                        "{}s/{}s",
                        config.pause_between_agents_secs, config.pause_between_tasks_secs
                    ),
                    Style::default().fg(Color::DarkGray),
                )),
            ])
        })
        .collect();

    let widths = [
        Constraint::Length(12),
        Constraint::Length(10),
        Constraint::Length(14),
        Constraint::Length(10),
        Constraint::Length(10),
    ];

    let table = Table::new(rows, widths).header(header).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " Build Loop ",
                Style::default()
                    .fg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(table, area);
}

fn render_orchestrator_config(frame: &mut Frame, area: Rect, config: &Config) {
    let header = Row::new(vec![
        Cell::from(Span::styled(
            "Role",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Provider",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Model",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Max Iters",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
        Cell::from(Span::styled(
            "Accept Policy",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        )),
    ]);

    let rows = vec![
        Row::new(vec![
            Cell::from(Span::styled("Proposer", Style::default().fg(Color::White))),
            Cell::from(Span::styled(
                Config::parse_provider(&config.orchestrator_proposer_provider).to_string(),
                Style::default().fg(Color::Gray),
            )),
            Cell::from(Span::styled(
                if config.orchestrator_proposer_model.is_empty() {
                    "(default)"
                } else {
                    &config.orchestrator_proposer_model
                },
                Style::default().fg(Color::Gray),
            )),
            Cell::from(Span::styled(
                format!("{}", config.orchestrator_max_iterations),
                Style::default().fg(Color::DarkGray),
            )),
            Cell::from(Span::styled(
                &config.orchestrator_accept_policy,
                Style::default().fg(Color::DarkGray),
            )),
        ]),
        Row::new(vec![
            Cell::from(Span::styled("Reviewer", Style::default().fg(Color::White))),
            Cell::from(Span::styled(
                Config::parse_provider(&config.orchestrator_reviewer_provider).to_string(),
                Style::default().fg(Color::Gray),
            )),
            Cell::from(Span::styled(
                if config.orchestrator_reviewer_model.is_empty() {
                    "(default)"
                } else {
                    &config.orchestrator_reviewer_model
                },
                Style::default().fg(Color::Gray),
            )),
            Cell::from(Span::styled("", Style::default())),
            Cell::from(Span::styled("", Style::default())),
        ]),
    ];

    let widths = [
        Constraint::Length(12),
        Constraint::Length(10),
        Constraint::Length(14),
        Constraint::Length(10),
        Constraint::Length(16),
    ];

    let table = Table::new(rows, widths).header(header).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                " Doubt Loop ",
                Style::default()
                    .fg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(table, area);
}

// ─── Patterns View ────────────────────────────────────────────

pub fn render_patterns(frame: &mut Frame, state: &AppState, config: &Config) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(10),   // Patterns list
            Constraint::Length(1), // Status bar
        ])
        .split(frame.area());

    render_patterns_list(frame, chunks[0], state, config);
    render_patterns_status_bar(frame, chunks[1], state);
}

// ─── Findings View ────────────────────────────────────────────

pub fn render_findings(frame: &mut Frame, state: &AppState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(10),   // Findings list
            Constraint::Length(1), // Status bar
        ])
        .split(frame.area());

    render_findings_list(frame, chunks[0], state);
    render_findings_status_bar(frame, chunks[1], state);
}

fn render_findings_list(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(ref outcome) = state.last_orchestrator_outcome else {
        let empty = Paragraph::new(vec![
            Line::from(""),
            Line::from(Span::styled(
                "  No review findings available.",
                Style::default().fg(Color::DarkGray),
            )),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    " Review Findings ",
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    };

    let max_lines = area.height.saturating_sub(2) as usize;
    let inner_width = area.width.saturating_sub(4) as usize;
    let mut display_lines: Vec<Line> = Vec::new();

    // Summary
    let status_color = if outcome.accepted {
        Color::Green
    } else {
        Color::Yellow
    };
    let status_label = if outcome.accepted {
        "accepted"
    } else {
        "unresolved findings"
    };
    display_lines.push(Line::from(vec![
        Span::styled("  Status: ", Style::default().fg(Color::White)),
        Span::styled(
            status_label,
            Style::default()
                .fg(status_color)
                .add_modifier(Modifier::BOLD),
        ),
    ]));
    display_lines.push(Line::from(Span::styled(
        format!("  Iterations: {}", outcome.iterations),
        Style::default().fg(Color::White),
    )));
    display_lines.push(Line::from(""));

    // Findings section
    let finding_count = outcome.final_review.findings.len();
    display_lines.push(Line::from(Span::styled(
        format!("  Findings ({})", finding_count),
        Style::default()
            .fg(Color::White)
            .add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));

    if outcome.final_review.findings.is_empty() {
        display_lines.push(Line::from(Span::styled(
            "  No findings.",
            Style::default().fg(Color::DarkGray),
        )));
        display_lines.push(Line::from(""));
    } else {
        for finding in &outcome.final_review.findings {
            let severity_style = match finding.severity.to_ascii_lowercase().as_str() {
                "high" => Style::default().fg(Color::Red).add_modifier(Modifier::BOLD),
                "medium" => Style::default().fg(Color::Yellow),
                _ => Style::default().fg(Color::Gray),
            };
            let severity_label = finding.severity.to_ascii_uppercase();
            let desc_width = inner_width.saturating_sub(severity_label.len() + 4);

            display_lines.push(Line::from(vec![
                Span::styled(format!(" {} ", severity_label), severity_style),
                Span::styled(
                    truncate_str(&finding.description, desc_width).to_string(),
                    Style::default().fg(Color::White),
                ),
            ]));

            if !finding.location.is_empty() {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "      at {}",
                        truncate_str(&finding.location, inner_width.saturating_sub(9))
                    ),
                    Style::default().fg(Color::DarkGray),
                )));
            }

            if !finding.suggestion.is_empty() {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "      Suggestion: {}",
                        truncate_str(&finding.suggestion, inner_width.saturating_sub(18))
                    ),
                    Style::default().fg(Color::Cyan),
                )));
            }

            display_lines.push(Line::from(""));
        }
    }

    // Validated claims section
    let validated_count = outcome.final_review.validated.len();
    display_lines.push(Line::from(Span::styled(
        format!("  Validated Claims ({})", validated_count),
        Style::default()
            .fg(Color::Green)
            .add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));

    if outcome.final_review.validated.is_empty() {
        display_lines.push(Line::from(Span::styled(
            "  No claims validated.",
            Style::default().fg(Color::DarkGray),
        )));
    } else {
        for claim in &outcome.final_review.validated {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  \u{2713} {}",
                    truncate_str(claim, inner_width.saturating_sub(4))
                ),
                Style::default().fg(Color::Green),
            )));
        }
    }

    let total_lines = display_lines.len();
    let scroll = state
        .findings_scroll
        .min(total_lines.saturating_sub(max_lines));
    let visible: Vec<Line> = display_lines
        .into_iter()
        .skip(scroll)
        .take(max_lines)
        .collect();

    let title = if outcome.accepted {
        " Review Findings "
    } else {
        " Review Findings (unresolved) "
    };

    let paragraph = Paragraph::new(visible).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(paragraph, area);
}

fn render_findings_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut spans = vec![
        Span::styled(
            " f ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" back  "),
        Span::styled(
            " \u{2191}\u{2193} ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit"),
    ];

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

fn render_patterns_list(frame: &mut Frame, area: Rect, state: &AppState, config: &Config) {
    use crate::patterns;

    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    let all_patterns = patterns::load_patterns(&patterns_dir);

    if all_patterns.is_empty() {
        let empty = Paragraph::new(vec![
            Line::from(""),
            Line::from(Span::styled(
                "  No patterns learned yet.",
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(""),
            Line::from(Span::styled(
                "  Patterns are extracted after each task completes.",
                Style::default().fg(Color::DarkGray),
            )),
            Line::from(Span::styled(
                format!("  They will appear in: {}", patterns_dir.display()),
                Style::default().fg(Color::DarkGray),
            )),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    " Learned Patterns ",
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let max_lines = area.height.saturating_sub(2) as usize;
    let inner_width = area.width.saturating_sub(4) as usize;

    // Each pattern takes 3 display lines: title, issue, solution
    let mut display_lines: Vec<Line> = Vec::new();

    for pattern in &all_patterns {
        let severity_style = match pattern.severity.as_deref() {
            Some("HIGH") => Style::default().fg(Color::Red).add_modifier(Modifier::BOLD),
            Some("MEDIUM") => Style::default().fg(Color::Yellow),
            _ => Style::default().fg(Color::Gray),
        };
        let severity = pattern.severity.as_deref().unwrap_or("LOW");
        let freq_label = if pattern.frequency > 1 {
            format!(" (seen {}x)", pattern.frequency)
        } else {
            String::new()
        };
        let auto_label = if pattern.auto_apply { " [auto]" } else { "" };

        display_lines.push(Line::from(vec![
            Span::styled(format!(" {} ", severity), severity_style),
            Span::styled(
                truncate_str(
                    &pattern.title,
                    inner_width
                        .saturating_sub(severity.len() + freq_label.len() + auto_label.len() + 4),
                ),
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(
                format!("{}{}", freq_label, auto_label),
                Style::default().fg(Color::DarkGray),
            ),
        ]));

        if let Some(ref issue) = pattern.issue {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "      {}",
                    truncate_str(issue, inner_width.saturating_sub(6))
                ),
                Style::default().fg(Color::Gray),
            )));
        }

        if let Some(ref solution) = pattern.solution {
            if !solution.planner.is_empty() {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "      Fix: {}",
                        truncate_str(&solution.planner, inner_width.saturating_sub(11))
                    ),
                    Style::default().fg(Color::Cyan),
                )));
            }
        }

        display_lines.push(Line::from(""));
    }

    let total_lines = display_lines.len();
    let scroll = state
        .patterns_scroll
        .min(total_lines.saturating_sub(max_lines));
    let visible: Vec<Line> = display_lines
        .into_iter()
        .skip(scroll)
        .take(max_lines)
        .collect();

    let title = format!(" Learned Patterns ({}) ", all_patterns.len());

    let paragraph = Paragraph::new(visible).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(paragraph, area);
}

fn render_patterns_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let back_label = " back  ";
    let mut spans = vec![
        Span::styled(
            " p ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(back_label),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit"),
    ];

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

fn format_duration_hms(duration: chrono::Duration) -> String {
    let total_secs = duration.num_seconds().max(0);
    let hours = total_secs / 3600;
    let mins = (total_secs % 3600) / 60;
    let secs = total_secs % 60;
    if hours > 0 {
        format!("{}h {:02}m {:02}s", hours, mins, secs)
    } else {
        format!("{}m {:02}s", mins, secs)
    }
}

pub fn render_startup(frame: &mut Frame, state: &AppState) {
    let layout = startup_layout(frame.area(), state);

    render_startup_summary(frame, layout.summary, state);
    render_startup_actions(frame, layout.actions, state);
    if let Some(flow_area) = layout.flow {
        render_startup_flow(frame, flow_area, state);
    }
    render_startup_content(frame, layout.content, state);
    render_startup_status_bar(frame, layout.status, state);
}

pub fn startup_hit_test(
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

fn startup_layout(area: Rect, _state: &AppState) -> StartupLayout {
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

fn render_header(frame: &mut Frame, area: Rect, state: &AppState) {
    let completed = state.completed_count;
    let total = state.total_count;
    let pct = if total > 0 {
        (completed as f64 / total as f64) * 100.0
    } else {
        0.0
    };

    let desc_width = area.width.saturating_sub(10) as usize;
    let task_line = if let Some(ref task) = state.current_task {
        format!("  {} — {}", task.id, task.short_desc(desc_width))
    } else if let Some(ref planning) = state.planning {
        if planning.orchestrator_mode {
            let iter_label = if planning.orchestrator_iteration > 0 {
                format!(
                    "Iteration {}/{}",
                    planning.orchestrator_iteration, planning.orchestrator_max_iterations
                )
            } else {
                "Starting...".to_string()
            };
            let role = planning
                .orchestrator_role_label
                .as_deref()
                .unwrap_or("Preparing");
            let model_suffix = if let Some(ref model) = planning.orchestrator_role_model {
                format!(" with {}", model)
            } else {
                String::new()
            };
            let findings = if planning.orchestrator_finding_count > 0 {
                format!(" | {} finding(s)", planning.orchestrator_finding_count)
            } else {
                String::new()
            };
            format!("  Design — {}: {}{}{}", iter_label, role, model_suffix, findings)
        } else {
            format!("  Planning — {}", planning.label)
        }
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
            "  ⎿ {} ({}) | {}m {}s | {}",
            role, model, mins, secs, activity
        )
    } else {
        String::new()
    };

    let brand = if state.project_name.is_empty() {
        "  FOUNDRY ".to_string()
    } else {
        format!("  {} ", state.project_name)
    };

    let mut header_text = vec![
        Line::from(vec![
            Span::styled(
                &brand,
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw(" "),
            Span::styled(
                if matches!(state.phase, AppPhase::Startup) {
                    " STOPPED "
                } else if state.stop_after_task {
                    " STOPPING "
                } else if state.run_mode == "hil" {
                    " RUNNING (Review) "
                } else {
                    " RUNNING "
                },
                Style::default()
                    .fg(Color::Black)
                    .bg(if matches!(state.phase, AppPhase::Startup) {
                        Color::DarkGray
                    } else if state.stop_after_task {
                        Color::Yellow
                    } else {
                        Color::Green
                    })
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw("  "),
            Span::styled(
                format!("[{}/{}] {:.0}%", completed, total, pct),
                Style::default()
                    .fg(Color::Yellow)
                    .add_modifier(Modifier::BOLD),
            ),
        ]),
        Line::from(Span::styled(
            task_line,
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            agent_line,
            Style::default().fg(Color::DarkGray),
        )),
    ];

    if let Some(next_task) = state.next_task_hint.as_ref() {
        header_text.push(Line::from(Span::styled(
            format!(
                "  Next: {}",
                truncate_str(next_task, area.width.saturating_sub(10) as usize)
            ),
            Style::default().fg(Color::Cyan),
        )));
    }

    // Log line removed from header -- the agent name + timer on line 3 already
    // conveys the same info. The status bar at the bottom shows the latest log.

    let header = Paragraph::new(header_text).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(Color::DarkGray)),
    );
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
            let first_char_len = remaining.chars().next().map(|c| c.len_utf8()).unwrap_or(1);
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
        Style::default().fg(Color::Cyan)
    } else if line.starts_with("[result]") {
        Style::default().fg(Color::DarkGray)
    } else if line.starts_with("[rate limited]") {
        Style::default().fg(Color::Yellow)
    } else if line.starts_with("[studio]") {
        Style::default().fg(Color::Cyan)
    } else if line.starts_with("[injected]") {
        Style::default()
            .fg(Color::Yellow)
            .add_modifier(Modifier::BOLD)
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
            AgentRole::Scout => Color::LightBlue,
            AgentRole::Planner => Color::Magenta,
            AgentRole::Builder => Color::Green,
            AgentRole::Reviewer => Color::Cyan,
            AgentRole::Fixer => Color::Yellow,
            AgentRole::Discovery => Color::Blue,
        };
        Span::styled(
            format!(" {} ", role),
            Style::default().fg(color).add_modifier(Modifier::BOLD),
        )
    } else {
        Span::styled(" Agent ", Style::default().fg(Color::DarkGray))
    };

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray))
            .title(title),
    );

    frame.render_widget(list, area);
}

fn render_task_queue(frame: &mut Frame, area: Rect, state: &AppState) {
    if state.task_queue.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " No tasks in queue yet.",
            Style::default().fg(Color::DarkGray),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::DarkGray))
                .title(Span::styled(
                    " Task Queue ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let max_lines = area.height.saturating_sub(2) as usize;
    let total = state.task_queue.len();
    let scroll = state.task_queue_scroll.min(total.saturating_sub(max_lines));
    let end = total.saturating_sub(scroll);
    let start = end.saturating_sub(max_lines);
    let inner_width = area.width.saturating_sub(4) as usize;

    let current_id = state.current_task.as_ref().map(|t| t.id.as_str());

    let items: Vec<ListItem> = state.task_queue[start..end]
        .iter()
        .map(|task| {
            let is_current = current_id == Some(task.id.as_str());

            // Color by task prefix: H=human(yellow), D=discovered(blue), T=planned(white)
            let prefix_color = if task.id.starts_with('H') {
                Color::Yellow
            } else if task.id.starts_with('D') {
                Color::Blue
            } else {
                Color::White
            };

            let was_wip = state
                .task_history
                .get(&task.id)
                .map(|h| !h.passed_review)
                .unwrap_or(false);

            let (icon, style) = if task.completed && was_wip {
                // WIP commit -- review failed
                ("\u{2717}", Style::default().fg(Color::Yellow))
            } else if task.completed {
                ("\u{25cf}", Style::default().fg(Color::Green))
            } else if is_current {
                (
                    "\u{25b6}",
                    Style::default()
                        .fg(prefix_color)
                        .add_modifier(Modifier::BOLD),
                )
            } else {
                ("\u{25cb}", Style::default().fg(Color::Gray))
            };

            // ID gets prefix color even when pending
            let id_style = if task.completed {
                style
            } else {
                Style::default().fg(prefix_color)
            };

            // Pipeline indicator for completed and current tasks
            let pipeline_spans = if let Some(history) = state.task_history.get(&task.id) {
                // Completed: show S>P>I>V with colors
                let all_stages = [
                    ("S", AgentRole::Scout),
                    ("P", AgentRole::Planner),
                    ("I", AgentRole::Builder),
                    ("V", AgentRole::Reviewer),
                ];
                let verify_color = if history.passed_review {
                    Color::Green
                } else {
                    Color::Red
                };
                let mut spans = vec![Span::styled(" ", Style::default())];
                for (label, role) in &all_stages {
                    let ran = history.stages_seen.contains(role);
                    let color = if !ran {
                        Color::DarkGray
                    } else if *role == AgentRole::Reviewer {
                        verify_color
                    } else {
                        Color::Green
                    };
                    let text = if ran {
                        label.to_string()
                    } else {
                        "-".to_string()
                    };
                    spans.push(Span::styled(text, Style::default().fg(color)));
                }
                if !history.passed_review {
                    spans.push(Span::styled("!", Style::default().fg(Color::Red)));
                }
                spans
            } else if is_current {
                // Current: show progress through pipeline
                let all_stages = [
                    ("S", AgentRole::Scout),
                    ("P", AgentRole::Planner),
                    ("I", AgentRole::Builder),
                    ("V", AgentRole::Reviewer),
                ];
                let active = state.current_agent.as_ref().map(|(r, _)| r);
                let mut spans = vec![Span::styled(" ", Style::default())];
                for (label, role) in &all_stages {
                    let seen = state.task_stages_seen.contains(role);
                    let is_active = active == Some(role);
                    let (text, color) = if is_active {
                        (label.to_string(), Color::Yellow)
                    } else if seen {
                        (label.to_string(), Color::Green)
                    } else {
                        (".".to_string(), Color::DarkGray)
                    };
                    let style = if is_active {
                        Style::default().fg(color).add_modifier(Modifier::BOLD)
                    } else {
                        Style::default().fg(color)
                    };
                    spans.push(Span::styled(text, style));
                }
                spans
            } else if task.completed {
                // Completed in a prior session -- no live pipeline data
                vec![Span::styled(
                    if was_wip { " \u{2717}" } else { " \u{2714}" },
                    Style::default().fg(if was_wip { Color::Yellow } else { Color::Green }),
                )]
            } else {
                // Pending: show anticipated pipeline in gray
                vec![Span::styled(" ....", Style::default().fg(Color::DarkGray))]
            };

            let pipeline_width: usize = pipeline_spans.iter().map(|s| s.width()).sum();
            let desc =
                task.short_desc(inner_width.saturating_sub(task.id.len() + 5 + pipeline_width));
            let mut spans = vec![
                Span::styled(format!(" {} ", icon), style),
                Span::styled(format!("{}: ", task.id), id_style),
                Span::styled(desc, style),
            ];
            spans.extend(pipeline_spans);
            ListItem::new(Line::from(spans))
        })
        .collect();

    let pending = total - state.completed_count;
    let title = format!(
        " Task Queue [{}/{} done | {} left] ",
        state.completed_count, total, pending
    );

    let list = List::new(items).block(
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

    frame.render_widget(list, area);
}

fn render_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    if matches!(state.phase, AppPhase::Planning) {
        render_planning_status_bar(frame, area, state);
        return;
    }

    let discovery_info = if state.discovery_round > 0 {
        format!(" | discovery round {} ", state.discovery_round)
    } else {
        String::new()
    };

    let mut spans = vec![
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" stop  "),
        Span::styled(
            " Ctrl+C ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" force quit  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " i ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" inject  "),
        Span::styled(
            " PgUp/PgDn ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" queue  "),
        Span::styled(
            " p ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" patterns"),
    ];

    if state.last_orchestrator_outcome.is_some() {
        spans.push(Span::styled(
            "  f ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw("findings"));
    }

    spans.push(Span::styled(discovery_info, Style::default().fg(Color::DarkGray)));

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available — `foundry update`", version),
            Style::default()
                .fg(Color::Green)
                .add_modifier(Modifier::BOLD),
        ));
    }

    let status = Line::from(spans);
    let bar = Paragraph::new(status);
    frame.render_widget(bar, area);
}

fn render_planning_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut spans = vec![
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " p ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" patterns"),
    ];

    if state.last_orchestrator_outcome.is_some() {
        spans.push(Span::styled(
            "  f ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw("findings"));
    }

    if let Some((_ts, msg)) = state.log_messages.last() {
        spans.push(Span::styled(
            format!("  {}", truncate_str(msg, 60)),
            Style::default().fg(Color::DarkGray),
        ));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available — `foundry update`", version),
            Style::default()
                .fg(Color::Green)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
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
    match selected_startup_action(state) {
        Some(StartupAction::DescribeWork) | Some(StartupAction::ScanProject) => {
            render_startup_intent(frame, area, state)
        }
        Some(StartupAction::ViewTasks) => render_startup_tasks(frame, area, state),
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
                " Describe The Project ".to_string(),
                "What do you want to build?".to_string(),
                format!(
                    "Foundry will save your brief in {}, turn it into initial tasks in {}, then start building.",
                    startup.spec_file_name, startup.tasks_file_name
                ),
                "Press Enter to create the brief and task queue.".to_string(),
            ),
            StartupScenario::NeedsQueue => (
                " Describe Next Work ".to_string(),
                "What do you want Foundry to do with this project?".to_string(),
                format!(
                    "Foundry will turn your description into task(s) in {} and start building. This does not scan the repo.",
                    startup.tasks_file_name
                ),
                "Press Enter to create tasks and start.".to_string(),
            ),
            StartupScenario::QueueReady => (
                " Describe More Work ".to_string(),
                "What else should be added to the queue?".to_string(),
                format!(
                    "Foundry will append task(s) to {} and then resume the build loop. Existing tasks stay in order.",
                    startup.tasks_file_name
                ),
                "Press Enter to add tasks and start.".to_string(),
            ),
            StartupScenario::QueueComplete => (
                " Describe Next Work ".to_string(),
                "What should happen next?".to_string(),
                format!(
                    "Foundry will turn your description into task(s) in {} and start building. This does not scan the repo.",
                    startup.tasks_file_name
                ),
                "Press Enter to create tasks and start.".to_string(),
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

fn startup_flow_next_label<'a>(state: &'a AppState, fallback: &'a str) -> String {
    state
        .startup
        .as_ref()
        .and_then(|startup| startup.next_pending_task.clone())
        .unwrap_or_else(|| fallback.to_string())
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

fn startup_preview_lines(state: &AppState) -> Option<&[String]> {
    let startup = state.startup.as_ref()?;
    match selected_startup_action(state) {
        Some(StartupAction::DescribeWork) | Some(StartupAction::ScanProject) => None,
        Some(StartupAction::EditSpec) => Some(&startup.spec_preview_lines),
        _ => Some(&startup.plan_preview_lines),
    }
}

fn selected_startup_action(state: &AppState) -> Option<StartupAction> {
    state
        .startup
        .as_ref()
        .and_then(|startup| startup.actions.get(startup.selected_action))
        .copied()
}

fn render_startup_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let Some(startup) = state.startup.as_ref() else {
        return;
    };

    let mut spans = if matches!(
        selected_startup_action(state),
        Some(StartupAction::DescribeWork) | Some(StartupAction::ScanProject)
    ) {
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
                spans.push(Span::raw("findings"));
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
        "review"
    } else {
        "auto"
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

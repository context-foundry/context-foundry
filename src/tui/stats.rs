use ratatui::{
    layout::{Constraint, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Cell, Paragraph, Row, Table, Wrap},
    Frame,
};

use crate::app::AppState;
use crate::config::Config;

pub(super) fn render_dashboard_stats(frame: &mut Frame, area: Rect, state: &AppState, _config: &Config) {
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

    // Cost and context usage
    lines.push(Line::from(vec![
        Span::styled("  Cost     ", Style::default().fg(Color::Cyan)),
        Span::styled(
            format!("${:.2}", state.session_cost_usd),
            Style::default().fg(Color::White),
        ),
        Span::styled("  ctx: ", Style::default().fg(Color::DarkGray)),
        Span::styled(
            state.agent_context_pct
                .map(|pct| format!("{}%", pct))
                .unwrap_or_else(|| "--".to_string()),
            Style::default().fg(match state.agent_context_pct {
                Some(p) if p >= 90 => Color::Red,
                Some(p) if p >= 70 => Color::Yellow,
                Some(_) => Color::Green,
                None => Color::DarkGray,
            }),
        ),
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

pub(super) fn render_session_config(frame: &mut Frame, area: Rect, config: &Config) {
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
                    if model.is_empty() {
                        "(default)".to_string()
                    } else {
                        // Capitalize first letter for display consistency
                        let mut chars = model.chars();
                        match chars.next() {
                            Some(c) => format!("{}{}", c.to_uppercase(), chars.as_str()),
                            None => String::new(),
                        }
                    },
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
                " Pipeline ",
                Style::default()
                    .fg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(table, area);
}

pub(super) fn render_orchestrator_config(frame: &mut Frame, area: Rect, config: &Config) {
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

pub(super) fn format_duration_hms(duration: chrono::Duration) -> String {
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

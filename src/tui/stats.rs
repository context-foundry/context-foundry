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
    let theme = &state.tui_theme;
    let mut lines = Vec::new();

    // Progress: [93/96] ████████████░░ 97%
    let completed = state.completed_count;
    let total = state.total_count;
    let pct = if total > 0 { completed * 100 / total } else { 0 };
    let left_label = format!(" [{}/{}] ", completed, total);
    let right_label = format!(" {}%", pct);
    let bar_width = (area.width.saturating_sub(4) as usize)
        .saturating_sub(left_label.len())
        .saturating_sub(right_label.len());
    let filled = if total > 0 {
        (completed as f64 / total as f64 * bar_width as f64) as usize
    } else {
        0
    };
    let empty = bar_width.saturating_sub(filled);
    let bar_spans: Vec<Span> = vec![
        Span::styled(
            left_label,
            Style::default().fg(theme.warning).add_modifier(ratatui::style::Modifier::BOLD),
        ),
        Span::styled(
            "\u{2588}".repeat(filled),
            Style::default().fg(theme.success),
        ),
        Span::styled(
            "\u{2591}".repeat(empty),
            Style::default().fg(theme.muted),
        ),
        Span::styled(
            right_label,
            Style::default().fg(theme.warning).add_modifier(ratatui::style::Modifier::BOLD),
        ),
    ];
    lines.push(Line::from(bar_spans));

    // Two-column layout: left = git + patterns, right = context + timing
    // We build each line with left and right halves padded to fill the width.
    let half_width = area.width.saturating_sub(4) as usize / 2; // borders + padding

    // ─── Row 1: Git | Context SPID ───
    let (ollama_label, ollama_color) = match state.last_pattern_match_mode.as_deref() {
        Some("semantic") => ("connected", Color::Green),
        Some("cooldown") => ("down", Color::Red),
        Some("keyword-only") => ("off", Color::Yellow),
        _ => ("--", Color::DarkGray),
    };

    fn ctx_pct_span(pct: Option<u8>) -> (String, Color) {
        match pct {
            Some(p) if p >= 90 => (format!("{}%", p), Color::Red),
            Some(p) if p >= 70 => (format!("{}%", p), Color::Yellow),
            Some(p) => (format!("{}%", p), Color::Green),
            None => ("--".to_string(), Color::DarkGray),
        }
    }

    let (s_str, s_col) = ctx_pct_span(state.spid_context_pcts[0]);
    let (p_str, p_col) = ctx_pct_span(state.spid_context_pcts[1]);
    let (i_str, i_col) = if state.dual_build.active
        && state.dual_build.context_pcts[0].is_some()
        && state.dual_build.context_pcts[1].is_some()
    {
        let (a_str, _) = ctx_pct_span(state.dual_build.context_pcts[0]);
        let (b_str, _) = ctx_pct_span(state.dual_build.context_pcts[1]);
        let max_pct = std::cmp::max(
            state.dual_build.context_pcts[0].unwrap_or(0),
            state.dual_build.context_pcts[1].unwrap_or(0),
        );
        let col = if max_pct >= 90 {
            Color::Red
        } else if max_pct >= 70 {
            Color::Yellow
        } else {
            Color::Green
        };
        (format!("{}/{}", a_str, b_str), col)
    } else {
        ctx_pct_span(state.spid_context_pcts[2])
    };
    let (d_str, d_col) = ctx_pct_span(state.spid_context_pcts[3]);

    let git_status_str = if state.git_initialized {
        let remote_part = state.git_remote.as_deref().unwrap_or("no remote");
        format!("{} | {} | {} dirty", state.git_branch, remote_part, state.git_dirty_count)
    } else {
        "not initialized".to_string()
    };
    let git_status_color = if !state.git_initialized {
        Color::Red
    } else if state.git_remote.is_none() {
        Color::Yellow
    } else {
        Color::Green
    };

    lines.push(Line::from(vec![
        Span::styled("  Git      ", Style::default().fg(theme.info)),
        Span::styled(format!("{:<width$}", git_status_str, width = half_width.saturating_sub(11)), Style::default().fg(git_status_color)),
        Span::styled("Context   ", Style::default().fg(theme.info)),
        Span::styled("S:", Style::default().fg(theme.muted)),
        Span::styled(format!("{:<4}", s_str), Style::default().fg(s_col)),
        Span::styled(" P:", Style::default().fg(theme.muted)),
        Span::styled(format!("{:<4}", p_str), Style::default().fg(p_col)),
        Span::styled(" I:", Style::default().fg(theme.muted)),
        Span::styled(format!("{:<4}", i_str), Style::default().fg(i_col)),
        Span::styled(" D:", Style::default().fg(theme.muted)),
        Span::styled(&d_str, Style::default().fg(d_col)),
    ]));

    // ─── Row 2: Extensions ───
    if !state.extension_inject_count.is_empty() {
        let ext_parts: Vec<String> = state
            .extension_inject_count
            .iter()
            .map(|(name, inj)| {
                let refs = state.extension_reference_count.get(name).copied().unwrap_or(0);
                format!("{} {} inj, {} ref", name, inj, refs)
            })
            .collect();
        lines.push(Line::from(vec![
            Span::styled("  Ext      ", Style::default().fg(theme.accent)),
            Span::styled(
                ext_parts.join("  "),
                Style::default().fg(theme.text),
            ),
        ]));
    }

    // ─── Row 3: Patterns + Ollama | Timing ───
    let now = chrono::Utc::now();
    let session_elapsed = now.signed_duration_since(state.session_start);
    let session_str = format_duration_hms(session_elapsed);

    let task_str = state
        .task_start
        .map(|ts| format_duration_hms(now.signed_duration_since(ts)))
        .unwrap_or_else(|| "--:--".to_string());

    lines.push(Line::from(vec![
        Span::styled("  Patterns ", Style::default().fg(theme.info)),
        Span::styled(format!("{} inj, {} applied", state.pattern_inject_count, state.pattern_apply_count), Style::default().fg(theme.text)),
        Span::styled("  session feat: ", Style::default().fg(theme.muted)),
        Span::styled(format!("{}", state.session_feat_commits), Style::default().fg(theme.success)),
        Span::styled("  session WIP: ", Style::default().fg(theme.muted)),
        Span::styled(format!("{}", state.session_wip_commits), Style::default().fg(theme.warning)),
        Span::styled("  Ollama: ", Style::default().fg(theme.muted)),
        Span::styled(format!("{:<width$}", ollama_label, width = half_width.saturating_sub(40)), Style::default().fg(ollama_color)),
        Span::styled("Timing    ", Style::default().fg(theme.info)),
        Span::styled("session: ", Style::default().fg(theme.muted)),
        Span::styled(&session_str, Style::default().fg(theme.text)),
        Span::styled("  task: ", Style::default().fg(theme.muted)),
        Span::styled(&task_str, Style::default().fg(theme.text)),
    ]));

    // ─── Row 3: left empty | Agent status on right ───
    let agent_label = state
        .current_agent
        .as_ref()
        .map(|(role, _)| {
            let model = state.current_agent_model.as_deref().unwrap_or("?");
            format!("{} ({})", role, model)
        })
        .unwrap_or_else(|| "idle".to_string());

    let agent_str = state
        .current_agent
        .as_ref()
        .map(|(_, started)| format_duration_hms(now.signed_duration_since(*started)))
        .unwrap_or_default();

    let left_pad = format!("{:<width$}", "", width = half_width);
    let mut agent_spans = vec![
        Span::styled(&left_pad, Style::default()),
        Span::styled("Agent     ", Style::default().fg(theme.info)),
        Span::styled(
            &agent_label,
            if state.current_agent.is_some() {
                Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme.muted)
            },
        ),
    ];
    if state.current_agent.is_some() {
        let spinner_chars = ['|', '/', '-', '\\'];
        let spinner = spinner_chars[state.tick_count % spinner_chars.len()];
        agent_spans.push(Span::styled(
            format!("  {} {} events  {}", spinner, state.events_received, agent_str),
            Style::default().fg(theme.muted),
        ));
    }
    lines.push(Line::from(agent_spans));

    let stats_block = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(theme.border))
                .title(Span::styled(
                    " Stats ",
                    Style::default()
                        .fg(theme.info)
                        .add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(stats_block, area);
}

#[allow(dead_code)]
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

#[allow(dead_code)]
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

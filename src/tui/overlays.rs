use ratatui::{
    layout::{Alignment, Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, Paragraph},
    Frame,
};

use crate::app::AppState;
use crate::config::Config;
use crate::utils::truncate_str;

pub(super) fn render_patterns(frame: &mut Frame, state: &AppState, config: &Config) {
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

pub(super) fn render_findings(frame: &mut Frame, state: &AppState) {
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
    let theme = &state.tui_theme;
    let Some(ref outcome) = state.last_orchestrator_outcome else {
        let empty = Paragraph::new(vec![
            Line::from(""),
            Line::from(Span::styled(
                "  No review findings available.",
                Style::default().fg(theme.muted),
            )),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(theme.border))
                .title(Span::styled(
                    " Review Findings ",
                    Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
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
        Span::styled("  Status: ", Style::default().fg(theme.text)),
        Span::styled(
            status_label,
            Style::default()
                .fg(status_color)
                .add_modifier(Modifier::BOLD),
        ),
    ]));
    display_lines.push(Line::from(Span::styled(
        format!("  Iterations: {}", outcome.iterations),
        Style::default().fg(theme.text),
    )));
    display_lines.push(Line::from(""));

    // Findings section
    let finding_count = outcome.final_review.findings.len();
    display_lines.push(Line::from(Span::styled(
        format!("  Findings ({})", finding_count),
        Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));

    if outcome.final_review.findings.is_empty() {
        display_lines.push(Line::from(Span::styled(
            "  No findings.",
            Style::default().fg(theme.muted),
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
                    Style::default().fg(theme.text),
                ),
            ]));

            if !finding.location.is_empty() {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "      at {}",
                        truncate_str(&finding.location, inner_width.saturating_sub(9))
                    ),
                    Style::default().fg(theme.muted),
                )));
            }

            if !finding.suggestion.is_empty() {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "      Suggestion: {}",
                        truncate_str(&finding.suggestion, inner_width.saturating_sub(18))
                    ),
                    Style::default().fg(theme.info),
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
            .fg(theme.success)
            .add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));

    if outcome.final_review.validated.is_empty() {
        display_lines.push(Line::from(Span::styled(
            "  No claims validated.",
            Style::default().fg(theme.muted),
        )));
    } else {
        for claim in &outcome.final_review.validated {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  \u{2713} {}",
                    truncate_str(claim, inner_width.saturating_sub(4))
                ),
                Style::default().fg(theme.success),
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
            .border_style(Style::default().fg(theme.border))
            .title(Span::styled(
                title,
                Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
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
                .bg(state.tui_theme.info)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" back  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit"),
    ];

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available", version),
            Style::default()
                .fg(state.tui_theme.success)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn render_patterns_list(frame: &mut Frame, area: Rect, state: &AppState, config: &Config) {
    let theme = &state.tui_theme;
    use crate::patterns;

    // Use cached patterns (populated when 'p' is pressed) to avoid
    // loading 800+ patterns from disk on every render frame (10fps).
    let fallback;
    let (all_patterns, patterns_dir) =
        if let (Some(cached), Some(dir)) = (&state.patterns_cache, &state.patterns_dir_cache) {
            (cached.as_slice(), dir.clone())
        } else {
            let dir = patterns::resolve_patterns_dir(&config.patterns_dir);
            fallback = patterns::load_patterns(&dir);
            (fallback.as_slice(), dir)
        };

    if all_patterns.is_empty() {
        let empty = Paragraph::new(vec![
            Line::from(""),
            Line::from(Span::styled(
                "  No patterns learned yet.",
                Style::default().fg(theme.muted),
            )),
            Line::from(""),
            Line::from(Span::styled(
                "  Patterns are extracted after each task completes.",
                Style::default().fg(theme.muted),
            )),
            Line::from(Span::styled(
                format!("  They will appear in: {}", patterns_dir.display()),
                Style::default().fg(theme.muted),
            )),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(theme.border))
                .title(Span::styled(
                    " Learned Patterns ",
                    Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let max_lines = area.height.saturating_sub(2) as usize;
    let inner_width = area.width.saturating_sub(4) as usize;

    // Each pattern takes 3 display lines: title, issue, solution
    let mut display_lines: Vec<Line> = Vec::new();

    for pattern in all_patterns {
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
                Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
            ),
            Span::styled(
                format!("{}{}", freq_label, auto_label),
                Style::default().fg(theme.muted),
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
                    Style::default().fg(theme.info),
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

    let title = format!(
        " Learned Patterns ({}) | {} ",
        all_patterns.len(),
        patterns_dir.display()
    );

    let paragraph = Paragraph::new(visible).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.border))
            .title(Span::styled(
                title,
                Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
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
                .bg(state.tui_theme.info)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(back_label),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit"),
    ];

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available", version),
            Style::default()
                .fg(state.tui_theme.success)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

// ─── Stats Overlay ──────────────────────────────────────────

pub(super) fn render_stats_overlay(frame: &mut Frame, state: &AppState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(10),   // Content area
            Constraint::Length(1), // Status bar
        ])
        .split(frame.area());

    render_stats_overlay_content(frame, chunks[0], state);
    render_stats_overlay_status_bar(frame, chunks[1], state);
}

fn render_stats_overlay_content(frame: &mut Frame, area: Rect, state: &AppState) {
    let theme = &state.tui_theme;

    let Some(ref report) = state.stats_overlay_report else {
        let empty = Paragraph::new(vec![
            Line::from(""),
            Line::from(Span::styled(
                "  No stats data available.",
                Style::default().fg(theme.muted),
            )),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(theme.border))
                .title(Span::styled(
                    " Stats Report ",
                    Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    };

    let mut display_lines: Vec<Line> = Vec::new();

    // ── Session Summary ──
    display_lines.push(Line::from(Span::styled(
        "  Session Summary",
        Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));
    display_lines.push(Line::from(Span::styled(
        format!("  Sessions: {}", report.summary.total_sessions),
        Style::default().fg(theme.text),
    )));
    display_lines.push(Line::from(Span::styled(
        format!("  Tasks: {}", report.summary.total_tasks),
        Style::default().fg(theme.text),
    )));
    let ratio_str = match report.summary.feat_wip_ratio {
        Some(r) => format!("{:.1}", r),
        None => "n/a".to_string(),
    };
    display_lines.push(Line::from(Span::styled(
        format!(
            "  Commits: {} feat / {} WIP (ratio: {})",
            report.summary.feat_count, report.summary.wip_count, ratio_str
        ),
        Style::default().fg(theme.text),
    )));
    display_lines.push(Line::from(Span::styled(
        format!("  Total Cost: ${:.2}", report.summary.total_cost_usd),
        Style::default().fg(theme.text),
    )));
    display_lines.push(Line::from(""));

    // ── Cost by Phase ──
    display_lines.push(Line::from(Span::styled(
        "  Cost by Phase",
        Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));
    if report.phase_costs.is_empty() {
        display_lines.push(Line::from(Span::styled(
            "  (no data)",
            Style::default().fg(theme.muted),
        )));
    } else {
        display_lines.push(Line::from(Span::styled(
            format!(
                "  {:<16} {:>6} {:>10} {:>10} {:>10}",
                "Role", "Runs", "Cost ($)", "Tokens In", "Tokens Out"
            ),
            Style::default().fg(theme.muted),
        )));
        for entry in &report.phase_costs {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  {:<16} {:>6} {:>10.2} {:>10} {:>10}",
                    entry.role,
                    entry.invocations,
                    entry.cost_usd,
                    fmt_overlay_tokens(entry.tokens_in),
                    fmt_overlay_tokens(entry.tokens_out),
                ),
                Style::default().fg(theme.text),
            )));
        }
    }
    display_lines.push(Line::from(""));

    // ── Quality Signals ──
    display_lines.push(Line::from(Span::styled(
        "  Quality Signals",
        Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));
    match report.quality.doubt_finding_rate {
        Some(r) => {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  Doubt finding rate: {:.1}% ({} of {} reviewed tasks had findings)",
                    r * 100.0,
                    report.quality.tasks_with_findings,
                    report.quality.tasks_reviewed,
                ),
                Style::default().fg(theme.text),
            )));
        }
        None => {
            display_lines.push(Line::from(Span::styled(
                "  Doubt finding rate: n/a (no reviewed tasks)",
                Style::default().fg(theme.text),
            )));
        }
    }
    match report.quality.budget_overrun_rate {
        Some(r) => {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  Budget overrun rate: {:.1}% ({} of {} budgeted executions)",
                    r * 100.0,
                    report.quality.budget_overruns,
                    report.quality.budgeted_executions,
                ),
                Style::default().fg(theme.text),
            )));
        }
        None => {
            display_lines.push(Line::from(Span::styled(
                "  Budget overrun rate: n/a",
                Style::default().fg(theme.text),
            )));
        }
    }
    if !report.summary.pass_rate_by_complexity.is_empty() {
        display_lines.push(Line::from(Span::styled(
            "  Pass Rate by Complexity:",
            Style::default().fg(theme.text),
        )));
        for c in &report.summary.pass_rate_by_complexity {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "    {:<12} {:.1}% ({}/{})",
                    c.complexity,
                    c.rate * 100.0,
                    c.feat,
                    c.total,
                ),
                Style::default().fg(theme.text),
            )));
        }
    }
    display_lines.push(Line::from(""));

    // ── Pattern Effectiveness (top 10) ──
    display_lines.push(Line::from(Span::styled(
        "  Pattern Effectiveness (top 10)",
        Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));
    display_lines.push(Line::from(Span::styled(
        format!(
            "  Total injections: {} ({} unique patterns)",
            report.patterns.total_injections, report.patterns.unique_patterns,
        ),
        Style::default().fg(theme.text),
    )));
    if report.patterns.effectiveness.is_empty() {
        display_lines.push(Line::from(Span::styled(
            "  (no data)",
            Style::default().fg(theme.muted),
        )));
    } else {
        display_lines.push(Line::from(Span::styled(
            format!(
                "  {:<36} {:>6} {:>6} {:>7} {:>6}",
                "Pattern", "Inj", "Cite", "Rate", "Signal"
            ),
            Style::default().fg(theme.muted),
        )));
        for eff in report.patterns.effectiveness.iter().take(10) {
            let pid = truncate_str(&eff.pattern_id, 36);
            let signal = if eff.low_signal { "LOW" } else { "ok" };
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  {:<36} {:>6} {:>6} {:>6.1}% {:>6}",
                    pid,
                    eff.injection_count,
                    eff.citation_count,
                    eff.citation_rate * 100.0,
                    signal,
                ),
                Style::default().fg(theme.text),
            )));
        }
    }
    display_lines.push(Line::from(""));

    // ── Trust Dashboard ──
    display_lines.push(Line::from(Span::styled(
        "  Trust Dashboard",
        Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
    )));
    display_lines.push(Line::from(""));
    if let Some(ref trust) = report.trust {
        match trust.acceptance_rate {
            Some(r) => {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "  Acceptance rate: {:.1}% ({} feat / {} completed)",
                        r * 100.0,
                        trust.feat_tasks,
                        trust.completed_tasks,
                    ),
                    Style::default().fg(theme.text),
                )));
            }
            None => {
                display_lines.push(Line::from(Span::styled(
                    "  Acceptance rate: n/a",
                    Style::default().fg(theme.text),
                )));
            }
        }
        match trust.review_rescue_rate {
            Some(r) => {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "  Review rescue rate: {:.1}% ({} rescued / {} with findings)",
                        r * 100.0,
                        trust.rescued_tasks,
                        trust.tasks_with_findings,
                    ),
                    Style::default().fg(theme.text),
                )));
            }
            None => {
                display_lines.push(Line::from(Span::styled(
                    "  Review rescue rate: n/a",
                    Style::default().fg(theme.text),
                )));
            }
        }
        display_lines.push(Line::from(Span::styled(
            format!("  Longest feat streak: {}", trust.longest_feat_streak),
            Style::default().fg(theme.text),
        )));
        if !trust.model_comparisons.is_empty() {
            display_lines.push(Line::from(Span::styled(
                "  Model Comparison:",
                Style::default().fg(theme.text),
            )));
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  {:<28} {:>6} {:>8} {:>10} {:>10}",
                    "Model", "Tasks", "Feat %", "Avg Cost", "Avg Dur"
                ),
                Style::default().fg(theme.muted),
            )));
            for mc in &trust.model_comparisons {
                display_lines.push(Line::from(Span::styled(
                    format!(
                        "  {:<28} {:>6} {:>7.1}% {:>10.2} {:>10.0}",
                        truncate_str(&mc.model_key, 28),
                        mc.task_count,
                        mc.feat_rate * 100.0,
                        mc.avg_cost_per_task,
                        mc.avg_duration_per_task,
                    ),
                    Style::default().fg(theme.text),
                )));
            }
        }
    } else {
        display_lines.push(Line::from(Span::styled(
            "  (no data)",
            Style::default().fg(theme.muted),
        )));
    }
    display_lines.push(Line::from(""));

    // ── Cache Efficiency ──
    if let Some(ref cache) = report.cache_efficiency {
        display_lines.push(Line::from(Span::styled(
            "  Cache Efficiency",
            Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
        )));
        display_lines.push(Line::from(""));
        display_lines.push(Line::from(Span::styled(
            format!(
                "  Cache read tokens: {}",
                fmt_overlay_tokens(cache.total_cache_read)
            ),
            Style::default().fg(theme.text),
        )));
        display_lines.push(Line::from(Span::styled(
            format!(
                "  Cache creation tokens: {}",
                fmt_overlay_tokens(cache.total_cache_creation)
            ),
            Style::default().fg(theme.text),
        )));
        let hit_str = match cache.cache_hit_ratio {
            Some(r) => format!("{:.1}%", r * 100.0),
            None => "n/a".to_string(),
        };
        display_lines.push(Line::from(Span::styled(
            format!("  Hit ratio: {}", hit_str),
            Style::default().fg(theme.text),
        )));
        display_lines.push(Line::from(""));
    }

    // ── Provider Versions ──
    if let Some(ref pv) = report.provider_versions {
        display_lines.push(Line::from(Span::styled(
            format!("  Provider Versions: {}", pv.versions.join(", ")),
            Style::default().fg(theme.text),
        )));
        for w in &pv.warnings {
            display_lines.push(Line::from(Span::styled(
                format!("  Warning: {}", w),
                Style::default().fg(Color::Yellow),
            )));
        }
        display_lines.push(Line::from(""));
    }

    // ── Render with scroll ──
    let total_lines = display_lines.len();
    let max_lines = area.height.saturating_sub(2) as usize;
    let scroll = state
        .stats_overlay_scroll
        .min(total_lines.saturating_sub(max_lines));
    let visible: Vec<Line> = display_lines
        .into_iter()
        .skip(scroll)
        .take(max_lines)
        .collect();

    let paragraph = Paragraph::new(visible).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.border))
            .title(Span::styled(
                " Stats Report ",
                Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(paragraph, area);
}

fn render_stats_overlay_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut spans = vec![
        Span::styled(
            " s ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.info)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" back  "),
        Span::styled(
            " Esc ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" back  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit"),
    ];

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available", version),
            Style::default()
                .fg(state.tui_theme.success)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn fmt_overlay_tokens(n: u64) -> String {
    if n >= 1_000_000 {
        format!("{:.1}M", n as f64 / 1_000_000.0)
    } else if n >= 1_000 {
        format!("{:.0}K", n as f64 / 1_000.0)
    } else {
        format!("{}", n)
    }
}

// ─── Settings Overlay ────────────────────────────────────────

/// Compute the settings overlay modal rect: 90% width x 80% height, centered,
/// clamped to a minimum of 80x24. Falls back to full-screen if the terminal is
/// smaller than 80x24.
pub fn settings_modal_rect(area: Rect) -> Rect {
    if area.width < 80 || area.height < 24 {
        return area;
    }
    let w = (area.width as u32 * 90 / 100).max(80) as u16;
    let h = (area.height as u32 * 80 / 100).max(24) as u16;
    let w = w.min(area.width);
    let h = h.min(area.height);
    let x = area.x + (area.width.saturating_sub(w)) / 2;
    let y = area.y + (area.height.saturating_sub(h)) / 2;
    Rect { x, y, width: w, height: h }
}

/// The `[ X ]` close button rect, derived from the modal rect.
/// Positioned at the top-right of the modal border.
pub fn close_btn_rect(modal: Rect) -> Rect {
    Rect {
        x: modal.x + modal.width.saturating_sub(6),
        y: modal.y,
        width: 5,
        height: 1,
    }
}

pub fn settings_overlay_row_hit_test(
    modal: Rect,
    scroll_offset: usize,
    column: u16,
    row: u16,
) -> Option<usize> {
    let inner = Rect {
        x: modal.x + 1,
        y: modal.y + 1,
        width: modal.width.saturating_sub(2),
        height: modal.height.saturating_sub(2),
    };
    let content_height = inner.height.saturating_sub(2);
    let content_bottom = inner.y.saturating_add(content_height);
    if column < inner.x
        || column >= inner.x.saturating_add(inner.width)
        || row < inner.y
        || row >= content_bottom
    {
        return None;
    }
    Some(scroll_offset + (row - inner.y) as usize)
}

pub fn model_picker_rect(parent: Rect, picker: &crate::app::ModelPicker) -> Rect {
    let item_count = picker.visible_items().len() as u16;
    let width = (parent.width * 60 / 100)
        .max(40)
        .min(parent.width.saturating_sub(4));
    let height = (item_count + 4)
        .min(parent.height.saturating_sub(4))
        .max(6);
    let x = parent.x + (parent.width.saturating_sub(width)) / 2;
    let y = parent.y + (parent.height.saturating_sub(height)) / 2;
    Rect {
        x,
        y,
        width,
        height,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModelPickerMouseTarget {
    FilterBar,
    Item(usize),
}

pub fn model_picker_hit_test(
    parent: Rect,
    picker: &crate::app::ModelPicker,
    column: u16,
    row: u16,
) -> Option<ModelPickerMouseTarget> {
    let popup = model_picker_rect(parent, picker);
    if column < popup.x
        || column >= popup.x.saturating_add(popup.width)
        || row < popup.y
        || row >= popup.y.saturating_add(popup.height)
    {
        return None;
    }

    let inner = Rect {
        x: popup.x + 1,
        y: popup.y + 1,
        width: popup.width.saturating_sub(2),
        height: popup.height.saturating_sub(2),
    };

    let filter_visible = picker.filtering || !picker.filter.is_empty();
    let mut content_y = inner.y;
    if filter_visible {
        if row == content_y
            && column >= inner.x
            && column < inner.x.saturating_add(inner.width)
        {
            return Some(ModelPickerMouseTarget::FilterBar);
        }
        content_y += 1;
    }

    let content_height = inner
        .height
        .saturating_sub(if filter_visible { 1 } else { 0 });
    let content_bottom = content_y.saturating_add(content_height);
    if row < content_y || row >= content_bottom {
        return None;
    }

    let scroll_offset = if picker.focus as u16 >= content_height {
        (picker.focus as u16 - content_height + 1) as usize
    } else {
        0
    };
    let idx = scroll_offset + (row - content_y) as usize;
    (idx < picker.visible_items().len()).then_some(ModelPickerMouseTarget::Item(idx))
}

fn stage_ids_match(lhs: &str, rhs: &str) -> bool {
    lhs == rhs
        || matches!(
            (lhs, rhs),
            ("build", "implement")
                | ("implement", "build")
                | ("audit", "doubt")
                | ("doubt", "audit")
                | ("discovery", "discover")
                | ("discover", "discovery")
                | ("pattern_extraction", "patterns")
                | ("patterns", "pattern_extraction")
        )
}

/// Render a floating settings overlay on top of whatever is already drawn.
pub(super) fn render_settings_overlay(frame: &mut Frame, state: &AppState) {
    use crate::app::{DualSelection, FieldKind, settings_sections};

    let theme = &state.tui_theme;
    let modal = settings_modal_rect(frame.area());

    // Shadow: 1 col right + 1 row down
    let shadow = Rect {
        x: modal.x + 1,
        y: modal.y + 1,
        width: modal.width.min(frame.area().width.saturating_sub(modal.x + 1)),
        height: modal.height.min(frame.area().height.saturating_sub(modal.y + 1)),
    };
    frame.render_widget(Clear, shadow);
    frame.render_widget(
        Paragraph::new("").style(Style::default().bg(Color::DarkGray)),
        shadow,
    );

    frame.render_widget(Clear, modal);
    frame.render_widget(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.accent))
            .style(Style::default().bg(theme.surface))
            .title(Span::styled(
                " Settings -- Foundry ",
                Style::default().fg(theme.accent).add_modifier(Modifier::BOLD),
            )),
        modal,
    );

    // Draw [ X ] close button
    let btn = close_btn_rect(modal);
    let buf = frame.buffer_mut();
    let btn_style = Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD);
    for (i, ch) in "[ X ]".chars().enumerate() {
        let col = btn.x + i as u16;
        if col < buf.area().width && btn.y < buf.area().height {
            buf[(col, btn.y)].set_char(ch).set_style(btn_style);
        }
    }

    let inner = Rect {
        x: modal.x + 1,
        y: modal.y + 1,
        width: modal.width.saturating_sub(2),
        height: modal.height.saturating_sub(2),
    };

    let highlight_bg = if theme.surface == Color::Reset { Color::DarkGray } else { theme.surface };

    let ov = state.settings_overlay.as_ref();
    let focus = ov.map(|o| o.focus).unwrap_or(0);
    let expanded = ov.map(|o| &o.expanded_sections);
    let scroll_offset = ov.map(|o| o.scroll_offset).unwrap_or(0);
    let editing = ov.and_then(|o| o.editing.as_ref());

    // Build the config snapshot for field values
    let config_path = state.buildloop_dir.parent().unwrap_or(std::path::Path::new(".")).join(".foundry.json");
    let config: Config = if let Ok(content) = std::fs::read_to_string(&config_path) {
        serde_json::from_str(&content).unwrap_or_default()
    } else {
        Config::default()
    };

    let sections = settings_sections();
    let content_height = inner.height.saturating_sub(2) as usize; // reserve 2 rows for hint bar
    let mut row_idx: usize = 0;
    let mut render_y: u16 = inner.y;

    for section in &sections {
        let is_expanded = expanded.map(|e| e.contains(section.id)).unwrap_or(section.default_expanded);
        let icon = if is_expanded { "\u{25BC}" } else { "\u{25B6}" };
        let focused = row_idx == focus;

        if row_idx >= scroll_offset && (row_idx - scroll_offset) < content_height {
            let style = if focused {
                Style::default().fg(theme.accent).add_modifier(Modifier::BOLD).bg(highlight_bg)
            } else {
                Style::default().fg(theme.accent).add_modifier(Modifier::BOLD)
            };
            let line = Line::from(Span::styled(
                format!(" {} {}", icon, section.name),
                style,
            ));
            frame.render_widget(Paragraph::new(line), Rect {
                x: inner.x,
                y: render_y,
                width: inner.width,
                height: 1,
            });
            render_y += 1;
        }
        row_idx += 1;

        if is_expanded {
            for field in &section.fields {
                if row_idx >= scroll_offset && (row_idx - scroll_offset) < content_height {
                    let field_focused = row_idx == focus;

                    // Get the current value
                    let value = match field.id {
                        "arena" => DualSelection::display_label(&state.builder_model_specs),
                        "builder" => {
                            let specs = &state.builder_model_specs;
                            let mut list: Vec<String> = specs.iter()
                                .map(|s| Config::readable_spec(s))
                                .collect();
                            if specs.len() >= 2 {
                                let combined = list.iter().take(specs.len()).cloned().collect::<Vec<_>>().join("/");
                                list.push(combined);
                            }
                            for m in &state.local_models {
                                if !list.contains(m) { list.push(m.clone()); }
                            }
                            list.get(state.builder_cursor).cloned().unwrap_or_else(|| "(default)".into())
                        }
                        "theme" => crate::tui::theme::current_name(&state.tui_theme).to_string(),
                        _ if editing
                            .is_some_and(|inline| inline.field_id == field.id) =>
                        {
                            editing.unwrap().buffer.clone()
                        }
                        _ => config.field_value(field.id),
                    };

                    let icon_str = match field.kind {
                        FieldKind::Bool => if value == "true" { "\u{2611}" } else { "\u{2610}" },
                        _ => " ",
                    };

                    let row_style = if field_focused {
                        Style::default().bg(highlight_bg)
                    } else {
                        Style::default()
                    };

                    let label_width = 28usize;
                    let value_width = 24usize;
                    let raw_display = if editing.is_some_and(|inline| inline.field_id == field.id) {
                        format!("{value}_")
                    } else {
                        value.clone()
                    };
                    let display_val = if raw_display.len() > value_width {
                        format!("{}...", &raw_display[..value_width - 3])
                    } else {
                        raw_display
                    };

                    let cursor_str = if field_focused { "> " } else { "  " };
                    let line = Line::from(vec![
                        Span::styled(cursor_str, if field_focused {
                            Style::default().fg(theme.accent).add_modifier(Modifier::BOLD)
                        } else {
                            Style::default().fg(theme.muted)
                        }),
                        Span::styled(format!("{} ", icon_str), Style::default().fg(theme.muted)),
                        Span::styled(format!("{:<width$}", field.label, width = label_width), row_style),
                        Span::styled(format!("{:<width$}", display_val, width = value_width), row_style.fg(Color::White)),
                        Span::styled(
                            truncate_str(field.hint, inner.width.saturating_sub(label_width as u16 + value_width as u16 + 6) as usize),
                            Style::default().fg(theme.muted),
                        ),
                    ]);
                    frame.render_widget(Paragraph::new(line), Rect {
                        x: inner.x,
                        y: render_y,
                        width: inner.width,
                        height: 1,
                    });
                    render_y += 1;
                }
                row_idx += 1;
            }
        }
    }

    let status_y = inner.y + inner.height.saturating_sub(2);
    let hint_y = inner.y + inner.height.saturating_sub(1);
    let has_picker = ov.is_some_and(|o| o.picker.is_some());
    let status_text = if let Some(editing) = editing {
        editing
            .error
            .as_deref()
            .map(str::to_string)
            .unwrap_or_else(|| format!("  editing {} -- Enter save, Ctrl+U clear", editing.field_id))
    } else if has_picker {
        "  Click a row to select or toggle a provider group".to_string()
    } else {
        "  Click a row to toggle, edit, or open the model picker".to_string()
    };
    frame.render_widget(
        Paragraph::new(Line::from(Span::styled(
            status_text,
            if editing.and_then(|inline| inline.error.as_ref()).is_some() {
                Style::default().fg(Color::Yellow)
            } else {
                Style::default().fg(theme.muted)
            },
        ))),
        Rect {
            x: inner.x,
            y: status_y,
            width: inner.width,
            height: 1,
        },
    );

    let hint_text = if has_picker {
        "  \u{2191}\u{2193} move  Enter select  / filter  Esc close picker"
    } else if editing.is_some() {
        "  Type to edit  Enter save  Backspace delete  Esc close"
    } else {
        "  \u{2191}\u{2193} move  Enter/Space toggle  \u{2190}\u{2192} cycle  Esc close"
    };
    frame.render_widget(
        Paragraph::new(Line::from(Span::styled(
            hint_text,
            Style::default().fg(theme.muted),
        ))),
        Rect { x: inner.x, y: hint_y, width: inner.width, height: 1 },
    );

    // Model picker popup (rendered on top of the settings overlay)
    if let Some(ov_state) = ov {
        if let Some(ref picker) = ov_state.picker {
            let stage_overridden = config
                .stage_overrides
                .iter()
                .any(|stage_id| stage_ids_match(stage_id, &picker.stage));
            let selected_route = stage_overridden
                .then(|| config.active_routing_for_stage(&picker.stage));
            render_model_picker(frame, theme, picker, modal, selected_route);
        }
    }

    // Confirm-close banner on top of everything
    if state
        .settings_overlay
        .as_ref()
        .is_some_and(|ov| ov.confirm_close)
    {
        render_confirm_banner(
            frame,
            modal,
            theme,
            "Save changes?",
            &["[y] save", "[n] discard", "[Esc] back"],
        );
    }
}

fn render_model_picker(
    frame: &mut Frame,
    theme: &crate::tui::theme::TuiTheme,
    picker: &crate::app::ModelPicker,
    parent: Rect,
    selected_route: Option<(String, String)>,
) {
    use crate::app::PickerItem;

    let items = picker.visible_items();
    let popup = model_picker_rect(parent, picker);

    frame.render_widget(Clear, popup);
    let title = format!(" Model for {} ", picker.stage);
    frame.render_widget(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.accent))
            .title(Span::styled(title, Style::default().fg(theme.accent).add_modifier(Modifier::BOLD))),
        popup,
    );

    let inner = Rect {
        x: popup.x + 1,
        y: popup.y + 1,
        width: popup.width.saturating_sub(2),
        height: popup.height.saturating_sub(2),
    };

    // Filter bar
    let mut content_y = inner.y;
    if !picker.filter.is_empty() || picker.filtering {
        let filter_line = Line::from(vec![
            Span::styled("/ ", Style::default().fg(theme.accent)),
            Span::styled(&picker.filter, Style::default().fg(Color::White)),
            if picker.filtering {
                Span::styled("_", Style::default().fg(Color::White).add_modifier(Modifier::SLOW_BLINK))
            } else {
                Span::raw("")
            },
        ]);
        frame.render_widget(
            Paragraph::new(filter_line),
            Rect { x: inner.x, y: content_y, width: inner.width, height: 1 },
        );
        content_y += 1;
    }

    let content_height = inner.height.saturating_sub(if picker.filtering || !picker.filter.is_empty() { 1 } else { 0 });
    let scroll_offset = if picker.focus as u16 >= content_height {
        (picker.focus as u16 - content_height + 1) as usize
    } else {
        0
    };

    let highlight_bg = if theme.surface == Color::Reset { Color::DarkGray } else { theme.surface };

    for (idx, item) in items.iter().enumerate() {
        if idx < scroll_offset { continue; }
        let row_y = content_y + (idx - scroll_offset) as u16;
        if row_y >= inner.y + inner.height { break; }

        let focused = idx == picker.focus;
        match item {
            PickerItem::GroupHeader(name, is_open) => {
                let icon = if *is_open { "\u{25BC}" } else { "\u{25B6}" };
                let style = if focused {
                    Style::default().fg(theme.accent).add_modifier(Modifier::BOLD).bg(highlight_bg)
                } else {
                    Style::default().fg(theme.accent).add_modifier(Modifier::BOLD)
                };
                let line = Line::from(Span::styled(format!(" {} {}", icon, name), style));
                frame.render_widget(
                    Paragraph::new(line),
                    Rect { x: inner.x, y: row_y, width: inner.width, height: 1 },
                );
            }
            PickerItem::Entry(entry) => {
                let is_selected = match selected_route.as_ref() {
                    Some((provider, model)) => {
                        provider == &entry.provider && model == &entry.model
                    }
                    None => entry.provider.is_empty() && entry.model.is_empty(),
                };
                let radio = if is_selected { "\u{25C9}" } else { "\u{25CB}" };
                let rec_hint = if entry.recommended { " (recommended)" } else { "" };
                let row_style = if focused {
                    Style::default().bg(highlight_bg)
                } else {
                    Style::default()
                };
                let line = Line::from(vec![
                    Span::styled(
                        if focused { "> " } else { "  " },
                        if focused { Style::default().fg(theme.accent) } else { Style::default().fg(theme.muted) },
                    ),
                    Span::styled(format!("  {} ", radio), Style::default().fg(theme.muted)),
                    Span::styled(&entry.label, row_style.fg(Color::White)),
                    Span::styled(rec_hint, Style::default().fg(theme.muted)),
                ]);
                frame.render_widget(
                    Paragraph::new(line),
                    Rect { x: inner.x, y: row_y, width: inner.width, height: 1 },
                );
            }
        }
    }
}

fn render_confirm_banner(
    frame: &mut Frame,
    parent: Rect,
    theme: &crate::tui::theme::TuiTheme,
    title: &str,
    actions: &[&str],
) {
    let text = format!("  {}  {}  ", title, actions.join("  "));
    let w = text.len() as u16 + 2;
    let h: u16 = 3;
    let x = parent.x + parent.width.saturating_sub(w) / 2;
    let y = parent.y + parent.height.saturating_sub(h) / 2;
    let area = Rect { x, y, width: w.min(parent.width), height: h };

    frame.render_widget(Clear, area);
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.accent))
        .style(Style::default().bg(theme.surface));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let mut spans = vec![
        Span::styled(
            format!("  {}  ", title),
            Style::default().fg(theme.accent).add_modifier(Modifier::BOLD),
        ),
    ];
    for action in actions {
        spans.push(Span::styled(
            format!(" {} ", action),
            Style::default().fg(theme.text),
        ));
    }
    frame.render_widget(Paragraph::new(Line::from(spans)), inner);
}

pub fn render_quit_confirm(frame: &mut Frame, theme: &crate::tui::theme::TuiTheme) {
    let area = frame.area();
    let w: u16 = 54.min(area.width.saturating_sub(2));
    let h: u16 = 9.min(area.height.saturating_sub(2));
    if w < 20 || h < 5 {
        // Terminal too small for the full modal -- fall back to a single line.
        let text = "  Quit foundry?  [y] quit  [n] cancel  ";
        let fw = (text.len() as u16 + 2).min(area.width);
        let fx = area.width.saturating_sub(fw) / 2;
        let fy = area.height.saturating_sub(3) / 2;
        let banner = Rect { x: fx, y: fy, width: fw, height: 3 };
        frame.render_widget(Clear, banner);
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.accent))
            .style(Style::default().bg(theme.surface));
        let inner = block.inner(banner);
        frame.render_widget(block, banner);
        frame.render_widget(
            Paragraph::new(Line::from(text)).style(Style::default().fg(theme.text)),
            inner,
        );
        return;
    }

    let x = area.width.saturating_sub(w) / 2;
    let y = area.height.saturating_sub(h) / 2;
    let modal = Rect { x, y, width: w, height: h };

    // Drop shadow: offset right 2, down 1, painted in the muted color so the
    // modal looks lifted off the surface behind it.
    let sx = modal.x.saturating_add(2);
    let sy = modal.y.saturating_add(1);
    let sw = modal.width.min(area.width.saturating_sub(sx));
    let sh = modal.height.min(area.height.saturating_sub(sy));
    if sw > 0 && sh > 0 {
        let shadow = Rect { x: sx, y: sy, width: sw, height: sh };
        frame.render_widget(Clear, shadow);
        frame.render_widget(
            Block::default().style(Style::default().bg(theme.muted)),
            shadow,
        );
    }

    // Main modal -- double border in accent, surface fill.
    frame.render_widget(Clear, modal);
    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Double)
        .border_style(
            Style::default()
                .fg(theme.accent)
                .add_modifier(Modifier::BOLD),
        )
        .style(Style::default().bg(theme.surface).fg(theme.text));
    let inner = block.inner(modal);
    frame.render_widget(block, modal);

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // title
            Constraint::Length(1), // spacer
            Constraint::Length(1), // message
            Constraint::Length(1), // spacer
            Constraint::Length(1), // buttons
            Constraint::Min(0),
        ])
        .split(inner);

    let title = Paragraph::new(Line::from(Span::styled(
        "Quit foundry?",
        Style::default()
            .fg(theme.accent)
            .add_modifier(Modifier::BOLD),
    )))
    .alignment(Alignment::Center);
    frame.render_widget(title, chunks[0]);

    let msg = Paragraph::new(Line::from(Span::styled(
        "Any in-flight work will be left as-is.",
        Style::default().fg(theme.muted),
    )))
    .alignment(Alignment::Center);
    frame.render_widget(msg, chunks[2]);

    let quit_btn = Span::styled(
        "  [Y] Quit  ",
        Style::default()
            .bg(theme.error)
            .fg(theme.text)
            .add_modifier(Modifier::BOLD),
    );
    let cancel_btn = Span::styled(
        "  [N] Cancel  ",
        Style::default()
            .bg(theme.border)
            .fg(theme.text)
            .add_modifier(Modifier::BOLD),
    );
    let buttons = Paragraph::new(Line::from(vec![
        quit_btn,
        Span::raw("    "),
        cancel_btn,
    ]))
    .alignment(Alignment::Center);
    frame.render_widget(buttons, chunks[4]);
}

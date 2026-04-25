use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, Paragraph},
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

/// Compute a fixed-size Rect centered within `area`.
fn centered_rect(width: u16, height: u16, area: Rect) -> Rect {
    let x = area.x + area.width.saturating_sub(width) / 2;
    let y = area.y + area.height.saturating_sub(height) / 2;
    Rect {
        x,
        y,
        width: width.min(area.width),
        height: height.min(area.height),
    }
}

/// Render a floating settings overlay on top of whatever is already drawn.
pub(super) fn render_settings_overlay(frame: &mut Frame, state: &AppState) {
    let theme = &state.tui_theme;
    let modal = centered_rect(50, 14, frame.area());

    // Shadow: 1 col right + 1 row down
    let shadow = Rect {
        x: modal.x + 1,
        y: modal.y + 1,
        width: modal.width.min(
            frame
                .area()
                .width
                .saturating_sub(modal.x + 1),
        ),
        height: modal.height.min(
            frame
                .area()
                .height
                .saturating_sub(modal.y + 1),
        ),
    };
    frame.render_widget(Clear, shadow);
    frame.render_widget(
        Paragraph::new("").style(Style::default().bg(Color::DarkGray)),
        shadow,
    );

    // Clear modal area and draw border
    frame.render_widget(Clear, modal);
    frame.render_widget(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.accent))
            .title(Span::styled(
                " Settings ",
                Style::default()
                    .fg(theme.accent)
                    .add_modifier(Modifier::BOLD),
            )),
        modal,
    );

    // Inner content area (inside the border)
    let inner = Rect {
        x: modal.x + 1,
        y: modal.y + 1,
        width: modal.width.saturating_sub(2),
        height: modal.height.saturating_sub(2),
    };

    // Helper: highlight style for focused row
    let highlight_bg = if theme.surface == Color::Reset {
        Color::DarkGray
    } else {
        theme.surface
    };

    let run_mode_val = &state.run_mode;
    let theme_val = crate::tui::theme::current_name(&state.tui_theme);
    let sandbox_val = &state.sandbox_status_label;

    // Unified builder list (mirrors build_unified_builders in app.rs)
    let unified_builders = {
        let specs = &state.builder_model_specs;
        let mut list: Vec<String> = specs.iter()
            .map(|s| Config::readable_spec(s))
            .collect();
        if specs.len() >= 2 {
            let combined = list.iter()
                .take(specs.len())
                .cloned()
                .collect::<Vec<_>>()
                .join("/");
            list.push(combined);
        }
        for m in &state.local_models {
            if !list.contains(m) {
                list.push(m.clone());
            }
        }
        list
    };
    let builder_val: &str = unified_builders
        .get(state.builder_cursor)
        .map(|s| s.as_str())
        .unwrap_or("(default)");

    // Rows indexed within inner area
    // 0: spacer
    // 1: run_mode (cursor 0)
    // 2: spacer
    // 3: builder (cursor 1)
    // 4: spacer
    // 5: theme (cursor 2)
    // 6: spacer
    // 7: sandbox read-only
    // 8: spacer
    // 9: horizontal rule
    // 10: spacer
    // 11: hint bar

    let rows: &[(usize, bool, &str, &str)] = &[
        (1, true, "Run Mode", run_mode_val),
        (3, true, "Builder",  builder_val),
        (5, true, "Theme",    theme_val),
    ];

    for (row_y, interactive, label, val) in rows {
        let cursor_idx = match *label {
            "Run Mode" => 0,
            "Builder"  => 1,
            _          => 2,
        };
        let focused = *interactive && state.settings_overlay_cursor == cursor_idx;
        let cursor_str = if focused { "> " } else { "  " };
        let cursor_style = if focused {
            Style::default()
                .fg(theme.accent)
                .add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(theme.muted)
        };
        let row_bg = if focused {
            Style::default().bg(highlight_bg)
        } else {
            Style::default()
        };
        // pad label to 15 chars
        let label_padded = format!("{:<15}", label);
        let line = Line::from(vec![
            Span::styled(cursor_str.to_string(), cursor_style),
            Span::styled(
                format!("{}  {}", label_padded, val),
                row_bg,
            ),
        ]);
        frame.render_widget(
            Paragraph::new(line),
            Rect {
                x: inner.x,
                y: inner.y + *row_y as u16,
                width: inner.width,
                height: 1,
            },
        );
    }

    // Sandbox row (read-only, no cursor, row 7)
    let sandbox_line = Line::from(vec![
        Span::styled("  ", Style::default()),
        Span::styled(
            format!("{:<15}  {} (read-only)", "Sandbox", sandbox_val),
            Style::default().fg(theme.muted),
        ),
    ]);
    frame.render_widget(
        Paragraph::new(sandbox_line),
        Rect {
            x: inner.x,
            y: inner.y + 7,
            width: inner.width,
            height: 1,
        },
    );

    // Horizontal rule (row 9)
    let rule = "-".repeat(inner.width.saturating_sub(2) as usize);
    frame.render_widget(
        Paragraph::new(Line::from(Span::styled(
            rule,
            Style::default().fg(theme.muted),
        ))),
        Rect {
            x: inner.x + 1,
            y: inner.y + 9,
            width: inner.width.saturating_sub(2),
            height: 1,
        },
    );

    // Hint bar (row 11)
    frame.render_widget(
        Paragraph::new(Line::from(Span::styled(
            "  \u{2191}\u{2193} move   \u{2190}\u{2192}/Enter cycle   Esc close",
            Style::default().fg(theme.muted),
        ))),
        Rect {
            x: inner.x,
            y: inner.y + 11,
            width: inner.width,
            height: 1,
        },
    );
}

use ratatui::{
    layout::{Alignment, Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, Paragraph},
    Frame,
};

use crate::app::AppState;
use crate::app::StageSummaryOverlay;
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

fn render_patterns_list(frame: &mut Frame, area: Rect, state: &AppState, _config: &Config) {
    let theme = &state.tui_theme;
    let summary_opt = state.skill_citation_summary.as_ref();

    let max_lines = area.height.saturating_sub(2) as usize;
    let inner_width = area.width.saturating_sub(4) as usize;
    let mut display_lines: Vec<Line> = Vec::new();

    let (title, db_path_str): (String, String) = match summary_opt {
        Some(s) if s.db_available => (
            format!(" Skill Citations ({} skills) ", s.all_skills.len()),
            s.db_path.display().to_string(),
        ),
        Some(s) => (
            " Skill Citations (telemetry unavailable) ".to_string(),
            s.db_path.display().to_string(),
        ),
        None => (
            " Skill Citations (loading...) ".to_string(),
            String::new(),
        ),
    };

    match summary_opt {
        None => {
            display_lines.push(Line::from(""));
            display_lines.push(Line::from(Span::styled(
                "  Loading skill citations...",
                Style::default().fg(theme.muted),
            )));
        }
        Some(summary) if !summary.db_available => {
            display_lines.push(Line::from(""));
            display_lines.push(Line::from(Span::styled(
                "  Telemetry DB unavailable.",
                Style::default().fg(theme.muted),
            )));
            display_lines.push(Line::from(Span::styled(
                format!("  Expected at: {}", summary.db_path.display()),
                Style::default().fg(theme.muted),
            )));
            display_lines.push(Line::from(""));
            display_lines.push(Line::from(Span::styled(
                "  Citations will appear here once the build loop records them.",
                Style::default().fg(theme.muted),
            )));
        }
        Some(summary) if summary.all_skills.is_empty() => {
            display_lines.push(Line::from(""));
            display_lines.push(Line::from(Span::styled(
                "  No skill citations recorded yet.",
                Style::default().fg(theme.muted),
            )));
            display_lines.push(Line::from(""));
            display_lines.push(Line::from(Span::styled(
                "  Run a task -- citations are recorded after each commit.",
                Style::default().fg(theme.muted),
            )));
        }
        Some(summary) => {
            display_lines.push(Line::from(Span::styled(
                format!(
                    "  {:<40} {:>5} {:>5} {:>10} {:>10}",
                    "skill", "pass", "wip", "stage", "last_used"
                ),
                Style::default().fg(theme.muted),
            )));
            for rec in &summary.all_skills {
                let stage = derive_stage_label(&rec.skill_name, &rec.cited_by_stage);
                let last_used_str = rec.last_used.clone().unwrap_or_else(|| "-".to_string());
                let name_w = inner_width.saturating_sub(38).max(20);
                let name_disp = truncate_str(&rec.skill_name, name_w);
                display_lines.push(Line::from(vec![
                    Span::styled(
                        format!("  {:<40} ", name_disp),
                        Style::default().fg(theme.text),
                    ),
                    Span::styled(
                        format!("{:>5} ", rec.citations_pass),
                        Style::default().fg(Color::Green),
                    ),
                    Span::styled(
                        format!("{:>5} ", rec.citations_wip),
                        Style::default().fg(Color::Yellow),
                    ),
                    Span::styled(
                        format!("{:>10} ", stage),
                        Style::default().fg(theme.info),
                    ),
                    Span::styled(
                        format!("{:>10}", last_used_str),
                        Style::default().fg(theme.muted),
                    ),
                ]));
            }
        }
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

    let full_title = if db_path_str.is_empty() {
        title
    } else {
        format!("{}| {} ", title, db_path_str)
    };

    let paragraph = Paragraph::new(visible).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.border))
            .title(Span::styled(
                full_title,
                Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(paragraph, area);
}

fn derive_stage_label(
    skill_name: &str,
    by_stage: &std::collections::HashMap<String, u64>,
) -> String {
    if skill_name.ends_with("-planner") {
        return "planner".to_string();
    }
    if skill_name.ends_with("-reviewer") {
        return "reviewer".to_string();
    }
    let mut best: Option<(&str, u64)> = None;
    for (stage, count) in by_stage {
        let pair: (&str, u64) = (stage.as_str(), *count);
        match best {
            None => best = Some(pair),
            Some((_, b)) if pair.1 > b => best = Some(pair),
            _ => {}
        }
    }
    best.map(|(s, _)| s.to_string()).unwrap_or_else(|| "-".to_string())
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
    Rect {
        x,
        y,
        width: w,
        height: h,
    }
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
    let height = (item_count + 4).min(parent.height.saturating_sub(4)).max(6);
    let x = parent.x + (parent.width.saturating_sub(width)) / 2;
    let y = parent.y + (parent.height.saturating_sub(height)) / 2;
    Rect {
        x,
        y,
        width,
        height,
    }
}

pub fn picker_close_btn_rect(popup: Rect) -> Rect {
    Rect {
        x: popup.x + popup.width.saturating_sub(6),
        y: popup.y,
        width: 5,
        height: 1,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModelPickerMouseTarget {
    /// User clicked the [X] button in the picker header.
    CloseBtn,
    /// User clicked outside the popup. Both this and CloseBtn should dismiss
    /// the picker; kept distinct so callers/tests can tell them apart.
    OutsideClick,
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

    let btn = picker_close_btn_rect(popup);
    if column >= btn.x && column < btn.x.saturating_add(btn.width) && row == btn.y {
        return Some(ModelPickerMouseTarget::CloseBtn);
    }

    if column < popup.x
        || column >= popup.x.saturating_add(popup.width)
        || row < popup.y
        || row >= popup.y.saturating_add(popup.height)
    {
        return Some(ModelPickerMouseTarget::OutsideClick);
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
        if row == content_y && column >= inner.x && column < inner.x.saturating_add(inner.width) {
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
    use crate::app::{settings_sections, Action, FieldKind, OverlayRow, SectionKind};

    let theme = &state.tui_theme;
    let modal = settings_modal_rect(frame.area());

    // Shadow: 1 col right + 1 row down
    let shadow = Rect {
        x: modal.x + 1,
        y: modal.y + 1,
        width: modal
            .width
            .min(frame.area().width.saturating_sub(modal.x + 1)),
        height: modal
            .height
            .min(frame.area().height.saturating_sub(modal.y + 1)),
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
                Style::default()
                    .fg(theme.accent)
                    .add_modifier(Modifier::BOLD),
            )),
        modal,
    );

    // Draw [ X ] close button
    let btn = close_btn_rect(modal);
    let buf = frame.buffer_mut();
    let btn_style = Style::default()
        .fg(Color::Yellow)
        .add_modifier(Modifier::BOLD);
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

    let highlight_bg = if theme.surface == Color::Reset {
        Color::DarkGray
    } else {
        theme.surface
    };

    let ov = state.settings_overlay.as_ref();
    let focus = ov.map(|o| o.focus).unwrap_or(0);
    let expanded = ov.map(|o| &o.expanded_sections);
    let scroll_offset = ov.map(|o| o.scroll_offset).unwrap_or(0);
    let editing = ov.and_then(|o| o.editing.as_ref());

    // Build the config snapshot for field values
    let config_path = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."))
        .join(".foundry.json");
    let config: Config = if let Ok(content) = std::fs::read_to_string(&config_path) {
        serde_json::from_str(&content).unwrap_or_default()
    } else {
        Config::default()
    };

    let dual_mode = state
        .settings_overlay
        .as_ref()
        .is_some_and(|ov| ov.dual_mode);
    let sections = settings_sections(dual_mode);
    let content_height = inner.height.saturating_sub(2) as usize; // reserve 2 rows for hint bar
    let mut row_idx: usize = 0;
    let mut render_y: u16 = inner.y;

    for section in &sections {
        let is_expanded = expanded
            .map(|e| e.contains(section.id))
            .unwrap_or(section.default_expanded);
        let icon = if is_expanded { "\u{25BC}" } else { "\u{25B6}" };
        let focused = row_idx == focus;

        if row_idx >= scroll_offset && (row_idx - scroll_offset) < content_height {
            let style = if focused {
                Style::default()
                    .fg(theme.accent)
                    .add_modifier(Modifier::BOLD)
                    .bg(highlight_bg)
            } else {
                Style::default()
                    .fg(theme.accent)
                    .add_modifier(Modifier::BOLD)
            };
            let line = Line::from(Span::styled(format!(" {} {}", icon, section.name), style));
            frame.render_widget(
                Paragraph::new(line),
                Rect {
                    x: inner.x,
                    y: render_y,
                    width: inner.width,
                    height: 1,
                },
            );
            render_y += 1;
        }
        row_idx += 1;

        if is_expanded {
            match section.kind {
                SectionKind::PipelineHealth => {
                    let rows: Vec<OverlayRow> = state
                        .settings_overlay
                        .as_ref()
                        .map(|o| o.pipeline_health_rows())
                        .unwrap_or_default();
                    for row in &rows {
                        if row_idx >= scroll_offset && (row_idx - scroll_offset) < content_height {
                            let row_focused = row_idx == focus;
                            let row_style = if row_focused {
                                Style::default().bg(highlight_bg)
                            } else {
                                Style::default()
                            };
                            let line = match row {
                                OverlayRow::ReportLine(text) => Line::from(vec![
                                    Span::styled("  ", Style::default().fg(theme.muted)),
                                    Span::styled(
                                        truncate_str(text, inner.width.saturating_sub(2) as usize),
                                        row_style.fg(theme.text),
                                    ),
                                ]),
                                OverlayRow::ActionButton(action) => {
                                    let label = match action {
                                        Action::RerunEvalOnLastRun => {
                                            "[ Re-run eval on last run ]"
                                        }
                                        Action::ViewInjectedPatterns => {
                                            "[ View injected this session ]"
                                        }
                                        Action::ViewAllPatterns => "[ View all global ]",
                                    };
                                    let cursor_str = if row_focused { "> " } else { "  " };
                                    Line::from(vec![
                                        Span::styled(
                                            cursor_str,
                                            if row_focused {
                                                Style::default()
                                                    .fg(theme.accent)
                                                    .add_modifier(Modifier::BOLD)
                                            } else {
                                                Style::default().fg(theme.muted)
                                            },
                                        ),
                                        Span::styled(
                                            label,
                                            row_style
                                                .fg(theme.accent)
                                                .add_modifier(Modifier::BOLD),
                                        ),
                                    ])
                                }
                                OverlayRow::Field(_) => Line::from(""),
                            };
                            frame.render_widget(
                                Paragraph::new(line),
                                Rect {
                                    x: inner.x,
                                    y: render_y,
                                    width: inner.width,
                                    height: 1,
                                },
                            );
                            render_y += 1;
                        }
                        row_idx += 1;
                    }
                }
                SectionKind::Patterns => {
                    let rows: Vec<OverlayRow> = state
                        .settings_overlay
                        .as_ref()
                        .map(|o| o.patterns_rows())
                        .unwrap_or_default();
                    for row in &rows {
                        if row_idx >= scroll_offset && (row_idx - scroll_offset) < content_height {
                            let row_focused = row_idx == focus;
                            let row_style = if row_focused {
                                Style::default().bg(highlight_bg)
                            } else {
                                Style::default()
                            };
                            let line = match row {
                                OverlayRow::ReportLine(text) => Line::from(vec![
                                    Span::styled("  ", Style::default().fg(theme.muted)),
                                    Span::styled(
                                        truncate_str(text, inner.width.saturating_sub(2) as usize),
                                        row_style.fg(theme.text),
                                    ),
                                ]),
                                OverlayRow::ActionButton(action) => {
                                    let label = match action {
                                        Action::RerunEvalOnLastRun => {
                                            "[ Re-run eval on last run ]"
                                        }
                                        Action::ViewInjectedPatterns => {
                                            "[ View injected this session ]"
                                        }
                                        Action::ViewAllPatterns => "[ View all global ]",
                                    };
                                    let cursor_str = if row_focused { "> " } else { "  " };
                                    Line::from(vec![
                                        Span::styled(
                                            cursor_str,
                                            if row_focused {
                                                Style::default()
                                                    .fg(theme.accent)
                                                    .add_modifier(Modifier::BOLD)
                                            } else {
                                                Style::default().fg(theme.muted)
                                            },
                                        ),
                                        Span::styled(
                                            label,
                                            row_style
                                                .fg(theme.accent)
                                                .add_modifier(Modifier::BOLD),
                                        ),
                                    ])
                                }
                                OverlayRow::Field(_) => Line::from(""),
                            };
                            frame.render_widget(
                                Paragraph::new(line),
                                Rect {
                                    x: inner.x,
                                    y: render_y,
                                    width: inner.width,
                                    height: 1,
                                },
                            );
                            render_y += 1;
                        }
                        row_idx += 1;
                    }
                }
                SectionKind::Standard => {
            for field in &section.fields {
                if row_idx >= scroll_offset && (row_idx - scroll_offset) < content_height {
                    let field_focused = row_idx == focus;

                    // Get the current value
                    let value = match field.id {
                        "arena" => {
                            if state.arena_mode == "dual" { "Dual".to_string() } else { "Solo".to_string() }
                        }
                        "builder" => {
                            let specs = &state.builder_model_specs;
                            let mut list: Vec<String> =
                                specs.iter().map(|s| Config::readable_spec(s)).collect();
                            if specs.len() >= 2 {
                                let combined = list
                                    .iter()
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
                            list.get(state.builder_cursor)
                                .cloned()
                                .unwrap_or_else(|| "(default)".into())
                        }
                        "theme" => crate::tui::theme::current_name(&state.tui_theme).to_string(),
                        _ if editing.is_some_and(|inline| inline.field_id == field.id) => {
                            editing.unwrap().buffer.clone()
                        }
                        _ => config.field_value(field.id),
                    };

                    // `backpressure_only` is stored with inverted semantics
                    // relative to its UI label "Doubt in the Loop?": when the
                    // user sees ON they expect Doubt to run, but the stored
                    // value `true` means *skip* Doubt. Flip just the display
                    // (and the value text below) so OK/checked = "Doubt runs".
                    let display_inverted = field.id == "backpressure_only";
                    let displayed_truthy = if display_inverted {
                        value == "false"
                    } else {
                        value == "true"
                    };
                    let icon_str = match field.kind {
                        FieldKind::Bool => {
                            if displayed_truthy {
                                "\u{2611}"
                            } else {
                                "\u{2610}"
                            }
                        }
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
                    } else if display_inverted && field.kind == FieldKind::Bool {
                        // Display inverted bools as ON/OFF (clearer than "true"/"false"
                        // when the displayed semantics oppose the stored value).
                        if displayed_truthy { "ON".to_string() } else { "OFF".to_string() }
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
                        Span::styled(
                            cursor_str,
                            if field_focused {
                                Style::default()
                                    .fg(theme.accent)
                                    .add_modifier(Modifier::BOLD)
                            } else {
                                Style::default().fg(theme.muted)
                            },
                        ),
                        Span::styled(format!("{} ", icon_str), Style::default().fg(theme.muted)),
                        Span::styled(
                            format!("{:<width$}", field.label, width = label_width),
                            row_style,
                        ),
                        Span::styled(
                            format!("{:<width$}", display_val, width = value_width),
                            row_style.fg(Color::White),
                        ),
                        Span::styled(
                            truncate_str(
                                field.hint,
                                inner
                                    .width
                                    .saturating_sub(label_width as u16 + value_width as u16 + 6)
                                    as usize,
                            ),
                            Style::default().fg(theme.muted),
                        ),
                    ]);
                    frame.render_widget(
                        Paragraph::new(line),
                        Rect {
                            x: inner.x,
                            y: render_y,
                            width: inner.width,
                            height: 1,
                        },
                    );
                    render_y += 1;
                }
                row_idx += 1;
            }
                }
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
            .unwrap_or_else(|| {
                format!("  editing {} -- Enter save, Ctrl+U clear", editing.field_id)
            })
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
        Rect {
            x: inner.x,
            y: hint_y,
            width: inner.width,
            height: 1,
        },
    );

    // Model picker popup (rendered on top of the settings overlay)
    if let Some(ov_state) = ov {
        if let Some(ref picker) = ov_state.picker {
            let selected_route = if picker.pipeline_b {
                let (p, m) = config.active_routing_for_stage_b(&picker.stage);
                if p.is_empty() && m.is_empty() { None } else { Some((p, m)) }
            } else {
                let stage_overridden = config
                    .stage_overrides
                    .iter()
                    .any(|stage_id| stage_ids_match(stage_id, &picker.stage));
                stage_overridden.then(|| config.active_routing_for_stage(&picker.stage))
            };
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
    let catalog = crate::model_catalog::load_catalog();
    let (stale_label, stale_warn) = crate::model_catalog::staleness_label(
        chrono::Utc::now(),
        catalog.source_fetched_at,
    );
    let base = if picker.pipeline_b {
        format!(" Model for {} (B) ", picker.stage)
    } else {
        format!(" Model for {} ", picker.stage)
    };
    let title = format!("{} {} ", base.trim_end(), stale_label);
    let title_color = if stale_warn { Color::Yellow } else { theme.accent };
    // "Refresh now" button deferred -- env var FOUNDRY_MODEL_REFRESH=force triggers a manual refresh.
    frame.render_widget(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(title_color))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(title_color)
                    .add_modifier(Modifier::BOLD),
            )),
        popup,
    );

    // Draw [ X ] close button
    let btn = picker_close_btn_rect(popup);
    let buf = frame.buffer_mut();
    let btn_style = Style::default()
        .fg(Color::Yellow)
        .add_modifier(Modifier::BOLD);
    for (i, ch) in "[ X ]".chars().enumerate() {
        let col = btn.x + i as u16;
        if col < buf.area().width && btn.y < buf.area().height {
            buf[(col, btn.y)].set_char(ch).set_style(btn_style);
        }
    }

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
                Span::styled(
                    "_",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::SLOW_BLINK),
                )
            } else {
                Span::raw("")
            },
        ]);
        frame.render_widget(
            Paragraph::new(filter_line),
            Rect {
                x: inner.x,
                y: content_y,
                width: inner.width,
                height: 1,
            },
        );
        content_y += 1;
    }

    let content_height =
        inner
            .height
            .saturating_sub(if picker.filtering || !picker.filter.is_empty() {
                1
            } else {
                0
            });
    let scroll_offset = if picker.focus as u16 >= content_height {
        (picker.focus as u16 - content_height + 1) as usize
    } else {
        0
    };

    let highlight_bg = if theme.surface == Color::Reset {
        Color::DarkGray
    } else {
        theme.surface
    };

    for (idx, item) in items.iter().enumerate() {
        if idx < scroll_offset {
            continue;
        }
        let row_y = content_y + (idx - scroll_offset) as u16;
        if row_y >= inner.y + inner.height {
            break;
        }

        let focused = idx == picker.focus;
        match item {
            PickerItem::GroupHeader(name, is_open) => {
                let icon = if *is_open { "\u{25BC}" } else { "\u{25B6}" };
                let style = if focused {
                    Style::default()
                        .fg(theme.accent)
                        .add_modifier(Modifier::BOLD)
                        .bg(highlight_bg)
                } else {
                    Style::default()
                        .fg(theme.accent)
                        .add_modifier(Modifier::BOLD)
                };
                let line = Line::from(Span::styled(format!(" {} {}", icon, name), style));
                frame.render_widget(
                    Paragraph::new(line),
                    Rect {
                        x: inner.x,
                        y: row_y,
                        width: inner.width,
                        height: 1,
                    },
                );
            }
            PickerItem::Entry(entry) => {
                let is_selected = match selected_route.as_ref() {
                    Some((provider, model)) => provider == &entry.provider && model == &entry.model,
                    None => entry.provider.is_empty() && entry.model.is_empty(),
                };
                let radio = if is_selected { "\u{25C9}" } else { "\u{25CB}" };
                let rec_hint = if entry.recommended {
                    " (recommended)"
                } else {
                    ""
                };
                let row_style = if focused {
                    Style::default().bg(highlight_bg)
                } else {
                    Style::default()
                };
                let line = Line::from(vec![
                    Span::styled(
                        if focused { "> " } else { "  " },
                        if focused {
                            Style::default().fg(theme.accent)
                        } else {
                            Style::default().fg(theme.muted)
                        },
                    ),
                    Span::styled(format!("  {} ", radio), Style::default().fg(theme.muted)),
                    Span::styled(&entry.label, row_style.fg(Color::White)),
                    Span::styled(rec_hint, Style::default().fg(theme.muted)),
                ]);
                frame.render_widget(
                    Paragraph::new(line),
                    Rect {
                        x: inner.x,
                        y: row_y,
                        width: inner.width,
                        height: 1,
                    },
                );
            }
        }
    }
}

fn confirm_banner_rect(parent: Rect) -> Rect {
    let w: u16 = 44.min(parent.width.saturating_sub(4));
    let h: u16 = 6;
    let x = parent.x + parent.width.saturating_sub(w) / 2;
    let y = parent.y + parent.height.saturating_sub(h) / 2;
    Rect {
        x,
        y,
        width: w,
        height: h,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConfirmBannerAction {
    Save,
    Discard,
    Back,
}

pub fn confirm_banner_hit_test(parent: Rect, col: u16, row: u16) -> Option<ConfirmBannerAction> {
    let banner = confirm_banner_rect(parent);
    let inner_y = banner.y + 3;
    if row != inner_y {
        return None;
    }
    let inner_x = banner.x + 1;
    let inner_w = banner.width.saturating_sub(2);
    if col < inner_x || col >= inner_x + inner_w {
        return None;
    }
    let rel = col - inner_x;
    let third = inner_w / 3;
    if rel < third {
        Some(ConfirmBannerAction::Save)
    } else if rel < third * 2 {
        Some(ConfirmBannerAction::Discard)
    } else {
        Some(ConfirmBannerAction::Back)
    }
}

fn render_confirm_banner(
    frame: &mut Frame,
    parent: Rect,
    theme: &crate::tui::theme::TuiTheme,
    title: &str,
    actions: &[&str],
) {
    let area = frame.area();
    let banner = confirm_banner_rect(parent);

    let sx = banner.x.saturating_add(2);
    let sy = banner.y.saturating_add(1);
    let sw = banner.width.min(area.width.saturating_sub(sx));
    let sh = banner.height.min(area.height.saturating_sub(sy));
    if sw > 0 && sh > 0 {
        let shadow = Rect {
            x: sx,
            y: sy,
            width: sw,
            height: sh,
        };
        frame.render_widget(Clear, shadow);
        frame.render_widget(
            Block::default().style(Style::default().bg(theme.muted)),
            shadow,
        );
    }

    frame.render_widget(Clear, banner);
    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Double)
        .border_style(
            Style::default()
                .fg(theme.accent)
                .add_modifier(Modifier::BOLD),
        )
        .style(Style::default().bg(theme.surface));
    let inner = block.inner(banner);
    frame.render_widget(block, banner);

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // title
            Constraint::Length(1), // spacer
            Constraint::Length(1), // buttons
            Constraint::Min(0),
        ])
        .split(inner);

    let title_line = Paragraph::new(Line::from(Span::styled(
        title,
        Style::default()
            .fg(theme.accent)
            .add_modifier(Modifier::BOLD),
    )))
    .alignment(Alignment::Center);
    frame.render_widget(title_line, chunks[0]);

    let third = chunks[2].width / 3;
    let btn_areas = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Length(third),
            Constraint::Length(third),
            Constraint::Min(0),
        ])
        .split(chunks[2]);

    for (i, action) in actions.iter().enumerate() {
        if i < 3 {
            let btn = Paragraph::new(Line::from(Span::styled(
                *action,
                Style::default().fg(theme.text),
            )))
            .alignment(Alignment::Center);
            frame.render_widget(btn, btn_areas[i]);
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QuitConfirmAction {
    Quit,
    Cancel,
}

pub fn quit_confirm_hit_test(area: Rect, col: u16, row: u16) -> Option<QuitConfirmAction> {
    let w: u16 = 54.min(area.width.saturating_sub(2));
    let h: u16 = 9.min(area.height.saturating_sub(2));
    if w < 20 || h < 5 {
        return None;
    }
    let x = area.width.saturating_sub(w) / 2;
    let y = area.height.saturating_sub(h) / 2;
    let inner_x = x + 1;
    let inner_y = y + 1;
    let inner_w = w.saturating_sub(2);
    let btn_row = inner_y + 4;
    if row != btn_row {
        return None;
    }
    if col < inner_x || col >= inner_x + inner_w {
        return None;
    }
    let mid = inner_x + inner_w / 2;
    if col < mid {
        Some(QuitConfirmAction::Quit)
    } else {
        Some(QuitConfirmAction::Cancel)
    }
}

pub fn render_quit_confirm(frame: &mut Frame, theme: &crate::tui::theme::TuiTheme) {
    let area = frame.area();
    let w: u16 = 54.min(area.width.saturating_sub(2));
    let h: u16 = 9.min(area.height.saturating_sub(2));
    if w < 20 || h < 5 {
        // Terminal too small for the full modal -- fall back to a single line.
        let text = "  Quit foundry?  [Y/Enter] quit  [N] cancel  ";
        let fw = (text.len() as u16 + 2).min(area.width);
        let fx = area.width.saturating_sub(fw) / 2;
        let fy = area.height.saturating_sub(3) / 2;
        let banner = Rect {
            x: fx,
            y: fy,
            width: fw,
            height: 3,
        };
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
    let modal = Rect {
        x,
        y,
        width: w,
        height: h,
    };

    // Drop shadow: offset right 2, down 1, painted in the muted color so the
    // modal looks lifted off the surface behind it.
    let sx = modal.x.saturating_add(2);
    let sy = modal.y.saturating_add(1);
    let sw = modal.width.min(area.width.saturating_sub(sx));
    let sh = modal.height.min(area.height.saturating_sub(sy));
    if sw > 0 && sh > 0 {
        let shadow = Rect {
            x: sx,
            y: sy,
            width: sw,
            height: sh,
        };
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
        "  [Y/Enter] Quit  ",
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
    let buttons = Paragraph::new(Line::from(vec![quit_btn, Span::raw("    "), cancel_btn]))
        .alignment(Alignment::Center);
    frame.render_widget(buttons, chunks[4]);
}

/// Action returned by `summary_modal_hit_test` when the user clicks inside
/// (or on a button of) the AI stage-summary modal.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SummaryModalAction {
    /// Click on the `[ X ]` close button OR the `[Esc] dismiss` footer button.
    Dismiss,
    /// Click on the `[r] refresh` footer button.
    Refresh,
    /// Click on the `[f] open file` footer button (only present when the stage
    /// has a fallback file -- not for ship).
    OpenFile,
    /// Click landed inside the modal but not on any actionable button.
    /// Returned so callers know the click was inside the modal (and should
    /// not fall through to underlying-screen handlers).
    None,
}

/// Geometry of the AI summary modal -- centered, fixed width/height.
/// Shared by renderer and hit-tester so the rects line up exactly.
fn summary_modal_rect(area: Rect) -> Option<Rect> {
    let w: u16 = 78.min(area.width.saturating_sub(2));
    let h: u16 = 18.min(area.height.saturating_sub(2));
    if w < 20 || h < 5 {
        return None;
    }
    let x = area.x + (area.width.saturating_sub(w)) / 2;
    let y = area.y + (area.height.saturating_sub(h)) / 2;
    Some(Rect {
        x,
        y,
        width: w,
        height: h,
    })
}

/// Rect of the footer `[Esc] dismiss   [r] refresh   [f] open file` line within
/// the modal. The footer text is center-aligned; segment widths are constant.
/// Returns `(esc_btn, r_btn, f_btn)` -- f_btn is None when the stage has no
/// fallback file (ship).
fn summary_footer_button_rects(
    modal: Rect,
    has_file: bool,
) -> (Rect, Rect, Option<Rect>) {
    // The full footer text (left-to-right):
    //   "[Esc] dismiss   [r] refresh   [f] open file"
    //    0    5         15  18       28  31         43
    // Each `[X]` segment is the clickable region; we accept clicks on the
    // bracket + the label that follows so the whole thing feels button-y.
    let footer_text_len: u16 = if has_file { 43 } else { 28 };
    let inner_w = modal.width.saturating_sub(2); // minus the L/R borders
    let pad = inner_w.saturating_sub(footer_text_len) / 2;
    let footer_x = modal.x + 1 + pad;
    let footer_y = modal.y + modal.height.saturating_sub(2);

    // Widths sized to "[Esc] dismiss" (13), "[r] refresh" (11), "[f] open file" (13).
    let esc_btn = Rect {
        x: footer_x,
        y: footer_y,
        width: 13,
        height: 1,
    };
    let r_btn = Rect {
        x: footer_x + 16,
        y: footer_y,
        width: 11,
        height: 1,
    };
    let f_btn = if has_file {
        Some(Rect {
            x: footer_x + 30,
            y: footer_y,
            width: 13,
            height: 1,
        })
    } else {
        None
    };
    (esc_btn, r_btn, f_btn)
}

/// Hit-test a mouse click against the AI summary modal. Returns `None` if the
/// modal isn't rendered (terminal too small); returns `SummaryModalAction::None`
/// if the click was inside the modal but not on any button (callers should
/// still treat this as "consumed" so it doesn't fall through to the screen
/// beneath).
pub fn summary_modal_hit_test(
    area: Rect,
    col: u16,
    row: u16,
    has_file: bool,
) -> Option<SummaryModalAction> {
    let modal = summary_modal_rect(area)?;
    if !rect_contains_xy(modal, col, row) {
        return None;
    }
    // [ X ] top-right close button -- shares geometry helper with the settings modal.
    let x_btn = close_btn_rect(modal);
    if rect_contains_xy(x_btn, col, row) {
        return Some(SummaryModalAction::Dismiss);
    }
    let (esc_btn, r_btn, f_btn) = summary_footer_button_rects(modal, has_file);
    if rect_contains_xy(esc_btn, col, row) {
        return Some(SummaryModalAction::Dismiss);
    }
    if rect_contains_xy(r_btn, col, row) {
        return Some(SummaryModalAction::Refresh);
    }
    if let Some(b) = f_btn {
        if rect_contains_xy(b, col, row) {
            return Some(SummaryModalAction::OpenFile);
        }
    }
    Some(SummaryModalAction::None)
}

fn rect_contains_xy(r: Rect, col: u16, row: u16) -> bool {
    col >= r.x && col < r.x + r.width && row >= r.y && row < r.y + r.height
}

pub fn render_stage_summary_overlay(
    frame: &mut Frame,
    theme: &crate::tui::theme::TuiTheme,
    overlay: &StageSummaryOverlay,
) {
    let area = frame.area();
    let modal = match summary_modal_rect(area) {
        Some(r) => r,
        None => return,
    };

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

    // Draw [ X ] close button on the top border, top-right.
    let x_btn = close_btn_rect(modal);
    let buf = frame.buffer_mut();
    let x_btn_style = Style::default()
        .fg(Color::Yellow)
        .add_modifier(Modifier::BOLD);
    for (i, ch) in "[ X ]".chars().enumerate() {
        let col = x_btn.x + i as u16;
        if col < buf.area().width && x_btn.y < buf.area().height {
            buf[(col, x_btn.y)].set_char(ch).set_style(x_btn_style);
        }
    }

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Min(0),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .split(inner);

    let title = Paragraph::new(Line::from(Span::styled(
        format!("{} -- AI summary", overlay.stage_label),
        Style::default()
            .fg(theme.accent)
            .add_modifier(Modifier::BOLD),
    )))
    .alignment(Alignment::Center);
    frame.render_widget(title, chunks[0]);

    let body: Paragraph = if overlay.in_flight && overlay.summary.is_none() {
        // Spinner + elapsed-time animation while waiting on the LLM. The TUI
        // re-renders every 100ms (frame tick), so the spinner advances one
        // braille frame per tick. Elapsed seconds counter tells the user how
        // close we are to the configured summary_timeout_secs cap.
        const SPINNER_FRAMES: &[char] = &[
            '\u{280B}', '\u{2819}', '\u{2839}', '\u{2838}', '\u{283C}',
            '\u{2834}', '\u{2826}', '\u{2827}', '\u{2807}', '\u{280F}',
        ];
        let elapsed = overlay.started_at.elapsed();
        let frame_idx =
            ((elapsed.as_millis() / 100) as usize) % SPINNER_FRAMES.len();
        let spinner = SPINNER_FRAMES[frame_idx];
        let secs = elapsed.as_secs();
        let line = Line::from(vec![
            Span::styled(
                format!("  {} ", spinner),
                Style::default()
                    .fg(theme.accent)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled("summarizing...", Style::default().fg(theme.muted)),
            Span::styled(
                format!("  ({}s)", secs),
                Style::default().fg(theme.muted),
            ),
        ]);
        Paragraph::new(line)
    } else if let Some(text) = &overlay.summary {
        Paragraph::new(text.as_str())
            .wrap(ratatui::widgets::Wrap { trim: false })
            .scroll((overlay.scroll_offset, 0))
            .style(Style::default().fg(theme.text))
    } else {
        Paragraph::new("")
    };
    frame.render_widget(body, chunks[2]);

    let model_label = if overlay.last_model.is_empty() {
        "(default)"
    } else {
        overlay.last_model.as_str()
    };
    let cache_label = if overlay.last_cache_hit { "cached" } else { "fresh" };
    let provider_label = if overlay.last_provider.is_empty() {
        "(default)"
    } else {
        overlay.last_provider.as_str()
    };
    let status_text = if let Some(err) = &overlay.last_error {
        format!("  error: {}", err)
    } else {
        format!(
            "  state: {}   {} {} -- {}",
            overlay.state.as_str(),
            cache_label,
            provider_label,
            model_label,
        )
    };
    let status_style = if overlay.last_error.is_some() {
        Style::default().fg(theme.error)
    } else {
        Style::default().fg(theme.muted)
    };
    let status = Paragraph::new(status_text).style(status_style);
    frame.render_widget(status, chunks[3]);

    // Footer hints styled as button-like spans: the `[Key]` brackets are
    // accent+bold (look clickable), the label text is muted. Hit regions for
    // mouse clicks are computed by `summary_footer_button_rects` -- if you
    // change the text widths here, change them there too.
    let has_file = overlay.stage != "ship";
    let btn_brackets = Style::default()
        .fg(theme.accent)
        .add_modifier(Modifier::BOLD | Modifier::UNDERLINED);
    let btn_label = Style::default().fg(theme.muted);
    let mut spans: Vec<Span> = vec![
        Span::styled("[Esc]", btn_brackets),
        Span::styled(" dismiss", btn_label),
        Span::styled("   ", btn_label),
        Span::styled("[r]", btn_brackets),
        Span::styled(" refresh", btn_label),
    ];
    if has_file {
        spans.push(Span::styled("   ", btn_label));
        spans.push(Span::styled("[f]", btn_brackets));
        spans.push(Span::styled(" open file", btn_label));
    }
    let footer = Paragraph::new(Line::from(spans)).alignment(Alignment::Center);
    frame.render_widget(footer, chunks[4]);
}

pub fn render_running_modal(
    frame: &mut Frame,
    theme: &crate::tui::theme::TuiTheme,
    kind: crate::app::RunningModalKind,
) {
    use crate::app::RunningModalKind;
    let area = frame.area();
    let (w, h): (u16, u16) = match kind {
        RunningModalKind::StopRun => (
            60.min(area.width.saturating_sub(2)),
            9.min(area.height.saturating_sub(2)),
        ),
        RunningModalKind::CtrlC => (
            64.min(area.width.saturating_sub(2)),
            13.min(area.height.saturating_sub(2)),
        ),
    };
    if w < 30 || h < 5 {
        // Terminal too small for the full modal -- fall back to a single line.
        let text = match kind {
            RunningModalKind::StopRun => "  Stop this run?  [Y] yes  [N] no  ",
            RunningModalKind::CtrlC => "  Ctrl+C menu  [1] exit  [2] startup  [3] cancel  ",
        };
        let fw = (text.len() as u16 + 2).min(area.width);
        let fx = area.width.saturating_sub(fw) / 2;
        let fy = area.height.saturating_sub(3) / 2;
        let banner = Rect {
            x: fx,
            y: fy,
            width: fw,
            height: 3,
        };
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
    let modal = Rect {
        x,
        y,
        width: w,
        height: h,
    };

    // Drop shadow: offset right 2, down 1.
    let sx = modal.x.saturating_add(2);
    let sy = modal.y.saturating_add(1);
    let sw = modal.width.min(area.width.saturating_sub(sx));
    let sh = modal.height.min(area.height.saturating_sub(sy));
    if sw > 0 && sh > 0 {
        let shadow = Rect {
            x: sx,
            y: sy,
            width: sw,
            height: sh,
        };
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

    match kind {
        RunningModalKind::StopRun => {
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
                "Stop this run?",
                Style::default()
                    .fg(theme.accent)
                    .add_modifier(Modifier::BOLD),
            )))
            .alignment(Alignment::Center);
            frame.render_widget(title, chunks[0]);

            let msg = Paragraph::new(Line::from(Span::styled(
                "It will halt after the current stage completes. The run can be resumed later.",
                Style::default().fg(theme.muted),
            )))
            .alignment(Alignment::Center);
            frame.render_widget(msg, chunks[2]);

            let stop_btn = Span::styled(
                "  [Y] Stop after current stage  ",
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
            let buttons =
                Paragraph::new(Line::from(vec![stop_btn, Span::raw("    "), cancel_btn]))
                    .alignment(Alignment::Center);
            frame.render_widget(buttons, chunks[4]);
        }
        RunningModalKind::CtrlC => {
            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .constraints([
                    Constraint::Length(1), // title
                    Constraint::Length(1), // spacer
                    Constraint::Length(1), // prompt
                    Constraint::Length(1), // spacer
                    Constraint::Length(1), // opt1
                    Constraint::Length(1), // opt2
                    Constraint::Length(1), // opt3
                    Constraint::Length(1), // spacer
                    Constraint::Length(1), // hint
                    Constraint::Min(0),
                ])
                .split(inner);

            let title = Paragraph::new(Line::from(Span::styled(
                "Ctrl+C -- what would you like to do?",
                Style::default()
                    .fg(theme.accent)
                    .add_modifier(Modifier::BOLD),
            )))
            .alignment(Alignment::Center);
            frame.render_widget(title, chunks[0]);

            let prompt = Paragraph::new(Line::from(Span::styled(
                "Choose an option:",
                Style::default().fg(theme.muted),
            )))
            .alignment(Alignment::Center);
            frame.render_widget(prompt, chunks[2]);

            let opt1 = Paragraph::new(Line::from(Span::styled(
                "  [1] Stop run and exit Foundry",
                Style::default().fg(theme.text),
            )))
            .alignment(Alignment::Left);
            frame.render_widget(opt1, chunks[4]);

            let opt2 = Paragraph::new(Line::from(Span::styled(
                "  [2] Stop run and return to startup screen",
                Style::default().fg(theme.text),
            )))
            .alignment(Alignment::Left);
            frame.render_widget(opt2, chunks[5]);

            let opt3 = Paragraph::new(Line::from(Span::styled(
                "  [3] Cancel (keep running)",
                Style::default().fg(theme.text),
            )))
            .alignment(Alignment::Left);
            frame.render_widget(opt3, chunks[6]);

            let hint = Paragraph::new(Line::from(Span::styled(
                "Press Ctrl+C again to force-quit immediately",
                Style::default()
                    .fg(theme.muted)
                    .add_modifier(Modifier::ITALIC),
            )))
            .alignment(Alignment::Center);
            frame.render_widget(hint, chunks[8]);
        }
    }
}

pub fn render_no_tasks_warning(frame: &mut Frame, theme: &crate::tui::theme::TuiTheme) {
    let area = frame.area();
    let w: u16 = 58.min(area.width.saturating_sub(2));
    let h: u16 = 9.min(area.height.saturating_sub(2));
    if w < 20 || h < 5 {
        let text = "  No TASKS.md found -- describe work first  [Enter] OK  ";
        let fw = (text.len() as u16 + 2).min(area.width);
        let fx = area.width.saturating_sub(fw) / 2;
        let fy = area.height.saturating_sub(3) / 2;
        let banner = Rect {
            x: fx,
            y: fy,
            width: fw,
            height: 3,
        };
        frame.render_widget(Clear, banner);
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(theme.warning))
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
    let modal = Rect {
        x,
        y,
        width: w,
        height: h,
    };

    let sx = modal.x.saturating_add(2);
    let sy = modal.y.saturating_add(1);
    let sw = modal.width.min(area.width.saturating_sub(sx));
    let sh = modal.height.min(area.height.saturating_sub(sy));
    if sw > 0 && sh > 0 {
        let shadow = Rect {
            x: sx,
            y: sy,
            width: sw,
            height: sh,
        };
        frame.render_widget(Clear, shadow);
        frame.render_widget(
            Block::default().style(Style::default().bg(theme.muted)),
            shadow,
        );
    }

    frame.render_widget(Clear, modal);
    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Double)
        .border_style(
            Style::default()
                .fg(theme.warning)
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
            Constraint::Length(1), // button
            Constraint::Min(0),
        ])
        .split(inner);

    let title = Paragraph::new(Line::from(Span::styled(
        "No task queue found",
        Style::default()
            .fg(theme.warning)
            .add_modifier(Modifier::BOLD),
    )))
    .alignment(Alignment::Center);
    frame.render_widget(title, chunks[0]);

    let msg = Paragraph::new(Line::from(Span::styled(
        "Describe work or scan the project to create TASKS.md.",
        Style::default().fg(theme.muted),
    )))
    .alignment(Alignment::Center);
    frame.render_widget(msg, chunks[2]);

    let ok_btn = Span::styled(
        "  [Enter] OK  ",
        Style::default()
            .bg(theme.accent)
            .fg(Color::Black)
            .add_modifier(Modifier::BOLD),
    );
    let buttons = Paragraph::new(Line::from(ok_btn)).alignment(Alignment::Center);
    frame.render_widget(buttons, chunks[4]);
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GitInitOfferAction {
    Github,
    Local,
    Skip,
}

pub fn git_init_offer_hit_test(
    area: Rect,
    gh_available: bool,
    col: u16,
    row: u16,
) -> Option<GitInitOfferAction> {
    let w: u16 = 56.min(area.width.saturating_sub(2));
    let h: u16 = if gh_available { 11 } else { 9 }.min(area.height.saturating_sub(2));
    if w < 20 || h < 5 {
        let text = if gh_available {
            "  No git repo  [G] GitHub  [L/Enter] Local  [S] Skip  "
        } else {
            "  No git repo  [L/Enter] Init  [S] Skip  "
        };
        let fw = (text.len() as u16 + 2).min(area.width);
        let fx = area.width.saturating_sub(fw) / 2;
        let fy = area.height.saturating_sub(3) / 2;
        let inner_x = fx.saturating_add(1);
        let inner_w = fw.saturating_sub(2);
        if row != fy.saturating_add(1) || col < inner_x || col >= inner_x.saturating_add(inner_w) {
            return None;
        }
        if gh_available {
            let third = inner_w / 3;
            if col < inner_x.saturating_add(third) {
                Some(GitInitOfferAction::Github)
            } else if col < inner_x.saturating_add(third.saturating_mul(2)) {
                Some(GitInitOfferAction::Local)
            } else {
                Some(GitInitOfferAction::Skip)
            }
        } else {
            let mid = inner_x.saturating_add(inner_w / 2);
            if col < mid {
                Some(GitInitOfferAction::Local)
            } else {
                Some(GitInitOfferAction::Skip)
            }
        }
    } else {
        let x = area.width.saturating_sub(w) / 2;
        let y = area.height.saturating_sub(h) / 2;
        let inner_x = x.saturating_add(1);
        let inner_y = y.saturating_add(1);
        let inner_w = w.saturating_sub(2);
        if col < inner_x || col >= inner_x.saturating_add(inner_w) {
            return None;
        }

        if gh_available {
            match row {
                r if r == inner_y.saturating_add(4) => Some(GitInitOfferAction::Github),
                r if r == inner_y.saturating_add(5) => Some(GitInitOfferAction::Local),
                r if r == inner_y.saturating_add(6) => Some(GitInitOfferAction::Skip),
                _ => None,
            }
        } else if row == inner_y.saturating_add(4) {
            let mid = inner_x.saturating_add(inner_w / 2);
            if col < mid {
                Some(GitInitOfferAction::Local)
            } else {
                Some(GitInitOfferAction::Skip)
            }
        } else {
            None
        }
    }
}

pub fn render_git_init_offer(
    frame: &mut Frame,
    theme: &crate::tui::theme::TuiTheme,
    gh_available: bool,
) {
    let area = frame.area();
    let w: u16 = 56.min(area.width.saturating_sub(2));
    let h: u16 = if gh_available { 11 } else { 9 }.min(area.height.saturating_sub(2));
    if w < 20 || h < 5 {
        let text = if gh_available {
            "  No git repo  [G] GitHub  [L/Enter] Local  [S] Skip  "
        } else {
            "  No git repo  [L/Enter] Init  [S] Skip  "
        };
        let fw = (text.len() as u16 + 2).min(area.width);
        let fx = area.width.saturating_sub(fw) / 2;
        let fy = area.height.saturating_sub(3) / 2;
        let banner = Rect {
            x: fx,
            y: fy,
            width: fw,
            height: 3,
        };
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
    let modal = Rect {
        x,
        y,
        width: w,
        height: h,
    };

    let sx = modal.x.saturating_add(2);
    let sy = modal.y.saturating_add(1);
    let sw = modal.width.min(area.width.saturating_sub(sx));
    let sh = modal.height.min(area.height.saturating_sub(sy));
    if sw > 0 && sh > 0 {
        let shadow = Rect {
            x: sx,
            y: sy,
            width: sw,
            height: sh,
        };
        frame.render_widget(Clear, shadow);
        frame.render_widget(
            Block::default().style(Style::default().bg(theme.muted)),
            shadow,
        );
    }

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

    if gh_available {
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(1), // title
                Constraint::Length(1), // spacer
                Constraint::Length(1), // message
                Constraint::Length(1), // spacer
                Constraint::Length(1), // GitHub button
                Constraint::Length(1), // local button
                Constraint::Length(1), // skip button
                Constraint::Min(0),
            ])
            .split(inner);

        let title = Paragraph::new(Line::from(Span::styled(
            "No git repository",
            Style::default()
                .fg(theme.accent)
                .add_modifier(Modifier::BOLD),
        )))
        .alignment(Alignment::Center);
        frame.render_widget(title, chunks[0]);

        let msg = Paragraph::new(Line::from(Span::styled(
            "Initialize a repository for this project?",
            Style::default().fg(theme.muted),
        )))
        .alignment(Alignment::Center);
        frame.render_widget(msg, chunks[2]);

        let gh_btn = Span::styled(
            "  [G] Create GitHub repo (private)  ",
            Style::default()
                .bg(theme.accent)
                .fg(Color::Black)
                .add_modifier(Modifier::BOLD),
        );
        frame.render_widget(
            Paragraph::new(Line::from(gh_btn)).alignment(Alignment::Center),
            chunks[4],
        );

        let local_btn = Span::styled(
            "  [L/Enter] Local git init  ",
            Style::default()
                .bg(theme.border)
                .fg(theme.text)
                .add_modifier(Modifier::BOLD),
        );
        frame.render_widget(
            Paragraph::new(Line::from(local_btn)).alignment(Alignment::Center),
            chunks[5],
        );

        let skip_btn = Span::styled("  [S/Esc] Skip  ", Style::default().fg(theme.muted));
        frame.render_widget(
            Paragraph::new(Line::from(skip_btn)).alignment(Alignment::Center),
            chunks[6],
        );
    } else {
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
            "No git repository",
            Style::default()
                .fg(theme.accent)
                .add_modifier(Modifier::BOLD),
        )))
        .alignment(Alignment::Center);
        frame.render_widget(title, chunks[0]);

        let msg = Paragraph::new(Line::from(Span::styled(
            "Initialize a local git repository?",
            Style::default().fg(theme.muted),
        )))
        .alignment(Alignment::Center);
        frame.render_widget(msg, chunks[2]);

        let init_btn = Span::styled(
            "  [L/Enter] Init  ",
            Style::default()
                .bg(theme.accent)
                .fg(Color::Black)
                .add_modifier(Modifier::BOLD),
        );
        let skip_btn = Span::styled(
            "  [S/Esc] Skip  ",
            Style::default()
                .bg(theme.border)
                .fg(theme.text)
                .add_modifier(Modifier::BOLD),
        );
        let buttons = Paragraph::new(Line::from(vec![init_btn, Span::raw("    "), skip_btn]))
            .alignment(Alignment::Center);
        frame.render_widget(buttons, chunks[4]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::app::{ModelEntry, ModelPicker};

    #[test]
    fn git_init_offer_hit_test_maps_modal_rows() {
        let area = Rect::new(0, 0, 120, 40);

        assert_eq!(
            git_init_offer_hit_test(area, true, 60, 19),
            Some(GitInitOfferAction::Github)
        );
        assert_eq!(
            git_init_offer_hit_test(area, true, 60, 20),
            Some(GitInitOfferAction::Local)
        );
        assert_eq!(
            git_init_offer_hit_test(area, true, 60, 21),
            Some(GitInitOfferAction::Skip)
        );
        assert_eq!(git_init_offer_hit_test(area, true, 60, 18), None);
    }

    #[test]
    fn git_init_offer_hit_test_splits_local_and_skip_without_gh() {
        let area = Rect::new(0, 0, 120, 40);

        assert_eq!(
            git_init_offer_hit_test(area, false, 40, 20),
            Some(GitInitOfferAction::Local)
        );
        assert_eq!(
            git_init_offer_hit_test(area, false, 70, 20),
            Some(GitInitOfferAction::Skip)
        );
        assert_eq!(git_init_offer_hit_test(area, false, 40, 19), None);
    }

    #[test]
    fn model_picker_hit_test_closes_only_on_close_or_outside() {
        let parent = Rect::new(0, 0, 100, 30);
        let picker = ModelPicker::new(
            "plan",
            vec![ModelEntry {
                provider: "test".to_string(),
                model: "model".to_string(),
                label: "Model".to_string(),
                recommended: false,
                group: "Test".to_string(),
            }],
        );
        let popup = model_picker_rect(parent, &picker);
        let close = picker_close_btn_rect(popup);

        assert_eq!(
            model_picker_hit_test(parent, &picker, close.x, close.y),
            Some(ModelPickerMouseTarget::CloseBtn)
        );
        assert_eq!(
            model_picker_hit_test(parent, &picker, 0, 0),
            Some(ModelPickerMouseTarget::OutsideClick)
        );
        assert_eq!(
            model_picker_hit_test(parent, &picker, popup.x + 1, popup.y + 3),
            None
        );
    }
}

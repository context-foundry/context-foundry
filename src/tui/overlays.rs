use ratatui::{
    layout::{Alignment, Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, Paragraph},
    Frame,
};

use crate::app::AppState;
use crate::app::{ExplorerContextMenu, SurfaceSummaryOverlay};
use crate::config::Config;
use crate::tui::modal_spec::{
    compute_modal_layout, modal_rect, render_unified_modal, unified_modal_hit_test, ModalButton,
    ModalSize, ModalSpec,
};
use crate::utils::truncate_str;

pub(super) fn render_patterns(frame: &mut Frame, state: &AppState, config: &Config) {
    let theme = &state.tui_theme;
    let area = frame.area();
    let inner_width = area.width.saturating_sub(6) as usize;
    let (title, body) = patterns_body_lines(state, config, inner_width);
    let spec = ModalSpec {
        title,
        body,
        footer_buttons: vec![
            ModalButton {
                key: "p".into(),
                label: " back".into(),
                action_id: "back".into(),
            },
            ModalButton {
                key: "\u{2191}\u{2193}".into(),
                label: " scroll".into(),
                action_id: "scroll".into(),
            },
            ModalButton {
                key: "q".into(),
                label: " quit".into(),
                action_id: "quit".into(),
            },
        ],
        status_line: None,
        size: ModalSize::Custom(area),
        scroll_offset: state.patterns_scroll as u16,
        show_close_button: true,
        border_color: theme.info,
        status_color: theme.muted,
    };
    let _ = render_unified_modal(frame, theme, &spec);
}

pub(super) fn render_findings(frame: &mut Frame, state: &AppState) {
    let theme = &state.tui_theme;
    let area = frame.area();
    let inner_width = area.width.saturating_sub(6) as usize;
    let (title, body) = findings_body_lines(state, inner_width);
    let spec = ModalSpec {
        title,
        body,
        footer_buttons: vec![
            ModalButton {
                key: "f".into(),
                label: " back".into(),
                action_id: "back".into(),
            },
            ModalButton {
                key: "\u{2191}\u{2193}".into(),
                label: " scroll".into(),
                action_id: "scroll".into(),
            },
            ModalButton {
                key: "q".into(),
                label: " quit".into(),
                action_id: "quit".into(),
            },
        ],
        status_line: None,
        size: ModalSize::Custom(area),
        scroll_offset: state.findings_scroll as u16,
        show_close_button: true,
        border_color: theme.info,
        status_color: theme.muted,
    };
    let _ = render_unified_modal(frame, theme, &spec);
}

fn findings_body_lines(state: &AppState, inner_width: usize) -> (String, Vec<Line<'static>>) {
    let theme = &state.tui_theme;
    let Some(ref outcome) = state.last_orchestrator_outcome else {
        let lines: Vec<Line<'static>> = vec![
            Line::from(""),
            Line::from(Span::styled(
                "  No review findings available.",
                Style::default().fg(theme.muted),
            )),
        ];
        return (" Review Findings ".to_string(), lines);
    };

    let mut display_lines: Vec<Line<'static>> = Vec::new();

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

    let title = if outcome.accepted {
        " Review Findings ".to_string()
    } else {
        " Review Findings (unresolved) ".to_string()
    };

    (title, display_lines)
}

fn patterns_body_lines(
    state: &AppState,
    _config: &Config,
    inner_width: usize,
) -> (String, Vec<Line<'static>>) {
    let theme = &state.tui_theme;
    let summary_opt = state.skill_citation_summary.as_ref();

    let mut display_lines: Vec<Line<'static>> = Vec::new();

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

    let full_title = if db_path_str.is_empty() {
        title
    } else {
        format!("{}| {} ", title, db_path_str)
    };

    (full_title, display_lines)
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

// ─── Stats Overlay ──────────────────────────────────────────

pub(super) fn render_stats_overlay(frame: &mut Frame, state: &AppState) {
    let theme = &state.tui_theme;
    let area = frame.area();
    let (title, body) = stats_body_lines(state);
    let spec = ModalSpec {
        title,
        body,
        footer_buttons: vec![
            ModalButton {
                key: "s".into(),
                label: " back".into(),
                action_id: "back".into(),
            },
            ModalButton {
                key: "Esc".into(),
                label: " back".into(),
                action_id: "dismiss".into(),
            },
            ModalButton {
                key: "\u{2191}\u{2193}".into(),
                label: " scroll".into(),
                action_id: "scroll".into(),
            },
            ModalButton {
                key: "q".into(),
                label: " quit".into(),
                action_id: "quit".into(),
            },
        ],
        status_line: None,
        size: ModalSize::Custom(area),
        scroll_offset: state.stats_overlay_scroll as u16,
        show_close_button: true,
        border_color: theme.info,
        status_color: theme.muted,
    };
    let _ = render_unified_modal(frame, theme, &spec);
}

fn stats_body_lines(state: &AppState) -> (String, Vec<Line<'static>>) {
    let theme = &state.tui_theme;

    let Some(ref report) = state.stats_overlay_report else {
        let lines: Vec<Line<'static>> = vec![
            Line::from(""),
            Line::from(Span::styled(
                "  No stats data available.",
                Style::default().fg(theme.muted),
            )),
        ];
        return (" Stats Report ".to_string(), lines);
    };

    let mut display_lines: Vec<Line<'static>> = Vec::new();

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

    (" Stats Report ".to_string(), display_lines)
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

    let ov = state.settings_overlay.as_ref();
    let focus = ov.map(|o| o.focus).unwrap_or(0);
    let expanded = ov.map(|o| &o.expanded_sections);
    let scroll_offset = ov.map(|o| o.scroll_offset).unwrap_or(0);
    let editing = ov.and_then(|o| o.editing.as_ref());
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
    let status_color = if editing.and_then(|inline| inline.error.as_ref()).is_some() {
        Color::Yellow
    } else {
        theme.muted
    };

    let spec = ModalSpec {
        title: " Settings -- Foundry ".to_string(),
        body: Vec::new(),
        footer_buttons: vec![
            ModalButton {
                key: "\u{2191}\u{2193}".into(),
                label: " navigate".into(),
                action_id: "nav".into(),
            },
            ModalButton {
                key: "Enter".into(),
                label: " toggle/edit".into(),
                action_id: "toggle".into(),
            },
            ModalButton {
                key: "Esc".into(),
                label: " close".into(),
                action_id: "dismiss".into(),
            },
        ],
        status_line: Some(Line::from(Span::styled(
            status_text,
            Style::default().fg(status_color),
        ))),
        size: ModalSize::Custom(modal),
        scroll_offset: 0,
        show_close_button: true,
        border_color: theme.accent,
        status_color,
    };
    let layout = match render_unified_modal(frame, theme, &spec) {
        Some(l) => l,
        None => return,
    };

    let inner = layout.body;

    let highlight_bg = if theme.surface == Color::Reset {
        Color::DarkGray
    } else {
        theme.surface
    };

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
    let content_height = inner.height as usize;
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
    let modal = modal_rect(area, ModalSize::Confirm)?;
    let layout = compute_modal_layout(modal);
    let spec = ModalSpec {
        title: String::new(),
        body: Vec::new(),
        footer_buttons: vec![
            ModalButton {
                key: "Y/Enter".into(),
                label: " Quit".into(),
                action_id: "quit".into(),
            },
            ModalButton {
                key: "N".into(),
                label: " Cancel".into(),
                action_id: "cancel".into(),
            },
        ],
        status_line: None,
        size: ModalSize::Confirm,
        scroll_offset: 0,
        show_close_button: true,
        border_color: Color::Reset,
        status_color: Color::Reset,
    };
    let id = unified_modal_hit_test(&layout, &spec, col, row)?;
    Some(match id.as_str() {
        "quit" => QuitConfirmAction::Quit,
        "cancel" | "dismiss" => QuitConfirmAction::Cancel,
        _ => return None,
    })
}

pub fn render_quit_confirm(frame: &mut Frame, theme: &crate::tui::theme::TuiTheme) {
    let body = vec![
        Line::from(""),
        Line::from(Span::styled(
            "Any in-flight work will be left as-is.",
            Style::default().fg(theme.muted),
        )),
    ];
    let spec = ModalSpec {
        title: "Quit foundry?".to_string(),
        body,
        footer_buttons: vec![
            ModalButton {
                key: "Y/Enter".into(),
                label: " Quit".into(),
                action_id: "quit".into(),
            },
            ModalButton {
                key: "N".into(),
                label: " Cancel".into(),
                action_id: "cancel".into(),
            },
        ],
        status_line: None,
        size: ModalSize::Confirm,
        scroll_offset: 0,
        show_close_button: true,
        border_color: theme.accent,
        status_color: theme.muted,
    };
    let _ = render_unified_modal(frame, theme, &spec);
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

fn summary_footer_buttons(has_file: bool) -> Vec<ModalButton> {
    let mut buttons = vec![
        ModalButton {
            key: "Esc".into(),
            label: " dismiss".into(),
            action_id: "dismiss".into(),
        },
        ModalButton {
            key: "r".into(),
            label: " refresh".into(),
            action_id: "refresh".into(),
        },
    ];
    if has_file {
        buttons.push(ModalButton {
            key: "f".into(),
            label: " open file".into(),
            action_id: "open-file".into(),
        });
    }
    buttons
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
    let modal = modal_rect(area, ModalSize::Small)?;
    let layout = compute_modal_layout(modal);
    let footer_buttons = summary_footer_buttons(has_file);
    let spec = ModalSpec {
        title: String::new(),
        body: Vec::new(),
        footer_buttons,
        status_line: None,
        size: ModalSize::Small,
        scroll_offset: 0,
        show_close_button: true,
        border_color: Color::Reset,
        status_color: Color::Reset,
    };
    let id = unified_modal_hit_test(&layout, &spec, col, row)?;
    Some(match id.as_str() {
        "dismiss" => SummaryModalAction::Dismiss,
        "refresh" => SummaryModalAction::Refresh,
        "open-file" => SummaryModalAction::OpenFile,
        _ => SummaryModalAction::None,
    })
}

pub fn render_surface_summary_overlay(
    frame: &mut Frame,
    theme: &crate::tui::theme::TuiTheme,
    overlay: &SurfaceSummaryOverlay,
) {
    let has_file = overlay.stage != "ship";
    let footer_buttons = summary_footer_buttons(has_file);

    let body: Vec<Line<'static>> = if overlay.in_flight && overlay.summary.is_none() {
        const SPINNER_FRAMES: &[char] = &[
            '\u{280B}', '\u{2819}', '\u{2839}', '\u{2838}', '\u{283C}',
            '\u{2834}', '\u{2826}', '\u{2827}', '\u{2807}', '\u{280F}',
        ];
        let elapsed = overlay.started_at.elapsed();
        let frame_idx =
            ((elapsed.as_millis() / 100) as usize) % SPINNER_FRAMES.len();
        let spinner = SPINNER_FRAMES[frame_idx];
        let secs = elapsed.as_secs();
        vec![Line::from(vec![
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
        ])]
    } else if let Some(text) = &overlay.summary {
        text.lines()
            .map(|l| Line::from(Span::styled(l.to_string(), Style::default().fg(theme.text))))
            .collect()
    } else {
        Vec::new()
    };

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
    let status_color = if overlay.last_error.is_some() {
        theme.error
    } else {
        theme.muted
    };
    let status_line = Some(Line::from(Span::styled(
        status_text,
        Style::default().fg(status_color),
    )));

    let spec = ModalSpec {
        title: format!("{} -- AI summary", overlay.stage_label),
        body,
        footer_buttons,
        status_line,
        size: ModalSize::Small,
        scroll_offset: overlay.scroll_offset,
        show_close_button: true,
        border_color: theme.accent,
        status_color,
    };
    let _ = render_unified_modal(frame, theme, &spec);
}

pub fn render_running_modal(
    frame: &mut Frame,
    theme: &crate::tui::theme::TuiTheme,
    kind: crate::app::RunningModalKind,
) {
    use crate::app::RunningModalKind;
    match kind {
        RunningModalKind::StopRun => {
            let body = vec![
                Line::from(""),
                Line::from(Span::styled(
                    "It will halt after the current stage completes. The run can be resumed later.",
                    Style::default().fg(theme.muted),
                )),
            ];
            let spec = ModalSpec {
                title: "Stop this run?".to_string(),
                body,
                footer_buttons: vec![
                    ModalButton {
                        key: "Y".into(),
                        label: " Stop after current stage".into(),
                        action_id: "stop".into(),
                    },
                    ModalButton {
                        key: "N".into(),
                        label: " Cancel".into(),
                        action_id: "cancel".into(),
                    },
                ],
                status_line: None,
                size: ModalSize::Confirm,
                scroll_offset: 0,
                show_close_button: true,
                border_color: theme.error,
                status_color: theme.muted,
            };
            let _ = render_unified_modal(frame, theme, &spec);
        }
        RunningModalKind::CtrlC => {
            let body = vec![
                Line::from(""),
                Line::from(Span::styled(
                    "  [1] Stop run and exit Foundry",
                    Style::default().fg(theme.text),
                )),
                Line::from(Span::styled(
                    "  [2] Stop run and return to startup screen",
                    Style::default().fg(theme.text),
                )),
                Line::from(Span::styled(
                    "  [3] Cancel (keep running)",
                    Style::default().fg(theme.text),
                )),
                Line::from(""),
                Line::from(Span::styled(
                    "Press Ctrl+C again to force-quit immediately",
                    Style::default()
                        .fg(theme.muted)
                        .add_modifier(Modifier::ITALIC),
                )),
            ];
            let spec = ModalSpec {
                title: "Ctrl+C -- what would you like to do?".to_string(),
                body,
                footer_buttons: vec![
                    ModalButton {
                        key: "1".into(),
                        label: " exit".into(),
                        action_id: "ctrlc-1".into(),
                    },
                    ModalButton {
                        key: "2".into(),
                        label: " startup".into(),
                        action_id: "ctrlc-2".into(),
                    },
                    ModalButton {
                        key: "3".into(),
                        label: " cancel".into(),
                        action_id: "ctrlc-3".into(),
                    },
                ],
                status_line: None,
                size: ModalSize::MenuMedium,
                scroll_offset: 0,
                show_close_button: true,
                border_color: theme.accent,
                status_color: theme.muted,
            };
            let _ = render_unified_modal(frame, theme, &spec);
        }
    }
}

pub fn render_no_tasks_warning(frame: &mut Frame, theme: &crate::tui::theme::TuiTheme) {
    let body = vec![
        Line::from(""),
        Line::from(Span::styled(
            "Describe work or scan the project to create TASKS.md.",
            Style::default().fg(theme.muted),
        )),
    ];
    let spec = ModalSpec {
        title: "No task queue found".to_string(),
        body,
        footer_buttons: vec![ModalButton {
            key: "Enter".into(),
            label: " OK".into(),
            action_id: "ok".into(),
        }],
        status_line: None,
        size: ModalSize::Confirm,
        scroll_offset: 0,
        show_close_button: true,
        border_color: theme.warning,
        status_color: theme.muted,
    };
    let _ = render_unified_modal(frame, theme, &spec);
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

// ─── Explorer right-click context menu ───────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContextMenuHit {
    AiSummary,
}

fn context_menu_rect(menu: &ExplorerContextMenu, frame_area: Rect) -> Rect {
    let width: u16 = 18;
    let height: u16 = 3;
    let x = menu
        .anchor_col
        .min(frame_area.x + frame_area.width.saturating_sub(width));
    let y = menu
        .anchor_row
        .min(frame_area.y + frame_area.height.saturating_sub(height));
    Rect::new(x, y, width, height)
}

pub fn render_explorer_context_menu(
    frame: &mut Frame,
    theme: &crate::tui::theme::TuiTheme,
    menu: &ExplorerContextMenu,
) {
    let area = frame.area();
    let rect = context_menu_rect(menu, area);
    frame.render_widget(Clear, rect);
    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Plain)
        .border_style(Style::default().fg(theme.accent))
        .style(Style::default().bg(theme.surface).fg(theme.text));
    let inner = block.inner(rect);
    frame.render_widget(block, rect);
    let line = Paragraph::new(Line::from(Span::styled(
        " AI summary ",
        Style::default().fg(theme.text),
    )));
    frame.render_widget(line, inner);
}

pub fn context_menu_hit_test(
    menu: &ExplorerContextMenu,
    col: u16,
    row: u16,
) -> Option<ContextMenuHit> {
    // Use a generous frame area so the rect calculation only clamps when the
    // anchor was placed beyond a sensible terminal size; click hit-tests do
    // not have access to the live frame area so we assume "fits in 200x80".
    let frame_area = Rect::new(0, 0, 200, 80);
    let rect = context_menu_rect(menu, frame_area);
    if col >= rect.x + 1
        && col < rect.x + rect.width.saturating_sub(1)
        && row == rect.y + 1
    {
        Some(ContextMenuHit::AiSummary)
    } else {
        None
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

    #[test]
    fn context_menu_hit_test_returns_ai_summary_on_label_row() {
        let menu = ExplorerContextMenu {
            anchor_col: 10,
            anchor_row: 5,
            file_path: std::path::PathBuf::from("/x/y.rs"),
        };
        let hit = context_menu_hit_test(&menu, 11, 6);
        assert_eq!(hit, Some(ContextMenuHit::AiSummary));
        let miss = context_menu_hit_test(&menu, 0, 0);
        assert!(miss.is_none());
    }
}

use ratatui::{
    layout::{Constraint, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Cell, Paragraph, Row, Table, Wrap},
    Frame,
};

use crate::agent::{AgentRole, ModelProvider};
use crate::app::AppState;
use crate::config::Config;

/// Single-letter abbreviation for a pipeline stage's QRPBA indicator
/// (`query`->Q, `research`->R, `plan`->P, `implement`->B, `doubt`->A).
/// Falls back to the uppercased first character of the stage label so
/// custom stages still render legibly.
fn stage_indicator_letter(stage: &crate::config::PipelineStageConfig) -> char {
    match stage.id.as_str() {
        "query" => 'Q',
        "research" => 'R',
        "plan" => 'P',
        "implement" => 'B',
        "doubt" => 'A',
        _ => stage
            .label
            .chars()
            .next()
            .map(|c| c.to_ascii_uppercase())
            .unwrap_or('?'),
    }
}

pub(super) fn render_dashboard_stats(
    frame: &mut Frame,
    area: Rect,
    state: &AppState,
    config: &Config,
) {
    let theme = &state.tui_theme;
    let mut lines = Vec::new();
    let selected_idx = state.dual_build.tab.min(1);
    let provider = effective_stats_provider(config, state, selected_idx);
    let visible_input_tokens = if state.dual_build.active {
        state.dual_build.input_tokens[selected_idx]
    } else {
        state.session_input_tokens
    };
    let visible_context_pcts = if state.dual_build.active {
        state.dual_build.context_pcts[selected_idx]
    } else {
        state.spid_context_pcts
    };
    let visible_stage_context_pcts = if state.dual_build.active {
        &state.dual_build.stage_context_pcts[selected_idx]
    } else {
        &state.stage_context_pcts
    };
    let metrics_unavailable = metrics_unavailable(provider, visible_input_tokens);

    // Progress: [93/96] ████████████░░ 97%
    let completed = state.completed_count;
    let total = state.total_count;
    let pct = (completed * 100).checked_div(total).unwrap_or(0);
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
            Style::default()
                .fg(theme.warning)
                .add_modifier(ratatui::style::Modifier::BOLD),
        ),
        Span::styled(
            "\u{2588}".repeat(filled),
            Style::default().fg(theme.success),
        ),
        Span::styled("\u{2591}".repeat(empty), Style::default().fg(theme.muted)),
        Span::styled(
            right_label,
            Style::default()
                .fg(theme.warning)
                .add_modifier(ratatui::style::Modifier::BOLD),
        ),
    ];
    lines.push(Line::from(bar_spans));

    // Two-column layout: left = git + patterns, right = context + timing
    // We build each line with left and right halves padded to fill the width.
    let half_width = area.width.saturating_sub(4) as usize / 2; // borders + padding

    // ─── Row 1: Git | Context QRPBA ───
    let (ollama_label, ollama_color) = match state.last_pattern_match_mode.as_deref() {
        Some("semantic") => ("connected", Color::Green),
        Some("cooldown") => ("down", Color::Red),
        Some("keyword-only") => ("off", Color::Yellow),
        _ => ("--", Color::DarkGray),
    };

    // Build per-stage context spans driven by config.pipeline_stages so the
    // bottom meter mirrors the pipeline diagram at the top (QRPBA when all
    // stages are enabled, fewer letters when stages are disabled).
    let context_stages: Vec<(char, String, Color)> = config
        .pipeline_stages
        .iter()
        .filter(|s| s.enabled)
        .map(|stage| {
            let letter = stage_indicator_letter(stage);
            let pct =
                if let Some(slot) = AgentRole::from_str(&stage.id).and_then(|r| r.qrpba_slot()) {
                    visible_context_pcts.get(slot).copied().flatten()
                } else {
                    visible_stage_context_pcts.get(&stage.id).copied()
                };
            let (text, color) = ctx_pct_span(pct, metrics_unavailable, theme.muted);
            (letter, text, color)
        })
        .collect();

    let git_status_str = if state.git_initialized {
        let remote_part = state.git_remote.as_deref().unwrap_or("no remote");
        format!(
            "{} | {} | {} dirty",
            state.git_branch, remote_part, state.git_dirty_count
        )
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

    let mut row1_spans = vec![
        Span::styled("  Git      ", Style::default().fg(theme.info)),
        Span::styled(
            format!(
                "{:<width$}",
                git_status_str,
                width = half_width.saturating_sub(11)
            ),
            Style::default().fg(git_status_color),
        ),
        Span::styled("Context   ", Style::default().fg(theme.info)),
    ];
    let last_idx = context_stages.len().saturating_sub(1);
    for (i, (letter, text, color)) in context_stages.iter().enumerate() {
        let label = if i == 0 {
            format!("{}:", letter)
        } else {
            format!(" {}:", letter)
        };
        row1_spans.push(Span::styled(label, Style::default().fg(theme.muted)));
        if i == last_idx {
            row1_spans.push(Span::styled(text.clone(), Style::default().fg(*color)));
        } else {
            row1_spans.push(Span::styled(
                format!("{:<4}", text),
                Style::default().fg(*color),
            ));
        }
    }
    lines.push(Line::from(row1_spans));

    if let Some(ref report) = state.eval_report_cache {
        if !report.aggregate_badge.is_empty() {
            let badge_color = badge_color_for(&report.aggregate_badge, theme);
            lines.push(Line::from(vec![
                Span::styled(
                    format!("{:<width$}", "", width = half_width),
                    Style::default(),
                ),
                Span::styled("Eval      ", Style::default().fg(theme.info)),
                Span::styled(report.aggregate_badge.clone(), Style::default().fg(badge_color)),
            ]));
        }
    }

    // ─── Row 2: Extensions ───
    if !state.extension_inject_count.is_empty() {
        let ext_parts: Vec<String> = state
            .extension_inject_count
            .iter()
            .map(|(name, inj)| {
                let refs = state
                    .extension_reference_count
                    .get(name)
                    .copied()
                    .unwrap_or(0);
                format!("{} {} inj, {} ref", name, inj, refs)
            })
            .collect();
        lines.push(Line::from(vec![
            Span::styled("  Plugins  ", Style::default().fg(theme.accent)),
            Span::styled(ext_parts.join("  "), Style::default().fg(theme.text)),
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

    let task_label: String = if let Some(t) = state.current_task.as_ref() {
        format!("task {}: ", t.id)
    } else {
        "task: ".to_string()
    };

    let stage_segments: Option<(String, String)> = state.current_agent.as_ref().map(|(role, started)| {
        let stage_label = format!("stage {}: ", role);
        let stage_str = format_duration_hms(now.signed_duration_since(*started));
        (stage_label, stage_str)
    });

    let (cost_label, cost_usd, input_tokens, output_tokens) = if state.dual_build.active {
        (
            format!(
                "Cost [{}: {}]",
                selected_idx + 1,
                state.dual_build.models[selected_idx]
            ),
            state.dual_build.cost_usd[selected_idx],
            state.dual_build.input_tokens[selected_idx],
            state.dual_build.output_tokens[selected_idx],
        )
    } else {
        (
            "Cost".to_string(),
            state.session_cost_usd,
            state.session_input_tokens,
            state.session_output_tokens,
        )
    };
    let (cost_str, cost_color) = if metrics_unavailable {
        (format!("N/A ({})", provider), theme.muted)
    } else {
        let cost_str = format!(
            "${:.2} ({}in / {}out)",
            cost_usd,
            format_compact_tokens(input_tokens),
            format_compact_tokens(output_tokens),
        );
        let cost_color = if cost_usd >= 10.0 {
            Color::Red
        } else if cost_usd >= 5.0 {
            Color::Yellow
        } else {
            theme.text
        };
        (cost_str, cost_color)
    };

    let patterns_left = format!(
        "{} inj, {} applied  feat: {}  WIP: {}",
        state.pattern_inject_count,
        state.pattern_apply_count,
        state.session_feat_commits,
        state.session_wip_commits,
    );
    lines.push(Line::from(vec![
        Span::styled("  Patterns ", Style::default().fg(theme.info)),
        Span::styled(
            format!(
                "{:<width$}",
                patterns_left,
                width = half_width.saturating_sub(11)
            ),
            Style::default().fg(theme.text),
        ),
        Span::styled(format!("{cost_label} "), Style::default().fg(theme.info)),
        Span::styled(&cost_str, Style::default().fg(cost_color)),
    ]));

    let dual_comparison = dual_comparison_line(state);
    let (ollama_left, ollama_left_color) = if let Some(comparison) = dual_comparison {
        (comparison, theme.text)
    } else if !state.tmux_session_names.is_empty() {
        let count = state.tmux_session_names.len();
        let latest = state.tmux_session_names.last().unwrap();
        let display = if count == 1 {
            format!("Tmux: {} | attach -t {}", count, latest)
        } else {
            format!("Tmux: {} sessions | attach -t {}", count, latest)
        };
        (display, theme.success)
    } else if config.agent_backend == "tmux" {
        ("Tmux: no active sessions".to_string(), theme.muted)
    } else {
        (format!("Ollama: {}", ollama_label), ollama_color)
    };

    let (sandbox_label, sandbox_color) = if state.sandbox_active {
        (
            format!("Sandbox: active ({})", config.sandbox_image),
            theme.success,
        )
    } else if state.sandbox_enabled {
        (
            format!("Sandbox: degraded ({})", state.sandbox_status_label),
            theme.warning,
        )
    } else {
        (
            "Sandbox: disabled (config override)".to_string(),
            theme.error,
        )
    };

    // ─── Row: Ollama/Tmux | Sandbox ───
    // Co-located on one row so the Timing row below can use the full width.
    lines.push(Line::from(vec![
        Span::styled("  ", Style::default()),
        Span::styled(
            format!(
                "{:<width$}",
                ollama_left,
                width = half_width.saturating_sub(2)
            ),
            Style::default().fg(ollama_left_color),
        ),
        Span::styled(sandbox_label, Style::default().fg(sandbox_color)),
    ]));

    // ─── Row: Timing (full width, three labeled timers) ───
    // The stage timer was previously crammed onto the same row as the
    // Ollama/Tmux indicator on the left half; on narrower terminals the
    // third (stage) timer wrapped or clipped and the user only saw two
    // timers. Giving Timing the full width keeps all three visible.
    {
        let mut timing_spans = vec![
            Span::styled("  Timing    ", Style::default().fg(theme.info)),
            Span::styled("session: ", Style::default().fg(theme.muted)),
            Span::styled(session_str.clone(), Style::default().fg(theme.text)),
            Span::styled("  ", Style::default()),
            Span::styled(task_label.clone(), Style::default().fg(theme.muted)),
            Span::styled(task_str.clone(), Style::default().fg(theme.text)),
        ];
        if let Some((stage_label, stage_str)) = stage_segments.as_ref() {
            timing_spans.push(Span::styled("  ", Style::default()));
            timing_spans.push(Span::styled(
                stage_label.clone(),
                Style::default().fg(theme.muted),
            ));
            timing_spans.push(Span::styled(stage_str.clone(), Style::default().fg(theme.text)));
        }
        lines.push(Line::from(timing_spans));
    }

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
                Style::default()
                    .fg(Color::Yellow)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme.muted)
            },
        ),
    ];
    if state.current_agent.is_some() {
        let spinner_chars = ['|', '/', '-', '\\'];
        let spinner = spinner_chars[state.tick_count % spinner_chars.len()];
        agent_spans.push(Span::styled(
            format!(
                "  {} {} events  {}",
                spinner, state.events_received, agent_str
            ),
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
                    Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(stats_block, area);
}

fn effective_stats_provider(
    config: &Config,
    state: &AppState,
    selected_idx: usize,
) -> ModelProvider {
    if state.dual_build.active {
        let model_label = state.dual_build.models[selected_idx].as_str();
        let provider_label = model_label.split_whitespace().next().unwrap_or(model_label);
        return Config::parse_provider(provider_label);
    }

    let mut display_config = config.clone();
    display_config.builder_models = state.builder_model_specs.clone();
    display_config.dual_selection = state.dual_selection.as_str().to_string();

    display_config
        .selected_pipeline_configs(&display_config.dual_selection)
        .into_iter()
        .next()
        .map(|selected| Config::parse_provider(&selected.builder_provider))
        .unwrap_or_else(|| Config::parse_provider(&config.builder_provider))
}

fn metrics_unavailable(provider: ModelProvider, input_tokens: u64) -> bool {
    if provider == ModelProvider::Claude {
        return false;
    }
    if input_tokens > 0 {
        return false;
    }
    true
}

fn ctx_pct_span(pct: Option<u8>, unavailable: bool, muted: Color) -> (String, Color) {
    if unavailable {
        return ("N/A".to_string(), muted);
    }

    match pct {
        Some(p) if p >= 90 => (format!("{}%", p), Color::Red),
        Some(p) if p >= 70 => (format!("{}%", p), Color::Yellow),
        Some(p) => (format!("{}%", p), Color::Green),
        None => ("--".to_string(), Color::DarkGray),
    }
}

fn format_compact_tokens(n: u64) -> String {
    if n >= 1_000_000 {
        format!("{:.1}M", n as f64 / 1_000_000.0)
    } else if n >= 1_000 {
        format!("{:.0}K", n as f64 / 1_000.0)
    } else {
        format!("{}", n)
    }
}

fn dual_comparison_line(state: &AppState) -> Option<String> {
    if !state.dual_build.active || state.dual_build.finished != [true, true] {
        return None;
    }

    let segments: Vec<String> = [0, 1]
        .into_iter()
        .map(|idx| {
            let model = state.dual_build.models[idx].as_str();
            let label = model.split_whitespace().next().unwrap_or(model);
            let provider = Config::parse_provider(label);
            if metrics_unavailable(provider, state.dual_build.input_tokens[idx]) {
                format!("{label}: N/A")
            } else {
                format!(
                    "{label}: ${:.2} ({}in/{}out)",
                    state.dual_build.cost_usd[idx],
                    format_compact_tokens(state.dual_build.input_tokens[idx]),
                    format_compact_tokens(state.dual_build.output_tokens[idx]),
                )
            }
        })
        .collect();

    Some(segments.join(" | "))
}

fn badge_color_for(badge: &str, theme: &crate::tui::theme::TuiTheme) -> Color {
    if badge.contains('\u{2717}') {
        theme.error
    } else if badge.contains('\u{26A0}') {
        theme.warning
    } else if badge.contains('\u{2713}') {
        theme.success
    } else {
        theme.muted
    }
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

#[cfg(test)]
mod tests {
    use super::*;
    use ratatui::backend::TestBackend;
    use ratatui::Terminal;
    use std::path::PathBuf;

    #[test]
    fn render_dashboard_stats_uses_selected_dual_pipeline_metrics() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.dual_build.active = true;
        state.dual_build.models = ["Claude".to_string(), "Codex".to_string()];
        state.dual_build.tab = 1;
        state.dual_build.cost_usd = [3.25, 1.50];
        state.dual_build.input_tokens = [12_000, 7_000];
        state.dual_build.output_tokens = [1_500, 500];
        state.dual_build.context_pcts = [
            [Some(40), Some(41), Some(42), Some(43), Some(44)],
            [Some(60), Some(61), Some(62), Some(66), Some(64)],
        ];
        state.session_cost_usd = 9.99;
        state.session_input_tokens = 90_000;
        state.session_output_tokens = 10_000;
        state.spid_context_pcts = [Some(10), Some(11), Some(22), Some(88), Some(33)];

        let rendered = render_stats_text(&state);

        assert!(rendered.contains("Cost [2: Codex]"));
        assert!(rendered.contains("$1.50 (7Kin / 500out)"));
        assert!(rendered.contains("Q:60%"));
        assert!(rendered.contains("R:61%"));
        assert!(rendered.contains("P:62%"));
        assert!(rendered.contains("B:66%"));
        assert!(rendered.contains("A:64%"));
        assert!(!rendered.contains("N/A (Codex)"));
        assert!(!rendered.contains("Q:10%"));
        assert!(!rendered.contains("R:11%"));
        assert!(!rendered.contains("P:22%"));
        assert!(!rendered.contains("B:88%"));
        assert!(!rendered.contains("A:33%"));
        assert!(!rendered.contains("$9.99 (90Kin / 10Kout)"));
    }

    #[test]
    fn render_dashboard_stats_uses_selected_claude_pipeline_context_in_dual_mode() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.dual_build.active = true;
        state.dual_build.models = ["Claude".to_string(), "Codex".to_string()];
        state.dual_build.tab = 0;
        state.dual_build.input_tokens = [8_000, 0];
        state.dual_build.context_pcts = [
            [Some(5), Some(15), Some(25), Some(35), Some(45)],
            [Some(50), Some(51), Some(61), Some(71), Some(81)],
        ];
        state.spid_context_pcts = [Some(90), Some(91), Some(92), Some(93), Some(94)];

        let rendered = render_stats_text(&state);

        assert!(rendered.contains("Q:5%"));
        assert!(rendered.contains("R:15%"));
        assert!(rendered.contains("P:25%"));
        assert!(rendered.contains("B:35%"));
        assert!(rendered.contains("A:45%"));
        assert!(!rendered.contains("90%"));
        assert!(!rendered.contains("91%"));
        assert!(!rendered.contains("92%"));
        assert!(!rendered.contains("93%"));
        assert!(!rendered.contains("94%"));
    }

    #[test]
    fn render_dashboard_stats_shows_dual_comparison_line_when_both_pipelines_finish() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.eval_report_cache = None;
        state.dual_build.active = true;
        state.dual_build.finished = [true, true];
        state.dual_build.models = ["Claude".to_string(), "Codex".to_string()];
        state.dual_build.cost_usd = [1.25, 2.50];
        state.dual_build.input_tokens = [1_000, 2_000];
        state.dual_build.output_tokens = [250, 400];

        let rendered = render_stats_text(&state);

        assert!(rendered.contains("Claude: $1.25 (1Kin/250out) | Codex: $2.50 (2Kin/400out)"));
        assert!(!rendered.contains("Ollama:"));
    }

    #[test]
    fn render_dashboard_stats_shows_na_for_selected_codex_pipeline_without_usage() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.builder_model_specs = vec!["claude:opus".to_string(), "codex:".to_string()];
        state.dual_selection = crate::app::DualSelection::Second;

        let rendered = render_stats_text(&state);

        assert!(rendered.contains("N/A (Codex)"));
        assert!(rendered.contains("Q:N/A"));
        assert!(rendered.contains("R:N/A"));
        assert!(rendered.contains("P:N/A"));
        assert!(rendered.contains("B:N/A"));
        assert!(rendered.contains("A:N/A"));
        assert!(!rendered.contains("$0.00 (0in / 0out)"));
    }

    #[test]
    fn render_dashboard_stats_shows_na_for_selected_codex_tab_without_usage() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.dual_build.active = true;
        state.dual_build.tab = 1;
        state.dual_build.models = ["Claude".to_string(), "Codex".to_string()];
        state.spid_context_pcts = [Some(10), Some(11), Some(22), Some(88), Some(33)];

        let rendered = render_stats_text(&state);

        assert!(rendered.contains("Cost [2: Codex]"));
        assert!(rendered.contains("N/A (Codex)"));
        assert!(rendered.contains("Q:N/A"));
        assert!(rendered.contains("R:N/A"));
        assert!(rendered.contains("P:N/A"));
        assert!(rendered.contains("B:N/A"));
        assert!(rendered.contains("A:N/A"));
        assert!(!rendered.contains("10%"));
        assert!(!rendered.contains("11%"));
        assert!(!rendered.contains("22%"));
        assert!(!rendered.contains("88%"));
        assert!(!rendered.contains("33%"));
    }

    #[test]
    fn render_dashboard_stats_shows_na_in_dual_comparison_line_for_codex_without_usage() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.eval_report_cache = None;
        state.dual_build.active = true;
        state.dual_build.finished = [true, true];
        state.dual_build.models = ["Claude".to_string(), "Codex".to_string()];
        state.dual_build.cost_usd = [1.25, 0.0];
        state.dual_build.input_tokens = [1_000, 0];
        state.dual_build.output_tokens = [250, 0];

        let rendered = render_stats_text(&state);

        assert!(rendered.contains("Claude: $1.25 (1Kin/250out)"));
        assert!(rendered.contains("Codex: N/A"));
        assert!(!rendered.contains("Codex: $0.00 (0in/0out)"));
    }

    #[test]
    fn render_dashboard_stats_omits_letters_for_disabled_pipeline_stages() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.spid_context_pcts = [Some(10), Some(20), Some(30), Some(40), Some(50)];
        let mut config = Config::default();
        // Disable Query and Audit -- meter should drop Q and A and only show R P B.
        for stage in &mut config.pipeline_stages {
            if stage.id == "query" || stage.id == "doubt" {
                stage.enabled = false;
            }
        }

        let rendered = render_stats_text_with_config(&state, &config);

        assert!(rendered.contains("R:20%"));
        assert!(rendered.contains("P:30%"));
        assert!(rendered.contains("B:40%"));
        assert!(!rendered.contains("Q:"));
        assert!(!rendered.contains("A:"));
    }

    #[test]
    fn render_dashboard_stats_default_config_renders_qrpba_letters_in_order() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.spid_context_pcts = [Some(11), Some(22), Some(33), Some(44), Some(55)];

        let rendered = render_stats_text(&state);

        let q = rendered.find("Q:11%").expect("Q letter present");
        let r = rendered.find("R:22%").expect("R letter present");
        let p = rendered.find("P:33%").expect("P letter present");
        let b = rendered.find("B:44%").expect("B letter present");
        let a = rendered.find("A:55%").expect("A letter present");
        assert!(q < r && r < p && p < b && b < a, "QRPBA ordering");
    }

    #[test]
    fn render_dashboard_stats_uses_custom_stage_context_by_stage_id() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.spid_context_pcts = [Some(11), Some(22), Some(33), Some(44), Some(55)];
        state.stage_context_pcts.insert("security".to_string(), 77);
        let mut config = Config::default();
        config
            .pipeline_stages
            .push(crate::config::PipelineStageConfig {
                id: "security".to_string(),
                label: "SECURITY".to_string(),
                enabled: true,
                prompt_override: None,
            });

        let rendered = render_stats_text_with_config(&state, &config);

        assert!(rendered.contains("B:44%"));
        assert!(rendered.contains(" S:77%"));
    }

    fn render_stats_text_tall(state: &AppState) -> String {
        let backend = TestBackend::new(180, 16);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_dashboard_stats(frame, frame.area(), state, &Config::default()))
            .expect("failed to draw stats");

        let buffer = terminal.backend().buffer();
        let area = *buffer.area();
        (0..area.height)
            .map(|y| {
                (0..area.width)
                    .map(|x| {
                        buffer
                            .cell((x, y))
                            .map(|cell| cell.symbol().to_string())
                            .unwrap_or_else(|| " ".to_string())
                    })
                    .collect::<Vec<_>>()
                    .join("")
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    #[test]
    fn timing_row_shows_three_labeled_timers_when_agent_active() {
        use chrono::Utc;
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.current_task = Some(crate::task::Task {
            id: "T1.1".into(),
            description: "x".into(),
            line_number: 0,
            completed: false,
            pipeline_progress: None,
        });
        state.task_start = Some(Utc::now() - chrono::Duration::seconds(699));
        state.current_agent = Some((AgentRole::Builder, Utc::now() - chrono::Duration::seconds(105)));

        let rendered = render_stats_text_tall(&state);

        assert!(rendered.contains("task T1.1:"), "rendered: {}", rendered);
        assert!(rendered.contains("stage BUILD:"), "rendered: {}", rendered);
        assert!(rendered.contains("session:"), "rendered: {}", rendered);
    }

    fn render_stats_text_at(width: u16, height: u16, state: &AppState) -> String {
        let backend = TestBackend::new(width, height);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_dashboard_stats(frame, frame.area(), state, &Config::default()))
            .expect("failed to draw stats");

        let buffer = terminal.backend().buffer();
        let area = *buffer.area();
        (0..area.height)
            .map(|y| {
                (0..area.width)
                    .map(|x| {
                        buffer
                            .cell((x, y))
                            .map(|cell| cell.symbol().to_string())
                            .unwrap_or_else(|| " ".to_string())
                    })
                    .collect::<Vec<_>>()
                    .join("")
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    #[test]
    fn timing_row_renders_third_stage_timer_on_narrow_terminal() {
        // Regression: the timing row used to share a line with the
        // Ollama/Tmux indicator on the left half. On terminals narrower
        // than ~150 cols the third (stage) timer wrapped or clipped and
        // disappeared. Verify it survives at 100 cols wide with the P+
        // role (the longest realistic stage label is around "stage RESEARCH:").
        use chrono::Utc;
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.current_task = Some(crate::task::Task {
            id: "T1.1".into(),
            description: "x".into(),
            line_number: 0,
            completed: false,
            pipeline_progress: None,
        });
        state.task_start = Some(Utc::now() - chrono::Duration::seconds(699));
        state.current_agent = Some((
            AgentRole::PlanReview,
            Utc::now() - chrono::Duration::seconds(235),
        ));

        let rendered = render_stats_text_at(100, 12, &state);

        assert!(rendered.contains("session:"), "rendered: {}", rendered);
        assert!(rendered.contains("task T1.1:"), "rendered: {}", rendered);
        assert!(rendered.contains("stage P+:"), "rendered: {}", rendered);
    }

    #[test]
    fn timing_row_omits_stage_segment_when_agent_is_none() {
        use chrono::Utc;
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.current_task = Some(crate::task::Task {
            id: "T1.1".into(),
            description: "x".into(),
            line_number: 0,
            completed: false,
            pipeline_progress: None,
        });
        state.task_start = Some(Utc::now() - chrono::Duration::seconds(699));
        state.current_agent = None;

        let rendered = render_stats_text_tall(&state);

        assert!(rendered.contains("task T1.1:"), "rendered: {}", rendered);
        assert!(rendered.contains("session:"), "rendered: {}", rendered);
        assert!(!rendered.contains("stage "), "should not contain 'stage '. rendered: {}", rendered);
    }

    #[test]
    fn timing_row_uses_generic_task_label_when_no_current_task() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.current_task = None;
        state.current_agent = None;

        let rendered = render_stats_text_tall(&state);

        assert!(rendered.contains("task: "), "rendered: {}", rendered);
        assert!(!rendered.contains("task T"), "rendered: {}", rendered);
    }

    fn render_stats_text(state: &AppState) -> String {
        render_stats_text_with_config(state, &Config::default())
    }

    fn render_stats_text_with_config(state: &AppState, config: &Config) -> String {
        let backend = TestBackend::new(160, 6);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_dashboard_stats(frame, frame.area(), state, config))
            .expect("failed to draw stats");

        let buffer = terminal.backend().buffer();
        let area = *buffer.area();
        (0..area.height)
            .map(|y| {
                (0..area.width)
                    .map(|x| {
                        buffer
                            .cell((x, y))
                            .map(|cell| cell.symbol().to_string())
                            .unwrap_or_else(|| " ".to_string())
                    })
                    .collect::<Vec<_>>()
                    .join("")
            })
            .collect::<Vec<_>>()
            .join("\n")
    }
}

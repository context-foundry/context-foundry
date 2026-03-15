use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
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

    let title = format!(
        " Learned Patterns ({}) | {} ",
        all_patterns.len(),
        patterns_dir.display()
    );

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

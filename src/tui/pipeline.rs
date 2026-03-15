use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

use crate::agent::AgentRole;
use crate::app::AppState;
use crate::config::Config;
use crate::utils::truncate_str;

pub(super) fn render_pipeline_map(frame: &mut Frame, area: Rect, state: &AppState, config: &Config) {
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
                let display = Config::display_provider_model(provider, model);
                truncate_str(&display, 14).to_string()
            } else {
                String::new()
            }
        } else {
            "GitHub".to_string()
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

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

    let pipe_color = Color::Rgb(227, 115, 75); // Claude Code orange (#E3734B)
    let box_width = 14usize;

    let roles = config.role_configs();

    // ─── Connected pipeline stages (left side) ─────────────
    struct StageInfo {
        label: &'static str,
        model_label: String,
        border_color: Color,
        text_style: Style,
    }

    // Map active role to connected stage index
    let active_connected = active_role.as_ref().and_then(|role| match role {
        AgentRole::Scout => Some(0),
        AgentRole::Planner => Some(1),
        AgentRole::Builder => Some(2),
        AgentRole::Reviewer | AgentRole::Fixer => Some(3),
        _ => None,
    });

    // Find verify model from role_configs (Reviewer provider/model)
    let verify_model = roles.iter()
        .find(|(name, _, _)| name.contains("erif") || name.contains("eview") || name.contains("ix"))
        .map(|(_, provider, model)| Config::display_provider_model(provider, model))
        .unwrap_or_default();

    let connected: Vec<StageInfo> = [
        ("SCOUT", Some(0)),
        ("PLAN", Some(1)),
        ("IMPLEMENT", Some(2)),
        ("DOUBT", None),    // the doubt loop -- uses verify_model
        ("SHIP", None),     // ship it Ralph
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
        } else if *label == "DOUBT" {
            truncate_str(&verify_model, 14).to_string()
        } else if *label == "SHIP" {
            "GitHub".to_string()
        } else {
            String::new()
        };

        let (border_color, text_style) = match active_connected {
            Some(ai) if i == ai => (
                pipe_color,
                Style::default().fg(Color::White).add_modifier(Modifier::BOLD),
            ),
            Some(ai) if i < ai => (Color::Green, Style::default().fg(Color::Green)),
            _ => (Color::DarkGray, Style::default().fg(Color::DarkGray)),
        };

        StageInfo { label, model_label, border_color, text_style }
    })
    .collect();

    // ─── Disconnected stages (right side) ───────────────────
    let discovery_active = active_role.as_ref() == Some(&AgentRole::Discovery);
    let discovery_used = state.is_discovering || state.discovery_round > 0;
    let patterns_used = state.session_patterns_learned > 0;

    // Find Discovery and Patterns model labels from role_configs
    let discovery_model = roles.iter()
        .find(|(name, _, _)| *name == "Discovery")
        .map(|(_, provider, model)| Config::display_provider_model(provider, model))
        .unwrap_or_default();
    let patterns_model = roles.iter()
        .find(|(name, _, _)| *name == "Patterns")
        .map(|(_, provider, model)| Config::display_provider_model(provider, model))
        .unwrap_or_default();

    let disconnected: Vec<StageInfo> = vec![
        StageInfo {
            label: "SAMSARA",
            model_label: truncate_str(&discovery_model, 14).to_string(),
            border_color: if discovery_active { pipe_color } else if discovery_used { Color::Green } else { Color::DarkGray },
            text_style: if discovery_active {
                Style::default().fg(Color::White).add_modifier(Modifier::BOLD)
            } else if discovery_used {
                Style::default().fg(Color::Green)
            } else {
                Style::default().fg(Color::DarkGray)
            },
        },
        StageInfo {
            label: "PATTERNS",
            model_label: truncate_str(&patterns_model, 14).to_string(),
            border_color: if patterns_used { Color::Green } else { Color::DarkGray },
            text_style: if patterns_used {
                Style::default().fg(Color::Green)
            } else {
                Style::default().fg(Color::DarkGray)
            },
        },
    ];

    // ─── Render boxes ───────────────────────────────────────
    // Helper: render one box's row segments
    fn box_top(s: &mut Vec<Span>, width: usize, color: Color) {
        s.push(Span::styled(
            format!("\u{256d}{}\u{256e}", "\u{2500}".repeat(width)),
            Style::default().fg(color),
        ));
    }
    fn box_mid(s: &mut Vec<Span>, width: usize, label: &str, style: Style, color: Color) {
        let pad_total = width.saturating_sub(label.len());
        let left = pad_total / 2;
        let right = pad_total - left;
        s.push(Span::styled("\u{2502}", Style::default().fg(color)));
        s.push(Span::styled(
            format!("{}{}{}", " ".repeat(left), label, " ".repeat(right)),
            style,
        ));
        s.push(Span::styled("\u{2502}", Style::default().fg(color)));
    }
    fn box_model(s: &mut Vec<Span>, width: usize, model: &str, color: Color) {
        let pad_total = width.saturating_sub(model.len());
        let left = pad_total / 2;
        let right = pad_total - left;
        s.push(Span::styled("\u{2502}", Style::default().fg(color)));
        s.push(Span::styled(
            format!("{}{}{}", " ".repeat(left), model, " ".repeat(right)),
            Style::default().fg(Color::DarkGray),
        ));
        s.push(Span::styled("\u{2502}", Style::default().fg(color)));
    }
    fn box_bot(s: &mut Vec<Span>, width: usize, color: Color) {
        s.push(Span::styled(
            format!("\u{2570}{}\u{256f}", "\u{2500}".repeat(width)),
            Style::default().fg(color),
        ));
    }

    // Build each line across all boxes
    let mut top_spans = vec![Span::raw("  ")];
    let mut mid_spans = vec![Span::raw("  ")];
    let mut model_spans = vec![Span::raw("  ")];
    let mut bot_spans = vec![Span::raw("  ")];

    // Connected stages with arrows
    for (i, stage) in connected.iter().enumerate() {
        box_top(&mut top_spans, box_width, stage.border_color);
        box_mid(&mut mid_spans, box_width, stage.label, stage.text_style, stage.border_color);
        box_model(&mut model_spans, box_width, &stage.model_label, stage.border_color);
        box_bot(&mut bot_spans, box_width, stage.border_color);

        if i < connected.len() - 1 {
            top_spans.push(Span::raw("    "));
            mid_spans.push(Span::styled(
                "\u{2500}\u{2500}\u{25b6}\u{2500}",
                Style::default().fg(pipe_color),
            ));
            model_spans.push(Span::raw("    "));
            bot_spans.push(Span::raw("    "));
        }
    }

    // Gap between connected and disconnected
    top_spans.push(Span::raw("        "));
    mid_spans.push(Span::raw("        "));
    model_spans.push(Span::raw("        "));
    bot_spans.push(Span::raw("        "));

    // Disconnected stages (no arrows)
    for (i, stage) in disconnected.iter().enumerate() {
        box_top(&mut top_spans, box_width, stage.border_color);
        box_mid(&mut mid_spans, box_width, stage.label, stage.text_style, stage.border_color);
        box_model(&mut model_spans, box_width, &stage.model_label, stage.border_color);
        box_bot(&mut bot_spans, box_width, stage.border_color);

        if i < disconnected.len() - 1 {
            top_spans.push(Span::raw("  "));
            mid_spans.push(Span::raw("  "));
            model_spans.push(Span::raw("  "));
            bot_spans.push(Span::raw("  "));
        }
    }

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

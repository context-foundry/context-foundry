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

fn effective_pipeline_configs(config: &Config, state: &AppState) -> Vec<Config> {
    let mut display_config = config.clone();
    display_config.builder_models = state.builder_model_specs.clone();
    display_config.dual_selection = state.dual_selection.as_str().to_string();
    display_config.selected_pipeline_configs(&display_config.dual_selection)
}

fn join_stage_labels<I>(labels: I) -> String
where
    I: IntoIterator<Item = String>,
{
    let mut unique = Vec::new();
    for label in labels {
        if !label.is_empty() && !unique.contains(&label) {
            unique.push(label);
        }
    }
    unique.join(" + ")
}

fn stage_model_label(configs: &[Config], stage: &str) -> String {
    join_stage_labels(configs.iter().map(|config| match stage {
        "SCOUT" => Config::display_provider_model(&config.scout_provider, &config.scout_model),
        "PLAN" => Config::display_provider_model(&config.planner_provider, &config.planner_model),
        "IMPLEMENT" => {
            Config::display_provider_model(&config.builder_provider, &config.builder_model)
        }
        "DOUBT" => {
            Config::display_provider_model(&config.reviewer_provider, &config.reviewer_model)
        }
        "DISCOVER" => {
            Config::display_provider_model(&config.discovery_provider, &config.discovery_model)
        }
        _ => String::new(),
    }))
}

pub(super) fn render_pipeline_map(
    frame: &mut Frame,
    area: Rect,
    state: &AppState,
    config: &Config,
) {
    let theme = &state.tui_theme;
    let active_role = if state.dual_build.active {
        state.dual_build.stages[state.dual_build.tab].clone()
    } else {
        state.current_agent.as_ref().map(|(role, _)| role.clone())
    };

    let pipe_color = theme.accent;
    let box_width = 14usize;

    let pipeline_configs = effective_pipeline_configs(config, state);

    // ─── Connected pipeline stages (left side) ─────────────
    struct StageInfo {
        label: &'static str,
        model_label: String,
        kind_label: &'static str,
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

    let connected: Vec<StageInfo> = [
        ("SCOUT", "scout-report"),
        ("PLAN", "current-plan"),
        ("IMPLEMENT", "build-claims"),
        ("DOUBT", "fresh context"),
        ("SHIP", "git + pr"),
    ]
    .iter()
    .enumerate()
    .map(|(i, (label, kind))| {
        let model_label = if *label == "SHIP" {
            "GitHub".to_string()
        } else {
            truncate_str(&stage_model_label(&pipeline_configs, label), 14).to_string()
        };

        let (border_color, text_style) = match active_connected {
            Some(ai) if i == ai => (
                pipe_color,
                Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
            ),
            Some(ai) if i < ai => (Color::Green, Style::default().fg(Color::Green)),
            _ => (theme.muted, Style::default().fg(theme.muted)),
        };

        StageInfo {
            label,
            model_label,
            kind_label: kind,
            border_color,
            text_style,
        }
    })
    .collect();

    // ─── Disconnected stages (right side) ───────────────────
    let discovery_active = active_role.as_ref() == Some(&AgentRole::Discovery);
    let discovery_used = state.is_discovering || state.discovery_round > 0;
    let patterns_used = state.session_patterns_learned > 0;

    let discovery_model = stage_model_label(&pipeline_configs, "DISCOVER");
    let patterns_model = config
        .role_configs()
        .iter()
        .find(|(name, _, _)| *name == "Patterns")
        .map(|(_, provider, model)| Config::display_provider_model(provider, model))
        .unwrap_or_default();

    let disconnected: Vec<StageInfo> = vec![
        StageInfo {
            label: "DISCOVER",
            model_label: truncate_str(&discovery_model, 14).to_string(),
            kind_label: "TASKS.md",
            border_color: if state.run_mode == "sprint" || state.run_mode == "review" {
                theme.muted
            } else if discovery_active {
                pipe_color
            } else if discovery_used {
                Color::Green
            } else {
                theme.muted
            },
            text_style: if state.run_mode == "sprint" || state.run_mode == "review" {
                Style::default().fg(theme.muted)
            } else if discovery_active {
                Style::default().fg(theme.text).add_modifier(Modifier::BOLD)
            } else if discovery_used {
                Style::default().fg(Color::Green)
            } else {
                Style::default().fg(theme.muted)
            },
        },
        StageInfo {
            label: "PATTERNS",
            model_label: truncate_str(&patterns_model, 14).to_string(),
            kind_label: "~/.foundry/",
            border_color: if patterns_used {
                Color::Green
            } else {
                theme.muted
            },
            text_style: if patterns_used {
                Style::default().fg(Color::Green)
            } else {
                Style::default().fg(theme.muted)
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
    fn box_model(s: &mut Vec<Span>, width: usize, model: &str, color: Color, muted: Color) {
        let pad_total = width.saturating_sub(model.len());
        let left = pad_total / 2;
        let right = pad_total - left;
        s.push(Span::styled("\u{2502}", Style::default().fg(color)));
        s.push(Span::styled(
            format!("{}{}{}", " ".repeat(left), model, " ".repeat(right)),
            Style::default().fg(muted),
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
    let mut kind_spans = vec![Span::raw("  ")];
    let mut bot_spans = vec![Span::raw("  ")];

    // Connected stages with arrows
    for (i, stage) in connected.iter().enumerate() {
        box_top(&mut top_spans, box_width, stage.border_color);
        box_mid(
            &mut mid_spans,
            box_width,
            stage.label,
            stage.text_style,
            stage.border_color,
        );
        box_model(
            &mut model_spans,
            box_width,
            &stage.model_label,
            stage.border_color,
            theme.muted,
        );
        box_model(
            &mut kind_spans,
            box_width,
            stage.kind_label,
            stage.border_color,
            theme.muted,
        );
        box_bot(&mut bot_spans, box_width, stage.border_color);

        if i < connected.len() - 1 {
            top_spans.push(Span::raw("    "));
            mid_spans.push(Span::styled(
                "\u{2500}\u{2500}\u{25b6}\u{2500}",
                Style::default().fg(pipe_color),
            ));
            model_spans.push(Span::raw("    "));
            kind_spans.push(Span::raw("    "));
            bot_spans.push(Span::raw("    "));
        }
    }

    // Gap between connected and disconnected
    top_spans.push(Span::raw("        "));
    mid_spans.push(Span::raw("        "));
    model_spans.push(Span::raw("        "));
    kind_spans.push(Span::raw("        "));
    bot_spans.push(Span::raw("        "));

    // Disconnected stages (no arrows)
    for (i, stage) in disconnected.iter().enumerate() {
        box_top(&mut top_spans, box_width, stage.border_color);
        box_mid(
            &mut mid_spans,
            box_width,
            stage.label,
            stage.text_style,
            stage.border_color,
        );
        box_model(
            &mut model_spans,
            box_width,
            &stage.model_label,
            stage.border_color,
            theme.muted,
        );
        box_model(
            &mut kind_spans,
            box_width,
            stage.kind_label,
            stage.border_color,
            theme.muted,
        );
        box_bot(&mut bot_spans, box_width, stage.border_color);

        if i < disconnected.len() - 1 {
            top_spans.push(Span::raw("  "));
            mid_spans.push(Span::raw("  "));
            model_spans.push(Span::raw("  "));
            kind_spans.push(Span::raw("  "));
            bot_spans.push(Span::raw("  "));
        }
    }

    let lines = vec![
        Line::from(""),
        Line::from(top_spans),
        Line::from(mid_spans),
        Line::from(model_spans),
        Line::from(kind_spans),
        Line::from(bot_spans),
    ];

    let pipeline = Paragraph::new(lines).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(theme.border))
            .title(Span::styled(
                " Pipeline ",
                Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(pipeline, area);
}

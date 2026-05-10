use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

/// Which box was clicked in the pipeline map.
#[derive(Debug, Clone)]
pub enum PipelineClick {
    /// Index into the ordered list of enabled connected stages.
    ConnectedStage(usize),
    Ship,
    Discover,
    Patterns,
}

/// Hit-test the pipeline map. `area` is the full pipeline area rect (Constraint::Length(6)).
/// `n_connected` is the number of enabled connected stages currently rendered.
/// Returns None if the click is outside all boxes.
pub fn pipeline_click(area: Rect, col: u16, row: u16, n_connected: usize) -> Option<PipelineClick> {
    // Box rows: area.y+0 (tops) through area.y+4 (bottoms).
    // area.y+5 is the Block bottom border.
    if row < area.y || row > area.y + 4 {
        return None;
    }
    // Box pitch: 16 chars wide, 20-char pitch (16 + 4-char arrow) for connected stages.
    // Leading "  " (2 cols) before first box.
    let box_w: u16 = 16;
    let pitch: u16 = 20; // box_w + arrow
    let x0 = area.x + 2; // x of first connected box's left border

    for i in 0..n_connected {
        let bx = x0 + i as u16 * pitch;
        if col >= bx && col < bx + box_w {
            return Some(PipelineClick::ConnectedStage(i));
        }
    }

    // Disconnected section starts after connected boxes + 8-char gap.
    // connected section width (no trailing arrow): n * box_w + (n-1) * 4
    let connected_w = if n_connected == 0 {
        0
    } else {
        n_connected as u16 * box_w + (n_connected as u16 - 1) * 4
    };
    let disc_x0 = x0 + connected_w + 8; // 8-char gap
    let disc_pitch: u16 = 18; // box_w + 2-char gap
    let disc_stages = [
        PipelineClick::Ship,
        PipelineClick::Discover,
        PipelineClick::Patterns,
    ];
    for (j, target) in disc_stages.into_iter().enumerate() {
        let bx = disc_x0 + j as u16 * disc_pitch;
        if col >= bx && col < bx + box_w {
            return Some(target);
        }
    }

    None
}

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

fn stage_model_label(configs: &[Config], stage_id: &str) -> String {
    join_stage_labels(configs.iter().map(|config| {
        let (prov, model) = config.active_routing_for_stage(stage_id);
        Config::display_provider_model(&prov, &model)
    }))
}

fn stage_kind_label(stage_id: &str) -> &'static str {
    match stage_id {
        "scout" => "scout-report",
        "query" => "prompt",
        "research" => "research",
        "plan" => "current-plan",
        "implement" => "build-claims",
        "doubt" => "fresh context",
        "discover" => "TASKS.md",
        _ => "custom",
    }
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
    let active_stage_id = if state.dual_build.active {
        state.dual_build.stage_ids[state.dual_build.tab]
            .clone()
            .or_else(|| active_role.as_ref().map(|role| role.slug().to_string()))
    } else {
        state
            .current_agent_stage_id
            .clone()
            .or_else(|| active_role.as_ref().map(|role| role.slug().to_string()))
    };

    let pipe_color = theme.accent;
    let box_width = 14usize;

    let pipeline_configs = effective_pipeline_configs(config, state);

    // ─── Connected pipeline stages (left side) ─────────────
    struct StageInfo {
        label: String,
        model_label: String,
        kind_label: String,
        border_color: Color,
        text_style: Style,
        stage_id: Option<String>,
    }

    // Filter to enabled stages; order follows config.pipeline_stages.
    let enabled_stages: Vec<&crate::config::PipelineStageConfig> = config
        .pipeline_stages
        .iter()
        .filter(|s| s.enabled)
        .collect();

    // First pass: build connected vec with default (muted) styling. Splice
    // virtual COACH (front) and P+ (after PLAN) stages when configured.
    let mut connected: Vec<StageInfo> = Vec::new();

    if config.run_mode == "coach" {
        let model_label =
            truncate_str(&stage_model_label(&pipeline_configs, "coach"), 14).to_string();
        connected.push(StageInfo {
            label: "COACH".to_string(),
            model_label,
            kind_label: "intake-brief".to_string(),
            border_color: theme.muted,
            text_style: Style::default().fg(theme.muted),
            stage_id: Some("coach".to_string()),
        });
    }

    for stage_cfg in enabled_stages.iter() {
        let model_label =
            truncate_str(&stage_model_label(&pipeline_configs, &stage_cfg.id), 14).to_string();
        let kind_label = stage_kind_label(&stage_cfg.id).to_string();

        connected.push(StageInfo {
            label: stage_cfg.label.clone(),
            model_label,
            kind_label,
            border_color: theme.muted,
            text_style: Style::default().fg(theme.muted),
            stage_id: Some(stage_cfg.id.clone()),
        });

        // Render P+ unconditionally between PLAN and BUILD. The
        // `config.plan_review_enabled` flag does not actually gate
        // when P+ fires at runtime, so gating only the diagram on it
        // produced a latent rendering bug where P+ ran but never
        // appeared in the pipeline view. The gate is retained as a
        // config option (used by the build pipeline) but does not
        // suppress the box.
        if stage_cfg.id == "plan" {
            let pr_model =
                truncate_str(&stage_model_label(&pipeline_configs, "plan-review"), 14).to_string();
            connected.push(StageInfo {
                label: "P+".to_string(),
                model_label: pr_model,
                kind_label: "plan-review".to_string(),
                border_color: theme.muted,
                text_style: Style::default().fg(theme.muted),
                stage_id: Some("plan-review".to_string()),
            });
        }
    }

    // Second pass: locate active stage in the assembled connected vec, then
    // recompute border_color/text_style with the same three-arm rule used
    // before. Active stage resolution is by stage_id so virtual stages match.
    let active_connected: Option<usize> = active_stage_id
        .as_deref()
        .and_then(|sid| connected.iter().position(|info| info.stage_id.as_deref() == Some(sid)));

    for (i, info) in connected.iter_mut().enumerate() {
        let (border_color, text_style) = match active_connected {
            Some(ai) if i == ai => (
                pipe_color,
                Style::default().fg(theme.text).add_modifier(Modifier::BOLD),
            ),
            Some(ai) if i < ai => (Color::Green, Style::default().fg(Color::Green)),
            _ => (theme.muted, Style::default().fg(theme.muted)),
        };
        info.border_color = border_color;
        info.text_style = text_style;
    }

    // ─── Disconnected stages (right side) ───────────────────
    let discovery_active = active_role.as_ref() == Some(&AgentRole::Discovery);
    let discovery_used = state.is_discovering || state.discovery_round > 0;
    let patterns_used = state.session_patterns_learned > 0;

    let discovery_model = stage_model_label(&pipeline_configs, "discovery");
    let patterns_model = config
        .role_configs()
        .iter()
        .find(|(name, _, _)| *name == "Patterns")
        .map(|(_, provider, model)| Config::display_provider_model(provider, model))
        .unwrap_or_default();

    let disconnected: Vec<StageInfo> = vec![
        StageInfo {
            label: "SHIP".to_string(),
            model_label: "GitHub".to_string(),
            kind_label: "git + pr".to_string(),
            border_color: if state.ship_active {
                Color::Green
            } else {
                theme.muted
            },
            text_style: if state.ship_active {
                Style::default()
                    .fg(Color::Green)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(theme.muted)
            },
            stage_id: None,
        },
        StageInfo {
            label: "DISCOVER".to_string(),
            model_label: truncate_str(&discovery_model, 14).to_string(),
            kind_label: "TASKS.md".to_string(),
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
            stage_id: None,
        },
        StageInfo {
            label: "PATTERNS".to_string(),
            model_label: truncate_str(&patterns_model, 14).to_string(),
            kind_label: "~/.foundry/".to_string(),
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
            stage_id: None,
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
            &stage.label,
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
            &stage.kind_label,
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
    if connected.len() <= 7 {
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
                &stage.label,
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
                &stage.kind_label,
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
    }

    let lines = vec![
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
    // Clear the area first to prevent stale glyphs from a previous, wider render bleeding in.
    frame.render_widget(ratatui::widgets::Clear, area);
    frame.render_widget(pipeline, area);
}

#[cfg(test)]
mod tests {
    use super::*;
    use ratatui::backend::TestBackend;
    use ratatui::Terminal;
    use std::path::PathBuf;

    fn render_pipeline_text(state: &AppState, config: &Config) -> String {
        let backend = TestBackend::new(220, 8);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_pipeline_map(frame, frame.area(), state, config))
            .expect("failed to draw pipeline");

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
    fn pipeline_renders_six_boxes_for_default_config() {
        // P+ is rendered unconditionally between PLAN and BUILD because
        // plan-review can run regardless of `config.plan_review_enabled`.
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config::default();
        let rendered = render_pipeline_text(&state, &config);

        assert!(rendered.contains("QUERY"), "rendered: {}", rendered);
        assert!(rendered.contains("RESEARCH"), "rendered: {}", rendered);
        assert!(rendered.contains("PLAN"), "rendered: {}", rendered);
        assert!(rendered.contains("P+"), "rendered: {}", rendered);
        assert!(rendered.contains("BUILD"), "rendered: {}", rendered);
        assert!(rendered.contains("AUDIT"), "rendered: {}", rendered);
        assert!(!rendered.contains("COACH"), "rendered: {}", rendered);
    }

    #[test]
    fn pipeline_renders_p_plus_even_when_plan_review_disabled() {
        // Regression: previously P+ was gated on `plan_review_enabled`,
        // but the runtime gate is broken (P+ fires anyway). The diagram
        // must reflect what users actually experience.
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config {
            plan_review_enabled: false,
            ..Config::default()
        };
        let rendered = render_pipeline_text(&state, &config);

        let plan_off = rendered.find("PLAN").expect("PLAN present");
        let pplus_off = rendered.find("P+").expect("P+ present");
        let build_off = rendered.find("BUILD").expect("BUILD present");
        assert!(
            plan_off < pplus_off && pplus_off < build_off,
            "expected PLAN < P+ < BUILD; rendered: {}",
            rendered
        );
    }

    #[test]
    fn pipeline_renders_coach_at_front_when_run_mode_coach() {
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config {
            run_mode: "coach".into(),
            ..Config::default()
        };
        let rendered = render_pipeline_text(&state, &config);

        let coach_off = rendered.find("COACH").expect("COACH present");
        let query_off = rendered.find("QUERY").expect("QUERY present");
        assert!(
            coach_off < query_off,
            "COACH should come before QUERY. rendered: {}",
            rendered
        );
    }

    #[test]
    fn pipeline_renders_p_plus_between_plan_and_build_when_plan_review_enabled() {
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config {
            plan_review_enabled: true,
            ..Config::default()
        };
        let rendered = render_pipeline_text(&state, &config);

        let plan_off = rendered.find("PLAN").expect("PLAN present");
        let pplus_off = rendered.find("P+").expect("P+ present");
        let build_off = rendered.find("BUILD").expect("BUILD present");
        assert!(
            plan_off < pplus_off && pplus_off < build_off,
            "expected PLAN < P+ < BUILD; rendered: {}",
            rendered
        );
    }

    #[test]
    fn pipeline_renders_active_stage_with_active_color_for_p_plus() {
        use chrono::Utc;
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.current_agent = Some((AgentRole::PlanReview, Utc::now()));
        state.current_agent_stage_id = Some("plan-review".into());
        let config = Config {
            plan_review_enabled: true,
            ..Config::default()
        };

        let backend = TestBackend::new(220, 8);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_pipeline_map(frame, frame.area(), &state, &config))
            .expect("failed to draw pipeline");

        let buffer = terminal.backend().buffer();
        let area = *buffer.area();
        // Find the label row containing "P+" by scanning all rows column by column.
        let accent = state.tui_theme.accent;
        let mut label_y_opt: Option<u16> = None;
        let mut p_col_opt: Option<u16> = None;
        for y in area.y..(area.y + area.height) {
            for x in 0..area.width.saturating_sub(1) {
                let s0 = buffer
                    .cell((x, y))
                    .map(|c| c.symbol().to_string())
                    .unwrap_or_default();
                let s1 = buffer
                    .cell((x + 1, y))
                    .map(|c| c.symbol().to_string())
                    .unwrap_or_default();
                if s0 == "P" && s1 == "+" {
                    label_y_opt = Some(y);
                    p_col_opt = Some(x);
                    break;
                }
            }
            if label_y_opt.is_some() {
                break;
            }
        }
        let label_y = label_y_opt.expect("P+ label rendered somewhere");
        let p_idx = p_col_opt.unwrap() as usize;
        // Search neighborhood of the P+ box for accent-colored cells (border
        // verticals on label_y, border top corners on label_y-1).
        let mut found_active = false;
        let xs: Vec<u16> = (p_idx.saturating_sub(2) as u16
            ..((p_idx as u16).saturating_add(16)).min(area.width))
            .collect();
        for y_off in 0..3i32 {
            let y_signed = label_y as i32 + y_off - 1;
            if y_signed < area.y as i32 || y_signed >= (area.y + area.height) as i32 {
                continue;
            }
            let y = y_signed as u16;
            for &x in &xs {
                if let Some(cell) = buffer.cell((x, y)) {
                    if cell.style().fg == Some(accent) {
                        found_active = true;
                        break;
                    }
                }
            }
            if found_active {
                break;
            }
        }
        assert!(
            found_active,
            "Expected P+ box (col={}, y={}) to use active color (accent={:?})",
            p_idx, label_y, accent
        );
    }

    #[test]
    fn pipeline_drops_disconnected_trio_when_seven_or_more_connected() {
        let state = AppState::new(PathBuf::from(".buildloop"));
        let mut config = Config {
            run_mode: "coach".into(),
            plan_review_enabled: true,
            ..Config::default()
        };
        config.pipeline_stages.push(crate::config::PipelineStageConfig {
            id: "security".to_string(),
            label: "SECURITY".to_string(),
            enabled: true,
            prompt_override: None,
        });
        config.pipeline_stages.push(crate::config::PipelineStageConfig {
            id: "lint".to_string(),
            label: "LINT".to_string(),
            enabled: true,
            prompt_override: None,
        });

        let rendered = render_pipeline_text(&state, &config);
        assert!(rendered.contains("COACH"), "rendered: {}", rendered);
        assert!(rendered.contains("P+"), "rendered: {}", rendered);
        assert!(!rendered.contains("SHIP"), "rendered: {}", rendered);
        assert!(!rendered.contains("DISCOVER"), "rendered: {}", rendered);
        assert!(!rendered.contains("PATTERNS"), "rendered: {}", rendered);
    }
}

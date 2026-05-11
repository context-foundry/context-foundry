use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

use crate::tui::theme::{TILE_HEIGHT, TILE_INNER_W};

/// Which box was clicked in the pipeline map.
#[derive(Debug, Clone)]
pub enum PipelineClick {
    /// Index into the ordered list of enabled connected stages.
    ConnectedStage(usize),
    Ship,
    Discover,
    Patterns,
}

/// Tile pitch in columns: 6-wide tile (TILE_INNER_W + 2 borders) + 2-cell gap/arrow = 8.
const TILE_W: u16 = TILE_INNER_W + 2;
const TILE_PITCH: u16 = TILE_W + 2;
/// Max connected tiles rendered on row 1.
const ROW1_MAX_TILES: usize = 5;

/// Hit-test the pipeline map. `area` is the full pipeline area rect
/// (Constraint::Length(9)). `n_connected` is the number of enabled connected
/// stages currently rendered. Returns None if the click is outside all tiles.
pub fn pipeline_click(area: Rect, col: u16, row: u16, n_connected: usize) -> Option<PipelineClick> {
    let row1_y0 = area.y + 1;
    let row2_y0 = row1_y0 + TILE_HEIGHT + 1;

    let in_row1 = row >= row1_y0 && row < row1_y0 + TILE_HEIGHT;
    let in_row2 = row >= row2_y0 && row < row2_y0 + TILE_HEIGHT;
    if !in_row1 && !in_row2 {
        return None;
    }

    let n_row1 = n_connected.min(ROW1_MAX_TILES);
    let n_row2_connected = n_connected.saturating_sub(ROW1_MAX_TILES);
    let x0 = area.x + 2;

    if in_row1 {
        for i in 0..n_row1 {
            let bx = x0 + (i as u16) * TILE_PITCH;
            if col >= bx && col < bx + TILE_W {
                return Some(PipelineClick::ConnectedStage(i));
            }
        }
    }

    if in_row2 {
        // Connected overflow on row 2 (left side).
        for j in 0..n_row2_connected {
            let bx = x0 + (j as u16) * TILE_PITCH;
            if col >= bx && col < bx + TILE_W {
                return Some(PipelineClick::ConnectedStage(ROW1_MAX_TILES + j));
            }
        }
        // Disconnected trio on row 2 (right side, separated by 8-cell gap).
        let disc_x0 = x0 + (n_row2_connected as u16) * TILE_PITCH + 4;
        let disc_stages = [
            PipelineClick::Ship,
            PipelineClick::Discover,
            PipelineClick::Patterns,
        ];
        for (j, target) in disc_stages.into_iter().enumerate() {
            let bx = disc_x0 + (j as u16) * TILE_PITCH;
            if col >= bx && col < bx + TILE_W {
                return Some(target);
            }
        }
    }

    None
}

use crate::agent::AgentRole;
use crate::app::AppState;
use crate::config::Config;

fn effective_pipeline_configs(config: &Config, state: &AppState) -> Vec<Config> {
    let mut display_config = config.clone();
    display_config.builder_models = state.builder_model_specs.clone();
    display_config.dual_selection = state.dual_selection.as_str().to_string();
    display_config.selected_pipeline_configs(&display_config.dual_selection)
}

/// Map a full stage label (e.g. "QUERY") to a short tile abbreviation.
fn tile_label(label: &str) -> String {
    match label {
        "QUERY" => "Q".to_string(),
        "RESEARCH" => "R".to_string(),
        "PLAN" => "P".to_string(),
        "P+" => "P+".to_string(),
        "BUILD" => "B".to_string(),
        "AUDIT" => "A".to_string(),
        "COACH" => "C".to_string(),
        "SHIP" => "SH".to_string(),
        "DISCOVER" => "DI".to_string(),
        "DISCOVERY" => "DI".to_string(),
        "SKILLS" => "SK".to_string(),
        "PATTERNS" => "SK".to_string(),
        other => other
            .chars()
            .take(2)
            .collect::<String>()
            .to_ascii_uppercase(),
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
    let _pipeline_configs = effective_pipeline_configs(config, state);

    struct StageInfo {
        label: String,
        border_color: Color,
        text_style: Style,
        stage_id: Option<String>,
    }

    let enabled_stages: Vec<&crate::config::PipelineStageConfig> = config
        .pipeline_stages
        .iter()
        .filter(|s| s.enabled)
        .collect();

    let mut connected: Vec<StageInfo> = Vec::new();

    if config.run_mode == "coach" {
        connected.push(StageInfo {
            label: "COACH".to_string(),
            border_color: theme.muted,
            text_style: Style::default().fg(theme.muted),
            stage_id: Some("coach".to_string()),
        });
    }

    for stage_cfg in enabled_stages.iter() {
        connected.push(StageInfo {
            label: stage_cfg.label.clone(),
            border_color: theme.muted,
            text_style: Style::default().fg(theme.muted),
            stage_id: Some(stage_cfg.id.clone()),
        });

        if stage_cfg.id == "plan" {
            connected.push(StageInfo {
                label: "P+".to_string(),
                border_color: theme.muted,
                text_style: Style::default().fg(theme.muted),
                stage_id: Some("plan-review".to_string()),
            });
        }
    }

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

    let discovery_active = active_role.as_ref() == Some(&AgentRole::Discovery);
    let discovery_used = state.is_discovering || state.discovery_round > 0;
    let patterns_used = state.session_patterns_learned > 0;

    let disconnected: Vec<StageInfo> = vec![
        StageInfo {
            label: "SHIP".to_string(),
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
            label: "SKILLS".to_string(),
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
            stage_id: Some("pattern_extraction".to_string()),
        },
    ];

    fn box_top(s: &mut Vec<Span<'static>>, width: usize, color: Color) {
        s.push(Span::styled(
            format!("\u{256d}{}\u{256e}", "\u{2500}".repeat(width)),
            Style::default().fg(color),
        ));
    }
    fn box_mid(s: &mut Vec<Span<'static>>, width: usize, label: &str, style: Style, color: Color) {
        let pad_total = width.saturating_sub(label.chars().count());
        let left = pad_total / 2;
        let right = pad_total - left;
        s.push(Span::styled("\u{2502}", Style::default().fg(color)));
        s.push(Span::styled(
            format!("{}{}{}", " ".repeat(left), label, " ".repeat(right)),
            style,
        ));
        s.push(Span::styled("\u{2502}", Style::default().fg(color)));
    }
    fn box_bot(s: &mut Vec<Span<'static>>, width: usize, color: Color) {
        s.push(Span::styled(
            format!("\u{2570}{}\u{256f}", "\u{2500}".repeat(width)),
            Style::default().fg(color),
        ));
    }

    let width = TILE_INNER_W as usize;
    let n_connected = connected.len();
    let n_row1 = n_connected.min(ROW1_MAX_TILES);
    let n_row2_connected = n_connected.saturating_sub(ROW1_MAX_TILES);

    // Row 1: top / mid / bot
    let mut top_r1 = vec![Span::raw("  ")];
    let mut mid_r1 = vec![Span::raw("  ")];
    let mut bot_r1 = vec![Span::raw("  ")];
    for (i, stage) in connected.iter().enumerate().take(n_row1) {
        let short = tile_label(&stage.label);
        box_top(&mut top_r1, width, stage.border_color);
        box_mid(&mut mid_r1, width, &short, stage.text_style, stage.border_color);
        box_bot(&mut bot_r1, width, stage.border_color);
        if i < n_row1 - 1 {
            top_r1.push(Span::raw("  "));
            mid_r1.push(Span::styled(
                "\u{2500}\u{25b6}",
                Style::default().fg(pipe_color),
            ));
            bot_r1.push(Span::raw("  "));
        }
    }

    // Inter-row gap line: includes optional wrap-down arrow above the first
    // row-2 connected tile.
    let mut gap_line: Vec<Span<'static>> = vec![Span::raw("  ")];
    if n_row2_connected > 0 {
        gap_line.push(Span::styled(
            "\u{21b3}",
            Style::default().fg(pipe_color).add_modifier(Modifier::BOLD),
        ));
    }

    // Row 2: overflow connected (left) + disconnected trio (right).
    let mut top_r2 = vec![Span::raw("  ")];
    let mut mid_r2 = vec![Span::raw("  ")];
    let mut bot_r2 = vec![Span::raw("  ")];
    for (j, stage) in connected
        .iter()
        .skip(ROW1_MAX_TILES)
        .take(n_row2_connected)
        .enumerate()
    {
        let short = tile_label(&stage.label);
        box_top(&mut top_r2, width, stage.border_color);
        box_mid(&mut mid_r2, width, &short, stage.text_style, stage.border_color);
        box_bot(&mut bot_r2, width, stage.border_color);
        if j < n_row2_connected - 1 {
            top_r2.push(Span::raw("  "));
            mid_r2.push(Span::styled(
                "\u{2500}\u{25b6}",
                Style::default().fg(pipe_color),
            ));
            bot_r2.push(Span::raw("  "));
        }
    }

    // Disconnected trio only when total connected <= 7 (matches old behavior).
    let render_disconnected = n_connected <= 7;
    if render_disconnected {
        // 4-cell gap between overflow connected and disconnected trio.
        let gap = if n_row2_connected > 0 { "    " } else { "      " };
        top_r2.push(Span::raw(gap.to_string()));
        mid_r2.push(Span::raw(gap.to_string()));
        bot_r2.push(Span::raw(gap.to_string()));

        for (i, stage) in disconnected.iter().enumerate() {
            let short = tile_label(&stage.label);
            box_top(&mut top_r2, width, stage.border_color);
            box_mid(&mut mid_r2, width, &short, stage.text_style, stage.border_color);
            box_bot(&mut bot_r2, width, stage.border_color);
            if i < disconnected.len() - 1 {
                top_r2.push(Span::raw("  "));
                mid_r2.push(Span::raw("  "));
                bot_r2.push(Span::raw("  "));
            }
        }
    }

    // Layout: 1 spacer + 3 row1 + 1 gap + 3 row2 + bottom border = 9 rows (Borders::BOTTOM provides the 9th).
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),           // 1-line spacer below title
            Constraint::Length(TILE_HEIGHT), // row 1 (3 lines)
            Constraint::Length(1),           // inter-row gap
            Constraint::Length(TILE_HEIGHT), // row 2 (3 lines)
            Constraint::Min(0),
        ])
        .split(area);

    let block = Block::default()
        .borders(Borders::BOTTOM)
        .border_style(Style::default().fg(theme.border))
        .title(Span::styled(
            " Pipeline ",
            Style::default().fg(theme.info).add_modifier(Modifier::BOLD),
        ));
    frame.render_widget(ratatui::widgets::Clear, area);
    frame.render_widget(block, area);

    let row1_paragraph = Paragraph::new(vec![
        Line::from(top_r1),
        Line::from(mid_r1),
        Line::from(bot_r1),
    ]);
    frame.render_widget(row1_paragraph, chunks[1]);

    let gap_paragraph = Paragraph::new(Line::from(gap_line));
    frame.render_widget(gap_paragraph, chunks[2]);

    let row2_paragraph = Paragraph::new(vec![
        Line::from(top_r2),
        Line::from(mid_r2),
        Line::from(bot_r2),
    ]);
    frame.render_widget(row2_paragraph, chunks[3]);
}

#[cfg(test)]
mod tests {
    use super::*;
    use ratatui::backend::TestBackend;
    use ratatui::Terminal;
    use std::path::PathBuf;

    fn render_pipeline_text(state: &AppState, config: &Config) -> String {
        let backend = TestBackend::new(220, 12);
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
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config::default();
        let rendered = render_pipeline_text(&state, &config);

        assert!(rendered.contains("Q"), "Q tile missing: {}", rendered);
        assert!(rendered.contains("R"), "R tile missing: {}", rendered);
        assert!(rendered.contains("P"), "P tile missing: {}", rendered);
        assert!(rendered.contains("P+"), "P+ tile missing: {}", rendered);
        assert!(rendered.contains("B"), "B tile missing: {}", rendered);
        assert!(rendered.contains("A"), "A tile missing: {}", rendered);
        assert!(!rendered.contains("COACH"), "rendered: {}", rendered);
    }

    #[test]
    fn pipeline_renders_p_plus_even_when_plan_review_disabled() {
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config {
            plan_review_enabled: false,
            ..Config::default()
        };
        let rendered = render_pipeline_text(&state, &config);

        let p_off = rendered.find(" P ").or_else(|| rendered.find("P "));
        let pplus_off = rendered.find("P+");
        let b_off = rendered.find(" B ").or_else(|| rendered.find("B "));
        assert!(p_off.is_some(), "P tile missing: {}", rendered);
        assert!(pplus_off.is_some(), "P+ tile missing: {}", rendered);
        assert!(b_off.is_some(), "B tile missing: {}", rendered);
    }

    #[test]
    fn pipeline_renders_coach_at_front_when_run_mode_coach() {
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config {
            run_mode: "coach".into(),
            ..Config::default()
        };
        let rendered = render_pipeline_text(&state, &config);

        let c_off = rendered.find(" C ").expect("C tile present");
        let q_off = rendered.find(" Q ").expect("Q tile present");
        assert!(
            c_off < q_off,
            "C should come before Q. rendered: {}",
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

        let pplus_off = rendered.find("P+").expect("P+ present");
        let b_off = rendered.find(" B ").or_else(|| rendered.find("B ")).expect("B present");
        assert!(pplus_off < b_off, "expected P+ < B; rendered: {}", rendered);
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

        let backend = TestBackend::new(220, 12);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_pipeline_map(frame, frame.area(), &state, &config))
            .expect("failed to draw pipeline");

        let buffer = terminal.backend().buffer();
        let area = *buffer.area();
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
        let mut found_active = false;
        let xs: Vec<u16> = (p_idx.saturating_sub(2) as u16
            ..((p_idx as u16).saturating_add(TILE_W + 2)).min(area.width))
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
            "Expected P+ tile (col={}, y={}) to use active color (accent={:?})",
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
        assert!(rendered.contains(" C "), "C tile missing: {}", rendered);
        assert!(rendered.contains("P+"), "P+ tile missing: {}", rendered);
        // Short labels for the disconnected trio.
        assert!(!rendered.contains("SH"), "SH should be dropped: {}", rendered);
        assert!(!rendered.contains("DI"), "DI should be dropped: {}", rendered);
        assert!(!rendered.contains("SK"), "SK should be dropped: {}", rendered);
    }

    #[test]
    fn pipeline_click_routes_row_1_connected_tiles_by_index() {
        // With default config + plan_review unconditional, connected = [Q,R,P,P+,B,A].
        // Row 1 holds first 5 (Q,R,P,P+,B). Row 2 holds A + disconnected trio.
        let area = Rect::new(0, 0, 220, 9);
        // Row 1 mid is at area.y + 1 + 1 = 2 (top of tile is +1; mid is +2).
        let row1_mid_y = area.y + 1 + 1;
        let x0 = area.x + 2;
        for i in 0..5 {
            let center = x0 + (i as u16) * TILE_PITCH + TILE_W / 2;
            let click = pipeline_click(area, center, row1_mid_y, 6);
            match click {
                Some(PipelineClick::ConnectedStage(idx)) => assert_eq!(idx, i),
                other => panic!("expected ConnectedStage({}), got {:?}", i, other),
            }
        }
    }

    #[test]
    fn pipeline_click_routes_row_2_disconnected_tiles() {
        let area = Rect::new(0, 0, 220, 9);
        // Row 2 starts at area.y + 1 + TILE_HEIGHT + 1 = area.y + 5. Mid = +6.
        let row2_mid_y = area.y + 1 + TILE_HEIGHT + 1 + 1;
        // n_connected = 6 -> n_row2_connected = 1 (AUDIT). disc starts at x0 + 1*pitch + 4.
        let x0 = area.x + 2;
        let disc_x0 = x0 + TILE_PITCH + 4;
        let ship_center = disc_x0 + TILE_W / 2;
        let disc_center = disc_x0 + TILE_PITCH + TILE_W / 2;
        let sk_center = disc_x0 + 2 * TILE_PITCH + TILE_W / 2;

        assert!(matches!(
            pipeline_click(area, ship_center, row2_mid_y, 6),
            Some(PipelineClick::Ship)
        ));
        assert!(matches!(
            pipeline_click(area, disc_center, row2_mid_y, 6),
            Some(PipelineClick::Discover)
        ));
        assert!(matches!(
            pipeline_click(area, sk_center, row2_mid_y, 6),
            Some(PipelineClick::Patterns)
        ));
    }

    #[test]
    fn pipeline_renders_two_rows_with_wrap_arrow() {
        let state = AppState::new(PathBuf::from(".buildloop"));
        let config = Config::default();
        let rendered = render_pipeline_text(&state, &config);
        // With 6 connected stages, A overflows to row 2, so the wrap-down arrow ↳ should appear.
        assert!(
            rendered.contains("\u{21b3}"),
            "wrap arrow missing: {}",
            rendered
        );
    }

    #[test]
    fn pipeline_modal_padding_constants_flow_through() {
        use crate::tui::theme::{MODAL_PADDING_H, MODAL_PADDING_V, TILE_HEIGHT, TILE_INNER_W};
        assert_eq!(MODAL_PADDING_H, 2);
        assert_eq!(MODAL_PADDING_V, 1);
        assert_eq!(TILE_INNER_W, 4);
        assert_eq!(TILE_HEIGHT, 3);
    }
}

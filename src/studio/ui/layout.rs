use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    widgets::BorderType,
};
use std::path::Path;

use crate::{agent::ModelProvider, utils::truncate_str};

use super::super::{model, state::StudioState};
use model::{
    FocusedPane, StudioTheme, COLUMN_RESIZE_HIT_MARGIN, COLUMN_SPLIT_WIDTH,
    DEFAULT_LEFT_COLUMN_PERCENT, DEFAULT_LEFT_CONTRACTS_HEIGHT, DEFAULT_LEFT_PROMPT_HEIGHT,
    DEFAULT_LEFT_SCAN_HEIGHT, DEFAULT_RIGHT_ACTIVITY_HEIGHT, DEFAULT_RIGHT_SESSIONS_HEIGHT,
    MIN_LEFT_BRIEF_HEIGHT, MIN_LEFT_COLUMN_WIDTH, MIN_LEFT_SECTION_HEIGHT, MIN_OUTPUT_HEIGHT,
    MIN_RIGHT_COLUMN_WIDTH, MIN_RIGHT_SECTION_HEIGHT, ROW_SPLIT_HEIGHT,
};

#[derive(Clone, Copy, Debug)]
pub(in crate::studio) struct StudioLayout {
    pub(in crate::studio) header: Rect,
    pub(in crate::studio) body: Rect,
    pub(in crate::studio) left_body: Rect,
    pub(in crate::studio) right_body: Rect,
    pub(in crate::studio) column_split: Rect,
    pub(in crate::studio) left_scan_prompt_split: Rect,
    pub(in crate::studio) left_prompt_contracts_split: Rect,
    pub(in crate::studio) left_contracts_brief_split: Rect,
    pub(in crate::studio) right_sessions_output_split: Rect,
    pub(in crate::studio) right_output_activity_split: Rect,
    pub(in crate::studio) scan: Rect,
    pub(in crate::studio) prompt: Rect,
    pub(in crate::studio) contracts: Rect,
    pub(in crate::studio) execution_brief: Rect,
    pub(in crate::studio) sessions: Rect,
    pub(in crate::studio) output: Rect,
    pub(in crate::studio) activity: Rect,
    pub(in crate::studio) status: Rect,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(in crate::studio) struct PromptPaneLayout {
    pub(in crate::studio) editor: Rect,
    pub(in crate::studio) history_label: Rect,
    pub(in crate::studio) history_list: Rect,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(in crate::studio) struct StudioLayoutConfig {
    pub(in crate::studio) left_column_percent: u16,
    pub(in crate::studio) left_scan_height: u16,
    pub(in crate::studio) left_prompt_height: u16,
    pub(in crate::studio) left_contracts_height: u16,
    pub(in crate::studio) right_sessions_height: u16,
    pub(in crate::studio) right_activity_height: u16,
}

impl Default for StudioLayoutConfig {
    fn default() -> Self {
        Self {
            left_column_percent: DEFAULT_LEFT_COLUMN_PERCENT,
            left_scan_height: DEFAULT_LEFT_SCAN_HEIGHT,
            left_prompt_height: DEFAULT_LEFT_PROMPT_HEIGHT,
            left_contracts_height: DEFAULT_LEFT_CONTRACTS_HEIGHT,
            right_sessions_height: DEFAULT_RIGHT_SESSIONS_HEIGHT,
            right_activity_height: DEFAULT_RIGHT_ACTIVITY_HEIGHT,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(in crate::studio) enum ResizeHandle {
    ColumnSplit,
    LeftScanPrompt,
    LeftPromptContracts,
    LeftContractsBrief,
    RightSessionsOutput,
    RightOutputActivity,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(in crate::studio) struct ResizeDragState {
    pub(in crate::studio) handle: ResizeHandle,
    pub(in crate::studio) start_column: u16,
    pub(in crate::studio) start_row: u16,
    pub(in crate::studio) initial_layout: StudioLayoutConfig,
}

pub(in crate::studio) fn studio_layout(area: Rect, config: StudioLayoutConfig) -> StudioLayout {
    let root = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(4),
            Constraint::Min(20),
            Constraint::Length(1),
        ])
        .split(area);

    let body_area = root[1];
    let left_width = clamped_left_column_width(body_area.width, config.left_column_percent);
    let column_split_width = if body_area.width >= 3 {
        COLUMN_SPLIT_WIDTH
    } else {
        0
    };
    let right_width = body_area
        .width
        .saturating_sub(left_width)
        .saturating_sub(column_split_width)
        .max(1);

    let body = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Length(left_width),
            Constraint::Length(column_split_width),
            Constraint::Min(right_width),
        ])
        .split(body_area);

    let left_height = left_content_height(body[0]).max(1);
    let mut left_scan_height = config.left_scan_height.max(MIN_LEFT_SECTION_HEIGHT);
    let mut left_prompt_height = config.left_prompt_height.max(MIN_LEFT_SECTION_HEIGHT);
    let mut left_contracts_height = config.left_contracts_height.max(MIN_LEFT_SECTION_HEIGHT);
    let left_brief_min = MIN_LEFT_BRIEF_HEIGHT.min(left_height.saturating_sub(3));
    let left_scan_max = left_height
        .saturating_sub(left_prompt_height)
        .saturating_sub(left_contracts_height)
        .saturating_sub(left_brief_min)
        .max(MIN_LEFT_SECTION_HEIGHT);
    left_scan_height = left_scan_height.min(left_scan_max);
    let left_prompt_max = left_height
        .saturating_sub(left_scan_height)
        .saturating_sub(left_contracts_height)
        .saturating_sub(left_brief_min)
        .max(MIN_LEFT_SECTION_HEIGHT);
    left_prompt_height = left_prompt_height.min(left_prompt_max);
    let left_contracts_max = left_height
        .saturating_sub(left_scan_height)
        .saturating_sub(left_prompt_height)
        .saturating_sub(left_brief_min)
        .max(MIN_LEFT_SECTION_HEIGHT);
    left_contracts_height = left_contracts_height.min(left_contracts_max);

    let left = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(left_scan_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Length(left_prompt_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Length(left_contracts_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Min(left_brief_min.max(1)),
        ])
        .split(body[0]);

    let right_height = right_content_height(body[2]).max(1);
    let mut right_sessions_height = config.right_sessions_height.max(MIN_RIGHT_SECTION_HEIGHT);
    let mut right_activity_height = config.right_activity_height.max(MIN_RIGHT_SECTION_HEIGHT);
    let output_min = MIN_OUTPUT_HEIGHT.min(right_height.saturating_sub(2));
    let right_sessions_max = right_height
        .saturating_sub(right_activity_height)
        .saturating_sub(output_min)
        .max(MIN_RIGHT_SECTION_HEIGHT);
    right_sessions_height = right_sessions_height.min(right_sessions_max);
    let right_activity_max = right_height
        .saturating_sub(right_sessions_height)
        .saturating_sub(output_min)
        .max(MIN_RIGHT_SECTION_HEIGHT);
    right_activity_height = right_activity_height.min(right_activity_max);

    let right = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(right_sessions_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Min(output_min.max(1)),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Length(right_activity_height),
        ])
        .split(body[2]);

    StudioLayout {
        header: root[0],
        body: body_area,
        left_body: body[0],
        right_body: body[2],
        column_split: body[1],
        left_scan_prompt_split: left[1],
        left_prompt_contracts_split: left[3],
        left_contracts_brief_split: left[5],
        right_sessions_output_split: right[1],
        right_output_activity_split: right[3],
        scan: left[0],
        prompt: left[2],
        contracts: left[4],
        execution_brief: left[6],
        sessions: right[0],
        output: right[2],
        activity: right[4],
        status: root[2],
    }
}

pub(in crate::studio) fn centered_rect(width: u16, height: u16, area: Rect) -> Rect {
    let popup_width = width.min(area.width.saturating_sub(2)).max(1);
    let popup_height = height.min(area.height.saturating_sub(2)).max(1);
    Rect::new(
        area.x + area.width.saturating_sub(popup_width) / 2,
        area.y + area.height.saturating_sub(popup_height) / 2,
        popup_width,
        popup_height,
    )
}

pub(in crate::studio) fn prompt_pane_layout(area: Rect, has_history: bool) -> PromptPaneLayout {
    let inner = bordered_inner(area);
    if inner.width == 0 || inner.height == 0 {
        return PromptPaneLayout::default();
    }

    if !has_history || inner.height < 5 {
        return PromptPaneLayout {
            editor: inner,
            history_label: Rect::default(),
            history_list: Rect::default(),
        };
    }

    let editor_height = inner.height.saturating_sub(3).clamp(3, 4);
    let history_height = inner.height.saturating_sub(editor_height).saturating_sub(1);

    if history_height == 0 {
        return PromptPaneLayout {
            editor: inner,
            history_label: Rect::default(),
            history_list: Rect::default(),
        };
    }

    PromptPaneLayout {
        editor: Rect::new(inner.x, inner.y, inner.width, editor_height),
        history_label: Rect::new(
            inner.x,
            inner.y.saturating_add(editor_height),
            inner.width,
            1,
        ),
        history_list: Rect::new(
            inner.x,
            inner.y.saturating_add(editor_height).saturating_add(1),
            inner.width,
            history_height,
        ),
    }
}

pub(in crate::studio) fn output_style(line: &str, theme: &StudioTheme) -> Style {
    if line.starts_with("[stderr]") {
        Style::default().fg(theme.error)
    } else if line.starts_with("[tool]") {
        Style::default().fg(theme.tool)
    } else if line.starts_with("[result]") {
        Style::default().fg(theme.tool_result)
    } else if line.starts_with("[studio]") {
        Style::default().fg(theme.info)
    } else if line.starts_with("[rate limited]") {
        Style::default().fg(theme.warning)
    } else {
        Style::default().fg(theme.text)
    }
}

pub(in crate::studio) fn current_studio_layout(state: &StudioState) -> Option<StudioLayout> {
    #[cfg(test)]
    let (width, height) = (120, 40);
    #[cfg(not(test))]
    let (width, height) = crossterm::terminal::size().ok()?;
    Some(studio_layout(
        Rect::new(0, 0, width, height),
        state.layout_config,
    ))
}

fn clamped_left_column_width(body_width: u16, percent: u16) -> u16 {
    let content_width = body_width.saturating_sub(COLUMN_SPLIT_WIDTH);
    if content_width > MIN_LEFT_COLUMN_WIDTH + MIN_RIGHT_COLUMN_WIDTH {
        ((content_width as u32 * percent as u32) / 100).clamp(
            MIN_LEFT_COLUMN_WIDTH as u32,
            content_width.saturating_sub(MIN_RIGHT_COLUMN_WIDTH) as u32,
        ) as u16
    } else {
        (content_width / 2).max(1)
    }
}

fn left_content_height(area: Rect) -> u16 {
    area.height
        .saturating_sub(LEFT_SPLIT_COUNT.saturating_mul(ROW_SPLIT_HEIGHT))
}

fn right_content_height(area: Rect) -> u16 {
    area.height
        .saturating_sub(RIGHT_SPLIT_COUNT.saturating_mul(ROW_SPLIT_HEIGHT))
}

pub(in crate::studio) fn resize_handle_at(
    layout: &StudioLayout,
    column: u16,
    row: u16,
) -> Option<ResizeHandle> {
    if rect_contains(layout.left_scan_prompt_split, column, row) {
        return Some(ResizeHandle::LeftScanPrompt);
    }
    if rect_contains(layout.left_prompt_contracts_split, column, row) {
        return Some(ResizeHandle::LeftPromptContracts);
    }
    if rect_contains(layout.left_contracts_brief_split, column, row) {
        return Some(ResizeHandle::LeftContractsBrief);
    }
    if rect_contains(layout.right_sessions_output_split, column, row) {
        return Some(ResizeHandle::RightSessionsOutput);
    }
    if rect_contains(layout.right_output_activity_split, column, row) {
        return Some(ResizeHandle::RightOutputActivity);
    }

    let min_column = layout
        .column_split
        .x
        .saturating_sub(COLUMN_RESIZE_HIT_MARGIN);
    let max_column = layout
        .column_split
        .x
        .saturating_add(layout.column_split.width.saturating_sub(1))
        .saturating_add(COLUMN_RESIZE_HIT_MARGIN);
    if row >= layout.column_split.y
        && row
            < layout
                .column_split
                .y
                .saturating_add(layout.column_split.height)
        && column >= min_column
        && column <= max_column
    {
        return Some(ResizeHandle::ColumnSplit);
    }

    None
}

pub(in crate::studio) fn apply_resize_drag(
    state: &mut StudioState,
    layout: &StudioLayout,
    drag: ResizeDragState,
    column: u16,
    row: u16,
) {
    let delta_columns = column as i32 - drag.start_column as i32;
    let delta_rows = row as i32 - drag.start_row as i32;
    let mut config = drag.initial_layout;

    match drag.handle {
        ResizeHandle::ColumnSplit => {
            let initial_left_width = clamped_left_column_width(
                layout.body.width,
                drag.initial_layout.left_column_percent,
            ) as i32;
            let min_left = 1.max(MIN_LEFT_COLUMN_WIDTH.min(layout.body.width / 2)) as i32;
            let min_right = 1.max(MIN_RIGHT_COLUMN_WIDTH.min(layout.body.width / 2)) as i32;
            let content_width = layout.body.width.saturating_sub(COLUMN_SPLIT_WIDTH);
            let max_left = content_width.saturating_sub(min_right as u16).max(1) as i32;
            let new_left_width = (initial_left_width + delta_columns).clamp(min_left, max_left);
            config.left_column_percent =
                ((new_left_width * 100) / content_width.max(1) as i32).clamp(1, 99) as u16;
        }
        ResizeHandle::LeftScanPrompt => {
            let max_height = (left_content_height(layout.left_body) as i32
                - drag.initial_layout.left_prompt_height as i32
                - drag.initial_layout.left_contracts_height as i32
                - MIN_LEFT_BRIEF_HEIGHT as i32)
                .max(MIN_LEFT_SECTION_HEIGHT as i32);
            config.left_scan_height = (drag.initial_layout.left_scan_height as i32 + delta_rows)
                .clamp(MIN_LEFT_SECTION_HEIGHT as i32, max_height)
                as u16;
        }
        ResizeHandle::LeftPromptContracts => {
            let max_height = (left_content_height(layout.left_body) as i32
                - drag.initial_layout.left_scan_height as i32
                - drag.initial_layout.left_contracts_height as i32
                - MIN_LEFT_BRIEF_HEIGHT as i32)
                .max(MIN_LEFT_SECTION_HEIGHT as i32);
            config.left_prompt_height = (drag.initial_layout.left_prompt_height as i32 + delta_rows)
                .clamp(MIN_LEFT_SECTION_HEIGHT as i32, max_height)
                as u16;
        }
        ResizeHandle::LeftContractsBrief => {
            let max_height = (left_content_height(layout.left_body) as i32
                - drag.initial_layout.left_scan_height as i32
                - drag.initial_layout.left_prompt_height as i32
                - MIN_LEFT_BRIEF_HEIGHT as i32)
                .max(MIN_LEFT_SECTION_HEIGHT as i32);
            config.left_contracts_height =
                (drag.initial_layout.left_contracts_height as i32 + delta_rows)
                    .clamp(MIN_LEFT_SECTION_HEIGHT as i32, max_height) as u16;
        }
        ResizeHandle::RightSessionsOutput => {
            let max_height = (right_content_height(layout.right_body) as i32
                - drag.initial_layout.right_activity_height as i32
                - MIN_OUTPUT_HEIGHT as i32)
                .max(MIN_RIGHT_SECTION_HEIGHT as i32);
            config.right_sessions_height =
                (drag.initial_layout.right_sessions_height as i32 + delta_rows)
                    .clamp(MIN_RIGHT_SECTION_HEIGHT as i32, max_height) as u16;
        }
        ResizeHandle::RightOutputActivity => {
            let max_height = (right_content_height(layout.right_body) as i32
                - drag.initial_layout.right_sessions_height as i32
                - MIN_OUTPUT_HEIGHT as i32)
                .max(MIN_RIGHT_SECTION_HEIGHT as i32);
            config.right_activity_height =
                (drag.initial_layout.right_activity_height as i32 - delta_rows)
                    .clamp(MIN_RIGHT_SECTION_HEIGHT as i32, max_height) as u16;
        }
    }

    state.layout_config = config;
}

pub(in crate::studio) fn pane_at_position(
    layout: &StudioLayout,
    column: u16,
    row: u16,
) -> Option<FocusedPane> {
    [
        (FocusedPane::Scan, layout.scan),
        (FocusedPane::Prompt, layout.prompt),
        (FocusedPane::Contracts, layout.contracts),
        (FocusedPane::ExecutionBrief, layout.execution_brief),
        (FocusedPane::Sessions, layout.sessions),
        (FocusedPane::Output, layout.output),
        (FocusedPane::Activity, layout.activity),
    ]
    .into_iter()
    .find_map(|(pane, area)| rect_contains(area, column, row).then_some(pane))
}

pub(in crate::studio) fn rect_contains(area: Rect, column: u16, row: u16) -> bool {
    let max_x = area.x.saturating_add(area.width);
    let max_y = area.y.saturating_add(area.height);
    column >= area.x && column < max_x && row >= area.y && row < max_y
}

fn bordered_inner(area: Rect) -> Rect {
    if area.width <= 2 || area.height <= 2 {
        Rect::default()
    } else {
        Rect::new(
            area.x.saturating_add(1),
            area.y.saturating_add(1),
            area.width.saturating_sub(2),
            area.height.saturating_sub(2),
        )
    }
}

pub(in crate::studio) fn pane_border_style(
    state: &StudioState,
    pane: FocusedPane,
    accent: Color,
) -> Style {
    if state.focused_pane == pane {
        Style::default().fg(accent).add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(state.theme.border)
    }
}

pub(in crate::studio) fn pane_title_style(
    state: &StudioState,
    pane: FocusedPane,
    accent: Color,
) -> Style {
    if state.focused_pane == pane {
        Style::default().fg(accent).add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(accent)
    }
}

pub(in crate::studio) fn pane_border_type(state: &StudioState, pane: FocusedPane) -> BorderType {
    if state.focused_pane == pane {
        BorderType::Thick
    } else {
        BorderType::Plain
    }
}

pub(in crate::studio) fn provider_color(theme: &StudioTheme, provider: ModelProvider) -> Color {
    match provider {
        ModelProvider::Claude => theme.claude,
        ModelProvider::Codex => theme.codex,
    }
}

pub(in crate::studio) fn studio_spinner(tick_count: usize) -> char {
    const SPINNER: &[char] = &['|', '/', '-', '\\'];
    SPINNER[tick_count % SPINNER.len()]
}

pub(in crate::studio) fn wrap_text_lines(text: &str, width: usize) -> Vec<String> {
    if width == 0 {
        return vec![String::new()];
    }

    let mut lines = Vec::new();
    for line in text.lines() {
        if line.is_empty() {
            lines.push(String::new());
            continue;
        }

        let mut remaining = line;
        while !remaining.is_empty() {
            if remaining.len() <= width {
                lines.push(remaining.to_string());
                break;
            }
            let safe_width = truncate_str(remaining, width).len();
            if safe_width == 0 {
                let first_char_len = remaining
                    .chars()
                    .next()
                    .map(|ch| ch.len_utf8())
                    .unwrap_or(1);
                lines.push(remaining[..first_char_len].to_string());
                remaining = &remaining[first_char_len..];
                continue;
            }
            let split_at = remaining[..safe_width]
                .rfind(' ')
                .map(|idx| idx + 1)
                .unwrap_or(safe_width);
            lines.push(remaining[..split_at].to_string());
            remaining = &remaining[split_at..];
        }
    }

    if lines.is_empty() {
        lines.push(String::new());
    }

    lines
}

pub(in crate::studio) fn truncate_display_path(path: &Path, max_len: usize) -> String {
    let display = path.display().to_string();
    if display.len() <= max_len {
        display
    } else {
        let suffix_len = max_len.saturating_sub(3);
        let mut start = display.len().saturating_sub(suffix_len);
        while start < display.len() && !display.is_char_boundary(start) {
            start += 1;
        }
        format!("...{}", &display[start..])
    }
}

const LEFT_SPLIT_COUNT: u16 = 3;
const RIGHT_SPLIT_COUNT: u16 = 2;

#[cfg(test)]
mod tests {
    use ratatui::layout::Rect;

    use super::super::super::{
        model::{
            FocusedPane, COLUMN_RESIZE_HIT_MARGIN, DEFAULT_LEFT_COLUMN_PERCENT,
            DEFAULT_LEFT_CONTRACTS_HEIGHT, DEFAULT_LEFT_PROMPT_HEIGHT, DEFAULT_LEFT_SCAN_HEIGHT,
            DEFAULT_RIGHT_ACTIVITY_HEIGHT, DEFAULT_RIGHT_SESSIONS_HEIGHT,
        },
        test_helpers::test_state,
    };
    use super::{
        apply_resize_drag, output_style, pane_at_position, prompt_pane_layout, resize_handle_at,
        studio_layout, ResizeDragState, ResizeHandle, StudioLayoutConfig,
    };

    #[test]
    fn pane_hit_testing_maps_points_to_expected_panes() {
        let layout = studio_layout(Rect::new(0, 0, 120, 40), StudioLayoutConfig::default());

        assert_eq!(
            pane_at_position(&layout, layout.scan.x + 1, layout.scan.y + 1),
            Some(FocusedPane::Scan)
        );
        assert_eq!(
            pane_at_position(&layout, layout.contracts.x + 1, layout.contracts.y + 1),
            Some(FocusedPane::Contracts)
        );
        assert_eq!(
            pane_at_position(
                &layout,
                layout.execution_brief.x + 1,
                layout.execution_brief.y + 1
            ),
            Some(FocusedPane::ExecutionBrief)
        );
        assert_eq!(
            pane_at_position(&layout, layout.output.x + 1, layout.output.y + 1),
            Some(FocusedPane::Output)
        );
        assert_eq!(pane_at_position(&layout, 0, 0), None);
    }

    #[test]
    fn resize_handle_hit_testing_identifies_all_splitters() {
        let layout = studio_layout(Rect::new(0, 0, 120, 40), StudioLayoutConfig::default());

        assert_eq!(
            resize_handle_at(&layout, layout.column_split.x, layout.column_split.y + 1),
            Some(ResizeHandle::ColumnSplit)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.left_scan_prompt_split.x + 1,
                layout.left_scan_prompt_split.y,
            ),
            Some(ResizeHandle::LeftScanPrompt)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.left_prompt_contracts_split.x + 1,
                layout.left_prompt_contracts_split.y,
            ),
            Some(ResizeHandle::LeftPromptContracts)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.left_contracts_brief_split.x + 1,
                layout.left_contracts_brief_split.y,
            ),
            Some(ResizeHandle::LeftContractsBrief)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.right_sessions_output_split.x + 1,
                layout.right_sessions_output_split.y,
            ),
            Some(ResizeHandle::RightSessionsOutput)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.right_output_activity_split.x + 1,
                layout.right_output_activity_split.y,
            ),
            Some(ResizeHandle::RightOutputActivity)
        );
        assert_eq!(
            resize_handle_at(&layout, layout.scan.x + 2, layout.scan.y + 2),
            None
        );
    }

    #[test]
    fn column_split_hit_testing_respects_grab_zone_boundaries() {
        let layout = studio_layout(Rect::new(0, 0, 120, 40), StudioLayoutConfig::default());

        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_sub(COLUMN_RESIZE_HIT_MARGIN),
                layout.column_split.y + 1,
            ),
            Some(ResizeHandle::ColumnSplit)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_add(COLUMN_RESIZE_HIT_MARGIN),
                layout.column_split.y + 1,
            ),
            Some(ResizeHandle::ColumnSplit)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_sub(COLUMN_RESIZE_HIT_MARGIN.saturating_add(1)),
                layout.column_split.y + 1,
            ),
            None
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_add(COLUMN_RESIZE_HIT_MARGIN.saturating_add(1)),
                layout.column_split.y + 1,
            ),
            None
        );
    }

    #[test]
    fn dragging_column_split_updates_layout_width() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::ColumnSplit,
            start_column: layout.column_split.x,
            start_row: layout.column_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.column_split.x.saturating_add(8),
            layout.column_split.y,
        );

        assert!(state.layout_config.left_column_percent > DEFAULT_LEFT_COLUMN_PERCENT);
    }

    #[test]
    fn dragging_scan_prompt_split_updates_scan_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::LeftScanPrompt,
            start_column: layout.left_scan_prompt_split.x + 1,
            start_row: layout.left_scan_prompt_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.left_scan_prompt_split.x + 1,
            layout.left_scan_prompt_split.y.saturating_add(2),
        );

        assert!(state.layout_config.left_scan_height > DEFAULT_LEFT_SCAN_HEIGHT);
    }

    #[test]
    fn dragging_prompt_contracts_split_updates_prompt_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::LeftPromptContracts,
            start_column: layout.left_prompt_contracts_split.x + 1,
            start_row: layout.left_prompt_contracts_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.left_prompt_contracts_split.x + 1,
            layout.left_prompt_contracts_split.y.saturating_add(2),
        );

        assert!(state.layout_config.left_prompt_height > DEFAULT_LEFT_PROMPT_HEIGHT);
    }

    #[test]
    fn dragging_contracts_brief_split_updates_contracts_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::LeftContractsBrief,
            start_column: layout.left_contracts_brief_split.x + 1,
            start_row: layout.left_contracts_brief_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.left_contracts_brief_split.x + 1,
            layout.left_contracts_brief_split.y.saturating_add(2),
        );

        assert!(state.layout_config.left_contracts_height > DEFAULT_LEFT_CONTRACTS_HEIGHT);
    }

    #[test]
    fn dragging_sessions_output_split_updates_sessions_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::RightSessionsOutput,
            start_column: layout.right_sessions_output_split.x + 1,
            start_row: layout.right_sessions_output_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.right_sessions_output_split.x + 1,
            layout.right_sessions_output_split.y.saturating_add(2),
        );

        assert!(state.layout_config.right_sessions_height > DEFAULT_RIGHT_SESSIONS_HEIGHT);
    }

    #[test]
    fn dragging_output_activity_split_down_shrinks_activity_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::RightOutputActivity,
            start_column: layout.right_output_activity_split.x + 1,
            start_row: layout.right_output_activity_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.right_output_activity_split.x + 1,
            layout.right_output_activity_split.y.saturating_add(2),
        );

        assert!(state.layout_config.right_activity_height < DEFAULT_RIGHT_ACTIVITY_HEIGHT);
    }

    #[test]
    fn dragging_output_activity_split_up_grows_activity_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::RightOutputActivity,
            start_column: layout.right_output_activity_split.x + 1,
            start_row: layout.right_output_activity_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.right_output_activity_split.x + 1,
            layout.right_output_activity_split.y.saturating_sub(2),
        );

        assert!(state.layout_config.right_activity_height > DEFAULT_RIGHT_ACTIVITY_HEIGHT);
    }

    #[test]
    fn studio_output_style_matches_semantic_prefixes() {
        let theme = test_state().theme;

        assert_eq!(output_style("[stderr] boom", &theme).fg, Some(theme.error));
        assert_eq!(output_style("[tool] read", &theme).fg, Some(theme.tool));
        assert_eq!(
            output_style("[result] ok", &theme).fg,
            Some(theme.tool_result)
        );
        assert_eq!(output_style("[studio] note", &theme).fg, Some(theme.info));
        assert_eq!(
            output_style("[rate limited] wait", &theme).fg,
            Some(theme.warning)
        );
        assert_eq!(output_style("plain text", &theme).fg, Some(theme.text));
    }

    #[test]
    fn prompt_pane_layout_splits_editor_and_history_regions() {
        let layout = prompt_pane_layout(Rect::new(0, 0, 48, 8), true);

        assert_eq!(layout.editor.height, 3);
        assert_eq!(layout.history_label.height, 1);
        assert_eq!(layout.history_list.height, 2);
        assert_eq!(
            layout.history_label.y,
            layout.editor.y + layout.editor.height
        );
        assert_eq!(
            layout.history_list.y,
            layout.history_label.y + layout.history_label.height
        );
    }
}

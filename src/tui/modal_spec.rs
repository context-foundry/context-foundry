use ratatui::layout::{Alignment, Constraint, Direction, Layout, Margin, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{
    Block, BorderType, Borders, Clear, Paragraph, Scrollbar, ScrollbarOrientation, ScrollbarState,
};
use ratatui::Frame;

use crate::tui::overlays::close_btn_rect;
use crate::tui::theme::{TuiTheme, MODAL_PADDING_H, MODAL_PADDING_V};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[allow(dead_code)]
pub enum ModalSize {
    /// 78 x 18 centered, matches today's AI-summary modal.
    Small,
    /// 90% width x 80% height, min 80x24, matches today's settings modal.
    Large,
    /// Width 60, height 9. Used for compact confirm dialogs (stop, quit).
    Confirm,
    /// Width 64, height 13. Used for the Ctrl+C three-option menu.
    MenuMedium,
    /// Caller supplies an absolute Rect (used by full-screen Stats/Patterns/Findings).
    Custom(Rect),
}

#[derive(Debug, Clone)]
pub struct ModalButton {
    /// Bracketed key tag (e.g. `"Esc"`, `"Y"`, `"r"`).
    pub key: String,
    /// Muted label rendered after the bracket (e.g. `" dismiss"`).
    pub label: String,
    /// Stable identifier used by callers to map clicks back to actions
    /// (e.g. `"dismiss"`, `"refresh"`, `"open-file"`, `"quit"`).
    pub action_id: String,
}

#[derive(Debug, Clone)]
pub struct ModalSpec {
    pub title: String,
    pub body: Vec<Line<'static>>,
    pub footer_buttons: Vec<ModalButton>,
    pub status_line: Option<Line<'static>>,
    pub size: ModalSize,
    pub scroll_offset: u16,
    pub show_close_button: bool,
    pub border_color: Color,
    pub status_color: Color,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ModalLayout {
    pub modal: Rect,
    pub body: Rect,
    pub title: Rect,
    pub status: Rect,
    pub footer: Rect,
    pub close_btn: Rect,
}

/// Compute the modal Rect for a given size variant. Returns None when the
/// terminal is too small for the requested size.
pub fn modal_rect(area: Rect, size: ModalSize) -> Option<Rect> {
    let (w, h) = match size {
        ModalSize::Small => {
            let w = 78u16.min(area.width.saturating_sub(2));
            let h = 18u16.min(area.height.saturating_sub(2));
            if w < 20 || h < 5 {
                return None;
            }
            (w, h)
        }
        ModalSize::Large => {
            if area.width < 80 || area.height < 24 {
                return Some(area);
            }
            let w = ((area.width as u32 * 90 / 100).max(80) as u16).min(area.width);
            let h = ((area.height as u32 * 80 / 100).max(24) as u16).min(area.height);
            (w, h)
        }
        ModalSize::Confirm => {
            let w = 60u16.min(area.width.saturating_sub(2));
            let h = 9u16.min(area.height.saturating_sub(2));
            if w < 30 || h < 5 {
                return None;
            }
            (w, h)
        }
        ModalSize::MenuMedium => {
            let w = 64u16.min(area.width.saturating_sub(2));
            let h = 13u16.min(area.height.saturating_sub(2));
            if w < 30 || h < 5 {
                return None;
            }
            (w, h)
        }
        ModalSize::Custom(r) => return Some(r),
    };
    let x = area.x + area.width.saturating_sub(w) / 2;
    let y = area.y + area.height.saturating_sub(h) / 2;
    Some(Rect {
        x,
        y,
        width: w,
        height: h,
    })
}

/// Split the modal rect into title / body / status / footer regions using the
/// shared padding constants.
pub fn compute_modal_layout(modal: Rect) -> ModalLayout {
    let padded = modal.inner(Margin {
        horizontal: MODAL_PADDING_H,
        vertical: MODAL_PADDING_V,
    });
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // title
            Constraint::Length(1), // spacer
            Constraint::Min(0),    // body
            Constraint::Length(1), // status
            Constraint::Length(1), // footer
        ])
        .split(padded);
    let close_btn = close_btn_rect(modal);
    ModalLayout {
        modal,
        title: chunks[0],
        body: chunks[2],
        status: chunks[3],
        footer: chunks[4],
        close_btn,
    }
}

/// Render the unified modal shell (shadow + double border + close button +
/// title + body + scrollbar + status + footer) for a `ModalSpec`. Returns the
/// laid-out rects so callers can hit-test against the same geometry.
pub fn render_unified_modal(
    frame: &mut Frame,
    theme: &TuiTheme,
    spec: &ModalSpec,
) -> Option<ModalLayout> {
    let area = frame.area();
    let modal = modal_rect(area, spec.size)?;

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
    frame.render_widget(
        Block::default()
            .borders(Borders::ALL)
            .border_type(BorderType::Double)
            .border_style(
                Style::default()
                    .fg(spec.border_color)
                    .add_modifier(Modifier::BOLD),
            )
            .style(Style::default().bg(theme.surface).fg(theme.text)),
        modal,
    );

    let layout = compute_modal_layout(modal);

    if spec.show_close_button {
        let btn = layout.close_btn;
        let buf = frame.buffer_mut();
        let style = Style::default()
            .fg(Color::Yellow)
            .add_modifier(Modifier::BOLD);
        for (i, ch) in "[ X ]".chars().enumerate() {
            let col = btn.x + i as u16;
            if col < buf.area().width && btn.y < buf.area().height {
                buf[(col, btn.y)].set_char(ch).set_style(style);
            }
        }
    }

    if !spec.title.is_empty() {
        let title = Paragraph::new(Line::from(Span::styled(
            spec.title.clone(),
            Style::default()
                .fg(spec.border_color)
                .add_modifier(Modifier::BOLD),
        )))
        .alignment(Alignment::Center);
        frame.render_widget(title, layout.title);
    }

    if !spec.body.is_empty() {
        let body = Paragraph::new(spec.body.clone())
            .wrap(ratatui::widgets::Wrap { trim: false })
            .scroll((spec.scroll_offset, 0));
        frame.render_widget(body, layout.body);

        let body_width = layout.body.width.max(1) as usize;
        let body_height = layout.body.height.max(1) as usize;
        let total_lines: usize = spec
            .body
            .iter()
            .map(|line| {
                let chars: usize = line.spans.iter().map(|s| s.content.chars().count()).sum();
                if chars == 0 {
                    1
                } else {
                    chars.div_ceil(body_width)
                }
            })
            .sum();
        if total_lines > body_height {
            let mut sb_state = ScrollbarState::new(total_lines.saturating_sub(body_height))
                .position(spec.scroll_offset as usize);
            let scrollbar = Scrollbar::new(ScrollbarOrientation::VerticalRight)
                .begin_symbol(None)
                .end_symbol(None)
                .track_style(Style::default().fg(theme.muted))
                .thumb_style(
                    Style::default()
                        .fg(spec.border_color)
                        .add_modifier(Modifier::BOLD),
                );
            frame.render_stateful_widget(scrollbar, layout.body, &mut sb_state);
        }
    }

    if let Some(line) = spec.status_line.as_ref() {
        let status = Paragraph::new(line.clone()).style(Style::default().fg(spec.status_color));
        frame.render_widget(status, layout.status);
    }

    if !spec.footer_buttons.is_empty() {
        let bracket_style = Style::default()
            .fg(theme.accent)
            .add_modifier(Modifier::BOLD | Modifier::UNDERLINED);
        let label_style = Style::default().fg(theme.muted);
        let mut spans: Vec<Span<'static>> = Vec::new();
        for (i, btn) in spec.footer_buttons.iter().enumerate() {
            if i > 0 {
                spans.push(Span::styled("   ", label_style));
            }
            spans.push(Span::styled(format!("[{}]", btn.key), bracket_style));
            spans.push(Span::styled(btn.label.clone(), label_style));
        }
        let footer = Paragraph::new(Line::from(spans)).alignment(Alignment::Center);
        frame.render_widget(footer, layout.footer);
    }

    Some(layout)
}

/// Width in cells of a single rendered footer button (`[key]label`).
fn footer_button_width(btn: &ModalButton) -> u16 {
    let key_chars = btn.key.chars().count() as u16;
    let label_chars = btn.label.chars().count() as u16;
    key_chars + 2 + label_chars
}

/// Total cells used by the footer (centered), including 3-cell separators.
fn footer_total_width(spec: &ModalSpec) -> u16 {
    if spec.footer_buttons.is_empty() {
        return 0;
    }
    let mut w: u16 = 0;
    for (i, btn) in spec.footer_buttons.iter().enumerate() {
        if i > 0 {
            w = w.saturating_add(3);
        }
        w = w.saturating_add(footer_button_width(btn));
    }
    w
}

/// Hit-test a mouse click against a rendered modal. Returns `None` if the
/// click was outside the modal Rect entirely. Returns `Some("dismiss")` for
/// the `[ X ]` close button. Returns `Some(action_id)` for footer buttons.
/// Returns `Some(String::new())` for clicks inside the modal but outside any
/// actionable region (caller should treat this as "consumed").
pub fn unified_modal_hit_test(
    layout: &ModalLayout,
    spec: &ModalSpec,
    col: u16,
    row: u16,
) -> Option<String> {
    if col < layout.modal.x
        || col >= layout.modal.x + layout.modal.width
        || row < layout.modal.y
        || row >= layout.modal.y + layout.modal.height
    {
        return None;
    }

    if spec.show_close_button
        && row == layout.close_btn.y
        && col >= layout.close_btn.x
        && col < layout.close_btn.x + layout.close_btn.width
    {
        return Some("dismiss".to_string());
    }

    if row == layout.footer.y && !spec.footer_buttons.is_empty() {
        let total = footer_total_width(spec);
        let footer_x = layout.footer.x + layout.footer.width.saturating_sub(total) / 2;
        let mut cur = footer_x;
        for (i, btn) in spec.footer_buttons.iter().enumerate() {
            if i > 0 {
                cur = cur.saturating_add(3);
            }
            let bw = footer_button_width(btn);
            if col >= cur && col < cur + bw {
                return Some(btn.action_id.clone());
            }
            cur = cur.saturating_add(bw);
        }
    }

    Some(String::new())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modal_rect_small_fits_terminal() {
        let area = Rect::new(0, 0, 120, 40);
        let r = modal_rect(area, ModalSize::Small).expect("small fits");
        assert_eq!(r.width, 78);
        assert_eq!(r.height, 18);
    }

    #[test]
    fn modal_rect_confirm_fits_terminal() {
        let area = Rect::new(0, 0, 120, 40);
        let r = modal_rect(area, ModalSize::Confirm).expect("confirm fits");
        assert_eq!(r.width, 60);
        assert_eq!(r.height, 9);
    }

    #[test]
    fn modal_rect_returns_none_when_too_small() {
        let area = Rect::new(0, 0, 10, 4);
        assert!(modal_rect(area, ModalSize::Small).is_none());
        assert!(modal_rect(area, ModalSize::Confirm).is_none());
    }

    #[test]
    fn compute_modal_layout_uses_padding() {
        let modal = Rect::new(0, 0, 60, 9);
        let l = compute_modal_layout(modal);
        // Inner rect after Margin{2,1} -> x=2, y=1, w=56, h=7
        assert_eq!(l.title.x, 2);
        assert_eq!(l.title.y, 1);
        assert_eq!(l.title.width, 56);
        // close button is at modal.x + width - 6 = 54
        assert_eq!(l.close_btn.x, modal.x + modal.width - 6);
        assert_eq!(l.close_btn.y, modal.y);
    }

    #[test]
    fn hit_test_returns_dismiss_on_close_button() {
        let modal = Rect::new(0, 0, 60, 9);
        let layout = compute_modal_layout(modal);
        let spec = ModalSpec {
            title: String::new(),
            body: Vec::new(),
            footer_buttons: Vec::new(),
            status_line: None,
            size: ModalSize::Confirm,
            scroll_offset: 0,
            show_close_button: true,
            border_color: Color::Reset,
            status_color: Color::Reset,
        };
        let id = unified_modal_hit_test(&layout, &spec, layout.close_btn.x + 2, layout.close_btn.y);
        assert_eq!(id.as_deref(), Some("dismiss"));
    }

    #[test]
    fn hit_test_returns_action_id_for_footer_button() {
        let modal = Rect::new(0, 0, 60, 9);
        let layout = compute_modal_layout(modal);
        let spec = ModalSpec {
            title: String::new(),
            body: Vec::new(),
            footer_buttons: vec![
                ModalButton {
                    key: "Y".into(),
                    label: " yes".into(),
                    action_id: "yes".into(),
                },
                ModalButton {
                    key: "N".into(),
                    label: " no".into(),
                    action_id: "no".into(),
                },
            ],
            status_line: None,
            size: ModalSize::Confirm,
            scroll_offset: 0,
            show_close_button: false,
            border_color: Color::Reset,
            status_color: Color::Reset,
        };
        // total footer: [Y] yes(7) + 3 + [N] no(6) = 16. Centered in width 56 starting at x=2 -> footer_x = 2 + (56-16)/2 = 22
        let id = unified_modal_hit_test(&layout, &spec, 22, layout.footer.y);
        assert_eq!(id.as_deref(), Some("yes"));
        // [N] no starts at 22 + 7 + 3 = 32, width 6 -> cols 32..38
        let id2 = unified_modal_hit_test(&layout, &spec, 33, layout.footer.y);
        assert_eq!(id2.as_deref(), Some("no"));
    }

    #[test]
    fn hit_test_returns_none_when_click_outside_modal() {
        let modal = Rect::new(10, 5, 60, 9);
        let layout = compute_modal_layout(modal);
        let spec = ModalSpec {
            title: String::new(),
            body: Vec::new(),
            footer_buttons: Vec::new(),
            status_line: None,
            size: ModalSize::Confirm,
            scroll_offset: 0,
            show_close_button: true,
            border_color: Color::Reset,
            status_color: Color::Reset,
        };
        assert!(unified_modal_hit_test(&layout, &spec, 0, 0).is_none());
        assert!(unified_modal_hit_test(&layout, &spec, 200, 50).is_none());
    }
}

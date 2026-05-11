# TUI Conventions

This document captures the shared rendering contract used by every floating
modal and by the pipeline-tile grid. It exists so new modals stay consistent
without re-deriving the same details from existing code.

## Unified modal contract

Every modal in the TUI (AI summary, settings, stats, patterns, findings,
running [stop / Ctrl+C], quit confirm, no-tasks warning) renders through
`tui::render_unified_modal(frame, theme, &ModalSpec) -> Option<ModalLayout>`.
Callers build a `ModalSpec` and call once; the renderer handles the shadow,
border, padding, close button, title, body, scrollbar, status line, and
footer.

### Visual conventions

- **Border**: `BorderType::Double` in the spec's `border_color`, with
  `Modifier::BOLD`.
- **Inner padding**: 2 cells horizontal, 1 cell vertical (constants
  `MODAL_PADDING_H` / `MODAL_PADDING_V` in `tui/theme.rs`). Applied via
  `Margin { horizontal, vertical }` before the title/body/status/footer
  split.
- **`[ X ]` close button**: top-right of the modal, rendered in
  `Color::Yellow + Modifier::BOLD`. Shared geometry helper:
  `overlays::close_btn_rect(modal)`.
- **Title row**: centered, in `border_color + Modifier::BOLD`.
- **Body**: scrollable. `Paragraph::new(spec.body).wrap(Wrap{trim:false}).scroll((offset, 0))`.
  When the wrapped-line total exceeds the body height, a proportional
  `Scrollbar` is rendered along the right edge of the body rect.
- **Status row (optional)**: a single styled `Line` above the footer.
  Uses `spec.status_color`. Use this for dynamic state messages
  (e.g. "editing X -- Enter save").
- **Footer**: centered list of button-style spans. Each `ModalButton`
  renders as `[Span::styled("[{key}]", accent+bold+underlined),
  Span::styled(label, muted)]`, separated by 3 spaces.
- **Dismiss behavior**: `[ X ]` close button always returns
  `action_id == "dismiss"` from `unified_modal_hit_test`. Per-modal
  callers translate that to their concrete action.
- **Hover lock**: while any modal is open, background-pane focus does
  NOT change on hover. (Regression coverage for commit 8353d0b.)

### Hit-testing

Use `tui::unified_modal_hit_test(&layout, &spec, col, row) -> Option<String>`:

- `None` -- the click missed the modal entirely; the caller may fall
  through to underlying-screen handlers.
- `Some("dismiss")` -- the user clicked the close button.
- `Some(action_id)` -- the user clicked a footer button.
- `Some(String::new())` -- the click landed inside the modal but on no
  actionable region. Treat as consumed.

## Pipeline tile layout

The pipeline area is fixed at **9 rows tall**:

```
y=0  spacer (under " Pipeline " title)
y=1  row 1 top border
y=2  row 1 label
y=3  row 1 bottom border
y=4  inter-row gap (may contain ↳ wrap arrow)
y=5  row 2 top border
y=6  row 2 label
y=7  row 2 bottom border
y=8  bottom border (Borders::BOTTOM provides this row)
```

The 9-row height is enforced at three render sites and four mouse-handler
layout sites that must stay in sync:

- `tui::render` (dashboard)
- `tui::render_running_explorer` (explore tab)
- `tui::running_layout` (pane rects for hover/click on the dashboard)
- `app::handle_*_mouse_at` layout chunks (status-bar, hit-test, hover)

If any one of these uses a different constraint length, mouse hit-tests
drift relative to what's actually drawn.

### Tile geometry

- Tile inner width: `TILE_INNER_W = 4` cells (between the L/R borders).
- Tile total width: `TILE_INNER_W + 2 = 6` cells (including borders).
- Tile height: `TILE_HEIGHT = 3` cells.
- Tile pitch: `6 + 2 = 8` cells (tile + arrow/gap).

### Row composition

- **Row 1**: holds the first up to 5 connected stages (`Q`, `R`, `P`,
  `P+`, `B`). Adjacent tiles separated by a `─▶` arrow.
- **Row 2**: holds connected overflow (typically just `A`) plus the
  disconnected trio (`SH`, `DI`, `SK`), separated by an 8-cell gap.
- **Wrap arrow**: when at least one connected stage spills onto row 2,
  a `↳` (`\u{21B3}`) appears on the inter-row gap line directly above
  the first row-2 connected tile.

### Tile labels

Long stage names are mapped to short uppercase abbreviations:

| Long       | Short |
|------------|-------|
| QUERY      | Q     |
| RESEARCH   | R     |
| PLAN       | P     |
| (P+ stays) | P+    |
| BUILD      | B     |
| AUDIT      | A     |
| COACH      | C     |
| SHIP       | SH    |
| DISCOVER   | DI    |
| SKILLS     | SK    |

Custom labels fall back to the first two ASCII characters, uppercased.

## Adding a new modal

1. Build a `ModalSpec` with the body lines, footer buttons, title,
   border color, and status line.
2. Pick a `ModalSize`:
   - `Small` -- 78x18 (AI summary, generic info).
   - `Large` -- 90% x 80% (settings-like, lots of content).
   - `Confirm` -- 60x9 (yes/no dialogs).
   - `MenuMedium` -- 64x13 (3-4 option menu).
   - `Custom(Rect)` -- full-screen / arbitrary.
3. Call `let _ = render_unified_modal(frame, theme, &spec);` once.
4. If the modal accepts mouse clicks, call
   `unified_modal_hit_test(&layout, &spec, col, row)` and route
   `action_id` to the matching `Action`.

## Adding a new pipeline stage

1. Add an entry to `config.pipeline_stages` (or the COACH/P+ virtual
   stages already handled).
2. Add a `tile_label` case in `tui/pipeline.rs` so the long name maps
   to a 1-2 char abbreviation.
3. Decide whether the stage is connected (row 1, up to 5; overflows
   wrap to row 2) or disconnected (row 2 only, fixed trio of SH/DI/SK).
4. If row 1 fills beyond 5 stages, the renderer automatically wraps
   the rest to row 2 with the `↳` indicator.

# Plan: Studio Modular Extraction

Date: 2026-03-07
Version: v1
Status: complete

## Context

`studio.rs` started at 6,664 lines with 225 top-level items. It contained types, attachment logic, contract CRUD, prompt composition, project scanning, session management, provider probing, TUI rendering, input handling, modal rendering, layout math, and tests -- all in one file. This makes navigation, review, and concurrent feature work unnecessarily difficult.

## Current State

- Root module is now `src/studio.rs` (15 lines) and only wires submodules plus the `run_tui` re-export
- Extracted modules: `providers.rs` (726 lines), `attachments.rs` (1,394 lines), `scan.rs` (244 lines), `shared.rs` (60 lines), `prompt.rs` (227 lines), `contracts.rs` (449 lines), `session.rs` (653 lines), `model.rs` (509 lines), `state.rs` (874 lines), `app.rs` (209 lines), `ui/layout.rs` (831 lines), `ui/render.rs` (767 lines), `ui/modals.rs` (274 lines), `ui/input.rs` (1,332 lines)
- 127 passing tests, with provider, attachment, scan, shared, prompt, contract, session, model, state, app, layout, render, and input tests colocated in their modules; modal rendering remains covered by input-layer tests
- The studio refactor target structure is now fully in place
- Other crate modules (`app.rs`, `agent.rs`, `tui.rs`, etc.) are 1,500-40,000 lines -- studio is the outlier

## Target Structure

```
src/studio.rs         -- root module during incremental extraction; becomes thin module late
src/studio/
  shared.rs           -- cross-cutting helpers used by multiple studio submodules
  app.rs              -- run_tui, event loop, terminal reader
  state.rs            -- StudioState, StudioEvent, state helpers
  model.rs            -- shared domain structs: contracts, attachments, sessions, readiness
  prompt.rs           -- compose_smoothed_prompt, preview prompt assembly
  scan.rs             -- scan_project, collect_matching_paths, output targets
  contracts.rs        -- contract load/persist/create/delete/cycle, sidecar lifecycle
  attachments.rs      -- sidecar I/O, resolution, formatting, picker (incl. macOS #[cfg])
  providers.rs        -- CLI probing, auth checks, help parsing, live probe, cache
  session.rs          -- start/run session, workspace snapshot, artifact discovery
  test_helpers.rs     -- shared #[cfg(test)] fixtures used across studio submodules
  ui/
    mod.rs            -- re-exports for ui submodules
    layout.rs         -- StudioLayout, StudioLayoutConfig, resize math, hit testing
    render.rs         -- pane rendering (header, scan, prompt, contracts, preview, sessions, output, activity, status)
    modals.rs         -- editor guide, delete confirmation, attachment manager rendering
    input.rs          -- key dispatch, mouse handling, prompt editing, modal key handlers
```

### Picker Decision

The macOS native picker (~60 lines) stays inside `attachments.rs` behind `#[cfg(target_os = "macos")]`. It earns its own `picker.rs` only when:
- Linux/Windows pickers are added
- The picker gets its own state/model beyond "return selected paths"
- The platform-specific code grows beyond a small helper

### Test Placement

Unit tests move with each extracted module in colocated `#[cfg(test)]` blocks. No standalone `tests.rs` file. A cross-module integration test file is added only if cross-module flows emerge that don't belong to any single module.

## Function-to-Module Mapping

### model.rs (~500 lines)
Shared constants, theme/style helpers, and domain/state structs that multiple studio modules depend on.

```
theme/layout/prompt constants
StudioTheme
panel_style
root_style
PreviewPromptCache
ExecutionContract
SessionLaunch
SessionState, SessionStatus
WorkspaceMode, ProviderMode, ProviderReadiness, ProviderState, AuthCheck
StudioEvent, FocusedPane, EditorChoice, EditorGuideState, DeleteConfirmationState, SessionStopConfirmationState
PendingStudioAction
ProbeCache, CachedProbeEntry, ClaudeAuthStatus, CapturedCommand
```

Tests: focused_pane_*, provider_mode_*, workspace_mode_*, editor_choice_*, provider_readiness_*

### providers.rs (~700 lines)
All provider probing, auth, caching. Pure functions, no StudioState mutation.

```
default_provider_mode
probe_claude_readiness
probe_codex_readiness
assess_claude_help
assess_codex_exec_help
check_claude_auth
check_codex_auth
run_claude_live_probe
run_codex_live_probe
run_command_with_timeout
make_probe_dir
claude_probe_output_contains_ok
summarize_command_failure
probe_cache_path
load_cached_live_probe
save_cached_live_probe
load_probe_cache
readiness_summary
header_readiness_label
log_provider_probe
display_model_name
command_exists
```

Tests: codex_probe_*, claude_probe_*, header_readiness_*, default_provider_mode_*, live_probe_*

### attachments.rs (~700 lines)
Attachment resolution, path validation, directory tree, format block, sidecar I/O, picker.

```
attachment_requested_display_path
attachment_path_has_parent_reference
is_external_attachment_path
external_attachment_count
normalize_absolute_display_path
normalize_relative_display_path
attachment_display_label
attachment_mode_label
attachment_error
truncate_with_notice
human_readable_bytes
directory_has_children
collect_directory_tree_lines
render_directory_tree
resolve_attachment_with_root
resolve_attachment
resolve_all_attachments
format_attachments_block
attachment_sidecar_path
attachment_mode_summary
load_attachment_specs
persist_attachment_specs
open_attachment_manager
cycle_attachment_manager_selection
toggle_selected_attachment_mark
remove_selected_execution_contract_attachments
infer_attachment_spec_from_selected_path
append_attachment_specs_for_paths
pick_attachment_paths (macOS, #[cfg])
pick_attachment_paths (non-macOS, #[cfg])
queue_selected_execution_contract_attachment_action
```

Tests: attachment_sidecar_path_*, load_attachment_specs_*, resolve_attachment_*, format_attachments_*, append_attachment_specs_*, attachment_manager_*

### prompt.rs (~200 lines)
Prompt composition and preview.

```
compose_smoothed_prompt
render_execution_contract_body
follow_up_context
follow_up_workspace_issue
```

Tests: smoothed_prompt_*, compose_smoothed_prompt_*, follow_up_*

### scan.rs (~200 lines)
Project discovery only.

```
scan_project
collect_matching_paths
collect_matching_paths_inner
collect_output_targets
```

Tests: project_scan_*

### shared.rs (~60 lines)
Cross-cutting helpers already shared by multiple extracted modules.

```
join_or_none
should_skip_snapshot_path
```

Tests: join_or_none_*, snapshot_skip_rules_*

### contracts.rs (~300 lines)
Contract CRUD, cycling, sidecar lifecycle.

```
execution_contracts_dir
execution_contract_selection_path
default_execution_contract_content
new_execution_contract_content
ensure_execution_contracts_exist
load_execution_contracts
load_execution_contracts_with_selection
execution_contract_name
persist_selected_execution_contract
cycle_execution_contract
create_execution_contract
edit_selected_execution_contract
delete_selected_execution_contract
execution_contract_list_label
```

Tests: execution_contract_list_label_*, load_execution_contracts_*, create_execution_contract_*, delete_selected_execution_contract_*

### session.rs (~650 lines)
Session lifecycle, workspace, artifacts.

```
start_sessions
run_session
prepare_workspace
copy_workspace_snapshot
copy_workspace_snapshot_inner
discover_artifacts
collect_recent_artifacts
```

Tests: start_sessions_*, prepare_workspace_*, discover_artifacts_*

### ui/layout.rs (~800 lines)
Layout structs, resize math, hit testing, pane styles.

```
StudioLayout
StudioLayoutConfig
ResizeHandle
ResizeDragState
studio_layout
centered_rect
output_style
current_studio_layout
clamped_left_column_width
left_content_height
right_content_height
resize_handle_at
apply_resize_drag
pane_at_position
rect_contains
pane_border_style
pane_title_style
pane_border_type
provider_color
studio_spinner
wrap_text_lines
truncate_display_path
```

Tests: pane_hit_testing_*, resize_handle_*, dragging_*, column_split_*, studio_output_style_*

### ui/render.rs (~760 lines)
Pane rendering and render-specific display helpers.

```
render (top-level dispatcher)
render_resize_handles
render_resize_handle
header_keybinding_text
render_header
render_scan
render_prompt
render_contracts
render_preview
render_sessions
format_session_list_line
session_elapsed_seconds
render_output
render_activity
render_status
session_status_color
prompt_text_for_display
preview_text_for_display
```

Tests: prompt_text_for_display_*, preview_text_for_display_*, completed_session_elapsed_time_*

### ui/modals.rs (~275 lines)
Modal rendering.

```
render_editor_guide
render_delete_confirmation
render_session_stop_confirmation
render_attachment_manager
```

Tests: (modal tests are mostly covered by input handler tests)

### ui/input.rs (~1300 lines)
Key dispatch, mouse handling, prompt editing, modal key handlers.

```
handle_event
handle_editor_guide_key
handle_delete_confirmation_key
handle_attachment_manager_key
request_quit
cancel_running_sessions
can_stop_selected_session
request_stop_selected_session
confirm_stop_selected_session
is_quit_key
set_focused_pane
handle_prompt_edit_key
handle_global_key
handle_mouse_event
activate_pane_from_click
scroll_pane_by_mouse
scroll_preview
request_delete_selected_execution_contract
cycle_editor_choice
queue_editor_action
pending_action_label
handle_pending_action
open_file_in_editor
select_session_from_click
select_execution_contract_from_click
```

Also includes editor preference types and functions:
```
resolve_system_editor_command
resolve_editor_command
editor_choice_summary
editor_command_name
editor_help_lines
editor_selection_path
load_editor_choice
persist_editor_choice
```

Tests: clicking_*, scrolling_*, arrow_keys_*, enter_edits_*, t_opens_*, editor_guide_*, editor_choice_*, quit_*

### state.rs (~850 lines)
Theme catalog construction, StudioState, session handle state, preview cache orchestration, and small state helpers used by input/app.

```
ThemeCatalog
builtin_themes
parse_hex_color
parse_color_spec
apply_theme_overrides
build_theme_catalog
SessionControl
StudioState struct and impl
preview_prompt
invalidate_preview_cache
refresh_execution_contracts
sync_attachment_manager_selection
cycle_theme
append_prompt_text
format_byte_count
log
```

Tests: preview_prompt_uses_cache_*, cycle_theme_*, theme_catalog_*, cycling_execution_contract_*

### app.rs (~200 lines)
Event loop, terminal setup/teardown, terminal reader.

```
spawn_terminal_event_reader
run_tui
shutdown_active_sessions
```

Tests: shutdown_active_sessions_*

### mod.rs (~20 lines)
Thin re-exports only.

```rust
mod app;
mod attachments;
mod contracts;
mod model;
mod prompt;
mod providers;
mod scan;
mod session;
mod state;
mod ui;

pub use app::run_tui;
```

## Implementation Steps

### Step 1: Extract providers module
Cleanest seam. No StudioState mutation. Pure functions with self-contained I/O.

- [x] T1.1: Create `src/studio/` directory for extracted submodules
- [x] T1.2: Extract provider functions and their tests into `src/studio/providers.rs`
- [x] T1.3: Add `mod providers;` and `use` statements in the root studio module
- [x] T1.4: Verify tests pass, `cargo clippy` clean

### Step 2: Extract attachments module
Strong functional boundary. Includes picker behind #[cfg].

- [x] T2.1: Extract attachment functions and their tests into `src/studio/attachments.rs`
- [x] T2.2: Update imports in the root studio module
- [x] T2.3: Verify tests pass, `cargo clippy` clean

### Step 3: Extract prompt and scan modules

- [x] T3.1: Extract scan functions and tests into `src/studio/scan.rs`
- [x] T3.2: Extract prompt composition functions and tests into `src/studio/prompt.rs`
- [x] T3.3: Update imports in the root studio module
- [x] T3.4: Verify tests pass, `cargo clippy` clean once prompt extraction is complete

### Step 4: Extract contracts module

- [x] T4.1: Extract contract functions and tests into `src/studio/contracts.rs`
- [x] T4.2: Update imports in the root studio module
- [x] T4.3: Verify tests pass, `cargo clippy` clean

### Step 5: Extract session module

- [x] T5.1: Extract session functions and tests into `src/studio/session.rs`
- [x] T5.2: Update imports in the root studio module
- [x] T5.3: Verify tests pass, `cargo clippy` clean

### Step 6: Extract UI modules

- [x] T6.1: Create `src/studio/ui/` directory with `mod.rs`
- [x] T6.2: Extract layout functions, layout structs, and tests into `src/studio/ui/layout.rs`
- [x] T6.3: Extract pane rendering into `src/studio/ui/render.rs`
- [x] T6.4: Extract modal rendering into `src/studio/ui/modals.rs`
- [x] T6.5: Extract input handling, editor prefs, and tests into `src/studio/ui/input.rs`
- [x] T6.6: Verify tests pass, `cargo clippy` clean

### Step 7: Extract model, state, and app modules

- [x] T7.1: Extract shared structs, theme/layout/prompt constants, and style helpers into `src/studio/model.rs`
- [x] T7.2: Extract StudioState, theme catalog construction, and state helpers into `src/studio/state.rs`
- [x] T7.3: Extract run_tui and event loop into `src/studio/app.rs`
- [x] T7.4: Slim `studio.rs` to thin module wiring and re-exports
- [x] T7.5: Verify tests pass, `cargo clippy` clean
- [x] T7.6: Confirm `main.rs` requires no change because the public interface remains `studio::run_tui`

## Architecture Decisions

**Extraction order follows dependency direction.** Providers has zero inbound dependencies from other studio code. Attachments depends on model types but nothing else. Each step peels off a leaf, never a hub. The state/app split comes last because it requires all other modules to be stable first.

**Visibility is `pub(super)` by default.** Functions extracted into submodules use `pub(super)` unless they need to be visible outside `studio/`. Only `run_tui` is truly public.

**No behavior changes.** This is a pure structural refactor. No logic changes, no API changes, no new features. Every step must produce identical behavior verified by the current test suite.

**Commit per step.** Each step gets its own commit so the refactor is bisectable and reviewable.

## Risks and Open Questions

1. **Circular dependencies.** `state.rs` will depend on `model.rs`, `contracts.rs`, `attachments.rs`, `scan.rs`, and `providers.rs` for `StudioState::new` and `preview_prompt`. This is expected -- state is the integration point. The key constraint is that none of those modules depend back on state.

2. **Test helper sharing.** `test_state()`, `test_scan()`, `test_contract()` are used across many test modules. These should live in a `#[cfg(test)] mod test_helpers` in `mod.rs` or `state.rs` and be imported by other test modules.

3. **Large diffs.** Steps 6 and 7 touch the most code. If these are too large for comfortable review, they can be split into sub-steps (e.g., extract layout.rs first, then render.rs, etc.). The plan already structures step 6 this way.

4. **App-shell cleanup.** Complete. `run_tui`, terminal event reading, and shutdown orchestration now live in `app.rs`, and the root is reduced to thin module wiring.

5. **use statement churn.** Each extraction changes import paths. Functions that were module-private become `pub(super)` or `pub(in crate::studio)`. This is mechanical but noisy in diffs. Reviewers should focus on the module boundaries, not the use statements.

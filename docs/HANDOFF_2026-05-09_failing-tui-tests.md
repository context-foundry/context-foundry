# Handoff: Failing TUI Tests After Overnight F1.x Run

Date: 2026-05-09
Status: investigation in progress

## TL;DR

Overnight Foundry run completed all three queued F-tasks (F1.1, F1.2, F1.3)
and shipped them as `feat()` commits on `main`. Build is green
(`cargo build --release` succeeds). Tests are NOT fully green:
**2 failing tests in `tui::stats`** that need fixing.

```
test result: FAILED. 858 passed; 2 failed; 5 ignored
```

Failing tests:
- `tui::stats::tests::render_dashboard_stats_shows_dual_comparison_line_when_both_pipelines_finish`
- `tui::stats::tests::render_dashboard_stats_shows_na_in_dual_comparison_line_for_codex_without_usage`

## What was done overnight (already committed, do not redo)

The plan executed was `docs/PLAN_planner-vertical-slicing.md`. All three
steps merged cleanly:

| Commit | Task | Files touched |
|--------|------|---------------|
| `b789efc` | feat(F1.1): tighten `plan_has_verification` + add `plan_has_per_phase_verification` | `src/eval/checks/heuristic.rs`, `src/eval/checks/mod.rs`, `src/app/build.rs`, `src/app/state.rs`, `docs/eval-harness.md`, `docs/PLAN_planner-vertical-slicing.md` |
| `5a23fbd` | feat(F1.2): tighten `planner_prompt` for vertical slicing on 5+ file ops | `src/prompts.rs` |
| `49e9ca6` | feat(F1.3): reviewer prompt repetition cleanup | `src/prompts.rs` |

Notable detail: F1.1 also re-applied a pre-existing `eval_report_cache`
hydration in `src/app/state.rs` (`AppState::new` now calls
`crate::eval::report::read_report(&buildloop_dir)` and stores the result).
This was the same fix manually applied earlier in the prior session;
Foundry independently produced the same change during F1.1.

## What's broken

Run reproduces with:

```bash
cargo test tui::stats
```

Output:
```
running 9 tests
test tui::stats::tests::render_dashboard_stats_default_config_renders_qrpba_letters_in_order ... ok
test tui::stats::tests::render_dashboard_stats_uses_custom_stage_context_by_stage_id ... ok
test tui::stats::tests::render_dashboard_stats_omits_letters_for_disabled_pipeline_stages ... ok
test tui::stats::tests::render_dashboard_stats_shows_na_for_selected_codex_tab_without_usage ... ok
test tui::stats::tests::render_dashboard_stats_shows_na_for_selected_codex_pipeline_without_usage ... ok
test tui::stats::tests::render_dashboard_stats_uses_selected_dual_pipeline_metrics ... ok
test tui::stats::tests::render_dashboard_stats_uses_selected_claude_pipeline_context_in_dual_mode ... ok
test tui::stats::tests::render_dashboard_stats_shows_na_in_dual_comparison_line_for_codex_without_usage ... FAILED
test tui::stats::tests::render_dashboard_stats_shows_dual_comparison_line_when_both_pipelines_finish ... FAILED

assertion failed: rendered.contains("Claude: $1.25 (1Kin/250out) | Codex: $2.50 (2Kin/400out)")
   --> src/tui/stats.rs:779
assertion failed: rendered.contains("Claude: $1.25 (1Kin/250out)")
   --> src/tui/stats.rs:836
```

## What I've already ruled out

- **None of the F-tasks touched `src/tui/stats.rs` directly**:
  - F1.1 (b789efc) -- only `eval/checks/*`, `app/build.rs`, `app/state.rs`, docs
  - F1.2 (5a23fbd) -- only `src/prompts.rs`
  - F1.3 (49e9ca6) -- only `src/prompts.rs`
  - Last edit to `src/tui/stats.rs` was `af13de7` (E1.6, EVAL badge)
- **The format string in `dual_comparison_line()` matches the expected text**:
  - `src/tui/stats.rs:451-476` -- format is `"{label}: ${:.2} ({}in/{}out)"`
  - With `cost_usd=1.25`, `input_tokens=1000`, `output_tokens=250`,
    `format_compact_tokens(1000)` returns `"1K"`, `format_compact_tokens(250)`
    returns `"250"`, so the produced string IS
    `"Claude: $1.25 (1Kin/250out)"` -- character for character what the test asserts.
- **The test was added in `e722150`** (T15.3) long before any F-task ran.

## My current hypothesis

The string is being **produced correctly but truncated/wrapped during
ratatui rendering**. The render path is:

```rust
// src/tui/stats.rs:296-311
lines.push(Line::from(vec![
    Span::styled("  ", ...),
    Span::styled(
        format!("{:<width$}", ollama_left, width = half_width.saturating_sub(2)),
        ...,
    ),
    Span::styled("Timing    ", ...),
    Span::styled("session: ", ...),
    Span::styled(&session_str, ...),
    Span::styled("  task: ", ...),
    Span::styled(&task_str, ...),
]));
```

The test backend is `TestBackend::new(160, 6)` (160 wide). `half_width` is
derived from area width inside `render_dashboard_stats`. If half_width
< the comparison line's actual length (56 chars for the dual-finished
case), or if a downstream styled span pushes total line width past 160,
ratatui's Buffer will clip the right side and `rendered.contains(...)`
will fail.

The next agent should:

1. **Print the actual rendered output** to see what's actually in the
   buffer for the failing tests. Add a `println!("{}", rendered);` to
   the test temporarily and re-run with `cargo test tui::stats -- --nocapture`.
2. **Inspect `half_width` calculation** in `render_dashboard_stats`
   (search for `half_width = ` near the top of the function, probably
   around `src/tui/stats.rs:200-260`).
3. **Check if recent changes to `render_dashboard_stats`** (the EVAL badge
   line added in E1.6) shrunk the available width for the ollama row.

## How to investigate

```bash
# Reproduce
cd /Users/Shared/homelab/context-foundry
cargo test tui::stats::tests::render_dashboard_stats_shows_dual_comparison_line_when_both_pipelines_finish -- --nocapture

# Look at the renderer
sed -n '200,320p' src/tui/stats.rs   # render_dashboard_stats top + ollama row
sed -n '440,480p' src/tui/stats.rs   # dual_comparison_line
sed -n '767,840p' src/tui/stats.rs   # the failing tests

# History sanity check
git log --oneline -- src/tui/stats.rs | head
```

## Suggested fixes (in order of preference)

1. **If the comparison line is being width-truncated**: don't pad it
   with `{:<width$}` when it's already long. Either render the
   comparison line on its own row, or skip the padding when content
   exceeds available width.
2. **If a sibling Span widened the row beyond 160**: shorten the right
   side (Timing block) when dual_comparison is present.
3. **Last resort**: relax the test asserts to check for the segments
   separately (`contains("Claude: $1.25")` and `contains("Codex: $2.50")`).
   Only do this if there's a real reason the full string can't fit;
   otherwise it masks a UX regression where users won't see the full
   comparison either.

## Other context worth knowing

- **Build/install command** (after fixing): from
  `/Users/Shared/homelab/context-foundry/CLAUDE.md`:
  ```bash
  cargo build --release && cp target/release/foundry ~/.cargo/bin/ && \
    codesign -s - --force ~/.cargo/bin/foundry
  ```
- **Doubt loop preference**: This session's work was tied to the
  "Doubt in the Loop" rule in `~/.claude/CLAUDE.md`. After fixing the
  TUI tests, the auditor would expect a full `cargo test` run with
  860/860 green plus a manual eyeball at the dual-comparison row in a
  live TUI session before declaring done.
- **Prior session's working file**: the original plan that drove this
  work is at `docs/PLAN_planner-vertical-slicing.md`. Its Verification
  section listed `cargo test eval::checks::heuristic::` and overall
  `cargo test` passing 856+. The 2 TUI failures are an unintended
  side effect not anticipated by that plan.
- **No WIP commits**: All three F-tasks shipped as `feat()`. Do NOT
  treat this as a failed run; just fix the TUI tests as a follow-up.
- **Git restore point**: tag `v3.1.0` exists from before the eval
  harness work landed. `git diff v3.1.0 -- src/tui/stats.rs` shows
  what changed in this file across the whole eval-harness arc; useful
  if the test was already fragile before E1.6.
- **Working tree is clean**. No stash entries from this session need
  popping. The 16 stash entries shown by `git stash list` are all
  from unrelated older work.

## Quick recap of where this all came from

The 3 F-tasks were queued in `docs/PLAN_planner-vertical-slicing.md`
to address two issues found by an earlier eval harness run on
context-foundry's own M1.1 plan:

1. Foundry's `planner_prompt` produces **horizontal** plans by default
   (3 of 3 sampled plans were horizontal -- exactly the "1200-line
   untestable" antipattern from Patrick Debois's "Context Is the New
   Code" talk).
2. The eval harness's `plan_has_verification` heuristic implicitly
   rewarded the horizontal pattern by checking for "any verification
   section" without checking for **per-phase** verification.

F1.1 fixed the heuristic, F1.2 fixed the prompt, F1.3 was an optional
reviewer-prompt cleanup. All three landed cleanly. The TUI test
regression appears to be unrelated to the planner/heuristic changes;
it's likely a width-budget issue in the dual-comparison row that
went unnoticed when E1.6 added the EVAL badge line.

## What to do first when you resume

1. Read this file.
2. Add `println!("{}", rendered);` to the failing test, run
   `cargo test tui::stats::tests::render_dashboard_stats_shows_dual_comparison_line_when_both_pipelines_finish -- --nocapture`,
   look at the actual output.
3. Diagnose the truncation/width issue.
4. Fix the renderer (preferred) or relax the test (last resort).
5. Re-run full `cargo test`. Should be 860/860.
6. Rebuild and reinstall foundry per the CLAUDE.md command above.
7. Commit as `fix(tui): <description>` with auditor summary per
   `~/homelab/CLAUDE.md` "Commit & Change Protocol".

# Plan: OpenCode Provider - Startup Validation Fix
Date: 2026-04-20
Version: v1
Status: completed

## Context

We just finished wiring `opencode` as a third provider (alongside `claude` and
`codex`). After rebuilding and running `foundry` from a project dir, startup
fails:

```
Error: required provider CLI not found: codex (builder (dual)).
Install the missing CLI(s) or change the corresponding *.provider setting
in .foundry.json
```

`codex` is not installed on this machine. `claude` and `opencode` are.

## Current State

### Uncommitted changes on `main` (opencode work, not yet committed)
- `src/agent.rs` — adds `ModelProvider::OpenCode`, `opencode run` command builder, run_agent delegation
- `src/config.rs` — `parse_provider` accepts `"opencode"`, spec prefix detection for `lmstudio/`, `ollama/`, `opencode/`, adds `"third"` branch in `selected_pipeline_configs`
- `src/app/build.rs`, `src/app/startup.rs`, `src/app/state.rs` — third-selection UX plumbing
- `src/prompts.rs`, `src/patterns.rs`, `src/embeddings.rs`, `src/tui/running.rs`, `src/tui/startup.rs`, `src/main.rs` — supporting changes
- `src/history.rs` — NEW, untracked (build history / cross-session recall)

### Project config in use
`~/homelab/context-foundry/.foundry.json`:
```json
"builder_models": ["claude:opus", "codex:"],
"dual_selection": "first"
```

With `dual_selection: "first"`, only `builder_models[0]` (Claude) actually runs.
Startup still validates every entry in `builder_models`, so it demands `codex`.

## Root Cause

`src/app/commands.rs:256-261` in `required_providers()`:

```rust
if config.builder_models.len() >= 2 {
    for spec in config.builder_models.iter().take(2) {
        let (provider_str, _model) = Config::parse_model_spec(spec);
        v.push(("builder (dual)", Config::parse_provider(&provider_str)));
    }
}
```

Pre-existing bug. It validates all builder_models regardless of which
`dual_selection` will actually route to. With opencode now a third option and
users actively switching selections, this trap is much easier to hit.

Note: `commands.rs` is NOT in the current uncommitted diff. The bug predates
this work — the opencode addition just made it visible.

## Fix Options (decision pending)

### Option 1: Config-only unblock (30 seconds, kicks the can)
Edit `.foundry.json`:
- Replace `"codex:"` with an opencode spec, e.g. `"opencode:lmstudio/<model>"`, or
- Drop the second entry entirely: `"builder_models": ["claude:opus"]`

Unblocks immediately. Leaves the validation bug in place for anyone else
switching providers.

### Option 2: Code fix (~10 lines in `commands.rs` + test) — RECOMMENDED
Make `required_providers()` align with `Config::selected_pipeline_configs()` —
only validate the providers that the current `dual_selection` actually uses.

Sketch:
```rust
if config.builder_models.len() >= 2 {
    let selected_specs: &[&String] = match config.dual_selection.as_str() {
        "first"  if !config.builder_models.is_empty() => &[&config.builder_models[0]],
        "second" if config.builder_models.len() >= 2  => &[&config.builder_models[1]],
        "third"  if config.builder_models.len() >= 3  => &[&config.builder_models[2]],
        "both"   if config.builder_models.len() >= 2  => &[&config.builder_models[0], &config.builder_models[1]],
        _ => &[],
    };
    for spec in selected_specs {
        let (provider_str, _model) = Config::parse_model_spec(spec);
        v.push(("builder (dual)", Config::parse_provider(&provider_str)));
    }
}
```

Notes:
- The slice-of-refs shape above won't compile as-is; use `Vec<&str>` or pass
  specs by index. Sketch only.
- Add a unit test covering each `dual_selection` value (including `"third"`)
  with a missing CLI for the non-selected provider — should NOT appear in
  `missing` output.
- Keep `"both"` strict so dual-pipeline mode still demands both CLIs.

## Implementation Steps (if Option 2 chosen)

- [ ] Modify `required_providers()` in `src/app/commands.rs` to branch on
      `config.dual_selection`
- [ ] Add tests in the `tests` mod at bottom of `commands.rs`:
  - [ ] `dual_first_only_requires_first_builder_model_provider`
  - [ ] `dual_second_only_requires_second_builder_model_provider`
  - [ ] `dual_third_only_requires_third_builder_model_provider`
  - [ ] `dual_both_requires_both_builder_model_providers`
  - [ ] `empty_dual_selection_requires_no_builder_model_providers` (or base
        provider only — confirm intended behavior by re-reading
        `selected_pipeline_configs`)
- [ ] `cargo build --release && cp target/release/foundry ~/.cargo/bin/`
- [ ] Run `foundry` from a project dir to verify startup succeeds with
      `codex` absent
- [ ] Then fold into the SPID DOUBT cycle for the broader opencode work

## Open Questions

- Is `codex` being retired in favor of `opencode`, or do we want to keep both
  supported and the user just didn't install codex here? (Affects whether the
  `.foundry.json` also needs updating post-fix.)
- Should an empty/unknown `dual_selection` with `builder_models.len() >= 2`
  validate nothing, or validate `builder_models[0]` as a safe default? Check
  how `selected_pipeline_configs` falls through its `_ =>` arm (returns
  `self.clone()` — uses base `builder_provider`, not any `builder_models` entry).
- `builder_models[0]` is `"claude:opus"` — if the user intended opencode as the
  default builder now, that should probably change too. Not in scope for this
  fix but worth flagging.

## Resume Instructions (tomorrow)

1. Read this file.
2. `cd ~/homelab/context-foundry && git status` — confirm the uncommitted
   opencode work is still present.
3. Decide Option 1 vs Option 2 (Option 2 recommended).
4. If Option 2: follow Implementation Steps above.
5. After startup works, return to the broader opencode integration work and
   run the SPID DOUBT cycle over the full diff (all 11 modified files +
   `src/history.rs`) before committing.

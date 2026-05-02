---
paths:
  - "src/app.rs"
  - "src/app/**/*.rs"
  - "src/main.rs"
  - "src/agent.rs"
  - "Cargo.toml"
---

# Architecture

## Build Loop Pipeline
```
Load Patterns → SCOUT → PLAN → [gate] → BUILD → [gate] → DOUBT → GIT COMMIT
```

Simple tasks (classified by complexity.rs) may skip Scout and/or Plan, going straight
to Build with the task description as the spec. Doubt can also be skipped for simple
tasks with learned trust (doubt-history clustering).

Prerequisite gates between stages block execution if preconditions aren't met:
- gate_builder: requires current-plan.md with `## File Operations` and `## Verification`
- gate_reviewer: warns if build-claims.md is missing (reviewer falls back to changed files)

If a gate fails, the planner is retried once with the validation error appended
(retry-with-error-feedback). If retry also fails, the task is blocked.

When TASKS.md completes, a DISCOVERY agent scans for new work and appends tasks.

## Dual-Model Arena

`arena_mode` in .foundry.json is the controlling field: `"solo"` runs one pipeline,
`"dual"` runs two. Toggled from the Settings overlay (Arena field).

When `arena_mode == "dual"`, `selected_pipeline_configs()` unconditionally returns
two configs:
- Pipeline A: `self` with `arena_mode` reset to `"solo"`, `builder_models` and
  `dual_selection` cleared.
- Pipeline B: `self.pipeline_b_config()` -- inherits A then overrides any stage
  whose `b_<stage>_provider` field is non-empty (per-stage routing for B).

`legacy `builder_models` / `dual_selection` are still consulted in solo mode for
single-pipeline routing (`first`/`second`/`third`), but they no longer trigger
dual mode -- only `arena_mode == "dual"` does.

Key invariants:
- Guards must be written as `arena_mode == "dual"` (positive match), not
  `!= "solo"`. The serde default for `arena_mode` is `""` (not `"solo"`), so
  negative guards misfire on configs that omit the field.
- Selecting a local model snapshots `arena_mode` into `prev_arena_mode` and forces
  `arena_mode = "solo"` for the duration of the local-model run.
  `clear_builder_routing` restores it.
- Pipeline B excludes Scout (outer-loop bootstrap), Discovery, Fixer, PR review,
  and Pattern extraction -- those run once per task, not once per pipeline.

In dual mode, worktrees live at `.buildloop/arena/{provider}/` with independent
.buildloop/ dirs. TUI tab switching (1/2) shows each pipeline's output. No
automated winner selection.

## Global Config

`~/.foundry/config.json` provides defaults for all projects. Project `.foundry.json` overrides.
`Config::load()` reads global first, then merges project fields on top.

## Module Responsibilities

| Module | Role |
|--------|------|
| `app.rs` | Build loop orchestration, TUI event loop |
| `agent.rs` | Spawns Claude CLI in PTY, parses stream-json output |
| `prompts.rs` | Role-specific prompt generation (planner/builder/reviewer/fixer/discovery) |
| `patterns.rs` | Load, match, merge, extract learned patterns |
| `config.rs` | `.foundry.json` settings with serde defaults |
| `task.rs` | Parse TASKS.md (`- [ ] T1.1: desc` format) |
| `tui.rs` | Ratatui terminal UI with per-role color coding |
| `git.rs` | Commit (`feat(T1.1):` or `WIP(T1.1):`) and push |
| `complexity.rs` | Task complexity classification (Simple/Medium/Complex) |
| `embeddings.rs` | Ollama-backed semantic pattern matching with cache |
| `utils.rs` | UTF-8 safe string truncation |
| `update.rs` | Self-update from GitHub releases |

## Event System
- `AppEvent` enum drives the TUI: `AgentOutput`, `AgentDone`, `LoopEvent`, `Key`, `Tick`, `UpdateAvailable`
- `LoopEvent` enum drives the build loop: `TaskStarted`, `AgentStarted`, `TaskCompleted`, `DiscoveryStarted`, etc.
- 100ms tick interval (10 fps) for TUI rendering.

## Per-Stage Routing
`stage_overrides` in `.foundry.json` lists stage IDs whose provider/model are pinned.
`Config::for_pipeline()` skips overridden stages when applying global builder selection.
`Config::active_routing_for_stage(stage_id)` is the single source of truth for dispatch.
Stage aliases: build/implement, audit/doubt, discovery/discover, pattern_extraction/patterns.
See `docs/per-stage-routing.md` for the full reference.

## Progress Indicators
Completed tasks use QRPBA indicators: Q=Query, R=Research, P=Plan, B=Build, A=Audit.
`-` = skipped, `+` = deferred, `!` = failed audit. Internal stage IDs remain
`query`, `research`, `plan`, `implement`, `doubt`. See `docs/progress-indicators.md`.

## Agent Invocation
- Claude CLI spawned in PTY (portable-pty) for line-buffered output.
- `--output-format stream-json` for structured event parsing.
- 180-second default idle timeout (`agent_timeout_secs`), configurable via `.foundry.json`.
- `CLAUDECODE=""` env var prevents nested Claude detection.

## Review Gate
- PASS = audit report contains "PASS" verdict AND no HIGH/MEDIUM findings.
- Reviewer has few-shot severity examples with borderline calibration (HIGH=unchecked user input, LOW=test-only return value, SKIP=unwrap on constant).
- Multi-pass review for large changesets (8+ files): per-file analysis + cross-file integration pass.
- Each finding includes: file, line, issue, category, source_evidence (snippet + line_range + reasoning), confidence (0.0-1.0).
- Findings below confidence_threshold (default 0.5) are logged for manual review, not auto-fixed.
- Explicit criteria define what to report vs skip (not confidence-based filtering for severity, but confidence-based routing for fix decisions).

## Key Files (Don't Modify Without Asking)
- `CLAUDE.md` — project instructions
- `TASKS.md` — task list (only the build loop marks tasks complete)
- `.buildloop/` — ephemeral build state

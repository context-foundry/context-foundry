# Architecture

## Build Loop Pipeline
```
Load Patterns → PLANNER → BUILDER → REVIEWER → FIXER (up to 2 passes) → GIT COMMIT
```

When IMPL_PLAN.md completes, a DISCOVERY agent scans for new work and appends tasks.

## Module Responsibilities

| Module | Role |
|--------|------|
| `app.rs` | Build loop orchestration, TUI event loop |
| `agent.rs` | Spawns Claude CLI in PTY, parses stream-json output |
| `prompts.rs` | Role-specific prompt generation (planner/builder/reviewer/fixer/discovery) |
| `patterns.rs` | Load, match, merge, extract learned patterns |
| `config.rs` | `.foundry.json` settings with serde defaults |
| `task.rs` | Parse IMPL_PLAN.md (`- [ ] T1.1: desc` format) |
| `tui.rs` | Ratatui terminal UI with per-role color coding |
| `git.rs` | Commit (`feat(T1.1):` or `WIP(T1.1):`) and push |
| `utils.rs` | UTF-8 safe string truncation |
| `update.rs` | Self-update from GitHub releases |

## Event System
- `AppEvent` enum drives the TUI: `AgentOutput`, `AgentDone`, `LoopEvent`, `Key`, `Tick`, `UpdateAvailable`
- `LoopEvent` enum drives the build loop: `TaskStarted`, `AgentStarted`, `TaskCompleted`, `DiscoveryStarted`, etc.
- 100ms tick interval (10 fps) for TUI rendering.

## Agent Invocation
- Claude CLI spawned in PTY (portable-pty) for line-buffered output.
- `--output-format stream-json` for structured event parsing.
- 600-second default timeout, configurable via `.foundry.json`.
- `CLAUDECODE=""` env var prevents nested Claude detection.

## Review Gate
- PASS = audit report contains "PASS" verdict AND no HIGH/MEDIUM findings.
- Fixer gets up to 2 passes. After pass 2, final verdict is accepted regardless.
- Convergence check: parse findings JSON for severity counts.

## Key Files (Don't Modify Without Asking)
- `CLAUDE.md` — project instructions
- `IMPL_PLAN.md` — task list (only the build loop marks tasks complete)
- `.buildloop/` — ephemeral build state

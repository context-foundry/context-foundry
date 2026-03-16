---
paths:
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

Prerequisite gates between stages block execution if preconditions aren't met:
- gate_builder: requires current-plan.md with `## File Operations` and `## Verification`
- gate_reviewer: warns if build-claims.md is missing (reviewer falls back to changed files)

If a gate fails, the planner is retried once with the validation error appended
(retry-with-error-feedback). If retry also fails, the task is blocked.

When TASKS.md completes, a DISCOVERY agent scans for new work and appends tasks.

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

## Agent Invocation
- Claude CLI spawned in PTY (portable-pty) for line-buffered output.
- `--output-format stream-json` for structured event parsing.
- 600-second default timeout, configurable via `.foundry.json`.
- `CLAUDECODE=""` env var prevents nested Claude detection.

## Review Gate
- PASS = audit report contains "PASS" verdict AND no HIGH/MEDIUM findings.
- Reviewer has few-shot severity examples (HIGH=security, MEDIUM=error-handling, LOW=style).
- Explicit criteria define what to report vs skip (not confidence-based filtering).
- Convergence check: parse findings JSON for severity counts.

## Key Files (Don't Modify Without Asking)
- `CLAUDE.md` — project instructions
- `TASKS.md` — task list (only the build loop marks tasks complete)
- `.buildloop/` — ephemeral build state

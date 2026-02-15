# Foundry

Autonomous build loop that plans, builds, validates, audits, and learns — forever.

Foundry reads an `IMPL_PLAN.md` task list and works through it using Claude Code agents in a TUI, committing each completed task. When all tasks are done, it discovers new work and keeps going.

## Task Flow

```
Load patterns from ~/.foundry/patterns/
  │
PLANNER (+ matched patterns) → .buildloop/current-plan.md
  │
BUILDER → implement plan
  │
VALIDATOR (+ patterns + runtime checks) → .buildloop/validation-report.md
  │  └─ if FAIL: FIXER → re-validate (up to 3x)
  │
AUDITOR (read-only doubt loop) → .buildloop/audit-report.md
  │  └─ if findings: FIXER → re-audit (converge on zero high/medium)
  │
PATTERN EXTRACTOR → merge into ~/.foundry/patterns/
  │
GIT COMMIT → feat(task_id) or WIP(task_id)
```

## Install

```bash
# Prerequisites: Rust toolchain + Claude Code CLI
cargo install --path .
```

Or build manually:

```bash
cargo build --release
# Binary at ./target/release/foundry
```

## Usage

Point foundry at any project directory that has an `IMPL_PLAN.md`:

```bash
# TUI mode (default)
foundry --dir /path/to/project

# Headless mode (CI/logs)
foundry --dir /path/to/project run --no-tui

# Check progress
foundry --dir /path/to/project status

# List all tasks
foundry --dir /path/to/project tasks
```

## Project Setup

A project needs two files to get started:

1. **`IMPL_PLAN.md`** — Task checklist (foundry reads and marks tasks done):
   ```markdown
   ## Phase 1
   - [ ] 1.1: Set up project scaffolding
   - [ ] 1.2: Implement authentication
   ```

2. **`ARCHITECTURE.md`** — What you're building (agents read this for context)

Optional:
- **`.foundry.json`** — Override defaults:
  ```json
  {
    "planner_model": "opus",
    "builder_model": "sonnet",
    "validator_model": "opus",
    "auditor_model": "opus",
    "max_fix_attempts": 3,
    "max_audit_iterations": 3,
    "patterns_dir": "~/.foundry/patterns"
  }
  ```
- **`CLAUDE.md`** — Project conventions (agents read this too)

## Extensions

Extensions are domain-specific knowledge packages that teach foundry agents how to work with specialized technologies. They contain guides, patterns, templates, and examples.

To use an extension, copy its `CLAUDE.md` and relevant docs into your project, or reference them from your project's `CLAUDE.md`.

See `extensions/` for available extensions.

## Architecture

- **config.rs** — Settings with serde defaults (backward-compatible JSON)
- **agent.rs** — Spawns Claude CLI in a PTY for real-time streaming
- **patterns.rs** — Load, match, format, merge, and extract learned patterns
- **prompts.rs** — Agent prompts (planner, builder, validator, fixer, auditor, discovery)
- **app.rs** — Build loop orchestration, audit loop, pattern extraction
- **tui.rs** — Ratatui terminal UI with live agent output
- **task.rs** — Parse IMPL_PLAN.md task lists
- **git.rs** — Commit and push helpers

## Previous Version

The Python MCP server + daemon that preceded this Rust rewrite is archived at:
- **Tag:** `v1.0-python`
- **Branch:** `archive/python-mcp`

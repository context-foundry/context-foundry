# Foundry

Autonomous build loop that plans, builds, reviews, and learns — forever.

Foundry reads an `IMPL_PLAN.md` task list and works through it using Claude Code agents in a TUI, committing each completed task. When all tasks are done, it discovers new work and keeps going.

## Task Flow

```
Load patterns from ~/.foundry/patterns/
  │
PLANNER (+ matched patterns) → .buildloop/current-plan.md
  │
BUILDER → implement plan
  │
REVIEWER (+ patterns + runtime checks) → .buildloop/review-report.md
  │  └─ if FAIL: FIXER → re-review (up to 2 passes)
  │
PATTERN EXTRACTOR → merge into ~/.foundry/patterns/
  │
GIT COMMIT → feat(task_id) or WIP(task_id)
```

## Install

```bash
# From source (requires Rust toolchain + Claude Code CLI)
cargo install --git https://github.com/context-foundry/context-foundry foundry
```

Or via Homebrew (once a release is published):

```bash
brew tap context-foundry/tap
brew install foundry
```

Or build locally:

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

# Self-update to latest release
foundry update
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
    "reviewer_model": "opus",
    "fixer_model": "opus",
    "patterns_dir": "~/.foundry/patterns"
  }
  ```
- **`CLAUDE.md`** — Project conventions (agents read this too)

## Agent Prompts

All agent prompts are defined in [`src/prompts.rs`](src/prompts.rs). Each agent has a dedicated prompt function:

| Agent | Function | Purpose |
|-------|----------|---------|
| Planner | `planner_prompt()` | Creates implementation plans from task descriptions |
| Builder | `builder_prompt()` | Implements the plan, runs stack-appropriate build checks |
| Reviewer | `reviewer_prompt()` | Combined validation + audit with structured findings |
| Fixer | `fixer_prompt()` | Fixes HIGH/MEDIUM issues from the review report |
| Discovery | `discovery_prompt()` | Scans the codebase for new tasks |
| Pattern Extractor | `pattern_extraction_prompt()` | Extracts reusable patterns from completed work |

Prompts are compiled into the binary. To customize them, edit `src/prompts.rs` and rebuild.

Key design decisions in the prompt system:
- **Stack-aware**: agents detect the tech stack from repo files (Cargo.toml, package.json, pyproject.toml) rather than assuming a specific language
- **Safe by default**: the reviewer only runs read-only checks (no `docker compose up`, no service mutations)
- **Pattern isolation**: learned patterns are injected as clearly delimited reference data, not as authoritative instructions
- **Evidence-based review**: every finding must cite file, line number, and concrete evidence

## Extensions

Extensions are domain-specific knowledge packages that teach foundry agents how to work with specialized technologies. They contain guides, patterns, templates, and examples.

To use an extension, copy its `CLAUDE.md` and relevant docs into your project, or reference them from your project's `CLAUDE.md`.

See `extensions/` for available extensions.

## Architecture

- **config.rs** — Settings with serde defaults (backward-compatible JSON)
- **agent.rs** — Spawns Claude CLI in a PTY for real-time streaming
- **patterns.rs** — Load, match, format, merge, and extract learned patterns
- **prompts.rs** — Agent prompts (planner, builder, reviewer, fixer, discovery, pattern extractor)
- **update.rs** — Self-update from GitHub Releases with checksum verification
- **app.rs** — Build loop orchestration, review loop, pattern extraction
- **tui.rs** — Ratatui terminal UI with live agent output
- **task.rs** — Parse IMPL_PLAN.md task lists
- **git.rs** — Commit and push helpers

## Previous Version

The Python MCP server + daemon that preceded this Rust rewrite is archived at:
- **Tag:** `v1.0-python`
- **Branch:** `archive/python-mcp`

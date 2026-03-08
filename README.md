# Foundry

Autonomous build loop that plans, builds, reviews, and learns — forever.

Foundry reads an `IMPL_PLAN.md` task list and works through it using Claude Code agents in a TUI, committing each completed task. When all tasks are done, it discovers new work and keeps going.

## Demos

- [Building a Second Brain with the Loop](https://youtu.be/VO_c2j0dPH0) — Foundry autonomously works through an implementation plan, building a second-brain app from a task list while the TUI streams each agent's output in real time.
- [Enhancing the Second Brain with the Loop](https://youtu.be/wL0RLml2Tio) — A follow-up run where foundry picks up where it left off, discovering new work and iterating on the second-brain app with patterns learned from the first pass.

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

## How It Works

Foundry is a harness for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Each agent (planner, builder, reviewer, fixer, discoverer) is a Claude Code CLI invocation with a role-specific prompt and scoped tool access. The Rust binary handles orchestration, streaming, and state — Claude does all the reasoning and file editing.

### The loop

Without guardrails, an autonomous build loop degrades fast. Task 3 builds on task 2's mistakes, which built on task 1's mistakes. Errors compound and the codebase drifts from the intended architecture.

Foundry's loop is designed around two forms of backpressure:

**Short-term: the review gate.** After the builder finishes, a reviewer agent audits the changes — running build checks, linting, tests, and a structured code audit. If the reviewer finds HIGH or MEDIUM severity issues, a fixer agent addresses them, and the reviewer runs again. This happens up to 2 passes. If the work passes, it gets a `feat(task-id)` commit. If it still fails after 2 passes, it gets a `WIP(task-id)` commit — a signal that the work isn't validated and shouldn't be built on confidently. The review gate prevents bad code from silently flowing forward.

**Long-term: pattern learning.** After each validated task, a pattern extractor agent scans the build artifacts, review findings, and plan to extract reusable lessons (e.g., "CFrame not Position for moving Roblox parts" or "always validate UTF-8 boundaries before string slicing"). These get saved as structured JSON to `~/.foundry/patterns/`. On the next task — in any project — matched patterns are injected into the planner and reviewer prompts as reference data. Patterns that recur 3+ times get auto-promoted, meaning they're always included. This is how the system gets better over time: a mistake made once becomes a check applied everywhere.

### Pattern scope

Patterns are global by default. They live in `~/.foundry/patterns/` and are loaded for every project on your machine. A lesson learned building project A is available when building project B.

If you want per-project isolation, set `patterns_dir` in `.foundry.json` to a project-local path.

### Discovery

When all tasks in `IMPL_PLAN.md` are complete, foundry doesn't stop. A discovery agent scans the codebase — reading architecture docs, looking for TODOs/FIXMEs, checking for failed tests, spotting inconsistencies — and appends new tasks to `IMPL_PLAN.md`. The loop then works through those. If discovery finds nothing, it sleeps and tries again later.

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

Prebuilt GitHub Release binaries are published for macOS, Linux, and Windows x86_64. `foundry update` uses those release assets directly.

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

# Interactive prompt-driven studio for Claude, Codex, or both
foundry --dir /path/to/project studio

# Headless mode (CI/logs)
foundry --dir /path/to/project run --no-tui

# Check progress
foundry --dir /path/to/project status

# List all tasks
foundry --dir /path/to/project tasks

# Self-update to latest release
foundry update
```

Studio is documented separately in [`docs/foundry-studio-readme.md`](docs/foundry-studio-readme.md) because it is a different workflow from the autonomous `run` loop.

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

Foundry does not ship with any extensions. Extensions are something you create yourself — domain-specific knowledge packages that teach foundry's agents how to work with your particular technologies, APIs, or workflows.

An extension is just a folder containing guides, patterns, templates, and examples (e.g., a `CLAUDE.md` with rules, a patterns JSON with learned issues). Foundry provides the framework: agents already know how to read `CLAUDE.md` files for project conventions, and the pattern system already knows how to load and match JSON pattern files. You supply the domain knowledge.

To use an extension, copy its `CLAUDE.md` and relevant docs into your project, or reference them from your project's `CLAUDE.md`.

## Architecture

- **config.rs** — Settings with serde defaults (backward-compatible JSON)
- **agent.rs** — Spawns Claude CLI in a PTY for real-time streaming
- **patterns.rs** — Load, match, format, merge, and extract learned patterns
- **prompts.rs** — Agent prompts (planner, builder, reviewer, fixer, discovery, pattern extractor)
- **studio/** — Prompt-driven multi-model TUI with workspace isolation, artifact capture, and modular Studio app/state/UI code
- **update.rs** — Self-update from GitHub Releases with checksum verification
- **app.rs** — Build loop orchestration, review loop, pattern extraction
- **tui.rs** — Ratatui terminal UI with live agent output
- **task.rs** — Parse IMPL_PLAN.md task lists
- **git.rs** — Commit and push helpers

## Previous Version

The Python MCP server + daemon that preceded this Rust rewrite is archived at:
- **Tag:** `v1.0-python`
- **Branch:** `archive/python-mcp`

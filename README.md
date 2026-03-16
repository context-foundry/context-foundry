# Foundry

Autonomous build loop that plans, builds, reviews, and learns — forever.

Foundry reads a `TASKS.md` task list and works through it using Claude Code agents in a TUI, committing each completed task. When all tasks are done, it discovers new work and keeps going.

## Demos

- [Building a Second Brain with the Loop](https://youtu.be/VO_c2j0dPH0) — Foundry autonomously works through an implementation plan, building a second-brain app from a task list while the TUI streams each agent's output in real time.
- [Enhancing the Second Brain with the Loop](https://youtu.be/wL0RLml2Tio) — A follow-up run where foundry picks up where it left off, discovering new work and iterating on the second-brain app with patterns learned from the first pass.

## Task Flow

```
Load patterns from ~/.foundry/patterns/
  │
SCOUT → .buildloop/scout-report.md (investigate codebase)
  │
PLAN (+ patterns + scout report) → .buildloop/current-plan.md
  │
IMPLEMENT → build the code, run checks
  │
VERIFY (fresh context) → audit claims, fix issues, write verdict
  │
PATTERN EXTRACTOR → merge into ~/.foundry/patterns/
  │
LOCAL GIT COMMIT → feat(task_id) or WIP(task_id)
  │
OPTIONAL AUTO-PUSH → only if `auto_push_remote` is configured
```

## How It Works

Foundry is a harness for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Each agent (planner, builder, reviewer, fixer, discoverer) is a Claude Code CLI invocation with a role-specific prompt and scoped tool access. The Rust binary handles orchestration, streaming, and state — Claude does all the reasoning and file editing.

### The loop

Without guardrails, an autonomous build loop degrades fast. Task 3 builds on task 2's mistakes, which built on task 1's mistakes. Errors compound and the codebase drifts from the intended architecture.

Foundry's loop is designed around two forms of backpressure:

**Short-term: the verify gate.** After implementation, a verify agent audits the changes in a fresh context -- running build checks, tests, and a structured code audit. If it finds HIGH or MEDIUM issues, it fixes them and re-runs verification. If everything passes, the task gets a `feat(task-id)` commit. If issues remain, it gets a `WIP(task-id)` commit. The verify gate prevents bad code from silently flowing forward.

**Pipeline tracking (SPID).** Every task carries a 4-character progress indicator that records which pipeline stages ran and whether they succeeded. The indicator is persisted in `TASKS.md` next to each task and committed with the code, so you get a permanent audit trail.

```
- [x] T1.1: Set up project scaffolding          [SPID]
- [x] T1.2: Implement auth flow                 [S-ID]
- [x] T1.3: Add rate limiting                   [SPID!]
- [ ] T1.4: Write integration tests             [....]
```

Each character represents a pipeline stage:

| Position | Stage | Meaning |
|----------|-------|---------|
| 1 | **S** = Scout ran | **-** = scout skipped |
| 2 | **P** = Plan ran | **-** = planner skipped (simple task) |
| 3 | **I** = Implement ran | |
| 4 | **D** = Doubt ran | **-** = doubt skipped |
| suffix | **!** = verify did not pass | (absent) = clean pass |

Examples: `SPID` = full pipeline, clean pass. `S-ID` = planner skipped, scouted and implemented and verified. `SPID!` = full pipeline but verify found unfixable issues (WIP commit).

The TUI shows these indicators in the task queue with color coding, and they survive across restarts since they're written directly into the task file.

**Why a fresh context matters.** The verify agent runs in a completely separate Claude session with no shared history from the builder. This is intentional. A model that just wrote the code retains its reasoning context and is less likely to question its own decisions. An independent instance -- given only the claims and the code -- catches bugs the author is blind to. This is the same multi-instance review architecture described in Anthropic's [Claude Certified Architect](https://www.anthropic.com/certifications) program as a production best practice for reliable AI-generated code.

**Long-term: pattern learning.** After each validated task, a pattern extractor agent scans the build artifacts, review findings, and plan to extract reusable lessons (e.g., "CFrame not Position for moving Roblox parts" or "always validate UTF-8 boundaries before string slicing"). These get saved as structured JSON to `~/.foundry/patterns/`. On the next task — in any project — matched patterns are injected into the planner and reviewer prompts as reference data. Patterns that recur 3+ times get auto-promoted, meaning they're always included. This is how the system gets better over time: a mistake made once becomes a check applied everywhere.

### Pattern scope

Patterns are global by default. They live in `~/.foundry/patterns/` and are loaded for every project on your machine. A lesson learned building project A is available when building project B.

If you want per-project isolation, set `patterns_dir` in `.foundry.json` to a project-local path.

### Discovery

When all tasks in `TASKS.md` are complete, foundry doesn't stop. A discovery agent scans the codebase — reading architecture docs, looking for TODOs/FIXMEs, checking for failed tests, spotting inconsistencies — and appends new tasks to `TASKS.md`. The loop then works through those. If discovery finds nothing, it sleeps and tries again later.

## Install

### Pre-built binaries

Download from [GitHub Releases](https://github.com/context-foundry/context-foundry/releases/latest):

| Platform | File |
|----------|------|
| macOS (Apple Silicon) | `foundry-aarch64-apple-darwin.tar.gz` |
| macOS (Intel) | `foundry-x86_64-apple-darwin.tar.gz` |
| Linux (x86_64) | `foundry-x86_64-unknown-linux-gnu.tar.gz` |
| Windows (x86_64) | `foundry-x86_64-pc-windows-msvc.zip` |

Extract and move to a directory in your PATH. On macOS/Linux:

```bash
tar xzf foundry-*.tar.gz
sudo mv foundry /usr/local/bin/
```

On Windows (PowerShell):

```powershell
Expand-Archive foundry-x86_64-pc-windows-msvc.zip -DestinationPath .
```

If you have Rust installed, `%USERPROFILE%\.cargo\bin\` is already in your PATH:

```powershell
Move-Item foundry.exe C:\Users\$env:USERNAME\.cargo\bin\
```

If you don't have Rust, put it anywhere and add that folder to your PATH:

```powershell
mkdir C:\tools
Move-Item foundry.exe C:\tools\
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\tools", "User")
```

Open a new terminal and `foundry` works from any directory.

### From source (all platforms)

Requires [Rust](https://rustup.rs) and [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code).

```bash
cargo install --git https://github.com/context-foundry/context-foundry foundry
```

### macOS (Homebrew)

```bash
brew tap context-foundry/tap
brew install foundry
```

### Windows (from source, step by step)

For locked-down machines where unsigned binaries are blocked, compile from source:

1. Install [Rust](https://rustup.rs) (includes `cargo`)
2. Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (select "C++ build tools" workload)
3. Run in PowerShell:

```powershell
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry
cargo install --path .
```

The binary is compiled on your machine from source -- no unsigned downloads, no SmartScreen warnings. `foundry.exe` will be in `%USERPROFILE%\.cargo\bin\`.

Or if you have Claude Code, paste this prompt and let it handle everything:

> Clone and build Context Foundry. Run: `git clone https://github.com/context-foundry/context-foundry.git && cd context-foundry && cargo install --path .`

### Self-update

```bash
foundry update
```

## Usage

Point foundry at any project directory that has a `TASKS.md`:

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

1. **`TASKS.md`** — Task checklist (foundry reads and marks tasks done):
   ```markdown
   ## Phase 1
   - [ ] 1.1: Set up project scaffolding
   - [ ] 1.2: Implement authentication
   ```

2. **`SPEC.md`** — Project specification (auto-generated from your description, agents read this for context)

Optional:
- **`.foundry.json`** — Override defaults:
  ```json
  {
    "planner_model": "opus",
    "builder_model": "sonnet",
    "reviewer_model": "opus",
    "fixer_model": "opus",
    "patterns_dir": "~/.foundry/patterns",
    "auto_push_remote": "snedea"
  }
  ```
- **`CLAUDE.md`** — Project conventions (agents read this too)

Legacy projects that still use `ARCHITECTURE.md` and `IMPL_PLAN.md` continue to work. Foundry prefers `SPEC.md` and `TASKS.md` when both are present.

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
- **task.rs** — Parse TASKS.md task lists
- **git.rs** — Commit and push helpers

## Previous Version

The Python MCP server + daemon that preceded this Rust rewrite is archived at:
- **Tag:** `v1.0-python`
- **Branch:** `archive/python-mcp`

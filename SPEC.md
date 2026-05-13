# Specification: Context Foundry

Context Foundry is a Rust-based autonomous build loop for AI coding agents. It
plans, builds, validates, commits, and discovers more work, forever -- and it
learns reusable patterns from each task so the next agent starts smarter than
the last.

This document is the human-readable system spec. It describes what Context
Foundry IS and DOES today (not how it was built and not future plans). For
deep dives, follow the `docs/*.md` links below.

> Companion documents:
> - `CLAUDE.md` -- instructions consumed by in-loop agents (not for humans).
> - `.claude/rules/architecture.md` -- module-level architecture rules.
> - `docs/*.md` -- design notes, runbooks, and per-feature deep dives.

## 1. Overview

Context Foundry is a CLI binary (`foundry`) that drives a multi-stage pipeline
over the tasks listed in a project's `TASKS.md`. Each task flows through some
subset of these stages:

| Code | Stage | Role |
|------|-------|------|
| Q | Query | Optional clarifying-question pass when SPEC.md is ambiguous |
| R | Research | Read-only investigation of the codebase, writes `.buildloop/research-report.md` |
| P | Plan | Writes `.buildloop/current-plan.md` from the research report |
| P+ | Plan Review | Iterative review of the plan (`plan-review`) with bounded retries |
| B | Build (Implement) | Executes the plan, writes `.buildloop/build-claims.md` |
| A | Audit (Doubt) | Fresh-context agent that verifies every claim, writes `.buildloop/review-report.md` |
| SH | Self-Heal | Optional fix pass driven by the auditor's HIGH/MEDIUM findings |
| DI | Discovery | When `TASKS.md` empties, scans the repo for new work and appends tasks |

Completed tasks in `TASKS.md` carry a QRPBA indicator (e.g. `[Q-RPBA]`) where
`-` means skipped, `+` means deferred, and `!` means failed audit. See
[`docs/progress-indicators.md`](docs/progress-indicators.md).

The pipeline is task-driven and non-interactive. A human edits `TASKS.md`
(or lets Discovery append tasks), launches `foundry`, and watches the TUI;
every stage commits its artifacts to `.buildloop/` and -- on a PASS audit --
to git as `feat(T<id>): ...` or, on FAIL, as `WIP(T<id>): ...`.

## 2. Architecture

### 2.1 The QRPBA pipeline

The build loop in `src/app/build.rs` walks `TASKS.md` and, for each pending
task, dispatches the stages above. Gates between stages enforce
preconditions:

- `gate_builder` requires `current-plan.md` to contain `## File Operations`
  and `## Verification` headings.
- `gate_reviewer` warns when `build-claims.md` is missing (the reviewer falls
  back to inspecting changed files).

If a gate fails, the planner is retried once with the validation error
appended (retry-with-error-feedback). Failure after retry blocks the task.
See [`.claude/rules/architecture.md`](.claude/rules/architecture.md) for the
authoritative gate definitions.

### 2.2 Complexity-driven stage skipping

`src/complexity.rs` classifies each task as Simple / Medium / Complex. Simple
tasks may skip Scout (research) and/or Plan and go straight to Build with the
task description as the spec. Doubt can also be skipped for Simple tasks with
learned trust (doubt-history clustering in `src/doubt_confidence.rs`).
Per-task overrides (`[fast]`, `[strict]`) are documented in
[`docs/task-composition.md`](docs/task-composition.md).

### 2.3 Dual-pipeline arena mode

`arena_mode` in `.foundry.json` controls pipeline cardinality:
`"solo"` runs one pipeline; `"dual"` runs two in parallel for head-to-head
comparison. In dual mode, worktrees live at `.buildloop/arena/{provider}/`
with independent `.buildloop/` directories. The TUI exposes tab-switching
(`1` / `2`) between pipelines. There is no automated winner selection -- the
human reviews both.

Key invariant: guard with a positive match (`arena_mode == "dual"`), not a
negative one. The `Config::default()` impl initializes the field to `"solo"`,
but a real on-disk `.foundry.json` that omits the key deserializes through
serde's `String` default (`""`). A negative guard like `!= "solo"` would
misfire on those unset/legacy values; `== "dual"` routes them safely to the
solo path.

### 2.4 Per-stage routing

`stage_overrides` in `.foundry.json` pins specific stages to specific
provider/model pairs (e.g. Claude Opus on Plan, Codex on Build, an OpenCode
local model on Discovery). `Config::active_routing_for_stage(stage_id)` is
the single source of truth for dispatch. Stage aliases:
`build`/`implement`, `audit`/`doubt`, `discovery`/`discover`,
`pattern_extraction`/`patterns`. Full reference:
[`docs/per-stage-routing.md`](docs/per-stage-routing.md).

### 2.5 Skills & Plugins model

Patterns are an evolving substrate. The legacy JSON pattern format
(`~/.foundry/patterns/*.json`) is still read for back-compat, but new
learnings are written as Anthropic-format `SKILL.md` files (frontmatter
plus markdown body). See Section 5 below and
[`docs/cross-provider-skills.md`](docs/cross-provider-skills.md).

Plugins live under `plugins/<name>/` and bundle domain-specific skills,
templates, and rules (e.g. Flowise, Roblox, Workday Extend). The legacy
directory name `extensions/` is migrated to `plugins/` on first startup.
See [`docs/extensions-as-plugins.md`](docs/extensions-as-plugins.md).

### 2.6 Coach Mode

`run_mode = "coach"` inserts a non-interactive intake-clarification stage
before Scout: Coach reads `SPEC.md`, writes `.buildloop/intake-brief.md`,
and Scout consumes the brief. Reference:
[`docs/coach-mode.md`](docs/coach-mode.md).

### 2.7 Eval Harness

After every task, an eval harness grades the run against plumbing checks
(system prompts wired, patterns injected, prior artifacts read) and
heuristic outcome checks (plan covers research, claims include
verification, audit produced findings). It never blocks the pipeline.
Reference: [`docs/eval-harness.md`](docs/eval-harness.md).

## 3. Tech Stack

| Layer | Choice |
|-------|--------|
| Language | Rust 2021 edition |
| Async runtime | Tokio (`tokio = "1"`, full features) |
| TUI | `ratatui` 0.30 + `crossterm` 0.28 |
| Process management | `portable-pty` 0.8 for line-buffered subprocess output |
| HTTP | `reqwest` 0.12 (rustls) |
| Serialization | `serde` + `serde_json` |
| CLI parsing | `clap` 4 (derive) |
| Telemetry / storage | `rusqlite` 0.31 (bundled SQLite) for skills + observatory dbs |
| Config | JSON (`.foundry.json` per project, `~/.foundry/config.json` global) |
| Logging path | `.buildloop/logs/` JSONL session transcripts |

Agents are invoked as subprocesses, not via SDK:
`claude` CLI, `codex` CLI, and `opencode` CLI (LM Studio / Ollama gateway).
Streamed output is parsed from `--output-format stream-json` where supported.
The Claude CLI runs inside a PTY so it streams tokens line-buffered.

See [`docs/why-rust.md`](docs/why-rust.md) for the rationale behind the
language choice.

## 4. Key Components

All modules below live under `src/` and are declared in `src/main.rs`. One
line per module; cross-reference with
[`.claude/rules/architecture.md`](.claude/rules/architecture.md) for the
authoritative module-responsibility table.

### 4.1 Build-loop core

| Module | Role |
|--------|------|
| `app.rs` / `app/` | TUI event loop and build-loop orchestration (`build.rs`, `planning.rs`, `review.rs`, `startup.rs`, `commands.rs`, `context.rs`, `state.rs`, `contract.rs`, `tests.rs`) |
| `agent.rs` | Spawns CLI agents (Claude / Codex / OpenCode) in PTYs; parses stream-json |
| `prompts.rs` | Role-specific prompt generation (planner/builder/reviewer/fixer/discovery/coach) |
| `complexity.rs` | Task complexity classification (Simple / Medium / Complex) |
| `task.rs` | Parse `TASKS.md` (`- [ ] T1.1: desc` format) |
| `task_eval.rs` | Heuristic quality scoring of authored tasks |
| `git.rs` | Commit (`feat(T1.1):` PASS / `WIP(T1.1):` FAIL) and push |
| `update.rs` | Self-update from GitHub releases |
| `init.rs` | First-run scaffolding (`.foundry.json`, `TASKS.md` template) |
| `run_manifest.rs` | Per-stage manifest written into `.buildloop/run-manifest.json` |

### 4.2 Patterns, skills, and learning

| Module | Role |
|--------|------|
| `patterns.rs` | Load, score (BM25), merge, extract learned patterns (legacy JSON) |
| `skills.rs` | Anthropic SKILL.md parser, ranker (BM25 + bonuses), `synthesize_keywords` fallback |
| `skill_discovery.rs` | Cross-provider discovery (AGENTS.md, .cursorrules, .claude/skills/, Copilot) |
| `skills_telemetry.rs` | SQLite-backed citation telemetry at `~/.foundry/skills-telemetry.db` |
| `embeddings.rs` | Ollama-backed semantic match (`nomic-embed-text`) with on-disk cache |
| `plugins.rs` | Plugin discovery and migration from legacy `extensions/` |

### 4.3 Reviewers, evaluators, governance

| Module | Role |
|--------|------|
| `eval/` | Eval-harness checks (`plumbing.rs`, `heuristic.rs`, `mod.rs`), `report.rs`, `scorer.rs`, `parser.rs`, `stage_id.rs`, `run.rs` |
| `doubt_confidence.rs` | Confidence routing for audit findings (auto-fix vs surface) |
| `review_pr.rs` | PR-mode review (when a GitHub PR is targeted) |
| `observatory.rs` | Long-running telemetry rollups; SQLite store |
| `history.rs` | Per-task historical records used by complexity & doubt heuristics |
| `budget.rs` | Token/time budget tracking per stage |
| `stats.rs` | Aggregated stats (cost, duration, pass-rate) for the Stats panel |

### 4.4 LLM I/O and external integrations

| Module | Role |
|--------|------|
| `llm/mod.rs` | Provider-agnostic dispatch entry point |
| `llm/summary.rs` | AI-generated stage summaries surfaced in the TUI |
| `llm/summary_cache.rs` | OnceLock-backed cache for stage summaries |
| `model_catalog/mod.rs` + `sources.rs` | Provider/model catalog and pricing |
| `ghcopilot.rs` | GitHub Copilot custom-instructions ingestion |
| `mcp.rs` | MCP tool surface exposed to in-loop agents |
| `orchestrator.rs` | Cross-pipeline orchestration (arena coordinator) |
| `dashboard.rs` | Web/JSON dashboard surface |

### 4.5 TUI

| Module | Role |
|--------|------|
| `tui/mod.rs` | Top-level TUI glue |
| `tui/running.rs` | Running-task layout (left pane, panels, citation/retrieval) |
| `tui/startup.rs` + `welcome.rs` | Startup chooser and welcome screen |
| `tui/overlays.rs` | Settings overlay, modals |
| `tui/modal_spec.rs` | Modal layout descriptors |
| `tui/pipeline.rs` | Pipeline visualization (stage badges, dual-pane in arena mode) |
| `tui/stats.rs` | Stats panel renderer |
| `tui/narrative.rs` | Narrative/timeline panel |
| `tui/theme.rs` | Theme tokens (OnceLock cached) |

### 4.6 Plumbing

| Module | Role |
|--------|------|
| `config.rs` | `.foundry.json` schema and global/project merge |
| `utils.rs` | UTF-8 safe string utilities, home-dir resolution |
| `isolation.rs` | Worktree isolation for arena mode |
| `sandbox.rs` | Sandboxing primitives (filesystem/exec scoping) |
| `tmux.rs` | Optional tmux-backed run multiplexer |
| `sync_flag.rs` | Cross-task synchronization flag |
| `studio.rs` | Foundry Studio integration |

## 5. Skills & Plugins

### 5.1 Storage layout

| Location | Purpose |
|----------|---------|
| `~/.foundry/skills/<topic>/SKILL.md` | Global, cross-project skills (the 14 Superpowers skills install here via symlink) |
| `~/.foundry/patterns/*.json` | Legacy JSON patterns (still read; not written for new learnings) |
| `~/.foundry/config.json` | Global default config |
| `~/.foundry/skills-telemetry.db` | SQLite citation telemetry (per-skill / per-stage / per-task) |
| `plugins/<name>/skills/<topic>/SKILL.md` | Plugin-bundled domain skills |
| `plugins/<name>/CLAUDE.md` | Plugin-level agent rules |
| `<project>/.foundry/patterns/*.json` | Per-project legacy patterns |
| `<project>/.claude/skills/<topic>/SKILL.md` | Per-project Anthropic-format skills |

### 5.2 Cross-provider discovery

`src/skill_discovery.rs` walks four well-known source formats and surfaces
them in the startup "External Skills" panel for opt-in:

| Source | Path | Ancestor walk? |
|--------|------|----------------|
| AGENTS.md | `<project>/AGENTS.md` and ancestors up to `$HOME` | Yes |
| .cursorrules | `<project>/.cursorrules` | No |
| Anthropic SKILL.md | `<project>/.claude/skills/<topic>/SKILL.md` | No |
| Copilot | `<project>/.github/copilot-instructions.md` | No |

Discovered skills are read-only and OFF by default. Opt-in state is
persisted per project in `.foundry.json` under `external_skills_enabled`.
Full reference: [`docs/cross-provider-skills.md`](docs/cross-provider-skills.md).

### 5.3 Telemetry

`src/skills_telemetry.rs` records every skill citation made by the
planner/builder/reviewer/fixer/discovery agents into
`~/.foundry/skills-telemetry.db` (SQLite). The TUI "Skill Citations
(post-task)" panel renders aggregates (session, top-cited-this-week,
last-cited) and the optional "Skills Retrieved" panel (gated by
`show_retrieval_panel`) renders the retriever's per-stage top picks
at injection time.

### 5.4 Ranking

`keyword_scores` in `src/patterns.rs` is the BM25 ranker
(k1 = 1.5, b = 0.75) with bonuses for tech-stack match (+1 each),
`auto_apply` (+2), frequency >= 3 (+1), and rating tier (+3 / +1 / -2).
Off-stack patterns are penalized -3. Final score is multiplied by
`0.5 + 0.5 * success_rate`. Patterns whose `promoted_to` field is
non-empty are excluded.

For SKILL.md files without explicit `metadata.cf-keywords`,
`synthesize_keywords(pattern_id, description)` in `src/skills.rs`
derives a token list from the kebab-split id plus the description
(stopword-filtered, capped at 24 tokens). Curated overrides for the
14 Superpowers skills can be supplied via
`~/.foundry/skill-keywords-overrides.json`.

## 6. Build & Run

### 6.1 Rebuild and install

```bash
cd ~/homelab/context-foundry \
  && cargo build --release \
  && cp target/release/foundry ~/.cargo/bin/ \
  && codesign -s - --force ~/.cargo/bin/foundry
```

The running TUI does NOT hot-reload. Quit, rebuild, and relaunch to pick
up changes.

### 6.2 Run

```bash
cd ~/some-project        # any git repo with a TASKS.md
foundry                  # default: launch the TUI loop
foundry run --no-tui     # headless streaming-log mode
foundry status           # current progress snapshot
foundry tasks            # list parsed tasks
foundry plan             # dedicated planning mode (no building)
```

### 6.3 Smoke gates

| Gate | Command | What it proves |
|------|---------|----------------|
| Local-model routing | `bash scripts/smoke-local-model.sh` | OpenCode + LM Studio round-trip; zero claude invocations |
| Test suite | `cargo test --release` | Library + binary tests |
| Lint | `cargo clippy --all-targets -- -D warnings` | Clippy-clean at deny-warnings |
| Build | `cargo build --release` | Release binary builds |

The local-model smoke test runbook lives at
[`docs/local-model-setup.md`](docs/local-model-setup.md).

## 7. Configuration

`.foundry.json` (project) overrides `~/.foundry/config.json` (global) via
JSON object merge. All fields are `#[serde(default)]` and optional. The
schema lives in `src/config.rs`. Highlighted fields:

| Field | Type | Purpose |
|-------|------|---------|
| `arena_mode` | `"solo"` \| `"dual"` | Pipeline cardinality |
| `run_mode` | `"auto"` \| `"sprint"` \| `"review"` \| `"coach"` | Top-level run mode |
| `builder_provider` / `builder_model` | string | Default builder routing |
| `planner_provider` / `planner_model` | string | Planner routing |
| `reviewer_provider` / `reviewer_model` | string | Reviewer (audit) routing |
| `fixer_provider` / `fixer_model` | string | Self-heal routing |
| `discovery_provider` / `discovery_model` | string | Discovery routing |
| `stage_overrides` | array of `{stage, provider, model}` | Per-stage pinned routing |
| `pipeline_stages` | array of `{id, label, enabled}` | Skip whole stages cleanly |
| `agent_timeout_secs` | u64 | Idle timeout (default 600s, hard = 4x) |
| `review_multipass_threshold` | usize | Files-changed threshold for multi-pass review |
| `confidence_threshold` | f64 | Auto-fix vs surface threshold (default 0.5) |
| `skip_planner_for_simple` | bool | Complexity-driven plan skip |
| `external_skills_enabled` | map<path, bool> | Cross-provider skill opt-ins |
| `show_retrieval_panel` | bool | Show retriever top-picks panel in TUI |
| `semantic_match_enabled` | bool | Enable Ollama-backed semantic match |
| `ollama_url` | string | Ollama endpoint (default `http://127.0.0.1:11435`) |
| `auto_push_remote` | string \| null | If set, push commits to this remote |
| `create_issue_on_wip` | bool | File a GitHub issue on FAIL audit |
| `on_task_complete` | string \| null | Fire-and-forget shell hook after commit |

For per-stage routing details, see
[`docs/per-stage-routing.md`](docs/per-stage-routing.md). The Settings
Overlay (`?` in the TUI) exposes ~40 fields across 9 collapsible sections;
the full schema reference is at
[`docs/settings-overlay.md`](docs/settings-overlay.md).

## 8. Further reading

- Build loop pipeline rules: [`.claude/rules/architecture.md`](.claude/rules/architecture.md)
- Task composition guidance: [`docs/task-composition.md`](docs/task-composition.md)
- Progress indicator scheme (QRPBA): [`docs/progress-indicators.md`](docs/progress-indicators.md)
- Per-stage routing: [`docs/per-stage-routing.md`](docs/per-stage-routing.md)
- Settings overlay reference: [`docs/settings-overlay.md`](docs/settings-overlay.md)
- Local model setup: [`docs/local-model-setup.md`](docs/local-model-setup.md)
- Eval harness: [`docs/eval-harness.md`](docs/eval-harness.md)
- Cross-provider skills: [`docs/cross-provider-skills.md`](docs/cross-provider-skills.md)
- Coach mode: [`docs/coach-mode.md`](docs/coach-mode.md)
- Extensions-as-plugins migration: [`docs/extensions-as-plugins.md`](docs/extensions-as-plugins.md)
- Why Rust: [`docs/why-rust.md`](docs/why-rust.md)
- Observability: [`docs/observability.md`](docs/observability.md)
- TUI conventions: [`docs/tui-conventions.md`](docs/tui-conventions.md)
- Patterns migration (skills): [`docs/patterns-migration.md`](docs/patterns-migration.md)
- AI stage summaries: [`docs/ai-stage-summaries.md`](docs/ai-stage-summaries.md)
- JIT knowledge injection: [`docs/jit-knowledge-injection.md`](docs/jit-knowledge-injection.md)
- Model catalog: [`docs/model-catalog.md`](docs/model-catalog.md)
- Sandbox model: [`docs/sandbox.md`](docs/sandbox.md)

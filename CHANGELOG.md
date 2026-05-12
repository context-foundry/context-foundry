# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.3.0] - 2026-05-12

### Changed (BREAKING with auto-migration)
- **`extensions/` → `plugins/` on disk.** The T1.22 rename was previously label-only — the on-disk directory was still named `extensions/`. v3.3.0 completes the rename. The repo directory is now `plugins/`, the user's global directory is `~/.foundry/plugins/`, and Foundry auto-migrates legacy `extensions/` directories on first startup (global, project-local, and ancestor lookups). The migration is one-shot and logs `info: Migrated <legacy> -> <new> (one-time)` to stderr.
- **`Config.extensions` field renamed to `Config.plugins`.** `.foundry.json` files that still use the legacy `"extensions": [...]` field name continue to deserialize via `#[serde(alias = "extensions")]`. On next save, Foundry rewrites the field to `"plugins"`. The legacy key is dropped on write.
- **MCP resource URI**: `foundry://extensions/index` → `foundry://plugins/index`. External MCP clients targeting the old URI must update.
- **Rust API**: `mod extensions` → `mod plugins`; `discover_extensions`, `load_extension_context`, `validate_extensions`, `count_extension_patterns`, `load_extension_patterns`, `save_extensions` and related identifiers all renamed. `ExtensionInfo`/`ExtensionSource` → `PluginInfo`/`PluginSource`. `LoopEvent::Extension*` events → `LoopEvent::Plugin*`. `TuiPane::Extensions` → `TuiPane::Plugins`.

### Removed
- **Plugin-internal `patterns/` directories strangled.** Each plugin's legacy `patterns/*.json` was either migrated to an aggregated `skills/<topic>-pitfalls/SKILL.md` (Anthropic Skills format) or moved to `docs/` when the content was expertise metadata rather than learned pitfalls. Affected plugins: extend (30 pitfalls), flowise (13 pitfalls + 1 parallel-execution skill), recon (4 pitfalls), roblox (5 pitfalls + 1 metadata file moved to docs), workday-agents (6 pitfalls). The `~/.foundry/patterns/` legacy global JSON store remains as read-only fallback only (loader prefers `~/.foundry/skills/` when it exists).

### Documentation
- `.claude/rules/extensions.md` renamed to `.claude/rules/plugins.md` with new paths glob (`plugins/**/*`).
- `extensions/README.md` (now `plugins/README.md`) and the agent-facing rule file both rewritten to make `skills/<topic>/SKILL.md` the canonical primary structure. Patterns demoted to "legacy, read-only fallback — do not add new entries."
- Active site docs (`skills-and-plugins.html`, `OVERVIEW.html`, `cca-alignment.html`, `ROUNDUP.html`, `cross-provider-skills.md`, `jit-knowledge-injection.md`, `extensions-as-plugins.md`, `SPEC_flowise-portable-kit.md`) swept for `extensions/` → `plugins/` path references.
- Project-level `CLAUDE.md` plugin section updated; all stale `patterns/<name>-common-issues.json` references replaced with new `skills/<name>-common-pitfalls/SKILL.md` paths.

## [3.2.0] - 2026-05-11

### Added
- **Skills migration complete** (T1.12-T1.16): legacy patterns abstraction strangled in favor of Anthropic Skills (SKILL.md files in `~/.foundry/skills/`). Hybrid retriever (BM25 + nomic-embed-text cosine + telemetry popularity boost) ranks candidates per task. Sidecar telemetry at `~/.foundry/skills-telemetry.db`.
- **AI stage summaries** (T1.24/T1.25): clicking any pipeline card opens an AI-generated summary of that stage's log + artifacts. Spinner + elapsed-seconds counter while waiting. Proportional scrollbar when output overflows. Clickable [X]/Esc/R/F buttons.
- **AI summary everywhere** (T1.33): clicking any dashboard pane (task queue, narrative, skill citations, stats, agent output) opens a contextual AI summary. Right-click in Explore view opens an "AI summary" context menu for files.
- **Cross-provider skill discovery** (T1.27/T1.28): CF discovers skills authored for other AI tools — AGENTS.md (Linux Foundation standard), `.cursorrules`, `.claude/skills/*/SKILL.md`, and `.github/copilot-instructions.md`. Surfaced in the startup screen's External Skills section with per-source opt-in.
- **Skills at every pipeline stage** (T1.31): skills now inject into QUERY, RESEARCH, PLAN, P+, BUILD, AUDIT, SHIP, and DISCOVER. The cf-stage hint is optional; the ranker decides relevance per stage.
- **Skill citation telemetry honest end-to-end** (T1.30): post-AUDIT scanner finds `**Skills referenced:** skill_id` footers in artifacts and writes to the sidecar DB. Success-rate-weighted ranker now learns from real outcomes (pass vs WIP).
- **Pre-task complexity badges** (T1.23): every task in the queue shows `[S]/[M]/[C]` complexity tier (predicted heuristically) or `[f]/[s]` (user-pinned via `[fast]`/`[strict]` flags). Drives per-task P+ depth.
- **Live-reload TASKS.md** (T1.19): external edits to TASKS.md appear in the running queue without restarting CF.
- **Esc + Ctrl+C confirmation dialogs** (T1.18): destructive single-tap behavior replaced by 2-option (Esc) and 3-option (Ctrl+C) confirmation modals.
- **Eval badge stale-vs-live distinction** (T1.29): the EVAL badge in the stats panel prefixes with `(last)` and dims when showing a previous task's eval during in-flight work.
- **Persisted pane split** (T1.17): the agent/task-queue split bar position survives CF restarts.
- **Per-stage routing**: each pipeline stage can use a different provider/model. Configured via `stage_overrides` in `.foundry.json`.
- **Unified TUI conventions**: shared modal padding, proportional scrollbars, accent-colored clickable buttons, X-button top-right close affordance, hover-locks-background, single-row pipeline tile layout with hover tooltips.

### Changed
- **Plugins rename** (T1.22): the user-facing label "Extensions" is now "Plugins" everywhere (TUI, docs, settings). On-disk directory name `extensions/` preserved for path stability.
- **P+ depth complexity-aware** (T1.23): plan-review iteration cap scales by task complexity tier (Simple = 1, Medium = 2, Complex = 3). Default cap added (T1.20) to prevent unbounded re-plan cycles.
- **Patterns panel → Skills Citations panel** (T1.21): the legacy patterns overlay was retired and replaced with a live Skill Citations panel backed by the sidecar telemetry DB.
- **Pattern extractor writes SKILL.md** (T1.26): post-task pattern extraction writes SKILL.md format directly to `~/.foundry/skills/` instead of `common-issues.json`. Closes the learn loop on the new format.
- **Stats panel reorganized**: dedicated Commits row (`feat: N  WIP: N`), Skills row shows `N inj, N applied, N learned`, EVAL prefix stripped from badge text to avoid label duplication.
- **Pipeline tile layout**: 9 tiles (Q/R/P/P+/B/A/SH/DI/SK) render on a single row with small 6-cell tiles, full names shown on hover via status bar tooltip.
- **Stage-summary subprocess timeout**: configurable via `summary_timeout_secs` in `.foundry.json` (default 20s, up from a hardcoded 5s that frequently timed out on Claude CLI cold-start).

### Fixed
- UTF-8 panic in `extract_prior_task_id`: raw byte-slicing of artifact files panicked when byte 1024 landed inside a multi-byte UTF-8 sequence. Now uses the shared `truncate_str` helper.
- AI summary modal hover focus leak: background panes used to flicker focus highlights while the modal was open.
- Pipeline tile click + hover during PLANNING phase: the initial "Scan project" phase had no pipeline click handler and a stale layout chunk. Now wired identically to RUNNING.
- Summarizer result event dropped during PLANNING phase: `handle_planning_event` had an empty match arm for `SurfaceSummaryReady`, causing summaries opened during planning to spin forever. Now applied.
- Duplicate "Reading stats.rs" in stage tail when stream state is `Reading`.
- Open-file action surfaces error message when stage has no fallback file or file doesn't exist (was silently closing the modal).
- Observatory subsystem residue (T1.32): orphaned `observatory.db` removed; JSONL retention policy added.

## [3.1.0] - 2026-04-30

(Tagged release; CHANGELOG was not updated at the time. See `git log v3.0.0..v3.1.0` for commits.)

## [3.0.0] - 2026-04-25

### Added
- Welcome screen on startup with 3D ASCII "Context Foundry" logo (larry3d font), version, date, provider status, rotating creative messages (30 hardcoded + async Ollama LLM generation), and contextfoundry.dev link
- Dashboard/Explore dual tabs in both startup and running view headers (replaces single toggle label)
- Settings deferred save with "Save changes? [y] save [n] discard [Esc] back" confirmation banner
- App quit confirmation banner ("Quit foundry? [y] quit [n] cancel") on Esc in startup/planning views
- LM Studio model auto-loading when new models are added via settings overlay
- Consistent popup styling: surface background on settings modal, accent-colored borders on all popups

### Changed
- Pipeline tab bar removed from pipeline diagram (tabs moved to view headers)
- Pipeline height reduced from 7 to 6 rows across all layouts
- Welcome screen dismisses on Enter, Esc, or Ctrl+C
- Version aligned to v3.0.0 across Cargo.toml, npm, and GitHub releases

### Fixed
- macOS code signing: build+install command now includes `codesign -s - --force` to prevent SIGKILL from Apple System Policy

## [0.7.3] - 2026-03-26

### Added
- Ancestor extension discovery: foundry walks up from the project directory checking each parent for `extensions/` subdirectories, so nested projects can discover sibling extensions without manual configuration
- `ExtensionSource::Ancestor` variant with priority-based deduplication (ProjectLocal > Ancestor > Global)
- Unit tests for ancestor discovery and priority override behavior

### Fixed
- Extension index test no longer fails when global/ancestor extensions exist on the host

## [0.7.2] - 2026-03-26

### Added
- Sandbox badge in TUI startup header reflecting actual runtime state (Docker available + config enabled)
- Ctrl+S hotkey to toggle sandbox mode on/off at runtime
- Large file handling guidance in all agent prompts (use Grep + offset/limit for files over 10K tokens)

### Changed
- Rate limit messages no longer appear in the agent output panel (status bar still shows retry state)
- File-too-large and file-not-found errors shown as `[info]` (muted) instead of `[stderr]` (red)

### Fixed
- Sandbox badge shows runtime reality, not config intent alone
- Ctrl+S sandbox toggle properly updates state and cleans up footer hints
- Model label renamed to "Claude" in TUI header

## [0.7.1] - 2026-03-25

### Added
- Docker sandbox isolation: agents run inside `Dockerfile.sandbox` containers (node:22-slim + Claude CLI + git)
- Sandbox config fields (`sandbox: bool`) with automatic Docker availability detection
- macOS Keychain credential extraction so containerized agents can authenticate
- Core tmux backend (`src/tmux.rs`) with session lifecycle management
- tmux-based pipeline integration and TUI support
- Checkpoint-based stage resumption -- Foundry resumes from the last completed stage on restart
- Live agent activity summary in the TUI header
- `--clean` flag for installer to remove stale app data before install

### Changed
- Retired Studio in favor of the main TUI (archived for reference)
- Pattern injection now reports actually-injected count, not total matched

### Fixed
- Agent prompts use absolute paths for monorepo subdirectories
- Scout reads UPDATED_SPECS.md for enhancement context
- Smart task archiving (T15.10 was previously an empty shell)

## [0.3.0] - 2026-03-07

### Added
- Foundry Studio session-stop confirmation with selected-session-only cancellation
- Smart Studio stream coloring for Claude Code protocol events, tool calls, results, and real errors
- Built-in Studio theme system with 8 bundled themes plus custom JSON themes and live theme cycling
- Windows x86_64 GitHub Release artifacts and Windows self-update support (`.zip`, PowerShell download/extract, `certutil` checksum verification)
- Bracketed-paste handling and prompt-size guards for very large pastes in Studio

### Changed
- Refactored Studio from a single `src/studio.rs` file into focused `src/studio/` modules (`app`, `state`, `model`, `ui`, and domain slices)
- Updated Studio documentation and README references to match the modular `src/studio/` layout
- Release workflow now packages Unix targets as `.tar.gz` and Windows targets as `.zip`

### Fixed
- Studio session elapsed timers now stop when a session finishes
- Studio prompt/preview rendering truncates oversized content instead of repeatedly rendering unbounded text
- `x stop` only appears for the selected running session in the Studio keybinding bar

## [0.2.0] - 2026-02-16

### Added
- `foundry update` subcommand for self-updating from GitHub Releases
- Non-blocking startup update check with TUI notification
- Cross-platform GitHub Actions release workflow (macOS ARM/x86, Linux ARM/x86)
- Homebrew tap support (`brew install context-foundry/tap/foundry`)
- CI workflow with cargo check, test, and clippy
- SHA256 checksum verification for release binaries
- CHANGELOG.md

### Changed
- Version bumped to 0.2.0
- Added repository and homepage metadata to Cargo.toml
- Self-updater now skips Python-only releases and only reports Rust binary releases

### Fixed
- Prompt injection surface: pattern context now wrapped in non-authoritative reference data delimiters
- Validation commands are now stack-aware (Rust/Python/Node) instead of hardcoded Python/Node
- Reviewer no longer runs `docker compose up` (replaced with read-only `docker compose config`)
- Pattern routing mismatch: reviewer role now correctly receives reviewer advice instead of planner advice
- Discovery agent allows 0 tasks and scopes exploration to primary source directories
- Numbering typo in pattern extraction instructions (1, 2, 4 → 1, 2, 3)
- Reviewer tone changed from presumptive to evidence-based ("every finding must cite specific evidence")

## [0.1.0] - 2025-01-01

### Added
- Initial Rust TUI with ratatui
- Autonomous build loop (planner → builder → reviewer → fixer)
- Pattern learning and extraction
- Discovery mode for finding new tasks
- Headless (no-TUI) streaming mode
- `foundry status` and `foundry tasks` subcommands
- Git auto-commit after task completion

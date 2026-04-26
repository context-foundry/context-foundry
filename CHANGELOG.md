# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

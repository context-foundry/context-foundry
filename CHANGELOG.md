# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [0.1.0] - 2025-01-01

### Added
- Initial Rust TUI with ratatui
- Autonomous build loop (planner → builder → reviewer → fixer)
- Pattern learning and extraction
- Discovery mode for finding new tasks
- Headless (no-TUI) streaming mode
- `foundry status` and `foundry tasks` subcommands
- Git auto-commit after task completion

# Foundry

Autonomous build loop that plans, builds, reviews, and learns -- forever.

This is the npm installer for Foundry. It downloads the correct pre-built binary for your platform from [GitHub Releases](https://github.com/context-foundry/context-foundry/releases).

## Install

```bash
npm install -g context-foundry
```

This installs the `foundry` command globally.

## Requirements

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) must be installed and authenticated

## Usage

```bash
# Point at any project with a TASKS.md
foundry --dir /path/to/project

# Interactive studio mode
foundry --dir /path/to/project studio

# Headless mode (CI/logs)
foundry --dir /path/to/project run --no-tui

# Self-update to latest release
foundry update
```

## Supported Platforms

| Platform | Architecture |
|----------|-------------|
| macOS | Apple Silicon (arm64) |
| macOS | Intel (x64) |
| Linux | x64 |
| Windows | x64 |

## More Info

See the full documentation at [github.com/context-foundry/context-foundry](https://github.com/context-foundry/context-foundry).

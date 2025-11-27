# Context Foundry

AI agent pattern-learning system that helps Claude and other AI agents improve over time.

## Installation

```bash
npm install -g context-foundry
```

This installs the `cf` command globally. The npm package is a thin wrapper that automatically installs and delegates to the Python engine via pip.

## Requirements

- **Node.js 16+** (for the npm wrapper)
- **Python 3.10+** (for the engine)

## Quick Start

```bash
# Launch the interactive TUI (Mission Control)
cf

# Or use the daemon for background operations
cfd start
cfd status
```

## Commands

### `cf` - Main CLI

```bash
cf              # Launch Mission Control TUI
cf --version    # Show version
cf --help       # Show help
```

### `cfd` - Daemon CLI

```bash
cfd start       # Start the daemon
cfd stop        # Stop the daemon
cfd status      # Get daemon status
cfd submit      # Submit a job
cfd list        # List jobs
cfd logs <id>   # Show job logs
```

## How It Works

The npm package is a **distribution shim** that:

1. Checks for Python 3.10+
2. Installs the Python `context-foundry` package via pip (if needed)
3. Delegates all commands to the Python CLI

This approach lets JavaScript/TypeScript developers install via their familiar `npm install` workflow while keeping the core logic in Python.

## Alternative Installation

If you prefer, install directly via pip:

```bash
pip install context-foundry
```

## Documentation

- [GitHub Repository](https://github.com/context-foundry/context-foundry)
- [Documentation](https://context-foundry.github.io)

## License

MIT

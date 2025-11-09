# Installing the `cf` Command

## Quick Installation

From the Context Foundry directory, run:

```bash
# Install in editable mode (recommended for development)
pip install -e .

# Or install normally
pip install .
```

That's it! Now you can run `cf` from anywhere:

```bash
cf              # Launch Context Foundry TUI
cf --version    # Show version
cf --help       # Show help
```

## What Gets Installed

The `cf` command is a CLI tool that provides easy access to Context Foundry features:

- **`cf`** - Launches the beautiful Context Foundry TUI (Terminal User Interface)
- **Purple/blue themed interface** - Matching contextfoundry.dev aesthetic
- **Manage builds** - View, monitor, and cancel autonomous builds
- **File exploration** - Browse build directories with full file trees
- **Natural language** - Just describe what you want to build

## Uninstallation

To remove the `cf` command:

```bash
pip uninstall context-foundry
```

## Troubleshooting

### Command not found

If `cf` doesn't work after installation:

1. Make sure pip's bin directory is in your PATH:
   ```bash
   python3 -m site --user-base
   # Add /bin to this path in your ~/.bashrc or ~/.zshrc
   ```

2. Or use the full path:
   ```bash
   python3 -m tools.cli
   ```

### Missing dependencies

If you get import errors:

```bash
cd /path/to/context-foundry
pip install -r requirements-mcp.txt
```

### Permission denied

On some systems you may need:

```bash
pip install --user -e .
```

## Development

For development, always use editable mode:

```bash
pip install -e .
```

This way your changes to the code are immediately reflected when you run `cf`.

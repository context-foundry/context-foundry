# Installing the `cf` Command

## Prerequisites

**⚠️ IMPORTANT: Python 3.10 or higher is required**

Context Foundry uses Python 3.10+ exclusive features:
- Structural pattern matching (`match` statements)
- Advanced type hints (`TypeAlias`, `ParamSpec`, etc.)

**Check your Python version:**
```bash
python3 --version
```

If you have Python 3.9 or earlier, you must upgrade:

**Option 1: Use pyenv (recommended)**
```bash
# Install pyenv if you don't have it
curl https://pyenv.run | bash

# Install Python 3.11+
pyenv install 3.11
pyenv local 3.11
```

**Option 2: System-wide upgrade**
```bash
# macOS (Homebrew)
brew install python@3.11

# Ubuntu/Debian
sudo apt update && sudo apt install python3.11

# Fedora/RHEL
sudo dnf install python3.11
```

**Option 3: Use a virtual environment** (doesn't require system upgrade)
```bash
# Create venv with Python 3.10+
python3.11 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Now proceed with installation below
```

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

### Python version error

If you see an error like:
```
ERROR: Package 'context-foundry' requires a different Python: 3.9.6 not in '>=3.10'
```

This means your Python version is too old. See the **Prerequisites** section above for upgrade instructions.

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

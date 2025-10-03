# Installation Guide

Quick installation guide for Context Foundry CLI.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git (for version control features)

## Installation

### Option 1: Development Installation (Recommended)

Install in development mode to work on the codebase:

```bash
# Clone the repository
git clone https://github.com/yourusername/context-foundry.git
cd context-foundry

# Install in development mode
pip install -e .
```

This creates a symlink, so changes to the code are immediately reflected.

### Option 2: Standard Installation

Install normally from the repository:

```bash
# Clone the repository
git clone https://github.com/yourusername/context-foundry.git
cd context-foundry

# Install
pip install .
```

### Option 3: From PyPI (Coming Soon)

Once published to PyPI:

```bash
pip install context-foundry
```

## Post-Installation Setup

### 1. Verify Installation

```bash
# Check that foundry command is available
foundry --version

# Should output: foundry, version 1.0.0
```

### 2. Initialize Configuration

```bash
# Create .env configuration file
foundry config --init
```

### 3. Set API Key

Get your API key from [Anthropic Console](https://console.anthropic.com/).

**Option A: Environment Variable (Temporary)**
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

**Option B: .env File (Persistent)**
```bash
# Edit .env file
nano .env

# Add your API key
ANTHROPIC_API_KEY=your_api_key_here
```

**Option C: Using CLI**
```bash
foundry config --set ANTHROPIC_API_KEY your_api_key_here
```

### 4. Verify Setup

```bash
# Run a test build
foundry build test-app "Create a simple hello world CLI in Python"
```

## Upgrading

### Development Installation

```bash
cd context-foundry
git pull
pip install -e . --upgrade
```

### Standard Installation

```bash
cd context-foundry
git pull
pip install . --upgrade
```

## Uninstallation

```bash
pip uninstall context-foundry
```

## Dependencies

Core dependencies (automatically installed):

- `anthropic>=0.40.0` - Claude API client
- `click>=8.0.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting
- `tabulate>=0.9.0` - Table display
- `python-dotenv>=1.0.0` - Environment management
- `sentence-transformers>=2.2.0` - Pattern library embeddings
- `numpy>=1.24.0` - Numerical operations
- `pyyaml>=6.0` - Configuration files

## Platform-Specific Notes

### macOS

```bash
# Install Python 3 (if not already installed)
brew install python3

# Install Context Foundry
pip3 install -e .
```

### Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# Install Context Foundry
pip3 install -e .
```

### Windows

```bash
# Install Python from python.org or Microsoft Store

# Install Context Foundry
pip install -e .
```

**Windows Note**: Some features like shell scripts (`overnight_session.sh`) require WSL or Git Bash.

## Virtual Environment (Recommended)

Use a virtual environment to isolate dependencies:

```bash
# Create virtual environment
python3 -m venv foundry-env

# Activate it
source foundry-env/bin/activate  # macOS/Linux
# or
foundry-env\Scripts\activate  # Windows

# Install Context Foundry
pip install -e .
```

## Troubleshooting

### Command Not Found

If `foundry` command is not found after installation:

```bash
# Check if pip bin directory is in PATH
python3 -m pip show context-foundry

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```

### Import Errors

If you get import errors:

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Permission Errors

On macOS/Linux, you may need:

```bash
# Install with user flag
pip install -e . --user
```

### SSL Certificate Errors

If you get SSL errors when calling the API:

```bash
# Install/update certificates
pip install --upgrade certifi
```

## Development Setup

For contributing to Context Foundry:

```bash
# Clone repository
git clone https://github.com/yourusername/context-foundry.git
cd context-foundry

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest

# Run type checking
mypy .

# Format code
black .
```

## Next Steps

After installation:

1. Read the [CLI Guide](CLI_GUIDE.md)
2. Review [Quick Start](README.md#quick-start)
3. Run your first build: `foundry build my-app "Your task"`
4. Explore patterns: `foundry patterns --stats`
5. Analyze sessions: `foundry analyze`

## Getting Help

```bash
# General help
foundry --help

# Command-specific help
foundry build --help
foundry status --help
foundry patterns --help

# Version info
foundry --version
```

## Support

- 📖 Documentation: [CLI_GUIDE.md](CLI_GUIDE.md)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/context-foundry/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/context-foundry/discussions)

---

*For detailed usage, see [CLI_GUIDE.md](CLI_GUIDE.md)*

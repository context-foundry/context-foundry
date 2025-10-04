# MCP Server Mode Setup Guide

This guide shows you how to use Context Foundry through Claude Desktop **without API charges** by running it as an MCP (Model Context Protocol) server.

## What is MCP Mode?

Context Foundry supports two modes:

| Feature | API Mode | MCP Mode |
|---------|----------|----------|
| **Cost** | Pay per token | Free (uses Claude subscription) |
| **Requirement** | Anthropic API key | Claude Pro/Max subscription |
| **Use Case** | CI/CD, automation | Interactive development |
| **Command** | `foundry build` | Via Claude Desktop |

## Prerequisites

- **Python 3.10 or higher** (MCP packages require Python 3.10+)
- Claude Desktop installed ([download here](https://claude.ai/download))
- Claude Pro or Max subscription
- Context Foundry installed:
  ```bash
  pip install -r requirements.txt          # Base installation
  pip install -r requirements-mcp.txt      # MCP mode dependencies
  ```

**Check your Python version:**
```bash
python --version  # Should show 3.10 or higher
```

**If you have Python 3.9 or older:**
- **Option A:** Upgrade Python to 3.10+ (recommended - see instructions below)
- **Option B:** Use API mode instead (no Python version requirement)

## Setup Steps

### 1. Locate Your Claude Desktop Config File

The config file location depends on your operating system:

**macOS:**
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
~/.config/Claude/claude_desktop_config.json
```

### 2. Edit the Config File

You can edit the file directly or use the Claude Desktop UI:

**Option A - Via Claude Desktop:**
1. Open Claude Desktop
2. Go to Settings → Developer → Edit Config
3. This will open the config file in your default editor

**Option B - Direct Edit:**
```bash
# macOS
open ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Linux
nano ~/.config/Claude/claude_desktop_config.json
```

### 3. Add Context Foundry to Your Config

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python",
      "args": ["-m", "tools.mcp_server"],
      "cwd": "/absolute/path/to/context-foundry"
    }
  }
}
```

**Important:** Replace `/absolute/path/to/context-foundry` with the actual path to your Context Foundry installation.

**Example:**
```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python",
      "args": ["-m", "tools.mcp_server"],
      "cwd": "/Users/yourname/projects/context-foundry"
    }
  }
}
```

**If you already have other MCP servers configured**, just add Context Foundry to the existing `mcpServers` object:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"]
    },
    "context-foundry": {
      "command": "python",
      "args": ["-m", "tools.mcp_server"],
      "cwd": "/Users/yourname/projects/context-foundry"
    }
  }
}
```

### 4. Restart Claude Desktop

Close and reopen Claude Desktop for the changes to take effect.

### 5. Verify Installation

In Claude Desktop, you should see the MCP server indicator in the UI. You can verify Context Foundry is loaded by asking:

```
What MCP tools are available?
```

Claude should list `context_foundry_build`, `context_foundry_status`, and `context_foundry_enhance` (coming soon).

## Using Context Foundry via MCP

Once configured, you can use Context Foundry directly through Claude Desktop:

### Build a New Project

```
Use context_foundry_build to create a todo app with:
- REST API using FastAPI
- SQLite database for storage
- CRUD operations (add, list, update, delete)
- Input validation
Call the project "todo-api"
```

### Check Status

```
Use context_foundry_status to show server information
```

### Autonomous Mode

```
Use context_foundry_build with autonomous mode to create a blog platform.
Don't ask for approval at checkpoints.
```

## How It Works

When you use Context Foundry through MCP:

1. **You type a request** in Claude Desktop
2. **Claude Desktop calls the MCP tool** (`context_foundry_build`)
3. **Context Foundry starts the workflow** (Scout → Architect → Builder)
4. **Prompts are sent back** to Claude Desktop for processing
5. **Claude processes them** using your subscription (no API charges!)
6. **Responses flow back** to Context Foundry
7. **Code files are created** in the `examples/` directory

## Upgrading Python (if needed)

If you have Python 3.9 or older, you need to upgrade:

**macOS (using Homebrew):**
```bash
brew install python@3.10
# Or for latest:
brew install python@3.12

# Verify
python3.10 --version
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-pip
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and install Python 3.10 or higher.

**After upgrading:**
```bash
# Use the new Python version
python3.10 -m pip install -r requirements.txt
python3.10 -m pip install -r requirements-mcp.txt

# Update your PATH or use python3.10 explicitly
```

## Troubleshooting

### Python Version Too Old

```
❌ MCP mode requires Python 3.10 or higher
Current version: Python 3.9
```

**Solution:** Upgrade Python (see section above) or use API mode instead.

### Server Not Showing Up

1. Check that the `cwd` path in your config is correct and absolute
2. Verify Python can find the `tools.mcp_server` module:
   ```bash
   cd /path/to/context-foundry
   python -m tools.mcp_server --help
   ```
3. Check Claude Desktop logs (Settings → Developer → View Logs)

### JSON Syntax Errors

Use a JSON validator to check your config file:
- https://jsonlint.com/
- Common issues: missing commas, extra commas, wrong quotes

### Permission Errors

Make sure the Context Foundry directory is readable:
```bash
chmod -R 755 /path/to/context-foundry
```

### Python Not Found

If you get "python command not found", try using the full path:
```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "/usr/bin/python3",
      "args": ["-m", "tools.mcp_server"],
      "cwd": "/path/to/context-foundry"
    }
  }
}
```

Find your Python path with:
```bash
which python3
```

## Quick Config Generator

Run this command to get a pre-filled config for your system:

```bash
foundry serve --config-help
```

This will show you the exact configuration with your current path already filled in.

## Switching Between Modes

You can use both modes! Keep both configured:

**For interactive development:**
- Use MCP mode through Claude Desktop (no charges)

**For automation/CI:**
- Use API mode with `foundry build` command (charges apply)

No configuration changes needed - just choose which interface to use.

## Next Steps

- [Tutorial](TUTORIAL.md) - Learn the Context Foundry workflow
- [README](../README.md) - Full documentation
- [GitHub Issues](https://github.com/snedea/context-foundry/issues) - Report problems or request features

---

**Cost Comparison:**

| Scenario | API Mode Cost | MCP Mode Cost |
|----------|---------------|---------------|
| Build 5 projects | ~$2-5 | $0 (included in subscription) |
| Daily development | ~$50-100/month | $0 (included in subscription) |
| Team of 5 | ~$250-500/month | $100/month (5 × $20 Pro) |

MCP mode makes sense if you're already paying for Claude Pro/Max and do interactive development work.


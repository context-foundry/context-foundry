# MCP Server Mode Setup Guide

> ✅ **MCP MODE IS FUNCTIONAL** (as of October 2025):
> MCP mode works as a terminal-based MCP server using your Anthropic API key. You can use `foundry serve` to start the MCP server and interact with it programmatically.
>
> ⚠️ **CLAUDE DESKTOP INTEGRATION NOT YET AVAILABLE:**
> While the MCP server works, Claude Desktop integration is blocked because Claude Desktop doesn't support MCP sampling. This means you can't use it through Claude Desktop's UI with your paid subscription (instead of API charges) yet. Use `foundry build` CLI or `foundry serve` for terminal-based MCP server.

This guide shows you how to set up Context Foundry as an MCP server. The MCP server works today using your API key. In the future, Claude Desktop integration would allow using your Claude subscription instead of per-token API charges.

## What is MCP Mode?

Context Foundry is designed to support two modes:

| Feature | API Mode | MCP Mode |
|---------|----------|----------|
| **Cost** | Pay per token | Uses Claude subscription (no per-token charges) |
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

| Scenario | API Mode Cost | MCP Mode Cost (When Available) |
|----------|---------------|---------------|
| Build 5 projects | ~$2-5 in API charges | Included in Claude Pro/Max subscription ($20/month) |
| Daily development | ~$50-100/month in API charges | Claude Pro/Max subscription ($20/month) |
| Team of 5 | ~$250-500/month in API charges | 5 × Claude Pro/Max subscriptions ($100/month total) |

MCP mode makes sense if you're already paying for Claude Pro/Max and do interactive development work - you avoid additional per-token API charges.

## Why Doesn't MCP Mode Work Yet?

Context Foundry needs to make multiple LLM calls during its Scout → Architect → Builder workflow. In MCP, this would be done through "sampling" - where the MCP server asks Claude Desktop to run inference and return results.

**The technical flow would be:**
1. Claude Desktop calls `context_foundry_build` MCP tool
2. Context Foundry MCP server calls `ctx.sample()` to ask Claude to do research
3. Claude Desktop processes the request and returns results
4. This repeats for architecture design and code generation

**Current status:**
Claude Desktop's MCP implementation doesn't support step #2-3 (sampling). When the server tries to call `ctx.sample()`, it gets the error: "Client does not support sampling".

**What we built:**
The complete MCP implementation is ready and tested. When Claude Desktop adds sampling support, Context Foundry will work immediately with no code changes needed. You can see this in our implementation at:
- `tools/mcp_server.py` - MCP server with context injection
- `ace/claude_code_client.py` - MCP-compatible client using ctx.sample()

**For now:**
Use API mode with your Anthropic API key. It works perfectly and gives you the full Context Foundry experience. This incurs per-token API charges separate from your Claude subscription.


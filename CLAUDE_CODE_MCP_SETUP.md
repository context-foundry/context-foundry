# Claude Code MCP Server Setup Guide

## Overview

This guide explains how to set up and use the Context Foundry MCP server to delegate tasks from your main Claude Code CLI session to fresh Claude Code instances. This allows you to:

- **Delegate work to clean contexts**: Spawn new Claude Code processes with fresh context windows
- **Parallel processing**: Run multiple tasks in separate instances
- **Context isolation**: Keep your main session focused while delegating sub-tasks
- **Automated workflows**: Chain multiple delegations for complex pipelines

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Terminal 1: MCP Server                    │
│                                                              │
│  $ python3 tools/mcp_server.py                              │
│  🚀 Starting Context Foundry MCP Server...                   │
│  📋 Available tools:                                         │
│     - context_foundry_build                                 │
│     - delegate_to_claude_code  ← NEW!                       │
│                                                              │
│  [Running, waiting for connections via stdio...]            │
└─────────────────────────────────────────────────────────────┘
                              ↕
                    MCP Protocol (stdio)
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                 Terminal 2: Claude Code CLI                  │
│                                                              │
│  $ claude-code                                              │
│  > Use mcp__delegate_to_claude_code to spawn tasks         │
│                                                              │
│  ┌──────────────────────────────────────────────┐          │
│  │ Delegation Request                           │          │
│  │ task: "Create hello.py"                     │          │
│  │ working_directory: "/tmp/test"              │          │
│  └──────────────────────────────────────────────┘          │
│                      ↓                                       │
│  ┌──────────────────────────────────────────────┐          │
│  │ Spawns subprocess:                           │          │
│  │ $ claude-code "Create hello.py"             │          │
│  │   (fresh instance, clean context)            │          │
│  └──────────────────────────────────────────────┘          │
│                      ↓                                       │
│  ┌──────────────────────────────────────────────┐          │
│  │ Returns results:                             │          │
│  │ ✅ Success | Duration | Output               │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required

1. **Python 3.10 or higher**
   ```bash
   python3 --version  # Should be 3.10+
   ```

2. **Context Foundry dependencies**
   ```bash
   cd /Users/name/homelab/context-foundry
   pip install -r requirements-mcp.txt
   ```

3. **Claude Code CLI** (installed and in PATH)
   ```bash
   which claude-code  # Should return a path
   claude-code --version  # Should show version
   ```

### Optional

- **API Keys**: If using models that require API keys (Anthropic, OpenAI, etc.)
- **Git**: For version control of generated code

## Installation

### Step 1: Install Dependencies

```bash
cd /Users/name/homelab/context-foundry

# Install MCP dependencies
pip install -r requirements-mcp.txt

# Verify installation
python3 -c "from fastmcp import FastMCP; print('FastMCP installed successfully')"
```

### Step 2: Verify MCP Server Code

The MCP server has been modified to include the `delegate_to_claude_code` tool:

```bash
# Check the server file exists
ls -la tools/mcp_server.py

# Verify the delegation tool is present
grep -n "delegate_to_claude_code" tools/mcp_server.py
```

### Step 3: Configure Claude Code MCP Settings

The MCP settings file has been created at `~/.config/claude-code/mcp_settings.json`:

```bash
# Verify the config exists
cat ~/.config/claude-code/mcp_settings.json
```

Expected contents:
```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3",
      "args": [
        "/Users/name/homelab/context-foundry/tools/mcp_server.py"
      ],
      "env": {},
      "disabled": false
    }
  }
}
```

**Important:** The paths in this file are absolute. If you move the `context-foundry` directory, update the path in `mcp_settings.json`.

### Step 4: Verify Claude Code CLI

```bash
# Check if claude-code is in PATH
which claude-code

# If not found, you may need to:
# 1. Install Claude Code CLI
# 2. Add it to PATH: export PATH="/path/to/claude-code:$PATH"
# 3. Add to your shell profile (~/.zshrc or ~/.bashrc)
```

## Usage

### Terminal 1: Start the MCP Server

Open a terminal and run:

```bash
cd /Users/name/homelab/context-foundry
python3 tools/mcp_server.py
```

You should see:
```
🚀 Starting Context Foundry MCP Server...
📋 Available tools:
   - context_foundry_build: Build projects using Context Foundry
   - context_foundry_enhance: Enhance existing projects (coming soon)
   - context_foundry_status: Get server status
   - delegate_to_claude_code: Delegate tasks to fresh Claude Code instances
💡 Configure in Claude Desktop or Claude Code CLI to use this server!
```

**Keep this terminal running!** The MCP server must remain active for Claude Code to connect to it.

### Terminal 2: Connect Claude Code CLI

Open a **new terminal** and start Claude Code:

```bash
claude-code
```

Claude Code will automatically detect the MCP server configuration and connect to it.

### Using the Delegation Tool

Inside your Claude Code session, you can now use the `mcp__delegate_to_claude_code` tool:

#### Example 1: Simple Task

```
Please use the mcp__delegate_to_claude_code tool to create a hello.py file
that prints "Hello World"
```

The tool will:
1. Spawn a fresh `claude-code` process
2. Pass the task to it
3. Wait for completion
4. Return the results

#### Example 2: Specify Working Directory

```
Use mcp__delegate_to_claude_code with:
- task: "Analyze this project and create a README.md"
- working_directory: "/Users/name/homelab/my-project"
```

#### Example 3: With Timeout and Flags

```
Use mcp__delegate_to_claude_code with:
- task: "Run all tests and create a coverage report"
- working_directory: "/Users/name/homelab/my-project"
- timeout_minutes: 15.0
- additional_flags: "--model claude-sonnet-4"
```

## Tool Parameters

### `delegate_to_claude_code()`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task` | string | Yes | - | The task/prompt to give to the new Claude Code instance |
| `working_directory` | string | No | Current directory | Directory where claude-code should run |
| `timeout_minutes` | float | No | 10.0 | Maximum execution time in minutes |
| `additional_flags` | string | No | None | Additional CLI flags (e.g., "--model claude-sonnet-4") |

## Example Workflows

### Workflow 1: Parallel Code Generation

Delegate multiple independent tasks to separate instances:

```
1. Use mcp__delegate_to_claude_code:
   - task: "Create backend API in Python Flask"
   - working_directory: "/tmp/project/backend"

2. Use mcp__delegate_to_claude_code:
   - task: "Create frontend UI in React"
   - working_directory: "/tmp/project/frontend"

3. Use mcp__delegate_to_claude_code:
   - task: "Create database schema and migrations"
   - working_directory: "/tmp/project/database"
```

Each delegation runs in a fresh Claude Code instance with clean context.

### Workflow 2: Analysis and Documentation

```
1. Use mcp__delegate_to_claude_code:
   - task: "Analyze the codebase architecture and create ARCHITECTURE.md"
   - working_directory: "/Users/name/homelab/my-project"
   - timeout_minutes: 20.0

2. Use mcp__delegate_to_claude_code:
   - task: "Generate API documentation from code"
   - working_directory: "/Users/name/homelab/my-project"
   - timeout_minutes: 15.0
```

### Workflow 3: Testing and Quality Assurance

```
1. Use mcp__delegate_to_claude_code:
   - task: "Create comprehensive unit tests for all modules"
   - working_directory: "/Users/name/homelab/my-project"

2. Use mcp__delegate_to_claude_code:
   - task: "Run tests and create coverage report"
   - working_directory: "/Users/name/homelab/my-project"
   - timeout_minutes: 10.0

3. Use mcp__delegate_to_claude_code:
   - task: "Analyze test results and suggest improvements"
   - working_directory: "/Users/name/homelab/my-project"
```

## Troubleshooting

### Issue: MCP Server won't start

**Error:** `ImportError: No module named 'fastmcp'`

**Solution:**
```bash
pip install -r requirements-mcp.txt
# Or specifically:
pip install fastmcp>=2.0.0 nest-asyncio>=1.5.0
```

**Error:** `SyntaxError` or Python version errors

**Solution:**
```bash
# Check Python version (must be 3.10+)
python3 --version

# If too old, upgrade Python or use a newer version:
python3.10 tools/mcp_server.py  # if you have 3.10 installed
```

### Issue: Claude Code doesn't see the MCP tools

**Symptoms:** `mcp__delegate_to_claude_code` tool not available

**Solutions:**

1. **Verify MCP settings file exists:**
   ```bash
   cat ~/.config/claude-code/mcp_settings.json
   ```

2. **Check the path in mcp_settings.json is correct:**
   ```bash
   # The path should point to your actual location
   python3 /Users/name/homelab/context-foundry/tools/mcp_server.py
   ```

3. **Restart Claude Code:**
   - Exit the current Claude Code session
   - Restart: `claude-code`

4. **Check MCP server is running in Terminal 1**

### Issue: "claude-code command not found"

**Error when delegating:** `❌ Error: claude-code command not found`

**Solutions:**

1. **Find where claude-code is installed:**
   ```bash
   # Try these locations:
   ls -la ~/bin/claude-code
   ls -la /usr/local/bin/claude-code
   ls -la ~/.local/bin/claude-code
   ```

2. **Add to PATH temporarily:**
   ```bash
   export PATH="/path/to/claude-code/directory:$PATH"
   ```

3. **Add to PATH permanently:**
   ```bash
   # For Zsh (macOS default):
   echo 'export PATH="/path/to/claude-code/directory:$PATH"' >> ~/.zshrc
   source ~/.zshrc

   # For Bash:
   echo 'export PATH="/path/to/claude-code/directory:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```

4. **Verify:**
   ```bash
   which claude-code
   claude-code --version
   ```

### Issue: Delegations timeout

**Symptoms:** Tasks consistently hit timeout limit

**Solutions:**

1. **Increase timeout:**
   ```
   Use mcp__delegate_to_claude_code with:
   - timeout_minutes: 20.0  # or higher
   ```

2. **Break tasks into smaller pieces:**
   - Instead of "Build entire application"
   - Use: "Create user authentication module" (separate delegations)

3. **Check if task is stuck:**
   - Some tasks may be waiting for user input
   - Ensure tasks are fully automated

### Issue: Working directory errors

**Error:** `❌ Error: Working directory does not exist`

**Solutions:**

1. **Create the directory first:**
   ```bash
   mkdir -p /path/to/working/directory
   ```

2. **Use absolute paths:**
   ```
   # Good:
   working_directory: "/Users/name/homelab/project"

   # May cause issues:
   working_directory: "~/project"  # Expand ~ first
   working_directory: "../project"  # Use absolute path instead
   ```

3. **Verify the path exists:**
   ```bash
   ls -la /path/to/working/directory
   ```

### Issue: Output not captured correctly

**Symptoms:** Empty stdout/stderr or missing output

**Solutions:**

1. **Check both stdout and stderr:** Output may be in either section

2. **Some commands may not produce output:** This is normal for some tasks

3. **Increase verbosity if possible:**
   ```
   additional_flags: "--verbose"  # if supported by claude-code
   ```

## Testing Your Setup

Follow the test scenarios in `examples/test_claude_code_delegation.md` to verify everything works:

```bash
# View test examples
cat /Users/name/homelab/context-foundry/examples/test_claude_code_delegation.md
```

Quick test:
```
In your Claude Code session (Terminal 2), say:

"Please use mcp__delegate_to_claude_code to create a file called test.txt
containing the text 'MCP delegation works!'"
```

Expected result:
- ✅ Success status
- `test.txt` file created
- Duration shown
- Output captured

## Advanced Configuration

### Custom Python Version

If you need to use a specific Python version for the MCP server:

Edit `~/.config/claude-code/mcp_settings.json`:
```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "/usr/local/bin/python3.11",  ← Specify full path
      "args": [
        "/Users/name/homelab/context-foundry/tools/mcp_server.py"
      ]
    }
  }
}
```

### Environment Variables

Pass environment variables to the MCP server:

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3",
      "args": [
        "/Users/name/homelab/context-foundry/tools/mcp_server.py"
      ],
      "env": {
        "ANTHROPIC_API_KEY": "your-api-key",
        "CUSTOM_VAR": "value"
      }
    }
  }
}
```

### Disable the MCP Server

To temporarily disable without deleting the configuration:

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3",
      "args": [
        "/Users/name/homelab/context-foundry/tools/mcp_server.py"
      ],
      "disabled": true  ← Set to true
    }
  }
}
```

## Performance Tips

1. **Timeout tuning:**
   - Simple tasks: 2-5 minutes
   - Code generation: 5-10 minutes
   - Analysis: 10-20 minutes
   - Complex projects: 20-30 minutes

2. **Working directory organization:**
   ```
   /tmp/delegations/
   ├── task-1/
   ├── task-2/
   └── task-3/
   ```

   Use separate directories for parallel delegations to avoid conflicts.

3. **Monitor resource usage:**
   ```bash
   # In a third terminal, monitor processes:
   watch -n 1 'ps aux | grep claude-code'
   ```

## Security Considerations

1. **API Keys:** Be careful not to pass sensitive API keys in `additional_flags`
2. **Working Directory:** Delegated instances have full access to the working directory
3. **Timeout:** Set reasonable timeouts to prevent runaway processes
4. **Code Review:** Always review code generated by delegated instances

## Next Steps

After successful setup:

1. ✅ **Verify**: Run test scenarios from `examples/test_claude_code_delegation.md`
2. 🔧 **Experiment**: Try delegating different types of tasks
3. 📊 **Optimize**: Tune timeouts based on your use cases
4. 🚀 **Automate**: Create workflows that chain multiple delegations
5. 📚 **Document**: Record your own delegation patterns

## Additional Resources

- **MCP Server Code:** `/Users/name/homelab/context-foundry/tools/mcp_server.py`
- **Test Examples:** `/Users/name/homelab/context-foundry/examples/test_claude_code_delegation.md`
- **MCP Settings:** `~/.config/claude-code/mcp_settings.json`
- **MCP Protocol Docs:** https://modelcontextprotocol.io/

## Getting Help

If you encounter issues:

1. Check this troubleshooting guide
2. Review the test examples
3. Check MCP server logs (Terminal 1)
4. Verify all prerequisites are met
5. Try the test scenarios step-by-step

## Summary

### Terminal 1 - Start MCP Server:
```bash
cd /Users/name/homelab/context-foundry
python3 tools/mcp_server.py
# Keep running!
```

### Terminal 2 - Use Claude Code:
```bash
claude-code
# Then use: mcp__delegate_to_claude_code tool
```

### Quick Test:
```
"Use mcp__delegate_to_claude_code to create hello.py that prints 'Hello World'"
```

That's it! You now have a working MCP server that can delegate tasks to fresh Claude Code instances. 🚀

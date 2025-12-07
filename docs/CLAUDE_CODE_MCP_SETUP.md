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
│  $ claude                                                   │
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
│  │ $ claude "Create hello.py"                  │          │
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
   cd {CF_ROOT}
   pip install -r requirements-mcp.txt
   ```

3. **Claude Code CLI** (installed and in PATH)
   ```bash
   which claude  # Should return a path
   claude --version  # Should show version
   ```

### Optional

- **API Keys**: If using models that require API keys (Anthropic, OpenAI, etc.)
- **Git**: For version control of generated code

## Configuration Approaches

Claude Code MCP servers can be configured in two ways:

### 1. Project-Scoped Configuration (Recommended)

**File**: `.mcp.json` (in your project directory)

**Advantages**:
- ✅ Shareable with team via version control
- ✅ Different settings per project
- ✅ Portable across machines
- ✅ Automatically detected when you run `claude` in the project directory

**Setup command**:
```bash
cd /path/to/context-foundry
claude mcp add --transport stdio context-foundry -s project -- $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py
```

**Verification**:
```bash
cat .mcp.json  # Should show your MCP server configuration
```

**Note**: Project-scoped servers won't appear in `claude mcp list` (which only shows global config). They're automatically detected when you run `claude` in the project directory.

### 2. Global Configuration (Recommended for Most Users)

**File**: `~/.claude.json` (user-level configuration)

**Advantages**:
- ✅ Available in all projects globally
- ✅ Works from any directory on your system
- ✅ Appears in `claude mcp list` from any directory
- ✅ No need to configure per-project

**Setup command**:
```bash
claude mcp add --scope user --transport stdio context-foundry -- python3.10 {CF_ROOT}/tools/mcp_server.py
```

**Important**:
- Use `--scope user` to make it truly global (not `--scope local`)
- Replace `{CF_ROOT}` with your actual Context Foundry path
- Replace `python3.10` with your Python version if different

**Verification**:
```bash
# Test from ANY directory:
cd /tmp
claude mcp list  # Should show: ✓ Connected: context-foundry
```

**If you move Context Foundry**: You must update the paths by removing and re-adding:
```bash
claude mcp remove context-foundry
claude mcp add --scope user --transport stdio context-foundry -- python3.10 /new/path/to/context-foundry/tools/mcp_server.py
```

---

## Installation

### Step 1: Install Dependencies

```bash
cd {CF_ROOT}

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

Choose **either** global (recommended) or project-scoped configuration:

#### Option A: Global Configuration (Recommended)

Makes the MCP server available from **any directory** on your system:

```bash
claude mcp add --scope user --transport stdio context-foundry -- python3.10 {CF_ROOT}/tools/mcp_server.py
```

Replace `{CF_ROOT}` with your actual path.

Verify from **any directory**:
```bash
cd /tmp  # Or any other directory
claude mcp list  # Should show: ✓ Connected: context-foundry
```

#### Option B: Project-Scoped

Only available when running `claude` from within the context-foundry directory:

```bash
cd /path/to/context-foundry
claude mcp add --scope project --transport stdio context-foundry -- $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py
```

Verify:
```bash
cat .mcp.json  # Should show the configuration
```

**See "Configuration Approaches" section above for detailed comparison and when to use each option.**

### Step 4: Verify Claude Code CLI

```bash
# Check if claude is in PATH
which claude

# If not found, you may need to:
# 1. Install Claude Code CLI
# 2. Add it to PATH: export PATH="/path/to/claude:$PATH"
# 3. Add to your shell profile (~/.zshrc or ~/.bashrc)
```

## Usage

### Terminal 1: Start the MCP Server

Open a terminal and run:

```bash
cd {CF_ROOT}
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
claude
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
1. Spawn a fresh `claude` process
2. Pass the task to it
3. Wait for completion
4. Return the results

#### Example 2: Specify Working Directory

```
Use mcp__delegate_to_claude_code with:
- task: "Analyze this project and create a README.md"
- working_directory: "~/projects/my-project"
```

#### Example 3: With Timeout and Flags

```
Use mcp__delegate_to_claude_code with:
- task: "Run all tests and create a coverage report"
- working_directory: "~/projects/my-project"
- timeout_minutes: 15.0
- additional_flags: "--model claude-sonnet-4"
```

## Tool Parameters

### `delegate_to_claude_code()`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task` | string | Yes | - | The task/prompt to give to the new Claude Code instance |
| `working_directory` | string | No | Current directory | Directory where claude should run |
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
   - working_directory: "~/projects/my-project"
   - timeout_minutes: 20.0

2. Use mcp__delegate_to_claude_code:
   - task: "Generate API documentation from code"
   - working_directory: "~/projects/my-project"
   - timeout_minutes: 15.0
```

### Workflow 3: Testing and Quality Assurance

```
1. Use mcp__delegate_to_claude_code:
   - task: "Create comprehensive unit tests for all modules"
   - working_directory: "~/projects/my-project"

2. Use mcp__delegate_to_claude_code:
   - task: "Run tests and create coverage report"
   - working_directory: "~/projects/my-project"
   - timeout_minutes: 10.0

3. Use mcp__delegate_to_claude_code:
   - task: "Analyze test results and suggest improvements"
   - working_directory: "~/projects/my-project"
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
   python3 {CF_ROOT}/tools/mcp_server.py
   ```

3. **Restart Claude Code:**
   - Exit the current Claude Code session
   - Restart: `claude`

4. **Check MCP server is running in Terminal 1**

### Issue: "claude command not found"

**Error when delegating:** `❌ Error: claude command not found`

**Solutions:**

1. **Find where claude is installed:**
   ```bash
   # Try these locations:
   ls -la ~/bin/claude
   ls -la /usr/local/bin/claude
   ls -la ~/.local/bin/claude
   ```

2. **Add to PATH temporarily:**
   ```bash
   export PATH="/path/to/claude/directory:$PATH"
   ```

3. **Add to PATH permanently:**
   ```bash
   # For Zsh (macOS default):
   echo 'export PATH="/path/to/claude/directory:$PATH"' >> ~/.zshrc
   source ~/.zshrc

   # For Bash:
   echo 'export PATH="/path/to/claude/directory:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```

4. **Verify:**
   ```bash
   which claude
   claude --version
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
   working_directory: "~/projects/project"

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
   additional_flags: "--verbose"  # if supported by claude
   ```

## Testing Your Setup

Follow the test scenarios in `examples/test_claude_code_delegation.md` to verify everything works:

```bash
# View test examples
cat {CF_ROOT}/examples/test_claude_code_delegation.md
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
        "{CF_ROOT}/tools/mcp_server.py"
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
        "{CF_ROOT}/tools/mcp_server.py"
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
        "{CF_ROOT}/tools/mcp_server.py"
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
   watch -n 1 'ps aux | grep claude'
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

- **MCP Server Code:** `{CF_ROOT}/tools/mcp_server.py`
- **Test Examples:** `{CF_ROOT}/examples/test_claude_code_delegation.md`
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
cd {CF_ROOT}
python3 tools/mcp_server.py
# Keep running!
```

### Terminal 2 - Use Claude Code:
```bash
claude
# Then use: mcp__delegate_to_claude_code tool
```

### Quick Test:
```
"Use mcp__delegate_to_claude_code to create hello.py that prints 'Hello World'"
```

That's it! You now have a working MCP server that can delegate tasks to fresh Claude Code instances. 🚀

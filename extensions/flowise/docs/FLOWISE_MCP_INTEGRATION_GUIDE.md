# Flowise MCP Integration Guide for Context Foundry

> Complete guide to integrating Context Foundry's autonomous development platform with Flowise via Model Context Protocol (MCP)

## Overview

This guide shows you how to connect Flowise to Context Foundry's MCP server, enabling conversational access to autonomous app building capabilities.

**What you'll get:**
- Build complete applications through chat
- Monitor builds in real-time
- Create and manage projects via natural language
- Access 13 powerful development tools

## Architecture

```
┌─────────────────┐
│  Flowise Agent  │
│   (Chat UI)     │
└────────┬────────┘
         │ MCP Protocol
         ↓
┌─────────────────┐
│ Context Foundry │
│   MCP Server    │ (Python FastMCP)
│   13 Tools      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Autonomous     │
│  Build System   │
└─────────────────┘
```

## Prerequisites

### Required

✅ **Flowise** installed and running
- Version: 1.4.0 or higher (for MCP support)
- Installation: https://docs.flowiseai.com/getting-started

✅ **Context Foundry** with MCP dependencies
```bash
cd /Users/name/homelab/context-foundry
pip install -r requirements-mcp.txt
```

✅ **Python 3.10+** (for MCP server)
```bash
python3 --version  # Should be 3.10 or higher
```

✅ **API Key** for LLM
- Anthropic (Claude) - Recommended
- OpenAI (GPT-4)
- Google (Gemini)

### Optional

⚡ **For Cloud Deployment**: HTTP server setup (see Advanced section)

## Quick Start (Local Development)

### Step 1: Verify Context Foundry MCP Server

Test that the MCP server works:

```bash
cd /Users/name/homelab/context-foundry
python3 tools/mcp_server.py

# You should see:
# 📋 Available tools:
#    - context_foundry_status
#    - autonomous_build_and_deploy
#    - delegate_to_claude_code_async
#    ... (13 total)
```

Press `Ctrl+C` to stop the test.

### Step 2: Import the Flowise Flow

1. Open Flowise UI (http://localhost:3000)
2. Click **"Agentflows"** → **"+ Add New"** → **"Load Agentflow"**
3. Select: `extensions/flowise/templates/context-foundry-chat-interface.json`
4. Click **"Save Agentflow"**

### Step 3: Configure MCP in Flowise Agent

1. Click on the **"Context Foundry Assistant"** agent node
2. Scroll down to find **"Tools"** section
3. Click **"+ Add Item"** to add a new tool
4. Select **"Custom MCP"** from the dropdown

### Step 4: Configure MCP Server Connection

In the Custom MCP configuration panel:

#### Transport Type: **stdio** (for local development)

**Configuration JSON:**
```json
{
  "command": "python3",
  "args": [
    "/Users/name/homelab/context-foundry/tools/mcp_server.py"
  ],
  "env": {
    "PYTHONPATH": "/Users/name/homelab/context-foundry"
  }
}
```

**Important**: Update the path if your Context Foundry is in a different location!

Click **"Refresh Actions"** button to discover tools.

### Step 5: Select Context Foundry Tools

After refreshing, you should see 13 tools appear:

✅ **Select these tools** (check all):
- `context_foundry_status`
- `autonomous_build_and_deploy`
- `delegate_to_claude_code_async`
- `get_delegation_result`
- `list_delegations`
- `cancel_delegation`
- `stream_delegation_output`
- `read_global_patterns`
- `save_global_patterns`
- `merge_project_patterns`
- `migrate_all_project_patterns`
- `share_patterns_to_community`
- Resource: `logs://latest`

### Step 6: Add API Credentials

1. In the agent node, find **"Credential"** dropdown
2. Click **"+ Add New Credential"**
3. Choose:
   - **Anthropic API** (for Claude) - Recommended
   - **OpenAI API** (for GPT-4)
   - **Google API** (for Gemini)
4. Enter your API key
5. Click **"Save"**

### Step 7: Save and Test

1. Click **"Save Agentflow"** (top right)
2. Click **"Start Chat"**
3. Test with:
   ```
   What can you help me build?
   ```

Expected response: The assistant explains it can build apps, check status, etc.

## Available MCP Tools

### Core Building Tools

| Tool | Purpose | Use When |
|------|---------|----------|
| `autonomous_build_and_deploy` | Build complete apps autonomously | User wants a new application |
| `delegate_to_claude_code_async` | Execute coding tasks in background | Need specific code changes |

### Monitoring Tools

| Tool | Purpose | Use When |
|------|---------|----------|
| `list_delegations` | Show all builds | User asks "what's running?" |
| `get_delegation_result` | Get build results | Check completed build |
| `stream_delegation_output` | Real-time build output | Show live progress |
| `cancel_delegation` | Stop a build | User wants to cancel |

### Pattern Tools

| Tool | Purpose | Use When |
|------|---------|----------|
| `read_global_patterns` | Read learned best practices | Avoid common issues |
| `save_global_patterns` | Save new patterns | After discovering fixes |
| `merge_project_patterns` | Merge project learnings | After build completes |
| `migrate_all_project_patterns` | Migrate all patterns | Bulk pattern import |
| `share_patterns_to_community` | Share via PR | Contribute back |

### Utility Tools

| Tool | Purpose | Use When |
|------|---------|----------|
| `context_foundry_status` | Get system status | Check if server is healthy |

### Resources

| Resource | Purpose | Use When |
|----------|---------|----------|
| `logs://latest` | Get recent build logs | Debug issues |

## Configuration Files Reference

### Stdio Configuration (Local - Recommended)

**File**: `mcp-configs/context-foundry-stdio.json`

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3",
      "args": [
        "/Users/name/homelab/context-foundry/tools/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/Users/name/homelab/context-foundry"
      }
    }
  }
}
```

**When to use**: Local Flowise development, desktop application

**Pros**:
- No network setup required
- Fast and secure
- Direct process communication

**Cons**:
- Doesn't work in cloud deployments
- Path must be absolute

### HTTP Configuration (Cloud Deployment)

**File**: `mcp-configs/context-foundry-http.json`

```json
{
  "mcpServers": {
    "context-foundry": {
      "url": "http://localhost:3001/mcp",
      "headers": {
        "Authorization": "Bearer {{$vars.contextFoundryToken}}"
      }
    }
  }
}
```

**When to use**: Flowise deployed to Vercel, Railway, Render, etc.

**Pros**:
- Works in cloud environments
- Supports multiple concurrent clients
- Can be load balanced

**Cons**:
- Requires HTTP server wrapper (see Advanced section)
- Network latency
- Need authentication

## Advanced: Cloud Deployment

### Option 1: Create HTTP Wrapper for MCP Server

Context Foundry's MCP server uses stdio (standard input/output), which doesn't work in cloud environments. You need an HTTP wrapper.

**Create**: `/Users/name/homelab/context-foundry/tools/mcp_server_http.py`

```python
#!/usr/bin/env python3
"""
HTTP wrapper for Context Foundry MCP server
Enables cloud deployment of MCP functionality
"""
from flask import Flask, request, jsonify
import subprocess
import json

app = Flask(__name__)

@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    """
    Proxy HTTP requests to stdio MCP server
    """
    try:
        # Get request payload
        data = request.json

        # Call MCP server via subprocess
        result = subprocess.run(
            ['python3', 'tools/mcp_server.py'],
            input=json.dumps(data),
            capture_output=True,
            text=True,
            cwd='/Users/name/homelab/context-foundry'
        )

        # Return response
        return jsonify(json.loads(result.stdout))

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)
```

**Install dependencies**:
```bash
pip install flask
```

**Run the HTTP server**:
```bash
python3 tools/mcp_server_http.py
```

### Option 2: Use ngrok for Testing

For temporary cloud access without deployment:

```bash
# Terminal 1: Start HTTP wrapper
python3 tools/mcp_server_http.py

# Terminal 2: Expose via ngrok
ngrok http 3001
```

Use the ngrok URL in Flowise MCP configuration:
```json
{
  "url": "https://your-ngrok-url.ngrok.io/mcp"
}
```

## Troubleshooting

### Issue: "No tools appear after Refresh Actions"

**Possible causes**:
1. MCP server not starting
2. Wrong path to mcp_server.py
3. Python version < 3.10
4. Missing FastMCP dependency

**Solutions**:

```bash
# 1. Test MCP server directly
python3 /Users/name/homelab/context-foundry/tools/mcp_server.py

# 2. Check Python version
python3 --version  # Must be 3.10+

# 3. Install MCP dependencies
cd /Users/name/homelab/context-foundry
pip install -r requirements-mcp.txt

# 4. Check for errors in Flowise logs
# Look for stdio connection errors
```

### Issue: "Tool execution fails with import errors"

**Cause**: PYTHONPATH not set correctly

**Solution**: Add to MCP config:
```json
{
  "env": {
    "PYTHONPATH": "/Users/name/homelab/context-foundry"
  }
}
```

### Issue: "Authorization failed" (HTTP mode)

**Cause**: Missing or invalid auth token

**Solution**:
1. Create Flowise variable: `contextFoundryToken`
2. Set a secure token value
3. Use in MCP config: `{{$vars.contextFoundryToken}}`
4. Pass same token to HTTP server

### Issue: "Builds don't start"

**Possible causes**:
1. Claude Code CLI not installed
2. Working directory doesn't exist
3. Git not configured

**Solutions**:

```bash
# 1. Verify Claude Code is installed
which claude-code

# 2. Check working directory
# Use relative paths: "my-app" not "/absolute/path/my-app"

# 3. Verify Git config
git config --global user.name
git config --global user.email
```

### Issue: "Slow tool responses"

**Cause**: Stdio overhead for large outputs

**Solution**:
1. Use HTTP mode for cloud deployment
2. Enable streaming: `stream_delegation_output`
3. Use `include_full_output=False` for summaries

### Issue: "Connection timeout"

**Cause**: MCP server process crashed or hung

**Solution**:
```bash
# Kill and restart MCP server processes
pkill -f mcp_server.py

# In Flowise, refresh the agent node to restart connection
```

## Security Best Practices

### 1. Protect API Keys

❌ **Don't**:
```json
{
  "headers": {
    "Authorization": "Bearer hardcoded-token-here"
  }
}
```

✅ **Do**:
```json
{
  "headers": {
    "Authorization": "Bearer {{$vars.contextFoundryToken}}"
  }
}
```

Store tokens in Flowise Variables, not in configuration files.

### 2. Use HTTPS in Production

For HTTP MCP mode:
- Always use HTTPS in production
- Use proper SSL certificates
- Don't expose HTTP endpoints publicly

### 3. Validate Working Directories

The MCP server accepts user-provided working directories. Ensure:
- Path validation in production
- Sandboxing if needed
- Don't allow arbitrary file system access

### 4. Monitor Resource Usage

MCP server spawns Claude Code processes:
- Set reasonable timeout limits
- Monitor concurrent builds
- Implement rate limiting if needed

## Testing the Integration

### Test 1: Server Status
```
User: Check the Context Foundry status
```

Expected: Assistant uses `context_foundry_status` tool and reports version/status

### Test 2: List Builds
```
User: Show me all my builds
```

Expected: Assistant uses `list_delegations` and shows running/completed builds

### Test 3: Build an App
```
User: Build me a simple todo app
```

Expected:
1. Assistant asks clarifying questions
2. Uses `autonomous_build_and_deploy`
3. Returns task_id
4. Offers to monitor progress

### Test 4: Stream Output
```
User: Show me real-time output from task abc-123
```

Expected: Assistant uses `stream_delegation_output` and displays live build progress

### Test 5: Read Patterns
```
User: What patterns have been learned?
```

Expected: Assistant uses `read_global_patterns` and summarizes common issues/solutions

## Example Interactions

### Building an Application

```
You: I need a weather dashboard with OpenWeatherMap

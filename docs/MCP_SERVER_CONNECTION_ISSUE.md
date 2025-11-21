# MCP Server Connection Issue - Forge Backend

**Status:** 🟡 Partial Success - Chat works, MCP tools not loading
**Date:** 2024-11-16
**Priority:** High

## Summary

Claude CLI successfully responds to chat requests when spawned by Forge's FastAPI backend, but the Context Foundry MCP server fails to connect. The same MCP configuration works perfectly when Claude CLI is run manually from the terminal.

## What Works ✅

1. **Chat Flow is Fully Operational**
   - Backend spawns Claude CLI subprocess successfully
   - Prompt written to stdin, stdin closed properly
   - Claude processes requests and streams responses
   - SSE streaming to frontend works correctly
   - User can have full conversations with Claude in Forge UI

2. **MCP Server Works from Terminal**
   - Running `claude --mcp-config ./mcp_config.json` from command line loads all 54 MCP tools
   - MCP server shows `"status": "connected"`
   - All `mcp__context-foundry__*` tools are available
   - Tool execution works correctly

## What Doesn't Work ❌

1. **MCP Server Fails in Subprocess**
   - When FastAPI backend spawns Claude CLI, MCP server shows `"status": "failed"`
   - No MCP tools are loaded (only built-in Claude Code tools available)
   - Cannot use `autonomous_build_and_deploy` or other CF tools from Forge

## Evidence

### Terminal (Working)
```bash
$ echo "test" | claude --print --output-format stream-json --mcp-config ./mcp_config.json 2>&1 | grep mcp_servers

"mcp_servers":[{"name":"context-foundry","status":"connected"}]
```

**Tools loaded:** 54 MCP tools including:
- `mcp__context-foundry__autonomous_build_and_deploy`
- `mcp__context-foundry__stream_delegation_output`
- `mcp__context-foundry__codex_search`
- ... and 51 more

### FastAPI Subprocess (Not Working)
```python
# Backend logs show:
"mcp_servers": [{"name": "context-foundry", "status": "failed"}]
```

**Tools loaded:** Only 16 built-in tools (Task, Bash, Glob, etc.)
**MCP tools:** None ❌

## Configuration

### MCP Config File
**Location:** `/Users/name/homelab/context-foundry/tools/glass-pane/backend/mcp_config.json`

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3",
      "args": ["/Users/name/homelab/context-foundry/tools/mcp_server.py"],
      "env": {}
    }
  }
}
```

### Backend Implementation
**File:** `tools/glass-pane/backend/services/claude_cli.py`

```python
# Path calculation
mcp_config_path = Path(__file__).parent.parent / "mcp_config.json"
# Result: /Users/name/homelab/context-foundry/tools/glass-pane/backend/mcp_config.json

# Command construction
cmd = [
    str(self.claude_path),
    "--print",
    "--output-format",
    "stream-json",
    "--model",
    config.model,
    "--verbose",
]

if mcp_config_path.exists():
    cmd.extend(["--mcp-config", str(mcp_config_path)])
    logger.info(f"Loading MCP config from: {mcp_config_path}")

# Subprocess spawn
process = await asyncio.create_subprocess_exec(
    *cmd,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=cwd,  # Working directory passed from request
)
```

## Debugging Performed

1. ✅ Verified MCP config file exists and is valid
2. ✅ Verified MCP server script exists and runs
3. ✅ Tested MCP server manually with JSON-RPC (works)
4. ✅ Tested Claude CLI from terminal with --mcp-config (works)
5. ✅ Verified path calculation in backend is correct
6. ✅ Confirmed backend logs show MCP config being loaded
7. ❌ Did not yet capture stderr from Claude CLI subprocess

## Potential Causes

### 1. **Working Directory Mismatch**
- Terminal test run from: `/Users/name/homelab/context-foundry`
- Backend subprocess cwd: `/Users/name/homelab/context-foundry/tools/glass-pane/backend` (default)
- May affect MCP server's ability to find dependencies

### 2. **Environment Variables**
- Terminal inherits full shell environment (PATH, PYTHONPATH, etc.)
- Subprocess may have minimal environment
- MCP server might need specific env vars to load CF tools

### 3. **Python Interpreter**
- Terminal uses system `python3`
- Subprocess uses system `python3` (explicitly specified)
- Could be different Python versions or missing packages

### 4. **File Permissions**
- MCP server script may need execute permissions
- Subprocess user context might differ from terminal

### 5. **Async Subprocess Timing**
- MCP server might be taking longer to initialize than expected
- Claude CLI might be timing out the connection attempt

### 6. **Stdio Handling**
- Closing stdin immediately might interfere with MCP server startup
- MCP server uses stdio protocol to communicate with Claude CLI

## Impact

**Current User Experience:**
- ✅ Users CAN chat with Claude in Forge
- ✅ Claude can use built-in tools (Read, Write, Bash, etc.)
- ❌ Users CANNOT trigger autonomous builds from Forge
- ❌ Cannot use Context Foundry's specialized tools

**Workaround:**
Users must use direct `autonomous_build_and_deploy` MCP tool from terminal instead of through Forge UI.

## Next Steps

### Priority 1: Capture Stderr
Add logging to capture Claude CLI's stderr output when MCP server fails:

```python
# Already added in claude_cli.py lines 399-405
if process.stderr:
    stderr_bytes = await process.stderr.read()
    stderr = stderr_bytes.decode("utf-8")
    if stderr.strip():
        logger.warning(f"Claude CLI stderr output:\n{stderr[:1000]}")
```

This will reveal the actual error message from the MCP server connection failure.

### Priority 2: Environment Debugging
Compare environments:

```bash
# Terminal
env | sort > /tmp/terminal-env.txt

# From subprocess (add to backend)
import os
logger.info(f"Subprocess environment: {sorted(os.environ.items())}")
```

### Priority 3: Test with Explicit CWD
Try spawning Claude CLI with explicit working directory:

```python
# Test with CF root as cwd instead of backend dir
process = await asyncio.create_subprocess_exec(
    *cmd,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd="/Users/name/homelab/context-foundry",  # CF root
)
```

### Priority 4: Add MCP Server Health Check
Create diagnostic endpoint:

```python
@router.get("/mcp-server-status")
async def check_mcp_server():
    """Test MCP server connection directly"""
    # Spawn MCP server and attempt JSON-RPC communication
    # Return detailed diagnostics
```

## Timeline

- **2024-11-16 22:00** - Discovered chat was hanging due to stdin never closing
- **2024-11-16 22:30** - Fixed stdin issue, chat flow now works
- **2024-11-16 22:45** - Identified MCP server connection failure
- **2024-11-16 23:00** - Confirmed MCP works from terminal, fails in subprocess
- **2024-11-16 23:15** - Documented issue and next steps

## References

- **Backend Service:** `tools/glass-pane/backend/services/claude_cli.py`
- **MCP Config:** `tools/glass-pane/backend/mcp_config.json`
- **MCP Server:** `tools/mcp_server.py`
- **Chat Endpoint:** `tools/glass-pane/backend/api/chat.py`

## Related Issues

- User originally reported: "Forge didn't respond to Santa chat app request"
- Root cause was: stdin never closed → Claude CLI hung waiting for input
- Fixed by: Adding `process.stdin.close()` after writing prompt
- Uncovered new issue: MCP server not connecting in subprocess context

## Success Metrics

**Current State:**
- Chat functionality: ✅ 100%
- MCP tool availability: ❌ 0%

**Goal:**
- Chat functionality: ✅ 100%
- MCP tool availability: ✅ 100%

Once MCP server connects successfully, users will be able to trigger full autonomous builds directly from Forge's chat interface using natural language (e.g., "Build a weather app").

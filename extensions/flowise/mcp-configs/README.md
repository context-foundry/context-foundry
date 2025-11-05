# Context Foundry MCP Configurations for Flowise

This directory contains MCP server configuration files for integrating Context Foundry with Flowise.

## Quick Start

### Local Development (Recommended)

Use **stdio transport** for local Flowise installations:

**Configuration**: `context-foundry-stdio.json`

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

**How to use in Flowise**:
1. Open your Context Foundry Assistant agent flow
2. Click the agent node
3. Scroll to **Tools** section
4. Click **+ Add Item**
5. Select **Custom MCP**
6. Copy the JSON from `context-foundry-stdio.json`
7. Click **Refresh Actions**
8. Select all 13 Context Foundry tools

### Cloud Deployment

Use **HTTP transport** for Flowise deployed to cloud (Vercel, Railway, etc.):

**Configuration**: `context-foundry-http.json`

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

**Prerequisites**:
1. Set up HTTP wrapper for MCP server (see guide)
2. Create Flowise variable: `contextFoundryToken`
3. Deploy HTTP server to accessible endpoint
4. Update URL in configuration

## Files in This Directory

| File | Purpose | Use When |
|------|---------|----------|
| `context-foundry-stdio.json` | Local stdio configuration | Flowise running locally |
| `context-foundry-http.json` | HTTP configuration | Flowise in cloud |
| `README.md` | This file | Documentation |

## Available MCP Tools

After configuration, you'll have access to 13 tools:

### Core Tools
- `autonomous_build_and_deploy` - Build complete applications
- `delegate_to_claude_code_async` - Execute coding tasks

### Monitoring
- `list_delegations` - Show all builds
- `get_delegation_result` - Get build results
- `stream_delegation_output` - Real-time progress
- `cancel_delegation` - Stop builds

### Patterns
- `read_global_patterns` - Read learned patterns
- `save_global_patterns` - Save patterns
- `merge_project_patterns` - Merge patterns
- `migrate_all_project_patterns` - Migrate patterns
- `share_patterns_to_community` - Share via PR

### Utility
- `context_foundry_status` - System status

### Resources
- `logs://latest` - Recent build logs

## Configuration Customization

### Update Paths

If Context Foundry is installed in a different location, update the path:

```json
{
  "args": [
    "/your/custom/path/context-foundry/tools/mcp_server.py"
  ]
}
```

### Add Environment Variables

```json
{
  "env": {
    "PYTHONPATH": "/path/to/context-foundry",
    "LOG_LEVEL": "debug",
    "CUSTOM_VAR": "value"
  }
}
```

### HTTP Authentication

For production HTTP deployments, use strong authentication:

1. Generate secure token:
```bash
openssl rand -hex 32
```

2. Store in Flowise variables as `contextFoundryToken`

3. Reference in config:
```json
{
  "headers": {
    "Authorization": "Bearer {{$vars.contextFoundryToken}}"
  }
}
```

## Troubleshooting

### Tools Don't Appear

✓ Check Python version: `python3 --version` (must be 3.10+)
✓ Install MCP deps: `pip install -r requirements-mcp.txt`
✓ Test server: `python3 tools/mcp_server.py`
✓ Check path is absolute, not relative

### Connection Errors

✓ Verify MCP server can start
✓ Check Flowise logs for stdio errors
✓ Ensure PYTHONPATH is set correctly
✓ Try restarting Flowise

### Tools Execute But Fail

✓ Check Claude Code CLI is installed
✓ Verify Git is configured
✓ Ensure working directories exist
✓ Check Context Foundry logs

## Documentation

📖 **Complete Setup Guide**: `../docs/FLOWISE_MCP_INTEGRATION_GUIDE.md`
📖 **System Prompt**: `../prompts/CONTEXT-FOUNDRY-ASSISTANT-PROMPT.md`
📖 **Quick Start**: `../templates/CONTEXT_FOUNDRY_CHAT_README.md`

## Support

- **Flowise MCP Docs**: https://docs.flowiseai.com/tutorials/tools-and-mcp
- **Context Foundry**: https://github.com/yourusername/context-foundry
- **FastMCP**: https://github.com/jlowin/fastmcp

## Version

- **Created**: 2025-11-04
- **MCP Protocol**: 2024-11-05
- **FastMCP Version**: Latest
- **Flowise Version**: 1.4.0+

---

**Ready to build apps through conversation!** 🚀

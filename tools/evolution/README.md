# Context Foundry Evolution System

The Evolution System provides specialized agents for codebase analysis and autonomous improvement.

**Note:** The main daemon functionality has been consolidated into `context_foundry/daemon/`. Use `cfd` commands to manage the daemon.

## Components

### Scout Agent (`agents/scout_agent.py`)
Scans codebases for issues using 15+ specialized scanners:
- Security vulnerabilities
- Code quality issues
- Performance problems
- Project type detection (Flowise, Roblox, Python, Node)
- Priority scoring

### Backlog Generator (`backlog_generator.py`)
Creates GitHub issues from Scout findings:
- Follows Context Foundry issue template
- Maintains 5-issue backlog
- AI-powered issue analysis

### Framework (`framework/`)
LLM provider abstraction for multi-provider support:
- Local Claude Code
- AWS Bedrock
- Bedrock Agents
- Phase-based model selection

## Usage

The evolution agents are used by the main CF daemon via MCP tools:

```bash
# Start the CF daemon
cfd start

# View dashboard
open http://localhost:8420
```

## Quick Links

- Main daemon: `context_foundry/daemon/`
- MCP tools: `tools/mcp_server.py`
- Dashboard: `tools/dashboard/` (Vite React app)

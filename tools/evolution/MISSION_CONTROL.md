# Mission Control - Context Foundry Evolution TUI

Beautiful terminal UI for managing the Evolution System with an AI chat interface.

## Overview

Mission Control is a single-pane-of-glass dashboard that brings together:

- **AI Chat Interface** - Familiar Claude-style chat for controlling builds
- **Live Status Dashboard** - Real-time daemon, MCP, and backlog health
- **Build Management** - Start/monitor builds in isolated sandboxes
- **Activity Logs** - Stream daemon and build events
- **Keyboard Controls** - Fast, keyboard-driven workflow

## Architecture

```
Mission Control (Textual TUI)
├── AI Chat Panel - Interactive assistant
├── Status Panel - System health (daemon, MCP, backlog)
├── Activity Log - Live daemon logs
└── Command Server - REST API for control

Supporting Components:
├── Sandbox Manager - Isolated build environments
├── Command Server - HTTP API (port 8765)
└── Evolution Daemon - Background automation
```

## Quick Start

### Launch Mission Control

```bash
# Simple launch
tools/evolution/scripts/mission-control.sh

# Or directly
python3 -m tools.evolution.mission_control
```

### Start Command Server (Optional)

For programmatic control:

```bash
python3 -m tools.evolution.command_server
# Listening on http://127.0.0.1:8765
```

## Features

### 1. AI Chat Interface

Chat with the assistant to:
- Start builds: `build my-app Add user authentication`
- Check status: `status`
- Get help: `help`
- Manage issues: `list issues`

### 2. Live Dashboard

Real-time monitoring:
- **Daemon**: Running status, PID
- **Backlog**: GitHub issue count (target: 20)
- **MCP**: Availability (Python 3.10+ check)
- **Builds**: Active sandbox count

### 3. Isolated Builds

All builds run in **temporary sandboxes** to protect Context Foundry source:

```python
# Sandboxes created in /tmp/cf-sandboxes
# Each build gets fresh clone
# Automatic cleanup after 24 hours
```

### 4. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+D` | Send chat message |
| `Ctrl+B` | Quick build prompt |
| `Ctrl+R` | Refresh all panels |
| `Ctrl+C` | Quit |

## Command Server API

### Endpoints

**Status:**
- `GET /status` - Overall system status
- `GET /daemon/status` - Daemon status
- `GET /mcp/status` - MCP availability
- `GET /issues` - GitHub issues
- `GET /sandboxes` - Active sandboxes

**Control:**
- `POST /build` - Start new build
- `POST /daemon/start` - Start daemon
- `POST /daemon/stop` - Stop daemon
- `POST /sandbox/{id}/cleanup` - Remove sandbox

### Examples

```bash
# Check status
curl http://localhost:8765/status

# Start build
curl -X POST http://localhost:8765/build \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "my-app",
    "task": "Add user authentication"
  }'

# List sandboxes
curl http://localhost:8765/sandboxes
```

## Sandbox Isolation

### Why Sandboxes?

Context Foundry's Evolution System now uses **isolated sandboxes** to:

1. **Protect the Framework** - Never modify Context Foundry source
2. **Safe Experimentation** - Each build in fresh clone
3. **Parallel Builds** - Multiple projects simultaneously
4. **Easy Cleanup** - Automatic garbage collection

### How It Works

```
1. User requests build via chat
2. Sandbox manager creates /tmp/cf-sandboxes/sandbox_abc123_20251108
3. Git clone --depth 1 <repo>
4. MCP autonomous_build_and_deploy runs in sandbox
5. PR created from sandbox
6. Sandbox auto-deleted after 24 hours
```

### Manual Sandbox Management

```python
from tools.evolution.sandboxes import SandboxManager

manager = SandboxManager()

# Create sandbox
path = manager.create_sandbox(
    repo_url="https://github.com/user/repo.git",
    task_id="unique-id"
)

# List sandboxes
sandboxes = manager.list_sandboxes()

# Cleanup
manager.cleanup_sandbox("task-id")
manager.cleanup_old_sandboxes(max_age_hours=24)

# Stats
stats = manager.get_stats()
# {'total_sandboxes': 2, 'total_size_mb': 145.3, 'base_dir': '/tmp/cf-sandboxes'}
```

## Integration with Evolution System

Mission Control **complements** the Evolution daemon:

**Daemon Responsibilities:**
- Backlog maintenance (every 5 minutes)
- Scout scans + AI analysis
- GitHub issue creation
- Monitoring stuck tasks

**Mission Control Responsibilities:**
- Interactive build control
- Real-time status visualization
- Manual build triggers
- Sandbox management

**They work together:**
```
Daemon (background)     Mission Control (foreground)
    |                            |
    |-- Maintains backlog        |-- Shows backlog status
    |-- Runs Scout              |-- Displays findings
    |-- Monitors MCP            |-- Chat interface for builds
    |                            |
    \-------- Shared State ------/
             (logs, database)
```

## Chat Commands

### Build Commands

```
build <name> <task>        Start new build in sandbox
list builds                Show active builds
stop build <id>           Stop running build
```

### System Commands

```
status                    System health check
restart daemon            Restart Evolution daemon
clean sandboxes          Remove old sandboxes
```

### Help Commands

```
help                     Show all commands
help builds              Build-specific help
help shortcuts           Keyboard shortcuts
```

## Development

### Adding New Chat Commands

Edit `tools/evolution/mission_control.py`:

```python
async def _process_command(self, message: str) -> str:
    # Add your command pattern
    if "my command" in message.lower():
        # Handle command
        return "Response message"
```

### Adding New Endpoints

Edit `tools/evolution/command_server.py`:

```python
def do_GET(self):
    if path == "/my/endpoint":
        self._handle_my_endpoint()

def _handle_my_endpoint(self):
    self._json_response({"data": "value"})
```

### Customizing UI

Edit CSS in `mission_control.py`:

```python
CSS = """
StatusPanel {
    border: solid cyan;  # Change colors
    height: 100%;
}
"""
```

## Troubleshooting

### Mission Control won't start

```bash
# Check Textual installation
pip3 install textual

# Check Python version
python3 --version  # Should be 3.9+
```

### Daemon shows as offline

```bash
# Start daemon
python3 -m tools.evolution.daemon start

# Check status
python3 -m tools.evolution.daemon status
```

### MCP shows as unavailable

```bash
# Upgrade Python (requires 3.10+)
brew install python@3.11

# Install MCP dependencies
pip3 install -r requirements-mcp.txt

# Restart daemon to detect
kill -HUP <daemon-pid>
```

### Sandboxes not cleaning up

```python
# Manual cleanup
from tools.evolution.sandboxes import SandboxManager
manager = SandboxManager()
manager.cleanup_old_sandboxes(max_age_hours=1)  # Aggressive cleanup
```

## Future Enhancements

- [ ] Web UI version (React + websockets)
- [ ] Build progress streaming
- [ ] Multi-project dashboard
- [ ] Slack/Discord notifications
- [ ] Custom Scout scan triggers
- [ ] Issue approval workflow
- [ ] PR review integration

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│              Mission Control (Textual TUI)               │
├─────────────┬──────────────┬──────────────┬─────────────┤
│ AI Chat     │ Status Panel │ Activity Log │ Chat Input  │
│             │              │              │             │
│ "build app" │ Daemon: ✓    │ [Live logs]  │ > _         │
│ "status"    │ Backlog: 20  │              │             │
│             │ MCP: Ready   │              │             │
└─────────────┴──────────────┴──────────────┴─────────────┘
       │              │               │
       ▼              ▼               ▼
┌─────────────┬──────────────┬───────────────┐
│ Command     │ Evolution    │ Sandbox       │
│ Server      │ Daemon       │ Manager       │
│ (REST API)  │ (Background) │ (Isolation)   │
└─────────────┴──────────────┴───────────────┘
       │              │               │
       ▼              ▼               ▼
┌─────────────────────────────────────────────┐
│          GitHub + MCP + File System         │
└─────────────────────────────────────────────┘
```

## Philosophy

**Simplicity is the ultimate sophistication** - Leonardo da Vinci

Mission Control embraces this by:
- Single command to launch
- Familiar chat interface
- Keyboard-first workflow
- No complex configuration
- Beautiful, minimal design
- Clear, actionable feedback

The dashboard is your **single source of truth** for Evolution System health and control.

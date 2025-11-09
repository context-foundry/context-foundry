# Context Foundry Evolution System (CFES)

**Version:** 1.0.0
**Status:** Alpha
**Architecture:** Daemon-based autonomous evolution layer

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Getting Started](#getting-started)
5. [Evolution Modes](#evolution-modes)
6. [MCP Tools Reference](#mcp-tools-reference)
7. [Configuration](#configuration)
8. [API Documentation](#api-documentation)
9. [Troubleshooting](#troubleshooting)
10. [Development](#development)

---

## Overview

The Context Foundry Evolution System (CFES) transforms Context Foundry from a task-based autonomous build tool into a continuously-evolving, self-improving system that runs perpetually.

### Key Features

- **Autonomous Evolution**: Three distinct modes (Self-Improvement, Chaos/Creative, Research)
- **Persistent Task Queue**: SQLite-based queue with ACID guarantees
- **Multi-Agent Network**: Coordinate with other CFES instances
- **Web Dashboard**: Real-time monitoring at http://localhost:8765
- **REST API**: Programmatic control at http://localhost:8766
- **MCP Integration**: 10 new tools for Claude Desktop/Code

### What Can CFES Do?

1. **Self-Improve**: Analyze Context Foundry's codebase, find TODOs, and create PRs
2. **Create Projects**: Generate random projects (web apps, CLI tools, games) autonomously
3. **Research**: Conduct multi-step research investigations (disabled by default)
4. **Pattern Application**: Apply proven patterns to existing projects
5. **Health Validation**: Run tests and validate project health

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│          External Interfaces                     │
│   Dashboard (8765) | REST API (8766) | WS (8767)│
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│         Evolution Daemon (Main Loop)             │
│                                                  │
│    ┌─────────────────────────────────┐          │
│    │   Task Queue (SQLite)            │          │
│    │   - Tasks (pending/running)      │          │
│    │   - Task History (completed)     │          │
│    │   - Project Registry             │          │
│    │   - Agent Network                │          │
│    └────────────┬────────────────────┘          │
│                 │                                 │
│    ┌────────────▼────────────────────┐          │
│    │   Evolution Modes (Plugins)     │          │
│    │   - Self-Improvement             │          │
│    │   - Chaos/Creative               │          │
│    │   - Research/Discovery           │          │
│    └────────────┬────────────────────┘          │
│                 │                                 │
│    ┌────────────▼────────────────────┐          │
│    │   Existing CF Build System      │          │
│    │   (via MCP delegation)          │          │
│    └─────────────────────────────────┘          │
└──────────────────────────────────────────────────┘
```

### Components

1. **Evolution Daemon** (`tools/evolution/daemon.py`)
   - Continuously-running service
   - Polls queue every 60 seconds
   - Respects CPU/memory limits
   - Graceful shutdown

2. **Task Queue Manager** (`tools/evolution/task_queue.py`)
   - SQLite-based persistence
   - Priority-based task scheduling
   - Automatic retry with exponential backoff
   - Task archiving (30 days)

3. **Resource Manager** (`tools/evolution/resource_manager.py`)
   - CPU/memory monitoring
   - Active hours enforcement
   - Resource limit checks

4. **Evolution Modes** (`tools/evolution/modes/`)
   - Plugin architecture
   - Base interface + concrete implementations
   - Generate and execute tasks

5. **Communication Layer** (`tools/evolution/communication/`)
   - REST API (FastAPI - placeholder)
   - Web Dashboard (Jinja2 templates)
   - WebSocket streaming
   - Local file exchange

6. **Agent Protocol** (`tools/evolution/agent_protocol.py`)
   - Multi-agent network
   - Message passing
   - Agent discovery

---

## Installation

### Prerequisites

- Python 3.11+ (for AsyncIO support)
- Context Foundry v2.x installed
- SQLite 3.x (usually included with Python)

### Install Dependencies

```bash
# Install CFES dependencies
pip install psutil

# Optional: For full web dashboard (FastAPI)
pip install fastapi uvicorn websockets jinja2

# Optional: For research mode
pip install arxiv
```

### Verify Installation

```bash
# Check daemon can start
python3 tools/evolution/daemon.py status

# Run tests
pytest tests/evolution/ -v
```

---

## Getting Started

### Quick Start (Manual Mode)

```bash
# Start daemon in foreground
python3 tools/evolution/daemon.py start --foreground
```

In another terminal:

```bash
# Create a task using Python
python3 << 'PYTHON'
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
from tools.evolution.task_queue import TaskQueueManager

queue = TaskQueueManager()
task_id = queue.create_task(
    task_type='chaos_creative',
    params={'project_type': 'web_app'},
    priority=7
)
print(f"Created task: {task_id}")
PYTHON

# Check task status
python3 << 'PYTHON'
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
from tools.evolution.task_queue import TaskQueueManager

queue = TaskQueueManager()
tasks = queue.list_tasks(status='all', limit=10)
for task in tasks:
    print(f"{task.id[:8]} - {task.type} - {task.status}")
PYTHON
```

### Using MCP Tools (Claude Desktop/Code)

```
User: Create a chaos/creative evolution task
Assistant: [uses create_evolution_task MCP tool]

User: Show me the evolution task queue
Assistant: [uses get_evolution_tasks MCP tool]

User: What's the daemon status?
Assistant: [uses get_daemon_status MCP tool]
```

### Install as System Service

```bash
# macOS (launchd) or Linux (systemd)
./scripts/install_service.sh

# Daemon will auto-start on boot
```

---

## Evolution Modes

### Mode A: Self-Improvement

**Purpose**: Analyze Context Foundry codebase and generate improvement tasks

**How it works:**
1. Scans `tools/` directory for TODO/FIXME comments
2. Creates tasks for each TODO (max 5 per run)
3. Executes by creating feature branch
4. Creates PR for human review (NEVER auto-merges)

**Example Task:**
```json
{
  "type": "self_improvement",
  "params": {
    "action": "implement_todo",
    "file": "tools/cache/scout_cache.py",
    "line": "42",
    "description": "TODO: Add cache expiration logic"
  }
}
```

**Schedule**: Daily at midnight (configurable)

---

### Mode B: Chaos/Creative

**Purpose**: Generate random projects to explore possibilities

**Project Types** (weighted):
- Web Apps (30%): React, Vue, Vanilla JS
- CLI Tools (20%): Python, Go, Rust
- Games (15%): 2D canvas, terminal games
- Frameworks (15%): Libraries, utilities
- Art (10%): Generative art, visualizations
- Experiments (10%): Novel ideas, research

**Example Projects:**
- "Real-time collaborative markdown editor"
- "Terminal-based roguelike dungeon crawler"
- "Generative art with procedural algorithms"

**Learning Loop:**
1. Generate project idea
2. Delegate to CF build system
3. Track: build time, test pass rate, patterns used
4. Update pattern library
5. Adjust weights based on success

**Schedule**: Every 6 hours (configurable)

---

### Mode C: Research/Discovery

**Purpose**: Research assistant for long-running investigations

**Capabilities:**
- WebSearch integration
- Paper discovery (arXiv, PubMed - requires APIs)
- Multi-step research workflows
- Hypothesis generation
- Markdown reports with citations

**Example Research Prompt:**
"Analyze quantum computing breakthroughs 2024-2025"

**Output:**
- `research-reports/quantum-computing-2024.md`
- Structured findings
- Hypotheses for further research

**Status**: Disabled by default (enable in config)

---

## MCP Tools Reference

### create_evolution_task

Create new evolution task and add to queue.

**Parameters:**
- `task_type` (required): 'self_improvement', 'chaos_creative', 'research', 'apply_pattern', 'validate'
- `target_project` (optional): Project path for apply_pattern/validate
- `pattern_id` (optional): Pattern ID for apply_pattern
- `priority` (optional): 1-10 (default: 5)
- `params` (optional): Additional parameters dict

**Returns:** JSON with task_id and status

**Example:**
```json
{
  "success": true,
  "task_id": "a1b2c3d4-...",
  "status": "pending",
  "message": "Evolution task created successfully"
}
```

---

### get_evolution_tasks

List evolution tasks with optional filters.

**Parameters:**
- `status` (optional): 'pending', 'running', 'completed', 'failed', 'all' (default: 'pending')
- `limit` (optional): Max tasks to return (default: 50)

**Returns:** JSON with task list

---

### start_evolution_daemon

Start the evolution daemon service.

**Parameters:**
- `config_path` (optional): Path to config file

**Returns:** JSON with start status

**Note:** For full daemonization, use `python3 tools/evolution/daemon.py start`

---

### stop_evolution_daemon

Stop the evolution daemon.

**Parameters:**
- `graceful` (optional): Wait for active tasks (default: true)

**Returns:** JSON with stop status

---

### get_daemon_status

Get daemon health, queue size, active tasks, and resource usage.

**Returns:** JSON with comprehensive status

**Example:**
```json
{
  "success": true,
  "status": {
    "running": true,
    "pid": 12345,
    "uptime_seconds": 3600,
    "queue_size": 5,
    "completed_tasks": 42,
    "failed_tasks": 2,
    "resource_usage": {
      "cpu_percent": 15.3,
      "memory_mb": 256.8
    }
  }
}
```

---

### register_project

Register a project in the global registry.

**Parameters:**
- `project_path` (required): Absolute path to project
- `project_type` (required): e.g., 'web-app', 'cli-tool'
- `metadata` (optional): Additional metadata dict

---

### apply_pattern_to_project

Apply a specific pattern to an existing project (creates task).

**Parameters:**
- `project_path` (required): Path to project
- `pattern_id` (required): Pattern ID from global library

---

### validate_project_health

Run tests and validate project health (creates validation task).

**Parameters:**
- `project_path` (required): Path to project to validate

---

### register_agent

Register an agent in the network.

**Parameters:**
- `agent_name` (required): Name of agent
- `agent_url` (optional): URL for remote agent
- `capabilities` (optional): List of capabilities

---

### send_agent_message

Send message to another agent.

**Parameters:**
- `target_agent` (required): Target agent name or ID
- `message_type` (required): 'task_delegation', 'learning_share', 'health_check'
- `payload` (required): Message payload dict

---

## Configuration

### Config File Location

`~/.context-foundry/evolution/config.json`

### Default Configuration

```json
{
  "daemon": {
    "enabled": true,
    "poll_interval_seconds": 60,
    "max_concurrent_tasks": 3,
    "log_level": "INFO"
  },
  "modes": {
    "self_improvement": {
      "enabled": true,
      "priority": 8,
      "schedule": "0 0 * * *",
      "max_daily_tasks": 5
    },
    "chaos_creative": {
      "enabled": true,
      "priority": 5,
      "schedule": "0 */6 * * *",
      "project_types": ["web-app", "cli-tool", "game", "framework"]
    },
    "research_discovery": {
      "enabled": false,
      "priority": 9,
      "schedule": "on_demand"
    }
  },
  "resources": {
    "max_cpu_percent": 80,
    "max_memory_gb": 16,
    "active_hours": [6, 22]
  },
  "communication": {
    "web_dashboard_port": 8765,
    "rest_api_port": 8766,
    "websocket_port": 8767,
    "expose_external": false
  },
  "agent_network": {
    "enable_discovery": true,
    "allow_external_agents": false,
    "trust_mode": "whitelist"
  }
}
```

### Configuration Options

**daemon.poll_interval_seconds**: How often to check queue (default: 60)
**daemon.max_concurrent_tasks**: Max tasks running simultaneously (default: 3)

**resources.max_cpu_percent**: Max CPU usage before pausing (default: 80)
**resources.max_memory_gb**: Max memory before pausing (default: 16)
**resources.active_hours**: [start_hour, end_hour] (default: [6, 22])

---

## API Documentation

### REST API Endpoints

**Base URL:** `http://localhost:8766`

#### POST /tasks

Create new task.

**Request Body:**
```json
{
  "task_type": "chaos_creative",
  "priority": 7,
  "params": {"project_type": "web_app"}
}
```

**Response:** Task object

---

#### GET /tasks

List tasks with filters.

**Query Parameters:**
- `status`: pending|running|completed|failed|all
- `type`: self_improvement|chaos_creative|research
- `limit`: Max results (default: 50)

---

#### GET /tasks/{id}

Get task details.

**Response:** Task object

---

#### DELETE /tasks/{id}

Cancel pending task.

---

#### GET /health

System health check.

**Response:**
```json
{
  "status": "healthy",
  "daemon_running": true,
  "queue_size": 5,
  "active_tasks": 2
}
```

---

## Troubleshooting

### Daemon won't start

**Check if already running:**
```bash
python3 tools/evolution/daemon.py status
```

**Remove stale PID file:**
```bash
rm ~/.context-foundry/evolution/daemon.pid
```

**Check logs:**
```bash
tail -f ~/.context-foundry/evolution/logs/daemon.log
```

---

### Tasks stuck in pending

**Check daemon is running:**
```bash
ps aux | grep "evolution/daemon.py"
```

**Check resource limits:**
```bash
# CPU usage
top

# Memory usage
free -h  # Linux
vm_stat  # macOS
```

**Check active hours:**
```bash
# Current hour should be between active_hours in config
date +%H
```

---

### Database locked errors

**Enable WAL mode** (should be automatic):
```bash
sqlite3 ~/.context-foundry/evolution/task_queue.db "PRAGMA journal_mode=WAL;"
```

**Check for other processes:**
```bash
lsof ~/.context-foundry/evolution/task_queue.db
```

---

## Development

### Running Tests

```bash
# All evolution tests
pytest tests/evolution/ -v

# Specific test file
pytest tests/evolution/test_task_queue.py -v

# With coverage
pytest tests/evolution/ --cov=tools/evolution --cov-report=html
```

### Adding New Evolution Mode

1. **Create mode file**: `tools/evolution/modes/my_mode.py`

2. **Inherit from BaseEvolutionMode**:
```python
from .base_mode import BaseEvolutionMode, TaskResult

class MyMode(BaseEvolutionMode):
    def generate_tasks(self):
        # Return list of task dicts
        pass

    def execute_task(self, task):
        # Execute and return TaskResult
        pass

    def validate_result(self, result):
        # Validate and return bool
        pass
```

3. **Register in daemon**:
```python
# tools/evolution/daemon.py
self.modes = {
    'my_mode': MyMode(),
    # ...
}
```

4. **Add to config**: Update `modes` section in config.json

---

### Project Structure

```
tools/evolution/
├── __init__.py
├── daemon.py              # Main daemon service
├── task_queue.py          # SQLite queue manager
├── resource_manager.py    # Resource monitoring
├── agent_protocol.py      # Multi-agent network
├── modes/
│   ├── __init__.py
│   ├── base_mode.py       # Abstract interface
│   ├── self_improvement.py
│   ├── chaos_creative.py
│   └── research_discovery.py
└── communication/
    ├── __init__.py
    ├── rest_api.py        # FastAPI endpoints
    ├── web_dashboard.py   # Dashboard UI
    ├── websocket_stream.py
    └── local_exchange.py  # File-based messaging

tests/evolution/
├── test_daemon.py
├── test_task_queue.py
└── test_modes.py

scripts/
├── start_evolution.sh
├── stop_evolution.sh
└── install_service.sh
```

---

## License

Same as Context Foundry (check main project LICENSE)

## Contributing

Submit PRs to Context Foundry main repository.

## Support

- GitHub Issues: [context-foundry/context-foundry](https://github.com/context-foundry/context-foundry/issues)
- Documentation: [docs/](../docs/)

---

**Built autonomously by Context Foundry** 🤖

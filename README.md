<div align="center">
  <img src="docs/assets/cf_logo_twitter_2025.png" alt="Context Foundry" width="100%">
</div>

# Context Foundry

> *"Generate probabilistically, validate deterministically."*

**Autonomous AI development platform** that spawns fresh Claude instances to research, design, build, test, and deploy complete software projects. Walk away and come back to production-ready code.

**Version 2.4.0** | [Quick Start](QUICKSTART.md) | [Documentation](docs/) | [Features](docs/FEATURES.md)

---

## What is Context Foundry?

Context Foundry is an **autonomous development platform** with three main components:

| Component | Description |
|-----------|-------------|
| **MCP Server** | Model Context Protocol server that exposes build tools to Claude Code |
| **Daemon (cfd)** | Background service managing build queues, resource limits, and process monitoring |
| **CLI Tools** | Terminal interface for monitoring builds and managing the system |

Unlike traditional AI coding assistants that require constant supervision, Context Foundry runs complete build pipelines autonomously:

```
You: "Build a weather dashboard with React"
[Walk away for 10 minutes]
Result: Complete app deployed to GitHub, tests passing
```

---

## Core Philosophy

Context Foundry combines **probabilistic AI generation** with **deterministic validation**:

- **Probabilistic**: AI agents generate code freely using their full capabilities
- **Deterministic**: Code-level validators verify outputs, checksums detect unauthorized changes, phase contracts enforce handoffs

This hybrid approach makes autonomous operation reliable. See [Architecture](docs/ARCHITECTURE.md) for details.

---

## Key Features

### Build Pipeline

| Feature | Description |
|---------|-------------|
| **8-Phase Workflow** | Scout -> Architect -> Builder -> Test -> Docs -> Deploy -> Feedback |
| **Self-Healing Tests** | Automatically fixes test failures through redesign/rebuild cycles |
| **Parallel Execution** | AI decides when to spawn parallel agents for faster builds |
| **Incremental Builds** | Smart change detection rebuilds only what changed |

### Pattern Learning

| Feature | Description |
|---------|-------------|
| **Global Patterns** | Cross-project knowledge stored in `~/.context-foundry/patterns/` |
| **Context Codex** | SQLite database tracking issues, solutions, and build metrics |
| **Skills Library** | Reusable code implementations with success rate tracking |
| **S3 Sync** | Share patterns with the community via AWS S3 |

### Infrastructure

| Feature | Description |
|---------|-------------|
| **Daemon Service** | Background process with task queue, resource limits, watchdog |
| **Mission Control TUI** | Terminal interface for real-time build monitoring |
| **BAML Type Safety** | Structured JSON outputs with schema validation |
| **Deterministic Enforcement** | Post-phase validators, checksum verification, state machine |

### Extensions

| Extension | Domain |
|-----------|--------|
| **Roblox** | Luau scripting, world generation, asset management |
| **Flowise** | AI workflow automation |
| **Workday** | Enterprise integration |

---

## Architecture

```
                                    Context Foundry
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
    │   │  MCP Server │    │   Daemon    │    │  CLI / TUI  │        │
    │   │             │    │   (cfd)     │    │             │        │
    │   │ - Build API │    │ - Queue     │    │ - Monitor   │        │
    │   │ - Patterns  │    │ - Watchdog  │    │ - Dashboard │        │
    │   │ - Skills    │    │ - Resources │    │ - Logs      │        │
    │   └──────┬──────┘    └──────┬──────┘    └─────────────┘        │
    │          │                  │                                   │
    │          └────────┬─────────┘                                   │
    │                   │                                             │
    │          ┌────────▼────────┐                                    │
    │          │  Phase Executor │                                    │
    │          │                 │                                    │
    │          │ Scout ──────────┼──▶ scout_report.json              │
    │          │ Architect ──────┼──▶ architecture.json              │
    │          │ Builder ────────┼──▶ source code                    │
    │          │ Test ───────────┼──▶ test-report.md                 │
    │          │ Deploy ─────────┼──▶ GitHub repo                    │
    │          └────────┬────────┘                                    │
    │                   │                                             │
    │          ┌────────▼────────┐                                    │
    │          │   Validators    │  ◀── Deterministic Enforcement    │
    │          │                 │                                    │
    │          │ - File checks   │                                    │
    │          │ - Checksums     │                                    │
    │          │ - BAML schemas  │                                    │
    │          └─────────────────┘                                    │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
```

Each phase spawns a **fresh Claude instance** with isolated context, preventing token bloat and ensuring consistent quality across long builds.

---

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry

# Install dependencies
pip install -e .
```

### 2. Configure Claude Code

Add to your Claude Code MCP settings (`~/.claude/mcp_settings.json`):

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python",
      "args": ["/path/to/context-foundry/tools/mcp_server.py"]
    }
  }
}
```

### 3. Run a Build

In Claude Code:
```
Use mcp__context-foundry__autonomous_build_and_deploy to build a todo app with React
```

See [Quick Start Guide](QUICKSTART.md) for detailed setup instructions.

---

## CLI Tools

### Daemon Management

```bash
# Start the daemon
./tools/cfd start

# Check status
./tools/cfd status

# View build logs
./tools/cfd logs <job-id> --follow

# List active builds
./tools/cfd list

# Stop the daemon
./tools/cfd stop
```

### Mission Control TUI

```bash
# Launch terminal interface
python tools/cli.py
```

---

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `autonomous_build_and_deploy` | Full build pipeline: research -> design -> build -> test -> deploy |
| `delegate_to_claude_code` | Spawn fresh Claude instance for subtasks |
| `delegate_to_claude_code_async` | Non-blocking delegation with progress tracking |
| `read_global_patterns` | Read learned patterns by type |
| `save_global_patterns` | Save new patterns to global storage |
| `search_skills` | Find reusable code implementations |
| `save_skill` | Save successful implementation as reusable skill |
| `sync_patterns_to_s3` | Upload patterns to community S3 bucket |
| `pull_patterns_from_s3` | Download community patterns |
| `create_evolution_task` | Create self-improvement task |
| `get_daemon_status` | Check daemon health and resource usage |

See [MCP Tools Reference](docs/MCP_SETUP.md) for complete documentation.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Quick Start](QUICKSTART.md) | Get running in 5 minutes |
| [User Guide](docs/USER_GUIDE.md) | Detailed usage instructions |
| [Architecture](docs/ARCHITECTURE.md) | How it works under the hood |
| [Features](docs/FEATURES.md) | Complete feature reference |
| [Innovations](docs/INNOVATIONS.md) | Technical breakthroughs explained |
| [Phase Handoff Flow](docs/phase-handoff-flow.md) | Inter-phase data contracts |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and fixes |
| [FAQ](docs/FAQ.md) | Frequently asked questions |

---

## File Structure

```
context-foundry/
├── tools/
│   ├── mcp_server.py          # MCP server entry point
│   ├── mcp_utils/             # Build orchestration, delegation, patterns
│   ├── prompts/phases/        # Phase-specific system prompts
│   ├── evolution/             # Daemon, self-improvement, safety
│   ├── tui/                   # Mission Control terminal interface
│   ├── baml_schemas/          # Type-safe output schemas
│   ├── metrics/               # Cost and performance tracking
│   └── cfd                    # Daemon CLI script
├── extensions/
│   ├── roblox/                # Roblox game development
│   ├── flowise/               # AI workflow automation
│   └── workday/               # Enterprise integration
├── docs/                      # Documentation
└── CLAUDE.md                  # Instructions for AI agents
```

---

## Contributing

We welcome contributions. See [Contributing Guide](docs/CONTRIBUTING.md) for details.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

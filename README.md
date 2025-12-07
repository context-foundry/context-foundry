<div align="center">
  <img src="docs/assets/cf_logo_twitter_2025.png" alt="Context Foundry" width="100%">
</div>

# Context Foundry

> *"Generate probabilistically, validate deterministically."*

**Autonomous AI development platform** that spawns fresh Claude instances to research, design, build, test, and deploy complete software projects. Walk away and come back to production-ready code.

**Version 3.0.0** | [Quick Start](QUICKSTART.md) | [Documentation](docs/) | [Desktop App](#desktop-app)

---

<div align="center">
  <img src="docs/images/dashboard-hero.png" alt="Context Foundry Desktop" width="100%">
  <p><em>Context Foundry Desktop - Native macOS app for visual build monitoring</em></p>
</div>

---

## What is Context Foundry?

Context Foundry is an **autonomous development platform** with four main components:

| Component | Description |
|-----------|-------------|
| **Desktop App** | Native macOS application with visual dashboard, job monitoring, and AI Sidekick chat |
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
| **Context Codex** | SQLite database tracking issues, solutions, and build metrics |
| **Skills Library** | Reusable code implementations with success rate tracking |

### Infrastructure

| Feature | Description |
|---------|-------------|
| **Daemon Service** | Background process with task queue, resource limits, watchdog |
| **Mission Control TUI** | Terminal interface for real-time build monitoring |
| **BAML Type Safety** | Structured JSON outputs with schema validation |
| **Deterministic Enforcement** | Post-phase validators, checksum verification, state machine |

### Extensions

Extensions let you specialize Context Foundry for specific domains. Think of them as giving the AI a business case, architectural blueprints, and success criteria before asking it to build something complex.

Create an extension by adding domain-specific patterns, example implementations, and validation rules to `extensions/<your-domain>/`. The AI will reference these during builds to produce domain-appropriate solutions.

---

## Architecture

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant S as Scout Agent
    participant A as Architect Agent
    participant B as Builder Agent
    participant T as Test Agent
    participant FS as .context-foundry/

    U->>O: Task Description

    rect rgb(225, 245, 254)
        Note over O,S: Scout Phase
        O->>S: spawn claude --system-prompt phase_scout.txt
        S->>FS: Write scout_report.json
        S->>O: Return scout-report.md
        O->>O: Parse MD -> SCOUT_JSON
    end

    rect rgb(232, 245, 233)
        Note over O,A: Architect Phase
        O->>A: spawn claude --system-prompt phase_architect.txt<br/>+ SCOUT_JSON injected
        A->>FS: Write architecture.json
        A->>O: Return architecture.md
        O->>O: Parse MD -> ARCHITECTURE_JSON
    end

    rect rgb(255, 243, 224)
        Note over O,B: Builder Phase
        O->>B: spawn claude --system-prompt phase_builder.txt<br/>+ ARCHITECTURE_JSON injected
        B->>FS: Write build-tasks.json
        B->>FS: Write source code files
        B->>O: Return completion status
    end

    rect rgb(252, 228, 236)
        Note over O,T: Test Phase
        O->>T: spawn claude --system-prompt phase_test.txt<br/>+ ARCHITECTURE_JSON.test_plan
        T->>FS: Write test-report-N.md
        T->>O: Return PASSED/FAILED
    end

    alt Tests PASSED
        O->>U: Build Complete
    else Tests FAILED
        O->>A: Re-run with failure context
        Note over A,T: Loop: Architect Fix -> Builder Fix -> Test
    end
```

Each phase spawns a **fresh Claude instance** with isolated context, preventing token bloat and ensuring consistent quality across long builds.

---

## Understanding Phases and Agents

A common question: **Are Scout, Architect, Builder, etc. "agents" or "phases"?**

**Answer: Both.** They are **phases** from an orchestration perspective, and **ephemeral agent instances** from an execution perspective.

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     DAEMON (Orchestrator)                        │
│  runner.py manages pipeline state, spawns agents sequentially   │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐          ┌─────────┐
   │  Scout  │    →     │Architect│    →     │ Builder │  → ...
   │ Agent   │          │ Agent   │          │ Agent   │
   └─────────┘          └─────────┘          └─────────┘
   200K tokens          200K tokens          200K tokens
   (ephemeral)          (ephemeral)          (ephemeral)
        │                     │                     │
        ▼                     ▼                     ▼
   scout-prompt.json    architect-prompt.json  builder-prompt.json
   scout-report.md      architecture.md        (code files)
```

### Key Characteristics

| Aspect | Reality |
|--------|---------|
| **Context Window** | Each phase gets its own fresh 200K tokens |
| **Lifecycle** | Ephemeral - spawned, runs, exits, context gone |
| **Communication** | Via **disk artifacts** (not shared memory) |
| **Implementation** | Each is a `claude` CLI subprocess |
| **State** | Persisted in `.context-foundry/` between phases |

### Why This Design?

1. **Token efficiency** - 7 phases × 200K = 1.4M potential tokens vs. one 200K window that fills up
2. **Isolation** - Builder crashing doesn't lose Scout's analysis
3. **Resumability** - Can restart from any phase (disk has state)
4. **Specialization** - Each agent gets a focused prompt for its specific task

They're essentially **stateless workers** that read artifacts, do work, write artifacts, and disappear.

---

## Desktop App

Context Foundry Desktop is a **native macOS application** that provides a visual interface for monitoring and managing builds.

<div align="center">
  <img src="docs/images/job-detail.png" alt="Job Detail View" width="80%">
</div>

### Features

| Feature | Description |
|---------|-------------|
| **Visual Dashboard** | See all jobs at a glance with status, duration, and phase progress |
| **Live Duration Counter** | Real-time timer showing build progress in seconds |
| **AI Sidekick Chat** | Natural language interface to check status, trigger builds, and get help |
| **Phase Timeline** | Visual progress through Scout → Architect → Builder → Test phases |
| **Conversation View** | See what the AI is thinking during each phase |
| **Artifact Browser** | View generated code with syntax highlighting and line numbers |
| **Dark Theme** | Native dark mode with beautiful purple accents |

### Install Desktop App

```bash
# Download from releases (macOS)
curl -L https://github.com/your-org/context-foundry/releases/latest/download/ContextFoundry.dmg -o ContextFoundry.dmg
open ContextFoundry.dmg

# Or build from source
cd apps/context-foundry-desktop
npm install
npm run tauri:build
```

See [Desktop App Documentation](apps/context-foundry-desktop/README.md) for full details.

---

## Quick Start

### Option 1: Desktop App (Recommended)

1. Download and install the Desktop App (see above)
2. Launch Context Foundry Desktop
3. Use the Sidekick chat to start your first build:
   ```
   "Build a todo app with React"
   ```

### Option 2: CLI

```bash
# Install via npm
npm install -g context-foundry

# Start the daemon
cfd start

# Build something
cf build "Create a weather dashboard with React"
```

This installs the package and automatically configures Claude Code. (Alternative: `pip install context-foundry && cf setup`)

### Option 3: Claude Code Integration

In Claude Code, just ask in natural language:

```
"Use CF to build a weather dashboard with React"
```

Walk away. Come back to deployed code on GitHub.

See [Quick Start Guide](QUICKSTART.md) for detailed setup instructions.

---

## CLI Tools

### Mission Control TUI

```bash
cf                    # Launch interactive terminal UI
```

### Daemon Management

```bash
cfd start             # Start the daemon
cfd status            # Check status
cfd logs <job-id>     # View build logs
cfd list              # List active builds
cfd stop              # Stop the daemon
```

---

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `autonomous_build_and_deploy` | Full build pipeline: research -> design -> build -> test -> deploy |
| `delegate_to_claude_code` | Spawn fresh Claude instance for subtasks |
| `delegate_to_claude_code_async` | Non-blocking delegation with progress tracking |
| `search_skills` | Find reusable code implementations |
| `save_skill` | Save successful implementation as reusable skill |
| `create_evolution_task` | Create self-improvement task |
| `get_daemon_status` | Check daemon health and resource usage |

See [MCP Tools Reference](docs/MCP_SETUP.md) for complete documentation.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Quick Start](QUICKSTART.md) | Get running in 5 minutes |
| [Desktop App](apps/context-foundry-desktop/README.md) | Native macOS/Windows application |
| [Dashboard](tools/dashboard/README.md) | Web dashboard development guide |
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
├── apps/
│   └── context-foundry-desktop/  # Native macOS/Windows desktop app (Tauri)
├── tools/
│   ├── dashboard/             # React dashboard frontend
│   ├── mcp_server.py          # MCP server entry point
│   ├── mcp_utils/             # Build orchestration, delegation, patterns
│   ├── prompts/phases/        # Phase-specific system prompts
│   ├── evolution/             # Daemon, self-improvement, safety
│   ├── cli.py                 # Main CLI (cf command)
│   └── cfd                    # Daemon CLI script
├── context_foundry/
│   └── daemon/                # Python daemon (HTTP API, job management)
├── extensions/                # Domain-specific extensions
├── npm/                       # npm package wrapper
├── docs/                      # Documentation
└── CLAUDE.md                  # Instructions for AI agents
```

---

## Contributing

We welcome contributions. See [Contributing Guide](docs/CONTRIBUTING.md) for details.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

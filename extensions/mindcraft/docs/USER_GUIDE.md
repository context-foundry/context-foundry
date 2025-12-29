# Mindcraft User Guide

This guide explains how to operate, debug, and extend the Mindcraft Orchestrator.

## 📋 Table of Contents
1. [Deployment](#deployment)
2. [Operating the Agents](#operating-the-agents)
3. [Troubleshooting](#troubleshooting)
4. [Advanced Configuration](#advanced-configuration)

---

## Deployment

### Prerequisites
- **Python 3.8+**
- **Context Foundry** installed
- **MindServer** running (e.g., `mineflayer-mindserver` on a Minecraft server)

### 1. Install Dependencies
```bash
pip install "python-socketio[client]" aiohttp pydantic
```

### 2. Install Tools
Run the installer script to link tools to your `~/.context-foundry/tools` directory:
```bash
python3 scripts/install_mindcraft.py
```

---

## Operating the Agents

### Starting the Orchestrator
The Orchestrator is the main process. It runs indefinitely, managing all agents.

**Dry Run (Testing):**
```bash
python3 ~/.context-foundry/tools/mindcraft_orchestrate.py --dry-run
```

**Live Production:**
```bash
# Set your server URL first!
export MINDCRAFT_SERVER_URL="wss://andy.minepad.cc"
python3 ~/.context-foundry/tools/mindcraft_orchestrate.py
```

### Manual Control
You can override the orchestrator or check status manually using the helper tools.

**Check Status:**
```bash
python3 ~/.context-foundry/tools/mindcraft_status.py
```

**Send a Message:**
```bash
python3 ~/.context-foundry/tools/mindcraft_agent.py --agent andy --msg "Go to sleep"
```

**Restart an Agent:**
```bash
python3 ~/.context-foundry/tools/mindcraft_agent.py --agent andy --restart
```

---

## Troubleshooting

### "Failed to connect"
- Check if your **MindServer** is actually running.
- Verify the URL (`wss://...` vs `ws://...`).
- Check firewalls/ports (default is 8080 or 443 depending on setup).

### Agent is Stuck
- The `monitor` module automatically detects stuck agents (stationary for >5 seconds).
- It will log a warning. In the future, it will auto-nudge them.
- **Manual Fix:** Use `mindcraft_agent.py --restart`.

### LLM / Planner Errors
- Ensure `claude` CLI is installed and authenticated (`claude login`).
- The Planner uses `claude` subprocess calls. If `claude` is not in your PATH, it will fail.
- Check logs in `~/.context-foundry/mindcraft/logs/`.

---

## Advanced Configuration

### Data Models
- **Goals:** Defined in `goals.py`. Types: Build, Gather, Explore, Survive.
- **State:** Defined in `models.py`. Includes Inventory, Biome, Gamemode.

### modifying Behavior (The Brain)
- **Prompts:** Edit `prompts/planner_system.md` to change the agent's personality or priorities.
- high priority goals are processed first.

### Persistence
- **State Files:** `~/.context-foundry/mindcraft/state/{agent}_state.json`
- **History:** `~/.context-foundry/mindcraft/logs/orchestration.jsonl`
- You can manually edit `state.json` to "inject" a fake state for testing.

# 🧠 Mindcraft Orchestrator

**Autonomous Minecraft Agent Framework for Context Foundry**

The Mindcraft Orchestrator enables 24/7 autonomous Minecraft agents driven by LLMs. It provides a complete "Body" (Client), "Eyes" (State Monitor), "Brain" (Planner), and "Hands" (Orchestrator) for your bots.

## 🌟 Features

*   **Real-time Control:** Bidirectional communication via Socket.io to MindServer.
*   **State Awareness:** Monitors health, hunger, inventory, and world events (Death, Night).
*   **Goal Planning:** Autonomous goal generation and prioritization using LLMs (Claude).
*   **Persistence:** Saves agent state and history to disk.
*   **Context Foundry Native:** Built as a first-class Extension with CLI tools.

## 🚀 Quick Start

### 1. Installation
The extension is built into Context Foundry. You just need to install the dependencies and tools.

```bash
# On your VPS or local machine
git pull
pip install "python-socketio[client]" aiohttp pydantic

# Install CLI tools to ~/.context-foundry/tools/
python3 scripts/install_mindcraft.py
```

### 2. Configuration
The system auto-detects configuration from Environment Variables (Recommended for VPS) or a config file.

**Option A: Environment Variables (Best for Docker/VPS)**
```bash
export MINDCRAFT_SERVER_URL="wss://your-server.com"
export MINDCRAFT_AGENTS="andy,bob"
```

**Option B: Config File**
Edit `~/.context-foundry/mindcraft/config.json`:
```json
{
  "server_url": "wss://andy.minepad.cc",
  "agents": ["andy"],
  "dry_run": false
}
```

### 3. Run It!
Start the autonomous loop:

```bash
# Dry Run (Simulation)
python3 ~/.context-foundry/tools/mindcraft_orchestrate.py --dry-run

# Live Connection
python3 ~/.context-foundry/tools/mindcraft_orchestrate.py
```

---

## 🛠 CLI Tools

The extension provides several standalone tools in `~/.context-foundry/tools/`:

| Tool | Description | Usage |
|------|-------------|-------|
| `mindcraft_orchestrate.py` | **The Main Loop.** Runs the full autonomous system. | `python3 mindcraft_orchestrate.py` |
| `mindcraft_status.py` | Check agent status (Health, Location). | `python3 mindcraft_status.py` |
| `mindcraft_agent.py` | Manual control (Chat, Start/Stop). | `python3 mindcraft_agent.py --msg "Hello"` |
| `mindcraft_config.py` | View or edit configuration. | `python3 mindcraft_config.py --view` |

## 🏗 Architecture

The system is composed of 4 main phases:

1.  **Foundation (`client.py`):** Handles raw Socket.io connectivity.
2.  **State Awareness (`monitor.py`, `models.py`):** Tracks changes and detects anomalies (stuck, death).
3.  **Planning (`planner.py`, `goals.py`):** Generates high-level goals ("Gather Wood") using `prompts/planner_system.md`.
4.  **Autonomy (`orchestrator.py`):** runs the main loop `Observe -> Plan -> Act`.

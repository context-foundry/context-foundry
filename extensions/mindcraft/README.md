# Mindcraft Orchestrator

**Autonomous Minecraft Agent Framework for Context Foundry**

The Mindcraft Orchestrator enables 24/7 autonomous Minecraft agents driven by LLMs. It provides intelligent control, state monitoring, and multiple operational modes for your bots.

## Features

- **LLM-Powered Intelligence:** Uses Claude CLI for context-aware responses and decisions
- **Multiple Modes:** Builder, Helper, and Defender modes for different play styles
- **RCON Integration:** Admin commands for giving items, teleporting, and server control
- **State Awareness:** Monitors health, hunger, position, and detects stuck agents
- **Auto-Rescue:** Detects underground/stuck agents and teleports them to safety
- **Unlimited Supplies:** Agents can request any items via RCON admin commands

## Quick Start

### Easy Mode Switching

Use the mode switcher script to quickly change Andy's behavior:

```bash
cd /home/chuck/homelab/context-foundry/extensions/mindcraft

# Start Andy in builder mode (builds villages, unlimited supplies)
./andy-mode.sh builder

# Start Andy in helper mode (follows players, assists with tasks)
./andy-mode.sh helper

# Start Andy in defender mode (combat, mob hunting, protection)
./andy-mode.sh defender

# Stop the orchestrator
./andy-mode.sh stop

# Check status
./andy-mode.sh status
```

### Manual Start

```bash
cd /home/chuck/homelab/context-foundry

# Start with specific mode
python -m extensions.mindcraft.orchestrator --mode builder
python -m extensions.mindcraft.orchestrator --mode helper
python -m extensions.mindcraft.orchestrator --mode defender
```

## Modes

### Builder Mode
Andy becomes a master village builder with unlimited supplies.
- Assigns building projects (houses, farms, towers, villages)
- Gives any materials Andy requests via RCON
- Focuses 100% on construction, never resource gathering
- Progressive complexity from simple houses to grand plazas

### Helper Mode
Andy becomes a helpful companion to players.
- Follows players and assists with their tasks
- Helps mine, build, and explore
- Places torches in dark areas
- Fights mobs that threaten players
- Doesn't start independent projects

### Defender Mode
Andy becomes a combat guardian.
- Patrols the village perimeter
- Hunts hostile mobs proactively
- Protects players from threats
- Equipped with full combat gear
- Priority: creepers > skeletons > zombies

## Mode Equipment Kits

Each mode automatically equips Andy with appropriate gear:

| Mode | Equipment |
|------|-----------|
| Builder | Diamond pickaxe, shovel, axe, 256 each of cobblestone/oak planks/glass, torches, doors |
| Helper | Diamond pickaxe, shovel, sword, shield, 64 torches, food, building blocks |
| Defender | Netherite sword, bow, 64 arrows, full diamond armor, shield, golden apples |

## RCON Commands

The orchestrator can execute any Minecraft command via RCON:

```python
# Give items
/give andy diamond_pickaxe 1
/give andy cobblestone 256

# Teleport
/tp andy 288 85 -48

# Effects
/effect give andy minecraft:regeneration 30 2
```

## Auto-Rescue System

The orchestrator automatically detects and rescues stuck agents:

- **Underground Detection:** If agent Y < 75, teleports to spawn
- **Stuck Detection:** If agent hasn't moved in 5+ checks, rescues
- **Invalid Position:** Skips Y=0 positions (indicates unloaded state)
- **Cooldowns:** 60-second rescue cooldown, 5-minute kit cooldown

## Logs

View orchestrator activity:
```bash
tail -f /tmp/orch_log.txt
```

## Architecture

```
orchestrator.py
├── LLM Integration (Claude CLI)
├── RCON Commands (docker exec rcon-cli)
├── Socket.io Client (MindServer connection)
├── State Monitor (position, health, inventory)
├── Stuck Detection & Auto-Rescue
└── Mode System (builder/helper/defender)
```

## Prompts

Mode-specific prompts are in `prompts/`:
- `mode_builder.md` - Village builder system prompt
- `mode_helper.md` - Helper companion system prompt
- `mode_defender.md` - Combat guardian system prompt

## Dependencies

- Python 3.8+
- python-socketio[client]
- Claude CLI (for LLM responses)
- Docker (for RCON access to Minecraft server)

# Context Foundry - Mindcraft Extension

## CRITICAL RULES - READ FIRST

### 1. AVOID WATER AT ALL COSTS
```
WATER IS THE ENEMY. Bots get stuck in water.
Never send agents near water. Always check for water before any action.
Include water_avoidance_radius: 5 in all pathfinding.
```

### 2. BE HELPFUL TO HUMANS
```
PRIMARY DIRECTIVE: Help human players on the server.
When humans join, prioritize assisting them with their objectives.
Gathering and building support takes priority over exploration.
```

### 3. RIDE THE SUBSCRIPTION
```
NEVER use Claude API directly.
ALWAYS use `claude` CLI to ride the subscription.
Use Context Foundry's delegation system for LLM planning.
```

## Quick Start

### Check Status
```python
# From CLI tool
python extensions/mindcraft/tools/mindcraft_status.py --dry-run

# Check if extension is available
from extensions.mindcraft import is_mindcraft_available
print(is_mindcraft_available())
```

### Send Command to Agent
```python
# Dry run test
python extensions/mindcraft/tools/mindcraft_agent.py \
    --agent andy \
    --command "Hello from Context Foundry!" \
    --dry-run

# Real command (requires server connection)
python extensions/mindcraft/tools/mindcraft_agent.py \
    --agent andy \
    --command "!collectBlocks(\"oak_log\", 64)"
```

### Configure Server
```bash
# Initialize config
python extensions/mindcraft/tools/mindcraft_config.py --action init

# Set server URL
python extensions/mindcraft/tools/mindcraft_config.py \
    --action set \
    --key server_url \
    --value "wss://andy.minepad.cc"
```

## Agent Names

| Agent | Theme | Purpose |
|-------|-------|---------|
| Andy | Original | Primary agent, general tasks |
| Dude | Big Lebowski | Future: Chill gathering |
| Walter | Big Lebowski | Future: Building/defending |
| Donny | Big Lebowski | Future: Assistance |

## Mindcraft Commands

Common commands the agents understand:

| Command | Description |
|---------|-------------|
| `!collectBlocks("block_name", count)` | Gather blocks |
| `!followPlayer("player_name")` | Follow a player |
| `!goToPosition(x, y, z)` | Move to coordinates |
| `!stop` | Stop current action |
| `!stay(-1)` | Stay in place |
| `!inventory` | Show inventory |
| `!nearbyBlocks` | List nearby blocks |

## Configuration

### Environment Variables
```bash
MINDCRAFT_SERVER_URL=wss://andy.minepad.cc
MINDCRAFT_AGENTS=andy
MINDCRAFT_DRY_RUN=false
```

### Config File
Location: `~/.context-foundry/mindcraft/config.json`

```json
{
  "server_url": "wss://andy.minepad.cc",
  "agents": ["andy"],
  "safety": {
    "avoid_blocks": ["water", "lava", "cactus"],
    "water_avoidance_radius": 5,
    "max_deaths_per_hour": 10
  },
  "notifications": {
    "discord_webhook": null,
    "notify_on_death": true,
    "notify_on_human_join": true
  }
}
```

## Safety Patterns

### Water Avoidance (CRITICAL)
```python
# Before any movement command, check for water
def is_safe_destination(x, y, z):
    # Query nearby blocks
    # Return False if water within water_avoidance_radius
    pass

# Use safe commands
"!goToPosition(x, y, z)" # ONLY after water check
```

### Death Recovery
When agent dies:
1. Log death event
2. Wait for respawn
3. Send to safe location (not near water!)
4. Resume previous goal

## Integration with Context Foundry

### Read Patterns
```python
# Before planning, check for known issues
patterns = mcp__context-foundry__read_global_patterns("common-issues")
minecraft_patterns = [p for p in patterns if p.get("domain") == "mindcraft"]
```

### Save New Patterns
```python
# After discovering an issue, save the pattern
new_pattern = {
    "id": "mc-xxx",
    "domain": "mindcraft",
    "category": "safety",
    "issue": "Description of what went wrong",
    "solution": "How to avoid it",
    "frequency": 1
}
# Add to patterns and save
```

### Delegation for Planning
```python
# Use claude CLI for LLM planning (rides subscription)
mcp__context-foundry__delegate_to_claude_code(
    task="Given agent inventory: {...}, generate next goal",
    working_directory="/path/to/context-foundry"
)
```

## Directory Structure

```
extensions/mindcraft/
├── CLAUDE.md           # This file - READ FIRST
├── __init__.py         # Extension entry point
├── detector.py         # Configuration detection
├── extensions_loader.py # Safe loading interface
├── client.py           # Socket.io client
├── tools/              # Standalone CLI tools
│   ├── mindcraft_agent.py
│   ├── mindcraft_status.py
│   └── mindcraft_config.py
├── patterns/           # Domain-specific patterns
│   └── mindcraft-common-issues.json
└── tests/
```

## Deployment

### VPS Setup (minepad.cc)
1. Clone Context Foundry repo
2. Run `python scripts/install_mindcraft.py`
3. Configure `~/.context-foundry/mindcraft/config.json`
4. Start orchestrator (Phase 4)

### Local Development
```bash
# Test with dry run mode
export MINDCRAFT_DRY_RUN=true
python extensions/mindcraft/tools/mindcraft_status.py
```

## Troubleshooting

### "python-socketio not installed"
```bash
pip install python-socketio[client] aiohttp
```

### "Failed to connect to MindServer"
- Check MINDCRAFT_SERVER_URL is correct
- Verify MindServer is running on VPS
- Try with --dry-run first

### "Agent not found"
- Check agent name is correct (case-sensitive)
- Verify agent is registered with MindServer
- Check agent is started

## References

- [Implementation Plan](../../docs/plans/MINDCRAFT-ORCHESTRATOR-IMPLEMENTATION-PLAN.md)
- [Mindcraft GitHub](https://github.com/kolbytn/mindcraft)
- [Context Foundry Extensions](../)

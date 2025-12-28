# Context Foundry Mindcraft Orchestrator - Implementation Plan

**Status:** DRAFT - Awaiting Approval
**Created:** 2025-12-28
**Author:** Claude (Opus 4.5) + Human Collaboration
**Decision Required:** Architecture direction (Extension vs Fork)

---

## Executive Summary

This plan outlines how to extend Context Foundry to orchestrate Mindcraft AI agents in Minecraft. The goal is **24/7 autonomous building and operation** - agents that work while you sleep, continuously constructing, gathering, and improving your Minecraft world.

### Current Setup
- Minecraft server: `minepad.cc`
- Mindcraft dashboard: `https://andy.minepad.cc/`
- Mindcraft JS running in Docker container
- Existing agent(s): Andy (and potentially others)

### Target State
Context Foundry becomes the "brain" that gives Mindcraft agents high-level goals, monitors their progress, adapts plans based on world state, and learns patterns from successes/failures.

---

## Decision: Extension (Recommended) vs Fork

### Recommendation: **Extension**

| Factor | Extension | Fork |
|--------|-----------|------|
| Maintenance | Single codebase | Two codebases to maintain |
| Pattern sharing | Automatic via global patterns | Manual sync required |
| MCP tools | Reuse existing delegation/patterns | Duplicate infrastructure |
| Updates | Get Context Foundry improvements | Manual merge required |
| Isolation | Domain-specific code isolated | Complete separation |

**Rationale:** This is a new domain (Minecraft/Mindcraft) similar to Roblox, Flowise, and Workday extensions. It doesn't modify core Context Foundry behavior - it adds new capabilities through the existing extension system.

**Location:** `extensions/mindcraft/`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Context Foundry (Your Machine)                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   Mindcraft Extension                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │   │
│  │  │ Goal Planner │  │ State        │  │ Pattern         │   │   │
│  │  │ (LLM-based)  │  │ Monitor      │  │ Learner         │   │   │
│  │  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘   │   │
│  │         │                 │                    │            │   │
│  │  ┌──────▼─────────────────▼────────────────────▼────────┐  │   │
│  │  │              Mindcraft Socket.io Client               │  │   │
│  │  └──────────────────────────┬────────────────────────────┘  │   │
│  └─────────────────────────────┼────────────────────────────────┘   │
└────────────────────────────────┼────────────────────────────────────┘
                                 │ WebSocket (Socket.io)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    minepad.cc (Your Server)                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   Mindcraft MindServer                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   Andy       │  │   Bob        │  │   ...        │      │   │
│  │  │   Agent      │  │   Agent      │  │   Agents     │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│                    Minecraft Server (Java)                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. Mindcraft Socket.io Client (`client.py`)

**Purpose:** Real-time bidirectional communication with Mindcraft server

**Key Functions:**
```python
class MindcraftClient:
    def connect(server_url: str) -> bool
    def disconnect() -> None

    # Agent Control
    def send_message(agent_name: str, message: str) -> None
    def start_agent(agent_name: str) -> None
    def stop_agent(agent_name: str) -> None
    def restart_agent(agent_name: str) -> None
    def create_agent(name: str, profile: dict) -> None
    def destroy_agent(agent_name: str) -> None

    # State Queries
    def get_agent_status(agent_name: str) -> AgentStatus
    def get_all_agents() -> List[AgentStatus]
    def subscribe_to_updates(callback: Callable) -> None

    # Configuration
    def get_agent_settings(agent_name: str) -> dict
    def set_agent_settings(agent_name: str, settings: dict) -> None
```

**Socket.io Events (from Mindcraft research):**
- `send-message` - Send commands to agents
- `agents-status` - Receive agent statuses
- `state-update` - Real-time state updates (1000ms interval)
- `bot-output` - Agent console output
- `chat-message` - Inter-agent communication

### 2. Goal Planner (`planner.py`)

**Purpose:** Generate high-level goals and break them into agent-executable tasks

**Architecture Decision:** LLM-based planning vs Rule-based

| Approach | Pros | Cons |
|----------|------|------|
| LLM-based | Flexible, creative, adapts to context | Cost, latency, unpredictable |
| Rule-based | Fast, predictable, cheap | Rigid, requires manual rules |
| Hybrid (Recommended) | Best of both | More complex |

**Hybrid Approach:**
1. LLM generates high-level goals based on world state
2. Rule engine translates goals into Mindcraft commands
3. LLM handles exceptions and creative problem-solving

**Goal Types:**
```python
@dataclass
class Goal:
    id: str
    type: GoalType  # BUILD, GATHER, EXPLORE, DEFEND, FARM, CRAFT
    description: str
    priority: int
    dependencies: List[str]  # Other goal IDs
    success_criteria: dict
    estimated_duration: Optional[int]  # seconds
    assigned_agent: Optional[str]
    status: GoalStatus  # PENDING, IN_PROGRESS, COMPLETED, FAILED, BLOCKED

class GoalType(Enum):
    BUILD = "build"        # Construct structures
    GATHER = "gather"      # Collect resources
    EXPLORE = "explore"    # Map new areas
    DEFEND = "defend"      # Protect from mobs
    FARM = "farm"          # Agriculture
    CRAFT = "craft"        # Create items
    MAINTAIN = "maintain"  # Repair/upkeep
```

**Planning Loop:**
```
Every N minutes:
  1. Query world state (agent positions, inventories, nearby blocks)
  2. Check goal completion status
  3. If goals completed → generate new goals
  4. If goals blocked → diagnose and adapt
  5. Prioritize and assign goals to agents
  6. Send commands via Mindcraft client
```

### 3. State Monitor (`monitor.py`)

**Purpose:** Track world state, agent health, and detect anomalies

**Key Metrics:**
```python
@dataclass
class AgentState:
    name: str
    health: float
    hunger: float
    position: Tuple[float, float, float]
    biome: str
    gamemode: str
    inventory: List[InventoryItem]
    equipped: List[str]
    current_action: str
    last_message: str
    online: bool
    last_seen: datetime
```

**Monitoring Features:**
- Agent death detection → auto-restart with recovery goals
- Stuck detection (no movement/progress) → intervention
- Resource thresholds → trigger gathering goals
- Night cycle → shelter/defense behaviors
- Inventory full → storage/crafting triggers

### 4. Pattern Learner (`patterns.py`)

**Purpose:** Learn from successes and failures, integrate with Context Foundry pattern system

**Pattern Types for Minecraft:**
```json
{
  "patterns": [
    {
      "id": "mc-001",
      "domain": "mindcraft",
      "category": "building",
      "issue": "Agent gets stuck building over water",
      "solution": "Pre-check for water blocks, place platform first",
      "frequency": 5,
      "success_rate": 0.85
    },
    {
      "id": "mc-002",
      "domain": "mindcraft",
      "category": "survival",
      "issue": "Agent dies at night without shelter",
      "solution": "Track time, prioritize shelter goal before nightfall",
      "frequency": 12
    }
  ]
}
```

**Integration with Context Foundry:**
```python
# Read existing patterns before planning
patterns = mcp__context-foundry__read_global_patterns("common-issues")
minecraft_patterns = [p for p in patterns if p.get("domain") == "mindcraft"]

# Save new patterns after learning
mcp__context-foundry__save_global_patterns("common-issues", updated_patterns)
```

### 5. Standalone Tools Interface (FileSystem Discovery)

**Purpose:** Expose Mindcraft orchestration as standalone scripts for automatic discovery by `filesystem_tools.py`

**Architecture Change:**
Instead of modifying `mcp_server.py`, we will provide standalone Python scripts in `extensions/mindcraft/tools/`. These will be symlinked/copied to `~/.context-foundry/tools/` for zero-config discovery by the MCP server.

**Tool Scripts:**
```python
# extensions/mindcraft/tools/mindcraft_orchestrate.py
def main(
    action: str, # "start", "stop", "status"
    server_url: str = DEFAULT_URL,
    goals: List[str] = [],
    autonomous_mode: bool = True
):
    """Control the high-level orchestration loop"""
    pass

# extensions/mindcraft/tools/mindcraft_goal.py
def main(
    action: str, # "add", "list", "cancel"
    goal_type: str = "build",
    description: str = "",
    priority: int = 5
):
    """Manage agent goals"""
    pass

# extensions/mindcraft/tools/mindcraft_agent.py
def main(
    agent_name: str,
    command: str
):
    """Direct agent control (pass-through)"""
    pass

# extensions/mindcraft/tools/mindcraft_config.py
def main(
    action: str = "get",
    key: Optional[str] = None,
    value: Optional[str] = None
):
    """Manage Mindcraft configuration"""
    pass
```

**Installation:**
A helper script `scripts/install_mindcraft.py` will link these tools to the global context foundry tools directory.

### 6. Persistence Layer (`persistence.py`)

**Purpose:** Maintain state across restarts, enable resume

**Storage Location:** `~/.context-foundry/mindcraft/`

**Files:**
```
~/.context-foundry/mindcraft/
├── config.json           # Server URL, agents, settings
├── goals/
│   ├── active.json       # Current goal queue
│   └── history.json      # Completed/failed goals
├── state/
│   ├── world_state.json  # Last known world state
│   └── agent_states.json # Per-agent state snapshots
├── patterns/
│   └── mindcraft-patterns.json  # Domain-specific patterns
└── logs/
    └── orchestration.log # Activity log
```

---

## Implementation Phases

### Phase 1: Foundation (Core Infrastructure)
**Goal:** Basic connectivity, extension compliance, and manual control

**Tasks:**
1. Create `extensions/mindcraft/` directory structure
2. Implement **Standard Extension Contract**:
    - `detector.py`: Detect Mindcraft configuration
    - `extensions_loader.py`: Safe loading interface
3. Implement Socket.io client with **Dry Run** mode
4. Create standalone tool scripts in `extensions/mindcraft/tools/`
5. Create `scripts/install_mindcraft.py` to link tools to global directory
6. Create CLAUDE.md with usage instructions
7. Test: Connect to andy.minepad.cc (or dry run), send message, receive status

**Deliverables:**
- [ ] `extensions/mindcraft/__init__.py`
- [ ] `extensions/mindcraft/detector.py`
- [ ] `extensions/mindcraft/extensions_loader.py`
- [ ] `extensions/mindcraft/client.py` (with Dry Run support)
- [ ] `extensions/mindcraft/tools/*.py` (Standalone scripts)
- [ ] `scripts/install_mindcraft.py`
- [ ] `extensions/mindcraft/CLAUDE.md`

**Validation:**
```bash
# Install tools
python scripts/install_mindcraft.py

# Verify discovery
mcp__context_foundry__search_tools("mindcraft")

# Test connection (Dry Run if server unavailable)
python extensions/mindcraft/tools/mindcraft_agent.py --agent andy --command "Hello" --dry-run
```

### Phase 2: State Awareness
**Goal:** Understand world state, track agents

**Tasks:**
1. Implement state monitor with real-time updates
2. Add agent health/hunger/position tracking
3. Implement persistence layer
4. Add anomaly detection (death, stuck, offline)
5. Test: Monitor agents for 1 hour, log all state changes

**Deliverables:**
- [ ] `extensions/mindcraft/monitor.py`
- [ ] `extensions/mindcraft/persistence.py`
- [ ] `extensions/mindcraft/models.py` (data classes)

**Validation:**
```python
# Run monitor for 1 hour, verify:
# - State updates logged every ~1 second
# - Agent deaths detected and logged
# - Position changes tracked
# - Persistence survives restart
```

### Phase 3: Goal Planning
**Goal:** Autonomous goal generation and execution

**Tasks:**
1. Design goal data model
2. Implement rule-based goal translator (goal → Mindcraft commands)
3. Add LLM-based goal generator (world state → goals)
4. Implement goal queue with priorities
5. Add goal completion detection
6. Test: Generate "gather 64 wood" goal, execute, verify completion

**Deliverables:**
- [ ] `extensions/mindcraft/planner.py`
- [ ] `extensions/mindcraft/goals.py`
- [ ] `extensions/mindcraft/prompts/` (LLM prompts for planning)

**Validation:**
```python
# Test goal lifecycle:
goal = mindcraft_add_goal("gather", "Collect 64 oak logs", priority=10)
# Wait...
status = mindcraft_get_goal_status(goal.id)
assert status == "completed"
```

### Phase 4: Autonomous Loop
**Goal:** 24/7 autonomous operation

**Tasks:**
1. Implement main orchestration loop
2. Add scheduling (planning intervals)
3. Implement error recovery and retry logic
4. Add night/day cycle awareness
5. Multi-agent coordination (if multiple agents)
6. Test: Run autonomously for 24 hours

**Deliverables:**
- [ ] `extensions/mindcraft/orchestrator.py`
- [ ] `extensions/mindcraft/scheduler.py`
- [ ] `scripts/start_mindcraft_orchestrator.py`

**Validation:**
```bash
# Start orchestrator
python scripts/start_mindcraft_orchestrator.py --server wss://andy.minepad.cc

# Check after 24 hours:
# - Agents still online
# - Goals completed
# - No critical errors
# - World has visible changes (builds, farms, etc.)
```

### Phase 5: Pattern Learning
**Goal:** Learn from experience, improve over time

**Tasks:**
1. Integrate with Context Foundry pattern system
2. Implement failure analysis
3. Add success pattern extraction
4. Auto-update patterns after significant events
5. Create `scripts/bootstrap_mindcraft_patterns.py` to seed the global codex
6. Test: Intentionally cause failure, verify pattern saved

**Deliverables:**
- [ ] `extensions/mindcraft/patterns.py`
- [ ] `patterns/mindcraft-common-issues.json`
- [ ] `scripts/bootstrap_mindcraft_patterns.py`

**Validation:**
```python
# Bootstrapping
python scripts/bootstrap_mindcraft_patterns.py

# Cause agent death, verify pattern recorded:
patterns = read_global_patterns("common-issues")
minecraft_patterns = [p for p in patterns if p["domain"] == "mindcraft"]
assert len(minecraft_patterns) > 0
```

### Phase 6: Advanced Features (Future)
**Goal:** Enhanced capabilities

**Potential Features:**
- Blueprint system (save/load structure designs)
- Multi-server support
- Web dashboard for monitoring
- Voice notifications via Discord
- Integration with other Context Foundry extensions

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Agent destroys builds | Medium | High | Add "protected zones" concept, confirmation for destructive actions |
| Socket connection drops | High | Medium | Auto-reconnect with exponential backoff |
| LLM generates bad goals | Medium | Medium | Rule-based validation, safe defaults |
| Server costs (LLM calls) | Medium | Low | Cache decisions, batch planning |
| Agent gets permanently stuck | Medium | Low | Timeout detection, manual override |

---

## Configuration

### Configuration Precedence
1. **Environment Variables** (Highest)
2. **Config File** (`~/.context-foundry/mindcraft/config.json`)
3. **Defaults** (Lowest)

### Environment Variables
```bash
# Required
MINDCRAFT_SERVER_URL=wss://andy.minepad.cc
MINDCRAFT_AGENTS=andy,bob  # Comma-separated

# Optional
MINDCRAFT_PLANNING_INTERVAL=300  # seconds
MINDCRAFT_AUTO_RESTART=true
MINDCRAFT_LLM_MODEL=claude-3-5-sonnet  # For planning
MINDCRAFT_DEBUG=false
MINDCRAFT_DRY_RUN=false
```

### Config File (`~/.context-foundry/mindcraft/config.json`)
```json
{
  "server_url": "wss://andy.minepad.cc",
  "agents": ["andy"],
  "planning": {
    "interval_seconds": 300,
    "model": "claude-3-5-sonnet",
    "max_concurrent_goals": 3
  },
  "safety": {
    "avoid_blocks": ["water", "lava", "cactus"],  // CRITICAL: Water kills bots
    "water_avoidance_radius": 5,  // Stay 5 blocks away from water
    "protected_zones": [
      {"center": [100, 64, 100], "radius": 50, "name": "spawn"}
    ],
    "banned_commands": ["!clearChat"],
    "max_deaths_per_hour": 10
  },
  "notifications": {
    "discord_webhook": null,
    "notify_on_death": true,
    "notify_on_goal_complete": false
  }
}
```

---

## Directory Structure

```
extensions/mindcraft/
├── __init__.py
├── CLAUDE.md                 # Instructions for Claude Code agents
├── README.md                 # Human documentation
│
├── detector.py               # Extension detection logic
├── extensions_loader.py      # Extension loading interface
├── client.py                 # Socket.io client
├── monitor.py                # State monitoring
├── planner.py                # Goal planning
├── goals.py                  # Goal data model and queue
├── orchestrator.py           # Main autonomous loop
├── persistence.py            # State persistence
├── patterns.py               # Pattern learning integration
├── models.py                 # Data classes
│
├── tools/                    # Standalone MCP Tools
│   ├── mindcraft_orchestrate.py
│   ├── mindcraft_goal.py
│   ├── mindcraft_agent.py
│   └── mindcraft_config.py
│
├── prompts/
│   ├── goal_generator.md     # LLM prompt for generating goals
│   ├── failure_analyzer.md   # LLM prompt for analyzing failures
│   └── command_translator.md # LLM prompt for goal→command translation
│
├── patterns/
│   └── mindcraft-common-issues.json  # Domain patterns
│
├── config/
│   └── default_config.json   # Default configuration
│
└── tests/
    ├── test_client.py
    ├── test_planner.py
    ├── test_monitor.py
    └── test_integration.py
```

**Helper Scripts:**
- `scripts/install_mindcraft.py`: Link tools to `~/.context-foundry/tools/`
- `scripts/bootstrap_mindcraft_patterns.py`: Load patterns into global codex

---

## Testing Strategy

### Unit Tests
- Socket.io client mocking (**Dry Run Mode**)
- Goal queue operations
- State persistence

### Integration Tests
- Connect to real Mindcraft server
- Send commands, verify execution
- State update subscription

### End-to-End Tests
- 1-hour autonomous operation
- Goal generation → execution → completion
- Error recovery scenarios

### Manual Validation Checklist
```markdown
## Phase 1 Validation
- [ ] Can connect to andy.minepad.cc from local machine
- [ ] Receive agent status updates
- [ ] Send chat message, see it in Minecraft
- [ ] Restart agent via MCP tool

## Phase 2 Validation
- [ ] State persists across script restart
- [ ] Agent death detected and logged
- [ ] Position tracking accurate

## Phase 3 Validation
- [ ] Goal "gather 32 cobblestone" executes correctly
- [ ] Goal marked complete when inventory has 32+ cobblestone
- [ ] Failed goal triggers retry

## Phase 4 Validation
- [ ] Runs 24 hours without intervention
- [ ] Handles night/day cycle
- [ ] Auto-recovers from agent death

## Phase 5 Validation
- [ ] Pattern saved after agent death
- [ ] Pattern influences future planning
```

---

## Dependencies

### Python Packages
```
python-socketio[client]>=5.10.0   # Socket.io client
aiohttp>=3.9.0                    # Async HTTP
pydantic>=2.0.0                   # Data validation
```

### Context Foundry Integration
- Pattern management (`read_global_patterns`, `save_global_patterns`)
- Delegation system (for LLM planning calls)
- MCP server registration

---

## Decisions Made (User Input - 2025-12-28)

### 1. Agent Names
- **Primary Agent:** Andy
- **Future Agents:** Big Lebowski themed (The Dude, Walter, Donny, Maude, Bunny, Jesus, etc.)
- **Start with:** Andy only, expand later as needed

### 2. Primary Directive: BE HELPFUL TO HUMANS
**This is the core mission.** Agents should:
- Help human players with their objectives when they join
- Assist with whatever humans are doing (farming, building, mining)
- Gather resources (wood, stone, iron, diamonds) - **Priority A**
- Build structures (farms, houses, storage) - **Priority B**
- **NOT** exploration/mapping - low priority

### 3. CRITICAL: Avoid Water
```
⚠️ WATER IS THE ENEMY ⚠️
Bots get stuck in water. Avoid it at all costs.
This must be a core pattern in all planning/execution.
```

### 4. Discord Notifications
- Use existing Context Foundry Discord webhook pattern
- User will create dedicated channel in Context Foundry Discord server
- Notify on: agent death, stuck detection, goal completion, human join events

### 5. LLM Usage: RIDE THE SUBSCRIPTION
```
🚫 NEVER use Claude API directly
✅ ALWAYS use `claude` CLI to ride the subscription
```

This means:
- All LLM planning must go through `claude` CLI
- Use Context Foundry's `delegate_to_claude_code` for planning tasks
- The orchestrator can run on VPS where Mindcraft is already configured for Claude Code

### 6. Multi-Agent Strategy
- **Phase 1:** Andy only
- **Future:** Add Big Lebowski agents as needed

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      minepad.cc VPS                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Docker Container: Mindcraft                                 │   │
│  │  ├── MindServer (Socket.io)                                 │   │
│  │  ├── Andy Agent                                              │   │
│  │  └── (Future: Dude, Walter, Donny agents)                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ▲                                      │
│                              │ localhost Socket.io                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Context Foundry Orchestrator                                │   │
│  │  ├── Mindcraft Extension (cloned from repo)                 │   │
│  │  ├── Goal Planner (uses `claude` CLI)                       │   │
│  │  └── State Monitor                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              │ `claude` CLI (rides subscription)    │
│                              ▼                                      │
│                    Anthropic (via subscription)                     │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ Discord Webhook
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                Context Foundry Discord Server                       │
│                #mindcraft-notifications channel                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Insight:** The orchestrator runs ON the VPS alongside Mindcraft, using `claude` CLI for planning. This avoids API costs and keeps everything co-located.

---

## Implementation Progress Log

### 2025-12-28: Initial Planning
- [x] Created implementation plan
- [x] Architecture reviewed by another agent
- [x] User provided configuration decisions
- [x] Phase 1: Foundation - COMPLETE

### 2025-12-28: Phase 1 Complete
**Deliverables Created:**
- [x] `extensions/mindcraft/__init__.py` - Extension entry point
- [x] `extensions/mindcraft/detector.py` - Configuration detection
- [x] `extensions/mindcraft/extensions_loader.py` - Safe loading interface
- [x] `extensions/mindcraft/client.py` - Socket.io client with Dry Run
- [x] `extensions/mindcraft/tools/mindcraft_agent.py` - Agent control tool
- [x] `extensions/mindcraft/tools/mindcraft_status.py` - Status check tool
- [x] `extensions/mindcraft/tools/mindcraft_config.py` - Config management tool
- [x] `scripts/install_mindcraft.py` - Installer script
- [x] `extensions/mindcraft/CLAUDE.md` - Agent documentation
- [x] `extensions/mindcraft/patterns/mindcraft-common-issues.json` - Initial patterns

**Tests Passed:**
```bash
# Detector self-test
python3 extensions/mindcraft/detector.py
# Output: Available: True

# Client dry-run test
python3 extensions/mindcraft/client.py
# Output: Connected, sent message, disconnected

# Status tool dry-run
python3 extensions/mindcraft/tools/mindcraft_status.py --dry-run
# Output: {"success": true, "agents": {"andy": {...}}}

# Agent tool dry-run
python3 extensions/mindcraft/tools/mindcraft_agent.py --dry-run --agent andy --command "Test"
# Output: {"success": true, "command": "Test"}
```

**Next:** VPS deployment and live server testing

---

## Next Steps

1. ~~User Approval~~ ✅ APPROVED
2. ~~Answer Open Questions~~ ✅ ANSWERED
3. **Phase 1 Start:** Create extension structure, implement basic client
4. **VPS Setup:** Clone Context Foundry repo to minepad.cc
5. **Iterative Testing:** Each phase includes validation before proceeding

---

## References

- [Mindcraft GitHub](https://github.com/kolbytn/mindcraft)
- [Mindcraft-CE (Community Edition)](https://github.com/mindcraft-ce/mindcraft-ce)
- [Socket.io Python Client](https://python-socketio.readthedocs.io/)
- [Mineflayer](https://github.com/PrismarineJS/mineflayer) (underlying Minecraft bot library)
- [Context Foundry Extensions](../extensions/)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-28
**Validation:** Other agents can verify this plan by reading this file and checking:
1. Extension directory exists at `extensions/mindcraft/`
2. Components match the described structure
3. Tests pass for each phase

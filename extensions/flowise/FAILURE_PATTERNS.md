# Flowise Extension - Failure Patterns

**Version**: 1.0
**Last Updated**: 2025-11-01
**Purpose**: Document common failure patterns and how to prevent them

---

## Table of Contents

1. [Meta-Description Instead of Complete Flow](#meta-description-instead-of-complete-flow)
2. [Missing Agent Nodes](#missing-agent-nodes)
3. [Separate Config Files Anti-Pattern](#separate-config-files-anti-pattern)
4. [Disconnected Agent Nodes](#disconnected-agent-nodes)
5. [Prevention Checklist](#prevention-checklist)

---

## Meta-Description Instead of Complete Flow

### Symptom

Generated Flowise JSON is only 144 lines instead of expected 1000+ lines for a multi-agent system. The file contains:
- Only 3 nodes (router LLM, router prompt, intent router)
- Node type `"customNode"` instead of `"agentFlow"`
- References to external config files instead of inline agent definitions
- A metadata object describing what SHOULD be in the file rather than actual implementation

**Example Failed Output**:
```json
{
  "nodes": [
    {"id": "router_intent_0", "type": "customNode", ...},
    {"id": "llm_router", "type": "customNode", ...},
    {"id": "prompt_router", "type": "customNode", ...}
  ],
  "agentConfigurations": {
    "note": "Full agent node definitions available in src/agents/*.json files",
    "agentFiles": [
      "src/agents/sales-agent-config.json",
      "src/agents/marketing-agent-config.json",
      ...
    ]
  }
}
```

### Root Cause

**Extension not activated for NEW projects**

The Flowise extension detector (`detector.py`) only scanned for existing JSON files with `nodes` and `edges` arrays. When creating a NEW project:
1. No existing files exist to scan
2. Detector returns `is_flowise=False`
3. Flowise extension patterns never load
4. Builder uses generic JSON generation instead of following AGENT_PATTERN_REFERENCE.md
5. Result: Invalid meta-description file instead of complete Flowise JSON

### Impact

- **Severity**: CRITICAL - Generated file completely unusable
- **Frequency**: 100% for new Flowise projects before fix
- **User Experience**: Confusing - appears successful but file doesn't import to Flowise

### Fix Applied

**Added task description detection** (2025-11-01)

1. Created `detect_flowise_intent_from_task()` in `detector.py`
   - Detects keywords: "Flowise", "agentflow", "multi-agent flow", etc.
   - Estimates agent count from task description
   - Returns proper detection structure for new projects

2. Created `detect_flowise_project()` hybrid function
   - Checks task description FIRST (for new projects)
   - Falls back to file scanning (for existing projects)
   - Ensures extension activates in both scenarios

3. Updated `extensions_loader.py`
   - Added `detect_extensions_from_task()` function
   - Added `get_extension_detection_result()` for comprehensive detection

4. Updated orchestrator integration
   - Task description now checked before file scanning
   - Flowise patterns load when keywords detected in task
   - Builder receives explicit instructions for inline node generation

### Prevention

**Before starting a Flowise build, verify**:
- [ ] Task description contains "Flowise" or similar keywords
- [ ] Extension detector returns `is_flowise=True` from task analysis
- [ ] AGENT_PATTERN_REFERENCE.md is loaded
- [ ] warehouse-operations-flow.json referenced as canonical example

**Builder phase validation** (must check before finishing):
- [ ] Generated JSON > 800 lines (for 10+ agent systems)
- [ ] Has 1 `startAgentflow_0` node
- [ ] Has 1 `conditionAgentAgentflow_0` node
- [ ] Has N `agentAgentflow_N` nodes (one per agent)
- [ ] All nodes have `type: "agentFlow"`, NOT `"customNode"`
- [ ] No external file references in main JSON
- [ ] All agent definitions inline in nodes array

---

## Missing Agent Nodes

### Symptom

Flowise JSON has the start node and condition node, but missing most or all agent nodes.

### Root Cause

Builder didn't follow the complete node generation pattern from AGENT_PATTERN_REFERENCE.md.

### Fix

Ensure Builder explicitly generates:
1. One `startAgentflow_0` node
2. One `conditionAgentAgentflow_0` node with N scenario outputs
3. N `agentAgentflow_[1...N]` nodes for each specialized agent
4. Complete edge connections from condition outputs to agent inputs

### Prevention

Reference warehouse-operations-flow.json structure showing complete node topology.

---

## Separate Config Files Anti-Pattern

### Symptom

Generated JSON references external files like `src/agents/sales-agent-config.json` instead of having all agents inline.

### Root Cause

Builder misinterpreted the requirement as "modular architecture" and split agents into separate files.

### Fix

**EXPLICIT REQUIREMENT**: ALL agent nodes MUST be inline in the main Flowise JSON file.

Flowise imports a single JSON file with ALL nodes defined in the `nodes` array. It does NOT support:
- ❌ External agent config files
- ❌ Split node definitions
- ❌ Module imports
- ❌ File references

**CORRECT Pattern** (warehouse-operations-flow.json):
```json
{
  "nodes": [
    {
      "id": "startAgentflow_0",
      "type": "agentFlow",
      ...
    },
    {
      "id": "conditionAgentAgentflow_0",
      "type": "agentFlow",
      ...
    },
    {
      "id": "agentAgentflow_1",
      "type": "agentFlow",
      "data": {
        "label": "Agent.Sales",
        "name": "agentAgentflow",
        "inputs": {
          "agentMessages": [...],
          "agentModelConfig": {...},
          ...
        }
      }
    },
    {
      "id": "agentAgentflow_2",
      "type": "agentFlow",
      ...
    }
    // ... ALL agents inline
  ],
  "edges": [...]
}
```

### Prevention

Builder instructions MUST include:
- "Generate ONE complete JSON file with ALL nodes inline"
- "DO NOT create separate agent config files"
- "Follow warehouse-operations-flow.json structure EXACTLY"
- "Expected output: 1000+ lines for 10+ agent systems"

---

## Disconnected Agent Nodes

### Symptom

Flowise JSON imports successfully and shows all agent nodes on the canvas, but some agents have validation error "This node is not connected to anything". Flow appears complete but certain agents cannot be triggered.

**Example** (Cloud Services Operations Center - 2025-11-01):
- 10 nodes total: 1 start + 1 router + 8 agents ✓
- Imported successfully ✓
- 2 agents disconnected:
  - Agent.Incident.Response - not connected
  - Agent.Billing.Analytics - not connected

### Root Cause

**Mismatch between condition router scenarios and agent count**

The condition router (conditionAgentAgentflow) creates output anchors based on the number of scenarios:
- 5 scenarios → 5 output anchors → can connect to 5 agents
- But workflow has 8 agents → 3 agents have no input connection

**Why this happens**:
1. Task specifies N specialized agents (e.g., 8 agents)
2. Task also specifies M trigger conditions/scenarios (e.g., 5 scenarios)
3. Builder generates M outputs on condition router (one per scenario)
4. Builder generates N agent nodes (one per agent)
5. Only first M agents get connected, remaining (N-M) agents are orphaned

**Example Architecture Error**:
```
5 Scenarios in Router:
- "Provision New Service" → Infrastructure Agent ✓
- "Cost Anomaly" → Cost Optimization Agent ✓
- "Security Alert" → Security & Compliance Agent ✓
- "Performance Issue" → Performance Monitoring Agent ✓
- "Customer Support" → Customer Support Agent ✓

Remaining Disconnected Agents:
- Incident Response Agent ❌ (no scenario routes to it)
- Billing & Usage Analytics Agent ❌ (no scenario routes to it)
```

### Impact

- **Severity**: MEDIUM - Flow imports but some agents unreachable
- **Frequency**: Occurs when agent count > scenario count
- **User Experience**: Confusing - agents visible but can't be triggered
- **Functional Impact**: Missing capabilities (e.g., incident response unavailable)

### Fix

**Option 1: Scenario Count = Agent Count** (Recommended)

Every agent MUST have a corresponding scenario in the condition router:

```json
{
  "conditionAgentScenarios": [
    {"scenario": "Provision New Service"},      // → Infrastructure Agent
    {"scenario": "Cost Anomaly"},               // → Cost Optimization Agent
    {"scenario": "Security Alert"},             // → Security Agent
    {"scenario": "Performance Issue"},          // → Performance Agent
    {"scenario": "Customer Support"},           // → Customer Support Agent
    {"scenario": "Incident Response"},          // → Incident Response Agent ✓
    {"scenario": "Billing Inquiry"},            // → Billing Analytics Agent ✓
    {"scenario": "Usage Analysis"}              // → Usage Analytics Agent ✓
  ]
}
```

**Option 2: Secondary Routers** (For Complex Flows)

Create sub-routers when agents serve multiple purposes:

```
Primary Router (5 scenarios) → 5 Primary Agents
  └→ One agent is itself a router with 3 scenarios → 3 Secondary Agents
```

**Option 3: Shared Scenarios**

Some scenarios can route to multiple agents (parallel execution):

```
"Security Alert" → [Security Agent, Incident Response Agent, Notification Agent]
```

### Prevention

**During Architect Phase**:
- [ ] Count specialized agents in task requirements
- [ ] Count trigger conditions/scenarios
- [ ] If agents > scenarios, add scenarios OR merge agents
- [ ] Create 1:1 mapping: scenario → agent
- [ ] Document routing logic explicitly

**During Builder Phase**:
- [ ] Generate scenario count = agent count
- [ ] Verify edge count = agent count (router → agents)
- [ ] Each agent must have incoming edge from router
- [ ] No orphaned nodes allowed

**Validation Rules** (Builder MUST check):
```python
node_count = len(start_nodes) + len(router_nodes) + len(agent_nodes)
# Expected: 1 start + 1 router + N agents = N+2 nodes

scenario_count = len(router.scenarios)
agent_count = len(agent_nodes)

if agent_count > scenario_count:
    raise ValidationError(
        f"Mismatch: {agent_count} agents but only {scenario_count} scenarios. "
        f"Add {agent_count - scenario_count} more scenarios to router."
    )

edge_count = len(edges)
# Expected: 1 edge (start → router) + N edges (router → agents) = N+1 edges

if edge_count != agent_count + 1:
    raise ValidationError(
        f"Missing connections: Expected {agent_count + 1} edges, found {edge_count}"
    )
```

### Correct Example

**Cloud Services Operations (Fixed)**:
```json
{
  "nodes": [
    {"id": "startAgentflow_0", "type": "agentFlow"},
    {
      "id": "conditionAgentAgentflow_1",
      "type": "agentFlow",
      "data": {
        "conditionAgentScenarios": [
          {"scenario": "Provision New Service"},
          {"scenario": "Cost Anomaly"},
          {"scenario": "Security Alert"},
          {"scenario": "Performance Issue"},
          {"scenario": "Incident Response"},      // ✓ Added
          {"scenario": "Customer Support"},
          {"scenario": "Billing Inquiry"},        // ✓ Added
          {"scenario": "Usage Analysis"}          // ✓ Added (if 8 agents total)
        ]
      }
    },
    {"id": "agentAgentflow_2", "label": "Infrastructure"},
    {"id": "agentAgentflow_3", "label": "Cost Optimization"},
    {"id": "agentAgentflow_4", "label": "Security"},
    {"id": "agentAgentflow_5", "label": "Performance"},
    {"id": "agentAgentflow_6", "label": "Incident Response"},   // ✓ Connected
    {"id": "agentAgentflow_7", "label": "Customer Support"},
    {"id": "agentAgentflow_8", "label": "Billing Analytics"},  // ✓ Connected
    {"id": "agentAgentflow_9", "label": "Usage Analytics"}
  ],
  "edges": [
    {"source": "startAgentflow_0", "target": "conditionAgentAgentflow_1"},
    {"source": "conditionAgentAgentflow_1", "target": "agentAgentflow_2", "sourceHandle": "...-output-0"},
    {"source": "conditionAgentAgentflow_1", "target": "agentAgentflow_3", "sourceHandle": "...-output-1"},
    // ... 8 edges total from router to agents
  ]
}
```

### Builder Guidance Update

Add to Builder instructions for Flowise flows:

```
EDGE VALIDATION REQUIREMENTS:

1. Count agents in task specification: N agents
2. Create N scenarios in condition router
3. Generate N output anchors on router (one per scenario)
4. Generate N+1 edges:
   - 1 edge: start → router
   - N edges: router output[i] → agent[i]
5. Validate: Every agent has exactly 1 incoming edge
6. Validate: No "disconnected" nodes

Formula Check:
  total_nodes = 1 (start) + 1 (router) + N (agents) = N + 2
  total_edges = N + 1
  router_outputs = N (must equal agent count)
```

---

## Prevention Checklist

### Before Build Starts

- [ ] Task description contains "Flowise" keyword
- [ ] Detector returns `is_flowise=True`
- [ ] AGENT_PATTERN_REFERENCE.md loaded
- [ ] warehouse-operations-flow.json set as canonical reference
- [ ] Builder knows agent count and complexity

### During Build (Scout Phase)

- [ ] Scout identifies this as Flowise multi-agent project
- [ ] Scout counts required agents
- [ ] Scout notes complexity level
- [ ] Scout references canonical examples

### During Build (Architect Phase)

- [ ] Architecture specifies inline node structure
- [ ] Edge connections planned (condition outputs → agent inputs)
- [ ] No mention of external config files

### During Build (Builder Phase)

- [ ] Builder generates nodes array with ALL agents
- [ ] Each agent is complete agentAgentflow node
- [ ] All use type: "agentFlow"
- [ ] Model configs inline in agentModelConfig
- [ ] Memory configs inline in agentEnableMemory/agentMemoryType

### Before Build Completes (Test Phase)

- [ ] JSON file size > 800 lines (for 10+ agents)
- [ ] Node count matches: 1 start + 1 condition + N agents
- [ ] No `"customNode"` types
- [ ] No external file references
- [ ] Structure matches warehouse-operations-flow.json

### After Build (Validation)

- [ ] Import to Flowise succeeds
- [ ] All agents visible on canvas
- [ ] Routing connections present
- [ ] Test with sample queries works

---

## Example Negative Pattern

**File**: `patterns/failures/enterprise-ops-center-meta-description.json`

This file shows the INCORRECT meta-description output that was generated before the fix was applied. Use it as a reference for what NOT to generate.

---

## Lessons Learned

1. **Extension activation is critical** - Without it, Builder has no guidance
2. **Task description must be checked** - File scanning alone insufficient for new projects
3. **Explicit size requirements needed** - "Complete flow" is ambiguous, "1000+ lines" is concrete
4. **Inline nodes are mandatory** - Flowise doesn't support external file references
5. **Validation before completion** - Catch failures before they're deployed

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-11-01 | Added "Disconnected Agent Nodes" pattern from Cloud Services Operations build |
| 1.0 | 2025-11-01 | Initial documentation of meta-description failure pattern |

---

**Remember**: When in doubt, compare to warehouse-operations-flow.json (1,164 lines, 9 agents, all inline).

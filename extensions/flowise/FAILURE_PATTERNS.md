# Flowise Extension - Failure Patterns

**Version**: 2.0
**Last Updated**: 2025-11-05
**Purpose**: Document common failure patterns and how to prevent them

---

## Table of Contents

1. [Meta-Description Instead of Complete Flow](#meta-description-instead-of-complete-flow)
2. [Missing Agent Nodes](#missing-agent-nodes)
3. [Separate Config Files Anti-Pattern](#separate-config-files-anti-pattern)
4. [Disconnected Agent Nodes](#disconnected-agent-nodes)
5. [Phantom Tool and Knowledge References](#phantom-tool-and-knowledge-references)
6. [Incorrect Tool JSON Structure (Pattern #6)](#incorrect-tool-json-structure-pattern-6)
7. [ConditionAgent Incomplete Scenarios (Pattern #7)](#conditionagent-incomplete-scenarios-pattern-7)
8. [Agent Nodes Missing inputParams (Pattern #8)](#agent-nodes-missing-inputparams-pattern-8)
9. [Missing Mermaid Diagram (Pattern #9)](#missing-mermaid-diagram-pattern-9)
10. [HIL Gate Invalid inputParams Configuration (Pattern #10)](#hil-gate-invalid-inputparams-configuration-pattern-10)
11. [HIL Node Missing Required inputParams Fields (Pattern #11)](#hil-node-missing-required-inputparams-fields-pattern-11)
12. [Modular Prompt Refactor Breaking Tool Inclusion (Pattern #12)](#modular-prompt-refactor-breaking-tool-inclusion-pattern-12)
13. [ConditionAgent Variable Format (Pattern #13)](#conditionagent-variable-format-pattern-13)
14. [Node Type Mismatch (Pattern #14)](#node-type-mismatch-pattern-14)
15. [Missing Start Node (Pattern #15)](#missing-start-node-pattern-15)
16. [Prevention Checklist](#prevention-checklist)

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

### Variant: Parallel Build Splitting (Added 2025-11-01)

**Symptom**:
Instead of one workflow JSON file, Builder creates multiple split files:
```
❌ flowise-workflow-nodes-0-1.json  (12K)
❌ flowise-workflow-nodes-2-4.json  (49K)
❌ flowise-workflow-nodes-5-7.json  (46K)
```

**Root Cause**:
Parallel build system (Phase 2.5) attempted to parallelize Flowise JSON generation by splitting node creation across multiple builder tasks. Each parallel task generated its assigned nodes, resulting in multiple JSON files instead of one complete workflow.

**Why This Happens**:
1. Builder planning phase identifies "large number of nodes" (e.g., 8 agents = 10 total nodes)
2. Planner creates parallel tasks to speed up build: "Create nodes 0-1", "Create nodes 2-4", etc.
3. Each parallel builder writes its own JSON file
4. Result: 3 separate JSON files instead of 1 complete workflow

**Example** (Gig Marketplace - 2025-11-01, Build ID: 06cc114d):
- Task: Build Flowise gig marketplace with 7 specialized agents
- Expected: `gig-marketplace-flow.json` (1 file, ~3500 lines)
- Actual: 3 split files created by parallel builders
- Impact: Cannot import into Flowise (expects 1 file)

**Fix**:
Orchestrator MUST prevent parallel splitting for Flowise JSON generation:

```json
// WRONG: Parallel mode for Flowise workflow JSON
{
  "parallel_mode": true,
  "tasks": [
    {"id": "nodes-0-1", "files": ["flowise-workflow-nodes-0-1.json"]},
    {"id": "nodes-2-4", "files": ["flowise-workflow-nodes-2-4.json"]},
    {"id": "nodes-5-7", "files": ["flowise-workflow-nodes-5-7.json"]}
  ]
}

// CORRECT: Single task for Flowise workflow JSON
{
  "parallel_mode": false,  // ← CRITICAL
  "tasks": [
    {
      "id": "flowise-flow",
      "description": "Create complete Flowise workflow in single JSON file",
      "files": ["gig-marketplace-flow.json"]
    }
  ]
}
```

**Additional Prevention**:
- Orchestrator MUST check for Flowise project detection (flowise_flow: True)
- When detected, MUST set `parallel_mode: false` for main workflow JSON
- Documentation files (README, guides) CAN still be parallel
- Tool/knowledge configs CAN still be parallel
- ONLY main workflow JSON must be single-task

**Validation Rules**:
```bash
# Pre-deployment check for Flowise projects
if [[ -f ".context-foundry/scout-report.md" ]] && grep -q "Flowise" .context-foundry/scout-report.md; then
  json_file_count=$(find . -maxdepth 1 -name "*flow*.json" -o -name "*workflow*.json" | wc -l)

  if [[ $json_file_count -ne 1 ]]; then
    echo "❌ ERROR: Flowise projects must have EXACTLY 1 workflow JSON file"
    echo "Found: $json_file_count files"
    exit 1
  fi
fi
```

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

## Agent Nodes Missing inputParams (Pattern #8)

### Symptom

**User Report** (2025-11-02):
> "When I double click on an agent in the ecommerce-support-flow.json, nothing happens. Agent.OrderTracking, Agent.Returns, Agent.Payment, etc. - nothing happens when I double click on them. I'm afraid the code is broken somewhere."

**Behavior in Flowise UI**:
- ✅ Workflow imports successfully
- ✅ All nodes appear on canvas with correct positions
- ✅ All edges/connections render correctly
- ❌ Double-clicking any agent node does NOTHING (no edit dialog)
- ❌ Cannot modify agent settings (model, messages, tools, memory)
- ❌ Workflow appears complete but agents are completely uneditable

**Severity**: CRITICAL - Workflow unusable without ability to edit agents

### Root Cause

**Agent nodes missing `inputParams` array**

The generated agent nodes have this structure:
```json
{
  "data": {
    "id": "agentAgentflow_1",
    "label": "Agent.OrderTracking",
    "name": "agentAgentflow",
    "type": "Agent",
    "inputs": {
      "agentModel": "chatOpenAI",
      "agentMessages": [...],
      "agentTools": [...]
    }
  }
}
```

But they're **missing the critical `inputParams` array**:
```json
{
  "data": {
    "inputParams": [  // ← MISSING!
      {
        "label": "Model",
        "name": "agentModel",
        "type": "asyncOptions",
        ...
      },
      // ... 14 more parameter definitions
    ],
    "inputs": { /* actual values */ }
  }
}
```

### What is inputParams?

**`inputParams` is the UI SCHEMA** - it tells Flowise:
- What fields to display when editing the node
- What type each field is (text, dropdown, array, etc.)
- What options are available (for dropdowns)
- Whether fields are optional or required
- How to render each field (with proper UI controls)

**`inputs` is the DATA** - the actual values for those fields

**Without inputParams**, Flowise UI has no schema to render the edit form, so double-clicking does nothing.

### Comparison: Template vs Generated

**AGENT-NODE-TEMPLATE.json (CORRECT)**:
```json
{
  "data": {
    "inputParams": [
      {
        "label": "Model",
        "name": "agentModel",
        "type": "asyncOptions",
        "loadMethod": "listModels",
        "id": "agentAgentflow_0-input-agentModel-asyncOptions"
      },
      {
        "label": "Messages",
        "name": "agentMessages",
        "type": "array",
        "array": [...]
      }
      // ... 13 more inputParam objects (15 total)
    ],
    "inputs": {
      "agentModel": "chatOpenAI",
      "agentMessages": [{"role": "system", "content": "..."}]
    }
  }
}
```

**ecommerce-support-flow.json Agent Nodes (WRONG)**:
```json
{
  "data": {
    // ❌ inputParams array completely missing!
    "inputs": {
      "agentModel": "chatOpenAI",
      "agentMessages": [{"role": "system", "content": "..."}]
    }
  }
}
```

### Impact

**User Experience**:
- Workflow imports without errors (misleading - appears successful)
- All nodes visible on canvas
- Cannot edit ANY agent settings via UI
- Must manually add ~300 lines of inputParams JSON per agent (8 agents = 2400+ lines!)
- **Production blocker** - workflow cannot be customized or debugged

**Why This is Worse Than Other Patterns**:
- Pattern #7 (incomplete scenarios) - at least you CAN open the node, just fields are blank
- Pattern #8 (missing inputParams) - you CAN'T EVEN OPEN the node

### Detection

**In Flowise UI** (fastest):
1. Import the workflow JSON
2. Double-click any agent node
3. If NOTHING happens (no edit dialog) → inputParams is missing

**In JSON file**:
```bash
# Search for inputParams in agent nodes
cat workflow.json | jq '.nodes[] | select(.data.type == "Agent") | has("data") and (.data | has("inputParams"))'

# Should return: true for each agent
# If returns: false or null → PATTERN VIOLATED
```

**Quick check**:
```bash
grep -c "\"inputParams\"" workflow.json
# Should be >= number of agent nodes
# If 0 → CRITICAL BUG
```

### Fix Required

**MUST copy the complete inputParams array** from AGENT-NODE-TEMPLATE.json to every generated agent node.

**Required inputParams (15 total)**:
1. `agentModel` - Model selection
2. `agentMessages` - System/user messages array
3. `agentTools` - Tools selection array
4. `agentToolsBuiltInOpenAI` - OpenAI built-in tools
5. `agentToolsBuiltInAnthropic` - Anthropic built-in tools
6. `agentToolsBuiltInGemini` - Gemini built-in tools
7. `agentKnowledgeDocumentStores` - Document stores
8. `agentKnowledgeVSEmbeddings` - Vector embeddings
9. `agentEnableMemory` - Memory toggle
10. `agentMemoryType` - Memory type selection
11. `agentMemoryWindowSize` - Window size
12. `agentMemoryMaxTokenLimit` - Token limit
13. `agentReturnResponseAs` - Response type
14. `agentUpdateState` - State updates
15. Model configuration object

### Prevention

**Before generating agent nodes**:
- [ ] Reference AGENT-NODE-TEMPLATE.json for complete structure
- [ ] Copy the ENTIRE inputParams array (15 objects, ~200 lines)
- [ ] Do NOT just copy inputs - MUST include inputParams
- [ ] Verify inputParams array exists in template (line 17+)

**During Builder phase**:
- [ ] For EVERY agent node, include both inputParams AND inputs
- [ ] inputParams defines the SCHEMA (what fields exist)
- [ ] inputs contains the DATA (values for those fields)
- [ ] Both are required - inputParams is NOT optional

**Post-generation validation**:
```bash
# Count inputParams arrays (should match agent count)
agent_count=$(cat workflow.json | jq '[.nodes[] | select(.data.type == "Agent")] | length')
inputparams_count=$(grep -c '"inputParams"' workflow.json)

if [ "$inputparams_count" -lt "$agent_count" ]; then
  echo "❌ CRITICAL: Some agent nodes missing inputParams"
  echo "Expected: $agent_count, Found: $inputparams_count"
fi
```

### Template Reference

**Source**: `extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json`

**Lines**: 17-210 (inputParams array definition)

**Size**: ~200 lines for 15 inputParam objects

**Critical Note**: This array is NOT optional. It is as essential as the `inputs` object.

### Relationship to Other Patterns

**Similar but different**:
- **Pattern #4** (condition-agent-no-scenarios): Missing scenarios array → can't route
- **Pattern #7** (condition-agent-incomplete-scenarios): Scenarios exist but incomplete → can edit but fields blank
- **Pattern #8** (agent-missing-inputparams): No schema at all → can't even open node

**Root cause similarity**:
All three involve missing or incomplete array structures that define UI schemas.

### Added to Global Pattern Library

This pattern has been added to:
- `/Users/name/.context-foundry/patterns/common-issues.json`
- Pattern ID: `agent-missing-inputparams`
- Severity: CRITICAL
- First seen: 2025-11-02 (ecommerce-support-workflow build)
- Total patterns: 10 (was 9)

### Quick Fix for Existing Workflows

If you have a broken workflow with missing inputParams:

1. Open AGENT-NODE-TEMPLATE.json
2. Copy lines 17-210 (the complete inputParams array)
3. For each agent node in your workflow JSON:
   - Add `"inputParams": [...]` before the `"inputs": {...}` line
   - Paste the copied inputParams array
   - Update the `id` fields to match your agent node ID
4. Save and re-import to Flowise

**Note**: This is manual work. Better to prevent the issue by ensuring Context Foundry generates it correctly.

---

## Missing Mermaid Diagram (Pattern #9)

### Symptom

**User Report** (2025-11-02):
> "The mermaid .md file did not populate in the readme of this flow/repository: personalized-training-flow. The idea is not to update this one, as much as the importance of ensuring that no matter what, the next flow, absolutely creates a mermaid flow .md file"

Generated Flowise workflow repository is missing:
- ❌ No `WORKFLOW-DIAGRAM.md` file in repository root
- ❌ No mermaid diagram embedded in README.md
- ❌ Workflow structure not visualized
- ❌ Agent connections not documented visually

**Severity**: HIGH - Workflow lacks critical visual documentation
**Impact**: Users cannot quickly understand workflow structure, agent relationships, or routing logic

### Root Cause

**Documentation phase skipped or mermaid_generator.py not executed**

The orchestrator has explicit instructions (lines 1437-1540) that state:
> "THIS IS A BLOCKING REQUIREMENT - Flowise projects without embedded diagrams are considered INCOMPLETE and MUST NOT be deployed."

But the build completed without:
1. Running the mermaid_generator.py script
2. Creating WORKFLOW-DIAGRAM.md file
3. Embedding diagram in README.md
4. Running diagram validation checks

**Why This Happens**:
- Documentation phase may have been skipped during deployment
- Mermaid generator script may have failed silently
- Validation checks (lines 1506-1519) were not executed
- Builder completed without creating diagram files

### Impact

**User Experience**:
- Cannot visualize workflow structure at a glance
- Must manually read through JSON to understand agent connections
- No quick reference for routing logic
- Missing professional documentation polish

**Examples from Recent Builds**:
- **Personalized Training Recommendations** (task 489ac13f): No WORKFLOW-DIAGRAM.md created
- User had to manually understand the 13-node structure by reading JSON

### Fix Required

**MUST execute mermaid_generator.py and embed diagram in README.md**

According to orchestrator instructions (lines 1437-1546), Builder MUST:

1. **Generate standalone diagram file**:
```bash
python3 /Users/name/homelab/context-foundry/extensions/flowise/mermaid_generator.py \
  personalized-training-recommendations-flow.json \
  WORKFLOW-DIAGRAM.md \
  --badges --interactive --legend --include-details
```

2. **Embed complete diagram in README.md**:
- Extract full content from WORKFLOW-DIAGRAM.md
- Insert RIGHT AFTER hero/title section, BEFORE "## Overview"
- Include ALL content (badges, mermaid block, interactive details, legend)
- Add horizontal rule `---` separator after diagram

3. **Run validation checks**:
```bash
# Check 1: WORKFLOW-DIAGRAM.md exists
test -f WORKFLOW-DIAGRAM.md || exit 1

# Check 2: README contains mermaid block
grep -q '```mermaid' README.md || exit 1

# Check 3: README contains diagram badges
grep -q 'img.shields.io/badge' README.md || exit 1
```

### Prevention

**Before Documentation Phase**:
- [ ] Verify Flowise project detection is active
- [ ] Confirm mermaid_generator.py exists and is executable
- [ ] Ensure workflow JSON file is finalized and valid

**During Documentation Phase** (REQUIRED):
- [ ] Run mermaid_generator.py with all flags (--badges --interactive --legend --include-details)
- [ ] Generate WORKFLOW-DIAGRAM.md in repository root
- [ ] Extract complete diagram content
- [ ] Embed in README.md after title, before "## Overview"
- [ ] Add horizontal rule separator

**After Documentation Phase** (BLOCKING VALIDATION):
- [ ] WORKFLOW-DIAGRAM.md file exists in repo root
- [ ] README.md contains `\`\`\`mermaid` code block
- [ ] README.md contains diagram badges (img.shields.io)
- [ ] Mermaid syntax is valid (no rendering errors)
- [ ] All agents appear in diagram
- [ ] Routing connections are visible

### Required Files

**WORKFLOW-DIAGRAM.md** (Standalone):
```markdown
# Personalized Training Recommendations - Workflow Diagram

![Agents](https://img.shields.io/badge/Agents-6-blue)
![Nodes](https://img.shields.io/badge/Nodes-13-green)
![Complexity](https://img.shields.io/badge/Complexity-Advanced-orange)

\`\`\`mermaid
graph TD
    Start[Start: Form Input] --> Supervisor
    Supervisor[Supervisor: LLM Coordinator] --> Router{Route to Agent}

    Router -->|Skills Gap| Agent1[Skills Gap Analyzer]
    Router -->|Availability| Agent2[Availability Matcher]
    Router -->|Experience| Agent3[Experience Level Advisor]
    Router -->|Project| Agent4[Project Alignment]
    Router -->|Career| Agent5[Career Path Consultant]
    Router -->|Finish| Synthesizer[Recommendation Synthesizer]

    Agent1 --> Loop1[Loop Back]
    Agent2 --> Loop2[Loop Back]
    Agent3 --> Loop3[Loop Back]
    Agent4 --> Loop4[Loop Back]
    Agent5 --> Loop5[Loop Back]

    Loop1 --> Supervisor
    Loop2 --> Supervisor
    Loop3 --> Supervisor
    Loop4 --> Supervisor
    Loop5 --> Supervisor
\`\`\`

### Interactive Details
Click nodes to expand:
- **Start**: Form input collecting 6 profile dimensions
- **Supervisor**: Coordinates multi-agent consultation
- **Router**: Routes to appropriate specialist agent
- **Agents**: 5 specialist agents for comprehensive analysis
- **Synthesizer**: Combines insights into actionable plan
```

**README.md** (Embedded):
```markdown
# Personalized Training Recommendations

> Multi-agent system for personalized training analysis

---

## Workflow Architecture

![Agents](https://img.shields.io/badge/Agents-6-blue)
![Nodes](https://img.shields.io/badge/Nodes-13-green)
![Complexity](https://img.shields.io/badge/Complexity-Advanced-orange)

\`\`\`mermaid
graph TD
    Start[Start: Form Input] --> Supervisor
    ...
\`\`\`

### Interactive Details
...

---

## Overview

This workflow provides personalized training recommendations...
```

### Validation Script

**Add to orchestrator test phase** (after documentation):

```bash
#!/bin/bash
# Flowise Mermaid Diagram Validation (BLOCKING)

echo "🔍 Validating Mermaid diagram generation..."

# Check 1: WORKFLOW-DIAGRAM.md exists
if [ ! -f "WORKFLOW-DIAGRAM.md" ]; then
  echo "❌ BLOCKING FAILURE: WORKFLOW-DIAGRAM.md not found"
  echo "   This is a REQUIRED file for all Flowise workflows"
  echo "   Run: python3 mermaid_generator.py workflow.json WORKFLOW-DIAGRAM.md --badges --interactive"
  exit 1
fi
echo "✅ WORKFLOW-DIAGRAM.md exists"

# Check 2: README contains mermaid block
if ! grep -q '```mermaid' README.md; then
  echo "❌ BLOCKING FAILURE: Diagram not embedded in README"
  echo "   Mermaid block must be inserted after title, before '## Overview'"
  exit 1
fi
echo "✅ Mermaid block embedded in README"

# Check 3: README contains diagram badges
if ! grep -q 'img.shields.io/badge' README.md; then
  echo "❌ BLOCKING FAILURE: Missing diagram badges in README"
  echo "   Badges show agent count, node count, and complexity at a glance"
  exit 1
fi
echo "✅ Diagram badges present in README"

# Check 4: Diagram contains agent nodes
agent_count=$(grep -c "Agent\[" WORKFLOW-DIAGRAM.md || echo "0")
if [ "$agent_count" -lt 3 ]; then
  echo "❌ WARNING: Only $agent_count agents found in diagram"
  echo "   Expected 3+ for multi-agent workflow"
fi
echo "✅ Diagram contains $agent_count agent nodes"

echo "✅ All Mermaid diagram validations PASSED"
```

### Quick Fix for Existing Workflows

If you have a deployed workflow without mermaid diagram:

1. Navigate to workflow directory
2. Run mermaid generator:
```bash
cd /path/to/workflow
python3 /Users/name/homelab/context-foundry/extensions/flowise/mermaid_generator.py \
  workflow-flow.json \
  WORKFLOW-DIAGRAM.md \
  --badges --interactive --legend --include-details
```
3. Copy content from WORKFLOW-DIAGRAM.md
4. Open README.md
5. Paste diagram content after title, before "## Overview"
6. Commit and push

### Why This Matters

**Professional Documentation**:
- Visual diagrams are industry standard for workflow documentation
- GitHub renders mermaid natively - no external tools needed
- Users understand structure in seconds vs minutes

**Debugging & Maintenance**:
- Quick reference for troubleshooting routing issues
- Easy to identify disconnected nodes
- Clear view of agent relationships

**User Experience**:
- First impression of workflow quality
- Reduces time-to-understanding
- Enables faster onboarding

### Added to Global Pattern Library

This pattern has been added to:
- `/Users/name/.context-foundry/patterns/common-issues.json`
- Pattern ID: `flowise-missing-mermaid-diagram`
- Severity: HIGH
- First seen: 2025-11-02 (personalized-training-recommendations build)
- Total patterns: 11 (was 10)

---

## HIL Node Missing Required inputParams Fields (Pattern #11)

### Symptom

Human-in-the-Loop (HIL) approval node causes **blank screen** when clicked in Flowise UI.

**User Experience**:
- Workflow imports successfully ✓
- All nodes display correctly on canvas ✓
- Double-clicking HIL node → **blank screen/white screen** ❌
- No error messages in browser console
- Node configuration completely inaccessible
- Other nodes work fine

**Occurred in**: Travel Booking & Expense Flow (2025-11-05)

### Root Cause

**HIL node missing required `inputParams` fields that Flowise UI expects to exist in the schema.**

The generated HIL node only included **3 inputParams**:
1. `humanInputDescriptionType` ✓
2. `humanInputDescription` ✓
3. `humanInputEnableFeedback` ✓

But Flowise requires **5 inputParams** to be present:
1. `humanInputDescriptionType` ✓
2. `humanInputDescription` ✓
3. **`humanInputModel`** ❌ MISSING
4. **`humanInputModelPrompt`** ❌ MISSING
5. `humanInputEnableFeedback` ✓

**Why this breaks Flowise:**
- Even though `humanInputModel` and `humanInputModelPrompt` are conditionally hidden via `"show": {"humanInputDescriptionType": "dynamic"}`, **Flowise still requires them to exist in the schema**
- When the UI tries to render the node, it looks for these fields in `inputParams`
- If they don't exist, the rendering engine fails silently → blank screen
- No error is thrown because it's a schema validation issue, not a runtime error

**Additionally:**
- Missing `humanInputModelConfig` object in the `inputs` field
- Incorrect dimensions: `width: 300, height: 400` instead of `width: 221, height: 80`

### Impact

**Severity**: CRITICAL - HIL node completely unusable
**Frequency**: 100% when HIL node is missing required inputParams
**User Experience**: Confusing - workflow imports successfully but one node is broken
**Debugging Difficulty**: HIGH - No error messages, silent failure

**Why This Is Critical:**
- HIL gates are essential for approval workflows
- Without working HIL gates, workflows cannot pause for human input
- User cannot configure approval messages or routing
- Forces manual recreation of the entire node in Flowise UI

### Correct Structure

**HIL node MUST include all 5 inputParams** (from AGENT_PATTERN_REFERENCE.md):

```json
{
  "data": {
    "inputParams": [
      {
        "label": "Description Type",
        "name": "humanInputDescriptionType",
        "type": "options",
        "options": [
          {"label": "Fixed", "name": "fixed"},
          {"label": "Dynamic", "name": "dynamic"}
        ],
        "id": "humanInputAgentflow_0-input-humanInputDescriptionType-options",
        "display": true
      },
      {
        "label": "Description",
        "name": "humanInputDescription",
        "type": "string",
        "placeholder": "Are you sure you want to proceed?",
        "acceptVariable": true,
        "rows": 8,
        "show": {"humanInputDescriptionType": "fixed"},
        "id": "humanInputAgentflow_0-input-humanInputDescription-string",
        "display": true
      },
      {
        "label": "Model",
        "name": "humanInputModel",
        "type": "asyncOptions",
        "loadMethod": "listModels",
        "loadConfig": true,
        "show": {"humanInputDescriptionType": "dynamic"},
        "id": "humanInputAgentflow_0-input-humanInputModel-asyncOptions",
        "display": false
      },
      {
        "label": "Prompt",
        "name": "humanInputModelPrompt",
        "type": "string",
        "acceptVariable": true,
        "generateInstruction": true,
        "rows": 12,
        "show": {"humanInputDescriptionType": "dynamic"},
        "id": "humanInputAgentflow_0-input-humanInputModelPrompt-string",
        "display": false
      },
      {
        "label": "Enable Feedback",
        "name": "humanInputEnableFeedback",
        "type": "boolean",
        "default": true,
        "id": "humanInputAgentflow_0-input-humanInputEnableFeedback-boolean",
        "display": true
      }
    ],
    "inputs": {
      "humanInputDescriptionType": "fixed",
      "humanInputDescription": "Approval message here",
      "humanInputEnableFeedback": true,
      "humanInputModelConfig": {
        "credential": "OpenAI API Key",
        "modelName": "gpt-4o-mini",
        "temperature": 0.0,
        "streaming": true,
        "humanInputModel": "chatOpenAI"
      }
    }
  },
  "width": 221,
  "height": 80
}
```

**Key Points:**
- All 5 inputParams MUST be present in the array
- Fields 3-4 are hidden via `"show"` condition but still required
- `humanInputModelConfig` MUST be present in `inputs` even when using "fixed" description type
- Correct dimensions: 221 x 80 (not 300 x 400)

### Fix Applied

**Updated on**: 2025-11-05

1. **Fixed HIL-NODE-TEMPLATE.json** (`prompts/HIL-NODE-TEMPLATE.json`)
   - Added `humanInputModel` inputParam (asyncOptions)
   - Added `humanInputModelPrompt` inputParam (string)
   - Added `humanInputModelConfig` to inputs object
   - Verified dimensions are 221 x 80

2. **Fixed travel-booking-expense-flow.json**
   - Added missing inputParams to HIL node
   - Added humanInputModelConfig to inputs
   - Corrected dimensions from 300x400 to 221x80
   - Validated JSON structure

3. **Updated AGENT_PATTERN_REFERENCE.md**
   - Already had correct 5-parameter structure documented
   - Verified all examples include full schema

### Prevention

**CRITICAL RULES for HIL Nodes:**

1. **Always include ALL 5 inputParams** - even if conditionally hidden
   - humanInputDescriptionType
   - humanInputDescription
   - **humanInputModel** (required even if hidden)
   - **humanInputModelPrompt** (required even if hidden)
   - humanInputEnableFeedback

2. **Always include humanInputModelConfig in inputs** - even when using "fixed" description type

3. **Use correct dimensions**: width: 221, height: 80

4. **Validate against AGENT_PATTERN_REFERENCE.md** - Section 4: "Human-in-the-Loop (HIL) Node"

5. **Copy from working templates**:
   - Use `prompts/HIL-NODE-TEMPLATE.json` (now fixed)
   - Reference AGENT_PATTERN_REFERENCE.md for complete structure
   - Never simplify or optimize by removing "unused" fields

**Builder Phase Validation:**
```
HIL Node Checklist:
✓ inputParams has exactly 5 fields
✓ humanInputModel present (even if hidden)
✓ humanInputModelPrompt present (even if hidden)
✓ inputs.humanInputModelConfig exists
✓ width: 221, height: 80
✓ outputAnchors has "proceed" and "reject"
```

**Why Hidden Fields Are Required:**
- Flowise UI schema validation requires all fields to exist
- Conditional visibility (`show`) only affects UI display, not schema
- Missing hidden fields cause silent rendering failures
- Schema must be complete even if user never sees certain fields

### Lesson Learned

**Never assume hidden fields can be omitted.**

Just because a field is conditionally hidden via `"show"` does not mean it can be removed from the schema. Flowise expects the **complete schema** to be present at all times. The `show` condition only controls **visibility**, not **existence**.

**Template Simplification = Broken Nodes**

The original HIL-NODE-TEMPLATE.json was "simplified" to only include the fields commonly used (fixed description type). This optimization broke the node because Flowise still expected the full schema.

**Always copy complete, working structures** - never simplify based on assumptions about what's "needed".

---

## Modular Prompt Refactor Breaking Tool Inclusion (Pattern #12)

### Symptom

Generated Flowise agents are **missing standard tools** (currentDateTime, searXNG) that should be automatically included in every agent.

**User Experience**:
- Workflow imports successfully ✓
- All nodes display correctly on canvas ✓
- Double-clicking agent nodes works ✓
- BUT agents missing tools dropdown shows no tools selected ❌
- Model configuration missing "Connect Credential" ❌
- DateTime tool missing ❌
- SearXNG tool missing ❌

**Occurred in**: Travel Booking & Expense Flow (2025-11-05) - After modular prompt refactor on 2025-11-04

### Root Cause

**Modular prompt refactor changed how orchestrator instructions are loaded, but Builder phase didn't execute the tool inclusion instructions.**

**Timeline of Events:**
1. **2025-11-04**: Commit c009c06 "Merge feature/modular-prompt-refactor"
   - Split orchestrator_prompt.txt into modular files
   - orchestrator_header.txt, orchestrator_footer.txt, phase_*.md modules
   - Build process: `build_orchestrator_prompt.py` combines modules into final prompt

2. **Before refactor**: Tool inclusion instructions were in main orchestrator_prompt.txt
   - Builder read AGENT-NODE-TEMPLATE.json
   - Copied lines 341-367 (agentTools array)
   - All agents had currentDateTime + searXNG

3. **After refactor**: Instructions exist in `phase_2_5_parallel_build.md` (lines 82-99)
   - But Builder phase didn't execute the Read commands
   - Builder didn't copy the template structure
   - Agents generated WITHOUT agentTools array

**The Instructions ARE Present:**
```markdown
🚨🚨🚨 **MANDATORY BUILDER REQUIREMENT: Read Files BEFORE Generating Agents** 🚨🚨🚨

**BEFORE generating ANY agent node, Builder MUST execute these Read commands**:

1. **READ the AGENT-NODE-TEMPLATE.json** (get the correct structure):
   Read /Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json

2. **LOCATE lines 341-367** in the template (agentTools array structure)

3. **COPY the agentTools structure EXACTLY** into every agent node
```

But the Builder didn't follow them.

### Impact

**Severity**: CRITICAL - Agents completely non-functional for real-world use
**Frequency**: 100% after modular prompt refactor (2025-11-04+)
**User Experience**: Workflow appears complete but lacks essential functionality
**Debugging Difficulty**: MEDIUM - Tools are missing but no errors shown

**Why This Is Critical:**
- DateTime tool provides temporal context (essential for time-sensitive queries)
- SearXNG enables real-time web search (essential for current information)
- Without these tools, agents can't:
  - Determine if information is current or outdated
  - Search for fresh facts or verify information
  - Access real-time data (prices, news, availability)
- Model credential missing prevents agents from executing at all in Flowise

**Business Impact:**
- Travel booking agents can't search for current flight prices
- Expense tracking can't determine current dates
- Any time-sensitive or research-based workflow is broken

### What Was Missing

**1. agentTools Array** (completely absent):
```json
// ❌ WRONG (what was generated):
{
  "inputs": {
    "agentModel": "chatOpenAI",
    "agentMessages": [...],
    // NO agentTools field at all!
    "agentEnableMemory": true
  }
}

// ✅ CORRECT (what should be generated):
{
  "inputs": {
    "agentModel": "chatOpenAI",
    "agentMessages": [...],
    "agentTools": [
      {
        "agentSelectedTool": "currentDateTime",
        "agentSelectedToolRequiresHumanInput": "",
        "agentSelectedToolConfig": {
          "agentSelectedTool": "currentDateTime"
        }
      },
      {
        "agentSelectedTool": "searXNG",
        "agentSelectedToolRequiresHumanInput": "",
        "agentSelectedToolConfig": {
          "apiBase": "https://s.llam.ai",
          "toolName": "searxng-search",
          "toolDescription": "...",
          // ... full config
          "agentSelectedTool": "searXNG"
        }
      }
    ],
    "agentEnableMemory": true
  }
}
```

**2. Model Configuration** (credential field missing in some cases):
```json
// ❌ INCOMPLETE:
"agentModelConfig": {
  "modelName": "gpt-4o-mini",
  "temperature": 0.7,
  "streaming": true,
  "agentModel": "chatOpenAI"
  // Missing: "credential": "OpenAI API Key"
}

// ✅ COMPLETE:
"agentModelConfig": {
  "credential": "OpenAI API Key",  // ← REQUIRED
  "modelName": "gpt-4o-mini",
  "temperature": 0.7,
  "streaming": true,
  "agentModel": "chatOpenAI"
}
```

### Fix Applied

**Updated on**: 2025-11-05

1. **Identified the regression**:
   - Compared generated flow against template
   - Confirmed agentTools array completely missing
   - Traced to modular prompt refactor commit (c009c06)

2. **Regenerated with explicit instructions**:
   - Created task with CRITICAL FIX prefix
   - Explicitly instructed to READ AGENT-NODE-TEMPLATE.json
   - Explicitly instructed to COPY lines 341-367
   - Emphasized this was a regression from working functionality

3. **Validated the fix**:
   ```bash
   ✓ All 4 agents have 2 tools (currentDateTime + searXNG)
   ✓ All agents have credential: "OpenAI API Key"
   ✓ All agents have correct model configuration
   ✓ JSON structure valid (12 nodes, 9 edges)
   ```

4. **Restored functionality**:
   - Agent.TravelSearch: Has tools ✓
   - Agent.Recommendations: Has tools ✓
   - Agent.ExpenseTracker: Has tools ✓
   - Agent.GeneralHelp: Has tools ✓

### Prevention

**CRITICAL RULES for Tool Inclusion:**

1. **ALWAYS include agentTools in EVERY agent** - Never generate agents without it
   - currentDateTime (temporal context)
   - searXNG (web search)

2. **Template is the source of truth** - Copy EXACT structure from lines 341-367
   ```
   Read /Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json
   ```

3. **Validate after generation**:
   ```python
   agents = [n for n in flow['nodes'] if n['data'].get('type') == 'Agent']
   for agent in agents:
       tools = agent['data']['inputs'].get('agentTools', [])
       assert len(tools) >= 2, f"{agent['data']['label']} missing tools!"
   ```

4. **ALWAYS include credential field in agentModelConfig**:
   ```json
   "agentModelConfig": {
     "credential": "OpenAI API Key",  // ← MANDATORY
     // ... other config
   }
   ```

**Builder Phase Validation Checklist:**
```
✓ Read AGENT-NODE-TEMPLATE.json before generating agents
✓ Locate lines 341-367 (agentTools array)
✓ Copy agentTools structure EXACTLY into every agent
✓ Verify 2 tools present: currentDateTime + searXNG
✓ Verify agentModelConfig.credential exists
✓ Verify agentModel field matches modelConfig.agentModel
```

**Test Phase Validation:**
```python
# BEFORE running any other tests, validate tools:
for agent_node in [n for n in flow['nodes'] if n['data']['type'] == 'Agent']:
    tools = agent_node['data']['inputs'].get('agentTools', [])
    if len(tools) < 2:
        print(f"❌ ERROR: {agent_node['data']['label']} missing standard tools!")
        print(f"   Has {len(tools)} tools, needs 2 (currentDateTime + searXNG)")
        print(f"   Fix: Copy lines 341-367 from AGENT-NODE-TEMPLATE.json")
        exit(1)
```

### Lesson Learned

**Modular prompt refactors require validation that all instructions are still executed.**

When refactoring the orchestrator prompt into modules:
1. ✅ Instructions were successfully moved to modules
2. ❌ Builder didn't execute the instructions in practice
3. ❌ No validation caught the regression

**The Problem:**
- Instructions exist in `phase_2_5_parallel_build.md`
- But runtime execution didn't follow them
- Gap between "prompt contains instructions" and "agent executes instructions"

**The Solution:**
- Add validation in Test phase to catch missing tools
- Make tool inclusion BLOCKING (exit code 1 if missing)
- Test both "instructions exist" AND "agents follow them"

**Never assume instructions are being followed - validate the output.**

### Related Issues

- Similar to HIL missing inputParams (Pattern #11) - incomplete node structure
- Similar to incorrect tool structure (Pattern #6) - but this is completely absent, not just wrong
- Different from phantom tools (Pattern #5) - these are REAL required tools, not invented ones
- Caused by system-level changes (modular prompt refactor), not individual build errors

### First Occurrence

- **Build**: Travel Booking & Expense Flow (2025-11-05)
- **Detected By**: User manual testing in Flowise UI
- **Trigger**: Modular prompt refactor commit c009c06 (2025-11-04)
- **Fixed**: Explicit tool inclusion instructions in regeneration task
- **Documentation**: Added to FAILURE_PATTERNS.md as Pattern #12

### Recommended System Fix

**Short-term** (DONE):
- Use explicit instructions when delegating to claude-code
- Include validation scripts in task description
- Regenerate with CRITICAL FIX prefix to emphasize importance

**Long-term** (TODO):
- Add automated test in Test phase that validates tool inclusion
- Make test BLOCKING (exit code 1 if tools missing)
- Add to `tools/orchestrator_prompt.txt` validation section
- Consider adding tools directly to Flowise UI rather than JSON generation
- Review all modular prompt modules for instruction execution gaps

**Validation Code to Add to Test Phase:**
```python
# Add to tools/prompts/phase_4_test.md around line 150

print("\n🔍 VALIDATING STANDARD TOOL INCLUSION...")
agents = [n for n in flow['nodes'] if n['data'].get('type') == 'Agent']
failed = False

for agent in agents:
    label = agent['data']['label']
    tools = agent['data']['inputs'].get('agentTools', [])

    if not tools or len(tools) < 2:
        print(f"❌ CRITICAL: {label} missing standard tools!")
        print(f"   Expected: currentDateTime + searXNG")
        print(f"   Found: {len(tools)} tools")
        failed = True
        continue

    tool_names = [t.get('agentSelectedTool') for t in tools]
    if 'currentDateTime' not in tool_names:
        print(f"❌ CRITICAL: {label} missing currentDateTime tool!")
        failed = True
    if 'searXNG' not in tool_names:
        print(f"❌ CRITICAL: {label} missing searXNG tool!")
        failed = True

if failed:
    print("\n🚨 DEPLOYMENT BLOCKED: Standard tools missing from agents")
    print("   Fix: Read AGENT-NODE-TEMPLATE.json lines 341-367 and copy agentTools structure")
    exit(1)

print("✅ All agents have required standard tools")
```

---

## ConditionAgent Variable Format (Pattern #13)

### Symptom

ConditionAgent node executes but produces **no output** and **doesn't route** to any path. The node completes execution (shows elapsed time) but the workflow stops.

**User-visible symptoms:**
- Condition node shows successful execution (e.g., "1.52 seconds")
- No output appears in logs after "Output" header
- Message doesn't route to any connected agents
- Flow execution stops after condition node

**Log examination reveals:**
```
user
{"input": can I book a trip to india, "scenarios": [...], "instruction": ...}

Output
(empty)
```

The user input value is **not quoted** in the JSON - this is malformed JSON that the LLM cannot parse.

### Root Cause

The `conditionAgentInput` field is using **plain text format** instead of Flowise's **rich text HTML format** for variables.

**❌ INCORRECT (Plain Text Format):**
```json
{
  "inputs": {
    "conditionAgentInput": "{{ question }}"
  }
}
```

**✅ CORRECT (Rich Text HTML Format):**
```json
{
  "inputs": {
    "conditionAgentInput": "<p><span class=\"variable\" data-type=\"mention\" data-id=\"question\" data-label=\"question\">{{ question }}</span> </p>"
  }
}
```

**Why this happens:**

When you use Flowise's UI to add a variable:
1. UI creates rich text HTML markup with special `<span>` tags
2. These tags tell Flowise: "This is a variable that needs JSON escaping"
3. During execution, Flowise recognizes the markup and properly escapes the value

When you use plain text format:
1. Flowise sees it as literal text, not a variable
2. No JSON escaping is applied
3. Result: `{"input": can I book a trip, ...}` instead of `{"input": "can I book a trip", ...}`
4. LLM receives malformed JSON and cannot parse it
5. No output is produced, no routing occurs

### Impact

- **Severity**: CRITICAL - Condition node completely non-functional
- **User Experience**: Confusing - node appears to execute successfully but workflow stops
- **Detection**: Only visible in logs (malformed JSON) or by testing in Flowise
- **Frequency**: 100% if plain text format is used

### Fix Applied

**Updated travel-booking-expense-flow.json** (Line 168):

Before:
```json
"conditionAgentInput": "{{ question }}"
```

After:
```json
"conditionAgentInput": "<p><span class=\"variable\" data-type=\"mention\" data-id=\"question\" data-label=\"question\">{{ question }}</span> </p>"
```

**Updated AGENT_PATTERN_REFERENCE.md** (Line 167 + added comprehensive explanation section):
- Changed canonical example to use rich text format
- Added "CRITICAL: Variable Format in conditionAgentInput" section
- Documented symptoms, common variables, and proper format

### Prevention

**When creating ConditionAgent nodes:**

1. ✅ **ALWAYS** use rich text HTML format for `conditionAgentInput`
2. ✅ Include proper `<span class="variable" ...>` markup
3. ✅ Set `data-id` to the variable name (e.g., "question", "$form.query", "$flow.state.key")
4. ✅ Set `data-label` to match `data-id`
5. ✅ Include both `<p>` wrapper and `<span>` for variable

**Template for common variables:**

```json
// User input from chat
"conditionAgentInput": "<p><span class=\"variable\" data-type=\"mention\" data-id=\"question\" data-label=\"question\">{{ question }}</span> </p>"

// Form field
"conditionAgentInput": "<p><span class=\"variable\" data-type=\"mention\" data-id=\"$form.fieldName\" data-label=\"$form.fieldName\">{{ $form.fieldName }}</span> </p>"

// Flow state
"conditionAgentInput": "<p><span class=\"variable\" data-type=\"mention\" data-id=\"$flow.state.key\" data-label=\"$flow.state.key\">{{ $flow.state.key }}</span> </p>"
```

**Builder Phase Validation:**
```python
# Add to phase_2_5_parallel_build.md validation:
condition_nodes = [n for n in flow['nodes'] if n['data']['type'] == 'ConditionAgent']
for node in condition_nodes:
    input_field = node['data']['inputs'].get('conditionAgentInput', '')

    # Check if using plain text format (wrong)
    if input_field.startswith('{{') and input_field.endswith('}}'):
        print(f"❌ ERROR: {node['data']['label']} uses plain text variable format!")
        print(f"   Found: {input_field}")
        print(f"   Fix: Use rich text HTML format with <span> tags")
        exit(1)

    # Check for proper HTML format (correct)
    if '<span class="variable"' not in input_field:
        print(f"⚠️  WARNING: {node['data']['label']} may have improper variable format")
        print(f"   Expected: HTML <span> tags for variables")

print("✅ All condition nodes use proper rich text variable format")
```

### Technical Details

**Rich Text HTML Format Structure:**

```html
<p>
  <span
    class="variable"
    data-type="mention"
    data-id="question"        <!-- Variable name -->
    data-label="question"      <!-- Display label -->
  >
    {{ question }}             <!-- Template syntax -->
  </span>
</p>
```

**Required attributes:**
- `class="variable"` - Identifies this as a variable
- `data-type="mention"` - Indicates variable reference type
- `data-id` - The actual variable name used by Flowise
- `data-label` - UI display label (usually matches data-id)

**During execution, Flowise:**
1. Parses the HTML to find `<span class="variable">` tags
2. Extracts `data-id` to know which variable to use
3. Retrieves the variable value from flow context
4. **JSON-escapes the value** (adds quotes, escapes special chars)
5. Constructs valid JSON message to send to LLM

### Lesson Learned

**Flowise uses rich text HTML markup internally for variable handling.**

When generating Flowise JSON programmatically:
1. ❌ Don't use plain `"{{ variable }}"` syntax
2. ✅ Always wrap variables in proper HTML markup
3. ✅ Include all required attributes (class, data-type, data-id, data-label)
4. ✅ Test in Flowise UI to verify proper execution

**The plain text format looks correct but is non-functional** - Flowise doesn't recognize it as a variable reference.

### Related Issues

- Different from Pattern #7 (incomplete scenarios) - this is about variable format
- Different from missing inputParams (Pattern #11) - schema is complete, format is wrong
- Similar to malformed JSON issues but at the configuration level
- Only affects fields that accept variables (conditionAgentInput, agent messages, etc.)

### First Occurrence

- **Build**: Travel Booking & Expense Flow (2025-11-05)
- **Detected By**: User testing in Flowise - condition node didn't route
- **Symptom**: Node executed but produced no output, workflow stopped
- **Investigation**: Compared with working examples, found format difference
- **Fixed**: Updated to use rich text HTML format for variables
- **Documentation**: Added to FAILURE_PATTERNS.md as Pattern #13

### Related Documentation

- AGENT_PATTERN_REFERENCE.md: Section "CRITICAL: Variable Format in conditionAgentInput"
- Working examples: Check Agentic RAG Agents.json, Change and Adoption Agent Agents.json
- Flowise documentation: Variable references in rich text fields

---

## Node Type Mismatch (Pattern #14)

### Symptom

Builder generated nodes with incorrect `type` and `name` fields, causing nodes to not render properly in Flowise UI (missing icons, sync errors).

**User Report** (2025-11-05):
> "The Compliance Threshold Check is malformed (has no icon) and Compliant Output and Non-Compliant Output both don't have icons. I think this is the reason my BCM Assessment Input has a sync problem that won't go away."

**Visual Symptoms in Flowise**:
- Node appears without icon (blank/generic icon)
- Node shows "sync problem" that won't clear
- Node missing from palette or can't be configured

**Structural Symptoms in JSON**:
- `type` field doesn't match Flowise node type registry
- `name` field doesn't match expected naming convention
- Missing required `inputParams` for specific node types

**Severity**: CRITICAL - Workflow completely unusable

### Root Cause

Builder used generic or incorrect node type names instead of consulting canonical node templates:

| Incorrect Type | Correct Type | Node Purpose |
|----------------|--------------|--------------|
| `"StartFlow"` | `"Start"` | Start node |
| `"ConditionNode"` | `"ConditionAgent"` | Conditional routing |
| Empty `inputParams` | Required params | DirectReply message |

### Examples

**Example 1: Start Node with Wrong Type**

❌ **INCORRECT:**
```json
{
  "data": {
    "name": "startAgentflow",
    "type": "StartFlow",  // ❌ Wrong type
    "color": "#81c784"
  }
}
```

✅ **CORRECT:**
```json
{
  "data": {
    "name": "startAgentflow",
    "type": "Start",  // ✅ Correct type
    "color": "#7EE787",
    "hideInput": true
  }
}
```

**Example 2: ConditionAgent with Wrong Type/Name**

❌ **INCORRECT:**
```json
{
  "data": {
    "name": "conditionNode",  // ❌ Wrong name
    "type": "ConditionNode",  // ❌ Wrong type
    "color": "#ff9800"
  }
}
```

✅ **CORRECT:**
```json
{
  "data": {
    "name": "conditionAgentAgentflow",  // ✅ Correct name
    "type": "ConditionAgent",  // ✅ Correct type
    "color": "#ff8fab",
    "inputParams": [
      {
        "label": "Model",
        "name": "conditionAgentModel",
        "type": "asyncOptions",
        "loadMethod": "listModels",
        "loadConfig": true
      },
      {
        "label": "Instructions",
        "name": "conditionAgentInstructions",
        "type": "string",
        "rows": 4
      },
      {
        "label": "Input",
        "name": "conditionAgentInput",
        "type": "string",
        "acceptVariable": true
      },
      {
        "label": "Scenarios",
        "name": "conditionAgentScenarios",
        "type": "array"
      }
    ]
  }
}
```

**Example 3: DirectReply Missing Required Fields**

❌ **INCORRECT:**
```json
{
  "data": {
    "name": "directReply",
    "type": "DirectReply",
    "color": "#9c27b0",
    "inputParams": [],  // ❌ Empty
    "inputs": {}  // ❌ No directReplyMessage
  }
}
```

✅ **CORRECT:**
```json
{
  "data": {
    "name": "directReplyAgentflow",
    "type": "DirectReply",
    "color": "#4DDBBB",
    "hideOutput": true,  // ✅ Required for terminal node
    "inputParams": [
      {
        "label": "Message",
        "name": "directReplyMessage",  // ✅ Required field
        "type": "string",
        "rows": 4,
        "acceptVariable": true,
        "id": "directReplyAgentflow_0-input-directReplyMessage-string",
        "display": true
      }
    ],
    "inputs": {
      "directReplyMessage": "Workflow complete!"
    }
  }
}
```

### Detection Strategy

**Automated Validation**:

```python
def validate_node_types(workflow):
    """
    Validate node types match Flowise registry
    """
    issues = []

    for node in workflow["nodes"]:
        node_type = node["data"]["type"]
        node_name = node["data"]["name"]

        # Check Start node
        if "start" in node_name.lower():
            if node_type != "Start":
                issues.append({
                    "pattern": "#14",
                    "node": node["id"],
                    "issue": f"Start node has wrong type: {node_type} (should be 'Start')",
                    "severity": "CRITICAL"
                })
            if "hideInput" not in node["data"]:
                issues.append({
                    "pattern": "#14",
                    "node": node["id"],
                    "issue": "Start node missing 'hideInput: true'",
                    "severity": "HIGH"
                })

        # Check ConditionAgent node
        if "condition" in node_name.lower() and "agent" in node_name.lower():
            if node_type != "ConditionAgent":
                issues.append({
                    "pattern": "#14",
                    "node": node["id"],
                    "issue": f"ConditionAgent has wrong type: {node_type} (should be 'ConditionAgent')",
                    "severity": "CRITICAL"
                })
            if node_name != "conditionAgentAgentflow":
                issues.append({
                    "pattern": "#14",
                    "node": node["id"],
                    "issue": f"ConditionAgent has wrong name: {node_name} (should be 'conditionAgentAgentflow')",
                    "severity": "HIGH"
                })

            # Check required inputParams
            required_params = ["conditionAgentModel", "conditionAgentInstructions",
                             "conditionAgentInput", "conditionAgentScenarios"]
            input_param_names = [p["name"] for p in node["data"].get("inputParams", [])]
            for req in required_params:
                if req not in input_param_names:
                    issues.append({
                        "pattern": "#14",
                        "node": node["id"],
                        "issue": f"ConditionAgent missing required inputParam: {req}",
                        "severity": "CRITICAL"
                    })

        # Check DirectReply node
        if node_type == "DirectReply":
            if "hideOutput" not in node["data"] or not node["data"]["hideOutput"]:
                issues.append({
                    "pattern": "#14",
                    "node": node["id"],
                    "issue": "DirectReply node missing 'hideOutput: true'",
                    "severity": "HIGH"
                })

            input_params = node["data"].get("inputParams", [])
            has_message_param = any(p["name"] == "directReplyMessage" for p in input_params)
            if not has_message_param:
                issues.append({
                    "pattern": "#14",
                    "node": node["id"],
                    "issue": "DirectReply node missing 'directReplyMessage' inputParam",
                    "severity": "CRITICAL"
                })

    return issues
```

### Prevention Strategy

**1. Use Canonical Node Templates**

Builder MUST reference these template files:
- `/extensions/flowise/prompts/START-NODE-TEMPLATE.json` (type: "Start")
- `/extensions/flowise/prompts/CONDITION-NODE-TEMPLATE.json` (type: "Condition" - deterministic)
- `/extensions/flowise/prompts/DIRECT-REPLY-NODE-TEMPLATE.json` (type: "DirectReply")

For **ConditionAgent** (AI routing), reference pattern files:
- `/extensions/flowise/templates/afv2-patterns/03-routing.json`
- `/extensions/flowise/templates/afv2-patterns/04-iteration.json`
- `/extensions/flowise/templates/afv2-patterns/05-looping.json`
- `/extensions/flowise/templates/afv2-patterns/06-hierarchy.json`

**2. Node Type Registry**

Create authoritative mapping:

```python
NODE_TYPE_REGISTRY = {
    "Start": {
        "name": "startAgentflow",
        "type": "Start",
        "required_fields": ["hideInput"],
        "template_file": "START-NODE-TEMPLATE.json"
    },
    "ConditionAgent": {
        "name": "conditionAgentAgentflow",
        "type": "ConditionAgent",
        "required_params": [
            "conditionAgentModel",
            "conditionAgentInstructions",
            "conditionAgentInput",
            "conditionAgentScenarios"
        ],
        "reference_files": [
            "templates/afv2-patterns/03-routing.json",
            "templates/afv2-patterns/04-iteration.json"
        ]
    },
    "DirectReply": {
        "name": "directReplyAgentflow",
        "type": "DirectReply",
        "required_fields": ["hideOutput"],
        "required_params": ["directReplyMessage"],
        "template_file": "DIRECT-REPLY-NODE-TEMPLATE.json"
    }
}
```

**3. Update Builder Instructions**

Add to `phase_2_5_parallel_build.md`:

```markdown
## CRITICAL: Node Type Accuracy

**ALWAYS** use correct node types from templates:

| Node Purpose | Correct Type | Template/Reference |
|--------------|--------------|-------------------|
| Workflow start | `"type": "Start"` | START-NODE-TEMPLATE.json |
| AI routing | `"type": "ConditionAgent"` | 03-routing.json (pattern) |
| Deterministic logic | `"type": "Condition"` | CONDITION-NODE-TEMPLATE.json |
| Terminal output | `"type": "DirectReply"` | DIRECT-REPLY-NODE-TEMPLATE.json |

**NEVER** use:
- ❌ `"type": "StartFlow"`
- ❌ `"type": "ConditionNode"`
- ❌ `"type": "directReply"` (lowercase)

**DirectReply MUST have**:
- `hideOutput: true`
- `inputParams` with `directReplyMessage` field
- `inputs.directReplyMessage` with actual message content
```

### Fix Procedure

**1. Fix Start Node**

```bash
jq '(.nodes[] | select(.data.type == "StartFlow")) |= (
  .data.type = "Start" |
  .data.color = "#7EE787" |
  .data.hideInput = true
)' workflow.json > workflow.fixed.json
```

**2. Fix ConditionAgent Node**

```bash
jq '(.nodes[] | select(.data.type == "ConditionNode")) |= (
  .data.type = "ConditionAgent" |
  .data.name = "conditionAgentAgentflow" |
  .data.color = "#ff8fab"
)' workflow.json > workflow.fixed.json
```

**3. Fix DirectReply Nodes**

```bash
jq '(.nodes[] | select(.data.type == "DirectReply" and (.data.inputParams | length == 0))) |= (
  .data.hideOutput = true |
  .data.inputParams = [{
    "label": "Message",
    "name": "directReplyMessage",
    "type": "string",
    "rows": 4,
    "acceptVariable": true,
    "display": true
  }] |
  .data.inputs.directReplyMessage = "Workflow complete!"
)' workflow.json > workflow.fixed.json
```

### Impact

**When This Pattern Occurs:**
- ❌ Nodes don't render in Flowise UI (missing icons)
- ❌ Workflow shows "sync problem" errors
- ❌ Cannot configure or execute workflow
- ❌ Workflow import fails silently

**Severity**: CRITICAL - Workflow completely unusable

### Related Patterns

- **Pattern #8**: Missing inputParams (similar root cause)
- **Pattern #6**: Incorrect tool JSON structure (similar validation issue)

### Resolution Status

- ✅ Pattern documented: 2025-11-05
- ✅ BCM workflow fixed and validated: 2025-11-05
- ⏳ Validator updated: Pending
- ⏳ Builder instructions updated: Pending
- ⏳ Node type registry created: Pending

### Example Workflows Affected

- `bcm-compliance-assessment.json` (2025-11-05) - All 3 issues present (FIXED)

### Added to Global Pattern Library

This pattern has been added to:
- `/Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md`
- Pattern ID: `node-type-mismatch`
- Severity: CRITICAL
- First seen: 2025-11-05 (bcm-compliance-assessment build)
- Total patterns: 14

---

## Prevention Checklist

### Before Build Starts

- [ ] Task description contains "Flowise" keyword
- [ ] Detector returns `is_flowise=True`
- [ ] AGENT_PATTERN_REFERENCE.md loaded
- [ ] warehouse-operations-flow.json set as canonical reference
- [ ] Builder knows agent count and complexity
- [ ] mermaid_generator.py script exists and is executable

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

### During Build (Documentation Phase)

- [ ] Run mermaid_generator.py to create WORKFLOW-DIAGRAM.md
- [ ] Generate with all flags: --badges --interactive --legend --include-details
- [ ] Embed complete mermaid diagram in README.md
- [ ] Add diagram badges (Agents, Nodes, Complexity)
- [ ] Place diagram after title, before "## Overview"

### Before Build Completes (Test Phase)

- [ ] JSON file size > 800 lines (for 10+ agents)
- [ ] Node count matches: 1 start + 1 condition + N agents
- [ ] No `"customNode"` types
- [ ] No external file references
- [ ] Structure matches warehouse-operations-flow.json
- [ ] HIL gates have exactly 3 inputParams (no humanInputOutputAnchors)
- [ ] HIL gates have no humanInputOutputAnchors in inputs object
- [ ] HIL gates have hardcoded outputAnchors (proceed/reject)
- [ ] WORKFLOW-DIAGRAM.md exists (BLOCKING)
- [ ] README.md contains ```mermaid block (BLOCKING)
- [ ] README.md contains diagram badges (BLOCKING)

### After Build (Validation)

- [ ] Import to Flowise succeeds
- [ ] All agents visible on canvas
- [ ] Routing connections present
- [ ] Test with sample queries works
- [ ] Mermaid diagram renders correctly on GitHub

---

## Phantom Tool and Knowledge References

### Symptom

Flowise workflow imports successfully but agents show validation errors in Flowise UI:
- **Tools section**: Shows "Tool *" required field as **blank/empty** (even though count shows tools exist)
- **Knowledge section**: Shows "Vector Store *", "Embedding Model *", "Knowledge Name *" as **blank/empty** with placeholder text
- User must manually configure every tool and knowledge base in Flowise UI

**Example** (Internal Talent Mobility - 2025-11-01):
```
Agent.EmployeeProfiling validation errors:
- Tool * (blank) - Required field
- Tool * (blank) - Required field
- Tool * (blank) - Required field
- Vector Store * (blank) - Required field
- Embedding Model * (blank) - Required field
- Knowledge Name * (shows placeholder: "A short name for the knowledge base...")
```

### Root Cause

**Builder generates PLACEHOLDER/EXAMPLE tool and knowledge references that don't exist in Flowise.**

When Builder plans agent capabilities, it invents tool names based on what the agent should do:
```json
"agentTools": [
  {
    "agentSelectedTool": "queryWorkdayHCM",  // ← Invented name, not real Flowise tool
    "agentSelectedToolRequiresHumanInput": ""
  },
  {
    "agentSelectedTool": "analyzeSkillsHistory",  // ← Doesn't exist
    "agentSelectedToolRequiresHumanInput": ""
  }
]
```

Similarly for knowledge bases:
```json
"agentKnowledgeVSEmbeddings": [
  {
    "vectorStore": "workday_skills_cloud",  // ← Invented reference
    "embeddingModel": "text-embedding-3-small",
    "knowledgeName": "A short name for the knowledge base...",  // ← Placeholder text
    "knowledgeDescription": "Describe what the knowledge base is about...",  // ← Placeholder
    "returnSourceDocuments": true
  }
]
```

**What happens in Flowise UI**:
1. User imports workflow ✓
2. Flowise tries to resolve "queryWorkdayHCM" tool reference
3. **Tool doesn't exist** in Flowise tool library
4. Dropdown shows blank (required field validation fails)
5. Same for vector stores, embedding models, knowledge bases

### Impact

**User Experience**:
- Workflow appears "broken" on import
- Every agent shows multiple validation errors
- User must manually configure all tools and knowledge bases
- Time-consuming post-import setup required

**Examples from Recent Builds**:
- **Internal Talent Mobility**: 6-7 phantom tools per agent × 7 agents = ~40+ manual configurations
- **Gig Marketplace**: Tools like "workday_get_worker_skills", "calculate_skill_similarity" don't exist

### Fix

**⚠️ APPROACH EVOLUTION - Nov 2025 Update**

**CURRENT Approach (Nov 2025+)**: Standard tools + documented custom tools
1. ✅ **INCLUDE STANDARD TOOLS** (currentDateTime + searXNG) - Real, working tools
2. ✅ **DOCUMENT CUSTOM TOOLS** in README - User adds in Flowise UI
3. ✅ **OMIT KNOWLEDGE BASES** (leave empty) - User configures in Flowise UI
4. ❌ **DO NOT INVENT** placeholder tool/knowledge names

**Standard Tools (Required as of Nov 2025)**:
ALL agents MUST include these 2 standard tools (NOT phantom references):
- **currentDateTime**: Real tool providing temporal context
- **searXNG**: Real federated search tool (apiBase: https://s.llam.ai)

These are NOT phantom references - they are real, required tools with actual implementations.
See: `/extensions/flowise/tool-configs/STANDARD_TOOLS.md`

**LEGACY Approach (Pre-Nov 2025 - DEPRECATED)**:
Leave all arrays completely empty (`agentTools: []`). This approach is NO LONGER USED.

**CORRECT Pattern (Option 1 - Standard Tools Only)**:
```json
{
  "inputs": {
    "agentModel": "chatOpenAI",
    "agentMessages": "",
    "agentTools": [
      {
        "agentSelectedTool": "currentDateTime",
        "agentSelectedToolRequiresHumanInput": "",
        "agentSelectedToolConfig": {
          "agentSelectedTool": "currentDateTime"
        }
      },
      {
        "agentSelectedTool": "searXNG",
        "agentSelectedToolRequiresHumanInput": "",
        "agentSelectedToolConfig": {
          "apiBase": "https://s.llam.ai",
          "toolName": "searxng-search",
          "toolDescription": "Federated web/meta search. Use when you need fresh facts or sources. Provide a natural-language query; returns a ranked, de-duplicated JSON list of result metadata for follow-up browsing and citation.",
          "headers": "",
          "format": "json",
          "categories": "",
          "engines": "",
          "language": "",
          "pageno": "",
          "time_range": "",
          "safesearch": "",
          "agentSelectedTool": "searXNG"
        }
      }
    ],  // ← Standard tools included, custom tools documented separately
    "agentKnowledgeDocumentStores": "",
    "agentKnowledgeVSEmbeddings": "",
    "agentEnableMemory": true,
    "agentMemoryType": "allMessages"
  }
}
```

**LEGACY Pattern (Pre-Nov 2025 - Empty Arrays)**:
```json
{
  "inputs": {
    "agentModel": "chatOpenAI",
    "agentMessages": [...],
    "agentTools": [],  // ← Old approach: completely empty
    "agentKnowledgeVSEmbeddings": [],
    "agentEnableMemory": true,
    "agentMemoryType": "allMessages"
  }
}
```

**CORRECT Pattern (Option 2 - Documentation)**:

In `README.md` or `INTEGRATION_GUIDE.md`:
```markdown
## Required Tool Configuration

After importing the workflow to Flowise, configure these custom tools:

### Agent.EmployeeProfiling Tools
1. **queryWorkdayHCM** - Custom Tool
   - Purpose: Query Workday HCM API for employee data
   - Auth: OAuth 2.0
   - Endpoint: https://api.workday.com/v1/workers

2. **analyzeSkillsHistory** - Custom Tool
   - Purpose: Analyze employee skills progression
   - Auth: API Key
   - Endpoint: https://api.workday.com/v1/skills

### Knowledge Base Configuration
1. **Workday Skills Cloud** - Vector Store
   - Type: Pinecone / Weaviate / Qdrant
   - Embedding Model: text-embedding-3-small (OpenAI)
   - Content: Workday Skills Cloud ontology documents
```

### Prevention

**During Architect Phase**:
- [ ] Architect MUST NOT invent tool names
- [ ] Architect MUST document required tools in architecture.md
- [ ] If APIs are mentioned, document as "Custom Tools (user configured)"

**During Builder Phase** (Nov 2025+ Approach):
- [ ] Builder INCLUDES standard tools (currentDateTime + searXNG) in `agentTools`
- [ ] Builder uses exact Flowise UI structure for standard tools (see Pattern #6)
- [ ] Builder uses correct tool names: "searXNG" NOT "searxng-search"
- [ ] Builder uses correct field names: "apiBase" NOT "baseUrl"
- [ ] Builder leaves `agentKnowledgeVSEmbeddings: []` empty (user configures in UI)
- [ ] For custom tools: Builder creates documentation files (not JSON references)
- [ ] Built-in tools (OpenAI web search, code interpreter) are OK to include in agentToolsBuiltInOpenAI
  - `tool-configs/recommended-tools.md`
  - `knowledge-configs/recommended-knowledge-bases.md`

**Validation Rules** (Test Phase - Nov 2025+ Updated):
```bash
# Check for correct standard tool names
for tool in $(jq -r '.nodes[].data.inputs.agentTools[]?.agentSelectedTool' flow.json 2>/dev/null); do
  if [[ -n "$tool" && "$tool" != "currentDateTime" && "$tool" != "searXNG" ]]; then
    echo "❌ WARNING: Found non-standard tool reference '$tool'"
    echo "   Standard tools must be: 'currentDateTime' and 'searXNG' (capital XNG!)"
    echo "   Custom tools should be documented in INTEGRATION_GUIDE.md instead"
  fi
done

# Check for correct searXNG structure (apiBase not baseUrl)
if jq -e '.nodes[].data.inputs.agentTools[]? | select(.agentSelectedTool == "searXNG") | select(.agentSelectedToolConfig.baseUrl)' flow.json > /dev/null 2>&1; then
  echo "❌ ERROR: searXNG uses 'baseUrl' - should be 'apiBase'"
  echo "   Fix: Change agentSelectedToolConfig.baseUrl to agentSelectedToolConfig.apiBase"
fi

# Check for boolean instead of empty string in agentSelectedToolRequiresHumanInput
if jq -e '.nodes[].data.inputs.agentTools[]? | select(.agentSelectedToolRequiresHumanInput == true or .agentSelectedToolRequiresHumanInput == false)' flow.json > /dev/null 2>&1; then
  echo "❌ ERROR: agentSelectedToolRequiresHumanInput uses boolean (true/false)"
  echo "   Fix: Use empty string \"\" instead of false, or omit the field"
fi

# Check for incorrect tool name "searxng-search" instead of "searXNG"
if jq -e '.nodes[].data.inputs.agentTools[]? | select(.agentSelectedTool == "searxng-search")' flow.json > /dev/null 2>&1; then
  echo "❌ ERROR: Found 'searxng-search' - should be 'searXNG' (capital XNG)"
  echo "   Note: 'searxng-search' goes in agentSelectedToolConfig.toolName, NOT agentSelectedTool"
fi

# Check for placeholder text in knowledge configs
if jq -e '.nodes[].data.inputs.agentKnowledgeVSEmbeddings[]? | select(.knowledgeName | contains("short name"))' flow.json > /dev/null 2>&1; then
  echo "❌ ERROR: Found placeholder text in knowledgeName field"
  echo "   Remove placeholder entries or replace with actual knowledge base names"
fi
```

### Documentation Template

**Add to INTEGRATION_GUIDE.md**:
```markdown
## Post-Import Configuration

This workflow requires manual configuration in Flowise UI:

### 1. Custom Tools Setup
For each agent, you'll need to create custom tools:

**Agent.EmployeeProfiling**:
- queryWorkdayHCM (Workday HCM API integration)
- analyzeSkillsHistory (Skills analysis endpoint)
- extractCompetencies (Competency extraction)

**How to create custom tools**:
1. In Flowise, go to Tools → Add Custom Tool
2. Configure API endpoints, authentication, and parameters
3. Assign tools to agents in the workflow

### 2. Knowledge Base Setup
Create vector stores for domain knowledge:

**Workday Skills Cloud Knowledge Base**:
- Vector Store: Choose (Pinecone, Weaviate, Qdrant, etc.)
- Embedding Model: text-embedding-3-small
- Documents: Upload Workday Skills Cloud ontology, competency definitions
- Assign to: Agent.EmployeeProfiling, Agent.SkillsMatching

### 3. Credential Configuration
Add API credentials in Flowise Credentials Manager:
- OpenAI API Key (for ChatGPT model)
- Workday OAuth 2.0 credentials
- Vector store API keys (if using cloud vector DB)
```

### Examples

**WRONG (Phantom References)**:
```json
"agentTools": [
  {"agentSelectedTool": "queryWorkdayHCM"},      // Doesn't exist
  {"agentSelectedTool": "analyzeSkillsHistory"}  // Doesn't exist
]
```

**RIGHT (Nov 2025+ - Standard Tools + Documentation)**:
```json
"agentTools": [
  {
    "agentSelectedTool": "currentDateTime",
    "agentSelectedToolRequiresHumanInput": "",
    "agentSelectedToolConfig": {
      "agentSelectedTool": "currentDateTime"
    }
  },
  {
    "agentSelectedTool": "searXNG",
    "agentSelectedToolRequiresHumanInput": "",
    "agentSelectedToolConfig": {
      "apiBase": "https://s.llam.ai",
      "toolName": "searxng-search",
      "toolDescription": "Federated web/meta search. Use when you need fresh facts or sources. Provide a natural-language query; returns a ranked, de-duplicated JSON list of result metadata for follow-up browsing and citation.",
      "headers": "",
      "format": "json",
      "categories": "",
      "engines": "",
      "language": "",
      "pageno": "",
      "time_range": "",
      "safesearch": "",
      "agentSelectedTool": "searXNG"
    }
  }
]  // ✓ Standard tools included with EXACT Flowise UI structure
```

Plus in `INTEGRATION_GUIDE.md`:
> **Custom Tools (User Configured)**: Create custom tools in Flowise for queryWorkdayHCM, analyzeSkillsHistory...

**LEGACY (Pre-Nov 2025 - DEPRECATED)**:
```json
"agentTools": []  // Old approach: completely empty
```

**ACCEPTABLE (Built-in OpenAI Tools)**:
```json
"agentToolsBuiltInOpenAI": ["web_search_preview", "code_interpreter"]  // ✓ Actual OpenAI tools
"agentTools": [/* standard tools here */]  // Include standard tools even with built-in tools
```

---

## Incorrect Tool JSON Structure (Pattern #6)

### Symptom

Flowise workflow crashes with **white screen** when opening agent nodes. Browser console shows:
- `Error: Invalid value for <svg> attribute width="1.3rem"`
- `Failed to load resource: the server responded with a status of 500 () (searxng-search, line 0)`
- `SyntaxError: JSON Parse error: Unexpected identifier "object"`

**User Experience**:
- Workflow imports successfully ✓
- Visual canvas displays nodes ✓
- Double-clicking any agent node → **white screen crash** ❌
- Agent configuration completely inaccessible

**Example** (Internal Talent Mobility - 2025-11-01):
```
All 8 agents have:
- agentTools: [currentDateTime, searxng-search] ✓ (referenced in JSON)
- BUT: Tools don't exist in Flowise instance ❌
- Result: 500 error when UI tries to load tool metadata → crash
```

### Root Cause

**Workflow JSON uses INCORRECT tool structure - wrong field names, wrong data types, wrong tool names.**

When Flowise UI loads an agent node, it:
1. Reads `agentTools` array from workflow JSON
2. Attempts to parse tool configuration with expected field names
3. **Field names don't match** (e.g., "baseUrl" instead of "apiBase") → Server returns 500 HTTP error
4. **Tool name doesn't match** (e.g., "searxng-search" instead of "searXNG") → Tool not found
5. UI tries to parse error response as JSON → Parse error
6. React component crashes trying to render invalid tool data → White screen

**The issue is JSON structure, NOT missing tools**:
- Tools are built-in to Flowise (currentDateTime, searXNG)
- But we used WRONG field names and structure
- Must match EXACT structure that Flowise UI generates
- Discovered by comparing working export vs our generated structure

### Impact

**Severity**: CRITICAL - Workflow completely unusable
**Frequency**: 100% when auto-including tools that don't exist
**User Experience**: Extremely confusing - workflow appears to import successfully but is broken

**Example from Recent Builds**:
- **Internal Talent Mobility** (task 1d8490fa): Built with INCORRECT tool structure (commit 91a13ef)
  - Used "searxng-search" instead of "searXNG"
  - Used "baseUrl" instead of "apiBase"
  - Used `false` instead of `""` for requiresHumanInput
  - Result: 500 errors and white screen crashes
- **Personalized Onboarding** (re-export after manual fix): Tools added via Flowise UI
  - Uses "searXNG" (correct name)
  - Uses "apiBase" (correct field)
  - Uses `""` (correct type)
  - Result: Workflow works perfectly ✓

### Fix Applied

**Corrected tool JSON structure to match Flowise UI output** (2025-11-01 - after discovering true root cause)

The initial fix (commit a743294) removed tools entirely, but the REAL issue was using wrong structure:

1. **Updated AGENT-NODE-TEMPLATE.json with CORRECT structure**
   - Changed tool name: "searxng-search" → "searXNG"
   - Changed field: "baseUrl" → "apiBase"
   - Changed type: `false` → `""`
   - Added all required fields: toolName, toolDescription, headers, format, categories, engines, language, etc.

2. **Re-added orchestrator requirements with correct structure**
   - Added back "Required Standard Tools" to Architect phase
   - Added back standard tools enforcement to Builder phase
   - Specified EXACT field names and structure to match Flowise UI

3. **Updated STANDARD_TOOLS.md**
   - Changed back to "Auto-included (with correct structure)"
   - Documented exact Flowise UI structure
   - Emphasized critical field name differences

**Discovery process**:
- User exported personalized-onboarding workflow AFTER adding tools via Flowise UI
- Compared working structure vs our broken structure
- Found multiple field name and type mismatches
- Updated to use EXACT Flowise UI structure

### Prevention

**CRITICAL RULE**: Use EXACT JSON structure from Flowise UI exports, not invented structure.

**Before generating workflow JSON**:
- [ ] Reference AGENT-NODE-TEMPLATE.json for exact tool structure
- [ ] Use correct tool names: "searXNG" NOT "searxng-search", "currentDateTime" (correct)
- [ ] Use correct field names: "apiBase" NOT "baseUrl"
- [ ] Use correct data types: `""` (empty string) NOT `false` (boolean)
- [ ] Include ALL required fields (toolName, toolDescription, format, etc.)

**Builder phase requirements**:
- [ ] Copy tool structure EXACTLY from AGENT-NODE-TEMPLATE.json
- [ ] Do NOT invent or modify field names
- [ ] Do NOT change data types (string vs boolean)
- [ ] Do NOT omit fields from the template
- [ ] When in doubt, export a working workflow from Flowise UI and compare

---

## ConditionAgent Incomplete Scenarios (Pattern #7)

### Symptom

**User Report** (2025-11-02):
> "The node 'Detect User Intention' is not populated - all scenarios 0-7 show blank Model, Instructions, and Input fields in Flowise UI"

Generated ConditionAgent has:
- ✅ Main fields populated: `conditionAgentModel`, `conditionAgentInstructions`, `conditionAgentInput`
- ❌ All scenarios (0-7) show blank in UI: Model = blank, Instructions = blank, Input = blank
- ❌ Scenarios array only contains simple objects: `{"scenario": "description"}`
- ❌ Missing: `model`, `instructions`, `input` fields for EACH scenario

**Severity**: CRITICAL - Router cannot function, requires manual configuration of 8+ scenarios

### Root Cause

**Incorrect scenarios array structure**

The `conditionAgentScenarios` array was generated with simple description-only objects:

```json
"conditionAgentScenarios": [
  {"scenario": "Order status, tracking, delivery questions"},
  {"scenario": "Returns, refunds, RMA, exchanges"},
  {"scenario": "Product information, specs, availability"},
  ...
]
```

But Flowise UI expects **complete configuration objects** for each scenario with model, instructions, and input fields.

### Impact

- **UI shows blank fields**: All 8 scenarios appear unconfigured in Flowise UI
- **Manual work required**: User must manually configure Model, Instructions, Input for 8+ scenarios
- **Router non-functional**: Workflow cannot route without scenario configuration
- **User confusion**: Main ConditionAgent fields work, but scenarios don't - unclear why
- **Production blocker**: Workflow cannot be used until all scenarios manually fixed

### Fix Required

Each scenario must be a **complete configuration object**, not just a description string.

**WRONG (Current)**:
```json
"conditionAgentScenarios": [
  {"scenario": "Order status, tracking, delivery questions"}
]
```

**CORRECT (Required)**:
```json
"conditionAgentScenarios": [
  {
    "scenario": "Order status, tracking, delivery questions",
    "model": "chatOpenAI",
    "instructions": "Route to Order Tracking when user asks about: order status, tracking number, delivery estimates, shipment updates, 'where is my order' (WISMO). Exception: if mentions 'return order' route to Returns instead.",
    "input": "{{question}}"
  },
  {
    "scenario": "Returns, refunds, RMA, exchanges",
    "model": "chatOpenAI",
    "instructions": "Route to Returns when user asks about: return policy, refund status, RMA processing, exchanges, defective items, damaged products. Exception: informational-only questions like 'What is your return policy?' may go to General Help.",
    "input": "{{question}}"
  }
]
```

**Critical Requirements**:
1. ✅ **scenario**: Description of what triggers this route
2. ✅ **model**: MUST match parent `conditionAgentModel` (e.g., "chatOpenAI")
3. ✅ **instructions**: Routing logic with keywords, exceptions, and context rules
4. ✅ **input**: Usually `"{{question}}"` to pass user input to scenario evaluation

### Prevention

**Before generating ConditionAgent**:
- [ ] Check AGENT_PATTERN_REFERENCE.md Section 2.2 for complete scenario structure
- [ ] Each scenario is a FULL object with 4 fields: scenario, model, instructions, input
- [ ] Model field matches parent conditionAgentModel exactly
- [ ] Instructions include keywords, exceptions, and routing rules
- [ ] Input field is `"{{question}}"` or appropriate variable

**During Builder phase**:
- [ ] Generate complete scenario objects, not just descriptions
- [ ] Copy model from parent conditionAgentModel to each scenario
- [ ] Write detailed routing instructions for each scenario
- [ ] Include exception handling in instructions (e.g., "if X then route to Y instead")

**Test in Flowise UI**:
- [ ] Open ConditionAgent node after import
- [ ] Verify each scenario (0, 1, 2...) shows:
  - ✅ Model: chatOpenAI (or parent model)
  - ✅ Instructions: populated with routing logic
  - ✅ Input: {{question}}
- [ ] If ANY scenario shows blank Model/Instructions/Input → PATTERN VIOLATED

### Template

**Complete Scenario Object Template**:
```json
{
  "scenario": "[Clear description of routing trigger]",
  "model": "chatOpenAI",
  "instructions": "[Routing logic]\n- Keywords: [list]\n- Route to: Scenario [N] ([Agent.Name])\n- Exceptions: [special cases]",
  "input": "{{question}}"
}
```

**Multi-Agent Router Example** (8 scenarios):
```json
"conditionAgentScenarios": [
  {
    "scenario": "Order Tracking - status, tracking, delivery",
    "model": "chatOpenAI",
    "instructions": "Keywords: order status, tracking, WISMO, delivery estimate\nRoute to: Scenario 0 (Agent.OrderTracking)\nException: return order → Scenario 1",
    "input": "{{question}}"
  },
  {
    "scenario": "Returns - refunds, RMA, exchanges",
    "model": "chatOpenAI",
    "instructions": "Keywords: return, refund, RMA, exchange, defective\nRoute to: Scenario 1 (Agent.Returns)\nException: informational only → Scenario 7",
    "input": "{{question}}"
  }
  // ... 6 more complete scenario objects
]
```

### Detection in Code Review

**Automated check**:
```python
# Check if scenarios are complete
for scenario in data['inputs']['conditionAgentScenarios']:
    assert 'scenario' in scenario, "Missing scenario description"
    assert 'model' in scenario, "Missing model field - CRITICAL"
    assert 'instructions' in scenario, "Missing instructions - CRITICAL"
    assert 'input' in scenario, "Missing input field - CRITICAL"
    assert scenario['model'] == parent_model, "Model mismatch"
```

**Manual verification**:
1. Open generated JSON in editor
2. Search for `"conditionAgentScenarios"`
3. Verify each scenario object has 4 fields minimum
4. If only `{"scenario": "..."}` → BUG DETECTED

### Related Patterns

- Pattern #4: condition-agent-no-scenarios (no scenarios at all)
- Pattern #7: condition-agent-incomplete-scenarios (scenarios exist but incomplete)

### Added to Global Pattern Library

This pattern has been added to:
- `/Users/name/.context-foundry/patterns/common-issues.json`
- Pattern ID: `condition-agent-incomplete-scenarios`
- Severity: CRITICAL
- First seen: 2025-11-02 (ecommerce-support-workflow build)

---

**Documentation pattern**:
```markdown
## Recommended Tools Setup (Optional)

To enhance agent capabilities, consider creating these tools in Flowise:

1. **currentDateTime** - Provides temporal awareness
   - Type: Custom JavaScript function
   - Returns: Current date/time in ISO format
   - Used by: All agents (for evaluating search result freshness)

2. **searxng-search** - Federated web search
   - Type: Custom HTTP API tool
   - Base URL: https://s.llam.ai
   - Used by: All agents (for real-time information)

After creating these tools in Flowise, you can manually add them to agents.
```

### Examples

**WRONG (Incorrect JSON Structure)**:
```json
{
  "inputs": {
    "agentTools": [
      {
        "agentSelectedTool": "currentDateTime",
        "agentSelectedToolRequiresHumanInput": false,  // ❌ Boolean!
        "agentSelectedToolConfig": {
          "agentSelectedTool": "currentDateTime"
        }
      },
      {
        "agentSelectedTool": "searxng-search",  // ❌ Wrong name!
        "agentSelectedToolRequiresHumanInput": false,  // ❌ Boolean!
        "agentSelectedToolConfig": {
          "agentSelectedTool": "searxng-search",
          "baseUrl": "https://s.llam.ai"  // ❌ Wrong field!
        }
      }
    ]
  }
}
```

**RIGHT (Correct Flowise UI Structure)**:
```json
{
  "inputs": {
    "agentTools": [
      {
        "agentSelectedTool": "currentDateTime",
        "agentSelectedToolRequiresHumanInput": "",  // ✓ Empty string
        "agentSelectedToolConfig": {
          "agentSelectedTool": "currentDateTime"
        }
      },
      {
        "agentSelectedTool": "searXNG",  // ✓ Correct name!
        "agentSelectedToolRequiresHumanInput": "",  // ✓ Empty string
        "agentSelectedToolConfig": {
          "apiBase": "https://s.llam.ai",  // ✓ Correct field!
          "toolName": "searxng-search",
          "toolDescription": "Federated web/meta search. Use when you need fresh facts or sources. Provide a natural-language query; returns a ranked, de-duplicated JSON list of result metadata for follow-up browsing and citation.",
          "headers": "",
          "format": "json",
          "categories": "",
          "engines": "",
          "language": "",
          "pageno": "",
          "time_range": "",
          "safesearch": "",
          "agentSelectedTool": "searXNG"
        }
      }
    ]
  }
}
```

### Related Patterns

**Pattern #5** (Phantom Tool References) vs **Pattern #6** (Incorrect Tool JSON Structure):
- **Pattern #5**: Inventing tool names that don't exist (`queryWorkdayHCM`, `analyzeSkillsHistory`)
- **Pattern #6**: Using REAL tools but with wrong JSON structure (wrong field names, wrong data types)

Both cause similar symptoms (500 errors, UI crashes) but different root causes:
- Pattern #5: Tool names are completely fictional/invented → Fix: Don't invent tools, use empty arrays
- Pattern #6: Tool names are real but structure is wrong → Fix: Use EXACT Flowise UI structure

**Key difference**: Pattern #5 is about tool existence, Pattern #6 is about JSON correctness.

---

## HIL Gate Invalid inputParams Configuration (Pattern #10)

### Symptom

When double-clicking a Human Input (HIL) node in Flowise, the UI shows a **blank screen** instead of the configuration panel. The node appears on the canvas but is not editable.

**Console Error** (if visible):
```
TypeError: Cannot read properties of undefined
Failed to render node configuration panel
```

### Root Cause

**HIL Gate node includes "Output Anchors" as an editable inputParam**

The generated HIL node incorrectly includes `humanInputOutputAnchors` as a user-configurable field in the `inputParams` array:

```json
{
  "data": {
    "name": "humanInputAgentflow",
    "inputParams": [
      {
        "label": "Description Type",
        "name": "humanInputDescriptionType",
        ...
      },
      {
        "label": "Description",
        "name": "humanInputDescription",
        ...
      },
      {
        "label": "Enable Feedback",
        "name": "humanInputEnableFeedback",
        ...
      },
      {
        "label": "Output Anchors",  // ❌ THIS SHOULD NOT EXIST
        "name": "humanInputOutputAnchors",
        "type": "array",
        "array": [
          {
            "label": "Anchor Name",
            "name": "anchorName",
            "type": "string"
          },
          {
            "label": "Anchor Label",
            "name": "anchorLabel",
            "type": "string"
          }
        ]
      }
    ],
    "inputs": {
      "humanInputDescriptionType": "fixed",
      "humanInputDescription": "...",
      "humanInputEnableFeedback": true,
      "humanInputOutputAnchors": [  // ❌ THIS SHOULD NOT EXIST
        {
          "anchorName": "proceed",
          "anchorLabel": "Approve"
        },
        {
          "anchorName": "reject",
          "anchorLabel": "Reject"
        }
      ]
    },
    "outputAnchors": [  // ✅ This is correct (hardcoded)
      {
        "id": "humanInputAgentflow_0-output-proceed",
        "label": "Proceed",
        "name": "proceed"
      },
      {
        "id": "humanInputAgentflow_0-output-reject",
        "label": "Reject",
        "name": "reject"
      }
    ]
  }
}
```

**Why This Causes Blank Screen**:
- Flowise UI expects HIL nodes to have only 3 configurable fields
- Adding `humanInputOutputAnchors` as inputParam confuses the rendering engine
- The UI attempts to render an array field that shouldn't exist
- Results in rendering failure → blank screen

### Impact

- **Severity**: HIGH - Node completely unusable in Flowise UI
- **Frequency**: Occurred in expense-approval-loop build (2025-11-04)
- **User Experience**: Confusing - node appears on canvas but can't be configured
- **Detectability**: Only discovered when user attempts to edit the node

### Expected Structure (Correct)

HIL nodes should have **ONLY 3 inputParams**:

```json
{
  "data": {
    "name": "humanInputAgentflow",
    "version": 1.0,
    "type": "HumanInput",
    "color": "#F06292",
    "inputParams": [
      {
        "label": "Description Type",
        "name": "humanInputDescriptionType",
        "type": "options",
        "options": [
          {"label": "Fixed", "name": "fixed"},
          {"label": "Dynamic", "name": "dynamic"}
        ],
        "display": true
      },
      {
        "label": "Description",
        "name": "humanInputDescription",
        "type": "string",
        "acceptVariable": true,
        "rows": 8,
        "show": {"humanInputDescriptionType": "fixed"},
        "display": true
      },
      {
        "label": "Enable Feedback",
        "name": "humanInputEnableFeedback",
        "type": "boolean",
        "default": true,
        "display": true
      }
    ],
    "inputs": {
      "humanInputDescriptionType": "fixed",
      "humanInputDescription": "...",
      "humanInputEnableFeedback": true
      // NO humanInputOutputAnchors!
    },
    "outputAnchors": [
      // Hardcoded, NOT user-configurable
      {
        "id": "humanInputAgentflow_0-output-proceed",
        "label": "Proceed",
        "name": "proceed",
        "description": "User approved"
      },
      {
        "id": "humanInputAgentflow_0-output-reject",
        "label": "Reject",
        "name": "reject",
        "description": "User rejected"
      }
    ]
  }
}
```

### Detection

**Automated Validation** (Recommended):
```bash
# Run comprehensive validator (checks Pattern #10 + all other patterns)
python3 /Users/name/homelab/context-foundry/extensions/flowise/validate_workflow.py workflow.json

# Exit codes:
#   0 = All validations passed
#   1 = Critical failures (Pattern #10 detected, build blocked)
#   2 = Warnings (manual review recommended)
```

**Manual Validation Commands**:
```bash
# Check for invalid humanInputOutputAnchors inputParam
jq '.nodes[] | select(.data.name == "humanInputAgentflow") | .data.inputParams[] | select(.name == "humanInputOutputAnchors")' flow.json

# If this returns results, the HIL node is INVALID
# Expected: No output (empty)
```

**Count InputParams** (should be exactly 3):
```bash
jq '.nodes[] | select(.data.name == "humanInputAgentflow") | {label: .data.label, inputParams_count: (.data.inputParams | length)}' flow.json

# Expected output:
# {
#   "label": "Manager Approval",
#   "inputParams_count": 3
# }
```

**Check for humanInputOutputAnchors in inputs**:
```bash
jq '.nodes[] | select(.data.name == "humanInputAgentflow") | .data.inputs | has("humanInputOutputAnchors")' flow.json

# Expected: false
```

### Fix Applied

**Removal of invalid configuration**:

1. Removed `humanInputOutputAnchors` from `inputParams` array
2. Removed `humanInputOutputAnchors` from `inputs` object
3. Kept `outputAnchors` hardcoded in node structure
4. Updated to canonical HIL-NODE-TEMPLATE.json structure

**Diff**:
```diff
  "inputParams": [
    {
      "label": "Description Type",
      ...
    },
    {
      "label": "Description",
      ...
    },
    {
      "label": "Enable Feedback",
      ...
-   },
-   {
-     "label": "Output Anchors",
-     "name": "humanInputOutputAnchors",
-     "type": "array",
-     ...
    }
  ],
  "inputs": {
    "humanInputDescriptionType": "fixed",
    "humanInputDescription": "...",
-   "humanInputEnableFeedback": true,
-   "humanInputOutputAnchors": [...]
+   "humanInputEnableFeedback": true
  }
```

### Prevention

**Automated Enforcement** (Test Phase):

The Context Foundry orchestrator automatically runs `validate_workflow.py` in the Test phase, which:
- ✅ Checks HIL gates have exactly 3 inputParams
- ✅ Detects invalid `humanInputOutputAnchors` in inputParams or inputs
- ✅ Validates outputAnchors are hardcoded (not user-configurable)
- ✅ **BLOCKS deployment** if Pattern #10 detected (exit code 1)

See: `tools/orchestrator_prompt.txt` lines 1877-1918 (Phase 4: Test)

**Builder Phase Instructions**:

When generating HIL (humanInputAgentflow) nodes:

1. ✅ **DO**: Use exactly **5 inputParams** (Description Type, Description, Model, Prompt, Enable Feedback)
2. ✅ **DO**: Include humanInputModel and humanInputModelPrompt even if hidden
3. ✅ **DO**: Include humanInputModelConfig in inputs object
4. ✅ **DO**: Hardcode outputAnchors with "proceed" and "reject" routes
5. ✅ **DO**: Reference HIL-NODE-TEMPLATE.json for canonical structure
6. ✅ **DO**: Use correct dimensions: width 221, height 80
7. ❌ **DON'T**: Add "Output Anchors" or `humanInputOutputAnchors` as inputParam
8. ❌ **DON'T**: Include `humanInputOutputAnchors` in inputs object
9. ❌ **DON'T**: Make outputAnchors user-configurable
10. ❌ **DON'T**: Omit hidden fields from schema (Pattern #11)

**Checklist for HIL Nodes**:
- [ ] inputParams array has exactly **5 elements** (not 3!)
- [ ] humanInputModel present (even if hidden via "show")
- [ ] humanInputModelPrompt present (even if hidden via "show")
- [ ] humanInputModelConfig in inputs object
- [ ] No `humanInputOutputAnchors` in inputParams
- [ ] No `humanInputOutputAnchors` in inputs
- [ ] outputAnchors hardcoded with proceed/reject
- [ ] version = 1.0
- [ ] type = "HumanInput" (not "Human Input")
- [ ] color = "#F06292"
- [ ] width = 221, height = 80

**Reference**: `/Users/name/homelab/context-foundry/extensions/flowise/prompts/HIL-NODE-TEMPLATE.json`

### Related Issues

- Similar to incorrect tool structure (Pattern #6) - wrong field configuration
- Different from phantom tools (Pattern #5) - fields exist but shouldn't be editable
- Affects UI rendering rather than runtime execution

### First Occurrence

- **Build**: expense-approval-loop (2025-11-04)
- **Detected By**: User attempting to configure node in Flowise UI
- **Fixed**: Manual removal of invalid inputParam + inputs field
- **Documentation**: Added to FAILURE_PATTERNS.md as Pattern #10

---

## Example Negative Pattern

**File**: `patterns/failures/enterprise-ops-center-meta-description.json`

This file shows the INCORRECT meta-description output that was generated before the fix was applied. Use it as a reference for what NOT to generate.

---

## Missing Start Node (Pattern #15)

### Symptom

Workflow JSON file loads in Flowise but cannot execute. The workflow has 15-20 nodes including Router, specialized agents, tools, and HIL gates, but **no Start node**. Users cannot submit input to the workflow.

**Visual Indicators**:
- Workflow appears in Flowise UI with all nodes visible
- No entry point/intake form visible
- First node is ConditionAgent (Router) instead of Start node
- Workflow cannot be triggered or tested

**Example Failed Structure**:
```json
{
  "nodes": [
    {
      "id": "conditionAgentAgentflow_0",  // ❌ WRONG: Router as first node
      "type": "conditionAgent",
      "data": {
        "type": "ConditionAgent",
        ...
      }
    },
    // ... 19 more nodes (agents, tools, HIL)
    // ❌ NO Start node anywhere
  ],
  "edges": [
    // Router connects to agents, but nothing feeds into Router
  ]
}
```

**Expected Structure**:
```json
{
  "nodes": [
    {
      "id": "startAgentflow_0",  // ✅ CORRECT: Start node first
      "type": "Start",
      "data": {
        "type": "Start",
        "name": "startAgentflow",
        "inputs": {
          "formTitle": "Vehicle & Parking Management",
          "formDescription": "Welcome...",
          "formInputTypes": [...]
        }
      }
    },
    {
      "id": "conditionAgentAgentflow_0",  // Router second
      ...
    }
  ]
}
```

### Root Cause

**Architect hallucinated existing implementation** and assumed Start node was already present, leading to:

1. **File Existence Hallucination**: Architect incorrectly believed there was an "existing 2,195-line workflow" that just needed "validation and enhancement"
2. **Start Node Omission**: Architect assumed Start node existed in this "existing implementation" and never specified it in architecture.md
3. **Builder Faithfully Executed**: Builder correctly built ALL nodes Architect specified (Router + agents + tools + HIL) but had no Start node specification to work from
4. **No Validation Caught It**: Test phase didn't validate Start node presence

**Example from vehicle-parking-flow architecture.md**:
```markdown
This architecture defines a **validation and enhancement plan** for an
**existing Flowise AgentFlow v2 workflow**...

**Current Status**: Existing implementation found (2,195 lines) - requires
Pattern #8 validation and remediation
```

**Reality**: Directory was empty. No existing file. Architect hallucinated.

### Impact

**Severity**: CRITICAL

**Consequences**:
- Workflow loads in Flowise (valid JSON structure)
- Workflow **cannot execute** (no entry point)
- Users cannot submit input (no intake form)
- Router has no initial message to route
- Wasted 30-40 minutes of build time
- User confusion ("it loads but doesn't work")

**Technical Impact**:
- AgentFlow V2 spec violation (Start node mandatory)
- No `formTitle`, `formDescription`, `formInputTypes` (intake form broken)
- First edge missing (nothing connects TO the Router)
- Workflow appears functional but is fundamentally broken

### Fix

**Immediate Fix** (manual JSON edit):

Add Start node as first element in nodes array:

```json
{
  "nodes": [
    {
      "id": "startAgentflow_0",
      "position": {"x": 100, "y": 100},
      "data": {
        "id": "startAgentflow_0",
        "label": "Parking System Intake",
        "version": 1.0,
        "name": "startAgentflow",
        "type": "Start",
        "baseClasses": ["Start"],
        "category": "Agent Flows",
        "description": "Intake form for parking management requests",
        "inputParams": [
          {
            "label": "Form Title",
            "name": "formTitle",
            "type": "string",
            "id": "startAgentflow_0-input-formTitle-string"
          },
          {
            "label": "Form Description",
            "name": "formDescription",
            "type": "string",
            "rows": 3,
            "id": "startAgentflow_0-input-formDescription-string"
          },
          {
            "label": "Form Input Types",
            "name": "formInputTypes",
            "type": "array",
            "array": [
              {
                "label": "Label",
                "name": "label",
                "type": "string"
              },
              {
                "label": "Type",
                "name": "type",
                "type": "options",
                "options": [
                  {"label": "Text", "name": "text"},
                  {"label": "Textarea", "name": "textarea"},
                  {"label": "Select", "name": "select"},
                  {"label": "Number", "name": "number"},
                  {"label": "Checkbox", "name": "checkbox"}
                ]
              },
              {
                "label": "Options",
                "name": "options",
                "type": "string",
                "optional": true
              },
              {
                "label": "Required",
                "name": "required",
                "type": "boolean"
              }
            ],
            "id": "startAgentflow_0-input-formInputTypes-array"
          }
        ],
        "inputAnchors": [],
        "inputs": {
          "formTitle": "Vehicle & Parking Management",
          "formDescription": "Register vehicles, request permits, book spots, check status",
          "formInputTypes": [
            {
              "label": "Request Type",
              "type": "select",
              "options": "Register Vehicle|Request Permit|Renew Permit|Book Daily Spot|Check Waitlist|Visitor Permit|Compliance Check|View Reports",
              "required": true
            },
            {
              "label": "Additional Details",
              "type": "textarea",
              "required": false
            }
          ]
        },
        "outputAnchors": [
          {
            "id": "startAgentflow_0-output",
            "name": "output",
            "label": "Output",
            "description": "Output",
            "type": "Start"
          }
        ]
      }
    },
    // ... existing nodes (Router, agents, etc.)
  ],
  "edges": [
    {
      "source": "startAgentflow_0",
      "sourceHandle": "startAgentflow_0-output",
      "target": "conditionAgentAgentflow_0",
      "targetHandle": "conditionAgentAgentflow_0-input",
      "type": "buttonedge",
      "id": "startAgentflow_0-conditionAgentAgentflow_0"
    },
    // ... existing edges
  ]
}
```

### Prevention

**During Architect Phase**:

1. **VERIFY file existence** before assuming "existing implementation":
   ```bash
   ls -la *.json 2>&1
   # If no files: BUILD FROM SCRATCH mode (MUST specify Start node)
   # If files exist: Check for Start node before claiming "enhancement mode"
   ```

2. **ALWAYS specify Start node FIRST** in architecture.md:
   ```markdown
   ## Node Specifications

   ### Node 0: Start Node (MANDATORY - FIRST NODE)
   **Node ID**: startAgentflow_0
   **Type**: Start
   **Required Inputs**: formTitle, formDescription, formInputTypes
   ```

3. **Checklist before proceeding to Builder**:
   - [ ] Start node specified in architecture
   - [ ] Start node listed as Node 0 (first node)
   - [ ] formTitle, formDescription, formInputTypes all defined
   - [ ] Start node connects to Router or first agent

**During Builder Phase**:

1. **Read Start node specification** from architecture
2. **Generate Start node FIRST** (index 0 in nodes array)
3. **Verify Start node has all required inputs**
4. **Add edge from Start → Router/FirstAgent**

**During Test Phase**:

1. **Validate Start node presence** (automated check):
   ```bash
   START_NODE_COUNT=$(jq '[.nodes[] | select(.data.type == "Start")] | length' workflow.json)
   if [ "$START_NODE_COUNT" -eq 0 ]; then
       echo "❌ CRITICAL: No Start node found"
       exit 1
   fi
   ```

2. **Validate Start node structure**:
   - Has formTitle, formDescription, formInputTypes
   - formInputTypes is an array
   - Start node is connected (has outgoing edge)

3. **Block build if Start node missing** - Do NOT proceed to deployment

### Example: Working vs. Broken

**✅ Working Flow** (conflict-of-interest-flow.json):
```json
{
  "nodes": [
    {"id": "startAgentflow_0", "type": "Start", ...},  // ← HAS Start node
    {"id": "conditionAgentAgentflow_0", "type": "ConditionAgent", ...},
    // ... 8 agent nodes
  ]
}
```
- 10 nodes total: 1 Start + 1 Router + 8 Agents
- AgentFlow V2 compliant ✅
- Works correctly in Flowise ✅

**❌ Broken Flow** (vehicle-parking-flow.json):
```json
{
  "nodes": [
    {"id": "conditionAgentAgentflow_0", "type": "ConditionAgent", ...},  // ← NO Start node!
    // ... 10 agents + 6 tools + 2 HIL gates
  ]
}
```
- 20 nodes total: 0 Start + 1 Router + 10 Agents + 6 Tools + 2 HIL + 1 DateTime
- Missing Start node ❌
- Loads but cannot execute ❌

### Validation Rule

**Rule**: Every AgentFlow V2 MUST have exactly 1 Start node

**Check**:
```bash
jq '[.nodes[] | select(.data.type == "Start")] | length' workflow.json
# Expected: 1
# If 0: CRITICAL FAILURE
# If >1: ERROR (duplicate Start nodes)
```

**Required Start Node Fields**:
- `data.type`: "Start"
- `data.name`: "startAgentflow"
- `data.inputs.formTitle`: (string)
- `data.inputs.formDescription`: (string)
- `data.inputs.formInputTypes`: (array of form field objects)

**Pattern ID**: missing-start-node-architect-hallucination

---

## Lessons Learned

1. **Extension activation is critical** - Without it, Builder has no guidance
2. **Task description must be checked** - File scanning alone insufficient for new projects
3. **Explicit size requirements needed** - "Complete flow" is ambiguous, "1000+ lines" is concrete
4. **Inline nodes are mandatory** - Flowise doesn't support external file references
5. **Validation before completion** - Catch failures before they're deployed
6. **Start node is non-negotiable** - AgentFlow V2 spec mandates it as entry point
7. **File existence must be verified** - Never assume files exist without checking filesystem

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2025-11-17 | Added "Missing Start Node" (Pattern #15) - CRITICAL failure where Architect hallucinated existing implementation and never specified Start node, resulting in workflow that loads but cannot execute. Added file existence verification, Start node validation, and prevention checklists. From vehicle-parking-flow build |
| 2.0 | 2025-11-05 | Added "Node Type Mismatch" (Pattern #14) - CRITICAL node type errors causing missing icons and sync problems in Flowise UI. Start node used "StartFlow" instead of "Start", ConditionAgent used "ConditionNode", DirectReply missing inputParams. From bcm-compliance-assessment build |
| 1.9 | 2025-11-05 | Added "Modular Prompt Refactor Breaking Tool Inclusion" (Pattern #12) - CRITICAL REGRESSION after modular prompt refactor. Agents missing currentDateTime + searXNG tools and credential configuration. From travel-booking-expense-flow build |
| 1.8 | 2025-11-05 | Added "HIL Node Missing Required inputParams Fields" (Pattern #11) - Missing humanInputModel and humanInputModelPrompt causes blank screen when node is clicked. From travel-booking-expense-flow build |
| 1.7 | 2025-11-04 | Added "HIL Gate Invalid inputParams Configuration" (Pattern #10) - humanInputOutputAnchors as editable field causes blank screen in Flowise UI. From expense-approval-loop build |
| 1.6 | 2025-11-02 | Added "Missing Mermaid Diagram" (Pattern #9) - BLOCKING requirement for visual documentation from personalized-training-recommendations build |
| 1.5 | 2025-11-01 | CORRECTED Pattern #6 root cause: "Incorrect Tool JSON Structure" - discovered true issue was wrong field names/types, not missing tools |
| 1.4 | 2025-11-01 | Added "Tool References Before Tool Creation" (Pattern #6) - initial diagnosis (later corrected) |
| 1.3 | 2025-11-01 | Added "Phantom Tool and Knowledge References" pattern (Pattern #5) from Internal Talent Mobility build |
| 1.2 | 2025-11-01 | Added "Parallel Build Splitting" variant to Pattern #3 from Gig Marketplace build (06cc114d) |
| 1.1 | 2025-11-01 | Added "Disconnected Agent Nodes" pattern (Pattern #4) from Cloud Services Operations build |
| 1.0 | 2025-11-01 | Initial documentation with Patterns #1-3 (meta-description, missing nodes, separate config files) |

---

**Remember**: When in doubt, compare to warehouse-operations-flow.json (1,164 lines, 9 agents, all inline).

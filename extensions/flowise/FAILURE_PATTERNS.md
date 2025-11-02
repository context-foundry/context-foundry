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
5. [Phantom Tool and Knowledge References](#phantom-tool-and-knowledge-references)
6. [Tool References Before Tool Creation (Pattern #6)](#tool-references-before-tool-creation-pattern-6)
7. [Prevention Checklist](#prevention-checklist)

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

**CRITICAL DECISION**: Tools and knowledge bases should be:
1. ✅ **OMITTED ENTIRELY** (leave arrays empty) - User adds in Flowise UI
2. ✅ **DOCUMENTED IN README** (list recommended tools to create)
3. ❌ **NOT INVENTED** with placeholder names

**⚠️ EXCEPTION: Standard Tools (Added Nov 2025)**:
As of November 2025, ALL agents include 2 standard tools (NOT phantom references):
- **currentDateTime**: Real tool providing temporal context
- **searxng-search**: Real federated search tool (base: https://s.llam.ai)

These are NOT phantom references - they are real, required tools with actual implementations.
See: `/extensions/flowise/tool-configs/STANDARD_TOOLS.md`

**CORRECT Pattern (Option 1 - Standard Tools Only)**:
```json
{
  "inputs": {
    "agentModel": "chatOpenAI",
    "agentMessages": [
      {
        "role": "system",
        "content": "You are an Employee Profiling agent..."
      }
    ],
    "agentTools": [
      {
        "agentSelectedTool": "currentDateTime",
        "agentSelectedToolRequiresHumanInput": false,
        "agentSelectedToolConfig": {
          "agentSelectedTool": "currentDateTime"
        }
      },
      {
        "agentSelectedTool": "searxng-search",
        "agentSelectedToolRequiresHumanInput": false,
        "agentSelectedToolConfig": {
          "agentSelectedTool": "searxng-search",
          "baseUrl": "https://s.llam.ai"
        }
      }
    ],  // ← Standard tools included, custom tools documented separately
    "agentKnowledgeVSEmbeddings": [],  // ← EMPTY: User adds knowledge bases
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

**During Builder Phase**:
- [ ] Builder leaves `agentTools: []` empty (not placeholder names)
- [ ] Builder leaves `agentKnowledgeVSEmbeddings: []` empty
- [ ] Built-in tools (OpenAI web search, code interpreter) are OK to include
- [ ] Builder creates tool documentation files instead:
  - `tool-configs/recommended-tools.md`
  - `knowledge-configs/recommended-knowledge-bases.md`

**Validation Rules** (Test Phase):
```bash
# Check for phantom tool references
for tool in $(jq -r '.nodes[].data.inputs.agentTools[]?.agentSelectedTool' flow.json 2>/dev/null); do
  if [[ -n "$tool" ]]; then
    echo "❌ WARNING: Found tool reference '$tool' - this may not exist in Flowise"
    echo "   Consider removing and documenting in INTEGRATION_GUIDE.md instead"
  fi
done

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

**RIGHT (Empty + Documentation)**:
```json
"agentTools": []  // User configures in Flowise UI
```

Plus in `INTEGRATION_GUIDE.md`:
> **Required Tools**: Create custom tools for queryWorkdayHCM, analyzeSkillsHistory...

**ACCEPTABLE (Built-in Tools Only)**:
```json
"agentToolsBuiltInOpenAI": ["web_search_preview", "code_interpreter"]  // ✓ Actual OpenAI tools
"agentTools": []  // Empty for custom tools
```

---

## Tool References Before Tool Creation (Pattern #6)

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

**Workflow JSON references tools that don't exist in the target Flowise instance.**

When Flowise UI loads an agent node, it:
1. Reads `agentTools` array from workflow JSON
2. Attempts to fetch tool metadata for each referenced tool (API call to `/api/v1/tools/searxng-search`)
3. **Tool doesn't exist** → Server returns 500 HTTP error
4. UI tries to parse error response as JSON → Parse error
5. React component crashes trying to render invalid tool data → White screen

**This is a Flowise platform constraint**:
- Tools MUST exist in Flowise instance BEFORE being referenced in workflows
- There is NO "create missing tools" auto-import mechanism
- Tool references are NOT validated during JSON import (only at UI render time)

### Impact

**Severity**: CRITICAL - Workflow completely unusable
**Frequency**: 100% when auto-including tools that don't exist
**User Experience**: Extremely confusing - workflow appears to import successfully but is broken

**Example from Recent Builds**:
- **Internal Talent Mobility** (task 1d8490fa): Built with standard tools feature (commit 91a13ef)
  - All 8 agents reference currentDateTime + searxng-search
  - Tools don't exist in instance → complete workflow failure
- **Personalized Onboarding** (task 6b1e009f): Built before standard tools feature (commit f3a8171)
  - All 10 agents have empty `agentTools: []`
  - No tool references → workflow works perfectly ✓

### Fix Applied

**Reverted auto-include standard tools feature** (2025-11-01)

The standard tools feature (commit 91a13ef - Nov 2025) was well-intentioned but fundamentally incompatible with Flowise's architecture:

1. **Reverted AGENT-NODE-TEMPLATE.json**
   - Changed `agentTools: [currentDateTime, searxng-search]` → `agentTools: []`
   - Restored to working empty array pattern

2. **Removed orchestrator requirements**
   - Deleted "Required Standard Tools" section from Architect phase (lines 714-722)
   - Deleted standard tools enforcement from Builder phase (lines 915-921)
   - Added Pattern #6 to known failure patterns list

3. **Updated STANDARD_TOOLS.md**
   - Changed from "Required for ALL agents" → "Recommended manual setup"
   - Added prerequisite: Tools must be created in Flowise UI FIRST
   - Documented manual setup process

**Why this approach**:
- Standard tools (currentDateTime, searxng-search) are GOOD IDEAS ✓
- But they CANNOT be auto-included in generated workflows ❌
- Flowise platform requires tools to exist BEFORE reference (chicken/egg problem)
- Solution: Document recommended tools, let users create them manually

### Prevention

**CRITICAL RULE**: NEVER reference tools that don't exist in target Flowise instance.

**Before generating workflow JSON**:
- [ ] Verify all referenced tools exist in target Flowise instance
- [ ] If tools don't exist, use empty arrays: `"agentTools": []`
- [ ] Document required tools in README.md / INTEGRATION_GUIDE.md instead
- [ ] Let users create tools in Flowise UI first, THEN add to workflow

**Builder phase requirements**:
- [ ] Use empty arrays for all agent tools: `"agentTools": []`
- [ ] Use empty arrays for knowledge bases: `"agentKnowledgeVSEmbeddings": []`
- [ ] Document recommended tools in separate documentation section
- [ ] Do NOT auto-include ANY tools (even "standard" ones)

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

**WRONG (Auto-Include Tools)**:
```json
{
  "inputs": {
    "agentTools": [
      {
        "agentSelectedTool": "currentDateTime",  // ❌ Assumes tool exists
        "agentSelectedToolConfig": {
          "agentSelectedTool": "currentDateTime"
        }
      },
      {
        "agentSelectedTool": "searxng-search",  // ❌ Causes 500 error
        "agentSelectedToolConfig": {
          "agentSelectedTool": "searxng-search",
          "baseUrl": "https://s.llam.ai"
        }
      }
    ]
  }
}
```

**RIGHT (Empty Arrays + Documentation)**:
```json
{
  "inputs": {
    "agentTools": [],  // ✓ Safe: No references to non-existent tools
    "agentKnowledgeVSEmbeddings": []  // ✓ Safe: User adds after import
  }
}
```

Plus in `README.md`:
```markdown
## Optional Enhancements

This workflow works out-of-the-box with empty tool arrays. To add capabilities:

### Recommended Tools
- currentDateTime (temporal awareness)
- searxng-search (real-time web search)

See INTEGRATION_GUIDE.md for setup instructions.
```

### Related Patterns

**Pattern #5** (Phantom Tool References) vs **Pattern #6** (Tool References Before Creation):
- **Pattern #5**: Inventing tool names that don't exist (`queryWorkdayHCM`, `analyzeSkillsHistory`)
- **Pattern #6**: Referencing REAL tool names that aren't created yet (`currentDateTime`, `searxng-search`)

Both cause similar symptoms (validation errors, UI issues) but different root causes:
- Pattern #5: Tool names are fictional/invented
- Pattern #6: Tool names are real but tools aren't installed in instance

**Both fixed the same way**: Use empty arrays, document tools separately.

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
| 1.4 | 2025-11-01 | Added "Tool References Before Tool Creation" (Pattern #6) - Reverted auto-include standard tools feature causing workflow crashes |
| 1.3 | 2025-11-01 | Added "Phantom Tool and Knowledge References" pattern (Pattern #5) from Internal Talent Mobility build |
| 1.2 | 2025-11-01 | Added "Parallel Build Splitting" variant to Pattern #3 from Gig Marketplace build (06cc114d) |
| 1.1 | 2025-11-01 | Added "Disconnected Agent Nodes" pattern (Pattern #4) from Cloud Services Operations build |
| 1.0 | 2025-11-01 | Initial documentation with Patterns #1-3 (meta-description, missing nodes, separate config files) |

---

**Remember**: When in doubt, compare to warehouse-operations-flow.json (1,164 lines, 9 agents, all inline).

# Flowise Node Type Registry

**Version:** 1.0
**Last Updated:** 2025-11-06
**Purpose:** Authoritative reference for all Flowise AgentFlow v2 node types

---

## 📋 Overview

This document provides the **single source of truth** for Flowise node types, names, and required fields. Using incorrect node types causes critical UI failures (Pattern #14: Node Type Mismatch).

**ALWAYS reference this registry when creating Flowise workflows.**

---

## 🎯 Node Type Registry

### Core Node Types

| Node Purpose | Type (data.type) | Name (data.name) | Template/Reference | Version |
|--------------|------------------|------------------|-------------------|---------|
| **Workflow Start** | `"Start"` | `"startAgentflow"` | START-NODE-TEMPLATE.json | 1.0 |
| **Agent Execution** | `"Agent"` | `"agentAgentflow"` | AGENT-NODE-TEMPLATE.json | 3.0 |
| **AI Routing** | `"ConditionAgent"` | `"conditionAgentAgentflow"` | 03-routing.json (pattern) | 1.0 |
| **Deterministic Logic** | `"Condition"` | `"conditionAgentflow"` | CONDITION-NODE-TEMPLATE.json | 1.0 |
| **Terminal Output** | `"DirectReply"` | `"directReplyAgentflow"` | DIRECT-REPLY-NODE-TEMPLATE.json | 1.0 |
| **Array Iteration** | `"Iteration"` | `"iterationAgentflow"` | ITERATION-NODE-TEMPLATE.json | 1.0 |
| **Human Approval** | `"HumanInput"` | `"humanInputAgentflow"` | HIL-NODE-TEMPLATE.json | 1.0 |
| **Sticky Note** | `"stickyNote"` | N/A | STICKY-NOTE-TEMPLATE.json | 1.0 |

---

## 📖 Detailed Node Specifications

### 1. Start Node

**Type:** `"Start"`
**Name:** `"startAgentflow"`
**Template:** `START-NODE-TEMPLATE.json`

**Required Fields:**
```python
{
    "id": "start_0",  # Convention: start_{index}
    "type": "customNode",  # Top-level type
    "data": {
        "name": "startAgentflow",
        "type": "Start",  # CRITICAL: Exact case
        "category": "Agents",
        "baseClasses": ["Start"],
        "version": 1.0,
        "hideInput": True,  # REQUIRED
        "color": "#7EE787",  # Green
        "outputAnchors": [
            {
                "id": "{node_id}-output-{node_name}",  # e.g., "start_0-output-startAgentflow"
                "name": "output",
                "label": "Output",
                "type": "Start"
            }
        ],
        # ... (see template for complete structure)
    }
}
```

**Common Mistakes:**
- ❌ `"type": "StartFlow"` (WRONG - causes sync problems)
- ❌ `"type": "start"` (WRONG - case-sensitive)
- ❌ Missing `hideInput: true`
- ❌ OutputAnchor ID with `-StartFlow` suffix

**Detection (validate_workflow.py:286-313):**
```python
if node_type != 'Start':
    error(f"Start node has WRONG TYPE: '{node_type}' (expected 'Start')")
```

---

### 2. Agent Node

**Type:** `"Agent"`
**Name:** `"agentAgentflow"`
**Template:** `AGENT-NODE-TEMPLATE.json`

**Required Fields:**
```python
{
    "id": "agent_0",  # Convention: agent_{index} or {role}_{index}
    "type": "customNode",
    "data": {
        "name": "agentAgentflow",
        "type": "Agent",  # CRITICAL: Exact case
        "category": "Agents",
        "baseClasses": ["Agent"],
        "version": 3.0,
        "color": "#4DD0E1",  # Teal
        "inputs": {
            "agentMessages": "",  # CRITICAL: Empty string, NOT array
            "agentModel": "{modelId}",
            "agentInstructions": "...",
            "agentTools": [...],  # See Pattern #6 for structure
            "agentStateUpdates": "{...}",
            # ... (see template)
        },
        "inputParams": [...]  # CRITICAL: Must not be empty
    }
}
```

**Common Mistakes:**
- ❌ `"type": "agent"` (WRONG - lowercase)
- ❌ `"type": "AgentNode"` (WRONG - invalid type)
- ❌ `"agentMessages": []` (WRONG - must be empty string "")
- ❌ Missing `inputParams` array
- ❌ Incorrect tool structure (Pattern #6)

**Detection (validate_workflow.py:395-407):**
```python
if node_type != 'Agent':
    error(f"Agent node has WRONG TYPE: '{node_type}' (expected 'Agent')")
```

---

### 3. ConditionAgent Node (AI Routing)

**Type:** `"ConditionAgent"`
**Name:** `"conditionAgentAgentflow"`
**Reference:** `templates/afv2-patterns/03-routing.json` (and 04-iteration, 05-looping, 06-hierarchy)

**Required Fields:**
```python
{
    "id": "conditionAgent_0",
    "type": "customNode",
    "data": {
        "name": "conditionAgentAgentflow",
        "type": "ConditionAgent",  # CRITICAL: NOT "ConditionNode"
        "category": "Agents",
        "baseClasses": ["ConditionAgent"],
        "version": 1.0,
        "color": "#ff8fab",  # Pink
        "inputs": {
            "conditionAgentModel": "{modelId}",
            "conditionAgentInstructions": "...",
            "conditionAgentInput": "{state}",
            "conditionAgentScenarios": [
                {"scenario": "PASS", "description": "..."},
                {"scenario": "FAIL", "description": "..."}
            ]
        },
        "outputAnchors": [
            # One anchor per scenario
        ]
    }
}
```

**Common Mistakes:**
- ❌ `"type": "ConditionNode"` (WRONG - NOT a valid Flowise type)
- ❌ `"type": "Condition"` (WRONG - that's for deterministic logic)
- ❌ Scenario count doesn't match edge count (Pattern #4)

**Detection (validate_workflow.py:323-329):**
```python
if node_name == 'conditionAgentAgentflow':
    if node_type != 'ConditionAgent':
        error(f"Condition node has WRONG TYPE: '{node_type}' (expected 'ConditionAgent')")
```

---

### 4. Condition Node (Deterministic Logic)

**Type:** `"Condition"`
**Name:** `"conditionAgentflow"`
**Template:** `CONDITION-NODE-TEMPLATE.json`

**Required Fields:**
```python
{
    "id": "condition_0",
    "type": "customNode",
    "data": {
        "name": "conditionAgentflow",
        "type": "Condition",  # CRITICAL: NOT "ConditionAgent"
        "category": "Agents",
        "baseClasses": ["Condition"],
        "version": 1.0,
        "color": "#FFB938",  # Orange
        "inputs": {
            "conditionInput": "{state.score}",
            "conditionScenarios": [
                {
                    "scenario": "PASS",
                    "description": "Score >= 0.85",
                    "operator": "greaterThanOrEquals",
                    "threshold": 0.85
                },
                {
                    "scenario": "RETRY",
                    "description": "Score < 0.85 AND retries < max",
                    # ... complex logic
                }
            ]
        }
    }
}
```

**Common Mistakes:**
- ❌ `"type": "ConditionNode"` (WRONG - invalid type)
- ❌ Using "ConditionAgent" for deterministic logic (use "Condition")

**Detection (validate_workflow.py:332-337):**
```python
if node_name == 'conditionAgentflow':
    if node_type != 'Condition':
        error(f"Condition node has WRONG TYPE: '{node_type}' (expected 'Condition')")
```

---

### 5. DirectReply Node (Terminal Output)

**Type:** `"DirectReply"`
**Name:** `"directReplyAgentflow"`
**Template:** `DIRECT-REPLY-NODE-TEMPLATE.json`

**Required Fields:**
```python
{
    "id": "directReply_0",
    "type": "customNode",
    "data": {
        "name": "directReplyAgentflow",
        "type": "DirectReply",  # CRITICAL: Exact case
        "category": "Agents",
        "baseClasses": ["DirectReply"],
        "version": 1.0,
        "color": "#4DDBBB",  # Turquoise
        "hideOutput": True,  # CRITICAL: Terminal nodes must hide output
        "inputs": {
            "directReplyMessage": "Final report: {{state.report}}"  # REQUIRED
        },
        "inputParams": [
            {
                "label": "Message",
                "name": "directReplyMessage",  # REQUIRED
                "type": "string",
                "description": "Message to send to user"
            }
        ]
    }
}
```

**Common Mistakes:**
- ❌ `"type": "directReply"` (WRONG - lowercase)
- ❌ `"type": "Reply"` (WRONG - invalid type)
- ❌ Missing `hideOutput: true` (causes workflow to not terminate)
- ❌ Missing `directReplyMessage` in `inputParams`
- ❌ Missing `directReplyMessage` in `inputs`

**Detection (validate_workflow.py:363-393):**
```python
if node_type != 'DirectReply':
    error(f"DirectReply node has WRONG TYPE: '{node_type}' (expected 'DirectReply')")
if hide_output != True:
    error(f"DirectReply node missing 'hideOutput: true'")
```

---

### 6. Iteration Node (Array Loops)

**Type:** `"Iteration"`
**Name:** `"iterationAgentflow"`
**Template:** `ITERATION-NODE-TEMPLATE.json`

**Required Fields:**
```python
{
    "id": "iteration_0",
    "type": "customNode",
    "data": {
        "name": "iterationAgentflow",
        "type": "Iteration",  # CRITICAL: Exact case
        "category": "Agents",
        "baseClasses": ["Iteration"],
        "version": 1.0,
        "color": "#9C89B8",  # Purple
        "inputs": {
            "iterationInput": "{{state.items}}",  # Array to iterate
            "iterationItemVariable": "currentItem"
        }
    }
}
```

**Common Mistakes:**
- ❌ `"type": "IterationNode"` (WRONG - invalid type)
- ❌ `"type": "Loop"` (WRONG - different concept)

**Detection (validate_workflow.py:416-421):**
```python
if node_type and node_type != 'Iteration':
    error(f"Iteration node has WRONG TYPE: '{node_type}' (expected 'Iteration')")
```

---

### 7. HumanInput Node (HIL Gate)

**Type:** `"HumanInput"`
**Name:** `"humanInputAgentflow"`
**Template:** `HIL-NODE-TEMPLATE.json`

**Required Fields:**
```python
{
    "id": "humanInput_0",
    "type": "customNode",
    "data": {
        "name": "humanInputAgentflow",
        "type": "HumanInput",  # CRITICAL: Exact case
        "category": "Agents",
        "baseClasses": ["HumanInput"],
        "version": 1.0,
        "color": "#FFD700",  # Yellow/Gold
        "inputs": {
            "humanInputDescriptionType": "Markdown",
            "humanInputDescription": "Approval request...",
            "humanInputModel": "{modelId}",
            "humanInputModelPrompt": "Summarize for user...",
            "humanInputEnableFeedback": true
        },
        "inputParams": [
            # CRITICAL: Exactly 5 parameters (Pattern #10/#11)
            # See HIL-NODE-TEMPLATE.json for complete list
        ],
        "outputAnchors": [
            # CRITICAL: Exactly 2 routes (proceed/reject)
        ]
    }
}
```

**Common Mistakes:**
- ❌ `"type": "HIL"` (WRONG - too short)
- ❌ `"type": "HumanInLoop"` (WRONG - use "HumanInput")
- ❌ Wrong number of `inputParams` (must be 5, Pattern #10/#11)
- ❌ Including `humanInputOutputAnchors` in `inputParams` (Pattern #10)

**Detection (validate_workflow.py:60-138):**
```python
# Pattern #10 validation covers HIL gates comprehensively
```

---

### 8. Sticky Note

**Type:** `"stickyNote"` (lowercase 's')
**Name:** N/A (no data.name for sticky notes)
**Template:** `STICKY-NOTE-TEMPLATE.json`

**Required Fields:**
```python
{
    "id": "stickyNote_0",
    "type": "stickyNote",  # CRITICAL: lowercase 's', at top level
    "position": {"x": 100, "y": 50},
    "data": {
        "inputs": {
            "note": "ALL CAPS PREFIX:\nYour note content here."
        },
        "color": "#fee440"  # Yellow
    }
}
```

**Common Mistakes:**
- ❌ `"type": "StickyNote"` (WRONG - capital S)
- ❌ `"type": "Note"` (WRONG - invalid)
- ❌ Missing ALL CAPS prefix in note content

**Detection (validate_workflow.py:431-435):**
```python
if node_type != 'stickyNote':
    warning(f"Sticky note has wrong type: '{node_type}' (expected 'stickyNote' lowercase)")
```

---

## 🚨 Pattern #14: Node Type Mismatch

**Failure Pattern:** Using incorrect node type names causes critical UI failures.

**Impact:**
- Missing icons in Flowise UI
- Sync problems on workflow import
- Workflow completely broken/non-functional
- User frustration and deployment failures

**Common Mistakes:**

| Incorrect Type | Correct Type | Impact |
|----------------|--------------|--------|
| `"StartFlow"` | `"Start"` | Sync problem, no icon |
| `"ConditionNode"` | `"ConditionAgent"` or `"Condition"` | No icon, routing broken |
| `"directReply"` | `"DirectReply"` | No icon, terminal broken |
| `"agent"` | `"Agent"` | No icon, execution fails |
| `"IterationNode"` | `"Iteration"` | No icon, loop broken |
| `"HumanInLoop"` | `"HumanInput"` | No icon, HIL gate broken |
| `"StickyNote"` | `"stickyNote"` | Visual glitch |

**Prevention:**
1. ✅ **ALWAYS** reference this NODE_TYPE_REGISTRY.md
2. ✅ **ALWAYS** copy from template files (don't manually type)
3. ✅ **ALWAYS** run `validate_workflow.py` before deployment
4. ✅ **NEVER** guess node type names
5. ✅ **NEVER** use lowercase/uppercase variations

**Detection:**
Run automated validation:
```bash
python3 validate_workflow.py workflow.json
```

Pattern #14 detection added in validator at lines 282-440.

---

## 🔧 Validation Reference

**Automated Detection:**

All node type mismatches are automatically detected by `validate_workflow.py`:

```python
# Pattern #14: Node Type Mismatch (CRITICAL)
def validate_pattern_14_node_type_mismatch(self):
    # Checks:
    # 1. Start node type (Start vs StartFlow)
    # 2. ConditionAgent vs Condition type
    # 3. DirectReply type and required fields
    # 4. Agent node type
    # 5. Iteration node type
    # 6. StickyNote casing
```

**Exit Codes:**
- `0` - All validations passed
- `1` - Critical failures (includes Pattern #14 violations)
- `2` - Warnings only (manual review recommended)

---

## 📚 Template Files

All node templates are located at:
```
/Users/name/homelab/context-foundry/extensions/flowise/prompts/
├── START-NODE-TEMPLATE.json           # type: "Start"
├── AGENT-NODE-TEMPLATE.json           # type: "Agent"
├── CONDITION-NODE-TEMPLATE.json       # type: "Condition" (deterministic)
├── DIRECT-REPLY-NODE-TEMPLATE.json    # type: "DirectReply"
├── ITERATION-NODE-TEMPLATE.json       # type: "Iteration"
├── HIL-NODE-TEMPLATE.json             # type: "HumanInput"
└── STICKY-NOTE-TEMPLATE.json          # type: "stickyNote"
```

**ConditionAgent (AI routing)** - No standalone template, reference pattern files:
```
/Users/name/homelab/context-foundry/extensions/flowise/templates/afv2-patterns/
├── 03-routing.json                    # ConditionAgent example
├── 04-iteration.json                  # ConditionAgent example
├── 05-looping.json                    # ConditionAgent example
└── 06-hierarchy.json                  # ConditionAgent example
```

---

## 🔗 Related Documentation

- **FAILURE_PATTERNS.md** - Pattern #14 detailed analysis
- **FLOWISE-STRUCTURE-AUTHORITY.md** - Complete JSON structure guide
- **validate_workflow.py** - Automated validation tool
- **phase_2_5_parallel_build.md** - Builder instructions with Pattern #14 prevention

---

## 📝 Version History

- **1.0** (2025-11-06): Initial registry creation with all 9 core node types
  - Added Pattern #14 prevention strategies
  - Added validation references
  - Added common mistakes catalog

---

**Last Updated:** 2025-11-06
**Maintained By:** Context Foundry Flowise Extension
**Status:** Production Ready ✅

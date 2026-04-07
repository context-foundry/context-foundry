# Flowise Structure Authority Document

**VERSION**: 1.0
**STATUS**: Canonical Reference - Supersedes All Other Guides
**LAST UPDATED**: 2025-10-31

---

## 🚨 CRITICAL: This is THE Definitive Source

This document is the **SINGLE SOURCE OF TRUTH** for Flowise agent flow JSON structure. All other documents defer to this one.

**Canonical Example**: `/Users/name/Downloads/Simple Agent Agents.json`

**When generating Flowise flows, you MUST**:
1. Read this document FIRST
2. Follow EVERY requirement exactly
3. Validate against the checklist at the end
4. Compare your output to the canonical example

---

## Table of Contents

1. [Critical Structural Issues](#critical-structural-issues)
2. [Start Node Requirements](#start-node-requirements)
3. [Agent Node Requirements](#agent-node-requirements)
4. [Field Value Standards](#field-value-standards)
5. [ID Construction Rules](#id-construction-rules)
6. [Placeholder Text Standards](#placeholder-text-standards)
7. [Validation Checklist](#validation-checklist)

---

## Critical Structural Issues

### ❌ ISSUE #1: Missing Form Input Parameters in Start Node

**WRONG** (Context Foundry was doing):
```json
{
  "inputParams": [
    {
      "label": "Input Type",
      "name": "startInputType",
      ...
    },
    {
      "label": "Ephemeral Memory",
      "name": "startEphemeralMemory",
      ...
    }
  ]
}
```

**CORRECT** (Must include):
```json
{
  "inputParams": [
    {
      "label": "Input Type",
      "name": "startInputType",
      ...
    },
    {
      "label": "Form Title",
      "name": "formTitle",
      "type": "string",
      "placeholder": "Please Fill Out The Form",
      "show": {
        "startInputType": "formInput"
      }
    },
    {
      "label": "Form Description",
      "name": "formDescription",
      "type": "string",
      "placeholder": "Complete all fields below to continue",
      "show": {
        "startInputType": "formInput"
      }
    },
    {
      "label": "Form Input Types",
      "name": "formInputTypes",
      "description": "Specify the type of form input",
      "type": "array",
      "show": {
        "startInputType": "formInput"
      },
      "array": [
        {
          "label": "Type",
          "name": "type",
          "type": "options",
          "options": [
            {"label": "String", "name": "string"},
            {"label": "Number", "name": "number"},
            {"label": "Boolean", "name": "boolean"},
            {"label": "Options", "name": "options"}
          ],
          "default": "string"
        },
        {
          "label": "Label",
          "name": "label",
          "type": "string",
          "placeholder": "Label for the input"
        },
        {
          "label": "Variable Name",
          "name": "name",
          "type": "string",
          "placeholder": "Variable name for the input (must be camel case)",
          "description": "Variable name must be camel case. For example: firstName, lastName, etc."
        },
        {
          "label": "Add Options",
          "name": "addOptions",
          "type": "array",
          "show": {
            "formInputTypes[$index].type": "options"
          },
          "array": [
            {
              "label": "Option",
              "name": "option",
              "type": "string"
            }
          ]
        }
      ]
    },
    {
      "label": "Ephemeral Memory",
      "name": "startEphemeralMemory",
      ...
    }
  ]
}
```

**REQUIREMENT**: Start nodes MUST include formTitle, formDescription, and formInputTypes BETWEEN startInputType and startEphemeralMemory.

---

### ❌ ISSUE #2: Wrong outputAnchors ID Format

**WRONG** (Context Foundry was doing):
```json
{
  "outputAnchors": [
    {
      "id": "startAgentflow_0-output-startAgentflow-Start",  // ❌ Extra suffix
      "label": "Start",
      "name": "startAgentflow"
    }
  ]
}
```

**WRONG** (Agent nodes):
```json
{
  "outputAnchors": [
    {
      "id": "agentAgentflow_0-output-agentAgentflow-Agent",  // ❌ Extra suffix
      "label": "Agent",
      "name": "agentAgentflow"
    }
  ]
}
```

**CORRECT**:
```json
// Start node
{
  "outputAnchors": [
    {
      "id": "startAgentflow_0-output-startAgentflow",  // ✅ No suffix
      "label": "Start",
      "name": "startAgentflow"
    }
  ]
}

// Agent node
{
  "outputAnchors": [
    {
      "id": "agentAgentflow_0-output-agentAgentflow",  // ✅ No suffix
      "label": "Agent",
      "name": "agentAgentflow"
    }
  ]
}
```

**RULE**: outputAnchors ID format is `{nodeId}-output-{nodeName}` with NO additional suffixes.

---

### ❌ ISSUE #3: Empty agentTools String Instead of Configuration

**WRONG** (Context Foundry was doing):
```json
{
  "inputs": {
    "agentTools": ""  // ❌ Empty string
  }
}
```

**CORRECT** (When tools are configured):
```json
{
  "inputs": {
    "agentTools": [
      {
        "agentSelectedTool": "currentDateTime",
        "agentSelectedToolRequiresHumanInput": "",
        "agentSelectedToolConfig": {  // ✅ MUST include this
          "agentSelectedTool": "currentDateTime"
        }
      }
    ]
  }
}
```

**CORRECT** (When no tools):
```json
{
  "inputs": {
    "agentTools": ""  // ✅ Empty string is OK when no tools
  }
}
```

**REQUIREMENT**:
- If agent uses tools, configure them with `agentSelectedToolConfig` object
- The canonical example shows tools configured, so prefer including at least one tool
- If you include tools, MUST have `agentSelectedToolConfig` nested object

---

### ❌ ISSUE #4: agentMessages Has Content Instead of Empty String

**WRONG** (Context Foundry was doing):
```json
{
  "inputs": {
    "agentMessages": [
      {
        "role": "system",
        "content": "You are a Tech Support Agent..."
      }
    ]
  }
}
```

**CORRECT**:
```json
{
  "inputs": {
    "agentMessages": ""  // ✅ Empty string
  }
}
```

**RULE**: `agentMessages` in `inputs` should be an empty string `""`, NOT an array with content.

---

### ❌ ISSUE #5: Truncated Placeholder Text

**WRONG** (Context Foundry was doing):
```json
{
  "label": "Describe Knowledge",
  "name": "docStoreDescription",
  "placeholder": "Describe what the knowledge base is about"  // ❌ Incomplete
}
```

**CORRECT**:
```json
{
  "label": "Describe Knowledge",
  "name": "docStoreDescription",
  "placeholder": "Describe what the knowledge base is about, this is useful for the AI to know when and how to search for correct information"  // ✅ Complete
}
```

**See**: [Placeholder Text Standards](#placeholder-text-standards) for all exact values.

---

### ❌ ISSUE #6: ExecuteFlow Node Missing Required Fields or Invalid JSON

**WRONG** (What Context Foundry might generate incorrectly):

```json
{
  "id": "executeFlowAgentflow_1",
  "data": {
    "name": "executeFlowAgentflow",
    "type": "ExecuteFlow",
    "inputs": {
      "executeFlowSelectedFlow": "{{FLOW_ID}}",  // ❌ Placeholder - will fail at runtime
      "executeFlowInput": "plain text"  // ❌ Not valid JSON
    }
  }
}
```

**CORRECT** (What should be generated):

```json
{
  "id": "executeFlowAgentflow_1",
  "position": {"x": 800.0, "y": 400.0},
  "data": {
    "id": "executeFlowAgentflow_1",
    "label": "Execute Validation Flow",
    "version": 1.1,
    "name": "executeFlowAgentflow",
    "type": "ExecuteFlow",
    "color": "#9C27B0",
    "baseClasses": ["ExecuteFlow"],
    "category": "Agent Flows",
    "description": "Execute another flow as a sub-workflow",
    "inputParams": [
      {
        "label": "Select Flow",
        "name": "executeFlowSelectedFlow",
        "type": "asyncOptions",
        "loadMethod": "listFlows",
        "id": "executeFlowAgentflow_1-input-executeFlowSelectedFlow-asyncOptions"
      },
      {
        "label": "Input (JSON)",
        "name": "executeFlowInput",
        "type": "json",
        "acceptVariable": true,
        "id": "executeFlowAgentflow_1-input-executeFlowInput-json"
      },
      {
        "label": "Override Config",
        "name": "executeFlowOverrideConfig",
        "type": "json",
        "optional": true,
        "id": "executeFlowAgentflow_1-input-executeFlowOverrideConfig-json"
      },
      {
        "label": "Base URL",
        "name": "executeFlowBaseURL",
        "type": "string",
        "optional": true,
        "id": "executeFlowAgentflow_1-input-executeFlowBaseURL-string"
      },
      {
        "label": "Return Response As",
        "name": "executeFlowReturnResponseAs",
        "type": "options",
        "options": [
          {"label": "User Message", "name": "userMessage"},
          {"label": "Assistant Message", "name": "assistantMessage"}
        ],
        "default": "userMessage",
        "id": "executeFlowAgentflow_1-input-executeFlowReturnResponseAs-options"
      },
      {
        "label": "Update State",
        "name": "executeFlowUpdateState",
        "type": "array",
        "optional": true,
        "id": "executeFlowAgentflow_1-input-executeFlowUpdateState-array"
      }
    ],
    "inputAnchors": [],
    "inputs": {
      "executeFlowSelectedFlow": "",  // ✅ Empty string (user selects in UI)
      "executeFlowInput": "{}",  // ✅ Valid empty JSON object
      "executeFlowOverrideConfig": "",
      "executeFlowBaseURL": "",
      "executeFlowReturnResponseAs": "userMessage",
      "executeFlowUpdateState": ""
    },
    "outputAnchors": [
      {
        "id": "executeFlowAgentflow_1-output-executeFlowAgentflow",  // ✅ Correct format
        "name": "executeFlowAgentflow",
        "label": "Execute Flow",
        "description": "Execute Flow",
        "type": "ExecuteFlow"
      }
    ],
    "outputs": {},
    "selected": false
  },
  "type": "agentFlow",
  "width": 300,
  "height": 400,
  "selected": false,
  "positionAbsolute": {"x": 800.0, "y": 400.0},
  "dragging": false
}
```

**REQUIREMENTS**:

The following MUST be true for ExecuteFlow nodes:

- [ ] `name` is EXACTLY `"executeFlowAgentflow"` (not "executeFlow" or "ExecuteFlow")
- [ ] `type` is EXACTLY `"ExecuteFlow"` (case-sensitive)
- [ ] `executeFlowSelectedFlow` is empty string `""` (not `"{{FLOW_ID}}"` or placeholder)
- [ ] `executeFlowInput` is valid JSON (minimum: `"{}"`, can also be `"{{question}}"` or valid JSON string)
- [ ] `executeFlowReturnResponseAs` is either `"userMessage"` or `"assistantMessage"` (no other values)
- [ ] All 6 input parameters present in `inputs` object (even if empty strings)
- [ ] Output anchor ID follows pattern: `executeFlowAgentflow_N-output-executeFlowAgentflow` (not `-output-agent` or other suffix)
- [ ] All inputParams have correct ID format: `executeFlowAgentflow_N-input-[paramName]-[type]`
- [ ] `version` is `1.1` (current stable version)
- [ ] `width` is `300` and `height` is `400` (standard dimensions)

**Validation Commands**:

```bash
# 1. Check executeFlowInput is valid JSON
jq '.nodes[] | select(.data.name=="executeFlowAgentflow") | .data.inputs.executeFlowInput' workflow.json | jq empty
# Should exit 0 (valid JSON)

# 2. Check executeFlowSelectedFlow is not placeholder
jq '.nodes[] | select(.data.name=="executeFlowAgentflow") | .data.inputs.executeFlowSelectedFlow' workflow.json | grep -q '{{FLOW_ID}}' && echo "❌ FAIL: Placeholder found" || echo "✅ PASS"

# 3. Check returnResponseAs has valid value
jq '.nodes[] | select(.data.name=="executeFlowAgentflow") | .data.inputs.executeFlowReturnResponseAs' workflow.json | grep -qE '^"(userMessage|assistantMessage)"$' && echo "✅ PASS" || echo "❌ FAIL"

# 4. Check output anchor format
jq '.nodes[] | select(.data.name=="executeFlowAgentflow") | .data.outputAnchors[0].id' workflow.json | grep -qE 'executeFlowAgentflow_[0-9]+-output-executeFlowAgentflow$' && echo "✅ PASS" || echo "❌ FAIL"

# 5. Count input parameters (should be 6)
jq '.nodes[] | select(.data.name=="executeFlowAgentflow") | .data.inputs | keys | length' workflow.json
# Should output: 6

# 6. Verify all required input keys present
jq '.nodes[] | select(.data.name=="executeFlowAgentflow") | .data.inputs | keys' workflow.json
# Should output: ["executeFlowSelectedFlow", "executeFlowInput", "executeFlowOverrideConfig", "executeFlowBaseURL", "executeFlowReturnResponseAs", "executeFlowUpdateState"]
```

**Common Mistakes**:

1. **Placeholder flow ID**: Using `{{FLOW_ID}}` instead of empty string `""`
2. **Invalid JSON**: Using plain text instead of JSON in `executeFlowInput`
3. **Wrong output anchor suffix**: Using `-output-agent` instead of `-output-executeFlowAgentflow`
4. **Missing optional fields**: Omitting `executeFlowOverrideConfig`, `executeFlowBaseURL`, or `executeFlowUpdateState` from `inputs` object
5. **Invalid returnResponseAs**: Using values other than `"userMessage"` or `"assistantMessage"`
6. **Wrong node name**: Using `"executeFlow"` or `"ExecuteFlow"` instead of `"executeFlowAgentflow"`

---

## Start Node Requirements

### Complete inputParams Order

Start node `inputParams` MUST have this EXACT order:

1. `startInputType` (options: chatInput, formInput)
2. **`formTitle`** (string, conditional)
3. **`formDescription`** (string, conditional)
4. **`formInputTypes`** (array, conditional)
5. `startEphemeralMemory` (boolean)
6. `startState` (array)
7. `startPersistState` (boolean)

### Complete inputs Values

```json
{
  "inputs": {
    "startInputType": "chatInput",
    "formTitle": "",
    "formDescription": "",
    "formInputTypes": "",
    "startEphemeralMemory": "",
    "startState": "",
    "startPersistState": ""
  }
}
```

**REQUIREMENT**: ALL seven fields must be present, even if empty strings.

---

## Agent Node Requirements

### agentMessages in inputParams

The `agentMessages` parameter definition in `inputParams` is CORRECT in both files - this is the parameter DEFINITION, not the value.

### agentMessages in inputs

**CRITICAL**: In the `inputs` object, `agentMessages` MUST be an empty string:

```json
{
  "inputs": {
    "agentMessages": ""  // ✅ Always empty string
  }
}
```

### agentTools Configuration

If tools are used:

```json
{
  "inputs": {
    "agentTools": [
      {
        "agentSelectedTool": "toolName",
        "agentSelectedToolRequiresHumanInput": "",
        "agentSelectedToolConfig": {
          "agentSelectedTool": "toolName"
        }
      }
    ]
  }
}
```

**REQUIREMENT**: The `agentSelectedToolConfig` nested object is MANDATORY when tools are configured.

---

## Field Value Standards

### Empty String vs Empty Array vs Object

**Use Empty String `""`**:
- `agentMessages`
- `agentToolsBuiltInOpenAI`
- `agentKnowledgeDocumentStores`
- `agentKnowledgeVSEmbeddings`
- `agentUserMessage`
- `agentUpdateState`
- `formTitle`
- `formDescription`
- `formInputTypes`
- `startEphemeralMemory`
- `startState`
- `startPersistState`

**Use Empty Array `[]`**: (Never - use empty string instead)

**Use Configured Array** (when applicable):
- `agentTools` (with agentSelectedToolConfig)
- `agentMessages` (when system messages needed - but canonical shows empty string)

**Use Object**:
- `agentModelConfig` (always configured with model settings)

---

## ID Construction Rules

### Pattern: `{nodeId}-{section}-{name}`

**Start Node Output Anchor**:
```
Format: startAgentflow_{N}-output-startAgentflow
Example: startAgentflow_0-output-startAgentflow
```

**Agent Node Output Anchor**:
```
Format: agentAgentflow_{N}-output-agentAgentflow
Example: agentAgentflow_0-output-agentAgentflow
```

**Input Parameter IDs**:
```
Format: {nodeId}-input-{paramName}-{paramType}
Example: agentAgentflow_0-input-agentModel-asyncOptions
Example: startAgentflow_0-input-startInputType-options
```

### ❌ FORBIDDEN Patterns

- ❌ `startAgentflow_0-output-startAgentflow-Start` (extra suffix)
- ❌ `agentAgentflow_0-output-agentAgentflow-Agent` (extra suffix)
- ❌ Any ID with extra suffixes beyond the standard pattern

---

## Placeholder Text Standards

### EXACT Placeholder Values (Must Match Exactly)

**Knowledge (Document Stores) - docStoreDescription**:
```
"Describe what the knowledge base is about, this is useful for the AI to know when and how to search for correct information"
```

**Knowledge (Vector Embeddings) - knowledgeName**:
```
"A short name for the knowledge base, this is useful for the AI to know when and how to search for correct information"
```

**Knowledge (Vector Embeddings) - knowledgeDescription**:
```
"Describe what the knowledge base is about, this is useful for the AI to know when and how to search for correct information"
```

**Form Input - formTitle**:
```
"Please Fill Out The Form"
```

**Form Input - formDescription**:
```
"Complete all fields below to continue"
```

**Form Input Types - label**:
```
"Label for the input"
```

**Form Input Types - name (Variable Name)**:
```
"Variable name for the input (must be camel case)"
```

**Flow State - key**:
```
"Foo"
```

**Flow State - value**:
```
"Bar"
```

---

## Validation Checklist

### Before Generating Any Flowise Flow

- [ ] Read `/Users/name/Downloads/Simple Agent Agents.json` (canonical example)
- [ ] Read this authority document (FLOWISE-STRUCTURE-AUTHORITY.md)
- [ ] Read AGENT-NODE-TEMPLATE.json
- [ ] Read START-NODE-TEMPLATE.json

### After Generating - Start Node Validation

- [ ] Has `formTitle` parameter (between startInputType and startEphemeralMemory)
- [ ] Has `formDescription` parameter
- [ ] Has `formInputTypes` parameter with complete array structure
- [ ] outputAnchors ID is `startAgentflow_N-output-startAgentflow` (no suffix)
- [ ] All 7 input fields present in inputs object

### After Generating - Agent Node Validation

- [ ] `agentMessages` in inputs is empty string `""`
- [ ] If tools configured: has `agentSelectedToolConfig` nested object
- [ ] outputAnchors ID is `agentAgentflow_N-output-agentAgentflow` (no suffix)
- [ ] Knowledge placeholders have FULL text (not truncated)
- [ ] All placeholder text matches standards exactly

### Structure Validation Commands

```bash
# Check outputAnchors IDs (should have no -Start or -Agent suffix)
grep -o '"id": "[^"]*-output-[^"]*"' flow.json

# Check for form input parameters in start node
grep -c '"name": "formTitle"' flow.json  # Should be 1
grep -c '"name": "formDescription"' flow.json  # Should be 1
grep -c '"name": "formInputTypes"' flow.json  # Should be 1

# Check agentMessages is empty string (not array)
grep -A 1 '"agentMessages":' flow.json | grep '""'  # Should match

# Check for agentSelectedToolConfig if tools used
grep -c 'agentSelectedToolConfig' flow.json  # Should match tool count

# Check placeholder text completeness
grep 'this is useful for the AI to know' flow.json  # Should find matches
```

---

## Design Patterns

### Self-Contained Agents

✅ Agents MUST be self-contained:
- Model selection built-in via `agentModel` (asyncOptions)
- Memory configuration built-in via `agentEnableMemory` + `agentMemoryType`
- Model config in `agentModelConfig` object
- No external model/memory nodes

❌ DO NOT create:
- Separate `chatOpenAI` nodes
- Separate `windowMemory` nodes
- Agents that reference external instances via `{{nodeId.data.instance}}`

### Node Naming

✅ CORRECT node names:
- `startAgentflow` (start nodes)
- `agentAgentflow` (agent nodes)

❌ WRONG node names:
- `start` or `Start`
- `agent` or `Agent`
- `supervisorAgent`
- `chatOpenAI`
- `windowMemory`

---

## Lessons Learned

### Problem: Generated flows don't import correctly to Flowise

**Root Causes**:
1. Missing form input parameters break start node functionality
2. Wrong outputAnchors IDs cause connection issues
3. Missing agentSelectedToolConfig prevents tools from working
4. System messages in agentMessages instead of empty string

### Solution: Follow This Authority Document

Every requirement in this document exists because:
1. It's present in the canonical working example
2. It's required for Flowise to function correctly
3. Omitting it causes import or runtime failures

---

## References

**Canonical Example**: `/Users/name/Downloads/Simple Agent Agents.json`
**Agent Template**: `/Users/name/homelab/context-foundry/extensions/flowise/node-templates/AGENT-NODE-TEMPLATE.json`
**Start Template**: `/Users/name/homelab/context-foundry/extensions/flowise/node-templates/START-NODE-TEMPLATE.json`
**Current Structure Guide**: `/Users/name/homelab/context-foundry/extensions/flowise/AGENT_PATTERN_REFERENCE.md`

---

## Version History

**v1.0** (2025-10-31):
- Initial creation based on line-by-line comparison
- Documents all 6 critical structural issues
- Establishes canonical reference patterns
- Provides complete validation checklist

---

**END OF AUTHORITY DOCUMENT**

When in doubt, ALWAYS refer to the canonical example: `/Users/name/Downloads/Simple Agent Agents.json`

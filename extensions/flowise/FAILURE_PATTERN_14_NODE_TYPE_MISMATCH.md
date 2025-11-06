# Failure Pattern #14: Node Type Mismatch

**Category**: Structural
**Severity**: CRITICAL
**Frequency**: Discovered 2025-11-05
**Affected Node Types**: Start, ConditionAgent, DirectReply

---

## Problem Description

Builder generated nodes with incorrect `type` and `name` fields, causing nodes to not render properly in Flowise UI (missing icons, sync errors).

---

## Symptoms

1. **Visual Symptoms in Flowise**:
   - Node appears without icon (blank/generic icon)
   - Node shows "sync problem" that won't clear
   - Node missing from palette or can't be configured

2. **Structural Symptoms in JSON**:
   - `type` field doesn't match Flowise node type registry
   - `name` field doesn't match expected naming convention
   - Missing required `inputParams` for specific node types

---

## Root Cause

Builder used generic or incorrect node type names instead of consulting canonical node templates:

| Incorrect Type | Correct Type | Node Purpose |
|----------------|--------------|--------------|
| `"StartFlow"` | `"Start"` | Start node |
| `"ConditionNode"` | `"ConditionAgent"` | Conditional routing |
| Empty `inputParams` | Required params | DirectReply message |

---

## Examples

### Example 1: Start Node with Wrong Type

**❌ INCORRECT:**
```json
{
  "data": {
    "name": "startAgentflow",
    "type": "StartFlow",  // ❌ Wrong type
    "color": "#81c784"
  }
}
```

**✅ CORRECT:**
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

---

### Example 2: ConditionAgent with Wrong Type/Name

**❌ INCORRECT:**
```json
{
  "data": {
    "name": "conditionNode",  // ❌ Wrong name
    "type": "ConditionNode",  // ❌ Wrong type
    "color": "#ff9800"
  }
}
```

**✅ CORRECT:**
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

---

### Example 3: DirectReply Missing Required Fields

**❌ INCORRECT:**
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

**✅ CORRECT:**
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

---

## Detection Strategy

### Automated Validation

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

---

## Prevention Strategy

### 1. **Use Canonical Node Templates**

Builder MUST reference these template files:
- `/extensions/flowise/prompts/START-NODE-TEMPLATE.json` (type: "Start")
- `/extensions/flowise/prompts/CONDITION-NODE-TEMPLATE.json` (type: "Condition" - deterministic)
- `/extensions/flowise/prompts/DIRECT-REPLY-NODE-TEMPLATE.json` (type: "DirectReply")

For **ConditionAgent** (AI routing), reference pattern files:
- `/extensions/flowise/templates/afv2-patterns/03-routing.json`
- `/extensions/flowise/templates/afv2-patterns/04-iteration.json`
- `/extensions/flowise/templates/afv2-patterns/05-looping.json`
- `/extensions/flowise/templates/afv2-patterns/06-hierarchy.json`

### 2. **Node Type Registry**

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

### 3. **Update Builder Instructions**

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

---

## Fix Procedure

### 1. Fix Start Node

```bash
jq '(.nodes[] | select(.data.type == "StartFlow")) |= (
  .data.type = "Start" |
  .data.color = "#7EE787" |
  .data.hideInput = true
)' workflow.json > workflow.fixed.json
```

### 2. Fix ConditionAgent Node

```bash
jq '(.nodes[] | select(.data.type == "ConditionNode")) |= (
  .data.type = "ConditionAgent" |
  .data.name = "conditionAgentAgentflow" |
  .data.color = "#ff8fab"
)' workflow.json > workflow.fixed.json
```

### 3. Fix DirectReply Nodes

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

---

## Impact

**When This Pattern Occurs:**
- ❌ Nodes don't render in Flowise UI (missing icons)
- ❌ Workflow shows "sync problem" errors
- ❌ Cannot configure or execute workflow
- ❌ Workflow import fails silently

**Severity**: CRITICAL - Workflow completely unusable

---

## Related Patterns

- **Pattern #8**: Missing inputParams (similar root cause)
- **Pattern #6**: Incorrect tool JSON structure (similar validation issue)

---

## Resolution Status

- ✅ Pattern documented: 2025-11-05
- ⏳ Validator updated: Pending
- ⏳ Builder instructions updated: Pending
- ⏳ Node type registry created: Pending

---

## Example Workflows Affected

- `bcm-compliance-assessment.json` (2025-11-05) - All 3 issues present

---

🔧 **Pattern Owner**: Claude Code
📅 **Last Updated**: 2025-11-05

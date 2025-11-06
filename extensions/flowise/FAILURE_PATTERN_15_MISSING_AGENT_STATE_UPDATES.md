# Failure Pattern #15: Missing Agent State Updates

**Category**: State Management
**Severity**: CRITICAL
**Frequency**: Discovered 2025-11-06
**Affected Node Types**: Agent (all agent nodes in multi-agent workflows)

---

## Problem Description

Builder generates agent nodes without `agentStateUpdates` configuration, causing agents to respond conversationally instead of progressing through the workflow. Agents cannot reliably update Flow State or trigger the next agent in the chain.

---

## Symptoms

1. **Runtime Symptoms in Flowise**:
   - First agent responds conversationally to user
   - Workflow stops after first agent instead of progressing
   - Subsequent agents never execute
   - Flow State remains empty or undefined

2. **Structural Symptoms in JSON**:
   - Agent nodes missing `agentStateUpdates` in `inputParams`
   - Agent nodes missing `agentStateUpdates` in `inputs`
   - Agent prompts rely on manual state updates (e.g., "$flow.state.extracted_data = {}")
   - No structured artifact outputs configured

---

## Root Cause

Builder assumes agents can manually update Flow State through their responses, but Flowise AgentFlow requires:
1. Explicit `agentStateUpdates` configuration in agent inputs
2. Agents to output artifacts with identifiers matching state variable names
3. State updates to be declarative, not imperative

**What Doesn't Work:**
```
Agent Prompt: "After extraction, update Flow State: $flow.state.extracted_data = {your JSON output}"
```

**What Works:**
```
Agent Inputs: agentStateUpdates: [{"key": "extracted_data", "value": "{{ extracted_data }}"}]
Agent Prompt: "<antArtifact identifier='extracted_data' type='application/json'>...JSON...</antArtifact>"
```

---

## Examples

### Example 1: Agent Without State Updates

**❌ INCORRECT:**
```json
{
  "data": {
    "type": "Agent",
    "label": "Agent.DataExtractor",
    "inputParams": [
      {
        "label": "Agent Name",
        "name": "agentName",
        "type": "string"
      },
      {
        "label": "System Message",
        "name": "agentSystemMessage",
        "type": "string"
      }
      // ❌ Missing agentStateUpdates inputParam
    ],
    "inputs": {
      "agentName": "Agent.DataExtractor",
      "agentSystemMessage": "Extract data and update $flow.state.extracted_data = {your output}"
      // ❌ No agentStateUpdates configuration
    }
  }
}
```

**✅ CORRECT:**
```json
{
  "data": {
    "type": "Agent",
    "label": "Agent.DataExtractor",
    "inputParams": [
      {
        "label": "Agent Name",
        "name": "agentName",
        "type": "string"
      },
      {
        "label": "System Message",
        "name": "agentSystemMessage",
        "type": "string"
      },
      {
        "label": "Update State",
        "name": "agentStateUpdates",
        "type": "array",
        "optional": true,
        "array": [
          {
            "label": "Key",
            "name": "key",
            "type": "string",
            "placeholder": "e.g., extracted_data"
          },
          {
            "label": "Value",
            "name": "value",
            "type": "string",
            "acceptVariable": true,
            "placeholder": "e.g., {{ extracted_data }}"
          }
        ]
      }
    ],
    "inputs": {
      "agentName": "Agent.DataExtractor",
      "agentSystemMessage": "Extract data and output as artifact...",
      "agentStateUpdates": [
        {
          "key": "extracted_data",
          "value": "{{ extracted_data }}"
        }
      ]
    }
  }
}
```

---

### Example 2: Agent Prompt With Artifact Output

**❌ INCORRECT:**
```
You are a data extraction agent.

Extract structured data from the invoice.

OUTPUT FORMAT (JSON):
{
  "invoice_number": "...",
  "vendor": "...",
  "total": 0
}

After extraction, update Flow State:
$flow.state.extracted_data = {your JSON output}
```

**✅ CORRECT:**
```
You are a data extraction agent.

Extract structured data from the invoice.

OUTPUT: Create an artifact called "extracted_data" with this JSON structure:

<antArtifact identifier="extracted_data" type="application/json" title="Extracted Invoice Data">
{
  "invoice_number": "INV-2025-11-06",
  "vendor": "Acme Corp",
  "total": 2500
}
</antArtifact>

DO NOT respond conversationally. Only output the artifact above with actual extracted data.
```

---

### Example 3: Multi-Agent Chain Configuration

**Complete Agent Configuration Example:**

```json
{
  "nodes": [
    {
      "id": "agent1",
      "data": {
        "type": "Agent",
        "label": "Agent.Extractor",
        "inputs": {
          "agentName": "Agent.Extractor",
          "agentSystemMessage": "Extract data as <antArtifact identifier='extracted_data'>...</antArtifact>",
          "agentStateUpdates": [
            {"key": "extracted_data", "value": "{{ extracted_data }}"}
          ]
        }
      }
    },
    {
      "id": "agent2",
      "data": {
        "type": "Agent",
        "label": "Agent.Validator",
        "inputs": {
          "agentName": "Agent.Validator",
          "agentSystemMessage": "Validate {{$flow.state.extracted_data}} and output <antArtifact identifier='validation_result'>...</antArtifact>",
          "agentStateUpdates": [
            {"key": "validation_result", "value": "{{ validation_result }}"}
          ]
        }
      }
    }
  ]
}
```

**Flow:**
1. Agent.Extractor outputs `extracted_data` artifact
2. `agentStateUpdates` maps `{{ extracted_data }}` → `$flow.state.extracted_data`
3. Agent.Validator reads `{{$flow.state.extracted_data}}`
4. Agent.Validator outputs `validation_result` artifact
5. Workflow continues automatically

---

## Detection Strategy

### Automated Validation

```python
def validate_agent_state_updates(workflow):
    """
    Validate agents in multi-agent workflows have agentStateUpdates configured
    """
    issues = []
    agent_nodes = [n for n in workflow["nodes"] if n["data"]["type"] == "Agent"]

    # Only validate if there are multiple agents (chaining pattern)
    if len(agent_nodes) < 2:
        return issues

    for node in agent_nodes:
        node_id = node["id"]
        node_label = node["data"].get("label", "Unknown")

        # Check if agentStateUpdates exists in inputParams
        input_params = node["data"].get("inputParams", [])
        has_state_updates_param = any(
            p["name"] == "agentStateUpdates" for p in input_params
        )

        if not has_state_updates_param:
            issues.append({
                "pattern": "#15",
                "node": node_id,
                "issue": f"Agent '{node_label}' missing 'agentStateUpdates' inputParam",
                "severity": "CRITICAL",
                "fix": "Add agentStateUpdates to inputParams array"
            })

        # Check if agentStateUpdates exists in inputs
        inputs = node["data"].get("inputs", {})
        state_updates = inputs.get("agentStateUpdates", [])

        if not state_updates or len(state_updates) == 0:
            issues.append({
                "pattern": "#15",
                "node": node_id,
                "issue": f"Agent '{node_label}' has no agentStateUpdates configuration",
                "severity": "CRITICAL",
                "fix": "Add state update mappings to inputs.agentStateUpdates"
            })

        # Check system message for artifact output instructions
        system_message = inputs.get("agentSystemMessage", "")
        if "antArtifact identifier=" not in system_message:
            issues.append({
                "pattern": "#15",
                "node": node_id,
                "issue": f"Agent '{node_label}' prompt doesn't use artifact output",
                "severity": "HIGH",
                "fix": "Update prompt to output <antArtifact identifier='variable_name'>...</antArtifact>"
            })

    return issues
```

---

## Prevention Strategy

### 1. **Always Add agentStateUpdates to Agent Nodes**

For **every** Agent node in a multi-agent workflow:

```json
{
  "label": "Update State",
  "name": "agentStateUpdates",
  "type": "array",
  "optional": true,
  "array": [
    {
      "label": "Key",
      "name": "key",
      "type": "string",
      "placeholder": "e.g., extracted_data"
    },
    {
      "label": "Value",
      "name": "value",
      "type": "string",
      "acceptVariable": true,
      "placeholder": "e.g., {{ extracted_data }}"
    }
  ],
  "id": "{node_id}-input-agentStateUpdates-array"
}
```

### 2. **State Update Mapping Pattern**

```json
{
  "inputs": {
    "agentStateUpdates": [
      {
        "key": "output_variable_name",
        "value": "{{ artifact_identifier }}"
      }
    ]
  }
}
```

**Examples:**
- DataExtractor: `{"key": "extracted_data", "value": "{{ extracted_data }}"}`
- Validator: `{"key": "validation_result", "value": "{{ validation_result }}"}`
- Enricher: `{"key": "enriched_data", "value": "{{ enriched_data }}"}`
- Report: `{"key": "final_report", "value": "{{ final_report }}"}`

### 3. **Artifact-Based Output Pattern**

Update agent prompts to use Anthropic artifact syntax:

```
OUTPUT: Create an artifact called "{identifier}" with this structure:

<antArtifact identifier="{identifier}" type="{type}" title="{title}">
{content}
</antArtifact>

DO NOT respond conversationally. Only output the artifact.
```

**Common Types:**
- `type="application/json"` - Structured data
- `type="text/plain"` - Plain text output
- `type="text/markdown"` - Formatted reports

### 4. **Update Builder Instructions**

Add to `phase_2_architect.md` and `phase_2_5_parallel_build.md`:

```markdown
## CRITICAL: Agent State Management

For **EVERY** Agent node in a multi-agent workflow:

### 1. Add agentStateUpdates InputParam

```json
{
  "label": "Update State",
  "name": "agentStateUpdates",
  "type": "array",
  "optional": true,
  "array": [
    {"label": "Key", "name": "key", "type": "string"},
    {"label": "Value", "name": "value", "type": "string", "acceptVariable": true}
  ]
}
```

### 2. Configure State Updates in Inputs

```json
{
  "inputs": {
    "agentStateUpdates": [
      {"key": "output_variable", "value": "{{ artifact_identifier }}"}
    ]
  }
}
```

### 3. Use Artifact Output in Prompts

**ALWAYS** use this format in agent system messages:

```
<antArtifact identifier="variable_name" type="application/json">
{structured output}
</antArtifact>

DO NOT respond conversationally. Only output the artifact.
```

**NEVER** use manual state updates like:
- ❌ "$flow.state.variable = {output}"
- ❌ "Update Flow State with your result"
- ❌ Conversational responses without artifacts

### State Update Examples by Agent Type

| Agent Purpose | State Key | Artifact ID | Example Value |
|---------------|-----------|-------------|---------------|
| Data Extraction | `extracted_data` | `extracted_data` | Parsed invoice JSON |
| Validation | `validation_result` | `validation_result` | Validation checks JSON |
| Enrichment | `enriched_data` | `enriched_data` | Enhanced data JSON |
| Risk Scoring | `risk_score` | `risk_score` | Numeric score (1-10) |
| Processing | `processing_status` | N/A | Fixed value: "processed" |
| Reporting | `final_report` | `final_report` | Confirmation message |
```

### 5. **Reference Working Template**

Use Pattern #1 (Chaining) as canonical reference:
- File: `/Users/name/homelab/afv2-pattern-01-chaining/01-chaining.json`
- All agents have proper `agentStateUpdates` configuration
- Prompts use artifact output pattern
- State flows reliably between agents

---

## Fix Procedure

### Automated Fix Script

```python
#!/usr/bin/env python3
"""
Fix missing agentStateUpdates in agent nodes
"""
import json
import sys

def fix_agent_state_updates(workflow_file, output_file, state_config):
    """
    Add agentStateUpdates to all agent nodes

    Args:
        workflow_file: Input workflow JSON
        output_file: Output workflow JSON
        state_config: Dict mapping agent labels to state update configs
    """
    with open(workflow_file, 'r') as f:
        workflow = json.load(f)

    for node in workflow['nodes']:
        if node['data']['type'] != 'Agent':
            continue

        label = node['data']['label']

        # Add inputParams definition
        input_params = node['data']['inputParams']
        has_param = any(p['name'] == 'agentStateUpdates' for p in input_params)

        if not has_param:
            input_params.append({
                "label": "Update State",
                "name": "agentStateUpdates",
                "type": "array",
                "optional": True,
                "array": [
                    {"label": "Key", "name": "key", "type": "string"},
                    {"label": "Value", "name": "value", "type": "string", "acceptVariable": True}
                ],
                "id": f"{node['id']}-input-agentStateUpdates-array"
            })

        # Add inputs configuration
        if label in state_config:
            node['data']['inputs']['agentStateUpdates'] = state_config[label]

    with open(output_file, 'w') as f:
        json.dump(workflow, f, indent=2)

    print(f"✅ Fixed workflow saved to {output_file}")

# Example state configuration
STATE_CONFIG = {
    "Agent.DataExtractor": [
        {"key": "extracted_data", "value": "{{ extracted_data }}"}
    ],
    "Agent.Validator": [
        {"key": "validation_result", "value": "{{ validation_result }}"}
    ],
    "Agent.Enricher": [
        {"key": "enriched_data", "value": "{{ enriched_data }}"},
        {"key": "risk_score", "value": "{{ risk_score }}"}
    ],
    "Agent.Report": [
        {"key": "final_report", "value": "{{ final_report }}"}
    ]
}

if __name__ == '__main__':
    fix_agent_state_updates(sys.argv[1], sys.argv[2], STATE_CONFIG)
```

---

## Impact

**When This Pattern Occurs:**
- ❌ Workflow stops after first agent
- ❌ Agents respond conversationally instead of progressing
- ❌ Flow State remains empty or undefined
- ❌ Subsequent agents never execute
- ❌ Cannot build reliable multi-agent chains

**Severity**: CRITICAL - Multi-agent workflows completely unusable

---

## Related Patterns

- **Pattern #1**: Complete Flow Validation (ensures end-to-end execution)
- **Pattern #8**: Missing inputParams (similar structural issue)

---

## Resolution Status

- ✅ Pattern documented: 2025-11-06
- ✅ Fix script created: fix_agent_state_updates.py
- ✅ Validation function added: validate_agent_state_updates()
- ⏳ Builder instructions updated: Pending
- ⏳ Validator integration: Pending

---

## Example Workflows Affected

- `document-processing-chain.json` (2025-11-06) - All 5 agent nodes missing state updates
- `invoice-processing-CHAT-v2-2025-11-06.json` (2025-11-06) - Fixed in v3

**Fixed Version**: `invoice-processing-CHAT-v3-2025-11-06.json`

---

## Key Learnings

1. **Declarative > Imperative**: Flowise requires declarative state updates via `agentStateUpdates`, not imperative commands in prompts
2. **Artifacts Are Essential**: Anthropic's artifact feature is the proper way to capture structured outputs
3. **Variable Naming Matters**: Artifact identifiers must match agentStateUpdates value placeholders
4. **Pattern #1 Is Gold Standard**: Always reference Pattern #1 for proper agent chain configuration

---

🔧 **Pattern Owner**: Claude Code
📅 **Last Updated**: 2025-11-06
📝 **Discovered During**: document-processing-chain workflow debugging

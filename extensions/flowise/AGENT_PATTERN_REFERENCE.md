# Flowise Multi-Agent JSON Structure - Authoritative Pattern Reference

**Status**: Canonical Reference
**Version**: 1.0
**Last Updated**: 2025-10-31

This document defines the authoritative pattern for creating Flowise multi-agent systems with JSON configuration. All Context Foundry generated Flowise flows MUST follow these patterns.

---

## Table of Contents

1. [Production-Ready Pattern Templates](#production-ready-pattern-templates) ⭐ NEW
2. [Core Architecture](#core-architecture)
3. [Node Types](#node-types)
4. [Agent Input Parameters](#agent-input-parameters)
5. [Actual Configured Values](#actual-configured-values)
6. [Edges Structure](#edges-structure)
7. [Critical Design Patterns](#critical-design-patterns)
8. [Implementation Checklist](#implementation-checklist)

---

## Production-Ready Pattern Templates

**🎯 Start Here: 9 Validated AFv2 Templates**

Context Foundry provides **9 production-ready AgentFlow v2 pattern templates** that demonstrate fundamental multi-agent orchestration patterns. All templates are validator-passing, FLOWISE-STRUCTURE-AUTHORITY compliant, and production-tested.

### Quick Reference

| # | Pattern | Complexity | Use Case | File |
|---|---------|------------|----------|------|
| 1 | **Chaining** | Low | Fixed sequential pipeline | `01-chaining.json` |
| 2 | **Parallel** | Medium | Multi-source research | `02-parallel.json` |
| 3 | **Routing** | Medium | Intent classification | `03-routing.json` |
| 4 | **Iteration** | High | Quality refinement loop | `04-iteration.json` |
| 5 | **Looping** | High | Validation retry logic | `05-looping.json` |
| 6 | **Hierarchy** | Very High | Task delegation | `06-hierarchy.json` |
| 7 | **Batch Processing** | Medium | Array/list processing | `07-batch-processing.json` |
| 8 | **Conditional Retry** | High | Score-based validation | `08-conditional-retry.json` |
| 9 | **API Integration** | Medium | External HTTP API calls | `09-api-integration.json` |

### Pattern Descriptions

#### 1️⃣ Chaining Pattern
**Flow:** Start → Chain1 → HIL Gate → Chain2 → Chain3 → Report

Linear 3-step sequential processing pipeline with human-in-the-loop approval gate. Demonstrates artifact handoffs between agents via state updates.

**Use Cases:**
- Document processing pipelines (OCR → Extract → Transform → Format)
- Data transformation workflows (Raw → Clean → Enrich → Publish)
- Sequential approval workflows

**Key Features:**
- 4 agents with clear specialization
- HIL gate with exactly 5 inputParams (Pattern #11 compliant)
- State updates tracking artifacts through pipeline (`artifacts.artifact_1/2/final_draft`)

#### 2️⃣ Parallel Pattern
**Flow:** Start → [Web Search || KB || Analyzer] → Aggregator → Report

Multi-source information gathering with concurrent execution and conflict resolution. Demonstrates fan-out/fan-in architecture.

**Use Cases:**
- Research synthesis from multiple sources
- Competitive analysis (web + internal data)
- Risk assessment with parallel checks

**Key Features:**
- 3 concurrent branches executing in parallel
- Built-in Anthropic tools (`web_search_20250305`)
- Aggregator with deduplication logic

#### 3️⃣ Routing Pattern
**Flow:** Start → Router → [Billing | Technical | General | FAIL] → Synthesize

Intent-based routing to domain-specific agents with confidence threshold validation.

**Use Cases:**
- Customer support routing
- Ticketing systems
- Multi-domain chatbots

**Key Features:**
- 4-path routing (including FAIL path for invalid input)
- Confidence threshold (0.6, configurable)
- Metadata tracking (confidence scores, alternate routes)

#### 4️⃣ Iteration Pattern
**Flow:** Start → Planner → Gate → Research → [loop back to Gate] → Report

Iterative quality improvement loop toward target score with convergence detection.

**Use Cases:**
- Content refinement until quality threshold met
- Code optimization to performance target
- Data quality improvement cycles

**Key Features:**
- Loop-back edge (Research → Gate, marked `animated: true`)
- Scoring system (0.0-1.0 scale, target 0.85)
- Max iterations limit (default 3)
- Early exit on convergence

#### 5️⃣ Looping Pattern
**Flow:** Start → Generate → Validate → Gate → [PASS → Return | FIX → Fix Plan → loop back | FAIL → Return]

Validation-driven retry loop with automated testing and fix generation.

**Use Cases:**
- Test-driven development (generate → test → fix loop)
- Policy compliance checking
- Automated code review with fixes

**Key Features:**
- 3-path gate (PASS, FIX, FAIL - not just binary)
- Loop-back edge (Fix Plan → Generate, marked `animated: true`)
- FAIL path prevents returning broken code after max retries
- Max retries limit (default 3)

#### 6️⃣ Hierarchy Pattern
**Flow:** Start → Supervisor → Checker → [Worker → Reviewer → loop back to Checker] → Final

Supervisor-orchestrated task delegation to specialist roles with review gates.

**Use Cases:**
- Software development workflows (planning → coding → review)
- Content creation (research → write → edit)
- Project management (delegate → execute → validate)

**Key Features:**
- Role-based architecture (Supervisor, Software Engineer, Code Reviewer)
- Step iterator (`hierarchy.current_step` incremented by Reviewer)
- Loop-back edge (Reviewer → Checker, marked `animated: true`)
- Role-specific tool ACLs

#### 7️⃣ Batch Processing Pattern
**Flow:** Start → Planner → Iteration Node → [Processor Agent (N times)] → Aggregator → Direct Reply

For-each iteration over arrays with sequential processing and result aggregation.

**Use Cases:**
- Sentiment analysis on multiple reviews/documents
- Batch document processing (OCR, extraction, classification)
- Multi-item quality checks (validate N files)
- Parallel data transformation pipelines

**Key Features:**
- **Iteration Node** for-each loops over input arrays
- Processor agent executes once per item (N iterations)
- Aggregator combines results from all iterations
- Handles empty arrays gracefully (0 iterations, no errors)
- State tracking: `batch.items[]`, `batch.results[]`

#### 8️⃣ Conditional Retry Pattern
**Flow:** Start → Generator → Validator → Condition Node (score check) → [PASS → Success Agent → Direct Reply | RETRY → Retry Controller → loop back to Generator | FAIL → Fail Agent → Direct Reply]

Score-based validation with deterministic threshold check and intelligent retry loop.

**Use Cases:**
- Content quality validation with iterative improvement
- Code generation with automated testing
- Data validation with auto-correction
- Compliance checking with remediation

**Key Features:**
- **Condition Node** deterministic threshold check (score ≥ 0.85, no LLM cost)
- **Retry Controller (Condition Agent)** uses Haiku model (90% cost savings)
- Loop-back edge with max 3 retries (prevents infinite loops)
- Dual terminal paths (Success/Fail Direct Reply nodes)
- State tracking: `retry.count`, `validation.score`, `retry.history[]`

#### 9️⃣ API Integration Pattern
**Flow:** Start → Parameter Extractor → HTTP Request Node → Condition Node (status check) → [SUCCESS (200) → Format Agent → Direct Reply | ERROR (5xx) → Retry Agent → loop back to HTTP | FATAL (4xx) → Error Handler → Direct Reply]

External HTTP API integration with intelligent error handling and retry logic.

**Use Cases:**
- Third-party API integration (payment, weather, geocoding)
- Webhook processing with retry logic
- Data enrichment from external sources
- Service composition (orchestrating multiple APIs)

**Key Features:**
- **HTTP Request Node** makes external API calls (GET/POST/PUT/DELETE)
- **Condition Node** routes by HTTP status code (200/4xx/5xx)
- Smart error handling: 5xx = retryable, 4xx = fatal (no retry)
- Exponential backoff on retries (2s, 4s, 8s)
- Max 3 retries for server errors
- State tracking: `api.request`, `api.response`, `api.status_code`, `api.retry_count`

### Template Location

All templates are located in:
```
/Users/name/homelab/context-foundry/extensions/flowise/templates/afv2-patterns/
```

**📖 Full Documentation:** See `templates/afv2-patterns/README.md` for:
- Detailed pattern descriptions
- Configuration standards
- State schema conventions
- Validation checklist
- Customization guide
- Troubleshooting tips

### Template Standards

All 9 templates follow these standards:

| Setting | Value | Notes |
|---------|-------|-------|
| **Model** | `claude-sonnet-4-5-20250929` | Latest Claude Sonnet |
| **Credential** | `"Anthropic API Key"` | Flowise credential label |
| **agentMessages** | `""` (empty string) | REQUIRED per FLOWISE-STRUCTURE-AUTHORITY |
| **Tools** | Nested `agentSelectedToolConfig` | Pattern #6 compliant |
| **HIL Gates** | Exactly 5 inputParams | Pattern #11 compliant |
| **Memory** | `agentEnableMemory: true` | All agents have memory |
| **Validation** | 100% pass rate | All pass `validate_workflow.py` |

### When to Use Each Pattern

**Choose Chaining when:**
- You have a fixed, linear sequence of operations
- Each step depends on the previous step's output
- You need human approval at key decision points

**Choose Parallel when:**
- You need information from multiple independent sources
- Operations can run concurrently without dependencies
- You need to aggregate/deduplicate results

**Choose Routing when:**
- Input can fall into distinct categories
- Each category requires specialized handling
- You want confidence-based routing logic

**Choose Iteration when:**
- You're improving a single artifact over time
- Quality can be measured on a numeric scale
- You want to stop when quality threshold is reached

**Choose Looping when:**
- You have explicit validation criteria (tests, policy checks)
- Failures can be automatically fixed and retried
- You need distinct PASS/FIX/FAIL outcomes

**Choose Hierarchy when:**
- You have distinct roles (supervisor, worker, reviewer)
- Tasks are delegated to specialists
- Work products need review before proceeding

**Choose Batch Processing when:**
- You need to process an array or list of items
- Each item requires the same processing logic
- Results should be aggregated at the end
- Items can be processed sequentially (not concurrently)

**Choose Conditional Retry when:**
- Output quality can be measured with a score (0.0-1.0)
- You want deterministic threshold checks (no LLM cost)
- Failed attempts can be improved with specific feedback
- You need to prevent infinite loops (max retries)

**Choose API Integration when:**
- You need to call external HTTP APIs
- You must handle different HTTP status codes (200/4xx/5xx)
- Server errors (5xx) should retry, client errors (4xx) should fail immediately
- You want exponential backoff on retries

### Integration with Orchestrator

**Architect Phase:** Reads `afv2-patterns/README.md` and selects appropriate pattern based on workflow requirements documented in `architecture.md`.

**Builder Phase:** Reads selected pattern JSON and uses it as structural reference, customizing agent personas, state keys, and thresholds for the specific use case.

---

## Core Architecture

### Root Structure

Every Flowise flow JSON consists of two main arrays:

```json
{
  "nodes": [...],  // Array of agent and condition nodes
  "edges": [...]   // Array of connections between nodes
}
```

**Key Principle**: Agents are **self-contained** - they do NOT connect to separate model or memory nodes.

---

## Node Types

### 1. Agent Node (agentAgentflow)

The primary building block for specialized agents. Each agent is a complete, self-contained unit.

#### Complete Structure

```json
{
  "id": "agentAgentflow_[NUMBER]",
  "position": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "data": {
    "id": "agentAgentflow_[NUMBER]",
    "label": "Agent.[DomainName]",  // e.g., "Agent.Payroll", "Agent.HCM.Core"
    "version": 2.2,
    "name": "agentAgentflow",
    "type": "Agent",
    "color": "#4DD0E1",
    "baseClasses": ["Agent"],
    "category": "Agent Flows",
    "description": "Dynamically choose and utilize tools during runtime, enabling multi-step reasoning",
    "inputParams": [...],  // See Agent Input Parameters section
    "inputAnchors": [],
    "inputs": {...},       // See Actual Configured Values section
    "outputAnchors": [
      {
        "id": "agentAgentflow_[N]-output-agentAgentflow-Agent|AgentExecutor",
        "name": "agentAgentflow",
        "label": "Agent",
        "description": "Agent",
        "type": "Agent | AgentExecutor"
      }
    ],
    "outputs": {},
    "selected": false
  },
  "type": "agentFlow",
  "width": 300,
  "height": 500,
  "selected": false,
  "positionAbsolute": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "dragging": false
}
```

#### Key Attributes

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `"agentAgentflow"` | MUST be exactly this |
| `type` | `"Agent"` | Identifies as agent node |
| `color` | `"#4DD0E1"` | Standard agent color (teal) |
| `version` | `2.2` | Current stable version |
| `width` | `300` | Standard width |
| `height` | `500` | Standard height |

---

### 2. Condition Node (conditionAgentAgentflow)

Central routing node that detects user intent and directs to appropriate specialized agents.

#### Complete Structure

```json
{
  "id": "conditionAgentAgentflow_[NUMBER]",
  "position": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "data": {
    "id": "conditionAgentAgentflow_[NUMBER]",
    "label": "Detect User Intention",
    "version": 1.1,
    "name": "conditionAgentAgentflow",
    "type": "ConditionAgent",
    "color": "#ff8fab",
    "baseClasses": ["ConditionAgent"],
    "category": "Agent Flows",
    "description": "Route user to appropriate agent based on detected intention",
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
        "rows": 4,
        "placeholder": "Analyze the user input and route to the appropriate agent..."
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
        "type": "array",
        "array": [
          {
            "label": "Scenario",
            "name": "scenario",
            "type": "string",
            "rows": 2
          }
        ]
      }
    ],
    "inputAnchors": [],
    "inputs": {
      "conditionAgentModel": "[MODEL_TYPE]",
      "conditionAgentInstructions": "[ROUTING_INSTRUCTIONS]",
      "conditionAgentInput": "<p><span class=\"variable\" data-type=\"mention\" data-id=\"question\" data-label=\"question\">{{ question }}</span> </p>",
      "conditionAgentScenarios": [
        {"scenario": "User is asking about Navigation"},
        {"scenario": "User is asking about HCM Core"},
        {"scenario": "User is asking about Payroll"},
        // ... up to 20+ scenarios
      ],
      "conditionAgentModelConfig": {
        "credential": "OpenAI API Key",
        "modelName": "gpt-4o-mini",
        "temperature": 0.2,
        "streaming": true,
        "maxTokens": "",
        "topP": "",
        "frequencyPenalty": "",
        "presencePenalty": "",
        "timeout": "",
        "strictToolCalling": "",
        "stopSequence": "",
        "basepath": "",
        "proxyUrl": "",
        "baseOptions": "",
        "allowImageUploads": "",
        "imageResolution": "low",
        "reasoning": "",
        "reasoningEffort": "",
        "reasoningSummary": "",
        "conditionAgentModel": "chatOpenAI"
      }
    },
    "outputAnchors": [
      {"id": "...-output-0", "label": 0, "name": 0, "description": "Condition 0"},
      {"id": "...-output-1", "label": 1, "name": 1, "description": "Condition 1"},
      // One output for each scenario
    ]
  },
  "type": "agentFlow",
  "width": 300,
  "height": 500
}
```

#### Key Attributes

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `"conditionAgentAgentflow"` | MUST be exactly this |
| `type` | `"ConditionAgent"` | Identifies as condition node |
| `color` | `"#ff8fab"` | Standard condition color (pink) |
| `version` | `1.1` | Current stable version |

#### Model Configuration

The `conditionAgentModelConfig` object configures the LLM used for routing decisions:

```json
"conditionAgentModelConfig": {
  "credential": "OpenAI API Key",
  "modelName": "gpt-4o-mini",        // Fast, cost-effective for routing
  "temperature": 0.2,                 // LOW for deterministic routing (0.1-0.3)
  "streaming": true,
  "maxTokens": "",
  "topP": "",
  "frequencyPenalty": "",
  "presencePenalty": "",
  "timeout": "",
  "strictToolCalling": "",
  "stopSequence": "",
  "basepath": "",
  "proxyUrl": "",
  "baseOptions": "",
  "allowImageUploads": "",
  "imageResolution": "low",
  "reasoning": "",
  "reasoningEffort": "",
  "reasoningSummary": "",
  "conditionAgentModel": "chatOpenAI"   // Must match conditionAgentModel value
}
```

**Critical Fields:**

| Field | Recommended Value | Notes |
|-------|------------------|-------|
| `modelName` | `"gpt-4o-mini"` or `"claude-sonnet-4-0"` | Fast models for routing |
| `temperature` | `0.1` - `0.3` | **MUST be low** for consistent routing |
| `streaming` | `true` | Standard for all agents |
| `conditionAgentModel` | `"chatOpenAI"`, `"chatAnthropic"`, `"chatGemini"` | Must match parent `conditionAgentModel` field |

**Temperature Importance:**

ConditionAgent routing decisions MUST be deterministic and consistent. High temperature (0.7-0.9) causes:
- ❌ Inconsistent routing for same questions
- ❌ Unpredictable agent selection
- ❌ Poor user experience

**Always use temperature 0.1-0.3 for ConditionAgent nodes.**

#### CRITICAL: Variable Format in conditionAgentInput

The `conditionAgentInput` field MUST use Flowise's **rich text HTML format** for variables, not plain text. This is required for proper JSON escaping during execution.

**❌ WRONG - Plain text format (causes malformed JSON):**
```json
"conditionAgentInput": "{{ question }}"
```

**✅ CORRECT - Rich text HTML format:**
```json
"conditionAgentInput": "<p><span class=\"variable\" data-type=\"mention\" data-id=\"question\" data-label=\"question\">{{ question }}</span> </p>"
```

**Why this matters:**
- Plain text format: Flowise doesn't recognize it as a variable → no JSON escaping → malformed JSON sent to LLM
- Rich text format: Flowise recognizes the variable → proper JSON escaping → valid JSON sent to LLM

**Common variables:**
- User input: `data-id="question"` → `{{ question }}`
- Form data: `data-id="$form.fieldName"` → `{{ $form.fieldName }}`
- Flow state: `data-id="$flow.state.key"` → `{{ $flow.state.key }}`

**Symptoms of using plain text format:**
- Condition node executes but produces no output
- LLM receives malformed JSON (missing quotes around input value)
- Node doesn't route to any output path
- Logs show: `{"input": can I book a trip, ...}` instead of `{"input": "can I book a trip", ...}`

**See also:** [Pattern #13: ConditionAgent Variable Format](#conditionagent-variable-format-pattern-13) in FAILURE_PATTERNS.md

#### Critical: Output Anchors

The condition node creates **one output anchor for each scenario** with a specific structure.

**Output Anchor Format:**

```json
{
  "id": "conditionAgentAgentflow_[N]-output-[INDEX]",
  "label": [INDEX],                    // Numeric: 0, 1, 2, etc.
  "name": [INDEX],                     // Same as label
  "description": "[SCENARIO_TEXT]"     // Human-readable scenario description
}
```

**Rules:**
- `id` format: `[nodeId]-output-[index]` (index is zero-based)
- `label` and `name`: Always numeric index (0, 1, 2, ...)
- `description`: Should match or summarize the scenario text for clarity

**Example:**

For a scenario: `{"scenario": "Payroll and Compensation"}`

The output anchor is:
```json
{
  "id": "conditionAgentAgentflow_0-output-0",
  "label": 0,
  "name": 0,
  "description": "Payroll and Compensation"
}
```

**Index Mapping:**
- Scenario at index 0 → output-0
- Scenario at index 1 → output-1
- Scenario at index 2 → output-2
- etc.

**Important:** Each output anchor connects via an edge to the appropriate specialized agent. Multiple outputs CAN connect to the same agent (see "Multiple Scenarios to Same Agent" pattern).

---

### 3. ExecuteFlow Node (executeFlowAgentflow)

Enables modular workflow composition by calling sub-flows (child workflows) from a parent workflow. Used for chaining, conditional sub-flow execution, and hierarchical agent architectures.

#### Complete Structure

```json
{
  "id": "executeFlowAgentflow_[NUMBER]",
  "position": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "data": {
    "id": "executeFlowAgentflow_[NUMBER]",
    "label": "[Descriptive Label]",  // e.g., "Validate Input", "Process Data"
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
        "id": "executeFlowAgentflow_[N]-input-executeFlowSelectedFlow-asyncOptions"
      },
      {
        "label": "Input (JSON)",
        "name": "executeFlowInput",
        "type": "json",
        "acceptVariable": true,
        "id": "executeFlowAgentflow_[N]-input-executeFlowInput-json"
      },
      {
        "label": "Override Config",
        "name": "executeFlowOverrideConfig",
        "type": "json",
        "optional": true,
        "id": "executeFlowAgentflow_[N]-input-executeFlowOverrideConfig-json"
      },
      {
        "label": "Base URL",
        "name": "executeFlowBaseURL",
        "type": "string",
        "optional": true,
        "id": "executeFlowAgentflow_[N]-input-executeFlowBaseURL-string"
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
        "id": "executeFlowAgentflow_[N]-input-executeFlowReturnResponseAs-options"
      },
      {
        "label": "Update State",
        "name": "executeFlowUpdateState",
        "type": "array",
        "optional": true,
        "id": "executeFlowAgentflow_[N]-input-executeFlowUpdateState-array"
      }
    ],
    "inputAnchors": [],
    "inputs": {
      "executeFlowSelectedFlow": "",
      "executeFlowInput": "{}",
      "executeFlowOverrideConfig": "",
      "executeFlowBaseURL": "",
      "executeFlowReturnResponseAs": "userMessage",
      "executeFlowUpdateState": ""
    },
    "outputAnchors": [
      {
        "id": "executeFlowAgentflow_[N]-output-executeFlowAgentflow",
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
  "positionAbsolute": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "dragging": false
}
```

#### Key Attributes

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| `name` | `"executeFlowAgentflow"` | Yes | MUST be exactly this |
| `type` | `"ExecuteFlow"` | Yes | Identifies node type |
| `color` | `"#9C27B0"` | No | Purple (distinguishes from agents/conditions) |
| `version` | `1.1` | Yes | Current stable version |
| `executeFlowSelectedFlow` | Flow ID string | Yes | Target sub-flow to execute |
| `executeFlowInput` | Valid JSON | Yes | Input data for sub-flow (minimum: `"{}"`) |
| `executeFlowReturnResponseAs` | `"userMessage"` or `"assistantMessage"` | Yes | Response attribution |

#### Input Parameters Explained

**executeFlowSelectedFlow** (Required)
- Flow ID of the sub-flow to execute
- Selected from dropdown (populated by `loadMethod: "listFlows"`)
- Empty string in generated JSON (user selects in Flowise UI)

**executeFlowInput** (Required)
- JSON object passed to sub-flow as input
- Supports variable interpolation: `"{{question}}"`, `"{{state.data}}"`
- Must be valid JSON (minimum: `"{}"`)
- Example: `"{\"query\": \"{{question}}\", \"context\": \"{{context}}\"}"`

**executeFlowReturnResponseAs** (Required)
- `"userMessage"`: Sub-flow response appears as user input to next node (default)
- `"assistantMessage"`: Sub-flow response appears as assistant message
- **Use userMessage when**: Next agent should respond TO the sub-flow output
- **Use assistantMessage when**: Sub-flow completes the interaction

**executeFlowOverrideConfig** (Optional)
- Override sub-flow configuration (e.g., temperature, max tokens)
- JSON format
- Rarely used in practice

**executeFlowBaseURL** (Optional)
- Custom base URL for sub-flow execution
- Useful for multi-instance Flowise deployments
- Usually empty (uses current instance)

**executeFlowUpdateState** (Optional)
- Array of state updates to apply after sub-flow execution
- Advanced pattern for state management
- Format: `[{"key": "value"}]`

#### Usage Examples

**Pattern A: Validation → Processing Pipeline**

```json
{
  "id": "executeFlowAgentflow_1",
  "data": {
    "label": "Validate Input",
    "name": "executeFlowAgentflow",
    "inputs": {
      "executeFlowSelectedFlow": "",  // User selects "input-validation" flow in UI
      "executeFlowInput": "{{question}}",
      "executeFlowReturnResponseAs": "userMessage"
    }
  }
}
```

**Flow**: `Start → ExecuteFlow (Validation) → Agent (Processing)`

**Use when**: Need to validate/sanitize input before main processing

---

**Pattern B: Conditional Sub-Flow Routing**

```json
{
  "id": "executeFlowAgentflow_2",
  "data": {
    "label": "Route to Specialist",
    "name": "executeFlowAgentflow",
    "inputs": {
      "executeFlowSelectedFlow": "",  // User selects flow per routing scenario
      "executeFlowInput": "{\"data\": \"{{processedData}}\", \"category\": \"{{category}}\"}",
      "executeFlowReturnResponseAs": "assistantMessage"
    }
  }
}
```

**Flow**: `Condition → ExecuteFlow (Technical) | ExecuteFlow (Billing) | ExecuteFlow (General)`

**Use when**: Different sub-flows handle different categories of requests

---

**Pattern C: Hierarchical/Nested Workflows**

```json
{
  "id": "executeFlowAgentflow_3",
  "data": {
    "label": "Department Router",
    "name": "executeFlowAgentflow",
    "inputs": {
      "executeFlowSelectedFlow": "",  // Department-level sub-flow
      "executeFlowInput": "{{question}}",
      "executeFlowReturnResponseAs": "userMessage"
    }
  }
}
```

**Flow**: `Parent Flow → ExecuteFlow (Department) → [Sub-flow contains ExecuteFlow (Team)]`

**Use when**: Multi-level hierarchical routing (organization → department → team)

**⚠️ Warning**: Avoid deep nesting (>3 levels) - causes performance degradation

---

#### Integration Patterns

**Sequential Processing Chain**
```
Start → ExecuteFlow A → ExecuteFlow B → ExecuteFlow C → Agent
```
Use for: Multi-stage data transformation pipelines

**Parallel Execution** (via Condition node)
```
Condition → ExecuteFlow A | ExecuteFlow B | ExecuteFlow C
```
Use for: Concurrent specialized processing

**Hybrid Pattern**
```
Agent → Condition → ExecuteFlow (Validation) → Agent (Process) → ExecuteFlow (Storage)
```
Use for: Complex workflows mixing agents, routing, and sub-flows

---

#### Common Pitfalls

❌ **WRONG**: Using placeholder flow IDs
```json
{
  "executeFlowSelectedFlow": "{{FLOW_ID}}"  // ❌ Will fail - not a real flow ID
}
```

✅ **CORRECT**: Empty string (user selects in UI) or real flow ID
```json
{
  "executeFlowSelectedFlow": ""  // ✅ User selects in Flowise UI
}
```

---

❌ **WRONG**: Invalid JSON in executeFlowInput
```json
{
  "executeFlowInput": "plain text here"  // ❌ Not valid JSON
}
```

✅ **CORRECT**: Valid JSON string
```json
{
  "executeFlowInput": "{\"key\": \"value\"}"  // ✅ Valid JSON
}
```

---

❌ **WRONG**: Incorrect output anchor ID format
```json
{
  "outputAnchors": [
    {"id": "executeFlowAgentflow_1-output-agent"}  // ❌ Wrong suffix
  ]
}
```

✅ **CORRECT**: Standard format
```json
{
  "outputAnchors": [
    {"id": "executeFlowAgentflow_1-output-executeFlowAgentflow"}  // ✅ Correct
  ]
}
```

---

#### Output Anchor

The ExecuteFlow node has ONE output anchor:

```json
{
  "id": "executeFlowAgentflow_[N]-output-executeFlowAgentflow",
  "name": "executeFlowAgentflow",
  "label": "Execute Flow",
  "type": "ExecuteFlow"
}
```

This output connects to the next node in the workflow (typically an agent or another ExecuteFlow).

---

### 4. Human Input Node (humanInputAgentflow)

Enables Human-in-the-Loop (HITL) checkpoints for approval workflows. Pauses execution and presents information to a human reviewer who can approve (proceed) or reject the proposed action.

#### Complete Structure

```json
{
  "id": "humanInputAgentflow_[NUMBER]",
  "position": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "data": {
    "id": "humanInputAgentflow_[NUMBER]",
    "label": "[Descriptive Label]",  // e.g., "Conflict Approval", "Budget Review"
    "version": 1.0,
    "name": "humanInputAgentflow",
    "type": "HumanInput",
    "color": "#F06292",
    "baseClasses": ["HumanInput"],
    "category": "Agent Flows",
    "description": "Request human input, approval or rejection during execution",
    "inputParams": [
      {
        "label": "Description Type",
        "name": "humanInputDescriptionType",
        "type": "options",
        "options": [
          {"label": "Fixed", "name": "fixed", "description": "Specify a fixed description"},
          {"label": "Dynamic", "name": "dynamic", "description": "Use LLM to generate a description"}
        ],
        "id": "humanInputAgentflow_[N]-input-humanInputDescriptionType-options",
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
        "id": "humanInputAgentflow_[N]-input-humanInputDescription-string",
        "display": true
      },
      {
        "label": "Model",
        "name": "humanInputModel",
        "type": "asyncOptions",
        "loadMethod": "listModels",
        "loadConfig": true,
        "show": {"humanInputDescriptionType": "dynamic"},
        "id": "humanInputAgentflow_[N]-input-humanInputModel-asyncOptions",
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
        "id": "humanInputAgentflow_[N]-input-humanInputModelPrompt-string",
        "display": false
      },
      {
        "label": "Enable Feedback",
        "name": "humanInputEnableFeedback",
        "type": "boolean",
        "default": true,
        "id": "humanInputAgentflow_[N]-input-humanInputEnableFeedback-boolean",
        "display": true
      }
    ],
    "inputAnchors": [],
    "inputs": {
      "humanInputDescriptionType": "fixed",
      "humanInputDescription": "",
      "humanInputEnableFeedback": true,
      "humanInputModelConfig": {
        "credential": "OpenAI API Key",
        "modelName": "gpt-4o-mini",
        "temperature": 0.0,
        "streaming": true,
        "humanInputModel": "chatOpenAI"
      }
    },
    "outputAnchors": [
      {
        "id": "humanInputAgentflow_[N]-output-proceed",
        "label": "Proceed",
        "name": "proceed",
        "description": "User approved"
      },
      {
        "id": "humanInputAgentflow_[N]-output-reject",
        "label": "Reject",
        "name": "reject",
        "description": "User rejected"
      }
    ],
    "outputs": {},
    "selected": false
  },
  "type": "agentFlow",
  "width": 221,
  "height": 80,
  "selected": false,
  "positionAbsolute": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "dragging": false
}
```

#### Key Attributes

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| `name` | `"humanInputAgentflow"` | Yes | MUST be exactly this |
| `type` | `"HumanInput"` | Yes | Identifies node type |
| `color` | `"#F06292"` | No | Pink (approval workflow theme) |
| `version` | `1.0` | Yes | Current stable version |
| `humanInputDescriptionType` | `"fixed"` or `"dynamic"` | Yes | Approval message generation method |
| `humanInputEnableFeedback` | `true` | Yes | Allow reviewer to provide feedback |

---

#### Variant A: Fixed Description with State Context

**Use Case**: Predefined approval messages with dynamic data from flow state

**Example - Conflict of Interest Approval**:

```json
{
  "id": "humanInputAgentflow_0",
  "data": {
    "label": "Conflict of Interest Approval",
    "name": "humanInputAgentflow",
    "inputs": {
      "humanInputDescriptionType": "fixed",
      "humanInputDescription": "⚠️ CONFLICT OF INTEREST DETECTED\n\nAction: {{ $flow.state.hitl.pending.action }}\nSummary: {{ $flow.state.hitl.pending.summary }}\nRisk Score: {{ $flow.state.hitl.pending.risk_score }}/10\nCost Estimate: ${{ $flow.state.hitl.pending.cost_estimate }}\n\nRecommended Mitigations:\n{{ $flow.state.hitl.pending.mitigations }}\n\n🔵 PROCEED: Approve with conflict waiver\n🔴 REJECT: Escalate to compliance team",
      "humanInputEnableFeedback": true
    },
    "outputAnchors": [
      {"id": "humanInputAgentflow_0-output-proceed", "label": "Proceed", "name": "proceed", "description": "User approved"},
      {"id": "humanInputAgentflow_0-output-reject", "label": "Reject", "name": "reject", "description": "User rejected"}
    ]
  }
}
```

**Template Variables**:
- `{{ $flow.state.* }}` - Access flow state data
- `{{ question }}` - Current user input
- `{{ $flow.state.hitl.pending.* }}` - Common HITL data structure

**Common State Schema for HITL**:
```json
{
  "hitl": {
    "pending": {
      "action": "string",              // Action requiring approval
      "summary": "string",             // Brief summary
      "risk_score": 1-10,              // Risk assessment
      "cost_estimate": "number",       // Financial impact
      "affected_parties": "string[]",  // Who is impacted
      "mitigations": "string",         // Recommended safeguards
      "timestamp": "ISO timestamp"
    }
  }
}
```

---

#### Variant B: Dynamic Description with LLM Generation

**Use Case**: Context-aware approval messages generated by LLM based on conversation history

**Example - Dynamic Approval with Conversation Summary**:

```json
{
  "id": "humanInputAgentflow_1",
  "data": {
    "label": "Dynamic Approval Gate",
    "name": "humanInputAgentflow",
    "inputs": {
      "humanInputDescriptionType": "dynamic",
      "humanInputModel": "chatAnthropic",
      "humanInputModelPrompt": "Summarize the conversation between the user and the assistant, reiterate the last message from the assistant, and ask if user would like to proceed or if they have any feedback.\n\nBegin by capturing the key points of the conversation, ensuring that you reflect the main ideas and themes discussed.\n\nThen, clearly reproduce the last message sent by the assistant to maintain continuity. Make sure the whole message is reproduced.\n\nFinally, ask the user if they would like to proceed, or provide any feedback on the last assistant message\n\nOutput Format The output should be structured in three parts in text:\n\nA summary of the conversation (1-3 sentences).\n\nThe last assistant message (exactly as it appeared).\n\nAsk the user if they would like to proceed, or provide any feedback on last assistant message. No other explanation and elaboration is needed.",
      "humanInputEnableFeedback": true,
      "humanInputModelConfig": {
        "credential": "Anthropic API Key",
        "modelName": "claude-sonnet-4-0",
        "temperature": 0.0,
        "streaming": true,
        "humanInputModel": "chatAnthropic"
      }
    },
    "outputAnchors": [
      {"id": "humanInputAgentflow_1-output-proceed", "label": "Proceed", "name": "proceed", "description": "User approved"},
      {"id": "humanInputAgentflow_1-output-reject", "label": "Reject", "name": "reject", "description": "User rejected"}
    ]
  }
}
```

**Model Configuration for Dynamic Mode**:
- **Temperature**: MUST be 0.0 for deterministic approval messages
- **Model**: Fast models (gpt-4o-mini, claude-sonnet-4-0)
- **Streaming**: true (standard for all agents)

---

#### Output Anchors (Critical Pattern)

The Human Input node has TWO output anchors with semantic labels:

```json
{
  "outputAnchors": [
    {
      "id": "humanInputAgentflow_[N]-output-proceed",
      "label": "Proceed",
      "name": "proceed",
      "description": "User approved"
    },
    {
      "id": "humanInputAgentflow_[N]-output-reject",
      "label": "Reject",
      "name": "reject",
      "description": "User rejected"
    }
  ]
}
```

**Rules**:
- `id` format: `[nodeId]-output-proceed` and `[nodeId]-output-reject`
- `label`: "Proceed" and "Reject" (user-visible labels)
- `name`: `proceed` and `reject` (internal identifiers)
- `description`: Explain what each path means

**Wiring Pattern**:
```
[Previous Agent]
       ↓
[Human Input Node]
   ↓proceed        ↓reject
[Approval Agent]  [Remediation Agent]
```

---

#### Wiring Examples

**Example 1: Approval → Processing, Rejection → Escalation**

```json
// Edge 1: Connect proceed to approval agent
{
  "source": "humanInputAgentflow_0",
  "sourceHandle": "humanInputAgentflow_0-output-proceed",
  "target": "agentAgentflow_1",  // Approval agent
  "targetHandle": "agentAgentflow_1",
  "data": {
    "sourceColor": "#F06292",
    "targetColor": "#4DD0E1",
    "edgeLabel": "Proceed",
    "isHumanInput": true
  }
}

// Edge 2: Connect reject to remediation agent
{
  "source": "humanInputAgentflow_0",
  "sourceHandle": "humanInputAgentflow_0-output-reject",
  "target": "agentAgentflow_2",  // Remediation agent
  "targetHandle": "agentAgentflow_2",
  "data": {
    "sourceColor": "#F06292",
    "targetColor": "#4DD0E1",
    "edgeLabel": "Reject",
    "isHumanInput": true
  }
}
```

**Note**: Set `isHumanInput: true` in edge data to indicate this edge originates from a HIL node.

---

**Example 2: Reject → Loop Back to Detection**

```json
// Reject path loops back to detector for modification
{
  "source": "humanInputAgentflow_0",
  "sourceHandle": "humanInputAgentflow_0-output-reject",
  "target": "agentAgentflow_0",  // Back to conflict detector
  "targetHandle": "agentAgentflow_0",
  "data": {
    "edgeLabel": "Modify & Retry",
    "isHumanInput": true
  }
}
```

---

#### Usage Patterns

**Pattern A: Single Approval Gate**
```
[Detection Agent] → [HIL Node] → [Proceed: Processing] | [Reject: Escalation]
```
Use for: Simple approve/reject decisions

---

**Pattern B: Multi-Stage Approval**
```
[Agent A] → [HIL 1] → [Agent B] → [HIL 2] → [Agent C]
```
Use for: Multi-level approval workflows (e.g., L1 approval → L2 approval)

---

**Pattern C: Conditional HIL (via Condition Node)**
```
[Condition] → [High Risk: HIL Node] | [Low Risk: Auto-Approve Agent]
```
Use for: Only pause for high-risk scenarios, auto-approve low-risk

---

**Pattern D: Rejection Loop**
```
[Detection] → [HIL] → [Proceed: Approve] | [Reject: Back to Detection]
```
Use for: Iterative refinement workflows

---

#### Common Use Cases

**1. Conflict of Interest Approval**
- Detection agent identifies conflict
- HIL node presents conflict details and severity
- Proceed → Generate waiver and approve
- Reject → Escalate to compliance team

**2. Budget Approval**
- Cost estimation agent calculates expense
- HIL node shows cost breakdown
- Proceed → Execute purchase
- Reject → Return to cost reduction agent

**3. Email Sending Approval**
- Email draft agent composes message
- HIL node shows email preview
- Proceed → Send email
- Reject → Revise draft

**4. Data Deletion Approval**
- Deletion agent identifies records to remove
- HIL node lists what will be deleted
- Proceed → Execute deletion
- Reject → Cancel operation

---

#### Best Practices

**✅ DO**:
- Use Fixed Description when approval context is known in advance
- Use Dynamic Description when context varies significantly
- Set temperature to 0.0 for deterministic approval messages
- Populate flow state BEFORE the HIL node (in previous agent)
- Use semantic labels ("Proceed"/"Reject", not "Output 0"/"Output 1")
- Enable feedback to capture human reviewer notes
- Wire both proceed AND reject paths (never leave reject path disconnected)

**❌ DON'T**:
- Use generic "Human Input" labels (use "Proceed"/"Reject")
- Leave reject path unwired (always handle rejections)
- Use high temperature for dynamic mode (causes inconsistent messages)
- Put complex logic in the HIL node (handle in agents before/after)
- Use HIL for simple informational messages (use regular agent responses)

---

#### Integration with Flow State

**Populating State for HIL Node**:

The agent BEFORE the HIL node should populate flow state:

```json
{
  "label": "Agent.ConflictDetector",
  "inputs": {
    "agentUpdateState": [
      {"key": "hitl.pending.action", "value": "{{ detected_action }}"},
      {"key": "hitl.pending.summary", "value": "{{ conflict_summary }}"},
      {"key": "hitl.pending.risk_score", "value": "{{ calculated_risk }}"},
      {"key": "hitl.pending.mitigations", "value": "{{ suggested_mitigations }}"}
    ]
  }
}
```

Then HIL node references these values in its description.

---

#### Common Pitfalls

❌ **WRONG**: Generic output labels
```json
{
  "outputAnchors": [
    {"id": "...-output-0", "label": "Human Input", "name": "humanInputAgentflow"},
    {"id": "...-output-1", "label": "Human Input", "name": "humanInputAgentflow"}
  ]
}
```

✅ **CORRECT**: Semantic labels
```json
{
  "outputAnchors": [
    {"id": "...-output-proceed", "label": "Proceed", "name": "proceed", "description": "User approved"},
    {"id": "...-output-reject", "label": "Reject", "name": "reject", "description": "User rejected"}
  ]
}
```

---

❌ **WRONG**: Disconnected reject path
```
[HIL Node] → proceed → [Agent]
           → reject → [NOTHING]
```

✅ **CORRECT**: Both paths wired
```
[HIL Node] → proceed → [Approval Agent]
           → reject → [Remediation Agent]
```

---

❌ **WRONG**: Empty description
```json
{
  "humanInputDescription": "Approve?"
}
```

✅ **CORRECT**: Context-rich description
```json
{
  "humanInputDescription": "⚠️ HIGH-RISK ACTION\n\nAction: {{ $flow.state.hitl.pending.action }}\nRisk: {{ $flow.state.hitl.pending.risk_score }}/10\n\nDetails:\n{{ $flow.state.hitl.pending.summary }}\n\nProceed?"
}
```

---

### 5. Loop Node (conditionAgentAgentflow)

Enables iterative workflows with retry logic, validation loops, and approval-with-revision patterns. The Loop Node is a specialized ConditionAgent that controls workflow loops with four deterministic exit paths.

#### Complete Structure

```json
{
  "id": "conditionAgentAgentflow_12",
  "position": { "x": 0, "y": 0 },
  "data": {
    "id": "conditionAgentAgentflow_12",
    "label": "Loop Control",
    "version": 1.1,
    "name": "conditionAgentAgentflow",
    "type": "ConditionAgent",
    "color": "#ffcc80",
    "baseClasses": ["ConditionAgent"],
    "category": "Agent Flows",
    "description": "Generic loop controller: Continue ↺, Exit (Approved/Validated), Exit (Max Iterations), or Escalate to Human.",
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
        "rows": 10
      },
      {
        "label": "Input (Loop Context)",
        "name": "conditionAgentInput",
        "type": "string",
        "acceptVariable": true
      },
      {
        "label": "Scenarios",
        "name": "conditionAgentScenarios",
        "type": "array"
      },
      {
        "label": "Max Iterations",
        "name": "loopMaxIterations",
        "type": "number",
        "default": 3
      },
      {
        "label": "Iteration Counter Key",
        "name": "loopIterationKey",
        "type": "string",
        "default": ".context-foundry/loop-iteration-count.txt"
      },
      {
        "label": "Delay Between Iterations (ms)",
        "name": "loopDelayMs",
        "type": "number",
        "default": 0
      },
      {
        "label": "Exit-On Approval States",
        "name": "exitOnApprovalStates",
        "type": "array"
      }
    ],
    "inputAnchors": [],
    "inputs": {
      "conditionAgentModel": "chatAnthropic",
      "conditionAgentInstructions": "You are the Loop Controller for enterprise workflows (promotion, validation, refinement). Decide ONE route:\n\nROUTES\n0 = CONTINUE (loop back for revision/correction)\n1 = EXIT: APPROVED/VALIDATED (success)\n2 = EXIT: MAX ITERATIONS (stop with failure)\n3 = ESCALATE TO HUMAN (handoff required)\n\nSIGNALS (from input JSON):\n- iteration_count (int)\n- max_iterations (int)\n- approval_state (e.g., PENDING, REJECTED, APPROVED)\n- validation_errors (array)\n- quality_score (0-100)\n- required_fields_missing (bool)\n- notes/comments (string)\n- exit_on_approval_states (array of strings)\n\nLOGIC (deterministic, then judgement):\n- If approval_state ∈ exit_on_approval_states → route 1\n- Else if iteration_count >= max_iterations → route 2\n- Else if validation_errors present OR required_fields_missing OR quality_score < 80 OR approval_state == \"REJECTED\" → route 0\n- Else if ambiguous/blocker needing human decision (e.g., policy conflict, missing policy mapping) → route 3\n- Otherwise → route 0\n\nReturn ONLY a compact JSON object: {\"route\": <0|1|2|3>, \"reason\": \"...\"}. No extra text.",
      "conditionAgentInput": "{{ loop_context }}",
      "conditionAgentScenarios": [
        { "scenario": "Continue: rejection or failed validation → requestor/agent revises and resubmits" },
        { "scenario": "Exit (Approved/Validated): passed gates/approvals" },
        { "scenario": "Exit (Max Iterations): safety stop after too many retries" },
        { "scenario": "Escalate to Human: ambiguous policy or high-risk decision" }
      ],
      "loopMaxIterations": 3,
      "loopIterationKey": ".context-foundry/loop-iteration-count.txt",
      "loopDelayMs": 0,
      "exitOnApprovalStates": ["APPROVED", "VALIDATED"],
      "conditionAgentModelConfig": {
        "credential": "Anthropic API Key",
        "modelName": "claude-sonnet-4-0",
        "temperature": 0.1,
        "streaming": true,
        "conditionAgentModel": "chatAnthropic"
      }
    },
    "outputAnchors": [
      {
        "id": "conditionAgentAgentflow_12-output-0",
        "label": 0,
        "name": 0,
        "description": "Continue (Loop Back)"
      },
      {
        "id": "conditionAgentAgentflow_12-output-1",
        "label": 1,
        "name": 1,
        "description": "Exit: Approved/Validated"
      },
      {
        "id": "conditionAgentAgentflow_12-output-2",
        "label": 2,
        "name": 2,
        "description": "Exit: Max Iterations"
      },
      {
        "id": "conditionAgentAgentflow_12-output-3",
        "label": 3,
        "name": 3,
        "description": "Exit: Escalate to Human"
      }
    ],
    "outputs": {},
    "selected": false
  },
  "type": "agentFlow",
  "width": 240,
  "height": 120
}
```

#### Key Attributes

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `"conditionAgentAgentflow"` | Same as Condition node (specialized usage) |
| `type` | `"ConditionAgent"` | Uses ConditionAgent for routing |
| `color` | `"#ffcc80"` | Orange (distinguishes from standard routing) |
| `version` | `1.1` | Current stable version |

#### Input Parameters Explained

**loopMaxIterations** (Required)
- Maximum number of loop iterations before forced exit
- Prevents infinite loops
- Recommended: 3-5 for production workflows
- Example: `3` (approval workflows), `5` (validation loops)

**loopIterationKey** (Required)
- Flow state key for tracking iteration count
- Default: `.context-foundry/loop-iteration-count.txt`
- Must be incremented by agent BEFORE loop node
- Used to enforce max iterations limit

**loopDelayMs** (Optional)
- Milliseconds to wait between iterations
- Default: `0` (no delay)
- Use when rate-limiting external API calls
- Example: `1000` (1 second delay)

**exitOnApprovalStates** (Required)
- Array of approval states that trigger successful exit (route 1)
- Common values: `["APPROVED", "VALIDATED", "PASSED", "COMPLETED"]`
- Checked first in routing logic
- Case-sensitive string matching

**conditionAgentInput** (Required)
- Variable containing loop context (JSON string)
- Must include: `iteration_count`, `max_iterations`, `approval_state`
- Optional: `validation_errors`, `quality_score`, `notes`
- Example: `"{{ loop_context }}"` from flow state

**conditionAgentInstructions** (Required)
- Routing logic for loop decisions
- Must be deterministic (use low temperature 0.1-0.2)
- Should include all 4 routes explicitly
- Template provided in LOOP-NODE-TEMPLATE.json

#### Output Anchors (Four Routes)

The Loop Node has FOUR output anchors with semantic labels:

```json
{
  "outputAnchors": [
    {
      "id": "conditionAgentAgentflow_12-output-0",
      "label": 0,
      "name": 0,
      "description": "Continue (Loop Back)"
    },
    {
      "id": "conditionAgentAgentflow_12-output-1",
      "label": 1,
      "name": 1,
      "description": "Exit: Approved/Validated"
    },
    {
      "id": "conditionAgentAgentflow_12-output-2",
      "label": 2,
      "name": 2,
      "description": "Exit: Max Iterations"
    },
    {
      "id": "conditionAgentAgentflow_12-output-3",
      "label": 3,
      "name": 3,
      "description": "Exit: Escalate to Human"
    }
  ]
}
```

**Routes**:
- **Route 0 (Continue)**: Loop back to revision/correction agent for another iteration
- **Route 1 (Exit Approved)**: Success exit, proceed to next workflow stage
- **Route 2 (Exit Max Iters)**: Failure exit, max iterations reached, stop with error
- **Route 3 (Escalate)**: Edge case exit, send to human review for decision

#### Routing Logic (Deterministic)

The Loop Node uses **deterministic logic** with this precedence:

1. **Check approval_state ∈ exitOnApprovalStates** → Route 1 (Exit Approved)
2. **Check iteration_count >= max_iterations** → Route 2 (Exit Max Iterations)
3. **Check validation_errors OR required_fields_missing OR quality_score < 80 OR approval_state == "REJECTED"** → Route 0 (Continue)
4. **Check ambiguous/blocker conditions** → Route 3 (Escalate to Human)
5. **Default** → Route 0 (Continue)

**Critical**: Use temperature 0.1-0.2 for consistent routing decisions.

---

#### Usage Patterns

**Pattern A: Approval with Revision Loop**

```
[Submission Agent] → [HIL Approval Gate] → [Reject Path] → [Loop Node]
                                                                  ↓
                                    0: Loop Back to Revision Agent ↺
                                    1: Exit (Approved) → Next Stage
                                    2: Exit (Max Iters) → Failure Handler
                                    3: Escalate → Executive Review
```

**Use When**: Approvals that allow revision and resubmission (promotion nominations, document approvals)

**Example - Promotion Nomination**:
```
Manager submits → Local Leadership HIL → Rejected
  ↓
Loop Node checks iteration (1 of 3)
  ↓
Route 0: Back to Manager → Revise justification → Resubmit
  ↓
Loop Node checks iteration (2 of 3)
  ↓
Approved → Route 1: Continue to Final Approval
```

---

**Pattern B: Validation with Correction Loop**

```
[User Input] → [Validator Agent] → [Loop Node]
                                        ↓
                      0: Back to Input Form ↺
                      1: Exit (Valid) → Processing Agent
                      2: Exit (Max Iters) → Error Display
                      3: Escalate → Manual Review
```

**Use When**: Data validation that requires user correction (form validation, data quality checks)

**Example - Document Validation**:
```
User uploads document → Validator finds errors
  ↓
Loop Node (iteration 1 of 5)
  ↓
Route 0: Back to User → Display errors → User corrects → Resubmit
  ↓
Still has errors → Loop Node (iteration 2 of 5)
  ↓
Route 0: Back to User again
  ↓
No errors → Route 1: Continue to Processing
```

---

**Pattern C: Quality Gate with Retry**

```
[Builder Agent] → [Quality Check Agent] → [Loop Node]
                                              ↓
                            0: Back to Builder Agent ↺
                            1: Exit (Passed) → Deploy
                            2: Exit (Max Iters) → Mark Failed
                            3: Escalate → Manual QA Review
```

**Use When**: Automated quality checks with retry logic (code quality, test execution, build validation)

**Example - Code Quality Loop**:
```
Builder generates code → Quality checker scores 65/100
  ↓
Loop Node (iteration 1 of 3, score < 80)
  ↓
Route 0: Back to Builder → Improve code → Re-check
  ↓
Quality checker scores 85/100
  ↓
Route 1: Quality passed → Continue to Deploy
```

---

#### Wiring Examples

**Example 1: Approval Loop with All Four Paths**

```json
// Edge 1: Validator to Loop Control
{
  "source": "agentAgentflow_1",
  "sourceHandle": "agentAgentflow_1-output-agentAgentflow-Agent|AgentExecutor",
  "target": "conditionAgentAgentflow_12",
  "targetHandle": "conditionAgentAgentflow_12",
  "type": "agentFlow"
}

// Edge 2: Loop Back to Revision Agent (Route 0)
{
  "source": "conditionAgentAgentflow_12",
  "sourceHandle": "conditionAgentAgentflow_12-output-0",
  "target": "agentAgentflow_2",
  "targetHandle": "agentAgentflow_2",
  "data": {
    "edgeLabel": "Continue (Retry)",
    "sourceColor": "#ffcc80",
    "targetColor": "#4DD0E1"
  },
  "type": "agentFlow"
}

// Edge 3: Exit Approved to Next Stage (Route 1)
{
  "source": "conditionAgentAgentflow_12",
  "sourceHandle": "conditionAgentAgentflow_12-output-1",
  "target": "agentAgentflow_3",
  "targetHandle": "agentAgentflow_3",
  "data": {
    "edgeLabel": "Approved",
    "sourceColor": "#ffcc80",
    "targetColor": "#4DD0E1"
  },
  "type": "agentFlow"
}

// Edge 4: Exit Max Iterations to Failure Handler (Route 2)
{
  "source": "conditionAgentAgentflow_12",
  "sourceHandle": "conditionAgentAgentflow_12-output-2",
  "target": "agentAgentflow_4",
  "targetHandle": "agentAgentflow_4",
  "data": {
    "edgeLabel": "Max Iterations",
    "sourceColor": "#ffcc80",
    "targetColor": "#4DD0E1"
  },
  "type": "agentFlow"
}

// Edge 5: Escalate to Human Review (Route 3)
{
  "source": "conditionAgentAgentflow_12",
  "sourceHandle": "conditionAgentAgentflow_12-output-3",
  "target": "humanInputAgentflow_0",
  "targetHandle": "humanInputAgentflow_0",
  "data": {
    "edgeLabel": "Escalate",
    "sourceColor": "#ffcc80",
    "targetColor": "#F06292"
  },
  "type": "agentFlow"
}
```

---

**Example 2: HIL Rejection → Loop Node**

```json
// HIL Reject Path to Loop Control
{
  "source": "humanInputAgentflow_0",
  "sourceHandle": "humanInputAgentflow_0-output-reject",
  "target": "conditionAgentAgentflow_12",
  "targetHandle": "conditionAgentAgentflow_12",
  "data": {
    "edgeLabel": "Rejected",
    "isHumanInput": true,
    "sourceColor": "#F06292",
    "targetColor": "#ffcc80"
  },
  "type": "agentFlow"
}

// Loop Back to Revision
{
  "source": "conditionAgentAgentflow_12",
  "sourceHandle": "conditionAgentAgentflow_12-output-0",
  "target": "agentAgentflow_1",
  "targetHandle": "agentAgentflow_1",
  "data": {
    "edgeLabel": "Revise & Resubmit"
  },
  "type": "agentFlow"
}
```

---

#### State Management

**Loop Context Structure**:

The agent BEFORE the Loop Node must populate flow state with loop context:

```json
{
  "agentUpdateState": [
    {"key": "loop.iteration_count", "value": "{{ $flow.state.loop.iteration_count + 1 }}"},
    {"key": "loop_context", "value": "{\"iteration_count\": {{ $flow.state.loop.iteration_count }}, \"max_iterations\": 3, \"approval_state\": \"{{ approval_state }}\", \"validation_errors\": {{ validation_errors }}, \"notes\": \"{{ notes }}\"}"}
  ]
}
```

**Required Fields in loop_context**:
- `iteration_count` (integer) - Current iteration number
- `max_iterations` (integer) - Maximum allowed iterations
- `approval_state` (string) - Current state (PENDING/REJECTED/APPROVED/VALIDATED)

**Optional Fields**:
- `validation_errors` (array) - List of validation errors
- `quality_score` (integer 0-100) - Quality metric
- `required_fields_missing` (boolean) - Validation flag
- `notes` (string) - Human-readable context

**State Reset**:

When loop exits successfully (route 1), reset the iteration counter:

```json
{
  "agentUpdateState": [
    {"key": "loop.iteration_count", "value": "0"}
  ]
}
```

---

#### Integration with HIL Gates

Loop Nodes complement HIL gates by handling rejection paths:

**Combined Pattern**:
```
[Submission Agent] → [HIL Approval Gate]
                         ↓ proceed → [Final Stage]
                         ↓ reject  → [Loop Node]
                                        ↓
                                  0: Revise & Resubmit ↺
                                  1: Approved (no loop needed)
                                  2: Max Iters → Abandon
                                  3: Escalate → Executive Review
```

**Benefits**:
- ✅ Enables iterative refinement after rejection
- ✅ Prevents infinite resubmission loops
- ✅ Provides escalation path for edge cases
- ✅ Tracks attempt count for audit trail

---

#### Common Pitfalls

❌ **WRONG**: No max iterations limit
```json
{
  "loopMaxIterations": ""  // ❌ Missing limit, risk of infinite loop
}
```

✅ **CORRECT**: Set reasonable limit
```json
{
  "loopMaxIterations": 3  // ✅ Prevents infinite loops
}
```

---

❌ **WRONG**: High temperature causes non-deterministic routing
```json
{
  "temperature": 0.9  // ❌ Random routing decisions
}
```

✅ **CORRECT**: Low temperature for deterministic logic
```json
{
  "temperature": 0.1  // ✅ Consistent routing
}
```

---

❌ **WRONG**: Missing iteration count tracking
```json
{
  "conditionAgentInput": "{{ question }}"  // ❌ No iteration count
}
```

✅ **CORRECT**: Include iteration count in context
```json
{
  "conditionAgentInput": "{{ loop_context }}",  // ✅ Contains iteration_count
  "agentUpdateState": [
    {"key": "loop.iteration_count", "value": "{{ $flow.state.loop.iteration_count + 1 }}"}
  ]
}
```

---

❌ **WRONG**: Unwired escalation path
```json
// Only routes 0, 1, 2 wired, route 3 disconnected
```

✅ **CORRECT**: Wire all four routes
```json
// Route 0: Loop back
// Route 1: Exit approved
// Route 2: Exit max iters
// Route 3: Escalate to human  // ✅ Always wire this path
```

---

#### Best Practices

**✅ DO**:
- Set loopMaxIterations to 3-5 for production
- Use temperature 0.1-0.2 for deterministic routing
- Track iteration_count in flow state
- Define clear exitOnApprovalStates
- Wire all four output paths
- Reset iteration counter on successful exit
- Include loop context in audit trail

**❌ DON'T**:
- Allow unlimited iterations (always set max)
- Use high temperature (causes random routing)
- Skip state tracking (loop can't enforce limits)
- Leave escalation path unwired (edge cases need handling)
- Use vague approval states (be explicit: "APPROVED" not "OK")
- Nest loops inside loops (causes complexity explosion)

---

### 6. Sticky Note Node (stickyNoteAgentflow)

A documentation and annotation node that helps explain and document parts of the agent flow. Sticky notes are purely informational - they don't execute logic or connect to other nodes via edges. They're used to make flows more readable and maintainable for humans.

#### Complete Structure

```json
{
  "id": "stickyNoteAgentflow_[NUMBER]",
  "position": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "data": {
    "id": "stickyNoteAgentflow_[NUMBER]",
    "label": "Sticky Note",
    "version": 1,
    "name": "stickyNoteAgentflow",
    "type": "StickyNote",
    "color": "#fee440",
    "baseClasses": ["StickyNote"],
    "category": "Agent Flows",
    "description": "Add notes to the agent flow",
    "inputParams": [
      {
        "label": "",
        "name": "note",
        "type": "string",
        "rows": 1,
        "placeholder": "Type something here",
        "optional": true,
        "id": "stickyNoteAgentflow_[N]-input-note-string",
        "display": true
      }
    ],
    "inputAnchors": [],
    "inputs": {
      "note": "Your documentation text here"
    },
    "outputAnchors": [
      {
        "id": "stickyNoteAgentflow_[N]-output-stickyNoteAgentflow",
        "label": "Sticky Note",
        "name": "stickyNoteAgentflow"
      }
    ],
    "outputs": {},
    "selected": false
  },
  "type": "stickyNote",
  "width": 215,
  "height": 122,
  "positionAbsolute": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "selected": false,
  "dragging": false
}
```

#### Key Attributes

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `"stickyNoteAgentflow"` | MUST be exactly this |
| `type` | `"StickyNote"` | Identifies as sticky note node |
| `color` | `"#fee440"` | Yellow (standard sticky note color) |
| `version` | `1` | Current stable version |
| `width` | `215` | Standard width |
| `height` | `122` | Standard height (can vary based on content) |

#### Input Parameters

**note** (Optional)
- The text content of the sticky note
- Can be multi-line (use `\n` for line breaks)
- Supports markdown-style formatting in some Flowise versions
- Maximum recommended length: 200-300 characters for readability

#### Usage Guidelines

**When to Use Sticky Notes:**
- ✅ Explaining complex routing logic in Condition nodes
- ✅ Documenting why a specific agent configuration was chosen
- ✅ Providing context about external system integrations
- ✅ Noting important considerations for human reviewers
- ✅ Marking areas that need future enhancement
- ✅ Explaining non-obvious workflow decisions

**When NOT to Use Sticky Notes:**
- ❌ As a substitute for clear agent labels
- ❌ To document every single node (creates visual clutter)
- ❌ For information that should be in system prompts
- ❌ As TODO markers (use proper project management tools)

#### Placement Best Practices

**Positioning Relative to Nodes:**

1. **Above Node**: Use when explaining what happens BEFORE execution
   ```
   [Sticky Note: "User input validated here"]
          ↓
   [Validation Agent]
   ```

2. **Below Node**: Use when explaining OUTCOMES or results
   ```
   [Decision Node]
          ↓
   [Sticky Note: "Routes to 3 possible agents based on intent"]
   ```

3. **To the Side**: Use for general context or warnings
   ```
   [Agent Node] ← [Sticky Note: "⚠️ Requires API key in config"]
   ```

**Position Offsets:**
- Above: Typically `y_offset = -150` to `-180` from target node
- Below: Typically `y_offset = +550` to `+600` from target node
- Left side: Typically `x_offset = -300` from target node
- Right side: Typically `x_offset = +350` from target node

#### Content Templates

**Template 1: Explaining Node Purpose**
```json
{
  "inputs": {
    "note": "PURPOSE:\nThis agent handles all payroll-related inquiries including:\n- Direct deposit setup\n- Pay stub access\n- Tax withholding questions"
  }
}
```

**Template 2: Warning/Caution**
```json
{
  "inputs": {
    "note": "IMPORTANT:\nThis node requires the 'payroll_api' tool to be configured in Flowise.\nSee INTEGRATION_GUIDE.md for setup instructions."
  }
}
```

**Template 3: Routing Logic Explanation**
```json
{
  "inputs": {
    "note": "ROUTING LOGIC:\nCondition outputs:\n0 = Navigation questions\n1 = Payroll questions\n2 = Benefits questions\n3 = General help (fallback)"
  }
}
```

**Template 4: Configuration Note**
```json
{
  "inputs": {
    "note": "CONFIGURATION:\nTemperature set to 0.1 for deterministic routing.\nDO NOT increase above 0.3 or routing becomes inconsistent."
  }
}
```

**Template 5: Human Action Required**
```json
{
  "inputs": {
    "note": "MANUAL SETUP REQUIRED:\nAfter importing:\n1. Select the 'employee-data' document store\n2. Configure OpenAI API credential\n3. Test with sample query"
  }
}
```

#### Integration with Agent Flows

**Pattern A: Documenting Complex Flows**
```
[Start] → [Sticky: "Main entry point"]
   ↓
[Condition] → [Sticky: "Routes based on user intent - see routing table below"]
   ↓
[Agent A] → [Sticky: "Handles technical support - requires tech_support_tools"]
```

**Pattern B: Explaining Approval Workflows**
```
[Detection Agent]
   ↓
[Sticky: "If conflict detected, pauses here for human review"]
   ↓
[HIL Approval Gate]
   ↓proceed / ↓reject
```

**Pattern C: Warning About External Dependencies**
```
[API Integration Agent] ← [Sticky: "WARNING: Requires external API\nEndpoint: https://api.example.com\nAuth: Bearer token in config"]
```

#### Visual Layout Recommendations

**Spacing:**
- Minimum 50px between sticky note and target node (prevents overlap)
- Align sticky notes horizontally when possible (cleaner look)
- Group related sticky notes together

**Quantity Guidelines:**
- Simple flow (3-5 nodes): 1-2 sticky notes maximum
- Medium flow (6-10 nodes): 2-4 sticky notes
- Complex flow (11+ nodes): 4-6 sticky notes maximum

**Priority Levels:**
- Critical (warnings, required actions): Use ALL CAPS headers
- Important (configuration notes): Clear headers with colons
- Informational (explanations): Concise descriptions

#### Common Use Cases

**1. Explaining Condition Node Routing**
```json
{
  "id": "stickyNoteAgentflow_0",
  "position": {"x": 800, "y": 50},
  "data": {
    "inputs": {
      "note": "INTENT ROUTING:\nScenario 0 → Navigation Agent\nScenario 1 → Payroll Agent\nScenario 2 → Benefits Agent\nScenario 3 → General Help\n\nSee AGENT_PATTERN_REFERENCE.md for routing logic details."
    }
  }
}
```

**2. Documenting HIL Gates**
```json
{
  "id": "stickyNoteAgentflow_1",
  "position": {"x": 500, "y": 600},
  "data": {
    "inputs": {
      "note": "HUMAN APPROVAL REQUIRED:\nPauses workflow for conflict of interest review.\n\nProceed = Continue with waiver\nReject = Escalate to compliance team"
    }
  }
}
```

**3. Configuration Requirements**
```json
{
  "id": "stickyNoteAgentflow_2",
  "position": {"x": 200, "y": -100},
  "data": {
    "inputs": {
      "note": "SETUP CHECKLIST:\n- Configure OpenAI API key\n- Select 'workday_docs' document store\n- Enable web_search_preview tool\n- Set memory to 'allMessages'"
    }
  }
}
```

**4. External System Integration**
```json
{
  "id": "stickyNoteAgentflow_3",
  "position": {"x": 1000, "y": 300},
  "data": {
    "inputs": {
      "note": "EXTERNAL API INTEGRATION:\nConnects to: Workday HCM API\nAuth: OAuth 2.0 (configured in Tools)\nRate limit: 100 requests/minute\nTimeout: 30 seconds"
    }
  }
}
```

#### Technical Details

**No Edge Connections:**
Sticky notes do NOT connect to other nodes via edges. They are standalone annotation elements.

❌ **WRONG**: Creating edges from/to sticky notes
```json
{
  "edges": [
    {
      "source": "stickyNoteAgentflow_0",
      "target": "agentAgentflow_1"  // ❌ Invalid - sticky notes don't connect
    }
  ]
}
```

✅ **CORRECT**: Sticky notes are independent
```json
{
  "nodes": [
    {"id": "stickyNoteAgentflow_0", ...},  // ✅ Standalone documentation
    {"id": "agentAgentflow_1", ...}
  ],
  "edges": []  // No edges to/from sticky note
}
```

**Output Anchors:**
While sticky notes have an `outputAnchors` array (for internal Flowise compatibility), these anchors are never used in practice. The output anchor exists for UI rendering purposes only.

#### Best Practices Summary

**✅ DO:**
- Use sticky notes sparingly (quality over quantity)
- Place notes strategically near complex logic
- Keep text concise (under 300 characters)
- Use clear ALL CAPS headers for categorization (PURPOSE, ROUTING LOGIC, CONFIGURATION, etc.)
- Explain WHY, not just WHAT
- Document manual setup steps required after import
- Warn about external dependencies

**❌ DON'T:**
- Add sticky notes to every node (creates clutter)
- Use as a substitute for clear agent labels
- Include implementation details that belong in code
- Create edges to/from sticky notes
- Overlap sticky notes with functional nodes
- Use excessive formatting or very long text

#### Example: Well-Documented Flow

```json
{
  "nodes": [
    {
      "id": "startAgentflow_0",
      "data": {"label": "Start", ...}
    },
    {
      "id": "stickyNoteAgentflow_0",
      "position": {"x": -164, "y": -50},
      "data": {
        "inputs": {
          "note": "WORKFLOW PURPOSE:\nMulti-agent HCM support system.\nRoutes user queries to specialized agents based on intent detection."
        }
      }
    },
    {
      "id": "conditionAgentAgentflow_0",
      "data": {"label": "Detect User Intention", ...}
    },
    {
      "id": "stickyNoteAgentflow_1",
      "position": {"x": 500, "y": 50},
      "data": {
        "inputs": {
          "note": "ROUTING LOGIC:\n0=Navigation | 1=Payroll | 2=Benefits\nTemp=0.2 for consistent routing"
        }
      }
    },
    {
      "id": "agentAgentflow_0",
      "data": {"label": "Agent.Navigation", ...}
    },
    {
      "id": "stickyNoteAgentflow_2",
      "position": {"x": 800, "y": 350},
      "data": {
        "inputs": {
          "note": "POST-IMPORT SETUP:\nConfigure 'workday_nav_docs' document store for this agent."
        }
      }
    }
  ],
  "edges": [
    // Edge connections between functional nodes only, no edges to sticky notes
  ]
}
```

---

## Agent Input Parameters

The `inputParams` array defines what configuration options the agent supports. This is the **schema** - actual values go in the `inputs` object.

### Essential Parameters

#### 1. Model Configuration

```json
{
  "label": "Model",
  "name": "agentModel",
  "type": "asyncOptions",
  "loadMethod": "listModels",
  "loadConfig": true,
  "id": "agentAgentflow_[N]-input-agentModel-asyncOptions",
  "display": true
}
```

**Critical**: Must be `asyncOptions` with `loadMethod: "listModels"` - this is how Flowise knows to populate the dropdown with available models.

---

#### 2. Agent Persona/Prompt (Messages)

```json
{
  "label": "Messages",
  "name": "agentMessages",
  "type": "array",
  "optional": true,
  "acceptVariable": true,
  "id": "agentAgentflow_[N]-input-agentMessages-array",
  "display": true,
  "array": [
    {
      "label": "Role",
      "name": "role",
      "type": "options",
      "options": [
        {"label": "System", "name": "system"},
        {"label": "Assistant", "name": "assistant"},
        {"label": "Developer", "name": "developer"},
        {"label": "User", "name": "user"}
      ],
      "default": "system",
      "id": "agentAgentflow_[N]-input-agentMessages-array-role-options"
    },
    {
      "label": "Content",
      "name": "content",
      "type": "string",
      "acceptVariable": true,
      "generateInstruction": true,
      "rows": 4,
      "id": "agentAgentflow_[N]-input-agentMessages-array-content-string"
    }
  ]
}
```

**Usage**: Define agent personality, capabilities, and boundaries in system messages.

---

#### 3. Built-in Tools

Platform-specific built-in capabilities:

```json
{
  "label": "Built-In Tools",
  "name": "agentBuiltInTools",
  "type": "multiOptions",
  "options": [
    // OpenAI Platform
    {"label": "Web Search (Preview)", "name": "web_search_preview"},
    {"label": "Code Interpreter", "name": "code_interpreter"},
    {"label": "Image Generation", "name": "image_generation"},

    // Gemini Platform
    {"label": "URL Context", "name": "urlContext"},
    {"label": "Google Search", "name": "googleSearch"},

    // Anthropic Platform
    {"label": "Web Search", "name": "web_search_20250305"},
    {"label": "Web Fetch", "name": "web_fetch_20250910"}
  ],
  "optional": true,
  "id": "agentAgentflow_[N]-input-agentBuiltInTools-multiOptions",
  "display": true
}
```

**Note**: Available tools depend on selected model platform.

---

#### 4. Custom Tools

```json
{
  "label": "Tools",
  "name": "agentTools",
  "type": "array",
  "optional": true,
  "id": "agentAgentflow_[N]-input-agentTools-array",
  "display": true,
  "array": [
    {
      "label": "Tool",
      "name": "agentSelectedTool",
      "type": "asyncOptions",
      "loadMethod": "listTools",
      "loadConfig": true,
      "id": "agentAgentflow_[N]-input-agentTools-array-agentSelectedTool-asyncOptions"
    },
    {
      "label": "Require Human Input",
      "name": "agentSelectedToolRequiresHumanInput",
      "type": "boolean",
      "optional": true,
      "id": "agentAgentflow_[N]-input-agentTools-array-agentSelectedToolRequiresHumanInput-boolean"
    }
  ]
}
```

**Usage**: Connect custom tools created in Flowise (API calls, database queries, etc.)

---

#### 5. Knowledge - Document Stores

```json
{
  "label": "Knowledge (Document Stores)",
  "name": "agentKnowledgeDocumentStores",
  "type": "array",
  "optional": true,
  "id": "agentAgentflow_[N]-input-agentKnowledgeDocumentStores-array",
  "display": true,
  "array": [
    {
      "label": "Document Store",
      "name": "documentStore",
      "type": "asyncOptions",
      "loadMethod": "listStores",
      "loadConfig": true,
      "id": "agentAgentflow_[N]-input-agentKnowledgeDocumentStores-array-documentStore-asyncOptions"
    },
    {
      "label": "Describe Knowledge",
      "name": "docStoreDescription",
      "type": "string",
      "rows": 4,
      "placeholder": "Describe what this knowledge contains and when to use it...",
      "id": "agentAgentflow_[N]-input-agentKnowledgeDocumentStores-array-docStoreDescription-string"
    },
    {
      "label": "Return Source Documents",
      "name": "returnSourceDocuments",
      "type": "boolean",
      "optional": true,
      "id": "agentAgentflow_[N]-input-agentKnowledgeDocumentStores-array-returnSourceDocuments-boolean"
    }
  ]
}
```

**Usage**: Pre-indexed document collections for RAG (Retrieval Augmented Generation).

---

#### 6. Knowledge - Vector Embeddings

```json
{
  "label": "Knowledge (Vector Embeddings)",
  "name": "agentKnowledgeVSEmbeddings",
  "type": "array",
  "optional": true,
  "id": "agentAgentflow_[N]-input-agentKnowledgeVSEmbeddings-array",
  "display": true,
  "array": [
    {
      "label": "Vector Store",
      "name": "vectorStore",
      "type": "asyncOptions",
      "loadMethod": "listVectorStores",
      "loadConfig": true,
      "id": "agentAgentflow_[N]-input-agentKnowledgeVSEmbeddings-array-vectorStore-asyncOptions"
    },
    {
      "label": "Embedding Model",
      "name": "embeddingModel",
      "type": "asyncOptions",
      "loadMethod": "listEmbeddings",
      "loadConfig": true,
      "id": "agentAgentflow_[N]-input-agentKnowledgeVSEmbeddings-array-embeddingModel-asyncOptions"
    },
    {
      "label": "Knowledge Name",
      "name": "knowledgeName",
      "type": "string",
      "placeholder": "e.g., Product Documentation",
      "id": "agentAgentflow_[N]-input-agentKnowledgeVSEmbeddings-array-knowledgeName-string"
    },
    {
      "label": "Describe Knowledge",
      "name": "knowledgeDescription",
      "type": "string",
      "rows": 4,
      "placeholder": "Describe what this knowledge contains and when to use it...",
      "id": "agentAgentflow_[N]-input-agentKnowledgeVSEmbeddings-array-knowledgeDescription-string"
    },
    {
      "label": "Return Source Documents",
      "name": "returnSourceDocuments",
      "type": "boolean",
      "optional": true,
      "id": "agentAgentflow_[N]-input-agentKnowledgeVSEmbeddings-array-returnSourceDocuments-boolean"
    }
  ]
}
```

**Usage**: Semantic search across vector-indexed content.

---

#### 7. Memory Configuration

```json
{
  "label": "Enable Memory",
  "name": "agentEnableMemory",
  "type": "boolean",
  "default": true,
  "id": "agentAgentflow_[N]-input-agentEnableMemory-boolean",
  "display": true
},
{
  "label": "Memory Type",
  "name": "agentMemoryType",
  "type": "options",
  "options": [
    {"label": "All Messages", "name": "allMessages"},
    {"label": "Window Size", "name": "windowSize"},
    {"label": "Conversation Summary", "name": "conversationSummary"},
    {"label": "Conversation Summary Buffer", "name": "conversationSummaryBuffer"}
  ],
  "default": "allMessages",
  "id": "agentAgentflow_[N]-input-agentMemoryType-options",
  "display": true,
  "additionalParams": true
},
{
  "label": "Memory Window Size",
  "name": "agentMemoryWindowSize",
  "type": "number",
  "default": 20,
  "step": 1,
  "optional": true,
  "additionalParams": true,
  "id": "agentAgentflow_[N]-input-agentMemoryWindowSize-number"
}
```

**Critical**: Memory is built INTO the agent - no separate memory nodes.

---

#### 8. State Management

```json
{
  "label": "Update Flow State",
  "name": "agentUpdateState",
  "type": "array",
  "optional": true,
  "additionalParams": true,
  "id": "agentAgentflow_[N]-input-agentUpdateState-array",
  "array": [
    {
      "label": "Key",
      "name": "key",
      "type": "asyncOptions",
      "loadMethod": "listRuntimeStateKeys",
      "loadConfig": true,
      "id": "agentAgentflow_[N]-input-agentUpdateState-array-key-asyncOptions"
    },
    {
      "label": "Value",
      "name": "value",
      "type": "string",
      "acceptVariable": true,
      "id": "agentAgentflow_[N]-input-agentUpdateState-array-value-string"
    }
  ]
}
```

**Usage**: Share state between agents in complex workflows.

---

#### 9. Additional Configuration

```json
{
  "label": "Max Iterations",
  "name": "agentMaxIterations",
  "type": "number",
  "optional": true,
  "additionalParams": true,
  "id": "agentAgentflow_[N]-input-agentMaxIterations-number"
},
{
  "label": "Variables",
  "name": "agentVariables",
  "type": "json",
  "optional": true,
  "acceptVariable": true,
  "list": true,
  "additionalParams": true,
  "id": "agentAgentflow_[N]-input-agentVariables-json"
}
```

---

## Actual Configured Values

The `inputs` object contains the actual values for the parameters defined in `inputParams`.

### Agent Persona Pattern

All agents follow this HTML-formatted persona structure:

```html
<p><em>You are an expert [ROLE] agent.</em> [SPECIFIC_CAPABILITIES_AND_BOUNDARIES]</p>
```

#### Examples

**Navigation Agent:**
```json
"agentMessages": [
  {
    "role": "system",
    "content": "<p><em>You are an expert Navigation Basics agent.</em> Provide the shortest click-path (2–5 steps) to reach Workday pages. Use official page names. If you don't know, say so.</p>"
  }
]
```

**Payroll Agent:**
```json
"agentMessages": [
  {
    "role": "system",
    "content": "<p><em>You are an expert Payroll agent.</em> Guide users through payment elections, direct deposit setup, and paycheck inquiries. Reference Workday payroll best practices.</p>"
  }
]
```

**HCM Agent:**
```json
"agentMessages": [
  {
    "role": "system",
    "content": "<p><em>You are an HCM agent.</em> Answer questions about staffing, compensation, benefits, and leave. Provide accurate Workday HCM guidance.</p>"
  }
]
```

### Model Configuration

The `agentModelConfig` object contains model-specific settings:

```json
"agentModelConfig": {
  "credential": "OpenAI API Key",  // Standard credential name in Flowise (see note below)
  "modelName": "gpt-4o-mini",      // or "claude-sonnet-4-0", "claude-opus-4-0"
  "temperature": 0.1,              // 0.1 for deterministic, 0.9 for creative
  "streaming": true,
  "maxTokens": "",
  "topP": "",
  "frequencyPenalty": "",
  "presencePenalty": "",
  "timeout": "",
  "strictToolCalling": "",
  "stopSequence": "",
  "basepath": "",
  "proxyUrl": "",
  "baseOptions": "",
  "allowImageUploads": "",
  "imageResolution": "low",
  "reasoning": "",
  "reasoningEffort": "",
  "reasoningSummary": "",
  "agentModel": "chatOpenAI"       // or "chatAnthropic", "chatGemini"
}
```

**Credential Configuration:**

The `credential` field references a credential name configured in the Flowise UI. Use these standard names:

| Model Platform | Standard Credential Name | Field Value |
|---------------|-------------------------|-------------|
| OpenAI (ChatGPT) | `"OpenAI API Key"` | `"credential": "OpenAI API Key"` |
| Anthropic (Claude) | `"Anthropic API Key"` | `"credential": "Anthropic API Key"` |
| Google (Gemini) | `"Google API Key"` | `"credential": "Google API Key"` |

**Important:**
- ✅ Use the EXACT credential name (case-sensitive) that exists in Flowise
- ✅ Create credentials once in Flowise UI, then reference by name in all agents
- ✅ This allows credential rotation without modifying workflow JSON
- ❌ Never hardcode API keys in JSON (security risk)
- ❌ Empty string `""` works but requires manual configuration after import

**Setup in Flowise:**
1. Go to Flowise UI → Credentials
2. Create new credential named exactly `"OpenAI API Key"` (for OpenAI models)
3. Paste your actual API key
4. Save
5. All agents with `"credential": "OpenAI API Key"` will automatically use it

#### Temperature Guidelines

| Temperature | Use Case | Example |
|-------------|----------|---------|
| 0.1 - 0.3 | Intent detection, routing | Condition nodes |
| 0.4 - 0.6 | Factual responses | Documentation agents |
| 0.7 - 0.9 | Creative responses | Content generation |

### Complete Input Example

```json
"inputs": {
  "agentModel": "chatOpenAI",
  "agentModelConfig": {
    "modelName": "gpt-4o-mini",
    "temperature": 0.9,
    "streaming": true,
    "imageResolution": "low",
    "agentModel": "chatOpenAI"
  },
  "agentMessages": [
    {
      "role": "system",
      "content": "<p><em>You are an expert Navigation agent.</em> Provide shortest click-paths to Workday pages.</p>"
    }
  ],
  "agentEnableMemory": true,
  "agentMemoryType": "allMessages",
  "agentMemoryWindowSize": 20,
  "agentBuiltInTools": ["web_search_preview"],
  "agentTools": [],
  "agentKnowledgeDocumentStores": [],
  "agentKnowledgeVSEmbeddings": [],
  "agentUpdateState": [],
  "agentMaxIterations": "",
  "agentVariables": ""
}
```

---

## Edges Structure

Edges connect nodes to create the agent flow.

### Standard Agent-to-Agent Connection

```json
{
  "source": "conditionAgentAgentflow_1",
  "sourceHandle": "conditionAgentAgentflow_1-output-3",
  "target": "agentAgentflow_3",
  "targetHandle": "agentAgentflow_3",
  "data": {
    "sourceColor": "#ff8fab",
    "targetColor": "#4DD0E1",
    "edgeLabel": "3",
    "isHumanInput": false
  },
  "type": "agentFlow",
  "id": "conditionAgentAgentflow_1-conditionAgentAgentflow_1-output-3-agentAgentflow_3-agentAgentflow_3"
}
```

### Key Components

| Field | Description | Example |
|-------|-------------|---------|
| `source` | ID of originating node | `"conditionAgentAgentflow_1"` |
| `sourceHandle` | Specific output anchor | `"conditionAgentAgentflow_1-output-3"` |
| `target` | ID of receiving node | `"agentAgentflow_3"` |
| `targetHandle` | Input anchor (usually node ID) | `"agentAgentflow_3"` |
| `edgeLabel` | Visual label on edge | `"3"` (scenario index) |
| `sourceColor` | Color of source node | `"#ff8fab"` (condition pink) |
| `targetColor` | Color of target node | `"#4DD0E1"` (agent teal) |

### Edge ID Pattern

```
[SOURCE_ID]-[SOURCE_HANDLE]-[TARGET_ID]-[TARGET_HANDLE]
```

Example:
```
conditionAgentAgentflow_1-conditionAgentAgentflow_1-output-3-agentAgentflow_3-agentAgentflow_3
```

---

## Critical Design Patterns

### 1. Intent Detection Architecture

```
User Input → Condition Node → [Scenario Matching] → Specialized Agent
```

**Implementation:**

1. Central `conditionAgentAgentflow` node acts as intelligent router
2. `conditionAgentScenarios` array defines all possible user intents
3. Each scenario gets a numbered output (0, 1, 2, ...)
4. Edges connect each output to the appropriate specialized agent

**Example Scenarios:**

```json
"conditionAgentScenarios": [
  {"scenario": "User is asking about Navigation"},
  {"scenario": "User is asking about HCM Core"},
  {"scenario": "User is asking about Payroll"},
  {"scenario": "User is asking about Recruiting"},
  {"scenario": "User is asking about Benefits"},
  {"scenario": "User needs general help or clarification"}
]
```

### 2. Agent Specialization

**Principle**: Each agent has a narrow, well-defined domain.

**Implementation:**
- Clear persona defining capabilities and boundaries
- Tools specific to domain
- Knowledge stores relevant to specialization
- Explicit statements about what agent can/cannot do

**Example - Payroll Agent:**

```json
{
  "label": "Agent.Payroll",
  "inputs": {
    "agentMessages": [
      {
        "role": "system",
        "content": "<p><em>You are an expert Payroll agent.</em> You handle payment elections, direct deposit, paycheck inquiries, and tax withholding questions. You do NOT handle benefits enrollment or time tracking - defer those to other agents.</p>"
      }
    ],
    "agentTools": [
      {"agentSelectedTool": "payroll_calculator"},
      {"agentSelectedTool": "direct_deposit_validator"}
    ]
  }
}
```

### 3. Scout Mode Pattern

**Definition:** Scout Mode is a design pattern for ConditionAgent instructions that enables intelligent, context-aware routing through detailed guidance and decision rules.

**Core Concept:** Instead of simple keyword matching, Scout Mode instructions teach the routing agent HOW to analyze user intent, WHEN to ask clarifying questions, and HOW to handle ambiguous or multi-domain requests.

**When to Use Scout Mode:**
- Complex routing scenarios (8+ agents)
- Overlapping domains or keywords
- Need for clarification logic
- Multi-intent handling required
- Cross-functional routing rules

**Scout Mode vs. Simple Routing:**

| Feature | Simple Routing | Scout Mode |
|---------|---------------|------------|
| Instructions | 2-3 sentences + keyword list | Structured sections with rules |
| Keywords | List only | List + context rules + priorities |
| Ambiguity | Direct to fallback | Attempt clarification first |
| Multi-intent | Not addressed | Explicit handling rules |
| Complexity | 3-5 scenarios | 8-20+ scenarios |
| Use Case | Straightforward categories | Complex overlapping domains |

---

#### Scout Mode Key Elements

**1. Detailed Routing Instructions**

Tell the condition agent HOW to analyze requests, not just WHAT to look for:

```json
"conditionAgentInstructions": "You are a routing specialist for HCM inquiries.

ANALYSIS PROCESS:
1. Identify primary keywords and their context
2. Determine user's main goal (information, action, troubleshooting)
3. Consider urgency indicators (ASAP, urgent, blocked)
4. Check for role-specific requests (manager, employee, HR admin)

Route to the agent that best matches the PRIMARY intent..."
```

**2. Keyword Mapping with Context Rules**

Map keywords to agents with conditional logic:

```
Navigation keywords: 'how do I find', 'where is', 'navigate to', 'page location'
  → Route to Navigation Agent
  → EXCEPTION: If also mentions 'permission denied' or 'access blocked', route to Security Agent instead

Payroll keywords: 'paycheck', 'direct deposit', 'payment', 'withholding', 'salary'
  → Route to Payroll Agent
  → EXCEPTION: If question is 'How do I find my paycheck?' (navigational), route to Navigation Agent
  → EXCEPTION: If about bank account update (not payment inquiry), route to Employee Data Agent
```

**3. Fallback Routing Logic**

Define escalation path when intent is unclear:

```
If intent is ambiguous or spans multiple domains:
1. Check if question is simple enough for General Help agent
2. If technical complexity detected, default to most specialized agent
3. If completely unclear, route to General Help with instruction to clarify

Priority order:
  Critical/Urgent → Route to most likely agent (bias toward action)
  Informational → Route to General Help for triage
  Troubleshooting → Route to technical specialist
```

**4. Multi-Intent Handling Rules**

Handle questions spanning multiple domains:

```
When question involves MULTIPLE domains:
- "I need to update my address for payroll and benefits"
  → Route to Employee Data Agent (PRIMARY action: address update)
  → Agent can coordinate with Payroll/Benefits as needed

- "How do I find the payroll page and what's my YTD earnings?"
  → Route to Payroll Agent (PRIMARY intent: payroll information)
  → Navigation is secondary, agent can provide page location

RULE: Choose the agent that handles the PRIMARY/CORE action, not the peripheral elements.
```

---

#### Scout Mode Example (Full Implementation)

```json
"conditionAgentInstructions": "You are an intelligent HCM routing agent using Scout Mode.

ROUTING PROCESS:
1. Analyze user input for primary intent
2. Identify keywords and context
3. Apply conditional routing rules
4. Select the most appropriate specialist

KEYWORD → AGENT MAPPING:

Navigation:
- Keywords: 'how do I find', 'where is', 'navigate to', 'locate page', 'can't find'
- Route to: Navigation Agent
- Exception: If mentions 'access denied' → Security Agent

Payroll:
- Keywords: 'paycheck', 'direct deposit', 'payment', 'salary', 'withholding', 'W-2', 'pay stub'
- Route to: Payroll Agent
- Exception: If only about 'finding' paycheck → Navigation Agent

Benefits:
- Keywords: 'health insurance', 'dental', '401k', 'retirement', 'enrollment', 'FSA', 'HSA'
- Route to: Benefits Agent
- Exception: Simple benefit questions → General Help Agent

Employee Data:
- Keywords: 'update address', 'phone number', 'emergency contact', 'personal info', 'name change'
- Route to: Employee Data Agent

Time & Attendance:
- Keywords: 'PTO', 'time off', 'vacation', 'sick leave', 'timesheet', 'hours worked'
- Route to: Time & Attendance Agent

MULTI-INTENT HANDLING:
- If question spans multiple domains, route to the agent handling the PRIMARY action
- Example: 'Update my address for payroll' → Employee Data Agent (core action: update)

FALLBACK RULES:
- If intent unclear and informational → General Help Agent
- If intent unclear but urgent → Most likely specialist (bias toward action)
- If completely ambiguous → General Help Agent with clarification request

CONTEXT AWARENESS:
- 'Urgent', 'ASAP', 'blocked' → Prioritize routing to action-capable agents
- 'How do I...', 'Where can I...' → Often navigational, check for Navigation keywords first
- Question marks with no action verbs → Likely informational, consider General Help"
```

---

#### Scout Mode Benefits

- ✅ Handles complex overlapping domains
- ✅ Reduces mis-routing and user frustration
- ✅ Enables context-aware decisions
- ✅ Provides clear escalation paths
- ✅ Supports clarification and triage logic

---

#### When NOT to Use Scout Mode

- ✗ Simple, non-overlapping categories (use basic routing instead)
- ✗ 3-5 clearly distinct scenarios
- ✗ Keywords have no overlap
- ✗ No need for clarification logic

**Simple Routing Example (No Scout Mode Needed):**

```json
"conditionAgentInstructions": "Classify the inquiry:

1. Technical Support - IT issues, system problems, errors
2. Billing - Invoices, payments, charges
3. General Help - All other inquiries

Select the most appropriate category."
```

This simple case doesn't need Scout Mode - categories are distinct, no overlap, no complex rules needed.

### 4. Multi-Level Routing

Complex workflows can chain agents together.

**Pattern:**
```
Condition → Agent A → Agent B → Agent C
```

**Use Cases:**
- Refinement workflows (rough draft → detailed review → final polish)
- Escalation workflows (L1 support → L2 support → L3 support)
- Multi-step processes (data collection → validation → processing)

**Implementation:**

Agent A's output connects to Agent B:

```json
// Edge from Agent A to Agent B
{
  "source": "agentAgentflow_1",
  "sourceHandle": "agentAgentflow_1-output-agentAgentflow-Agent|AgentExecutor",
  "target": "agentAgentflow_2",
  "targetHandle": "agentAgentflow_2",
  "type": "agentFlow"
}
```

### 5. Multiple Scenarios to Same Agent Pattern

**Valid Pattern**: Multiple scenario outputs CAN connect to the same agent.

**When to Use:**
- Different routing reasons but same handling logic
- Analytics benefit from separate scenario tracking
- User clarity through explicit scenario names vs. combined catch-all
- Future flexibility (easy to split agents later if needed)

**Example:**

```json
"conditionAgentScenarios": [
  {"scenario": "Time and Attendance Issues"},     // Output 2
  {"scenario": "Employee Data Updates"},          // Output 3
  {"scenario": "Onboarding Questions"},           // Output 4
  {"scenario": "Performance Management"}          // Output 5
]

// Edges - Multiple scenarios route to same agent:
[
  {
    "source": "conditionAgentAgentflow_0",
    "sourceHandle": "conditionAgentAgentflow_0-output-2",
    "target": "agentAgentflow_5",  // HCM General Agent
    "data": { "edgeLabel": "Time" }
  },
  {
    "source": "conditionAgentAgentflow_0",
    "sourceHandle": "conditionAgentAgentflow_0-output-3",
    "target": "agentAgentflow_5",  // SAME agent
    "data": { "edgeLabel": "Employee Data" }
  },
  {
    "source": "conditionAgentAgentflow_0",
    "sourceHandle": "conditionAgentAgentflow_0-output-4",
    "target": "agentAgentflow_5",  // SAME agent
    "data": { "edgeLabel": "Onboarding" }
  },
  {
    "source": "conditionAgentAgentflow_0",
    "sourceHandle": "conditionAgentAgentflow_0-output-5",
    "target": "agentAgentflow_5",  // SAME agent
    "data": { "edgeLabel": "Performance" }
  }
]
```

**Benefits:**
- ✅ Clearer routing analytics (track which scenario triggered)
- ✅ More explicit intent categories in condition instructions
- ✅ Easier to split agents later without changing condition node
- ✅ Better visibility in Flowise UI (multiple labeled edges)

**Use Case Example:**

An HCM General Agent can handle multiple categories that don't warrant dedicated specialists:
- Time & Attendance (not complex enough for dedicated agent)
- Employee Data updates (simple updates, not full data management)
- Onboarding questions (general guidance, not full onboarding workflow)

Rather than creating 4 separate agents or one vague "Other" scenario, use explicit scenarios that route to the same generalist agent.

### 6. Knowledge Integration

Agents can access two types of knowledge:

#### Document Stores (Pre-indexed)

```json
"agentKnowledgeDocumentStores": [
  {
    "documentStore": "workday_navigation_docs",
    "docStoreDescription": "Official Workday navigation documentation with step-by-step guides for finding pages and features",
    "returnSourceDocuments": true
  }
]
```

#### Vector Embeddings (Semantic search)

```json
"agentKnowledgeVSEmbeddings": [
  {
    "vectorStore": "payroll_knowledge_base",
    "embeddingModel": "text-embedding-3-small",
    "knowledgeName": "Payroll Procedures",
    "knowledgeDescription": "Comprehensive payroll policies, procedures, and troubleshooting guides",
    "returnSourceDocuments": true
  }
]
```

### 7. Tool Configuration

#### Built-in Tools

Platform-specific capabilities enabled directly:

```json
"agentBuiltInTools": ["web_search_preview", "code_interpreter"]
```

#### Custom Tools

Tools created in Flowise and connected to agents:

```json
"agentTools": [
  {
    "agentSelectedTool": "calculate_payroll",
    "agentSelectedToolRequiresHumanInput": ""
  },
  {
    "agentSelectedTool": "approve_time_off",
    "agentSelectedToolRequiresHumanInput": ""  // Configure human approval in Flowise UI
  }
]
```

**Note**: Use empty string `""` for `agentSelectedToolRequiresHumanInput` in JSON (NOT boolean `true`/`false`). Configure human-in-the-loop approval in the Flowise UI after importing the workflow.

**Custom Tools Reminder**: These are example/placeholder tool names for documentation purposes. Per Pattern #5, do NOT include custom tool references in generated JSON - document them in README/INTEGRATION_GUIDE instead. Only standard tools (currentDateTime, searXNG) should be in the JSON.

---

## Implementation Checklist

Use this checklist when creating new agents:

### Node Creation

- [ ] 1. Define unique ID following pattern `agentAgentflow_[NUMBER]`
- [ ] 2. Set descriptive label: `Agent.[DomainName]`
- [ ] 3. Calculate position coordinates (visual layout)
- [ ] 4. Set standard dimensions (width: 300, height: 500)

### Agent Configuration

- [ ] 5. Create persona in system message (HTML `<p><em>` format)
- [ ] 6. Define capabilities and boundaries clearly
- [ ] 7. Configure model type and temperature
- [ ] 8. Add relevant built-in tools (if any)
- [ ] 9. Connect custom tools (if any)
- [ ] 10. Configure knowledge stores (if any)
- [ ] 11. Set memory configuration (enable, type, window size)

### Integration

- [ ] 12. Add scenario to condition node `conditionAgentScenarios` array
- [ ] 13. Create output anchor on condition node
- [ ] 14. Create edge from condition output to agent input
- [ ] 15. Configure any agent-to-agent connections
- [ ] 16. Set state management (if needed)

### Validation

- [ ] 17. Verify all required `inputParams` present
- [ ] 18. Verify all `inputs` values populated
- [ ] 19. Verify edge connections valid
- [ ] 20. Test in Flowise (import and verify rendering)

---

## Common Pitfalls to Avoid

### ❌ WRONG: Separate Model Nodes

```json
{
  "nodes": [
    {
      "id": "chatOpenAI_1",
      "data": {"name": "chatOpenAI"}
    },
    {
      "id": "agent_1",
      "data": {
        "inputs": {
          "model": "{{chatOpenAI_1.data.instance}}"  // ❌ External reference
        }
      }
    }
  ]
}
```

### ✅ CORRECT: Self-Contained Agent

```json
{
  "nodes": [
    {
      "id": "agentAgentflow_1",
      "data": {
        "name": "agentAgentflow",
        "inputs": {
          "agentModel": "chatOpenAI",  // ✅ Built-in model selection
          "agentModelConfig": {
            "modelName": "gpt-4o-mini"
          }
        }
      }
    }
  ]
}
```

### ❌ WRONG: Separate Memory Nodes

```json
{
  "nodes": [
    {
      "id": "windowMemory_1",
      "data": {"name": "windowMemory"}
    },
    {
      "id": "agent_1",
      "data": {
        "inputs": {
          "memory": "{{windowMemory_1.data.instance}}"  // ❌ External reference
        }
      }
    }
  ]
}
```

### ✅ CORRECT: Built-in Memory

```json
{
  "nodes": [
    {
      "id": "agentAgentflow_1",
      "data": {
        "inputs": {
          "agentEnableMemory": true,        // ✅ Built-in memory
          "agentMemoryType": "windowSize",
          "agentMemoryWindowSize": 20
        }
      }
    }
  ]
}
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-31 | Initial authoritative pattern reference |

---

## References

- **Canonical Example**: Simple Agent Agents.json (self-contained agent template)
- **Context Foundry Integration**: See `SELF-CONTAINED-AGENTS-FIX.md`
- **Flowise Documentation**: [Official Flowise Docs](https://docs.flowiseai.com/)

---

## Support

For questions or issues with this pattern:

1. Verify against canonical examples in `/templates/`
2. Check `SELF-CONTAINED-AGENTS-FIX.md` for common issues
3. Review generated flows against this reference
4. Test import in Flowise to validate structure

---

**Remember**: Agents are self-contained. No separate model or memory nodes. Everything configures within the agent node itself.

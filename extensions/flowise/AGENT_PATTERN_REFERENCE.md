# Flowise Multi-Agent JSON Structure - Authoritative Pattern Reference

**Status**: Canonical Reference
**Version**: 1.0
**Last Updated**: 2025-10-31

This document defines the authoritative pattern for creating Flowise multi-agent systems with JSON configuration. All Context Foundry generated Flowise flows MUST follow these patterns.

---

## Table of Contents

1. [Core Architecture](#core-architecture)
2. [Node Types](#node-types)
3. [Agent Input Parameters](#agent-input-parameters)
4. [Actual Configured Values](#actual-configured-values)
5. [Edges Structure](#edges-structure)
6. [Critical Design Patterns](#critical-design-patterns)
7. [Implementation Checklist](#implementation-checklist)

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
      "conditionAgentInput": "{{ question }}",
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

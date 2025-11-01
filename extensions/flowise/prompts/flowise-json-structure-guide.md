# Flowise Agent Flow JSON Structure Guide

**CRITICAL**: When building Flowise agent flows, you MUST use the exact node structure that Flowise exports.

## ⚠️ MOST IMPORTANT: Self-Contained Agents

**Flowise agents are SELF-CONTAINED** - they include model and memory configuration WITHIN the agent node itself.

### ❌ WRONG - Separate Nodes (What Context Foundry was doing)

```json
{
  "nodes": [
    {
      "id": "chatOpenAI_1",
      "type": "agentFlow",
      "data": {
        "name": "chatOpenAI",  // ❌ Separate model node
        "type": "ChatOpenAI"
      }
    },
    {
      "id": "windowMemory_1",
      "type": "agentFlow",
      "data": {
        "name": "windowMemory",  // ❌ Separate memory node
        "type": "WindowMemory"
      }
    },
    {
      "id": "agent_1",
      "type": "agentFlow",
      "data": {
        "name": "agent",  // ❌ Agent without built-in config
        "inputs": {
          "model": "{{chatOpenAI_1.data.instance}}",  // ❌ WRONG!
          "memory": "{{windowMemory_1.data.instance}}"  // ❌ WRONG!
        }
      }
    }
  ]
}
```

### ✅ CORRECT - Self-Contained Agent

```json
{
  "nodes": [
    {
      "id": "agentAgentflow_0",
      "type": "agentFlow",
      "data": {
        "name": "agentAgentflow",  // ✅ CORRECT!
        "type": "Agent",
        "inputParams": [
          {
            "label": "Model",
            "name": "agentModel",
            "type": "asyncOptions",  // ✅ Built-in model selection
            "loadMethod": "listModels",
            "loadConfig": true
          },
          {
            "label": "Enable Memory",
            "name": "agentEnableMemory",  // ✅ Built-in memory
            "type": "boolean",
            "default": true
          },
          {
            "label": "Memory Type",
            "name": "agentMemoryType",  // ✅ Built-in memory config
            "type": "options",
            "options": [
              {"label": "All Messages", "name": "allMessages"},
              {"label": "Window Size", "name": "windowSize"},
              {"label": "Conversation Summary", "name": "conversationSummary"}
            ]
          }
        ],
        "inputs": {
          "agentModel": "chatOpenAI",  // ✅ Model selected within agent
          "agentEnableMemory": true,
          "agentMemoryType": "windowSize",
          "agentModelConfig": {  // ✅ Model config within agent
            "modelName": "gpt-4o-mini",
            "temperature": 0.9,
            "streaming": true
          }
        }
      }
    }
  ]
}
```

## ❌ WRONG - Generic Node Structure

```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "customNode",  // ❌ WRONG!
      "data": {
        "name": "chatInput",  // ❌ Generic
        "type": "ChatOpenAI"  // ❌ Wrong type
      }
    }
  ]
}
```

## ✅ CORRECT - Flowise Agent Flow Structure

```json
{
  "nodes": [
    {
      "id": "startAgentflow_0",
      "type": "agentFlow",  // ✅ CORRECT! Use "agentFlow" type
      "position": {
        "x": -162.58,
        "y": 117.81
      },
      "data": {
        "id": "startAgentflow_0",
        "label": "Start",
        "version": 1.1,
        "name": "startAgentflow",  // ✅ Specific Flowise node name
        "type": "Start",  // ✅ Node type: Start, Agent, Condition, Loop, etc.
        "color": "#7EE787",  // ✅ Visual color
        "hideInput": true,
        "baseClasses": ["Start"],
        "category": "Agent Flows",  // ✅ MUST be "Agent Flows"
        "description": "Starting point of the agentflow",
        "inputParams": [
          {
            "label": "Input Type",
            "name": "startInputType",
            "type": "options",
            "options": [...],
            "default": "chatInput",
            "id": "startAgentflow_0-input-startInputType-options",  // ✅ Full ID
            "display": true
          }
        ],
        "inputs": {
          "startInputType": "chatInput"
        }
      }
    }
  ],
  "edges": [
    {
      "source": "startAgentflow_0",
      "sourceHandle": "startAgentflow_0-output-startAgentflow-Start",  // ✅ Full handle ID
      "target": "agent_1",
      "targetHandle": "agent_1-input-agent-Agent",  // ✅ Full handle ID
      "type": "buttonedge",  // ✅ Must be "buttonedge"
      "id": "startAgentflow_0-startAgentflow_0-output-startAgentflow-Start-agent_1-agent_1-input-agent-Agent"
    }
  ]
}
```

## Key Differences

### Node Types
- ✅ **ALWAYS use**: `"type": "agentFlow"` (NOT "customNode")
- ✅ **Category**: `"category": "Agent Flows"` (NOT "Chat Models" or "Chains")

### Node Names (data.name)
Flowise Agent Flow specific nodes:
- ✅ `startAgentflow` - Start node
- ✅ `agent` - Agent node (worker agents)
- ✅ `supervisorAgent` - Supervisor agent
- ✅ `condition` - Condition/routing node
- ✅ `loop` - Loop node
- ✅ `iteration` - Iteration node (parallel processing)
- ✅ `endAgentflow` - End node
- ✅ `stickyNote` - Sticky note (documentation)

### Visual Properties
Always include:
- ✅ `color`: Hex color code (e.g., "#7EE787" for green, "#FFA500" for orange)
- ✅ `hideInput`: Boolean for visual display
- ✅ `version`: Node version (e.g., 1.1, 2.2)

### Input Parameters
Must have full structure:
```json
{
  "label": "Human-readable label",
  "name": "camelCaseName",
  "type": "options" | "string" | "number" | "boolean" | "array",
  "id": "nodeId-input-paramName-type",  // ✅ MUST include full ID
  "display": true | false,
  "optional": true | false,
  "description": "Help text"
}
```

### Edge Structure
Must include:
- ✅ `sourceHandle`: Full handle ID like "nodeId-output-nodeName-NodeType"
- ✅ `targetHandle`: Full handle ID like "nodeId-input-nodeName-NodeType"
- ✅ `type`: "buttonedge" (Flowise uses this for agent flows)
- ✅ `id`: Concatenated full edge ID

## Complete Example: Supervisor Agent Node

```json
{
  "id": "supervisorAgent_0",
  "type": "agentFlow",
  "position": { "x": 500, "y": 300 },
  "data": {
    "id": "supervisorAgent_0",
    "label": "Chief Operations Supervisor",
    "version": 2.2,
    "name": "supervisorAgent",
    "type": "Supervisor",
    "color": "#FFA500",
    "hideInput": false,
    "baseClasses": ["Supervisor", "Agent"],
    "category": "Agent Flows",
    "description": "Supervisor agent that routes to workers",
    "inputParams": [
      {
        "label": "Supervisor Name",
        "name": "supervisorName",
        "type": "string",
        "placeholder": "Chief Operations Agent",
        "id": "supervisorAgent_0-input-supervisorName-string",
        "display": true
      },
      {
        "label": "Supervisor Prompt",
        "name": "supervisorPrompt",
        "type": "string",
        "rows": 10,
        "placeholder": "You are the supervisor...",
        "id": "supervisorAgent_0-input-supervisorPrompt-string",
        "display": true
      },
      {
        "label": "Agent Model",
        "name": "model",
        "type": "ChatOpenAI",
        "optional": false,
        "id": "supervisorAgent_0-input-model-ChatOpenAI"
      },
      {
        "label": "Memory",
        "name": "memory",
        "type": "BaseChatMemory",
        "optional": true,
        "id": "supervisorAgent_0-input-memory-BaseChatMemory"
      },
      {
        "label": "Worker Nodes",
        "name": "workerNodes",
        "type": "array",
        "array": [
          {
            "label": "Worker Name",
            "name": "workerName",
            "type": "string"
          }
        ],
        "id": "supervisorAgent_0-input-workerNodes-array",
        "display": true
      },
      {
        "label": "Recursion Limit",
        "name": "recursionLimit",
        "type": "number",
        "default": 15,
        "step": 1,
        "id": "supervisorAgent_0-input-recursionLimit-number",
        "display": true
      }
    ],
    "inputAnchors": [
      {
        "label": "Agent Model",
        "name": "model",
        "type": "ChatOpenAI",
        "id": "supervisorAgent_0-input-model-ChatOpenAI"
      },
      {
        "label": "Memory",
        "name": "memory",
        "type": "BaseChatMemory",
        "optional": true,
        "id": "supervisorAgent_0-input-memory-BaseChatMemory"
      },
      {
        "label": "Input Moderation",
        "name": "inputModeration",
        "type": "Moderation",
        "optional": true,
        "list": true,
        "id": "supervisorAgent_0-input-inputModeration-Moderation"
      }
    ],
    "inputs": {
      "supervisorName": "Chief Operations Agent",
      "supervisorPrompt": "You are the Chief Operations Agent...",
      "model": "{{chatOpenAI_1.data.instance}}",
      "memory": "{{conversationSummaryMemory_0.data.instance}}",
      "workerNodes": [
        { "workerName": "Customer Service" },
        { "workerName": "Logistics Planning" },
        { "workerName": "Documentation" },
        { "workerName": "Exception Handler" },
        { "workerName": "Pricing" }
      ],
      "recursionLimit": 15
    },
    "outputAnchors": [
      {
        "id": "supervisorAgent_0-output-supervisorAgent-Supervisor",
        "name": "supervisorAgent",
        "label": "Supervisor Agent",
        "description": "Supervisor Agent",
        "type": "Supervisor"
      }
    ],
    "outputs": {},
    "selected": false
  },
  "width": 300,
  "height": 600,
  "selected": false,
  "positionAbsolute": { "x": 500, "y": 300 },
  "dragging": false
}
```

## Complete Example: Worker Agent Node

```json
{
  "id": "agent_1",
  "type": "agentFlow",
  "position": { "x": 1000, "y": 300 },
  "data": {
    "id": "agent_1",
    "label": "Customer Service Agent",
    "version": 2.2,
    "name": "agent",
    "type": "Agent",
    "color": "#4A90E2",
    "hideInput": false,
    "baseClasses": ["Agent"],
    "category": "Agent Flows",
    "description": "Worker agent for customer service tasks",
    "inputParams": [
      {
        "label": "Agent Name",
        "name": "agentName",
        "type": "string",
        "placeholder": "Customer Service Agent",
        "id": "agent_1-input-agentName-string",
        "display": true
      },
      {
        "label": "Agent Description",
        "name": "agentDesc",
        "type": "string",
        "rows": 3,
        "placeholder": "Handles customer inquiries...",
        "id": "agent_1-input-agentDesc-string",
        "display": true
      },
      {
        "label": "System Message",
        "name": "systemMessage",
        "type": "string",
        "rows": 10,
        "placeholder": "You are a customer service agent...",
        "id": "agent_1-input-systemMessage-string",
        "display": true
      },
      {
        "label": "Agent Model",
        "name": "model",
        "type": "ChatOpenAI",
        "id": "agent_1-input-model-ChatOpenAI"
      },
      {
        "label": "Tools",
        "name": "tools",
        "type": "Tool",
        "list": true,
        "optional": true,
        "id": "agent_1-input-tools-Tool"
      },
      {
        "label": "Memory",
        "name": "memory",
        "type": "BaseChatMemory",
        "optional": true,
        "id": "agent_1-input-memory-BaseChatMemory"
      },
      {
        "label": "Max Iterations",
        "name": "maxIterations",
        "type": "number",
        "default": 5,
        "optional": true,
        "id": "agent_1-input-maxIterations-number"
      }
    ],
    "inputAnchors": [
      {
        "label": "Tools",
        "name": "tools",
        "type": "Tool",
        "list": true,
        "optional": true,
        "id": "agent_1-input-tools-Tool"
      },
      {
        "label": "Agent Model",
        "name": "model",
        "type": "ChatOpenAI",
        "id": "agent_1-input-model-ChatOpenAI"
      },
      {
        "label": "Memory",
        "name": "memory",
        "type": "BaseChatMemory",
        "optional": true,
        "id": "agent_1-input-memory-BaseChatMemory"
      }
    ],
    "inputs": {
      "agentName": "Customer Service Agent",
      "agentDesc": "Handles customer inquiries, tracking updates, and support requests",
      "systemMessage": "You are a customer service agent for a global shipping company...",
      "model": "{{chatOpenAI_2.data.instance}}",
      "tools": ["{{trackingTool_0.data.instance}}", "{{notificationTool_0.data.instance}}"],
      "memory": "{{windowMemory_1.data.instance}}",
      "maxIterations": 5
    },
    "outputAnchors": [
      {
        "id": "agent_1-output-agent-Agent",
        "name": "agent",
        "label": "Agent",
        "description": "Agent",
        "type": "Agent"
      }
    ],
    "outputs": {},
    "selected": false
  },
  "width": 300,
  "height": 550,
  "selected": false,
  "positionAbsolute": { "x": 1000, "y": 300 },
  "dragging": false
}
```

## Colors to Use

Suggested colors for visual hierarchy:
- **Start Node**: `#7EE787` (Green)
- **Supervisor Agent**: `#FFA500` (Orange)
- **Worker Agents**: `#4A90E2` (Blue)
- **Condition/Router**: `#9B59B6` (Purple)
- **Loop**: `#E74C3C` (Red)
- **End Node**: `#95A5A6` (Gray)
- **Sticky Notes**: `#FFE066` (Yellow)

## ⚠️ CRITICAL: Complete Agent Node Structure

**USE THIS TEMPLATE** for every agent you create:

**Template File**: `/Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json`

**Real Example**: `/Users/name/Downloads/Simple Agent Agents.json`

### Complete `agentAgentflow` Node Requirements:

1. **Node Type & Name**
   ```json
   {
     "type": "agentFlow",
     "data": {
       "name": "agentAgentflow",  // MUST be this exact name
       "type": "Agent",
       "version": 2.2
     }
   }
   ```

2. **Model Selection (Built-in)**
   ```json
   {
     "label": "Model",
     "name": "agentModel",
     "type": "asyncOptions",  // NOT a separate node!
     "loadMethod": "listModels",
     "loadConfig": true
   }
   ```

3. **Memory Configuration (Built-in)**
   ```json
   {
     "label": "Enable Memory",
     "name": "agentEnableMemory",
     "type": "boolean",
     "default": true
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
     ]
   }
   ```

4. **Tools Configuration**
   ```json
   {
     "label": "OpenAI Built-in Tools",
     "name": "agentToolsBuiltInOpenAI",
     "type": "multiOptions",
     "options": [
       {"label": "Web Search", "name": "web_search_preview"},
       {"label": "Code Interpreter", "name": "code_interpreter"},
       {"label": "Image Generation", "name": "image_generation"}
     ]
   },
   {
     "label": "Tools",
     "name": "agentTools",
     "type": "array",
     "array": [
       {
         "label": "Tool",
         "name": "agentSelectedTool",
         "type": "asyncOptions",
         "loadMethod": "listTools"
       }
     ]
   }
   ```

5. **Knowledge Sources**
   ```json
   {
     "label": "Knowledge (Document Stores)",
     "name": "agentKnowledgeDocumentStores",
     "type": "array",
     "array": [
       {
         "label": "Document Store",
         "name": "documentStore",
         "type": "asyncOptions",
         "loadMethod": "listStores"
       },
       {
         "label": "Describe Knowledge",
         "name": "docStoreDescription",
         "type": "string",
         "rows": 4
       }
     ]
   }
   ```

6. **Flow State Management**
   ```json
   {
     "label": "Update Flow State",
     "name": "agentUpdateState",
     "type": "array",
     "array": [
       {
         "label": "Key",
         "name": "key",
         "type": "asyncOptions",
         "loadMethod": "listRuntimeStateKeys",
         "freeSolo": true
       },
       {
         "label": "Value",
         "name": "value",
         "type": "string",
         "acceptVariable": true
       }
     ]
   }
   ```

7. **Model Config in Inputs**
   ```json
   "inputs": {
     "agentModel": "chatOpenAI",
     "agentModelConfig": {
       "modelName": "gpt-4o-mini",
       "temperature": 0.9,
       "streaming": true,
       "maxTokens": "",
       "topP": "",
       "frequencyPenalty": "",
       "presencePenalty": "",
       "agentModel": "chatOpenAI"
     }
   }
   ```

### ⚠️ DO NOT CREATE:
- ❌ Separate `chatOpenAI` nodes
- ❌ Separate `windowMemory` nodes
- ❌ Separate `conversationSummaryMemory` nodes
- ❌ Agent nodes that reference external model/memory via `{{instance}}`

### ✅ DO CREATE:
- ✅ Self-contained `agentAgentflow` nodes
- ✅ Built-in model selection via `agentModel` parameter
- ✅ Built-in memory config via `agentEnableMemory`/`agentMemoryType`
- ✅ Model config in `agentModelConfig` object within `inputs`

## Reference Templates

See your 13 analyzed Flowise templates in:
`/Users/name/homelab/context-foundry/extensions/flowise/templates/`

**Canonical Example**: `/Users/name/Downloads/Simple Agent Agents.json`

These show the exact structure Flowise expects!

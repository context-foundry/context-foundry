# Flowise Tool Nodes vs Custom Tools: When to Use Each

When building AI workflows in Flowise, you have multiple ways to execute functions and extend your agent's capabilities. Understanding the differences between **Tool Nodes**, **Custom Function Nodes**, and **Agent Custom Tools** is crucial for building efficient, cost-effective workflows.

This comprehensive guide breaks down each approach, when to use them, and how to avoid common pitfalls.

## Table of Contents
1. [Overview: Three Approaches to Tool Execution](#overview)
2. [Tool Node: Deterministic Execution](#tool-node)
3. [Custom Function Node: JavaScript Execution](#custom-function)
4. [Agent Custom Tools: LLM-Driven Tool Selection](#agent-custom-tools)
5. [Key Differences Comparison](#comparison)
6. [When to Use Each Approach](#decision-framework)
7. [Real-World Examples](#examples)
8. [Best Practices & Common Pitfalls](#best-practices)
9. [Quick Decision Guide](#quick-guide)

---

<a name="overview"></a>
## Overview: Three Approaches to Tool Execution

Flowise provides three distinct ways to execute tools and functions in your workflows:

| Approach | Execution Type | LLM Involved? | Cost |
|----------|---------------|---------------|------|
| **Tool Node** | Deterministic | No | $0 |
| **Custom Function Node** | Deterministic | No | $0 |
| **Agent Custom Tools** | Dynamic | Yes | LLM API costs |

Each approach serves different use cases, and choosing the right one can dramatically impact both your workflow's performance and operational costs.

---

<a name="tool-node"></a>
## Tool Node: Deterministic Execution

### What is a Tool Node?

The **Tool Node** provides a mechanism for directly and deterministically executing a specific, pre-defined Flowise Tool within your workflow sequence. Unlike the Agent node, where the LLM dynamically chooses a tool based on reasoning, the Tool node executes **exactly the tool** you select during configuration—no AI reasoning, no uncertainty.

### How It Works

1. **Triggering**: When workflow execution reaches a Tool node, it activates immediately
2. **Tool Identification**: It identifies the specific Flowise Tool selected in configuration
3. **Input Argument Resolution**: It resolves input parameters from:
   - Previous node outputs (`{{ previousNode.output }}`)
   - Flow state variables (`{{ $flow.state.someKey }}`)
   - Static text values
4. **Execution**: Invokes the tool's underlying code or API call with resolved arguments
5. **Output Generation**: Receives the tool's execution result
6. **Output Propagation**: Makes the result available via its output anchor for subsequent nodes

### Configuration Parameters

```json
{
  "id": "toolAgentflow_0",
  "data": {
    "name": "toolAgentflow",
    "type": "Tool",
    "inputs": {
      "toolSelection": "calculator",
      "toolArguments": [
        {
          "parameterName": "operation",
          "value": "{{ $flow.state.math_expression }}"
        }
      ],
      "toolStateUpdates": [
        {
          "key": "tool.calculator_result",
          "value": "{{ toolOutput }}"
        }
      ]
    }
  }
}
```

**Key Configuration Options:**

- **Tool Selection**: Choose from available Flowise tools via dropdown
- **Input Arguments**: Map workflow data to tool parameters
  - **Map Argument Name**: The tool's expected parameter name (e.g., `input` for Calculator)
  - **Provide Argument Value**: Use dynamic variables or static text
- **Update Flow State**: Store tool output in `$flow.state` for later nodes

### Built-in Tools Available

Flowise comes with several powerful built-in tools:

#### 1. **Calculator**
- **Purpose**: Arithmetic operations
- **Cost Savings**: $0.0002 vs $0.0032 for LLM calculation (16x cheaper!)
- **Use Cases**: Simple math, deterministic calculations

#### 2. **currentDateTime**
- **Purpose**: Temporal awareness and time-based logic
- **Response Format**:
```json
{
  "currentDateTime": "2025-11-01T22:45:00.000Z",
  "timestamp": 1730500000000,
  "date": "Fri Nov 01 2025",
  "time": "22:45:00 GMT+0000 (UTC)"
}
```
- **Use Cases**:
  - Search result freshness evaluation
  - Deadline awareness
  - Time-sensitive decisions
  - Context validation

#### 3. **searXNG (Federated Search)**
- **Purpose**: Privacy-respecting, federated web search
- **Configuration**:
```json
{
  "agentSelectedTool": "searXNG",
  "agentSelectedToolConfig": {
    "apiBase": "https://s.llam.ai",
    "toolName": "searxng-search",
    "toolDescription": "Federated web/meta search...",
    "format": "json",
    "categories": "",
    "engines": "",
    "language": "",
    "pageno": "",
    "time_range": "",
    "safesearch": ""
  }
}
```
- **Use Cases**:
  - Real-time web searches
  - Current facts lookup
  - Trend research
  - Information verification

#### 4. **Anthropic Web Search**
- **Purpose**: Built-in Anthropic web search capability
- **Use Cases**: Multi-source parallel research, real-time information gathering

### When to Use Tool Node

✅ **Use Tool Node when:**
- You know **exactly which tool** to execute at a specific workflow point
- The tool selection doesn't require LLM reasoning
- You want **zero LLM costs** for tool execution
- You need **deterministic, predictable** behavior
- Input parameters are readily available from previous nodes or flow state

❌ **Don't use Tool Node when:**
- The LLM needs to **choose between multiple tools** dynamically
- Tool selection depends on complex reasoning about the user's intent
- You need the agent to decide whether a tool is needed at all

---

<a name="custom-function"></a>
## Custom Function Node: JavaScript Execution

### What is a Custom Function Node?

The **Custom Function Node** allows you to execute **server-side JavaScript** for complex transformations and custom business logic. Unlike Tool Nodes (which execute pre-defined tools), Custom Function Nodes let you write arbitrary JavaScript code tailored to your specific needs.

### How It Works

```json
{
  "id": "customFunctionAgentflow_0",
  "data": {
    "name": "customFunctionAgentflow",
    "type": "CustomFunction",
    "inputs": {
      "customFunctionVariables": [
        {"variableName": "input", "value": "{{ $flow.state.user_input }}"},
        {"variableName": "multiplier", "value": "2"}
      ],
      "customFunctionCode": "// JavaScript code here"
    }
  }
}
```

### Configuration Parameters

- **Variables**: Map dynamic values from Flow State
  - Each variable becomes accessible in your code via the `$vars` object
- **JavaScript Function**: Write your custom logic
  - Access variables: `$vars.variableName`
  - Must return a string (use `JSON.stringify()` for objects)
  - Executes server-side with full Node.js capabilities

### Example: Data Transformation

```javascript
// Access variables via $vars object
const input = $vars.input;
const multiplier = $vars.multiplier || 2;

// Perform calculation
const result = parseInt(input) * multiplier;

// Return formatted result
return JSON.stringify({
  result: result,
  formatted: `${input} × ${multiplier} = ${result}`,
  timestamp: new Date().toISOString()
});
```

### Common Use Cases

1. **Data Parsing & Transformation**
   - Convert between formats (CSV to JSON, XML to JSON)
   - Clean and normalize data
   - Extract specific fields from complex objects

2. **Schema Validation**
   - Validate data against custom business rules
   - Check required fields
   - Enforce data constraints

3. **Custom Business Logic**
   - Calculate discounts or pricing
   - Apply business-specific rules
   - Generate custom identifiers

4. **ETL Operations** (Extract, Transform, Load)
   - Data pipeline processing
   - Batch transformations
   - Data aggregation

### When to Use Custom Function Node

✅ **Use Custom Function Node when:**
- You need **custom logic** not available in pre-built tools
- You're performing **data transformations** or manipulations
- You want **zero LLM costs** for processing
- You need **full JavaScript/Node.js capabilities**
- The operation is **deterministic** (same input = same output)

❌ **Don't use Custom Function Node when:**
- A pre-built Tool Node already does what you need (use that instead)
- You need LLM reasoning or natural language understanding
- The operation could be handled by a simpler node type

---

<a name="agent-custom-tools"></a>
## Agent Custom Tools: LLM-Driven Tool Selection

### What are Agent Custom Tools?

**Agent Custom Tools** are tools registered within an Agent node that the LLM can **dynamically choose** based on its reasoning about the user's request. Unlike Tool Nodes (which execute deterministically), the LLM decides:
- **Whether** to use a tool at all
- **Which** tool to use (if multiple are available)
- **When** to use it during the conversation

### Two Ways to Create Custom Tools

#### Method 1: JSON Schema

Define your tool's structure using JSON Schema:

```json
{
  "name": "weather_lookup",
  "description": "Get current weather for a location",
  "parameters": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City name or coordinates"
      },
      "units": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"],
        "description": "Temperature units"
      }
    },
    "required": ["location"]
  }
}
```

#### Method 2: JavaScript Function

Paste a JavaScript function directly:

```javascript
async function customTool(input) {
  // Your custom logic here
  const response = await fetch(`https://api.example.com/data?q=${input}`);
  return await response.json();
}
```

### Agent Tool Configuration

Tools are configured in the Agent node's "Tools" section:

```json
{
  "inputParams": [
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
        },
        {
          "label": "Require Human Input",
          "name": "agentSelectedToolRequiresHumanInput",
          "type": "boolean"
        }
      ]
    }
  ]
}
```

### Standard Practice: Auto-Included Tools

By Flowise convention, agents typically auto-include two standard tools:

1. **currentDateTime**: Temporal awareness
2. **searXNG**: Web search capability

This ensures agents can handle time-sensitive queries and look up current information without manual configuration.

### When to Use Agent Custom Tools

✅ **Use Agent Custom Tools when:**
- The LLM needs to **decide which tool** to use based on user intent
- You have **multiple tools** and the LLM should choose the right one
- Tool usage requires **contextual reasoning**
- You want the agent to have **flexible tool selection**
- The workflow is **conversational** and tool needs vary by request

❌ **Don't use Agent Custom Tools when:**
- You know exactly which tool to execute (use Tool Node instead)
- Tool execution should be deterministic and predictable
- You want to minimize LLM costs (Tool/Function nodes are free)

---

<a name="comparison"></a>
## Key Differences Comparison

### Cost Comparison

| Approach | LLM Tokens Used | Typical Cost | Example Operation |
|----------|----------------|--------------|-------------------|
| **Tool Node** | 0 | $0 | Calculator: $0.0002 |
| **Custom Function** | 0 | $0 | Data transformation: $0 |
| **LLM Node** | ~5K tokens | $0.0032 | Stateless text processing |
| **Agent + Tools** | ~10-20K tokens | $0.006-$0.012 | Reasoning + tool selection |

**Key Insight**: Tool and Custom Function nodes are **16x cheaper** than using LLMs for simple operations!

### Execution Type Comparison

| Feature | Tool Node | Custom Function | Agent Custom Tools |
|---------|-----------|-----------------|-------------------|
| **Execution** | Deterministic | Deterministic | Dynamic (LLM-driven) |
| **Tool Selection** | Pre-configured | N/A (single function) | LLM chooses |
| **When to Execute** | Fixed in workflow | Fixed in workflow | LLM decides |
| **Reasoning Required** | No | No | Yes |
| **Available Tools** | Pre-built + registered | Custom JavaScript | Pre-built + custom |
| **Configuration** | Dropdown selection | Write JS code | JSON Schema or JS |

### Architecture Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                         TOOL NODE                            │
│                                                              │
│  Input → [Select Tool] → Execute → Output                   │
│           └─ calculator, searXNG, etc.                      │
│                                                              │
│  Cost: $0 | Deterministic: Yes | LLM Reasoning: No          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    CUSTOM FUNCTION NODE                      │
│                                                              │
│  Input → [JavaScript Code] → Execute → Output               │
│           └─ Your custom logic                              │
│                                                              │
│  Cost: $0 | Deterministic: Yes | LLM Reasoning: No          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   AGENT CUSTOM TOOLS                         │
│                                                              │
│  User Request → [LLM] → Should I use a tool?                │
│                   └─ Yes → Which one?                       │
│                          └─ Tool A, B, or C?               │
│                               └─ Execute → Output          │
│                                                              │
│  Cost: $$$ | Deterministic: No | LLM Reasoning: Yes         │
└─────────────────────────────────────────────────────────────┘
```

---

<a name="decision-framework"></a>
## When to Use Each Approach

### Decision Tree

```
Do you know EXACTLY which tool/function to execute?
│
├─ YES: Does a pre-built tool exist for this?
│   │
│   ├─ YES: Use TOOL NODE
│   │       (calculator, currentDateTime, searXNG, etc.)
│   │
│   └─ NO: Do you need custom JavaScript logic?
│       │
│       ├─ YES: Use CUSTOM FUNCTION NODE
│       │       (data transformation, ETL, custom business rules)
│       │
│       └─ NO: Use TOOL NODE with custom tool registration
│
└─ NO: Does the LLM need to decide which tool to use?
    │
    ├─ YES: Use AGENT CUSTOM TOOLS
    │       (dynamic tool selection, conversational AI)
    │
    └─ NO: Consider if you need a tool at all
            (maybe use Condition Node or LLM Node instead)
```

### Scenario-Based Guide

#### Scenario 1: "I need to perform arithmetic calculations"

**Best Choice**: **Tool Node** with Calculator

**Why**:
- Pre-built tool available
- Deterministic operation
- 16x cheaper than LLM calculation ($0.0002 vs $0.0032)
- No reasoning required

**Example**: Flowise Pattern #11 (Smart Calculator) uses conditional routing:
- SIMPLE operations → Calculator Tool (free)
- COMPLEX operations → Math Solver LLM (paid)

---

#### Scenario 2: "I need to transform CSV data to JSON"

**Best Choice**: **Custom Function Node**

**Why**:
- Custom logic required
- No pre-built tool for CSV parsing
- Deterministic transformation
- Zero LLM costs

**Example Code**:
```javascript
const csvData = $vars.csvInput;
const lines = csvData.split('\n');
const headers = lines[0].split(',');
const result = lines.slice(1).map(line => {
  const values = line.split(',');
  return headers.reduce((obj, header, i) => {
    obj[header.trim()] = values[i]?.trim();
    return obj;
  }, {});
});
return JSON.stringify(result);
```

---

#### Scenario 3: "My agent needs to search the web when asked about current events"

**Best Choice**: **Agent Custom Tools** (searXNG)

**Why**:
- LLM needs to decide **if** search is needed (not all queries require it)
- LLM needs to formulate the search query based on user's question
- Dynamic tool selection based on context
- Standard practice in Flowise (auto-included in agents)

**Example**: User asks "What's the weather in Paris?" → Agent decides to use searXNG tool → Formats query → Returns results

---

#### Scenario 4: "I want to check if a date is before a deadline"

**Best Choice**: **Tool Node** with currentDateTime + **Condition Node**

**Why**:
- Use Tool Node to get current date (deterministic, free)
- Use Condition Node to compare dates (no LLM needed)
- Total cost: $0

**Workflow**:
```
[Tool Node: currentDateTime]
    → Store in $flow.state.now
    → [Condition Node: $flow.state.now < $flow.state.deadline]
        → TRUE: Continue workflow
        → FALSE: Send "deadline passed" message
```

---

#### Scenario 5: "I have 5 different tools and the agent should pick the right one"

**Best Choice**: **Agent Custom Tools**

**Why**:
- Multiple tools available
- LLM reasoning required to select appropriate tool
- Context-dependent selection
- Only way to enable dynamic multi-tool selection

**Example**: Customer support agent with tools:
- `check_order_status` (requires order ID)
- `process_refund` (requires order ID + reason)
- `update_address` (requires order ID + new address)
- `track_shipment` (requires tracking number)
- `faq_search` (requires question)

The LLM analyzes the user's message and picks the appropriate tool.

---

<a name="examples"></a>
## Real-World Examples from Flowise Patterns

### Example 1: Smart Calculator (Cost Optimization)

**Source**: Flowise AFv2 Pattern #11

**Problem**: Math calculations cost money when using LLMs, even for simple operations.

**Solution**: Conditional routing based on complexity:

```json
{
  "workflow": [
    {
      "node": "condition",
      "check": "{{ $flow.state.expression_complexity }}",
      "routes": {
        "SIMPLE": "calculator_tool_node",
        "COMPLEX": "math_solver_llm"
      }
    }
  ]
}
```

**Results**:
- SIMPLE operations: Calculator Tool Node = $0.0002
- COMPLEX operations: LLM = $0.0032
- **16x cost savings** for simple math!

---

### Example 2: Data Pipeline (ETL Workflow)

**Source**: Flowise AFv2 Pattern #13

**Problem**: Need to process, validate, and transform data from multiple sources.

**Solution**: Chain of Custom Function Nodes:

```
[Fetch Data]
  → [Custom Function: Parse JSON]
  → [Custom Function: Validate Schema]
  → [Custom Function: Transform Format]
  → [Custom Function: Aggregate Results]
  → [Store in Database]
```

**Benefits**:
- Zero LLM costs for entire pipeline
- Deterministic, repeatable processing
- Full JavaScript capabilities for complex transformations

---

### Example 3: Research Agent (Parallel Tool Execution)

**Source**: Flowise AFv2 Pattern #2

**Problem**: Need to gather information from multiple sources simultaneously.

**Solution**: Agent with multiple tools + parallel execution:

```json
{
  "agentTools": [
    {"agentSelectedTool": "web_search_20250305"},
    {"agentSelectedTool": "searXNG"},
    {"agentSelectedTool": "currentDateTime"}
  ],
  "parallelExecution": true
}
```

**Workflow**:
1. User asks: "What are the latest AI breakthroughs in 2025?"
2. Agent uses `currentDateTime` to know it's 2025
3. Agent uses `web_search_20250305` + `searXNG` in parallel
4. Agent synthesizes results from multiple sources

**Benefits**:
- LLM orchestrates which tools to use
- Parallel execution reduces latency
- Combines real-time data with reasoning

---

<a name="best-practices"></a>
## Best Practices & Common Pitfalls

### Critical: Use Exact Field Names

**The #1 mistake** when configuring tools is using incorrect field names.

❌ **WRONG** (Pattern #6 original bug):
```json
{
  "agentSelectedTool": "searxng-search",  // Wrong casing
  "agentSelectedToolRequiresHumanInput": false,  // Wrong type
  "agentSelectedToolConfig": {
    "baseUrl": "https://s.llam.ai"  // Wrong field name
  }
}
```

✅ **CORRECT**:
```json
{
  "agentSelectedTool": "searXNG",  // Correct: capital X, capital NG
  "agentSelectedToolRequiresHumanInput": "",  // Correct: empty string, not boolean
  "agentSelectedToolConfig": {
    "apiBase": "https://s.llam.ai"  // Correct: apiBase not baseUrl
  }
}
```

**Lesson**: Always export from Flowise UI and use exact structure—don't invent field names!

---

### Cost Optimization Patterns

1. **Use Tool Nodes for deterministic operations**
   - Calculator instead of LLM for math
   - currentDateTime instead of asking LLM "what time is it?"

2. **Use Condition Nodes instead of LLM for simple logic**
   - Boolean checks, comparisons, routing
   - Save LLM calls for complex reasoning

3. **Use Custom Function Nodes for data processing**
   - Parsing, validation, transformation
   - Zero cost vs thousands of tokens for LLM processing

4. **Route by complexity**
   - Simple → Free tools
   - Complex → LLM reasoning

---

### When NOT to Use Each Approach

#### Don't Use Tool Node When:
- ❌ LLM needs to decide which tool to use
- ❌ Tool selection depends on complex reasoning
- ❌ You need custom logic not available in pre-built tools

#### Don't Use Custom Function Node When:
- ❌ A pre-built Tool Node already exists (use that instead)
- ❌ You need LLM reasoning or NLU
- ❌ The operation requires AI capabilities

#### Don't Use Agent Custom Tools When:
- ❌ Tool execution should be deterministic
- ❌ You want to minimize costs
- ❌ You know exactly which tool to execute upfront

---

### Performance Considerations

**Tool Node & Custom Function**:
- ⚡ Near-instant execution (milliseconds)
- ⚡ No API latency
- ⚡ Predictable performance

**Agent Custom Tools**:
- 🐢 LLM reasoning adds 2-5 seconds
- 🐢 API call latency
- 🐢 Variable performance based on model load

**Best Practice**: Use Tool/Function nodes in performance-critical paths!

---

<a name="quick-guide"></a>
## Quick Decision Guide

### Use **Tool Node** when:
- ✅ Pre-built tool exists (calculator, currentDateTime, searXNG)
- ✅ You know exactly which tool to execute
- ✅ Deterministic execution required
- ✅ Want to minimize costs ($0)
- ✅ Need predictable performance

### Use **Custom Function Node** when:
- ✅ Need custom JavaScript logic
- ✅ Data transformation/parsing required
- ✅ ETL operations
- ✅ Schema validation
- ✅ No pre-built tool available
- ✅ Want to minimize costs ($0)

### Use **Agent Custom Tools** when:
- ✅ LLM should choose which tool to use
- ✅ Multiple tools available, context-dependent selection
- ✅ Conversational AI with flexible tool usage
- ✅ Tool usage requires reasoning about user intent
- ✅ Dynamic, non-deterministic workflow

---

## Conclusion

Understanding when to use **Tool Nodes**, **Custom Function Nodes**, and **Agent Custom Tools** is essential for building efficient, cost-effective Flowise workflows.

**Key Takeaways**:

1. **Tool Nodes** = Deterministic, pre-built tools, $0 cost
2. **Custom Function Nodes** = Custom JavaScript logic, $0 cost
3. **Agent Custom Tools** = LLM-driven dynamic tool selection, $$ cost

**Golden Rule**: Use the **simplest, cheapest approach** that meets your requirements:
- Known tool needed? → Tool Node
- Custom logic needed? → Custom Function Node
- LLM should choose? → Agent Custom Tools

By following this guide, you can build workflows that are both powerful and cost-effective!

---

## Further Resources

- **Flowise GitHub**: https://github.com/FlowiseAI/Flowise
- **Pattern Examples**: https://github.com/FlowiseAI/Flowise/tree/main/templates
- **Tool Documentation**: See Flowise docs for full list of built-in tools
- **Community Discord**: Join the Flowise community for tips and examples

---

*Written using insights from the Flowise repository and real-world production patterns.*

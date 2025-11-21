# How to Add Example Flows

## Quick Guide

### 1. Identify the Pattern Type

Determine which category your flow belongs to:

- **routing** - Intent-based routing, smart query routing, multi-domain chatbots
- **parallel** - Concurrent execution, fan-out/fan-in, multi-aspect analysis
- **sequential** - Step-by-step workflows, processing pipelines, chaining
- **conditional** - Decision trees, branching logic, if/then patterns
- **loop** - Iteration, batch processing, recursive workflows
- **hybrid** - Mixed patterns, complex multi-stage workflows

### 2. Add Your Flow

```bash
# Copy your tested, working flow to the appropriate directory
cp your-working-flow.json extensions/flowise/examples/{pattern-type}/

# Use a descriptive name that explains the use case
# Good: customer-support-routing.json
# Bad: flow1.json
```

### 3. File Naming Convention

Use this format: `{domain}-{purpose}-{pattern}.json`

**Examples:**
- `customer-support-routing.json` - Routes customer queries by intent
- `multi-database-parallel.json` - Queries multiple databases concurrently
- `document-processing-sequential.json` - Multi-step document analysis
- `approval-workflow-conditional.json` - Conditional approval routing
- `batch-email-loop.json` - Iterates through email list

### 4. Quality Checklist

Before adding an example, ensure it:

- ✅ **Works in Flowise** - Tested and verified
- ✅ **Imports correctly** - No JSON errors or missing fields
- ✅ **Renders properly** - All nodes visible in canvas
- ✅ **Executes successfully** - End-to-end flow completes
- ✅ **Uses AgentFlow v2.2** - Correct node types, edge types
- ✅ **Has complete structures** - Full inputParams arrays (~200 lines per agent)
- ✅ **Is production-ready** - Not a prototype or experiment

### 5. Optional: Add Context

Create a companion `{flow-name}.md` file with:

```markdown
# {Flow Name}

## Use Case
Describe what this flow does and when to use it

## Key Features
- Feature 1
- Feature 2

## Nodes
- **Node A**: Description
- **Node B**: Description

## Customization Tips
- How to adapt this flow for different use cases
- Which parts are generic vs specific
```

## Example: Adding a Routing Flow

Let's say you have a great **customer intent routing flow**:

```bash
# 1. Copy your flow
cp ~/my-flows/customer-intent.json \
   extensions/flowise/examples/routing/customer-intent-routing.json

# 2. (Optional) Add documentation
cat > extensions/flowise/examples/routing/customer-intent-routing.md <<EOF
# Customer Intent Routing Flow

## Use Case
Routes customer queries to specialized agents based on intent:
- Support queries → Technical Support Agent
- Sales inquiries → Sales Agent
- Billing questions → Billing Agent
- General questions → FAQ Agent

## Key Features
- LLM-based intent classification
- Fallback to general agent
- Context preservation across routing

## Nodes
- **Start**: Captures user query
- **Intent Classifier**: Analyzes query intent using Claude
- **Support Agent**: Handles technical support
- **Sales Agent**: Handles sales inquiries
- **Billing Agent**: Handles billing/payment questions
- **FAQ Agent**: Fallback for general questions

## Customization Tips
- Modify agent personas in agentMessages
- Add/remove routing branches in classifier logic
- Adjust confidence thresholds for routing decisions
EOF
```

## How Agents Use Examples

When you run a build:

1. **Architecture phase** specifies: "Create a routing workflow for customer support"
2. **Builder phase** reads: `extensions/flowise/examples/routing/`
3. **Builder finds**: `customer-intent-routing.json`
4. **Builder uses it as template**:
   - Copies node structure, connections, inputParams
   - Adapts agent personas to match your requirements
   - Adjusts routing logic for your specific use case
5. **Result**: High-quality flow that follows proven patterns

## Benefits

**Without examples:**
- Agent guesses structure from patterns
- May miss important fields
- Trial and error to get working flow
- 50% success rate on first try

**With examples:**
- Agent copies proven structure
- All fields present and correct
- Follows validated pattern
- 95% success rate on first try

## Pattern Directory Index

| Pattern Type | Current Examples | Description |
|-------------|------------------|-------------|
| **routing/** | 6 | Intent-based routing flows |
| **parallel/** | 0 | Concurrent execution flows |
| **sequential/** | 0 | Step-by-step chaining flows |
| **conditional/** | 0 | Decision tree flows |
| **loop/** | 0 | Iteration/batch flows |
| **hybrid/** | 0 | Mixed pattern flows |

**Current routing examples:**
- `smart-routing-customer-intent.json` - Customer query routing
- `workday-fdm-query-router.json` - Workday query routing
- `vehicle-parking-agentflow-v2.json` - Vehicle parking management routing
- `vehicle-parking-flow.json` - Vehicle parking routing (v1)
- `vehicle-parking-flow-fixed.json` - Vehicle parking routing (fixed version)
- `vehicle-parking-management.json` - Vehicle parking routing (legacy)

## Contributing

Your examples help the entire community! When you create a great flow:

1. Test it thoroughly
2. Add it to the appropriate directory
3. Use clear, descriptive naming
4. (Optional) Add documentation
5. Watch future builds use your example as a template

Every example you add makes Context Foundry smarter for everyone.

# Routing Pattern Examples

## What is a Routing Pattern?

A routing pattern uses **ConditionAgent** or **LLM classification** to analyze user input and route to specialized agents based on intent, topic, or criteria.

## When to Use

- Multi-domain chatbots (support, sales, technical)
- Intent-based routing (question types, user roles)
- Smart query routing (database selection, API selection)
- Triage systems (priority routing, department routing)

## Pattern Structure

```
Start Node
  └─> LLM Classifier (analyzes intent)
       ├─> Route A (specialized agent)
       ├─> Route B (specialized agent)
       ├─> Route C (specialized agent)
       └─> Default fallback
```

## Examples in This Directory

Each JSON file is a **working, production-quality** Flowise AgentFlow v2.2 workflow that demonstrates routing patterns.

### Using These Examples

When building a routing flow:

1. **Review the example** that most closely matches your use case
2. **Copy the structure**: Node types, connections, inputParams
3. **Adapt the content**: Change agent personas, routing conditions, tools
4. **Keep the pattern**: Don't reinvent the wheel - routing patterns follow proven structures

### Quality Standards

All examples in this directory:
- ✅ Use AgentFlow v2.2 schema (correct node types, edge types)
- ✅ Include complete inputParams arrays (~200 lines per agent)
- ✅ Use proper agentMessages format (array with role/content)
- ✅ Include agentStateUpdates for state management
- ✅ Have validated connections (proper source/target anchors)
- ✅ Follow naming conventions (clear, descriptive node names)

### Contributing Examples

To add your routing flow:
1. Test it thoroughly in Flowise
2. Export as JSON
3. Add descriptive file name: `{domain}-{purpose}-routing.json`
4. Place in this directory
5. Agents will automatically discover it on next build

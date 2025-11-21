# Sequential/Chaining Pattern Examples

## What is a Sequential Pattern?

A sequential pattern **chains multiple agents** where each agent's output becomes the next agent's input, forming a processing pipeline.

## When to Use

- Multi-step workflows (research → analyze → synthesize)
- Refinement pipelines (draft → review → polish)
- Progressive enhancement (basic → detailed → expert)
- Data transformation pipelines (extract → transform → load)

## Pattern Structure

```
Start Node
  └─> Agent A (step 1)
       └─> Agent B (step 2, uses A's output)
            └─> Agent C (step 3, uses B's output)
                 └─> Final Result
```

## Examples Coming Soon

Add your sequential workflow flows here!

### Quality Standards

All examples should:
- ✅ Use AgentFlow v2.2 schema
- ✅ Show proper state passing between agents
- ✅ Demonstrate output → input chaining
- ✅ Include error handling for failed steps

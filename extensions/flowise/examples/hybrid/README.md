# Hybrid Pattern Examples

## What is a Hybrid Pattern?

A hybrid pattern **combines multiple workflow patterns** (routing + parallel, sequential + loop, etc.) to create sophisticated multi-stage workflows.

## When to Use

- Complex business processes requiring multiple patterns
- Multi-stage workflows with different execution models per stage
- Enterprise applications with diverse processing needs
- Advanced orchestration scenarios

## Pattern Structure

```
Start Node
  └─> Stage 1: Routing (classify intent)
       ├─> Branch A: Sequential processing
       │    └─> Stage 2a: Step-by-step workflow
       └─> Branch B: Parallel processing
            └─> Stage 2b: Concurrent execution
                 └─> Stage 3: Loop (batch processing)
                      └─> Final synthesis
```

## Examples Coming Soon

Add your hybrid/mixed-pattern flows here!

### Quality Standards

All examples should:
- ✅ Use AgentFlow v2.2 schema
- ✅ Clearly document which patterns are combined
- ✅ Show transitions between pattern types
- ✅ Handle state passing across pattern boundaries
- ✅ Include detailed documentation explaining the hybrid approach

### Common Hybrid Combinations

1. **Routing → Sequential**: Route to different processing pipelines
2. **Parallel → Merge → Routing**: Gather data, then route based on results
3. **Loop → Conditional**: Iterate with branching logic per iteration
4. **Sequential → Parallel → Sequential**: Initial prep, parallel work, final synthesis
5. **Routing → Conditional → Loop**: Intent-based routing to conditional workflows with iteration

### Documentation Requirements

Hybrid flows MUST include a companion `.md` file explaining:
- Which patterns are used and where
- Why this combination was chosen
- How state flows between patterns
- Customization guidance for each pattern stage

**Example:**
```
customer-journey-hybrid.json
customer-journey-hybrid.md  ← Required documentation
```

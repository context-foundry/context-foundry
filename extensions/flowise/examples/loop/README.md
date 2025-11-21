# Loop/Iteration Pattern Examples

## What is a Loop Pattern?

A loop pattern **iterates over a collection** or **repeats execution** until a condition is met, enabling batch processing and recursive workflows.

## When to Use

- Batch processing (process each item in a list)
- Iterative refinement (improve until quality threshold met)
- Data collection (gather multiple responses)
- Retry logic (repeat until success)
- Aggregation (combine results from multiple iterations)

## Pattern Structure

```
Start Node
  └─> Loop Node
       ├─> Process Item (iteration body)
       │    └─> Update State
       └─> Check Condition
            ├─> Continue (next iteration)
            └─> Exit (loop complete)
```

## Examples Coming Soon

Add your loop/iteration flows here!

### Quality Standards

All examples should:
- ✅ Use AgentFlow v2.2 schema
- ✅ Include loop initialization (starting state)
- ✅ Show iteration logic (process each item)
- ✅ Have exit condition (prevent infinite loops)
- ✅ Demonstrate state accumulation (collect results)
- ✅ Handle empty collections gracefully

### Common Loop Types

1. **For-each loop**: Iterate over collection
2. **While loop**: Repeat until condition false
3. **Retry loop**: Repeat until success or max attempts
4. **Refinement loop**: Improve until quality threshold met

### Flowise Loop Features

- Use **Loop** node for iteration control
- Access loop state via `$flow.state.loopIndex`
- Use **agentStateUpdates** to accumulate results
- Set max iterations to prevent runaway loops

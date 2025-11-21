# Conditional Pattern Examples

## What is a Conditional Pattern?

A conditional pattern uses **decision logic** to branch execution based on specific conditions, criteria, or rules, creating dynamic workflow paths.

## When to Use

- Decision trees (if/then/else logic)
- Rule-based routing (condition-based branching)
- Threshold-based actions (budget limits, approval levels)
- Status-based workflows (approved/rejected/pending)
- Multi-criteria evaluation (scoring, filtering)

## Pattern Structure

```
Start Node
  └─> Evaluate Condition
       ├─> Path A (if condition 1)
       ├─> Path B (if condition 2)
       ├─> Path C (if condition 3)
       └─> Default path (else)
```

## Examples Coming Soon

Add your conditional branching flows here!

### Quality Standards

All examples should:
- ✅ Use AgentFlow v2.2 schema
- ✅ Show clear decision logic
- ✅ Handle all branches (including default/fallback)
- ✅ Use ConditionAgent or similar decision nodes
- ✅ Include proper state management for branching

### Difference from Routing

**Conditional** patterns branch based on **data/rules** (numeric thresholds, status values, boolean flags).

**Routing** patterns branch based on **intent/classification** (LLM analyzes meaning, semantic understanding).

**Example:**
- Conditional: "If price > $1000, route to senior approval" (rule-based)
- Routing: "If user message is about billing, route to billing agent" (intent-based)

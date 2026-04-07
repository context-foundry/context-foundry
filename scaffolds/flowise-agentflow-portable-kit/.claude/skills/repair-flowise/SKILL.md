---
name: repair-flowise
description: Repair a Flowise AgentFlow v2 file until validation and Floweyes both pass. Use after build-flowise or when audit findings already exist.
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Edit
  - MultiEdit
  - Bash
argument-hint: "Path to the flow JSON file"
---

Repair the Flowise flow at:

$ARGUMENTS

## Steps

1. Read `AGENTS.md`.
2. Run `scripts/repair-flowise.sh $ARGUMENTS`.
3. Read the resulting artifacts and apply the minimum code changes needed to clear failures.
4. Re-run:
   - `scripts/validate-flowise.sh $ARGUMENTS`
   - `scripts/audit-flowise.sh $ARGUMENTS`
5. Repeat until both checks pass or you can point to a hard blocker.

## Rules

- Preserve working structure where possible.
- Do not rewrite the flow from scratch unless the current structure is unrecoverable.

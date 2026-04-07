---
name: audit-flowise
description: Review a Flowise flow in fresh context using validation and Floweyes findings. Use when a generated Flowise flow needs an independent audit.
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
argument-hint: "Path to the flow JSON file"
---

Audit the Flowise flow at:

$ARGUMENTS

## Steps

1. Read `AGENTS.md`.
2. Read the JSON flow file.
3. Read the matching validation artifact in `artifacts/flowise/`.
4. Read the matching audit artifact in `artifacts/flowise/`.
5. Identify concrete defects, not prompt preferences.
6. Distinguish ACTION findings from ADVICE findings.

## Output

Write `artifacts/flowise/<slug>.review.md` with:

- verdict: PASS or FAIL
- actionable defects with file-local evidence
- repair priorities in the order they should be fixed

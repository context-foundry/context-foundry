---
name: build-flowise
description: Build or update a Flowise AgentFlow v2 JSON file with selective retrieval, validation, and audit. Use when asked to create or modify audited Flowise flows.
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Edit
  - MultiEdit
  - Bash
argument-hint: "Describe the flow to build"
---

Build a Flowise AgentFlow v2 for:

$ARGUMENTS

## Selected Context

!`python3 "${CLAUDE_SKILL_DIR}/../../../scripts/flowise-select-context.py" --manifest "${CLAUDE_SKILL_DIR}/../../../.flowise-kit/manifest.json" --query "$ARGUMENTS"`

## Steps

1. Read `AGENTS.md` and the selected context report.
2. Read only the example flows, templates, and expertise slices named in the selection report.
3. Build or update exactly one flow JSON in `output/`.
4. Run:
   - `scripts/validate-flowise.sh <file>`
   - `scripts/audit-flowise.sh <file>`
5. If either check fails, use the `repair-flowise` workflow logic and rerun both checks.
6. Stop only when both checks pass or when you can point to concrete blocking findings.

## Output

- Flow file in `output/`
- validation artifact in `artifacts/flowise/`
- audit artifact in `artifacts/flowise/`

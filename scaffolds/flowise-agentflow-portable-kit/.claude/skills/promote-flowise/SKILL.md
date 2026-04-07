---
name: promote-flowise
description: Promote a passing Flowise flow from output into example-flows and update retrieval metadata. Use when a draft flow becomes a durable reference.
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Edit
  - MultiEdit
  - Bash
argument-hint: "Source flow path and destination example path"
---

Promote the passing flow described by:

$ARGUMENTS

## Steps

1. Confirm the source flow already passes validation and audit.
2. Move or copy it into `example-flows/`.
3. Update `.flowise-kit/manifest.json` if this flow should be part of retrieval.
4. If this adds a durable new pattern, note it for upstream corpus maintenance.

## Rules

- Do not promote failing or partially edited drafts.
- Keep example names stable and descriptive.

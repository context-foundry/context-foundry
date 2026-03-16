---
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
argument-hint: "What are you trying to build or understand?"
---

Investigate this codebase to prepare for implementation work.

## Steps

1. Read `CLAUDE.md`, `SPEC.md`, `TASKS.md` if they exist.
2. Detect tech stack from project files (Cargo.toml, package.json, pyproject.toml, etc.).
3. Read relevant source files based on the user's intent.
4. Identify risks, constraints, and architectural patterns.

## Output

Write findings to `.buildloop/scout-report.md` with these sections:

```markdown
# Scout Report

## Tech Stack
- Language, framework, key dependencies

## Relevant Files
- file.rs -- what it does and why it matters for this task

## Architecture Notes
- How the system is structured, key patterns

## Risks
- What could go wrong, edge cases, constraints

## Suggested Approach
- Recommended implementation strategy
```

## Rules
- Read-only. Do not modify any files except `.buildloop/scout-report.md`.
- Be specific. Cite file:line for every claim.
- Focus on what's relevant to the user's stated intent.

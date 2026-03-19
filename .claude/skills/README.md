# Claude Code Skills

Skills are slash commands for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Type `/skill-name` in a Claude Code session to run one. Each skill runs in a forked context with scoped tool access, so it can't accidentally modify files it shouldn't.

These skills mirror the pipeline stages that foundry runs autonomously, but packaged for interactive use -- useful when you want to run a single stage manually instead of the full loop.

## Available Skills

| Skill | Command | Tools | Purpose |
|-------|---------|-------|---------|
| **audit** | `/audit` | Read, Grep, Glob, Bash | Fresh-context code review. Reads build claims, verifies them against actual code, runs `cargo build`, `cargo test`, and `cargo clippy`. Writes findings to `.buildloop/review-report.md`. |
| **extract-patterns** | `/extract-patterns` | Read, Write, Grep, Glob | Scans build artifacts and review reports for reusable lessons. Deduplicates against existing patterns and writes 0-5 new patterns to `.buildloop/patterns-extracted.json`. |
| **scout** | `/scout` | Read, Grep, Glob, Bash | Read-only codebase investigation. Detects tech stack, reads key files, identifies risks. Writes a scout report to `.buildloop/scout-report.md`. |

## How they work

Each skill has a `SKILL.md` file with frontmatter that controls execution:

```yaml
---
context: fork           # Runs in an isolated context
allowed-tools:          # Only these tools are available
  - Read
  - Grep
argument-hint: "..."    # Prompt shown when invoking
---
```

The `context: fork` setting means the skill runs with a fresh context -- it doesn't see your conversation history. This is intentional for audit and review tasks where independent judgment matters.

## Relationship to foundry

These are the same operations foundry's autonomous pipeline runs (SCOUT, VERIFY, PATTERN EXTRACTOR), exposed as manual commands. Use them when you want human-in-the-loop control over individual stages, or when working outside the full pipeline.

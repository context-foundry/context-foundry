---
paths:
  - "src/prompts.rs"
---

# Prompt Engineering

## Prompt Functions
| Function | Role | Output |
|----------|------|--------|
| `planner_prompt()` | Plan implementation | `.buildloop/current-plan.md` |
| `builder_prompt()` | Execute plan | Code changes |
| `reviewer_prompt()` | Validate changes | `.buildloop/review-report.md` (JSON findings) |
| `fixer_prompt()` | Fix review issues | Code changes |
| `pattern_extraction_prompt()` | Extract learnings | `.buildloop/patterns-extracted.json` |
| `discovery_prompt()` | Find new work | Appends tasks to TASKS.md |

## Conventions
- Raw string literals: `r#"..."#`
- Pattern context injected as clearly delimited reference blocks (not authoritative instructions).
- Reviewer is READ-ONLY — cannot mutate services or run `docker compose up`.
- Stack detection: looks for Cargo.toml (Rust), package.json (Node), pyproject.toml (Python), etc.
- Every finding must cite file, line, and concrete issue.

## When Modifying Prompts
- Keep prompts focused on the role — planner plans, builder builds, reviewer only reads.
- Maintain the JSON structure for review findings (reviewer parses it programmatically).
- Test prompt changes with `cargo test` — prompts.rs has unit tests for context wrapping.

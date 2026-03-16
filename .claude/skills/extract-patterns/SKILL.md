---
context: fork
allowed-tools:
  - Read
  - Write
  - Grep
  - Glob
argument-hint: "Task ID or description of work to extract patterns from (or blank for latest)"
---

Extract reusable patterns from recent build artifacts.

## Steps

1. Read `.buildloop/build-claims.md` and `.buildloop/review-report.md` if they exist.
2. Read recent git history: `git log --oneline -5`
3. Identify 0-5 reusable patterns -- things that went wrong, non-obvious solutions, or techniques worth remembering.
4. Check existing patterns in `~/.foundry/patterns/` to avoid duplicates.

## Output

Write patterns to `.buildloop/patterns-extracted.json`:

```json
[
  {
    "pattern_id": "kebab-case-id",
    "title": "Short descriptive title",
    "severity": "HIGH|MEDIUM|LOW",
    "keywords": ["keyword1", "keyword2"],
    "tech_stack": ["rust"],
    "issue": "What went wrong or what was non-obvious",
    "solution": {
      "planner": "What the planner should do differently",
      "reviewer": "What the reviewer should check for"
    }
  }
]
```

## Rules
- Only extract genuinely reusable patterns, not task-specific details.
- Check for duplicates before writing.
- If nothing worth extracting, write an empty array `[]`.

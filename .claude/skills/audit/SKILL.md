---
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
argument-hint: "Describe what was changed (or leave blank to auto-detect from git diff)"
---

Audit and validate recent changes. You are a fresh-context reviewer with no knowledge of why these changes were made -- that's the point.

## Steps

1. If the user provided a description, use it. Otherwise, run `git diff HEAD~1 --stat` to see what changed.
2. Read `.buildloop/build-claims.md` if it exists. These are the builder's claims about what was implemented.
3. For every claim, verify it against the actual code. Read the files, check the logic.
4. Run the build: `cargo build 2>&1` and tests: `cargo test 2>&1`
5. Run `cargo clippy -- -D warnings 2>&1`

## Output Format

Write findings to `.buildloop/review-report.md`:

```markdown
# Review Report

## Verdict: PASS | FAIL

## Findings
```json
{
  "high": [{"file": "path", "line": N, "issue": "description", "category": "bug|security|logic"}],
  "medium": [{"file": "path", "line": N, "issue": "description", "category": "error-handling|correctness"}],
  "low": [{"file": "path", "line": N, "issue": "description", "category": "style|naming"}]
}
```

## What to Report
- Bugs, security issues, logic errors
- Missing error handling at system boundaries
- Claims in build-claims.md that don't match actual code

## What to Skip
- Style preferences consistent with existing code
- Minor naming choices in local scope
- Patterns that match the rest of the codebase

@AGENTS.md

## Claude Code

- Use the project skills under `.claude/skills/` for Flowise work.
- Load only the corpus selected by `scripts/flowise-select-context.py`.
- Let hooks write validation and audit artifacts after JSON edits.
- If `artifacts/flowise/latest-status.json` reports failure, continue repairing instead of stopping.

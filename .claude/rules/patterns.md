---
paths:
  - "src/patterns.rs"
  - "**/*.json"
---

# Pattern System (LEGACY)

> **Deprecated as of v3.3.0.** Patterns have been replaced by Anthropic Agent Skills (`SKILL.md` files). See `.claude/rules/plugins.md` for the current system. The loader at `src/patterns.rs:233` reads `~/.foundry/skills/` first and falls back to JSON patterns only when no skills exist. This document describes the fallback format. Do not author new patterns; write skills instead.

## Pattern JSON Schema (legacy)
```json
{
  "pattern_id": "kebab-case-id",
  "title": "Short descriptive title",
  "first_seen": "task_id",
  "last_seen": "task_id",
  "frequency": 1,
  "severity": "HIGH|MEDIUM|LOW",
  "keywords": ["keyword1", "keyword2"],
  "tech_stack": ["python", "fastapi"],
  "issue": "What goes wrong",
  "solution": {
    "planner": "What the planner should do differently",
    "reviewer": "What the reviewer should check for"
  },
  "auto_apply": false,
  "learned_from": "task_id"
}
```

## Storage Locations
- **Global**: `~/.foundry/patterns/` — shared across all projects, loaded by default
- **Project**: `.foundry/patterns/` — project-specific learnings
- **Plugins** (legacy): `plugins/<name>/patterns/` — domain-specific JSON fallback. New plugin learnings should go to `plugins/<name>/skills/<topic>/SKILL.md` instead.

## Matching Algorithm
- Exact word match = +2 points, substring = +1, tech stack = +1 each
- `auto_apply` boost = +2, frequency >= 3 boost = +1
- Auto-promote to `auto_apply` when frequency reaches 3
- Top 10 matched patterns injected into planner/reviewer prompts

## After Solving Issues
1. Add to the relevant patterns file (extension or project).
2. Merge to global: `mcp__context-foundry__merge_project_patterns(path, "common-issues")`
3. Patterns deduplicate by `pattern_id` on merge.

## Extension Pattern Format
Extensions use a wrapper object:
```json
{
  "pattern_type": "common-issues",
  "domain": "roblox",
  "version": "1.0.0",
  "last_updated": "2025-11-25",
  "patterns": [ ... ]
}
```

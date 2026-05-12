# Plugins

A **plugin** (also called a **domain pack**, formerly **extension**) is a self-contained knowledge package that teaches foundry agents how to work with a specialized technology or domain. Plugins live in `plugins/<name>/` directories and are discovered automatically from three locations (highest priority wins):

1. `<project>/plugins/` (project-local)
2. Ancestor directories' `plugins/` folders (closest wins)
3. `~/.foundry/plugins/` (global)

The legacy `extensions/` directory name is auto-migrated on first startup; references in old docs or configs continue to load via a one-shot `fs::rename`.

## Taxonomy

A plugin is a directory containing any combination of these component types:

| Component | Location | Purpose | Required? |
|-----------|----------|---------|-----------|
| **Instructions** | `CLAUDE.md` | Authored domain rules, critical constraints, and session-start checklists. Always injected into agent prompts when the plugin is selected. | Yes (only required file) |
| **Skills** | `skills/<topic>/SKILL.md` | Learned domain pitfalls and solutions in the Anthropic Agent Skills format. Ranked by the hybrid retriever (BM25 + nomic-embed cosine + telemetry) and injected per stage. | No |
| **Docs** | `docs/` | Reference guides, specs, API documentation, governance lists, asset inventories, analyzer output. | No |
| **Templates** | `templates/` | Starter blueprints and proven command templates for common operations. | No |
| **Examples** | `examples/` | Working reference implementations, sample projects, and demo flows. | No |
| **Patterns (legacy)** | `patterns/*.json` | Pre-T1.13 pattern JSON. Read-only fallback — loaded only when no `skills/` directory is present. Do not add new entries here. | No |

### Directory structure

```
plugins/<name>/
├── CLAUDE.md                          # Instructions (required)
├── skills/
│   └── <topic>/
│       └── SKILL.md                   # One skill per directory (Anthropic Skills format)
├── docs/                              # Reference guides, specs, asset catalogs
├── templates/                         # Starter blueprints, command templates
├── examples/                          # Working reference projects
├── scripts/                           # Utility scripts
├── config/                            # Configuration files
└── patterns/                          # Legacy JSON (read-only fallback, deprecated)
```

## What Belongs Where

| File type | Correct location | NOT in |
|-----------|-----------------|--------|
| Learned pitfalls with `name`, `description`, body | `skills/<topic>/SKILL.md` | `docs/`, `patterns/` |
| API documentation, specs, developer guides | `docs/` | `skills/` |
| Asset inventories, catalog JSON | `docs/` | `skills/` |
| Governance lists (approved sources, allowed repos) | `docs/` | `skills/` |
| Analyzer output, expertise metadata | `docs/` | `skills/` |
| Command templates, starter configs | `templates/` | `skills/`, `docs/` |
| Sample projects, demo flows | `examples/` | `docs/` |
| Critical rules, session checklists | `CLAUDE.md` | `docs/` |

**The `skills/` directory holds Anthropic Agent Skills.** Each immediate subdirectory contains one `SKILL.md` file (plus optional supporting assets). The retriever ranks every skill in every plugin per stage per task and injects the top N.

**The `patterns/` directory is deprecated.** Foundry's loader at `src/patterns.rs` reads `skills/` first and only falls back to `patterns/*.json` when no skills exist. New learnings should be written as `SKILL.md`, not JSON. Existing `patterns/*.json` files are left in place as read-only fallback for back-compat.

### Canonical SKILL.md schema

```markdown
---
name: kebab-case-skill-id
description: One-sentence "use when..." trigger. The retriever matches
  the task description against this field, so be specific.
metadata:
  cf-stage: planner          # planner | reviewer | both — hint, not a filter
  cf-keywords: [searchable, terms, tech-stack-tags]
  cf-severity: HIGH          # HIGH | MEDIUM | LOW
  cf-citations-pass: 0       # auto-updated by post-AUDIT scanner
  cf-citations-wip: 0        # auto-updated by post-AUDIT scanner
---

## Issue
What goes wrong — prose description, file:line evidence if applicable.

## Solution
What the planner should do, what the reviewer should check for.
```

Required frontmatter fields: `name`, `description`. The `metadata` block is optional; all `cf-*` fields default. The body is free-form Markdown.

## Using a Plugin

1. Create your plugin folder:
   ```bash
   mkdir -p plugins/my-tech/skills
   ```

2. Write a `CLAUDE.md` with critical rules and references your agents need.

3. Reference it from your project's `CLAUDE.md`:
   ```markdown
   ## Plugin
   Read /path/to/context-foundry/plugins/my-tech/CLAUDE.md for domain rules.
   ```

## External skills

If your project already has skill / instruction files authored for other AI
tools (`AGENTS.md`, `.cursorrules`, or project-local
`.claude/skills/<topic>/SKILL.md`), CF surfaces them in a startup-screen
"External Skills" section and lets you opt them into the planner-prompt
context per project. Read-only -- CF never modifies those files. See
[`docs/cross-provider-skills.md`](../docs/cross-provider-skills.md) for the
full reference.

4. Run foundry — agents read the plugin docs during planning and building. The TUI startup screen shows each discovered plugin with its name, skill count, and a one-line description extracted from the first non-heading paragraph of its `CLAUDE.md`.

## Plugin Ideas

- **Game engines** — Roblox, Unity, Godot rules and patterns
- **Frameworks** — Next.js, Rails, FastAPI conventions
- **Platforms** — Workday, Salesforce, AWS CDK guides
- **Workflows** — Flowise, n8n, Temporal patterns
- **Languages** — Luau, Zig, Elixir idioms and gotchas

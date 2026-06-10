---
paths:
  - "plugins/**/*"
---

# Plugins

Plugins are domain-specific knowledge packages under `plugins/`. The legacy `extensions/` directory is auto-migrated on first startup (one-shot `fs::rename`); do not reference it in new code or docs.

## Taxonomy

A **plugin** (or **domain pack**) is a directory containing any combination of:

| Component | Location | Purpose |
|-----------|----------|---------|
| **Instructions** | `CLAUDE.md` | Authored domain rules; always injected into agent prompts |
| **Skills** | `skills/<topic>/SKILL.md` | Learned domain pitfalls in Anthropic Agent Skills format; retriever ranks per stage |
| **Docs** | `docs/` | Reference guides, specs, API docs, asset inventories |
| **Templates** | `templates/` | Starter blueprints, command templates |
| **Examples** | `examples/` | Working reference implementations |
| **Patterns (legacy)** | `patterns/*.json` | Pre-T1.13 JSON. Read-only fallback. Do not add new entries. |

## Structure Convention
```
plugins/<name>/
├── CLAUDE.md                       # Domain rules (read before any work in this domain)
├── skills/
│   └── <topic>/SKILL.md            # One skill per directory (Anthropic Skills format)
├── docs/                           # Reference guides, specs, asset catalogs
├── templates/                      # Starter blueprints, command templates
├── examples/                       # Working reference projects
├── scripts/                        # Utility scripts
├── config/                         # Configuration
└── patterns/                       # Legacy JSON (deprecated, read-only fallback)
```

## What Belongs Where

| File type | Correct location | NOT in |
|-----------|-----------------|--------|
| Learned pitfalls (`name`, `description`, body) | `skills/<topic>/SKILL.md` | `docs/`, `patterns/` |
| API docs, specs, developer guides | `docs/` | `skills/` |
| Asset inventories, catalog JSON, governance lists | `docs/` | `skills/` |
| Analyzer output, expertise metadata | `docs/` | `skills/` |
| Command templates, starter configs | `templates/` | `skills/` |
| Sample projects, demo flows | `examples/` | `docs/` |

**Rule: new learnings go to `skills/<topic>/SKILL.md`, not `patterns/*.json`.** The loader at `src/patterns.rs:233` reads `skills/` first and falls back to `patterns/` only when no skills exist. Pattern JSON is deprecated; do not add new entries to it.

### SKILL.md schema

```markdown
---
name: kebab-case-skill-id
description: One-sentence "use when..." trigger. Retriever matches against this.
metadata:
  cf-stage: planner          # planner | reviewer | both — hint, not filter
  cf-keywords: [searchable, terms, tech-stack-tags]
  cf-severity: HIGH
  cf-citations-pass: 0       # auto-updated by post-AUDIT scanner
  cf-citations-wip: 0
---

## Issue
What goes wrong.

## Solution
What planner should do, what reviewer should check for.
```

Required frontmatter: `name`, `description`. All `metadata.cf-*` fields default.

## Available Plugins

| Plugin | Domain | Key Trigger |
|--------|--------|-------------|
| `roblox` | Roblox world gen, Lune scripting | .rbxl/.rbxm files, Roblox work |
| `extend` | Workday Extend apps | Orchestrations, integrations, BIRT |
| `workday-agents` | Workday Marketplace compliance agents | ACA, multi-state tax, compliance rule engines |
| `flowise` | Flowise AI workflows | AgentFlow v2, chatflows |
| `recon` | Fleet ops, iDRAC queries | Server inventory, batch ops |

## Rules
- **Always read the plugin's CLAUDE.md** before working in that domain.
- Plugin CLAUDE.md files are discovered automatically when Claude reads files in those directories.
- When solving new domain issues, write a new `skills/<topic>/SKILL.md` in the relevant plugin. Do NOT add to `patterns/*.json`.
- **Never put non-skill files in `skills/`.** Reference docs, asset catalogs, and analyzer output go in `docs/`.

## MCP Server
The MCP server (`src/mcp.rs`) exposes **resources only** over stdio. No tool calls.

| URI | Purpose |
|-----|---------|
| `foundry://plugins/index` | List of available plugins with name, description, source, skill count |
| `foundry://patterns/catalog` | Legacy pattern catalog (gated by `pattern_dual_emit`; returns `[]` when off) |

To load skills, read the SKILL.md files under `plugins/<plugin>/skills/<slug>/` directly. The plugin index resource helps discover which plugins are available.

---
paths:
  - "extensions/**/*"
---

# Extensions

Extensions are domain-specific knowledge packages under `extensions/`.

## Taxonomy

An **extension** (or **domain pack**) is a directory containing any combination of:

| Component | Location | Purpose |
|-----------|----------|---------|
| **Instructions** | `CLAUDE.md` | Authored domain rules; always injected into agent prompts |
| **Patterns** | `patterns/*.json` | Learned recurring pitfalls in canonical schema; keyword-matched at plan time |
| **Docs** | `docs/` | Reference guides, specs, API docs, asset inventories |
| **Templates** | `templates/` | Starter blueprints, command templates |
| **Examples** | `examples/` | Working reference implementations |

## Structure Convention
```
extensions/<name>/
├── CLAUDE.md                          # Domain rules (read before any work in this domain)
├── patterns/<name>-common-issues.json # Canonical pattern JSON only
├── docs/                              # Reference guides, specs, asset catalogs
├── templates/                         # Starter blueprints, command templates
├── examples/                          # Working reference projects
├── scripts/                           # Utility scripts
└── config/                            # Configuration
```

## What Belongs Where

| File type | Correct location | NOT in |
|-----------|-----------------|--------|
| Learned pitfalls (`pattern_id`, `title`, `issue`, `solution`) | `patterns/` | `docs/` |
| API docs, specs, developer guides | `docs/` | `patterns/` |
| Asset inventories, catalog JSON, governance lists | `docs/` | `patterns/` |
| Analyzer output, expertise metadata | `docs/` | `patterns/` |
| Command templates, starter configs | `templates/` | `patterns/` |
| Sample projects, demo flows | `examples/` | `docs/` |

**Rule: `patterns/` is ONLY for canonical-schema pattern JSON.** Every file in `patterns/` must parse as `Vec<Pattern>`, `PatternWrapper { patterns: Vec<Pattern> }`, or a single `Pattern` per `src/patterns.rs`. Non-pattern files (reference docs, asset catalogs, expertise metadata) belong in `docs/`.

## Available Extensions

| Extension | Domain | Key Trigger |
|-----------|--------|-------------|
| `roblox` | Roblox world gen, Lune scripting | .rbxl/.rbxm files, Roblox work |
| `extend` | Workday Extend apps | Orchestrations, integrations, BIRT |
| `workday-agents` | Workday Marketplace compliance agents | ACA, multi-state tax, compliance rule engines |
| `flowise` | Flowise AI workflows | AgentFlow v2, chatflows |
| `workday` | Workday platform | Learning patterns |
| `recon` | Fleet ops, iDRAC queries | Server inventory, batch ops |

## Rules
- **Always read the extension's CLAUDE.md** before working in that domain.
- Extension CLAUDE.md files are discovered automatically when Claude reads files in those directories.
- When solving new domain issues, update the extension's patterns file — not just the global one.
- **Never put non-pattern files in `patterns/`.** Reference docs, asset catalogs, and analyzer output go in `docs/`.

## MCP Tools
| Tool | Purpose |
|------|---------|
| `read_global_patterns` | Load learned patterns before starting |
| `save_global_patterns` | Save new discoveries |
| `merge_project_patterns` | Promote project patterns to global |
| `delegate_to_claude_code` | Spawn fresh agent for subtasks |
| `search_skills` | Find reusable code/patterns |

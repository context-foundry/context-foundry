# Extensions

An **extension** (also called a **domain pack**) is a self-contained knowledge package that teaches foundry agents how to work with a specialized technology or domain. Extensions live in `extensions/<name>/` directories and are discovered automatically from three locations (highest priority wins):

1. `<project>/extensions/` (project-local)
2. Ancestor directories' `extensions/` folders (closest wins)
3. `~/.foundry/extensions/` (global)

## Taxonomy

An extension is a directory containing any combination of these component types:

| Component | Location | Purpose | Required? |
|-----------|----------|---------|-----------|
| **Instructions** | `CLAUDE.md` | Authored domain rules, critical constraints, and session-start checklists. Always injected into agent prompts when the extension is selected. | Yes (only required file) |
| **Patterns** | `patterns/*.json` | Learned recurring pitfalls in canonical pattern schema. Keyword-matched at plan time and injected as warnings. | No |
| **Docs** | `docs/` | Reference guides, specs, API documentation, governance lists, asset inventories, analyzer output. | No |
| **Templates** | `templates/` | Starter blueprints and proven command templates for common operations. | No |
| **Examples** | `examples/` | Working reference implementations, sample projects, and demo flows. | No |

### Directory structure

```
extensions/<name>/
├── CLAUDE.md                          # Instructions (required)
├── patterns/
│   └── <name>-common-issues.json      # Canonical pattern JSON only
├── docs/                              # Reference guides, specs, asset catalogs
├── templates/                         # Starter blueprints, command templates
├── examples/                          # Working reference projects
├── scripts/                           # Utility scripts
└── config/                            # Configuration files
```

## What Belongs Where

| File type | Correct location | NOT in |
|-----------|-----------------|--------|
| Learned pitfalls with `pattern_id`, `title`, `issue`, `solution` fields | `patterns/` | `docs/` |
| API documentation, specs, developer guides | `docs/` | `patterns/` |
| Asset inventories, catalog JSON | `docs/` | `patterns/` |
| Governance lists (approved sources, allowed repos) | `docs/` | `patterns/` |
| Analyzer output, expertise metadata | `docs/` | `patterns/` |
| Command templates, starter configs | `templates/` | `patterns/`, `docs/` |
| Sample projects, demo flows | `examples/` | `docs/` |
| Critical rules, session checklists | `CLAUDE.md` | `docs/` |

**The `patterns/` directory is ONLY for canonical-schema pattern JSON files.** Every file in `patterns/` must be parseable by foundry's pattern loader (`src/patterns.rs`) as either a `Vec<Pattern>`, a `PatternWrapper { patterns: Vec<Pattern> }`, or a single `Pattern`. Files that do not conform to this schema (reference docs, asset catalogs, expertise metadata, governance lists) belong in `docs/` instead.

### Canonical pattern schema

```json
[
  {
    "pattern_id": "unique-kebab-id",
    "title": "Short description of the pitfall",
    "keywords": ["searchable", "terms"],
    "tech_stack": ["technology", "framework"],
    "issue": "What goes wrong — prose description",
    "solution": {
      "planner": "What the planner should do to avoid this",
      "reviewer": "What the reviewer should check for"
    },
    "severity": "HIGH",
    "frequency": 1,
    "auto_apply": false
  }
]
```

Required fields: `pattern_id`, `title`. All other fields have defaults.

## Using an Extension

1. Create your extension folder:
   ```bash
   mkdir -p extensions/my-tech/patterns
   ```

2. Write a `CLAUDE.md` with critical rules and references your agents need.

3. Reference it from your project's `CLAUDE.md`:
   ```markdown
   ## Extension
   Read /path/to/context-foundry/extensions/my-tech/CLAUDE.md for domain rules.
   ```

4. Run foundry — agents read the extension docs during planning and building. The TUI startup screen shows each discovered extension with its name, pattern count, and a one-line description extracted from the first non-heading paragraph of its `CLAUDE.md`.

## Extension Ideas

- **Game engines** — Roblox, Unity, Godot rules and patterns
- **Frameworks** — Next.js, Rails, FastAPI conventions
- **Platforms** — Workday, Salesforce, AWS CDK guides
- **Workflows** — Flowise, n8n, Temporal patterns
- **Languages** — Luau, Zig, Elixir idioms and gotchas

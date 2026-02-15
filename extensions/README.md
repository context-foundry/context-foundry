# Extensions

Extensions are domain-specific knowledge packages that teach foundry agents how to work with specialized technologies. They live in this directory and get referenced from your project's `CLAUDE.md`.

## What's in an Extension

An extension is just a folder with knowledge files:

```
extensions/
└── roblox/
    ├── CLAUDE.md                  # Quick reference and critical rules
    ├── patterns/
    │   └── common-issues.json     # Learned patterns (auto-merged by foundry)
    ├── prompts/                   # Phase-specific guidance (optional)
    │   ├── planner.md
    │   └── validator.md
    ├── docs/                      # Guides, specs, API references
    └── examples/                  # Working reference projects or templates
```

The only required file is `CLAUDE.md` — everything else is optional.

## Using an Extension

1. Create your extension folder here:
   ```bash
   mkdir -p extensions/my-tech/patterns
   ```

2. Write a `CLAUDE.md` with the critical rules and references your agents need.

3. Reference it from your project's `CLAUDE.md`:
   ```markdown
   ## Extension
   Read /path/to/context-foundry/extensions/my-tech/CLAUDE.md for domain rules.
   ```

4. Run foundry as usual — agents will read the extension docs during planning and building.

## Patterns

The `patterns/` folder holds JSON files that foundry's pattern system loads automatically via `~/.foundry/patterns/`. You can also keep extension-specific patterns here and reference them from your project.

Pattern files follow this structure:

```json
[
  {
    "pattern_id": "unique-kebab-id",
    "title": "Short description",
    "keywords": ["searchable", "terms"],
    "tech_stack": ["roblox", "luau"],
    "issue": "What goes wrong",
    "solution": {
      "planner": "What the planner should do",
      "validator": "What the validator should check"
    },
    "severity": "HIGH",
    "frequency": 1,
    "auto_apply": false
  }
]
```

## Examples

Extension ideas:
- **Game engines** — Roblox, Unity, Godot rules and patterns
- **Frameworks** — Next.js, Rails, FastAPI conventions
- **Platforms** — Workday, Salesforce, AWS CDK guides
- **Workflows** — Flowise, n8n, Temporal patterns
- **Languages** — Luau, Zig, Elixir idioms and gotchas

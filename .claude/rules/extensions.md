---
paths:
  - "extensions/**/*"
---

# Extensions

Extensions are domain-specific knowledge packages under `extensions/`.

## Structure Convention
```
extensions/<name>/
├── CLAUDE.md                          # Domain rules (read before any work in this domain)
├── patterns/<name>-common-issues.json # Learned issues
├── docs/                              # Deep guides and specs
├── examples/                          # Working reference projects
├── scripts/                           # Utility scripts
└── config/                            # Configuration
```

## Available Extensions

| Extension | Domain | Key Trigger |
|-----------|--------|-------------|
| `roblox` | Roblox world gen, Lune scripting | .rbxl/.rbxm files, Roblox work |
| `extend` | Workday Extend apps | Orchestrations, integrations, BIRT |
| `workday-agents` | Workday Marketplace compliance agents | ACA, multi-state tax, compliance rule engines |
| `flowise` | Flowise AI workflows | AgentFlow v2, chatflows |
| `workday` | Workday platform | Learning patterns |

## Rules
- **Always read the extension's CLAUDE.md** before working in that domain.
- Extension CLAUDE.md files are discovered automatically when Claude reads files in those directories.
- When solving new domain issues, update the extension's patterns file — not just the global one.

## MCP Tools
| Tool | Purpose |
|------|---------|
| `read_global_patterns` | Load learned patterns before starting |
| `save_global_patterns` | Save new discoveries |
| `merge_project_patterns` | Promote project patterns to global |
| `delegate_to_claude_code` | Spawn fresh agent for subtasks |
| `search_skills` | Find reusable code/patterns |

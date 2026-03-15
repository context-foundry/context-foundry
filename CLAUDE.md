# Context Foundry

Context Foundry is a pattern-learning system that helps AI agents improve over time by capturing and sharing solutions to common problems.

## Global Patterns

Patterns are stored in `~/.context-foundry/patterns/`. Read them before starting work:

```lua
mcp__context-foundry__read_global_patterns("common-issues")
```

## Extensions

Context Foundry has domain-specific extensions. **When working on tasks for a specific domain, read that extension's CLAUDE.md first.**

### Roblox Extension
**Location:** `extensions/roblox/`
**When to read:** Any Roblox world generation, Lune scripting, or .rbxl/.rbxm work

**IMPORTANT - Read before Roblox work:**
- `extensions/roblox/CLAUDE.md` - Critical patterns and commands
- `extensions/roblox/patterns/roblox-common-issues.json` - Learned issues

**Key learnings:**
- Use `add_to_world.luau` (not `generate_world.luau`)
- Use CFrame, not Position, for moving parts
- Don't generate worlds from scratch - load original and clone

### Workday Extend Extension
**Location:** `extensions/extend/`
**When to read:** Any Workday Extend app development, orchestrations, integrations, security configuration, BIRT reports, or Workday API work

**IMPORTANT - Read before Extend work:**
- `extensions/extend/CLAUDE.md` - Index of all guides and critical rules
- `extensions/extend/WORKDAY_EXTEND_DEVELOPER_GUIDE.md` - Comprehensive dev workflow
- `extensions/extend/WORKDAY_EXTEND_ARCHITECTURE.md` - AMD/PMD/SMD metadata structures
- `extensions/extend/orchestrations-integrations-guide.md` - Orchestrations deep dive
- `extensions/extend/security-reporting-birt-notes.md` - Security, reporting, BIRT

**Key learnings:**
- Extend apps are metadata-driven (no arbitrary code execution)
- Always activate security policy changes after modification
- WIDs are tenant-specific -- use Reference IDs instead
- Credentials never migrate between tenants
- Test before every biannual Workday release

### Recon Extension
**Location:** `extensions/recon/`
**When to read:** Any fleet checks, iDRAC queries, racadm commands, server inventory lookups, or batch ops from a management server

**IMPORTANT - Read before ops/recon work:**
- `extensions/recon/CLAUDE.md` - Domain rules and key files
- `extensions/recon/config/inventory-schema.json` - CSV column mapping
- `extensions/recon/templates/` - Proven command templates

**Key learnings:**
- Always use `grep -w` for hostname lookups (avoid substring matches)
- SSH to iDRAC needs `-o ConnectTimeout=5` to avoid hanging loops
- Always label batch output with the current hostname

### Other Extensions
| Extension | Path | Domain |
|-----------|------|--------|
| Flowise | `extensions/flowise/` | Flowise AI workflows |
| Workday | `extensions/workday/` | Workday learning patterns |

## MCP Tools Available

Context Foundry provides these MCP tools:

| Tool | Purpose |
|------|---------|
| `read_global_patterns` | Read learned patterns |
| `save_global_patterns` | Save new patterns |
| `merge_project_patterns` | Merge project patterns to global |
| `delegate_to_claude_code` | Delegate tasks to fresh Claude instances |
| `search_skills` | Find reusable code skills |

## After Solving Issues

When you solve a new problem, save the pattern:

1. Add to the relevant extension's patterns file
2. Merge to global: `mcp__context-foundry__merge_project_patterns(path, "common-issues")`

This helps future agents avoid the same issues.

## Doubt Loop

The doubt loop is handled by the VERIFY stage of the SPID pipeline (a fresh-context
agent that reads build-claims.md and audits with "Audit and validate these claims.
Find the gaps."). Individual agents (scout, planner, builder) should NOT self-audit
or spawn sub-agents for verification -- that wastes time and tokens. Focus on doing
your job well and let VERIFY catch the gaps with fresh eyes.

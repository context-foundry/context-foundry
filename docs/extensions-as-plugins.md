# Extensions as Anthropic Plugins (T1.14)

Context Foundry's `extensions/<name>/` directories now ship in two compatible layouts at once:

- **Legacy layout** (pre-T1.14): a single `CLAUDE.md` plus optional `patterns/`, `docs/`, `templates/`, `examples/`.
- **Plugin layout** (T1.14+): a `.claude-plugin/plugin.json` manifest plus one or more `skills/<topic>/SKILL.md` files.

The plugin layout aligns with the [Anthropic Plugins reference](https://code.claude.com/docs/en/plugins-reference) and the [Skills specification](https://agentskills.io/specification), so any extension is installable via:

```bash
claude /plugin install <local-path-or-repo>
```

## What changed

For each in-scope extension (`roblox`, `extend`, `recon`, `workday-agents`, `flowise`, `workday`), T1.14 added:

1. `extensions/<name>/.claude-plugin/plugin.json` -- the Anthropic plugin manifest (`name`, `version`, `description`, `author`, `keywords`).
2. `extensions/<name>/skills/<topic>/SKILL.md` -- one skill mirroring the existing `CLAUDE.md` body, with standard Anthropic Skills frontmatter (`name`, `description`).

The original `CLAUDE.md` is preserved. The migration is additive.

## How Context Foundry's loader picks between layouts

`src/extensions.rs::scan_extensions_dir` accepts a directory as an extension when it has either `CLAUDE.md` OR `.claude-plugin/plugin.json`.

`src/extensions.rs::load_extension_context` reads the body that goes inside the `--- BEGIN EXTENSION CONTEXT: <name> ---` / `--- END EXTENSION CONTEXT: <name> ---` block as follows:

1. If the extension has a `skills/` directory containing at least one `<topic>/SKILL.md`, concatenate every SKILL.md body (frontmatter stripped) in lexicographic order.
2. Otherwise, fall back to reading `CLAUDE.md`.

The `BEGIN/END EXTENSION CONTEXT` delimiter format is unchanged -- Context Foundry still owns the per-stage injection policy. Only the source of the body changes.

## Adding a new skill to an existing plugin extension

1. Create `extensions/<name>/skills/<new-topic>/SKILL.md`.
2. Use this frontmatter shape:
   ```markdown
   ---
   name: <new-topic>
   description: <one-sentence trigger phrase: when should the agent activate this skill>
   ---

   <skill body in Markdown>
   ```
3. The next pipeline run picks up the new SKILL.md automatically -- no code changes required.

## Adding a new plugin extension from scratch

1. Create `extensions/<name>/.claude-plugin/plugin.json` matching the schema below.
2. Create at least one `extensions/<name>/skills/<topic>/SKILL.md`.
3. (Optional) Create `extensions/<name>/CLAUDE.md` if you want a legacy reader to still see the rules without the skill loader.

### plugin.json minimum schema

```json
{
  "name": "context-foundry-<name>",
  "version": "0.1.0",
  "description": "<one-line description>",
  "author": { "name": "Context Foundry", "url": "https://github.com/snedea/context-foundry" },
  "homepage": "https://github.com/snedea/context-foundry/tree/main/extensions/<name>",
  "repository": "https://github.com/snedea/context-foundry",
  "license": "MIT",
  "keywords": ["..."]
}
```

## Removed responsibilities

- Context Foundry's loader no longer inspects `CLAUDE.md` first when `skills/` is present -- skills win.
- Context Foundry still owns the *injection policy* (which extensions are selected per stage, the `BEGIN/END EXTENSION CONTEXT` framing). The Anthropic plugin spec only owns the on-disk *transport*.

## In-scope extensions

| Extension | Plugin name | Skill(s) |
|-----------|-------------|----------|
| `roblox` | `context-foundry-roblox` | `skills/roblox-world-gen/SKILL.md` |
| `extend` | `context-foundry-workday-extend` | `skills/workday-extend-pmd/SKILL.md` |
| `recon` | `context-foundry-recon` | `skills/fleet-recon/SKILL.md` |
| `workday-agents` | `context-foundry-workday-agents` | `skills/compliance-agent-architecture/SKILL.md` |
| `flowise` | `context-foundry-flowise` | `skills/flowise-agentflow/SKILL.md` |
| `workday` | `context-foundry-workday` | (none -- docs-only) |

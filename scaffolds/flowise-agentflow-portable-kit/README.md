# flowise-agentflow-portable-kit

Portable scaffold for building and auditing Flowise AgentFlow v2 in:

- Claude Code
- GitHub Copilot CLI

## What This Is

This directory is a reusable target-repo skeleton. Its contents are meant to be copied into the root of a normal project repository that wants Flowise generation, validation, and audit without running Context Foundry.

## Directory Answer

While authoring the scaffold, stay in the Context Foundry repo root:

```bash
cd /Users/name/homelab/context-foundry
```

When applying the scaffold to a real project, change to that target repo root first, then copy or install the scaffold there.

Example:

```bash
cd /path/to/target-repo
/Users/name/homelab/context-foundry/scaffolds/flowise-agentflow-portable-kit/install-into-target.sh .
```

## Scaffold Name

The scaffold bundle is called `flowise-agentflow-portable-kit`.

The directory name is also the recommended package name if you later publish it as a standalone template repo.

## What You Get

- shared `AGENTS.md` and `CLAUDE.md`
- Claude Code rules, skills, hooks, and auditor agent
- GitHub Copilot CLI instructions, agents, and hooks
- local Flowise corpus subset for retrieval
- validator and Floweyes wrapper scripts
- benchmark example set

## Important Reference Note

The bundled `example-flows/` corpus is copied from the upstream Flowise extension as reference material.

That does not mean every copied example already passes strict Floweyes. The scaffold is designed to surface those gaps with validation and audit artifacts instead of hiding them.

## What Still Needs Real Environment Setup

- `floweyes` on `PATH`, or `FLOWEYES_BIN`, or `FLOWEYES_DIR`
- a target repository where the scaffold is copied to the root
- an LLM session that invokes the provided skills or agents

## Quick Start In a Target Repo

1. Copy this scaffold into the target repo root.
2. Set one of:
   - `FLOWEYES_BIN=/absolute/path/to/floweyes`
   - `FLOWEYES_DIR=/absolute/path/to/floweyes-source`
3. Start Claude Code or Copilot CLI from the target repo root.
4. Ask it to use the Flowise build path:
   - Claude Code: `/build-flowise Build an AgentFlow v2 for ...`
   - Copilot CLI: `copilot --agent flowise-builder --prompt "Build an AgentFlow v2 for ..."`

## Notes

- This bundle is intentionally AgentFlow v2 focused.
- Chatflows and sequential v1 flows are not part of the audited path.

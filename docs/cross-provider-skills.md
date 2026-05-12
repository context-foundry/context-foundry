# Cross-Provider Skill Discovery

Context Foundry can discover skill / instruction files authored for other AI
tools and let you opt them into the planner-prompt context per project. This is
strictly read-only: CF never modifies your AGENTS.md, .cursorrules, or
.claude/skills/ files.

## Recognized formats and paths

| Source | Path | Format | Walks ancestors? |
|---|---|---|---|
| `AGENTS.md` | `<project>/AGENTS.md` and each ancestor up to `$HOME` | Plain markdown | Yes |
| `.cursorrules` | `<project>/.cursorrules` | Plain markdown | No (project root only) |
| `.claude/skills/<topic>/SKILL.md` | `<project>/.claude/skills/<topic>/SKILL.md` | Anthropic SKILL.md (frontmatter + body) | No (project root only) |
| `.github/copilot-instructions.md` | `<project>/.github/copilot-instructions.md` | Plain markdown | No (project root only) |

The `.claude/skills/` source uses CF's existing SKILL.md parser, so files
authored against the Anthropic Claude Code convention drop in unchanged.
FlowiseKit-style frontmatter fields (`context`, `allowed-tools`,
`argument-hint`) are accepted and ignored gracefully.

## How to opt skills in

When you launch CF on a project that has any of these files, an "External
Skills" section appears in the startup screen below the Plugins panel. Each
entry shows its provenance label (`AGENTS.md`, `.cursorrules`, `.claude/skills/`,
`.github/copilot-instructions.md`) and a checkbox. The default state is OFF --
discovered skills do not affect the planner prompt unless you check the box.

Opt-in state is persisted per project in `.foundry.json` under
`external_skills_enabled`, keyed by absolute file path.

## How they appear in the planner prompt

Each opted-in skill is appended to both planner and reviewer prompt context,
inside an `## External Skills` block. Each entry leads with the file path and
a `source: <agents-md|cursor|claude-project|copilot>` label so the agent can
see provenance.

## Precedence and shadowing

When two discovered skills share the same `derived_name`, CF picks one
according to this precedence (highest first):

1. Project `.claude/skills/<topic>/SKILL.md`
2. Project `AGENTS.md`
3. Project `.github/copilot-instructions.md`
4. Ancestor `AGENTS.md` (closest first)
5. `.cursorrules`

Shadowing only fires when two discovered skills share the same `derived_name`;
in practice the four sources produce distinct names (e.g. `agents-md-<parent>`,
`copilot-instructions`, `cursorrules`), so this list also doubles as the UI
display order.

The loser is shown in the UI as `shadowed by <winner>` so you can see
which file wins.

CF-native skills under `~/.foundry/skills/` and plugin-bundled
`plugins/<name>/skills/<topic>/SKILL.md` always win over discovered
external skills with the same name.

## GitHub Copilot custom instructions

Copilot's `.github/copilot-instructions.md` is a single plain-markdown file
with no frontmatter and no activation semantics. CF discovers it at the
project root only (no ancestor walk -- Copilot's convention is
project-local). The entire file body is imported as one skill block,
labelled `source: copilot` in the planner prompt; CF does NOT split the
file per heading.

CF does not read the path-scoped variant `.github/instructions/*.instructions.md`
(the one with `applyTo:` glob frontmatter). Those files carry activation
semantics that don't translate cleanly to CF's "apply globally for the run"
model and would require lossy interpretation.

## Explicit non-goals (Tier 1)

This is the slimmest "meet you where you're at" version. The following are
intentionally out of scope:

- LLM-rated skill quality / scoring
- Lifecycle curation (auto-archive, deprecation)
- Activation semantics (`.cursor/rules/*.mdc` `globs`, scope hints) -- CF
  applies opted-in rules globally for the run
- Writing back to provider files (CF is read-only here, always)
- Other formats: GEMINI.md, `.clinerules`, `.cursor/rules/*.mdc`,
  `.claude/agents/`, `.claude/rules/`, `.claude/hooks/`,
  `.github/instructions/*.instructions.md` (deferred)

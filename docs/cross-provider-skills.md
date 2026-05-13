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

## How they reach the planner / builder / reviewer

As of T2.4 (May 2026), cross-provider discovered skills are folded into
Context Foundry's auto-retrieval skill pool alongside `~/.foundry/skills/`.
There is no per-skill checkbox to opt them in -- any SKILL.md / AGENTS.md /
.cursorrules / .github/copilot-instructions.md found at startup is eligible
for retrieval. The same BM25 + semantic-rerank + telemetry ranker that
selects from the global pool now sees the union of all sources.

The startup screen shows a single one-line summary above the Plugins panel,
e.g. `Skill pool: 321 global, 14 from .claude/skills/, 3 from AGENTS.md = 338 total`.

Provenance is preserved on every `SkillFile` (the `provenance` field) and
surfaced in telemetry / citation logs as one of `global-foundry`,
`claude-project`, `agents-md`, `copilot`, or `cursor`. Injection treats
all provenances identically -- the source label is informational only.

Note: when a foreign skill's `derived_name` collides with a CF-native skill
under `~/.foundry/skills/`, the CF-native skill wins the dedup (see
Precedence below) and is the only one that reaches the ranker.

## Precedence (name-collision rule)

When two skills share a `dir_name` / `frontmatter.name`, the merged pool
keeps the highest-precedence entry. Order (highest first):

1. `~/.foundry/skills/<topic>/SKILL.md` (CF-native global)
2. Project `.claude/skills/<topic>/SKILL.md`
3. Project `AGENTS.md` (then ancestor `AGENTS.md` walking outward)
4. `.github/copilot-instructions.md`
5. `.cursorrules`

## Legacy `.foundry.json` field

Older projects may carry a `external_skills_enabled` map keyed by absolute
path. T2.4 honors this field on read for backward compatibility: those
skills get a "pinned always-on" bit set in addition to being in the
auto-pool, but new selections cannot be made through the UI. The field is
deprecated and will be removed in a future release. A one-line note is
logged to stderr at startup when the field is non-empty.

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

## Keyword overrides for foreign skills

Some external skill sources (notably Anthropic Superpowers SKILL.md files) ship
without a `metadata.cf-keywords` block. CF synthesizes a fallback from the
skill's name and description (see `synthesize_keywords` in `src/skills.rs`),
but the synthesized list is generic. For known foreign skill packs, a curated
keyword list improves BM25 retrieval quality.

CF reads a sidecar JSON file at `~/.foundry/skill-keywords-overrides.json` at
startup. The file is a map of `skill_id -> [keyword, keyword, ...]`. Example:

```json
{
  "test-driven-development": ["test", "tdd", "test-driven", "implementation", "bugfix"],
  "systematic-debugging": ["debug", "bug", "reproduce", "isolate", "root-cause"]
}
```

When `skill_to_pattern` builds a Pattern for a skill, it merges keyword sources
in this order, deduplicating while preserving first occurrence:

1. The curated overrides entry for the skill's `pattern_id` (if any).
2. Then EITHER (a) the synthesized fallback from `synthesize_keywords(pattern_id, description)` if frontmatter `cf-keywords` is empty, OR (b) the authored `cf-keywords` verbatim if non-empty. The synthesized fallback and authored cf-keywords are mutually exclusive -- a skill with explicit `cf-keywords` is NEVER augmented with synthesized tokens. This preserves the pre-T2.1 vocabulary for skills that opt in to explicit metadata.

In practice the override map only carries entries for foreign skill packs that
lack `cf-keywords` (the 14 Superpowers skills under `~/.foundry/skills/`). For
those skills the merged vector is `overrides ++ synthesized` (deduped); for any
skill with authored `cf-keywords` and no override entry, the merged vector is
identical to the authored list.

The file is loaded once and cached for the process lifetime. If the file is
missing or malformed, CF silently falls back to the source-2 branch -- no
error is surfaced and no curated overrides are applied.

The override map's `skill_id` keys match the on-disk directory name under
`~/.foundry/skills/<dir>/SKILL.md` (the same key CF uses as `pattern_id`).

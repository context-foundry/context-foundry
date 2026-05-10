# Patterns Migration Log

## 2026-05 Pre-Migration Prune (T1.12)

Prior to migrating learned patterns to the Anthropic Skills format
(T1.13), the global pattern store at `~/.foundry/patterns/common-issues.json`
was pruned to remove low-signal entries. This document records what was
removed and how to recover it.

### Why

Independent audit of the pattern store (recorded in `TASKS.md` under
"Skills/Plugins Migration (T1.12-T1.15)") found:

- 2271 of 2384 patterns (95%) had `frequency == 1` -- captured once,
  never recurred.
- Only 7 patterns had ever been cited in a passing build; zero had been
  cited in WIP.
- 923 patterns were tagged HIGH severity, more than LOW -- severity had
  inflated until it was meaningless.

Migrating thousands of low-signal entries to Skills would amplify the
noise. Pruning first lets the Skills store start clean.

### Predicate

An entry was pruned if and only if all three conditions held:

- `cited_in_pass == 0`
- `cited_in_wip  == 0`
- `frequency     == 1`

Equivalently: any entry with at least one citation OR `frequency >= 2`
was kept. This is the "ruthless" rule from T1.12 in `TASKS.md`.

Entries missing the `frequency` field default to 0 and are kept (the
predicate matches strict equality with 1).

### Command

```
foundry patterns prune-stale            # prompts before writing
foundry patterns prune-stale --yes      # non-interactive
foundry patterns prune-stale --dry-run  # report only, no writes
```

Source file: `~/.foundry/patterns/common-issues.json`
Archive file: `~/.foundry/patterns/pruned-pre-migration-2026-05.json`

### Recovery

The archive file is the full, unmodified JSON of every pruned entry,
written as a top-level JSON array. To restore one or more entries:

1. Open `~/.foundry/patterns/pruned-pre-migration-2026-05.json`.
2. Copy the desired entries.
3. Append them to the `patterns` array in
   `~/.foundry/patterns/common-issues.json` (or to the top-level array if
   that file is in array format).

The archive is **not** auto-cleaned. It will remain until manually
deleted, so a future change of mind is reversible.

### Idempotency

`foundry patterns prune-stale` refuses to run if
`~/.foundry/patterns/pruned-pre-migration-2026-05.json` already exists.
This is a one-time migration; remove the archive file manually if you
truly want to re-run. (`--dry-run` is allowed even when the archive
exists, since it touches no files.)

### Survivor file in the all-pruned edge case

If the predicate matches every entry, `common-issues.json` is rewritten
as an empty JSON array (or a wrapper object with `"patterns": []`),
not deleted. Its continued existence is meaningful as a sentinel for
T1.13 and downstream tooling.

### Successor work

Surviving entries are migrated to `~/.foundry/skills/` by T1.13. After
T1.13 lands, `common-issues.json` becomes a fallback source and is
scheduled for full removal in T1.15.

## 2026-05 Skills Migration (T1.13)

After pruning (T1.12), each surviving pattern in
`~/.foundry/patterns/common-issues.json` is converted to a SKILL.md file
under `~/.foundry/skills/<dir>/SKILL.md`. The matcher prefers Skills
when any SKILL.md is present and falls back to the legacy JSON store
otherwise.

### Command

```
foundry patterns migrate-to-skills            # prompts before writing
foundry patterns migrate-to-skills --yes      # non-interactive
foundry patterns migrate-to-skills --dry-run  # report only, no writes
```

### Output shape

Each emitted SKILL.md has standard `name` and `description` fields plus
a `metadata` map carrying CF-specific extensions: `cf-stage`
(`planner`/`reviewer`), `cf-citations-pass`, `cf-citations-wip`,
`cf-last-used`, `cf-frequency`, `cf-severity`, and `cf-keywords`. The
body has `## Issue` and `## Solution` sections.

When a pattern has both planner and reviewer advice, two files are
written: `<pattern_id>-planner/SKILL.md` and
`<pattern_id>-reviewer/SKILL.md`. Otherwise a single
`<pattern_id>/SKILL.md` is emitted with the appropriate `cf-stage`.

Patterns whose `solution` is null or whose planner+reviewer text are
both empty are skipped.

### Idempotency

The command refuses to overwrite any existing SKILL.md. Remove the
conflicting directories under `~/.foundry/skills/` if you really want
to re-run.

### Fallback

`patterns::load_patterns_from_global` reads `~/.foundry/skills/` first;
if no SKILL.md is present, it falls back to the JSON store. Removal of
the JSON fallback is scheduled for T1.15.

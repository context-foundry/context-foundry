# Task Composition Guide

Task composition is the upstream lever that drives the entire pipeline cost.
The complexity engine reads the shape of a task to set its budget; well-composed
tasks land cheaply, bundled tasks thrash through P+ revisions.

This guide explains how to compose tasks that the pipeline can run efficiently,
what to do when a task feels too big, and how to read the diagnostic signals
when a run goes sideways.

## The Core Rule

**One mental model change per task.**

If you cannot describe the change in a single sentence with one verb and one
object, the task is over-bundled. Split it.

## Why Composition Matters

The pipeline (Q -> R -> P -> P+ -> BUILD -> AUDIT) makes assumptions about
coherence. P+ in particular tries to reason about the entire plan as one
integrated change. When a task description bundles independent concerns, P+ has
to verify each concern's constraints separately, then verify the constraints
don't conflict, then re-derive the relationships -- and it does this from
scratch each iteration.

The cost is non-linear. Two unrelated concerns in one task is not 2x the cost
of one concern; it's often 4-5x because P+ revises the plan to address concern
A's gaps, which invalidates the cross-checks for concern B, which triggers
another iteration.

### Reference cases

| Task | Composition | Cost | Outcome |
|------|-------------|------|---------|
| **T1.16** | `(1) wire ranker (2) BM25 upgrade (3) telemetry boost` -- three layers explicitly numbered | ~$20 / 63 min | 4 PLAN attempts, 3 P+ rejection cycles before BUILD |
| **T1.18** | Two modals + key handler + render dispatch | ~$15 / 35 min | 3/3 P+ iterations, each catching a real bug |
| **T1.17** | Persist one config field across restart | ~$2 / 8 min | First-pass through pipeline, no P+ rejections |

T1.16 is the canonical bad-composition case. Split into three sub-tasks
(T1.16a/b/c), the same total scope would have shipped in ~$8 over ~25 minutes.

T1.18 is borderline: the concerns are related (both modals, shared state) but
the integration surface is broad. P+ earned its rigor tax here; it caught the
explorer-view branch bug, the Ctrl+C-trap bug, and the `enter_home_surface`
race. Borderline tasks pay either way: P+ thrashes if you split too aggressively,
or the bugs ship if you don't run P+ at all. Bias toward splitting.

T1.17 is the gold standard: one config field, one persistence path, one merge
point. The pipeline ran clean.

## Signs a Task Is Over-Bundled

Split if any of these apply:

- **Numbered sub-features**: the description contains `(1) ... (2) ... (3)` or
  `1. ... 2. ... 3.` listing distinct features.
- **"AND also" / "plus" / "three layers" / "and additionally"** anywhere in the
  lead sentence or the Why section.
- **Multiple distinct verbs in the opening clause**: "add X and refactor Y and
  rename Z" -- three verbs is three tasks.
- **File references span more than ~6 distinct paths**. Real blast radius is
  hard to plan and hard to verify.
- **Description exceeds ~500 words**. Long is not always wrong (T1.16's was 800
  words), but long + numbered features is almost always wrong.
- **The Constraints section needs subsections to organize itself.** If you find
  yourself writing "Constraints for layer 1: ... Constraints for layer 2: ...",
  those are two tasks.
- **You catch yourself writing "while we're at it"** -- the second concern
  doesn't belong.

## Signs a Task Is Well-Composed

Let it run if all of these are true:

- **One verb, one concern, one mental model**. The lead sentence describes a
  single action against a single object.
- **File refs concentrated in 1-3 modules**. Not 1-3 files -- 1-3 modules.
  A task that touches `src/skills.rs`, `src/skills_telemetry.rs`, and a test
  file is fine; a task that touches `src/skills.rs`, `src/app.rs`, `src/tui/`,
  `src/config.rs`, `src/patterns.rs` is not.
- **Constraints can be checked independently**. Each constraint is a local
  invariant, not a cross-cutting requirement.
- **Verification checks are local to the change**. The reviewer can validate
  the task without re-reading the rest of the codebase.
- **The Why section explains one motivation**, not a chained "because A, and
  also B, and additionally C."

## How to Split

Three patterns work well:

### Sequential foundation -> consumer

Split when one piece is a foundation the others depend on.

> T1.16 -> T1.16a (foundation: BM25 keyword scoring upgrade), T1.16b (consumer:
> wire skill ranker through `match_patterns_semantic`), T1.16c (consumer:
> telemetry popularity boost).

T1.16a ships first; the others run against the new BM25.

### Parallel surfaces

Split when concerns touch separate UI/state surfaces that don't share logic.

> T1.18 -> T1.18a (StopRun modal for Esc), T1.18b (CtrlC modal with 3-option
> menu).

These can ship in either order. The shared state plumbing
(`running_screen_modal: Option<RunningModalKind>`) goes with whichever lands
first.

### Layer separation

Split when the change has both a state-model layer and a UI layer.

> T1.17 (single field) -- not split, fine as-is.
>
> T1.21 (retire patterns panel) -- could be split into T1.21a (add SQLite
> read-side helpers in `skills_telemetry.rs`) + T1.21b (rebuild the panel/overlay
> against the new helpers). Split if the helpers themselves are non-trivial;
> bundle if they're a thin SELECT.

## Per-Task Override Flags

Planned via T1.23. The flags will go after the task ID in TASKS.md:

- **`[fast]`** -- skip P+ entirely. Use when:
  - The spec has explicit `Files:` + `Constraints:` + `Verification:` sections
    with line numbers
  - You trust BUILD + AUDIT to catch what P+ would catch
  - The task is small (Simple-classified) and you'd rather see it ship than
    review the plan

- **`[strict]`** -- force full 3-iteration P+ even on Simple tasks. Use when:
  - The change is risky (auth, migrations, infrastructure)
  - You explicitly want fresh-context plan review even though the spec is
    bounded

Until T1.23 ships, the only lever is composition: rewrite the task to match
what you want the pipeline to do.

## Quick Checklist Before Filing

Run this checklist before adding a task to TASKS.md:

```
[ ] Lead sentence: one verb, one object?
[ ] No numbered sub-features (1) (2) (3) in the description?
[ ] No "AND also" / "plus" / "three layers" in the Why section?
[ ] File refs concentrated in 1-3 modules?
[ ] Description under ~500 words (or clearly justified)?
[ ] Constraints are local invariants, not cross-cutting?
[ ] Verification checks are local to the change?
[ ] If you removed half the task, would the remainder still make sense as a
    standalone task? (If yes, you're over-bundled.)
```

If two or more of these fail, split the task.

## When NOT to Use the Pipeline at All

A task with **zero file:line references and zero verifiable behavioral claims
adds nothing for the pipeline to verify**. Foundry's mechanism is checking
plan claims against code and verifying audit findings against behavior; prose
tasks (documentation, README updates, conceptual brainstorming, architecture
decision records) have no codebase counterpart to check against. Running them
through the pipeline pays plan-review and audit costs for zero marginal benefit.

Don't pipeline these:

- "Write a guide explaining X" -- direct edit or Claude Code direct
- "Update the README to mention the new feature" -- direct edit
- "Brainstorm options for Y" -- conversational, not a build
- "Document the architecture decision we just made" -- direct write
- "Reorganize TASKS.md sections" -- direct edit

Pipeline these:

- "Add endpoint X with handler at `src/api/foo.rs:120`, validation per
  schema in `docs/spec.md`, returning 400 when input is empty"
- "Refactor `Foo::bar` to take `&str` instead of `String` -- update the 8
  call sites listed in `Files:`, preserve behavior verified by the existing
  tests in `tests/foo_test.rs`"
- Anything where you'd want a fresh-context auditor to confirm the diff
  matches the spec

The rule of thumb: if the task description has at least one ``file_path:line``
reference and at least one Verification check that the auditor could run
against the code, the pipeline adds value. If it doesn't, write it directly.

This rule applies to documentation tasks too. Even `docs/task-composition.md`
itself was written direct, not through the pipeline -- it's prose with no
behavioral claims, so the pipeline would have priced it at the same rate as
a real engineering task and produced no benefit.

## When to Bundle Anyway

Sometimes splitting hurts more than it helps:

- **Tightly coupled concerns where the split is artificial.** If the "two
  tasks" share 80% of their plan, you're going to write the same plan twice.
  Bundle.

- **One change that requires another to even compile.** If T1.16a's BUILD would
  produce an unused function until T1.16b lands, bundle them. The pipeline
  doesn't reward shipping dead code.

- **Atomic refactors.** Renaming a module everywhere is one change, not N
  changes per call site, even if it touches 30 files. The classifier should
  recognize this; the composition is wide but the mental model is one rename.

In these cases, write the bundle but signal it explicitly: lead with "This is
intentionally bundled because <reason>; splitting would <cost>." That tells
P+ (and future readers) the rigor cost is conscious, not accidental.

## See Also

- [`docs/progress-indicators.md`](progress-indicators.md) -- QRPBA indicators
  on completed tasks, including what `!` after a stage letter means.
- [`docs/eval-harness.md`](eval-harness.md) -- the per-stage badges that show
  whether each stage's plumbing was healthy.
- [`docs/per-stage-routing.md`](per-stage-routing.md) -- routing different
  stages to different models. Splitting tasks composes well with routing
  cheaper models to lower-rigor stages.

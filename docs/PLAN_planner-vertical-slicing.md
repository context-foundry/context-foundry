# Plan: Planner Vertical Slicing + Eval Heuristic Tightening
Date: 2026-05-09
Version: v1
Status: planning

## Resume context (read this first if picking up cold)

This plan picks up from work done 2026-05-08 in
`/Users/Shared/homelab/context-eval/docs/PLAN_context-eval-followups.md`.
Read that file's Decision Log for the full story; condensed version here:

**What was diagnosed (steps 1-3 of the prior plan):**
- Foundry's stage prompts: total ~123 instructions across 5 stages.
  Reviewer is the only one above 40 (~55). NOT broken; minor cleanup
  candidate at most.
- **3 of 3 sampled `current-plan.md` files were classified HORIZONTAL.**
  Foundry's planner produces layer-by-layer plans by default --
  exactly the antipattern the engineering talk warned against
  ("models default to horizontal plans which lead to 1200+ lines of
  untestable code"). The clearest failure mode in our sample was
  context-foundry M1.1 at ~1000 lines, 12 file ops, single end-block
  verification, no intermediate testable steps.
- The eval harness's `plan_has_verification` heuristic rewards plans
  for "has a verification section" without checking *where* it
  appears. The check itself implicitly endorses the horizontal pattern.
- The user's CLAUDE.md was patched and committed (commit `f939244`)
  resolving 4 HIGH-severity rule contradictions plus an em-dash sweep.
  That work is DONE.

**What's queued (this plan):**
Three Foundry-side cleanups, prioritized by leverage. Plan is to do
the first two together (~2-3 hours) since they're complementary; the
third is optional and lower-priority.

**Files to know about before starting:**
- `src/prompts.rs` -- `planner_prompt` (lines 321-449),
  `reviewer_prompt` (lines 769-986).
- `src/eval/checks/heuristic.rs` -- where `PlanHasVerification` lives.
- Sample horizontal plans for inspiration:
  - `/Users/Shared/homelab/context-foundry/.buildloop/current-plan.md`
    (M1.1, 996 lines, ideal failure-mode example)
  - `/Users/Shared/homelab/i9-reverification/.buildloop/current-plan.md`
    (Python/compliance, smaller)

## Context

The thesis behind context-eval (saved to homelab memory as
"context-eval guiding thesis"): coding agents won because code has
cheap automatic verification -- tests, types, compilers, linters.
The work for other domains is to manufacture equivalent signals,
preferably tiered (fast cheap checks first, slow expensive ones
later) rather than single end-stage human review.

Per-phase verification is exactly that pattern applied to Foundry's
orchestration layer. Horizontal plans collapse N tiered verification
signals into one end-block signal: a bug introduced at step 7 of a
12-step plan only surfaces at the final verification, with no
intermediate signal about which step broke. Vertical plans restore
the verifier-generator asymmetry -- many cheap signals along the way
instead of one expensive end-block check.

This is fixable at the prompt level but requires care: small tasks
genuinely shouldn't be sliced vertically (artificial), and the change
should not break Foundry's ability to handle simple tasks. For small
tasks (under 5 file ops), single-block verification is fine -- the
antipattern bites at scale. The vertical-slicing rule should be
conditional on file count, not universal.

The fix is two-part: change the prompt so the planner produces
vertical plans on medium/complex tasks, AND change the eval heuristic
so the check rewards the new pattern instead of the old one. Doing
only the prompt change without the heuristic change leaves the eval
falsely happy with end-block verification. Doing only the heuristic
change penalizes Foundry's current output until the prompt is updated.
Pair them.

## Implementation Steps

### Step 1: Tighten `plan_has_verification` heuristic (smallest first)

- [ ] Read the current `PlanHasVerification` implementation in
      `src/eval/checks/heuristic.rs` (around the
      `STAGES_PLAN`-using check, after `PlanCoversResearchFiles`).
- [ ] Add a second pass to count `## Verification` headings (or
      similarly-named sections) in the plan. Decision tree:
      - 0 verification sections -> Fail (current behavior).
      - 1 verification section + plan has fewer than 5 file ops ->
        Pass with evidence "single verification block, plan size
        warrants no slicing".
      - 1 verification section + plan has 5+ file ops -> Pass with
        a soft-fail (Status::Pass but evidence flagging that
        per-phase verification would be better).
      - 2+ verification sections -> Pass cleanly.
- [ ] Decision: should "soft-fail" be Pass or new "Warn" status? v1
      check API has Pass/Fail/Skip. Adding Warn is bigger surgery.
      v1 of THIS plan: keep Pass, but add evidence string flagging
      the issue. v2: introduce Warn if it proves useful.
- [ ] Add a new dedicated check `plan_has_per_phase_verification`
      at Standard severity that fails when plan has 5+ file ops AND
      only 1 verification section. This is the cleaner approach --
      separates the "has any verification" check from the "has
      per-phase verification" check.
- [ ] Add unit tests covering:
      - 0 ops, 0 verifications -> existing check fails as before.
      - 3 ops, 1 verification -> existing passes, per-phase passes.
      - 12 ops, 1 verification -> existing passes, per-phase fails.
      - 12 ops, 4 verifications -> both pass.
- [ ] Update plumbing/heuristic count in any docs that say "8
      heuristic checks". After this step there will be 9.

Effort: 30-45 min. Risk: low.

### Step 2: Tighten `planner_prompt` to require vertical slicing on medium/complex tasks

This is the bigger change. The prompt currently produces a single
plan with all file operations in one ordered list. We want:

- Small tasks (1-4 file ops, simple): keep current behavior.
- Medium tasks (5-9 file ops): plan should be split into 2-3 phases,
  each with its own verification step.
- Complex tasks (10+ file ops): plan should be split into 3-5 phases.

- [ ] Read `planner_prompt` (lines 321-449). Current structure:
      INSTRUCTIONS block -> PLAN FORMAT spec -> RULES -> GOOD/BAD
      examples -> IMPORTANT.
- [ ] Modify the PLAN FORMAT spec to support multiple phases:
      ```markdown
      ## Phase 1: <name -- the slice>
      ### File Operations (Phase 1)
      ...
      ### Verification (Phase 1)
      <commands that prove this slice works>

      ## Phase 2: <name>
      ### File Operations (Phase 2)
      ...
      ### Verification (Phase 2)
      ...
      ```
- [ ] Add a complexity-aware rule to RULES:
      "If the task touches 5 or more files, split the plan into 2-3
      phases, each producing an independently verifiable increment.
      Each phase must end with a Verification subsection containing
      at least one runnable command. If the task touches fewer than
      5 files, a single Verification block at the end is acceptable."
- [ ] Add a GOOD example showing a 3-phase plan for a hypothetical
      "add new endpoint with frontend" task. Add a BAD example
      showing the same task as a single horizontal block.
- [ ] Update the planner gate (in `src/app/build.rs`, the
      `gate_builder` mentioned in CLAUDE.md) to ALSO accept the
      multi-phase format. Current gate checks for
      `## File Operations` and `## Verification` sections. Either:
      (a) widen the regex to match `## File Operations (Phase N)`
          variants too, OR
      (b) keep the existing top-level `## File Operations` /
          `## Verification` requirement and have phases be sub-sections
          (`### File Operations (Phase 1)`).
      Option (b) is less invasive; pick that.
- [ ] Run end-to-end on a sample task to verify the planner produces
      a multi-phase plan AND the gate doesn't reject it.

Effort: 1-2 hours. Risk: medium -- changes the shape of every plan
Foundry produces. Test on a non-trivial task before declaring done.

### Step 3: (Optional) Reviewer prompt repetition cleanup

Do this only if steps 1-2 went smoothly and there's energy left.

- [ ] In `src/prompts.rs:769-986`, locate the 5 places that say
      "fix HIGH/MEDIUM, skip LOW" (YOUR JOB / severity examples /
      WHEN YOU FIND ISSUES / VERDICT RULES / closing RULES) and
      consolidate to 1-2 mentions, with cross-references rather
      than restatements.
- [ ] Same for "every finding must cite source_evidence" (3
      mentions in PROVENANCE / closing RULES / JSON example).
- [ ] Aim to drop reviewer_prompt's instruction count from ~55 to
      ~40 without losing semantic content.
- [ ] Verify on a sample task that reviewer behavior is unchanged
      (still emits structured JSON findings, still respects severity
      classifications).

Effort: 1 hour. Risk: low/medium -- could subtly change reviewer
behavior. Validate before committing.

## Architecture Decisions

- **Pair the prompt change with the heuristic change.** Doing one
  without the other creates incoherent feedback signals.
- **Two checks, not one with mixed semantics.** Keep
  `plan_has_verification` as the simple "has any" check. Add
  `plan_has_per_phase_verification` as the new sophistication.
  Cleaner than overloading the existing check's evidence string.
- **Threshold at 5 file operations.** The horizontal-vs-vertical
  distinction matters at scale. The talk's "1200-line untestable"
  example was at clearly-medium scope. 5 files is the empirical
  threshold from looking at our 3 sampled plans (the small one
  was 4 files; the others were 5+).
- **Don't introduce `Warn` status to the check API.** v1 has Pass /
  Fail / Skip. Adding a fourth status is real surgery (manifest
  schema, scorer thresholds, badge rendering). Use a separate check
  with clear evidence instead.
- **Plan gate stays as-is**, just accept either format. Migration
  path: existing tasks (single-section plans) still pass the gate.
  New tasks (multi-phase plans) also pass.

## Risks & Open Questions

- **Will the planner reliably follow the new structure?** Multi-phase
  plans require more sophisticated reasoning. There's a real risk
  the planner produces malformed phase headers or skips Phase 2's
  verification. Mitigation: a strong few-shot example in the prompt
  + the new heuristic check catching omissions.

- **Backward compatibility with old plans.** Existing
  `current-plan.md` files in `.buildloop/` won't match the new format.
  The eval harness reads them via heuristic checks, not regex parses,
  so they should still grade -- just with the new check failing on
  the old files. That's acceptable: re-running them would generate
  new-format plans anyway.

- **Complexity classifier interaction.** Foundry's `complexity.rs`
  classifies tasks Simple/Medium/Complex. The new prompt rule should
  align: Simple = 1 phase OK, Medium/Complex = 2+ phases required.
  Check whether complexity is passed into `planner_prompt`; if not,
  use file-count as the proxy.

- **Test plan.** Need a non-trivial real task to validate. Options:
  (a) cherry-pick a deferred TASKS.md item, (b) construct a synthetic
  test task ("add a new MCP tool that searches patterns by tag"),
  (c) re-run an existing M1.1-class task in a scratch directory.
  Option (a) gives the most realistic signal but takes longer.

- **Should the comprehension check (context-eval.py) be re-run after
  this work?** The user's CLAUDE.md doesn't change as part of this
  plan, but Foundry's prompts do. Could the new prompts have new
  contradictions? Worth a 5-minute eyeball check after step 2.

## Verification

- [ ] `cargo test eval::checks::heuristic::` passes including the
      new tests for `plan_has_per_phase_verification`.
- [ ] `cargo test` overall: 856+ tests still pass.
- [ ] Run a 5+-file task in a scratch project; inspect the
      generated `current-plan.md`; confirm it has 2+ phases each
      with verification.
- [ ] Re-classify the new plan (vertical/horizontal) using the
      same Opus-subagent method used in the original step 2.
      Should classify VERTICAL.
- [ ] Eval-report on that task should show
      `plan_has_per_phase_verification: pass` and overall plan
      stage badge `P✓`.
- [ ] Re-run a small-task scratch project; confirm the planner
      still produces single-section plans (the new rule doesn't
      mandate phases below the threshold).

## Decision Log

- **2026-05-09 [planning]**: Plan created from queued items in
  `context-eval/docs/PLAN_context-eval-followups.md`. Sequencing:
  heuristic first (small, clean), then prompt (bigger, paired with
  the new check). Reviewer-prompt cleanup is optional follow-up.

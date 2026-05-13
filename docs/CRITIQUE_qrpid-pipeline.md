# Critique: QRPID Pipeline Specification

**Reviewer:** Architecture audit (fresh-context)
**Date:** 2026-03-28
**Spec under review:** `docs/SPEC_qrpid-pipeline.md`

> **Note (2026-05-12):** This critique pre-dates the v3.3.0 rename. References to
> `extensions/`, `wrap_with_extensions()`, and "extension context" refer to what is
> now `plugins/`, `wrap_with_plugins()`, and "plugin context."
**Cross-reference:** `docs/PLAN_cross-model-orchestrator.md`

---

## 1. Executive Summary

QRPID is a well-motivated evolution of SPID. The core insight -- separating question generation from research to prevent implementation anchoring -- is sound and addresses a real failure mode where Scout reads code through the lens of what it already plans to build. The five-phase structure with orchestrator-driven transitions is a genuine architectural upgrade over the current agent-driven model. However, the spec has three load-bearing gaps: (1) it specifies no mechanism for the orchestrator to actually enforce context isolation beyond "input control," which is aspirational given that Claude CLI agents have unrestricted tool access; (2) it introduces context budgets as soft targets but provides no feedback loop when they are exceeded; and (3) it does not address how QRPID composes with the existing cross-model orchestrator, creating an ambiguous relationship between two orchestration layers.

---

## 2. Structural Analysis

### 2.1 The Q/R Split Is the Right Decomposition

SPID's Scout phase conflates two distinct cognitive tasks: deciding what to investigate and doing the investigation. This conflation means Scout's research is anchored by its initial assumptions about the task. QRPID's Q/R split forces the Question agent to commit to research targets before any code is read, and forces the Research agent to answer questions it did not write. This is a genuine debiasing mechanism.

The cost is one additional agent invocation per full pipeline run. Given that the current pipeline already runs 4 agents (Scout, Plan, Build, Doubt) at ~$0.10-0.50 each, adding a fifth is marginal -- especially since Q should be cheap (no code reading, <15% context utilization).

### 2.2 The Isolation Matrix Is the Spec's Load-Bearing Wall

The entire value proposition of QRPID depends on the Context Isolation Matrix (line 396-403). If isolation is not enforced, QRPID degrades to "SPID with more steps." This is the section that needs the most hardening.

**Problem:** The spec says agents "cannot read artifacts from phases they shouldn't see (enforced by input control)" (line 389). But the current agent infrastructure (`src/agent.rs`) spawns Claude CLI with full filesystem access. The agent receives a prompt that says "read this file," but nothing prevents it from reading `.buildloop/questions.md` during the Plan phase or `.buildloop/current-plan.md` during Doubt. The enforcement is prompt-based, not mechanism-based.

**Implication:** This is acceptable for a v1 if acknowledged explicitly. Prompt-based isolation works ~95% of the time. But the spec presents it as "enforced by input control" which overstates the guarantee. The spec should distinguish between "mechanically enforced" (the orchestrator literally does not pass the file path) and "prompt-enforced" (the agent is told not to look).

**Concrete fix:** The orchestrator should only include artifacts in the prompt that the phase is allowed to see. Additionally, for the two critical isolation boundaries (R cannot see the task; D cannot see the plan), the orchestrator should move the restricted artifacts out of `.buildloop/` into a temporary location before spawning the agent, and restore them after. This is the only mechanism-level enforcement available without Docker filesystem restrictions.

### 2.3 The "Plan Only Sees Plan" Rule for Implement Is Overly Strict

Line 401 shows Implement receives only the Plan, with no access to Task, SPEC, Research, or Patterns. The argument is that this "forces the plan to be complete and self-contained." In practice, this creates a failure mode where the builder encounters an ambiguity the plan did not anticipate and has no context to resolve it.

The current SPID builder already suffers from this: `builder_prompt()` receives only the plan, and builders regularly make incorrect assumptions when the plan is underspecified. QRPID's Plan phase is better-informed (it receives structured research), so plans should be higher quality. But the spec should still allow the builder to read SPEC.md as a fallback reference -- it is static project context, not a dynamic artifact that could cause bias.

### 2.4 Transition Validation Is Necessary but Not Sufficient

The transition rules (e.g., "at least 5 questions covering 3 categories" at line 91) are good structural checks. But they cannot catch substantive emptiness: an agent can produce 10 questions that are all variants of "what files exist?" and pass the gate.

The spec acknowledges this for retries ("an agent might produce a structurally valid but substantively empty artifact" -- Open Question 4) but does not propose a mitigation. The orchestrator should add a simple heuristic: if any two questions share >80% token overlap, reject the artifact. Similarly for research answers that are all "could not determine" with an `[UNANSWERED]` tag.

### 2.5 The 30-Question Cap Is Probably Fine; the 30-File Cap Is Not

30 questions is a soft cap with diminishing returns -- past 15-20, additional questions tend to be speculative. The cap is reasonable.

30 files for Research is more problematic. The current codebase (`context-foundry`) has 35 Rust source files. A non-trivial task touching the pipeline (e.g., "add QRPID support") would need to read most of them. For larger projects (the user's homelab has 50+ projects), the Research agent would hit the cap on a single service's codebase exploration.

**Concrete fix:** Replace the hard file cap with a tiered budget: 30 files for questions covering 1-2 categories, 50 files for 3-4 categories, 75 files for 5-6 categories. The number of question categories is a reasonable proxy for exploration breadth.

---

## 3. Failure Mode Analysis

### FM-1: Research Agent Reads Task Description from Filesystem

**Trigger:** R agent uses Grep to search `.buildloop/` or reads `TASKS.md` (which contains the task description). The questions in `questions.md` reference the task by ID, making it trivial for R to find the original text.

**Impact:** Defeats the purpose of Q/R isolation. Research becomes anchored to the task framing.

**Mitigation:** (a) The questions artifact schema (line 66) includes `Task: <task-id and title>`. Remove the title from R's copy -- pass only the task ID so R cannot reconstruct the full task. (b) Add to R's prompt: "Do NOT read TASKS.md, SPEC.md, or any .buildloop/ files other than questions.md." (c) For mechanism-level enforcement, write a sanitized copy of `questions.md` that strips the task header before passing to R.

### FM-2: Question Agent Generates Implementation-Biased Questions

**Trigger:** Q receives matched patterns that contain solution details. Patterns include `solution.planner` and `solution.reviewer` fields with specific implementation guidance. Q unconsciously steers questions toward validating the pattern's solution rather than exploring alternatives.

**Impact:** Research becomes a confirmation exercise rather than genuine exploration. The pipeline produces plans that match historical patterns even when the current context differs.

**Mitigation:** Inject only the `issue` and `keywords` fields of matched patterns into Q, not the `solution` fields. The solution fields should be injected into P (Plan), where they are appropriate.

### FM-3: Plan Phase Cannot Resolve Unanswered Questions

**Trigger:** Research marks 3+ questions as `[UNANSWERED]` and the Plan phase's 5-file cap is insufficient to resolve them.

**Impact:** Plan is built on incomplete information. Builder deviates from plan. Doubt catches the deviations but cannot assess whether they were correct because Doubt has no context on what was originally intended.

**Mitigation:** Open Question 6 asks about this. The spec proposes two options: let Plan read 5 files, or bounce back to R. The bounce-back is better because it preserves phase isolation -- the Research agent is purpose-built for codebase exploration; the Plan agent is not. However, a full R re-run is wasteful. Instead: the orchestrator should spawn a targeted "R2" pass that receives only the unanswered questions (not the full question set) and has a reduced file budget (10 files). This avoids re-reading files already covered in the first R pass.

### FM-4: Doubt Cannot Distinguish Intentional Deviations from Bugs

**Trigger:** Builder deviates from the plan (documented in "Deviations from Plan" section of build-claims.md). Doubt does not see the plan, so it cannot assess whether the deviation was reasonable.

**Impact:** Doubt may flag a deliberate design deviation as a bug, or may miss a deviation that silently dropped a planned feature.

**Mitigation:** This is the strongest argument for Doubt seeing a constrained view of the plan. Not the full plan (which would cause confirmation bias), but the "Constraints" and "Open Risks" sections. These are verifiable invariants, not implementation details. The orchestrator should extract these sections and append them to the claims file as "Plan Constraints (for verification)."

### FM-5: Batched Doubt Loses Specificity

**Trigger:** Three tasks run as `[QRP I-]` with deferred Doubt. The combined Doubt agent receives three `build-claims.md` files worth of claims spanning unrelated code changes.

**Impact:** Attention dilution. The Doubt agent is less thorough on each individual task than a dedicated pass would be. This is already a known issue with SPID's batched doubt.

**Mitigation:** The spec should specify that batched Doubt receives claims files sequentially (not concatenated) and produces separate verdict sections per task. The orchestrator should fail the batch if any single task has a HIGH finding, not just if the overall report says FAIL.

### FM-6: Pattern Extraction Runs Only on PASS

**Trigger:** Pipeline completes with verdict FAIL. The Doubt agent found real issues. These are exactly the kind of issues that should be captured as patterns for future tasks.

**Impact:** The most valuable learning signal (real bugs caught by Doubt) is never saved.

**Mitigation:** Pattern extraction should run on both PASS and FAIL outcomes. For FAIL, extract the Doubt findings as patterns with severity matching the finding severity. For PASS, extract deviations and surprises as currently specified.

### FM-7: Agent Timeout Kills Multi-Step Research

**Trigger:** Research agent hits the 600-second default timeout (`config.agent_timeout_secs`) while methodically answering 25+ questions across a large codebase.

**Impact:** Partial research report. The orchestrator's transition validator may reject it (not all questions answered). Pipeline fails at R.

**Mitigation:** The spec should recommend a higher timeout for R (e.g., 900s) or, better, the orchestrator should dynamically set the timeout based on question count: `base_timeout + (questions * 20s)`.

---

## 4. Context Isolation Critique

### 4.1 R Not Seeing the Task: Correct but Leaky

The isolation is conceptually right. In practice, the questions themselves encode the task. A question like "How does the pattern matching algorithm in `src/patterns.rs` handle keyword collisions?" tells R exactly what feature area is being worked on. This is unavoidable and acceptable -- the point is not to hide the domain but to prevent R from forming implementation opinions. The questions channel R's attention without anchoring its conclusions.

However, the artifact schema includes `Task: <task-id and title>` (line 68). This leaks the exact task framing into R's input. This should be removed or reduced to just the task ID.

### 4.2 D Not Seeing the Plan: Too Strict

The spec's rationale is preventing confirmation bias. This is valid for the implementation details in the plan. But the plan's "Constraints" section (line 217-219) contains invariants that Doubt should verify. Without them, Doubt can only check "does the code work?" not "does the code respect the project's constraints?"

The current SPID reviewer already has this problem. The reviewer in `src/prompts.rs` checks claims against code but has no mechanism to verify that a claimed "MUST NOT" constraint was actually respected.

**Recommendation:** Give D the Plan's "Constraints" and "Open Risks" sections. Withhold everything else.

### 4.3 I Not Seeing Research: Correct

The builder should work from the plan, not from raw research. If the plan is good, the builder does not need research. If the plan is bad, the builder reading research would mask the plan's deficiency rather than exposing it (through deviations that Doubt can catch).

### 4.4 Q Not Seeing Code: Correct and Important

This is the most important isolation boundary. If Q reads code, it becomes Scout again. The whole value of the Q/R split depends on Q operating at the conceptual level.

### 4.5 Missing from the Matrix: Extension Context

The matrix does not mention extension context (CLAUDE.md from `extensions/`). Currently, `wrap_with_extensions()` in `src/prompts.rs:44` prepends extension context to every agent prompt. Under QRPID, which phases should receive extension context?

- Q: Yes (domain knowledge helps generate better questions)
- R: Yes (domain rules affect how code should be read)
- P: Yes (design decisions must respect domain constraints)
- I: Yes (implementation must follow domain conventions)
- D: Debatable. Extension context could bias Doubt toward the project's stated conventions rather than objective correctness. But without it, Doubt might flag convention-compliant code as issues.

The spec should add an Extension Context row to the isolation matrix.

---

## 5. Compatibility with Cross-Model Orchestrator

### 5.1 Two Orchestration Layers

The cross-model orchestrator (`docs/PLAN_cross-model-orchestrator.md`) is a proposer/reviewer loop for design-time decisions. QRPID is a build-time pipeline. The plan explicitly says "This is NOT a replacement for the build loop" (line 22). So far, so good.

But there is a composition question the spec does not address: **where does the cross-model orchestrator fit in the QRPID pipeline?**

The most natural integration point is the Plan phase. P produces a design + plan. The cross-model orchestrator could review the plan before it reaches I. This would mean:

```
Q -> R -> P -> [Orchestrator Loop: proposer=P output, reviewer=cross-model] -> I -> D
```

This is powerful but raises questions:
- Does the orchestrator loop count as part of P, or is it a new phase between P and I?
- If the reviewer proposes changes to the plan, does P re-run (new agent) or does the proposer iterate in-place?
- How do the two acceptance policies (QRPID's transition validation and the orchestrator's `accept_policy`) interact?

**Recommendation:** Define the orchestrator as an optional "P+" subphase that runs after P's transition validation passes. The orchestrator's proposer receives P's output as its initial artifact. The orchestrator's reviewer uses a different model (per the cross-model config). The orchestrator's output replaces `current-plan.md`. This keeps it clean: QRPID controls the macro flow, the orchestrator controls the micro-loop within a single phase.

### 5.2 Envelope Compatibility

The cross-model orchestrator uses JSON envelopes (`ProposerOutput`, `ReviewerOutput`). QRPID uses markdown artifacts. These are not in conflict -- the orchestrator's `artifact_text` field can contain the markdown plan. But the orchestrator's `claims` array (line 39-42 of the plan) overlaps with QRPID's "Claims" section in `build-claims.md`.

This creates a naming collision: "claims" means different things in the two systems. In the orchestrator, claims are statements about the plan's correctness. In QRPID, claims are statements about the implementation's correctness.

**Recommendation:** Rename the orchestrator's `claims` to `design_assertions` to distinguish from QRPID's implementation claims. This is a trivial change to `src/orchestrator.rs:23` (`ProposerOutput.claims` field).

### 5.3 Agent Role Mapping

The current `AgentRole` enum in `src/agent.rs:19-26` has: Scout, Planner, Builder, Reviewer, Fixer, Discovery. QRPID needs: Questioner, Researcher, Planner, Builder, Reviewer. The cross-model orchestrator adds: Proposer, OrchestratorReviewer (distinct from the Doubt reviewer).

This is getting crowded. The spec should define a clear mapping:

| QRPID Phase | AgentRole | Provider Config Field |
|-------------|-----------|----------------------|
| Q | Questioner | `questioner_provider` / `questioner_model` |
| R | Researcher | `researcher_provider` / `researcher_model` |
| P | Planner | `planner_provider` / `planner_model` (existing) |
| I | Builder | `builder_provider` / `builder_model` (existing) |
| D | Reviewer | `reviewer_provider` / `reviewer_model` (existing) |

Q and R are new and should default to the cheapest model (Sonnet-class) since they are structured, low-creativity tasks.

---

## 6. Open Questions Assessment

### Spec's Open Questions

**OQ1: Is the 30-file cap on Research too low?**

Yes, for non-trivial tasks in codebases with 20+ files. See section 2.5. Use a tiered budget keyed on question category count. If the project has a working `scout-report.md` from a prior SPID run, allow R to read it as a "free" file (does not count against the cap) since it provides architectural orientation without deep code reading.

**OQ2: Should Plan see the questions artifact too?**

No. The questions are an intermediate artifact whose value is fully captured by the research report. If R answered the question, P has the answer. If R marked it `[UNANSWERED]`, P knows what is missing. Seeing the original questions adds noise without information.

**OQ3: Should Doubt see the plan?**

Partially. See section 4.2. Doubt should see the Plan's "Constraints" and "Open Risks" sections but not the implementation steps. This gives Doubt verifiable invariants without anchoring it to implementation expectations.

**OQ4: Is one retry on validation failure enough?**

No. One retry is enough for mechanical formatting failures (missing headers, wrong section names). But substantive failures (too few questions, empty answers) need a different strategy: the retry prompt should include the specific validation error, not just "try again." The current codebase already does this for the builder gate (line 65-100 of `src/app/build.rs` -- `gate_builder` returns a specific failure message). Apply the same pattern: the orchestrator includes the validation failure message in the retry prompt.

Two retries with error feedback is the right number. After two failures, the task is likely underspecified or the model is inadequate -- retrying further wastes tokens.

**OQ5: Should pattern injection be transparent?**

Yes. The agent should know which patterns were matched and why. This is not just about transparency -- it is about calibration. If the agent sees "Pattern #47: UTC timestamps without Z suffix cause timezone bugs (severity: HIGH, matched on keywords: timestamp, date)" it can evaluate whether the pattern applies. If patterns are silently injected as context, the agent may overweight them because they appear as authoritative instructions rather than conditional advice.

The current `format_patterns_for_prompt()` in `src/patterns.rs` already labels patterns clearly. Ensure QRPID preserves this.

**OQ6: How should the orchestrator handle [UNANSWERED] questions that block planning?**

Spawn a targeted R2 pass. See FM-3 for details. The R2 agent receives only the unanswered questions and a 10-file budget. If R2 also fails to answer, the question is marked `[UNRESOLVABLE]` and Plan must work around it (documenting the gap in "Open Risks").

### Unanswered Clarifying Questions (4-8)

These were not answered by the user. Taking positions:

**CQ4: Should QRPID replace SPID immediately, or run as an opt-in alternative?**

Run as opt-in first. The current SPID works. QRPID should be selectable via `.foundry.json` (`"pipeline": "qrpid"` vs `"pipeline": "spid"`). This allows A/B comparison on real tasks before committing. The `AgentRole` enum and prompt functions for SPID should remain intact until QRPID is proven over 20+ tasks.

**CQ5: How should QRPID interact with the complexity classifier?**

Simple tasks should skip Q+R entirely (equivalent to `[QRPID:fast]`). The complexity classifier (`src/complexity.rs`) already routes simple tasks to cheaper models and skips Scout. QRPID should respect this: Simple tasks go `-PID` or even `--ID` (direct build from task description). Medium tasks run full `QRPID`. Complex tasks run `QRPID` with the cross-model orchestrator loop on Plan.

**CQ6: Should artifacts accumulate across tasks or reset each run?**

Reset. The spec already says this (line 430: "overwritten each pipeline run"). This is correct. Accumulation creates context pollution between tasks. Git history preserves the record.

However, there is an exception: the research report from a completed task should be available to the next task's Q phase if both tasks operate in the same code area. The orchestrator should check whether `research-report.md` exists and was generated within the last N minutes; if so, Q can reference it as "prior research" (read-only, not counted as a new artifact).

**CQ7: What is the failure mode for the orchestrator state machine itself?**

The spec says "the orchestrator is a state machine, not a suggestion" (line 391) but does not define its own failure modes. What happens when:
- The orchestrator process crashes mid-pipeline?
- An agent's output is valid JSON/markdown but semantically nonsensical?
- The filesystem is modified externally between phases?

The existing checkpoint system (`src/app/build.rs:34-63`) handles crash recovery for SPID. QRPID should extend this: the checkpoint should record the completed phase (Q, R, P, I, D) and the orchestrator should resume from the last completed phase. This is a straightforward extension of the existing `Checkpoint` struct -- add a `pipeline_phase: String` field.

**CQ8: What are the token cost implications?**

Back-of-envelope for a full QRPID run (Opus for P/I/D, Sonnet for Q/R):
- Q: ~2K input, ~1K output = ~$0.02
- R: ~30K input (questions + 30 file reads), ~3K output = ~$0.15
- P: ~10K input (task + research + patterns), ~3K output = ~$0.20
- I: ~15K input (plan + files), ~10K output = ~$0.50
- D: ~10K input (claims + code), ~5K output = ~$0.30

Total: ~$1.17 per task at current pricing. SPID is ~$0.90 (4 phases, no Q). The ~30% cost increase buys better research isolation. For the user's stated optimization target (better task success rate), this is worthwhile. The cost is dominated by I and D, which are unchanged from SPID.

---

## 7. Recommendations

### MUST (blocking -- spec is incomplete without these)

**M1: Define enforcement mechanism for context isolation.** The spec claims "enforced by input control" but the current agent infrastructure provides no filesystem restrictions. Either (a) acknowledge this is prompt-enforced and accept the ~5% leak rate, or (b) specify that the orchestrator moves restricted artifacts to a temp directory before spawning isolated agents. The spec must be honest about the guarantee level.

**M2: Add extension context to the isolation matrix.** The matrix is missing a row for extension CLAUDE.md content, which is currently injected into every agent. Define which phases receive it.

**M3: Strip task title from R's input.** The `questions.md` artifact schema includes `Task: <task-id and title>` which leaks the task framing into R. Change to `Task: <task-id>` only in the copy passed to R.

**M4: Define checkpoint schema for crash recovery.** The existing SPID checkpoint (`src/app/build.rs:34-39`) must be extended with a `pipeline_phase` field. Without this, a crash during R would restart from scratch rather than resuming at R.

**M5: Specify the AgentRole mapping and config fields.** QRPID introduces two new roles (Questioner, Researcher). The spec must define the corresponding config fields and their defaults to be implementable.

### SHOULD (important -- significantly improves the design)

**S1: Inject only pattern `issue`/`keywords` into Q; defer `solution` to P.** Prevents Q from generating implementation-biased questions. See FM-2.

**S2: Allow Doubt to see Plan's "Constraints" and "Open Risks" sections.** Partial plan visibility gives Doubt verifiable invariants without anchoring. See section 4.2 and FM-4.

**S3: Allow Implement to read SPEC.md as fallback reference.** SPEC.md is static project context that helps the builder resolve ambiguities the plan did not anticipate. It does not cause the bias that dynamic artifacts (research, task description) would.

**S4: Replace the fixed 30-file Research cap with a tiered budget.** Scale with question category count: 30/50/75 files for 1-2/3-4/5-6 categories. See section 2.5.

**S5: Define the cross-model orchestrator integration point as "P+" subphase.** See section 5.1. This prevents architectural ambiguity when both systems are active.

**S6: Rename orchestrator `claims` to `design_assertions`.** Avoids naming collision with QRPID's implementation claims. See section 5.2.

**S7: Run pattern extraction on FAIL outcomes, not just PASS.** Doubt findings on failed pipelines are the highest-value patterns. See FM-6.

**S8: Increase retry count to 2 with error feedback.** One retry is insufficient for substantive failures. Include the specific validation error in the retry prompt. See OQ4.

### COULD (nice to have -- improves ergonomics)

**C1: Add duplicate-detection heuristic to question validation.** Reject question sets where any two questions share >80% token overlap. Low implementation cost, catches degenerate Q output.

**C2: Dynamic timeout scaling for Research.** Set timeout to `base_timeout + (question_count * 20s)` instead of the global `agent_timeout_secs`. See FM-7.

**C3: Support targeted R2 re-run for unanswered questions.** Rather than letting Plan read 5 files (which breaks its isolation contract), spawn a focused R2 pass. See FM-3 and OQ6.

**C4: Make QRPID opt-in via config.** Add `"pipeline": "spid" | "qrpid"` to `.foundry.json`. Keep SPID as default until QRPID proves itself over 20+ tasks. See CQ4.

**C5: Allow Q to reference prior research report.** If `research-report.md` exists from a recent task in the same code area, Q can use it for orientation without re-reading code. See CQ6.

**C6: Add substantive emptiness checks to transition validators.** Beyond structural validation (file exists, sections present), check for degenerate content (all questions identical, all answers `[UNANSWERED]`, all claims identical). Low-cost heuristic that catches pathological agent output.

---

## Appendix: Decision Log

| Decision Point | Position Taken | Confidence | Rationale |
|---------------|---------------|------------|-----------|
| R isolation enforcement | Prompt-based is acceptable for v1 with temp-dir mechanism for critical boundaries | High | Docker sandbox is available but heavy; temp-dir move is lightweight and sufficient |
| Doubt seeing plan | Partial (Constraints + Open Risks only) | High | Confirmed by FM-4 analysis; current SPID reviewer already suffers from this gap |
| 30-file cap | Too low; tier it | Medium | Depends on target codebase size; context-foundry alone has 35 .rs files |
| Cross-model orchestrator integration | P+ subphase | High | Clean separation of concerns; both specs are explicit about their scope |
| QRPID vs SPID migration | Opt-in first | High | Risk management; SPID works today |
| Token cost | ~30% increase over SPID; acceptable for success rate target | Medium | Estimate based on current pricing; varies with model and task complexity |

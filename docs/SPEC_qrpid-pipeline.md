# QRPID Pipeline Specification

> Evolution of SPID, incorporating phase isolation and context budgeting from CRISPY.

**Status:** Draft -- pending critique
**Date:** 2026-03-28
**Replaces:** SPID (Scout, Plan, Implement, Doubt)

---

## Pipeline Overview

```
Q ──→ R ──→ P ──→ I ──→ D
              ↑         ↑
           patterns   patterns
           injected   extracted
```

Five phases. Each phase is a **separate agent invocation** -- no phase bleeds into another. The orchestrator controls all transitions. Agents return structured artifacts; the orchestrator validates the schema before advancing.

| Phase | Name | Purpose | Sees original task? |
|-------|------|---------|-------------------|
| Q | Question | Generate research queries from task | Yes |
| R | Research | Objective codebase exploration | **No** -- only sees questions |
| P | Plan | Design + tactical implementation plan | Yes + research report |
| I | Implement | Execute the plan | Plan only |
| D | Doubt | Fresh-context audit | Claims only |

---

## Phase 1: Question (Q)

**Goal:** Convert a task description into a set of research questions that will fully inform a plan, without reading any code yet.

### Inputs
- Task description (from TASKS.md or user)
- SPEC.md (if exists) -- project-level context only
- Matched patterns from `~/.foundry/patterns/` (keyword-matched against task)

### Outputs
- `.buildloop/questions.md`

### Context Budget
- **Max input:** Task + SPEC.md + matched patterns. No source code.
- **Max output:** 30 questions, grouped by category.
- **Target context utilization:** <15%

### Agent Instructions (kept under 40)
1. Read the task description carefully.
2. Read SPEC.md if provided for project context.
3. Review any matched patterns for known risks.
4. Generate questions in these categories:
   - **Architecture:** How is the relevant code structured today?
   - **Dependencies:** What does this feature touch? What depends on what it touches?
   - **Conventions:** What patterns does this codebase use for similar features?
   - **Data:** What data models, schemas, or state are involved?
   - **Risk:** What could break? What edge cases exist?
   - **Verification:** How will we know this works?
5. Each question must be answerable by reading code, configs, or tests -- not by asking a human.
6. Do not suggest implementations. Do not read source code.
7. Write output to `.buildloop/questions.md` using the artifact schema below.

### Artifact Schema
```markdown
# Research Questions
Task: <task-id and title>
Generated: <timestamp>

## Architecture
- Q1: <question>
- Q2: <question>

## Dependencies
- Q3: <question>

## Conventions
- Q4: <question>

## Data
- Q5: <question>

## Risk
- Q6: <question>

## Verification
- Q7: <question>
```

### Transition Rule
Orchestrator validates: file exists, has at least 5 questions, covers at least 3 categories. Then advances to R.

---

## Phase 2: Research (R)

**Goal:** Objectively explore the codebase to answer the questions. No implementation opinions. Pure fact-finding.

### Inputs
- `.buildloop/questions.md` (from Q)
- Full codebase read access (Glob, Grep, Read)
- **NOT the original task description** -- this is the key isolation trick

### Outputs
- `.buildloop/research-report.md`

### Context Budget
- **Max input:** Questions + codebase reads.
- **Max file reads:** 30 files. If you need more, you're exploring too broadly.
- **Max output:** ~200 lines.
- **Target context utilization:** <40%

### Agent Instructions
1. Read `.buildloop/questions.md`.
2. For each question, explore the codebase to find the answer.
3. Cite every finding as `file:line` -- no vague references.
4. If a question cannot be answered from the code, mark it `[UNANSWERED]` with a note on why.
5. Do not suggest how to implement anything. Report what exists, not what should exist.
6. Do not read files that aren't relevant to answering a question. Stay focused.
7. Note any surprises -- things that contradict expectations or seem fragile.
8. Write output to `.buildloop/research-report.md` using the artifact schema below.

### Artifact Schema
```markdown
# Research Report
Questions source: .buildloop/questions.md
Generated: <timestamp>
Files read: <count>

## Findings

### Q1: <original question>
**Answer:** <factual answer with file:line citations>

### Q2: <original question>
**Answer:** <factual answer>
...

## Unanswered Questions
- Q<N>: <question> -- [UNANSWERED] <reason>

## Surprises
- <anything unexpected discovered during research>

## Files Examined
- <path> -- <why it was read>
```

### Transition Rule
Orchestrator validates: file exists, every question has an answer or `[UNANSWERED]` tag, at least 1 file citation exists. Then advances to P.

---

## Phase 3: Plan (P)

**Goal:** Design the solution and produce a deterministic implementation plan. This is the first phase that sees both the task AND the research findings. Merges CRISPY's "Design" and "Plan" -- one phase, one artifact, two sections.

### Inputs
- Task description (reintroduced here)
- `.buildloop/research-report.md` (from R)
- Matched patterns from `~/.foundry/patterns/`
- SPEC.md (if exists)

### Outputs
- `.buildloop/current-plan.md`

### Context Budget
- **Max input:** Task + research report + patterns + SPEC.md. Minimal new file reads (only if research report has `[UNANSWERED]` questions that block planning).
- **Max new file reads:** 5 (for unanswered questions only).
- **Max output:** ~150 lines.
- **Target context utilization:** <40%

### Agent Instructions
1. Read the task description and `.buildloop/research-report.md`.
2. Review matched patterns for known solutions and pitfalls.
3. **Design section:** Write a short (3-5 paragraph) design narrative:
   - What changes, why this approach, what alternatives were considered.
   - Reference specific findings from the research report.
4. **Plan section:** Write a vertical implementation plan:
   - Plan one feature path end-to-end, not a horizontal list of all files.
   - Each step: action (CREATE/MODIFY), file path, what changes, function signatures.
   - Order steps by execution sequence, not by file.
   - Include verification commands (build, test, lint) at checkpoints -- not just at the end.
5. List constraints: things the implementation must NOT do (from patterns, research surprises).
6. If research has `[UNANSWERED]` questions that block the plan, read those specific files now (max 5).
7. Write output to `.buildloop/current-plan.md` using the artifact schema below.

### Artifact Schema
```markdown
# Implementation Plan
Task: <task-id and title>
Generated: <timestamp>
Research: .buildloop/research-report.md

## Design

<3-5 paragraph design narrative>

### Alternatives Considered
- <option> -- <why rejected>

## Plan

### Step 1: <description>
- **Action:** CREATE | MODIFY
- **File:** <path>
- **Changes:** <specific description with function signatures>
- **Depends on:** <previous step or "none">

### Step 2: <description>
...

### Checkpoint: Verify <what>
- **Command:** <build/test/lint command>
- **Expected:** <what success looks like>

### Step N: ...

## Constraints
- MUST NOT: <constraint from patterns or research>
- MUST NOT: <constraint>

## Open Risks
- <risk that Doubt should specifically verify>
```

### Transition Rule
Orchestrator validates: file exists, has at least 1 step, every step has Action + File + Changes, at least 1 checkpoint exists. Then advances to I.

---

## Phase 4: Implement (I)

**Goal:** Execute the plan. Write code, run verification commands, report claims.

### Inputs
- `.buildloop/current-plan.md` (from P)
- Full codebase write access

### Outputs
- Code changes (files created/modified)
- `.buildloop/build-claims.md`

### Context Budget
- **Max input:** Plan + files being modified. Do NOT re-read the research report.
- **Target context utilization:** <60% (implementation needs room for iterating on errors)

### Agent Instructions
1. Read `.buildloop/current-plan.md`.
2. Execute each step in order.
3. Run checkpoint verification commands as specified in the plan.
4. If a step fails:
   - Try to fix within the plan's constraints.
   - If fix requires deviating from the plan, document the deviation.
   - Do NOT re-architect. If the plan is fundamentally wrong, stop and report.
5. After all steps complete, write `.buildloop/build-claims.md`.
6. Each claim must be a specific, verifiable statement -- not "it works" but "endpoint GET /api/foo returns 200 with JSON body matching FooResponse schema."

### Artifact Schema
```markdown
# Build Claims
Task: <task-id and title>
Generated: <timestamp>
Plan: .buildloop/current-plan.md

## Files Changed
- [CREATE|MODIFY] <path> -- <description>

## Verification Results
- Build: PASS|FAIL (<command>)
- Tests: PASS|FAIL (<command>)
- Lint: PASS|FAIL (<command>)

## Claims
- [ ] <specific verifiable statement>
- [ ] <specific verifiable statement>

## Deviations from Plan
- Step <N>: <what changed and why>

## Gaps and Assumptions
- <anything not verified>
- <assumptions that Doubt should check>
```

### Transition Rule
Orchestrator validates: file exists, at least 1 file in "Files Changed", at least 1 claim listed. Then advances to D.

---

## Phase 5: Doubt (D)

**Goal:** Fresh-context audit. Verify claims against actual code. Fix issues.

### Inputs
- `.buildloop/build-claims.md` (from I)
- Full codebase read + write access
- **NOT the task description, research, or plan** -- fresh eyes

### Outputs
- `.buildloop/review-report.md`
- Direct code fixes for HIGH/MEDIUM issues

### Context Budget
- **Max input:** Claims + code under review.
- **Target context utilization:** <50%

### Agent Prompt
> "Audit and validate these claims. Find the gaps. Read `.buildloop/build-claims.md`. For every claim, verify it against the actual code. Run the build and tests yourself. For every HIGH or MEDIUM issue, fix it directly -- do not just report. Write findings to `.buildloop/review-report.md`."

### Severity Levels
- **HIGH:** Claim is false, code is broken, or security issue. Must fix before merge.
- **MEDIUM:** Claim is partially true, edge case missed, or test gap. Must fix before merge.
- **LOW:** Style issue, minor optimization, or documentation gap. File for later.

### Artifact Schema
```markdown
# Review Report
Claims source: .buildloop/build-claims.md
Generated: <timestamp>
Verdict: PASS | FAIL

## Claim Verification
- [x] <claim> -- VERIFIED <how>
- [ ] <claim> -- FAILED <what's wrong>

## Issues Found
### HIGH: <title>
- **What:** <description>
- **Where:** <file:line>
- **Fix:** <what was done> | NEEDS HUMAN

### MEDIUM: <title>
...

### LOW: <title>
...

## Build/Test Results
- Build: PASS|FAIL (<command>)
- Tests: PASS|FAIL (<command>)

## Final Verdict
<PASS or FAIL with summary>
```

### Transition Rule
- If verdict is PASS: orchestrator commits as `feat(<task-id>): <description>`
- If verdict is FAIL with unfixed HIGHs: orchestrator commits as `WIP(<task-id>): <description>` and flags for human review

---

## Pipeline Modes

### Full Mode: `[QRPID]`
All 5 phases run. Use for:
- First task in a new project
- Risky changes (migrations, auth, infra)
- Unfamiliar codebases

### Fast Mode: `[QRPID:fast]` -- skip Q+R
Starts at Plan. Use when:
- `.buildloop/research-report.md` exists and is current
- Task is a continuation in the same codebase area
- SPEC.md has explicit implementation detail

Becomes `[-PID]` in task markers.

### Batched Doubt
For sequential tasks in one session, defer D and run once at the end.
Tasks marked `[QRP I-]` until the combined Doubt runs.

---

## Deterministic Phase Transitions

The orchestrator -- not the agent -- controls all transitions. Each phase:

1. **Spawns** a fresh agent with phase-specific prompt + inputs
2. **Receives** the agent's output artifact
3. **Validates** artifact against the schema (required fields, minimum counts)
4. **Advances** to next phase only on validation pass
5. **Fails** the pipeline if validation fails after 1 retry

Agents cannot:
- Decide to skip a phase
- Start the next phase within their response
- Read artifacts from phases they shouldn't see (enforced by input control)

This is the core architectural difference from SPID: **the orchestrator is a state machine, not a suggestion.**

---

## Context Isolation Matrix

| Phase | Task | SPEC | Questions | Research | Patterns | Plan | Claims | Code (read) | Code (write) |
|-------|------|------|-----------|----------|----------|------|--------|-------------|-------------|
| Q     | Yes  | Yes  | --        | --       | Yes      | --   | --     | No          | No          |
| R     | **No** | No | Yes       | --       | No       | --   | --     | Yes         | No          |
| P     | Yes  | Yes  | No        | Yes      | Yes      | --   | --     | Limited*    | No          |
| I     | No   | No   | No        | No       | No       | Yes  | --     | Yes         | Yes         |
| D     | **No** | No | No        | No       | No       | **No** | Yes  | Yes         | Yes (fixes) |

*Plan can read up to 5 files only to resolve `[UNANSWERED]` research questions.

Key isolation rules:
- **R never sees the task.** This prevents implementation anchoring during research.
- **D never sees the task or plan.** This prevents confirmation bias during audit.
- **I only sees the plan.** This forces the plan to be complete and self-contained.

### Isolation Enforcement Guarantee

Context isolation is enforced at the **filesystem level**: the orchestrator physically moves restricted artifacts out of the project workspace before spawning the agent, and restores them after the agent completes. This is stronger than prompt-only isolation (which has a ~5% leak rate from curious agents) but weaker than process-level isolation (e.g., Docker filesystem restrictions).

**Mechanism:** `PhaseIsolation::activate()` in `src/isolation.rs` renames restricted files to a temporary staging directory. The agent process has no path to the staging directory in its prompt or working directory. Files are automatically restored via a `Drop` safety net if the agent crashes.

**What this guarantees:**
- R cannot `Read`, `Grep`, or `Glob` for TASKS.md -- the file does not exist during R's execution
- D cannot `Read` `.buildloop/current-plan.md` -- the file does not exist during D's execution
- Standard filesystem tools (find, cat, grep) will not discover hidden files

**What this does NOT guarantee:**
- The agent could theoretically search `/tmp` for `.foundry-isolation-*` directories (extremely unlikely without explicit instruction)
- Information that has already been embedded in other artifacts (e.g., task ID in `questions.md` header) is not redacted
- CLAUDE.md and other auto-injected context may reference restricted concepts indirectly

**Config:** `"phase_isolation": true` in `.foundry.json` enables this enforcement. Default: `false` (opt-in during QRPID development).

---

## Pattern Integration

### Before Q (injection)
Orchestrator keyword-matches task description against `~/.foundry/patterns/*.json` and injects matched patterns into Q and P inputs.

### After D (extraction)
On pipeline completion, extract 0-5 new patterns from the build artifacts:
- Issues found by Doubt that the builder missed
- Deviations from plan that succeeded (the plan was wrong)
- Surprises from research that affected the design

Save to `~/.foundry/patterns/` with: `pattern_id`, `title`, `severity`, `keywords`, `issue`, `solution`, `source_task`.

---

## Artifact Lifecycle

All artifacts live in `.buildloop/` and are **overwritten** each pipeline run (not accumulated). They represent the current state, not history. Git history is the log.

```
.buildloop/
├── questions.md          # Q output
├── research-report.md    # R output
├── current-plan.md       # P output
├── build-claims.md       # I output
├── review-report.md      # D output
└── logs/                 # Raw agent outputs (debug)
```

---

## Migration from SPID

| SPID concept | QRPID equivalent | Change |
|-------------|-------------------|--------|
| Scout | Q + R | Split into isolated phases |
| Plan | P | Now receives structured research, not raw scout dump |
| Implement | I | Unchanged |
| Doubt | D | Unchanged |
| `scout-report.md` | `questions.md` + `research-report.md` | Two artifacts instead of one |
| `[SPID]` markers | `[QRPID]` markers | Updated in TASKS.md |
| Fast mode skips Scout | Fast mode skips Q+R | Same concept, new naming |
| No context budgets | Per-phase budgets | New constraint |
| Agent-driven transitions | Orchestrator-driven transitions | Architectural change |

---

## Open Questions for Critique

1. **Is the 30-file cap on Research too low?** Large codebases might need more exploration. But uncapped reads defeat the context budget purpose.
2. **Should Plan see the questions artifact too?** Currently it only sees research answers. Seeing the questions might help it understand what was asked and why.
3. **Should Doubt see the plan?** Current spec says no (fresh eyes). But seeing the plan might help Doubt verify intent, not just correctness.
4. **Is one retry on validation failure enough?** Schema validation is mechanical, but an agent might produce a structurally valid but substantively empty artifact.
5. **Should pattern injection be transparent?** Currently patterns are silently injected. Should the agent know which patterns were matched and why?
6. **How should the orchestrator handle [UNANSWERED] questions that block planning?** Current spec lets Plan read 5 files. Alternative: bounce back to R for a targeted second pass.

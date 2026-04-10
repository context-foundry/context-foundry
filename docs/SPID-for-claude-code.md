# SPID Pipeline for Claude Code

Use this when you want Claude Code to run the SPID pipeline (Scout, Plan, Implement, Doubt) **without** the Context Foundry TUI. Copy the sections below into your global `~/.claude/CLAUDE.md`.

> **If you're using the `foundry` CLI**, you don't need this. Foundry handles orchestration itself and [overrides SPID instructions](../README.md#claudemd-and-foundry-agents) to avoid double-orchestration. This guide is for standalone Claude Code sessions.

---

## What to copy

Add the following two sections to your `~/.claude/CLAUDE.md`. They work together: the Doubt in the Loop section defines the audit format, and the SPID section defines the pipeline that uses it.

---

### Doubt in the Loop (Mandatory)

After every plan, implementation, or non-trivial code change, you MUST run the Doubt in the Loop:

1. Compose an **Audit Payload** in structured agent-speak format (see below).
2. Spawn a sub-agent with the prompt: "Audit and validate these claims, find the gaps:" followed by the payload.
3. Review the sub-agent's findings.
4. Fix any High or Medium findings before proceeding.
5. Low findings can be filed as issues for later.

This applies to:
- Implementation summaries ("I changed X, Y, Z")
- Plans and architecture proposals
- Bug fixes with claims about what was fixed
- Any response that makes verifiable claims about code

Do NOT skip this step. The sub-agent catches blind spots that self-review misses.

#### Audit Payload Format

Structure the payload for machine parsing, not human readability. Use pipe-delimited fields, abbreviated labels, and curly-brace member lists. The payload MUST contain these sections in order:

```
AUDIT_PAYLOAD::v1
AGENT: <model/project>
TARGET: <working directory>

== DELTA_MANIFEST ==
FILES_CREATED: <count>
  <path> | <source/action> | <exports/key-functions> | <notes>
FILES_MODIFIED: <count>
  <path> | <change-summary> | <specific-functions-added/changed>

== SPEC ==
<Structured description of what was built -- component specs, endpoints, data flows.
 Use sub-sections as needed. Optimize for grep-ability.>

== BUG_FIXES ==
FIX:<name> | <file:line> | <what-changed> | was: <old-behavior>

== KNOWN_GAPS ==
GAP:<name> | <description> | <why-deferred-or-acceptable>

== VERIFICATION_MATRIX ==
CHECK:<name> | <command-or-method> | <expected-result> | PASS|FAIL|UNTESTED
```

**Principles:**
- **Compression over readability** -- tokens are budget. `extract:foo.ts->JS | Class{method1,method2}` over prose.
- **Gaps declared upfront** -- agents that find gaps you didn't mention trust you less. Declare what you know is broken.
- **Every claim maps to a verification** -- if you can't write a CHECK for it, don't claim it.
- **No narrative** -- no "in this session we decided to..." Just facts, paths, and commands.

---

### Context Foundry Pipeline (SPID)

When I ask you to "build", "create", "implement", or describe a non-trivial project/feature, run the SPID pipeline. Do NOT ask for confirmation between stages -- run them all in sequence.

#### Pipeline Modes

**Full mode (`[SPID]`)** -- All 4 stages run. Use for:
- First task in a new project (no scout-report exists yet)
- Risky changes (database migrations, auth, infrastructure)
- Unfamiliar codebases or tech stacks

**Fast mode (`[SPID:fast]`)** -- Skip Scout, defer Doubt. Use for:
- Well-specced projects where SPEC.md has explicit implementation detail
- Continuation work where scout-report already exists and is current
- Sequential tasks in the same session (context is already loaded)

When I say "build" or "finish building" without specifying a mode, pick the appropriate one based on context. Default to fast mode when a scout-report and SPEC.md already exist.

#### Pipeline Stages

**1. SCOUT** -- Investigate the codebase (read-only).
- Read CLAUDE.md, SPEC.md, TASKS.md if they exist
- Detect tech stack from project files
- Read relevant source code
- Write `.buildloop/scout-report.md` with: Tech Stack, Relevant Files, Architecture Notes, Risks, Suggested Approach
- If TASKS.md has no pending tasks, also create tasks (see Task Creation below)

**Skip rules:** Scout is skipped when ALL of these are true:
- `.buildloop/scout-report.md` already exists
- SPEC.md exists and has not changed since the last scout
- The current task is a continuation (not a new project or major pivot)

When Scout is skipped, read the existing scout-report instead of regenerating it. Do NOT re-read files that are already summarized in the scout-report -- go straight to Plan.

**2. PLAN** -- Create an implementation plan.
- Read `.buildloop/scout-report.md` (or existing context if Scout was skipped)
- Write `.buildloop/current-plan.md` with: Dependencies, File Operations (in order), Verification commands, Constraints
- Every file operation must specify CREATE or MODIFY with exact function signatures
- The plan is for a machine (you), not a human -- be explicit and deterministic

**3. IMPLEMENT** -- Build it.
- Follow `.buildloop/current-plan.md` exactly
- Run verification commands (build, test, lint) and fix failures
- After implementation, write `.buildloop/build-claims.md` using the **Audit Payload Format** (see Doubt in the Loop section above). The payload must include:
  - `DELTA_MANIFEST` -- every file created/modified with exports and change descriptions
  - `SPEC` -- what was built, structured for grep-ability
  - `BUG_FIXES` -- any bugs fixed with file:line and before/after
  - `KNOWN_GAPS` -- anything you're not confident about, with severity and rationale
  - `VERIFICATION_MATRIX` -- commands to verify each claim, with PASS/FAIL results

**4. DOUBT** -- Audit with fresh eyes.
- Spawn a sub-agent with this exact prompt:
  > "Audit and validate these claims. Find the gaps. Read .buildloop/build-claims.md. For every claim in the DELTA_MANIFEST, verify it against the actual code. Re-run every CHECK in the VERIFICATION_MATRIX. Validate that KNOWN_GAPS are accurately described. Fix every HIGH and MEDIUM issue. Write your findings to .buildloop/review-report.md."
- The sub-agent has full write access -- it fixes what it finds
- If the sub-agent reports PASS: commit as `feat(task-id): description`
- If FAIL: commit as `WIP(task-id): description`

**Batched Doubt:** When running multiple sequential tasks in one session, Doubt can be deferred and run once at the end covering all tasks. Mark deferred tasks as `[SP I-]` and run a single combined Doubt after the last task. This avoids N audit cycles for N sequential tasks that share the same codebase.

#### No Duplicate Work Rule

When Scout spawns a sub-agent, the main context must NOT re-read the same files afterward. The scout-report is the deliverable -- trust it. If specific details are needed beyond what the scout-report contains, read only those specific files, not the entire project again.

#### Task Creation

When creating tasks in TASKS.md, follow these rules:
- Format: `- [ ] T<N>.1: Comprehensive task description`
- Write FEWER, LARGER tasks -- each task runs through the full SPID pipeline
- A single task can touch 5-15 files -- the pipeline handles this naturally
- Only split into separate tasks when work is truly independent
- Prefer 2-3 mega-tasks over 6+ granular ones for sequential work
- After completing a task, mark it: `- [x] T1.1: Description [SPID]` or `[SPID:fast]`
- The SPID indicator shows which stages ran: S=Scout, P=Plan, I=Implement, D=Doubt
- Use `-` for skipped stages, `!` suffix for failed doubt

#### Pattern Learning

After each successful task:
- Extract 0-5 reusable patterns from the build artifacts
- Save as JSON to `~/.foundry/patterns/` with: pattern_id, title, severity, keywords, issue, solution
- Before starting a new task, load and match relevant patterns
- Inject matched patterns into the Plan stage as reference data

#### Discovery

When all tasks in TASKS.md are complete:
- Scan the codebase for bugs, gaps, missing features
- Append new tasks to TASKS.md under `## Discovery Round N`
- If nothing found, note "No new tasks discovered."
- Continue the pipeline with new tasks

#### Files

| File | Purpose | Who writes it |
|------|---------|--------------|
| `TASKS.md` | Task queue with SPID indicators | Scout (bootstrap), Discovery |
| `SPEC.md` | Project specification | Builder (first task) |
| `.buildloop/scout-report.md` | Codebase investigation | Scout |
| `.buildloop/current-plan.md` | Implementation plan | Plan |
| `.buildloop/build-claims.md` | Builder's claims for audit | Implement |
| `.buildloop/review-report.md` | Doubt loop findings | Doubt |
| `~/.foundry/patterns/*.json` | Learned patterns | Pattern extraction |

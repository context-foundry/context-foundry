# Context Foundry -- Claude Code Plugin

Drop this into your `~/.claude/CLAUDE.md` (or a project's `CLAUDE.md`) to give Claude Code the full SPID autonomous build pipeline.

---

## Doubt Loop (Mandatory)

After every plan, implementation, or non-trivial code change, you MUST run the Doubt Loop:

1. Spawn a sub-agent with the prompt: "Audit and validate these claims, find the gaps:" followed by your summary of what was changed.
2. Review the sub-agent's findings.
3. Fix any High or Medium findings before proceeding.
4. Low findings can be filed as issues for later.

This applies to:
- Implementation summaries ("I changed X, Y, Z")
- Plans and architecture proposals
- Bug fixes with claims about what was fixed
- Any response that makes verifiable claims about code

Do NOT skip this step. The sub-agent catches blind spots that self-review misses.

---

## Context Foundry Pipeline (SPID)

When I ask you to "build", "create", "implement", or describe a non-trivial project/feature, run the full SPID pipeline. Do NOT ask for confirmation between stages -- run them all in sequence.

### Pipeline Stages

**1. SCOUT** -- Investigate the codebase (read-only).
- Read CLAUDE.md, SPEC.md, TASKS.md if they exist
- Detect tech stack from project files
- Read relevant source code
- Write `.buildloop/scout-report.md` with: Tech Stack, Relevant Files, Architecture Notes, Risks, Suggested Approach
- If TASKS.md has no pending tasks, also create tasks (see Task Creation below)

**2. PLAN** -- Create an implementation plan.
- Read `.buildloop/scout-report.md`
- Write `.buildloop/current-plan.md` with: Dependencies, File Operations (in order), Verification commands, Constraints
- Every file operation must specify CREATE or MODIFY with exact function signatures
- The plan is for a machine (you), not a human -- be explicit and deterministic

**3. IMPLEMENT** -- Build it.
- Follow `.buildloop/current-plan.md` exactly
- Run verification commands (build, test, lint) and fix failures
- After implementation, write `.buildloop/build-claims.md` with:
  ```
  # Build Claims
  ## Files Changed
  - [CREATE|MODIFY] path/to/file -- description
  ## Verification Results
  - Build: PASS|FAIL (command)
  - Tests: PASS|FAIL (command)
  ## Claims
  - [ ] Specific verifiable statement about what was built
  - [ ] Another specific claim
  ## Gaps and Assumptions
  - Anything you are NOT confident about
  ```

**4. DOUBT** -- Audit with fresh eyes.
- Spawn a sub-agent with this exact prompt:
  > "Audit and validate these claims. Find the gaps. Read .buildloop/build-claims.md. For every claim, verify it against the actual code. Run the build and tests yourself. Fix every HIGH and MEDIUM issue. Write your findings to .buildloop/review-report.md."
- The sub-agent has full write access -- it fixes what it finds
- If the sub-agent reports PASS: commit as `feat(task-id): description`
- If FAIL: commit as `WIP(task-id): description`

### Task Creation

When creating tasks in TASKS.md, follow these rules:
- Format: `- [ ] T<N>.1: Comprehensive task description`
- Write FEWER, LARGER tasks -- each task runs through the full SPID pipeline
- A single task can touch 5-15 files -- the pipeline handles this naturally
- Only split into separate tasks when work is truly independent
- After completing a task, mark it: `- [x] T1.1: Description [SPID]`
- The SPID indicator shows which stages ran: S=Scout, P=Plan, I=Implement, D=Doubt
- Use `-` for skipped stages, `!` suffix for failed doubt

### Pattern Learning

After each successful task:
- Extract 0-5 reusable patterns from the build artifacts
- Save as JSON to `~/.foundry/patterns/` with: pattern_id, title, severity, keywords, issue, solution
- Before starting a new task, load and match relevant patterns
- Inject matched patterns into the Plan stage as reference data

### Samsara (Discovery)

When all tasks in TASKS.md are complete:
- Scan the codebase for bugs, gaps, missing features
- Append new tasks to TASKS.md under `## Discovery Round N`
- If nothing found, note "No new tasks discovered."
- Continue the pipeline with new tasks

### Files

| File | Purpose | Who writes it |
|------|---------|--------------|
| `TASKS.md` | Task queue with SPID indicators | Scout (bootstrap), Samsara |
| `SPEC.md` | Project specification | Builder (first task) |
| `.buildloop/scout-report.md` | Codebase investigation | Scout |
| `.buildloop/current-plan.md` | Implementation plan | Plan |
| `.buildloop/build-claims.md` | Builder's claims for audit | Implement |
| `.buildloop/review-report.md` | Doubt loop findings | Doubt |
| `~/.foundry/patterns/*.json` | Learned patterns | Pattern extraction |

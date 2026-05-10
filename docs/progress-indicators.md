# Progress Indicators (QRPBA)

Context Foundry writes a compact pipeline indicator next to each task in
`TASKS.md`. The indicator records the coarse execution path for that task:
which pipeline stages ran, which were skipped or resumed, and whether the final
audit path passed.

This is deliberately simple, and that is the point. A task line becomes a small
audit record that travels with the code:

```text
- [x] T1.1: Set up project scaffolding          [QRP-BA]
- [x] T1.2: Implement auth flow                 [--P-BA]
- [x] T1.3: Add rate limiting                   [QRP-BA!]
- [ ] T1.4: Write integration tests             [....]
```

The indicator is committed with the task update and code changes. That makes it
part of Git history, not just a terminal status line that disappears when the
TUI exits.

## Why This Exists

Context Foundry is a staged pipeline. Query, Research, Plan, Build, and Audit
run in separate contexts, exchange information through `.buildloop/` artifacts,
and can be skipped, retried, checkpoint-resumed, or bypassed based on task
complexity and configuration.

Without a persisted indicator, a completed task only says "done." It does not
say whether it was done with the full pipeline, a fast path, a skipped audit, or
a failed audit that produced a WIP commit. That distinction matters when reading
history later.

We have seen this become important while designing the eval harness:

- Prompt plumbing can fail silently. A stage can produce output even if it did
  not receive the expected system prompt, pattern context, extension context, or
  prior artifact reference.
- Skips are not all the same. A stage can be skipped because the task is simple,
  because a checkpoint says prior work is reusable, because batch mode deferred
  audit, or because a stage is disabled.
- Runtime state is spread across several places. The TUI has live in-memory
  state, `.buildloop/` has local runtime artifacts, and `TASKS.md` is the
  durable project record.
- A human reviewing a commit needs the coarse path immediately. The full logs
  may be gone, but `[QRP-BA]` or `[---B-]` still tells you how much process ran.

The indicator is not a full eval result. It is the durable headline. The eval
harness plan adds a deeper generated report (`.buildloop/eval-report.json`) for
plumbing and heuristic checks, but the QRPBA marker remains the Git-backed
summary on the task itself.

## Is This Stateful?

Yes, but there are different kinds of state in Context Foundry.

| Layer | Location | Lifetime | Committed? | Purpose |
|-------|----------|----------|------------|---------|
| Live UI state | Rust process memory | Current TUI session | No | Shows active stage and recent task history while Foundry is running |
| Runtime state | `.buildloop/` | Local workspace run state | Usually no | Stores stage artifacts, logs, checkpoints, telemetry, and generated reports |
| Task state | `TASKS.md` | Project history | Yes | Stores task completion and the compact QRPBA execution record |
| Git state | Git commits | Repository history | Yes | Makes task outcome and pipeline path reviewable later |

So when this document says the indicator is "stateful," it means it is durable
task state in `TASKS.md`. It is not the only state in Foundry, and it is not the
most detailed state. It is the small piece of state that is intentionally
checked in.

## Letter Scheme

The stable pipeline slots are:

| Position | Letter | Stage | Meaning |
|----------|--------|-------|---------|
| 1 | `Q` | Query | Investigation questions ran |
| 2 | `R` | Research | Research or scout context ran |
| 3 | `P` | Plan | Planner ran or was checkpoint-resumed |
| 4 | `+` or `-` | P+ | Optional plan-review subphase ran or skipped |
| 5 | `B` | Build | Builder/implement ran or was checkpoint-resumed |
| 6 | `A` | Audit | Audit/verify/doubt ran |

The common visual shorthand is still "QRPBA" because those are the five core
stages. In the persisted marker, there is also an optional P+ sub-slot between
Plan and Build. Most tasks show `-` in that slot because P+ is skipped.

## Symbols

| Symbol | Meaning |
|--------|---------|
| `Q`, `R`, `P`, `B`, `A` | The corresponding core stage ran, or a checkpoint-resumed stage is counted as already completed |
| `+` | P+ plan review ran and accepted a reviewed plan |
| `-` | That slot was skipped, reused, deferred, or checkpoint-resumed without a fresh agent run |
| `.` | Pending or in-progress placeholder |
| `!` | Failure sentinel: audit did not validate, P+ failed, or the task committed as WIP |

Checkpoint-resumed stages count as completed for the coarse task indicator. The
more precise reason belongs in logs today and in the eval harness manifest once
that lands.

## Examples

| Indicator | Interpretation |
|-----------|----------------|
| `QRP-BA` | Full core pipeline ran; P+ skipped; audit passed |
| `--P-BA` | Query and Research skipped or reused; Plan, Build, and Audit ran |
| `---B-` | Fast path: only Build ran; Audit skipped |
| `QRP+BA` | Query, Research, Plan, accepted P+ review, Build, and Audit ran |
| `QRP-BA!` | Full core pipeline ran, but audit did not validate; WIP path |
| `---B-!` | Build-only path produced a WIP result |

## What It Does Not Prove

The QRPBA indicator is intentionally coarse. It answers "which path did the
pipeline take?" It does not prove the path was healthy.

For example, `[QRP-BA]` does not by itself prove:

- the Planner received the matched pattern context;
- the Builder read `.buildloop/current-plan.md`;
- the Audit read `.buildloop/build-claims.md`;
- extension context was injected;
- the configured model matched the effective runtime model;
- the stage artifact was complete and non-truncated.

Those are eval-harness concerns. The indicator belongs in Git because it is the
minimal historical record. The eval harness belongs in `.buildloop/` because it
is detailed run observability.

## How It Is Written

Foundry updates the task line during the run and writes a final indicator just
before committing. The final write is intentionally late: agents may edit
`TASKS.md` while they run, so Foundry rewrites the indicator after the pipeline
has finished and before `git add -A`.

The parser treats the marker as part of the task line, but removes it from the
human-readable task description when loading tasks. Existing indicators are
replaced in place rather than appended repeatedly.

## TUI Display

The TUI has two related displays:

- Current run: live in-memory state shows stages as active, seen, or pending.
- Completed task: persisted task history or the marker in `TASKS.md` shows the
  durable result.

This is why the TUI can show richer live progress while the task is running, but
the committed marker stays compact.

Color conventions:

- Green: stage ran and the task validated.
- Red/yellow: failed audit or WIP path.
- Gray: skipped, pending, or unavailable stage data.

### Narrative panel

The right column also includes a 6-row Narrative panel between the Task Queue
and Patterns panes. It surfaces three lines:

- **Last:** the most recent commit subject, short SHA, and relative age. Comes
  from `git log -1 --format='%s|%cr|%h'`, refreshed every 10 seconds in the
  background.
- **Now:** the current task ID + short description, the active stage ID,
  elapsed stage time, and event count. Reads `state.current_task`,
  `state.current_agent`, `state.current_agent_stage_id`, and
  `state.events_received`.
- **Next:** the next pending task description from `state.next_task_hint`.

When a slot has no data the panel falls back to placeholder copy
(`no prior commits`, `no task in progress`, `queue empty`). The panel is
read-only and never blocks the TUI.

## Relationship To The Eval Harness

The planned eval harness adds a second, deeper status line:

```text
EVAL Q✓R✓P✓B⚠A✓
```

That line grades plumbing and heuristic checks from a run manifest, transcripts,
and artifacts. It is more detailed than QRPBA and can distinguish "stage ran"
from "stage ran with missing context."

The two indicators answer different questions:

| Indicator | Question answered | Source |
|-----------|-------------------|--------|
| QRPBA marker | Which execution path did this task take? | `TASKS.md`, committed |
| EVAL badge | Did the path appear healthy? | `.buildloop/eval-report.json`, generated |

Keep both. The committed marker is the durable project memory. The eval report
is the local diagnostic record.

## Legacy Indicators (SPID / RPID)

Before P33.1 (commit `5560b0a`), indicators used the SPID scheme:
`S` = Scout, `P` = Plan, `I` = Implement, `D` = Doubt/Verify. Some older
`TASKS.md` files may still contain markers such as `[SPID]`, `[S-ID]`, or
`[RPID]`.

Treat those as read-only historical artifacts. Do not rewrite old completed
tasks just to modernize their markers.

If a current run writes `I` or `D` in a new indicator, that is a regression. The
current task marker vocabulary is Q/R/P/P+/B/A plus `-`, `.`, and `!`.

## Related Docs

- [README.md](../README.md) -- project overview with indicator examples
- [Local model setup](local-model-setup.md) -- smoke gate check 6 validates QRPBA convention
- [Per-stage routing](per-stage-routing.md) -- how different models can be pinned to each stage
- [Eval harness plan](PLAN_eval-harness.md) -- planned deeper run-health reporting

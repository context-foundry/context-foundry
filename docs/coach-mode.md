# Coach Mode

Coach mode (`run_mode = "coach"`) inserts an intake-clarification stage between the user's typed intent and the bootstrap Scout. Its purpose is to surface assumptions in the user's spec before the autonomous pipeline silently bundles everything into one task.

Toggle via `Ctrl+M` (cycles auto -> sprint -> review -> coach -> auto) or via the Settings overlay (`?` -> Pipeline -> Run Mode).

## v1 (current): non-interactive pre-flight

When `run_mode == "coach"` and `.buildloop/intake-brief.md` does not yet exist, Coach runs a single turn before tasks are created. The hook fires at two entry points:

1. **`run_append_tasks`** (`src/app/planning.rs`) — the greenfield path. When the user types intent in the startup screen and Foundry plans the initial task queue, Coach runs first and the planner's `append_tasks_prompt` then prepends the brief.
2. **`spawn_build_loop`** (`src/app/build.rs`) — the bootstrap-Scout path. When the build loop kicks off against an empty TASKS.md (e.g. after Discovery clears the queue), Coach runs and `bootstrap_scout_prompt` consumes the brief.

In both cases:

- Coach reads `SPEC.md` (and any prior `.buildloop/intake-thread.md`).
- Coach writes `.buildloop/intake-brief.md` with: outline, surface/stack, key constraints, suspected task decomposition, and any open assumptions.
- The downstream prompt prepends the brief in a `--- BEGIN INTAKE BRIEF (clarified by user via Coach mode) ---` block; when the brief contradicts SPEC.md, the brief is the source of truth.

The Coach prompt always asks the agent to choose between two paths:

- `READY_TO_PROCEED` — confident enough; write `intake-brief.md` and stop.
- `AWAITING_USER` — write open questions to `intake-thread.md` and stop without a brief.

In v1 there is no UI to answer questions, so the user-facing flow is effectively path A. Coach is opt-in; users on `auto` / `sprint` / `review` see no behavior change.

## v2 (planned): multi-turn chat

The same `coach_intake_prompt` is designed for multi-turn use. v2 will:

- Display Coach's reply in the agent pane after each turn.
- Reuse the existing startup input box for the user's reply.
- Append each `(user, coach)` pair to `intake-thread.md`.
- Loop until Coach emits `READY_TO_PROCEED` (or the user types `go` / hits the 5-turn cap).

Architectural constraint that v2 must respect: do **not** suspend a PTY waiting for user input. Each Coach turn is a separate stateless `run_agent()` call.

## File layout

| File | Owner | Purpose |
|------|-------|---------|
| `.buildloop/intake-thread.md` | Coach (append-only) | Append-only transcript of `(user_turn, coach_turn)` pairs |
| `.buildloop/intake-brief.md` | Coach (write-once) | Final reconciled brief consumed by bootstrap Scout |
| `.buildloop/history/<task_id>/<UTC-timestamp>/` | Build loop (per-task cleanup) | Archived snapshots of `research-report.md`, `current-plan.md`, `build-claims.md`, `review-report.md`, `patterns-extracted.json`, `questions.md` taken just before per-task cleanup deletes them. `<task_id>` is the **producing** task (resolved from artifact headers), or `_orphaned` if no header is parseable. Retained per `history_retention_tasks` (default 50); pruning is best-effort and runs at end of cleanup. |

Both files persist after the run (per-task cleanup in `src/app/build.rs` does not touch them).

## Composition with eval

Coach composes with the existing eval ladder rather than replacing any check:

- `scout_explains_task_decomposition` (already shipped) — forces Scout to justify task count regardless of how the brief was produced.
- `task_queue_well_formed` (already shipped) — validates the resulting TASKS.md.
- v2 will add `intake_questions_present`, `intake_user_answers_captured`, `intake_brief_consumed_by_bootstrap`.

## Skipping Coach

Coach is automatically skipped when:

- `run_mode != "coach"`, OR
- `.buildloop/intake-brief.md` already exists (idempotent across re-runs — delete the file to re-coach), OR
- TASKS.md already has pending tasks (Coach only runs at the bootstrap-scout entry point).

## See also

- `docs/PLAN_coach-mode.md` — implementation plan
- [`docs/task-composition.md`](task-composition.md) — Coach exists to clarify task spec before Scout runs; what Coach optimizes for is exactly what good task composition produces. If your TASKS.md entries already pass the composition checklist, Coach has less to add.
- `src/prompts.rs::coach_intake_prompt` — the prompt
- `src/agent.rs::AgentRole::Coach` — restrictive tool surface (Read/Glob/Grep/Write only)
- `src/app/build.rs` — pre-flight invocation site

# Plan: Coach Mode

Date: 2026-05-09
Version: v1
Status: planning

## Context

Foundry's bootstrap Scout silently bundles SPECs into a single mega-task with no user dialogue. We added two downstream guarantees this session — `scout_explains_task_decomposition` (forces Scout to justify count) and `task_queue_well_formed` (validates the resulting TASKS.md). Coach mode is the upstream input-quality fix: a chat-shaped pre-flight that lets the user clarify ambiguous specs before TASKS.md is created. After the user types `go`, the pipeline runs autonomously.

## Architectural Constraint

The agent harness (src/agent.rs) is built around PTY-based agents that run to completion. **Do not suspend a PTY waiting for user input.** Each Coach turn must be a separate stateless `run_agent()` call. Persistence is via two files in `.buildloop/`:

- `intake-thread.md` — append-only transcript of (user_turn, assistant_turn) pairs
- `intake-brief.md` — the final reconciled brief that bootstrap Scout reads

## Scope (v1 -- non-interactive pre-flight)

A full chat-shaped multi-turn Coach requires reworking the agent state machine
(no PTY suspension), async event plumbing for inter-turn return-to-Startup
transitions, and the TUI input handler. That is multi-day work.

v1 ships the load-bearing infrastructure without the chat UX:

In:
- `run_mode = "coach"` as fourth value, toggled via Ctrl+M and Settings overlay
- New `AgentRole::Coach` with restrictive tool surface (Read/Glob/Grep/Write)
- `coach_intake_prompt(user_intent, spec, intake_thread, turn)` -- the same
  prompt that v2 will reuse for multi-turn
- Coach runs ONCE before bootstrap Scout in the same pipeline pass when
  `run_mode == "coach"`. No chat. Coach reads SPEC.md, writes
  `.buildloop/intake-brief.md` with: outline, suspected task decomposition,
  open assumptions
- `bootstrap_scout_prompt` consumes `intake-brief.md` when present
- Coach is greenfield-only: skipped when `intake-brief.md` already exists or
  TASKS.md has pending tasks

Deferred to v2:
- Multi-turn chat in the TUI input box (the user-visible "chat with the model"
  experience) -- the prompt is already designed for it
- Eval hooks (`intake_questions_present`, `intake_user_answers_captured`,
  `intake_brief_consumed_by_bootstrap`)
- Resuming an interrupted Coach session
- Voice/streaming UI changes

## File Operations (in order)

### 1. CREATE `src/app/coach.rs` (new module)
Module owning Coach state and orchestration helpers.
- `pub struct CoachState { pub thread_md: String, pub turn: usize, pub awaiting_agent: bool, pub awaiting_user: bool }` plus `Default` impl
- `pub fn intake_thread_path(buildloop_dir: &Path) -> PathBuf`
- `pub fn intake_brief_path(buildloop_dir: &Path) -> PathBuf`
- `pub fn append_user_turn(thread: &mut String, turn: usize, user_msg: &str)`
- `pub fn append_assistant_turn(thread: &mut String, turn: usize, assistant_msg: &str)`
- `pub fn parse_agent_signal(assistant_msg: &str) -> CoachSignal` where `enum CoachSignal { ReadyToProceed, AwaitingUser, Unknown }`
- Unit tests on the parsers and formatters.

### 2. MODIFY `src/agent.rs`
- Add `Coach` variant to `AgentRole` enum (line 19-30)
- Add to `AgentRole::from_str` parsing
- Add to `AgentRole::as_str` rendering ("coach")
- Add to `qrpba_slot()` returning `None` (Coach is pre-pipeline; no QRPBA letter)
- Update any exhaustive match sites the compiler complains about

### 3. MODIFY `src/prompts.rs`
- Add `pub fn coach_intake_prompt(user_intent: &str, spec_content: Option<&str>, intake_thread: &str, turn: usize) -> String`
  - Prompt shape: "You are the COACH. Goal: clarify the user's intent into a concrete brief. If intent is detailed enough, emit `READY_TO_PROCEED` and write `.buildloop/intake-brief.md` directly. Otherwise emit `AWAITING_USER`, write 1-4 short questions to `.buildloop/intake-thread.md` (append, don't overwrite), include suspected task decomposition, and stop. Do NOT exceed 5 turns."
  - Emit `--- BEGIN INTAKE THREAD ---` block when thread is non-empty
  - Emit `--- BEGIN SPEC ---` block when SPEC content present
- Modify `bootstrap_scout_prompt` (line 80) to accept `intake_brief: Option<&str>` parameter; prepend a `--- BEGIN INTAKE BRIEF (clarified by user) ---` block when present, with note that "intake-brief is the source of truth — the user clarified it intentionally"

### 4. MODIFY `src/app/state.rs`
- Add `pub coach: crate::app::coach::CoachState` field to `StartupState` (around line 120)
- Add `Default::default()` initialization
- Update FieldDef hint (line 455) from `"auto / sprint / review"` to `"auto / sprint / review / coach"`

### 5. MODIFY `src/app/startup.rs`
- Update Ctrl+M cycle (line 445-475): add "coach" between "review" and "auto"
- In `handle_startup_submit` (line 748-886): branch when `state.run_mode == "coach"`:
  - First submission: write user intent to `intake-thread.md` turn 0, spawn Coach agent
  - On agent finish: read agent output, parse signal, append to thread display, decide next state
  - Subsequent submissions: append user reply, spawn Coach agent again
  - On `READY_TO_PROCEED` (or user types literal `go`): set `pending_transition` to existing `StartBuild` (after writing final intake-brief.md)

### 6. MODIFY `src/app.rs` (the giant App orchestrator)
- Handle `LoopEvent::AgentDone` for Coach role: parse output, append to thread, update CoachState flags, redraw
- Make sure the agent-output channel routes Coach output to the agent pane just like Scout

### 7. MODIFY `src/app/build.rs`
- At bootstrap Scout invocation (line 2211): if `intake-brief.md` exists, read its contents and pass as new `intake_brief` parameter to `bootstrap_scout_prompt`. Otherwise pass `None`.

### 8. MODIFY `src/main.rs`
- Add `mod coach;` if not picked up via `app/coach.rs` mod inclusion (Rust will need `pub mod coach` in `src/app/mod.rs`)

### 9. MODIFY `src/app/mod.rs`
- `pub mod coach;`

## Verification

- `cargo build --release` succeeds
- `cargo test` passes (add unit tests for CoachState, signal parser, prompt builder)
- Manual smoke: `foundry` in fresh dir → press Ctrl+M to cycle to Coach → type `build me a weather app` → see Coach agent emit questions → type `make it offline-first` → repeat → type `go` → bootstrap Scout fires with intake-brief.md content visible in scout-report.md
- Existing tests for run_mode (auto/sprint/review) still pass

## Constraints

- No PTY suspension
- No modifications to `.buildloop/` semantics for non-Coach modes
- Must be opt-in via run_mode; users on Auto/Sprint/Review see zero behavior change
- Settings overlay must auto-pick up new mode value (FieldDef-driven)
- The Coach agent should have minimal tool access: Read, Write, Glob (no Bash, no Edit) to keep blast radius contained

## Risk

- **High**: Wiring multi-turn agent flow into AppPhase::Startup is the most novel piece — existing patterns are fire-and-forget per task. Mitigation: keep state explicitly on `CoachState`, drive transitions from `LoopEvent::AgentDone` matched on Role::Coach.
- **Medium**: Ctrl+M cycle and FieldDef enum need to enumerate the new value consistently. Mitigation: grep for `"auto" | "sprint" | "review"` and update all sites.
- **Medium**: bootstrap_scout_prompt signature change breaks call sites. Mitigation: only one call site (build.rs:2211); add the new param as `Option<&str>` so older test fixtures stay compiling.

## Out of Scope

- Eval hooks (deferred to v2)
- Multi-agent Coach (use the configured Sonnet)
- Session resume after crash
- Internationalization of Coach prompts

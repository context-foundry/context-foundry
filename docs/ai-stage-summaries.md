# AI Stage Summaries

Clicking any pipeline card in the TUI spawns a Haiku-grade LLM call that reads the relevant artifact and recent log tail, then renders a state-aware summary in a centred modal. The mechanism is the same `summarize_stage` foundation that T1.24 added for P+ summaries; T1.25 extended it to cover every pipeline card.

## Per-stage Coverage

| Stage        | Click target                          | Artifact(s)                                  | Inline data         | Prompt focus                                              |
|--------------|---------------------------------------|----------------------------------------------|---------------------|-----------------------------------------------------------|
| query        | Connected card 0                      | `.buildloop/questions.md`                    | -                   | Structured questions, HIGH priority items                 |
| research     | Connected card                        | `.buildloop/research-report.md`              | -                   | Tech stack, top risks, files inspected                    |
| plan         | Connected card                        | `.buildloop/current-plan.md`                 | -                   | File operations, verification commands                    |
| plan-review  | Connected card (P+ enabled)           | `.buildloop/current-plan.md`                 | -                   | P+ iteration state, findings                              |
| implement    | Connected card                        | `.buildloop/build-claims.md`                 | -                   | DELTA_MANIFEST, VERIFICATION_MATRIX, KNOWN_GAPS           |
| doubt        | Connected card                        | `.buildloop/review-report.md`                | -                   | Findings by severity, what was fixed                      |
| ship         | SHIP card (disconnected)              | (none)                                       | `git log` + status  | Latest commit subject + working tree state                |
| discover     | DISCOVER card (disconnected)          | `TASKS.md` (project root)                    | -                   | Discovery Round summary, new task IDs proposed            |

SHIP has no `.buildloop/` artifact; the click router gathers `git log -1` and `git status --porcelain` synchronously in the main thread before the summary call. The combined output is capped at 4096 bytes via `truncate_str`.

## States

Every prompt is parameterised by the stage's `StageState`:

- `not_started` -- stage has not run in this session yet. Prompts instruct the model to say so plainly.
- `running` -- stage is currently executing. Prompts emphasise current iteration / progress.
- `complete` -- last run succeeded. Prompts focus on outcomes.
- `failed` -- last commit was a WIP marker. Prompts call out failure reasons.

State is detected by `detect_stage_state` in `src/app.rs` based on the active agent and the presence of a `.buildloop/logs/<stage>-out.jsonl` log file plus the last commit subject.

## Keybindings

While the summary overlay is open:

- `Esc` or `q` -- dismiss the overlay (does not affect pipeline state).
- `r` -- refresh; ignores the cache and re-runs the LLM call.
- `f` -- dismiss the overlay and open the underlying artifact in the running explorer. Disabled for SHIP because SHIP has no backing file.

## Configuration

Three config fields drive summarisation:

- `summary_provider` (default `claude`) -- which LLM provider runs the summary call.
- `summary_model` (default `haiku`) -- which model the provider uses. Per-stage routing for the `summary` role overrides this global default.
- `prefer_file_open_over_summary` (default `false`) -- when set to `true`, every connected pipeline card and the DISCOVER card open the underlying file directly instead of summarising. SHIP becomes a no-op in this mode (it has no file to open).

Set these in `.foundry.json` (project) or `~/.foundry/config.json` (global). Project values override global.

## Caching

Summary results are cached in-memory keyed by BLAKE3 of `(stage, state, artifact mtimes)`. The cache invalidates on either an artifact mtime change OR a state transition. SHIP includes its inline `git log` / `git status` output in the prompt body. Because the inline text is regenerated on every click and folded into `log_tail` (not the artifact mtime set), SHIP summaries are computed fresh per click rather than cached against repo state; the cache will still serve a previous result for the same stage+state combination until the user presses `r` to force refresh.

Press `r` to bypass the cache for any stage.

## Cost

Each summary call:

- Reads up to 4096 bytes per artifact (`read_artifact_excerpt`) plus up to 8192 bytes of log tail.
- Issues a single Haiku call with a 5-second timeout.
- Caps output at 500 tokens (~4096 bytes after `truncate_str`).

20 clicks in a single session typically cost under $0.10 with mostly cache hits.

## Non-goals

The summary mechanism explicitly does NOT:

- Write back to artifacts or modify `.buildloop/` files.
- Modify the build state, advance the pipeline, or interrupt running agents.
- Edit `TASKS.md` or any other project file.
- Add new MCP tools, agent roles, or orchestrator stages. Observability for stage-summary calls already exists via the `StageSummaryRequested` event emitted to the observatory.

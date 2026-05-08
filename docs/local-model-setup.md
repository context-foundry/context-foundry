# Local Model Setup -- LM Studio + opencode

Foundry's Phase 32 routes the builder stage through the `opencode` CLI when the
user picks an LM Studio (or Ollama) model in the settings overlay. To exercise
that wiring end-to-end, you need: (1) `opencode` on PATH, (2) LM Studio running
with its OpenAI-compatible server bound to `http://127.0.0.1:1234`, and (3) at
least one model loaded inside LM Studio whose context window (`n_ctx`) is at
least 8192 tokens. Foundry's prompts plus `agent_system_directives` regularly
push past 4096 tokens; a smaller `n_ctx` produces the `exceeds the available
context size` error that P32.7 surfaces as `ContextOverflow`. After loading,
confirm the model is visible to opencode by running `opencode models lmstudio`
-- the leaf name (last path segment) is the canonical opencode model id.

To run the smoke test, build a release foundry binary (`cargo build --release`)
then execute `bash scripts/smoke-local-model.sh`. The script creates a throw-
away project in `$TMPDIR`, points `.foundry.json` at the first model returned
by `opencode models lmstudio`, runs `foundry run --no-tui --output-format json`,
and asserts six checks: foundry exits 0, the JSON output reports
`config.builder_provider == "opencode"`, at least one log file exists under
`.buildloop/logs/`, that log carries the opencode `sessionID` marker (and
zero log files carry Claude's `subtype:"init"` marker), and stderr is free of
the typed errors `ContextOverflow`, `ProviderUnreachable`, and `ModelNotLoaded`.
On PASS the script prints `[smoke] PASS  (workspace: ...)` and exits 0; pass
`--keep` to leave the workspace behind for inspection, or
`--timeout <secs>` to override the default 600s cap. The same gate is wired
to `cargo test --test local_model_smoke -- --ignored` for parity with the rest
of the test suite.

## Headless JSON envelope (`out.json`)

`foundry run --no-tui --output-format json` writes a single JSON object to
stdout. The envelope is versioned via `schema_version` (currently `2`). The
smoke gate asserts this version and fails loudly when it changes so callers
know to update their parsers. The schema is defined in
`src/app/commands.rs` (`HEADLESS_REPORT_SCHEMA_VERSION`, `SessionReport`,
`SessionStats`, `ConfigSnapshot`, `TaskResult`, `FindingCounts`).

```json
{
  "schema_version": 2,
  "tasks": [
    {
      "id": "T1.1",
      "description": "Create a file named hello.txt ...",
      "status": "DONE",
      "commit_sha": "abc123...",
      "findings": { "high": 0, "medium": 0, "low": 0 },
      "duration_secs": 12.34
    }
  ],
  "session": {
    "total_duration_secs": 42.7,
    "patterns_injected": 0,
    "patterns_learned": 0,
    "feat_commits": 1,
    "wip_commits": 0
  },
  "config": {
    "run_mode": "sprint",
    "builder_provider": "opencode",
    "builder_model": "lmstudio/qwen3.6-35b-a3b",
    "reviewer_provider": "claude",
    "reviewer_model": "opus"
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | integer | Bump when any field below is renamed or removed. Smoke gate asserts this is `2`. |
| `tasks[].status` | string | `"DONE"` (clean pass / `feat` commit) or `"WIP"` (verify failed / `WIP` commit). |
| `tasks[].commit_sha` | string \| null | `null` when no commit was produced. |
| `tasks[].findings` | object | Counts of HIGH/MEDIUM/LOW review findings. |
| `session.feat_commits` | integer | Number of tasks that produced a `feat(...)` commit. |
| `session.wip_commits` | integer | Number of tasks that produced a `WIP(...)` commit. |
| `config.builder_provider` | string | `"claude"`, `"codex"`, or `"opencode"`. The smoke gate requires `"opencode"`. |
| `config.builder_model` | string | When `builder_provider == "opencode"` and the routing target is LM Studio, this MUST start with `"lmstudio/"`. |

## Interpreting smoke-gate failures

`scripts/smoke-local-model.sh` runs six checks in order. When the script
prints `[smoke] FAIL:`, find the failing check below to triage.

**Check 1 -- foundry exit code.**
Failure messages: `foundry hit the <N>s cap -- LM Studio probably stalled` or
`foundry exited with code <rc>`. The first means LM Studio accepted the
request but never finished generating; raise `n_ctx`, pick a smaller / faster
model, or pass `--timeout 1200`. The second means the run errored before
producing output -- inspect `$WORK/stderr.log` (the path is printed) for the
typed error (see check 5) or for a missing-binary message.

**Check 2 -- envelope shape and routing.**
Failure messages: `schema_version == ...`, `config.builder_provider == ...`,
`config.builder_model == ...`, or `out.json has zero tasks recorded`.
`schema_version` mismatch means the JSON envelope changed since this gate was
written -- bump `HEADLESS_REPORT_SCHEMA_VERSION` in `src/app/commands.rs` and
update both this document and `scripts/smoke-local-model.sh`. A
`builder_provider` mismatch means `.foundry.json` did not route through
opencode (most often: `dual_selection` was overridden or `builder_models[0]`
was edited). A `builder_model` that does not start with `lmstudio/` means the
LM Studio model id resolution failed (verify `opencode models lmstudio`
returns a non-empty first line). Zero tasks means the build loop exited
before processing `T1.1` -- inspect stderr for a gate or prerequisite error.

**Check 3 -- log file presence.**
Failure message: `no .buildloop/logs/*.jsonl produced (builder never spawned an agent)`.
The pipeline reached `IMPLEMENT` but the builder agent was never invoked --
usually because a prerequisite gate (`gate_builder` requires
`current-plan.md` with `## File Operations` and `## Verification`) failed.
The smoke script pre-seeds those artifacts; if this check still fails,
verify that the pre-seeded `.buildloop/current-plan.md` was not stripped by
a `git clean` or by a builder rebuild.

**Check 4 -- opencode session marker / Claude leak.**
Failure messages: `no opencode 'sessionID' marker in any log file (opencode never ran)`
or `found Claude stream-json 'subtype:init' in <N> log file(s) -- routing leaked to Claude`.
The first means the spawned agent was opencode but it never emitted a session
event -- check that the `opencode` binary on PATH is current, that LM Studio
is reachable, and that the model loaded in LM Studio appears in
`opencode models lmstudio`. The second means routing fell back to Claude
despite `builder_provider == "opencode"` -- this is the regression that
P32.5 fixed (do NOT silently default `ModelProvider::Claude`); reproduce
locally with `foundry run --no-tui` and verify `Config::for_pipeline` is
applied.

**Check 5 -- typed agent errors.**
Failure message: `typed agent error in stderr.log -- [error/<Kind>] ...`.
Three kinds are detected:
- `ContextOverflow` -- the loaded model's `n_ctx` is too small. Open LM
  Studio, raise `n_ctx` to at least 8192, reload the model, retry.
- `ProviderUnreachable` -- LM Studio is not running on `127.0.0.1:1234` or
  the OpenAI-compatible server is disabled in LM Studio's "Local Server"
  tab. Start LM Studio, enable the local server, retry.
- `ModelNotLoaded` -- LM Studio is reachable but the requested model is not
  loaded. The smoke script picks the first model from `opencode models
  lmstudio`; if that disagrees with what is loaded, load the model in LM
  Studio's UI before retrying.
Each kind is defined in `src/agent.rs:120-143` (`AgentErrorKind`) and
classified by `classify_agent_error` (`src/agent.rs:2314`).

**Check 6 -- QRPBA indicator convention.**
Failure messages: `indicator ... contains legacy 'I'` or `indicator ... contains legacy 'D'`
or `indicator ... missing 'B'`. The pipeline progress indicator written to TASKS.md uses
the QRPBA taxonomy: **Q**uery, **R**esearch, **P**lan, **B**uild, **A**udit. A `-` in
any slot means that stage was skipped. Legacy indicators used SPID (Scout, Plan,
Implement, Verify/Doubt) -- the letters `I` and `D` should never appear. If they do,
the indicator-writing code in `src/app/build.rs` has regressed (see commit `5560b0a`
for the P33.1 fix).

## Empty-diff WIP and idle-timeout behavior

Local models sometimes produce syntactically valid agent output that does not
result in any actual file changes -- the model "talks about" the change without
making it, or produces edits that revert themselves. Two safeguards handle this:

**EmptyDeliverable gate (D2.4).** After the implement stage completes, foundry
diffs the worktree against the last commit. If no real file changes landed (only
whitespace or no diff at all), the task is committed as `WIP(<task-id>):
description` with a typed `EmptyDeliverable` error rather than claiming success
with a `feat(...)` commit. This prevents the audit stage from reviewing a
no-op and reporting a false PASS. The gate is implemented in
`src/app/build.rs` (`commit_as_feat_if_real_changes`).

**Idle timeout (D2.8).** The opencode subprocess is force-killed after
`agent_implement_idle_secs` seconds (default 60) of silence -- no stdout
events from the agent. This catches models that stall mid-generation
(common when `n_ctx` is close to the prompt size). The timeout is
configurable in `.foundry.json`. When triggered, the task is committed as
WIP with an idle-timeout reason. The suppression of opencode's own
lifecycle events (step start/end) ensures the idle timer only resets on
meaningful output, not on heartbeat noise.

**Agent timeout.** The top-level `agent_timeout_secs` (default 600s) controls
the idle timeout for all agents. The hard timeout is 4x the idle timeout
(2400s = 40 min at default). Override in `.foundry.json` or in the Settings
Overlay under Budgets & timeouts.

**Reading the indicator.** After a run, TASKS.md shows each completed task
with a bracketed indicator:
```
- [x] T1.1: Create hello.txt [---B-]
- [x] T1.2: Add tests [QRP+BA]
- [x] T1.3: Stalled model [---B-!]
```
Each character maps to a pipeline stage: Q(uery) R(esearch) P(lan) +(plan
review) B(uild) A(udit). A `-` means the stage was skipped; `!` at the end
means the audit reported failures (the commit was `WIP` not `feat`). The
smoke gate's check 6 asserts `B` is present and no legacy `I`/`D` appears.
See [`docs/progress-indicators.md`](progress-indicators.md) for the full
QRPBA reference and migration notes from the legacy SPID scheme.

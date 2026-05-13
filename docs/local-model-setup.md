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

## Phase 32.1 audit verdict (2026-05-13)

The Phase 32.1 codex audit (artifact: `.buildloop/codex-audit.log`) flagged five
HIGH-severity gaps in local-model routing. T1.38 walked each gap against the
current code, fixed the one real bug, and locked in regression coverage for the
remaining four. The verdict table below records the result so future agents do
not re-open the same gaps.

| Gap | Audit severity | Verdict | Evidence |
|-----|----------------|---------|----------|
| (a) routing-not-all-stages -- `save_builder_routing` only writes `builder_*` keys; need all 8 stages overridden | HIGH | PASS (no code change; covered by tests) | `Config::for_pipeline` (src/config.rs:1497-1588) overrides all 8 stage `*_provider` fields and, when the parsed provider is OpenCode, propagates the model string to all 8 `*_model` fields. Locked in by `for_pipeline_with_opencode_routes_all_eight_stages_to_opencode_and_propagates_model` (LM Studio spec) and the new `for_pipeline_with_opencode_ollama_spec_routes_all_eight_stages_and_propagates_model` (Ollama spec) in src/config.rs. |
| (b) ollama-not-routed -- Ollama selection may not save `builder_provider` correctly | HIGH | PASS (no code change; covered by tests) | `apply_builder_selection` (src/app.rs:269-316) routes both lmstudio and ollama through the same `Config::save_local_model` + `Config::save_builder_routing("opencode", "<lmstudio\|ollama>/<name>")` branch. Locked in by the new `save_builder_routing_persists_ollama_spec_identically_to_lmstudio` test in src/config.rs. |
| (c) hardcoded-claude-fallbacks -- pattern extraction and planner fallback may bypass user selection | HIGH | PASS (no code change) | `src/app/build.rs:7177-7181` gates pattern extraction with `if Config::parse_provider(...) != ModelProvider::Claude { skip }`, so the hardcoded `agent::ModelProvider::Claude` at src/app/build.rs:7312 sits inside `run_pattern_extraction`, which is unreachable when a local model is active. `src/app/planning.rs` uses `Config::parse_provider(&ctx.config.planner_provider)` -- no hardcoded Claude in the build-loop hot path. |
| (d) opencode-event-parsing -- TUI may have no structured progress for opencode runs | HIGH | PASS (no code change) | `parse_opencode_line` (src/agent.rs) and the dispatcher fully parse OpenCode `--format json` events into `AgentOutputEvent::{Text, ToolUse, ToolResult, Stderr, Result, Usage, Error}`. The TODO referenced in the audit is resolved. |
| (e) no-error-surface -- missing opencode / unreachable LM Studio / model not loaded may hang or silently fail | HIGH | FAIL (real bug, fixed in T1.38) | `provider_binary_is_available` previously short-circuited to `true` for every provider whose `uses_pty()` was `false`, which incorrectly included OpenCode. The "opencode binary missing" failure was hidden behind a late PTY spawn error. T1.38 rewrote the function to actually `which opencode` and exempt only GhCopilot (see "What changed" below). The other three failure modes (LM Studio unreachable, model not loaded, context overflow) were already surfaced via the `classify_agent_error` typed-error taxonomy. |

### What changed in T1.38

1. **`provider_binary_is_available` now probes `which opencode`** (src/app/commands.rs:185-204). The function only exempts `ModelProvider::GhCopilot`; all other providers, including `OpenCode`, are now checked via the host's `which` (`where` on Windows). Effect: when `opencode` is not on PATH, `ensure_required_providers_available` reports `required provider CLI not found: opencode (builder)` before the run starts, instead of failing late inside the PTY spawn.
2. **`ModelProvider::uses_pty` was deleted** (src/agent.rs). The helper had a single caller, which was rewritten in change (1) to use `matches!(provider, ModelProvider::GhCopilot)` directly. The helper had no other in-tree callers and no published-API consumers (foundry is a binary, not a library).
3. **New for_pipeline + save_builder_routing parity tests for Ollama specs** (src/config.rs). Both `for_pipeline_with_opencode_ollama_spec_routes_all_eight_stages_and_propagates_model` and `save_builder_routing_persists_ollama_spec_identically_to_lmstudio` assert that an `ollama/<name>` spec produces the same all-eight-stages routing and the same persisted `.foundry.json` shape as the LM Studio counterpart. A regression that drops the `ollama/` prefix or fails to propagate the model to non-builder stages will now fail in CI.
4. **Two new unit tests guarding the run-mode binary gate for OpenCode** (src/app/commands.rs). `opencode_missing_is_reported_in_run_mode_when_builder_provider_is_opencode` confirms that the missing-CLI report flows through `missing_provider_commands` when the closure says OpenCode is unavailable. `opencode_present_passes_run_mode_gate_when_builder_provider_is_opencode` confirms the empty-missing case is reachable when the closure marks OpenCode available.

### Failure-mode taxonomy

| Failure mode | Detection | Surfaced as |
|--------------|-----------|-------------|
| `opencode` missing on PATH | `provider_binary_is_available(OpenCode)` returns `false`; `ensure_required_providers_available` bails before any agent spawn. | `anyhow::Error("required provider CLI not found: opencode (...)")` -- shown to the operator at startup; non-zero exit for `foundry run --no-tui`. |
| LM Studio (or Ollama) unreachable | `classify_agent_error` matches `"connection refused"` / `"failed to connect"` / `"Connection refused"` patterns in the agent stderr stream. | `AgentErrorKind::ProviderUnreachable` -- TUI shows a typed toast; circuit breaker (src/app.rs:4921-4946) aborts the run within ~10 s. |
| Model not loaded | `classify_agent_error` matches `"model not loaded"` / `404 /v1/models` / `model_not_found` patterns. | `AgentErrorKind::ModelNotLoaded` -- typed toast tells the user to load a model. |
| Context overflow | Regex match on `tokens=<N>` / `ctx_size=<N>` / context-overflow phrases in the agent error stream. | `AgentErrorKind::ContextOverflow` -- toast names the actual `tokens` and `ctx_size` and tells the user to raise n_ctx and press R to retry. |

### Known gaps (deferred -- not part of T1.38)

- **GhCopilot binary-availability gate.** `provider_binary_is_available(GhCopilot)` returns `true` unconditionally. GhCopilot depends on the `gh` CLI for OAuth, so an absent `gh` binary will still fail at runtime with no typed startup error. T1.38 is scoped to local-model routing (LM Studio / Ollama / OpenCode); fixing the `gh` gate is a separate concern. Suggested follow-up: probe `gh` via `Command::new(lookup_cmd).arg("gh")` in the GhCopilot branch (or in a new dedicated dependency check).
- **Ollama end-to-end smoke parity.** `scripts/smoke-local-model.sh` is LM-Studio-only by design; per the T1.38 task constraints, the script was not modified. Ollama runtime parity is asserted only at the config-routing layer via the unit tests added in T1.38, not end-to-end against a live `ollama serve`. Suggested follow-up: a separate task to extend the smoke script (or add a sibling `scripts/smoke-ollama-model.sh`) so a regression in ollama-prefix handling surfaces in CI.

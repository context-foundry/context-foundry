# Eval Harness

Context Foundry runs a lightweight eval harness after every task completion.
It grades the run against plumbing-integrity checks (system prompts present,
patterns injected, prior artifacts read) and heuristic outcome checks
(plan covers research, claims include verification results, audit produced
findings). It produces a per-stage badge and a JSON report. It never blocks
the pipeline.

## What it checks

The harness runs 17 checks per run: 8 plumbing + 9 heuristic.

### Plumbing checks (8)

Plumbing checks confirm the orchestrator wired prompts and artifacts through
to each stage correctly. They read from `.buildloop/run-manifest.json`
(orchestrator-recorded) and, for one Claude-only check, from the JSONL
session transcripts in `.buildloop/logs/`.

| Check | Severity | Purpose |
|-------|----------|---------|
| `stage_completed_successfully` | Critical | Manifest invocation status is `Ran`. Fails on `Failed`. Guarantees a crashed stage produces `EVAL ... ✗ ...` even if other checks coincidentally pass. |
| `system_prompt_present` | Critical | Manifest's `system_prompt_bytes > 0`. Hash alone is insufficient because `blake3("")` is non-empty. |
| `model_matches_config` | Standard | `effective_provider`/`effective_model` equals `originally_configured_*` AND `override_reason` is null. Skips when `override_reason` is set. |
| `extension_loaded` | Standard | Manifest's `prompt_extension_names_found` contains every entry in `selected_extension_names`. Skips when no extensions are selected. |
| `patterns_injected` | Standard | Manifest's `prompt_pattern_ids_found` contains every entry in `matched_pattern_ids`. Skips when no patterns matched. |
| `prior_artifact_received` | Critical | Stage N's prompt contains stage N-1's artifact basename (Plan -> `research-report.md`, Build -> `current-plan.md`, Audit -> `build-claims.md`, Research -> `questions.md`). |
| `prior_artifact_read` | Standard, Claude-only | Walks `assistant.message.content[]` in the JSONL for `tool_use` records named `Read` whose `input.file_path` ends in the prior artifact basename. Subagent-issued reads (`parent_tool_use_id` set) count. Skips with evidence "non-Claude provider, transcript adapter not in v1" for Codex / OpenCode / GhCopilot stages. |
| `expected_artifact_written` | Standard | Manifest's `expected_artifact_path` exists on disk with > 200 bytes. Skips when stage status is `Skipped`/`Reused`/`CheckpointResume`. |

### Heuristic checks (9)

Heuristic checks read the artifact files directly. All are provider-agnostic.

| Check | Purpose |
|-------|---------|
| `plan_covers_research_files` | Every file path mentioned in `research-report.md` also appears in `current-plan.md`. |
| `plan_has_verification` | `current-plan.md` has a verification section with at least one command. |
| `plan_has_per_phase_verification` | When `current-plan.md` has 5+ file operations, requires 2+ verification sections (per-phase verification). Fails on horizontal plans (5+ file ops with a single end-block verification). |
| `build_claims_has_files_changed` | `build-claims.md` has `## Files Changed` with at least one `[CREATE\|MODIFY]` line. |
| `build_claims_has_verification_results` | `build-claims.md` has `## Verification Results` with PASS / FAIL / SKIPPED for Build, Tests, Lint. |
| `build_claims_files_exist` | Every path under `## Files Changed` exists on disk. |
| `build_claims_has_gaps_section` | `build-claims.md` has a `## Gaps and Assumptions` section. |
| `audit_engaged` | `review-report.md` markdown contains a fenced ```json block whose object has a non-empty `high`/`medium`/`low` array OR an explicit PASS verdict with rationale. Skips when `audit_skipped_reason` is set. |
| `audit_findings_localized` | When findings exist, every entry in `high`/`medium`/`low` carries a `file` and a `line`. |

## How structured prompt evidence is computed

The orchestrator computes three "found" lists over the FULL assembled prompt
(not the preview) at invocation time and stores them in the manifest entry:

- `prompt_pattern_ids_found` -- substring match against `[<pattern_id>]`
  with the literal square brackets, per the formatter at
  `src/patterns.rs:366`. Bare-substring matching would produce false positives
  on English-word IDs like `simple` or `gates`.
- `prompt_extension_names_found` -- substring match against
  `--- BEGIN EXTENSION CONTEXT: <name> ---`, the wrapper marker injected by
  `src/extensions.rs:192`. Names, not paths -- two extensions in different
  roots (Global vs ProjectLocal) collide on name; precedence resolves to the
  highest-priority source.
- `prompt_artifact_refs_found` -- substring match against the basename of each
  prior artifact path (e.g. `current-plan.md`).

Prompt previews (first 1024 bytes) are diagnostic only and do NOT drive the
checks.

## Where the report and manifest live

| File | Owner | Contents |
|------|-------|----------|
| `.buildloop/run-manifest.json` | Orchestrator | Per-invocation manifest entries: stage_id, role, status, provider/model triple, prompt hashes, prompt-evidence found-lists, log_path, started_at / exit_observed_at. Atomically flushed at every stage transition and at task finalization. |
| `.buildloop/eval-report.json` | Eval harness | `schema_version`, `run_id`, `task_id`, `generated_at`, per-stage scores with each check's status and evidence, aggregate badge, `completion_path`, `notes` array surfacing override and non-Claude scopes. Idempotent (byte-identical re-runs modulo `generated_at`). |
| `.buildloop/logs/<STAGE>-<timestamp>.jsonl` | Agent runner | Claude SDK stream-json transcripts for Claude stages. Non-Claude providers write `studio-<provider>-*.jsonl` instead. |

Both `run-manifest.json` and `eval-report.json` live under `.buildloop/`,
which is gitignored (`.gitignore:28`).

## Vocabularies

### `override_reason`

Stored on each manifest invocation. Open vocabulary. Currently emitted:

- `null` -- no override; `effective_*` matches `originally_configured_*`.
- `"budget_recovery"` -- budget recovery (`src/app/build.rs:3752`,
  `src/app/build.rs:4824`) rewrote the model after the orchestrator built
  the original spec.

When `override_reason` is set, `model_matches_config` Skips with the reason
as evidence and the eval-report `notes` array surfaces the count.

### `skip_reason`

Stored on `Skipped` / `Reused` / `CheckpointResume` invocations. Currently
emitted:

- `"checkpoint_q_research"` -- Q+R reused from a prior session checkpoint
  (`src/app/build.rs:3058`).
- `"simple_task_skip_planner"` -- planner skipped because the task is simple
  (`src/app/build.rs:3034`).
- `"simple_task_skip_doubt"` -- audit skipped because the task is simple
  (`src/app/build.rs:5150`).
- `"batch_deferred_doubt"` -- audit deferred under batch mode
  (`src/app/build.rs:4937`).
- `"confidence_skip_doubt"` -- audit skipped because confidence is high
  (`src/app/build.rs:4971`).
- `"stage_disabled_<id>"` -- stage disabled in `.foundry.json`.
- `"checkpoint_skip_builder"` -- builder skipped because checkpoint resume
  has the artifact already (`src/app/build.rs:4615`).

The vocabulary is open-ended. New skip mechanisms add entries here.

### `actual_provider` / `actual_model`

`effective_*` is what the orchestrator requested. `actual_*` is what
`agent::run_agent` actually ran. The two diverge on the Codex -> Claude
fallback path at `src/agent.rs:989`: AgentResult returns with
`actual_provider: "claude"` and `fallback_reason: Some("codex transport
stall, fell back to claude default")`. `actual_model` may arrive empty;
the eval parser fills it from the JSONL `system/init.model` event before
running checks.

Checks that depend on log format (`prior_artifact_read`) key on
`actual_provider`, not `effective_provider`, so a Codex -> Claude fallback
parses correctly.

## How to read the badge

The status meter renders a single line below the QRPBA pipeline indicator:

```
EVAL Q✓ R✓ P✓ B⚠ A✓
```

Glyphs map per stage:

- `✓` -- all checks pass.
- `⚠` -- any heuristic fail or non-critical plumbing fail.
- `✗` -- any Critical plumbing fail.
- `-` -- stage status is `Skipped`, `Reused`, or `CheckpointResume`.

A Q+R reuse run reads `EVAL Q- R- P✓ B✓ A✓`. A doubt-skip run reads
`EVAL Q✓ R✓ P✓ B✓ A-`. A builder failure reads `EVAL Q✓ R✓ P✓ B✗ A-`.

Stoplight fallback `EVAL ●` renders when the report exists but the terminal
cannot render the per-stage glyphs.

## How to debug a failed check

1. Press `?` in the TUI to open the Settings overlay.
2. Scroll to the "Pipeline Health" section. It auto-expands the first time
   you open it after a fresh run completes.
3. Each stage row lists every check with its status (`PASS` / `FAIL` /
   `SKIP`) and an evidence string explaining why. Failed checks name the
   missing field, the missing artifact basename, or the file:line reason.
4. Fix the root cause in the source (or your pipeline configuration), then
   click "Re-run eval on last run" at the bottom of the section to re-grade
   the existing manifest and logs without re-running the pipeline. The
   report rewrites idempotently (modulo `generated_at`).

## Per-stage aggregation rules

A single stage may have multiple invocations -- planner retry, parallel
builder slots, multipass review (per-file passes plus integration). The
scorer aggregates per stage:

- The worst status across all checks for **non-superseded invocations only**
  determines the badge.
- Retry sets `superseded_by: <retry_id>` on the prior attempt. The scorer
  ignores superseded entries; the overlay still surfaces them as historical
  record so a failed first attempt is visible.
- Multipass review never supersedes -- per-file passes and the integration
  pass all count toward the Audit badge.
- Parallel builder slots all count -- worst-status wins, consistent with
  multipass review.

`Failed` invocations are graded normally; the Critical
`stage_completed_successfully` check guarantees a `Failed` stage produces
`✗`.

## v1 scope and degraded grading

The v1 harness is Claude-focused on transcript parsing. Manifest-based
plumbing checks are provider-agnostic; only `prior_artifact_read` requires
a Claude SDK JSONL transcript.

### Codex stages

Codex / OpenCode / GhCopilot stages still get all manifest plumbing checks
and all heuristic checks. `prior_artifact_read` Skips with evidence
"non-Claude provider, transcript adapter not in v1".

### Codex doubt (`run_codex_doubt`)

`src/app/review.rs:141-285` calls `run_codex_subprocess` twice and never
returns an `AgentResult`. With `DOUBT_ENGINE=codex` documented as the
default, this is the most common audit path.

v1 records a single placeholder Audit invocation with
`actual_provider: "codex"`, `log_path: null`, `parser_skipped: true`, and
the doubt result's status. All transcript-dependent checks Skip;
manifest-only checks (`system_prompt_present`, `model_matches_config`,
`extension_loaded`, `patterns_injected`, `prior_artifact_received`) also
Skip because there is no orchestrator-side prompt assembly to record. The
Audit badge for codex-doubt runs reflects only
`stage_completed_successfully` (Critical) and the heuristic checks against
`review-report.md` (which `run_codex_doubt` does write).

A real Codex transcript adapter is the v2 priority #1.

### Custom-card invocations

`run_custom_card` (`src/app/build.rs:180`) invokes `agent::run_agent` for
`pipeline_stages` entries with `prompt_override`. These produce
`IMPLEMENT-*.jsonl` logs but their stage ID is a user-defined string that
does not fit `StageId { Query, Research, Plan, Build, Audit }`. v1 skips
manifest writes inside `run_custom_card` entirely; the eval run-loader
tolerates orphan `IMPLEMENT-*.jsonl` files with no manifest entry. v2
extends `StageId` with a `Custom(String)` variant.

### Abrupt aborts

`process_task` has 18+ early-return sites. v1 instruments six of them:
post-audit pass, post-audit fail, post-audit-skipped (doubt-trust / batch
/ confidence / config), builder failure, planner failure, doubt skip. Any
other early abort (config-validation errors, panics, abort signals) leaves
the manifest in whatever state the last flush wrote, produces no
eval-report on this run, and the TUI renders no badge -- consistent with
the "best-effort, never blocks" invariant.

## v2 roadmap

- Provider-specific transcript adapters. Codex first (most common doubt
  engine), then OpenCode, then GhCopilot.
- Custom-card support via `StageId::Custom(String)`.
- Golden tasks: a fixed set of regression tasks the harness can replay.
- LLM-as-judge for the heuristic layer.
- Regression tracking across runs.
- Per-model A/B and pattern-effectiveness scoring.
- Cost-adjusted score.
- Per-stage live scoring (currently report runs at task finalization).

## Related docs

- [Settings Overlay](settings-overlay.md) -- the `?` modal that exposes
  Pipeline Health and the "Re-run eval on last run" action.
- [Per-stage routing](per-stage-routing.md) -- how `effective_provider` /
  `effective_model` are resolved.
- [Progress indicators](progress-indicators.md) -- the QRPBA letters in
  `TASKS.md` are the durable summary; the EVAL badge is the per-run detail.
- [PLAN_eval-harness.md](PLAN_eval-harness.md) -- v8 design spec, including
  the run-manifest schema and architecture decisions.

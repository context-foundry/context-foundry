# Plan: Eval Harness for Context Foundry
Date: 2026-05-07
Version: v8 (revised after seventh audit; scope cut applied)
Status: planning

> **Note (2026-05-12):** This plan was written before the v3.3.0 rename. Symbol
> references below say `src/extensions.rs`, `wrap_with_extensions()`, and
> `BEGIN/END EXTENSION CONTEXT`; the live equivalents are `src/plugins.rs`,
> `wrap_with_plugins()`, and `BEGIN/END PLUGIN CONTEXT`. Line numbers cited are
> pre-rename and have shifted.

## Revision history

- **v1** -- assumed prompts could be reconstructed from JSONL.
- **v2** -- introduced `.buildloop/run-manifest.json`; per-stage Check API; renamed schema-aligned heuristic checks; finalization hook; stage canonicalization; OverlayRow variants.
- **v3** -- structured prompt evidence (`prompt_*_found`); in-memory manifest with atomic flush; `originally_configured_*`/`effective_*`/`override_reason` for model drift; reviewer fenced-JSON-in-markdown parsing; blake3 hashing; broadened IO scope; heuristic count corrected to eight.
- **v4** (post-audit-3): Extensions matched by name via `BEGIN EXTENSION CONTEXT:` marker. Manifest writes orchestrator-level via `PromptEvidenceSpec`. First-class `StageStatus`. v1 parser scoped Claude-only.
- **v5** (post-audit-4): `AgentResult.log_path`; `system_prompt_bytes` (blake3-empty trap); `StageInvocationId`; Failed graded with new Critical `stage_completed_successfully` check; eight plumbing checks.
- **v6** (post-audit-5): AgentResult provider provenance (`actual_provider`/`actual_model`/`fallback_reason`); retry supersession; Research -> questions.md; `Arc<Mutex<RunManifest>>` for parallel slots; eight plumbing checks.
- **v7** (post-audit-6): `AgentResult.log_path: Option<PathBuf>`; `StageId` serde rename to pipeline slugs; `actual_model` fill-in from JSONL.
- **v8** (this version, post-audit-7): Scope cut + fixes. **Out of v1 scope** (with explicit risk notes, deferred to v2): codex-doubt path (`src/app/review.rs:141-285` calls `run_codex_subprocess` twice and never returns an `AgentResult`; v1 records a single placeholder Audit entry with `log_path: None, parser_skipped: true, actual_provider: "codex"` and Skips all transcript-dependent checks); custom-card invocations (`run_custom_card` at `build.rs:180` with arbitrary `pipeline_stages` IDs that don't fit `StageId`; v1 skips these entirely with no manifest write). **Mechanical fixes**: (1) phantom "Fixer in review.rs" wiring site removed -- `AgentRole::Fixer` exists in the enum but is never invoked (per comment at `review.rs:546`). (2) Single-pass reviewer site added at `src/app/review.rs:605` (the default path for small changesets). (3) `AgentResult` constructor handling stated as a rule, not per-site enumeration: any constructor before its log path is created sets `log_path: None`; any constructor after sets `log_path: Some(...)`; this covers the ten ghcopilot.rs sites and the additional agent.rs sites at `:917, 1228, 1315, 1375, 1597`. (4) Codex->Claude fallback at `agent.rs:989` now specifies the post-await mutation pattern explicitly (`let mut r = Box::pin(...).await?; r.fallback_reason = Some(...); r.actual_provider = "claude"; return Ok(r);`) so the inner Claude AgentResult gets the fallback fields the outer caller intends. (5) `Some(result.log_path)` wording fixed -- `log_path` is already `Option<PathBuf>`, so the call is `log_path: result.log_path.clone()` (no `Some(...)` wrapper). (6) `Mutex` qualified as `std::sync::Mutex`; explicit warning that the guard must never be held across an `await`. (7) `prior_artifact_read` rule specified: parser walks `assistant.message.content[]` for `tool_use` items, matches by basename suffix on `tool_use.input.file_path`, subagent-issued reads (`parent_tool_use_id != null`) count. (8) `prompt_pattern_ids_found` anchors on `[<pattern_id>]` brackets per the formatter at `patterns.rs:366`, not bare substring. (9) Stale `Q->questions.md` clause removed from TASKS.md. (10) Scout/Research disambiguation: manifest entries are keyed by `(invocation_id)`; both Scout and Research map to `stage_id: "research"` in JSON; the `role` field disambiguates. (11) Citation precision: extension wrapper marker is at `src/extensions.rs:192`. (12) Task finalization: v1 instruments the six known completion paths (post-audit pass/fail/skipped, builder failure, planner failure, doubt skip); abrupt config aborts produce no eval-report and the TUI gracefully renders no badge.

## Context

Context Foundry orchestrates five agents (Query, Research, Plan, Build, Audit) with extension injection, pattern injection, per-stage system directives, multiple providers (Claude / Codex / OpenCode / GhCopilot / Codex-doubt), and conditional skip/reuse paths driven by complexity, checkpoints, batching, and confidence. There is no automated way to verify that the plumbing of a real run worked: did each agent receive a non-empty system prompt, did the planner load the matched patterns, did the builder read the research-report, did the auditor read the build-claims, did skipped stages skip for the right reason. Plumbing failures degrade output silently.

This plan adds a live, score-based eval harness that runs after every real foundry run, grades the run against plumbing and heuristic-outcome checks, and surfaces a per-stage badge in the TUI status meter plus a full breakdown inside the Settings overlay. It never blocks the pipeline.

The harness is a pure function of three sources of truth:
1. `.buildloop/run-manifest.json` -- orchestrator-owned, in-memory, atomically flushed.
2. `.buildloop/logs/<STAGE>-<timestamp>.jsonl` -- Claude SDK session transcripts for Claude stages only.
3. Stage artifact files in `.buildloop/`.

A roadmap to a richer "thorough" version (golden tasks, LLM-as-judge, regression tracking, provider transcript adapters) is sketched at the end. v1 is plumbing checks plus a heuristic outcome layer.

## Current State (verified, all rounds)

- Prompts pass via CLI args (`-p`, `--append-system-prompt`) at `src/agent.rs:1143-1163`. JSONL never carries them.
- Patterns are appended at the END of the planner prompt as a `--- BEGIN REFERENCE DATA ---` block (`src/prompts.rs:333-345`); reviewer's `build-claims.md` reference trails large diff text (`src/prompts.rs:827`). Short prompt previews are not load-bearing.
- Extension wrapper at `src/extensions.rs:192`: emits `--- BEGIN EXTENSION CONTEXT: {name} ---\n{content}\n--- END EXTENSION CONTEXT: {name} ---`. **Name appears in prompt, path does not.**
- Builder claims schema is `## Files Changed` / `## Verification Results` / `## Claims` / `## Gaps and Assumptions` (`src/prompts.rs:592-610`).
- Reviewer schema is markdown with fenced JSON object containing `high`/`medium`/`low` arrays (`src/prompts.rs:941`).
- Effective model drifts from configured via budget recovery (`src/app/build.rs:3752, 4824`).
- Audit can be skipped (`src/app/build.rs:4937, 4971, 5150`).
- Four distinct skip mechanisms: planner skip (`build.rs:3034`), Q+R reuse from checkpoint or simple-task (`build.rs:3058`), builder skip (`build.rs:4615`), doubt skip (`build.rs:5162`).
- Stage display strings: SCOUT, QUERY, RESEARCH, PLAN, IMPLEMENT, VERIFY (Reviewer + Fixer share VERIFY), P+, DISCOVERY (`src/agent.rs:32-46`). Legacy filenames: PLANNER, BUILDER, REVIEWER, FIXER.
- Multi-provider runtime: Claude PTY + stream JSON (default), Codex (`agent.rs:956`), OpenCode (`agent.rs:1022`), GhCopilot (`agent.rs:1044`), Codex-as-doubt (`src/app/review.rs:480`). Each provider has its own log shape; only Claude SDK JSONL is well-known.
- `run_agent` signature at `src/agent.rs:932`: `(role, provider, model, prompt, project_dir, output_tx, log_dir, allowed_tools, timeout_secs, shutdown, config_override)` -- does NOT carry matched_pattern_ids, original-configured routing, override_reason, or expected artifact path. The orchestrator at `build.rs:4811` already has all of those.
- Settings overlay renders config `SectionDef`/`FieldDef` rows only (`src/app/state.rs:369`, `src/tui/overlays.rs:1101`).
- Extensions discovered from Global / Ancestor / ProjectLocal per `src/extensions.rs:33`.
- `blake3 = "1"` at `Cargo.toml:26`.

What does NOT exist:
- Any per-run manifest.
- Any post-run quality grading.
- Any "Pipeline Health" surface in the TUI.

## Implementation Steps

- [ ] **0. Run manifest infrastructure (`src/run_manifest.rs`).** New `RunManifest` struct + `ManifestHandle` (single in-memory owner, owned by the orchestrator). Schema below. Atomic flush (`.tmp` + rename) at each stage transition and at task finalization. Best-effort writes (`let _ = ...`).

  Public API (orchestrator-only writers):
  ```rust
  pub struct StageInvocationId(u64);  // opaque, monotonic per run

  pub struct PromptEvidenceSpec<'a> {
      pub stage_id: StageId,
      pub role: AgentRole,
      pub expected_artifact_path: Option<PathBuf>,
      pub originally_configured_provider: String,
      pub originally_configured_model: String,
      pub effective_provider: String,
      pub effective_model: String,
      pub override_reason: Option<String>,
      pub system_prompt: &'a str,
      pub user_prompt: &'a str,
      pub matched_pattern_ids: Vec<String>,
      pub selected_extension_names: Vec<String>,
      pub prior_artifact_paths: Vec<PathBuf>,  // basenames the harness will look for
  }

  impl ManifestHandle {
      pub fn record_invocation(&self, spec: PromptEvidenceSpec) -> StageInvocationId;
      pub fn record_exit(&self, id: StageInvocationId, status: StageStatus, exit_observed_at: DateTime<Utc>, exit_info: AgentExitInfo);
      pub fn record_skip(&self, stage_id: StageId, role: AgentRole, status: StageStatus, skip_reason: String, artifact_source: Option<ArtifactSource>) -> StageInvocationId;
      pub fn mark_superseded(&self, prior_id: StageInvocationId, by_id: StageInvocationId);
      pub fn record_completion(&self, completion_path: CompletionPath);
      pub fn flush(&self) -> Result<()>;
  }

  pub struct AgentExitInfo {
      pub log_path: Option<PathBuf>,
      pub actual_provider: String,
      pub actual_model: String,         // may be "" on Codex->Claude fallback; eval parser fills from JSONL system/init
      pub fallback_reason: Option<String>,
  }
  ```
  `AgentResult` carries the same shape (also `Option<PathBuf>` for `log_path`); the orchestrator copies the four fields into `AgentExitInfo` when calling `record_exit`. Early-return error paths (GhCopilot auth failure at `ghcopilot.rs:747-754`, sandbox rejection at `agent.rs:1050-1057`) construct AgentResult with `log_path: None`.
  `ManifestHandle` is internally `Arc<Mutex<RunManifest>>` so it can be cloned cheaply and used from parallel builder slots (`src/app/build.rs:1185`) without contention -- writes are brief and infrequent. All methods take `&self`.
  `record_invocation` returns a fresh `StageInvocationId` (monotonic counter scoped to the run). The orchestrator holds the ID and passes it back to `record_exit` along with the `log_path` it received from `AgentResult`. `record_skip` also returns an ID for symmetry. Same-role multiple invocations (planner retry, multipass review) get distinct IDs and distinct manifest entries.

  `record_invocation` computes:
  - `system_prompt_hash` (`blake3:<hex>`) and `system_prompt_bytes: usize` (raw byte length, NOT hash length -- protects against the `blake3("")` non-empty-hash trap).
  - `user_prompt_hash` and `user_prompt_bytes`.
  - `system_prompt_preview` and `user_prompt_preview` (first 1024 bytes, diagnostic only).
  - Structured prompt evidence over the FULL `user_prompt`:
    - `prompt_pattern_ids_found`: substring match against each `matched_pattern_ids` entry.
    - `prompt_artifact_refs_found`: substring match against each `prior_artifact_paths` basename.
    - `prompt_extension_names_found`: substring match against `--- BEGIN EXTENSION CONTEXT: {name} ---` for each `selected_extension_names` entry.

- [ ] **1. Orchestrator integration in `src/app/build.rs` and `src/app/review.rs`.** Minimal `src/agent.rs` and `src/ghcopilot.rs` changes: add four fields to `AgentResult` -- `log_path: Option<PathBuf>`, `actual_provider: String`, `actual_model: String`, `fallback_reason: Option<String>`.

  **Field-assignment rule** (covers all `AgentResult` constructors, including the ten in `ghcopilot.rs` at `:747, 815, 830, 858, 869, 916, 946, 956, 1010, 1042` and the agent.rs sites at `:917, 1228, 1315, 1375, 1597`): any constructor that runs **before** its function's log path has been initialized sets `log_path: None`; any constructor at or after the path-init line sets `log_path: Some(log_path.clone())`. Default the provider fields to `actual_provider = effective_provider`, `actual_model = effective_model`, `fallback_reason: None`. All existing AgentResult tests must be updated.

  **Codex->Claude fallback at `agent.rs:989`** is the only site that needs explicit post-await mutation. Change the existing `return Box::pin(run_agent(...)).await` to:
  ```rust
  let mut r = Box::pin(run_agent(/* ModelProvider::Claude, "" */)).await?;
  r.actual_provider = "claude".to_string();
  // r.actual_model stays "" -- Claude SDK picked default; eval parser fills from JSONL system/init
  r.fallback_reason = Some("codex transport stall, fell back to claude default".to_string());
  return Ok(r);
  ```
  This is a behavior-preserving structural change: the recursive call still happens, the AgentResult is still returned; only the four new fields differ.

  **Wire `ManifestHandle` (`Arc<std::sync::Mutex<RunManifest>>`) through `RunContext`.** Clone for parallel builder slots at `build.rs:1185`. **The mutex guard must never be held across an `await`** -- acquire the lock, mutate, drop the guard before any async call. `flush()` is synchronous file IO inside the lock; brief and acceptable.

  **Integration sites** (build a `PromptEvidenceSpec`, call `record_invocation` BEFORE `agent::run_agent`, capture `StageInvocationId`, then `record_exit(id, status, now, AgentExitInfo { log_path: result.log_path.clone(), actual_provider: result.actual_provider.clone(), actual_model: result.actual_model.clone(), fallback_reason: result.fallback_reason.clone() })` after):
  - planner ~`build.rs:3034`
  - planner retry `build.rs:4097` (also call `mark_superseded(first_planner_id, by: retry_id)`)
  - builder regular ~`build.rs:4811`
  - builder parallel slot `build.rs:1185`
  - reviewer single-pass `review.rs:605` (default for changesets at or below `review_multipass_threshold`)
  - reviewer per-file multipass `review.rs:886`
  - reviewer integration multipass `review.rs:1017`
  - scout / query / research / discovery sites

  Status is `Ran` on success, `Failed` on error. (`AgentRole::Fixer` is in the enum but never invoked -- per the comment at `review.rs:546`, the reviewer audits AND fixes; no separate fixer agent. No wiring needed.)

  At the planner retry site (`build.rs:4097`): after `record_invocation` for the retry returns its ID, call `mark_superseded(first_planner_id, by: retry_id)`. The first attempt becomes informational; aggregation considers only the retry's status.

  At each skip/reuse path (planner skip ~`build.rs:3034`, Q+R reuse ~`build.rs:3058`, builder skip ~`build.rs:4615`, doubt skip ~`build.rs:5162`), call `record_skip` with the appropriate `StageStatus` and `skip_reason`. At task finalization, call `record_completion(completion_path)` and `flush`.

- [ ] **2. JSONL parser, Claude-only (`src/eval/parser.rs`).** `StageTranscript { stage_id, log_path, model_from_init, tools_from_init, tool_uses, tool_results, assistant_messages, exit_observed }`. `parse_stage_log(path) -> Result<StageTranscript>`. Resilient to malformed lines. v1 only handles Claude SDK JSONL; non-Claude logs return `StageTranscript { tool_uses: vec![], ... }` with a `parser_skipped: true` flag so checks can Skip cleanly.

- [ ] **3. Run loader (`src/eval/run.rs`).** `RunTranscripts { manifest, stages }`. `latest_run() -> Result<RunTranscripts>` reads `.buildloop/run-manifest.json` and loads each stage's JSONL by the path the manifest records. Stages with `StageStatus::Skipped|Reused|CheckpointResume` have no log to parse; `stages` includes a stub transcript with `parser_skipped: true`.

- [ ] **4. Stage canonicalization (`src/eval/stage_id.rs`).** Enum reads as QRPBA badges, serializes to existing pipeline slugs:
  ```rust
  #[derive(Serialize, Deserialize)]
  #[serde(rename_all = "lowercase")]
  pub enum StageId {
      Query,
      Research,
      Plan,
      #[serde(rename = "implement")]
      Build,
      #[serde(rename = "doubt")]
      Audit,
  }
  ```
  Manifest JSON, eval-report JSON, and verification examples ALL use the serialized form (`query`, `research`, `plan`, `implement`, `doubt`) -- aligned with `src/agent.rs:48-64` slugs and the existing pipeline_stage_enabled/stage_overrides config keys. Internal Rust code uses the enum names. `from_log_prefix(&str)` and `from_role(AgentRole)` handle current and legacy display strings (SCOUT, QUERY, RESEARCH, PLAN, IMPLEMENT, VERIFY, P+, DISCOVERY + legacy PLANNER, BUILDER, REVIEWER, FIXER). Audit accumulates Reviewer + Fixer. Hard-coded canonical prior-artifact map: Research -> `.buildloop/questions.md` (per `src/prompts.rs:279`), Plan -> `.buildloop/research-report.md`, Build -> `.buildloop/current-plan.md`, Audit -> `.buildloop/build-claims.md`. Query has no prior artifact (first stage).

- [ ] **5. Check registry (`src/eval/checks/mod.rs`).**
  ```rust
  trait Check {
      fn name(&self) -> &str;
      fn category(&self) -> Category;       // Plumbing | Heuristic
      fn severity(&self) -> Severity;       // Critical | Standard
      fn applies_to(&self) -> &[StageId];
      fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult>;
  }
  struct StageCheckResult { stage: StageId, status: Status, evidence: String }
  enum Status { Pass, Fail, Skip }
  ```
  Check skip rule: checks **Skip with evidence** when the invocation's `status` is `Skipped|Reused|CheckpointResume`. Checks **grade normally** when status is `Ran` or `Failed`. `Failed` invocations additionally fail the new Critical `stage_completed_successfully` check (see plumbing list), guaranteeing `✗` regardless of which other checks coincidentally pass.

  Per-stage aggregation: each stage may have multiple invocations (planner retry, multipass review). The scorer aggregates per stage by taking the worst status across all checks for **non-superseded invocations only**. Invocations with `superseded_by: Some(_)` are reported in the overlay (so the failed first attempt is visible) but do not contribute to the badge. Multipass review never sets `superseded_by` -- all per-file passes and the integration pass count toward stage status.

- [ ] **6. Eight plumbing checks (`src/eval/checks/plumbing.rs`).** Provider-agnostic except where noted:
  - `stage_completed_successfully` (Critical) -- manifest invocation's `status` is `Ran`. Fails on `Failed`. (Skip rule does not apply: this check is the reason `Failed` produces `✗` even when other checks coincidentally pass on a stage that crashed early.)
  - `system_prompt_present` (Critical) -- manifest's `system_prompt_bytes > 0`. Hash alone is insufficient because `blake3("")` is well-defined and non-empty.
  - `model_matches_config` -- pass if `effective_*` equals `originally_configured_*` AND `override_reason` is null. Skip when `override_reason` is set; evidence names the reason. Eval-report `notes` array surfaces the count.
  - `extension_loaded` -- check manifest's `prompt_extension_names_found` contains every entry from `selected_extension_names`. Skip if `selected_extension_names` is empty. Matches against the `BEGIN EXTENSION CONTEXT: {name}` marker injected by `src/extensions.rs:192`, NOT against absolute paths.
  - `patterns_injected` -- check manifest's `prompt_pattern_ids_found` contains every entry from `matched_pattern_ids`. Skip if no patterns matched. **The found-list is computed by matching `[<pattern_id>]` (with brackets) per the formatter at `src/patterns.rs:366`, NOT bare substring** -- otherwise English-word IDs like `simple` or `gates` produce false positives from unrelated prose.
  - `prior_artifact_received` (Critical) -- check manifest's `prompt_artifact_refs_found` contains stage N-1's artifact basename for stage N.
  - `prior_artifact_read` (Standard, **Claude-only**) -- the parser walks `assistant.message.content[]` items in the JSONL for `tool_use` records with `name == "Read"`. The check passes if any such record has `input.file_path` ending in the prior artifact's basename (e.g., `current-plan.md`). Subagent-issued reads (records carrying `parent_tool_use_id`) count -- the parent agent invoked Read transitively. Skip with evidence "non-Claude provider, transcript adapter not in v1" when `actual_provider != "claude"` or `parser_skipped == true`. Keys on `actual_provider`, not `effective_provider`, so Codex->Claude fallback parses correctly.
  - `expected_artifact_written` -- manifest's `expected_artifact_path` exists on disk with > 200 bytes. Skip if the stage status is `Skipped|Reused|CheckpointResume`.

- [ ] **7. Eight heuristic checks (`src/eval/checks/heuristic.rs`).** All provider-agnostic (operate on artifacts, not transcripts):
  - `plan_covers_research_files` -- every file path in `research-report.md` appears in `current-plan.md`.
  - `plan_has_verification` -- `current-plan.md` has a verification section with at least one command.
  - `build_claims_has_files_changed` -- `## Files Changed` with at least one `[CREATE|MODIFY]` line.
  - `build_claims_has_verification_results` -- `## Verification Results` with PASS/FAIL/SKIPPED for Build, Tests, Lint.
  - `build_claims_files_exist` -- every path under `## Files Changed` exists on disk.
  - `build_claims_has_gaps_section` -- `## Gaps and Assumptions` is present.
  - `audit_engaged` -- parse `review-report.md` markdown, locate the fenced ```json block, parse the inner object, confirm at least one of `high`/`medium`/`low` is non-empty OR the verdict is explicit PASS with rationale. Skip if `audit_skipped_reason` is set.
  - `audit_findings_localized` -- when findings exist, each entry in `high`/`medium`/`low` has `file` and `line`.

- [ ] **8. Scorer (`src/eval/scorer.rs`).** Aggregate per stage. `✓` all pass, `⚠` any heuristic fail or non-critical plumbing fail, `✗` any Critical plumbing fail, `-` stage status is `Skipped|Reused|CheckpointResume` per manifest. Aggregate badge: `EVAL Q✓R✓P✓B⚠A✓` or `EVAL Q-R-P✓B✓A✓` (Q+R reused).

- [ ] **9. Report writer (`src/eval/report.rs`).** Write `.buildloop/eval-report.json` with `schema_version`, `run_id`, `task_id`, `generated_at`, per-stage scores (including stage status + skip_reason + artifact_source), every check's status + evidence, aggregate badge, manifest's `completion_path`, `notes` array (overrides + non-Claude stages). Idempotent.

- [ ] **10. Pipeline finalization hook.** `eval::run_for_current_task()` is called from `src/app/build.rs` at all task-completion paths. Best-effort. Single call site at task-completion is preferred.

- [ ] **11. TUI status meter.** Add an `EVAL` line below the QRPBA line. Locate via `grep -rn "QRPBA" src/tui/` during Research. Render badges from `eval-report.json`. Graceful degradation on missing report.

- [ ] **12. Settings overlay -- new row variants.**
  ```rust
  enum OverlayRow {
      Field(FieldDef),         // existing
      ReportLine(String),      // new
      ActionButton(Action),    // new
  }
  ```
  Add a "Pipeline Health" section after the routing/model section. Collapsed by default; auto-expands the first time it is opened after a fresh run completes. Per-stage rows; "re-run eval on last run" action button at the bottom.

- [ ] **13. Documentation.** Create `docs/eval-harness.md`. Cross-link from README, `docs/settings-overlay.md`, project root `CLAUDE.md`. Add `.gitignore` lines for `.buildloop/eval-report.json` and `.buildloop/run-manifest.json`.

- [ ] **14. Verification** -- see Verification section.

## Run Manifest

```json
{
  "schema_version": 1,
  "run_id": "2026-05-07T14-32-08-T1.1",
  "task_id": "T1.1",
  "started_at": "2026-05-07T14:32:08Z",
  "finished_at": "2026-05-07T14:48:51Z",
  "completion_path": "audit_pass",
  "config_snapshot": { "stage_overrides": [], "agent_timeout_secs": 600 },
  "audit_skipped_reason": null,
  "invocations": [
    {
      "invocation_id": 1,
      "stage_id": "research",
      "role": "Research",
      "status": "reused",
      "skip_reason": "Checkpoint: reusing questions + research from previous session",
      "artifact_source": "checkpoint",
      "log_path": null,
      "expected_artifact_path": ".buildloop/research-report.md"
    },
    {
      "invocation_id": 2,
      "stage_id": "plan",
      "role": "Planner",
      "status": "failed",
      "superseded_by": 3,
      "skip_reason": null,
      "artifact_source": "this_run",
      "log_path": ".buildloop/logs/PLAN-20260507-143215.jsonl",
      "expected_artifact_path": ".buildloop/current-plan.md",
      "originally_configured_provider": "claude",
      "originally_configured_model": "claude-opus-4-7",
      "effective_provider": "claude",
      "effective_model": "claude-opus-4-7",
      "actual_provider": "claude",
      "actual_model": "claude-opus-4-7",
      "fallback_reason": null,
      "override_reason": null,
      "system_prompt_hash": "blake3:abc123...",
      "system_prompt_bytes": 4096,
      "user_prompt_hash": "blake3:def456...",
      "user_prompt_bytes": 18432,
      "matched_pattern_ids": ["pat_002", "pat_017"],
      "selected_extension_names": ["recon"],
      "prompt_pattern_ids_found": ["pat_002", "pat_017"],
      "prompt_artifact_refs_found": ["research-report.md"],
      "prompt_extension_names_found": ["recon"],
      "started_at": "2026-05-07T14:32:15Z",
      "exit_status": "gate_failed",
      "exit_observed_at": "2026-05-07T14:35:42Z"
    },
    {
      "invocation_id": 3,
      "stage_id": "plan",
      "role": "Planner",
      "status": "ran",
      "superseded_by": null,
      "skip_reason": null,
      "artifact_source": "this_run",
      "log_path": ".buildloop/logs/PLAN-20260507-143612.jsonl",
      "expected_artifact_path": ".buildloop/current-plan.md",
      "actual_provider": "claude",
      "actual_model": "claude-opus-4-7",
      "fallback_reason": null,
      "started_at": "2026-05-07T14:36:12Z",
      "exit_status": "ok",
      "exit_observed_at": "2026-05-07T14:38:01Z"
    }
  ]
}
```

`status`: `ran` | `skipped` | `reused` | `checkpoint_resume` | `failed`. Reused/skipped/checkpoint_resume have null `log_path` and null prompt hashes; their checks all Skip.

`artifact_source`: `this_run` | `checkpoint` | `previous_run` (when reusing a checkpoint or a stage that completed earlier in the same run cluster).

`override_reason`: null normally; `"budget_recovery"` when budget recovery rewrites the model. Open vocabulary; document in `docs/eval-harness.md`.

`selected_extension_names`: extension names (e.g. `"recon"`), not paths. The wrapper at `src/extensions.rs:192` injects `--- BEGIN EXTENSION CONTEXT: {name} ---`; the name is what the harness can find in the prompt.

`prompt_*_found` are computed at invocation time over the FULL assembled prompt; previews are diagnostic only.

`actual_model` may arrive empty from `AgentResult` on the Codex->Claude fallback path (`agent.rs:989` invokes Claude with an empty model string, letting the Claude SDK pick a default). When `actual_model == ""` AND a `log_path` exists, the eval parser fills the manifest's `actual_model` from the JSONL `system/init.model` event before running checks. If the log is missing or malformed, `actual_model` stays empty and `model_matches_config` Skips with evidence "actual model unknown (no JSONL system/init)".

## Architecture Decisions

- **Orchestrator owns the manifest.** All writes go through `ManifestHandle`. `src/agent.rs` receives only minimal structural changes (four new fields on `AgentResult`, no signatures, no behavior). The orchestrator at `src/app/build.rs:4811` and `src/app/review.rs` already has the matched patterns, originally-configured routing, override_reason, expected artifact -- the agent does not.
- **Manifest, not log mining.** Prompts cannot be reconstructed from JSONL alone.
- **Structured prompt evidence, not preview greps.** Computed over the FULL prompt at invocation time; previews stay only as diagnostic evidence.
- **In-memory manifest, atomic flush.** Single owner. No file-based read-modify-write. Prevents lost updates under multipass review and dual-pipeline.
- **First-class stage status.** `StageStatus { Ran, Skipped, Reused, CheckpointResume, Failed }` with `skip_reason` and `artifact_source`. Models the four skip paths at `build.rs:3034, 3058, 4615, 5162`. Checks Skip on `Skipped|Reused|CheckpointResume` only; `Ran` and `Failed` are graded; the Critical `stage_completed_successfully` check ensures `Failed` produces `✗`.
- **Provider scope: Claude-only JSONL parsing in v1.** Codex / OpenCode / GhCopilot / Codex-doubt stages still get manifest-based plumbing checks; only `prior_artifact_read` Skips with a "transcript adapter not in v1" evidence string. Provider transcript adapters are v2 roadmap.
- **Per-invocation manifest entries with supersession.** Same role can fire repeatedly within one stage. Each invocation gets a `StageInvocationId` and its own manifest entry. Retries set `superseded_by` on the prior attempt via `mark_superseded`. The scorer aggregates per stage by worst-status across **non-superseded** invocations only; superseded entries appear in the overlay as historical record. Multipass review never supersedes -- all passes count.
- **Concurrency.** `ManifestHandle = Arc<std::sync::Mutex<RunManifest>>`. Cloned for parallel builder slots (`build.rs:1185`). Writes are brief and infrequent; lock contention is negligible. The mutex guard MUST never be held across an `await` -- this is a tokio footgun that can deadlock the runtime. Acquire, mutate, drop the guard, then call any async code. `flush()` is synchronous file IO inside the lock; brief and acceptable.
- **Task finalization mechanism.** `process_task` has 18+ early-return sites. v1 explicitly instruments six of them: post-audit pass, post-audit fail, post-audit-skipped (doubt-trust / batch / confidence / config), builder failure, planner failure, and the doubt skip path. At each, `record_completion(...)` + `flush` + `let _ = eval::run_for_current_task(...)`. Any other early abort (config-validation errors, panics, abort signals) leaves the manifest in whatever state the last flush wrote, produces no eval-report on this run, and the TUI renders no badge -- consistent with the "best-effort, never blocks" invariant. A v2 refactor could route all returns through a Drop guard or inner-function pattern.
- **Effective vs actual provider.** `effective_*` is what the orchestrator requested. `actual_*` is what `agent::run_agent` actually ran (may differ on Codex->Claude fallback at `agent.rs:989`). Checks that depend on log format (`prior_artifact_read`) key on `actual_provider`. Fallbacks surface in the eval-report `notes` array.
- **`Failed` is graded, not skipped.** Skip propagation only applies to `Skipped|Reused|CheckpointResume`. The Critical `stage_completed_successfully` check guarantees that a failed stage produces `✗`.
- **`AgentResult` provider/log provenance.** Log paths are timestamp-generated inside `agent.rs`/`ghcopilot.rs` and use a `studio-{provider}-` prefix for non-Claude; the orchestrator cannot precompute them. AgentResult gains four fields: `log_path: Option<PathBuf>` (None on early-return failure paths), `actual_provider`, `actual_model` (may be "" until eval parser fills from JSONL system/init on Codex->Claude fallback), `fallback_reason`. No signatures change; no behavior changes.
- **Per-stage check API.**
- **Hook at task finalization.**
- **Three-field model record.** `originally_configured_*` + `effective_*` + `override_reason`.
- **Score, never block.**
- **Severity tiers.**
- **Idempotent re-eval.**
- **New overlay row variants.**

## Risks & Open Questions

- **Extension name uniqueness.** Two extensions with the same name in different roots (Global vs ProjectLocal) collide. `src/extensions.rs:33` resolves precedence (highest-priority source wins); the manifest stores the resolved name. Document the precedence rule in `docs/eval-harness.md`.
- **`prior_artifact_paths` accuracy.** The orchestrator must know which prior artifact is canonical for each stage (planner reads research-report.md; builder reads current-plan.md; reviewer reads build-claims.md). Hard-code this map in `src/eval/stage_id.rs` rather than re-deriving at eval time.
- **Reviewer JSON parsing.** Confirm the writer never emits multiple ```json fences or wraps the block in extra formatting. Done during Research.
- **Skip-reason vocabulary.** Document the strings: `"checkpoint_q_research"`, `"simple_task_skip_planner"`, `"simple_task_skip_doubt"`, `"batch_deferred_doubt"`, `"confidence_skip_doubt"`, `"stage_disabled_<id>"`, `"checkpoint_skip_builder"`. Open-ended.
- **Provider transcript adapters.** v1 explicitly Skips `prior_artifact_read` for non-Claude. If non-Claude becomes the dominant configuration, this is a v2 priority -- start with a Codex adapter (since Foundry's doubt-engine codex path is most common).
- **Codex-doubt is grading-degraded in v1.** `run_codex_doubt` (`src/app/review.rs:141-285`) calls `run_codex_subprocess` twice and never produces an `AgentResult`. With `DOUBT_ENGINE=codex` documented as the default in `CLAUDE.md`, this is the most common audit path. v1 records a single placeholder Audit invocation with `actual_provider: "codex"`, `log_path: None`, `parser_skipped: true`, status from the doubt result; all transcript-dependent checks (`prior_artifact_read`) Skip; manifest-only checks (`system_prompt_present`, `model_matches_config`, etc.) also Skip because there's no orchestrator-side prompt assembly to record. The Audit badge for codex-doubt runs reflects only `stage_completed_successfully` (Critical) and the heuristic-outcome checks against `review-report.md` (which `run_codex_doubt` does write). Document this in `docs/eval-harness.md`. Building a real codex adapter is v2 priority #1.
- **Custom-card invocations are skipped in v1.** `run_custom_card` (`src/app/build.rs:180`) invokes `agent::run_agent` for `pipeline_stages` entries with `prompt_override`. These produce `IMPLEMENT-*.jsonl` logs but their `stage.id` is a user-defined string that doesn't fit `StageId { Query, Research, Plan, Build, Audit }`. v1 skips manifest writes inside `run_custom_card` entirely; the eval run-loader tolerates orphan `IMPLEMENT-*.jsonl` files with no manifest entry (logs and continues). v2 extends `StageId` with a `Custom(String)` variant.
- **`process_task` early-abort paths beyond the six instrumented ones** leave a stale manifest and produce no eval-report. Acceptable for v1.
- **Scout vs Research disambiguation.** Both map to `stage_id: "research"` in JSON; the manifest's `role` field distinguishes (`"Scout"` vs `"Research"`). The eval overlay surfaces both rows when both ran. Aggregation across the `research` stage_id treats each invocation independently; per-stage Research badge takes the worst non-superseded status (consistent with planner-retry rules).
- **Manifest mid-stage crash.** Atomic flushes happen at stage boundaries; a crash inside a stage leaves the manifest one stage behind. Eval reads what is on disk; partial-stage data does not exist. Acceptable.
- **Dual-pipeline.** Each pipeline owns its own ManifestHandle rooted at `.buildloop/arena/{provider}/`.
- **Backwards-compat.** Runs without a manifest produce a minimal "no-data" eval-report; badge omitted; no crash.

## Roadmap (v2 of the harness)

Provider-specific transcript adapters (Codex, OpenCode, GhCopilot); golden tasks; LLM-as-judge; regression tracking; per-model A/B; pattern effectiveness; cost-adjusted score; per-stage live scoring.

## Files

| File | Action | Purpose |
|------|--------|---------|
| `src/run_manifest.rs` | CREATE | `RunManifest`, `ManifestHandle`, `PromptEvidenceSpec`, `StageInvocationId`, `StageStatus`, atomic flush, blake3 hashing |
| `src/agent.rs` | MODIFY (minimal) | Add four fields to `AgentResult`: `log_path: PathBuf`, `actual_provider: String`, `actual_model: String`, `fallback_reason: Option<String>`. Assign at the path-construction sites (`agent.rs:1138, 1338, 608`). On the Codex->Claude fallback path (`agent.rs:989`), set `actual_provider = "claude"` and `fallback_reason = Some(...)`. No signature changes; no behavior changes. |
| `src/app/build.rs` | MODIFY | Own ManifestHandle; `record_invocation` before each agent call (capture `StageInvocationId`); `record_exit(id, status, now, AgentExitInfo { log_path: result.log_path.clone(), .. })` after; `record_skip` for all skip paths (`build.rs:3034, 3058, 4615, 5162`); `record_completion` + `flush` at finalization; `eval::run_for_current_task` call |
| `src/app/review.rs` | MODIFY | Equivalent for Reviewer per-file (`review.rs:886`) + integration (`review.rs:1017`) + Fixer + codex-doubt (`review.rs:480`); each call gets its own invocation_id |
| `src/eval/mod.rs` | CREATE | Public `run_for_current_task()` |
| `src/eval/parser.rs` | CREATE | Claude-only JSONL parser; `parser_skipped: true` for non-Claude |
| `src/eval/run.rs` | CREATE | Manifest-driven `latest_run()` |
| `src/eval/stage_id.rs` | CREATE | Canonical stage map; canonical prior-artifact map |
| `src/eval/checks/mod.rs` | CREATE | Per-stage Check trait |
| `src/eval/checks/plumbing.rs` | CREATE | 8 plumbing checks (one Claude-only) |
| `src/eval/checks/heuristic.rs` | CREATE | 8 heuristic checks (provider-agnostic) |
| `src/eval/scorer.rs` | CREATE | Severity tiers, badge |
| `src/eval/report.rs` | CREATE | Idempotent JSON output |
| `src/app/state.rs` | MODIFY | Add `OverlayRow::ReportLine`, `OverlayRow::ActionButton` |
| `src/tui/overlays.rs` | MODIFY | Render new variants; Pipeline Health section |
| `src/tui/<status meter file>` | MODIFY | EVAL badge line |
| `docs/eval-harness.md` | CREATE | User-facing doc |
| `.gitignore` | MODIFY | `.buildloop/eval-report.json`, `.buildloop/run-manifest.json` |
| `CLAUDE.md` (project root) | MODIFY | One-paragraph "Eval Harness" subsection |

`src/agent.rs` and `src/ghcopilot.rs` receive minimal structural changes only -- four new fields on `AgentResult` (`log_path: Option<PathBuf>`, `actual_provider`, `actual_model`, `fallback_reason`), populated at construction sites. No signature changes, no behavior changes, no logic changes beyond field assignment.

## Constraints

- Eval must NEVER block the pipeline. All entry points use `let _ = ...`.
- IO scope: read/write under `.buildloop/`; read-only under `~/.foundry/patterns/`, `~/.foundry/extensions/`, any ancestor `extensions/` of `project_dir`, the project's `extensions/` -- in practice, any path that resolves from a manifest-recorded `selected_extension_name` is allowed for read.
- No new external crates. blake3 is direct (`Cargo.toml:26`); use it. Hash labels: `blake3:<hex>`.
- Idempotent re-eval (modulo `generated_at`).
- Backwards compatible.
- Manifest concurrency: single in-memory owner; all writes through `ManifestHandle`; atomic flush; no read-modify-write.
- No em-dashes in prose or comments. Use `--`.
- Severity tiers, not weighted scores.
- TUI footprint: one row, ~16 chars. Stoplight fallback `EVAL ●`.
- Dual-pipeline isolation.
- Provider scope: v1 parses Claude SDK JSONL only; non-Claude stages Skip the one transcript-dependent check.

## Verification

- `cargo test eval::` covers: parser happy path; malformed JSONL recovery; manifest-driven loading; every plumbing check positive + negative; every heuristic check positive + negative; scorer thresholds (all pass / heuristic fail / critical fail / skipped / reused); idempotent report; stage_id canonicalization (current + legacy); Reviewer + Fixer accumulating into Audit; non-Claude stage Skip propagation.
- `cargo test run_manifest::` covers: in-memory updates; atomic flush; partial-write recovery; dual-pipeline isolation; single-owner invariant; record_skip with each StageStatus variant; PromptEvidenceSpec hash + structured-evidence computation.
- Manual happy path: `EVAL Q✓R✓P✓B✓A✓`.
- Manual Q+R reuse: rerun a task with checkpoints intact. `EVAL Q-R-P✓B✓A✓`; manifest stage entries for query/research show `status: "reused"`, `skip_reason: "Checkpoint: reusing questions + research from previous session"`.
- Manual planner skip (simple task with detailed description): `EVAL Q✓R✓P-B✓A✓`; planner stage entry shows `status: "skipped"`, `skip_reason: "simple_task_skip_planner"`.
- Manual builder skip via checkpoint: `EVAL Q✓R✓P✓B-A✓`; builder stage entry shows `status: "checkpoint_resume"`.
- Manual doubt skip: doubt-trust skip enabled. `EVAL Q✓R✓P✓B✓A-`; `audit_engaged` is Skip; `completion_path` is `audit_skipped`.
- Manual builder failure: induce builder failure. Eval still runs. Builder invocation `status: "failed"`; `stage_completed_successfully` for Build is FAIL (Critical); aggregate `EVAL Q✓R✓P✓B✗A-`. Other Build checks may or may not fail depending on how far the stage got -- only `stage_completed_successfully` is guaranteed to fail and lock the badge to `✗`.
- Manual planner retry, retry succeeds: induce a planner gate failure to trigger the retry path at `build.rs:4097`. Manifest contains two Planner invocations under `stage_id: "plan"`. The first has `status: "failed"` and `superseded_by: <retry_id>`; the second has `status: "ran"` and `superseded_by: null`. Scorer aggregates non-superseded only -> `P✓`. Overlay shows both invocations; the failed first attempt is visible as historical record.
- Manual planner retry, retry also fails: same setup, retry also fails. Both invocations have `status: "failed"`; the first is superseded by the second; the second is non-superseded. Aggregation considers only the second -> `P✗` (`stage_completed_successfully` fails on the second).
- Manual Codex->Claude fallback: configure a stage to use Codex; simulate a Codex transport stall that triggers `agent.rs:989`. AgentResult returns with `actual_provider: "claude"`, `fallback_reason: Some(...)`. Manifest's stage entry has `effective_provider: "codex"` (requested) and `actual_provider: "claude"` (what ran). `prior_artifact_read` keys on actual and parses the Claude JSONL successfully. Eval-report `notes` array contains the fallback line.
- Manual parallel builder slots: enable parallel builders so `build.rs:1185` runs N concurrent slots. Manifest contains N Builder invocations, all under `stage_id: "implement"`, none superseded. Aggregation across non-superseded -> worst-status wins (consistent with multipass review). No write contention or lost entries; cloning the `Arc<Mutex<RunManifest>>` is the only concurrency primitive needed.
- Manual Research prior artifact: run a Research stage that should read `.buildloop/questions.md` (per `src/prompts.rs:279`). `prior_artifact_received` for Research checks for `questions.md` in the assembled prompt; `prior_artifact_read` checks for a `Read` of `.buildloop/questions.md` in tool_uses.
- Manual GhCopilot early-return paths: configure GhCopilot without a valid `gh` token to trigger `ghcopilot.rs:747-754`; OR enable sandbox mode with GhCopilot to trigger `agent.rs:1050-1057`. AgentResult returns with `log_path: None`. Manifest entry has `log_path: null`, `status: "failed"`. `stage_completed_successfully` fails -> stage badge `✗`. `expected_artifact_written` fails too (no artifact produced). The harness does not crash on the missing log.
- Manual actual_model fill-in: configure Plan with Codex; trigger transport stall at `agent.rs:989` so it falls back to Claude with empty model. AgentResult has `actual_provider: "claude"`, `actual_model: ""`. The eval parser reads the resulting Claude JSONL's `system/init.model` event (e.g. `"claude-opus-4-7"`) and fills the manifest's `actual_model` field. `model_matches_config` then runs against `originally_configured_model` ("codex/...") vs `actual_model` ("claude-opus-4-7"); they differ AND `fallback_reason` is set, so it Skips with evidence naming the fallback (consistent with the `override_reason` Skip rule).
- Manual stage_id serialization: in any verification, confirm manifest JSON uses `"stage_id": "implement"` (not `"build"`) for Builder invocations and `"stage_id": "doubt"` (not `"audit"`) for Reviewer/Fixer invocations. Eval-internal Rust code uses `StageId::Build` / `StageId::Audit`.
- Manual multipass review: configure a changeset that triggers per-file Reviewer passes (`review.rs:886`) followed by integration (`review.rs:1017`). Manifest contains N+1 Reviewer invocations under `stage_id: "doubt"` plus any Fixer invocations. Audit badge aggregates the worst status across all of them.
- Manual blake3-empty trap: in a debug build, force the planner system prompt to empty string. `system_prompt_present` FAILS because `system_prompt_bytes == 0`, even though `system_prompt_hash` would still be `blake3:af1349b9...`. Critical fail; aggregate `P✗`.
- Manual log_path round-trip: configure Builder to use Codex (which writes `studio-codex-*.jsonl`). Manifest's Build invocation `log_path` is the actual studio-prefixed path returned via `AgentResult.log_path`, not a guessed `IMPLEMENT-*.jsonl`.
- Manual budget-recovery override: configure a model that triggers budget recovery. `model_matches_config` is Skip with evidence `"budget_recovery"`; aggregate stays `✓`. `notes` array includes "1 stage ran under budget_recovery override."
- Manual late-prompt evidence: place a pattern reference 5KB into the prompt. `patterns_injected` PASSES.
- Manual extension via name: enable an extension named `recon`. `extension_loaded` matches against the `BEGIN EXTENSION CONTEXT: recon` marker; PASSES regardless of which root the extension lives in.
- Manual non-Claude stage: configure Builder to use Codex. The seven manifest-based plumbing checks and all eight heuristic checks still grade. `prior_artifact_read` is Skip with evidence "non-Claude provider, transcript adapter not in v1". Aggregate Build badge is `✓`.
- Manual reviewer JSON variations: review-report.md with all-empty arrays + explicit PASS verdict + rationale -> `audit_engaged` PASS. Findings missing `file` or `line` -> `audit_findings_localized` FAIL.
- Manual idempotency: re-run eval twice; report byte-identical (modulo `generated_at`).
- Manual graceful degradation: delete manifest and/or report; TUI renders without crash.
- Manual concurrency: multipass review (Reviewer + Fixer in sequence). Both stage entries present; Audit badge aggregates correctly.
- `grep -rn "panic!\|\.unwrap()" src/eval/ src/run_manifest.rs` returns no hits in non-test code.

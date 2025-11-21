# BAML Consistency Rollout Plan

- **Scope**: Reduce brittleness by using BAML (or BAML-aligned parsing) across Scout, Architect, Build, Test, and Deploy outputs. Keep markdown for human readability but ensure machine-facing JSON is schema-validated.

## Phase 1: Stabilize Build Plan (now)
- Post-process `build-tasks.json` after `CreateBuildPlan` to set defaults: `provider="Claude"`, synthesize `agent_instruction` when missing, ensure `task_id`, `build_commands`, deps arrays, and cycle checks pass.
- Harden `_normalize_build_tasks_schema` with required-field checks; refuse parallel execution if incomplete. Log override/repair warnings vs hard failures.
- Add provenance fields (e.g., `schema_version`, `generated_by`, `generated_at`) and distinguish hard errors (fail/re-gen) from soft repairs (warn/telemetry).
- Add unit tests for build-plan normalization and required-field enforcement.
- Declare Builder consumes normalized JSON only (markdown is not trusted for execution).

## Phase 2: Structured Scout + Architect (JSON-first preferred)
- Target flow: LLM → JSON (BAML schema) → render markdown for humans. Keep markdown rendering as a derivative, not the source of truth.
- Interim (if needed): parse existing markdown via `ParseScoutMarkdown` / `ParseArchitectureMarkdown` to produce `scout_report.json` and `architecture.json`; treat these parsers as temporary adapters and log parse failures.
- Align prompts with schema fields; add concise schema reminders in prompts to reduce missing sections.

## Phase 3: Builder Consumption & Telemetry
- Builder consumes the normalized build-plan JSON as the single source of truth (optionally emit a normalized `build-plan.json` for telemetry).
- Keep runtime provider override to Claude for defense-in-depth; log when overrides occur.
- Add `python tools/use_baml.py validate-all --cwd <project>` to run parsers/validators; allow agents/tests to call it, not just CI/pre-commit.
- Telemetry: track num_tasks, num_parallel_groups, auto-repairs vs hard failures, provider overrides.

## Phase 4: Test and Deploy Schemas
- Define BAML schemas for test results and deploy summaries; emit JSON first and render markdown from it for humans.
- Add validations and unit tests for these schemas.

## Cleanup and Drift Prevention
- Remove or clearly mark unused schemas once wiring is complete.
- Keep prompts and schemas in sync; consider generating prompt snippets from BAML definitions for field lists.
- Add CI checks: run agents on fixtures, validate against schemas, fail on missing/changed fields; support deprecation windows for schema changes.
- Document the flow: LLM → JSON (schema) → builder/test/deploy consume JSON → markdown rendered from JSON for humans.

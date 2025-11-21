# BAML JSON-First Rollout (Scout → Architect → Build Plan → Builder)

## What we’re doing
- Consume structured JSON instead of markdown in downstream phases to reduce brittleness and enforce schemas.
- JSON-first chain:
  - Architect reads `scout_report.json` (fallback to `scout-report.md` with warning).
  - Build-plan reads `architecture.json` and parallel recommendation from `scout_report.json` (fallback to markdown with warning).
  - Builder prefers `architecture.json` + normalized `build-tasks.json` (uses markdown only if JSON missing).
- Fail-fast on missing/invalid JSON where safe; warn + fallback only as a last resort.

## Steps to implement

1) Architect input
   - Change Architect phase to load `scout_report.json` if it exists; otherwise warn and use `scout-report.md`.
   - Ensure `scout_report.json` is written earlier (already done via BAML parse).

2) Build-plan generation
   - Feed `architecture.json` (and the parallel recommendation from `scout_report.json`) into `CreateBuildPlan`.
   - If JSON missing/invalid, warn and fall back to markdown.
   - Keep post-process defaults/provenance and cycle checks.

3) Builder input
   - When building, prefer `architecture.json` (fallback to `architecture.md` with warning) alongside `build-tasks.json`.
   - Continue to gate parallel execution on normalized/parallel-ready plans.

4) Validation/CLI
   - Add a `validate-all` entry point that checks scout/architect JSON presence/shape and build-plan readiness in one run; allow phases to call it.
   - Add provenance fields (`schema_version`, `generated_by`, `generated_at`) to scout/architect JSON if not present.

5) Telemetry and warnings
   - Log when using JSON vs markdown, and when falling back.
   - Surface parse failures and fallback counts for observability.

## Rollout notes
- Treat markdown parsing as a temporary adapter; the steady state is JSON-first with markdown rendered for humans.
- If JSON generation fails, either regenerate the phase or use a single fallback to markdown with a clear warning.
- Maintain a small compatibility shim for older field names during rollout.

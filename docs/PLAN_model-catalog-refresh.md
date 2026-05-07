# Plan: Model Catalog & Pricing Auto-Refresh
Date: 2026-05-06
Version: v1
Status: planning

## Context

Anthropic and OpenAI ship new models on a cadence of weeks. Pricing also
changes (price drops on legacy models, new tiers on flagship models).
Context Foundry currently bakes a model list and rate card into the binary
at compile time, so any model released after the last `cargo build` is
invisible to the picker, and rate changes are silently wrong until the next
release.

Concrete trigger: Claude Opus 4.7 shipped recently, but Foundry's Model
Picker, pre-flight estimates, and Stats `avg_cost_per_task` projections
still reference whatever was current the last time the binary was built.
The user noticed and asked for an auto-refresh mechanism so they never have
to think about this again.

Per-run `cost_usd` is **not** the stale surface. The Claude SDK reports
`total_cost_usd` directly in the result JSON (parsed in `src/stats.rs:271`
and elsewhere); that value is authoritative for actual usage. The staleness
is in:

1. **Model Picker rate column** in the Settings Overlay (`src/tui/overlays.rs`)
2. **Pre-flight budget estimates** before a run starts
3. **`avg_cost_per_task` projections** in the Stats / Trust overlay for
   models that have not been run yet (`src/stats.rs`)
4. **The model list itself** -- new models do not appear in the picker
   until the binary is rebuilt

This plan addresses 1-4. It does not change how `cost_usd` flows from the
SDK.

## Current State

- Model lists and rate references are scattered across `src/stats.rs`,
  `src/tui/overlays.rs`, and the builder model spec parser in
  `src/config.rs`. No single source of truth exists.
- Hardcoded model IDs appear in test fixtures (`src/agent.rs:3271, 3294`)
  and in production rate-projection paths.
- No on-disk catalog file. No refresh mechanism. No staleness annotation.
- New models require a code change + `cargo build --release` + reinstall.

## Goals

A new model released yesterday (Claude Opus 4.7, GPT-5.x variant, etc.)
shows up in the Model Picker the next time the user launches `foundry`,
and stale prices for older models are corrected automatically -- without
the user editing JSON or rebuilding the binary.

Hard non-goals:
- Do not block TUI startup on network calls.
- Do not phone home for telemetry.
- Do not auto-switch the user's pinned model when a newer version appears.
- Do not touch `cost_usd` reporting flow.

## Architecture Decisions

### Catalog source of truth

Single canonical schema:

```rust
struct ModelEntry {
    provider: Provider,           // Anthropic | OpenAI | OpenCode | ...
    model_id: String,             // e.g. "claude-opus-4-7"
    display_name: String,
    context_window: u32,
    input_price_per_mtok: f64,
    cached_input_price_per_mtok: Option<f64>,
    output_price_per_mtok: f64,
    deprecated_at: Option<DateTime<Utc>>,
    released_at: Option<DateTime<Utc>>,
    source_url: String,
    source_fetched_at: DateTime<Utc>,
}
```

Two copies:
- **Baked-in fallback** at `src/model_catalog/baseline.json` (compiled with
  `include_str!`). Ships with the binary so first-run with no network still
  works.
- **Live refreshable copy** at `~/.foundry/model_catalog.json`. Atomically
  replaced on successful refresh.

### Refresh policy

On `foundry` startup:

1. Read `~/.foundry/model_catalog.json`'s `source_fetched_at`.
2. If fetched within 24h: skip refresh, use as-is.
3. Otherwise: spawn refresh in the background via `tokio::spawn`. **Do not
   await before TUI render.**
4. On success: atomically replace the on-disk catalog and emit an activity
   log line.
5. On failure (network, rate limit, parse error): log at INFO level and
   continue with last-good catalog.

Hard ceiling: never refresh more than once per 6h regardless of how many
`foundry` invocations happen in that window. Prevents accidental DDoS of
the providers' APIs from a developer running `foundry` in tight loops.

Env var override `FOUNDRY_MODEL_REFRESH=force|skip|auto` (default `auto`).
Settings Overlay also gets a "Refresh now" button.

### Sources

Per provider:

| Provider | Source | Auth | Fallback |
|---|---|---|---|
| Anthropic | `GET /v1/models` | `ANTHROPIC_API_KEY` | curated pricing JSON (URL configurable) |
| OpenAI | `GET /v1/models` for the list, curated JSON for rates (OpenAI does not expose pricing via API) | `OPENAI_API_KEY` | baked-in baseline |
| OpenCode (local) | `opencode list-models` shell-out | none | empty list, $0 rates |

Each entry records the source URL and `source_fetched_at` so the user can
audit drift.

### Bandwidth budget

- One HTTP request per provider, gzip-encoded.
- `If-Modified-Since` / `ETag` honored when the source supports it.
- Total bytes per refresh under 100KB in steady state.
- Catalog file on disk under 50KB.
- No analytics, no telemetry, no third-party trackers.

### UI surface

Model Picker (Settings Overlay):
- Rate column shows current input / output $ per Mtok.
- Section header annotation: `(updated 3h ago)` / `(stale: 9d)`.
- Stale (>14d) catalogs render the annotation in the warning theme color.
- "Refresh now" button triggers in-process refresh.

Stats / Trust overlay's per-model rate projections read from the same
catalog. No second source of truth.

### New-model surfacing

When refresh discovers a `model_id` not present in the previous catalog,
emit one activity log line:

```
[catalog] new model available: claude-opus-4-7
          (input $X / output $Y per Mtok)
```

**Informational only.** Do not auto-switch the user's selection.

### Deprecation handling

When a model the user currently has pinned (in `.foundry.json` or
`stage_overrides`) is marked `deprecated_at` in a refresh:
- Emit a warning in the activity log.
- Annotate the Model Picker row: `(deprecated, sunset YYYY-MM-DD)`.
- Do **not** auto-migrate. The user picks the replacement.

## Implementation Steps

- [ ] Create `src/model_catalog/mod.rs`. Define `ModelCatalog`,
      `ModelEntry`, `load_catalog()`, `refresh_catalog_async()`,
      `refresh_policy_should_run()`. On-disk path is
      `~/.foundry/model_catalog.json`.
- [ ] Create `src/model_catalog/baseline.json` covering current Claude
      family (Opus 4.x, Sonnet 4.x, Haiku 4.x), GPT-4.x / GPT-5 / o-series
      as of build time, and a placeholder local-model entry.
      `include_str!` it into the binary.
- [ ] Create `src/model_catalog/sources.rs`. Per-provider fetchers, called
      in parallel with `tokio::join!`. Each returns
      `Result<Vec<ModelEntry>, FetchError>`.
- [ ] In `src/app.rs` (or wherever bootstrap lives), spawn
      `refresh_catalog_async()` with `tokio::spawn`. **Do not await before
      TUI render.**
- [ ] Update `src/tui/overlays.rs`. Model Picker reads from the live
      catalog. Add the "Refresh now" button and the staleness annotation.
- [ ] Update `src/stats.rs`. `avg_cost_per_task` projection helpers read
      rates from the catalog, not from compile-time constants. Replace
      hardcoded prices with catalog lookups (fall back to baseline if
      `model_id` missing).
- [ ] Add to `src/config.rs` and `.foundry.json`: optional
      `model_catalog_refresh_secs` (default 86400) and
      `model_catalog_url_overrides` (map of provider -> URL) for users
      pointing at internal mirrors.
- [ ] Create `docs/model-catalog.md`. Cover: where the catalog lives,
      refresh cadence, env var overrides, how to pin a stale catalog
      (`FOUNDRY_MODEL_REFRESH=skip`), how to add a new provider source,
      JSON schema. Cross-link from `docs/settings-overlay.md` and the
      README.
- [ ] Add a one-paragraph "Model Catalog" subsection to root `CLAUDE.md`
      pointing future agents at `docs/model-catalog.md`.
- [ ] Add unit tests in `src/model_catalog/`: baseline load, on-disk
      load, refresh-skip when fresh, refresh-run when stale, parse failure
      falls back to last-good, parse failure with no last-good falls back
      to baseline, deprecation annotation appears.

## Constraints

- **Privacy.** No analytics, no telemetry, no model-id reporting back to
  any Context Foundry server. The only network calls are direct provider
  API calls the user is already authenticated against, plus optionally a
  curated static pricing JSON URL (auditable in the docs).
- **Bandwidth.** Hard cap 100KB per refresh; one refresh per 6h regardless
  of invocation count.
- **Failure mode.** Network failure must be invisible except as one
  activity-log line. The TUI never blocks on catalog refresh.
- **No em-dashes** in prose or comments. Use `--`.
- **Backwards compat.** Existing `.foundry.json` configs keep working with
  no migration. New fields are additive with defaults.
- **Determinism in tests.** All catalog logic testable without network --
  inject a `CatalogSource` trait and provide a fixture-backed
  implementation for tests.

## Risks & Open Questions

1. **Anthropic `/v1/models` pricing surface.** The endpoint returns model
   IDs and context windows but may not return pricing. If pricing is not
   exposed via API, we fall back to a curated JSON (probably mirrored from
   docs.anthropic.com). Decide: do we host that JSON, or fetch directly
   from a public URL? Hosting it adds maintenance; fetching adds a
   dependency on a URL we do not control.
2. **OpenAI never exposes pricing via API.** Same problem, harder. Curated
   JSON is required.
3. **OpenCode CLI version drift.** `opencode list-models` output format may
   change. Defensive parsing required.
4. **`tokio::spawn` lifecycle.** If the user quits `foundry` mid-refresh,
   the spawned task should drop cleanly without writing a partial catalog.
   Use atomic-write pattern (write to `.tmp`, rename on success).
5. **First-run race.** If the user's first launch is offline, baseline
   catalog is used. If they go online and launch a second time within 24h,
   no refresh happens. Acceptable -- next-day launch will refresh.
6. **Catalog drift between machines.** Two laptops will have different
   `~/.foundry/model_catalog.json` timestamps. Not a problem; each refreshes
   on its own cadence.

## Verification Matrix

| Check | Method | Expected |
|---|---|---|
| Unit tests pass | `cargo test model_catalog::` | All green |
| Offline first-launch | rm `~/.foundry/model_catalog.json`; disconnect network; launch `foundry` | Picker renders with baseline; activity log notes offline fallback |
| Online refresh | `ANTHROPIC_API_KEY` set; launch `foundry`; wait | Picker shows at least one model not in `baseline.json`, or all baseline entries have updated `source_fetched_at` |
| 6h hard cap | `FOUNDRY_MODEL_REFRESH=force` + launch twice quickly | Only first invocation issues a network call |
| Deprecation surfacing | Pin `claude-opus-4-6` as Plan stage; run refresh that marks it deprecated (fixture) | Picker row annotated; activity log warns; pinned selection preserved |
| No hardcoded model IDs in production | `grep -rn "claude-opus\|claude-sonnet\|claude-haiku" src/ \| grep -vE "test\|mod\.rs\|baseline\.json"` | Zero hits |
| Catalog size | `du -h ~/.foundry/model_catalog.json` after refresh | Under 50KB |

## Out of Scope

- Pattern JSONs in `~/.foundry/patterns/` and `extensions/*/patterns/`.
- `SPEC.md` -- if it exists, leave it alone; spec-sync is a separate task.
- Anthropic SDK or vendored client code -- this layers a refresh on top,
  not changing how `cost_usd` flows from the SDK.
- Recomputing per-run cost locally from token counts (different and larger
  task; not needed since the SDK reports `total_cost_usd` directly).

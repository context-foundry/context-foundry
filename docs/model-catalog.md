# Model Catalog

Context Foundry keeps a local catalog of provider models and per-token prices
so the Model Picker can show what is currently available and what each model
costs. The catalog refreshes automatically in the background -- no JSON edits,
no rebuilds.

## Where the catalog lives

| Layer | Path | Purpose |
|---|---|---|
| Baked-in baseline | `src/model_catalog/baseline.json` (compiled into the binary) | First-run / offline fallback |
| Live copy | `~/.foundry/model_catalog.json` | Updated on each successful refresh |

## Refresh cadence

- On `foundry` startup, a background task checks the live catalog's
  `source_fetched_at`.
- If fetched within the last 24h, no network call is made.
- Otherwise, refresh runs in parallel against Anthropic, OpenAI, and the local
  `opencode` CLI.
- A hard ceiling of one refresh per 6h applies regardless of how many times
  `foundry` is launched.
- Refresh never blocks the TUI. Failures land in the activity log.

## Environment overrides

| Variable | Effect |
|---|---|
| `FOUNDRY_MODEL_REFRESH=auto` | Default. 24h cadence, 6h hard ceiling. |
| `FOUNDRY_MODEL_REFRESH=force` | Refresh on every launch (still bounded by the 6h ceiling). |
| `FOUNDRY_MODEL_REFRESH=skip` | Never refresh. Use the on-disk catalog or baseline. |
| `ANTHROPIC_API_KEY` | Required for Anthropic refresh. Without it, Anthropic models keep their existing entries. |
| `OPENAI_API_KEY` | Required for OpenAI refresh. Same fallback behavior. |

## Pinning a stale catalog

Set `FOUNDRY_MODEL_REFRESH=skip` for the session, or delete
`~/.foundry/model_catalog.json` to fall back to the baked-in baseline.

## Pointing at an internal mirror

In `.foundry.json`:

```json
{
  "model_catalog_url_overrides": {
    "anthropic": "https://internal.example.com/anthropic/v1/models",
    "openai": "https://internal.example.com/openai/v1/models"
  },
  "model_catalog_refresh_secs": 86400
}
```

`model_catalog_refresh_secs: 0` disables the background refresh entirely.

## Schema

`~/.foundry/model_catalog.json`:

```json
{
  "schema_version": 1,
  "source_fetched_at": "2026-05-08T12:00:00Z",
  "entries": [
    {
      "provider": "claude",
      "model_id": "claude-opus-4-7",
      "display_name": "Claude Opus 4.7",
      "context_window": 200000,
      "input_price_per_mtok": 15.0,
      "cached_input_price_per_mtok": 1.5,
      "output_price_per_mtok": 75.0,
      "deprecated_at": null,
      "released_at": null,
      "source_url": "https://api.anthropic.com/v1/models",
      "source_fetched_at": "2026-05-08T12:00:00Z",
      "recommended": true,
      "group": "Claude"
    }
  ]
}
```

## Adding a new provider source

1. Add a `fetch_<provider>` async function to `src/model_catalog/sources.rs`
   that returns `Result<Vec<ModelEntry>>`.
2. Add the call into the `tokio::join!` in
   `src/model_catalog/mod.rs::refresh_catalog_async`.
3. Add a default-pricing helper if the provider does not return prices via API.
4. Add an entry to `src/model_catalog/baseline.json` so first-run users see
   sane defaults.
5. Update `src/config.rs::default_group_for_provider` if the provider needs a
   new picker group.

## Privacy and bandwidth

- No telemetry, no analytics, no model-id reporting back to a Context Foundry
  server.
- The only network calls are direct provider API calls the user is already
  authenticated against.
- One HTTP request per provider per refresh. Total bytes in steady state
  under 100KB.
- Catalog file on disk under 50KB.

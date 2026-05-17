# Context Foundry Build Service (M1 skeleton)

`foundry serve` runs a long-running HTTP control plane: a `/v1` REST API, a
Postgres-backed job store, a worker pool that drives builds, a TTL reaper that
expires previews, and an Anthropic auth proxy.

This is the **M1 skeleton** (T35.3). It wires a `MockBuildBackend` (which
replays a recorded build event stream) and a `LocalFilesystem` storage
backend, so the whole submit -> claim -> build -> ready path is exercisable
without Docker. Real Docker builds and cloud object storage land in **M2
(T35.4)**.

## Running

```bash
foundry serve
```

The service needs a reachable Postgres database. It applies its own
migrations on startup (`migrations/0001_init.sql`).

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `FOUNDRY_SERVICE_DATABASE_URL` | `postgres://foundry:foundry@localhost:5432/foundry` | Postgres connection string |
| `FOUNDRY_SERVICE_BIND` | `0.0.0.0:8787` | `/v1` API bind address |
| `FOUNDRY_SERVICE_PROXY_BIND` | `0.0.0.0:8788` | Anthropic auth proxy bind address |
| `FOUNDRY_SERVICE_API_KEYS` | (empty) | Comma-separated bearer API keys; supports rotation (list both) |
| `ANTHROPIC_API_KEY` | (empty) | Real Anthropic key held by the proxy; never crosses to a build |
| `FOUNDRY_SERVICE_ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Upstream the proxy forwards to |
| `FOUNDRY_SERVICE_WORKERS` | `3` | Worker-pool size |
| `FOUNDRY_SERVICE_QUEUE_CAP` | `50` | Max queued jobs before `429 queue_full` (enforced atomically) |
| `FOUNDRY_SERVICE_MAX_CONCURRENT_BUILDS` | `3` | Global cap on in-flight builds, independent of `FOUNDRY_SERVICE_WORKERS` |
| `FOUNDRY_SERVICE_BUILD_MEMORY` | `4g` | `--memory` cap for a build container |
| `FOUNDRY_SERVICE_BUILD_CPUS` | `2` | `--cpus` cap for a build container |
| `FOUNDRY_SERVICE_BUILD_PIDS_LIMIT` | `512` | `--pids-limit` cap for a build container |
| `FOUNDRY_SERVICE_MIN_TTL_HOURS` | `1` | Lower clamp for preview TTL |
| `FOUNDRY_SERVICE_DEFAULT_TTL_HOURS` | `24` | TTL used when a request omits one |
| `FOUNDRY_SERVICE_MAX_TTL_HOURS` | `72` | Upper clamp for preview TTL |
| `FOUNDRY_SERVICE_STORAGE` | `./.foundry-service/storage` | Local storage root |
| `FOUNDRY_SERVICE_MAX_INPUT_BYTES` | `524288` | Max size of `spec_md` / `tasks_md` |
| `FOUNDRY_SERVICE_REAPER_INTERVAL_SECS` | `60` | TTL reaper poll interval |
| `FOUNDRY_SERVICE_PROXY_MAX_CONCURRENT` | `8` | Max concurrent in-flight requests per proxy token |
| `FOUNDRY_SERVICE_PROXY_MAX_BODY_BYTES` | `4194304` | Max proxied request body size |
| `FOUNDRY_SERVICE_PROXY_MAX_OUTPUT_TOKENS` | `8192` | Max `max_tokens` a proxied request may request |
| `FOUNDRY_SERVICE_PROXY_MODEL_PREFIXES` | `claude-` | Comma-separated allowed model name prefixes |

## `/v1` API

All routes require a `Authorization: Bearer <key>` header **except**
`/v1/healthz`.

| Method | Path | Purpose | Success |
|--------|------|---------|---------|
| `POST` | `/v1/jobs` | Submit a build | `202 Accepted` |
| `GET` | `/v1/jobs` | List jobs (`?owner=&status=`) | `200` |
| `GET` | `/v1/jobs/{id}` | Poll a job | `200` |
| `GET` | `/v1/jobs/{id}/logs` | Build event log (`?stage=&tail=`) | `200 text/plain` |
| `GET` | `/v1/jobs/{id}/artifact` | Source artifact | `200` stream / `302` redirect |
| `GET` | `/v1/jobs/{id}/diagnostics` | Diagnostics bundle | `200` stream / `302` redirect |
| `POST` | `/v1/jobs/{id}/cancel` | Cancel a non-terminal job | `200` |
| `DELETE` | `/v1/jobs/{id}/preview` | Expire a ready job's preview now | `204` |
| `GET` | `/v1/healthz` | Liveness + queue depth (no auth) | `200` |

`LocalFilesystem` streams artifacts/diagnostics directly with `200`; storage
backends that can sign URLs return short-TTL `302` redirects instead.

### Error codes

Typed JSON errors carry `{ "schema_version": 1, "error": <code>, "message": <text> }`:

| Code | HTTP | When |
|------|------|------|
| `validation_error` | `400` | Malformed body, bad `app_name`, oversize input, already-terminal job |
| `idempotency_conflict` | `409` | `idempotency_key` reused with a different normalized request |
| `queue_full` | `429` | Queued job count is at `FOUNDRY_SERVICE_QUEUE_CAP` |
| `rate_limited` | `429` | Proxy paused dispatch after an upstream Anthropic `429` (carries `Retry-After`) |
| `not_found` | `404` | Unknown job or missing artifact |
| `unauthorized` | `401` | Missing/invalid bearer token |
| `internal_error` | `500` | Unexpected server fault |

### Idempotency

A submit is idempotent on `(owner, idempotency_key)`. The server compares a
hash over the **normalized semantic request**: `spec_md`, `tasks_md`,
`app_name`, and the **server-clamped** `preview_ttl_hours`. An identical retry
returns the existing job (`202`); a reuse of the key with a different
normalized request returns `409 idempotency_conflict`. Because the TTL is
clamped before hashing, two requests whose raw `preview_ttl_hours` differ but
clamp to the same value are treated as identical.

## Auth proxy

The proxy (`/v1/messages` on `FOUNDRY_SERVICE_PROXY_BIND`) holds the real
`ANTHROPIC_API_KEY`. Builds never see it: each build is issued a scoped,
revocable token. The proxy enforces coarse abuse limits — a Claude-only model
allowlist, a max concurrent in-flight request cap (atomic), a max request body
size, and a max output-token ceiling — then forwards to Anthropic.

### Rate-limit-aware dispatch

When Anthropic returns a `429` the proxy reads its `Retry-After` header (or
falls back to 60s) and pauses dispatch: subsequent `/v1/messages` calls are
short-circuited with `429 rate_limited` until the window clears, instead of
piling load onto an account already over its headroom. The gate is purely
reactive — it arms only after a `429` is observed, never proactively. When the
window clears, in-flight builds retry in lockstep and may re-arm the gate.

## See also

- Design spec: [`docs/superpowers/specs/2026-05-16-foundry-build-service-design.md`](superpowers/specs/2026-05-16-foundry-build-service-design.md)

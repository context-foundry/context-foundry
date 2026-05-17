# Context Foundry Build Service -- API Contract (v1)

This is the `/v1` REST contract the Context Foundry build service exposes and
that Knowmler integrates against. Audience: Knowmler integration engineers.

The Knowmler side of the integration -- generating `SPEC.md` + `TASKS.md`, the
submit UI, the progress bar, embedding the live preview -- is a separate spec
in the Knowmler repo and is **out of scope here**. The `/v1` API is the shared
interface between the two repos.

## v1 integration notes

Four facts to design the Knowmler integration around:

- **Polling only.** Progress reaches Knowmler by polling
  `GET /v1/jobs/{id}` every few seconds. There is no SSE or webhook push in
  v1. The response shapes leave room for a future
  `GET /v1/jobs/{id}/events` without a breaking change.
- **Claude only.** v1 service builds are Claude-only -- the `foundry-builder`
  image and the auth proxy are Anthropic-specific.
- **No USD budget cap.** v1 has no per-run USD budget cap: there is no
  `budget_usd` request field and no `budget_exceeded` error code. The
  wall-clock build timeout plus the auth proxy's abuse limits are the only
  cost controls. `cost_usd` is reported, not enforced.
- **WIP audit failures still produce `ready`.** Under the `service` run mode,
  a task whose audit fails is recorded as WIP and the build advances to the
  next task. The job still reaches `ready` with a live preview;
  `quality.audit` then reports `"fail"`. A job becomes `failed` only on a
  hard error (build crash, wall-clock timeout, preview-deploy failure).
  `GET /v1/jobs/{id}/diagnostics` exposes the actual review findings.

## Authentication

Every route except `GET /v1/healthz` requires an
`Authorization: Bearer <key>` header. A missing or non-matching key returns
`401 unauthorized`. The service trusts a single caller (Knowmler) -- it is not
a public multi-tenant API. Keys rotate operationally; see the
[API key rotation](build-service-runbook.md) section of the operator runbook.

## Endpoints

| Method | Path | Purpose | Success status |
|--------|------|---------|----------------|
| `POST` | `/v1/jobs` | Submit a build | `202 Accepted` |
| `GET` | `/v1/jobs` | List jobs (`?owner=&status=`) | `200` |
| `GET` | `/v1/jobs/{id}` | Poll a job | `200` |
| `GET` | `/v1/jobs/{id}/logs` | Build event log (`?stage=&tail=`) | `200 text/plain` |
| `GET` | `/v1/jobs/{id}/artifact` | Source artifact | `200` stream / `302` redirect |
| `GET` | `/v1/jobs/{id}/diagnostics` | Diagnostics bundle | `200` stream / `302` redirect |
| `POST` | `/v1/jobs/{id}/cancel` | Cancel a non-terminal job | `200` |
| `DELETE` | `/v1/jobs/{id}/preview` | Expire a ready job's preview now | `204 No Content` |
| `GET` | `/v1/healthz` | Liveness + queue depth (no auth) | `200` |

### POST /v1/jobs

Request body (`SubmitRequest`). The body is parsed manually from raw bytes, so
a malformed body returns a typed `validation_error`.

```json
{
  "app_name": "string (required, [a-z0-9-] slug, <=63 chars, not '-'-bordered)",
  "spec_md": "string (required, non-empty, <= max_input_bytes)",
  "tasks_md": "string (required, non-empty, <= max_input_bytes)",
  "owner": "string (required, non-empty)",
  "preview_ttl_hours": 24,
  "idempotency_key": "string (required, non-empty)"
}
```

`preview_ttl_hours` is optional (i32, server-clamped). Response `202` -- the
same shape for a fresh submit and an idempotent replay:

```json
{
  "schema_version": 1,
  "job_id": "fj_<ULID>",
  "status": "queued",
  "queue_position": 0,
  "created_at": "<RFC3339>",
  "poll_url": "/v1/jobs/<id>"
}
```

`queue_position` is an i64 or `null`.

### GET /v1/jobs/{id}

Response `200` -- the full `JobView`:

```json
{
  "schema_version": 1,
  "job_id": "fj_...",
  "app_name": "string",
  "owner": "string",
  "status": "queued|building|deploying|ready|failed|canceled|expired",
  "percent": 0,
  "stage_label": "string or null",
  "preview_url": "string or null",
  "preview_expires_at": "<RFC3339> or null",
  "queue_position": 0,
  "cost_usd": 0.0,
  "created_at": "<RFC3339>",
  "started_at": "<RFC3339> or null",
  "finished_at": "<RFC3339> or null",
  "error": null,
  "quality": { "audit": "pending", "findings": {"high":0,"medium":0,"low":0} },
  "detail": {}
}
```

`error` is `null`, or `{ "code": "...", "message": "..." }` when an error code
is set. `quality.audit` is one of `pending` / `pass` / `fail`. `quality` and
`detail` are passthrough JSON columns.

### GET /v1/jobs

Query params `owner` and `status` are both optional. Response `200`:

```json
{ "schema_version": 1, "jobs": [ "<JobView>", "..." ], "next_cursor": null }
```

The page limit is hard-coded at 100.

### GET /v1/jobs/{id}/logs

Query params `stage` and `tail` are both optional. Returns the raw event log
as `text/plain; charset=utf-8` -- **not** JSON.

### GET /v1/jobs/{id}/artifact

### GET /v1/jobs/{id}/diagnostics

Both return either a `200` stream (the `LocalFilesystem` backend streams the
bytes directly, with `Content-Type` and `Content-Disposition` headers) or a
`302 Found` redirect with a `Location` header (a signing backend such as
`AzureBlob` returns a short-TTL signed URL). **Knowmler must follow
redirects.**

### POST /v1/jobs/{id}/cancel

Response `200` with the updated `JobView`. Returns `validation_error` if the
job is already in a terminal state.

### DELETE /v1/jobs/{id}/preview

Response `204 No Content`. Returns `validation_error` ("job has no active
preview") unless the job's status is `ready`.

### GET /v1/healthz

Response `200`, no auth required:

```json
{ "status": "ok", "queue_depth": 0, "workers": 3 }
```

The degraded form (when the DB count fails) omits `queue_depth`:

```json
{ "status": "degraded", "workers": 3 }
```

## Job status state machine

A job progresses monotonically:

```
queued -> building -> deploying -> ready | failed | canceled -> expired
```

A `ready` job has a **live preview container** until its TTL elapses. `ready`
is terminal for the build pipeline but **not** "no live resources" -- the
reaper later tears the preview down and moves the job to `expired`. Knowmler
should treat `ready` and `expired` as distinct: `expired` means the preview
URL no longer serves.

## Error codes

Typed JSON errors carry:

```json
{ "schema_version": 1, "error": "<code>", "message": "<text>" }
```

| `error` value | HTTP | When |
|---------------|------|------|
| `validation_error` | `400` | Malformed body, bad `app_name`, oversize input, already-terminal job |
| `unauthorized` | `401` | Missing or invalid bearer token |
| `not_found` | `404` | Unknown job or missing artifact |
| `idempotency_conflict` | `409` | `idempotency_key` reused with a different normalized request |
| `app_name_conflict` | `409` | `app_name` is already held by an in-flight or live (`ready`) build -- the preview hostname would collide; pick a different slug and resubmit |
| `queue_full` | `429` | Queued job count is at `FOUNDRY_SERVICE_QUEUE_CAP` |
| `build_timeout` | `500` | Build exceeded the wall-clock timeout |
| `build_crashed` | `500` | The builder produced no terminal report |
| `preview_deploy_failed` | `500` | Preview deployment failed |
| `backend_unavailable` | `500` | The build backend could not start the build |
| `canceled` | `500` | The job was canceled |
| `internal_error` | `500` | Unexpected server fault |

`429 queue_full` and the proxy's `429 rate_limited` both signal that Knowmler
should back off and retry later.

## Idempotency

A submit is idempotent on `(owner, idempotency_key)`. The server hashes the
**normalized semantic request** -- `spec_md`, `tasks_md`, `app_name`, and the
**server-clamped** `preview_ttl_hours`. An identical retry returns the
existing job (`202`); reusing the key with a different normalized request
returns `409 idempotency_conflict`. Because the TTL is clamped before hashing,
two requests whose raw `preview_ttl_hours` differ but clamp to the same value
are treated as identical.

## quality.audit semantics

The default `quality` shape on a fresh job:

```json
{ "audit": "pending", "findings": {"high":0,"medium":0,"low":0} }
```

`audit` transitions to `pass` or `fail`. A WIP / failed-audit task is **not**
a failed job: under the `service` run mode the build advances past it and the
job still reaches `ready` with a live preview, with `quality.audit` reporting
`"fail"`. Knowmler should surface `quality.audit:"fail"` to the user as a
"shaky build" and link to `GET /v1/jobs/{id}/diagnostics` for the findings.

## See also

- [build-service.md](build-service.md) -- service overview
- [build-service-runbook.md](build-service-runbook.md) -- operator runbook
- [Design spec](superpowers/specs/2026-05-16-foundry-build-service-design.md)

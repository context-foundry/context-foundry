# Design: Context Foundry Build Service (`foundry serve`)

Date: 2026-05-16
Status: design — tasking ready (revised after audit passes)
Author: brainstormed with Claude

## Context & goal

Knowmler (`~/homelab/knowmler`) is a content-analysis platform: it ingests
YouTube/PDF/URL/text and extracts summaries, insights, claims, and prompts. The
goal is to let a Knowmler user take an analyzed idea, have Knowmler turn it into a
build job, and have **Context Foundry actually build a working app from it** —
without anyone watching the TUI.

Context Foundry today is a Rust TUI (`foundry`) wrapping a build pipeline
(Query → Research → Plan → Implement → Doubt, "QRPBA"). The build engine
(`build_loop()`) already runs headless (`foundry run --no-tui`). This project adds
a **service layer** around it: a job queue, an HTTP API, ephemeral build
containers, progress reporting, and live preview hosting.

This covers **the Context Foundry build service only** (the `context-foundry`
repo, Rust). The Knowmler-side work — generating `SPEC.md`+`TASKS.md` from its
analysis, the submit UI, the progress bar, embedding the preview — is a separate
spec in the Knowmler repo. The `/v1` API contract here is the shared interface.

This spec has been through audit rounds against the actual codebase
(`.buildloop/review-report.md`, `.buildloop/review-report-round2.md`, a
user-supplied third pass, and follow-up invalidation). Their findings are folded
in as resolved design. The load-bearing correction: **v1 is service-layer code
plus a real package of engine work (M0)** — `foundry` was built to be watched,
and making it run correctly unattended needs more than a wrapper. The QRPBA
pipeline *logic* is untouched; its *output surface* and *run-mode behavior* are
not.

`cli-printing-press` was evaluated and not used: it generates agent-native CLIs
*from* APIs, the inverse of this need. Its typed-error / JSON-when-piped philosophy
is borrowed.

## Locked decisions

| # | Decision |
|---|----------|
| 1 | CF runs as a **separate build host** with an HTTP API; Knowmler is a remote client. |
| 2 | Job input is **`SPEC.md` + `TASKS.md`**, both authored by Knowmler's analysis. |
| 3 | Each build gets a **live preview environment**; the API returns a preview URL. |
| 4 | Each build runs in a **fresh, disposable container**, dispatched from a queue (~3 concurrent). |
| 5 | Progress reaches Knowmler by **polling** `GET /v1/jobs/{id}`. |
| 6 | Implemented as a **`foundry serve`** subcommand on the existing binary. |
| 7 | Two pluggable seams: a **`BuildBackend` trait** (`LocalDocker` / `AzureContainerApps`) and a **`StorageBackend` trait** (`LocalFilesystem` / `AzureBlob`). Same binary, both environments. No VMs, no Kubernetes. |
| 8 | The real `ANTHROPIC_API_KEY` **never enters a build container**. The daemon runs an **auth proxy** holding the key; build containers get `ANTHROPIC_BASE_URL` → the proxy plus a per-build scoped token. |
| 9 | **v1 has no per-run USD budget cap.** The per-job wall-clock timeout plus auth-proxy abuse limits are coarse damage controls; a precise `--budget` flag is deferred to v2. |
| 10 | Build containers run `foundry` in an **isolated `service` execution profile**: a dedicated `service` run mode (see E3), a service-owned `.foundry.json` with explicit unattended-safe values, a clean `HOME`, and a pinned git identity — no ambient host config or credentials influence a build. |
| 11 | **v1 service builds are Claude-only.** The `foundry-builder` image and the auth proxy are Anthropic-specific. Other providers (Codex/OpenCode/Copilot), each needing its own credential/proxy story, are v2. |

## Engine prerequisites (M0)

`foundry` was built to be watched in a TUI. Three engine changes make it correct
to run unattended. They touch output, reporting, and run-mode behavior — **not the
QRPBA pipeline logic** — but they are real work, not "wrapping," and they are the
first milestone.

- **E1 — a real progress event stream.** Add `foundry run --output-format
  json-stream`: a **versioned, line-delimited JSON event stream** on stdout, one
  object per line, the final line being the terminal `SessionReport`. This is
  *not* just "serialize the existing enum": today the core Q/R/P/B/A stages emit a
  role-only `AgentStarted` and there is **no stage-finished event** (stage
  completion arrives as `AppEvent::AgentDone`, which the headless loop discards).
  E1 must (a) design a concrete, documented public event schema with an
  `event_schema_version`; (b) add **stage lifecycle events** — stage-started and
  stage-finished — for the core stages, not only builder sub-stages; (c) cover
  task started/completed, per-`Usage` cost deltas, and task counts.
- **E2 — `cost_usd` on `SessionReport`.** CF tracks per-agent cost at runtime
  (`AgentOutputEvent::Usage.cost_usd`) but the headless loop only prints each delta
  to stderr. E2 accumulates them into a cumulative `cost_usd` field on the terminal
  report and bumps the report schema 2 → 3. The bump is breaking: the same change
  must update `docs/ci-output-schema.json`, the exact-equality `schema_version ==
  2` assertion in `scripts/smoke-local-model.sh`, and `docs/local-model-setup.md`.
- **E3 — a `service` run mode.** `foundry` defaults to `run_mode = "auto"`, which
  starts a Discovery round when the task queue empties — a service build would
  never terminate. And a WIP (audit-failed) task is currently retried, with a hard
  stop after two consecutive WIPs. Add a `service` run mode that: (a) **terminates
  when the queue empties**, with no Discovery (like `sprint`); (b) treats a
  **WIP/audit-fail task as terminal for that task** — records its quality, advances
  to the next task, with **no retry and no consecutive-WIP hard-stop**; (c)
  **suppresses background noise unsuited to an unattended run** — notably the
  GitHub update check `run_headless` spawns at startup. This makes a service build
  bounded, deterministic, and consistent with the API's "a failed audit is not a
  failed job" contract.

## Build container contract

Independent of the engine work, the `foundry-builder` image and its entrypoint
must establish a clean, service-owned execution environment. This
is builder-image work (M2), not engine work, but it is a hard prerequisite for
correct builds:

- **Service-owned config.** The entrypoint sets a clean `HOME` and writes a
  service-owned `.foundry.json`. It is not a minimal override; it pins the
  unattended-safe profile explicitly: `run_mode: "service"`, all stage providers
  Claude, pinned model routing, `plugins: []`, `auto_push_remote: null`,
  `require_human_approval: false`, `planner_lookahead: false`,
  `backpressure_only: false`, `batch_doubt: false`,
  `skip_doubt_for_simple: false`, `doubt_confidence_threshold: 0`,
  `parallel_builder: false`, `arena_mode: "solo"`, `sandbox: false`, and no
  local-model routing. The outer build container is the isolation boundary; nested
  `foundry` sandbox containers are disabled in v1 so credentials and storage
  grants do not need to cross another Docker boundary. `Config::load` merges
  `~/.foundry/config.json` + project `.foundry.json` + env — without isolation,
  ambient host config could silently change routing, plugins, sandboxing, or run
  mode.
- **Git identity.** The entrypoint runs `git config user.name/user.email` (a
  service identity). `foundry` records task results from commits, and `git commit`
  fails silently (`Ok(false)`) without an identity — commit SHAs would vanish.
- **`claude` on `PATH`**, with no `~/.claude.json` in the image that could shadow
  the injected credentials.
- **Auth via the proxy.** The entrypoint receives `ANTHROPIC_BASE_URL` (the
  daemon's auth proxy) and a per-build scoped token as `ANTHROPIC_API_KEY` — never
  the real key (decision #8).
- **Storage via a per-job grant.** The entrypoint also receives a narrow storage
  grant for this job. LocalDocker gets a mounted per-job directory. Azure gets
  short-lived SAS permissions scoped to exact job paths: read input, create/append
  logs, create diagnostics, create the source artifact; no list/delete and no
  access outside `jobs/<id>/`.

## 1. System architecture & components

`foundry serve` is a long-running **control plane**. It orchestrates `foundry run`
inside ephemeral containers; it owns no build logic.

```
                  Knowmler  (separate repo, separate spec)
                     |  HTTPS + API key
                     v
        +-------------------------------------------+
        |   foundry serve   (always-on)             |  <- 1 ACA app / 1 homelab container
        |  +----------+  +--------------+           |
        |  | HTTP API |  | Worker pool  |           |
        |  +----+-----+  |  (N tokio)   |           |
        |       |        +------+-------+           |
        |  +----v---------------v------+            |
        |  |  Job store (Postgres)     |            |
        |  +---------------------------+            |
        |  +-----------+ +-----------+ +----------+ |
        |  | TTL reaper| | Auth proxy| | Backends | |
        |  +-----------+ +-----+-----+ | (traits) | |
        +--------------------+-+-------+----+------+-+
                             | |            | launches / stores
              +--------------+ |  +---------+----------+
              | (Anthropic API)|  v                    v
              v                +-------------------+  +--------------------+
        api.anthropic.com      | Build container   |  | Preview container  |
                               | foundry run       |  | runs the built app |
          +-- ANTHROPIC_BASE_URL -> Auth proxy <----+  | (scale-to-zero)    |
          |                    | (ephemeral)       |  | build-<id>.<domain>|
          +--------------------+-------------------+  +--------------------+
                                       | source -> StorageBackend
```

| Component | Responsibility | Depends on |
|---|---|---|
| HTTP API | Accept/validate submissions, serve job status, authenticate the single caller. Stateless. `axum` (new dep). | Job store |
| Job store | Durable queue + job state. Postgres via `sqlx` (new dep). Survives daemon restarts; local dev runs Postgres via Compose. | — |
| Worker pool | N tokio tasks. Each claims a `queued` job (`SELECT … FOR UPDATE SKIP LOCKED`), drives it build → deploy, writes progress. N configurable, default 3. | Job store, BuildBackend, StorageBackend |
| `BuildBackend` trait | Environment-specific launch: start a build container, expose its events via `stream_events()` (container stdout on LocalDocker; tailing the `stream.jsonl` Append Blob on Azure, since ACA log streaming is a single-replica preview feature), build the app image, deploy/teardown a preview. Impls: `LocalDocker`, `AzureContainerApps`. | Docker socket *or* Azure REST API |
| `StorageBackend` trait | Environment-specific storage for job inputs, logs, diagnostics, and the source artifact. Issues per-job build storage grants (mount path for `LocalFilesystem`, path-scoped SAS for `AzureBlob`). Serves `GET /artifact` and `GET /diagnostics` as a short-TTL signed-URL redirect (`AzureBlob`) or a streamed `200` (`LocalFilesystem`, which has no signed-URL concept). Impls: `LocalFilesystem`, `AzureBlob`. | local disk *or* Azure Blob |
| Auth proxy | Holds the real `ANTHROPIC_API_KEY`. Accepts requests from build containers bearing a per-build scoped token, validates the token against the live job, enforces coarse abuse limits (model allowlist, max concurrent requests, max request body/output token parameters), and forwards to `api.anthropic.com` with the real key. The key never enters a build container. | — |
| TTL reaper | Tears down preview environments past TTL, marks jobs `expired`, sweeps orphans. | Job store, BuildBackend |
| `foundry-builder` image | One image: `foundry` + Node + `claude` CLI + git + common toolchains. Entrypoint establishes the Build Container Contract (above) and runs `foundry run --no-tui --output-format json-stream`. | — |

Key properties:

- **The pipeline logic is untouched.** v1 changes `foundry`'s output surface and
  adds a `service` run mode (M0); the QRPBA control flow is unchanged.
- **Two environment seams.** `BuildBackend` and `StorageBackend` are the only
  environment-specific code. API, queue, workers, reaper, auth proxy, and progress
  logic are environment-agnostic and testable with mocks.
- **The daemon never builds in-process.** Builds always run in a separate,
  disposable container — isolation (untrusted generated code, multi-user) and the
  spin-up/spin-down model. The daemon tracks progress via `stream_events()`.
- **The real Claude key never enters a build container** (decision #8).
- **Two container roles, separate lifecycles.** Build containers are ephemeral;
  preview containers outlive the build (until TTL).

## 2. API contract

All endpoints under `/v1`. Every request carries `Authorization: Bearer <api-key>`;
the service trusts exactly one caller (Knowmler) and has no user model of its own.
`owner` is opaque metadata for Knowmler's bookkeeping. HTTPS only.

| Method & path | Purpose |
|---|---|
| `POST /v1/jobs` | Submit a build job |
| `GET /v1/jobs/{id}` | Poll job status (Knowmler hits this every few seconds) |
| `GET /v1/jobs` | List jobs, filter by `owner`/`status` |
| `GET /v1/jobs/{id}/logs` | Fetch the build log (`?stage=`, `?tail=N`) |
| `GET /v1/jobs/{id}/artifact` | Download built source as a tarball (signed-URL redirect or stream) |
| `GET /v1/jobs/{id}/diagnostics` | Download build diagnostics (`.buildloop/*.md` + `.buildloop/history/**`) |
| `POST /v1/jobs/{id}/cancel` | Cancel a queued or running job |
| `DELETE /v1/jobs/{id}/preview` | Dismiss the preview before its TTL |
| `GET /v1/healthz` | Liveness/readiness (no auth) |

### `POST /v1/jobs`

Request:
```json
{
  "app_name": "recipe-finder",
  "spec_md": "<full SPEC.md content>",
  "tasks_md": "<full TASKS.md content>",
  "owner": "knowmler-user-1234",
  "preview_ttl_hours": 24,
  "idempotency_key": "uuid"
}
```
`app_name` is a strict slug `[a-z0-9-]` (flows into subdomain/container names).
`spec_md`/`tasks_md` are required, ≤512 KB each. `preview_ttl_hours` is optional,
clamped server-side. `idempotency_key` dedupes retried submits: idempotency is
scoped to `(owner, idempotency_key)` and the **normalized semantic request** is
hashed — `spec_md`, `tasks_md`, `app_name`, and the server-clamped
`preview_ttl_hours`. A repeat with the same normalized request returns the
existing job; a repeat with a different normalized request returns
`409 idempotency_conflict`. (No `budget_usd` in v1 — decision #9.)

Response `202 Accepted`: `{ schema_version, job_id ("fj_"+ULID), status:"queued",
queue_position, created_at, poll_url }`.
Errors: `400 validation_error`, `401`, `409 idempotency_conflict` (key reused
with a different normalized request — an identical repeat instead returns the
existing job as `202`), `429 queue_full`.

### `GET /v1/jobs/{id}`

```json
{
  "schema_version": 1,
  "job_id": "fj_01HMXR8...",
  "app_name": "recipe-finder",
  "owner": "knowmler-user-1234",
  "status": "building",
  "percent": 47,
  "stage_label": "Building task 2 of 4",
  "preview_url": null,
  "preview_expires_at": null,
  "queue_position": null,
  "cost_usd": 0.82,
  "created_at": "...", "started_at": "...", "finished_at": null,
  "error": null,
  "quality": { "audit": "pending", "findings": {"high":0,"medium":0,"low":0} },
  "detail": {
    "tasks_total": 4,
    "tasks_completed": 1,
    "tasks_wip": 0,
    "current_task": {"id": "T1.2", "description": "..."},
    "stages": [
      {"id":"query","status":"pass"}, {"id":"research","status":"pass"},
      {"id":"plan","status":"running"}, {"id":"implement","status":"pending"},
      {"id":"doubt","status":"pending"}
    ],
    "agent_activity": "Planner: drafting current-plan.md"
  }
}
```
`percent`+`status`+`stage_label` are the casual view; `detail`+`quality` the rich
view, populated from the E1 stream. `404` if unknown.

### Status state machine

```
queued --> building --> deploying --> ready --> expired
   |           |             |
   +-----------+-------------+--> failed     (hard error)
   +-----------+-------------+--> canceled   (POST /cancel)
```

**A WIP/failed-audit task is not a failed job.** Under the `service` run mode (E3),
a task whose audit fails is recorded as WIP in `quality`/`detail.tasks_wip`, and
the build advances to the next task. The job still reaches `ready` with a live
preview of whatever was built; `quality.audit` reports `"fail"`. A job becomes
`failed` only on a hard error: build crash, wall-clock timeout, or preview-deploy
failure.

### Typed error codes

`validation_error`, `idempotency_conflict`, `queue_full`, `build_timeout`,
`build_crashed`, `preview_deploy_failed`, `backend_unavailable`, `canceled`,
`internal_error`. (`budget_exceeded` is intentionally absent in v1 — decision #9.)

### Other endpoints

- `GET /v1/jobs` — `{ "jobs":[<summary>...], "next_cursor":... }`.
- `GET /v1/jobs/{id}/logs` — plain text; `?stage=`, `?tail=N`.
- `GET /v1/jobs/{id}/artifact` — the source tarball: a `302` to a short-TTL
  signed URL (`AzureBlob`) or a streamed `200` (`LocalFilesystem`). Works after the
  preview expires.
- `GET /v1/jobs/{id}/diagnostics` — a tarball of the build's `.buildloop/*.md`
  plus `.buildloop/history/**` task snapshots (review reports, plans, build
  claims). Lets Knowmler show the *actual* findings behind a
  `quality.audit:"fail"` job, not just high/medium/low counts.
- `POST /v1/jobs/{id}/cancel` — kills the build/preview container → `canceled`.
- `DELETE /v1/jobs/{id}/preview` — tears the preview down early → `expired`.
- `GET /v1/healthz` — unauthenticated; queue depth, workers, backend reachability.

SSE/webhook push is not in v1; the response shapes leave room for a future
`GET /v1/jobs/{id}/events` without a breaking change.

## 3. Job lifecycle & data flow

1. **Submit.** API validates (sizes, markdown parses, TTL clamped), inserts a
   `jobs` row at `queued`, returns `job_id`. A repeated `idempotency_key` returns
   the existing job only when the normalized request hash matches.
2. **Claim.** A worker atomically claims the oldest queued job via
   `SELECT … FOR UPDATE SKIP LOCKED`, flips it to `building`.
3. **Stage inputs.** The worker writes `SPEC.md` + `TASKS.md` via the
   `StorageBackend` under `jobs/<id>/input/`, appends the preview-contract task to
   `TASKS.md` (Section 4), and counts `- [ ]` lines to record `tasks_total`.
4. **Issue build capabilities.** The worker registers a per-build scoped token
   with the auth proxy, bound to this job and revoked when the job ends. It also
   asks the `StorageBackend` for a per-job storage grant. LocalDocker grants this
   as a bind mount; Azure grants this as short-lived SAS permissions to exact
   job paths, with no list/delete.
5. **Launch the build container** via `backend.start_build(job)`. The
   `foundry-builder` entrypoint establishes the Build Container Contract (clean
   `HOME`, service-owned `.foundry.json` with `run_mode: "service"`, git identity,
   storage grant), then: pull inputs → `git init` an empty repo → drop in
   `SPEC.md`+`TASKS.md` →
   run `foundry run --no-tui --output-format json-stream` (reaching Anthropic only
   through `ANTHROPIC_BASE_URL` → the auth proxy) → on completion, tar the repo to
   `jobs/<id>/output/source.tar.gz`. The tarball is the working tree **plus `.git`
   history** (per-task commits are build provenance), **excluding** `.buildloop/`
   and dependency/build dirs (`node_modules/`, `target/`, `dist/`). Separately, the
   entrypoint copies `.buildloop/*.md` and `.buildloop/history/**` to
   `jobs/<id>/diagnostics/` — kept out of the source tarball, but retained so the
   evidence behind any shaky task in a multi-task `ready` job is retrievable via
   `GET /diagnostics`.
6. **Track progress.** The build container tees the **JSONL event stream (E1)** to
   both its stdout and `jobs/<id>/logs/stream.jsonl` in storage. For Azure this is
   an Append Blob: the entrypoint creates it as an append blob and writes each JSONL
   chunk with append operations; `AzureContainerApps::stream_events()` tails by
   persisted byte offset/ETag and retries safely if polling races a write. The
   worker consumes it via `backend.stream_events()` — reading container stdout on
   LocalDocker, tailing the append blob on Azure — and maps events to the monotonic
   percent scheme below. Postgres writes are throttled (on stage change or every
   ~2s). The full stream + stderr live under `jobs/<id>/logs/`.
7. **Build completes.** The stream's final line is the terminal `SessionReport`.
   Hard failure (crash, timeout) → `failed`. Otherwise → continue; `quality`
   (including any WIP tasks) and `cost_usd` captured from the report.
8. **Build the app image.** Worker → `deploying`, calls `backend.build_image`
   against the repo's root `Dockerfile` (or a synthesized fallback — Section 4).
9. **Deploy the preview** via `backend.deploy_preview`, then health-check it.
10. **Ready.** Worker writes `preview_url`, `preview_expires_at`, `finished_at`,
    status `ready`; the build token and storage grant are revoked/expired.
11. **Expiry.** The reaper tears down previews past TTL → `expired`.

Progress percent — derived from the E1 stream:

| Range | Phase | Driver |
|---|---|---|
| 0–5% | Container starting | `start_build` returns |
| 5–85% | Building tasks | `(tasks_completed + tasks_wip) / tasks_total`, subdivided by E1 stage-started/finished events within the current task |
| 85–95% | Image build | `build_image` |
| 95–100% | Preview deploy + health check | `deploy_preview` |

Percent is clamped to never decrease.

Data layout:
```
StorageBackend (LocalFilesystem / Azure Blob)   Postgres
  jobs/<id>/input/        SPEC.md, TASKS.md        jobs        — full job state
  jobs/<id>/output/       source.tar.gz            job_events  — compact progress history
  jobs/<id>/logs/         stream.jsonl, stderr.log
  jobs/<id>/diagnostics/  review-report.md, current-plan.md, build-claims.md,
                          history/<task_id>/<timestamp>/*.md
```

## 4. Preview hosting

A build produces *source*; the user needs a *running app*. Every build must emit
one uniform artifact: a working root `Dockerfile`. The service appends a
**preview-contract task** to `TASKS.md` before the build:

> Produce a root-level `Dockerfile` that builds and serves the app. The app must:
> bind `0.0.0.0` on `$PORT` (default `8080`) and `EXPOSE` it; expose a root route
> (or `/healthz`) returning HTTP 200; run **fully self-contained** (SQLite or
> in-memory only, no external database, no required secrets); not set
> `X-Frame-Options` or a `frame-ancestors` CSP that blocks iframe embedding.

**Fallback Dockerfile.** The injected task is prose with no hard guarantee the
agent honors it. If the build emits no valid root `Dockerfile`, the worker
synthesizes a fallback by stack detection — `package.json` → Node multi-stage,
`requirements.txt`/`pyproject.toml` → Python, else a static-file server. Only if
the fallback also fails does the job fail with `preview_deploy_failed` (source
artifact still retrievable). M2/M3 testing measures the honor + fallback rates.

Running the preview, per backend:

| | LocalDocker (homelab/dev) | AzureContainerApps (prod) |
|---|---|---|
| Image build | `docker build` | ACR Tasks (`az acr build`) — no daemon |
| Run | `docker run -d`, isolated network | scale-to-zero ACA app from the ACR image |
| URL | `build-<id>.foundry.<domain>` via Caddy dynamic route + wildcard TLS | the ACA-generated FQDN |
| Idle cost | container up until TTL | ~$0 — scales to zero |

Preview containers are sandboxed: no secrets, isolated network (inbound ingress
only, no internal routing), CPU/mem/pids caps, bounded restart policy. If the
image builds but the app crashes on startup, the health check times out →
`failed` / `preview_deploy_failed`, artifact retrievable.

TTL is set at submit (`preview_ttl_hours`, default 24h, server-clamped). The reaper
expires previews past TTL and sweeps orphans; `DELETE /v1/jobs/{id}/preview` tears
down on demand. Source artifacts survive teardown. TTL extension is v2.

## 5. Persistence, errors, recovery, security, cost

### Persistence

Postgres via `sqlx`, versioned migrations run on startup.

```
jobs        — id (fj_+ULID), app_name, owner, status, percent, stage_label,
              spec_url/tasks_url/artifact_url/preview_url, preview_expires_at,
              cost_usd (reported, not capped), ttl_hours,
              idempotency_key, request_hash (unique on (owner, idempotency_key)),
              worker_id, error_code/error_message, quality jsonb, detail jsonb,
              created_at/started_at/finished_at/updated_at
job_events  — id, job_id FK, ts, kind, percent, stage, payload jsonb
```
Indexes: `(status, created_at)` for the claim query, `(owner, created_at)` for
listing, unique on `(owner, idempotency_key)`. On a repeat submit,
`request_hash` decides existing-job vs `idempotency_conflict`. Bulky data
(source, full logs) lives in the `StorageBackend`; Postgres holds state + a
compact event history. The request hash is computed over the normalized semantic
request (`spec_md`, `tasks_md`, `app_name`, and server-clamped TTL), so retry
semantics are deterministic.

### Error taxonomy

| Failure | Stage | Outcome | Code |
|---|---|---|---|
| Bad payload | API | rejected (400) | `validation_error` |
| Idempotency key reused with a different normalized request | API | rejected (409) | `idempotency_conflict` |
| Queue at capacity | API | rejected (429) | `queue_full` |
| Build container won't start | start_build | `failed` | `backend_unavailable` |
| Wall-clock timeout | build | `failed` | `build_timeout` |
| Container crash / nonzero exit | build | `failed` | `build_crashed` |
| Task audit fails (WIP) | build | `ready` — not a failure | — (`quality.audit="fail"`) |
| No Dockerfile + fallback fails | build_image | `failed` (artifact downloadable) | `preview_deploy_failed` |
| Preview app crashes on startup | deploy_preview | `failed` (artifact downloadable) | `preview_deploy_failed` |
| Daemon restarted mid-build | recovery | `failed` | `internal_error` |
| Canceled by Knowmler | cancel | `canceled` | `canceled` |

Retry policy: the service does *not* auto-retry the LLM build. Pure infra failures
*before the build starts* (`backend_unavailable` on launch) get up to 2 retries
with backoff.

### Crash recovery

A startup reconciler: `queued` jobs are left for workers; `building`/`deploying`
jobs whose worker is gone have any live container killed and are marked `failed` /
`internal_error` — builds are not idempotent and never silently re-run; a partial
output tarball, if produced, keeps its `artifact_url`. An orphan sweep tears down
containers/previews/proxy tokens with no matching job row. SIGTERM: stop claiming,
drain in-flight workers to a deadline, exit; stragglers are caught on next boot.

### Security

- **API auth** — one shared bearer token, out-of-band delivery, stored as a
  secret, constant-time compared; two keys accepted during rotation. `GET /healthz`
  is the only unauthenticated route. HTTPS only.
- **Claude credentials.** The real `ANTHROPIC_API_KEY` is held
  only by the daemon's **auth proxy**. A build container runs untrusted, possibly
  prompt-injected code with shell/tool access — so it never receives the real key.
  It gets `ANTHROPIC_BASE_URL` → the proxy and a **per-build scoped token** that is
  bound to one job, revoked when the job ends, and usable only for Anthropic API
  calls through the proxy. The proxy enforces coarse abuse limits for that token:
  Claude-only model allowlist, max concurrent requests, max request body size, and
  max output-token parameters. A leaked token is still a spend credential until
  revocation/timeout, but it cannot expose the real key or reach other providers.
  The proxy is also the natural home for a future per-job spend cap (v2).
- **Storage grants.** Build containers never receive daemon or cloud credentials.
  LocalDocker gets a per-job bind mount. Azure builds get short-lived SAS grants
  scoped to `jobs/<id>/input/*` read plus exact `jobs/<id>/logs/*`,
  `jobs/<id>/diagnostics/*`, and `jobs/<id>/output/source.tar.gz` create/append
  writes. Grants have no list/delete permission and no access outside the job
  prefix.
- **Build container network** — **general internet egress is allowed**: builds
  need it for package installs and for the Research/Scout stages' WebFetch/WebSearch
  tools, and a tight registry allowlist is not operationally feasible. But **no
  inbound**, and **no route to the daemon's other ports, the job store, or other
  containers**. Anthropic traffic still flows only through the auth proxy. The
  residual risk — a prompt-injected build phoning out — is bounded by the ephemeral
  container, the absence of the real API key in it (decision #8), and no
  internal-network access; see Open Risks. Non-root, dropped caps, read-only root
  FS where feasible, CPU/mem/pids caps, wall-clock timeout.
- **Build config isolation** — the entrypoint sets a clean `HOME` and a
  service-owned `.foundry.json` with the exact pinned service profile above, so
  ambient host config cannot alter a build (decision #10).
- **Preview container** — no secrets, isolated network (inbound only), resource
  caps, bounded restart policy.
- **Secrets at rest** — the real key and Azure creds live as daemon secrets; on
  Azure the daemon uses a **managed identity** (no static cloud creds). Public API
  downloads use short-TTL signed URLs where the backend supports them; build
  containers use the narrower storage grant described above.
- **Trust model** — not a public multi-tenant API; trusts one caller, Knowmler.
  Fresh container per build, no shared state.

### Cost & resource controls

- **Wall-clock timeout is the v1 cost ceiling** (~60 min, configurable; exceed →
  kill → `build_timeout`). No USD cap or `budget_exceeded` state in v1 (decision
  #9). The auth proxy's request/concurrency/model limits are abuse dampers, not a
  precise spend cap.
- **Cost accounting** — the worker sums E1 `Usage` deltas and reads the terminal
  `SessionReport.cost_usd` (E2) into the job record. Reported, not capped.
- **Queue cap** → `429 queue_full`; **global concurrency cap** (config-driven,
  separate from worker count) keeps N builds below the Anthropic account's
  rate-limit headroom.
- **Container resource limits** — CPU/mem/pids on build *and* preview containers.

## 6. Testing strategy

No real LLM build runs in CI; the build is behind `BuildBackend`, mocked.

| Layer | Covers | In CI? |
|---|---|---|
| Unit | Progress derivation, status state machine, error mapping, validation, slug sanitization, idempotency including normalized TTL, TTL math, proxy token lifecycle and limits, service-profile rendering | Yes |
| `MockBuildBackend` | Whole daemon end to end by replaying a recorded JSONL stream + a fixture app. Zero LLM cost. | Yes |
| Job store | Real ephemeral Postgres: `FOR UPDATE SKIP LOCKED` correctness under N workers, migrations, idempotency | Yes |
| API contract | Schemas, status codes, `401`, every typed error code (golden tests) | Yes |
| Crash recovery | `building` jobs with dead workers; reconciler; orphan + token sweep | Yes |
| Auth proxy | Token validation, scoping, revocation, coarse abuse limits; key never echoed | Yes |
| Storage grants | Local mount shape, Azure SAS permission shape, no list/delete, diagnostics include `.buildloop/history/**` | Yes |
| LocalDocker / LocalFilesystem | `build_image` + fallback + `deploy_preview` + teardown against a fixture app | If Docker present |
| E2E smoke | A few real builds — tiny spec, ~10 min wall-clock cap — assert `ready` + preview 200. Behind `FOUNDRY_E2E=1` | Manual |
| Azure backend | One minimal real build on a live subscription | Manual |

Two fixtures carry the weight: a recorded JSONL event stream from real
`--output-format json-stream` (once E1's schema is frozen — it then unblocks the
`MockBuildBackend`), and a fixture app repo. Observability: structured `tracing`,
`/healthz`, full per-job stream + stderr in storage.

## 7. Delivery milestones

- **M0 — Engine prerequisites.** E1 (json-stream output + a documented event
  schema + stage lifecycle events), E2 (`cost_usd` on `SessionReport`, schema
  2 → 3, with the coordinated smoke-script/schema-doc updates), E3 (the `service`
  run mode: queue-empty termination + WIP-terminal-per-task). Verified with a
  recorded-stream fixture whose frozen schema unblocks M1. *Two tasks: E1+E2
  (output surface) and E3 (run mode).*
- **M1 — Service skeleton.** `foundry serve` subcommand, `axum` API, `sqlx` +
  Postgres schema/migrations, worker pool, TTL reaper, the `BuildBackend` and
  `StorageBackend` traits, storage grants, the auth proxy with coarse abuse
  limits, `MockBuildBackend` + `LocalFilesystem`, all endpoints, bearer auth.
  Walking skeleton: `POST /jobs` → poll → `ready` with a fixture preview.
- **M2 — Real build (LocalDocker).** The `foundry-builder` image (Build Container
  Contract, exact service profile, LocalFilesystem mount grant),
  `LocalDocker::start_build` + `stream_events`, per-build proxy tokens end to end,
  JSONL progress derivation, source artifact + diagnostics capture.
- **M3 — Preview hosting.** `build_image` + fallback Dockerfile + `deploy_preview`
  + Caddy routing + health check + reaper + `DELETE /preview`.
- **M4 — Hardening.** Crash recovery, wall-clock timeout, cancel, drain; then
  queue cap, global concurrency cap / rate-limit dispatch, full error taxonomy.
  *Two tasks: resilience and access/limits.*
- **M5 — Azure backend.** `AzureContainerApps` + `AzureBlob` impls — ACA Jobs,
  ACR Tasks, scale-to-zero apps, managed identity, path-scoped SAS build grants;
  `stream_events()` tails the `stream.jsonl` Append Blob by offset rather than
  depending on ACA log streaming.
- **M6 — Docs + ops.** Runbook, the Knowmler-facing API doc, deployment manifests
  (Compose for homelab, Bicep/`az` for ACA), the smoke script.

M0 unblocks everything; M1–M4 deliver a working homelab service; M5 adds the cloud
target; M6 is the documentation deliverable. Nine implementation tasks total
(M0→2, M1, M2, M3, M4→2, M5, M6).

## 8. Out of scope / future

- The Knowmler side (spec generation, submit UI, progress bar, preview embedding).
- Per-run USD budget cap (`--budget` + `budget_exceeded`) — v2; the auth proxy is
  the planned enforcement point.
- SSE/webhook progress push; pretty Azure preview subdomains; TTL extension;
  global daily spend cap.
- Apps needing managed infra (external DB, secrets) — the preview contract
  requires self-contained apps.

## 9. Open risks

- **M0 is a real work package, not a wrapper.** The audit passes converged on
  this. E1's event schema and E3's `service` run mode are the critical path; if
  M0 slips or its event coverage is thin, progress reporting and build termination
  both degrade. M0 ships and is fixture-verified before M1 proceeds.
- **Dockerfile-as-contract reliability** — the injected task is prose; the
  fallback Dockerfile is the mitigation but a synthesized image may not run every
  app faithfully. M2/M3 testing measures the rates.
- **Auth proxy is now on the critical path** — every build's Claude traffic flows
  through it; it must be highly available and not a bottleneck. It is a small
  forwarding proxy, but it needs its own tests, health checks, and abuse-limit
  telemetry.
- **Build cost** — a long build at metered API pricing plus ACA vCPU-seconds is
  real money, and v1 has no USD cap (decision #9). Wall-clock timeout plus proxy
  model/concurrency/request limits reduce runaway damage but do not provide exact
  spend enforcement; cost is reported per job.
- **WIP-as-terminal build quality** — under E3 a build proceeds past an
  audit-failed task. Later tasks may build on shaky code. `quality` surfaces this
  to Knowmler, and `GET /diagnostics` exposes the actual review findings, but the
  preview may be of a partially-broken app. Acceptable for v1 (the user still sees
  *something* and is told it is shaky); revisit if hit rates are high.
- **Build-container egress** — a build has general internet egress (needed for
  packages and web tools), so a prompt-injected build could exfiltrate the
  SPEC/TASKS content or generated source. Accepted for v1: the real API key and
  cloud credentials are not in the container (decisions #8 and #10), storage
  grants cannot list/delete or leave the job prefix, the container is ephemeral
  with no internal-network access, and the input originates from Knowmler (a
  semi-trusted source). Revisit if builds ever handle more sensitive input.

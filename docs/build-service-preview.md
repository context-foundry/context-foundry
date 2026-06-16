# Build Service -- Preview Hosting (M3 / T35.5)

This document covers the preview-hosting layer of the `foundry serve` build
service: app image build, fallback `Dockerfile` synthesis, local preview
deployment, Caddy routing, health checks, and preview teardown.

## Overview

After a build container exits, the worker (`src/service/worker.rs`) finishes a
job in this order:

1. Collect and persist the **source artifact** + diagnostics (`source.tar.gz`).
   This happens *before* the preview image build, so a preview failure still
   leaves the source downloadable.
2. Build the **app image** from the build's `Dockerfile` (or a synthesized
   fallback).
3. Run an **isolated preview container** and health-check it.
4. Register a **Caddy route** so the preview is reachable by URL.
5. Mark the job `ready` with a `preview_url` and a TTL-bounded expiry.

## The preview-contract task

Before running the build, the worker appends a synthetic task to the job's
`TASKS.md` (`models::append_preview_contract` /
`models::PREVIEW_CONTRACT_TASK`). The DB row keeps the caller's original
`tasks_md`; only the staged copy handed to the build container is augmented.

`TPREVIEW.1` instructs the build agent to:

- produce a root-level `Dockerfile`,
- bind `0.0.0.0` on the `$PORT` env var (default `8080`) and `EXPOSE` it,
- return HTTP 200 from `/` or `/healthz`,
- run fully self-contained (SQLite or in-memory storage, no external database,
  no required secrets or environment configuration),
- avoid `X-Frame-Options` / `frame-ancestors` headers that would block iframe
  embedding.

## Image build + fallback

`LocalDocker::build_image` (`src/service/localdocker.rs`):

1. If the build emitted a valid root `Dockerfile` (a non-comment line starting
   with `FROM `), it is honored: `docker build -f Dockerfile`.
2. Otherwise a fallback is synthesized by **stack detection**:
   - `package.json` -> Node (`node:22-slim`, `npm start`)
   - `requirements.txt` / `pyproject.toml` -> Python (`python:3.12-slim`,
     `python app.py` / `main.py`, else `http.server`)
   - neither -> static (`python:3.12-slim`, `python -m http.server`)
   The fallback is written to `Dockerfile.foundry-fallback` *after* the source
   artifact is packed, so it never pollutes `source.tar.gz`.
3. The job fails with `preview_deploy_failed` **only when both** the project
   `Dockerfile` and the fallback fail to build. The source artifact stays
   downloadable in that case.

The chosen Dockerfile is recorded as a `job_events` row
(`kind = "image_built"`, `stage` = `project` / `fallback_node` /
`fallback_python` / `fallback_static`) -- the honor/fallback metric. No schema
migration is needed.

## Preview container isolation

`LocalDocker::preview_run_argv` runs the preview with:

- `--network foundry-preview` -- an `--internal` bridge network (inbound-only,
  no egress).
- `--restart on-failure:3` -- a bounded restart policy.
- `--memory` / `--cpus` / `--pids-limit` -- resource caps.
- only `-e PORT=8080` -- **no secrets**, no `ANTHROPIC_*` env.

**No host port is published.** The preview is reached by **container name** on
the `foundry-preview` network (`foundry-preview-<job>:8080`); the
`foundry-service` process and the Caddy that fronts previews both join that
network. Host-port publishing does not work here -- the network is
`--internal`, and the service runs in its own container with its own loopback.

A health-check failure tears the container down, so a failed deploy leaves
nothing running.

## Caddy routing

`src/service/caddy.rs` POSTs a `reverse_proxy` route to the Caddy admin API at
`caddy_admin_url`, appending it to the routes of the configured HTTP server
(`caddy_server_name`, default `srv0`). The route's upstream is the preview
container by name (`foundry-preview-<job>:8080`); its host match and the
`preview_url` stored on the job are `https://<app_name>.<preview_base_domain>`
(`app_name` is the `/v1` request slug). The route `@id` keys off the job id,
so route registration stays unique even if two jobs share an `app_name` -- but
the host *match* does not (see "Hostname uniqueness" below).

Route registration is **best-effort**: a Caddy that is down or misconfigured
logs a warning and the job still reaches `ready`. Only a failed container start
or a health-check timeout produces `preview_deploy_failed`.

Caddy must already have an HTTP server configured for the route POST to land.

## Hostname uniqueness

The preview hostname is `<app_name>.<domain>`, and the `/v1` API validates
`app_name` for slug *shape* only -- there is no uniqueness constraint on
`app_name` in the jobs table. Two live previews with the same `app_name`
register two Caddy routes (distinct `@id`s) that match the **same** host;
Caddy serves whichever it resolves first.

The caller (Knowmler) owns naming and **must** keep `app_name` unique among
currently-live (`ready`) previews -- e.g. by regenerating or suffixing the
playful slug on collision. See `SPEC_knowmler-build-integration.md` (D5).

## TTL + teardown

- The TTL reaper (`src/service/reaper.rs`) marks `ready` jobs whose
  `preview_expires_at` has elapsed as `expired`.
- `DELETE /v1/jobs/{id}/preview` expires a ready job's preview on demand.
- `LocalDocker::teardown` removes the build container, the preview container,
  and the Caddy route (all best-effort).

## Configuration

Eight `FOUNDRY_SERVICE_*` env vars tune preview hosting:

| Env var | Default | Purpose |
|---------|---------|---------|
| `FOUNDRY_SERVICE_PREVIEW_NETWORK` | `foundry-preview` | Isolated preview network name |
| `FOUNDRY_SERVICE_PREVIEW_DOMAIN` | `foundry.local` | Base domain (`<app_name>.<domain>`) |
| `FOUNDRY_SERVICE_CADDY_ADMIN_URL` | `http://localhost:2019` | Caddy admin API URL |
| `FOUNDRY_SERVICE_CADDY_SERVER` | `srv0` | Caddy HTTP-server name routes append to |
| `FOUNDRY_SERVICE_PREVIEW_HEALTH_TIMEOUT_SECS` | `60` | Health-check poll budget |
| `FOUNDRY_SERVICE_PREVIEW_MEMORY` | `512m` | Preview container `--memory` cap |
| `FOUNDRY_SERVICE_PREVIEW_CPUS` | `1` | Preview container `--cpus` cap |
| `FOUNDRY_SERVICE_PREVIEW_PIDS_LIMIT` | `256` | Preview container `--pids-limit` cap |

## Manual smoke

With Docker and a running Caddy that has an `srv0` HTTP server:

```bash
FOUNDRY_SERVICE_BUILD_BACKEND=local_docker foundry serve
```

Submit a job whose `tasks_md` describes the `tests/fixtures/preview-apps/node`
app via `POST /v1/jobs`, poll `GET /v1/jobs/{id}` until `status` is `ready`,
then:

```bash
curl -H "Host: build-<id>.foundry.local" http://localhost/   # expect HTTP 200
curl -fsS http://localhost:2019/config/                       # route registered
```

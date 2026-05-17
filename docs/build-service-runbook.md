# Context Foundry Build Service -- Operator Runbook

`foundry serve` is the long-running control plane for the Context Foundry
build service: a `/v1` REST API on `FOUNDRY_SERVICE_BIND`, an Anthropic auth
proxy on `FOUNDRY_SERVICE_PROXY_BIND`, a Postgres-backed job store, a worker
pool that drives builds, and a TTL reaper that expires previews. This runbook
is the authoritative operations reference. For the service overview see
[build-service.md](build-service.md); for the caller-facing API contract see
[build-service-api.md](build-service-api.md).

## Topology

The service is **two listeners** in one process:

- the `/v1` API on `FOUNDRY_SERVICE_BIND` (default `0.0.0.0:8787`)
- the Anthropic auth proxy on `FOUNDRY_SERVICE_PROXY_BIND` (default
  `0.0.0.0:8788`)

It depends on an **external Postgres** (the job store -- it is never embedded
or mocked). The **build backend** is one of `mock`, `local_docker`, or
`azure_container_apps`, selected by `FOUNDRY_SERVICE_BUILD_BACKEND`. The
**storage backend** is `LocalFilesystem` (default) or `AzureBlob` (used by the
Azure backend).

The binary does **not hot-reload**. Every configuration or environment change
requires a process restart to take effect.

## Deployment options

### Local / homelab (Docker Compose)

Use the Compose stack under [`../deploy/compose/`](../deploy/compose/docker-compose.yml)
-- Postgres + service + Caddy. See [`../deploy/README.md`](../deploy/README.md)
for the procedure and validation commands.

### Azure Container Apps

Use the Bicep template + `az` wrapper under
[`../deploy/azure/`](../deploy/azure/main.bicep). The daemon image **must** be
built with `cargo build --release --features azure`. Without the `azure`
feature the binary `bail!`s at startup when
`FOUNDRY_SERVICE_BUILD_BACKEND=azure_container_apps`.

## Environment variable reference

This is the authoritative full reference. Every variable treats an empty
string the same as unset. The quick subset in
[build-service.md](build-service.md) is a convenience copy.

### Core service config

These are read by `ServiceConfig::from_env()`. None are strictly required by
`from_env()` itself (every one has a default); a bad address or non-numeric
value is a hard startup error.

| Variable | Type | Default | Required | Purpose |
|----------|------|---------|----------|---------|
| `FOUNDRY_SERVICE_DATABASE_URL` | string | `postgres://foundry:foundry@localhost:5432/foundry` | optional | Postgres connection string for the job store |
| `FOUNDRY_SERVICE_BIND` | socket addr | `0.0.0.0:8787` | optional | `/v1` API bind address (hard error if unparseable) |
| `FOUNDRY_SERVICE_PROXY_BIND` | socket addr | `0.0.0.0:8788` | optional | Auth proxy bind address (hard error if unparseable) |
| `FOUNDRY_SERVICE_API_KEYS` | CSV strings | (empty) | optional | Comma-separated `/v1` bearer keys; empty = fail-closed |
| `ANTHROPIC_API_KEY` | string | (empty) | conditional | Real Anthropic key held by the proxy (see Upstream auth) |
| `FOUNDRY_SERVICE_ANTHROPIC_BASE_URL` | string | `https://api.anthropic.com` | optional | Upstream the proxy forwards to |
| `FOUNDRY_SERVICE_WORKERS` | usize | `3` | optional | Worker-pool size |
| `FOUNDRY_SERVICE_QUEUE_CAP` | usize | `50` | optional | Max queued jobs before `429 queue_full` |
| `FOUNDRY_SERVICE_MIN_TTL_HOURS` | i32 | `1` | optional | Lower clamp for preview TTL |
| `FOUNDRY_SERVICE_DEFAULT_TTL_HOURS` | i32 | `24` | optional | TTL used when a request omits one |
| `FOUNDRY_SERVICE_MAX_TTL_HOURS` | i32 | `72` | optional | Upper clamp for preview TTL |
| `FOUNDRY_SERVICE_STORAGE` | path | `./.foundry-service/storage` | optional | Local storage root (`LocalFilesystem`) |
| `FOUNDRY_SERVICE_MAX_INPUT_BYTES` | usize | `524288` | optional | Max size of `spec_md` / `tasks_md` |
| `FOUNDRY_SERVICE_REAPER_INTERVAL_SECS` | u64 | `60` | optional | TTL reaper poll interval |
| `FOUNDRY_SERVICE_PROXY_MAX_CONCURRENT` | usize | `8` | optional | Max concurrent in-flight requests per proxy token |
| `FOUNDRY_SERVICE_PROXY_MAX_BODY_BYTES` | usize | `4194304` | optional | Max proxied request body size |
| `FOUNDRY_SERVICE_PROXY_MAX_OUTPUT_TOKENS` | u64 | `8192` | optional | Max `max_tokens` a proxied request may ask for |
| `FOUNDRY_SERVICE_PROXY_MODEL_PREFIXES` | CSV strings | `claude-` | optional | Allowed model-name prefixes |
| `FOUNDRY_SERVICE_BUILD_BACKEND` | string | `mock` | optional | `mock` / `local_docker` / `azure_container_apps` |
| `FOUNDRY_SERVICE_BUILDER_IMAGE` | string | `foundry-builder:latest` | optional | Builder container image |
| `FOUNDRY_SERVICE_BUILDER_PROXY_URL` | string | `http://host.docker.internal:8788` | optional | URL builder containers use to reach the proxy |
| `FOUNDRY_SERVICE_DOCKER_BIN` | string | `docker` | optional | Docker CLI binary name/path |
| `FOUNDRY_SERVICE_PREVIEW_NETWORK` | string | `foundry-preview` | optional | Docker network for preview containers |
| `FOUNDRY_SERVICE_PREVIEW_DOMAIN` | string | `foundry.local` | optional | Base domain for preview URLs |
| `FOUNDRY_SERVICE_CADDY_ADMIN_URL` | string | `http://localhost:2019` | optional | Caddy admin API URL for preview routing |
| `FOUNDRY_SERVICE_CADDY_SERVER` | string | `srv0` | optional | Caddy server name to patch |
| `FOUNDRY_SERVICE_PREVIEW_HEALTH_TIMEOUT_SECS` | u64 | `60` | optional | Preview-container health-wait timeout |
| `FOUNDRY_SERVICE_PREVIEW_MEMORY` | string | `512m` | optional | `--memory` cap for a preview container |
| `FOUNDRY_SERVICE_PREVIEW_CPUS` | string | `1` | optional | `--cpus` cap for a preview container |
| `FOUNDRY_SERVICE_PREVIEW_PIDS_LIMIT` | u32 | `256` | optional | `--pids-limit` cap for a preview container |
| `FOUNDRY_SERVICE_BUILD_TIMEOUT_SECS` | u64 | `3600` | optional | Wall-clock build timeout (the v1 cost ceiling) |
| `FOUNDRY_SERVICE_DRAIN_DEADLINE_SECS` | u64 | `30` | optional | SIGTERM drain deadline for in-flight workers |
| `FOUNDRY_SERVICE_MAX_CONCURRENT_BUILDS` | usize | `3` | optional | Global in-flight build cap (separate from `_WORKERS`) |
| `FOUNDRY_SERVICE_BUILD_MEMORY` | string | `4g` | optional | `--memory` cap for a build container |
| `FOUNDRY_SERVICE_BUILD_CPUS` | string | `2` | optional | `--cpus` cap for a build container |
| `FOUNDRY_SERVICE_BUILD_PIDS_LIMIT` | u32 | `512` | optional | `--pids-limit` cap for a build container |

### Upstream auth (auth proxy credential)

These configure the credential the auth proxy presents to Anthropic. They are
read by `resolve_upstream_auth()`.

| Variable | Type | Default | Required | Purpose |
|----------|------|---------|----------|---------|
| `FOUNDRY_SERVICE_UPSTREAM_AUTH` | `api_key` \| `oauth` | `api_key` | optional | Upstream credential mode (any other value is a hard error) |
| `FOUNDRY_SERVICE_OAUTH_TOKEN` | string | (empty) | required in `oauth` mode | OAuth access token |
| `FOUNDRY_SERVICE_OAUTH_REFRESH_TOKEN` | string | (empty) | optional | OAuth refresh token |
| `FOUNDRY_SERVICE_OAUTH_CLIENT_ID` | string | (empty) | optional | OAuth client id |
| `FOUNDRY_SERVICE_OAUTH_REFRESH_URL` | string | `https://console.anthropic.com/v1/oauth/token` | optional | OAuth token refresh endpoint |
| `FOUNDRY_SERVICE_OAUTH_EXPIRES_AT` | u64 (unix secs) | unset → none | optional | OAuth token expiry (hard error if non-numeric) |

**Conditional fail-fast validation.** `validate_upstream_credentials()` runs
when `build_backend != "mock"` **OR** `FOUNDRY_SERVICE_UPSTREAM_AUTH` is
explicitly set to a non-empty value. When it runs:

- `api_key` mode requires a non-empty `ANTHROPIC_API_KEY` and **rejects** a
  simultaneously-set `FOUNDRY_SERVICE_OAUTH_TOKEN` (ambiguous credential).
- `oauth` mode requires a non-empty `FOUNDRY_SERVICE_OAUTH_TOKEN`.

With the default `mock` backend and no explicit `FOUNDRY_SERVICE_UPSTREAM_AUTH`,
a missing `ANTHROPIC_API_KEY` is tolerated -- this is why the smoke test runs
without any Anthropic credential.

### Azure backend config

These are read only when the binary is built `--features azure` **and**
`FOUNDRY_SERVICE_BUILD_BACKEND=azure_container_apps`. The first 7 are required
(the binary `bail!`s if any is unset or empty).

| Variable | Type | Default | Required | Purpose |
|----------|------|---------|----------|---------|
| `FOUNDRY_SERVICE_AZURE_SUBSCRIPTION_ID` | string | (none) | required | Azure subscription id |
| `FOUNDRY_SERVICE_AZURE_RESOURCE_GROUP` | string | (none) | required | Resource group for ACA Jobs / Container Apps |
| `FOUNDRY_SERVICE_AZURE_LOCATION` | string | (none) | required | Azure region |
| `FOUNDRY_SERVICE_AZURE_STORAGE_ACCOUNT` | string | (none) | required | Storage account for job objects |
| `FOUNDRY_SERVICE_AZURE_STORAGE_KEY` | string | (none) | required | Storage account key (SAS signing) |
| `FOUNDRY_SERVICE_AZURE_ACR_NAME` | string | (none) | required | ACR for image builds |
| `FOUNDRY_SERVICE_AZURE_ACA_ENVIRONMENT` | string | (none) | required | ACA managed environment name |
| `FOUNDRY_SERVICE_AZURE_STORAGE_CONTAINER` | string | `foundry-jobs` | optional | Blob container for job objects |
| `FOUNDRY_SERVICE_AZURE_MI_CLIENT_ID` | string | (empty) | optional | User-assigned MI client id (empty = system-assigned) |
| `FOUNDRY_SERVICE_AZURE_ARM_URL` | string | `https://management.azure.com` | optional | ARM endpoint |
| `FOUNDRY_SERVICE_AZURE_BLOB_URL` | string | `https://<account>.blob.core.windows.net` | optional | Blob service endpoint |
| `FOUNDRY_SERVICE_AZURE_IMDS_URL` | string | `http://169.254.169.254/metadata/identity/oauth2/token` | optional | IMDS token endpoint |
| `FOUNDRY_SERVICE_AZURE_SIGNED_URL_TTL_SECS` | u64 | `900` | optional | TTL for signed artifact/diagnostics URLs |
| `FOUNDRY_SERVICE_AZURE_SAS_GRANT_TTL_SECS` | u64 | `3600` | optional | TTL for the build-context SAS grant ACR consumes |

## Starting and stopping

`foundry serve` runs in the foreground. On startup it applies its migrations
(`migrations/0001_init.sql`) idempotently via `sqlx::migrate!` -- sqlx tracks
applied versions in `_sqlx_migrations` and skips already-applied ones.

On **SIGTERM** the service stops claiming new jobs, drains in-flight workers up
to `FOUNDRY_SERVICE_DRAIN_DEADLINE_SECS`, then exits. Stragglers are reconciled
on the next boot.

**Startup reconciliation** leaves `queued` jobs claimable, kills orphaned
`building`/`deploying` containers left behind by dead workers, marks those
orphaned jobs with status `failed` carrying an error code (`internal_error` or
`build_crashed`), and preserves any partial artifact URL. It never silently
re-runs an LLM build.

## API key rotation

The `/v1` bearer keys live in `FOUNDRY_SERVICE_API_KEYS` (comma-separated).
They are compared in constant time (`subtle::ConstantTimeEq`); an empty list is
fail-closed (every protected route returns `401`). There is **no rotation
endpoint and no hot-reload**.

To rotate without downtime:

1. Set `FOUNDRY_SERVICE_API_KEYS` to `old,new` and restart.
2. Migrate every caller (Knowmler) to `new`.
3. Set `FOUNDRY_SERVICE_API_KEYS` to `new` only and restart.

`/v1/healthz` stays reachable without a key throughout. "Revoking" a key means
removing it from the list and restarting.

The auth proxy's per-build scoped tokens are a **separate** credential system:
they are issued per job and revoked when the job ends or is canceled. Rotating
`FOUNDRY_SERVICE_API_KEYS` does not touch them.

## Log tailing

The service writes the full per-job event stream to storage at
`jobs/<id>/logs/stream.jsonl`, with the build's stderr persisted alongside it.
`GET /v1/jobs/{id}/logs` serves this stream.

For an Azure deployment, operator log tailing of the **daemon process** uses:

```bash
az containerapp logs show --name <app> --resource-group <rg> --follow
```

There is no `az containerapp logs tail` subcommand -- use `logs show
--follow`. Note that `AzureContainerApps::stream_events()` deliberately does
**not** depend on ACA log streaming: it tails the `stream.jsonl` Append Blob
by byte offset / ETag, so per-job logs are available regardless of the ACA log
pipeline.

## Cost and resource guidance

The **wall-clock build timeout** (`FOUNDRY_SERVICE_BUILD_TIMEOUT_SECS`,
default `3600`s) is the v1 cost ceiling: exceeding it kills the build and
returns `build_timeout`.

**v1 has no per-run USD budget cap** and no `budget_exceeded` state (locked
decision #9). The auth proxy's request/concurrency/model limits are abuse
dampers, not a spend cap. Cost is *reported* per job (`cost_usd` on the job
view), never *enforced*.

Capacity and resource levers:

- `FOUNDRY_SERVICE_QUEUE_CAP` -- queued-job ceiling; over it, submits get
  `429 queue_full`.
- `FOUNDRY_SERVICE_MAX_CONCURRENT_BUILDS` -- global in-flight build cap,
  separate from `FOUNDRY_SERVICE_WORKERS`.
- Per-container CPU/memory/pids caps: `FOUNDRY_SERVICE_BUILD_MEMORY` /
  `_BUILD_CPUS` / `_BUILD_PIDS_LIMIT` and the `FOUNDRY_SERVICE_PREVIEW_*`
  equivalents.

On Azure, builds run as ACA Jobs and previews as scale-to-zero Container Apps,
both billed by vCPU-second / memory -- a long timeout and a high concurrency
cap directly raise the bill.

## Failure-mode playbooks

| Symptom | Likely cause | Remediation |
|---------|--------------|-------------|
| `401 unauthorized` on every route | `FOUNDRY_SERVICE_API_KEYS` unset/empty (fail-closed) or wrong key | Set `FOUNDRY_SERVICE_API_KEYS` and restart; confirm the caller's key |
| `429 queue_full` | Queued jobs at `FOUNDRY_SERVICE_QUEUE_CAP` | Raise the cap or wait; the caller should back off |
| `429 rate_limited` (proxy) | Upstream Anthropic returned `429`; the proxy paused dispatch | Wait for the `Retry-After` window; lower `FOUNDRY_SERVICE_MAX_CONCURRENT_BUILDS` |
| `build_timeout` | Build exceeded `FOUNDRY_SERVICE_BUILD_TIMEOUT_SECS` | Inspect diagnostics; raise the timeout only if the spec genuinely needs it |
| `build_crashed` | Builder produced no terminal report (stream ended early) | Check `jobs/<id>/logs/stream.jsonl` and the build stderr |
| `preview_deploy_failed` | Both the project Dockerfile and the synthesized fallback failed | The source artifact is still downloadable; inspect diagnostics |
| `backend_unavailable` | `start_build` failed (Docker daemon down, ACA Job submit error) | Check the Docker daemon / ACA quota and connectivity |
| Service exits at startup: "requires building foundry with --features azure" | `FOUNDRY_SERVICE_BUILD_BACKEND=azure_container_apps` but the binary lacks the `azure` feature | Rebuild with `cargo build --release --features azure` |
| Postgres unreachable at startup | The service cannot apply migrations | Verify `FOUNDRY_SERVICE_DATABASE_URL` and that Postgres is up |
| Azure: SAS blob ops fail with `AuthenticationFailed` (HTTP 403) | A SAS service-version / string-to-sign mismatch in the daemon's SAS signing (a pre-existing `src/service/azure.rs` issue, tracked separately) | Not env-tunable; file a bug against `src/service/azure.rs` |
| Azure: `build_image` fails to fetch the ACR build context | The source-context SAS expired before ACR fetched it | Raise `FOUNDRY_SERVICE_AZURE_SAS_GRANT_TTL_SECS` |

## Diagnostics and artifact retention

Per-job objects live under `jobs/<id>/` in the storage backend:

- `input/` -- the submitted `SPEC.md` / `TASKS.md`
- `logs/stream.jsonl` -- the full event stream, plus the build's stderr
- `diagnostics/` -- the `.buildloop/*.md` and `.buildloop/history/**` bundle
- `output/source.tar.gz` -- the source artifact

Preview containers expire at their TTL (`preview_ttl_hours`, clamped to
`[FOUNDRY_SERVICE_MIN_TTL_HOURS, FOUNDRY_SERVICE_MAX_TTL_HOURS]`). The TTL
reaper polls every `FOUNDRY_SERVICE_REAPER_INTERVAL_SECS`, tears the container
down, and the `ready` job moves to `expired`. An expired preview does **not**
delete the job row or the stored artifacts/diagnostics -- they remain
downloadable for post-mortem.

**Retention policy.** Stored job objects are retained for **30 days** by
default:

- `LocalFilesystem`: prune with a cron / `find`-based job removing
  `jobs/<id>/` directories older than 30 days.
- `AzureBlob`: configure an Azure Storage lifecycle-management rule on the
  `foundry-jobs` container to delete blobs older than 30 days. The container
  is provisioned by [`../deploy/azure/main.bicep`](../deploy/azure/main.bicep);
  the lifecycle rule itself is an operator step documented in
  [`../deploy/README.md`](../deploy/README.md).

## See also

- [build-service.md](build-service.md) -- service overview
- [build-service-api.md](build-service-api.md) -- Knowmler-facing API contract
- [build-service-localdocker.md](build-service-localdocker.md) -- the LocalDocker backend (M2)
- [build-service-preview.md](build-service-preview.md) -- preview hosting (M3)
- [`../deploy/README.md`](../deploy/README.md) -- deployment manifests
- [Design spec](superpowers/specs/2026-05-16-foundry-build-service-design.md)

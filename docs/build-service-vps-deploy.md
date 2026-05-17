# Build Service -- VPS Deploy (OAuth subscription mode)

How to deploy `foundry serve` (the Context Foundry build service) on the VPS
with the **`local_docker`** backend, authenticating to Anthropic through the
auth proxy in **`upstream_auth=oauth`** mode -- i.e. on the Claude
**subscription**, never a metered API key. This is the deployment Knowmler
drives by calling the `/v1` API.

Scope: this doc covers the **`foundry serve` proxy** credential path. The
**host-level** Claude OAuth (the host shell and Knowmler, which both ride the
ambient `~/.claude` login) is a separate, host-scoped concern -- see
[CLAUDE_OAUTH_SETUP.md](CLAUDE_OAUTH_SETUP.md). The two do not share code: a
`foundry` binary upgrade never touches `~/.claude`, and `foundry serve`'s build
containers never read it. Keep that separation in mind throughout.

See also: [operator runbook](build-service-runbook.md) (full env reference,
playbooks), [API contract](build-service-api.md) (the `/v1` interface Knowmler
calls), [LocalDocker backend](build-service-localdocker.md),
[deploy manifests](../deploy/README.md).

---

## 1. The service `.env` (OAuth mode)

**File location.** The service is configured by a single env file:

```
<repo>/deploy/compose/.env        e.g. /home/chuck/context-foundry/deploy/compose/.env
```

It is created from `deploy/compose/example.env` and is **gitignored -- never
commit it**. It is read **only** by the `foundry-service` container.

**Scope rule.** The OAuth variables below belong **only in this file**. Never
put `FOUNDRY_SERVICE_OAUTH_*`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, or
`ANTHROPIC_AUTH_TOKEN` in a global or shared environment -- not in
`/etc/environment`, not in a shell profile, not in any compose file or env a
host `claude` process or Knowmler inherits. That is the rule
[CLAUDE_OAUTH_SETUP.md](CLAUDE_OAUTH_SETUP.md) enforces; this file's `.env` is
scoped to one container and does not leak into it.

**Recommended `.env`** for an OAuth-mode `local_docker` deployment. The OAuth
block is **not** in `example.env` -- you add it:

```ini
# --- Postgres (consumed by the `postgres` service) ---
POSTGRES_USER=foundry
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=foundry
FOUNDRY_SERVICE_DATABASE_URL=postgres://foundry:<strong-password>@postgres:5432/foundry

# --- listeners (inside the container) ---
FOUNDRY_SERVICE_BIND=0.0.0.0:8787
FOUNDRY_SERVICE_PROXY_BIND=0.0.0.0:8788

# --- /v1 API bearer key(s): this is what Knowmler authenticates with ---
FOUNDRY_SERVICE_API_KEYS=<strong-random-string>

# --- real builds on the host Docker daemon ---
FOUNDRY_SERVICE_BUILD_BACKEND=local_docker
FOUNDRY_SERVICE_CADDY_ADMIN_URL=http://caddy:2019
FOUNDRY_SERVICE_BUILDER_PROXY_URL=http://host.docker.internal:8788

# --- upstream auth: Claude subscription via OAuth, NOT a metered API key ---
FOUNDRY_SERVICE_UPSTREAM_AUTH=oauth
FOUNDRY_SERVICE_OAUTH_TOKEN=<OAuth access token -- see "Token source" below>
FOUNDRY_SERVICE_OAUTH_REFRESH_TOKEN=
# In oauth mode ANTHROPIC_API_KEY is unused -- leave it empty.
ANTHROPIC_API_KEY=
```

(Optional, advanced: `FOUNDRY_SERVICE_OAUTH_CLIENT_ID`,
`FOUNDRY_SERVICE_OAUTH_REFRESH_URL` (default
`https://console.anthropic.com/v1/oauth/token`), and
`FOUNDRY_SERVICE_OAUTH_EXPIRES_AT`. See "Token refresh" below -- leave them
unset for the recommended path.)

### Token source

**Recommended -- `claude setup-token`.** On the VPS, as the host user, run:

```bash
claude setup-token
```

This mints a long-lived OAuth token for headless use. Put it in
`FOUNDRY_SERVICE_OAUTH_TOKEN`; leave `FOUNDRY_SERVICE_OAUTH_REFRESH_TOKEN` and
`FOUNDRY_SERVICE_OAUTH_EXPIRES_AT` empty. This token is **independent of the
interactive `~/.claude` login** -- the service gets its own credential.

**Alternative -- lift from `~/.claude/.credentials.json`.** That file holds
`claudeAiOauth.accessToken` and `claudeAiOauth.refreshToken`. You *could* set
`FOUNDRY_SERVICE_OAUTH_TOKEN` / `FOUNDRY_SERVICE_OAUTH_REFRESH_TOKEN` from them
-- **but this risks logging out Knowmler.** The interactive `claude` login and
Knowmler both share that exact `~/.claude/.credentials.json`. OAuth refresh
tokens are normally single-use/rotating: when `foundry serve` refreshes,
Anthropic issues it a new refresh token and invalidates the shared one, so the
next time the interactive `claude` / Knowmler tries to refresh it fails. **Use
`claude setup-token` instead** so the service never touches the shared refresh
lineage.

**`FOUNDRY_SERVICE_OAUTH_EXPIRES_AT` units.** If you ever set it, it is unix
**seconds**. `~/.claude/.credentials.json` stores `expiresAt` in
**milliseconds** -- divide by 1000. Simplest: leave it unset (see "Token
refresh").

---

## 2. Deploy steps (`local_docker` on the VPS)

Prerequisites: Docker + Docker Compose on the VPS. Postgres and Caddy are
provided by the Compose stack. Run from the context-foundry repo root.

```bash
cd ~/context-foundry                      # adjust to the real path on the VPS

# 0. Ensure the repo has the T35 build-service code (see "Repo state" at the
#    end of this doc -- the service code and this doc must both be present).
git pull                                  # or otherwise sync to the unified main

# 1. Build the foundry-builder image. The local_docker backend runs every
#    build inside it. build.sh builds the release binary if absent, stages it,
#    and `docker build`s the image. (The Compose stack does NOT build this --
#    it is a separate host image.)
bash docker/foundry-builder/build.sh       # -> foundry-builder:latest

# 2. Create and edit the service .env per section 1.
cp deploy/compose/example.env deploy/compose/.env
$EDITOR deploy/compose/.env

# 3. Validate the Compose manifest.
docker compose -f deploy/compose/docker-compose.yml config

# 4. Host OAuth baseline BEFORE deploy -- must PASS, record it.
bash scripts/check-claude-oauth.sh

# 5. Bring the stack up (Postgres + foundry serve + Caddy).
docker compose -f deploy/compose/docker-compose.yml up -d --build

# 6. Host OAuth baseline AFTER deploy -- still PASS == the host login is
#    untouched by the deploy.
bash scripts/check-claude-oauth.sh
```

The guard script in steps 4 and 6 checks the **host** (host shell + Knowmler).
A matching PASS before and after proves the deploy did not disturb the host
login. It does **not** verify the new service -- that is sections 3 and 4.

References: [deploy/README.md](../deploy/README.md),
[build-service-runbook.md](build-service-runbook.md),
[build-service-localdocker.md](build-service-localdocker.md).

---

## 3. Service-level verification

This complements -- does not replace -- `scripts/check-claude-oauth.sh`. Where
a command runs inside the service container, `SVC` abbreviates
`docker compose -f deploy/compose/docker-compose.yml exec foundry-service`.

**(a) The service is in `oauth` mode, not `api_key`.**

```bash
SVC printenv FOUNDRY_SERVICE_UPSTREAM_AUTH      # -> oauth
curl -s localhost:8787/v1/healthz                # -> {"status":"ok",...}
```

Stronger guarantee: `foundry serve` fails fast at startup
(`validate_upstream_credentials()` in `src/service/config.rs`) -- in `oauth`
mode it `bail!`s if `FOUNDRY_SERVICE_OAUTH_TOKEN` is empty; in `api_key` mode it
`bail!`s if `ANTHROPIC_API_KEY` is empty. A service that is **running** in
`oauth` mode therefore necessarily has a token and is not silently on
`api_key`.

**(b) The proxy daemon holds the real credential -- and only the daemon.**

```bash
SVC printenv FOUNDRY_SERVICE_OAUTH_TOKEN        # non-empty: the real token
```

The token lives only in the `foundry-service` container's environment. The
proxy never echoes it in an API response (the real credential is never
placed in a response body) and never writes it into a build.

**(c) Build containers receive only the fake per-build token.** During a build
(section 4), in another shell:

```bash
docker ps --filter ancestor=foundry-builder:latest --format '{{.ID}}'
docker inspect <id> --format '{{json .Config.Env}}' | tr ',' '\n' | grep ANTHROPIC
# ANTHROPIC_BASE_URL=http://host.docker.internal:8788
# ANTHROPIC_API_KEY=<per-build proxy token>
```

The `ANTHROPIC_API_KEY` here is the **proxy-issued per-build token** -- scoped
to that one job and revoked when it ends. **Diff it against your
`FOUNDRY_SERVICE_OAUTH_TOKEN` -- they must differ.** The build container never
receives the real credential (`src/service/localdocker.rs` enforces this with a
test asserting the real key never appears in the container argv).

**(d) Token refresh.** Refresh only fires when `FOUNDRY_SERVICE_OAUTH_EXPIRES_AT`
is set and the token is within 300s of expiry, and it requires
`FOUNDRY_SERVICE_OAUTH_REFRESH_TOKEN`. With the recommended long-lived
`claude setup-token` token and no `EXPIRES_AT`, refresh never fires -- that is
intended; you re-mint the token when it eventually expires (section 5). Refresh
is not part of the routine smoke test; to exercise it deliberately you would
configure a refresh token plus a near-future `EXPIRES_AT` in a staging run and
watch the service logs.

---

## 4. The real acceptance test -- one smoke build to `ready`

`scripts/smoke-build-service.sh` boots `foundry serve` with the **mock**
backend -- it tests the `/v1` plumbing with no LLM and **does not exercise
OAuth**. The real OAuth acceptance test is a live build against the deployed
`local_docker` + `oauth` service:

```bash
KEY=<the FOUNDRY_SERVICE_API_KEYS value>

# Submit
curl -s -X POST localhost:8787/v1/jobs \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{
    "app_name": "oauth-smoke",
    "owner": "ops",
    "idempotency_key": "oauth-smoke-1",
    "spec_md": "# Smoke\nA trivial app.\n",
    "tasks_md": "- [ ] T1.1: Create README.md containing the word hello.\n"
  }'
# -> 202 {"job_id":"fj_...","status":"queued",...}

# Poll until terminal
curl -s localhost:8787/v1/jobs/<job_id> -H "Authorization: Bearer $KEY"
# repeat until "status":"ready"  (or "failed")
```

**Pass = the job reaches `ready`.** Because the service is in `oauth` mode with
no API key configured anywhere, a `ready` job means the proxy authenticated to
Anthropic with the OAuth token -- the build ran on the subscription. There is
no API-key fallback path in `oauth` mode.

**Confirm it billed the subscription, not metered API:**

- *Deductive (authoritative).* `FOUNDRY_SERVICE_UPSTREAM_AUTH=oauth` + no real
  `ANTHROPIC_API_KEY` set + job `ready` => the subscription was used. In
  `oauth` mode the proxy has only the Bearer-token path.
- *Direct.* Check the **API** usage/billing dashboard at `console.anthropic.com`
  for the build window -- it must show **zero** new API spend. Subscription
  usage is tracked separately from API billing.
- The job's `cost_usd` is a **computed** figure (tokens x list price) reported
  for visibility. It is not an API charge and does not mean you were
  API-billed.

---

## 5. Failure modes and fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `foundry serve` exits at startup: `upstream_auth=api_key requires ANTHROPIC_API_KEY but it is empty` | `FOUNDRY_SERVICE_UPSTREAM_AUTH` was omitted, so it defaulted to `api_key`, and (correctly) no API key is set | Set `FOUNDRY_SERVICE_UPSTREAM_AUTH=oauth` in `.env` and restart. **Do not "fix" it by adding `ANTHROPIC_API_KEY`** -- that switches you to metered API billing. This is the failure mode that matters: the misconfig is caught loudly at startup, but the wrong remediation is the path onto metered billing. |
| `foundry serve` exits at startup: `upstream_auth=oauth requires FOUNDRY_SERVICE_OAUTH_TOKEN but it is empty` | `oauth` mode selected but the token field is blank | Populate `FOUNDRY_SERVICE_OAUTH_TOKEN` (section 1) and restart |
| Builds begin failing with upstream `401`/auth errors after weeks or months | The OAuth token expired (no refresh configured -- expected for a `setup-token` token) | Re-run `claude setup-token`, update `FOUNDRY_SERVICE_OAUTH_TOKEN`, restart the service. The binary does not hot-reload -- a restart is required. |
| The interactive `claude` / Knowmler is suddenly logged out | The service was configured with the refresh token from `~/.claude/.credentials.json`; the proxy refreshed and rotated the shared token, invalidating the host login's copy | Re-`claude login` on the host to restore `~/.claude`, then switch the service to a `claude setup-token` token (section 1) so it holds an independent credential |
| `429 rate_limited` from the proxy; builds stall | `foundry serve`, Knowmler, and the interactive Context Foundry all draw on **one** Claude subscription, and the combined load hit the subscription rate ceiling | Lower `FOUNDRY_SERVICE_MAX_CONCURRENT_BUILDS`; serialize heavy build bursts; or give the build service its own subscription/credential. The proxy honors `Retry-After`. |

Note: omitting `upstream_auth=oauth` is **fail-fast at startup**, not a silent
mis-bill -- `validate_upstream_credentials()` runs whenever the build backend
is not `mock`. The genuine risk is the operator's *remediation*: reaching for
an API key instead of selecting `oauth` mode.

---

## 6. Fallback -- bind-mount `~/.claude` (only if the proxy OAuth path fails)

If the proxy OAuth path proves broken end to end -- the section 4 build never
reaches `ready` and the service logs show the proxy failing upstream auth --
there is a proven fallback. Knowmler already authenticates its container by
bind-mounting `~/.claude` and shelling out to the `claude` CLI; the same can be
done for `foundry serve` build containers.

It requires **code changes, not configuration**:

- `src/service/localdocker.rs`: bind-mount the host `~/.claude` read-only into
  the build container (`-v $HOME/.claude:/home/builder/.claude:ro`) and stop
  injecting `ANTHROPIC_BASE_URL` / the per-build proxy `ANTHROPIC_API_KEY`, so
  the container's `claude` CLI uses the mounted ambient OAuth directly and
  bypasses the proxy.
- `docker/foundry-builder/entrypoint.sh`: it currently **removes** any ambient
  `~/.claude.json` to enforce the clean-HOME Build Container Contract; that
  removal would have to be conditioned off.

This forfeits the proxy's per-build token scoping and abuse limits, and
contradicts the shipped Build Container Contract. **Do not implement it unless
the proxy OAuth path fails the section 4 test.** It is recorded here only as a
known escape hatch.

---

## Repo state -- prerequisite for this deploy

The T35 build-service code (`foundry serve`, the auth proxy, `src/service/`,
the `deploy/` manifests, this doc) and the host OAuth doc
([CLAUDE_OAUTH_SETUP.md](CLAUDE_OAUTH_SETUP.md)) were developed on different
machines and must be on one unified `main` before the VPS can deploy. The VPS
`git pull` in section 2 step 0 must land a `main` that contains **both** the
`src/service/` build-service code **and** this `docs/` set. If `git pull` does
not bring in `src/service/`, the branches have not been reconciled yet --
resolve that first.

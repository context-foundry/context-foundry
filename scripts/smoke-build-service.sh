#!/usr/bin/env bash
# smoke-build-service.sh -- build-service /v1 API smoke test.
#
# Boots `foundry serve` with the mock build backend, submits a fixture job
# through POST /v1/jobs, polls to a terminal state, and checks the
# logs/artifact/diagnostics endpoints. Exit 0 == PASS.
#
# Usage:
#   bash scripts/smoke-build-service.sh
#   bash scripts/smoke-build-service.sh --keep            # keep the workspace
#   bash scripts/smoke-build-service.sh --timeout <secs>  # poll cap (default 180)
#   bash scripts/smoke-build-service.sh --api-port <n>    # /v1 API port (default 8787)
#   bash scripts/smoke-build-service.sh --proxy-port <n>  # proxy port (default 8788)
#
# Prereqs: curl, python3; a reachable Postgres at FOUNDRY_SERVICE_DATABASE_URL
#   OR docker (an ephemeral Postgres is started); the `foundry` release binary
#   (FOUNDRY_BIN env, target/release/foundry, or `command -v foundry`).
#
# Related docs: docs/build-service-runbook.md, docs/build-service-api.md.
# Exit codes: 0 PASS, 1 FAIL, 2 bad CLI argument.
set -euo pipefail

KEEP=0
TIMEOUT_SECS=180
API_PORT=8787
PROXY_PORT=8788

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep)       KEEP=1; shift ;;
    --timeout)    [[ $# -ge 2 ]] || { echo "[smoke] FAIL: --timeout requires a value" >&2; exit 1; }; TIMEOUT_SECS="$2"; shift 2 ;;
    --api-port)   [[ $# -ge 2 ]] || { echo "[smoke] FAIL: --api-port requires a value" >&2; exit 1; }; API_PORT="$2"; shift 2 ;;
    --proxy-port) [[ $# -ge 2 ]] || { echo "[smoke] FAIL: --proxy-port requires a value" >&2; exit 1; }; PROXY_PORT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "[smoke] unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

fail() { echo "[smoke] FAIL: $*" >&2; exit 1; }
info() { echo "[smoke] $*"; }

resolve_foundry_bin() {
  if [[ -n "${FOUNDRY_BIN:-}" ]]; then
    [[ -x "$FOUNDRY_BIN" ]] || fail "FOUNDRY_BIN=$FOUNDRY_BIN is not executable"
    echo "$FOUNDRY_BIN"
    return
  fi
  local repo_root
  repo_root="$(cd "$(dirname "$0")/.." && pwd)"
  if [[ -x "$repo_root/target/release/foundry" ]]; then
    echo "$repo_root/target/release/foundry"
    return
  fi
  if command -v foundry >/dev/null 2>&1; then
    command -v foundry
    return
  fi
  fail "foundry binary not found (set FOUNDRY_BIN, run 'cargo build --release', or install foundry on PATH)"
}

SERVE_PID=""
MANAGED_PG=0
PG_CONTAINER=""
WORK=""

# shellcheck disable=SC2329  # invoked indirectly via `trap cleanup EXIT`
cleanup() {
  if [[ -n "$SERVE_PID" ]] && kill -0 "$SERVE_PID" 2>/dev/null; then
    kill "$SERVE_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$SERVE_PID" 2>/dev/null || true
  fi
  if [[ "$MANAGED_PG" == "1" && -n "$PG_CONTAINER" ]]; then
    docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
  fi
  if [[ -n "$WORK" ]]; then
    if [[ "$KEEP" == "1" ]]; then
      info "leaving workspace at $WORK"
    else
      rm -rf "$WORK"
    fi
  fi
}

command -v curl    >/dev/null 2>&1 || fail "curl not in PATH"
command -v python3 >/dev/null 2>&1 || fail "python3 not in PATH (used to assert JSON output)"

FOUNDRY_BIN="$(resolve_foundry_bin)"
info "using foundry binary: $FOUNDRY_BIN"

API_KEY="smoke-$(date +%s)-$RANDOM"

DB_URL="${FOUNDRY_SERVICE_DATABASE_URL:-postgres://foundry:foundry@127.0.0.1:5432/foundry}"

read -r DB_HOST DB_PORT < <(DB_URL="$DB_URL" python3 -c '
import os, urllib.parse
u = urllib.parse.urlparse(os.environ["DB_URL"])
print(u.hostname or "127.0.0.1", u.port or 5432)
')

pg_reachable() {
  DB_HOST="$DB_HOST" DB_PORT="$DB_PORT" python3 -c '
import os, socket, sys
try:
    socket.create_connection((os.environ["DB_HOST"], int(os.environ["DB_PORT"])), 2).close()
except OSError:
    sys.exit(1)
'
}

if pg_reachable; then
  MANAGED_PG=0
  info "using existing Postgres at $DB_HOST:$DB_PORT"
elif command -v docker >/dev/null 2>&1; then
  PG_CONTAINER="foundry-smoke-pg-$$"
  info "no reachable Postgres -- starting ephemeral container $PG_CONTAINER"
  docker run -d --rm --name "$PG_CONTAINER" \
    -e POSTGRES_USER=foundry -e POSTGRES_PASSWORD=foundry -e POSTGRES_DB=foundry \
    -p 5432 postgres:16-alpine >/dev/null
  MANAGED_PG=1
  trap cleanup EXIT
  PG_HOST_PORT="$(docker port "$PG_CONTAINER" 5432/tcp | head -n 1 | sed 's/.*://')"
  [[ -n "$PG_HOST_PORT" ]] || fail "could not determine the ephemeral Postgres host port"
  DB_URL="postgres://foundry:foundry@127.0.0.1:$PG_HOST_PORT/foundry"
  pg_ok=0
  for _ in $(seq 1 30); do
    if docker exec "$PG_CONTAINER" pg_isready -U foundry >/dev/null 2>&1; then
      pg_ok=1
      break
    fi
    sleep 1
  done
  [[ "$pg_ok" == "1" ]] || fail "ephemeral Postgres did not become ready within 30s"
  info "ephemeral Postgres ready at 127.0.0.1:$PG_HOST_PORT"
else
  fail "no reachable Postgres and docker is unavailable -- set FOUNDRY_SERVICE_DATABASE_URL or install Docker (see docs/build-service-runbook.md)"
fi

WORK="$(mktemp -d -t foundry-svc-smoke.XXXXXX)"
trap cleanup EXIT
info "workspace: $WORK"

# Service env. ANTHROPIC_API_KEY and FOUNDRY_SERVICE_UPSTREAM_AUTH are
# deliberately NOT exported: with the mock backend and no explicit upstream
# auth, startup credential validation stays skipped and the run has zero LLM
# cost.
export FOUNDRY_SERVICE_DATABASE_URL="$DB_URL"
export FOUNDRY_SERVICE_BIND="127.0.0.1:$API_PORT"
export FOUNDRY_SERVICE_PROXY_BIND="127.0.0.1:$PROXY_PORT"
export FOUNDRY_SERVICE_API_KEYS="$API_KEY"
export FOUNDRY_SERVICE_BUILD_BACKEND="mock"
export FOUNDRY_SERVICE_STORAGE="$WORK/storage"

"$FOUNDRY_BIN" serve >"$WORK/serve.log" 2>"$WORK/serve.err.log" &
SERVE_PID=$!

healthy=0
for _ in $(seq 1 30); do
  kill -0 "$SERVE_PID" 2>/dev/null || fail "foundry serve exited during startup -- see $WORK/serve.err.log"
  if curl -fsS "http://127.0.0.1:$API_PORT/v1/healthz" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done
[[ "$healthy" == "1" ]] || fail "service did not become healthy -- see $WORK/serve.err.log"
info "service healthy on 127.0.0.1:$API_PORT"

# Check 1 -- auth fail-closed.
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$API_PORT/v1/jobs")"
[[ "$code" == "401" ]] || fail "GET /v1/jobs without a bearer key returned $code (expected 401)"
info "check 1: unauthenticated /v1/jobs -> 401"

# Build the submit body.
API_KEY="$API_KEY" python3 - >"$WORK/req.json" <<'PY'
import json, os
body = {
    "app_name": "smoke-app",
    "spec_md": "# Smoke Spec\n\nA fixture spec for the build-service smoke test.\n",
    "tasks_md": "## Tasks\n\n- [ ] T1.1: Smoke fixture task.\n",
    "owner": "smoke",
    "idempotency_key": os.environ["API_KEY"],
}
print(json.dumps(body))
PY

# Check 2 -- submit.
resp="$(curl -sS -X POST \
  -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  --data @"$WORK/req.json" -w $'\n%{http_code}' \
  "http://127.0.0.1:$API_PORT/v1/jobs")"
status="${resp##*$'\n'}"
body="${resp%$'\n'*}"
[[ "$status" == "202" ]] || fail "POST /v1/jobs returned $status (expected 202): $body"
JOB_ID="$(BODY="$body" python3 -c 'import json,os; print(json.loads(os.environ["BODY"])["job_id"])')"
[[ -n "$JOB_ID" ]] || fail "POST /v1/jobs response has no job_id: $body"
info "check 2: POST /v1/jobs -> 202, job_id=$JOB_ID"

# Check 3 -- poll to a terminal state.
STATUS=""
PREVIEW_URL=""
for ((i = 0; i < TIMEOUT_SECS; i++)); do
  jv="$(curl -sS -H "Authorization: Bearer $API_KEY" \
    "http://127.0.0.1:$API_PORT/v1/jobs/$JOB_ID")"
  read -r STATUS PREVIEW_URL < <(BODY="$jv" python3 -c '
import json, os
d = json.loads(os.environ["BODY"])
print(d.get("status", ""), d.get("preview_url") or "")
')
  case "$STATUS" in
    ready|failed|canceled|expired) break ;;
  esac
  sleep 1
done
case "$STATUS" in
  ready|failed|canceled|expired) ;;
  *) fail "job $JOB_ID did not reach a terminal state within ${TIMEOUT_SECS}s (last status=$STATUS)" ;;
esac
[[ "$STATUS" == "ready" ]] || fail "job terminal status is $STATUS (expected ready with the mock backend) -- see $WORK/serve.err.log"
info "check 3: job reached ready"

# Check 4 -- logs.
code="$(curl -s -o "$WORK/logs.txt" -w '%{http_code}' \
  -H "Authorization: Bearer $API_KEY" \
  "http://127.0.0.1:$API_PORT/v1/jobs/$JOB_ID/logs")"
[[ "$code" == "200" ]] || fail "GET .../logs returned $code (expected 200)"
[[ -s "$WORK/logs.txt" ]] || fail "logs body is empty"
info "check 4: GET .../logs -> 200, $(wc -c <"$WORK/logs.txt") bytes"

# Check 5 -- artifact.
code="$(curl -s -o "$WORK/artifact.bin" -w '%{http_code}' \
  -H "Authorization: Bearer $API_KEY" \
  "http://127.0.0.1:$API_PORT/v1/jobs/$JOB_ID/artifact")"
[[ "$code" == "200" ]] || fail "GET .../artifact returned $code (expected 200 for the LocalFilesystem backend)"
[[ -s "$WORK/artifact.bin" ]] || fail "artifact body is empty"
info "check 5: GET .../artifact -> 200, $(wc -c <"$WORK/artifact.bin") bytes"

# Check 6 -- diagnostics.
code="$(curl -s -o "$WORK/diagnostics.bin" -w '%{http_code}' \
  -H "Authorization: Bearer $API_KEY" \
  "http://127.0.0.1:$API_PORT/v1/jobs/$JOB_ID/diagnostics")"
[[ "$code" == "200" ]] || fail "GET .../diagnostics returned $code (expected 200 for the LocalFilesystem backend)"
[[ -s "$WORK/diagnostics.bin" ]] || fail "diagnostics body is empty"
info "check 6: GET .../diagnostics -> 200, $(wc -c <"$WORK/diagnostics.bin") bytes"

# Check 7 -- preview reachability (conditional). The mock backend emits a
# synthetic preview URL on the preview.local domain that no container serves,
# so the reachability check only runs against a real Docker backend.
if command -v docker >/dev/null 2>&1 \
  && docker info >/dev/null 2>&1 \
  && [[ -n "$PREVIEW_URL" ]] \
  && [[ "$PREVIEW_URL" != *preview.local* ]]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$PREVIEW_URL")"
  [[ "$code" == "200" ]] || fail "preview URL $PREVIEW_URL returned $code (expected 200)"
  info "check 7: preview URL -> 200"
else
  info "check 7: skipped preview reachability check (mock backend preview URL is synthetic -- run against a real Docker backend to exercise it)"
fi

echo "[smoke] PASS  (workspace: $WORK)"
exit 0

#!/usr/bin/env bash
# scripts/smoke-local-model.sh -- Phase 32 GATE smoke test.
# Spins up a tiny throw-away project, configures .foundry.json to route the
# builder stage through opencode + LM Studio, runs foundry run --no-tui, and
# asserts the round trip produced opencode invocations and zero claude
# invocations. Exit code 0 == PASS, anything else == FAIL.
#
# Usage:
#   bash scripts/smoke-local-model.sh                # default 600s cap
#   bash scripts/smoke-local-model.sh --keep         # leave temp dir behind
#   bash scripts/smoke-local-model.sh --timeout 900  # custom cap (seconds)
#
# Prereqs (script aborts otherwise):
#   - opencode in PATH
#   - LM Studio reachable at http://127.0.0.1:1234 with at least one model loaded
#     and that model must appear in `opencode models lmstudio`
#   - `foundry` release binary (FOUNDRY_BIN env, target/release/foundry, or
#     `command -v foundry`, in that order)
set -euo pipefail

KEEP=0
TIMEOUT_SECS=600
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep)    KEEP=1;             shift ;;
    --timeout) [[ $# -ge 2 ]] || { echo "[smoke] FAIL: --timeout requires a value" >&2; exit 1; }; TIMEOUT_SECS="$2";  shift 2 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
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

resolve_timeout_cmd() {
  if command -v gtimeout >/dev/null 2>&1; then
    echo "gtimeout"
  elif command -v timeout >/dev/null 2>&1; then
    echo "timeout"
  else
    echo ""
  fi
}

FOUNDRY_BIN="$(resolve_foundry_bin)"
TIMEOUT_CMD="$(resolve_timeout_cmd)"
[[ -n "$TIMEOUT_CMD" ]] || info "warning: neither gtimeout nor timeout found; running without time cap"

command -v opencode >/dev/null 2>&1 || fail "opencode not in PATH"
command -v curl     >/dev/null 2>&1 || fail "curl not in PATH"
command -v git      >/dev/null 2>&1 || fail "git not in PATH"
command -v python3  >/dev/null 2>&1 || fail "python3 not in PATH (used to assert JSON output)"

curl -fsS --max-time 3 http://127.0.0.1:1234/v1/models >/dev/null \
  || fail "LM Studio is not reachable at http://127.0.0.1:1234 -- start LM Studio and load a model"

MODEL="$(opencode models lmstudio 2>/dev/null | head -n 1 | tr -d '[:space:]')"
[[ -n "$MODEL" ]] || fail "'opencode models lmstudio' returned no models -- load a model in LM Studio with sufficient n_ctx"
info "using LM Studio model: $MODEL"
info "using foundry binary: $FOUNDRY_BIN"

WORK="$(mktemp -d -t foundry-smoke.XXXXXX)"
cleanup() {
  if [[ "$KEEP" == "1" ]]; then
    info "leaving workspace at $WORK"
  else
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT
info "workspace: $WORK"

cd "$WORK"
git init -q .
git config user.email "smoke@example.com"
git config user.name  "smoke"

cat >SPEC.md <<'EOF'
# Smoke Spec

print hello world
EOF

cat >TASKS.md <<'EOF'
## Tasks

- [ ] T1.1: Create a file named hello.txt at the repo root containing the single line "hello world".
EOF

MODEL="$MODEL" python3 - <<'PY'
import json, os, sys
model = os.environ["MODEL"]
config = {
    "builder_provider": "opencode",
    "builder_model": model,
    "builder_models": [f"opencode:{model}"],
    "dual_selection": "first",
    "run_mode": "sprint",
    "agent_timeout_secs": 300,
    "skip_planner_for_simple": True,
    "pipeline_stages": [
        {"id": "query",     "label": "QUERY",     "enabled": False},
        {"id": "research",  "label": "RESEARCH",  "enabled": False},
        {"id": "plan",      "label": "PLAN",      "enabled": False},
        {"id": "implement", "label": "IMPLEMENT", "enabled": True},
        {"id": "doubt",     "label": "DOUBT",     "enabled": False},
    ],
}
with open(".foundry.json", "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
PY

# Pre-seed buildloop artifacts so any gate that expects them does not fail the
# build before the IMPLEMENT stage runs.
mkdir -p .buildloop
cat >.buildloop/research-report.md <<'EOF'
# Research Report
Trivial smoke task. No additional context required.
EOF
cat >.buildloop/current-plan.md <<'EOF'
# Plan: T1.1

## File Operations
### 1. CREATE hello.txt
- operation: CREATE
- content: hello world

## Verification
- run: cat hello.txt
- expect: hello world
EOF

git add -A
git commit -q -m "smoke: initial workspace"

info "running foundry run --no-tui (cap=${TIMEOUT_SECS}s)"
RUN_RC=0
if [[ -n "$TIMEOUT_CMD" ]]; then
  set +e
  "$TIMEOUT_CMD" "${TIMEOUT_SECS}s" "$FOUNDRY_BIN" run --no-tui --output-format json \
    >out.json 2>stderr.log
  RUN_RC=$?
  set -e
else
  set +e
  "$FOUNDRY_BIN" run --no-tui --output-format json >out.json 2>stderr.log
  RUN_RC=$?
  set -e
fi
info "foundry exit code: $RUN_RC"

# Check 1: foundry exited 0 (timeout=124 reported separately)
if [[ "$RUN_RC" == "124" ]]; then
  fail "foundry hit the ${TIMEOUT_SECS}s cap -- LM Studio probably stalled. See $WORK/stderr.log"
fi
[[ "$RUN_RC" == "0" ]] || fail "foundry exited with code $RUN_RC (see $WORK/stderr.log)"

# Check 2: out.json is valid JSON with the expected provider routing
python3 - <<'PY'
import json, sys, os
data = json.load(open("out.json"))
schema = data.get("schema_version")
if schema != 2:
    print(f"[smoke] FAIL: schema_version == {schema!r} (expected 2) -- headless JSON envelope changed; bump HEADLESS_REPORT_SCHEMA_VERSION in src/app/commands.rs and update this assertion + docs/local-model-setup.md", file=sys.stderr)
    sys.exit(1)
cfg = data.get("config", {})
provider = cfg.get("builder_provider", "")
model    = cfg.get("builder_model", "")
if provider != "opencode":
    print(f"[smoke] FAIL: config.builder_provider == {provider!r} (expected 'opencode')", file=sys.stderr)
    sys.exit(1)
if not model.startswith("lmstudio/"):
    print(f"[smoke] FAIL: config.builder_model == {model!r} (expected 'lmstudio/...')", file=sys.stderr)
    sys.exit(1)
tasks = data.get("tasks") or []
if not tasks:
    print("[smoke] FAIL: out.json has zero tasks recorded", file=sys.stderr)
    sys.exit(1)
print(f"[smoke] check 2: schema_version={schema} builder_provider=opencode builder_model={model} tasks={len(tasks)}")
PY

# Check 3: at least one .buildloop/logs/*.jsonl was produced
shopt -s nullglob
LOG_FILES=( .buildloop/logs/*.jsonl )
shopt -u nullglob
[[ ${#LOG_FILES[@]} -gt 0 ]] || fail "no .buildloop/logs/*.jsonl produced (builder never spawned an agent)"
echo "[smoke] check 3: ${#LOG_FILES[@]} log file(s) in .buildloop/logs/"

# Check 4: at least one log file shows an opencode session marker AND no log file
# shows a Claude stream-json system/init marker. Accept any spelling of the
# session-ID field (sessionID, session_id, sessionId) since opencode's casing
# has historically drifted between releases. Fallback assertion: every log file
# the builder produced must contain at least one parseable JSON line.
OPENCODE_HITS=0
CLAUDE_HITS=0
JSON_LINE_TOTAL=0
for f in "${LOG_FILES[@]}"; do
  if grep -Eq '"(sessionID|session_id|sessionId)"' "$f"; then
    OPENCODE_HITS=$((OPENCODE_HITS + 1))
  fi
  if grep -q '"subtype":"init"' "$f"; then
    CLAUDE_HITS=$((CLAUDE_HITS + 1))
  fi
  FILE_JSON_LINES="$(LOG_PATH="$f" python3 -c '
import json, os, sys
ok = 0
with open(os.environ["LOG_PATH"]) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            ok += 1
        except json.JSONDecodeError:
            pass
print(ok)
')"
  JSON_LINE_TOTAL=$((JSON_LINE_TOTAL + FILE_JSON_LINES))
done
[[ "$OPENCODE_HITS" -ge 1 ]] || fail "no opencode session marker (sessionID/session_id/sessionId) in any log file (opencode never ran or schema drifted)"
[[ "$CLAUDE_HITS" -eq 0 ]] || fail "found Claude stream-json 'subtype:init' in $CLAUDE_HITS log file(s) -- routing leaked to Claude"
[[ "$JSON_LINE_TOTAL" -ge 1 ]] || fail "no parseable JSON lines across ${#LOG_FILES[@]} log file(s) -- builder log is malformed (capture pipe broken or all output stripped)"
echo "[smoke] check 4: opencode_hits=$OPENCODE_HITS claude_hits=$CLAUDE_HITS json_lines=$JSON_LINE_TOTAL"

# Check 5: no typed agent error surfaced on stderr
if grep -E '\[error/(ContextOverflow|ProviderUnreachable|ModelNotLoaded)' stderr.log >/dev/null; then
  fail "typed agent error in stderr.log -- $(grep -E '\[error/' stderr.log | head -n 1)"
fi
echo "[smoke] check 5: no ContextOverflow/ProviderUnreachable/ModelNotLoaded errors"

# Check 6: TASKS.md indicator uses QRPBA convention (B for Build, A for Audit),
# not the legacy SPID convention (I for Implement, D for Doubt/Verify).
TASK_LINE="$(grep -E '^\s*- \[x\]' TASKS.md || true)"
if [[ -z "$TASK_LINE" ]]; then
  fail "no completed task in TASKS.md -- build loop did not mark T1.1 done"
fi
INDICATOR="$(echo "$TASK_LINE" | grep -oE '\[[A-Z!.\-+]{4,7}\]' || true)"
if [[ -z "$INDICATOR" ]]; then
  fail "completed task line has no pipeline indicator: $TASK_LINE"
fi
if echo "$INDICATOR" | grep -q 'I'; then
  fail "indicator $INDICATOR contains legacy 'I' (Implement) -- expected 'B' (Build). Sub-fix P33.1 may have regressed."
fi
if echo "$INDICATOR" | grep -q 'D'; then
  fail "indicator $INDICATOR contains legacy 'D' (Doubt/Verify) -- expected 'A' (Audit). Sub-fix P33.1 may have regressed."
fi
if ! echo "$INDICATOR" | grep -q 'B'; then
  fail "indicator $INDICATOR missing 'B' (Build) -- the implement stage did not register in the progress indicator"
fi
echo "[smoke] check 6: indicator=$INDICATOR (QRPBA convention, no legacy I/D)"

echo "[smoke] PASS  (workspace: $WORK)"
exit 0

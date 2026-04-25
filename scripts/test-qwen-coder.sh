#!/usr/bin/env bash
# Switch /tmp/qwen-test to use qwen3-coder-30b and relaunch foundry.
# Usage: bash scripts/test-qwen-coder.sh
set -euo pipefail

WORKDIR="${1:-/tmp/qwen-test}"
MODEL="${2:-qwen/qwen3-coder-30b}"
LMSTUDIO_URL="http://localhost:1234/v1/models"

echo "[switch] checking LM Studio at $LMSTUDIO_URL"
if ! curl -sf "$LMSTUDIO_URL" > /dev/null; then
  echo "[switch] ERROR: LM Studio not reachable. Start it first." >&2
  exit 1
fi

echo "[switch] checking $MODEL is loaded in LM Studio"
if ! curl -sf "$LMSTUDIO_URL" | jq -r '.data[].id' | grep -qFx "$MODEL"; then
  echo "[switch] ERROR: $MODEL is NOT loaded. Load it in LM Studio's GUI first (with n_ctx >= 32768)." >&2
  echo "[switch] Models currently visible to LM Studio:" >&2
  curl -sf "$LMSTUDIO_URL" | jq -r '.data[].id' | sed 's/^/  - /' >&2
  exit 1
fi

echo "[switch] preparing workspace at $WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"
[ -d .git ] || git init -q

cat > SPEC.md <<'EOF'
# Test
Verify foundry can drive a coder-tuned local model end-to-end.
EOF

cat > TASKS.md <<EOF
- [ ] T1.1: Create main.py with a hello() function that prints "hi from coder"
EOF

# Drop spurious files left by previous failed runs (e.g. UPDATED_SPECS.md from
# the append-tasks planner, stray .py files from hallucinated implements).
rm -f UPDATED_SPECS.md
find . -maxdepth 1 -name "main.py" -delete 2>/dev/null || true

if [ -f .foundry.json ]; then
  jq --arg m "lmstudio/$MODEL" --arg lm "$MODEL" \
    '.builder_model = $m | .builder_models = ["opencode:" + $m] | .local_model = $lm | .dual_selection = "first"' \
    .foundry.json > .foundry.json.tmp && mv .foundry.json.tmp .foundry.json
else
  cat > .foundry.json <<EOF
{
  "builder_provider": "opencode",
  "builder_model": "lmstudio/$MODEL",
  "builder_models": ["opencode:lmstudio/$MODEL"],
  "local_model": "$MODEL",
  "dual_selection": "first"
}
EOF
fi

rm -rf .buildloop

# Commit any pending cleanup so the TUI sees "0 dirty" and a clean main.
if [ -n "$(git status -s)" ]; then
  git add -A
  git commit -q -m "reset: clean state for qwen3-coder-30b test"
fi

echo "[switch] config:"
jq '{builder_provider, builder_model, dual_selection}' .foundry.json

echo "[switch] launching foundry (DOUBT_ENGINE=claude). Press Enter inside the TUI to start the loop."
echo "[switch] >>> DON'T touch the settings overlay -- it has a known stale-state bug (D2.1)."
echo
exec env DOUBT_ENGINE=claude foundry

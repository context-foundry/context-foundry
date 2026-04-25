#!/usr/bin/env bash
# Set up a tiny test project and launch foundry against the qwen LM Studio model.
# Usage: bash scripts/qwen-test.sh [workdir]
#   workdir defaults to /tmp/qwen-test
set -euo pipefail

WORKDIR="${1:-/tmp/qwen-test}"
LMSTUDIO_URL="http://localhost:1234/v1/models"

echo "[qwen-test] checking LM Studio at $LMSTUDIO_URL"
if ! curl -sf "$LMSTUDIO_URL" > /dev/null; then
  echo "[qwen-test] ERROR: LM Studio not reachable. Start it and load the qwen model first." >&2
  exit 1
fi

echo "[qwen-test] preparing workspace at $WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

if [ ! -d .git ]; then
  git init -q
fi

cat > SPEC.md <<'EOF'
# Test
A tiny project for verifying foundry's local-model routing.
EOF

cat > TASKS.md <<'EOF'
- [ ] T1.1: Create main.py with a hello() function that prints "hi from qwen"
EOF

echo "[qwen-test] launching foundry (DOUBT_ENGINE=claude)"
echo "[qwen-test] inside the TUI: press ? -> cycle Builder to qwen/qwen3.6-27b -> Esc -> Enter"
echo
exec env DOUBT_ENGINE=claude foundry

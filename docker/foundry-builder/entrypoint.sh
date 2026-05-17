#!/usr/bin/env bash
# foundry-builder entrypoint — establishes the Build Container Contract, then
# runs the headless build (M2 / T35.4).
#
# Contract:
#   - clean HOME, no ambient ~/.claude.json shadowing the injected credentials
#   - `claude` and `foundry` on PATH
#   - a pinned service git identity (git commit fails silently without one)
#   - a service-owned .foundry.json (mounted in by the LocalDocker backend)
#   - auth via the proxy: ANTHROPIC_BASE_URL + a per-build scoped token
#
# stdout is the json-stream event stream (captured by LocalDocker into
# jobs/<id>/logs/stream.jsonl); stderr carries human/progress noise.
set -euo pipefail

# ── Clean HOME: no ambient host config or credentials may influence a build ──
export HOME=/home/builder
rm -f "$HOME/.claude.json" /root/.claude.json 2>/dev/null || true
rm -rf "$HOME/.foundry" 2>/dev/null || true

# ── Required toolchain ───────────────────────────────────────────────────────
command -v claude  >/dev/null 2>&1 || { echo "fatal: claude CLI not on PATH" >&2; exit 1; }
command -v foundry >/dev/null 2>&1 || { echo "fatal: foundry not on PATH"   >&2; exit 1; }

# ── Auth must arrive as the per-build proxy token, never the real key ────────
# The token is delivered as ANTHROPIC_AUTH_TOKEN so the `claude` CLI sends it
# as `Authorization: Bearer` — the header the auth proxy validates.
: "${ANTHROPIC_BASE_URL:?fatal: ANTHROPIC_BASE_URL (auth proxy) not set}"
: "${ANTHROPIC_AUTH_TOKEN:?fatal: ANTHROPIC_AUTH_TOKEN (scoped proxy token) not set}"

# ── Pinned service git identity ──────────────────────────────────────────────
git config --global user.name  "Context Foundry Service"
git config --global user.email "service@build.contextfoundry.local"
git config --global init.defaultBranch main

# ── Build working tree (the LocalDocker bind mount) ──────────────────────────
cd /work
test -f .foundry.json || { echo "fatal: service .foundry.json missing" >&2; exit 1; }
test -f SPEC.md       || { echo "fatal: SPEC.md missing"               >&2; exit 1; }
test -f TASKS.md      || { echo "fatal: TASKS.md missing"              >&2; exit 1; }

# Fresh git repo so per-task commits are recorded as build provenance.
if [ ! -d .git ]; then
  git init -q
  git add -A
  git commit -q -m "chore: context foundry service build inputs" || true
fi

# ── Run the build: stdout = json-stream, stderr = noise ──────────────────────
exec foundry run --no-tui --output-format json-stream

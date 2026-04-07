#!/bin/bash
set -euo pipefail

if command -v floweyes >/dev/null 2>&1; then
  exec floweyes "$@"
fi

if [ -n "${FLOWEYES_BIN:-}" ] && [ -x "${FLOWEYES_BIN}" ]; then
  exec "${FLOWEYES_BIN}" "$@"
fi

if [ -n "${FLOWEYES_DIR:-}" ] && [ -d "${FLOWEYES_DIR}" ]; then
  exec uv run --directory "${FLOWEYES_DIR}" floweyes "$@"
fi

if [ -x ".flowise-kit/vendor/floweyes/floweyes" ]; then
  exec ".flowise-kit/vendor/floweyes/floweyes" "$@"
fi

echo "floweyes not found. Set FLOWEYES_BIN, set FLOWEYES_DIR, add floweyes to PATH, or vendor a binary at .flowise-kit/vendor/floweyes/floweyes" >&2
exit 127

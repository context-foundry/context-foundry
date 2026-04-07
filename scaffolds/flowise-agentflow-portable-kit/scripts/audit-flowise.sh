#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: scripts/audit-flowise.sh <flow.json>" >&2
  exit 2
fi

FILE="$1"
FILE_ABS="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"
SLUG="$(basename "$FILE" .json)"
OUT_DIR="artifacts/flowise"
OUT_FILE="${OUT_DIR}/${SLUG}.audit.json"

mkdir -p "$OUT_DIR"

if scripts/resolve-floweyes.sh --strict --format json "$FILE_ABS" > "$OUT_FILE"; then
  exit 0
else
  exit 1
fi

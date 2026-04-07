#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: scripts/validate-flowise.sh <flow.json>" >&2
  exit 2
fi

FILE="$1"
SLUG="$(basename "$FILE" .json)"
OUT_DIR="artifacts/flowise"
OUT_FILE="${OUT_DIR}/${SLUG}.validate.json"

mkdir -p "$OUT_DIR"

if node scripts/validate-flowise.js "$FILE" > "$OUT_FILE"; then
  exit 0
else
  exit 1
fi

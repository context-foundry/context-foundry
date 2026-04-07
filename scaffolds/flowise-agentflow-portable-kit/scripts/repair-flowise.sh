#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: scripts/repair-flowise.sh <flow.json>" >&2
  exit 2
fi

FILE="$1"
SLUG="$(basename "$FILE" .json)"
OUT_DIR="artifacts/flowise"
REPORT="${OUT_DIR}/${SLUG}.repair.md"

mkdir -p "$OUT_DIR"

VALIDATE_EXIT=0
AUDIT_EXIT=0

scripts/validate-flowise.sh "$FILE" || VALIDATE_EXIT=$?
scripts/audit-flowise.sh "$FILE" || AUDIT_EXIT=$?

{
  echo "# Flowise Repair Report"
  echo
  echo "- file: \`$FILE\`"
  echo "- validate_exit: $VALIDATE_EXIT"
  echo "- audit_exit: $AUDIT_EXIT"
  echo
  echo "## Next Action"
  if [ "$VALIDATE_EXIT" -ne 0 ]; then
    echo "- Fix structural validation errors first using \`artifacts/flowise/${SLUG}.validate.json\`."
  fi
  if [ "$AUDIT_EXIT" -ne 0 ]; then
    echo "- Fix Floweyes ACTION findings using \`artifacts/flowise/${SLUG}.audit.json\`."
  fi
  if [ "$VALIDATE_EXIT" -eq 0 ] && [ "$AUDIT_EXIT" -eq 0 ]; then
    echo "- No repair required."
  fi
} > "$REPORT"

if [ "$VALIDATE_EXIT" -eq 0 ] && [ "$AUDIT_EXIT" -eq 0 ]; then
  exit 0
fi

exit 1

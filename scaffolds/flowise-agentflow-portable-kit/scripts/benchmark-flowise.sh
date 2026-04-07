#!/bin/bash
set -euo pipefail

OUT_DIR="artifacts/flowise/benchmarks"
mkdir -p "$OUT_DIR"
SUMMARY="${OUT_DIR}/summary.md"

FILES=(
  "example-flows/afv2-patterns/01-chaining.json"
  "example-flows/afv2-patterns/02-parallel.json"
  "example-flows/afv2-patterns/03-routing.json"
  "example-flows/afv2-patterns/04-iteration.json"
  "example-flows/masterclass-2025/software-dev-team-agents.json"
  "example-flows/masterclass-2025/deep-research-agentflow.json"
  "example-flows/succession-planning-orchestrator.json"
)

PASS_COUNT=0
FAIL_COUNT=0

{
  echo "# Flowise Benchmark Summary"
  echo
  for file in "${FILES[@]}"; do
    echo "## ${file}"
    VALIDATE=0
    AUDIT=0
    scripts/validate-flowise.sh "$file" || VALIDATE=$?
    scripts/audit-flowise.sh "$file" || AUDIT=$?
    echo "- validate_exit: ${VALIDATE}"
    echo "- audit_exit: ${AUDIT}"
    echo
    if [ "$VALIDATE" -eq 0 ] && [ "$AUDIT" -eq 0 ]; then
      PASS_COUNT=$((PASS_COUNT + 1))
    else
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
  done
  echo "## Totals"
  echo
  echo "- passed: ${PASS_COUNT}"
  echo "- failed: ${FAIL_COUNT}"
} > "$SUMMARY"

cat "$SUMMARY"

if [ "$FAIL_COUNT" -eq 0 ]; then
  exit 0
fi

exit 1

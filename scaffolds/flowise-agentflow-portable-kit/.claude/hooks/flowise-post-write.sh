#!/bin/bash
set -euo pipefail

INPUT="$(cat)"
TMP_STATUS="$(mktemp)"

python3 - "$INPUT" "$TMP_STATUS" <<'PY'
import json
import sys

raw = sys.argv[1]
out = sys.argv[2]
data = json.loads(raw or "{}")
tool_input = data.get("tool_input") or {}
if not tool_input and "toolArgs" in data:
    try:
        tool_input = json.loads(data["toolArgs"] or "{}")
    except json.JSONDecodeError:
        tool_input = {}

path_value = (
    tool_input.get("file_path")
    or tool_input.get("path")
    or tool_input.get("filePath")
    or tool_input.get("target_file")
    or ""
)

json.dump(
    {
        "is_claude": "tool_name" in data,
        "path": path_value,
    },
    open(out, "w"),
)
PY

PATH_VALUE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["path"])' "$TMP_STATUS")"
IS_CLAUDE="$(python3 -c 'import json,sys; print("1" if json.load(open(sys.argv[1]))["is_claude"] else "0")' "$TMP_STATUS")"
rm -f "$TMP_STATUS"

if [[ -z "$PATH_VALUE" ]]; then
  exit 0
fi

if [[ ! "$PATH_VALUE" =~ ^(output|example-flows)/.*\.json$ ]]; then
  exit 0
fi

VALIDATE_EXIT=0
AUDIT_EXIT=0

scripts/validate-flowise.sh "$PATH_VALUE" || VALIDATE_EXIT=$?
scripts/audit-flowise.sh "$PATH_VALUE" || AUDIT_EXIT=$?

python3 - "$PATH_VALUE" "$VALIDATE_EXIT" "$AUDIT_EXIT" <<'PY'
import json
import sys
from pathlib import Path

path_value = sys.argv[1]
validate_exit = int(sys.argv[2])
audit_exit = int(sys.argv[3])
status = {
    "file": path_value,
    "validate_exit": validate_exit,
    "audit_exit": audit_exit,
    "ok": validate_exit == 0 and audit_exit == 0,
}
out = Path("artifacts/flowise/latest-status.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(status, indent=2) + "\n")
PY

if [ "$IS_CLAUDE" = "1" ] && { [ "$VALIDATE_EXIT" -ne 0 ] || [ "$AUDIT_EXIT" -ne 0 ]; }; then
  python3 - "$PATH_VALUE" <<'PY'
import json
import sys
path_value = sys.argv[1]
payload = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (
            f"Flowise checks failed for {path_value}. "
            "Read artifacts/flowise/latest-status.json and repair before stopping."
        )
    }
}
print(json.dumps(payload))
PY
fi

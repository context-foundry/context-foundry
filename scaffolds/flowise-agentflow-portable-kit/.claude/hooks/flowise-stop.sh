#!/bin/bash
set -euo pipefail

cat >/dev/null

if [ ! -f artifacts/flowise/latest-status.json ]; then
  exit 0
fi

python3 - <<'PY'
import json
from pathlib import Path

status = json.loads(Path("artifacts/flowise/latest-status.json").read_text())
if status.get("ok"):
    raise SystemExit(0)

payload = {
    "decision": "block",
    "reason": (
        "Flowise validation or audit is still failing. "
        "Read artifacts/flowise/latest-status.json, the matching validate/audit artifacts, and repair the latest flow before stopping."
    ),
}
print(json.dumps(payload))
PY

#!/bin/bash
set -euo pipefail

INPUT="$(cat)"

python3 - "$INPUT" <<'PY'
import json
import os
import sys

raw = sys.argv[1]
data = json.loads(raw or "{}")

tool_name = data.get("tool_name") or data.get("toolName") or ""
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

protected_prefixes = [
    "example-flows/",
    ".flowise-kit/corpus/",
    ".flowise-kit/manifest.json",
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/rules/",
    ".github/instructions/"
]

allow = os.environ.get("FLOWISE_KIT_ALLOW_CANONICAL_EDIT") == "1"
blocked = (
    tool_name.lower() in {"write", "edit", "multiedit", "create", "edit", "create"}
    and path_value
    and any(path_value == prefix or path_value.startswith(prefix) for prefix in protected_prefixes)
    and not allow
)

if not blocked:
    sys.exit(0)

reason = (
    f"Canonical Flowise reference path '{path_value}' is protected. "
    "Set FLOWISE_KIT_ALLOW_CANONICAL_EDIT=1 for intentional maintenance."
)

if "tool_name" in data:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
else:
    payload = {
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }

print(json.dumps(payload))
PY

# Flowise AgentFlow v2

This repository contains a Flowise AgentFlow v2 portable kit.

- Save draft flows to `output/<slug>.json`.
- Use the shared skills under `.claude/skills/` when a Flowise task is specialized enough to benefit from them.
- Do not load the entire corpus by default. Use `.flowise-kit/manifest.json` and `scripts/flowise-select-context.py` to retrieve only the relevant examples and templates.
- Treat a flow as incomplete until both `scripts/validate-flowise.sh` and `scripts/audit-flowise.sh` pass.
- Preserve audit artifacts under `artifacts/flowise/`.

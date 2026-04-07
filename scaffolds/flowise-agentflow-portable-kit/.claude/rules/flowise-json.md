---
paths:
  - "output/**/*.json"
  - "example-flows/**/*.json"
---

# Flowise JSON Rules

- Keep files as single valid JSON documents.
- Prefer exact field names from the local corpus templates over invented variants.
- Maintain explicit node IDs, edge IDs, and state wiring.
- Do not leave partial placeholder fields in committed example flows.
- Run `scripts/validate-flowise.sh` and `scripts/audit-flowise.sh` after edits.

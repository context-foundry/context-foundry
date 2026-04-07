---
paths:
  - "example-flows/**/*"
  - ".flowise-kit/manifest.json"
---

# Flowise Promotion Rules

- Only promote flows that already pass validation and audit.
- Keep promoted examples stable and reusable.
- Update `.flowise-kit/manifest.json` when a promoted flow changes retrieval behavior.
- Treat `.flowise-kit/corpus/` and `example-flows/` as canonical references. Edit them intentionally.

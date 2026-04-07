# Flowise Core Rules

- Build only Flowise AgentFlow v2 for the audited path.
- Save drafts to `output/`.
- Use the selected corpus slice from `.flowise-kit/manifest.json`; do not mass-load the corpus.
- Always run structural validation and Floweyes audit before claiming success.
- If validation or audit fails, fix the JSON instead of explaining it away.
- Preserve machine-readable artifacts under `artifacts/flowise/`.

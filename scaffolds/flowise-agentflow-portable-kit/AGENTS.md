# Flowise AgentFlow v2

Build Flowise AgentFlow v2 JSON that passes structural validation and Floweyes audit.

## Output Contract

- Save draft flows to `output/<slug>.json`.
- Treat a flow as incomplete until both checks pass:
  - `scripts/validate-flowise.sh output/<slug>.json`
  - `scripts/audit-flowise.sh output/<slug>.json`
- Do not claim success while ACTION findings remain.

## Runtime Context Rule

Do not load the entire corpus by default.

Before building or repairing a flow:

1. Classify the request against `.flowise-kit/manifest.json`.
2. Load only the selected examples, node templates, and expertise slices.
3. Prefer AgentFlow v2 examples over chatflow examples.

## Flowise Invariants

- Use correct field names for AgentFlow v2.
- Use HTML span variable references where required by the local corpus rules.
- Ensure every flow has a valid Start node.
- Keep node wiring and state updates explicit.
- Preserve validator and audit artifacts under `artifacts/flowise/`.

## Builder / Auditor Separation

- The builder generates or edits the JSON.
- The auditor reviews with fresh context and should not merely repeat the builder's rationale.
- The auditor must use validation and Floweyes findings as primary evidence.

## Promotion Rule

When a draft becomes a durable reference:

1. Move or copy it into `example-flows/`.
2. Update `.flowise-kit/manifest.json` if it changes the retrieval set.
3. Add newly learned stable patterns back to the canonical source corpus during maintenance.

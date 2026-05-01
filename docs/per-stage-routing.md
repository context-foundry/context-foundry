# Per-Stage Routing

Foundry's pipeline normally routes all stages through a single provider selected
via `Ctrl+D` (arena toggle) or the Builder row in the Settings Overlay. Per-stage
routing overrides let you pin individual stages to different providers and models
while the rest of the pipeline follows the global selection.

## Use case

Run Claude Opus 4.7 on Plan and Audit (where reasoning quality matters most) while
running Codex on Build (where speed and cost matter more). Or pin Discovery to a
cheaper model while keeping the builder on Opus.

## How it works

### Runtime resolution

`Config::active_routing_for_stage(stage_id)` is the single source of truth. Both
the TUI display and agent dispatch call this method rather than reading
`*_provider` / `*_model` fields directly.

Resolution order:
1. If `stage_id` is listed in `stage_overrides`, the stage keeps its own
   `*_provider` / `*_model` fields unchanged, even when `for_pipeline()` would
   override them with the global builder selection.
2. Otherwise, `for_pipeline()` overrides the stage's provider to match the
   global selection.

### Global builder cycle interaction

When the user presses `Ctrl+D` to cycle the global builder (e.g. from Claude to
Codex), `for_pipeline()` overrides every stage's provider -- **except** stages
listed in `stage_overrides`. Those pinned stages remain on their configured
provider regardless of the global cycle.

## Configuration

Per-stage overrides are stored in `.foundry.json`. Two pieces of data work
together:

1. **Per-stage fields** -- each stage has its own `*_provider` and `*_model`
   fields (e.g. `planner_provider`, `planner_model`).
2. **`stage_overrides` array** -- lists which stage IDs are pinned. Only stages
   in this array keep their own fields when `for_pipeline()` runs.

### JSON shape

```json
{
  "builder_provider": "codex",
  "builder_model": "",

  "planner_provider": "claude",
  "planner_model": "opus",

  "reviewer_provider": "claude",
  "reviewer_model": "opus",

  "stage_overrides": ["plan", "audit"]
}
```

In this example:
- **Plan** is pinned to Claude Opus (listed in `stage_overrides`)
- **Audit** is pinned to Claude Opus (listed in `stage_overrides`)
- **All other stages** (Query, Research, Build, Discovery, Fixer, Patterns)
  follow the global builder selection -- here, Codex

### Supported stage IDs

| Stage ID | Provider field | Model field | Aliases |
|----------|---------------|-------------|---------|
| `scout` | `scout_provider` | `scout_model` | -- |
| `query` | `query_provider` | `query_model` | -- |
| `research` | `research_provider` | `research_model` | -- |
| `plan` | `planner_provider` | `planner_model` | -- |
| `build` | `builder_provider` | `builder_model` | `implement` |
| `audit` | `reviewer_provider` | `reviewer_model` | `doubt` |
| `discovery` | `discovery_provider` | `discovery_model` | `discover` |
| `fixer` | `fixer_provider` | `fixer_model` | -- |
| `pattern_extraction` | `pattern_extraction_provider` | `pattern_extraction_model` | `patterns` |
| `pr_review` | `pr_review_provider` | `pr_review_model` | -- |

Aliases are accepted interchangeably in both `stage_overrides` and
`active_routing_for_stage()`.

## Settings Overlay

The Settings Overlay (`?` to open) exposes per-stage routing under the
**Routing** section. Below the Arena and Builder rows, each stage has its own
row (Query, Research, Plan, Build, Audit, Discovery, PR Review, Patterns, Fixer).

Press **Enter** on a stage row to open the Model Picker dropdown. The picker
shows all available models grouped by provider (Claude, Codex, LM Studio, Ollama).
Selecting a model from the picker:

1. Writes the stage's `*_provider` and `*_model` fields to `.foundry.json`
2. Adds the stage ID to `stage_overrides` if not already present
3. The stage is now pinned -- global builder cycling will not affect it

To **unpin** a stage (return it to following the global selection), select the
"(use global)" or default entry in the picker, which removes the stage from
`stage_overrides`.

See [`docs/settings-overlay.md`](settings-overlay.md) for the full overlay
reference.

## Worked example

**Goal:** Claude Opus 4.7 on Plan, Codex on Build, Claude Opus 4.7 on Audit.

1. Open the Settings Overlay (`?`)
2. Navigate to "Plan" under Routing, press Enter
3. Select "Claude Opus 4.7" from the Model Picker
4. Navigate to "Audit", press Enter
5. Select "Claude Opus 4.7"
6. Navigate to "Builder", cycle to Codex (or pick from the dropdown)
7. Press Esc to close the overlay

Resulting `.foundry.json`:
```json
{
  "planner_provider": "claude",
  "planner_model": "opus",
  "builder_provider": "codex",
  "builder_model": "",
  "reviewer_provider": "claude",
  "reviewer_model": "opus",
  "stage_overrides": ["plan", "audit"]
}
```

When `Ctrl+D` cycles the global builder from Codex to Claude, Plan and Audit
remain on Claude Opus -- only the non-pinned stages change.

## Implementation references

- `Config::stage_overrides` -- `src/config.rs:437`
- `Config::for_pipeline()` -- `src/config.rs:1212` (skips overridden stages)
- `Config::active_routing_for_stage()` -- `src/config.rs:1351`
- `Config::set_stage_routing()` -- `src/config.rs:1385` (writes override to JSON)
- `Config::clear_stage_routing()` -- `src/config.rs:1420` (removes override)
- Settings sections definition -- `src/app/state.rs:365` (`settings_sections()`)

## Related docs

- [Settings Overlay](settings-overlay.md) -- full overlay reference
- [Progress Indicators](progress-indicators.md) -- QRPBA letters map to stage IDs
- [README.md](../README.md) -- dual-model arena and pipeline overview

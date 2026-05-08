# Settings Overlay

The Settings Overlay is a modal panel that exposes foundry's ~40 user-tunable
configuration fields organized into 9 collapsible sections. All changes persist
to `.foundry.json` in the project directory.

## Opening and closing

| Action | Effect |
|--------|--------|
| Press `?` | Open the overlay from any TUI screen |
| Press `Esc` | Close the overlay (from any state -- field editing, model picker, or browse) |
| Click outside the modal | Close the overlay |
| Click `[ X ]` button | Close the overlay (top-right corner of the modal) |

When you close the overlay after making changes, a **confirm banner** appears:
`Save changes? [y] save  [n] discard  [Esc] back`. Press `y` to persist, `n` to
discard, or `Esc` to return to the overlay.

## Modal chrome

The overlay renders as a 90% width x 80% height modal centered on the terminal,
with a minimum size of 80x24 characters. A drop shadow appears offset 1 column
right and 1 row down. The title bar reads "Settings -- Foundry" in the accent
color, with a clickable `[ X ]` close button at the top-right.

If the terminal is smaller than 80x24, the overlay falls back to full-screen.

## Navigation

| Key | Action |
|-----|--------|
| Up/Down arrows | Move focus between rows |
| Enter or Space | Toggle booleans, open Model Picker for stage/enum rows |
| Left/Right arrows | Cycle enum values (run mode, theme, etc.) |
| Esc | Close overlay / close picker / cancel editing |
| Mouse click | Select any row; click `[ X ]` to close |

## Sections

The overlay has 9 sections. Each section is collapsible -- press Enter on a
section header to expand or collapse it. Sections marked **(expanded)** are open
by default; all others start collapsed.

### 1. Routing **(expanded)**

Controls which AI provider and model runs each pipeline stage.

| Field | Type | Description |
|-------|------|-------------|
| Arena | Enum | Global builder selection: solo first / solo second / dual pipeline (`Ctrl+D` equivalent) |
| Builder | Enum | Active builder `provider:model` (cycles through configured `builder_models` plus discovered local models) |
| Query | Stage picker | Per-stage model override -- opens Model Picker |
| Research | Stage picker | Per-stage model override |
| Plan | Stage picker | Per-stage model override |
| Build | Stage picker | Per-stage model override |
| Audit | Stage picker | Per-stage model override |
| Discovery | Stage picker | Per-stage model override |
| PR Review | Stage picker | Per-stage model override |
| Patterns | Stage picker | Per-stage model override |
| Fixer | Stage picker | Per-stage model override |

Per-stage overrides are documented in detail in
[`docs/per-stage-routing.md`](per-stage-routing.md).

<!-- screenshot: routing-section-expanded.png -->

### 2. Pipeline behavior **(expanded)**

Controls how the build loop processes tasks.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Run Mode | Enum | `auto` | `auto` / `sprint` / `review` |
| Pipeline Mode | Enum | `full` | `full` / `fast` / `backpressure` |
| Plan Review | Bool | `false` | Review plan before building |
| Review Mode | Enum | `diff-only` | `diff-only` / `full-file` |
| Skip Planner (simple) | Bool | `true` | Simple tasks skip the plan stage |
| Skip Scout (simple) | Bool | `true` | Simple tasks skip the scout stage |
| Skip Doubt (simple) | Bool | `true` | Simple tasks skip the audit stage |
| Batch Doubt | Bool | `true` | Defer audit to end of session |
| Planner Lookahead | Bool | `true` | Pre-plan next task while building current one |
| Planning Iterations | Number | `0` | 0 = single pass planner |
| Doubt Engine | Enum | `claude` | `claude` / `codex` |
| Confidence Threshold | Number | `0.5` | 0.0-1.0; findings below this are logged only, not auto-fixed |
| Parallel Builder | Bool | `false` | Fork builder across files |
| Parallel Min Files | Number | `3` | Minimum files to trigger parallel build |

<!-- screenshot: pipeline-section.png -->

### 3. Budgets & timeouts **(expanded)**

Controls timing, cost limits, and backoff behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Agent Timeout (secs) | Number | `600` | Idle timeout per agent (hard timeout = 4x = 40 min) |
| Pause Between Tasks | Number | `10` | Seconds between tasks |
| Pause Between Agents | Number | `3` | Seconds between agent spawns within a task |
| Pause Between Cycles | Number | `30` | Seconds between discovery cycles |
| Adaptive Pauses | Bool | `true` | Auto-adjust pause timing based on rate limits |
| Cost Limit (USD) | Number | `0.0` | 0.0 = unlimited |
| Overrun Threshold | Number | `10` | % over budget before warning |
| Budget Recovery | Bool | `false` | Auto-recover from budget overrun |
| Discovery Cooldown | Number | `5` | Minutes between discovery rounds |

The `agent_timeout_secs` default is `600` (10 min idle, hard timeout 4x = 40 min).
It was briefly `180` between commits `5854172` and the bump back to `600`, but
180s caused infinite WIP-retry loops on planning-heavy tasks where Opus thinks
for 3+ minutes before emitting its first tool call. Override here or in
`.foundry.json` if your tasks need different agent run lengths.

<!-- screenshot: budgets-section.png -->

### 4. Local models

Configuration for LM Studio and Ollama integration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Local Model | Readonly | (empty) | Shows currently selected local model |
| Ollama URL | Editor | `http://127.0.0.1:11434` | Ollama API endpoint |
| Embedding Model | Editor | `nomic-embed-text` | Model for semantic pattern matching |
| Embedding Timeout (ms) | Number | `2000` | Timeout for embedding requests |
| Semantic Match | Bool | `true` | Enable embedding-based pattern matching |

See [`docs/local-model-setup.md`](local-model-setup.md) for the full local model
runbook.

<!-- screenshot: local-models-section.png -->

### 5. Sandbox & security

Docker isolation and security controls.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Sandbox | Bool | `true` | Docker isolation for agents |
| Sandbox Image | Editor | `foundry-sandbox:latest` | Docker image name |
| Phase Isolation | Bool | `true` | Isolate build phases |
| Semgrep | Bool | `false` | Run static analysis on agent output |
| Human Approval | Bool | `false` | Require human approval before commit |
| Phase RBAC | Bool | `true` | Enforce role-based access per phase |

<!-- screenshot: sandbox-section.png -->

### 6. Discovery & patterns

Controls for task archiving and pattern injection.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Auto Archive | Bool | `true` | Archive completed tasks |
| Archive Keep First | Number | `3` | Keep N first tasks visible in TASKS.md |
| Archive Keep Last | Number | `3` | Keep N last tasks visible |
| Max Patterns | Number | `10` | Max patterns injected per task |
| Min Patterns | Number | `2` | Min patterns injected per task |
| History Results | Number | `5` | Max history entries in scout prompt |

<!-- screenshot: discovery-section.png -->

### 7. Git & PR

Git integration and pull request behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Auto Push Remote | Editor | (empty) | Git remote name for auto-push; empty = off |
| Issue on WIP | Bool | `false` | Create GitHub issue on WIP commits |
| PR Review Concurrency | Number | `4` | Parallel file reviews in PR review mode |
| PR Poll Interval | Number | `30` | Seconds between PR approval checks |
| Dashboard Port | Number | `9400` | Port for the web dashboard |

<!-- screenshot: git-section.png -->

### 8. Display & theme

Visual preferences.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Theme | Enum | `dark` | TUI color theme |
| Preview Wrap | Bool | `false` | Wrap long lines in file preview |

<!-- screenshot: display-section.png -->

### 9. Extensions & hooks

Extension selection and lifecycle hooks.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Extensions | Editor | (empty) | Active extension list (comma-separated) |
| On Task Complete | Editor | (empty) | Shell hook after each task commit |
| Build Command | Editor | (empty) | Custom build/verify command |

<!-- screenshot: extensions-section.png -->

## Inline editing rules

Different field types have different editing behaviors:

| Field type | Interaction |
|------------|-------------|
| **Bool** | Space or Enter toggles between `true` / `false`. Checkbox icon updates. |
| **Enum** | Left/Right arrows cycle through valid values. Enter opens a picker if available. |
| **Number** | Enter opens inline editor. Type the value, press Enter to save. |
| **Editor** | Enter opens inline editor (for free-form strings like paths, URLs, shell commands). Type the value, press Enter to save. Backspace deletes. Ctrl+U clears. |
| **Readonly** | Display-only, not editable. |
| **StagePicker** | Enter opens the Model Picker dropdown. |

For inline editing: a cursor (`_`) appears after the current value. The status
bar shows "editing {field} -- Enter save, Ctrl+U clear". Press Esc to cancel
without saving. Invalid values (e.g. non-numeric input for a Number field)
show a yellow warning in the status bar.

## Model Picker dropdown

The Model Picker is a floating popup that appears when you press Enter on a
Builder or Stage Picker field. It lists all available models grouped by provider.

### Features

- **Provider groups** -- collapsible headers (Claude, Codex, LM Studio, Ollama).
  Press Enter on a group header to expand/collapse.
- **Filter bar** -- press `/` to activate filtering. Type to filter models by
  name. Press Esc to clear filter or close the picker.
- **Radio selection** -- the currently active model shows a filled radio button.
  Press Enter to select a different model.
- **Scroll** -- Up/Down arrows navigate; the list scrolls when items exceed the
  popup height.
- **Mouse** -- click any row to select it.

### Behavior for stage pickers

When selecting a model for a stage picker (Query, Plan, Build, etc.):
- The selected model's provider and model are written to `.foundry.json`
- The stage ID is added to `stage_overrides`
- The stage is now **pinned** -- global builder cycling does not affect it

See [`docs/per-stage-routing.md`](per-stage-routing.md) for details.

## Persistence

All settings persist to `.foundry.json` in the project directory. Global defaults
in `~/.foundry/config.json` apply when project-level values are absent. Changes
made in the overlay are written on save (confirm `[y]`); discarding (`[n]`)
reverts to the pre-overlay state.

## Related docs

- [Per-stage routing](per-stage-routing.md) -- how stage overrides work
- [Eval harness](eval-harness.md) -- per-run plumbing and heuristic grading; the Pipeline Health section is its primary UI surface
- [Progress indicators](progress-indicators.md) -- QRPBA letters for pipeline stages
- [Local model setup](local-model-setup.md) -- LM Studio + opencode configuration
- [README.md](../README.md) -- project overview

# Multi-Model Studio Plan

## Goal

Add a new interactive `foundry studio` mode that lets a user:

- inspect the current project directory
- write a natural-language build/report prompt
- run Claude Code, Codex, or both against that prompt
- choose whether both models share the same workspace or use isolated workspaces
- surface generated artifacts, especially self-contained HTML reports/dashboards

The existing autonomous build loop stays intact. The studio mode is additive.

## Review Findings From The Current Rust App

1. The runtime is Claude-specific today.
   `src/agent.rs` hardcodes the `claude` CLI and Claude stream parsing, so Codex cannot be plugged in without a provider abstraction.

2. The current TUI is status-only.
   `src/tui.rs` renders a live build loop, but there is no prompt editor, provider selector, workspace selector, or multi-session layout.

3. Stop-after-task is incomplete.
   `src/app.rs` tracks `stop_after_task` in UI state, but the build loop only checks for a `.buildloop/stop` file that the TUI never writes.

4. Task parsing is narrower than the README examples.
   `src/task.rs` expects IDs like `A1.1:` while the README shows `1.1:`. That mismatch is unrelated to studio mode, but it should be corrected later.

## Design

### 1. New Command Surface

Add a `studio` subcommand:

```bash
foundry --dir /path/to/project studio
```

This launches a separate interactive TUI dedicated to prompt-driven work rather than the autonomous task loop.

### 2. Provider Abstraction

Create a provider/runtime layer that supports:

- `Claude`
- `Codex`

Each provider defines:

- CLI executable name
- default model string
- command arguments for non-interactive execution
- output parsing strategy
- whether the provider needs a git repo check bypass in isolated workspaces

### 3. Prompt Smoothening

Before launching a model, the raw user prompt is wrapped with:

- a repository scan summary
- artifact/report instructions
- workspace/output path instructions
- provider-neutral delivery rules

The smoothed prompt will explicitly instruct the model to:

- inspect the repository before editing
- preserve the existing stack and conventions
- produce a self-contained HTML report when the request implies a report/dashboard
- write artifacts under `.foundry/studio/artifacts/...`
- describe what it changed and where to open the artifact

### 4. Workspace Modes

Support two workspace modes:

- `shared`
  Both providers run in the main project directory.

- `isolated`
  Each provider gets its own snapshot workspace under `.foundry/studio/workspaces/<provider>/`.

The isolated mode is the default because it avoids collisions when both models edit simultaneously.

The snapshot copy should skip heavy/generated paths:

- `.git`
- `target`
- `node_modules`
- `.venv`
- `venv`
- `__pycache__`
- `.pytest_cache`
- `.ruff_cache`
- `.build-venv`
- `.foundry/studio`

Codex should use `--skip-git-repo-check` in isolated mode because the snapshot is not a full git checkout.

### 5. Directory Scan

Add a lightweight local scan that summarizes:

- top-level files/directories
- detected stack signals (`Cargo.toml`, `package.json`, `pyproject.toml`, etc.)
- likely data/report inputs (`csv`, `json`, `db`, `sqlite`, `parquet`, `md`)
- likely frontend/report output areas (`public`, `dist`, `apps`, `tools`)

This summary is shown in the TUI and injected into the smoothed prompt.

### 6. Studio TUI

Add a dedicated TUI with these areas:

- header: project, provider mode, workspace mode, key hints
- project scan pane
- prompt editor pane
- smoothed prompt preview pane
- sessions pane
- output pane for the selected session
- artifacts/log pane

Keyboard controls:

- `Tab`: cycle focus
- `e`: toggle prompt edit mode
- `p`: cycle provider target (`claude`, `codex`, `both`)
- `w`: cycle workspace mode (`isolated`, `shared`)
- `r`: refresh directory scan + smoothed prompt
- `s`: start run
- `j` / `k`: change selected session
- `q`: quit

### 7. Session Execution

When the user starts a run:

- create one session per selected provider
- create/refresh isolated workspaces if needed
- assign an artifact directory per session
- launch both sessions concurrently when provider mode is `both`
- stream each session into its own buffer
- detect generated `.html` files under the session artifact directory and workspace

### 8. Verification

Implementation must include:

- `cargo fmt`
- `cargo test`
- at least unit tests for:
  - prompt smoothing includes artifact instructions
  - workspace ignore rules
  - directory scan stack detection
  - basic provider output parsing helpers

## Implementation Order

1. Add the plan file.
2. Add provider/runtime abstractions and workspace preparation helpers.
3. Add studio prompt composition and project scanning.
4. Add the `studio` command and TUI.
5. Add tests and run verification.

## Explicit Non-Goals For This Pass

- multi-turn resume across provider sessions
- merging changes automatically back from isolated workspaces
- browser auto-open for generated HTML artifacts
- replacing the existing autonomous loop

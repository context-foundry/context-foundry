# Foundry Studio

Foundry Studio is a separate mode from the autonomous `foundry run` loop.

The loop works from `IMPL_PLAN.md`, runs a fixed multi-stage workflow, reviews the result, and commits progress automatically.

Studio is interactive and prompt-driven. You point it at a repository, describe what you want, and run Claude, Codex, or both against that request inside the current project or isolated snapshots.

The prompt starts blank by default.

## What Studio Is For

Use `foundry studio` when you want:

- one-off app building, dashboards, reports, prototypes, or repo analysis
- direct prompt control instead of task-list automation
- side-by-side Claude and Codex runs
- isolated workspaces so two model runs do not collide
- a visible execution brief, live output, and captured artifacts

Use `foundry run` when you want:

- the autonomous plan/build/review/fix/discover loop
- progress tracked from `IMPL_PLAN.md`
- automatic review gating and git commits
- pattern learning integrated into the loop

## Command

```bash
foundry --dir /path/to/project studio
```

## Provider Support

Studio can run:

- `Claude`
- `Codex`
- `Both`

At startup, Studio probes each provider before allowing runs:

- CLI availability
- required CLI features
- authentication status
- a cached live smoke check

If a provider is not ready, Studio fail-closes and shows the reason in the UI instead of failing halfway through a run.

## Workspace Modes

Studio supports two workspace modes:

- `isolated`
  Each provider gets its own snapshot workspace under `.foundry/studio/workspaces/<provider>/`
- `shared`
  Runs directly in the project directory

`isolated` is the default and is safer when running both providers.

Artifacts are written under:

```text
<workspace>/.foundry/studio/artifacts/<run>/<provider>/
```

Each session saves its execution brief as:

```text
execution-brief.md
```

## What Studio Sends To The Model

Studio does not use the autonomous loop prompts from `src/prompts.rs`.

Instead, it builds a single execution brief that includes:

- your raw prompt
- a lightweight project scan
- the workspace path the model is allowed to work in
- the artifact directory it should write to
- delivery guidance for reports, dashboards, and HTML artifacts
- follow-up context from the selected prior session when you continue a run

This brief is shown in the `Execution Brief` pane and saved per session so you can inspect exactly what was sent.

## Execution Contracts

Studio applies exactly one execution contract to a run.

Contracts are stored as Markdown files under:

```text
.foundry/studio/contracts/
```

A contract is additional instruction text layered on top of your prompt before a run starts. This is what lets you change the execution brief without editing Studio code.

Studio supports:

- selecting one contract at a time
- adding a new contract
- editing the selected contract
- deleting the selected contract

Studio does not stack multiple contracts onto one prompt.

Supported placeholders inside contract files:

- `{{workspace_dir}}`
- `{{artifact_dir}}`
- `{{provider_label}}`

Studio tracks an editor selection inside the app.

- Press `v` to cycle editors between `system`, `nano`, `vi`, and `code --wait`
- The current selection is shown in the header and contracts pane
- The selection persists under `.foundry/studio/.editor`

When the selection is `system`, Studio uses `$VISUAL`, then `$EDITOR`, then `vi`.

When you add or edit a contract, Studio first shows a short help overlay that:

- tells you which editor command will open
- shows common save/exit shortcuts for that editor
- lets you press `v` to switch editors, `Enter` to open, or `Esc` to cancel

Deleting a contract now opens a confirmation prompt. Press `y` to confirm or `n` / `Esc` to cancel.

If you keep the `system` selection and do not want the default `vi` fallback, set one of these before launching Studio:

```bash
export VISUAL="nano"
export EDITOR="code --wait"
```

## UI Layout

Studio has seven main panes:

- `Project Scan`
- `Prompt`
- `Execution Contracts`
- `Execution Brief`
- `Sessions`
- `Output`
- `Artifacts + Log`

The status bar shows:

- current mode
- focused pane
- prompt size
- session count

The sessions pane shows:

- selected session
- provider
- running/done/failed status
- spinner while active
- event count
- elapsed time

The activity pane shows:

- Claude readiness
- Codex readiness
- workspace path
- execution brief path
- artifact directory
- last-event heartbeat
- recent logs

## Controls

Keyboard:

- `e` enter prompt edit mode
- `c` cycle execution contract
- `v` cycle editor
- `a` add a new execution contract
- `x` edit the selected execution contract
- `d` delete the selected execution contract
- `s` start a fresh run
- `f` continue from the selected session
- `p` cycle provider mode
- `w` cycle workspace mode
- `r` rescan the project
- `j` / `k` switch selected session
- `Up` / `Down` move execution contracts when that pane is focused, or scroll output when the output pane is focused
- `Tab` / `Shift+Tab` cycle pane focus
- drag the visible split bars with the mouse to resize columns left/right and pane stacks up/down
- use the mouse wheel or trackpad over `Execution Brief` or `Output` to scroll that pane
- `q` quit
- `Ctrl+C` quit

Mouse:

- click a pane to focus it
- click the prompt pane to enter edit mode
- click a session row to select it
- drag the visible split bars between panes to resize them
- scroll in the `Execution Brief` or `Output` pane

## Follow-Up Runs

Press `f` to continue from the selected session.

A follow-up:

- targets the selected session's provider only
- reuses the selected session's workspace
- includes recent prior output as follow-up context
- refuses to start if that workspace no longer exists

This is meant for continuing a Claude run as Claude or a Codex run as Codex. It does not switch providers across follow-ups.

## Output And Artifacts

Studio streams visible model output and tool activity into the `Output` pane.

It does not expose hidden chain-of-thought. What you get is:

- visible text output
- tool-use events
- tool-result previews
- stderr/status messages
- final result text when available

Artifacts are discovered from the session artifact directory first, then from the workspace if needed. Studio currently looks for recent:

- `.html`
- `.htm`
- `.md`
- `.json`

This makes Studio especially useful for:

- HTML dashboards
- self-contained reports
- generated specs
- machine-readable outputs

## Config

Studio reads `.foundry.json` from the target project.

Relevant fields:

```json
{
  "studio_claude_model": "opus",
  "studio_codex_model": ""
}
```

Notes:

- `studio_claude_model` defaults to `opus`
- `studio_codex_model` defaults to empty, which means "use the Codex CLI default model"

## Important Differences From The Loop

Studio is not a lighter skin over `foundry run`. It is a different workflow.

`foundry run`:

- works from `IMPL_PLAN.md`
- uses the fixed loop prompts in `src/prompts.rs`
- runs planning, implementation, review, fixing, and discovery
- can commit and push work

`foundry studio`:

- starts from a free-form user prompt
- uses the Studio execution brief built from the `src/studio/` prompt/state modules
- does not run the plan/review/fix loop
- does not commit or push automatically
- is designed for interactive exploration and artifact generation

## Current Limits

Studio currently does not:

- auto-merge isolated workspace changes back into the main project
- show hidden model reasoning
- switch providers mid-follow-up
- open artifacts automatically in a browser

## Related Files

- `src/studio/` — Studio TUI app shell, state/model modules, provider/session logic, and UI rendering/input
- `src/agent.rs` — Claude/Codex provider execution and stream parsing
- `docs/multi-model-studio-plan.md` — implementation plan and design notes
- `README.md` — top-level Foundry loop documentation

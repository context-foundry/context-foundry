# Handoff: GitHub Agent Phase 36

Date: 2026-05-22 night, America/Chicago
Pickup target: 2026-05-23 morning

## Current state

- PR is open: https://github.com/context-foundry/context-foundry/pull/273
- Remote PR branch: `origin/phase36/github-agent`
- Local clean branch pointer: `phase36/github-agent`
- No tag was pushed.
- No release was cut.
- No GitHub secrets or labels were changed.
- Do not push local `main` directly. It is still `ahead 3, behind 13`; the clean rebased stack is on `phase36/github-agent`.

## Commit mapping

Local `main` has the original three local commits:

- `09f1d1f` - `feat(T36.1-T36.6): repo-aware headless Foundry for GitHub agents`
- `3627f05` - `fix(T36.5): address audit findings -- honor repo routing, widen allowlist, harden triggers`
- `786e082` - `chore(release): prepare v4.1.0`

The PR branch has the same work rebased onto current `origin/main`:

- `d4983b7` - `feat(T36.1-T36.6): repo-aware headless Foundry for GitHub agents`
- `5e6a308` - `fix(T36.5): address audit findings -- honor repo routing, widen allowlist, harden triggers`
- `331eccd` - `chore(release): prepare v4.1.0`

## What Phase 36 adds

- No new standalone CLI was created. It extends the existing `foundry` CLI.
- The new GitHub path runs:

```bash
foundry run --no-tui --output-format json-stream --profile ci
```

- GitHub Actions is the UI/launcher:
  - `workflow_dispatch` or trusted issue label starts work.
  - The runner checks out the repo, creates a branch, writes `SPEC.md` / `TASKS.md`, runs Foundry, pushes, opens a PR, posts a check/comment, and uploads `.buildloop`.
- Foundry itself is still the brain/runtime. GitHub provides the repo checkout, token, PRs, checks, comments, and artifacts.

## Validation already done

Local validation passed:

```bash
cargo check --bin foundry
cargo test --bin foundry provider_allowlist
cargo test --bin foundry load_layered
actionlint .github/workflows/foundry-agent.yml
python3 -m py_compile scripts/foundry-ci-report.py
git show --check --stat HEAD
git diff --check
```

Remote PR checks:

- `Foundry PR Review`: passed
  - https://github.com/context-foundry/context-foundry/actions/runs/26321577882/job/77491419975
- `Build Service Smoke`: passed
  - https://github.com/context-foundry/context-foundry/actions/runs/26321577898/job/77491420007
- `Check & Test`: failed in `cargo clippy`
  - https://github.com/context-foundry/context-foundry/actions/runs/26321577898/job/77491420008

## Current blocker

CI failed only in clippy. The failures appear unrelated to the Phase 36 behavior, but they block merge because CI runs with `-D warnings`.

Clippy errors from run `26321577898`:

1. `src/app.rs:3959`
   - `clippy::collapsible_match`
   - Collapse `MouseEventKind::Up(MouseButton::Left)` + nested `if state.dragging_split` into a guarded match arm.

2. `src/app.rs:6282`
   - `clippy::collapsible_match`
   - Collapse `MouseEventKind::Down(MouseButton::Right)` + nested `if tui::rect_contains(...)` into a guarded match arm.

3. `src/tui/overlays.rs:2728`
   - `clippy::unnecessary_min_or_max`
   - Replace:

```rust
total_lines.saturating_sub(1).max(0)
```

   with:

```rust
total_lines.saturating_sub(1)
```

4. `src/skills.rs:2627`
   - `clippy::unnecessary_sort_by`
   - Replace:

```rust
scored.sort_by(|a, b| b.1.cmp(&a.1));
```

   with:

```rust
scored.sort_by_key(|b| std::cmp::Reverse(b.1));
```

## Local dirty files to avoid

The current checkout has unrelated dirty files. Do not include them in the PR unless intentionally continuing that separate work:

- `.claude/rules/plugins.md`
- `CLAUDE.md`
- `docs/OVERVIEW.html`
- `docs/ROUNDUP.html`
- `plugins/recon/CLAUDE.md`
- `plugins/recon/skills/fleet-recon/SKILL.md`
- `plugins/workday-agents/CLAUDE.md`
- `plugins/workday-agents/skills/compliance-agent-architecture/SKILL.md`
- `scaffolds/flowise-agentflow-portable-kit/.flowise-kit/corpus/node-templates/CONTEXT-FOUNDRY-ASSISTANT-PROMPT.md`
- `symphony-vs-context-foundry.html`

## Suggested morning sequence

1. Work from the clean PR branch, not dirty local `main`.

```bash
git fetch origin
git switch phase36/github-agent
```

If the dirty local files block switching, use a new worktree outside this checkout:

```bash
git worktree add /private/tmp/context-foundry-pr273 phase36/github-agent
cd /private/tmp/context-foundry-pr273
```

2. Fix the four clippy warnings listed above.

3. Validate locally:

```bash
cargo clippy --all-targets -- -D warnings
cargo check --bin foundry
actionlint .github/workflows/foundry-agent.yml
python3 -m py_compile scripts/foundry-ci-report.py
```

4. Commit and push to the PR branch:

```bash
git add src/app.rs src/tui/overlays.rs src/skills.rs
git commit -m "fix: satisfy clippy on PR 273"
git push origin phase36/github-agent
```

5. Wait for PR checks.

```bash
gh pr checks 273 --repo context-foundry/context-foundry --watch
```

6. After PR #273 is reviewed and merged, release steps are:

```bash
git fetch origin
git tag v4.1.0 origin/main
git push origin v4.1.0
```

That triggers `release.yml` and publishes `foundry-linux.tar.gz` with the new `--profile` flags.

7. After the release exists, finish the GitHub Agent integration gate:
   - Add repo secret: `ANTHROPIC_API_KEY`
   - Create repo label: `foundry-agent`
   - Dispatch a trivial `Foundry Agent` workflow task
   - Confirm clean-runner Claude auth works

## Product explanation to keep straight

For a new app repo, do not copy Foundry source into the app. The app repo only needs the workflow, optional `.foundry.json`, and the model secret. The workflow installs the released Foundry binary at runtime, runs it against that repo, and opens a PR.

Future cleanup target: convert the workflow into a reusable GitHub Action or GitHub App so setup becomes closer to "install Context Foundry, add secret, run task" instead of copying a workflow file.

# Plan: Repo-aware headless Foundry for GitHub agents (v3, post-convergence)

Date: 2026-05-22
Version: v3
Status: implemented locally; release + clean-runner smoke pending

## Audit changelog (vs v2)

v2 described "Architecture B" -- keep the VPS running `foundry serve` as the engine,
add `/v1/skills` + `/v1/plugins` endpoints, build an `npm` MCP wrapper with 8 tools,
wire a GitHub App, and deploy via `gh`. Three rounds of audit in conversation
(2026-05-22) rejected that ordering. The reasons:

- **The execution primitive already exists.** `foundry run --no-tui --output-format
  json-stream` (src/main.rs:61) -> `app::run_headless` (src/app/commands.rs:467)
  already runs against the current checkout, loads merged Config (global -> project
  `.foundry.json`, src/config.rs:980), respects per-stage routing, writes
  `.buildloop`, makes per-task `feat:`/`WIP:` commits (src/git.rs), and emits a
  versioned `SessionReport` with commits/cost/findings/typed_error
  (src/app/commands.rs:797). A new `run-repo` command would duplicate
  `Commands::Run`.
- **v2 built surfaces before the primitive.** Skill endpoints, an MCP wrapper, and a
  GitHub App are integration scaffolding. They are not what makes Foundry a GitHub
  coding agent; a repo-aware headless run that opens a PR is.
- **The VPS is not required.** In a GitHub runner `actions/checkout` already places
  the repo on disk, and the runner token already pushes and opens PRs. So
  "repo-aware" needs zero clone logic and no remote build service in v1.
- **v2 would have lost per-stage model control.** The service build profile
  hard-pins providers and clears `stage_overrides` (src/service/localdocker.rs:44).
  The fix is a profile overlay, not a remote service.

This v3 supersedes v2. The task breakdown lives in `TASKS.md` Phase 36.

## Context

Run Context Foundry's QRPBA pipeline (Query / Research / Plan / Build / Audit)
against an existing GitHub repository, from a GitHub Actions runner, landing the
work as per-task commits on a branch with a PR. The same headless primitive also
serves VS Code and (later, optionally) the Copilot cloud agent. The TUI stays a
local-only frontend.

**Architecture: repo-aware headless Foundry.** The runner is both the frontend
input (issue/label/dispatch) and the sandbox (the checked-out repo). Foundry runs
headless inside it. There is no always-on service, no MCP bridge, and no GitHub App
in v1. GitHub is the product surface (issues to request, PRs/checks/comments to
review); Foundry is the engine.

This follows the open-agents lesson ("the agent is not the sandbox") with the
pragmatic simplification that for fire-and-forget "implement this task, open a PR"
work the GitHub runner IS the sandbox, so we do not need a separate hibernating VM.

**Target repo:** `snedea/context-foundry` (private; separate from
`origin = context-foundry/context-foundry`).

## Current state (verified against source, 2026-05-22)

- `Commands::Run` exposes `--no-tui` and `--output-format json|json-stream`
  (src/main.rs:61-68), dispatching to `app::run_headless` (src/app/commands.rs:467).
- Headless run loads `Config` via the global->project merge (src/config.rs:980) and
  respects per-stage routing (`active_routing_for_stage`).
- Terminal `SessionReport` carries per-task status, commit SHAs, feat/WIP counts,
  cost, and `typed_error` (src/app/commands.rs:797). A JSONL `StreamEmitter` drives
  `json-stream`.
- `run_mode = "service"` is behavior-only (src/app/service_mode.rs): empty-queue
  termination, no Discovery, no bootstrap Scout, WIP-terminal, no update check. It
  does NOT touch model/provider/stage routing.
- `render_service_profile()` (src/service/localdocker.rs:44) is a SEPARATE thing --
  it writes a whole `.foundry.json` that pins providers to Claude and clears
  `stage_overrides`. The CI profile must NOT be derived from it.
- `agent.rs` spawns the `claude` CLI in a PTY and relies on ambient auth; it has no
  `ANTHROPIC_API_KEY` handling of its own and only knows `ANTHROPIC_BASE_URL`
  (src/config.rs:456). The "two worlds" split: interactive=Keychain, serve=proxy.
- `ReviewPr` already had `--ignore-project-config` for CI trust; `Commands::Run`
  now has the same flag for future untrusted-run variants.
- The greenfield `foundry serve` build service (Phase 35, v4.0.0) seeds work dirs
  with SPEC.md/TASKS.md only (src/service/localdocker.rs:649) and builds preview
  containers. Repo-aware mode is ADDITIVE and must not break it.

## Implementation steps (-> TASKS.md Phase 36)

- [ ] T36.1 -- headless provider auth in a Keychain-less runner (env passthrough +
      manual smoke). The gate; prove it before the rest.
- [x] T36.2 -- `--profile <name>` Config overlay + a built-in `ci` profile
      (`run_mode=service` + provider allowlist + budget caps; preserves routing).
- [x] T36.3 -- exit-code policy for headless runs (0 only when all feat/pass).
- [x] T36.4 -- `run --ignore-project-config` trust flag (mirror ReviewPr).
- [x] T36.5 -- label/dispatch-gated `.github/workflows/foundry-agent.yml` that
      checks out, branches first, runs headless, pushes, opens a PR, uploads
      `.buildloop`.
- [x] T36.6 -- PR/check reporting from the `SessionReport`.
- [ ] T36.7 -- (deferred, optional) MCP launcher for VS Code / Copilot.
- [ ] T36.8 -- (deferred) GitHub App packaging.

## Architecture decisions

- **No new command.** Extend `Commands::Run`, do not add `run-repo`.
- **No second config universe.** A named profile is a thin overlay onto the existing
  `Config` (global -> project -> profile). `.github/foundry.yml`, if used later, maps
  into `Config`, it does not replace it.
- **`run_mode` and model routing are independent.** The `ci` profile sets bounded
  behavior and a provider allowlist; it inherits stage routing from the repo.
- **Runner is the sandbox.** No clone logic, no tarball artifact, no remote service
  in v1; GitHub provides the checkout, token, and PR.
- **Trust boundary.** The v1 Action never checks out a PR head. It checks out the
  trusted default branch, honors that branch's `.foundry.json` so per-stage routing
  works in CI, and gates issue-triggered runs by both maintainer label and trusted
  issue author. Future variants that run untrusted PR code must use
  `--ignore-project-config`.
- **Defer the heavy surfaces.** MCP launcher and GitHub App come only after the
  Action path is proven.

## Risks and open questions

- **Auth is the real gate (T36.1).** No Keychain in a runner. The `claude` CLI must
  authenticate from `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` in the runner
  env. Unproven until the manual smoke runs.
- **CI provider set is small.** LM Studio (desktop GUI) and Ollama (model pulls +
  disk + minutes) are non-starters in a stock runner. CI realistically = Claude
  and/or Codex via API-key secrets. The `ci` profile declares the allowed set and
  fails fast otherwise.
- **Cost/runtime.** A QRPBA run is 25-60 min and $8-20 unattended. The `ci` profile
  sets budget/runtime caps; the workflow sets `timeout-minutes`.
- **Durability is deferred.** A dead runner mid-run loses progress. v1 just uploads
  `.buildloop` as an artifact for a human re-run; resumable branch state is a later
  epic (GitHub Actions cannot cheaply match open-agents' VM snapshotting).
- **Do not break the greenfield service.** Phase 35's `foundry serve` shares
  `app::run_headless`; the profile work fixes its over-constraint rather than forking
  a third execution path.

# Build service: the LocalDocker backend (M2)

The build service (`foundry serve`) drives builds through a pluggable
[`BuildBackend`](../src/service/backend.rs). M1 shipped `MockBuildBackend`
(replays a recorded event stream). M2 (T35.4) adds **`LocalDocker`** — real
builds in disposable `foundry-builder` containers — and the `foundry-builder`
image itself.

## Components

| Piece | Location |
|-------|----------|
| `LocalDocker` backend | `src/service/localdocker.rs` |
| `foundry-builder` image | `docker/foundry-builder/` |
| Build Container Contract | `docker/foundry-builder/entrypoint.sh` + `render_service_profile()` |

## Build Container Contract

Every build runs in a container with a clean, service-owned environment so no
ambient host config can influence it. The contract is split across two pieces:

- **`entrypoint.sh`** sets a clean `HOME`, removes any ambient `~/.claude.json`
  / `~/.foundry/`, pins a service git identity, requires the service
  `.foundry.json` + `SPEC.md` + `TASKS.md`, `git init`s the working tree, and
  `exec`s `foundry run --no-tui --output-format json-stream`.
- **`render_service_profile()`** (`localdocker.rs`) renders the exact
  unattended-safe `.foundry.json`. `LocalDocker` writes it into the
  bind-mounted working tree before launch:

  | Field | Value |
  |-------|-------|
  | `run_mode` | `"service"` |
  | `planner/builder/reviewer/fixer/discovery_provider` | `"claude"` (supports `"claude"`, `"codex"`, `"opencode"`, `"mistral"`) |
  | `planner/builder/discovery_model` | `"opus"` |
  | `reviewer/fixer_model` | `"sonnet"` |
  | `builder_models`, `stage_overrides`, `plugins` | `[]` |
  | `local_model` | `""` (no local-model routing) |
  | `auto_push_remote` | `null` |
  | `require_human_approval`, `planner_lookahead`, `backpressure_only` | `false` |
  | `batch_doubt`, `skip_doubt_for_simple`, `parallel_builder`, `sandbox` | `false` |
  | `doubt_confidence_threshold` | `0` |
  | `arena_mode` | `"solo"` |

  `sandbox` is `false` because the outer build container is itself the
  isolation boundary — nested `foundry` sandbox containers are not used in v1.

## What LocalDocker does

For each job, `LocalDocker`:

1. Lays out the per-job storage directory's `work/` subtree, writes the
   service `.foundry.json` + `SPEC.md` + `TASKS.md` into it.
2. Runs `docker run` against `foundry-builder`, bind-mounting `work/` at
   `/work`, injecting `ANTHROPIC_BASE_URL` (the auth proxy) and the per-build
   scoped token as `ANTHROPIC_API_KEY`, with CPU/memory/pids caps.
3. Captures container stdout into `jobs/<id>/logs/stream.jsonl` and stderr into
   `jobs/<id>/logs/stderr.log`.
4. Packs the **source artifact** (`collect_artifact`) — the working tree plus
   `.git` history, excluding `.buildloop/`, `node_modules/`, `target/`,
   `dist/`.
5. Packs the **diagnostics bundle** (`collect_diagnostics`) — `.buildloop/*.md`
   plus the `.buildloop/history/**` per-task snapshots, the evidence behind any
   WIP/audit-failed task in a multi-task `ready` job.

`build_image` / `deploy_preview` land in M3 (T35.5).

## Configuration

`run_serve()` selects the backend from `ServiceConfig`:

| Env var | Default | Purpose |
|---------|---------|---------|
| `FOUNDRY_SERVICE_BUILD_BACKEND` | `mock` | `mock` or `local_docker` |
| `FOUNDRY_SERVICE_BUILDER_IMAGE` | `foundry-builder:latest` | image tag |
| `FOUNDRY_SERVICE_BUILDER_PROXY_URL` | `http://host.docker.internal:8788` | `ANTHROPIC_BASE_URL` for the container |
| `FOUNDRY_SERVICE_DOCKER_BIN` | `docker` | docker CLI binary |

If the auth proxy is bound to a non-default port, set
`FOUNDRY_SERVICE_BUILDER_PROXY_URL` to match.

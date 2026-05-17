# foundry-builder image

The disposable build container for the Context Foundry build service
(`foundry serve`). One image carries `foundry`, Node, the `claude` CLI, git, and
common toolchains. Its entrypoint establishes the **Build Container Contract**
and runs the headless build.

## Build

```bash
docker/foundry-builder/build.sh            # tags foundry-builder:latest
docker/foundry-builder/build.sh myrepo/foundry-builder:v1
```

`build.sh` stages `target/release/foundry` into the build context (building it
first if missing), runs `docker build`, and removes the staged binary
afterwards.

## Build Container Contract

`entrypoint.sh` establishes, before any build runs:

- **Clean `HOME`** (`/home/builder`) — no ambient `~/.claude.json` or
  `~/.foundry/` may shadow the injected credentials or alter routing.
- **`claude` and `foundry` on `PATH`**.
- **Pinned service git identity** — `git commit` fails silently without one,
  and `foundry` records task results from commits.
- **Service-owned `.foundry.json`** — the `LocalDocker` backend renders the
  exact unattended-safe profile (`run_mode: "service"`, all routing Claude-only,
  no plugins, no auto-push, no human gate, no local-model routing, sandbox off)
  and writes it into the bind-mounted working tree. `entrypoint.sh` requires it.
- **Auth via the proxy** — the container receives `ANTHROPIC_BASE_URL` (the
  daemon's auth proxy) and a per-build scoped token as `ANTHROPIC_API_KEY`,
  never the real key.

The entrypoint then `git init`s the working tree, requires `SPEC.md` +
`TASKS.md`, and `exec`s `foundry run --no-tui --output-format json-stream`.
stdout is the JSONL event stream; stderr is human/progress noise.

## How `LocalDocker` drives it

`src/service/localdocker.rs` mounts the per-job storage directory's `work/`
subtree at `/work`, injects the env above, runs the container, captures
container stdout into `jobs/<id>/logs/stream.jsonl` and stderr into
`stderr.log`, then — off the bind mount — packs `source.tar.gz` (working tree
plus `.git`, excluding `.buildloop/`, `node_modules/`, `target/`, `dist/`) and
the diagnostics bundle (`.buildloop/*.md` plus `.buildloop/history/**`).

See [`docs/build-service-localdocker.md`](../../docs/build-service-localdocker.md).

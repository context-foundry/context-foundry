# Plan: Build-service auth-proxy 401 fix

Date: 2026-05-17
Version: v1
Status: in-progress

## Context

VPS deploy of `foundry serve` (local_docker backend, OAuth subscription mode).
The smoke build fails: every Claude call in the builder container returns
`401 proxy request denied`, so every task silently completes as WIP with
`$0.00` cost.

## Current State

- `foundry serve` is deployed and healthy (oauth mode, guard PASS).
- The storage-wiring defect is already fixed (host-shared bind mount, service
  runs as uid 10001:994).
- Root cause of the 401: header mismatch at the builder->proxy boundary.
  - `src/service/proxy.rs` `messages_handler` reads the inbound per-build
    token from the `Authorization: Bearer` header only.
  - `src/service/localdocker.rs` `docker_run_argv` injects the per-build token
    into the builder as `ANTHROPIC_API_KEY`; the `claude` CLI sends
    `ANTHROPIC_API_KEY` in the `x-api-key` header, never `Authorization`.
  - Proxy sees an empty token -> `ProxyDenial::Unauthorized` -> 401.

## Implementation Steps

- [ ] localdocker.rs `docker_run_argv`: inject the per-build token as
      `ANTHROPIC_AUTH_TOKEN` instead of `ANTHROPIC_API_KEY` (the `claude` CLI
      sends `ANTHROPIC_AUTH_TOKEN` as `Authorization: Bearer`). Keep
      `ANTHROPIC_BASE_URL`. Update the doc comment.
- [ ] localdocker.rs unit test `docker_run_argv_injects_proxy_mount_and_caps`:
      assert `ANTHROPIC_AUTH_TOKEN=fb_tok`.
- [ ] docker/foundry-builder/entrypoint.sh: require `ANTHROPIC_AUTH_TOKEN`
      instead of `ANTHROPIC_API_KEY` (keep the `ANTHROPIC_BASE_URL` check).
- [ ] Rebuild `foundry-builder:latest` (entrypoint changed).
- [ ] Recompile + redeploy `foundry-service` (`docker compose up -d --build`).
- [ ] Guard PASS before/after; re-run the smoke build.
- [ ] Confirm the job reaches `ready` with non-zero `cost_usd`.

## Architecture Decisions

- Keep the per-build-token + auth-proxy architecture (no token copy, no
  `~/.claude` bind-mount) -- per explicit instruction.
- Use `ANTHROPIC_AUTH_TOKEN`, not `CLAUDE_CODE_OAUTH_TOKEN`: the per-build
  token is an opaque random string, not an Anthropic OAuth-format token;
  `ANTHROPIC_AUTH_TOKEN` is the format-agnostic bearer var.

## Follow-on defects (found while verifying the fix)

Fixing the 401 (confirmed: auth validates, build logged `[cost] $0.02`)
surfaced further proxy defects that block a clean `ready`:

- **Output-token damper too low.** `FOUNDRY_SERVICE_PROXY_MAX_OUTPUT_TOKENS`
  default 8192 < the `max_tokens` the `claude` CLI requests for Opus/Sonnet ->
  `ProxyDenial::OutputTokensTooHigh` 400. Fixed via `.env` (64000).
- **Concurrency damper too low.** `FOUNDRY_SERVICE_PROXY_MAX_CONCURRENT`
  default 8 < a Claude Code build's in-flight burst -> `too_many_concurrent`.
  Fixed via `.env` (64).
- **`anthropic-beta` header dropped.** `proxy.rs` `messages_handler` rebuilt
  the upstream request from scratch and forwarded only its own
  `oauth-2025-04-20` beta header, discarding the client's `anthropic-beta`.
  Claude Code's `context_management` body field then failed upstream with
  `400 "Extra inputs are not permitted"`. Fixed in code: `merge_anthropic_beta`
  combines the inbound + upstream beta tokens (de-duplicated) into one header.
- **Preview image ref not lowercased.** `preview_image_ref` built a Docker
  image tag from the job ID, but job IDs are `fj_` + an (uppercase) ULID, and
  Docker image repository names must be lowercase -> `docker build -t`
  rejected the tag instantly, failing the job with `preview_deploy_failed`
  *after* a fully successful build (audit pass, cost ~$1.63, 2/2 tasks).
  Fixed in code: `preview_image_ref` lowercases the sanitized component.
  (Container names are exempt from the lowercase rule and are unchanged.)
- **#7 — preview unreachable: `--internal` network vs published port.**
  `preview_run_argv` published a host port (`-p 127.0.0.1::8080`) and
  `read_preview_port` read it back via `docker port`, but the preview network
  is `--internal` and Docker does not publish host ports on internal
  networks. Even if it did, the containerised `foundry-service` has its own
  loopback. Fixed: dropped `-p` / `read_preview_port` / `port_argv`; the
  service reaches the preview by container name on the shared `foundry-preview`
  network (`foundry-service` now joins that network via compose). Also
  `caddy.rs preview_hostname` now uses `app_name` -> `<app_name>.knowmler.com`
  (D5 in `SPEC_knowmler-build-integration.md`).
- **#8 — success path tore down the live preview.** On a job reaching
  `ready`, `worker.rs` called `cleanup` -> `LocalDocker::teardown`, which
  `docker rm -f`s the build container *and the preview container* and removes
  the Caddy route. Correct for failure paths; wrong on success — it destroyed
  the preview the instant the job went `ready`. (Latent until #7 was fixed:
  earlier builds failed before `ready`, so `cleanup` only ran on failure
  paths.) Fixed: the success path releases only the proxy token + storage
  grant; `teardown` is not called (the build container is `--rm`, already
  gone; the preview + route must survive).

## Risks & Open Questions

- `ANTHROPIC_AUTH_TOKEN` -> `Authorization: Bearer` confirmed working (denials
  moved past the auth check; non-zero cost observed).
- Host subscription must stay untouched (guard PASS before/after).
- `azure_aca.rs` has the identical `ANTHROPIC_API_KEY` defect for the Azure
  backend -- pinned with a `TODO(auth-401)` at the call site, not fixed
  (out of scope; behind the `azure` feature flag).

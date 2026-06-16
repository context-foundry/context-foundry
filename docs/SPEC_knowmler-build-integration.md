# SPEC: Knowmler → Context Foundry Build Integration

Date: 2026-05-17
Status: draft — round-1 decisions locked; backlog + open items noted
Owner: snedea

## Why this exists — the weight

A *promoted* idea in Knowmler is not a guess. It is an idea a user articulated,
an AI-built `index.html` mockup the user **liked**, a prototype the community
**voted up**, and a ranking that **promoted** it to the top. By the time an
admin builds it, market risk is already retired: demand is validated and the
visual target is proven.

Consequence for design: the build that follows is not a speculative experiment.
It earns a real engineering pipeline, a real repo, and real hosting. The
`index.html` mockup is unusually high-signal context — most builds start from a
prose guess; this one starts from a prototype the audience already endorsed.

## End-to-end flow

```
Knowmler "lab"
  user submits idea (by hand or AI-chat, four questions)
    → AI builds index.html mockup → hosted (S3 today)
  community votes → idea reaches "promoted"

Admin opens a promoted idea → "Build with Context Foundry"
  → dialog: confirms a full-stack build (~20–60 min); picks complexity S/M/L
  → Knowmler assembles SPEC.md (idea answers + mockup) and TASKS.md
  → user reviews / edits SPEC.md + TASKS.md            ← pre-build gate
  → Knowmler calls POST /v1/jobs { spec_md, tasks_md, ... }
  → Context Foundry build service builds the full-stack app
  → outputs: a running preview URL  +  a GitHub repo (source + SPEC.md)
  → user polls progress, then receives the live app + the repo
```

The build *engine* already exists and is proven: `foundry serve` runs on the
Claude subscription (OAuth), and the `/v1` contract is shipped and tested. The
"Build with Context Foundry" button is, mechanically, `POST /v1/jobs`.

## Locked decisions (round 1)

### D1 — Knowmler owns SPEC + TASKS; both user-editable before the build

- Knowmler assembles **both** `SPEC.md` and `TASKS.md`.
- Both are shown to the end user and are **editable before the build starts**.
- Rationale: task decomposition encodes Knowmler's identity and guardrails;
  keeping it in Knowmler means tweaking a guardrail never requires recompiling
  the Foundry binary. `/v1/jobs` already requires `tasks_md`, so this needs
  **no Foundry API change** — and it removes the need for any "spec-only mode".
- Refinement: Knowmler's decomposition must follow Foundry's task-composition
  rules ([`task-composition.md`](task-composition.md)) — one mental model per
  task — or the pipeline thrashes. Knowmler owns the initial *shape*; Foundry's
  PLAN stage refines *within* each task.

### D2 — SPEC.md content

`SPEC.md` must carry both signal sources:

- the user's original answers to the four idea questions (hand-entered or
  AI-assisted), and
- the promoted `index.html` mockup — **embedded inline, or referenced by its
  hosted URL** (the mockup is the visual contract; HTML is context).

### D3 — GitHub is the deliverable home

- The built full-stack app's source is exported to a **GitHub repo**.
- The original mockup preview URL is (a) recorded in the repo and (b) fed into
  `SPEC.md`'s context. `SPEC.md` is committed into the repo, so the repo is
  self-documenting: idea → mockup → tasks → built code.
- v1 uses a **Context-Foundry-owned GitHub org/account** (one service-level
  auth); commits are authored as "Context Foundry". Per-user GitHub routing is
  deferred — see B1.

### D4 — Preview hosting

- The idea-stage mockup stays a static `index.html` (S3 today) — unchanged.
- A Context Foundry build is a **full-stack app**: its preview is a running
  container behind a reverse proxy, not a static page. This depends on the
  `foundry serve` preview subsystem — see Open Items O1.

### D5 — Preview URL scheme

- Preview URLs live under **`*.knowmler.com`**.
- The subdomain is a **playful, app-derived slug** — e.g.
  `wishful-stickers.knowmler.com` for a sticker app,
  `intelligent-feedback.knowmler.com` for a feedback app. Always inclusive,
  never offensive, in the spirit of Knowmler usernames.
- **Knowmler generates the slug** from the app (consistent with D1 — Knowmler
  owns identity/naming) and passes it as the `/v1` `app_name` field, which is
  already an `[a-z0-9-]` slug. Foundry's preview hostname becomes
  `<app_name>.knowmler.com` (today it is `build-<job_id>.<domain>` — `caddy.rs`
  `preview_hostname` must change to use `app_name`).
- `knowmler.com` is already a homelab-Caddy domain with Cloudflare DNS+TLS, so
  a `*.knowmler.com` wildcard cert is obtainable via the existing Cloudflare
  DNS challenge.
- The `preview_url` returned by `/v1` is `https://` — previews are served
  through a TLS-terminating Caddy; an `http://` URL would mixed-content-fail
  when consumed from Knowmler's HTTPS pages. (Fixed in `caddy.rs::preview_url`.)

### D6 — Preview hostname uniqueness is Knowmler's responsibility

`app_name` becomes the preview hostname (`<app_name>.knowmler.com`). The `/v1`
API validates `app_name` for slug *shape* only; there is no uniqueness
constraint. Two live previews with the same `app_name` collide on the same
host. **Knowmler must guarantee `app_name` is unique among currently-live
(`ready`) previews** — regenerate/suffix the playful slug on collision. Open:
whether the build service should *also* hard-reject a submit whose `app_name`
matches a live preview (a defence-in-depth guard) — see O5.

## Responsibility split (two repos)

| Knowmler | Context Foundry |
|----------|-----------------|
| "Build with Context Foundry" admin button | `/v1` build service (done) |
| Build dialog: complexity S/M/L + time estimate | builds the app |
| `SPEC.md` + `TASKS.md` assembly from idea + mockup | GitHub export of source |
| SPEC/TASKS editor UI (pre-build gate) | preview hosting |
| Progress UI (polls `GET /v1/jobs/{id}`) | — |

## Backlog / deferred

### B1 — Per-user GitHub integration (enhancement)

User account page shows a **GitHub** login state next to the existing Google
login (logged in / logged out), wired to GitHub OAuth so a user's builds land
in *their* repos. Significant subsystem (per-user OAuth, `gh` in the builder).
Deferred — high-level scaffolding only for now; build shortly after v1.

### B2 — Complexity → time/cost control

Build dialog complexity S/M/L maps to a build budget. Provisional targets from
round-0 discussion: S ≤ 2h, M ~ 2h, L ~ 4h. Needs a `/v1` request field
(`complexity` or explicit timeout) — the API has none today. Low priority.

## Open items still needing decisions

- **O1 — Preview hosting.** Three parts, all required before a build yields a
  working `*.knowmler.com` preview URL:
  1. *Code (Context Foundry):* the preview subsystem has an unresolved defect
     — preview containers on an `--internal` Docker network cannot publish a
     host port, so `read_preview_port` fails (see
     [`PLAN_build-service-401-fix.md`](PLAN_build-service-401-fix.md) follow-on
     notes). Fix: route to the preview by container name on a shared network
     instead of a published host port. Also: `caddy.rs preview_hostname` →
     `<app_name>.knowmler.com` (D5). **DONE — defects #7 (preview network) and
     #8 (success-path teardown) fixed; PR context-foundry#269. Verified
     reachable on the VPS-internal network only, not yet externally.**
  2. *DNS:* a wildcard `*.knowmler.com` (or `*.preview.knowmler.com`) record
     pointing at the VPS, on Cloudflare.
  3. *Reverse proxy:* a `*.knowmler.com` wildcard block in the **homelab
     Caddy** (production — fronts ~20 domains) that routes each
     `<app>.knowmler.com` to the matching preview container. The build service
     registers/removes these routes via Caddy's admin API.
- **O2 — Mockup transport.** Embed the `index.html` in `spec_md` vs reference
  it by hosted URL (D2 permits either). Decide based on `spec_md` size limits
  and whether the builder container has network access to fetch the URL.
- **O3 — Hosting platform.** S3 today; Azure possible on other deployments.
  Keep the built-app preview platform-agnostic (the container model is; static
  mockup hosting is the part that varies).
- **O4 — Embedding the preview in Knowmler (iframe vs link).** If the built
  app is shown inside an iframe (as the idea-stage S3 mockup is), the
  `knowmler.com` CSP `frame-src` must add `https://*.knowmler.com`
  (`caddy2/Caddyfile`) — a production change to bundle with the Caddy work. If
  the rollout is link-only, no CSP change is needed. **Decide before the
  production-Caddy change.**
- **O5 — Service-side slug-collision guard (optional).** D6 makes unique
  `app_name`s Knowmler's responsibility. Optionally the build service could
  *also* reject a `/v1` submit whose `app_name` matches a currently-`ready`
  preview — defence in depth. Decide whether to implement.

## Task decomposition (to refine after O1–O5)

High-level, to be split into file-referenced, single-concern tasks per repo:

- Context Foundry: fix the preview subsystem (O1); GitHub export of build
  source (D3); optional `complexity` field (B2).
- Knowmler: admin "Build" button + dialog; `SPEC.md`/`TASKS.md` assembly from
  idea + mockup (D1, D2); pre-build SPEC/TASKS editor; build-progress UI.

Pure-prose vision does not pipeline (see `task-composition.md`). This SPEC is
the planning artifact; the file-referenced tasks derived from it are what can
later run through Context Foundry.

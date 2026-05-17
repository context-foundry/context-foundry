# Plan: Per-org preview base domain
Date: 2026-05-17
Version: v1
Status: completed -- `cargo check` clean, 68 service unit tests pass

## Context
Context Foundry previews are served at `<app_name>.<base_domain>`, where
`base_domain` is one global config value (`FOUNDRY_SERVICE_PREVIEW_DOMAIN`).
Knowmler wants previews namespaced per organization:
`<app_name>.<org_slug>.knowmler.com`. The build service must therefore accept
an org slug per job and compose the preview hostname from it. See the knowmler
repo's `docs/PLAN_foundry-preview-subdomains.md`.

## Design
Knowmler passes an optional `org_slug` on `POST /v1/jobs`. The service keeps
`preview_base_domain` as the ROOT domain (server config, not caller input) and
composes the effective hostname:
- `org_slug` present -> `<app_name>.<org_slug>.<root>`
- `org_slug` absent  -> `<app_name>.<root>` (unchanged; backward compatible)

The caller controls only the `org_slug` segment, validated as a DNS label
(same rule as `app_name`). It cannot redirect previews to an arbitrary domain.

## Current State (verified 2026-05-17)
- `caddy.rs`: `preview_hostname(app_name, base_domain)` /
  `preview_url(app_name, base_domain)`.
- `localdocker.rs::deploy_preview` (lines 732, 779) calls both with
  `self.preview.base_domain`.
- `SubmitRequest` and `Job` (`models.rs`) have no org field.
- `jobs` table (`migrations/0001_init.sql`) has no org column;
  `db.rs::row_to_job` maps every column via `SELECT *`.
- `db.rs::app_name_in_use` checks `app_name` GLOBALLY.
- `normalized_request_hash` hashes `(app_name, spec_md, tasks_md, ttl)`.
- No `tests/` integration test touches these symbols; the change is contained
  to `src/service/`.

## Implementation Steps
- [x] 1. `migrations/0002_add_org_slug.sql`: `ALTER TABLE jobs ADD COLUMN
      org_slug TEXT;` (nullable) + index `(app_name, org_slug)`.
- [x] 2. `models.rs`: add `org_slug: Option<String>` to `SubmitRequest` and
      `Job`; add `org_slug` to `normalized_request_hash`; validate `org_slug`
      in `validate_submit` (DNS label). Update unit tests.
- [x] 3. `caddy.rs`: `preview_hostname` / `preview_url` take
      `org_slug: Option<&str>` and a `root_domain`. Update doc + tests.
- [x] 4. `db.rs`: map `org_slug` in `row_to_job`; add it to `insert_job` and
      `insert_job_capped`; `app_name_in_use` gains `org_slug` and scopes with
      `org_slug IS NOT DISTINCT FROM $2`.
- [x] 5. `api.rs`: thread `org_slug` through `submit_job` (hash, conflict
      check, `Job` construction); add `org_slug` to `JobView`.
- [x] 6. `localdocker.rs::deploy_preview`: pass `job.org_slug.as_deref()`.
- [x] 7. `cargo check` + `cargo test` (service module).

## Architecture Decisions
- Caller passes `org_slug`, NOT a full base domain: the root domain stays
  server-controlled, so a caller cannot point a preview at an arbitrary host.
- `org_slug` reuses the `valid_app_name` DNS-label rule.
- Backward compatible: a request without `org_slug` behaves exactly as today.
- The `app_name` collision guard becomes per-org (two orgs may reuse a name);
  for org-less jobs (`NULL`) behavior is unchanged.

## Risks & Open Questions
- `org_slug` is added to the idempotency hash, so an idempotency_key reused
  with a different org correctly conflicts.
- `normalized_request_hash` conflates `None` and `Some("")`; safe in practice
  because `validate_submit` rejects an empty `org_slug` before the hash.
- This is a separate repo from knowmler; deploy/version coordination needed.
- Knowmler's build-submission code must start sending `org_slug` (separate,
  later task in the knowmler repo).

-- 0002_add_org_slug.sql
-- Per-org preview namespacing. When a job carries an org_slug, its preview
-- hostname becomes <app_name>.<org_slug>.<root_domain>; otherwise it stays
-- <app_name>.<root_domain> (unchanged). Nullable: existing jobs and org-less
-- `foundry serve` use have no organization.
ALTER TABLE jobs ADD COLUMN org_slug TEXT;

-- Supports the per-org app_name collision check (db::app_name_in_use).
CREATE INDEX jobs_app_org ON jobs (app_name, org_slug);

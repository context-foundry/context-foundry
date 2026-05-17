-- T35.3 M1 service skeleton: control-plane schema for `foundry serve`.
-- Non-reversible migration applied via sqlx::migrate!("./migrations").

CREATE TABLE jobs (
    id                 TEXT PRIMARY KEY,
    app_name           TEXT NOT NULL,
    owner              TEXT NOT NULL,
    status             TEXT NOT NULL,
    percent            INT NOT NULL DEFAULT 0,
    stage_label        TEXT,
    spec_md            TEXT NOT NULL,
    tasks_md           TEXT NOT NULL,
    spec_url           TEXT,
    tasks_url          TEXT,
    artifact_url       TEXT,
    preview_url        TEXT,
    preview_expires_at TIMESTAMPTZ,
    cost_usd           DOUBLE PRECISION NOT NULL DEFAULT 0,
    ttl_hours          INT NOT NULL,
    idempotency_key    TEXT NOT NULL,
    request_hash       TEXT NOT NULL,
    worker_id          TEXT,
    error_code         TEXT,
    error_message      TEXT,
    quality            JSONB NOT NULL DEFAULT '{"audit":"pending","findings":{"high":0,"medium":0,"low":0}}'::jsonb,
    detail             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at         TIMESTAMPTZ,
    finished_at        TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX jobs_owner_idem ON jobs (owner, idempotency_key);
CREATE INDEX jobs_status_created ON jobs (status, created_at);
CREATE INDEX jobs_owner_created ON jobs (owner, created_at);

CREATE TABLE job_events (
    id      BIGSERIAL PRIMARY KEY,
    job_id  TEXT NOT NULL REFERENCES jobs(id),
    ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind    TEXT NOT NULL,
    percent INT,
    stage   TEXT,
    payload JSONB
);

CREATE INDEX job_events_job ON job_events (job_id, ts);

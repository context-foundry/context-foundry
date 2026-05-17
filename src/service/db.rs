//! Postgres connection pool, migrations, and the job-store queries.
//!
//! Only runtime `sqlx::query` / `sqlx::query_scalar` are used (never the
//! compile-time `query!` macros), so a normal `cargo build` needs no live
//! database. `sqlx::migrate!` reads the migrations directory at compile time.

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use sqlx::postgres::{PgPoolOptions, PgRow};
use sqlx::{PgPool, Row};

use crate::service::config::ServiceConfig;
use crate::service::models::{Job, JobStatus};

/// Connect to Postgres with a pool sized for the worker count plus headroom
/// for API/reaper queries.
pub async fn connect(cfg: &ServiceConfig) -> Result<PgPool> {
    PgPoolOptions::new()
        .max_connections(cfg.worker_count as u32 + 8)
        .connect(&cfg.database_url)
        .await
        .context("connect postgres")
}

/// Apply all pending migrations. Idempotent — sqlx tracks applied versions.
pub async fn run_migrations(pool: &PgPool) -> Result<()> {
    sqlx::migrate!("./migrations")
        .run(pool)
        .await
        .context("run migrations")?;
    Ok(())
}

fn row_to_job(row: &PgRow) -> Job {
    let status = JobStatus::from_wire(&row.get::<String, _>("status")).unwrap_or(JobStatus::Failed);
    Job {
        id: row.get("id"),
        app_name: row.get("app_name"),
        owner: row.get("owner"),
        status,
        percent: row.get("percent"),
        stage_label: row.get("stage_label"),
        spec_md: row.get("spec_md"),
        tasks_md: row.get("tasks_md"),
        artifact_url: row.get("artifact_url"),
        preview_url: row.get("preview_url"),
        preview_expires_at: row.get("preview_expires_at"),
        cost_usd: row.get("cost_usd"),
        ttl_hours: row.get("ttl_hours"),
        idempotency_key: row.get("idempotency_key"),
        request_hash: row.get("request_hash"),
        worker_id: row.get("worker_id"),
        error_code: row.get("error_code"),
        error_message: row.get("error_message"),
        quality: row.get("quality"),
        detail: row.get("detail"),
        created_at: row.get("created_at"),
        started_at: row.get("started_at"),
        finished_at: row.get("finished_at"),
        updated_at: row.get("updated_at"),
    }
}

/// Look up an existing job by its `(owner, idempotency_key)` pair.
pub async fn find_by_idempotency(
    pool: &PgPool,
    owner: &str,
    key: &str,
) -> Result<Option<Job>> {
    let row = sqlx::query("SELECT * FROM jobs WHERE owner = $1 AND idempotency_key = $2")
        .bind(owner)
        .bind(key)
        .fetch_optional(pool)
        .await
        .context("find job by idempotency key")?;
    Ok(row.as_ref().map(row_to_job))
}

/// Count jobs currently in the `queued` state.
pub async fn count_queued(pool: &PgPool) -> Result<i64> {
    sqlx::query_scalar::<_, i64>("SELECT count(*) FROM jobs WHERE status = 'queued'")
        .fetch_one(pool)
        .await
        .context("count queued jobs")
}

/// Insert a freshly built job. Returns `Ok(true)` on insert, `Ok(false)` when
/// the unique `(owner, idempotency_key)` index rejected it (Postgres `23505`).
pub async fn insert_job(pool: &PgPool, job: &Job) -> Result<bool> {
    let result = sqlx::query(
        "INSERT INTO jobs \
         (id, app_name, owner, status, percent, spec_md, tasks_md, cost_usd, ttl_hours, idempotency_key, request_hash) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
    )
    .bind(job.id.as_str())
    .bind(job.app_name.as_str())
    .bind(job.owner.as_str())
    .bind(job.status.as_str())
    .bind(job.percent)
    .bind(job.spec_md.as_str())
    .bind(job.tasks_md.as_str())
    .bind(job.cost_usd)
    .bind(job.ttl_hours)
    .bind(job.idempotency_key.as_str())
    .bind(job.request_hash.as_str())
    .execute(pool)
    .await;

    match result {
        Ok(_) => Ok(true),
        Err(e) => {
            let is_unique_violation = e
                .as_database_error()
                .and_then(|d| d.code())
                .is_some_and(|c| c == "23505");
            if is_unique_violation {
                Ok(false)
            } else {
                Err(anyhow::Error::new(e).context("insert job"))
            }
        }
    }
}

/// Fetch a single job by id.
pub async fn get_job(pool: &PgPool, id: &str) -> Result<Option<Job>> {
    let row = sqlx::query("SELECT * FROM jobs WHERE id = $1")
        .bind(id)
        .fetch_optional(pool)
        .await
        .context("get job")?;
    Ok(row.as_ref().map(row_to_job))
}

/// List jobs, optionally filtered by owner and/or status, newest first.
///
/// One of four static query strings is selected by which filters are present;
/// filter values are bound as positional parameters and are NEVER interpolated
/// into the SQL.
pub async fn list_jobs(
    pool: &PgPool,
    owner: Option<&str>,
    status: Option<&str>,
    limit: i64,
) -> Result<Vec<Job>> {
    let rows = match (owner, status) {
        (None, None) => {
            sqlx::query("SELECT * FROM jobs ORDER BY created_at DESC LIMIT $1")
                .bind(limit)
                .fetch_all(pool)
                .await
        }
        (Some(o), None) => {
            sqlx::query("SELECT * FROM jobs WHERE owner = $1 ORDER BY created_at DESC LIMIT $2")
                .bind(o)
                .bind(limit)
                .fetch_all(pool)
                .await
        }
        (None, Some(s)) => {
            sqlx::query("SELECT * FROM jobs WHERE status = $1 ORDER BY created_at DESC LIMIT $2")
                .bind(s)
                .bind(limit)
                .fetch_all(pool)
                .await
        }
        (Some(o), Some(s)) => sqlx::query(
            "SELECT * FROM jobs WHERE owner = $1 AND status = $2 ORDER BY created_at DESC LIMIT $3",
        )
        .bind(o)
        .bind(s)
        .bind(limit)
        .fetch_all(pool)
        .await,
    };
    let rows = rows.context("list jobs")?;
    Ok(rows.iter().map(row_to_job).collect())
}

/// 1-based position of a queued job in the FIFO queue, or `None` if the job is
/// no longer queued.
pub async fn queue_position(pool: &PgPool, job: &Job) -> Result<Option<i64>> {
    if job.status != JobStatus::Queued {
        return Ok(None);
    }
    let n: i64 = sqlx::query_scalar::<_, i64>(
        "SELECT count(*) + 1 FROM jobs WHERE status = 'queued' AND created_at < $1",
    )
    .bind(job.created_at)
    .fetch_one(pool)
    .await
    .context("compute queue position")?;
    Ok(Some(n))
}

/// Atomically claim the oldest queued job for a worker using
/// `FOR UPDATE SKIP LOCKED`, so concurrent workers never claim the same job.
pub async fn claim_next(pool: &PgPool, worker_id: &str) -> Result<Option<Job>> {
    let row = sqlx::query(
        "UPDATE jobs \
         SET status = 'building', worker_id = $1, started_at = now(), updated_at = now() \
         WHERE id = ( \
             SELECT id FROM jobs WHERE status = 'queued' \
             ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED \
         ) \
         RETURNING *",
    )
    .bind(worker_id)
    .fetch_optional(pool)
    .await
    .context("claim next job")?;
    Ok(row.as_ref().map(row_to_job))
}

/// Update a job's running progress. `percent` only ever increases
/// (`GREATEST`); a job already `canceled` is left untouched so an in-flight
/// worker cannot resurrect it.
#[allow(clippy::too_many_arguments)]
pub async fn update_job_progress(
    pool: &PgPool,
    id: &str,
    status: JobStatus,
    percent: i32,
    stage_label: Option<&str>,
    cost_usd: f64,
    quality: &serde_json::Value,
    detail: &serde_json::Value,
) -> Result<()> {
    sqlx::query(
        "UPDATE jobs \
         SET status = $2, percent = GREATEST(percent, $3), stage_label = $4, \
             cost_usd = $5, quality = $6, detail = $7, updated_at = now() \
         WHERE id = $1 AND status <> 'canceled'",
    )
    .bind(id)
    .bind(status.as_str())
    .bind(percent)
    .bind(stage_label)
    .bind(cost_usd)
    .bind(quality.clone())
    .bind(detail.clone())
    .execute(pool)
    .await
    .context("update job progress")?;
    Ok(())
}

/// Finalize a job. `percent` is `GREATEST`-guarded, so callers that should not
/// change it pass `0`. A job already `canceled` is left untouched.
#[allow(clippy::too_many_arguments)]
pub async fn finish_job(
    pool: &PgPool,
    id: &str,
    status: JobStatus,
    percent: i32,
    error_code: Option<&str>,
    error_message: Option<&str>,
    artifact_url: Option<&str>,
    preview_url: Option<&str>,
    preview_expires_at: Option<DateTime<Utc>>,
) -> Result<()> {
    sqlx::query(
        "UPDATE jobs \
         SET status = $2, percent = GREATEST(percent, $3), error_code = $4, \
             error_message = $5, artifact_url = $6, preview_url = $7, \
             preview_expires_at = $8, finished_at = now(), updated_at = now() \
         WHERE id = $1 AND status <> 'canceled'",
    )
    .bind(id)
    .bind(status.as_str())
    .bind(percent)
    .bind(error_code)
    .bind(error_message)
    .bind(artifact_url)
    .bind(preview_url)
    .bind(preview_expires_at)
    .execute(pool)
    .await
    .context("finish job")?;
    Ok(())
}

/// Cancel a job, but only while it is still cancellable (`queued`, `building`,
/// or `deploying`). Returns the updated job, or `None` if it had already
/// reached a terminal state (so a cancel cannot overwrite a completed `ready`
/// job and orphan its preview).
pub async fn cancel_job(pool: &PgPool, id: &str) -> Result<Option<Job>> {
    let row = sqlx::query(
        "UPDATE jobs \
         SET status = 'canceled', error_code = 'canceled', \
             error_message = 'canceled by caller', finished_at = now(), updated_at = now() \
         WHERE id = $1 AND status IN ('queued', 'building', 'deploying') \
         RETURNING *",
    )
    .bind(id)
    .fetch_optional(pool)
    .await
    .context("cancel job")?;
    Ok(row.as_ref().map(row_to_job))
}

/// Append a job-lifecycle event.
pub async fn insert_event(
    pool: &PgPool,
    job_id: &str,
    kind: &str,
    percent: Option<i32>,
    stage: Option<&str>,
) -> Result<()> {
    sqlx::query("INSERT INTO job_events (job_id, kind, percent, stage) VALUES ($1, $2, $3, $4)")
        .bind(job_id)
        .bind(kind)
        .bind(percent)
        .bind(stage)
        .execute(pool)
        .await
        .context("insert job event")?;
    Ok(())
}

/// On daemon startup, fail any job left mid-build by a previous process.
/// `queued` rows are untouched — M1 has no live containers to kill (M4/T35.6
/// adds container reconciliation).
pub async fn reconcile_startup(pool: &PgPool) -> Result<()> {
    sqlx::query(
        "UPDATE jobs \
         SET status = 'failed', error_code = 'internal_error', \
             error_message = 'daemon restarted mid-build', \
             finished_at = now(), updated_at = now() \
         WHERE status IN ('building', 'deploying')",
    )
    .execute(pool)
    .await
    .context("reconcile jobs on startup")?;
    Ok(())
}

/// Mark every `ready` job whose preview TTL has elapsed as `expired`.
/// Returns the ids that were expired.
pub async fn expire_due_previews(pool: &PgPool) -> Result<Vec<String>> {
    let rows = sqlx::query(
        "UPDATE jobs SET status = 'expired', updated_at = now() \
         WHERE status = 'ready' AND preview_expires_at IS NOT NULL AND preview_expires_at < now() \
         RETURNING id",
    )
    .fetch_all(pool)
    .await
    .context("expire due previews")?;
    Ok(rows.iter().map(|r| r.get::<String, _>("id")).collect())
}

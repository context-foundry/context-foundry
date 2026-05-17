//! The `/v1` HTTP API: bearer auth, job submit/poll/list/logs/artifact/
//! diagnostics/cancel/delete-preview, and an unauthenticated health check.

use std::sync::Arc;

use axum::{
    body::{Body, Bytes},
    extract::{Path, Query, Request, State},
    http::{header, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{delete, get, post},
    Json, Router,
};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::json;
use subtle::ConstantTimeEq;
use ulid::Ulid;

use crate::service::backend::{ArtifactKind, ArtifactResponse};
use crate::service::models::{self, ErrorCode, Job, JobStatus, SubmitRequest};
use crate::service::{db, AppState};

// ─── Response shapes ────────────────────────────────────────────────────────

#[derive(Serialize)]
struct ApiError {
    schema_version: u32,
    error: String,
    message: String,
}

#[derive(Deserialize)]
struct ListQuery {
    owner: Option<String>,
    status: Option<String>,
}

#[derive(Deserialize)]
struct LogsQuery {
    stage: Option<String>,
    tail: Option<usize>,
}

#[derive(Serialize)]
struct JobView {
    schema_version: u32,
    job_id: String,
    app_name: String,
    owner: String,
    status: String,
    percent: i32,
    stage_label: Option<String>,
    preview_url: Option<String>,
    preview_expires_at: Option<String>,
    queue_position: Option<i64>,
    cost_usd: f64,
    created_at: String,
    started_at: Option<String>,
    finished_at: Option<String>,
    error: Option<serde_json::Value>,
    quality: serde_json::Value,
    detail: serde_json::Value,
}

// ─── Response helpers ───────────────────────────────────────────────────────

fn api_error(status: StatusCode, code: &str, message: &str) -> Response {
    let body = ApiError {
        schema_version: 1,
        error: code.to_string(),
        message: message.to_string(),
    };
    (status, Json(body)).into_response()
}

/// A typed error response whose HTTP status is derived from the [`ErrorCode`].
fn err(code: ErrorCode, message: &str) -> Response {
    let status =
        StatusCode::from_u16(code.http_status()).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
    api_error(status, code.as_str(), message)
}

fn not_found(message: &str) -> Response {
    api_error(StatusCode::NOT_FOUND, "not_found", message)
}

fn unauthorized() -> Response {
    api_error(
        StatusCode::UNAUTHORIZED,
        "unauthorized",
        "missing or invalid bearer token",
    )
}

/// The `202 Accepted` body returned for both a fresh submit and an idempotent
/// replay, so a retrying client always parses the same shape.
fn job_accepted(job: &Job, queue_position: Option<i64>) -> Response {
    (
        StatusCode::ACCEPTED,
        Json(json!({
            "schema_version": 1,
            "job_id": job.id,
            "status": job.status.as_str(),
            "queue_position": queue_position,
            "created_at": job.created_at.to_rfc3339(),
            "poll_url": format!("/v1/jobs/{}", job.id),
        })),
    )
        .into_response()
}

async fn job_view(state: &Arc<AppState>, job: &Job) -> JobView {
    let queue_position = db::queue_position(&state.pool, job).await.ok().flatten();
    let error = job.error_code.as_ref().map(|code| {
        json!({ "code": code, "message": job.error_message })
    });
    JobView {
        schema_version: 1,
        job_id: job.id.clone(),
        app_name: job.app_name.clone(),
        owner: job.owner.clone(),
        status: job.status.as_str().to_string(),
        percent: job.percent,
        stage_label: job.stage_label.clone(),
        preview_url: job.preview_url.clone(),
        preview_expires_at: job.preview_expires_at.map(|t| t.to_rfc3339()),
        queue_position,
        cost_usd: job.cost_usd,
        created_at: job.created_at.to_rfc3339(),
        started_at: job.started_at.map(|t| t.to_rfc3339()),
        finished_at: job.finished_at.map(|t| t.to_rfc3339()),
        error,
        quality: job.quality.clone(),
        detail: job.detail.clone(),
    }
}

// ─── Bearer auth middleware ─────────────────────────────────────────────────

async fn auth_mw(State(state): State<Arc<AppState>>, req: Request, next: Next) -> Response {
    let presented = req
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .unwrap_or("")
        .as_bytes()
        .to_vec();
    let accepted = !state.config.api_keys.is_empty()
        && state.config.api_keys.iter().any(|k| {
            k.len() == presented.len()
                && k.as_bytes().ct_eq(presented.as_slice()).unwrap_u8() == 1
        });
    if accepted {
        next.run(req).await
    } else {
        unauthorized()
    }
}

// ─── Handlers ───────────────────────────────────────────────────────────────

/// `POST /v1/jobs` — submit a build. The body is parsed manually so a
/// malformed or incomplete request returns the typed `validation_error`
/// instead of axum's default JSON rejection.
async fn submit_job(State(state): State<Arc<AppState>>, body: Bytes) -> Response {
    let req: SubmitRequest = match serde_json::from_slice(&body) {
        Ok(r) => r,
        Err(_) => {
            return err(
                ErrorCode::ValidationError,
                "malformed or incomplete request body",
            )
        }
    };
    if let Err(message) = models::validate_submit(&state.config, &req) {
        return err(ErrorCode::ValidationError, &message);
    }

    let ttl = models::clamp_ttl(&state.config, req.preview_ttl_hours);
    let hash =
        models::normalized_request_hash(&req.app_name, &req.spec_md, &req.tasks_md, ttl);

    match db::find_by_idempotency(&state.pool, &req.owner, &req.idempotency_key).await {
        Ok(Some(existing)) => {
            return if existing.request_hash == hash {
                let qp = db::queue_position(&state.pool, &existing).await.ok().flatten();
                job_accepted(&existing, qp)
            } else {
                err(
                    ErrorCode::IdempotencyConflict,
                    "idempotency_key reused with a different request",
                )
            };
        }
        Ok(None) => {}
        Err(_) => return err(ErrorCode::InternalError, "idempotency lookup failed"),
    }

    match db::count_queued(&state.pool).await {
        Ok(n) if n as usize >= state.config.queue_cap => {
            return err(ErrorCode::QueueFull, "the build queue is full")
        }
        Ok(_) => {}
        Err(_) => return err(ErrorCode::InternalError, "queue depth check failed"),
    }

    let now = Utc::now();
    let job = Job {
        id: format!("fj_{}", Ulid::new()),
        app_name: req.app_name.clone(),
        owner: req.owner.clone(),
        status: JobStatus::Queued,
        percent: 0,
        stage_label: None,
        spec_md: req.spec_md.clone(),
        tasks_md: req.tasks_md.clone(),
        artifact_url: None,
        preview_url: None,
        preview_expires_at: None,
        cost_usd: 0.0,
        ttl_hours: ttl,
        idempotency_key: req.idempotency_key.clone(),
        request_hash: hash.clone(),
        worker_id: None,
        error_code: None,
        error_message: None,
        quality: json!({ "audit": "pending", "findings": { "high": 0, "medium": 0, "low": 0 } }),
        detail: json!({}),
        created_at: now,
        started_at: None,
        finished_at: None,
        updated_at: now,
    };

    match db::insert_job(&state.pool, &job).await {
        Ok(true) => {}
        Ok(false) => {
            // Lost an idempotency race with a concurrent submit.
            return match db::find_by_idempotency(&state.pool, &req.owner, &req.idempotency_key)
                .await
            {
                Ok(Some(other)) if other.request_hash == hash => {
                    let qp = db::queue_position(&state.pool, &other).await.ok().flatten();
                    job_accepted(&other, qp)
                }
                Ok(Some(_)) => err(
                    ErrorCode::IdempotencyConflict,
                    "idempotency_key reused with a different request",
                ),
                _ => err(ErrorCode::InternalError, "job insert race could not be resolved"),
            };
        }
        Err(_) => return err(ErrorCode::InternalError, "job insert failed"),
    }

    let _ = db::insert_event(&state.pool, &job.id, "submitted", Some(0), None).await;
    let qp = db::queue_position(&state.pool, &job).await.ok().flatten();
    job_accepted(&job, qp)
}

/// `GET /v1/jobs/{id}` — poll a job.
async fn get_job(State(state): State<Arc<AppState>>, Path(id): Path<String>) -> Response {
    match db::get_job(&state.pool, &id).await {
        Ok(Some(job)) => (StatusCode::OK, Json(job_view(&state, &job).await)).into_response(),
        Ok(None) => not_found("job not found"),
        Err(_) => err(ErrorCode::InternalError, "failed to load job"),
    }
}

/// `GET /v1/jobs` — list jobs, optionally filtered by `owner` / `status`.
async fn list_jobs(
    State(state): State<Arc<AppState>>,
    Query(q): Query<ListQuery>,
) -> Response {
    match db::list_jobs(&state.pool, q.owner.as_deref(), q.status.as_deref(), 100).await {
        Ok(jobs) => {
            let mut views = Vec::with_capacity(jobs.len());
            for job in &jobs {
                views.push(job_view(&state, job).await);
            }
            (
                StatusCode::OK,
                Json(json!({
                    "schema_version": 1,
                    "jobs": views,
                    "next_cursor": serde_json::Value::Null,
                })),
            )
                .into_response()
        }
        Err(_) => err(ErrorCode::InternalError, "failed to list jobs"),
    }
}

/// `GET /v1/jobs/{id}/logs` — stream the recorded build event log as text.
async fn get_logs(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
    Query(q): Query<LogsQuery>,
) -> Response {
    match db::get_job(&state.pool, &id).await {
        Ok(Some(_)) => {}
        Ok(None) => return not_found("job not found"),
        Err(_) => return err(ErrorCode::InternalError, "failed to load job"),
    }
    match state
        .storage
        .read_logs(&id, q.stage.as_deref(), q.tail)
        .await
    {
        Ok(text) => (
            StatusCode::OK,
            [(header::CONTENT_TYPE, "text/plain; charset=utf-8")],
            text,
        )
            .into_response(),
        Err(_) => err(ErrorCode::InternalError, "failed to read job logs"),
    }
}

async fn artifact_response(state: &Arc<AppState>, id: &str, kind: ArtifactKind) -> Response {
    match db::get_job(&state.pool, id).await {
        Ok(Some(_)) => {}
        Ok(None) => return not_found("job not found"),
        Err(_) => return err(ErrorCode::InternalError, "failed to load job"),
    }
    match state.storage.fetch(id, kind).await {
        Ok(ArtifactResponse::Stream {
            filename,
            content_type,
            bytes,
        }) => (
            StatusCode::OK,
            [
                (header::CONTENT_TYPE, content_type),
                (
                    header::CONTENT_DISPOSITION,
                    format!("attachment; filename=\"{filename}\""),
                ),
            ],
            Body::from(bytes),
        )
            .into_response(),
        Ok(ArtifactResponse::Redirect { url }) => {
            (StatusCode::FOUND, [(header::LOCATION, url)], ()).into_response()
        }
        Err(_) => not_found("artifact not found"),
    }
}

/// `GET /v1/jobs/{id}/artifact` — fetch the source artifact.
async fn get_artifact(State(state): State<Arc<AppState>>, Path(id): Path<String>) -> Response {
    artifact_response(&state, &id, ArtifactKind::Artifact).await
}

/// `GET /v1/jobs/{id}/diagnostics` — fetch the diagnostics bundle.
async fn get_diagnostics(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Response {
    artifact_response(&state, &id, ArtifactKind::Diagnostics).await
}

/// `POST /v1/jobs/{id}/cancel` — cancel a non-terminal job.
async fn cancel_job(State(state): State<Arc<AppState>>, Path(id): Path<String>) -> Response {
    let job = match db::get_job(&state.pool, &id).await {
        Ok(Some(j)) => j,
        Ok(None) => return not_found("job not found"),
        Err(_) => return err(ErrorCode::InternalError, "failed to load job"),
    };
    if job.status.is_terminal() {
        return err(ErrorCode::ValidationError, "job is already in a terminal state");
    }
    let _ = state.build.teardown(&id).await;
    // db::cancel_job only updates jobs still in a cancellable state, so a
    // worker that completed the job to `ready` in the meantime is not
    // overwritten — we then report its true current state.
    match db::cancel_job(&state.pool, &id).await {
        Ok(Some(canceled)) => {
            (StatusCode::OK, Json(job_view(&state, &canceled).await)).into_response()
        }
        Ok(None) => match db::get_job(&state.pool, &id).await {
            Ok(Some(current)) => {
                (StatusCode::OK, Json(job_view(&state, &current).await)).into_response()
            }
            _ => err(ErrorCode::InternalError, "job vanished during cancel"),
        },
        Err(_) => err(ErrorCode::InternalError, "failed to cancel job"),
    }
}

/// `DELETE /v1/jobs/{id}/preview` — expire a ready job's preview now.
async fn delete_preview(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Response {
    let job = match db::get_job(&state.pool, &id).await {
        Ok(Some(j)) => j,
        Ok(None) => return not_found("job not found"),
        Err(_) => return err(ErrorCode::InternalError, "failed to load job"),
    };
    if job.status != JobStatus::Ready {
        return err(ErrorCode::ValidationError, "job has no active preview");
    }
    let _ = state.build.teardown(&id).await;
    match db::finish_job(
        &state.pool,
        &id,
        JobStatus::Expired,
        100,
        None,
        None,
        job.artifact_url.as_deref(),
        None,
        None,
    )
    .await
    {
        Ok(()) => StatusCode::NO_CONTENT.into_response(),
        Err(_) => err(ErrorCode::InternalError, "failed to expire preview"),
    }
}

/// `GET /v1/healthz` — unauthenticated liveness/queue-depth check.
async fn healthz(State(state): State<Arc<AppState>>) -> Response {
    match db::count_queued(&state.pool).await {
        Ok(n) => (
            StatusCode::OK,
            Json(json!({
                "status": "ok",
                "queue_depth": n,
                "workers": state.config.worker_count,
            })),
        )
            .into_response(),
        Err(_) => (
            StatusCode::OK,
            Json(json!({
                "status": "degraded",
                "workers": state.config.worker_count,
            })),
        )
            .into_response(),
    }
}

/// Build the `/v1` API router. Every route is behind the bearer middleware
/// except `/v1/healthz`.
pub fn router(state: Arc<AppState>) -> Router {
    let protected = Router::new()
        .route("/v1/jobs", post(submit_job).get(list_jobs))
        .route("/v1/jobs/{id}", get(get_job))
        .route("/v1/jobs/{id}/logs", get(get_logs))
        .route("/v1/jobs/{id}/artifact", get(get_artifact))
        .route("/v1/jobs/{id}/diagnostics", get(get_diagnostics))
        .route("/v1/jobs/{id}/cancel", post(cancel_job))
        .route("/v1/jobs/{id}/preview", delete(delete_preview))
        .route_layer(middleware::from_fn_with_state(state.clone(), auth_mw));

    Router::new()
        .merge(protected)
        .route("/v1/healthz", get(healthz))
        .with_state(state)
}

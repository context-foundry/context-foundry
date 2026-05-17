//! Worker pool: claim queued jobs and drive each through the build lifecycle.
//!
//! In M1 the [`crate::service::backend::BuildBackend`] is the mock backend, so
//! `drive_job` exercises the full submit -> claim -> build -> ready path
//! deterministically by parsing a recorded event stream.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use chrono::{Duration as ChronoDuration, Utc};
use serde_json::{json, Value};
use ulid::Ulid;

use crate::service::backend::StorageGrant;
use crate::service::models::{self, Job, JobStatus};
use crate::service::{db, AppState};

/// Spawn `worker_count` worker loops. Returns their join handles.
pub fn run_worker_pool(
    state: Arc<AppState>,
    shutdown: Arc<AtomicBool>,
) -> Vec<tokio::task::JoinHandle<()>> {
    (0..state.config.worker_count)
        .map(|i| {
            let worker_id = format!("w{i}-{}", Ulid::new());
            tokio::spawn(worker_loop(state.clone(), worker_id, shutdown.clone()))
        })
        .collect()
}

async fn worker_loop(state: Arc<AppState>, worker_id: String, shutdown: Arc<AtomicBool>) {
    while !shutdown.load(Ordering::Relaxed) {
        match db::claim_next(&state.pool, &worker_id).await {
            Ok(Some(job)) => drive_job(&state, job).await,
            Ok(None) => tokio::time::sleep(Duration::from_millis(500)).await,
            Err(_) => tokio::time::sleep(Duration::from_secs(1)).await,
        }
    }
}

/// Drive one claimed job to a terminal state. Every fallible step is matched
/// explicitly (never `?`) so a failure records a typed `failed` job rather
/// than aborting the worker.
pub async fn drive_job(state: &Arc<AppState>, mut job: Job) {
    // Append the preview-contract task so the build emits a previewable app.
    // The DB row keeps the original tasks_md; only the staged copy is augmented.
    job.tasks_md = models::append_preview_contract(&job.tasks_md);

    // 1. Persist the submitted inputs.
    if let Err(e) = state
        .storage
        .put_input(&job.id, &job.spec_md, &job.tasks_md)
        .await
    {
        fail(
            state,
            &job.id,
            "internal_error",
            &format!("store input failed: {e}"),
            None,
        )
        .await;
        return;
    }

    // 2. Mint a scoped proxy token and issue the storage grant.
    let token = state.proxy.register(&job.id);
    let grant = match state.storage.issue_grant(&job.id).await {
        Ok(g) => g,
        Err(e) => {
            state.proxy.revoke(&token);
            fail(
                state,
                &job.id,
                "internal_error",
                &format!("issue grant failed: {e}"),
                None,
            )
            .await;
            return;
        }
    };

    // 3. Start the build under a wall-clock timeout. Exceeding it kills the
    //    build (via `cleanup` -> `teardown`, which `docker rm -f`s the
    //    container) and fails the job with `build_timeout`, not
    //    `backend_unavailable`.
    let build_timeout = Duration::from_secs(state.config.build_timeout_secs);
    let started = state.build.start_build(&job, &grant, &token);
    let handle = match tokio::time::timeout(build_timeout, started).await {
        Ok(Ok(h)) => h,
        Ok(Err(e)) => {
            cleanup(state, &token, &grant, &job.id).await;
            fail(
                state,
                &job.id,
                "backend_unavailable",
                &format!("start build failed: {e}"),
                None,
            )
            .await;
            return;
        }
        Err(_elapsed) => {
            cleanup(state, &token, &grant, &job.id).await;
            fail(
                state,
                &job.id,
                "build_timeout",
                &format!(
                    "build exceeded the {}s wall-clock timeout",
                    state.config.build_timeout_secs
                ),
                None,
            )
            .await;
            return;
        }
    };

    // 4. Mark building.
    let _ = db::update_job_progress(
        &state.pool,
        &job.id,
        JobStatus::Building,
        5,
        Some("Build container starting"),
        0.0,
        &json!({}),
        &json!({}),
    )
    .await;

    // 5. Collect the event stream.
    let stream = match state.build.stream_events(&handle).await {
        Ok(s) => s,
        Err(e) => {
            cleanup(state, &token, &grant, &job.id).await;
            fail(
                state,
                &job.id,
                "build_crashed",
                &format!("stream failed: {e}"),
                None,
            )
            .await;
            return;
        }
    };

    // 6. Parse it; a missing terminal report means the build crashed.
    let parsed = parse_stream(&stream);
    if parsed.report.is_none() {
        cleanup(state, &token, &grant, &job.id).await;
        fail(
            state,
            &job.id,
            "build_crashed",
            "no terminal report in the build stream",
            None,
        )
        .await;
        return;
    }

    // 7. Persist the logs.
    let _ = state.storage.put_logs(&job.id, &stream).await;

    // 8. Replay progress checkpoints.
    for (percent, label) in &parsed.checkpoints {
        let _ = db::update_job_progress(
            &state.pool,
            &job.id,
            JobStatus::Building,
            *percent,
            Some(label),
            parsed.cost,
            &parsed.quality,
            &parsed.detail,
        )
        .await;
        let _ = db::insert_event(&state.pool, &job.id, "stage", Some(*percent), Some(label)).await;
    }

    // 9. Collect and persist the source artifact + diagnostics now — BEFORE
    //    the preview image build — so a preview-deploy failure still leaves
    //    the source artifact downloadable.
    let artifact_bytes = match state.build.collect_artifact(&handle).await {
        Ok(bytes) => bytes,
        Err(e) => {
            cleanup(state, &token, &grant, &job.id).await;
            fail(
                state,
                &job.id,
                "internal_error",
                &format!("collect artifact failed: {e}"),
                None,
            )
            .await;
            return;
        }
    };
    let artifact_url = match state.storage.put_artifact(&job.id, &artifact_bytes).await {
        Ok(url) => url,
        Err(e) => {
            cleanup(state, &token, &grant, &job.id).await;
            fail(
                state,
                &job.id,
                "internal_error",
                &format!("store artifact failed: {e}"),
                None,
            )
            .await;
            return;
        }
    };
    // Diagnostics are best-effort: a failure must not sink the job.
    let diagnostics_bytes = state
        .build
        .collect_diagnostics(&handle)
        .await
        .unwrap_or_default();
    let _ = state
        .storage
        .put_diagnostics(&job.id, &diagnostics_bytes)
        .await;

    // 10. Move to deploying.
    let _ = db::update_job_progress(
        &state.pool,
        &job.id,
        JobStatus::Deploying,
        85,
        Some("Building app image"),
        parsed.cost,
        &parsed.quality,
        &parsed.detail,
    )
    .await;

    // 11. Build the app image (honors a root Dockerfile or a synthesized
    //     fallback). A failure here is non-fatal to the artifact: the source
    //     tarball stored in step 9 stays downloadable.
    let image = match state.build.build_image(&job).await {
        Ok(i) => i,
        Err(e) => {
            cleanup(state, &token, &grant, &job.id).await;
            fail(
                state,
                &job.id,
                "preview_deploy_failed",
                &format!("build image failed: {e}"),
                Some(&artifact_url),
            )
            .await;
            return;
        }
    };
    // Record which Dockerfile produced the image (honor vs fallback metric).
    let _ = db::insert_event(
        &state.pool,
        &job.id,
        "image_built",
        Some(85),
        Some(&image.dockerfile_source),
    )
    .await;

    // 12. Deploy the preview and health-check it.
    let preview = match state.build.deploy_preview(&job, &image).await {
        Ok(p) => p,
        Err(e) => {
            cleanup(state, &token, &grant, &job.id).await;
            fail(
                state,
                &job.id,
                "preview_deploy_failed",
                &format!("deploy preview failed: {e}"),
                Some(&artifact_url),
            )
            .await;
            return;
        }
    };

    // 13. Final deploying checkpoint.
    let _ = db::update_job_progress(
        &state.pool,
        &job.id,
        JobStatus::Deploying,
        95,
        Some("Deploying preview"),
        parsed.cost,
        &parsed.quality,
        &parsed.detail,
    )
    .await;

    // 14. Finish ready (sets percent = GREATEST(percent, 100) in the same write).
    let expires = Utc::now() + ChronoDuration::hours(job.ttl_hours as i64);
    let _ = db::finish_job(
        &state.pool,
        &job.id,
        JobStatus::Ready,
        100,
        None,
        None,
        Some(&artifact_url),
        Some(&preview.url),
        Some(expires),
    )
    .await;
    let _ = db::insert_event(&state.pool, &job.id, "ready", Some(100), None).await;

    // 15. Release the proxy token and storage grant.
    cleanup(state, &token, &grant, &job.id).await;
}

async fn cleanup(state: &Arc<AppState>, token: &str, grant: &StorageGrant, job_id: &str) {
    state.proxy.revoke(token);
    let _ = state.storage.revoke_grant(grant).await;
    let _ = state.build.teardown(job_id).await;
}

async fn fail(state: &Arc<AppState>, id: &str, code: &str, msg: &str, artifact_url: Option<&str>) {
    // `percent = 0` -> GREATEST leaves the existing percent unchanged. An
    // `artifact_url` is carried through on a preview failure so the source
    // tarball stays downloadable.
    let _ = db::finish_job(
        &state.pool,
        id,
        JobStatus::Failed,
        0,
        Some(code),
        Some(msg),
        artifact_url,
        None,
        None,
    )
    .await;
}

/// The build-relevant facts extracted from a recorded event stream.
struct ParsedStream {
    cost: f64,
    quality: Value,
    detail: Value,
    report: Option<Value>,
    checkpoints: Vec<(i32, String)>,
}

/// Parse the recorded JSONL event stream.
///
/// A value with an `"event"` key is a streamed event; a value with a
/// `"schema_version"` key and no `"event"` key is the terminal session
/// report. The report's `cost_usd` is authoritative; the streamed cumulative
/// cost is the fallback.
fn parse_stream(jsonl: &str) -> ParsedStream {
    let mut last_cumulative = 0.0_f64;
    let mut last_stage_label = String::new();
    let mut last_total = 0_i64;
    let mut last_completed = 0_i64;
    let mut last_wip = 0_i64;
    let mut checkpoints: Vec<(i32, String)> = Vec::new();
    let mut report: Option<Value> = None;

    for line in jsonl.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let value: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(_) => continue,
        };
        if let Some(event) = value.get("event").and_then(|e| e.as_str()) {
            match event {
                "counts" => {
                    last_total = value["tasks_total"].as_i64().unwrap_or(last_total);
                    last_completed = value["tasks_completed"].as_i64().unwrap_or(0);
                    last_wip = value["tasks_wip"].as_i64().unwrap_or(0);
                    let total = last_total.max(1);
                    let frac = (last_completed + last_wip) as f64 / total as f64;
                    let percent = 5 + (frac * 80.0) as i32;
                    checkpoints.push((percent, last_stage_label.clone()));
                }
                "cost" => {
                    last_cumulative =
                        value["cumulative_usd"].as_f64().unwrap_or(last_cumulative);
                }
                "stage_started" => {
                    let role = value["role"].as_str().unwrap_or("");
                    let task_id = value["task_id"].as_str().unwrap_or("");
                    last_stage_label = format!("{role} {task_id}").trim().to_string();
                }
                _ => {}
            }
        } else if value.get("schema_version").is_some() {
            report = Some(value);
        }
    }

    let cost = report
        .as_ref()
        .and_then(|r| r.get("cost_usd"))
        .and_then(|c| c.as_f64())
        .unwrap_or(last_cumulative);

    let mut high = 0_i64;
    let mut medium = 0_i64;
    let mut low = 0_i64;
    let mut any_wip = false;
    if let Some(r) = &report {
        if let Some(tasks) = r.get("tasks").and_then(|t| t.as_array()) {
            for task in tasks {
                if task
                    .get("status")
                    .and_then(|s| s.as_str())
                    .map(|s| s.eq_ignore_ascii_case("wip"))
                    .unwrap_or(false)
                {
                    any_wip = true;
                }
                let findings = &task["findings"];
                high += findings.get("high").and_then(|v| v.as_i64()).unwrap_or(0);
                medium += findings.get("medium").and_then(|v| v.as_i64()).unwrap_or(0);
                low += findings.get("low").and_then(|v| v.as_i64()).unwrap_or(0);
            }
        }
    }
    let audit = if any_wip { "fail" } else { "pass" };
    let quality = json!({
        "audit": audit,
        "findings": { "high": high, "medium": medium, "low": low },
    });
    let detail = json!({
        "tasks_total": last_total,
        "tasks_completed": last_completed,
        "tasks_wip": last_wip,
        "stages": [],
    });

    ParsedStream {
        cost,
        quality,
        detail,
        report,
        checkpoints,
    }
}

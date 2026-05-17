//! Job/status/error domain types, request validation, and the idempotency
//! request hash.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::service::config::ServiceConfig;

// ─── Job lifecycle ──────────────────────────────────────────────────────────

/// Lifecycle state of a build job.
///
/// Monotonicity is enforced by SQL guards (claim filters `status='queued'`,
/// progress/finish filter `status <> 'canceled'`, percent uses `GREATEST`),
/// not by an in-process transition machine — that machine is T35.7 scope.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Queued,
    Building,
    Deploying,
    Ready,
    Failed,
    Canceled,
    Expired,
}

impl JobStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            JobStatus::Queued => "queued",
            JobStatus::Building => "building",
            JobStatus::Deploying => "deploying",
            JobStatus::Ready => "ready",
            JobStatus::Failed => "failed",
            JobStatus::Canceled => "canceled",
            JobStatus::Expired => "expired",
        }
    }

    /// Parse a status from its wire/DB representation.
    pub fn from_wire(s: &str) -> Option<JobStatus> {
        match s {
            "queued" => Some(JobStatus::Queued),
            "building" => Some(JobStatus::Building),
            "deploying" => Some(JobStatus::Deploying),
            "ready" => Some(JobStatus::Ready),
            "failed" => Some(JobStatus::Failed),
            "canceled" => Some(JobStatus::Canceled),
            "expired" => Some(JobStatus::Expired),
            _ => None,
        }
    }

    /// A job in a terminal state cannot be claimed or progressed further.
    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            JobStatus::Ready | JobStatus::Failed | JobStatus::Canceled | JobStatus::Expired
        )
    }
}

/// Typed API error codes. `http_status` maps each to its response status.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    ValidationError,
    IdempotencyConflict,
    QueueFull,
    BuildTimeout,
    BuildCrashed,
    PreviewDeployFailed,
    BackendUnavailable,
    Canceled,
    InternalError,
}

impl ErrorCode {
    pub fn as_str(&self) -> &'static str {
        match self {
            ErrorCode::ValidationError => "validation_error",
            ErrorCode::IdempotencyConflict => "idempotency_conflict",
            ErrorCode::QueueFull => "queue_full",
            ErrorCode::BuildTimeout => "build_timeout",
            ErrorCode::BuildCrashed => "build_crashed",
            ErrorCode::PreviewDeployFailed => "preview_deploy_failed",
            ErrorCode::BackendUnavailable => "backend_unavailable",
            ErrorCode::Canceled => "canceled",
            ErrorCode::InternalError => "internal_error",
        }
    }

    pub fn http_status(&self) -> u16 {
        match self {
            ErrorCode::ValidationError => 400,
            ErrorCode::IdempotencyConflict => 409,
            ErrorCode::QueueFull => 429,
            _ => 500,
        }
    }
}

/// A build job as stored in the `jobs` table.
#[derive(Clone, Debug)]
pub struct Job {
    pub id: String,
    pub app_name: String,
    pub owner: String,
    pub status: JobStatus,
    pub percent: i32,
    pub stage_label: Option<String>,
    pub spec_md: String,
    pub tasks_md: String,
    pub artifact_url: Option<String>,
    pub preview_url: Option<String>,
    pub preview_expires_at: Option<DateTime<Utc>>,
    pub cost_usd: f64,
    pub ttl_hours: i32,
    pub idempotency_key: String,
    pub request_hash: String,
    pub worker_id: Option<String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    pub quality: serde_json::Value,
    pub detail: serde_json::Value,
    pub created_at: DateTime<Utc>,
    pub started_at: Option<DateTime<Utc>>,
    pub finished_at: Option<DateTime<Utc>>,
    pub updated_at: DateTime<Utc>,
}

/// A `POST /v1/jobs` request body.
#[derive(Clone, Debug, Deserialize)]
pub struct SubmitRequest {
    pub app_name: String,
    pub spec_md: String,
    pub tasks_md: String,
    pub owner: String,
    pub preview_ttl_hours: Option<i32>,
    pub idempotency_key: String,
}

// ─── Validation + idempotency ───────────────────────────────────────────────

/// An app name must be a DNS-label-style slug: non-empty, <= 63 chars, only
/// `[a-z0-9-]`, and not bordered by `-`.
pub fn valid_app_name(name: &str) -> bool {
    if name.is_empty() || name.len() > 63 {
        return false;
    }
    if name.starts_with('-') || name.ends_with('-') {
        return false;
    }
    name.chars()
        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-')
}

/// Clamp a requested preview TTL to the server's `[min, max]` window,
/// defaulting to `default_ttl_hours` when the request omits one.
pub fn clamp_ttl(cfg: &ServiceConfig, requested: Option<i32>) -> i32 {
    requested
        .unwrap_or(cfg.default_ttl_hours)
        .clamp(cfg.min_ttl_hours, cfg.max_ttl_hours)
}

/// Hash the *normalized semantic request* used for idempotency comparison.
///
/// The TTL component is the SERVER-CLAMPED value, so two requests whose raw
/// `preview_ttl_hours` differ but clamp identically produce the same hash.
/// Fields are separated by a `0x1e` record-separator byte so concatenation
/// ambiguity cannot collide distinct inputs.
pub fn normalized_request_hash(
    app_name: &str,
    spec_md: &str,
    tasks_md: &str,
    clamped_ttl: i32,
) -> String {
    let mut hasher = blake3::Hasher::new();
    for field in [app_name, spec_md, tasks_md] {
        hasher.update(field.as_bytes());
        hasher.update(&[0x1e]);
    }
    hasher.update(clamped_ttl.to_string().as_bytes());
    hasher.finalize().to_hex().to_string()
}

// ─── Preview contract ───────────────────────────────────────────────────────

/// The preview-contract task appended to every build's `TASKS.md`. It tells
/// the build agent to emit a previewable, self-contained `Dockerfile`.
pub const PREVIEW_CONTRACT_TASK: &str = "- [ ] TPREVIEW.1: Produce a root-level `Dockerfile` that builds and serves this app for preview hosting. The container must bind `0.0.0.0` on the `$PORT` environment variable (default `8080`) and `EXPOSE` that port; a request to `/` or `/healthz` must return HTTP 200. The app must run fully self-contained: SQLite or in-memory storage only, no external database, no required secrets or environment configuration. Do not set `X-Frame-Options` or a `frame-ancestors` Content-Security-Policy that would block iframe embedding.";

/// Append [`PREVIEW_CONTRACT_TASK`] to a `TASKS.md` body as a new task line,
/// separated from the existing content by a blank line.
pub fn append_preview_contract(tasks_md: &str) -> String {
    let mut out = tasks_md.to_string();
    if !out.ends_with('\n') {
        out.push('\n');
    }
    out.push('\n');
    out.push_str(PREVIEW_CONTRACT_TASK);
    out.push('\n');
    out
}

/// Validate a submit request. Returns a human-readable reason on failure.
pub fn validate_submit(cfg: &ServiceConfig, req: &SubmitRequest) -> Result<(), String> {
    if !valid_app_name(&req.app_name) {
        return Err("app_name must be a non-empty [a-z0-9-] slug not bordered by '-'".to_string());
    }
    if req.spec_md.is_empty() {
        return Err("spec_md must not be empty".to_string());
    }
    if req.spec_md.len() > cfg.max_input_bytes {
        return Err(format!(
            "spec_md exceeds the maximum input size of {} bytes",
            cfg.max_input_bytes
        ));
    }
    if req.tasks_md.is_empty() {
        return Err("tasks_md must not be empty".to_string());
    }
    if req.tasks_md.len() > cfg.max_input_bytes {
        return Err(format!(
            "tasks_md exceeds the maximum input size of {} bytes",
            cfg.max_input_bytes
        ));
    }
    if req.owner.is_empty() {
        return Err("owner must not be empty".to_string());
    }
    if req.idempotency_key.is_empty() {
        return Err("idempotency_key must not be empty".to_string());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::SocketAddr;
    use std::path::PathBuf;

    fn cfg() -> ServiceConfig {
        ServiceConfig {
            database_url: "postgres://localhost/test".to_string(),
            bind_addr: "127.0.0.1:0".parse::<SocketAddr>().unwrap(),
            proxy_bind_addr: "127.0.0.1:0".parse::<SocketAddr>().unwrap(),
            api_keys: vec!["k".to_string()],
            anthropic_api_key: String::new(),
            anthropic_base_url: "https://api.anthropic.com".to_string(),
            worker_count: 1,
            queue_cap: 10,
            min_ttl_hours: 1,
            default_ttl_hours: 24,
            max_ttl_hours: 72,
            storage_root: PathBuf::from("/tmp/foundry-test"),
            max_input_bytes: 1024,
            reaper_interval_secs: 60,
            proxy_max_concurrent: 4,
            proxy_max_body_bytes: 4096,
            proxy_max_output_tokens: 8192,
            proxy_model_prefixes: vec!["claude-".to_string()],
            build_backend: "mock".to_string(),
            builder_image: "foundry-builder:latest".to_string(),
            builder_proxy_url: "http://host.docker.internal:8788".to_string(),
            docker_bin: "docker".to_string(),
            preview_network: "foundry-preview".to_string(),
            preview_base_domain: "foundry.local".to_string(),
            caddy_admin_url: "http://localhost:2019".to_string(),
            caddy_server_name: "srv0".to_string(),
            preview_health_timeout_secs: 60,
            preview_memory: "512m".to_string(),
            preview_cpus: "1".to_string(),
            preview_pids_limit: 256,
            build_timeout_secs: 3600,
            drain_deadline_secs: 30,
        }
    }

    #[test]
    fn valid_app_name_accepts_and_rejects() {
        assert!(valid_app_name("recipe-finder"));
        assert!(valid_app_name("app1"));
        assert!(!valid_app_name("Recipe"));
        assert!(!valid_app_name("-x"));
        assert!(!valid_app_name("x-"));
        assert!(!valid_app_name(""));
        assert!(!valid_app_name("under_score"));
    }

    #[test]
    fn clamp_ttl_clamps_bounds_and_default() {
        let c = cfg();
        assert_eq!(clamp_ttl(&c, Some(0)), 1); // below min
        assert_eq!(clamp_ttl(&c, Some(99999)), 72); // above max
        assert_eq!(clamp_ttl(&c, None), 24); // default
        assert_eq!(clamp_ttl(&c, Some(48)), 48); // in-range untouched
    }

    #[test]
    fn request_hash_is_stable_and_sensitive() {
        let a = normalized_request_hash("app", "spec", "tasks", 24);
        let b = normalized_request_hash("app", "spec", "tasks", 24);
        assert_eq!(a, b);
        assert_ne!(a, normalized_request_hash("app", "spec-2", "tasks", 24));
        assert_ne!(a, normalized_request_hash("app", "spec", "tasks", 48));
    }

    #[test]
    fn preview_contract_is_appended_as_a_task_line() {
        let out = append_preview_contract("- [ ] T1.1: build the app");
        assert!(out.contains("- [ ] T1.1: build the app"));
        assert!(out.contains("TPREVIEW.1"));
        assert!(out.ends_with('\n'));
        // Idempotent newline handling: an input that already ends in a
        // newline still yields a clean append.
        let out2 = append_preview_contract("- [ ] T1.1: x\n");
        assert!(out2.contains("TPREVIEW.1"));
    }

    #[test]
    fn request_hash_equal_when_clamped_ttl_equal() {
        let c = cfg();
        // Two distinct raw TTLs that both clamp to max_ttl_hours (72).
        let t1 = clamp_ttl(&c, Some(99999));
        let t2 = clamp_ttl(&c, Some(500));
        assert_eq!(t1, t2);
        assert_eq!(
            normalized_request_hash("app", "spec", "tasks", t1),
            normalized_request_hash("app", "spec", "tasks", t2),
        );
    }
}

//! Anthropic auth proxy.
//!
//! The proxy holds the real `ANTHROPIC_API_KEY` and never lets it cross to a
//! build. Each build is issued a scoped, revocable proxy token; the build
//! presents that token, the proxy validates it and enforces coarse abuse
//! limits (Claude-only model allowlist, max concurrent in-flight requests,
//! max request body size, max output tokens), then forwards to Anthropic with
//! the real key.

use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, RwLock};

use axum::{
    body::Body,
    extract::State,
    http::{header, HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::post,
    Json, Router,
};
use serde_json::json;
use ulid::Ulid;

use crate::service::config::ServiceConfig;
use crate::service::AppState;

/// A per-build proxy token with an atomic in-flight-request counter.
pub struct ProxyToken {
    pub job_id: String,
    pub in_flight: AtomicUsize,
}

impl ProxyToken {
    /// Atomically reserve one in-flight slot. Returns `false` (and rolls the
    /// counter back) when the concurrency cap is already reached, so there is
    /// no check-then-act race.
    pub fn try_acquire(&self, max: usize) -> bool {
        let prev = self.in_flight.fetch_add(1, Ordering::SeqCst);
        if prev >= max {
            self.in_flight.fetch_sub(1, Ordering::SeqCst);
            false
        } else {
            true
        }
    }

    /// Release a previously acquired in-flight slot.
    pub fn release(&self) {
        self.in_flight.fetch_sub(1, Ordering::SeqCst);
    }
}

/// Reasons the proxy rejects a request.
#[derive(Debug, PartialEq, Eq)]
pub enum ProxyDenial {
    Unauthorized,
    ModelNotAllowed,
    BodyTooLarge,
    OutputTokensTooHigh,
    TooManyConcurrent,
}

impl ProxyDenial {
    pub fn http_status(&self) -> StatusCode {
        match self {
            ProxyDenial::Unauthorized => StatusCode::UNAUTHORIZED,
            ProxyDenial::ModelNotAllowed => StatusCode::FORBIDDEN,
            ProxyDenial::BodyTooLarge => StatusCode::PAYLOAD_TOO_LARGE,
            ProxyDenial::OutputTokensTooHigh => StatusCode::BAD_REQUEST,
            ProxyDenial::TooManyConcurrent => StatusCode::TOO_MANY_REQUESTS,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            ProxyDenial::Unauthorized => "unauthorized",
            ProxyDenial::ModelNotAllowed => "model_not_allowed",
            ProxyDenial::BodyTooLarge => "body_too_large",
            ProxyDenial::OutputTokensTooHigh => "output_tokens_too_high",
            ProxyDenial::TooManyConcurrent => "too_many_concurrent_requests",
        }
    }
}

/// Issues, validates, and revokes per-build proxy tokens.
pub struct ProxyRegistry {
    cfg: ServiceConfig,
    http: reqwest::Client,
    tokens: RwLock<HashMap<String, Arc<ProxyToken>>>,
}

impl ProxyRegistry {
    pub fn new(cfg: ServiceConfig) -> ProxyRegistry {
        ProxyRegistry {
            cfg,
            http: reqwest::Client::new(),
            tokens: RwLock::new(HashMap::new()),
        }
    }

    /// Mint a fresh scoped token for a build.
    pub fn register(&self, job_id: &str) -> String {
        let token = format!("fb_{}", Ulid::new());
        let entry = Arc::new(ProxyToken {
            job_id: job_id.to_string(),
            in_flight: AtomicUsize::new(0),
        });
        self.tokens
            .write()
            .expect("proxy token map poisoned")
            .insert(token.clone(), entry);
        token
    }

    /// Revoke a token; subsequent requests with it are rejected.
    pub fn revoke(&self, token: &str) {
        self.tokens
            .write()
            .expect("proxy token map poisoned")
            .remove(token);
    }

    /// Revoke every token issued for one job; returns how many were removed.
    /// Used by cancel and the orphan sweep.
    pub fn revoke_job(&self, job_id: &str) -> usize {
        let mut map = self.tokens.write().expect("proxy token map poisoned");
        let before = map.len();
        map.retain(|_, tok| tok.job_id != job_id);
        before - map.len()
    }

    /// Drop every token whose job is not in `active_ids` (orphan token sweep);
    /// returns how many were removed.
    pub fn sweep(&self, active_ids: &[&str]) -> usize {
        let mut map = self.tokens.write().expect("proxy token map poisoned");
        let before = map.len();
        map.retain(|_, tok| active_ids.contains(&tok.job_id.as_str()));
        before - map.len()
    }

    /// Look up a live token.
    pub fn validate(&self, token: &str) -> Option<Arc<ProxyToken>> {
        self.tokens
            .read()
            .expect("proxy token map poisoned")
            .get(token)
            .cloned()
    }

    /// Run the stateless abuse checks for a request. The concurrency cap is
    /// NOT checked here — it is enforced atomically by
    /// [`ProxyToken::try_acquire`], so there is no check-then-act race.
    pub fn evaluate(
        &self,
        token: &str,
        model: &str,
        max_tokens: u64,
        body_len: usize,
    ) -> Result<Arc<ProxyToken>, ProxyDenial> {
        let tok = self.validate(token).ok_or(ProxyDenial::Unauthorized)?;
        if body_len > self.cfg.proxy_max_body_bytes {
            return Err(ProxyDenial::BodyTooLarge);
        }
        let model_allowed = self
            .cfg
            .proxy_model_prefixes
            .iter()
            .any(|p| model.starts_with(p.as_str()));
        if !model_allowed {
            return Err(ProxyDenial::ModelNotAllowed);
        }
        if max_tokens > self.cfg.proxy_max_output_tokens {
            return Err(ProxyDenial::OutputTokensTooHigh);
        }
        Ok(tok)
    }
}

fn denial_response(denial: &ProxyDenial) -> Response {
    (
        denial.http_status(),
        Json(json!({ "error": denial.as_str(), "message": "proxy request denied" })),
    )
        .into_response()
}

/// `POST /v1/messages` — validate the scoped token + limits, then forward to
/// Anthropic with the real key. The real key is never echoed in a response.
async fn messages_handler(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    body: Body,
) -> Response {
    let cfg = &state.config;

    let token = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .unwrap_or("")
        .to_string();

    let body_bytes = match axum::body::to_bytes(body, cfg.proxy_max_body_bytes + 1).await {
        Ok(b) => b,
        Err(_) => return denial_response(&ProxyDenial::BodyTooLarge),
    };

    let parsed: serde_json::Value =
        serde_json::from_slice(&body_bytes).unwrap_or(serde_json::Value::Null);
    let model = parsed
        .get("model")
        .and_then(|m| m.as_str())
        .unwrap_or("")
        .to_string();
    let max_tokens = parsed
        .get("max_tokens")
        .and_then(|m| m.as_u64())
        .unwrap_or(0);

    let tok = match state
        .proxy
        .evaluate(&token, &model, max_tokens, body_bytes.len())
    {
        Ok(t) => t,
        Err(d) => return denial_response(&d),
    };

    if !tok.try_acquire(cfg.proxy_max_concurrent) {
        return denial_response(&ProxyDenial::TooManyConcurrent);
    }

    let upstream = state
        .proxy
        .http
        .post(format!("{}/v1/messages", cfg.anthropic_base_url))
        .header("x-api-key", &cfg.anthropic_api_key)
        .header("anthropic-version", "2023-06-01")
        .header(header::CONTENT_TYPE, "application/json")
        .body(body_bytes.to_vec())
        .send()
        .await;
    tok.release();

    match upstream {
        Ok(resp) => {
            let status = StatusCode::from_u16(resp.status().as_u16())
                .unwrap_or(StatusCode::BAD_GATEWAY);
            let bytes = resp.bytes().await.unwrap_or_default();
            (
                status,
                [(header::CONTENT_TYPE, "application/json")],
                bytes,
            )
                .into_response()
        }
        Err(_) => (
            StatusCode::BAD_GATEWAY,
            Json(json!({ "error": "upstream_error", "message": "anthropic request failed" })),
        )
            .into_response(),
    }
}

/// The proxy router (`/v1/messages` only).
pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/v1/messages", post(messages_handler))
        .with_state(state)
}

/// Bind and serve the auth proxy on `proxy_bind_addr`.
pub async fn serve_proxy(state: Arc<AppState>) -> anyhow::Result<()> {
    let addr = state.config.proxy_bind_addr;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, router(state)).await?;
    Ok(())
}

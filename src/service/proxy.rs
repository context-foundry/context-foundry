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
use std::time::{Duration, SystemTime};

use anyhow::{anyhow, bail, Context, Result};
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

use crate::service::config::{
    resolve_upstream_auth, ServiceConfig, UpstreamAuthConfig, UpstreamAuthMode,
};
use crate::service::ratelimit::RateLimitState;
use crate::service::AppState;

/// The `anthropic-beta` header value required when authenticating to the
/// Anthropic API with an OAuth token rather than an API key.
const OAUTH_BETA_HEADER: &str = "oauth-2025-04-20";

/// Refresh an OAuth access token this many seconds before it expires.
const OAUTH_REFRESH_SKEW_SECS: u64 = 300;

/// The upstream credential the proxy presents to Anthropic. Resolved once at
/// `ProxyRegistry::new` time; the real value never leaves this process.
enum UpstreamAuth {
    /// Legacy mode: a static `ANTHROPIC_API_KEY`.
    ApiKey(String),
    /// OAuth mode: a refreshable access token.
    OAuth(Arc<OAuthTokenState>),
}

/// A point-in-time OAuth access token and its expiry.
#[derive(Clone, Debug)]
struct TokenSnapshot {
    access_token: String,
    expires_at: Option<SystemTime>,
}

/// Holds the live OAuth access token and refreshes it before expiry.
struct OAuthTokenState {
    snapshot: RwLock<TokenSnapshot>,
    refresh_token: Option<String>,
    client_id: Option<String>,
    refresh_url: String,
    http: reqwest::Client,
    skew: Duration,
}

impl UpstreamAuth {
    /// Turn the env-resolved [`UpstreamAuthConfig`] into the runtime credential.
    fn from_resolved(cfg: UpstreamAuthConfig, http: reqwest::Client) -> UpstreamAuth {
        match cfg.mode {
            UpstreamAuthMode::ApiKey => UpstreamAuth::ApiKey(cfg.api_key),
            UpstreamAuthMode::OAuth => {
                let refresh_token = (!cfg.oauth_refresh_token.is_empty())
                    .then(|| cfg.oauth_refresh_token.clone());
                let client_id =
                    (!cfg.oauth_client_id.is_empty()).then(|| cfg.oauth_client_id.clone());
                UpstreamAuth::OAuth(Arc::new(OAuthTokenState::new(
                    cfg.oauth_token,
                    cfg.oauth_expires_at,
                    refresh_token,
                    client_id,
                    cfg.oauth_refresh_url,
                    http,
                )))
            }
        }
    }
}

impl OAuthTokenState {
    /// Construct the token state with the configured access token.
    fn new(
        access_token: String,
        expires_at: Option<SystemTime>,
        refresh_token: Option<String>,
        client_id: Option<String>,
        refresh_url: String,
        http: reqwest::Client,
    ) -> OAuthTokenState {
        OAuthTokenState {
            snapshot: RwLock::new(TokenSnapshot {
                access_token,
                expires_at,
            }),
            refresh_token,
            client_id,
            refresh_url,
            http,
            skew: Duration::from_secs(OAUTH_REFRESH_SKEW_SECS),
        }
    }

    /// Return a valid access token, refreshing first if it is near expiry. A
    /// refresh failure is propagated as `Err` (a typed upstream error), never
    /// a panic.
    async fn current_token(&self) -> Result<String> {
        let needs = {
            let snap = self.snapshot.read().expect("oauth token lock poisoned");
            needs_refresh(snap.expires_at, SystemTime::now(), self.skew)
        };
        if !needs {
            return Ok(self
                .snapshot
                .read()
                .expect("oauth token lock poisoned")
                .access_token
                .clone());
        }
        let refreshed = self.refresh().await;
        self.apply_refreshed(refreshed)
    }

    /// POST the refresh token to the OAuth endpoint and parse the new token.
    /// A missing refresh token, a network failure, a non-2xx status, or a
    /// malformed body all return `Err` -- never a panic; the error message
    /// never includes the token.
    async fn refresh(&self) -> Result<TokenSnapshot> {
        let refresh_token = match self.refresh_token.as_deref() {
            Some(t) if !t.is_empty() => t,
            _ => bail!("oauth access token requires refresh but no refresh token is configured"),
        };
        let mut form: Vec<(&str, &str)> = vec![
            ("grant_type", "refresh_token"),
            ("refresh_token", refresh_token),
        ];
        if let Some(cid) = self.client_id.as_deref().filter(|s| !s.is_empty()) {
            form.push(("client_id", cid));
        }
        let resp = self
            .http
            .post(&self.refresh_url)
            .form(&form)
            .send()
            .await
            .context("oauth token refresh request failed")?;
        let status = resp.status();
        let body = resp
            .bytes()
            .await
            .context("read oauth refresh response body")?;
        if !status.is_success() {
            bail!("oauth token refresh returned HTTP {}", status.as_u16());
        }
        parse_refresh_response(&body, SystemTime::now())
    }

    /// Commit a successful refresh to `snapshot`, or surface the failure. On
    /// `Err` the snapshot is left unchanged.
    fn apply_refreshed(&self, result: Result<TokenSnapshot>) -> Result<String> {
        let snap = result.context("oauth upstream token refresh failed")?;
        let mut guard = self.snapshot.write().expect("oauth token lock poisoned");
        *guard = snap;
        Ok(guard.access_token.clone())
    }
}

/// Build the legacy `x-api-key` header set.
fn api_key_headers(key: &str) -> Vec<(&'static str, String)> {
    vec![("x-api-key", key.to_string())]
}

/// Build the OAuth header set: a bearer token plus the required
/// `anthropic-beta` header.
fn oauth_headers(access_token: &str) -> Vec<(&'static str, String)> {
    vec![
        ("authorization", format!("Bearer {access_token}")),
        ("anthropic-beta", OAUTH_BETA_HEADER.to_string()),
    ]
}

/// Append the comma-separated `anthropic-beta` tokens in `raw` to `into`,
/// trimmed and de-duplicated.
fn push_beta_tokens(raw: &str, into: &mut Vec<String>) {
    for tok in raw.split(',').map(str::trim).filter(|s| !s.is_empty()) {
        if !into.iter().any(|p| p == tok) {
            into.push(tok.to_string());
        }
    }
}

/// Merge the client's inbound `anthropic-beta` opt-ins with the beta tokens the
/// upstream auth headers carry, into one de-duplicated header value. Returns
/// `None` when neither side requests a beta.
///
/// The proxy rebuilds the upstream request from scratch, so without this merge
/// the client's `anthropic-beta` is dropped — and a beta body field it depends
/// on (e.g. `context_management`) is then rejected upstream with a 400
/// "Extra inputs are not permitted".
fn merge_anthropic_beta(
    inbound: &HeaderMap,
    auth_headers: &[(&'static str, String)],
) -> Option<String> {
    let mut parts: Vec<String> = Vec::new();
    for v in inbound.get_all("anthropic-beta").iter() {
        if let Ok(s) = v.to_str() {
            push_beta_tokens(s, &mut parts);
        }
    }
    for (name, value) in auth_headers {
        if name.eq_ignore_ascii_case("anthropic-beta") {
            push_beta_tokens(value, &mut parts);
        }
    }
    (!parts.is_empty()).then(|| parts.join(","))
}

/// Decide whether an OAuth token must be refreshed: `true` when it is expired
/// or within `skew` of expiry. A token with no expiry never needs refresh.
fn needs_refresh(expires_at: Option<SystemTime>, now: SystemTime, skew: Duration) -> bool {
    match expires_at {
        None => false,
        Some(exp) => match now.checked_add(skew) {
            Some(deadline) => deadline >= exp,
            None => true,
        },
    }
}

/// Parse an OAuth token-refresh JSON response. Malformed JSON or a
/// missing/empty `access_token` returns `Err` -- never a panic.
fn parse_refresh_response(body: &[u8], now: SystemTime) -> Result<TokenSnapshot> {
    let v: serde_json::Value =
        serde_json::from_slice(body).context("parse oauth refresh response as JSON")?;
    let access_token = v
        .get("access_token")
        .and_then(|t| t.as_str())
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow!("oauth refresh response missing access_token"))?
        .to_string();
    let expires_at = v
        .get("expires_in")
        .and_then(|e| e.as_u64())
        .and_then(|secs| now.checked_add(Duration::from_secs(secs)));
    Ok(TokenSnapshot {
        access_token,
        expires_at,
    })
}

/// The typed `502` returned when an OAuth refresh fails. It carries a generic
/// message and never echoes the real credential.
fn upstream_credential_error() -> Response {
    (
        StatusCode::BAD_GATEWAY,
        Json(json!({ "error": "upstream_error", "message": "upstream credential unavailable" })),
    )
        .into_response()
}

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
    /// Rate-limit-aware dispatch gate driven by upstream Anthropic responses.
    ratelimit: RateLimitState,
    /// The upstream credential presented to Anthropic; never leaves the proxy.
    upstream: UpstreamAuth,
}

impl ProxyRegistry {
    pub fn new(cfg: ServiceConfig) -> ProxyRegistry {
        let http = reqwest::Client::new();
        // `from_env()` already validated the credential in production; this
        // fallback only covers the test/embedded path where a `ServiceConfig`
        // is built directly. It degrades to legacy `api_key` mode.
        let resolved = resolve_upstream_auth(&cfg.anthropic_api_key).unwrap_or_else(|_| {
            UpstreamAuthConfig {
                mode: UpstreamAuthMode::ApiKey,
                api_key: cfg.anthropic_api_key.clone(),
                oauth_token: String::new(),
                oauth_refresh_token: String::new(),
                oauth_client_id: String::new(),
                oauth_refresh_url: String::new(),
                oauth_expires_at: None,
            }
        });
        let upstream = UpstreamAuth::from_resolved(resolved, http.clone());
        ProxyRegistry {
            cfg,
            http,
            tokens: RwLock::new(HashMap::new()),
            ratelimit: RateLimitState::new(),
            upstream,
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

    /// The remaining rate-limit pause, or `None` when dispatch is clear.
    pub fn dispatch_delay(&self) -> Option<Duration> {
        self.ratelimit.dispatch_delay()
    }

    /// Feed an upstream Anthropic response into the rate-limit gate. A `429`
    /// arms the gate; any other status leaves dispatch clear.
    pub fn note_upstream_response(&self, status: u16, headers: &HeaderMap) {
        self.ratelimit.record_response(status, headers);
    }

    /// Produce the auth headers for the upstream forward, refreshing an OAuth
    /// token first when it is near expiry. An OAuth refresh failure surfaces
    /// as `Err` (a typed upstream error), never a panic.
    async fn upstream_headers(&self) -> Result<Vec<(&'static str, String)>> {
        match &self.upstream {
            UpstreamAuth::ApiKey(key) => Ok(api_key_headers(key)),
            UpstreamAuth::OAuth(state) => {
                let token = state.current_token().await?;
                Ok(oauth_headers(&token))
            }
        }
    }
}

fn denial_response(denial: &ProxyDenial) -> Response {
    (
        denial.http_status(),
        Json(json!({ "error": denial.as_str(), "message": "proxy request denied" })),
    )
        .into_response()
}

/// Record a limiter denial in telemetry, then return the typed denial
/// response. Telemetry recording is additive — the HTTP status/body are
/// unchanged from [`denial_response`].
fn denied(state: &Arc<AppState>, job_id: Option<&str>, denial: ProxyDenial) -> Response {
    state.telemetry.record_limiter_denial(
        job_id,
        denial.as_str(),
        "auth proxy abuse damper rejected request",
    );
    denial_response(&denial)
}

/// A typed `429` response carrying a `Retry-After` header, returned when the
/// rate-limit gate is armed. It never carries the real `ANTHROPIC_API_KEY`.
fn rate_limited_response(delay: Duration) -> Response {
    (
        StatusCode::TOO_MANY_REQUESTS,
        [(header::RETRY_AFTER, delay.as_secs().max(1).to_string())],
        Json(json!({
            "error": "rate_limited",
            "message": "upstream rate limit reached; dispatch paused"
        })),
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
        Err(_) => return denied(&state, None, ProxyDenial::BodyTooLarge),
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
        Err(d) => return denied(&state, None, d),
    };

    // Rate-limit-aware dispatch: when Anthropic recently returned 429,
    // refuse new upstream calls until its retry-after window clears
    // rather than piling load onto an account over its headroom.
    if let Some(delay) = state.proxy.dispatch_delay() {
        state
            .telemetry
            .record_rate_limit_pause(Some(&tok.job_id), delay.as_secs());
        return rate_limited_response(delay);
    }

    // Resolve the upstream credential (refreshing an OAuth token when it
    // is near expiry). A refresh failure is a typed upstream error, never
    // a panic, and never echoes the real credential. This runs before
    // `try_acquire` so a refresh failure leaks no in-flight slot.
    let auth_headers = match state.proxy.upstream_headers().await {
        Ok(h) => h,
        Err(_) => return upstream_credential_error(),
    };

    if !tok.try_acquire(cfg.proxy_max_concurrent) {
        return denied(&state, Some(&tok.job_id), ProxyDenial::TooManyConcurrent);
    }

    // The client's `anthropic-beta` opt-ins must survive the request rebuild,
    // merged with whatever the upstream credential requires — see
    // `merge_anthropic_beta`.
    let merged_beta = merge_anthropic_beta(&headers, &auth_headers);
    let mut request = state
        .proxy
        .http
        .post(format!("{}/v1/messages", cfg.anthropic_base_url))
        .header("anthropic-version", "2023-06-01")
        .header(header::CONTENT_TYPE, "application/json");
    for (name, value) in &auth_headers {
        if !name.eq_ignore_ascii_case("anthropic-beta") {
            request = request.header(*name, value.as_str());
        }
    }
    if let Some(beta) = &merged_beta {
        request = request.header("anthropic-beta", beta.as_str());
    }
    let upstream = request.body(body_bytes.to_vec()).send().await;
    tok.release();

    match upstream {
        Ok(resp) => {
            let status_u16 = resp.status().as_u16();
            let resp_headers = resp.headers().clone();
            // Feed the upstream status/headers to the rate-limit gate so a 429
            // pauses dispatch for subsequent builds.
            state.proxy.note_upstream_response(status_u16, &resp_headers);
            let status =
                StatusCode::from_u16(status_u16).unwrap_or(StatusCode::BAD_GATEWAY);
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::UNIX_EPOCH;

    #[test]
    fn api_key_headers_are_byte_identical() {
        // `api_key` mode must be byte-identical to the legacy proxy: exactly
        // one header named `x-api-key` carrying the raw key.
        assert_eq!(
            api_key_headers("sk-test-123"),
            vec![("x-api-key", "sk-test-123".to_string())]
        );
    }

    #[test]
    fn oauth_headers_have_bearer_and_beta() {
        assert_eq!(
            oauth_headers("tok-abc"),
            vec![
                ("authorization", "Bearer tok-abc".to_string()),
                ("anthropic-beta", "oauth-2025-04-20".to_string()),
            ]
        );
    }

    #[test]
    fn merge_anthropic_beta_combines_client_and_oauth_deduped() {
        let mut inbound = HeaderMap::new();
        inbound.insert(
            "anthropic-beta",
            "context-management-2025-06-27, oauth-2025-04-20"
                .parse()
                .unwrap(),
        );
        let merged = merge_anthropic_beta(&inbound, &oauth_headers("tok")).unwrap();
        assert!(merged.contains("context-management-2025-06-27"));
        assert_eq!(
            merged.matches("oauth-2025-04-20").count(),
            1,
            "the OAuth beta the client also sent must not be duplicated"
        );
    }

    #[test]
    fn merge_anthropic_beta_none_when_neither_side_sets_it() {
        assert!(merge_anthropic_beta(&HeaderMap::new(), &api_key_headers("k")).is_none());
    }

    #[test]
    fn needs_refresh_true_when_within_skew() {
        let now = SystemTime::now();
        assert!(needs_refresh(
            Some(now + Duration::from_secs(60)),
            now,
            Duration::from_secs(300)
        ));
    }

    #[test]
    fn needs_refresh_true_when_expired() {
        assert!(needs_refresh(
            Some(UNIX_EPOCH + Duration::from_secs(1)),
            SystemTime::now(),
            Duration::from_secs(300)
        ));
    }

    #[test]
    fn needs_refresh_false_when_fresh() {
        let now = SystemTime::now();
        assert!(!needs_refresh(
            Some(now + Duration::from_secs(86400)),
            now,
            Duration::from_secs(300)
        ));
    }

    #[test]
    fn needs_refresh_false_when_no_expiry() {
        assert!(!needs_refresh(
            None,
            SystemTime::now(),
            Duration::from_secs(300)
        ));
    }

    #[test]
    fn parse_refresh_response_reads_token_and_expiry() {
        let now = SystemTime::now();
        let snap =
            parse_refresh_response(br#"{"access_token":"new-tok","expires_in":3600}"#, now)
                .expect("valid refresh response parses");
        assert_eq!(snap.access_token, "new-tok");
        let exp = snap.expires_at.expect("expires_at present");
        assert!(exp > now);
    }

    #[test]
    fn parse_refresh_response_rejects_garbage() {
        assert!(parse_refresh_response(b"not json", SystemTime::now()).is_err());
        assert!(parse_refresh_response(br#"{"expires_in":10}"#, SystemTime::now()).is_err());
    }

    #[test]
    fn apply_refreshed_ok_updates_snapshot() {
        let state = OAuthTokenState::new(
            "old".into(),
            None,
            None,
            None,
            "http://unused".into(),
            reqwest::Client::new(),
        );
        let result = state.apply_refreshed(Ok(TokenSnapshot {
            access_token: "new".into(),
            expires_at: None,
        }));
        assert_eq!(result.unwrap(), "new");
        assert_eq!(
            state
                .snapshot
                .read()
                .expect("lock")
                .access_token,
            "new"
        );
    }

    #[test]
    fn apply_refreshed_err_keeps_snapshot() {
        let state = OAuthTokenState::new(
            "old".into(),
            None,
            None,
            None,
            "http://unused".into(),
            reqwest::Client::new(),
        );
        let result = state.apply_refreshed(Err(anyhow!("boom")));
        assert!(result.is_err());
        assert_eq!(
            state
                .snapshot
                .read()
                .expect("lock")
                .access_token,
            "old"
        );
    }

    #[tokio::test]
    async fn current_token_returns_existing_when_fresh() {
        let state = OAuthTokenState::new(
            "live-tok".into(),
            Some(SystemTime::now() + Duration::from_secs(86400)),
            None,
            None,
            "http://unused".into(),
            reqwest::Client::new(),
        );
        assert_eq!(state.current_token().await.unwrap(), "live-tok");
    }

    #[tokio::test]
    async fn current_token_refresh_failure_is_typed_error_not_panic() {
        // Expired token, no refresh token configured: `current_token` must
        // surface a typed `Err` (no network call, no panic).
        let state = OAuthTokenState::new(
            "stale".into(),
            Some(UNIX_EPOCH + Duration::from_secs(1)),
            None,
            None,
            "http://unused".into(),
            reqwest::Client::new(),
        );
        assert!(state.current_token().await.is_err());
    }
}

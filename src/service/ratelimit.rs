//! Rate-limit-aware dispatch gate.
//!
//! Tracks Anthropic `429` / `Retry-After` responses observed by the auth
//! proxy so new upstream calls can be paused while the account is over its
//! rate-limit headroom, rather than piling load onto an already-throttled
//! account. The gate is purely reactive: it arms only after an upstream `429`
//! is seen (see `KNOWN_GAPS` in the build claims).

use std::sync::RwLock;
use std::time::{Duration, Instant};

use axum::http::HeaderMap;

/// Fallback pause when Anthropic returns 429 with no parseable `retry-after`.
const DEFAULT_RETRY_AFTER_SECS: u64 = 60;

/// Tracks when upstream dispatch should pause due to Anthropic rate limiting.
pub struct RateLimitState {
    paused_until: RwLock<Option<Instant>>,
}

impl RateLimitState {
    /// A fresh gate with dispatch clear.
    pub fn new() -> RateLimitState {
        RateLimitState {
            paused_until: RwLock::new(None),
        }
    }

    /// Arm the dispatch gate when an upstream `429` is observed. A non-429
    /// status is ignored, leaving dispatch clear.
    pub fn record_response(&self, status: u16, headers: &HeaderMap) {
        if status != 429 {
            return;
        }
        let delay = parse_retry_after(headers)
            .unwrap_or(Duration::from_secs(DEFAULT_RETRY_AFTER_SECS));
        self.arm(delay);
    }

    /// Pause dispatch for `delay` from now.
    pub fn arm(&self, delay: Duration) {
        *self.paused_until.write().expect("rate-limit lock poisoned") =
            Some(Instant::now() + delay);
    }

    /// The remaining pause, or `None` when dispatch is clear.
    pub fn dispatch_delay(&self) -> Option<Duration> {
        let guard = self.paused_until.read().expect("rate-limit lock poisoned");
        let until = (*guard)?;
        let remaining = until.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            None
        } else {
            Some(remaining)
        }
    }
}

impl Default for RateLimitState {
    fn default() -> Self {
        Self::new()
    }
}

/// Parse a `Retry-After` header as integer seconds. Returns `None` for a
/// missing or unparseable header — including the RFC HTTP-date form, which
/// falls through to the caller's default.
fn parse_retry_after(headers: &HeaderMap) -> Option<Duration> {
    let raw = headers.get(axum::http::header::RETRY_AFTER)?.to_str().ok()?;
    let secs: u64 = raw.trim().parse().ok()?;
    Some(Duration::from_secs(secs))
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::{header, HeaderValue};

    fn hdrs(retry_after: &str) -> HeaderMap {
        let mut h = HeaderMap::new();
        h.insert(header::RETRY_AFTER, HeaderValue::from_str(retry_after).unwrap());
        h
    }

    #[test]
    fn parse_retry_after_reads_integer_seconds() {
        assert_eq!(
            parse_retry_after(&hdrs("45")),
            Some(Duration::from_secs(45))
        );
    }

    #[test]
    fn parse_retry_after_rejects_garbage_and_missing() {
        assert_eq!(parse_retry_after(&hdrs("soon")), None);
        assert_eq!(parse_retry_after(&HeaderMap::new()), None);
    }

    #[test]
    fn record_429_arms_the_gate() {
        let s = RateLimitState::new();
        s.record_response(429, &hdrs("30"));
        let d = s.dispatch_delay().expect("gate armed");
        assert!(d > Duration::from_secs(25) && d <= Duration::from_secs(30));
    }

    #[test]
    fn record_200_leaves_dispatch_clear() {
        let s = RateLimitState::new();
        s.record_response(200, &hdrs("30"));
        assert!(s.dispatch_delay().is_none());
    }

    #[test]
    fn record_429_without_header_uses_default() {
        let s = RateLimitState::new();
        s.record_response(429, &HeaderMap::new());
        let d = s.dispatch_delay().expect("gate armed");
        assert!(d > Duration::from_secs(55));
    }

    #[test]
    fn expired_pause_clears() {
        let s = RateLimitState::new();
        s.arm(Duration::ZERO);
        assert!(s.dispatch_delay().is_none());
    }
}

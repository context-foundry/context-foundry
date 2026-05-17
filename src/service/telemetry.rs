//! Structured service telemetry.
//!
//! An in-memory, bounded recorder of typed [`ServiceEvent`]s — backend
//! failures, auth-proxy limiter denials, rate-limit pauses, and job status
//! transitions. Every recorded event also emits a structured JSON line on
//! stderr so the events are observable in process logs. Telemetry is in-memory
//! only: it never writes Postgres and has no migration.

use std::sync::RwLock;

use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::json;

use crate::service::models::JobStatus;

/// The bounded ring keeps at most this many of the most recent events.
pub const TELEMETRY_RING_CAP: usize = 512;

/// The category of a recorded service event.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ServiceEventKind {
    /// A backend build step failed (every typed `failed` outcome).
    BackendFailure,
    /// An auth-proxy abuse damper rejected a request.
    LimiterDenial,
    /// Dispatch was paused after an upstream Anthropic 429.
    RateLimitPause,
    /// A job advanced (or attempted to advance) its lifecycle status.
    StatusTransition,
}

impl ServiceEventKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            ServiceEventKind::BackendFailure => "backend_failure",
            ServiceEventKind::LimiterDenial => "limiter_denial",
            ServiceEventKind::RateLimitPause => "rate_limit_pause",
            ServiceEventKind::StatusTransition => "status_transition",
        }
    }
}

/// A single structured telemetry event.
#[derive(Clone, Debug, Serialize)]
pub struct ServiceEvent {
    pub kind: ServiceEventKind,
    pub ts: DateTime<Utc>,
    pub job_id: Option<String>,
    pub code: String,
    pub message: String,
    /// `true` when the event reflects an expected, legal operation; `false`
    /// flags an illegal/abnormal occurrence (e.g. an illegal status edge).
    pub legal: bool,
}

/// An in-memory, bounded recorder of [`ServiceEvent`]s.
pub struct Telemetry {
    events: RwLock<Vec<ServiceEvent>>,
}

impl Telemetry {
    pub fn new() -> Telemetry {
        Telemetry {
            events: RwLock::new(Vec::new()),
        }
    }

    /// Emit a structured stderr line and append the event to the bounded ring,
    /// dropping the oldest events once the cap is exceeded.
    fn record(&self, ev: ServiceEvent) {
        eprintln!(
            "{}",
            json!({
                "telemetry": ev.kind.as_str(),
                "ts": ev.ts.to_rfc3339(),
                "job_id": ev.job_id,
                "code": ev.code,
                "message": ev.message,
                "legal": ev.legal,
            })
        );
        let mut events = self.events.write().expect("telemetry lock poisoned");
        events.push(ev);
        let len = events.len();
        if len > TELEMETRY_RING_CAP {
            events.drain(0..len - TELEMETRY_RING_CAP);
        }
    }

    /// Record a backend build-step failure.
    pub fn record_backend_failure(&self, job_id: &str, code: &str, message: &str) {
        self.record(ServiceEvent {
            kind: ServiceEventKind::BackendFailure,
            ts: Utc::now(),
            job_id: Some(job_id.to_string()),
            code: code.to_string(),
            message: message.to_string(),
            legal: true,
        });
    }

    /// Record an auth-proxy abuse-damper denial. `job_id` is `None` when the
    /// denied request carried no valid token.
    pub fn record_limiter_denial(&self, job_id: Option<&str>, reason: &str, message: &str) {
        self.record(ServiceEvent {
            kind: ServiceEventKind::LimiterDenial,
            ts: Utc::now(),
            job_id: job_id.map(|s| s.to_string()),
            code: reason.to_string(),
            message: message.to_string(),
            legal: true,
        });
    }

    /// Record a dispatch pause triggered by an upstream Anthropic 429.
    pub fn record_rate_limit_pause(&self, job_id: Option<&str>, delay_secs: u64) {
        self.record(ServiceEvent {
            kind: ServiceEventKind::RateLimitPause,
            ts: Utc::now(),
            job_id: job_id.map(|s| s.to_string()),
            code: "rate_limited".to_string(),
            message: format!("dispatch paused {delay_secs}s after upstream 429"),
            legal: true,
        });
    }

    /// Record a job status transition. `legal` reflects whether the edge is a
    /// permitted, monotonic transition per [`JobStatus::can_transition_to`].
    pub fn record_status_transition(&self, job_id: &str, from: JobStatus, to: JobStatus) {
        let legal = from.can_transition_to(to);
        let code = format!("{}->{}", from.as_str(), to.as_str());
        let message = if legal {
            "job status advanced".to_string()
        } else {
            "ILLEGAL status transition attempted".to_string()
        };
        self.record(ServiceEvent {
            kind: ServiceEventKind::StatusTransition,
            ts: Utc::now(),
            job_id: Some(job_id.to_string()),
            code,
            message,
            legal,
        });
    }

    /// A snapshot of every event currently in the ring (oldest first).
    pub fn recent(&self) -> Vec<ServiceEvent> {
        self.events
            .read()
            .expect("telemetry lock poisoned")
            .clone()
    }

    /// Every event of one kind, oldest first.
    pub fn events_of(&self, kind: ServiceEventKind) -> Vec<ServiceEvent> {
        self.events
            .read()
            .expect("telemetry lock poisoned")
            .iter()
            .filter(|e| e.kind == kind)
            .cloned()
            .collect()
    }

    /// How many events of one kind are in the ring.
    pub fn count(&self, kind: ServiceEventKind) -> usize {
        self.events_of(kind).len()
    }
}

impl Default for Telemetry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backend_failure_is_recorded_and_queryable() {
        let t = Telemetry::new();
        t.record_backend_failure("fj_1", "build_crashed", "boom");
        assert_eq!(t.count(ServiceEventKind::BackendFailure), 1);
        let evs = t.events_of(ServiceEventKind::BackendFailure);
        assert_eq!(evs[0].code, "build_crashed");
        assert_eq!(evs[0].job_id, Some("fj_1".to_string()));
    }

    #[test]
    fn limiter_denial_is_recorded() {
        let t = Telemetry::new();
        t.record_limiter_denial(None, "model_not_allowed", "denied");
        let evs = t.events_of(ServiceEventKind::LimiterDenial);
        assert_eq!(evs[0].code, "model_not_allowed");
        assert!(evs[0].job_id.is_none());
    }

    #[test]
    fn legal_status_transition_is_marked_legal() {
        let t = Telemetry::new();
        t.record_status_transition("fj_1", JobStatus::Building, JobStatus::Deploying);
        let evs = t.events_of(ServiceEventKind::StatusTransition);
        assert_eq!(evs.len(), 1);
        assert!(evs[0].legal);
        assert_eq!(evs[0].code, "building->deploying");
    }

    #[test]
    fn illegal_status_transition_is_marked_illegal() {
        let t = Telemetry::new();
        t.record_status_transition("fj_1", JobStatus::Ready, JobStatus::Building);
        let evs = t.events_of(ServiceEventKind::StatusTransition);
        assert!(!evs[0].legal);
    }

    #[test]
    fn ring_is_bounded_to_cap() {
        let t = Telemetry::new();
        for _ in 0..TELEMETRY_RING_CAP + 25 {
            t.record_backend_failure("fj", "c", "m");
        }
        assert_eq!(t.recent().len(), TELEMETRY_RING_CAP);
    }
}

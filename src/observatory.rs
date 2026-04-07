use std::io::Write;
use std::path::Path;

use chrono::Utc;
use serde::{Deserialize, Serialize};

use crate::agent::AgentOutputEvent;

/// Per-agent usage accumulator. Populated by the forwarding task as Usage
/// events stream through. Read by the caller after the agent completes.
#[derive(Debug, Clone, Default)]
pub struct AgentUsage {
    pub cost_usd: f64,
    pub tokens_in: u64,
    pub tokens_out: u64,
    pub context_pct: u8,
    pub cache_creation_tokens: u64,
    pub cache_read_tokens: u64,
}

/// Envelope written as a single JSON line to the events file.
/// Public + Deserialize so that `stats.rs` can read events back.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventEnvelope {
    pub timestamp: String,
    pub session_id: String,
    pub project_dir: String,
    pub event_type: String,
    pub payload: serde_json::Value,
}

/// All observatory event variants. Each serializes to a JSON payload.
#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum ObservatoryEvent {
    SessionStarted {
        config: serde_json::Value,
    },
    SessionEnded {
        total_tasks: usize,
        feat_count: usize,
        wip_count: usize,
        total_cost_usd: f64,
        duration_secs: f64,
    },
    TaskStarted {
        task_id: String,
        description: String,
        complexity: String,
    },
    AgentStarted {
        role: String,
        provider: String,
        model: String,
    },
    AgentDone {
        role: String,
        success: bool,
        duration_secs: f64,
        tokens_in: u64,
        tokens_out: u64,
        cost_usd: f64,
        context_pct: u8,
        #[serde(default)]
        cache_creation_tokens: u64,
        #[serde(default)]
        cache_read_tokens: u64,
    },
    ReviewFindings {
        task_id: String,
        high: usize,
        medium: usize,
        low: usize,
        findings_json: String,
    },
    PatternInjected {
        task_id: String,
        pattern_ids: Vec<String>,
        count: usize,
    },
    PatternApplied {
        task_id: String,
        pattern_ids: Vec<String>,
        count: usize,
    },
    PatternCited {
        task_id: String,
        role: String,
        artifact: String,
        pattern_id: String,
    },
    TaskCompleted {
        task_id: String,
        verdict: String,
        complexity: String,
        total_cost_usd: f64,
        total_duration_secs: f64,
        findings_high: usize,
        findings_medium: usize,
        findings_low: usize,
        phases_run: String,
        builder_provider: String,
        builder_model: String,
        reviewer_provider: String,
        reviewer_model: String,
        commit_sha: String,
    },
    Committed {
        task_id: String,
        sha: String,
        commit_type: String,
    },
    BudgetOverrun {
        task_id: String,
        phase: String,
        target_pct: u8,
        actual_pct: u8,
        recovery_action: String,
    },
    RateLimited {
        provider: String,
        wait_secs: u64,
    },
    DualPipelineStarted {
        session_id: String,
        models: Vec<String>,
    },
    DualPipelineCompleted {
        session_id: String,
        wall_clock_secs: f64,
        pipeline_0_success: bool,
        pipeline_1_success: bool,
    },
}

/// Create a unique session identifier for this build loop invocation.
pub fn generate_session_id() -> String {
    uuid::Uuid::new_v4().to_string()
}

/// Return a snake_case string for the event variant name.
pub fn event_type_str(event: &ObservatoryEvent) -> &'static str {
    match event {
        ObservatoryEvent::SessionStarted { .. } => "session_started",
        ObservatoryEvent::SessionEnded { .. } => "session_ended",
        ObservatoryEvent::TaskStarted { .. } => "task_started",
        ObservatoryEvent::AgentStarted { .. } => "agent_started",
        ObservatoryEvent::AgentDone { .. } => "agent_done",
        ObservatoryEvent::ReviewFindings { .. } => "review_findings",
        ObservatoryEvent::PatternInjected { .. } => "pattern_injected",
        ObservatoryEvent::PatternApplied { .. } => "pattern_applied",
        ObservatoryEvent::PatternCited { .. } => "pattern_cited",
        ObservatoryEvent::TaskCompleted { .. } => "task_completed",
        ObservatoryEvent::Committed { .. } => "committed",
        ObservatoryEvent::BudgetOverrun { .. } => "budget_overrun",
        ObservatoryEvent::RateLimited { .. } => "rate_limited",
        ObservatoryEvent::DualPipelineStarted { .. } => "dual_pipeline_started",
        ObservatoryEvent::DualPipelineCompleted { .. } => "dual_pipeline_completed",
    }
}

/// Append a single JSON line to the daily events file. Best-effort -- never panics or blocks.
pub fn log_event(session_id: &str, project_dir: &Path, event: ObservatoryEvent) {
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    let observatory_dir = std::path::PathBuf::from(home)
        .join(".foundry")
        .join("observatory");

    if let Err(e) = std::fs::create_dir_all(&observatory_dir) {
        eprintln!("observatory: failed to create directory: {}", e);
        return;
    }

    let date_str = Utc::now().format("%Y-%m-%d").to_string();
    let filename = format!("events-{}.jsonl", date_str);
    let path = observatory_dir.join(filename);

    let event_type = event_type_str(&event).to_string();
    let payload = serde_json::to_value(&event).unwrap_or(serde_json::Value::Null);

    let envelope = EventEnvelope {
        timestamp: Utc::now().to_rfc3339(),
        session_id: session_id.to_string(),
        project_dir: project_dir.display().to_string(),
        event_type,
        payload,
    };

    let json_line = match serde_json::to_string(&envelope) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("observatory: failed to serialize event: {}", e);
            return;
        }
    };

    let mut file = match std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
    {
        Ok(f) => f,
        Err(e) => {
            eprintln!("observatory: failed to open events file: {}", e);
            return;
        }
    };

    if let Err(e) = file.write_all(format!("{}\n", json_line).as_bytes()) {
        eprintln!("observatory: failed to write event: {}", e);
    }
}

impl AgentUsage {
    /// Extract cost/token data from a Usage event and add to running totals.
    pub fn accumulate(&mut self, event: &AgentOutputEvent) {
        if let AgentOutputEvent::Usage {
            cost_usd,
            input_tokens,
            output_tokens,
            context_window,
            cache_creation_tokens,
            cache_read_tokens,
        } = event
        {
            self.cost_usd += cost_usd;
            self.tokens_in += input_tokens;
            self.tokens_out += output_tokens;
            self.cache_creation_tokens += cache_creation_tokens;
            self.cache_read_tokens += cache_read_tokens;
            if *context_window > 0 {
                let total = input_tokens + output_tokens;
                self.context_pct =
                    ((total as f64 / *context_window as f64) * 100.0).min(100.0) as u8;
            }
        }
    }
}

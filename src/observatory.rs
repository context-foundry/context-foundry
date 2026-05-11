use std::io::Write;
use std::path::{Path, PathBuf};

use chrono::{NaiveDate, Utc};
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
        cc_version: String,
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
        cc_version: String,
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
    TaskClassified {
        task_id: String,
        complexity: String,
        override_flag: String,
        p_plus_cycles_budget: usize,
        bundling_score: usize,
        signals: serde_json::Value,
    },
    PlanReviewLoopCapped {
        task_id: String,
        cycles_used: usize,
        cycles_cap: usize,
        finding_count: usize,
        feedback_summary: String,
    },
    StageSummaryRequested {
        stage: String,
        cache_hit: bool,
        provider: String,
        model: String,
        latency_ms: u128,
        state: String,
        error: Option<String>,
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
        ObservatoryEvent::TaskClassified { .. } => "task_classified",
        ObservatoryEvent::PlanReviewLoopCapped { .. } => "plan_review_loop_capped",
        ObservatoryEvent::StageSummaryRequested { .. } => "stage_summary_requested",
        ObservatoryEvent::RateLimited { .. } => "rate_limited",
        ObservatoryEvent::DualPipelineStarted { .. } => "dual_pipeline_started",
        ObservatoryEvent::DualPipelineCompleted { .. } => "dual_pipeline_completed",
    }
}

/// Return `~/.foundry/observatory/` (best-effort: falls back to `./.foundry/observatory`
/// when `HOME` is unset).
pub fn observatory_dir_path() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".foundry").join("observatory")
}

/// Outcome of a single `run_retention_cleanup` invocation. Counts and any
/// best-effort errors are bubbled up so the caller can log them.
#[derive(Debug, Default, Clone)]
pub struct RetentionReport {
    pub db_archived: usize,
    pub jsonl_archived: usize,
    pub errors: Vec<String>,
}

/// Archive orphan SQLite files and stale daily JSONL files from the observatory
/// directory. Idempotent and best-effort: every failure is pushed into
/// `RetentionReport::errors` and the pass continues with the next file.
///
/// SQLite cleanup is narrow: only the legacy `observatory.db` family
/// (`observatory.db`, `observatory.db-wal`, `observatory.db-shm`,
/// `observatory.db-journal`) is archived. Other `*.db` files are left alone so
/// users may keep ad-hoc analysis files in this directory.
///
/// JSONL retention: files matching `events-YYYY-MM-DD.jsonl` whose date is
/// strictly older than `today_utc - retention_days` are archived. Today's
/// active file is never touched. `retention_days == 0` disables JSONL pruning
/// entirely (orphan SQLite cleanup still runs).
pub fn run_retention_cleanup(retention_days: usize) -> RetentionReport {
    let mut report = RetentionReport::default();
    let obs_dir = observatory_dir_path();
    if !obs_dir.exists() {
        return report;
    }

    let archived_dir = obs_dir.join(".archived");
    if let Err(e) = std::fs::create_dir_all(&archived_dir) {
        report
            .errors
            .push(format!("create {}: {}", archived_dir.display(), e));
        return report;
    }

    let today = Utc::now().date_naive();
    let jsonl_cutoff = if retention_days == 0 {
        None
    } else {
        Some(today - chrono::Duration::days(retention_days as i64))
    };

    let entries = match std::fs::read_dir(&obs_dir) {
        Ok(e) => e,
        Err(e) => {
            report
                .errors
                .push(format!("read_dir {}: {}", obs_dir.display(), e));
            return report;
        }
    };

    for entry in entries {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => continue,
        };

        let is_file = entry
            .file_type()
            .map(|t| t.is_file())
            .unwrap_or(false);
        if !is_file {
            continue;
        }

        let fname = entry.file_name().to_string_lossy().into_owned();

        if matches!(
            fname.as_str(),
            "observatory.db"
                | "observatory.db-wal"
                | "observatory.db-shm"
                | "observatory.db-journal"
        ) {
            if move_to_archive(&entry.path(), &archived_dir, &mut report) {
                report.db_archived += 1;
            }
            continue;
        }

        if fname.starts_with("events-") && fname.ends_with(".jsonl") {
            let date_part = &fname[7..fname.len() - 6];
            let file_date = match NaiveDate::parse_from_str(date_part, "%Y-%m-%d") {
                Ok(d) => d,
                Err(_) => continue,
            };
            if file_date == today {
                continue;
            }
            let cutoff = match jsonl_cutoff {
                Some(c) => c,
                None => continue,
            };
            if file_date < cutoff
                && move_to_archive(&entry.path(), &archived_dir, &mut report)
            {
                report.jsonl_archived += 1;
            }
        }
    }

    report
}

/// Move `src` into `archived_dir`. If the destination already exists (the
/// idempotent case), leave the source untouched. Returns `true` if the file
/// was moved successfully.
fn move_to_archive(src: &Path, archived_dir: &Path, report: &mut RetentionReport) -> bool {
    let file_name = match src.file_name() {
        Some(n) => n,
        None => return false,
    };
    let dest = archived_dir.join(file_name);
    if dest.exists() {
        return false;
    }
    match std::fs::rename(src, &dest) {
        Ok(()) => true,
        Err(e) => {
            report.errors.push(format!(
                "rename {} -> {}: {}",
                src.display(),
                dest.display(),
                e
            ));
            false
        }
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

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;
    use std::fs;

    #[test]
    fn event_type_str_includes_stage_summary_requested() {
        let ev = ObservatoryEvent::StageSummaryRequested {
            stage: "plan-review".into(),
            cache_hit: false,
            provider: "claude".into(),
            model: "haiku".into(),
            latency_ms: 1234,
            state: "running".into(),
            error: None,
        };
        assert_eq!(event_type_str(&ev), "stage_summary_requested");
    }

    /// Run `body` with `HOME` pointed at a fresh temp dir. Restores the prior
    /// HOME after the closure returns (or unsets it if it was unset before).
    fn with_temp_home<F: FnOnce(&Path)>(body: F) {
        let prev = std::env::var("HOME").ok();
        let tmp = tempfile::tempdir().expect("tempdir");
        std::env::set_var("HOME", tmp.path());
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            body(tmp.path());
        }));
        match prev {
            Some(v) => std::env::set_var("HOME", v),
            None => std::env::remove_var("HOME"),
        }
        if let Err(e) = result {
            std::panic::resume_unwind(e);
        }
    }

    fn obs_dir(home: &Path) -> PathBuf {
        home.join(".foundry").join("observatory")
    }

    #[test]
    #[serial]
    fn retention_cleanup_archives_orphan_db() {
        with_temp_home(|home| {
            let dir = obs_dir(home);
            fs::create_dir_all(&dir).unwrap();
            for name in ["observatory.db", "observatory.db-wal", "observatory.db-shm"] {
                fs::write(dir.join(name), b"x").unwrap();
            }
            let report = run_retention_cleanup(30);
            assert_eq!(report.db_archived, 3, "{:?}", report);
            assert_eq!(report.jsonl_archived, 0);
            assert!(report.errors.is_empty(), "{:?}", report.errors);
            for name in ["observatory.db", "observatory.db-wal", "observatory.db-shm"] {
                assert!(!dir.join(name).exists(), "src {} still present", name);
                assert!(
                    dir.join(".archived").join(name).exists(),
                    "{} missing in archived",
                    name
                );
            }
        });
    }

    #[test]
    #[serial]
    fn retention_cleanup_spares_today_and_recent_jsonl() {
        with_temp_home(|home| {
            let dir = obs_dir(home);
            fs::create_dir_all(&dir).unwrap();
            let today = Utc::now().date_naive();
            let recent = today - chrono::Duration::days(5);
            let stale = today - chrono::Duration::days(60);
            let today_name = format!("events-{}.jsonl", today.format("%Y-%m-%d"));
            let recent_name = format!("events-{}.jsonl", recent.format("%Y-%m-%d"));
            let stale_name = format!("events-{}.jsonl", stale.format("%Y-%m-%d"));
            fs::write(dir.join(&today_name), b"{}\n").unwrap();
            fs::write(dir.join(&recent_name), b"{}\n").unwrap();
            fs::write(dir.join(&stale_name), b"{}\n").unwrap();

            let report = run_retention_cleanup(30);
            assert_eq!(report.jsonl_archived, 1, "{:?}", report);
            assert_eq!(report.db_archived, 0);
            assert!(report.errors.is_empty(), "{:?}", report.errors);
            assert!(dir.join(&today_name).exists(), "today's file moved!");
            assert!(dir.join(&recent_name).exists(), "5-day-old file moved!");
            assert!(!dir.join(&stale_name).exists(), "stale file still in obs dir");
            assert!(
                dir.join(".archived").join(&stale_name).exists(),
                "stale file missing from archive"
            );
        });
    }

    #[test]
    #[serial]
    fn retention_cleanup_is_idempotent() {
        with_temp_home(|home| {
            let dir = obs_dir(home);
            fs::create_dir_all(&dir).unwrap();
            let stale = Utc::now().date_naive() - chrono::Duration::days(60);
            let stale_name = format!("events-{}.jsonl", stale.format("%Y-%m-%d"));
            fs::write(dir.join(&stale_name), b"{}\n").unwrap();

            let first = run_retention_cleanup(30);
            let second = run_retention_cleanup(30);
            assert_eq!(first.jsonl_archived, 1);
            assert_eq!(second.jsonl_archived, 0);
            assert!(first.errors.is_empty(), "{:?}", first.errors);
            assert!(second.errors.is_empty(), "{:?}", second.errors);
            assert!(
                dir.join(".archived").join(&stale_name).exists(),
                "archived file missing after second pass"
            );
        });
    }

    #[test]
    #[serial]
    fn retention_cleanup_disabled_skips_jsonl_but_archives_db() {
        with_temp_home(|home| {
            let dir = obs_dir(home);
            fs::create_dir_all(&dir).unwrap();
            let stale = Utc::now().date_naive() - chrono::Duration::days(365);
            let stale_name = format!("events-{}.jsonl", stale.format("%Y-%m-%d"));
            fs::write(dir.join(&stale_name), b"{}\n").unwrap();
            fs::write(dir.join("observatory.db"), b"x").unwrap();

            let report = run_retention_cleanup(0);
            assert_eq!(report.db_archived, 1, "{:?}", report);
            assert_eq!(report.jsonl_archived, 0, "{:?}", report);
            assert!(report.errors.is_empty(), "{:?}", report.errors);
            assert!(dir.join(&stale_name).exists(), "JSONL was archived despite retention=0");
            assert!(
                !dir.join("observatory.db").exists(),
                "orphan db not archived"
            );
        });
    }

    #[test]
    #[serial]
    fn retention_cleanup_leaves_user_db_files_untouched() {
        with_temp_home(|home| {
            let dir = obs_dir(home);
            fs::create_dir_all(&dir).unwrap();
            fs::write(dir.join("analytics.db"), b"x").unwrap();
            fs::write(dir.join("cache.db-wal"), b"x").unwrap();
            fs::write(dir.join("notes.txt"), b"x").unwrap();

            let report = run_retention_cleanup(30);
            assert_eq!(report.db_archived, 0, "{:?}", report);
            assert!(report.errors.is_empty(), "{:?}", report.errors);
            assert!(dir.join("analytics.db").exists(), "analytics.db archived");
            assert!(dir.join("cache.db-wal").exists(), "cache.db-wal archived");
            assert!(dir.join("notes.txt").exists(), "notes.txt archived");
        });
    }

    #[test]
    #[serial]
    fn retention_cleanup_no_obs_dir_is_noop() {
        with_temp_home(|home| {
            // obs dir never created
            let report = run_retention_cleanup(30);
            assert_eq!(report.db_archived, 0);
            assert_eq!(report.jsonl_archived, 0);
            assert!(report.errors.is_empty());
            assert!(!home.join(".foundry").join("observatory").exists());
        });
    }
}

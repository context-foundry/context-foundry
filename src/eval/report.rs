#![allow(dead_code)]

use crate::eval::run::RunTranscripts;
use crate::eval::scorer::{Scores, StageScore};
use crate::run_manifest::CompletionPath;
use crate::utils::atomic_write_file;
use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use serde::Serialize;
use std::path::{Path, PathBuf};

pub const EVAL_REPORT_SCHEMA_VERSION: u32 = 1;
pub const EVAL_REPORT_FILENAME: &str = "eval-report.json";

#[derive(Debug, Serialize)]
pub struct EvalReport<'a> {
    pub schema_version: u32,
    pub run_id: &'a str,
    pub task_id: &'a str,
    pub generated_at: DateTime<Utc>,
    pub completion_path: Option<CompletionPath>,
    pub aggregate_badge: &'a str,
    pub stages: &'a std::collections::BTreeMap<String, StageScore>,
    pub notes: Vec<String>,
}

pub fn build_notes(run: &RunTranscripts) -> Vec<String> {
    let mut notes = Vec::new();

    // Override reasons grouped by reason
    let mut override_groups: std::collections::BTreeMap<String, usize> =
        std::collections::BTreeMap::new();
    for (inv, _) in run.invocations.iter() {
        if let Some(reason) = inv.override_reason.as_deref() {
            *override_groups.entry(reason.to_string()).or_insert(0) += 1;
        }
    }
    for (reason, count) in override_groups {
        notes.push(format!("{} stage(s) ran under {} override", count, reason));
    }

    // Non-Claude provider count
    let non_claude_count = run
        .invocations
        .iter()
        .filter(|(inv, _)| {
            inv.actual_provider
                .as_deref()
                .map(|p| !p.is_empty() && p != "claude")
                .unwrap_or(false)
        })
        .count();
    if non_claude_count > 0 {
        notes.push(format!(
            "{} stage(s) used non-Claude provider; transcript-dependent checks Skip in v1",
            non_claude_count
        ));
    }

    // Fallback reasons
    let fallback_reasons: Vec<String> = run
        .invocations
        .iter()
        .filter_map(|(inv, _)| inv.fallback_reason.clone())
        .collect();
    if !fallback_reasons.is_empty() {
        notes.push(format!(
            "{} stage(s) fell back to Claude: {}",
            fallback_reasons.len(),
            fallback_reasons.join("; ")
        ));
    }

    if let Some(reason) = run.manifest.audit_skipped_reason.as_deref() {
        notes.push(format!("audit skipped: {}", reason));
    }

    notes
}

pub fn write_report(
    run: &RunTranscripts,
    scores: &Scores,
    buildloop_dir: &Path,
    generated_at: DateTime<Utc>,
) -> Result<PathBuf> {
    let notes = build_notes(run);
    let report = EvalReport {
        schema_version: EVAL_REPORT_SCHEMA_VERSION,
        run_id: &run.manifest.run_id,
        task_id: &run.manifest.task_id,
        generated_at,
        completion_path: run.manifest.completion_path,
        aggregate_badge: &scores.aggregate_badge,
        stages: &scores.stages,
        notes,
    };
    let bytes = serde_json::to_vec_pretty(&report).context("failed to serialize eval-report")?;
    std::fs::create_dir_all(buildloop_dir)
        .with_context(|| format!("failed to create {}", buildloop_dir.display()))?;
    let path = buildloop_dir.join(EVAL_REPORT_FILENAME);
    atomic_write_file(&path, &bytes)
        .with_context(|| format!("failed to write eval-report to {}", path.display()))?;
    Ok(path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent::AgentRole;
    use crate::eval::run::latest_run;
    use crate::eval::scorer::score_run;
    use crate::eval::stage_id::StageId;
    use crate::run_manifest::{
        AgentExitInfo, ManifestHandle, PromptEvidenceSpec, StageStatus,
    };
    use std::fs;
    use tempfile::TempDir;

    fn empty_spec<'a>(stage: StageId, role: AgentRole, system: &'a str, user: &'a str) -> PromptEvidenceSpec<'a> {
        PromptEvidenceSpec {
            stage_id: stage,
            role,
            expected_artifact_path: None,
            originally_configured_provider: String::new(),
            originally_configured_model: String::new(),
            effective_provider: String::new(),
            effective_model: String::new(),
            override_reason: None,
            system_prompt: system,
            user_prompt: user,
            matched_pattern_ids: Vec::new(),
            selected_extension_names: Vec::new(),
            prior_artifact_paths: Vec::new(),
        }
    }

    fn run_with_one_invocation(bl: &Path) -> RunTranscripts {
        let h = ManifestHandle::new(bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        latest_run(bl).unwrap()
    }

    #[test]
    fn write_report_creates_eval_report_json() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        let r = run_with_one_invocation(&bl);
        let scores = score_run(&r);
        let path = write_report(&r, &scores, &bl, Utc::now()).unwrap();
        assert!(path.exists());
        let bytes = fs::read(&path).unwrap();
        let v: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(v.get("schema_version").and_then(|x| x.as_u64()), Some(1));
        let badge = v.get("aggregate_badge").and_then(|x| x.as_str()).unwrap();
        assert!(badge.starts_with("EVAL "));
        assert!(v.get("stages").map(|s| s.is_object()).unwrap_or(false));
    }

    #[test]
    fn write_report_idempotent_modulo_generated_at() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        let r = run_with_one_invocation(&bl);
        let scores = score_run(&r);
        let when = Utc::now();
        let path = write_report(&r, &scores, &bl, when).unwrap();
        let first = fs::read(&path).unwrap();
        let _ = write_report(&r, &scores, &bl, when).unwrap();
        let second = fs::read(&path).unwrap();
        assert_eq!(first, second);

        let later = when + chrono::Duration::seconds(60);
        let _ = write_report(&r, &scores, &bl, later).unwrap();
        let third = fs::read(&path).unwrap();
        assert_ne!(first, third);
        // Diff should be in generated_at field only
        let v1: serde_json::Value = serde_json::from_slice(&first).unwrap();
        let v3: serde_json::Value = serde_json::from_slice(&third).unwrap();
        assert_ne!(v1.get("generated_at"), v3.get("generated_at"));
        let mut v1_clean = v1.clone();
        let mut v3_clean = v3.clone();
        v1_clean.as_object_mut().unwrap().remove("generated_at");
        v3_clean.as_object_mut().unwrap().remove("generated_at");
        assert_eq!(v1_clean, v3_clean);
    }

    #[test]
    fn build_notes_records_override_reason() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user");
        spec.override_reason = Some("budget_recovery".to_string());
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let notes = build_notes(&r);
        assert!(notes.iter().any(|n| n.contains("budget_recovery")));
    }

    #[test]
    fn build_notes_records_non_claude_provider() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(
            id,
            StageStatus::Ran,
            Utc::now(),
            AgentExitInfo {
                log_path: None,
                actual_provider: "codex".to_string(),
                actual_model: String::new(),
                fallback_reason: None,
            },
        );
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let notes = build_notes(&r);
        assert!(notes.iter().any(|n| n.contains("non-Claude provider")));
    }

    #[test]
    fn build_notes_records_fallback_reason() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(
            id,
            StageStatus::Ran,
            Utc::now(),
            AgentExitInfo {
                log_path: None,
                actual_provider: "claude".to_string(),
                actual_model: String::new(),
                fallback_reason: Some("codex transport stall".to_string()),
            },
        );
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let notes = build_notes(&r);
        assert!(notes.iter().any(|n| n.contains("codex transport stall")));
    }
}

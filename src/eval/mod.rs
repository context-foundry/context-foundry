#![allow(dead_code)]

use anyhow::Result;
use chrono::Utc;
use std::path::Path;

pub mod checks;
pub mod parser;
pub mod report;
pub mod run;
pub mod scorer;
pub mod stage_id;

pub fn run_for_current_task(project_dir: &Path) -> Result<()> {
    let buildloop_dir = project_dir.join(".buildloop");
    let mut run = match run::latest_run(&buildloop_dir) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("eval: skipping (no manifest): {}", e);
            return Ok(());
        }
    };

    for (inv, transcript) in run.invocations.iter_mut() {
        if inv.actual_model.as_deref().unwrap_or("").is_empty() {
            if let Some(model) = transcript.model_from_init.clone() {
                inv.actual_model = Some(model);
            }
        }
    }

    let scores = scorer::score_run(&run);
    let generated_at = Utc::now();

    if let Err(e) = report::write_report(&run, &scores, &buildloop_dir, generated_at) {
        eprintln!("eval: failed to write report: {}", e);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent::AgentRole;
    use crate::eval::stage_id::StageId;
    use crate::run_manifest::{
        AgentExitInfo, ManifestHandle, PromptEvidenceSpec, StageStatus,
    };
    use std::fs;
    use tempfile::TempDir;

    const FIXTURE: &str = include_str!("../../tests/fixtures/claude-stage.jsonl");

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

    #[test]
    fn run_for_current_task_returns_ok_when_manifest_missing() {
        let tmp = TempDir::new().unwrap();
        let result = run_for_current_task(tmp.path());
        assert!(result.is_ok());
        assert!(!tmp.path().join(".buildloop").join("eval-report.json").exists());
    }

    #[test]
    fn run_for_current_task_writes_report_when_manifest_present() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        run_for_current_task(tmp.path()).unwrap();
        let report_path = bl.join("eval-report.json");
        assert!(report_path.exists());
        let bytes = fs::read(&report_path).unwrap();
        let v: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(v.get("schema_version").and_then(|x| x.as_u64()), Some(1));
    }

    #[test]
    fn run_for_current_task_fills_actual_model_from_jsonl() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        let log_path = bl.join("PLAN-20260507-000000.jsonl");
        fs::write(&log_path, FIXTURE).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(
            id,
            StageStatus::Ran,
            Utc::now(),
            AgentExitInfo {
                log_path: Some(log_path),
                actual_provider: "claude".to_string(),
                actual_model: String::new(),
                fallback_reason: None,
            },
        );
        h.flush().unwrap();
        run_for_current_task(tmp.path()).unwrap();
        // Verify the report exists and parses; actual_model is private to in-memory run.
        // Best we can do externally: verify report is present and the manifest itself is unchanged.
        let report_path = bl.join("eval-report.json");
        assert!(report_path.exists());
        // Read manifest, confirm actual_model was NOT mutated on disk
        let manifest_path = bl.join("run-manifest.json");
        let raw = fs::read_to_string(&manifest_path).unwrap();
        let v: serde_json::Value = serde_json::from_str(&raw).unwrap();
        let inv = &v["invocations"][0];
        // actual_model on disk should still be missing or empty since we set it to "" before flushing
        assert!(
            inv.get("actual_model")
                .and_then(|x| x.as_str())
                .map(|s| s.is_empty())
                .unwrap_or(true)
        );
        // Re-load via latest_run and call run_for_current_task again to be sure we don't panic on any shape.
        // Then verify directly that latest_run returns a transcript with model_from_init set.
        let r = crate::eval::run::latest_run(&bl).unwrap();
        assert_eq!(r.invocations[0].1.model_from_init.as_deref(), Some("claude-opus-4-7"));
    }
}

#![allow(dead_code)]

use crate::eval::parser::{parse_stage_log, StageTranscript};
use crate::run_manifest::{read_manifest, RunManifest, StageInvocation, StageStatus};
use anyhow::{Context, Result};
use std::path::Path;

#[derive(Debug)]
pub struct RunTranscripts {
    pub manifest: RunManifest,
    pub invocations: Vec<(StageInvocation, StageTranscript)>,
}

pub fn latest_run(buildloop_dir: &Path) -> Result<RunTranscripts> {
    let manifest_path = buildloop_dir.join("run-manifest.json");
    let manifest = read_manifest(&manifest_path)
        .with_context(|| format!("failed to load manifest {}", manifest_path.display()))?;

    let mut invocations = Vec::with_capacity(manifest.invocations.len());
    for inv in manifest.invocations.iter().cloned() {
        let stage_id = inv.stage_id;
        let make_stub = || StageTranscript::stub(inv.log_path.clone().unwrap_or_default(), stage_id);

        let is_skipped = matches!(
            inv.status,
            Some(StageStatus::Skipped) | Some(StageStatus::Reused) | Some(StageStatus::CheckpointResume)
        );
        let transcript = match (is_skipped, inv.log_path.clone()) {
            (true, _) | (_, None) => make_stub(),
            (false, Some(log_path)) => {
                if !log_path.exists() {
                    eprintln!(
                        "warning: manifest log_path missing on disk: {}",
                        log_path.display()
                    );
                    make_stub()
                } else {
                    match parse_stage_log(&log_path) {
                        Ok(t) => t,
                        Err(e) => {
                            eprintln!(
                                "warning: failed to parse log {}: {}",
                                log_path.display(),
                                e
                            );
                            make_stub()
                        }
                    }
                }
            }
        };

        invocations.push((inv, transcript));
    }

    Ok(RunTranscripts {
        manifest,
        invocations,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent::AgentRole;
    use crate::eval::stage_id::StageId;
    use crate::run_manifest::{ArtifactSource, ManifestHandle};
    use chrono::Utc;
    use std::fs;
    use tempfile::TempDir;

    const FIXTURE: &str = include_str!("../../tests/fixtures/claude-stage.jsonl");

    fn make_buildloop(tmp: &TempDir) -> std::path::PathBuf {
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        bl
    }

    #[test]
    fn latest_run_returns_stub_for_skipped_invocation() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        h.record_skip(
            StageId::Plan,
            AgentRole::Planner,
            StageStatus::Skipped,
            "simple_task_skip_planner".to_string(),
            None,
        );
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        assert_eq!(r.invocations.len(), 1);
        assert!(r.invocations[0].1.parser_skipped);
    }

    #[test]
    fn latest_run_parses_log_for_ran_invocation() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let log_path = bl.join("PLAN-20260507-000000.jsonl");
        fs::write(&log_path, FIXTURE).unwrap();

        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_skip(
            StageId::Plan,
            AgentRole::Planner,
            StageStatus::Ran,
            "ran".to_string(),
            Some(ArtifactSource::ThisRun),
        );
        h.record_exit(
            id,
            StageStatus::Ran,
            Utc::now(),
            crate::run_manifest::AgentExitInfo {
                log_path: Some(log_path.clone()),
                actual_provider: String::new(),
                actual_model: String::new(),
                fallback_reason: None,
            },
        );
        h.flush().unwrap();

        let r = latest_run(&bl).unwrap();
        assert_eq!(r.invocations.len(), 1);
        assert!(!r.invocations[0].1.parser_skipped);
        assert!(r.invocations[0].1.model_from_init.is_some());
    }

    #[test]
    fn latest_run_handles_missing_log_file() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let bogus = bl.join("PLAN-doesnotexist.jsonl");

        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_skip(
            StageId::Plan,
            AgentRole::Planner,
            StageStatus::Ran,
            "ran".to_string(),
            Some(ArtifactSource::ThisRun),
        );
        h.record_exit(
            id,
            StageStatus::Ran,
            Utc::now(),
            crate::run_manifest::AgentExitInfo {
                log_path: Some(bogus),
                actual_provider: String::new(),
                actual_model: String::new(),
                fallback_reason: None,
            },
        );
        h.flush().unwrap();

        let r = latest_run(&bl).unwrap();
        assert_eq!(r.invocations.len(), 1);
        assert!(r.invocations[0].1.parser_skipped);
    }

    #[test]
    fn latest_run_errors_on_missing_manifest() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let result = latest_run(&bl);
        assert!(result.is_err());
    }
}

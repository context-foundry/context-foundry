#![allow(dead_code)]

use crate::eval::checks::{
    invocation_skip_status, non_superseded, skip_evidence_for_status, Category, Check, Severity,
    StageCheckResult, Status,
};
use crate::eval::run::RunTranscripts;
use crate::eval::stage_id::{prior_artifact, StageId};
use crate::run_manifest::StageStatus;

const ALL_STAGES: &[StageId] = &[
    StageId::Query,
    StageId::Research,
    StageId::Plan,
    StageId::Build,
    StageId::Audit,
];
const ARTIFACT_MIN_BYTES: u64 = 200;

pub struct StageCompletedSuccessfully;
pub struct SystemPromptPresent;
pub struct ModelMatchesConfig;
pub struct ExtensionLoaded;
pub struct PatternsInjected;
pub struct PriorArtifactReceived;
pub struct PriorArtifactRead;
pub struct ExpectedArtifactWritten;

impl Check for StageCompletedSuccessfully {
    fn name(&self) -> &'static str {
        "stage_completed_successfully"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Critical
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, _) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            let (status, evidence) = match inv.status {
                Some(StageStatus::Ran) => (Status::Pass, "status=ran".to_string()),
                Some(StageStatus::Failed) => (Status::Fail, "status=failed".to_string()),
                Some(StageStatus::Skipped)
                | Some(StageStatus::Reused)
                | Some(StageStatus::CheckpointResume) => (
                    Status::Skip,
                    skip_evidence_for_status(inv.status, &inv.skip_reason),
                ),
                None => (Status::Skip, "status=unknown".to_string()),
            };
            out.push(StageCheckResult {
                stage,
                invocation_id: inv.invocation_id,
                status,
                evidence,
            });
        }
        out
    }
}

impl Check for SystemPromptPresent {
    fn name(&self) -> &'static str {
        "system_prompt_present"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Critical
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, _) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            if invocation_skip_status(inv).is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: skip_evidence_for_status(inv.status, &inv.skip_reason),
                });
                continue;
            }
            let n = inv.system_prompt_bytes.unwrap_or(0);
            if n > 0 {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Pass,
                    evidence: format!("system_prompt_bytes={}", n),
                });
            } else {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Fail,
                    evidence: "system_prompt_bytes=0 (blake3-empty trap: hash alone is non-empty for an empty prompt)".to_string(),
                });
            }
        }
        out
    }
}

impl Check for ModelMatchesConfig {
    fn name(&self) -> &'static str {
        "model_matches_config"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Standard
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, _) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            if invocation_skip_status(inv).is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: skip_evidence_for_status(inv.status, &inv.skip_reason),
                });
                continue;
            }
            if inv.override_reason.is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: format!(
                        "override_reason={}",
                        inv.override_reason.as_deref().unwrap_or("")
                    ),
                });
                continue;
            }
            let oc_p = inv.originally_configured_provider.as_deref().unwrap_or("");
            let oc_m = inv.originally_configured_model.as_deref().unwrap_or("");
            let ef_p = inv.effective_provider.as_deref().unwrap_or("");
            let ef_m = inv.effective_model.as_deref().unwrap_or("");
            if oc_p == ef_p && oc_m == ef_m {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Pass,
                    evidence: format!("provider={} model={}", ef_p, ef_m),
                });
            } else {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Fail,
                    evidence: format!(
                        "configured={}/{} effective={}/{}",
                        oc_p, oc_m, ef_p, ef_m
                    ),
                });
            }
        }
        out
    }
}

impl Check for ExtensionLoaded {
    fn name(&self) -> &'static str {
        "extension_loaded"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Standard
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, _) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            if invocation_skip_status(inv).is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: skip_evidence_for_status(inv.status, &inv.skip_reason),
                });
                continue;
            }
            if inv.selected_extension_names.is_empty() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: "no extensions selected".to_string(),
                });
                continue;
            }
            let missing: Vec<String> = inv
                .selected_extension_names
                .iter()
                .filter(|n| !inv.prompt_extension_names_found.contains(n))
                .cloned()
                .collect();
            if missing.is_empty() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Pass,
                    evidence: format!("found={:?}", inv.prompt_extension_names_found),
                });
            } else {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Fail,
                    evidence: format!("missing={:?}", missing),
                });
            }
        }
        out
    }
}

impl Check for PatternsInjected {
    fn name(&self) -> &'static str {
        "patterns_injected"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Standard
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, _) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            if invocation_skip_status(inv).is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: skip_evidence_for_status(inv.status, &inv.skip_reason),
                });
                continue;
            }
            if inv.matched_pattern_ids.is_empty() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: "no patterns matched".to_string(),
                });
                continue;
            }
            let missing: Vec<String> = inv
                .matched_pattern_ids
                .iter()
                .filter(|n| !inv.prompt_pattern_ids_found.contains(n))
                .cloned()
                .collect();
            if missing.is_empty() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Pass,
                    evidence: format!("found={:?}", inv.prompt_pattern_ids_found),
                });
            } else {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Fail,
                    evidence: format!("missing={:?}", missing),
                });
            }
        }
        out
    }
}

impl Check for PriorArtifactReceived {
    fn name(&self) -> &'static str {
        "prior_artifact_received"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Critical
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, _) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            if invocation_skip_status(inv).is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: skip_evidence_for_status(inv.status, &inv.skip_reason),
                });
                continue;
            }
            let canonical = match prior_artifact(stage) {
                Some(p) => p,
                None => {
                    out.push(StageCheckResult {
                        stage,
                        invocation_id: inv.invocation_id,
                        status: Status::Skip,
                        evidence: "no prior artifact for stage".to_string(),
                    });
                    continue;
                }
            };
            let basename = std::path::Path::new(canonical)
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("");
            if inv.prompt_artifact_refs_found.iter().any(|s| s == basename) {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Pass,
                    evidence: format!("found={}", basename),
                });
            } else {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Fail,
                    evidence: format!(
                        "missing={} found={:?}",
                        basename, inv.prompt_artifact_refs_found
                    ),
                });
            }
        }
        out
    }
}

impl Check for PriorArtifactRead {
    fn name(&self) -> &'static str {
        "prior_artifact_read"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Standard
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, transcript) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            if invocation_skip_status(inv).is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: skip_evidence_for_status(inv.status, &inv.skip_reason),
                });
                continue;
            }
            let provider = inv.actual_provider.as_deref().unwrap_or("");
            if provider != "claude" || transcript.parser_skipped {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: "non-Claude provider, transcript adapter not in v1".to_string(),
                });
                continue;
            }
            let canonical = match prior_artifact(stage) {
                Some(p) => p,
                None => {
                    out.push(StageCheckResult {
                        stage,
                        invocation_id: inv.invocation_id,
                        status: Status::Skip,
                        evidence: "no prior artifact for stage".to_string(),
                    });
                    continue;
                }
            };
            let basename = std::path::Path::new(canonical)
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("");
            let matched = transcript.tool_uses.iter().any(|tu| {
                tu.name == "Read"
                    && tu
                        .input
                        .get("file_path")
                        .and_then(|v| v.as_str())
                        .map(|s| s.ends_with(basename))
                        .unwrap_or(false)
            });
            if matched {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Pass,
                    evidence: format!("read tool_use found for {}", basename),
                });
            } else {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Fail,
                    evidence: format!(
                        "no Read tool_use for {} in {} tool_uses",
                        basename,
                        transcript.tool_uses.len()
                    ),
                });
            }
        }
        out
    }
}

impl Check for ExpectedArtifactWritten {
    fn name(&self) -> &'static str {
        "expected_artifact_written"
    }
    fn category(&self) -> Category {
        Category::Plumbing
    }
    fn severity(&self) -> Severity {
        Severity::Standard
    }
    fn applies_to(&self) -> &[StageId] {
        ALL_STAGES
    }
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult> {
        let mut out = Vec::new();
        for (inv, _) in run
            .invocations
            .iter()
            .filter(|(inv, _)| non_superseded(inv) && inv.stage_id.is_some())
        {
            let stage = match inv.stage_id {
                Some(s) => s,
                None => continue,
            };
            if invocation_skip_status(inv).is_some() {
                out.push(StageCheckResult {
                    stage,
                    invocation_id: inv.invocation_id,
                    status: Status::Skip,
                    evidence: skip_evidence_for_status(inv.status, &inv.skip_reason),
                });
                continue;
            }
            let path = match &inv.expected_artifact_path {
                Some(p) => p,
                None => {
                    out.push(StageCheckResult {
                        stage,
                        invocation_id: inv.invocation_id,
                        status: Status::Skip,
                        evidence: "no expected_artifact_path on invocation".to_string(),
                    });
                    continue;
                }
            };
            match std::fs::metadata(path) {
                Err(_) => {
                    out.push(StageCheckResult {
                        stage,
                        invocation_id: inv.invocation_id,
                        status: Status::Fail,
                        evidence: format!("artifact missing on disk: {}", path.display()),
                    });
                }
                Ok(m) => {
                    if m.len() > ARTIFACT_MIN_BYTES {
                        out.push(StageCheckResult {
                            stage,
                            invocation_id: inv.invocation_id,
                            status: Status::Pass,
                            evidence: format!("{} bytes={}", path.display(), m.len()),
                        });
                    } else {
                        out.push(StageCheckResult {
                            stage,
                            invocation_id: inv.invocation_id,
                            status: Status::Fail,
                            evidence: format!(
                                "artifact too small: {} bytes={}",
                                path.display(),
                                m.len()
                            ),
                        });
                    }
                }
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent::AgentRole;
    use crate::eval::run::{latest_run, RunTranscripts};
    use crate::run_manifest::{
        AgentExitInfo, ArtifactSource, ManifestHandle, PromptEvidenceSpec, StageStatus,
    };
    use chrono::Utc;
    use std::fs;
    use std::path::{Path, PathBuf};
    use tempfile::TempDir;

    const FIXTURE: &str = include_str!("../../../tests/fixtures/claude-stage.jsonl");

    fn make_buildloop(tmp: &TempDir) -> PathBuf {
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
        bl
    }

    fn empty_spec<'a>(
        stage: StageId,
        role: AgentRole,
        system: &'a str,
        user: &'a str,
    ) -> PromptEvidenceSpec<'a> {
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

    fn run_check(check: impl Check, run: &RunTranscripts) -> Vec<StageCheckResult> {
        check.run(run)
    }

    #[test]
    fn stage_completed_successfully_passes_on_ran() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(
            id,
            StageStatus::Ran,
            Utc::now(),
            AgentExitInfo::default(),
        );
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(StageCompletedSuccessfully, &r);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].status, Status::Pass);
        assert_eq!(results[0].evidence, "status=ran");
    }

    #[test]
    fn stage_completed_successfully_fails_on_failed() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(
            id,
            StageStatus::Failed,
            Utc::now(),
            AgentExitInfo::default(),
        );
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(StageCompletedSuccessfully, &r);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].status, Status::Fail);
    }

    #[test]
    fn stage_completed_successfully_skips_on_skipped() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        h.record_skip(
            StageId::Plan,
            AgentRole::Planner,
            StageStatus::Skipped,
            "skip".to_string(),
            None,
        );
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(StageCompletedSuccessfully, &r);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].status, Status::Skip);
    }

    #[test]
    fn system_prompt_present_fails_on_zero_bytes() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "", "user"));
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(SystemPromptPresent, &r);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].status, Status::Fail);
    }

    #[test]
    fn system_prompt_present_passes_on_nonzero() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "abc", "user"));
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(SystemPromptPresent, &r);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].status, Status::Pass);
    }

    #[test]
    fn model_matches_config_passes_when_equal_no_override() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let spec = PromptEvidenceSpec {
            stage_id: StageId::Plan,
            role: AgentRole::Planner,
            expected_artifact_path: None,
            originally_configured_provider: "claude".to_string(),
            originally_configured_model: "opus".to_string(),
            effective_provider: "claude".to_string(),
            effective_model: "opus".to_string(),
            override_reason: None,
            system_prompt: "sys",
            user_prompt: "user",
            matched_pattern_ids: Vec::new(),
            selected_extension_names: Vec::new(),
            prior_artifact_paths: Vec::new(),
        };
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ModelMatchesConfig, &r);
        assert_eq!(results[0].status, Status::Pass);
    }

    #[test]
    fn model_matches_config_skips_on_override_reason() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let spec = PromptEvidenceSpec {
            stage_id: StageId::Plan,
            role: AgentRole::Planner,
            expected_artifact_path: None,
            originally_configured_provider: "claude".to_string(),
            originally_configured_model: "opus".to_string(),
            effective_provider: "claude".to_string(),
            effective_model: "haiku".to_string(),
            override_reason: Some("budget_recovery".to_string()),
            system_prompt: "sys",
            user_prompt: "user",
            matched_pattern_ids: Vec::new(),
            selected_extension_names: Vec::new(),
            prior_artifact_paths: Vec::new(),
        };
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ModelMatchesConfig, &r);
        assert_eq!(results[0].status, Status::Skip);
        assert!(results[0].evidence.contains("budget_recovery"));
    }

    #[test]
    fn model_matches_config_fails_on_drift() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let spec = PromptEvidenceSpec {
            stage_id: StageId::Plan,
            role: AgentRole::Planner,
            expected_artifact_path: None,
            originally_configured_provider: "claude".to_string(),
            originally_configured_model: "opus".to_string(),
            effective_provider: "codex".to_string(),
            effective_model: "gpt5".to_string(),
            override_reason: None,
            system_prompt: "sys",
            user_prompt: "user",
            matched_pattern_ids: Vec::new(),
            selected_extension_names: Vec::new(),
            prior_artifact_paths: Vec::new(),
        };
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ModelMatchesConfig, &r);
        assert_eq!(results[0].status, Status::Fail);
    }

    #[test]
    fn extension_loaded_skips_when_none_selected() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user"));
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ExtensionLoaded, &r);
        assert_eq!(results[0].status, Status::Skip);
    }

    #[test]
    fn extension_loaded_passes_with_marker() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let user = "before --- BEGIN EXTENSION CONTEXT: recon --- after";
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", user);
        spec.selected_extension_names = vec!["recon".to_string()];
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ExtensionLoaded, &r);
        assert_eq!(results[0].status, Status::Pass);
    }

    #[test]
    fn extension_loaded_fails_when_marker_missing() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let user = "user prompt without marker";
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", user);
        spec.selected_extension_names = vec!["recon".to_string()];
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ExtensionLoaded, &r);
        assert_eq!(results[0].status, Status::Fail);
    }

    #[test]
    fn patterns_injected_passes_only_with_brackets() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let user = "text [pat-a] more";
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", user);
        spec.matched_pattern_ids = vec!["pat-a".to_string(), "pat-b".to_string()];
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(PatternsInjected, &r);
        assert_eq!(results[0].status, Status::Fail);
        assert!(results[0].evidence.contains("pat-b"));

        // Now both present
        let tmp2 = TempDir::new().unwrap();
        let bl2 = make_buildloop(&tmp2);
        let h2 = ManifestHandle::new(&bl2, "T1.1", Utc::now());
        let user2 = "text [pat-a] [pat-b] tail";
        let mut spec2 = empty_spec(StageId::Plan, AgentRole::Planner, "sys", user2);
        spec2.matched_pattern_ids = vec!["pat-a".to_string(), "pat-b".to_string()];
        let id2 = h2.record_invocation(spec2);
        h2.record_exit(id2, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h2.flush().unwrap();
        let r2 = latest_run(&bl2).unwrap();
        let results2 = run_check(PatternsInjected, &r2);
        assert_eq!(results2[0].status, Status::Pass);
    }

    #[test]
    fn patterns_injected_does_not_false_positive_on_bare_word() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let user = "the simple thing";
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", user);
        spec.matched_pattern_ids = vec!["simple".to_string()];
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(PatternsInjected, &r);
        assert_eq!(results[0].status, Status::Fail);
    }

    #[test]
    fn prior_artifact_received_passes_when_basename_present() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let user = "see research-report.md please";
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", user);
        spec.prior_artifact_paths = vec![PathBuf::from(".buildloop/research-report.md")];
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(PriorArtifactReceived, &r);
        assert_eq!(results[0].status, Status::Pass);
    }

    #[test]
    fn prior_artifact_received_skips_for_query() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let id = h.record_invocation(empty_spec(StageId::Query, AgentRole::Query, "sys", "user"));
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(PriorArtifactReceived, &r);
        assert_eq!(results[0].status, Status::Skip);
        assert_eq!(results[0].evidence, "no prior artifact for stage");
    }

    #[test]
    fn prior_artifact_read_skips_for_non_claude() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
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
        let results = run_check(PriorArtifactRead, &r);
        assert_eq!(results[0].status, Status::Skip);
        assert!(results[0].evidence.contains("non-Claude"));
    }

    #[test]
    fn prior_artifact_read_passes_on_subagent_read() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let log_path = bl.join("PLAN-20260507-000000.jsonl");
        fs::write(&log_path, FIXTURE).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        // Build invocation with prior artifact .buildloop/current-plan.md
        let mut spec = empty_spec(StageId::Build, AgentRole::Builder, "sys", "user");
        spec.expected_artifact_path = None;
        spec.prior_artifact_paths = vec![PathBuf::from(".buildloop/current-plan.md")];
        let id = h.record_invocation(spec);
        // Need to use a log_path with a Build prefix (IMPLEMENT or BUILDER)
        // The fixture doesn't matter -- but we need parser to produce tool_uses.
        // The fixture file name needs to be matched by stage_id_from_log_path. We named it PLAN- which maps to Plan,
        // but that affects parsed stage_id of transcript only, not whether parser_skipped.
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
        let r = latest_run(&bl).unwrap();
        let results = run_check(PriorArtifactRead, &r);
        assert_eq!(results[0].status, Status::Pass);
    }

    #[test]
    fn prior_artifact_read_fails_when_basename_missing() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        // Write a Claude JSONL fixture with no matching Read
        let log_path = bl.join("PLAN-20260507-000001.jsonl");
        let body = r#"{"type":"system","subtype":"init","session_id":"s1","model":"claude","tools":["Read"]}
{"type":"assistant","message":{"id":"m1","role":"assistant","content":[{"type":"tool_use","id":"tu1","name":"Read","input":{"file_path":"/abs/some/other.md"}}]}}
{"type":"result","subtype":"success","session_id":"s1"}
"#;
        fs::write(&log_path, body).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user");
        spec.prior_artifact_paths = vec![PathBuf::from(".buildloop/research-report.md")];
        let id = h.record_invocation(spec);
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
        let r = latest_run(&bl).unwrap();
        let results = run_check(PriorArtifactRead, &r);
        assert_eq!(results[0].status, Status::Fail);
    }

    #[test]
    fn expected_artifact_written_passes_for_large_file() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let artifact_path = bl.join("current-plan.md");
        let body: String = "x".repeat(300);
        fs::write(&artifact_path, body).unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user");
        spec.expected_artifact_path = Some(artifact_path.clone());
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ExpectedArtifactWritten, &r);
        assert_eq!(results[0].status, Status::Pass);
    }

    #[test]
    fn expected_artifact_written_fails_for_small_or_missing() {
        let tmp = TempDir::new().unwrap();
        let bl = make_buildloop(&tmp);
        let small_path = bl.join("current-plan.md");
        fs::write(&small_path, b"").unwrap();
        let h = ManifestHandle::new(&bl, "T1.1", Utc::now());
        let mut spec = empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user");
        spec.expected_artifact_path = Some(small_path.clone());
        let id = h.record_invocation(spec);
        h.record_exit(id, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h.flush().unwrap();
        let r = latest_run(&bl).unwrap();
        let results = run_check(ExpectedArtifactWritten, &r);
        assert_eq!(results[0].status, Status::Fail);

        // Now missing path
        let tmp2 = TempDir::new().unwrap();
        let bl2 = make_buildloop(&tmp2);
        let missing = bl2.join("does-not-exist.md");
        let h2 = ManifestHandle::new(&bl2, "T1.1", Utc::now());
        let mut spec2 = empty_spec(StageId::Plan, AgentRole::Planner, "sys", "user");
        spec2.expected_artifact_path = Some(missing);
        let id2 = h2.record_invocation(spec2);
        h2.record_exit(id2, StageStatus::Ran, Utc::now(), AgentExitInfo::default());
        h2.flush().unwrap();
        let r2 = latest_run(&bl2).unwrap();
        let results2 = run_check(ExpectedArtifactWritten, &r2);
        assert_eq!(results2[0].status, Status::Fail);
    }

    // Suppress unused warning: helper kept for future tests.
    #[allow(dead_code)]
    fn _unused(_p: &Path) {}
    #[allow(dead_code)]
    fn _unused2(_a: ArtifactSource) {}
}

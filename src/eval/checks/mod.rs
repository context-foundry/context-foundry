#![allow(dead_code)]

use crate::eval::run::RunTranscripts;
use crate::eval::stage_id::StageId;
use crate::run_manifest::{StageInvocation, StageStatus};

pub mod heuristic;
pub mod plumbing;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Category {
    Plumbing,
    Heuristic,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Severity {
    Critical,
    Standard,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Status {
    Pass,
    Fail,
    Skip,
}

#[derive(Debug, Clone)]
pub struct StageCheckResult {
    pub stage: StageId,
    pub invocation_id: u64,
    pub status: Status,
    pub evidence: String,
}

pub trait Check {
    fn name(&self) -> &'static str;
    fn category(&self) -> Category;
    fn severity(&self) -> Severity;
    fn applies_to(&self) -> &[StageId];
    fn run(&self, run: &RunTranscripts) -> Vec<StageCheckResult>;
}

pub fn invocation_skip_status(inv: &StageInvocation) -> Option<Status> {
    match inv.status {
        Some(StageStatus::Skipped)
        | Some(StageStatus::Reused)
        | Some(StageStatus::CheckpointResume) => Some(Status::Skip),
        _ => None,
    }
}

pub fn non_superseded(inv: &StageInvocation) -> bool {
    inv.superseded_by.is_none()
}

pub fn iter_stage(
    run: &RunTranscripts,
    stage: StageId,
) -> impl Iterator<Item = &(StageInvocation, crate::eval::parser::StageTranscript)> {
    run.invocations
        .iter()
        .filter(move |(inv, _)| inv.stage_id == Some(stage))
}

pub fn skip_evidence_for_status(
    status: Option<StageStatus>,
    skip_reason: &Option<String>,
) -> String {
    format!(
        "invocation status {:?}; reason: {}",
        status,
        skip_reason.as_deref().unwrap_or("none")
    )
}

pub fn all_checks() -> Vec<Box<dyn Check>> {
    vec![
        Box::new(plumbing::StageCompletedSuccessfully),
        Box::new(plumbing::SystemPromptPresent),
        Box::new(plumbing::ModelMatchesConfig),
        Box::new(plumbing::ExtensionLoaded),
        Box::new(plumbing::PatternsInjected),
        Box::new(plumbing::PriorArtifactReceived),
        Box::new(plumbing::PriorArtifactRead),
        Box::new(plumbing::ExpectedArtifactWritten),
        Box::new(heuristic::ScoutExplainsTaskDecomposition),
        Box::new(heuristic::TaskQueueWellFormed),
        Box::new(heuristic::PlanCoversResearchFiles),
        Box::new(heuristic::PlanHasVerification),
        Box::new(heuristic::PlanHasPerPhaseVerification),
        Box::new(heuristic::BuildClaimsHasFilesChanged),
        Box::new(heuristic::BuildClaimsHasVerificationResults),
        Box::new(heuristic::BuildClaimsFilesExist),
        Box::new(heuristic::BuildClaimsHasGapsSection),
        Box::new(heuristic::AuditEngaged),
        Box::new(heuristic::AuditFindingsLocalized),
        Box::new(heuristic::BashCommandsSafe),
        Box::new(heuristic::PatternCitationsPersisted),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn invocation_skip_status_skips_for_skipped_reused_checkpoint_resume() {
        let make = |s: Option<StageStatus>| StageInvocation {
            status: s,
            ..Default::default()
        };
        assert_eq!(
            invocation_skip_status(&make(Some(StageStatus::Skipped))),
            Some(Status::Skip)
        );
        assert_eq!(
            invocation_skip_status(&make(Some(StageStatus::Reused))),
            Some(Status::Skip)
        );
        assert_eq!(
            invocation_skip_status(&make(Some(StageStatus::CheckpointResume))),
            Some(Status::Skip)
        );
        assert_eq!(invocation_skip_status(&make(Some(StageStatus::Ran))), None);
        assert_eq!(invocation_skip_status(&make(Some(StageStatus::Failed))), None);
    }

    #[test]
    fn all_checks_returns_twenty_one() {
        assert_eq!(all_checks().len(), 21);
    }
}

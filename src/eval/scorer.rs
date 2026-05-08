#![allow(dead_code)]

use crate::eval::checks::{all_checks, Category, Severity, Status};
use crate::eval::run::RunTranscripts;
use crate::eval::stage_id::StageId;
use crate::run_manifest::StageStatus;
use serde::Serialize;
use std::collections::{BTreeMap, HashMap};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum StageBadge {
    Pass,
    Warn,
    Fail,
    Skipped,
}

impl StageBadge {
    pub fn glyph(self) -> char {
        match self {
            Self::Pass => '✓',
            Self::Warn => '⚠',
            Self::Fail => '✗',
            Self::Skipped => '-',
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct CheckOutcome {
    pub name: String,
    pub category: String,
    pub severity: String,
    pub status: Status,
    pub evidence: String,
    pub invocation_id: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct InvocationScore {
    pub invocation_id: u64,
    pub role: String,
    pub status: Option<StageStatus>,
    pub superseded_by: Option<u64>,
    pub skip_reason: Option<String>,
    pub artifact_source: Option<String>,
    pub checks: Vec<CheckOutcome>,
}

#[derive(Debug, Clone, Serialize)]
pub struct StageScore {
    pub stage: StageId,
    pub badge: StageBadge,
    pub invocations: Vec<InvocationScore>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Scores {
    pub stages: BTreeMap<String, StageScore>,
    pub aggregate_badge: String,
}

const QRPBA_ORDER: [StageId; 5] = [
    StageId::Query,
    StageId::Research,
    StageId::Plan,
    StageId::Build,
    StageId::Audit,
];

pub fn score_run(run: &RunTranscripts) -> Scores {
    let checks = all_checks();
    let mut by_inv: BTreeMap<u64, Vec<CheckOutcome>> = BTreeMap::new();
    for check in checks.iter() {
        let results = check.run(run);
        for r in results {
            let outcome = CheckOutcome {
                name: check.name().to_string(),
                category: format!("{:?}", check.category()).to_lowercase(),
                severity: format!("{:?}", check.severity()).to_lowercase(),
                status: r.status,
                evidence: r.evidence,
                invocation_id: r.invocation_id,
            };
            by_inv.entry(r.invocation_id).or_default().push(outcome);
        }
    }

    let mut stages: HashMap<StageId, Vec<InvocationScore>> = HashMap::new();
    for (inv, _) in run.invocations.iter() {
        let stage = match inv.stage_id {
            Some(s) => s,
            None => continue,
        };
        let checks_for_inv = by_inv.remove(&inv.invocation_id).unwrap_or_default();
        let artifact_source = inv
            .artifact_source
            .and_then(|a| serde_json::to_value(a).ok())
            .and_then(|v| v.as_str().map(|s| s.to_string()));
        let inv_score = InvocationScore {
            invocation_id: inv.invocation_id,
            role: inv.role.clone(),
            status: inv.status,
            superseded_by: inv.superseded_by,
            skip_reason: inv.skip_reason.clone(),
            artifact_source,
            checks: checks_for_inv,
        };
        stages.entry(stage).or_default().push(inv_score);
    }

    let mut stage_badges: HashMap<StageId, StageBadge> = HashMap::new();
    let mut output_stages: BTreeMap<String, StageScore> = BTreeMap::new();
    for stage in QRPBA_ORDER {
        let invs = stages.remove(&stage);
        let badge = aggregate_stage(invs.as_ref());
        stage_badges.insert(stage, badge);
        if let Some(invocations) = invs {
            output_stages.insert(
                stage.slug().to_string(),
                StageScore {
                    stage,
                    badge,
                    invocations,
                },
            );
        }
    }

    let aggregate_badge = aggregate_badge_string(&stage_badges);

    Scores {
        stages: output_stages,
        aggregate_badge,
    }
}

fn aggregate_stage(invocations: Option<&Vec<InvocationScore>>) -> StageBadge {
    let invs = match invocations {
        Some(v) if !v.is_empty() => v,
        _ => return StageBadge::Skipped,
    };
    let live: Vec<&InvocationScore> = invs.iter().filter(|i| i.superseded_by.is_none()).collect();
    if live.is_empty() {
        return StageBadge::Skipped;
    }
    let all_skip = live.iter().all(|i| {
        matches!(
            i.status,
            Some(StageStatus::Skipped)
                | Some(StageStatus::Reused)
                | Some(StageStatus::CheckpointResume)
        )
    });
    if all_skip {
        return StageBadge::Skipped;
    }

    let mut worst = StageBadge::Pass;
    for i in &live {
        for co in &i.checks {
            match co.status {
                Status::Skip | Status::Pass => {}
                Status::Fail => {
                    let critical_plumbing = co.severity == severity_to_lower(Severity::Critical)
                        && co.category == category_to_lower(Category::Plumbing);
                    if critical_plumbing {
                        worst = StageBadge::Fail;
                    } else if !matches!(worst, StageBadge::Fail) {
                        worst = StageBadge::Warn;
                    }
                }
            }
        }
    }
    worst
}

fn severity_to_lower(s: Severity) -> String {
    format!("{:?}", s).to_lowercase()
}

fn category_to_lower(c: Category) -> String {
    format!("{:?}", c).to_lowercase()
}

fn aggregate_badge_string(stages: &HashMap<StageId, StageBadge>) -> String {
    let q = stages.get(&StageId::Query).copied().unwrap_or(StageBadge::Skipped).glyph();
    let r = stages
        .get(&StageId::Research)
        .copied()
        .unwrap_or(StageBadge::Skipped)
        .glyph();
    let p = stages.get(&StageId::Plan).copied().unwrap_or(StageBadge::Skipped).glyph();
    let b = stages.get(&StageId::Build).copied().unwrap_or(StageBadge::Skipped).glyph();
    let a = stages
        .get(&StageId::Audit)
        .copied()
        .unwrap_or(StageBadge::Skipped)
        .glyph();
    format!("EVAL Q{}R{}P{}B{}A{}", q, r, p, b, a)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent::AgentRole;
    use crate::eval::run::latest_run;
    use crate::run_manifest::{
        AgentExitInfo, ManifestHandle, PromptEvidenceSpec, StageStatus,
    };
    use chrono::Utc;
    use std::fs;
    use tempfile::TempDir;

    fn make_check_outcome(severity: &str, category: &str, status: Status) -> CheckOutcome {
        CheckOutcome {
            name: "x".to_string(),
            category: category.to_string(),
            severity: severity.to_string(),
            status,
            evidence: String::new(),
            invocation_id: 1,
        }
    }

    fn inv_score(checks: Vec<CheckOutcome>) -> InvocationScore {
        InvocationScore {
            invocation_id: 1,
            role: "Planner".to_string(),
            status: Some(StageStatus::Ran),
            superseded_by: None,
            skip_reason: None,
            artifact_source: None,
            checks,
        }
    }

    #[test]
    fn aggregate_stage_returns_pass_when_all_pass() {
        let invs = vec![inv_score(vec![make_check_outcome(
            "critical",
            "plumbing",
            Status::Pass,
        )])];
        assert_eq!(aggregate_stage(Some(&invs)), StageBadge::Pass);
    }

    #[test]
    fn aggregate_stage_returns_warn_on_heuristic_fail() {
        let invs = vec![inv_score(vec![make_check_outcome(
            "standard",
            "heuristic",
            Status::Fail,
        )])];
        assert_eq!(aggregate_stage(Some(&invs)), StageBadge::Warn);
    }

    #[test]
    fn aggregate_stage_returns_warn_on_non_critical_plumbing_fail() {
        let invs = vec![inv_score(vec![make_check_outcome(
            "standard",
            "plumbing",
            Status::Fail,
        )])];
        assert_eq!(aggregate_stage(Some(&invs)), StageBadge::Warn);
    }

    #[test]
    fn aggregate_stage_returns_fail_on_critical_plumbing_fail() {
        let invs = vec![inv_score(vec![make_check_outcome(
            "critical",
            "plumbing",
            Status::Fail,
        )])];
        assert_eq!(aggregate_stage(Some(&invs)), StageBadge::Fail);
    }

    #[test]
    fn aggregate_stage_returns_skipped_when_all_invocations_skipped() {
        let mut s1 = inv_score(vec![]);
        s1.status = Some(StageStatus::Skipped);
        let mut s2 = inv_score(vec![]);
        s2.status = Some(StageStatus::Reused);
        let invs = vec![s1, s2];
        assert_eq!(aggregate_stage(Some(&invs)), StageBadge::Skipped);
    }

    #[test]
    fn aggregate_ignores_superseded_invocations() {
        let mut s1 = inv_score(vec![make_check_outcome("critical", "plumbing", Status::Fail)]);
        s1.superseded_by = Some(2);
        let s2 = inv_score(vec![make_check_outcome("critical", "plumbing", Status::Pass)]);
        let invs = vec![s1, s2];
        assert_eq!(aggregate_stage(Some(&invs)), StageBadge::Pass);
    }

    #[test]
    fn aggregate_multipass_takes_worst() {
        let s1 = inv_score(vec![make_check_outcome("critical", "plumbing", Status::Pass)]);
        let s2 = inv_score(vec![make_check_outcome("critical", "plumbing", Status::Pass)]);
        let s3 = inv_score(vec![make_check_outcome("critical", "plumbing", Status::Fail)]);
        let invs = vec![s1, s2, s3];
        assert_eq!(aggregate_stage(Some(&invs)), StageBadge::Fail);
    }

    #[test]
    fn aggregate_badge_string_renders_qrpba_order() {
        let mut m: HashMap<StageId, StageBadge> = HashMap::new();
        m.insert(StageId::Query, StageBadge::Pass);
        m.insert(StageId::Research, StageBadge::Warn);
        m.insert(StageId::Plan, StageBadge::Fail);
        m.insert(StageId::Build, StageBadge::Pass);
        m.insert(StageId::Audit, StageBadge::Skipped);
        let s = aggregate_badge_string(&m);
        assert_eq!(s, "EVAL Q✓R⚠P✗B✓A-");
    }

    #[test]
    fn score_run_smoke_via_manifest_handle() {
        let tmp = TempDir::new().unwrap();
        let bl = tmp.path().join(".buildloop");
        fs::create_dir_all(&bl).unwrap();
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
        let scores = score_run(&r);
        assert!(scores.aggregate_badge.starts_with("EVAL "));
        assert_eq!(scores.aggregate_badge.chars().count(), "EVAL Q-R-P-B-A-".chars().count());
    }
}

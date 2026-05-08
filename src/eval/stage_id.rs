#![allow(dead_code)]

use crate::agent::AgentRole;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum StageId {
    Query,
    Research,
    Plan,
    #[serde(rename = "implement")]
    Build,
    #[serde(rename = "doubt")]
    Audit,
}

impl StageId {
    pub fn slug(self) -> &'static str {
        match self {
            StageId::Query => "query",
            StageId::Research => "research",
            StageId::Plan => "plan",
            StageId::Build => "implement",
            StageId::Audit => "doubt",
        }
    }
}

pub fn from_log_prefix(prefix: &str) -> Option<StageId> {
    let key = prefix.trim().to_ascii_uppercase();
    match key.as_str() {
        "QUERY" => Some(StageId::Query),
        "RESEARCH" | "SCOUT" => Some(StageId::Research),
        "PLAN" | "PLANNER" => Some(StageId::Plan),
        "IMPLEMENT" | "BUILDER" | "BUILD" => Some(StageId::Build),
        "VERIFY" | "REVIEWER" | "FIXER" | "DOUBT" | "AUDIT" => Some(StageId::Audit),
        "P+" | "PLAN-REVIEW" | "DISCOVERY" | "DISCOVER" => None,
        _ => None,
    }
}

pub fn from_role(role: &AgentRole) -> Option<StageId> {
    match role {
        AgentRole::Query => Some(StageId::Query),
        AgentRole::Research | AgentRole::Scout => Some(StageId::Research),
        AgentRole::Planner => Some(StageId::Plan),
        AgentRole::Builder => Some(StageId::Build),
        AgentRole::Reviewer | AgentRole::Fixer => Some(StageId::Audit),
        AgentRole::PlanReview | AgentRole::Discovery => None,
    }
}

pub fn prior_artifact(stage: StageId) -> Option<&'static str> {
    match stage {
        StageId::Query => None,
        StageId::Research => Some(".buildloop/questions.md"),
        StageId::Plan => Some(".buildloop/research-report.md"),
        StageId::Build => Some(".buildloop/current-plan.md"),
        StageId::Audit => Some(".buildloop/build-claims.md"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stage_id_serde_lowercase_round_trip() {
        let cases = [
            (StageId::Query, "\"query\""),
            (StageId::Research, "\"research\""),
            (StageId::Plan, "\"plan\""),
            (StageId::Build, "\"implement\""),
            (StageId::Audit, "\"doubt\""),
        ];
        for (variant, expected) in cases {
            let s = serde_json::to_string(&variant).unwrap();
            assert_eq!(s, expected, "variant {:?} should serialize to {}", variant, expected);
            let back: StageId = serde_json::from_str(&s).unwrap();
            assert_eq!(back, variant);
        }
    }

    #[test]
    fn from_log_prefix_handles_legacy_and_current() {
        assert_eq!(from_log_prefix("PLANNER"), Some(StageId::Plan));
        assert_eq!(from_log_prefix("PLAN"), Some(StageId::Plan));
        assert_eq!(from_log_prefix("BUILDER"), Some(StageId::Build));
        assert_eq!(from_log_prefix("IMPLEMENT"), Some(StageId::Build));
        assert_eq!(from_log_prefix("REVIEWER"), Some(StageId::Audit));
        assert_eq!(from_log_prefix("FIXER"), Some(StageId::Audit));
        assert_eq!(from_log_prefix("VERIFY"), Some(StageId::Audit));
        assert_eq!(from_log_prefix("SCOUT"), Some(StageId::Research));
        assert_eq!(from_log_prefix("P+"), None);
        assert_eq!(from_log_prefix("DISCOVERY"), None);
        assert_eq!(from_log_prefix("UNKNOWN"), None);
    }

    #[test]
    fn from_role_covers_every_variant() {
        assert_eq!(from_role(&AgentRole::Query), Some(StageId::Query));
        assert_eq!(from_role(&AgentRole::Research), Some(StageId::Research));
        assert_eq!(from_role(&AgentRole::Scout), Some(StageId::Research));
        assert_eq!(from_role(&AgentRole::Planner), Some(StageId::Plan));
        assert_eq!(from_role(&AgentRole::Builder), Some(StageId::Build));
        assert_eq!(from_role(&AgentRole::Reviewer), Some(StageId::Audit));
        assert_eq!(from_role(&AgentRole::Fixer), Some(StageId::Audit));
        assert_eq!(from_role(&AgentRole::PlanReview), None);
        assert_eq!(from_role(&AgentRole::Discovery), None);
    }

    #[test]
    fn prior_artifact_map() {
        assert_eq!(prior_artifact(StageId::Query), None);
        assert_eq!(prior_artifact(StageId::Research), Some(".buildloop/questions.md"));
        assert_eq!(prior_artifact(StageId::Plan), Some(".buildloop/research-report.md"));
        assert_eq!(prior_artifact(StageId::Build), Some(".buildloop/current-plan.md"));
        assert_eq!(prior_artifact(StageId::Audit), Some(".buildloop/build-claims.md"));
    }
}

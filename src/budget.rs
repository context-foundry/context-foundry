use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::agent::AgentRole;
use crate::observatory::AgentUsage;
use crate::utils::atomic_write_file;

/// Per-phase context budget targets (percentage of context window).
/// Defaults match QRPID spec targets.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(default)]
pub struct BudgetTargets {
    pub scout: u8,    // QRPID Q+R phase: 15%
    pub planner: u8,  // QRPID P phase: 40%
    pub builder: u8,  // QRPID I phase: 60%
    pub reviewer: u8,     // QRPID D phase: 50%
    pub plan_review: u8,  // QRPID P+ phase: 35%
}

impl Default for BudgetTargets {
    fn default() -> Self {
        Self {
            scout: 15,
            planner: 40,
            builder: 60,
            reviewer: 50,
            plan_review: 35,
        }
    }
}

impl BudgetTargets {
    /// Map an AgentRole to its configured budget target percentage.
    pub fn target_for_role(&self, role: &AgentRole) -> Option<u8> {
        match role {
            AgentRole::Scout => Some(self.scout),
            AgentRole::Planner => Some(self.planner),
            AgentRole::Builder => Some(self.builder),
            AgentRole::Reviewer => Some(self.reviewer),
            AgentRole::Fixer => Some(self.reviewer), // shares D-phase budget
            AgentRole::Discovery => None,
        }
    }
}

/// Recovery actions the orchestrator can take when a phase overruns its budget.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RecoveryAction {
    /// Overrun within tolerance or no overrun -- continue normally
    Continue,
    /// Inject context summary directive into next phase prompt to compensate
    Summarize,
    /// Upgrade next phase to higher-capacity model
    Escalate,
    /// Recommend splitting the phase into narrower follow-up (logged, not auto-executed)
    SplitRecommended,
}

impl std::fmt::Display for RecoveryAction {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            RecoveryAction::Continue => write!(f, "continue"),
            RecoveryAction::Summarize => write!(f, "summarize"),
            RecoveryAction::Escalate => write!(f, "escalate"),
            RecoveryAction::SplitRecommended => write!(f, "split-recommended"),
        }
    }
}

/// Telemetry record for a single phase's budget evaluation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseBudgetRecord {
    pub phase: String,
    pub target_pct: u8,
    pub actual_pct: u8,
    pub overrun: bool,
    pub overrun_amount: i16,
    pub tokens_in: u64,
    pub tokens_out: u64,
    pub cost_usd: f64,
    pub recovery_action: RecoveryAction,
}

/// Complete budget telemetry for a pipeline run.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BudgetTelemetry {
    pub task_id: String,
    pub timestamp: String,
    pub records: Vec<PhaseBudgetRecord>,
    pub any_overrun: bool,
    pub recovery_actions_taken: Vec<String>,
}

/// Compare actual context usage to target budget and select recovery action.
pub fn evaluate_phase(
    role: &AgentRole,
    usage: &AgentUsage,
    targets: &BudgetTargets,
    overrun_threshold: u8,
) -> PhaseBudgetRecord {
    let target = targets.target_for_role(role).unwrap_or(50);
    let actual = usage.context_pct;
    let overrun_amount = actual as i16 - target as i16;
    let overrun = overrun_amount > 0;

    let recovery_action = if !overrun || overrun_amount <= overrun_threshold as i16 {
        RecoveryAction::Continue
    } else if overrun_amount <= 20 {
        RecoveryAction::Summarize
    } else if overrun_amount <= 40 {
        RecoveryAction::Escalate
    } else {
        RecoveryAction::SplitRecommended
    };

    PhaseBudgetRecord {
        phase: format!("{}", role),
        target_pct: target,
        actual_pct: actual,
        overrun,
        overrun_amount,
        tokens_in: usage.tokens_in,
        tokens_out: usage.tokens_out,
        cost_usd: usage.cost_usd,
        recovery_action,
    }
}

/// Generate a prompt prefix for the next phase when Summarize recovery is triggered.
pub fn summarize_directive(phase_name: &str, actual_pct: u8, target_pct: u8) -> String {
    format!(
        "CONTEXT BUDGET ALERT: The previous {} phase used {}% of the context window \
         (target: {}%). To compensate, prioritize the most critical findings and be concise. \
         Avoid re-reading files that the previous phase already summarized. \
         Focus on the highest-impact items only.",
        phase_name, actual_pct, target_pct,
    )
}

/// Persist budget telemetry to .buildloop/budget-telemetry.json.
pub fn write_telemetry(buildloop_dir: &Path, telemetry: &BudgetTelemetry) {
    let path = buildloop_dir.join("budget-telemetry.json");
    let json = match serde_json::to_string_pretty(telemetry) {
        Ok(s) => s,
        Err(_) => return,
    };
    let _ = atomic_write_file(&path, json.as_bytes());
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent::AgentRole;
    use crate::observatory::AgentUsage;

    #[test]
    fn test_default_budget_targets() {
        let t = BudgetTargets::default();
        assert_eq!(t.scout, 15);
        assert_eq!(t.planner, 40);
        assert_eq!(t.builder, 60);
        assert_eq!(t.reviewer, 50);
    }

    #[test]
    fn test_target_for_role_mapping() {
        let t = BudgetTargets::default();
        assert_eq!(t.target_for_role(&AgentRole::Scout), Some(15));
        assert_eq!(t.target_for_role(&AgentRole::Planner), Some(40));
        assert_eq!(t.target_for_role(&AgentRole::Builder), Some(60));
        assert_eq!(t.target_for_role(&AgentRole::Reviewer), Some(50));
        assert_eq!(t.target_for_role(&AgentRole::Fixer), Some(50));
        assert_eq!(t.target_for_role(&AgentRole::Discovery), None);
    }

    #[test]
    fn test_evaluate_phase_under_budget() {
        let usage = AgentUsage {
            context_pct: 10,
            tokens_in: 1000,
            tokens_out: 500,
            cost_usd: 0.01,
        };
        let targets = BudgetTargets::default();
        let record = evaluate_phase(&AgentRole::Planner, &usage, &targets, 10);
        assert!(!record.overrun);
        assert_eq!(record.recovery_action, RecoveryAction::Continue);
        assert_eq!(record.overrun_amount, -30); // 10 - 40
    }

    #[test]
    fn test_evaluate_phase_within_threshold() {
        let usage = AgentUsage {
            context_pct: 45,
            tokens_in: 5000,
            tokens_out: 2000,
            cost_usd: 0.05,
        };
        let targets = BudgetTargets::default();
        let record = evaluate_phase(&AgentRole::Planner, &usage, &targets, 10);
        assert!(record.overrun);
        assert_eq!(record.recovery_action, RecoveryAction::Continue); // within tolerance
        assert_eq!(record.overrun_amount, 5);
    }

    #[test]
    fn test_evaluate_phase_summarize() {
        let usage = AgentUsage {
            context_pct: 55,
            tokens_in: 8000,
            tokens_out: 3000,
            cost_usd: 0.10,
        };
        let targets = BudgetTargets::default();
        let record = evaluate_phase(&AgentRole::Planner, &usage, &targets, 5);
        assert!(record.overrun);
        assert_eq!(record.recovery_action, RecoveryAction::Summarize);
        assert_eq!(record.overrun_amount, 15);
    }

    #[test]
    fn test_evaluate_phase_escalate() {
        let usage = AgentUsage {
            context_pct: 75,
            tokens_in: 15000,
            tokens_out: 5000,
            cost_usd: 0.20,
        };
        let targets = BudgetTargets::default();
        let record = evaluate_phase(&AgentRole::Planner, &usage, &targets, 5);
        assert!(record.overrun);
        assert_eq!(record.recovery_action, RecoveryAction::Escalate);
        assert_eq!(record.overrun_amount, 35);
    }

    #[test]
    fn test_evaluate_phase_split_recommended() {
        let usage = AgentUsage {
            context_pct: 95,
            tokens_in: 25000,
            tokens_out: 8000,
            cost_usd: 0.50,
        };
        let targets = BudgetTargets::default();
        let record = evaluate_phase(&AgentRole::Planner, &usage, &targets, 5);
        assert!(record.overrun);
        assert_eq!(record.recovery_action, RecoveryAction::SplitRecommended);
        assert_eq!(record.overrun_amount, 55);
    }

    #[test]
    fn test_summarize_directive_contains_phase_name() {
        let directive = summarize_directive("Scout", 55, 15);
        assert!(directive.contains("Scout"));
        assert!(directive.contains("55%"));
        assert!(directive.contains("15%"));
    }

    #[test]
    fn test_write_telemetry_creates_file() {
        let dir = tempfile::tempdir().unwrap();
        let telemetry = BudgetTelemetry {
            task_id: "T1.1".to_string(),
            timestamp: "2026-01-01T00:00:00Z".to_string(),
            records: vec![PhaseBudgetRecord {
                phase: "Scout".to_string(),
                target_pct: 15,
                actual_pct: 20,
                overrun: true,
                overrun_amount: 5,
                tokens_in: 1000,
                tokens_out: 500,
                cost_usd: 0.01,
                recovery_action: RecoveryAction::Continue,
            }],
            any_overrun: true,
            recovery_actions_taken: vec!["Scout: continue".to_string()],
        };
        write_telemetry(dir.path(), &telemetry);
        let path = dir.path().join("budget-telemetry.json");
        assert!(path.exists());
        let content = std::fs::read_to_string(&path).unwrap();
        assert!(content.contains("T1.1"));
    }

    #[test]
    fn test_recovery_action_display() {
        assert_eq!(format!("{}", RecoveryAction::Continue), "continue");
        assert_eq!(format!("{}", RecoveryAction::Summarize), "summarize");
        assert_eq!(format!("{}", RecoveryAction::Escalate), "escalate");
        assert_eq!(
            format!("{}", RecoveryAction::SplitRecommended),
            "split-recommended"
        );
    }
}

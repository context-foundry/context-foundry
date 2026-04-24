use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use serde::Serialize;

use crate::agent::AgentExitKind;
use crate::config::Config;
use crate::sync_flag::SyncFlag;

use super::contract::ContractPaths;

#[derive(Debug, Clone, Serialize)]
#[allow(dead_code)]
pub enum FailureType {
    Timeout,
    Crash,
    GateFail,
    ReviewFail,
    RateLimited,
    StopRequested,
}

impl FailureType {
    #[allow(dead_code)]
    pub fn from_exit_kind(kind: &AgentExitKind) -> Self {
        match kind {
            AgentExitKind::TimedOut => FailureType::Timeout,
            AgentExitKind::Cancelled => FailureType::StopRequested,
            AgentExitKind::TransportStall => FailureType::Crash,
            AgentExitKind::Failed => FailureType::Crash,
            AgentExitKind::Completed => FailureType::Crash,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct StageResult {
    pub stage: String,
    pub success: bool,
    pub failure_type: Option<FailureType>,
    pub attempted_action: String,
    pub partial_results: Vec<String>,
    pub suggestions: Vec<String>,
}

impl StageResult {
    pub fn success(stage: &str, action: &str) -> Self {
        StageResult {
            stage: stage.to_string(),
            success: true,
            failure_type: None,
            attempted_action: action.to_string(),
            partial_results: Vec::new(),
            suggestions: Vec::new(),
        }
    }

    pub fn failure(
        stage: &str,
        action: &str,
        failure_type: FailureType,
        suggestions: Vec<String>,
    ) -> Self {
        StageResult {
            stage: stage.to_string(),
            success: false,
            failure_type: Some(failure_type),
            attempted_action: action.to_string(),
            partial_results: Vec::new(),
            suggestions,
        }
    }

    #[allow(dead_code)]
    pub fn with_partial_results(mut self, results: Vec<String>) -> Self {
        self.partial_results = results;
        self
    }
}

#[derive(Clone)]
pub(super) struct RunContext {
    pub(super) project_dir: PathBuf,
    pub(super) session_id: String,
    pub(super) config: Config,
    pub(super) spec_path: PathBuf,
    pub(super) updated_specs_path: PathBuf,
    pub(super) plan_path: PathBuf,
    pub(super) buildloop_dir: PathBuf,
    pub(super) log_dir: PathBuf,
    pub(super) current_plan: PathBuf,
    pub(super) review_report: PathBuf,
    pub(super) shutdown: Arc<AtomicBool>,
    pub(super) review_gate: Arc<SyncFlag>,
    pub(super) tasks_file_lock: Arc<Mutex<()>>,
    /// Cumulative session cost in millicents (1 USD = 100_000 millicents).
    /// Shared between build loop and output forwarding tasks.
    pub(super) session_cost_millicents: Arc<std::sync::atomic::AtomicU64>,
    /// Gate: set to true when awaiting commit approval, cleared when user responds.
    pub(super) commit_approval_gate: Arc<SyncFlag>,
    /// Result: true = approved (feat), false = denied (WIP). Only valid when gate is cleared.
    pub(super) commit_approval_result: Arc<SyncFlag>,
    /// Claude CLI version, detected once at session start.
    pub(super) cc_version: String,
}

impl RunContext {
    pub(super) fn new(
        project_dir: &Path,
        config: Config,
        shutdown: Arc<AtomicBool>,
        tasks_file_lock: Arc<Mutex<()>>,
    ) -> Self {
        let contract_paths = ContractPaths::resolve(project_dir);
        let buildloop_dir = project_dir.join(".buildloop");
        let log_dir = buildloop_dir.join("logs");

        Self {
            project_dir: project_dir.to_path_buf(),
            session_id: String::new(),
            config,
            spec_path: contract_paths.spec_path,
            updated_specs_path: contract_paths.updated_specs_path,
            plan_path: contract_paths.tasks_path,
            buildloop_dir: buildloop_dir.clone(),
            log_dir,
            current_plan: buildloop_dir.join("current-plan.md"),
            review_report: buildloop_dir.join("review-report.md"),
            shutdown,
            review_gate: Arc::new(SyncFlag::new(false)),
            tasks_file_lock,
            session_cost_millicents: Arc::new(std::sync::atomic::AtomicU64::new(0)),
            commit_approval_gate: Arc::new(SyncFlag::new(false)),
            commit_approval_result: Arc::new(SyncFlag::new(false)),
            cc_version: crate::agent::detect_cc_version(),
        }
    }

    pub(super) fn ensure_runtime_dirs(&self) {
        if let Err(e) = std::fs::create_dir_all(&self.log_dir) {
            eprintln!(
                "Warning: failed to create log directory {}: {}",
                self.log_dir.display(),
                e
            );
        }
    }

    pub(super) fn stop_file(&self) -> PathBuf {
        self.buildloop_dir.join("stop")
    }

    pub(super) fn is_stop_requested(&self) -> bool {
        let stop_file_exists = self.stop_file().exists();
        let shutdown_flag = self.shutdown.load(Ordering::Acquire);
        stop_file_exists || shutdown_flag
    }

    pub(super) fn spec_file_name(&self) -> String {
        self.spec_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned()
    }

    pub(super) fn tasks_file_name(&self) -> String {
        self.plan_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned()
    }

    /// Absolute path to spec file, for use in agent prompts.
    /// Claude Code may resolve cwd to git root, so bare filenames
    /// can match the wrong file in monorepo subdirectories.
    pub(super) fn spec_file_prompt_path(&self) -> String {
        self.spec_path.display().to_string()
    }

    /// Absolute path to tasks file, for use in agent prompts.
    pub(super) fn tasks_file_prompt_path(&self) -> String {
        self.plan_path.display().to_string()
    }

    /// Create a derived RunContext that inherits session_id and
    /// session_cost_millicents from self, but uses a new Config.
    /// Used by DualSelection::First/Second where only one pipeline runs.
    pub(super) fn derive(&self, config: Config) -> Self {
        let mut ctx = RunContext::new(
            &self.project_dir,
            config,
            self.shutdown.clone(),
            self.tasks_file_lock.clone(),
        );
        ctx.session_id = self.session_id.clone();
        ctx.session_cost_millicents = self.session_cost_millicents.clone();
        ctx
    }

    /// Create a derived RunContext for a worktree-based sub-pipeline
    /// (DualSelection::Both). Uses a different project_dir and generates
    /// a sub-session ID like "{parent_session_id}/pipeline-0" for
    /// telemetry disambiguation.
    pub(super) fn derive_sub_session(
        &self,
        config: Config,
        project_dir: &Path,
        sub_label: &str,
    ) -> Self {
        let mut ctx = RunContext::new(
            project_dir,
            config,
            self.shutdown.clone(),
            self.tasks_file_lock.clone(),
        );
        ctx.session_id = format!("{}/{}", self.session_id, sub_label);
        ctx.session_cost_millicents = self.session_cost_millicents.clone();
        ctx
    }
}

#[cfg(test)]
mod tests {
    use super::RunContext;
    use crate::config::Config;
    use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
    use std::sync::{Arc, Mutex};

    #[test]
    fn test_derive_inherits_session_id_and_cost() {
        let dir = std::env::temp_dir().join(format!(
            "foundry-ctx-derive-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        let mut parent = RunContext::new(
            &dir,
            Config::default(),
            Arc::new(AtomicBool::new(false)),
            Arc::new(Mutex::new(())),
        );
        parent.session_id = "sess-abc-123".to_string();
        parent.session_cost_millicents = Arc::new(AtomicU64::new(42_000));

        let child = parent.derive(Config::default());
        assert_eq!(child.session_id, "sess-abc-123");
        // Must share the same Arc, not a copy
        assert!(Arc::ptr_eq(
            &child.session_cost_millicents,
            &parent.session_cost_millicents
        ));
        // Mutating one is visible in the other
        child
            .session_cost_millicents
            .fetch_add(1000, Ordering::Relaxed);
        assert_eq!(
            parent.session_cost_millicents.load(Ordering::Relaxed),
            43_000
        );

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn test_derive_sub_session_generates_sub_id_and_shares_cost() {
        let parent_dir = std::env::temp_dir().join(format!(
            "foundry-ctx-subsess-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let child_dir = std::env::temp_dir().join(format!(
            "foundry-ctx-subsess-wt-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&parent_dir).unwrap();
        std::fs::create_dir_all(&child_dir).unwrap();

        let mut parent = RunContext::new(
            &parent_dir,
            Config::default(),
            Arc::new(AtomicBool::new(false)),
            Arc::new(Mutex::new(())),
        );
        parent.session_id = "sess-xyz-789".to_string();
        parent.session_cost_millicents = Arc::new(AtomicU64::new(10_000));

        let child = parent.derive_sub_session(Config::default(), &child_dir, "pipeline-0");
        assert_eq!(child.session_id, "sess-xyz-789/pipeline-0");
        assert_eq!(child.project_dir, child_dir);
        assert!(Arc::ptr_eq(
            &child.session_cost_millicents,
            &parent.session_cost_millicents
        ));

        let _ = std::fs::remove_dir_all(parent_dir);
        let _ = std::fs::remove_dir_all(child_dir);
    }

    #[test]
    fn test_derive_independent_approval_gates() {
        let dir = std::env::temp_dir().join(format!(
            "foundry-ctx-derive-gate-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();

        let parent = RunContext::new(
            &dir,
            Config::default(),
            Arc::new(AtomicBool::new(false)),
            Arc::new(Mutex::new(())),
        );

        let child = parent.derive(Config::default());

        // Gate/result must NOT be shared with parent
        assert!(!Arc::ptr_eq(
            &child.commit_approval_gate,
            &parent.commit_approval_gate
        ));
        assert!(!Arc::ptr_eq(
            &child.commit_approval_result,
            &parent.commit_approval_result
        ));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn test_derive_sub_session_slot_pattern_shares_cost() {
        let parent_dir = std::env::temp_dir().join(format!(
            "foundry-ctx-slot-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&parent_dir).unwrap();

        let mut parent = RunContext::new(
            &parent_dir,
            Config::default(),
            Arc::new(AtomicBool::new(false)),
            Arc::new(Mutex::new(())),
        );
        parent.session_id = "sess-parallel-test".to_string();
        parent.session_cost_millicents = Arc::new(AtomicU64::new(5_000));

        // Simulate creating slot contexts like run_parallel_builder does
        let mut slot_contexts = Vec::new();
        for slot_idx in 0..3 {
            let slot_dir = parent_dir.join(format!("slot-{}", slot_idx));
            std::fs::create_dir_all(&slot_dir).unwrap();
            let wt_ctx = parent.derive_sub_session(
                Config::default(),
                &slot_dir,
                &format!("slot-{}", slot_idx),
            );
            slot_contexts.push((slot_dir, wt_ctx));
        }

        // Verify each slot has the correct sub-session ID
        assert_eq!(slot_contexts[0].1.session_id, "sess-parallel-test/slot-0");
        assert_eq!(slot_contexts[1].1.session_id, "sess-parallel-test/slot-1");
        assert_eq!(slot_contexts[2].1.session_id, "sess-parallel-test/slot-2");

        // Verify all slots share the same session_cost_millicents Arc as parent
        for (_, wt_ctx) in &slot_contexts {
            assert!(Arc::ptr_eq(
                &wt_ctx.session_cost_millicents,
                &parent.session_cost_millicents
            ));
        }

        // Verify cost updates from any slot are visible in parent and all other slots
        slot_contexts[0]
            .1
            .session_cost_millicents
            .fetch_add(10_000, Ordering::Relaxed);
        slot_contexts[1]
            .1
            .session_cost_millicents
            .fetch_add(20_000, Ordering::Relaxed);
        slot_contexts[2]
            .1
            .session_cost_millicents
            .fetch_add(15_000, Ordering::Relaxed);
        assert_eq!(
            parent.session_cost_millicents.load(Ordering::Relaxed),
            50_000 // 5_000 initial + 10_000 + 20_000 + 15_000
        );

        let _ = std::fs::remove_dir_all(parent_dir);
    }

    #[test]
    fn test_derive_sub_session_independent_approval_gates() {
        let parent_dir = std::env::temp_dir().join(format!(
            "foundry-ctx-gate-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let child_dir_0 = parent_dir.join("wt-0");
        let child_dir_1 = parent_dir.join("wt-1");
        std::fs::create_dir_all(&parent_dir).unwrap();
        std::fs::create_dir_all(&child_dir_0).unwrap();
        std::fs::create_dir_all(&child_dir_1).unwrap();

        let parent = RunContext::new(
            &parent_dir,
            Config::default(),
            Arc::new(AtomicBool::new(false)),
            Arc::new(Mutex::new(())),
        );

        let child0 = parent.derive_sub_session(Config::default(), &child_dir_0, "pipeline-0");
        let child1 = parent.derive_sub_session(Config::default(), &child_dir_1, "pipeline-1");

        // Gate/result must NOT be shared between sub-sessions
        assert!(!Arc::ptr_eq(
            &child0.commit_approval_gate,
            &child1.commit_approval_gate
        ));
        assert!(!Arc::ptr_eq(
            &child0.commit_approval_result,
            &child1.commit_approval_result
        ));
        assert!(!Arc::ptr_eq(
            &child0.commit_approval_gate,
            &parent.commit_approval_gate
        ));
        assert!(!Arc::ptr_eq(
            &child0.commit_approval_result,
            &parent.commit_approval_result
        ));

        // Setting one pipeline's gate should not affect the other
        child0.commit_approval_gate.set();
        assert!(!child1.commit_approval_gate.get());
        assert!(!parent.commit_approval_gate.get());

        let _ = std::fs::remove_dir_all(parent_dir);
    }

    #[test]
    fn test_derive_sub_session_independent_review_gates() {
        let parent_dir = std::env::temp_dir().join(format!(
            "foundry-ctx-rgate-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let child_dir_0 = parent_dir.join("wt-0");
        let child_dir_1 = parent_dir.join("wt-1");
        std::fs::create_dir_all(&parent_dir).unwrap();
        std::fs::create_dir_all(&child_dir_0).unwrap();
        std::fs::create_dir_all(&child_dir_1).unwrap();

        let parent = RunContext::new(
            &parent_dir,
            Config::default(),
            Arc::new(AtomicBool::new(false)),
            Arc::new(Mutex::new(())),
        );

        let child0 = parent.derive_sub_session(Config::default(), &child_dir_0, "pipeline-0");
        let child1 = parent.derive_sub_session(Config::default(), &child_dir_1, "pipeline-1");

        // review_gate must NOT be shared between sub-sessions
        assert!(!Arc::ptr_eq(&child0.review_gate, &child1.review_gate));
        assert!(!Arc::ptr_eq(&child0.review_gate, &parent.review_gate));

        // Setting one pipeline's review_gate should not affect the other
        child0.review_gate.set();
        assert!(!child1.review_gate.get());
        assert!(!parent.review_gate.get());

        let _ = std::fs::remove_dir_all(parent_dir);
    }
}

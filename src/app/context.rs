use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use crate::config::Config;

use super::contract::ContractPaths;

#[derive(Clone)]
pub(super) struct RunContext {
    pub(super) project_dir: PathBuf,
    pub(super) config: Config,
    pub(super) spec_path: PathBuf,
    pub(super) plan_path: PathBuf,
    pub(super) buildloop_dir: PathBuf,
    pub(super) log_dir: PathBuf,
    pub(super) current_plan: PathBuf,
    pub(super) review_report: PathBuf,
    pub(super) shutdown: Arc<AtomicBool>,
}

impl RunContext {
    pub(super) fn new(project_dir: &Path, config: Config, shutdown: Arc<AtomicBool>) -> Self {
        let contract_paths = ContractPaths::resolve(project_dir);
        let buildloop_dir = project_dir.join(".buildloop");
        let log_dir = buildloop_dir.join("logs");

        Self {
            project_dir: project_dir.to_path_buf(),
            config,
            spec_path: contract_paths.spec_path,
            plan_path: contract_paths.tasks_path,
            buildloop_dir: buildloop_dir.clone(),
            log_dir,
            current_plan: buildloop_dir.join("current-plan.md"),
            review_report: buildloop_dir.join("review-report.md"),
            shutdown,
        }
    }

    pub(super) fn ensure_runtime_dirs(&self) {
        let _ = std::fs::create_dir_all(&self.log_dir);
    }

    pub(super) fn stop_file(&self) -> PathBuf {
        self.buildloop_dir.join("stop")
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
}

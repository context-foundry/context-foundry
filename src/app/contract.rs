use std::path::{Path, PathBuf};

pub(super) const SPEC_FILE_NAME: &str = "SPEC.md";
pub(super) const LEGACY_SPEC_FILE_NAME: &str = "ARCHITECTURE.md";
pub(super) const TASKS_FILE_NAME: &str = "TASKS.md";
pub(super) const LEGACY_TASKS_FILE_NAME: &str = "IMPL_PLAN.md";
pub(super) const UPDATED_SPECS_FILE_NAME: &str = "UPDATED_SPECS.md";

#[derive(Debug, Clone)]
pub(super) struct ContractPaths {
    pub(super) spec_path: PathBuf,
    pub(super) tasks_path: PathBuf,
    pub(super) updated_specs_path: PathBuf,
    spec_conflict: bool,
    tasks_conflict: bool,
}

impl ContractPaths {
    pub(super) fn resolve(project_dir: &Path) -> Self {
        let (spec_path, spec_conflict) =
            select_contract_path(project_dir, SPEC_FILE_NAME, LEGACY_SPEC_FILE_NAME);
        let (tasks_path, tasks_conflict) =
            select_contract_path(project_dir, TASKS_FILE_NAME, LEGACY_TASKS_FILE_NAME);

        Self {
            spec_path,
            tasks_path,
            updated_specs_path: project_dir.join(UPDATED_SPECS_FILE_NAME),
            spec_conflict,
            tasks_conflict,
        }
    }

    pub(super) fn spec_file_name(&self) -> String {
        file_name(&self.spec_path)
    }

    pub(super) fn tasks_file_name(&self) -> String {
        file_name(&self.tasks_path)
    }

    pub(super) fn updated_specs_path(&self) -> &Path {
        &self.updated_specs_path
    }

    pub(super) fn warnings(&self) -> Vec<String> {
        let mut warnings = Vec::new();

        if self.spec_conflict {
            warnings.push(format!(
                "Both {} and {} exist; using {}",
                SPEC_FILE_NAME, LEGACY_SPEC_FILE_NAME, SPEC_FILE_NAME
            ));
        }

        if self.tasks_conflict {
            warnings.push(format!(
                "Both {} and {} exist; using {}",
                TASKS_FILE_NAME, LEGACY_TASKS_FILE_NAME, TASKS_FILE_NAME
            ));
        }

        warnings
    }
}

fn select_contract_path(project_dir: &Path, preferred: &str, legacy: &str) -> (PathBuf, bool) {
    let preferred_path = project_dir.join(preferred);
    let legacy_path = project_dir.join(legacy);
    let preferred_exists = preferred_path.exists();
    let legacy_exists = legacy_path.exists();

    match (preferred_exists, legacy_exists) {
        (true, true) => (preferred_path, true),
        (true, false) => (preferred_path, false),
        (false, true) => (legacy_path, false),
        (false, false) => (preferred_path, false),
    }
}

fn file_name(path: &Path) -> String {
    path.file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_project_dir(name: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("{}-{}", name, unique));
        std::fs::create_dir_all(&dir).expect("failed to create temp dir");
        dir
    }

    #[test]
    fn resolve_prefers_new_contract_names() {
        let dir = temp_project_dir("foundry-contract-new");
        std::fs::write(dir.join(SPEC_FILE_NAME), "# Spec\n").expect("write spec");
        std::fs::write(dir.join(TASKS_FILE_NAME), "- [ ] T1.1: Task\n").expect("write tasks");

        let paths = ContractPaths::resolve(&dir);
        assert_eq!(paths.spec_file_name(), SPEC_FILE_NAME);
        assert_eq!(paths.tasks_file_name(), TASKS_FILE_NAME);
        assert!(paths.warnings().is_empty());

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn resolve_falls_back_to_legacy_contract_names() {
        let dir = temp_project_dir("foundry-contract-legacy");
        std::fs::write(dir.join(LEGACY_SPEC_FILE_NAME), "# Architecture\n").expect("write spec");
        std::fs::write(dir.join(LEGACY_TASKS_FILE_NAME), "- [ ] T1.1: Task\n")
            .expect("write tasks");

        let paths = ContractPaths::resolve(&dir);
        assert_eq!(paths.spec_file_name(), LEGACY_SPEC_FILE_NAME);
        assert_eq!(paths.tasks_file_name(), LEGACY_TASKS_FILE_NAME);
        assert!(paths.warnings().is_empty());

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn resolve_warns_when_both_new_and_legacy_exist() {
        let dir = temp_project_dir("foundry-contract-both");
        std::fs::write(dir.join(SPEC_FILE_NAME), "# Spec\n").expect("write spec");
        std::fs::write(dir.join(LEGACY_SPEC_FILE_NAME), "# Architecture\n").expect("write spec");
        std::fs::write(dir.join(TASKS_FILE_NAME), "- [ ] T1.1: Task\n").expect("write tasks");
        std::fs::write(
            dir.join(LEGACY_TASKS_FILE_NAME),
            "- [ ] T9.9: Legacy task\n",
        )
        .expect("write tasks");

        let paths = ContractPaths::resolve(&dir);
        assert_eq!(paths.spec_file_name(), SPEC_FILE_NAME);
        assert_eq!(paths.tasks_file_name(), TASKS_FILE_NAME);
        assert_eq!(paths.warnings().len(), 2);

        let _ = std::fs::remove_dir_all(dir);
    }
}

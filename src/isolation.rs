use anyhow::{Context as _, Result};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

/// Tracks files that have been temporarily hidden from the project workspace.
/// On drop, any un-restored files are automatically recovered (safety net).
pub struct PhaseIsolation {
    /// Map from original path -> temp backup path
    hidden: HashMap<PathBuf, PathBuf>,
    /// Temp directory holding the hidden files (cleaned up on restore)
    staging_dir: PathBuf,
    /// Whether restore() was explicitly called
    restored: bool,
}

/// Returns the list of files that must be hidden from the Research (R) phase.
/// Not yet called -- infrastructure for QRPID R-phase isolation.
#[allow(dead_code)]
pub fn research_restricted_paths(tasks_path: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if tasks_path.exists() {
        paths.push(tasks_path.to_path_buf());
    }
    paths
}

/// Returns the list of files that must be hidden from the Doubt (D) phase.
pub fn doubt_restricted_paths(buildloop_dir: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let plan = buildloop_dir.join("current-plan.md");
    if plan.exists() {
        paths.push(plan);
    }
    let questions = buildloop_dir.join("questions.md");
    if questions.exists() {
        paths.push(questions);
    }
    let research = buildloop_dir.join("research-report.md");
    if research.exists() {
        paths.push(research);
    }
    paths
}

impl PhaseIsolation {
    /// Hide all specified files by moving them to a temp staging directory.
    /// After this call, the files do not exist at their original paths.
    pub fn activate(restricted_paths: &[PathBuf]) -> Result<Self> {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let seq = COUNTER.fetch_add(1, Ordering::Relaxed);
        let staging_dir = std::env::temp_dir()
            .join(format!(".foundry-isolation-{}-{}", std::process::id(), seq));
        std::fs::create_dir_all(&staging_dir)
            .with_context(|| format!("failed to create staging dir {}", staging_dir.display()))?;

        let mut hidden = HashMap::new();
        let mut counter: usize = 0;

        for path in restricted_paths {
            if !path.exists() {
                continue;
            }
            let base_name = path
                .file_name()
                .unwrap_or(std::ffi::OsStr::new("unknown"))
                .to_os_string();
            let mut temp_name = base_name.clone();
            // Handle collisions from different directories with same filename
            while hidden.values().any(|v: &PathBuf| v.file_name() == Some(&temp_name)) {
                counter += 1;
                let name_str = base_name.to_string_lossy();
                temp_name = std::ffi::OsString::from(format!("{}_{}", name_str, counter));
            }
            let temp_path = staging_dir.join(&temp_name);
            move_file(path, &temp_path)
                .with_context(|| format!("failed to hide {}", path.display()))?;
            hidden.insert(path.clone(), temp_path);
        }

        Ok(PhaseIsolation {
            hidden,
            staging_dir,
            restored: false,
        })
    }

    /// Move all hidden files back to their original locations.
    /// Idempotent -- safe to call multiple times.
    pub fn restore(&mut self) -> Result<()> {
        if self.restored {
            return Ok(());
        }
        self.restored = true;
        for (original, temp) in &self.hidden {
            if temp.exists() {
                move_file(temp, original)
                    .with_context(|| format!("failed to restore {}", original.display()))?;
            }
        }
        let _ = std::fs::remove_dir_all(&self.staging_dir);
        Ok(())
    }

    /// Returns the original paths of all currently hidden files.
    pub fn hidden_paths(&self) -> Vec<&Path> {
        self.hidden.keys().map(|p| p.as_path()).collect()
    }
}

impl Drop for PhaseIsolation {
    fn drop(&mut self) {
        if !self.restored {
            for (original, temp) in &self.hidden {
                let _ = move_file(temp, original);
            }
            let _ = std::fs::remove_dir_all(&self.staging_dir);
        }
    }
}

/// Move a file from `src` to `dst`. Tries rename first (same-filesystem),
/// falls back to copy+remove when rename fails (cross-filesystem, macOS
/// temp-dir symlink issues, etc.).
fn move_file(src: &Path, dst: &Path) -> std::io::Result<()> {
    match std::fs::rename(src, dst) {
        Ok(()) => Ok(()),
        Err(_) => {
            std::fs::copy(src, dst)?;
            std::fs::remove_file(src)?;
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn setup_temp_files(names: &[&str]) -> (tempfile::TempDir, Vec<PathBuf>) {
        let dir = tempfile::tempdir().unwrap();
        let mut paths = Vec::new();
        for name in names {
            let p = dir.path().join(name);
            if let Some(parent) = p.parent() {
                fs::create_dir_all(parent).unwrap();
            }
            fs::write(&p, format!("content of {}", name)).unwrap();
            paths.push(p);
        }
        (dir, paths)
    }

    #[test]
    fn test_activate_hides_files() {
        let (_dir, paths) = setup_temp_files(&["a.md", "b.md"]);
        let guard = PhaseIsolation::activate(&paths).unwrap();
        assert!(!paths[0].exists(), "a.md should be hidden");
        assert!(!paths[1].exists(), "b.md should be hidden");
        assert_eq!(guard.hidden_paths().len(), 2);
        drop(guard); // restore via Drop
    }

    #[test]
    fn test_restore_brings_files_back() {
        let (_dir, paths) = setup_temp_files(&["a.md", "b.md"]);
        let mut guard = PhaseIsolation::activate(&paths).unwrap();
        assert!(!paths[0].exists());
        guard.restore().unwrap();
        assert!(paths[0].exists(), "a.md should be restored");
        assert!(paths[1].exists(), "b.md should be restored");
        assert_eq!(fs::read_to_string(&paths[0]).unwrap(), "content of a.md");
        assert_eq!(fs::read_to_string(&paths[1]).unwrap(), "content of b.md");
    }

    #[test]
    fn test_restore_is_idempotent() {
        let (_dir, paths) = setup_temp_files(&["a.md"]);
        let mut guard = PhaseIsolation::activate(&paths).unwrap();
        guard.restore().unwrap();
        guard.restore().unwrap(); // second call should not error
        assert!(paths[0].exists());
    }

    #[test]
    fn test_drop_restores_if_not_explicit() {
        let (_dir, paths) = setup_temp_files(&["a.md"]);
        {
            let _guard = PhaseIsolation::activate(&paths).unwrap();
            assert!(!paths[0].exists());
            // guard dropped here without explicit restore()
        }
        assert!(paths[0].exists(), "Drop should restore a.md");
        assert_eq!(fs::read_to_string(&paths[0]).unwrap(), "content of a.md");
    }

    #[test]
    fn test_skips_nonexistent_paths() {
        let dir = tempfile::tempdir().unwrap();
        let paths = vec![
            dir.path().join("nonexistent1.md"),
            dir.path().join("nonexistent2.md"),
        ];
        let guard = PhaseIsolation::activate(&paths).unwrap();
        assert!(guard.hidden_paths().is_empty());
    }

    #[test]
    fn test_research_restricted_paths_includes_tasks() {
        let dir = tempfile::tempdir().unwrap();
        let tasks = dir.path().join("TASKS.md");
        fs::write(&tasks, "- [ ] T1.1: do stuff").unwrap();
        let result = research_restricted_paths(&tasks);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0], tasks);
    }

    #[test]
    fn test_doubt_restricted_paths_includes_plan() {
        let dir = tempfile::tempdir().unwrap();
        let buildloop = dir.path().join(".buildloop");
        fs::create_dir_all(&buildloop).unwrap();
        let plan = buildloop.join("current-plan.md");
        fs::write(&plan, "# Plan\n## Step 1").unwrap();
        let result = doubt_restricted_paths(&buildloop);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0], plan);
    }

    #[test]
    fn test_isolation_prevents_grep_discovery() {
        let dir = tempfile::tempdir().unwrap();
        let tasks = dir.path().join("TASKS.md");
        let secret = "T99.1: secret task description";
        fs::write(&tasks, secret).unwrap();

        // Also create a subdirectory with another file to make sure
        // walking the project tree doesn't find the content
        let sub = dir.path().join("src");
        fs::create_dir_all(&sub).unwrap();
        fs::write(sub.join("main.rs"), "fn main() {}").unwrap();

        let paths = vec![tasks.clone()];
        let guard = PhaseIsolation::activate(&paths).unwrap();

        // Walk project directory recursively and check no file contains the secret
        fn walk_and_check(dir: &Path, needle: &str) -> bool {
            if dir.is_file() {
                if let Ok(content) = fs::read_to_string(dir) {
                    if content.contains(needle) {
                        return true; // found -- isolation failed
                    }
                }
                return false;
            }
            if dir.is_dir() {
                if let Ok(entries) = fs::read_dir(dir) {
                    for entry in entries.flatten() {
                        if walk_and_check(&entry.path(), needle) {
                            return true;
                        }
                    }
                }
            }
            false
        }

        assert!(
            !walk_and_check(dir.path(), secret),
            "secret task text should not be discoverable in project tree"
        );

        drop(guard);
        assert!(tasks.exists(), "TASKS.md should be restored after drop");
        assert_eq!(fs::read_to_string(&tasks).unwrap(), secret);
    }

    #[test]
    fn test_doubt_isolation_hides_plan_content() {
        let dir = tempfile::tempdir().unwrap();
        let buildloop = dir.path().join(".buildloop");
        fs::create_dir_all(&buildloop).unwrap();

        let plan_content = "# Plan\n## Step 1: Create src/isolation.rs\n## Step 2: Modify config";
        fs::write(buildloop.join("current-plan.md"), plan_content).unwrap();
        fs::write(
            buildloop.join("questions.md"),
            "# Questions\nQ1: What?",
        )
        .unwrap();

        let restricted = doubt_restricted_paths(&buildloop);
        assert_eq!(restricted.len(), 2);

        let guard = PhaseIsolation::activate(&restricted).unwrap();
        assert!(!buildloop.join("current-plan.md").exists());
        assert!(!buildloop.join("questions.md").exists());

        drop(guard);
        assert!(buildloop.join("current-plan.md").exists());
        assert!(buildloop.join("questions.md").exists());
        assert_eq!(
            fs::read_to_string(buildloop.join("current-plan.md")).unwrap(),
            plan_content
        );
    }
}

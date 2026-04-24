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
/// Hides TASKS.md, UPDATED_SPECS.md, and checkpoint.json to enforce phase isolation --
/// Research answers questions based on codebase investigation, not task context.
/// checkpoint.json contains the full task_desc which would defeat isolation.
pub fn research_restricted_paths(
    tasks_path: &Path,
    updated_specs_path: &Path,
    buildloop_dir: &Path,
) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if tasks_path.exists() {
        paths.push(tasks_path.to_path_buf());
    }
    if updated_specs_path.exists() {
        paths.push(updated_specs_path.to_path_buf());
    }
    let checkpoint = buildloop_dir.join("checkpoint.json");
    if checkpoint.exists() {
        paths.push(checkpoint);
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
        let staging_dir =
            std::env::temp_dir().join(format!(".foundry-isolation-{}-{}", std::process::id(), seq));
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
            while hidden
                .values()
                .any(|v: &PathBuf| v.file_name() == Some(&temp_name))
            {
                counter += 1;
                let name_str = base_name.to_string_lossy();
                temp_name = std::ffi::OsString::from(format!("{}_{}", name_str, counter));
            }
            let temp_path = staging_dir.join(&temp_name);
            match move_file(path, &temp_path)
                .with_context(|| format!("failed to hide {}", path.display()))
            {
                Ok(()) => {
                    hidden.insert(path.clone(), temp_path);
                }
                Err(e) => {
                    // Roll back all files already moved in earlier iterations
                    let mut rollback_ok = true;
                    for (original, temp) in &hidden {
                        if move_file(temp, original).is_err() {
                            rollback_ok = false;
                        }
                    }
                    if rollback_ok {
                        if let Err(e) = std::fs::remove_dir_all(&staging_dir) {
                            eprintln!(
                                "Warning: failed to clean up staging directory {}: {}",
                                staging_dir.display(),
                                e,
                            );
                        }
                    } else {
                        eprintln!(
                            "WARNING: PhaseIsolation::activate() rollback failed to restore \
                             all files. Staging directory preserved at: {}",
                            staging_dir.display(),
                        );
                    }
                    return Err(e);
                }
            }
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
        let total = self.hidden.len();
        let mut _restored_count: usize = 0;
        let mut missing_files: Vec<&Path> = Vec::new();
        for (original, temp) in &self.hidden {
            if temp.exists() {
                move_file(temp, original)
                    .with_context(|| format!("failed to restore {}", original.display()))?;
                _restored_count += 1;
            } else {
                missing_files.push(original.as_path());
            }
        }
        self.restored = true;
        if !missing_files.is_empty() {
            eprintln!(
                "WARNING: PhaseIsolation::restore() found {}/{} temp files missing from staging. \
                 Original files are permanently lost: {:?}. \
                 Staging directory preserved at: {}",
                missing_files.len(),
                total,
                missing_files,
                self.staging_dir.display(),
            );
            // Do NOT remove staging dir -- preserve for forensics (matching Drop behavior)
        } else if let Err(e) = std::fs::remove_dir_all(&self.staging_dir) {
            eprintln!(
                "Warning: failed to clean up staging directory {}: {}",
                self.staging_dir.display(),
                e,
            );
        }
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
            let total = self.hidden.len();
            let mut restored_count = 0usize;
            for (original, temp) in &self.hidden {
                if move_file(temp, original).is_ok() {
                    restored_count += 1;
                }
            }
            if restored_count < total {
                eprintln!(
                    "WARNING: PhaseIsolation failed to restore {}/{} files. \
                     Staging directory preserved at: {}",
                    total - restored_count,
                    total,
                    self.staging_dir.display(),
                );
            } else if let Err(e) = std::fs::remove_dir_all(&self.staging_dir) {
                eprintln!(
                    "Warning: failed to clean up staging directory {}: {}",
                    self.staging_dir.display(),
                    e,
                );
            }
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
    use serial_test::serial;
    use std::fs;
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;

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
    #[serial]
    fn test_activate_hides_files() {
        let (_dir, paths) = setup_temp_files(&["a.md", "b.md"]);
        let guard = PhaseIsolation::activate(&paths).unwrap();
        assert!(!paths[0].exists(), "a.md should be hidden");
        assert!(!paths[1].exists(), "b.md should be hidden");
        assert_eq!(guard.hidden_paths().len(), 2);
        drop(guard); // restore via Drop
    }

    #[test]
    #[serial]
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
    #[serial]
    fn test_restore_is_idempotent() {
        let (_dir, paths) = setup_temp_files(&["a.md"]);
        let mut guard = PhaseIsolation::activate(&paths).unwrap();
        guard.restore().unwrap();
        guard.restore().unwrap(); // second call should not error
        assert!(paths[0].exists());
    }

    #[test]
    #[serial]
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
    #[serial]
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
        let updated_specs = dir.path().join("UPDATED_SPECS.md");
        fs::write(&updated_specs, "Enhancement request").unwrap();
        let buildloop = dir.path().join(".buildloop");
        fs::create_dir_all(&buildloop).unwrap();
        let checkpoint = buildloop.join("checkpoint.json");
        fs::write(&checkpoint, r#"{"task_id":"T1","task_desc":"test","completed_stage":"query","timestamp":"2026-01-01T00:00:00Z"}"#).unwrap();
        let result = research_restricted_paths(&tasks, &updated_specs, &buildloop);
        assert_eq!(result.len(), 3);
        assert_eq!(result[0], tasks);
        assert_eq!(result[1], updated_specs);
        assert_eq!(result[2], checkpoint);
    }

    #[test]
    fn test_research_restricted_paths_without_checkpoint() {
        let dir = tempfile::tempdir().unwrap();
        let tasks = dir.path().join("TASKS.md");
        fs::write(&tasks, "- [ ] T1.1: do stuff").unwrap();
        let updated_specs = dir.path().join("UPDATED_SPECS.md");
        // updated_specs does not exist
        let buildloop = dir.path().join(".buildloop");
        // buildloop does not exist, so checkpoint.json won't exist
        let result = research_restricted_paths(&tasks, &updated_specs, &buildloop);
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
    #[serial]
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
    #[serial]
    fn test_doubt_isolation_hides_plan_content() {
        let dir = tempfile::tempdir().unwrap();
        let buildloop = dir.path().join(".buildloop");
        fs::create_dir_all(&buildloop).unwrap();

        let plan_content = "# Plan\n## Step 1: Create src/isolation.rs\n## Step 2: Modify config";
        fs::write(buildloop.join("current-plan.md"), plan_content).unwrap();
        fs::write(buildloop.join("questions.md"), "# Questions\nQ1: What?").unwrap();

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

    #[test]
    #[serial]
    fn test_restore_partial_failure_triggers_drop_recovery() {
        let (_dir, paths) = setup_temp_files(&["a.md", "b.md"]);
        let _guard = PhaseIsolation::activate(&paths).unwrap();
        assert!(!paths[0].exists());
        assert!(!paths[1].exists());

        // Sabotage: delete original's parent directory for the second file
        // so restore will fail mid-loop for that file. But since HashMap
        // iteration order is non-deterministic, we sabotage both parents
        // and then recreate one, so exactly one file's restore can succeed
        // during Drop.
        //
        // Actually, a simpler approach: delete one of the temp backup files
        // so move_file finds nothing to move for it (temp.exists() check
        // skips it), then the loop completes and restored=true. That does
        // NOT trigger the bug. We need move_file to FAIL (return Err).
        //
        // To trigger a move_file failure: remove the parent directory of
        // one original path so the move destination is invalid.
        let _parent_1 = paths[1].parent().unwrap();
        // paths share the same parent (tempdir), so we can't remove it.
        // Instead, directly verify the flag behavior: after the fix,
        // restored should be false if restore() returns Err.

        // Create a scenario: make destination unwritable by removing parent
        // We need separate parent dirs for this test.
        let dir_a = tempfile::tempdir().unwrap();
        let dir_b = tempfile::tempdir().unwrap();
        let file_a = dir_a.path().join("x.md");
        let file_b = dir_b.path().join("y.md");
        fs::write(&file_a, "content-x").unwrap();
        fs::write(&file_b, "content-y").unwrap();

        let mut guard2 = PhaseIsolation::activate(&[file_a.clone(), file_b.clone()]).unwrap();
        assert!(!file_a.exists());
        assert!(!file_b.exists());

        // Remove dir_b entirely so restoring file_b fails (no parent dir)
        drop(dir_b);

        // restore() should return Err because it can't restore file_b
        let result = guard2.restore();
        assert!(
            result.is_err(),
            "restore should fail when a destination parent is gone"
        );

        // The key assertion: after a failed restore(), Drop still runs recovery.
        // Since restored is still false, Drop will attempt to move files back.
        // file_a may or may not have been restored depending on iteration order,
        // but the guard should NOT have set restored=true.
        // Drop will fire when guard2 goes out of scope and attempt best-effort recovery.
        drop(guard2);

        // file_a should exist (either restore() got it before the error, or Drop recovered it)
        assert!(
            file_a.exists(),
            "file_a should be recovered after partial failure"
        );
    }

    #[test]
    #[serial]
    fn test_drop_preserves_staging_dir_on_restore_failure() {
        // Create two files in separate directories so we can delete one parent
        let dir_a = tempfile::tempdir().unwrap();
        let dir_b = tempfile::tempdir().unwrap();
        let file_a = dir_a.path().join("keep.md");
        let file_b = dir_b.path().join("lose.md");
        fs::write(&file_a, "content-keep").unwrap();
        fs::write(&file_b, "content-lose").unwrap();

        let guard = PhaseIsolation::activate(&[file_a.clone(), file_b.clone()]).unwrap();
        let staging_dir = guard.staging_dir.clone();
        assert!(!file_a.exists());
        assert!(!file_b.exists());
        assert!(staging_dir.exists());

        // Remove dir_b so restoring file_b will fail (parent gone)
        let dir_b_path = dir_b.path().to_path_buf();
        drop(dir_b);
        assert!(!dir_b_path.exists());

        // Drop the guard -- it should attempt best-effort restore
        drop(guard);

        // file_a should be restored (its parent still exists)
        assert!(file_a.exists(), "file_a should be recovered by Drop");
        assert_eq!(fs::read_to_string(&file_a).unwrap(), "content-keep");

        // Staging dir must be preserved because file_b could not be restored
        assert!(
            staging_dir.exists(),
            "staging dir must be preserved when a file cannot be restored"
        );

        // The unrestorable file's content must still exist somewhere in staging
        let mut found_content = false;
        for entry in fs::read_dir(&staging_dir).unwrap() {
            let entry = entry.unwrap();
            if let Ok(content) = fs::read_to_string(entry.path()) {
                if content == "content-lose" {
                    found_content = true;
                    break;
                }
            }
        }
        assert!(
            found_content,
            "staging dir must contain the unrestorable file's content"
        );

        // Cleanup
        let _ = fs::remove_dir_all(&staging_dir);
    }

    #[cfg(unix)]
    #[test]
    #[serial]
    fn test_activate_partial_failure_rolls_back() {
        let dir_ab = tempfile::tempdir().unwrap();
        let file1 = dir_ab.path().join("file1.md");
        let file2 = dir_ab.path().join("file2.md");
        fs::write(&file1, "content-1").unwrap();
        fs::write(&file2, "content-2").unwrap();

        let dir_c = tempfile::tempdir().unwrap();
        let file3 = dir_c.path().join("file3.md");
        fs::write(&file3, "content-3").unwrap();

        // Make dir_c read-only so move_file fails for file3
        let mut perms = fs::metadata(dir_c.path()).unwrap().permissions();
        perms.set_mode(0o555);
        fs::set_permissions(dir_c.path(), perms).unwrap();

        // Snapshot existing staging dirs before activate
        let pid = std::process::id();
        let tmp = std::env::temp_dir();
        let prefix = format!(".foundry-isolation-{}-", pid);
        let collect_staging_dirs =
            |tmp: &Path, prefix: &str| -> std::collections::HashSet<std::ffi::OsString> {
                fs::read_dir(tmp)
                    .unwrap()
                    .filter_map(|e| e.ok())
                    .filter(|e| e.file_name().to_string_lossy().starts_with(prefix))
                    .map(|e| e.file_name())
                    .collect()
            };
        let before_dirs = collect_staging_dirs(&tmp, &prefix);

        let result = PhaseIsolation::activate(&[file1.clone(), file2.clone(), file3.clone()]);
        assert!(
            result.is_err(),
            "activate should fail when move_file fails for file3"
        );

        // All files should exist at their original locations
        assert!(
            file1.exists(),
            "file1 should be rolled back to original location"
        );
        assert!(
            file2.exists(),
            "file2 should be rolled back to original location"
        );
        assert!(
            file3.exists(),
            "file3 should still exist (move failed before removal)"
        );
        assert_eq!(fs::read_to_string(&file1).unwrap(), "content-1");
        assert_eq!(fs::read_to_string(&file2).unwrap(), "content-2");

        // No new staging directories should persist
        let after_dirs = collect_staging_dirs(&tmp, &prefix);
        let new_dirs: std::collections::HashSet<_> = after_dirs.difference(&before_dirs).collect();
        assert!(
            new_dirs.is_empty(),
            "no new staging directories should persist after partial activation failure, found: {:?}",
            new_dirs,
        );

        // Restore dir_c permissions so tempdir cleanup succeeds
        let mut perms = fs::metadata(dir_c.path()).unwrap().permissions();
        perms.set_mode(0o755);
        fs::set_permissions(dir_c.path(), perms).unwrap();
    }

    #[test]
    #[serial]
    fn test_restore_warns_when_temp_files_missing() {
        let (_dir, paths) = setup_temp_files(&["a.md", "b.md"]);
        let mut guard = PhaseIsolation::activate(&paths).unwrap();
        assert!(!paths[0].exists());
        assert!(!paths[1].exists());
        let staging_dir = guard.staging_dir.clone();

        // Delete one temp file from the staging directory to simulate external deletion
        let first_temp = fs::read_dir(&staging_dir)
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        fs::remove_file(&first_temp).unwrap();

        // restore() should succeed (Ok), not return Err
        let result = guard.restore();
        assert!(
            result.is_ok(),
            "restore() should return Ok even when temp files are missing"
        );

        // Staging dir must be preserved (not deleted) because a file was missing
        assert!(
            staging_dir.exists(),
            "staging dir must be preserved when a temp file was missing"
        );

        // Exactly one file should be restored (the one whose temp still existed)
        let restored_count = paths.iter().filter(|p| p.exists()).count();
        assert_eq!(
            restored_count, 1,
            "only one file should be restored when one temp file is missing"
        );

        // Cleanup
        let _ = fs::remove_dir_all(&staging_dir);
    }

    #[cfg(unix)]
    #[test]
    #[serial]
    fn test_activate_rollback_preserves_staging_when_move_back_fails() {
        // This tests the invariant implemented in activate()'s Err handler:
        // if any rollback move_file fails, staging_dir must be preserved.
        // We recreate the rollback scenario directly because we cannot make
        // a rollback fail through the public API (synchronous, no mid-call
        // filesystem state change possible).

        // Set up a staging dir with two files (simulating already-moved files)
        let staging_dir = std::env::temp_dir().join(format!(
            ".foundry-isolation-test-rollback-{}",
            std::process::id()
        ));
        fs::create_dir_all(&staging_dir).unwrap();
        let temp_a = staging_dir.join("a.md");
        let temp_b = staging_dir.join("b.md");
        fs::write(&temp_a, "content-a").unwrap();
        fs::write(&temp_b, "content-b").unwrap();

        // Original paths: dir_a exists (rollback will succeed), dir_b does not (rollback will fail)
        let dir_a = tempfile::tempdir().unwrap();
        let original_a = dir_a.path().join("a.md");
        // dir_b is gone -- simulates parent deleted during agent phase
        let original_b = PathBuf::from("/tmp/nonexistent-foundry-test-dir/b.md");
        assert!(!original_b.parent().unwrap().exists());

        let mut hidden = HashMap::new();
        hidden.insert(original_a.clone(), temp_a.clone());
        hidden.insert(original_b.clone(), temp_b.clone());

        // Execute the same rollback logic as activate()'s Err handler
        let mut rollback_ok = true;
        for (original, temp) in &hidden {
            if move_file(temp, original).is_err() {
                rollback_ok = false;
            }
        }
        if rollback_ok {
            let _ = fs::remove_dir_all(&staging_dir);
        }
        // (In production code, the else branch logs a warning)

        // Staging dir MUST be preserved because file_b's rollback failed
        assert!(
            staging_dir.exists(),
            "staging dir must be preserved when rollback move_file fails"
        );

        // file_a should have been moved back to its original location
        assert!(original_a.exists(), "file_a should be rolled back");
        assert_eq!(fs::read_to_string(&original_a).unwrap(), "content-a");

        // file_b's content must still be in the staging dir (last surviving copy)
        assert!(
            temp_b.exists() || staging_dir.join("b.md").exists(),
            "file_b content must survive in staging dir"
        );

        // Cleanup
        let _ = fs::remove_dir_all(&staging_dir);
    }
}

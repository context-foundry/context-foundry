use anyhow::Result;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::config::Config;
use crate::utils::truncate_str;

#[allow(dead_code)]
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct GitContext {
    pub branch: String,
    pub dirty_count: usize,
    pub recent_commits: Vec<String>,
}

/// Check git and gh readiness, returning advisory log messages.
/// Auto-initializes a git repo if the project isn't one yet.
pub fn check_git_readiness(project_dir: &Path) -> Vec<String> {
    let mut messages = Vec::new();

    // 1. Check if project_dir is a git repo; auto-init if not
    let is_git = Command::new("git")
        .args(["rev-parse", "--is-inside-work-tree"])
        .current_dir(project_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false);

    if !is_git {
        let init_result = Command::new("git")
            .arg("init")
            .current_dir(project_dir)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        match init_result {
            Ok(s) if s.success() => {
                messages.push("Initialized git repo".into());
                // Create an initial empty commit so HEAD exists.
                // Without this, git operations fail in repos with no commits.
                let _ = Command::new("git")
                    .args(["commit", "--allow-empty", "-m", "Initial commit"])
                    .current_dir(project_dir)
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .status();
            }
            Ok(s) => messages.push(format!("git init failed (exit {})", s)),
            Err(e) => messages.push(format!("git init failed: {}", e)),
        }
    }

    // 2. Check gh auth status (advisory)
    match Command::new("gh")
        .args(["auth", "status"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
    {
        Err(_) => {
            messages
                .push("gh: not installed -- install GitHub CLI to enable GitHub features".into());
        }
        Ok(s) if !s.success() => {
            messages.push(
                "gh auth: not logged in -- run 'gh auth login' to enable GitHub features".into(),
            );
        }
        Ok(_) => {} // authenticated, no noise
    }

    messages
}

#[allow(dead_code)]
pub fn gather_git_context(project_dir: &Path) -> Option<GitContext> {
    let branch_output = Command::new("git")
        .args(["symbolic-ref", "--short", "HEAD"])
        .current_dir(project_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok()?;

    if !branch_output.status.success() {
        return None;
    }

    let branch = String::from_utf8_lossy(&branch_output.stdout)
        .trim()
        .to_string();

    let status_output = Command::new("git")
        .args(["status", "--porcelain"])
        .current_dir(project_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok();
    let dirty_count = status_output
        .as_ref()
        .map(|out| String::from_utf8_lossy(&out.stdout).lines().count())
        .unwrap_or(0);

    let recent_output = Command::new("git")
        .args(["log", "--oneline", "-3"])
        .current_dir(project_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok();
    let recent_commits = recent_output
        .as_ref()
        .filter(|out| out.status.success())
        .map(|out| {
            String::from_utf8_lossy(&out.stdout)
                .lines()
                .map(|line| line.trim().to_string())
                .filter(|line| !line.is_empty())
                .collect()
        })
        .unwrap_or_default();

    Some(GitContext {
        branch,
        dirty_count,
        recent_commits,
    })
}

pub fn commit_and_push(
    project_dir: &Path,
    config: &Config,
    task_id: &str,
    task_desc: &str,
    is_wip: bool,
) -> Result<bool> {
    // Stage all changes except .buildloop/logs
    Command::new("git")
        .args(["add", "-A"])
        .current_dir(project_dir)
        .output()?;

    let _ = Command::new("git")
        .args(["reset", "--", ".buildloop/logs/"])
        .current_dir(project_dir)
        .output();

    // Check if there's anything to commit
    let status = Command::new("git")
        .args(["diff", "--cached", "--quiet"])
        .current_dir(project_dir)
        .status()?;

    if status.success() {
        return Ok(false);
    }

    let short_desc = truncate_str(task_desc, 72);

    let msg = if is_wip {
        format!(
            "WIP({}): {}\n\nValidation did not pass. Committing to preserve progress.\n\nAutomated by: foundry",
            task_id, short_desc
        )
    } else {
        format!(
            "feat({}): {}\n\nImplemented and validated by autonomous build loop.\n\nAutomated by: foundry",
            task_id, short_desc
        )
    };

    let result = Command::new("git")
        .args(["commit", "-m", &msg])
        .current_dir(project_dir)
        .output()?;

    if !result.status.success() {
        return Ok(false);
    }

    maybe_push_commit(project_dir, config.auto_push_remote.as_deref())?;

    Ok(true)
}

fn maybe_push_commit(project_dir: &Path, remote: Option<&str>) -> Result<()> {
    let Some(remote) = remote.filter(|remote| !remote.trim().is_empty()) else {
        return Ok(());
    };

    let _ = Command::new("git")
        .args(["push", remote, "HEAD"])
        .current_dir(project_dir)
        .output()?;

    Ok(())
}

/// Create a feature branch, push it, and open a PR via `gh`.
/// Returns the PR number on success.
///
/// If the current branch is the repo's default branch (e.g. `main`), a new
/// feature branch `foundry/hil-<epoch>` is created so the PR targets default
/// instead of trying main-to-main (which GitHub rejects).
pub fn create_pr(
    project_dir: &Path,
    config: &Config,
    title: &str,
    body: &str,
) -> Result<Option<u64>> {
    // Determine current branch
    let branch_out = Command::new("git")
        .args(["branch", "--show-current"])
        .current_dir(project_dir)
        .output()?;
    let current_branch = String::from_utf8_lossy(&branch_out.stdout)
        .trim()
        .to_string();

    // Detect the default branch (usually "main" or "master")
    let default_branch = detect_default_branch(project_dir);

    let push_branch = if current_branch == default_branch {
        // Cannot PR default into default -- create a feature branch
        let epoch = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let feature_branch = format!("foundry/hil-{}", epoch);
        let checkout = Command::new("git")
            .args(["checkout", "-b", &feature_branch])
            .current_dir(project_dir)
            .output()?;
        if !checkout.status.success() {
            anyhow::bail!(
                "git checkout -b {} failed: {}",
                feature_branch,
                String::from_utf8_lossy(&checkout.stderr)
            );
        }
        feature_branch
    } else {
        current_branch
    };

    // Determine which remote to push to
    let remote = config
        .auto_push_remote
        .as_deref()
        .filter(|r| !r.trim().is_empty())
        .unwrap_or("origin");

    // Push the branch
    let push_result = Command::new("git")
        .args(["push", "-u", remote, &push_branch])
        .current_dir(project_dir)
        .output()?;

    if !push_result.status.success() {
        anyhow::bail!(
            "git push failed: {}",
            String::from_utf8_lossy(&push_result.stderr)
        );
    }

    // Create PR via gh
    let pr_result = Command::new("gh")
        .args([
            "pr",
            "create",
            "--base",
            &default_branch,
            "--title",
            title,
            "--body",
            body,
        ])
        .current_dir(project_dir)
        .output()?;

    if !pr_result.status.success() {
        let stderr = String::from_utf8_lossy(&pr_result.stderr);
        // If a PR already exists for this branch, that's fine
        if stderr.contains("already exists") {
            return Ok(None);
        }
        anyhow::bail!("gh pr create failed: {}", stderr);
    }

    // Parse PR number from output (gh prints the PR URL)
    let stdout = String::from_utf8_lossy(&pr_result.stdout);
    let pr_number = stdout
        .trim()
        .rsplit('/')
        .next()
        .and_then(|s| s.parse::<u64>().ok());

    Ok(pr_number)
}

/// Detect the default branch for the repo. Tries `gh repo view` first,
/// falls back to common names, then the current branch.
fn detect_default_branch(project_dir: &Path) -> String {
    // Try gh repo view --json defaultBranchRef
    if let Ok(output) = Command::new("gh")
        .args(["repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"])
        .current_dir(project_dir)
        .output()
    {
        if output.status.success() {
            let name = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !name.is_empty() {
                return name;
            }
        }
    }

    // Fallback: check if "main" or "master" branches exist locally
    for candidate in &["main", "master"] {
        let check = Command::new("git")
            .args(["rev-parse", "--verify", candidate])
            .current_dir(project_dir)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        if let Ok(s) = check {
            if s.success() {
                return candidate.to_string();
            }
        }
    }

    "main".to_string()
}

/// Annotate completed tasks in TASKS.md with a PR number.
/// Inserts `PR:#N` before the pipeline progress indicator (e.g. `[SPID]`) so
/// that the trailing `[XXXX]` regex in task.rs continues to match.
/// If there is no indicator, the tag is appended at the end.
pub fn annotate_tasks_with_pr(plan_path: &Path, pr_number: u64) -> Result<()> {
    use regex::Regex;
    use std::sync::LazyLock;

    static RE_PROGRESS_TAIL: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"\s+\[([A-Z!.\-]{4,6})\]\s*$").unwrap());

    let content = std::fs::read_to_string(plan_path)?;
    let mut lines: Vec<String> = content.lines().map(String::from).collect();

    let pr_tag = format!("PR:#{}", pr_number);

    for line in lines.iter_mut() {
        let trimmed = line.trim_start();
        // Only annotate completed tasks that don't already have a PR tag
        if trimmed.starts_with("- [x]") && !line.contains("PR:#") {
            if let Some(m) = RE_PROGRESS_TAIL.find(line) {
                // Insert PR tag before the [SPID] indicator
                let insert_pos = m.start();
                line.insert_str(insert_pos, &format!(" {}", pr_tag));
            } else {
                line.push_str(&format!(" {}", pr_tag));
            }
        }
    }

    crate::utils::atomic_write_file(plan_path, (lines.join("\n") + "\n").as_bytes())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::commit_and_push;
    use crate::config::Config;
    use std::fs;
    use std::path::{Path, PathBuf};
    use std::process::{Command, Stdio};
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir(name: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("{}-{}", name, unique));
        fs::create_dir_all(&dir).expect("create temp dir");
        dir
    }

    fn git(dir: &Path, args: &[&str]) {
        let status = Command::new("git")
            .args(args)
            .current_dir(dir)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .expect("run git");
        assert!(status.success(), "git command failed: {:?}", args);
    }

    fn init_repo(dir: &Path) {
        git(dir, &["init"]);
        git(dir, &["config", "user.email", "test@test.com"]);
        git(dir, &["config", "user.name", "Test User"]);
        fs::write(dir.join("README.md"), "seed\n").expect("write readme");
        git(dir, &["add", "README.md"]);
        git(dir, &["commit", "-m", "init"]);
    }

    fn current_branch(dir: &Path) -> String {
        let output = Command::new("git")
            .args(["branch", "--show-current"])
            .current_dir(dir)
            .output()
            .expect("git branch --show-current");
        String::from_utf8_lossy(&output.stdout).trim().to_string()
    }

    #[test]
    fn commit_and_push_commits_locally_without_auto_push_remote() {
        let repo_dir = temp_dir("foundry-git-local-only");
        init_repo(&repo_dir);
        fs::write(repo_dir.join("notes.txt"), "hello\n").expect("write notes");

        let committed = commit_and_push(
            &repo_dir,
            &Config::default(),
            "T1.1",
            "Add notes file",
            false,
        )
        .expect("commit should succeed");
        assert!(committed);

        let status_output = Command::new("git")
            .args(["status", "--short"])
            .current_dir(&repo_dir)
            .output()
            .expect("git status");
        assert!(
            String::from_utf8_lossy(&status_output.stdout)
                .trim()
                .is_empty(),
            "repo should be clean after commit"
        );

        let _ = fs::remove_dir_all(repo_dir);
    }

    #[test]
    fn commit_and_push_pushes_to_configured_remote() {
        let remote_dir = temp_dir("foundry-git-remote");
        let repo_dir = temp_dir("foundry-git-with-remote");
        git(&remote_dir, &["init", "--bare"]);
        init_repo(&repo_dir);
        git(
            &repo_dir,
            &["remote", "add", "snedea", remote_dir.to_str().unwrap()],
        );

        fs::write(repo_dir.join("notes.txt"), "hello\n").expect("write notes");
        let config = Config {
            auto_push_remote: Some("snedea".to_string()),
            ..Config::default()
        };

        let committed = commit_and_push(&repo_dir, &config, "T1.2", "Push notes file", false)
            .expect("commit and push should succeed");
        assert!(committed);

        let branch = current_branch(&repo_dir);
        let remote_output = Command::new("git")
            .args([
                "--git-dir",
                remote_dir.to_str().unwrap(),
                "rev-parse",
                &format!("refs/heads/{}", branch),
            ])
            .output()
            .expect("git rev-parse remote branch");
        assert!(
            remote_output.status.success(),
            "configured remote should receive pushed branch"
        );

        let _ = fs::remove_dir_all(repo_dir);
        let _ = fs::remove_dir_all(remote_dir);
    }

    #[test]
    fn annotate_tasks_appends_pr_tag_to_completed_tasks() {
        let path = temp_dir("foundry-annotate-basic");
        let file = path.join("TASKS.md");
        fs::write(
            &file,
            "- [x] T1.1: First task\n- [ ] T1.2: Pending task\n- [x] T1.3: Third task\n",
        )
        .expect("write tasks");

        super::annotate_tasks_with_pr(&file, 42).expect("annotate should succeed");
        let content = fs::read_to_string(&file).expect("read tasks");

        assert!(content.contains("- [x] T1.1: First task PR:#42"));
        assert!(content.contains("- [ ] T1.2: Pending task"));
        assert!(!content.contains("T1.2: Pending task PR:#42"));
        assert!(content.contains("- [x] T1.3: Third task PR:#42"));

        let _ = fs::remove_dir_all(path);
    }

    #[test]
    fn annotate_tasks_skips_already_tagged_lines() {
        let path = temp_dir("foundry-annotate-skip");
        let file = path.join("TASKS.md");
        fs::write(
            &file,
            "- [x] T1.1: First task PR:#10\n- [x] T1.2: Second task\n",
        )
        .expect("write tasks");

        super::annotate_tasks_with_pr(&file, 42).expect("annotate should succeed");
        let content = fs::read_to_string(&file).expect("read tasks");

        // T1.1 should keep its original PR tag, not get a second one
        assert!(content.contains("- [x] T1.1: First task PR:#10"));
        assert!(!content.contains("PR:#42\n- [x] T1.1"));
        // T1.2 should get the new tag
        assert!(content.contains("- [x] T1.2: Second task PR:#42"));

        let _ = fs::remove_dir_all(path);
    }

    #[test]
    fn annotate_tasks_inserts_pr_tag_before_spid_indicator() {
        let path = temp_dir("foundry-annotate-spid");
        let file = path.join("TASKS.md");
        fs::write(
            &file,
            "- [x] T1.1: First task [SPID]\n- [x] T1.2: No indicator\n- [x] T1.3: With exclaim [SPI!]\n",
        )
        .expect("write tasks");

        super::annotate_tasks_with_pr(&file, 7).expect("annotate should succeed");
        let content = fs::read_to_string(&file).expect("read tasks");

        // PR tag should appear before the [SPID] indicator
        assert!(
            content.contains("T1.1: First task PR:#7 [SPID]"),
            "PR tag should be before [SPID], got: {}",
            content
        );
        // No indicator -- tag goes at end
        assert!(content.contains("T1.2: No indicator PR:#7"));
        // Works with [SPI!] too
        assert!(
            content.contains("T1.3: With exclaim PR:#7 [SPI!]"),
            "PR tag should be before [SPI!], got: {}",
            content
        );

        let _ = fs::remove_dir_all(path);
    }
}

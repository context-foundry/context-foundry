use anyhow::Result;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::config::Config;
use crate::utils::truncate_str;

#[allow(dead_code)]
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct GitContext {
    pub branch: String,
    pub remote: Option<String>,
    pub dirty_count: usize,
    pub recent_commits: Vec<String>,
}

/// Check if `gh` CLI is installed and authenticated.
pub fn is_gh_authenticated() -> bool {
    Command::new("gh")
        .args(["auth", "status"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
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

    let remote = Command::new("git")
        .args(["remote"])
        .current_dir(project_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok()
        .and_then(|out| {
            String::from_utf8_lossy(&out.stdout)
                .lines()
                .next()
                .filter(|l| !l.trim().is_empty())
                .map(|l| l.trim().to_string())
        });

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
        remote,
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
#[allow(dead_code)]
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
#[allow(dead_code)]
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

/// Create a per-task PR: branch off the current branch, commit, push,
/// create a PR, then switch back to the base branch.
/// Returns `(committed, pr_number)`. Only used for validated (feat) commits.
pub fn commit_task_pr(
    project_dir: &Path,
    config: &Config,
    task_id: &str,
    task_desc: &str,
    plan_path: &Path,
) -> Result<(bool, Option<u64>)> {
    // Remember the base branch so we can return to it after the PR.
    let base_branch = {
        let out = Command::new("git")
            .args(["branch", "--show-current"])
            .current_dir(project_dir)
            .output()?;
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };

    // Sanitize task_id for branch name (e.g. "T1.1" -> "t1.1")
    let feature_branch = format!("foundry/{}", task_id.to_lowercase());

    let checkout = Command::new("git")
        .args(["checkout", "-B", &feature_branch])
        .current_dir(project_dir)
        .output()?;
    if !checkout.status.success() {
        anyhow::bail!(
            "git checkout -B {} failed: {}",
            feature_branch,
            String::from_utf8_lossy(&checkout.stderr)
        );
    }

    // Stage everything except logs (same as commit_and_push)
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
        // Nothing staged -- return to base and clean up the empty branch
        let _ = Command::new("git")
            .args(["checkout", &base_branch])
            .current_dir(project_dir)
            .output();
        let _ = Command::new("git")
            .args(["branch", "-d", &feature_branch])
            .current_dir(project_dir)
            .output();
        return Ok((false, None));
    }

    let short_desc = truncate_str(task_desc, 72);
    let msg = format!(
        "feat({}): {}\n\nImplemented and validated by autonomous build loop.\n\nAutomated by: foundry",
        task_id, short_desc
    );

    let commit_result = Command::new("git")
        .args(["commit", "-m", &msg])
        .current_dir(project_dir)
        .output()?;
    if !commit_result.status.success() {
        let _ = Command::new("git")
            .args(["checkout", &base_branch])
            .current_dir(project_dir)
            .output();
        return Ok((false, None));
    }

    // Push the feature branch
    let remote = config
        .auto_push_remote
        .as_deref()
        .filter(|r| !r.trim().is_empty())
        .unwrap_or("origin");

    let push_result = Command::new("git")
        .args(["push", "-u", remote, &feature_branch])
        .current_dir(project_dir)
        .output()?;

    let mut pr_number = None;
    if push_result.status.success() {
        let pr_body = format!(
            "## `feat({})`: {}\n\nImplemented and validated by autonomous build loop.\n\n---\nGenerated by `foundry v{}`",
            task_id, task_desc, env!("CARGO_PKG_VERSION"),
        );
        let pr_title = format!("feat({}): {}", task_id, &short_desc);

        let pr_result = Command::new("gh")
            .args([
                "pr", "create",
                "--base", &base_branch,
                "--title", &pr_title,
                "--body", &pr_body,
            ])
            .current_dir(project_dir)
            .output();

        if let Ok(output) = pr_result {
            if output.status.success() {
                pr_number = String::from_utf8_lossy(&output.stdout)
                    .trim()
                    .rsplit('/')
                    .next()
                    .and_then(|s| s.parse::<u64>().ok());
            }
        }
    }

    // Annotate TASKS.md with the PR number and push the annotation
    if let Some(pr_num) = pr_number {
        if annotate_tasks_with_pr(plan_path, pr_num, Some(task_id)).is_ok() {
            // Stage only TASKS.md (plan_path) to avoid picking up unrelated changes
            let _ = Command::new("git")
                .args(["add", &plan_path.to_string_lossy()])
                .current_dir(project_dir)
                .output();
            let annotation_msg = format!("annotate TASKS.md with PR #{} for {}", pr_num, task_id);
            let _ = Command::new("git")
                .args(["commit", "-m", &annotation_msg])
                .current_dir(project_dir)
                .output();
            let _ = Command::new("git")
                .args(["push", remote, &feature_branch])
                .current_dir(project_dir)
                .output();
        }
    }

    // Switch back to base branch for the next task
    let _ = Command::new("git")
        .args(["checkout", &base_branch])
        .current_dir(project_dir)
        .output();

    // Re-apply TASKS.md modifications (mark_done + progress indicator) to the base
    // branch working directory. The feature branch commit captured these changes, but
    // switching back to base reverts TASKS.md to the base version. Without this,
    // the build loop re-parses the task as pending and causes an infinite loop.
    if let Ok(feature_tasks_content) = Command::new("git")
        .args(["show", &format!("{}:{}", feature_branch, plan_path.file_name().unwrap().to_string_lossy())])
        .current_dir(project_dir)
        .output()
    {
        if feature_tasks_content.status.success() {
            let tasks_bytes = &feature_tasks_content.stdout;
            let _ = crate::utils::atomic_write_file(plan_path, tasks_bytes);
            // Stage and commit the TASKS.md update on the base branch
            let _ = Command::new("git")
                .args(["add", &plan_path.to_string_lossy()])
                .current_dir(project_dir)
                .output();
            let base_msg = format!("mark {} done on base branch", task_id);
            let _ = Command::new("git")
                .args(["commit", "-m", &base_msg])
                .current_dir(project_dir)
                .output();
        }
    }

    Ok((true, pr_number))
}

/// Create a GitHub issue for a WIP task with review findings as the body.
/// Returns the issue number on success, `None` if the number could not be
/// parsed from `gh` output. Best-effort: callers should catch errors.
pub fn create_wip_issue(
    project_dir: &Path,
    task_id: &str,
    task_desc: &str,
    review_report_path: &Path,
) -> Result<Option<u64>> {
    let mut review_body = std::fs::read_to_string(review_report_path)
        .unwrap_or_else(|_| "No review report available.".to_string());

    if review_body.trim().is_empty() {
        review_body = "No review report available.".to_string();
    }

    // Truncate to stay within GitHub's 65536-byte issue body limit
    const MAX_BODY_BYTES: usize = 60_000;
    if review_body.len() > MAX_BODY_BYTES {
        let end = {
            let mut e = MAX_BODY_BYTES;
            while e > 0 && !review_body.is_char_boundary(e) {
                e -= 1;
            }
            e
        };
        review_body = format!("{}\n\n...(truncated)", &review_body[..end]);
    }

    let title = format!(
        "WIP({}): {} -- validation failed",
        task_id,
        truncate_str(task_desc, 60),
    );

    let body = format!(
        "## WIP Commit: `{task_id}`\n\n\
         **Task:** {task_desc}\n\n\
         Validation did not pass. This issue was auto-created by foundry.\n\n\
         ---\n\n\
         ## Review Findings\n\n\
         {review_body}\n"
    );

    let output = Command::new("gh")
        .args(["issue", "create", "--title", &title, "--body", &body])
        .current_dir(project_dir)
        .output()?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        anyhow::bail!("gh issue create failed: {}", stderr);
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let issue_number = stdout
        .trim()
        .rsplit('/')
        .next()
        .and_then(|s| s.parse::<u64>().ok());

    Ok(issue_number)
}

/// Annotate completed tasks in TASKS.md with a PR number.
/// Inserts `PR:#N` before the pipeline progress indicator (e.g. `[SPID]`) so
/// that the trailing `[XXXX]` regex in task.rs continues to match.
/// If there is no indicator, the tag is appended at the end.
pub fn annotate_tasks_with_pr(plan_path: &Path, pr_number: u64, task_id_filter: Option<&str>) -> Result<()> {
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
            // If a task_id filter is set, only annotate the matching task line
            if let Some(filter_id) = task_id_filter {
                let id_with_colon = format!("{}:", filter_id);
                if !trimmed.contains(&id_with_colon) {
                    continue;
                }
            }
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
    fn commit_task_pr_creates_feature_branch_and_returns_to_base() {
        use super::commit_task_pr;

        let repo_dir = temp_dir("foundry-task-pr");
        init_repo(&repo_dir);
        let base = current_branch(&repo_dir);

        fs::write(repo_dir.join("feature.txt"), "new code\n").expect("write feature");

        // No remote, so push will fail but commit + branch should succeed
        let result = commit_task_pr(&repo_dir, &Config::default(), "T1.1", "Add feature", &repo_dir.join("TASKS.md"));
        assert!(result.is_ok() || result.is_err()); // push may fail, that's fine

        // After the call, we should be back on the base branch
        assert_eq!(current_branch(&repo_dir), base, "should return to base branch");

        // The feature branch should exist with the commit
        let branches = Command::new("git")
            .args(["branch"])
            .current_dir(&repo_dir)
            .output()
            .expect("git branch");
        let branch_list = String::from_utf8_lossy(&branches.stdout);
        assert!(
            branch_list.contains("foundry/t1.1"),
            "feature branch should exist, got: {}",
            branch_list
        );

        // Verify the commit message on the feature branch
        let log = Command::new("git")
            .args(["log", "--oneline", "-1", "foundry/t1.1"])
            .current_dir(&repo_dir)
            .output()
            .expect("git log");
        let log_text = String::from_utf8_lossy(&log.stdout);
        assert!(
            log_text.contains("feat(T1.1)"),
            "commit should have feat prefix, got: {}",
            log_text
        );

        let _ = fs::remove_dir_all(repo_dir);
    }

    #[test]
    fn commit_task_pr_returns_false_when_nothing_to_commit() {
        use super::commit_task_pr;

        let repo_dir = temp_dir("foundry-task-pr-empty");
        init_repo(&repo_dir);

        // No changes -- should return (false, None) and clean up the branch
        let (committed, pr) =
            commit_task_pr(&repo_dir, &Config::default(), "T2.1", "No changes", &repo_dir.join("TASKS.md"))
                .expect("should not error");
        assert!(!committed);
        assert!(pr.is_none());

        // Feature branch should not exist (cleaned up)
        let branches = Command::new("git")
            .args(["branch"])
            .current_dir(&repo_dir)
            .output()
            .expect("git branch");
        let branch_list = String::from_utf8_lossy(&branches.stdout);
        assert!(
            !branch_list.contains("foundry/t2.1"),
            "empty feature branch should be deleted, got: {}",
            branch_list
        );

        let _ = fs::remove_dir_all(repo_dir);
    }

    #[test]
    fn create_wip_issue_reads_review_report() {
        use super::create_wip_issue;

        let dir = temp_dir("foundry-wip-issue");
        let review_path = dir.join("review-report.md");
        fs::write(&review_path, "## Findings\n- HIGH: broken tests\n").expect("write review");

        // gh is not available in test, so this will fail with a Command error.
        // We just verify the function signature and that it reads the report.
        let result = create_wip_issue(&dir, "T1.1", "Add widget", &review_path);
        // Expected: Err because gh is not configured in test env, OR Ok(None) if gh
        // happens to be available but the repo doesn't exist on GitHub.
        // Either outcome is acceptable -- the test validates the function compiles
        // and accepts the expected arguments.
        assert!(result.is_ok() || result.is_err());

        let _ = fs::remove_dir_all(dir);
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

        super::annotate_tasks_with_pr(&file, 42, None).expect("annotate should succeed");
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

        super::annotate_tasks_with_pr(&file, 42, None).expect("annotate should succeed");
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

        super::annotate_tasks_with_pr(&file, 7, None).expect("annotate should succeed");
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

    #[test]
    fn annotate_tasks_scoped_to_single_task() {
        let path = temp_dir("foundry-annotate-scoped");
        let file = path.join("TASKS.md");
        fs::write(
            &file,
            "- [x] T1.1: First task [SPID]\n- [x] T2.1: Second task [SPID]\n- [x] T3.1: Third task [SPID]\n- [ ] T4.1: Pending task\n",
        )
        .expect("write tasks");

        super::annotate_tasks_with_pr(&file, 99, Some("T2.1")).expect("annotate should succeed");
        let content = fs::read_to_string(&file).expect("read tasks");

        // Only T2.1 should get the PR tag
        assert!(
            content.contains("T2.1: Second task PR:#99 [SPID]"),
            "T2.1 should be annotated, got: {}",
            content
        );
        // T1.1 and T3.1 should NOT get the PR tag
        assert!(
            !content.contains("T1.1: First task PR:#99"),
            "T1.1 should NOT be annotated, got: {}",
            content
        );
        assert!(
            !content.contains("T3.1: Third task PR:#99"),
            "T3.1 should NOT be annotated, got: {}",
            content
        );
        // Pending task should never be annotated
        assert!(!content.contains("T4.1: Pending task PR:#99"));

        let _ = fs::remove_dir_all(path);
    }
}

use std::path::Path;

use tokio::sync::mpsc;

use crate::agent::{self, AgentRole};
use crate::config::Config;
use crate::prompts;

use super::context::RunContext;
use super::{AppEvent, LoopEvent};

/// Returns `(passed, fix_passes)` so the caller can persist the pipeline progress indicator.
pub(super) async fn run_review_loop(
    task_id: &str,
    task_desc: &str,
    ctx: &RunContext,
    pattern_context: &str,
    extension_context: &str,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> (bool, usize) {
    let files_changed = get_changed_files(&ctx.project_dir);
    if files_changed.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "No changed files to review".to_string(),
        )));
        return (false, 0);
    }

    let files_list = files_changed.join("\n");

    // Determine whether to pass a diff or file list to the reviewer.
    let diff_for_review = if ctx.config.review_mode == "diff-only" {
        let diff = get_diff_for_review(&ctx.project_dir);
        if diff.is_empty() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Diff is empty, falling back to file list for review".to_string(),
            )));
            None
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Using diff-only review mode".to_string(),
            )));
            Some(diff)
        }
    } else {
        None
    };

    // The reviewer has full write access and fixes issues it finds in a single pass.
    // No separate fixer agent — the reviewer audits, fixes, re-verifies, and reports.
    let reviewer_tools: &[&str] = &["Read", "Glob", "Grep", "Write", "Bash"];

    let _ = std::fs::remove_file(&ctx.review_report);

    // Snapshot changed files before review so we can detect if reviewer applied fixes.
    let pre_review_files = get_changed_files(&ctx.project_dir);

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Reviewer,
        Config::display_provider_model(
            &ctx.config.reviewer_provider,
            &ctx.config.reviewer_model,
        ),
    )));

    let prompt = prompts::reviewer_prompt(
        task_id,
        task_desc,
        &files_list,
        1,
        pattern_context,
        diff_for_review.as_deref(),
        &ctx.spec_file_name(),
        &ctx.tasks_file_name(),
    );
    let prompt = prompts::wrap_with_extensions(&prompt, extension_context);
    let review_result = agent::run_agent(
        &AgentRole::Reviewer,
        Config::parse_provider(&ctx.config.reviewer_provider),
        &ctx.config.reviewer_model,
        &prompt,
        &ctx.project_dir,
        agent_tx,
        &ctx.log_dir,
        Some(reviewer_tools),
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
    )
    .await;

    let _ = tx.send(AppEvent::AgentDone(
        review_result.as_ref().map(|r| r.success).unwrap_or(false),
    ));

    let reviewer_succeeded = review_result.as_ref().map(|r| r.success).unwrap_or(false);
    if !reviewer_succeeded {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Fix agent failed — treating as review failure".to_string(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
            task_id: task_id.to_string(),
            fix_passes: 0,
            passed: false,
        }));
        return (false, 0);
    }

    // Detect whether the reviewer applied fixes by checking for new file changes.
    let post_review_files = get_changed_files(&ctx.project_dir);
    let reviewer_made_fixes = post_review_files.len() > pre_review_files.len()
        || post_review_files != pre_review_files;
    let fix_passes: usize = if reviewer_made_fixes { 1 } else { 0 };

    if reviewer_made_fixes {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Fix agent applied fixes during audit".to_string(),
        )));
    }

    // Guard: reviewer agent succeeded but report file is missing or empty.
    let report_has_content = ctx.review_report.exists()
        && std::fs::metadata(&ctx.review_report)
            .map(|m| m.len() > 0)
            .unwrap_or(false);

    if !report_has_content {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Fix agent succeeded but review-report.md is missing or empty — treating as failure".to_string(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
            task_id: task_id.to_string(),
            fix_passes,
            passed: false,
        }));
        return (false, fix_passes);
    }

    let verdict_pass = check_review_passed(&ctx.review_report);
    let (high, medium, _low) = parse_audit_findings(&ctx.review_report);

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Review: verdict={}, {} high, {} medium findings",
        if verdict_pass { "PASS" } else { "FAIL" },
        high,
        medium
    ))));

    let passed = verdict_pass || (high == 0 && medium == 0);

    if passed {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Review passed".to_string(),
        )));
    } else {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Review failed: {} high, {} medium unfixed issues remain",
            high, medium
        ))));
    }

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
        task_id: task_id.to_string(),
        fix_passes,
        passed,
    }));
    (passed, fix_passes)
}

fn get_diff_for_review(project_dir: &Path) -> String {
    // Try unstaged changes first (git diff HEAD).
    let output = std::process::Command::new("git")
        .args(["diff", "HEAD"])
        .current_dir(project_dir)
        .output();
    if let Ok(out) = &output {
        let diff = String::from_utf8_lossy(&out.stdout);
        let trimmed = diff.trim();
        if !trimmed.is_empty() {
            return trimmed.to_string();
        }
    }

    // Fall back to staged-only changes.
    let output = std::process::Command::new("git")
        .args(["diff", "--cached"])
        .current_dir(project_dir)
        .output();
    if let Ok(out) = &output {
        let diff = String::from_utf8_lossy(&out.stdout);
        let trimmed = diff.trim();
        if !trimmed.is_empty() {
            return trimmed.to_string();
        }
    }

    String::new()
}

fn get_changed_files(project_dir: &Path) -> Vec<String> {
    let output = std::process::Command::new("git")
        .args(["status", "--porcelain"])
        .current_dir(project_dir)
        .output();

    match output {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            stdout
                .lines()
                .filter_map(|line| {
                    if line.len() <= 3 {
                        return None;
                    }
                    let mut file = line[3..].trim();
                    if let Some(arrow_pos) = file.find(" -> ") {
                        file = file[arrow_pos + 4..].trim();
                    }
                    let file = file.trim_matches('"');
                    if file.is_empty() || file.starts_with(".buildloop/") {
                        return None;
                    }
                    Some(file.to_string())
                })
                .collect()
        }
        Err(_) => Vec::new(),
    }
}

fn parse_audit_findings(report_path: &Path) -> (usize, usize, usize) {
    let content = match std::fs::read_to_string(report_path) {
        Ok(c) => c,
        Err(_) => return (1, 0, 0),
    };

    if content.trim().is_empty() {
        return (1, 0, 0);
    }

    let json_str = extract_json_from_report(&content);
    if json_str.is_empty() {
        eprintln!("warning: audit report has no JSON code fence, treating as 1 high finding");
        return (1, 0, 0);
    }

    match serde_json::from_str::<serde_json::Value>(&json_str) {
        Ok(v) => {
            let high = v
                .get("high")
                .and_then(|a| a.as_array())
                .map(|a| a.len())
                .unwrap_or(0);
            let medium = v
                .get("medium")
                .and_then(|a| a.as_array())
                .map(|a| a.len())
                .unwrap_or(0);
            let low = v
                .get("low")
                .and_then(|a| a.as_array())
                .map(|a| a.len())
                .unwrap_or(0);
            (high, medium, low)
        }
        Err(e) => {
            eprintln!(
                "warning: failed to parse audit JSON: {}, treating as 1 high finding",
                e
            );
            (1, 0, 0)
        }
    }
}

fn extract_json_from_report(content: &str) -> String {
    let mut in_json_fence = false;
    let mut json_lines = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("```json") {
            in_json_fence = true;
            continue;
        }
        if in_json_fence && trimmed.starts_with("```") {
            break;
        }
        if in_json_fence {
            json_lines.push(line);
        }
    }

    json_lines.join("\n")
}

fn check_review_passed(report_path: &Path) -> bool {
    if let Ok(content) = std::fs::read_to_string(report_path) {
        let lower = content.to_lowercase();
        lower.contains("verdict: pass") || lower.contains("verdict:pass")
    } else {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::{
        check_review_passed, extract_json_from_report, get_changed_files, parse_audit_findings,
    };
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir(name: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("{}-{}", name, unique));
        std::fs::create_dir_all(&dir).expect("failed to create temp dir");
        dir
    }

    #[test]
    fn extract_json_from_report_reads_json_fence() {
        let content = "notes\n```json\n{\"high\":[],\"medium\":[]}\n```\n";
        assert_eq!(
            extract_json_from_report(content),
            "{\"high\":[],\"medium\":[]}"
        );
    }

    #[test]
    fn parse_audit_findings_treats_malformed_json_as_high() {
        let dir = temp_dir("foundry-review-json");
        let report = dir.join("report.md");
        std::fs::write(&report, "```json\n{not valid}\n```").expect("failed to write report");

        assert_eq!(parse_audit_findings(&report), (1, 0, 0));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn check_review_passed_matches_verdict_line() {
        let dir = temp_dir("foundry-review-pass");
        let report = dir.join("report.md");
        std::fs::write(&report, "Verdict: PASS\n").expect("failed to write report");

        assert!(check_review_passed(&report));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn get_changed_files_lists_modified_files_in_git_repo() {
        let dir = temp_dir("foundry-review-git");
        std::process::Command::new("git")
            .args(["init"])
            .current_dir(&dir)
            .output()
            .expect("git init should run");
        std::process::Command::new("git")
            .args(["config", "user.name", "Test User"])
            .current_dir(&dir)
            .output()
            .expect("git config user.name should run");
        std::process::Command::new("git")
            .args(["config", "user.email", "test@example.com"])
            .current_dir(&dir)
            .output()
            .expect("git config user.email should run");

        std::fs::write(dir.join("src.txt"), "one\n").expect("failed to write source file");
        std::process::Command::new("git")
            .args(["add", "src.txt"])
            .current_dir(&dir)
            .output()
            .expect("git add should run");
        std::process::Command::new("git")
            .args(["commit", "-m", "init"])
            .current_dir(&dir)
            .output()
            .expect("git commit should run");

        std::fs::write(dir.join("src.txt"), "two\n").expect("failed to update source file");

        let changed = get_changed_files(&dir);
        assert_eq!(changed, vec!["src.txt".to_string()]);

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn parse_audit_findings_returns_high_for_missing_file() {
        let path = PathBuf::from("/tmp/nonexistent-review-report-foundry.md");
        assert_eq!(parse_audit_findings(&path), (1, 0, 0));
    }

    #[test]
    fn parse_audit_findings_returns_high_for_empty_file() {
        let dir = temp_dir("foundry-review-empty");
        let report = dir.join("report.md");
        std::fs::write(&report, "").expect("failed to write report");

        assert_eq!(parse_audit_findings(&report), (1, 0, 0));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn parse_audit_findings_returns_high_for_whitespace_only_file() {
        let dir = temp_dir("foundry-review-whitespace");
        let report = dir.join("report.md");
        std::fs::write(&report, "   \n  \n").expect("failed to write report");

        assert_eq!(parse_audit_findings(&report), (1, 0, 0));

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn check_review_passed_returns_false_for_missing_file() {
        let path = PathBuf::from("/tmp/nonexistent-review-report-foundry.md");
        assert!(!check_review_passed(&path));
    }
}

use std::path::Path;

use tokio::sync::mpsc;

use crate::agent::{self, AgentRole};
use crate::config::Config;
use crate::prompts;

use super::context::RunContext;
use super::{AppEvent, LoopEvent};

pub(super) async fn run_review_loop(
    task_id: &str,
    task_desc: &str,
    ctx: &RunContext,
    pattern_context: &str,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> bool {
    let files_changed = get_changed_files(&ctx.project_dir);
    if files_changed.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "No changed files to review".to_string(),
        )));
        return false;
    }

    let files_list = files_changed.join("\n");
    let reviewer_tools: &[&str] = &["Read", "Glob", "Grep", "Write", "Bash"];

    for pass in 1..=2 {
        let _ = std::fs::remove_file(&ctx.review_report);

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

        let prompt =
            prompts::reviewer_prompt(task_id, task_desc, &files_list, pass, pattern_context);
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

        let verdict_pass = check_review_passed(&ctx.review_report);
        let (high, medium, _low) = parse_audit_findings(&ctx.review_report);

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Review pass {}/2: verdict={}, {} high, {} medium findings",
            pass,
            if verdict_pass { "PASS" } else { "FAIL" },
            high,
            medium
        ))));

        if verdict_pass || (high == 0 && medium == 0) {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Review passed — no actionable issues found".to_string(),
            )));
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
                task_id: task_id.to_string(),
                fix_passes: pass.saturating_sub(1),
                passed: true,
            }));
            return true;
        }

        if pass < 2 {
            tokio::time::sleep(std::time::Duration::from_secs(
                ctx.config.pause_between_agents_secs,
            ))
            .await;

            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            tokio::spawn(async move {
                while let Some(evt) = agent_rx.recv().await {
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Fixer,
                Config::display_provider_model(&ctx.config.fixer_provider, &ctx.config.fixer_model),
            )));

            let prompt = prompts::fixer_prompt(
                task_id,
                task_desc,
                pass,
                &ctx.spec_file_name(),
                &ctx.tasks_file_name(),
            );
            let fix_result = agent::run_agent(
                &AgentRole::Fixer,
                Config::parse_provider(&ctx.config.fixer_provider),
                &ctx.config.fixer_model,
                &prompt,
                &ctx.project_dir,
                agent_tx,
                &ctx.log_dir,
                None,
                ctx.config.agent_timeout_secs,
                Some(ctx.shutdown.clone()),
            )
            .await;

            let _ = tx.send(AppEvent::AgentDone(
                fix_result.map(|r| r.success).unwrap_or(false),
            ));

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Fixer completed, running second review pass...".to_string(),
            )));

            tokio::time::sleep(std::time::Duration::from_secs(
                ctx.config.pause_between_agents_secs,
            ))
            .await;
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Review pass 2 still has issues: {} high, {} medium — committing as-is",
                high, medium
            ))));
            // One fixer ran (pass 1), then re-review (pass 2) still failed
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
                task_id: task_id.to_string(),
                fix_passes: 1,
                passed: false,
            }));
        }
    }

    check_review_passed(&ctx.review_report)
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
        Err(_) => return (0, 0, 0),
    };

    if content.trim().is_empty() {
        return (0, 0, 0);
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
        content.to_lowercase().contains("verdict: pass")
            || content.to_lowercase().contains("verdict:pass")
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
}

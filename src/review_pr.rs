use anyhow::{anyhow, Context as _, Result};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Instant;
use tokio::sync::mpsc;

use crate::agent::{self, AgentOutputEvent, AgentResult, AgentRole};
use crate::config::Config;
use crate::observatory::{self, AgentUsage, ObservatoryEvent};
use crate::prompts;
use std::collections::HashSet;

// ─── Types ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy)]
pub enum ReviewPrOutput {
    Stdout,
    Json,
    Comment,
}

struct PrMetadata {
    title: String,
    body: String,
    head_branch: String,
    base_branch: String,
    changed_files: Vec<String>,
}

// ─── Helpers ─────────────────────────────────────────────────────

fn parse_output_mode(s: &str) -> Result<ReviewPrOutput> {
    match s.to_lowercase().as_str() {
        "stdout" => Ok(ReviewPrOutput::Stdout),
        "json" => Ok(ReviewPrOutput::Json),
        "comment" => Ok(ReviewPrOutput::Comment),
        _ => Err(anyhow!("Invalid output mode '{}'. Expected: stdout, json, comment", s)),
    }
}

fn detect_repo_from_git_remote(project_dir: &Path) -> Result<String> {
    let output = Command::new("git")
        .args(["remote", "get-url", "origin"])
        .current_dir(project_dir)
        .output()
        .context("Failed to run 'git remote get-url origin'")?;

    if !output.status.success() {
        return Err(anyhow!("Could not detect git remote origin. Use --repo OWNER/REPO."));
    }

    let url = String::from_utf8_lossy(&output.stdout).trim().to_string();

    // SSH format: git@github.com:OWNER/REPO.git
    if url.starts_with("git@") {
        let without_prefix = url.strip_prefix("git@").unwrap_or(&url);
        let normalized = without_prefix.replacen(':', "/", 1);
        let stripped = normalized.strip_suffix(".git").unwrap_or(&normalized);
        let parts: Vec<&str> = stripped.split('/').collect();
        if parts.len() >= 3 {
            return Ok(format!("{}/{}", parts[parts.len() - 2], parts[parts.len() - 1]));
        }
    }

    // HTTPS format: https://github.com/OWNER/REPO.git
    if url.contains("github.com") {
        if let Some(path) = url.split("github.com/").nth(1) {
            let stripped = path.strip_suffix(".git").unwrap_or(path);
            let parts: Vec<&str> = stripped.split('/').collect();
            if parts.len() >= 2 {
                return Ok(format!("{}/{}", parts[0], parts[1]));
            }
        }
    }

    Err(anyhow!("Could not parse OWNER/REPO from remote URL: {}", url))
}

fn fetch_pr_diff(pr_number: u32, repo: &str) -> Result<String> {
    let output = Command::new("gh")
        .args(["pr", "diff", &pr_number.to_string(), "--repo", repo])
        .output()
        .context("Failed to run 'gh pr diff'. Is gh CLI installed?")?;

    if !output.status.success() {
        return Err(anyhow!(
            "gh pr diff failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

fn fetch_pr_metadata(pr_number: u32, repo: &str) -> Result<PrMetadata> {
    let output = Command::new("gh")
        .args([
            "pr", "view",
            &pr_number.to_string(),
            "--repo", repo,
            "--json", "title,body,headRefName,baseRefName,files",
        ])
        .output()
        .context("Failed to run 'gh pr view'. Is gh CLI installed?")?;

    if !output.status.success() {
        return Err(anyhow!(
            "gh pr view failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    let json: serde_json::Value = serde_json::from_slice(&output.stdout)
        .context("Failed to parse 'gh pr view' JSON output")?;

    let title = json["title"].as_str().unwrap_or("").to_string();
    let body = json["body"].as_str().unwrap_or("").to_string();
    let head_branch = json["headRefName"].as_str().unwrap_or("").to_string();
    let base_branch = json["baseRefName"].as_str().unwrap_or("").to_string();

    let changed_files = json["files"]
        .as_array()
        .map(|arr| {
            arr.iter()
                .filter_map(|f| f["path"].as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    Ok(PrMetadata {
        title,
        body,
        head_branch,
        base_branch,
        changed_files,
    })
}

fn setup_temp_buildloop(project_dir: &Path, pr_number: u32, repo: &str) -> Result<PathBuf> {
    let pr_review_dir = project_dir.join(format!(".buildloop/pr-review-{}-{}", repo.replace('/', "--"), pr_number));
    let log_dir = pr_review_dir.join("logs");
    std::fs::create_dir_all(&log_dir).context("Failed to create PR review buildloop directory")?;
    Ok(pr_review_dir)
}

fn split_diff_by_file(diff: &str) -> Vec<(String, String)> {
    let mut result: Vec<(String, String)> = Vec::new();
    let mut current_file: Option<String> = None;
    let mut current_lines: Vec<&str> = Vec::new();

    for line in diff.lines() {
        if line.starts_with("diff --git ") {
            if let Some(file) = current_file.take() {
                result.push((file, current_lines.join("\n")));
                current_lines.clear();
            }
            let file_path = line
                .rsplit(" b/")
                .next()
                .unwrap_or("")
                .to_string();
            let file_path = if file_path.is_empty() {
                line.to_string()
            } else {
                file_path
            };
            current_file = Some(file_path);
        }
        current_lines.push(line);
    }

    if let Some(file) = current_file {
        if !current_lines.is_empty() {
            result.push((file, current_lines.join("\n")));
        }
    }

    result
}

fn merge_pr_findings(all_findings: &[serde_json::Value]) -> serde_json::Value {
    let mut high_all: Vec<serde_json::Value> = Vec::new();
    let mut medium_all: Vec<serde_json::Value> = Vec::new();
    let mut low_all: Vec<serde_json::Value> = Vec::new();

    for findings in all_findings {
        for (key, acc) in [
            ("high", &mut high_all),
            ("medium", &mut medium_all),
            ("low", &mut low_all),
        ] {
            if let Some(arr) = findings.get(key).and_then(|v| v.as_array()) {
                acc.extend(arr.iter().cloned());
            }
        }
    }

    // Deduplicate by (file, issue) pair
    fn dedup(items: &mut Vec<serde_json::Value>) {
        let mut seen = HashSet::new();
        items.retain(|item| {
            let file = item
                .get("file")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let issue = item
                .get("issue")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            seen.insert((file, issue))
        });
    }

    dedup(&mut high_all);
    dedup(&mut medium_all);
    dedup(&mut low_all);

    serde_json::json!({
        "high": high_all,
        "medium": medium_all,
        "low": low_all,
    })
}

fn parse_findings_json(report_content: &str) -> Result<serde_json::Value> {
    let mut in_json_block = false;
    let mut json_lines = Vec::new();

    for line in report_content.lines() {
        if line.trim().starts_with("```json") {
            in_json_block = true;
            continue;
        }
        if in_json_block && line.trim().starts_with("```") {
            let json_str = json_lines.join("\n");
            let value: serde_json::Value = serde_json::from_str(&json_str)
                .context("Failed to parse JSON findings block")?;
            return Ok(value);
        }
        if in_json_block {
            json_lines.push(line);
        }
    }

    Err(anyhow!("No valid JSON findings block found in review report"))
}

fn count_findings(findings: &serde_json::Value) -> (usize, usize, usize) {
    let high = findings.get("high").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
    let medium = findings.get("medium").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
    let low = findings.get("low").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
    (high, medium, low)
}

fn build_json_output(
    pr_number: u32,
    files_reviewed: usize,
    findings: &serde_json::Value,
    cost_usd: f64,
    duration_secs: f64,
) -> Result<String> {
    let (high, medium, low) = count_findings(findings);
    let output = serde_json::json!({
        "findings": findings,
        "summary": {
            "pr_number": pr_number,
            "files_reviewed": files_reviewed,
            "findings_high": high,
            "findings_medium": medium,
            "findings_low": low,
            "cost_usd": cost_usd,
            "duration_secs": duration_secs,
        }
    });
    serde_json::to_string_pretty(&output).context("Failed to format JSON output")
}

fn post_pr_comment(pr_number: u32, repo: &str, body: &str) -> Result<()> {
    let output = Command::new("gh")
        .args([
            "pr", "comment",
            &pr_number.to_string(),
            "--repo", repo,
            "--body", body,
        ])
        .output()
        .context("Failed to run 'gh pr comment'")?;

    if !output.status.success() {
        return Err(anyhow!(
            "gh pr comment failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    println!("Review posted as comment on PR #{}", pr_number);
    Ok(())
}

// ─── Multi-pass PR Review ───────────────────────────────────────

#[allow(clippy::too_many_arguments)]
async fn run_multipass_pr_review(
    pr_number: u32,
    metadata: &PrMetadata,
    diff: &str,
    config: &Config,
    pr_provider: &str,
    pr_model: &str,
    session_id: &str,
    project_dir: &Path,
    log_dir: &Path,
    review_report: &Path,
    review_report_relative: &str,
) -> (Result<AgentResult>, AgentUsage) {
    eprintln!(
        "Multi-pass PR review: {} files exceed threshold, running per-file analysis",
        metadata.changed_files.len()
    );

    let file_diffs = split_diff_by_file(diff);
    let diff_map: std::collections::HashMap<&str, &str> = file_diffs
        .iter()
        .map(|(f, d)| (f.as_str(), d.as_str()))
        .collect();

    let mut total_usage = AgentUsage::default();
    let mut all_per_file_findings: Vec<serde_json::Value> = Vec::new();

    for (i, file) in metadata.changed_files.iter().enumerate() {
        eprintln!(
            "Reviewing file {}/{}: {}",
            i + 1,
            metadata.changed_files.len(),
            file
        );

        let _ = std::fs::remove_file(review_report);

        let file_diff = diff_map.get(file.as_str()).copied().unwrap_or("");
        let prompt = prompts::pr_review_per_file_prompt(
            pr_number,
            &metadata.title,
            file,
            file_diff,
            review_report_relative,
        );

        let (agent_tx, mut agent_rx) = mpsc::unbounded_channel::<AgentOutputEvent>();

        let fwd_handle = tokio::spawn(async move {
            let mut usage = AgentUsage::default();
            while let Some(evt) = agent_rx.recv().await {
                usage.accumulate(&evt);
                if let AgentOutputEvent::Text(ref t) = evt {
                    eprint!("{}", t);
                }
            }
            usage
        });

        observatory::log_event(
            session_id,
            project_dir,
            ObservatoryEvent::AgentStarted {
                role: "Reviewer".to_string(),
                provider: pr_provider.to_string(),
                model: pr_model.to_string(),
            },
        );
        let per_file_start = Instant::now();

        let pr_review_tools: &[&str] = &["Read", "Glob", "Grep", "Bash"];
        let result = agent::run_agent(
            &AgentRole::Reviewer,
            Config::parse_provider(pr_provider),
            pr_model,
            &prompt,
            project_dir,
            agent_tx,
            log_dir,
            Some(pr_review_tools),
            config.agent_timeout_secs,
            None,
        )
        .await;

        let agent_usage = fwd_handle.await.unwrap_or_default();
        total_usage.tokens_in += agent_usage.tokens_in;
        total_usage.tokens_out += agent_usage.tokens_out;
        total_usage.cost_usd += agent_usage.cost_usd;
        total_usage.context_pct = total_usage.context_pct.max(agent_usage.context_pct);

        observatory::log_event(
            session_id,
            project_dir,
            ObservatoryEvent::AgentDone {
                role: "Reviewer".to_string(),
                success: result.is_ok(),
                duration_secs: per_file_start.elapsed().as_secs_f64(),
                tokens_in: agent_usage.tokens_in,
                tokens_out: agent_usage.tokens_out,
                cost_usd: agent_usage.cost_usd,
                context_pct: agent_usage.context_pct,
            },
        );

        if result.is_ok() {
            let findings = std::fs::read_to_string(review_report)
                .ok()
                .and_then(|content| parse_findings_json(&content).ok())
                .unwrap_or_else(|| {
                    serde_json::json!({"high": [], "medium": [], "low": []})
                });
            all_per_file_findings.push(findings);
        } else {
            eprintln!(
                "Per-file review failed for {} -- continuing with remaining files",
                file
            );
        }
    }

    // Clean up before integration pass
    let _ = std::fs::remove_file(review_report);

    let merged_findings = merge_pr_findings(&all_per_file_findings);
    let per_file_findings_json =
        serde_json::to_string_pretty(&merged_findings).unwrap_or_default();
    let (pf_high, pf_medium, _pf_low) = count_findings(&merged_findings);
    eprintln!(
        "Per-file analysis complete. Found {} high, {} medium findings. Running integration review...",
        pf_high, pf_medium
    );

    // Integration pass
    let prompt = prompts::pr_review_integration_prompt(
        pr_number,
        &metadata.title,
        &metadata.body,
        &metadata.head_branch,
        &metadata.base_branch,
        &metadata.changed_files.join("\n"),
        &per_file_findings_json,
        review_report_relative,
    );

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel::<AgentOutputEvent>();

    let fwd_handle = tokio::spawn(async move {
        let mut usage = AgentUsage::default();
        while let Some(evt) = agent_rx.recv().await {
            usage.accumulate(&evt);
            if let AgentOutputEvent::Text(ref t) = evt {
                eprint!("{}", t);
            }
        }
        usage
    });

    observatory::log_event(
        session_id,
        project_dir,
        ObservatoryEvent::AgentStarted {
            role: "Reviewer".to_string(),
            provider: pr_provider.to_string(),
            model: pr_model.to_string(),
        },
    );
    let integration_start = Instant::now();

    let pr_review_tools: &[&str] = &["Read", "Glob", "Grep", "Bash"];
    let integration_result = agent::run_agent(
        &AgentRole::Reviewer,
        Config::parse_provider(pr_provider),
        pr_model,
        &prompt,
        project_dir,
        agent_tx,
        log_dir,
        Some(pr_review_tools),
        config.agent_timeout_secs,
        None,
    )
    .await;

    let agent_usage = fwd_handle.await.unwrap_or_default();
    total_usage.tokens_in += agent_usage.tokens_in;
    total_usage.tokens_out += agent_usage.tokens_out;
    total_usage.cost_usd += agent_usage.cost_usd;
    total_usage.context_pct = total_usage.context_pct.max(agent_usage.context_pct);

    observatory::log_event(
        session_id,
        project_dir,
        ObservatoryEvent::AgentDone {
            role: "Reviewer".to_string(),
            success: integration_result.is_ok(),
            duration_secs: integration_start.elapsed().as_secs_f64(),
            tokens_in: agent_usage.tokens_in,
            tokens_out: agent_usage.tokens_out,
            cost_usd: agent_usage.cost_usd,
            context_pct: agent_usage.context_pct,
        },
    );

    match integration_result {
        Ok(agent_res) => (Ok(agent_res), total_usage),
        Err(e) => (
            Err(anyhow!("PR review integration agent failed: {}", e)),
            total_usage,
        ),
    }
}

// ─── Main Entry Point ────────────────────────────────────────────

pub async fn run(
    project_dir: &Path,
    pr_number: u32,
    repo: Option<String>,
    output: &str,
) -> Result<()> {
    let output_mode = parse_output_mode(output)?;

    let repo = match repo {
        Some(r) => r,
        None => detect_repo_from_git_remote(project_dir)?,
    };

    eprintln!("Reviewing PR #{} in {}...", pr_number, repo);

    let diff = fetch_pr_diff(pr_number, &repo)?;
    if diff.is_empty() {
        return Err(anyhow!("PR #{} has no diff", pr_number));
    }

    let metadata = fetch_pr_metadata(pr_number, &repo)?;

    let buildloop_dir = setup_temp_buildloop(project_dir, pr_number, &repo)?;
    let log_dir = buildloop_dir.join("logs");
    let review_report = buildloop_dir.join("review-report.md");

    // Remove any existing review-report.md
    let _ = std::fs::remove_file(&review_report);

    let config = Config::load(project_dir);

    // Resolve PR review model/provider with fallback to reviewer defaults
    let pr_provider = if config.pr_review_provider.is_empty() {
        config.reviewer_provider.clone()
    } else {
        config.pr_review_provider.clone()
    };
    let pr_model = if config.pr_review_model.is_empty() {
        config.reviewer_model.clone()
    } else {
        config.pr_review_model.clone()
    };

    // Observatory: session tracking
    let session_id = format!("pr-review-{}-{}", repo.replace('/', "--"), pr_number);
    let session_start = Instant::now();

    observatory::log_event(
        &session_id,
        project_dir,
        ObservatoryEvent::SessionStarted {
            config: serde_json::json!({
                "pr_number": pr_number,
                "repo": repo,
                "pr_review_provider": pr_provider,
                "pr_review_model": pr_model,
                "output_mode": output,
                "diff_line_count": diff.lines().count(),
                "changed_file_count": metadata.changed_files.len(),
            }),
        },
    );

    let multipass_threshold = if config.pr_review_multipass_threshold > 0 {
        config.pr_review_multipass_threshold
    } else {
        config.review_multipass_threshold
    };

    eprintln!(
        "PR diff: {} lines, {} changed files (multipass threshold: {})",
        diff.lines().count(),
        metadata.changed_files.len(),
        multipass_threshold,
    );

    let changed_files_str = metadata.changed_files.join("\n");
    let review_report_relative = format!(".buildloop/pr-review-{}-{}/review-report.md", repo.replace('/', "--"), pr_number);

    let use_multipass = multipass_threshold > 0 && metadata.changed_files.len() > multipass_threshold;

    let (agent_result, usage) = if use_multipass {
        run_multipass_pr_review(
            pr_number,
            &metadata,
            &diff,
            &config,
            &pr_provider,
            &pr_model,
            &session_id,
            project_dir,
            &log_dir,
            &review_report,
            &review_report_relative,
        )
        .await
    } else {
        // Single-pass review (existing flow)
        let prompt = prompts::pr_review_prompt(
            pr_number,
            &metadata.title,
            &metadata.body,
            &metadata.head_branch,
            &metadata.base_branch,
            &diff,
            &changed_files_str,
            &review_report_relative,
        );

        let (agent_tx, mut agent_rx) = mpsc::unbounded_channel::<AgentOutputEvent>();

        let fwd_handle = tokio::spawn(async move {
            let mut usage = AgentUsage::default();
            while let Some(evt) = agent_rx.recv().await {
                usage.accumulate(&evt);
                if let AgentOutputEvent::Text(ref t) = evt {
                    eprint!("{}", t);
                }
            }
            usage
        });

        observatory::log_event(
            &session_id,
            project_dir,
            ObservatoryEvent::AgentStarted {
                role: "Reviewer".to_string(),
                provider: pr_provider.clone(),
                model: pr_model.clone(),
            },
        );
        let agent_start = Instant::now();

        let pr_review_tools: &[&str] = &["Read", "Glob", "Grep", "Bash"];
        let result = agent::run_agent(
            &AgentRole::Reviewer,
            Config::parse_provider(&pr_provider),
            &pr_model,
            &prompt,
            project_dir,
            agent_tx,
            &log_dir,
            Some(pr_review_tools),
            config.agent_timeout_secs,
            None,
        )
        .await;

        let usage = fwd_handle.await.unwrap_or_default();

        observatory::log_event(
            &session_id,
            project_dir,
            ObservatoryEvent::AgentDone {
                role: "Reviewer".to_string(),
                success: result.is_ok(),
                duration_secs: agent_start.elapsed().as_secs_f64(),
                tokens_in: usage.tokens_in,
                tokens_out: usage.tokens_out,
                cost_usd: usage.cost_usd,
                context_pct: usage.context_pct,
            },
        );

        (result, usage)
    };

    if let Err(ref e) = agent_result {
        observatory::log_event(
            &session_id,
            project_dir,
            ObservatoryEvent::SessionEnded {
                total_tasks: 0,
                feat_count: 0,
                wip_count: 0,
                total_cost_usd: usage.cost_usd,
                duration_secs: session_start.elapsed().as_secs_f64(),
            },
        );
        let _ = std::fs::remove_dir_all(&buildloop_dir);
        return Err(anyhow!("PR review agent failed: {}", e));
    }

    let report_content = match std::fs::read_to_string(&review_report) {
        Ok(content) => content,
        Err(_) => {
            observatory::log_event(
                &session_id,
                project_dir,
                ObservatoryEvent::SessionEnded {
                    total_tasks: 0,
                    feat_count: 0,
                    wip_count: 0,
                    total_cost_usd: usage.cost_usd,
                    duration_secs: session_start.elapsed().as_secs_f64(),
                },
            );
            let _ = std::fs::remove_dir_all(&buildloop_dir);
            return Err(anyhow!("Reviewer did not produce review-report.md"));
        }
    };

    // Parse findings for observatory and JSON output
    let findings = parse_findings_json(&report_content).unwrap_or_else(|_| {
        serde_json::json!({"high": [], "medium": [], "low": []})
    });
    let (high, medium, low) = count_findings(&findings);

    observatory::log_event(
        &session_id,
        project_dir,
        ObservatoryEvent::ReviewFindings {
            task_id: format!("pr-review-{}-{}", repo.replace('/', "--"), pr_number),
            high,
            medium,
            low,
            findings_json: serde_json::to_string(&findings).unwrap_or_default(),
        },
    );

    let total_duration_secs = session_start.elapsed().as_secs_f64();

    let output_result = match output_mode {
        ReviewPrOutput::Stdout => {
            println!("{}", report_content);
            Ok(())
        }
        ReviewPrOutput::Json => {
            build_json_output(
                pr_number,
                metadata.changed_files.len(),
                &findings,
                usage.cost_usd,
                total_duration_secs,
            )
            .map(|s| println!("{}", s))
        }
        ReviewPrOutput::Comment => {
            post_pr_comment(pr_number, &repo, &report_content)
        }
    };

    // Observatory: session ended (always runs, even if output failed)
    observatory::log_event(
        &session_id,
        project_dir,
        ObservatoryEvent::SessionEnded {
            total_tasks: 1,
            feat_count: if high == 0 && medium == 0 { 1 } else { 0 },
            wip_count: if high > 0 || medium > 0 { 1 } else { 0 },
            total_cost_usd: usage.cost_usd,
            duration_secs: total_duration_secs,
        },
    );

    let _ = std::fs::remove_dir_all(&buildloop_dir);

    output_result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_output_mode_valid() {
        assert!(matches!(parse_output_mode("stdout").unwrap(), ReviewPrOutput::Stdout));
        assert!(matches!(parse_output_mode("json").unwrap(), ReviewPrOutput::Json));
        assert!(matches!(parse_output_mode("comment").unwrap(), ReviewPrOutput::Comment));
        assert!(matches!(parse_output_mode("JSON").unwrap(), ReviewPrOutput::Json));
    }

    #[test]
    fn test_parse_output_mode_invalid() {
        assert!(parse_output_mode("xml").is_err());
    }

    #[test]
    fn test_count_findings() {
        let findings = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "bad"}],
            "medium": [{"file": "b.rs", "issue": "meh"}, {"file": "c.rs", "issue": "hmm"}],
            "low": []
        });
        assert_eq!(count_findings(&findings), (1, 2, 0));
    }

    #[test]
    fn test_count_findings_empty() {
        let findings = serde_json::json!({});
        assert_eq!(count_findings(&findings), (0, 0, 0));
    }

    #[test]
    fn test_parse_findings_json_extracts_json_fence() {
        let content = "# Review\n\n```json\n{\"high\":[],\"medium\":[],\"low\":[]}\n```\n";
        let result = parse_findings_json(content).unwrap();
        assert_eq!(result, serde_json::json!({"high": [], "medium": [], "low": []}));
    }

    #[test]
    fn test_parse_findings_json_no_fence() {
        let content = "# Review\nNo JSON here.";
        assert!(parse_findings_json(content).is_err());
    }

    #[test]
    fn test_session_id_includes_repo_slug() {
        let repo = "owner/repo-name";
        let pr_number = 42u32;
        let session_id = format!("pr-review-{}-{}", repo.replace('/', "--"), pr_number);
        assert_eq!(session_id, "pr-review-owner--repo-name-42");
    }

    #[test]
    fn test_session_id_different_repos_no_collision() {
        let pr_number = 42u32;
        let repo_a = "alice/project";
        let repo_b = "bob/project";
        let id_a = format!("pr-review-{}-{}", repo_a.replace('/', "--"), pr_number);
        let id_b = format!("pr-review-{}-{}", repo_b.replace('/', "--"), pr_number);
        assert_ne!(id_a, id_b);
        assert_eq!(id_a, "pr-review-alice--project-42");
        assert_eq!(id_b, "pr-review-bob--project-42");
    }

    #[test]
    fn test_session_id_no_ambiguity_with_hyphenated_org() {
        let pr_number = 10u32;
        let repo_a = "alice-org/repo";
        let repo_b = "alice/org-repo";
        let id_a = format!("pr-review-{}-{}", repo_a.replace('/', "--"), pr_number);
        let id_b = format!("pr-review-{}-{}", repo_b.replace('/', "--"), pr_number);
        assert_ne!(id_a, id_b);
        assert_eq!(id_a, "pr-review-alice-org--repo-10");
        assert_eq!(id_b, "pr-review-alice--org-repo-10");
    }

    #[test]
    fn test_setup_temp_buildloop_and_cleanup() {
        let tmp = std::env::temp_dir().join("foundry-test-cleanup");
        std::fs::create_dir_all(&tmp).unwrap();
        let pr_dir = setup_temp_buildloop(&tmp, 99, "owner/repo").unwrap();
        assert!(pr_dir.exists());
        assert!(pr_dir.join("logs").exists());
        // Simulate cleanup
        let _ = std::fs::remove_dir_all(&pr_dir);
        assert!(!pr_dir.exists());
        // Clean up test dir
        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn test_build_json_output_structure() {
        let findings = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "bad"}],
            "medium": [],
            "low": [{"file": "b.rs", "issue": "meh"}]
        });
        let output = build_json_output(42, 5, &findings, 0.15, 30.5).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&output).unwrap();

        assert_eq!(parsed["summary"]["pr_number"], 42);
        assert_eq!(parsed["summary"]["files_reviewed"], 5);
        assert_eq!(parsed["summary"]["findings_high"], 1);
        assert_eq!(parsed["summary"]["findings_medium"], 0);
        assert_eq!(parsed["summary"]["findings_low"], 1);
        assert_eq!(parsed["summary"]["cost_usd"], 0.15);
        assert_eq!(parsed["summary"]["duration_secs"], 30.5);
        assert!(parsed["findings"]["high"].is_array());
    }

    #[test]
    fn test_split_diff_by_file_basic() {
        let diff = "diff --git a/src/foo.rs b/src/foo.rs\nindex abc..def 100644\n--- a/src/foo.rs\n+++ b/src/foo.rs\n@@ -1,3 +1,4 @@\n+added line\n existing\ndiff --git a/src/bar.rs b/src/bar.rs\nindex abc..def 100644\n--- a/src/bar.rs\n+++ b/src/bar.rs\n@@ -1,2 +1,3 @@\n+another";
        let result = split_diff_by_file(diff);
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].0, "src/foo.rs");
        assert_eq!(result[1].0, "src/bar.rs");
        assert!(result[0].1.contains("+added line"));
        assert!(result[1].1.contains("+another"));
    }

    #[test]
    fn test_split_diff_by_file_empty() {
        let result = split_diff_by_file("");
        assert!(result.is_empty());
    }

    #[test]
    fn test_split_diff_by_file_single_file() {
        let diff = "diff --git a/src/only.rs b/src/only.rs\nindex abc..def 100644\n--- a/src/only.rs\n+++ b/src/only.rs\n@@ -1,2 +1,3 @@\n+new line";
        let result = split_diff_by_file(diff);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "src/only.rs");
    }

    #[test]
    fn test_merge_pr_findings_deduplicates() {
        let findings_a = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "bug1"}],
            "medium": [{"file": "b.rs", "issue": "warn1"}],
            "low": []
        });
        let findings_b = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "bug1"}, {"file": "c.rs", "issue": "bug2"}],
            "medium": [],
            "low": [{"file": "d.rs", "issue": "style1"}]
        });
        let merged = merge_pr_findings(&[findings_a, findings_b]);
        assert_eq!(merged["high"].as_array().unwrap().len(), 2); // bug1 deduplicated
        assert_eq!(merged["medium"].as_array().unwrap().len(), 1);
        assert_eq!(merged["low"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_merge_pr_findings_empty() {
        let merged = merge_pr_findings(&[]);
        assert_eq!(merged["high"].as_array().unwrap().len(), 0);
        assert_eq!(merged["medium"].as_array().unwrap().len(), 0);
        assert_eq!(merged["low"].as_array().unwrap().len(), 0);
    }
}

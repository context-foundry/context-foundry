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
            // Flush previous file chunk
            if let Some(file) = current_file.take() {
                result.push((file, current_lines.join("\n")));
                current_lines.clear();
            } else if !current_lines.is_empty() {
                // Previous diff --git had no +++ line (binary file)
                let fallback = extract_path_from_diff_header(&current_lines);
                result.push((fallback, current_lines.join("\n")));
                current_lines.clear();
            }
            // Do NOT extract path here -- wait for +++ b/ line
            current_file = None;
        } else if current_file.is_none() {
            if let Some(path) = line.strip_prefix("+++ b/") {
                current_file = Some(path.to_string());
            } else if line.starts_with("+++ /dev/null") {
                // Deleted file -- fall back to diff --git header
                let fallback = extract_path_from_diff_header(&current_lines);
                current_file = Some(fallback);
            }
        }
        current_lines.push(line);
    }

    // Flush final chunk
    if let Some(file) = current_file {
        if !current_lines.is_empty() {
            result.push((file, current_lines.join("\n")));
        }
    } else if !current_lines.is_empty() {
        // Final chunk had no +++ line (binary file)
        let fallback = extract_path_from_diff_header(&current_lines);
        result.push((fallback, current_lines.join("\n")));
    }

    result
}

/// Extract file path from a diff --git header line as a fallback.
/// Searches the given lines for the first "diff --git" header and uses
/// rsplit(" b/") to extract the path. Only used for binary/deleted files
/// where no "+++ b/" line exists.
fn extract_path_from_diff_header(lines: &[&str]) -> String {
    for line in lines {
        if line.starts_with("diff --git ") {
            let path = line.rsplit(" b/").next().unwrap_or("").to_string();
            if !path.is_empty() {
                return path;
            }
            return line.to_string();
        }
    }
    String::new()
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

    // Deduplicate by (file, issue) pair across all severities.
    // A single shared set ensures a finding reported at HIGH is not
    // also kept if re-reported at MEDIUM or LOW.
    {
        let mut seen: HashSet<(String, String)> = HashSet::new();
        let extract_key = |item: &serde_json::Value| -> (String, String) {
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
            (file, issue)
        };
        // Process high first (highest priority), then medium, then low.
        // First occurrence wins; duplicates at lower severities are removed.
        high_all.retain(|item| seen.insert(extract_key(item)));
        medium_all.retain(|item| seen.insert(extract_key(item)));
        low_all.retain(|item| seen.insert(extract_key(item)));
    }

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

fn replace_findings_in_report(report_content: &str, merged_findings: &serde_json::Value) -> String {
    let merged_json = match serde_json::to_string_pretty(merged_findings) {
        Ok(j) => j,
        Err(_) => return report_content.to_string(),
    };

    let mut result = String::new();
    let mut in_json_block = false;
    let mut replaced = false;

    for line in report_content.lines() {
        if line.trim().starts_with("```json") && !replaced {
            in_json_block = true;
            result.push_str("```json\n");
            result.push_str(&merged_json);
            result.push('\n');
            continue;
        }
        if in_json_block && line.trim().starts_with("```") {
            result.push_str("```\n");
            in_json_block = false;
            replaced = true;
            continue;
        }
        if in_json_block {
            continue;
        }
        result.push_str(line);
        result.push('\n');
    }

    if !replaced {
        result.push_str("\n## All Findings\n\n```json\n");
        result.push_str(&merged_json);
        result.push_str("\n```\n");
    }

    result
}

/// Rewrites the "## Verdict: PASS" or "## Verdict: CONCERNS" line to match the actual
/// merged finding counts. Called after replace_findings_in_report to ensure consistency.
fn rewrite_verdict_line(report_content: &str, high: usize, medium: usize) -> String {
    let new_verdict = if high + medium > 0 {
        "## Verdict: CONCERNS"
    } else {
        "## Verdict: PASS"
    };

    let mut result = String::new();
    for line in report_content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("## Verdict:") {
            result.push_str(new_verdict);
        } else {
            result.push_str(line);
        }
        result.push('\n');
    }
    result
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

fn build_per_file_fallback_report(
    pr_number: u32,
    files_reviewed: usize,
    findings: &serde_json::Value,
) -> String {
    let (high, medium, low) = count_findings(findings);
    let verdict = if high + medium > 0 { "CONCERNS" } else { "PASS" };
    let findings_json = serde_json::to_string_pretty(findings).unwrap_or_default();
    format!(
        "# Foundry PR Review: #{pr_number}\n\n\
         > Integration review agent failed. Results below are from per-file analysis ({files_reviewed} files).\n\n\
         ## Verdict: {verdict}\n\n\
         **Findings:** {high} high, {medium} medium, {low} low\n\n\
         ```json\n{findings_json}\n```\n"
    )
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
) -> (Result<AgentResult>, AgentUsage, serde_json::Value, usize) {
    let file_diffs = split_diff_by_file(diff);
    let diff_map: std::collections::HashMap<&str, &str> = file_diffs
        .iter()
        .map(|(f, d)| (f.as_str(), d.as_str()))
        .collect();

    // Filter out files not in the diff (binary, submodule, rename-limited) or with empty/binary diff content
    let reviewable_files: Vec<&String> = metadata
        .changed_files
        .iter()
        .filter(|file| match diff_map.get(file.as_str()) {
            None => {
                eprintln!(
                    "Skipping {} (not in diff -- binary, submodule, or rename-limited)",
                    file
                );
                false
            }
            Some(diff_content) => {
                let is_binary_diff = diff_content.contains("Binary files ")
                    && diff_content.contains(" differ");
                if diff_content.trim().is_empty() || is_binary_diff {
                    eprintln!("Skipping {} (binary or empty diff)", file);
                    false
                } else {
                    true
                }
            }
        })
        .collect();

    eprintln!(
        "Multi-pass PR review: {}/{} files have reviewable diffs, running per-file analysis",
        reviewable_files.len(),
        metadata.changed_files.len()
    );

    let mut total_usage = AgentUsage::default();
    let mut all_per_file_findings: Vec<serde_json::Value> = Vec::new();
    let mut per_file_success_count: usize = 0;

    for (i, file) in reviewable_files.iter().enumerate() {
        eprintln!(
            "Reviewing file {}/{}: {}",
            i + 1,
            reviewable_files.len(),
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
            per_file_success_count += 1;
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

    if reviewable_files.is_empty() {
        return (
            Err(anyhow!("No reviewable files in PR (all files were binary, submodule, or empty-diff)")),
            total_usage,
            serde_json::Value::Null,
            0,
        );
    }

    if per_file_success_count == 0 {
        return (
            Err(anyhow!(
                "All {} per-file review agents failed -- cannot produce a valid review",
                reviewable_files.len()
            )),
            total_usage,
            serde_json::Value::Null,
            reviewable_files.len(),
        );
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
        Ok(agent_res) => (Ok(agent_res), total_usage, merged_findings, reviewable_files.len()),
        Err(e) => (
            Err(anyhow!("PR review integration agent failed: {}", e)),
            total_usage,
            merged_findings,
            reviewable_files.len(),
        ),
    }
}

// ─── Main Entry Point ────────────────────────────────────────────

pub async fn run(
    project_dir: &Path,
    pr_number: u32,
    repo: Option<String>,
    output: &str,
    ignore_project_config: bool,
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

    let config = if ignore_project_config {
        Config::load_global_only()
    } else {
        Config::load(project_dir)
    };

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

    let (agent_result, usage, per_file_findings, reviewable_file_count) = if use_multipass {
        let (res, usg, pf, reviewable_count) = run_multipass_pr_review(
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
        .await;
        (res, usg, Some(pf), reviewable_count)
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

        (result, usage, None, metadata.changed_files.len())
    };

    if let Err(ref e) = agent_result {
        if let Some(pf_findings) = per_file_findings.filter(|v| v.is_object()) {
            // Integration agent failed but per-file findings exist -- use them
            eprintln!("Integration agent failed: {}. Using per-file findings.", e);

            let (high, medium, low) = count_findings(&pf_findings);

            observatory::log_event(
                &session_id,
                project_dir,
                ObservatoryEvent::ReviewFindings {
                    task_id: format!("pr-review-{}-{}", repo.replace('/', "--"), pr_number),
                    high,
                    medium,
                    low,
                    findings_json: serde_json::to_string(&pf_findings).unwrap_or_default(),
                },
            );

            let total_duration_secs = session_start.elapsed().as_secs_f64();

            let report_content = build_per_file_fallback_report(
                pr_number,
                reviewable_file_count,
                &pf_findings,
            );

            let output_result = match output_mode {
                ReviewPrOutput::Stdout => {
                    println!("{}", report_content);
                    Ok(())
                }
                ReviewPrOutput::Json => {
                    build_json_output(
                        pr_number,
                        reviewable_file_count,
                        &pf_findings,
                        usage.cost_usd,
                        total_duration_secs,
                    )
                    .map(|s| println!("{}", s))
                }
                ReviewPrOutput::Comment => {
                    post_pr_comment(pr_number, &repo, &report_content)
                }
            };

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

            return output_result;
        }

        // No per-file findings available (single-pass failure)
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
            // In multipass mode, per-file findings may be salvageable even if the
            // integration agent succeeded but failed to write review-report.md.
            if let Some(pf_findings) = per_file_findings.filter(|v| v.is_object()) {
                eprintln!("review-report.md missing after agent success. Using per-file findings.");

                let (high, medium, low) = count_findings(&pf_findings);

                observatory::log_event(
                    &session_id,
                    project_dir,
                    ObservatoryEvent::ReviewFindings {
                        task_id: format!("pr-review-{}-{}", repo.replace('/', "--"), pr_number),
                        high,
                        medium,
                        low,
                        findings_json: serde_json::to_string(&pf_findings).unwrap_or_default(),
                    },
                );

                let total_duration_secs = session_start.elapsed().as_secs_f64();

                let report_content = build_per_file_fallback_report(
                    pr_number,
                    reviewable_file_count,
                    &pf_findings,
                );

                let output_result = match output_mode {
                    ReviewPrOutput::Stdout => {
                        println!("{}", report_content);
                        Ok(())
                    }
                    ReviewPrOutput::Json => {
                        build_json_output(
                            pr_number,
                            reviewable_file_count,
                            &pf_findings,
                            usage.cost_usd,
                            total_duration_secs,
                        )
                        .map(|s| println!("{}", s))
                    }
                    ReviewPrOutput::Comment => {
                        post_pr_comment(pr_number, &repo, &report_content)
                    }
                };

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

                return output_result;
            }

            // No per-file findings available (single-pass, or multipass with no valid findings)
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
    let integration_findings = parse_findings_json(&report_content).unwrap_or_else(|_| {
        serde_json::json!({"high": [], "medium": [], "low": []})
    });

    // Merge per-file and integration findings (multipass only)
    let is_multipass = per_file_findings.is_some();
    let findings = if let Some(pf) = per_file_findings {
        merge_pr_findings(&[pf, integration_findings])
    } else {
        integration_findings
    };
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

    // For multipass, replace the JSON findings block in the report with merged findings
    // so stdout and comment outputs include per-file findings, not just integration-only
    let report_content = if is_multipass {
        let merged_report = replace_findings_in_report(&report_content, &findings);
        // Rewrite verdict line to match merged finding counts (D60.1)
        // The integration agent's verdict was based only on its own cross-file findings;
        // after merging per-file findings the verdict may need to change.
        rewrite_verdict_line(&merged_report, high, medium)
    } else {
        report_content
    };

    let output_result = match output_mode {
        ReviewPrOutput::Stdout => {
            println!("{}", report_content);
            Ok(())
        }
        ReviewPrOutput::Json => {
            build_json_output(
                pr_number,
                reviewable_file_count,
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
    fn test_split_diff_by_file_binary() {
        let diff = "diff --git a/image.png b/image.png\nBinary files /dev/null and b/image.png differ\ndiff --git a/src/main.rs b/src/main.rs\nindex abc..def 100644\n--- a/src/main.rs\n+++ b/src/main.rs\n@@ -1,2 +1,3 @@\n+new line";
        let result = split_diff_by_file(diff);
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].0, "image.png");
        assert!(result[0].1.contains("Binary files"));
        assert_eq!(result[1].0, "src/main.rs");
    }

    #[test]
    fn test_split_diff_by_file_path_with_b_segment() {
        let diff = "diff --git a/lib/sub b/file.rs b/lib/sub b/file.rs\nindex abc..def 100644\n--- a/lib/sub b/file.rs\n+++ b/lib/sub b/file.rs\n@@ -1,2 +1,3 @@\n+new line";
        let result = split_diff_by_file(diff);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "lib/sub b/file.rs");
    }

    #[test]
    fn test_split_diff_by_file_deleted_file() {
        let diff = "diff --git a/old.rs b/old.rs\nindex abc..def 100644\n--- a/old.rs\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-deleted line";
        let result = split_diff_by_file(diff);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "old.rs");
        assert!(result[0].1.contains("-deleted line"));
    }

    #[test]
    fn test_split_diff_by_file_mixed_binary_and_text() {
        let diff = "diff --git a/icon.png b/icon.png\nBinary files /dev/null and b/icon.png differ\ndiff --git a/src/lib.rs b/src/lib.rs\nindex abc..def 100644\n--- a/src/lib.rs\n+++ b/src/lib.rs\n@@ -1,2 +1,3 @@\n+line";
        let result = split_diff_by_file(diff);
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].0, "icon.png");
        assert_eq!(result[1].0, "src/lib.rs");
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

    #[test]
    fn test_replace_findings_in_report_replaces_json_block() {
        let report = "# Review\n\n## Verdict: PASS\n\n## Findings\n\n```json\n{\"high\":[],\"medium\":[],\"low\":[]}\n```\n\n## Summary\nLooks good.\n";
        let merged = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "bug", "line": 10}],
            "medium": [],
            "low": []
        });
        let result = replace_findings_in_report(report, &merged);
        // Should contain the merged finding
        assert!(result.contains("\"a.rs\""));
        assert!(result.contains("\"bug\""));
        // Should still contain other prose
        assert!(result.contains("## Verdict: PASS"));
        assert!(result.contains("Looks good."));
        // Should NOT contain the original empty findings
        // (the merged JSON replaces the original block)
        let parsed = parse_findings_json(&result).unwrap();
        assert_eq!(parsed["high"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_replace_findings_in_report_no_json_block() {
        let report = "# Review\n\nNo findings block here.\n";
        let merged = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "bug"}],
            "medium": [],
            "low": []
        });
        let result = replace_findings_in_report(report, &merged);
        // Should append a findings section
        assert!(result.contains("## All Findings"));
        assert!(result.contains("\"a.rs\""));
    }

    #[test]
    fn test_multipass_merge_preserves_per_file_and_integration() {
        // Simulates the merge logic from run()
        let per_file = serde_json::json!({
            "high": [{"file": "auth.rs", "issue": "sql injection"}],
            "medium": [{"file": "api.rs", "issue": "unwrap on input"}],
            "low": []
        });
        let integration = serde_json::json!({
            "high": [],
            "medium": [{"file": "api.rs", "issue": "type mismatch across modules"}],
            "low": [{"file": "lib.rs", "issue": "unused import"}]
        });
        let merged = merge_pr_findings(&[per_file, integration]);
        let (h, m, l) = count_findings(&merged);
        assert_eq!(h, 1); // auth.rs sql injection from per-file
        assert_eq!(m, 2); // unwrap from per-file + type mismatch from integration
        assert_eq!(l, 1); // unused import from integration
    }

    #[test]
    fn test_multipass_merge_deduplicates_shared_findings() {
        // If integration agent re-reports a per-file finding despite instructions,
        // merge_pr_findings deduplicates by (file, issue)
        let per_file = serde_json::json!({
            "high": [{"file": "auth.rs", "issue": "sql injection"}],
            "medium": [],
            "low": []
        });
        let integration = serde_json::json!({
            "high": [{"file": "auth.rs", "issue": "sql injection"}],
            "medium": [],
            "low": []
        });
        let merged = merge_pr_findings(&[per_file, integration]);
        let (h, _m, _l) = count_findings(&merged);
        assert_eq!(h, 1); // deduplicated: same (file, issue) pair
    }

    #[test]
    fn test_rewrite_verdict_pass_to_concerns() {
        let report = "# PR Review\n\n## Verdict: PASS\n\n## Summary\nLooks good.\n\n```json\n{\"high\":[],\"medium\":[],\"low\":[]}\n```\n";
        let result = rewrite_verdict_line(report, 1, 0);
        assert!(result.contains("## Verdict: CONCERNS"));
        assert!(!result.contains("## Verdict: PASS"));
        // Other content preserved
        assert!(result.contains("# PR Review"));
        assert!(result.contains("Looks good."));
    }

    #[test]
    fn test_rewrite_verdict_concerns_stays_concerns() {
        let report = "# PR Review\n\n## Verdict: CONCERNS\n\n## Summary\nIssues found.\n";
        let result = rewrite_verdict_line(report, 2, 1);
        assert!(result.contains("## Verdict: CONCERNS"));
    }

    #[test]
    fn test_rewrite_verdict_concerns_to_pass() {
        let report = "# PR Review\n\n## Verdict: CONCERNS\n\n## Summary\nFalse alarm.\n";
        let result = rewrite_verdict_line(report, 0, 0);
        assert!(result.contains("## Verdict: PASS"));
        assert!(!result.contains("## Verdict: CONCERNS"));
    }

    #[test]
    fn test_rewrite_verdict_no_verdict_line() {
        let report = "# PR Review\n\nNo verdict here.\n";
        let result = rewrite_verdict_line(report, 1, 0);
        // No verdict line to rewrite -- content unchanged (except trailing newline normalization)
        assert!(result.contains("No verdict here."));
        assert!(!result.contains("## Verdict:"));
    }

    #[test]
    fn test_replace_findings_and_rewrite_verdict_combined() {
        // End-to-end: integration agent wrote PASS with empty findings,
        // but per-file review found a HIGH issue. After merge + verdict rewrite,
        // both JSON and verdict should reflect the HIGH finding.
        let integration_report = "# PR Review -- #42: Test PR\n\n## Verdict: PASS\n\n## Summary\nNo cross-file issues.\n\n## Findings\n\n```json\n{\"high\":[],\"medium\":[],\"low\":[]}\n```\n";
        let per_file = serde_json::json!({
            "high": [{"file": "auth.rs", "issue": "sql injection", "line": 10}],
            "medium": [],
            "low": []
        });
        let integration = serde_json::json!({
            "high": [],
            "medium": [],
            "low": []
        });
        let merged = merge_pr_findings(&[per_file, integration]);
        let (high, medium, _low) = count_findings(&merged);

        let after_replace = replace_findings_in_report(integration_report, &merged);
        let final_report = rewrite_verdict_line(&after_replace, high, medium);

        // Verdict should now be CONCERNS
        assert!(final_report.contains("## Verdict: CONCERNS"), "verdict should be CONCERNS after merging per-file HIGH finding");
        assert!(!final_report.contains("## Verdict: PASS"));
        // JSON block should contain the per-file finding
        let parsed = parse_findings_json(&final_report).unwrap();
        assert_eq!(parsed["high"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_build_per_file_fallback_report_concerns() {
        let findings = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "critical bug"}],
            "medium": [],
            "low": [{"file": "b.rs", "issue": "style"}]
        });
        let report = build_per_file_fallback_report(42, 5, &findings);
        assert!(report.contains("# Foundry PR Review: #42"));
        assert!(report.contains("Verdict: CONCERNS"));
        assert!(report.contains("1 high, 0 medium, 1 low"));
        assert!(report.contains("Integration review agent failed"));
        assert!(report.contains("```json"));
    }

    #[test]
    fn test_build_per_file_fallback_report_pass() {
        let findings = serde_json::json!({
            "high": [],
            "medium": [],
            "low": []
        });
        let report = build_per_file_fallback_report(10, 3, &findings);
        assert!(report.contains("Verdict: PASS"));
        assert!(report.contains("0 high, 0 medium, 0 low"));
    }

    #[test]
    fn test_empty_findings_with_zero_successes_detected() {
        // Verify the structural condition: empty findings arrays + 0 success count
        // should be treated as failure, not PASS
        let merged = merge_pr_findings(&[]); // no per-file findings at all
        let (high, medium, low) = count_findings(&merged);
        assert_eq!((high, medium, low), (0, 0, 0));
        // With per_file_success_count == 0 AND these counts, the code now returns Err
        // (tested implicitly through the early return in run_multipass_pr_review)
    }

    #[test]
    fn test_build_per_file_fallback_report_uses_provided_file_count() {
        let findings = serde_json::json!({
            "high": [{"file": "a.rs", "issue": "bad"}],
            "medium": [],
            "low": []
        });
        // Pass 3 as files_reviewed (the reviewable count), not 10 (total changed)
        let report = build_per_file_fallback_report(42, 3, &findings);
        assert!(report.contains("3 files"));
        assert!(report.contains("Verdict: CONCERNS"));
    }

    #[test]
    fn test_build_json_output_reviewable_file_count() {
        let findings = serde_json::json!({"high": [], "medium": [], "low": []});
        let output = build_json_output(42, 7, &findings, 0.10, 15.0).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&output).unwrap();
        assert_eq!(parsed["summary"]["files_reviewed"], 7);
    }
}

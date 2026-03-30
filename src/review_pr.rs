use anyhow::{anyhow, Context as _, Result};
use std::path::{Path, PathBuf};
use std::process::Command;
use tokio::sync::mpsc;

use crate::agent::{self, AgentRole, AgentOutputEvent};
use crate::config::Config;
use crate::observatory::AgentUsage;
use crate::prompts;

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

fn setup_temp_buildloop(project_dir: &Path) -> Result<PathBuf> {
    let buildloop_dir = project_dir.join(".buildloop");
    let log_dir = buildloop_dir.join("logs");
    std::fs::create_dir_all(&log_dir).context("Failed to create .buildloop/logs/")?;
    Ok(buildloop_dir)
}

fn format_as_json(report_content: &str) -> Result<String> {
    let mut in_json_block = false;
    let mut json_lines = Vec::new();

    for line in report_content.lines() {
        if line.trim().starts_with("```json") {
            in_json_block = true;
            continue;
        }
        if in_json_block && line.trim().starts_with("```") {
            // Try to parse what we collected
            let json_str = json_lines.join("\n");
            let value: serde_json::Value = serde_json::from_str(&json_str)
                .context("Failed to parse JSON findings block")?;
            return serde_json::to_string_pretty(&value)
                .context("Failed to format JSON findings");
        }
        if in_json_block {
            json_lines.push(line);
        }
    }

    Err(anyhow!("No valid JSON findings block found in review report"))
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

    let buildloop_dir = setup_temp_buildloop(project_dir)?;
    let log_dir = buildloop_dir.join("logs");
    let review_report = buildloop_dir.join("review-report.md");

    // Remove any existing review-report.md
    let _ = std::fs::remove_file(&review_report);

    let config = Config::load(project_dir);

    let changed_files_str = metadata.changed_files.join("\n");
    let prompt = prompts::pr_review_prompt(
        pr_number,
        &metadata.title,
        &metadata.body,
        &metadata.head_branch,
        &metadata.base_branch,
        &diff,
        &changed_files_str,
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

    agent::run_agent(
        &AgentRole::Reviewer,
        Config::parse_provider(&config.reviewer_provider),
        &config.reviewer_model,
        &prompt,
        project_dir,
        agent_tx,
        &log_dir,
        None,
        config.agent_timeout_secs,
        None,
    )
    .await?;

    let _usage = fwd_handle.await.unwrap_or_default();

    let report_content = std::fs::read_to_string(&review_report)
        .context("Reviewer did not produce review-report.md")?;

    match output_mode {
        ReviewPrOutput::Stdout => {
            println!("{}", report_content);
        }
        ReviewPrOutput::Json => {
            let json = format_as_json(&report_content)?;
            println!("{}", json);
        }
        ReviewPrOutput::Comment => {
            post_pr_comment(pr_number, &repo, &report_content)?;
        }
    }

    Ok(())
}

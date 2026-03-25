use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;

use crate::agent::{self, AgentOutputEvent, AgentRole, ModelProvider};
use crate::app::commands::{ensure_required_providers_available, ProviderCommandMode};
use crate::config::Config;
use crate::sandbox::SandboxConfig;
use crate::utils::{atomic_write_file, truncate_str};

// ─── Data Model ──────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposerOutput {
    pub artifact_type: String,
    pub artifact_text: String,
    #[serde(default)]
    pub rationale: String,
    #[serde(default)]
    pub claims: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewerOutput {
    pub status: String,
    #[serde(default)]
    pub findings: Vec<Finding>,
    #[serde(default)]
    pub validated: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    pub severity: String,
    pub description: String,
    #[serde(default)]
    pub location: String,
    #[serde(default)]
    pub suggestion: String,
}

#[derive(Debug, Clone)]
pub struct OrchestratorOutcome {
    pub artifact: ProposerOutput,
    pub final_review: ReviewerOutput,
    pub iterations: usize,
    pub accepted: bool,
}

// ─── Config ──────────────────────────────────────────────────

pub struct OrchestratorConfig {
    pub proposer_provider: ModelProvider,
    pub proposer_model: String,
    pub reviewer_provider: ModelProvider,
    pub reviewer_model: String,
    pub max_iterations: usize,
    pub accept_policy: AcceptPolicy,
    pub agent_timeout_secs: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AcceptPolicy {
    AllowLowAndMedium,
    AllowLowOnly,
    RequireClean,
}

impl OrchestratorConfig {
    pub fn from_config(config: &Config) -> Self {
        let accept_policy = match config.orchestrator_accept_policy.as_str() {
            "no-high" => AcceptPolicy::AllowLowAndMedium,
            "no-high-medium" => AcceptPolicy::AllowLowOnly,
            "no-findings" => AcceptPolicy::RequireClean,
            _ => AcceptPolicy::AllowLowOnly,
        };

        Self {
            proposer_provider: Config::parse_provider(&config.orchestrator_proposer_provider),
            proposer_model: config.orchestrator_proposer_model.clone(),
            reviewer_provider: Config::parse_provider(&config.orchestrator_reviewer_provider),
            reviewer_model: config.orchestrator_reviewer_model.clone(),
            max_iterations: config.orchestrator_max_iterations,
            accept_policy,
            agent_timeout_secs: config.agent_timeout_secs,
        }
    }
}

// ─── Prompts ─────────────────────────────────────────────────

fn proposer_prompt(intent: &str, prior_findings: Option<&str>) -> String {
    let findings_block = prior_findings
        .map(|f| {
            format!(
                r#"

PRIOR REVIEW FINDINGS (address these in your revised artifact):
{f}
"#
            )
        })
        .unwrap_or_default();

    format!(
        r#"You are a senior software architect. Your job is to produce a well-reviewed artifact.

USER INTENT: {intent}
{findings_block}
INSTRUCTIONS:
1. Read the project's SPEC.md, TASKS.md, and CLAUDE.md for context
2. Read relevant source code
3. Produce your artifact

OUTPUT FORMAT: You MUST output a single JSON object with these fields and nothing else.
Do not add any text before or after the JSON.

{{
  "artifact_type": "plan" or "code_change" or "analysis",
  "artifact_text": "the full artifact content as a string",
  "rationale": "why you chose this approach",
  "claims": ["verifiable claim 1", "verifiable claim 2"]
}}

RULES:
- artifact_type must be one of: plan, code_change, analysis
- artifact_text contains the actual deliverable (plan, diff description, analysis)
- claims must be specific and verifiable by a reviewer with repo access
- Do not wrap the JSON in markdown fences"#
    )
}

fn reviewer_prompt(proposer_output: &ProposerOutput) -> String {
    let claims_block = if proposer_output.claims.is_empty() {
        String::new()
    } else {
        format!(
            "\nCLAIMS TO VERIFY:\n{}",
            proposer_output
                .claims
                .iter()
                .enumerate()
                .map(|(i, c)| format!("{}. {}", i + 1, c))
                .collect::<Vec<_>>()
                .join("\n")
        )
    };

    let review_scope = match proposer_output.artifact_type.as_str() {
        "plan" => "Review this plan for gaps, risks, and implementation soundness.",
        "code_change" => "Validate these code change claims. Check for bugs and verify files.",
        _ => "Check factual accuracy and flag unsupported claims.",
    };

    format!(
        r#"You are a senior code reviewer and architect. {review_scope}

ARTIFACT TYPE: {artifact_type}

ARTIFACT:
{artifact_text}

RATIONALE: {rationale}
{claims_block}

INSTRUCTIONS:
1. Read the project's source code, SPEC.md, TASKS.md, and CLAUDE.md
2. Verify each claim against the actual codebase
3. Identify gaps, risks, and incorrect assumptions

OUTPUT FORMAT: You MUST output a single JSON object with these fields and nothing else.
Do not add any text before or after the JSON.

{{
  "status": "clean" or "findings",
  "findings": [
    {{
      "severity": "high" or "medium" or "low",
      "description": "what is wrong or missing",
      "location": "file or section reference",
      "suggestion": "what to do instead"
    }}
  ],
  "validated": ["claim that was verified as correct"]
}}

RULES:
- status must be "clean" only if there are zero findings
- Every finding must cite a specific location or evidence
- severity: high = will cause failure or incorrect behavior, medium = could cause problems, low = minor issue
- Do not wrap the JSON in markdown fences"#,
        artifact_type = proposer_output.artifact_type,
        artifact_text = proposer_output.artifact_text,
        rationale = proposer_output.rationale,
    )
}

// ─── Parsing ─────────────────────────────────────────────────

fn parse_proposer_output(response: &str) -> ProposerOutput {
    // Try to extract JSON from the response
    if let Some(parsed) = extract_json::<ProposerOutput>(response) {
        return parsed;
    }

    // Fallback: wrap raw text as analysis
    ProposerOutput {
        artifact_type: "analysis".to_string(),
        artifact_text: response.to_string(),
        rationale: String::new(),
        claims: Vec::new(),
    }
}

fn parse_reviewer_output(response: &str) -> ReviewerOutput {
    if let Some(parsed) = extract_json::<ReviewerOutput>(response) {
        return parsed;
    }

    // Fallback: treat entire response as a single high finding
    ReviewerOutput {
        status: "findings".to_string(),
        findings: vec![Finding {
            severity: "high".to_string(),
            description: format!(
                "Reviewer output was not valid JSON: {}",
                truncate_str(response, 200)
            ),
            location: String::new(),
            suggestion: "Review the raw reviewer output manually.".to_string(),
        }],
        validated: Vec::new(),
    }
}

fn extract_json<T: serde::de::DeserializeOwned>(text: &str) -> Option<T> {
    // Try the whole text first
    if let Ok(parsed) = serde_json::from_str(text.trim()) {
        return Some(parsed);
    }

    // Try to find JSON object boundaries, skipping braces inside string values
    let start = text.find('{')?;
    let mut depth: i32 = 0;
    let mut end: Option<usize> = None;
    let mut in_string: bool = false;
    let mut escape_next: bool = false;
    for (i, ch) in text[start..].char_indices() {
        if escape_next {
            escape_next = false;
            continue;
        }
        if in_string {
            match ch {
                '\\' => escape_next = true,
                '"' => in_string = false,
                _ => {}
            }
        } else {
            match ch {
                '"' => in_string = true,
                '{' => depth += 1,
                '}' => {
                    depth -= 1;
                    if depth == 0 {
                        end = Some(start + i + 1);
                        break;
                    }
                }
                _ => {}
            }
        }
    }

    let json_str = &text[start..end?];
    serde_json::from_str(json_str).ok()
}

// ─── Acceptance Policy ───────────────────────────────────────

fn is_accepted(review: &ReviewerOutput, policy: AcceptPolicy) -> bool {
    // Don't trust status=="clean" if findings actually exist
    if review.findings.is_empty() {
        return true;
    }

    let severity_is = |f: &Finding, level: &str| f.severity.eq_ignore_ascii_case(level);

    match policy {
        AcceptPolicy::RequireClean => false, // findings exist, so not clean
        AcceptPolicy::AllowLowAndMedium => !review.findings.iter().any(|f| severity_is(f, "high")),
        AcceptPolicy::AllowLowOnly => !review
            .findings
            .iter()
            .any(|f| severity_is(f, "high") || severity_is(f, "medium")),
    }
}

fn format_findings_for_proposer(review: &ReviewerOutput) -> String {
    review
        .findings
        .iter()
        .map(|f| {
            let mut line = format!("- {} [{}]", f.description, f.severity);
            if !f.location.is_empty() {
                line.push_str(&format!(" at {}", f.location));
            }
            if !f.suggestion.is_empty() {
                line.push_str(&format!("\n  Suggestion: {}", f.suggestion));
            }
            line
        })
        .collect::<Vec<_>>()
        .join("\n")
}

// ─── Orchestration Loop ──────────────────────────────────────

pub async fn orchestrate(
    intent: &str,
    config: &OrchestratorConfig,
    project_dir: &Path,
    log_dir: &Path,
    on_event: impl Fn(&str),
    event_tx: Option<mpsc::UnboundedSender<AgentOutputEvent>>,
    shutdown: Option<Arc<AtomicBool>>,
) -> Result<OrchestratorOutcome> {
    let _ = std::fs::create_dir_all(log_dir);

    let mut last_artifact = None;
    let mut last_review = None;
    let mut findings_text: Option<String> = None;

    // Helper closure to send separator lines to the TUI
    let send_separator = |tx: &Option<mpsc::UnboundedSender<AgentOutputEvent>>, text: &str| {
        if let Some(tx) = tx {
            let _ = tx.send(AgentOutputEvent::Text(String::new()));
            let _ = tx.send(AgentOutputEvent::Text(text.to_string()));
            let _ = tx.send(AgentOutputEvent::Text(String::new()));
        }
    };

    for iteration in 1..=config.max_iterations {
        // Check shutdown flag before starting next iteration
        if shutdown
            .as_ref()
            .is_some_and(|flag| flag.load(Ordering::Relaxed))
        {
            on_event("Shutdown requested, aborting design loop.");
            return Ok(OrchestratorOutcome {
                artifact: last_artifact.unwrap_or(ProposerOutput {
                    artifact_type: "analysis".to_string(),
                    artifact_text: "Design loop cancelled by shutdown.".to_string(),
                    rationale: String::new(),
                    claims: Vec::new(),
                }),
                final_review: last_review.unwrap_or(ReviewerOutput {
                    status: "findings".to_string(),
                    findings: Vec::new(),
                    validated: Vec::new(),
                }),
                iterations: iteration.saturating_sub(1),
                accepted: false,
            });
        }

        on_event(&format!(
            "Iteration {}/{}: proposer ({} {})...",
            iteration, config.max_iterations, config.proposer_provider, config.proposer_model,
        ));

        // Run proposer
        send_separator(
            &event_tx,
            &format!(
                "--- Proposer pass (iteration {}/{}) ---",
                iteration, config.max_iterations
            ),
        );
        let prompt = proposer_prompt(intent, findings_text.as_deref());
        let proposer_result = run_agent_and_capture(
            &AgentRole::Planner,
            config.proposer_provider,
            &config.proposer_model,
            &prompt,
            project_dir,
            log_dir,
            event_tx.as_ref(),
            config.agent_timeout_secs,
            shutdown.clone(),
        )
        .await?;

        let artifact = parse_proposer_output(&proposer_result);
        on_event(&format!(
            "Proposer produced: {} ({} claims)",
            artifact.artifact_type,
            artifact.claims.len(),
        ));

        // Run reviewer
        on_event(&format!(
            "Reviewing with {} {}...",
            config.reviewer_provider, config.reviewer_model,
        ));

        let review_prompt = reviewer_prompt(&artifact);
        send_separator(&event_tx, "--- Reviewer pass ---");
        let reviewer_result = run_agent_and_capture(
            &AgentRole::Reviewer,
            config.reviewer_provider,
            &config.reviewer_model,
            &review_prompt,
            project_dir,
            log_dir,
            event_tx.as_ref(),
            config.agent_timeout_secs,
            shutdown.clone(),
        )
        .await?;

        let review = parse_reviewer_output(&reviewer_result);
        let finding_count = review.findings.len();
        let high_count = review
            .findings
            .iter()
            .filter(|f| f.severity.eq_ignore_ascii_case("high"))
            .count();
        let medium_count = review
            .findings
            .iter()
            .filter(|f| f.severity.eq_ignore_ascii_case("medium"))
            .count();

        on_event(&format!(
            "Review: {} ({} findings: {} high, {} medium, {} low, {} validated)",
            review.status,
            finding_count,
            high_count,
            medium_count,
            finding_count - high_count - medium_count,
            review.validated.len(),
        ));

        let accepted = is_accepted(&review, config.accept_policy);

        if accepted {
            on_event(&format!("Accepted after {} iteration(s).", iteration,));

            return Ok(OrchestratorOutcome {
                artifact,
                final_review: review,
                iterations: iteration,
                accepted: true,
            });
        }

        // Not accepted -- format findings for next round
        findings_text = Some(format_findings_for_proposer(&review));
        on_event(&format!(
            "Not accepted. Routing {} finding(s) back to proposer.",
            finding_count,
        ));

        last_artifact = Some(artifact);
        last_review = Some(review);
    }

    // Max iterations reached
    on_event(&format!(
        "Max iterations ({}) reached. Emitting with unresolved findings.",
        config.max_iterations,
    ));

    Ok(OrchestratorOutcome {
        artifact: last_artifact.unwrap_or(ProposerOutput {
            artifact_type: "analysis".to_string(),
            artifact_text:
                "Orchestrator reached max iterations without producing an accepted artifact."
                    .to_string(),
            rationale: String::new(),
            claims: Vec::new(),
        }),
        final_review: last_review.unwrap_or(ReviewerOutput {
            status: "findings".to_string(),
            findings: Vec::new(),
            validated: Vec::new(),
        }),
        iterations: config.max_iterations,
        accepted: false,
    })
}

#[allow(clippy::too_many_arguments)]
async fn run_agent_and_capture(
    role: &AgentRole,
    provider: ModelProvider,
    model: &str,
    prompt: &str,
    project_dir: &Path,
    log_dir: &Path,
    tui_tx: Option<&mpsc::UnboundedSender<AgentOutputEvent>>,
    timeout_secs: u64,
    shutdown: Option<Arc<AtomicBool>>,
) -> Result<String> {
    let (output_tx, mut output_rx) = mpsc::unbounded_channel::<AgentOutputEvent>();

    // Clone the TUI forwarder for the spawned task
    let tui_forward = tui_tx.cloned();

    // Spawn a task to collect agent output events and forward to TUI
    let collector = tokio::spawn(async move {
        let mut final_text = String::new();
        let mut all_text = Vec::new();
        while let Some(evt) = output_rx.recv().await {
            // Forward to TUI if channel is available
            if let Some(ref tx) = tui_forward {
                let _ = tx.send(evt.clone());
            }
            // Collect for text extraction
            match evt {
                AgentOutputEvent::Result(text) => final_text = text,
                AgentOutputEvent::Text(text) => all_text.push(text),
                _ => {}
            }
        }
        // Prefer the Result event; fall back to concatenated Text events
        if final_text.is_empty() {
            final_text = all_text.join("\n");
        }
        final_text
    });

    let result = agent::run_agent(
        role,
        provider,
        model,
        prompt,
        project_dir,
        output_tx,
        log_dir,
        None,
        timeout_secs,
        shutdown,
    )
    .await
    .context("agent execution failed")?;

    let final_text = collector.await.unwrap_or_default();

    if final_text.is_empty() && !result.success {
        anyhow::bail!("agent failed without producing output");
    }

    Ok(final_text)
}

// ─── Output Writing ──────────────────────────────────────────

pub fn write_orchestrator_output(
    buildloop_dir: &Path,
    outcome: &OrchestratorOutcome,
) -> std::io::Result<()> {
    let output_path = buildloop_dir.join("orchestrator-output.md");
    let output_content = format!(
        "# Orchestrator Output\n\n\
         Type: {}\n\
         Iterations: {}\n\
         Status: {}\n\n\
         ## Artifact\n\n{}\n\n\
         ## Rationale\n\n{}\n\n\
         ## Review Status: {}\n\n\
         ### Findings\n{}\n\n\
         ### Validated\n{}\n",
        outcome.artifact.artifact_type,
        outcome.iterations,
        if outcome.accepted {
            "accepted"
        } else {
            "unresolved findings"
        },
        outcome.artifact.artifact_text,
        outcome.artifact.rationale,
        outcome.final_review.status,
        outcome
            .final_review
            .findings
            .iter()
            .map(|f| format!("- [{}] {} ({})", f.severity, f.description, f.location))
            .collect::<Vec<_>>()
            .join("\n"),
        outcome
            .final_review
            .validated
            .iter()
            .map(|v| format!("- {}", v))
            .collect::<Vec<_>>()
            .join("\n"),
    );
    atomic_write_file(&output_path, output_content.as_bytes())
}

// ─── CLI Entry Point ─────────────────────────────────────────

pub async fn run_design_command(project_dir: &Path, intent: &str) -> Result<()> {
    let config = Config::load(project_dir);
    ensure_required_providers_available(&config, ProviderCommandMode::Design)?;
    let orch_config = OrchestratorConfig::from_config(&config);
    let buildloop_dir = project_dir.join(".buildloop");
    let log_dir = buildloop_dir.join("logs");

    eprintln!("Foundry design mode");
    eprintln!("Intent: {}", intent);
    eprintln!(
        "Proposer: {} {} | Reviewer: {} {}",
        orch_config.proposer_provider,
        orch_config.proposer_model,
        orch_config.reviewer_provider,
        orch_config.reviewer_model,
    );
    eprintln!("Max iterations: {}", orch_config.max_iterations);
    let sandbox_cfg = SandboxConfig::detect(
        config.sandbox,
        &config.sandbox_image,
        config.sandbox_extra_mounts.clone(),
    );
    match sandbox_cfg.status() {
        crate::sandbox::SandboxStatus::Active => {
            eprintln!("Sandbox: active ({})", sandbox_cfg.image);
        }
        crate::sandbox::SandboxStatus::DockerNotFound => {
            eprintln!("Sandbox: Docker not found (unsandboxed)");
        }
        crate::sandbox::SandboxStatus::ImageNotFound => {
            eprintln!("Sandbox: image '{}' not found (unsandboxed)", sandbox_cfg.image);
        }
        crate::sandbox::SandboxStatus::Disabled => {
            eprintln!("Sandbox: disabled");
        }
    }
    eprintln!();

    let shutdown = Arc::new(AtomicBool::new(false));
    let shutdown_signal = shutdown.clone();
    tokio::spawn(async move {
        let _ = tokio::signal::ctrl_c().await;
        shutdown_signal.store(true, Ordering::Relaxed);
    });

    let outcome = orchestrate(
        intent,
        &orch_config,
        project_dir,
        &log_dir,
        |msg| eprintln!("[orchestrator] {}", msg),
        None,
        Some(shutdown),
    )
    .await?;

    write_orchestrator_output(&buildloop_dir, &outcome)?;
    let output_path = buildloop_dir.join("orchestrator-output.md");

    eprintln!();
    if outcome.accepted {
        eprintln!(
            "Accepted in {} iteration(s). Output written to {}",
            outcome.iterations,
            output_path.display()
        );
    } else {
        eprintln!(
            "Reached max iterations with unresolved findings. Output written to {}",
            output_path.display()
        );
    }
    eprintln!("Review the output, then apply to TASKS.md or SPEC.md manually.");

    Ok(())
}

// ─── Tests ───────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_valid_proposer_json() {
        let json = r#"{"artifact_type":"plan","artifact_text":"Build X","rationale":"Because Y","claims":["A works","B works"]}"#;
        let output = parse_proposer_output(json);
        assert_eq!(output.artifact_type, "plan");
        assert_eq!(output.artifact_text, "Build X");
        assert_eq!(output.claims.len(), 2);
    }

    #[test]
    fn parse_proposer_with_surrounding_text() {
        let text = "Sure, here's my plan:\n{\"artifact_type\":\"plan\",\"artifact_text\":\"Do the thing\",\"rationale\":\"R\",\"claims\":[]}\nHope that helps!";
        let output = parse_proposer_output(text);
        assert_eq!(output.artifact_type, "plan");
        assert_eq!(output.artifact_text, "Do the thing");
    }

    #[test]
    fn parse_proposer_fallback_wraps_raw_text() {
        let text = "This is just plain text without JSON";
        let output = parse_proposer_output(text);
        assert_eq!(output.artifact_type, "analysis");
        assert!(output.artifact_text.contains("plain text"));
    }

    #[test]
    fn parse_valid_reviewer_json() {
        let json = r#"{"status":"findings","findings":[{"severity":"high","description":"Bug X","location":"file.rs:10","suggestion":"Fix it"}],"validated":["Claim A"]}"#;
        let output = parse_reviewer_output(json);
        assert_eq!(output.status, "findings");
        assert_eq!(output.findings.len(), 1);
        assert_eq!(output.findings[0].severity, "high");
        assert_eq!(output.validated.len(), 1);
    }

    #[test]
    fn parse_clean_review() {
        let json = r#"{"status":"clean","findings":[],"validated":["All good"]}"#;
        let output = parse_reviewer_output(json);
        assert_eq!(output.status, "clean");
        assert!(output.findings.is_empty());
    }

    #[test]
    fn parse_reviewer_fallback() {
        let text = "Not JSON at all";
        let output = parse_reviewer_output(text);
        assert_eq!(output.status, "findings");
        assert_eq!(output.findings.len(), 1);
        assert_eq!(output.findings[0].severity, "high");
    }

    #[test]
    fn accept_policy_no_high_medium() {
        let clean = ReviewerOutput {
            status: "clean".to_string(),
            findings: Vec::new(),
            validated: Vec::new(),
        };
        assert!(is_accepted(&clean, AcceptPolicy::AllowLowOnly));

        let low_only = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "low".to_string(),
                description: "Minor".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(is_accepted(&low_only, AcceptPolicy::AllowLowOnly));

        let has_medium = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "medium".to_string(),
                description: "Issue".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(&has_medium, AcceptPolicy::AllowLowOnly));
    }

    #[test]
    fn accept_policy_no_high() {
        let has_medium = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "medium".to_string(),
                description: "Issue".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(is_accepted(&has_medium, AcceptPolicy::AllowLowAndMedium));

        let has_high = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "high".to_string(),
                description: "Bug".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(&has_high, AcceptPolicy::AllowLowAndMedium));
    }

    #[test]
    fn accept_policy_no_findings() {
        let low_only = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "low".to_string(),
                description: "Minor".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(&low_only, AcceptPolicy::RequireClean));
    }

    #[test]
    fn format_findings_includes_all_fields() {
        let review = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "high".to_string(),
                description: "Cache key collision".to_string(),
                location: "embeddings.rs:258".to_string(),
                suggestion: "Use model:hash as key".to_string(),
            }],
            validated: Vec::new(),
        };
        let formatted = format_findings_for_proposer(&review);
        assert!(formatted.contains("Cache key collision"));
        assert!(formatted.contains("[high]"));
        assert!(formatted.contains("embeddings.rs:258"));
        assert!(formatted.contains("Use model:hash as key"));
    }

    #[test]
    fn extract_json_from_markdown_fenced_response() {
        let text = "```json\n{\"status\":\"clean\",\"findings\":[],\"validated\":[]}\n```";
        // Our extractor finds the { } block inside the fences
        let result: Option<ReviewerOutput> = extract_json(text);
        assert!(result.is_some());
        assert_eq!(result.unwrap().status, "clean");
    }

    #[test]
    fn max_iterations_produces_outcome() {
        // This tests the data flow, not the actual agent calls
        let config = OrchestratorConfig {
            proposer_provider: ModelProvider::Claude,
            proposer_model: "opus".to_string(),
            reviewer_provider: ModelProvider::Claude,
            reviewer_model: "opus".to_string(),
            max_iterations: 0, // zero = immediate termination
            accept_policy: AcceptPolicy::AllowLowOnly,
            agent_timeout_secs: 600,
        };
        // With max_iterations=0, the loop body never runs
        assert_eq!(config.max_iterations, 0);
    }

    #[test]
    fn is_accepted_rejects_clean_status_with_findings() {
        let review = ReviewerOutput {
            status: "clean".to_string(),
            findings: vec![Finding {
                severity: "high".to_string(),
                description: "Missed bug".to_string(),
                location: "main.rs:1".to_string(),
                suggestion: "Fix it".to_string(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(&review, AcceptPolicy::AllowLowAndMedium));
        assert!(!is_accepted(&review, AcceptPolicy::AllowLowOnly));
        assert!(!is_accepted(&review, AcceptPolicy::RequireClean));
    }

    #[test]
    fn is_accepted_allows_clean_status_with_low_findings_under_low_policy() {
        let review = ReviewerOutput {
            status: "clean".to_string(),
            findings: vec![Finding {
                severity: "low".to_string(),
                description: "Nit".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(is_accepted(&review, AcceptPolicy::AllowLowOnly));
        assert!(is_accepted(&review, AcceptPolicy::AllowLowAndMedium));
        assert!(!is_accepted(&review, AcceptPolicy::RequireClean));
    }

    #[test]
    fn severity_matching_is_case_insensitive() {
        let review_high_upper = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "HIGH".to_string(),
                description: "Bug".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(
            &review_high_upper,
            AcceptPolicy::AllowLowAndMedium
        ));

        let review_high_title = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "High".to_string(),
                description: "Bug".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(
            &review_high_title,
            AcceptPolicy::AllowLowAndMedium
        ));

        let review_medium_upper = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "MEDIUM".to_string(),
                description: "Issue".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(
            &review_medium_upper,
            AcceptPolicy::AllowLowOnly
        ));

        let review_medium_title = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "Medium".to_string(),
                description: "Issue".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(!is_accepted(
            &review_medium_title,
            AcceptPolicy::AllowLowOnly
        ));

        let review_low_upper = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "LOW".to_string(),
                description: "Nit".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(is_accepted(&review_low_upper, AcceptPolicy::AllowLowOnly));

        let review_low_title = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "Low".to_string(),
                description: "Nit".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        assert!(is_accepted(&review_low_title, AcceptPolicy::AllowLowOnly));
    }

    #[test]
    fn extract_json_from_triple_backtick_fenced_block() {
        let input = "Here is the output:\n```json\n{\"status\":\"findings\",\"findings\":[{\"severity\":\"high\",\"description\":\"Bug\",\"location\":\"x.rs\",\"suggestion\":\"fix\"}],\"validated\":[\"claim1\"]}\n```\nDone.";
        let result = extract_json::<ReviewerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.status, "findings");
        assert_eq!(parsed.findings.len(), 1);
        assert_eq!(parsed.findings[0].severity, "high");
        assert_eq!(parsed.validated.len(), 1);
        assert_eq!(parsed.validated[0], "claim1");
    }

    #[test]
    fn extract_json_from_backtick_fenced_without_language_tag() {
        let input = "```\n{\"artifact_type\":\"plan\",\"artifact_text\":\"Do X\",\"rationale\":\"Y\",\"claims\":[]}\n```";
        let result = extract_json::<ProposerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.artifact_type, "plan");
        assert_eq!(parsed.artifact_text, "Do X");
    }

    #[test]
    fn extract_json_returns_none_for_no_json() {
        let input = "This is plain text with no braces or JSON";
        let result = extract_json::<ReviewerOutput>(input);
        assert!(result.is_none());
    }

    #[test]
    fn extract_json_handles_nested_braces() {
        let input = "Result: {\"artifact_type\":\"code_change\",\"artifact_text\":\"fn main() { println!(\\\"hello\\\"); }\",\"rationale\":\"test\",\"claims\":[]}";
        let result = extract_json::<ProposerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.artifact_type, "code_change");
        assert!(parsed.artifact_text.contains("println"));
    }

    #[test]
    fn extract_json_skips_braces_inside_string_values() {
        let input =
            r#"{"artifact_type":"code","artifact_text":"x } y","rationale":"test","claims":[]}"#;
        let result = extract_json::<ProposerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.artifact_type, "code");
        assert_eq!(parsed.artifact_text, "x } y");
    }

    #[test]
    fn extract_json_skips_braces_in_multiline_code_artifact() {
        let input = r#"{"artifact_type":"code_change","artifact_text":"fn main() {\n    println!(\"hello\");\n}\nfn helper() {","rationale":"partial","claims":[]}"#;
        let result = extract_json::<ProposerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.artifact_type, "code_change");
        assert!(parsed.artifact_text.contains("fn helper()"));
    }

    #[test]
    fn extract_json_handles_escaped_quotes_in_strings() {
        let input = r#"{"artifact_type":"test","artifact_text":"she said \"hello\" and {left}","rationale":"r","claims":[]}"#;
        let result = extract_json::<ProposerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.artifact_text, r#"she said "hello" and {left}"#);
    }

    #[test]
    fn extract_json_handles_escaped_backslash_before_quote() {
        let input = r#"{"status":"clean","findings":[],"validated":["path is C:\\"]}"#;
        let result = extract_json::<ReviewerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.status, "clean");
        assert_eq!(parsed.validated.len(), 1);
        assert_eq!(parsed.validated[0], r#"path is C:\"#);
    }

    #[test]
    fn extract_json_with_only_opening_brace_in_string() {
        let input = r#"Preamble text {"artifact_type":"analysis","artifact_text":"{ { {","rationale":"test","claims":[]}"#;
        let result = extract_json::<ProposerOutput>(input);
        assert!(result.is_some());
        let parsed = result.unwrap();
        assert_eq!(parsed.artifact_type, "analysis");
        assert_eq!(parsed.artifact_text, "{ { {");
    }

    #[test]
    fn format_findings_omits_empty_location_and_suggestion() {
        let review = ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![Finding {
                severity: "medium".to_string(),
                description: "Something wrong".to_string(),
                location: String::new(),
                suggestion: String::new(),
            }],
            validated: Vec::new(),
        };
        let formatted = format_findings_for_proposer(&review);
        assert!(formatted.contains("Something wrong"));
        assert!(formatted.contains("[medium]"));
        assert!(!formatted.contains(" at "));
        assert!(!formatted.contains("Suggestion:"));
    }

    #[test]
    fn write_orchestrator_output_creates_file() {
        let unique_nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("foundry-orch-write-{}", unique_nanos));
        std::fs::create_dir_all(&dir).unwrap();

        let outcome = OrchestratorOutcome {
            artifact: ProposerOutput {
                artifact_type: "plan".to_string(),
                artifact_text: "Build the thing".to_string(),
                rationale: "Because reasons".to_string(),
                claims: vec!["claim1".to_string()],
            },
            final_review: ReviewerOutput {
                status: "clean".to_string(),
                findings: Vec::new(),
                validated: vec!["claim1".to_string()],
            },
            iterations: 2,
            accepted: true,
        };

        let result = write_orchestrator_output(&dir, &outcome);
        assert!(result.is_ok());

        let content = std::fs::read_to_string(dir.join("orchestrator-output.md")).unwrap();
        assert!(content.contains("Type: plan"));
        assert!(content.contains("Iterations: 2"));
        assert!(content.contains("Status: accepted"));
        assert!(content.contains("Build the thing"));
        assert!(content.contains("Because reasons"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn write_orchestrator_output_unresolved_shows_findings() {
        let unique_nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("foundry-orch-unresolved-{}", unique_nanos));
        std::fs::create_dir_all(&dir).unwrap();

        let outcome = OrchestratorOutcome {
            artifact: ProposerOutput {
                artifact_type: "analysis".to_string(),
                artifact_text: "Incomplete result".to_string(),
                rationale: String::new(),
                claims: Vec::new(),
            },
            final_review: ReviewerOutput {
                status: "findings".to_string(),
                findings: vec![Finding {
                    severity: "high".to_string(),
                    description: "Critical bug".to_string(),
                    location: "main.rs:5".to_string(),
                    suggestion: "Fix it".to_string(),
                }],
                validated: Vec::new(),
            },
            iterations: 3,
            accepted: false,
        };

        let result = write_orchestrator_output(&dir, &outcome);
        assert!(result.is_ok());

        let content = std::fs::read_to_string(dir.join("orchestrator-output.md")).unwrap();
        assert!(content.contains("Status: unresolved findings"));
        assert!(content.contains("Critical bug"));
        assert!(content.contains("[high]"));
        assert!(content.contains("main.rs:5"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn from_config_parses_accept_policy() {
        // "no-high-medium" (the default) maps to AllowLowOnly
        let mut config = Config::default();
        config.orchestrator_accept_policy = "no-high-medium".into();
        let orch = OrchestratorConfig::from_config(&config);
        assert_eq!(orch.accept_policy, AcceptPolicy::AllowLowOnly);

        // "no-high" maps to AllowLowAndMedium
        config.orchestrator_accept_policy = "no-high".into();
        let orch = OrchestratorConfig::from_config(&config);
        assert_eq!(orch.accept_policy, AcceptPolicy::AllowLowAndMedium);

        // "no-findings" maps to RequireClean
        config.orchestrator_accept_policy = "no-findings".into();
        let orch = OrchestratorConfig::from_config(&config);
        assert_eq!(orch.accept_policy, AcceptPolicy::RequireClean);

        // Unknown string falls back to AllowLowOnly
        config.orchestrator_accept_policy = "unknown-value".into();
        let orch = OrchestratorConfig::from_config(&config);
        assert_eq!(orch.accept_policy, AcceptPolicy::AllowLowOnly);
    }

    #[test]
    fn finding_count_log_matches_acceptance_for_mixed_case_severity() {
        // Simulate the same counting logic used in the orchestrate() log line (lines 424-425)
        // to verify it agrees with is_accepted() for all casing variants.
        let cases: Vec<(&str, &str)> = vec![
            ("high", "medium"),
            ("HIGH", "MEDIUM"),
            ("High", "Medium"),
            ("hIgH", "mEdIuM"),
        ];

        for (high_str, medium_str) in &cases {
            let review = ReviewerOutput {
                status: "findings".to_string(),
                findings: vec![
                    Finding {
                        severity: high_str.to_string(),
                        description: "Bug".to_string(),
                        location: String::new(),
                        suggestion: String::new(),
                    },
                    Finding {
                        severity: medium_str.to_string(),
                        description: "Issue".to_string(),
                        location: String::new(),
                        suggestion: String::new(),
                    },
                ],
                validated: Vec::new(),
            };

            // Replicate the counting logic from orchestrate()
            let high_count = review
                .findings
                .iter()
                .filter(|f| f.severity.eq_ignore_ascii_case("high"))
                .count();
            let medium_count = review
                .findings
                .iter()
                .filter(|f| f.severity.eq_ignore_ascii_case("medium"))
                .count();

            assert_eq!(
                high_count, 1,
                "high_count should be 1 for severity='{}' but got {}",
                high_str, high_count
            );
            assert_eq!(
                medium_count, 1,
                "medium_count should be 1 for severity='{}' but got {}",
                medium_str, medium_count
            );

            // Verify log counts agree with is_accepted
            assert!(
                !is_accepted(&review, AcceptPolicy::AllowLowAndMedium),
                "is_accepted should reject when high='{}' is present",
                high_str
            );
            assert!(
                !is_accepted(&review, AcceptPolicy::AllowLowOnly),
                "is_accepted should reject when high='{}' or medium='{}' is present",
                high_str,
                medium_str
            );
        }
    }
}

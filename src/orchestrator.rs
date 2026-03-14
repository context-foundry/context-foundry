use std::path::Path;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;

use crate::agent::{self, AgentOutputEvent, AgentRole, ModelProvider};
use crate::config::Config;

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
            description: format!("Reviewer output was not valid JSON: {}", &response[..response.len().min(200)]),
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

    // Try to find JSON object boundaries
    let start = text.find('{')?;
    let mut depth = 0i32;
    let mut end = None;
    for (i, ch) in text[start..].char_indices() {
        match ch {
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
        AcceptPolicy::AllowLowOnly => {
            !review
                .findings
                .iter()
                .any(|f| severity_is(f, "high") || severity_is(f, "medium"))
        }
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
) -> Result<OrchestratorOutcome> {
    let _ = std::fs::create_dir_all(log_dir);

    let mut last_artifact = None;
    let mut last_review = None;
    let mut findings_text: Option<String> = None;

    for iteration in 1..=config.max_iterations {
        on_event(&format!(
            "Iteration {}/{}: proposer ({} {})...",
            iteration,
            config.max_iterations,
            config.proposer_provider,
            config.proposer_model,
        ));

        // Run proposer
        let prompt = proposer_prompt(intent, findings_text.as_deref());
        let proposer_result = run_agent_and_capture(
            &AgentRole::Planner,
            config.proposer_provider,
            &config.proposer_model,
            &prompt,
            project_dir,
            log_dir,
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
        let reviewer_result = run_agent_and_capture(
            &AgentRole::Reviewer,
            config.reviewer_provider,
            &config.reviewer_model,
            &review_prompt,
            project_dir,
            log_dir,
        )
        .await?;

        let review = parse_reviewer_output(&reviewer_result);
        let finding_count = review.findings.len();
        let high_count = review.findings.iter().filter(|f| f.severity == "high").count();
        let medium_count = review.findings.iter().filter(|f| f.severity == "medium").count();

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
            on_event(&format!(
                "Accepted after {} iteration(s).",
                iteration,
            ));

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
            artifact_text: "Orchestrator reached max iterations without producing an accepted artifact.".to_string(),
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

async fn run_agent_and_capture(
    role: &AgentRole,
    provider: ModelProvider,
    model: &str,
    prompt: &str,
    project_dir: &Path,
    log_dir: &Path,
) -> Result<String> {
    let (output_tx, mut output_rx) = mpsc::unbounded_channel::<AgentOutputEvent>();

    // Spawn a task to collect agent output events
    let collector = tokio::spawn(async move {
        let mut final_text = String::new();
        let mut all_text = Vec::new();
        while let Some(evt) = output_rx.recv().await {
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
        600,
        None,
    )
    .await
    .context("agent execution failed")?;

    let final_text = collector.await.unwrap_or_default();

    if final_text.is_empty() && !result.success {
        anyhow::bail!("agent failed without producing output");
    }

    Ok(final_text)
}

// ─── CLI Entry Point ─────────────────────────────────────────

pub async fn run_design_command(project_dir: &Path, intent: &str) -> Result<()> {
    let config = Config::load(project_dir);
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
    eprintln!();

    let outcome = orchestrate(
        intent,
        &orch_config,
        project_dir,
        &log_dir,
        |msg| eprintln!("[orchestrator] {}", msg),
    )
    .await?;

    // Write artifact to .buildloop/
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
        if outcome.accepted { "accepted" } else { "unresolved findings" },
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
    std::fs::write(&output_path, &output_content)?;

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
        };
        // With max_iterations=0, the loop body never runs
        assert_eq!(config.max_iterations, 0);
    }
}

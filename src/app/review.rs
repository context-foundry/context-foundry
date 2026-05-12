use std::collections::HashSet;
use std::path::Path;
use std::time::{Duration, Instant};

use tokio::io::AsyncBufReadExt;
use tokio::sync::mpsc;

use crate::agent::{self, AgentOutputEvent, AgentRole};
use crate::budget;
use crate::config::Config;
use crate::eval::stage_id::StageId;
use crate::isolation;
use crate::observatory::{self, AgentUsage, ObservatoryEvent};
use crate::prompts;
use crate::run_manifest::{AgentExitInfo, PromptEvidenceSpec, StageInvocationId, StageStatus};

use super::build::{build_evidence_spec, manifest_exit_info};
use super::commands;
use super::context::RunContext;
use super::{AppEvent, LoopEvent};

const CODEX_REVIEW_REPORT_RELATIVE_PATH: &str = ".buildloop/review-report.md";
const CODEX_DEFAULT_MODEL: &str = "default";

fn detect_codex_version() -> String {
    let output = match std::process::Command::new("codex")
        .arg("--version")
        .output()
    {
        Ok(o) => o,
        Err(_) => return "unknown".to_string(),
    };
    let raw = String::from_utf8_lossy(&output.stdout);
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return "unknown".to_string();
    }
    trimmed
        .strip_prefix("codex-cli ")
        .unwrap_or(trimmed)
        .trim()
        .to_string()
}

fn changed_file_sets_differ(before: &[String], after: &[String]) -> bool {
    let before_set: HashSet<&str> = before.iter().map(String::as_str).collect();
    let after_set: HashSet<&str> = after.iter().map(String::as_str).collect();
    before_set != after_set
}

/// Run a single codex subprocess, streaming stdout/stderr to the TUI.
/// Returns true if the process exited with code 0.
async fn run_codex_subprocess(
    args: &[&str],
    project_dir: &std::path::Path,
    stdin_path: Option<&std::path::Path>,
    timeout_secs: u64,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> bool {
    let mut cmd = tokio::process::Command::new("codex");
    cmd.args(args)
        .current_dir(project_dir)
        .kill_on_drop(true)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());

    match stdin_path {
        Some(path) => match std::fs::File::open(path) {
            Ok(file) => {
                cmd.stdin(std::process::Stdio::from(file));
            }
            Err(e) => {
                let _ = tx.send(AppEvent::AgentOutput(AgentOutputEvent::Stderr(format!(
                    "[codex] failed to open stdin file {}: {e}",
                    path.display()
                ))));
                return false;
            }
        },
        None => {
            cmd.stdin(std::process::Stdio::null());
        }
    }

    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            let _ = tx.send(AppEvent::AgentOutput(AgentOutputEvent::Stderr(format!(
                "[codex] failed to start: {e}"
            ))));
            return false;
        }
    };

    let stdout = child.stdout.take().expect("stdout piped");
    let stderr = child.stderr.take().expect("stderr piped");

    let tx1 = tx.clone();
    let stdout_handle = tokio::spawn(async move {
        let mut lines = tokio::io::BufReader::new(stdout).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = tx1.send(AppEvent::AgentOutput(AgentOutputEvent::Text(line)));
        }
    });

    let tx2 = tx.clone();
    let stderr_handle = tokio::spawn(async move {
        let mut lines = tokio::io::BufReader::new(stderr).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = tx2.send(AppEvent::AgentOutput(AgentOutputEvent::Stderr(format!(
                "[stderr] {line}"
            ))));
        }
    });

    let mut timed_out = false;
    let status = if timeout_secs == 0 {
        child.wait().await
    } else {
        tokio::select! {
            status = child.wait() => status,
            _ = tokio::time::sleep(Duration::from_secs(timeout_secs)) => {
                timed_out = true;
                let _ = tx.send(AppEvent::AgentOutput(AgentOutputEvent::Stderr(
                    format!("[codex] timed out after {}s; terminating subprocess", timeout_secs),
                )));
                if let Err(e) = child.kill().await {
                    let _ = tx.send(AppEvent::AgentOutput(AgentOutputEvent::Stderr(
                        format!("[codex] failed to terminate timed out subprocess: {e}"),
                    )));
                }
                child.wait().await
            }
        }
    };
    let _ = tokio::join!(stdout_handle, stderr_handle);
    !timed_out && status.map(|s| s.success()).unwrap_or(false)
}

/// Doubt stage via Codex: runs `codex exec` (audit + fix) followed by
/// `codex review --uncommitted` (independent diff review). Both write
/// findings to .buildloop/review-report.md. Budget record is always None
/// because Codex does not expose token usage in the same format.
async fn run_codex_doubt(
    task_id: &str,
    _task_desc: &str,
    ctx: &RunContext,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> (
    bool,
    usize,
    (usize, usize, usize),
    Option<budget::PhaseBudgetRecord>,
) {
    let codex_version = detect_codex_version();
    let codex_start = Instant::now();
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Reviewer,
        "Codex Doubt".to_string(),
    )));
    observatory::log_event(
        &ctx.session_id,
        &ctx.project_dir,
        ObservatoryEvent::AgentStarted {
            role: format!("{}", AgentRole::Reviewer),
            provider: "codex".to_string(),
            model: CODEX_DEFAULT_MODEL.to_string(),
            cc_version: codex_version,
        },
    );

    let _ = std::fs::remove_file(&ctx.review_report);
    let pre_files = get_changed_files(&ctx.project_dir);

    let claims_path = ctx.buildloop_dir.join("build-claims.md");

    let audit_prompt = format!(
        "Audit and validate these claims. Find every gap. For each claim in DELTA_MANIFEST \
         verify it against actual code. Report PASS/FAIL/ISSUE for each CHECK in \
         VERIFICATION_MATRIX. Fix every HIGH and MEDIUM issue directly in the code. \
         Write complete findings -- what you checked, what you found, and what you fixed \
         -- to {CODEX_REVIEW_REPORT_RELATIVE_PATH}."
    );

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
        "Codex doubt: running audit + fix pass (codex exec)".to_string(),
    )));

    let exec_ok = run_codex_subprocess(
        &[
            "-a",
            "never",
            "exec",
            "-s",
            "workspace-write",
            "-c",
            "model_reasoning_effort=xhigh",
            &audit_prompt,
        ],
        &ctx.project_dir,
        Some(&claims_path),
        ctx.config.agent_timeout_secs,
        tx,
    )
    .await;

    if !exec_ok {
        let _ = tx.send(AppEvent::AgentDone(false));
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::AgentDone {
                role: format!("{}", AgentRole::Reviewer),
                success: false,
                duration_secs: codex_start.elapsed().as_secs_f64(),
                tokens_in: 0,
                tokens_out: 0,
                cost_usd: 0.0,
                context_pct: 0,
                cache_creation_tokens: 0,
                cache_read_tokens: 0,
            },
        );
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
            task_id: task_id.to_string(),
            fix_passes: 0,
            passed: false,
        }));
        return (false, 0, (0, 0, 0), None);
    }

    let review_prompt = format!(
        "Review for correctness, edge cases, and gaps. Cross-reference \
         .buildloop/build-claims.md for context. Append findings to \
         {CODEX_REVIEW_REPORT_RELATIVE_PATH}."
    );

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
        "Codex doubt: running independent diff review (codex review)".to_string(),
    )));

    // Non-fatal: if codex review fails the exec pass already wrote findings.
    let review_ok = run_codex_subprocess(
        &[
            "-a",
            "never",
            "review",
            "--uncommitted",
            "-c",
            "model_reasoning_effort=xhigh",
            &review_prompt,
        ],
        &ctx.project_dir,
        None,
        ctx.config.agent_timeout_secs,
        tx,
    )
    .await;
    if !review_ok {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Codex doubt: codex review failed; using findings from codex exec".to_string(),
        )));
    }

    let _ = tx.send(AppEvent::AgentDone(true));
    observatory::log_event(
        &ctx.session_id,
        &ctx.project_dir,
        ObservatoryEvent::AgentDone {
            role: format!("{}", AgentRole::Reviewer),
            success: true,
            duration_secs: codex_start.elapsed().as_secs_f64(),
            tokens_in: 0,
            tokens_out: 0,
            cost_usd: 0.0,
            context_pct: 0,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
        },
    );

    let post_files = get_changed_files(&ctx.project_dir);
    let made_fixes = changed_file_sets_differ(&pre_files, &post_files);
    let fix_passes: usize = if made_fixes { 1 } else { 0 };
    if made_fixes {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Codex doubt: applied fixes".to_string(),
        )));
    }

    let report_has_content = ctx.review_report.exists()
        && std::fs::metadata(&ctx.review_report)
            .map(|m| m.len() > 0)
            .unwrap_or(false);

    if !report_has_content {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Codex doubt: review-report.md missing or empty -- treating as failure".to_string(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
            task_id: task_id.to_string(),
            fix_passes,
            passed: false,
        }));
        return (false, fix_passes, (0, 0, 0), None);
    }

    let verdict_pass = check_review_passed(&ctx.review_report);
    let (high, medium, low) = parse_audit_findings(&ctx.review_report);
    {
        let findings_json = std::fs::read_to_string(&ctx.review_report)
            .ok()
            .map(|content| extract_json_from_report(&content))
            .unwrap_or_default();
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::ReviewFindings {
                task_id: task_id.to_string(),
                high,
                medium,
                low,
                findings_json,
            },
        );
    }

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Codex doubt: verdict={}, {} high, {} medium findings",
        if verdict_pass { "PASS" } else { "FAIL" },
        high,
        medium,
    ))));

    let passed = verdict_pass || (high == 0 && medium == 0);
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
        task_id: task_id.to_string(),
        fix_passes,
        passed,
    }));

    (passed, fix_passes, (high, medium, low), None)
}

/// Returns `(passed, fix_passes, (high, medium, low), reviewer_budget_record)` so the caller can persist the pipeline progress indicator.
pub(super) async fn run_review_loop(
    task_id: &str,
    task_desc: &str,
    ctx: &RunContext,
    pattern_context: &str,
    plugin_context: &str,
    tx: &mpsc::UnboundedSender<AppEvent>,
    pattern_ids: &[String],
) -> (
    bool,
    usize,
    (usize, usize, usize),
    Option<budget::PhaseBudgetRecord>,
) {
    let cc_version = ctx.cc_version.clone();
    let files_changed = get_changed_files(&ctx.project_dir);
    if files_changed.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "No changed files to review".to_string(),
        )));
        return (false, 0, (0, 0, 0), None);
    }

    // When diff is too large or not used, enrich the file list with
    // a compact stat summary (+/- lines per file) so the reviewer knows
    // where the bulk of changes are and can read files selectively.
    let files_list = {
        let stat_output = std::process::Command::new("git")
            .args(["diff", "--stat", "HEAD"])
            .current_dir(&ctx.project_dir)
            .output();
        match stat_output {
            Ok(out) if out.status.success() => {
                let stat = String::from_utf8_lossy(&out.stdout);
                if stat.trim().is_empty() {
                    files_changed.join("\n")
                } else {
                    format!(
                        "{}\n\nDiff stat:\n{}",
                        files_changed.join("\n"),
                        stat.trim()
                    )
                }
            }
            _ => files_changed.join("\n"),
        }
    };

    // Determine whether to pass a diff or file list to the reviewer.
    // For large diffs (> 50KB / ~12K tokens), fall back to file list with
    // stat summary so the reviewer reads files selectively instead of
    // consuming context window on a massive inline diff.
    const DIFF_SIZE_LIMIT: usize = 50_000;

    let diff_for_review = if ctx.config.review_mode == "diff-only" {
        let diff = get_diff_for_review(&ctx.project_dir);
        if diff.is_empty() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Diff is empty, falling back to file list for review".to_string(),
            )));
            None
        } else if diff.len() > DIFF_SIZE_LIMIT {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Diff too large ({}KB) -- using file list with stat summary instead",
                diff.len() / 1024,
            ))));
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

    // Run semgrep static analysis if enabled, before the AI review.
    let semgrep_findings = if ctx.config.semgrep_enabled {
        let findings = commands::run_semgrep(
            &ctx.project_dir,
            &ctx.config.semgrep_rulesets,
            &files_changed,
        );
        if findings.is_empty() {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "semgrep: no findings".to_string(),
            )));
        } else {
            let line_count = findings.lines().count().saturating_sub(2); // exclude header/footer
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "semgrep: {} finding(s) injected into reviewer context",
                line_count
            ))));
        }
        findings
    } else {
        String::new()
    };

    // Phase isolation: hide plan and research artifacts from Doubt agent
    let mut phase_guard: Option<isolation::PhaseIsolation> = None;
    if ctx.config.phase_isolation {
        let restricted = isolation::doubt_restricted_paths(&ctx.buildloop_dir);
        match isolation::PhaseIsolation::activate(&restricted) {
            Ok(guard) => {
                let hidden_count = guard.hidden_paths().len();
                if hidden_count > 0 {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Phase isolation: hid {} artifact(s) from reviewer",
                        hidden_count,
                    ))));
                }
                phase_guard = Some(guard);
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Phase isolation: failed to activate -- {}. Continuing without isolation.",
                    e,
                ))));
            }
        }
    }

    // Helper: restore phase isolation with TUI-visible error logging.
    // Called explicitly before every return to avoid relying on Drop's eprintln!.
    let restore_phase_guard = |phase_guard: &mut Option<isolation::PhaseIsolation>,
                               tx: &mpsc::UnboundedSender<AppEvent>| {
        if let Some(mut guard) = phase_guard.take() {
            if let Err(e) = guard.restore() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Phase isolation: restore failed -- {}",
                    e,
                ))));
            }
        }
    };

    // Codex doubt engine: launch Codex as an external process instead of a
    // Claude sub-agent. Configured via doubt_engine = "codex" in .foundry.json
    // or FOUNDRY_DOUBT_ENGINE / DOUBT_ENGINE env vars.
    if ctx.config.doubt_engine == "codex" {
        // codex-doubt evidence is degraded in v1 (no orchestrator-side prompt assembly,
        // no AgentResult). Transcript adapter is v2 priority #1 -- see docs/PLAN_eval-harness.md.
        let codex_doubt_spec = PromptEvidenceSpec {
            stage_id: StageId::Audit,
            role: AgentRole::Reviewer,
            expected_artifact_path: Some(ctx.review_report.clone()),
            originally_configured_provider: "codex".to_string(),
            originally_configured_model: CODEX_DEFAULT_MODEL.to_string(),
            effective_provider: "codex".to_string(),
            effective_model: CODEX_DEFAULT_MODEL.to_string(),
            override_reason: None,
            system_prompt: "",
            user_prompt: "",
            matched_pattern_ids: Vec::new(),
            selected_plugin_names: Vec::new(),
            prior_artifact_paths: Vec::new(),
        };
        let codex_doubt_inv_id: StageInvocationId =
            ctx.manifest.record_invocation(codex_doubt_spec);
        let result = run_codex_doubt(task_id, task_desc, ctx, tx).await;
        // result.0 is the audit verdict (PASS/FAIL of findings), not whether the
        // codex subprocess ran. A FAIL verdict with findings is still a successful
        // invocation -- the agent ran and produced output. Distinguishing
        // "verdict failed" vs "agent crashed" requires extra information that
        // run_codex_doubt does not currently surface in its return tuple, so v1
        // records StageStatus::Ran unconditionally for the placeholder.
        let codex_doubt_status = StageStatus::Ran;
        ctx.manifest.record_exit(
            codex_doubt_inv_id,
            codex_doubt_status,
            chrono::Utc::now(),
            AgentExitInfo {
                log_path: None,
                actual_provider: "codex".to_string(),
                actual_model: CODEX_DEFAULT_MODEL.to_string(),
                fallback_reason: None,
            },
        );
        restore_phase_guard(&mut phase_guard, tx);
        return result;
    }

    // Multi-pass review: when file count exceeds threshold, run per-file
    // analysis passes followed by a cross-file integration pass.
    let threshold = ctx.config.review_multipass_threshold;
    if threshold > 0 && files_changed.len() > threshold {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
            AgentRole::Reviewer,
            Config::display_provider_model(
                &ctx.config.reviewer_provider,
                &ctx.config.reviewer_model,
            ),
        )));
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::AgentStarted {
                role: format!("{}", AgentRole::Reviewer),
                provider: ctx.config.reviewer_provider.clone(),
                model: ctx.config.reviewer_model.clone(),
                cc_version: cc_version.clone(),
            },
        );
        let multipass_start = Instant::now();
        let result = run_multipass_review(
            task_id,
            task_desc,
            ctx,
            pattern_context,
            plugin_context,
            tx,
            &files_changed,
            &files_list,
            diff_for_review.as_deref(),
            &semgrep_findings,
            pattern_ids,
        )
        .await;
        let _ = tx.send(AppEvent::AgentDone(result.0));
        let (passed, fixes, findings, multipass_budget, multipass_usage) = result;
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::AgentDone {
                role: format!("{}", AgentRole::Reviewer),
                success: passed,
                duration_secs: multipass_start.elapsed().as_secs_f64(),
                tokens_in: multipass_usage.tokens_in,
                tokens_out: multipass_usage.tokens_out,
                cost_usd: multipass_usage.cost_usd,
                context_pct: multipass_usage.context_pct,
                cache_creation_tokens: multipass_usage.cache_creation_tokens,
                cache_read_tokens: multipass_usage.cache_read_tokens,
            },
        );
        restore_phase_guard(&mut phase_guard, tx);
        return (passed, fixes, findings, multipass_budget);
    }

    // The reviewer has full write access and fixes issues it finds in a single pass.
    // No separate fixer agent -- the reviewer audits, fixes, re-verifies, and reports.

    if let Err(e) = std::fs::remove_file(&ctx.review_report) {
        if e.kind() != std::io::ErrorKind::NotFound {
            eprintln!("Warning: failed to remove stale review-report.md: {}", e);
        }
    }

    // Snapshot changed files before review so we can detect if reviewer applied fixes.
    let pre_review_files = get_changed_files(&ctx.project_dir);

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    let fwd_handle = tokio::spawn(async move {
        let mut usage = AgentUsage::default();
        while let Some(evt) = agent_rx.recv().await {
            usage.accumulate(&evt);
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
        usage
    });

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Reviewer,
        Config::display_provider_model(&ctx.config.reviewer_provider, &ctx.config.reviewer_model),
    )));
    observatory::log_event(
        &ctx.session_id,
        &ctx.project_dir,
        ObservatoryEvent::AgentStarted {
            role: format!("{}", AgentRole::Reviewer),
            provider: ctx.config.reviewer_provider.clone(),
            model: ctx.config.reviewer_model.clone(),
            cc_version: cc_version.clone(),
        },
    );

    let prompt = prompts::reviewer_prompt(
        task_id,
        task_desc,
        &files_list,
        1,
        pattern_context,
        diff_for_review.as_deref(),
        &ctx.spec_file_prompt_path(),
        &ctx.tasks_file_prompt_path(),
        &semgrep_findings,
    );
    let prompt = prompts::wrap_with_plugins(&prompt, plugin_context);
    if !plugin_context.is_empty() {
        for ext_name in &ctx.config.plugins {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PluginInjected {
                name: ext_name.clone(),
                agent_role: AgentRole::Reviewer.to_string(),
                task_id: task_id.to_string(),
            }));
        }
    }
    let reviewer_spec = build_evidence_spec(
        StageId::Audit,
        AgentRole::Reviewer,
        Some(ctx.review_report.clone()),
        &ctx.config.reviewer_provider,
        &ctx.config.reviewer_model,
        &ctx.config.reviewer_provider,
        &ctx.config.reviewer_model,
        None,
        "",
        &prompt,
        pattern_ids.to_vec(),
        ctx.config.plugins.clone(),
    );
    let reviewer_inv_id: StageInvocationId = ctx.manifest.record_invocation(reviewer_spec);
    let reviewer_start = Instant::now();
    let review_result = agent::run_agent(
        &AgentRole::Reviewer,
        Config::parse_provider(&ctx.config.reviewer_provider),
        &ctx.config.reviewer_model,
        &prompt,
        &ctx.project_dir,
        agent_tx,
        &ctx.log_dir,
        None,
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
        Some(&ctx.config),
    )
    .await;

    let (reviewer_status, reviewer_exit) = manifest_exit_info(
        &review_result,
        &ctx.config.reviewer_provider,
        &ctx.config.reviewer_model,
    );
    ctx.manifest.record_exit(
        reviewer_inv_id,
        reviewer_status,
        chrono::Utc::now(),
        reviewer_exit,
    );

    let agent_usage = fwd_handle.await.unwrap_or_default();
    let _ = tx.send(AppEvent::AgentDone(
        review_result.as_ref().map(|r| r.success).unwrap_or(false),
    ));
    observatory::log_event(
        &ctx.session_id,
        &ctx.project_dir,
        ObservatoryEvent::AgentDone {
            role: format!("{}", AgentRole::Reviewer),
            success: review_result.as_ref().map(|r| r.success).unwrap_or(false),
            duration_secs: reviewer_start.elapsed().as_secs_f64(),
            tokens_in: agent_usage.tokens_in,
            tokens_out: agent_usage.tokens_out,
            cost_usd: agent_usage.cost_usd,
            context_pct: agent_usage.context_pct,
            cache_creation_tokens: agent_usage.cache_creation_tokens,
            cache_read_tokens: agent_usage.cache_read_tokens,
        },
    );
    // Budget telemetry: Reviewer
    let mut reviewer_budget_record: Option<budget::PhaseBudgetRecord> = None;
    if ctx.config.budget_recovery_enabled {
        let record = budget::evaluate_phase(
            &AgentRole::Reviewer,
            &agent_usage,
            &ctx.config.budget_targets,
            ctx.config.budget_overrun_threshold,
        );
        if record.overrun && record.recovery_action != budget::RecoveryAction::Continue {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                phase: format!("{}", AgentRole::Reviewer),
                target_pct: record.target_pct,
                actual_pct: record.actual_pct,
                recovery: format!("{}", record.recovery_action),
            }));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::BudgetOverrun {
                    task_id: task_id.to_string(),
                    phase: format!("{}", AgentRole::Reviewer),
                    target_pct: record.target_pct,
                    actual_pct: record.actual_pct,
                    recovery_action: format!("{}", record.recovery_action),
                },
            );
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Budget overrun: {} used {}% (target {}%), recovery: {} (no subsequent phase)",
                AgentRole::Reviewer,
                record.actual_pct,
                record.target_pct,
                record.recovery_action,
            ))));
        } else if record.overrun {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Budget: {} used {}% (target {}%, within tolerance)",
                AgentRole::Reviewer,
                record.actual_pct,
                record.target_pct,
            ))));
        }
        reviewer_budget_record = Some(record);
    }

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
        restore_phase_guard(&mut phase_guard, tx);
        return (false, 0, (0, 0, 0), reviewer_budget_record);
    }

    // Detect whether the reviewer applied fixes by checking for new file changes.
    let post_review_files = get_changed_files(&ctx.project_dir);
    let reviewer_made_fixes = changed_file_sets_differ(&pre_review_files, &post_review_files);
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
            "Fix agent succeeded but review-report.md is missing or empty — treating as failure"
                .to_string(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
            task_id: task_id.to_string(),
            fix_passes,
            passed: false,
        }));
        restore_phase_guard(&mut phase_guard, tx);
        return (false, fix_passes, (0, 0, 0), reviewer_budget_record);
    }

    let verdict_pass = check_review_passed(&ctx.review_report);
    let (high, medium, low) = parse_audit_findings(&ctx.review_report);
    {
        let findings_json = std::fs::read_to_string(&ctx.review_report)
            .ok()
            .map(|content| extract_json_from_report(&content))
            .unwrap_or_default();
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::ReviewFindings {
                task_id: task_id.to_string(),
                high,
                medium,
                low,
                findings_json,
            },
        );
    }

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Review: verdict={}, {} high, {} medium findings",
        if verdict_pass { "PASS" } else { "FAIL" },
        high,
        medium
    ))));

    let (prov_count, prov_total) = count_provenance_coverage(&ctx.review_report);
    if prov_total > 0 {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Provenance: {}/{} findings have source_evidence",
            prov_count, prov_total
        ))));
    }

    let (conf_count, conf_total) = count_confidence_coverage(&ctx.review_report);
    if conf_total > 0 {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Confidence: {}/{} findings have confidence scores",
            conf_count, conf_total
        ))));
    }

    let low_conf_warnings =
        log_low_confidence_findings(&ctx.review_report, ctx.config.confidence_threshold);
    for warning in &low_conf_warnings {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(warning.clone())));
    }

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

    // Restore hidden artifacts (explicit restore for TUI-visible error reporting)
    restore_phase_guard(&mut phase_guard, tx);

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
        task_id: task_id.to_string(),
        fix_passes,
        passed,
    }));
    (
        passed,
        fix_passes,
        (high, medium, low),
        reviewer_budget_record,
    )
}

#[allow(clippy::too_many_arguments)]
async fn run_multipass_review(
    task_id: &str,
    task_desc: &str,
    ctx: &RunContext,
    pattern_context: &str,
    plugin_context: &str,
    tx: &mpsc::UnboundedSender<AppEvent>,
    files_changed: &[String],
    files_list: &str,
    diff_for_review: Option<&str>,
    semgrep_findings: &str,
    pattern_ids: &[String],
) -> (
    bool,
    usize,
    (usize, usize, usize),
    Option<budget::PhaseBudgetRecord>,
    AgentUsage,
) {
    let cc_version = ctx.cc_version.clone();
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Multi-pass review: {} files exceed threshold ({}), running per-file analysis",
        files_changed.len(),
        ctx.config.review_multipass_threshold,
    ))));

    let mut total_usage = crate::observatory::AgentUsage::default();
    let mut all_per_file_findings: Vec<serde_json::Value> = Vec::new();

    for (i, file) in files_changed.iter().enumerate() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Reviewing file {}/{}: {}",
            i + 1,
            files_changed.len(),
            file,
        ))));

        // Remove stale report before each per-file reviewer.
        if let Err(e) = std::fs::remove_file(&ctx.review_report) {
            if e.kind() != std::io::ErrorKind::NotFound {
                eprintln!(
                    "Warning: failed to remove stale review-report.md before per-file review: {}",
                    e
                );
            }
        }

        let file_diff = get_diff_for_file(&ctx.project_dir, file);
        let prompt = prompts::reviewer_per_file_prompt(
            task_id,
            task_desc,
            file,
            &file_diff,
            &ctx.spec_file_prompt_path(),
            &ctx.tasks_file_prompt_path(),
        );

        // The per-file prompt is NOT plugin-wrapped (only single-pass and
        // integration prompts are). Recording an empty selected_plugin_names
        // makes E1.5's `plugin_loaded` Skip cleanly per the E1.5 spec.
        let per_file_spec = build_evidence_spec(
            StageId::Audit,
            AgentRole::Reviewer,
            Some(ctx.review_report.clone()),
            &ctx.config.reviewer_provider,
            &ctx.config.reviewer_model,
            &ctx.config.reviewer_provider,
            &ctx.config.reviewer_model,
            None,
            "",
            &prompt,
            pattern_ids.to_vec(),
            Vec::new(),
        );
        let per_file_inv_id: StageInvocationId =
            ctx.manifest.record_invocation(per_file_spec);

        let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
        let fwd_tx = tx.clone();
        let fwd_handle = tokio::spawn(async move {
            let mut usage = AgentUsage::default();
            while let Some(evt) = agent_rx.recv().await {
                usage.accumulate(&evt);
                let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
            }
            usage
        });

        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::AgentStarted {
                role: format!("{}", AgentRole::Reviewer),
                provider: ctx.config.reviewer_provider.clone(),
                model: ctx.config.reviewer_model.clone(),
                cc_version: cc_version.clone(),
            },
        );
        let per_file_start = Instant::now();
        let result = agent::run_agent(
            &AgentRole::Reviewer,
            Config::parse_provider(&ctx.config.reviewer_provider),
            &ctx.config.reviewer_model,
            &prompt,
            &ctx.project_dir,
            agent_tx,
            &ctx.log_dir,
            None,
            ctx.config.agent_timeout_secs,
            Some(ctx.shutdown.clone()),
            Some(&ctx.config),
        )
        .await;

        let (per_file_status, per_file_exit) = manifest_exit_info(
            &result,
            &ctx.config.reviewer_provider,
            &ctx.config.reviewer_model,
        );
        ctx.manifest.record_exit(
            per_file_inv_id,
            per_file_status,
            chrono::Utc::now(),
            per_file_exit,
        );

        let agent_usage = fwd_handle.await.unwrap_or_default();
        total_usage.tokens_in += agent_usage.tokens_in;
        total_usage.tokens_out += agent_usage.tokens_out;
        total_usage.cost_usd += agent_usage.cost_usd;
        total_usage.context_pct = total_usage.context_pct.max(agent_usage.context_pct);
        total_usage.cache_creation_tokens += agent_usage.cache_creation_tokens;
        total_usage.cache_read_tokens += agent_usage.cache_read_tokens;
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::AgentDone {
                role: format!("{}", AgentRole::Reviewer),
                success: result.as_ref().map(|r| r.success).unwrap_or(false),
                duration_secs: per_file_start.elapsed().as_secs_f64(),
                tokens_in: agent_usage.tokens_in,
                tokens_out: agent_usage.tokens_out,
                cost_usd: agent_usage.cost_usd,
                context_pct: agent_usage.context_pct,
                cache_creation_tokens: agent_usage.cache_creation_tokens,
                cache_read_tokens: agent_usage.cache_read_tokens,
            },
        );

        if result.as_ref().map(|r| r.success).unwrap_or(false) {
            let findings = parse_findings_from_agent_output(&ctx.review_report);
            all_per_file_findings.push(findings);
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Per-file review failed for {} -- continuing with remaining files",
                file,
            ))));
        }

        if ctx.is_stop_requested() {
            break;
        }
    }

    // Clean up per-file report before integration pass.
    if let Err(e) = std::fs::remove_file(&ctx.review_report) {
        if e.kind() != std::io::ErrorKind::NotFound {
            eprintln!(
                "Warning: failed to remove stale review-report.md before integration pass: {}",
                e
            );
        }
    }

    let merged_per_file = merge_findings(&all_per_file_findings);
    let per_file_findings_json = serde_json::to_string_pretty(&merged_per_file).unwrap_or_default();

    let high_count = merged_per_file
        .get("high")
        .and_then(|v| v.as_array())
        .map(|a| a.len())
        .unwrap_or(0);
    let medium_count = merged_per_file
        .get("medium")
        .and_then(|v| v.as_array())
        .map(|a| a.len())
        .unwrap_or(0);

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Per-file analysis complete. Found {} high, {} medium findings. Running integration review...",
        high_count, medium_count,
    ))));

    // Snapshot pre-review files for fix detection.
    let pre_review_files = get_changed_files(&ctx.project_dir);

    // Build integration prompt.
    let prompt = prompts::reviewer_integration_prompt(
        task_id,
        task_desc,
        files_list,
        &per_file_findings_json,
        pattern_context,
        diff_for_review,
        &ctx.spec_file_prompt_path(),
        &ctx.tasks_file_prompt_path(),
        semgrep_findings,
    );
    let prompt = prompts::wrap_with_plugins(&prompt, plugin_context);

    if !plugin_context.is_empty() {
        for ext_name in &ctx.config.plugins {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::PluginInjected {
                name: ext_name.clone(),
                agent_role: AgentRole::Reviewer.to_string(),
                task_id: task_id.to_string(),
            }));
        }
    }

    let integration_spec = build_evidence_spec(
        StageId::Audit,
        AgentRole::Reviewer,
        Some(ctx.review_report.clone()),
        &ctx.config.reviewer_provider,
        &ctx.config.reviewer_model,
        &ctx.config.reviewer_provider,
        &ctx.config.reviewer_model,
        None,
        "",
        &prompt,
        pattern_ids.to_vec(),
        ctx.config.plugins.clone(),
    );
    let integration_inv_id: StageInvocationId = ctx.manifest.record_invocation(integration_spec);

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    let fwd_handle = tokio::spawn(async move {
        let mut usage = AgentUsage::default();
        while let Some(evt) = agent_rx.recv().await {
            usage.accumulate(&evt);
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
        usage
    });

    observatory::log_event(
        &ctx.session_id,
        &ctx.project_dir,
        ObservatoryEvent::AgentStarted {
            role: format!("{}", AgentRole::Reviewer),
            provider: ctx.config.reviewer_provider.clone(),
            model: ctx.config.reviewer_model.clone(),
            cc_version: cc_version.clone(),
        },
    );
    let integration_start = Instant::now();
    let review_result = agent::run_agent(
        &AgentRole::Reviewer,
        Config::parse_provider(&ctx.config.reviewer_provider),
        &ctx.config.reviewer_model,
        &prompt,
        &ctx.project_dir,
        agent_tx,
        &ctx.log_dir,
        None,
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
        Some(&ctx.config),
    )
    .await;

    let (integration_status, integration_exit) = manifest_exit_info(
        &review_result,
        &ctx.config.reviewer_provider,
        &ctx.config.reviewer_model,
    );
    ctx.manifest.record_exit(
        integration_inv_id,
        integration_status,
        chrono::Utc::now(),
        integration_exit,
    );

    let agent_usage = fwd_handle.await.unwrap_or_default();
    total_usage.tokens_in += agent_usage.tokens_in;
    total_usage.tokens_out += agent_usage.tokens_out;
    total_usage.cost_usd += agent_usage.cost_usd;
    total_usage.context_pct = total_usage.context_pct.max(agent_usage.context_pct);
    total_usage.cache_creation_tokens += agent_usage.cache_creation_tokens;
    total_usage.cache_read_tokens += agent_usage.cache_read_tokens;
    observatory::log_event(
        &ctx.session_id,
        &ctx.project_dir,
        ObservatoryEvent::AgentDone {
            role: format!("{}", AgentRole::Reviewer),
            success: review_result.as_ref().map(|r| r.success).unwrap_or(false),
            duration_secs: integration_start.elapsed().as_secs_f64(),
            tokens_in: agent_usage.tokens_in,
            tokens_out: agent_usage.tokens_out,
            cost_usd: agent_usage.cost_usd,
            context_pct: agent_usage.context_pct,
            cache_creation_tokens: agent_usage.cache_creation_tokens,
            cache_read_tokens: agent_usage.cache_read_tokens,
        },
    );

    if !review_result.as_ref().map(|r| r.success).unwrap_or(false) {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Integration reviewer failed".to_string(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
            task_id: task_id.to_string(),
            fix_passes: 0,
            passed: false,
        }));
        let budget_record = if ctx.config.budget_recovery_enabled {
            Some(budget::evaluate_phase(
                &AgentRole::Reviewer,
                &total_usage,
                &ctx.config.budget_targets,
                ctx.config.budget_overrun_threshold,
            ))
        } else {
            None
        };
        return (false, 0, (0, 0, 0), budget_record, total_usage);
    }

    // Detect if integration reviewer made fixes.
    let post_review_files = get_changed_files(&ctx.project_dir);
    let reviewer_made_fixes =
        post_review_files.len() > pre_review_files.len() || post_review_files != pre_review_files;
    let fix_passes: usize = if reviewer_made_fixes { 1 } else { 0 };

    // Guard: report must exist and have content.
    let report_has_content = ctx.review_report.exists()
        && std::fs::metadata(&ctx.review_report)
            .map(|m| m.len() > 0)
            .unwrap_or(false);

    if !report_has_content {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Integration reviewer succeeded but review-report.md is missing or empty -- treating as failure"
                .to_string(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
            task_id: task_id.to_string(),
            fix_passes,
            passed: false,
        }));
        let budget_record = if ctx.config.budget_recovery_enabled {
            Some(budget::evaluate_phase(
                &AgentRole::Reviewer,
                &total_usage,
                &ctx.config.budget_targets,
                ctx.config.budget_overrun_threshold,
            ))
        } else {
            None
        };
        return (false, fix_passes, (0, 0, 0), budget_record, total_usage);
    }

    let verdict_pass = check_review_passed(&ctx.review_report);
    let (high, medium, low) = parse_audit_findings(&ctx.review_report);
    {
        let findings_json = std::fs::read_to_string(&ctx.review_report)
            .ok()
            .map(|content| extract_json_from_report(&content))
            .unwrap_or_default();
        observatory::log_event(
            &ctx.session_id,
            &ctx.project_dir,
            ObservatoryEvent::ReviewFindings {
                task_id: task_id.to_string(),
                high,
                medium,
                low,
                findings_json,
            },
        );
    }

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
        "Integration review: verdict={}, {} high, {} medium findings",
        if verdict_pass { "PASS" } else { "FAIL" },
        high,
        medium,
    ))));

    let (prov_count, prov_total) = count_provenance_coverage(&ctx.review_report);
    if prov_total > 0 {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Provenance: {}/{} findings have source_evidence",
            prov_count, prov_total
        ))));
    }

    let (conf_count, conf_total) = count_confidence_coverage(&ctx.review_report);
    if conf_total > 0 {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Confidence: {}/{} findings have confidence scores",
            conf_count, conf_total
        ))));
    }

    let low_conf_warnings =
        log_low_confidence_findings(&ctx.review_report, ctx.config.confidence_threshold);
    for warning in &low_conf_warnings {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(warning.clone())));
    }

    let passed = verdict_pass || (high == 0 && medium == 0);

    // Budget telemetry: Reviewer (multipass)
    let reviewer_budget_record: Option<budget::PhaseBudgetRecord> = if ctx
        .config
        .budget_recovery_enabled
    {
        let record = budget::evaluate_phase(
            &AgentRole::Reviewer,
            &total_usage,
            &ctx.config.budget_targets,
            ctx.config.budget_overrun_threshold,
        );
        if record.overrun && record.recovery_action != budget::RecoveryAction::Continue {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BudgetOverrun {
                phase: format!("{}", AgentRole::Reviewer),
                target_pct: record.target_pct,
                actual_pct: record.actual_pct,
                recovery: format!("{}", record.recovery_action),
            }));
            observatory::log_event(
                &ctx.session_id,
                &ctx.project_dir,
                ObservatoryEvent::BudgetOverrun {
                    task_id: task_id.to_string(),
                    phase: format!("{}", AgentRole::Reviewer),
                    target_pct: record.target_pct,
                    actual_pct: record.actual_pct,
                    recovery_action: format!("{}", record.recovery_action),
                },
            );
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Budget overrun: {} (multipass) used {}% (target {}%), recovery: {} (no subsequent phase)",
                AgentRole::Reviewer, record.actual_pct, record.target_pct, record.recovery_action,
            ))));
        } else if record.overrun {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Budget: {} (multipass) used {}% (target {}%, within tolerance)",
                AgentRole::Reviewer,
                record.actual_pct,
                record.target_pct,
            ))));
        }
        Some(record)
    } else {
        None
    };

    if passed {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Multi-pass review passed".to_string(),
        )));
    } else {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Multi-pass review failed: {} high, {} medium unfixed issues remain",
            high, medium,
        ))));
    }

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskReviewResult {
        task_id: task_id.to_string(),
        fix_passes,
        passed,
    }));

    (
        passed,
        fix_passes,
        (high, medium, low),
        reviewer_budget_record,
        total_usage,
    )
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

fn get_diff_for_file(project_dir: &Path, file_path: &str) -> String {
    let output = std::process::Command::new("git")
        .args(["diff", "HEAD", "--", file_path])
        .current_dir(project_dir)
        .output();
    if let Ok(out) = &output {
        if out.status.success() {
            let diff = String::from_utf8_lossy(&out.stdout);
            let trimmed = diff.trim();
            if !trimmed.is_empty() {
                return trimmed.to_string();
            }
        }
    }

    // Fall back to staged-only changes.
    let output = std::process::Command::new("git")
        .args(["diff", "--cached", "--", file_path])
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

fn parse_findings_from_agent_output(report_path: &Path) -> serde_json::Value {
    let content = match std::fs::read_to_string(report_path) {
        Ok(c) => c,
        Err(_) => return serde_json::json!({"high": [], "medium": [], "low": []}),
    };

    let json_str = extract_json_from_report(&content);
    if json_str.is_empty() {
        return serde_json::json!({"high": [], "medium": [], "low": []});
    }

    serde_json::from_str::<serde_json::Value>(&json_str)
        .unwrap_or_else(|_| serde_json::json!({"high": [], "medium": [], "low": []}))
}

fn merge_findings(all_findings: &[serde_json::Value]) -> serde_json::Value {
    let mut high_all: Vec<serde_json::Value> = Vec::new();
    let mut medium_all: Vec<serde_json::Value> = Vec::new();
    let mut low_all: Vec<serde_json::Value> = Vec::new();

    for findings in all_findings {
        for (key, target) in [
            ("high", &mut high_all),
            ("medium", &mut medium_all),
            ("low", &mut low_all),
        ] {
            if let Some(arr) = findings.get(key).and_then(|v| v.as_array()) {
                for finding in arr {
                    target.push(finding.clone());
                }
            }
        }
    }

    // Deduplicate each severity level by (file, issue) pair.
    fn dedup(findings: Vec<serde_json::Value>) -> Vec<serde_json::Value> {
        let mut seen = HashSet::new();
        let mut result = Vec::new();
        for finding in findings {
            let file = finding
                .get("file")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let issue = finding
                .get("issue")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            if seen.insert((file, issue)) {
                result.push(finding);
            }
        }
        result
    }

    high_all = dedup(high_all);
    medium_all = dedup(medium_all);
    low_all = dedup(low_all);

    serde_json::json!({
        "high": high_all,
        "medium": medium_all,
        "low": low_all,
    })
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

/// Count how many findings across all severity levels have source_evidence populated.
/// Returns (with_provenance, total_findings).
fn count_provenance_coverage(report_path: &Path) -> (usize, usize) {
    let content = match std::fs::read_to_string(report_path) {
        Ok(c) => c,
        Err(_) => return (0, 0),
    };

    let json_str = extract_json_from_report(&content);
    if json_str.is_empty() {
        return (0, 0);
    }

    let v: serde_json::Value = match serde_json::from_str(&json_str) {
        Ok(v) => v,
        Err(_) => return (0, 0),
    };

    let mut with_provenance = 0usize;
    let mut total = 0usize;

    for key in &["high", "medium", "low"] {
        if let Some(arr) = v.get(*key).and_then(|a| a.as_array()) {
            for finding in arr {
                total += 1;
                if let Some(ev) = finding.get("source_evidence") {
                    if ev
                        .get("snippet")
                        .and_then(|s| s.as_str())
                        .map(|s| !s.is_empty())
                        .unwrap_or(false)
                        && ev
                            .get("reasoning")
                            .and_then(|s| s.as_str())
                            .map(|s| !s.is_empty())
                            .unwrap_or(false)
                    {
                        with_provenance += 1;
                    }
                }
            }
        }
    }

    (with_provenance, total)
}

/// Parse findings from review report and return log messages for findings
/// below the confidence threshold.
fn log_low_confidence_findings(report_path: &Path, threshold: f64) -> Vec<String> {
    let content = match std::fs::read_to_string(report_path) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };

    let json_str = extract_json_from_report(&content);
    if json_str.is_empty() {
        return Vec::new();
    }

    let v: serde_json::Value = match serde_json::from_str(&json_str) {
        Ok(v) => v,
        Err(_) => return Vec::new(),
    };

    let mut warnings: Vec<String> = Vec::new();

    for key in &["high", "medium", "low"] {
        if let Some(arr) = v.get(*key).and_then(|a| a.as_array()) {
            for finding in arr {
                let confidence = finding
                    .get("confidence")
                    .and_then(|c| c.as_f64())
                    .unwrap_or(1.0);
                if confidence < threshold {
                    let file = finding
                        .get("file")
                        .and_then(|f| f.as_str())
                        .unwrap_or("unknown");
                    let line = finding.get("line").and_then(|l| l.as_u64()).unwrap_or(0);
                    warnings.push(format!(
                        "Low-confidence finding in {}:{} -- consider manual review (confidence: {:.2})",
                        file, line, confidence
                    ));
                }
            }
        }
    }

    warnings
}

/// Count how many findings have a confidence field populated.
/// Returns (with_confidence, total_findings).
fn count_confidence_coverage(report_path: &Path) -> (usize, usize) {
    let content = match std::fs::read_to_string(report_path) {
        Ok(c) => c,
        Err(_) => return (0, 0),
    };

    let json_str = extract_json_from_report(&content);
    if json_str.is_empty() {
        return (0, 0);
    }

    let v: serde_json::Value = match serde_json::from_str(&json_str) {
        Ok(v) => v,
        Err(_) => return (0, 0),
    };

    let mut with_confidence = 0usize;
    let mut total = 0usize;

    for key in &["high", "medium", "low"] {
        if let Some(arr) = v.get(*key).and_then(|a| a.as_array()) {
            for finding in arr {
                total += 1;
                if finding.get("confidence").and_then(|c| c.as_f64()).is_some() {
                    with_confidence += 1;
                }
            }
        }
    }

    (with_confidence, total)
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
        changed_file_sets_differ, check_review_passed, extract_json_from_report, get_changed_files,
        parse_audit_findings,
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

    #[test]
    fn changed_file_sets_differ_ignores_order() {
        let before = vec!["a.rs".to_string(), "b.rs".to_string()];
        let after = vec!["b.rs".to_string(), "a.rs".to_string()];
        assert!(
            !changed_file_sets_differ(&before, &after),
            "file-order churn should not count as a fix pass"
        );
    }

    #[test]
    fn count_provenance_coverage_counts_findings_with_evidence() {
        let dir = temp_dir("foundry-review-provenance");
        let report = dir.join("report.md");
        std::fs::write(&report, r#"# Report
```json
{
  "high": [
    {"file": "a.rs", "line": 1, "issue": "bug", "fixed": true, "category": "logic", "source_evidence": {"snippet": "let x = 1;", "line_range": [1, 1], "reasoning": "x is wrong"}},
    {"file": "b.rs", "line": 2, "issue": "bug2", "fixed": true, "category": "logic"}
  ],
  "medium": [],
  "low": [
    {"file": "c.rs", "line": 3, "issue": "style", "category": "style", "source_evidence": {"snippet": "fn foo()", "line_range": [3, 3], "reasoning": "naming"}}
  ]
}
```
"#).expect("failed to write report");

        let (with_prov, total) = super::count_provenance_coverage(&report);
        assert_eq!(with_prov, 2, "two findings have complete source_evidence");
        assert_eq!(total, 3, "three total findings");

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn count_provenance_coverage_returns_zero_for_missing_file() {
        let path = std::path::PathBuf::from("/tmp/nonexistent-provenance-test.md");
        let (with_prov, total) = super::count_provenance_coverage(&path);
        assert_eq!(with_prov, 0);
        assert_eq!(total, 0);
    }

    #[test]
    fn count_provenance_coverage_rejects_empty_snippet() {
        let dir = temp_dir("foundry-review-provenance-empty");
        let report = dir.join("report.md");
        std::fs::write(&report, r#"# Report
```json
{
  "high": [
    {"file": "a.rs", "line": 1, "issue": "bug", "fixed": true, "category": "logic", "source_evidence": {"snippet": "", "line_range": [1, 1], "reasoning": "x is wrong"}}
  ],
  "medium": [],
  "low": []
}
```
"#).expect("failed to write report");

        let (with_prov, total) = super::count_provenance_coverage(&report);
        assert_eq!(
            with_prov, 0,
            "empty snippet should not count as valid provenance"
        );
        assert_eq!(total, 1);

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn log_low_confidence_findings_returns_warnings_below_threshold() {
        let dir = temp_dir("foundry-review-confidence");
        let report = dir.join("report.md");
        std::fs::write(&report, r#"# Report
```json
{
  "high": [
    {"file": "a.rs", "line": 10, "issue": "real bug", "fixed": true, "category": "logic", "source_evidence": {"snippet": "x", "line_range": [10, 10], "reasoning": "r"}, "confidence": 0.95},
    {"file": "b.rs", "line": 20, "issue": "maybe bug", "fixed": true, "category": "logic", "source_evidence": {"snippet": "y", "line_range": [20, 20], "reasoning": "r"}, "confidence": 0.3}
  ],
  "medium": [
    {"file": "c.rs", "line": 30, "issue": "uncertain", "fixed": true, "category": "error-handling", "source_evidence": {"snippet": "z", "line_range": [30, 30], "reasoning": "r"}, "confidence": 0.45}
  ],
  "low": []
}
```
"#).expect("failed to write report");

        let warnings = super::log_low_confidence_findings(&report, 0.5);
        assert_eq!(
            warnings.len(),
            2,
            "should have 2 low-confidence findings below 0.5"
        );
        assert!(
            warnings[0].contains("b.rs:20"),
            "first warning should mention b.rs:20"
        );
        assert!(
            warnings[1].contains("c.rs:30"),
            "second warning should mention c.rs:30"
        );
        assert!(
            warnings[0].contains("consider manual review"),
            "warning should suggest manual review"
        );

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn log_low_confidence_findings_treats_missing_confidence_as_high() {
        let dir = temp_dir("foundry-review-confidence-missing");
        let report = dir.join("report.md");
        std::fs::write(
            &report,
            r#"# Report
```json
{
  "high": [
    {"file": "a.rs", "line": 10, "issue": "bug", "fixed": true, "category": "logic"}
  ],
  "medium": [],
  "low": []
}
```
"#,
        )
        .expect("failed to write report");

        let warnings = super::log_low_confidence_findings(&report, 0.5);
        assert!(
            warnings.is_empty(),
            "findings without confidence field should default to 1.0 (high confidence)"
        );

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn count_confidence_coverage_counts_findings_with_confidence() {
        let dir = temp_dir("foundry-review-confidence-coverage");
        let report = dir.join("report.md");
        std::fs::write(&report, r#"# Report
```json
{
  "high": [
    {"file": "a.rs", "line": 1, "issue": "bug", "fixed": true, "category": "logic", "confidence": 0.9},
    {"file": "b.rs", "line": 2, "issue": "bug2", "fixed": true, "category": "logic"}
  ],
  "medium": [],
  "low": [
    {"file": "c.rs", "line": 3, "issue": "style", "category": "style", "confidence": 0.4}
  ]
}
```
"#).expect("failed to write report");

        let (with_conf, total) = super::count_confidence_coverage(&report);
        assert_eq!(with_conf, 2, "two findings have confidence scores");
        assert_eq!(total, 3, "three total findings");

        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn count_confidence_coverage_returns_zero_for_missing_file() {
        let path = std::path::PathBuf::from("/tmp/nonexistent-confidence-test.md");
        let (with_conf, total) = super::count_confidence_coverage(&path);
        assert_eq!(with_conf, 0);
        assert_eq!(total, 0);
    }
}

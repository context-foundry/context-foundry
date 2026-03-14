use std::time::Duration;

use tokio::sync::mpsc;

use crate::agent::{self, AgentRole};
use crate::config::Config;
use crate::{
    git, patterns, prompts,
    task::{self, Task},
};

use std::collections::HashMap;
use std::path::PathBuf;

use super::context::RunContext;
use super::{review, AppEvent, LoopEvent};

// ─── State File Backup/Restore ───────────────────────────────
// Scaffold tools (e.g. `npm create vite --overwrite`) can delete
// SPEC.md, TASKS.md, and .buildloop/ during a build. We back up
// critical files before each task and restore them if missing.

struct StateBackup {
    files: HashMap<PathBuf, Vec<u8>>,
}

fn backup_state_files(ctx: &RunContext) -> StateBackup {
    // Critical state files: task queue, spec, build plan, and project conventions.
    // CLAUDE.md is read by every agent; its deletion degrades all agent behavior.
    let critical = [
        ctx.plan_path.clone(),
        ctx.spec_path.clone(),
        ctx.current_plan.clone(),
        ctx.project_dir.join("CLAUDE.md"),
    ];

    let mut files = HashMap::new();
    for path in &critical {
        if let Ok(content) = std::fs::read(path) {
            files.insert(path.clone(), content);
        }
    }
    files.insert(
        ctx.buildloop_dir.clone(),
        Vec::new(), // marker: directory existed
    );
    StateBackup { files }
}

fn restore_state_files(
    ctx: &RunContext,
    backup: &StateBackup,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> usize {
    let mut restored = 0;

    // Ensure .buildloop dir exists
    if !ctx.buildloop_dir.exists() {
        let _ = std::fs::create_dir_all(&ctx.buildloop_dir);
        let _ = std::fs::create_dir_all(&ctx.log_dir);
    }

    // Files where truncation (exists but empty/tiny) should also trigger restore.
    // Excludes current_plan which is legitimately deleted and rewritten each task.
    let truncation_protected = [&ctx.plan_path, &ctx.spec_path];

    for (path, content) in &backup.files {
        // Skip the directory marker and empty backups
        if *path == ctx.buildloop_dir || content.is_empty() {
            continue;
        }

        let needs_restore = if !path.exists() {
            true
        } else if truncation_protected.contains(&path) {
            // Detect truncation: file exists but is much smaller than backup
            let current_size = std::fs::metadata(path).map(|m| m.len()).unwrap_or(0);
            current_size < 10 && content.len() > 10
        } else {
            false
        };

        if needs_restore {
            if let Some(parent) = path.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            match std::fs::write(path, content) {
                Ok(()) => restored += 1,
                Err(e) => {
                    let name = path.file_name().unwrap_or_default().to_string_lossy();
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                        "Warning: failed to restore {}: {}",
                        name, e
                    ))));
                }
            }
        }
    }

    restored
}

pub(super) async fn build_loop(ctx: RunContext, tx: mpsc::UnboundedSender<AppEvent>) {
    ctx.ensure_runtime_dirs();

    let mut discovery_round: usize = 0;

    loop {
        let tasks = match task::parse_tasks(&ctx.plan_path) {
            Ok(t) => t,
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Failed to parse {}: {}",
                    ctx.tasks_file_name(),
                    e
                ))));
                tokio::time::sleep(Duration::from_secs(5)).await;
                continue;
            }
        };

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
            task::count_completed(&tasks),
            tasks.len(),
        )));
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::QueueUpdated(tasks.clone())));

        let next = task::next_pending(&tasks).cloned();

        if let Some(task_info) = next {
            let queue_next = task::nth_pending(&tasks, 1)
                .map(|task| format!("{} — {}", task.id, task.short_desc(72)));
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::NextTaskUpdated(queue_next)));

            // Backup state files before the builder runs -- scaffold tools
            // with --overwrite can delete everything in the project root.
            let state_backup = backup_state_files(&ctx);

            let success = process_task(&task_info, &ctx, &tx).await;

            // Restore state files if the builder deleted or truncated them
            let restored = restore_state_files(&ctx, &state_backup, &tx);
            if restored > 0 {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Restored {} state file(s) deleted during build",
                    restored
                ))));
            }

            if success {
                let _ = task::mark_done(&ctx.plan_path, task_info.line_number);
            }

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskCompleted(
                task_info.id.clone(),
                success,
            )));

            if let Ok(tasks) = task::parse_tasks(&ctx.plan_path) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
                    task::count_completed(&tasks),
                    tasks.len(),
                )));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::QueueUpdated(tasks)));
            }

            let stop_file = ctx.stop_file();
            if stop_file.exists() {
                let _ = std::fs::remove_file(stop_file);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_tasks_secs)).await;
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::NextTaskUpdated(None)));
            discovery_round += 1;

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryStarted));

            let pre_count = tasks.len();

            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            tokio::spawn(async move {
                while let Some(evt) = agent_rx.recv().await {
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Discovery,
                Config::display_provider_model(
                    &ctx.config.discovery_provider,
                    &ctx.config.discovery_model,
                ),
            )));

            let prompt = prompts::discovery_prompt(
                discovery_round,
                &ctx.spec_file_name(),
                &ctx.tasks_file_name(),
            );
            let result = agent::run_agent(
                &AgentRole::Discovery,
                Config::parse_provider(&ctx.config.discovery_provider),
                &ctx.config.discovery_model,
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
                result.as_ref().map(|r| r.success).unwrap_or(false),
            ));

            let new_tasks = match task::parse_tasks(&ctx.plan_path) {
                Ok(t) => t.len().saturating_sub(pre_count),
                Err(_) => 0,
            };

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryCompleted(
                new_tasks,
            )));

            if new_tasks == 0 {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "No new tasks found — waiting before next scan...".to_string(),
                )));
                tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_cycles_secs)).await;
            } else {
                let _ = git::commit_and_push(
                    &ctx.project_dir,
                    &ctx.config,
                    &format!("D{}", discovery_round),
                    &format!(
                        "Discovery round {} — {} new tasks",
                        discovery_round, new_tasks
                    ),
                    false,
                );
            }

            if let Ok(tasks) = task::parse_tasks(&ctx.plan_path) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
                    task::count_completed(&tasks),
                    tasks.len(),
                )));
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::QueueUpdated(tasks)));
            }
        }
    }
}

async fn process_task(
    task_info: &Task,
    ctx: &RunContext,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> bool {
    let task_id = &task_info.id;
    let task_desc = &task_info.description;
    let patterns_extracted = ctx.buildloop_dir.join("patterns-extracted.json");

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskStarted(
        task_info.clone(),
    )));

    let _ = std::fs::remove_file(&ctx.current_plan);
    let _ = std::fs::remove_file(&ctx.review_report);
    let _ = std::fs::remove_file(&patterns_extracted);

    let patterns_dir = patterns::resolve_patterns_dir(&ctx.config.patterns_dir);
    let all_patterns = patterns::load_patterns(&patterns_dir);

    let matched = if ctx.config.semantic_match_enabled {
        let keyword_scores = patterns::keyword_scores(&all_patterns, task_desc);
        let (scored, result) = crate::embeddings::match_patterns_semantic(
            &all_patterns,
            task_desc,
            &ctx.config.embedding_model,
            ctx.config.embedding_timeout_ms,
            &keyword_scores,
        )
        .await;
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Pattern matching ({}): cache {}/{} hit",
            result.mode, result.cache_hits, result.cache_hits + result.cache_misses
        ))));
        scored.into_iter().map(|(p, _)| p).collect::<Vec<_>>()
    } else {
        patterns::match_patterns(&all_patterns, task_desc)
    };

    let pattern_context =
        patterns::format_patterns_for_prompt(&matched, "planner", ctx.config.max_pattern_injection);

    if !matched.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Matched {} patterns for task",
            matched.len()
        ))));
    }

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Planner,
        Config::display_provider_model(&ctx.config.planner_provider, &ctx.config.planner_model),
    )));

    let prompt = prompts::planner_prompt(
        task_id,
        task_desc,
        &pattern_context,
        &ctx.spec_file_name(),
        &ctx.tasks_file_name(),
    );
    let plan_result = agent::run_agent(
        &AgentRole::Planner,
        Config::parse_provider(&ctx.config.planner_provider),
        &ctx.config.planner_model,
        &prompt,
        &ctx.project_dir,
        agent_tx,
        &ctx.log_dir,
        None,
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
    )
    .await;

    let plan_ok = plan_result.map(|r| r.success).unwrap_or(false);
    let _ = tx.send(AppEvent::AgentDone(plan_ok));

    if !plan_ok || !ctx.current_plan.exists() {
        let committed =
            git::commit_and_push(&ctx.project_dir, &ctx.config, task_id, task_desc, true)
                .unwrap_or(false);
        let message = if committed {
            format!("PLANNER failed for {} — committed WIP changes", task_id)
        } else {
            format!(
                "PLANNER failed for {} — no repository changes to commit",
                task_id
            )
        };
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(message)));
        return false;
    }

    tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_agents_secs)).await;

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Builder,
        Config::display_provider_model(&ctx.config.builder_provider, &ctx.config.builder_model),
    )));

    let prompt = prompts::builder_prompt(
        task_id,
        task_desc,
        &ctx.spec_file_name(),
        &ctx.tasks_file_name(),
    );
    let build_result = agent::run_agent(
        &AgentRole::Builder,
        Config::parse_provider(&ctx.config.builder_provider),
        &ctx.config.builder_model,
        &prompt,
        &ctx.project_dir,
        agent_tx,
        &ctx.log_dir,
        None,
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
    )
    .await;

    let build_ok = build_result.map(|r| r.success).unwrap_or(false);
    let _ = tx.send(AppEvent::AgentDone(build_ok));

    if !build_ok {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "BUILDER failed for {} — committing WIP",
            task_id
        ))));
        let _ = git::commit_and_push(&ctx.project_dir, &ctx.config, task_id, task_desc, true);
        return false;
    }

    tokio::time::sleep(Duration::from_secs(ctx.config.pause_between_agents_secs)).await;

    let validated = if ctx.config.backpressure_only {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Backpressure-only mode: skipping LLM review (builder verification passed)".to_string(),
        )));
        true
    } else {
        let reviewer_pattern_context = patterns::format_patterns_for_prompt(
            &matched,
            "reviewer",
            ctx.config.max_pattern_injection,
        );
        review::run_review_loop(task_id, task_desc, ctx, &reviewer_pattern_context, tx).await
    };

    let committed = git::commit_and_push(
        &ctx.project_dir,
        &ctx.config,
        task_id,
        task_desc,
        !validated,
    )
    .unwrap_or(false);

    if committed {
        let prefix = if validated { "feat" } else { "WIP" };
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Committed {}({})",
            prefix, task_id
        ))));
    }

    if validated {
        // Fire-and-forget: pattern extraction runs in the background so the
        // loop can start the next task immediately.  It writes to a separate
        // patterns directory, not to the source tree, so there is no conflict.
        let bg_task_id = task_id.to_string();
        let bg_task_desc = task_desc.to_string();
        let bg_ctx = ctx.clone();
        let bg_patterns_dir = patterns_dir.clone();
        let bg_patterns_extracted = patterns_extracted.clone();
        let bg_tx = tx.clone();
        tokio::spawn(async move {
            tokio::time::sleep(Duration::from_secs(bg_ctx.config.pause_between_agents_secs)).await;
            run_pattern_extraction(
                &bg_task_id,
                &bg_task_desc,
                &bg_ctx,
                &bg_patterns_dir,
                &bg_patterns_extracted,
                &bg_tx,
            )
            .await;
            let _ = std::fs::remove_file(&bg_patterns_extracted);
        });
    }

    if should_restart_docker(task_desc) {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Restarting Docker services...".to_string(),
        )));
        let _ = std::process::Command::new("docker")
            .args(["compose", "down"])
            .current_dir(&ctx.project_dir)
            .output();
        let _ = std::process::Command::new("docker")
            .args(["compose", "up", "-d", "--build"])
            .current_dir(&ctx.project_dir)
            .output();
    }

    validated
}

async fn run_pattern_extraction(
    task_id: &str,
    task_desc: &str,
    ctx: &RunContext,
    patterns_dir: &std::path::Path,
    patterns_extracted: &std::path::Path,
    tx: &mpsc::UnboundedSender<AppEvent>,
) {
    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let model = &ctx.config.discovery_model;
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Discovery,
        Config::display_provider_model(&ctx.config.discovery_provider, model),
    )));
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
        "Extracting patterns from build artifacts...".to_string(),
    )));

    let prompt = prompts::pattern_extraction_prompt(task_id, task_desc);
    let result = agent::run_agent(
        &AgentRole::Discovery,
        Config::parse_provider(&ctx.config.discovery_provider),
        model,
        &prompt,
        &ctx.project_dir,
        agent_tx,
        &ctx.log_dir,
        Some(&["Read", "Write"]),
        600,
        Some(ctx.shutdown.clone()),
    )
    .await;

    let _ = tx.send(AppEvent::AgentDone(
        result.as_ref().map(|r| r.success).unwrap_or(false),
    ));

    if patterns_extracted.exists() {
        match patterns::extract_patterns_from_file(patterns_extracted) {
            Ok(new_patterns) if !new_patterns.is_empty() => {
                match patterns::merge_patterns(patterns_dir, new_patterns) {
                    Ok(added) => {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Merged patterns: {} new added to {}",
                            added,
                            patterns_dir.display()
                        ))));
                    }
                    Err(e) => {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                            "Failed to merge patterns: {}",
                            e
                        ))));
                    }
                }
            }
            Ok(_) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "No patterns extracted for this task".to_string(),
                )));
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Failed to parse extracted patterns: {}",
                    e
                ))));
            }
        }
    }
}

fn should_restart_docker(task_desc: &str) -> bool {
    let lower = task_desc.to_lowercase();
    lower.contains("docker")
        || lower.contains("compose")
        || lower.contains("dockerfile")
        || lower.contains("caddy")
        || lower.contains("integration")
        || lower.contains("scaffold")
}

#[cfg(test)]
mod tests {
    use super::should_restart_docker;

    #[test]
    fn should_restart_docker_matches_expected_keywords() {
        assert!(should_restart_docker("Update docker compose stack"));
        assert!(should_restart_docker("Fix caddy integration issue"));
        assert!(should_restart_docker("Scaffold local environment"));
        assert!(!should_restart_docker("Refactor auth callback parser"));
    }
}

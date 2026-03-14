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
use crate::utils::atomic_write_file;

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
            match atomic_write_file(path, content) {
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

    let mut discovery_round: usize = task::highest_discovery_round(&ctx.plan_path);

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
                let _lock = ctx.tasks_file_lock.lock().unwrap_or_else(|e| e.into_inner());
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

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryStarted(discovery_round)));

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

            // Check stop after discovery agent completion
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Stop requested after DISCOVERY agent — shutting down".to_string(),
                )));
                let stop_file = ctx.stop_file();
                if stop_file.exists() {
                    let _ = std::fs::remove_file(stop_file);
                }
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

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
                // Check stop after inter-cycle sleep
                if ctx.is_stop_requested() {
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                        "Stop requested during discovery pause — shutting down".to_string(),
                    )));
                    let stop_file = ctx.stop_file();
                    if stop_file.exists() {
                        let _ = std::fs::remove_file(stop_file);
                    }
                    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                    return;
                }
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

            // Check stop after discovery commit
            if ctx.is_stop_requested() {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "Stop requested after discovery commit — shutting down".to_string(),
                )));
                let stop_file = ctx.stop_file();
                if stop_file.exists() {
                    let _ = std::fs::remove_file(stop_file);
                }
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
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

    // Check stop between planner and builder
    if ctx.is_stop_requested() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Stop requested after PLANNER for {} — skipping remaining stages",
            task_id
        ))));
        let _ = git::commit_and_push(&ctx.project_dir, &ctx.config, task_id, task_desc, true);
        return false;
    }

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

    // Check stop between builder and reviewer
    if ctx.is_stop_requested() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Stop requested after BUILDER for {} — skipping review",
            task_id
        ))));
        let _ = git::commit_and_push(&ctx.project_dir, &ctx.config, task_id, task_desc, true);
        return false;
    }

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
    let (agent_tx, _agent_rx) = mpsc::unbounded_channel();

    let model = &ctx.config.discovery_model;
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
        format!(
            "Background pattern extraction started ({})",
            Config::display_provider_model(&ctx.config.discovery_provider, model),
        ),
    )));
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
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
        ctx.config.agent_timeout_secs,
        Some(ctx.shutdown.clone()),
    )
    .await;

    let success = result.as_ref().map(|r| r.success).unwrap_or(false);
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
        format!(
            "Background pattern extraction {}",
            if success { "completed" } else { "failed" },
        ),
    )));

    if patterns_extracted.exists() {
        match patterns::extract_patterns_from_file(patterns_extracted) {
            Ok(new_patterns) if !new_patterns.is_empty() => {
                match patterns::merge_patterns(patterns_dir, new_patterns) {
                    Ok(added) => {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                            "Merged patterns: {} new added to {}",
                            added,
                            patterns_dir.display()
                        ))));
                    }
                    Err(e) => {
                        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                            "Failed to merge patterns: {}",
                            e
                        ))));
                    }
                }
            }
            Ok(_) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(
                    "No patterns extracted for this task".to_string(),
                )));
            }
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::BackgroundLog(format!(
                    "Failed to parse extracted patterns: {}",
                    e
                ))));
            }
        }
    }
}

fn should_restart_docker(task_desc: &str) -> bool {
    let lower = task_desc.to_lowercase();
    let has_docker_word = lower.contains("docker")
        || lower.contains("dockerfile")
        || lower.contains("caddy");
    if has_docker_word {
        return true;
    }
    let infra_qualifiers = ["docker", "container", "service", "environment"];
    let broad_keywords = ["integration", "scaffold", "compose"];
    for kw in &broad_keywords {
        if lower.contains(kw) {
            for qual in &infra_qualifiers {
                if lower.contains(qual) {
                    return true;
                }
            }
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::should_restart_docker;
    use super::{backup_state_files, restore_state_files};
    use crate::app::context::RunContext;
    use crate::app::state::{AppEvent, LoopEvent};
    use crate::config::Config;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::{Arc, Mutex};
    use tokio::sync::mpsc;

    #[test]
    fn should_restart_docker_matches_expected_keywords() {
        // Primary Docker keywords -- always trigger
        assert!(should_restart_docker("Update docker compose stack"));
        assert!(should_restart_docker("Fix Dockerfile build stage"));
        assert!(should_restart_docker("Update caddy reverse proxy"));

        // Broad keywords WITH infrastructure qualifier -- trigger
        assert!(should_restart_docker("Fix caddy integration issue"));
        assert!(should_restart_docker("Scaffold docker environment"));
        assert!(should_restart_docker("Scaffold container setup"));
        assert!(should_restart_docker("Integration service config"));
        assert!(should_restart_docker("Rebuild compose services"));
        assert!(should_restart_docker("Compose container networking"));
        assert!(should_restart_docker("Update compose docker config"));

        // Broad keywords WITHOUT infrastructure qualifier -- do NOT trigger
        assert!(!should_restart_docker("Add integration tests"));
        assert!(!should_restart_docker("Scaffold test fixtures"));
        assert!(!should_restart_docker("Scaffold auth module"));
        assert!(!should_restart_docker("Fix integration callback parser"));
        assert!(!should_restart_docker("Compose validation error messages"));
        assert!(!should_restart_docker("Compose a response template"));

        // Unrelated tasks -- do NOT trigger
        assert!(!should_restart_docker("Refactor auth callback parser"));
        assert!(!should_restart_docker("Add unit tests for parser"));
    }

    fn make_test_ctx(name: &str) -> (RunContext, PathBuf) {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("foundry-backup-{}-{}", name, unique));
        std::fs::create_dir_all(&dir).expect("create temp dir");
        std::fs::write(
            dir.join("TASKS.md"),
            "- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n",
        )
        .expect("write TASKS.md");
        std::fs::write(
            dir.join("SPEC.md"),
            "# Test Spec\n\nThis is the spec.\n",
        )
        .expect("write SPEC.md");
        std::fs::write(
            dir.join("CLAUDE.md"),
            "# CLAUDE.md\n\nProject instructions.\n",
        )
        .expect("write CLAUDE.md");
        std::fs::create_dir_all(dir.join(".buildloop")).expect("create .buildloop");
        std::fs::write(
            dir.join(".buildloop/current-plan.md"),
            "# Plan: T1.1\n\n## Steps\n1. Do the thing\n",
        )
        .expect("write current-plan.md");
        let ctx = RunContext::new(&dir, Config::default(), Arc::new(AtomicBool::new(false)), Arc::new(Mutex::new(())));
        (ctx, dir)
    }

    fn drain_events(rx: &mut mpsc::UnboundedReceiver<AppEvent>) -> Vec<String> {
        let mut msgs = Vec::new();
        while let Ok(evt) = rx.try_recv() {
            if let AppEvent::LoopEvent(LoopEvent::Log(msg)) = evt {
                msgs.push(msg);
            }
        }
        msgs
    }

    #[test]
    fn test_backup_captures_all_state_files() {
        let (ctx, dir) = make_test_ctx("capture");
        let backup = backup_state_files(&ctx);

        assert!(backup.files.contains_key(&ctx.plan_path));
        assert!(backup.files.contains_key(&ctx.spec_path));
        assert!(backup.files.contains_key(&ctx.current_plan));
        assert!(backup.files.contains_key(&ctx.project_dir.join("CLAUDE.md")));
        assert_eq!(
            backup.files.get(&ctx.plan_path).unwrap(),
            b"- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n"
        );
        assert_eq!(
            backup.files.get(&ctx.spec_path).unwrap(),
            b"# Test Spec\n\nThis is the spec.\n"
        );
        assert!(backup.files.contains_key(&ctx.buildloop_dir));
        assert!(backup.files.get(&ctx.buildloop_dir).unwrap().is_empty());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_recovers_deleted_files() {
        let (ctx, dir) = make_test_ctx("restore-deleted");
        let backup = backup_state_files(&ctx);

        std::fs::remove_file(&ctx.plan_path).unwrap();
        std::fs::remove_file(&ctx.spec_path).unwrap();
        std::fs::remove_file(ctx.project_dir.join("CLAUDE.md")).unwrap();

        assert!(!ctx.plan_path.exists());
        assert!(!ctx.spec_path.exists());

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 3);
        assert!(ctx.plan_path.exists());
        assert!(ctx.spec_path.exists());
        assert!(ctx.project_dir.join("CLAUDE.md").exists());
        assert_eq!(
            std::fs::read_to_string(&ctx.plan_path).unwrap(),
            "- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_recovers_truncated_files() {
        let (ctx, dir) = make_test_ctx("restore-truncated");
        let backup = backup_state_files(&ctx);

        std::fs::write(&ctx.plan_path, "").unwrap();
        std::fs::write(&ctx.spec_path, "short").unwrap();

        assert!(ctx.plan_path.exists());
        assert!(ctx.spec_path.exists());

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 2);
        assert_eq!(
            std::fs::read_to_string(&ctx.plan_path).unwrap(),
            "- [ ] T1.1: Test task\n- [ ] T1.2: Another task\n"
        );
        assert_eq!(
            std::fs::read_to_string(&ctx.spec_path).unwrap(),
            "# Test Spec\n\nThis is the spec.\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_does_not_overwrite_rewritten_current_plan() {
        let (ctx, dir) = make_test_ctx("no-overwrite-plan");
        let backup = backup_state_files(&ctx);

        std::fs::write(
            &ctx.current_plan,
            "# Plan: T1.2\n\nNew plan content written by planner.\n",
        )
        .unwrap();

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 0);
        assert_eq!(
            std::fs::read_to_string(&ctx.current_plan).unwrap(),
            "# Plan: T1.2\n\nNew plan content written by planner.\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_restore_recovers_deleted_current_plan() {
        let (ctx, dir) = make_test_ctx("deleted-plan");
        let backup = backup_state_files(&ctx);

        std::fs::remove_file(&ctx.current_plan).unwrap();
        assert!(!ctx.current_plan.exists());

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 1);
        assert!(ctx.current_plan.exists());
        assert_eq!(
            std::fs::read_to_string(&ctx.current_plan).unwrap(),
            "# Plan: T1.1\n\n## Steps\n1. Do the thing\n"
        );

        let _ = drain_events(&mut rx);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[cfg(unix)]
    #[test]
    fn test_restore_write_failure_produces_warning_log() {
        use std::os::unix::fs::PermissionsExt;

        let (ctx, dir) = make_test_ctx("write-fail");
        let backup = backup_state_files(&ctx);

        std::fs::remove_file(&ctx.plan_path).unwrap();
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o444)).unwrap();

        let (tx, mut rx) = mpsc::unbounded_channel();
        let restored = restore_state_files(&ctx, &backup, &tx);

        assert_eq!(restored, 0);

        let msgs = drain_events(&mut rx);
        assert!(msgs.len() >= 1);
        assert!(msgs.iter().any(|m| m.contains("Warning") && m.contains("TASKS.md")));

        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o755)).unwrap();
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_is_stop_requested_detects_stop_file() {
        let (ctx, dir) = make_test_ctx("stop-file");
        assert!(!ctx.is_stop_requested());
        std::fs::write(ctx.stop_file(), "").unwrap();
        assert!(ctx.is_stop_requested());
        std::fs::remove_file(ctx.stop_file()).unwrap();
        assert!(!ctx.is_stop_requested());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_is_stop_requested_detects_shutdown_flag() {
        let (ctx, dir) = make_test_ctx("shutdown-flag");
        assert!(!ctx.is_stop_requested());
        ctx.shutdown.store(true, Ordering::Relaxed);
        assert!(ctx.is_stop_requested());
        let _ = std::fs::remove_dir_all(&dir);
    }
}

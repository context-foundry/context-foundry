use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use crossterm::event::{self, Event, KeyCode, KeyModifiers};
use futures::StreamExt;
use std::path::{Path, PathBuf};
use std::time::Duration;
use tokio::sync::mpsc;

use crate::agent::{self, AgentOutputEvent, AgentRole};
use crate::update;
use crate::utils::truncate_str;
use crate::config::Config;
use crate::git;
use crate::patterns;
use crate::prompts;
use crate::task::{self, Task};
use crate::tui;

// ─── App State ───────────────────────────────────────────────

pub struct AppState {
    pub current_task: Option<Task>,
    pub current_agent: Option<(AgentRole, DateTime<Utc>)>,
    pub current_agent_model: Option<String>,
    pub agent_output: Vec<String>,
    pub scroll_offset: usize,
    pub log_messages: Vec<(DateTime<Utc>, String)>,
    pub completed_count: usize,
    pub total_count: usize,
    pub discovery_round: usize,
    pub is_discovering: bool,
    pub should_quit: bool,
    pub stop_after_task: bool,
    pub events_received: usize,
    pub tick_count: usize,
    pub update_available: Option<String>,
}

impl AppState {
    fn new() -> Self {
        Self {
            current_task: None,
            current_agent: None,
            current_agent_model: None,
            agent_output: Vec::new(),
            scroll_offset: 0,
            log_messages: Vec::new(),
            completed_count: 0,
            total_count: 0,
            discovery_round: 0,
            is_discovering: false,
            should_quit: false,
            stop_after_task: false,
            events_received: 0,
            tick_count: 0,
            update_available: None,
        }
    }

    fn log(&mut self, msg: impl Into<String>) {
        self.log_messages.push((Utc::now(), msg.into()));
    }

    fn clear_agent(&mut self) {
        self.current_agent = None;
        self.current_agent_model = None;
        self.agent_output.clear();
        self.scroll_offset = 0;
    }

    fn set_agent(&mut self, role: AgentRole, model: &str) {
        self.agent_output.clear();
        self.scroll_offset = 0;
        self.events_received = 0;
        self.current_agent = Some((role, Utc::now()));
        self.current_agent_model = Some(model.to_string());
    }

    fn update_counts(&mut self, tasks: &[Task]) {
        self.total_count = tasks.len();
        self.completed_count = task::count_completed(tasks);
    }
}

// ─── Events ──────────────────────────────────────────────────

enum AppEvent {
    AgentOutput(AgentOutputEvent),
    AgentDone(bool),
    LoopEvent(LoopEvent),
    Key(event::KeyEvent),
    Tick,
    UpdateAvailable(String),
}

enum LoopEvent {
    TaskStarted(Task),
    AgentStarted(AgentRole, String),
    TaskCompleted(String, bool),
    DiscoveryStarted,
    DiscoveryCompleted(usize),
    Log(String),
    CountsUpdated(usize, usize),
    Finished,
}

// ─── TUI Mode ────────────────────────────────────────────────

pub async fn run_tui(project_dir: &Path) -> Result<()> {
    // Validate project
    let plan_path = project_dir.join("IMPL_PLAN.md");
    if !plan_path.exists() {
        anyhow::bail!("IMPL_PLAN.md not found in {}", project_dir.display());
    }

    // Check claude CLI
    which_claude()?;

    let config = Config::load(project_dir);
    let mut state = AppState::new();

    // Initial task parse
    let tasks = task::parse_tasks(&plan_path)?;
    state.update_counts(&tasks);
    state.log(format!(
        "Loop started — {} tasks ({} done, {} pending)",
        state.total_count,
        state.completed_count,
        task::count_pending(&tasks)
    ));

    // Setup terminal
    let mut terminal = tui::setup_terminal()?;

    // Event channels
    let (event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();

    // Spawn the build loop
    let loop_tx = event_tx.clone();
    let loop_dir = project_dir.to_path_buf();
    let loop_config = config.clone();
    tokio::spawn(async move {
        build_loop(loop_dir, loop_config, loop_tx).await;
    });

    // Spawn tick timer (10 fps)
    let tick_tx = event_tx.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_millis(100));
        loop {
            interval.tick().await;
            if tick_tx.send(AppEvent::Tick).is_err() {
                break;
            }
        }
    });

    // Spawn keyboard reader
    let key_tx = event_tx.clone();
    tokio::spawn(async move {
        let mut reader = crossterm::event::EventStream::new();
        loop {
            if let Some(Ok(Event::Key(key))) = reader.next().await {
                if key_tx.send(AppEvent::Key(key)).is_err() {
                    break;
                }
            }
        }
    });

    // Background update check (non-blocking, delayed)
    let update_tx = event_tx.clone();
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_secs(2)).await;
        let result = tokio::task::spawn_blocking(update::check_for_update).await;
        if let Ok(Ok(Some(version))) = result {
            let _ = update_tx.send(AppEvent::UpdateAvailable(version));
        }
    });

    // Main render loop
    loop {
        // Draw
        terminal.draw(|frame| tui::render(frame, &state))?;

        // Process events
        match event_rx.recv().await {
            Some(AppEvent::Tick) => {
                state.tick_count = state.tick_count.wrapping_add(1);
                // Drain any queued events without blocking
                while let Ok(evt) = event_rx.try_recv() {
                    handle_event(&mut state, evt);
                    if state.should_quit {
                        break;
                    }
                }
            }
            Some(evt) => {
                handle_event(&mut state, evt);
            }
            None => break,
        }

        if state.should_quit {
            break;
        }
    }

    // Restore terminal
    tui::restore_terminal(&mut terminal)?;

    println!("\nFoundry stopped. {} tasks completed.", state.completed_count);
    Ok(())
}

fn handle_event(state: &mut AppState, event: AppEvent) {
    match event {
        AppEvent::AgentOutput(output) => {
            state.events_received += 1;
            match output {
            AgentOutputEvent::Text(text) => {
                // Streaming text — append to current line or start new
                state.agent_output.push(text);
            }
            AgentOutputEvent::ToolUse { tool, input_preview } => {
                let msg = if input_preview.is_empty() {
                    format!("[tool] {}", tool)
                } else {
                    format!("[tool] {} — {}", tool, input_preview)
                };
                state.agent_output.push(msg);
            }
            AgentOutputEvent::ToolResult { output_preview } => {
                if !output_preview.is_empty() {
                    // Show first line only to avoid flooding
                    let first_line = output_preview.lines().next().unwrap_or("");
                    let display = if first_line.len() > 100 {
                        format!("[result] {}...", truncate_str(first_line, 100))
                    } else {
                        format!("[result] {}", first_line)
                    };
                    state.agent_output.push(display);
                }
            }
            AgentOutputEvent::Stderr(line) => {
                state.agent_output.push(format!("[stderr] {}", line));
            }
            AgentOutputEvent::Result(text) => {
                state.agent_output.push(String::new());
                for line in text.lines().take(10) {
                    state.agent_output.push(line.to_string());
                }
            }
        }},
        AppEvent::AgentDone(success) => {
            if let Some((ref role, _)) = state.current_agent {
                let status = if success { "completed" } else { "FAILED" };
                state.log(format!("{} {}", role, status));
            }
        }
        AppEvent::LoopEvent(le) => match le {
            LoopEvent::TaskStarted(task) => {
                state.log(format!("Task {} started", task.id));
                state.current_task = Some(task);
                state.clear_agent();
            }
            LoopEvent::AgentStarted(role, model) => {
                state.log(format!("{} spawned ({})", role, model));
                state.set_agent(role, &model);
            }
            LoopEvent::TaskCompleted(id, success) => {
                let status = if success { "done" } else { "WIP" };
                state.log(format!("Task {} — {}", id, status));
                state.current_task = None;
                state.clear_agent();
            }
            LoopEvent::DiscoveryStarted => {
                state.is_discovering = true;
                state.discovery_round += 1;
                state.log(format!("Discovery round {} started", state.discovery_round));
                state.clear_agent();
            }
            LoopEvent::DiscoveryCompleted(new_count) => {
                state.is_discovering = false;
                state.log(format!("Discovery found {} new tasks", new_count));
            }
            LoopEvent::Log(msg) => {
                state.log(msg);
            }
            LoopEvent::CountsUpdated(completed, total) => {
                state.completed_count = completed;
                state.total_count = total;
            }
            LoopEvent::Finished => {
                state.log("All work complete — loop finished");
                state.should_quit = true;
            }
        },
        AppEvent::Key(key) => {
            match key.code {
                KeyCode::Char('q') => {
                    state.should_quit = true;
                }
                KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                    if state.stop_after_task {
                        // Second Ctrl+C: quit immediately
                        state.should_quit = true;
                    } else {
                        state.stop_after_task = true;
                        state.log("Will stop after current task completes (Ctrl+C again to force quit)");
                    }
                }
                KeyCode::Up => {
                    state.scroll_offset = state.scroll_offset.saturating_add(3);
                }
                KeyCode::Down => {
                    state.scroll_offset = state.scroll_offset.saturating_sub(3);
                }
                _ => {}
            }
        }
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
    }
}

// ─── Build Loop (runs in background task) ────────────────────

async fn build_loop(
    project_dir: PathBuf,
    config: Config,
    tx: mpsc::UnboundedSender<AppEvent>,
) {
    let plan_path = project_dir.join("IMPL_PLAN.md");
    let buildloop_dir = project_dir.join(".buildloop");
    let log_dir = buildloop_dir.join("logs");
    let current_plan = buildloop_dir.join("current-plan.md");
    let review_report = buildloop_dir.join("review-report.md");

    // Ensure dirs exist
    let _ = std::fs::create_dir_all(&log_dir);

    let mut discovery_round: usize = 0;

    loop {
        // Re-parse tasks each iteration
        let tasks = match task::parse_tasks(&plan_path) {
            Ok(t) => t,
            Err(e) => {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                    "Failed to parse IMPL_PLAN.md: {}",
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

        // Find next pending task
        let next = task::next_pending(&tasks).cloned();

        if let Some(task_info) = next {
            // Process this task
            let success = process_task(
                &task_info,
                &project_dir,
                &config,
                &plan_path,
                &current_plan,
                &review_report,
                &log_dir,
                &tx,
            )
            .await;

            // Only mark done if validation passed
            if success {
                let _ = task::mark_done(&plan_path, task_info.line_number);
            }

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskCompleted(
                task_info.id.clone(),
                success,
            )));

            // Update counts
            if let Ok(tasks) = task::parse_tasks(&plan_path) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
                    task::count_completed(&tasks),
                    tasks.len(),
                )));
            }

            // Check if we should stop
            // We check a simple file-based signal since we can't directly read AppState
            let stop_file = buildloop_dir.join("stop");
            if stop_file.exists() {
                let _ = std::fs::remove_file(&stop_file);
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Finished));
                return;
            }

            tokio::time::sleep(Duration::from_secs(config.pause_between_tasks_secs)).await;
        } else {
            // No pending tasks — run discovery
            discovery_round += 1;

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryStarted));

            let pre_count = tasks.len();

            // Run discovery agent
            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            tokio::spawn(async move {
                while let Some(evt) = agent_rx.recv().await {
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Discovery,
                config.discovery_model.clone(),
            )));

            let prompt = prompts::discovery_prompt(discovery_round);
            let result = agent::run_agent(
                &AgentRole::Discovery,
                &config.discovery_model,
                &prompt,
                &project_dir,
                agent_tx,
                &log_dir,
                None,
                config.agent_timeout_secs,
            )
            .await;

            let _ = tx.send(AppEvent::AgentDone(
                result.as_ref().map(|r| r.success).unwrap_or(false),
            ));

            // Count new tasks
            let new_tasks = match task::parse_tasks(&plan_path) {
                Ok(t) => t.len().saturating_sub(pre_count),
                Err(_) => 0,
            };

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::DiscoveryCompleted(new_tasks)));

            if new_tasks == 0 {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                    "No new tasks found — waiting before next scan...".to_string(),
                )));
                tokio::time::sleep(Duration::from_secs(config.pause_between_cycles_secs)).await;
            } else {
                // Commit the new tasks
                let _ = git::commit_and_push(
                    &project_dir,
                    &format!("D{}", discovery_round),
                    &format!("Discovery round {} — {} new tasks", discovery_round, new_tasks),
                    false,
                );
            }

            // Update counts
            if let Ok(tasks) = task::parse_tasks(&plan_path) {
                let _ = tx.send(AppEvent::LoopEvent(LoopEvent::CountsUpdated(
                    task::count_completed(&tasks),
                    tasks.len(),
                )));
            }
        }
    }
}

async fn process_task(
    task_info: &Task,
    project_dir: &Path,
    config: &Config,
    _plan_path: &Path,
    current_plan: &Path,
    review_report: &Path,
    log_dir: &Path,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> bool {
    let task_id = &task_info.id;
    let task_desc = &task_info.description;
    let buildloop_dir = project_dir.join(".buildloop");
    let patterns_extracted = buildloop_dir.join("patterns-extracted.json");

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::TaskStarted(
        task_info.clone(),
    )));

    // Clean ephemeral files
    let _ = std::fs::remove_file(current_plan);
    let _ = std::fs::remove_file(review_report);
    let _ = std::fs::remove_file(&patterns_extracted);

    // ── LOAD PATTERNS ──
    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    let all_patterns = patterns::load_patterns(&patterns_dir);
    let matched = patterns::match_patterns(&all_patterns, task_desc);
    let pattern_context = patterns::format_patterns_for_prompt(&matched, "planner");

    if !matched.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Matched {} patterns for task",
            matched.len()
        ))));
    }

    // ── PLANNER ──
    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Planner,
        config.planner_model.clone(),
    )));

    let prompt = prompts::planner_prompt(task_id, task_desc, &pattern_context);
    let plan_result = agent::run_agent(
        &AgentRole::Planner,
        &config.planner_model,
        &prompt,
        project_dir,
        agent_tx,
        log_dir,
        None,
        config.agent_timeout_secs,
    )
    .await;

    let plan_ok = plan_result.map(|r| r.success).unwrap_or(false);
    let _ = tx.send(AppEvent::AgentDone(plan_ok));

    if !plan_ok || !current_plan.exists() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "PLANNER failed for {}",
            task_id
        ))));
        return false;
    }

    // Pause between agents to avoid rate limiting
    tokio::time::sleep(Duration::from_secs(config.pause_between_agents_secs)).await;

    // ── BUILDER ──
    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Builder,
        config.builder_model.clone(),
    )));

    let prompt = prompts::builder_prompt(task_id, task_desc);
    let build_result = agent::run_agent(
        &AgentRole::Builder,
        &config.builder_model,
        &prompt,
        project_dir,
        agent_tx,
        log_dir,
        None,
        config.agent_timeout_secs,
    )
    .await;

    let build_ok = build_result.map(|r| r.success).unwrap_or(false);
    let _ = tx.send(AppEvent::AgentDone(build_ok));

    if !build_ok {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "BUILDER failed for {} — committing WIP",
            task_id
        ))));
        let _ = git::commit_and_push(project_dir, task_id, task_desc, true);
        return false;
    }

    // Pause between agents to avoid rate limiting
    tokio::time::sleep(Duration::from_secs(config.pause_between_agents_secs)).await;

    // ── REVIEW + FIX LOOP (2 passes max) ──
    let reviewer_pattern_context = patterns::format_patterns_for_prompt(&matched, "reviewer");
    let validated = run_review_loop(
        task_id,
        task_desc,
        project_dir,
        config,
        review_report,
        log_dir,
        &reviewer_pattern_context,
        tx,
    )
    .await;

    // ── COMMIT ──
    let committed = git::commit_and_push(project_dir, task_id, task_desc, !validated)
        .unwrap_or(false);

    if committed {
        let prefix = if validated { "feat" } else { "WIP" };
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Committed {}({})",
            prefix, task_id
        ))));
    }

    // ── PATTERN EXTRACTION ──
    if validated {
        // Pause between agents to avoid rate limiting
        tokio::time::sleep(Duration::from_secs(config.pause_between_agents_secs)).await;
        run_pattern_extraction(
            task_id,
            task_desc,
            project_dir,
            config,
            &patterns_dir,
            &patterns_extracted,
            log_dir,
            tx,
        )
        .await;
    }

    // ── CLEANUP ──
    let _ = std::fs::remove_file(&patterns_extracted);

    // ── DOCKER RESTART (selective) ──
    if should_restart_docker(task_desc) {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "Restarting Docker services...".to_string(),
        )));
        let _ = std::process::Command::new("docker")
            .args(["compose", "down"])
            .current_dir(project_dir)
            .output();
        let _ = std::process::Command::new("docker")
            .args(["compose", "up", "-d", "--build"])
            .current_dir(project_dir)
            .output();
    }

    validated
}

// ─── Review Loop (unified validator + auditor) ───────────────

async fn run_review_loop(
    task_id: &str,
    task_desc: &str,
    project_dir: &Path,
    config: &Config,
    review_report: &Path,
    log_dir: &Path,
    pattern_context: &str,
    tx: &mpsc::UnboundedSender<AppEvent>,
) -> bool {
    let files_changed = get_changed_files(project_dir);
    if files_changed.is_empty() {
        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
            "No changed files to review".to_string(),
        )));
        return false;
    }

    let files_list = files_changed.join("\n");
    let reviewer_tools: &[&str] = &["Read", "Glob", "Grep", "Write", "Bash"];

    for pass in 1..=2 {
        let _ = std::fs::remove_file(review_report);

        // ── Run Reviewer ──
        let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
        let fwd_tx = tx.clone();
        tokio::spawn(async move {
            while let Some(evt) = agent_rx.recv().await {
                let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
            }
        });

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
            AgentRole::Reviewer,
            config.reviewer_model.clone(),
        )));

        let prompt = prompts::reviewer_prompt(
            task_id,
            task_desc,
            &files_list,
            pass,
            pattern_context,
        );
        let review_result = agent::run_agent(
            &AgentRole::Reviewer,
            &config.reviewer_model,
            &prompt,
            project_dir,
            agent_tx,
            log_dir,
            Some(reviewer_tools),
            config.agent_timeout_secs,
        )
        .await;

        let _ = tx.send(AppEvent::AgentDone(
            review_result.as_ref().map(|r| r.success).unwrap_or(false),
        ));

        // Check verdict and parse findings
        let verdict_pass = check_review_passed(review_report);
        let (high, medium, _low) = parse_audit_findings(review_report);

        let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
            "Review pass {}/2: verdict={}, {} high, {} medium findings",
            pass,
            if verdict_pass { "PASS" } else { "FAIL" },
            high,
            medium
        ))));

        // Convergence: PASS verdict AND no high/medium findings
        if verdict_pass && high == 0 && medium == 0 {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Review passed — no issues found".to_string(),
            )));
            return true;
        }

        // Run Fixer (unless this is the last pass)
        if pass < 2 {
            // Pause between agents to avoid rate limiting
            tokio::time::sleep(Duration::from_secs(config.pause_between_agents_secs)).await;
            let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
            let fwd_tx = tx.clone();
            tokio::spawn(async move {
                while let Some(evt) = agent_rx.recv().await {
                    let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
                }
            });

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Fixer,
                config.fixer_model.clone(),
            )));

            let prompt = prompts::fixer_prompt(task_id, task_desc, pass);
            let fix_result = agent::run_agent(
                &AgentRole::Fixer,
                &config.fixer_model,
                &prompt,
                project_dir,
                agent_tx,
                log_dir,
                None,
                config.agent_timeout_secs,
            )
            .await;

            let _ = tx.send(AppEvent::AgentDone(
                fix_result.map(|r| r.success).unwrap_or(false),
            ));

            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
                "Fixer completed, running second review pass...".to_string(),
            )));

            // Pause between agents to avoid rate limiting
            tokio::time::sleep(Duration::from_secs(config.pause_between_agents_secs)).await;
        } else {
            let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(format!(
                "Review pass 2 still has issues: {} high, {} medium — committing as-is",
                high, medium
            ))));
        }
    }

    // If we exit the loop without returning true, check the final verdict
    check_review_passed(review_report)
}

// ─── Pattern Extraction ──────────────────────────────────────

async fn run_pattern_extraction(
    task_id: &str,
    task_desc: &str,
    project_dir: &Path,
    config: &Config,
    patterns_dir: &Path,
    patterns_extracted: &Path,
    log_dir: &Path,
    tx: &mpsc::UnboundedSender<AppEvent>,
) {
    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let fwd_tx = tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = fwd_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    // Pattern extraction is lightweight — use the discovery model, not builder
    let model = &config.discovery_model;
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::AgentStarted(
        AgentRole::Discovery, // Reuse Discovery role display for pattern extraction
        model.clone(),
    )));
    let _ = tx.send(AppEvent::LoopEvent(LoopEvent::Log(
        "Extracting patterns from build artifacts...".to_string(),
    )));

    let prompt = prompts::pattern_extraction_prompt(task_id, task_desc);
    let result = agent::run_agent(
        &AgentRole::Discovery,
        model,
        &prompt,
        project_dir,
        agent_tx,
        log_dir,
        Some(&["Read", "Write"]),
        600, // pattern extraction is lightweight, 10min is generous
    )
    .await;

    let _ = tx.send(AppEvent::AgentDone(
        result.as_ref().map(|r| r.success).unwrap_or(false),
    ));

    // Merge extracted patterns into global store
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

// ─── Helpers ─────────────────────────────────────────────────

/// Get files changed since last commit (excluding .buildloop/).
/// Handles renames (R  old -> new), copies, and quoted paths.
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
                    let trimmed = line.trim();
                    if trimmed.len() <= 3 {
                        return None;
                    }
                    let mut file = trimmed[3..].trim();
                    // Handle renames/copies: "R  old -> new" — take the destination
                    if let Some(arrow_pos) = file.find(" -> ") {
                        file = file[arrow_pos + 4..].trim();
                    }
                    // Strip quotes from paths with special characters
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

/// Parse audit report JSON to count high/medium/low findings.
/// Returns (1, 0, 0) if the report exists but JSON is malformed — treats parse
/// failure as a HIGH finding to prevent false "all clear" convergence.
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
        // Report exists with content but no JSON fence — treat as suspicious
        eprintln!("warning: audit report has no JSON code fence, treating as 1 high finding");
        return (1, 0, 0);
    }

    match serde_json::from_str::<serde_json::Value>(&json_str) {
        Ok(v) => {
            let high = v.get("high").and_then(|a| a.as_array()).map(|a| a.len()).unwrap_or(0);
            let medium = v.get("medium").and_then(|a| a.as_array()).map(|a| a.len()).unwrap_or(0);
            let low = v.get("low").and_then(|a| a.as_array()).map(|a| a.len()).unwrap_or(0);
            (high, medium, low)
        }
        Err(e) => {
            eprintln!("warning: failed to parse audit JSON: {}, treating as 1 high finding", e);
            (1, 0, 0)
        }
    }
}

/// Extract JSON content from markdown code fences in audit report.
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

fn should_restart_docker(task_desc: &str) -> bool {
    let lower = task_desc.to_lowercase();
    lower.contains("docker")
        || lower.contains("compose")
        || lower.contains("dockerfile")
        || lower.contains("caddy")
        || lower.contains("integration")
        || lower.contains("scaffold")
}

fn which_claude() -> Result<()> {
    let output = std::process::Command::new("which")
        .arg("claude")
        .output()
        .context("failed to run 'which' command")?;
    if !output.status.success() {
        anyhow::bail!("claude CLI not found in PATH — install Claude Code first");
    }
    Ok(())
}

// ─── Headless Mode ───────────────────────────────────────────

pub async fn run_headless(project_dir: &Path) -> Result<()> {
    let plan_path = project_dir.join("IMPL_PLAN.md");
    if !plan_path.exists() {
        anyhow::bail!("IMPL_PLAN.md not found in {}", project_dir.display());
    }

    which_claude()?;

    let config = Config::load(project_dir);
    let (tx, mut rx) = mpsc::unbounded_channel::<AppEvent>();

    let loop_dir = project_dir.to_path_buf();
    let loop_config = config;
    let loop_tx = tx.clone();
    tokio::spawn(async move {
        build_loop(loop_dir, loop_config, loop_tx).await;
    });

    // Background update check
    let update_tx = tx;
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_secs(2)).await;
        let result = tokio::task::spawn_blocking(update::check_for_update).await;
        if let Ok(Ok(Some(version))) = result {
            let _ = update_tx.send(AppEvent::UpdateAvailable(version));
        }
    });

    let mut update_version: Option<String> = None;

    // Print events to stdout
    while let Some(evt) = rx.recv().await {
        match evt {
            AppEvent::AgentOutput(AgentOutputEvent::Text(text)) => {
                println!("{}", text);
            }
            AppEvent::AgentOutput(AgentOutputEvent::ToolUse { tool, input_preview }) => {
                eprintln!("[tool] {} {}", tool, input_preview);
            }
            AppEvent::AgentOutput(AgentOutputEvent::ToolResult { output_preview }) => {
                if !output_preview.is_empty() {
                    let first = output_preview.lines().next().unwrap_or("");
                    eprintln!("[result] {}", first);
                }
            }
            AppEvent::AgentOutput(AgentOutputEvent::Stderr(line)) => {
                eprintln!("[stderr] {}", line);
            }
            AppEvent::AgentOutput(AgentOutputEvent::Result(text)) => {
                println!("{}", text);
            }
            AppEvent::LoopEvent(le) => match le {
                LoopEvent::TaskStarted(t) => {
                    eprintln!("\n=== TASK: {} — {} ===", t.id, t.short_desc(80));
                }
                LoopEvent::AgentStarted(role, model) => {
                    eprintln!("--- {} ({}) ---", role, model);
                }
                LoopEvent::TaskCompleted(id, ok) => {
                    let status = if ok { "DONE" } else { "WIP" };
                    eprintln!("=== {} {} ===\n", id, status);
                }
                LoopEvent::DiscoveryStarted => {
                    eprintln!("\n=== DISCOVERY ===");
                }
                LoopEvent::DiscoveryCompleted(n) => {
                    eprintln!("=== Discovery found {} new tasks ===\n", n);
                }
                LoopEvent::Log(msg) => {
                    eprintln!("[log] {}", msg);
                }
                LoopEvent::Finished => break,
                _ => {}
            },
            AppEvent::UpdateAvailable(version) => {
                update_version = Some(version);
            }
            _ => {}
        }
    }

    if let Some(version) = update_version {
        eprintln!(
            "\nUpdate available: v{} → v{}. Run `foundry update` to upgrade.",
            update::current_version(),
            version
        );
    }

    Ok(())
}

// ─── Status & Tasks Commands ─────────────────────────────────

pub fn show_status(project_dir: &Path) -> Result<()> {
    let plan_path = project_dir.join("IMPL_PLAN.md");
    let tasks = task::parse_tasks(&plan_path)?;

    let completed = task::count_completed(&tasks);
    let pending = task::count_pending(&tasks);
    let total = tasks.len();
    let pct = if total > 0 {
        (completed as f64 / total as f64) * 100.0
    } else {
        0.0
    };

    println!("Foundry Status — {}", project_dir.display());
    println!("─────────────────────────────────────");
    println!(
        "Progress: {}/{} ({:.0}%) — {} pending",
        completed, total, pct, pending
    );

    if let Some(next) = task::next_pending(&tasks) {
        println!("Next task: {} — {}", next.id, next.short_desc(60));
    } else {
        println!("All tasks complete — discovery mode");
    }

    Ok(())
}

pub fn show_tasks(project_dir: &Path) -> Result<()> {
    let plan_path = project_dir.join("IMPL_PLAN.md");
    let tasks = task::parse_tasks(&plan_path)?;

    for t in &tasks {
        let check = if t.completed { "x" } else { " " };
        println!("[{}] {} — {}", check, t.id, t.short_desc(70));
    }

    println!(
        "\n{} done, {} pending",
        task::count_completed(&tasks),
        task::count_pending(&tasks)
    );

    Ok(())
}

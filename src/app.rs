use anyhow::{Context, Result};
use crossterm::event::{self, Event, KeyCode, KeyModifiers};
use futures::StreamExt;
use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;

mod build;
pub(crate) mod commands;
mod context;
mod contract;
mod planning;
mod review;
mod startup;
mod state;

use self::context::RunContext;
use self::contract::ContractPaths;
use self::startup::{
    classify_plan_status, detect_startup_scenario, enter_home_surface, enter_startup_surface,
    handle_startup_event, load_pending_task_at,
};
pub use self::state::FileEntry;
pub use self::state::{
    settings_sections, Action, AppPhase, AppState, ClickableSurface, CurrentClassification,
    DualSelection, ExplorerContextMenu, ExtensionDisplayInfo, FieldKind, ModelEntry, ModelPicker,
    OverlayRow, PatternEventKind, PickerItem, PlanStatus, PlanningState, RunningModalKind,
    SectionKind, StartupAction, StartupScenario, StartupState, StreamState,
    SurfaceSummaryOverlay, TuiPane,
};
use self::state::{AppEvent, AppendTasksRequest, LoopEvent, PendingTransition, PlanningOutcome};
use crate::agent::{AgentErrorKind, AgentOutputEvent, AgentRole};
use crate::complexity::TaskOverride;
use crate::config::Config;
use crate::eval;
use crate::llm::summary::summarize_surface;
use crate::llm::summary_cache::StageState;
use crate::eval::report as eval_report;
use crate::git;
use crate::orchestrator::{self, OrchestratorConfig, OrchestratorOutcome};
use crate::task;
use crate::tmux;
use crate::tui;
use crate::update;
use crate::utils::{atomic_write_file, truncate_str};

// ─── TUI Mode ────────────────────────────────────────────────

/// Result of probing all providers for available models.
/// `lmstudio_opencode_map` keys are LM Studio short ids (suffix after the last `/`
/// in the `/v1/models` id) and values are the canonical opencode model paths
/// emitted by `opencode models lmstudio` (e.g. `lmstudio/qwen/qwen3-coder-30b`).
/// `opencode_warning` is `Some(msg)` if `opencode models lmstudio` failed or
/// returned an empty list while LM Studio itself reported models.
pub(super) struct ModelsDiscovery {
    pub lmstudio: Vec<String>,
    pub ollama: Vec<String>,
    pub lmstudio_opencode_map: HashMap<String, String>,
    pub opencode_warning: Option<String>,
    pub claude_available: bool,
    pub codex_available: bool,
    pub copilot_available: bool,
}

/// Probe all providers for available models and CLI presence.
/// Checks LM Studio, Ollama, opencode, Claude CLI, Codex CLI, and gh (Copilot).
pub(super) async fn fetch_available_models(ollama_url: String) -> ModelsDiscovery {
    tokio::task::spawn_blocking(move || {
        let mut lmstudio: Vec<String> = Vec::new();
        let mut ollama: Vec<String> = Vec::new();
        let mut opencode_warning: Option<String> = None;

        // LM Studio: GET http://127.0.0.1:1234/v1/models
        let lm_out = std::process::Command::new("curl")
            .args(["-s", "--max-time", "2", "http://127.0.0.1:1234/v1/models"])
            .output();
        if let Ok(out) = lm_out {
            if let Ok(text) = std::str::from_utf8(&out.stdout) {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(text) {
                    if let Some(arr) = val.get("data").and_then(|d| d.as_array()) {
                        for item in arr {
                            if let Some(id) = item.get("id").and_then(|v| v.as_str()) {
                                if !id.is_empty() {
                                    lmstudio.push(id.to_string());
                                }
                            }
                        }
                    }
                }
            }
        }

        // Ollama: GET {ollama_url}/api/tags
        let ollama_out = std::process::Command::new("curl")
            .args([
                "-s",
                "--max-time",
                "2",
                &format!("{}/api/tags", ollama_url),
            ])
            .output();
        if let Ok(out) = ollama_out {
            if let Ok(text) = std::str::from_utf8(&out.stdout) {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(text) {
                    if let Some(arr) = val.get("models").and_then(|m| m.as_array()) {
                        for item in arr {
                            if let Some(name) = item.get("name").and_then(|v| v.as_str()) {
                                let s = name.to_string();
                                if !s.is_empty() {
                                    ollama.push(s);
                                }
                            }
                        }
                    }
                }
            }
        }

        // opencode: shell out to `opencode models lmstudio` and parse the canonical paths.
        let oc_out = std::process::Command::new("opencode")
            .args(["models", "lmstudio"])
            .output();
        let oc_text: String = match oc_out {
            Ok(out) if out.status.success() => {
                String::from_utf8_lossy(&out.stdout).to_string()
            }
            _ => String::new(),
        };
        let lmstudio_opencode_map = build_lmstudio_canonical_map(&oc_text);
        if !lmstudio.is_empty() && lmstudio_opencode_map.is_empty() {
            opencode_warning = Some(
                "Warning: `opencode models lmstudio` returned no results; LM Studio model routing may use raw IDs and miss namespaces.".to_string()
            );
        }

        // Claude CLI: check presence via `claude --version`
        let claude_available = std::process::Command::new("claude")
            .arg("--version")
            .output()
            .is_ok_and(|o| o.status.success());

        // Codex CLI: check presence via `codex --version`
        let codex_available = std::process::Command::new("codex")
            .arg("--version")
            .output()
            .is_ok_and(|o| o.status.success());

        // GitHub Copilot: check if `gh auth token` succeeds (implies gh CLI + auth)
        let copilot_available = std::process::Command::new("gh")
            .args(["auth", "token"])
            .output()
            .is_ok_and(|o| o.status.success());

        ModelsDiscovery {
            lmstudio,
            ollama,
            lmstudio_opencode_map,
            opencode_warning,
            claude_available,
            codex_available,
            copilot_available,
        }
    })
    .await
    .unwrap_or_else(|_| ModelsDiscovery {
        lmstudio: vec![],
        ollama: vec![],
        lmstudio_opencode_map: HashMap::new(),
        opencode_warning: None,
        claude_available: false,
        codex_available: false,
        copilot_available: false,
    })
}

/// Pure parser: convert newline-delimited output of `opencode models lmstudio` into a
/// `{short_id -> canonical_path}` HashMap. The short id is the segment after the last
/// `/` (or the whole line if there is no `/`). The value is the original line as-is so
/// the canonical `lmstudio/...` prefix is preserved for `Config::save_builder_routing`.
fn build_lmstudio_canonical_map(opencode_stdout: &str) -> HashMap<String, String> {
    let mut map: HashMap<String, String> = HashMap::new();
    for raw_line in opencode_stdout.lines() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }
        let after_prefix = line.strip_prefix("lmstudio/").unwrap_or(line);
        let suffix = after_prefix.rsplit('/').next().unwrap_or(after_prefix);
        if suffix.is_empty() {
            continue;
        }
        map.insert(suffix.to_string(), line.to_string());
    }
    map
}

/// Returns how many lines to scroll per wheel tick based on inter-event timing.
/// Fast spins (events arriving <50ms apart) scroll up to 8 lines; a leisurely single
/// click scrolls 2. This approximates browser-style velocity without physics simulation.
fn wheel_lines(last: Option<std::time::Instant>) -> usize {
    match last {
        Some(t) => {
            let ms = t.elapsed().as_millis();
            if ms < 50 {
                8
            } else if ms < 100 {
                5
            } else if ms < 200 {
                3
            } else {
                2
            }
        }
        None => 2,
    }
}

/// Build the unified builder list: configured specs + combined-label (if 2+) + local models.
/// Specs are stored as raw config values (e.g. "claude:opus") but the combined "both" entry
/// uses readable labels (e.g. "claude:claude-opus-4-7/codex") so it's unambiguous.
fn build_unified_builders(specs: &[String], local_models: &[String]) -> Vec<String> {
    let mut list: Vec<String> = specs.iter().map(|s| Config::readable_spec(s)).collect();
    if specs.len() >= 2 {
        let combined = list
            .iter()
            .take(specs.len())
            .cloned()
            .collect::<Vec<_>>()
            .join("/");
        list.push(combined);
    }
    for m in local_models {
        if !list.contains(m) {
            list.push(m.clone());
        }
    }
    list
}

/// Apply a unified builder selection to state and persist to .foundry.json.
/// `value` is a readable spec label (from build_unified_builders), not the raw config string.
fn apply_builder_selection(state: &mut AppState, value: &str) {
    let dir = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."))
        .to_path_buf();
    // Match against readable spec labels for each configured spec
    for (i, spec) in state.builder_model_specs.clone().iter().enumerate() {
        if Config::readable_spec(spec) == value {
            Config::clear_builder_routing(&dir);
            state.dual_selection = match i {
                0 => DualSelection::First,
                1 => DualSelection::Second,
                _ => DualSelection::Third,
            };
            state.selected_local_model = String::new();
            Config::save_dual_selection(&dir, state.dual_selection.as_str());
            Config::save_local_model(&dir, "");
            return;
        }
    }
    // Local model: derive prefix from source list (LM Studio takes precedence
    // if a name appears in both) and route via opencode for both.
    if state.local_models.contains(&value.to_string()) {
        let model_path = if state.lmstudio_models.iter().any(|m| m == value) {
            // Always use the LM Studio /v1/models id verbatim with the
            // lmstudio/ provider prefix. opencode's `models lmstudio` output
            // is inconsistent: it strips vendor namespaces for some models
            // (e.g. reports "lmstudio/qwen3.6-27b" for LM Studio's
            // "qwen/qwen3.6-27b") which then routes to a JIT-loaded duplicate
            // with the default 4K context window. Trusting the LM Studio id
            // directly preserves the namespace so opencode forwards the
            // correct model id to LM Studio's API and hits the user's
            // already-loaded instance.
            format!("lmstudio/{}", value)
        } else {
            format!("ollama/{}", value)
        };
        state.selected_local_model = value.to_string();
        Config::save_local_model(&dir, value);
        Config::save_builder_routing(&dir, "opencode", &model_path);
        // After persisting the new local-model routing, re-validate that the
        // newly required provider CLI(s) are available AND mirror the disk
        // state into the in-memory AppState fields the TUI reads (D2.1: the
        // pipeline cards / Dual Pipeline panel / Cost label all read from
        // state.builder_model_specs and state.dual_selection -- without this
        // refresh they keep showing the previous config until the user fully
        // restarts foundry). Surface provider validation via state.log so
        // the user finds out before pressing Run, not at first agent
        // invocation.
        let reloaded = Config::load(&dir);
        state.builder_model_specs = reloaded.builder_models.clone();
        state.dual_selection = DualSelection::from_str(&reloaded.dual_selection);
        match commands::ensure_required_providers_available(
            &reloaded,
            commands::ProviderCommandMode::Run,
        ) {
            Ok(()) => {
                state.log(format!(
                    "Builder set to opencode/{}; required provider CLIs are available.",
                    model_path
                ));
            }
            Err(e) => {
                state.log(format!(
                    "Builder set to opencode/{} but provider validation failed: {}",
                    model_path, e
                ));
            }
        }
        return;
    }
    // Combined entry (specs joined with "/") -- set to Both
    Config::clear_builder_routing(&dir);
    state.dual_selection = DualSelection::Both;
    state.selected_local_model = String::new();
    Config::save_dual_selection(&dir, "both");
    Config::save_local_model(&dir, "");
}

/// Compute the initial builder_cursor from current dual_selection / selected_local_model.
fn init_builder_cursor(state: &mut AppState) {
    let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
    let target = if !state.selected_local_model.is_empty() {
        state.selected_local_model.clone()
    } else {
        let specs = &state.builder_model_specs;
        match state.dual_selection {
            DualSelection::Both => {
                // Combined entry is at index specs.len() in the unified list
                unified.get(specs.len()).cloned().unwrap_or_default()
            }
            DualSelection::First | DualSelection::Off => specs
                .first()
                .map(|s| Config::readable_spec(s))
                .unwrap_or_default(),
            DualSelection::Second => specs
                .get(1)
                .map(|s| Config::readable_spec(s))
                .unwrap_or_default(),
            DualSelection::Third => specs
                .get(2)
                .map(|s| Config::readable_spec(s))
                .unwrap_or_default(),
        }
    };
    state.builder_cursor = unified.iter().position(|m| m == &target).unwrap_or(0);
}

pub async fn run_tui(project_dir: &Path) -> Result<()> {
    let config = Config::load(project_dir);
    commands::ensure_required_providers_available(&config, commands::ProviderCommandMode::Run)?;
    let buildloop_dir = project_dir.join(".buildloop");
    std::fs::create_dir_all(&buildloop_dir).with_context(|| {
        format!(
            "Failed to create .buildloop directory: {}",
            buildloop_dir.display()
        )
    })?;
    if let Err(e) = std::fs::remove_file(buildloop_dir.join("stop")) {
        if e.kind() != std::io::ErrorKind::NotFound {
            eprintln!("Warning: failed to remove stale stop file: {}", e);
        }
    }
    let shutdown = Arc::new(AtomicBool::new(false));
    let mut state = AppState::new(buildloop_dir);
    state.run_mode = config.run_mode.clone();
    state.selected_local_model = config.local_model.clone();
    state.builder_model_specs = config.builder_models.clone();
    state.arena_mode = config.arena_mode.clone();
    state.agent_pane_split = config.agent_pane_split.clamp(20, 80);
    {
        let (p, m) = config.active_routing_for_stage("build");
        state.build_stage_label = Config::display_provider_model(&p, &m);
    }
    if config.builder_models.len() >= 2 {
        state.dual_selection = state::DualSelection::from_str(&config.dual_selection);
    }
    init_builder_cursor(&mut state);
    if let Some(tc) = config.truecolor {
        crate::tui::theme::set_truecolor_override(tc);
    }
    state.tui_theme = crate::tui::theme::from_name(&config.theme);

    // Sandbox detection
    let sandbox_cfg = config.sandbox_config();
    let sandbox_status = sandbox_cfg.status();
    state.sandbox_active = sandbox_cfg.is_active();
    state.sandbox_enabled = config.sandbox;
    state.sandbox_status_label = format!("{}", sandbox_status);
    match sandbox_status {
        crate::sandbox::SandboxStatus::Active => {
            sandbox_cfg.ensure_credentials_for_container();
            state.log(format!(
                "Sandbox active: image={}, mounts={}",
                sandbox_cfg.image,
                1 + sandbox_cfg.extra_mounts.len()
            ));
        }
        crate::sandbox::SandboxStatus::DockerNotFound => {
            state.log(
                "Warning: sandbox enabled but Docker not found; agents will run unsandboxed"
                    .to_string(),
            );
        }
        crate::sandbox::SandboxStatus::ImageNotFound => {
            state.log(format!(
                "Warning: sandbox image '{}' not found; agents will run unsandboxed. Run: docker/build-sandbox.sh",
                sandbox_cfg.image
            ));
        }
        crate::sandbox::SandboxStatus::Disabled => {
            state.log(
                "Warning: sandbox disabled by config override -- agents will run unsandboxed"
                    .to_string(),
            );
        }
    }

    // Tmux backend validation and stale session cleanup
    if config.agent_backend == "tmux" {
        if tmux::tmux_binary_available() {
            let stale = tmux::cleanup_stale_sessions(&config.tmux_session_prefix);
            for name in &stale {
                state.log(format!("Cleaned up stale tmux session: {}", name));
            }
        } else {
            state.log(
                "Warning: tmux backend configured but tmux binary not found; falling back to PTY"
                    .to_string(),
            );
        }
    }

    // Observatory retention cleanup: archive orphan SQLite + stale JSONL files.
    {
        let report =
            crate::observatory::run_retention_cleanup(config.observatory_jsonl_retention_days);
        if report.db_archived > 0 {
            state.log(format!(
                "Observatory: archived {} orphan SQLite file(s) to ~/.foundry/observatory/.archived/",
                report.db_archived
            ));
        }
        if report.jsonl_archived > 0 {
            state.log(format!(
                "Observatory: archived {} stale event log(s) older than {} day(s)",
                report.jsonl_archived, config.observatory_jsonl_retention_days
            ));
        }
        for err in &report.errors {
            state.log(format!("Observatory cleanup warning: {}", err));
        }
    }

    // Git/GH readiness checks
    if git::is_git_repo(project_dir) {
        for msg in git::check_git_readiness(project_dir) {
            state.log(msg);
        }
    } else {
        state.gh_cli_available = git::is_gh_cli_available();
        state.show_git_init_offer = true;
        state.log("No git repository detected".to_string());
    }
    for msg in ContractPaths::resolve(project_dir).warnings() {
        state.log(msg);
    }

    // Ollama status is checked by the background health checker (every 10s)

    enter_home_surface(project_dir, &mut state, None);

    // Setup terminal
    let mut terminal = tui::setup_terminal()?;

    // Event channels
    let (event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();
    state.event_tx = Some(event_tx.clone());

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

    // Background Ollama health check (every 10 seconds)
    if config.semantic_match_enabled {
        let ollama_tx = event_tx.clone();
        let ollama_url = config.ollama_url.clone();
        tokio::spawn(async move {
            loop {
                let url = format!("{}/api/tags", ollama_url);
                let connected = tokio::task::spawn_blocking(move || {
                    std::process::Command::new("curl")
                        .args(["-s", "--max-time", "2", &url])
                        .output()
                        .map(|o| o.status.success())
                        .unwrap_or(false)
                })
                .await
                .unwrap_or(false);
                if ollama_tx.send(AppEvent::OllamaStatus(connected)).is_err() {
                    break;
                }
                tokio::time::sleep(Duration::from_secs(10)).await;
            }
        });
    }

    // Spawn keyboard reader (keep handle so we can abort it for external editors)
    let mut terminal_reader_handle = spawn_terminal_event_reader(event_tx.clone());

    // Background update check (non-blocking, delayed)
    let update_tx = event_tx.clone();
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_secs(2)).await;
        let result = tokio::task::spawn_blocking(update::check_for_update).await;
        if let Ok(Ok(Some(version))) = result {
            let _ = update_tx.send(AppEvent::UpdateAvailable(version));
        }
    });

    // Background model-catalog refresh (non-blocking, delayed).
    let catalog_tx = event_tx.clone();
    let catalog_url_overrides = config.model_catalog_url_overrides.clone();
    let catalog_refresh_secs = config.model_catalog_refresh_secs;
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_secs(3)).await;
        if catalog_refresh_secs == 0 {
            return;
        }
        let mode = crate::model_catalog::refresh_mode_from_env();
        let catalog = crate::model_catalog::load_catalog();
        if !crate::model_catalog::refresh_policy_should_run(&catalog, mode, chrono::Utc::now()) {
            return;
        }
        let (log_tx, mut log_rx) = mpsc::unbounded_channel::<String>();
        let refresh_handle = tokio::spawn(crate::model_catalog::refresh_catalog_async(
            catalog,
            catalog_url_overrides,
            Some(log_tx),
        ));
        let mut messages: Vec<String> = Vec::new();
        while let Some(line) = log_rx.recv().await {
            messages.push(line);
        }
        match refresh_handle.await {
            Ok(Ok(_next)) => {}
            Ok(Err(e)) => {
                messages.push(format!("[catalog] refresh failed: {}", e));
            }
            Err(e) => {
                messages.push(format!("[catalog] refresh task panicked: {}", e));
            }
        }
        if !messages.is_empty() {
            let _ = catalog_tx.send(AppEvent::CatalogRefreshed(messages));
        }
    });

    // Fetch a fresh welcome message from a local LLM (best-effort, non-blocking)
    {
        let welcome_tx = event_tx.clone();
        let ollama_url = config.ollama_url.clone();
        tokio::spawn(async move {
            let msg = tokio::task::spawn_blocking(move || fetch_welcome_message(&ollama_url))
                .await
                .ok()
                .flatten();
            if let Some(text) = msg {
                let _ = welcome_tx.send(AppEvent::WelcomeMessage(text));
            }
        });
    }

    // Background narrative refresh: re-read `git log -1` every 10 seconds and
    // post the result to the TUI. Best-effort; never blocks rendering.
    {
        let narrative_tx = event_tx.clone();
        let project_dir_buf = project_dir.to_path_buf();
        tokio::spawn(async move {
            loop {
                let dir = project_dir_buf.clone();
                let brief = tokio::task::spawn_blocking(move || {
                    crate::git::last_commit_brief(&dir)
                })
                .await
                .ok()
                .flatten();
                if narrative_tx
                    .send(AppEvent::NarrativeRefresh(brief))
                    .is_err()
                {
                    break;
                }
                tokio::time::sleep(Duration::from_secs(10)).await;
            }
        });
    }

    // Main render loop
    loop {
        // Draw based on phase
        terminal.draw(|frame| {
            if state.show_welcome {
                tui::render_welcome(frame, &state);
            } else {
                match state.phase {
                    AppPhase::Startup => {
                        if state.show_stats_overlay {
                            tui::render_stats_overlay(frame, &state);
                        } else if state.show_findings {
                            tui::render_findings(frame, &state);
                        } else if state.show_run_view {
                            tui::render(frame, &state, &config);
                        } else {
                            tui::render_startup(frame, &state);
                        }
                    }
                    AppPhase::Planning | AppPhase::Running => {
                        if state.show_stats_overlay {
                            tui::render_stats_overlay(frame, &state);
                        } else if state.show_findings {
                            tui::render_findings(frame, &state);
                        } else if state.show_patterns {
                            tui::render_patterns(frame, &state, &config);
                        } else if state.show_running_explorer
                            && matches!(state.phase, AppPhase::Running)
                        {
                            tui::render_running_explorer(frame, &state, &config);
                        } else {
                            tui::render(frame, &state, &config);
                        }
                    }
                }
                // Settings overlay floats on top -- render after base view
                if state.show_settings_overlay {
                    tui::render_settings_overlay(frame, &state);
                }
                if state.surface_summary_overlay.is_some() {
                    tui::render_surface_summary_overlay(frame, &state);
                }
                // Warning/confirmation banners on top of everything
                if state.show_git_init_offer {
                    tui::render_git_init_offer(frame, &state.tui_theme, state.gh_cli_available);
                }
                if state.show_no_tasks_warning {
                    tui::render_no_tasks_warning(frame, &state.tui_theme);
                }
                if state.confirm_quit {
                    tui::render_quit_confirm(frame, &state.tui_theme);
                }
                if let Some(kind) = state.running_screen_modal {
                    tui::render_running_modal(frame, &state.tui_theme, kind);
                }
            } // close show_welcome else
        })?;

        // Process events
        match event_rx.recv().await {
            Some(evt) => process_received_event(&mut state, evt, &mut event_rx, &config),
            None => break,
        }

        // When user requests stop, kill the running agent immediately.
        // Discovery and other read-only agents have nothing critical to preserve.
        if state.stop_after_task {
            shutdown.store(true, Ordering::Release);
        } else {
            shutdown.store(false, Ordering::Release);
        }

        if let Some(editor_path) =
            apply_pending_transition(project_dir, &config, &event_tx, &mut state, &shutdown)
        {
            // Abort the terminal event reader so it stops competing for input
            terminal_reader_handle.abort();
            tui::restore_terminal(&mut terminal)?;
            let editor_result = launch_external_editor(&editor_path);
            terminal = tui::setup_terminal()?;
            // Respawn the terminal event reader
            terminal_reader_handle = spawn_terminal_event_reader(event_tx.clone());
            let message = match editor_result {
                Ok(()) => {
                    let name = editor_path
                        .file_name()
                        .unwrap_or_default()
                        .to_string_lossy();
                    Some(format!("{} saved. Changes apply on the next run.", name))
                }
                Err(e) => Some(format!("Editor failed: {}", e)),
            };
            enter_home_surface(project_dir, &mut state, message);
        }

        if state.should_quit {
            break;
        }
    }

    // Signal all spawned agent processes to terminate so spawn_blocking
    // threads exit promptly instead of blocking tokio runtime shutdown.
    shutdown.store(true, Ordering::Release);
    terminal_reader_handle.abort();

    // Restore terminal
    tui::restore_terminal(&mut terminal)?;

    if let Some(ref sid) = state.observatory_session_id {
        let project_dir_canonical =
            dunce::canonicalize(project_dir).unwrap_or_else(|_| project_dir.to_path_buf());
        if let Err(e) = crate::stats::print_session_summary(sid, &project_dir_canonical) {
            eprintln!("Warning: could not print session summary: {}", e);
        }
    }
    if state.observatory_session_id.is_none() || state.completed_count == 0 {
        println!(
            "\nFoundry stopped. {} tasks completed.",
            state.completed_count
        );
    }
    Ok(())
}

fn spawn_terminal_event_reader(
    event_tx: mpsc::UnboundedSender<AppEvent>,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut reader = crossterm::event::EventStream::new();
        loop {
            if let Some(evt) = reader.next().await {
                let Ok(evt) = evt else {
                    break;
                };
                let app_event = match evt {
                    Event::Key(key) if key.kind == event::KeyEventKind::Press => {
                        Some(AppEvent::Key(key))
                    }
                    Event::Key(_) => None, // Ignore Release/Repeat (Windows fires both)
                    Event::Mouse(mouse) => Some(AppEvent::Mouse(mouse)),
                    Event::Paste(text) => Some(AppEvent::Paste(text)),
                    _ => None,
                };
                if let Some(app_event) = app_event {
                    if event_tx.send(app_event).is_err() {
                        break;
                    }
                }
            }
        }
    })
}

fn dispatch_event(state: &mut AppState, event: AppEvent, config: &Config) {
    // Welcome screen: dismiss only on Enter
    if state.show_welcome {
        match &event {
            AppEvent::Key(key)
                if key.code == crossterm::event::KeyCode::Enter
                    || key.code == crossterm::event::KeyCode::Esc
                    || (key.code == crossterm::event::KeyCode::Char('c')
                        && key
                            .modifiers
                            .contains(crossterm::event::KeyModifiers::CONTROL)) =>
            {
                state.show_welcome = false;
                return;
            }
            AppEvent::Key(_) | AppEvent::Mouse(_) | AppEvent::Paste(_) => {
                return;
            }
            AppEvent::WelcomeMessage(ref msg) => {
                state.welcome_message = msg.clone();
                return;
            }
            _ => {}
        }
    }
    if matches!(&event, AppEvent::WelcomeMessage(_)) {
        return; // ignore late arrivals after welcome is dismissed
    }
    if let AppEvent::NarrativeRefresh(brief) = &event {
        state.last_commit_brief = brief.clone();
        return;
    }
    match state.phase {
        AppPhase::Startup => handle_startup_event(state, event, config),
        AppPhase::Planning => handle_planning_event(state, event, config),
        AppPhase::Running => handle_event(state, event, config),
    }
}

fn process_received_event(
    state: &mut AppState,
    event: AppEvent,
    event_rx: &mut mpsc::UnboundedReceiver<AppEvent>,
    config: &Config,
) {
    let should_drain = matches!(event, AppEvent::Tick);
    dispatch_event(state, event, config);

    if !should_drain {
        return;
    }

    // Keep the UI responsive by draining any events that piled up since the last frame.
    while let Ok(evt) = event_rx.try_recv() {
        dispatch_event(state, evt, config);
        if state.should_quit {
            break;
        }
    }
}

fn apply_pending_transition(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    shutdown: &Arc<AtomicBool>,
) -> Option<std::path::PathBuf> {
    while let Some(transition) = state.pending_transition.take() {
        match transition {
            PendingTransition::StartBuild => {
                if let Err(e) = spawn_build_loop(project_dir, config, event_tx, state, shutdown) {
                    let message = format!("Cannot start loop: {}", e);
                    state.log(message.clone());
                    enter_home_surface(project_dir, state, Some(message));
                } else {
                    state.phase = AppPhase::Running;
                    state.startup = None;
                    state.planning = None;
                    state.focused_pane = state::TuiPane::AgentOutput;
                    state.show_running_explorer = false;
                    state.running_explorer = None;
                }
            }
            PendingTransition::StartPlanning { user_intent, label } => {
                spawn_inline_planning(
                    project_dir,
                    config,
                    event_tx,
                    state,
                    user_intent,
                    label,
                    shutdown,
                );
            }
            PendingTransition::StartDesign { user_intent } => {
                spawn_design_loop(project_dir, config, event_tx, state, user_intent, shutdown);
            }
            PendingTransition::AppendTasks(request) => {
                spawn_append_tasks(project_dir, config, event_tx, state, request, shutdown);
            }
            PendingTransition::OpenExternalEditor { file_path } => {
                return Some(file_path);
            }
            PendingTransition::ShowStartup { message } => {
                enter_startup_surface(project_dir, state, message);
                state.focused_pane = state::TuiPane::Explorer;
            }
        }
    }
    None
}

fn launch_external_editor(file_path: &Path) -> Result<()> {
    // Ensure the file exists (create with minimal content if new)
    if !file_path.exists() {
        if let Some(parent) = file_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let name = file_path.file_name().unwrap_or_default().to_string_lossy();
        let header = if name.contains("TASKS") || name.contains("IMPL_PLAN") {
            "# Task Queue\n\n"
        } else {
            "# Specification\n\n"
        };
        std::fs::write(file_path, header)?;
    }

    let editor = std::env::var("EDITOR")
        .ok()
        .filter(|v| !v.trim().is_empty())
        .unwrap_or_else(|| {
            if cfg!(target_os = "windows") {
                "notepad".to_string()
            } else {
                "nano".to_string()
            }
        });

    let status = if cfg!(target_os = "windows") {
        std::process::Command::new("cmd")
            .arg("/C")
            .arg(&editor)
            .arg(file_path)
            .status()
            .context("failed to launch editor")?
    } else {
        std::process::Command::new("sh")
            .arg("-c")
            .arg(format!("{} \"$FOUNDRY_TARGET_FILE\"", editor))
            .env("FOUNDRY_TARGET_FILE", file_path)
            .status()
            .context("failed to launch editor")?
    };

    if !status.success() {
        anyhow::bail!("editor exited with status {}", status);
    }

    Ok(())
}

fn spawn_build_loop(
    project_dir: &Path,
    _config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    shutdown: &Arc<AtomicBool>,
) -> Result<()> {
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;
    state.tasks_file_path = Some(plan_path.clone());
    state.tasks_file_mtime = std::fs::metadata(&plan_path)
        .and_then(|m| m.modified())
        .ok();
    if !plan_path.exists() {
        state.show_no_tasks_warning = true;
        anyhow::bail!(
            "{} not found — describe work or scan the project from startup first",
            plan_path.file_name().unwrap_or_default().to_string_lossy()
        );
    }

    let tasks = task::parse_tasks(&plan_path)?;
    state.update_counts(&tasks);
    state.task_queue = tasks.clone();
    state.current_task = None;
    state.next_task_hint = load_pending_task_at(project_dir, 0);
    state.log(format!(
        "Loop started -- {} tasks ({} done, {} pending)",
        state.total_count,
        state.completed_count,
        task::count_pending(&tasks)
    ));

    // Reload config from disk so settings-overlay writes (builder_provider,
    // builder_model, local_model, etc.) are honored by the build loop. The
    // startup-loaded `config` parameter is intentionally ignored here -- only
    // the four TUI-session toggles below are carried over from AppState.
    let mut loop_config = Config::load(project_dir);
    loop_config.run_mode = state.run_mode.clone();
    loop_config.dual_selection = state.dual_selection.as_str().to_string();
    loop_config.builder_models = state.builder_model_specs.clone();
    loop_config.extensions = state.selected_extension_names();

    state.review_gates.clear();
    state.review_session_id = None;
    state.pending_reviews.clear();
    state.awaiting_review = false;
    state.awaiting_pr = None;
    state.pr_poll_last_check = None;

    let mut run_context = RunContext::new(
        project_dir,
        loop_config,
        shutdown.clone(),
        state.tasks_file_lock.clone(),
    );
    run_context.session_cost_millicents = state.session_cost_millicents.clone();
    let loop_tx = event_tx.clone();
    tokio::spawn(async move {
        build::build_loop(run_context, loop_tx).await;
    });

    Ok(())
}

fn spawn_inline_planning(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    user_intent: Option<String>,
    label: String,
    shutdown: &Arc<AtomicBool>,
) {
    state.phase = AppPhase::Planning;
    state.startup = None;
    state.planning = Some(PlanningState {
        label: label.clone(),
        user_intent: user_intent.clone(),
        orchestrator_mode: false,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;
    state.set_agent(
        AgentRole::Planner,
        &Config::display_provider_model(&config.planner_provider, &config.planner_model),
    );
    state.log(format!("Planning started — {}", label));

    let run_context = RunContext::new(
        project_dir,
        config.clone(),
        shutdown.clone(),
        state.tasks_file_lock.clone(),
    );
    let event_tx = event_tx.clone();
    tokio::spawn(async move {
        planning::spawn_inline_planning_task(run_context, event_tx, user_intent).await;
    });
}

fn spawn_append_tasks(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    request: AppendTasksRequest,
    shutdown: &Arc<AtomicBool>,
) {
    let _ = config;
    if !prepare_append_tasks_start(
        project_dir,
        state,
        &request,
        commands::provider_binary_is_available(crate::agent::ModelProvider::Claude),
    ) {
        return;
    }

    state.phase = AppPhase::Planning;
    state.startup = None;
    state.planning = Some(PlanningState {
        label: request.label.clone(),
        user_intent: Some(request.description.clone()),
        orchestrator_mode: false,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;

    let mut working = Config::load(project_dir);
    let dual_sel = state.dual_selection.as_str().to_string();
    working.dual_selection = dual_sel.clone();
    working.builder_models = state.builder_model_specs.clone();
    let mut pipeline_configs = working.selected_pipeline_configs(&dual_sel);
    let effective_config = pipeline_configs.drain(..).next().unwrap_or(working);

    let run_context = RunContext::new(
        project_dir,
        effective_config,
        shutdown.clone(),
        state.tasks_file_lock.clone(),
    );
    let event_tx = event_tx.clone();
    tokio::spawn(async move {
        planning::run_append_tasks(run_context, event_tx, request.description).await;
    });
}

fn prepare_append_tasks_start(
    project_dir: &Path,
    state: &mut AppState,
    request: &AppendTasksRequest,
    _claude_available: bool,
) -> bool {
    // Task append uses an LLM to expand descriptions but works without
    // claude CLI (falls back gracefully). Check removed for simplicity.

    if request.seed_spec_from_description {
        if let Err(e) = seed_spec_from_brief(project_dir, &request.description) {
            let message = format!(
                "Cannot save {}: {}",
                ContractPaths::resolve(project_dir).spec_file_name(),
                e
            );
            state.log(message.clone());
            enter_startup_surface(project_dir, state, Some(message));
            return false;
        }
        state.log(format!(
            "Saved {} from the startup brief",
            ContractPaths::resolve(project_dir).spec_file_name()
        ));
    }

    true
}

pub(super) fn seed_spec_from_brief(project_dir: &Path, description: &str) -> Result<()> {
    let contract_paths = ContractPaths::resolve(project_dir);
    if contract_paths.spec_path.exists() {
        return Ok(());
    }

    if let Some(parent) = contract_paths.spec_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let project_name = project_dir
        .file_name()
        .unwrap_or_default()
        .to_string_lossy();
    let spec = format!("# Specification: {project_name}\n\n## Project Brief\n{description}\n");
    atomic_write_file(&contract_paths.spec_path, spec.as_bytes())?;
    Ok(())
}

fn handle_planning_event(state: &mut AppState, event: AppEvent, config: &Config) {
    match event {
        AppEvent::AgentOutput(output) => {
            handle_agent_output(state, output);
            if let Some(ref mut planning) = state.planning {
                if planning.orchestrator_mode {
                    if let Some(last_line) = state.agent_output.last() {
                        if let Some(rest) = last_line.strip_prefix("[orchestrator] Iteration ") {
                            if let Some(slash_pos) = rest.find('/') {
                                if let Ok(iter_num) = rest[..slash_pos].parse::<usize>() {
                                    planning.orchestrator_iteration = iter_num;
                                }
                            }
                            if rest.contains("proposer") {
                                planning.orchestrator_role_label = Some("Proposing".to_string());
                                if let Some(paren_open) = rest.find('(') {
                                    if let Some(paren_close) = rest.find(')') {
                                        if paren_close > paren_open + 1 {
                                            planning.orchestrator_role_model =
                                                Some(rest[paren_open + 1..paren_close].to_string());
                                        }
                                    }
                                }
                            }
                        }
                        if let Some(rest) = last_line.strip_prefix("[orchestrator] Reviewing with ")
                        {
                            planning.orchestrator_role_label = Some("Reviewing".to_string());
                            let model_str = rest.trim_end_matches("...");
                            if !model_str.is_empty() {
                                planning.orchestrator_role_model = Some(model_str.to_string());
                            }
                        }
                        if let Some(rest) = last_line.strip_prefix("[orchestrator] Review: ") {
                            if let Some(paren_start) = rest.find('(') {
                                let after_paren = &rest[paren_start + 1..];
                                if let Some(space) = after_paren.find(' ') {
                                    if let Ok(count) = after_paren[..space].parse::<usize>() {
                                        planning.orchestrator_finding_count = count;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        AppEvent::AgentDone(success) => handle_agent_done(state, success),

        AppEvent::DualPipelineEvent(idx, inner) => {
            handle_dual_pipeline_event(state, idx, *inner, config)
        }
        AppEvent::PlanningFinished(outcome) => apply_planning_outcome(state, outcome),
        AppEvent::OrchestratorFinished(outcome) => apply_orchestrator_outcome(state, outcome),
        AppEvent::Key(key) => handle_planning_key(state, key, config),
        AppEvent::Mouse(mouse) => {
            use crossterm::event::{MouseButton, MouseEventKind};
            if matches!(mouse.kind, MouseEventKind::Down(MouseButton::Left)) {
                let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                if state.confirm_quit {
                    let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                    if let Some(action) = tui::quit_confirm_hit_test(area, mouse.column, mouse.row)
                    {
                        match action {
                            tui::QuitConfirmAction::Quit => state.should_quit = true,
                            tui::QuitConfirmAction::Cancel => state.confirm_quit = false,
                        }
                    }
                    return;
                }
                if handle_settings_overlay_mouse(state, mouse, terminal_size) {
                    return;
                }
                let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                let chunks = ratatui::layout::Layout::default()
                    .direction(ratatui::layout::Direction::Vertical)
                    .constraints([
                        ratatui::layout::Constraint::Length(5),
                        ratatui::layout::Constraint::Length(9),
                        ratatui::layout::Constraint::Min(8),
                        ratatui::layout::Constraint::Length(8),
                        ratatui::layout::Constraint::Length(1),
                    ])
                    .split(area);
                let status_bar = chunks[4];
                if mouse.row == status_bar.y {
                    if let Some(action) =
                        tui::running_status_bar_hit_test(status_bar, mouse.column, state)
                    {
                        match action {
                            tui::RunningStatusBarAction::Quit => {
                                state.confirm_quit = true;
                            }
                            tui::RunningStatusBarAction::Settings => {
                                toggle_settings_overlay(state);
                            }
                            tui::RunningStatusBarAction::Patterns => {
                                state.show_patterns = !state.show_patterns;
                                if state.show_patterns {
                                    refresh_skill_citation_summary(state);
                                }
                            }
                            tui::RunningStatusBarAction::Findings => {
                                state.show_findings = !state.show_findings;
                            }
                            _ => {}
                        }
                    }
                }
            }
        }
        AppEvent::Paste(_) => {}
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
            let needs_refresh = match state.skill_citation_summary_loaded_at {
                None => true,
                Some(last) => last.elapsed() >= std::time::Duration::from_secs(30),
            };
            if needs_refresh {
                refresh_skill_citation_summary(state);
            }
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
        AppEvent::OllamaStatus(connected) => {
            state.last_pattern_match_mode = Some(
                if connected {
                    "semantic"
                } else {
                    "keyword-only"
                }
                .to_string(),
            );
        }
        AppEvent::CatalogRefreshed(messages) => {
            for line in messages {
                state.log(line);
            }
        }
        AppEvent::LocalModels {
            lmstudio,
            ollama,
            lmstudio_opencode_map,
            opencode_warning,
            claude_available,
            codex_available,
            copilot_available,
        } => {
            let mut merged: Vec<String> = Vec::with_capacity(lmstudio.len() + ollama.len());
            for m in lmstudio.iter().chain(ollama.iter()) {
                if !merged.contains(m) {
                    merged.push(m.clone());
                }
            }
            state.lmstudio_models = lmstudio;
            state.ollama_models = ollama;
            state.local_models = merged;
            state.lmstudio_id_to_opencode_path = lmstudio_opencode_map;
            state.claude_cli_available = claude_available;
            state.codex_cli_available = codex_available;
            state.copilot_available = copilot_available;
            if let Some(msg) = opencode_warning {
                state.log(msg);
            }
            init_builder_cursor(state);
        }
        AppEvent::LoopEvent(LoopEvent::StatsReady(report)) => {
            if state.stats_loading {
                state.stats_overlay_report = Some(*report);
                state.show_stats_overlay = true;
                state.stats_overlay_scroll = 0;
            }
            state.stats_loading = false;
        }
        AppEvent::LoopEvent(LoopEvent::StatsLoadFailed) => {
            state.stats_loading = false;
            state.log("Stats: failed to load events".to_string());
        }
        AppEvent::WelcomeMessage(msg) => {
            if state.show_welcome {
                state.welcome_message = msg;
            }
        }
        AppEvent::SurfaceSummaryReady { .. } => {}
        AppEvent::NarrativeRefresh(brief) => {
            state.last_commit_brief = brief;
        }
        AppEvent::LoopEvent(_) => {}
    }
}

/// Close the settings overlay if it is open. Returns true when it consumed
/// the key (caller should return early). Called as the FIRST check in every
/// Esc handler so the overlay always wins.
pub(crate) fn handle_overlay_esc(state: &mut AppState) -> bool {
    if state.show_settings_overlay {
        // Three-level Esc: picker → confirm banner → close
        if let Some(ref mut ov) = state.settings_overlay {
            if ov.picker.is_some() {
                ov.picker = None;
                return true;
            }
            if ov.confirm_close {
                ov.confirm_close = false;
                return true;
            }
            if ov.dirty {
                ov.confirm_close = true;
                return true;
            }
        }
        state.show_settings_overlay = false;
        state.settings_overlay = None;
        return true;
    }
    false
}

fn handle_running_modal_key(
    state: &mut AppState,
    key: event::KeyEvent,
    kind: RunningModalKind,
) {
    match kind {
        RunningModalKind::StopRun => match key.code {
            KeyCode::Char('y') | KeyCode::Char('Y') | KeyCode::Enter => {
                state.running_screen_modal = None;
                state.stop_after_task = true;
                state.write_stop_file();
                state.log("Stopping after current stage completes");
            }
            KeyCode::Char('n') | KeyCode::Char('N') | KeyCode::Esc => {
                state.running_screen_modal = None;
            }
            _ => {}
        },
        RunningModalKind::CtrlC => {
            if matches!(key.code, KeyCode::Char('c'))
                && key.modifiers.contains(KeyModifiers::CONTROL)
            {
                // Second Ctrl+C while modal open: force-quit immediately. Preserves muscle memory.
                state.running_screen_modal = None;
                state.remove_stop_file();
                state.should_quit = true;
                return;
            }
            match key.code {
                KeyCode::Char('1') => {
                    state.running_screen_modal = None;
                    state.stop_after_task = true;
                    state.write_stop_file();
                    state.should_quit = true;
                    state.log("Stopping run and exiting Foundry");
                }
                KeyCode::Char('2') => {
                    state.running_screen_modal = None;
                    state.stop_after_task = true;
                    state.write_stop_file();
                    state.log("Stopping run -- returning to startup screen");
                    let project_dir = state
                        .buildloop_dir
                        .parent()
                        .unwrap_or(std::path::Path::new("."))
                        .to_path_buf();
                    enter_home_surface(
                        &project_dir,
                        state,
                        Some("Run stopped by user".to_string()),
                    );
                }
                KeyCode::Char('3') | KeyCode::Esc => {
                    state.running_screen_modal = None;
                }
                _ => {}
            }
        }
    }
}

/// Toggle the settings overlay open/closed. Initializes SettingsOverlayState
/// on open. Returns true when newly opened (caller should fetch local models).
fn toggle_settings_overlay(state: &mut AppState) -> bool {
    let was_open = state.show_settings_overlay;
    state.show_settings_overlay = !state.show_settings_overlay;
    state.settings_overlay_cursor = 0;
    if !was_open {
        let dual = state.arena_mode == "dual";
        let mut ov = state::SettingsOverlayState::with_dual_mode(dual);
        let project_dir = state.buildloop_dir.parent().unwrap_or(Path::new("."));
        let config_path = project_dir.join(".foundry.json");
        ov.original_json = std::fs::read_to_string(&config_path).ok();
        ov.eval_report_cache = eval_report::read_report(&state.buildloop_dir);
        if ov.eval_report_cache.is_some() && ov.eval_pipeline_health_first_view {
            ov.expanded_sections.insert("pipeline_health".to_string());
            ov.eval_pipeline_health_first_view = false;
        }
        // Populate Patterns Detail snapshot. AppState does not currently track
        // per-session injected pattern ids, so injected_ids is empty -- the
        // "Injected this session" filter renders header + buttons only until
        // the user toggles to All. Future work may thread the live set in.
        let global_patterns = crate::patterns::load_patterns_from_global();
        ov.patterns_section_cache = Some(state::PatternsSectionSnapshot {
            all: global_patterns,
            injected_ids: std::collections::BTreeSet::new(),
            filter: state::PatternsFilter::InjectedThisSession,
        });
        if ov.patterns_section_cache.is_some() && ov.patterns_section_first_view {
            ov.expanded_sections.insert("patterns_detail".to_string());
            ov.patterns_section_first_view = false;
        }
        state.settings_overlay = Some(ov);
        state.eval_report_cache = state
            .settings_overlay
            .as_ref()
            .and_then(|o| o.eval_report_cache.clone());
        sync_settings_overlay_view(state);
        true
    } else {
        state.settings_overlay = None;
        false
    }
}

fn mark_settings_dirty(state: &mut AppState) {
    if let Some(ref mut ov) = state.settings_overlay {
        ov.dirty = true;
    }
}

fn refresh_eval_report_cache(state: &mut AppState) {
    // Probe mtime BEFORE reading content. If an atomic rename happens
    // between probe and read, we end up with a fresh snapshot paired
    // with a slightly-older mtime, which the staleness predicate
    // handles conservatively (marks as stale for one extra render
    // cycle until the next refresh). The reverse order would let an
    // old snapshot pair with a fresh mtime -- exactly the false-fresh
    // bug T1.29 is fixing.
    let mtime = std::fs::metadata(
        state
            .buildloop_dir
            .join(eval_report::EVAL_REPORT_FILENAME),
    )
    .ok()
    .and_then(|m| m.modified().ok());
    let snap = eval_report::read_report(&state.buildloop_dir);
    state.eval_report_cache = snap.clone();
    state.eval_report_mtime = mtime;
    if let Some(ref mut ov) = state.settings_overlay {
        ov.eval_report_cache = snap;
    }
}

fn overlay_project_dir(state: &AppState) -> &Path {
    state.buildloop_dir.parent().unwrap_or(Path::new("."))
}

fn flush_settings_to_disk(state: &mut AppState) {
    let project_dir = overlay_project_dir(state).to_path_buf();
    let config = Config::load(&project_dir);

    // Collect all lmstudio model IDs from current config
    let mut lmstudio_models: Vec<String> = Vec::new();
    for spec in &config.builder_models {
        if let Some(model_part) = spec.strip_prefix("opencode:lmstudio/") {
            lmstudio_models.push(model_part.to_string());
        }
    }
    if config.builder_model.starts_with("lmstudio/") {
        lmstudio_models.push(
            config
                .builder_model
                .trim_start_matches("lmstudio/")
                .to_string(),
        );
    }
    for so in &config.stage_overrides {
        // Format: "stage:provider:model" e.g. "build:opencode:lmstudio/foo"
        if let Some((_stage, rest)) = so.split_once(':') {
            if let Some(model_part) = rest.strip_prefix("opencode:lmstudio/") {
                lmstudio_models.push(model_part.to_string());
            }
        }
    }
    lmstudio_models.sort();
    lmstudio_models.dedup();

    // Compare with original to only load new models
    let original_models: Vec<String> = state
        .settings_overlay
        .as_ref()
        .and_then(|ov| ov.original_json.as_ref())
        .and_then(|json| serde_json::from_str::<serde_json::Value>(json).ok())
        .map(|val| {
            let mut models = Vec::new();
            if let Some(bm) = val.get("builder_model").and_then(|v| v.as_str()) {
                if let Some(m) = bm.strip_prefix("lmstudio/") {
                    models.push(m.to_string());
                }
            }
            if let Some(arr) = val.get("builder_models").and_then(|v| v.as_array()) {
                for item in arr {
                    if let Some(s) = item.as_str() {
                        if let Some(m) = s.strip_prefix("opencode:lmstudio/") {
                            models.push(m.to_string());
                        }
                    }
                }
            }
            models
        })
        .unwrap_or_default();

    for model in &lmstudio_models {
        if !original_models.contains(model) {
            trigger_lmstudio_load(model.clone());
        }
    }
}

fn trigger_lmstudio_load(model_id: String) {
    tokio::spawn(tokio::task::spawn_blocking(move || {
        let body = serde_json::json!({"model": model_id});
        let _ = std::process::Command::new("curl")
            .args([
                "-s",
                "--max-time",
                "10",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                &body.to_string(),
                "http://127.0.0.1:1234/v1/models/load",
            ])
            .output();
    }));
}

fn fetch_welcome_message(ollama_url: &str) -> Option<String> {
    let prompt = "Write ONE short creative piece for a CLI tool splash screen. \
        Pick randomly: a haiku, a riddle, a witty saying, a rhyming couplet, \
        or a fun programming proverb. Theme: code, building, forging, patterns, \
        or learning from mistakes. Keep it positive and under 4 lines. \
        Output ONLY the piece, no labels or explanation.";

    let body = serde_json::json!({
        "model": "llama3.2",
        "prompt": prompt,
        "stream": false,
        "options": { "temperature": 1.2, "num_predict": 80 }
    });

    let out = std::process::Command::new("curl")
        .args([
            "-s",
            "--max-time",
            "5",
            "-X",
            "POST",
            "-H",
            "Content-Type: application/json",
            "-d",
            &body.to_string(),
            &format!("{}/api/generate", ollama_url),
        ])
        .output()
        .ok()?;

    if !out.status.success() {
        return None;
    }

    let val: serde_json::Value = serde_json::from_slice(&out.stdout).ok()?;
    let response = val.get("response")?.as_str()?.trim().to_string();
    if response.is_empty() || response.len() > 500 {
        return None;
    }
    Some(response)
}

fn discard_settings_changes(state: &mut AppState) {
    let project_dir = overlay_project_dir(state).to_path_buf();
    if let Some(ref original) = state
        .settings_overlay
        .as_ref()
        .and_then(|ov| ov.original_json.clone())
    {
        let config_path = project_dir.join(".foundry.json");
        let _ = std::fs::write(&config_path, original);
    }
    let config = Config::load(&project_dir);
    state.run_mode = config.run_mode.clone();
    state.tui_theme = crate::tui::theme::from_name(&config.theme);
    state.dual_selection = state::DualSelection::from_str(&config.dual_selection);
}

fn load_settings_config(state: &AppState) -> Config {
    Config::load(overlay_project_dir(state))
}

fn settings_field_kind(field_id: &str) -> state::FieldKind {
    state::settings_sections(true)
        .iter()
        .flat_map(|section| section.fields.iter())
        .find(|field| field.id == field_id)
        .map(|field| field.kind)
        .unwrap_or(state::FieldKind::Readonly)
}

fn begin_inline_edit(state: &mut AppState, field_id: &str) {
    let config = load_settings_config(state);
    if let Some(ref mut ov) = state.settings_overlay {
        ov.editing = Some(state::InlineEdit {
            field_id: field_id.to_string(),
            buffer: config.field_value(field_id),
            error: None,
        });
    }
}

fn commit_inline_edit(state: &mut AppState) {
    let (field_id, buffer) = {
        let Some(ov) = state.settings_overlay.as_ref() else {
            return;
        };
        let Some(editing) = ov.editing.as_ref() else {
            return;
        };
        (editing.field_id.clone(), editing.buffer.clone())
    };

    match Config::save_field(overlay_project_dir(state), &field_id, &buffer) {
        Ok(()) => {
            apply_field_to_state(state, &field_id, &buffer);
            mark_settings_dirty(state);
            if let Some(ref mut ov) = state.settings_overlay {
                ov.editing = None;
            }
        }
        Err(error) => {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut editing) = ov.editing {
                    editing.error = Some(error);
                }
            }
        }
    }
}

pub(super) fn sync_settings_overlay_view(state: &mut AppState) {
    let Some(ov) = state.settings_overlay.as_mut() else {
        return;
    };
    let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
    let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
    let modal = tui::settings_modal_rect(area);
    let visible_rows = modal.height.saturating_sub(4).max(1) as usize;
    ov.ensure_focus_visible(visible_rows);
    if let Some(ref mut picker) = ov.picker {
        picker.clamp_focus();
    }
}

pub(super) fn handle_settings_overlay_key(state: &mut AppState, key: event::KeyEvent) -> bool {
    if !state.show_settings_overlay {
        return false;
    }

    // Confirm-close banner intercepts all keys
    if state
        .settings_overlay
        .as_ref()
        .is_some_and(|ov| ov.confirm_close)
    {
        match key.code {
            KeyCode::Char('y') | KeyCode::Char('Y') => {
                flush_settings_to_disk(state);
                state.show_settings_overlay = false;
                state.settings_overlay = None;
            }
            KeyCode::Char('n') | KeyCode::Char('N') => {
                discard_settings_changes(state);
                state.show_settings_overlay = false;
                state.settings_overlay = None;
            }
            KeyCode::Esc => {
                if let Some(ref mut ov) = state.settings_overlay {
                    ov.confirm_close = false;
                }
            }
            _ => {}
        }
        return true;
    }

    match key.code {
        KeyCode::Esc | KeyCode::Char('q') => {
            handle_overlay_esc(state);
            return true;
        }
        _ => {}
    }

    let is_editing = state
        .settings_overlay
        .as_ref()
        .and_then(|ov| ov.editing.as_ref())
        .is_some();
    if is_editing {
        let field_id = state
            .settings_overlay
            .as_ref()
            .and_then(|ov| ov.editing.as_ref())
            .map(|editing| editing.field_id.clone())
            .unwrap_or_default();
        let field_kind = settings_field_kind(&field_id);
        match key.code {
            KeyCode::Enter => commit_inline_edit(state),
            KeyCode::Backspace => {
                if let Some(ref mut ov) = state.settings_overlay {
                    if let Some(ref mut editing) = ov.editing {
                        editing.buffer.pop();
                        editing.error = None;
                    }
                }
            }
            KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                if let Some(ref mut ov) = state.settings_overlay {
                    if let Some(ref mut editing) = ov.editing {
                        editing.buffer.clear();
                        editing.error = None;
                    }
                }
            }
            KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                let accepts_char = match field_kind {
                    state::FieldKind::Editor => true,
                    state::FieldKind::Number => c.is_ascii_digit() || matches!(c, '.' | '-'),
                    _ => false,
                };
                if accepts_char {
                    if let Some(ref mut ov) = state.settings_overlay {
                        if let Some(ref mut editing) = ov.editing {
                            editing.buffer.push(c);
                            editing.error = None;
                        }
                    }
                }
            }
            _ => {}
        }
        return true;
    }

    match key.code {
        KeyCode::Enter | KeyCode::Char(' ') => {
            if state
                .settings_overlay
                .as_ref()
                .is_some_and(|ov| ov.picker.is_some())
            {
                handle_picker_select(state);
            } else {
                handle_settings_action(state);
            }
        }
        KeyCode::Left
            if state
                .settings_overlay
                .as_ref()
                .is_some_and(|ov| ov.picker.is_none()) =>
        {
            handle_settings_left(state);
        }
        KeyCode::Right
            if state
                .settings_overlay
                .as_ref()
                .is_some_and(|ov| ov.picker.is_none()) =>
        {
            handle_settings_right(state);
        }
        KeyCode::Char('/')
            if state
                .settings_overlay
                .as_ref()
                .is_some_and(|ov| ov.picker.is_some()) =>
        {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.filtering = true;
                }
            }
        }
        KeyCode::Char(c)
            if state
                .settings_overlay
                .as_ref()
                .is_some_and(|ov| ov.picker.as_ref().is_some_and(|picker| picker.filtering)) =>
        {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.filter.push(c);
                    picker.focus = 0;
                    picker.clamp_focus();
                }
            }
        }
        KeyCode::Backspace
            if state
                .settings_overlay
                .as_ref()
                .is_some_and(|ov| ov.picker.as_ref().is_some_and(|picker| picker.filtering)) =>
        {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.filter.pop();
                    if picker.filter.is_empty() {
                        picker.filtering = false;
                    }
                    picker.focus = 0;
                    picker.clamp_focus();
                }
            }
        }
        KeyCode::Up => {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.focus = picker.focus.saturating_sub(1);
                    picker.clamp_focus();
                } else {
                    ov.focus = ov.focus.saturating_sub(1);
                }
            }
            sync_settings_overlay_view(state);
        }
        KeyCode::Down => {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.focus = (picker.focus + 1).min(picker.visible_count().saturating_sub(1));
                    picker.clamp_focus();
                } else {
                    ov.focus = (ov.focus + 1).min(ov.visible_row_count().saturating_sub(1));
                }
            }
            sync_settings_overlay_view(state);
        }
        _ => {}
    }
    true
}

pub(super) fn handle_settings_overlay_mouse(
    state: &mut AppState,
    mouse: crossterm::event::MouseEvent,
    terminal_size: (u16, u16),
) -> bool {
    use crossterm::event::{MouseButton, MouseEventKind};

    if !state.show_settings_overlay {
        return false;
    }

    match mouse.kind {
        MouseEventKind::ScrollUp => {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.focus = picker.focus.saturating_sub(1);
                    picker.clamp_focus();
                } else {
                    ov.focus = ov.focus.saturating_sub(1);
                }
            }
            sync_settings_overlay_view(state);
            return true;
        }
        MouseEventKind::ScrollDown => {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.focus = (picker.focus + 1).min(picker.visible_count().saturating_sub(1));
                    picker.clamp_focus();
                } else {
                    ov.focus = (ov.focus + 1).min(ov.visible_row_count().saturating_sub(1));
                }
            }
            sync_settings_overlay_view(state);
            return true;
        }
        MouseEventKind::Down(MouseButton::Left) => {}
        _ => return true,
    }

    let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
    let modal = tui::settings_modal_rect(area);

    if state
        .settings_overlay
        .as_ref()
        .is_some_and(|ov| ov.confirm_close)
    {
        if let Some(action) = tui::confirm_banner_hit_test(modal, mouse.column, mouse.row) {
            match action {
                tui::ConfirmBannerAction::Save => {
                    flush_settings_to_disk(state);
                    state.show_settings_overlay = false;
                    state.settings_overlay = None;
                }
                tui::ConfirmBannerAction::Discard => {
                    discard_settings_changes(state);
                    state.show_settings_overlay = false;
                    state.settings_overlay = None;
                }
                tui::ConfirmBannerAction::Back => {
                    if let Some(ref mut ov) = state.settings_overlay {
                        ov.confirm_close = false;
                    }
                }
            }
        }
        return true;
    }

    let btn = tui::close_btn_rect(modal);
    if tui::rect_contains(btn, mouse.column, mouse.row)
        || !tui::rect_contains(modal, mouse.column, mouse.row)
    {
        handle_overlay_esc(state);
        return true;
    }

    enum OverlayMouseAction {
        PickerClose,
        PickerFilter,
        PickerItem(usize),
        Row(usize),
        None,
    }

    let action = {
        let Some(ov) = state.settings_overlay.as_ref() else {
            return true;
        };
        if let Some(ref picker) = ov.picker {
            match tui::model_picker_hit_test(modal, picker, mouse.column, mouse.row) {
                Some(tui::ModelPickerMouseTarget::CloseBtn)
                | Some(tui::ModelPickerMouseTarget::OutsideClick) => {
                    OverlayMouseAction::PickerClose
                }
                Some(tui::ModelPickerMouseTarget::FilterBar) => OverlayMouseAction::PickerFilter,
                Some(tui::ModelPickerMouseTarget::Item(index)) => {
                    OverlayMouseAction::PickerItem(index)
                }
                None => OverlayMouseAction::None,
            }
        } else if let Some(index) =
            tui::settings_overlay_row_hit_test(modal, ov.scroll_offset, mouse.column, mouse.row)
        {
            OverlayMouseAction::Row(index)
        } else {
            OverlayMouseAction::None
        }
    };

    match action {
        OverlayMouseAction::PickerClose => {
            if let Some(ref mut ov) = state.settings_overlay {
                ov.picker = None;
            }
        }
        OverlayMouseAction::PickerFilter => {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.filtering = true;
                }
            }
        }
        OverlayMouseAction::PickerItem(index) => {
            if let Some(ref mut ov) = state.settings_overlay {
                if let Some(ref mut picker) = ov.picker {
                    picker.focus = index;
                    picker.clamp_focus();
                }
            }
            handle_picker_select(state);
        }
        OverlayMouseAction::Row(index) => {
            let row = state
                .settings_overlay
                .as_ref()
                .and_then(|ov| ov.row_at_index(index));
            if let Some(ref mut ov) = state.settings_overlay {
                ov.focus = index;
            }
            sync_settings_overlay_view(state);
            if let Some(row) = row {
                settings_action_for_row(state, &row);
            }
            sync_settings_overlay_view(state);
        }
        OverlayMouseAction::None => {}
    }

    true
}

fn handle_planning_key(state: &mut AppState, key: event::KeyEvent, config: &Config) {
    if state.confirm_quit {
        match key.code {
            KeyCode::Char('y') | KeyCode::Char('Y') | KeyCode::Enter => {
                state.should_quit = true;
            }
            KeyCode::Char('n') | KeyCode::Char('N') | KeyCode::Esc => state.confirm_quit = false,
            _ => {}
        }
        return;
    }
    match key.code {
        KeyCode::Char('q') | KeyCode::Esc => {
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() {
                state.surface_summary_overlay = None;
                return;
            }
            if handle_overlay_esc(state) {
                return;
            }
            if state.show_stats_overlay {
                state.show_stats_overlay = false;
                state.stats_loading = false;
                state.stats_overlay_report = None;
                state.stats_overlay_scroll = 0;
            } else {
                state.confirm_quit = true;
            }
        }
        KeyCode::Char('r')
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() =>
        {
            let Some(overlay) = state.surface_summary_overlay.as_ref().cloned() else {
                return;
            };
            let project_dir = state
                .buildloop_dir
                .parent()
                .unwrap_or(std::path::Path::new("."))
                .to_path_buf();
            trigger_surface_summary(
                state,
                &project_dir,
                config,
                overlay.surface.clone(),
                true,
            );
        }
        KeyCode::Char('f')
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() =>
        {
            let Some(overlay) = state.surface_summary_overlay.as_ref().cloned() else {
                return;
            };
            let project_dir = state
                .buildloop_dir
                .parent()
                .unwrap_or(std::path::Path::new("."))
                .to_path_buf();
            surface_open_file(state, &project_dir, config, &overlay);
        }
        // Scroll the AI summary body. Keys claim the event only when the
        // overlay is open so they don't steal Up/Down from the running screen.
        KeyCode::Up
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() =>
        {
            if let Some(o) = state.surface_summary_overlay.as_mut() {
                o.scroll_offset = o.scroll_offset.saturating_sub(1);
            }
        }
        KeyCode::Down
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() =>
        {
            if let Some(o) = state.surface_summary_overlay.as_mut() {
                o.scroll_offset = o.scroll_offset.saturating_add(1);
            }
        }
        KeyCode::PageUp
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() =>
        {
            if let Some(o) = state.surface_summary_overlay.as_mut() {
                o.scroll_offset = o.scroll_offset.saturating_sub(8);
            }
        }
        KeyCode::PageDown
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() =>
        {
            if let Some(o) = state.surface_summary_overlay.as_mut() {
                o.scroll_offset = o.scroll_offset.saturating_add(8);
            }
        }
        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.should_quit = true;
        }
        KeyCode::Char('s') if !key.modifiers.contains(KeyModifiers::CONTROL) => {
            if state.show_stats_overlay {
                state.show_stats_overlay = false;
                state.stats_loading = false;
                state.stats_overlay_report = None;
                state.stats_overlay_scroll = 0;
            } else {
                compute_and_show_stats_overlay(state);
            }
        }
        KeyCode::Char('f') if state.last_orchestrator_outcome.is_some() => {
            state.show_findings = !state.show_findings;
            state.findings_scroll = 0;
        }
        KeyCode::Char('p') => {
            state.show_patterns = !state.show_patterns;
            if state.show_patterns {
                refresh_patterns_cache(state, config);
                refresh_skill_citation_summary(state);
            }
        }
        // Sandbox toggle removed -- config-only override for implementers.
        KeyCode::Char('s') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.log("Sandbox toggle disabled -- override via .foundry.json only".to_string());
        }
        KeyCode::Char('t') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
            state.tui_theme = new_theme;
            state.log(format!("Theme: {}", name));
        }
        KeyCode::Char('?') if toggle_settings_overlay(state) => {
            if let Some(tx) = state.event_tx.clone() {
                let ollama_url = config.ollama_url.clone();
                tokio::spawn(async move {
                    let discovery = fetch_available_models(ollama_url).await;
                    let _ = tx.send(AppEvent::LocalModels {
                        lmstudio: discovery.lmstudio,
                        ollama: discovery.ollama,
                        lmstudio_opencode_map: discovery.lmstudio_opencode_map,
                        opencode_warning: discovery.opencode_warning,
                        claude_available: discovery.claude_available,
                        codex_available: discovery.codex_available,
                        copilot_available: discovery.copilot_available,
                    });
                });
            }
        }
        _ if handle_settings_overlay_key(state, key) => {}
        KeyCode::Up => {
            if state.settings_overlay.is_some() {
                return;
            }
            if state.show_stats_overlay {
                state.stats_overlay_scroll = state.stats_overlay_scroll.saturating_sub(3);
            } else if state.show_findings {
                state.findings_scroll = state.findings_scroll.saturating_sub(3);
            } else if state.show_patterns {
                state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
            } else {
                let max = state.agent_output.len().saturating_sub(1);
                state.scroll_offset = state.scroll_offset.saturating_add(3).min(max);
            }
        }
        KeyCode::Down => {
            if state.settings_overlay.is_some() {
                return;
            }
            if state.show_stats_overlay {
                state.stats_overlay_scroll = state.stats_overlay_scroll.saturating_add(3);
            } else if state.show_findings {
                state.findings_scroll = state.findings_scroll.saturating_add(3);
            } else if state.show_patterns {
                state.patterns_scroll = state.patterns_scroll.saturating_add(3);
            } else {
                state.scroll_offset = state.scroll_offset.saturating_sub(3);
            }
        }
        KeyCode::PageUp => {
            let max = state.task_queue.len().saturating_sub(1);
            state.task_queue_scroll = state.task_queue_scroll.saturating_add(3).min(max);
        }
        KeyCode::PageDown => {
            state.task_queue_scroll = state.task_queue_scroll.saturating_sub(3);
        }
        _ => {}
    }
}

fn handle_event(state: &mut AppState, event: AppEvent, config: &Config) {
    match event {
        AppEvent::AgentOutput(output) => handle_agent_output(state, output),

        AppEvent::DualPipelineEvent(idx, inner) => {
            handle_dual_pipeline_event(state, idx, *inner, config)
        }
        AppEvent::AgentDone(success) => handle_agent_done(state, success),
        AppEvent::LoopEvent(le) => match le {
            LoopEvent::TaskStarted(task) => {
                state.log(format!("Task {} started", task.id));
                state.current_task = Some(task);
                state.task_start = Some(chrono::Utc::now());
                state.task_stages_seen.clear();
                state.active_pattern_keywords.clear();
                state.spid_context_pcts = [None; 5];
                state.stage_context_pcts.clear();
                state.clear_agent();
                state.current_classification = None;
            }
            LoopEvent::TaskClassified {
                task_id,
                tier,
                override_flag,
                p_plus_cycles_budget,
            } => {
                let override_suffix = if matches!(override_flag, TaskOverride::None) {
                    String::new()
                } else {
                    format!(" [{}]", override_flag.label())
                };
                state.log(format!(
                    "Task {} classified {:?}{} (P+ budget {})",
                    task_id, tier, override_suffix, p_plus_cycles_budget,
                ));
                state.current_classification = Some(CurrentClassification {
                    tier,
                    override_flag,
                    p_plus_cycles_budget,
                });
            }
            LoopEvent::AgentStarted(role, model) => {
                state.log(format!("{} spawned ({})", role, model));
                if !state.task_stages_seen.contains(&role) {
                    state.task_stages_seen.push(role.clone());
                }
                state.set_agent(role, &model);
            }
            LoopEvent::AgentStageStarted {
                role,
                stage_id,
                model,
            } => {
                state.log(format!("{} spawned for {} ({})", role, stage_id, model));
                if AgentRole::from_str(&stage_id)
                    .and_then(|stage_role| stage_role.qrpba_slot())
                    .is_some()
                    && !state.task_stages_seen.contains(&role)
                {
                    state.task_stages_seen.push(role.clone());
                }
                state.set_agent_for_stage(role, &model, stage_id);
            }
            LoopEvent::DualBuildStarted { models } => {
                state.dual_build = state::DualBuildState {
                    active: true,
                    streams: [Vec::new(), Vec::new()],
                    event_counts: [0, 0],
                    models: models.clone(),
                    tab: 0,
                    cost_usd: [0.0, 0.0],
                    input_tokens: [0, 0],
                    output_tokens: [0, 0],
                    context_pcts: [[None; 5]; 2],
                    stage_context_pcts: Default::default(),
                    finished: [false, false],
                    stages: [None, None],
                    stage_ids: [None, None],
                    stage_models: [String::new(), String::new()],
                    last_event_was_delta: [false, false],
                };
                state.log(format!(
                    "Dual pipeline started: {} vs {}",
                    models[0], models[1]
                ));
            }
            LoopEvent::DualBuildStreamDone(idx, success) => {
                if idx < 2 {
                    state.dual_build.finished[idx] = true;
                    let status = if success { "completed" } else { "failed" };
                    state.log(format!(
                        "Pipeline {} ({}): {}",
                        idx + 1,
                        state.dual_build.models[idx],
                        status
                    ));
                }
            }
            LoopEvent::TaskCompleted(id, success) => {
                state.reset_dual_build();
                let status = if success { "done" } else { "WIP" };
                if success {
                    state.session_feat_commits += 1;
                } else {
                    state.session_wip_commits += 1;
                }
                state.log(format!("Task {} — {}", id, status));
                // Save stages into history (review result may arrive separately)
                if !state.task_history.contains_key(&id) {
                    state.task_history_order.push(id.clone());
                }
                let history = state.task_history.entry(id.clone()).or_default();
                history.stages_seen = state.task_stages_seen.clone();
                // If task succeeded and no TaskReviewResult arrived yet,
                // mark as passed so the icon shows green (not default false)
                if success && history.fix_passes == 0 {
                    history.passed_review = true;
                }
                state.cap_task_history();
                state.current_task = None;
                state.task_start = None;
                state.task_stages_seen.clear();
                state.clear_agent();
                state.ship_active = false;
                refresh_eval_report_cache(state);
                if let Some(ref mut ov) = state.settings_overlay {
                    ov.eval_pipeline_health_first_view = true;
                    ov.patterns_section_first_view = true;
                }
            }
            LoopEvent::TaskReport { .. } => {
                // TaskReport is consumed by headless mode only; TUI ignores it.
            }
            LoopEvent::NextTaskUpdated(next_task) => {
                state.next_task_hint = next_task;
            }
            LoopEvent::DiscoveryStarted(round) => {
                state.is_discovering = true;
                state.discovery_round = round;
                state.log(format!("Discovery round {} started", round));
                state.clear_agent();
            }
            LoopEvent::DiscoveryCompleted(new_count) => {
                state.is_discovering = false;
                state.log(format!("Discovery found {} new tasks", new_count));
            }
            LoopEvent::ExtensionKeywordsLoaded { ref keywords } => {
                state.extension_keywords = keywords.clone();
            }
            LoopEvent::ExtensionInjected {
                ref name,
                ref agent_role,
                ref task_id,
            } => {
                state.session_extensions_used.push(state::ExtensionEvent {
                    name: name.clone(),
                    agent_role: agent_role.clone(),
                    task_id: task_id.clone(),
                });
                *state
                    .extension_inject_count
                    .entry(name.clone())
                    .or_insert(0) += 1;
            }
            LoopEvent::PatternsUsed {
                ref titles,
                ref keywords_by_title,
            } => {
                for title in titles {
                    state.session_patterns.push(state::PatternEvent {
                        title: title.clone(),
                        kind: state::PatternEventKind::Used,
                    });
                }
                state.pattern_inject_count += titles.len();
                state.active_pattern_keywords = keywords_by_title.clone();
            }
            LoopEvent::SkillCitationsRecorded { ref skill_names } => {
                state.session_skill_citation_count += skill_names.len();
                for name in skill_names {
                    state.session_skill_citations_set.insert(name.clone());
                }
                refresh_skill_citation_summary(state);
            }
            LoopEvent::BudgetOverrun {
                phase,
                target_pct,
                actual_pct,
                recovery,
            } => {
                state.log(format!(
                    "BUDGET OVERRUN: {} used {}% (target {}%) -- recovery: {}",
                    phase, actual_pct, target_pct, recovery,
                ));
            }
            LoopEvent::Log(ref msg) => {
                // Track patterns learned from "Merged patterns: N new added" messages
                if msg.starts_with("Merged patterns:") {
                    if let Some(count_str) = msg
                        .strip_prefix("Merged patterns: ")
                        .and_then(|s| s.split_whitespace().next())
                    {
                        if let Ok(n) = count_str.parse::<usize>() {
                            state.session_patterns_learned += n;
                        }
                    }
                }
                // Track review findings from "Review pass N/2: verdict=X, N high, N medium findings"
                if msg.starts_with("Review pass ") {
                    if let Some(rest) = msg.split("verdict=").nth(1) {
                        // Parse "FAIL, 2 high, 1 medium findings"
                        for part in rest.split(',') {
                            let trimmed = part.trim();
                            if trimmed.ends_with("high") {
                                if let Ok(n) = trimmed
                                    .split_whitespace()
                                    .next()
                                    .unwrap_or("0")
                                    .parse::<usize>()
                                {
                                    state.session_review_high += n;
                                }
                            } else if trimmed.ends_with("medium") {
                                if let Ok(n) = trimmed
                                    .split_whitespace()
                                    .next()
                                    .unwrap_or("0")
                                    .parse::<usize>()
                                {
                                    state.session_review_medium += n;
                                }
                            }
                        }
                    }
                }
                // Track pattern matching mode for dashboard
                if msg.starts_with("Pattern matching (") {
                    if let Some(mode) = msg
                        .strip_prefix("Pattern matching (")
                        .and_then(|s| s.split(')').next())
                    {
                        state.last_pattern_match_mode = Some(mode.to_string());
                    }
                }
                state.log(msg.clone());
            }
            LoopEvent::StatsReady(report) => {
                if state.stats_loading {
                    state.stats_overlay_report = Some(*report);
                    state.show_stats_overlay = true;
                    state.stats_overlay_scroll = 0;
                }
                state.stats_loading = false;
            }
            LoopEvent::StatsLoadFailed => {
                state.stats_loading = false;
                state.log("Stats: failed to load events".to_string());
            }
            LoopEvent::BackgroundLog(ref msg) => {
                // Track patterns learned from "Merged patterns: N new added" messages
                if msg.starts_with("Merged patterns:") {
                    if let Some(count_str) = msg
                        .strip_prefix("Merged patterns: ")
                        .and_then(|s| s.split_whitespace().next())
                    {
                        if let Ok(n) = count_str.parse::<usize>() {
                            state.session_patterns_learned += n;
                        }
                    }
                }
                if let Some(title) = msg.strip_prefix("Pattern learned: ") {
                    state.session_patterns.push(state::PatternEvent {
                        title: title.to_string(),
                        kind: state::PatternEventKind::Learned,
                    });
                }
                state.log(msg.clone());
            }
            LoopEvent::CountsUpdated(completed, total) => {
                state.completed_count = completed;
                state.total_count = total;
            }
            LoopEvent::QueueUpdated(tasks) => {
                state.task_queue = tasks;
            }
            LoopEvent::TasksFileMtime(mtime) => {
                state.tasks_file_mtime = mtime;
            }
            LoopEvent::TaskReviewResult {
                task_id,
                fix_passes,
                passed,
            } => {
                if !state.task_history.contains_key(&task_id) {
                    state.task_history_order.push(task_id.clone());
                }
                let history = state.task_history.entry(task_id).or_default();
                history.fix_passes = fix_passes;
                history.passed_review = passed;
                state.cap_task_history();
            }
            LoopEvent::WaitingForReview {
                pr_num,
                ref session_id,
                ref gate,
            } => {
                state.review_gates.insert(session_id.clone(), gate.clone());
                if !state.awaiting_review {
                    state.awaiting_review = true;
                    state.review_session_id = Some(session_id.clone());
                    state.awaiting_pr = pr_num;
                    state.pr_poll_last_check = None;
                    if let Some(num) = pr_num {
                        state.log(format!(
                            "Awaiting PR #{} review -- press Enter to skip or wait for approval",
                            num
                        ));
                    } else {
                        state.log("Awaiting review -- press Enter or 'c' to continue");
                    }
                } else {
                    state
                        .pending_reviews
                        .push_back((session_id.clone(), pr_num));
                    state.log(format!(
                        "Review queued for session {} (another review in progress)",
                        session_id
                    ));
                }
            }
            LoopEvent::PrApproved {
                pr_num,
                ref session_id,
            } => {
                // Clear the gate for the specific session that was approved
                if let Some(gate) = state.review_gates.remove(session_id) {
                    gate.clear();
                }
                if state.review_session_id.as_deref() == Some(session_id.as_str()) {
                    // Active review was approved -- advance display state
                    state.review_session_id = None;
                    state.awaiting_pr = None;
                    state.pr_poll_last_check = None;
                    if let Some((next_sid, next_pr)) = state.pending_reviews.pop_front() {
                        state.review_session_id = Some(next_sid.clone());
                        state.awaiting_pr = next_pr;
                        state.pr_poll_last_check = None;
                        if let Some(num) = next_pr {
                            state.log(format!(
                                "PR #{} approved -- now reviewing PR #{}",
                                pr_num, num
                            ));
                        } else {
                            state.log(format!("PR #{} approved -- next review ready, press Enter or 'c' to continue", pr_num));
                        }
                    } else {
                        state.awaiting_review = false;
                        state.log(format!("PR #{} approved -- resuming pipeline", pr_num));
                    }
                } else {
                    // Approved session was queued -- remove it from pending
                    state.pending_reviews.retain(|(sid, _)| sid != session_id);
                    state.log(format!("PR #{} approved (session {})", pr_num, session_id));
                }
            }
            LoopEvent::PrClosed {
                pr_num,
                ref session_id,
            } => {
                // Clear the gate for the specific session whose PR was closed
                if let Some(gate) = state.review_gates.remove(session_id) {
                    gate.clear();
                }
                if state.review_session_id.as_deref() == Some(session_id.as_str()) {
                    // Active review was closed -- advance display state
                    state.review_session_id = None;
                    state.awaiting_pr = None;
                    state.pr_poll_last_check = None;
                    if let Some((next_sid, next_pr)) = state.pending_reviews.pop_front() {
                        state.review_session_id = Some(next_sid);
                        state.awaiting_pr = next_pr;
                        state.pr_poll_last_check = None;
                    } else {
                        state.awaiting_review = false;
                    }
                } else {
                    // Closed session was queued -- remove it from pending
                    state.pending_reviews.retain(|(sid, _)| sid != session_id);
                }
                // Create stop file to halt the build loop
                state.write_stop_file();
                state.stop_after_task = true;
                state.log(format!(
                    "PR #{} was closed without merge -- stopping",
                    pr_num
                ));
            }
            LoopEvent::AwaitCommitApproval {
                ref task_id,
                ref proposed_commit_type,
                ref session_id,
                ref gate,
                ref result,
            } => {
                state
                    .commit_approval_gates
                    .insert(session_id.clone(), gate.clone());
                state
                    .commit_approval_results
                    .insert(session_id.clone(), result.clone());
                if !state.awaiting_commit_approval {
                    // No prompt currently showing -- display this one immediately.
                    state.awaiting_commit_approval = true;
                    state.approval_session_id = Some(session_id.clone());
                    state.approval_task_id = Some(task_id.clone());
                    state.approval_proposed_type = Some(proposed_commit_type.clone());
                } else {
                    // Another prompt is already showing -- queue this one so it
                    // is not lost when the current approval is handled.
                    state.pending_approvals.push_back((
                        session_id.clone(),
                        task_id.clone(),
                        proposed_commit_type.clone(),
                    ));
                }
                state.log(format!(
                    "Commit {} as {}? Press [y] to approve or [n] to deny",
                    task_id, proposed_commit_type
                ));
            }
            LoopEvent::CommitApprovalResponse { approved } => {
                // The y/n handler already manages awaiting_commit_approval and display
                // fields (advancing to the next queued approval if any). Do not reset
                // them here or a queued approval waiting for display would be cleared.
                if !approved {
                    state.log("Commit denied -- will commit as WIP and pause".to_string());
                }
            }
            LoopEvent::ShipStarted => {
                state.ship_active = true;
                state.log("Ship: committing changes".to_string());
            }
            LoopEvent::ShipDone => {
                state.ship_active = false;
            }
            LoopEvent::ParallelBuilderProgress { total, done } => {
                state.parallel_builder_progress = if done >= total {
                    None // Clear when all done
                } else {
                    Some((total, done))
                };
                state.log(format!(
                    "Parallel builder: {}/{} slots complete",
                    done, total
                ));
            }
            LoopEvent::TmuxSessionStarted(name) => {
                state.tmux_session_names.push(name);
            }
            LoopEvent::PrPollChecked => {
                state.pr_poll_last_check = Some(std::time::Instant::now());
            }
            LoopEvent::SessionIdAssigned(ref sid) => {
                state.observatory_session_id = Some(sid.clone());
            }
            LoopEvent::Finished => {
                // Emit warnings for injected-but-never-referenced extensions
                let warnings: Vec<String> = state.extension_inject_count
                    .iter()
                    .filter_map(|(ext_name, inject_count)| {
                        let ref_count = state.extension_reference_count.get(ext_name).copied().unwrap_or(0);
                        if *inject_count > 0 && ref_count == 0 {
                            Some(format!(
                                "Warning: Extension '{}' was injected {} times but never referenced -- check if the extension content is relevant to this task.",
                                ext_name, inject_count
                            ))
                        } else {
                            None
                        }
                    })
                    .collect();
                for warning in warnings {
                    state.log(warning);
                }
                state.log("All work complete — loop finished");
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."))
                    .to_path_buf();
                enter_home_surface(
                    &project_dir,
                    state,
                    Some("Build loop finished.".to_string()),
                );
            }
        },
        AppEvent::Key(key) => {
            if state.confirm_quit {
                match key.code {
                    KeyCode::Char('y') | KeyCode::Char('Y') | KeyCode::Enter => {
                        state.should_quit = true;
                    }
                    KeyCode::Char('n') | KeyCode::Char('N') | KeyCode::Esc => {
                        state.confirm_quit = false;
                    }
                    _ => {}
                }
            } else if state.inject_input.is_some() {
                handle_inject_key(state, key);
            } else if state.dual_arena_ready()
                && matches!(key.code, KeyCode::Char('q') | KeyCode::Esc)
            {
                let project_dir = state
                    .buildloop_dir
                    .parent()
                    .unwrap_or(std::path::Path::new("."))
                    .to_path_buf();
                enter_home_surface(
                    &project_dir,
                    state,
                    Some("Arena results preserved in .buildloop/arena/".to_string()),
                );
            } else if state.show_running_explorer {
                // Commit approval gate: y/n approves or denies (must be before other handlers)
                if state.awaiting_commit_approval
                    && matches!(key.code, KeyCode::Char('y') | KeyCode::Char('n'))
                {
                    let approved = matches!(key.code, KeyCode::Char('y'));
                    let session_id = state.approval_session_id.take();
                    state.approval_task_id = None;
                    state.approval_proposed_type = None;
                    if let Some(sid) = session_id {
                        if let Some(result_arc) = state.commit_approval_results.get(&sid) {
                            result_arc.store(approved);
                        }
                        if let Some(gate_arc) = state.commit_approval_gates.get(&sid) {
                            gate_arc.clear();
                        }
                        state.commit_approval_gates.remove(&sid);
                        state.commit_approval_results.remove(&sid);
                    }
                    // Advance to next queued approval if one arrived while this was pending.
                    if let Some((next_sid, next_tid, next_ptype)) =
                        state.pending_approvals.pop_front()
                    {
                        state.approval_session_id = Some(next_sid);
                        state.approval_task_id = Some(next_tid.clone());
                        state.approval_proposed_type = Some(next_ptype.clone());
                        state.log(format!(
                            "Commit {} as {}? Press [y] to approve or [n] to deny",
                            next_tid, next_ptype
                        ));
                    } else {
                        state.awaiting_commit_approval = false;
                    }
                    if approved {
                        state.log("Approved -- committing as feat".to_string());
                    } else {
                        state.log("Denied -- committing as WIP".to_string());
                    }
                // Review gate: Enter/c clears the review pause (must be before other handlers)
                } else if state.awaiting_review
                    && matches!(key.code, KeyCode::Enter | KeyCode::Char('c'))
                {
                    if let Some(ref sid) = state.review_session_id.take() {
                        if let Some(gate) = state.review_gates.remove(sid) {
                            gate.clear();
                        }
                    }
                    state.awaiting_pr = None;
                    state.pr_poll_last_check = None;
                    // Advance to next queued review if one exists
                    if let Some((next_sid, next_pr)) = state.pending_reviews.pop_front() {
                        state.review_session_id = Some(next_sid);
                        state.awaiting_pr = next_pr;
                        state.pr_poll_last_check = None;
                        state.log("Continuing -- next review ready");
                    } else {
                        state.awaiting_review = false;
                        state.log("Continuing to next task");
                    }
                } else {
                    match key.code {
                        KeyCode::Char('?') if toggle_settings_overlay(state) => {
                            if let Some(tx) = state.event_tx.clone() {
                                let ollama_url = config.ollama_url.clone();
                                tokio::spawn(async move {
                                    let discovery = fetch_available_models(ollama_url).await;
                                    let _ = tx.send(AppEvent::LocalModels {
                                        lmstudio: discovery.lmstudio,
                                        ollama: discovery.ollama,
                                        lmstudio_opencode_map: discovery.lmstudio_opencode_map,
                                        opencode_warning: discovery.opencode_warning,
                                        claude_available: discovery.claude_available,
                                        codex_available: discovery.codex_available,
                                        copilot_available: discovery.copilot_available,
                                    });
                                });
                            }
                        }
                        _ if handle_settings_overlay_key(state, key) => {}
                        KeyCode::Char('q') | KeyCode::Esc => {
                            if handle_overlay_esc(state) {
                                // overlay closed
                            } else if state.show_stats_overlay && key.code == KeyCode::Esc {
                                state.show_stats_overlay = false;
                                state.stats_loading = false;
                                state.stats_overlay_report = None;
                                state.stats_overlay_scroll = 0;
                            } else if state.stop_after_task {
                                state.stop_after_task = false;
                                state.remove_stop_file();
                                state.log("Stop cancelled -- resuming build");
                            } else {
                                state.stop_after_task = true;
                                state.write_stop_file();
                                state.log("Stopping after current task (Esc again to cancel, Ctrl+C to force quit)");
                            }
                        }
                        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            if state.stop_after_task {
                                state.remove_stop_file();
                                state.should_quit = true;
                            } else {
                                state.stop_after_task = true;
                                state.write_stop_file();
                                state.log(
                                "Will stop after current task completes (Ctrl+C again to force quit)",
                            );
                            }
                        }
                        KeyCode::Tab | KeyCode::BackTab => {
                            state.show_running_explorer = false;
                            state.focused_pane = state::TuiPane::AgentOutput;
                        }
                        KeyCode::Up => {
                            move_running_explorer_selection(state, -1);
                        }
                        KeyCode::Down => {
                            move_running_explorer_selection(state, 1);
                        }
                        KeyCode::PageUp => {
                            move_running_explorer_selection(state, -10);
                        }
                        KeyCode::PageDown => {
                            move_running_explorer_selection(state, 10);
                        }
                        KeyCode::Enter => {
                            handle_running_explorer_enter(state);
                        }
                        KeyCode::Char('a') => {
                            if let Some(ref mut explorer) = state.running_explorer {
                                startup::toggle_expand_all(explorer);
                            }
                        }
                        KeyCode::Char('w') => {
                            let project_dir = state
                                .buildloop_dir
                                .parent()
                                .unwrap_or(std::path::Path::new("."));
                            if let Some(ref mut explorer) = state.running_explorer {
                                startup::toggle_preview_wrap(explorer, project_dir);
                            }
                        }
                        _ => {}
                    }
                } // close review-gate else
            } else {
                // Commit approval gate: y/n approves or denies (must be before other handlers)
                if state.awaiting_commit_approval
                    && matches!(key.code, KeyCode::Char('y') | KeyCode::Char('n'))
                {
                    let approved = matches!(key.code, KeyCode::Char('y'));
                    let session_id = state.approval_session_id.take();
                    state.approval_task_id = None;
                    state.approval_proposed_type = None;
                    if let Some(sid) = session_id {
                        if let Some(result_arc) = state.commit_approval_results.get(&sid) {
                            result_arc.store(approved);
                        }
                        if let Some(gate_arc) = state.commit_approval_gates.get(&sid) {
                            gate_arc.clear();
                        }
                        state.commit_approval_gates.remove(&sid);
                        state.commit_approval_results.remove(&sid);
                    }
                    // Advance to next queued approval if one arrived while this was pending.
                    if let Some((next_sid, next_tid, next_ptype)) =
                        state.pending_approvals.pop_front()
                    {
                        state.approval_session_id = Some(next_sid);
                        state.approval_task_id = Some(next_tid.clone());
                        state.approval_proposed_type = Some(next_ptype.clone());
                        state.log(format!(
                            "Commit {} as {}? Press [y] to approve or [n] to deny",
                            next_tid, next_ptype
                        ));
                    } else {
                        state.awaiting_commit_approval = false;
                    }
                    if approved {
                        state.log("Approved -- committing as feat".to_string());
                    } else {
                        state.log("Denied -- committing as WIP".to_string());
                    }
                // Review gate: Enter/c clears the review pause (must be before other handlers)
                } else if state.awaiting_review
                    && matches!(key.code, KeyCode::Enter | KeyCode::Char('c'))
                {
                    if let Some(ref sid) = state.review_session_id.take() {
                        if let Some(gate) = state.review_gates.remove(sid) {
                            gate.clear();
                        }
                    }
                    state.awaiting_pr = None;
                    state.pr_poll_last_check = None;
                    // Advance to next queued review if one exists
                    if let Some((next_sid, next_pr)) = state.pending_reviews.pop_front() {
                        state.review_session_id = Some(next_sid);
                        state.awaiting_pr = next_pr;
                        state.pr_poll_last_check = None;
                        state.log("Continuing -- next review ready");
                    } else {
                        state.awaiting_review = false;
                        state.log("Continuing to next task");
                    }
                } else if let Some(kind) = state.running_screen_modal {
                    handle_running_modal_key(state, key, kind);
                } else {
                    match key.code {
                        KeyCode::Char('r') | KeyCode::Char('R') if state.typed_error_can_retry => {
                            // D1.3: ContextOverflow retry. User confirmed they
                            // fixed LM Studio's n_ctx; re-spawn the build loop.
                            // The main TUI loop will store(false) on shutdown
                            // next iteration because stop_after_task is now
                            // false; apply_pending_transition then spawns a
                            // fresh build_loop with the same shared Arc.
                            state.typed_error_toast = None;
                            state.typed_error_can_retry = false;
                            state.last_typed_error = None;
                            state.stop_after_task = false;
                            state.remove_stop_file();
                            state.log("Retrying after ContextOverflow -- restarting build loop");
                            state.pending_transition = Some(PendingTransition::StartBuild);
                        }
                        KeyCode::Esc if state.typed_error_toast.is_some() => {
                            state.typed_error_toast = None;
                            state.typed_error_can_retry = false;
                        }
                        KeyCode::Char('?') if toggle_settings_overlay(state) => {
                            if let Some(tx) = state.event_tx.clone() {
                                let ollama_url = config.ollama_url.clone();
                                tokio::spawn(async move {
                                    let discovery = fetch_available_models(ollama_url).await;
                                    let _ = tx.send(AppEvent::LocalModels {
                                        lmstudio: discovery.lmstudio,
                                        ollama: discovery.ollama,
                                        lmstudio_opencode_map: discovery.lmstudio_opencode_map,
                                        opencode_warning: discovery.opencode_warning,
                                        claude_available: discovery.claude_available,
                                        codex_available: discovery.codex_available,
                                        copilot_available: discovery.copilot_available,
                                    });
                                });
                            }
                        }
                        _ if handle_settings_overlay_key(state, key) => {}
                        KeyCode::Char('r')
                            if !state.show_settings_overlay
                                && state.surface_summary_overlay.is_some() =>
                        {
                            let Some(overlay) =
                                state.surface_summary_overlay.as_ref().cloned()
                            else {
                                return;
                            };
                            let project_dir = state
                                .buildloop_dir
                                .parent()
                                .unwrap_or(std::path::Path::new("."))
                                .to_path_buf();
                            trigger_surface_summary(
                                state,
                                &project_dir,
                                config,
                                overlay.surface.clone(),
                                true,
                            );
                        }
                        KeyCode::Char('f')
                            if !state.show_settings_overlay
                                && state.surface_summary_overlay.is_some() =>
                        {
                            let Some(overlay) =
                                state.surface_summary_overlay.as_ref().cloned()
                            else {
                                return;
                            };
                            let project_dir = state
                                .buildloop_dir
                                .parent()
                                .unwrap_or(std::path::Path::new("."))
                                .to_path_buf();
                            surface_open_file(state, &project_dir, config, &overlay);
                        }
                        KeyCode::Char('q') => {
                            if !state.show_settings_overlay
                                && state.surface_summary_overlay.is_some()
                            {
                                state.surface_summary_overlay = None;
                            } else if handle_overlay_esc(state) {
                                // overlay closed
                            } else if state.show_stats_overlay {
                                state.show_stats_overlay = false;
                                state.stats_loading = false;
                                state.stats_overlay_report = None;
                                state.stats_overlay_scroll = 0;
                            } else if state.stop_after_task {
                                state.stop_after_task = false;
                                state.remove_stop_file();
                                state.log("Stop cancelled -- resuming build");
                            } else {
                                state.stop_after_task = true;
                                state.write_stop_file();
                                state.log("Stopping after current task (q again to cancel, Ctrl+C to force quit)");
                            }
                        }
                        KeyCode::Esc
                            if !state.show_settings_overlay
                                && state.surface_summary_overlay.is_some() =>
                        {
                            state.surface_summary_overlay = None;
                        }
                        KeyCode::Esc if !handle_overlay_esc(state) && state.show_stats_overlay => {
                            state.show_stats_overlay = false;
                            state.stats_loading = false;
                            state.stats_overlay_report = None;
                            state.stats_overlay_scroll = 0;
                        }
                        KeyCode::Esc if !handle_overlay_esc(state) => {
                            // Open the StopRun modal instead of arming the soft-stop directly.
                            // The modal sets stop_after_task only after the user picks Y.
                            state.running_screen_modal = Some(RunningModalKind::StopRun);
                        }
                        KeyCode::Esc => {}
                        KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            // Open the CtrlC modal. Force-quit on second Ctrl+C is handled
                            // inside handle_running_modal_key when the modal is already open.
                            state.running_screen_modal = Some(RunningModalKind::CtrlC);
                        }
                        KeyCode::Char('f') if state.last_orchestrator_outcome.is_some() => {
                            state.show_findings = !state.show_findings;
                            state.findings_scroll = 0;
                        }
                        KeyCode::Char('p') => {
                            if state.show_patterns {
                                state.show_patterns = false;
                            } else {
                                state.show_patterns = true;
                                refresh_patterns_cache(state, config);
                                refresh_skill_citation_summary(state);
                            }
                        }
                        KeyCode::Char('s') if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                            if state.show_stats_overlay {
                                state.show_stats_overlay = false;
                                state.stats_loading = false;
                                state.stats_overlay_report = None;
                                state.stats_overlay_scroll = 0;
                            } else {
                                compute_and_show_stats_overlay(state);
                            }
                        }
                        // Sandbox toggle removed -- config-only override for implementers.
                        KeyCode::Char('s') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                            state.log(
                                "Sandbox toggle disabled -- override via .foundry.json only"
                                    .to_string(),
                            );
                        }
                        KeyCode::Char('i') => {
                            state.inject_input = Some(String::new());
                        }
                        KeyCode::Char('t') => {
                            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
                            state.tui_theme = new_theme;
                            state.log(format!("Theme: {}", name));
                        }
                        KeyCode::Char('1') if state.dual_build.active => {
                            state.dual_build.tab = 0;
                        }
                        KeyCode::Char('2') if state.dual_build.active => {
                            state.dual_build.tab = 1;
                        }
                        KeyCode::Up => {
                            if let Some(ref mut ov) = state.settings_overlay {
                                ov.focus = ov.focus.saturating_sub(1);
                            } else if state.show_stats_overlay {
                                state.stats_overlay_scroll =
                                    state.stats_overlay_scroll.saturating_sub(3);
                            } else if state.show_findings {
                                state.findings_scroll = state.findings_scroll.saturating_sub(3);
                            } else if state.show_patterns {
                                state.patterns_scroll = state.patterns_scroll.saturating_sub(3);
                            } else {
                                let max = state.agent_output.len().saturating_sub(1);
                                state.scroll_offset =
                                    state.scroll_offset.saturating_add(3).min(max);
                            }
                        }
                        KeyCode::Down => {
                            if let Some(ref mut ov) = state.settings_overlay {
                                let max = ov.visible_row_count().saturating_sub(1);
                                ov.focus = (ov.focus + 1).min(max);
                            } else if state.show_stats_overlay {
                                state.stats_overlay_scroll =
                                    state.stats_overlay_scroll.saturating_add(3);
                            } else if state.show_findings {
                                state.findings_scroll = state.findings_scroll.saturating_add(3);
                            } else if state.show_patterns {
                                state.patterns_scroll = state.patterns_scroll.saturating_add(3);
                            } else {
                                state.scroll_offset = state.scroll_offset.saturating_sub(3);
                            }
                        }
                        KeyCode::PageUp => {
                            let max = state.task_queue.len().saturating_sub(1);
                            state.task_queue_scroll =
                                state.task_queue_scroll.saturating_add(3).min(max);
                        }
                        KeyCode::PageDown => {
                            state.task_queue_scroll = state.task_queue_scroll.saturating_sub(3);
                        }
                        KeyCode::Tab | KeyCode::BackTab => {
                            if state.show_running_explorer {
                                // Return to dashboard
                                state.show_running_explorer = false;
                                state.focused_pane = state::TuiPane::AgentOutput;
                            } else {
                                // Enter explorer view -- lazily populate running_explorer
                                if state.running_explorer.is_none() {
                                    let project_dir = state
                                        .buildloop_dir
                                        .parent()
                                        .unwrap_or(std::path::Path::new("."));
                                    let scenario = detect_startup_scenario(project_dir);
                                    let plan_status = classify_plan_status(
                                        &self::contract::ContractPaths::resolve(project_dir)
                                            .tasks_path,
                                    );
                                    state.running_explorer = Some(StartupState::new(
                                        project_dir,
                                        scenario,
                                        plan_status,
                                        None,
                                    ));
                                }
                                state.show_running_explorer = true;
                                state.focused_pane = state::TuiPane::Explorer;
                            }
                        }
                        _ => {}
                    }
                } // close review-gate else
            }
        }
        AppEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
            if state.tick_count % crate::app::state::TASKS_RELOAD_TICK_STRIDE == 0 {
                let _ = state.handle_tasks_file_change();
            }
            let needs_refresh = match state.skill_citation_summary_loaded_at {
                None => true,
                Some(last) => last.elapsed() >= std::time::Duration::from_secs(30),
            };
            if needs_refresh {
                refresh_skill_citation_summary(state);
            }
        }
        AppEvent::UpdateAvailable(version) => {
            state.update_available = Some(version);
        }
        AppEvent::OllamaStatus(connected) => {
            state.last_pattern_match_mode = Some(
                if connected {
                    "semantic"
                } else {
                    "keyword-only"
                }
                .to_string(),
            );
        }
        AppEvent::CatalogRefreshed(messages) => {
            for line in messages {
                state.log(line);
            }
        }
        AppEvent::LocalModels {
            lmstudio,
            ollama,
            lmstudio_opencode_map,
            opencode_warning,
            claude_available,
            codex_available,
            copilot_available,
        } => {
            let mut merged: Vec<String> = Vec::with_capacity(lmstudio.len() + ollama.len());
            for m in lmstudio.iter().chain(ollama.iter()) {
                if !merged.contains(m) {
                    merged.push(m.clone());
                }
            }
            state.lmstudio_models = lmstudio;
            state.ollama_models = ollama;
            state.local_models = merged;
            state.lmstudio_id_to_opencode_path = lmstudio_opencode_map;
            state.claude_cli_available = claude_available;
            state.codex_cli_available = codex_available;
            state.copilot_available = copilot_available;
            if let Some(msg) = opencode_warning {
                state.log(msg);
            }
            init_builder_cursor(state);
        }
        AppEvent::Mouse(mouse) => {
            use crossterm::event::{MouseButton, MouseEventKind};
            let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
            if state.confirm_quit && matches!(mouse.kind, MouseEventKind::Down(MouseButton::Left)) {
                let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                if let Some(action) = tui::quit_confirm_hit_test(area, mouse.column, mouse.row) {
                    match action {
                        tui::QuitConfirmAction::Quit => state.should_quit = true,
                        tui::QuitConfirmAction::Cancel => state.confirm_quit = false,
                    }
                }
                return;
            }
            // AI summary overlay claims the mouse before anything else when open:
            // wheel scrolls the body; left-click dispatches to the [X]/Esc/R/F buttons.
            if !state.show_settings_overlay && state.surface_summary_overlay.is_some() {
                let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                match mouse.kind {
                    MouseEventKind::ScrollUp => {
                        if let Some(o) = state.surface_summary_overlay.as_mut() {
                            o.scroll_offset = o.scroll_offset.saturating_sub(3);
                        }
                        return;
                    }
                    MouseEventKind::ScrollDown => {
                        if let Some(o) = state.surface_summary_overlay.as_mut() {
                            o.scroll_offset = o.scroll_offset.saturating_add(3);
                        }
                        return;
                    }
                    MouseEventKind::Down(MouseButton::Left) => {
                        let has_file = surface_has_fallback_file(
                            state.surface_summary_overlay.as_ref(),
                        );
                        match tui::summary_modal_hit_test(
                            area,
                            mouse.column,
                            mouse.row,
                            has_file,
                        ) {
                            Some(tui::SummaryModalAction::Dismiss) => {
                                state.surface_summary_overlay = None;
                                return;
                            }
                            Some(tui::SummaryModalAction::Refresh) => {
                                let Some(overlay) =
                                    state.surface_summary_overlay.as_ref().cloned()
                                else {
                                    return;
                                };
                                let project_dir = state
                                    .buildloop_dir
                                    .parent()
                                    .unwrap_or(std::path::Path::new("."))
                                    .to_path_buf();
                                trigger_surface_summary(
                                    state,
                                    &project_dir,
                                    config,
                                    overlay.surface.clone(),
                                    true,
                                );
                                return;
                            }
                            Some(tui::SummaryModalAction::OpenFile) => {
                                let Some(overlay) =
                                    state.surface_summary_overlay.as_ref().cloned()
                                else {
                                    return;
                                };
                                let project_dir = state
                                    .buildloop_dir
                                    .parent()
                                    .unwrap_or(std::path::Path::new("."))
                                    .to_path_buf();
                                surface_open_file(state, &project_dir, config, &overlay);
                                return;
                            }
                            Some(tui::SummaryModalAction::None) => {
                                // Click was inside the modal but not on a button.
                                // Consume it -- do not fall through to underlying screen.
                                return;
                            }
                            None => {
                                // Click was outside the modal. Falls through.
                            }
                        }
                    }
                    _ => {}
                }
            }
            if handle_settings_overlay_mouse(state, mouse, terminal_size) {
                return;
            }
            // Pipeline stage clicks and view tab clicks work in BOTH Dashboard and Explore views.
            if matches!(mouse.kind, MouseEventKind::Down(MouseButton::Left)) {
                let full_area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                let layout_chunks = ratatui::layout::Layout::default()
                    .direction(ratatui::layout::Direction::Vertical)
                    .constraints([
                        ratatui::layout::Constraint::Length(5),
                        ratatui::layout::Constraint::Length(9),
                        ratatui::layout::Constraint::Min(8),
                        ratatui::layout::Constraint::Length(8),
                        ratatui::layout::Constraint::Length(1),
                    ])
                    .split(full_area);
                let pipeline_area = layout_chunks[1];
                // Header tab click (Dashboard / Explore tabs on first row)
                if mouse.row == layout_chunks[0].y {
                    if let Some(target) = tui::running_header_tab_hit_test(state, mouse.column) {
                        match target {
                            tui::RunningHeaderTab::Dashboard => {
                                state.show_running_explorer = false;
                            }
                            tui::RunningHeaderTab::Explore => {
                                if state.running_explorer.is_none() {
                                    let project_dir = state
                                        .buildloop_dir
                                        .parent()
                                        .unwrap_or(std::path::Path::new("."));
                                    let scenario = detect_startup_scenario(project_dir);
                                    let plan_status = classify_plan_status(
                                        &self::contract::ContractPaths::resolve(project_dir)
                                            .tasks_path,
                                    );
                                    state.running_explorer = Some(StartupState::new(
                                        project_dir,
                                        scenario,
                                        plan_status,
                                        None,
                                    ));
                                }
                                state.show_running_explorer = true;
                                state.focused_pane = state::TuiPane::Explorer;
                            }
                        }
                    }
                }
                // Pipeline stage click (box rows)
                let mut n_connected = config.pipeline_stages.iter().filter(|s| s.enabled).count();
                if config.run_mode == "coach" {
                    n_connected += 1;
                }
                if config.plan_review_enabled {
                    n_connected += 1;
                }
                if let Some(click) =
                    tui::pipeline_click(pipeline_area, mouse.column, mouse.row, n_connected)
                {
                    let project_dir = state
                        .buildloop_dir
                        .parent()
                        .unwrap_or(std::path::Path::new("."))
                        .to_path_buf();
                    let target = pipeline_click_target(click, &project_dir, config);
                    handle_pipeline_click_target(state, &project_dir, config, target);
                }
            }
            if state.show_running_explorer {
                // Delegate to running explorer mouse handler
                let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                handle_startup_mouse_at_for_running(state, mouse, terminal_size, config);
            } else {
                match mouse.kind {
                    MouseEventKind::Moved
                        if !state.dragging_split
                            && !state.show_stats_overlay
                            && !state.show_patterns
                            && !state.show_findings
                            && !state.show_settings_overlay
                            && state.surface_summary_overlay.is_none() =>
                    {
                        // Hover instantly switches focused pane -- no click required.
                        let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                        let area =
                            ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                        let has_ext = state.available_extensions.iter().any(|e| e.selected)
                            || !state.session_extensions_used.is_empty();
                        let panes = tui::running_layout(area, has_ext, state.agent_pane_split);
                        let bottom_chunks = ratatui::layout::Layout::default()
                            .direction(ratatui::layout::Direction::Vertical)
                            .constraints([
                                ratatui::layout::Constraint::Length(5),
                                ratatui::layout::Constraint::Length(9),
                                ratatui::layout::Constraint::Min(8),
                                ratatui::layout::Constraint::Length(8),
                                ratatui::layout::Constraint::Length(1),
                            ])
                            .split(area);
                        if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::AgentOutput;
                        } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::TaskQueue;
                        } else if tui::rect_contains(panes.narrative, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::Narrative;
                        } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::PatternsLearned;
                        } else if panes
                            .extensions_used
                            .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                        {
                            state.focused_pane = state::TuiPane::Extensions;
                        } else if tui::rect_contains(bottom_chunks[3], mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::Stats;
                        }
                        state.mouse_over_separator = (mouse.column == panes.separator_col
                            || mouse.column + 1 == panes.separator_col)
                            && mouse.row >= panes.agent_output.y
                            && mouse.row < panes.agent_output.y + panes.agent_output.height;
                    }
                    MouseEventKind::ScrollUp => {
                        let lines = wheel_lines(state.last_scroll_at);
                        state.last_scroll_at = Some(std::time::Instant::now());
                        if state.show_stats_overlay {
                            state.stats_overlay_scroll =
                                state.stats_overlay_scroll.saturating_sub(lines);
                        } else if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_sub(lines);
                        } else if state.show_findings {
                            state.findings_scroll = state.findings_scroll.saturating_sub(lines);
                        } else {
                            let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                            let area =
                                ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                            let has_ext = state.available_extensions.iter().any(|e| e.selected)
                                || !state.session_extensions_used.is_empty();
                            let panes = tui::running_layout(area, has_ext, state.agent_pane_split);
                            if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::AgentOutput;
                                let max = state.agent_output.len().saturating_sub(1);
                                state.scroll_offset =
                                    state.scroll_offset.saturating_add(lines).min(max);
                            } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row)
                            {
                                state.focused_pane = state::TuiPane::TaskQueue;
                                let max = state.task_queue.len().saturating_sub(1);
                                state.task_queue_scroll =
                                    state.task_queue_scroll.saturating_add(lines).min(max);
                            } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::PatternsLearned;
                                state.patterns_scroll = state.patterns_scroll.saturating_sub(lines);
                            } else if panes
                                .extensions_used
                                .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                            {
                                state.focused_pane = state::TuiPane::Extensions;
                            }
                        }
                    }
                    MouseEventKind::ScrollDown => {
                        let lines = wheel_lines(state.last_scroll_at);
                        state.last_scroll_at = Some(std::time::Instant::now());
                        if state.show_stats_overlay {
                            state.stats_overlay_scroll =
                                state.stats_overlay_scroll.saturating_add(lines);
                        } else if state.show_patterns {
                            state.patterns_scroll = state.patterns_scroll.saturating_add(lines);
                        } else if state.show_findings {
                            state.findings_scroll = state.findings_scroll.saturating_add(lines);
                        } else {
                            let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                            let area =
                                ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                            let has_ext = state.available_extensions.iter().any(|e| e.selected)
                                || !state.session_extensions_used.is_empty();
                            let panes = tui::running_layout(area, has_ext, state.agent_pane_split);
                            if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::AgentOutput;
                                state.scroll_offset = state.scroll_offset.saturating_sub(lines);
                            } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row)
                            {
                                state.focused_pane = state::TuiPane::TaskQueue;
                                state.task_queue_scroll =
                                    state.task_queue_scroll.saturating_sub(lines);
                            } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                                state.focused_pane = state::TuiPane::PatternsLearned;
                                state.patterns_scroll = state.patterns_scroll.saturating_add(lines);
                            } else if panes
                                .extensions_used
                                .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                            {
                                state.focused_pane = state::TuiPane::Extensions;
                            }
                        }
                    }
                    MouseEventKind::Down(MouseButton::Left) => {
                        let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                        let area =
                            ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                        let has_ext = state.available_extensions.iter().any(|e| e.selected)
                            || !state.session_extensions_used.is_empty();
                        let panes = tui::running_layout(area, has_ext, state.agent_pane_split);
                        // Bottom stats rect (used for both hit-test and dispatch)
                        let bottom_full = ratatui::layout::Rect::new(
                            0,
                            0,
                            terminal_size.0,
                            terminal_size.1,
                        );
                        let bottom_chunks = ratatui::layout::Layout::default()
                            .direction(ratatui::layout::Direction::Vertical)
                            .constraints([
                                ratatui::layout::Constraint::Length(5),
                                ratatui::layout::Constraint::Length(9),
                                ratatui::layout::Constraint::Min(8),
                                ratatui::layout::Constraint::Length(8),
                                ratatui::layout::Constraint::Length(1),
                            ])
                            .split(bottom_full);
                        let stats_rect = bottom_chunks[3];
                        // Check if clicking on the vertical separator (±1 column tolerance)
                        let on_sep = mouse.column == panes.separator_col
                            || mouse.column + 1 == panes.separator_col;
                        let in_middle = mouse.row >= panes.agent_output.y
                            && mouse.row < panes.agent_output.y + panes.agent_output.height;
                        // Dispatch surface click only when no blocking modal is open.
                        let dispatch_allowed = state.surface_summary_overlay.is_none()
                            && !state.show_stats_overlay
                            && !state.show_patterns
                            && !state.show_findings
                            && !state.show_settings_overlay
                            && !state.show_git_init_offer
                            && !state.show_no_tasks_warning
                            && !state.awaiting_commit_approval
                            && state.running_screen_modal.is_none()
                            && state.inject_input.is_none();
                        let surface_for_click: Option<ClickableSurface> = if on_sep && in_middle {
                            None
                        } else if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                            Some(ClickableSurface::AgentOutput)
                        } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row) {
                            Some(ClickableSurface::TaskQueue)
                        } else if tui::rect_contains(panes.narrative, mouse.column, mouse.row) {
                            Some(ClickableSurface::Narrative)
                        } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                            Some(ClickableSurface::SkillCitations)
                        } else if panes
                            .extensions_used
                            .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                        {
                            None // Extensions pane has no specific surface yet
                        } else if tui::rect_contains(stats_rect, mouse.column, mouse.row) {
                            Some(ClickableSurface::Stats)
                        } else {
                            None
                        };
                        if on_sep && in_middle {
                            state.dragging_split = true;
                        } else if tui::rect_contains(panes.agent_output, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::AgentOutput;
                        } else if tui::rect_contains(panes.task_queue, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::TaskQueue;
                        } else if tui::rect_contains(panes.narrative, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::Narrative;
                        } else if tui::rect_contains(panes.patterns, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::PatternsLearned;
                        } else if panes
                            .extensions_used
                            .is_some_and(|r| tui::rect_contains(r, mouse.column, mouse.row))
                        {
                            state.focused_pane = state::TuiPane::Extensions;
                        } else if tui::rect_contains(stats_rect, mouse.column, mouse.row) {
                            state.focused_pane = state::TuiPane::Stats;
                        } else {
                            let full_area =
                                ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
                            let layout_chunks = ratatui::layout::Layout::default()
                                .direction(ratatui::layout::Direction::Vertical)
                                .constraints([
                                    ratatui::layout::Constraint::Length(5),
                                    ratatui::layout::Constraint::Length(9),
                                    ratatui::layout::Constraint::Min(8),
                                    ratatui::layout::Constraint::Length(8),
                                    ratatui::layout::Constraint::Length(1),
                                ])
                                .split(full_area);
                            let status_bar = layout_chunks[4];
                            if mouse.row == status_bar.y {
                                if let Some(action) = tui::running_status_bar_hit_test(
                                    status_bar,
                                    mouse.column,
                                    state,
                                ) {
                                    match action {
                                        tui::RunningStatusBarAction::Quit => {
                                            if state.dual_arena_ready() {
                                                let project_dir = state
                                                    .buildloop_dir
                                                    .parent()
                                                    .unwrap_or(std::path::Path::new("."))
                                                    .to_path_buf();
                                                enter_home_surface(
                                                    &project_dir,
                                                    state,
                                                    Some("Arena results preserved in .buildloop/arena/".to_string()),
                                                );
                                            } else if state.stop_after_task {
                                                state.stop_after_task = false;
                                                state.remove_stop_file();
                                                state.log("Stop cancelled -- resuming build");
                                            } else {
                                                state.stop_after_task = true;
                                                state.write_stop_file();
                                                state.log("Stopping after current task (q again to cancel, Ctrl+C to force quit)");
                                            }
                                        }
                                        tui::RunningStatusBarAction::Settings => {
                                            toggle_settings_overlay(state);
                                        }
                                        tui::RunningStatusBarAction::ToggleView => {
                                            if !state.show_running_explorer {
                                                if state.running_explorer.is_none() {
                                                    let project_dir = state
                                                        .buildloop_dir
                                                        .parent()
                                                        .unwrap_or(std::path::Path::new("."));
                                                    let scenario =
                                                        detect_startup_scenario(project_dir);
                                                    let plan_status = classify_plan_status(
                                                        &self::contract::ContractPaths::resolve(
                                                            project_dir,
                                                        )
                                                        .tasks_path,
                                                    );
                                                    state.running_explorer =
                                                        Some(StartupState::new(
                                                            project_dir,
                                                            scenario,
                                                            plan_status,
                                                            None,
                                                        ));
                                                }
                                                state.show_running_explorer = true;
                                                state.focused_pane = state::TuiPane::Explorer;
                                            } else {
                                                state.show_running_explorer = false;
                                            }
                                        }
                                        tui::RunningStatusBarAction::Patterns => {
                                            state.show_patterns = !state.show_patterns;
                                            if state.show_patterns {
                                                refresh_skill_citation_summary(state);
                                            }
                                        }
                                        tui::RunningStatusBarAction::Stats => {
                                            if state.show_stats_overlay {
                                                state.show_stats_overlay = false;
                                                state.stats_loading = false;
                                                state.stats_overlay_report = None;
                                                state.stats_overlay_scroll = 0;
                                            } else {
                                                compute_and_show_stats_overlay(state);
                                            }
                                        }
                                        tui::RunningStatusBarAction::Findings => {
                                            state.show_findings = !state.show_findings;
                                        }
                                        tui::RunningStatusBarAction::Inject => {
                                            state.inject_input = Some(String::new());
                                        }
                                        tui::RunningStatusBarAction::Approve
                                        | tui::RunningStatusBarAction::Deny
                                        | tui::RunningStatusBarAction::Continue => {}
                                    }
                                }
                            }
                        }
                        // Per-pane AI summary dispatch (T1.33). Triggered after
                        // focused_pane updates. Gated by modal-focus barriers so
                        // open overlays/modals consume the click instead.
                        if let Some(s) = surface_for_click {
                            if dispatch_allowed {
                                let project_dir = state
                                    .buildloop_dir
                                    .parent()
                                    .unwrap_or(std::path::Path::new("."))
                                    .to_path_buf();
                                handle_surface_click(state, &project_dir, config, s);
                            }
                        }
                    }
                    MouseEventKind::Drag(MouseButton::Left) if state.dragging_split => {
                        let terminal_size = crossterm::terminal::size().unwrap_or((120, 40));
                        let total_width = terminal_size.0;
                        if total_width > 0 {
                            let pct = (mouse.column as u32 * 100 / total_width as u32).clamp(20, 80)
                                as u16;
                            state.agent_pane_split = pct;
                        }
                    }
                    MouseEventKind::Up(MouseButton::Left) => {
                        if state.dragging_split {
                            state.dragging_split = false;
                            Config::save_agent_pane_split_global(state.agent_pane_split);
                        }
                    }
                    _ => {}
                }
            }
        }
        AppEvent::Paste(text) => {
            if let Some(ref mut buf) = state.inject_input {
                buf.push_str(&text);
            }
        }
        AppEvent::PlanningFinished(outcome) => {
            let message = if let Some(error) = outcome.error {
                format!("Ignoring late planning result while running: {}", error)
            } else {
                format!(
                    "Ignoring late planning result while running ({} total tasks, {} pending)",
                    outcome.total_tasks, outcome.pending_tasks
                )
            };
            state.log(message);
        }
        AppEvent::OrchestratorFinished(_) => {
            state.log("Ignoring late orchestrator result while running");
        }
        AppEvent::WelcomeMessage(_) => {}
        AppEvent::SurfaceSummaryReady { surface, outcome } => {
            if let Some(overlay) = state.surface_summary_overlay.as_mut() {
                if overlay.surface == surface {
                    overlay.in_flight = false;
                    overlay.summary = Some(outcome.summary);
                    overlay.last_cache_hit = outcome.cache_hit;
                    overlay.last_model = outcome.model;
                    overlay.last_provider = outcome.provider;
                    overlay.last_error = outcome.error;
                }
            }
        }
        AppEvent::NarrativeRefresh(brief) => {
            state.last_commit_brief = brief;
        }
    }
}

fn handle_inject_key(state: &mut AppState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Char(c) => {
            if let Some(ref mut buf) = state.inject_input {
                buf.push(c);
            }
        }
        KeyCode::Backspace => {
            if let Some(ref mut buf) = state.inject_input {
                buf.pop();
            }
        }
        KeyCode::Esc if !handle_overlay_esc(state) => {
            state.inject_input = None;
        }
        KeyCode::Esc => {}
        KeyCode::Enter => {
            let text = state.inject_input.take().unwrap_or_default();
            let text = text.trim().to_string();
            if text.is_empty() {
                return;
            }
            // "!" prefix = run next (insert after current task)
            let (run_next, description) = if let Some(rest) = text.strip_prefix('!') {
                (true, rest.trim().to_string())
            } else {
                (false, text)
            };
            if description.is_empty() {
                return;
            }
            commit_inject_task(state, &description, run_next);
        }
        _ => {}
    }
}

fn commit_inject_task(state: &mut AppState, description: &str, run_next: bool) {
    let lock = state.tasks_file_lock.clone();
    let _lock = lock.lock().unwrap_or_else(|e| e.into_inner());
    let project_dir = state.buildloop_dir.parent().unwrap_or(Path::new("."));
    let plan_path = ContractPaths::resolve(project_dir).tasks_path;

    // Read existing plan to find highest H-group number (H{N}.{M} format).
    // The task parser regex requires `[A-Za-z]?\d+\.\d+:` so we must use
    // dot-separated IDs like H1.1, H2.1, etc.
    let content = std::fs::read_to_string(&plan_path).unwrap_or_default();
    let mut max_h_group: usize = 0;
    for line in content.lines() {
        let trimmed = line.trim_start();
        let rest = trimmed
            .strip_prefix("- [ ] H")
            .or_else(|| trimmed.strip_prefix("- [x] H"));
        if let Some(rest) = rest {
            // Parse the group number before the dot (e.g. "3" from "H3.1: desc")
            if let Some(num_str) = rest.split('.').next() {
                if let Ok(n) = num_str.trim().parse::<usize>() {
                    max_h_group = max_h_group.max(n);
                }
            }
        }
    }

    let next_group = max_h_group + 1;
    let task_id = format!("H{}.1", next_group);
    let new_task_line = format!("- [ ] {}: {}", task_id, description);

    if run_next {
        // Insert right after the current task's line in the file.
        // Find the first unchecked task line and insert before it.
        let current_line = state
            .current_task
            .as_ref()
            .map(|t| t.line_number)
            .unwrap_or(0);
        let lines: Vec<&str> = content.lines().collect();
        let mut insert_at = None;

        // Find the first pending task after the current one
        for (i, line) in lines.iter().enumerate() {
            let trimmed = line.trim_start();
            if trimmed.starts_with("- [ ] ") && i + 1 > current_line {
                insert_at = Some(i);
                break;
            }
        }

        let mut new_content = String::new();
        match insert_at {
            Some(pos) => {
                for (i, line) in lines.iter().enumerate() {
                    if i == pos {
                        new_content.push_str(&new_task_line);
                        new_content.push('\n');
                    }
                    new_content.push_str(line);
                    new_content.push('\n');
                }
            }
            None => {
                // No pending task found after current -- append
                new_content = content.clone();
                if !new_content.ends_with('\n') {
                    new_content.push('\n');
                }
                new_content.push_str(&new_task_line);
                new_content.push('\n');
            }
        }

        if let Err(e) = atomic_write_file(&plan_path, new_content.as_bytes()) {
            state.log(format!("Failed to inject task: {}", e));
            return;
        }
    } else {
        // Append to end (default) -- read + atomic write for crash safety
        let mut full_content = content.clone();
        if !full_content.ends_with('\n') {
            full_content.push('\n');
        }
        full_content.push_str(&new_task_line);
        full_content.push('\n');
        if let Err(e) = atomic_write_file(&plan_path, full_content.as_bytes()) {
            state.log(format!("Failed to inject task: {}", e));
            return;
        }
    }

    let placement = if run_next { " (run next)" } else { "" };
    state.agent_output.push(format!(
        "[injected] {}: {}{}",
        task_id, description, placement
    ));
    state.log(format!("Injected task {}{}", task_id, placement));
    state.total_count += 1;
}

const AGENT_OUTPUT_CAP: usize = 2000;

#[allow(dead_code)]
fn cycle_settings_cursor(state: &mut AppState, _config: &Config) {
    let project_dir = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."));
    match state.settings_overlay_cursor {
        0 => {
            state.run_mode = match state.run_mode.as_str() {
                "auto" => "sprint".into(),
                "sprint" => "review".into(),
                _ => "auto".into(),
            };
            Config::save_run_mode(project_dir, &state.run_mode);
        }
        1 => {
            let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
            if !unified.is_empty() {
                state.builder_cursor = (state.builder_cursor + 1) % unified.len();
                let val = unified[state.builder_cursor].clone();
                apply_builder_selection(state, &val);
            }
        }
        2 => {
            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
            state.tui_theme = new_theme;
            Config::save_theme(project_dir, name);
        }
        _ => {}
    }
}

#[allow(dead_code)]
pub(super) fn cycle_settings_cursor_startup(state: &mut AppState) {
    let project_dir = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."));
    match state.settings_overlay_cursor {
        0 => {
            state.run_mode = match state.run_mode.as_str() {
                "auto" => "sprint".into(),
                "sprint" => "review".into(),
                _ => "auto".into(),
            };
            Config::save_run_mode(project_dir, &state.run_mode);
        }
        1 => {
            let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
            if !unified.is_empty() {
                state.builder_cursor = (state.builder_cursor + 1) % unified.len();
                let val = unified[state.builder_cursor].clone();
                apply_builder_selection(state, &val);
            }
        }
        2 => {
            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
            state.tui_theme = new_theme;
            Config::save_theme(project_dir, name);
        }
        _ => {}
    }
}

#[allow(dead_code)]
fn cycle_settings_left(state: &mut AppState, _config: &Config) {
    let project_dir = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."));
    match state.settings_overlay_cursor {
        0 => {
            state.run_mode = match state.run_mode.as_str() {
                "auto" => "review".into(),
                "sprint" => "auto".into(),
                _ => "sprint".into(),
            };
            Config::save_run_mode(project_dir, &state.run_mode);
        }
        1 => {
            let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
            if !unified.is_empty() {
                state.builder_cursor = if state.builder_cursor == 0 {
                    unified.len() - 1
                } else {
                    state.builder_cursor - 1
                };
                let val = unified[state.builder_cursor].clone();
                apply_builder_selection(state, &val);
            }
        }
        2 => {
            let (new_theme, name) = crate::tui::theme::cycle_prev(&state.tui_theme);
            state.tui_theme = new_theme;
            Config::save_theme(project_dir, name);
        }
        _ => {}
    }
}

#[allow(dead_code)]
fn cycle_settings_right(state: &mut AppState, _config: &Config) {
    let project_dir = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."));
    match state.settings_overlay_cursor {
        0 => {
            state.run_mode = match state.run_mode.as_str() {
                "auto" => "sprint".into(),
                "sprint" => "review".into(),
                _ => "auto".into(),
            };
            Config::save_run_mode(project_dir, &state.run_mode);
        }
        1 => {
            let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
            if !unified.is_empty() {
                state.builder_cursor = (state.builder_cursor + 1) % unified.len();
                let val = unified[state.builder_cursor].clone();
                apply_builder_selection(state, &val);
            }
        }
        2 => {
            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
            state.tui_theme = new_theme;
            Config::save_theme(project_dir, name);
        }
        _ => {}
    }
}

#[allow(dead_code)]
pub(super) fn cycle_settings_left_startup(state: &mut AppState) {
    let project_dir = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."));
    match state.settings_overlay_cursor {
        0 => {
            state.run_mode = match state.run_mode.as_str() {
                "auto" => "review".into(),
                "sprint" => "auto".into(),
                _ => "sprint".into(),
            };
            Config::save_run_mode(project_dir, &state.run_mode);
        }
        1 => {
            let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
            if !unified.is_empty() {
                state.builder_cursor = if state.builder_cursor == 0 {
                    unified.len() - 1
                } else {
                    state.builder_cursor - 1
                };
                let val = unified[state.builder_cursor].clone();
                apply_builder_selection(state, &val);
            }
        }
        2 => {
            let (new_theme, name) = crate::tui::theme::cycle_prev(&state.tui_theme);
            state.tui_theme = new_theme;
            Config::save_theme(project_dir, name);
        }
        _ => {}
    }
}

#[allow(dead_code)]
pub(super) fn cycle_settings_right_startup(state: &mut AppState) {
    let project_dir = state
        .buildloop_dir
        .parent()
        .unwrap_or(std::path::Path::new("."));
    match state.settings_overlay_cursor {
        0 => {
            state.run_mode = match state.run_mode.as_str() {
                "auto" => "sprint".into(),
                "sprint" => "review".into(),
                _ => "auto".into(),
            };
            Config::save_run_mode(project_dir, &state.run_mode);
        }
        1 => {
            let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
            if !unified.is_empty() {
                state.builder_cursor = (state.builder_cursor + 1) % unified.len();
                let val = unified[state.builder_cursor].clone();
                apply_builder_selection(state, &val);
            }
        }
        2 => {
            let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
            state.tui_theme = new_theme;
            Config::save_theme(project_dir, name);
        }
        _ => {}
    }
}

// ─── New Settings Overlay Handlers (section model) ──────────

fn handle_settings_action(state: &mut AppState) {
    let row = state
        .settings_overlay
        .as_ref()
        .and_then(|ov| ov.row_at_focus());
    let Some(row) = row else {
        return;
    };
    settings_action_for_row(state, &row);
    sync_settings_overlay_view(state);
}

fn settings_action_for_row(state: &mut AppState, row: &state::RowId) {
    match row {
        state::RowId::SectionHeader(id) => {
            if let Some(ref mut ov) = state.settings_overlay {
                ov.toggle_section(id);
            }
        }
        state::RowId::Field(field_id) => match settings_field_kind(field_id) {
            state::FieldKind::Bool => {
                let config = load_settings_config(state);
                let new_val = if config.field_value(field_id) == "true" {
                    "false"
                } else {
                    "true"
                };
                if let Ok(()) = Config::save_field(overlay_project_dir(state), field_id, new_val) {
                    apply_field_to_state(state, field_id, new_val);
                }
            }
            state::FieldKind::Enum => {
                cycle_enum_field(state, field_id, 1);
            }
            state::FieldKind::Number | state::FieldKind::Editor => {
                begin_inline_edit(state, field_id);
            }
            state::FieldKind::Readonly => {}
            state::FieldKind::StagePicker => {
                open_model_picker(state, field_id);
            }
        },
        state::RowId::ReportLine(_, _) => {}
        state::RowId::ActionButton(_, action) => match action {
            state::Action::RerunEvalOnLastRun => {
                let project_dir = overlay_project_dir(state).to_path_buf();
                let _ = eval::run_for_current_task(&project_dir);
                refresh_eval_report_cache(state);
            }
            state::Action::ViewInjectedPatterns => {
                if let Some(ref mut ov) = state.settings_overlay {
                    if let Some(ref mut cache) = ov.patterns_section_cache {
                        cache.filter = state::PatternsFilter::InjectedThisSession;
                    }
                }
            }
            state::Action::ViewAllPatterns => {
                if let Some(ref mut ov) = state.settings_overlay {
                    if let Some(ref mut cache) = ov.patterns_section_cache {
                        cache.filter = state::PatternsFilter::All;
                    }
                }
            }
        },
    }
}

fn handle_settings_left(state: &mut AppState) {
    let row = state
        .settings_overlay
        .as_ref()
        .and_then(|ov| ov.row_at_focus());
    let Some(state::RowId::Field(field_id)) = row else {
        return;
    };
    match settings_field_kind(&field_id) {
        state::FieldKind::Bool => {
            let config = load_settings_config(state);
            let new_val = if config.field_value(&field_id) == "true" {
                "false"
            } else {
                "true"
            };
            if let Ok(()) = Config::save_field(overlay_project_dir(state), &field_id, new_val) {
                apply_field_to_state(state, &field_id, new_val);
            }
        }
        state::FieldKind::Enum => {
            cycle_enum_field(state, &field_id, -1);
        }
        _ => {}
    }
}

fn handle_settings_right(state: &mut AppState) {
    let row = state
        .settings_overlay
        .as_ref()
        .and_then(|ov| ov.row_at_focus());
    let Some(state::RowId::Field(field_id)) = row else {
        return;
    };
    match settings_field_kind(&field_id) {
        state::FieldKind::Bool => {
            let config = load_settings_config(state);
            let new_val = if config.field_value(&field_id) == "true" {
                "false"
            } else {
                "true"
            };
            if let Ok(()) = Config::save_field(overlay_project_dir(state), &field_id, new_val) {
                apply_field_to_state(state, &field_id, new_val);
            }
        }
        state::FieldKind::Enum => {
            cycle_enum_field(state, &field_id, 1);
        }
        _ => {}
    }
}

pub(super) fn open_model_picker(state: &mut AppState, field_id: &str) {
    let stage_id = match Config::stage_id_from_field(field_id) {
        Some(id) => id,
        None => return,
    };
    let is_b = Config::is_pipeline_b_field(field_id);
    let entries = Config::list_available_models(
        state.claude_cli_available,
        state.codex_cli_available,
        state.copilot_available,
        &state.lmstudio_models,
        &state.ollama_models,
    );
    let picker = state::ModelPicker::with_pipeline(stage_id, is_b, entries);
    if let Some(ref mut ov) = state.settings_overlay {
        ov.picker = Some(picker);
    }
    sync_settings_overlay_view(state);
}

pub(super) fn handle_picker_select(state: &mut AppState) {
    let (stage, pipeline_b, provider, model) = {
        let ov = match state.settings_overlay.as_ref() {
            Some(ov) => ov,
            None => return,
        };
        let picker = match ov.picker.as_ref() {
            Some(p) => p,
            None => return,
        };
        let items = picker.visible_items();
        let item = match items.get(picker.focus) {
            Some(i) => i,
            None => return,
        };
        match item {
            state::PickerItem::GroupHeader(group, _) => {
                let group = group.clone();
                if let Some(ref mut ov) = state.settings_overlay {
                    if let Some(ref mut p) = ov.picker {
                        if p.groups_open.contains(&group) {
                            p.groups_open.remove(&group);
                        } else {
                            p.groups_open.insert(group);
                        }
                    }
                }
                return;
            }
            state::PickerItem::Entry(entry) => (
                picker.stage.clone(),
                picker.pipeline_b,
                entry.provider.clone(),
                entry.model.clone(),
            ),
        }
    };

    let project_dir = overlay_project_dir(state);
    if pipeline_b {
        if provider.is_empty() && model.is_empty() {
            Config::clear_stage_routing_b(project_dir, &stage);
        } else {
            Config::set_stage_routing_b(project_dir, &stage, &provider, &model);
        }
    } else if provider.is_empty() && model.is_empty() {
        Config::clear_stage_routing(project_dir, &stage);
    } else {
        Config::set_stage_routing(project_dir, &stage, &provider, &model);
    }
    if stage == "build" && !pipeline_b {
        state.build_stage_label = Config::display_provider_model(&provider, &model);
    }
    mark_settings_dirty(state);

    // Close picker after selection
    if let Some(ref mut ov) = state.settings_overlay {
        ov.picker = None;
    }
}

fn cycle_enum_field(state: &mut AppState, field_id: &str, direction: i32) {
    let project_dir = overlay_project_dir(state).to_path_buf();
    match field_id {
        "arena" => {
            let new_mode = if state.arena_mode == "dual" { "solo" } else { "dual" };
            state.arena_mode = new_mode.to_string();
            Config::save_arena_mode(&project_dir, new_mode);
            if new_mode == "solo" {
                state.reset_dual_build();
            }
            let dual = new_mode == "dual";
            if let Some(ref mut ov) = state.settings_overlay {
                // Preserve user-visible overlay state across the rebuild:
                // focus position, scroll, expanded/collapsed sections, dirty
                // flag, and baseline JSON. Then clamp focus since dual->solo
                // drops the Pipeline B rows (~5 fields) and could leave the
                // cursor out of range.
                let old_focus = ov.focus;
                let old_scroll = ov.scroll_offset;
                let old_expanded = ov.expanded_sections.clone();
                let old_dirty = ov.dirty;
                let old_original = ov.original_json.clone();
                *ov = state::SettingsOverlayState::with_dual_mode(dual);
                ov.focus = old_focus;
                ov.scroll_offset = old_scroll;
                ov.expanded_sections = old_expanded;
                ov.dirty = old_dirty;
                ov.original_json = old_original;
                ov.clamp_focus();
            }
        }
        "builder" => {
            let unified = build_unified_builders(&state.builder_model_specs, &state.local_models);
            if !unified.is_empty() {
                if direction > 0 {
                    state.builder_cursor = (state.builder_cursor + 1) % unified.len();
                } else {
                    state.builder_cursor = if state.builder_cursor == 0 {
                        unified.len() - 1
                    } else {
                        state.builder_cursor - 1
                    };
                }
                let val = unified[state.builder_cursor].clone();
                apply_builder_selection(state, &val);
            }
        }
        "theme" => {
            if direction > 0 {
                let (new_theme, name) = crate::tui::theme::cycle_next(&state.tui_theme);
                state.tui_theme = new_theme;
                Config::save_theme(&project_dir, name);
            } else {
                let (new_theme, name) = crate::tui::theme::cycle_prev(&state.tui_theme);
                state.tui_theme = new_theme;
                Config::save_theme(&project_dir, name);
            }
        }
        _ => {
            let values = Config::enum_values(field_id);
            if values.is_empty() {
                return;
            }
            let config = load_settings_config(state);
            let current = config.field_value(field_id);
            let idx = values.iter().position(|v| *v == current).unwrap_or(0);
            let new_idx = if direction > 0 {
                (idx + 1) % values.len()
            } else if idx == 0 {
                values.len() - 1
            } else {
                idx - 1
            };
            let new_val = values[new_idx];
            if let Ok(()) = Config::save_field(&project_dir, field_id, new_val) {
                apply_field_to_state(state, field_id, new_val);
            }
        }
    }
    mark_settings_dirty(state);
}

fn apply_field_to_state(state: &mut AppState, field_id: &str, value: &str) {
    match field_id {
        "run_mode" => state.run_mode = value.to_string(),
        "preview_wrap" => {
            if let Some(ref mut startup) = state.startup {
                startup.preview_wrap = value == "true";
            }
        }
        _ => {}
    }
}

fn compute_and_show_stats_overlay(state: &mut AppState) {
    if state.stats_loading {
        return;
    }
    let event_tx = match state.event_tx.clone() {
        Some(tx) => tx,
        None => {
            state.log("Stats: event channel not available".to_string());
            return;
        }
    };
    let buildloop_dir = state.buildloop_dir.clone();
    state.stats_loading = true;
    tokio::spawn(async move {
        let result = tokio::task::spawn_blocking(move || {
            let obs_dir = match crate::stats::observatory_dir() {
                Ok(d) => d,
                Err(_) => return None,
            };
            let project_dir = buildloop_dir.parent().unwrap_or(std::path::Path::new("."));
            let canonical =
                dunce::canonicalize(project_dir).unwrap_or_else(|_| project_dir.to_path_buf());
            let (events, skipped) = match crate::stats::load_events(&obs_dir, 1, Some(&canonical)) {
                Ok(r) => r,
                Err(_) => return None,
            };
            Some(crate::stats::compute_stats(
                &events,
                skipped,
                1,
                Some(&canonical.display().to_string()),
                false,
            ))
        })
        .await;
        match result {
            Ok(Some(report)) => {
                let _ = event_tx.send(AppEvent::LoopEvent(LoopEvent::StatsReady(Box::new(report))));
            }
            _ => {
                let _ = event_tx.send(AppEvent::LoopEvent(LoopEvent::StatsLoadFailed));
            }
        }
    });
}

fn refresh_patterns_cache(state: &mut AppState, config: &Config) {
    use crate::patterns;
    let dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    state.patterns_cache = Some(patterns::load_patterns(&dir));
    state.patterns_dir_cache = Some(dir);
}

fn refresh_skill_citation_summary(state: &mut AppState) {
    let db_path = crate::skills_telemetry::db_path();
    match crate::skills_telemetry::open_db(&db_path) {
        Ok(conn) => {
            let top_skills = crate::skills_telemetry::top_cited_skills(&conn, 50)
                .unwrap_or_default();
            let week_ago = chrono::Utc::now() - chrono::Duration::days(7);
            let week_recent = crate::skills_telemetry::recent_citations(&conn, week_ago)
                .unwrap_or_default();
            let last_cited: Option<(String, String)> = top_skills
                .iter()
                .max_by(|a, b| a.last_used.cmp(&b.last_used))
                .and_then(|r| {
                    r.last_used
                        .as_ref()
                        .map(|d| (r.skill_name.clone(), d.clone()))
                });
            let all_skills = crate::skills_telemetry::top_cited_skills(&conn, 10_000)
                .unwrap_or_default();
            let top3: Vec<crate::skills_telemetry::TelemetryRecord> =
                week_recent.into_iter().take(3).collect();
            state.skill_citation_summary = Some(crate::app::state::SkillCitationSummary {
                session_skills_cited: state.session_skill_citations_set.len(),
                session_citations: state.session_skill_citation_count,
                top_skills: top3,
                last_cited,
                all_skills,
                db_available: true,
                db_path,
            });
        }
        Err(_) => {
            state.skill_citation_summary = Some(crate::app::state::SkillCitationSummary {
                session_skills_cited: state.session_skill_citations_set.len(),
                session_citations: state.session_skill_citation_count,
                top_skills: Vec::new(),
                last_cited: None,
                all_skills: Vec::new(),
                db_available: false,
                db_path,
            });
        }
    }
    state.skill_citation_summary_loaded_at = Some(std::time::Instant::now());
}

fn format_agent_error(kind: &AgentErrorKind) -> String {
    match kind {
        AgentErrorKind::ContextOverflow { tokens, ctx_size } => match (tokens, ctx_size) {
            (Some(t), Some(c)) => format!(
                "LM Studio context overflow: prompt was {} tokens but the loaded model has only n_ctx={}. Reload the model in LM Studio with a larger context size.",
                t, c
            ),
            _ => "LM Studio context overflow: the prompt exceeded the loaded model's n_ctx. Reload the model with a larger context size in LM Studio.".to_string(),
        },
        AgentErrorKind::ProviderUnreachable { url } => match url {
            Some(u) => format!(
                "Provider unreachable at {}. Confirm LM Studio is running and listening on the expected port.",
                u
            ),
            None => "Provider unreachable: failed to connect. Confirm LM Studio is running and listening on the expected port (default 127.0.0.1:1234).".to_string(),
        },
        AgentErrorKind::ModelNotLoaded { model } => match model {
            Some(m) => format!(
                "Model not loaded: '{}'. Load this model in LM Studio (or pick a different one in foundry settings).",
                m
            ),
            None => "Model not loaded: the requested model is not available in LM Studio. Load it (or pick a different one in foundry settings).".to_string(),
        },
    }
}

fn record_context_pct_for_stage(
    stage_id: Option<&str>,
    role: Option<&AgentRole>,
    pct: u8,
    qrpba_context_pcts: &mut [Option<u8>; 5],
    custom_context_pcts: &mut HashMap<String, u8>,
) {
    if let Some(stage_id) = stage_id {
        if let Some(stage_role) = AgentRole::from_str(stage_id) {
            if let Some(slot) = stage_role.qrpba_slot() {
                qrpba_context_pcts[slot] = Some(pct);
            }
            return;
        }

        let stage_id = stage_id.trim();
        if !stage_id.is_empty() {
            custom_context_pcts.insert(stage_id.to_string(), pct);
        }
        return;
    }

    if let Some(role) = role {
        if let Some(slot) = role.qrpba_slot() {
            qrpba_context_pcts[slot] = Some(pct);
        }
    }
}

fn handle_agent_output(state: &mut AppState, output: AgentOutputEvent) {
    state.events_received += 1;
    match output {
        AgentOutputEvent::TextDelta(ref chunk) => {
            if state.stream_state != StreamState::WritingText {
                state.stream_state = StreamState::WritingText;
                state.stream_text_delta_count = 0;
            }
            state.stream_text_delta_count = state.stream_text_delta_count.saturating_add(1);
            if state.stream_text_delta_count == 1 {
                state.agent_output.push(chunk.clone());
            } else if let Some(last) = state.agent_output.last_mut() {
                last.push_str(chunk);
            } else {
                state.agent_output.push(chunk.clone());
            }
            state.status_summary =
                format!("writing... ({} chunks)", state.stream_text_delta_count);
        }
        AgentOutputEvent::Text(ref text) => {
            if text.starts_with("[rate limited]") {
                // Show in status bar only -- don't pollute the output panel
                state.status_summary = "Waiting for API retry".to_string();
            } else {
                state.agent_output.push(text.clone());
                state.stream_state = StreamState::Idle;
                state.stream_text_delta_count = 0;
            }
        }
        AgentOutputEvent::ToolUse {
            ref tool,
            ref input_preview,
        } => {
            let msg = if input_preview.is_empty() {
                format!("[tool] {}", tool)
            } else {
                format!("[tool] {} — {}", tool, input_preview)
            };
            state.agent_output.push(msg);

            // Derive human-readable status summary from tool call
            let basename = Path::new(input_preview.as_str())
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or(input_preview.as_str());
            state.status_summary = match tool.as_str() {
                "Read" => format!("Reading {}", basename),
                "Glob" => format!("Exploring {}", truncate_str(input_preview, 40)),
                "Grep" => format!("Searching for {}", truncate_str(input_preview, 40)),
                "Bash" => format!("Running {}", truncate_str(input_preview, 40)),
                "Edit" | "Write" => {
                    if input_preview.contains("scout-report") {
                        "Writing scout report".to_string()
                    } else if input_preview.contains("current-plan") {
                        "Writing plan".to_string()
                    } else if input_preview.contains("build-claims") {
                        "Writing build claims".to_string()
                    } else {
                        format!("Editing {}", basename)
                    }
                }
                _ => state.status_summary.clone(),
            };
            state.stream_state = StreamState::Reading;
            state.stream_text_delta_count = 0;
        }
        AgentOutputEvent::ToolResult { output_preview } => {
            if !output_preview.is_empty() {
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
            // Track tmux session names from "[foundry] tmux session: ..." messages
            if let Some(rest) = line.strip_prefix("[foundry] tmux session: ") {
                if let Some(name) = rest.split_whitespace().next() {
                    state.tmux_session_names.push(name.to_string());
                }
            }
            // Downgrade expected operational messages from [stderr] to [info]
            if line.contains("exceeds maximum allowed tokens")
                || line.contains("File does not exist")
            {
                state.agent_output.push(format!("[info] {}", line));
            } else {
                state.agent_output.push(format!("[stderr] {}", line));
            }
        }
        AgentOutputEvent::Result(text) => {
            state.agent_output.push(String::new());
            for line in text.lines().take(10) {
                state.agent_output.push(line.to_string());
            }
        }
        AgentOutputEvent::Usage {
            cost_usd,
            input_tokens,
            output_tokens,
            context_window,
            ..
        } => {
            state.session_cost_usd += cost_usd;
            state.session_input_tokens += input_tokens;
            state.session_output_tokens += output_tokens;
            // Update shared atomic for build loop cost-limit check
            let millicents = (cost_usd * 100_000.0) as u64;
            state
                .session_cost_millicents
                .fetch_add(millicents, std::sync::atomic::Ordering::Relaxed);
            let total_tokens = input_tokens + output_tokens;
            if context_window > 0 {
                let pct = ((total_tokens as f64 / context_window as f64) * 100.0).min(100.0) as u8;
                state.agent_context_pct = Some(pct);
                // Save to the stage slot immediately (set_agent resets agent_context_pct
                // when the next stage starts, so we must capture it here)
                let stage_id = state.current_agent_stage_id.clone();
                let role = state.current_agent.as_ref().map(|(role, _)| role.clone());
                record_context_pct_for_stage(
                    stage_id.as_deref(),
                    role.as_ref(),
                    pct,
                    &mut state.spid_context_pcts,
                    &mut state.stage_context_pcts,
                );
            }
        }
        AgentOutputEvent::Error { kind, raw } => {
            let display = format_agent_error(&kind);
            state.agent_output.push(format!("[error] {}", display));
            state.agent_output.push(format!("[error/raw] {}", raw));
            state.log(format!("Agent error: {}", display));
            state.status_summary = display.clone();
            // ─── Circuit breaker (D1.3) ──────────────────────────────
            // Stop the run on the first typed agent error so subsequent
            // pipeline stages don't re-emit the same failure. The main
            // TUI loop pumps state.stop_after_task -> shutdown.store(true)
            // on the next iteration.
            state.last_typed_error = Some(kind.clone());
            let can_retry = matches!(kind, AgentErrorKind::ContextOverflow { .. });
            let toast = if can_retry {
                format!(
                    "{} -- open LM Studio, increase n_ctx, then press R to retry (Esc to dismiss)",
                    display
                )
            } else {
                format!("{} -- run aborted (Esc to dismiss)", display)
            };
            state.typed_error_toast = Some(toast);
            state.typed_error_can_retry = can_retry;
            state.stop_after_task = true;
            state.write_stop_file();
        }
    }
    if state.agent_output.len() > AGENT_OUTPUT_CAP {
        let excess = state.agent_output.len() - AGENT_OUTPUT_CAP;
        state.agent_output.drain(..excess);
        if state.scroll_offset >= excess {
            state.scroll_offset -= excess;
        } else {
            state.scroll_offset = 0;
        }
    }
}

fn handle_dual_build_output(state: &mut AppState, idx: usize, output: AgentOutputEvent) {
    if idx >= 2 {
        return;
    }
    state.dual_build.event_counts[idx] += 1;

    match &output {
        AgentOutputEvent::TextDelta(chunk) => {
            let last_was_delta = state
                .dual_build
                .last_event_was_delta
                .get(idx)
                .copied()
                .unwrap_or(false);
            if last_was_delta {
                if let Some(last) = state.dual_build.streams[idx].last_mut() {
                    last.push_str(chunk);
                } else {
                    state.dual_build.streams[idx].push(chunk.clone());
                }
            } else {
                state.dual_build.streams[idx].push(chunk.clone());
            }
            if let Some(slot) = state.dual_build.last_event_was_delta.get_mut(idx) {
                *slot = true;
            }
        }
        AgentOutputEvent::Text(text) => {
            state.dual_build.streams[idx].push(text.clone());
            if let Some(slot) = state.dual_build.last_event_was_delta.get_mut(idx) {
                *slot = false;
            }
        }
        AgentOutputEvent::ToolUse {
            tool,
            input_preview,
        } => {
            let msg = if input_preview.is_empty() {
                format!("[tool] {}", tool)
            } else {
                format!("[tool] {} -- {}", tool, input_preview)
            };
            state.dual_build.streams[idx].push(msg);
            if let Some(slot) = state.dual_build.last_event_was_delta.get_mut(idx) {
                *slot = false;
            }
        }
        AgentOutputEvent::ToolResult { output_preview } => {
            if !output_preview.is_empty() {
                let first_line = output_preview.lines().next().unwrap_or("");
                let display = if first_line.len() > 100 {
                    format!("[result] {}...", truncate_str(first_line, 100))
                } else {
                    format!("[result] {}", first_line)
                };
                state.dual_build.streams[idx].push(display);
            }
        }
        AgentOutputEvent::Stderr(line) => {
            state.dual_build.streams[idx].push(format!("[stderr] {}", line));
        }
        AgentOutputEvent::Result(text) => {
            state.dual_build.streams[idx].push(String::new());
            for line in text.lines().take(10) {
                state.dual_build.streams[idx].push(line.to_string());
            }
        }
        AgentOutputEvent::Usage {
            cost_usd,
            input_tokens,
            output_tokens,
            context_window,
            ..
        } => {
            state.session_cost_usd += cost_usd;
            state.session_input_tokens += input_tokens;
            state.session_output_tokens += output_tokens;
            let millicents = (cost_usd * 100_000.0) as u64;
            state
                .session_cost_millicents
                .fetch_add(millicents, std::sync::atomic::Ordering::Relaxed);
            state.dual_build.cost_usd[idx] += cost_usd;
            state.dual_build.input_tokens[idx] += input_tokens;
            state.dual_build.output_tokens[idx] += output_tokens;
            let total_tokens = input_tokens + output_tokens;
            if *context_window > 0 {
                let pct = ((total_tokens as f64 / *context_window as f64) * 100.0).min(100.0) as u8;
                let stage_id = state.dual_build.stage_ids[idx].clone();
                let role = state.dual_build.stages[idx].clone();
                record_context_pct_for_stage(
                    stage_id.as_deref(),
                    role.as_ref(),
                    pct,
                    &mut state.dual_build.context_pcts[idx],
                    &mut state.dual_build.stage_context_pcts[idx],
                );
            }
        }
        AgentOutputEvent::Error { kind, raw } => {
            let display = format_agent_error(kind);
            state.dual_build.streams[idx].push(format!("[error] {}", display));
            state.dual_build.streams[idx].push(format!("[error/raw] {}", raw));
            // ─── Circuit breaker (D1.3) ──────────────────────────────
            // Same logic as handle_agent_output: stop both pipelines on
            // the first typed error from either side.
            state.last_typed_error = Some(kind.clone());
            let can_retry = matches!(kind, AgentErrorKind::ContextOverflow { .. });
            let toast = if can_retry {
                format!(
                    "{} -- open LM Studio, increase n_ctx, then press R to retry (Esc to dismiss)",
                    display
                )
            } else {
                format!("{} -- run aborted (Esc to dismiss)", display)
            };
            state.typed_error_toast = Some(toast);
            state.typed_error_can_retry = can_retry;
            state.stop_after_task = true;
            state.write_stop_file();
        }
    }

    // Cap stream buffer
    let cap = AGENT_OUTPUT_CAP;
    if state.dual_build.streams[idx].len() > cap {
        let excess = state.dual_build.streams[idx].len() - cap;
        state.dual_build.streams[idx].drain(..excess);
    }
}

fn handle_dual_pipeline_event(state: &mut AppState, idx: usize, event: AppEvent, _config: &Config) {
    if idx >= 2 {
        return;
    }
    match event {
        AppEvent::AgentOutput(output) => {
            handle_dual_build_output(state, idx, output);
        }
        AppEvent::AgentDone(_success) => {
            // Individual agent done within a pipeline -- not the whole pipeline
        }
        AppEvent::LoopEvent(le) => match le {
            LoopEvent::AgentStarted(role, model) => {
                state.dual_build.stage_ids[idx] = Some(role.slug().to_string());
                state.dual_build.stages[idx] = Some(role);
                state.dual_build.stage_models[idx] = model;
            }
            LoopEvent::AgentStageStarted {
                role,
                stage_id,
                model,
            } => {
                state.dual_build.stages[idx] = Some(role);
                state.dual_build.stage_ids[idx] = Some(stage_id);
                state.dual_build.stage_models[idx] = model;
            }
            LoopEvent::Log(msg) => {
                state.dual_build.streams[idx].push(format!("[log] {}", msg));
                state.dual_build.event_counts[idx] += 1;
            }
            LoopEvent::TaskCompleted(_id, _success) => {
                // Pipeline finished
                state.dual_build.finished[idx] = true;
            }
            _ => {
                // Other loop events from the pipeline -- ignore at top level
            }
        },
        _ => {}
    }
}

pub(super) fn handle_agent_done(state: &mut AppState, success: bool) {
    // ─── Extension & Pattern Reference Detection ───
    if !state.agent_output.is_empty() {
        let agent_role_str = state
            .current_agent
            .as_ref()
            .map(|(role, _)| role.to_string())
            .unwrap_or_else(|| "unknown".to_string());

        // Build lowercased output for keyword matching (join last 200 lines to bound scan cost)
        let scan_lines = state.agent_output.len().min(200);
        let output_text: String = state.agent_output[state.agent_output.len() - scan_lines..]
            .iter()
            .fold(String::new(), |mut acc, line| {
                acc.push(' ');
                acc.push_str(line);
                acc
            })
            .to_lowercase();

        // Check extension keywords (clone to avoid borrow conflict with state.log)
        let ext_kw_snapshot: Vec<(String, Vec<String>)> = state
            .extension_keywords
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        for (ext_name, keywords) in &ext_kw_snapshot {
            let matched: Vec<String> = keywords
                .iter()
                .filter(|kw| kw.len() >= 4 && output_text.contains(kw.as_str()))
                .take(5)
                .cloned()
                .collect();
            if !matched.is_empty() {
                *state
                    .extension_reference_count
                    .entry(ext_name.clone())
                    .or_insert(0) += 1;
                state.log(format!(
                    "Extension '{}' referenced by {} (keywords: {})",
                    ext_name,
                    agent_role_str,
                    matched.join(", ")
                ));
            }
        }

        // Check pattern keywords (clone to avoid borrow conflict with state.log)
        let pat_kw_snapshot: Vec<(String, Vec<String>)> = state
            .active_pattern_keywords
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        for (title, keywords) in &pat_kw_snapshot {
            let has_match = keywords
                .iter()
                .any(|kw| kw.len() >= 4 && output_text.contains(kw.as_str()));
            if has_match {
                state.pattern_apply_count += 1;
                state.log(format!("Pattern '{}' applied by {}", title, agent_role_str));
            }
        }
    }

    if let Some((ref role, _)) = state.current_agent {
        let status = if success { "completed" } else { "FAILED" };
        state.log(format!("{} {}", role, status));
    }
}

fn apply_planning_outcome(state: &mut AppState, outcome: PlanningOutcome) {
    state.clear_agent();
    state.planning = None;
    state.total_count = outcome.total_tasks;
    state.completed_count = outcome.completed_tasks;

    if let Some(error) = outcome.error {
        let message = format!("Planning failed: {}", error);
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
        return;
    }

    if !outcome.success {
        let message = "Planning failed — review planner output and try again".to_string();
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
        return;
    }

    if outcome.pending_tasks > 0 && outcome.return_to_startup {
        let message = format!(
            "Added {} task(s) — {} pending. Review the queue, then Continue when ready.",
            outcome.new_tasks, outcome.pending_tasks
        );
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
    } else if outcome.pending_tasks > 0 {
        state.log(format!(
            "Queue ready — {} total tasks ({} new, {} pending)",
            outcome.total_tasks, outcome.new_tasks, outcome.pending_tasks
        ));
        state.pending_transition = Some(PendingTransition::StartBuild);
    } else {
        let message = if outcome.total_tasks == 0 {
            "Planning complete — no tasks found".to_string()
        } else {
            "Planning complete — no pending tasks found".to_string()
        };
        state.log(message.clone());
        state.pending_transition = Some(PendingTransition::ShowStartup {
            message: Some(message),
        });
    }
}

fn spawn_design_loop(
    project_dir: &Path,
    config: &Config,
    event_tx: &mpsc::UnboundedSender<AppEvent>,
    state: &mut AppState,
    user_intent: String,
    shutdown: &Arc<AtomicBool>,
) {
    let orch_config = OrchestratorConfig::from_config(config);
    let label = format!("Design: {}", truncate_str(&user_intent, 48));
    state.phase = AppPhase::Planning;
    state.startup = None;
    state.planning = Some(PlanningState {
        label: label.clone(),
        user_intent: Some(user_intent.clone()),
        orchestrator_mode: true,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: orch_config.max_iterations,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.current_task = None;
    state.next_task_hint = None;
    state.is_discovering = false;
    state.set_agent(
        AgentRole::Planner,
        &format!("{} {}", orch_config.proposer_provider, {
            let m = orch_config.proposer_model.trim();
            let mut chars = m.chars();
            match chars.next() {
                Some(c) => format!("{}{}", c.to_uppercase(), chars.as_str()),
                None => String::new(),
            }
        }),
    );
    state.log(format!("Design started — {}", label));

    let project_dir = project_dir.to_path_buf();
    let event_tx = event_tx.clone();
    let user_intent_clone = user_intent;
    let shutdown_clone = Some(shutdown.clone());

    // Create a channel to forward agent output events from the orchestrator to the TUI
    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel::<AgentOutputEvent>();
    let forward_tx = event_tx.clone();
    tokio::spawn(async move {
        while let Some(evt) = agent_rx.recv().await {
            let _ = forward_tx.send(AppEvent::AgentOutput(evt));
        }
    });

    tokio::spawn(async move {
        let buildloop_dir = project_dir.join(".buildloop");
        let log_dir = buildloop_dir.join("logs");
        if let Err(e) = std::fs::create_dir_all(&log_dir) {
            eprintln!(
                "Warning: failed to create log directory {}: {}",
                log_dir.display(),
                e
            );
        }

        let tx = event_tx.clone();
        let result = orchestrator::orchestrate(
            &user_intent_clone,
            &orch_config,
            &project_dir,
            &log_dir,
            |msg| {
                let _ = tx.send(AppEvent::AgentOutput(AgentOutputEvent::Text(format!(
                    "[orchestrator] {}",
                    msg
                ))));
            },
            Some(agent_tx),
            shutdown_clone,
        )
        .await;

        match result {
            Ok(outcome) => {
                let _ = orchestrator::write_orchestrator_output(&buildloop_dir, &outcome);
                let _ = event_tx.send(AppEvent::OrchestratorFinished(outcome));
            }
            Err(e) => {
                let fallback = OrchestratorOutcome {
                    artifact: orchestrator::ProposerOutput {
                        artifact_type: "analysis".to_string(),
                        artifact_text: format!("Orchestrator error: {}", e),
                        rationale: String::new(),
                        design_assertions: Vec::new(),
                    },
                    final_review: orchestrator::ReviewerOutput {
                        status: "findings".to_string(),
                        findings: Vec::new(),
                        validated: Vec::new(),
                    },
                    iterations: 0,
                    accepted: false,
                };
                let _ = event_tx.send(AppEvent::OrchestratorFinished(fallback));
            }
        }
    });
}

fn apply_orchestrator_outcome(state: &mut AppState, outcome: OrchestratorOutcome) {
    state.clear_agent();
    state.planning = None;

    let has_unresolved = !outcome.accepted && !outcome.final_review.findings.is_empty();

    let message = if outcome.accepted {
        format!(
            "Design accepted after {} iteration(s). Output in .buildloop/orchestrator-output.md",
            outcome.iterations
        )
    } else {
        format!(
            "Design completed with unresolved findings after {} iteration(s). Output in .buildloop/orchestrator-output.md",
            outcome.iterations
        )
    };
    state.log(message.clone());

    state.last_orchestrator_outcome = Some(outcome);

    if has_unresolved {
        state.show_findings = true;
        state.findings_scroll = 0;
    }

    state.pending_transition = Some(PendingTransition::ShowStartup {
        message: Some(message),
    });
}

// ─── Plan Mode (gap analysis, no building) ───────────────────

pub async fn run_plan_mode(project_dir: &Path, max_iterations: u64) -> Result<()> {
    planning::run_plan_mode(project_dir, max_iterations).await
}

// ─── Headless Mode ───────────────────────────────────────────

pub async fn run_headless(project_dir: &Path, output_format: Option<String>) -> Result<()> {
    commands::run_headless(project_dir, output_format).await
}

// ─── Status & Tasks Commands ─────────────────────────────────

pub fn show_status(project_dir: &Path) -> Result<()> {
    commands::show_status(project_dir)
}

pub fn show_tasks(project_dir: &Path) -> Result<()> {
    commands::show_tasks(project_dir)
}

pub fn show_task_evaluation(project_dir: &Path) -> Result<()> {
    commands::show_task_evaluation(project_dir)
}

// ─── Extract Patterns Command ─────────────────────────────────

pub fn run_extract(project_dir: &Path) -> Result<()> {
    commands::run_extract(project_dir)
}

pub fn run_patterns_prune(yes: bool) -> Result<()> {
    commands::run_patterns_prune(yes)
}

pub fn run_patterns_prune_stale(yes: bool, dry_run: bool) -> Result<()> {
    commands::run_patterns_prune_stale(yes, dry_run)
}

pub fn run_patterns_migrate_to_skills(yes: bool, dry_run: bool) -> Result<()> {
    commands::run_patterns_migrate_to_skills(yes, dry_run)
}

pub fn run_patterns_promote(apply: bool, days: u32) -> Result<()> {
    commands::run_patterns_promote(apply, days)
}

// ─── Running Explorer Helpers ─────────────────────────────────

#[derive(Debug)]
enum PipelineClickTarget {
    StageSummary {
        stage_id: String,
        fallback_file: Option<std::path::PathBuf>,
    },
    OpenFile(std::path::PathBuf),
    None,
}

fn stage_fallback_file(
    stage_id: &str,
    project_dir: &std::path::Path,
) -> Option<std::path::PathBuf> {
    let buildloop = project_dir.join(".buildloop");
    match stage_id {
        "scout" => Some(buildloop.join("scout-report.md")),
        "query" => Some(buildloop.join("questions.md")),
        "research" => Some(buildloop.join("research-report.md")),
        "plan" => Some(buildloop.join("current-plan.md")),
        "implement" => Some(buildloop.join("build-claims.md")),
        "doubt" => Some(buildloop.join("review-report.md")),
        "coach" => Some(buildloop.join("intake-brief.md")),
        "plan-review" => Some(buildloop.join("current-plan.md")),
        "discover" => Some(ContractPaths::resolve(project_dir).tasks_path),
        _ => None,
    }
}

fn pipeline_click_target(
    click: tui::PipelineClick,
    project_dir: &std::path::Path,
    config: &Config,
) -> PipelineClickTarget {
    let enabled_stages: Vec<&crate::config::PipelineStageConfig> = config
        .pipeline_stages
        .iter()
        .filter(|s| s.enabled)
        .collect();
    let mut connected_ids: Vec<String> = Vec::new();
    if config.run_mode == "coach" {
        connected_ids.push("coach".to_string());
    }
    for stage in enabled_stages.iter() {
        connected_ids.push(stage.id.clone());
        if stage.id == "plan" && config.plan_review_enabled {
            connected_ids.push("plan-review".to_string());
        }
    }
    match click {
        tui::PipelineClick::ConnectedStage(i) => {
            let stage_id = match connected_ids.get(i) {
                Some(s) => s.as_str(),
                None => return PipelineClickTarget::None,
            };
            let fallback_file = stage_fallback_file(stage_id, project_dir);
            if config.prefer_file_open_over_summary {
                return match fallback_file {
                    Some(p) => PipelineClickTarget::OpenFile(p),
                    None => PipelineClickTarget::None,
                };
            }
            PipelineClickTarget::StageSummary {
                stage_id: stage_id.to_string(),
                fallback_file,
            }
        }
        tui::PipelineClick::Discover => {
            let fallback = ContractPaths::resolve(project_dir).tasks_path;
            if config.prefer_file_open_over_summary {
                return PipelineClickTarget::OpenFile(fallback);
            }
            PipelineClickTarget::StageSummary {
                stage_id: "discover".to_string(),
                fallback_file: Some(fallback),
            }
        }
        tui::PipelineClick::Ship => {
            if config.prefer_file_open_over_summary {
                return PipelineClickTarget::None;
            }
            PipelineClickTarget::StageSummary {
                stage_id: "ship".to_string(),
                fallback_file: None,
            }
        }
        tui::PipelineClick::Patterns => {
            // The "SKILLS" card (formerly PATTERNS) extracts new skills into
            // ~/.foundry/skills/ after a passing build. There's no single
            // artifact file to fall back to, but the summarizer can still
            // describe the stage from its log tail.
            if config.prefer_file_open_over_summary {
                return PipelineClickTarget::None;
            }
            PipelineClickTarget::StageSummary {
                stage_id: "pattern_extraction".to_string(),
                fallback_file: None,
            }
        }
    }
}

fn stage_summary_inputs(
    stage_id: &str,
    project_dir: &std::path::Path,
) -> (Vec<std::path::PathBuf>, Option<String>) {
    let buildloop = project_dir.join(".buildloop");
    match stage_id {
        "query" => (vec![buildloop.join("questions.md")], None),
        "research" => (vec![buildloop.join("research-report.md")], None),
        "plan" => (vec![buildloop.join("current-plan.md")], None),
        "plan-review" => (vec![buildloop.join("current-plan.md")], None),
        "implement" => (vec![buildloop.join("build-claims.md")], None),
        "doubt" => (vec![buildloop.join("review-report.md")], None),
        "coach" => (vec![buildloop.join("intake-brief.md")], None),
        "scout" => (vec![buildloop.join("scout-report.md")], None),
        "discover" => (
            vec![ContractPaths::resolve(project_dir).tasks_path],
            None,
        ),
        "ship" => (Vec::new(), Some(collect_ship_log_blocking(project_dir))),
        // No single artifact -- the extractor writes per-skill SKILL.md files
        // into ~/.foundry/skills/. The summarizer reads the stage log instead.
        "pattern_extraction" => (Vec::new(), None),
        _ => (Vec::new(), None),
    }
}

fn collect_ship_log_blocking(project_dir: &std::path::Path) -> String {
    let dir_arg = project_dir.display().to_string();
    let log_stdout = std::process::Command::new("git")
        .args([
            "-C",
            &dir_arg,
            "log",
            "-1",
            "--pretty=format:%h %s%n%an <%ae>%n%ad",
            "--date=iso",
        ])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
        .unwrap_or_default();
    let status_stdout = std::process::Command::new("git")
        .args(["-C", &dir_arg, "status", "--porcelain"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
        .unwrap_or_default();
    let combined = format!(
        "git log -1:\n{}\ngit status --porcelain:\n{}",
        log_stdout, status_stdout
    );
    crate::utils::truncate_str(&combined, 4096).to_string()
}

fn handle_pipeline_click_target(
    state: &mut AppState,
    project_dir: &std::path::Path,
    config: &Config,
    target: PipelineClickTarget,
) {
    match target {
        PipelineClickTarget::StageSummary {
            stage_id,
            fallback_file: _,
        } => {
            let already_in_flight = state
                .surface_summary_overlay
                .as_ref()
                .is_some_and(|o| o.stage == stage_id && o.in_flight);
            if !already_in_flight {
                let label = stage_label_for(&stage_id, config);
                trigger_stage_summary(state, project_dir, config, &stage_id, &label, false);
            }
        }
        PipelineClickTarget::OpenFile(path) => {
            navigate_explorer_to_file(state, project_dir, &path);
        }
        PipelineClickTarget::None => {}
    }
}

fn detect_stage_state(stage_id: &str, state: &AppState, buildloop_dir: &Path) -> StageState {
    if let Some((role, _)) = &state.current_agent {
        if role.slug() == stage_id {
            return StageState::Running;
        }
    }
    let log_path = buildloop_dir
        .join("logs")
        .join(format!("{}-out.jsonl", stage_id));
    if log_path.exists() {
        let is_wip = state
            .last_commit_brief
            .as_ref()
            .map(|b| b.subject.starts_with("WIP"))
            .unwrap_or(false);
        if is_wip {
            return StageState::Failed;
        }
        return StageState::Complete;
    }
    StageState::NotStarted
}

fn read_log_tail(buildloop_dir: &Path, stage_id: &str, max_bytes: usize) -> Option<String> {
    let path = buildloop_dir
        .join("logs")
        .join(format!("{}-out.jsonl", stage_id));
    let bytes = std::fs::read(&path).ok()?;
    if bytes.len() <= max_bytes {
        Some(String::from_utf8_lossy(&bytes).into_owned())
    } else {
        Some(String::from_utf8_lossy(&bytes[bytes.len() - max_bytes..]).into_owned())
    }
}

fn stage_label_for(stage_id: &str, config: &Config) -> String {
    match stage_id {
        "plan-review" => "P+".to_string(),
        "ship" => "SHIP".to_string(),
        "discover" => "DISCOVER".to_string(),
        "pattern_extraction" => "SKILLS".to_string(),
        _ => config.pipeline_stage_label(stage_id),
    }
}

fn trigger_stage_summary(
    state: &mut AppState,
    project_dir: &Path,
    config: &Config,
    stage_id: &str,
    stage_label: &str,
    force_refresh: bool,
) {
    let _ = stage_label; // surface.label() now drives the label
    trigger_surface_summary(
        state,
        project_dir,
        config,
        ClickableSurface::PipelineStage(stage_id.to_string()),
        force_refresh,
    );
}

fn trigger_surface_summary(
    state: &mut AppState,
    project_dir: &Path,
    config: &Config,
    surface: ClickableSurface,
    force_refresh: bool,
) {
    let buildloop_dir = state.buildloop_dir.clone();
    let (stage_state, stage_id_for_log) = match &surface {
        ClickableSurface::PipelineStage(sid) => (
            detect_stage_state(sid, state, &buildloop_dir),
            Some(sid.clone()),
        ),
        _ => (StageState::Running, None),
    };
    let (artifacts, extra_log) = surface_summary_inputs(&surface, state, project_dir);
    let disk_log = stage_id_for_log
        .as_deref()
        .and_then(|sid| read_log_tail(&buildloop_dir, sid, 8192));
    let log_tail = match (disk_log, extra_log) {
        (Some(a), Some(b)) => Some(format!("{}\n{}", a, b)),
        (None, Some(b)) => Some(b),
        (Some(a), None) => Some(a),
        (None, None) => None,
    };

    let stage_id_string = match &surface {
        ClickableSurface::PipelineStage(sid) => sid.clone(),
        _ => surface.tag().to_string(),
    };
    let stage_label_string = surface.label();

    let existing = state.surface_summary_overlay.take();
    let preserve_summary = if force_refresh {
        None
    } else {
        existing.as_ref().and_then(|o| o.summary.clone())
    };
    state.surface_summary_overlay = Some(SurfaceSummaryOverlay {
        surface: surface.clone(),
        stage: stage_id_string,
        stage_label: stage_label_string,
        state: stage_state.clone(),
        summary: preserve_summary,
        in_flight: true,
        last_error: None,
        last_cache_hit: false,
        last_model: existing
            .as_ref()
            .map(|o| o.last_model.clone())
            .unwrap_or_default(),
        last_provider: existing
            .as_ref()
            .map(|o| o.last_provider.clone())
            .unwrap_or_default(),
        scroll_offset: if force_refresh {
            0
        } else {
            existing.as_ref().map(|o| o.scroll_offset).unwrap_or(0)
        },
        started_at: std::time::Instant::now(),
    });
    drop(existing);

    let cfg = config.clone();
    let surface_owned = surface.clone();
    let state_clone = stage_state;
    let event_tx = match state.event_tx.clone() {
        Some(t) => t,
        None => return,
    };
    let session_id = state.observatory_session_id.clone().unwrap_or_default();
    let proj = project_dir.to_path_buf();

    tokio::spawn(async move {
        let outcome = summarize_surface(
            surface_owned.clone(),
            state_clone,
            artifacts,
            log_tail,
            &cfg,
            force_refresh,
        )
        .await;
        crate::observatory::log_event(
            &session_id,
            &proj,
            crate::observatory::ObservatoryEvent::StageSummaryRequested {
                stage: outcome.stage.clone(),
                cache_hit: outcome.cache_hit,
                provider: outcome.provider.clone(),
                model: outcome.model.clone(),
                latency_ms: outcome.latency_ms,
                state: outcome.state.as_str().to_string(),
                error: outcome.error.clone(),
            },
        );
        let _ = event_tx.send(AppEvent::SurfaceSummaryReady {
            surface: surface_owned,
            outcome,
        });
    });
}

fn handle_surface_click(
    state: &mut AppState,
    project_dir: &Path,
    config: &Config,
    surface: ClickableSurface,
) {
    // If the user explicitly prefers file-open over summary AND the surface is
    // a pipeline stage with a known fallback file, open that file instead.
    if let ClickableSurface::PipelineStage(ref stage_id) = surface {
        if config.prefer_file_open_over_summary {
            if let Some(path) = stage_fallback_file(stage_id, project_dir) {
                navigate_explorer_to_file(state, project_dir, &path);
                return;
            }
        }
    }
    let already_in_flight = state
        .surface_summary_overlay
        .as_ref()
        .is_some_and(|o| o.surface == surface && o.in_flight);
    if !already_in_flight {
        trigger_surface_summary(state, project_dir, config, surface, false);
    }
}

fn surface_summary_inputs(
    surface: &ClickableSurface,
    state: &AppState,
    project_dir: &std::path::Path,
) -> (Vec<std::path::PathBuf>, Option<String>) {
    match surface {
        ClickableSurface::PipelineStage(stage_id) => stage_summary_inputs(stage_id, project_dir),
        ClickableSurface::TaskQueue => (
            vec![ContractPaths::resolve(project_dir).tasks_path],
            None,
        ),
        ClickableSurface::Narrative => {
            let mut s = String::new();
            if let Some(brief) = state.last_commit_brief.as_ref() {
                s.push_str(&format!(
                    "Last commit: {} ({}, {})\n",
                    brief.subject, brief.short_sha, brief.relative_age
                ));
            } else {
                s.push_str("Last commit: none\n");
            }
            if let Some(task) = state.current_task.as_ref() {
                s.push_str(&format!(
                    "Current task: {} -- {}\n",
                    task.id,
                    task.short_desc(120)
                ));
            } else {
                s.push_str("Current task: none\n");
            }
            if let Some(stage) = state.current_agent_stage_id.as_deref() {
                s.push_str(&format!("Active stage: {}\n", stage));
            }
            if let Some(hint) = state.next_task_hint.as_ref() {
                s.push_str(&format!("Next task hint: {}\n", hint));
            }
            s.push_str(&format!("Events received: {}\n", state.events_received));
            let truncated = crate::utils::truncate_str(&s, 4096).to_string();
            (vec![], Some(truncated))
        }
        ClickableSurface::SkillCitations => {
            let mut s = String::new();
            if let Some(summary) = state.skill_citation_summary.as_ref() {
                s.push_str(&format!(
                    "DB reachable: {}\n",
                    if summary.db_available { "yes" } else { "no" }
                ));
                s.push_str(&format!(
                    "Session citations: {}\n",
                    summary.session_citations
                ));
                s.push_str(&format!(
                    "Session unique skills cited: {}\n",
                    summary.session_skills_cited
                ));
                s.push_str("Top skills:\n");
                for row in summary.top_skills.iter().take(8) {
                    s.push_str(&format!("- {}\n", row.skill_name));
                }
                if !state.session_skill_citations_set.is_empty() {
                    s.push_str("Cited this session:\n");
                    for name in state.session_skill_citations_set.iter().take(8) {
                        s.push_str(&format!("- {}\n", name));
                    }
                }
            } else {
                s.push_str("no skill citation data loaded");
            }
            let truncated = crate::utils::truncate_str(&s, 4096).to_string();
            (vec![], Some(truncated))
        }
        ClickableSurface::Stats => {
            let mut s = String::new();
            s.push_str(&format!(
                "Session cost: ${:.4}\n",
                state.session_cost_usd
            ));
            s.push_str(&format!("Input tokens: {}\n", state.session_input_tokens));
            s.push_str(&format!(
                "Output tokens: {}\n",
                state.session_output_tokens
            ));
            s.push_str(&format!(
                "Completed: {} / {} tasks\n",
                state.completed_count, state.total_count
            ));
            if let Some(report) = state.eval_report_cache.as_ref() {
                s.push_str(&format!("Eval cache present: {} stages\n", report.stages.len()));
            } else {
                s.push_str("Eval report: not yet written\n");
            }
            let truncated = crate::utils::truncate_str(&s, 4096).to_string();
            (vec![], Some(truncated))
        }
        ClickableSurface::AgentOutput => {
            let mut chrono: Vec<String> = state
                .agent_output
                .iter()
                .rev()
                .take(80)
                .cloned()
                .collect();
            chrono.reverse();
            let joined = chrono.join("\n");
            let truncated = crate::utils::truncate_str(&joined, 4096).to_string();
            (vec![], Some(truncated))
        }
        ClickableSurface::ExplorerFile(path) => (vec![path.clone()], None),
    }
}

/// Map a pipeline click to the artifact file path for that stage.
#[allow(dead_code)]
fn pipeline_click_artifact(
    click: tui::PipelineClick,
    project_dir: &std::path::Path,
    config: &Config,
) -> Option<std::path::PathBuf> {
    let buildloop = project_dir.join(".buildloop");
    let enabled_stages: Vec<&crate::config::PipelineStageConfig> = config
        .pipeline_stages
        .iter()
        .filter(|s| s.enabled)
        .collect();
    // Build the same connected ordering used by the renderer so click index
    // resolves correctly when virtual COACH and P+ stages are present.
    let mut connected_ids: Vec<String> = Vec::new();
    if config.run_mode == "coach" {
        connected_ids.push("coach".to_string());
    }
    for stage in enabled_stages.iter() {
        connected_ids.push(stage.id.clone());
        if stage.id == "plan" && config.plan_review_enabled {
            connected_ids.push("plan-review".to_string());
        }
    }
    match click {
        tui::PipelineClick::ConnectedStage(i) => {
            let stage_id = connected_ids.get(i).map(|s| s.as_str()).unwrap_or("");
            let file = match stage_id {
                "scout" => buildloop.join("scout-report.md"),
                "query" => buildloop.join("questions.md"),
                "research" => buildloop.join("research-report.md"),
                "plan" => buildloop.join("current-plan.md"),
                "implement" => buildloop.join("build-claims.md"),
                "doubt" => buildloop.join("review-report.md"),
                "coach" => buildloop.join("intake-brief.md"),
                "plan-review" => buildloop.join("plan-review-feedback.md"),
                _ => return None,
            };
            Some(file)
        }
        tui::PipelineClick::Discover => Some(ContractPaths::resolve(project_dir).tasks_path),
        tui::PipelineClick::Ship | tui::PipelineClick::Patterns => None,
    }
}

fn surface_has_fallback_file(overlay: Option<&SurfaceSummaryOverlay>) -> bool {
    let Some(o) = overlay else { return false };
    match &o.surface {
        ClickableSurface::PipelineStage(stage_id) => stage_id != "ship",
        ClickableSurface::TaskQueue => true,
        ClickableSurface::ExplorerFile(_) => true,
        ClickableSurface::Narrative
        | ClickableSurface::SkillCitations
        | ClickableSurface::Stats
        | ClickableSurface::AgentOutput => false,
    }
}

fn surface_open_file(
    state: &mut AppState,
    project_dir: &std::path::Path,
    config: &Config,
    overlay: &SurfaceSummaryOverlay,
) {
    let resolved: Option<std::path::PathBuf> = match &overlay.surface {
        ClickableSurface::PipelineStage(stage_id) => stage_fallback_file(stage_id, project_dir),
        ClickableSurface::TaskQueue => Some(ContractPaths::resolve(project_dir).tasks_path),
        ClickableSurface::ExplorerFile(path) => Some(path.clone()),
        _ => None,
    };
    match resolved {
        Some(path) if path.exists() => {
            state.surface_summary_overlay = None;
            handle_pipeline_click_target(
                state,
                project_dir,
                config,
                PipelineClickTarget::OpenFile(path),
            );
        }
        Some(path) => {
            if let Some(o) = state.surface_summary_overlay.as_mut() {
                o.last_error = Some(format!(
                    "No file to open: {} (not written yet)",
                    path.display()
                ));
            }
        }
        None => {
            if let Some(o) = state.surface_summary_overlay.as_mut() {
                o.last_error =
                    Some(format!("No fallback file defined for {}", overlay.stage_label));
            }
        }
    }
}

/// Open the running explorer and navigate directly to `target_path`.
/// Expands parent directories as needed and loads the file preview.
fn navigate_explorer_to_file(
    state: &mut AppState,
    project_dir: &std::path::Path,
    target_path: &std::path::Path,
) {
    if state.running_explorer.is_none() {
        let scenario = detect_startup_scenario(project_dir);
        let plan_status =
            classify_plan_status(&self::contract::ContractPaths::resolve(project_dir).tasks_path);
        state.running_explorer = Some(StartupState::new(project_dir, scenario, plan_status, None));
    }
    let Some(explorer) = state.running_explorer.as_mut() else {
        return;
    };

    // Expand all ancestor directories containing the target file.
    for entry in explorer.file_tree.iter_mut() {
        if entry.is_dir && target_path.starts_with(&entry.path) {
            entry.expanded = true;
        }
    }

    // Find the file in the (now-expanded) tree.
    let idx = explorer
        .file_tree
        .iter()
        .position(|e| e.path == target_path);
    if let Some(idx) = idx {
        explorer.explorer_selected = idx;
        let path = explorer.file_tree[idx].path.clone();
        explorer.file_preview_content = load_file_preview_for_running(&path);
        explorer.file_preview_scroll = 0;
        // Scroll the tree so the selection is visible.
        let vis = explorer.visible_indices();
        let vis_pos = vis.iter().position(|&i| i == idx).unwrap_or(0);
        explorer.explorer_scroll = vis_pos.saturating_sub(5);
    }

    state.show_running_explorer = true;
    state.focused_pane = state::TuiPane::Preview;
}

fn move_running_explorer_selection(state: &mut AppState, delta: isize) {
    let Some(explorer) = state.running_explorer.as_mut() else {
        return;
    };
    let vis = explorer.visible_indices();
    if vis.is_empty() {
        return;
    }
    let cur_pos = vis
        .iter()
        .position(|&i| i == explorer.explorer_selected)
        .unwrap_or(0);
    let max_pos = vis.len() - 1;
    let new_pos = (cur_pos as isize + delta).clamp(0, max_pos as isize) as usize;
    let new_index = vis[new_pos];
    if new_index == explorer.explorer_selected {
        return;
    }
    explorer.explorer_selected = new_index;
    let visible_estimate: usize = 20;
    if new_pos < explorer.explorer_scroll {
        explorer.explorer_scroll = new_pos;
    } else if new_pos >= explorer.explorer_scroll + visible_estimate {
        explorer.explorer_scroll = new_pos.saturating_sub(visible_estimate) + 1;
    }
    // Load preview for new selection
    let entry = &explorer.file_tree[new_index];
    explorer.file_preview_content = if entry.is_dir {
        vec!["<directory>".to_string()]
    } else {
        load_file_preview_for_running(&entry.path)
    };
    explorer.file_preview_scroll = 0;
}

fn handle_running_explorer_enter(state: &mut AppState) {
    let Some(explorer) = state.running_explorer.as_mut() else {
        return;
    };
    let selected = explorer.explorer_selected;
    if selected >= explorer.file_tree.len() {
        return;
    }
    if explorer.file_tree[selected].is_dir {
        explorer.file_tree[selected].expanded = !explorer.file_tree[selected].expanded;
        if !explorer.file_tree[selected].expanded {
            let vis = explorer.visible_indices();
            if !vis.contains(&explorer.explorer_selected) {
                explorer.explorer_selected = selected;
            }
        }
    } else {
        let file_path = explorer.file_tree[selected].path.clone();
        state.pending_transition = Some(state::PendingTransition::OpenExternalEditor { file_path });
    }
}

fn load_file_preview_for_running(path: &std::path::Path) -> Vec<String> {
    if path.is_dir() {
        return vec!["<directory>".to_string()];
    }
    match std::fs::read_to_string(path) {
        Ok(content) => content.lines().take(500).map(|l| l.to_string()).collect(),
        Err(_) => vec!["<binary or unreadable file>".to_string()],
    }
}

fn handle_startup_mouse_at_for_running(
    state: &mut AppState,
    mouse: crossterm::event::MouseEvent,
    terminal_size: (u16, u16),
    config: &Config,
) {
    use crossterm::event::{MouseButton, MouseEventKind};
    if state.confirm_quit && matches!(mouse.kind, MouseEventKind::Down(MouseButton::Left)) {
        let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
        if let Some(action) = tui::quit_confirm_hit_test(area, mouse.column, mouse.row) {
            match action {
                tui::QuitConfirmAction::Quit => state.should_quit = true,
                tui::QuitConfirmAction::Cancel => state.confirm_quit = false,
            }
        }
        return;
    }
    if handle_settings_overlay_mouse(state, mouse, terminal_size) {
        return;
    }
    // Running explorer uses the same 36/64 split for the middle section
    let area = ratatui::layout::Rect::new(0, 0, terminal_size.0, terminal_size.1);
    let chunks = ratatui::layout::Layout::default()
        .direction(ratatui::layout::Direction::Vertical)
        .constraints([
            ratatui::layout::Constraint::Length(5),
            ratatui::layout::Constraint::Length(9),
            ratatui::layout::Constraint::Min(10),
            ratatui::layout::Constraint::Length(6),
            ratatui::layout::Constraint::Length(1),
        ])
        .split(area);
    let middle_cols = ratatui::layout::Layout::default()
        .direction(ratatui::layout::Direction::Horizontal)
        .constraints([
            ratatui::layout::Constraint::Percentage(36),
            ratatui::layout::Constraint::Percentage(64),
        ])
        .split(chunks[2]);
    let explorer_area = middle_cols[0];
    let preview_area = middle_cols[1];

    match mouse.kind {
        MouseEventKind::Down(MouseButton::Right) => {
            // Right-click opens an AI-summary context menu on a file entry.
            if tui::rect_contains(explorer_area, mouse.column, mouse.row) {
                if let Some(ref explorer) = state.running_explorer {
                    let inner_top = explorer_area.y + 1;
                    let inner_bottom = explorer_area.y + explorer_area.height.saturating_sub(1);
                    if mouse.row >= inner_top && mouse.row < inner_bottom {
                        let relative_row = (mouse.row - inner_top) as usize;
                        let vis = explorer.visible_indices();
                        let vis_index = explorer.explorer_scroll + relative_row;
                        if let Some(&tree_idx) = vis.get(vis_index) {
                            if let Some(entry) = explorer.file_tree.get(tree_idx) {
                                if !entry.is_dir {
                                    state.explorer_context_menu = Some(ExplorerContextMenu {
                                        anchor_col: mouse.column,
                                        anchor_row: mouse.row,
                                        file_path: entry.path.clone(),
                                    });
                                }
                            }
                        }
                    }
                }
            }
            return;
        }
        MouseEventKind::Down(MouseButton::Left) => {
            // If a context menu is open, the click either fires the AI-summary
            // action (when on the label row) or dismisses the menu.
            if let Some(menu) = state.explorer_context_menu.clone() {
                if let Some(hit) = tui::context_menu_hit_test(&menu, mouse.column, mouse.row) {
                    state.explorer_context_menu = None;
                    if hit == tui::ContextMenuHit::AiSummary {
                        let project_dir = state
                            .buildloop_dir
                            .parent()
                            .unwrap_or(std::path::Path::new("."))
                            .to_path_buf();
                        handle_surface_click(
                            state,
                            &project_dir,
                            config,
                            ClickableSurface::ExplorerFile(menu.file_path),
                        );
                    }
                    return;
                }
                // Click outside the menu: dismiss and continue normal handling.
                state.explorer_context_menu = None;
            }
            // Check toggle buttons first (border row)
            if let Some(ref explorer) = state.running_explorer {
                if let Some(tui::StartupMouseTarget::ExpandAllToggle) =
                    tui::explorer_toggle_hit_test(
                        explorer_area,
                        mouse.column,
                        mouse.row,
                        &explorer.file_tree,
                    )
                {
                    state.focused_pane = state::TuiPane::Explorer;
                    if let Some(ref mut ex) = state.running_explorer {
                        startup::toggle_expand_all(ex);
                    }
                    return;
                }
                if let Some(tui::StartupMouseTarget::WrapToggle) = tui::preview_toggle_hit_test(
                    preview_area,
                    mouse.column,
                    mouse.row,
                    explorer.preview_wrap,
                ) {
                    state.focused_pane = state::TuiPane::Preview;
                    let project_dir = state
                        .buildloop_dir
                        .parent()
                        .unwrap_or(std::path::Path::new("."));
                    if let Some(ref mut ex) = state.running_explorer {
                        startup::toggle_preview_wrap(ex, project_dir);
                    }
                    return;
                }
            }

            // Status bar click (bottom row) -- Stop/Startup button
            let status_bar = chunks[4];
            if mouse.row == status_bar.y {
                let stop_label = if state.dual_arena_ready() {
                    " Startup "
                } else {
                    " Stop "
                };
                let stop_w = stop_label.chars().count() as u16 + " Esc ".chars().count() as u16;
                if mouse.column >= status_bar.x && mouse.column < status_bar.x + stop_w {
                    if state.dual_arena_ready() {
                        let project_dir = state
                            .buildloop_dir
                            .parent()
                            .unwrap_or(std::path::Path::new("."))
                            .to_path_buf();
                        enter_home_surface(
                            &project_dir,
                            state,
                            Some("Arena results preserved in .buildloop/arena/".to_string()),
                        );
                    } else if state.stop_after_task {
                        state.stop_after_task = false;
                        state.remove_stop_file();
                        state.log("Stop cancelled -- resuming build");
                    } else {
                        state.stop_after_task = true;
                        state.write_stop_file();
                        state.log("Stopping after current task (click again to cancel)");
                    }
                    return;
                }
            }

            if tui::rect_contains(explorer_area, mouse.column, mouse.row) {
                state.focused_pane = state::TuiPane::Explorer;
                // Hit-test to select file entry
                let inner_top = explorer_area.y + 1;
                let inner_bottom = explorer_area.y + explorer_area.height.saturating_sub(1);
                if mouse.row >= inner_top && mouse.row < inner_bottom {
                    if let Some(ref mut explorer) = state.running_explorer {
                        let relative_row = (mouse.row - inner_top) as usize;
                        let vis = explorer.visible_indices();
                        let vis_index = explorer.explorer_scroll + relative_row;
                        if vis_index < vis.len() {
                            let tree_idx = vis[vis_index];
                            explorer.explorer_selected = tree_idx;
                            let vis_pos = vis.iter().position(|&i| i == tree_idx).unwrap_or(0);
                            let visible_estimate: usize = 20;
                            if vis_pos < explorer.explorer_scroll {
                                explorer.explorer_scroll = vis_pos;
                            } else if vis_pos >= explorer.explorer_scroll + visible_estimate {
                                explorer.explorer_scroll =
                                    vis_pos.saturating_sub(visible_estimate) + 1;
                            }
                            // Toggle folder expanded/collapsed on click
                            if explorer.file_tree[tree_idx].is_dir {
                                explorer.file_tree[tree_idx].expanded =
                                    !explorer.file_tree[tree_idx].expanded;
                                explorer.file_preview_content = vec!["<directory>".to_string()];
                            } else {
                                explorer.file_preview_content = load_file_preview_for_running(
                                    &explorer.file_tree[tree_idx].path,
                                );
                            }
                            explorer.file_preview_scroll = 0;
                        }
                    }
                }
            } else if tui::rect_contains(preview_area, mouse.column, mouse.row) {
                state.focused_pane = state::TuiPane::Preview;
            }
        }
        MouseEventKind::ScrollUp => match state.focused_pane {
            state::TuiPane::Preview => {
                if let Some(ref mut explorer) = state.running_explorer {
                    explorer.file_preview_scroll = explorer.file_preview_scroll.saturating_sub(3);
                }
            }
            _ => {
                move_running_explorer_selection(state, -3);
            }
        },
        MouseEventKind::ScrollDown => match state.focused_pane {
            state::TuiPane::Preview => {
                if let Some(ref mut explorer) = state.running_explorer {
                    let max_scroll = explorer.file_preview_content.len().saturating_sub(1);
                    explorer.file_preview_scroll =
                        (explorer.file_preview_scroll + 3).min(max_scroll);
                }
            }
            _ => {
                move_running_explorer_selection(state, 3);
            }
        },
        _ => {}
    }
}

#[cfg(test)]
mod tests;

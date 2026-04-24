use anyhow::{Context as _, Result};
use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use serde_json::Value;
use std::io::BufRead;
use std::path::Path;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, Instant};

use crate::config::Config;
use crate::prompts::agent_system_directives;
use crate::tmux::TmuxSession;
use crate::utils::truncate_str;
use tokio::sync::mpsc;

#[derive(Debug, Clone, PartialEq)]
pub enum AgentRole {
    Scout,
    Query,
    Research,
    Planner,
    Builder,
    Reviewer,
    Fixer,
    PlanReview,
    Discovery,
}

impl std::fmt::Display for AgentRole {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            AgentRole::Scout => write!(f, "SCOUT"),
            AgentRole::Query => write!(f, "QUERY"),
            AgentRole::Research => write!(f, "RESEARCH"),
            AgentRole::Planner => write!(f, "PLAN"),
            AgentRole::Builder => write!(f, "IMPLEMENT"),
            AgentRole::Reviewer => write!(f, "VERIFY"),
            AgentRole::Fixer => write!(f, "VERIFY"),
            AgentRole::PlanReview => write!(f, "P+"),
            AgentRole::Discovery => write!(f, "DISCOVERY"),
        }
    }
}

/// Centralized source of truth for which tools each agent role may use.
/// This is tool-surface reduction, not a hard filesystem security boundary --
/// any role with Bash access is still trusted code.
pub fn allowed_tools_for_role(role: &AgentRole) -> &'static [&'static str] {
    match role {
        AgentRole::Scout => &["Read", "Glob", "Grep", "Bash", "WebFetch", "WebSearch"],
        AgentRole::Query => &["Write"],
        AgentRole::Research => &[
            "Read",
            "Glob",
            "Grep",
            "Bash",
            "Write",
            "WebFetch",
            "WebSearch",
        ],
        AgentRole::Planner => &["Read", "Glob", "Grep", "Edit", "Write"],
        AgentRole::PlanReview => &["Read", "Glob", "Grep", "Edit", "Write"],
        AgentRole::Builder => &[
            "Bash",
            "Edit",
            "Write",
            "Read",
            "Glob",
            "Grep",
            "NotebookEdit",
            "WebFetch",
            "WebSearch",
        ],
        AgentRole::Reviewer => &["Read", "Glob", "Grep", "Bash", "Edit", "Write"],
        AgentRole::Fixer => &["Read", "Glob", "Grep", "Bash", "Edit", "Write"],
        AgentRole::Discovery => &["Read", "Glob", "Grep", "Bash", "Edit", "Write"],
    }
}

/// Parsed events from claude's stream-json output.
#[derive(Debug, Clone)]
pub enum AgentOutputEvent {
    /// Assistant is generating text
    Text(String),
    /// Agent is calling a tool
    ToolUse { tool: String, input_preview: String },
    /// Tool returned a result
    ToolResult { output_preview: String },
    /// Raw stderr line
    Stderr(String),
    /// Final result text
    Result(String),
    /// Token usage and cost from result event
    Usage {
        cost_usd: f64,
        input_tokens: u64,
        output_tokens: u64,
        context_window: u64,
        cache_creation_tokens: u64,
        cache_read_tokens: u64,
    },
}

pub struct AgentResult {
    pub success: bool,
    #[allow(dead_code)]
    pub exit_code: i32,
    pub exit_kind: AgentExitKind,
    pub failure_message: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentExitKind {
    Completed,
    Failed,
    Cancelled,
    TimedOut,
    TransportStall,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentBackend {
    Pty,
    Tmux,
}

impl AgentResult {
    pub fn should_retry(&self) -> bool {
        matches!(self.exit_kind, AgentExitKind::TransportStall)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModelProvider {
    Claude,
    Codex,
    OpenCode,
}

impl ModelProvider {
    pub fn slug(self) -> &'static str {
        match self {
            ModelProvider::Claude => "claude",
            ModelProvider::Codex => "codex",
            ModelProvider::OpenCode => "opencode",
        }
    }

    /// Resolve the node CLI entry-point for this provider on Windows.
    /// Returns `Some(path)` if found, `None` otherwise.
    ///
    /// Tries two strategies:
    /// 1. `where claude.cmd` -> sibling `node_modules/` (standard npm global)
    /// 2. `npm root -g` -> global modules root (works with Volta, pnpm, fnm, nvm-windows)
    #[cfg(target_os = "windows")]
    fn resolve_node_cli(self) -> Option<std::path::PathBuf> {
        let (cmd_name, module) = match self {
            ModelProvider::Claude => ("claude.cmd", "@anthropic-ai/claude-code/cli.js"),
            ModelProvider::Codex => ("codex.cmd", "@anthropic-ai/codex/cli.js"),
            // OpenCode is not distributed via npm, so it doesn't have a node
            // cli.js. The caller falls back to plain PATH resolution.
            ModelProvider::OpenCode => return None,
        };

        // Strategy 1: find .cmd via `where`, look for sibling node_modules
        if let Ok(output) = std::process::Command::new("where").arg(cmd_name).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                if let Some(first_line) = stdout.lines().next() {
                    let cmd_path = std::path::PathBuf::from(first_line.trim());
                    if let Some(dir) = cmd_path.parent() {
                        let cli_js = dir.join("node_modules").join(module);
                        if cli_js.exists() {
                            return Some(cli_js);
                        }
                    }
                }
            }
        }

        // Strategy 2: ask npm for the global modules root (handles Volta, pnpm, fnm)
        if let Ok(output) = std::process::Command::new("npm")
            .args(["root", "-g"])
            .output()
        {
            if output.status.success() {
                let root = String::from_utf8_lossy(&output.stdout);
                let cli_js = std::path::PathBuf::from(root.trim()).join(module);
                if cli_js.exists() {
                    return Some(cli_js);
                }
            }
        }

        None
    }

    /// Builds a `CommandBuilder` for this provider (for PTY execution).
    /// On Windows, invokes `node <cli.js>` directly to avoid portable_pty's
    /// broken quoting of paths-with-spaces and cmd.exe arg mangling.
    pub fn command_builder(self) -> CommandBuilder {
        #[cfg(target_os = "windows")]
        {
            if let Some(cli_js) = self.resolve_node_cli() {
                let mut cmd = CommandBuilder::new("node");
                cmd.arg(cli_js.to_string_lossy().to_string());
                return cmd;
            }
            // Last resort: invoke via cmd.exe /c so .cmd wrappers are handled.
            // portable_pty's CreateProcessW can't execute .cmd files directly.
            eprintln!(
                "[foundry] warning: could not resolve {} cli.js; using cmd.exe /c fallback",
                self.slug()
            );
            let mut cmd = CommandBuilder::new("cmd");
            cmd.arg("/c");
            cmd.arg(self.slug());
            return cmd;
        }
        #[cfg(not(target_os = "windows"))]
        CommandBuilder::new(self.slug())
    }
}

/// Returns `true` when the process is running as root/sudo on Unix.
/// `--dangerously-skip-permissions` is blocked by the Claude CLI in this case,
/// so we fall back to `--allowedTools` with an explicit tool list.
pub fn is_running_as_root() -> bool {
    #[cfg(unix)]
    {
        // nix::unistd::getuid() would work too, but checking /proc avoids extra deps.
        std::env::var("USER").map(|u| u == "root").unwrap_or(false)
            || std::path::Path::new("/proc/self/status").exists()
                && std::fs::read_to_string("/proc/self/status")
                    .map(|s| s.contains("Uid:\t0\t"))
                    .unwrap_or(false)
    }
    #[cfg(not(unix))]
    {
        false
    }
}

/// Detect the installed Claude CLI version by running `claude --version`.
/// Returns a version string like "1.0.20" or "unknown" on failure.
pub fn detect_cc_version() -> String {
    let output = match std::process::Command::new("claude")
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
    let version = if let Some(rest) = trimmed.strip_prefix("claude-code ") {
        rest.trim()
    } else {
        trimmed
    };
    if version.is_empty() {
        "unknown".to_string()
    } else {
        version.to_string()
    }
}

/// The default tool allowlist used as a fallback when `--dangerously-skip-permissions`
/// is unavailable (e.g. running as root). Covers every tool an agent might need.
pub const ROOT_ALLOWED_TOOLS: &str =
    "Bash,Edit,Write,Read,Glob,Grep,NotebookEdit,WebFetch,WebSearch,TodoWrite";

/// Append permission flags to a PTY `CommandBuilder`.
/// Prefers `--dangerously-skip-permissions`; falls back to `--allowedTools` when root.
fn append_permission_flags_pty(cmd: &mut CommandBuilder) {
    if is_running_as_root() {
        cmd.arg("--allowedTools");
        cmd.arg(ROOT_ALLOWED_TOOLS);
    } else {
        cmd.arg("--dangerously-skip-permissions");
    }
}

/// Append permission flags to a `Vec<String>` arg list (for sandbox wrapping).
fn append_permission_flags_args(args: &mut Vec<String>) {
    if is_running_as_root() {
        args.push("--allowedTools".to_string());
        args.push(ROOT_ALLOWED_TOOLS.to_string());
    } else {
        args.push("--dangerously-skip-permissions".to_string());
    }
}

impl std::fmt::Display for ModelProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ModelProvider::Claude => write!(f, "Claude"),
            ModelProvider::Codex => write!(f, "Codex"),
            ModelProvider::OpenCode => write!(f, "OpenCode"),
        }
    }
}

pub struct ProviderRunOptions<'a> {
    pub provider: ModelProvider,
    pub model: &'a str,
    pub prompt: &'a str,
    pub project_dir: &'a Path,
    pub output_tx: mpsc::UnboundedSender<AgentOutputEvent>,
    pub log_dir: &'a Path,
    pub timeout_secs: u64,
    pub skip_git_repo_check: bool,
    pub cancel_flag: Option<Arc<AtomicBool>>,
    pub config_override: Option<&'a Config>,
}

const PROVIDER_POLL_INTERVAL: Duration = Duration::from_millis(500);
const PROVIDER_HARD_TIMEOUT_MULTIPLIER: u64 = 4;
const CODEX_STALL_GRACE_SECS: u64 = 90;
const CODEX_FAST_STALL_SECS: u64 = 45;
const RUN_AGENT_CODEX_MAX_ATTEMPTS: usize = 2;

#[derive(Debug)]
struct ProviderProgressState {
    last_progress_at: Instant,
    /// Timestamp of last raw bytes received from PTY — secondary progress signal.
    /// When parsed events fail (e.g. unparseable JSON), raw bytes still indicate
    /// the agent is alive and working.
    last_raw_bytes_at: Instant,
    /// Timestamp of last successfully parsed JSON event (via note_provider_event).
    /// NOT updated by note_provider_stderr_line (unparseable lines).
    last_parsed_event_at: Instant,
    last_transport_issue_at: Option<Instant>,
    transport_issue_count: usize,
}

impl ProviderProgressState {
    fn new(now: Instant) -> Self {
        Self {
            last_progress_at: now,
            last_raw_bytes_at: now,
            last_parsed_event_at: now,
            last_transport_issue_at: None,
            transport_issue_count: 0,
        }
    }

    fn record_progress_at(&mut self, now: Instant) {
        self.last_progress_at = now;
        self.last_raw_bytes_at = now;
        self.last_transport_issue_at = None;
        self.transport_issue_count = 0;
    }

    /// Record that a successfully parsed JSON event was received.
    /// Only called from note_provider_event(), NOT from note_provider_stderr_line().
    fn record_parsed_event_at(&mut self, now: Instant) {
        self.last_parsed_event_at = now;
    }

    /// Record that raw bytes were received from PTY, even if they didn't parse.
    fn record_raw_bytes_at(&mut self, now: Instant) {
        self.last_raw_bytes_at = now;
    }

    fn record_transport_issue_at(&mut self, now: Instant) {
        self.last_transport_issue_at = Some(now);
        self.transport_issue_count += 1;
    }

    fn no_progress_for(&self, now: Instant) -> Duration {
        now.saturating_duration_since(self.last_progress_at)
    }

    /// Returns true when the agent should be considered idle.
    ///
    /// Two triggers:
    /// 1. Original: all output has stopped (parsed events, stderr, raw bytes).
    /// 2. Tertiary: raw bytes/stderr still flowing but no successfully parsed JSON
    ///    events for > timeout. The agent is alive but output is unusable (e.g.,
    ///    non-JSON debug info, ConPTY mangling every line).
    fn is_truly_idle(&self, now: Instant, timeout: Duration) -> bool {
        let no_progress = self.no_progress_for(now) >= timeout;
        let no_raw = now.saturating_duration_since(self.last_raw_bytes_at) >= timeout;

        // Original: all output has stopped
        if no_progress && no_raw {
            return true;
        }

        // Tertiary: raw bytes or stderr still flowing, but no successfully parsed
        // JSON events for > timeout.
        let no_parsed_events = now.saturating_duration_since(self.last_parsed_event_at) >= timeout;
        if no_parsed_events && !no_raw {
            return true;
        }

        false
    }

    fn transport_stalled(&self, now: Instant) -> bool {
        let Some(last_issue_at) = self.last_transport_issue_at else {
            return false;
        };

        if last_issue_at <= self.last_progress_at {
            return false;
        }

        let since_progress = self.no_progress_for(now);
        since_progress >= Duration::from_secs(CODEX_STALL_GRACE_SECS)
            || (self.transport_issue_count >= 2
                && since_progress >= Duration::from_secs(CODEX_FAST_STALL_SECS))
    }
}

fn is_codex_transport_issue(text: &str) -> bool {
    let lower = text.to_ascii_lowercase();
    lower.contains("stream disconnected before completion")
        || lower.contains("idle timeout waiting for websocket")
        || lower.contains("reconnecting...")
        || ((lower.contains("websocket") || lower.contains("stream"))
            && (lower.contains("disconnect")
                || lower.contains("timeout")
                || lower.contains("reconnect")))
}

fn note_provider_event(
    provider: ModelProvider,
    event: &AgentOutputEvent,
    progress: &Arc<Mutex<ProviderProgressState>>,
) {
    let mut guard = progress
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    let now = Instant::now();
    match event {
        AgentOutputEvent::Stderr(text)
            if provider == ModelProvider::Codex && is_codex_transport_issue(text) =>
        {
            guard.record_transport_issue_at(now);
        }
        _ => {
            guard.record_progress_at(now);
            guard.record_parsed_event_at(now);
        }
    }
}

fn note_provider_stderr_line(
    provider: ModelProvider,
    line: &str,
    progress: &Arc<Mutex<ProviderProgressState>>,
) {
    let mut guard = progress
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    let now = Instant::now();
    if provider == ModelProvider::Codex && is_codex_transport_issue(line) {
        guard.record_transport_issue_at(now);
    } else {
        guard.record_progress_at(now);
    }
}

fn should_retry_run_agent_attempt(
    provider: ModelProvider,
    outcome: &AgentResult,
    attempt: usize,
    max_attempts: usize,
) -> bool {
    provider == ModelProvider::Codex && attempt < max_attempts && outcome.should_retry()
}

/// Check whether a failed Codex outcome looks like a rate/quota limit,
/// meaning we should fall back to Claude instead of returning the failure.
///
/// Checks the failure_message for rate-limit keywords, and also treats
/// TransportStall and Failed exit kinds (after retries are exhausted) as
/// potential infrastructure issues worth falling back from.
fn should_fallback_to_claude(outcome: &AgentResult) -> bool {
    if outcome.success {
        return false;
    }

    // Check failure message for rate-limit / quota keywords
    if let Some(ref msg) = outcome.failure_message {
        let lower = msg.to_ascii_lowercase();
        if lower.contains("rate")
            || lower.contains("limit")
            || lower.contains("quota")
            || lower.contains("subscription")
            || lower.contains("429")
            || lower.contains("too many requests")
        {
            return true;
        }
    }

    // TransportStall after retries exhausted is likely an infrastructure issue
    matches!(
        outcome.exit_kind,
        AgentExitKind::TransportStall | AgentExitKind::Failed
    )
}

pub async fn run_provider_session(options: ProviderRunOptions<'_>) -> Result<AgentResult> {
    let timestamp = chrono::Utc::now().format("%Y%m%d-%H%M%S");
    let log_file_path = options.log_dir.join(format!(
        "studio-{}-{}.jsonl",
        options.provider.slug(),
        timestamp
    ));
    let final_message_path = options.log_dir.join(format!(
        "studio-{}-{}-last.txt",
        options.provider.slug(),
        timestamp
    ));
    std::fs::create_dir_all(options.log_dir)?;

    let mut cmd = match options.provider {
        ModelProvider::Claude => {
            let mut cmd = ModelProvider::Claude.command_builder();
            cmd.arg("-p");
            cmd.arg(options.prompt);
            if !options.model.trim().is_empty() {
                cmd.arg("--model");
                cmd.arg(options.model);
            }
            append_permission_flags_pty(&mut cmd);
            cmd.arg("--output-format");
            cmd.arg("stream-json");
            cmd.arg("--verbose");
            cmd.env("CLAUDECODE", "");
            cmd.arg("--append-system-prompt");
            cmd.arg(agent_system_directives());
            cmd
        }
        ModelProvider::Codex => {
            let mut cmd = ModelProvider::Codex.command_builder();
            cmd.arg("exec");
            cmd.arg("--json");
            if !options.model.trim().is_empty() {
                cmd.arg("--model");
                cmd.arg(options.model);
            }
            cmd.arg("--full-auto");
            cmd.arg("--output-last-message");
            cmd.arg(final_message_path.to_string_lossy().to_string());
            if options.skip_git_repo_check {
                cmd.arg("--skip-git-repo-check");
            }
            cmd.arg(format!(
                "{}\n\n{}",
                agent_system_directives(),
                options.prompt
            ));
            cmd
        }
        ModelProvider::OpenCode => {
            let mut cmd = ModelProvider::OpenCode.command_builder();
            cmd.arg("run");
            if !options.model.trim().is_empty() {
                cmd.arg("--model");
                cmd.arg(options.model);
            }
            cmd.arg("--format");
            cmd.arg("json");
            cmd.arg("--dangerously-skip-permissions");
            cmd.arg(format!(
                "{}\n\n{}",
                agent_system_directives(),
                options.prompt
            ));
            cmd
        }
    };

    cmd.cwd(options.project_dir);

    // Sandbox wrapping for provider sessions
    let config = match options.config_override {
        Some(c) => c.clone(),
        None => Config::load(options.project_dir),
    };
    let sandbox_cfg = config.sandbox_config();
    let cmd = if sandbox_cfg.is_active() {
        let (program, args, env_vars): (&str, Vec<String>, Vec<(&str, &str)>) =
            match options.provider {
                ModelProvider::Claude => {
                    let program = "claude";
                    let mut args = vec!["-p".to_string(), options.prompt.to_string()];
                    if !options.model.trim().is_empty() {
                        args.push("--model".to_string());
                        args.push(options.model.to_string());
                    }
                    append_permission_flags_args(&mut args);
                    args.push("--output-format".to_string());
                    args.push("stream-json".to_string());
                    args.push("--verbose".to_string());
                    args.push("--append-system-prompt".to_string());
                    args.push(agent_system_directives());
                    (program, args, vec![("CLAUDECODE", "")])
                }
                ModelProvider::Codex => {
                    let program = "codex";
                    let mut args = vec!["exec".to_string(), "--json".to_string()];
                    if !options.model.trim().is_empty() {
                        args.push("--model".to_string());
                        args.push(options.model.to_string());
                    }
                    args.push("--full-auto".to_string());
                    args.push("--output-last-message".to_string());
                    args.push(format!(
                        "/work/{}",
                        final_message_path
                            .strip_prefix(options.project_dir)
                            .unwrap_or(&final_message_path)
                            .display()
                    ));
                    if options.skip_git_repo_check {
                        args.push("--skip-git-repo-check".to_string());
                    }
                    args.push(format!(
                        "{}\n\n{}",
                        agent_system_directives(),
                        options.prompt
                    ));
                    (program, args, vec![])
                }
                ModelProvider::OpenCode => {
                    let program = "opencode";
                    let mut args = vec!["run".to_string()];
                    if !options.model.trim().is_empty() {
                        args.push("--model".to_string());
                        args.push(options.model.to_string());
                    }
                    args.push("--format".to_string());
                    args.push("json".to_string());
                    args.push("--dangerously-skip-permissions".to_string());
                    args.push(format!(
                        "{}\n\n{}",
                        agent_system_directives(),
                        options.prompt
                    ));
                    (program, args, vec![])
                }
            };
        sandbox_cfg.wrap_command_builder(program, &args, options.project_dir, &env_vars)
    } else {
        cmd
    };

    let pty_system = native_pty_system();
    let pair = pty_system.openpty(PtySize {
        rows: 24,
        cols: 4096, // wide enough to avoid wrapping JSON lines; must fit i16 for ConPTY
        pixel_width: 0,
        pixel_height: 0,
    })?;

    let child = pair.slave.spawn_command(cmd)?;
    drop(pair.slave);

    let reader = pair.master.try_clone_reader()?;
    let master = pair.master;
    let (result_tx, result_rx) = tokio::sync::oneshot::channel();
    let provider = options.provider;
    let model_name = options.model.to_string();
    let timeout_secs = options.timeout_secs;
    let output_tx = options.output_tx;
    let cancel_flag = options.cancel_flag.clone();
    let progress = Arc::new(Mutex::new(ProviderProgressState::new(Instant::now())));

    tokio::task::spawn_blocking(move || {
        let tx = output_tx;
        let mut child = child;
        let log_path = log_file_path.clone();
        let model_label = model_name.clone();
        let final_output_path = final_message_path.clone();
        let read_tx = tx.clone();
        let read_progress = progress.clone();

        let read_thread = std::thread::spawn(move || {
            read_provider_output(
                reader,
                &read_tx,
                &log_path,
                provider,
                &model_label,
                &read_progress,
            );
        });

        let hard_timeout_secs = timeout_secs.saturating_mul(PROVIDER_HARD_TIMEOUT_MULTIPLIER);
        let hard_deadline = Instant::now() + Duration::from_secs(hard_timeout_secs);
        let mut result = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::Failed,
            failure_message: None,
        };

        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    result.success = status.success();
                    result.exit_code = if status.success() { 0 } else { 1 };
                    result.exit_kind = if status.success() {
                        AgentExitKind::Completed
                    } else {
                        AgentExitKind::Failed
                    };
                    if !status.success() {
                        result.failure_message =
                            Some(format!("{} exited unsuccessfully", provider));
                    }
                    break;
                }
                Ok(None) => {
                    if cancel_flag
                        .as_ref()
                        .is_some_and(|flag| flag.load(Ordering::Acquire))
                    {
                        let _ = child.kill();
                        let _ = child.wait();
                        let message = format!("{} cancelled by studio", provider);
                        let _ = tx.send(AgentOutputEvent::Stderr(message.clone()));
                        result.exit_kind = AgentExitKind::Cancelled;
                        result.failure_message = Some(message);
                        break;
                    }

                    let now = Instant::now();
                    let progress_snapshot = progress
                        .lock()
                        .unwrap_or_else(|poisoned| poisoned.into_inner());

                    if provider == ModelProvider::Codex && progress_snapshot.transport_stalled(now)
                    {
                        let _ = child.kill();
                        let _ = child.wait();
                        let message = format!(
                            "{} stalled after websocket reconnects; aborting this attempt",
                            provider
                        );
                        let _ = tx.send(AgentOutputEvent::Stderr(message.clone()));
                        result.exit_kind = AgentExitKind::TransportStall;
                        result.failure_message = Some(message);
                        break;
                    }

                    if progress_snapshot.is_truly_idle(now, Duration::from_secs(timeout_secs)) {
                        let _ = child.kill();
                        let _ = child.wait();
                        let message = format!(
                            "{} timed out after {}s without progress",
                            provider, timeout_secs
                        );
                        let _ = tx.send(AgentOutputEvent::Stderr(message.clone()));
                        result.exit_kind = AgentExitKind::TimedOut;
                        result.failure_message = Some(message);
                        break;
                    }

                    if now >= hard_deadline {
                        let _ = child.kill();
                        let _ = child.wait();
                        let message = format!(
                            "{} timed out after {}s total runtime",
                            provider, hard_timeout_secs
                        );
                        let _ = tx.send(AgentOutputEvent::Stderr(message.clone()));
                        result.exit_kind = AgentExitKind::TimedOut;
                        result.failure_message = Some(message);
                        break;
                    }
                    drop(progress_snapshot);
                    std::thread::sleep(PROVIDER_POLL_INTERVAL);
                }
                Err(err) => {
                    let message = format!("{} failed while waiting on process: {}", provider, err);
                    let _ = tx.send(AgentOutputEvent::Stderr(message.clone()));
                    result.exit_kind = AgentExitKind::Failed;
                    result.failure_message = Some(message);
                    break;
                }
            }
        }

        drop(master);
        let _ = read_thread.join();

        if provider == ModelProvider::Codex
            && matches!(
                result.exit_kind,
                AgentExitKind::Completed | AgentExitKind::Failed
            )
        {
            if let Ok(text) = std::fs::read_to_string(&final_output_path) {
                if !text.trim().is_empty() {
                    let _ = tx.send(AgentOutputEvent::Result(text));
                }
            }
        }

        let _ = result_tx.send(result);
    });

    Ok(result_rx.await.unwrap_or(AgentResult {
        success: false,
        exit_code: 1,
        exit_kind: AgentExitKind::Failed,
        failure_message: Some("provider session result channel closed".to_string()),
    }))
}

/// Spawn a claude CLI agent inside a PTY.
///
/// Node.js block-buffers stdout when it detects a pipe or file (16KB chunks).
/// By spawning inside a PTY, Node.js sees a terminal and uses line-buffered
/// (synchronous) writes — each JSON event flushes immediately, giving us
/// true real-time streaming in the TUI.
#[allow(clippy::too_many_arguments)]
pub async fn run_agent(
    role: &AgentRole,
    provider: ModelProvider,
    model: &str,
    prompt: &str,
    project_dir: &Path,
    output_tx: mpsc::UnboundedSender<AgentOutputEvent>,
    log_dir: &Path,
    allowed_tools: Option<&[&str]>,
    timeout_secs: u64,
    shutdown: Option<Arc<AtomicBool>>,
    config_override: Option<&Config>,
) -> Result<AgentResult> {
    let role_tools = allowed_tools_for_role(role);
    let effective_tools: &[&str] = allowed_tools.unwrap_or(role_tools);

    let config = match config_override {
        Some(c) => c.clone(),
        None => Config::load(project_dir),
    };

    // For Codex, delegate to run_provider_session which has full
    // Codex support (JSON output parsing, stall detection), plus
    // a single automatic retry on transport stalls in the build loop.
    if provider == ModelProvider::Codex {
        if config.enforce_phase_rbac {
            let _ = output_tx.send(AgentOutputEvent::Stderr(
                "[foundry] enforce_phase_rbac: Codex provider does not support tool allowlists; enforcement not applied".to_string(),
            ));
        }
        let max_attempts = RUN_AGENT_CODEX_MAX_ATTEMPTS;
        let mut attempt = 1;
        loop {
            let outcome = run_provider_session(ProviderRunOptions {
                provider: ModelProvider::Codex,
                model,
                prompt,
                project_dir,
                output_tx: output_tx.clone(),
                log_dir,
                timeout_secs,
                skip_git_repo_check: false,
                cancel_flag: shutdown.clone(),
                config_override: Some(&config),
            })
            .await?;

            if should_retry_run_agent_attempt(provider, &outcome, attempt, max_attempts) {
                let _ = output_tx.send(AgentOutputEvent::Stderr(format!(
                    "Codex transport stalled; retrying attempt {}/{}",
                    attempt + 1,
                    max_attempts
                )));
                attempt += 1;
                continue;
            }

            // Retries exhausted -- check if we should fall back to Claude
            if should_fallback_to_claude(&outcome) {
                let _ = output_tx.send(AgentOutputEvent::Stderr(format!(
                    "Codex {} failed ({}); falling back to Claude default model",
                    role,
                    outcome
                        .failure_message
                        .as_deref()
                        .unwrap_or("unknown error"),
                )));
                return Box::pin(run_agent(
                    role,
                    ModelProvider::Claude,
                    "",
                    prompt,
                    project_dir,
                    output_tx,
                    log_dir,
                    Some(effective_tools),
                    timeout_secs,
                    shutdown,
                    Some(&config),
                ))
                .await;
            }

            return Ok(outcome);
        }
    }

    // OpenCode: delegate to run_provider_session which builds the `opencode run`
    // CLI invocation. No retry loop or Claude fallback -- OpenCode is typically
    // a local model (LM Studio / Ollama), so network-style stalls don't apply.
    if provider == ModelProvider::OpenCode {
        if config.enforce_phase_rbac {
            let _ = output_tx.send(AgentOutputEvent::Stderr(
                "[foundry] enforce_phase_rbac: OpenCode provider does not support tool allowlists; enforcement not applied".to_string(),
            ));
        }
        return run_provider_session(ProviderRunOptions {
            provider: ModelProvider::OpenCode,
            model,
            prompt,
            project_dir,
            output_tx,
            log_dir,
            timeout_secs,
            skip_git_repo_check: false,
            cancel_flag: shutdown,
            config_override: Some(&config),
        })
        .await;
    }

    let sandbox_cfg = config.sandbox_config();
    let backend = if sandbox_cfg.is_active() && config.agent_backend == "tmux" {
        let _ = output_tx.send(AgentOutputEvent::Stderr(
            "[foundry] sandbox active; forcing PTY backend (tmux incompatible with containerized agents)".to_string(),
        ));
        AgentBackend::Pty
    } else if config.agent_backend == "tmux" && crate::tmux::tmux_binary_available() {
        AgentBackend::Tmux
    } else {
        if config.agent_backend == "tmux" {
            let _ = output_tx.send(AgentOutputEvent::Stderr(
                "[foundry] tmux binary not found; falling back to PTY backend".to_string(),
            ));
        }
        AgentBackend::Pty
    };

    match backend {
        AgentBackend::Pty => {
            run_agent_pty(
                role,
                model,
                prompt,
                project_dir,
                output_tx,
                log_dir,
                effective_tools,
                timeout_secs,
                shutdown,
                &config,
            )
            .await
        }
        AgentBackend::Tmux => {
            run_agent_tmux(
                role,
                model,
                prompt,
                project_dir,
                output_tx,
                log_dir,
                effective_tools,
                timeout_secs,
                shutdown,
                config.tmux_session_prefix.clone(),
                config.tmux_keep_sessions,
                &config,
            )
            .await
        }
    }
}

#[allow(clippy::too_many_arguments)]
async fn run_agent_pty(
    role: &AgentRole,
    model: &str,
    prompt: &str,
    project_dir: &Path,
    output_tx: mpsc::UnboundedSender<AgentOutputEvent>,
    log_dir: &Path,
    effective_tools: &[&str],
    timeout_secs: u64,
    shutdown: Option<Arc<AtomicBool>>,
    config: &Config,
) -> Result<AgentResult> {
    let timestamp = chrono::Utc::now().format("%Y%m%d-%H%M%S");
    let log_file_path = log_dir.join(format!("{}-{}.jsonl", role, timestamp));
    std::fs::create_dir_all(log_dir)?;

    // Build command for PTY execution
    let mut cmd = ModelProvider::Claude.command_builder();
    cmd.arg("-p");
    cmd.arg(prompt);
    if !model.trim().is_empty() {
        cmd.arg("--model");
        cmd.arg(model);
    }
    if config.enforce_phase_rbac {
        cmd.arg("--allowedTools");
        cmd.arg(effective_tools.join(","));
    } else {
        append_permission_flags_pty(&mut cmd);
    }
    cmd.arg("--output-format");
    cmd.arg("stream-json");
    cmd.arg("--verbose");
    // Override any CLAUDE.md instructions that conflict with foundry's orchestration.
    cmd.arg("--append-system-prompt");
    cmd.arg(agent_system_directives());
    cmd.arg("--tools");
    cmd.arg(effective_tools.join(","));
    cmd.cwd(project_dir);
    // Prevent nested Claude detection -- set on the command, not process-wide
    cmd.env("CLAUDECODE", "");

    // Sandbox wrapping: replace cmd with docker run wrapper if sandbox is active
    let sandbox_cfg = config.sandbox_config();
    let cmd = if sandbox_cfg.is_active() {
        // Build the program and args for wrap_command_builder
        let program = "claude";
        let mut args: Vec<String> = vec!["-p".to_string(), prompt.to_string()];
        if !model.trim().is_empty() {
            args.push("--model".to_string());
            args.push(model.to_string());
        }
        if config.enforce_phase_rbac {
            args.push("--allowedTools".to_string());
            args.push(effective_tools.join(","));
        } else {
            append_permission_flags_args(&mut args);
        }
        args.push("--output-format".to_string());
        args.push("stream-json".to_string());
        args.push("--verbose".to_string());
        args.push("--append-system-prompt".to_string());
        args.push(agent_system_directives());
        args.push("--tools".to_string());
        args.push(effective_tools.join(","));
        sandbox_cfg.wrap_command_builder(program, &args, project_dir, &[("CLAUDECODE", "")])
    } else {
        cmd
    };

    // Open a PTY -- this is the key to real-time streaming.
    let pty_system = native_pty_system();
    let pair = pty_system.openpty(PtySize {
        rows: 24,
        cols: 4096,
        pixel_width: 0,
        pixel_height: 0,
    })?;

    let child = pair.slave.spawn_command(cmd)?;
    drop(pair.slave);

    let reader = pair.master.try_clone_reader()?;
    let master = pair.master;

    let (result_tx, result_rx) = tokio::sync::oneshot::channel();

    let role_name = role.to_string();
    let model_name = model.to_string();
    tokio::task::spawn_blocking(move || {
        let tx = output_tx;
        let mut child = child;

        let model_label = model_name.clone();
        let progress = Arc::new(Mutex::new(ProviderProgressState::new(Instant::now())));
        let read_progress = progress.clone();
        let read_thread = std::thread::spawn(move || {
            read_pty_output(reader, &tx, &log_file_path, &model_label, &read_progress);
        });

        let hard_timeout_secs = timeout_secs.saturating_mul(PROVIDER_HARD_TIMEOUT_MULTIPLIER);
        let hard_deadline = Instant::now() + Duration::from_secs(hard_timeout_secs);
        let mut result = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::Failed,
            failure_message: None,
        };

        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    result.success = status.success();
                    result.exit_code = if status.success() { 0 } else { 1 };
                    result.exit_kind = if status.success() {
                        AgentExitKind::Completed
                    } else {
                        AgentExitKind::Failed
                    };
                    if !status.success() {
                        result.failure_message =
                            Some(format!("Agent {} exited unsuccessfully", role_name));
                    }
                    break;
                }
                Ok(None) => {
                    if shutdown
                        .as_ref()
                        .is_some_and(|flag| flag.load(Ordering::Acquire))
                    {
                        let _ = child.kill();
                        let _ = child.wait();
                        result.exit_kind = AgentExitKind::Cancelled;
                        result.failure_message =
                            Some(format!("Agent {} cancelled by shutdown", role_name));
                        break;
                    }
                    let now = Instant::now();
                    let progress_snapshot = progress
                        .lock()
                        .unwrap_or_else(|poisoned| poisoned.into_inner());

                    if progress_snapshot.is_truly_idle(now, Duration::from_secs(timeout_secs)) {
                        drop(progress_snapshot);
                        let _ = child.kill();
                        let _ = child.wait();
                        let message = format!(
                            "Agent {} timed out after {}s without progress",
                            role_name, timeout_secs
                        );
                        eprintln!("[foundry] {} -- killed", message);
                        result.exit_kind = AgentExitKind::TimedOut;
                        result.failure_message = Some(message);
                        break;
                    }

                    if now >= hard_deadline {
                        drop(progress_snapshot);
                        let _ = child.kill();
                        let _ = child.wait();
                        let message = format!(
                            "Agent {} timed out after {}s total runtime",
                            role_name, hard_timeout_secs
                        );
                        eprintln!("[foundry] {} -- killed", message);
                        result.exit_kind = AgentExitKind::TimedOut;
                        result.failure_message = Some(message);
                        break;
                    }

                    drop(progress_snapshot);
                    std::thread::sleep(PROVIDER_POLL_INTERVAL);
                }
                Err(err) => {
                    result.failure_message = Some(format!(
                        "Agent {} failed while waiting on process: {}",
                        role_name, err
                    ));
                    break;
                }
            }
        }

        drop(master);
        let _ = read_thread.join();

        let _ = result_tx.send(result);
    });

    Ok(result_rx.await.unwrap_or(AgentResult {
        success: false,
        exit_code: 1,
        exit_kind: AgentExitKind::Failed,
        failure_message: Some(format!("Agent {} result channel closed", role)),
    }))
}

#[allow(clippy::too_many_arguments)]
async fn run_agent_tmux(
    role: &AgentRole,
    model: &str,
    prompt: &str,
    project_dir: &Path,
    output_tx: mpsc::UnboundedSender<AgentOutputEvent>,
    log_dir: &Path,
    effective_tools: &[&str],
    timeout_secs: u64,
    shutdown: Option<Arc<AtomicBool>>,
    tmux_prefix: String,
    tmux_keep_sessions: bool,
    config: &Config,
) -> Result<AgentResult> {
    let timestamp = chrono::Utc::now().format("%Y%m%d-%H%M%S");
    let log_file_path = log_dir.join(format!("{}-{}.jsonl", role, timestamp));
    std::fs::create_dir_all(log_dir)?;

    let role_slug = format!("{}", role).to_lowercase();
    let abs_log_dir = dunce::canonicalize(log_dir).unwrap_or_else(|_| log_dir.to_path_buf());

    let session = TmuxSession::create(&tmux_prefix, &role_slug, project_dir, &abs_log_dir)
        .context("failed to create tmux session")?;

    let cli_command = TmuxSession::build_cli_command(
        ModelProvider::Claude.slug(),
        prompt,
        model,
        effective_tools,
        config.enforce_phase_rbac,
    );

    session
        .send_keys(&cli_command)
        .context("failed to send command to tmux session")?;

    let _ = output_tx.send(AgentOutputEvent::Stderr(format!(
        "[foundry] tmux session: {} (attach with: tmux attach -t {})",
        session.name, session.name
    )));

    let (result_tx, result_rx) = tokio::sync::oneshot::channel();

    let role_name = role.to_string();
    let model_name = model.to_string();
    tokio::task::spawn_blocking(move || {
        let tx = output_tx;
        let progress = Arc::new(Mutex::new(ProviderProgressState::new(Instant::now())));

        let hard_timeout_secs = timeout_secs.saturating_mul(PROVIDER_HARD_TIMEOUT_MULTIPLIER);
        let hard_deadline = Instant::now() + Duration::from_secs(hard_timeout_secs);
        let mut result = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::Failed,
            failure_message: None,
        };

        let pipe_file = match std::fs::File::open(&session.log_file) {
            Ok(f) => f,
            Err(err) => {
                result.failure_message = Some(format!("failed to open pipe log: {}", err));
                let _ = result_tx.send(result);
                return;
            }
        };
        let mut pipe_reader = std::io::BufReader::new(pipe_file);
        let mut log_file = std::fs::File::create(&log_file_path).ok();
        let mut buf = String::new();

        loop {
            // Check shutdown flag
            if shutdown
                .as_ref()
                .is_some_and(|flag| flag.load(Ordering::Acquire))
            {
                session.kill().ok();
                result.exit_kind = AgentExitKind::Cancelled;
                result.failure_message = Some(format!("Agent {} cancelled by shutdown", role_name));
                break;
            }

            // Read new lines from pipe file
            loop {
                buf.clear();
                match pipe_reader.read_line(&mut buf) {
                    Ok(0) => break,
                    Ok(_) => {
                        let line = buf.trim_end();
                        if line.is_empty() {
                            continue;
                        }

                        {
                            let mut guard = progress.lock().unwrap_or_else(|p| p.into_inner());
                            guard.record_raw_bytes_at(Instant::now());
                        }

                        if let Some(ref mut f) = log_file {
                            use std::io::Write;
                            let _ = writeln!(f, "{}", line);
                        }

                        match parse_claude_provider_line(line, &model_name) {
                            ParsedClaudeLine::Event(event) => {
                                note_provider_event(ModelProvider::Claude, &event, &progress);
                                let _ = tx.send(event);
                                LAST_RESULT_USAGE.with(|cell| {
                                    if let Some(usage) = cell.take() {
                                        let _ = tx.send(AgentOutputEvent::Usage {
                                            cost_usd: usage.cost_usd,
                                            input_tokens: usage.input_tokens,
                                            output_tokens: usage.output_tokens,
                                            context_window: usage.context_window,
                                            cache_creation_tokens: usage.cache_creation_tokens,
                                            cache_read_tokens: usage.cache_read_tokens,
                                        });
                                    }
                                });
                            }
                            ParsedClaudeLine::Ignore => {
                                // Valid JSON parsed -- update last_parsed_event_at so the
                                // tertiary idle check doesn't fire for thinking-only assistant
                                // messages (which are valid JSON with no displayable content).
                                {
                                    let mut guard =
                                        progress.lock().unwrap_or_else(|p| p.into_inner());
                                    guard.record_parsed_event_at(Instant::now());
                                }
                                LAST_RESULT_USAGE.with(|cell| {
                                    if let Some(usage) = cell.take() {
                                        let _ = tx.send(AgentOutputEvent::Usage {
                                            cost_usd: usage.cost_usd,
                                            input_tokens: usage.input_tokens,
                                            output_tokens: usage.output_tokens,
                                            context_window: usage.context_window,
                                            cache_creation_tokens: usage.cache_creation_tokens,
                                            cache_read_tokens: usage.cache_read_tokens,
                                        });
                                    }
                                });
                            }
                            ParsedClaudeLine::Unparsed => {
                                let cleaned = strip_ansi(line);
                                if !cleaned.is_empty() && !is_api_noise(&cleaned) {
                                    note_provider_stderr_line(
                                        ModelProvider::Claude,
                                        &cleaned,
                                        &progress,
                                    );
                                    let _ = tx.send(AgentOutputEvent::Stderr(cleaned));
                                }
                            }
                        }
                    }
                    Err(_) => break,
                }
            }

            // Check if session is still alive
            if !session.is_alive() {
                // Final drain -- read remaining lines from pipe file
                loop {
                    buf.clear();
                    match pipe_reader.read_line(&mut buf) {
                        Ok(0) => break,
                        Ok(_) => {
                            let line = buf.trim_end();
                            if line.is_empty() {
                                continue;
                            }

                            if let Some(ref mut f) = log_file {
                                use std::io::Write;
                                let _ = writeln!(f, "{}", line);
                            }

                            match parse_claude_provider_line(line, &model_name) {
                                ParsedClaudeLine::Event(event) => {
                                    note_provider_event(ModelProvider::Claude, &event, &progress);
                                    let _ = tx.send(event);
                                    LAST_RESULT_USAGE.with(|cell| {
                                        if let Some(usage) = cell.take() {
                                            let _ = tx.send(AgentOutputEvent::Usage {
                                                cost_usd: usage.cost_usd,
                                                input_tokens: usage.input_tokens,
                                                output_tokens: usage.output_tokens,
                                                context_window: usage.context_window,
                                                cache_creation_tokens: usage.cache_creation_tokens,
                                                cache_read_tokens: usage.cache_read_tokens,
                                            });
                                        }
                                    });
                                }
                                ParsedClaudeLine::Ignore => {
                                    LAST_RESULT_USAGE.with(|cell| {
                                        if let Some(usage) = cell.take() {
                                            let _ = tx.send(AgentOutputEvent::Usage {
                                                cost_usd: usage.cost_usd,
                                                input_tokens: usage.input_tokens,
                                                output_tokens: usage.output_tokens,
                                                context_window: usage.context_window,
                                                cache_creation_tokens: usage.cache_creation_tokens,
                                                cache_read_tokens: usage.cache_read_tokens,
                                            });
                                        }
                                    });
                                }
                                ParsedClaudeLine::Unparsed => {
                                    let cleaned = strip_ansi(line);
                                    if !cleaned.is_empty() && !is_api_noise(&cleaned) {
                                        note_provider_stderr_line(
                                            ModelProvider::Claude,
                                            &cleaned,
                                            &progress,
                                        );
                                        let _ = tx.send(AgentOutputEvent::Stderr(cleaned));
                                    }
                                }
                            }
                        }
                        Err(_) => break,
                    }
                }

                result.success = true;
                result.exit_code = 0;
                result.exit_kind = AgentExitKind::Completed;
                break;
            }

            // Check idle timeout
            let now = Instant::now();
            let progress_snapshot = progress.lock().unwrap_or_else(|p| p.into_inner());

            if progress_snapshot.is_truly_idle(now, Duration::from_secs(timeout_secs)) {
                drop(progress_snapshot);
                session.kill().ok();
                let message = format!(
                    "Agent {} timed out after {}s without progress",
                    role_name, timeout_secs
                );
                eprintln!("[foundry] {} -- killed", message);
                result.exit_kind = AgentExitKind::TimedOut;
                result.failure_message = Some(message);
                break;
            }

            // Check hard deadline
            if now >= hard_deadline {
                drop(progress_snapshot);
                session.kill().ok();
                let message = format!(
                    "Agent {} timed out after {}s total runtime",
                    role_name, hard_timeout_secs
                );
                eprintln!("[foundry] {} -- killed", message);
                result.exit_kind = AgentExitKind::TimedOut;
                result.failure_message = Some(message);
                break;
            }

            drop(progress_snapshot);
            std::thread::sleep(PROVIDER_POLL_INTERVAL);
        }

        if !tmux_keep_sessions {
            let _ = session.kill();
        }

        let _ = result_tx.send(result);
    });

    Ok(result_rx.await.unwrap_or(AgentResult {
        success: false,
        exit_code: 1,
        exit_kind: AgentExitKind::Failed,
        failure_message: Some(format!("Agent {} result channel closed", role)),
    }))
}

/// Read PTY output line by line, parse stream-json events, send to TUI.
/// Also writes raw lines to the log file.
#[derive(Debug)]
enum ParsedClaudeLine {
    Event(AgentOutputEvent),
    Ignore,
    Unparsed,
}

fn read_pty_output(
    reader: Box<dyn std::io::Read + Send>,
    tx: &mpsc::UnboundedSender<AgentOutputEvent>,
    log_path: &Path,
    model_name: &str,
    progress: &Arc<Mutex<ProviderProgressState>>,
) {
    let mut buf_reader = std::io::BufReader::new(reader);
    let mut log_file = std::fs::File::create(log_path).ok();
    let mut buf = String::new();

    loop {
        buf.clear();
        match buf_reader.read_line(&mut buf) {
            Ok(0) => break, // EOF — child exited and PTY closed
            Ok(_) => {
                let line = buf.trim_end();
                if line.is_empty() {
                    continue;
                }

                // Record raw bytes as secondary progress signal — even if
                // the line fails to parse, receiving bytes means the agent is alive.
                {
                    let mut guard = progress.lock().unwrap_or_else(|p| p.into_inner());
                    guard.record_raw_bytes_at(Instant::now());
                }

                // Persist raw output to log file
                if let Some(ref mut f) = log_file {
                    use std::io::Write;
                    let _ = writeln!(f, "{}", line);
                }

                match parse_claude_provider_line(line, model_name) {
                    ParsedClaudeLine::Event(event) => {
                        note_provider_event(ModelProvider::Claude, &event, progress);
                        if tx.send(event).is_err() {
                            return; // Channel closed
                        }
                        // Emit Usage event if a result was just parsed
                        LAST_RESULT_USAGE.with(|cell| {
                            if let Some(usage) = cell.take() {
                                let _ = tx.send(AgentOutputEvent::Usage {
                                    cost_usd: usage.cost_usd,
                                    input_tokens: usage.input_tokens,
                                    output_tokens: usage.output_tokens,
                                    context_window: usage.context_window,
                                    cache_creation_tokens: usage.cache_creation_tokens,
                                    cache_read_tokens: usage.cache_read_tokens,
                                });
                            }
                        });
                    }
                    ParsedClaudeLine::Ignore => {
                        // Valid JSON parsed -- update last_parsed_event_at so the
                        // tertiary idle check doesn't fire for thinking-only assistant
                        // messages (which are valid JSON with no displayable content).
                        {
                            let mut guard = progress.lock().unwrap_or_else(|p| p.into_inner());
                            guard.record_parsed_event_at(Instant::now());
                        }
                        // Drain usage even when the Result event itself was suppressed
                        LAST_RESULT_USAGE.with(|cell| {
                            if let Some(usage) = cell.take() {
                                let _ = tx.send(AgentOutputEvent::Usage {
                                    cost_usd: usage.cost_usd,
                                    input_tokens: usage.input_tokens,
                                    output_tokens: usage.output_tokens,
                                    context_window: usage.context_window,
                                    cache_creation_tokens: usage.cache_creation_tokens,
                                    cache_read_tokens: usage.cache_read_tokens,
                                });
                            }
                        });
                        continue;
                    }
                    ParsedClaudeLine::Unparsed => {
                        let cleaned = strip_ansi(line);
                        if !cleaned.is_empty() && !is_api_noise(&cleaned) {
                            note_provider_stderr_line(ModelProvider::Claude, &cleaned, progress);
                            if tx.send(AgentOutputEvent::Stderr(cleaned)).is_err() {
                                return;
                            }
                        }
                    }
                }
            }
            Err(_) => break,
        }
    }
}

fn read_provider_output(
    reader: Box<dyn std::io::Read + Send>,
    tx: &mpsc::UnboundedSender<AgentOutputEvent>,
    log_path: &Path,
    provider: ModelProvider,
    model_name: &str,
    progress: &Arc<Mutex<ProviderProgressState>>,
) {
    let mut buf_reader = std::io::BufReader::new(reader);
    let mut log_file = std::fs::File::create(log_path).ok();
    let mut buf = String::new();

    loop {
        buf.clear();
        match buf_reader.read_line(&mut buf) {
            Ok(0) => break,
            Ok(_) => {
                let line = buf.trim_end();
                if line.is_empty() {
                    continue;
                }

                // Record raw bytes as secondary progress signal
                {
                    let mut guard = progress.lock().unwrap_or_else(|p| p.into_inner());
                    guard.record_raw_bytes_at(Instant::now());
                }

                if let Some(ref mut f) = log_file {
                    use std::io::Write;
                    let _ = writeln!(f, "{}", line);
                }

                match provider {
                    ModelProvider::Claude => match parse_claude_provider_line(line, model_name) {
                        ParsedClaudeLine::Event(event) => {
                            note_provider_event(provider, &event, progress);
                            if tx.send(event).is_err() {
                                return;
                            }
                            // Emit Usage event if a result was just parsed
                            LAST_RESULT_USAGE.with(|cell| {
                                if let Some(usage) = cell.take() {
                                    let _ = tx.send(AgentOutputEvent::Usage {
                                        cost_usd: usage.cost_usd,
                                        input_tokens: usage.input_tokens,
                                        output_tokens: usage.output_tokens,
                                        context_window: usage.context_window,
                                        cache_creation_tokens: usage.cache_creation_tokens,
                                        cache_read_tokens: usage.cache_read_tokens,
                                    });
                                }
                            });
                            continue;
                        }
                        ParsedClaudeLine::Ignore => {
                            // Valid JSON parsed -- update last_parsed_event_at so the
                            // tertiary idle check doesn't fire for thinking-only assistant
                            // messages (which are valid JSON with no displayable content).
                            {
                                let mut guard = progress.lock().unwrap_or_else(|p| p.into_inner());
                                guard.record_parsed_event_at(Instant::now());
                            }
                            // A result event with empty text still sets LAST_RESULT_USAGE.
                            // Drain it here so Usage is emitted even when the Result itself
                            // was suppressed (empty non-error result).
                            LAST_RESULT_USAGE.with(|cell| {
                                if let Some(usage) = cell.take() {
                                    let _ = tx.send(AgentOutputEvent::Usage {
                                        cost_usd: usage.cost_usd,
                                        input_tokens: usage.input_tokens,
                                        output_tokens: usage.output_tokens,
                                        context_window: usage.context_window,
                                        cache_creation_tokens: usage.cache_creation_tokens,
                                        cache_read_tokens: usage.cache_read_tokens,
                                    });
                                }
                            });
                            continue;
                        }
                        ParsedClaudeLine::Unparsed => {}
                    },
                    ModelProvider::Codex => {
                        if let Some(event) = parse_codex_event(line, model_name) {
                            note_provider_event(provider, &event, progress);
                            if tx.send(event).is_err() {
                                return;
                            }
                            continue;
                        }
                    }
                    ModelProvider::OpenCode => {
                        // TODO: parse OpenCode JSON events (--format json).
                        // For now fall through to raw stderr passthrough so
                        // output is still visible in the TUI.
                    }
                }

                let cleaned = strip_ansi(line);
                if !cleaned.is_empty() && !is_api_noise(&cleaned) {
                    note_provider_stderr_line(provider, &cleaned, progress);
                    if tx.send(AgentOutputEvent::Stderr(cleaned)).is_err() {
                        return;
                    }
                }
            }
            Err(_) => break,
        }
    }
}

fn parse_claude_provider_line(line: &str, model_name: &str) -> ParsedClaudeLine {
    // Fast path: try parsing raw line (works on Unix and clean PTY output)
    if let Ok(v) = serde_json::from_str::<Value>(line) {
        return parse_claude_json(&v, model_name);
    }
    // On Windows, ConPTY injects ANSI escape sequences (cursor visibility,
    // bracketed paste, etc.) into the output stream. These appear at the start,
    // end, or even mid-line within JSON events, making them unparseable.
    // Strip ANSI and retry before giving up.
    let cleaned = strip_ansi(line);
    if !cleaned.is_empty() && cleaned != line {
        if let Ok(v) = serde_json::from_str::<Value>(&cleaned) {
            return parse_claude_json(&v, model_name);
        }
    }
    ParsedClaudeLine::Unparsed
}

fn parse_claude_json(v: &Value, model_name: &str) -> ParsedClaudeLine {
    let Some(kind) = v.get("type").and_then(|value| value.as_str()) else {
        return ParsedClaudeLine::Unparsed;
    };

    match kind {
        "assistant" => {
            if let Some(usage) = v.get("message").and_then(|m| m.get("usage")) {
                let turn_input = usage
                    .get("input_tokens")
                    .and_then(|t| t.as_u64())
                    .unwrap_or(0)
                    + usage
                        .get("cache_creation_input_tokens")
                        .and_then(|t| t.as_u64())
                        .unwrap_or(0)
                    + usage
                        .get("cache_read_input_tokens")
                        .and_then(|t| t.as_u64())
                        .unwrap_or(0);
                if turn_input > 0 {
                    LAST_TURN_INPUT_TOKENS.with(|c| c.set(turn_input));
                }
            }
            parse_claude_assistant_message(v)
                .map(ParsedClaudeLine::Event)
                .unwrap_or(ParsedClaudeLine::Ignore)
        }
        "user" => parse_claude_user_message(v)
            .map(ParsedClaudeLine::Event)
            .unwrap_or(ParsedClaudeLine::Ignore),
        "system" => parse_claude_system_event(v)
            .map(ParsedClaudeLine::Event)
            .unwrap_or(ParsedClaudeLine::Ignore),
        "result" => parse_claude_result_event(v)
            .map(ParsedClaudeLine::Event)
            .unwrap_or(ParsedClaudeLine::Ignore),
        "rate_limit_event" => {
            let message = v
                .get("message")
                .and_then(|value| value.as_str())
                .unwrap_or("API rate limited — waiting for retry...");
            ParsedClaudeLine::Event(AgentOutputEvent::Text(format!(
                "[rate limited] {}",
                message
            )))
        }
        "error" => ParsedClaudeLine::Event(AgentOutputEvent::Stderr(
            extract_string_by_keys(v, &["message", "error", "text", "summary"])
                .unwrap_or_else(|| "Claude emitted an error event".to_string()),
        )),
        _ => {
            let subtype = v
                .get("subtype")
                .and_then(|value| value.as_str())
                .unwrap_or("");
            let display_type = if kind == "assistant" {
                model_name
            } else {
                kind
            };
            let label = if subtype.is_empty() {
                format!("[{}]", display_type)
            } else {
                format!("[{}:{}]", display_type, subtype)
            };
            if let Some(text) = extract_string_by_keys(v, &["message", "text", "summary", "detail"])
            {
                let text = truncate_for_preview(&text, 160);
                if text.is_empty() {
                    ParsedClaudeLine::Event(AgentOutputEvent::Text(label))
                } else {
                    ParsedClaudeLine::Event(AgentOutputEvent::Text(format!("{} {}", label, text)))
                }
            } else {
                ParsedClaudeLine::Event(AgentOutputEvent::Text(label))
            }
        }
    }
}

fn parse_claude_assistant_message(v: &Value) -> Option<AgentOutputEvent> {
    let content = v.get("message")?.get("content")?.as_array()?;
    content.iter().find_map(parse_claude_content_block)
}

fn parse_claude_content_block(block: &Value) -> Option<AgentOutputEvent> {
    match block.get("type").and_then(|value| value.as_str()) {
        Some("text") => {
            let text = block.get("text").and_then(|value| value.as_str())?;
            (!text.is_empty()).then(|| AgentOutputEvent::Text(text.to_string()))
        }
        Some("tool_use") => {
            let tool = block
                .get("name")
                .and_then(|value| value.as_str())
                .unwrap_or("unknown")
                .to_string();
            let input_preview = block
                .get("input")
                .map(|input| parse_claude_tool_use_preview(&tool, input))
                .unwrap_or_default();
            Some(AgentOutputEvent::ToolUse {
                tool,
                input_preview,
            })
        }
        Some("thinking") | Some("redacted_thinking") => None,
        Some(kind) if kind.contains("tool_use") => {
            let tool = block
                .get("name")
                .and_then(|value| value.as_str())
                .unwrap_or(kind)
                .to_string();
            let input_preview = block
                .get("input")
                .map(|input| parse_claude_tool_use_preview(&tool, input))
                .unwrap_or_default();
            Some(AgentOutputEvent::ToolUse {
                tool,
                input_preview,
            })
        }
        _ => None,
    }
}

fn parse_claude_tool_use_preview(tool: &str, input: &Value) -> String {
    let preview = match tool {
        "Read" | "Write" | "Edit" => input
            .get("file_path")
            .and_then(|value| value.as_str())
            .unwrap_or("")
            .to_string(),
        "Bash" => input
            .get("command")
            .and_then(|value| value.as_str())
            .unwrap_or("")
            .to_string(),
        "Glob" | "Grep" => input
            .get("pattern")
            .and_then(|value| value.as_str())
            .unwrap_or("")
            .to_string(),
        _ => extract_string_by_keys(
            input,
            &[
                "file_path",
                "command",
                "pattern",
                "path",
                "query",
                "description",
                "input",
            ],
        )
        .unwrap_or_else(|| input.to_string()),
    };

    truncate_for_preview(&preview, 120)
}

fn parse_claude_user_message(v: &Value) -> Option<AgentOutputEvent> {
    let content = v.get("message")?.get("content")?.as_array()?;
    for block in content {
        if block.get("type").and_then(|value| value.as_str()) != Some("tool_result") {
            continue;
        }

        let tool_use_result = v.get("tool_use_result");
        let stderr = tool_use_result
            .and_then(|value| value.get("stderr"))
            .and_then(|value| value.as_str())
            .unwrap_or("");
        let is_error = block
            .get("is_error")
            .and_then(|value| value.as_bool())
            .unwrap_or(false)
            || tool_use_result
                .and_then(|value| value.get("is_error"))
                .and_then(|value| value.as_bool())
                .unwrap_or(false)
            || !stderr.trim().is_empty();
        let text = parse_claude_tool_result_text(block, tool_use_result);
        if text.trim().is_empty() {
            return None;
        }
        return Some(if is_error {
            AgentOutputEvent::Stderr(truncate_for_preview(&text, 200))
        } else {
            AgentOutputEvent::ToolResult {
                output_preview: truncate_for_preview(&text, 200),
            }
        });
    }

    None
}

fn parse_claude_tool_result_text(block: &Value, tool_use_result: Option<&Value>) -> String {
    if let Some(tool_use_result) = tool_use_result {
        if let Some(stderr) = tool_use_result
            .get("stderr")
            .and_then(|value| value.as_str())
            .filter(|value| !value.trim().is_empty())
        {
            return stderr.to_string();
        }
        if let Some(stdout) = tool_use_result
            .get("stdout")
            .and_then(|value| value.as_str())
            .filter(|value| !value.trim().is_empty())
        {
            return stdout.to_string();
        }
        if let Some(matches) = tool_use_result
            .get("matches")
            .and_then(|value| value.as_array())
        {
            let joined = matches
                .iter()
                .filter_map(|item| item.as_str())
                .collect::<Vec<_>>()
                .join(", ");
            if !joined.is_empty() {
                return joined;
            }
        }
        if let Some(text) = extract_string_by_keys(
            tool_use_result,
            &["content", "result", "message", "summary", "query"],
        ) {
            if !text.trim().is_empty() {
                return text;
            }
        }
    }

    if let Some(content) = block.get("content") {
        if let Some(text) = extract_first_string(content) {
            if !text.trim().is_empty() {
                return text.to_string();
            }
        }
        if let Some(items) = content.as_array() {
            let joined = items
                .iter()
                .filter_map(|item| item.get("tool_name").and_then(|value| value.as_str()))
                .collect::<Vec<_>>()
                .join(", ");
            if !joined.is_empty() {
                return joined;
            }
        }
    }

    String::new()
}

fn parse_claude_result_event(v: &Value) -> Option<AgentOutputEvent> {
    let subtype = v
        .get("subtype")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    let is_error = v
        .get("is_error")
        .and_then(|value| value.as_bool())
        .unwrap_or(false)
        || subtype.contains("error")
        || subtype.contains("fail");
    let text =
        extract_string_by_keys(v, &["result", "message", "text", "summary"]).unwrap_or_default();

    // Extract usage data and emit as a separate event via the caller's channel.
    // We store it in a thread-local so the PTY reader can emit it after the Result event.
    LAST_RESULT_USAGE.with(|cell| {
        let cost = v
            .get("total_cost_usd")
            .and_then(|c| c.as_f64())
            .unwrap_or(0.0);
        let usage = v.get("usage");
        let cache_creation = usage
            .and_then(|u| u.get("cache_creation_input_tokens"))
            .and_then(|t| t.as_u64())
            .unwrap_or(0);
        let cache_read = usage
            .and_then(|u| u.get("cache_read_input_tokens"))
            .and_then(|t| t.as_u64())
            .unwrap_or(0);
        let cumulative_input = cache_creation
            + cache_read
            + usage
                .and_then(|u| u.get("input_tokens"))
                .and_then(|t| t.as_u64())
                .unwrap_or(0);
        let output_tokens = usage
            .and_then(|u| u.get("output_tokens"))
            .and_then(|t| t.as_u64())
            .unwrap_or(0);

        // Use per-turn input tokens from the last assistant event if available.
        // Falls back to cumulative total when no assistant event was seen
        // (e.g., single-turn session or stripped stream).
        let last_turn = LAST_TURN_INPUT_TOKENS.with(|c| c.get());
        let estimated_input = if last_turn > 0 {
            last_turn
        } else {
            cumulative_input
        };

        // Find context window from modelUsage (first model entry)
        let context_window = v
            .get("modelUsage")
            .and_then(|mu| mu.as_object())
            .and_then(|map| map.values().next())
            .and_then(|model| model.get("contextWindow"))
            .and_then(|cw| cw.as_u64())
            .unwrap_or(200_000);

        cell.set(Some(ResultUsage {
            cost_usd: cost,
            input_tokens: estimated_input,
            output_tokens,
            context_window,
            cache_creation_tokens: cache_creation,
            cache_read_tokens: cache_read,
        }));
    });

    if text.trim().is_empty() {
        return if is_error {
            Some(AgentOutputEvent::Stderr(format!(
                "Claude session ended with {}",
                if subtype.is_empty() {
                    "an error"
                } else {
                    subtype
                }
            )))
        } else {
            None
        };
    }

    Some(if is_error {
        AgentOutputEvent::Stderr(text)
    } else {
        AgentOutputEvent::Result(text)
    })
}

#[derive(Clone)]
struct ResultUsage {
    cost_usd: f64,
    input_tokens: u64,
    output_tokens: u64,
    context_window: u64,
    cache_creation_tokens: u64,
    cache_read_tokens: u64,
}

thread_local! {
    static LAST_RESULT_USAGE: std::cell::Cell<Option<ResultUsage>> = const { std::cell::Cell::new(None) };
}

thread_local! {
    static LAST_TURN_INPUT_TOKENS: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
}

fn parse_claude_system_event(v: &Value) -> Option<AgentOutputEvent> {
    let subtype = v
        .get("subtype")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    let stderr = v
        .get("stderr")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .trim();

    if !stderr.is_empty() {
        return Some(AgentOutputEvent::Stderr(stderr.to_string()));
    }

    if subtype.contains("error") {
        let text = extract_string_by_keys(v, &["message", "output", "stdout", "summary"])
            .unwrap_or_else(|| format!("Claude system event failed: {}", subtype));
        return Some(AgentOutputEvent::Stderr(text));
    }

    if subtype == "hook_response" {
        let outcome = v
            .get("outcome")
            .and_then(|value| value.as_str())
            .unwrap_or("");
        if !outcome.is_empty() && outcome != "success" {
            let text = extract_string_by_keys(v, &["output", "stdout", "message", "summary"])
                .unwrap_or_else(|| format!("Claude hook failed: {}", outcome));
            return Some(AgentOutputEvent::Stderr(truncate_for_preview(&text, 200)));
        }
    }

    None
}

fn parse_codex_event(line: &str, model_name: &str) -> Option<AgentOutputEvent> {
    let v: Value = serde_json::from_str(line).ok()?;
    let kind = v
        .get("type")
        .and_then(|value| value.as_str())
        .or_else(|| v.get("event").and_then(|value| value.as_str()))
        .unwrap_or("");

    if let Some(tool) = extract_string_by_keys(&v, &["tool", "tool_name", "name"]) {
        if kind.contains("tool") || kind.contains("call") {
            let input_preview = extract_string_by_keys(
                &v,
                &[
                    "input",
                    "arguments",
                    "command",
                    "cmd",
                    "preview",
                    "description",
                ],
            )
            .unwrap_or_default();
            return Some(AgentOutputEvent::ToolUse {
                tool,
                input_preview: truncate_for_preview(&input_preview, 120),
            });
        }
    }

    if kind.contains("tool_result") || kind.contains("tool_output") {
        let output = extract_string_by_keys(
            &v,
            &["output", "content", "result", "message", "text", "summary"],
        )
        .unwrap_or_default();
        if output.is_empty() {
            return None;
        }
        return Some(AgentOutputEvent::ToolResult {
            output_preview: truncate_for_preview(&output, 200),
        });
    }

    if kind.contains("error") || kind.contains("failed") {
        let text = extract_string_by_keys(&v, &["message", "error", "text", "summary"])
            .unwrap_or_else(|| line.to_string());
        return Some(AgentOutputEvent::Stderr(text));
    }

    if kind.contains("completed") || kind == "result" || kind == "final" {
        if let Some(text) =
            extract_string_by_keys(&v, &["result", "message", "content", "text", "summary"])
        {
            if !text.is_empty() {
                return Some(AgentOutputEvent::Result(text));
            }
        }
    }

    if let Some(text) = extract_string_by_keys(
        &v,
        &[
            "text", "delta", "message", "content", "summary", "output", "reason",
        ],
    ) {
        if !text.is_empty() {
            if kind.starts_with("message")
                || kind.starts_with("response")
                || kind.starts_with("content")
                || kind.is_empty()
            {
                return Some(AgentOutputEvent::Text(text));
            }

            return Some(AgentOutputEvent::Text(format!(
                "[{}:{}] {}",
                model_name, kind, text
            )));
        }
    }

    if !kind.is_empty() {
        return Some(AgentOutputEvent::Text(format!("[{}:{}]", model_name, kind)));
    }

    None
}

fn extract_string_by_keys(value: &Value, keys: &[&str]) -> Option<String> {
    for key in keys {
        if let Some(candidate) = value.get(*key).and_then(extract_first_string) {
            if !candidate.trim().is_empty() {
                return Some(candidate.to_string());
            }
        }
    }

    extract_first_string(value).map(|text| text.to_string())
}

fn extract_first_string(value: &Value) -> Option<&str> {
    match value {
        Value::String(text) => Some(text.as_str()),
        Value::Array(items) => items.iter().find_map(extract_first_string),
        Value::Object(map) => {
            let preferred = [
                "text", "delta", "message", "content", "output", "summary", "reason", "error",
                "command",
            ];

            for key in preferred {
                if let Some(text) = map.get(key).and_then(extract_first_string) {
                    return Some(text);
                }
            }

            map.values().find_map(extract_first_string)
        }
        _ => None,
    }
}

fn truncate_for_preview(text: &str, max_len: usize) -> String {
    if text.len() > max_len {
        format!("{}...", truncate_str(text, max_len))
    } else {
        text.to_string()
    }
}

/// Parse a single line of claude's stream-json NDJSON output.
#[cfg(test)]
fn parse_stream_event(line: &str) -> Option<AgentOutputEvent> {
    let v: Value = serde_json::from_str(line).ok()?;
    match parse_claude_json(&v, "claude") {
        ParsedClaudeLine::Event(event) => Some(event),
        ParsedClaudeLine::Ignore | ParsedClaudeLine::Unparsed => None,
    }
}

/// Strip ANSI escape sequences and C0 control characters from PTY output.
/// Handles CSI (`\x1b[...X`), OSC (`\x1b]...BEL` / `\x1b]...\x1b\\`),
/// simple two-byte escapes (`\x1b X`), and stray control chars (BEL, etc.).
/// Returns the cleaned string. Empty after trim means the line was pure noise.
/// Filter out raw API response fragments that leak through when the PTY
/// wraps long JSON lines (common on Windows). These are noise from the
/// Claude CLI's stderr or split stream-json lines.
fn is_api_noise(line: &str) -> bool {
    let l = line.trim();
    // Fragments of base64-encoded content blocks
    if l.len() > 60
        && l.chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '+' || c == '/' || c == '=')
    {
        return true;
    }
    // Raw API JSON fragments (usage, session, content_block, etc.)
    if l.contains("\"cache_creation_input_tokens\"")
        || l.contains("\"cache_read_input_tokens\"")
        || l.contains("\"stop_reason\":")
        || l.contains("\"stop_sequence\":")
        || l.contains("\"session_id\":")
        || l.contains("\"parent_tool_use_id\":")
        || l.contains("\"service_tier\":")
        || l.contains("\"inference_profile\"")
    {
        return true;
    }
    false
}

fn strip_ansi(line: &str) -> String {
    let mut out = String::with_capacity(line.len());
    let mut chars = line.chars().peekable();

    while let Some(c) = chars.next() {
        if c == '\x1b' {
            match chars.peek() {
                // CSI: \x1b[ ... final byte is 0x40..=0x7E per ECMA-48
                Some('[') => {
                    chars.next(); // consume '['
                    while let Some(&ch) = chars.peek() {
                        chars.next();
                        if ('@'..='~').contains(&ch) {
                            break;
                        }
                    }
                }
                // OSC: \x1b] ... terminated by BEL (\x07) or ST (\x1b\\)
                Some(']') => {
                    chars.next(); // consume ']'
                    while let Some(&ch) = chars.peek() {
                        if ch == '\x07' {
                            chars.next();
                            break;
                        }
                        if ch == '\x1b' {
                            chars.next();
                            if chars.peek() == Some(&'\\') {
                                chars.next();
                            }
                            break;
                        }
                        chars.next();
                    }
                }
                // Simple two-byte escape: \x1b + one character
                Some(_) => {
                    chars.next();
                }
                // Trailing lone ESC at end of line
                None => {}
            }
        } else if c.is_control() && c != '\n' && c != '\t' {
            // Drop stray C0 control characters (BEL, BS, etc.)
        } else {
            out.push(c);
        }
    }

    // Return the stripped content as-is (preserving internal whitespace).
    // Only consider it empty/noise if trimming yields nothing.
    if out.trim().is_empty() {
        String::new()
    } else {
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strip_ansi_csi_sequences() {
        // Cursor visibility, bracketed paste mode
        assert_eq!(strip_ansi("\x1b[?25h\x1b[?2004l"), "");
        // CSI with content around it
        assert_eq!(strip_ansi("hello\x1b[31mworld\x1b[0m"), "helloworld");
    }

    #[test]
    fn strip_ansi_csi_at_terminator() {
        // CSI with @ final byte (Insert Character) — must not eat 'b'
        assert_eq!(strip_ansi("a\x1b[0@b"), "ab");
    }

    #[test]
    fn strip_ansi_osc_bel_terminated() {
        // OSC title set terminated by BEL
        assert_eq!(strip_ansi("\x1b]0;title\x07hello"), "hello");
    }

    #[test]
    fn strip_ansi_osc_st_terminated() {
        // OSC terminated by ST (\x1b\\)
        assert_eq!(strip_ansi("\x1b]0;title\x1b\\hello"), "hello");
    }

    #[test]
    fn strip_ansi_mixed_noise() {
        // Real PTY noise from screenshots: escape codes + semicolons + digits
        let noise = "\x1b[<u\x1b[?1004l\x1b[?2004l\x1b[?25h\x1b]9;4;0;\x07\x1b[?25h";
        assert_eq!(strip_ansi(noise), "");
    }

    #[test]
    fn strip_ansi_preserves_plain_text() {
        assert_eq!(strip_ansi("just plain text"), "just plain text");
    }

    #[test]
    fn strip_ansi_preserves_leading_whitespace() {
        // Indented stack frames must keep their formatting
        assert_eq!(strip_ansi("    at main.rs:42"), "    at main.rs:42");
        assert_eq!(strip_ansi("  \x1b[31merror\x1b[0m here"), "  error here");
    }

    #[test]
    fn strip_ansi_stray_control_chars() {
        // BEL and other control chars outside escape sequences
        assert_eq!(strip_ansi("a\x07b\x08c"), "abc");
    }

    #[test]
    fn parse_claude_line_strips_ansi_before_json() {
        // Simulate ConPTY injecting cursor-hide before JSON
        let line = "\x1b[?25l{\"type\":\"system\",\"subtype\":\"init\",\"session_id\":\"abc\"}";
        match parse_claude_provider_line(line, "opus") {
            ParsedClaudeLine::Event(_) | ParsedClaudeLine::Ignore => {} // parsed OK
            ParsedClaudeLine::Unparsed => panic!("should have parsed after ANSI strip"),
        }
    }

    #[test]
    fn parse_claude_line_strips_ansi_wrapping_json() {
        // ConPTY bracketed paste + cursor-show wrapping a full event
        let line = "\x1b[?2004l{\"type\":\"assistant\",\"message\":{\"content\":[{\"type\":\"text\",\"text\":\"hello\"}]}}\x1b[?25h";
        match parse_claude_provider_line(line, "opus") {
            ParsedClaudeLine::Event(AgentOutputEvent::Text(t)) => {
                assert_eq!(t, "hello");
            }
            other => panic!("expected Text event, got {:?}", other),
        }
    }

    #[test]
    fn parse_claude_line_clean_json_fast_path() {
        // Clean JSON without ANSI should still work (fast path)
        let line = r#"{"type":"system","subtype":"init","session_id":"x"}"#;
        match parse_claude_provider_line(line, "opus") {
            ParsedClaudeLine::Unparsed => panic!("clean JSON should parse"),
            _ => {}
        }
    }

    #[test]
    fn codex_transport_issue_detection_matches_reconnect_timeout_lines() {
        assert!(is_codex_transport_issue(
            "Reconnecting... 2/5 (stream disconnected before completion: idle timeout waiting for websocket)"
        ));
        assert!(!is_codex_transport_issue("tool stderr: permission denied"));
    }

    #[test]
    fn provider_progress_state_flags_codex_transport_stalls() {
        let start = Instant::now();
        let mut state = ProviderProgressState::new(start);

        state.record_progress_at(start);
        state.record_transport_issue_at(start + Duration::from_secs(5));
        assert!(!state.transport_stalled(start + Duration::from_secs(30)));
        assert!(state.transport_stalled(start + Duration::from_secs(96)));
    }

    #[test]
    fn provider_progress_state_clears_transport_stall_after_progress_resumes() {
        let start = Instant::now();
        let mut state = ProviderProgressState::new(start);

        state.record_transport_issue_at(start + Duration::from_secs(5));
        state.record_progress_at(start + Duration::from_secs(20));

        assert!(!state.transport_stalled(start + Duration::from_secs(120)));
    }

    #[test]
    fn test_is_truly_idle_original_behavior_no_output() {
        // When no output at all, idle fires after timeout (existing behavior preserved)
        let start = Instant::now();
        let state = ProviderProgressState::new(start);
        let timeout = Duration::from_secs(60);

        assert!(!state.is_truly_idle(start + Duration::from_secs(30), timeout));
        assert!(state.is_truly_idle(start + Duration::from_secs(61), timeout));
    }

    #[test]
    fn test_is_truly_idle_tertiary_fires_with_stderr_but_no_parsed_events() {
        // Simulates the pathological case: agent outputs non-JSON continuously.
        // record_raw_bytes_at + record_progress_at called (from note_provider_stderr_line),
        // but record_parsed_event_at is NEVER called.
        let start = Instant::now();
        let mut state = ProviderProgressState::new(start);
        let timeout = Duration::from_secs(60);

        // Unparseable lines arrive at 30s and 55s
        state.record_raw_bytes_at(start + Duration::from_secs(30));
        state.record_progress_at(start + Duration::from_secs(30));
        state.record_raw_bytes_at(start + Duration::from_secs(55));
        state.record_progress_at(start + Duration::from_secs(55));

        // At 59s: last_parsed_event_at = start (59s ago < 60s timeout). Not idle yet.
        assert!(!state.is_truly_idle(start + Duration::from_secs(59), timeout));

        // At 61s: last_parsed_event_at = start (61s ago > timeout), raw bytes at 55s (6s ago).
        // Tertiary fires: no_parsed_events=true, !no_raw=true
        assert!(state.is_truly_idle(start + Duration::from_secs(61), timeout));
    }

    #[test]
    fn test_is_truly_idle_does_not_fire_when_parsed_events_flow() {
        // When parsed events keep arriving, neither original nor tertiary fires
        let start = Instant::now();
        let mut state = ProviderProgressState::new(start);
        let timeout = Duration::from_secs(60);

        // Parsed event at 50s
        state.record_progress_at(start + Duration::from_secs(50));
        state.record_parsed_event_at(start + Duration::from_secs(50));
        state.record_raw_bytes_at(start + Duration::from_secs(50));

        // At 100s: last_parsed_event_at = 50s (50s ago < 60s timeout). Not idle.
        assert!(!state.is_truly_idle(start + Duration::from_secs(100), timeout));

        // At 111s: last_parsed_event_at = 50s (61s ago > timeout), no_raw also > timeout.
        // Original check fires: no_progress=true, no_raw=true
        assert!(state.is_truly_idle(start + Duration::from_secs(111), timeout));
    }

    #[test]
    fn test_is_truly_idle_tertiary_fires_when_parsed_events_stop_mid_session() {
        // Agent starts producing parsed events, then switches to only unparseable output
        let start = Instant::now();
        let mut state = ProviderProgressState::new(start);
        let timeout = Duration::from_secs(60);

        // Parsed event at 10s
        state.record_progress_at(start + Duration::from_secs(10));
        state.record_parsed_event_at(start + Duration::from_secs(10));

        // Unparseable output continues at 50s, 60s, 65s (no parsed_event_at update)
        state.record_raw_bytes_at(start + Duration::from_secs(50));
        state.record_progress_at(start + Duration::from_secs(50));
        state.record_raw_bytes_at(start + Duration::from_secs(60));
        state.record_progress_at(start + Duration::from_secs(60));
        state.record_raw_bytes_at(start + Duration::from_secs(65));
        state.record_progress_at(start + Duration::from_secs(65));

        // At 71s: last_parsed_event_at = 10s (61s ago > timeout), raw at 65s (6s ago).
        // Tertiary fires.
        assert!(state.is_truly_idle(start + Duration::from_secs(71), timeout));
    }

    #[test]
    fn test_ignore_events_refresh_last_parsed_event_at_preventing_tertiary_idle() {
        // Simulates the PTY path where the agent emits valid-but-ignored JSON events
        // (thinking-only assistant messages, empty results). These are ParsedClaudeLine::Ignore
        // events that should refresh last_parsed_event_at to prevent spurious tertiary idle.
        let start = Instant::now();
        let mut state = ProviderProgressState::new(start);
        let timeout = Duration::from_secs(60);

        // Raw bytes arrive continuously (agent is alive)
        state.record_raw_bytes_at(start + Duration::from_secs(30));
        state.record_progress_at(start + Duration::from_secs(30));

        // An Ignore event arrives at 40s -- this is the record_parsed_event_at call
        // that the PTY Ignore handler must make.
        state.record_parsed_event_at(start + Duration::from_secs(40));

        // More raw bytes at 55s
        state.record_raw_bytes_at(start + Duration::from_secs(55));
        state.record_progress_at(start + Duration::from_secs(55));

        // At 95s: last_parsed_event_at = 40s (55s ago < 60s timeout).
        // Tertiary should NOT fire because the Ignore event refreshed last_parsed_event_at.
        assert!(!state.is_truly_idle(start + Duration::from_secs(95), timeout));

        // At 101s: last_parsed_event_at = 40s (61s ago > timeout), raw at 55s (46s ago < timeout).
        // NOW tertiary fires because no new parsed event (including Ignore) arrived.
        assert!(state.is_truly_idle(start + Duration::from_secs(101), timeout));
    }

    #[test]
    fn run_agent_retry_policy_retries_codex_transport_stalls_once() {
        let outcome = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::TransportStall,
            failure_message: Some("stalled".to_string()),
        };

        assert!(should_retry_run_agent_attempt(
            ModelProvider::Codex,
            &outcome,
            1,
            RUN_AGENT_CODEX_MAX_ATTEMPTS
        ));
        assert!(!should_retry_run_agent_attempt(
            ModelProvider::Codex,
            &outcome,
            RUN_AGENT_CODEX_MAX_ATTEMPTS,
            RUN_AGENT_CODEX_MAX_ATTEMPTS
        ));
    }

    #[test]
    fn run_agent_retry_policy_does_not_retry_claude_or_non_transport_failures() {
        let transport_outcome = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::TransportStall,
            failure_message: Some("stalled".to_string()),
        };
        let failed_outcome = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::Failed,
            failure_message: Some("failed".to_string()),
        };

        assert!(!should_retry_run_agent_attempt(
            ModelProvider::Claude,
            &transport_outcome,
            1,
            RUN_AGENT_CODEX_MAX_ATTEMPTS
        ));
        assert!(!should_retry_run_agent_attempt(
            ModelProvider::Codex,
            &failed_outcome,
            1,
            RUN_AGENT_CODEX_MAX_ATTEMPTS
        ));
    }

    #[test]
    fn parse_rate_limit_event() {
        let json = r#"{"type":"rate_limit_event","message":"Rate limited, retrying in 5s"}"#;
        let event = parse_stream_event(json);
        match event {
            Some(AgentOutputEvent::Text(t)) => {
                assert!(t.contains("[rate limited]"));
                assert!(t.contains("retrying in 5s"));
            }
            other => panic!("expected Text with rate limit message, got {:?}", other),
        }
    }

    #[test]
    fn parse_rate_limit_event_no_message() {
        let json = r#"{"type":"rate_limit_event"}"#;
        let event = parse_stream_event(json);
        match event {
            Some(AgentOutputEvent::Text(t)) => {
                assert_eq!(t, "[rate limited] API rate limited — waiting for retry...");
            }
            other => panic!("expected Text with rate limit fallback, got {:?}", other),
        }
    }

    #[test]
    fn parse_codex_tool_event() {
        let json =
            r#"{"type":"tool_call","tool":"shell","input":{"command":"cargo test --quiet"}}"#;
        let event = parse_codex_event(json, "gpt-5.4");
        match event {
            Some(AgentOutputEvent::ToolUse {
                tool,
                input_preview,
            }) => {
                assert_eq!(tool, "shell");
                assert!(input_preview.contains("cargo test"));
            }
            other => panic!("expected ToolUse, got {:?}", other),
        }
    }

    #[test]
    fn parse_codex_message_event() {
        let json = r#"{"type":"message","content":"Built a dashboard and wrote report.html"}"#;
        let event = parse_codex_event(json, "gpt-5.4");
        match event {
            Some(AgentOutputEvent::Text(text)) => {
                assert!(text.contains("Built a dashboard"));
            }
            other => panic!("expected Text, got {:?}", other),
        }
    }

    #[test]
    fn parse_claude_tool_use_event() {
        let json = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/demo.rs"}}]}}"#;
        let event = parse_stream_event(json);
        match event {
            Some(AgentOutputEvent::ToolUse {
                tool,
                input_preview,
            }) => {
                assert_eq!(tool, "Read");
                assert_eq!(input_preview, "/tmp/demo.rs");
            }
            other => panic!("expected ToolUse, got {:?}", other),
        }
    }

    #[test]
    fn parse_claude_user_tool_result_event() {
        let json = r#"{"type":"user","message":{"content":[{"type":"tool_result","content":"Todos updated","is_error":false}]},"tool_use_result":{"stdout":"Todos updated","stderr":"","is_error":false}}"#;
        let event = parse_stream_event(json);
        match event {
            Some(AgentOutputEvent::ToolResult { output_preview }) => {
                assert_eq!(output_preview, "Todos updated");
            }
            other => panic!("expected ToolResult, got {:?}", other),
        }
    }

    #[test]
    fn parse_claude_error_result_event() {
        let json = r#"{"type":"result","subtype":"error_max_turns","is_error":true,"result":"Max turns reached"}"#;
        let event = parse_stream_event(json);
        match event {
            Some(AgentOutputEvent::Stderr(text)) => {
                assert!(text.contains("Max turns reached"));
            }
            other => panic!("expected Stderr, got {:?}", other),
        }
    }

    #[test]
    fn parse_result_uses_per_turn_input_tokens() {
        // Reset thread-local state
        LAST_TURN_INPUT_TOKENS.with(|c| c.set(0));
        LAST_RESULT_USAGE.with(|c| c.set(None));

        // 1. Parse an assistant event with per-turn usage
        let assistant_json = r#"{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}],"usage":{"input_tokens":50000,"cache_creation_input_tokens":10000,"cache_read_input_tokens":30000,"output_tokens":500}}}"#;
        let _ = parse_stream_event(assistant_json);

        // Verify thread-local was set: 50000 + 10000 + 30000 = 90000
        let stored = LAST_TURN_INPUT_TOKENS.with(|c| c.get());
        assert_eq!(stored, 90_000, "LAST_TURN_INPUT_TOKENS should be 90000");

        // 2. Parse a result event with cumulative usage (much larger, simulating multi-turn)
        let result_json = r#"{"type":"result","subtype":"success","result":"done","usage":{"input_tokens":200000,"cache_creation_input_tokens":50000,"cache_read_input_tokens":100000,"output_tokens":20000},"num_turns":10,"total_cost_usd":0.5,"modelUsage":{"claude-sonnet-4-20250514":{"contextWindow":200000}}}"#;
        let _ = parse_stream_event(result_json);

        // 3. Verify the ResultUsage used per-turn (90000), not cumulative estimate
        let usage = LAST_RESULT_USAGE.with(|c| c.take());
        assert!(usage.is_some(), "LAST_RESULT_USAGE should be set");
        let usage = usage.unwrap();
        assert_eq!(
            usage.input_tokens, 90_000,
            "input_tokens should be per-turn value (90000), not cumulative"
        );
        assert_eq!(usage.output_tokens, 20_000);
        assert_eq!(usage.context_window, 200_000);
        assert!((usage.cost_usd - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn parse_result_falls_back_to_cumulative_without_assistant() {
        // Reset thread-local state
        LAST_TURN_INPUT_TOKENS.with(|c| c.set(0));
        LAST_RESULT_USAGE.with(|c| c.set(None));

        // Parse a result event WITHOUT a preceding assistant event
        let result_json = r#"{"type":"result","subtype":"success","result":"done","usage":{"input_tokens":100000,"cache_creation_input_tokens":20000,"cache_read_input_tokens":50000,"output_tokens":5000},"num_turns":5,"total_cost_usd":0.1,"modelUsage":{"claude-sonnet-4-20250514":{"contextWindow":200000}}}"#;
        let _ = parse_stream_event(result_json);

        // Should fall back to cumulative: 100000 + 20000 + 50000 = 170000
        let usage = LAST_RESULT_USAGE.with(|c| c.take());
        assert!(usage.is_some(), "LAST_RESULT_USAGE should be set");
        let usage = usage.unwrap();
        assert_eq!(
            usage.input_tokens, 170_000,
            "input_tokens should be cumulative fallback (170000)"
        );
    }

    #[test]
    fn parse_claude_thinking_message_is_ignored() {
        let json = r#"{"type":"assistant","message":{"content":[{"type":"thinking","thinking":"hidden"}]}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude-opus"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn parse_claude_system_stderr_event() {
        let json = r#"{"type":"system","subtype":"hook_response","stderr":"permission denied"}"#;
        let event = parse_claude_provider_line(json, "claude-opus");
        match event {
            ParsedClaudeLine::Event(AgentOutputEvent::Stderr(text)) => {
                assert!(text.contains("permission denied"));
            }
            other => panic!("expected stderr event, got {:?}", other),
        }
    }

    #[test]
    fn parse_claude_system_hook_failure_event() {
        let json = r#"{"type":"system","subtype":"hook_response","outcome":"failure","output":"hook failed"}"#;
        let event = parse_claude_provider_line(json, "claude-opus");
        match event {
            ParsedClaudeLine::Event(AgentOutputEvent::Stderr(text)) => {
                assert!(text.contains("hook failed"));
            }
            other => panic!("expected hook failure stderr, got {:?}", other),
        }
    }

    #[test]
    fn fallback_triggers_on_rate_limit_keywords() {
        let keywords = [
            "rate limit exceeded",
            "quota exhausted for this billing period",
            "subscription limit reached",
            "HTTP 429 too many requests",
            "API rate limit hit",
        ];
        for msg in keywords {
            let outcome = AgentResult {
                success: false,
                exit_code: 1,
                exit_kind: AgentExitKind::Failed,
                failure_message: Some(msg.to_string()),
            };
            assert!(
                should_fallback_to_claude(&outcome),
                "expected fallback for message: {msg}"
            );
        }
    }

    #[test]
    fn fallback_triggers_on_transport_stall_and_failed() {
        for kind in [AgentExitKind::TransportStall, AgentExitKind::Failed] {
            let outcome = AgentResult {
                success: false,
                exit_code: 1,
                exit_kind: kind,
                failure_message: Some("something went wrong".to_string()),
            };
            assert!(
                should_fallback_to_claude(&outcome),
                "expected fallback for exit kind: {kind:?}"
            );
        }
    }

    #[test]
    fn fallback_skips_successful_outcomes() {
        let outcome = AgentResult {
            success: true,
            exit_code: 0,
            exit_kind: AgentExitKind::Completed,
            failure_message: None,
        };
        assert!(!should_fallback_to_claude(&outcome));
    }

    #[test]
    fn fallback_skips_non_rate_limit_cancellations_and_timeouts() {
        for kind in [AgentExitKind::Cancelled, AgentExitKind::TimedOut] {
            let outcome = AgentResult {
                success: false,
                exit_code: 1,
                exit_kind: kind,
                failure_message: Some("user cancelled".to_string()),
            };
            assert!(
                !should_fallback_to_claude(&outcome),
                "should NOT fallback for exit kind: {kind:?}"
            );
        }
    }

    #[test]
    fn test_agent_backend_pty_is_default() {
        let config = crate::config::Config::default();
        assert_eq!(config.agent_backend, "pty");
    }

    #[test]
    fn test_agent_backend_tmux_from_config() {
        let config: crate::config::Config = serde_json::from_str(r#"{"agent_backend": "tmux"}"#)
            .expect("config should deserialize");
        assert_eq!(config.agent_backend, "tmux");
    }

    #[test]
    #[ignore]
    fn test_run_agent_tmux_creates_session() {
        use crate::tmux::TmuxSession;

        let tmp = std::env::temp_dir();
        let session =
            TmuxSession::create("test", "builder", &std::env::current_dir().unwrap(), &tmp)
                .expect("should create session");

        session.send_keys("echo hello").expect("should send keys");
        std::thread::sleep(Duration::from_millis(500));

        assert!(session.is_alive());

        session.kill().expect("should kill session");
        std::thread::sleep(Duration::from_millis(100));

        assert!(!session.is_alive());
    }

    #[tokio::test]
    #[ignore]
    async fn test_scout_via_tmux_backend_e2e() {
        use crate::tmux;

        if !tmux::tmux_binary_available() {
            eprintln!("tmux not available, skipping e2e test");
            return;
        }

        let unique = std::process::id();
        let project_dir = std::env::temp_dir().join(format!("foundry-tmux-scout-e2e-{}", unique));
        std::fs::create_dir_all(&project_dir).unwrap();

        // Write minimal project files
        std::fs::write(
            project_dir.join("CLAUDE.md"),
            "# Test\nA trivial test project.",
        )
        .unwrap();
        std::fs::write(
            project_dir.join(".foundry.json"),
            r#"{"agent_backend":"tmux","tmux_session_prefix":"foundry-e2e","tmux_keep_sessions":false,"agent_timeout_secs":60}"#,
        )
        .unwrap();

        let log_dir = project_dir.join(".buildloop").join("logs");
        std::fs::create_dir_all(&log_dir).unwrap();

        // Verify no pre-existing test sessions
        let pre = tmux::list_sessions("foundry-e2e");
        assert!(pre.is_empty(), "stale test sessions found: {:?}", pre);

        let (tx, mut rx) = mpsc::unbounded_channel();
        let shutdown = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));

        let result = run_agent(
            &AgentRole::Scout,
            ModelProvider::Claude,
            "",
            "List the files in this project. Write a one-line summary to .buildloop/scout-report.md.",
            &project_dir,
            tx,
            &log_dir,
            None,
            60,
            Some(shutdown),
            None,
        )
        .await;

        // Collect events
        let mut events = Vec::new();
        while let Ok(event) = rx.try_recv() {
            events.push(event);
        }

        assert!(result.is_ok(), "run_agent should not return Err");
        let agent_result = result.unwrap();
        assert!(
            agent_result.success,
            "scout should succeed, got: {:?}",
            agent_result.failure_message
        );
        assert!(!events.is_empty(), "should have received output events");

        // Verify sessions cleaned up (keep_sessions=false)
        let post = tmux::list_sessions("foundry-e2e");
        assert!(post.is_empty(), "sessions not cleaned up: {:?}", post);

        let _ = std::fs::remove_dir_all(&project_dir);
    }

    #[test]
    fn test_allowed_tools_for_role_scout() {
        let tools = allowed_tools_for_role(&AgentRole::Scout);
        assert_eq!(
            tools,
            &["Read", "Glob", "Grep", "Bash", "WebFetch", "WebSearch"]
        );
        assert!(!tools.contains(&"Edit"));
        assert!(!tools.contains(&"Write"));
    }

    #[test]
    fn test_allowed_tools_for_role_planner() {
        let tools = allowed_tools_for_role(&AgentRole::Planner);
        assert_eq!(tools, &["Read", "Glob", "Grep", "Edit", "Write"]);
        assert!(!tools.contains(&"Bash"));
        assert!(!tools.contains(&"WebFetch"));
        assert!(!tools.contains(&"NotebookEdit"));
    }

    #[test]
    fn test_allowed_tools_for_role_plan_review() {
        let tools = allowed_tools_for_role(&AgentRole::PlanReview);
        assert_eq!(tools, allowed_tools_for_role(&AgentRole::Planner));
    }

    #[test]
    fn test_allowed_tools_for_role_builder() {
        let tools = allowed_tools_for_role(&AgentRole::Builder);
        assert!(tools.contains(&"Bash"));
        assert!(tools.contains(&"Edit"));
        assert!(tools.contains(&"Write"));
        assert!(tools.contains(&"Read"));
        assert!(tools.contains(&"Glob"));
        assert!(tools.contains(&"Grep"));
        assert!(tools.contains(&"NotebookEdit"));
        assert!(tools.contains(&"WebFetch"));
        assert!(tools.contains(&"WebSearch"));
        assert_eq!(tools.len(), 9);
    }

    #[test]
    fn test_allowed_tools_for_role_reviewer() {
        let tools = allowed_tools_for_role(&AgentRole::Reviewer);
        assert_eq!(tools, &["Read", "Glob", "Grep", "Bash", "Edit", "Write"]);
        assert!(!tools.contains(&"NotebookEdit"));
        assert!(!tools.contains(&"WebFetch"));
    }

    #[test]
    fn test_allowed_tools_for_role_fixer() {
        let tools = allowed_tools_for_role(&AgentRole::Fixer);
        assert_eq!(tools, allowed_tools_for_role(&AgentRole::Reviewer));
    }

    #[test]
    fn test_allowed_tools_for_role_discovery() {
        let tools = allowed_tools_for_role(&AgentRole::Discovery);
        assert_eq!(tools, &["Read", "Glob", "Grep", "Bash", "Edit", "Write"]);
    }

    #[test]
    fn test_all_roles_have_allowlists() {
        let roles = [
            AgentRole::Scout,
            AgentRole::Query,
            AgentRole::Research,
            AgentRole::Planner,
            AgentRole::Builder,
            AgentRole::Reviewer,
            AgentRole::Fixer,
            AgentRole::PlanReview,
            AgentRole::Discovery,
        ];
        for role in &roles {
            let tools = allowed_tools_for_role(role);
            assert!(
                !tools.is_empty(),
                "role {:?} should have non-empty tool list",
                role
            );
        }
    }

    #[test]
    fn test_scout_lacks_edit_write() {
        let tools = allowed_tools_for_role(&AgentRole::Scout);
        assert!(!tools.contains(&"Edit"));
        assert!(!tools.contains(&"Write"));
    }

    #[test]
    fn test_builder_has_full_access() {
        let tools = allowed_tools_for_role(&AgentRole::Builder);
        for root_tool in ROOT_ALLOWED_TOOLS.split(',') {
            if root_tool == "TodoWrite" {
                continue;
            }
            assert!(
                tools.contains(&root_tool),
                "Builder should have tool '{}' from ROOT_ALLOWED_TOOLS",
                root_tool
            );
        }
    }

    #[test]
    fn test_query_role_uses_allowed_tools_not_skip_permissions() {
        let tools = allowed_tools_for_role(&AgentRole::Query);
        assert_eq!(tools, &["Write"], "Query role should only have Write tool");
        // Verify that with enforce_phase_rbac=true (default), the CLI command
        // uses --allowedTools instead of --dangerously-skip-permissions
        let cmd = crate::tmux::TmuxSession::build_cli_command(
            "claude",
            "test prompt",
            "sonnet",
            tools,
            true,
        );
        assert!(
            cmd.contains("--allowedTools"),
            "Query CLI command must contain --allowedTools, got: {}",
            cmd
        );
        assert!(
            cmd.contains("Write"),
            "Query CLI command must list Write tool, got: {}",
            cmd
        );
        assert!(
            !cmd.contains("--dangerously-skip-permissions"),
            "Query CLI command must NOT contain --dangerously-skip-permissions, got: {}",
            cmd
        );
    }

    // ─── Malformed stream-json input tests ─────────────────────────

    #[test]
    fn malformed_json_missing_type_field() {
        let json = r#"{"message":"no type field here"}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Unparsed
        ));
    }

    #[test]
    fn malformed_json_null_type_field() {
        let json = r#"{"type":null}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Unparsed
        ));
    }

    #[test]
    fn malformed_json_numeric_type_field() {
        let json = r#"{"type":42}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Unparsed
        ));
    }

    #[test]
    fn malformed_json_unknown_type_renders_as_text() {
        let json = r#"{"type":"banana","message":"unexpected"}"#;
        match parse_claude_provider_line(json, "claude") {
            ParsedClaudeLine::Event(AgentOutputEvent::Text(t)) => {
                assert!(
                    t.contains("[banana]"),
                    "expected [banana] label, got: {}",
                    t
                );
            }
            other => panic!("expected Text event with [banana], got {:?}", other),
        }
    }

    #[test]
    fn malformed_assistant_missing_message_field() {
        let json = r#"{"type":"assistant"}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_assistant_missing_content_array() {
        let json = r#"{"type":"assistant","message":{}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_assistant_empty_content_array() {
        let json = r#"{"type":"assistant","message":{"content":[]}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_assistant_content_not_array() {
        let json = r#"{"type":"assistant","message":{"content":"not an array"}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_content_block_missing_type() {
        let json = r#"{"type":"assistant","message":{"content":[{"text":"hello"}]}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_content_block_unknown_type() {
        let json = r#"{"type":"assistant","message":{"content":[{"type":"unknown_block","data":"stuff"}]}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_tool_use_missing_name_defaults_to_unknown() {
        let json = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","input":{"file_path":"/tmp/x"}}]}}"#;
        match parse_claude_provider_line(json, "claude") {
            ParsedClaudeLine::Event(AgentOutputEvent::ToolUse { tool, .. }) => {
                assert_eq!(tool, "unknown");
            }
            other => panic!("expected ToolUse with tool=unknown, got {:?}", other),
        }
    }

    #[test]
    fn malformed_tool_use_missing_input() {
        let json =
            r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read"}]}}"#;
        match parse_claude_provider_line(json, "claude") {
            ParsedClaudeLine::Event(AgentOutputEvent::ToolUse {
                tool,
                input_preview,
            }) => {
                assert_eq!(tool, "Read");
                assert!(
                    input_preview.is_empty(),
                    "expected empty input_preview, got: {}",
                    input_preview
                );
            }
            other => panic!("expected ToolUse with empty input, got {:?}", other),
        }
    }

    #[test]
    fn malformed_text_block_missing_text_field() {
        let json = r#"{"type":"assistant","message":{"content":[{"type":"text"}]}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_text_block_empty_text() {
        let json = r#"{"type":"assistant","message":{"content":[{"type":"text","text":""}]}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_user_message_missing_content() {
        let json = r#"{"type":"user","message":{}}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_user_message_missing_message() {
        let json = r#"{"type":"user"}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_result_missing_everything() {
        LAST_TURN_INPUT_TOKENS.with(|c| c.set(0));
        LAST_RESULT_USAGE.with(|c| c.set(None));
        let json = r#"{"type":"result"}"#;
        let event = parse_stream_event(json);
        // extract_first_string fallback finds "result" (the type value), so this
        // returns Some(Result("result")) rather than None. The key point is no crash.
        assert!(event.is_some(), "minimal result should not crash");
        let usage = LAST_RESULT_USAGE.with(|c| c.take());
        assert!(
            usage.is_some(),
            "LAST_RESULT_USAGE should still be set even with missing fields"
        );
    }

    #[test]
    fn malformed_result_missing_usage() {
        LAST_TURN_INPUT_TOKENS.with(|c| c.set(0));
        LAST_RESULT_USAGE.with(|c| c.set(None));
        let json = r#"{"type":"result","subtype":"success","result":"done"}"#;
        let event = parse_stream_event(json);
        match event {
            Some(AgentOutputEvent::Result(text)) => assert_eq!(text, "done"),
            other => panic!("expected Result(\"done\"), got {:?}", other),
        }
        let usage = LAST_RESULT_USAGE.with(|c| c.take());
        match usage {
            Some(u) => {
                assert_eq!(u.cost_usd, 0.0);
                assert_eq!(u.input_tokens, 0);
                assert_eq!(u.output_tokens, 0);
            }
            None => panic!("LAST_RESULT_USAGE should be Some with zero values"),
        }
    }

    #[test]
    fn malformed_system_empty_body() {
        let json = r#"{"type":"system"}"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Ignore
        ));
    }

    #[test]
    fn malformed_system_error_subtype_no_message() {
        let json = r#"{"type":"system","subtype":"error_something"}"#;
        match parse_claude_provider_line(json, "claude") {
            ParsedClaudeLine::Event(AgentOutputEvent::Stderr(text)) => {
                assert!(
                    text.contains("error_something"),
                    "expected error_something in stderr text, got: {}",
                    text
                );
            }
            other => panic!("expected Stderr with error_something, got {:?}", other),
        }
    }

    #[test]
    fn malformed_truncated_json() {
        let json = r#"{"type":"assistant","message":{"content":[{"type":"te"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Unparsed
        ));
    }

    #[test]
    fn malformed_not_json_at_all() {
        let line = "This is not JSON at all";
        assert!(matches!(
            parse_claude_provider_line(line, "claude"),
            ParsedClaudeLine::Unparsed
        ));
    }

    #[test]
    fn malformed_json_array_instead_of_object() {
        let json = r#"[1, 2, 3]"#;
        assert!(matches!(
            parse_claude_provider_line(json, "claude"),
            ParsedClaudeLine::Unparsed
        ));
    }

    #[test]
    fn malformed_error_event_missing_message() {
        let json = r#"{"type":"error"}"#;
        // extract_string_by_keys falls back to extract_first_string, which finds
        // "error" (the value of "type") via map.values() scan. So the Stderr text
        // is "error", not the fallback message. The key point is no crash.
        match parse_claude_provider_line(json, "claude") {
            ParsedClaudeLine::Event(AgentOutputEvent::Stderr(text)) => {
                assert!(
                    !text.is_empty(),
                    "expected non-empty stderr text for error event",
                );
            }
            other => panic!("expected Stderr event, got {:?}", other),
        }
    }

    #[test]
    fn malformed_rate_limit_null_message() {
        let json = r#"{"type":"rate_limit_event","message":null}"#;
        match parse_stream_event(json) {
            Some(AgentOutputEvent::Text(t)) => {
                assert!(
                    t.contains("API rate limited"),
                    "expected rate limit fallback text, got: {}",
                    t
                );
            }
            other => panic!("expected Text with rate limit message, got {:?}", other),
        }
    }

    #[test]
    fn malformed_codex_not_json() {
        let line = "not json at all";
        assert!(parse_codex_event(line, "gpt-5.4").is_none());
    }

    #[test]
    fn malformed_codex_empty_object() {
        let json = "{}";
        assert!(parse_codex_event(json, "gpt-5.4").is_none());
    }

    #[test]
    fn malformed_tool_result_empty_content() {
        let json = r#"{"type":"user","message":{"content":[{"type":"tool_result","content":"","is_error":false}]}}"#;
        let event = parse_stream_event(json);
        assert!(
            event.is_none(),
            "empty tool_result content should return None"
        );
    }
}

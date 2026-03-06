use anyhow::Result;
use portable_pty::{CommandBuilder, PtySize, native_pty_system};
use serde_json::Value;
use std::io::BufRead;
use std::path::Path;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

use crate::utils::truncate_str;
use tokio::sync::mpsc;

#[derive(Debug, Clone, PartialEq)]
pub enum AgentRole {
    Planner,
    Builder,
    Reviewer,
    Fixer,
    Discovery,
}

impl std::fmt::Display for AgentRole {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            AgentRole::Planner => write!(f, "PLANNER"),
            AgentRole::Builder => write!(f, "BUILDER"),
            AgentRole::Reviewer => write!(f, "REVIEWER"),
            AgentRole::Fixer => write!(f, "FIXER"),
            AgentRole::Discovery => write!(f, "DISCOVERY"),
        }
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
}

pub struct AgentResult {
    pub success: bool,
    #[allow(dead_code)]
    pub exit_code: i32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModelProvider {
    Claude,
    Codex,
}

impl ModelProvider {
    pub fn slug(self) -> &'static str {
        match self {
            ModelProvider::Claude => "claude",
            ModelProvider::Codex => "codex",
        }
    }
}

impl std::fmt::Display for ModelProvider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ModelProvider::Claude => write!(f, "Claude"),
            ModelProvider::Codex => write!(f, "Codex"),
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
}

pub async fn run_provider_session(options: ProviderRunOptions<'_>) -> Result<AgentResult> {
    let timestamp = chrono::Utc::now().format("%Y%m%d-%H%M%S");
    let log_file_path = options
        .log_dir
        .join(format!("studio-{}-{}.jsonl", options.provider.slug(), timestamp));
    let final_message_path = options
        .log_dir
        .join(format!("studio-{}-{}-last.txt", options.provider.slug(), timestamp));
    std::fs::create_dir_all(options.log_dir)?;

    let mut cmd = match options.provider {
        ModelProvider::Claude => {
            let mut cmd = CommandBuilder::new("claude");
            cmd.arg("-p");
            cmd.arg(options.prompt);
            if !options.model.trim().is_empty() {
                cmd.arg("--model");
                cmd.arg(options.model);
            }
            cmd.arg("--dangerously-skip-permissions");
            cmd.arg("--output-format");
            cmd.arg("stream-json");
            cmd.arg("--verbose");
            cmd.env("CLAUDECODE", "");
            cmd
        }
        ModelProvider::Codex => {
            let mut cmd = CommandBuilder::new("codex");
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
            cmd.arg(options.prompt);
            cmd
        }
    };

    cmd.cwd(options.project_dir);

    let pty_system = native_pty_system();
    let pair = pty_system.openpty(PtySize {
        rows: 24,
        cols: 80,
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

    tokio::task::spawn_blocking(move || {
        let tx = output_tx;
        let mut child = child;
        let log_path = log_file_path.clone();
        let model_label = model_name.clone();
        let final_output_path = final_message_path.clone();
        let read_tx = tx.clone();

        let read_thread = std::thread::spawn(move || {
            read_provider_output(reader, &read_tx, &log_path, provider, &model_label);
        });

        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(timeout_secs);
        let mut success = false;

        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    success = status.success();
                    break;
                }
                Ok(None) => {
                    if cancel_flag
                        .as_ref()
                        .is_some_and(|flag| flag.load(Ordering::Relaxed))
                    {
                        let _ = child.kill();
                        let _ = child.wait();
                        let _ = tx.send(AgentOutputEvent::Stderr(format!(
                            "{} cancelled by studio shutdown",
                            provider
                        )));
                        break;
                    }
                    if std::time::Instant::now() >= deadline {
                        let _ = child.kill();
                        let _ = child.wait();
                        let _ = tx.send(AgentOutputEvent::Stderr(format!(
                            "{} timed out after {}s",
                            provider, timeout_secs
                        )));
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(500));
                }
                Err(err) => {
                    let _ = tx.send(AgentOutputEvent::Stderr(format!(
                        "{} failed while waiting on process: {}",
                        provider, err
                    )));
                    break;
                }
            }
        }

        drop(master);
        let _ = read_thread.join();

        if provider == ModelProvider::Codex {
            if let Ok(text) = std::fs::read_to_string(&final_output_path) {
                if !text.trim().is_empty() {
                    let _ = tx.send(AgentOutputEvent::Result(text));
                }
            }
        }

        let _ = result_tx.send(success);
    });

    let success = result_rx.await.unwrap_or(false);
    Ok(AgentResult {
        success,
        exit_code: if success { 0 } else { 1 },
    })
}

/// Spawn a claude CLI agent inside a PTY.
///
/// Node.js block-buffers stdout when it detects a pipe or file (16KB chunks).
/// By spawning inside a PTY, Node.js sees a terminal and uses line-buffered
/// (synchronous) writes — each JSON event flushes immediately, giving us
/// true real-time streaming in the TUI.
pub async fn run_agent(
    role: &AgentRole,
    model: &str,
    prompt: &str,
    project_dir: &Path,
    output_tx: mpsc::UnboundedSender<AgentOutputEvent>,
    log_dir: &Path,
    allowed_tools: Option<&[&str]>,
    timeout_secs: u64,
) -> Result<AgentResult> {
    let timestamp = chrono::Utc::now().format("%Y%m%d-%H%M%S");
    let log_file_path = log_dir.join(format!("{}-{}.jsonl", role, timestamp));
    std::fs::create_dir_all(log_dir)?;

    // Build command for PTY execution
    let mut cmd = CommandBuilder::new("claude");
    cmd.arg("-p");
    cmd.arg(prompt);
    cmd.arg("--model");
    cmd.arg(model);
    cmd.arg("--dangerously-skip-permissions");
    cmd.arg("--output-format");
    cmd.arg("stream-json");
    cmd.arg("--verbose");
    if let Some(tools) = allowed_tools {
        cmd.arg("--tools");
        cmd.arg(tools.join(","));
    }
    cmd.cwd(project_dir);

    // Prevent nested Claude detection — set on the command, not process-wide
    cmd.env("CLAUDECODE", "");

    // Open a PTY — this is the key to real-time streaming.
    // Node.js checks if stdout is a TTY (via isatty()). When it is,
    // process.stdout.write() is synchronous and line-buffered.
    let pty_system = native_pty_system();
    let pair = pty_system.openpty(PtySize {
        rows: 24,
        cols: 80,
        pixel_width: 0,
        pixel_height: 0,
    })?;

    let child = pair.slave.spawn_command(cmd)?;
    drop(pair.slave); // Release slave; child has its own fd copy

    let reader = pair.master.try_clone_reader()?;
    let master = pair.master; // Keep alive until child exits

    // Use oneshot channel to get result back from blocking thread
    let (result_tx, result_rx) = tokio::sync::oneshot::channel();

    let role_name = role.to_string();
    let model_name = model.to_string();
    tokio::task::spawn_blocking(move || {
        let tx = output_tx;
        let mut child = child;

        // Spawn reader thread — reads PTY output line by line
        let model_label = model_name.clone();
        let read_thread = std::thread::spawn(move || {
            read_pty_output(reader, &tx, &log_file_path, &model_label);
        });

        // Wait for child process to exit with timeout
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(timeout_secs);
        let mut success = false;

        loop {
            // Check if child has exited (non-blocking poll via short sleep + try)
            match child.try_wait() {
                Ok(Some(status)) => {
                    success = status.success();
                    break;
                }
                Ok(None) => {
                    // Still running — check timeout
                    if std::time::Instant::now() >= deadline {
                        // Timeout — kill the child process
                        let _ = child.kill();
                        let _ = child.wait(); // Reap
                        eprintln!(
                            "[foundry] Agent {} timed out after {}s — killed",
                            role_name, timeout_secs
                        );
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(500));
                }
                Err(_) => break,
            }
        }

        // Drop master to close PTY — triggers EOF on reader
        drop(master);

        // Wait for reader to drain remaining output
        let _ = read_thread.join();

        let _ = result_tx.send(success);
    });

    let success = result_rx.await.unwrap_or(false);

    Ok(AgentResult {
        success,
        exit_code: if success { 0 } else { 1 },
    })
}

/// Read PTY output line by line, parse stream-json events, send to TUI.
/// Also writes raw lines to the log file.
fn read_pty_output(
    reader: Box<dyn std::io::Read + Send>,
    tx: &mpsc::UnboundedSender<AgentOutputEvent>,
    log_path: &Path,
    model_name: &str,
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

                // Persist raw output to log file
                if let Some(ref mut f) = log_file {
                    use std::io::Write;
                    let _ = writeln!(f, "{}", line);
                }

                // Try to parse as a stream-json event
                match parse_stream_event(line) {
                    Some(event) => {
                        if tx.send(event).is_err() {
                            return; // Channel closed
                        }
                    }
                    None => {
                        // Check if it's a JSON event type we don't handle
                        if let Ok(v) = serde_json::from_str::<Value>(line) {
                            if let Some(t) = v.get("type").and_then(|t| t.as_str()) {
                                // Skip turn-marker events that have no displayable content
                                if matches!(t, "user" | "system") {
                                    continue;
                                }
                                let sub = v
                                    .get("subtype")
                                    .and_then(|s| s.as_str())
                                    .unwrap_or("");
                                let display_type = if t == "assistant" {
                                    model_name
                                } else {
                                    t
                                };
                                let label = if sub.is_empty() {
                                    format!("[{}]", display_type)
                                } else {
                                    format!("[{}:{}]", display_type, sub)
                                };
                                let _ = tx.send(AgentOutputEvent::Text(label));
                            }
                        } else {
                            // Non-JSON line (stderr merged through PTY).
                            // Strip ANSI escape sequences and drop lines that are
                            // purely terminal control noise.
                            if !line.is_empty() {
                                let cleaned = strip_ansi(line);
                                if !cleaned.is_empty() {
                                    let _ = tx.send(AgentOutputEvent::Stderr(cleaned));
                                }
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

                if let Some(ref mut f) = log_file {
                    use std::io::Write;
                    let _ = writeln!(f, "{}", line);
                }

                let parsed = match provider {
                    ModelProvider::Claude => parse_claude_provider_line(line, model_name),
                    ModelProvider::Codex => parse_codex_event(line, model_name),
                };

                if let Some(event) = parsed {
                    if tx.send(event).is_err() {
                        return;
                    }
                    continue;
                }

                let cleaned = strip_ansi(line);
                if !cleaned.is_empty() && tx.send(AgentOutputEvent::Stderr(cleaned)).is_err() {
                    return;
                }
            }
            Err(_) => break,
        }
    }
}

fn parse_claude_provider_line(line: &str, model_name: &str) -> Option<AgentOutputEvent> {
    if let Some(event) = parse_stream_event(line) {
        return Some(event);
    }

    if let Ok(v) = serde_json::from_str::<Value>(line) {
        if let Some(t) = v.get("type").and_then(|t| t.as_str()) {
            if matches!(t, "user" | "system") {
                return None;
            }
            let sub = v.get("subtype").and_then(|s| s.as_str()).unwrap_or("");
            let display_type = if t == "assistant" { model_name } else { t };
            let label = if sub.is_empty() {
                format!("[{}]", display_type)
            } else {
                format!("[{}:{}]", display_type, sub)
            };
            return Some(AgentOutputEvent::Text(label));
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
                &["input", "arguments", "command", "cmd", "preview", "description"],
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
        if let Some(text) = extract_string_by_keys(
            &v,
            &["result", "message", "content", "text", "summary"],
        ) {
            if !text.is_empty() {
                return Some(AgentOutputEvent::Result(text));
            }
        }
    }

    if let Some(text) = extract_string_by_keys(
        &v,
        &[
            "text",
            "delta",
            "message",
            "content",
            "summary",
            "output",
            "reason",
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
                model_name,
                kind,
                text
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
                "text",
                "delta",
                "message",
                "content",
                "output",
                "summary",
                "reason",
                "error",
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
fn parse_stream_event(line: &str) -> Option<AgentOutputEvent> {
    let v: Value = serde_json::from_str(line).ok()?;

    match v.get("type")?.as_str()? {
        // Assistant message — contains text and/or tool_use content blocks
        "assistant" => {
            let content = v.get("message")?.get("content")?.as_array()?;

            for block in content {
                match block.get("type").and_then(|t| t.as_str()) {
                    Some("text") => {
                        if let Some(text) = block.get("text").and_then(|t| t.as_str()) {
                            if !text.is_empty() {
                                return Some(AgentOutputEvent::Text(text.to_string()));
                            }
                        }
                    }
                    Some("tool_use") => {
                        let tool = block
                            .get("name")
                            .and_then(|n| n.as_str())
                            .unwrap_or("unknown")
                            .to_string();

                        let input_preview = if let Some(input) = block.get("input") {
                            match tool.as_str() {
                                "Read" => input
                                    .get("file_path")
                                    .and_then(|p| p.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                "Write" => input
                                    .get("file_path")
                                    .and_then(|p| p.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                "Edit" => input
                                    .get("file_path")
                                    .and_then(|p| p.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                "Bash" => input
                                    .get("command")
                                    .and_then(|c| c.as_str())
                                    .map(|c| {
                                        if c.len() > 80 {
                                            format!("{}...", truncate_str(c, 80))
                                        } else {
                                            c.to_string()
                                        }
                                    })
                                    .unwrap_or_default(),
                                "Glob" => input
                                    .get("pattern")
                                    .and_then(|p| p.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                "Grep" => input
                                    .get("pattern")
                                    .and_then(|p| p.as_str())
                                    .unwrap_or("")
                                    .to_string(),
                                _ => {
                                    let s = input.to_string();
                                    if s.len() > 100 {
                                        format!("{}...", truncate_str(&s, 100))
                                    } else {
                                        s
                                    }
                                }
                            }
                        } else {
                            String::new()
                        };

                        return Some(AgentOutputEvent::ToolUse {
                            tool,
                            input_preview,
                        });
                    }
                    _ => {}
                }
            }
            None
        }

        // Tool result
        "tool_result" | "tool_output" => {
            let output = v
                .get("output")
                .or_else(|| v.get("content"))
                .and_then(|o| o.as_str())
                .unwrap_or("")
                .to_string();

            if output.is_empty() {
                return None;
            }

            let preview = if output.len() > 200 {
                format!("{}...", truncate_str(&output, 200))
            } else {
                output
            };

            Some(AgentOutputEvent::ToolResult {
                output_preview: preview,
            })
        }

        // Final result
        "result" => {
            let text = v
                .get("result")
                .and_then(|r| r.as_str())
                .unwrap_or("")
                .to_string();

            if !text.is_empty() {
                Some(AgentOutputEvent::Result(text))
            } else {
                None
            }
        }

        // Rate limit event — Claude CLI got throttled by the API.
        // Surface it so the TUI shows what's happening instead of a raw label.
        "rate_limit_event" => {
            let msg = v
                .get("message")
                .and_then(|m| m.as_str())
                .unwrap_or("API rate limited — waiting for retry...");
            Some(AgentOutputEvent::Text(format!("[rate limited] {}", msg)))
        }

        _ => None,
    }
}

/// Strip ANSI escape sequences and C0 control characters from PTY output.
/// Handles CSI (`\x1b[...X`), OSC (`\x1b]...BEL` / `\x1b]...\x1b\\`),
/// simple two-byte escapes (`\x1b X`), and stray control chars (BEL, etc.).
/// Returns the cleaned string. Empty after trim means the line was pure noise.
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
            Some(AgentOutputEvent::ToolUse { tool, input_preview }) => {
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
}

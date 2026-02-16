use anyhow::Result;
use portable_pty::{CommandBuilder, PtySize, native_pty_system};
use serde_json::Value;
use std::io::BufRead;
use std::path::Path;

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

    tokio::task::spawn_blocking(move || {
        let tx = output_tx;
        let mut child = child;

        // Spawn reader thread — reads PTY output line by line
        let read_thread = std::thread::spawn(move || {
            read_pty_output(reader, &tx, &log_file_path);
        });

        // Wait for child process to exit
        let status = child.wait();

        // Drop master to close PTY — triggers EOF on reader
        drop(master);

        // Wait for reader to drain remaining output
        let _ = read_thread.join();

        let success = status.map(|s| s.success()).unwrap_or(false);
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
                                let label = if sub.is_empty() {
                                    format!("[{}]", t)
                                } else {
                                    format!("[{}:{}]", t, sub)
                                };
                                let _ = tx.send(AgentOutputEvent::Text(label));
                            }
                        } else {
                            // Non-JSON line (stderr merged through PTY)
                            if !line.is_empty() {
                                let _ = tx.send(AgentOutputEvent::Stderr(line.to_string()));
                            }
                        }
                    }
                }
            }
            Err(_) => break,
        }
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

        _ => None,
    }
}

//! GitHub Copilot provider for Context Foundry (experimental).
//!
//! Rides the user's existing GitHub Copilot subscription via the `gh` CLI
//! OAuth token — no separate API key required. Calls the GitHub Copilot
//! chat completions API in an agentic tool-calling loop.
//!
//! EXPERIMENTAL: The internal token endpoint and chat completions API used
//! here are not a stable public contract. This provider may break without
//! notice if GitHub changes their internal API surface.

use anyhow::{anyhow, Context as _, Result};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::SystemTime;
use tokio::sync::mpsc;

use crate::agent::{AgentExitKind, AgentOutputEvent, AgentResult};

// ─── API constants ──────────────────────────────────────────────────────────

const COPILOT_TOKEN_URL: &str = "https://api.github.com/copilot_internal/v2/token";
const COPILOT_CHAT_URL: &str = "https://api.githubcopilot.com/chat/completions";
const EDITOR_VERSION: &str = "vscode/1.85.0";
const COPILOT_INTEGRATION_ID: &str = "vscode-chat";
const USER_AGENT_STR: &str = "context-foundry/3.0.0";
const DEFAULT_MODEL: &str = "gpt-4o";
/// Refresh the Copilot token if it expires within this many seconds.
const TOKEN_REFRESH_MARGIN_SECS: u64 = 300;
/// Default Bash tool timeout.
const TOOL_BASH_TIMEOUT_SECS: u64 = 120;
/// Maximum lines returned by Read without an explicit limit.
const MAX_FILE_READ_LINES: usize = 2000;
/// Hard cap on characters returned by any single tool call.
const MAX_TOOL_OUTPUT_CHARS: usize = 50_000;
/// Guard against infinite tool-call loops.
const MAX_AGENTIC_TURNS: usize = 50;
/// Maximum grep result lines before truncation.
const MAX_GREP_RESULTS: usize = 500;

// ─── Public types ───────────────────────────────────────────────────────────

pub struct GhCopilotOptions<'a> {
    pub model: &'a str,
    pub prompt: &'a str,
    pub system_directives: &'a str,
    pub project_dir: &'a Path,
    pub output_tx: mpsc::UnboundedSender<AgentOutputEvent>,
    pub log_dir: &'a Path,
    pub timeout_secs: u64,
    pub allowed_tools: &'a [&'a str],
    pub cancel_flag: Option<Arc<AtomicBool>>,
}

// ─── Token management ───────────────────────────────────────────────────────

#[derive(Clone)]
struct CopilotToken {
    token: String,
    expires_at: SystemTime,
}

impl CopilotToken {
    fn needs_refresh(&self) -> bool {
        match self.expires_at.duration_since(SystemTime::now()) {
            Ok(remaining) => remaining.as_secs() < TOKEN_REFRESH_MARGIN_SECS,
            Err(_) => true,
        }
    }
}

fn get_github_token() -> Result<String> {
    let output = std::process::Command::new("gh")
        .args(["auth", "token"])
        .output()
        .context("gh CLI not found. Install with: winget install GitHub.cli (or brew install gh)")?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!(
            "gh auth token failed: {}. Run: gh auth login",
            stderr.trim()
        ));
    }
    let token = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if token.is_empty() {
        return Err(anyhow!(
            "gh auth token returned empty. Run: gh auth login --web -h github.com"
        ));
    }
    Ok(token)
}

async fn fetch_copilot_token(
    client: &reqwest::Client,
    github_token: &str,
) -> Result<CopilotToken> {
    let resp = client
        .get(COPILOT_TOKEN_URL)
        .header("Authorization", format!("token {}", github_token))
        .header("Editor-Version", EDITOR_VERSION)
        .header("Copilot-Integration-Id", COPILOT_INTEGRATION_ID)
        .header("User-Agent", USER_AGENT_STR)
        .header("Accept", "application/json")
        .send()
        .await
        .context("Failed to reach GitHub API for Copilot token")?;

    let status = resp.status();
    if status == 401 || status == 403 {
        return Err(anyhow!(
            "GitHub Copilot access denied (HTTP {}). \
             Make sure your account has an active Copilot subscription.",
            status
        ));
    }
    if !status.is_success() {
        let body = resp.text().await.unwrap_or_default();
        return Err(anyhow!(
            "GitHub Copilot token exchange failed (HTTP {}): {}",
            status,
            body
        ));
    }

    let body: Value = resp
        .json()
        .await
        .context("Failed to parse Copilot token response")?;

    let token = body["token"]
        .as_str()
        .ok_or_else(|| anyhow!("No 'token' field in Copilot token response"))?
        .to_string();

    let expires_at = body["expires_at"]
        .as_str()
        .and_then(parse_iso8601)
        .unwrap_or_else(|| {
            // Default: 30 minutes from now
            SystemTime::now() + std::time::Duration::from_secs(1800)
        });

    Ok(CopilotToken { token, expires_at })
}

fn parse_iso8601(s: &str) -> Option<SystemTime> {
    chrono::DateTime::parse_from_rfc3339(s)
        .ok()
        .and_then(|dt| {
            let secs = dt.timestamp();
            if secs < 0 {
                return None;
            }
            SystemTime::UNIX_EPOCH
                .checked_add(std::time::Duration::from_secs(secs as u64))
        })
}

// ─── Path safety ────────────────────────────────────────────────────────────

/// Resolve `requested` relative to `project_dir` and reject anything that
/// escapes the project root (e.g. `../../etc/passwd`).
fn safe_path(project_dir: &Path, requested: &str) -> Result<PathBuf> {
    let raw = if Path::new(requested).is_absolute() {
        PathBuf::from(requested)
    } else {
        project_dir.join(requested)
    };

    let normalized = normalize_path(&raw);
    let proj_normalized = normalize_path(project_dir);

    if !normalized.starts_with(&proj_normalized) {
        return Err(anyhow!(
            "Path '{}' is outside the project directory",
            requested
        ));
    }
    Ok(normalized)
}

/// Resolve `..` and `.` components without requiring the path to exist.
fn normalize_path(p: &Path) -> PathBuf {
    // Prefer OS canonicalization (resolves symlinks, handles Windows \\?\).
    if let Ok(c) = dunce::canonicalize(p) {
        return c;
    }
    // Fallback for paths that don't exist yet (e.g. Write to new file).
    let mut out = Vec::new();
    for comp in p.components() {
        match comp {
            std::path::Component::ParentDir => {
                out.pop();
            }
            std::path::Component::CurDir => {}
            c => out.push(c),
        }
    }
    out.iter().collect()
}

fn truncate_output(s: &str) -> String {
    if s.len() > MAX_TOOL_OUTPUT_CHARS {
        format!(
            "{}…[truncated {} chars]",
            &s[..MAX_TOOL_OUTPUT_CHARS],
            s.len() - MAX_TOOL_OUTPUT_CHARS
        )
    } else {
        s.to_string()
    }
}

// ─── Tool definitions ───────────────────────────────────────────────────────

fn build_tool_definitions(allowed_tools: &[&str]) -> Vec<Value> {
    let mut defs = Vec::new();
    for &tool in allowed_tools {
        match tool {
            "Bash" => defs.push(json!({
                "type": "function",
                "function": {
                    "name": "Bash",
                    "description": "Execute a shell command in the project directory. Use for build, test, git, and filesystem operations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to run"
                            },
                            "timeout": {
                                "type": "number",
                                "description": "Timeout in seconds (default: 120)"
                            }
                        },
                        "required": ["command"]
                    }
                }
            })),
            "Read" => defs.push(json!({
                "type": "function",
                "function": {
                    "name": "Read",
                    "description": "Read a file's contents. Has a 10,000-token limit per call. \
                                    For large files use Grep to find sections, then Read with offset+limit.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file (relative to project root)"
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Line number to start reading from (0-indexed)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of lines to read"
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            })),
            "Write" => defs.push(json!({
                "type": "function",
                "function": {
                    "name": "Write",
                    "description": "Write content to a file (creates or overwrites). Parent directories are created automatically.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write"
                            }
                        },
                        "required": ["file_path", "content"]
                    }
                }
            })),
            "Edit" => defs.push(json!({
                "type": "function",
                "function": {
                    "name": "Edit",
                    "description": "Edit a file by replacing one exact occurrence of old_str with new_str. \
                                    old_str must match exactly and must be unique in the file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file"
                            },
                            "old_str": {
                                "type": "string",
                                "description": "Exact string to replace (must be unique in file)"
                            },
                            "new_str": {
                                "type": "string",
                                "description": "Replacement string"
                            }
                        },
                        "required": ["file_path", "old_str", "new_str"]
                    }
                }
            })),
            "Glob" => defs.push(json!({
                "type": "function",
                "function": {
                    "name": "Glob",
                    "description": "Find files matching a glob pattern (e.g. '**/*.rs', 'src/**/*.ts').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Glob pattern to match"
                            },
                            "path": {
                                "type": "string",
                                "description": "Directory to search in (default: project root)"
                            }
                        },
                        "required": ["pattern"]
                    }
                }
            })),
            "Grep" => defs.push(json!({
                "type": "function",
                "function": {
                    "name": "Grep",
                    "description": "Search for a regex pattern in files. Returns file:line: text matches.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Regex pattern to search for"
                            },
                            "path": {
                                "type": "string",
                                "description": "Directory or file to search in (default: project root)"
                            },
                            "glob": {
                                "type": "string",
                                "description": "File glob filter (e.g. '*.rs', '*.ts')"
                            },
                            "case_insensitive": {
                                "type": "boolean",
                                "description": "Case-insensitive search (default: false)"
                            }
                        },
                        "required": ["pattern"]
                    }
                }
            })),
            "WebFetch" => defs.push(json!({
                "type": "function",
                "function": {
                    "name": "WebFetch",
                    "description": "Fetch a URL and return its text content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to fetch"
                            },
                            "prompt": {
                                "type": "string",
                                "description": "Optional: describe what information you are looking for"
                            }
                        },
                        "required": ["url"]
                    }
                }
            })),
            // NotebookEdit, TodoWrite, WebSearch, AskUserQuestion are not
            // implemented in this provider. Silently omit them from the
            // tool surface so the model never tries to call them.
            _ => {}
        }
    }
    defs
}

// ─── Tool execution ─────────────────────────────────────────────────────────

async fn execute_tool(
    name: &str,
    args: &Value,
    project_dir: &Path,
    client: &reqwest::Client,
) -> String {
    match name {
        "Bash" => {
            let Some(command) = args["command"].as_str() else {
                return "Error: missing 'command' parameter".to_string();
            };
            let timeout_secs = args["timeout"].as_u64().unwrap_or(TOOL_BASH_TIMEOUT_SECS);
            truncate_output(&run_bash(command, project_dir, timeout_secs).await)
        }
        "Read" => {
            let Some(file_path) = args["file_path"].as_str() else {
                return "Error: missing 'file_path' parameter".to_string();
            };
            let offset = args["offset"].as_u64().unwrap_or(0) as usize;
            let limit = args["limit"].as_u64().map(|n| n as usize);
            match read_file(project_dir, file_path, offset, limit) {
                Ok(c) => truncate_output(&c),
                Err(e) => format!("Error: {}", e),
            }
        }
        "Write" => {
            let Some(file_path) = args["file_path"].as_str() else {
                return "Error: missing 'file_path' parameter".to_string();
            };
            let content = args["content"].as_str().unwrap_or("");
            match write_file(project_dir, file_path, content) {
                Ok(()) => "File written successfully".to_string(),
                Err(e) => format!("Error: {}", e),
            }
        }
        "Edit" => {
            let Some(file_path) = args["file_path"].as_str() else {
                return "Error: missing 'file_path' parameter".to_string();
            };
            let old_str = args["old_str"].as_str().unwrap_or("");
            let new_str = args["new_str"].as_str().unwrap_or("");
            match edit_file(project_dir, file_path, old_str, new_str) {
                Ok(()) => "File edited successfully".to_string(),
                Err(e) => format!("Error: {}", e),
            }
        }
        "Glob" => {
            let Some(pattern) = args["pattern"].as_str() else {
                return "Error: missing 'pattern' parameter".to_string();
            };
            let search_dir = args["path"]
                .as_str()
                .map(|p| project_dir.join(p))
                .unwrap_or_else(|| project_dir.to_path_buf());
            match glob_files(&search_dir, pattern, project_dir) {
                Ok(files) if files.is_empty() => "No files found matching pattern".to_string(),
                Ok(files) => files.join("\n"),
                Err(e) => format!("Error: {}", e),
            }
        }
        "Grep" => {
            let Some(pattern) = args["pattern"].as_str() else {
                return "Error: missing 'pattern' parameter".to_string();
            };
            let search_path = args["path"]
                .as_str()
                .map(|p| project_dir.join(p))
                .unwrap_or_else(|| project_dir.to_path_buf());
            let glob_filter = args["glob"].as_str();
            let case_insensitive = args["case_insensitive"].as_bool().unwrap_or(false);
            match grep_files(pattern, &search_path, glob_filter, case_insensitive, project_dir) {
                Ok(results) if results.is_empty() => "No matches found".to_string(),
                Ok(results) => truncate_output(&results.join("\n")),
                Err(e) => format!("Error: {}", e),
            }
        }
        "WebFetch" => {
            let Some(url) = args["url"].as_str() else {
                return "Error: missing 'url' parameter".to_string();
            };
            match fetch_url(client, url).await {
                Ok(content) => truncate_output(&content),
                Err(e) => format!("Error fetching {}: {}", url, e),
            }
        }
        _ => format!("Error: tool '{}' is not available in the GhCopilot provider", name),
    }
}

async fn run_bash(command: &str, cwd: &Path, timeout_secs: u64) -> String {
    #[cfg(windows)]
    let mut cmd = {
        let mut c = tokio::process::Command::new("cmd");
        c.args(["/c", command]);
        c
    };
    #[cfg(not(windows))]
    let mut cmd = {
        let mut c = tokio::process::Command::new("sh");
        c.args(["-c", command]);
        c
    };

    cmd.current_dir(cwd)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());

    let deadline = std::time::Duration::from_secs(timeout_secs);
    match tokio::time::timeout(deadline, cmd.output()).await {
        Ok(Ok(out)) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            let stderr = String::from_utf8_lossy(&out.stderr);
            let combined = match (stdout.is_empty(), stderr.is_empty()) {
                (false, false) => format!("{}\n{}", stdout, stderr),
                (false, true) => stdout.into_owned(),
                (true, false) => stderr.into_owned(),
                (true, true) => {
                    if out.status.success() {
                        "(no output)".to_string()
                    } else {
                        format!("(exit {})", out.status.code().unwrap_or(-1))
                    }
                }
            };
            combined
        }
        Ok(Err(e)) => format!("Failed to execute command: {}", e),
        Err(_) => format!("Command timed out after {}s", timeout_secs),
    }
}

fn read_file(
    project_dir: &Path,
    file_path: &str,
    offset: usize,
    limit: Option<usize>,
) -> Result<String> {
    let path = safe_path(project_dir, file_path)?;
    let content =
        std::fs::read_to_string(&path).with_context(|| format!("Cannot read '{}'", file_path))?;

    let lines: Vec<&str> = content.lines().collect();
    let start = offset.min(lines.len());
    let cap = limit.unwrap_or(MAX_FILE_READ_LINES);
    let end = (start + cap).min(lines.len());

    let result = lines[start..end].join("\n");
    if end < lines.len() {
        Ok(format!(
            "{}\n…[{} more lines — use offset={} to continue]",
            result,
            lines.len() - end,
            end
        ))
    } else {
        Ok(result)
    }
}

fn write_file(project_dir: &Path, file_path: &str, content: &str) -> Result<()> {
    let path = safe_path(project_dir, file_path)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("Cannot create directories for '{}'", file_path))?;
    }
    std::fs::write(&path, content).with_context(|| format!("Cannot write '{}'", file_path))
}

fn edit_file(
    project_dir: &Path,
    file_path: &str,
    old_str: &str,
    new_str: &str,
) -> Result<()> {
    let path = safe_path(project_dir, file_path)?;
    let content = std::fs::read_to_string(&path)
        .with_context(|| format!("Cannot read '{}' for editing", file_path))?;

    let count = content.matches(old_str).count();
    if count == 0 {
        return Err(anyhow!(
            "old_str not found in '{}'. The string must match exactly.",
            file_path
        ));
    }
    if count > 1 {
        return Err(anyhow!(
            "old_str found {} times in '{}'. Add more context to make it unique.",
            count,
            file_path
        ));
    }

    let new_content = content.replacen(old_str, new_str, 1);
    std::fs::write(&path, new_content)
        .with_context(|| format!("Cannot write '{}' after edit", file_path))
}

fn glob_files(search_dir: &Path, pattern: &str, project_dir: &Path) -> Result<Vec<String>> {
    let glob_pat = glob::Pattern::new(pattern)
        .with_context(|| format!("Invalid glob pattern: '{}'", pattern))?;

    let proj_normalized = normalize_path(project_dir);
    let mut results = Vec::new();

    let walker = walkdir::WalkDir::new(search_dir)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| !should_skip_dir(e.file_name().to_str().unwrap_or("")));

    for entry in walker.filter_map(|e| e.ok()) {
        if !entry.file_type().is_file() {
            continue;
        }
        let path = entry.path();
        let file_name = entry.file_name().to_str().unwrap_or("");
        let rel = path
            .strip_prefix(&proj_normalized)
            .unwrap_or(path)
            .to_string_lossy()
            .replace('\\', "/");

        if glob_pat.matches(file_name) || glob_pat.matches(&rel) {
            results.push(rel);
        }
    }

    results.sort();
    Ok(results)
}

fn grep_files(
    pattern: &str,
    search_path: &Path,
    glob_filter: Option<&str>,
    case_insensitive: bool,
    project_dir: &Path,
) -> Result<Vec<String>> {
    use regex::Regex;
    let re = if case_insensitive {
        Regex::new(&format!("(?i){}", pattern))
    } else {
        Regex::new(pattern)
    }
    .with_context(|| format!("Invalid regex: '{}'", pattern))?;

    let glob_pat = glob_filter
        .map(|g| {
            glob::Pattern::new(g).with_context(|| format!("Invalid glob filter: '{}'", g))
        })
        .transpose()?;

    let proj_normalized = normalize_path(project_dir);
    let mut results = Vec::new();

    let walker = walkdir::WalkDir::new(search_path)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| !should_skip_dir(e.file_name().to_str().unwrap_or("")));

    'outer: for entry in walker.filter_map(|e| e.ok()) {
        if !entry.file_type().is_file() {
            continue;
        }
        let path = entry.path();
        let file_name = entry.file_name().to_str().unwrap_or("");

        if let Some(ref gp) = glob_pat {
            if !gp.matches(file_name) {
                continue;
            }
        }

        let rel = path
            .strip_prefix(&proj_normalized)
            .unwrap_or(path)
            .to_string_lossy()
            .replace('\\', "/");

        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(_) => continue, // skip binary/unreadable files
        };

        for (line_no, line) in content.lines().enumerate() {
            if re.is_match(line) {
                results.push(format!("{}:{}: {}", rel, line_no + 1, line));
                if results.len() >= MAX_GREP_RESULTS {
                    results.push(format!(
                        "…[truncated at {} results]",
                        MAX_GREP_RESULTS
                    ));
                    break 'outer;
                }
            }
        }
    }

    Ok(results)
}

/// Returns true for directory names that should be skipped during file walks.
fn should_skip_dir(name: &str) -> bool {
    matches!(
        name,
        "node_modules" | "target" | ".git" | "dist" | "build" | ".next" | "__pycache__"
    )
}

async fn fetch_url(client: &reqwest::Client, url: &str) -> Result<String> {
    let resp = client
        .get(url)
        .header("User-Agent", USER_AGENT_STR)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .with_context(|| format!("Cannot reach '{}'", url))?;
    Ok(resp.text().await?)
}

// ─── Copilot chat completions ────────────────────────────────────────────────

struct CopilotResponse {
    message: Value,
    finish_reason: String,
    prompt_tokens: u64,
    completion_tokens: u64,
}

const AUTH_ERROR_SENTINEL: &str = "copilot_auth_expired";

async fn call_copilot(
    client: &reqwest::Client,
    token: &str,
    model: &str,
    messages: &[Value],
    tools: &[Value],
) -> Result<CopilotResponse> {
    let mut body = json!({
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "stream": false
    });
    if !tools.is_empty() {
        body["tools"] = json!(tools);
        body["tool_choice"] = json!("auto");
    }

    let resp = client
        .post(COPILOT_CHAT_URL)
        .header("Authorization", format!("Bearer {}", token))
        .header("Content-Type", "application/json")
        .header("Copilot-Integration-Id", COPILOT_INTEGRATION_ID)
        .header("Editor-Version", EDITOR_VERSION)
        .header("User-Agent", USER_AGENT_STR)
        .header("Accept", "application/json")
        .json(&body)
        .send()
        .await
        .context("Failed to reach GitHub Copilot API")?;

    let status = resp.status();
    if status == 401 || status == 403 {
        // Signal to caller to refresh token and retry.
        return Err(anyhow!(AUTH_ERROR_SENTINEL));
    }
    if status == 429 {
        return Err(anyhow!(
            "Rate limited by GitHub Copilot API — wait a moment and try again"
        ));
    }
    if !status.is_success() {
        let body_text = resp.text().await.unwrap_or_default();
        return Err(anyhow!(
            "GitHub Copilot API error (HTTP {}): {}",
            status,
            body_text
        ));
    }

    let json: Value = resp
        .json()
        .await
        .context("Failed to parse Copilot API response as JSON")?;

    let prompt_tokens = json["usage"]["prompt_tokens"].as_u64().unwrap_or(0);
    let completion_tokens = json["usage"]["completion_tokens"].as_u64().unwrap_or(0);
    let finish_reason = json["choices"][0]["finish_reason"]
        .as_str()
        .unwrap_or("stop")
        .to_string();
    let message = json["choices"][0]["message"].clone();

    Ok(CopilotResponse {
        message,
        finish_reason,
        prompt_tokens,
        completion_tokens,
    })
}

/// Returns the approximate context window size for the given model slug.
fn model_context_window(model: &str) -> u64 {
    let lower = model.to_ascii_lowercase();
    if lower.contains("claude") || lower.starts_with("o1") || lower.starts_with("o3") {
        200_000
    } else {
        128_000
    }
}

// ─── Main session entry point ────────────────────────────────────────────────

pub async fn run_ghcopilot_session(options: GhCopilotOptions<'_>) -> Result<AgentResult> {
    let tx = &options.output_tx;
    let project_dir = options.project_dir;
    let model = if options.model.trim().is_empty() {
        DEFAULT_MODEL
    } else {
        options.model
    };

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .context("Failed to build HTTP client")?;

    let _ = tx.send(AgentOutputEvent::Stderr(
        "[ghcopilot] EXPERIMENTAL provider — API stability not guaranteed".to_string(),
    ));

    // Acquire GitHub OAuth token via gh CLI.
    let github_token = match get_github_token() {
        Ok(t) => t,
        Err(e) => {
            let msg = format!("[ghcopilot] {}", e);
            let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
            return Ok(AgentResult {
                success: false,
                exit_code: 1,
                exit_kind: AgentExitKind::Failed,
                failure_message: Some(msg),
            });
        }
    };

    // Exchange for a Copilot API token.
    let mut copilot_token = match fetch_copilot_token(&client, &github_token).await {
        Ok(t) => t,
        Err(e) => {
            let msg = format!("[ghcopilot] {}", e);
            let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
            return Ok(AgentResult {
                success: false,
                exit_code: 1,
                exit_kind: AgentExitKind::Failed,
                failure_message: Some(msg),
            });
        }
    };

    // Set up log file.
    std::fs::create_dir_all(options.log_dir)?;
    let timestamp = chrono::Utc::now().format("%Y%m%d-%H%M%S");
    let log_path = options
        .log_dir
        .join(format!("studio-ghcopilot-{}.jsonl", timestamp));
    let mut log_file = std::fs::File::create(&log_path).ok();

    let _ = tx.send(AgentOutputEvent::Text(format!(
        "[ghcopilot] model: {}",
        model
    )));

    let tool_defs = build_tool_definitions(options.allowed_tools);
    let system_content = options.system_directives.trim().to_string();

    let mut messages: Vec<Value> = vec![
        json!({"role": "system", "content": system_content}),
        json!({"role": "user",   "content": options.prompt}),
    ];

    let overall_deadline =
        std::time::Instant::now() + std::time::Duration::from_secs(options.timeout_secs);
    let context_window = model_context_window(model);
    let mut total_input: u64 = 0;
    let mut total_output: u64 = 0;

    for turn in 0..MAX_AGENTIC_TURNS {
        // Cancellation check.
        if options
            .cancel_flag
            .as_ref()
            .is_some_and(|f| f.load(Ordering::Acquire))
        {
            return Ok(AgentResult {
                success: false,
                exit_code: 1,
                exit_kind: AgentExitKind::Cancelled,
                failure_message: Some("Cancelled".to_string()),
            });
        }

        // Overall timeout check.
        if std::time::Instant::now() >= overall_deadline {
            let msg = format!(
                "[ghcopilot] timed out after {} seconds",
                options.timeout_secs
            );
            let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
            return Ok(AgentResult {
                success: false,
                exit_code: 1,
                exit_kind: AgentExitKind::TimedOut,
                failure_message: Some(msg),
            });
        }

        // Proactive token refresh before the API call.
        if copilot_token.needs_refresh() {
            match fetch_copilot_token(&client, &github_token).await {
                Ok(t) => copilot_token = t,
                Err(e) => {
                    let _ = tx.send(AgentOutputEvent::Stderr(format!(
                        "[ghcopilot] token refresh warning: {}",
                        e
                    )));
                }
            }
        }

        let thinking_msg = if turn == 0 {
            "[ghcopilot] thinking…".to_string()
        } else {
            "[ghcopilot] processing tool results…".to_string()
        };
        let _ = tx.send(AgentOutputEvent::Text(thinking_msg));

        // Call the Copilot API, with one automatic retry on token expiry.
        let response = {
            let result =
                call_copilot(&client, &copilot_token.token, model, &messages, &tool_defs).await;

            match result {
                Ok(r) => r,
                Err(e) if e.to_string() == AUTH_ERROR_SENTINEL => {
                    // Token was rejected — refresh and retry once.
                    let _ = tx.send(AgentOutputEvent::Stderr(
                        "[ghcopilot] token rejected, refreshing…".to_string(),
                    ));
                    match fetch_copilot_token(&client, &github_token).await {
                        Ok(t) => {
                            copilot_token = t;
                            match call_copilot(
                                &client,
                                &copilot_token.token,
                                model,
                                &messages,
                                &tool_defs,
                            )
                            .await
                            {
                                Ok(r) => r,
                                Err(e2) => {
                                    let msg = format!(
                                        "[ghcopilot] API call failed after token refresh: {}",
                                        e2
                                    );
                                    let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
                                    return Ok(AgentResult {
                                        success: false,
                                        exit_code: 1,
                                        exit_kind: AgentExitKind::Failed,
                                        failure_message: Some(msg),
                                    });
                                }
                            }
                        }
                        Err(re) => {
                            let msg = format!("[ghcopilot] token refresh failed: {}", re);
                            let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
                            return Ok(AgentResult {
                                success: false,
                                exit_code: 1,
                                exit_kind: AgentExitKind::Failed,
                                failure_message: Some(msg),
                            });
                        }
                    }
                }
                Err(e) => {
                    let msg = format!("[ghcopilot] API error: {}", e);
                    let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
                    return Ok(AgentResult {
                        success: false,
                        exit_code: 1,
                        exit_kind: AgentExitKind::Failed,
                        failure_message: Some(msg),
                    });
                }
            }
        };

        // Log the raw message.
        if let Some(ref mut f) = log_file {
            use std::io::Write;
            let _ = writeln!(f, "{}", response.message);
        }

        total_input += response.prompt_tokens;
        total_output += response.completion_tokens;

        // Emit any text content the model produced.
        if let Some(text) = response.message["content"].as_str() {
            let text = text.trim();
            if !text.is_empty() {
                let _ = tx.send(AgentOutputEvent::Text(text.to_string()));
            }
        }

        match response.finish_reason.as_str() {
            "stop" | "end_turn" => {
                // Model is done — extract final answer.
                let result_text = response.message["content"]
                    .as_str()
                    .unwrap_or("")
                    .trim()
                    .to_string();

                // Emit accumulated token usage.
                let _ = tx.send(AgentOutputEvent::Usage {
                    cost_usd: 0.0, // subscription-based, no per-call cost
                    input_tokens: total_input,
                    output_tokens: total_output,
                    context_window,
                    cache_creation_tokens: 0,
                    cache_read_tokens: 0,
                });

                let _ = tx.send(AgentOutputEvent::Result(result_text));
                return Ok(AgentResult {
                    success: true,
                    exit_code: 0,
                    exit_kind: AgentExitKind::Completed,
                    failure_message: None,
                });
            }

            "tool_calls" => {
                let tool_calls = match response.message["tool_calls"].as_array() {
                    Some(tc) if !tc.is_empty() => tc.clone(),
                    _ => {
                        let _ = tx.send(AgentOutputEvent::Stderr(
                            "[ghcopilot] finish_reason=tool_calls but no tool_calls in message"
                                .to_string(),
                        ));
                        break;
                    }
                };

                // Append the assistant message (with its tool_calls) to history.
                messages.push(response.message.clone());

                // Execute each tool call and collect results.
                for tc in &tool_calls {
                    let call_id = tc["id"].as_str().unwrap_or("").to_string();
                    let fn_name = tc["function"]["name"].as_str().unwrap_or("unknown");
                    let args_str = tc["function"]["arguments"].as_str().unwrap_or("{}");
                    let args: Value =
                        serde_json::from_str(args_str).unwrap_or(json!({}));

                    let input_preview = args_str.chars().take(120).collect::<String>();
                    let _ = tx.send(AgentOutputEvent::ToolUse {
                        tool: fn_name.to_string(),
                        input_preview,
                    });

                    let result = execute_tool(fn_name, &args, project_dir, &client).await;

                    let output_preview = result.chars().take(120).collect::<String>();
                    let _ = tx.send(AgentOutputEvent::ToolResult { output_preview });

                    messages.push(json!({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result
                    }));
                }
                // Continue the loop for the next model turn.
            }

            "length" => {
                let msg = "[ghcopilot] context length exceeded — response truncated".to_string();
                let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
                return Ok(AgentResult {
                    success: false,
                    exit_code: 1,
                    exit_kind: AgentExitKind::Failed,
                    failure_message: Some(msg),
                });
            }

            other => {
                let _ = tx.send(AgentOutputEvent::Stderr(format!(
                    "[ghcopilot] unexpected finish_reason: '{}'",
                    other
                )));
                break;
            }
        }
    }

    // Reached MAX_AGENTIC_TURNS without a "stop" finish.
    let msg = format!(
        "[ghcopilot] reached maximum turn limit ({}) without completing",
        MAX_AGENTIC_TURNS
    );
    let _ = tx.send(AgentOutputEvent::Stderr(msg.clone()));
    Ok(AgentResult {
        success: false,
        exit_code: 1,
        exit_kind: AgentExitKind::Failed,
        failure_message: Some(msg),
    })
}

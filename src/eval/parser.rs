#![allow(dead_code)]

use crate::eval::stage_id::{from_log_prefix, StageId};
use anyhow::{Context, Result};
use serde_json::Value;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct ToolUseRecord {
    pub name: String,
    pub input: Value,
    pub parent_tool_use_id: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ToolResultRecord {
    pub tool_use_id: Option<String>,
    pub is_error: bool,
    pub text: Option<String>,
}

#[derive(Debug, Clone)]
pub struct StageTranscript {
    pub stage_id: Option<StageId>,
    pub log_path: PathBuf,
    pub model_from_init: Option<String>,
    pub tools_from_init: Vec<String>,
    pub tool_uses: Vec<ToolUseRecord>,
    pub tool_results: Vec<ToolResultRecord>,
    pub assistant_messages: Vec<String>,
    pub exit_observed: bool,
    pub parser_skipped: bool,
    pub malformed_line_count: usize,
}

impl StageTranscript {
    pub fn stub(log_path: PathBuf, stage_id: Option<StageId>) -> Self {
        Self {
            stage_id,
            log_path,
            model_from_init: None,
            tools_from_init: Vec::new(),
            tool_uses: Vec::new(),
            tool_results: Vec::new(),
            assistant_messages: Vec::new(),
            exit_observed: false,
            parser_skipped: true,
            malformed_line_count: 0,
        }
    }
}

fn strip_ansi_prefix(line: &str) -> &str {
    match line.find('{') {
        Some(i) => &line[i..],
        None => line,
    }
}

fn stage_id_from_log_path(path: &Path) -> Option<StageId> {
    let name = path.file_name()?.to_str()?;
    let segment = name.split('-').next()?;
    from_log_prefix(segment)
}

fn is_non_claude_log(path: &Path) -> bool {
    let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
    name.starts_with("studio-")
}

pub fn parse_stage_log(path: &Path) -> Result<StageTranscript> {
    let stage_id = stage_id_from_log_path(path);
    if is_non_claude_log(path) {
        return Ok(StageTranscript::stub(path.to_path_buf(), stage_id));
    }
    let file = File::open(path)
        .with_context(|| format!("failed to open log file {}", path.display()))?;
    let reader = BufReader::new(file);

    let mut transcript = StageTranscript {
        stage_id,
        log_path: path.to_path_buf(),
        model_from_init: None,
        tools_from_init: Vec::new(),
        tool_uses: Vec::new(),
        tool_results: Vec::new(),
        assistant_messages: Vec::new(),
        exit_observed: false,
        parser_skipped: false,
        malformed_line_count: 0,
    };

    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => {
                transcript.malformed_line_count += 1;
                continue;
            }
        };
        let line_str = line.trim();
        if line_str.is_empty() {
            continue;
        }
        let stripped = strip_ansi_prefix(line_str);
        if !stripped.starts_with('{') {
            continue;
        }
        let v: Value = match serde_json::from_str(stripped) {
            Ok(v) => v,
            Err(e) => {
                eprintln!(
                    "warning: skipping malformed JSONL line in {}: {}",
                    path.display(),
                    e
                );
                transcript.malformed_line_count += 1;
                continue;
            }
        };
        let kind = v.get("type").and_then(|x| x.as_str()).unwrap_or("");
        match kind {
            "system" => {
                let subtype = v.get("subtype").and_then(|x| x.as_str()).unwrap_or("");
                if subtype == "init" {
                    if let Some(model) = v.get("model").and_then(|x| x.as_str()) {
                        transcript.model_from_init = Some(model.to_string());
                    }
                    if let Some(arr) = v.get("tools").and_then(|x| x.as_array()) {
                        for elem in arr {
                            if let Some(s) = elem.as_str() {
                                transcript.tools_from_init.push(s.to_string());
                            } else if let Some(name) = elem.get("name").and_then(|x| x.as_str()) {
                                transcript.tools_from_init.push(name.to_string());
                            }
                        }
                    }
                }
            }
            "assistant" => {
                parse_assistant_content(&v, &mut transcript);
            }
            "user" => {
                parse_user_content(&v, &mut transcript);
            }
            "result" => {
                transcript.exit_observed = true;
            }
            _ => {}
        }
    }

    Ok(transcript)
}

fn parse_assistant_content(v: &Value, transcript: &mut StageTranscript) {
    let arr = match v
        .get("message")
        .and_then(|m| m.get("content"))
        .and_then(|c| c.as_array())
    {
        Some(a) => a,
        None => return,
    };
    for block in arr {
        let kind = block.get("type").and_then(|x| x.as_str()).unwrap_or("");
        if kind == "tool_use" || kind.contains("tool_use") {
            let name = block
                .get("name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string();
            let input = block.get("input").cloned().unwrap_or(Value::Null);
            let parent_tool_use_id = block
                .get("parent_tool_use_id")
                .and_then(|x| x.as_str())
                .map(|s| s.to_string())
                .or_else(|| {
                    v.get("parent_tool_use_id")
                        .and_then(|x| x.as_str())
                        .map(|s| s.to_string())
                });
            transcript.tool_uses.push(ToolUseRecord {
                name,
                input,
                parent_tool_use_id,
            });
        } else if kind == "text" {
            if let Some(t) = block.get("text").and_then(|x| x.as_str()) {
                transcript.assistant_messages.push(t.to_string());
            }
        }
    }
}

fn parse_user_content(v: &Value, transcript: &mut StageTranscript) {
    let arr = match v
        .get("message")
        .and_then(|m| m.get("content"))
        .and_then(|c| c.as_array())
    {
        Some(a) => a,
        None => return,
    };
    for block in arr {
        if block.get("type").and_then(|x| x.as_str()) != Some("tool_result") {
            continue;
        }
        let tool_use_id = block
            .get("tool_use_id")
            .and_then(|x| x.as_str())
            .map(|s| s.to_string());
        let is_error = block
            .get("is_error")
            .and_then(|x| x.as_bool())
            .unwrap_or(false)
            || v.get("tool_use_result")
                .and_then(|tur| tur.get("is_error"))
                .and_then(|x| x.as_bool())
                .unwrap_or(false);
        let text = block.get("content").and_then(|c| {
            if let Some(s) = c.as_str() {
                Some(s.to_string())
            } else if let Some(arr) = c.as_array() {
                Some(
                    arr.iter()
                        .filter_map(|item| item.get("text").and_then(|x| x.as_str()))
                        .collect::<Vec<_>>()
                        .join("\n"),
                )
            } else {
                None
            }
        });
        transcript.tool_results.push(ToolResultRecord {
            tool_use_id,
            is_error,
            text,
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::Builder;

    const FIXTURE: &str = include_str!("../../tests/fixtures/claude-stage.jsonl");

    fn write_fixture_with_prefix(prefix: &str, suffix: &str, content: &str) -> tempfile::NamedTempFile {
        let mut f = Builder::new()
            .prefix(prefix)
            .suffix(suffix)
            .tempfile()
            .unwrap();
        f.write_all(content.as_bytes()).unwrap();
        f.flush().unwrap();
        f
    }

    #[test]
    fn parse_stage_log_happy_path() {
        let f = write_fixture_with_prefix("PLAN-20260507-000000", ".jsonl", FIXTURE);
        let transcript = parse_stage_log(f.path()).unwrap();
        assert!(!transcript.parser_skipped);
        assert_eq!(transcript.model_from_init.as_deref(), Some("claude-opus-4-7"));
        assert!(transcript.tools_from_init.contains(&"Read".to_string()));
        assert!(!transcript.tool_uses.is_empty());
        let read_use = transcript
            .tool_uses
            .iter()
            .find(|t| t.name == "Read")
            .expect("expected at least one Read tool_use");
        let fp = read_use.input.get("file_path").and_then(|v| v.as_str()).unwrap();
        assert!(fp.ends_with("current-plan.md"), "got: {}", fp);
        assert!(transcript
            .tool_uses
            .iter()
            .any(|t| t.parent_tool_use_id.is_some()));
        assert!(!transcript.tool_results.is_empty());
        assert!(transcript.exit_observed);
        assert!(!transcript.assistant_messages.is_empty());
    }

    #[test]
    fn parse_stage_log_skips_malformed_lines() {
        let f = write_fixture_with_prefix("PLAN-20260507-000000", ".jsonl", FIXTURE);
        let transcript = parse_stage_log(f.path()).unwrap();
        assert!(transcript.malformed_line_count >= 1);
    }

    #[test]
    fn parse_stage_log_skips_non_claude() {
        let f = write_fixture_with_prefix("studio-codex-", ".jsonl", "anything goes here");
        let transcript = parse_stage_log(f.path()).unwrap();
        assert!(transcript.parser_skipped);
        assert!(transcript.tool_uses.is_empty());
        assert!(transcript.tool_results.is_empty());
        assert!(transcript.assistant_messages.is_empty());
    }

    #[test]
    fn parse_stage_log_missing_file_errors() {
        let result = parse_stage_log(Path::new("/nonexistent/path/should-not-exist.jsonl"));
        assert!(result.is_err());
    }

    #[test]
    fn stage_id_from_log_path_extracts_prefix() {
        assert_eq!(
            stage_id_from_log_path(Path::new("PLAN-20260507-143215.jsonl")),
            Some(StageId::Plan)
        );
        assert_eq!(
            stage_id_from_log_path(Path::new("BUILDER-x.jsonl")),
            Some(StageId::Build)
        );
    }
}

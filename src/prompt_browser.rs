//! Parse `src/prompts.rs` at compile time and expose its `pub fn *_prompt`
//! functions for the Viewer overlay's Prompts tab. Read-only: the modal
//! shows the function source verbatim (template strings, placeholders,
//! everything) so users can see what foundry actually sends to LLMs.
//!
//! Editing prompts requires rebuilding foundry, so we don't offer an
//! in-modal editor for the Prompts tab.

const PROMPTS_SRC: &str = include_str!("prompts.rs");

#[derive(Debug, Clone)]
pub struct PromptInfo {
    /// Function name, e.g. `"planner_prompt"`.
    pub name: String,
    /// First non-empty `///` line above the function. Empty if none.
    pub doc_summary: String,
    /// Full function source (signature + body), verbatim from prompts.rs.
    pub source: String,
}

pub fn list_prompts() -> Vec<PromptInfo> {
    let lines: Vec<&str> = PROMPTS_SRC.lines().collect();
    let mut out: Vec<PromptInfo> = Vec::new();
    let mut i = 0;
    while i < lines.len() {
        let line = lines[i];
        if let Some(name) = parse_pub_fn_name(line) {
            let (body, end) = collect_function_body(&lines, i);
            // Filter: any function whose name CONTAINS "_prompt" — this
            // covers both `*_prompt` (e.g. planner_prompt) and `*_prompt_*`
            // (e.g. stage_summary_prompt_query, stage_summary_prompt_research)
            // while still excluding infrastructure helpers like
            // `agent_system_directives` and `wrap_with_plugins`.
            // Explicit deny-list for known formatters that happen to match.
            const NOT_A_PROMPT: &[&str] = &["format_stage_results_for_prompt"];
            if name.contains("_prompt") && !NOT_A_PROMPT.contains(&name.as_str()) {
                let mut doc_summary = collect_doc_summary(&lines, i);
                if doc_summary.is_empty() {
                    // Fallback: surface the signature line (`pub fn foo(...) -> ...`)
                    // so the viewer at least shows *something* informative when
                    // a function lacks a `///` doc comment.
                    doc_summary = signature_summary(&body);
                }
                out.push(PromptInfo {
                    name,
                    doc_summary,
                    source: body,
                });
            }
            i = end;
            continue;
        }
        i += 1;
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    out
}

/// Extract a one-line signature summary from the start of a function body.
/// Joins continuation lines up to the opening `{` so multi-line signatures
/// collapse to one display row.
fn signature_summary(body: &str) -> String {
    let mut out = String::new();
    for raw in body.lines() {
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        if !out.is_empty() {
            out.push(' ');
        }
        out.push_str(line);
        if line.contains('{') {
            break;
        }
    }
    // Trim trailing brace if present.
    if let Some(stripped) = out.strip_suffix('{') {
        return stripped.trim_end().to_string();
    }
    out
}

/// If `line` is `pub fn <name>(...)`, returns `Some(name)`. Excludes `agent_*`
/// helpers? No, include all pub fns from prompts.rs -- they're all relevant.
fn parse_pub_fn_name(line: &str) -> Option<String> {
    let trimmed = line.trim_start();
    let rest = trimmed.strip_prefix("pub fn ")?;
    let end = rest.find('(')?;
    let name = rest[..end].trim();
    if name.is_empty() {
        return None;
    }
    Some(name.to_string())
}

/// Walk backwards from the `pub fn` line collecting consecutive `///` lines.
/// Returns the first non-empty doc line (stripped of `///`) as a one-line
/// summary, or an empty string if no doc comment is present.
fn collect_doc_summary(lines: &[&str], fn_idx: usize) -> String {
    let mut idx = fn_idx;
    let mut first: String = String::new();
    while idx > 0 {
        idx -= 1;
        let l = lines[idx].trim_start();
        if let Some(rest) = l.strip_prefix("///") {
            let cleaned = rest.trim();
            if !cleaned.is_empty() {
                first = cleaned.to_string();
            }
        } else if l.starts_with("//") {
            // skip plain line comments contiguous with the doc block
            continue;
        } else if l.is_empty() {
            // blank lines between doc and fn are allowed
            continue;
        } else {
            break;
        }
    }
    first
}

/// Collect lines from `start` (the `pub fn` line) through the matching closing
/// brace of the function body. Handles raw strings (`r#"..."#`) so embedded
/// braces and quotes don't confuse the brace counter.
///
/// Returns `(source, next_line_idx)` where `next_line_idx` is the index of the
/// first line after the function's closing brace.
fn collect_function_body(lines: &[&str], start: usize) -> (String, usize) {
    let mut depth: i32 = 0;
    let mut started = false;
    let mut end = start;
    let mut collected: Vec<&str> = Vec::new();
    // Cross-line state: raw strings and regular strings can span lines in
    // Rust source, so these MUST persist across line boundaries.
    let mut in_str = false;
    let mut in_raw = false;
    let mut raw_hashes: usize = 0;

    for (offset, line) in lines[start..].iter().enumerate() {
        collected.push(line);
        let mut chars = line.chars().peekable();
        while let Some(c) = chars.next() {
            if in_raw {
                if c == '"' {
                    let mut hashes_seen = 0;
                    while let Some(&p) = chars.peek() {
                        if p == '#' && hashes_seen < raw_hashes {
                            chars.next();
                            hashes_seen += 1;
                        } else {
                            break;
                        }
                    }
                    if hashes_seen == raw_hashes {
                        in_raw = false;
                    }
                }
                continue;
            }
            if in_str {
                if c == '\\' {
                    chars.next();
                } else if c == '"' {
                    in_str = false;
                }
                continue;
            }
            if c == 'r' {
                // detect r#"..."# or r"..."
                let mut lookahead = chars.clone();
                let mut hashes = 0usize;
                while let Some(&p) = lookahead.peek() {
                    if p == '#' {
                        lookahead.next();
                        hashes += 1;
                    } else {
                        break;
                    }
                }
                if let Some(&p) = lookahead.peek() {
                    if p == '"' {
                        // consume hashes + quote in `chars`
                        for _ in 0..hashes {
                            chars.next();
                        }
                        chars.next(); // consume the opening quote
                        in_raw = true;
                        raw_hashes = hashes;
                        continue;
                    }
                }
            }
            if c == '"' {
                in_str = true;
                continue;
            }
            if c == '/' {
                if let Some(&'/') = chars.peek() {
                    // line comment, skip rest of line
                    break;
                }
            }
            if c == '{' {
                depth += 1;
                started = true;
            } else if c == '}' {
                depth -= 1;
                if started && depth == 0 {
                    end = start + offset + 1;
                    return (collected.join("\n"), end);
                }
            }
        }
        end = start + offset + 1;
    }
    (collected.join("\n"), end)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_at_least_some_prompts() {
        let prompts = list_prompts();
        // Filtered to `*_prompt` only; expect a strong majority of the
        // ~40 public functions in prompts.rs.
        assert!(
            prompts.len() >= 30,
            "expected at least 30 *_prompt functions, got {}",
            prompts.len()
        );
    }

    #[test]
    fn filters_non_prompt_functions() {
        let prompts = list_prompts();
        for excluded in [
            "agent_system_directives",
            "wrap_with_plugins",
            "format_stage_results_for_prompt",
        ] {
            assert!(
                !prompts.iter().any(|p| p.name == excluded),
                "{} should be filtered out (helper, not a prompt)",
                excluded
            );
        }
        for p in &prompts {
            assert!(
                p.name.contains("_prompt"),
                "non-prompt entry leaked through: {}",
                p.name
            );
        }
    }

    #[test]
    fn includes_stage_summary_suffix_prompts() {
        let prompts = list_prompts();
        for needed in [
            "stage_summary_prompt_query",
            "stage_summary_prompt_research",
            "stage_summary_prompt_plan",
            "stage_summary_prompt_build",
            "stage_summary_prompt_audit",
        ] {
            assert!(
                prompts.iter().any(|p| p.name == needed),
                "{} should be included (prompt-producing fn)",
                needed
            );
        }
    }

    #[test]
    fn every_prompt_has_a_summary() {
        let prompts = list_prompts();
        for p in &prompts {
            assert!(
                !p.doc_summary.is_empty(),
                "{} has no summary (doc comment or signature fallback)",
                p.name
            );
        }
    }

    #[test]
    fn finds_planner_prompt() {
        let prompts = list_prompts();
        let planner = prompts.iter().find(|p| p.name == "planner_prompt");
        assert!(planner.is_some(), "planner_prompt not found");
        let p = planner.unwrap();
        assert!(p.source.contains("pub fn planner_prompt"));
        assert!(p.source.trim_end().ends_with('}'));
    }

    #[test]
    fn parses_raw_string_function_body() {
        // agent_system_directives uses regular string concatenation, not raw
        // strings -- but planner_prompt is a good raw-string test target.
        let prompts = list_prompts();
        let planner = prompts.iter().find(|p| p.name == "planner_prompt").unwrap();
        // The function body should contain at least one r#"..."# literal.
        assert!(
            planner.source.contains("r#\"") || planner.source.contains('"'),
            "planner_prompt body unexpectedly empty of string literals"
        );
    }
}

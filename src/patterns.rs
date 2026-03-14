use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatternSolution {
    #[serde(default)]
    pub planner: String,
    #[serde(default)]
    #[serde(alias = "validator")]
    pub reviewer: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pattern {
    pub pattern_id: String,
    pub title: String,
    #[serde(default)]
    pub first_seen: String,
    #[serde(default)]
    pub last_seen: String,
    #[serde(default)]
    pub frequency: usize,
    #[serde(default)]
    pub severity: Option<String>,
    #[serde(default)]
    pub keywords: Vec<String>,
    #[serde(default)]
    pub tech_stack: Vec<String>,
    #[serde(default)]
    pub issue: Option<String>,
    #[serde(default)]
    pub solution: Option<PatternSolution>,
    #[serde(default)]
    pub auto_apply: bool,
    #[serde(default)]
    pub learned_from: Option<String>,
}

/// Expand `~/` prefix using $HOME environment variable.
/// Falls back to /tmp/.foundry/patterns if HOME is unset (e.g., containers).
pub fn resolve_patterns_dir(config_str: &str) -> PathBuf {
    if let Some(rest) = config_str.strip_prefix("~/") {
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home).join(rest);
        }
        // HOME unset — use /tmp fallback instead of literal ~/
        eprintln!("warning: HOME not set, using /tmp/.foundry/patterns for pattern storage");
        return PathBuf::from("/tmp/.foundry/patterns");
    }
    PathBuf::from(config_str)
}

/// Load all patterns from JSON files in the patterns directory.
pub fn load_patterns(dir: &Path) -> Vec<Pattern> {
    let mut patterns = Vec::new();

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return patterns,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("json") {
            if let Ok(content) = std::fs::read_to_string(&path) {
                // Try as array first, then as single pattern
                if let Ok(mut arr) = serde_json::from_str::<Vec<Pattern>>(&content) {
                    patterns.append(&mut arr);
                } else if let Ok(p) = serde_json::from_str::<Pattern>(&content) {
                    patterns.push(p);
                } else {
                    eprintln!("warning: failed to parse patterns file: {}", path.display());
                }
            }
        }
    }

    patterns
}

/// Match patterns against a task description using whole-word keyword matching.
/// Returns patterns sorted by relevance (highest score first).
pub fn match_patterns<'a>(patterns: &'a [Pattern], task_desc: &str) -> Vec<&'a Pattern> {
    let scored = keyword_scores(patterns, task_desc);
    let mut result: Vec<(&Pattern, usize)> = scored
        .into_iter()
        .filter(|(_, score)| *score > 0)
        .map(|(idx, score)| (&patterns[idx], score))
        .collect();
    result.sort_by(|a, b| b.1.cmp(&a.1));
    result.into_iter().map(|(p, _)| p).collect()
}

/// Returns (pattern_index, keyword_score) pairs for all patterns.
/// Used by the semantic matcher as the keyword baseline for reranking.
pub fn keyword_scores(patterns: &[Pattern], task_desc: &str) -> Vec<(usize, usize)> {
    let desc_lower = task_desc.to_lowercase();
    let desc_words: Vec<&str> = desc_lower.split_whitespace().collect();

    patterns
        .iter()
        .enumerate()
        .filter_map(|(i, p)| {
            let mut score = 0usize;

            for kw in &p.keywords {
                let kw_lower = kw.to_lowercase();
                if desc_words.iter().any(|w| *w == kw_lower) {
                    score += 2;
                } else if desc_lower.contains(&kw_lower) {
                    score += 1;
                }
            }

            for tech in &p.tech_stack {
                let tech_lower = tech.to_lowercase();
                if desc_words.iter().any(|w| *w == tech_lower) || desc_lower.contains(&tech_lower) {
                    score += 1;
                }
            }

            if p.auto_apply && score > 0 {
                score += 2;
            }

            if p.frequency >= 3 && score > 0 {
                score += 1;
            }

            if score > 0 { Some((i, score)) } else { None }
        })
        .collect()
}

/// Format matched patterns as markdown text for injection into agent prompts.
/// `max_patterns` caps how many patterns are injected to protect the context "smart zone".
pub fn format_patterns_for_prompt(
    patterns: &[&Pattern],
    role: &str,
    max_patterns: usize,
) -> String {
    if patterns.is_empty() {
        return String::new();
    }

    let limit = if max_patterns == 0 { 10 } else { max_patterns };
    let role_lower = role.to_lowercase();
    let mut out = String::new();
    out.push_str("\n\n---\n## Known Patterns (from previous builds)\n\n");

    for (i, p) in patterns.iter().enumerate().take(limit) {
        out.push_str(&format!(
            "### {}. {} (seen {}x{})\n",
            i + 1,
            p.title,
            p.frequency,
            p.severity
                .as_deref()
                .map(|s| format!(", {}", s))
                .unwrap_or_default()
        ));

        if let Some(ref issue) = p.issue {
            out.push_str(&format!("**Issue:** {}\n", issue));
        }

        if let Some(ref sol) = p.solution {
            let advice = if role_lower == "reviewer" {
                &sol.reviewer
            } else {
                &sol.planner
            };
            if !advice.is_empty() {
                out.push_str(&format!("**Advice:** {}\n", advice));
            }
        }

        out.push('\n');
    }

    out
}

/// Merge new patterns into the patterns directory, deduplicating by pattern_id.
/// Uses atomic write (tmp + rename) to prevent data corruption.
/// Returns the number of new patterns added.
pub fn merge_patterns(dir: &Path, new_patterns: Vec<Pattern>) -> Result<usize> {
    if new_patterns.is_empty() {
        return Ok(0);
    }

    std::fs::create_dir_all(dir)?;

    let target = dir.join("common-issues.json");
    let tmp = dir.join(".common-issues.json.tmp");

    // Load existing patterns — handle both array and single-object formats
    let mut existing: Vec<Pattern> = if target.exists() {
        let content = std::fs::read_to_string(&target)?;
        serde_json::from_str::<Vec<Pattern>>(&content)
            .or_else(|_| serde_json::from_str::<Pattern>(&content).map(|p| vec![p]))
            .unwrap_or_default()
    } else {
        Vec::new()
    };

    // Index existing by pattern_id
    let mut by_id: HashMap<String, usize> = existing
        .iter()
        .enumerate()
        .map(|(i, p)| (p.pattern_id.clone(), i))
        .collect();

    let mut added = 0usize;

    for np in new_patterns {
        if let Some(&idx) = by_id.get(&np.pattern_id) {
            // Update existing: add incoming frequency (at least 1), update last_seen
            existing[idx].frequency += np.frequency.max(1);
            if !np.last_seen.is_empty() {
                existing[idx].last_seen = np.last_seen;
            }
            // Graduate to auto_apply after 3+ occurrences
            if existing[idx].frequency >= 3 {
                existing[idx].auto_apply = true;
            }
        } else {
            by_id.insert(np.pattern_id.clone(), existing.len());
            existing.push(np);
            added += 1;
        }
    }

    // Atomic write: write to tmp, then rename
    let json = serde_json::to_string_pretty(&existing)?;
    std::fs::write(&tmp, &json)?;
    std::fs::rename(&tmp, &target)?;

    Ok(added)
}

/// Parse patterns from a JSON file (e.g., agent-extracted patterns).
pub fn extract_patterns_from_file(path: &Path) -> Result<Vec<Pattern>> {
    let content = std::fs::read_to_string(path)?;

    // Try direct parse
    if let Ok(patterns) = serde_json::from_str::<Vec<Pattern>>(&content) {
        return Ok(patterns);
    }

    // Try extracting JSON from markdown code fences
    let json = extract_json_from_content(&content);
    if !json.is_empty() {
        if let Ok(patterns) = serde_json::from_str::<Vec<Pattern>>(&json) {
            return Ok(patterns);
        }
    }

    Ok(Vec::new())
}

/// Extract JSON content from the first ```json code fence in markdown.
fn extract_json_from_content(content: &str) -> String {
    let mut in_fence = false;
    let mut json_lines = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim_start();
        if trimmed.starts_with("```") {
            if in_fence {
                break; // closing fence
            }
            if trimmed.starts_with("```json") {
                in_fence = true;
            }
            continue;
        }
        if in_fence {
            json_lines.push(line);
        }
    }

    json_lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pattern_solution_deserializes_reviewer_field() {
        let json = r#"{"planner": "plan advice", "reviewer": "review advice"}"#;
        let sol: PatternSolution = serde_json::from_str(json).unwrap();
        assert_eq!(sol.reviewer, "review advice");
    }

    #[test]
    fn test_pattern_solution_deserializes_validator_alias() {
        let json = r#"{"planner": "plan advice", "validator": "old validator advice"}"#;
        let sol: PatternSolution = serde_json::from_str(json).unwrap();
        assert_eq!(sol.reviewer, "old validator advice");
    }

    #[test]
    fn test_format_patterns_routes_reviewer_advice() {
        let pattern = Pattern {
            pattern_id: "test-1".to_string(),
            title: "Test Pattern".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 1,
            severity: Some("HIGH".to_string()),
            keywords: vec!["test".to_string()],
            tech_stack: vec![],
            issue: Some("some issue".to_string()),
            solution: Some(PatternSolution {
                planner: "planner advice".to_string(),
                reviewer: "reviewer advice".to_string(),
            }),
            auto_apply: false,
            learned_from: None,
        };
        let patterns = vec![&pattern];

        let reviewer_output = format_patterns_for_prompt(&patterns, "reviewer", 10);
        assert!(
            reviewer_output.contains("reviewer advice"),
            "reviewer role should get reviewer advice"
        );

        let planner_output = format_patterns_for_prompt(&patterns, "planner", 10);
        assert!(
            planner_output.contains("planner advice"),
            "planner role should get planner advice"
        );
    }
}

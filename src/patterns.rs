use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::complexity::TaskComplexity;
use crate::utils::atomic_write_file;

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
    /// How many times agents have cited this pattern in their output artifacts.
    /// Tracked automatically after each task to measure pattern usefulness.
    #[serde(default)]
    pub used_count: usize,
    /// Extension CLAUDE.md path this pattern was promoted to (e.g. "extensions/rust/CLAUDE.md").
    /// Non-empty means the pattern has graduated to extension prose and should be excluded from injection.
    #[serde(default)]
    pub promoted_to: String,
    /// ISO date when the pattern was promoted (e.g. "2026-04-07").
    #[serde(default)]
    pub promoted_at: String,
}

/// Wrapper object format used by extension pattern files.
/// Example: {"pattern_type": "common-issues", "domain": "recon", "patterns": [...]}
/// Preserves extra metadata fields (pattern_type, domain, version, etc.) on round-trip.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct PatternWrapper {
    patterns: Vec<Pattern>,
    /// Capture all non-"patterns" keys so they survive a write-back.
    #[serde(flatten)]
    extra: HashMap<String, serde_json::Value>,
}

/// Expand `~/` prefix using $HOME environment variable.
/// Falls back to platform temp dir + .foundry/patterns if HOME is unset (e.g., containers).
pub fn resolve_patterns_dir(config_str: &str) -> PathBuf {
    if let Some(rest) = config_str.strip_prefix("~/") {
        let base = if cfg!(target_os = "windows") {
            std::env::var("LOCALAPPDATA")
                .or_else(|_| std::env::var("USERPROFILE"))
                .ok()
        } else {
            std::env::var("HOME").ok()
        };
        if let Some(base) = base {
            return PathBuf::from(base).join(rest);
        }
        // HOME unset — use platform temp dir instead of literal ~/
        let fallback = std::env::temp_dir().join(".foundry").join("patterns");
        eprintln!("warning: HOME not set, using {} for pattern storage", fallback.display());
        return fallback;
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
                // Try as array first, then wrapper object, then single pattern
                if let Ok(mut arr) = serde_json::from_str::<Vec<Pattern>>(&content) {
                    patterns.append(&mut arr);
                } else if let Ok(wrapper) = serde_json::from_str::<PatternWrapper>(&content) {
                    patterns.extend(wrapper.patterns);
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

/// Load all patterns from JSON files in a directory, returning each pattern paired with its source file path.
/// Needed by the promote command to know which JSON file to write `promoted_to` back to.
pub fn load_patterns_with_sources(dir: &Path) -> Vec<(Pattern, PathBuf)> {
    let mut results = Vec::new();

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return results,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("json") {
            if let Ok(content) = std::fs::read_to_string(&path) {
                if let Ok(arr) = serde_json::from_str::<Vec<Pattern>>(&content) {
                    for p in arr {
                        results.push((p, path.clone()));
                    }
                } else if let Ok(wrapper) = serde_json::from_str::<PatternWrapper>(&content) {
                    for p in wrapper.patterns {
                        results.push((p, path.clone()));
                    }
                } else if let Ok(p) = serde_json::from_str::<Pattern>(&content) {
                    results.push((p, path.clone()));
                } else {
                    eprintln!("warning: failed to parse patterns file: {}", path.display());
                }
            }
        }
    }

    results
}

/// Detect the project's tech stack by checking for marker files in the project directory.
pub fn detect_project_tech_stack(project_dir: &Path) -> Vec<String> {
    let mut stacks = Vec::new();
    if project_dir.join("Cargo.toml").exists() {
        stacks.push("rust".to_string());
    }
    if project_dir.join("package.json").exists() {
        stacks.push("javascript".to_string());
        stacks.push("typescript".to_string());
    }
    if project_dir.join("pyproject.toml").exists() || project_dir.join("setup.py").exists() {
        stacks.push("python".to_string());
    }
    if project_dir.join("go.mod").exists() {
        stacks.push("go".to_string());
    }
    stacks
}

/// Match patterns against a task description using whole-word keyword matching.
/// Returns patterns sorted by relevance (highest score first).
pub fn match_patterns<'a>(patterns: &'a [Pattern], task_desc: &str, detected_stack: &[String]) -> Vec<&'a Pattern> {
    let scored = keyword_scores(patterns, task_desc, detected_stack);
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
pub fn keyword_scores(patterns: &[Pattern], task_desc: &str, detected_stack: &[String]) -> Vec<(usize, usize)> {
    let desc_lower = task_desc.to_lowercase();
    let desc_words: Vec<&str> = desc_lower.split_whitespace().collect();

    patterns
        .iter()
        .enumerate()
        .filter_map(|(i, p)| {
            // Skip promoted patterns -- they now live in extension CLAUDE.md
            if !p.promoted_to.is_empty() {
                return None;
            }

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

            // Usefulness tracking: boost patterns agents actually cite, demote noise.
            // Inspired by TOIN (Tool Output Intelligence Network) in chopratejas/headroom,
            // which learns field importance from retrieval rates.
            // https://github.com/chopratejas/headroom
            if score > 0 {
                if p.used_count > 0 && p.frequency > 0 {
                    let ratio = p.used_count as f64 / p.frequency as f64;
                    if ratio > 0.3 {
                        score += 2; // high-utility pattern
                    }
                }
                if p.used_count == 0 && p.frequency >= 5 {
                    score = score.saturating_sub(1); // never-cited noise
                }
            }

            // Tech-stack affinity: penalize patterns from unrelated domains
            if score > 0 && !detected_stack.is_empty() && !p.tech_stack.is_empty() {
                let has_match = p.tech_stack.iter().any(|ts| {
                    let ts_lower = ts.to_lowercase();
                    detected_stack.iter().any(|ds| ds.to_lowercase() == ts_lower)
                });
                if !has_match {
                    score = score.saturating_sub(3);
                }
            }

            if score > 0 {
                Some((i, score))
            } else {
                None
            }
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
            "### {}. {} [{}] (seen {}x{})\n",
            i + 1,
            p.title,
            p.pattern_id,
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

/// Return the effective pattern injection cap based on task complexity.
///
/// Simple tasks get `min` patterns, medium tasks get 5 (capped at `max`),
/// and complex tasks get the full `max` value.
pub fn scaled_injection_count(complexity: TaskComplexity, max: usize, min: usize) -> usize {
    match complexity {
        TaskComplexity::Simple => min,
        TaskComplexity::Medium => 5_usize.min(max),
        TaskComplexity::Complex => max,
    }
}

/// Scan text for references to pattern IDs or titles.
/// Returns the pattern_ids of patterns that were cited.
pub fn scan_citations(text: &str, patterns: &[Pattern]) -> Vec<String> {
    if text.is_empty() || patterns.is_empty() {
        return Vec::new();
    }

    let text_lower = text.to_lowercase();
    let text_words: Vec<&str> = text_lower.split_whitespace().collect();

    patterns
        .iter()
        .filter(|p| {
            // Check exact pattern_id word match
            let id_lower = p.pattern_id.to_lowercase();
            let id_match = text_words.iter().any(|w| w.trim_matches(|c: char| !c.is_alphanumeric() && c != '-') == id_lower);
            if id_match {
                return true;
            }
            // Check title substring match (case-insensitive)
            let title_lower = p.title.to_lowercase();
            if title_lower.len() >= 8 && text_lower.contains(&title_lower) {
                return true;
            }
            false
        })
        .map(|p| p.pattern_id.clone())
        .collect()
}

/// Increment used_count for cited patterns across all JSON files in a directory.
/// Mirrors load_patterns() behavior: scans every *.json file, not just common-issues.json.
/// Returns the total number of patterns updated.
pub fn update_used_counts(dir: &Path, cited_ids: &[String]) -> Result<usize> {
    if cited_ids.is_empty() {
        return Ok(0);
    }

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return Ok(0),
    };

    let mut total_updated = 0usize;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        // Detect original format and update in place to preserve file shape.
        // Try wrapper first (has metadata like pattern_type, domain, version).
        if let Ok(mut wrapper) = serde_json::from_str::<PatternWrapper>(&content) {
            let mut file_updated = 0usize;
            for p in &mut wrapper.patterns {
                if cited_ids.contains(&p.pattern_id) {
                    p.used_count += 1;
                    file_updated += 1;
                }
            }
            if file_updated > 0 {
                let json = serde_json::to_string_pretty(&wrapper)?;
                atomic_write_file(&path, json.as_bytes())?;
                total_updated += file_updated;
            }
            continue;
        }

        // Plain array format
        if let Ok(mut patterns) = serde_json::from_str::<Vec<Pattern>>(&content) {
            let mut file_updated = 0usize;
            for p in &mut patterns {
                if cited_ids.contains(&p.pattern_id) {
                    p.used_count += 1;
                    file_updated += 1;
                }
            }
            if file_updated > 0 {
                let json = serde_json::to_string_pretty(&patterns)?;
                atomic_write_file(&path, json.as_bytes())?;
                total_updated += file_updated;
            }
            continue;
        }

        // Single pattern object
        if let Ok(mut pattern) = serde_json::from_str::<Pattern>(&content) {
            if cited_ids.contains(&pattern.pattern_id) {
                pattern.used_count += 1;
                let json = serde_json::to_string_pretty(&pattern)?;
                atomic_write_file(&path, json.as_bytes())?;
                total_updated += 1;
            }
        }
    }

    Ok(total_updated)
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
    // Load existing patterns — handle both array and single-object formats
    let mut existing: Vec<Pattern> = if target.exists() {
        let content = std::fs::read_to_string(&target)?;
        serde_json::from_str::<Vec<Pattern>>(&content)
            .or_else(|_| serde_json::from_str::<PatternWrapper>(&content).map(|w| w.patterns))
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

    let json = serde_json::to_string_pretty(&existing)?;
    atomic_write_file(&target, json.as_bytes())?;

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
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
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

    #[test]
    fn test_load_patterns_wrapper_format() {
        let dir = std::env::temp_dir().join("foundry_test_wrapper");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let wrapper_json = r#"{
            "pattern_type": "common-issues",
            "domain": "recon",
            "version": "1.0.0",
            "last_updated": "2026-03-12",
            "patterns": [
                {
                    "pattern_id": "test-wrapper-1",
                    "title": "First wrapper pattern",
                    "frequency": 1,
                    "keywords": ["test"]
                },
                {
                    "pattern_id": "test-wrapper-2",
                    "title": "Second wrapper pattern",
                    "frequency": 2,
                    "keywords": ["wrapper"]
                }
            ]
        }"#;
        std::fs::write(dir.join("wrapper.json"), wrapper_json).unwrap();

        let patterns = load_patterns(&dir);
        assert_eq!(patterns.len(), 2, "should load both patterns from wrapper");
        assert_eq!(patterns[0].pattern_id, "test-wrapper-1");
        assert_eq!(patterns[1].pattern_id, "test-wrapper-2");
        assert_eq!(patterns[1].frequency, 2);

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_load_patterns_wrapper_metadata_format() {
        let dir = std::env::temp_dir().join("foundry_test_wrapper_meta");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let wrapper_json = r#"{
            "metadata": {
                "version": "1.0",
                "description": "Test patterns"
            },
            "patterns": [
                {
                    "pattern_id": "meta-1",
                    "title": "Metadata wrapper pattern",
                    "frequency": 1,
                    "keywords": ["meta"]
                }
            ]
        }"#;
        std::fs::write(dir.join("meta-wrapper.json"), wrapper_json).unwrap();

        let patterns = load_patterns(&dir);
        assert_eq!(
            patterns.len(),
            1,
            "should load pattern from metadata-style wrapper"
        );
        assert_eq!(patterns[0].pattern_id, "meta-1");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_load_patterns_mixed_formats() {
        let dir = std::env::temp_dir().join("foundry_test_mixed");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        // Array format
        let array_json = r#"[
            {
                "pattern_id": "arr-1",
                "title": "Array pattern",
                "frequency": 1,
                "keywords": []
            }
        ]"#;
        std::fs::write(dir.join("array.json"), array_json).unwrap();

        // Wrapper format
        let wrapper_json = r#"{
            "pattern_type": "common-issues",
            "domain": "test",
            "patterns": [
                {
                    "pattern_id": "wrap-1",
                    "title": "Wrapper pattern",
                    "frequency": 1,
                    "keywords": []
                }
            ]
        }"#;
        std::fs::write(dir.join("wrapper.json"), wrapper_json).unwrap();

        // Single pattern format
        let single_json = r#"{
            "pattern_id": "single-1",
            "title": "Single pattern",
            "frequency": 1,
            "keywords": []
        }"#;
        std::fs::write(dir.join("single.json"), single_json).unwrap();

        let patterns = load_patterns(&dir);
        assert_eq!(patterns.len(), 3, "should load from all three formats");

        let ids: Vec<&str> = patterns.iter().map(|p| p.pattern_id.as_str()).collect();
        assert!(ids.contains(&"arr-1"), "should contain array pattern");
        assert!(ids.contains(&"wrap-1"), "should contain wrapper pattern");
        assert!(ids.contains(&"single-1"), "should contain single pattern");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_merge_patterns_wrapper_format() {
        let dir = std::env::temp_dir().join("foundry_test_merge_wrapper");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        // Write existing patterns in wrapper format
        let wrapper_json = r#"{
            "pattern_type": "common-issues",
            "domain": "test",
            "version": "1.0.0",
            "patterns": [
                {
                    "pattern_id": "existing-1",
                    "title": "Existing pattern one",
                    "frequency": 2,
                    "keywords": ["existing"]
                },
                {
                    "pattern_id": "existing-2",
                    "title": "Existing pattern two",
                    "frequency": 1,
                    "keywords": ["test"]
                }
            ]
        }"#;
        std::fs::write(dir.join("common-issues.json"), wrapper_json).unwrap();

        // Merge: one duplicate (existing-1) and one new (new-1)
        let new_patterns = vec![
            Pattern {
                pattern_id: "existing-1".to_string(),
                title: "Updated existing".to_string(),
                first_seen: String::new(),
                last_seen: "D9.1".to_string(),
                frequency: 1,
                severity: None,
                keywords: vec![],
                tech_stack: vec![],
                issue: None,
                solution: None,
                auto_apply: false,
                learned_from: None,
                used_count: 0,
                promoted_to: String::new(),
                promoted_at: String::new(),
            },
            Pattern {
                pattern_id: "new-1".to_string(),
                title: "Brand new pattern".to_string(),
                first_seen: String::new(),
                last_seen: "D9.1".to_string(),
                frequency: 1,
                severity: None,
                keywords: vec![],
                tech_stack: vec![],
                issue: None,
                solution: None,
                auto_apply: false,
                learned_from: None,
                used_count: 0,
                promoted_to: String::new(),
                promoted_at: String::new(),
            },
        ];

        let added = merge_patterns(&dir, new_patterns).unwrap();
        assert_eq!(added, 1, "only new-1 should count as added");

        // Read back -- merge_patterns writes flat array format
        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        assert_eq!(result.len(), 3, "should have existing-1, existing-2, new-1");

        let e1 = result
            .iter()
            .find(|p| p.pattern_id == "existing-1")
            .unwrap();
        assert_eq!(e1.frequency, 3, "existing-1 frequency should be 2 + 1 = 3");
        assert_eq!(e1.last_seen, "D9.1");
        assert!(e1.auto_apply, "frequency 3 should graduate to auto_apply");

        let e2 = result
            .iter()
            .find(|p| p.pattern_id == "existing-2")
            .unwrap();
        assert_eq!(e2.frequency, 1, "existing-2 should be unchanged");

        let n1 = result.iter().find(|p| p.pattern_id == "new-1");
        assert!(n1.is_some(), "new-1 should be present");

        let _ = std::fs::remove_dir_all(&dir);
    }

    use crate::complexity::TaskComplexity;

    #[test]
    fn test_scaled_injection_simple_returns_min() {
        assert_eq!(scaled_injection_count(TaskComplexity::Simple, 10, 2), 2);
    }

    #[test]
    fn test_scaled_injection_medium_returns_5_capped() {
        assert_eq!(scaled_injection_count(TaskComplexity::Medium, 10, 2), 5);
        // When max < 5, medium is capped at max
        assert_eq!(scaled_injection_count(TaskComplexity::Medium, 3, 1), 3);
    }

    #[test]
    fn test_scaled_injection_complex_returns_max() {
        assert_eq!(scaled_injection_count(TaskComplexity::Complex, 10, 2), 10);
    }

    #[test]
    fn test_scaled_injection_zero_max() {
        assert_eq!(scaled_injection_count(TaskComplexity::Complex, 0, 0), 0);
        assert_eq!(scaled_injection_count(TaskComplexity::Simple, 0, 0), 0);
    }

    fn make_test_pattern(id: &str, title: &str, freq: usize, used: usize) -> Pattern {
        Pattern {
            pattern_id: id.to_string(),
            title: title.to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: freq,
            severity: None,
            keywords: vec!["rust".to_string()],
            tech_stack: vec![],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: used,
            promoted_to: String::new(),
            promoted_at: String::new(),
        }
    }

    #[test]
    fn test_scan_citations_finds_pattern_id() {
        let patterns = vec![
            make_test_pattern("sql-injection-check", "SQL Injection Prevention", 3, 0),
            make_test_pattern("missing-error-handling", "Missing Error Handling", 2, 0),
        ];
        let text = "The reviewer noted a sql-injection-check issue in the handler.";
        let cited = scan_citations(text, &patterns);
        assert_eq!(cited, vec!["sql-injection-check"]);
    }

    #[test]
    fn test_scan_citations_finds_title() {
        let patterns = vec![
            make_test_pattern("sql-inject", "SQL Injection Prevention", 3, 0),
        ];
        let text = "This relates to SQL Injection Prevention as documented.";
        let cited = scan_citations(text, &patterns);
        assert_eq!(cited, vec!["sql-inject"]);
    }

    #[test]
    fn test_scan_citations_ignores_short_titles() {
        let patterns = vec![
            make_test_pattern("short", "Bug Fix", 1, 0),
        ];
        let text = "This is a bug fix for the handler.";
        let cited = scan_citations(text, &patterns);
        assert!(cited.is_empty(), "short titles (<8 chars) should not match");
    }

    #[test]
    fn test_scan_citations_empty_inputs() {
        let patterns = vec![make_test_pattern("test", "Test Pattern Long Enough", 1, 0)];
        assert!(scan_citations("", &patterns).is_empty());
        assert!(scan_citations("some text", &[]).is_empty());
    }

    #[test]
    fn test_usefulness_boost_high_ratio() {
        let patterns = vec![
            make_test_pattern("high-use", "High Use Pattern", 5, 3), // ratio 0.6
            make_test_pattern("low-use", "Low Use Pattern", 5, 0),  // ratio 0.0
        ];
        let scores = keyword_scores(&patterns, "rust project", &[]);
        let high_score = scores.iter().find(|(i, _)| *i == 0).map(|(_, s)| *s).unwrap_or(0);
        let low_score = scores.iter().find(|(i, _)| *i == 1).map(|(_, s)| *s).unwrap_or(0);
        assert!(
            high_score > low_score,
            "high-use pattern (score={}) should outscore never-cited pattern (score={})",
            high_score, low_score
        );
    }

    #[test]
    fn test_update_used_counts_increments() {
        let dir = std::env::temp_dir().join("foundry_test_used_counts");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns = vec![
            make_test_pattern("p1", "Pattern One Long Title", 3, 0),
            make_test_pattern("p2", "Pattern Two Long Title", 2, 1),
        ];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("common-issues.json"), &json).unwrap();

        let updated = update_used_counts(&dir, &["p1".to_string()]).unwrap();
        assert_eq!(updated, 1);

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p1 = result.iter().find(|p| p.pattern_id == "p1").unwrap();
        assert_eq!(p1.used_count, 1, "p1 should have been incremented");
        let p2 = result.iter().find(|p| p.pattern_id == "p2").unwrap();
        assert_eq!(p2.used_count, 1, "p2 should be unchanged");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_update_used_counts_scans_all_json_files() {
        let dir = std::env::temp_dir().join("foundry_test_used_counts_multi");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        // Pattern in common-issues.json (plain array format)
        let p1 = vec![make_test_pattern("p1", "Pattern In Common", 2, 0)];
        std::fs::write(
            dir.join("common-issues.json"),
            serde_json::to_string_pretty(&p1).unwrap(),
        )
        .unwrap();

        // Pattern in security.json (wrapper format with metadata)
        let wrapper_json = r#"{
            "pattern_type": "security-issues",
            "domain": "recon",
            "version": "1.0.0",
            "patterns": [
                {
                    "pattern_id": "p2",
                    "title": "Pattern In Security",
                    "frequency": 3,
                    "keywords": ["security"],
                    "used_count": 0
                }
            ]
        }"#;
        std::fs::write(dir.join("security.json"), wrapper_json).unwrap();

        let updated = update_used_counts(&dir, &["p1".to_string(), "p2".to_string()]).unwrap();
        assert_eq!(updated, 2, "should update patterns across both files");

        // Verify security.json preserved wrapper format and metadata
        let content = std::fs::read_to_string(dir.join("security.json")).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(
            parsed["pattern_type"], "security-issues",
            "wrapper metadata must be preserved"
        );
        assert_eq!(
            parsed["domain"], "recon",
            "wrapper metadata must be preserved"
        );
        assert_eq!(
            parsed["patterns"][0]["used_count"], 1,
            "p2 used_count should be incremented"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_project_tech_stack_rust() {
        let dir = std::env::temp_dir().join("foundry_test_detect_stack_rust");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("Cargo.toml"), "[package]\nname = \"test\"").unwrap();
        let stacks = detect_project_tech_stack(&dir);
        assert!(stacks.contains(&"rust".to_string()));
        assert!(!stacks.contains(&"python".to_string()));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_project_tech_stack_multiple() {
        let dir = std::env::temp_dir().join("foundry_test_detect_stack_multi");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("package.json"), "{}").unwrap();
        std::fs::write(dir.join("pyproject.toml"), "[project]").unwrap();
        let stacks = detect_project_tech_stack(&dir);
        assert!(stacks.contains(&"javascript".to_string()));
        assert!(stacks.contains(&"typescript".to_string()));
        assert!(stacks.contains(&"python".to_string()));
        assert!(!stacks.contains(&"rust".to_string()));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_project_tech_stack_empty() {
        let dir = std::env::temp_dir().join("foundry_test_detect_stack_empty");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let stacks = detect_project_tech_stack(&dir);
        assert!(stacks.is_empty());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_tech_stack_affinity_penalty() {
        let react_pattern = Pattern {
            pattern_id: "no-default-starter-css".to_string(),
            title: "Never use default starter template".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 5,
            severity: Some("HIGH".to_string()),
            keywords: vec!["css".to_string(), "styling".to_string(), "html".to_string()],
            tech_stack: vec!["html".to_string(), "css".to_string(), "react".to_string()],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
        };
        let rust_pattern = Pattern {
            pattern_id: "utf8-byte-slice-panic".to_string(),
            title: "Never slice Rust strings by byte index".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 5,
            severity: Some("HIGH".to_string()),
            keywords: vec!["rust".to_string(), "string".to_string(), "utf8".to_string()],
            tech_stack: vec!["rust".to_string()],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
        };
        let patterns = vec![react_pattern, rust_pattern];
        let rust_stack = vec!["rust".to_string()];

        // With Rust detected stack, the React pattern should be penalized
        let scores = keyword_scores(&patterns, "fix css styling in rust string handling", &rust_stack);
        let react_score = scores.iter().find(|(i, _)| *i == 0).map(|(_, s)| *s).unwrap_or(0);
        let rust_score = scores.iter().find(|(i, _)| *i == 1).map(|(_, s)| *s).unwrap_or(0);
        assert!(
            rust_score > react_score,
            "rust pattern (score={}) should outscore react pattern (score={}) in a Rust project",
            rust_score, react_score
        );

        // With empty detected stack, no penalty applied (stack-agnostic mode)
        let scores_no_stack = keyword_scores(&patterns, "fix css styling in rust string handling", &[]);
        let react_score_no_stack = scores_no_stack.iter().find(|(i, _)| *i == 0).map(|(_, s)| *s).unwrap_or(0);
        assert!(react_score_no_stack > react_score, "no-stack mode should not penalize react pattern");
    }

    #[test]
    fn test_tech_stack_affinity_empty_pattern_stack_no_penalty() {
        // Patterns with empty tech_stack are stack-agnostic and should NOT be penalized
        let agnostic_pattern = Pattern {
            pattern_id: "agnostic-pattern".to_string(),
            title: "Agnostic Pattern".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 3,
            severity: Some("MEDIUM".to_string()),
            keywords: vec!["rust".to_string()],
            tech_stack: vec![],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
        };
        let patterns = vec![agnostic_pattern];
        let rust_stack = vec!["rust".to_string()];
        let scores_with_stack = keyword_scores(&patterns, "rust project", &rust_stack);
        let scores_without_stack = keyword_scores(&patterns, "rust project", &[]);
        let score_with = scores_with_stack.iter().find(|(i, _)| *i == 0).map(|(_, s)| *s).unwrap_or(0);
        let score_without = scores_without_stack.iter().find(|(i, _)| *i == 0).map(|(_, s)| *s).unwrap_or(0);
        assert_eq!(score_with, score_without, "patterns with empty tech_stack should not be penalized");
    }

    #[test]
    fn test_promoted_patterns_excluded_from_matching() {
        let active = Pattern {
            pattern_id: "active-pattern".to_string(),
            title: "Active Pattern".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 3,
            severity: None,
            keywords: vec!["rust".to_string()],
            tech_stack: vec![],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
        };
        let promoted = Pattern {
            pattern_id: "promoted-pattern".to_string(),
            title: "Promoted Pattern".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 3,
            severity: None,
            keywords: vec!["rust".to_string()],
            tech_stack: vec![],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: "extensions/rust/CLAUDE.md".to_string(),
            promoted_at: "2026-04-07".to_string(),
        };
        let patterns = vec![active, promoted];
        let matched = match_patterns(&patterns, "rust project", &[]);
        assert_eq!(matched.len(), 1, "only active pattern should match");
        assert_eq!(matched[0].pattern_id, "active-pattern");
    }

    #[test]
    fn test_promoted_patterns_excluded_from_keyword_scores() {
        let active = Pattern {
            pattern_id: "active-pattern".to_string(),
            title: "Active Pattern".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 3,
            severity: None,
            keywords: vec!["rust".to_string()],
            tech_stack: vec![],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
        };
        let promoted = Pattern {
            pattern_id: "promoted-pattern".to_string(),
            title: "Promoted Pattern".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 3,
            severity: None,
            keywords: vec!["rust".to_string()],
            tech_stack: vec![],
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: "extensions/rust/CLAUDE.md".to_string(),
            promoted_at: "2026-04-07".to_string(),
        };
        let patterns = vec![active, promoted];
        let scores = keyword_scores(&patterns, "rust project", &[]);
        let indices: Vec<usize> = scores.iter().map(|(i, _)| *i).collect();
        assert!(indices.contains(&0), "active pattern index should be present");
        assert!(!indices.contains(&1), "promoted pattern index should NOT be present");
    }

    #[test]
    fn test_load_patterns_with_sources() {
        let dir = std::env::temp_dir().join("foundry_test_load_with_sources");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns_json = serde_json::to_string_pretty(&vec![
            make_test_pattern("src-1", "Source Pattern One", 1, 0),
            make_test_pattern("src-2", "Source Pattern Two", 2, 0),
        ]).unwrap();
        let json_path = dir.join("test-patterns.json");
        std::fs::write(&json_path, &patterns_json).unwrap();

        let results = load_patterns_with_sources(&dir);
        assert_eq!(results.len(), 2, "should load both patterns");
        for (_, path) in &results {
            assert_eq!(path, &json_path, "source path should match");
        }
        let ids: Vec<&str> = results.iter().map(|(p, _)| p.pattern_id.as_str()).collect();
        assert!(ids.contains(&"src-1"));
        assert!(ids.contains(&"src-2"));

        let _ = std::fs::remove_dir_all(&dir);
    }
}

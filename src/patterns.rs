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
/// Falls back to /tmp/.foundry/patterns if HOME is unset (e.g., containers).
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

            // Usefulness tracking: boost patterns agents actually cite, demote noise
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
        let scores = keyword_scores(&patterns, "rust project");
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
}

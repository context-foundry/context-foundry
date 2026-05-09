use anyhow::Result;
use chrono::{NaiveDate, Utc};
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
    #[serde(default, deserialize_with = "deserialize_pattern_solution")]
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
    /// ISO date when agents last cited this pattern (e.g. "2026-04-09").
    /// Updated automatically by update_used_counts(). Used for time-based decay.
    #[serde(default)]
    pub last_used_at: Option<String>,
    /// How many times this pattern was cited in a task that ended in feat() (PASS).
    /// Used by Pattern::success_rate(). Updated automatically by update_used_counts().
    #[serde(default)]
    pub cited_in_pass: usize,
    /// How many times this pattern was cited in a task that ended in WIP() (FAIL).
    /// Used by Pattern::success_rate(). Updated automatically by update_used_counts().
    #[serde(default)]
    pub cited_in_wip: usize,
    /// Per-stage citation counts. Keys are agent role slugs in lowercase
    /// ("planner", "builder", "reviewer", "scout"). Empty by default.
    /// Updated by update_used_counts() when threaded with a stage attribution.
    #[serde(default)]
    pub cited_by_stage: HashMap<String, usize>,
}

/// Feedback signal from a builder agent about a pattern's quality.
#[derive(Debug, Clone, PartialEq)]
pub enum PatternFeedback {
    /// Pattern was helpful and correct
    Confirmed(String),
    /// Pattern is outdated or wrong
    Stale(String),
    /// Pattern is actively harmful/misleading
    Wrong(String),
}

/// Outcome of the task that cited a pattern. Threaded into update_used_counts to
/// distinguish pass-cited patterns from wip-cited patterns.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CommitOutcome {
    Pass,
    Wip,
}

impl Pattern {
    /// Compute a dynamic star rating (0.0 to 5.0) based on usage recency,
    /// citation ratio, and frequency. Higher is better.
    pub fn rating(&self) -> f32 {
        let mut score: f32 = 0.0;

        // Base: frequency contributes up to 1.5 stars (log scale, caps at ~20 occurrences)
        let freq_score = (self.frequency as f32).ln_1p().min(3.0) * 0.5;
        score += freq_score;

        // Citation ratio: up to 2.0 stars for patterns agents actually reference
        if self.frequency > 0 {
            let ratio = self.used_count as f32 / self.frequency as f32;
            score += ratio.min(1.0) * 2.0;
        }

        // Recency: up to 1.5 stars, decaying over 90 days from last use
        if let Some(ref date_str) = self.last_used_at {
            if let Ok(last_used) = NaiveDate::parse_from_str(date_str, "%Y-%m-%d") {
                let today = Utc::now().date_naive();
                let days_ago = (today - last_used).num_days().max(0) as f32;
                let recency = (1.0 - days_ago / 90.0).max(0.0);
                score += recency * 1.5;
            }
        }

        score.min(5.0)
    }

    /// Return a star display string (e.g. "3.2" rendered as context for prompts).
    pub fn star_display(&self) -> String {
        format!("{:.1}/5", self.rating())
    }

    /// Fraction of pass-cited / total cited. Defaults to 1.0 (neutral) when no
    /// citations are recorded so unproven patterns are not penalized.
    pub fn success_rate(&self) -> f64 {
        let total = self.cited_in_pass + self.cited_in_wip;
        if total == 0 {
            return 1.0_f64;
        }
        self.cited_in_pass as f64 / total as f64
    }
}

// ─── Solution deserializer ───────────────────────────────
fn deserialize_pattern_solution<'de, D>(
    deserializer: D,
) -> Result<Option<PatternSolution>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    use serde::de::Error;
    let value = serde_json::Value::deserialize(deserializer)?;
    match value {
        serde_json::Value::Null => Ok(None),
        serde_json::Value::String(s) => Ok(Some(PatternSolution {
            planner: s.clone(),
            reviewer: s,
        })),
        serde_json::Value::Object(_) => {
            let sol: PatternSolution = serde_json::from_value(value).map_err(Error::custom)?;
            Ok(Some(sol))
        }
        other => Err(Error::custom(format!(
            "expected solution to be a string, object, or null, got: {}",
            other
        ))),
    }
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
        eprintln!(
            "warning: HOME not set, using {} for pattern storage",
            fallback.display()
        );
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

/// Convenience: load all patterns from `~/.foundry/patterns/`.
pub fn load_patterns_from_global() -> Vec<Pattern> {
    let dir = resolve_patterns_dir("~/.foundry/patterns");
    load_patterns(&dir)
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
pub fn match_patterns<'a>(
    patterns: &'a [Pattern],
    task_desc: &str,
    detected_stack: &[String],
) -> Vec<&'a Pattern> {
    let scored = keyword_scores(patterns, task_desc, detected_stack);
    let mut result: Vec<(&Pattern, usize)> = scored
        .into_iter()
        .filter(|(_, score)| *score > 0)
        .map(|(idx, score)| (&patterns[idx], score))
        .collect();
    result.sort_by_key(|a| std::cmp::Reverse(a.1));
    result.into_iter().map(|(p, _)| p).collect()
}

/// Returns (pattern_index, keyword_score) pairs for all patterns.
/// Used by the semantic matcher as the keyword baseline for reranking.
pub fn keyword_scores(
    patterns: &[Pattern],
    task_desc: &str,
    detected_stack: &[String],
) -> Vec<(usize, usize)> {
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

            // Star rating: composite score from citation ratio, recency, and frequency.
            // Replaces the old ad-hoc usefulness tracking with a unified metric.
            if score > 0 {
                let rating = p.rating();
                if rating >= 3.0 {
                    score += 3; // high-value pattern
                } else if rating >= 1.5 {
                    score += 1; // moderate-value pattern
                } else if p.frequency >= 5 {
                    score = score.saturating_sub(2); // low-rated despite many appearances = noise
                }
            }

            // Tech-stack affinity: penalize patterns from unrelated domains
            if score > 0 && !detected_stack.is_empty() && !p.tech_stack.is_empty() {
                let has_match = p.tech_stack.iter().any(|ts| {
                    let ts_lower = ts.to_lowercase();
                    detected_stack
                        .iter()
                        .any(|ds| ds.to_lowercase() == ts_lower)
                });
                if !has_match {
                    score = score.saturating_sub(3);
                }
            }

            // Success-rate factor: 0.5 + 0.5 * success_rate.
            // Pristine new patterns have neutral 1.0; 0%-pass patterns are halved.
            if score > 0 {
                let sr = p.success_rate();
                let factor = 0.5_f64 + 0.5_f64 * sr;
                score = ((score as f64) * factor).round() as usize;
            }

            if score > 0 {
                Some((i, score))
            } else {
                None
            }
        })
        .collect()
}

/// Stage-aware keyword ranker. Calls `keyword_scores` for the base score, then
/// applies a per-stage attribution boost/penalty and an exponential recency decay.
#[allow(dead_code)]
pub fn keyword_scores_for_stage(
    patterns: &[Pattern],
    task_desc: &str,
    detected_stack: &[String],
    stage: &str,
) -> Vec<(usize, usize)> {
    let base = keyword_scores(patterns, task_desc, detected_stack);
    let stage_lc = stage.to_lowercase();
    let today = Utc::now().date_naive();

    base.into_iter()
        .filter_map(|(idx, mut score)| {
            // Stage attribution: boost if cited in this stage, penalize if only in others.
            let cby = &patterns[idx].cited_by_stage;
            let total: usize = cby.values().sum();
            let this_stage = cby.get(&stage_lc).copied().unwrap_or(0);
            if total > 0 && this_stage > 0 {
                score = score.saturating_add(1);
            } else if total > 0 && this_stage == 0 {
                score = score.saturating_sub(1);
            }

            // Recency decay: exp(-days_ago / 90), floored at 0.1.
            if let Some(date_str) = patterns[idx].last_used_at.as_ref() {
                if let Ok(last_used) = NaiveDate::parse_from_str(date_str, "%Y-%m-%d") {
                    let days_ago = (today - last_used).num_days().max(0) as f64;
                    let decay = (-days_ago / 90.0_f64).exp().max(0.1_f64);
                    score = ((score as f64) * decay).round() as usize;
                }
            }

            if score > 0 {
                Some((idx, score))
            } else {
                None
            }
        })
        .collect()
}

/// Convenience wrapper mirroring `match_patterns` but using the stage-aware ranker.
#[allow(dead_code)]
pub fn match_patterns_for_stage<'a>(
    patterns: &'a [Pattern],
    task_desc: &str,
    detected_stack: &[String],
    stage: &str,
) -> Vec<&'a Pattern> {
    let scored = keyword_scores_for_stage(patterns, task_desc, detected_stack, stage);
    let mut result: Vec<(&Pattern, usize)> = scored
        .into_iter()
        .filter(|(_, score)| *score > 0)
        .map(|(idx, score)| (&patterns[idx], score))
        .collect();
    result.sort_by_key(|a| std::cmp::Reverse(a.1));
    result.into_iter().map(|(p, _)| p).collect()
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
            "### {}. {} [{}] (seen {}x, rating {}{})  \n",
            i + 1,
            p.title,
            p.pattern_id,
            p.frequency,
            p.star_display(),
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
            let id_match = text_words
                .iter()
                .any(|w| w.trim_matches(|c: char| !c.is_alphanumeric() && c != '-') == id_lower);
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

/// Increment used_count and stamp last_used_at for cited patterns across all JSON files in a directory.
/// Mirrors load_patterns() behavior: scans every *.json file, not just common-issues.json.
/// Also tallies pass/wip success counts and per-stage citation counts.
/// `cited_by_role` is a list of `(pattern_id, role)` pairs; duplicates are tallied per stage.
/// Returns the total number of distinct (pattern, file) updates.
pub fn update_used_counts(
    dir: &Path,
    cited_by_role: &[(String, String)],
    outcome: CommitOutcome,
) -> Result<usize> {
    if cited_by_role.is_empty() {
        return Ok(0);
    }

    let today = Utc::now().format("%Y-%m-%d").to_string();

    // Deduplicated set of pattern_ids -- used as the primary "did this pattern get cited" filter.
    let cited_ids: Vec<String> = {
        let mut v: Vec<String> = cited_by_role.iter().map(|(pid, _)| pid.clone()).collect();
        v.sort();
        v.dedup();
        v
    };

    // Per-pattern stage tally. role is lowercased so storage matches keyword_scores_for_stage().
    let mut stage_counts: HashMap<String, HashMap<String, usize>> = HashMap::new();
    for (pid, role) in cited_by_role {
        let role_lc = role.to_lowercase();
        *stage_counts
            .entry(pid.clone())
            .or_default()
            .entry(role_lc)
            .or_insert(0) += 1;
    }

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return Ok(0),
    };

    let apply_to_pattern = |p: &mut Pattern| {
        p.used_count += 1;
        p.last_used_at = Some(today.clone());
        match outcome {
            CommitOutcome::Pass => p.cited_in_pass += 1,
            CommitOutcome::Wip => p.cited_in_wip += 1,
        }
        if let Some(role_map) = stage_counts.get(&p.pattern_id) {
            for (role, count) in role_map {
                *p.cited_by_stage.entry(role.clone()).or_insert(0) += count;
            }
        }
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
                    apply_to_pattern(p);
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
                    apply_to_pattern(p);
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
                apply_to_pattern(&mut pattern);
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

    let today = Utc::now().format("%Y-%m-%d").to_string();
    let mut added = 0usize;

    for np in new_patterns {
        if let Some(&idx) = by_id.get(&np.pattern_id) {
            // Update existing: add incoming frequency (at least 1), stamp last_seen with today
            existing[idx].frequency += np.frequency.max(1);
            existing[idx].last_seen = today.clone();
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

/// Decay stale patterns: disable auto_apply for patterns not used in `decay_days`.
/// Writes changes back to disk. Returns the number of patterns decayed.
pub fn decay_stale_patterns(dir: &Path, decay_days: i64) -> usize {
    let today = Utc::now().date_naive();
    let mut total_decayed = 0usize;

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return 0,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let decay_pattern = |p: &mut Pattern| -> bool {
            if !p.auto_apply || !p.promoted_to.is_empty() {
                return false;
            }
            match &p.last_used_at {
                Some(date_str) => {
                    // Has been cited before -- decay if last citation is old enough
                    let Ok(last_date) = NaiveDate::parse_from_str(date_str, "%Y-%m-%d") else {
                        return false;
                    };
                    let days_inactive = (today - last_date).num_days();
                    if days_inactive >= decay_days {
                        p.auto_apply = false;
                        return true;
                    }
                    false
                }
                None => {
                    // Never cited by any agent. If auto_apply was set purely
                    // from frequency (merge_patterns promotes at freq >= 3),
                    // this pattern has been injected but never referenced.
                    // Decay it -- auto_apply should require proven usefulness.
                    if p.frequency >= 5 && p.used_count == 0 {
                        p.auto_apply = false;
                        return true;
                    }
                    false
                }
            }
        };

        // Try wrapper format
        if let Ok(mut wrapper) = serde_json::from_str::<PatternWrapper>(&content) {
            let mut file_decayed = 0usize;
            for p in &mut wrapper.patterns {
                if decay_pattern(p) {
                    file_decayed += 1;
                }
            }
            if file_decayed > 0 {
                if let Ok(json) = serde_json::to_string_pretty(&wrapper) {
                    let _ = atomic_write_file(&path, json.as_bytes());
                }
                total_decayed += file_decayed;
            }
            continue;
        }

        // Plain array
        if let Ok(mut patterns) = serde_json::from_str::<Vec<Pattern>>(&content) {
            let mut file_decayed = 0usize;
            for p in &mut patterns {
                if decay_pattern(p) {
                    file_decayed += 1;
                }
            }
            if file_decayed > 0 {
                if let Ok(json) = serde_json::to_string_pretty(&patterns) {
                    let _ = atomic_write_file(&path, json.as_bytes());
                }
                total_decayed += file_decayed;
            }
            continue;
        }

        // Single pattern
        if let Ok(mut pattern) = serde_json::from_str::<Pattern>(&content) {
            if decay_pattern(&mut pattern) {
                if let Ok(json) = serde_json::to_string_pretty(&pattern) {
                    let _ = atomic_write_file(&path, json.as_bytes());
                }
                total_decayed += 1;
            }
        }
    }

    total_decayed
}

/// Parse PATTERN_FEEDBACK markers from builder output.
/// Format: `PATTERN_FEEDBACK: pattern-id | confirmed|stale|wrong | optional reason`
pub fn parse_pattern_feedback(text: &str) -> Vec<(String, PatternFeedback)> {
    let mut results = Vec::new();
    for line in text.lines() {
        let trimmed = line.trim();
        if !trimmed.starts_with("PATTERN_FEEDBACK:") {
            continue;
        }
        let rest = trimmed.trim_start_matches("PATTERN_FEEDBACK:").trim();
        let parts: Vec<&str> = rest.splitn(3, '|').map(|s| s.trim()).collect();
        if parts.len() < 2 {
            continue;
        }
        let pattern_id = parts[0].to_string();
        let reason = parts.get(2).unwrap_or(&"").to_string();
        let feedback = match parts[1].to_lowercase().as_str() {
            "confirmed" => PatternFeedback::Confirmed(reason),
            "stale" => PatternFeedback::Stale(reason),
            "wrong" => PatternFeedback::Wrong(reason),
            _ => continue,
        };
        results.push((pattern_id, feedback));
    }
    results
}

/// Apply feedback to patterns on disk. Confirmed patterns get used_count bumped
/// and last_used_at stamped. Stale/wrong patterns get auto_apply disabled.
/// Returns count of patterns modified.
pub fn apply_feedback(dir: &Path, feedback: &[(String, PatternFeedback)]) -> Result<usize> {
    if feedback.is_empty() {
        return Ok(0);
    }

    let today = Utc::now().format("%Y-%m-%d").to_string();

    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return Ok(0),
    };

    let mut total = 0usize;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let apply_to_pattern = |p: &mut Pattern, today: &str| -> bool {
            let Some((_, fb)) = feedback.iter().find(|(id, _)| *id == p.pattern_id) else {
                return false;
            };
            match fb {
                PatternFeedback::Confirmed(_) => {
                    p.used_count += 1;
                    p.last_used_at = Some(today.to_string());
                }
                PatternFeedback::Stale(_) | PatternFeedback::Wrong(_) => {
                    p.auto_apply = false;
                }
            }
            true
        };

        // Try wrapper
        if let Ok(mut wrapper) = serde_json::from_str::<PatternWrapper>(&content) {
            let mut changed = 0usize;
            for p in &mut wrapper.patterns {
                if apply_to_pattern(p, &today) {
                    changed += 1;
                }
            }
            if changed > 0 {
                let json = serde_json::to_string_pretty(&wrapper)?;
                atomic_write_file(&path, json.as_bytes())?;
                total += changed;
            }
            continue;
        }

        // Plain array
        if let Ok(mut patterns) = serde_json::from_str::<Vec<Pattern>>(&content) {
            let mut changed = 0usize;
            for p in &mut patterns {
                if apply_to_pattern(p, &today) {
                    changed += 1;
                }
            }
            if changed > 0 {
                let json = serde_json::to_string_pretty(&patterns)?;
                atomic_write_file(&path, json.as_bytes())?;
                total += changed;
            }
            continue;
        }

        // Single
        if let Ok(mut pattern) = serde_json::from_str::<Pattern>(&content) {
            if apply_to_pattern(&mut pattern, &today) {
                let json = serde_json::to_string_pretty(&pattern)?;
                atomic_write_file(&path, json.as_bytes())?;
                total += 1;
            }
        }
    }

    Ok(total)
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
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
                last_used_at: None,
                cited_in_pass: 0,
                cited_in_wip: 0,
                cited_by_stage: HashMap::new(),
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
                last_used_at: None,
                cited_in_pass: 0,
                cited_in_wip: 0,
                cited_by_stage: HashMap::new(),
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
        // last_seen is now stamped as today's ISO date, not the task_id
        assert!(!e1.last_seen.is_empty(), "last_seen should be set");
        assert!(
            e1.last_seen.contains('-'),
            "last_seen should be ISO date format"
        );
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
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
        let patterns = vec![make_test_pattern(
            "sql-inject",
            "SQL Injection Prevention",
            3,
            0,
        )];
        let text = "This relates to SQL Injection Prevention as documented.";
        let cited = scan_citations(text, &patterns);
        assert_eq!(cited, vec!["sql-inject"]);
    }

    #[test]
    fn test_scan_citations_ignores_short_titles() {
        let patterns = vec![make_test_pattern("short", "Bug Fix", 1, 0)];
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
            make_test_pattern("low-use", "Low Use Pattern", 5, 0),   // ratio 0.0
        ];
        let scores = keyword_scores(&patterns, "rust project", &[]);
        let high_score = scores
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        let low_score = scores
            .iter()
            .find(|(i, _)| *i == 1)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert!(
            high_score > low_score,
            "high-use pattern (score={}) should outscore never-cited pattern (score={})",
            high_score,
            low_score
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

        let cites: Vec<(String, String)> = vec![("p1".to_string(), "builder".to_string())];
        let updated = update_used_counts(&dir, &cites, CommitOutcome::Pass).unwrap();
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

        let cites: Vec<(String, String)> = vec![
            ("p1".to_string(), "builder".to_string()),
            ("p2".to_string(), "builder".to_string()),
        ];
        let updated = update_used_counts(&dir, &cites, CommitOutcome::Pass).unwrap();
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
        };
        let patterns = vec![react_pattern, rust_pattern];
        let rust_stack = vec!["rust".to_string()];

        // With Rust detected stack, the React pattern should be penalized
        let scores = keyword_scores(
            &patterns,
            "fix css styling in rust string handling",
            &rust_stack,
        );
        let react_score = scores
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        let rust_score = scores
            .iter()
            .find(|(i, _)| *i == 1)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert!(
            rust_score > react_score,
            "rust pattern (score={}) should outscore react pattern (score={}) in a Rust project",
            rust_score,
            react_score
        );

        // With empty detected stack, no penalty applied (stack-agnostic mode)
        let scores_no_stack =
            keyword_scores(&patterns, "fix css styling in rust string handling", &[]);
        let react_score_no_stack = scores_no_stack
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert!(
            react_score_no_stack > react_score,
            "no-stack mode should not penalize react pattern"
        );
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
        };
        let patterns = vec![agnostic_pattern];
        let rust_stack = vec!["rust".to_string()];
        let scores_with_stack = keyword_scores(&patterns, "rust project", &rust_stack);
        let scores_without_stack = keyword_scores(&patterns, "rust project", &[]);
        let score_with = scores_with_stack
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        let score_without = scores_without_stack
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert_eq!(
            score_with, score_without,
            "patterns with empty tech_stack should not be penalized"
        );
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
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
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
        };
        let patterns = vec![active, promoted];
        let scores = keyword_scores(&patterns, "rust project", &[]);
        let indices: Vec<usize> = scores.iter().map(|(i, _)| *i).collect();
        assert!(
            indices.contains(&0),
            "active pattern index should be present"
        );
        assert!(
            !indices.contains(&1),
            "promoted pattern index should NOT be present"
        );
    }

    #[test]
    fn test_load_patterns_with_sources() {
        let dir = std::env::temp_dir().join("foundry_test_load_with_sources");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns_json = serde_json::to_string_pretty(&vec![
            make_test_pattern("src-1", "Source Pattern One", 1, 0),
            make_test_pattern("src-2", "Source Pattern Two", 2, 0),
        ])
        .unwrap();
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

    #[test]
    fn test_rating_fresh_high_use() {
        let today = Utc::now().format("%Y-%m-%d").to_string();
        let mut p = make_test_pattern("rated", "Rated Pattern", 10, 8);
        p.last_used_at = Some(today);
        let r = p.rating();
        assert!(
            r >= 3.0,
            "high-use recently-used pattern should rate 3+, got {}",
            r
        );
    }

    #[test]
    fn test_rating_stale_unused() {
        let mut p = make_test_pattern("stale", "Stale Pattern", 10, 0);
        p.last_used_at = Some("2020-01-01".to_string());
        let r = p.rating();
        assert!(
            r < 2.0,
            "stale never-cited pattern should rate below 2.0, got {}",
            r
        );
        assert_eq!(p.star_display(), format!("{r:.1}/5"));
    }

    #[test]
    fn test_rating_no_dates() {
        let p = make_test_pattern("new", "New Pattern", 1, 0);
        let r = p.rating();
        assert!(
            (0.0..=5.0).contains(&r),
            "rating should be in range, got {}",
            r
        );
    }

    #[test]
    fn test_parse_pattern_feedback() {
        let text = "some output\nPATTERN_FEEDBACK: sql-inject-001 | confirmed | worked great\nmore output\nPATTERN_FEEDBACK: stale-pattern | stale | no longer relevant\nPATTERN_FEEDBACK: bad-pattern | wrong | caused errors\n";
        let fb = parse_pattern_feedback(text);
        assert_eq!(fb.len(), 3);
        assert_eq!(fb[0].0, "sql-inject-001");
        assert!(matches!(fb[0].1, PatternFeedback::Confirmed(_)));
        assert_eq!(fb[1].0, "stale-pattern");
        assert!(matches!(fb[1].1, PatternFeedback::Stale(_)));
        assert_eq!(fb[2].0, "bad-pattern");
        assert!(matches!(fb[2].1, PatternFeedback::Wrong(_)));
    }

    #[test]
    fn test_parse_pattern_feedback_empty() {
        let fb = parse_pattern_feedback("no feedback here");
        assert!(fb.is_empty());
    }

    #[test]
    fn test_decay_stale_patterns() {
        let dir = std::env::temp_dir().join("foundry_test_decay");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let mut fresh = make_test_pattern("fresh", "Fresh Pattern", 5, 3);
        fresh.auto_apply = true;
        fresh.last_used_at = Some(Utc::now().format("%Y-%m-%d").to_string());

        let mut stale = make_test_pattern("stale", "Stale Pattern", 5, 1);
        stale.auto_apply = true;
        stale.last_used_at = Some("2020-01-01".to_string());

        let patterns = vec![fresh, stale];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("test.json"), &json).unwrap();

        let decayed = decay_stale_patterns(&dir, 90);
        assert_eq!(decayed, 1, "only stale pattern should be decayed");

        let content = std::fs::read_to_string(dir.join("test.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let fresh_p = result.iter().find(|p| p.pattern_id == "fresh").unwrap();
        assert!(fresh_p.auto_apply, "fresh pattern should keep auto_apply");
        let stale_p = result.iter().find(|p| p.pattern_id == "stale").unwrap();
        assert!(!stale_p.auto_apply, "stale pattern should lose auto_apply");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_decay_never_cited_auto_apply_pattern() {
        // Regression: merge_patterns() can set auto_apply=true at freq>=3
        // without ever setting last_used_at. These never-cited patterns
        // must still decay rather than staying auto_apply forever.
        let dir = std::env::temp_dir().join("foundry_test_decay_never_cited");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let mut never_cited = make_test_pattern("never-cited", "Never Cited Pattern", 5, 0);
        never_cited.auto_apply = true;
        // last_used_at is None (never cited by any agent)

        let mut low_freq = make_test_pattern("low-freq", "Low Freq Pattern", 2, 0);
        low_freq.auto_apply = true;
        // freq < 5, should not decay via the never-cited path

        let mut mid_freq = make_test_pattern("mid-freq", "Mid Freq Pattern", 4, 0);
        mid_freq.auto_apply = true;
        // freq < 5, should not decay via the never-cited path

        let patterns = vec![never_cited, low_freq, mid_freq];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("test.json"), &json).unwrap();

        let decayed = decay_stale_patterns(&dir, 90);
        assert_eq!(decayed, 1, "only never-cited freq>=5 pattern should decay");

        let content = std::fs::read_to_string(dir.join("test.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let nc = result
            .iter()
            .find(|p| p.pattern_id == "never-cited")
            .unwrap();
        assert!(
            !nc.auto_apply,
            "never-cited auto_apply pattern should lose auto_apply"
        );
        let lf = result.iter().find(|p| p.pattern_id == "low-freq").unwrap();
        assert!(lf.auto_apply, "low-freq pattern should keep auto_apply");
        let mf = result.iter().find(|p| p.pattern_id == "mid-freq").unwrap();
        assert!(mf.auto_apply, "mid-freq pattern should keep auto_apply");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_apply_feedback_keeps_used_count_for_stale_patterns() {
        let dir = std::env::temp_dir().join("foundry_test_apply_feedback");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let mut stale = make_test_pattern("stale", "Stale Pattern", 6, 4);
        stale.auto_apply = true;
        let json = serde_json::to_string_pretty(&vec![stale]).unwrap();
        std::fs::write(dir.join("test.json"), json).unwrap();

        let changed = apply_feedback(
            &dir,
            &[(
                "stale".to_string(),
                PatternFeedback::Stale("no longer applies".to_string()),
            )],
        )
        .unwrap();
        assert_eq!(changed, 1);

        let content = std::fs::read_to_string(dir.join("test.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let stale = result.iter().find(|p| p.pattern_id == "stale").unwrap();
        assert!(
            !stale.auto_apply,
            "stale feedback should disable auto_apply"
        );
        assert_eq!(
            stale.used_count, 4,
            "stale feedback should not rewrite historical citation counts"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_pattern_deserializes_string_solution() {
        let json = r#"{"pattern_id":"flowise-credential-must-be-uuid","title":"x","severity":"high","keywords":["credential"],"issue":"i","solution":"set credential to the UUID"}"#;
        let p: Pattern = serde_json::from_str(json).unwrap();
        let sol = p.solution.expect("solution should deserialize");
        assert_eq!(sol.planner, "set credential to the UUID");
        assert_eq!(sol.reviewer, "set credential to the UUID");
    }

    #[test]
    fn test_pattern_deserializes_object_solution() {
        let json = r#"{"pattern_id":"x","title":"y","solution":{"planner":"P","reviewer":"R"}}"#;
        let p: Pattern = serde_json::from_str(json).unwrap();
        let sol = p.solution.unwrap();
        assert_eq!(sol.planner, "P");
        assert_eq!(sol.reviewer, "R");
    }

    #[test]
    fn test_load_patterns_single_object_with_string_solution() {
        let dir = std::env::temp_dir().join("foundry_test_single_string_solution");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let json_literal = r#"{
  "pattern_id": "flowise-credential-must-be-uuid",
  "title": "Model config credential field must be the credential UUID",
  "severity": "high",
  "keywords": ["credential", "FLOWISE_CREDENTIAL_ID"],
  "issue": "Setting modelConfig.credential to a display name causes the dropdown to show blank.",
  "solution": "Set modelConfig.credential to the credential UUID."
}"#;
        std::fs::write(dir.join("flowise-credential.json"), json_literal).unwrap();

        let patterns = load_patterns(&dir);
        assert_eq!(patterns.len(), 1);
        assert_eq!(patterns[0].pattern_id, "flowise-credential-must-be-uuid");
        let sol = patterns[0].solution.as_ref().unwrap();
        assert!(sol.planner.contains("UUID"));
        assert!(sol.reviewer.contains("UUID"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_update_used_counts_stamps_last_used_at() {
        let dir = std::env::temp_dir().join("foundry_test_used_counts_date");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns = vec![make_test_pattern("p1", "Pattern One Long", 3, 0)];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("test.json"), &json).unwrap();

        let cites: Vec<(String, String)> = vec![("p1".to_string(), "builder".to_string())];
        update_used_counts(&dir, &cites, CommitOutcome::Pass).unwrap();

        let content = std::fs::read_to_string(dir.join("test.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p1 = result.iter().find(|p| p.pattern_id == "p1").unwrap();
        assert!(p1.last_used_at.is_some(), "last_used_at should be set");
        assert!(
            p1.last_used_at.as_ref().unwrap().contains('-'),
            "should be ISO date"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    // ─── T1.3a: success-rate tracking ───────────────────────────

    #[test]
    fn test_success_rate_neutral_for_unused() {
        let p = make_test_pattern("p", "Untouched Pattern Title", 1, 0);
        assert_eq!(p.success_rate(), 1.0);
    }

    #[test]
    fn test_success_rate_half_for_one_each() {
        let mut p = make_test_pattern("p", "Half Half Pattern Title", 1, 0);
        p.cited_in_pass = 1;
        p.cited_in_wip = 1;
        assert_eq!(p.success_rate(), 0.5);
    }

    #[test]
    fn test_success_rate_one_for_all_pass() {
        let mut p = make_test_pattern("p", "All Pass Pattern Title", 1, 0);
        p.cited_in_pass = 5;
        p.cited_in_wip = 0;
        assert_eq!(p.success_rate(), 1.0);
    }

    #[test]
    fn test_update_used_counts_pass_increments_cited_in_pass() {
        let dir = std::env::temp_dir().join("foundry_test_used_counts_pass");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns = vec![make_test_pattern("p1", "Pattern One Long Title", 3, 0)];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("common-issues.json"), &json).unwrap();

        let cites: Vec<(String, String)> = vec![("p1".to_string(), "builder".to_string())];
        update_used_counts(&dir, &cites, CommitOutcome::Pass).unwrap();

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p1 = result.iter().find(|p| p.pattern_id == "p1").unwrap();
        assert_eq!(p1.cited_in_pass, 1, "PASS should bump cited_in_pass");
        assert_eq!(p1.cited_in_wip, 0, "PASS should not touch cited_in_wip");
        assert_eq!(p1.used_count, 1, "used_count should still increment");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_update_used_counts_wip_increments_cited_in_wip() {
        let dir = std::env::temp_dir().join("foundry_test_used_counts_wip");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns = vec![make_test_pattern("p1", "Pattern One Long Title", 3, 0)];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("common-issues.json"), &json).unwrap();

        let cites: Vec<(String, String)> = vec![("p1".to_string(), "builder".to_string())];
        update_used_counts(&dir, &cites, CommitOutcome::Wip).unwrap();

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p1 = result.iter().find(|p| p.pattern_id == "p1").unwrap();
        assert_eq!(p1.cited_in_wip, 1, "WIP should bump cited_in_wip");
        assert_eq!(p1.cited_in_pass, 0, "WIP should not touch cited_in_pass");
        assert_eq!(p1.used_count, 1, "used_count should still increment");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_keyword_scores_success_rate_factor_halves_zero_pass() {
        let mut all_pass = make_test_pattern("all-pass", "All Pass Pattern Title", 1, 0);
        all_pass.cited_in_pass = 5;
        all_pass.cited_in_wip = 0;
        let mut all_wip = make_test_pattern("all-wip", "All Wip Pattern Title", 1, 0);
        all_wip.cited_in_pass = 0;
        all_wip.cited_in_wip = 5;
        let patterns = vec![all_pass, all_wip];

        let scores = keyword_scores(&patterns, "rust project", &[]);
        let pass_score = scores
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        let wip_score = scores
            .iter()
            .find(|(i, _)| *i == 1)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert!(
            pass_score > wip_score,
            "all-pass score ({}) should beat all-wip score ({})",
            pass_score,
            wip_score
        );
    }

    #[test]
    fn test_keyword_scores_unproven_patterns_not_penalized() {
        // Use a pattern with citation ratio 0.6 + frequency 5 to push base score even and high.
        let mut neutral = make_test_pattern("neutral", "Neutral Pattern Title", 5, 3);
        neutral.cited_in_pass = 0;
        neutral.cited_in_wip = 0;
        let patterns = vec![neutral];

        let scores = keyword_scores(&patterns, "rust project", &[]);
        let s = scores
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, sc)| *sc)
            .unwrap_or(0);
        // success_rate is 1.0 -> factor 1.0 -> no rounding loss.
        // Score should still be > 0 (was non-zero pre-T1.3a).
        assert!(s > 0, "neutral pattern should keep its score (got {})", s);
    }

    // ─── T1.3b: per-stage attribution + recency decay ───────────

    #[test]
    fn test_update_used_counts_records_stage() {
        let dir = std::env::temp_dir().join("foundry_test_records_stage");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns = vec![make_test_pattern("p1", "Stage Recording Pattern Title", 3, 0)];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("common-issues.json"), &json).unwrap();

        let cites: Vec<(String, String)> = vec![("p1".to_string(), "Planner".to_string())];
        update_used_counts(&dir, &cites, CommitOutcome::Pass).unwrap();

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p1 = result.iter().find(|p| p.pattern_id == "p1").unwrap();
        assert_eq!(p1.cited_by_stage.get("planner").copied(), Some(1));
        assert!(p1.cited_by_stage.get("reviewer").is_none());
        assert!(p1.cited_by_stage.get("builder").is_none());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_update_used_counts_aggregates_stages() {
        let dir = std::env::temp_dir().join("foundry_test_aggregates_stages");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let patterns = vec![make_test_pattern("p1", "Aggregated Stages Pattern Title", 3, 0)];
        let json = serde_json::to_string_pretty(&patterns).unwrap();
        std::fs::write(dir.join("common-issues.json"), &json).unwrap();

        let cites: Vec<(String, String)> = vec![
            ("p1".to_string(), "Planner".to_string()),
            ("p1".to_string(), "Reviewer".to_string()),
            ("p1".to_string(), "Planner".to_string()),
        ];
        update_used_counts(&dir, &cites, CommitOutcome::Pass).unwrap();

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p1 = result.iter().find(|p| p.pattern_id == "p1").unwrap();
        assert_eq!(p1.cited_by_stage.get("planner").copied(), Some(2));
        assert_eq!(p1.cited_by_stage.get("reviewer").copied(), Some(1));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_citation_pipeline_end_to_end_pass() {
        let dir = std::env::temp_dir().join("foundry_test_citation_e2e_pass");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let pat1 = make_test_pattern("pat-injected", "End To End Test Pattern Title", 3, 0);
        let pat2 = make_test_pattern("pat-uninjected", "Other Unrelated Pattern Title", 1, 0);
        let json = serde_json::to_string_pretty(&vec![pat1, pat2]).unwrap();
        std::fs::write(dir.join("common-issues.json"), &json).unwrap();

        let planner_text = "## Plan\n- We will avoid the issue described in [pat-injected].\n";
        let builder_text = "## Build claims\n- Implemented per [pat-injected] guidance.\n";
        let reviewer_text = "## Review\n- No findings related to [pat-injected].\n";

        let loaded = load_patterns(&dir);
        assert_eq!(loaded.len(), 2);

        let mut cited_by_role: Vec<(String, String)> = Vec::new();
        for (text, role) in [
            (planner_text, "Planner"),
            (builder_text, "Builder"),
            (reviewer_text, "Reviewer"),
        ] {
            let cited = scan_citations(text, &loaded);
            for id in cited {
                cited_by_role.push((id, role.to_lowercase()));
            }
        }
        assert_eq!(cited_by_role.len(), 3);

        let updated = update_used_counts(&dir, &cited_by_role, CommitOutcome::Pass).unwrap();
        assert_eq!(updated, 1);

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();

        let p = result
            .iter()
            .find(|p| p.pattern_id == "pat-injected")
            .unwrap();
        assert_eq!(p.cited_in_pass, 1);
        assert_eq!(p.cited_in_wip, 0);
        assert_eq!(p.used_count, 1);
        assert!(p.last_used_at.is_some());
        assert_eq!(p.cited_by_stage.get("planner"), Some(&1));
        assert_eq!(p.cited_by_stage.get("builder"), Some(&1));
        assert_eq!(p.cited_by_stage.get("reviewer"), Some(&1));

        let other = result
            .iter()
            .find(|p| p.pattern_id == "pat-uninjected")
            .unwrap();
        assert_eq!(other.cited_in_pass, 0);
        assert_eq!(other.cited_in_wip, 0);
        assert_eq!(other.used_count, 0);
        assert!(other.cited_by_stage.is_empty());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_citation_pipeline_end_to_end_wip() {
        let dir = std::env::temp_dir().join("foundry_test_citation_e2e_wip");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let pat1 = make_test_pattern("pat-injected", "End To End Test Pattern Title", 3, 0);
        let pat2 = make_test_pattern("pat-uninjected", "Other Unrelated Pattern Title", 1, 0);
        let json = serde_json::to_string_pretty(&vec![pat1, pat2]).unwrap();
        std::fs::write(dir.join("common-issues.json"), &json).unwrap();

        let planner_text = "## Plan\n- We will avoid the issue described in [pat-injected].\n";
        let builder_text = "## Build claims\n- Implemented per [pat-injected] guidance.\n";
        let reviewer_text = "## Review\n- No findings related to [pat-injected].\n";

        let loaded = load_patterns(&dir);
        assert_eq!(loaded.len(), 2);

        let mut cited_by_role: Vec<(String, String)> = Vec::new();
        for (text, role) in [
            (planner_text, "Planner"),
            (builder_text, "Builder"),
            (reviewer_text, "Reviewer"),
        ] {
            let cited = scan_citations(text, &loaded);
            for id in cited {
                cited_by_role.push((id, role.to_lowercase()));
            }
        }
        assert_eq!(cited_by_role.len(), 3);

        update_used_counts(&dir, &cited_by_role, CommitOutcome::Wip).unwrap();

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p = result
            .iter()
            .find(|p| p.pattern_id == "pat-injected")
            .unwrap();
        assert_eq!(p.cited_in_wip, 1);
        assert_eq!(p.cited_in_pass, 0);
        assert_eq!(p.used_count, 1);
        assert_eq!(p.cited_by_stage.get("planner"), Some(&1));

        update_used_counts(&dir, &cited_by_role, CommitOutcome::Pass).unwrap();

        let content = std::fs::read_to_string(dir.join("common-issues.json")).unwrap();
        let result: Vec<Pattern> = serde_json::from_str(&content).unwrap();
        let p = result
            .iter()
            .find(|p| p.pattern_id == "pat-injected")
            .unwrap();
        assert_eq!(p.cited_in_wip, 1);
        assert_eq!(p.cited_in_pass, 1);
        assert_eq!(p.used_count, 2);
        assert_eq!(p.cited_by_stage.get("planner"), Some(&2));
        assert_eq!(p.cited_by_stage.get("builder"), Some(&2));
        assert_eq!(p.cited_by_stage.get("reviewer"), Some(&2));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_keyword_scores_for_stage_boosts_matching_stage() {
        let mut planner_pat = make_test_pattern("planner-pat", "Planner Helper Pattern Title", 1, 0);
        planner_pat.cited_by_stage.insert("planner".to_string(), 5);
        let mut reviewer_pat =
            make_test_pattern("reviewer-pat", "Reviewer Helper Pattern Title", 1, 0);
        reviewer_pat
            .cited_by_stage
            .insert("reviewer".to_string(), 5);
        let patterns = vec![planner_pat, reviewer_pat];

        let scores = keyword_scores_for_stage(&patterns, "rust project", &[], "planner");
        let p_score = scores
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        let r_score = scores
            .iter()
            .find(|(i, _)| *i == 1)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert!(
            p_score > r_score,
            "planner-cited pattern (score={}) should outscore reviewer-cited pattern (score={}) at the planner stage",
            p_score,
            r_score
        );
    }

    #[test]
    fn test_keyword_scores_for_stage_recency_decay() {
        let today = Utc::now().date_naive();
        let mut fresh = make_test_pattern("fresh", "Fresh Pattern Title", 1, 0);
        fresh.last_used_at = Some(today.format("%Y-%m-%d").to_string());
        let mut old = make_test_pattern("old", "Old Pattern Title", 1, 0);
        let old_date = today
            .checked_sub_signed(chrono::Duration::days(180))
            .unwrap();
        old.last_used_at = Some(old_date.format("%Y-%m-%d").to_string());
        let patterns = vec![fresh, old];

        let scores = keyword_scores_for_stage(&patterns, "rust project", &[], "builder");
        let fresh_score = scores
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        let old_score = scores
            .iter()
            .find(|(i, _)| *i == 1)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert!(
            fresh_score > old_score,
            "fresh pattern (score={}) should outscore 180-day-old pattern (score={})",
            fresh_score,
            old_score
        );
    }

    #[test]
    fn test_keyword_scores_for_stage_decay_floor() {
        let today = Utc::now().date_naive();
        // Use a pattern with high frequency + auto_apply for a large raw score.
        let mut p = make_test_pattern("ancient", "Ancient Pattern Title", 10, 8);
        p.auto_apply = true;
        let ancient_date = today
            .checked_sub_signed(chrono::Duration::days(365))
            .unwrap();
        p.last_used_at = Some(ancient_date.format("%Y-%m-%d").to_string());

        // First confirm raw score is large enough to survive the 0.1 floor.
        let raw = keyword_scores(&[p.clone()], "rust project", &[]);
        let raw_score = raw
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        assert!(raw_score >= 5, "raw score should be large (got {})", raw_score);

        let scores = keyword_scores_for_stage(&[p], "rust project", &[], "builder");
        let s = scores
            .iter()
            .find(|(i, _)| *i == 0)
            .map(|(_, s)| *s)
            .unwrap_or(0);
        let floor = ((raw_score as f64) * 0.1_f64).round() as usize;
        assert!(
            s >= floor,
            "decay floor (10%) should keep ancient pattern at >= {} (got {})",
            floor,
            s
        );
        assert!(s > 0, "decayed score should not be zero (got {})", s);
    }
}

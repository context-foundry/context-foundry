/// Task complexity classifier for model routing.
///
/// Classifies tasks by heuristic keyword/length analysis so the build loop
/// can route simple tasks to cheaper models and reserve expensive models
/// for complex work.
use std::sync::LazyLock;

use regex::Regex;
use serde::Serialize;

// ─── Complexity Tier ────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum TaskComplexity {
    Simple,
    Medium,
    Complex,
}

/// Per-task user override read from `[fast]` / `[strict]` flags in TASKS.md.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum TaskOverride {
    #[default]
    None,
    Fast,
    Strict,
}

impl TaskOverride {
    pub fn label(&self) -> &'static str {
        match self {
            TaskOverride::None => "",
            TaskOverride::Fast => "fast",
            TaskOverride::Strict => "strict",
        }
    }
}

/// Composition signals derived from the task description text.
#[derive(Debug, Clone, Default, Serialize)]
pub struct TaskSignals {
    pub numbered_subfeatures: usize,
    pub bundling_phrases: usize,
    pub distinct_verbs: usize,
    pub file_refs: usize,
    pub word_count: usize,
    pub bundling_score: usize,
}

/// Full classification result: tier, override applied, and the raw signals
/// that produced the tier. Returned by `classify_task_full`.
#[derive(Debug, Clone, Serialize)]
pub struct TaskClassification {
    pub tier: TaskComplexity,
    pub override_flag: TaskOverride,
    pub signals: TaskSignals,
}

// ─── Keywords ───────────────────────────────────────────────────────

const SIMPLE_KEYWORDS: &[&str] = &[
    "rename", "add", "change", "update", "fix", "set", "remove", "delete", "move", "typo", "color",
    "label", "text", "value", "flag", "toggle", "bump", "version",
];

const COMPLEX_KEYWORDS: &[&str] = &[
    "architect",
    "redesign",
    "refactor",
    "migrate",
    "rewrite",
    "system",
    "framework",
    "engine",
    "infrastructure",
    "overhaul",
];

// ─── Composition Signals ────────────────────────────────────────────

const BUNDLING_PHRASES: &[&str] = &[
    "and also",
    "and additionally",
    " plus ",
    "three layers",
    "two layers",
    "four layers",
    "(1)",
    "(2)",
    "(3)",
];

static RE_NUMBERED_SUBFEATURE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\(\s*(\d+)\s*\)").unwrap());

static RE_FILE_REF: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"`([A-Za-z0-9_\-./]+(?:[/.][A-Za-z0-9_\-./]+)+)`").unwrap());

const VERB_TOKENS: &[&str] = &[
    "add", "remove", "rename", "refactor", "wire", "upgrade", "build", "create", "delete",
    "implement", "replace", "scale", "gate", "compute", "emit", "render", "show", "parse",
    "extract", "inject", "split", "merge", "fix", "update", "introduce",
];

fn count_numbered_subfeatures(lower: &str) -> usize {
    let mut set: std::collections::HashSet<String> = std::collections::HashSet::new();
    for caps in RE_NUMBERED_SUBFEATURE.captures_iter(lower) {
        set.insert(caps[1].to_string());
    }
    set.len()
}

fn count_bundling_phrases(lower: &str) -> usize {
    BUNDLING_PHRASES.iter().filter(|p| lower.contains(*p)).count()
}

fn count_distinct_verbs(lower: &str) -> usize {
    let lead = lower.split('.').next().unwrap_or("");
    let scan = if lead.len() < 3 { lower } else { lead };
    let mut count = 0;
    for verb in VERB_TOKENS {
        if scan.contains(&format!(" {} ", verb)) || scan.starts_with(&format!("{} ", verb)) {
            count += 1;
        }
    }
    count
}

fn count_file_refs(text: &str) -> usize {
    let mut set: std::collections::HashSet<String> = std::collections::HashSet::new();
    for caps in RE_FILE_REF.captures_iter(text) {
        set.insert(caps[1].to_string());
    }
    set.len()
}

fn count_words(text: &str) -> usize {
    text.split_whitespace().count()
}

fn compute_signals(task_desc: &str) -> TaskSignals {
    let lower = task_desc.to_lowercase();
    let numbered_subfeatures = count_numbered_subfeatures(&lower);
    let bundling_phrases = count_bundling_phrases(&lower);
    let distinct_verbs = count_distinct_verbs(&lower);
    let file_refs = count_file_refs(task_desc);
    let word_count = count_words(task_desc);
    let bundling_score = numbered_subfeatures.saturating_add(bundling_phrases)
        + (if distinct_verbs >= 3 { 1 } else { 0 })
        + (if file_refs > 6 { 1 } else { 0 });
    TaskSignals {
        numbered_subfeatures,
        bundling_phrases,
        distinct_verbs,
        file_refs,
        word_count,
        bundling_score,
    }
}

// ─── Classifier ─────────────────────────────────────────────────────

/// Classify a task description into a complexity tier.
///
/// Rules (applied in order):
/// 1. Complex: description > 200 chars OR contains a complex keyword.
/// 2. Simple:  description < 80 chars AND contains a simple keyword.
/// 3. Medium:  everything else.
pub fn classify_task(task_desc: &str) -> TaskComplexity {
    let lower = task_desc.to_lowercase();
    let len = task_desc.len();

    // Check complex first -- long descriptions or complex keywords.
    if len > 200 || COMPLEX_KEYWORDS.iter().any(|kw| lower.contains(kw)) {
        return TaskComplexity::Complex;
    }

    // Check simple -- short descriptions with a simple keyword.
    if len < 80 && SIMPLE_KEYWORDS.iter().any(|kw| lower.contains(kw)) {
        return TaskComplexity::Simple;
    }

    TaskComplexity::Medium
}

/// Classify task with additional context about spec detail level.
/// When SPEC.md is detailed (>200 lines), downgrade Complex to Medium
/// since the spec provides enough guidance to reduce ambiguity.
#[allow(dead_code)]
pub fn classify_task_with_context(task_desc: &str, spec_line_count: usize) -> TaskComplexity {
    let base = classify_task(task_desc);
    if spec_line_count > 200 && base == TaskComplexity::Complex {
        TaskComplexity::Medium
    } else {
        base
    }
}

/// Full classifier with composition-aware bundling bump and per-task override.
///
/// Computes `TaskSignals`, then:
/// 1. Starts with the keyword/length-based `classify_task` tier (preserving
///    existing behavior for un-flagged, non-bundled tasks).
/// 2. If `bundling_score >= 3`, bumps tier by one (Simple -> Medium,
///    Medium -> Complex, Complex stays Complex).
/// 3. Applies the per-task override: Fast forces Simple, Strict forces Complex.
pub fn classify_task_full(task_desc: &str, override_flag: TaskOverride) -> TaskClassification {
    let signals = compute_signals(task_desc);
    let base_tier = classify_task(task_desc);
    let bumped_tier = if signals.bundling_score >= 3 {
        match base_tier {
            TaskComplexity::Simple => TaskComplexity::Medium,
            TaskComplexity::Medium => TaskComplexity::Complex,
            TaskComplexity::Complex => TaskComplexity::Complex,
        }
    } else {
        base_tier
    };
    let final_tier = match override_flag {
        TaskOverride::Fast => TaskComplexity::Simple,
        TaskOverride::Strict => TaskComplexity::Complex,
        TaskOverride::None => bumped_tier,
    };
    TaskClassification {
        tier: final_tier,
        override_flag,
        signals,
    }
}

/// Per-tier P+ iteration cap.
/// - Simple: 0 (skip P+ entirely)
/// - Medium: 1 (single review pass)
/// - Complex: `configured_cycles + 1` (current default; saturating)
pub fn p_plus_cycles_budget(tier: TaskComplexity, configured_cycles: usize) -> usize {
    match tier {
        TaskComplexity::Simple => 0,
        TaskComplexity::Medium => 1,
        TaskComplexity::Complex => configured_cycles.saturating_add(1),
    }
}

// ─── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn simple_short_rename() {
        assert_eq!(classify_task("rename field X to Y"), TaskComplexity::Simple);
    }

    #[test]
    fn simple_fix_typo() {
        assert_eq!(classify_task("fix typo in README"), TaskComplexity::Simple);
    }

    #[test]
    fn simple_bump_version() {
        assert_eq!(
            classify_task("bump version to 1.2.3"),
            TaskComplexity::Simple
        );
    }

    #[test]
    fn complex_keyword_refactor() {
        assert_eq!(
            classify_task("refactor auth module"),
            TaskComplexity::Complex
        );
    }

    #[test]
    fn complex_keyword_migrate() {
        assert_eq!(
            classify_task("migrate database to PostgreSQL"),
            TaskComplexity::Complex
        );
    }

    #[test]
    fn complex_long_description() {
        let long = "a".repeat(201);
        assert_eq!(classify_task(&long), TaskComplexity::Complex);
    }

    #[test]
    fn medium_no_keywords() {
        assert_eq!(
            classify_task("implement caching layer"),
            TaskComplexity::Medium
        );
    }

    #[test]
    fn medium_simple_keyword_but_long() {
        // 80+ chars with a simple keyword stays medium (not simple).
        let desc = format!(
            "update the configuration file with new settings for the deployment pipeline across {}",
            "all environments"
        );
        assert!(desc.len() >= 80);
        assert_eq!(classify_task(&desc), TaskComplexity::Medium);
    }

    #[test]
    fn complex_beats_simple_when_both_present() {
        // "refactor" is complex, "fix" is simple -- complex wins.
        assert_eq!(
            classify_task("fix and refactor auth"),
            TaskComplexity::Complex
        );
    }

    #[test]
    fn case_insensitive() {
        assert_eq!(classify_task("RENAME field"), TaskComplexity::Simple);
        assert_eq!(classify_task("REFACTOR module"), TaskComplexity::Complex);
    }

    #[test]
    fn empty_string_is_medium() {
        // 0 chars < 80, but no simple keywords -- medium.
        assert_eq!(classify_task(""), TaskComplexity::Medium);
    }

    #[test]
    fn exactly_80_chars_with_simple_keyword() {
        // 80 chars is NOT < 80, so not simple.
        let desc = format!("fix {}", "x".repeat(76));
        assert_eq!(desc.len(), 80);
        assert_eq!(classify_task(&desc), TaskComplexity::Medium);
    }

    #[test]
    fn exactly_200_chars_is_not_complex() {
        let desc = "x".repeat(200);
        assert_eq!(classify_task(&desc), TaskComplexity::Medium);
    }

    #[test]
    fn detailed_spec_downgrades_complex_to_medium() {
        assert_eq!(
            classify_task_with_context("refactor auth module", 500),
            TaskComplexity::Medium
        );
    }

    #[test]
    fn short_spec_keeps_complex() {
        assert_eq!(
            classify_task_with_context("refactor auth module", 100),
            TaskComplexity::Complex
        );
    }

    #[test]
    fn detailed_spec_does_not_affect_simple() {
        assert_eq!(
            classify_task_with_context("fix typo in README", 500),
            TaskComplexity::Simple
        );
    }

    // ─── T1.23: composition signals + override + budget ────────────

    #[test]
    fn t116_bundled_task_classifies_complex_via_bundling_score() {
        // Use a real fragment of T1.16-style description with (1)/(2)/(3) markers
        // and enough words to bump bundling_score above 3.
        let desc = "Wire the ranker into pattern injection (1) plumb the pipeline (2) BM25 upgrade with normalization and tf-idf weighting (3) telemetry boost for tracking outcomes -- this work spans multiple modules and requires changes to scoring, search, and the reporting layer to land coherently.";
        let result = classify_task_full(desc, TaskOverride::None);
        assert_eq!(result.tier, TaskComplexity::Complex);
        assert!(result.signals.bundling_score >= 3, "signals: {:?}", result.signals);
    }

    #[test]
    fn t117_short_config_field_classifies_simple() {
        let desc = "add a `batch_doubt` field to Config";
        let result = classify_task_full(desc, TaskOverride::None);
        assert_eq!(result.tier, TaskComplexity::Simple);
        assert_eq!(result.signals.bundling_score, 0);
    }

    #[test]
    fn t118_modal_dispatch_classifies_medium() {
        // ~150 chars, no (1)/(2) markers, no complex keywords, no simple keywords
        // strong enough to fall in <80 + simple. Use vocabulary that avoids both.
        let desc =
            "implement modal dispatch logic across four ratatui panels covering escape and ctrl-c handling and the corresponding key event routing through the running view";
        assert!(desc.len() > 80);
        let result = classify_task_full(desc, TaskOverride::None);
        assert_eq!(result.tier, TaskComplexity::Medium);
    }

    #[test]
    fn fast_override_forces_simple() {
        let desc = "refactor the entire authentication subsystem and migrate token storage to a new framework";
        let result = classify_task_full(desc, TaskOverride::Fast);
        assert_eq!(result.tier, TaskComplexity::Simple);
    }

    #[test]
    fn strict_override_forces_complex() {
        let desc = "fix typo";
        let result = classify_task_full(desc, TaskOverride::Strict);
        assert_eq!(result.tier, TaskComplexity::Complex);
    }

    #[test]
    fn bundling_score_threshold_three_bumps_one_tier() {
        // Medium-shape string (~100 chars, no complex keywords) with (1)/(2)/(3)
        let desc = "implement caching across services with (1) policy (2) ttl knobs (3) eviction handling to round it out";
        let result = classify_task_full(desc, TaskOverride::None);
        assert_eq!(result.tier, TaskComplexity::Complex);
        assert_eq!(result.signals.numbered_subfeatures, 3);
    }

    #[test]
    fn signals_count_file_refs() {
        let desc = "rewrite `src/app/build.rs` and `src/complexity.rs` and `src/task.rs` parser";
        let result = classify_task_full(desc, TaskOverride::None);
        assert!(result.signals.file_refs >= 3, "signals: {:?}", result.signals);
    }

    #[test]
    fn p_plus_cycles_budget_per_tier() {
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Simple, 2), 0);
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Medium, 2), 1);
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Complex, 2), 3);
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Complex, 0), 1);
    }
}

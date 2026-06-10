/// Task complexity classifier for model routing.
///
/// Classifies tasks by composition signals (bundling, risk domains, structural
/// keywords, blast radius) so the build loop can route simple tasks through a
/// light pipeline and reserve the heavyweight plan-review machinery for work
/// that actually warrants it. Description LENGTH alone is deliberately not a
/// complexity signal: well-composed tasks in this codebase carry detailed,
/// explicit descriptions (the task-composition guidance encourages it), and
/// telemetry showed a raw length rule classified 96% of tasks Complex.
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
    /// True when the description touches a high-stakes domain (auth, security,
    /// payments, migrations, schema, infrastructure).
    pub risk_hit: bool,
    /// Count of structural keywords present (architect, redesign, refactor,
    /// rewrite, overhaul) -- big-blast-radius verbs.
    pub structural_hits: usize,
    /// The composite score the tier decision is made from. Complex >= 2.
    pub composite_score: usize,
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

/// Big-blast-radius verbs. Each hit adds 1 to the composite score (capped at 2),
/// so a lone "refactor the parser" lands Medium while "redesign the pipeline
/// architecture" or "refactor auth" lands Complex.
const STRUCTURAL_KEYWORDS: &[&str] = &["architect", "redesign", "refactor", "rewrite", "overhaul"];

/// High-stakes domains where mistakes are expensive: matched as token PREFIXES
/// so "authentication"/"authorization"/"migrations" hit. Any hit adds 2 to the
/// composite score (Complex on its own combined with any other signal, and
/// Complex outright when paired with a structural keyword). "auth" is handled
/// separately as an exact token so "author"/"authored" do not match.
const RISK_KEYWORD_PREFIXES: &[&str] = &[
    "authent",
    "authoriz",
    "secur",
    "encrypt",
    "payment",
    "migrat",
    "infrastructure",
    "schema",
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
    "add",
    "remove",
    "rename",
    "refactor",
    "wire",
    "upgrade",
    "build",
    "create",
    "delete",
    "implement",
    "replace",
    "scale",
    "gate",
    "compute",
    "emit",
    "render",
    "show",
    "parse",
    "extract",
    "inject",
    "split",
    "merge",
    "fix",
    "update",
    "introduce",
];

fn count_numbered_subfeatures(lower: &str) -> usize {
    let mut set: std::collections::HashSet<String> = std::collections::HashSet::new();
    for caps in RE_NUMBERED_SUBFEATURE.captures_iter(lower) {
        set.insert(caps[1].to_string());
    }
    set.len()
}

fn count_bundling_phrases(lower: &str) -> usize {
    BUNDLING_PHRASES
        .iter()
        .filter(|p| lower.contains(*p))
        .count()
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

fn text_tokens(lower: &str) -> impl Iterator<Item = &str> {
    lower
        .split(|c: char| !c.is_alphanumeric())
        .filter(|t| !t.is_empty())
}

fn has_risk_keyword(lower: &str) -> bool {
    text_tokens(lower)
        .any(|token| token == "auth" || RISK_KEYWORD_PREFIXES.iter().any(|p| token.starts_with(p)))
}

fn count_structural_keywords(lower: &str) -> usize {
    STRUCTURAL_KEYWORDS
        .iter()
        .filter(|k| text_tokens(lower).any(|token| token.starts_with(**k)))
        .count()
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
    let risk_hit = has_risk_keyword(&lower);
    let structural_hits = count_structural_keywords(&lower);
    // Length contributes only at the documented over-bundling thresholds
    // (docs/task-composition.md: >500 words means the task is doing too much).
    let length_score = if word_count > 500 {
        2
    } else if word_count > 300 {
        1
    } else {
        0
    };
    let composite_score =
        bundling_score + (if risk_hit { 2 } else { 0 }) + structural_hits.min(2) + length_score;
    TaskSignals {
        numbered_subfeatures,
        bundling_phrases,
        distinct_verbs,
        file_refs,
        word_count,
        bundling_score,
        risk_hit,
        structural_hits,
        composite_score,
    }
}

// ─── Classifier ─────────────────────────────────────────────────────

fn classify_from_signals(task_desc: &str, signals: &TaskSignals) -> TaskComplexity {
    if signals.composite_score >= 2 {
        return TaskComplexity::Complex;
    }

    // Simple: a short imperative that LEADS with a simple keyword ("fix typo",
    // "bump version"). Leading-position matching prevents embedded hits like
    // "change detection" in a feature description from downgrading real work.
    let lower = task_desc.to_lowercase();
    let leads_with_simple = SIMPLE_KEYWORDS.iter().any(|k| {
        text_tokens(lower.trim_start())
            .next()
            .is_some_and(|token| token == *k)
    });
    if task_desc.len() < 80
        && leads_with_simple
        && signals.distinct_verbs <= 1
        && signals.composite_score == 0
    {
        return TaskComplexity::Simple;
    }

    TaskComplexity::Medium
}

/// Classify a task description into a complexity tier.
///
/// Rules (applied in order):
/// 1. Complex: composite score >= 2, where score = bundling signals
///    + 2 per risk-domain hit + structural keywords (capped at 2)
///    + over-bundling length (>300 words +1, >500 words +2).
/// 2. Simple:  < 80 chars AND leads with a simple keyword AND a single verb
///    AND score == 0.
/// 3. Medium:  everything else (the default for substantial, well-composed work).
pub fn classify_task(task_desc: &str) -> TaskComplexity {
    classify_from_signals(task_desc, &compute_signals(task_desc))
}

/// Full classifier with composition signals and per-task override.
///
/// The tier comes from the same composite scorer as `classify_task`; the
/// override then applies on top: Fast forces Simple, Strict forces Complex.
pub fn classify_task_full(task_desc: &str, override_flag: TaskOverride) -> TaskClassification {
    let signals = compute_signals(task_desc);
    let base_tier = classify_from_signals(task_desc, &signals);
    let final_tier = match override_flag {
        TaskOverride::Fast => TaskComplexity::Simple,
        TaskOverride::Strict => TaskComplexity::Complex,
        TaskOverride::None => base_tier,
    };
    TaskClassification {
        tier: final_tier,
        override_flag,
        signals,
    }
}

/// Per-tier P+ iteration cap.
/// - Simple: 0 (skip P+ entirely)
/// - Medium: 0 (plan runs, but P+ review is reserved for Complex work --
///   telemetry showed P+ on routine tasks added 50% wall-clock for no
///   measurable outcome change)
/// - Complex: `configured_cycles + 1` (saturating)
pub fn p_plus_cycles_budget(tier: TaskComplexity, configured_cycles: usize) -> usize {
    match tier {
        TaskComplexity::Simple => 0,
        TaskComplexity::Medium => 0,
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
    fn complex_structural_plus_risk() {
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
    fn long_description_alone_is_not_complex() {
        // Raw length no longer implies complexity: a verbose but single-concern
        // description routes Medium. (Old behavior: >200 chars -> Complex.)
        let long = "a".repeat(201);
        assert_eq!(classify_task(&long), TaskComplexity::Medium);
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
        // "refactor" (structural) + "auth" (risk) -- complex wins over "fix".
        assert_eq!(
            classify_task("fix and refactor auth"),
            TaskComplexity::Complex
        );
    }

    #[test]
    fn case_insensitive() {
        assert_eq!(classify_task("RENAME field"), TaskComplexity::Simple);
        // A bare structural keyword with no risk domain or scale signals is
        // Medium now -- "refactor module" is routine work, not architecture.
        assert_eq!(classify_task("REFACTOR module"), TaskComplexity::Medium);
    }

    #[test]
    fn empty_string_is_medium() {
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
    fn multiple_structural_keywords_are_complex() {
        assert_eq!(
            classify_task("redesign the pipeline architecture"),
            TaskComplexity::Complex
        );
    }

    #[test]
    fn structural_keywords_match_token_prefixes_not_substrings() {
        let result = classify_task_full(
            "prearchitected antirefactor notes for the release",
            TaskOverride::None,
        );
        assert_eq!(result.signals.structural_hits, 0);
        assert_eq!(result.tier, TaskComplexity::Medium);
    }

    #[test]
    fn leading_simple_keyword_allows_punctuation() {
        assert_eq!(classify_task("fix: README typo"), TaskComplexity::Simple);
    }

    #[test]
    fn embedded_simple_keyword_does_not_downgrade() {
        // "change" appears mid-description ("change detection") -- this is a
        // build-from-scratch feature, not a one-line change. Must not be Simple.
        let desc = "Federal Register watcher core, change detection, and GitHub issue notifier (cloud-agnostic Python)";
        assert_eq!(classify_task(desc), TaskComplexity::Medium);
    }

    #[test]
    fn risk_prefix_does_not_match_author() {
        let result = classify_task_full("document author workflow notes", TaskOverride::None);
        assert!(!result.signals.risk_hit, "'author' must not match 'auth'");
    }

    #[test]
    fn risk_prefix_matches_authentication() {
        let result =
            classify_task_full("implement authentication token refresh", TaskOverride::None);
        assert!(result.signals.risk_hit);
        assert_eq!(result.tier, TaskComplexity::Complex);
    }

    #[test]
    fn overbundled_length_contributes_to_complex() {
        // >500 words of multi-concern prose scores +2 -> Complex on its own.
        let desc = "implement the watcher ".repeat(170);
        let result = classify_task_full(&desc, TaskOverride::None);
        assert!(result.signals.word_count > 500);
        assert_eq!(result.tier, TaskComplexity::Complex);
    }

    // ─── T1.23: composition signals + override + budget ────────────

    #[test]
    fn t116_bundled_task_classifies_complex_via_bundling_score() {
        // Use a real fragment of T1.16-style description with (1)/(2)/(3) markers
        // and enough words to bump bundling_score above 3.
        let desc = "Wire the ranker into pattern injection (1) plumb the pipeline (2) BM25 upgrade with normalization and tf-idf weighting (3) telemetry boost for tracking outcomes -- this work spans multiple modules and requires changes to scoring, search, and the reporting layer to land coherently.";
        let result = classify_task_full(desc, TaskOverride::None);
        assert_eq!(result.tier, TaskComplexity::Complex);
        assert!(
            result.signals.bundling_score >= 3,
            "signals: {:?}",
            result.signals
        );
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
        // ~150 chars, no (1)/(2) markers, no risk/structural keywords, no
        // leading simple keyword.
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
    fn bundling_score_threshold_bumps_to_complex() {
        // Medium-shape string (~100 chars, no risk/structural keywords) with (1)/(2)/(3)
        let desc = "implement caching across services with (1) policy (2) ttl knobs (3) eviction handling to round it out";
        let result = classify_task_full(desc, TaskOverride::None);
        assert_eq!(result.tier, TaskComplexity::Complex);
        assert_eq!(result.signals.numbered_subfeatures, 3);
    }

    #[test]
    fn signals_count_file_refs() {
        let desc = "rewrite `src/app/build.rs` and `src/complexity.rs` and `src/task.rs` parser";
        let result = classify_task_full(desc, TaskOverride::None);
        assert!(
            result.signals.file_refs >= 3,
            "signals: {:?}",
            result.signals
        );
    }

    #[test]
    fn p_plus_cycles_budget_per_tier() {
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Simple, 2), 0);
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Medium, 2), 0);
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Complex, 2), 3);
        assert_eq!(p_plus_cycles_budget(TaskComplexity::Complex, 0), 1);
    }
}

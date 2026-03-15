/// Task complexity classifier for model routing.
///
/// Classifies tasks by heuristic keyword/length analysis so the build loop
/// can route simple tasks to cheaper models and reserve expensive models
/// for complex work.

// ─── Complexity Tier ────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskComplexity {
    Simple,
    Medium,
    Complex,
}

// ─── Keywords ───────────────────────────────────────────────────────

const SIMPLE_KEYWORDS: &[&str] = &[
    "rename", "add", "change", "update", "fix", "set", "remove", "delete",
    "move", "typo", "color", "label", "text", "value", "flag", "toggle",
    "bump", "version",
];

const COMPLEX_KEYWORDS: &[&str] = &[
    "architect", "redesign", "refactor", "migrate", "rewrite", "system",
    "framework", "engine", "infrastructure", "overhaul",
];

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
pub fn classify_task_with_context(task_desc: &str, spec_line_count: usize) -> TaskComplexity {
    let base = classify_task(task_desc);
    if spec_line_count > 200 && base == TaskComplexity::Complex {
        TaskComplexity::Medium
    } else {
        base
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
        assert_eq!(classify_task("bump version to 1.2.3"), TaskComplexity::Simple);
    }

    #[test]
    fn complex_keyword_refactor() {
        assert_eq!(classify_task("refactor auth module"), TaskComplexity::Complex);
    }

    #[test]
    fn complex_keyword_migrate() {
        assert_eq!(classify_task("migrate database to PostgreSQL"), TaskComplexity::Complex);
    }

    #[test]
    fn complex_long_description() {
        let long = "a".repeat(201);
        assert_eq!(classify_task(&long), TaskComplexity::Complex);
    }

    #[test]
    fn medium_no_keywords() {
        assert_eq!(classify_task("implement caching layer"), TaskComplexity::Medium);
    }

    #[test]
    fn medium_simple_keyword_but_long() {
        // 80+ chars with a simple keyword stays medium (not simple).
        let desc = format!("update the configuration file with new settings for the deployment pipeline across {}", "all environments");
        assert!(desc.len() >= 80);
        assert_eq!(classify_task(&desc), TaskComplexity::Medium);
    }

    #[test]
    fn complex_beats_simple_when_both_present() {
        // "refactor" is complex, "fix" is simple -- complex wins.
        assert_eq!(classify_task("fix and refactor auth"), TaskComplexity::Complex);
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
}

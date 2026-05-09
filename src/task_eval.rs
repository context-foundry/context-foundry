use anyhow::{Context, Result};
use regex::Regex;
use std::collections::{BTreeMap, HashMap};
use std::path::Path;
use std::sync::LazyLock;

use crate::task;

static RE_TASK_ID_STRICT: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^([A-Za-z]?\d+\.\d+):\s*(.+)$").unwrap());
static RE_ANY_CHECKBOX: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^-\s*\[[^\]]*\]\s*").unwrap());
static RE_PROGRESS_SUFFIX_ANY: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\s+\[([^\]]+)\]\s*$").unwrap());
static RE_PROGRESS_SUFFIX_VALID: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\s+\[([A-Z!.\-+]{4,7})\]\s*$").unwrap());
static RE_FILE_PATH: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\b[A-Za-z0-9_./\-]+\.[A-Za-z][A-Za-z0-9]{0,7}\b").unwrap());

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskEvalSeverity {
    Error,
    Warning,
}

impl TaskEvalSeverity {
    pub fn label(self) -> &'static str {
        match self {
            Self::Error => "ERROR",
            Self::Warning => "WARN",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskEvalFinding {
    pub severity: TaskEvalSeverity,
    pub code: &'static str,
    pub line: Option<usize>,
    pub task_id: Option<String>,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskQueueEvaluation {
    pub task_count: usize,
    pub pending_count: usize,
    pub completed_count: usize,
    pub findings: Vec<TaskEvalFinding>,
}

impl TaskQueueEvaluation {
    pub fn error_count(&self) -> usize {
        self.findings
            .iter()
            .filter(|f| f.severity == TaskEvalSeverity::Error)
            .count()
    }

    pub fn warning_count(&self) -> usize {
        self.findings
            .iter()
            .filter(|f| f.severity == TaskEvalSeverity::Warning)
            .count()
    }

    pub fn ok(&self) -> bool {
        self.error_count() == 0
    }
}

pub fn evaluate_tasks_file(path: &Path) -> Result<TaskQueueEvaluation> {
    let content = std::fs::read_to_string(path)
        .with_context(|| format!("failed to read task queue {}", path.display()))?;
    Ok(evaluate_tasks_content(&content))
}

pub fn evaluate_tasks_content(content: &str) -> TaskQueueEvaluation {
    let parsed_tasks = task::parse_tasks_from_str(content);
    let pending_count = task::count_pending(&parsed_tasks);
    let completed_count = task::count_completed(&parsed_tasks);
    let mut findings = Vec::new();
    let mut seen_ids: HashMap<String, usize> = HashMap::new();
    let mut descriptions: BTreeMap<String, (usize, String)> = BTreeMap::new();
    let mut file_shaped_task_count = 0usize;

    for (line_idx, line) in content.lines().enumerate() {
        let line_number = line_idx + 1;
        let trimmed = line.trim_start();

        if RE_ANY_CHECKBOX.is_match(trimmed)
            && !(trimmed.starts_with("- [ ] ") || trimmed.starts_with("- [x] "))
        {
            findings.push(finding(
                TaskEvalSeverity::Error,
                "invalid_checkbox",
                Some(line_number),
                None,
                "task lines must use '- [ ] ' or '- [x] '".to_string(),
            ));
            continue;
        }

        let task_text = if let Some(rest) = trimmed.strip_prefix("- [ ] ") {
            rest
        } else if let Some(rest) = trimmed.strip_prefix("- [x] ") {
            rest
        } else {
            continue;
        };

        let (task_id, description) = match RE_TASK_ID_STRICT.captures(task_text) {
            Some(caps) => (caps[1].to_string(), caps[2].trim().to_string()),
            None => {
                findings.push(finding(
                    TaskEvalSeverity::Error,
                    "missing_or_invalid_task_id",
                    Some(line_number),
                    None,
                    "task line must start with an ID like T1.1:, D2.1:, or H3.1:".to_string(),
                ));
                continue;
            }
        };

        if let Some(first_line) = seen_ids.insert(task_id.clone(), line_number) {
            findings.push(finding(
                TaskEvalSeverity::Error,
                "duplicate_task_id",
                Some(line_number),
                Some(task_id.clone()),
                format!("task ID already appeared on line {}", first_line),
            ));
        }

        let description_without_progress =
            strip_progress_suffix(&description, line_number, &task_id, &mut findings);
        let normalized = normalize_description(&description_without_progress);

        if normalized.is_empty() {
            findings.push(finding(
                TaskEvalSeverity::Error,
                "empty_description",
                Some(line_number),
                Some(task_id.clone()),
                "task description is empty".to_string(),
            ));
            continue;
        }

        if description_without_progress.contains("**")
            || description_without_progress.contains("__")
        {
            findings.push(finding(
                TaskEvalSeverity::Warning,
                "markdown_emphasis_in_task",
                Some(line_number),
                Some(task_id.clone()),
                "task lines should avoid markdown bold/italic because downstream prompts require plain task lines".to_string(),
            ));
        }

        if normalized.len() < 20 {
            findings.push(finding(
                TaskEvalSeverity::Warning,
                "vague_description",
                Some(line_number),
                Some(task_id.clone()),
                "task description is very short; include the user-visible outcome and verification scope".to_string(),
            ));
        }

        if looks_like_busywork(&normalized) {
            findings.push(finding(
                TaskEvalSeverity::Warning,
                "scaffolding_or_busywork",
                Some(line_number),
                Some(task_id.clone()),
                "task looks like setup/scanning/documentation busywork rather than working software".to_string(),
            ));
        }

        if looks_file_shaped(&normalized) {
            file_shaped_task_count += 1;
        }

        if let Some((first_line, first_id)) =
            descriptions.insert(normalized, (line_number, task_id.clone()))
        {
            findings.push(finding(
                TaskEvalSeverity::Warning,
                "duplicate_description",
                Some(line_number),
                Some(task_id),
                format!("description duplicates {} on line {}", first_id, first_line),
            ));
        }
    }

    if parsed_tasks.is_empty() && !content.contains("No new tasks discovered") {
        findings.push(finding(
            TaskEvalSeverity::Warning,
            "empty_task_queue",
            None,
            None,
            "task queue contains no task lines".to_string(),
        ));
    }

    if parsed_tasks.len() >= 5 && file_shaped_task_count * 2 >= parsed_tasks.len() {
        findings.push(finding(
            TaskEvalSeverity::Warning,
            "possible_file_by_file_split",
            None,
            None,
            format!(
                "{} of {} tasks look file-shaped; task queues should split by coherent vertical slices, not by file",
                file_shaped_task_count,
                parsed_tasks.len()
            ),
        ));
    }

    TaskQueueEvaluation {
        task_count: parsed_tasks.len(),
        pending_count,
        completed_count,
        findings,
    }
}

pub fn format_task_queue_evaluation(eval: &TaskQueueEvaluation) -> String {
    let mut out = String::new();
    out.push_str("TASKS.md Evaluation\n");
    out.push_str("-------------------\n");
    out.push_str(&format!(
        "Tasks: {} total, {} pending, {} completed\n",
        eval.task_count, eval.pending_count, eval.completed_count
    ));
    out.push_str(&format!(
        "Findings: {} error(s), {} warning(s)\n",
        eval.error_count(),
        eval.warning_count()
    ));

    if eval.findings.is_empty() {
        out.push_str("Result: PASS\n");
        return out;
    }

    out.push_str("Result: ");
    out.push_str(if eval.ok() { "WARN\n" } else { "FAIL\n" });
    for finding in &eval.findings {
        let location = match (finding.line, finding.task_id.as_deref()) {
            (Some(line), Some(id)) => format!("line {} {}", line, id),
            (Some(line), None) => format!("line {}", line),
            (None, Some(id)) => id.to_string(),
            (None, None) => "queue".to_string(),
        };
        out.push_str(&format!(
            "- [{}] {} at {}: {}\n",
            finding.severity.label(),
            finding.code,
            location,
            finding.message
        ));
    }

    out
}

fn strip_progress_suffix(
    description: &str,
    line_number: usize,
    task_id: &str,
    findings: &mut Vec<TaskEvalFinding>,
) -> String {
    if RE_PROGRESS_SUFFIX_VALID.is_match(description) {
        return RE_PROGRESS_SUFFIX_VALID
            .replace(description, "")
            .trim()
            .to_string();
    }

    if let Some(caps) = RE_PROGRESS_SUFFIX_ANY.captures(description) {
        if let Some(m) = caps.get(1) {
            let suffix = m.as_str();
            if suffix
                .chars()
                .all(|c| c.is_ascii_uppercase() || ".-+!".contains(c))
            {
                findings.push(finding(
                    TaskEvalSeverity::Error,
                    "invalid_progress_suffix",
                    Some(line_number),
                    Some(task_id.to_string()),
                    format!(
                        "progress suffix [{}] must be 4-7 chars from A-Z, '.', '-', '+', or '!'",
                        suffix
                    ),
                ));
            }
        }
    }

    description.trim().to_string()
}

fn normalize_description(s: &str) -> String {
    s.split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .trim()
        .to_ascii_lowercase()
}

fn looks_like_busywork(normalized: &str) -> bool {
    const PHRASES: &[&str] = &[
        "bootstrap the project",
        "set up project structure",
        "setup project structure",
        "establish foundations",
        "scan the codebase",
        "create spec.md",
        "write spec.md",
        "create readme",
        "write readme",
        "create .gitignore",
    ];
    PHRASES.iter().any(|phrase| normalized.contains(phrase))
}

fn looks_file_shaped(normalized: &str) -> bool {
    if !RE_FILE_PATH.is_match(normalized) {
        return false;
    }
    normalized.starts_with("create ")
        || normalized.starts_with("modify ")
        || normalized.starts_with("update ")
        || normalized.starts_with("add ")
        || normalized.starts_with("write ")
}

fn finding(
    severity: TaskEvalSeverity,
    code: &'static str,
    line: Option<usize>,
    task_id: Option<String>,
    message: String,
) -> TaskEvalFinding {
    TaskEvalFinding {
        severity,
        code,
        line,
        task_id,
        message,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid_task_queue_passes() {
        let eval = evaluate_tasks_content(
            "# Task Queue\n\n- [ ] T1.1: Build the weather app with map search, hourly forecast, unit toggle, and verification\n",
        );
        assert!(eval.ok());
        assert_eq!(eval.task_count, 1);
        assert!(eval.findings.is_empty());
    }

    #[test]
    fn invalid_task_line_reports_missing_id() {
        let eval = evaluate_tasks_content("- [ ] Build the thing\n");
        assert!(!eval.ok());
        assert!(eval
            .findings
            .iter()
            .any(|f| f.code == "missing_or_invalid_task_id"));
    }

    #[test]
    fn duplicate_ids_are_errors() {
        let eval = evaluate_tasks_content("- [ ] T1.1: First task\n- [ ] T1.1: Second task\n");
        assert!(!eval.ok());
        assert!(eval.findings.iter().any(|f| f.code == "duplicate_task_id"));
    }

    #[test]
    fn invalid_progress_suffix_is_error() {
        let eval = evaluate_tasks_content("- [ ] T1.1: Build the thing [TOO-LONG]\n");
        assert!(!eval.ok());
        assert!(eval
            .findings
            .iter()
            .any(|f| f.code == "invalid_progress_suffix"));
    }

    #[test]
    fn scaffolding_busywork_is_warning() {
        let eval =
            evaluate_tasks_content("- [ ] T1.1: Bootstrap the project and create README files\n");
        assert!(eval.ok());
        assert!(eval
            .findings
            .iter()
            .any(|f| f.code == "scaffolding_or_busywork"));
    }

    #[test]
    fn file_by_file_split_warns() {
        let eval = evaluate_tasks_content(
            "- [ ] T1.1: Create src/a.rs\n\
- [ ] T1.2: Create src/b.rs\n\
- [ ] T1.3: Create src/c.rs\n\
- [ ] T1.4: Create src/d.rs\n\
- [ ] T1.5: Create src/e.rs\n",
        );
        assert!(eval.ok());
        assert!(eval
            .findings
            .iter()
            .any(|f| f.code == "possible_file_by_file_split"));
    }

    #[test]
    fn formatter_shows_fail_for_errors() {
        let eval = evaluate_tasks_content("- [ ] Build the thing\n");
        let output = format_task_queue_evaluation(&eval);
        assert!(output.contains("Result: FAIL"));
        assert!(output.contains("missing_or_invalid_task_id"));
    }
}

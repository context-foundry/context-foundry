use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::io::{BufRead, Write};
use std::path::{Path, PathBuf};

/// A single build task record, appended to the history log after each task completes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildRecord {
    /// ISO timestamp (e.g. "2026-04-09T14:30:00Z")
    pub timestamp: String,
    /// Task ID (e.g. "T1.1", "D2.3")
    pub task_id: String,
    /// Task description
    pub description: String,
    /// Project directory (absolute path)
    pub project: String,
    /// "pass" or "wip"
    pub outcome: String,
    /// Git commit SHA (if committed)
    pub commit_sha: Option<String>,
    /// Pattern IDs that were injected for this task
    pub patterns_injected: Vec<String>,
    /// Pattern IDs that were actually cited by agents
    pub patterns_cited: Vec<String>,
    /// Number of files changed
    pub files_changed: usize,
    /// Duration in seconds
    pub duration_secs: f64,
}

/// Resolve the history directory, expanding `~/` to $HOME.
pub fn resolve_history_dir(config_str: &str) -> PathBuf {
    if let Some(rest) = config_str.strip_prefix("~/") {
        if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
            return PathBuf::from(home).join(rest);
        }
    }
    PathBuf::from(config_str)
}

/// Append a build record to the JSONL history file.
/// Creates the directory and file if they don't exist.
pub fn append_record(history_dir: &Path, record: &BuildRecord) -> std::io::Result<()> {
    std::fs::create_dir_all(history_dir)?;
    let path = history_dir.join("build-history.jsonl");
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)?;
    let json = serde_json::to_string(record)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    writeln!(file, "{}", json)?;
    Ok(())
}

/// Search build history for records matching a keyword query.
/// Returns the top `limit` matches, most recent first.
/// Searches task_id, description, project, and pattern IDs.
pub fn search_history(history_dir: &Path, query: &str, limit: usize) -> Vec<BuildRecord> {
    if limit == 0 {
        return Vec::new();
    }

    let query = query.trim();
    if query.is_empty() {
        return Vec::new();
    }

    let path = history_dir.join("build-history.jsonl");
    let file = match std::fs::File::open(&path) {
        Ok(f) => f,
        Err(_) => return Vec::new(),
    };

    let query_lower = query.to_lowercase();

    let reader = std::io::BufReader::new(file);
    let mut matches: Vec<BuildRecord> = reader
        .lines()
        .map_while(Result::ok)
        .filter_map(|line| serde_json::from_str::<BuildRecord>(&line).ok())
        .filter(|record| {
            let searchable = format!(
                "{} {} {} {} {}",
                record.task_id,
                record.description,
                record.project,
                record.patterns_injected.join(" "),
                record.patterns_cited.join(" "),
            )
            .to_lowercase();
            searchable.contains(&query_lower)
        })
        .collect();

    // Most recent first
    matches.reverse();
    matches.truncate(limit);
    matches
}

/// Format search results as a markdown summary for injection into scout prompts.
/// Renders all records passed in -- caller controls the count via search_history(limit).
pub fn format_history_for_prompt(records: &[BuildRecord]) -> String {
    if records.is_empty() {
        return String::new();
    }

    let mut out = String::new();
    out.push_str("\n\n---\n## Previous Work on Similar Tasks\n\n");
    out.push_str("| Task | Date | Outcome | Duration | Files | Patterns |\n");
    out.push_str("| --- | --- | --- | ---: | ---: | --- |\n");

    for r in records {
        let task = format!("{}: {}", r.task_id, sanitize_history_cell(&r.description));
        let date = sanitize_history_cell(r.timestamp.get(..10).unwrap_or(&r.timestamp));
        let outcome = sanitize_history_cell(&r.outcome);
        let patterns = if r.patterns_cited.is_empty() {
            "-".to_string()
        } else {
            sanitize_history_cell(&r.patterns_cited.join(", "))
        };
        out.push_str(&format!(
            "| {} | {} | {} | {:.0}s | {} | {} |\n",
            task, date, outcome, r.duration_secs, r.files_changed, patterns,
        ));
    }

    out
}

fn sanitize_history_cell(value: &str) -> String {
    value.replace('|', "\\|").replace('\n', " ")
}

/// Create a BuildRecord with the current timestamp.
#[allow(clippy::too_many_arguments)]
pub fn new_record(
    task_id: &str,
    description: &str,
    project: &str,
    outcome: &str,
    commit_sha: Option<String>,
    patterns_injected: Vec<String>,
    patterns_cited: Vec<String>,
    files_changed: usize,
    duration_secs: f64,
) -> BuildRecord {
    BuildRecord {
        timestamp: Utc::now().to_rfc3339(),
        task_id: task_id.to_string(),
        description: description.to_string(),
        project: project.to_string(),
        outcome: outcome.to_string(),
        commit_sha,
        patterns_injected,
        patterns_cited,
        files_changed,
        duration_secs,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_append_and_search() {
        let dir = std::env::temp_dir().join("foundry_test_history");
        let _ = std::fs::remove_dir_all(&dir);

        let r1 = new_record(
            "T1.1",
            "Add authentication middleware",
            "/home/user/project",
            "pass",
            Some("abc123".to_string()),
            vec!["auth-pattern".to_string()],
            vec!["auth-pattern".to_string()],
            5,
            120.0,
        );
        let r2 = new_record(
            "T1.2",
            "Fix database migration bug",
            "/home/user/project",
            "wip",
            None,
            vec![],
            vec![],
            2,
            45.0,
        );

        append_record(&dir, &r1).unwrap();
        append_record(&dir, &r2).unwrap();

        let results = search_history(&dir, "authentication", 10);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].task_id, "T1.1");

        let results = search_history(&dir, "database", 10);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].task_id, "T1.2");

        let results = search_history(&dir, "project", 10);
        assert_eq!(results.len(), 2, "both records match on project path");

        let results = search_history(&dir, "authentication middleware", 10);
        assert_eq!(results.len(), 1, "full substring query should match");

        let results = search_history(&dir, "authentication bug", 10);
        assert!(
            results.is_empty(),
            "query should not match when the full substring is absent"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_search_empty_dir() {
        let dir = std::env::temp_dir().join("foundry_test_history_empty");
        let results = search_history(&dir, "anything", 10);
        assert!(results.is_empty());
        let results = search_history(&dir, "", 10);
        assert!(results.is_empty());
        let results = search_history(&dir, "anything", 0);
        assert!(results.is_empty());
    }

    #[test]
    fn test_format_history() {
        let records = vec![new_record(
            "T1.1",
            "Add auth",
            "/project",
            "pass",
            None,
            vec![],
            vec!["auth-001".to_string()],
            3,
            60.0,
        )];
        let formatted = format_history_for_prompt(&records);
        assert!(formatted.contains("| Task | Date | Outcome | Duration | Files | Patterns |"));
        assert!(formatted.contains("T1.1"));
        assert!(formatted.contains("Add auth"));
        assert!(formatted.contains("auth-001"));
    }
}

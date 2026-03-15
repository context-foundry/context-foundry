use anyhow::Result;
use regex::Regex;
use std::fs;
use std::path::Path;
use std::sync::LazyLock;

use crate::utils::{atomic_write_file, truncate_str};

static RE_TASK_ID: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^([A-Za-z]?\d+\.\d+):\s*").unwrap());

static RE_DISCOVERY_HEADER: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"## Discovery Round (\d+)").unwrap());

static RE_DISCOVERY_TASK_ID: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"D(\d+)\.\d+").unwrap());

/// Matches a pipeline progress indicator like `[PB..]` or `[PBRF!]` at the end of a task line.
static RE_PIPELINE_PROGRESS: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\s+\[([A-Z!.\-]{4,6})\]\s*$").unwrap());

#[derive(Debug, Clone)]
pub struct Task {
    pub id: String,
    pub description: String,
    pub line_number: usize,
    pub completed: bool,
    pub pipeline_progress: Option<String>,
}

impl Task {
    pub fn short_desc(&self, max_len: usize) -> String {
        if self.description.len() <= max_len {
            self.description.clone()
        } else {
            truncate_str(&self.description, max_len).to_string()
        }
    }
}

pub fn parse_tasks(plan_path: &Path) -> Result<Vec<Task>> {
    let content = fs::read_to_string(plan_path)?;

    let mut tasks = Vec::new();

    for (i, line) in content.lines().enumerate() {
        let line_trimmed = line.trim_start();

        let (completed, text) = if let Some(rest) = line_trimmed.strip_prefix("- [ ] ") {
            (false, rest.to_string())
        } else if let Some(rest) = line_trimmed.strip_prefix("- [x] ") {
            (true, rest.to_string())
        } else {
            continue;
        };

        let (id, description) = if let Some(caps) = RE_TASK_ID.captures(&text) {
            let id = caps[1].to_string();
            let desc = text[caps[0].len()..].to_string();
            (id, desc)
        } else {
            ("TASK".to_string(), text)
        };

        // Extract pipeline progress indicator (e.g. `[PB..]`) from end of description.
        let (description, pipeline_progress) =
            if let Some(caps) = RE_PIPELINE_PROGRESS.captures(&description) {
                let progress = caps[1].to_string();
                let desc = description[..caps.get(0).unwrap().start()].to_string();
                (desc, Some(progress))
            } else {
                (description, None)
            };

        tasks.push(Task {
            id,
            description,
            line_number: i + 1,
            completed,
            pipeline_progress,
        });
    }

    Ok(tasks)
}

pub fn next_pending(tasks: &[Task]) -> Option<&Task> {
    nth_pending(tasks, 0)
}

pub fn nth_pending(tasks: &[Task], index: usize) -> Option<&Task> {
    tasks.iter().filter(|t| !t.completed).nth(index)
}

pub fn mark_done(plan_path: &Path, line_number: usize) -> Result<()> {
    let content = fs::read_to_string(plan_path)?;
    let mut lines: Vec<String> = content.lines().map(String::from).collect();

    // Primary: try the original line number (fast path when file hasn't changed)
    if line_number > 0
        && line_number <= lines.len()
        && lines[line_number - 1].trim_start().starts_with("- [ ]")
    {
        lines[line_number - 1] = lines[line_number - 1].replace("- [ ]", "- [x]");
        atomic_write_file(plan_path, (lines.join("\n") + "\n").as_bytes())?;
        return Ok(());
    }

    // Fallback: file changed since parsing (lines shifted due to discovery/inject).
    // Extract the task ID from the original line and search for it.
    let id_prefix = if line_number > 0 && line_number <= lines.len() {
        extract_task_id_prefix(&lines[line_number - 1])
    } else {
        None
    };

    if let Some(ref prefix) = id_prefix {
        for line in lines.iter_mut() {
            if line.trim_start().starts_with("- [ ]") && line.contains(prefix) {
                *line = line.replace("- [ ]", "- [x]");
                atomic_write_file(plan_path, (lines.join("\n") + "\n").as_bytes())?;
                return Ok(());
            }
        }
    }

    // Last resort: scan all unchecked lines for one matching the original content
    if line_number > 0 && line_number <= lines.len() {
        let original_trimmed = lines[line_number - 1].trim().to_string();
        for line in lines.iter_mut() {
            if line.trim_start().starts_with("- [ ]") && line.trim() == original_trimmed {
                *line = line.replace("- [ ]", "- [x]");
                atomic_write_file(plan_path, (lines.join("\n") + "\n").as_bytes())?;
                return Ok(());
            }
        }
    }

    // Nothing matched -- the task may already be checked or the file is very different
    Ok(())
}

/// Update the pipeline progress indicator `[XXXX]` on the task line in the plan file.
/// If the line already has an indicator, it is replaced; otherwise one is appended.
pub fn update_task_progress(plan_path: &Path, task_id: &str, progress: &str) -> Result<()> {
    let content = fs::read_to_string(plan_path)?;
    let mut lines: Vec<String> = content.lines().map(String::from).collect();

    let id_with_colon = format!("{}:", task_id);

    for line in lines.iter_mut() {
        let trimmed = line.trim_start();
        if (trimmed.starts_with("- [ ]") || trimmed.starts_with("- [x]"))
            && trimmed.contains(&id_with_colon)
        {
            // Strip existing progress indicator if present.
            if let Some(caps) = RE_PIPELINE_PROGRESS.captures(line) {
                let start = caps.get(0).unwrap().start();
                line.truncate(start);
            }
            // Append the new indicator.
            line.push_str(&format!(" [{}]", progress));
            atomic_write_file(plan_path, (lines.join("\n") + "\n").as_bytes())?;
            return Ok(());
        }
    }

    Ok(())
}

fn extract_task_id_prefix(line: &str) -> Option<String> {
    let rest = line
        .trim_start()
        .strip_prefix("- [ ] ")
        .or_else(|| line.trim_start().strip_prefix("- [x] "))?;
    let colon_pos = rest.find(':')?;
    Some(rest[..colon_pos + 1].to_string())
}

pub fn count_completed(tasks: &[Task]) -> usize {
    tasks.iter().filter(|t| t.completed).count()
}

pub fn count_pending(tasks: &[Task]) -> usize {
    tasks.iter().filter(|t| !t.completed).count()
}

pub fn highest_discovery_round(plan_path: &Path) -> usize {
    let content = match fs::read_to_string(plan_path) {
        Ok(c) => c,
        Err(_) => return 0,
    };

    let mut max_round: usize = 0;

    for line in content.lines() {
        if let Some(caps) = RE_DISCOVERY_HEADER.captures(line) {
            if let Ok(n) = caps[1].parse::<usize>() {
                if n > max_round {
                    max_round = n;
                }
            }
        }
        if let Some(caps) = RE_DISCOVERY_TASK_ID.captures(line) {
            if let Ok(n) = caps[1].parse::<usize>() {
                if n > max_round {
                    max_round = n;
                }
            }
        }
    }

    max_round
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_plan_path(name: &str) -> std::path::PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        std::env::temp_dir().join(format!("{}-{}.md", name, unique))
    }

    #[test]
    fn parse_numeric_task_ids_from_readme_style_tasks() -> Result<()> {
        let plan_path = temp_plan_path("foundry-task-plan");
        fs::write(
            &plan_path,
            "## Phase 1\n- [ ] 1.1: Set up project scaffolding\n- [x] 1.2: Implement auth\n",
        )?;

        let tasks = parse_tasks(&plan_path)?;
        fs::remove_file(&plan_path)?;

        assert_eq!(tasks.len(), 2);
        assert_eq!(tasks[0].id, "1.1");
        assert_eq!(tasks[1].id, "1.2");
        assert!(!tasks[0].completed);
        assert!(tasks[1].completed);
        Ok(())
    }

    #[test]
    fn parse_letter_prefixed_task_ids_still_works() -> Result<()> {
        let plan_path = temp_plan_path("foundry-task-alpha-plan");
        fs::write(&plan_path, "- [ ] A1.1: Review architecture\n")?;

        let tasks = parse_tasks(&plan_path)?;
        fs::remove_file(&plan_path)?;

        assert_eq!(tasks.len(), 1);
        assert_eq!(tasks[0].id, "A1.1");
        Ok(())
    }

    #[test]
    fn test_highest_discovery_round_empty_file() {
        let plan_path = temp_plan_path("foundry-disc-empty");
        fs::write(&plan_path, "## Phase 1\n- [ ] T1.1: Do stuff\n").unwrap();
        let result = highest_discovery_round(&plan_path);
        fs::remove_file(&plan_path).unwrap();
        assert_eq!(result, 0);
    }

    #[test]
    fn test_highest_discovery_round_multiple_rounds() {
        let plan_path = temp_plan_path("foundry-disc-multi");
        fs::write(
            &plan_path,
            "## Discovery Round 1\n- [x] D1.1: Fix bug\n\n## Discovery Round 5\n- [x] D5.1: Another fix\n\n## Discovery Round 3\n- [x] D3.1: Old fix\n",
        )
        .unwrap();
        let result = highest_discovery_round(&plan_path);
        fs::remove_file(&plan_path).unwrap();
        assert_eq!(result, 5);
    }

    #[test]
    fn test_highest_discovery_round_from_task_ids() {
        let plan_path = temp_plan_path("foundry-disc-taskid");
        fs::write(
            &plan_path,
            "## Phase 1\n- [x] D12.3: Found by task ID regex\n",
        )
        .unwrap();
        let result = highest_discovery_round(&plan_path);
        fs::remove_file(&plan_path).unwrap();
        assert_eq!(result, 12);
    }

    #[test]
    fn test_highest_discovery_round_missing_file() {
        let plan_path = temp_plan_path("foundry-disc-missing-nonexistent");
        let result = highest_discovery_round(&plan_path);
        assert_eq!(result, 0);
    }
}

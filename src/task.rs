use anyhow::Result;
use regex::Regex;
use std::fs;
use std::path::Path;

use crate::utils::truncate_str;

#[derive(Debug, Clone)]
pub struct Task {
    pub id: String,
    pub description: String,
    pub line_number: usize,
    pub completed: bool,
}

impl Task {
    pub fn short_desc(&self, max_len: usize) -> String {
        if self.description.len() <= max_len {
            self.description.clone()
        } else {
            format!(
                "{}...",
                truncate_str(&self.description, max_len.saturating_sub(3))
            )
        }
    }
}

pub fn parse_tasks(plan_path: &Path) -> Result<Vec<Task>> {
    let content = fs::read_to_string(plan_path)?;
    let re_id = Regex::new(r"^([A-Za-z]?\d+\.\d+):\s*")?;

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

        let (id, description) = if let Some(caps) = re_id.captures(&text) {
            let id = caps[1].to_string();
            let desc = text[caps[0].len()..].to_string();
            (id, desc)
        } else {
            ("TASK".to_string(), text)
        };

        tasks.push(Task {
            id,
            description,
            line_number: i + 1,
            completed,
        });
    }

    Ok(tasks)
}

pub fn next_pending(tasks: &[Task]) -> Option<&Task> {
    tasks.iter().find(|t| !t.completed)
}

pub fn mark_done(plan_path: &Path, line_number: usize) -> Result<()> {
    let content = fs::read_to_string(plan_path)?;
    let mut lines: Vec<String> = content.lines().map(String::from).collect();

    if line_number > 0 && line_number <= lines.len() {
        lines[line_number - 1] = lines[line_number - 1].replace("- [ ]", "- [x]");
    }

    fs::write(plan_path, lines.join("\n") + "\n")?;
    Ok(())
}

pub fn count_completed(tasks: &[Task]) -> usize {
    tasks.iter().filter(|t| t.completed).count()
}

pub fn count_pending(tasks: &[Task]) -> usize {
    tasks.iter().filter(|t| !t.completed).count()
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
}

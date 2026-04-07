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

/// Matches a pipeline progress indicator like `[SPID]` or `[SPID!]` (and legacy `[PBRF]`) at the end of a task line.
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

/// Archive completed phases from TASKS.md to TASKS-ARCHIVE.md.
/// For each phase where all tasks are `[x]`, keep the first `keep_first` and
/// last `keep_last` tasks in TASKS.md and move the rest to the archive.
/// Returns the number of tasks archived.
pub fn archive_completed_phases(
    tasks_path: &Path,
    keep_first: usize,
    keep_last: usize,
) -> Result<usize> {
    let content = fs::read_to_string(tasks_path)?;
    let lines: Vec<&str> = content.lines().collect();

    // Parse into phases: (header_line_idx, Vec<task_line_idx>)
    let mut phases: Vec<(usize, Vec<usize>)> = Vec::new();
    let mut current_phase: Option<(usize, Vec<usize>)> = None;

    for (i, line) in lines.iter().enumerate() {
        if line.starts_with("## ") {
            if let Some(phase) = current_phase.take() {
                phases.push(phase);
            }
            current_phase = Some((i, Vec::new()));
        } else if let Some(ref mut phase) = current_phase {
            let trimmed = line.trim_start();
            if trimmed.starts_with("- [x] ") || trimmed.starts_with("- [ ] ") {
                phase.1.push(i);
            }
        }
    }
    if let Some(phase) = current_phase {
        phases.push(phase);
    }

    // Identify phases eligible for archiving:
    // - All tasks are [x] (no pending)
    // - For large phases (> keep_first + keep_last): archive middle, keep edges
    // - For small phases (<= keep_first + keep_last): archive ALL tasks
    let keep_total = keep_first + keep_last;
    let mut lines_to_archive: Vec<usize> = Vec::new();
    let mut archive_annotations: Vec<(usize, usize, usize)> = Vec::new(); // (header_idx, archived_count, retained_count)
    let mut fully_archived_headers: Vec<usize> = Vec::new(); // headers of sections archived entirely

    for (header_idx, task_indices) in &phases {
        if task_indices.is_empty() {
            continue;
        }
        // Check all tasks are completed
        let all_completed = task_indices
            .iter()
            .all(|&i| lines[i].trim_start().starts_with("- [x] "));
        if !all_completed {
            continue;
        }
        if task_indices.len() <= keep_total {
            // Small completed section: archive ALL tasks and the header
            for &idx in task_indices {
                lines_to_archive.push(idx);
            }
            fully_archived_headers.push(*header_idx);
            let archived_count = task_indices.len();
            let retained_count = 0;
            archive_annotations.push((*header_idx, archived_count, retained_count));
            continue;
        }
        // Large completed section: archive the middle, keep first N and last N
        let archive_start = keep_first;
        let archive_end = task_indices.len() - keep_last;
        for &idx in &task_indices[archive_start..archive_end] {
            lines_to_archive.push(idx);
        }
        let archived_count = archive_end - archive_start;
        let retained_count = task_indices.len() - archived_count;
        archive_annotations.push((*header_idx, archived_count, retained_count));
    }

    if lines_to_archive.is_empty() {
        return Ok(0);
    }

    let total_archived = lines_to_archive.len();

    // Build archive content
    let archive_path = tasks_path.with_file_name("TASKS-ARCHIVE.md");
    let mut archive_content = if archive_path.exists() {
        fs::read_to_string(&archive_path).unwrap_or_default()
    } else {
        "# Archived Tasks\n\n".to_string()
    };

    // Group archived lines by their phase header for readable archive output
    let mut current_header: Option<String> = None;
    for &line_idx in &lines_to_archive {
        // Find the phase header for this line
        let header = phases
            .iter()
            .filter(|(h, _)| *h < line_idx)
            .next_back()
            .map(|(h, _)| lines[*h]);
        if let Some(h) = header {
            if current_header.as_deref() != Some(h) {
                archive_content.push_str(&format!("\n{}\n\n", h));
                current_header = Some(h.to_string());
            }
        }
        archive_content.push_str(lines[line_idx]);
        archive_content.push('\n');
    }

    // Write archive
    atomic_write_file(&archive_path, archive_content.as_bytes())?;

    // Rebuild TASKS.md without archived lines, adding annotation to headers
    let archived_set: std::collections::HashSet<usize> = lines_to_archive.into_iter().collect();
    let fully_archived_set: std::collections::HashSet<usize> =
        fully_archived_headers.into_iter().collect();
    let mut new_lines: Vec<String> = Vec::new();
    // Track lines between a fully-archived header and the next header (description
    // paragraphs, blank lines) so they are also removed.
    let mut skipping_fully_archived_section = false;

    for (i, line) in lines.iter().enumerate() {
        // If this line IS a fully-archived header, replace with a summary line
        if fully_archived_set.contains(&i) {
            if let Some(&(_, archived, _)) = archive_annotations
                .iter()
                .find(|(h, _, _)| *h == i)
            {
                let header_text = line.trim_start_matches("## ").to_string();
                new_lines.push(format!(
                    "- {} ({} tasks archived to TASKS-ARCHIVE.md)",
                    header_text, archived
                ));
            }
            skipping_fully_archived_section = true;
            continue;
        }
        // Skip non-task lines (descriptions, blanks) belonging to a fully-archived section
        if skipping_fully_archived_section {
            if line.starts_with("## ") {
                // New section -- stop skipping
                skipping_fully_archived_section = false;
            } else if archived_set.contains(&i) {
                // Task line in the fully-archived section -- already handled
                continue;
            } else {
                // Description paragraph or blank line in fully-archived section
                continue;
            }
        }
        if archived_set.contains(&i) {
            // Check if this is the first archived line in its phase -- insert marker
            let is_first_in_phase = !archived_set.contains(&(i.saturating_sub(1)))
                || i == 0;
            if is_first_in_phase {
                let count = archived_set.iter().filter(|&&idx| {
                    // Count archived lines in the same phase
                    let phase = phases.iter().find(|(_, tasks)| tasks.contains(&idx));
                    let this_phase = phases.iter().find(|(_, tasks)| tasks.contains(&i));
                    phase.map(|p| p.0) == this_phase.map(|p| p.0)
                }).count();
                new_lines.push(format!("  ... ({} tasks archived to TASKS-ARCHIVE.md)", count));
            }
            continue;
        }
        // Annotate phase headers with archive counts (large sections only)
        if let Some(&(_, archived, retained)) = archive_annotations
            .iter()
            .find(|(h, _, _)| *h == i)
        {
            if retained > 0 {
                let header = line.to_string();
                new_lines.push(format!("{} ({} archived, {} retained)", header, archived, retained));
            } else {
                new_lines.push(line.to_string());
            }
        } else {
            new_lines.push(line.to_string());
        }
    }

    let new_content = new_lines.join("\n") + "\n";
    atomic_write_file(tasks_path, new_content.as_bytes())?;

    Ok(total_archived)
}

/// Returns true if a section is an archive summary (no actionable context for Query agent).
/// Detection: header contains "archived" (case-insensitive), OR >50% of non-empty content
/// lines match archive reference patterns (Phase, Discovery, Human, Roadmap, Total archived).
fn is_archive_summary_section(section_lines: &[&str]) -> bool {
    if let Some(header) = section_lines.first() {
        if header.to_lowercase().contains("archived") {
            return true;
        }
    }

    let content_lines: Vec<&&str> = section_lines
        .iter()
        .skip(1)
        .filter(|l| !l.trim().is_empty())
        .collect();

    if content_lines.is_empty() {
        return false;
    }

    let archive_ref_count = content_lines
        .iter()
        .filter(|l| {
            let trimmed = l.trim_start();
            trimmed.starts_with("- Phase ")
                || trimmed.starts_with("- Discovery ")
                || trimmed.starts_with("- Human ")
                || trimmed.starts_with("- Roadmap ")
                || trimmed.starts_with("- **Total archived")
        })
        .count();

    archive_ref_count > content_lines.len() / 2
}

/// Extract a trimmed version of TASKS.md content suitable for the Query agent prompt.
/// Keeps preamble, genuine non-task sections (e.g. Notes), all sections with pending
/// tasks, and the 2 most recent completed-only sections. Older completed-only sections
/// and archive summary sections are collapsed to a single summary line.
pub fn extract_query_context(tasks_content: &str) -> String {
    if tasks_content.trim().is_empty() {
        return String::new();
    }

    let lines: Vec<&str> = tasks_content.lines().collect();

    // Parse into sections: (start_idx, end_idx, has_pending, has_completed)
    struct Section {
        start: usize,
        end: usize,
        has_pending: bool,
        has_completed: bool,
    }

    let mut sections: Vec<Section> = Vec::new();
    let mut current_start: Option<usize> = None;

    for (i, line) in lines.iter().enumerate() {
        if line.starts_with("## ") {
            if let Some(start) = current_start {
                sections.push(Section {
                    start,
                    end: i,
                    has_pending: false,
                    has_completed: false,
                });
            }
            current_start = Some(i);
        }
    }
    if let Some(start) = current_start {
        sections.push(Section {
            start,
            end: lines.len(),
            has_pending: false,
            has_completed: false,
        });
    }

    // Classify sections
    for section in sections.iter_mut() {
        for &line in &lines[section.start..section.end] {
            let trimmed = line.trim_start();
            if trimmed.starts_with("- [ ] ") {
                section.has_pending = true;
            } else if trimmed.starts_with("- [x] ") {
                section.has_completed = true;
            }
        }
    }

    // Identify completed-only sections (for trimming)
    let completed_only_indices: Vec<usize> = sections
        .iter()
        .enumerate()
        .filter(|(_, s)| s.has_completed && !s.has_pending)
        .map(|(i, _)| i)
        .collect();

    // Keep the last 2 completed-only sections
    let keep_completed: std::collections::HashSet<usize> = if completed_only_indices.len() > 2 {
        completed_only_indices[completed_only_indices.len() - 2..]
            .iter()
            .copied()
            .collect()
    } else {
        completed_only_indices.iter().copied().collect()
    };

    // Lines before the first ## section (preamble)
    let preamble_end = sections.first().map(|s| s.start).unwrap_or(lines.len());

    let mut output = Vec::new();

    // Include preamble
    for &line in &lines[..preamble_end] {
        output.push(line.to_string());
    }

    // Process each section
    for (i, section) in sections.iter().enumerate() {
        if section.has_pending {
            // Include entirely
            for &line in &lines[section.start..section.end] {
                output.push(line.to_string());
            }
        } else if section.has_completed {
            if keep_completed.contains(&i) {
                // Include entirely
                for &line in &lines[section.start..section.end] {
                    output.push(line.to_string());
                }
            } else {
                // Collapsed: header + count
                output.push(lines[section.start].to_string());
                let completed_count = lines[section.start..section.end]
                    .iter()
                    .filter(|l| l.trim_start().starts_with("- [x] "))
                    .count();
                output.push(format!(
                    "({} completed tasks omitted for brevity)",
                    completed_count
                ));
                output.push(String::new());
            }
        } else {
            // Non-task section -- collapse archive summaries, keep others in full
            let section_lines = &lines[section.start..section.end];
            if is_archive_summary_section(section_lines) {
                output.push(lines[section.start].to_string());
                let ref_count = section_lines[1..]
                    .iter()
                    .filter(|l| !l.trim().is_empty())
                    .count();
                output.push(format!(
                    "({} archive references omitted)",
                    ref_count
                ));
                output.push(String::new());
            } else {
                for &line in section_lines {
                    output.push(line.to_string());
                }
            }
        }
    }

    output.join("\n")
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

    #[test]
    fn test_extract_query_context_only_pending() {
        let input = "# Tasks\n\n## Phase 1\n- [ ] T1.1: Do first thing\n- [ ] T1.2: Do second thing\n";
        let result = extract_query_context(input);
        assert!(result.contains("- [ ] T1.1: Do first thing"));
        assert!(result.contains("- [ ] T1.2: Do second thing"));
        assert!(result.contains("## Phase 1"));
    }

    #[test]
    fn test_extract_query_context_trims_old_completed() {
        let input = "\
## Phase 1\n\
- [x] T1.1: Old task 1\n\
\n\
## Phase 2\n\
- [x] T2.1: Old task 2\n\
\n\
## Phase 3\n\
- [x] T3.1: Recent task 1\n\
\n\
## Phase 4\n\
- [x] T4.1: Recent task 2\n\
\n\
## Phase 5\n\
- [ ] T5.1: Pending task\n";
        let result = extract_query_context(input);
        // Phase 1 and 2 should be collapsed (only last 2 completed kept)
        assert!(result.contains("## Phase 1"));
        assert!(result.contains("(1 completed tasks omitted for brevity)"));
        assert!(!result.contains("T1.1: Old task 1"));
        assert!(result.contains("## Phase 2"));
        assert!(!result.contains("T2.1: Old task 2"));
        // Phase 3 and 4 should be kept in full (last 2 completed)
        assert!(result.contains("- [x] T3.1: Recent task 1"));
        assert!(result.contains("- [x] T4.1: Recent task 2"));
        // Pending section fully preserved
        assert!(result.contains("- [ ] T5.1: Pending task"));
    }

    #[test]
    fn test_extract_query_context_collapses_archive_summary() {
        let input = "\
## Completed Work (archived to TASKS-ARCHIVE.md)\n\
- Phase 1: Context Foundry Visualizer (1 task)\n\
- Phase 2: TUI polish (3 tasks)\n\
- Discovery Round 1 (2 tasks archived)\n\
- Discovery Round 2 (3 tasks archived)\n\
\n\
## Phase 3\n\
- [x] T3.1: Done thing\n\
\n\
## Phase 4\n\
- [ ] T4.1: Pending thing\n";
        let result = extract_query_context(input);
        // Archive summary section should be collapsed
        assert!(result.contains("## Completed Work (archived to TASKS-ARCHIVE.md)"));
        assert!(result.contains("(4 archive references omitted)"));
        assert!(!result.contains("- Phase 1: Context Foundry Visualizer (1 task)"));
        assert!(!result.contains("- Discovery Round 1 (2 tasks archived)"));
        // Other sections preserved normally
        assert!(result.contains("- [x] T3.1: Done thing"));
        assert!(result.contains("- [ ] T4.1: Pending thing"));
    }

    #[test]
    fn test_extract_query_context_collapses_archive_by_content_pattern() {
        let input = "\
## Archive Summary\n\
- Phase 1: Context Foundry Visualizer (1 task)\n\
- Phase 2: TUI polish (3 tasks)\n\
- Discovery Round 34 (1 tasks archived)\n\
- Roadmap (6 tasks)\n\
- Human Tasks: H1.1, H2.1, H3.1 (3 tasks)\n\
- **Total archived: ~175 tasks**\n\
\n\
## Phase 4\n\
- [ ] T4.1: Pending thing\n";
        let result = extract_query_context(input);
        // Header does not contain "archived" but >50% of lines match archive patterns
        assert!(result.contains("## Archive Summary"));
        assert!(result.contains("(6 archive references omitted)"));
        assert!(!result.contains("- Phase 1: Context Foundry Visualizer"));
        assert!(!result.contains("- Discovery Round 34"));
        assert!(!result.contains("- Roadmap (6 tasks)"));
        // Pending section preserved
        assert!(result.contains("- [ ] T4.1: Pending thing"));
    }

    #[test]
    fn test_extract_query_context_preserves_genuine_non_task_sections() {
        let input = "\
## Notes\n\
This project uses a custom build pipeline.\n\
See ARCHITECTURE.md for details.\n\
\n\
## Phase 1\n\
- [ ] T1.1: Pending task\n";
        let result = extract_query_context(input);
        // Notes section has no archive patterns -- preserved in full
        assert!(result.contains("## Notes"));
        assert!(result.contains("This project uses a custom build pipeline."));
        assert!(result.contains("See ARCHITECTURE.md for details."));
        assert!(result.contains("- [ ] T1.1: Pending task"));
    }

    #[test]
    fn test_extract_query_context_empty_input() {
        assert_eq!(extract_query_context(""), "");
        assert_eq!(extract_query_context("   \n  \n"), "");
    }
}

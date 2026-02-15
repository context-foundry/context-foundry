use anyhow::Result;
use std::path::Path;
use std::process::Command;

use crate::utils::truncate_str;

pub fn commit_and_push(
    project_dir: &Path,
    task_id: &str,
    task_desc: &str,
    is_wip: bool,
) -> Result<bool> {
    // Stage all changes except .buildloop/logs
    Command::new("git")
        .args(["add", "-A"])
        .current_dir(project_dir)
        .output()?;

    let _ = Command::new("git")
        .args(["reset", "--", ".buildloop/logs/"])
        .current_dir(project_dir)
        .output();

    // Check if there's anything to commit
    let status = Command::new("git")
        .args(["diff", "--cached", "--quiet"])
        .current_dir(project_dir)
        .status()?;

    if status.success() {
        return Ok(false);
    }

    let short_desc = truncate_str(task_desc, 72);

    let msg = if is_wip {
        format!(
            "WIP({}): {}\n\nValidation did not pass. Committing to preserve progress.\n\nAutomated by: foundry",
            task_id, short_desc
        )
    } else {
        format!(
            "feat({}): {}\n\nImplemented and validated by autonomous build loop.\n\nAutomated by: foundry",
            task_id, short_desc
        )
    };

    let result = Command::new("git")
        .args(["commit", "-m", &msg])
        .current_dir(project_dir)
        .output()?;

    if !result.status.success() {
        return Ok(false);
    }

    // Push (best effort)
    let _ = Command::new("git")
        .args(["push", "origin", "main"])
        .current_dir(project_dir)
        .output();

    Ok(true)
}

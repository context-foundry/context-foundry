use anyhow::Result;
use std::{
    fs,
    path::{Path, PathBuf},
};

use crate::utils::atomic_write_file;

use super::model::{
    PromptHistoryEntry, MAX_PROMPT_HISTORY_ENTRIES, STUDIO_PROMPT_HISTORY_FILE, STUDIO_ROOT_DIR,
};

fn prompt_history_path(project_dir: &Path) -> PathBuf {
    project_dir
        .join(STUDIO_ROOT_DIR)
        .join(STUDIO_PROMPT_HISTORY_FILE)
}

fn trim_prompt_history(entries: &mut Vec<PromptHistoryEntry>) {
    if entries.len() > MAX_PROMPT_HISTORY_ENTRIES {
        entries.truncate(MAX_PROMPT_HISTORY_ENTRIES);
    }
}

pub(super) fn load_prompt_history(project_dir: &Path) -> Vec<PromptHistoryEntry> {
    let path = prompt_history_path(project_dir);
    let Ok(contents) = fs::read_to_string(path) else {
        return Vec::new();
    };
    let Ok(mut entries) = serde_json::from_str::<Vec<PromptHistoryEntry>>(&contents) else {
        return Vec::new();
    };
    trim_prompt_history(&mut entries);
    entries
}

pub(super) fn persist_prompt_history(
    project_dir: &Path,
    entries: &[PromptHistoryEntry],
) -> Result<()> {
    let path = prompt_history_path(project_dir);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut trimmed = entries.to_vec();
    trim_prompt_history(&mut trimmed);
    atomic_write_file(&path, serde_json::to_string_pretty(&trimmed)?.as_bytes())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use anyhow::Result;
    use chrono::Utc;
    use std::fs;

    use super::{load_prompt_history, persist_prompt_history};
    use crate::studio::{model::PromptHistoryEntry, test_helpers::temp_test_dir};

    #[test]
    fn load_prompt_history_missing_file_returns_empty() {
        let project_dir = temp_test_dir("foundry-prompt-history-missing");
        assert!(load_prompt_history(&project_dir).is_empty());
    }

    #[test]
    fn prompt_history_round_trips_through_json() -> Result<()> {
        let project_dir = temp_test_dir("foundry-prompt-history-round-trip");
        let entries = vec![PromptHistoryEntry {
            created_at: Utc::now(),
            prompt: "build the artifact".into(),
            provider_mode: "both".into(),
            workspace_mode: "isolated".into(),
            contract_name: "Standard Build Contract".into(),
            follow_up: false,
        }];

        persist_prompt_history(&project_dir, &entries)?;
        let loaded = load_prompt_history(&project_dir);

        assert_eq!(loaded.len(), 1);
        assert_eq!(loaded[0].prompt, "build the artifact");
        fs::remove_dir_all(project_dir)?;
        Ok(())
    }

    #[test]
    fn persist_prompt_history_trims_to_reasonable_limit() -> Result<()> {
        let project_dir = temp_test_dir("foundry-prompt-history-cap");
        let entries = (0..(super::super::model::MAX_PROMPT_HISTORY_ENTRIES + 5))
            .map(|idx| PromptHistoryEntry {
                created_at: Utc::now(),
                prompt: format!("prompt {}", idx),
                provider_mode: "both".into(),
                workspace_mode: "isolated".into(),
                contract_name: "Standard Build Contract".into(),
                follow_up: false,
            })
            .collect::<Vec<_>>();

        persist_prompt_history(&project_dir, &entries)?;
        let loaded = load_prompt_history(&project_dir);

        fs::remove_dir_all(project_dir)?;
        assert_eq!(
            loaded.len(),
            super::super::model::MAX_PROMPT_HISTORY_ENTRIES
        );
        assert_eq!(loaded[0].prompt, "prompt 0");
        Ok(())
    }
}

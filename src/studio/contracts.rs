use anyhow::{Context, Result};
use chrono::Utc;
use std::{
    fs,
    path::{Path, PathBuf},
};

use crate::utils::atomic_write_file;

use super::{
    attachments::{attachment_sidecar_path, external_attachment_count, load_attachment_specs},
    model::{
        ExecutionContract, FocusedPane, PendingStudioAction, STUDIO_CONTRACTS_DIR, STUDIO_ROOT_DIR,
        STUDIO_SELECTED_CONTRACT_FILE,
    },
    state::StudioState,
    ui::input::queue_editor_action,
};

pub(super) fn execution_contracts_dir(project_dir: &Path) -> PathBuf {
    project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR)
}

pub(super) fn execution_contract_list_label(contract: &ExecutionContract) -> String {
    if contract.attachments.is_empty() {
        contract.name.clone()
    } else {
        let external_count = external_attachment_count(&contract.attachments);
        if external_count == 0 {
            format!(
                "{} [{} attached]",
                contract.name,
                contract.attachments.len()
            )
        } else {
            format!(
                "{} [{} attached, {} external]",
                contract.name,
                contract.attachments.len(),
                external_count
            )
        }
    }
}

fn execution_contract_selection_path(project_dir: &Path) -> PathBuf {
    execution_contracts_dir(project_dir).join(STUDIO_SELECTED_CONTRACT_FILE)
}

pub(super) fn default_execution_contract_content() -> &'static str {
    r#"# Standard Build Contract

- Inspect the repository before editing anything.
- Work only inside this workspace: {{workspace_dir}}
- Prefer the existing stack, conventions, and architecture over rewrites.
- Favor polished, production-quality results over placeholder output.
- If the request implies analysis, reporting, dashboarding, or visualization, generate a self-contained HTML artifact.
- Write primary generated artifacts to: {{artifact_dir}}
- If you create an HTML report, use inline CSS/JS so the file can be opened directly in a browser.
- End with a concise summary of assumptions, files changed, and the exact artifact path(s) to open.

## Delivery Guidance

- When possible, make the result feel intentional and finished, not generic.
- If data sources are ambiguous, inspect the repository and state what you found.
- If the user asks for a dashboard or report, compute the answer from repository data and create the artifact instead of only describing it.
- Treat this contract as instructions layered on top of the user's objective, not a replacement for it."#
}

fn new_execution_contract_content(name: &str) -> String {
    default_execution_contract_content().replacen(
        "# Standard Build Contract",
        &format!("# {}", name),
        1,
    )
}

fn ensure_execution_contracts_exist(project_dir: &Path) -> Result<()> {
    let dir = execution_contracts_dir(project_dir);
    fs::create_dir_all(&dir)?;

    let has_visible_contract = fs::read_dir(&dir)?
        .filter_map(|entry| entry.ok())
        .any(|entry| {
            let path = entry.path();
            path.is_file()
                && path.extension().and_then(|ext| ext.to_str()) == Some("md")
                && !entry.file_name().to_string_lossy().starts_with('.')
        });

    if !has_visible_contract {
        fs::write(
            dir.join("standard.md"),
            default_execution_contract_content(),
        )?;
    }

    Ok(())
}

pub(super) fn load_execution_contracts(
    project_dir: &Path,
) -> Result<(Vec<ExecutionContract>, usize)> {
    load_execution_contracts_with_selection(project_dir, None)
}

pub(super) fn load_execution_contracts_with_selection(
    project_dir: &Path,
    preferred_file_name: Option<&str>,
) -> Result<(Vec<ExecutionContract>, usize)> {
    ensure_execution_contracts_exist(project_dir)?;
    let dir = execution_contracts_dir(project_dir);
    let selected_path = execution_contract_selection_path(project_dir);
    let selected_file = preferred_file_name
        .map(str::to_string)
        .or_else(|| {
            fs::read_to_string(&selected_path)
                .ok()
                .map(|value| value.trim().to_string())
        })
        .filter(|value| !value.is_empty());

    let mut contracts = Vec::new();
    let mut entries: Vec<_> = fs::read_dir(&dir)?.filter_map(|entry| entry.ok()).collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        let file_name = entry.file_name().to_string_lossy().to_string();
        if file_name.starts_with('.') {
            continue;
        }
        let path = entry.path();
        if !path.is_file() || path.extension().and_then(|ext| ext.to_str()) != Some("md") {
            continue;
        }
        let body = fs::read_to_string(&path)
            .with_context(|| format!("failed to read execution contract {}", path.display()))?;
        let attachments = load_attachment_specs(&path);
        contracts.push(ExecutionContract {
            name: execution_contract_name(&file_name, &body),
            file_name,
            path,
            body,
            attachments,
        });
    }

    if contracts.is_empty() {
        anyhow::bail!("no execution contracts available");
    }

    let selected_index = selected_file
        .as_deref()
        .and_then(|wanted| {
            contracts
                .iter()
                .position(|contract| contract.file_name == wanted)
        })
        .unwrap_or(0);
    persist_selected_execution_contract(
        project_dir,
        &contracts
            .get(selected_index)
            .context("selected execution contract index out of bounds")?
            .file_name,
    )?;
    Ok((contracts, selected_index))
}

fn execution_contract_name(file_name: &str, body: &str) -> String {
    body.lines()
        .find_map(|line| {
            let trimmed = line.trim();
            trimmed
                .strip_prefix("# ")
                .map(str::trim)
                .filter(|name| !name.is_empty())
                .map(ToOwned::to_owned)
        })
        .unwrap_or_else(|| file_name.trim_end_matches(".md").replace('-', " "))
}

pub(super) fn persist_selected_execution_contract(
    project_dir: &Path,
    file_name: &str,
) -> Result<()> {
    let path = execution_contract_selection_path(project_dir);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    atomic_write_file(&path, file_name.as_bytes())?;
    Ok(())
}

pub(super) fn cycle_execution_contract(state: &mut StudioState, forward: bool) {
    if state.execution_contracts.is_empty() {
        return;
    }

    let len = state.execution_contracts.len();
    let current = state.selected_execution_contract_index();
    let selected_index = if forward {
        (current + 1) % len
    } else {
        current
            .checked_sub(1)
            .unwrap_or_else(|| len.saturating_sub(1))
    };
    state.set_selected_execution_contract_index(selected_index);
    if let Some(contract) = state.selected_execution_contract() {
        if let Err(err) =
            persist_selected_execution_contract(&state.project_dir, &contract.file_name)
        {
            state.log(format!("failed to persist selected contract: {}", err));
        } else {
            state.log(format!("execution contract: {}", contract.name));
        }
    }
}

pub(super) fn create_execution_contract(state: &mut StudioState) -> Result<()> {
    let dir = execution_contracts_dir(&state.project_dir);
    fs::create_dir_all(&dir)?;
    let contract_name = format!("Custom Contract {}", Utc::now().format("%H:%M:%S"));
    let file_name = format!("contract-{}.md", Utc::now().format("%Y%m%d-%H%M%S"));
    let path = dir.join(&file_name);
    atomic_write_file(&path, new_execution_contract_content(&contract_name).as_bytes())?;
    atomic_write_file(&attachment_sidecar_path(&path), b"[]\n")?;
    let (contracts, selected_index) =
        load_execution_contracts_with_selection(&state.project_dir, Some(&file_name))?;
    state.execution_contracts = contracts;
    state.set_selected_execution_contract_index(selected_index);
    state.focused_pane = FocusedPane::Contracts;
    queue_editor_action(
        state,
        PendingStudioAction::EditExecutionContract {
            path,
            action_label: "new contract",
        },
    );
    state.log("created new execution contract");
    Ok(())
}

pub(super) fn edit_selected_execution_contract(state: &mut StudioState) {
    let Some(selected) = state.selected_execution_contract().cloned() else {
        state.log("no execution contract to edit");
        return;
    };
    queue_editor_action(
        state,
        PendingStudioAction::EditExecutionContract {
            path: selected.path,
            action_label: "contract",
        },
    );
    state.focused_pane = FocusedPane::Contracts;
}

pub(super) fn delete_selected_execution_contract(state: &mut StudioState) -> Result<()> {
    if state.execution_contracts.len() <= 1 {
        anyhow::bail!("cannot delete the last execution contract");
    }

    let selected_index = state.selected_execution_contract_index();
    let selected = state
        .selected_execution_contract()
        .cloned()
        .context("no execution contract selected")?;
    let trash_dir = execution_contracts_dir(&state.project_dir).join(".trash");
    fs::create_dir_all(&trash_dir)?;
    let trash_name = format!(
        "{}-{}",
        Utc::now().format("%Y%m%d-%H%M%S"),
        selected.file_name
    );
    fs::rename(&selected.path, trash_dir.join(trash_name))?;
    let sidecar_path = attachment_sidecar_path(&selected.path);
    if sidecar_path.exists() {
        let sidecar_name = sidecar_path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("contract.attachments.json");
        let trashed_sidecar_name =
            format!("{}-{}", Utc::now().format("%Y%m%d-%H%M%S"), sidecar_name);
        fs::rename(&sidecar_path, trash_dir.join(trashed_sidecar_name))?;
    }

    let preferred_file_name = state
        .execution_contracts
        .iter()
        .enumerate()
        .find_map(|(idx, contract)| {
            (idx != selected_index
                && (idx == selected_index.saturating_add(1)
                    || idx == selected_index.saturating_sub(1)))
            .then(|| contract.file_name.clone())
        })
        .or_else(|| {
            state
                .execution_contracts
                .iter()
                .enumerate()
                .find_map(|(idx, contract)| {
                    (idx != selected_index).then(|| contract.file_name.clone())
                })
        });
    let (contracts, selected_index) = load_execution_contracts_with_selection(
        &state.project_dir,
        preferred_file_name.as_deref(),
    )?;
    let deleted_name = selected.name;
    state.execution_contracts = contracts;
    state.set_selected_execution_contract_index(selected_index);
    if let Some(contract) = state.selected_execution_contract() {
        persist_selected_execution_contract(&state.project_dir, &contract.file_name)?;
    }
    state.log(format!("deleted execution contract: {}", deleted_name));
    Ok(())
}

#[cfg(test)]
mod tests {
    use anyhow::Result;
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    use super::super::{
        attachments::{attachment_sidecar_path, AttachmentMode, AttachmentSpec},
        model::{STUDIO_CONTRACTS_DIR, STUDIO_ROOT_DIR},
        test_helpers::{temp_test_dir, test_contract, test_state},
    };
    use super::{
        create_execution_contract, delete_selected_execution_contract,
        execution_contract_list_label, load_execution_contracts,
        load_execution_contracts_with_selection,
    };

    #[test]
    fn execution_contract_list_label_includes_attachment_count() {
        let mut contract = test_contract();
        assert_eq!(
            execution_contract_list_label(&contract),
            "Standard Build Contract"
        );

        contract.attachments = vec![
            AttachmentSpec {
                path: "docs/one.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            AttachmentSpec {
                path: "docs/two.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
        ];
        assert_eq!(
            execution_contract_list_label(&contract),
            "Standard Build Contract [2 attached]"
        );

        contract.attachments.push(AttachmentSpec {
            path: "/tmp/external.md".into(),
            mode: AttachmentMode::InlineFile,
            label: None,
        });
        assert_eq!(
            execution_contract_list_label(&contract),
            "Standard Build Contract [3 attached, 1 external]"
        );
    }

    #[test]
    fn load_execution_contracts_bootstraps_default_contract() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir = std::env::temp_dir().join(format!("foundry-studio-contracts-{}", unique));
        fs::create_dir_all(&project_dir)?;

        let (contracts, selected) = load_execution_contracts(&project_dir)?;
        fs::remove_dir_all(&project_dir)?;

        assert_eq!(selected, 0);
        assert_eq!(contracts.len(), 1);
        assert_eq!(contracts[0].file_name, "standard.md");
        Ok(())
    }

    #[test]
    fn create_execution_contract_creates_empty_attachment_sidecar() -> Result<()> {
        let project_dir = temp_test_dir("foundry-create-contract-sidecar");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;

        create_execution_contract(&mut state)?;

        let sidecar_path =
            attachment_sidecar_path(&state.selected_execution_contract().unwrap().path);
        let sidecar = fs::read_to_string(&sidecar_path)?;

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(sidecar, "[]\n");
        Ok(())
    }

    #[test]
    fn delete_selected_execution_contract_moves_contract_and_sidecar_to_trash() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir =
            std::env::temp_dir().join(format!("foundry-studio-delete-contract-{}", unique));
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        fs::write(
            contracts_dir.join("standard.md"),
            "# Standard Build Contract\n",
        )?;
        fs::write(contracts_dir.join("reporting.md"), "# Reporting Contract\n")?;
        fs::write(
            contracts_dir.join("reporting.attachments.json"),
            r#"[{"path":"docs/report.md","mode":"inline_file"}]"#,
        )?;

        let (contracts, selected_index) =
            load_execution_contracts_with_selection(&project_dir, Some("reporting.md"))?;
        let mut state = test_state();
        state.project_dir = project_dir.clone();
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;

        delete_selected_execution_contract(&mut state)?;

        assert_eq!(state.execution_contracts.len(), 1);
        assert_eq!(state.execution_contracts[0].file_name, "standard.md");
        assert!(contracts_dir.join(".trash").exists());
        assert!(!contracts_dir.join("reporting.attachments.json").exists());
        let trashed_entries = fs::read_dir(contracts_dir.join(".trash"))?
            .filter_map(|entry| entry.ok())
            .map(|entry| entry.file_name().to_string_lossy().to_string())
            .collect::<Vec<_>>();
        assert!(trashed_entries
            .iter()
            .any(|name| name.ends_with("reporting.attachments.json")));

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }
}

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeSet,
    fs,
    path::{Component, Path, PathBuf},
};

#[cfg(target_os = "macos")]
use std::process::Command;

use super::shared::should_skip_snapshot_path;
#[cfg(not(target_os = "macos"))]
use super::ui::input::queue_editor_action;
use super::{
    model::{
        FocusedPane, PendingStudioAction, MAX_INLINE_FILE_BYTES, MAX_TOTAL_ATTACHMENT_CHARS,
        MAX_TREE_DEPTH, MAX_TREE_FILES,
    },
    state::StudioState,
};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub(super) struct AttachmentSpec {
    pub(super) path: String,
    pub(super) mode: AttachmentMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub(super) label: Option<String>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(super) enum AttachmentMode {
    InlineFile,
    DirectoryTree,
}

#[derive(Clone, Debug)]
pub(super) struct ResolvedAttachment {
    pub(super) spec: AttachmentSpec,
    pub(super) label: String,
    pub(super) content: String,
    pub(super) truncated: bool,
    pub(super) error: Option<String>,
}

#[derive(Clone, Debug, Default)]
pub(super) struct AttachmentManagerState {
    pub(super) selected_attachment: usize,
    pub(super) marked_attachments: BTreeSet<usize>,
}

pub(super) fn attachment_requested_display_path(spec: &AttachmentSpec) -> String {
    let trimmed = spec.path.trim().replace('\\', "/");
    trimmed
        .trim_end_matches('/')
        .trim_end_matches('\\')
        .to_string()
}

fn attachment_path_has_parent_reference(path: &Path) -> bool {
    path.components()
        .any(|component| matches!(component, Component::ParentDir))
}

fn is_external_attachment_path(path: &str) -> bool {
    Path::new(path.trim()).is_absolute()
}

pub(super) fn external_attachment_count(specs: &[AttachmentSpec]) -> usize {
    specs
        .iter()
        .filter(|spec| is_external_attachment_path(&spec.path))
        .count()
}

pub(super) fn normalize_absolute_display_path(path: &Path) -> String {
    let display = path.to_string_lossy().replace('\\', "/");
    if display.len() > 1 && display.ends_with('/') && !display.ends_with(":/") {
        display.trim_end_matches('/').to_string()
    } else {
        display
    }
}

pub(super) fn normalize_relative_display_path(path: &Path) -> String {
    let mut parts = Vec::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::Normal(value) => parts.push(value.to_string_lossy().to_string()),
            Component::ParentDir => {
                if !parts.is_empty() {
                    parts.pop();
                } else {
                    parts.push("..".to_string());
                }
            }
            Component::RootDir | Component::Prefix(_) => {}
        }
    }

    if parts.is_empty() {
        ".".to_string()
    } else {
        parts.join("/")
    }
}

fn attachment_display_label(spec: &AttachmentSpec, display_path: &str) -> String {
    let custom_label = spec
        .label
        .as_deref()
        .map(str::trim)
        .filter(|label| !label.is_empty());
    match custom_label {
        Some(label) if label != display_path => format!("{} [{}]", label, display_path),
        Some(label) => label.to_string(),
        None => display_path.to_string(),
    }
}

fn attachment_mode_label(mode: &AttachmentMode) -> &'static str {
    match mode {
        AttachmentMode::InlineFile => "inline file",
        AttachmentMode::DirectoryTree => "directory tree",
    }
}

fn attachment_error(
    spec: &AttachmentSpec,
    display_path: &str,
    message: String,
) -> ResolvedAttachment {
    ResolvedAttachment {
        spec: spec.clone(),
        label: attachment_display_label(spec, display_path),
        content: format!("[ATTACHMENT ERROR: {}]", message),
        truncated: false,
        error: Some(message),
    }
}

fn truncate_with_notice(text: &str, max_chars: usize, notice: &str) -> String {
    if text.chars().count() <= max_chars {
        return text.to_string();
    }
    if max_chars == 0 {
        return String::new();
    }

    let notice_chars = notice.chars().count();
    if max_chars <= notice_chars {
        return notice.chars().take(max_chars).collect();
    }

    let prefix_chars = max_chars - notice_chars;
    let cutoff = text
        .char_indices()
        .nth(prefix_chars)
        .map(|(idx, _)| idx)
        .unwrap_or(text.len());
    format!("{}{}", &text[..cutoff], notice)
}

fn human_readable_bytes(size: u64) -> String {
    if size >= 1024 * 1024 {
        format!("{:.1} MB", size as f64 / (1024.0 * 1024.0))
    } else if size >= 1024 {
        format!("{:.1} KB", size as f64 / 1024.0)
    } else {
        format!("{} B", size)
    }
}

fn directory_has_children(path: &Path) -> bool {
    fs::read_dir(path)
        .ok()
        .and_then(|mut entries| entries.next())
        .is_some()
}

fn collect_directory_tree_lines(
    current_abs: &Path,
    current_project_rel: Option<&Path>,
    depth: usize,
    lines: &mut Vec<String>,
    entry_count: &mut usize,
    truncated: &mut bool,
) -> Result<()> {
    let mut entries: Vec<_> = fs::read_dir(current_abs)?
        .filter_map(|entry| entry.ok())
        .collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        if *entry_count >= MAX_TREE_FILES {
            lines.push(format!(
                "{}[truncated: max {} entries reached]",
                "  ".repeat(depth + 1),
                MAX_TREE_FILES
            ));
            *truncated = true;
            break;
        }

        let name = entry.file_name().to_string_lossy().to_string();
        let indent = "  ".repeat(depth + 1);
        *entry_count += 1;

        let child_project_rel = current_project_rel.map(|relative| relative.join(&name));
        if let Some(child_rel) = child_project_rel.as_deref() {
            if should_skip_snapshot_path(child_rel) {
                lines.push(format!("{}{} [snapshot-excluded]", indent, name));
                continue;
            }
        }

        let file_type = match entry.file_type() {
            Ok(file_type) => file_type,
            Err(err) => {
                lines.push(format!("{}{} [error: {}]", indent, name, err));
                continue;
            }
        };

        if file_type.is_symlink() {
            lines.push(format!("{}{} [symlink omitted]", indent, name));
            continue;
        }

        if file_type.is_file() {
            let size = entry
                .metadata()
                .map(|metadata| metadata.len())
                .unwrap_or_default();
            lines.push(format!(
                "{}{} ({})",
                indent,
                name,
                human_readable_bytes(size)
            ));
            continue;
        }

        if file_type.is_dir() {
            lines.push(format!("{}{}/", indent, name));
            if depth + 1 >= MAX_TREE_DEPTH {
                if directory_has_children(&entry.path()) {
                    lines.push(format!(
                        "{}  [truncated: max depth {} reached]",
                        indent, MAX_TREE_DEPTH
                    ));
                    *truncated = true;
                }
                continue;
            }
            collect_directory_tree_lines(
                &entry.path(),
                child_project_rel.as_deref(),
                depth + 1,
                lines,
                entry_count,
                truncated,
            )?;
            continue;
        }

        lines.push(format!("{}{}", indent, name));
    }

    Ok(())
}

fn render_directory_tree(
    root_abs: &Path,
    root_display_path: &str,
    root_project_rel: Option<&Path>,
) -> Result<(String, bool)> {
    let mut lines = vec![format!("{}/", root_display_path)];
    let mut entry_count = 0usize;
    let mut truncated = false;

    if root_project_rel.is_some_and(should_skip_snapshot_path) {
        lines.push("[warning] path is excluded from isolated workspace snapshots".to_string());
    }

    collect_directory_tree_lines(
        root_abs,
        root_project_rel,
        0,
        &mut lines,
        &mut entry_count,
        &mut truncated,
    )?;

    Ok((lines.join("\n"), truncated))
}

fn resolve_attachment_with_root(
    spec: &AttachmentSpec,
    project_dir: &Path,
    canonical_project: &Path,
) -> ResolvedAttachment {
    let requested_path = attachment_requested_display_path(spec);
    if requested_path.is_empty() {
        return attachment_error(
            spec,
            "<empty attachment path>",
            "attachment path is empty".to_string(),
        );
    }

    let requested = Path::new(spec.path.trim());
    if !requested.is_absolute() && attachment_path_has_parent_reference(requested) {
        return attachment_error(
            spec,
            &requested_path,
            format!(
                "attachment path cannot contain '..' components: {}",
                requested_path
            ),
        );
    }

    let lookup_path = if requested.is_absolute() {
        requested.to_path_buf()
    } else {
        project_dir.join(requested)
    };
    let canonical_target = match fs::canonicalize(&lookup_path) {
        Ok(path) => path,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            return attachment_error(
                spec,
                &requested_path,
                format!("attachment path does not exist: {}", requested_path),
            );
        }
        Err(err) => {
            return attachment_error(
                spec,
                &requested_path,
                format!("failed to resolve attachment {}: {}", requested_path, err),
            );
        }
    };

    let project_relative = match canonical_target.strip_prefix(canonical_project) {
        Ok(path) => Some(path.to_path_buf()),
        Err(_) if requested.is_absolute() => None,
        Err(_) => {
            return attachment_error(
                spec,
                &requested_path,
                format!(
                    "attachment path escapes the project root: {}",
                    requested_path
                ),
            );
        }
    };
    let display_path = project_relative
        .as_deref()
        .map(normalize_relative_display_path)
        .unwrap_or_else(|| normalize_absolute_display_path(&canonical_target));

    match spec.mode {
        AttachmentMode::InlineFile => {
            if !canonical_target.is_file() {
                return attachment_error(
                    spec,
                    &display_path,
                    format!("attachment is not a file: {}", display_path),
                );
            }

            let bytes = match fs::read(&canonical_target) {
                Ok(bytes) => bytes,
                Err(err) => {
                    return attachment_error(
                        spec,
                        &display_path,
                        format!("failed to read attachment {}: {}", display_path, err),
                    );
                }
            };

            let truncated = bytes.len() > MAX_INLINE_FILE_BYTES;
            let content = if truncated {
                format!(
                    "{}\n[truncated: file exceeds {} bytes]",
                    String::from_utf8_lossy(&bytes[..MAX_INLINE_FILE_BYTES]),
                    MAX_INLINE_FILE_BYTES
                )
            } else {
                String::from_utf8_lossy(&bytes).to_string()
            };

            ResolvedAttachment {
                spec: spec.clone(),
                label: attachment_display_label(spec, &display_path),
                content,
                truncated,
                error: None,
            }
        }
        AttachmentMode::DirectoryTree => {
            if !canonical_target.is_dir() {
                return attachment_error(
                    spec,
                    &display_path,
                    format!("attachment is not a directory: {}", display_path),
                );
            }

            match render_directory_tree(
                &canonical_target,
                &display_path,
                project_relative.as_deref(),
            ) {
                Ok((content, truncated)) => ResolvedAttachment {
                    spec: spec.clone(),
                    label: attachment_display_label(spec, &display_path),
                    content,
                    truncated,
                    error: None,
                },
                Err(err) => attachment_error(
                    spec,
                    &display_path,
                    format!("failed to list attachment {}: {}", display_path, err),
                ),
            }
        }
    }
}

#[cfg(test)]
pub(super) fn resolve_attachment(spec: &AttachmentSpec, project_dir: &Path) -> ResolvedAttachment {
    let requested_path = attachment_requested_display_path(spec);
    let canonical_project = match fs::canonicalize(project_dir) {
        Ok(path) => path,
        Err(err) => {
            return attachment_error(
                spec,
                requested_path.as_str(),
                format!(
                    "failed to resolve project root {}: {}",
                    project_dir.display(),
                    err
                ),
            );
        }
    };

    resolve_attachment_with_root(spec, project_dir, &canonical_project)
}

pub(super) fn resolve_all_attachments(
    specs: &[AttachmentSpec],
    project_dir: &Path,
) -> Vec<ResolvedAttachment> {
    if specs.is_empty() {
        return Vec::new();
    }

    let canonical_project = match fs::canonicalize(project_dir) {
        Ok(path) => path,
        Err(err) => {
            return specs
                .iter()
                .map(|spec| {
                    attachment_error(
                        spec,
                        attachment_requested_display_path(spec).as_str(),
                        format!(
                            "failed to resolve project root {}: {}",
                            project_dir.display(),
                            err
                        ),
                    )
                })
                .collect();
        }
    };

    let mut remaining_chars = MAX_TOTAL_ATTACHMENT_CHARS;
    let mut resolved = Vec::with_capacity(specs.len());

    for spec in specs {
        let mut attachment = resolve_attachment_with_root(spec, project_dir, &canonical_project);
        let content_chars = attachment.content.chars().count();
        if content_chars > remaining_chars {
            attachment.content = truncate_with_notice(
                &attachment.content,
                remaining_chars,
                "\n[truncated: total attachment size budget reached]",
            );
            attachment.truncated = true;
        }
        remaining_chars = remaining_chars.saturating_sub(attachment.content.chars().count());
        resolved.push(attachment);
    }

    resolved
}

pub(super) fn format_attachments_block(resolved: &[ResolvedAttachment]) -> String {
    if resolved.is_empty() {
        return String::new();
    }

    let mut blocks = Vec::with_capacity(resolved.len() + 1);
    blocks.push("Attached context:".to_string());
    let external_count = resolved
        .iter()
        .filter(|attachment| is_external_attachment_path(&attachment.spec.path))
        .count();
    if external_count > 0 {
        blocks.push(format!(
            "[warning] {} external attachment(s) are outside the project root and their contents will be sent to the model",
            external_count
        ));
    }

    for attachment in resolved {
        let line_count = if attachment.content.is_empty() {
            0
        } else {
            attachment.content.lines().count()
        };
        let mut meta = vec![
            attachment_mode_label(&attachment.spec.mode).to_string(),
            format!(
                "{} {}",
                line_count,
                if line_count == 1 { "line" } else { "lines" }
            ),
        ];
        if attachment.error.is_some() {
            meta.push("error".to_string());
        } else if attachment.truncated {
            meta.push("truncated".to_string());
        }
        blocks.push(format!(
            "--- BEGIN ATTACHMENT: {} ({}) ---\n{}\n--- END ATTACHMENT: {} ---",
            attachment.label,
            meta.join(", "),
            attachment.content,
            attachment.label
        ));
    }

    format!("\n\n{}", blocks.join("\n\n"))
}

pub(super) fn attachment_sidecar_path(contract_path: &Path) -> PathBuf {
    contract_path.with_extension("attachments.json")
}

pub(super) fn attachment_mode_summary(mode: AttachmentMode) -> &'static str {
    match mode {
        AttachmentMode::InlineFile => "file",
        AttachmentMode::DirectoryTree => "folder",
    }
}

pub(super) fn load_attachment_specs(contract_path: &Path) -> Vec<AttachmentSpec> {
    let sidecar_path = attachment_sidecar_path(contract_path);
    let content = match fs::read_to_string(&sidecar_path) {
        Ok(content) => content,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Vec::new(),
        Err(err) => {
            eprintln!(
                "Foundry Studio: failed to read attachment sidecar {}: {}",
                sidecar_path.display(),
                err
            );
            return Vec::new();
        }
    };

    match serde_json::from_str::<Vec<AttachmentSpec>>(&content) {
        Ok(specs) => specs,
        Err(err) => {
            eprintln!(
                "Foundry Studio: failed to parse attachment sidecar {}: {}",
                sidecar_path.display(),
                err
            );
            Vec::new()
        }
    }
}

pub(super) fn persist_attachment_specs(
    contract_path: &Path,
    specs: &[AttachmentSpec],
) -> Result<()> {
    let sidecar_path = attachment_sidecar_path(contract_path);
    if let Some(parent) = sidecar_path.parent() {
        fs::create_dir_all(parent)?;
    }
    let serialized = serde_json::to_string_pretty(specs)?;
    fs::write(sidecar_path, format!("{}\n", serialized))?;
    Ok(())
}

pub(super) fn open_attachment_manager(state: &mut StudioState) {
    state.attachment_manager = Some(AttachmentManagerState::default());
    state.sync_attachment_manager_selection();
    state.focused_pane = FocusedPane::Contracts;
}

pub(super) fn cycle_attachment_manager_selection(state: &mut StudioState, forward: bool) {
    let attachment_len = state.selected_execution_contract().attachments.len();
    if attachment_len == 0 {
        return;
    }

    if let Some(manager) = state.attachment_manager.as_mut() {
        manager.selected_attachment = if forward {
            (manager.selected_attachment + 1) % attachment_len
        } else {
            manager
                .selected_attachment
                .checked_sub(1)
                .unwrap_or_else(|| attachment_len.saturating_sub(1))
        };
    }
}

pub(super) fn toggle_selected_attachment_mark(state: &mut StudioState) {
    let attachment_len = state.selected_execution_contract().attachments.len();
    if attachment_len == 0 {
        return;
    }

    if let Some(manager) = state.attachment_manager.as_mut() {
        let selected = manager
            .selected_attachment
            .min(attachment_len.saturating_sub(1));
        if !manager.marked_attachments.insert(selected) {
            manager.marked_attachments.remove(&selected);
        }
    }
}

#[cfg(not(target_os = "macos"))]
fn edit_selected_execution_contract_attachments(state: &mut StudioState) -> Result<()> {
    let selected = state.selected_execution_contract().clone();
    let sidecar_path = attachment_sidecar_path(&selected.path);
    if !sidecar_path.exists() {
        fs::write(&sidecar_path, "[]\n")?;
    }
    queue_editor_action(
        state,
        PendingStudioAction::EditExecutionContract {
            path: sidecar_path,
            action_label: "contract attachments",
        },
    );
    state.focused_pane = FocusedPane::Contracts;
    Ok(())
}

pub(super) fn queue_selected_execution_contract_attachment_action(
    state: &mut StudioState,
) -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        let selected = state.selected_execution_contract().clone();
        state.pending_action = Some(PendingStudioAction::PickExecutionContractAttachment {
            contract_path: selected.path,
        });
        state.focused_pane = FocusedPane::Contracts;
        Ok(())
    }

    #[cfg(not(target_os = "macos"))]
    {
        edit_selected_execution_contract_attachments(state)
    }
}

pub(super) fn remove_selected_execution_contract_attachments(
    state: &mut StudioState,
) -> Result<()> {
    let attachment_len = state.selected_execution_contract().attachments.len();
    if attachment_len == 0 {
        state.log("contract has no attachments");
        return Ok(());
    }

    let indices = {
        let manager = state
            .attachment_manager
            .as_ref()
            .context("attachment manager is not open")?;
        if manager.marked_attachments.is_empty() {
            BTreeSet::from([manager
                .selected_attachment
                .min(attachment_len.saturating_sub(1))])
        } else {
            manager
                .marked_attachments
                .iter()
                .copied()
                .filter(|idx| *idx < attachment_len)
                .collect()
        }
    };

    let contract_path = state.selected_execution_contract().path.clone();
    let existing = load_attachment_specs(&contract_path);
    let removed_paths: Vec<String> = existing
        .iter()
        .enumerate()
        .filter(|(idx, _)| indices.contains(idx))
        .map(|(_, spec)| spec.path.clone())
        .collect();
    let retained: Vec<AttachmentSpec> = existing
        .into_iter()
        .enumerate()
        .filter(|(idx, _)| !indices.contains(idx))
        .map(|(_, spec)| spec)
        .collect();

    persist_attachment_specs(&contract_path, &retained)?;
    state.refresh_execution_contracts()?;
    if let Some(manager) = state.attachment_manager.as_mut() {
        manager.marked_attachments.clear();
        if retained.is_empty() {
            manager.selected_attachment = 0;
        } else {
            manager.selected_attachment = manager
                .selected_attachment
                .min(retained.len().saturating_sub(1));
        }
    }
    state.log(format!(
        "removed {} attachment(s){}",
        removed_paths.len(),
        if removed_paths.is_empty() {
            String::new()
        } else {
            format!(": {}", removed_paths.join(", "))
        }
    ));
    Ok(())
}

pub(super) fn infer_attachment_spec_from_selected_path(
    selected_path: &Path,
    project_dir: &Path,
) -> Result<AttachmentSpec> {
    let canonical_project = fs::canonicalize(project_dir).with_context(|| {
        format!(
            "failed to resolve project root for attachment picker: {}",
            project_dir.display()
        )
    })?;
    let canonical_selected = fs::canonicalize(selected_path).with_context(|| {
        format!(
            "failed to resolve selected attachment path: {}",
            selected_path.display()
        )
    })?;
    let mode = if canonical_selected.is_dir() {
        AttachmentMode::DirectoryTree
    } else if canonical_selected.is_file() {
        AttachmentMode::InlineFile
    } else {
        anyhow::bail!(
            "selected attachment is neither a file nor a directory: {}",
            selected_path.display()
        );
    };
    let path = canonical_selected
        .strip_prefix(&canonical_project)
        .map(normalize_relative_display_path)
        .unwrap_or_else(|_| normalize_absolute_display_path(&canonical_selected));

    Ok(AttachmentSpec {
        path,
        mode,
        label: None,
    })
}

pub(super) fn append_attachment_specs_for_paths(
    contract_path: &Path,
    project_dir: &Path,
    selected_paths: &[PathBuf],
) -> Result<Vec<AttachmentSpec>> {
    let mut specs = load_attachment_specs(contract_path);
    let mut changed = false;

    for selected_path in selected_paths {
        let spec = infer_attachment_spec_from_selected_path(selected_path, project_dir)?;
        if specs
            .iter()
            .any(|existing| existing.path == spec.path && existing.mode == spec.mode)
        {
            continue;
        }
        specs.push(spec);
        changed = true;
    }

    if changed || !attachment_sidecar_path(contract_path).exists() {
        persist_attachment_specs(contract_path, &specs)?;
    }

    Ok(specs)
}

#[cfg(target_os = "macos")]
pub(super) fn pick_attachment_paths(project_dir: &Path) -> Result<Vec<PathBuf>> {
    let script = r#"
ObjC.import("AppKit");
ObjC.import("Foundation");
var app = $.NSApplication.sharedApplication;
app.setActivationPolicy($.NSApplicationActivationPolicyRegular);
var panel = $.NSOpenPanel.openPanel;
panel.setCanChooseFiles(true);
panel.setCanChooseDirectories(true);
panel.setAllowsMultipleSelection(true);
panel.setCanCreateDirectories(false);
panel.setResolvesAliases(true);
panel.setPrompt($("Attach"));
panel.setMessage($("Choose file(s) or folder(s) to attach"));
var projectDir = $.NSProcessInfo.processInfo.environment.objectForKey("FOUNDRY_PROJECT_DIR");
if (projectDir) {
    panel.setDirectoryURL($.NSURL.fileURLWithPath($(ObjC.unwrap(projectDir))));
}
$.NSRunningApplication.currentApplication.activateWithOptions($.NSApplicationActivateIgnoringOtherApps);
app.activateIgnoringOtherApps(true);
panel.orderFrontRegardless;
var response = panel.runModal;
if (response !== $.NSModalResponseOK) { ""; }
else {
    var urls = panel.URLs;
    var out = [];
    for (var i = 0; i < urls.count; i++) {
        out.push(ObjC.unwrap(urls.objectAtIndex(i).path));
    }
    out.join("\n");
}
"#;

    let output = Command::new("osascript")
        .args(["-l", "JavaScript", "-e", script])
        .env("FOUNDRY_PROJECT_DIR", project_dir)
        .output()
        .context("failed to open macOS attachment picker")?;

    if !output.status.success() {
        anyhow::bail!(
            "attachment picker failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }

    Ok(String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(PathBuf::from)
        .collect())
}

#[cfg(not(target_os = "macos"))]
pub(super) fn pick_attachment_paths(_project_dir: &Path) -> Result<Vec<PathBuf>> {
    anyhow::bail!("native attachment picker is only available on macOS");
}

#[cfg(test)]
mod tests {
    use super::super::{
        contracts::load_execution_contracts,
        model::{FocusedPane, PendingStudioAction, STUDIO_CONTRACTS_DIR, STUDIO_ROOT_DIR},
        test_helpers::{temp_test_dir, test_state},
    };
    use super::*;
    #[cfg(unix)]
    use std::os::unix::fs::symlink;
    use std::{
        fs,
        path::{Path, PathBuf},
    };

    #[test]
    fn attachment_sidecar_path_rewrites_md_extension() {
        let contract_path = Path::new("/tmp/project/.foundry/studio/contracts/standard.md");
        assert_eq!(
            attachment_sidecar_path(contract_path),
            PathBuf::from("/tmp/project/.foundry/studio/contracts/standard.attachments.json")
        );
    }

    #[test]
    fn append_attachment_specs_for_paths_writes_relative_paths_and_modes() -> Result<()> {
        let project_dir = temp_test_dir("foundry-append-attachments");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::create_dir_all(&contracts_dir)?;
        fs::write(
            project_dir.join("Cargo.toml"),
            "[package]\nname = \"demo\"\n",
        )?;
        fs::write(project_dir.join("docs/readme.md"), "# Docs\n")?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;

        let specs = append_attachment_specs_for_paths(
            &contract_path,
            &project_dir,
            &[project_dir.join("Cargo.toml"), project_dir.join("docs")],
        )?;
        let loaded_specs = load_attachment_specs(&contract_path);

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(specs, loaded_specs);
        assert_eq!(specs.len(), 2);
        assert_eq!(specs[0].path, "Cargo.toml");
        assert_eq!(specs[0].mode, AttachmentMode::InlineFile);
        assert_eq!(specs[1].path, "docs");
        assert_eq!(specs[1].mode, AttachmentMode::DirectoryTree);
        Ok(())
    }

    #[test]
    fn append_attachment_specs_for_paths_allows_external_paths() -> Result<()> {
        let temp_root = temp_test_dir("foundry-append-external-attachments");
        let project_dir = temp_root.join("project");
        let external_dir = temp_root.join("external");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        fs::create_dir_all(&external_dir)?;
        fs::write(external_dir.join("notes.md"), "# Notes\n")?;
        fs::create_dir_all(external_dir.join("reports"))?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;

        let specs = append_attachment_specs_for_paths(
            &contract_path,
            &project_dir,
            &[external_dir.join("notes.md"), external_dir.join("reports")],
        )?;
        let canonical_external = fs::canonicalize(&external_dir)?;

        fs::remove_dir_all(&temp_root)?;
        assert_eq!(specs.len(), 2);
        assert_eq!(
            specs[0].path,
            normalize_absolute_display_path(&canonical_external.join("notes.md"))
        );
        assert_eq!(specs[0].mode, AttachmentMode::InlineFile);
        assert_eq!(
            specs[1].path,
            normalize_absolute_display_path(&canonical_external.join("reports"))
        );
        assert_eq!(specs[1].mode, AttachmentMode::DirectoryTree);
        Ok(())
    }

    #[test]
    fn load_attachment_specs_missing_file_returns_empty() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-missing");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;

        let specs = load_attachment_specs(&contract_path);

        fs::remove_dir_all(&project_dir)?;
        assert!(specs.is_empty());
        Ok(())
    }

    #[test]
    fn load_attachment_specs_malformed_json_returns_empty() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-malformed");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;
        fs::write(attachment_sidecar_path(&contract_path), "{not json")?;

        let specs = load_attachment_specs(&contract_path);

        fs::remove_dir_all(&project_dir)?;
        assert!(specs.is_empty());
        Ok(())
    }

    #[test]
    fn resolve_attachment_inline_file_reads_content() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-inline");
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::write(project_dir.join("docs/api.md"), "# API\nline two\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "docs/api.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(resolved.label, "docs/api.md");
        assert!(resolved.content.contains("# API"));
        assert!(resolved.error.is_none());
        assert!(!resolved.truncated);
        Ok(())
    }

    #[test]
    fn resolve_attachment_reads_absolute_path_outside_project() -> Result<()> {
        let temp_root = temp_test_dir("foundry-attachment-absolute");
        let project_dir = temp_root.join("project");
        let outside_path = temp_root.join("outside.md");
        fs::create_dir_all(&project_dir)?;
        fs::write(&outside_path, "secret\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: normalize_absolute_display_path(&outside_path),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );
        let canonical_outside = fs::canonicalize(&outside_path)?;

        fs::remove_dir_all(&temp_root)?;
        assert!(resolved.error.is_none());
        assert_eq!(
            resolved.label,
            normalize_absolute_display_path(&canonical_outside)
        );
        assert!(resolved.content.contains("secret"));
        Ok(())
    }

    #[test]
    fn resolve_attachment_rejects_escape_path() -> Result<()> {
        let temp_root = temp_test_dir("foundry-attachment-escape");
        let project_dir = temp_root.join("project");
        fs::create_dir_all(&project_dir)?;
        fs::write(temp_root.join("outside.md"), "secret\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "../outside.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&temp_root)?;
        assert!(resolved.error.is_some());
        assert!(resolved.content.contains("cannot contain '..' components"));
        Ok(())
    }

    #[cfg(unix)]
    #[test]
    fn resolve_attachment_rejects_symlink_escape() -> Result<()> {
        let temp_root = temp_test_dir("foundry-attachment-symlink");
        let project_dir = temp_root.join("project");
        fs::create_dir_all(&project_dir)?;
        let outside_path = temp_root.join("outside.md");
        fs::write(&outside_path, "secret\n")?;
        symlink(&outside_path, project_dir.join("leak.md"))?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "leak.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&temp_root)?;
        assert!(resolved.error.is_some());
        assert!(resolved.content.contains("escapes the project root"));
        Ok(())
    }

    #[test]
    fn resolve_attachment_directory_tree_marks_snapshot_excluded_paths() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-tree");
        fs::create_dir_all(project_dir.join(".foundry/studio/logs"))?;
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        fs::write(project_dir.join(".foundry/studio/logs/run.log"), "log\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: ".".into(),
                mode: AttachmentMode::DirectoryTree,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert!(resolved.error.is_none());
        assert!(resolved.content.contains("studio [snapshot-excluded]"));
        assert!(resolved.content.contains("src/"));
        Ok(())
    }

    #[test]
    fn resolve_attachment_external_directory_tree_keeps_full_listing() -> Result<()> {
        let temp_root = temp_test_dir("foundry-attachment-external-tree");
        let project_dir = temp_root.join("project");
        let external_dir = temp_root.join("external");
        fs::create_dir_all(&project_dir)?;
        fs::create_dir_all(external_dir.join(".foundry/studio/logs"))?;
        fs::write(external_dir.join(".foundry/studio/logs/run.log"), "log\n")?;
        fs::write(external_dir.join("notes.md"), "# Notes\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: normalize_absolute_display_path(&external_dir),
                mode: AttachmentMode::DirectoryTree,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&temp_root)?;
        assert!(resolved.error.is_none());
        assert!(resolved.content.contains(".foundry/"));
        assert!(resolved.content.contains("studio/"));
        assert!(!resolved.content.contains("[snapshot-excluded]"));
        Ok(())
    }

    #[test]
    fn resolve_attachment_inline_file_truncates_large_files() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-large-inline");
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::write(
            project_dir.join("docs/big.txt"),
            "a".repeat(MAX_INLINE_FILE_BYTES + 1024),
        )?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "docs/big.txt".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert!(resolved.error.is_none());
        assert!(resolved.truncated);
        assert!(resolved.content.contains("file exceeds"));
        Ok(())
    }

    #[test]
    fn resolve_all_attachments_truncates_when_total_budget_is_exceeded() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-budget");
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::write(project_dir.join("docs/one.txt"), "a".repeat(60_000))?;
        fs::write(project_dir.join("docs/two.txt"), "b".repeat(60_000))?;

        let resolved = resolve_all_attachments(
            &[
                AttachmentSpec {
                    path: "docs/one.txt".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
                AttachmentSpec {
                    path: "docs/two.txt".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
            ],
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(resolved.len(), 2);
        assert!(!resolved[0].truncated);
        assert!(resolved[1].truncated);
        assert!(resolved[1]
            .content
            .contains("total attachment size budget reached"));
        Ok(())
    }

    #[test]
    fn format_attachments_block_is_empty_for_no_attachments() {
        assert!(format_attachments_block(&[]).is_empty());
    }

    #[test]
    fn format_attachments_block_warns_on_external_attachments() {
        let attachment = ResolvedAttachment {
            spec: AttachmentSpec {
                path: "/tmp/external.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            label: "/tmp/external.md".into(),
            content: "secret".into(),
            truncated: false,
            error: None,
        };

        let block = format_attachments_block(&[attachment]);

        assert!(block.contains("external attachment(s) are outside the project root"));
        assert!(block.contains("BEGIN ATTACHMENT: /tmp/external.md"));
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn queue_selected_execution_contract_attachment_action_queues_picker_on_macos() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-manager-add");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.focused_pane = FocusedPane::Contracts;
        open_attachment_manager(&mut state);

        let selected_contract_path = state.selected_execution_contract().path.clone();
        queue_selected_execution_contract_attachment_action(&mut state)?;

        match state
            .pending_action
            .as_ref()
            .expect("pending picker action")
        {
            PendingStudioAction::PickExecutionContractAttachment { contract_path } => {
                assert_eq!(contract_path, &selected_contract_path);
            }
            PendingStudioAction::EditExecutionContract { .. } => {
                panic!("expected native picker action");
            }
        }
        assert!(state.attachment_manager.is_some());

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[cfg(not(target_os = "macos"))]
    #[test]
    fn queue_selected_execution_contract_attachment_action_opens_editor_on_non_macos() -> Result<()>
    {
        let project_dir = temp_test_dir("foundry-attachment-manager-add");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.focused_pane = FocusedPane::Contracts;
        open_attachment_manager(&mut state);

        let sidecar_path = attachment_sidecar_path(&state.selected_execution_contract().path);
        queue_selected_execution_contract_attachment_action(&mut state)?;

        let guide = state
            .editor_guide
            .as_ref()
            .expect("editor guide should be open");
        match &guide.action {
            PendingStudioAction::EditExecutionContract { path, action_label } => {
                assert_eq!(path, &sidecar_path);
                assert_eq!(*action_label, "contract attachments");
            }
            PendingStudioAction::PickExecutionContractAttachment { .. } => {
                panic!("expected editor fallback action");
            }
        }
        assert!(state.attachment_manager.is_some());

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn remove_selected_execution_contract_attachments_removes_only_marked_items() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-manager-delete");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;
        persist_attachment_specs(
            &contract_path,
            &[
                AttachmentSpec {
                    path: "Cargo.toml".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
                AttachmentSpec {
                    path: "src".into(),
                    mode: AttachmentMode::DirectoryTree,
                    label: None,
                },
            ],
        )?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        open_attachment_manager(&mut state);
        toggle_selected_attachment_mark(&mut state);
        cycle_attachment_manager_selection(&mut state, true);
        remove_selected_execution_contract_attachments(&mut state)?;

        let remaining = load_attachment_specs(&contract_path);
        fs::remove_dir_all(&project_dir)?;
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].path, "src");
        assert!(state.attachment_manager.is_some());
        assert!(state
            .logs
            .last()
            .is_some_and(|(_, line)| { line.contains("removed 1 attachment(s): Cargo.toml") }));
        Ok(())
    }

    #[test]
    fn remove_selected_execution_contract_attachments_removes_selected_and_clamps_selection(
    ) -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-manager-delete-selected");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;
        persist_attachment_specs(
            &contract_path,
            &[
                AttachmentSpec {
                    path: "Cargo.toml".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
                AttachmentSpec {
                    path: "src".into(),
                    mode: AttachmentMode::DirectoryTree,
                    label: None,
                },
            ],
        )?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        open_attachment_manager(&mut state);
        cycle_attachment_manager_selection(&mut state, true);
        remove_selected_execution_contract_attachments(&mut state)?;

        let remaining = load_attachment_specs(&contract_path);
        let selected_attachment = state
            .attachment_manager
            .as_ref()
            .map(|manager| manager.selected_attachment)
            .unwrap_or(usize::MAX);
        fs::remove_dir_all(&project_dir)?;
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].path, "Cargo.toml");
        assert_eq!(selected_attachment, 0);
        Ok(())
    }
}

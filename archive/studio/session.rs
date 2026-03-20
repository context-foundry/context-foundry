use anyhow::{Context, Result};
use chrono::Utc;
use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
    sync::{atomic::AtomicBool, Arc},
    time::SystemTime,
};
use tokio::sync::mpsc;

use crate::agent::{self, AgentOutputEvent, AgentResult, ModelProvider, ProviderRunOptions};
use crate::utils::atomic_write_file_best_effort;

use super::{
    attachments::{external_attachment_count, resolve_all_attachments},
    model::{
        SessionLaunch, SessionState, SessionStatus, StudioEvent, WorkspaceMode, STUDIO_ROOT_DIR,
    },
    prompt::{compose_smoothed_prompt, follow_up_context, follow_up_workspace_issue},
    providers::display_model_name,
    shared::should_skip_snapshot_path,
    state::{SessionControl, StudioState},
};

const STUDIO_PROVIDER_TIMEOUT_SECS: u64 = 900;
const CODEX_MAX_ATTEMPTS: usize = 2;

fn max_provider_attempts(provider: ModelProvider) -> usize {
    if provider == ModelProvider::Codex {
        CODEX_MAX_ATTEMPTS
    } else {
        1
    }
}

fn should_retry_provider_attempt(
    provider: ModelProvider,
    outcome: &AgentResult,
    attempt: usize,
    max_attempts: usize,
) -> bool {
    provider == ModelProvider::Codex && attempt < max_attempts && outcome.should_retry()
}

pub(super) fn start_sessions(
    state: &mut StudioState,
    tx: mpsc::UnboundedSender<StudioEvent>,
    follow_up: bool,
) {
    if state.has_running_sessions() {
        state.log("wait for the current run to finish before starting another");
        return;
    }

    if state.prompt.trim().is_empty() {
        state.log("enter a prompt before starting a run");
        return;
    }

    let follow_up_seed = if follow_up {
        if let Some(session) = state.selected_session() {
            let provider = session.provider;
            let workspace_dir = session.workspace_dir.clone();
            let prior_context = follow_up_context(session);
            if let Some(issue) = follow_up_workspace_issue(&workspace_dir) {
                state.log(issue);
                return;
            }
            state.log(format!(
                "follow-up continues {} in {}",
                provider,
                workspace_dir.display()
            ));
            Some((provider, workspace_dir, prior_context))
        } else {
            state.log("select a session before sending a follow-up");
            return;
        }
    } else {
        None
    };

    let requested = if let Some((provider, _, _)) = &follow_up_seed {
        vec![*provider]
    } else {
        state.provider_mode.providers().to_vec()
    };
    let blocked: Vec<String> = requested
        .iter()
        .filter_map(|provider| {
            let readiness = state.provider_readiness(*provider);
            if readiness.is_available() {
                None
            } else {
                Some(format!("{}: {}", provider, readiness.detail))
            }
        })
        .collect();

    if !blocked.is_empty() {
        state.log(format!("run blocked: {}", blocked.join(" | ")));
        return;
    }

    if !follow_up && state.workspace_mode == WorkspaceMode::Shared && requested.len() > 1 {
        state.log("shared mode with both providers can cause overlapping edits");
    }

    if let Err(err) = state.record_prompt_history_entry(follow_up) {
        state.log(format!("prompt history persist failed: {}", err));
    }

    let run_id = Utc::now().format("%Y%m%d-%H%M%S").to_string();
    let project_dir = state.project_dir.clone();
    let scan = state.scan.clone();
    let prompt = state.prompt.clone();
    let Some(execution_contract) = state.selected_execution_contract().cloned() else {
        state.log("no execution contract selected");
        return;
    };
    let external_count = external_attachment_count(&execution_contract.attachments);
    if external_count > 0 {
        state.log(format!(
            "warning: {} attachment(s) are outside the project root and will be sent to the model",
            external_count
        ));
    }

    for provider in requested {
        let prior_context = follow_up_seed
            .as_ref()
            .map(|(_, _, context)| context.clone());
        let model = state.model_for(provider).to_string();
        let workspace_dir = if let Some((_, workspace_dir, _)) = &follow_up_seed {
            workspace_dir.clone()
        } else {
            match state.workspace_mode {
                WorkspaceMode::Shared => project_dir.clone(),
                WorkspaceMode::Isolated => project_dir
                    .join(STUDIO_ROOT_DIR)
                    .join("workspaces")
                    .join(provider.slug()),
            }
        };
        let artifact_dir = workspace_dir
            .join(STUDIO_ROOT_DIR)
            .join("artifacts")
            .join(&run_id)
            .join(provider.slug());
        let session_id = format!("{}-{}", run_id, provider.slug());

        state.sessions.push(SessionState {
            id: session_id.clone(),
            provider,
            model: model.clone(),
            workspace_dir: workspace_dir.clone(),
            artifact_dir: artifact_dir.clone(),
            status: SessionStatus::Running,
            started_at: Utc::now(),
            finished_at: None,
            output: vec![format!(
                "{} session {} in {}",
                provider,
                if follow_up { "continuing" } else { "starting" },
                workspace_dir.display()
            )],
            artifacts: Vec::new(),
            error: None,
            event_count: 0,
            last_event_at: None,
            prompt_path: Some(artifact_dir.join("execution-brief.md")),
            stop_requested: false,
        });
        state.selected_session = state.sessions.len().saturating_sub(1);
        state.output_scroll = 0;
        state.log(format!(
            "{} {} with model {}",
            if follow_up { "continuing" } else { "starting" },
            provider,
            display_model_name(&model)
        ));

        let control_session_id = session_id.clone();
        let launch = SessionLaunch {
            id: session_id,
            provider,
            model,
            workspace_mode: state.workspace_mode,
            project_dir: project_dir.clone(),
            workspace_dir,
            artifact_dir,
            prompt: prompt.clone(),
            execution_contract: execution_contract.clone(),
            scan: scan.clone(),
            prior_context,
            prepare_workspace: !follow_up,
        };
        let cancel_flag = Arc::new(AtomicBool::new(false));
        let task = tokio::spawn(run_session(launch, tx.clone(), cancel_flag.clone()));
        state
            .session_controls
            .insert(control_session_id, SessionControl { cancel_flag, task });
    }
}

async fn run_session(
    launch: SessionLaunch,
    tx: mpsc::UnboundedSender<StudioEvent>,
    cancel_flag: Arc<AtomicBool>,
) {
    if let Err(err) = prepare_workspace(&launch) {
        let _ = tx.send(StudioEvent::SessionFinished {
            session_id: launch.id,
            success: false,
            artifacts: Vec::new(),
            error: Some(format!("workspace preparation failed: {}", err)),
        });
        return;
    }

    if let Err(err) = fs::create_dir_all(&launch.artifact_dir) {
        let _ = tx.send(StudioEvent::SessionFinished {
            session_id: launch.id,
            success: false,
            artifacts: Vec::new(),
            error: Some(format!("artifact directory setup failed: {}", err)),
        });
        return;
    }

    let attachments =
        resolve_all_attachments(&launch.execution_contract.attachments, &launch.project_dir);
    let smoothed_prompt = compose_smoothed_prompt(
        &launch.provider.to_string(),
        &launch.prompt,
        &launch.execution_contract,
        &attachments,
        &launch.scan,
        &launch.workspace_dir.display().to_string(),
        &launch.artifact_dir.display().to_string(),
        launch.prior_context.as_deref(),
    );
    let prompt_path = launch.artifact_dir.join("execution-brief.md");
    atomic_write_file_best_effort(&prompt_path, smoothed_prompt.as_bytes());
    let _ = tx.send(StudioEvent::SessionOutput {
        session_id: launch.id.clone(),
        event: AgentOutputEvent::Text(format!(
            "[studio] execution brief saved to {}",
            prompt_path.display()
        )),
    });
    let log_dir = launch.project_dir.join(STUDIO_ROOT_DIR).join("logs");
    let _ = fs::create_dir_all(&log_dir);
    let started_at = SystemTime::now();

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let forward_tx = tx.clone();
    let session_id = launch.id.clone();
    tokio::spawn(async move {
        while let Some(event) = agent_rx.recv().await {
            let _ = forward_tx.send(StudioEvent::SessionOutput {
                session_id: session_id.clone(),
                event,
            });
        }
    });

    let max_attempts = max_provider_attempts(launch.provider);
    let mut attempt = 1;
    let result = loop {
        let result = agent::run_provider_session(ProviderRunOptions {
            provider: launch.provider,
            model: &launch.model,
            prompt: &smoothed_prompt,
            project_dir: &launch.workspace_dir,
            output_tx: agent_tx.clone(),
            log_dir: &log_dir,
            timeout_secs: STUDIO_PROVIDER_TIMEOUT_SECS,
            skip_git_repo_check: launch.workspace_mode == WorkspaceMode::Isolated,
            cancel_flag: Some(cancel_flag.clone()),
        })
        .await;

        match result {
            Ok(outcome)
                if should_retry_provider_attempt(
                    launch.provider,
                    &outcome,
                    attempt,
                    max_attempts,
                ) =>
            {
                attempt += 1;
                let _ = tx.send(StudioEvent::SessionOutput {
                    session_id: launch.id.clone(),
                    event: AgentOutputEvent::Text(format!(
                        "[studio] {} transport stalled; retrying attempt {}/{}",
                        launch.provider, attempt, max_attempts
                    )),
                });
            }
            other => break other,
        }
    };

    let artifacts = discover_artifacts(&launch.workspace_dir, &launch.artifact_dir, started_at);
    let (success, error) = match result {
        Ok(outcome) => (outcome.success, outcome.failure_message),
        Err(err) => (false, Some(err.to_string())),
    };

    let _ = tx.send(StudioEvent::SessionFinished {
        session_id: launch.id,
        success,
        artifacts,
        error,
    });
}

fn prepare_workspace(launch: &SessionLaunch) -> Result<()> {
    if !launch.prepare_workspace {
        fs::create_dir_all(&launch.workspace_dir)?;
        return Ok(());
    }

    if launch.workspace_mode == WorkspaceMode::Shared {
        return Ok(());
    }

    // Try git worktree first for git repos
    if is_git_repo(&launch.project_dir) {
        return create_worktree(&launch.project_dir, &launch.workspace_dir, &launch.id);
    }

    // Fallback: copy snapshot for non-git projects
    if launch.workspace_dir.exists() {
        fs::remove_dir_all(&launch.workspace_dir).with_context(|| {
            format!(
                "failed to remove existing workspace {}",
                launch.workspace_dir.display()
            )
        })?;
    }

    if let Some(parent) = launch.workspace_dir.parent() {
        fs::create_dir_all(parent)?;
    }

    copy_workspace_snapshot(&launch.project_dir, &launch.workspace_dir)
}

fn is_git_repo(dir: &Path) -> bool {
    std::process::Command::new("git")
        .args(["rev-parse", "--is-inside-work-tree"])
        .current_dir(dir)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn create_worktree(project_dir: &Path, workspace_dir: &Path, session_id: &str) -> Result<()> {
    // 1. Snapshot dirty state (tracked + untracked) without disturbing the user's index.
    //    Save the index file, stage everything, create a stash ref, then restore.
    let git_dir_output = std::process::Command::new("git")
        .args(["rev-parse", "--git-dir"])
        .current_dir(project_dir)
        .output()
        .context("failed to locate git dir")?;
    let git_dir_raw = String::from_utf8_lossy(&git_dir_output.stdout)
        .trim()
        .to_string();
    let git_dir = if Path::new(&git_dir_raw).is_absolute() {
        PathBuf::from(&git_dir_raw)
    } else {
        project_dir.join(&git_dir_raw)
    };
    let index_path = git_dir.join("index");
    let index_backup = index_backup_path(&git_dir, session_id);

    // Save current index
    let had_index = index_path.exists();
    if had_index {
        fs::copy(&index_path, &index_backup).context("failed to back up git index")?;
    }

    // Stage all files (including untracked) and snapshot
    let _ = std::process::Command::new("git")
        .args(["add", "-A"])
        .current_dir(project_dir)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();
    let stash_output = std::process::Command::new("git")
        .args(["stash", "create"])
        .current_dir(project_dir)
        .output()
        .context("failed to run git stash create")?;

    // Restore original index state
    if had_index {
        fs::rename(&index_backup, &index_path).with_context(|| {
            format!(
                "failed to restore git index from backup {}",
                index_backup.display()
            )
        })?;
    } else if index_path.exists() {
        fs::remove_file(&index_path).with_context(|| {
            format!(
                "failed to remove temporary git index {}",
                index_path.display()
            )
        })?;
    }
    if index_backup.exists() {
        let _ = fs::remove_file(&index_backup);
    }

    let stash_ref = String::from_utf8_lossy(&stash_output.stdout)
        .trim()
        .to_string();
    let checkout_ref = if stash_ref.is_empty() {
        "HEAD".to_string()
    } else {
        stash_ref
    };

    // 2. Clean up existing worktree at this path
    let _ = std::process::Command::new("git")
        .args([
            "worktree",
            "remove",
            "--force",
            &workspace_dir.display().to_string(),
        ])
        .current_dir(project_dir)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();

    if workspace_dir.exists() {
        let _ = fs::remove_dir_all(workspace_dir);
    }

    let _ = std::process::Command::new("git")
        .args(["worktree", "prune"])
        .current_dir(project_dir)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();

    // 3. Ensure parent dir exists
    if let Some(parent) = workspace_dir.parent() {
        fs::create_dir_all(parent)?;
    }

    // 4. Create the worktree
    let result = std::process::Command::new("git")
        .args([
            "worktree",
            "add",
            "--detach",
            &workspace_dir.display().to_string(),
            &checkout_ref,
        ])
        .current_dir(project_dir)
        .output()
        .context("failed to run git worktree add")?;

    if !result.status.success() {
        let stderr = String::from_utf8_lossy(&result.stderr);
        anyhow::bail!("git worktree add failed: {}", stderr.trim());
    }

    Ok(())
}

fn index_backup_path(git_dir: &Path, session_id: &str) -> PathBuf {
    let sanitized: String = session_id
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || ch == '-' || ch == '_' {
                ch
            } else {
                '_'
            }
        })
        .collect();
    let suffix = if sanitized.is_empty() {
        "session".to_string()
    } else {
        sanitized
    };
    git_dir.join(format!("index.foundry-backup-{}", suffix))
}

#[allow(dead_code)]
fn remove_worktree(project_dir: &Path, workspace_dir: &Path) {
    let _ = std::process::Command::new("git")
        .args([
            "worktree",
            "remove",
            "--force",
            &workspace_dir.display().to_string(),
        ])
        .current_dir(project_dir)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();

    if workspace_dir.exists() {
        let _ = fs::remove_dir_all(workspace_dir);
    }

    let _ = std::process::Command::new("git")
        .args(["worktree", "prune"])
        .current_dir(project_dir)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();
}

fn copy_workspace_snapshot(src_root: &Path, dst_root: &Path) -> Result<()> {
    fs::create_dir_all(dst_root)?;
    copy_workspace_snapshot_inner(src_root, dst_root, Path::new(""))
}

fn copy_workspace_snapshot_inner(src_root: &Path, dst_root: &Path, rel: &Path) -> Result<()> {
    let current_src = if rel.as_os_str().is_empty() {
        src_root.to_path_buf()
    } else {
        src_root.join(rel)
    };

    let mut entries: Vec<_> = fs::read_dir(&current_src)?
        .filter_map(|entry| entry.ok())
        .collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        let name = entry.file_name();
        let next_rel = if rel.as_os_str().is_empty() {
            PathBuf::from(&name)
        } else {
            rel.join(&name)
        };

        if should_skip_snapshot_path(&next_rel) {
            continue;
        }

        let src_path = src_root.join(&next_rel);
        let dst_path = dst_root.join(&next_rel);
        let file_type = entry.file_type()?;

        if file_type.is_dir() {
            fs::create_dir_all(&dst_path)?;
            copy_workspace_snapshot_inner(src_root, dst_root, &next_rel)?;
        } else if file_type.is_file() {
            if let Some(parent) = dst_path.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::copy(&src_path, &dst_path).with_context(|| {
                format!(
                    "failed to copy {} to {}",
                    src_path.display(),
                    dst_path.display()
                )
            })?;
        }
    }

    Ok(())
}

fn discover_artifacts(
    workspace_dir: &Path,
    artifact_dir: &Path,
    started_at: SystemTime,
) -> Vec<PathBuf> {
    let mut paths = BTreeSet::new();
    collect_recent_artifacts(artifact_dir, artifact_dir, started_at, &mut paths, 12);
    if paths.is_empty() {
        collect_recent_artifacts(workspace_dir, workspace_dir, started_at, &mut paths, 12);
    }
    paths.into_iter().collect()
}

fn collect_recent_artifacts(
    root: &Path,
    current: &Path,
    started_at: SystemTime,
    paths: &mut BTreeSet<PathBuf>,
    limit: usize,
) {
    if paths.len() >= limit {
        return;
    }

    let Ok(entries) = fs::read_dir(current) else {
        return;
    };

    let mut entries: Vec<_> = entries.filter_map(|entry| entry.ok()).collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        if paths.len() >= limit {
            return;
        }
        let path = entry.path();
        let rel = path.strip_prefix(root).unwrap_or(&path);
        if should_skip_snapshot_path(rel) {
            continue;
        }

        let Ok(file_type) = entry.file_type() else {
            continue;
        };

        if file_type.is_dir() {
            collect_recent_artifacts(root, &path, started_at, paths, limit);
            continue;
        }

        let Some(ext) = path.extension().and_then(|ext| ext.to_str()) else {
            continue;
        };
        if !matches!(ext, "html" | "htm" | "md" | "json") {
            continue;
        }

        let Ok(metadata) = entry.metadata() else {
            continue;
        };
        let modified = metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH);
        if modified < started_at {
            continue;
        }
        paths.insert(path);
    }
}

#[cfg(test)]
mod tests {
    use anyhow::Result;
    use std::{
        fs,
        path::{Path, PathBuf},
        sync::{atomic::AtomicBool, Arc},
        time::{Duration, SystemTime},
    };
    use tokio::sync::mpsc;

    use crate::agent::{AgentExitKind, AgentResult, ModelProvider};

    use super::super::{
        model::{ProviderMode, SessionLaunch, StudioEvent, WorkspaceMode, STUDIO_ROOT_DIR},
        test_helpers::{temp_test_dir, test_contract, test_scan, test_state},
    };
    use super::{
        discover_artifacts, index_backup_path, prepare_workspace, remove_worktree, run_session,
        should_retry_provider_attempt, start_sessions, CODEX_MAX_ATTEMPTS,
    };

    fn test_launch(
        project_dir: &Path,
        workspace_dir: &Path,
        workspace_mode: WorkspaceMode,
        prepare_workspace_flag: bool,
    ) -> SessionLaunch {
        SessionLaunch {
            id: "session-1".into(),
            provider: ModelProvider::Claude,
            model: "opus".into(),
            workspace_mode,
            project_dir: project_dir.to_path_buf(),
            workspace_dir: workspace_dir.to_path_buf(),
            artifact_dir: workspace_dir
                .join(STUDIO_ROOT_DIR)
                .join("artifacts")
                .join("run")
                .join("claude"),
            prompt: "test prompt".into(),
            execution_contract: test_contract(),
            scan: test_scan(),
            prior_context: None,
            prepare_workspace: prepare_workspace_flag,
        }
    }

    #[test]
    fn start_sessions_blocks_when_any_requested_provider_is_unavailable() {
        let mut state = test_state();
        state.provider_mode = ProviderMode::Both;
        state.prompt = "ship it".into();
        let (tx, _rx) = mpsc::unbounded_channel();

        start_sessions(&mut state, tx, false);

        assert!(state.sessions.is_empty());
        assert!(state
            .logs
            .iter()
            .any(|(_, message)| message.contains("run blocked:")));
    }

    #[test]
    fn prepare_workspace_copies_project_snapshot_for_isolated_runs() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-prepare-copy");
        let workspace_dir = project_dir.join(STUDIO_ROOT_DIR).join("workspaces/claude");
        fs::create_dir_all(project_dir.join("src"))?;
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR).join("logs"))?;
        fs::create_dir_all(&workspace_dir)?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        fs::write(
            project_dir.join(STUDIO_ROOT_DIR).join("logs/session.md"),
            "log\n",
        )?;
        fs::write(workspace_dir.join("stale.txt"), "stale\n")?;

        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, true);
        prepare_workspace(&launch)?;

        assert!(workspace_dir.join("src/main.rs").exists());
        assert!(!workspace_dir.join("stale.txt").exists());
        assert!(!workspace_dir
            .join(STUDIO_ROOT_DIR)
            .join("logs/session.md")
            .exists());

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn prepare_workspace_follow_up_only_creates_workspace_directory() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-follow-up-workspace");
        let workspace_dir = project_dir.join(STUDIO_ROOT_DIR).join("workspaces/claude");
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;

        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, false);
        prepare_workspace(&launch)?;

        assert!(workspace_dir.exists());
        assert!(!workspace_dir.join("src/main.rs").exists());

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    fn git_init(dir: &Path) {
        std::process::Command::new("git")
            .args(["init"])
            .current_dir(dir)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .expect("git init");
        std::process::Command::new("git")
            .args(["add", "-A"])
            .current_dir(dir)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .expect("git add");
        std::process::Command::new("git")
            .args([
                "-c",
                "user.email=test@test.com",
                "-c",
                "user.name=Test",
                "commit",
                "--allow-empty",
                "-m",
                "init",
            ])
            .current_dir(dir)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .expect("git commit");
    }

    #[test]
    fn prepare_workspace_creates_worktree_for_git_repos() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-worktree");
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        git_init(&project_dir);

        let workspace_dir = project_dir.join(STUDIO_ROOT_DIR).join("workspaces/claude");
        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, true);
        prepare_workspace(&launch)?;

        // Worktree marker: .git is a file (not a directory) pointing to the main repo
        assert!(workspace_dir.join(".git").exists());
        assert!(workspace_dir.join(".git").is_file());
        // Source files should be present
        assert!(workspace_dir.join("src/main.rs").exists());

        remove_worktree(&project_dir, &workspace_dir);
        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn prepare_workspace_worktree_captures_dirty_state() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-worktree-dirty");
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        git_init(&project_dir);

        // Make an uncommitted change
        fs::write(
            project_dir.join("src/main.rs"),
            "fn main() { println!(\"dirty\"); }\n",
        )?;

        let workspace_dir = project_dir.join(STUDIO_ROOT_DIR).join("workspaces/claude");
        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, true);
        prepare_workspace(&launch)?;

        let content = fs::read_to_string(workspace_dir.join("src/main.rs"))?;
        assert!(
            content.contains("dirty"),
            "worktree should contain uncommitted changes: {}",
            content
        );

        remove_worktree(&project_dir, &workspace_dir);
        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn prepare_workspace_worktree_preserves_staged_state() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-worktree-staged");
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        git_init(&project_dir);

        // Stage a change
        fs::write(
            project_dir.join("src/main.rs"),
            "fn main() { /* staged */ }\n",
        )?;
        std::process::Command::new("git")
            .args(["add", "src/main.rs"])
            .current_dir(&project_dir)
            .status()
            .expect("git add");

        // Verify something is staged
        let before = std::process::Command::new("git")
            .args(["diff", "--cached", "--name-only"])
            .current_dir(&project_dir)
            .output()
            .expect("git diff --cached");
        let staged_before = String::from_utf8_lossy(&before.stdout).trim().to_string();
        assert!(
            staged_before.contains("main.rs"),
            "file should be staged before worktree creation"
        );

        let workspace_dir = project_dir.join(STUDIO_ROOT_DIR).join("workspaces/claude");
        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, true);
        prepare_workspace(&launch)?;

        // Verify the staged state is still intact
        let after = std::process::Command::new("git")
            .args(["diff", "--cached", "--name-only"])
            .current_dir(&project_dir)
            .output()
            .expect("git diff --cached");
        let staged_after = String::from_utf8_lossy(&after.stdout).trim().to_string();
        assert_eq!(
            staged_before, staged_after,
            "staged files should be preserved after worktree creation"
        );

        remove_worktree(&project_dir, &workspace_dir);
        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn prepare_workspace_worktree_captures_untracked_files() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-worktree-untracked");
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        git_init(&project_dir);

        // Add an untracked file after the initial commit
        fs::write(project_dir.join("src/new_module.rs"), "pub fn hello() {}\n")?;

        let workspace_dir = project_dir.join(STUDIO_ROOT_DIR).join("workspaces/claude");
        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, true);
        prepare_workspace(&launch)?;

        assert!(
            workspace_dir.join("src/new_module.rs").exists(),
            "worktree should contain untracked files"
        );
        let content = fs::read_to_string(workspace_dir.join("src/new_module.rs"))?;
        assert!(
            content.contains("hello"),
            "untracked file should have expected content: {}",
            content
        );

        remove_worktree(&project_dir, &workspace_dir);
        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn prepare_workspace_replaces_existing_worktree() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-worktree-replace");
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        git_init(&project_dir);

        let workspace_dir = project_dir.join(STUDIO_ROOT_DIR).join("workspaces/claude");

        // Create worktree twice -- second run should replace the first
        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, true);
        prepare_workspace(&launch)?;
        assert!(workspace_dir.join("src/main.rs").exists());

        let launch = test_launch(&project_dir, &workspace_dir, WorkspaceMode::Isolated, true);
        prepare_workspace(&launch)?;
        assert!(workspace_dir.join("src/main.rs").exists());
        assert!(workspace_dir.join(".git").is_file());

        remove_worktree(&project_dir, &workspace_dir);
        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn index_backup_path_is_unique_per_session() {
        let git_dir = Path::new("/tmp/foundry-git-dir");
        let first = index_backup_path(git_dir, "session-1");
        let second = index_backup_path(git_dir, "session-2");
        let sanitized = index_backup_path(git_dir, "session/with spaces");

        assert_ne!(first, second);
        assert!(sanitized.ends_with("index.foundry-backup-session_with_spaces"));
    }

    #[test]
    fn discover_artifacts_prefers_artifact_dir_before_workspace_fallback() -> Result<()> {
        let root = temp_test_dir("foundry-session-artifacts-prefer");
        let artifact_dir = root.join("artifacts");
        let workspace_dir = root.join("workspace");
        fs::create_dir_all(&artifact_dir)?;
        fs::create_dir_all(&workspace_dir)?;

        let started_at = SystemTime::now() - Duration::from_secs(2);
        let artifact_path = artifact_dir.join("report.md");
        let workspace_path = workspace_dir.join("fallback.html");
        fs::write(&artifact_path, "# report\n")?;
        fs::write(&workspace_path, "<html></html>\n")?;

        let artifacts = discover_artifacts(&workspace_dir, &artifact_dir, started_at);

        assert_eq!(artifacts, vec![artifact_path]);
        fs::remove_dir_all(&root)?;
        Ok(())
    }

    #[test]
    fn discover_artifacts_falls_back_to_workspace_when_artifact_dir_is_empty() -> Result<()> {
        let root = temp_test_dir("foundry-session-artifacts-fallback");
        let artifact_dir = root.join("artifacts");
        let workspace_dir = root.join("workspace");
        fs::create_dir_all(&artifact_dir)?;
        fs::create_dir_all(&workspace_dir)?;

        let started_at = SystemTime::now() - Duration::from_secs(2);
        let workspace_path = workspace_dir.join("report.html");
        fs::write(&workspace_path, "<html></html>\n")?;

        let artifacts = discover_artifacts(&workspace_dir, &artifact_dir, started_at);

        assert_eq!(artifacts, vec![workspace_path]);
        fs::remove_dir_all(&root)?;
        Ok(())
    }

    #[test]
    fn codex_transport_stalls_are_retryable_once() {
        let outcome = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::TransportStall,
            failure_message: Some("Codex stalled after websocket reconnects".into()),
        };

        assert!(should_retry_provider_attempt(
            ModelProvider::Codex,
            &outcome,
            1,
            CODEX_MAX_ATTEMPTS
        ));
        assert!(!should_retry_provider_attempt(
            ModelProvider::Codex,
            &outcome,
            CODEX_MAX_ATTEMPTS,
            CODEX_MAX_ATTEMPTS
        ));
        assert!(!should_retry_provider_attempt(
            ModelProvider::Claude,
            &outcome,
            1,
            CODEX_MAX_ATTEMPTS
        ));
    }

    #[test]
    fn non_transport_failures_are_not_retried() {
        let outcome = AgentResult {
            success: false,
            exit_code: 1,
            exit_kind: AgentExitKind::Failed,
            failure_message: Some("tool failed".into()),
        };

        assert!(!should_retry_provider_attempt(
            ModelProvider::Codex,
            &outcome,
            1,
            CODEX_MAX_ATTEMPTS
        ));
    }

    #[tokio::test]
    async fn run_session_sends_workspace_error_when_prepare_workspace_fails() {
        let project_dir = PathBuf::from("/nonexistent/foundry-session-test/project");
        let workspace_dir = PathBuf::from("/tmp/foundry-session-ws-fail");
        let launch = SessionLaunch {
            id: "session-fail-ws".into(),
            provider: ModelProvider::Claude,
            model: "opus".into(),
            workspace_mode: WorkspaceMode::Isolated,
            project_dir,
            workspace_dir,
            artifact_dir: PathBuf::from("/tmp/foundry-session-ws-fail/artifacts"),
            prompt: "test".into(),
            execution_contract: test_contract(),
            scan: test_scan(),
            prior_context: None,
            prepare_workspace: true,
        };

        let (tx, mut rx) = mpsc::unbounded_channel();
        let cancel_flag = Arc::new(AtomicBool::new(false));
        run_session(launch, tx, cancel_flag).await;

        match rx.recv().await.expect("should receive event") {
            StudioEvent::SessionFinished {
                session_id,
                success,
                error,
                ..
            } => {
                assert_eq!(session_id, "session-fail-ws");
                assert!(!success);
                let msg = error.expect("should have error message");
                assert!(
                    msg.contains("workspace preparation failed"),
                    "unexpected error: {}",
                    msg
                );
            }
            _ => panic!("expected SessionFinished"),
        }
    }

    #[tokio::test]
    async fn run_session_sends_artifact_error_when_artifact_dir_creation_fails() -> Result<()> {
        let project_dir = temp_test_dir("foundry-session-artfail");
        fs::create_dir_all(&project_dir)?;
        // Place a regular file where artifact_dir needs a directory ancestor
        let blocker = project_dir.join("blocker");
        fs::write(&blocker, "not a directory")?;

        let launch = SessionLaunch {
            id: "session-fail-art".into(),
            provider: ModelProvider::Claude,
            model: "opus".into(),
            workspace_mode: WorkspaceMode::Shared,
            project_dir: project_dir.clone(),
            workspace_dir: project_dir.clone(),
            artifact_dir: blocker.join("cannot").join("create"),
            prompt: "test".into(),
            execution_contract: test_contract(),
            scan: test_scan(),
            prior_context: None,
            prepare_workspace: true,
        };

        let (tx, mut rx) = mpsc::unbounded_channel();
        let cancel_flag = Arc::new(AtomicBool::new(false));
        run_session(launch, tx, cancel_flag).await;

        match rx.recv().await.expect("should receive event") {
            StudioEvent::SessionFinished {
                session_id,
                success,
                error,
                ..
            } => {
                assert_eq!(session_id, "session-fail-art");
                assert!(!success);
                let msg = error.expect("should have error message");
                assert!(
                    msg.contains("artifact directory setup failed"),
                    "unexpected error: {}",
                    msg
                );
            }
            _ => panic!("expected SessionFinished"),
        }

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }
}

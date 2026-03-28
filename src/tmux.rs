use anyhow::{Context, Result};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Instant;
use uuid::Uuid;

use crate::prompts::AUTONOMY_OVERRIDE;

pub struct TmuxSession {
    pub name: String,
    pub log_file: PathBuf,
    pub project_dir: PathBuf,
    pub created_at: Instant,
}

impl TmuxSession {
    pub fn create(
        prefix: &str,
        role_slug: &str,
        project_dir: &Path,
        log_dir: &Path,
    ) -> Result<Self> {
        let name = format!(
            "{}-{}-{}",
            prefix,
            role_slug,
            Uuid::new_v4().as_simple()
        );
        let log_file = log_dir.join(format!("{}.pipe", name));

        assert!(
            log_dir.is_absolute(),
            "log_dir must be absolute for pipe-pane"
        );

        std::fs::create_dir_all(log_dir).context("creating log dir for tmux pipe")?;
        std::fs::File::create(&log_file).context("creating pipe log file")?;

        let status = Command::new("tmux")
            .args([
                "new-session",
                "-d",
                "-s",
                &name,
                "-x",
                "4096",
                "-y",
                "24",
                "-c",
            ])
            .arg(project_dir)
            .status()
            .context("tmux new-session failed")?;

        if !status.success() {
            anyhow::bail!("tmux new-session exited with non-zero status");
        }

        let pipe_status = Command::new("tmux")
            .args(["pipe-pane", "-t", &name])
            .arg(format!("cat >> {}", log_file.display()))
            .status()
            .context("tmux pipe-pane failed")?;

        if !pipe_status.success() {
            let _ = Command::new("tmux")
                .args(["kill-session", "-t", &name])
                .status();
            anyhow::bail!("tmux pipe-pane failed");
        }

        std::thread::sleep(std::time::Duration::from_millis(50));

        Ok(TmuxSession {
            name,
            log_file,
            project_dir: project_dir.to_path_buf(),
            created_at: Instant::now(),
        })
    }

    pub fn send_keys(&self, command: &str) -> Result<()> {
        let status = Command::new("tmux")
            .args(["send-keys", "-t", &self.name, command, "Enter"])
            .status()
            .context("tmux send-keys failed")?;

        if !status.success() {
            anyhow::bail!("tmux send-keys exited with non-zero status");
        }

        Ok(())
    }

    pub fn is_alive(&self) -> bool {
        match Command::new("tmux")
            .args(["has-session", "-t", &self.name])
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
        {
            Ok(status) => status.success(),
            Err(_) => false,
        }
    }

    pub fn kill(&self) -> Result<()> {
        let _ = Command::new("tmux")
            .args(["kill-session", "-t", &self.name])
            .status()
            .context("tmux kill-session failed")?;

        Ok(())
    }

    pub fn build_cli_command(
        provider: &str,
        prompt: &str,
        model: &str,
        allowed_tools: Option<&[&str]>,
    ) -> String {
        let mut parts: Vec<String> = vec![provider.to_string()];

        parts.push("-p".into());
        parts.push(shell_escape_single_quote(prompt));

        if !model.trim().is_empty() {
            parts.push("--model".into());
            parts.push(model.into());
        }

        if crate::agent::is_running_as_root() {
            parts.push("--allowedTools".into());
            parts.push(crate::agent::ROOT_ALLOWED_TOOLS.into());
        } else {
            parts.push("--dangerously-skip-permissions".into());
        }
        parts.push("--output-format".into());
        parts.push("stream-json".into());
        parts.push("--verbose".into());

        parts.push("--append-system-prompt".into());
        parts.push(shell_escape_single_quote(AUTONOMY_OVERRIDE));

        if let Some(tools) = allowed_tools {
            parts.push("--tools".into());
            parts.push(tools.join(","));
        }

        let cmd = parts.join(" ");
        format!("CLAUDECODE= {}", cmd)
    }
}

pub fn tmux_binary_available() -> bool {
    let lookup_cmd = if cfg!(target_os = "windows") {
        "where"
    } else {
        "which"
    };
    Command::new(lookup_cmd)
        .arg("tmux")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

pub fn list_sessions(prefix: &str) -> Vec<String> {
    let output = match Command::new("tmux")
        .args(["list-sessions", "-F", "#{session_name}"])
        .output()
    {
        Ok(o) if o.status.success() => o,
        _ => return Vec::new(),
    };
    let stdout = String::from_utf8_lossy(&output.stdout);
    let needle = format!("{}-", prefix);
    stdout
        .lines()
        .filter(|line| line.starts_with(&needle))
        .map(|s| s.to_string())
        .collect()
}

pub fn cleanup_stale_sessions(prefix: &str) -> Vec<String> {
    let sessions = list_sessions(prefix);
    for name in &sessions {
        let _ = Command::new("tmux")
            .args(["kill-session", "-t", name])
            .status();
    }
    sessions
}

fn shell_escape_single_quote(s: &str) -> String {
    let replaced = s.replace('\'', "'\\''");
    format!("'{}'", replaced)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_session_name_format() {
        let session = TmuxSession {
            name: "foundry-builder-abc123".into(),
            log_file: PathBuf::from("/tmp/foundry-builder-abc123.pipe"),
            project_dir: PathBuf::from("/tmp"),
            created_at: Instant::now(),
        };
        assert!(session.name.starts_with("foundry-builder"));
    }

    #[test]
    fn test_shell_escape_single_quote_basic() {
        assert_eq!(shell_escape_single_quote("hello world"), "'hello world'");
    }

    #[test]
    fn test_shell_escape_single_quote_with_quotes() {
        assert_eq!(shell_escape_single_quote("it's"), "'it'\\''s'");
    }

    #[test]
    fn test_build_cli_command_basic() {
        let result =
            TmuxSession::build_cli_command("claude", "do something", "opus", None);
        assert!(result.contains("claude"));
        assert!(result.contains("-p"));
        assert!(result.contains("'do something'"));
        assert!(result.contains("--model"));
        assert!(result.contains("opus"));
        // When running as root, falls back to --allowedTools; otherwise uses --dangerously-skip-permissions
        assert!(
            result.contains("--dangerously-skip-permissions") || result.contains("--allowedTools"),
            "expected permission flag in: {result}"
        );
        assert!(result.contains("--output-format"));
        assert!(result.contains("stream-json"));
        assert!(result.contains("--verbose"));
        assert!(result.starts_with("CLAUDECODE= "));
    }

    #[test]
    fn test_build_cli_command_with_tools() {
        let result = TmuxSession::build_cli_command(
            "claude",
            "prompt",
            "opus",
            Some(&["Read", "Write"]),
        );
        assert!(result.contains("--tools"));
        assert!(result.contains("Read,Write"));
    }

    #[test]
    fn test_build_cli_command_empty_model() {
        let result = TmuxSession::build_cli_command("claude", "prompt", "", None);
        assert!(!result.contains("--model"));
    }

    #[test]
    #[ignore]
    fn test_tmux_session_lifecycle() {
        let session = TmuxSession::create(
            "test",
            "unit",
            &std::env::current_dir().unwrap(),
            &std::env::temp_dir(),
        )
        .expect("should create session");

        assert!(session.is_alive());

        session
            .send_keys("echo hello")
            .expect("should send keys");

        std::thread::sleep(std::time::Duration::from_millis(200));

        assert!(session.log_file.exists());
        let content = std::fs::read_to_string(&session.log_file).unwrap();
        assert!(!content.is_empty());

        session.kill().expect("should kill session");

        std::thread::sleep(std::time::Duration::from_millis(100));

        assert!(!session.is_alive());
    }

    #[test]
    #[ignore]
    fn test_tmux_pipe_pane_captures_output() {
        let session = TmuxSession::create(
            "test",
            "pipe",
            &std::env::current_dir().unwrap(),
            &std::env::temp_dir(),
        )
        .expect("should create session");

        session
            .send_keys("echo MARKER_STRING")
            .expect("should send keys");

        std::thread::sleep(std::time::Duration::from_millis(500));

        let content = std::fs::read_to_string(&session.log_file).unwrap();
        assert!(
            content.contains("MARKER_STRING"),
            "pipe log should contain MARKER_STRING, got: {}",
            content
        );

        session.kill().expect("should kill session");
    }

    #[test]
    fn test_tmux_binary_available_returns_bool() {
        let _result: bool = tmux_binary_available();
    }

    #[test]
    fn test_list_sessions_returns_vec() {
        let result = list_sessions("nonexistent-prefix-xyz");
        assert!(result.is_empty());
    }

    #[test]
    fn test_cleanup_stale_sessions_noop_when_none() {
        let result = cleanup_stale_sessions("nonexistent-prefix-xyz");
        assert!(result.is_empty());
    }

    #[test]
    #[ignore]
    fn test_list_and_cleanup_sessions() {
        if !tmux_binary_available() {
            eprintln!("tmux not available, skipping");
            return;
        }

        let prefix = format!("foundry-lifecycle-test-{}", std::process::id());
        let session = TmuxSession::create(
            &prefix,
            "unit",
            &std::env::current_dir().unwrap(),
            &std::env::temp_dir(),
        )
        .expect("should create session");

        // list_sessions should find it
        let found = list_sessions(&prefix);
        assert!(
            found.contains(&session.name),
            "list_sessions should contain {}, got: {:?}",
            session.name,
            found
        );

        // cleanup should kill it
        let killed = cleanup_stale_sessions(&prefix);
        assert!(
            killed.contains(&session.name),
            "cleanup should report {}, got: {:?}",
            session.name,
            killed
        );

        std::thread::sleep(std::time::Duration::from_millis(100));

        // Should be gone now
        let remaining = list_sessions(&prefix);
        assert!(
            remaining.is_empty(),
            "sessions should be cleaned up, got: {:?}",
            remaining
        );
    }
}

use anyhow::{Context, Result};
use chrono::Utc;
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
};

use crate::{agent::ModelProvider, utils::{atomic_write_file_best_effort, truncate_str}};

use super::{
    model::{
        AuthCheck, CachedProbeEntry, CapturedCommand, ClaudeAuthStatus, ProbeCache, ProviderMode,
        ProviderReadiness, LIVE_PROBE_TIMEOUT_SECS, LIVE_PROBE_TTL_SECS, STUDIO_ROOT_DIR,
    },
    state::StudioState,
};

pub(super) fn default_provider_mode(
    claude_readiness: &ProviderReadiness,
    codex_readiness: &ProviderReadiness,
) -> ProviderMode {
    match (
        claude_readiness.is_available(),
        codex_readiness.is_available(),
    ) {
        (true, true) => ProviderMode::Both,
        (true, false) => ProviderMode::Claude,
        (false, true) => ProviderMode::Codex,
        (false, false) => ProviderMode::Claude,
    }
}

pub(super) fn probe_claude_readiness(project_dir: &Path, model: &str) -> ProviderReadiness {
    if !command_exists("claude") {
        return ProviderReadiness::missing("claude CLI not found in PATH");
    }

    let output = Command::new(ModelProvider::Claude.binary()).arg("--help").output();
    let output = match output {
        Ok(output) => output,
        Err(err) => {
            return ProviderReadiness::blocked(format!("failed to run `claude --help`: {}", err));
        }
    };

    if !output.status.success() {
        return ProviderReadiness::blocked(format!(
            "`claude --help` exited with status {}",
            output.status
        ));
    }

    let mut help_text = String::new();
    help_text.push_str(&String::from_utf8_lossy(&output.stdout));
    if !output.stderr.is_empty() {
        if !help_text.is_empty() {
            help_text.push('\n');
        }
        help_text.push_str(&String::from_utf8_lossy(&output.stderr));
    }

    let contract = assess_claude_help(&help_text);
    if !contract.is_available() {
        return contract;
    }

    let auth = match check_claude_auth() {
        Ok(auth) => auth,
        Err(err) => {
            return ProviderReadiness::blocked(format!("Claude auth status check failed: {}", err));
        }
    };

    if !auth.authenticated {
        return ProviderReadiness::blocked(auth.detail);
    }

    if let Some(detail) =
        load_cached_live_probe(project_dir, ModelProvider::Claude, model, &auth.detail)
    {
        return ProviderReadiness::ready(detail);
    }

    match run_claude_live_probe(model) {
        Ok(()) => {
            save_cached_live_probe(project_dir, ModelProvider::Claude, model, &auth.detail);
            ProviderReadiness::ready(format!("authenticated; live smoke OK via {}", auth.detail))
        }
        Err(err) => ProviderReadiness::blocked(format!(
            "authenticated but live Claude smoke failed: {}",
            err
        )),
    }
}

pub(super) fn probe_codex_readiness(project_dir: &Path, model: &str) -> ProviderReadiness {
    if !command_exists("codex") {
        return ProviderReadiness::missing("codex CLI not found in PATH");
    }

    let output = Command::new("codex").args(["exec", "--help"]).output();
    let output = match output {
        Ok(output) => output,
        Err(err) => {
            return ProviderReadiness::blocked(format!(
                "failed to run `codex exec --help`: {}",
                err
            ));
        }
    };

    if !output.status.success() {
        return ProviderReadiness::blocked(format!(
            "`codex exec --help` exited with status {}",
            output.status
        ));
    }

    let mut help_text = String::new();
    help_text.push_str(&String::from_utf8_lossy(&output.stdout));
    if !output.stderr.is_empty() {
        if !help_text.is_empty() {
            help_text.push('\n');
        }
        help_text.push_str(&String::from_utf8_lossy(&output.stderr));
    }

    let contract = assess_codex_exec_help(&help_text);
    if !contract.is_available() {
        return contract;
    }

    let auth = match check_codex_auth() {
        Ok(auth) => auth,
        Err(err) => {
            return ProviderReadiness::blocked(format!("Codex login status check failed: {}", err));
        }
    };

    if !auth.authenticated {
        return ProviderReadiness::blocked(auth.detail);
    }

    if let Some(detail) =
        load_cached_live_probe(project_dir, ModelProvider::Codex, model, &auth.detail)
    {
        return ProviderReadiness::ready(detail);
    }

    match run_codex_live_probe(model) {
        Ok(()) => {
            save_cached_live_probe(project_dir, ModelProvider::Codex, model, &auth.detail);
            ProviderReadiness::ready(format!("authenticated; live smoke OK via {}", auth.detail))
        }
        Err(err) => ProviderReadiness::blocked(format!(
            "authenticated but live Codex smoke failed: {}",
            err
        )),
    }
}

fn assess_claude_help(help_text: &str) -> ProviderReadiness {
    let required_tokens = [
        ("usage", "Usage: claude"),
        ("--print", "--print"),
        ("--output-format", "--output-format"),
        ("stream-json", "stream-json"),
        ("--verbose", "--verbose"),
        (
            "--dangerously-skip-permissions",
            "--dangerously-skip-permissions",
        ),
    ];

    let missing: Vec<&str> = required_tokens
        .iter()
        .filter_map(|(label, token)| (!help_text.contains(token)).then_some(*label))
        .collect();

    if missing.is_empty() {
        ProviderReadiness::ready(
            "--print, --output-format=stream-json, --verbose, and --dangerously-skip-permissions supported",
        )
    } else {
        ProviderReadiness::blocked(format!(
            "missing required Claude features: {}",
            missing.join(", ")
        ))
    }
}

fn assess_codex_exec_help(help_text: &str) -> ProviderReadiness {
    let required_tokens = [
        ("exec usage", "Usage: codex exec"),
        ("--json", "--json"),
        ("--full-auto", "--full-auto"),
        ("--output-last-message", "--output-last-message"),
        ("--skip-git-repo-check", "--skip-git-repo-check"),
    ];

    let missing: Vec<&str> = required_tokens
        .iter()
        .filter_map(|(label, token)| (!help_text.contains(token)).then_some(*label))
        .collect();

    if missing.is_empty() {
        ProviderReadiness::ready(
            "exec, --json, --full-auto, --output-last-message, and --skip-git-repo-check supported",
        )
    } else {
        ProviderReadiness::blocked(format!(
            "missing required Codex exec features: {}",
            missing.join(", ")
        ))
    }
}

fn check_claude_auth() -> Result<AuthCheck> {
    let output = Command::new(ModelProvider::Claude.binary())
        .args(["auth", "status", "--json"])
        .output()
        .context("failed to run `claude auth status --json`")?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let status: ClaudeAuthStatus =
        serde_json::from_str(&stdout).context("failed to parse Claude auth status JSON")?;

    if status.logged_in {
        let auth_method = status.auth_method.as_deref().unwrap_or("unknown");
        let api_provider = status.api_provider.as_deref().unwrap_or("unknown");
        Ok(AuthCheck {
            authenticated: true,
            detail: format!("{} / {}", auth_method, api_provider),
        })
    } else {
        Ok(AuthCheck {
            authenticated: false,
            detail: "not logged in".to_string(),
        })
    }
}

fn check_codex_auth() -> Result<AuthCheck> {
    let output = Command::new("codex")
        .args(["login", "status"])
        .output()
        .context("failed to run `codex login status`")?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let text = if !stdout.is_empty() { stdout } else { stderr };

    let normalized = text.to_lowercase();
    if normalized.contains("logged in") {
        Ok(AuthCheck {
            authenticated: true,
            detail: text,
        })
    } else if normalized.contains("not logged in") || normalized.contains("logged out") {
        Ok(AuthCheck {
            authenticated: false,
            detail: if text.is_empty() {
                "not logged in".to_string()
            } else {
                text
            },
        })
    } else if output.status.success() {
        Ok(AuthCheck {
            authenticated: false,
            detail: if text.is_empty() {
                "login status did not confirm authentication".to_string()
            } else {
                text
            },
        })
    } else {
        anyhow::bail!(
            "`codex login status` exited with status {}: {}",
            output.status,
            text
        );
    }
}

fn run_claude_live_probe(model: &str) -> Result<()> {
    let probe_dir = make_probe_dir("claude")?;
    let mut cmd = Command::new(ModelProvider::Claude.binary());
    cmd.current_dir(&probe_dir);
    cmd.arg("-p");
    cmd.arg("Reply with exactly OK and no other text.");
    if !model.trim().is_empty() {
        cmd.arg("--model");
        cmd.arg(model);
    }
    cmd.args([
        "--output-format",
        "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--tools",
        "",
    ]);

    let result = run_command_with_timeout(cmd, Duration::from_secs(LIVE_PROBE_TIMEOUT_SECS));
    let _ = fs::remove_dir_all(&probe_dir);
    let output = result?;

    if !output.success {
        anyhow::bail!(summarize_command_failure("claude live smoke", &output));
    }

    if !claude_probe_output_contains_ok(&output.stdout) {
        anyhow::bail!("unexpected Claude smoke output");
    }

    Ok(())
}

fn run_codex_live_probe(model: &str) -> Result<()> {
    let probe_dir = make_probe_dir("codex")?;
    let last_message_path = probe_dir.join("last-message.txt");
    let mut cmd = Command::new("codex");
    cmd.current_dir(&probe_dir);
    cmd.arg("exec");
    cmd.arg("--json");
    cmd.arg("--full-auto");
    cmd.arg("--skip-git-repo-check");
    cmd.arg("--ephemeral");
    cmd.arg("--output-last-message");
    cmd.arg(last_message_path.to_string_lossy().to_string());
    if !model.trim().is_empty() {
        cmd.arg("--model");
        cmd.arg(model);
    }
    cmd.arg("Reply with exactly OK and do not run commands, inspect files, or use tools.");

    let result = run_command_with_timeout(cmd, Duration::from_secs(LIVE_PROBE_TIMEOUT_SECS));
    let output = result?;
    let last_message = fs::read_to_string(&last_message_path).unwrap_or_default();
    let _ = fs::remove_dir_all(&probe_dir);

    if !output.success {
        anyhow::bail!(summarize_command_failure("codex live smoke", &output));
    }

    if !last_message.to_uppercase().contains("OK") {
        anyhow::bail!("unexpected Codex smoke output");
    }

    Ok(())
}

fn run_command_with_timeout(mut cmd: Command, timeout: Duration) -> Result<CapturedCommand> {
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());
    let mut child = cmd.spawn().context("failed to spawn probe command")?;
    let deadline = Instant::now() + timeout;

    loop {
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            anyhow::bail!("timed out after {}s", timeout.as_secs());
        }

        match child
            .try_wait()
            .context("failed while waiting for probe command")?
        {
            Some(status) => {
                let mut stdout = String::new();
                let mut stderr = String::new();
                if let Some(mut handle) = child.stdout.take() {
                    let _ = handle.read_to_string(&mut stdout);
                }
                if let Some(mut handle) = child.stderr.take() {
                    let _ = handle.read_to_string(&mut stderr);
                }
                return Ok(CapturedCommand {
                    success: status.success(),
                    stdout,
                    stderr,
                });
            }
            None => std::thread::sleep(Duration::from_millis(100)),
        }
    }
}

fn make_probe_dir(provider_slug: &str) -> Result<PathBuf> {
    let path = std::env::temp_dir().join(format!(
        "foundry-studio-live-probe-{}-{}",
        provider_slug,
        Utc::now().timestamp_nanos_opt().unwrap_or(0)
    ));
    fs::create_dir_all(&path)?;
    Ok(path)
}

fn claude_probe_output_contains_ok(stdout: &str) -> bool {
    for line in stdout.lines() {
        if !line.contains('{') {
            continue;
        }
        let Ok(value) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };
        if let Some(result) = value.get("result").and_then(|value| value.as_str()) {
            if result.to_uppercase().contains("OK") {
                return true;
            }
        }
        if let Some(content) = value
            .get("message")
            .and_then(|message| message.get("content"))
            .and_then(|content| content.as_array())
        {
            for block in content {
                if let Some(text) = block.get("text").and_then(|value| value.as_str()) {
                    if text.to_uppercase().contains("OK") {
                        return true;
                    }
                }
            }
        }
    }

    false
}

fn summarize_command_failure(context: &str, output: &CapturedCommand) -> String {
    let stderr = truncate_str(output.stderr.trim(), 120);
    let stdout = truncate_str(output.stdout.trim(), 120);
    format!(
        "{} failed; stderr=`{}` stdout=`{}`",
        context,
        if stderr.is_empty() { "<empty>" } else { stderr },
        if stdout.is_empty() { "<empty>" } else { stdout }
    )
}

fn probe_cache_path(project_dir: &Path) -> PathBuf {
    project_dir.join(STUDIO_ROOT_DIR).join("probe-cache.json")
}

fn load_cached_live_probe(
    project_dir: &Path,
    provider: ModelProvider,
    model: &str,
    auth_detail: &str,
) -> Option<String> {
    let path = probe_cache_path(project_dir);
    let content = fs::read_to_string(path).ok()?;
    let cache: ProbeCache = serde_json::from_str(&content).ok()?;
    let now = Utc::now();

    cache.entries.iter().find_map(|entry| {
        let fresh =
            now.signed_duration_since(entry.checked_at).num_seconds() <= LIVE_PROBE_TTL_SECS;
        if entry.provider == provider.slug()
            && entry.model == model
            && entry.auth_detail == auth_detail
            && fresh
        {
            let age = now
                .signed_duration_since(entry.checked_at)
                .num_seconds()
                .max(0);
            Some(format!(
                "authenticated; cached live smoke OK ({}s old)",
                age
            ))
        } else {
            None
        }
    })
}

fn save_cached_live_probe(
    project_dir: &Path,
    provider: ModelProvider,
    model: &str,
    auth_detail: &str,
) {
    let path = probe_cache_path(project_dir);
    let mut cache = load_probe_cache(&path).unwrap_or_default();
    cache.entries.retain(|entry| {
        !(entry.provider == provider.slug()
            && entry.model == model
            && entry.auth_detail == auth_detail)
    });
    cache.entries.push(CachedProbeEntry {
        provider: provider.slug().to_string(),
        model: model.to_string(),
        auth_detail: auth_detail.to_string(),
        checked_at: Utc::now(),
    });

    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(content) = serde_json::to_string_pretty(&cache) {
        atomic_write_file_best_effort(&path, content.as_bytes());
    }
}

fn load_probe_cache(path: &Path) -> Option<ProbeCache> {
    let content = fs::read_to_string(path).ok()?;
    serde_json::from_str(&content).ok()
}

pub(super) fn readiness_summary(readiness: &ProviderReadiness) -> String {
    let summary = format!("{} - {}", readiness.short_label(), readiness.detail);
    if summary.len() > 78 {
        format!("{}...", truncate_str(&summary, 75))
    } else {
        summary
    }
}

pub(super) fn header_readiness_label(readiness: &ProviderReadiness) -> String {
    if readiness.is_available() {
        return "ready".to_string();
    }

    let detail = readiness.detail.trim();
    let concise = detail
        .strip_prefix("missing required Claude features: ")
        .or_else(|| detail.strip_prefix("missing required Codex features: "))
        .or_else(|| detail.strip_prefix("authenticated but live Claude smoke failed: "))
        .or_else(|| detail.strip_prefix("authenticated but live Codex smoke failed: "))
        .or_else(|| detail.strip_prefix("Claude auth status check failed: "))
        .or_else(|| detail.strip_prefix("Codex login status check failed: "))
        .unwrap_or(detail);

    let label = if detail.contains("CLI not found in PATH") {
        "CLI missing".to_string()
    } else {
        concise.to_string()
    };

    if label.len() > 32 {
        format!("{}...", truncate_str(&label, 29))
    } else {
        label
    }
}

pub(super) fn log_provider_probe(state: &mut StudioState, provider: ModelProvider) {
    let message = {
        let readiness = state.provider_readiness(provider);
        format!("{} {}", provider, readiness_summary(readiness))
    };
    state.log(message);
}

pub(super) fn display_model_name(model: &str) -> &str {
    if model.trim().is_empty() {
        "<cli-default>"
    } else {
        model
    }
}

fn command_exists(command: &str) -> bool {
    let lookup_cmd = if cfg!(target_os = "windows") { "where" } else { "which" };
    std::process::Command::new(lookup_cmd)
        .arg(command)
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use anyhow::Result;
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    use crate::agent::ModelProvider;

    use super::super::model::{ProviderMode, ProviderReadiness, ProviderState, STUDIO_ROOT_DIR};
    use super::{
        assess_claude_help, assess_codex_exec_help, claude_probe_output_contains_ok,
        default_provider_mode, header_readiness_label, load_cached_live_probe,
        save_cached_live_probe,
    };

    #[test]
    fn codex_probe_accepts_required_exec_features() {
        let help = r#"
Run Codex non-interactively

Usage: codex exec [OPTIONS] [PROMPT] [COMMAND]

Options:
      --skip-git-repo-check
      --full-auto
      --json
  -o, --output-last-message <FILE>
"#;

        let readiness = assess_codex_exec_help(help);
        assert_eq!(readiness.state, ProviderState::Ready);
    }

    #[test]
    fn codex_probe_blocks_when_required_flag_is_missing() {
        let help = r#"
Run Codex non-interactively

Usage: codex exec [OPTIONS] [PROMPT] [COMMAND]

Options:
      --full-auto
      --json
"#;

        let readiness = assess_codex_exec_help(help);
        assert_eq!(readiness.state, ProviderState::Blocked);
        assert!(readiness.detail.contains("--output-last-message"));
        assert!(readiness.detail.contains("--skip-git-repo-check"));
    }

    #[test]
    fn claude_probe_accepts_required_help_features() {
        let help = r#"
Usage: claude [options] [command] [prompt]

Options:
  -p, --print
  --output-format <format> text json stream-json
  --verbose
  --dangerously-skip-permissions
"#;

        let readiness = assess_claude_help(help);
        assert_eq!(readiness.state, ProviderState::Ready);
    }

    #[test]
    fn claude_probe_blocks_when_stream_json_support_is_missing() {
        let help = r#"
Usage: claude [options] [command] [prompt]

Options:
  -p, --print
  --output-format <format> text json
"#;

        let readiness = assess_claude_help(help);
        assert_eq!(readiness.state, ProviderState::Blocked);
        assert!(readiness.detail.contains("stream-json"));
        assert!(readiness.detail.contains("--verbose"));
        assert!(readiness.detail.contains("--dangerously-skip-permissions"));
    }

    #[test]
    fn default_provider_mode_prefers_claude_when_nothing_is_ready() {
        let claude = ProviderReadiness::missing("claude missing");
        let codex = ProviderReadiness::missing("codex missing");

        assert_eq!(default_provider_mode(&claude, &codex), ProviderMode::Claude);
    }

    #[test]
    fn header_readiness_label_shows_real_auth_reason() {
        let readiness = ProviderReadiness::blocked("not logged in");
        assert_eq!(header_readiness_label(&readiness), "not logged in");
    }

    #[test]
    fn header_readiness_label_strips_verbose_feature_prefix() {
        let readiness = ProviderReadiness::blocked(
            "missing required Claude features: stream-json, --verbose, --dangerously-skip-permissions",
        );
        assert!(header_readiness_label(&readiness).contains("stream-json"));
    }

    #[test]
    fn header_readiness_label_keeps_ready_short() {
        let readiness = ProviderReadiness::ready("authenticated; live smoke OK");
        assert_eq!(header_readiness_label(&readiness), "ready");
    }

    #[test]
    fn claude_live_probe_parser_accepts_result_event() {
        let output = r#"{"type":"result","result":"OK"}"#;
        assert!(claude_probe_output_contains_ok(output));
    }

    #[test]
    fn live_probe_cache_round_trip() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir = std::env::temp_dir().join(format!("foundry-probe-cache-{}", unique));
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        save_cached_live_probe(
            &project_dir,
            ModelProvider::Claude,
            "opus",
            "api-key / firstParty",
        );

        let cached = load_cached_live_probe(
            &project_dir,
            ModelProvider::Claude,
            "opus",
            "api-key / firstParty",
        );
        fs::remove_dir_all(&project_dir)?;

        assert!(cached.is_some());
        assert!(cached.unwrap_or_default().contains("cached live smoke OK"));
        Ok(())
    }
}

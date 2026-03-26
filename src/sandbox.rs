use portable_pty::CommandBuilder;
use std::path::Path;

/// Runtime sandbox configuration resolved from Config + host detection.
#[derive(Debug, Clone)]
pub struct SandboxConfig {
    pub enabled: bool,
    pub docker_available: bool,
    pub image_available: bool,
    pub image: String,
    pub extra_mounts: Vec<String>,
    /// Credential directories to mount from $HOME (e.g. [".claude", ".copilot"]).
    pub auth_dirs: Vec<String>,
    /// Extra environment variables injected into the container ("KEY=VALUE").
    pub env: Vec<String>,
}

/// Effective sandbox state after detection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SandboxStatus {
    /// Docker found, image found, sandbox enabled.
    Active,
    /// Sandbox enabled but Docker CLI not on PATH.
    DockerNotFound,
    /// Docker found but sandbox image not pulled/built.
    ImageNotFound,
    /// User explicitly disabled sandbox via config.
    Disabled,
}

impl std::fmt::Display for SandboxStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            SandboxStatus::Active => write!(f, "active"),
            SandboxStatus::DockerNotFound => write!(f, "docker not found"),
            SandboxStatus::ImageNotFound => write!(f, "image not found"),
            SandboxStatus::Disabled => write!(f, "disabled"),
        }
    }
}

impl SandboxConfig {
    pub fn detect(
        enabled: bool,
        image: &str,
        extra_mounts: Vec<String>,
        auth_dirs: Vec<String>,
        env: Vec<String>,
    ) -> Self {
        if !enabled {
            return SandboxConfig {
                enabled: false,
                docker_available: false,
                image_available: false,
                image: image.to_string(),
                extra_mounts,
                auth_dirs,
                env,
            };
        }

        let docker_available = crate::app::commands::docker_is_available();
        let image_available = if docker_available {
            crate::app::commands::sandbox_image_exists(image)
        } else {
            false
        };

        SandboxConfig {
            enabled: true,
            docker_available,
            image_available,
            image: image.to_string(),
            extra_mounts,
            auth_dirs,
            env,
        }
    }

    pub fn status(&self) -> SandboxStatus {
        if !self.enabled {
            return SandboxStatus::Disabled;
        }
        if !self.docker_available {
            return SandboxStatus::DockerNotFound;
        }
        if !self.image_available {
            return SandboxStatus::ImageNotFound;
        }
        SandboxStatus::Active
    }

    pub fn is_active(&self) -> bool {
        self.status() == SandboxStatus::Active
    }

    /// On macOS, CLI tools store OAuth tokens in the Keychain. Docker containers
    /// run Linux and can't access the host Keychain, so CLIs fall back to reading
    /// credential files from disk. This method extracts credentials from the
    /// Keychain and writes them to the appropriate files for each configured auth dir.
    ///
    /// Supported auth dirs:
    /// - ".claude": extracts from Keychain service "Claude Code-credentials"
    ///   to ~/.claude/.credentials.json
    /// - ".copilot": extracts from Keychain service "copilot-cli"
    ///   to ~/.copilot/config.json (if not already present)
    pub fn ensure_credentials_for_container(&self) {
        if !self.is_active() {
            return;
        }
        if cfg!(not(target_os = "macos")) {
            return;
        }
        let home = match std::env::var("HOME") {
            Ok(h) => h,
            Err(_) => return,
        };
        let user = std::env::var("USER").unwrap_or_else(|_| "user".to_string());
        let home_path = Path::new(&home);

        for auth_dir in &self.auth_dirs {
            match auth_dir.as_str() {
                ".claude" => {
                    let creds_path = home_path.join(".claude").join(".credentials.json");
                    if creds_path.exists() {
                        continue;
                    }
                    extract_keychain_credential(
                        "Claude Code-credentials",
                        &user,
                        &creds_path,
                    );
                }
                ".copilot" => {
                    let config_path = home_path.join(".copilot").join("config.json");
                    if config_path.exists() {
                        continue;
                    }
                    extract_keychain_credential(
                        "copilot-cli",
                        &user,
                        &config_path,
                    );
                }
                _ => {
                    // Custom auth dirs: no automatic credential extraction.
                    // Users must ensure credential files exist on the host.
                }
            }
        }
    }

    pub fn wrap_command_builder(
        &self,
        program: &str,
        args: &[String],
        project_dir: &Path,
        env_vars: &[(&str, &str)],
    ) -> CommandBuilder {
        let mut cmd = CommandBuilder::new("docker");
        cmd.args(["run", "--rm", "-it"]);

        // Bind-mount the project directory to /work
        let host_path = project_dir.to_string_lossy().to_string();
        let host_path = if cfg!(target_os = "windows") {
            translate_windows_path(&host_path)
        } else {
            host_path
        };
        cmd.arg("-v");
        cmd.arg(format!("{}:/work", host_path));

        // Set working directory inside container
        cmd.args(["-w", "/work"]);

        // Mount configured auth directories from $HOME into the container.
        // Each dir is mounted read-write at /home/node/<dir> so CLIs can
        // write session data and debug logs.
        if let Some(home) = std::env::var_os("HOME")
            .or_else(|| std::env::var_os("USERPROFILE"))
        {
            let home_path = Path::new(&home);
            for auth_dir in &self.auth_dirs {
                let host_dir = home_path.join(auth_dir);
                if host_dir.is_dir() {
                    let host_str = host_dir.to_string_lossy().to_string();
                    let host_str = if cfg!(target_os = "windows") {
                        translate_windows_path(&host_str)
                    } else {
                        host_str
                    };
                    cmd.arg("-v");
                    cmd.arg(format!("{}:/home/node/{}", host_str, auth_dir));
                }
            }
            // ~/.claude.json (CLI config) -- mount read-only if present
            let claude_json = home_path.join(".claude.json");
            if claude_json.is_file() {
                let host_json = claude_json.to_string_lossy().to_string();
                let host_json = if cfg!(target_os = "windows") {
                    translate_windows_path(&host_json)
                } else {
                    host_json
                };
                cmd.arg("-v");
                cmd.arg(format!("{}:/home/node/.claude.json:ro", host_json));
            }
        }

        // Forward env vars from caller
        for (key, value) in env_vars {
            cmd.arg("-e");
            cmd.arg(format!("{}={}", key, value));
        }

        // Forward configured sandbox env vars (e.g. ANTHROPIC_BASE_URL for copilot-api)
        for env_spec in &self.env {
            cmd.arg("-e");
            cmd.arg(env_spec);
        }

        // Forward ANTHROPIC_API_KEY from host if set
        if std::env::var("ANTHROPIC_API_KEY").is_ok() {
            cmd.args(["-e", "ANTHROPIC_API_KEY"]);
        }

        // Forward extra mounts
        for mount in &self.extra_mounts {
            cmd.arg("-v");
            cmd.arg(mount);
        }

        // Image name
        cmd.arg(&self.image);

        // Original program and args
        cmd.arg(program);
        for arg in args {
            cmd.arg(arg);
        }

        cmd
    }
}

/// Extract a credential from the macOS Keychain and write it to a file.
/// No-op on non-macOS platforms. Silently returns if extraction fails.
fn extract_keychain_credential(service: &str, account: &str, dest: &Path) {
    if cfg!(not(target_os = "macos")) {
        return;
    }
    // Ensure parent directory exists
    if let Some(parent) = dest.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let output = std::process::Command::new("security")
        .args(["find-generic-password", "-s", service, "-a", account, "-w"])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output();
    match output {
        Ok(out) if out.status.success() => {
            let cred_data = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !cred_data.is_empty() {
                if let Err(e) = std::fs::write(dest, &cred_data) {
                    eprintln!("Failed to write credential to {}: {}", dest.display(), e);
                } else {
                    #[cfg(unix)]
                    {
                        use std::os::unix::fs::PermissionsExt;
                        let _ = std::fs::set_permissions(
                            dest,
                            std::fs::Permissions::from_mode(0o600),
                        );
                    }
                }
            }
        }
        _ => {
            eprintln!(
                "Could not extract credentials from Keychain service '{}' for sandbox",
                service,
            );
        }
    }
}

/// Convert Windows-style paths (C:\Users\...) to Docker Desktop WSL2 format (/c/Users/...).
pub fn translate_windows_path(path: &str) -> String {
    if path.len() >= 2 && path.as_bytes()[1] == b':' {
        let drive = (path.as_bytes()[0] as char).to_ascii_lowercase();
        let rest = &path[2..];
        let rest = rest.replace('\\', "/");
        format!("/{drive}{rest}")
    } else {
        path.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sandbox_status_disabled() {
        let config = SandboxConfig {
            enabled: false,
            docker_available: true,
            image_available: true,
            image: "test:latest".into(),
            extra_mounts: vec![],
            auth_dirs: vec![".claude".into()],
            env: vec![],
        };
        assert_eq!(config.status(), SandboxStatus::Disabled);
        assert!(!config.is_active());
    }

    #[test]
    fn test_sandbox_status_active() {
        let config = SandboxConfig {
            enabled: true,
            docker_available: true,
            image_available: true,
            image: "test:latest".into(),
            extra_mounts: vec![],
            auth_dirs: vec![".claude".into()],
            env: vec![],
        };
        assert_eq!(config.status(), SandboxStatus::Active);
        assert!(config.is_active());
    }

    #[test]
    fn test_sandbox_status_docker_not_found() {
        let config = SandboxConfig {
            enabled: true,
            docker_available: false,
            image_available: false,
            image: "test:latest".into(),
            extra_mounts: vec![],
            auth_dirs: vec![".claude".into()],
            env: vec![],
        };
        assert_eq!(config.status(), SandboxStatus::DockerNotFound);
        assert!(!config.is_active());
    }

    #[test]
    fn test_sandbox_status_image_not_found() {
        let config = SandboxConfig {
            enabled: true,
            docker_available: true,
            image_available: false,
            image: "test:latest".into(),
            extra_mounts: vec![],
            auth_dirs: vec![".claude".into()],
            env: vec![],
        };
        assert_eq!(config.status(), SandboxStatus::ImageNotFound);
        assert!(!config.is_active());
    }

    #[test]
    fn test_translate_windows_path_drive_letter() {
        assert_eq!(translate_windows_path(r"C:\Users\name\project"), "/c/Users/name/project");
        assert_eq!(translate_windows_path(r"D:\work\repo"), "/d/work/repo");
    }

    #[test]
    fn test_translate_windows_path_lowercase() {
        assert_eq!(translate_windows_path(r"c:\users\name"), "/c/users/name");
    }

    #[test]
    fn test_translate_windows_path_unix_passthrough() {
        assert_eq!(translate_windows_path("/home/user/project"), "/home/user/project");
        assert_eq!(translate_windows_path("/Users/name/homelab"), "/Users/name/homelab");
    }

    #[test]
    fn test_translate_windows_path_empty() {
        assert_eq!(translate_windows_path(""), "");
    }

    #[test]
    fn test_wrap_command_builder_basic() {
        let config = SandboxConfig {
            enabled: true,
            docker_available: true,
            image_available: true,
            image: "foundry-sandbox:latest".into(),
            extra_mounts: vec![],
            auth_dirs: vec![".claude".into()],
            env: vec![],
        };
        let cmd = config.wrap_command_builder(
            "claude",
            &["-p".into(), "hello".into(), "--dangerously-skip-permissions".into()],
            Path::new("/Users/name/project"),
            &[("CLAUDECODE", "")],
        );
        // CommandBuilder fields are pub(crate) in portable-pty so we can't inspect them directly.
        // Verify the builder was constructed without panicking.
        let _ = cmd;
    }

    #[test]
    fn test_wrap_command_builder_with_extra_mounts() {
        let config = SandboxConfig {
            enabled: true,
            docker_available: true,
            image_available: true,
            image: "foundry-sandbox:latest".into(),
            extra_mounts: vec!["/data:/data:ro".into(), "/cache:/cache".into()],
            auth_dirs: vec![".claude".into()],
            env: vec![],
        };
        let cmd = config.wrap_command_builder(
            "claude",
            &["-p".into(), "test".into()],
            Path::new("/tmp/project"),
            &[],
        );
        let _ = cmd;
    }

    #[test]
    fn test_sandbox_status_display() {
        assert_eq!(format!("{}", SandboxStatus::Active), "active");
        assert_eq!(format!("{}", SandboxStatus::DockerNotFound), "docker not found");
        assert_eq!(format!("{}", SandboxStatus::ImageNotFound), "image not found");
        assert_eq!(format!("{}", SandboxStatus::Disabled), "disabled");
    }
}

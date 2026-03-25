// Items in this module are consumed by agent.rs in T19.3.
#![allow(dead_code)]

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
    pub fn detect(enabled: bool, image: &str, extra_mounts: Vec<String>) -> Self {
        if !enabled {
            return SandboxConfig {
                enabled: false,
                docker_available: false,
                image_available: false,
                image: image.to_string(),
                extra_mounts,
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

    pub fn wrap_command_builder(
        &self,
        program: &str,
        args: &[String],
        project_dir: &Path,
        env_vars: &[(&str, &str)],
    ) -> CommandBuilder {
        let mut cmd = CommandBuilder::new("docker");
        cmd.args(["run", "--rm", "-i"]);

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

        // Forward env vars
        for (key, value) in env_vars {
            cmd.arg("-e");
            cmd.arg(format!("{}={}", key, value));
        }

        // Forward ANTHROPIC_API_KEY from host
        cmd.args(["-e", "ANTHROPIC_API_KEY"]);

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

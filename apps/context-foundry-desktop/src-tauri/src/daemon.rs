//! Daemon Management Module
//!
//! Handles spawning, monitoring, and controlling the Context Foundry daemon (cfd).
//! This module provides process supervision and health checking.

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};
use serde::{Deserialize, Serialize};
use log::{info, warn, error, debug};
use thiserror::Error;
use tokio::time::sleep;

/// Default port for the CF Daemon HTTP API
const DEFAULT_API_PORT: u16 = 8421;

/// Maximum time to wait for daemon to become healthy
const HEALTH_TIMEOUT_SECS: u64 = 30;

/// Interval between health check polls
const HEALTH_POLL_INTERVAL_MS: u64 = 500;

/// Errors that can occur during daemon management
#[derive(Error, Debug)]
pub enum DaemonError {
    #[error("Failed to spawn daemon process: {0}")]
    SpawnError(String),

    #[error("Daemon failed to become healthy within {0} seconds")]
    HealthTimeout(u64),

    #[error("Daemon health check failed: {0}")]
    HealthCheckFailed(String),

    #[error("Failed to find cfd binary: {0}")]
    BinaryNotFound(String),

    #[error("Failed to stop daemon: {0}")]
    StopError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("HTTP request error: {0}")]
    HttpError(#[from] reqwest::Error),
}

/// Current status of the daemon
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DaemonStatus {
    pub running: bool,
    pub port: u16,
    pub pid: Option<u32>,
    pub uptime_seconds: Option<u64>,
    pub jobs_running: Option<u32>,
    pub jobs_total: Option<u32>,
    pub version: Option<String>,
}

impl Default for DaemonStatus {
    fn default() -> Self {
        Self {
            running: false,
            port: DEFAULT_API_PORT,
            pid: None,
            uptime_seconds: None,
            jobs_running: None,
            jobs_total: None,
            version: None,
        }
    }
}

/// Health response from the daemon API
#[derive(Debug, Deserialize)]
struct HealthResponse {
    status: String,
    uptime_seconds: Option<f64>,
    pid: Option<u32>,
    jobs_running: Option<u32>,
    jobs_completed: Option<u32>,
    jobs_failed: Option<u32>,
    jobs_pending: Option<u32>,
    version: Option<String>,
}

/// Manages the Context Foundry daemon process
pub struct DaemonManager {
    port: u16,
    child_process: Option<Child>,
    http_client: reqwest::Client,
    cfd_binary_path: Option<PathBuf>,
}

impl DaemonManager {
    /// Create a new DaemonManager
    pub fn new() -> Self {
        let port = std::env::var("CFD_HTTP_API_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(DEFAULT_API_PORT);

        let http_client = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            port,
            child_process: None,
            http_client,
            cfd_binary_path: None,
        }
    }

    /// Get the API base URL
    fn api_url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    /// Find the cfd binary path
    fn find_cfd_binary(&mut self) -> Result<PathBuf, DaemonError> {
        if let Some(ref path) = self.cfd_binary_path {
            return Ok(path.clone());
        }

        // Check common locations in order of preference
        let candidates: Vec<PathBuf> = vec![
            // 1. Check if cfd is in PATH
            which_cfd(),
            // 2. macOS Application Support
            dirs::data_local_dir()
                .map(|p| p.join("ContextFoundry/bin/cfd")),
            // 3. Home directory .local/bin
            dirs::home_dir()
                .map(|p| p.join(".local/bin/cfd")),
            // 4. Homebrew location (Apple Silicon)
            Some(PathBuf::from("/opt/homebrew/bin/cfd")),
            // 5. Homebrew location (Intel)
            Some(PathBuf::from("/usr/local/bin/cfd")),
        ]
        .into_iter()
        .flatten()
        .collect();

        for path in candidates {
            debug!("Checking for cfd at: {:?}", path);
            if path.exists() && path.is_file() {
                info!("Found cfd binary at: {:?}", path);
                self.cfd_binary_path = Some(path.clone());
                return Ok(path);
            }
        }

        Err(DaemonError::BinaryNotFound(
            "Could not find 'cfd' binary. Please ensure Context Foundry is installed.".to_string()
        ))
    }

    /// Check if daemon is currently healthy via HTTP API
    pub async fn check_health(&self) -> Result<DaemonStatus, DaemonError> {
        let url = format!("{}/health", self.api_url());
        debug!("Checking daemon health at: {}", url);

        let response = self.http_client.get(&url).send().await?;

        if !response.status().is_success() {
            return Err(DaemonError::HealthCheckFailed(
                format!("Health check returned status: {}", response.status())
            ));
        }

        let health: HealthResponse = response.json().await?;

        let jobs_total = health.jobs_running.unwrap_or(0)
            + health.jobs_completed.unwrap_or(0)
            + health.jobs_failed.unwrap_or(0)
            + health.jobs_pending.unwrap_or(0);

        Ok(DaemonStatus {
            running: health.status == "healthy" || health.status == "ok",
            port: self.port,
            pid: health.pid,
            uptime_seconds: health.uptime_seconds.map(|u| u as u64),
            jobs_running: health.jobs_running,
            jobs_total: Some(jobs_total),
            version: health.version,
        })
    }

    /// Get current daemon status (non-blocking)
    pub async fn get_status(&self) -> Result<DaemonStatus, DaemonError> {
        match self.check_health().await {
            Ok(status) => Ok(status),
            Err(_) => Ok(DaemonStatus::default()),
        }
    }

    /// Ensure the daemon is running, starting it if necessary
    pub async fn ensure_running(&mut self) -> Result<DaemonStatus, DaemonError> {
        // First check if already running
        if let Ok(status) = self.check_health().await {
            if status.running {
                info!("Daemon already running on port {}", self.port);
                return Ok(status);
            }
        }

        info!("Daemon not running, attempting to start...");
        self.spawn().await
    }

    /// Spawn the daemon process
    async fn spawn(&mut self) -> Result<DaemonStatus, DaemonError> {
        let binary_path = self.find_cfd_binary()?;

        info!("Spawning daemon from: {:?}", binary_path);

        // Spawn cfd start command
        let child = Command::new(&binary_path)
            .arg("start")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| DaemonError::SpawnError(e.to_string()))?;

        self.child_process = Some(child);

        // Wait for daemon to become healthy
        self.wait_for_health().await
    }

    /// Wait for daemon to become healthy
    async fn wait_for_health(&self) -> Result<DaemonStatus, DaemonError> {
        let start = Instant::now();
        let timeout = Duration::from_secs(HEALTH_TIMEOUT_SECS);

        info!("Waiting for daemon to become healthy (timeout: {}s)...", HEALTH_TIMEOUT_SECS);

        loop {
            if start.elapsed() > timeout {
                return Err(DaemonError::HealthTimeout(HEALTH_TIMEOUT_SECS));
            }

            match self.check_health().await {
                Ok(status) if status.running => {
                    info!("Daemon is healthy after {:?}", start.elapsed());
                    return Ok(status);
                }
                Ok(_) => {
                    debug!("Daemon not yet healthy, retrying...");
                }
                Err(e) => {
                    debug!("Health check failed (may still be starting): {}", e);
                }
            }

            sleep(Duration::from_millis(HEALTH_POLL_INTERVAL_MS)).await;
        }
    }

    /// Stop the daemon
    pub async fn stop(&mut self) -> Result<(), DaemonError> {
        info!("Stopping daemon...");

        // Try to find and use cfd binary to stop gracefully
        if let Ok(binary_path) = self.find_cfd_binary() {
            let output = Command::new(&binary_path)
                .arg("stop")
                .output()
                .map_err(|e| DaemonError::StopError(e.to_string()))?;

            if output.status.success() {
                info!("Daemon stopped successfully");
                self.child_process = None;
                return Ok(());
            } else {
                warn!("cfd stop command failed: {:?}", output);
            }
        }

        // If we spawned it, try to kill directly
        if let Some(ref mut child) = self.child_process {
            match child.kill() {
                Ok(_) => {
                    info!("Daemon process killed");
                    self.child_process = None;
                    Ok(())
                }
                Err(e) => Err(DaemonError::StopError(e.to_string())),
            }
        } else {
            Ok(())
        }
    }

    /// Restart the daemon
    pub async fn restart(&mut self) -> Result<DaemonStatus, DaemonError> {
        info!("Restarting daemon...");

        // Stop if running
        let _ = self.stop().await;

        // Give it a moment
        sleep(Duration::from_millis(500)).await;

        // Start again
        self.spawn().await
    }
}

impl Default for DaemonManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for DaemonManager {
    fn drop(&mut self) {
        // Note: We don't kill the daemon on drop since it should persist
        // after the desktop app closes. The daemon runs independently.
        if let Some(ref mut child) = self.child_process {
            // Just detach, don't kill
            let _ = child.id();
        }
    }
}

/// Find cfd in PATH using which command (or equivalent)
fn which_cfd() -> Option<PathBuf> {
    Command::new("which")
        .arg("cfd")
        .output()
        .ok()
        .and_then(|output| {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout)
                    .trim()
                    .to_string();
                if !path.is_empty() {
                    Some(PathBuf::from(path))
                } else {
                    None
                }
            } else {
                None
            }
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_daemon_status_default() {
        let status = DaemonStatus::default();
        assert!(!status.running);
        assert_eq!(status.port, DEFAULT_API_PORT);
        assert!(status.pid.is_none());
    }

    #[test]
    fn test_daemon_manager_new() {
        let manager = DaemonManager::new();
        assert_eq!(manager.port, DEFAULT_API_PORT);
        assert!(manager.child_process.is_none());
    }

    #[test]
    fn test_api_url() {
        let manager = DaemonManager::new();
        assert!(manager.api_url().contains("127.0.0.1"));
        assert!(manager.api_url().contains("8421"));
    }
}

//! Context Foundry Desktop - Tauri Backend Library
//!
//! This module provides the core functionality for the Context Foundry Desktop application,
//! including daemon management, health checking, and IPC with the frontend.

mod daemon;
mod api;
mod tray;
mod commands;

use std::sync::Arc;
use tokio::sync::Mutex;
use tauri::{AppHandle, Manager, Emitter};
use log::{info, error};

pub use daemon::DaemonManager;
pub use api::DaemonApi;

/// Application state shared across the Tauri app
pub struct AppState {
    pub daemon_manager: Arc<Mutex<DaemonManager>>,
    pub api: Arc<DaemonApi>,
}

impl AppState {
    pub fn new() -> Self {
        let daemon_manager = Arc::new(Mutex::new(DaemonManager::new()));
        let api = Arc::new(DaemonApi::new());

        Self {
            daemon_manager,
            api,
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Application Setup
// ============================================================================

/// Initialize the Tauri application with all plugins and state
pub fn run() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            info!("Context Foundry Desktop starting up...");

            // Initialize application state
            let state = AppState::new();
            app.manage(state);

            // Setup system tray
            if let Err(e) = tray::setup_tray(app) {
                error!("Failed to setup system tray: {}", e);
            }

            // Spawn background task to ensure daemon is running
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                startup_daemon_check(handle).await;
            });

            info!("Context Foundry Desktop initialized successfully");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::check_daemon_status,
            commands::start_daemon,
            commands::stop_daemon,
            commands::restart_daemon,
            commands::get_health,
            commands::get_jobs,
            commands::get_job,
            commands::get_job_tree,
            commands::get_job_timeline,
            commands::get_job_gates,
            commands::get_metrics,
            commands::get_recent_events,
            commands::get_config,
            commands::cmd_get_agents,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Performs initial daemon check on startup
async fn startup_daemon_check(handle: AppHandle) {
    info!("Checking daemon status on startup...");

    let state: tauri::State<'_, AppState> = handle.state();
    let mut manager = state.daemon_manager.lock().await;

    match manager.ensure_running().await {
        Ok(status) => {
            info!("Daemon is running: {:?}", status);
            // Emit event to frontend
            let _ = handle.emit("daemon-status", &status);
        }
        Err(e) => {
            error!("Failed to start daemon: {}", e);
            // Emit error event to frontend
            let _ = handle.emit("daemon-error", e.to_string());
        }
    }
}

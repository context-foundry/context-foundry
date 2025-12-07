use crate::daemon;
use crate::AppState;
use tauri::State;

/// Check if the daemon is currently running
#[tauri::command]
pub async fn check_daemon_status(state: State<'_, AppState>) -> Result<daemon::DaemonStatus, String> {
    let manager = state.daemon_manager.lock().await;
    manager.get_status().await.map_err(|e| e.to_string())
}

/// Start the daemon if not already running
#[tauri::command]
pub async fn start_daemon(state: State<'_, AppState>) -> Result<daemon::DaemonStatus, String> {
    let mut manager = state.daemon_manager.lock().await;
    manager.ensure_running().await.map_err(|e| e.to_string())
}

/// Stop the daemon
#[tauri::command]
pub async fn stop_daemon(state: State<'_, AppState>) -> Result<(), String> {
    let mut manager = state.daemon_manager.lock().await;
    manager.stop().await.map_err(|e| e.to_string())
}

/// Restart the daemon
#[tauri::command]
pub async fn restart_daemon(state: State<'_, AppState>) -> Result<daemon::DaemonStatus, String> {
    let mut manager = state.daemon_manager.lock().await;
    manager.restart().await.map_err(|e| e.to_string())
}

/// Get health information from the daemon API
#[tauri::command]
pub async fn get_health(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    state.api.health().await.map_err(|e| e.to_string())
}

/// Get list of jobs from the daemon API
#[tauri::command]
pub async fn get_jobs(
    state: State<'_, AppState>,
    status: Option<String>,
    limit: Option<u32>,
    offset: Option<u32>,
) -> Result<serde_json::Value, String> {
    state.api.get_jobs(status, limit, offset).await.map_err(|e| e.to_string())
}

/// Get a specific job by ID
#[tauri::command]
pub async fn get_job(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    state.api.get_job(&job_id).await.map_err(|e| e.to_string())
}

/// Get job tree (phases and tasks)
#[tauri::command]
pub async fn get_job_tree(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    state.api.get_job_tree(&job_id).await.map_err(|e| e.to_string())
}

/// Get job timeline (events)
#[tauri::command]
pub async fn get_job_timeline(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    state.api.get_job_timeline(&job_id).await.map_err(|e| e.to_string())
}

/// Get job phase gates
#[tauri::command]
pub async fn get_job_gates(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    state.api.get_job_gates(&job_id).await.map_err(|e| e.to_string())
}

/// Get metrics from the daemon
#[tauri::command]
pub async fn get_metrics(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    state.api.get_metrics().await.map_err(|e| e.to_string())
}

/// Get recent events
#[tauri::command]
pub async fn get_recent_events(
    state: State<'_, AppState>,
    event_type: Option<String>,
) -> Result<serde_json::Value, String> {
    state.api.get_recent_events(event_type).await.map_err(|e| e.to_string())
}

/// Get daemon configuration
#[tauri::command]
pub async fn get_config(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    state.api.get_config().await.map_err(|e| e.to_string())
}

/// Get agent configuration
#[tauri::command(rename = "get_agents")]
pub async fn cmd_get_agents(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    state.api.get_agents().await.map_err(|e| e.to_string())
}

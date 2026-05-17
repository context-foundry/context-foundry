//! TTL reaper: periodically expire previews whose TTL has elapsed.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use crate::service::{db, AppState};

/// Run the reaper loop until `shutdown` is set.
pub async fn run_reaper(state: Arc<AppState>, shutdown: Arc<AtomicBool>) {
    while !shutdown.load(Ordering::Relaxed) {
        if let Ok(ids) = db::expire_due_previews(&state.pool).await {
            for id in ids {
                let _ = state.build.teardown(&id).await;
                let _ = db::insert_event(&state.pool, &id, "expired", None, None).await;
            }
        }
        let _ = sweep_orphans_once(&state).await;
        tokio::time::sleep(Duration::from_secs(state.config.reaper_interval_secs)).await;
    }
}

/// Run a single reaper pass — used by tests. Returns the expired job ids.
pub async fn reap_once(state: &Arc<AppState>) -> anyhow::Result<Vec<String>> {
    let ids = db::expire_due_previews(&state.pool).await?;
    for id in &ids {
        let _ = state.build.teardown(id).await;
        let _ = db::insert_event(&state.pool, id, "expired", None, None).await;
    }
    Ok(ids)
}

/// One orphan-sweep pass: tear down build/preview containers and proxy tokens
/// whose job id is no longer active (a job from a dead worker, or a cancelled
/// job whose token was leaked). Returns the swept container job labels.
pub async fn sweep_orphans_once(state: &Arc<AppState>) -> anyhow::Result<Vec<String>> {
    let active = db::active_job_ids(&state.pool).await?;
    let swept = state.build.sweep_orphans(&active).await.unwrap_or_default();
    let active_refs: Vec<&str> = active.iter().map(String::as_str).collect();
    let removed_tokens = state.proxy.sweep(&active_refs);
    if !swept.is_empty() || removed_tokens > 0 {
        eprintln!(
            "foundry service: orphan sweep removed {} container(s), {} proxy token(s)",
            swept.len(),
            removed_tokens
        );
    }
    Ok(swept)
}

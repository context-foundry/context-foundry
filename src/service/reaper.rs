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

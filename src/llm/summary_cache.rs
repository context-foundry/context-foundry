use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};
use std::time::SystemTime;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StageState {
    NotStarted,
    Running,
    Complete,
    Failed,
}

impl StageState {
    pub fn as_str(&self) -> &'static str {
        match self {
            StageState::NotStarted => "not_started",
            StageState::Running => "running",
            StageState::Complete => "complete",
            StageState::Failed => "failed",
        }
    }
}

#[derive(Debug, Clone)]
pub struct CacheKeyInput<'a> {
    pub surface_tag: &'a str,
    pub stage: &'a str,
    pub state: &'a StageState,
    pub artifacts: &'a [PathBuf],
}

pub struct StageSummaryCache {
    inner: Mutex<HashMap<String, String>>,
}

pub fn global() -> &'static StageSummaryCache {
    static CACHE: OnceLock<StageSummaryCache> = OnceLock::new();
    CACHE.get_or_init(|| StageSummaryCache {
        inner: Mutex::new(HashMap::new()),
    })
}

pub fn compute_key(input: &CacheKeyInput<'_>) -> String {
    let mut hasher = blake3::Hasher::new();
    hasher.update(input.surface_tag.as_bytes());
    hasher.update(b"\0");
    hasher.update(input.stage.as_bytes());
    hasher.update(b"|");
    hasher.update(input.state.as_str().as_bytes());
    for p in input.artifacts {
        hasher.update(b"|");
        hasher.update(p.to_string_lossy().as_bytes());
        match std::fs::metadata(p).and_then(|m| m.modified()) {
            Ok(t) => match t.duration_since(SystemTime::UNIX_EPOCH) {
                Ok(dur) => {
                    hasher.update(&dur.as_nanos().to_le_bytes());
                }
                Err(_) => {
                    hasher.update(b":noent");
                }
            },
            Err(_) => {
                hasher.update(b":noent");
            }
        }
    }
    let hex = hasher.finalize().to_hex().to_string();
    hex.chars().take(32).collect::<String>()
}

pub fn lookup(cache: &StageSummaryCache, key: &str) -> Option<String> {
    let guard = cache.inner.lock().ok()?;
    guard.get(key).cloned()
}

pub fn insert(cache: &StageSummaryCache, key: String, summary: String) {
    let Ok(mut guard) = cache.inner.lock() else {
        return;
    };
    if guard.len() >= 256 {
        guard.clear();
    }
    guard.insert(key, summary);
}

pub fn invalidate(cache: &StageSummaryCache, key: &str) {
    let Ok(mut guard) = cache.inner.lock() else {
        return;
    };
    guard.remove(key);
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::thread;
    use std::time::Duration;

    #[test]
    fn cache_key_includes_mtime() {
        let mut tmp = tempfile::NamedTempFile::new().expect("tempfile");
        tmp.write_all(b"a").unwrap();
        tmp.flush().unwrap();
        let path = tmp.path().to_path_buf();
        let artifacts = vec![path.clone()];

        let key1 = compute_key(&CacheKeyInput {
            surface_tag: "pipeline_stage",
            stage: "plan-review",
            state: &StageState::Running,
            artifacts: &artifacts,
        });

        thread::sleep(Duration::from_millis(1100));
        std::fs::write(&path, b"b").unwrap();

        let key2 = compute_key(&CacheKeyInput {
            surface_tag: "pipeline_stage",
            stage: "plan-review",
            state: &StageState::Running,
            artifacts: &artifacts,
        });

        assert_ne!(key1, key2, "mtime change must change the cache key");
    }

    #[test]
    fn cache_key_changes_on_state_transition() {
        let tmp = tempfile::NamedTempFile::new().expect("tempfile");
        let path = tmp.path().to_path_buf();
        std::fs::write(&path, b"a").unwrap();
        let artifacts = vec![path];

        let key_running = compute_key(&CacheKeyInput {
            surface_tag: "pipeline_stage",
            stage: "plan-review",
            state: &StageState::Running,
            artifacts: &artifacts,
        });
        let key_complete = compute_key(&CacheKeyInput {
            surface_tag: "pipeline_stage",
            stage: "plan-review",
            state: &StageState::Complete,
            artifacts: &artifacts,
        });

        assert_ne!(
            key_running, key_complete,
            "state transition must change the cache key"
        );
    }
}

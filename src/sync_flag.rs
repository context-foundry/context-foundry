//! `SyncFlag` -- a thin wrapper around `AtomicBool` that enforces Acquire/Release
//! ordering for cross-thread gate signaling. Use this instead of raw `AtomicBool`
//! whenever a boolean is shared between threads as a pause/resume or done/not-done
//! flag.
//!
//! ## Why this exists
//! Relaxed ordering on AtomicBool gates is unsound on ARM/Apple Silicon.
//! This bug was fixed in D53.2 (commit_approval_gate) and D56.1 (review_gate)
//! but kept recurring because new atomics default to Relaxed. SyncFlag makes
//! the correct ordering the only option.
//!
//! ## When NOT to use SyncFlag
//! - Monotonic counters (AtomicU64 for cost accumulation) -- Relaxed is correct
//! - Process-local sequence counters (AtomicU64 in isolation.rs) -- Relaxed is correct
//! - Single-threaded config flags (AtomicU8 for truecolor override) -- Relaxed is correct
//!
//! Clippy note: if you see `Ordering::Relaxed` on an AtomicBool used as a
//! cross-thread gate, replace it with SyncFlag.

use std::sync::atomic::{AtomicBool, Ordering};

/// A boolean flag for cross-thread signaling with correct memory ordering.
///
/// - `set()` uses `Release` ordering (publishes all prior writes)
/// - `clear()` uses `Release` ordering (publishes all prior writes)
/// - `get()` uses `Acquire` ordering (sees all writes before the flag change)
#[derive(Debug)]
pub struct SyncFlag {
    inner: AtomicBool,
}

impl SyncFlag {
    pub const fn new(value: bool) -> Self {
        Self {
            inner: AtomicBool::new(value),
        }
    }

    /// Load the flag value with Acquire ordering.
    pub fn get(&self) -> bool {
        self.inner.load(Ordering::Acquire)
    }

    /// Store `true` with Release ordering.
    pub fn set(&self) {
        self.inner.store(true, Ordering::Release);
    }

    /// Store `false` with Release ordering.
    pub fn clear(&self) {
        self.inner.store(false, Ordering::Release);
    }

    /// Store an arbitrary value with Release ordering.
    pub fn store(&self, value: bool) {
        self.inner.store(value, Ordering::Release);
    }
}

impl Default for SyncFlag {
    fn default() -> Self {
        Self::new(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    #[test]
    fn test_sync_flag_default_is_false() {
        let flag = SyncFlag::new(false);
        assert!(!flag.get());
    }

    #[test]
    fn test_sync_flag_set_and_clear() {
        let flag = SyncFlag::new(false);
        flag.set();
        assert!(flag.get());
        flag.clear();
        assert!(!flag.get());
    }

    #[test]
    fn test_sync_flag_store_arbitrary() {
        let flag = SyncFlag::new(false);
        flag.store(true);
        assert!(flag.get());
        flag.store(false);
        assert!(!flag.get());
    }

    #[test]
    fn test_sync_flag_arc_shared() {
        let flag = Arc::new(SyncFlag::new(false));
        let flag2 = flag.clone();
        flag.set();
        assert!(flag2.get());
        flag2.clear();
        assert!(!flag.get());
    }
}

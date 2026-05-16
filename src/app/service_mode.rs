//! Run-mode policy for the unattended build-service mode.
//!
//! `service` is the unattended build-service run mode (Phase 35); it
//! (1) terminates on an empty queue with no Discovery, (2) skips the
//! bootstrap Scout, (3) treats a WIP/audit-failed task as terminal
//! (mark done, advance, no retry), (4) disables the consecutive-WIP
//! hard stop, and `run_headless` also skips the GitHub update check.
//! `auto`/`sprint`/`review`/`coach` are unaffected.

/// The canonical `run_mode` string for the build-service mode.
pub(super) const SERVICE: &str = "service";

/// True when the run mode is the build-service mode.
pub(super) fn is_service(run_mode: &str) -> bool {
    run_mode == SERVICE
}

/// True when a WIP / audit-failed task must be marked done (advance,
/// no retry) instead of left pending.
pub(super) fn wip_is_terminal(run_mode: &str) -> bool {
    is_service(run_mode)
}

/// True when the consecutive-WIP hard stop (pause after two WIPs on
/// the same task) is enforced.
pub(super) fn enforces_consecutive_wip_stop(run_mode: &str) -> bool {
    !is_service(run_mode)
}

/// True when the build loop may run the bootstrap Scout that invents
/// an initial task queue from an empty `TASKS.md`.
pub(super) fn runs_bootstrap_scout(run_mode: &str) -> bool {
    !is_service(run_mode)
}

/// True when `run_headless` should spawn the background GitHub update check.
pub(super) fn spawns_update_check(run_mode: &str) -> bool {
    !is_service(run_mode)
}

#[cfg(test)]
mod tests {
    use super::*;

    const OTHER_MODES: [&str; 4] = ["auto", "sprint", "review", "coach"];

    #[test]
    fn is_service_true_only_for_service() {
        assert!(is_service("service"));
        for m in OTHER_MODES {
            assert!(!is_service(m));
        }
    }

    #[test]
    fn wip_is_terminal_only_in_service_mode() {
        assert!(wip_is_terminal("service"));
        for m in OTHER_MODES {
            assert!(!wip_is_terminal(m));
        }
    }

    #[test]
    fn consecutive_wip_stop_disabled_only_in_service_mode() {
        assert!(!enforces_consecutive_wip_stop("service"));
        for m in OTHER_MODES {
            assert!(enforces_consecutive_wip_stop(m));
        }
    }

    #[test]
    fn bootstrap_scout_skipped_only_in_service_mode() {
        assert!(!runs_bootstrap_scout("service"));
        for m in OTHER_MODES {
            assert!(runs_bootstrap_scout(m));
        }
    }

    #[test]
    fn update_check_skipped_only_in_service_mode() {
        assert!(!spawns_update_check("service"));
        for m in OTHER_MODES {
            assert!(spawns_update_check(m));
        }
    }

    #[test]
    fn unknown_mode_keeps_default_behavior() {
        assert!(!is_service("loop"));
        assert!(runs_bootstrap_scout("loop"));
        assert!(spawns_update_check("loop"));
    }
}

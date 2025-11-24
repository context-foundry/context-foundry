# CF Daemon Timeout & Cleanup Fixes

This note documents the changes applied to stop autonomous builds from running past
their SLA, holding the worker hostage, and leaving orphaned CLAUDE processes alive.

## Summary

1. **Default timeout lowered to 90 minutes**
   - `context_foundry/daemon/config.py` now sets `default_job_timeout_minutes = 90`, so all new jobs inherit the intended deadline unless explicitly overridden via CLI/config.

2. **Workers respect the config timeout**
   - `JobManager._execute_job` reads the value from config (or per-job params) instead of hard-coding 120 minutes, ensuring the daemon’s enforcement aligns with monitoring expectations.

3. **Automatic process cleanup for cancellations & timeouts**
   - `JobManager.cancel_job` calls into the runner to kill any tracked subprocesses before marking the job cancelled.
   - When a job exceeds its timeout, `_execute_job` now calls the same termination helper before failing the job and freeing the worker.
   - Jobs cancelled mid-run no longer get re-queued for retries.

4. **Runner tracks job IDs and tears down process trees**
   - Every delegation/autonomous build subprocess is tagged with its owning job ID inside `Runner.active_tasks`.
   - Added `Runner.terminate_job_processes` and `_kill_process_tree`, which terminate the CLAUDE wrapper plus any child processes (using `psutil` when available).
   - Autonomous build timeout handler now uses `_kill_process_tree` so the run actually stops instead of lingering after the timeout log.

5. **Graceful shutdown cleans up everything**
   - `Runner.cleanup_active_tasks` delegates to `_kill_process_tree`, so daemon restarts no longer leave orphaned builds.

## Recommended Follow-Up

- Restart the daemon (or redeploy) so the new defaults/config take effect.
- Requeue/cancel any RUNNING jobs started before the change so they pick up the new timeout behavior.

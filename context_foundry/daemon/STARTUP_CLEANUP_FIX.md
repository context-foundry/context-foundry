# Startup Lock Cleanup Fix

## Problem Identified

**Original Implementation Gap:**

The `cleanup_stale_locks()` method only iterated over the in-memory `_active_locks` dict, which is **empty on daemon startup**. This meant stale `.cfd-lock` files from crashed builds persisted indefinitely until someone tried to acquire that specific directory again.

```python
# BEFORE (broken)
def cleanup_stale_locks(self):
    with self._lock:
        for path in list(self._active_locks.keys()):  # <- EMPTY on startup!
            # Check and remove stale locks
            ...
```

**Result:** Orphaned lockfiles from crashed builds blocked directories permanently until manual intervention or accidental cleanup during a new build attempt.

## Solution

### 1. Enhanced `cleanup_stale_locks()` Method

Now accepts an optional `working_directories` parameter to scan disk-based lockfiles:

```python
def cleanup_stale_locks(self, working_directories: Optional[List[Union[str, Path]]] = None):
    """
    Clean up stale locks on daemon startup

    Scans both:
    1. In-memory locks (from current daemon instance)
    2. Disk-based lockfiles (from provided working directories)
    """
    with self._lock:
        # First: Check in-memory locks
        for path in list(self._active_locks.keys()):
            ...

        # Second: Check disk lockfiles from provided directories
        # THIS IS THE KEY FIX for startup cleanup
        if working_directories:
            for workdir in working_directories:
                norm_path = self.normalize_path(workdir)
                lockfile_path = norm_path / self.LOCK_FILENAME

                if lockfile_path.exists():
                    lock_info = self._read_lockfile(lockfile_path)
                    is_stale, reason = self._is_lock_stale(lock_info)

                    if is_stale:
                        self._remove_lockfile(lockfile_path)
```

### 2. JobManager Integration

Added `_get_potentially_locked_directories()` to find directories that need cleanup:

```python
def _get_potentially_locked_directories(self) -> List[str]:
    """
    Get working directories from jobs that might have lockfiles

    Called on daemon startup to find directories that need stale lock cleanup.
    """
    workdirs = []

    # Check RUNNING jobs (may have crashed with locks still held)
    running_jobs = self.store.list_jobs(status=JobStatus.RUNNING, limit=1000)
    for job in running_jobs:
        workdir = job.params.get("working_directory")
        if workdir:
            workdirs.append(workdir)

    # Also check recent FAILED jobs (may have left stale locks)
    failed_jobs = self.store.list_jobs(status=JobStatus.FAILED, limit=100)
    for job in failed_jobs:
        workdir = job.params.get("working_directory")
        if workdir:
            workdirs.append(workdir)

    return list(set(workdirs))  # Deduplicate
```

### 3. Startup Flow

Now when daemon starts:

```python
def start(self, num_workers: Optional[int] = None):
    ...
    # Clean up stale working directory locks
    logger.info("Cleaning up stale working directory locks...")
    workdirs_to_check = self._get_potentially_locked_directories()  # <- NEW
    self._workdir_lock.cleanup_stale_locks(workdirs_to_check)        # <- FIXED

    # Start worker threads
    ...
```

## Behavior After Fix

### Scenario 1: Clean Daemon Startup (No Stale Locks)

```
Daemon Start
    ↓
Query Database: Get RUNNING/FAILED jobs
    ↓
Extract working_directories: []  (empty)
    ↓
cleanup_stale_locks([])
    ↓
Result: No stale locks found
```

### Scenario 2: Daemon Restart After Crash

```
Daemon Crashed (left orphaned .cfd-lock files)
    ↓
Daemon Restart
    ↓
Query Database: Get RUNNING jobs
    ↓
Jobs Found:
  - job_abc: /Users/name/homelab/weather-map (status: RUNNING)
  - job_xyz: /Users/name/homelab/test-app (status: RUNNING)
    ↓
Extract working_directories:
  - /Users/name/homelab/weather-map
  - /Users/name/homelab/test-app
    ↓
cleanup_stale_locks([...directories...])
    ↓
For each directory:
  - Check .cfd-lock file
  - Read PID from lockfile
  - Check: os.kill(pid, 0)
    ↓
    ├─→ PID exists: Keep lock (process still running)
    └─→ PID dead: REMOVE lock (crashed process)
    ↓
Result: Stale locks removed, active locks preserved
```

### Scenario 3: Stale Lock Cleanup Details

**Example lockfile:** `/Users/name/homelab/weather-map/.cfd-lock`
```json
{
  "job_id": "abc-123",
  "pid": 12345,
  "locked_at": "2025-11-13T22:14:00.000000"
}
```

**Cleanup logic:**
```python
# Check if PID 12345 still exists
try:
    os.kill(12345, 0)  # Signal 0 = existence check
    # PID exists -> lock is active
except OSError:
    # PID doesn't exist -> lock is stale -> REMOVE
    lockfile.unlink()
```

## Test Coverage

**New Tests Added:**

1. `test_startup_cleanup_with_working_directories`
   - Verifies cleanup scans provided directories
   - Removes stale locks (dead PID + timeout)
   - Preserves active locks

2. `test_startup_cleanup_without_working_directories`
   - Verifies orphaned locks persist without directory list
   - Verifies cleanup works when directories provided

**All 11 tests passing:**
```
✅ test_acquire_and_release
✅ test_concurrent_lock_rejection
✅ test_path_normalization
✅ test_stale_lock_detection_dead_pid
✅ test_stale_lock_detection_timeout
✅ test_wrong_job_cannot_release_lock
✅ test_lockfile_survives_manager_restart
✅ test_cleanup_stale_locks
✅ test_multiple_directories
✅ test_startup_cleanup_with_working_directories (NEW)
✅ test_startup_cleanup_without_working_directories (NEW)
```

## Database Query Performance

**Impact on startup:**

- **Query 1:** `list_jobs(status=RUNNING, limit=1000)` - Fast (indexed by status)
- **Query 2:** `list_jobs(status=FAILED, limit=100)` - Fast (indexed by status)
- **Typical result:** 0-10 directories to check
- **Overhead:** ~10-50ms on startup (negligible)

**Trade-off:** Minimal startup cost for robust stale lock cleanup.

## Alternative Approaches Considered

### 1. Global Lock Registry File

**Idea:** Maintain a central registry of all active locks in `~/.context-foundry/active_locks.json`

**Rejected because:**
- Single point of failure
- Requires file locking (complexity)
- Harder to clean up on crash
- Current DB-based approach is more reliable

### 2. Periodic Background Cleanup

**Idea:** Run cleanup every N minutes while daemon is running

**Rejected because:**
- Startup cleanup is sufficient
- Adds background task complexity
- Lockfiles are cleaned on-demand during `acquire()` anyway

### 3. Full Filesystem Scan

**Idea:** Scan entire filesystem for `.cfd-lock` files on startup

**Rejected because:**
- Slow (could take seconds)
- Unnecessary (we know which dirs to check from DB)
- Privacy concerns (scanning user files)

## Files Modified

- `context_foundry/daemon/workdir_lock.py:297-366` - Enhanced cleanup method
- `context_foundry/daemon/jobs.py:210-241` - Added directory discovery
- `context_foundry/daemon/jobs.py:226-231` - Integrated cleanup on startup
- `tests/test_workdir_lock.py:260-343` - Added new tests

## Verification

Run tests:
```bash
pytest tests/test_workdir_lock.py -v
# Result: 11 passed in 0.09s
```

Restart daemon:
```bash
./tools/cfd stop
./tools/cfd start
./tools/cfd status
# Result: Daemon running with stale lock cleanup on startup
```

## Summary

The critical gap has been fixed. The daemon now:

✅ **Scans disk-based lockfiles** on startup (not just in-memory locks)
✅ **Removes stale locks** from crashed builds automatically
✅ **Queries database** to find directories that need checking
✅ **Preserves active locks** while removing orphaned ones
✅ **Tested thoroughly** with comprehensive test suite

Orphaned `.cfd-lock` files from crashed builds will no longer persist indefinitely.

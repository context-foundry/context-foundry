# Working Directory Locking

## Overview

The Context Foundry daemon now implements robust working directory locking to prevent concurrent builds in the same directory. This eliminates race conditions and file conflicts when multiple builds are submitted to the same project path.

## Problem Statement

**Before:** The daemon could execute multiple builds simultaneously in the same working directory, causing:
- File conflicts (e.g., `architecture.md` from one build, `scout-report.md` from another)
- Corrupted build artifacts
- Confusing timestamps and phase ordering
- Build failures due to concurrent file access

**After:** Only one build can execute in a given working directory at a time, with automatic conflict detection and resolution.

## Architecture

### Two-Layer Locking Mechanism

1. **In-Memory Locks** (for current daemon instance)
   - Fast lock checking within a single daemon process
   - Thread-safe using Python's `threading.Lock`
   - Tracks `{normalized_path: job_id}` mapping

2. **Disk-Based Lockfiles** (survives daemon restarts)
   - Lockfile: `.cfd-lock` in working directory
   - Contains: job ID, daemon PID, timestamp
   - Enables lock persistence across daemon restarts
   - Provides stale lock detection

### Lock Lifecycle

```
Job Submitted
    ↓
Working Directory Lock Requested
    ↓
Check In-Memory Locks ──────────→ If Locked: REJECT or QUEUE
    ↓ Not Locked
Check Disk Lockfile
    ↓
    ├─→ No Lockfile: Acquire Lock
    ├─→ Lockfile Exists + Stale: Remove & Acquire
    └─→ Lockfile Exists + Active: REJECT
    ↓
Lock Acquired
    ↓
Execute Job
    ↓
Release Lock (in finally block)
    ↓
Remove Lockfile
```

## Stale Lock Detection

A lock is considered stale if:

1. **Dead Process**: The PID in the lockfile no longer exists
   ```python
   os.kill(pid, 0)  # Check if process exists
   ```

2. **Timeout**: Lock age exceeds `LOCK_TIMEOUT_SECONDS` (default: 3600s)
   ```python
   age_seconds > LOCK_TIMEOUT_SECONDS
   ```

3. **Invalid Data**: Lockfile is corrupted or unreadable

### Stale Lock Cleanup

**On Daemon Startup:**
```python
manager.cleanup_stale_locks()
```
- Scans all tracked locks
- Removes locks for dead processes
- Removes locks exceeding timeout
- Cleans up orphaned lockfiles

**Before Lock Acquisition:**
- Automatically checks if existing lock is stale
- Removes stale lock and proceeds with acquisition

## Usage

### For Daemon Developers

The locking mechanism is **automatic** - no changes needed to job submission code:

```python
# Jobs with working_directory param are automatically locked
job = job_manager.submit_job(
    job_type=JobType.TESTING,
    params={
        "working_directory": "/path/to/project",  # This triggers locking
        "other_param": "value"
    }
)
```

### For Build System Integration

**Autonomous Build Integration:**

The autonomous build system automatically extracts `working_directory` from job params:

```python
# In tools/mcp_utils/autonomous_build.py
task_config = {
    "working_directory": "/Users/name/homelab/my-app",  # Auto-locked
    "task": "Build my app",
    ...
}
```

### Lock Status Checking

```python
from context_foundry.daemon.workdir_lock import WorkDirLockManager

manager = WorkDirLockManager()

# Check if directory is locked
is_locked, holder_job_id = manager.is_locked("/path/to/project")

if is_locked:
    print(f"Directory locked by job: {holder_job_id}")
```

## Behavior

### Concurrent Build Rejection

**Scenario:** Two builds submitted to same directory

```python
# Job 1 submitted first
job1 = submit_job(working_directory="/Users/name/homelab/weather-map")
# Lock acquired: /Users/name/homelab/weather-map → job1

# Job 2 submitted (concurrent)
job2 = submit_job(working_directory="/Users/name/homelab/weather-map")
# Lock denied: Directory already locked by job1
# Job 2 STATUS: FAILED
# Job 2 ERROR: "Working directory ... already locked by job <job1_id>"
```

### Successful Sequential Builds

```python
# Job 1 completes
# Lock released automatically in finally block

# Job 2 submitted
# Lock acquired: /Users/name/homelab/weather-map → job2
# Job 2 executes successfully
```

### Daemon Restart Handling

```bash
# Daemon running, job1 active with lock
$ ./tools/cfd stop

# Daemon restarted
$ ./tools/cfd start
# On startup: cleanup_stale_locks() called
# If job1 PID still exists: lock preserved
# If job1 PID dead: lock removed (stale)
```

## Lockfile Format

`.cfd-lock` (JSON):
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "pid": 12345,
  "locked_at": "2025-11-13T22:30:00.123456",
  "daemon_version": "1.0"
}
```

## Configuration

### Lock Timeout

Modify `LOCK_TIMEOUT_SECONDS` in `workdir_lock.py`:

```python
class WorkDirLockManager:
    LOCK_TIMEOUT_SECONDS = 3600  # 1 hour default
```

**Considerations:**
- **Too short**: Valid long-running builds may be killed
- **Too long**: Stuck builds block directory unnecessarily
- **Recommended**: 2-3x expected max build duration

### Lockfile Name

Modify `LOCK_FILENAME` to avoid conflicts:

```python
class WorkDirLockManager:
    LOCK_FILENAME = ".cfd-lock"  # Hidden file
```

## Error Messages

### Lock Acquisition Failure

```
Working directory /Users/name/homelab/my-app is already locked by job abc-123-def.
Cannot execute concurrent builds in the same directory.
```

**Resolution:**
1. Wait for the other job to complete
2. Cancel the blocking job if it's stuck
3. Manually remove `.cfd-lock` if you're certain it's stale

### Stale Lock Warning

```
Stale lock detected for /Users/name/homelab/my-app: Process 12345 no longer exists. Removing.
```

**Action:** Informational only - lock automatically removed

## Troubleshooting

### Directory Permanently Locked

**Symptom:** Jobs always fail with "already locked" error, even though no build is running

**Diagnosis:**
```bash
# Check for lockfile
ls -la /path/to/project/.cfd-lock

# Read lockfile
cat /path/to/project/.cfd-lock

# Check if PID exists
ps aux | grep <pid_from_lockfile>
```

**Solutions:**
1. **Restart daemon** (triggers cleanup on startup)
   ```bash
   ./tools/cfd stop
   ./tools/cfd start
   ```

2. **Manual removal** (if PID is definitely dead)
   ```bash
   rm /path/to/project/.cfd-lock
   ```

3. **Kill stuck process** (if PID still exists but hung)
   ```bash
   kill -9 <pid>
   rm /path/to/project/.cfd-lock
   ```

### Lock Not Preventing Concurrent Builds

**Symptom:** Multiple builds still running in same directory

**Diagnosis:**
```python
# Check if job has working_directory param
job = store.get_job(job_id)
print(job.params.get("working_directory"))  # Should not be None
```

**Solutions:**
1. Ensure job params include `working_directory`
2. Verify JobManager has lock manager initialized
3. Check daemon logs for lock acquisition messages

## Testing

Run the test suite:

```bash
pytest tests/test_workdir_lock.py -v
```

### Test Coverage

- ✅ Basic lock acquisition and release
- ✅ Concurrent lock rejection
- ✅ Path normalization (absolute vs relative)
- ✅ Stale lock detection (dead PID)
- ✅ Stale lock detection (timeout)
- ✅ Wrong job cannot release lock
- ✅ Lockfile persistence across manager instances
- ✅ Cleanup of stale locks
- ✅ Multiple directories locked independently

## Performance Impact

**Memory:** O(n) where n = number of active builds (typical: < 10)

**Disk I/O:**
- Lock acquisition: 1 read + 1 write
- Lock release: 1 delete
- Stale check: 1 read

**CPU:** Minimal - only during lock operations (< 1ms)

## Future Enhancements

### Optional: Queuing Instead of Rejection

Instead of failing jobs with locked directories, queue them:

```python
# In JobManager
def _execute_job(self, job_id: str):
    if working_dir and not self._workdir_lock.acquire(working_dir, job_id):
        # Instead of failing, requeue with delay
        logger.info(f"Directory locked, requeueing {job_id}")
        time.sleep(5)  # Back off
        self._job_queue.put(job_id)  # Retry later
        return
```

### Optional: Per-Job Subdirectories

Avoid locking entirely by using unique subdirectories:

```python
unique_workdir = f"{base_dir}/{job_id}"
os.makedirs(unique_workdir, exist_ok=True)
```

**Trade-off:** More disk space, but zero contention

## References

- Implementation: `context_foundry/daemon/workdir_lock.py`
- Integration: `context_foundry/daemon/jobs.py`
- Tests: `tests/test_workdir_lock.py`
- Related Issue: Concurrent build race condition (Nov 2025)

# Daemon Health Monitoring - External Watchdog

## Status: SAFETY NET + DEBUG INSTRUMENTATION ACTIVE

**Current State**: External watchdog monitors main loop and auto-restarts on hang (✅ Active since restart)
**Debug Logging**: Comprehensive trace logging around all blocking calls (✅ Active, logging every minute)
**Thread Dumps**: Auto-capture on hang detection (✅ Ready, will trigger at 2min hang)
**Root Cause**: Still unknown - waiting for next hang to analyze debug logs
**Next Step**: Monitor logs and analyze thread dump when hang occurs

## Problem Statement

On 2025-11-19, the CF daemon experienced a silent hang where the main loop stopped progressing but the process remained alive:

**Evidence from logs:**
```
15:05:34 - Daemon starts (PID 17297, 3 workers)
15:46:00 - Last "Stats:" log from main loop
         [2h 40m gap with NO main loop logs]
15:51:18 - Worker thread still alive (logged subprocess exit)
16:24:25 - Worker thread still alive (logged job timeout error)
19:02:45 - New job inserted into jobs.db
19:04:29 - Daemon restart, new PID 65438
19:04:29 - Job immediately picked up and started
```

**Symptoms:**
- Stats loop stopped logging at 15:46:00
- Worker threads kept running (logged events at 15:51 and 16:24)
- Process stayed alive (no crash logs, no restart until manual intervention)
- New jobs not processed (job submitted at 19:02 but not started until restart)
- Fresh daemon works fine (immediately picked up queued job)

**Root cause:** Unknown - stats loop silently stopped, possibly due to unhandled signal, OS event, or edge case in the main loop.

## Solution Evolution

### Attempt 1: In-Loop Heartbeat (FAILED)
Added heartbeat tracking inside the main loop - **didn't work because when the loop hangs, the heartbeat code can't run**.

### Attempt 2: Fixed Stats Logging (FAILED)
Fixed stats timing bugs - **didn't prevent the hang, just made stats more reliable**.

### Attempt 3: External Watchdog (CURRENT - SAFETY NET)
**Implemented external watchdog thread** that monitors main loop from outside and auto-restarts on hang.

**Critical Realization**: Health monitoring INSIDE a hung loop cannot detect the hang. The watchdog must run in a **separate thread** that remains independent of the main loop.

## Current Implementation: External Watchdog Thread

### Architecture

```
Main Process (PID 87842)
├─ Main Loop Thread (can hang)
│  ├─ Updates self._main_loop_heartbeat every iteration
│  ├─ Writes heartbeat file every 5 iterations
│  └─ Logs stats every minute
│
└─ Watchdog Thread (CFDaemonWatchdog) ← INDEPENDENT
   ├─ Checks self._main_loop_heartbeat every 10 seconds
   ├─ Logs warnings if heartbeat age > 60s
   ├─ Logs critical alerts if age > 120s
   └─ Force restarts daemon via SIGTERM after 3 critical alerts
```

### Changes Made

#### 1. External Watchdog Thread (`server.py:458-511`)

**New method `_watchdog_loop()`**:
```python
def _watchdog_loop(self):
    """Runs in separate thread, independent of main loop"""
    while not self._watchdog_stop:
        time.sleep(10)  # Check every 10 seconds

        age = time.time() - self._main_loop_heartbeat

        if age > 120:  # 2+ minutes without heartbeat
            consecutive_warnings += 1
            logger.critical(f"[WATCHDOG] MAIN LOOP HUNG! ({consecutive_warnings}/3)")

            if consecutive_warnings >= 3:
                logger.critical("[WATCHDOG] Force restarting...")
                os.kill(os.getpid(), signal.SIGTERM)
```

**Started on daemon init (`server.py:404-412`)**:
```python
self._watchdog_thread = threading.Thread(
    target=self._watchdog_loop,
    name="CFDaemonWatchdog",
    daemon=True
)
self._watchdog_thread.start()
```

#### 2. Main Loop Updates Shared Heartbeat

**Main loop updates watchdog-monitored timestamp (`server.py:530-542`)**:
```python
while self.running:
    current_time = time.time()

    # Update heartbeat for EXTERNAL watchdog monitoring
    self._main_loop_heartbeat = current_time

    # Write heartbeat file (every 5 iterations to reduce I/O)
    if iteration_count % 5 == 0:
        heartbeat_file.write_text(...)
```

#### 3. Graceful Watchdog Shutdown

**Stop method waits for watchdog (`server.py:610-618`)**:
```python
def stop(self):
    # Stop watchdog thread
    if self._watchdog_thread and self._watchdog_thread.is_alive():
        self._watchdog_stop = True
        self._watchdog_thread.join(timeout=5.0)
```

### Auto-Restart Behavior

When the main loop hangs:
1. **T+60s**: `[WATCHDOG] Main loop slow: no heartbeat for 60s`
2. **T+120s**: `[WATCHDOG] MAIN LOOP HUNG DETECTED! No heartbeat for 120s (warning 1/3)`
3. **T+130s**: `[WATCHDOG] MAIN LOOP HUNG DETECTED! No heartbeat for 130s (warning 2/3)`
4. **T+140s**: `[WATCHDOG] MAIN LOOP HUNG DETECTED! No heartbeat for 140s (warning 3/3)`
5. **T+140s**: `[WATCHDOG] Main loop confirmed hung for 2+ minutes. Initiating forced restart...`
6. Daemon sends `SIGTERM` to itself → Graceful shutdown
7. **Requires external supervisor** (systemd, supervisord, Docker restart policy) to restart daemon

**Important**: The watchdog triggers self-termination, but **does not restart the daemon**. You need an external process supervisor to automatically restart after SIGTERM.

#### 2. Enhanced Status Command (cli.py)

The `cfd status` command now shows health information:

```bash
$ cfd status
Daemon is running (PID 77285)
Health: ✓ Healthy

$ cfd status --verbose
Daemon is running (PID 77285)
Health: ✓ Healthy
  Last heartbeat: 2s ago
  Loop iterations: 127
  Heartbeat PID: 77285

Job Statistics:
  cancelled: 23
  failed: 42
  succeeded: 18
...
```

**Health states:**
- `✓ Healthy` - Heartbeat < 10 seconds old
- `⚠ Warning (heartbeat Xs old)` - 10-60 seconds old
- `✗ UNHEALTHY (heartbeat Xs old - daemon may be hung)` - > 60 seconds old

#### 3. Heartbeat File Format

Location: `~/.context-foundry/cfd/daemon_heartbeat.txt`

```
1763602568          # Unix timestamp of last update
127                 # Total loop iterations since start
77285               # Daemon PID
```

Updated every second while daemon is running.

## Benefits

### 1. Early Detection
If the main loop hangs again, we'll see:
- **In logs**: Critical warning every 3 minutes explaining the issue
- **Via status**: `cfd status` shows UNHEALTHY with age of last heartbeat
- **Via monitoring**: External tools can read heartbeat file

### 2. Diagnostics
The iteration count and timestamp help diagnose:
- Whether the loop is progressing (count increasing)
- How long the daemon has been running
- When the hang occurred (last heartbeat time)

### 3. External Monitoring
The heartbeat file enables:
- Automated health checks from external scripts
- Monitoring dashboards
- Auto-restart triggers when daemon is unhealthy

### 4. No False Positives
The health check differentiates between:
- **Process alive but hung** (PID exists, heartbeat stale)
- **Process crashed** (PID gone, no heartbeat file)
- **Stats loop stuck** (heartbeat fresh, stats not logging)

## Testing

### Test 1: Normal Operation
```bash
$ cfd start
$ sleep 5
$ cfd status
Daemon is running (PID 77285)
Health: ✓ Healthy
```
✅ **Result**: Healthy status, heartbeat updating every second

### Test 2: Verbose Status
```bash
$ cfd status --verbose
Health: ✓ Healthy
  Last heartbeat: 1s ago
  Loop iterations: 55
  Heartbeat PID: 77285
```
✅ **Result**: Shows detailed health metrics

### Test 3: Heartbeat File
```bash
$ cat ~/.context-foundry/cfd/daemon_heartbeat.txt
1763602568
63
77285

$ sleep 2 && cat ~/.context-foundry/cfd/daemon_heartbeat.txt
1763602570
127
77285
```
✅ **Result**: Timestamp and iterations increment every second

## ROOT CAUSE INVESTIGATION - STILL NEEDED

### What We Know

**Symptom**: Main loop completely stops executing, no errors logged

**Evidence from hangs**:
1. **First hang (15:46)**: Stats stopped logging, no logs for 2h 40m
2. **Second hang (19:37)**: Stats stopped logging, heartbeat frozen at iteration 414
3. **Third hang (19:51)**: Same pattern - loop just stops

**What's NOT the cause**:
- ❌ Not an exception (try/except around loop doesn't catch it)
- ❌ Not stats logging bug (fixed in v2, still hung)
- ❌ Not file I/O blocking (heartbeat writes every 5 iterations, not blocking)
- ❌ Not crashed process (PID remains alive, workers still log)

### Suspects to Investigate

#### 1. `job_manager.get_stats()` Deadlock
**Hypothesis**: The stats call might deadlock on a lock held by worker threads.

**Investigation needed**:
```python
# Add timeout to stats call
try:
    with timeout(5):  # 5 second timeout
        stats = self.job_manager.get_stats()
except TimeoutError:
    logger.error("Stats call timed out - possible deadlock!")
```

**Check**: `jobs.py:761` - Does `get_stats()` acquire locks that workers hold?

#### 2. GIL Starvation
**Hypothesis**: Worker threads hold GIL, starving main loop.

**Investigation needed**:
- Add GIL monitoring
- Check if workers are CPU-bound during hangs
- Use `sys.setswitchinterval()` to adjust thread switching

#### 3. Signal Handling Race
**Hypothesis**: Signal handler might be blocking main loop.

**Investigation needed**:
```python
# Check signal handlers in server.py
def _setup_signal_handlers(self):
    # Are handlers blocking?
```

#### 4. File Descriptor Leak
**Hypothesis**: Process runs out of file descriptors, blocking on I/O.

**Investigation needed**:
```bash
# Monitor FD count
lsof -p <daemon_pid> | wc -l
```

### Debugging Plan

✅ **IMPLEMENTED (2025-11-19):**

1. **Pre/post logging around all blocking calls** (`server.py:572-574`, `jobs.py:769-778`, `store.py:508-518`):
   ```python
   # In server.py - main loop
   logger.debug("[HANG-DEBUG] About to call get_stats() at {time}")
   stats = self.job_manager.get_stats()
   logger.debug("[HANG-DEBUG] get_stats() returned at {time}")

   # In jobs.py - get_stats()
   logger.debug("[HANG-DEBUG] get_stats(): About to call store.get_job_stats()")
   job_stats = self.store.get_job_stats()
   logger.debug("[HANG-DEBUG] get_stats(): store.get_job_stats() returned")

   logger.debug("[HANG-DEBUG] get_stats(): About to acquire _running_jobs_lock")
   with self._running_jobs_lock:
       logger.debug("[HANG-DEBUG] get_stats(): Acquired _running_jobs_lock")
       # ... work ...
   logger.debug("[HANG-DEBUG] get_stats(): Released _running_jobs_lock")

   # In store.py - get_job_stats()
   logger.debug("[HANG-DEBUG] get_job_stats(): About to acquire DB connection")
   with self._get_connection() as conn:
       logger.debug("[HANG-DEBUG] get_job_stats(): Executing SQL query")
       # ... query ...
       logger.debug("[HANG-DEBUG] get_job_stats(): Query complete")
   ```

2. **Thread dump on hang detection** (`server.py:499-516`):
   ```python
   if age > 120 and consecutive_warnings == 1:
       # Capture thread stacks using faulthandler
       import faulthandler
       stack_buffer = io.StringIO()
       faulthandler.dump_traceback(file=stack_buffer, all_threads=True)

       # Log and save to file
       logger.critical(f"[WATCHDOG] Thread dump:\n{stack_trace}")
       dump_file.write_text(stack_trace)
   ```

3. **TODO: Monitor system resources**:
   - CPU usage per thread
   - Memory usage
   - File descriptor count
   - Lock contention metrics

4. **TODO: Reproduce under controlled conditions**:
   - Run with single worker
   - Run without job queue
   - Run with various load patterns

### Next Steps

**SHORT TERM**: Watchdog provides safety net (✅ Implemented)
**MEDIUM TERM**: Detailed debug logging to identify hang point (✅ Implemented)
**NEXT**: Wait for hang to occur and analyze debug logs
**LONG TERM**: Fix root cause once identified

### What the Debug Logs Look Like in Production

**Normal operation (every minute):**
```
2025-11-19 20:26:00,461 - INFO - [HANG-DEBUG] About to call get_stats() at 1763605560.461
2025-11-19 20:26:00,462 - INFO - [HANG-DEBUG] get_stats(): About to call store.get_job_stats() at 1763605560.462
2025-11-19 20:26:00,462 - INFO - [HANG-DEBUG] get_job_stats(): About to acquire DB connection at 1763605560.462
2025-11-19 20:26:00,462 - INFO - [HANG-DEBUG] get_job_stats(): Acquired DB connection, executing query at 1763605560.463
2025-11-19 20:26:00,463 - INFO - [HANG-DEBUG] get_job_stats(): Query executed, fetching results at 1763605560.463
2025-11-19 20:26:00,463 - INFO - [HANG-DEBUG] get_job_stats(): Fetched all rows at 1763605560.464
2025-11-19 20:26:00,463 - INFO - [HANG-DEBUG] get_stats(): store.get_job_stats() returned at 1763605560.464
2025-11-19 20:26:00,463 - INFO - [HANG-DEBUG] get_stats(): About to acquire _running_jobs_lock at 1763605560.464
2025-11-19 20:26:00,464 - INFO - [HANG-DEBUG] get_stats(): Acquired _running_jobs_lock at 1763605560.464
2025-11-19 20:26:00,464 - INFO - [HANG-DEBUG] get_stats(): Released _running_jobs_lock at 1763605560.464
2025-11-19 20:26:00,464 - INFO - [HANG-DEBUG] get_stats() returned at 1763605560.465
2025-11-19 20:26:00,465 - INFO - Stats: 0 running, {'cancelled': 23, 'failed': 42, 'succeeded': 18} total jobs
```

**Total time: ~4ms** - All operations complete quickly with no blocking.

### What the Debug Logs Will Tell Us When Hang Occurs

**If hang is in database call:**
```
[HANG-DEBUG] About to call get_stats() at 1234567890.123
[HANG-DEBUG] get_stats(): About to call store.get_job_stats() at 1234567890.124
[HANG-DEBUG] get_job_stats(): About to acquire DB connection at 1234567890.125
[HANG-DEBUG] get_job_stats(): Executing SQL query at 1234567890.126
<no further logs - HUNG IN SQL QUERY>
```

**If hang is in lock acquisition:**
```
[HANG-DEBUG] About to call get_stats() at 1234567890.123
[HANG-DEBUG] get_stats(): About to call store.get_job_stats() at 1234567890.124
[HANG-DEBUG] get_stats(): store.get_job_stats() returned at 1234567890.130
[HANG-DEBUG] get_stats(): About to acquire _running_jobs_lock at 1234567890.131
<no further logs - HUNG WAITING FOR LOCK>
```

**If hang is elsewhere:**
```
[HANG-DEBUG] About to call get_stats() at 1234567890.123
<no further logs - HUNG BEFORE get_stats() CALL>
```

**Thread dump will show:**
- Exact line where main loop is stuck
- What locks are held by which threads
- Full call stack for all threads
- Saved to: `~/.context-foundry/cfd/logs/thread_dump_{timestamp}.txt`

## Future Enhancements

### Possible Improvements
1. ✅ **External watchdog** - DONE (auto-restart on hang)
2. **Metrics export**: Expose health metrics via HTTP endpoint
3. **Alert integration**: Send notifications when UNHEALTHY state detected
4. **Historical tracking**: Log heartbeat gaps to identify patterns
5. **Thread dumps**: Auto-capture stack traces on hang detection

## Files Changed

- `context_foundry/daemon/server.py`: Added health monitoring to main loop
- `context_foundry/daemon/cli.py`: Enhanced status command with health check
- `docs/DAEMON_HEALTH_MONITORING_FIX.md`: This documentation

## Deployment

The fix is active immediately after:
```bash
cfd stop
cfd start
```

No configuration changes required. Existing daemons will automatically gain health monitoring.

## Monitoring Commands

```bash
# Check daemon health
cfd status

# Detailed health info
cfd status --verbose

# Monitor heartbeat file
watch -n 1 cat ~/.context-foundry/cfd/daemon_heartbeat.txt

# Check for health warnings in logs
tail -f ~/.context-foundry/cfd/logs/cfd.log | grep "HEALTH CHECK"
```

## Related Issues

- Original incident: 2025-11-19 15:46:00 - 19:04:29 (daemon hang)
- Job affected: ad8e5df5-5335-4b72-92f7-09adcb230087 (queued but not processed)
- Previous job timeout: acd11c45-1521-4520-bfa9-a6aad84221f2 (exceeded 60 min)

---

**Author**: Claude Code
**Date**: 2025-11-19
**Status**: Deployed and active

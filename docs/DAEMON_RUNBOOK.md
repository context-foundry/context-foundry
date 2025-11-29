# CF Daemon Operator Runbook

This runbook provides operational guidance for the Context Foundry Daemon (cfd).

## Quick Reference

| Command | Description |
|---------|-------------|
| `cfd status` | Check daemon health and job counts |
| `cfd list` | List recent jobs with status |
| `cfd logs <job_id>` | View logs for specific job |
| `cfd logs --follow` | Stream live logs |
| `cfd timeline <job_id>` | View job event timeline |
| `cfd gates <job_id>` | Check phase gate status |
| `cfd tree <job_id>` | View job tree (phases + tasks hierarchy) |
| `cfd stop` | Stop daemon gracefully |
| `cfd start` | Start daemon in background |

## How to Check Job Status

### 1. Check Overall Daemon Health

```bash
cfd status
```

Expected healthy output:
```
CF Daemon Status
  Running: Yes
  PID: 12345
  Uptime: 2h 15m
  Jobs: 2 running, 5 queued, 123 total
  Workers: 2/2 active
```

### 2. List Jobs by Status

```bash
# List all recent jobs
cfd list

# Filter by status
cfd list --status running
cfd list --status queued
cfd list --status failed
cfd list --status stalled
```

### 3. Get Job Details

```bash
# View job timeline (all events)
cfd timeline <job_id>

# View gate status (phase progression)
cfd gates <job_id>

# View phase summary
cfd phase-summary <job_id>

# View recent events across all jobs
cfd events --limit 50
```

### 4. Reconstruct Job State (Debug)

For debugging, reconstruct the complete state from events:

```bash
cfd reconstruct <job_id>
```

This replays all events and shows the computed state.

### 5. View Job Tree

Show a hierarchical view of phases and tasks:

```bash
# ASCII tree view
cfd tree <job_id>

# JSON format
cfd tree <job_id> --json
```

Example output:
```
Job e0fc0679 (RUNNING)
+-- Phase: Scout (SUCCEEDED)
|   +-- Task b916d083 (SUCCEEDED)
+-- Phase: Architect (SUCCEEDED)
|   +-- Task c7d8e9f0 (SUCCEEDED)
+-- Phase: Builder (RUNNING)
|   +-- Task a1b2c3d4 (RUNNING)
+-- Phase: Test (PENDING)
+-- Phase: Feedback (PENDING)
```

---

## HTTP/JSON Status API

The daemon provides a REST API for programmatic access to job status, timelines, and metrics.

### API Base URL

```
http://127.0.0.1:8421
```

Default port is 8421. Configure via `CFD_HTTP_API_PORT` environment variable.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with uptime and job counts |
| `GET /jobs` | List jobs (supports `?status=`, `?limit=`, `?offset=`) |
| `GET /jobs/{job_id}` | Get job details with phase summary |
| `GET /jobs/{job_id}/timeline` | Get event timeline |
| `GET /jobs/{job_id}/gates` | Get gate status report |
| `GET /jobs/{job_id}/tree` | Get job tree (phases + tasks hierarchy) |
| `GET /events/recent` | Recent events across all jobs |
| `GET /metrics` | Metrics snapshot |

### Sample curl Commands

```bash
# Health check
curl http://localhost:8421/health

# List running jobs
curl "http://localhost:8421/jobs?status=running&limit=10"

# Get job details
curl http://localhost:8421/jobs/<job_id>

# Get job timeline
curl http://localhost:8421/jobs/<job_id>/timeline

# Get gate status
curl http://localhost:8421/jobs/<job_id>/gates

# Get job tree (hierarchical view)
curl http://localhost:8421/jobs/<job_id>/tree

# Get recent events
curl "http://localhost:8421/events/recent?limit=50"

# Get metrics
curl http://localhost:8421/metrics
```

### Job Tree JSON Structure

The `/jobs/{job_id}/tree` endpoint returns:

```json
{
  "job_id": "e0fc0679-1234-5678-90ab-cdef01234567",
  "status": "running",
  "created_at": "2024-01-15T10:30:00",
  "started_at": "2024-01-15T10:30:05",
  "completed_at": null,
  "phases": [
    {
      "phase": "Scout",
      "status": "succeeded",
      "sequence": 0,
      "tasks": [
        {
          "task_id": "b916d083-...",
          "status": "succeeded",
          "created_at": "2024-01-15T10:30:05",
          "started_at": "2024-01-15T10:30:06",
          "completed_at": "2024-01-15T10:32:15",
          "last_heartbeat": "2024-01-15T10:32:15"
        }
      ]
    },
    {
      "phase": "Builder",
      "status": "running",
      "sequence": 2,
      "tasks": [
        {
          "task_id": "a1b2c3d4-...",
          "status": "running",
          "created_at": "2024-01-15T10:35:00",
          "started_at": "2024-01-15T10:35:01",
          "completed_at": null,
          "last_heartbeat": "2024-01-15T10:40:30"
        }
      ]
    }
  ]
}
```

### API Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CFD_ENABLE_HTTP_API` | `true` | Enable/disable HTTP API |
| `CFD_HTTP_API_HOST` | `127.0.0.1` | Bind address |
| `CFD_HTTP_API_PORT` | `8421` | Port number |

---

## What to Do If a Job is STALLED

A job enters STALLED status when:
- No heartbeat received for 10 minutes
- No task activity detected

### Diagnosis Steps

1. **Check what phase the job was in:**
   ```bash
   cfd gates <job_id>
   cfd timeline <job_id>
   ```

2. **Look for errors in logs:**
   ```bash
   cfd logs <job_id> | grep -i error
   cfd logs <job_id> | grep -i timeout
   ```

3. **Check system resources:**
   ```bash
   # CPU and memory
   top -l 1 | head -20

   # Disk space
   df -h
   ```

### Recovery Options

#### Option A: Resume the Job
If the issue was transient (network, resource exhaustion):
```bash
cfd resume <job_id>
```
This transitions STALLED -> RUNNING and retries.

#### Option B: Cancel and Restart
If the job data may be corrupted:
```bash
cfd cancel <job_id> --reason "Stalled, manual cancel"

# Submit a new job
cfd submit --task "<original task>" --working-dir /path/to/project
```

#### Option C: Investigate Root Cause
Check daemon logs for patterns:
```bash
tail -500 ~/.context-foundry/logs/cfd.log | grep -E "(stall|timeout|heartbeat)"
```

---

## Common Failure Patterns

### 1. Phase Timeout

**Symptoms:**
- Task status shows `timed_out`
- Logs show "Task exceeded timeout"

**Causes:**
- LLM API slowness
- Large codebase (Scout phase)
- Complex builds (Builder phase)

**Resolution:**
- Increase timeout in job params: `--timeout-minutes 120`
- Check API status at status.anthropic.com
- For large repos, consider incremental builds

### 2. Zombie Tasks

**Symptoms:**
- Task stuck in `running` but no log updates
- No heartbeats in timeline
- Watchdog should auto-detect after 5 minutes

**Resolution:**
The task watchdog will automatically:
1. Detect stale heartbeats (>5 min)
2. Mark task as `timed_out`
3. Mark job as `failed` or `stalled`

If watchdog misses it:
```bash
cfd cancel <job_id> --reason "Zombie task"
```

### 3. Database Lock Contention

**Symptoms:**
- Logs show "database is locked"
- Multiple workers contending
- Slow job submissions

**Resolution:**
The daemon uses WAL mode to handle this. If persistent:
```bash
# Stop daemon
cfd stop

# Checkpoint the database
sqlite3 ~/.context-foundry/daemon.db "PRAGMA wal_checkpoint(TRUNCATE);"

# Restart
cfd start
```

### 4. Worker Exhaustion

**Symptoms:**
- Jobs stuck in `queued` for too long
- All workers busy with slow jobs

**Resolution:**
```bash
# Check worker status
cfd status

# If needed, increase workers (requires config edit + restart)
# Edit ~/.context-foundry/config.yaml
# max_concurrent_jobs: 4
cfd stop && cfd start
```

### 5. Out of Memory / Context Window

**Symptoms:**
- Phase fails with context_percent > 95%
- LLM returns truncated responses
- Logs show "context window exceeded"

**Resolution:**
- Use incremental mode: `--incremental`
- Reduce Scout scope with .cfignore
- Split large tasks into smaller builds

---

## Where Logs Live

### Log Files

| Log File | Purpose | Location |
|----------|---------|----------|
| Main daemon log | All daemon events | `~/.context-foundry/logs/cfd.log` |
| Job output | Per-job conversation | `~/.context-foundry/conversations/conversation-<job_id>.log` |
| Thread dump | Captured on hangs | `~/.context-foundry/logs/thread_dump_<timestamp>.txt` |
| Build output | Full build stdout | `.context-foundry/build-output-<task_id>.txt` |

### Structured Logs

The daemon emits JSON-structured logs for machine parsing. Key events:

```
event="job_transition" job_id=<id> old_status=<old> new_status=<new>
event="task_transition" job_id=<id> task_id=<id> phase=<phase>
event="gate_passed" job_id=<id> phase=<phase>
event="gate_failed" job_id=<id> phase=<phase>
event="stale_task_detected" job_id=<id> task_id=<id>
event="stalled_job_detected" job_id=<id>
event="job_auto_completed" job_id=<id>
```

### Searching Logs

```bash
# Find all job transitions
grep "job_transition" ~/.context-foundry/logs/cfd.log

# Find all failures
grep -E "(failed|error|timeout)" ~/.context-foundry/logs/cfd.log

# Find events for a specific job
grep "<first 8 chars of job_id>" ~/.context-foundry/logs/cfd.log

# Watch live structured events
tail -f ~/.context-foundry/logs/cfd.log | grep -E "event="
```

---

## Metrics

The daemon tracks metrics for monitoring:

### Counters
- `daemon.jobs.started` - Jobs started
- `daemon.jobs.succeeded` - Jobs completed successfully
- `daemon.jobs.failed` - Jobs that failed
- `daemon.jobs.stalled` - Jobs that stalled
- `daemon.jobs.timed_out` - Jobs that timed out
- `daemon.tasks.started{phase=X}` - Tasks started per phase
- `daemon.tasks.succeeded{phase=X}` - Tasks succeeded per phase
- `daemon.gates.passed{phase=X}` - Gates passed per phase
- `daemon.gates.failed{phase=X}` - Gates failed per phase
- `daemon.watchdog.iterations` - Watchdog check cycles
- `daemon.watchdog.stale_tasks_detected` - Stale tasks found
- `daemon.watchdog.auto_completions` - Jobs auto-completed

### Gauges
- `daemon.jobs.active` - Currently running jobs
- `daemon.jobs.queued` - Jobs waiting in queue
- `daemon.uptime_seconds` - Daemon uptime

### Timings
- `daemon.jobs.duration_seconds` - Job completion time
- `daemon.phases.duration_seconds{phase=X}` - Phase duration

Metrics are stored in-memory. Future integration with Prometheus/StatsD planned.

---

## Emergency Procedures

### Emergency Stop (All Builds)

```bash
cfd emergency-stop

# To resume:
cfd emergency-resume
```

### Force Kill Daemon

If daemon is completely unresponsive:
```bash
# Find PID
cat ~/.context-foundry/cfd.pid

# Force kill
kill -9 <pid>

# Clean up
rm ~/.context-foundry/cfd.pid
```

### Database Recovery

If database is corrupted:
```bash
# Stop daemon
cfd stop

# Backup current DB
cp ~/.context-foundry/daemon.db ~/.context-foundry/daemon.db.bak

# Integrity check
sqlite3 ~/.context-foundry/daemon.db "PRAGMA integrity_check;"

# If corrupted, start fresh (loses history):
rm ~/.context-foundry/daemon.db
cfd start
```

---

## Health Checks

### Automated (via watchdog)

The daemon has two watchdog threads:

1. **Main Loop Watchdog** - Checks if main loop is alive
   - Warning at 60s without heartbeat
   - Critical at 120s without heartbeat
   - Forces restart after 3 consecutive failures

2. **Task Watchdog** - Checks for stale tasks/jobs
   - Runs every 30 seconds
   - Detects stale heartbeats (>5 min)
   - Detects stalled jobs (>10 min)
   - Auto-completes finished jobs

### Manual Health Check

```bash
# Quick check
cfd status

# Check heartbeat file
cat ~/.context-foundry/daemon_heartbeat.txt
# Format: timestamp\niteration_count\npid

# Verify process is alive
ps aux | grep cfd
```

---

## Configuration Reference

Default config location: `~/.context-foundry/config.yaml`

```yaml
# Core settings
data_dir: ~/.context-foundry
log_dir: ~/.context-foundry/logs
log_level: INFO

# Worker settings
max_concurrent_jobs: 2
default_job_timeout_minutes: 90

# Dashboard settings
enable_dashboard: true
dashboard_host: 127.0.0.1
dashboard_port: 8420
dashboard_refresh_interval: 5

# HTTP API settings
enable_http_api: true
http_api_host: 127.0.0.1
http_api_port: 8421

# Watchdog thresholds (internal)
# heartbeat_timeout: 300     # 5 minutes for stale tasks
# stall_threshold: 600       # 10 minutes for stalled jobs
# job_timeout_grace: 60      # Grace period before timeout
```

---

## Support

- Dashboard: http://localhost:8420 (when enabled)
- HTTP API: http://localhost:8421 (when enabled)
- GitHub Issues: https://github.com/anthropics/context-foundry/issues
- Logs: `~/.context-foundry/logs/`

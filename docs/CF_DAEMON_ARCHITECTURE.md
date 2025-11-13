# Context Foundry Daemon Architecture

## Overview

The Context Foundry Daemon (cfd) is a background service that manages autonomous build tasks by orchestrating Claude Code agents. It provides a persistent queue for build jobs, concurrent execution, and progress tracking.

## Core Concepts

### What is a Job?

A **job** is a work item submitted to the CF Daemon. It represents a build, test, or deployment task that needs to be executed by a Claude Code agent.

Each job is a database record containing:
- **ID**: Unique identifier (UUID)
- **Type**: Job type (testing, building, deployment, etc.)
- **Status**: Current state (queued, running, succeeded, failed, cancelled)
- **Parameters**: Task description, working directory, timeout, etc.
- **Timestamps**: When created, started, completed
- **Results**: Output from the Claude Code agent
- **Retry count**: Number of retry attempts

Example job:
```json
{
  "id": "17044610-0379-4708-b9a3-768e8535e3ec",
  "type": "testing",
  "status": "succeeded",
  "priority": 7,
  "params": {
    "working_directory": "/tmp/test-project",
    "task": "Run all tests and fix any failures",
    "timeout_minutes": 30
  },
  "created_at": "2025-11-13 11:20:06",
  "started_at": "2025-11-13 11:20:07",
  "completed_at": "2025-11-13 11:22:15",
  "result": {
    "success": true,
    "exit_code": 0,
    "task_id": "ed3465f6-7571-4843-9894-0984f8702dac"
  }
}
```

### Are Jobs Claude Code Agents?

**Yes, indirectly!** Each job spawns a separate Claude Code agent process that autonomously executes the task.

## Architecture Diagram

```
┌───────────────────────────────────────────────────────────────┐
│                     CF Daemon Process                          │
│                    (background service)                        │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ JobManager                                            │     │
│  │  - SQLite database (job queue)                       │     │
│  │  - Worker thread pool (default: 3 workers)           │     │
│  │  - Job lifecycle management                          │     │
│  │  - Retry logic                                       │     │
│  └──────────────────────────────────────────────────────┘     │
│           │                                                    │
│           │ Worker picks up queued job (~0.5s polling)        │
│           ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ Runner                                                │     │
│  │  - Executes jobs via delegation                      │     │
│  │  - Spawns Claude Code subprocesses                   │     │
│  │  - Tracks phase progress (Scout→Architect→Builder)   │     │
│  │  - Emits PhaseEvents and LogEntries                  │     │
│  │  - Triggers pattern merge on success                 │     │
│  └──────────────────────────────────────────────────────┘     │
│           │                                                    │
└───────────┼────────────────────────────────────────────────────┘
            │
            │ Spawns subprocess via delegate_to_claude_code_async()
            ▼
┌───────────────────────────────────────────────────────────────┐
│         Separate Claude Code CLI Process (Agent)              │
│                  (one per job)                                │
│                                                               │
│  This is the actual AI agent that autonomously:              │
│                                                               │
│  Phase 1: Scout                                               │
│    - Explore codebase structure                              │
│    - Identify relevant files                                 │
│    - Understand dependencies                                 │
│                                                               │
│  Phase 2: Architect                                           │
│    - Design implementation approach                          │
│    - Plan file changes                                       │
│    - Identify risks                                          │
│                                                               │
│  Phase 3: Builder                                             │
│    - Write/modify code                                       │
│    - Create tests                                            │
│    - Handle dependencies                                     │
│                                                               │
│  Phase 4: Test                                                │
│    - Run test suite                                          │
│    - Verify build passes                                     │
│    - Fix failures (with retry loop)                          │
│                                                               │
│  Writes progress to:                                         │
│    .context-foundry/current-phase.json                       │
│    .context-foundry/patterns/common-issues.json              │
│    .context-foundry/build-output-{task_id}.txt               │
└───────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. CF Daemon (`context_foundry/daemon/server.py`)

The main daemon process that:
- Runs persistently in the background
- Manages PID file (`~/.context-foundry/cfd/daemon.pid`)
- Handles signals (SIGTERM, SIGINT, SIGHUP)
- Supervises JobManager
- Logs to `~/.context-foundry/cfd/logs/cfd.log`

### 2. JobManager (`context_foundry/daemon/jobs.py`)

Manages the job queue:
- Accepts job submissions
- Spawns worker threads (default: 3 concurrent jobs)
- Polls SQLite database for QUEUED jobs
- Executes jobs via Runner
- Handles retries on failure
- Tracks job status transitions

Job lifecycle:
```
QUEUED → RUNNING → SUCCEEDED
              ↓
           FAILED → (retry) → QUEUED
              ↓
       (max retries) → FAILED (permanent)

CANCELLED (user requested)
```

### 3. Runner (`context_foundry/daemon/runner.py`)

Executes individual jobs:
- Calls `delegate_to_claude_code_async()` to spawn Claude Code subprocess
- Polls for phase transitions by reading `.context-foundry/current-phase.json`
- Emits **PhaseEvents** (Scout started, Architect completed, etc.)
- Emits **LogEntries** (progress messages, errors, warnings)
- Triggers pattern merge on successful completion
- Returns results to JobManager

### 4. Store (`context_foundry/daemon/store.py`)

SQLite database wrapper:
- **Jobs table**: Job records with status, params, results
- **Logs table**: Structured log entries for each job
- **Phase events table**: Phase transition tracking
- Uses WAL mode for concurrent access
- Provides query interface for CLI

### 5. CLI (`context_foundry/daemon/cli.py`)

Command-line interface for users:
- `cfd start` - Start the daemon
- `cfd stop` - Stop the daemon
- `cfd status` - Check daemon status
- `cfd submit` - Submit a new job
- `cfd list` - List jobs with filters
- `cfd show <job_id>` - Show job details
- `cfd logs <job_id>` - View job logs
- `cfd cancel <job_id>` - Cancel a job

## How It Works: End-to-End Flow

### Step 1: Submit a Job

```bash
cfd submit \
  --type testing \
  --params '{"working_directory": "/path/to/project", "task": "Fix all failing tests"}' \
  --priority 5
```

Output:
```
Job submitted: 17044610-0379-4708-b9a3-768e8535e3ec
  Type: testing
  Priority: 5
  Status: queued
```

### Step 2: Daemon Creates Job Record

JobManager creates a record in SQLite:
```sql
INSERT INTO jobs (id, type, status, priority, params, created_at)
VALUES ('17044610-...', 'testing', 'queued', 5, '{"task": "..."}', '2025-11-13 11:20:06');
```

Emits log entry:
```sql
INSERT INTO logs (job_id, level, message, timestamp)
VALUES ('17044610-...', 'INFO', 'Job submitted: testing', '2025-11-13 11:20:06');
```

### Step 3: Worker Thread Picks Up Job

Worker polls database every ~0.5 seconds:
```sql
SELECT * FROM jobs WHERE status = 'queued' ORDER BY priority DESC, created_at ASC LIMIT 1;
```

Updates status:
```sql
UPDATE jobs SET status = 'running', started_at = '2025-11-13 11:20:07' WHERE id = '17044610-...';
```

### Step 4: Runner Spawns Claude Code Agent

Runner calls delegation function:
```python
result = delegate_to_claude_code_async_impl(
    task="Fix all failing tests",
    working_directory="/path/to/project",
    timeout_minutes=30,
    additional_flags=None
)
```

This spawns:
```bash
claude-code --prompt "Fix all failing tests" --working-directory /path/to/project
```

Returns delegation task ID:
```json
{"task_id": "ed3465f6-7571-4843-9894-0984f8702dac", "status": "started"}
```

### Step 5: Claude Code Agent Executes Autonomously

Agent runs through phases:

**Scout Phase** (探索):
- Searches for test files
- Identifies test framework
- Reads failing test output
- Writes: `.context-foundry/current-phase.json` → `{"phase": "scout", "timestamp": "..."}`

**Architect Phase** (设计):
- Analyzes test failures
- Plans fixes for each failure
- Identifies files to modify
- Writes: `.context-foundry/current-phase.json` → `{"phase": "architect", ...}`

**Builder Phase** (构建):
- Fixes test code
- Updates implementation
- Handles dependencies
- Writes: `.context-foundry/current-phase.json` → `{"phase": "builder", ...}`

**Test Phase** (测试):
- Runs test suite
- Verifies all tests pass
- If failures, retries fixes (up to 3 iterations)
- Writes patterns: `.context-foundry/patterns/common-issues.json`

### Step 6: Runner Tracks Progress

While agent runs, Runner polls every 5 seconds:
```python
phase_info = read_phase_info("/path/to/project")
# Returns: {"phase": "architect", "timestamp": "...", "tokens_used": 15000}

if current_phase != last_phase:
    emit_phase_event(job_id, phase="architect", status="in_progress")
    emit_log(job_id, "Phase transition: scout → architect")
```

Emits to database:
```sql
INSERT INTO phase_events (job_id, phase, status, timestamp, details)
VALUES ('17044610-...', 'architect', 'in_progress', '2025-11-13 11:21:30', '{"tokens_used": 15000}');

INSERT INTO logs (job_id, level, message, phase, timestamp)
VALUES ('17044610-...', 'INFO', 'Phase transition: scout → architect', 'architect', '2025-11-13 11:21:30');
```

### Step 7: Agent Completes

Claude Code agent finishes:
- Exit code: 0 (success)
- Output written to: `.context-foundry/build-output-ed3465f6.txt`
- Patterns written to: `.context-foundry/patterns/common-issues.json`

### Step 8: Runner Processes Results

Runner detects completion:
```python
result = get_delegation_result_impl(task_id="ed3465f6-...")
# Returns: {"exit_code": 0, "status": "completed", "output_summary": "..."}
```

If successful, triggers pattern merge:
```python
merge_project_patterns_impl(
    project_pattern_file="/path/to/project/.context-foundry/patterns/common-issues.json",
    pattern_type="common-issues",
    increment_build_count=True
)
```

This writes learnings to global pattern library:
```
~/.context-foundry/patterns/common-issues.json  ← Updated with new patterns
```

### Step 9: Job Marked Complete

JobManager updates database:
```sql
UPDATE jobs
SET status = 'succeeded',
    completed_at = '2025-11-13 11:22:15',
    result = '{"success": true, "exit_code": 0, "task_id": "ed3465f6-..."}'
WHERE id = '17044610-...';
```

Emits final log:
```sql
INSERT INTO logs (job_id, level, message, timestamp)
VALUES ('17044610-...', 'INFO', 'Job completed successfully', '2025-11-13 11:22:15');
```

### Step 10: User Views Results

```bash
cfd show 17044610-0379-4708-b9a3-768e8535e3ec
```

Output:
```
Job ID: 17044610-0379-4708-b9a3-768e8535e3ec
Type: testing
Status: succeeded
Priority: 5
Created: 2025-11-13 11:20:06
Started: 2025-11-13 11:20:07
Completed: 2025-11-13 11:22:15
Duration: 128.45s

Parameters:
{
  "working_directory": "/path/to/project",
  "task": "Fix all failing tests"
}

Result:
{
  "success": true,
  "task_id": "ed3465f6-7571-4843-9894-0984f8702dac",
  "exit_code": 0
}

Phase Events:
  scout: in_progress at 2025-11-13 11:20:10
  architect: in_progress at 2025-11-13 11:21:30
  builder: in_progress at 2025-11-13 11:21:45
  test: completed at 2025-11-13 11:22:15
```

## Key Features

### 1. Concurrent Execution

Multiple jobs run simultaneously:
```bash
# Submit 5 jobs
cfd submit --type testing --params '{"task": "Job 1"}' &
cfd submit --type testing --params '{"task": "Job 2"}' &
cfd submit --type testing --params '{"task": "Job 3"}' &
cfd submit --type testing --params '{"task": "Job 4"}' &
cfd submit --type testing --params '{"task": "Job 5"}' &
wait

# With 3 workers:
# - Jobs 1, 2, 3 start immediately
# - Jobs 4, 5 queue and start as workers free up
```

### 2. Priority Queue

Higher priority jobs execute first:
```bash
cfd submit --priority 10 --params '{"task": "Critical fix"}'   # Runs first
cfd submit --priority 5 --params '{"task": "Normal task"}'     # Runs second
cfd submit --priority 1 --params '{"task": "Low priority"}'    # Runs last
```

### 3. Retry Logic

Failed jobs automatically retry:
```python
# Config default: max_retries = 3
job fails → retry 1 → retry 2 → retry 3 → permanent failure
```

### 4. Real-time Monitoring

Track job progress as it runs:
```bash
# Follow logs in real-time
cfd logs <job_id> --follow

# Output:
2025-11-13 11:20:06 INFO                  Job submitted: testing
2025-11-13 11:20:07 INFO                  Job execution started: testing
2025-11-13 11:20:10 INFO      [scout]     Phase transition: Start → scout
2025-11-13 11:21:30 INFO      [architect] Phase transition: scout → architect
2025-11-13 11:21:45 INFO      [builder]   Phase transition: architect → builder
2025-11-13 11:22:15 INFO      [test]      Phase transition: builder → test
2025-11-13 11:22:15 INFO                  Job completed successfully
```

### 5. Self-Improvement

Successful builds contribute learnings back to pattern library:
```
Project patterns:         Global patterns:
.context-foundry/         ~/.context-foundry/patterns/
  patterns/                 common-issues.json ← Merged here
    common-issues.json      scout-learnings.json
                            test-patterns.json
```

Patterns accumulate across all builds, making future builds smarter.

## Configuration

Config file: `~/.context-foundry/cfd/config.json`

```json
{
  "poll_interval_seconds": 60,
  "max_concurrent_jobs": 3,
  "log_level": "INFO",
  "default_job_timeout_minutes": 120,
  "default_max_retries": 3,
  "max_cpu_percent": 80.0,
  "max_memory_gb": 16.0
}
```

Environment variables override config:
```bash
export CFD_MAX_CONCURRENT=5
export CFD_LOG_LEVEL=DEBUG
export GITHUB_TOKEN=ghp_xxxxx

cfd start  # Uses env vars
```

## Database Schema

### Jobs Table
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    params TEXT NOT NULL,
    result TEXT,
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    metadata TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
```

### Phase Events Table
```sql
CREATE TABLE phase_events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT,
    tokens_used INTEGER,
    context_percent REAL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
```

### Logs Table
```sql
CREATE TABLE logs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    phase TEXT,
    source TEXT,
    metadata TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
```

## Troubleshooting

### Job stuck in QUEUED status

Check if daemon is running:
```bash
cfd status
```

If not running:
```bash
cfd start --foreground
```

Check logs:
```bash
tail -f ~/.context-foundry/cfd/logs/cfd.log
```

### Workers not picking up jobs

Verify worker threads started:
```bash
cfd status --verbose

# Should show:
# Job Statistics:
#   queued: 1
# ...
# Daemon is running (PID 12345)
```

Check daemon logs for worker startup:
```bash
grep "Worker started" ~/.context-foundry/cfd/logs/cfd.log
```

### Job taking too long

Check which phase it's stuck in:
```bash
# View phase events
sqlite3 ~/.context-foundry/cfd/jobs.db \
  "SELECT phase, status, timestamp FROM phase_events WHERE job_id = '<job_id>' ORDER BY timestamp;"

# Check current phase in project
cat /path/to/project/.context-foundry/current-phase.json
```

### View raw delegation output

Full output is written to:
```bash
cat /path/to/project/.context-foundry/build-output-{task_id}.txt
```

## Known Limitations

1. **Background daemonization not implemented**: Daemon always runs in foreground. Use terminal multiplexer (tmux/screen) for persistent background operation.

2. **Worker count changes require restart**: Changing `max_concurrent_jobs` via SIGHUP config reload requires daemon restart to take effect.

3. **Running job cancellation**: Cancelling a RUNNING job sets status to CANCELLED but doesn't actually stop the Claude Code subprocess. Only QUEUED jobs can be cancelled before execution.

## Future Enhancements

Planned features:
- [ ] True background daemonization (fork/setsid)
- [ ] Dynamic worker pool resizing
- [ ] Job dependencies (job B waits for job A)
- [ ] Scheduled/cron jobs
- [ ] GitHub integration (auto-trigger on PR/push)
- [ ] Resource limits enforcement
- [ ] Job output streaming to CLI
- [ ] Web dashboard for monitoring

## Related Documentation

- [CF Daemon Implementation Status](./IMPLEMENTATION_STATUS.md)
- [Phase Spawning Design](./PHASE_SPAWNING_IMPLEMENTATION_SPEC.md)
- [MCP Server Integration](./MCP_SERVER_INTEGRATION.md)
- [Pattern Management](./PATTERN_LIBRARY.md)

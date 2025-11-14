# Context Foundry Daemon (cfd)

The Context Foundry Daemon is a background service that orchestrates autonomous build, test, and deployment tasks. It manages a persistent job queue, executes tasks through delegated Claude Code instances, and tracks progress with comprehensive logging.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)
- [Job Management](#job-management)
- [Daemonization](#daemonization)
- [Logging](#logging)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Overview

The Context Foundry Daemon (cfd) provides:

- **Persistent Job Queue**: SQLite-backed queue survives daemon restarts
- **Concurrent Execution**: Configurable worker pool for parallel job execution
- **Autonomous Builds**: Delegates complex tasks to fresh Claude Code instances
- **Phase Tracking**: Monitor Scout → Architect → Builder → Test phases
- **Pattern Learning**: Automatic pattern merge after successful builds
- **Signal Handling**: Graceful shutdown (SIGTERM/SIGINT) and config reload (SIGHUP)
- **Proper Daemonization**: Unix double-fork with full file descriptor management

### What It's NOT

The Context Foundry Daemon is **not** the same as the "evolution daemon" found in `tools/evolution/`. That's a separate system. This is the **CF Daemon** for build orchestration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CF Daemon (cfd)                      │
│                                                         │
│  ┌──────────────┐      ┌─────────────┐                │
│  │   Server     │─────→│ JobManager  │                │
│  │  (server.py) │      │ (jobs.py)   │                │
│  └──────────────┘      └──────┬──────┘                │
│         │                     │                        │
│         │              ┌──────▼──────┐                │
│         │              │   Workers   │                │
│         │              │  (threads)  │                │
│         │              └──────┬──────┘                │
│         │                     │                        │
│  ┌──────▼──────┐      ┌──────▼──────┐                │
│  │   Config    │      │   Runner    │                │
│  │ (config.py) │      │ (runner.py) │                │
│  └─────────────┘      └──────┬──────┘                │
│                              │                        │
│  ┌─────────────┐      ┌──────▼──────────────────┐   │
│  │   Store     │◄─────│  Claude Code Instance   │   │
│  │ (store.py)  │      │  (subprocess)           │   │
│  └─────────────┘      └─────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Components

- **Server** (`server.py`): Main daemon process with PID management and signal handling
- **JobManager** (`jobs.py`): Thread pool executor managing concurrent job execution
- **Runner** (`runner.py`): Executes jobs by delegating to Claude Code CLI instances
- **Store** (`store.py`): SQLite persistence for jobs, logs, and phase events
- **Config** (`config.py`): Configuration loading and management
- **CLI** (`cli.py`): Command-line interface for daemon control
- **Models** (`models.py`): Domain models (Job, JobType, JobStatus, etc.)

## Installation

### Prerequisites

- Python 3.9 or higher
- Claude Code CLI installed and configured
- SQLite 3.8.0 or higher (usually included with Python)

### Install Package

From the repository root:

```bash
# Install in development mode
pip install -e .

# Or install normally
pip install .
```

This makes the `cfd` command available system-wide.

### Verify Installation

```bash
cfd --help
```

## Quick Start

### 1. Start the Daemon

```bash
# Start in background (daemonized)
cfd start

# Or run in foreground (for debugging)
cfd start --foreground
```

### 2. Check Status

```bash
# Basic status
cfd status

# Detailed status with job statistics
cfd status --verbose
```

### 3. Submit a Job

```bash
# Submit a build job
cfd submit \
  --type autonomous_build \
  --params '{"task": "Create a hello world app", "working_directory": "/tmp/test-app"}' \
  --priority 5

# Submit and wait for completion
cfd submit \
  --type autonomous_build \
  --params '{"task": "Run tests", "working_directory": "/path/to/project"}' \
  --wait
```

### 4. Monitor Jobs

```bash
# List all jobs
cfd list

# List only running jobs
cfd list --status running

# Show detailed job info
cfd show <job-id>

# Stream job logs
cfd logs <job-id> --follow
```

### 5. Stop the Daemon

```bash
# Graceful shutdown (waits for running jobs)
cfd stop

# Force shutdown after timeout
cfd stop --timeout 10
```

## CLI Reference

### `cfd start`

Start the daemon.

```bash
cfd start [--foreground] [--config CONFIG]
```

**Options:**
- `--foreground`, `-f`: Run in foreground mode (logs to stdout + file)
- `--config CONFIG`: Path to config file (default: `~/.context-foundry/cfd/config.json`)

**Background Mode** (default):
- Daemonizes using Unix double-fork
- Redirects stdin/stdout/stderr to `/dev/null`
- Logs only to file (`~/.context-foundry/cfd/logs/cfd.log`)
- Returns immediately after verifying child started

**Foreground Mode**:
- Runs in terminal (Ctrl+C to stop)
- Logs to both stdout and file
- Useful for debugging

**Exit Codes:**
- `0`: Daemon started successfully
- `1`: Failed to start (check logs for details)

### `cfd stop`

Stop the daemon gracefully.

```bash
cfd stop [--timeout SECONDS]
```

**Options:**
- `--timeout SECONDS`: Graceful shutdown timeout (default: 30)

**Behavior:**
1. Sends SIGTERM to daemon
2. Waits up to `timeout` seconds for graceful shutdown
3. Sends SIGKILL if timeout exceeded

### `cfd status`

Get daemon status.

```bash
cfd status [--verbose]
```

**Options:**
- `--verbose`, `-v`: Show detailed status including job statistics and configuration

**Output:**
```
Daemon is running (PID 12345)

Job Statistics:
  running: 2
  succeeded: 45
  failed: 3
  cancelled: 1

Configuration:
  Data dir: /Users/name/.context-foundry/cfd
  Log dir: /Users/name/.context-foundry/cfd/logs
  DB path: /Users/name/.context-foundry/cfd/jobs.db
  Max concurrent jobs: 3
```

### `cfd submit`

Submit a new job to the queue.

```bash
cfd submit --type TYPE --params JSON [OPTIONS]
```

**Required Options:**
- `--type TYPE`: Job type (see [Job Types](#job-types))
- `--params JSON`: Job parameters as JSON string

**Optional:**
- `--priority N`: Priority 1-10 (default: 5, higher = more important)
- `--max-retries N`: Maximum retry attempts (default: 3)
- `--wait`: Wait for job to complete before returning
- `--timeout SECONDS`: Timeout for `--wait` (default: unlimited)

**Example:**
```bash
cfd submit \
  --type autonomous_build \
  --params '{
    "task": "Create a FastAPI hello world app",
    "working_directory": "/tmp/fastapi-demo",
    "github_repo_name": "my-fastapi-demo"
  }' \
  --priority 8 \
  --wait
```

### `cfd list`

List jobs.

```bash
cfd list [--status STATUS] [--limit N] [--offset N]
```

**Options:**
- `--status STATUS`: Filter by status (`queued`, `running`, `succeeded`, `failed`, `cancelled`)
- `--limit N`: Maximum jobs to show (default: 50)
- `--offset N`: Pagination offset (default: 0)

**Output:**
```
ID                                   Type                Status      Priority Created
------------------------------------ ------------------- ----------- -------- --------------------
550e8400-e29b-41d4-a716-446655440000 autonomous_build    succeeded   8        2025-01-15 14:23:10
6ba7b810-9dad-11d1-80b4-00c04fd430c8 autonomous_build    running     5        2025-01-15 14:25:33
```

### `cfd show`

Show detailed job information.

```bash
cfd show JOB_ID
```

**Output:**
```
Job ID: 550e8400-e29b-41d4-a716-446655440000
Type: autonomous_build
Status: succeeded
Priority: 8
Created: 2025-01-15 14:23:10
Started: 2025-01-15 14:23:12
Completed: 2025-01-15 14:28:45
Retry count: 0/3
Duration: 333.15s

Parameters:
{
  "task": "Create a FastAPI hello world app",
  "working_directory": "/tmp/fastapi-demo"
}

Result:
{
  "exit_code": 0,
  "github_url": "https://github.com/user/my-fastapi-demo"
}

Phase Events:
  scout: completed at 2025-01-15 14:23:45
  architect: completed at 2025-01-15 14:24:12
  builder: completed at 2025-01-15 14:27:30
  test: completed at 2025-01-15 14:28:40
```

### `cfd logs`

View job logs.

```bash
cfd logs JOB_ID [--follow] [--level LEVEL] [--limit N]
```

**Options:**
- `--follow`, `-f`: Stream logs in real-time (like `tail -f`)
- `--level LEVEL`: Filter by log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `--limit N`: Maximum log entries to show (default: 100)

**Example:**
```bash
# View last 100 logs
cfd logs 550e8400-e29b-41d4-a716-446655440000

# Stream logs in real-time
cfd logs 6ba7b810-9dad-11d1-80b4-00c04fd430c8 --follow

# Show only errors
cfd logs 550e8400-e29b-41d4-a716-446655440000 --level ERROR
```

### `cfd cancel`

Cancel a running job.

```bash
cfd cancel JOB_ID
```

**Behavior:**
- Marks job as `CANCELLED` in database
- Sends SIGTERM to running subprocess (if active)
- Job will not be retried

## Configuration

Configuration is loaded from `~/.context-foundry/cfd/config.json`.

### Default Configuration

```json
{
  "data_dir": "~/.context-foundry/cfd",
  "log_dir": "~/.context-foundry/cfd/logs",
  "log_level": "INFO",
  "max_concurrent_jobs": 3,
  "default_max_retries": 3,
  "job_timeout_minutes": 90
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `data_dir` | string | `~/.context-foundry/cfd` | Data directory (contains DB and PID file) |
| `log_dir` | string | `~/.context-foundry/cfd/logs` | Log file directory |
| `log_level` | string | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `max_concurrent_jobs` | int | 3 | Maximum concurrent worker threads |
| `default_max_retries` | int | 3 | Default retry count for failed jobs |
| `job_timeout_minutes` | int | 90 | Default timeout for job execution |

### Reload Configuration

Send SIGHUP to reload configuration without restarting:

```bash
# Find daemon PID
cfd status

# Send SIGHUP
kill -HUP <pid>
```

**Reloadable Settings:**
- `log_level`: Changes take effect immediately

**Non-Reloadable Settings** (require restart):
- `max_concurrent_jobs`: Worker pool size is fixed at startup
- `data_dir`, `log_dir`: Directories are set during initialization

**Note:** Config paths are converted to absolute paths at startup, so SIGHUP reload works even if you provided a relative path to `--config`.

## Job Management

### Job Types

The daemon supports these job types:

#### `autonomous_build`

Autonomous build and deployment orchestration.

**Parameters:**
```json
{
  "task": "string (required) - Task description",
  "working_directory": "string (required) - Project directory",
  "github_repo_name": "string (optional) - GitHub repo name",
  "timeout_minutes": "int (optional) - Override default timeout",
  "mode": "string (optional) - new_project|existing_repo|incremental"
}
```

**Phases:**
1. **Scout**: Explore codebase and gather context
2. **Architect**: Plan implementation approach
3. **Builder**: Execute implementation
4. **Test**: Run tests and verify

### Job Lifecycle

```
QUEUED → RUNNING → SUCCEEDED
                 → FAILED (may retry)
                 → CANCELLED
```

**States:**

- **QUEUED**: Job submitted, waiting for worker
- **RUNNING**: Worker executing job
- **SUCCEEDED**: Job completed successfully
- **FAILED**: Job failed (will retry if `retry_count < max_retries`)
- **CANCELLED**: Job cancelled by user

### Retry Logic

Failed jobs automatically retry up to `max_retries` times:

1. Job fails with error
2. `retry_count` incremented
3. If `retry_count < max_retries`, job returns to QUEUED
4. If `retry_count >= max_retries`, job stays FAILED

### Job Priorities

Jobs are executed in priority order (1-10, higher = sooner):

- **1-3**: Low priority (background tasks)
- **4-6**: Normal priority (default: 5)
- **7-9**: High priority (urgent tasks)
- **10**: Critical priority (immediate execution)

Within the same priority, jobs execute FIFO.

## Daemonization

The CF Daemon implements proper Unix daemonization using the double-fork technique.

### How It Works

**Background Mode** (`cfd start`):

1. **First Fork**: Parent exits, child continues
2. **Process Isolation**:
   - `os.setsid()`: Create new session
   - `os.chdir("/")`: Change to root directory
   - `os.umask(0)`: Reset file creation mask
3. **Second Fork**: Prevent acquiring controlling terminal
4. **File Descriptor Redirection**:
   - `stdin` → `/dev/null`
   - `stdout` → `/dev/null`
   - `stderr` → `/dev/null`
5. **Status Reporting**: Child reports success/failure to parent via pipe
6. **Logging Setup**: Configure file-only logging after fork
7. **Main Loop**: Enter daemon event loop

**Foreground Mode** (`cfd start --foreground`):

- No forking
- Logs to both stdout and file
- Ctrl+C to stop
- Useful for debugging

### Error Reporting

The daemon uses a parent/child status pipe to report initialization errors:

1. Parent waits up to 5 seconds for child status
2. Child sends "OK" on successful initialization
3. Child sends "ERROR: <message>" on failure
4. Parent exits with appropriate code

**Example error scenarios:**

```bash
$ cfd start
Starting Context Foundry Daemon in background...
Daemon failed to start: ERROR: Failed to write PID file: Permission denied
$ echo $?
1
```

### PID File Management

- **Location**: `~/.context-foundry/cfd/daemon.pid`
- **Contains**: Child process PID (not parent)
- **Stale Detection**: Automatically removes stale PID files
- **Locking**: Prevents multiple daemon instances

### Signal Handling

| Signal | Behavior |
|--------|----------|
| SIGTERM | Graceful shutdown (waits for running jobs) |
| SIGINT | Graceful shutdown (Ctrl+C in foreground mode) |
| SIGHUP | Reload configuration (log level only) |

### File Descriptor Management

The daemon properly manages file descriptors across the fork:

1. **Before Fork**: File descriptors inherited from parent
2. **After Fork**:
   - Old handlers flushed and closed
   - New handlers created for log file
   - stdin/stdout/stderr → `/dev/null`

This prevents:
- File descriptor leaks
- Terminal pollution from background process
- Log duplication

## Logging

### Log Locations

- **Daemon Log**: `~/.context-foundry/cfd/logs/cfd.log`
- **Job Logs**: Stored in SQLite (`Store.get_logs(job_id)`)

### Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages (non-fatal issues)
- **ERROR**: Error messages (fatal issues)

### Log Format

```
2025-01-15 14:23:10,123 - context_foundry.daemon.server - INFO - CF Daemon started (PID 12345, 3 workers)
```

### Viewing Logs

**Daemon logs:**
```bash
# Tail daemon log
tail -f ~/.context-foundry/cfd/logs/cfd.log

# View last 100 lines
tail -100 ~/.context-foundry/cfd/logs/cfd.log
```

**Job logs:**
```bash
# View job logs via CLI
cfd logs <job-id>

# Stream job logs
cfd logs <job-id> --follow
```

## Testing

### Running Tests

The daemon includes comprehensive tests with proper daemonization coverage.

**Prerequisites:**
```bash
# Install package in development mode
pip install -e .
```

**Run all daemon tests:**
```bash
# Run all daemon tests
pytest tests/test_daemon_*.py -v

# Run just daemonization tests
pytest tests/test_daemon_daemonization.py -v

# Or with PYTHONPATH
PYTHONPATH=. pytest tests/test_daemon_daemonization.py -v

# Or with python module
python3 -m pytest tests/test_daemon_daemonization.py -v
```

### Test Coverage

| Test Suite | Coverage |
|------------|----------|
| `test_daemon_store.py` | SQLite persistence, job CRUD |
| `test_daemon_jobs.py` | JobManager, worker threads, concurrency |
| `test_daemon_daemonization.py` | Fork logic, FD redirection, status pipes |

**Note:** Daemonization tests use extensive mocking (os.fork, os.dup2, etc.) to test logic without actual process forking. True end-to-end daemonization testing requires manual testing or subprocess-based test harness.

## Troubleshooting

### Daemon Won't Start

**Problem:** `cfd start` exits with error

**Solutions:**

1. **Check if already running:**
   ```bash
   cfd status
   # If running, stop first:
   cfd stop
   ```

2. **Check permissions:**
   ```bash
   # Ensure data directory is writable
   ls -ld ~/.context-foundry/cfd
   mkdir -p ~/.context-foundry/cfd
   chmod 755 ~/.context-foundry/cfd
   ```

3. **Check logs:**
   ```bash
   tail -50 ~/.context-foundry/cfd/logs/cfd.log
   ```

4. **Run in foreground for debugging:**
   ```bash
   cfd start --foreground
   ```

### Daemon Hangs on Startup

**Problem:** `cfd start` times out with "timed out waiting for status confirmation"

**Cause:** Child process hung during initialization (likely in JobManager.start() or Store initialization)

**Solutions:**

1. **Check database:**
   ```bash
   # Ensure database is not corrupted
   sqlite3 ~/.context-foundry/cfd/jobs.db "PRAGMA integrity_check;"
   ```

2. **Run in foreground with debug logging:**
   ```bash
   # Edit config to set log_level: DEBUG
   vim ~/.context-foundry/cfd/config.json

   # Start in foreground
   cfd start --foreground
   ```

3. **Remove stale database:**
   ```bash
   # CAUTION: This deletes all job history
   rm ~/.context-foundry/cfd/jobs.db
   cfd start
   ```

### Jobs Not Running

**Problem:** Jobs stuck in QUEUED state

**Solutions:**

1. **Check daemon is running:**
   ```bash
   cfd status
   ```

2. **Check worker threads:**
   ```bash
   cfd status --verbose
   # Look for "Max concurrent jobs: N"
   ```

3. **Check for deadlocked jobs:**
   ```bash
   # List running jobs
   cfd list --status running

   # If stuck, cancel them
   cfd cancel <job-id>
   ```

4. **Restart daemon:**
   ```bash
   cfd stop
   cfd start
   ```

### Configuration Not Reloading

**Problem:** Changes to config file not taking effect after SIGHUP

**Cause:** Some settings require daemon restart (e.g., `max_concurrent_jobs`)

**Solution:**

1. **Check what's reloadable:**
   - ✅ `log_level`: Reloads via SIGHUP
   - ❌ `max_concurrent_jobs`: Requires restart
   - ❌ `data_dir`, `log_dir`: Requires restart

2. **Restart for non-reloadable settings:**
   ```bash
   cfd stop
   cfd start
   ```

### Relative Config Path Issues

**Problem:** Config reload fails after daemonization with relative path

**Solution:** This is now handled automatically. Config paths are converted to absolute paths in `__init__`, so SIGHUP reload works even if you specified a relative path:

```bash
# This now works correctly
cfd --config ./my-config.json start
# (internally converted to absolute path before chdir("/"))
```

### Can't Import context_foundry in Tests

**Problem:** `pytest tests/test_daemon_daemonization.py` fails with `ModuleNotFoundError`

**Solution:**

Package must be installed before running tests:

```bash
# Install in development mode
pip install -e .

# Then run tests
pytest tests/test_daemon_daemonization.py -v
```

Or set PYTHONPATH:
```bash
PYTHONPATH=. pytest tests/test_daemon_daemonization.py -v
```

## Advanced Usage

### Custom Config Location

```bash
# Start with custom config
cfd --config /path/to/my-config.json start

# Relative paths work too (converted to absolute internally)
cfd --config ./config/dev.json start
```

### Multiple Daemon Instances

To run multiple CF Daemon instances (e.g., for different projects):

1. **Create separate configs:**
   ```json
   // ~/.context-foundry/project-a/config.json
   {
     "data_dir": "~/.context-foundry/project-a",
     "log_dir": "~/.context-foundry/project-a/logs"
   }
   ```

2. **Start with different configs:**
   ```bash
   cfd --config ~/.context-foundry/project-a/config.json start
   cfd --config ~/.context-foundry/project-b/config.json start
   ```

Each instance maintains its own PID file, database, and logs.

### Job Submission from Scripts

```python
#!/usr/bin/env python3
import subprocess
import json

def submit_build(task, working_dir, priority=5):
    """Submit a build job to CF Daemon"""
    params = {
        "task": task,
        "working_directory": working_dir
    }

    result = subprocess.run([
        "cfd", "submit",
        "--type", "autonomous_build",
        "--params", json.dumps(params),
        "--priority", str(priority),
        "--wait"
    ], capture_output=True, text=True)

    return result.returncode == 0

# Example usage
success = submit_build(
    task="Create a FastAPI app with user authentication",
    working_dir="/tmp/auth-service",
    priority=8
)
print(f"Build {'succeeded' if success else 'failed'}")
```

## See Also

- [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) - Development status and roadmap
- [Context Foundry MCP Server](../../README.md) - Main project documentation
- [Claude Code Documentation](https://docs.claude.com/claude-code) - Claude Code CLI docs

## Contributing

When contributing to the CF Daemon:

1. **Add tests** for new features (especially daemonization-related changes)
2. **Update this README** for user-facing changes
3. **Follow existing patterns** in server.py, jobs.py, etc.
4. **Test thoroughly** in both foreground and background modes
5. **Check for FD leaks** when modifying daemonization code

## License

Same as the main Context Foundry project.

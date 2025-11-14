# Context Foundry Daemon - Daemonization Guide

This document provides a comprehensive technical overview of how the Context Foundry Daemon (cfd) implements proper Unix daemonization.

## Table of Contents

- [Overview](#overview)
- [The Double-Fork Technique](#the-double-fork-technique)
- [Implementation Details](#implementation-details)
- [File Descriptor Management](#file-descriptor-management)
- [Error Reporting](#error-reporting)
- [Signal Handling](#signal-handling)
- [Testing Daemonization](#testing-daemonization)
- [Common Pitfalls](#common-pitfalls)
- [References](#references)

## Overview

The CF Daemon supports two modes of operation:

1. **Foreground Mode** (`cfd start --foreground`): Runs in the terminal, logs to stdout + file
2. **Background Mode** (`cfd start`): Properly daemonizes using Unix double-fork

This guide focuses on the background mode implementation.

### Why Proper Daemonization Matters

A properly daemonized process:

- ✅ Has no controlling terminal (immune to terminal signals)
- ✅ Has PPID = 1 (adopted by init/systemd)
- ✅ Doesn't hold open file descriptors from parent
- ✅ Doesn't pollute the parent's terminal with output
- ✅ Can survive the parent session ending

**Improper daemonization** (e.g., just `&` or `nohup`) can lead to:

- ❌ Process killed when terminal closes
- ❌ Stray output appearing in terminal
- ❌ File descriptor leaks
- ❌ Resource contention with parent process

## The Double-Fork Technique

The CF Daemon uses the classic Unix double-fork technique:

```
Parent Process
    │
    ├─ fork() #1
    │
    ▼
First Child
    │
    ├─ setsid()      # Create new session
    ├─ chdir("/")    # Change working directory
    ├─ umask(0)      # Reset file creation mask
    │
    ├─ fork() #2
    │
    ▼
Second Child (Daemon)
    │
    ├─ dup2(stdin → /dev/null)
    ├─ dup2(stdout → /dev/null)
    ├─ dup2(stderr → /dev/null)
    │
    ▼
Main Daemon Loop
```

### Why Two Forks?

**First Fork:**
- Parent can exit immediately (returns control to shell)
- Child becomes session leader via `setsid()`

**Second Fork:**
- Prevents daemon from re-acquiring a controlling terminal
- Session leaders can acquire controlling terminals; non-leaders cannot
- Second child is not a session leader → cannot acquire terminal

## Implementation Details

### Entry Point: `CFDaemon.start()`

**Location:** `context_foundry/daemon/server.py:294-391`

```python
def start(self, foreground: bool = False) -> bool:
    # 1. Check if already running
    if self._check_pid_file():
        print("Daemon is already running", file=sys.stderr)
        return False

    # 2. Daemonize if background mode
    if not foreground:
        print("Starting Context Foundry Daemon in background...")
        sys.stdout.flush()  # Prevent duplicate output across forks

        status_pipe_r = self._daemonize()

        if status_pipe_r is not None:
            # We're the parent - wait for child status
            return self._wait_for_child_status(status_pipe_r)

    # 3. We're the child (or foreground) - setup logging
    self._setup_logging(background_mode=not foreground)

    # 4. Write PID file, setup signals, start workers
    # ...

    # 5. Report success to parent (if background mode)
    self._report_status(True)

    # 6. Enter main loop
    self._run_foreground()
    return True
```

### The `_daemonize()` Method

**Location:** `context_foundry/daemon/server.py:212-281`

```python
def _daemonize(self) -> Optional[int]:
    """
    Daemonize using Unix double-fork technique.

    Returns:
        Pipe read fd for parent to check status, or None if we're the child
    """
    # Create status pipe for parent/child communication
    pipe_r, pipe_w = os.pipe()

    # --- FIRST FORK ---
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - close write end and return read end
            os.close(pipe_w)
            return pipe_r
    except OSError as e:
        os.close(pipe_r)
        os.close(pipe_w)
        print(f"First fork failed: {e}", file=sys.stderr)
        sys.exit(1)

    # --- FIRST CHILD ---
    os.close(pipe_r)  # Close read end (child only writes)

    # Decouple from parent environment
    os.chdir("/")      # Don't keep parent's cwd mounted
    os.setsid()        # Create new session (become session leader)
    os.umask(0)        # Don't inherit parent's umask

    # --- SECOND FORK ---
    try:
        pid = os.fork()
        if pid > 0:
            # First child exits - second child continues
            sys.exit(0)
    except OSError as e:
        # Report error to parent via pipe
        try:
            error_msg = f"Second fork failed: {e}\n"
            os.write(pipe_w, error_msg.encode())
        except Exception:
            pass
        finally:
            os.close(pipe_w)
        sys.exit(1)

    # --- SECOND CHILD (DAEMON) ---

    # Redirect stdin/stdout/stderr to /dev/null
    sys.stdout.flush()
    sys.stderr.flush()

    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, sys.stdin.fileno())   # 0
    os.dup2(devnull, sys.stdout.fileno())  # 1
    os.dup2(devnull, sys.stderr.fileno())  # 2

    if devnull > 2:
        os.close(devnull)

    # Store status pipe for later
    self._status_pipe = pipe_w
    return None  # We're the child
```

### Key Design Decisions

#### 1. Status Pipe Before First Fork

The status pipe is created **before** the first fork so both parent and child have access:

- Parent keeps read end (`pipe_r`)
- Child keeps write end (`pipe_w`)
- Child reports initialization success/failure via pipe

#### 2. Config Path Absolutization

**Location:** `context_foundry/daemon/server.py:47-52`

```python
# Convert config_path to absolute before chdir("/")
if config_path is not None:
    self.config_path = Path(config_path).resolve()
else:
    self.config_path = None
```

This ensures SIGHUP config reload works even after `chdir("/")`.

#### 3. Deferred Logging Setup

Logging is configured **after** the fork completes:

```python
# After fork decision
self._setup_logging(background_mode=not foreground)
```

This prevents:
- File descriptor leaks from parent's log handlers
- Duplicate log entries across parent/child
- Logging to closed file descriptors

#### 4. Proper Handler Cleanup

**Location:** `context_foundry/daemon/server.py:78-85`

```python
def _setup_logging(self, background_mode: bool = False):
    # Flush and close old handlers before clearing
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
    root_logger.handlers.clear()

    # Add new handlers...
```

This prevents file descriptor leaks when logging is reconfigured.

## File Descriptor Management

### The Problem

When a process forks, the child inherits **all** open file descriptors from the parent:

```
Parent Process:
  fd 0 (stdin)  → terminal
  fd 1 (stdout) → terminal
  fd 2 (stderr) → terminal
  fd 3          → log file (FileHandler)
  fd 4          → database connection
  fd 5          → ...

After fork():
  Child has fd 0-5 all still open!
```

If the child doesn't close these:
- Terminal FDs stay open (daemon tied to terminal)
- Parent's file handles leak (locks, resource exhaustion)
- Output can appear in unexpected places

### The Solution

**Step 1: Redirect standard FDs to `/dev/null`**

```python
devnull = os.open(os.devnull, os.O_RDWR)  # Open /dev/null
os.dup2(devnull, 0)  # stdin  → /dev/null
os.dup2(devnull, 1)  # stdout → /dev/null
os.dup2(devnull, 2)  # stderr → /dev/null

if devnull > 2:
    os.close(devnull)  # Close the original fd if not 0/1/2
```

**Step 2: Close/recreate application FDs**

```python
# Close old log handlers (from parent)
for handler in root_logger.handlers[:]:
    handler.flush()
    handler.close()
root_logger.handlers.clear()

# Create new handlers (in child)
file_handler = logging.FileHandler(log_file)
root_logger.addHandler(file_handler)

# Database connections are recreated on first use (lazy init)
```

### Background vs Foreground Mode

**Background Mode:**
- stdin/stdout/stderr → `/dev/null`
- Only FileHandler for logging
- No terminal output

**Foreground Mode:**
- stdin/stdout/stderr unchanged
- FileHandler + StreamHandler for logging
- Output to terminal + file

This is controlled by the `background_mode` parameter to `_setup_logging()`.

## Error Reporting

The daemon uses a pipe-based protocol to report initialization errors from child to parent.

### Parent Side: `_wait_for_child_status()`

**Location:** `context_foundry/daemon/server.py:393-433`

```python
def _wait_for_child_status(self, pipe_fd: int) -> bool:
    import select

    # Wait up to 5 seconds for child status
    ready, _, _ = select.select([pipe_fd], [], [], 5.0)

    if ready:
        status = os.read(pipe_fd, 1024).decode().strip()
        os.close(pipe_fd)

        if status.startswith("OK"):
            print("Daemon started successfully")
            return True
        else:
            print(f"Daemon failed to start: {status}", file=sys.stderr)
            return False
    else:
        # Timeout - child likely hung
        os.close(pipe_fd)
        print("Daemon failed to start: timed out", file=sys.stderr)
        return False
```

### Child Side: `_report_status()`

**Location:** `context_foundry/daemon/server.py:283-292`

```python
def _report_status(self, success: bool, error_msg: str = ""):
    if hasattr(self, '_status_pipe'):
        try:
            status = "OK\n" if success else f"ERROR: {error_msg}\n"
            os.write(self._status_pipe, status.encode())
            os.close(self._status_pipe)
            delattr(self, '_status_pipe')
        except Exception:
            pass  # Pipe may already be closed
```

### Error Scenarios

**Scenario 1: Logging setup fails**

```python
try:
    self._setup_logging(background_mode=not foreground)
except Exception as e:
    error_msg = f"Failed to setup logging: {e}"
    if foreground:
        print(error_msg, file=sys.stderr)  # User sees error
    self._report_status(False, error_msg)  # Parent sees error
    return False
```

**Scenario 2: Child hangs during init**

```python
# Parent waits 5 seconds
ready, _, _ = select.select([pipe_fd], [], [], 5.0)

if not ready:
    # Timeout - child never reported
    print("Daemon failed to start: timed out", file=sys.stderr)
    return False  # Exit code 1
```

**Scenario 3: Successful start**

```python
# Child completes initialization
self._report_status(True)  # Sends "OK\n"

# Parent receives it
if status.startswith("OK"):
    print("Daemon started successfully")
    return True  # Exit code 0
```

## Signal Handling

### Signals Handled

**Location:** `context_foundry/daemon/server.py:165-210`

| Signal | Handler | Behavior |
|--------|---------|----------|
| SIGTERM | `handle_shutdown_signal` | Graceful shutdown |
| SIGINT | `handle_shutdown_signal` | Graceful shutdown (Ctrl+C) |
| SIGHUP | `handle_reload_signal` | Reload configuration |

### Graceful Shutdown

```python
def handle_shutdown_signal(signum, frame):
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name}, initiating graceful shutdown...")
    self.stop()

def stop(self):
    logger.info("Stopping Context Foundry Daemon...")
    self.running = False

    # Stop JobManager (waits for running jobs)
    self.job_manager.stop(timeout=30.0)

    # Remove PID file
    self._remove_pid_file()

    logger.info("CF Daemon stopped")
```

### Config Reload (SIGHUP)

```python
def handle_reload_signal(signum, frame):
    logger.info("Received SIGHUP, reloading configuration...")

    old_log_level = self.config.log_level

    # Reload from absolute config path (safe after chdir("/"))
    self.config = Config.load(self.config_path)

    # Update log level if changed
    if old_log_level != self.config.log_level:
        new_level = getattr(logging, self.config.log_level.upper())
        logging.getLogger().setLevel(new_level)
        logger.info(f"Log level updated: {old_log_level} → {self.config.log_level}")

    # Note: worker count changes require restart
    if old_worker_count != self.config.max_concurrent_jobs:
        logger.warning("Worker count changed, requires restart")
```

## Testing Daemonization

### Test Strategy

**Location:** `tests/test_daemon_daemonization.py`

The test suite uses **extensive mocking** to test daemonization logic without actual forking:

```python
@patch('os.fork')
@patch('os.pipe')
@patch('os.chdir')
@patch('os.setsid')
@patch('os.umask')
@patch('os.open')
@patch('os.dup2')
def test_daemonize_child_redirects_fds(self, mock_dup2, mock_open, ...):
    """Test that child redirects stdin/stdout/stderr to /dev/null"""

    # Simulate both forks returning 0 (child process)
    mock_fork.side_effect = [0, 0]

    # Simulate /dev/null fd
    mock_open.return_value = 5

    daemon._daemonize()

    # Verify stdin/stdout/stderr were redirected
    mock_dup2.assert_any_call(5, 0)  # stdin
    mock_dup2.assert_any_call(5, 1)  # stdout
    mock_dup2.assert_any_call(5, 2)  # stderr
```

### Test Coverage

The test suite covers:

1. **Logging Configuration** (3 tests)
   - Foreground mode: file + stream handlers
   - Background mode: file handler only
   - Handler cleanup before reconfiguration

2. **Daemonization Logic** (3 tests)
   - First fork: parent gets pipe fd
   - Second child: redirects all FDs
   - Fork failure: writes error to pipe

3. **Status Reporting** (3 tests)
   - Success: writes "OK\n"
   - Failure: writes "ERROR: ..."
   - No pipe: doesn't crash

4. **Status Waiting** (3 tests)
   - Success: reads "OK\n", returns True
   - Failure: reads "ERROR: ...", returns False
   - Timeout: returns False (not True!)

5. **Start Integration** (3 tests)
   - Foreground: no daemonization
   - Background parent: waits for status
   - Background child: reports status

**Total: 15 tests**

### Limitations

⚠️ **Important:** These are **unit tests with mocking**, not true integration tests.

They test the **logic** of daemonization, but do **not** test:
- Actual fork() behavior
- Real file descriptor redirection
- Process tree manipulation
- Signal delivery across forks

**True end-to-end testing** requires:
- Manual testing: `./tools/cfd start && ps -p $(cat ~/.context-foundry/cfd/daemon.pid) -o pid,ppid,command`
- Subprocess-based test harness
- Real process forking in test environment

## Common Pitfalls

### 1. Logging Before Daemonization

**❌ Wrong:**
```python
def __init__(self, config):
    self._setup_logging()  # In __init__
    # ...

def start(self, foreground=False):
    if not foreground:
        self._daemonize()  # Fork happens here
        # Child now has duplicate log handlers!
```

**✅ Correct:**
```python
def __init__(self, config):
    self._logging_configured = False  # Flag, don't setup yet
    # ...

def start(self, foreground=False):
    if not foreground:
        self._daemonize()  # Fork first

    self._setup_logging(background_mode=not foreground)  # Then setup
```

### 2. Not Closing Old Handlers

**❌ Wrong:**
```python
def _setup_logging(self):
    root_logger.handlers.clear()  # Doesn't close FDs!
    root_logger.addHandler(FileHandler(log_file))
```

**✅ Correct:**
```python
def _setup_logging(self):
    for handler in root_logger.handlers[:]:
        handler.flush()   # Flush buffered logs
        handler.close()   # Close file descriptor
    root_logger.handlers.clear()
    root_logger.addHandler(FileHandler(log_file))
```

### 3. Not Redirecting stderr

**❌ Wrong:**
```python
os.dup2(devnull, 0)  # stdin
os.dup2(devnull, 1)  # stdout
# stderr not redirected - prints still go to terminal!
```

**✅ Correct:**
```python
os.dup2(devnull, 0)  # stdin
os.dup2(devnull, 1)  # stdout
os.dup2(devnull, 2)  # stderr - all three!
```

### 4. Treating Timeout as Success

**❌ Wrong:**
```python
ready, _, _ = select.select([pipe_fd], [], [], 5.0)
if not ready:
    # Timeout - assume success
    return True  # WRONG! Child may be hung
```

**✅ Correct:**
```python
ready, _, _ = select.select([pipe_fd], [], [], 5.0)
if not ready:
    # Timeout - child hung or crashed
    print("Daemon failed to start: timed out", file=sys.stderr)
    return False  # Treat as failure
```

### 5. Relative Config Paths After chdir("/")

**❌ Wrong:**
```python
def __init__(self, config_path):
    self.config_path = config_path  # Store as-is

def start(self, foreground=False):
    if not foreground:
        os.chdir("/")  # Relative paths now broken!

def reload_config(self):
    self.config = Config.load(self.config_path)  # Fails!
```

**✅ Correct:**
```python
def __init__(self, config_path):
    # Convert to absolute before chdir("/")
    self.config_path = Path(config_path).resolve() if config_path else None

def reload_config(self):
    # Still works after chdir("/")
    self.config = Config.load(self.config_path)
```

### 6. Silent Errors in Foreground Mode

**❌ Wrong:**
```python
try:
    self._setup_logging()
except Exception as e:
    self._report_status(False, str(e))  # Only sent to pipe
    return False  # User sees nothing in foreground mode!
```

**✅ Correct:**
```python
try:
    self._setup_logging()
except Exception as e:
    error_msg = f"Failed to setup logging: {e}"
    if foreground:
        print(error_msg, file=sys.stderr)  # User sees error
    self._report_status(False, error_msg)  # Parent sees error
    return False
```

## References

### Unix Daemonization Resources

- Stevens, W. Richard. "Advanced Programming in the UNIX Environment" (Chapter 13: Daemon Processes)
- [The Linux Programming Interface](https://man7.org/tlpi/) - Chapter 37: Creating Daemons
- `man 7 daemon` - Linux daemon(7) manual page
- [Proper Unix daemonization](https://www.freedesktop.org/software/systemd/man/daemon.html#New-Style%20Daemons) - systemd documentation

### Python Daemonization

- [PEP 3143](https://www.python.org/dev/peps/pep-3143/) - Standard daemon process library (rejected, but informative)
- [python-daemon](https://pypi.org/project/python-daemon/) - Third-party daemonization library
- [Supervisor](http://supervisord.org/) - Alternative: process control system

### Context Foundry Resources

- [README.md](./README.md) - Main daemon documentation
- [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) - Implementation status
- [tests/test_daemon_daemonization.py](../../tests/test_daemon_daemonization.py) - Test suite

## Contributing

When modifying daemonization code:

1. **Understand the flow** - Read this guide thoroughly
2. **Test both modes** - Foreground and background
3. **Check FD leaks** - Use `lsof -p <pid>` to verify
4. **Add tests** - Mock new behavior in test suite
5. **Update docs** - Keep this guide current
6. **Manual testing** - Always test real daemonization

### Verification Checklist

After changes, verify:

- [ ] `cfd start` returns to shell immediately
- [ ] `ps -p $(cat ~/.context-foundry/cfd/daemon.pid) -o ppid` shows PPID = 1
- [ ] `lsof -p <pid>` shows no leaked FDs
- [ ] No terminal output in background mode
- [ ] Errors surface in foreground mode
- [ ] Config reload works with relative paths
- [ ] Timeout treated as failure
- [ ] All 15 tests pass

## Conclusion

The CF Daemon's daemonization implementation follows Unix best practices:

✅ Double-fork prevents controlling terminal
✅ File descriptors properly redirected to /dev/null
✅ Logging handlers flushed/closed before fork
✅ Parent/child status pipe for error reporting
✅ Config paths converted to absolute before chdir("/")
✅ Timeouts treated as failures
✅ Errors surface in foreground mode
✅ Comprehensive test coverage (with honest limitations)

This ensures the daemon runs reliably in production without resource leaks, terminal pollution, or silent failures.

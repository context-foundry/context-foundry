"""
CF Daemon Server

Main daemon process with signal handling, PID management, and service supervision.
"""

import faulthandler
import errno
import io
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


from .config import Config
from .store import Store
from .jobs import JobManager
from .runner import create_runner
from .dashboard import DashboardServer
from .http_api import APIServer
from .metrics import get_metrics, log_structured, init_metrics


# Import emergency stop for daemon monitoring
try:
    from tools.mcp_utils.emergency_stop import is_emergency_stop_active

    EMERGENCY_STOP_AVAILABLE = True
except ImportError:
    EMERGENCY_STOP_AVAILABLE = False


logger = logging.getLogger(__name__)


class CFDaemon:
    """
    Context Foundry Daemon server

    Main orchestration service that:
    - Manages PID file
    - Handles signals (SIGTERM, SIGINT, SIGHUP)
    - Supervises JobManager
    - Provides graceful shutdown
    """

    def __init__(
        self, config: Optional[Config] = None, config_path: Optional[Path] = None
    ):
        """
        Initialize CF Daemon

        Args:
            config: Configuration instance (loads default if not provided)
            config_path: Path to config file (for reload via SIGHUP)
        """
        self.config = config or Config.load(config_path)

        # Convert config_path to absolute path before daemonization (which does chdir("/"))
        # This ensures SIGHUP reload works even after changing working directory
        if config_path is not None:
            self.config_path = Path(config_path).resolve()
        else:
            self.config_path = None

        self.config.ensure_directories()

        # Initialize components
        self.store = Store(self.config.db_path)
        self.runner = create_runner(self.store)

        # JobManager uses runner as callable
        self.job_manager = JobManager(
            config=self.config,
            store=self.store,
            runner=lambda job, store: self.runner.run(job),
        )

        self.running = False
        self._logging_configured = False
        self.dashboard_server: Optional[DashboardServer] = None
        self.http_api_server: Optional[APIServer] = None

        # Watchdog: shared state for external monitoring
        self._main_loop_heartbeat = time.time()
        self._watchdog_thread = None
        self._watchdog_stop_event = threading.Event()

        # Task watchdog: monitors for stale tasks and enforces timeouts
        self._task_watchdog_thread = None
        self._task_watchdog_stop_event = threading.Event()

        # State machine for centralized state transitions
        self._state_machine = None  # Lazy init after store is ready

        # Enable faulthandler for thread dump capability
        faulthandler.enable()

    def _setup_logging(self, background_mode: bool = False):
        """
        Configure logging

        Args:
            background_mode: If True, only log to file (no stdout).
                           If False, log to both file and stdout.
        """
        log_file = self.config.log_dir / "cfd.log"
        self.config.log_dir.mkdir(parents=True, exist_ok=True)

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(
            getattr(logging, self.config.log_level.upper(), logging.INFO)
        )

        # Properly close and flush existing handlers before clearing
        for handler in root_logger.handlers[:]:
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass  # Ignore errors closing handlers (may already be closed)
        root_logger.handlers.clear()

        # Add file handler (always present)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Add stream handler only in foreground mode
        if not background_mode:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)

        self._logging_configured = True

    def _write_pid_file(self):
        """Write PID file"""
        try:
            self.config.pid_file.parent.mkdir(parents=True, exist_ok=True)
            self.config.pid_file.write_text(str(os.getpid()))
            logger.info(f"PID file written: {self.config.pid_file}")
        except Exception as e:
            logger.error(f"Failed to write PID file: {e}")
            raise

    def _remove_pid_file(self):
        """Remove PID file"""
        try:
            if self.config.pid_file.exists():
                self.config.pid_file.unlink()
                logger.info("PID file removed")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")

    def _check_pid_file(self) -> bool:
        """
        Check if daemon is already running

        Returns:
            True if another instance is running, False otherwise
        """
        import errno

        if not self.config.pid_file.exists():
            return False

        try:
            pid = int(self.config.pid_file.read_text().strip())

            # Check if process with this PID exists
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                # Use print since logging may not be configured yet
                if self._logging_configured:
                    logger.error(f"Daemon already running with PID {pid}")
                return True
            except OSError as e:
                # EPERM (errno 1) means process exists but we can't signal it
                # This happens in sandboxed/restricted environments
                # EPERM is sufficient proof the process exists
                if e.errno == errno.EPERM:
                    if self._logging_configured:
                        logger.error(f"Daemon already running with PID {pid}")
                    return True

                # ESRCH (errno 3) means no such process - stale PID file
                # Use print since logging may not be configured yet
                if self._logging_configured:
                    logger.warning(f"Removing stale PID file (PID {pid})")
                self.config.pid_file.unlink()
                return False

        except (ValueError, FileNotFoundError):
            # Invalid PID file - silently remove (logging may not be configured)
            if self._logging_configured:
                logger.warning("Invalid PID file, removing")
            self.config.pid_file.unlink()
            return False

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def handle_shutdown_signal(signum, frame):
            """Handle shutdown signals"""
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            self.stop()

        def handle_reload_signal(signum, frame):
            """Handle reload signal"""
            logger.info("Received SIGHUP, reloading configuration...")
            try:
                old_worker_count = self.config.max_concurrent_jobs
                old_log_level = self.config.log_level

                # Reload configuration from original config path
                self.config = Config.load(self.config_path)

                # Update logging level if changed
                if old_log_level != self.config.log_level:
                    new_level = getattr(
                        logging, self.config.log_level.upper(), logging.INFO
                    )
                    logging.getLogger().setLevel(new_level)
                    logger.info(
                        f"Log level updated: {old_log_level} → {self.config.log_level}"
                    )

                # Update JobManager config reference
                # Note: Worker count changes require daemon restart
                self.job_manager.config = self.config

                if old_worker_count != self.config.max_concurrent_jobs:
                    logger.warning(
                        f"Worker count changed ({old_worker_count} → {self.config.max_concurrent_jobs}), "
                        "but requires daemon restart to take effect"
                    )

                logger.info("Configuration reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload configuration: {e}")

        # Register signal handlers
        signal.signal(signal.SIGTERM, handle_shutdown_signal)
        signal.signal(signal.SIGINT, handle_shutdown_signal)
        # SIGHUP is not available on Windows
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, handle_reload_signal)

        logger.info("Signal handlers registered")

    def _ensure_path(self) -> None:
        """
        Ensure PATH includes common binary locations.

        When the daemon is started by launchd (macOS) or as a Windows service,
        it may have a minimal PATH that doesn't include homebrew/node locations.
        The Claude CLI is a Node.js script, so we need node in PATH.
        """
        import platform

        current_path = os.environ.get("PATH", "")
        is_windows = platform.system() == "Windows"
        separator = ";" if is_windows else ":"

        if is_windows:
            # Windows: common locations for Node.js and npm
            appdata = os.environ.get("APPDATA", "")
            localappdata = os.environ.get("LOCALAPPDATA", "")
            programfiles = os.environ.get("ProgramFiles", r"C:\Program Files")

            required_paths = [
                os.path.join(programfiles, "nodejs"),  # Standard Node.js install
                os.path.join(appdata, "npm") if appdata else "",  # npm global
                os.path.join(localappdata, "Programs", "nodejs")
                if localappdata
                else "",
            ]
            # Filter out empty paths
            required_paths = [p for p in required_paths if p]
        else:
            # macOS/Linux: common locations for homebrew and system binaries
            required_paths = [
                "/opt/homebrew/bin",  # Homebrew on Apple Silicon
                "/usr/local/bin",  # Homebrew on Intel Mac, common location
                "/opt/homebrew/sbin",
                "/usr/local/sbin",
            ]

        # Build new PATH with required paths at the front
        path_parts = current_path.split(separator) if current_path else []
        for required in reversed(required_paths):
            if required and required not in path_parts:
                path_parts.insert(0, required)

        os.environ["PATH"] = separator.join(path_parts)

    def _daemonize(self) -> Optional[int]:
        """
        Daemonize the process.

        On Unix: Uses the double-fork technique to detach from controlling terminal.
        On Windows: Uses subprocess.Popen with DETACHED_PROCESS flag.

        Returns:
            Pipe read fd for parent to check child status, or None if we're the child.
            On Windows, always returns a pipe fd (parent waits for subprocess).
        """
        # Windows-specific daemonization using subprocess
        if sys.platform == 'win32':
            return self._daemonize_windows()

        # Unix double-fork daemonization
        return self._daemonize_unix()

    def _daemonize_windows(self) -> int:
        """
        Windows-specific daemonization using subprocess.Popen.

        Spawns a detached subprocess running the daemon in foreground mode.

        Returns:
            Pipe read fd for parent to check child status.
        """
        # Create a pipe for child status communication
        pipe_r, pipe_w = os.pipe()

        # Build command to start daemon in foreground mode as a detached process
        cmd = [sys.executable, '-m', 'context_foundry.daemon.cli', 'start', '--foreground']
        if self.config_path:
            cmd.extend(['--config', str(self.config_path)])

        # Windows-specific creation flags for detached process
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000

        try:
            # Start the subprocess detached from this console
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                close_fds=True,
            )

            # Give the subprocess a moment to start and write its PID file
            time.sleep(0.5)

            # Check if process is still running
            if proc.poll() is None:
                # Process is running, write OK to pipe
                os.write(pipe_w, b"OK\n")
            else:
                # Process exited unexpectedly
                os.write(pipe_w, f"ERROR: Process exited with code {proc.returncode}\n".encode())

        except Exception as e:
            os.write(pipe_w, f"ERROR: {e}\n".encode())
        finally:
            os.close(pipe_w)

        return pipe_r

    def _daemonize_unix(self) -> Optional[int]:
        """
        Unix-specific daemonization using the double-fork technique.

        Returns:
            Pipe read fd for parent to check child status, or None if we're the child.
        """
        # Create a pipe for child status communication
        # Parent reads from pipe_r, child writes to pipe_w
        pipe_r, pipe_w = os.pipe()

        try:
            # First fork
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

        # First child process - close read end
        os.close(pipe_r)

        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # First child exits - second child continues
                sys.exit(0)
        except OSError as e:
            # Write error to pipe before exiting
            try:
                error_msg = f"Second fork failed: {e}\n"
                os.write(pipe_w, error_msg.encode())
            except Exception:
                pass
            finally:
                os.close(pipe_w)
            sys.exit(1)

        # Second child (daemon process) - redirect all file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        # Open /dev/null for reading and writing
        devnull = os.open(os.devnull, os.O_RDWR)

        # Redirect stdin, stdout, stderr to /dev/null
        os.dup2(devnull, sys.stdin.fileno())
        os.dup2(devnull, sys.stdout.fileno())
        os.dup2(devnull, sys.stderr.fileno())

        # Close the original /dev/null fd if it's not one of the standard fds
        if devnull > 2:
            os.close(devnull)

        # CRITICAL: Preserve HOME for Claude CLI auth (reads tokens from ~/.config/claude/)
        # Note: PATH is already set by _ensure_path() called at start()
        # The double-fork can sometimes lose these env vars
        if "HOME" not in os.environ:
            import pwd

            os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir

        # Store the status pipe for later use
        self._status_pipe = pipe_w
        return None  # We're the child

    def _report_status(self, success: bool, error_msg: str = ""):
        """Report status to parent process via status pipe"""
        if hasattr(self, "_status_pipe"):
            try:
                status = "OK\n" if success else f"ERROR: {error_msg}\n"
                os.write(self._status_pipe, status.encode())
                os.close(self._status_pipe)
                delattr(self, "_status_pipe")
            except Exception:
                pass  # Pipe may already be closed

    def start(self, foreground: bool = False) -> bool:
        """
        Start the daemon

        Args:
            foreground: If False, daemonize and run in background. If True, run in foreground.

        Returns:
            True if daemon started successfully, False otherwise.
            In background mode, this returns in the parent after verifying child started.
        """
        # Ensure PATH includes common binary locations (needed for Claude CLI which requires node)
        # This fixes issues when daemon is started by launchd with minimal PATH
        self._ensure_path()

        # Check if already running (before fork)
        if self._check_pid_file():
            print("Daemon is already running", file=sys.stderr)
            return False

        status_pipe_r = None

        # Daemonize before setting up logging if running in background
        if not foreground:
            # Print to console before daemonizing
            print("Starting Context Foundry Daemon in background...")
            sys.stdout.flush()  # Flush to prevent duplicate output across forks

            status_pipe_r = self._daemonize()

            if status_pipe_r is not None:
                # We're the parent - wait for child status
                return self._wait_for_child_status(status_pipe_r)

        # We're the child (or in foreground mode)
        # Setup logging after fork (background_mode=True in daemon, False in foreground)
        try:
            self._setup_logging(background_mode=not foreground)
        except Exception as e:
            error_msg = f"Failed to setup logging: {e}"
            # In foreground mode, print to stderr so user sees the error
            if foreground:
                print(error_msg, file=sys.stderr)
            self._report_status(False, error_msg)
            return False

        logger.info("Starting Context Foundry Daemon...")

        # Write PID file (with the child process PID after fork)
        try:
            self._write_pid_file()
        except Exception as e:
            error_msg = f"Failed to write PID file: {e}"
            if self._logging_configured:
                logger.error(error_msg)
            if foreground:
                print(error_msg, file=sys.stderr)
            self._report_status(False, error_msg)
            return False

        # Setup signal handlers
        try:
            self._setup_signal_handlers()
        except Exception as e:
            error_msg = f"Failed to setup signal handlers: {e}"
            logger.error(error_msg)
            if foreground:
                print(error_msg, file=sys.stderr)
            self._report_status(False, error_msg)
            return False

        # Start JobManager
        try:
            self.job_manager.start(num_workers=self.config.max_concurrent_jobs)
        except Exception as e:
            error_msg = f"Failed to start JobManager: {e}"
            logger.error(error_msg)
            if foreground:
                print(error_msg, file=sys.stderr)
            self._report_status(False, error_msg)
            return False

        # Start lightweight dashboard server (best-effort)
        if self.config.enable_dashboard:
            try:
                self.dashboard_server = DashboardServer(
                    host=self.config.dashboard_host,
                    port=self.config.dashboard_port,
                    job_manager=self.job_manager,
                    store=self.store,
                    refresh_interval=self.config.dashboard_refresh_interval,
                )
                self.dashboard_server.start()
            except Exception as e:
                logger.error(f"Failed to start dashboard server: {e}")

        # Start HTTP API server (best-effort)
        if self.config.enable_http_api:
            try:
                self.http_api_server = APIServer(
                    store=self.store,
                    host=self.config.http_api_host,
                    port=self.config.http_api_port,
                    job_manager=self.job_manager,
                )
                self.http_api_server.start()
                logger.info(f"HTTP API available at {self.http_api_server.url}")
            except Exception as e:
                logger.error(f"Failed to start HTTP API server: {e}")

        self.running = True

        # Initialize metrics system
        init_metrics(enable=True)

        logger.info(
            f"CF Daemon started (PID {os.getpid()}, "
            f"{self.config.max_concurrent_jobs} workers)"
        )

        if foreground:
            logger.info("Running in foreground mode (Ctrl+C to stop)")
        else:
            logger.info("Running in background mode")

        # Clean up stale heartbeat file from previous run (if any)
        self._cleanup_stale_heartbeat_file()

        # Start watchdog thread to monitor main loop health
        self._watchdog_stop_event.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, name="CFDaemonWatchdog", daemon=False
        )
        self._watchdog_thread.start()
        logger.info("Watchdog thread started")

        # Start task watchdog thread to monitor stale tasks/jobs
        self._task_watchdog_stop_event.clear()
        self._task_watchdog_thread = threading.Thread(
            target=self._task_watchdog_loop, name="CFDaemonTaskWatchdog", daemon=False
        )
        self._task_watchdog_thread.start()
        logger.info("Task watchdog thread started")

        # Report success to parent
        self._report_status(True)

        self._run_foreground()
        return True

    def _wait_for_child_status(self, pipe_fd: int) -> bool:
        """
        Wait for child process status via pipe

        Args:
            pipe_fd: Read end of status pipe

        Returns:
            True if child started successfully, False otherwise
        """
        try:
            if sys.platform == 'win32':
                # Windows: Use threading with timeout since select() doesn't work with pipes
                result = {'status': None, 'error': None}

                def read_pipe():
                    try:
                        result['status'] = os.read(pipe_fd, 1024).decode().strip()
                    except Exception as e:
                        result['error'] = str(e)

                reader_thread = threading.Thread(target=read_pipe, daemon=True)
                reader_thread.start()
                reader_thread.join(timeout=5.0)

                os.close(pipe_fd)

                if reader_thread.is_alive():
                    # Timeout - thread is still reading
                    print(
                        "Daemon failed to start: timed out waiting for status confirmation",
                        file=sys.stderr,
                    )
                    return False

                if result['error']:
                    print(f"Error reading daemon status: {result['error']}", file=sys.stderr)
                    return False

                status = result['status']
                if status and status.startswith("OK"):
                    print("Daemon started successfully")
                    return True
                else:
                    print(f"Daemon failed to start: {status}", file=sys.stderr)
                    return False
            else:
                # Unix: Use select() for timeout
                import select
                ready, _, _ = select.select([pipe_fd], [], [], 5.0)

                if ready:
                    # Read status from pipe
                    status = os.read(pipe_fd, 1024).decode().strip()
                    os.close(pipe_fd)

                    if status.startswith("OK"):
                        print("Daemon started successfully")
                        return True
                    else:
                        print(f"Daemon failed to start: {status}", file=sys.stderr)
                        return False
                else:
                    # Timeout - child failed to report status (likely hung during init)
                    os.close(pipe_fd)
                    print(
                        "Daemon failed to start: timed out waiting for status confirmation",
                        file=sys.stderr,
                    )
                    print(
                        "(Child process may have hung during initialization)",
                        file=sys.stderr,
                    )
                    return False

        except Exception as e:
            print(f"Error waiting for daemon status: {e}", file=sys.stderr)
            try:
                os.close(pipe_fd)
            except Exception:
                pass
            return False

    def _watchdog_loop(self):
        """
        External watchdog thread that monitors main loop health.

        Runs in a separate thread to detect if the main loop hangs.
        If the main loop stops updating the heartbeat, logs critical
        error and can optionally restart the daemon.
        """
        logger.info("[WATCHDOG] Starting external watchdog thread")
        consecutive_warnings = 0

        while not self._watchdog_stop_event.is_set():
            try:
                # Wait so we can exit promptly when stop signal arrives
                if self._watchdog_stop_event.wait(10):
                    break

                # Check how long since main loop last updated heartbeat
                age = time.time() - self._main_loop_heartbeat

                if age > 120:  # 2 minutes without heartbeat
                    consecutive_warnings += 1
                    logger.critical(
                        f"[WATCHDOG] MAIN LOOP HUNG DETECTED! "
                        f"No heartbeat for {int(age)}s "
                        f"(warning {consecutive_warnings}/3)"
                    )

                    # On first critical warning, dump thread stacks for debugging
                    if consecutive_warnings == 1:
                        logger.critical(
                            "[WATCHDOG] Capturing thread dump for hang diagnosis..."
                        )
                        try:
                            # Capture thread stacks to string buffer
                            stack_buffer = io.StringIO()
                            faulthandler.dump_traceback(
                                file=stack_buffer, all_threads=True
                            )
                            stack_trace = stack_buffer.getvalue()

                            # Log thread stacks (may be long, but critical for debugging)
                            logger.critical(f"[WATCHDOG] Thread dump:\n{stack_trace}")

                            # Also write to dedicated file for post-mortem analysis
                            dump_file = (
                                self.config.log_dir
                                / f"thread_dump_{int(time.time())}.txt"
                            )
                            dump_file.write_text(stack_trace)
                            logger.critical(
                                f"[WATCHDOG] Thread dump saved to {dump_file}"
                            )
                        except Exception as dump_error:
                            logger.error(
                                f"[WATCHDOG] Failed to capture thread dump: {dump_error}"
                            )

                    if consecutive_warnings >= 3:  # 3 checks = 30+ seconds of hang
                        logger.critical(
                            "[WATCHDOG] Main loop confirmed hung for 2+ minutes. "
                            "Initiating forced restart..."
                        )
                        # Force daemon restart by sending SIGTERM to self, then SIGKILL fallback
                        self._force_stop_with_sigkill_fallback()
                        break

                elif age > 60:  # Warning at 60 seconds
                    logger.warning(
                        f"[WATCHDOG] Main loop slow: no heartbeat for {int(age)}s"
                    )
                    consecutive_warnings = 0
                else:
                    # Reset warning counter if heartbeat is fresh
                    if consecutive_warnings > 0:
                        logger.info(
                            f"[WATCHDOG] Main loop recovered (heartbeat age: {int(age)}s)"
                        )
                    consecutive_warnings = 0

            except Exception as e:
                logger.error(f"[WATCHDOG] Error in watchdog thread: {e}", exc_info=True)
                time.sleep(10)

        logger.info("[WATCHDOG] Watchdog thread stopped")

    def _task_watchdog_loop(self):
        """
        Task watchdog thread that monitors for stale tasks and jobs.

        This implements Critical Fix #1 (per-phase heartbeat detection) and
        Critical Fix #3 (watchdog enforcement).

        Runs periodically to:
        - Detect tasks with stale heartbeats (no activity for > threshold)
        - Detect jobs that have exceeded their timeout
        - Mark stale tasks/jobs as TIMED_OUT
        - Attempt graceful termination of stuck processes
        """
        from .state_machine import get_state_machine
        from .models import JobStatus

        logger.info("[TASK-WATCHDOG] Starting task watchdog thread")

        # Get state machine (lazy init)
        if self._state_machine is None:
            self._state_machine = get_state_machine(self.store)

        # Configuration
        heartbeat_timeout = 300  # 5 minutes without heartbeat = stale
        job_timeout_grace = 60  # Extra grace period before marking job timed out
        check_interval = 30  # Check every 30 seconds

        while not self._task_watchdog_stop_event.is_set():
            try:
                # Wait so we can exit promptly when stop signal arrives
                if self._task_watchdog_stop_event.wait(check_interval):
                    break

                # Skip if daemon is stopping
                if not self.running:
                    continue

                # --- Check for stale tasks ---
                metrics = get_metrics()
                metrics.inc_watchdog_iterations()

                try:
                    stale_tasks = self._state_machine.get_stale_tasks(heartbeat_timeout)
                    for task in stale_tasks:
                        log_structured(
                            logger,
                            logging.WARNING,
                            f"[TASK-WATCHDOG] Detected stale task: {task.name}",
                            event="stale_task_detected",
                            job_id=task.job_id,
                            task_id=task.id,
                            phase=task.name,
                            last_heartbeat=str(task.last_heartbeat)
                            if task.last_heartbeat
                            else None,
                            reason="heartbeat_timeout",
                        )
                        metrics.inc_watchdog_stale_tasks_detected()

                        # Mark task as timed out
                        try:
                            self._state_machine.timeout_task(task.id)
                            log_structured(
                                logger,
                                logging.INFO,
                                f"[TASK-WATCHDOG] Marked task {task.name} as TIMED_OUT",
                                event="task_timed_out_by_watchdog",
                                job_id=task.job_id,
                                task_id=task.id,
                                phase=task.name,
                            )
                        except Exception as e:
                            logger.error(
                                f"[TASK-WATCHDOG] Failed to timeout task {task.id}: {e}"
                            )

                except Exception as e:
                    logger.error(f"[TASK-WATCHDOG] Error checking stale tasks: {e}")

                # --- Check for stale/timed-out jobs ---
                try:
                    # Get jobs that have exceeded their timeout
                    running_jobs = self.store.list_jobs(
                        status=JobStatus.RUNNING, limit=100
                    )

                    for job in running_jobs:
                        if not job.started_at:
                            continue

                        # Get job timeout (from params or default)
                        timeout_minutes = job.params.get(
                            "timeout_minutes", self.config.default_job_timeout_minutes
                        )
                        timeout_seconds = (timeout_minutes * 60) + job_timeout_grace

                        elapsed = (datetime.now() - job.started_at).total_seconds()

                        if elapsed > timeout_seconds:
                            logger.warning(
                                f"[TASK-WATCHDOG] Job {job.id[:8]} exceeded timeout "
                                f"({int(elapsed)}s > {timeout_seconds}s)"
                            )

                            # Attempt to terminate any running processes
                            if self.runner:
                                terminate_fn = getattr(
                                    self.runner, "terminate_job_processes", None
                                )
                                if callable(terminate_fn):
                                    try:
                                        logger.info(
                                            f"[TASK-WATCHDOG] Terminating processes for job {job.id[:8]}"
                                        )
                                        terminate_fn(job.id)
                                    except Exception as term_err:
                                        logger.error(
                                            f"[TASK-WATCHDOG] Failed to terminate job processes: {term_err}"
                                        )

                            # Mark job as timed out via state machine
                            try:
                                self._state_machine.timeout_job(job.id)
                                logger.info(
                                    f"[TASK-WATCHDOG] Marked job {job.id[:8]} as TIMED_OUT"
                                )
                            except Exception as e:
                                logger.error(
                                    f"[TASK-WATCHDOG] Failed to timeout job {job.id}: {e}"
                                )

                except Exception as e:
                    logger.error(f"[TASK-WATCHDOG] Error checking stale jobs: {e}")

                # --- Check for stalled jobs (no activity but not timed out) ---
                stall_threshold = 1800  # 30 minutes without heartbeat = stalled
                try:
                    stalled_jobs = self._state_machine.get_stale_jobs(stall_threshold)
                    for job in stalled_jobs:
                        log_structured(
                            logger,
                            logging.WARNING,
                            f"[TASK-WATCHDOG] Detected stalled job: {job.id[:8]}",
                            event="stalled_job_detected",
                            job_id=job.id,
                            stall_threshold_seconds=stall_threshold,
                            reason="no_heartbeat",
                        )
                        metrics.inc_watchdog_stale_jobs_detected()

                        # Mark job as stalled
                        try:
                            self._state_machine.stall_job(
                                job.id,
                                reason=f"No task activity for {stall_threshold}s",
                            )
                            log_structured(
                                logger,
                                logging.INFO,
                                f"[TASK-WATCHDOG] Marked job {job.id[:8]} as STALLED",
                                event="job_stalled_by_watchdog",
                                job_id=job.id,
                                old_status="running",
                                new_status="stalled",
                            )
                        except Exception as e:
                            logger.error(
                                f"[TASK-WATCHDOG] Failed to stall job {job.id}: {e}"
                            )

                except Exception as e:
                    logger.error(f"[TASK-WATCHDOG] Error checking stalled jobs: {e}")

                # --- Check for completable jobs (all tasks terminal) ---
                try:
                    running_jobs = self.store.list_jobs(
                        status=JobStatus.RUNNING, limit=100
                    )

                    for job in running_jobs:
                        # Try to complete job if all required phases are done
                        try:
                            updated = self._state_machine.try_complete_job(job.id)
                            if updated:
                                log_structured(
                                    logger,
                                    logging.INFO,
                                    f"[TASK-WATCHDOG] Job {job.id[:8]} auto-completed with status {updated.status.value}",
                                    event="job_auto_completed",
                                    job_id=job.id,
                                    old_status="running",
                                    new_status=updated.status.value,
                                    reason="all_required_phases_complete",
                                )
                                metrics.inc_watchdog_auto_completions()
                        except Exception as e:
                            logger.error(
                                f"[TASK-WATCHDOG] Error trying to complete job {job.id}: {e}"
                            )

                except Exception as e:
                    logger.error(
                        f"[TASK-WATCHDOG] Error checking completable jobs: {e}"
                    )

            except Exception as e:
                logger.error(
                    f"[TASK-WATCHDOG] Error in task watchdog thread: {e}", exc_info=True
                )
                time.sleep(check_interval)

        logger.info("[TASK-WATCHDOG] Task watchdog thread stopped")

    def _run_foreground(self):
        """Run daemon in foreground"""
        try:
            # Health monitoring: track when main loop last progressed
            last_stats_logged = time.time()
            heartbeat_file = self.config.data_dir / "daemon_heartbeat.txt"
            iteration_count = 0
            last_stats_minute = -1  # Track which minute we last logged stats

            # Main loop - just keep alive while JobManager workers run
            logger.info("[DEBUG] Entering main loop, watchdog monitoring heartbeat")
            while self.running:
                try:
                    current_time = time.time()
                    iteration_count += 1

                    # Update heartbeat (main loop is still progressing)
                    # This is monitored by external watchdog thread
                    self._main_loop_heartbeat = current_time

                    # Write heartbeat file for external monitoring (every 5 iterations to reduce I/O)
                    if iteration_count % 5 == 0:
                        self._write_heartbeat_file(
                            heartbeat_file, current_time, iteration_count
                        )

                    # Health check: detect if stats loop has stopped progressing
                    time_since_stats = current_time - last_stats_logged
                    if time_since_stats > 180:  # 3 minutes without stats
                        logger.critical(
                            f"HEALTH CHECK FAILED: Stats loop has not logged for "
                            f"{int(time_since_stats)}s. Main loop still alive "
                            f"(iteration {iteration_count}) but stats may be stuck. "
                            f"Workers may not be processing jobs."
                        )
                        # Reset to avoid log spam (log once per 3 minutes)
                        last_stats_logged = current_time

                    # Periodically log stats (with error handling to prevent silent crashes)
                    # Use fresh time and avoid missed windows by tracking which minute we logged
                    current_minute = int(current_time // 60)
                    if current_minute != last_stats_minute:
                        try:
                            # DEBUG: Track exact timing of get_stats() call (INFO level for production debugging)
                            logger.info(
                                f"[HANG-DEBUG] About to call get_stats() at {time.time():.3f}"
                            )
                            stats = self.job_manager.get_stats()
                            logger.info(
                                f"[HANG-DEBUG] get_stats() returned at {time.time():.3f}"
                            )

                            logger.info(
                                f"Stats: {stats['jobs_running']} running, "
                                f"{stats['job_counts']} total jobs"
                            )
                            # Stats successfully logged - update tracking
                            last_stats_logged = current_time
                            last_stats_minute = current_minute
                        except Exception as e:
                            # Log error but continue running
                            logger.error(f"Failed to get stats: {e}", exc_info=True)
                            # Still update minute to avoid repeated errors
                            last_stats_minute = current_minute

                        # Check emergency stop status (once per minute with stats)
                        if EMERGENCY_STOP_AVAILABLE:
                            try:
                                if is_emergency_stop_active():
                                    logger.warning(
                                        "EMERGENCY STOP ACTIVE - New builds will be blocked, "
                                        "running builds will stop at next phase boundary. "
                                        "Run 'cfd emergency-resume' to clear."
                                    )
                            except Exception:
                                pass  # Don't let emergency stop check crash daemon

                    time.sleep(1)

                except Exception as e:
                    # Catch any loop iteration errors to prevent silent death
                    logger.error(f"Error in main loop iteration: {e}", exc_info=True)
                    time.sleep(1)  # Prevent tight error loop

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.stop()
        except Exception as e:
            # Catch any other unexpected exceptions to prevent silent daemon death
            logger.critical(f"Fatal error in daemon main loop: {e}", exc_info=True)
            self.stop()
            raise

    def stop(self):
        """Stop the daemon"""
        if not self.running:
            logger.warning("Daemon not running")
            return

        logger.info("Stopping Context Foundry Daemon...")
        self.running = False

        if self.dashboard_server:
            logger.info("Stopping dashboard server...")
            try:
                self.dashboard_server.stop()
            finally:
                self.dashboard_server = None

        if self.http_api_server:
            logger.info("Stopping HTTP API server...")
            try:
                self.http_api_server.stop()
            finally:
                self.http_api_server = None

        # Stop watchdog thread
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            logger.info("Stopping watchdog thread...")
            self._watchdog_stop_event.set()
            self._watchdog_thread.join(timeout=5.0)
            if self._watchdog_thread.is_alive():
                logger.warning("Watchdog thread did not stop gracefully")
            else:
                logger.info("Watchdog thread stopped")

        # Stop task watchdog thread
        if self._task_watchdog_thread and self._task_watchdog_thread.is_alive():
            logger.info("Stopping task watchdog thread...")
            self._task_watchdog_stop_event.set()
            self._task_watchdog_thread.join(timeout=5.0)
            if self._task_watchdog_thread.is_alive():
                logger.warning("Task watchdog thread did not stop gracefully")
            else:
                logger.info("Task watchdog thread stopped")

        # Clean up any active subprocess tasks before stopping workers
        logger.info("Cleaning up active subprocess tasks...")
        self.runner.cleanup_active_tasks()

        # Stop JobManager
        self.job_manager.stop(timeout=30.0)

        # Remove PID file
        self._remove_pid_file()

        # Clean up heartbeat file
        try:
            heartbeat_file = self.config.data_dir / "daemon_heartbeat.txt"
            if heartbeat_file.exists():
                heartbeat_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove heartbeat file: {e}")

        logger.info("CF Daemon stopped")

    def status(self) -> dict:
        """
        Get daemon status

        Returns:
            Dict with status information
        """
        return {
            "running": self.running,
            "pid": os.getpid(),
            "config": {
                "data_dir": str(self.config.data_dir),
                "log_dir": str(self.config.log_dir),
                "db_path": str(self.config.db_path),
                "max_concurrent_jobs": self.config.max_concurrent_jobs,
                "dashboard_host": self.config.dashboard_host,
                "dashboard_port": self.config.dashboard_port,
                "dashboard_enabled": self.config.enable_dashboard,
            },
            "job_manager": self.job_manager.get_stats() if self.running else None,
            "dashboard_running": bool(self.dashboard_server),
        }

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        """Return True if a PID is alive (or inaccessible but present)."""
        try:
            os.kill(pid, 0)
            return True
        except OSError as e:
            return e.errno == errno.EPERM

    def _cleanup_stale_heartbeat_file(self):
        """Remove a stale or unreadable heartbeat file from previous runs."""
        heartbeat_file = self.config.data_dir / "daemon_heartbeat.txt"
        if not heartbeat_file.exists():
            return

        try:
            lines = heartbeat_file.read_text().strip().split("\n")
            if len(lines) < 3:
                heartbeat_file.unlink()
                logger.info("Removed incomplete heartbeat file")
                return

            last_ts = int(lines[0])
            heartbeat_pid = int(lines[2])
            age = time.time() - last_ts

            # If another process is still alive, keep the file so status reflects that
            if heartbeat_pid != os.getpid() and self._pid_is_alive(heartbeat_pid):
                logger.warning(
                    f"Existing heartbeat belongs to live PID {heartbeat_pid}; keeping file"
                )
                return

            # If stale or from a dead process, remove so the new daemon writes fresh heartbeats
            if age > 300 or not self._pid_is_alive(heartbeat_pid):
                heartbeat_file.unlink()
                logger.info(
                    f"Removed stale heartbeat file from PID {heartbeat_pid} (age: {int(age)}s)"
                )
        except Exception as e:
            logger.warning(
                f"Failed to inspect heartbeat file: {e}; removing stale copy"
            )
            try:
                heartbeat_file.unlink()
            except Exception as unlink_error:
                logger.warning(
                    f"Failed to remove corrupted heartbeat file: {unlink_error}"
                )

    def _write_heartbeat_file(
        self, heartbeat_file: Path, current_time: float, iteration_count: int
    ):
        """Write heartbeat file with retries and atomic replace."""
        payload = f"{int(current_time)}\n{iteration_count}\n{os.getpid()}"
        tmp_path = heartbeat_file.with_suffix(".tmp")

        for attempt in range(3):
            try:
                heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_text(payload)
                tmp_path.replace(heartbeat_file)
                return
            except Exception as e:
                logger.error(
                    f"Failed to write heartbeat file (attempt {attempt + 1}/3): {e}",
                    exc_info=True,
                )
                time.sleep(0.2 * (attempt + 1))

        logger.critical(
            "Failed to persist heartbeat file after 3 attempts; health checks may be stale"
        )

    def _force_stop_with_sigkill_fallback(self, grace: int = 20):
        """Send SIGTERM to self and schedule SIGKILL if the process doesn't exit."""
        pid = os.getpid()
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            logger.error(f"[WATCHDOG] Failed to send SIGTERM: {e}")
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception as kill_error:
                logger.critical(
                    f"[WATCHDOG] Failed to SIGKILL after SIGTERM failure: {kill_error}"
                )
            return

        def _sigkill_timer():
            deadline = time.time() + grace
            while time.time() < deadline:
                if not self._pid_is_alive(pid):
                    return
                time.sleep(1)
            if self._pid_is_alive(pid):
                logger.critical(
                    "[WATCHDOG] Daemon did not exit after SIGTERM; sending SIGKILL"
                )
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception as kill_error:
                    logger.critical(f"[WATCHDOG] Failed to send SIGKILL: {kill_error}")

        threading.Thread(
            target=_sigkill_timer, name="CFDSigkillTimer", daemon=True
        ).start()


def _is_pid_running(pid: int) -> bool:
    """
    Check if a process with the given PID is running.

    Uses platform-specific methods:
    - Windows: Uses ctypes to call OpenProcess
    - Unix: Uses os.kill(pid, 0)

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise
    """
    if sys.platform == 'win32':
        # Windows: Use OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        # Unix: Use os.kill(pid, 0)
        try:
            os.kill(pid, 0)
            return True
        except OSError as e:
            # EPERM means process exists but we can't signal it
            if e.errno == errno.EPERM:
                return True
            return False


def get_running_daemon_pid(config: Optional[Config] = None) -> Optional[int]:
    """
    Get PID of running daemon instance

    Args:
        config: Configuration instance (loads default if not provided)

    Returns:
        PID if daemon is running, None otherwise
    """
    config = config or Config.load()

    if not config.pid_file.exists():
        return None

    try:
        pid = int(config.pid_file.read_text().strip())

        # Verify process exists
        if _is_pid_running(pid):
            return pid
        return None

    except (ValueError, FileNotFoundError):
        return None


def stop_running_daemon(config: Optional[Config] = None, timeout: int = 30) -> bool:
    """
    Stop a running daemon instance

    Args:
        config: Configuration instance (loads default if not provided)
        timeout: Seconds to wait for graceful shutdown

    Returns:
        True if daemon was stopped, False if not running
    """
    pid = get_running_daemon_pid(config)
    if not pid:
        return False

    logger.info(f"Sending SIGTERM to daemon (PID {pid})")

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Wait for process to exit
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                os.kill(pid, 0)  # Check if still alive
                time.sleep(0.5)
            except OSError:
                # Process exited
                logger.info("Daemon stopped gracefully")
                return True

        # Timeout exceeded, force kill
        logger.warning("Graceful shutdown timeout, sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
        return True

    except ProcessLookupError:
        # Process already gone
        return True
    except Exception as e:
        logger.error(f"Failed to stop daemon: {e}")
        return False

"""
CF Daemon Server

Main daemon process with signal handling, PID management, and service supervision.
"""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from .config import Config
from .store import Store
from .jobs import JobManager
from .runner import create_runner


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
        signal.signal(signal.SIGHUP, handle_reload_signal)

        logger.info("Signal handlers registered")

    def _daemonize(self) -> Optional[int]:
        """
        Daemonize the process using the Unix double-fork technique

        This detaches the process from the controlling terminal and runs it in the background.

        Returns:
            Pipe read fd for parent to check child status, or None if we're the child
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

        self.running = True

        logger.info(
            f"CF Daemon started (PID {os.getpid()}, "
            f"{self.config.max_concurrent_jobs} workers)"
        )

        if foreground:
            logger.info("Running in foreground mode (Ctrl+C to stop)")
        else:
            logger.info("Running in background mode")

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
        import select

        try:
            # Wait up to 5 seconds for child to report status
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

    def _run_foreground(self):
        """Run daemon in foreground"""
        try:
            # Main loop - just keep alive while JobManager workers run
            while self.running:
                time.sleep(1)

                # Periodically log stats (with error handling to prevent silent crashes)
                if int(time.time()) % 60 == 0:  # Every minute
                    try:
                        stats = self.job_manager.get_stats()
                        logger.info(
                            f"Stats: {stats['jobs_running']} running, "
                            f"{stats['job_counts']} total jobs"
                        )
                    except Exception as e:
                        # Log error but continue running
                        logger.error(f"Failed to get stats: {e}", exc_info=True)

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

        # Clean up any active subprocess tasks before stopping workers
        logger.info("Cleaning up active subprocess tasks...")
        self.runner.cleanup_active_tasks()

        # Stop JobManager
        self.job_manager.stop(timeout=30.0)

        # Remove PID file
        self._remove_pid_file()

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
            },
            "job_manager": self.job_manager.get_stats() if self.running else None,
        }


def get_running_daemon_pid(config: Optional[Config] = None) -> Optional[int]:
    """
    Get PID of running daemon instance

    Args:
        config: Configuration instance (loads default if not provided)

    Returns:
        PID if daemon is running, None otherwise
    """
    import errno

    config = config or Config.load()

    if not config.pid_file.exists():
        return None

    try:
        pid = int(config.pid_file.read_text().strip())

        # Verify process exists using os.kill(pid, 0)
        try:
            os.kill(pid, 0)
            return pid
        except OSError as e:
            # EPERM (errno 1) means process exists but we can't signal it
            # This happens in sandboxed/restricted environments
            # EPERM is sufficient proof the process exists
            if e.errno == errno.EPERM:
                logger.debug(
                    f"Permission denied signaling PID {pid}, but process exists"
                )
                return pid

            # ESRCH (errno 3) means no such process - PID file is stale
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

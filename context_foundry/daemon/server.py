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
        self.config_path = config_path  # Store for SIGHUP reload
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
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging"""
        log_file = self.config.log_dir / "cfd.log"
        self.config.log_dir.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper(), logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout),
            ],
        )

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
                logger.error(f"Daemon already running with PID {pid}")
                return True
            except OSError as e:
                # EPERM (errno 1) means process exists but we can't signal it
                # This happens in sandboxed/restricted environments
                # EPERM is sufficient proof the process exists
                if e.errno == errno.EPERM:
                    logger.debug(
                        f"Permission denied signaling PID {pid}, but process exists"
                    )
                    logger.error(f"Daemon already running with PID {pid}")
                    return True

                # ESRCH (errno 3) means no such process - stale PID file
                logger.warning(f"Removing stale PID file (PID {pid})")
                self.config.pid_file.unlink()
                return False

        except (ValueError, FileNotFoundError):
            # Invalid PID file
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

    def start(self, foreground: bool = False):
        """
        Start the daemon

        Args:
            foreground: Currently ignored - daemon always runs in foreground.
                       Background daemonization is not yet implemented.
        """
        # Check if already running
        if self._check_pid_file():
            raise RuntimeError("Daemon is already running")

        logger.info("Starting Context Foundry Daemon...")

        # Write PID file
        self._write_pid_file()

        # Setup signal handlers
        self._setup_signal_handlers()

        # Start JobManager
        self.job_manager.start(num_workers=self.config.max_concurrent_jobs)

        self.running = True

        logger.info(
            f"CF Daemon started (PID {os.getpid()}, "
            f"{self.config.max_concurrent_jobs} workers)"
        )

        # NOTE: Background daemonization not yet implemented
        # Daemon always runs in foreground regardless of 'foreground' parameter
        if not foreground:
            logger.warning(
                "Background mode requested but not implemented - running in foreground. "
                "Use Ctrl+C to stop or run in a terminal multiplexer (screen/tmux)."
            )
        else:
            logger.info("Running in foreground mode (Ctrl+C to stop)")

        self._run_foreground()

    def _run_foreground(self):
        """Run daemon in foreground"""
        try:
            # Main loop - just keep alive while JobManager workers run
            while self.running:
                time.sleep(1)

                # Periodically log stats
                if int(time.time()) % 60 == 0:  # Every minute
                    stats = self.job_manager.get_stats()
                    logger.info(
                        f"Stats: {stats['jobs_running']} running, "
                        f"{stats['job_counts']} total jobs"
                    )

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.stop()

    def stop(self):
        """Stop the daemon"""
        if not self.running:
            logger.warning("Daemon not running")
            return

        logger.info("Stopping Context Foundry Daemon...")
        self.running = False

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

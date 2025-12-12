#!/usr/bin/env python3
"""
Tests for CFDaemon daemonization functionality.

Tests critical daemonization behavior through unit tests with mocking:
- Fork handling and process isolation (mocked with os.fork)
- File descriptor management (mocked with os.dup2, sys.stdin/stdout/stderr)
- Logging configuration in background vs foreground mode
- Parent/child status communication via pipes
- PID file management with proper child PID
- Error reporting from child to parent

NOTE: These are primarily unit tests with extensive mocking. The "integration" tests
mock _daemonize(), _wait_for_child_status(), and _run_foreground() to test the
start() method's control flow without actually forking. True end-to-end integration
testing of daemonization requires manual testing or a test harness that can handle
real process forking (e.g., running ./tools/cfd start in a subprocess).

Running these tests:
    The package must be installed before running tests. From repo root:
        pip install -e .

    Then run tests with any of these methods:
        pytest tests/test_daemon_daemonization.py -v
        python3 -m pytest tests/test_daemon_daemonization.py -v
        PYTHONPATH=. pytest tests/test_daemon_daemonization.py -v

    Note: tests/conftest.py adds paths to sys.path, but only AFTER module collection.
    Since this test file imports context_foundry modules at the top level, the package
    must already be importable before pytest collects the test.
"""

import pytest
import tempfile
import shutil
import os
import logging
from pathlib import Path
from unittest.mock import patch
from context_foundry.daemon.server import CFDaemon
from context_foundry.daemon.config import Config


@pytest.mark.unit
class TestLoggingConfiguration:
    """Test logging setup in different modes"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.json"
        self.log_dir = Path(self.temp_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        # Clear root logger handlers
        logging.getLogger().handlers.clear()

    def test_setup_logging_foreground_mode(self):
        """Test logging setup in foreground mode includes both file and stream handlers"""
        # Create config pointing to our temp dir
        config = Config(
            data_dir=Path(self.temp_dir), log_dir=self.log_dir, log_level="INFO"
        )

        daemon = CFDaemon(config=config)
        daemon._setup_logging(background_mode=False)

        # Check root logger has 2 handlers (file + stream)
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 2

        # Check we have both FileHandler and StreamHandler
        handler_types = [type(h).__name__ for h in root_logger.handlers]
        assert "FileHandler" in handler_types
        assert "StreamHandler" in handler_types

        # Verify log file was created
        assert (self.log_dir / "cfd.log").exists()

    def test_setup_logging_background_mode(self):
        """Test logging setup in background mode only includes file handler"""
        config = Config(
            data_dir=Path(self.temp_dir), log_dir=self.log_dir, log_level="INFO"
        )

        daemon = CFDaemon(config=config)
        daemon._setup_logging(background_mode=True)

        # Check root logger has only 1 handler (file)
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1

        # Check it's a FileHandler
        assert type(root_logger.handlers[0]).__name__ == "FileHandler"

        # Verify log file was created
        assert (self.log_dir / "cfd.log").exists()

    def test_setup_logging_closes_old_handlers(self):
        """Test that setup_logging properly closes old handlers before clearing"""
        config = Config(
            data_dir=Path(self.temp_dir), log_dir=self.log_dir, log_level="INFO"
        )

        daemon = CFDaemon(config=config)

        # Setup logging first time
        daemon._setup_logging(background_mode=False)

        # Get references to old handlers
        old_handlers = list(logging.getLogger().handlers)

        # Setup logging again (simulating post-fork reconfiguration)
        daemon._setup_logging(background_mode=True)

        # Old handlers should have been closed
        # Note: We can't easily verify .close() was called without mocking,
        # but we can verify they were replaced
        new_handlers = list(logging.getLogger().handlers)
        assert len(new_handlers) == 1
        assert new_handlers[0] not in old_handlers


@pytest.mark.unit
class TestDaemonizationLogic:
    """Test daemonization fork logic and file descriptor handling"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("os.fork")
    @patch("os.pipe")
    @patch("os.close")
    def test_daemonize_first_fork_parent_returns_pipe(
        self, mock_close, mock_pipe, mock_fork
    ):
        """Test that parent process after first fork gets pipe read fd"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)

        # Simulate pipe creation
        mock_pipe.return_value = (3, 4)  # pipe_r=3, pipe_w=4

        # Simulate first fork - parent process (pid > 0)
        mock_fork.return_value = 1234  # child PID

        result = daemon._daemonize()

        # Parent should get pipe read fd
        assert result == 3

        # Parent should have closed write end
        mock_close.assert_called_with(4)

    @pytest.mark.skipif(
        os.environ.get("CI") is not None
        or os.environ.get("GITHUB_ACTIONS") is not None,
        reason="Daemon fork tests require real file descriptors, skipping in CI",
    )
    @patch("sys.stdin")
    @patch("sys.stdout")
    @patch("sys.stderr")
    @patch("os.fork")
    @patch("os.pipe")
    @patch("os.chdir")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("os.open")
    @patch("os.dup2")
    @patch("os.close")
    @patch("sys.exit")
    def test_daemonize_child_redirects_fds(
        self,
        mock_exit,
        mock_close,
        mock_dup2,
        mock_open,
        mock_umask,
        mock_setsid,
        mock_chdir,
        mock_pipe,
        mock_fork,
        mock_stderr,
        mock_stdout,
        mock_stdin,
    ):
        """Test that child process properly redirects file descriptors"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)

        # Mock file descriptors
        mock_stdin.fileno.return_value = 0
        mock_stdout.fileno.return_value = 1
        mock_stderr.fileno.return_value = 2

        # Simulate pipe creation
        mock_pipe.return_value = (3, 4)

        # Simulate both forks returning 0 (child process)
        mock_fork.side_effect = [0, 0]

        # Simulate /dev/null fd
        mock_open.return_value = 5

        result = daemon._daemonize()

        # Child should return None
        assert result is None

        # Verify process isolation calls
        mock_chdir.assert_called_once_with("/")
        mock_setsid.assert_called_once()
        mock_umask.assert_called_once_with(0)

        # Verify /dev/null was opened
        mock_open.assert_called_once_with(os.devnull, os.O_RDWR)

        # Verify stdin, stdout, stderr were redirected to /dev/null
        assert mock_dup2.call_count == 3
        mock_dup2.assert_any_call(5, 0)  # stdin
        mock_dup2.assert_any_call(5, 1)  # stdout
        mock_dup2.assert_any_call(5, 2)  # stderr

    @pytest.mark.skipif(
        os.environ.get("CI") is not None
        or os.environ.get("GITHUB_ACTIONS") is not None,
        reason="Daemon fork tests require real file descriptors, skipping in CI",
    )
    @patch("sys.stdin")
    @patch("sys.stdout")
    @patch("sys.stderr")
    @patch("os.fork")
    @patch("os.pipe")
    @patch("os.write")
    @patch("os.close")
    @patch("os.chdir")
    @patch("os.setsid")
    @patch("os.umask")
    @patch("sys.exit")
    def test_daemonize_second_fork_failure_writes_error(
        self,
        mock_exit,
        mock_umask,
        mock_setsid,
        mock_chdir,
        mock_close,
        mock_write,
        mock_pipe,
        mock_fork,
        mock_stderr,
        mock_stdout,
        mock_stdin,
    ):
        """Test that second fork failure writes error to status pipe"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)

        # Mock file descriptors (needed even though we won't reach the dup2 call)
        mock_stdin.fileno.return_value = 0
        mock_stdout.fileno.return_value = 1
        mock_stderr.fileno.return_value = 2

        # Simulate pipe creation
        mock_pipe.return_value = (3, 4)

        # First fork succeeds (child), second fork fails
        mock_fork.side_effect = [0, OSError("Fork failed")]

        # Configure sys.exit mock to raise SystemExit
        mock_exit.side_effect = SystemExit(1)

        with pytest.raises(SystemExit):
            daemon._daemonize()

        # Verify error was written to pipe
        assert mock_write.called
        call_args = mock_write.call_args[0]
        assert call_args[0] == 4  # Write end of pipe
        assert b"Second fork failed" in call_args[1]


@pytest.mark.unit
class TestStatusReporting:
    """Test parent/child status communication"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("os.write")
    @patch("os.close")
    def test_report_status_success(self, mock_close, mock_write):
        """Test reporting success status to parent"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)
        daemon._status_pipe = 4  # Simulated write end of pipe

        daemon._report_status(success=True)

        # Verify "OK" was written
        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == 4
        assert b"OK\n" == mock_write.call_args[0][1]

        # Verify pipe was closed
        mock_close.assert_called_once_with(4)

        # Verify _status_pipe attribute was removed
        assert not hasattr(daemon, "_status_pipe")

    @patch("os.write")
    @patch("os.close")
    def test_report_status_failure(self, mock_close, mock_write):
        """Test reporting failure status to parent"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)
        daemon._status_pipe = 4

        daemon._report_status(success=False, error_msg="Test error")

        # Verify error was written
        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == 4
        assert b"ERROR: Test error\n" == mock_write.call_args[0][1]

    def test_report_status_no_pipe(self):
        """Test reporting status when no pipe exists (should not crash)"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)

        # Should not raise exception
        daemon._report_status(success=True)
        daemon._report_status(success=False, error_msg="Test")


@pytest.mark.unit
class TestWaitForChildStatus:
    """Test parent waiting for child status"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("select.select")
    @patch("os.read")
    @patch("os.close")
    def test_wait_for_child_status_success(self, mock_close, mock_read, mock_select):
        """Test parent receives success status from child"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)

        # Simulate select returning pipe as ready
        mock_select.return_value = ([3], [], [])

        # Simulate reading "OK" from pipe
        mock_read.return_value = b"OK\n"

        result = daemon._wait_for_child_status(pipe_fd=3)

        assert result is True
        mock_close.assert_called_once_with(3)

    @patch("select.select")
    @patch("os.read")
    @patch("os.close")
    def test_wait_for_child_status_failure(self, mock_close, mock_read, mock_select):
        """Test parent receives failure status from child"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)

        # Simulate select returning pipe as ready
        mock_select.return_value = ([3], [], [])

        # Simulate reading error from pipe
        mock_read.return_value = b"ERROR: Failed to start\n"

        result = daemon._wait_for_child_status(pipe_fd=3)

        assert result is False
        mock_close.assert_called_once_with(3)

    @patch("select.select")
    @patch("os.close")
    def test_wait_for_child_status_timeout(self, mock_close, mock_select):
        """Test parent timeout waiting for child status"""
        config = Config(data_dir=Path(self.temp_dir), log_dir=self.log_dir)
        daemon = CFDaemon(config=config)

        # Simulate select timeout (no ready descriptors)
        mock_select.return_value = ([], [], [])

        result = daemon._wait_for_child_status(pipe_fd=3)

        # On timeout, treat as failure (child likely hung)
        assert result is False
        mock_close.assert_called_once_with(3)


@pytest.mark.integration
class TestDaemonStartIntegration:
    """
    Integration tests for daemon start control flow.

    Note: These tests mock the actual daemonization (_daemonize, _run_foreground)
    to test the start() method's logic without real forking. They verify that
    the correct code paths are taken in foreground vs background mode, but do not
    test actual fork behavior or file descriptor redirection.
    """

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.pid_dir = Path(self.temp_dir) / "pid"
        self.pid_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        # Clear root logger handlers
        logging.getLogger().handlers.clear()

    @patch.object(CFDaemon, "_daemonize")
    @patch.object(CFDaemon, "_run_foreground")
    def test_start_foreground_mode(self, mock_run, mock_daemonize):
        """Test starting daemon in foreground mode (no daemonization)"""
        config = Config(
            data_dir=Path(self.temp_dir),
            log_dir=self.log_dir,
            pid_file=self.pid_dir / "daemon.pid",
        )

        daemon = CFDaemon(config=config)

        # Mock _run_foreground to prevent actual loop
        mock_run.return_value = None

        result = daemon.start(foreground=True)

        # Should not call daemonize in foreground mode
        mock_daemonize.assert_not_called()

        # Should call _run_foreground
        mock_run.assert_called_once()

        # Should return True
        assert result is True

        # Should create PID file
        assert config.pid_file.exists()

        # Logging should be configured for foreground (stdout + file)
        assert len(logging.getLogger().handlers) == 2

    @patch.object(CFDaemon, "_daemonize")
    @patch.object(CFDaemon, "_wait_for_child_status")
    def test_start_background_mode_parent(self, mock_wait, mock_daemonize):
        """Test parent process in background mode"""
        config = Config(
            data_dir=Path(self.temp_dir),
            log_dir=self.log_dir,
            pid_file=self.pid_dir / "daemon.pid",
        )

        daemon = CFDaemon(config=config)

        # Simulate parent process (daemonize returns pipe fd)
        mock_daemonize.return_value = 3
        mock_wait.return_value = True

        result = daemon.start(foreground=False)

        # Parent should call daemonize
        mock_daemonize.assert_called_once()

        # Parent should wait for child status
        mock_wait.assert_called_once_with(3)

        # Should return child's success status
        assert result is True

    @patch.object(CFDaemon, "_daemonize")
    @patch.object(CFDaemon, "_report_status")
    @patch.object(CFDaemon, "_run_foreground")
    def test_start_background_mode_child(self, mock_run, mock_report, mock_daemonize):
        """Test child process in background mode"""
        config = Config(
            data_dir=Path(self.temp_dir),
            log_dir=self.log_dir,
            pid_file=self.pid_dir / "daemon.pid",
        )

        daemon = CFDaemon(config=config)

        # Simulate child process (daemonize returns None)
        mock_daemonize.return_value = None
        mock_run.return_value = None

        result = daemon.start(foreground=False)

        # Child should report success
        mock_report.assert_called_with(True)

        # Child should call _run_foreground
        mock_run.assert_called_once()

        # Should return True
        assert result is True

        # Logging should be configured for background (file only)
        assert len(logging.getLogger().handlers) == 1
        assert type(logging.getLogger().handlers[0]).__name__ == "FileHandler"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

#!/usr/bin/env python3
"""
Critical path tests for EvolutionDaemon
Covers uncovered branches and error handling scenarios
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import signal

from tools.evolution.daemon import EvolutionDaemon


class TestDaemonStartMethod(unittest.TestCase):
    """Test daemon start method and initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.json"

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("tools.evolution.daemon.setup_logging")
    def test_start_returns_false_if_already_running(self, mock_setup_logging):
        """Test that start returns False if daemon is already running"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock is_running to return True
        with patch.object(daemon, "is_running", return_value=True):
            result = daemon.start()

        self.assertFalse(result)
        mock_logger.error.assert_called_once()

    @patch("tools.evolution.daemon.setup_logging")
    def test_start_calls_cleanup_on_exception(self, mock_setup_logging):
        """Test that start calls cleanup even when main_loop raises exception"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock methods
        with patch.object(daemon, "is_running", return_value=False):
            with patch.object(daemon, "_write_pid"):
                with patch.object(daemon, "setup_signal_handlers"):
                    with patch.object(
                        daemon, "main_loop", side_effect=RuntimeError("Test error")
                    ):
                        with patch.object(daemon, "cleanup") as mock_cleanup:
                            daemon.start()

                            # Verify cleanup was called despite exception
                            mock_cleanup.assert_called_once()

    @patch("tools.evolution.daemon.setup_logging")
    def test_start_logs_fatal_error_on_exception(self, mock_setup_logging):
        """Test that fatal errors are logged"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        with patch.object(daemon, "is_running", return_value=False):
            with patch.object(daemon, "_write_pid"):
                with patch.object(daemon, "setup_signal_handlers"):
                    with patch.object(
                        daemon, "main_loop", side_effect=ValueError("Fatal!")
                    ):
                        with patch.object(daemon, "cleanup"):
                            daemon.start()

        # Verify error was logged with exc_info
        error_calls = [
            c for c in mock_logger.error.call_args_list if "Fatal error" in str(c)
        ]
        self.assertGreater(len(error_calls), 0)


class TestDaemonMainLoopPRHandling(unittest.TestCase):
    """Test main loop PR detection and task queuing"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("tools.evolution.daemon.setup_logging")
    def test_main_loop_pauses_when_prs_open(self, mock_setup_logging):
        """Test that main loop pauses when PRs are open"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()
        daemon.stop_requested = False

        check_count = [0]

        def mock_check_prs():
            check_count[0] += 1
            if check_count[0] >= 2:
                daemon.stop_requested = True
            return [{"number": 123, "title": "Test PR"}]

        with patch.object(daemon, "_check_open_prs", side_effect=mock_check_prs):
            with patch.object(daemon, "_interruptible_sleep") as mock_sleep:
                with patch.object(daemon, "resource_manager") as mock_rm:
                    daemon.main_loop()

        # Verify sleep was called (daemon paused)
        self.assertGreater(mock_sleep.call_count, 0)
        # Verify it logged pause message
        log_messages = [str(c) for c in mock_logger.info.call_args_list]
        paused_messages = [m for m in log_messages if "PAUSED" in m]
        self.assertGreater(len(paused_messages), 0)


class TestDaemonResourceChecks(unittest.TestCase):
    """Test resource checking in main loop"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_main_loop_skips_tasks_when_resources_unavailable(self, mock_setup_logging):
        """Test that main loop skips task execution when resources unavailable"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()
        daemon.stop_requested = False

        check_count = [0]

        def mock_can_accept():
            check_count[0] += 1
            if check_count[0] >= 2:
                daemon.stop_requested = True
            return False, "CPU limit exceeded"

        with patch.object(daemon, "_check_open_prs", return_value=[]):
            with patch.object(
                daemon.resource_manager, "can_accept_task", side_effect=mock_can_accept
            ):
                with patch.object(daemon, "_interruptible_sleep") as mock_sleep:
                    daemon.main_loop()

        # Verify daemon paused due to resource limits
        self.assertGreater(mock_sleep.call_count, 0)


class TestDaemonSignalHandlerWindows(unittest.TestCase):
    """Test signal handler setup on Windows (no SIGHUP)"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_setup_signal_handlers_handles_missing_sighup(self, mock_setup_logging):
        """Test that setup_signal_handlers handles missing SIGHUP gracefully"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock signal.signal to raise AttributeError for SIGHUP
        original_signal = signal.signal

        def mock_signal(signum, handler):
            if signum == signal.SIGHUP:
                raise AttributeError("SIGHUP not available")
            return original_signal(signum, handler)

        with patch("signal.signal", side_effect=mock_signal):
            # Should not raise exception
            daemon.setup_signal_handlers()


class TestCheckOpenPRsGitHub(unittest.TestCase):
    """Test _check_open_prs GitHub API integration"""

    @patch("tools.evolution.daemon.setup_logging")
    @patch("subprocess.run")
    def test_check_open_prs_handles_gh_not_installed(
        self, mock_run, mock_setup_logging
    ):
        """Test that check_open_prs handles missing gh CLI gracefully"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock subprocess to raise FileNotFoundError
        mock_run.side_effect = FileNotFoundError("gh not found")

        result = daemon._check_open_prs()

        # Should return empty list
        self.assertEqual(result, [])

    @patch("tools.evolution.daemon.setup_logging")
    @patch("subprocess.run")
    def test_check_open_prs_handles_subprocess_error(
        self, mock_run, mock_setup_logging
    ):
        """Test that check_open_prs handles subprocess errors"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock subprocess to raise error
        mock_run.side_effect = RuntimeError("Subprocess failed")

        result = daemon._check_open_prs()

        # Should return empty list
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

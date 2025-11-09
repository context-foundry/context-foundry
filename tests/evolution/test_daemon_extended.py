#!/usr/bin/env python3
"""
Extended tests for Evolution Daemon covering critical paths
Tests daemon lifecycle, task execution, resource management, and error handling.
"""

import os
import json
import pytest
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from tools.evolution.daemon import EvolutionDaemon, setup_logging
from tools.evolution.task_queue import Task, TaskType, TaskStatus


@pytest.fixture
def temp_config():
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        config = {
            "daemon": {
                "enabled": True,
                "poll_interval_seconds": 1,  # Short interval for testing
                "max_concurrent_tasks": 2,
                "log_level": "INFO",
            },
            "modes": {
                "self_improvement": {"enabled": True, "priority": 8},
                "chaos_creative": {"enabled": True, "priority": 5},
                "research_discovery": {"enabled": False, "priority": 9},
            },
            "resources": {
                "max_cpu_percent": 80,
                "max_memory_gb": 16,
                "active_hours": [0, 23],
            },
        }
        json.dump(config, f)
        config_path = f.name

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.unlink(config_path)


@pytest.fixture
def daemon(temp_config):
    """Create EvolutionDaemon instance."""
    daemon = EvolutionDaemon(temp_config)
    yield daemon
    # Cleanup
    daemon.cleanup()


class TestDaemonInitialization:
    """Test daemon initialization and configuration."""

    def test_init_with_config_file(self, temp_config):
        """Test initialization with config file."""
        daemon = EvolutionDaemon(temp_config)
        assert daemon.config is not None
        assert daemon.config["daemon"]["poll_interval_seconds"] == 1
        assert daemon.config["daemon"]["max_concurrent_tasks"] == 2
        daemon.cleanup()

    def test_init_without_config_file(self):
        """Test initialization without config file (uses defaults)."""
        daemon = EvolutionDaemon(config_path="/nonexistent/path.json")
        assert daemon.config is not None
        assert daemon.config["daemon"]["poll_interval_seconds"] == 60
        assert daemon.config["daemon"]["enabled"] is True
        daemon.cleanup()

    def test_init_creates_components(self, daemon):
        """Test that initialization creates all required components."""
        assert daemon.task_queue is not None
        assert daemon.resource_manager is not None
        assert len(daemon.modes) == 3
        assert TaskType.SELF_IMPROVEMENT.value in daemon.modes
        assert TaskType.CHAOS_CREATIVE.value in daemon.modes
        assert TaskType.RESEARCH.value in daemon.modes

    def test_init_sets_initial_state(self, daemon):
        """Test that initialization sets correct initial state."""
        assert daemon.running is False
        assert daemon.stop_requested is False
        assert len(daemon.active_tasks) == 0
        assert daemon.poll_count == 0
        assert daemon.was_paused_for_pr is False


class TestDaemonPIDManagement:
    """Test PID file management."""

    def test_write_pid(self, daemon):
        """Test writing PID file."""
        daemon._write_pid()
        assert daemon.pid_file.exists()
        assert daemon.pid is not None

        # Read PID from file
        with open(daemon.pid_file) as f:
            file_pid = int(f.read().strip())
        assert file_pid == daemon.pid

    def test_get_pid(self, daemon):
        """Test getting PID from file."""
        daemon._write_pid()
        pid = daemon.get_pid()
        assert pid == daemon.pid

    def test_get_pid_no_file(self, daemon):
        """Test getting PID when file doesn't exist."""
        pid = daemon.get_pid()
        assert pid is None

    def test_remove_pid(self, daemon):
        """Test removing PID file."""
        daemon._write_pid()
        assert daemon.pid_file.exists()
        daemon._remove_pid()
        assert not daemon.pid_file.exists()

    def test_is_running_false_no_pid(self, daemon):
        """Test is_running returns False when no PID file."""
        assert daemon.is_running() is False

    def test_is_running_true_when_running(self, daemon):
        """Test is_running returns True for current process."""
        daemon._write_pid()
        assert daemon.is_running() is True

    def test_is_running_false_for_dead_process(self, daemon):
        """Test is_running returns False for non-existent PID."""
        daemon.pid_file.parent.mkdir(parents=True, exist_ok=True)
        # Write a PID that doesn't exist (99999 unlikely to be running)
        with open(daemon.pid_file, "w") as f:
            f.write("99999")
        assert daemon.is_running() is False


class TestDaemonSignalHandling:
    """Test signal handling."""

    def test_handle_sigterm(self, daemon):
        """Test SIGTERM handler sets stop_requested."""
        daemon._handle_sigterm(None, None)
        assert daemon.stop_requested is True

    def test_handle_sigint(self, daemon):
        """Test SIGINT handler sets stop_requested."""
        daemon._handle_sigint(None, None)
        assert daemon.stop_requested is True

    def test_handle_sighup_reloads_config(self, temp_config):
        """Test SIGHUP handler reloads configuration."""
        # Create daemon with temp config
        daemon = EvolutionDaemon(temp_config)
        original_interval = daemon.config["daemon"]["poll_interval_seconds"]

        # Modify config file
        with open(temp_config, "w") as f:
            new_config = daemon.config.copy()
            new_config["daemon"]["poll_interval_seconds"] = 999
            json.dump(new_config, f)

        # Store the config path for reload
        original_path = temp_config
        daemon.config_path = original_path

        # Mock _load_config to actually load from the file we just modified
        with patch.object(daemon, "_load_config") as mock_load:
            # Make _load_config return the new config
            with open(temp_config) as f:
                new_config = json.load(f)
            mock_load.return_value = new_config

            # Trigger reload
            daemon._handle_sighup(None, None)

            # Verify config was reloaded
            assert daemon.config["daemon"]["poll_interval_seconds"] == 999

        daemon.cleanup()


class TestDaemonInterruptibleSleep:
    """Test interruptible sleep functionality."""

    def test_interruptible_sleep_completes(self, daemon):
        """Test interruptible sleep completes normally."""
        start = time.time()
        daemon._interruptible_sleep(2)
        elapsed = time.time() - start
        assert elapsed >= 2
        assert elapsed < 3  # Should not overshoot significantly

    def test_interruptible_sleep_interrupted(self, daemon):
        """Test interruptible sleep can be interrupted."""
        daemon.stop_requested = False

        # Set stop_requested after 1 second
        def set_stop():
            time.sleep(1)
            daemon.stop_requested = True

        import threading

        thread = threading.Thread(target=set_stop)
        thread.start()

        start = time.time()
        daemon._interruptible_sleep(10)  # Try to sleep 10 seconds
        elapsed = time.time() - start

        # Should wake up after ~1 second, not 10
        assert elapsed < 5
        thread.join()


class TestDaemonTaskExecution:
    """Test task execution."""

    def test_execute_task_success(self, daemon):
        """Test successful task execution."""
        # Create a mock task
        task = Task(
            id="test-task-1",
            type=TaskType.SELF_IMPROVEMENT.value,
            status=TaskStatus.PENDING.value,
            priority=5,
            params={"test": "value"},
            created_at=datetime.now().isoformat(),
        )

        # Mock the mode execution
        mock_result = Mock()
        mock_result.output = {"status": "completed"}
        mock_result.error = None

        with patch.object(
            daemon.modes[TaskType.SELF_IMPROVEMENT.value],
            "execute_task",
            return_value=mock_result,
        ):
            with patch.object(
                daemon.modes[TaskType.SELF_IMPROVEMENT.value],
                "validate_result",
                return_value=True,
            ):
                with patch.object(
                    daemon.task_queue, "update_task_status"
                ) as mock_update:
                    daemon._execute_task(task)

                    # Verify task was marked as completed
                    mock_update.assert_called_once()
                    args = mock_update.call_args
                    assert args[0][0] == task.id
                    assert args[0][1] == TaskStatus.COMPLETED.value

    def test_execute_task_failure(self, daemon):
        """Test task execution failure."""
        task = Task(
            id="test-task-fail",
            type=TaskType.SELF_IMPROVEMENT.value,
            status=TaskStatus.PENDING.value,
            priority=5,
            params={},
            created_at=datetime.now().isoformat(),
        )

        # Mock mode to raise exception
        with patch.object(
            daemon.modes[TaskType.SELF_IMPROVEMENT.value],
            "execute_task",
            side_effect=Exception("Test error"),
        ):
            with patch.object(daemon.task_queue, "should_retry", return_value=False):
                with patch.object(
                    daemon.task_queue, "update_task_status"
                ) as mock_update:
                    daemon._execute_task(task)

                    # Verify task was marked as failed
                    mock_update.assert_called_once()
                    args = mock_update.call_args
                    assert args[0][0] == task.id
                    assert args[0][1] == TaskStatus.FAILED.value

    def test_execute_task_with_retry(self, daemon):
        """Test task retry on failure."""
        task = Task(
            id="test-task-retry",
            type=TaskType.SELF_IMPROVEMENT.value,
            status=TaskStatus.PENDING.value,
            priority=5,
            params={},
            created_at=datetime.now().isoformat(),
            max_retries=3,
            retry_count=0,
        )

        # Mock mode to raise exception
        with patch.object(
            daemon.modes[TaskType.SELF_IMPROVEMENT.value],
            "execute_task",
            side_effect=Exception("Temporary error"),
        ):
            with patch.object(daemon.task_queue, "should_retry", return_value=True):
                with patch.object(daemon.task_queue, "retry_task") as mock_retry:
                    daemon._execute_task(task)

                    # Verify task was retried
                    mock_retry.assert_called_once_with(task.id)

    def test_execute_task_unknown_type(self, daemon):
        """Test execution of task with unknown type."""
        task = Task(
            id="test-unknown",
            type="unknown_type",
            status=TaskStatus.PENDING.value,
            priority=5,
            params={},
            created_at=datetime.now().isoformat(),
        )

        with patch.object(daemon.task_queue, "should_retry", return_value=False):
            with patch.object(daemon.task_queue, "update_task_status") as mock_update:
                daemon._execute_task(task)

                # Should mark as failed
                mock_update.assert_called_once()
                args = mock_update.call_args
                assert args[0][1] == TaskStatus.FAILED.value


class TestDaemonStop:
    """Test daemon stop functionality."""

    def test_stop_graceful(self, daemon):
        """Test graceful stop waits for active tasks."""
        daemon.active_tasks = {"task-1": Mock()}

        # Mock the active tasks to clear after a short delay
        def clear_tasks():
            time.sleep(0.5)
            daemon.active_tasks.clear()

        import threading

        thread = threading.Thread(target=clear_tasks)
        thread.start()

        start = time.time()
        daemon.stop(graceful=True)
        elapsed = time.time() - start

        # Should have waited for tasks to clear
        assert elapsed >= 0.5
        assert daemon.stop_requested is True
        assert daemon.running is False
        thread.join()

    def test_stop_immediate(self, daemon):
        """Test immediate stop doesn't wait."""
        daemon.active_tasks = {"task-1": Mock()}

        start = time.time()
        daemon.stop(graceful=False)
        elapsed = time.time() - start

        # Should return immediately
        assert elapsed < 1
        assert daemon.stop_requested is True
        assert daemon.running is False


class TestDaemonCleanup:
    """Test daemon cleanup."""

    def test_cleanup_removes_pid(self, daemon):
        """Test cleanup removes PID file."""
        daemon._write_pid()
        assert daemon.pid_file.exists()

        daemon.cleanup()
        assert not daemon.pid_file.exists()

    def test_cleanup_closes_queue(self, daemon):
        """Test cleanup closes task queue."""
        with patch.object(daemon.task_queue, "close") as mock_close:
            daemon.cleanup()
            mock_close.assert_called_once()


class TestDaemonResourceManagement:
    """Test resource management integration."""

    def test_respects_resource_limits(self, daemon):
        """Test daemon respects resource limits."""
        # Mock resource manager to deny tasks
        with patch.object(
            daemon.resource_manager,
            "can_accept_task",
            return_value=(False, "CPU limit exceeded"),
        ):
            # Should not execute tasks when resources are exhausted
            with patch.object(daemon.task_queue, "get_next_task") as mock_get:
                # Set up minimal main loop iteration
                daemon.stop_requested = False

                # Run one iteration
                with patch.object(
                    daemon,
                    "_interruptible_sleep",
                    side_effect=lambda x: setattr(daemon, "stop_requested", True),
                ):
                    daemon.main_loop()

                # Should not have tried to get tasks
                mock_get.assert_not_called()


class TestDaemonPRDetection:
    """Test PR detection and pausing."""

    @patch("subprocess.run")
    def test_check_open_prs_success(self, mock_run, daemon):
        """Test successful PR detection."""
        # Mock git remote command
        mock_run.return_value = Mock(
            returncode=0, stdout="https://github.com/owner/repo.git\n"
        )

        # Mock requests
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "number": 123,
                    "head": {"ref": "self-improvement/test-branch"},
                    "title": "Test PR",
                }
            ]
            mock_get.return_value = mock_response

            prs = daemon._check_open_prs()
            assert len(prs) == 1
            assert prs[0]["number"] == 123

    @patch("subprocess.run")
    def test_check_open_prs_no_git(self, mock_run, daemon):
        """Test PR detection when git fails."""
        mock_run.return_value = Mock(returncode=1, stdout="")
        prs = daemon._check_open_prs()
        assert prs == []


class TestDaemonIntegration:
    """Integration tests for complete workflows."""

    def test_daemon_lifecycle(self, daemon):
        """Test complete daemon lifecycle."""
        # Should start in stopped state
        assert daemon.is_running() is False

        # Write PID to simulate starting
        daemon._write_pid()
        assert daemon.is_running() is True

        # Cleanup
        daemon.cleanup()
        assert daemon.is_running() is False

    def test_config_reload(self, temp_config):
        """Test configuration can be reloaded."""
        # Create daemon with temp config
        daemon = EvolutionDaemon(temp_config)
        original_interval = daemon.config["daemon"]["poll_interval_seconds"]

        # Modify config
        with open(temp_config, "w") as f:
            new_config = daemon.config.copy()
            new_config["daemon"]["poll_interval_seconds"] = original_interval + 100
            json.dump(new_config, f)

        # Mock _load_config to actually load from the file we modified
        with patch.object(daemon, "_load_config") as mock_load:
            # Make _load_config return the new config
            with open(temp_config) as f:
                new_cfg = json.load(f)
            mock_load.return_value = new_cfg

            # Reload
            daemon._handle_sighup(None, None)

            assert (
                daemon.config["daemon"]["poll_interval_seconds"]
                == original_interval + 100
            )

        daemon.cleanup()


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_logging_creates_log_dir(self):
        """Test that setup_logging creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = setup_logging(log_dir)

            assert log_dir.exists()
            assert log_dir.is_dir()
            assert logger is not None

    def test_setup_logging_creates_log_file(self):
        """Test that setup_logging creates log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            logger = setup_logging(log_dir)

            log_file = log_dir / "daemon.log"

            # Write a test message
            logger.info("Test message")

            # Log file should exist and contain the message
            assert log_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

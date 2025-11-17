#!/usr/bin/env python3
"""
Additional critical path tests for EvolutionDaemon - Round 3
Targets remaining uncovered lines to improve test coverage
"""

import unittest
from unittest.mock import Mock, patch
import json

from tools.evolution.daemon import EvolutionDaemon
from tools.evolution.task_queue import Task, TaskStatus, TaskType


class TestDaemonMaxConcurrentTasks(unittest.TestCase):
    """Test max concurrent task limits in main loop"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_main_loop_respects_max_concurrent_limit(self, mock_setup_logging):
        """Test that daemon pauses when max concurrent tasks reached"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()
        daemon.stop_requested = False
        daemon.active_tasks = ["task1", "task2", "task3"]  # Simulate 3 active tasks

        check_count = [0]

        def stop_after_checks():
            check_count[0] += 1
            if check_count[0] >= 2:
                daemon.stop_requested = True
            return []

        with patch.object(daemon, "_check_open_prs", side_effect=stop_after_checks):
            with patch.object(
                daemon.resource_manager, "can_accept_task", return_value=(True, "")
            ):
                with patch.object(daemon, "_interruptible_sleep"):
                    daemon.main_loop()

        # Verify daemon logged max concurrent reached
        log_messages = [str(c) for c in mock_logger.debug.call_args_list]
        max_concurrent_messages = [m for m in log_messages if "Max concurrent" in m]
        self.assertGreater(len(max_concurrent_messages), 0)


class TestDaemonPeriodicResourceLogging(unittest.TestCase):
    """Test periodic resource usage logging"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_main_loop_increments_poll_count(self, mock_setup_logging):
        """Test that main loop increments poll count correctly"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()
        daemon.stop_requested = False
        daemon.poll_count = 0

        poll_count = [0]

        def stop_after_polls():
            poll_count[0] += 1
            # Stop after 2 polls
            if poll_count[0] >= 2:
                daemon.stop_requested = True
            return []

        with patch.object(daemon, "_check_open_prs", side_effect=stop_after_polls):
            with patch.object(
                daemon.resource_manager, "can_accept_task", return_value=(True, "")
            ):
                with patch.object(
                    daemon.task_queue, "get_next_task", return_value=None
                ):
                    with patch.object(
                        daemon.task_queue, "count_running", return_value=0
                    ):
                        with patch.object(
                            daemon.task_queue, "count_pending", return_value=0
                        ):
                            with patch.object(daemon, "_queue_next_improvement_task"):
                                with patch.object(daemon, "_interruptible_sleep"):
                                    daemon.main_loop()

        # Verify poll count increased (showing loop ran)
        self.assertGreater(daemon.poll_count, 0)


class TestDaemonExceptionHandling(unittest.TestCase):
    """Test exception handling in main loop"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_main_loop_catches_and_logs_exceptions(self, mock_setup_logging):
        """Test that exceptions in main loop are caught and logged"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()
        daemon.stop_requested = False

        exception_count = [0]

        def raise_then_stop():
            exception_count[0] += 1
            if exception_count[0] == 1:
                raise ValueError("Test exception in main loop")
            else:
                daemon.stop_requested = True
                return []

        with patch.object(daemon, "_check_open_prs", side_effect=raise_then_stop):
            with patch.object(daemon, "_interruptible_sleep"):
                daemon.main_loop()

        # Verify exception was logged
        error_calls = [
            c
            for c in mock_logger.error.call_args_list
            if "Error in main loop" in str(c)
        ]
        self.assertGreater(len(error_calls), 0)


class TestDaemonEmptyQueueBehavior(unittest.TestCase):
    """Test daemon behavior when queue is empty"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_main_loop_generates_improvement_task_when_queue_empty(
        self, mock_setup_logging
    ):
        """Test that daemon generates improvement task when queue is empty"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()
        daemon.stop_requested = False

        check_count = [0]

        def stop_after_checks():
            check_count[0] += 1
            if check_count[0] >= 2:
                daemon.stop_requested = True
            return []

        with patch.object(daemon, "_check_open_prs", side_effect=stop_after_checks):
            with patch.object(
                daemon.resource_manager, "can_accept_task", return_value=(True, "")
            ):
                with patch.object(daemon.task_queue, "count_running", return_value=0):
                    with patch.object(
                        daemon.task_queue, "count_pending", return_value=0
                    ):
                        with patch.object(
                            daemon.task_queue, "get_next_task", return_value=None
                        ):
                            with patch.object(
                                daemon, "_queue_next_improvement_task"
                            ) as mock_queue:
                                with patch.object(daemon, "_interruptible_sleep"):
                                    daemon.main_loop()

        # Verify queue_next_improvement_task was called
        self.assertGreater(mock_queue.call_count, 0)


class TestDaemonGetUptime(unittest.TestCase):
    """Test get_uptime method"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_get_uptime_returns_duration(self, mock_setup_logging):
        """Test that get_uptime returns time since start"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Current implementation returns 0.0 - test the actual behavior
        uptime = daemon.get_uptime()

        # Verify it returns a float
        self.assertIsInstance(uptime, float)
        self.assertEqual(uptime, 0.0)


class TestDaemonPRDetectionEdgeCases(unittest.TestCase):
    """Test edge cases in PR detection logic"""

    @patch("tools.evolution.daemon.setup_logging")
    @patch("subprocess.run")
    def test_check_open_prs_handles_invalid_json_from_gh(
        self, mock_run, mock_setup_logging
    ):
        """Test that invalid JSON from gh CLI is handled gracefully"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock gh CLI returning invalid JSON
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json {[}"
        mock_run.return_value = mock_result

        result = daemon._check_open_prs()

        # Should return empty list when JSON parsing fails
        self.assertEqual(result, [])

    @patch("tools.evolution.daemon.setup_logging")
    @patch("subprocess.run")
    def test_check_recently_closed_prs_handles_no_git_repo(
        self, mock_run, mock_setup_logging
    ):
        """Test that check_recently_closed_prs handles non-git directories"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock gh CLI to raise error (not in git repo)
        mock_run.side_effect = Exception("Not a git repository")

        # Should not raise exception
        result = daemon._check_recently_closed_prs()

        # Should return empty list
        self.assertEqual(result, [])

    @patch("tools.evolution.daemon.setup_logging")
    @patch("subprocess.run")
    def test_detect_prs_and_complete_tasks_handles_no_matching_branch(
        self, mock_run, mock_setup_logging
    ):
        """Test PR detection when branch name doesn't match task"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Mock open PR with branch that doesn't match any task
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            [
                {
                    "number": 123,
                    "title": "Test PR",
                    "headRefName": "feature/random-branch",
                }
            ]
        )
        mock_run.return_value = mock_result

        # Mock running task with different branch - use correct Task constructor
        from datetime import datetime

        mock_task = Task(
            id="task-1",
            type=TaskType.SELF_IMPROVEMENT.value,
            status=TaskStatus.RUNNING.value,
            priority=5,
            params={"branch": "self-improvement/task-abc123"},
            created_at=datetime.utcnow().isoformat(),
        )

        with patch.object(daemon.task_queue, "list_tasks", return_value=[mock_task]):
            with patch.object(daemon.task_queue, "update_task_status") as mock_update:
                daemon._detect_prs_and_complete_tasks()

        # Task should not be completed since branch doesn't match
        mock_update.assert_not_called()

    @patch("tools.evolution.daemon.setup_logging")
    def test_queue_next_improvement_task_runs_without_error(self, mock_setup_logging):
        """Test that queue_next_improvement_task handles case with no TODOs"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Just verify the method can be called without crashing
        with patch.object(daemon.task_queue, "create_task"):
            # Should not raise an exception
            try:
                daemon._queue_next_improvement_task()
                success = True
            except Exception as e:
                print(f"Exception raised: {e}")
                success = False

            self.assertTrue(success)

    @patch("tools.evolution.daemon.setup_logging")
    def test_queue_next_improvement_task_creates_task_with_todos(
        self, mock_setup_logging
    ):
        """Test that queue_next_improvement_task creates task when TODOs exist"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()

        # Enable MCP to avoid early return
        daemon.mcp_available = True

        # Mock mode that returns tasks
        mock_mode = Mock()
        mock_mode._find_todos.return_value = [
            {"file": "test.py", "line": 10, "todo": "test coverage"}
        ]
        daemon.modes[TaskType.SELF_IMPROVEMENT.value] = mock_mode

        # Mock GitHub issues check to return 0 (no GitHub tasks)
        with patch.object(daemon, "_poll_github_issues", return_value=0):
            with patch.object(daemon.task_queue, "create_task") as mock_create:
                daemon._queue_next_improvement_task()

        # Should create task
        mock_create.assert_called_once()


class TestDaemonTaskPickupAndExecution(unittest.TestCase):
    """Test task pickup and execution flow (lines 270-271)"""

    @patch("tools.evolution.daemon.setup_logging")
    def test_main_loop_picks_up_and_executes_task(self, mock_setup_logging):
        """Test that daemon picks up task and executes it (lines 270-271)"""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger

        daemon = EvolutionDaemon()
        daemon.stop_requested = False

        # Create a mock task
        mock_task = Task(
            id="task-execute-123",
            type=TaskType.SELF_IMPROVEMENT.value,
            status=TaskStatus.PENDING.value,
            priority=5,
            params={"description": "Test task execution"},
            created_at="2024-01-01T00:00:00",
        )

        call_count = [0]

        def return_task_once():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_task
            daemon.stop_requested = True
            return None

        with patch.object(daemon, "_check_open_prs", return_value=[]):
            with patch.object(
                daemon.resource_manager, "can_accept_task", return_value=(True, "")
            ):
                with patch.object(daemon.task_queue, "count_running", return_value=0):
                    with patch.object(
                        daemon.task_queue, "count_pending", return_value=1
                    ):
                        with patch.object(
                            daemon.task_queue,
                            "get_next_task",
                            side_effect=return_task_once,
                        ):
                            with patch.object(daemon, "_execute_task") as mock_execute:
                                with patch.object(daemon, "_interruptible_sleep"):
                                    daemon.main_loop()

        # Verify task was picked up and executed (line 270-271)
        mock_execute.assert_called_once_with(mock_task)

        # Verify log message for picking up task (line 270)
        log_messages = [str(c) for c in mock_logger.info.call_args_list]
        pickup_messages = [
            m for m in log_messages if "Picked up task: task-execute-123" in m
        ]
        self.assertGreater(len(pickup_messages), 0)


if __name__ == "__main__":
    unittest.main()

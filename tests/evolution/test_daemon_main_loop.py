"""
Comprehensive tests for Evolution Daemon main loop and PR detection.

CRITICAL PATHS TESTED:
- PR detection and pause logic
- GitHub API integration with rate limiting
- PR completion detection
- Next task queueing
- Perpetual loop state machine

Priority: 10/10 - This is the core autonomous loop. Failures here break the entire system.
"""

import pytest
from unittest.mock import Mock, patch
import time

from tools.evolution.daemon import EvolutionDaemon
from tools.evolution.task_queue import TaskStatus, TaskType


class TestDaemonMainLoop:
    """Test Evolution Daemon main loop integration"""

    @pytest.fixture
    def daemon(self, tmp_path):
        """Create daemon with temporary PID file location"""
        with patch.object(EvolutionDaemon, "_load_config") as mock_config:
            mock_config.return_value = {
                "daemon": {
                    "enabled": True,
                    "poll_interval_seconds": 1,  # Fast polling for tests
                    "max_concurrent_tasks": 1,
                    "log_level": "INFO",
                },
                "modes": {
                    "self_improvement": {"enabled": True, "priority": 8},
                },
                "resources": {
                    "max_cpu_percent": 80,
                    "max_memory_gb": 16,
                    "active_hours": [0, 24],  # Always active
                },
            }

            daemon = EvolutionDaemon()
            # Override PID file to use temp directory
            daemon.pid_file = tmp_path / "test_daemon.pid"
            return daemon

    def test_pr_detection_pauses_daemon(self, daemon):
        """Test that detecting open PRs pauses the daemon from picking up new tasks"""
        with patch.object(daemon, "_check_open_prs") as mock_check_prs:
            with patch.object(daemon, "_interruptible_sleep") as mock_sleep:
                with patch.object(daemon, "task_queue") as mock_queue:
                    # Simulate open PR
                    mock_check_prs.return_value = [
                        {
                            "number": 123,
                            "title": "Test PR",
                            "head": {"ref": "self-improvement/test"},
                        }
                    ]

                    # Run one iteration of the loop
                    daemon.stop_requested = False

                    # Start loop in background and stop after one iteration
                    import threading

                    def run_loop():
                        daemon.main_loop()

                    thread = threading.Thread(target=run_loop)
                    thread.start()

                    # Let it run one iteration
                    time.sleep(0.5)
                    daemon.stop_requested = True
                    thread.join(timeout=2)

                    # Verify that task queue was NOT accessed (paused)
                    mock_queue.get_next_task.assert_not_called()

                    # Verify pause logging happened
                    assert daemon.was_paused_for_pr

    def test_pr_merge_queues_next_task(self, daemon):
        """Test that PRs being merged triggers next task queueing"""
        with patch.object(daemon, "_check_open_prs") as mock_check_prs:
            with patch.object(
                daemon, "_queue_next_improvement_task"
            ) as mock_queue_task:
                with patch.object(daemon, "_interruptible_sleep") as mock_sleep:
                    with patch.object(
                        daemon.task_queue, "get_next_task"
                    ) as mock_get_task:
                        with patch.object(
                            daemon.task_queue, "count_pending"
                        ) as mock_count_pending:
                            with patch.object(
                                daemon.task_queue, "count_running"
                            ) as mock_count_running:
                                # Simulate: was paused, now no PRs
                                daemon.was_paused_for_pr = True
                                mock_check_prs.return_value = []  # No open PRs
                                mock_count_pending.return_value = 0
                                mock_count_running.return_value = 0
                                mock_get_task.return_value = None

                                # Mock resource check to allow task acceptance
                                with patch.object(
                                    daemon.resource_manager, "can_accept_task"
                                ) as mock_resource:
                                    mock_resource.return_value = (True, "OK")

                                    # Run one iteration
                                    daemon.stop_requested = False
                                    import threading

                                    def run_loop():
                                        daemon.main_loop()

                                    thread = threading.Thread(target=run_loop)
                                    thread.start()
                                    time.sleep(0.5)
                                    daemon.stop_requested = True
                                    thread.join(timeout=2)

                                    # Verify next task was queued
                                    assert mock_queue_task.called


class TestGitHubAPIIntegration:
    """Test GitHub API integration for PR detection"""

    @pytest.fixture
    def daemon(self, tmp_path):
        """Create daemon for GitHub API tests"""
        with patch.object(EvolutionDaemon, "_load_config") as mock_config:
            mock_config.return_value = {
                "daemon": {"poll_interval_seconds": 60},
                "resources": {},
            }
            daemon = EvolutionDaemon()
            daemon.pid_file = tmp_path / "test_daemon.pid"
            return daemon

    def test_check_open_prs_github_api_success(self, daemon):
        """Test successful GitHub API call to check open PRs"""
        with patch("subprocess.run") as mock_run:
            with patch("requests.get") as mock_requests_get:
                # Mock git remote command
                mock_run.return_value = Mock(
                    returncode=0, stdout="https://github.com/testowner/testrepo.git\n"
                )

                # Mock GitHub API response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = [
                    {
                        "number": 123,
                        "title": "Self-improvement task",
                        "head": {"ref": "self-improvement/task-abc123"},
                        "html_url": "https://github.com/testowner/testrepo/pull/123",
                    },
                    {
                        "number": 124,
                        "title": "Manual PR",
                        "head": {"ref": "feature/manual"},
                        "html_url": "https://github.com/testowner/testrepo/pull/124",
                    },
                ]
                mock_requests_get.return_value = mock_response

                # Call the method
                prs = daemon._check_open_prs()

                # Verify only Evolution PRs are returned
                assert len(prs) == 1
                assert prs[0]["number"] == 123
                assert "self-improvement" in prs[0]["head"]["ref"]

    def test_check_open_prs_rate_limiting(self, daemon):
        """Test GitHub API rate limiting handling"""
        with patch("subprocess.run") as mock_run:
            with patch("requests.get") as mock_requests_get:
                # Mock git remote command
                mock_run.return_value = Mock(
                    returncode=0, stdout="https://github.com/testowner/testrepo.git\n"
                )

                # Mock rate limit response
                mock_response = Mock()
                mock_response.status_code = 403
                mock_response.text = "API rate limit exceeded"
                mock_requests_get.return_value = mock_response

                # Call should handle gracefully
                prs = daemon._check_open_prs()

                # Should return empty list, not raise
                assert prs == []

    def test_check_open_prs_network_error(self, daemon):
        """Test GitHub API network error handling"""
        with patch("subprocess.run") as mock_run:
            with patch("requests.get") as mock_requests_get:
                # Mock git remote command
                mock_run.return_value = Mock(
                    returncode=0, stdout="https://github.com/testowner/testrepo.git\n"
                )

                # Mock network error
                mock_requests_get.side_effect = Exception("Connection timeout")

                # Should handle gracefully
                prs = daemon._check_open_prs()
                assert prs == []

    def test_check_open_prs_with_github_token(self, daemon):
        """Test that GitHub token is used when available"""
        with patch("subprocess.run") as mock_run:
            with patch("requests.get") as mock_requests_get:
                with patch.dict("os.environ", {"GITHUB_TOKEN": "test_token_123"}):
                    # Mock git remote
                    mock_run.return_value = Mock(
                        returncode=0,
                        stdout="https://github.com/testowner/testrepo.git\n",
                    )

                    # Mock API response
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = []
                    mock_requests_get.return_value = mock_response

                    daemon._check_open_prs()

                    # Verify Authorization header was set
                    call_kwargs = mock_requests_get.call_args[1]
                    assert "headers" in call_kwargs
                    assert (
                        call_kwargs["headers"]["Authorization"]
                        == "token test_token_123"
                    )


class TestPRDetectionAndTaskCompletion:
    """Test PR detection and task completion race condition fix"""

    @pytest.fixture
    def daemon(self, tmp_path):
        """Create daemon for PR detection tests"""
        with patch.object(EvolutionDaemon, "_load_config") as mock_config:
            mock_config.return_value = {
                "daemon": {"poll_interval_seconds": 60},
                "resources": {},
            }
            daemon = EvolutionDaemon()
            daemon.pid_file = tmp_path / "test_daemon.pid"
            return daemon

    def test_detect_prs_and_complete_tasks_matching(self, daemon):
        """Test that PRs are matched to running tasks and marked completed"""
        with patch.object(daemon, "_check_open_prs") as mock_check_prs:
            with patch.object(daemon.task_queue, "list_tasks") as mock_list_tasks:
                with patch.object(
                    daemon.task_queue, "update_task_status"
                ) as mock_update:
                    # Mock open PR
                    mock_check_prs.return_value = [
                        {
                            "number": 123,
                            "head": {"ref": "self-improvement/task-abc12345"},
                            "html_url": "https://github.com/test/repo/pull/123",
                        }
                    ]

                    # Mock running task with matching ID
                    mock_task = Mock()
                    mock_task.id = "abc12345-1234-1234-1234-123456789012"  # First 8 chars: abc12345
                    mock_list_tasks.return_value = [mock_task]

                    # Call detection
                    daemon._detect_prs_and_complete_tasks()

                    # Verify task was marked completed
                    mock_update.assert_called_once()
                    call_args = mock_update.call_args
                    assert call_args[0][0] == mock_task.id
                    assert call_args[0][1] == TaskStatus.COMPLETED.value

    def test_detect_prs_no_matching_tasks(self, daemon):
        """Test that non-matching PRs don't affect tasks"""
        with patch.object(daemon, "_check_open_prs") as mock_check_prs:
            with patch.object(daemon.task_queue, "list_tasks") as mock_list_tasks:
                with patch.object(
                    daemon.task_queue, "update_task_status"
                ) as mock_update:
                    # Mock PR with different task ID
                    mock_check_prs.return_value = [
                        {
                            "number": 123,
                            "head": {"ref": "self-improvement/task-xyz99999"},
                            "html_url": "https://github.com/test/repo/pull/123",
                        }
                    ]

                    # Mock running task with non-matching ID
                    mock_task = Mock()
                    mock_task.id = "abc12345-1234-1234-1234-123456789012"
                    mock_list_tasks.return_value = [mock_task]

                    # Call detection
                    daemon._detect_prs_and_complete_tasks()

                    # Verify task was NOT updated
                    mock_update.assert_not_called()


class TestNextTaskQueueing:
    """Test next task queueing for perpetual loop"""

    @pytest.fixture
    def daemon(self, tmp_path):
        """Create daemon for task queueing tests"""
        with patch.object(EvolutionDaemon, "_load_config") as mock_config:
            mock_config.return_value = {
                "daemon": {"poll_interval_seconds": 60},
                "resources": {},
            }
            daemon = EvolutionDaemon()
            daemon.pid_file = tmp_path / "test_daemon.pid"
            return daemon

    def test_queue_next_improvement_task_with_todos(self, daemon):
        """Test queuing next task when TODOs are available"""
        with patch.object(
            daemon.modes[TaskType.SELF_IMPROVEMENT.value], "_find_todos"
        ) as mock_find_todos:
            with patch.object(daemon.task_queue, "create_task") as mock_create_task:
                # Mock available TODOs
                mock_find_todos.return_value = [
                    {
                        "file": "/test/file.py",
                        "line": "42",
                        "text": "TODO: Implement feature X",
                        "priority": 9,
                        "category": "feature",
                    }
                ]

                mock_create_task.return_value = "task-id-123"

                # Call queue next task
                daemon._queue_next_improvement_task()

                # Verify task was created
                mock_create_task.assert_called_once()
                call_args = mock_create_task.call_args
                assert call_args[1]["task_type"] == TaskType.SELF_IMPROVEMENT.value
                assert call_args[1]["priority"] == 9

    def test_queue_next_improvement_task_no_todos(self, daemon):
        """Test behavior when no TODOs are available"""
        with patch.object(
            daemon.modes[TaskType.SELF_IMPROVEMENT.value], "_find_todos"
        ) as mock_find_todos:
            with patch.object(daemon.task_queue, "create_task") as mock_create_task:
                # Mock no TODOs
                mock_find_todos.return_value = []

                # Should not raise, just log warning
                daemon._queue_next_improvement_task()

                # No task should be created
                mock_create_task.assert_not_called()


class TestRunningTasksPause:
    """Test that daemon waits for running tasks before picking up new ones"""

    @pytest.fixture
    def daemon(self, tmp_path):
        """Create daemon for running tasks tests"""
        with patch.object(EvolutionDaemon, "_load_config") as mock_config:
            mock_config.return_value = {
                "daemon": {"poll_interval_seconds": 1, "max_concurrent_tasks": 3},
                "resources": {},
            }
            daemon = EvolutionDaemon()
            daemon.pid_file = tmp_path / "test_daemon.pid"
            return daemon

    def test_daemon_waits_for_running_tasks(self, daemon):
        """Test that daemon doesn't pick up new tasks while tasks are running"""
        with patch.object(daemon, "_check_open_prs") as mock_check_prs:
            with patch.object(daemon.task_queue, "count_pending") as mock_count_pending:
                with patch.object(
                    daemon.task_queue, "count_running"
                ) as mock_count_running:
                    with patch.object(
                        daemon.task_queue, "get_next_task"
                    ) as mock_get_task:
                        with patch.object(daemon, "_interruptible_sleep") as mock_sleep:
                            with patch.object(
                                daemon.resource_manager, "can_accept_task"
                            ) as mock_resource:
                                # Setup: no open PRs, resources available, but task is running
                                mock_check_prs.return_value = []
                                mock_resource.return_value = (True, "OK")
                                mock_count_pending.return_value = 5
                                mock_count_running.return_value = 1  # 1 task running

                                # Run one iteration
                                daemon.stop_requested = False
                                import threading

                                def run_loop():
                                    daemon.main_loop()

                                thread = threading.Thread(target=run_loop)
                                thread.start()
                                time.sleep(0.5)
                                daemon.stop_requested = True
                                thread.join(timeout=2)

                                # Verify daemon did NOT pick up new task
                                mock_get_task.assert_not_called()


class TestInterruptibleSleep:
    """Test interruptible sleep for responsive shutdown"""

    @pytest.fixture
    def daemon(self, tmp_path):
        """Create daemon for sleep tests"""
        with patch.object(EvolutionDaemon, "_load_config") as mock_config:
            mock_config.return_value = {"daemon": {}, "resources": {}}
            daemon = EvolutionDaemon()
            daemon.pid_file = tmp_path / "test_daemon.pid"
            return daemon

    def test_interruptible_sleep_respects_stop_request(self, daemon):
        """Test that sleep can be interrupted by stop request"""
        import time

        start_time = time.time()

        # Set stop_requested after 0.5 seconds
        def set_stop():
            time.sleep(0.5)
            daemon.stop_requested = True

        import threading

        stopper = threading.Thread(target=set_stop)
        stopper.start()

        # Try to sleep for 10 seconds (should interrupt after 0.5)
        daemon._interruptible_sleep(10)

        elapsed = time.time() - start_time
        stopper.join()

        # Should have stopped much earlier than 10 seconds
        assert elapsed < 2.0  # Give some margin
        assert daemon.stop_requested


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Integration tests for job submission flow
"""

import pytest
from unittest.mock import Mock

from tools.tui_daemon.manager import TUIManager


class TestJobSubmission:
    """Integration tests for job submission"""

    @pytest.fixture
    def manager(self, mock_daemon_client):
        """Create TUIManager with mocked client"""
        manager = TUIManager()
        manager.daemon_client = mock_daemon_client
        return manager

    def test_submit_build_success(self, manager):
        """Test successful build submission"""
        # Mock job manager
        mock_job = Mock()
        mock_job.job_id = "new-job-123"
        manager.daemon_client.job_manager = Mock()
        manager.daemon_client.job_manager.submit_job.return_value = mock_job

        params = {
            "task": "build a todo app",
            "working_directory": "~/projects/todo",
            "mode": "smart",
            "max_iterations": 5,
            "timeout": 3600,
        }

        job = manager.submit_build(params)

        assert job is not None
        assert job.job_id == "new-job-123"

    def test_submit_build_with_github_repo(self, manager):
        """Test build submission with GitHub repo"""
        mock_job = Mock()
        mock_job.job_id = "new-job-456"
        manager.daemon_client.job_manager = Mock()
        manager.daemon_client.job_manager.submit_job.return_value = mock_job

        params = {
            "task": "create app",
            "working_directory": "~/app",
            "github_repo": "user/project",
            "mode": "smart",
        }

        job = manager.submit_build(params)

        assert job is not None
        # Verify github_repo was passed
        call_args = manager.daemon_client.job_manager.submit_job.call_args
        assert call_args[0][1]["github_repo"] == "user/project"

    def test_submit_build_failure(self, manager):
        """Test build submission failure"""
        manager.daemon_client.job_manager = Mock()
        manager.daemon_client.job_manager.submit_job.side_effect = Exception("DB error")

        params = {"task": "build app"}
        job = manager.submit_build(params)

        assert job is None

    def test_cancel_job_success(self, manager):
        """Test successful job cancellation"""
        manager.daemon_client.job_manager = Mock()
        manager.daemon_client.job_manager.cancel_job.return_value = None

        result = manager.cancel_job("job-123")

        assert result is True
        manager.daemon_client.job_manager.cancel_job.assert_called_once_with("job-123")

    def test_cancel_job_failure(self, manager):
        """Test job cancellation failure"""
        manager.daemon_client.job_manager = Mock()
        manager.daemon_client.job_manager.cancel_job.side_effect = Exception("Error")

        result = manager.cancel_job("job-123")

        assert result is False

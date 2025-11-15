"""
End-to-end tests for conversation flow
"""

import pytest
from unittest.mock import Mock

from tools.tui_daemon.conversation_parser import ConversationParser
from tools.tui_daemon.manager import TUIManager


class TestConversationFlow:
    """End-to-end tests for conversation → parse → submit flow"""

    @pytest.fixture
    def manager(self, mock_daemon_client):
        """Create TUIManager with mocked client"""
        manager = TUIManager()
        manager.daemon_client = mock_daemon_client
        return manager

    def test_full_conversation_flow(self, manager):
        """Test complete flow from NL input to job submission"""
        # Step 1: User input
        user_input = "build a todo app with react in ~/projects/todo"

        # Step 2: Parse
        parser = ConversationParser()
        params = parser.parse(user_input)

        assert params.task is not None
        assert params.working_directory == "~/projects/todo"

        # Step 3: Submit
        mock_job = Mock()
        mock_job.job_id = "submitted-job-123"
        manager.daemon_client.job_manager = Mock()
        manager.daemon_client.job_manager.submit_job.return_value = mock_job

        job_params = {
            "task": params.task,
            "working_directory": params.working_directory,
            "mode": params.mode,
            "max_iterations": params.max_iterations,
            "timeout": params.timeout,
        }

        job = manager.submit_build(job_params)

        # Verify job was created
        assert job is not None
        assert job.job_id == "submitted-job-123"

    def test_conversation_with_edits(self, manager):
        """Test flow with parameter editing"""
        # Parse initial input
        parser = ConversationParser()
        params = parser.parse("build a game")

        # Simulate user editing working directory
        params.working_directory = "~/custom/path"

        # Submit edited params
        mock_job = Mock()
        mock_job.job_id = "edited-job-456"
        manager.daemon_client.job_manager = Mock()
        manager.daemon_client.job_manager.submit_job.return_value = mock_job

        job_params = {
            "task": params.task,
            "working_directory": params.working_directory,
            "mode": params.mode,
        }

        manager.submit_build(job_params)

        # Verify edited directory was used
        call_args = manager.daemon_client.job_manager.submit_job.call_args
        assert call_args[0][1]["working_directory"] == "~/custom/path"

    def test_conversation_with_low_confidence(self, manager):
        """Test handling of low-confidence parse"""
        parser = ConversationParser()
        params = parser.parse("make something")

        # Low confidence should still allow submission
        # (user confirmation handles ambiguity)
        assert params.confidence < 0.5
        assert params.working_directory is not None  # Should have default

    def test_multiple_builds(self, manager):
        """Test submitting multiple builds in sequence"""
        parser = ConversationParser()
        manager.daemon_client.job_manager = Mock()

        # First build
        params1 = parser.parse("build todo app")
        mock_job1 = Mock(job_id="job-1")
        manager.daemon_client.job_manager.submit_job.return_value = mock_job1

        job1 = manager.submit_build(
            {
                "task": params1.task,
                "working_directory": params1.working_directory,
            }
        )

        # Second build
        params2 = parser.parse("create api")
        mock_job2 = Mock(job_id="job-2")
        manager.daemon_client.job_manager.submit_job.return_value = mock_job2

        job2 = manager.submit_build(
            {
                "task": params2.task,
                "working_directory": params2.working_directory,
            }
        )

        # Both should succeed
        assert job1.job_id == "job-1"
        assert job2.job_id == "job-2"
        assert manager.daemon_client.job_manager.submit_job.call_count == 2

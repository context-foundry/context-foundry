#!/usr/bin/env python3
"""
Comprehensive tests for Evolution MCP Tools
Tests all MCP tool functions for the Evolution System.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from tools import evolution_mcp_tools


@pytest.fixture
def mock_task_queue():
    """Mock TaskQueueManager."""
    mock = MagicMock()
    with patch('tools.evolution_mcp_tools.get_task_queue', return_value=mock):
        yield mock


@pytest.fixture
def mock_daemon():
    """Mock EvolutionDaemon."""
    mock = MagicMock()
    with patch('tools.evolution_mcp_tools.get_daemon', return_value=mock):
        yield mock


class TestCreateEvolutionTask:
    """Test create_evolution_task_impl."""

    def test_create_task_success(self, mock_task_queue):
        """Test successful task creation."""
        mock_task_queue.create_task.return_value = "task-123"

        result = evolution_mcp_tools.create_evolution_task_impl(
            task_type="self_improvement",
            priority=7
        )

        # Parse JSON response
        data = json.loads(result)
        assert data["success"] is True
        assert data["task_id"] == "task-123"
        assert data["status"] == "pending"

        # Verify create_task was called correctly
        mock_task_queue.create_task.assert_called_once()
        args = mock_task_queue.create_task.call_args
        assert args[1]["task_type"] == "self_improvement"
        assert args[1]["priority"] == 7

    def test_create_task_with_target_project(self, mock_task_queue):
        """Test task creation with target project."""
        mock_task_queue.create_task.return_value = "task-456"

        result = evolution_mcp_tools.create_evolution_task_impl(
            task_type="chaos_creative",
            target_project="/path/to/project",
            priority=5
        )

        data = json.loads(result)
        assert data["success"] is True

        # Verify target_project was passed
        args = mock_task_queue.create_task.call_args
        assert args[1]["params"]["target_project"] == "/path/to/project"

    def test_create_task_with_pattern_id(self, mock_task_queue):
        """Test task creation with pattern ID."""
        mock_task_queue.create_task.return_value = "task-789"

        result = evolution_mcp_tools.create_evolution_task_impl(
            task_type="apply_pattern",
            pattern_id="pattern-123",
            priority=8
        )

        data = json.loads(result)
        assert data["success"] is True

        # Verify pattern_id was passed
        args = mock_task_queue.create_task.call_args
        assert args[1]["params"]["pattern_id"] == "pattern-123"

    def test_create_task_with_params(self, mock_task_queue):
        """Test task creation with additional params."""
        mock_task_queue.create_task.return_value = "task-params"

        custom_params = {"key": "value", "number": 42}
        result = evolution_mcp_tools.create_evolution_task_impl(
            task_type="research",
            priority=6,
            params=custom_params
        )

        data = json.loads(result)
        assert data["success"] is True

        # Verify params were merged
        args = mock_task_queue.create_task.call_args
        assert "key" in args[1]["params"]
        assert args[1]["params"]["key"] == "value"

    def test_create_task_error_handling(self, mock_task_queue):
        """Test error handling in task creation."""
        mock_task_queue.create_task.side_effect = Exception("Database error")

        result = evolution_mcp_tools.create_evolution_task_impl(
            task_type="self_improvement",
            priority=5
        )

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data
        assert "Database error" in data["error"]


class TestGetEvolutionTasks:
    """Test get_evolution_tasks_impl."""

    def test_get_tasks_default(self, mock_task_queue):
        """Test getting tasks with default parameters."""
        mock_task = Mock()
        mock_task.to_dict.return_value = {"id": "task-1", "status": "pending"}
        mock_task_queue.list_tasks.return_value = [mock_task]

        result = evolution_mcp_tools.get_evolution_tasks_impl()

        data = json.loads(result)
        assert data["success"] is True
        assert data["count"] == 1
        assert len(data["tasks"]) == 1

        # Verify list_tasks was called with default params
        mock_task_queue.list_tasks.assert_called_once_with(status="pending", limit=50)

    def test_get_tasks_all(self, mock_task_queue):
        """Test getting all tasks."""
        mock_tasks = [Mock(), Mock(), Mock()]
        for i, task in enumerate(mock_tasks):
            task.to_dict.return_value = {"id": f"task-{i}"}
        mock_task_queue.list_tasks.return_value = mock_tasks

        result = evolution_mcp_tools.get_evolution_tasks_impl(status="all", limit=100)

        data = json.loads(result)
        assert data["success"] is True
        assert data["count"] == 3
        assert len(data["tasks"]) == 3

        # Verify list_tasks was called with None for status
        mock_task_queue.list_tasks.assert_called_once_with(status=None, limit=100)

    def test_get_tasks_filtered_status(self, mock_task_queue):
        """Test getting tasks filtered by status."""
        mock_task = Mock()
        mock_task.to_dict.return_value = {"id": "completed-1", "status": "completed"}
        mock_task_queue.list_tasks.return_value = [mock_task]

        result = evolution_mcp_tools.get_evolution_tasks_impl(status="completed", limit=25)

        data = json.loads(result)
        assert data["success"] is True
        assert data["count"] == 1

        mock_task_queue.list_tasks.assert_called_once_with(status="completed", limit=25)

    def test_get_tasks_empty(self, mock_task_queue):
        """Test getting tasks when queue is empty."""
        mock_task_queue.list_tasks.return_value = []

        result = evolution_mcp_tools.get_evolution_tasks_impl()

        data = json.loads(result)
        assert data["success"] is True
        assert data["count"] == 0
        assert len(data["tasks"]) == 0

    def test_get_tasks_error_handling(self, mock_task_queue):
        """Test error handling when listing tasks."""
        mock_task_queue.list_tasks.side_effect = Exception("Connection error")

        result = evolution_mcp_tools.get_evolution_tasks_impl()

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data


class TestStartEvolutionDaemon:
    """Test start_evolution_daemon_impl."""

    def test_start_daemon_success(self, mock_daemon):
        """Test starting daemon when not already running."""
        mock_daemon.is_running.return_value = False

        result = evolution_mcp_tools.start_evolution_daemon_impl()

        data = json.loads(result)
        assert data["success"] is True
        assert "message" in data

    def test_start_daemon_already_running(self, mock_daemon):
        """Test starting daemon when already running."""
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = 12345

        result = evolution_mcp_tools.start_evolution_daemon_impl()

        data = json.loads(result)
        assert data["success"] is False
        assert "already running" in data["message"].lower()
        assert data["pid"] == 12345

    def test_start_daemon_with_config(self, mock_daemon):
        """Test starting daemon with custom config path."""
        mock_daemon.is_running.return_value = False

        result = evolution_mcp_tools.start_evolution_daemon_impl(
            config_path="/custom/config.json"
        )

        data = json.loads(result)
        assert data["success"] is True

    def test_start_daemon_error_handling(self, mock_daemon):
        """Test error handling when starting daemon."""
        mock_daemon.is_running.side_effect = Exception("Permission denied")

        result = evolution_mcp_tools.start_evolution_daemon_impl()

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data


class TestStopEvolutionDaemon:
    """Test stop_evolution_daemon_impl."""

    def test_stop_daemon_success(self, mock_daemon):
        """Test successfully stopping daemon."""
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = 12345

        with patch('os.kill') as mock_kill:
            result = evolution_mcp_tools.stop_evolution_daemon_impl()

            data = json.loads(result)
            assert data["success"] is True
            assert "12345" in data["message"]

            # Verify SIGTERM was sent
            mock_kill.assert_called_once_with(12345, 15)

    def test_stop_daemon_not_running(self, mock_daemon):
        """Test stopping daemon when not running."""
        mock_daemon.is_running.return_value = False

        result = evolution_mcp_tools.stop_evolution_daemon_impl()

        data = json.loads(result)
        assert data["success"] is False
        assert "not running" in data["message"].lower()

    def test_stop_daemon_no_pid(self, mock_daemon):
        """Test stopping daemon when PID cannot be determined."""
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = None

        result = evolution_mcp_tools.stop_evolution_daemon_impl()

        data = json.loads(result)
        assert data["success"] is False
        assert "could not determine" in data["message"].lower()

    def test_stop_daemon_graceful_flag(self, mock_daemon):
        """Test graceful parameter is accepted."""
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = 12345

        with patch('os.kill'):
            result = evolution_mcp_tools.stop_evolution_daemon_impl(graceful=False)
            data = json.loads(result)
            assert data["success"] is True


class TestGetDaemonStatus:
    """Test get_daemon_status_impl."""

    def test_get_status_running(self, mock_daemon, mock_task_queue):
        """Test getting status when daemon is running."""
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = 12345
        mock_daemon.get_uptime.return_value = 3600.0
        mock_task_queue.count_pending.return_value = 5
        mock_task_queue.count_completed.return_value = 10
        mock_task_queue.count_failed.return_value = 2

        with patch('psutil.cpu_percent', return_value=45.2):
            with patch('psutil.virtual_memory') as mock_mem:
                mock_mem.return_value.used = 8 * 1024**3  # 8 GB

                result = evolution_mcp_tools.get_daemon_status_impl()

                data = json.loads(result)
                assert data["success"] is True
                assert data["status"]["running"] is True
                assert data["status"]["pid"] == 12345
                assert data["status"]["uptime_seconds"] == 3600.0
                assert data["status"]["queue_size"] == 5
                assert data["status"]["completed_tasks"] == 10
                assert data["status"]["failed_tasks"] == 2
                assert "cpu_percent" in data["status"]["resource_usage"]
                assert "memory_mb" in data["status"]["resource_usage"]

    def test_get_status_not_running(self, mock_daemon, mock_task_queue):
        """Test getting status when daemon is not running."""
        mock_daemon.is_running.return_value = False
        mock_task_queue.count_pending.return_value = 0
        mock_task_queue.count_completed.return_value = 0
        mock_task_queue.count_failed.return_value = 0

        with patch('psutil.cpu_percent', return_value=10.0):
            with patch('psutil.virtual_memory') as mock_mem:
                mock_mem.return_value.used = 4 * 1024**3  # 4 GB

                result = evolution_mcp_tools.get_daemon_status_impl()

                data = json.loads(result)
                assert data["success"] is True
                assert data["status"]["running"] is False
                assert data["status"]["pid"] is None
                assert data["status"]["uptime_seconds"] == 0

    def test_get_status_error_handling(self, mock_daemon):
        """Test error handling when getting status."""
        mock_daemon.is_running.side_effect = Exception("System error")

        result = evolution_mcp_tools.get_daemon_status_impl()

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data


class TestRegisterProject:
    """Test register_project_impl."""

    def test_register_project_success(self, mock_task_queue):
        """Test successful project registration."""
        result = evolution_mcp_tools.register_project_impl(
            project_path="/path/to/project",
            project_type="python"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert "/path/to/project" in data["message"]

        # Verify register_project was called
        mock_task_queue.register_project.assert_called_once_with(
            path="/path/to/project",
            project_type="python",
            metadata={}
        )

    def test_register_project_with_metadata(self, mock_task_queue):
        """Test project registration with metadata."""
        metadata = {"version": "1.0.0", "framework": "django"}

        result = evolution_mcp_tools.register_project_impl(
            project_path="/path/to/project",
            project_type="python",
            metadata=metadata
        )

        data = json.loads(result)
        assert data["success"] is True

        # Verify metadata was passed
        args = mock_task_queue.register_project.call_args
        assert args[1]["metadata"] == metadata

    def test_register_project_error_handling(self, mock_task_queue):
        """Test error handling in project registration."""
        mock_task_queue.register_project.side_effect = Exception("Invalid path")

        result = evolution_mcp_tools.register_project_impl(
            project_path="/invalid/path",
            project_type="python"
        )

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data


class TestApplyPatternToProject:
    """Test apply_pattern_to_project_impl."""

    def test_apply_pattern_success(self, mock_task_queue):
        """Test successful pattern application."""
        mock_task_queue.create_task.return_value = "task-pattern-123"

        result = evolution_mcp_tools.apply_pattern_to_project_impl(
            project_path="/path/to/project",
            pattern_id="pattern-456"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["task_id"] == "task-pattern-123"

        # Verify task was created correctly
        mock_task_queue.create_task.assert_called_once()
        args = mock_task_queue.create_task.call_args
        assert args[1]["task_type"] == "apply_pattern"
        assert args[1]["params"]["project_path"] == "/path/to/project"
        assert args[1]["params"]["pattern_id"] == "pattern-456"
        assert args[1]["priority"] == 7

    def test_apply_pattern_error_handling(self, mock_task_queue):
        """Test error handling in pattern application."""
        mock_task_queue.create_task.side_effect = Exception("Pattern not found")

        result = evolution_mcp_tools.apply_pattern_to_project_impl(
            project_path="/path/to/project",
            pattern_id="invalid-pattern"
        )

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data


class TestValidateProjectHealth:
    """Test validate_project_health_impl."""

    def test_validate_health_success(self, mock_task_queue):
        """Test successful health validation."""
        mock_task_queue.create_task.return_value = "task-validate-789"

        result = evolution_mcp_tools.validate_project_health_impl(
            project_path="/path/to/project"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["task_id"] == "task-validate-789"

        # Verify validation task was created
        mock_task_queue.create_task.assert_called_once()
        args = mock_task_queue.create_task.call_args
        assert args[1]["task_type"] == "validate"
        assert args[1]["params"]["project_path"] == "/path/to/project"
        assert args[1]["priority"] == 8

    def test_validate_health_error_handling(self, mock_task_queue):
        """Test error handling in health validation."""
        mock_task_queue.create_task.side_effect = Exception("Project not found")

        result = evolution_mcp_tools.validate_project_health_impl(
            project_path="/nonexistent/path"
        )

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data


class TestRegisterAgent:
    """Test register_agent_impl."""

    def test_register_agent_basic(self, mock_task_queue):
        """Test basic agent registration."""
        mock_task_queue.register_agent.return_value = "agent-123"

        result = evolution_mcp_tools.register_agent_impl(agent_name="TestAgent")

        data = json.loads(result)
        assert data["success"] is True
        assert data["agent_id"] == "agent-123"
        assert "TestAgent" in data["message"]

        # Verify register_agent was called
        mock_task_queue.register_agent.assert_called_once_with(
            name="TestAgent",
            url=None,
            capabilities=[]
        )

    def test_register_agent_with_details(self, mock_task_queue):
        """Test agent registration with URL and capabilities."""
        mock_task_queue.register_agent.return_value = "agent-456"
        capabilities = ["code_generation", "testing"]

        result = evolution_mcp_tools.register_agent_impl(
            agent_name="AdvancedAgent",
            agent_url="http://localhost:8080",
            capabilities=capabilities
        )

        data = json.loads(result)
        assert data["success"] is True

        # Verify details were passed
        args = mock_task_queue.register_agent.call_args
        assert args[1]["name"] == "AdvancedAgent"
        assert args[1]["url"] == "http://localhost:8080"
        assert args[1]["capabilities"] == capabilities

    def test_register_agent_error_handling(self, mock_task_queue):
        """Test error handling in agent registration."""
        mock_task_queue.register_agent.side_effect = Exception("Registration failed")

        result = evolution_mcp_tools.register_agent_impl(agent_name="FailAgent")

        data = json.loads(result)
        assert data["success"] is False
        assert "error" in data


class TestIntegration:
    """Integration tests for MCP tools."""

    def test_full_workflow(self, mock_task_queue, mock_daemon):
        """Test a complete workflow using multiple tools."""
        # Start daemon
        mock_daemon.is_running.return_value = False
        start_result = evolution_mcp_tools.start_evolution_daemon_impl()
        assert json.loads(start_result)["success"] is True

        # Create task
        mock_task_queue.create_task.return_value = "workflow-task-1"
        create_result = evolution_mcp_tools.create_evolution_task_impl(
            task_type="self_improvement",
            priority=8
        )
        assert json.loads(create_result)["success"] is True

        # Get status
        mock_daemon.is_running.return_value = True
        mock_daemon.get_pid.return_value = 99999
        mock_daemon.get_uptime.return_value = 100.0
        mock_task_queue.count_pending.return_value = 1
        mock_task_queue.count_completed.return_value = 0
        mock_task_queue.count_failed.return_value = 0

        with patch('psutil.cpu_percent', return_value=30.0):
            with patch('psutil.virtual_memory') as mock_mem:
                mock_mem.return_value.used = 6 * 1024**3
                status_result = evolution_mcp_tools.get_daemon_status_impl()
                status_data = json.loads(status_result)
                assert status_data["success"] is True
                assert status_data["status"]["queue_size"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

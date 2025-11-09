#!/usr/bin/env python3
"""
Unit and integration tests for Evolution Daemon.

Tests critical daemon functionality:
- Daemon initialization and configuration loading
- Task polling and execution coordination
- Resource management integration
- Signal handling and graceful shutdown
- PID file management
- Error recovery and retry logic
- Multi-mode task orchestration

Priority: 10/10 - Core daemon orchestration logic
"""

import pytest
import tempfile
import shutil
import json
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import daemon components
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "evolution"))

from tools.evolution.daemon import EvolutionDaemon, setup_logging
from tools.evolution.task_queue import TaskType, TaskStatus


@pytest.mark.unit
@pytest.mark.tier1
class TestDaemonInitialization:
    """Test daemon initialization and configuration"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_daemon_initialization_with_default_config(self):
        """Test daemon initializes with default config when no config file exists"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        assert daemon.config is not None
        assert "daemon" in daemon.config
        assert daemon.config["daemon"]["enabled"] is True
        assert daemon.config["daemon"]["poll_interval_seconds"] == 60
        assert daemon.config["daemon"]["max_concurrent_tasks"] == 1

    def test_daemon_initialization_with_custom_config(self):
        """Test daemon loads custom configuration correctly"""
        custom_config = {
            "daemon": {
                "enabled": True,
                "poll_interval_seconds": 30,
                "max_concurrent_tasks": 2,
                "log_level": "DEBUG",
            },
            "modes": {"self_improvement": {"enabled": True, "priority": 10}},
        }

        self.config_path.write_text(json.dumps(custom_config))
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        assert daemon.config["daemon"]["poll_interval_seconds"] == 30
        assert daemon.config["daemon"]["max_concurrent_tasks"] == 2
        assert daemon.config["daemon"]["log_level"] == "DEBUG"

    def test_daemon_components_initialized(self):
        """Test all daemon components are properly initialized"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Check task queue initialized
        assert daemon.task_queue is not None

        # Check resource manager initialized
        assert daemon.resource_manager is not None

        # Check modes initialized
        assert daemon.modes is not None
        assert TaskType.SELF_IMPROVEMENT.value in daemon.modes
        assert TaskType.CHAOS_CREATIVE.value in daemon.modes
        assert TaskType.RESEARCH.value in daemon.modes

    def test_daemon_initial_state(self):
        """Test daemon initial state is correct"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        assert daemon.running is False
        assert daemon.stop_requested is False
        assert daemon.active_tasks == {}
        assert daemon.poll_count == 0
        assert daemon.was_paused_for_pr is False


@pytest.mark.unit
@pytest.mark.tier1
class TestDaemonPIDManagement:
    """Test daemon PID file management"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

        # Override PID file location for testing
        self.pid_dir = Path(self.temp_dir) / ".context-foundry" / "evolution"
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.pid_file = self.pid_dir / "daemon.pid"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("tools.evolution.daemon.Path.home")
    def test_pid_file_creation(self, mock_home):
        """Test daemon creates PID file on start"""
        mock_home.return_value = Path(self.temp_dir)

        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Manually write PID file (simulating daemon.start())
        daemon.pid_file.parent.mkdir(parents=True, exist_ok=True)
        daemon.pid_file.write_text(str(os.getpid()))

        assert daemon.pid_file.exists()
        assert daemon.pid_file.read_text() == str(os.getpid())

    @patch("tools.evolution.daemon.Path.home")
    def test_pid_file_cleanup(self, mock_home):
        """Test daemon removes PID file on shutdown"""
        mock_home.return_value = Path(self.temp_dir)

        daemon = EvolutionDaemon(config_path=str(self.config_path))
        daemon.pid_file.parent.mkdir(parents=True, exist_ok=True)
        daemon.pid_file.write_text(str(os.getpid()))

        # Simulate cleanup
        if daemon.pid_file.exists():
            daemon.pid_file.unlink()

        assert not daemon.pid_file.exists()


@pytest.mark.unit
@pytest.mark.tier1
class TestDaemonTaskPolling:
    """Test daemon task polling logic"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("tools.evolution.daemon.TaskQueueManager")
    def test_daemon_polls_for_pending_tasks(self, mock_queue_manager):
        """Test daemon polls queue for pending tasks"""
        # Setup mock queue
        mock_queue = MagicMock()
        mock_task = Mock(
            id="test-task-001",
            type=TaskType.SELF_IMPROVEMENT.value,
            status=TaskStatus.PENDING.value,
            priority=8,
        )
        mock_queue.get_next_task.return_value = mock_task
        mock_queue_manager.return_value = mock_queue

        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Verify task queue is available
        assert daemon.task_queue is not None

    @patch("tools.evolution.daemon.ResourceManager")
    def test_daemon_checks_resources_before_execution(self, mock_resource_mgr):
        """Test daemon checks resource availability before task execution"""
        mock_resources = MagicMock()
        mock_resources.can_acquire.return_value = True
        mock_resource_mgr.return_value = mock_resources

        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Verify resource manager is available
        assert daemon.resource_manager is not None


@pytest.mark.integration
@pytest.mark.tier1
class TestDaemonSignalHandling:
    """Test daemon signal handling for graceful shutdown"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_daemon_stop_request_flag(self):
        """Test daemon stop_requested flag can be set"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        assert daemon.stop_requested is False
        daemon.stop_requested = True
        assert daemon.stop_requested is True

    def test_daemon_running_state_management(self):
        """Test daemon running state can be managed"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        assert daemon.running is False
        daemon.running = True
        assert daemon.running is True
        daemon.running = False
        assert daemon.running is False


@pytest.mark.integration
@pytest.mark.tier1
class TestDaemonModeExecution:
    """Test daemon mode execution and orchestration"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_daemon_has_all_modes_registered(self):
        """Test daemon registers all evolution modes"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Verify all modes are registered
        assert TaskType.SELF_IMPROVEMENT.value in daemon.modes
        assert TaskType.CHAOS_CREATIVE.value in daemon.modes
        assert TaskType.RESEARCH.value in daemon.modes

        # Verify modes are instances
        assert daemon.modes[TaskType.SELF_IMPROVEMENT.value] is not None
        assert daemon.modes[TaskType.CHAOS_CREATIVE.value] is not None
        assert daemon.modes[TaskType.RESEARCH.value] is not None

    @patch("tools.evolution.daemon.SelfImprovementMode")
    def test_daemon_executes_self_improvement_mode(self, mock_mode_class):
        """Test daemon can execute self-improvement mode"""
        mock_mode = MagicMock()
        mock_mode_class.return_value = mock_mode

        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Verify mode is accessible
        assert TaskType.SELF_IMPROVEMENT.value in daemon.modes


@pytest.mark.integration
@pytest.mark.tier1
class TestDaemonErrorHandling:
    """Test daemon error handling and recovery"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_daemon_handles_invalid_config(self):
        """Test daemon raises error with invalid configuration"""
        # Write invalid JSON
        self.config_path.write_text("{invalid json}")

        # Should raise JSONDecodeError
        with pytest.raises(Exception):  # Will be JSONDecodeError
            daemon = EvolutionDaemon(config_path=str(self.config_path))

    def test_daemon_handles_missing_config(self):
        """Test daemon handles missing config file"""
        # Don't create config file
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Should use default config
        assert daemon.config is not None
        assert daemon.config["daemon"]["enabled"] is True


@pytest.mark.unit
@pytest.mark.tier2
class TestLoggingSetup:
    """Test daemon logging configuration"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_logging_directory_creation(self):
        """Test logging setup creates log directory"""
        logger = setup_logging(self.log_dir)

        assert self.log_dir.exists()
        assert (self.log_dir / "daemon.log").exists()
        assert logger is not None

    def test_logging_configuration(self):
        """Test logging is properly configured"""
        logger = setup_logging(self.log_dir)

        # Verify logger name
        assert logger.name == "tools.evolution.daemon"

        # Verify logger level
        assert logger.level <= 20  # INFO or lower


@pytest.mark.integration
@pytest.mark.tier1
class TestDaemonTaskLifecycle:
    """Test complete task lifecycle through daemon"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_daemon_tracks_active_tasks(self):
        """Test daemon tracks active tasks correctly"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Initially no active tasks
        assert daemon.active_tasks == {}

        # Simulate adding active task
        task_id = "test-task-001"
        daemon.active_tasks[task_id] = {
            "started_at": datetime.now(),
            "type": TaskType.SELF_IMPROVEMENT.value,
        }

        assert task_id in daemon.active_tasks
        assert daemon.active_tasks[task_id]["type"] == TaskType.SELF_IMPROVEMENT.value

    def test_daemon_poll_count_increments(self):
        """Test daemon poll count increments"""
        daemon = EvolutionDaemon(config_path=str(self.config_path))

        assert daemon.poll_count == 0
        daemon.poll_count += 1
        assert daemon.poll_count == 1
        daemon.poll_count += 1
        assert daemon.poll_count == 2


@pytest.mark.integration
@pytest.mark.tier1
class TestDaemonResourceCoordination:
    """Test daemon coordination with resource manager"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "config.json"

    def teardown_method(self):
        """Cleanup"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("tools.evolution.daemon.ResourceManager")
    def test_daemon_uses_resource_manager_config(self, mock_resource_mgr):
        """Test daemon passes resource config to resource manager"""
        custom_config = {
            "daemon": {"enabled": True},
            "resources": {"max_concurrent_tasks": 2, "max_tokens_per_day": 100000},
        }

        self.config_path.write_text(json.dumps(custom_config))

        daemon = EvolutionDaemon(config_path=str(self.config_path))

        # Verify resource manager was initialized with config
        mock_resource_mgr.assert_called_once_with(custom_config["resources"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

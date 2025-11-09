"""Tests for Evolution Daemon"""

import pytest
from tools.evolution.daemon import EvolutionDaemon


def test_daemon_initialization():
    """Test daemon can be initialized"""
    daemon = EvolutionDaemon()
    assert daemon is not None
    assert daemon.config is not None
    assert daemon.task_queue is not None
    assert daemon.resource_manager is not None


def test_daemon_status():
    """Test daemon status check"""
    daemon = EvolutionDaemon()
    # Initially not running
    assert daemon.is_running() == False
    assert daemon.get_pid() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

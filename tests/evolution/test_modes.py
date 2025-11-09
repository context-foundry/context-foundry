"""Tests for Evolution Modes"""

import pytest
from tools.evolution.modes.self_improvement import SelfImprovementMode
from tools.evolution.modes.chaos_creative import ChaosCreativeMode
from tools.evolution.modes.research_discovery import ResearchDiscoveryMode


def test_self_improvement_mode():
    """Test self-improvement mode"""
    mode = SelfImprovementMode()
    tasks = mode.generate_tasks()
    assert isinstance(tasks, list)


def test_chaos_creative_mode():
    """Test chaos/creative mode"""
    mode = ChaosCreativeMode()
    tasks = mode.generate_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) > 0
    assert "project_type" in tasks[0]["params"]


def test_research_discovery_mode():
    """Test research/discovery mode"""
    mode = ResearchDiscoveryMode()
    tasks = mode.generate_tasks()
    assert isinstance(tasks, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

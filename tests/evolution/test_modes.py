"""Tests for Evolution Modes"""

import pytest
import tempfile
from pathlib import Path
from tools.evolution.modes.self_improvement import SelfImprovementMode
from tools.evolution.modes.chaos_creative import ChaosCreativeMode
from tools.evolution.modes.research_discovery import ResearchDiscoveryMode


def test_self_improvement_mode():
    """Test self-improvement mode"""
    mode = SelfImprovementMode()
    tasks = mode.generate_tasks()
    assert isinstance(tasks, list)


def test_find_todos():
    """Test that _find_todos correctly identifies TODO/FIXME comments"""
    mode = SelfImprovementMode()
    todos = mode._find_todos()

    # Should return a list
    assert isinstance(todos, list)

    # Each todo should have the required keys
    for todo in todos:
        assert 'file' in todo
        assert 'line' in todo
        assert 'text' in todo
        assert isinstance(todo['file'], str)
        assert isinstance(todo['line'], str)
        assert isinstance(todo['text'], str)


def test_find_todos_filters_self_reference():
    """Test that _find_todos filters out self-referential TODOs"""
    mode = SelfImprovementMode()
    todos = mode._find_todos()

    # Should not include the "Check for TODOs/FIXMEs" comment from self_improvement.py
    for todo in todos:
        assert 'Check for TODOs/FIXMEs' not in todo['text']


def test_find_todos_unique_results():
    """Test that _find_todos returns unique results (no duplicates)"""
    mode = SelfImprovementMode()
    todos = mode._find_todos()

    # Check for uniqueness
    seen = set()
    for todo in todos:
        key = (todo['file'], todo['line'])
        assert key not in seen, f"Duplicate TODO found: {key}"
        seen.add(key)


def test_chaos_creative_mode():
    """Test chaos/creative mode"""
    mode = ChaosCreativeMode()
    tasks = mode.generate_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) > 0
    assert 'project_type' in tasks[0]['params']


def test_research_discovery_mode():
    """Test research/discovery mode"""
    mode = ResearchDiscoveryMode()
    tasks = mode.generate_tasks()
    assert isinstance(tasks, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

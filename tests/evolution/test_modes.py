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
        assert 'priority' in todo
        assert 'category' in todo
        assert isinstance(todo['file'], str)
        assert isinstance(todo['line'], str)
        assert isinstance(todo['text'], str)
        assert isinstance(todo['priority'], int)
        assert isinstance(todo['category'], str)
        # Priority should be 1-10
        assert 1 <= todo['priority'] <= 10


def test_find_todos_filters_self_reference():
    """Test that _find_todos filters out self-referential TODOs"""
    mode = SelfImprovementMode()
    todos = mode._find_todos()

    # Should not include self-referential comments from self_improvement.py
    for todo in todos:
        assert 'Check for TODOs/FIXMEs' not in todo['text']
        assert 'intelligent prioritization' not in todo['text']


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


def test_prioritize_todo():
    """Test priority and category calculation for TODOs"""
    mode = SelfImprovementMode()

    # FIXME should have higher priority than TODO
    fixme_priority, fixme_category = mode._prioritize_todo("# FIXME: broken feature", "/test/file.py")
    todo_priority, todo_category = mode._prioritize_todo("# TODO: add feature", "/test/file.py")
    assert fixme_priority > todo_priority
    assert fixme_category == 'bug_fix'

    # Urgent keywords should increase priority
    urgent_priority, urgent_category = mode._prioritize_todo("# TODO: URGENT - fix this", "/test/file.py")
    normal_priority, normal_category = mode._prioritize_todo("# TODO: add feature", "/test/file.py")
    assert urgent_priority > normal_priority
    assert urgent_category == 'urgent'

    # Security-related should have high priority and correct category
    security_priority, security_category = mode._prioritize_todo("# TODO: fix authentication vulnerability", "/test/file.py")
    assert security_category == 'security'
    assert security_priority >= 8

    # Performance-related
    perf_priority, perf_category = mode._prioritize_todo("# TODO: optimize query performance", "/test/file.py")
    assert perf_category == 'performance'

    # Testing-related
    test_priority, test_category = mode._prioritize_todo("# TODO: add test coverage", "/test/file.py")
    assert test_category == 'testing'

    # Documentation should have lower priority
    doc_priority, doc_category = mode._prioritize_todo("# TODO: document this function", "/test/file.py")
    assert doc_category == 'documentation'
    assert doc_priority <= 5

    # Refactoring
    refactor_priority, refactor_category = mode._prioritize_todo("# TODO: refactor this code", "/test/file.py")
    assert refactor_category == 'refactoring'

    # Core files should get priority boost
    core_priority, _ = mode._prioritize_todo("# TODO: fix this", "/core/engine.py")
    normal_priority, _ = mode._prioritize_todo("# TODO: fix this", "/utils/helper.py")
    assert core_priority > normal_priority


def test_prioritized_task_generation():
    """Test that tasks are generated with priority metadata"""
    mode = SelfImprovementMode()
    tasks = mode.generate_tasks()

    # Each task should have priority and category in params
    for task in tasks:
        if task.get('type') == 'self_improvement':
            params = task.get('params', {})
            if params.get('action') == 'implement_todo':
                assert 'priority' in params
                assert 'category' in params


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

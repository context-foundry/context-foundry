"""Tests for Task Queue Manager"""

import pytest
import tempfile
from pathlib import Path
from tools.evolution.task_queue import TaskQueueManager, TaskStatus


def test_create_task():
    """Test task creation"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_queue.db")
        queue = TaskQueueManager(db_path=db_path)

        task_id = queue.create_task(
            task_type="self_improvement", params={"test": "data"}, priority=7
        )

        assert task_id is not None
        assert len(task_id) > 0

        # Verify task was created
        task = queue.get_task(task_id)
        assert task is not None
        assert task.type == "self_improvement"
        assert task.status == TaskStatus.PENDING.value
        assert task.priority == 7
        assert task.params["test"] == "data"


def test_get_next_task():
    """Test getting next pending task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_queue.db")
        queue = TaskQueueManager(db_path=db_path)

        # Create low priority task
        task1_id = queue.create_task("self_improvement", {}, priority=3)

        # Create high priority task
        task2_id = queue.create_task("chaos_creative", {}, priority=8)

        # Should get high priority task first
        task = queue.get_next_task()
        assert task is not None
        assert task.id == task2_id
        assert task.priority == 8
        assert task.status == TaskStatus.RUNNING.value


def test_list_tasks():
    """Test listing tasks with filters"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_queue.db")
        queue = TaskQueueManager(db_path=db_path)

        queue.create_task("self_improvement", {}, priority=5)
        queue.create_task("chaos_creative", {}, priority=7)
        queue.create_task("research", {}, priority=3)

        # List all tasks
        tasks = queue.list_tasks(limit=10)
        assert len(tasks) == 3

        # List by status
        pending_tasks = queue.list_tasks(status=TaskStatus.PENDING.value)
        assert len(pending_tasks) == 3


def test_project_registry():
    """Test project registration"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_queue.db")
        queue = TaskQueueManager(db_path=db_path)

        queue.register_project(
            path="/path/to/project", project_type="web-app", metadata={"tech": "react"}
        )

        projects = queue.list_projects()
        assert len(projects) == 1
        assert projects[0]["path"] == "/path/to/project"
        assert projects[0]["project_type"] == "web-app"
        assert projects[0]["metadata"]["tech"] == "react"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

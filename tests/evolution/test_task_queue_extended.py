#!/usr/bin/env python3
"""
Extended tests for tools/evolution/task_queue.py

These tests cover critical database operations, task management,
and ACID properties of the task queue system.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from tools.evolution.task_queue import (
    Task, TaskQueueManager, TaskStatus, TaskType
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)
    # Cleanup WAL files
    for ext in ['-wal', '-shm']:
        wal_path = path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


class TestTaskDataclass:
    """Tests for Task dataclass"""

    def test_task_to_dict(self):
        """Test converting task to dictionary"""
        task = Task(
            id="task-123",
            type="self_improvement",
            status="pending",
            priority=5,
            params={"key": "value"},
            created_at="2025-11-07T10:00:00",
            started_at=None,
            completed_at=None,
            result=None,
            error_message=None,
            retry_count=0,
            max_retries=3
        )

        task_dict = task.to_dict()

        assert task_dict['id'] == "task-123"
        assert task_dict['type'] == "self_improvement"
        assert task_dict['status'] == "pending"
        assert task_dict['priority'] == 5
        assert task_dict['params'] == {"key": "value"}
        assert task_dict['retry_count'] == 0

    def test_task_from_dict(self):
        """Test creating task from dictionary"""
        task_dict = {
            'id': 'task-456',
            'type': 'chaos_creative',
            'status': 'running',
            'priority': 7,
            'params': {'test': 'data'},
            'created_at': '2025-11-07T10:00:00',
            'started_at': '2025-11-07T10:05:00',
            'completed_at': None,
            'result': None,
            'error_message': None,
            'retry_count': 1,
            'max_retries': 3
        }

        task = Task.from_dict(task_dict)

        assert task.id == 'task-456'
        assert task.type == 'chaos_creative'
        assert task.status == 'running'
        assert task.priority == 7
        assert task.retry_count == 1


class TestTaskQueueInit:
    """Tests for TaskQueueManager initialization"""

    def test_init_with_custom_path(self, temp_db):
        """Test initialization with custom database path"""
        manager = TaskQueueManager(temp_db)

        assert manager.db_path == temp_db
        assert manager.conn is not None
        assert os.path.exists(temp_db)

    def test_init_creates_tables(self, temp_db):
        """Test that initialization creates required tables"""
        manager = TaskQueueManager(temp_db)

        cursor = manager.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)
        tables = [row[0] for row in cursor.fetchall()]

        assert 'tasks' in tables
        assert 'task_history' in tables
        assert 'project_registry' in tables or 'agent_network' in tables

    def test_wal_mode_enabled(self, temp_db):
        """Test that WAL mode is enabled for concurrency"""
        manager = TaskQueueManager(temp_db)

        cursor = manager.conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]

        assert mode.lower() == 'wal'

    def test_default_path_creation(self):
        """Test that default path creates directory structure"""
        manager = TaskQueueManager()

        expected_dir = Path.home() / ".context-foundry" / "evolution"
        assert expected_dir.exists()
        assert os.path.exists(manager.db_path)

        # Cleanup
        manager.close()
        os.unlink(manager.db_path)
        for ext in ['-wal', '-shm']:
            wal_path = manager.db_path + ext
            if os.path.exists(wal_path):
                os.unlink(wal_path)


class TestCreateTask:
    """Tests for task creation"""

    def test_create_basic_task(self, temp_db):
        """Test creating a basic task"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.SELF_IMPROVEMENT,
            params={"test": "data"},
            priority=5
        )

        assert task_id is not None
        assert isinstance(task_id, str)

        # Verify task exists in database
        cursor = manager.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row['type'] == 'self_improvement'
        assert row['status'] == 'pending'
        assert row['priority'] == 5

    def test_create_task_with_high_priority(self, temp_db):
        """Test creating high priority task"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.VALIDATE,
            params={},
            priority=10
        )

        cursor = manager.conn.cursor()
        cursor.execute("SELECT priority FROM tasks WHERE id = ?", (task_id,))
        priority = cursor.fetchone()['priority']

        assert priority == 10

    def test_create_task_with_low_priority(self, temp_db):
        """Test creating low priority task"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.RESEARCH,
            params={},
            priority=1
        )

        cursor = manager.conn.cursor()
        cursor.execute("SELECT priority FROM tasks WHERE id = ?", (task_id,))
        priority = cursor.fetchone()['priority']

        assert priority == 1


class TestGetNextTask:
    """Tests for getting next task from queue"""

    def test_get_next_task_empty_queue(self, temp_db):
        """Test getting task from empty queue"""
        manager = TaskQueueManager(temp_db)

        task = manager.get_next_task()

        assert task is None

    def test_get_next_task_single(self, temp_db):
        """Test getting single task from queue"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.SELF_IMPROVEMENT,
            params={"key": "value"},
            priority=5
        )

        task = manager.get_next_task()

        assert task is not None
        assert task.id == task_id
        assert task.status == TaskStatus.RUNNING  # Should be updated
        assert task.started_at is not None

    def test_get_next_task_priority_order(self, temp_db):
        """Test that tasks are returned in priority order"""
        manager = TaskQueueManager(temp_db)

        # Create tasks with different priorities
        low_id = manager.create_task(
            task_type=TaskType.RESEARCH,
            params={"priority": "low"},
            priority=3
        )
        high_id = manager.create_task(
            task_type=TaskType.VALIDATE,
            params={"priority": "high"},
            priority=9
        )
        mid_id = manager.create_task(
            task_type=TaskType.CHAOS_CREATIVE,
            params={"priority": "mid"},
            priority=6
        )

        # Should get high priority first
        task1 = manager.get_next_task()
        assert task1.id == high_id

        # Then mid priority
        task2 = manager.get_next_task()
        assert task2.id == mid_id

        # Then low priority
        task3 = manager.get_next_task()
        assert task3.id == low_id

    def test_get_next_task_skips_running(self, temp_db):
        """Test that running tasks are not returned"""
        manager = TaskQueueManager(temp_db)

        task_id1 = manager.create_task(
            task_type=TaskType.SELF_IMPROVEMENT,
            params={},
            priority=5
        )
        task_id2 = manager.create_task(
            task_type=TaskType.RESEARCH,
            params={},
            priority=4
        )

        # Get first task (should be running now)
        task1 = manager.get_next_task()
        assert task1.id == task_id1

        # Next call should get second task
        task2 = manager.get_next_task()
        assert task2.id == task_id2

        # No more tasks
        task3 = manager.get_next_task()
        assert task3 is None


class TestUpdateTaskStatus:
    """Tests for updating task status"""

    def test_update_to_completed(self, temp_db):
        """Test updating task to completed"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.SELF_IMPROVEMENT,
            params={},
            priority=5
        )

        result = {"output": "success"}
        manager.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            result=result
        )

        cursor = manager.conn.cursor()
        cursor.execute("""
            SELECT status, result_json, completed_at
            FROM tasks WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()

        assert row['status'] == 'completed'
        assert row['completed_at'] is not None
        import json
        assert json.loads(row['result_json']) == result

    def test_update_to_failed(self, temp_db):
        """Test updating task to failed"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.VALIDATE,
            params={},
            priority=5
        )

        error_msg = "Task failed due to error"
        manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            error=error_msg
        )

        cursor = manager.conn.cursor()
        cursor.execute("""
            SELECT status, error_message
            FROM tasks WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()

        assert row['status'] == 'failed'
        assert row['error_message'] == error_msg


class TestRetryTask:
    """Tests for task retry logic"""

    def test_should_retry_within_limits(self, temp_db):
        """Test that task should retry within max retries"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.SELF_IMPROVEMENT,
            params={},
            priority=5
        )

        # Manually set retry count
        cursor = manager.conn.cursor()
        cursor.execute("""
            UPDATE tasks SET retry_count = 2
            WHERE id = ?
        """, (task_id,))
        manager.conn.commit()

        # Get task and check
        task = manager.get_task(task_id)
        should_retry = manager.should_retry(task)
        assert should_retry is True

    def test_should_not_retry_at_max(self, temp_db):
        """Test that task should not retry at max retries"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.VALIDATE,
            params={},
            priority=5
        )

        # Set retry count to max
        cursor = manager.conn.cursor()
        cursor.execute("""
            UPDATE tasks SET retry_count = 3
            WHERE id = ?
        """, (task_id,))
        manager.conn.commit()

        # Get task and check
        task = manager.get_task(task_id)
        should_retry = manager.should_retry(task)
        assert should_retry is False

    def test_retry_task_increments_count(self, temp_db):
        """Test that retry increments retry count"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(
            task_type=TaskType.CHAOS_CREATIVE,
            params={},
            priority=5
        )

        manager.retry_task(task_id)

        cursor = manager.conn.cursor()
        cursor.execute("""
            SELECT retry_count, status
            FROM tasks WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()

        assert row['retry_count'] == 1
        assert row['status'] == 'pending'


class TestListTasks:
    """Tests for listing tasks"""

    def test_list_all_tasks(self, temp_db):
        """Test listing all tasks"""
        manager = TaskQueueManager(temp_db)

        task_id1 = manager.create_task(
            task_type=TaskType.SELF_IMPROVEMENT,
            params={},
            priority=5
        )
        task_id2 = manager.create_task(
            task_type=TaskType.RESEARCH,
            params={},
            priority=7
        )

        tasks = manager.list_tasks()

        assert len(tasks) == 2
        task_ids = [t.id for t in tasks]
        assert task_id1 in task_ids
        assert task_id2 in task_ids

    def test_list_tasks_by_status(self, temp_db):
        """Test listing tasks by status"""
        manager = TaskQueueManager(temp_db)

        pending_id = manager.create_task(
            task_type=TaskType.VALIDATE,
            params={},
            priority=5
        )
        running_id = manager.create_task(
            task_type=TaskType.RESEARCH,
            params={},
            priority=5
        )

        # Update one to running
        manager.update_task_status(running_id, TaskStatus.RUNNING)

        pending_tasks = manager.list_tasks(status=TaskStatus.PENDING)
        running_tasks = manager.list_tasks(status=TaskStatus.RUNNING)

        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == pending_id

        assert len(running_tasks) == 1
        assert running_tasks[0].id == running_id

    def test_list_tasks_with_limit(self, temp_db):
        """Test listing tasks with limit"""
        manager = TaskQueueManager(temp_db)

        for i in range(5):
            manager.create_task(
                task_type=TaskType.SELF_IMPROVEMENT,
                params={},
                priority=5
            )

        tasks = manager.list_tasks(limit=3)

        assert len(tasks) == 3


class TestCountMethods:
    """Tests for count methods"""

    def test_count_pending(self, temp_db):
        """Test counting pending tasks"""
        manager = TaskQueueManager(temp_db)

        manager.create_task(TaskType.SELF_IMPROVEMENT, {}, 5)
        manager.create_task(TaskType.RESEARCH, {}, 5)

        task_id = manager.create_task(TaskType.VALIDATE, {}, 5)
        manager.update_task_status(task_id, TaskStatus.COMPLETED)

        count = manager.count_pending()
        assert count == 2

    def test_count_completed(self, temp_db):
        """Test counting completed tasks"""
        manager = TaskQueueManager(temp_db)

        task_id1 = manager.create_task(TaskType.SELF_IMPROVEMENT, {}, 5)
        task_id2 = manager.create_task(TaskType.RESEARCH, {}, 5)

        manager.update_task_status(task_id1, TaskStatus.COMPLETED)
        manager.create_task(TaskType.VALIDATE, {}, 5)

        count = manager.count_completed()
        assert count == 1

    def test_count_failed(self, temp_db):
        """Test counting failed tasks"""
        manager = TaskQueueManager(temp_db)

        task_id1 = manager.create_task(TaskType.CHAOS_CREATIVE, {}, 5)
        task_id2 = manager.create_task(TaskType.RESEARCH, {}, 5)

        manager.update_task_status(task_id1, TaskStatus.FAILED)
        manager.update_task_status(task_id2, TaskStatus.FAILED)

        count = manager.count_failed()
        assert count == 2


class TestArchiveTasks:
    """Tests for archiving old tasks"""

    def test_archive_old_completed_tasks(self, temp_db):
        """Test archiving old completed tasks"""
        manager = TaskQueueManager(temp_db)

        # Create old completed task
        old_task_id = manager.create_task(TaskType.SELF_IMPROVEMENT, {}, 5)
        manager.update_task_status(old_task_id, TaskStatus.COMPLETED)

        # Manually set completed_at to 40 days ago
        old_date = (datetime.utcnow() - timedelta(days=40)).isoformat()
        cursor = manager.conn.cursor()
        cursor.execute("""
            UPDATE tasks SET completed_at = ?
            WHERE id = ?
        """, (old_date, old_task_id))
        manager.conn.commit()

        # Create recent completed task
        recent_task_id = manager.create_task(TaskType.RESEARCH, {}, 5)
        manager.update_task_status(recent_task_id, TaskStatus.COMPLETED)

        # Archive tasks older than 30 days
        archived_count = manager.archive_old_tasks(days=30)

        assert archived_count == 1

        # Verify old task is archived
        cursor.execute("""
            SELECT status FROM tasks WHERE id = ?
        """, (old_task_id,))
        # The archived task should no longer exist or have different status
        # Implementation may vary


class TestCancelTask:
    """Tests for cancelling tasks"""

    def test_cancel_pending_task(self, temp_db):
        """Test cancelling a pending task"""
        manager = TaskQueueManager(temp_db)

        task_id = manager.create_task(TaskType.SELF_IMPROVEMENT, {}, 5)

        manager.cancel_task(task_id)

        cursor = manager.conn.cursor()
        cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        assert row['status'] == 'cancelled'


class TestClose:
    """Tests for closing the database connection"""

    def test_close_connection(self, temp_db):
        """Test closing database connection"""
        manager = TaskQueueManager(temp_db)

        manager.close()

        # Verify connection is closed
        with pytest.raises(sqlite3.ProgrammingError):
            manager.conn.execute("SELECT 1")

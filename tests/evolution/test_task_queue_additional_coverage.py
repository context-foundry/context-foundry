#!/usr/bin/env python3
"""
Additional critical path tests for TaskQueueManager - Round 3
Targets remaining uncovered lines and edge cases
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

from tools.evolution.task_queue import TaskQueueManager, Task, TaskStatus, TaskType


class TestTaskQueueExceptionHandling(unittest.TestCase):
    """Test exception handling in get_next_task"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_queue.db"
        self.queue = TaskQueueManager(db_path=str(self.db_path))

    def tearDown(self):
        """Clean up"""
        self.queue.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_next_task_with_no_tasks_returns_none(self):
        """Test that get_next_task returns None when queue is empty"""
        # Don't create any tasks
        task = self.queue.get_next_task()

        # Should return None
        self.assertIsNone(task)


class TestTaskQueueCalculateBackoff(unittest.TestCase):
    """Test backoff calculation for retries"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_queue.db"
        self.queue = TaskQueueManager(db_path=str(self.db_path))

    def tearDown(self):
        """Clean up"""
        self.queue.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculate_backoff_returns_exponential_delay(self):
        """Test that calculate_backoff returns exponential backoff"""
        # Test various retry counts - actual implementation is 2^retry_count
        backoff_0 = self.queue.calculate_backoff(0)
        backoff_1 = self.queue.calculate_backoff(1)
        backoff_2 = self.queue.calculate_backoff(2)
        backoff_3 = self.queue.calculate_backoff(3)

        # Verify exponential growth (2^n)
        self.assertEqual(backoff_0, 1)   # 2^0
        self.assertEqual(backoff_1, 2)   # 2^1
        self.assertEqual(backoff_2, 4)   # 2^2
        self.assertEqual(backoff_3, 8)   # 2^3

    def test_calculate_backoff_grows_exponentially(self):
        """Test that backoff grows exponentially with retries"""
        # High retry count
        backoff_10 = self.queue.calculate_backoff(10)
        backoff_20 = self.queue.calculate_backoff(20)

        # Verify exponential growth
        self.assertEqual(backoff_10, 1024)     # 2^10
        self.assertEqual(backoff_20, 1048576)  # 2^20


class TestTaskQueueCountRunning(unittest.TestCase):
    """Test count_running method"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_queue.db"
        self.queue = TaskQueueManager(db_path=str(self.db_path))

    def tearDown(self):
        """Clean up"""
        self.queue.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_count_running_returns_zero_when_no_running_tasks(self):
        """Test count_running returns 0 when no tasks are running"""
        # Create some tasks but not running (remove description param)
        self.queue.create_task(
            task_type=TaskType.SELF_IMPROVEMENT.value,
            params={'description': 'Pending task'}
        )

        count = self.queue.count_running()
        self.assertEqual(count, 0)

    def test_count_running_returns_correct_count(self):
        """Test count_running returns correct number of running tasks"""
        # Create and start multiple tasks (remove description param)
        task_id_1 = self.queue.create_task(
            task_type=TaskType.SELF_IMPROVEMENT.value,
            params={'description': 'Task 1'}
        )
        task_id_2 = self.queue.create_task(
            task_type=TaskType.SELF_IMPROVEMENT.value,
            params={'description': 'Task 2'}
        )
        task_id_3 = self.queue.create_task(
            task_type=TaskType.SELF_IMPROVEMENT.value,
            params={'description': 'Task 3'}
        )

        # Mark first two as running
        self.queue.update_task_status(task_id_1, TaskStatus.RUNNING.value)
        self.queue.update_task_status(task_id_2, TaskStatus.RUNNING.value)

        count = self.queue.count_running()
        self.assertEqual(count, 2)


class TestTaskQueueAgentRegistration(unittest.TestCase):
    """Test agent registration methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_queue.db"
        self.queue = TaskQueueManager(db_path=str(self.db_path))

    def tearDown(self):
        """Clean up"""
        self.queue.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_agent_creates_agent_record(self):
        """Test that register_agent creates an agent in database"""
        agent_name = "Test Agent"
        agent_url = "http://localhost:8080"
        capabilities = ['code', 'test']

        # Use correct signature: register_agent(name, url, capabilities)
        agent_id = self.queue.register_agent(agent_name, agent_url, capabilities)

        # Verify agent was created
        agent = self.queue.get_agent(agent_id)
        self.assertIsNotNone(agent)
        self.assertEqual(agent['name'], agent_name)
        self.assertEqual(agent['url'], agent_url)
        self.assertEqual(agent['capabilities'], capabilities)

    def test_get_agent_returns_none_for_nonexistent_agent(self):
        """Test that get_agent returns None for agent that doesn't exist"""
        agent = self.queue.get_agent('nonexistent-agent-xyz')
        self.assertIsNone(agent)

    def test_register_agent_with_minimal_params(self):
        """Test register_agent with only required params"""
        agent_name = "Minimal Agent"

        # Register with just name
        agent_id = self.queue.register_agent(agent_name)

        # Verify agent was created
        agent = self.queue.get_agent(agent_id)
        self.assertIsNotNone(agent)
        self.assertEqual(agent['name'], agent_name)
        self.assertIsNone(agent['url'])
        self.assertEqual(agent['capabilities'], [])


class TestTaskQueueGetTaskEdgeCases(unittest.TestCase):
    """Test get_task method edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_queue.db"
        self.queue = TaskQueueManager(db_path=str(self.db_path))

    def tearDown(self):
        """Clean up"""
        self.queue.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_task_returns_none_for_nonexistent_task(self):
        """Test that get_task returns None for task that doesn't exist"""
        task = self.queue.get_task('nonexistent-task-id')
        self.assertIsNone(task)

    def test_get_task_returns_task_with_all_fields(self):
        """Test that get_task returns complete task object"""
        task_id = self.queue.create_task(
            task_type=TaskType.SELF_IMPROVEMENT.value,
            params={'key': 'value', 'description': 'Complete task test'},
            priority=10
        )

        task = self.queue.get_task(task_id)

        self.assertIsNotNone(task)
        self.assertEqual(task.id, task_id)
        self.assertEqual(task.type, TaskType.SELF_IMPROVEMENT.value)
        # Description is in params, not a top-level attribute
        self.assertEqual(task.params['description'], "Complete task test")
        self.assertEqual(task.priority, 10)


class TestTaskQueueListTasksFiltering(unittest.TestCase):
    """Test list_tasks filtering with edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_queue.db"
        self.queue = TaskQueueManager(db_path=str(self.db_path))

    def tearDown(self):
        """Clean up"""
        self.queue.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_tasks_with_empty_status_filter(self):
        """Test list_tasks handles empty status list"""
        # Create some tasks
        self.queue.create_task(
            task_type=TaskType.SELF_IMPROVEMENT.value,
            params={'description': 'Task 1'}
        )

        # Query with empty status filter
        tasks = self.queue.list_tasks(status=[])

        # Should return all tasks (empty filter means no filtering)
        self.assertEqual(len(tasks), 1)

    def test_list_tasks_respects_limit(self):
        """Test that list_tasks respects limit parameter"""
        # Create multiple tasks
        for i in range(10):
            self.queue.create_task(
                task_type=TaskType.SELF_IMPROVEMENT.value,
                params={'description': f'Task {i}'}
            )

        # Query with limit
        tasks = self.queue.list_tasks(limit=5)

        self.assertEqual(len(tasks), 5)


if __name__ == '__main__':
    unittest.main()

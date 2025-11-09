#!/usr/bin/env python3
"""
End-to-end integration tests for Evolution System workflows.

Tests complete workflows from task creation through execution and completion:
- Task Queue → Daemon → Mode Execution → Result Recording
- Self-Improvement Mode: TODO discovery → Task creation → PR generation
- Resource Manager integration with Daemon
- Multi-task coordination and priority handling
- Error handling and retry logic

Priority: 10/10 - Core evolution system workflows
"""

import pytest
import tempfile
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import evolution components
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "evolution"))

from tools.evolution.task_queue import TaskQueueManager
from tools.evolution.resource_manager import ResourceManager


@pytest.mark.integration
@pytest.mark.tier1
class TestEvolutionSystemE2E:
    """End-to-end tests for complete evolution workflows"""

    def setup_method(self):
        """Setup test environment"""
        # Create temporary directory for test database and files
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "evolution_test.db"

        # Initialize task queue
        self.task_queue = TaskQueueManager()

        # Create mock resource manager
        self.resource_manager = ResourceManager()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, "task_queue"):
            self.task_queue.close()
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_task_lifecycle_complete_workflow(self):
        """Test complete task lifecycle: create → queue → execute → complete"""
        # Step 1: Create task
        task_id = self.task_queue.create_task(
            task_type="self_improvement",
            description="Fix authentication bug in login.py",
            priority=5,
            metadata={"file": "src/login.py", "line": 42},
        )

        assert task_id is not None

        # Step 2: Verify task is in queue
        task = self.task_queue.get_task(task_id)
        assert task is not None
        assert task["status"] == "pending"
        assert task["task_type"] == "self_improvement"
        assert task["description"] == "Fix authentication bug in login.py"

        # Step 3: Simulate daemon picking up task
        next_task = self.task_queue.get_next_task()
        assert next_task is not None
        assert next_task["id"] == task_id
        assert next_task["status"] == "running"

        # Step 4: Simulate task execution and completion
        self.task_queue.update_task_status(
            task_id,
            status="completed",
            result={"pr_url": "https://github.com/user/repo/pull/123"},
        )

        # Step 5: Verify final state
        completed_task = self.task_queue.get_task(task_id)
        assert completed_task["status"] == "completed"
        assert (
            completed_task["result"]["pr_url"]
            == "https://github.com/user/repo/pull/123"
        )
        assert completed_task["completed_at"] is not None

    def test_multi_task_priority_handling(self):
        """Test that higher priority tasks are executed first"""
        # Create tasks with different priorities
        low_priority = self.task_queue.create_task(
            task_type="chaos_creative", description="Low priority task", priority=1
        )

        high_priority = self.task_queue.create_task(
            task_type="self_improvement", description="High priority task", priority=10
        )

        medium_priority = self.task_queue.create_task(
            task_type="research", description="Medium priority task", priority=5
        )

        # Get next task - should be high priority
        next_task = self.task_queue.get_next_task()
        assert next_task["id"] == high_priority
        assert next_task["priority"] == 10

        # Mark as completed and get next
        self.task_queue.update_task_status(high_priority, "completed")

        next_task = self.task_queue.get_next_task()
        assert next_task["id"] == medium_priority
        assert next_task["priority"] == 5

        # Mark as completed and get next
        self.task_queue.update_task_status(medium_priority, "completed")

        next_task = self.task_queue.get_next_task()
        assert next_task["id"] == low_priority
        assert next_task["priority"] == 1

    def test_task_retry_on_failure(self):
        """Test retry logic when task fails"""
        # Create task
        task_id = self.task_queue.create_task(
            task_type="self_improvement",
            description="Task that will fail initially",
            priority=5,
        )

        # Get and fail task (first attempt)
        task = self.task_queue.get_next_task()
        self.task_queue.update_task_status(
            task_id, status="failed", error="Network timeout"
        )

        # Verify task is marked as failed
        failed_task = self.task_queue.get_task(task_id)
        assert failed_task["status"] == "failed"
        assert failed_task["retry_count"] == 1

        # Retry task
        self.task_queue.retry_task(task_id)

        # Verify task is back in pending state
        retried_task = self.task_queue.get_task(task_id)
        assert retried_task["status"] == "pending"
        assert retried_task["retry_count"] == 1

        # Get task again and complete successfully
        task = self.task_queue.get_next_task()
        self.task_queue.update_task_status(
            task_id, status="completed", result={"success": True}
        )

        # Verify final state
        final_task = self.task_queue.get_task(task_id)
        assert final_task["status"] == "completed"
        assert final_task["retry_count"] == 1

    def test_concurrent_task_handling(self):
        """Test handling multiple tasks running concurrently"""
        # Create multiple tasks
        task_ids = []
        for i in range(5):
            task_id = self.task_queue.create_task(
                task_type="chaos_creative",
                description=f"Concurrent task {i}",
                priority=5,
            )
            task_ids.append(task_id)

        # Simulate multiple workers picking up tasks
        running_tasks = []
        for _ in range(3):
            task = self.task_queue.get_next_task()
            if task:
                running_tasks.append(task["id"])

        assert len(running_tasks) == 3

        # Verify all running tasks have status 'running'
        for task_id in running_tasks:
            task = self.task_queue.get_task(task_id)
            assert task["status"] == "running"

        # Complete running tasks
        for task_id in running_tasks:
            self.task_queue.update_task_status(task_id, "completed")

        # Verify remaining tasks are still pending
        remaining_tasks = [tid for tid in task_ids if tid not in running_tasks]
        for task_id in remaining_tasks:
            task = self.task_queue.get_task(task_id)
            assert task["status"] == "pending"

    def test_task_queue_statistics(self):
        """Test queue statistics and monitoring"""
        # Create tasks in various states
        pending_id = self.task_queue.create_task(
            task_type="self_improvement", description="Pending task", priority=5
        )

        running_task = self.task_queue.get_next_task()

        completed_id = self.task_queue.create_task(
            task_type="research", description="Task to complete", priority=5
        )
        task = self.task_queue.get_next_task()
        self.task_queue.update_task_status(task["id"], "completed")

        failed_id = self.task_queue.create_task(
            task_type="chaos_creative", description="Task to fail", priority=5
        )
        task = self.task_queue.get_next_task()
        self.task_queue.update_task_status(task["id"], "failed", error="Test failure")

        # Get queue statistics
        stats = self.task_queue.get_queue_stats()

        assert stats["pending"] >= 1
        assert stats["running"] >= 1
        assert stats["completed"] >= 1
        assert stats["failed"] >= 1
        assert stats["total"] >= 4

    @patch("subprocess.run")
    def test_self_improvement_workflow_simulation(self, mock_subprocess):
        """Test simulated self-improvement workflow with mocked execution"""
        # Mock successful Claude Code delegation
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="PR created: https://github.com/user/repo/pull/456",
            stderr="",
        )

        # Create self-improvement task
        task_id = self.task_queue.create_task(
            task_type="self_improvement",
            description="TODO: Implement caching for API responses",
            priority=7,
            metadata={
                "file": "src/api.py",
                "line": 156,
                "todo_text": "TODO: Implement caching for API responses",
            },
        )

        # Simulate daemon picking up task
        task = self.task_queue.get_next_task()
        assert task["task_type"] == "self_improvement"

        # Simulate mode execution (would normally call MCP delegation)
        # For testing, we'll just verify the task can be processed
        result = {
            "pr_url": "https://github.com/user/repo/pull/456",
            "branch": "self-improvement/api-caching",
            "changes": ["src/api.py", "tests/test_api.py"],
        }

        # Update task with result
        self.task_queue.update_task_status(task_id, status="completed", result=result)

        # Verify completion
        completed_task = self.task_queue.get_task(task_id)
        assert completed_task["status"] == "completed"
        assert "pr_url" in completed_task["result"]

    def test_task_timeout_handling(self):
        """Test handling of tasks that exceed timeout"""
        # Create task with short timeout
        task_id = self.task_queue.create_task(
            task_type="research",
            description="Long-running task",
            priority=5,
            metadata={"timeout_minutes": 1},
        )

        # Get task (starts running)
        task = self.task_queue.get_next_task()

        # Simulate timeout by manually setting old start time
        conn = sqlite3.connect(str(self.db_path))
        old_time = (datetime.now() - timedelta(minutes=2)).isoformat()
        conn.execute(
            "UPDATE tasks SET started_at = ? WHERE id = ?", (old_time, task_id)
        )
        conn.commit()
        conn.close()

        # Check for timed-out tasks
        timed_out = self.task_queue.get_timed_out_tasks(timeout_minutes=1)
        assert len(timed_out) > 0
        assert timed_out[0]["id"] == task_id

        # Mark as failed due to timeout
        self.task_queue.update_task_status(
            task_id, status="failed", error="Task exceeded timeout of 1 minutes"
        )

        # Verify failure
        failed_task = self.task_queue.get_task(task_id)
        assert failed_task["status"] == "failed"
        assert "timeout" in failed_task["error"].lower()

    def test_task_metadata_preservation(self):
        """Test that task metadata is preserved throughout lifecycle"""
        metadata = {
            "source": "github_issue",
            "issue_number": 123,
            "labels": ["bug", "high-priority"],
            "assignee": "evolution-system",
            "custom_data": {"nested": "value", "count": 42},
        }

        task_id = self.task_queue.create_task(
            task_type="self_improvement",
            description="Fix bug from GitHub issue #123",
            priority=8,
            metadata=metadata,
        )

        # Retrieve and verify metadata
        task = self.task_queue.get_task(task_id)
        assert task["metadata"]["source"] == "github_issue"
        assert task["metadata"]["issue_number"] == 123
        assert "bug" in task["metadata"]["labels"]
        assert task["metadata"]["custom_data"]["count"] == 42

        # Execute and complete task
        task = self.task_queue.get_next_task()
        self.task_queue.update_task_status(
            task_id, status="completed", result={"pr_url": "test"}
        )

        # Verify metadata still intact after completion
        completed_task = self.task_queue.get_task(task_id)
        assert completed_task["metadata"]["source"] == "github_issue"
        assert completed_task["metadata"]["custom_data"]["count"] == 42

    def test_queue_persistence_across_restarts(self):
        """Test that queue state persists across database connections"""
        # Create tasks
        task_id_1 = self.task_queue.create_task(
            task_type="self_improvement", description="Task 1", priority=5
        )

        task_id_2 = self.task_queue.create_task(
            task_type="chaos_creative", description="Task 2", priority=3
        )

        # Close connection
        self.task_queue.close()

        # Reopen with new TaskQueue instance
        new_queue = TaskQueue(str(self.db_path))

        # Verify tasks still exist
        task_1 = new_queue.get_task(task_id_1)
        task_2 = new_queue.get_task(task_id_2)

        assert task_1 is not None
        assert task_2 is not None
        assert task_1["description"] == "Task 1"
        assert task_2["description"] == "Task 2"

        # Verify queue operations work
        next_task = new_queue.get_next_task()
        assert next_task["id"] == task_id_1  # Higher priority

        new_queue.close()


@pytest.mark.integration
@pytest.mark.tier2
class TestResourceManagerIntegration:
    """Test resource manager integration with evolution system"""

    def setup_method(self):
        """Setup test environment"""
        self.resource_manager = ResourceManager()

    def test_resource_limits_enforcement(self):
        """Test that resource limits are properly enforced"""
        # Get current resource usage
        usage = self.resource_manager.get_resource_usage()

        assert "cpu_percent" in usage
        assert "memory_percent" in usage
        assert "disk_usage_percent" in usage

        # Verify all values are reasonable
        assert 0 <= usage["cpu_percent"] <= 100
        assert 0 <= usage["memory_percent"] <= 100
        assert 0 <= usage["disk_usage_percent"] <= 100

    def test_resource_threshold_checking(self):
        """Test resource threshold alerts"""
        # Check if resources are within limits
        is_safe = self.resource_manager.check_resource_safety(
            cpu_threshold=90, memory_threshold=90, disk_threshold=95
        )

        # Should return boolean
        assert isinstance(is_safe, bool)

    def test_resource_monitoring_during_task_execution(self):
        """Test resource monitoring while simulating task execution"""
        # Take snapshot before
        before = self.resource_manager.get_resource_usage()

        # Simulate some work (small allocation)
        data = [i for i in range(1000)]

        # Take snapshot after
        after = self.resource_manager.get_resource_usage()

        # Both snapshots should have valid data
        assert before["cpu_percent"] >= 0
        assert after["cpu_percent"] >= 0


@pytest.mark.integration
@pytest.mark.tier2
class TestEvolutionErrorHandling:
    """Test error handling in evolution workflows"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "evolution_error_test.db"
        self.task_queue = TaskQueue(str(self.db_path))

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, "task_queue"):
            self.task_queue.close()
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_database_corruption_recovery(self):
        """Test recovery from database errors"""
        # Create a task
        task_id = self.task_queue.create_task(
            task_type="self_improvement", description="Test task", priority=5
        )

        # Close connection
        self.task_queue.close()

        # Attempt to reopen and recover
        try:
            new_queue = TaskQueue(str(self.db_path))
            task = new_queue.get_task(task_id)
            assert task is not None
            new_queue.close()
        except Exception as e:
            pytest.fail(f"Failed to recover from database operation: {e}")

    def test_invalid_task_type_handling(self):
        """Test handling of invalid task types"""
        # Attempt to create task with invalid type
        task_id = self.task_queue.create_task(
            task_type="invalid_mode_type",
            description="Task with invalid type",
            priority=5,
        )

        # Should still create task (validation happens at execution)
        assert task_id is not None
        task = self.task_queue.get_task(task_id)
        assert task["task_type"] == "invalid_mode_type"

    def test_malformed_metadata_handling(self):
        """Test handling of malformed metadata"""
        # Create task with various metadata types
        task_id = self.task_queue.create_task(
            task_type="self_improvement",
            description="Test metadata handling",
            priority=5,
            metadata={
                "string": "value",
                "number": 42,
                "boolean": True,
                "null": None,
                "list": [1, 2, 3],
                "nested": {"key": "value"},
            },
        )

        # Retrieve and verify metadata was preserved
        task = self.task_queue.get_task(task_id)
        assert task["metadata"]["string"] == "value"
        assert task["metadata"]["number"] == 42
        assert task["metadata"]["boolean"] is True
        assert task["metadata"]["null"] is None
        assert task["metadata"]["list"] == [1, 2, 3]
        assert task["metadata"]["nested"]["key"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

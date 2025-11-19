"""
Tests for job lifecycle management.

Tests cover:
- Job status transitions (QUEUED → RUNNING → SUCCEEDED/FAILED/TIMED_OUT/CANCELLED)
- Agent tracking (register/complete agents)
- Timeout handling
- Stall detection
"""

import pytest
import time
from datetime import datetime, timedelta

from context_foundry.daemon.models import (
    Job,
    JobStatus,
    JobType,
    AgentTracker,
)
from context_foundry.daemon.jobs import JobManager
from context_foundry.daemon.config import Config
from context_foundry.daemon.store import Store


class TestJobStatus:
    """Test JobStatus enum"""

    def test_terminal_states_includes_timed_out(self):
        """TIMED_OUT should be in terminal states"""
        terminal = JobStatus.terminal_states()
        assert JobStatus.TIMED_OUT in terminal
        assert JobStatus.SUCCEEDED in terminal
        assert JobStatus.FAILED in terminal
        assert JobStatus.CANCELLED in terminal

    def test_running_not_terminal(self):
        """RUNNING should not be terminal"""
        terminal = JobStatus.terminal_states()
        assert JobStatus.RUNNING not in terminal
        assert JobStatus.QUEUED not in terminal


class TestAgentTracker:
    """Test AgentTracker class"""

    def test_register_agent(self):
        """Test registering agents increments counters"""
        tracker = AgentTracker(job_id="test-job")

        count = tracker.register_agent("agent-1")
        assert count == 1
        assert tracker.active_count == 1
        assert tracker.total_spawned == 1
        assert "agent-1" in tracker.agent_ids

    def test_complete_agent_success(self):
        """Test completing agent decrements counter"""
        tracker = AgentTracker(job_id="test-job")
        tracker.register_agent("agent-1")
        tracker.register_agent("agent-2")

        count = tracker.complete_agent("agent-1", success=True)
        assert count == 1
        assert tracker.active_count == 1
        assert tracker.total_completed == 1
        assert "agent-1" not in tracker.agent_ids

    def test_complete_agent_failure(self):
        """Test completing agent with failure"""
        tracker = AgentTracker(job_id="test-job")
        tracker.register_agent("agent-1")

        tracker.complete_agent("agent-1", success=False)
        assert tracker.total_failed == 1
        assert tracker.total_completed == 0

    def test_is_complete(self):
        """Test is_complete when all agents done"""
        tracker = AgentTracker(job_id="test-job")

        # Not complete if nothing spawned
        assert not tracker.is_complete()

        tracker.register_agent("agent-1")
        assert not tracker.is_complete()

        tracker.complete_agent("agent-1")
        assert tracker.is_complete()

    def test_is_stalled(self):
        """Test stall detection"""
        tracker = AgentTracker(job_id="test-job")
        tracker.register_agent("agent-1")

        # Not stalled immediately
        assert not tracker.is_stalled(stall_threshold_seconds=0.1)

        # Set last activity to past
        tracker.last_activity = datetime.now() - timedelta(seconds=10)
        assert tracker.is_stalled(stall_threshold_seconds=5)

    def test_no_stall_if_no_active(self):
        """No stall if no active agents"""
        tracker = AgentTracker(job_id="test-job")
        tracker.register_agent("agent-1")
        tracker.complete_agent("agent-1")
        tracker.last_activity = datetime.now() - timedelta(seconds=100)

        # Not stalled because active_count is 0
        assert not tracker.is_stalled(stall_threshold_seconds=1)

    def test_serialization(self):
        """Test to_dict and from_dict"""
        tracker = AgentTracker(job_id="test-job")
        tracker.register_agent("agent-1")
        tracker.complete_agent("agent-1")

        data = tracker.to_dict()
        restored = AgentTracker.from_dict(data)

        assert restored.job_id == tracker.job_id
        assert restored.total_spawned == tracker.total_spawned
        assert restored.total_completed == tracker.total_completed


class TestJobManagerAgentTracking:
    """Test JobManager agent tracking methods"""

    @pytest.fixture
    def job_manager(self, tmp_path):
        """Create JobManager with temp storage"""
        config = Config()
        db_path = tmp_path / "test.db"
        store = Store(db_path)
        return JobManager(config=config, store=store)

    def test_register_agent(self, job_manager):
        """Test registering agent creates tracker"""
        job_id = "test-job-1"
        count = job_manager.register_agent(job_id, "agent-1")

        assert count == 1
        tracker = job_manager.get_agent_tracker(job_id)
        assert tracker is not None
        assert tracker.active_count == 1

    def test_complete_agent(self, job_manager):
        """Test completing agent"""
        job_id = "test-job-1"
        job_manager.register_agent(job_id, "agent-1")
        job_manager.register_agent(job_id, "agent-2")

        count = job_manager.complete_agent(job_id, "agent-1")
        assert count == 1

        count = job_manager.complete_agent(job_id, "agent-2")
        assert count == 0

    def test_is_job_stalled(self, job_manager):
        """Test stall detection through JobManager"""
        job_id = "test-job-1"

        # No tracker = not stalled
        assert not job_manager.is_job_stalled(job_id)

        job_manager.register_agent(job_id, "agent-1")

        # Just registered = not stalled
        assert not job_manager.is_job_stalled(job_id, stall_threshold_seconds=0.1)


class TestJobManagerTimeout:
    """Test JobManager timeout handling"""

    @pytest.fixture
    def job_manager(self, tmp_path):
        """Create JobManager with temp storage"""
        config = Config()
        config.default_job_timeout_minutes = 0.01  # Very short for testing
        db_path = tmp_path / "test.db"
        store = Store(db_path)
        return JobManager(config=config, store=store)

    def test_job_creation(self, job_manager):
        """Test basic job creation"""
        job = job_manager.submit_job(
            job_type=JobType.DELEGATION,
            params={"task": "test task"},
            priority=5,
        )

        assert job.status == JobStatus.QUEUED
        assert job.type == JobType.DELEGATION

        # Retrieve job
        retrieved = job_manager.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

    def test_cancel_queued_job(self, job_manager):
        """Test cancelling a queued job"""
        job = job_manager.submit_job(
            job_type=JobType.DELEGATION,
            params={"task": "test task"},
        )

        result = job_manager.cancel_job(job.id)
        assert result is True

        cancelled_job = job_manager.get_job(job.id)
        assert cancelled_job.status == JobStatus.CANCELLED

    def test_cannot_cancel_terminal_job(self, job_manager):
        """Test cannot cancel job in terminal state"""
        job = job_manager.submit_job(
            job_type=JobType.DELEGATION,
            params={"task": "test task"},
        )

        # First cancel
        job_manager.cancel_job(job.id)

        # Second cancel should fail
        result = job_manager.cancel_job(job.id)
        assert result is False

    def test_list_jobs_by_status(self, job_manager):
        """Test listing jobs by status"""
        # Create some jobs
        job1 = job_manager.submit_job(
            job_type=JobType.DELEGATION,
            params={"task": "task 1"},
        )
        job2 = job_manager.submit_job(
            job_type=JobType.DELEGATION,
            params={"task": "task 2"},
        )

        # Cancel one
        job_manager.cancel_job(job1.id)

        # List queued
        queued = job_manager.list_jobs(status=JobStatus.QUEUED)
        assert len(queued) == 1
        assert queued[0].id == job2.id

        # List cancelled
        cancelled = job_manager.list_jobs(status=JobStatus.CANCELLED)
        assert len(cancelled) == 1
        assert cancelled[0].id == job1.id


class TestJobModel:
    """Test Job model"""

    def test_job_creation(self):
        """Test Job.create factory method"""
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={"task": "build project"},
            priority=8,
        )

        assert job.id is not None
        assert job.type == JobType.AUTONOMOUS_BUILD
        assert job.status == JobStatus.QUEUED
        assert job.priority == 8
        assert job.params["task"] == "build project"

    def test_priority_clamping(self):
        """Test priority is clamped to [1, 10]"""
        job_low = Job.create(
            job_type=JobType.DELEGATION,
            params={},
            priority=0,
        )
        assert job_low.priority == 1

        job_high = Job.create(
            job_type=JobType.DELEGATION,
            params={},
            priority=100,
        )
        assert job_high.priority == 10

    def test_serialization(self):
        """Test to_dict and from_dict"""
        job = Job.create(
            job_type=JobType.AUTONOMOUS_BUILD,
            params={"task": "test"},
        )
        job.started_at = datetime.now()

        data = job.to_dict()
        restored = Job.from_dict(data)

        assert restored.id == job.id
        assert restored.type == job.type
        assert restored.status == job.status

    def test_duration(self):
        """Test duration calculation"""
        job = Job.create(
            job_type=JobType.DELEGATION,
            params={},
        )

        # No duration if not started
        assert job.duration() is None

        # Has duration if started
        job.started_at = datetime.now() - timedelta(seconds=10)
        duration = job.duration()
        assert duration is not None
        assert duration >= 10


class TestTimeoutIntegration:
    """Integration tests for timeout behavior"""

    @pytest.fixture
    def job_manager_with_runner(self, tmp_path):
        """Create JobManager with mock runner that times out"""
        config = Config()
        config.default_job_timeout_minutes = 0.01  # 600ms timeout
        db_path = tmp_path / "test.db"
        store = Store(db_path)

        # Create a runner that takes too long
        def slow_runner(job, store):
            time.sleep(10)  # Will exceed timeout
            return {"success": True}

        manager = JobManager(config=config, store=store, runner=slow_runner)
        return manager

    def test_timeout_sets_timed_out_status(self, job_manager_with_runner):
        """Verify timeout marks job as TIMED_OUT, not FAILED"""
        manager = job_manager_with_runner

        # Submit job
        job = manager.submit_job(
            job_type=JobType.DELEGATION,
            params={"task": "test", "timeout_minutes": 0.01},
            max_retries=3,  # Should NOT retry on timeout
        )

        # Start manager and execute
        manager.start(num_workers=1)
        time.sleep(2.0)  # Allow job to timeout and status to update
        manager.stop(timeout=5.0)

        # Verify status is TIMED_OUT
        final_job = manager.get_job(job.id)
        assert (
            final_job.status == JobStatus.TIMED_OUT
        ), f"Expected TIMED_OUT but got {final_job.status}"

        # Verify no retry happened
        assert (
            final_job.retry_count == 0
        ), f"Expected 0 retries but got {final_job.retry_count}"

    def test_timeout_cleans_up_agent_tracker(self, job_manager_with_runner):
        """Verify agent tracker is cleaned up on timeout"""
        manager = job_manager_with_runner

        job = manager.submit_job(
            job_type=JobType.DELEGATION,
            params={"task": "test", "timeout_minutes": 0.01},
        )

        # Register an agent before timeout
        manager.register_agent(job.id, "test-agent")

        # Execute
        manager.start(num_workers=1)
        time.sleep(2.0)  # Allow job to timeout and cleanup
        manager.stop(timeout=5.0)

        # Verify tracker was cleaned up
        tracker = manager.get_agent_tracker(job.id)
        assert tracker is None, "Agent tracker should be cleaned up on timeout"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

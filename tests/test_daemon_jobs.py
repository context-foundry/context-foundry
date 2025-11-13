"""
Unit tests for Context Foundry Daemon JobManager

Tests job submission, lifecycle management, worker execution, and error handling.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

from context_foundry.daemon.jobs import JobManager
from context_foundry.daemon.store import Store
from context_foundry.daemon.config import Config
from context_foundry.daemon.models import (
    JobStatus,
    JobType,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Create Store instance with temporary database"""
    return Store(temp_db)


@pytest.fixture
def config(temp_db):
    """Create Config instance for testing"""
    cfg = Config()
    cfg.data_dir = temp_db.parent
    cfg.log_dir = temp_db.parent / "logs"
    cfg.db_path = temp_db
    cfg.max_concurrent_jobs = 2
    cfg.default_max_retries = 2
    return cfg


@pytest.fixture
def mock_runner():
    """Create mock runner for testing"""
    return Mock(return_value={"status": "success"})


@pytest.fixture
def job_manager(config, store, mock_runner):
    """Create JobManager instance for testing"""
    return JobManager(config, store, runner=mock_runner)


class TestJobSubmission:
    """Test job submission and retrieval"""

    def test_submit_job(self, job_manager, store):
        """Test submitting a new job"""
        job = job_manager.submit_job(
            job_type=JobType.NEW_PROJECT,
            params={"task": "Build weather app"},
            priority=7,
        )

        assert job.id is not None
        assert job.type == JobType.NEW_PROJECT
        assert job.status == JobStatus.QUEUED
        assert job.priority == 7
        assert job.params == {"task": "Build weather app"}

        # Verify job was persisted
        retrieved = store.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

    def test_submit_job_with_default_priority(self, job_manager):
        """Test submitting job with default priority"""
        job = job_manager.submit_job(
            job_type=JobType.TESTING,
            params={},
        )

        assert job.priority == 5  # Default priority

    def test_submit_job_with_metadata(self, job_manager):
        """Test submitting job with metadata"""
        job = job_manager.submit_job(
            job_type=JobType.ENHANCEMENT,
            params={},
            metadata={"source": "cli", "user": "test"},
        )

        assert job.metadata == {"source": "cli", "user": "test"}

    def test_submit_job_creates_log(self, job_manager, store):
        """Test that job submission creates a log entry"""
        job = job_manager.submit_job(
            job_type=JobType.NEW_PROJECT,
            params={},
        )

        logs = store.get_logs(job.id)
        assert len(logs) >= 1
        assert logs[0].level == "INFO"
        assert "submitted" in logs[0].message.lower()

    def test_get_job(self, job_manager):
        """Test retrieving a job by ID"""
        job = job_manager.submit_job(
            job_type=JobType.TESTING,
            params={},
        )

        retrieved = job_manager.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

    def test_get_nonexistent_job(self, job_manager):
        """Test getting a job that doesn't exist"""
        result = job_manager.get_job("nonexistent-id")
        assert result is None

    def test_list_jobs(self, job_manager):
        """Test listing jobs"""
        job1 = job_manager.submit_job(JobType.NEW_PROJECT, {}, priority=5)
        job2 = job_manager.submit_job(JobType.ENHANCEMENT, {}, priority=8)
        job3 = job_manager.submit_job(JobType.TESTING, {}, priority=3)

        jobs = job_manager.list_jobs()
        assert len(jobs) == 3

        # Should be ordered by priority (highest first)
        assert jobs[0].id == job2.id  # priority 8
        assert jobs[1].id == job1.id  # priority 5
        assert jobs[2].id == job3.id  # priority 3

    def test_list_jobs_filter_by_status(self, job_manager, store):
        """Test listing jobs filtered by status"""
        job1 = job_manager.submit_job(JobType.NEW_PROJECT, {})
        job2 = job_manager.submit_job(JobType.ENHANCEMENT, {})

        # Manually update job2 status
        store.update_job_status(job2.id, JobStatus.RUNNING, started_at=datetime.now())

        queued_jobs = job_manager.list_jobs(status=JobStatus.QUEUED)
        assert len(queued_jobs) == 1
        assert queued_jobs[0].id == job1.id

        running_jobs = job_manager.list_jobs(status=JobStatus.RUNNING)
        assert len(running_jobs) == 1
        assert running_jobs[0].id == job2.id


class TestJobCancellation:
    """Test job cancellation"""

    def test_cancel_queued_job(self, job_manager, store):
        """Test cancelling a queued job"""
        job = job_manager.submit_job(JobType.TESTING, {})

        result = job_manager.cancel_job(job.id)
        assert result is True

        # Verify job status
        cancelled = store.get_job(job.id)
        assert cancelled.status == JobStatus.CANCELLED
        assert cancelled.completed_at is not None

    def test_cancel_nonexistent_job(self, job_manager):
        """Test cancelling a job that doesn't exist"""
        result = job_manager.cancel_job("nonexistent-id")
        assert result is False

    def test_cannot_cancel_completed_job(self, job_manager, store):
        """Test that completed jobs cannot be cancelled"""
        job = job_manager.submit_job(JobType.TESTING, {})

        # Mark as succeeded
        store.update_job_status(
            job.id,
            JobStatus.SUCCEEDED,
            completed_at=datetime.now(),
        )

        result = job_manager.cancel_job(job.id)
        assert result is False

        # Verify status unchanged
        job = store.get_job(job.id)
        assert job.status == JobStatus.SUCCEEDED

    def test_cancel_creates_log(self, job_manager, store):
        """Test that cancellation creates a log entry"""
        job = job_manager.submit_job(JobType.TESTING, {})

        job_manager.cancel_job(job.id)

        logs = store.get_logs(job.id)
        cancel_logs = [log for log in logs if "cancel" in log.message.lower()]
        assert len(cancel_logs) >= 1


class TestWorkerManagement:
    """Test worker lifecycle management"""

    def test_start_workers(self, job_manager):
        """Test starting worker threads"""
        assert not job_manager.is_running()

        job_manager.start(num_workers=2)

        assert job_manager.is_running()
        assert len(job_manager._workers) == 2

        # Cleanup
        job_manager.stop()

    def test_stop_workers(self, job_manager):
        """Test stopping worker threads"""
        job_manager.start(num_workers=2)
        assert job_manager.is_running()

        job_manager.stop()

        assert not job_manager.is_running()
        assert len(job_manager._workers) == 0

    def test_cannot_start_twice(self, job_manager, caplog):
        """Test that starting twice logs a warning"""
        job_manager.start()
        job_manager.start()  # Should log warning

        assert "already running" in caplog.text.lower()

        # Cleanup
        job_manager.stop()

    def test_stop_when_not_running(self, job_manager, caplog):
        """Test stopping when not running logs a warning"""
        job_manager.stop()

        assert "not running" in caplog.text.lower()


class TestJobExecution:
    """Test job execution via workers"""

    def test_execute_job_success(self, job_manager, mock_runner, store):
        """Test successful job execution"""
        # Start workers first
        job_manager.start(num_workers=1)

        # Submit job after workers are running
        job = job_manager.submit_job(JobType.TESTING, {"test": "data"})

        # Wait for job to complete (with timeout)
        max_wait = 10.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            job = store.get_job(job.id)
            if job.status == JobStatus.SUCCEEDED:
                break
            time.sleep(0.2)

        # Stop workers
        job_manager.stop()

        # Verify job succeeded
        assert job.status == JobStatus.SUCCEEDED
        assert job.result == {"status": "success"}
        assert job.started_at is not None
        assert job.completed_at is not None

        # Verify runner was called
        mock_runner.assert_called_once()

    def test_execute_job_failure(self, job_manager, store, config):
        """Test job execution with failure"""
        # Create runner that raises exception
        failing_runner = Mock(side_effect=RuntimeError("Job failed"))
        job_manager.runner = failing_runner

        # Start workers first
        job_manager.start(num_workers=1)

        # Submit job with low max_retries to fail faster
        job = job_manager.submit_job(JobType.TESTING, {}, max_retries=1)

        # Wait for job to fail (with longer timeout for retries)
        max_wait = 15.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            job = store.get_job(job.id)
            if job.status == JobStatus.FAILED:
                break
            time.sleep(0.2)

        # Stop workers
        job_manager.stop()

        # Verify job failed
        assert job.status == JobStatus.FAILED
        assert job.error is not None
        assert "Job failed" in job.error

    def test_job_retry_on_failure(self, job_manager, store, config):
        """Test that failed jobs are retried"""
        # Create runner that fails initially then succeeds
        call_count = {"count": 0}

        def retry_runner(job, store):
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise RuntimeError("First attempt failed")
            return {"status": "success"}

        job_manager.runner = retry_runner

        # Submit job
        job = job_manager.submit_job(JobType.TESTING, {}, max_retries=3)

        # Start workers
        job_manager.start(num_workers=1)

        # Wait for job to succeed (with timeout)
        max_wait = 10.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            job = store.get_job(job.id)
            if job.status == JobStatus.SUCCEEDED:
                break
            time.sleep(0.1)

        # Stop workers
        job_manager.stop()

        # Verify job eventually succeeded after retry
        assert job.status == JobStatus.SUCCEEDED
        assert job.retry_count == 1  # One retry was needed
        assert call_count["count"] == 2  # Runner called twice

    def test_job_max_retries_exceeded(self, job_manager, store):
        """Test that jobs fail after max retries"""
        # Create runner that always fails
        failing_runner = Mock(side_effect=RuntimeError("Always fails"))
        job_manager.runner = failing_runner

        # Submit job with low max_retries
        job = job_manager.submit_job(JobType.TESTING, {}, max_retries=1)

        # Start workers
        job_manager.start(num_workers=1)

        # Wait for job to fail permanently (with timeout)
        max_wait = 10.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            job = store.get_job(job.id)
            if job.status == JobStatus.FAILED and job.retry_count >= 1:
                break
            time.sleep(0.1)

        # Stop workers
        job_manager.stop()

        # Verify job failed permanently
        assert job.status == JobStatus.FAILED
        assert job.retry_count == 1  # Max retries reached

    def test_multiple_jobs_executed(self, job_manager, mock_runner, store):
        """Test that multiple jobs are executed"""
        # Submit multiple jobs
        job1 = job_manager.submit_job(JobType.TESTING, {})
        job2 = job_manager.submit_job(JobType.TESTING, {})
        job3 = job_manager.submit_job(JobType.TESTING, {})

        # Start workers
        job_manager.start(num_workers=2)

        # Wait for all jobs to complete (with timeout)
        max_wait = 10.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            jobs = store.list_jobs(status=JobStatus.SUCCEEDED)
            if len(jobs) >= 3:
                break
            time.sleep(0.1)

        # Stop workers
        job_manager.stop()

        # Verify all jobs succeeded
        succeeded_jobs = store.list_jobs(status=JobStatus.SUCCEEDED)
        assert len(succeeded_jobs) >= 3

        succeeded_ids = {j.id for j in succeeded_jobs}
        assert job1.id in succeeded_ids
        assert job2.id in succeeded_ids
        assert job3.id in succeeded_ids


class TestJobStats:
    """Test job statistics and monitoring"""

    def test_get_stats_not_running(self, job_manager):
        """Test getting stats when not running"""
        stats = job_manager.get_stats()

        assert stats["running"] is False
        assert stats["num_workers"] == 0
        assert stats["jobs_running"] == 0

    def test_get_stats_running(self, job_manager):
        """Test getting stats when running"""
        job_manager.start(num_workers=2)

        stats = job_manager.get_stats()

        assert stats["running"] is True
        assert stats["num_workers"] == 2

        # Cleanup
        job_manager.stop()

    def test_get_stats_with_jobs(self, job_manager, store):
        """Test getting stats with various job statuses"""
        # Create jobs in different states
        _ = job_manager.submit_job(JobType.TESTING, {})
        job2 = job_manager.submit_job(JobType.TESTING, {})

        store.update_job_status(
            job2.id, JobStatus.SUCCEEDED, completed_at=datetime.now()
        )

        stats = job_manager.get_stats()

        assert "job_counts" in stats
        assert stats["job_counts"].get("queued", 0) >= 1
        assert stats["job_counts"].get("succeeded", 0) >= 1

    def test_get_running_jobs(self, job_manager, store):
        """Test getting list of running jobs"""
        # Submit jobs
        _ = job_manager.submit_job(JobType.TESTING, {})
        job2 = job_manager.submit_job(JobType.TESTING, {})

        # Mark one as running
        store.update_job_status(job2.id, JobStatus.RUNNING, started_at=datetime.now())

        running_jobs = job_manager.get_running_jobs()

        assert len(running_jobs) == 1
        assert running_jobs[0].id == job2.id
        assert running_jobs[0].status == JobStatus.RUNNING


class TestNoRunner:
    """Test behavior when no runner is configured"""

    def test_execute_without_runner(self, config, store):
        """Test that execution fails gracefully without runner"""
        job_manager = JobManager(config, store, runner=None)

        # Start workers first
        job_manager.start(num_workers=1)

        # Submit job with low max_retries to fail faster
        job = job_manager.submit_job(JobType.TESTING, {}, max_retries=1)

        # Wait for job to fail (with longer timeout for retries)
        max_wait = 15.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            job = store.get_job(job.id)
            if job.status == JobStatus.FAILED:
                break
            time.sleep(0.2)

        # Stop workers
        job_manager.stop()

        # Verify job failed
        assert job.status == JobStatus.FAILED
        assert "No runner configured" in job.error

"""
Unit tests for Context Foundry Daemon Store

Tests SQLite persistence for jobs, phase events, and logs.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from context_foundry.daemon.store import Store
from context_foundry.daemon.models import (
    Job,
    JobStatus,
    JobType,
    PhaseEvent,
    LogEntry,
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


class TestStoreInitialization:
    """Test Store initialization and schema creation"""

    def test_creates_database_file(self, temp_db):
        """Test that Store creates database file"""
        assert not temp_db.exists()
        Store(temp_db)
        assert temp_db.exists()

    def test_creates_tables(self, store, temp_db):
        """Test that Store creates required tables"""
        import sqlite3

        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "jobs" in tables
        assert "phase_events" in tables
        assert "logs" in tables

    def test_enables_wal_mode(self, store, temp_db):
        """Test that WAL mode is enabled"""
        import sqlite3

        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()

        assert mode.upper() == "WAL"

    def test_creates_indexes(self, store, temp_db):
        """Test that indexes are created"""
        import sqlite3

        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "idx_jobs_status" in indexes
        assert "idx_jobs_priority" in indexes
        assert "idx_phase_events_job_id" in indexes
        assert "idx_logs_job_id" in indexes


class TestJobOperations:
    """Test Job CRUD operations"""

    def test_save_and_get_job(self, store):
        """Test saving and retrieving a job"""
        job = Job.create(
            job_type=JobType.NEW_PROJECT,
            params={"task": "Build weather app"},
            priority=7,
        )

        store.save_job(job)
        retrieved = store.get_job(job.id)

        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.type == JobType.NEW_PROJECT
        assert retrieved.status == JobStatus.QUEUED
        assert retrieved.priority == 7
        assert retrieved.params == {"task": "Build weather app"}

    def test_get_nonexistent_job(self, store):
        """Test getting a job that doesn't exist"""
        result = store.get_job("nonexistent-id")
        assert result is None

    def test_update_job(self, store):
        """Test updating a job via save_job"""
        job = Job.create(
            job_type=JobType.TESTING,
            params={"test": "all"},
        )

        store.save_job(job)

        # Update job
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        store.save_job(job)

        # Retrieve and verify
        retrieved = store.get_job(job.id)
        assert retrieved.status == JobStatus.RUNNING
        assert retrieved.started_at is not None

    def test_list_jobs_empty(self, store):
        """Test listing jobs when none exist"""
        jobs = store.list_jobs()
        assert jobs == []

    def test_list_jobs_all(self, store):
        """Test listing all jobs"""
        job1 = Job.create(JobType.NEW_PROJECT, params={}, priority=5)
        job2 = Job.create(JobType.ENHANCEMENT, params={}, priority=8)
        job3 = Job.create(JobType.TESTING, params={}, priority=3)

        store.save_job(job1)
        store.save_job(job2)
        store.save_job(job3)

        jobs = store.list_jobs()
        assert len(jobs) == 3

        # Should be ordered by priority DESC, then created_at ASC
        assert jobs[0].id == job2.id  # priority 8
        assert jobs[1].id == job1.id  # priority 5
        assert jobs[2].id == job3.id  # priority 3

    def test_list_jobs_filter_by_status(self, store):
        """Test listing jobs filtered by status"""
        job1 = Job.create(JobType.NEW_PROJECT, params={})
        job1.status = JobStatus.QUEUED

        job2 = Job.create(JobType.ENHANCEMENT, params={})
        job2.status = JobStatus.RUNNING

        job3 = Job.create(JobType.TESTING, params={})
        job3.status = JobStatus.SUCCEEDED

        store.save_job(job1)
        store.save_job(job2)
        store.save_job(job3)

        queued_jobs = store.list_jobs(status=JobStatus.QUEUED)
        assert len(queued_jobs) == 1
        assert queued_jobs[0].id == job1.id

        running_jobs = store.list_jobs(status=JobStatus.RUNNING)
        assert len(running_jobs) == 1
        assert running_jobs[0].id == job2.id

    def test_list_jobs_filter_by_type(self, store):
        """Test listing jobs filtered by type"""
        job1 = Job.create(JobType.NEW_PROJECT, params={})
        job2 = Job.create(JobType.ENHANCEMENT, params={})
        job3 = Job.create(JobType.NEW_PROJECT, params={})

        store.save_job(job1)
        store.save_job(job2)
        store.save_job(job3)

        new_project_jobs = store.list_jobs(job_type=JobType.NEW_PROJECT)
        assert len(new_project_jobs) == 2

        enhancement_jobs = store.list_jobs(job_type=JobType.ENHANCEMENT)
        assert len(enhancement_jobs) == 1

    def test_list_jobs_pagination(self, store):
        """Test job listing with limit and offset"""
        for i in range(10):
            job = Job.create(JobType.TESTING, params={"index": i})
            store.save_job(job)

        # First page
        page1 = store.list_jobs(limit=3, offset=0)
        assert len(page1) == 3

        # Second page
        page2 = store.list_jobs(limit=3, offset=3)
        assert len(page2) == 3

        # Pages should not overlap
        page1_ids = {j.id for j in page1}
        page2_ids = {j.id for j in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_update_job_status(self, store):
        """Test updating job status"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        # Update to RUNNING
        started_at = datetime.now()
        store.update_job_status(
            job.id,
            JobStatus.RUNNING,
            started_at=started_at,
        )

        retrieved = store.get_job(job.id)
        assert retrieved.status == JobStatus.RUNNING
        assert retrieved.started_at is not None

        # Update to SUCCEEDED
        completed_at = datetime.now()
        result = {"success": True}
        store.update_job_status(
            job.id,
            JobStatus.SUCCEEDED,
            completed_at=completed_at,
            result=result,
        )

        retrieved = store.get_job(job.id)
        assert retrieved.status == JobStatus.SUCCEEDED
        assert retrieved.completed_at is not None
        assert retrieved.result == result

    def test_update_job_status_with_error(self, store):
        """Test updating job status with error"""
        job = Job.create(JobType.TESTING, params={})
        store.save_job(job)

        error_msg = "Test failed: assertion error"
        store.update_job_status(
            job.id,
            JobStatus.FAILED,
            completed_at=datetime.now(),
            error=error_msg,
        )

        retrieved = store.get_job(job.id)
        assert retrieved.status == JobStatus.FAILED
        assert retrieved.error == error_msg

    def test_increment_retry_count(self, store):
        """Test incrementing retry count"""
        job = Job.create(JobType.ENHANCEMENT, params={})
        store.save_job(job)

        assert job.retry_count == 0

        # Increment once
        count = store.increment_retry_count(job.id)
        assert count == 1

        retrieved = store.get_job(job.id)
        assert retrieved.retry_count == 1

        # Increment again
        count = store.increment_retry_count(job.id)
        assert count == 2

        retrieved = store.get_job(job.id)
        assert retrieved.retry_count == 2

    def test_delete_job(self, store):
        """Test deleting a job"""
        job = Job.create(JobType.TESTING, params={})
        store.save_job(job)

        assert store.get_job(job.id) is not None

        deleted = store.delete_job(job.id)
        assert deleted is True

        assert store.get_job(job.id) is None

    def test_delete_nonexistent_job(self, store):
        """Test deleting a job that doesn't exist"""
        deleted = store.delete_job("nonexistent-id")
        assert deleted is False


class TestPhaseEventOperations:
    """Test PhaseEvent operations"""

    def test_save_and_get_phase_event(self, store):
        """Test saving and retrieving phase events"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        event = PhaseEvent.create(
            job_id=job.id,
            phase="Scout",
            status="started",
            details={"files_scanned": 42},
        )

        store.save_phase_event(event)

        events = store.get_phase_events(job.id)
        assert len(events) == 1
        assert events[0].phase == "Scout"
        assert events[0].status == "started"
        assert events[0].details == {"files_scanned": 42}

    def test_get_phase_events_multiple(self, store):
        """Test getting multiple phase events"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        # Create multiple events
        event1 = PhaseEvent.create(job.id, "Scout", "started")
        event2 = PhaseEvent.create(job.id, "Scout", "completed", duration_seconds=45.2)
        event3 = PhaseEvent.create(job.id, "Architect", "started")

        store.save_phase_event(event1)
        store.save_phase_event(event2)
        store.save_phase_event(event3)

        events = store.get_phase_events(job.id)
        assert len(events) == 3

        # Should be ordered by timestamp
        assert events[0].phase == "Scout"
        assert events[0].status == "started"
        assert events[1].phase == "Scout"
        assert events[1].status == "completed"
        assert events[2].phase == "Architect"

    def test_get_phase_events_filtered(self, store):
        """Test getting phase events filtered by phase"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        event1 = PhaseEvent.create(job.id, "Scout", "completed")
        event2 = PhaseEvent.create(job.id, "Architect", "started")
        event3 = PhaseEvent.create(job.id, "Architect", "completed")

        store.save_phase_event(event1)
        store.save_phase_event(event2)
        store.save_phase_event(event3)

        architect_events = store.get_phase_events(job.id, phase="Architect")
        assert len(architect_events) == 2
        assert all(e.phase == "Architect" for e in architect_events)

    def test_phase_event_with_metrics(self, store):
        """Test saving phase events with metrics"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        event = PhaseEvent.create(
            job_id=job.id,
            phase="Builder",
            status="completed",
            duration_seconds=120.5,
            tokens_used=15000,
            context_percent=75.2,
        )

        store.save_phase_event(event)

        events = store.get_phase_events(job.id)
        assert len(events) == 1
        assert events[0].duration_seconds == 120.5
        assert events[0].tokens_used == 15000
        assert events[0].context_percent == 75.2


class TestLogOperations:
    """Test LogEntry operations"""

    def test_save_and_get_logs(self, store):
        """Test saving and retrieving logs"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        log = LogEntry.create(
            job_id=job.id,
            level="INFO",
            message="Job started",
            phase="Scout",
            source="runner",
        )

        store.save_log(log)

        logs = store.get_logs(job.id)
        assert len(logs) == 1
        assert logs[0].level == "INFO"
        assert logs[0].message == "Job started"
        assert logs[0].phase == "Scout"
        assert logs[0].source == "runner"

    def test_get_logs_multiple(self, store):
        """Test getting multiple logs"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        log1 = LogEntry.create(job.id, "INFO", "Starting Scout")
        log2 = LogEntry.create(job.id, "INFO", "Scout completed")
        log3 = LogEntry.create(job.id, "INFO", "Starting Architect")

        store.save_log(log1)
        store.save_log(log2)
        store.save_log(log3)

        logs = store.get_logs(job.id)
        assert len(logs) == 3

        # Should be ordered by timestamp
        assert logs[0].message == "Starting Scout"
        assert logs[1].message == "Scout completed"
        assert logs[2].message == "Starting Architect"

    def test_get_logs_filtered_by_level(self, store):
        """Test getting logs filtered by level"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        log1 = LogEntry.create(job.id, "INFO", "Info message")
        log2 = LogEntry.create(job.id, "WARNING", "Warning message")
        log3 = LogEntry.create(job.id, "ERROR", "Error message")

        store.save_log(log1)
        store.save_log(log2)
        store.save_log(log3)

        error_logs = store.get_logs(job.id, level="ERROR")
        assert len(error_logs) == 1
        assert error_logs[0].message == "Error message"

    def test_get_logs_filtered_by_phase(self, store):
        """Test getting logs filtered by phase"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        log1 = LogEntry.create(job.id, "INFO", "Scout log", phase="Scout")
        log2 = LogEntry.create(job.id, "INFO", "Architect log", phase="Architect")
        log3 = LogEntry.create(job.id, "INFO", "Another Scout log", phase="Scout")

        store.save_log(log1)
        store.save_log(log2)
        store.save_log(log3)

        scout_logs = store.get_logs(job.id, phase="Scout")
        assert len(scout_logs) == 2
        assert all("Scout" in log.message or log.phase == "Scout" for log in scout_logs)

    def test_get_logs_with_limit(self, store):
        """Test getting logs with limit"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        # Create many logs
        for i in range(20):
            log = LogEntry.create(job.id, "INFO", f"Message {i}")
            store.save_log(log)

        logs = store.get_logs(job.id, limit=5)
        assert len(logs) == 5

    def test_log_with_metadata(self, store):
        """Test saving logs with metadata"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        log = LogEntry.create(
            job_id=job.id,
            level="ERROR",
            message="Build failed",
            metadata={"exit_code": 1, "command": "npm build"},
        )

        store.save_log(log)

        logs = store.get_logs(job.id)
        assert len(logs) == 1
        assert logs[0].metadata == {"exit_code": 1, "command": "npm build"}


class TestUtilityOperations:
    """Test utility operations"""

    def test_get_job_stats(self, store):
        """Test getting job statistics"""
        job1 = Job.create(JobType.NEW_PROJECT, params={})
        job1.status = JobStatus.QUEUED

        job2 = Job.create(JobType.ENHANCEMENT, params={})
        job2.status = JobStatus.RUNNING

        job3 = Job.create(JobType.TESTING, params={})
        job3.status = JobStatus.SUCCEEDED

        job4 = Job.create(JobType.VALIDATION, params={})
        job4.status = JobStatus.SUCCEEDED

        store.save_job(job1)
        store.save_job(job2)
        store.save_job(job3)
        store.save_job(job4)

        stats = store.get_job_stats()
        assert stats["queued"] == 1
        assert stats["running"] == 1
        assert stats["succeeded"] == 2

    def test_cleanup_old_jobs(self, store):
        """Test cleaning up old completed jobs"""
        # Create old completed job
        old_job = Job.create(JobType.TESTING, params={})
        old_job.status = JobStatus.SUCCEEDED
        old_job.completed_at = datetime.now() - timedelta(days=40)
        store.save_job(old_job)

        # Create recent completed job
        recent_job = Job.create(JobType.TESTING, params={})
        recent_job.status = JobStatus.SUCCEEDED
        recent_job.completed_at = datetime.now() - timedelta(days=10)
        store.save_job(recent_job)

        # Create running job (should not be deleted)
        running_job = Job.create(JobType.TESTING, params={})
        running_job.status = JobStatus.RUNNING
        store.save_job(running_job)

        # Cleanup jobs older than 30 days
        deleted = store.cleanup_old_jobs(days=30)
        assert deleted == 1

        # Verify only old job was deleted
        assert store.get_job(old_job.id) is None
        assert store.get_job(recent_job.id) is not None
        assert store.get_job(running_job.id) is not None

    def test_delete_job_cascades(self, store):
        """Test that deleting a job deletes related data"""
        job = Job.create(JobType.NEW_PROJECT, params={})
        store.save_job(job)

        # Add phase event and log
        event = PhaseEvent.create(job.id, "Scout", "completed")
        log = LogEntry.create(job.id, "INFO", "Job completed")

        store.save_phase_event(event)
        store.save_log(log)

        # Verify data exists
        assert len(store.get_phase_events(job.id)) == 1
        assert len(store.get_logs(job.id)) == 1

        # Delete job
        store.delete_job(job.id)

        # Verify related data is also deleted
        assert len(store.get_phase_events(job.id)) == 0
        assert len(store.get_logs(job.id)) == 0


class TestConcurrency:
    """Test concurrent access patterns"""

    def test_multiple_stores_same_db(self, temp_db):
        """Test that multiple Store instances can access same database"""
        store1 = Store(temp_db)
        store2 = Store(temp_db)

        job = Job.create(JobType.NEW_PROJECT, params={})
        store1.save_job(job)

        # Should be visible from other store instance
        retrieved = store2.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

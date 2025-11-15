"""
Tests for DaemonClient - SQLite integration
"""

import pytest
from unittest.mock import Mock, patch

from tools.tui_daemon.daemon_client import DaemonClient, SystemMetrics


class TestDaemonClient:
    """Test suite for DaemonClient"""

    def test_connection_success(self, tmp_path):
        """Test successful database connection"""
        # Create a fake db file
        db_file = tmp_path / "jobs.db"
        db_file.touch()

        with patch("tools.tui_daemon.daemon_client.Store") as mock_store_class:
            client = DaemonClient(str(db_file))
            result = client.connect()

            assert result is True
            assert client.connected is True
            mock_store_class.assert_called_once_with(str(db_file))

    def test_connection_failure_no_file(self):
        """Test connection failure when db doesn't exist"""
        client = DaemonClient("/nonexistent/jobs.db")
        result = client.connect()

        assert result is False
        assert client.connected is False

    def test_list_jobs(self, mock_daemon_client):
        """Test listing jobs"""
        jobs = mock_daemon_client.list_jobs(limit=10)

        assert len(jobs) == 3
        assert jobs[0].status == "succeeded"
        assert jobs[1].status == "running"
        assert jobs[2].status == "failed"

    def test_list_jobs_with_filter(self, mock_daemon_client):
        """Test listing jobs with status filter"""
        mock_daemon_client.store.list_jobs.return_value = [
            j for j in mock_daemon_client.store.list_jobs() if j.status == "running"
        ]

        jobs = mock_daemon_client.list_jobs(status="running")

        assert len(jobs) == 1
        assert jobs[0].status == "running"

    def test_get_job(self, mock_daemon_client):
        """Test getting a single job"""
        job_id = "a3f2b1c4-0000-0000-0000-000000000001"
        job = mock_daemon_client.get_job(job_id)

        assert job is not None
        assert job.job_id == job_id
        assert job.status == "succeeded"

    def test_get_job_not_found(self, mock_daemon_client):
        """Test getting non-existent job"""
        job = mock_daemon_client.get_job("nonexistent")

        assert job is None

    def test_get_metrics(self, mock_daemon_client):
        """Test calculating system metrics"""
        metrics = mock_daemon_client.get_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.total_jobs == 3
        assert metrics.active_jobs == 1  # Only 1 running job
        assert metrics.success_rate == pytest.approx(33.33, rel=0.1)
        assert metrics.avg_duration_seconds > 0

    def test_get_metrics_disconnected(self):
        """Test metrics when disconnected"""
        client = DaemonClient()
        metrics = client.get_metrics()

        assert metrics.total_jobs == 0
        assert metrics.active_jobs == 0
        assert metrics.success_rate == 0.0

    def test_submit_job(self, mock_daemon_client):
        """Test job submission"""
        mock_job = Mock()
        mock_job.job_id = "new-job-123"
        mock_daemon_client.job_manager = Mock()
        mock_daemon_client.job_manager.submit_job.return_value = mock_job

        params = {"task": "test build"}
        job = mock_daemon_client.submit_job("autonomous_build", params)

        assert job is not None
        assert job.job_id == "new-job-123"
        mock_daemon_client.job_manager.submit_job.assert_called_once_with(
            "autonomous_build", params
        )

    def test_cancel_job(self, mock_daemon_client):
        """Test job cancellation"""
        mock_daemon_client.job_manager = Mock()
        mock_daemon_client.job_manager.cancel_job.return_value = None

        result = mock_daemon_client.cancel_job("some-job-id")

        assert result is True
        mock_daemon_client.job_manager.cancel_job.assert_called_once_with("some-job-id")

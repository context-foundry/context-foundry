"""
Pytest configuration and fixtures for TUI tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from tools.tui_daemon.daemon_client import PhaseEvent, LogEntry


@pytest.fixture
def mock_store():
    """Mock Store with sample data"""
    store = Mock()

    # Sample jobs
    sample_jobs = [
        Mock(
            job_id="a3f2b1c4-0000-0000-0000-000000000001",
            job_type="autonomous_build",
            status="succeeded",
            priority=1,
            params_json='{"task": "build todo app"}',
            created_at=datetime.now() - timedelta(hours=1),
            started_at=datetime.now() - timedelta(minutes=50),
            completed_at=datetime.now() - timedelta(minutes=45),
            error_message=None,
            result_json='{"success": true}',
            params={"task": "build todo app"},
            duration=timedelta(minutes=5),
        ),
        Mock(
            job_id="b1c4d5e6-0000-0000-0000-000000000002",
            job_type="autonomous_build",
            status="running",
            priority=1,
            params_json='{"task": "create api"}',
            created_at=datetime.now() - timedelta(minutes=10),
            started_at=datetime.now() - timedelta(minutes=8),
            completed_at=None,
            error_message=None,
            result_json=None,
            params={"task": "create api"},
            duration=timedelta(minutes=8),
        ),
        Mock(
            job_id="c7d8e9f0-0000-0000-0000-000000000003",
            job_type="autonomous_build",
            status="failed",
            priority=1,
            params_json='{"task": "build game"}',
            created_at=datetime.now() - timedelta(hours=2),
            started_at=datetime.now() - timedelta(hours=2),
            completed_at=datetime.now() - timedelta(hours=1, minutes=55),
            error_message="Build failed",
            result_json=None,
            params={"task": "build game"},
            duration=timedelta(minutes=5),
        ),
    ]

    store.list_jobs.return_value = sample_jobs
    store.get_job.side_effect = lambda job_id: next(
        (job for job in sample_jobs if job.job_id == job_id), None
    )

    return store


@pytest.fixture
def mock_daemon_client(mock_store):
    """Mock DaemonClient with connected store"""
    from tools.tui_daemon.daemon_client import DaemonClient

    client = DaemonClient()
    client.store = mock_store
    client._connected = True

    return client


@pytest.fixture
def sample_phase_events():
    """Sample phase events for testing"""
    return [
        PhaseEvent(
            job_id="a3f2b1c4",
            phase="scout",
            status="completed",
            timestamp=datetime.now() - timedelta(minutes=50),
            progress_percent=100.0,
        ),
        PhaseEvent(
            job_id="a3f2b1c4",
            phase="architect",
            status="completed",
            timestamp=datetime.now() - timedelta(minutes=48),
            progress_percent=100.0,
        ),
        PhaseEvent(
            job_id="a3f2b1c4",
            phase="builder",
            status="started",
            timestamp=datetime.now() - timedelta(minutes=46),
            progress_percent=65.0,
        ),
    ]


@pytest.fixture
def sample_log_entries():
    """Sample log entries for testing"""
    return [
        LogEntry(
            job_id="a3f2b1c4",
            timestamp=datetime.now() - timedelta(minutes=50),
            level="INFO",
            message="Starting Scout phase...",
            phase="scout",
            source="scout_agent",
        ),
        LogEntry(
            job_id="a3f2b1c4",
            timestamp=datetime.now() - timedelta(minutes=49),
            level="SUCCESS",
            message="Scout completed successfully",
            phase="scout",
            source="scout_agent",
        ),
        LogEntry(
            job_id="a3f2b1c4",
            timestamp=datetime.now() - timedelta(minutes=48),
            level="INFO",
            message="Starting Architect phase...",
            phase="architect",
            source="architect_agent",
        ),
        LogEntry(
            job_id="a3f2b1c4",
            timestamp=datetime.now() - timedelta(minutes=46),
            level="WARNING",
            message="Large file detected, may take longer",
            phase="architect",
            source="architect_agent",
        ),
    ]


@pytest.fixture
def sample_nl_inputs():
    """Sample natural language inputs for parser testing"""
    return {
        "simple": "build a todo app with react",
        "with_directory": "create a fastapi backend in ~/api",
        "with_timeout": "make a game timeout 30m",
        "with_iterations": "build python cli iterations 3",
        "with_github": "create app from repo: user/project",
        "complete": "build todo app with react in ~/projects/todo timeout 1h iterations 5",
    }


@pytest.fixture
def expected_parse_results():
    """Expected parse results for NL inputs"""
    return {
        "simple": {
            "task": "build a todo app with react",
            "working_directory": "~/homelab/todo-app",
            "mode": "smart",
            "max_iterations": 5,
            "timeout": 3600,
        },
        "with_directory": {
            "task": "create a fastapi backend",
            "working_directory": "~/api",
            "mode": "smart",
        },
        "with_timeout": {
            "task": "make a game",
            "timeout": 1800,  # 30 minutes
        },
        "with_iterations": {
            "task": "build python cli",
            "max_iterations": 3,
        },
    }

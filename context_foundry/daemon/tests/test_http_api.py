"""
Tests for the HTTP/JSON Status API.

Tests cover:
- Health endpoint
- Jobs list endpoint
- Individual job endpoint
- Job timeline endpoint
- Job gates endpoint
- Job tree endpoint
- Recent events endpoint
- Error handling (404, validation)
"""

import json
import pytest
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

from context_foundry.daemon.http_api import (
    APIServer,
    get_job_tree,
    format_job_tree_ascii,
)
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from context_foundry.daemon.models import Job, JobType


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Create a Store instance with a temporary database."""
    return Store(temp_db)


@pytest.fixture
def state_machine(store):
    """Create a StateMachine instance."""
    return StateMachine(store)


@pytest.fixture
def sample_job(store):
    """Create a sample job for testing."""
    job = Job.create(
        job_type=JobType.AUTONOMOUS_BUILD,
        params={"task": "Build a test app", "working_directory": "/tmp/test"},
        priority=5,
    )
    store.save_job(job)
    return job


@pytest.fixture
def api_server(store):
    """Create and start an API server for testing."""
    # Use a random high port to avoid conflicts
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = APIServer(store=store, host="127.0.0.1", port=port)
    server.start()

    # Wait for server to be ready
    time.sleep(0.2)

    yield server

    server.stop()


def make_request(server: APIServer, path: str, method: str = "GET") -> dict:
    """Make an HTTP request and return JSON response."""
    url = f"{server.url}{path}"
    req = urllib.request.Request(url, method=method)

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return {
                "status": response.status,
                "data": json.loads(response.read().decode("utf-8")),
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "data": json.loads(e.read().decode("utf-8")),
        }


# =============================================================================
# HEALTH ENDPOINT TESTS
# =============================================================================


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_ok(self, api_server):
        """Health endpoint returns status ok."""
        result = make_request(api_server, "/health")

        assert result["status"] == 200
        assert result["data"]["status"] == "ok"
        assert "uptime_seconds" in result["data"]
        assert "active_jobs" in result["data"]
        assert "timestamp" in result["data"]

    def test_health_uptime_increases(self, api_server):
        """Health endpoint uptime increases over time."""
        result1 = make_request(api_server, "/health")
        time.sleep(0.5)
        result2 = make_request(api_server, "/health")

        assert result2["data"]["uptime_seconds"] > result1["data"]["uptime_seconds"]


# =============================================================================
# JOBS LIST ENDPOINT TESTS
# =============================================================================


class TestJobsListEndpoint:
    """Tests for GET /jobs."""

    def test_list_jobs_empty(self, api_server):
        """List jobs returns empty list when no jobs."""
        result = make_request(api_server, "/jobs")

        assert result["status"] == 200
        assert result["data"]["jobs"] == []
        assert result["data"]["count"] == 0

    def test_list_jobs_with_jobs(self, api_server, sample_job):
        """List jobs returns jobs."""
        result = make_request(api_server, "/jobs")

        assert result["status"] == 200
        assert result["data"]["count"] == 1
        assert result["data"]["jobs"][0]["job_id"] == sample_job.id

    def test_list_jobs_with_limit(self, api_server, store):
        """List jobs respects limit parameter."""
        # Create multiple jobs
        for i in range(10):
            job = Job.create(
                job_type=JobType.AUTONOMOUS_BUILD,
                params={"task": f"Task {i}"},
                priority=5,
            )
            store.save_job(job)

        result = make_request(api_server, "/jobs?limit=3")

        assert result["status"] == 200
        assert result["data"]["count"] == 3
        assert result["data"]["limit"] == 3

    def test_list_jobs_with_status_filter(self, api_server, store, state_machine):
        """List jobs respects status filter."""
        # Create jobs with different statuses
        job1 = Job.create(job_type=JobType.AUTONOMOUS_BUILD, params={}, priority=5)
        store.save_job(job1)
        state_machine.start_job(job1.id)

        job2 = Job.create(job_type=JobType.AUTONOMOUS_BUILD, params={}, priority=5)
        store.save_job(job2)
        # job2 stays queued

        result = make_request(api_server, "/jobs?status=running")

        assert result["status"] == 200
        assert result["data"]["count"] == 1
        assert result["data"]["jobs"][0]["status"] == "running"


# =============================================================================
# JOB DETAIL ENDPOINT TESTS
# =============================================================================


class TestJobDetailEndpoint:
    """Tests for GET /jobs/{job_id}."""

    def test_get_job_success(self, api_server, sample_job):
        """Get job returns job details."""
        result = make_request(api_server, f"/jobs/{sample_job.id}")

        assert result["status"] == 200
        assert result["data"]["job_id"] == sample_job.id
        assert result["data"]["status"] == "queued"
        assert "params" in result["data"]
        assert "phase_summary" in result["data"]

    def test_get_job_not_found(self, api_server):
        """Get job returns 404 for non-existent job."""
        result = make_request(api_server, "/jobs/nonexistent-job-id")

        assert result["status"] == 404
        assert "error" in result["data"]


# =============================================================================
# JOB TIMELINE ENDPOINT TESTS
# =============================================================================


class TestJobTimelineEndpoint:
    """Tests for GET /jobs/{job_id}/timeline."""

    def test_get_timeline_empty(self, api_server, sample_job):
        """Get timeline returns empty list for new job."""
        result = make_request(api_server, f"/jobs/{sample_job.id}/timeline")

        assert result["status"] == 200
        assert result["data"]["job_id"] == sample_job.id
        assert isinstance(result["data"]["events"], list)

    def test_get_timeline_with_events(self, api_server, sample_job, state_machine):
        """Get timeline returns events after state changes."""
        state_machine.start_job(sample_job.id)
        task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(task.id)

        result = make_request(api_server, f"/jobs/{sample_job.id}/timeline")

        assert result["status"] == 200
        assert len(result["data"]["events"]) > 0

    def test_get_timeline_not_found(self, api_server):
        """Get timeline returns 404 for non-existent job."""
        result = make_request(api_server, "/jobs/nonexistent-job-id/timeline")

        assert result["status"] == 404


# =============================================================================
# JOB GATES ENDPOINT TESTS
# =============================================================================


class TestJobGatesEndpoint:
    """Tests for GET /jobs/{job_id}/gates."""

    def test_get_gates_success(self, api_server, sample_job):
        """Get gates returns gate status."""
        result = make_request(api_server, f"/jobs/{sample_job.id}/gates")

        assert result["status"] == 200
        assert result["data"]["job_id"] == sample_job.id
        assert "gates" in result["data"]
        assert isinstance(result["data"]["gates"], list)
        assert "all_required_passed" in result["data"]

    def test_get_gates_with_progress(self, api_server, sample_job, state_machine):
        """Get gates shows progress after phase completion."""
        state_machine.start_job(sample_job.id)

        # Complete Scout phase
        task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(task.id)
        state_machine.complete_task(task.id, result={})

        result = make_request(api_server, f"/jobs/{sample_job.id}/gates")

        assert result["status"] == 200
        # Find Scout gate
        scout_gate = next(
            (g for g in result["data"]["gates"] if g["phase"] == "Scout"), None
        )
        assert scout_gate is not None
        assert scout_gate["status"] == "passed"

    def test_get_gates_not_found(self, api_server):
        """Get gates returns 404 for non-existent job."""
        result = make_request(api_server, "/jobs/nonexistent-job-id/gates")

        assert result["status"] == 404


# =============================================================================
# JOB TREE ENDPOINT TESTS
# =============================================================================


class TestJobTreeEndpoint:
    """Tests for GET /jobs/{job_id}/tree."""

    def test_get_tree_success(self, api_server, sample_job):
        """Get tree returns job tree structure."""
        result = make_request(api_server, f"/jobs/{sample_job.id}/tree")

        assert result["status"] == 200
        assert result["data"]["job_id"] == sample_job.id
        assert "phases" in result["data"]
        assert isinstance(result["data"]["phases"], list)

    def test_get_tree_with_tasks(self, api_server, sample_job, state_machine):
        """Get tree shows tasks within phases."""
        state_machine.start_job(sample_job.id)

        # Create tasks for multiple phases
        for i, phase in enumerate(["Scout", "Builder"]):
            task = state_machine.create_task_for_phase(sample_job.id, phase, i, 300)
            state_machine.start_task(task.id)

        result = make_request(api_server, f"/jobs/{sample_job.id}/tree")

        assert result["status"] == 200

        # Find Scout phase
        scout_phase = next(
            (p for p in result["data"]["phases"] if p["phase"] == "Scout"), None
        )
        assert scout_phase is not None
        assert len(scout_phase["tasks"]) > 0
        assert scout_phase["status"] == "running"

    def test_get_tree_not_found(self, api_server):
        """Get tree returns 404 for non-existent job."""
        result = make_request(api_server, "/jobs/nonexistent-job-id/tree")

        assert result["status"] == 404


# =============================================================================
# RECENT EVENTS ENDPOINT TESTS
# =============================================================================


class TestRecentEventsEndpoint:
    """Tests for GET /events/recent."""

    def test_get_recent_events_empty(self, api_server):
        """Get recent events returns empty list when no events."""
        result = make_request(api_server, "/events/recent")

        assert result["status"] == 200
        assert isinstance(result["data"]["events"], list)

    def test_get_recent_events_with_limit(self, api_server, sample_job, state_machine):
        """Get recent events respects limit parameter."""
        state_machine.start_job(sample_job.id)

        # Create multiple tasks to generate events
        for i, phase in enumerate(["Scout", "Architect", "Builder"]):
            task = state_machine.create_task_for_phase(sample_job.id, phase, i, 300)
            state_machine.start_task(task.id)

        result = make_request(api_server, "/events/recent?limit=2")

        assert result["status"] == 200
        # May have fewer if events haven't been generated
        assert result["data"]["count"] <= 2


# =============================================================================
# METRICS ENDPOINT TESTS
# =============================================================================


class TestMetricsEndpoint:
    """Tests for GET /metrics."""

    def test_get_metrics(self, api_server):
        """Get metrics returns metrics snapshot."""
        result = make_request(api_server, "/metrics")

        assert result["status"] == 200
        assert "metrics" in result["data"]
        assert "timestamp" in result["data"]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_for_unknown_path(self, api_server):
        """Unknown paths return 404."""
        result = make_request(api_server, "/unknown/path")

        assert result["status"] == 404
        assert "error" in result["data"]

    def test_invalid_status_filter(self, api_server):
        """Invalid status filter returns 400."""
        result = make_request(api_server, "/jobs?status=invalid_status")

        assert result["status"] == 400
        assert "error" in result["data"]


# =============================================================================
# JOB TREE HELPER TESTS
# =============================================================================


class TestJobTreeHelper:
    """Tests for get_job_tree helper function."""

    def test_get_job_tree_not_found(self, store):
        """get_job_tree returns error for non-existent job."""
        result = get_job_tree(store, "nonexistent")

        assert "error" in result

    def test_get_job_tree_empty_job(self, store, sample_job):
        """get_job_tree returns correct structure for job with no tasks."""
        result = get_job_tree(store, sample_job.id)

        assert result["job_id"] == sample_job.id
        assert result["status"] == "queued"
        assert "phases" in result
        # Dynamic phase discovery: no tasks means no phases
        assert len(result["phases"]) == 0

    def test_get_job_tree_with_tasks(self, store, sample_job, state_machine):
        """get_job_tree includes tasks in correct phases."""
        state_machine.start_job(sample_job.id)

        # Create Scout task
        scout_task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(scout_task.id)
        state_machine.complete_task(scout_task.id, result={})

        result = get_job_tree(store, sample_job.id)

        scout_phase = next((p for p in result["phases"] if p["phase"] == "Scout"), None)
        assert scout_phase is not None
        assert len(scout_phase["tasks"]) == 1
        assert scout_phase["tasks"][0]["task_id"] == scout_task.id


class TestFormatJobTreeAscii:
    """Tests for format_job_tree_ascii helper function."""

    def test_format_error_tree(self):
        """format_job_tree_ascii handles error case."""
        result = format_job_tree_ascii({"error": "Job not found"})

        assert "Error:" in result

    def test_format_empty_tree(self, store, sample_job):
        """format_job_tree_ascii formats empty job tree."""
        tree = get_job_tree(store, sample_job.id)
        result = format_job_tree_ascii(tree)

        assert sample_job.id[:8] in result
        assert "QUEUED" in result
        # Dynamic phase discovery: no tasks means no phases in output

    def test_format_tree_with_tasks(self, store, sample_job, state_machine):
        """format_job_tree_ascii includes task info."""
        state_machine.start_job(sample_job.id)

        task = state_machine.create_task_for_phase(sample_job.id, "Scout", 0, 300)
        state_machine.start_task(task.id)

        tree = get_job_tree(store, sample_job.id)
        result = format_job_tree_ascii(tree)

        assert "Scout" in result
        assert "RUNNING" in result
        assert task.id[:8] in result

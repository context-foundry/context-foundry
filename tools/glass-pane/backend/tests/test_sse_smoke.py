import pytest
from fastapi.testclient import TestClient
from main import app
from models.job import Job
from datetime import datetime

client = TestClient(app)


@pytest.fixture
def test_job():
    """Create a test job fixture (not inserted into DB)"""

    # Create test job matching new schema
    job = Job(
        id="test-sse-job-123",
        type="autonomous_build",
        status="running",
        created_at=datetime.utcnow().isoformat() + "Z",
        started_at=datetime.utcnow().isoformat() + "Z",
        completed_at=None,
        project_name="Test SSE Project",
        current_phase="scout",
        tokens_used=1000,
        total_files=5,
        params={"working_directory": "/tmp/test-sse", "task": "Test build"},
    )

    yield job


def test_sse_endpoint_exists(test_job):
    """Verify SSE endpoint responds with valid job"""
    response = client.get(f"/sse/jobs/{test_job.id}/updates")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"

    # Note: Full SSE streaming test requires real HTTP client (httpx)

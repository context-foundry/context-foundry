import pytest
from fastapi.testclient import TestClient
from main import app
from services.store_service import StoreService
from models.job import Job
from datetime import datetime

client = TestClient(app)


@pytest.fixture
def test_job():
    """Create a test job in the database"""
    store = StoreService()

    # Create test job
    job = Job(
        id="test-sse-job-123",
        project_name="Test SSE Project",
        project_path="/tmp/test-sse",
        current_phase="scout",
        status="in_progress",
        started_at=datetime.utcnow().isoformat() + "Z",
        tokens_used=1000,
        total_tokens=200000,
        total_files=0,
    )

    # Insert into DB
    store.create_job(job)

    yield job

    # Cleanup after test
    try:
        store.delete_job(job.id)
    except Exception:
        pass  # Job may already be deleted


def test_sse_endpoint_exists(test_job):
    """Verify SSE endpoint responds with valid job"""
    response = client.get(f"/sse/jobs/{test_job.id}/updates")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"

    # Note: Full SSE streaming test requires real HTTP client (httpx)

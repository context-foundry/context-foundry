from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify health check works"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_jobs_endpoint():
    """Verify jobs list endpoint"""
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert "jobs" in response.json()


def test_cors_headers():
    """Verify CORS headers present"""
    response = client.get("/api/jobs")
    assert "access-control-allow-origin" in response.headers

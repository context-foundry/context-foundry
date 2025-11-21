"""
API Integration Tests for Chat Endpoints with Working Directory.

Tests the full request chain through FastAPI endpoints to verify:
- Session creation with working_directory
- Session retrieval includes working_directory
- Session update (PATCH) can set/clear working_directory
"""

import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_create_session_with_working_directory():
    """Test POST /api/chat/sessions with working_directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create session with working directory
        response = client.post(
            "/api/chat/sessions",
            json={
                "model": "sonnet",
                "plan_mode": False,
                "bypass_permissions": False,
                "title": "Test Session",
                "working_directory": temp_dir,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["working_directory"] == str(Path(temp_dir).absolute())


def test_create_session_without_working_directory():
    """Test POST /api/chat/sessions without working_directory."""
    response = client.post(
        "/api/chat/sessions",
        json={
            "model": "sonnet",
            "plan_mode": False,
            "bypass_permissions": False,
            "title": "Test Session",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["working_directory"] is None


def test_get_session_includes_working_directory():
    """Test GET /api/chat/sessions/{id} returns working_directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create session
        create_response = client.post(
            "/api/chat/sessions",
            json={"model": "sonnet", "working_directory": temp_dir},
        )
        session_id = create_response.json()["id"]

        # Get session
        get_response = client.get(f"/api/chat/sessions/{session_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["session"]["working_directory"] == str(Path(temp_dir).absolute())


def test_update_session_working_directory():
    """Test PATCH /api/chat/sessions/{id} to update working_directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create session without working directory
        create_response = client.post("/api/chat/sessions", json={"model": "sonnet"})
        session_id = create_response.json()["id"]

        # Update with working directory
        update_response = client.patch(
            f"/api/chat/sessions/{session_id}", json={"working_directory": temp_dir}
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["working_directory"] == str(Path(temp_dir).absolute())


def test_clear_session_working_directory():
    """Test PATCH /api/chat/sessions/{id} to clear working_directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create session with working directory
        create_response = client.post(
            "/api/chat/sessions",
            json={"model": "sonnet", "working_directory": temp_dir},
        )
        session_id = create_response.json()["id"]
        assert create_response.json()["working_directory"] is not None

        # Clear by sending empty string
        clear_response = client.patch(
            f"/api/chat/sessions/{session_id}", json={"working_directory": ""}
        )

        assert clear_response.status_code == 200
        data = clear_response.json()
        assert data["working_directory"] is None


def test_list_sessions_includes_working_directory():
    """Test GET /api/chat/sessions includes working_directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create session with working directory
        client.post(
            "/api/chat/sessions",
            json={"model": "sonnet", "working_directory": temp_dir},
        )

        # List sessions
        list_response = client.get("/api/chat/sessions")

        assert list_response.status_code == 200
        data = list_response.json()
        assert "sessions" in data
        # At least one session should have working_directory
        assert any(
            s.get("working_directory") == str(Path(temp_dir).absolute())
            for s in data["sessions"]
        )


def test_invalid_working_directory_rejected():
    """Test that invalid working directories are rejected."""
    # Try to create session with nonexistent directory
    response = client.post(
        "/api/chat/sessions",
        json={
            "model": "sonnet",
            "working_directory": "/nonexistent/path/that/does/not/exist",
        },
    )

    assert response.status_code == 500  # Internal server error from validation
    assert "does not exist" in response.json()["detail"]

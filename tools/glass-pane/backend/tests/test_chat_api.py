"""
Automated tests for chat API endpoints.

Tests verify the chat session management, message handling,
and CLI integration endpoints work correctly.

Uses temporary test database configured in conftest.py to avoid
polluting production data.
"""


# Note: app and client fixtures are provided by conftest.py
# The test database is automatically set up before any imports


def test_cli_status_endpoint(client):
    """Verify Claude CLI status endpoint returns valid response"""
    response = client.get("/api/chat/cli-status")

    assert response.status_code == 200
    data = response.json()

    assert "available" in data
    assert isinstance(data["available"], bool)

    if data["available"]:
        assert "path" in data
        assert "version" in data
    else:
        assert "error" in data


def test_create_chat_session(client):
    """Test creating a new chat session"""
    response = client.post(
        "/api/chat/sessions",
        json={
            "model": "sonnet",
            "plan_mode": False,
            "bypass_permissions": True,
            "title": "Test Session",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify session structure
    assert "id" in data
    assert data["model"] == "sonnet"
    assert data["plan_mode"] is False
    assert data["bypass_permissions"] is True
    assert data["title"] == "Test Session"
    assert data["message_count"] == 0
    assert "created_at" in data
    assert "last_activity" in data

    return data["id"]  # Return for cleanup


def test_list_chat_sessions(client):
    """Test listing chat sessions"""
    # First create a session
    create_response = client.post(
        "/api/chat/sessions",
        json={"model": "sonnet", "plan_mode": False, "bypass_permissions": False},
    )
    assert create_response.status_code == 200
    created_session = create_response.json()

    # Now list sessions
    response = client.get("/api/chat/sessions")

    assert response.status_code == 200
    data = response.json()

    assert "sessions" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["sessions"], list)
    assert data["total"] >= 1

    # Verify our session is in the list
    session_ids = [s["id"] for s in data["sessions"]]
    assert created_session["id"] in session_ids


def test_get_session_history(client):
    """Test getting session history"""
    # Create session
    create_response = client.post(
        "/api/chat/sessions",
        json={"model": "haiku", "plan_mode": True, "bypass_permissions": False},
    )
    session_id = create_response.json()["id"]

    # Get history
    response = client.get(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 200
    data = response.json()

    assert "session" in data
    assert "messages" in data
    assert data["session"]["id"] == session_id
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) == 0  # New session has no messages


def test_update_session(client):
    """Test updating session settings"""
    # Create session
    create_response = client.post(
        "/api/chat/sessions",
        json={"model": "sonnet", "plan_mode": False, "bypass_permissions": False},
    )
    session_id = create_response.json()["id"]

    # Update session
    response = client.patch(
        f"/api/chat/sessions/{session_id}",
        json={"model": "opus", "plan_mode": True, "title": "Updated Title"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == session_id
    assert data["model"] == "opus"
    assert data["plan_mode"] is True
    assert data["title"] == "Updated Title"


def test_delete_session(client):
    """Test deleting a chat session"""
    # Create session
    create_response = client.post(
        "/api/chat/sessions",
        json={"model": "sonnet", "plan_mode": False, "bypass_permissions": False},
    )
    session_id = create_response.json()["id"]

    # Delete session
    response = client.delete(f"/api/chat/sessions/{session_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify session is deleted
    get_response = client.get(f"/api/chat/sessions/{session_id}")
    assert get_response.status_code == 404


def test_clear_session_messages(client):
    """Test clearing messages from a session"""
    # Create session
    create_response = client.post(
        "/api/chat/sessions",
        json={"model": "sonnet", "plan_mode": False, "bypass_permissions": False},
    )
    session_id = create_response.json()["id"]

    # Clear messages
    response = client.delete(f"/api/chat/sessions/{session_id}/messages")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "count" in data


def test_session_not_found(client):
    """Test 404 response for non-existent session"""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/api/chat/sessions/{fake_id}")
    assert response.status_code == 404


if __name__ == "__main__":
    # Run tests using pytest to ensure fixtures are used
    print("Running chat API tests with pytest...")
    print(
        "This ensures temporary test database is used (no production data pollution)\n"
    )
    import subprocess
    from pathlib import Path

    result = subprocess.run(
        ["pytest", __file__, "-v"], cwd=Path(__file__).parent.parent
    )
    exit(result.returncode)

"""
Unit tests for FastAPI endpoints.
"""

import pytest
import os
from fastapi.testclient import TestClient
from backend.main import app
from backend import database


# Use a test database
TEST_DB = "backend/test_api_tasks.db"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Set up test database before each test and clean up after."""
    original_db = database.DATABASE_FILE
    database.DATABASE_FILE = TEST_DB

    # Initialize the test database
    database.init_db()

    yield

    # Clean up
    database.DATABASE_FILE = original_db
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "task-manager-api"}


def test_get_tasks_empty(client):
    """Test getting tasks when none exist."""
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task(client):
    """Test creating a new task."""
    task_data = {"title": "Test Task", "description": "Test Description"}

    response = client.post("/tasks", json=task_data)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["description"] == "Test Description"
    assert data["completed"] is False
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_task_without_description(client):
    """Test creating a task without description."""
    task_data = {"title": "Test Task"}

    response = client.post("/tasks", json=task_data)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["description"] == ""


def test_create_task_validation_error_empty_title(client):
    """Test creating a task with empty title."""
    task_data = {"title": "", "description": "Description"}

    response = client.post("/tasks", json=task_data)

    assert response.status_code == 422


def test_create_task_validation_error_missing_title(client):
    """Test creating a task without title."""
    task_data = {"description": "Description"}

    response = client.post("/tasks", json=task_data)

    assert response.status_code == 422


def test_get_tasks_returns_created_tasks(client):
    """Test that created tasks are returned by GET /tasks."""
    # Create tasks
    client.post("/tasks", json={"title": "Task 1", "description": "Desc 1"})
    client.post("/tasks", json={"title": "Task 2", "description": "Desc 2"})

    # Get tasks
    response = client.get("/tasks")

    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    # Should be ordered by created_at DESC (newest first)
    assert tasks[0]["title"] == "Task 2"
    assert tasks[1]["title"] == "Task 1"


def test_update_task(client):
    """Test updating a task."""
    # Create task
    create_response = client.post(
        "/tasks",
        json={"title": "Original Title", "description": "Original Description"},
    )
    task_id = create_response.json()["id"]

    # Update task
    update_data = {
        "title": "Updated Title",
        "description": "Updated Description",
        "completed": True,
    }
    response = client.put(f"/tasks/{task_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Updated Description"
    assert data["completed"] is True


def test_update_task_partial(client):
    """Test partial update of a task."""
    # Create task
    create_response = client.post(
        "/tasks",
        json={"title": "Original Title", "description": "Original Description"},
    )
    task_id = create_response.json()["id"]

    # Update only completed status
    update_data = {"completed": True}
    response = client.put(f"/tasks/{task_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Original Title"  # Unchanged
    assert data["description"] == "Original Description"  # Unchanged
    assert data["completed"] is True  # Changed


def test_update_task_not_found(client):
    """Test updating a non-existent task."""
    update_data = {"title": "Updated Title"}
    response = client.put("/tasks/999", json=update_data)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_task_validation_error(client):
    """Test updating task with invalid data."""
    # Create task
    create_response = client.post("/tasks", json={"title": "Test Task"})
    task_id = create_response.json()["id"]

    # Try to update with empty title
    update_data = {"title": ""}
    response = client.put(f"/tasks/{task_id}", json=update_data)

    assert response.status_code == 422


def test_delete_task(client):
    """Test deleting a task."""
    # Create task
    create_response = client.post("/tasks", json={"title": "Test Task"})
    task_id = create_response.json()["id"]

    # Delete task
    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 204

    # Verify task is gone
    get_response = client.get("/tasks")
    tasks = get_response.json()
    assert len(tasks) == 0


def test_delete_task_not_found(client):
    """Test deleting a non-existent task."""
    response = client.delete("/tasks/999")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_cors_headers(client):
    """Test that CORS headers are present."""
    response = client.options("/tasks", headers={"Origin": "http://localhost:5173"})

    # FastAPI's CORSMiddleware should add these headers
    assert response.status_code == 200

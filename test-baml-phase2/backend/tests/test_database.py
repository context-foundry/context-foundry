"""
Unit tests for database operations.
"""

import pytest
import os
import sqlite3
from backend import database


# Use a test database
TEST_DB = "backend/test_tasks.db"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Set up test database before each test and clean up after."""
    # Override the database file
    original_db = database.DATABASE_FILE
    database.DATABASE_FILE = TEST_DB

    # Initialize the test database
    database.init_db()

    yield

    # Clean up
    database.DATABASE_FILE = original_db
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_init_db_creates_table():
    """Test that init_db creates the tasks table."""
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tasks'
    """)
    result = cursor.fetchone()

    assert result is not None
    assert result[0] == "tasks"

    conn.close()


def test_create_task():
    """Test creating a new task."""
    task = database.create_task("Test Task", "Test Description")

    assert task["id"] is not None
    assert task["title"] == "Test Task"
    assert task["description"] == "Test Description"
    assert task["completed"] == 0
    assert task["created_at"] is not None
    assert task["updated_at"] is not None


def test_create_task_without_description():
    """Test creating a task without description."""
    task = database.create_task("Test Task")

    assert task["title"] == "Test Task"
    assert task["description"] == ""


def test_get_all_tasks():
    """Test retrieving all tasks."""
    # Create some tasks
    database.create_task("Task 1", "Description 1")
    database.create_task("Task 2", "Description 2")

    tasks = database.get_all_tasks()

    assert len(tasks) == 2
    # Tasks should be ordered by created_at DESC (newest first)
    assert tasks[0]["title"] == "Task 2"
    assert tasks[1]["title"] == "Task 1"


def test_get_all_tasks_empty():
    """Test retrieving tasks when none exist."""
    tasks = database.get_all_tasks()
    assert len(tasks) == 0


def test_get_task_by_id():
    """Test retrieving a specific task by ID."""
    created_task = database.create_task("Test Task", "Test Description")
    task_id = created_task["id"]

    task = database.get_task_by_id(task_id)

    assert task is not None
    assert task["id"] == task_id
    assert task["title"] == "Test Task"


def test_get_task_by_id_not_found():
    """Test retrieving a non-existent task."""
    task = database.get_task_by_id(999)
    assert task is None


def test_update_task_title():
    """Test updating task title."""
    created_task = database.create_task("Original Title", "Description")
    task_id = created_task["id"]

    updated_task = database.update_task(task_id, title="Updated Title")

    assert updated_task is not None
    assert updated_task["title"] == "Updated Title"
    assert updated_task["description"] == "Description"


def test_update_task_description():
    """Test updating task description."""
    created_task = database.create_task("Title", "Original Description")
    task_id = created_task["id"]

    updated_task = database.update_task(task_id, description="Updated Description")

    assert updated_task is not None
    assert updated_task["description"] == "Updated Description"


def test_update_task_completed():
    """Test updating task completion status."""
    created_task = database.create_task("Test Task")
    task_id = created_task["id"]

    updated_task = database.update_task(task_id, completed=True)

    assert updated_task is not None
    assert updated_task["completed"] == 1


def test_update_task_multiple_fields():
    """Test updating multiple fields at once."""
    created_task = database.create_task("Original", "Original Desc")
    task_id = created_task["id"]

    updated_task = database.update_task(
        task_id, title="Updated", description="Updated Desc", completed=True
    )

    assert updated_task is not None
    assert updated_task["title"] == "Updated"
    assert updated_task["description"] == "Updated Desc"
    assert updated_task["completed"] == 1


def test_update_task_not_found():
    """Test updating a non-existent task."""
    result = database.update_task(999, title="New Title")
    assert result is None


def test_delete_task():
    """Test deleting a task."""
    created_task = database.create_task("Test Task")
    task_id = created_task["id"]

    deleted = database.delete_task(task_id)

    assert deleted is True

    # Verify task is gone
    task = database.get_task_by_id(task_id)
    assert task is None


def test_delete_task_not_found():
    """Test deleting a non-existent task."""
    deleted = database.delete_task(999)
    assert deleted is False

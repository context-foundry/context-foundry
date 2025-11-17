"""
Pytest configuration and shared fixtures for Glass Pane backend tests.

This module sets up the test environment before any imports happen,
ensuring tests use isolated temporary databases and don't pollute
production data.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path


# CRITICAL: Set environment variables BEFORE any app imports
# This ensures all modules respect the test database path
def pytest_configure(config):
    """
    Pytest hook called before test collection starts.

    This is the safest place to set environment variables because
    it runs before any test modules are imported.
    """
    # Create temporary test database
    temp_db = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db")
    temp_db_path = temp_db.name
    temp_db.close()

    # Store for cleanup
    config.test_db_path = temp_db_path

    # Set DB_PATH before any imports
    os.environ["DB_PATH"] = temp_db_path

    # Add backend directory to Python path for imports
    backend_dir = Path(__file__).parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def pytest_unconfigure(config):
    """
    Pytest hook called after all tests complete.

    Cleanup temporary test database.
    """
    if hasattr(config, "test_db_path"):
        try:
            os.unlink(config.test_db_path)
        except Exception:
            pass  # File may already be deleted


@pytest.fixture(scope="session")
def test_db_path(request):
    """Get the path to the temporary test database."""
    return request.config.test_db_path


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db(test_db_path):
    """
    Initialize test database schema before any tests run.

    This fixture runs automatically once per test session.
    """
    import sqlite3

    # Create database connection
    conn = sqlite3.connect(test_db_path)

    try:
        # Create chat tables schema
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model TEXT DEFAULT 'sonnet',
                plan_mode BOOLEAN DEFAULT 0,
                bypass_permissions BOOLEAN DEFAULT 0,
                title TEXT,
                message_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens_used INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
            );

            -- Create jobs table (needed by StoreService)
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL DEFAULT 'autonomous_build',
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                project_name TEXT,
                current_phase TEXT,
                tokens_used INTEGER DEFAULT 0,
                total_files INTEGER DEFAULT 0,
                params_json TEXT,
                error TEXT
            );
        """)
        conn.commit()

        # Verify database is initialized
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert "chat_sessions" in tables, "chat_sessions table not created"
        assert "chat_messages" in tables, "chat_messages table not created"
        assert "jobs" in tables, "jobs table not created"

    finally:
        conn.close()

    yield test_db_path


@pytest.fixture(scope="session")
def app(initialize_test_db):
    """
    Provide FastAPI app instance configured with test database.

    This fixture imports the app AFTER the test database is set up,
    ensuring all imports use the correct DB_PATH.
    """
    # Now safe to import app (DB_PATH already set in pytest_configure)
    from main import app
    from config import settings

    # Verify app is using test database
    assert str(settings.expanded_db_path) == str(
        initialize_test_db
    ), f"App not using test DB! Using: {settings.expanded_db_path}"

    return app


@pytest.fixture
def client(app):
    """
    Provide TestClient for API testing.

    Each test gets a fresh client instance but shares the same
    app and database for the test session.
    """
    from fastapi.testclient import TestClient

    return TestClient(app)

"""
Test to verify conftest.py properly sets up test environment.
"""

import os
from pathlib import Path


def test_environment_setup(test_db_path):
    """Verify test database path is set correctly."""
    # Check DB_PATH environment variable is set
    assert "DB_PATH" in os.environ, "DB_PATH not set in environment"

    # Check it points to a temp file
    db_path = os.environ["DB_PATH"]
    assert (
        "/tmp" in db_path or "temp" in db_path.lower()
    ), f"DB_PATH doesn't look like temp file: {db_path}"

    # Check test_db_path fixture works
    assert test_db_path is not None
    assert str(test_db_path) == db_path

    print(f"✓ Test DB path: {test_db_path}")


def test_settings_use_test_db(app, test_db_path):
    """Verify app settings use the test database."""
    from config import settings

    # Settings should use test database
    assert str(settings.expanded_db_path) == str(
        test_db_path
    ), f"Settings using wrong DB: {settings.expanded_db_path} != {test_db_path}"

    print(f"✓ Settings correctly using test DB: {settings.expanded_db_path}")


def test_database_tables_exist(test_db_path):
    """Verify test database has required tables."""
    import sqlite3

    conn = sqlite3.connect(test_db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    # Check required tables exist
    assert "chat_sessions" in tables, "chat_sessions table missing"
    assert "chat_messages" in tables, "chat_messages table missing"
    assert "jobs" in tables, "jobs table missing"

    print(f"✓ Test DB has required tables: {tables}")


def test_production_db_not_used():
    """Verify production database path is NOT being used."""
    from config import settings

    prod_db_path = Path.home() / ".context-foundry" / "cfd" / "jobs.db"

    # Settings should NOT point to production DB
    assert (
        settings.expanded_db_path != prod_db_path
    ), f"DANGER: Tests using production database at {prod_db_path}!"

    print(f"✓ Not using production DB: {prod_db_path}")

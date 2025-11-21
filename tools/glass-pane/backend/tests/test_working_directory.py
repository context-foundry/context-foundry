"""
Tests for working directory feature in chat sessions.

Verifies that:
- Sessions can be created with working_directory
- Working directory is stored and retrieved correctly
- Working directory can be updated via PATCH
- Path validation works (absolute paths, directory existence)
"""

import pytest
from pathlib import Path
from services.chat_service import ChatService


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_chat.db"
    service = ChatService(db_path, timeout=5.0)

    # Initialize tables
    conn = service._get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                model TEXT NOT NULL,
                plan_mode BOOLEAN NOT NULL,
                bypass_permissions BOOLEAN NOT NULL,
                title TEXT,
                message_count INTEGER NOT NULL DEFAULT 0,
                working_directory TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tokens_used INTEGER,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    finally:
        conn.close()

    return service


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    test_dir = tmp_path / "test_working_dir"
    test_dir.mkdir()
    return str(test_dir.absolute())


def test_create_session_with_working_directory(temp_db, temp_dir):
    """Test creating a session with a working directory."""
    session = temp_db.create_session(model="sonnet", working_directory=temp_dir)

    assert session.working_directory == temp_dir
    assert Path(session.working_directory).is_absolute()

    # Verify it's stored in database
    retrieved = temp_db.get_session(session.id)
    assert retrieved is not None
    assert retrieved.working_directory == temp_dir


def test_create_session_without_working_directory(temp_db):
    """Test creating a session without a working directory."""
    session = temp_db.create_session(model="sonnet")

    assert session.working_directory is None

    retrieved = temp_db.get_session(session.id)
    assert retrieved is not None
    assert retrieved.working_directory is None


def test_update_session_working_directory(temp_db, temp_dir):
    """Test updating an existing session's working directory."""
    # Create session without working directory
    session = temp_db.create_session(model="sonnet")
    assert session.working_directory is None

    # Update with working directory
    success = temp_db.update_session(session_id=session.id, working_directory=temp_dir)
    assert success

    # Verify update
    updated = temp_db.get_session(session.id)
    assert updated.working_directory == temp_dir


def test_working_directory_validation_nonexistent(temp_db):
    """Test that nonexistent directories are rejected."""
    with pytest.raises(ValueError, match="does not exist"):
        temp_db.create_session(
            model="sonnet", working_directory="/nonexistent/directory/path"
        )


def test_working_directory_validation_not_a_directory(temp_db, tmp_path):
    """Test that file paths are rejected (must be directories)."""
    # Create a file, not a directory
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test")

    with pytest.raises(ValueError, match="not a directory"):
        temp_db.create_session(model="sonnet", working_directory=str(test_file))


def test_working_directory_converted_to_absolute(temp_db, tmp_path):
    """Test that relative paths are converted to absolute."""
    import os

    # Create a subdirectory
    test_dir = tmp_path / "subdir"
    test_dir.mkdir()

    # Change to parent directory
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Create session with relative path
        session = temp_db.create_session(model="sonnet", working_directory="./subdir")

        # Should be converted to absolute path
        assert Path(session.working_directory).is_absolute()
        assert session.working_directory == str(test_dir.absolute())
    finally:
        os.chdir(original_dir)


def test_multiple_sessions_different_directories(temp_db, tmp_path):
    """Test that different sessions can have different working directories."""
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    session1 = temp_db.create_session(model="sonnet", working_directory=str(dir1))

    session2 = temp_db.create_session(model="haiku", working_directory=str(dir2))

    assert session1.working_directory == str(dir1.absolute())
    assert session2.working_directory == str(dir2.absolute())
    assert session1.working_directory != session2.working_directory


def test_clear_working_directory(temp_db, temp_dir):
    """Test clearing a working directory by passing empty string."""
    # Create session with working directory
    session = temp_db.create_session(model="sonnet", working_directory=temp_dir)
    assert session.working_directory == temp_dir

    # Clear it by passing empty string
    success = temp_db.update_session(session_id=session.id, working_directory="")
    assert success

    # Verify it's cleared
    updated = temp_db.get_session(session.id)
    assert updated.working_directory is None

"""
Database layer for task manager application.
Handles SQLite connection management and CRUD operations.
"""

import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Dict, Any


DATABASE_FILE = "backend/tasks.db"


@contextmanager
def get_db_connection():
    """Context manager for database connections with automatic cleanup."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database with tasks table and indexes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                completed BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for common query patterns
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_completed ON tasks(completed)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON tasks(created_at DESC)
        """)


def get_all_tasks() -> List[Dict[str, Any]]:
    """Retrieve all tasks from database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, completed, created_at, updated_at
            FROM tasks
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def create_task(title: str, description: str = "") -> Dict[str, Any]:
    """
    Insert new task into database.

    Args:
        title: Task title (required)
        description: Task description (optional, defaults to empty string)

    Returns:
        Dictionary containing the created task with all fields
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (title, description, completed)
            VALUES (?, ?, 0)
        """,
            (title, description),
        )

        task_id = cursor.lastrowid

        # Fetch the created task to return complete data
        cursor.execute(
            """
            SELECT id, title, description, completed, created_at, updated_at
            FROM tasks
            WHERE id = ?
        """,
            (task_id,),
        )

        row = cursor.fetchone()
        return dict(row)


def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    completed: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update existing task in database.

    Args:
        task_id: ID of task to update
        title: New title (optional)
        description: New description (optional)
        completed: New completion status (optional)

    Returns:
        Updated task dictionary or None if task not found
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        params = []

        if title is not None:
            update_fields.append("title = ?")
            params.append(title)

        if description is not None:
            update_fields.append("description = ?")
            params.append(description)

        if completed is not None:
            update_fields.append("completed = ?")
            params.append(1 if completed else 0)

        # Always update the updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        if not update_fields:
            # No fields to update, just return current task
            return get_task_by_id(task_id)

        params.append(task_id)

        query = f"""
            UPDATE tasks
            SET {', '.join(update_fields)}
            WHERE id = ?
        """

        cursor.execute(query, params)

        if cursor.rowcount == 0:
            return None

        # Fetch and return updated task
        cursor.execute(
            """
            SELECT id, title, description, completed, created_at, updated_at
            FROM tasks
            WHERE id = ?
        """,
            (task_id,),
        )

        row = cursor.fetchone()
        return dict(row) if row else None


def delete_task(task_id: int) -> bool:
    """
    Delete task from database.

    Args:
        task_id: ID of task to delete

    Returns:
        True if task was deleted, False if task not found
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0


def get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve single task by ID.

    Args:
        task_id: ID of task to retrieve

    Returns:
        Task dictionary or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, completed, created_at, updated_at
            FROM tasks
            WHERE id = ?
        """,
            (task_id,),
        )

        row = cursor.fetchone()
        return dict(row) if row else None

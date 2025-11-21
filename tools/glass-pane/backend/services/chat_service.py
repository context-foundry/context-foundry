"""
Chat Service

Manages chat sessions and messages in SQLite database.
Provides CRUD operations for the Forge chat interface.
"""

import logging
import sqlite3
import uuid
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    """Represents a chat session."""

    id: str
    created_at: str
    last_activity: str
    model: str
    plan_mode: bool
    bypass_permissions: bool
    title: Optional[str]
    message_count: int
    working_directory: Optional[str] = None


@dataclass
class ChatMessage:
    """Represents a chat message."""

    id: int
    session_id: str
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    timestamp: str
    tokens_used: Optional[int] = None


class ChatService:
    """
    Service for managing chat sessions and messages.

    Provides database operations for the Forge chat interface,
    including session management and message history.
    """

    def __init__(self, db_path: Path, timeout: float = 5.0):
        """
        Initialize Chat service.

        Args:
            db_path: Path to Context Foundry jobs.db
            timeout: Query timeout in seconds
        """
        self.db_path = db_path
        self.timeout = timeout
        self._validate_db()

    def _validate_db(self):
        """Validate database exists and has chat tables."""
        if not self.db_path.exists():
            logger.warning(f"Database not found at {self.db_path}")
        else:
            logger.info(f"Connected to chat database: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new database connection with WAL mode."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrent reads
        conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ========== Session Operations ==========

    def create_session(
        self,
        model: str = "sonnet",
        plan_mode: bool = False,
        bypass_permissions: bool = False,
        title: Optional[str] = None,
        working_directory: Optional[str] = None,
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            model: Claude model to use (sonnet/opus/haiku)
            plan_mode: Enable plan mode
            bypass_permissions: Bypass permission checks
            title: Optional session title
            working_directory: Optional working directory for CLI execution

        Returns:
            Created ChatSession
        """
        # Validate working directory if provided
        if working_directory:
            working_dir_path = Path(working_directory)
            if not working_dir_path.exists():
                raise ValueError(
                    f"Working directory does not exist: {working_directory}"
                )
            if not working_dir_path.is_dir():
                raise ValueError(
                    f"Working directory is not a directory: {working_directory}"
                )
            # Convert to absolute path
            working_directory = str(working_dir_path.absolute())

        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO chat_sessions
                (id, created_at, last_activity, model, plan_mode, bypass_permissions, title, message_count, working_directory)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    session_id,
                    now,
                    now,
                    model,
                    plan_mode,
                    bypass_permissions,
                    title,
                    working_directory,
                ),
            )
            conn.commit()

            return ChatSession(
                id=session_id,
                created_at=now,
                last_activity=now,
                model=model,
                plan_mode=plan_mode,
                bypass_permissions=bypass_permissions,
                title=title,
                message_count=0,
                working_directory=working_directory,
            )
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get a chat session by ID.

        Args:
            session_id: Session UUID

        Returns:
            ChatSession or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return ChatSession(
                id=row["id"],
                created_at=row["created_at"],
                last_activity=row["last_activity"],
                model=row["model"],
                plan_mode=bool(row["plan_mode"]),
                bypass_permissions=bool(row["bypass_permissions"]),
                title=row["title"],
                message_count=row["message_count"],
                working_directory=row["working_directory"],
            )
        finally:
            conn.close()

    def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> Tuple[List[ChatSession], int]:
        """
        List all chat sessions, ordered by recent activity.

        Args:
            limit: Maximum sessions to return
            offset: Pagination offset

        Returns:
            Tuple of (sessions list, total count)
        """
        conn = self._get_connection()
        try:
            # Get sessions
            cursor = conn.execute(
                """
                SELECT * FROM chat_sessions
                ORDER BY last_activity DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()

            sessions = [
                ChatSession(
                    id=row["id"],
                    created_at=row["created_at"],
                    last_activity=row["last_activity"],
                    model=row["model"],
                    plan_mode=bool(row["plan_mode"]),
                    bypass_permissions=bool(row["bypass_permissions"]),
                    title=row["title"],
                    message_count=row["message_count"],
                    working_directory=row["working_directory"],
                )
                for row in rows
            ]

            # Get total count
            total = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]

            return sessions, total
        finally:
            conn.close()

    def update_session(
        self,
        session_id: str,
        model: Optional[str] = None,
        plan_mode: Optional[bool] = None,
        bypass_permissions: Optional[bool] = None,
        title: Optional[str] = None,
        working_directory: Optional[str] = None,
    ) -> bool:
        """
        Update session settings.

        Args:
            session_id: Session UUID
            model: New model selection
            plan_mode: New plan mode setting
            bypass_permissions: New permissions setting
            title: New title
            working_directory: New working directory (empty string to clear)

        Returns:
            True if updated, False if session not found
        """
        # Handle working directory with special cases:
        # - None: no change (parameter not provided by API)
        # - Empty string: clear the directory (set to NULL)
        # - Non-empty string: validate and set
        update_working_directory = False
        if working_directory is not None:
            if working_directory == "":
                # Explicitly clear the working directory
                working_directory = None
                update_working_directory = True
            else:
                # Validate non-empty directory
                working_dir_path = Path(working_directory)
                if not working_dir_path.exists():
                    raise ValueError(
                        f"Working directory does not exist: {working_directory}"
                    )
                if not working_dir_path.is_dir():
                    raise ValueError(
                        f"Working directory is not a directory: {working_directory}"
                    )
                # Convert to absolute path
                working_directory = str(working_dir_path.absolute())
                update_working_directory = True

        updates = []
        params = []

        if model is not None:
            updates.append("model = ?")
            params.append(model)

        if plan_mode is not None:
            updates.append("plan_mode = ?")
            params.append(plan_mode)

        if bypass_permissions is not None:
            updates.append("bypass_permissions = ?")
            params.append(bypass_permissions)

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if update_working_directory:
            updates.append("working_directory = ?")
            params.append(working_directory)

        if not updates:
            return False

        # Always update last_activity
        updates.append("last_activity = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(session_id)

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                f"UPDATE chat_sessions SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session and all its messages.

        Args:
            session_id: Session UUID

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ========== Message Operations ==========

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens_used: Optional[int] = None,
    ) -> ChatMessage:
        """
        Add a message to a session.

        Args:
            session_id: Session UUID
            role: Message role (user/assistant/system)
            content: Message content
            tokens_used: Optional token count

        Returns:
            Created ChatMessage
        """
        now = datetime.utcnow().isoformat()

        conn = self._get_connection()
        try:
            # Insert message
            cursor = conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, timestamp, tokens_used)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, now, tokens_used),
            )
            message_id = cursor.lastrowid

            # Update session's last_activity and message_count
            conn.execute(
                """
                UPDATE chat_sessions
                SET last_activity = ?, message_count = message_count + 1
                WHERE id = ?
                """,
                (now, session_id),
            )

            conn.commit()

            return ChatMessage(
                id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                timestamp=now,
                tokens_used=tokens_used,
            )
        finally:
            conn.close()

    def get_session_messages(
        self, session_id: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[ChatMessage]:
        """
        Get all messages for a session.

        Args:
            session_id: Session UUID
            limit: Maximum messages to return (None = all)
            offset: Pagination offset

        Returns:
            List of ChatMessage objects ordered by timestamp
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """
            params = [session_id]

            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                ChatMessage(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    tokens_used=row["tokens_used"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def clear_session_messages(self, session_id: str) -> int:
        """
        Clear all messages from a session.

        Args:
            session_id: Session UUID

        Returns:
            Number of messages deleted
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM chat_messages WHERE session_id = ?", (session_id,)
            )
            deleted_count = cursor.rowcount

            # Reset message count
            conn.execute(
                "UPDATE chat_sessions SET message_count = 0 WHERE id = ?", (session_id,)
            )

            conn.commit()
            return deleted_count
        finally:
            conn.close()

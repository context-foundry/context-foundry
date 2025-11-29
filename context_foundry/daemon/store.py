"""
Persistence layer for Context Foundry Daemon

SQLite-based storage for jobs, phase events, and logs.
Uses WAL mode for better concurrency.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from datetime import datetime

from .models import Job, JobStatus, JobType, Task, TaskStatus, PhaseEvent, LogEntry


class Store:
    """
    SQLite-based persistence for CF Daemon

    Manages storage for:
    - Jobs (lifecycle, status, results)
    - Phase events (Scout → Architect → Builder → Test → Deploy)
    - Log entries (structured logs per job)
    """

    def __init__(self, db_path: Path):
        """
        Initialize store

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Cached connection for read-only operations (like get_stats)
        # This avoids creating a new connection for frequent read operations
        self._read_conn = None
        self._read_conn_lock = None  # Lazy init to avoid import issues

        # Initialize database
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper settings

        Uses explicit timeout to prevent indefinite hangs on lock contention.
        Default sqlite3 timeout is 5s, but we use 10s for better resilience.
        """
        # timeout=10.0 prevents indefinite blocking on locked database
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,  # 10 second timeout for lock contention
        )
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        # Set busy_timeout to handle concurrent access more gracefully
        # This is in milliseconds - 10000ms = 10 seconds
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_read_connection(self):
        """Get a cached read-only connection for frequent read operations.

        This avoids the overhead of creating new connections for operations
        like get_stats() that are called every minute. The connection is
        thread-safe via a lock.

        Returns:
            A sqlite3 connection configured for reads
        """
        if self._read_conn_lock is None:
            self._read_conn_lock = threading.Lock()

        with self._read_conn_lock:
            if self._read_conn is None:
                logger = logging.getLogger(__name__)
                logger.info("[DB] Creating cached read connection")
                self._read_conn = sqlite3.connect(
                    str(self.db_path), check_same_thread=False, timeout=10.0
                )
                self._read_conn.row_factory = sqlite3.Row
                self._read_conn.execute("PRAGMA busy_timeout = 10000")
                # Use query_only mode for read connection
                self._read_conn.execute("PRAGMA query_only = ON")
            return self._read_conn

    def close(self):
        """Close any cached connections."""
        if self._read_conn is not None:
            try:
                self._read_conn.close()
            except Exception:
                pass
            self._read_conn = None

    def _init_db(self):
        """Initialize database schema with tables and indexes"""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            # Increase autocheckpoint threshold to reduce checkpoint frequency
            # Default is 1000 pages, we use 2000 to reduce blocking
            conn.execute("PRAGMA wal_autocheckpoint = 2000")

            # Jobs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    params_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result_json TEXT,
                    error TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
            """)

            # Tasks table (first-class phase/task representation)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    last_heartbeat TEXT,
                    error TEXT,
                    result_json TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    parent_task_id TEXT,
                    sequence INTEGER NOT NULL DEFAULT 0,
                    timeout_seconds INTEGER,
                    tokens_used INTEGER,
                    context_percent REAL,
                    FOREIGN KEY (job_id) REFERENCES jobs(id),
                    FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
                )
            """)

            # Phase events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS phase_events (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    duration_seconds REAL,
                    tokens_used INTEGER,
                    context_percent REAL,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)

            # Logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    phase TEXT,
                    source TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)

            # Indexes for performance
            self._create_indexes(conn)

    def _create_indexes(self, conn):
        """Create indexes for common queries"""
        # Job indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs(status, priority DESC)"
        )

        # Task indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_job_id ON tasks(job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_job_status ON tasks(job_id, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_last_heartbeat ON tasks(last_heartbeat)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id)"
        )

        # Phase event indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_phase_events_job_id ON phase_events(job_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_phase_events_timestamp ON phase_events(timestamp)"
        )

        # Log indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_job_id ON logs(job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")

    # ===== Job CRUD Operations =====

    def save_job(self, job: Job) -> None:
        """
        Save or update a job

        Args:
            job: Job instance to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    id, type, status, priority, params_json,
                    created_at, started_at, completed_at,
                    result_json, error, retry_count, max_retries, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    job.id,
                    job.type.value,
                    job.status.value,
                    job.priority,
                    json.dumps(job.params),
                    job.created_at.isoformat(),
                    job.started_at.isoformat() if job.started_at else None,
                    job.completed_at.isoformat() if job.completed_at else None,
                    json.dumps(job.result) if job.result else None,
                    job.error,
                    job.retry_count,
                    job.max_retries,
                    json.dumps(job.metadata),
                ),
            )

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve a job by ID

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job instance or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_job(dict(row))

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        """
        List jobs with optional filters

        Args:
            status: Filter by job status
            job_type: Filter by job type
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of Job instances
        """
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if job_type:
            query += " AND type = ?"
            params.append(job_type.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_job(dict(row)) for row in rows]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update job status and related fields

        Args:
            job_id: Job ID to update
            status: New job status
            started_at: Start timestamp (for RUNNING status)
            completed_at: Completion timestamp (for terminal statuses)
            result: Job result data (for SUCCEEDED status)
            error: Error message (for FAILED status)
            metadata: Job metadata to merge with existing (new keys added, existing keys updated).
                     Performs in-store read-merge-write to preserve existing metadata fields.
        """
        updates = ["status = ?"]
        params = [status.value]

        if started_at:
            updates.append("started_at = ?")
            params.append(started_at.isoformat())

        if completed_at:
            updates.append("completed_at = ?")
            params.append(completed_at.isoformat())

        if result is not None:
            updates.append("result_json = ?")
            params.append(json.dumps(result))

        if error is not None:
            updates.append("error = ?")
            params.append(error)

        params.append(job_id)

        with self._get_connection() as conn:
            # If metadata provided, read existing and merge (new keys added, existing updated)
            if metadata is not None:
                cursor = conn.execute(
                    "SELECT metadata_json FROM jobs WHERE id = ?", (job_id,)
                )
                row = cursor.fetchone()
                existing_metadata = {}
                if row and row[0]:
                    try:
                        existing_metadata = json.loads(row[0])
                    except json.JSONDecodeError:
                        pass
                # Merge: existing keys preserved unless overwritten by new metadata
                merged = {**existing_metadata, **metadata}
                updates.append("metadata_json = ?")
                params.insert(-1, json.dumps(merged))  # Insert before job_id

            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", params)

    def increment_retry_count(self, job_id: str) -> int:
        """
        Increment job retry count

        Args:
            job_id: Job ID to update

        Returns:
            New retry count
        """
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET retry_count = retry_count + 1 WHERE id = ?", (job_id,)
            )

            cursor = conn.execute(
                "SELECT retry_count FROM jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            return row["retry_count"] if row else 0

    def _row_to_job(self, row: Dict[str, Any]) -> Job:
        """Convert database row to Job instance"""
        return Job(
            id=row["id"],
            type=JobType(row["type"]),
            status=JobStatus(row["status"]),
            priority=row["priority"],
            params=json.loads(row["params_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"])
            if row["started_at"]
            else None,
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            metadata=json.loads(row["metadata_json"]),
        )

    # ===== Task CRUD Operations =====

    def save_task(self, task: Task) -> None:
        """
        Save or update a task

        Args:
            task: Task instance to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, job_id, name, status, created_at, started_at, completed_at,
                    last_heartbeat, error, result_json, metadata_json, parent_task_id,
                    sequence, timeout_seconds, tokens_used, context_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task.id,
                    task.job_id,
                    task.name,
                    task.status.value,
                    task.created_at.isoformat(),
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.last_heartbeat.isoformat() if task.last_heartbeat else None,
                    task.error,
                    json.dumps(task.result) if task.result else None,
                    json.dumps(task.metadata),
                    task.parent_task_id,
                    task.sequence,
                    task.timeout_seconds,
                    task.tokens_used,
                    task.context_percent,
                ),
            )

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieve a task by ID

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task instance or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_task(dict(row))

    def get_tasks_for_job(
        self,
        job_id: str,
        status: Optional[TaskStatus] = None,
    ) -> List[Task]:
        """
        Get all tasks for a job

        Args:
            job_id: Job ID to get tasks for
            status: Optional status filter

        Returns:
            List of Task instances ordered by sequence
        """
        query = "SELECT * FROM tasks WHERE job_id = ?"
        params = [job_id]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY sequence ASC"

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_task(dict(row)) for row in rows]

    def get_task_by_name(self, job_id: str, name: str) -> Optional[Task]:
        """
        Get a task by job_id and name (phase)

        Args:
            job_id: Job ID
            name: Task name (e.g., "Scout", "Architect")

        Returns:
            Task instance or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE job_id = ? AND name = ?",
                (job_id, name),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(dict(row))

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update task status and related fields

        Args:
            task_id: Task ID to update
            status: New task status
            started_at: Start timestamp
            completed_at: Completion timestamp
            error: Error message
            result: Task result data

        Returns:
            True if task was updated, False if not found
        """
        updates = ["status = ?"]
        params = [status.value]

        if started_at:
            updates.append("started_at = ?")
            params.append(started_at.isoformat())

        if completed_at:
            updates.append("completed_at = ?")
            params.append(completed_at.isoformat())

        if error is not None:
            updates.append("error = ?")
            params.append(error)

        if result is not None:
            updates.append("result_json = ?")
            params.append(json.dumps(result))

        params.append(task_id)

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            return cursor.rowcount > 0

    def update_task_heartbeat(self, task_id: str) -> bool:
        """
        Update task heartbeat timestamp

        Args:
            task_id: Task ID to update

        Returns:
            True if task was updated, False if not found
        """
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET last_heartbeat = ? WHERE id = ?",
                (now, task_id),
            )
            return cursor.rowcount > 0

    def get_stale_tasks(self, heartbeat_timeout_seconds: float = 300) -> List[Task]:
        """
        Get tasks that appear stale (no recent heartbeat)

        Args:
            heartbeat_timeout_seconds: Time without heartbeat to consider stale

        Returns:
            List of stale Task instances
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(seconds=heartbeat_timeout_seconds)
        cutoff_iso = cutoff.isoformat()

        with self._get_connection() as conn:
            # Tasks in active states with stale heartbeat
            cursor = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('running', 'waiting_approval')
                AND (
                    (last_heartbeat IS NOT NULL AND last_heartbeat < ?)
                    OR (last_heartbeat IS NULL AND started_at IS NOT NULL AND started_at < ?)
                )
            """,
                (cutoff_iso, cutoff_iso),
            )
            rows = cursor.fetchall()
            return [self._row_to_task(dict(row)) for row in rows]

    def delete_tasks_for_job(self, job_id: str) -> int:
        """
        Delete all tasks for a job

        Args:
            job_id: Job ID to delete tasks for

        Returns:
            Number of tasks deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
            return cursor.rowcount

    def _row_to_task(self, row: Dict[str, Any]) -> Task:
        """Convert database row to Task instance"""
        return Task(
            id=row["id"],
            job_id=row["job_id"],
            name=row["name"],
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"])
            if row["started_at"]
            else None,
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
            last_heartbeat=datetime.fromisoformat(row["last_heartbeat"])
            if row["last_heartbeat"]
            else None,
            error=row["error"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            metadata=json.loads(row["metadata_json"]),
            parent_task_id=row["parent_task_id"],
            sequence=row["sequence"],
            timeout_seconds=row["timeout_seconds"],
            tokens_used=row["tokens_used"],
            context_percent=row["context_percent"],
        )

    # ===== Phase Event Operations =====

    def save_phase_event(self, event: PhaseEvent) -> None:
        """
        Save a phase event

        Args:
            event: PhaseEvent instance to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO phase_events (
                    id, job_id, phase, status, timestamp,
                    details_json, duration_seconds, tokens_used, context_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.id,
                    event.job_id,
                    event.phase,
                    event.status,
                    event.timestamp.isoformat(),
                    json.dumps(event.details),
                    event.duration_seconds,
                    event.tokens_used,
                    event.context_percent,
                ),
            )

    def get_phase_events(
        self,
        job_id: str,
        phase: Optional[str] = None,
    ) -> List[PhaseEvent]:
        """
        Get phase events for a job

        Args:
            job_id: Job ID to get events for
            phase: Optional phase filter

        Returns:
            List of PhaseEvent instances
        """
        query = "SELECT * FROM phase_events WHERE job_id = ?"
        params = [job_id]

        if phase:
            query += " AND phase = ?"
            params.append(phase)

        query += " ORDER BY timestamp ASC"

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_phase_event(dict(row)) for row in rows]

    def _row_to_phase_event(self, row: Dict[str, Any]) -> PhaseEvent:
        """Convert database row to PhaseEvent instance"""
        return PhaseEvent(
            id=row["id"],
            job_id=row["job_id"],
            phase=row["phase"],
            status=row["status"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            details=json.loads(row["details_json"]),
            duration_seconds=row["duration_seconds"],
            tokens_used=row["tokens_used"],
            context_percent=row["context_percent"],
        )

    # ===== Timeline & Replay Helpers =====

    def get_job_timeline(
        self,
        job_id: str,
        include_heartbeats: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get complete timeline of events for a job.

        Returns a unified timeline combining job events, task events, phase events,
        and optionally heartbeats, sorted by timestamp.

        Args:
            job_id: Job ID to get timeline for
            include_heartbeats: Whether to include heartbeat events
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries with unified format
        """
        events = []

        with self._get_connection() as conn:
            # 1. Get job lifecycle events (created, started, completed)
            job_cursor = conn.execute(
                "SELECT id, status, created_at, started_at, completed_at FROM jobs WHERE id = ?",
                [job_id],
            )
            job_row = job_cursor.fetchone()
            if job_row:
                # Job created event
                if job_row["created_at"]:
                    events.append(
                        {
                            "id": f"{job_id}_created",
                            "timestamp": job_row["created_at"],
                            "type": "job_event",
                            "event_type": "job_created",
                            "status": "created",
                            "phase": None,
                            "details": {},
                        }
                    )
                # Job started event
                if job_row["started_at"]:
                    events.append(
                        {
                            "id": f"{job_id}_started",
                            "timestamp": job_row["started_at"],
                            "type": "job_event",
                            "event_type": "job_started",
                            "status": "started",
                            "phase": None,
                            "details": {},
                        }
                    )
                # Job completed event
                if job_row["completed_at"]:
                    final_status = job_row["status"]  # succeeded, failed, etc.
                    events.append(
                        {
                            "id": f"{job_id}_completed",
                            "timestamp": job_row["completed_at"],
                            "type": "job_event",
                            "event_type": f"job_{final_status}",
                            "status": final_status,
                            "phase": None,
                            "details": {},
                        }
                    )

            # 2. Get task lifecycle events (created, started, completed)
            task_cursor = conn.execute(
                "SELECT id, name, status, created_at, started_at, completed_at FROM tasks WHERE job_id = ?",
                [job_id],
            )
            for task_row in task_cursor.fetchall():
                task_id = task_row["id"]
                task_name = task_row["name"]
                # Task created event
                if task_row["created_at"]:
                    events.append(
                        {
                            "id": f"{task_id}_created",
                            "timestamp": task_row["created_at"],
                            "type": "task_event",
                            "event_type": "task_created",
                            "status": "created",
                            "phase": task_name,
                            "details": {"task_id": task_id},
                        }
                    )
                # Task started event
                if task_row["started_at"]:
                    events.append(
                        {
                            "id": f"{task_id}_started",
                            "timestamp": task_row["started_at"],
                            "type": "task_event",
                            "event_type": "task_started",
                            "status": "started",
                            "phase": task_name,
                            "details": {"task_id": task_id},
                        }
                    )
                # Task completed event
                if task_row["completed_at"]:
                    final_status = task_row["status"]  # succeeded, failed, etc.
                    events.append(
                        {
                            "id": f"{task_id}_completed",
                            "timestamp": task_row["completed_at"],
                            "type": "task_event",
                            "event_type": f"task_{final_status}",
                            "status": final_status,
                            "phase": task_name,
                            "details": {"task_id": task_id},
                        }
                    )

            # 3. Get phase events
            query = "SELECT * FROM phase_events WHERE job_id = ?"
            params = [job_id]

            if not include_heartbeats:
                query += " AND status != 'heartbeat'"

            query += " ORDER BY timestamp ASC"

            cursor = conn.execute(query, params)
            for row in cursor.fetchall():
                # Create event_type from phase + status (e.g., "phase_started")
                event_type = f"phase_{row['status']}"
                event = {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "type": "phase_event",
                    "event_type": event_type,
                    "phase": row["phase"],
                    "status": row["status"],
                    "details": json.loads(row["details_json"])
                    if row["details_json"]
                    else {},
                    "duration_seconds": row["duration_seconds"],
                    "tokens_used": row["tokens_used"],
                }
                events.append(event)

        # Sort all events by timestamp
        events.sort(key=lambda e: e["timestamp"])

        # Apply limit after sorting - return MOST RECENT events (last N)
        if limit and len(events) > limit:
            events = events[-limit:]  # Take last N to get most recent

        return events

    def get_job_phase_summary(self, job_id: str) -> Dict[str, Any]:
        """
        Get a summary of phase progress for a job.

        Returns a structured summary showing each phase's status,
        duration, and key metrics.

        Args:
            job_id: Job ID

        Returns:
            Dictionary with phase progress summary
        """
        # Get job info
        job = self.get_job(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        # Get tasks
        tasks = self.get_tasks_for_job(job_id)

        # Build phase summary
        phases = {}
        for task in tasks:
            duration = None
            if task.started_at and task.completed_at:
                duration = (task.completed_at - task.started_at).total_seconds()

            phases[task.name] = {
                "status": task.status.value,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat()
                if task.completed_at
                else None,
                "duration_seconds": duration,
                "tokens_used": task.tokens_used,
                "error": task.error,
                "last_heartbeat": task.last_heartbeat.isoformat()
                if task.last_heartbeat
                else None,
            }

        # Calculate overall progress
        total_phases = len(phases)
        completed = sum(1 for p in phases.values() if p["status"] == "succeeded")
        failed = sum(
            1 for p in phases.values() if p["status"] in ("failed", "timed_out")
        )
        running = sum(1 for p in phases.values() if p["status"] == "running")

        return {
            "job_id": job_id,
            "job_status": job.status.value,
            "job_started_at": job.started_at.isoformat() if job.started_at else None,
            "job_completed_at": job.completed_at.isoformat()
            if job.completed_at
            else None,
            "phases": phases,
            "progress": {
                "total": total_phases,
                "completed": completed,
                "failed": failed,
                "running": running,
                "pending": total_phases - completed - failed - running,
            },
        }

    def get_recent_events(
        self,
        limit: int = 50,
        event_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent events across all jobs.

        Includes job lifecycle events, task lifecycle events, and phase events
        for a unified view of system activity.

        Useful for monitoring/debugging recent activity.

        Args:
            limit: Maximum number of events
            event_types: Filter by event type (e.g., ["task_failed", "job_succeeded"])

        Returns:
            List of recent events with job context
        """
        events = []

        with self._get_connection() as conn:
            # 1. Get recent job lifecycle events
            job_cursor = conn.execute(
                """SELECT j.id, j.status, j.created_at, j.started_at, j.completed_at, j.params_json
                   FROM jobs j
                   ORDER BY j.created_at DESC
                   LIMIT ?""",
                [limit * 2],  # Get more jobs to ensure we have enough events
            )
            for job_row in job_cursor.fetchall():
                job_id = job_row["id"]
                job_params = (
                    json.loads(job_row["params_json"]) if job_row["params_json"] else {}
                )
                job_task = job_params.get("task", "")[:50]

                # Job created event
                if job_row["created_at"]:
                    events.append(
                        {
                            "id": f"{job_id}_created",
                            "timestamp": job_row["created_at"],
                            "job_id": job_id,
                            "job_task": job_task,
                            "type": "job_event",
                            "event_type": "job_created",
                            "phase": None,
                            "status": "created",
                            "details": {},
                        }
                    )
                # Job started event
                if job_row["started_at"]:
                    events.append(
                        {
                            "id": f"{job_id}_started",
                            "timestamp": job_row["started_at"],
                            "job_id": job_id,
                            "job_task": job_task,
                            "type": "job_event",
                            "event_type": "job_started",
                            "phase": None,
                            "status": "started",
                            "details": {},
                        }
                    )
                # Job completed event
                if job_row["completed_at"]:
                    final_status = job_row["status"]
                    events.append(
                        {
                            "id": f"{job_id}_completed",
                            "timestamp": job_row["completed_at"],
                            "job_id": job_id,
                            "job_task": job_task,
                            "type": "job_event",
                            "event_type": f"job_{final_status}",
                            "phase": None,
                            "status": final_status,
                            "details": {},
                        }
                    )

            # 2. Get recent task lifecycle events
            task_cursor = conn.execute(
                """SELECT t.id, t.job_id, t.name, t.status, t.created_at, t.started_at, t.completed_at,
                          j.params_json
                   FROM tasks t
                   JOIN jobs j ON t.job_id = j.id
                   ORDER BY t.created_at DESC
                   LIMIT ?""",
                [limit * 2],
            )
            for task_row in task_cursor.fetchall():
                task_id = task_row["id"]
                job_id = task_row["job_id"]
                task_name = task_row["name"]
                job_params = (
                    json.loads(task_row["params_json"])
                    if task_row["params_json"]
                    else {}
                )
                job_task = job_params.get("task", "")[:50]

                # Task created event
                if task_row["created_at"]:
                    events.append(
                        {
                            "id": f"{task_id}_created",
                            "timestamp": task_row["created_at"],
                            "job_id": job_id,
                            "job_task": job_task,
                            "type": "task_event",
                            "event_type": "task_created",
                            "phase": task_name,
                            "status": "created",
                            "details": {"task_id": task_id},
                        }
                    )
                # Task started event
                if task_row["started_at"]:
                    events.append(
                        {
                            "id": f"{task_id}_started",
                            "timestamp": task_row["started_at"],
                            "job_id": job_id,
                            "job_task": job_task,
                            "type": "task_event",
                            "event_type": "task_started",
                            "phase": task_name,
                            "status": "started",
                            "details": {"task_id": task_id},
                        }
                    )
                # Task completed event
                if task_row["completed_at"]:
                    final_status = task_row["status"]
                    events.append(
                        {
                            "id": f"{task_id}_completed",
                            "timestamp": task_row["completed_at"],
                            "job_id": job_id,
                            "job_task": job_task,
                            "type": "task_event",
                            "event_type": f"task_{final_status}",
                            "phase": task_name,
                            "status": final_status,
                            "details": {"task_id": task_id},
                        }
                    )

            # 3. Get phase events
            query = """
                SELECT pe.*, j.params_json
                FROM phase_events pe
                JOIN jobs j ON pe.job_id = j.id
                WHERE pe.status != 'heartbeat'
            """
            params = []

            if event_types:
                placeholders = ",".join("?" * len(event_types))
                query += f" AND pe.status IN ({placeholders})"
                params = list(event_types)

            query += f" ORDER BY pe.timestamp DESC LIMIT {limit * 2}"

            cursor = conn.execute(query, params)
            for row in cursor.fetchall():
                job_params = (
                    json.loads(row["params_json"]) if row["params_json"] else {}
                )
                events.append(
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "job_id": row["job_id"],
                        "job_task": job_params.get("task", "")[:50],
                        "type": "phase_event",
                        "event_type": f"phase_{row['status']}",
                        "phase": row["phase"],
                        "status": row["status"],
                        "details": json.loads(row["details_json"])
                        if row["details_json"]
                        else {},
                    }
                )

        # Filter by event_types if specified (applies to all event types now)
        if event_types:
            events = [
                e
                for e in events
                if e.get("status") in event_types or e.get("event_type") in event_types
            ]

        # Sort by timestamp descending (most recent first)
        events.sort(key=lambda e: e["timestamp"], reverse=True)

        # Apply limit
        return events[:limit]

    def reconstruct_job_state(self, job_id: str) -> Dict[str, Any]:
        """
        Reconstruct job state from events (event sourcing lite).

        This allows understanding how a job reached its current state
        by replaying key events.

        Args:
            job_id: Job ID

        Returns:
            Reconstructed state with event history
        """
        # Get job
        job = self.get_job(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        # Get all events (excluding heartbeats)
        events = self.get_job_timeline(job_id, include_heartbeats=False)

        # Reconstruct state changes
        state_changes = []
        task_states = {}

        for event in events:
            status = event.get("status", "")

            # Track job status changes
            if status.startswith("job_"):
                state_changes.append(
                    {
                        "timestamp": event["timestamp"],
                        "type": "job_status",
                        "from": event.get("details", {}).get("from_status"),
                        "to": event.get("details", {}).get("to_status"),
                        "reason": event.get("details", {}).get("reason"),
                    }
                )

            # Track task status changes
            elif status.startswith("task_"):
                phase = event.get("phase")
                if phase:
                    task_states[phase] = {
                        "status": status.replace("task_", ""),
                        "timestamp": event["timestamp"],
                    }
                    state_changes.append(
                        {
                            "timestamp": event["timestamp"],
                            "type": "task_status",
                            "phase": phase,
                            "from": event.get("details", {}).get("from_status"),
                            "to": event.get("details", {}).get("to_status"),
                        }
                    )

            # Track gate events
            elif status.startswith("gate_"):
                state_changes.append(
                    {
                        "timestamp": event["timestamp"],
                        "type": "gate",
                        "phase": event.get("phase"),
                        "status": status,
                    }
                )

        return {
            "job_id": job_id,
            "current_status": job.status.value,
            "task_states": task_states,
            "state_changes": state_changes,
            "total_events": len(events),
        }

    # ===== Log Operations =====

    def save_log(self, log_entry: LogEntry) -> None:
        """
        Save a log entry

        Args:
            log_entry: LogEntry instance to save
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO logs (
                    id, job_id, timestamp, level, message,
                    metadata_json, phase, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    log_entry.id,
                    log_entry.job_id,
                    log_entry.timestamp.isoformat(),
                    log_entry.level,
                    log_entry.message,
                    json.dumps(log_entry.metadata),
                    log_entry.phase,
                    log_entry.source,
                ),
            )

    def get_logs(
        self,
        job_id: str,
        level: Optional[str] = None,
        phase: Optional[str] = None,
        limit: int = 1000,
    ) -> List[LogEntry]:
        """
        Get log entries for a job

        Args:
            job_id: Job ID to get logs for
            level: Optional log level filter
            phase: Optional phase filter
            limit: Maximum number of logs to return

        Returns:
            List of LogEntry instances
        """
        query = "SELECT * FROM logs WHERE job_id = ?"
        params = [job_id]

        if level:
            query += " AND level = ?"
            params.append(level.upper())

        if phase:
            query += " AND phase = ?"
            params.append(phase)

        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_log_entry(dict(row)) for row in rows]

    def _row_to_log_entry(self, row: Dict[str, Any]) -> LogEntry:
        """Convert database row to LogEntry instance"""
        return LogEntry(
            id=row["id"],
            job_id=row["job_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            level=row["level"],
            message=row["message"],
            metadata=json.loads(row["metadata_json"]),
            phase=row["phase"],
            source=row["source"],
        )

    # ===== Utility Operations =====

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job and all related data

        Args:
            job_id: Job ID to delete

        Returns:
            True if job was deleted, False if not found
        """
        with self._get_connection() as conn:
            # Delete related data first (foreign key constraints)
            conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM phase_events WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM logs WHERE job_id = ?", (job_id,))

            # Delete job
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    def get_job_stats(self) -> Dict[str, int]:
        """
        Get job statistics

        Uses cached read connection to avoid creating new connections
        for this frequently-called operation (every minute).

        Returns:
            Dictionary with counts per status
        """
        import time

        logger = logging.getLogger(__name__)
        logger.info(
            f"[HANG-DEBUG] get_job_stats(): About to get read connection at {time.time():.3f}"
        )

        try:
            conn = self._get_read_connection()
            logger.info(
                f"[HANG-DEBUG] get_job_stats(): Got read connection, executing query at {time.time():.3f}"
            )
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM jobs
                GROUP BY status
            """)
            logger.info(
                f"[HANG-DEBUG] get_job_stats(): Query executed, fetching results at {time.time():.3f}"
            )
            rows = cursor.fetchall()
            logger.info(
                f"[HANG-DEBUG] get_job_stats(): Fetched all rows at {time.time():.3f}"
            )

            return {row["status"]: row["count"] for row in rows}
        except sqlite3.DatabaseError as e:
            # If cached connection is stale, reset it and retry with fresh connection
            logger.warning(
                f"[HANG-DEBUG] get_job_stats(): Database error, resetting connection: {e}"
            )
            self._read_conn = None
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count
                    FROM jobs
                    GROUP BY status
                """)
                rows = cursor.fetchall()
                return {row["status"]: row["count"] for row in rows}

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """
        Delete completed/failed jobs older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of jobs deleted
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        with self._get_connection() as conn:
            # Get jobs to delete
            cursor = conn.execute(
                """
                SELECT id FROM jobs
                WHERE status IN ('succeeded', 'failed', 'cancelled')
                AND completed_at < ?
            """,
                (cutoff_iso,),
            )

            job_ids = [row["id"] for row in cursor.fetchall()]

            # Delete related data
            for job_id in job_ids:
                conn.execute("DELETE FROM phase_events WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM logs WHERE job_id = ?", (job_id,))

            # Delete jobs
            cursor = conn.execute(
                """
                DELETE FROM jobs
                WHERE status IN ('succeeded', 'failed', 'cancelled')
                AND completed_at < ?
            """,
                (cutoff_iso,),
            )

            return cursor.rowcount

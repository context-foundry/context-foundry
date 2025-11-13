"""
Persistence layer for Context Foundry Daemon

SQLite-based storage for jobs, phase events, and logs.
Uses WAL mode for better concurrency.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from datetime import datetime

from .models import Job, JobStatus, JobType, PhaseEvent, LogEntry


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

        # Initialize database
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper settings"""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema with tables and indexes"""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

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

        query += " ORDER BY priority DESC, created_at ASC LIMIT ? OFFSET ?"
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
            conn.execute("DELETE FROM phase_events WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM logs WHERE job_id = ?", (job_id,))

            # Delete job
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    def get_job_stats(self) -> Dict[str, int]:
        """
        Get job statistics

        Returns:
            Dictionary with counts per status
        """
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

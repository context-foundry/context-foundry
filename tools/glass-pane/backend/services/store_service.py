"""
Wrapper service for Context Foundry Store API.

This service provides a clean interface to the Context Foundry SQLite database,
handling connection management, query execution, and data transformation.
"""

import logging
import sqlite3
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from models.job import Job, JobDetailResponse
from models.log import Log
from models.phase import PhaseInfo

logger = logging.getLogger(__name__)


class StoreService:
    """
    Interface to Context Foundry's SQLite database.

    Provides read-only access with thread-safe operations and automatic
    connection management.
    """

    def __init__(self, db_path: Path, timeout: float = 5.0):
        """
        Initialize Store service.

        Args:
            db_path: Path to Context Foundry jobs.db
            timeout: Query timeout in seconds
        """
        self.db_path = db_path
        self.timeout = timeout
        self._validate_db()

    def _validate_db(self):
        """Validate database exists and is accessible."""
        if not self.db_path.exists():
            logger.warning(f"Database not found at {self.db_path}")
        else:
            logger.info(f"Connected to database: {self.db_path}")

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
        return conn

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Job], int]:
        """
        List jobs with optional filtering.

        Args:
            status: Filter by status ('running', 'succeeded', 'failed', 'cancelled')
            limit: Maximum number of jobs to return
            offset: Pagination offset

        Returns:
            Tuple of (jobs list, total count)
        """
        conn = self._get_connection()
        try:
            # Build query with case-insensitive status comparison
            query = "SELECT * FROM jobs"
            params = []

            if status:
                query += " WHERE LOWER(status) = LOWER(?)"
                params.append(status)

            query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            # Execute query
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            # Get total count
            count_query = "SELECT COUNT(*) FROM jobs"
            if status:
                count_query += " WHERE LOWER(status) = LOWER(?)"
                total = conn.execute(count_query, [status]).fetchone()[0]
            else:
                total = conn.execute(count_query).fetchone()[0]

            # Transform to Job models
            jobs = [self._row_to_job(row) for row in rows]

            return jobs, total

        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a specific job by ID.

        Args:
            job_id: Job UUID

        Returns:
            Job model or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", [job_id])
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_job(row)

        finally:
            conn.close()

    def get_job_working_directory(self, job_id: str) -> Optional[str]:
        """
        Get working directory for a specific job from params_json.

        Args:
            job_id: Job UUID

        Returns:
            Working directory path or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT params_json FROM jobs WHERE id = ?", [job_id])
            row = cursor.fetchone()

            if not row:
                return None

            import json

            params = json.loads(row["params_json"])
            working_dir = params.get("working_directory")

            if working_dir:
                logger.info(f"Job {job_id} working_directory: {working_dir}")
            return working_dir

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse params_json for job {job_id}: {e}")
            return None
        finally:
            conn.close()

    def get_job_detail(self, job_id: str) -> Optional[JobDetailResponse]:
        """
        Get detailed job information including phase history.

        Args:
            job_id: Job UUID

        Returns:
            JobDetailResponse or None if not found
        """
        job = self.get_job(job_id)
        if not job:
            return None

        # Get phase history (if phase_events table exists)
        phases = self._get_phase_history(job_id)

        return JobDetailResponse(
            id=job.id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            project_name=job.project_name,
            current_phase=job.current_phase,
            tokens_used=job.tokens_used,
            total_files=job.total_files,
            phases=phases,
        )

    def _get_phase_history(self, job_id: str) -> List[PhaseInfo]:
        """Get phase execution history for a job."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    phase,
                    status,
                    timestamp,
                    duration_seconds,
                    details_json
                FROM phase_events
                WHERE job_id = ?
                ORDER BY timestamp ASC
                """,
                [job_id],
            )
            rows = cursor.fetchall()

            phases = []
            for row in rows:
                phase_name = row["phase"]
                status = row["status"]
                timestamp = row["timestamp"]
                duration = row["duration_seconds"]

                # Calculate completed_at if duration exists
                completed_at = None
                if duration and timestamp:
                    from datetime import datetime, timedelta

                    try:
                        start = datetime.fromisoformat(timestamp)
                        end = start + timedelta(seconds=duration)
                        completed_at = end.isoformat()
                    except (ValueError, TypeError):
                        pass

                # Extract iteration number from phase name (e.g., "Test_iteration_1" → 1)
                iteration = 0
                if "_iteration_" in phase_name.lower():
                    try:
                        iteration = int(phase_name.split("_iteration_")[-1])
                        # Clean up phase name (remove iteration suffix)
                        phase_name = phase_name.split("_iteration_")[0]
                    except (ValueError, IndexError):
                        pass

                # Map status to PhaseStatus enum
                status_map = {
                    "in_progress": "active",
                    "completed": "completed",
                    "failed": "failed",
                    "pending": "pending",
                }
                mapped_status = status_map.get(status.lower(), status)

                phases.append(
                    PhaseInfo(
                        phase=phase_name,
                        status=mapped_status,
                        description="",
                        started_at=timestamp,
                        completed_at=completed_at,
                        iteration=iteration,
                    )
                )

            return phases

        except Exception as e:
            logger.warning(f"Failed to get phase history for job {job_id}: {e}")
            return []
        finally:
            conn.close()

    def get_logs(
        self,
        job_id: str,
        level: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        since_timestamp: Optional[str] = None,
        since_id: Optional[str] = None,
    ) -> tuple[List[Log], int]:
        """
        Get logs for a specific job.

        Args:
            job_id: Job UUID
            level: Filter by log level
            search: Text search in message
            limit: Maximum number of logs
            offset: Pagination offset
            since_timestamp: Get logs after this timestamp (for incremental fetches)
            since_id: Get logs after this ID when timestamp matches (for lossless streaming)

        Returns:
            Tuple of (logs list, total count)
        """
        conn = self._get_connection()
        try:
            # Build query
            query = "SELECT * FROM logs WHERE job_id = ?"
            params = [job_id]

            if level:
                query += " AND level = ?"
                params.append(level)

            if search:
                query += " AND message LIKE ?"
                params.append(f"%{search}%")

            # Use composite filtering to handle same-timestamp logs
            if since_timestamp is not None:
                if since_id is not None:
                    # Get logs where (timestamp > since_timestamp) OR (timestamp = since_timestamp AND id > since_id)
                    query += " AND ((timestamp > ?) OR (timestamp = ? AND id > ?))"
                    params.extend([since_timestamp, since_timestamp, since_id])
                else:
                    query += " AND timestamp > ?"
                    params.append(since_timestamp)

            query += " ORDER BY timestamp ASC, id ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            # Execute query
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            # Get total count
            count_query = "SELECT COUNT(*) FROM logs WHERE job_id = ?"
            count_params = [job_id]

            if level:
                count_query += " AND level = ?"
                count_params.append(level)

            if search:
                count_query += " AND message LIKE ?"
                count_params.append(f"%{search}%")

            total = conn.execute(count_query, count_params).fetchone()[0]

            # Transform to Log models
            logs = [self._row_to_log(row) for row in rows]

            return logs, total

        finally:
            conn.close()

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job model."""
        # sqlite3.Row supports dict-like access via [] but not .get()
        # Convert to dict for easier access with defaults
        row_dict = dict(row)

        # Parse metadata_json to extract project_name
        import json

        metadata = {}
        try:
            metadata = json.loads(row_dict.get("metadata_json", "{}"))
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse metadata_json for job {row_dict['id']}")

        params = {}
        try:
            params = json.loads(row_dict.get("params_json", "{}"))
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse params_json for job {row_dict['id']}")

        # Extract project_name from metadata or params
        project_name = metadata.get("project_name")
        if not project_name:
            working_dir = params.get("working_directory", "")
            project_name = Path(working_dir).name if working_dir else "Unknown"

        # Get tokens_used and total_files from metadata, or try to load from session-summary.json
        tokens_used = metadata.get("tokens_used", 0)
        total_files = metadata.get("total_files", 0)
        current_phase = metadata.get("current_phase")

        # If metadata is empty, try to load from session-summary.json
        if tokens_used == 0 and total_files == 0:
            working_dir = params.get("working_directory", "")
            if working_dir:
                summary_path = (
                    Path(working_dir) / ".context-foundry" / "session-summary.json"
                )
                if summary_path.exists():
                    try:
                        summary_data = json.loads(summary_path.read_text())

                        # Calculate total tokens from all phases
                        context_metrics = summary_data.get("context_metrics", {})
                        by_phase = context_metrics.get("by_phase", {})
                        for phase_name, phase_data in by_phase.items():
                            tokens_used += phase_data.get("tokens_used", 0)

                        # Get file count from files_created array
                        files_created = summary_data.get("files_created", [])
                        total_files = len(files_created)

                        logger.info(
                            f"Loaded metrics from session-summary.json for job {row_dict['id']}: {tokens_used} tokens, {total_files} files"
                        )
                    except (json.JSONDecodeError, FileNotFoundError) as e:
                        logger.debug(
                            f"Could not load session-summary.json for job {row_dict['id']}: {e}"
                        )

        return Job(
            id=row_dict["id"],
            status=row_dict.get("status", "unknown"),
            started_at=row_dict.get("started_at") or datetime.now().isoformat(),
            completed_at=row_dict.get("completed_at"),
            project_name=project_name,
            current_phase=current_phase,
            tokens_used=tokens_used,
            total_files=total_files,
        )

    def _row_to_log(self, row: sqlite3.Row) -> Log:
        """Convert database row to Log model."""
        return Log(
            id=row["id"],
            job_id=row["job_id"],
            timestamp=row["timestamp"],
            level=row["level"],
            message=row["message"],
        )


# Note: This is a mock implementation since we don't have access to the actual
# Context Foundry Store API. In production, this would import and use the real Store.

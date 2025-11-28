"""
Daemon Client - SQLite query wrapper for CF Daemon

Provides a clean interface to query the CF Daemon's SQLite database
using the Store API from context_foundry.daemon.store.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    from context_foundry.daemon.store import Store
    from context_foundry.daemon.models import Job, JobType, JobStatus
    from context_foundry.daemon.jobs import JobManager
    from context_foundry.daemon.config import DaemonConfig
except ImportError:
    # Graceful fallback for testing
    Store = None
    Job = None
    JobType = None
    JobStatus = None
    JobManager = None
    DaemonConfig = None


@dataclass
class PhaseEvent:
    """Phase event model matching database schema"""

    job_id: str
    phase: str  # scout, architect, builder, test
    status: str  # started, completed, failed
    timestamp: datetime
    progress_percent: float
    metadata_json: Optional[str] = None


@dataclass
class LogEntry:
    """Log entry model matching database schema"""

    job_id: str
    timestamp: datetime
    level: str  # INFO, SUCCESS, WARNING, ERROR, DEBUG
    message: str
    phase: Optional[str] = None
    source: Optional[str] = None


@dataclass
class SystemMetrics:
    """Aggregated system statistics"""

    total_jobs: int
    active_jobs: int
    success_rate: float
    avg_duration_seconds: float


class DaemonClient:
    """
    Client for interacting with CF Daemon's SQLite database.

    Uses the official Store API to ensure compatibility and thread-safety.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the daemon client.

        Args:
            db_path: Path to jobs.db (defaults to ~/.context-foundry/cfd/jobs.db)
        """
        if db_path is None:
            db_path = os.path.expanduser("~/.context-foundry/cfd/jobs.db")

        self.db_path = Path(db_path)
        self.store: Optional[Store] = None
        self.job_manager: Optional[JobManager] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Connect to the daemon's database.

        Returns:
            True if connected successfully, False otherwise
        """
        if not self.db_path.exists():
            return False

        try:
            if Store is None:
                return False

            self.store = Store(str(self.db_path))

            # Initialize JobManager (without runner for read operations)
            if JobManager and DaemonConfig:
                config = DaemonConfig()
                self.job_manager = JobManager(config, self.store, runner=None)

            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    @property
    def connected(self) -> bool:
        """Check if client is connected to database"""
        return self._connected

    def list_jobs(self, limit: int = 100, status: Optional[str] = None) -> List[Job]:
        """
        List jobs from the database.

        Args:
            limit: Maximum number of jobs to return
            status: Filter by status (queued, running, succeeded, failed, cancelled)

        Returns:
            List of Job objects
        """
        if not self._connected or self.store is None:
            return []

        try:
            if status:
                jobs = self.store.list_jobs(limit=limit, status=status)
            else:
                jobs = self.store.list_jobs(limit=limit)
            return jobs
        except Exception:
            return []

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a single job by ID.

        Args:
            job_id: Job UUID

        Returns:
            Job object or None if not found
        """
        if not self._connected or self.store is None:
            return None

        try:
            return self.store.get_job(job_id)
        except Exception:
            return None

    def get_phases(self, job_id: str) -> List[PhaseEvent]:
        """
        Get phase events for a job.

        Args:
            job_id: Job UUID

        Returns:
            List of PhaseEvent objects ordered by timestamp
        """
        if not self._connected or self.store is None:
            return []

        try:
            # Query phase_events table directly
            events = self.store.get_phase_events(job_id)
            return events
        except Exception:
            return []

    def get_logs(
        self, job_id: str, since_timestamp: Optional[datetime] = None, limit: int = 1000
    ) -> List[LogEntry]:
        """
        Get logs for a job.

        Args:
            job_id: Job UUID
            since_timestamp: Only return logs after this timestamp
            limit: Maximum number of logs to return

        Returns:
            List of LogEntry objects ordered by timestamp
        """
        if not self._connected or self.store is None:
            return []

        try:
            if since_timestamp:
                logs = self.store.get_logs(job_id, since=since_timestamp, limit=limit)
            else:
                logs = self.store.get_logs(job_id, limit=limit)
            return logs
        except Exception:
            return []

    def get_metrics(self) -> SystemMetrics:
        """
        Calculate system-wide metrics.

        Returns:
            SystemMetrics with aggregated statistics
        """
        if not self._connected or self.store is None:
            return SystemMetrics(
                total_jobs=0, active_jobs=0, success_rate=0.0, avg_duration_seconds=0.0
            )

        try:
            all_jobs = self.store.list_jobs(limit=1000)
            total = len(all_jobs)

            active = sum(1 for job in all_jobs if job.status in ["queued", "running"])

            succeeded = sum(1 for job in all_jobs if job.status == "succeeded")

            success_rate = (succeeded / total * 100) if total > 0 else 0.0

            # Calculate average duration for completed jobs
            durations = [
                job.duration.total_seconds()
                for job in all_jobs
                if job.duration is not None
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

            return SystemMetrics(
                total_jobs=total,
                active_jobs=active,
                success_rate=success_rate,
                avg_duration_seconds=avg_duration,
            )
        except Exception:
            return SystemMetrics(
                total_jobs=0, active_jobs=0, success_rate=0.0, avg_duration_seconds=0.0
            )

    def submit_job(
        self, job_type: str, params: Dict, metadata: Optional[Dict] = None
    ) -> Optional[Job]:
        """
        Submit a new job via JobManager.

        Args:
            job_type: Type of job (autonomous_build, test, etc.)
            params: Job parameters dictionary
            metadata: Optional metadata dictionary for display purposes

        Returns:
            Created Job object or None on error
        """
        if not self._connected or self.job_manager is None:
            return None

        try:
            # Auto-generate metadata if not provided
            if metadata is None:
                from pathlib import Path

                working_dir = params.get("working_directory", "")
                project_name = Path(working_dir).name if working_dir else "Unknown"
                metadata = {
                    "source": "tui",
                    "build_type": params.get("mode", "new_project"),
                    "project_name": project_name,
                }
            job = self.job_manager.submit_job(job_type, params, metadata=metadata)
            return job
        except Exception:
            return None

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job UUID

        Returns:
            True if cancelled successfully, False otherwise
        """
        if not self._connected or self.job_manager is None:
            return False

        try:
            self.job_manager.cancel_job(job_id)
            return True
        except Exception:
            return False

"""
Job Table Widget - DataTable showing job list

Displays jobs with columns: ID, Type, Status, Phase, Duration
Supports row selection and status icon rendering.
"""

from datetime import timedelta
from typing import List, Optional
from textual.widgets import DataTable

from ..daemon_client import Job


class JobTable(DataTable):
    """
    DataTable widget for displaying jobs.

    Columns:
    - ID: Short job ID (first 8 chars)
    - Type: Job type
    - Status: Status with icon
    - Phase: Current phase
    - Duration: Formatted duration
    """

    # Status icon mapping
    STATUS_ICONS = {
        "queued": "⏳",
        "running": "🔄",
        "succeeded": "✓",
        "failed": "✗",
        "cancelled": "🚫",
    }

    def __init__(self, **kwargs):
        """Initialize the job table"""
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Setup table columns"""
        self.add_column("ID", width=10)
        self.add_column("Type", width=15)
        self.add_column("Status", width=12)
        self.add_column("Phase", width=12)
        self.add_column("Duration", width=12)

    def update_jobs(self, jobs: List[Job]) -> None:
        """
        Update table with new job list.

        Args:
            jobs: List of Job objects to display
        """
        # Clear existing rows
        self.clear()

        # Add rows for each job
        for job in jobs:
            self.add_row(
                self._format_id(job.job_id),
                self._format_type(job.job_type),
                self._format_status(job.status),
                self._get_current_phase(job),
                self._format_duration(job.duration),
                key=job.job_id,
            )

    def _format_id(self, job_id: str) -> str:
        """Format job ID (first 8 chars)"""
        return job_id[:8] if len(job_id) >= 8 else job_id

    def _format_type(self, job_type: str) -> str:
        """Format job type for display"""
        if job_type == "autonomous_build":
            return "Build"
        return job_type.capitalize()

    def _format_status(self, status: str) -> str:
        """Format status with icon"""
        icon = self.STATUS_ICONS.get(status, "?")
        return f"{icon} {status.capitalize()}"

    def _get_current_phase(self, job: Job) -> str:
        """Get current phase for job"""
        # This would ideally query phase_events, but for now
        # we'll infer from status
        if job.status == "queued":
            return "-"
        elif job.status == "running":
            return "Building"  # Could be improved with actual phase data
        elif job.status == "succeeded":
            return "Complete"
        elif job.status == "failed":
            return "Failed"
        return "-"

    def _format_duration(self, duration: Optional[timedelta]) -> str:
        """Format duration as HH:MM:SS"""
        if duration is None:
            return "-"

        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_selected_job_id(self) -> Optional[str]:
        """
        Get the job ID of the currently selected row.

        Returns:
            Job ID string or None if no selection
        """
        if self.cursor_row >= 0 and self.cursor_row < len(self.rows):
            row_key = self.get_row_at(self.cursor_row)
            if row_key:
                return str(row_key[0])  # Row key is the job_id
        return None

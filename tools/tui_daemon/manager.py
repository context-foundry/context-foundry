"""
TUI Manager - Central state coordinator

Manages navigation between screens, daemon connection lifecycle,
and global state for the TUI application.
"""

from typing import Optional, Callable, List
from enum import Enum

from .daemon_client import DaemonClient, Job
from .log_streamer import LogStreamer


class Screen(Enum):
    """Available screens in the TUI"""

    CONVERSATION = "conversation"
    DASHBOARD = "dashboard"
    DETAIL = "detail"


class TUIManager:
    """
    Central state management for the TUI application.

    Coordinates:
    - Screen navigation
    - Daemon connection lifecycle
    - Job refresh intervals
    - Selected job state
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the TUI manager.

        Args:
            db_path: Path to jobs.db (defaults to ~/.context-foundry/cfd/jobs.db)
        """
        self.daemon_client = DaemonClient(db_path)
        self.log_streamer = LogStreamer(self.daemon_client)

        # State
        self._current_screen = Screen.DASHBOARD
        self._selected_job_id: Optional[str] = None
        self._auto_refresh_enabled = True
        self._refresh_callbacks: List[Callable] = []

    def initialize(self) -> bool:
        """
        Initialize connection to daemon.

        Returns:
            True if connected successfully, False otherwise
        """
        return self.daemon_client.connect()

    @property
    def connected(self) -> bool:
        """Check if connected to daemon"""
        return self.daemon_client.connected

    @property
    def current_screen(self) -> Screen:
        """Get current screen"""
        return self._current_screen

    def navigate_to(self, screen: Screen) -> None:
        """
        Navigate to a different screen.

        Args:
            screen: Target screen to navigate to
        """
        self._current_screen = screen

    def get_current_jobs(self, limit: int = 100) -> List[Job]:
        """
        Get current job list.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of Job objects
        """
        return self.daemon_client.list_jobs(limit=limit)

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a specific job.

        Args:
            job_id: Job UUID

        Returns:
            Job object or None
        """
        return self.daemon_client.get_job(job_id)

    def select_job(self, job_id: str) -> None:
        """
        Select a job for detailed view.

        Args:
            job_id: Job UUID to select
        """
        self._selected_job_id = job_id

    @property
    def selected_job_id(self) -> Optional[str]:
        """Get currently selected job ID"""
        return self._selected_job_id

    def submit_build(self, params: dict) -> Optional[Job]:
        """
        Submit a new autonomous build.

        Args:
            params: Build parameters dict

        Returns:
            Created Job object or None on error
        """
        return self.daemon_client.submit_job("autonomous_build", params)

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job UUID to cancel

        Returns:
            True if cancelled successfully, False otherwise
        """
        return self.daemon_client.cancel_job(job_id)

    def register_refresh_callback(self, callback: Callable) -> None:
        """
        Register a callback for auto-refresh events.

        Args:
            callback: Function to call on each refresh interval
        """
        if callback not in self._refresh_callbacks:
            self._refresh_callbacks.append(callback)

    def trigger_refresh(self) -> None:
        """Trigger all registered refresh callbacks"""
        for callback in self._refresh_callbacks:
            try:
                callback()
            except Exception:
                pass  # Silently ignore callback errors

    @property
    def auto_refresh_enabled(self) -> bool:
        """Check if auto-refresh is enabled"""
        return self._auto_refresh_enabled

    def toggle_auto_refresh(self) -> None:
        """Toggle auto-refresh on/off"""
        self._auto_refresh_enabled = not self._auto_refresh_enabled

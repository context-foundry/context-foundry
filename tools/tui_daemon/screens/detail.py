"""
Detail Screen - Job details with phase pipeline and log streaming

Shows detailed view of a selected job including:
- Job metadata
- Phase pipeline visualization
- Real-time log streaming
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Footer

from ..manager import TUIManager
from ..widgets.phase_pipeline import PhasePipeline
from ..widgets.log_viewer import LogViewer


class DetailScreen(Screen):
    """
    Detail screen for viewing job progress and logs.

    Features:
    - Job metadata display
    - Phase pipeline visualization
    - Real-time log streaming
    - Action buttons (Cancel, Retry, Export)
    """

    BINDINGS = [
        ("escape", "back_to_dashboard", "Back"),
        ("c", "cancel_job", "Cancel Job"),
        ("r", "retry_job", "Retry"),
        ("a", "toggle_autoscroll", "Toggle Auto-scroll"),
    ]

    def __init__(self, manager: TUIManager, **kwargs):
        """
        Initialize the detail screen.

        Args:
            manager: TUIManager instance
        """
        super().__init__(**kwargs)
        self.manager = manager
        self._job_id = manager.selected_job_id
        self._phase_pipeline: PhasePipeline = None
        self._log_viewer: LogViewer = None
        self._job_info: Static = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout"""
        # Header with job info
        self._job_info = Static("Loading job...", classes="header")
        yield self._job_info

        # Phase pipeline
        yield Static("Phase Pipeline:", classes="section-title")
        self._phase_pipeline = PhasePipeline()
        yield self._phase_pipeline

        # Log viewer
        yield Static("Logs:", classes="section-title")
        self._log_viewer = LogViewer()
        yield self._log_viewer

        # Footer
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount"""
        if not self._job_id:
            self._job_info.update("❌ No job selected")
            return

        # Load job data
        self._load_job_data()

        # Start log streaming
        self._start_log_streaming()

    def on_unmount(self) -> None:
        """Handle screen unmount"""
        # Stop log streaming
        if self.manager.log_streamer.is_streaming:
            self.manager.log_streamer.stop_streaming()

    def _load_job_data(self) -> None:
        """Load and display job data"""
        job = self.manager.get_job(self._job_id)
        if not job:
            self._job_info.update("❌ Job not found")
            return

        # Update job info header
        duration_str = "N/A"
        if job.duration:
            total_seconds = int(job.duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            duration_str = f"{minutes}m {seconds}s"

        self._job_info.update(
            f"Job: {job.job_id[:8]} | Status: {job.status} | Duration: {duration_str}"
        )

        # Load phase events
        phases = self.manager.daemon_client.get_phases(self._job_id)
        if self._phase_pipeline:
            self._phase_pipeline.update_phases(phases)

    def _start_log_streaming(self) -> None:
        """Start streaming logs for the job"""

        def on_new_logs(logs):
            """Callback for new logs"""
            if self._log_viewer:
                self._log_viewer.append_logs(logs)

        # Start streaming
        self.manager.log_streamer.start_streaming(self._job_id, on_new_logs)

    def action_back_to_dashboard(self) -> None:
        """Navigate back to dashboard"""
        self.app.pop_screen()

    def action_cancel_job(self) -> None:
        """Cancel the current job"""
        if self._job_id:
            success = self.manager.cancel_job(self._job_id)
            if success:
                self._job_info.update(self._job_info.renderable + " | Cancelling...")

    def action_retry_job(self) -> None:
        """Retry the job with same parameters"""
        job = self.manager.get_job(self._job_id)
        if job:
            # Re-submit with same params
            new_job = self.manager.submit_build(job.params)
            if new_job:
                self._job_info.update(f"✅ Retried as {new_job.job_id[:8]}")

    def action_toggle_autoscroll(self) -> None:
        """Toggle auto-scroll in log viewer"""
        if self._log_viewer:
            self._log_viewer.toggle_auto_scroll()

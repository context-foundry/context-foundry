"""
Dashboard Screen - Live job monitoring

Displays job table with auto-refresh and system metrics.
Main entry point for the TUI application.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Footer

from ..manager import TUIManager
from ..widgets.job_table import JobTable
from ..widgets.metrics_panel import MetricsPanel


class DashboardScreen(Screen):
    """
    Dashboard screen with job table and metrics.

    Features:
    - Live job table with 1-second auto-refresh
    - System metrics panel
    - Row selection → navigate to detail screen
    - Keyboard shortcuts for actions
    """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("n", "new_build", "New Build"),
        ("q", "quit_app", "Quit"),
        ("enter", "view_details", "View Details"),
    ]

    def __init__(self, manager: TUIManager, **kwargs):
        """
        Initialize the dashboard screen.

        Args:
            manager: TUIManager instance
        """
        super().__init__(**kwargs)
        self.manager = manager
        self._job_table: JobTable = None
        self._metrics_panel: MetricsPanel = None
        self._auto_refresh_timer = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout"""
        # Header
        yield Static("📊 CF Daemon Dashboard", classes="header")

        # Metrics panel
        self._metrics_panel = MetricsPanel()
        yield self._metrics_panel

        # Job table
        self._job_table = JobTable()
        yield self._job_table

        # Footer with keybindings
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount"""
        # Initial data load
        self._refresh_data()

        # Start auto-refresh (1 second interval)
        self._auto_refresh_timer = self.set_interval(1.0, self._refresh_data)

    def on_unmount(self) -> None:
        """Handle screen unmount"""
        # Stop auto-refresh
        if self._auto_refresh_timer:
            self._auto_refresh_timer.stop()

    def _refresh_data(self) -> None:
        """Refresh jobs and metrics from daemon"""
        if not self.manager.connected:
            return

        # Get jobs
        jobs = self.manager.get_current_jobs(limit=100)

        # Update job table
        if self._job_table:
            self._job_table.update_jobs(jobs)

        # Get and update metrics
        metrics = self.manager.daemon_client.get_metrics()
        if self._metrics_panel:
            self._metrics_panel.update_metrics(metrics)

    def action_refresh(self) -> None:
        """Manual refresh action"""
        self._refresh_data()

    def action_new_build(self) -> None:
        """Navigate to conversation screen for new build"""
        from .conversation import ConversationScreen

        self.app.push_screen(ConversationScreen(self.manager))

    def action_quit_app(self) -> None:
        """Quit the application"""
        self.app.exit()

    def action_view_details(self) -> None:
        """Navigate to detail screen for selected job"""
        if not self._job_table:
            return

        job_id = self._job_table.get_selected_job_id()
        if job_id:
            # Set selected job in manager
            self.manager.select_job(job_id)

            # Navigate to detail screen
            from .detail import DetailScreen

            self.app.push_screen(DetailScreen(self.manager))

"""Dashboard screen - main view"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding

from ..widgets.build_table import BuildTable
from ..widgets.phase_progress import PhaseProgressWidget
from ..widgets.token_gauge import TokenGaugeWidget
from ..data.provider import TUIDataProvider


class DashboardScreen(Screen):
    """Main dashboard view"""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("m", "metrics", "Metrics"),
        Binding("n", "new_project", "New Project"),
        Binding("escape", "quit", "Quit"),
    ]

    def __init__(self, provider: TUIDataProvider):
        super().__init__()
        self.provider = provider

    def compose(self) -> ComposeResult:
        """Compose the dashboard"""
        yield Header()

        with Container():
            with Vertical():
                yield Static(
                    "[bold cyan]Context Foundry Build Monitor[/bold cyan]",
                    id="title"
                )
                yield PhaseProgressWidget(id="phase-progress")
                yield TokenGaugeWidget(id="token-gauge")
                yield BuildTable(id="build-table")

        yield Footer()

    def on_mount(self):
        """Setup data refresh when screen mounts"""
        self.set_interval(1.5, self.refresh_data)
        # Auto-detect new builds every 30 seconds
        self.set_interval(30.0, self.auto_detect_builds)
        self.provider.subscribe(self.refresh_data)

    def on_unmount(self):
        """Cleanup when screen unmounts"""
        self.provider.unsubscribe(self.refresh_data)

    async def refresh_data(self):
        """Refresh dashboard data"""
        try:
            # Get recent builds (includes all tracked builds)
            builds = await self.provider.get_recent_builds()

            # Use the most recent build for the phase progress widget
            if builds:
                most_recent = builds[0]

                # Update progress widget
                progress_widget = self.query_one("#phase-progress", PhaseProgressWidget)
                progress_widget.current_phase = f"{most_recent.current_phase}"

                # Calculate progress based on phase
                phase_map = {
                    "Scout": 14,
                    "Architect": 28,
                    "Builder": 57,
                    "Test": 71,
                    "Fix": 85,
                    "Deploy": 95,
                    "Complete": 100
                }
                phase_name = most_recent.current_phase.split()[0]  # Get first word
                progress = phase_map.get(phase_name, 0)

                progress_widget.progress_detail = most_recent.status
                progress_widget.progress = progress

                # Update token gauge (mock data for now)
                # TODO: Get real token data from metrics
                token_widget = self.query_one("#token-gauge", TokenGaugeWidget)
                token_widget.tokens_used = 50000  # Mock
                token_widget.tokens_total = 200000
            else:
                # No builds - show empty state
                progress_widget = self.query_one("#phase-progress", PhaseProgressWidget)
                progress_widget.current_phase = "No active builds"
                progress_widget.progress_detail = "Press 'n' to launch a new build"
                progress_widget.progress = 0

            # Update build table
            build_table = self.query_one("#build-table", BuildTable)
            build_table.builds = builds

        except Exception as e:
            # Log error but don't crash
            import traceback
            # You can log to a file here if needed
            pass

    def action_quit(self):
        """Quit the app"""
        self.app.exit()

    def action_help(self):
        """Show help screen"""
        self.app.push_screen("help")

    def action_refresh(self):
        """Manual refresh"""
        self.refresh_data()

    def action_metrics(self):
        """Show metrics screen"""
        self.app.push_screen("metrics")

    def action_new_project(self):
        """Show new project screen"""
        self.app.push_screen("new_project")

    def auto_detect_builds(self):
        """Trigger auto-detection of running builds"""
        self.provider._auto_detect_builds()

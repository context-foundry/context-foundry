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
        self.provider.subscribe(self.refresh_data)

    def on_unmount(self):
        """Cleanup when screen unmounts"""
        self.provider.unsubscribe(self.refresh_data)

    async def refresh_data(self):
        """Refresh dashboard data"""
        try:
            # Get current build
            build = await self.provider.get_current_build()

            if build:
                # Update progress widget
                progress_widget = self.query_one("#phase-progress", PhaseProgressWidget)
                progress_widget.current_phase = f"{build.current_phase} ({build.phase_number})"
                progress_widget.progress_detail = build.progress_detail
                progress_widget.progress = build.get_progress_percentage()

                # Update token gauge (mock data for now)
                # TODO: Get real token data from metrics
                token_widget = self.query_one("#token-gauge", TokenGaugeWidget)
                token_widget.tokens_used = 50000  # Mock
                token_widget.tokens_total = 200000

            # Get recent builds
            builds = await self.provider.get_recent_builds()
            build_table = self.query_one("#build-table", BuildTable)
            build_table.builds = builds

        except Exception as e:
            # Log error but don't crash
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

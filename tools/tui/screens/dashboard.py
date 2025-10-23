"""Dashboard screen - main view"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding

from ..widgets.build_table import BuildTable
from ..widgets.phase_progress import PhaseProgressWidget
from ..widgets.token_gauge import TokenGaugeWidget
from ..widgets.phase_pipeline import PhasesPipelineWidget
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
                yield PhasesPipelineWidget(id="phase-pipeline")

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

            # Update pipeline widget with most recent build
            pipeline = self.query_one("#phase-pipeline", PhasesPipelineWidget)

            if builds:
                most_recent = builds[0]

                # Get the actual build status object
                from pathlib import Path
                build_status = await self.provider.get_current_build(
                    Path(self.provider._tracked_builds[0]) if self.provider._tracked_builds else None
                )

                if build_status:
                    # Update pipeline with build data
                    duration = most_recent.duration_minutes
                    pipeline.update_from_build(build_status, duration)
                else:
                    # No build status available
                    pipeline.update_from_build(None)
            else:
                # No builds - show empty state
                pipeline.update_from_build(None)

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

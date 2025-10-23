"""Build detail screen - detailed view of a single build"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding

from ..widgets.log_viewer import LogViewerWidget
from ..data.provider import TUIDataProvider


class BuildDetailScreen(Screen):
    """Detailed view of a single build"""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
        Binding("d", "dashboard", "Dashboard"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, provider: TUIDataProvider, session_id: str):
        super().__init__()
        self.provider = provider
        self.session_id = session_id

    def compose(self) -> ComposeResult:
        """Compose the build detail screen"""
        yield Header()

        with Container():
            with Vertical():
                yield Static(
                    f"[bold]Build Details: {self.session_id}[/bold]",
                    id="build-title"
                )
                yield Static("Loading...", id="build-info")
                yield Static("[bold]Build Logs[/bold]", id="logs-title")
                yield LogViewerWidget(id="build-logs")

        yield Footer()

    def on_mount(self):
        """Setup when screen mounts"""
        self.set_interval(2.0, self.refresh_data)
        self.refresh_data()

    async def refresh_data(self):
        """Refresh build detail data"""
        try:
            # Get current build status
            build = await self.provider.get_current_build()

            if build and build.session_id == self.session_id:
                # Update build info
                info = self.query_one("#build-info", Static)
                info_text = f"""
[bold]Phase:[/bold] {build.current_phase} ({build.phase_number})
[bold]Status:[/bold] {build.status}
[bold]Progress:[/bold] {build.progress_detail}
[bold]Test Iteration:[/bold] {build.test_iteration}
[bold]Phases Completed:[/bold] {', '.join(build.phases_completed)}
[bold]Started:[/bold] {build.started_at.strftime('%Y-%m-%d %H:%M:%S')}
[bold]Last Updated:[/bold] {build.last_updated.strftime('%Y-%m-%d %H:%M:%S')}
"""
                info.update(info_text)

            # Get and display logs
            logs = await self.provider.get_build_logs(self.session_id)
            log_viewer = self.query_one("#build-logs", LogViewerWidget)

            # Only update if logs changed
            if logs:
                log_viewer.clear_logs()
                log_viewer.add_logs(logs, "info")

        except Exception:
            pass

    def action_quit(self):
        """Quit application"""
        self.app.exit()

    def action_pop_screen(self):
        """Go back"""
        self.app.pop_screen()

    def action_dashboard(self):
        """Go to dashboard"""
        self.app.pop_screen()

    def action_refresh(self):
        """Manual refresh"""
        self.refresh_data()

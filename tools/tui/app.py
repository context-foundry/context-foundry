"""Main TUI application"""

from textual.app import App
from textual.binding import Binding

from .config import TUIConfig
from .data.provider import TUIDataProvider
from .screens.dashboard import DashboardScreen
from .screens.help import HelpScreen
from .screens.metrics import MetricsScreen
from .screens.new_project import NewProjectScreen


class ContextFoundryTUI(App):
    """Context Foundry TUI Monitor Application"""

    CSS = """
    Screen {
        background: $surface;
    }

    #title {
        background: $primary;
        color: $text;
        padding: 1;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #phase-progress {
        height: 5;
        padding: 1;
        border: solid $primary;
        margin-bottom: 1;
    }

    #phase-label {
        text-style: bold;
    }

    #phase-detail {
        color: $text-muted;
        margin-bottom: 1;
    }

    #token-gauge {
        height: 4;
        padding: 1;
        border: solid $accent;
        margin-bottom: 1;
    }

    #build-table {
        height: 1fr;
        border: solid $success;
    }

    #metrics-title, #agent-title, #build-title, #logs-title {
        padding: 1;
        text-align: center;
        margin-bottom: 1;
    }

    #stats-container {
        height: auto;
        padding: 1;
        border: solid $primary;
        margin-bottom: 1;
    }

    #stats-summary, #stats-details {
        width: 1fr;
        padding: 1;
    }

    #agent-table {
        height: 1fr;
        border: solid $accent;
    }

    #build-info {
        padding: 1;
        border: solid $primary;
        margin-bottom: 1;
    }

    #build-logs {
        height: 1fr;
        border: solid $success;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "dashboard", "Dashboard"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.config = TUIConfig.from_env()
        self.provider = TUIDataProvider(self.config)

    async def on_mount(self):
        """Initialize app"""
        # Start data provider
        await self.provider.start()

        # Install screens
        self.install_screen(DashboardScreen(self.provider), name="dashboard")
        self.install_screen(HelpScreen(), name="help")
        self.install_screen(MetricsScreen(self.provider), name="metrics")
        self.install_screen(NewProjectScreen(self.provider), name="new_project")

        # Push dashboard as initial screen
        self.push_screen("dashboard")

    async def on_unmount(self):
        """Cleanup on app shutdown"""
        await self.provider.stop()

    def action_quit(self):
        """Quit application"""
        self.exit()

    def action_dashboard(self):
        """Go to dashboard"""
        # Pop all screens and push dashboard
        while len(self.screen_stack) > 1:
            self.pop_screen()

    def action_help(self):
        """Show help screen"""
        self.push_screen("help")

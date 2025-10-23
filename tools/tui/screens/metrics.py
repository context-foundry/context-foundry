"""Metrics screen - system statistics"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, DataTable
from textual.binding import Binding

from ..data.provider import TUIDataProvider


class MetricsScreen(Screen):
    """Metrics and analytics screen"""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
        Binding("d", "dashboard", "Dashboard"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, provider: TUIDataProvider):
        super().__init__()
        self.provider = provider

    def compose(self) -> ComposeResult:
        """Compose the metrics screen"""
        yield Header()

        with Container():
            with Vertical():
                yield Static("[bold]System Statistics[/bold]", id="metrics-title")

                with Horizontal(id="stats-container"):
                    yield Static("Loading...", id="stats-summary")
                    yield Static("", id="stats-details")

                yield Static("[bold]Agent Metrics[/bold]", id="agent-title")
                yield DataTable(id="agent-table")

        yield Footer()

    def on_mount(self):
        """Setup when screen mounts"""
        # Setup agent table
        table = self.query_one("#agent-table", DataTable)
        table.add_columns("Agent", "Calls", "Tokens", "Cost", "Avg Latency")
        table.zebra_stripes = True

        # Start refresh cycle
        self.set_interval(2.0, self.refresh_data)
        self.refresh_data()

    async def refresh_data(self):
        """Refresh metrics data"""
        try:
            # Get system stats
            stats = await self.provider.get_system_stats()

            # Update stats summary
            summary = self.query_one("#stats-summary", Static)
            summary_text = f"""
[bold]Total Builds:[/bold] {stats.total_builds}
[bold]Active:[/bold] {stats.active_builds}
[bold]Completed:[/bold] {stats.completed_builds}
[bold]Failed:[/bold] {stats.failed_builds}
"""
            summary.update(summary_text)

            # Update stats details
            details = self.query_one("#stats-details", Static)
            details_text = f"""
[bold]Total Tokens:[/bold] {stats.total_tokens_used:,}
[bold]Total Cost:[/bold] ${stats.total_cost_usd:.2f}
[bold]Avg Duration:[/bold] {stats.avg_build_duration_minutes:.1f}m
"""
            details.update(details_text)

            # Get agent metrics
            agents = await self.provider.get_agent_metrics()
            table = self.query_one("#agent-table", DataTable)
            table.clear()

            if agents:
                for agent in agents:
                    table.add_row(
                        agent.agent_name,
                        str(agent.total_calls),
                        f"{agent.tokens_used:,}",
                        f"${agent.cost_usd:.2f}",
                        f"{agent.avg_latency_ms:.0f}ms"
                    )
            else:
                table.add_row("—", "No agent data available", "—", "—", "—")

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

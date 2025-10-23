"""Log viewer widget"""

from textual.widgets import RichLog
from typing import List


class LogViewerWidget(RichLog):
    """Display build logs with rich formatting"""

    def __init__(self, **kwargs):
        super().__init__(
            max_lines=1000,
            highlight=True,
            markup=True,
            **kwargs
        )

    def add_log(self, message: str, level: str = "info"):
        """Add log message with styling"""
        styles = {
            "info": ("[blue]ℹ[/blue]", ""),
            "success": ("[green]✓[/green]", "green"),
            "warning": ("[yellow]⚠[/yellow]", "yellow"),
            "error": ("[red]✗[/red]", "red"),
            "debug": ("[dim]•[/dim]", "dim"),
        }

        icon, color = styles.get(level, ("[blue]•[/blue]", ""))

        if color:
            self.write(f"{icon} [{color}]{message}[/{color}]")
        else:
            self.write(f"{icon} {message}")

    def add_logs(self, messages: List[str], level: str = "info"):
        """Add multiple log messages"""
        for msg in messages:
            self.add_log(msg, level)

    def clear_logs(self):
        """Clear all logs"""
        self.clear()

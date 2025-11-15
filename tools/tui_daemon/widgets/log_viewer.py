"""
Log Viewer Widget - RichLog with syntax highlighting

Displays logs with color coding by level and supports:
- Auto-scroll toggle
- Log level filtering
- Search functionality
"""

from typing import List, Optional
from textual.widgets import RichLog, Static
from textual.containers import Vertical
from textual.reactive import reactive

from ..daemon_client import LogEntry
from ..log_streamer import LogStreamer


class LogViewer(Vertical):
    """
    Log viewer with RichLog display and controls.

    Features:
    - Color-coded log levels
    - Auto-scroll toggle
    - Log level filtering (ALL/INFO/WARNING/ERROR)
    - Line numbers with timestamps
    """

    auto_scroll = reactive(True)
    filter_level = reactive("ALL")

    def __init__(self, **kwargs):
        """Initialize the log viewer"""
        super().__init__(**kwargs)
        self._log_display: Optional[RichLog] = None
        self._logs: List[LogEntry] = []

    def compose(self):
        """Compose the widget layout"""
        # Controls
        yield Static("[A] Toggle Auto-scroll | [F] Filter: ALL", id="log-controls")

        # Log display
        self._log_display = RichLog(highlight=True, markup=True, wrap=True)
        yield self._log_display

    def append_logs(self, logs: List[LogEntry]) -> None:
        """
        Append new logs to the display.

        Args:
            logs: List of LogEntry objects to append
        """
        if not self._log_display:
            return

        # Filter logs by level
        filtered_logs = [log for log in logs if self._should_show_log(log)]

        # Append to display
        for log in filtered_logs:
            formatted = LogStreamer.format_log(log)
            self._log_display.write(formatted)

        # Auto-scroll to bottom
        if self.auto_scroll:
            self._log_display.scroll_end()

        # Store logs
        self._logs.extend(logs)

    def clear(self) -> None:
        """Clear all logs"""
        if self._log_display:
            self._log_display.clear()
        self._logs = []

    def toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll on/off"""
        self.auto_scroll = not self.auto_scroll

    def set_filter_level(self, level: str) -> None:
        """
        Set log level filter.

        Args:
            level: One of: ALL, INFO, WARNING, ERROR
        """
        self.filter_level = level

        # Refresh display with new filter
        self._refresh_display()

    def _should_show_log(self, log: LogEntry) -> bool:
        """Check if log should be shown based on filter"""
        if self.filter_level == "ALL":
            return True
        elif self.filter_level == "INFO":
            return log.level in ["INFO", "SUCCESS"]
        elif self.filter_level == "WARNING":
            return log.level == "WARNING"
        elif self.filter_level == "ERROR":
            return log.level == "ERROR"
        return True

    def _refresh_display(self) -> None:
        """Refresh display with current filter"""
        if not self._log_display:
            return

        # Clear and re-add filtered logs
        self._log_display.clear()

        for log in self._logs:
            if self._should_show_log(log):
                formatted = LogStreamer.format_log(log)
                self._log_display.write(formatted)

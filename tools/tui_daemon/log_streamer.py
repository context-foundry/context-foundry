"""
Log Streamer - Real-time log polling from SQLite

Polls the logs table every 500ms and provides formatted log entries
with syntax highlighting for different log levels.
"""

import asyncio
from datetime import datetime
from typing import Callable, List, Optional
from rich.text import Text

from .daemon_client import DaemonClient, LogEntry


class LogStreamer:
    """
    Real-time log streaming from SQLite database.

    Polls the logs table at regular intervals and calls a callback
    with new log entries. Supports color formatting and auto-scroll.
    """

    # Color scheme for log levels
    LEVEL_COLORS = {
        "INFO": "cyan",
        "SUCCESS": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "DEBUG": "dim white",
    }

    def __init__(self, daemon_client: DaemonClient, poll_interval: float = 0.5):
        """
        Initialize the log streamer.

        Args:
            daemon_client: Connected DaemonClient instance
            poll_interval: Polling interval in seconds (default 500ms)
        """
        self.daemon_client = daemon_client
        self.poll_interval = poll_interval
        self._streaming = False
        self._current_job_id: Optional[str] = None
        self._last_timestamp: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self._callback: Optional[Callable[[List[LogEntry]], None]] = None

    def start_streaming(
        self, job_id: str, callback: Callable[[List[LogEntry]], None]
    ) -> None:
        """
        Start streaming logs for a job.

        Args:
            job_id: Job UUID to stream logs for
            callback: Function to call with new log entries
        """
        if self._streaming:
            self.stop_streaming()

        self._current_job_id = job_id
        self._callback = callback
        self._last_timestamp = None
        self._streaming = True

        # Start the polling task
        self._task = asyncio.create_task(self._poll_loop())

    def stop_streaming(self) -> None:
        """Stop the log streaming."""
        self._streaming = False
        if self._task:
            self._task.cancel()
            self._task = None
        self._current_job_id = None
        self._callback = None
        self._last_timestamp = None

    async def _poll_loop(self) -> None:
        """Internal polling loop that runs every poll_interval."""
        while self._streaming:
            try:
                new_logs = self.get_new_logs()
                if new_logs and self._callback:
                    self._callback(new_logs)

                    # Update last timestamp
                    self._last_timestamp = new_logs[-1].timestamp

                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Continue polling even on errors
                await asyncio.sleep(self.poll_interval)

    def get_new_logs(self) -> List[LogEntry]:
        """
        Query for new logs since last timestamp.

        Returns:
            List of new LogEntry objects
        """
        if not self._current_job_id:
            return []

        return self.daemon_client.get_logs(
            self._current_job_id, since_timestamp=self._last_timestamp
        )

    @classmethod
    def format_log(
        cls, log_entry: LogEntry, show_timestamp: bool = True, show_phase: bool = True
    ) -> Text:
        """
        Format a log entry with colors.

        Args:
            log_entry: LogEntry to format
            show_timestamp: Include timestamp in output
            show_phase: Include phase in output

        Returns:
            Rich Text object with formatting
        """
        text = Text()

        # Timestamp
        if show_timestamp:
            timestamp_str = log_entry.timestamp.strftime("%H:%M:%S")
            text.append(f"[{timestamp_str}] ", style="dim")

        # Level with color
        level_color = cls.LEVEL_COLORS.get(log_entry.level, "white")
        text.append(f"[{log_entry.level}]", style=f"bold {level_color}")
        text.append(" ")

        # Phase (if available)
        if show_phase and log_entry.phase:
            text.append(f"({log_entry.phase}) ", style="blue")

        # Message
        text.append(log_entry.message, style=level_color)

        return text

    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming"""
        return self._streaming

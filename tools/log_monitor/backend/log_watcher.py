"""
Log file watcher using watchdog
Monitors log files for changes and emits parsed entries
"""

import asyncio
import glob
from pathlib import Path
from typing import Dict, Callable, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from .parsers import LogParser


class LogFileHandler(FileSystemEventHandler):
    """Handle file system events for log files"""

    def __init__(
        self,
        callback: Callable,
        parser: LogParser,
        server_name: str,
        debounce_ms: int = 100,
    ):
        self.callback = callback
        self.parser = parser
        self.server_name = server_name
        self.debounce_ms = debounce_ms
        self.file_positions: Dict[str, int] = {}
        self.pending_events: Dict[str, asyncio.Task] = {}

    def on_modified(self, event):
        """Handle file modification"""
        if event.is_directory:
            return

        if isinstance(event, (FileModifiedEvent, FileCreatedEvent)):
            self._schedule_read(event.src_path)

    def on_created(self, event):
        """Handle file creation"""
        if event.is_directory:
            return

        if isinstance(event, FileCreatedEvent):
            # New file - start from beginning
            self.file_positions[event.src_path] = 0
            self._schedule_read(event.src_path)

    def _schedule_read(self, file_path: str):
        """Schedule file read with debouncing"""
        # Cancel pending read if exists
        if file_path in self.pending_events:
            self.pending_events[file_path].cancel()

        # Schedule new read after debounce delay
        loop = asyncio.get_event_loop()
        self.pending_events[file_path] = loop.call_later(
            self.debounce_ms / 1000.0,
            lambda: asyncio.create_task(self._read_new_content(file_path)),
        )

    async def _read_new_content(self, file_path: str):
        """Read new content from file since last read"""
        try:
            # Get last position (0 if new file)
            last_pos = self.file_positions.get(file_path, 0)

            # Read new content
            with open(file_path, "r") as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                new_pos = f.tell()

            # Update position
            self.file_positions[file_path] = new_pos

            # Parse and emit entries
            for line in new_lines:
                if line.strip():
                    entry = self.parser.parse(line, self.server_name)
                    if entry:
                        await self.callback(entry)

        except (IOError, OSError) as e:
            # File might not exist or be readable - log but don't crash
            print(f"Warning: Could not read {file_path}: {e}")


class LogFileWatcher:
    """
    Watch log files for changes and emit parsed entries.

    Uses watchdog library for efficient file system monitoring.
    """

    def __init__(
        self, parser: LogParser, broadcast_callback: Callable, debounce_ms: int = 100
    ):
        """
        Initialize log file watcher.

        Args:
            parser: LogParser instance
            broadcast_callback: Async function to call with parsed LogEntry
            debounce_ms: Debounce delay in milliseconds
        """
        self.parser = parser
        self.broadcast_callback = broadcast_callback
        self.debounce_ms = debounce_ms
        self.observer = Observer()
        self.handlers: Dict[str, LogFileHandler] = {}
        self.watched_paths: Set[str] = set()

    def start_watching(self, sources: list):
        """
        Start watching log sources.

        Args:
            sources: List of LogSourceConfig objects
        """
        for source in sources:
            for pattern in source.paths:
                self._watch_pattern(pattern, source.name)

        # Start observer
        if not self.observer.is_alive():
            self.observer.start()

    def _watch_pattern(self, pattern: str, server_name: str):
        """Watch files matching a glob pattern"""
        # Expand user home directory
        pattern = str(Path(pattern).expanduser())

        # Find existing files
        existing_files = glob.glob(pattern)

        if not existing_files:
            print(f"Warning: No files found for pattern: {pattern}")
            return

        for file_path in existing_files:
            self._watch_file(file_path, server_name)

    def _watch_file(self, file_path: str, server_name: str):
        """Watch a specific file"""
        file_path = str(Path(file_path).absolute())

        if file_path in self.watched_paths:
            return  # Already watching

        # Create handler
        handler = LogFileHandler(
            callback=self.broadcast_callback,
            parser=self.parser,
            server_name=server_name,
            debounce_ms=self.debounce_ms,
        )

        # Watch parent directory (watchdog requirement)
        watch_dir = str(Path(file_path).parent)

        # Schedule observer
        self.observer.schedule(handler, watch_dir, recursive=False)

        # Track
        self.watched_paths.add(file_path)
        self.handlers[file_path] = handler

        # Read existing content (tail last 100 lines)
        asyncio.create_task(self._read_existing_content(file_path, server_name))

        print(f"Watching: {file_path} (server: {server_name})")

    async def _read_existing_content(
        self, file_path: str, server_name: str, lines: int = 100
    ):
        """Read last N lines from existing file"""
        try:
            with open(file_path, "r") as f:
                # Read all lines
                all_lines = f.readlines()

                # Get last N lines
                recent_lines = (
                    all_lines[-lines:] if len(all_lines) > lines else all_lines
                )

                # Update file position to end
                self.handlers[file_path].file_positions[file_path] = f.tell()

                # Parse and emit
                for line in recent_lines:
                    if line.strip():
                        entry = self.parser.parse(line, server_name)
                        if entry:
                            await self.broadcast_callback(entry)

        except (IOError, OSError) as e:
            print(f"Warning: Could not read existing content from {file_path}: {e}")

    def stop_watching(self):
        """Stop watching all files"""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

        self.watched_paths.clear()
        self.handlers.clear()

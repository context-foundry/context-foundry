"""
File system watcher for .context-foundry directory.

Monitors changes to session files and triggers SSE events.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Set
from datetime import datetime
from threading import Timer

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .broadcaster import Broadcaster
from .session_parser import SessionParser

logger = logging.getLogger(__name__)


class PhaseFileHandler(FileSystemEventHandler):
    """
    Watchdog handler for Context Foundry session files.

    Monitors:
    - current-phase.json → phase_update events
    - session-summary.json → file_created events
    """

    def __init__(
        self,
        broadcaster: Broadcaster,
        session_parser: SessionParser,
        job_id: str,
        debounce_seconds: float = 0.5,
    ):
        """
        Initialize file handler.

        Args:
            broadcaster: SSE broadcaster instance
            session_parser: Session file parser
            job_id: Current job ID
            debounce_seconds: Debounce delay for file changes
        """
        super().__init__()
        self.broadcaster = broadcaster
        self.session_parser = session_parser
        self.job_id = job_id
        self.debounce_seconds = debounce_seconds

        # Debounce timers
        self._phase_timer: Optional[Timer] = None
        self._summary_timer: Optional[Timer] = None

        # Track previous file list for diffing
        self._previous_files: Set[str] = set()

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        file_name = file_path.name

        if file_name == "current-phase.json":
            self._handle_phase_update()
        elif file_name == "session-summary.json":
            self._handle_summary_update()

    def _handle_phase_update(self):
        """Handle current-phase.json modification with debouncing."""
        # Cancel existing timer
        if self._phase_timer:
            self._phase_timer.cancel()

        # Schedule new broadcast
        self._phase_timer = Timer(self.debounce_seconds, self._broadcast_phase)
        self._phase_timer.start()

    def _broadcast_phase(self):
        """Read phase file and broadcast update."""
        phase_data = self.session_parser.read_current_phase(self.job_id)

        if not phase_data:
            return

        event = {
            "type": "phase_update",
            "data": {
                "phase": phase_data.get("phase"),
                "status": phase_data.get("status"),
                "description": phase_data.get("description", ""),
            },
        }

        # Broadcast to job-specific channel
        channel = f"job:{self.job_id}"
        asyncio.run(self.broadcaster.publish(channel, event))

        logger.info(f"Broadcast phase update: {event['data']}")

    def _handle_summary_update(self):
        """Handle session-summary.json modification with debouncing."""
        # Cancel existing timer
        if self._summary_timer:
            self._summary_timer.cancel()

        # Schedule new broadcast
        self._summary_timer = Timer(self.debounce_seconds, self._broadcast_file_changes)
        self._summary_timer.start()

    def _broadcast_file_changes(self):
        """Detect new files and broadcast file_created events."""
        current_files = set(self.session_parser.get_files_created())

        # Detect new files
        new_files = current_files - self._previous_files

        if new_files:
            for file_path in new_files:
                event = {
                    "type": "file_created",
                    "data": {
                        "path": file_path,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    },
                }

                channel = f"job:{self.job_id}"
                asyncio.run(self.broadcaster.publish(channel, event))

                logger.info(f"Broadcast file created: {file_path}")

        # Update previous files
        self._previous_files = current_files


class FileWatcher:
    """
    Manages file system watching for Context Foundry builds.

    Creates and manages watchdog observers for active jobs.
    """

    def __init__(
        self,
        broadcaster: Broadcaster,
        watch_path: Path,
        debounce_seconds: float = 0.5,
    ):
        """
        Initialize file watcher.

        Args:
            broadcaster: SSE broadcaster instance
            watch_path: Path to .context-foundry directory
            debounce_seconds: Debounce delay
        """
        self.broadcaster = broadcaster
        self.watch_path = watch_path
        self.debounce_seconds = debounce_seconds
        self.session_parser = SessionParser(watch_path)

        # Active observers by job_id
        self._observers: dict[str, Observer] = {}

    def start_watching(self, job_id: str):
        """
        Start watching for a specific job.

        Args:
            job_id: Job UUID to watch
        """
        if job_id in self._observers:
            logger.warning(f"Already watching job {job_id}")
            return

        # Create handler
        handler = PhaseFileHandler(
            broadcaster=self.broadcaster,
            session_parser=self.session_parser,
            job_id=job_id,
            debounce_seconds=self.debounce_seconds,
        )

        # Create and start observer
        observer = Observer()
        observer.schedule(handler, str(self.watch_path), recursive=False)
        observer.start()

        self._observers[job_id] = observer
        logger.info(f"Started watching {self.watch_path} for job {job_id}")

    def stop_watching(self, job_id: str):
        """
        Stop watching for a specific job.

        Args:
            job_id: Job UUID
        """
        observer = self._observers.pop(job_id, None)

        if observer:
            observer.stop()
            observer.join(timeout=2.0)
            logger.info(f"Stopped watching for job {job_id}")

    def stop_all(self):
        """Stop all active observers."""
        for job_id in list(self._observers.keys()):
            self.stop_watching(job_id)

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
        self._markdown_timers: dict[str, Optional[Timer]] = {}

        # Track previous file list for diffing
        # Initialize with existing files to prevent re-broadcasting
        existing_files = session_parser.get_files_created()
        self._previous_files: Set[str] = set(existing_files)

        # Track markdown files to prevent duplicate broadcasts
        self._markdown_files: Set[str] = set()

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
        elif file_name.endswith(".md"):
            self._handle_markdown_update(file_path)

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        file_name = file_path.name

        if file_name.endswith(".md"):
            self._handle_markdown_update(file_path)

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
        """Detect new files and broadcast file_created + metrics_update events."""
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

        # Broadcast metrics update
        self._broadcast_metrics()

    def _broadcast_metrics(self):
        """Calculate and broadcast cumulative metrics from session-summary.json."""
        summary = self.session_parser.read_session_summary()

        if not summary:
            return

        # Calculate cumulative metrics
        total_tokens = 0
        total_duration = 0

        context_metrics = summary.get("context_metrics", {})
        by_phase = context_metrics.get("by_phase", {})

        for phase_name, phase_data in by_phase.items():
            total_tokens += phase_data.get("tokens_used", 0)
            total_duration += phase_data.get("duration_seconds", 0)

        # Get file count
        files_count = len(self._previous_files)

        event = {
            "type": "metrics_update",
            "data": {
                "tokens_used": total_tokens,
                "duration": int(total_duration),
                "files": files_count,
            },
        }

        channel = f"job:{self.job_id}"
        asyncio.run(self.broadcaster.publish(channel, event))

        logger.info(
            f"Broadcast metrics: {total_tokens} tokens, {int(total_duration)}s, {files_count} files"
        )

    def _handle_markdown_update(self, file_path: Path):
        """Handle markdown file creation/modification with debouncing."""
        file_name = file_path.name

        # Cancel existing timer for this file
        if file_name in self._markdown_timers and self._markdown_timers[file_name]:
            self._markdown_timers[file_name].cancel()

        # Schedule new broadcast
        self._markdown_timers[file_name] = Timer(
            self.debounce_seconds, lambda: self._broadcast_markdown(file_path)
        )
        self._markdown_timers[file_name].start()

    def _broadcast_markdown(self, file_path: Path):
        """Read markdown file and broadcast update."""
        file_name = file_path.name

        # Check if file exists and is readable
        if not file_path.exists():
            return

        try:
            stat = file_path.stat()

            # Determine if this is a new file or update
            is_new = file_name not in self._markdown_files
            self._markdown_files.add(file_name)

            event = {
                "type": "markdown_update",
                "data": {
                    "name": file_name,
                    "path": str(file_path.relative_to(file_path.parent.parent)),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "is_new": is_new,
                },
            }

            # Broadcast to job-specific channel
            channel = f"job:{self.job_id}"
            asyncio.run(self.broadcaster.publish(channel, event))

            logger.info(f"Broadcast markdown update: {file_name} (new={is_new})")
        except Exception as e:
            logger.error(f"Error broadcasting markdown file {file_path}: {e}")


class FileWatcher:
    """
    Manages file system watching for Context Foundry builds.

    Creates and manages watchdog observers for active jobs.
    """

    def __init__(
        self,
        broadcaster: Broadcaster,
        store_service,
        debounce_seconds: float = 0.5,
    ):
        """
        Initialize file watcher.

        Args:
            broadcaster: SSE broadcaster instance
            store_service: StoreService instance to look up job directories
            debounce_seconds: Debounce delay
        """
        self.broadcaster = broadcaster
        self.store_service = store_service
        self.debounce_seconds = debounce_seconds

        # Active observers and parsers by job_id
        self._observers: dict[str, Observer] = {}
        self._parsers: dict[str, SessionParser] = {}

        # Track job status for change detection
        self._job_statuses: dict[str, str] = {}
        self._status_poll_tasks: dict[str, asyncio.Task] = {}

        # Track last seen log (timestamp, id) tuple for incremental fetches
        self._last_log_positions: dict[str, tuple[str, str]] = {}
        self._log_poll_tasks: dict[str, asyncio.Task] = {}

    async def _send_initial_metrics(self, job_id: str):
        """Send initial metrics snapshot when user subscribes."""
        parser = self._parsers.get(job_id)
        total_tokens = 0
        total_duration = 0
        files_count = 0

        # Read from session summary file (primary source of truth)
        if parser:
            summary = parser.read_session_summary()
            if summary:
                context_metrics = summary.get("context_metrics", {})
                by_phase = context_metrics.get("by_phase", {})

                for phase_name, phase_data in by_phase.items():
                    total_tokens += phase_data.get("tokens_used", 0)
                    total_duration += phase_data.get("duration_seconds", 0)

                files_count = len(summary.get("files_created", []))
                logger.info(
                    f"Loaded metrics from session-summary.json: {total_tokens} tokens, {files_count} files"
                )

        # Send metrics even if zero (user should see the initialized state)
        event = {
            "type": "metrics_update",
            "data": {
                "tokens_used": total_tokens,
                "duration": int(total_duration),
                "files": files_count,
            },
        }

        channel = f"job:{job_id}"
        await self.broadcaster.publish(channel, event)
        logger.info(
            f"Sent initial metrics: {total_tokens} tokens, {int(total_duration)}s, {files_count} files"
        )

    async def _send_initial_files(self, job_id: str):
        """Send initial file snapshot when user subscribes."""
        parser = self._parsers.get(job_id)

        if not parser:
            logger.warning(f"No parser available for job {job_id}")
            return

        # Get existing files from session summary
        existing_files = parser.get_files_created()

        if not existing_files:
            logger.debug(f"No existing files found for job {job_id}")
            return

        # Update PhaseFileHandler's _previous_files to prevent duplicates
        # when the file watcher detects subsequent changes
        handler = None
        observer = self._observers.get(job_id)
        if observer and hasattr(observer, "_handlers"):
            # Find the PhaseFileHandler from the observer's handlers
            for h in observer._handlers.values():
                for event_handler in h:
                    if hasattr(event_handler, "_previous_files"):
                        handler = event_handler
                        break

        if handler:
            handler._previous_files.update(existing_files)
            logger.info(
                f"Updated _previous_files with {len(existing_files)} existing files"
            )

        # Broadcast each file as file_created event
        channel = f"job:{job_id}"
        for file_path in existing_files:
            event = {
                "type": "file_created",
                "data": {
                    "path": file_path,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            }
            await self.broadcaster.publish(channel, event)

        logger.info(f"Sent {len(existing_files)} initial files for job {job_id}")

    def start_watching(self, job_id: str):
        """
        Start watching for a specific job.

        Args:
            job_id: Job UUID to watch
        """
        if job_id in self._observers:
            logger.warning(f"Already watching job {job_id}")
            return

        # Get working directory for this job
        working_dir = self.store_service.get_job_working_directory(job_id)
        if not working_dir:
            logger.error(f"Cannot watch job {job_id}: no working_directory in database")
            return

        # Build path to .context-foundry directory
        watch_path = Path(working_dir) / ".context-foundry"
        if not watch_path.exists():
            logger.warning(f"Watch path does not exist yet: {watch_path}")
            # Don't return - the directory will be created by the build
            # We'll start watching the parent and wait for it

        # Create session parser for this job's directory
        session_parser = SessionParser(watch_path)
        self._parsers[job_id] = session_parser

        # Create handler
        handler = PhaseFileHandler(
            broadcaster=self.broadcaster,
            session_parser=session_parser,
            job_id=job_id,
            debounce_seconds=self.debounce_seconds,
        )

        # Create and start observer
        observer = Observer()
        try:
            observer.schedule(handler, str(watch_path), recursive=False)
            observer.start()
            self._observers[job_id] = observer
            logger.info(f"Started watching {watch_path} for job {job_id}")
        except FileNotFoundError:
            # Directory doesn't exist yet, watch parent directory
            parent_dir = Path(working_dir)
            if parent_dir.exists():
                observer.schedule(handler, str(parent_dir), recursive=True)
                observer.start()
                self._observers[job_id] = observer
                logger.info(
                    f"Started watching {parent_dir} (recursive) for job {job_id}, waiting for .context-foundry"
                )

        # Start status polling
        self._start_status_polling(job_id)

        # Start log polling
        self._start_log_polling(job_id)

        # Send initial metrics snapshot (async task)
        asyncio.create_task(self._send_initial_metrics(job_id))

        # Send initial files snapshot (async task)
        asyncio.create_task(self._send_initial_files(job_id))

    def stop_watching(self, job_id: str):
        """
        Stop watching for a specific job.

        Args:
            job_id: Job UUID
        """
        observer = self._observers.pop(job_id, None)
        self._parsers.pop(job_id, None)

        # Stop status polling
        self._stop_status_polling(job_id)

        # Stop log polling
        self._stop_log_polling(job_id)

        if observer:
            observer.stop()
            observer.join(timeout=2.0)
            logger.info(f"Stopped watching for job {job_id}")

    async def _poll_job_status(self, job_id: str):
        """
        Periodically poll database for job status changes.

        Args:
            job_id: Job UUID to monitor
        """
        poll_interval = 5  # seconds

        while job_id in self._observers:
            try:
                await asyncio.sleep(poll_interval)

                # Get current job from database
                job = self.store_service.get_job(job_id)
                if not job:
                    logger.warning(f"Job {job_id} not found in database")
                    break

                current_status = job.status
                previous_status = self._job_statuses.get(job_id)

                # Detect status change
                if current_status and current_status != previous_status:
                    self._job_statuses[job_id] = current_status

                    # Broadcast status change event
                    event = {
                        "type": "job_status_change",
                        "data": {
                            "status": current_status,
                        },
                    }

                    channel = f"job:{job_id}"
                    await self.broadcaster.publish(channel, event)

                    logger.info(
                        f"Job {job_id} status changed: {previous_status} → {current_status}"
                    )

                    # Stop polling if job is terminal (succeeded, failed, cancelled)
                    if current_status in ("succeeded", "failed", "cancelled"):
                        break

            except asyncio.CancelledError:
                logger.info(f"Status polling cancelled for job {job_id}")
                break
            except Exception as e:
                logger.error(f"Error polling status for job {job_id}: {e}")

    def _start_status_polling(self, job_id: str):
        """Start async status polling task for a job."""
        if job_id in self._status_poll_tasks:
            return

        # Create and store the task
        try:
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._poll_job_status(job_id))
            self._status_poll_tasks[job_id] = task
        except RuntimeError:
            # No event loop running, skip polling for now
            logger.warning(
                f"Cannot start status polling for job {job_id}: no event loop"
            )
            return

        # Initialize current status
        job = self.store_service.get_job(job_id)
        if job:
            self._job_statuses[job_id] = job.status

        logger.info(f"Started status polling for job {job_id}")

    def _stop_status_polling(self, job_id: str):
        """Stop status polling task for a job."""
        task = self._status_poll_tasks.pop(job_id, None)
        self._job_statuses.pop(job_id, None)

        if task:
            task.cancel()
            logger.info(f"Stopped status polling for job {job_id}")

    async def _poll_job_logs(self, job_id: str):
        """
        Periodically poll database for new logs.

        Args:
            job_id: Job UUID to monitor
        """
        poll_interval = 2  # seconds (faster than status polling for real-time logs)
        batch_size = 50  # Maximum logs per batch

        while job_id in self._observers:
            try:
                await asyncio.sleep(poll_interval)

                # Get last seen position (timestamp, id) tuple
                last_position = self._last_log_positions.get(job_id)
                since_timestamp = last_position[0] if last_position else None
                since_id = last_position[1] if last_position else None

                # Fetch new logs from database
                logs, _ = self.store_service.get_logs(
                    job_id=job_id,
                    since_timestamp=since_timestamp,
                    since_id=since_id,
                    limit=batch_size,
                )

                if logs:
                    # Update last seen position to (max_timestamp, last_id_at_max_timestamp)
                    # Sort logs by timestamp to find the max
                    sorted_logs = sorted(logs, key=lambda log: (log.timestamp, log.id))
                    last_log = sorted_logs[-1]
                    self._last_log_positions[job_id] = (last_log.timestamp, last_log.id)

                    # Convert Log models to dict for JSON serialization
                    log_dicts = [
                        {
                            "id": log.id,
                            "job_id": log.job_id,
                            "timestamp": log.timestamp,
                            "level": log.level,
                            "message": log.message,
                        }
                        for log in logs
                    ]

                    # Broadcast log batch event
                    event = {
                        "type": "log_batch",
                        "data": {
                            "logs": log_dicts,
                        },
                    }

                    channel = f"job:{job_id}"
                    await self.broadcaster.publish(channel, event)

                    logger.debug(
                        f"Broadcast {len(logs)} new logs for job {job_id} (since {last_position})"
                    )

            except asyncio.CancelledError:
                logger.info(f"Log polling cancelled for job {job_id}")
                break
            except Exception as e:
                logger.error(f"Error polling logs for job {job_id}: {e}")

    def _start_log_polling(self, job_id: str):
        """Start async log polling task for a job."""
        if job_id in self._log_poll_tasks:
            return

        # Create and store the task
        try:
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._poll_job_logs(job_id))
            self._log_poll_tasks[job_id] = task
        except RuntimeError:
            # No event loop running, skip polling for now
            logger.warning(f"Cannot start log polling for job {job_id}: no event loop")
            return

        # Don't initialize last_log_positions - None means fetch all logs from beginning

        logger.info(f"Started log polling for job {job_id}")

    def _stop_log_polling(self, job_id: str):
        """Stop log polling task for a job."""
        task = self._log_poll_tasks.pop(job_id, None)
        self._last_log_positions.pop(job_id, None)

        if task:
            task.cancel()
            logger.info(f"Stopped log polling for job {job_id}")

    def stop_all(self):
        """Stop all active observers and polling tasks."""
        for job_id in list(self._observers.keys()):
            self.stop_watching(job_id)

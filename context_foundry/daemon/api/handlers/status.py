"""
Status and SSE event streaming API handlers.

Handles status endpoints and Server-Sent Events for real-time updates.
"""

import json
import logging
import time
from datetime import datetime
from queue import Empty

from .base import HandlerMixin

logger = logging.getLogger(__name__)


class StatusHandlersMixin(HandlerMixin):
    """Mixin providing status and SSE handler methods."""

    def handle_status(self) -> None:
        """Serve current status as JSON."""
        from .. import utils

        payload = utils.build_status_payload(
            self.server.context.job_manager, self.server.context.store
        )
        self.send_json_response(payload)

    def handle_events(self) -> None:
        """
        Stream events via SSE using the event bus.

        Uses a hybrid approach:
        - Subscribes to event bus for real-time job updates
        - Sends heartbeats every 15 seconds to keep connection alive
        - Falls back to full status updates every 30 seconds for sync
        """
        from ..events import get_event_bus
        from .. import utils

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Subscribe to the event bus
        event_bus = get_event_bus()
        subscriber_id, event_queue = event_bus.subscribe(include_recent=False)

        try:
            # Send initial full status payload
            payload = utils.build_status_payload(
                self.server.context.job_manager, self.server.context.store
            )
            initial_message = f"data: {json.dumps(payload)}\n\n"
            self.wfile.write(initial_message.encode("utf-8"))
            self.wfile.flush()

            last_heartbeat = time.time()
            last_full_sync = time.time()
            heartbeat_interval = 15.0
            full_sync_interval = 30.0

            while not self.server.context.stop_event.is_set():
                try:
                    # Try to get an event from the queue
                    try:
                        event = event_queue.get(timeout=1.0)
                        event_data = event.to_dict()
                        message = f"data: {json.dumps(event_data)}\n\n"
                        self.wfile.write(message.encode("utf-8"))
                        self.wfile.flush()
                    except Empty:
                        pass

                    now = time.time()

                    # Send heartbeat periodically
                    if now - last_heartbeat >= heartbeat_interval:
                        heartbeat_data = {
                            "type": "heartbeat",
                            "timestamp": datetime.now().isoformat(),
                        }
                        heartbeat_message = f"data: {json.dumps(heartbeat_data)}\n\n"
                        self.wfile.write(heartbeat_message.encode("utf-8"))
                        self.wfile.flush()
                        last_heartbeat = now

                    # Send full sync periodically
                    if now - last_full_sync >= full_sync_interval:
                        payload = utils.build_status_payload(
                            self.server.context.job_manager, self.server.context.store
                        )
                        sync_message = f"data: {json.dumps(payload)}\n\n"
                        self.wfile.write(sync_message.encode("utf-8"))
                        self.wfile.flush()
                        last_full_sync = now

                except Exception as e:
                    logger.debug(f"SSE event loop error: {e}")
                    break

        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            logger.warning("Dashboard SSE loop error: %s", exc)
        finally:
            event_bus.unsubscribe(subscriber_id)

    def handle_agent_activity(self, query: str) -> None:
        """SSE endpoint for real-time agent activity during phase execution."""
        from urllib.parse import parse_qs
        from ..models import JobStatus

        params = parse_qs(query)

        if not self.check_auth_with_query(query):
            self.send_error(401, "Unauthorized: missing or invalid auth token")
            return

        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_error(400, "Missing 'job_id' parameter")
            return

        job = self.server.context.store.get_job(job_id)
        if not job:
            self.send_error(404, f"Job not found: {job_id}")
            return

        working_dir = job.params.get("working_directory")
        if not working_dir:
            self.send_error(400, "No working directory for job")
            return

        self.send_sse_headers()

        try:
            while not self.server.context.stop_event.is_set():
                job = self.server.context.store.get_job(job_id)
                if job and job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                    self.send_sse_event(
                        "complete", {"job_id": job_id, "status": job.status.value}
                    )
                    break

                self.send_sse_event("heartbeat", {"job_id": job_id})
                time.sleep(2)

        except (BrokenPipeError, ConnectionResetError):
            pass

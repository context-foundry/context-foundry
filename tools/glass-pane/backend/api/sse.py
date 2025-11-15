"""
Server-Sent Events (SSE) endpoints for real-time updates.
"""

import asyncio
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from services.broadcaster import broadcaster
from services.file_watcher import FileWatcher
from services.store_service import StoreService
from config import settings

router = APIRouter(prefix="/sse", tags=["sse"])
logger = logging.getLogger(__name__)

# Initialize services
store = StoreService(settings.expanded_db_path)
file_watcher = FileWatcher(
    broadcaster=broadcaster,
    store_service=store,
    debounce_seconds=settings.debounce_seconds,
)


@router.get("/jobs/{job_id}/updates")
async def stream_job_updates(job_id: str, request: Request):
    """
    Server-Sent Events stream for real-time job updates.

    Path Parameters:
    - job_id: Job UUID to subscribe to

    Event Types:
    - phase_update: Phase changed
    - file_created: New file detected
    - log_batch: New logs (batched)
    - metrics_update: Token/duration/files updated
    - job_status_change: Job status changed
    - heartbeat: Keep-alive ping (every 30s)

    Example Event:
    ```
    event: phase_update
    data: {"phase": "Builder", "status": "building", "description": "Creating components"}
    ```
    """
    # Verify job exists
    job = store.get_job(job_id)
    if not job:
        logger.warning(f"SSE connection attempted for non-existent job: {job_id}")
        return EventSourceResponse(
            _error_event_generator(f"Job {job_id} not found"),
            status_code=404,
        )

    logger.info(f"SSE connection established for job {job_id}")

    # Start watching files for this job
    file_watcher.start_watching(job_id)

    # Create event generator
    async def event_generator():
        """Generate SSE events from broadcaster."""
        channel = f"job:{job_id}"
        heartbeat_task = None

        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(_heartbeat_sender(channel))

            # Subscribe to events
            async for event in broadcaster.subscribe(channel):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from job {job_id}")
                    break

                # Yield event to client
                yield {
                    "event": event["type"],
                    "data": json.dumps(event["data"]),
                }

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for job {job_id}")

        finally:
            # Clean up heartbeat task
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

            # Stop watching files for this job
            file_watcher.stop_watching(job_id)

            logger.info(f"SSE connection closed for job {job_id}")

    return EventSourceResponse(event_generator())


async def _heartbeat_sender(channel: str):
    """
    Send periodic heartbeat events to keep connection alive.

    Args:
        channel: Channel to send heartbeats to
    """
    while True:
        await asyncio.sleep(settings.heartbeat_interval)

        event = {
            "type": "heartbeat",
            "data": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        }

        await broadcaster.publish(channel, event)


async def _error_event_generator(error_message: str):
    """Generate a single error event."""
    yield {
        "event": "error",
        "data": {"message": error_message},
    }

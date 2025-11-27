"""
Agent Events API - Receives real-time agent activity from Claude Code hooks.

This module provides endpoints for:
- Receiving webhook events from Claude Code hooks
- SSE streaming of agent activity to the Glass Pane frontend
- Historical event retrieval
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from collections import defaultdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-events", tags=["agent-events"])


# In-memory event storage (per-session)
# In production, consider using Redis or a database
sessions: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {
        "events": [],
        "started_at": None,
        "last_activity": None,
        "status": "unknown",
        "cwd": None,
    }
)

# SSE subscribers for live updates
subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)


class AgentEvent(BaseModel):
    """Event from Claude Code hooks."""

    event_type: str
    session_id: str
    timestamp: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_response: Optional[str] = None
    prompt: Optional[str] = None
    cwd: Optional[str] = None
    reason: Optional[str] = None
    hook_event: Optional[str] = None


@router.post("")
async def receive_event(event: AgentEvent):
    """
    Receive webhook events from Claude Code hooks.

    This endpoint is called by the glass-pane-webhook.sh hook script
    whenever Claude Code performs actions.
    """
    session_id = event.session_id
    session = sessions[session_id]

    # Update session metadata
    session["last_activity"] = event.timestamp

    if event.event_type == "session_start":
        session["started_at"] = event.timestamp
        session["status"] = "active"
        session["cwd"] = event.cwd
        logger.info(f"Session started: {session_id}")

    elif event.event_type == "session_end":
        session["status"] = "completed"
        logger.info(f"Session ended: {session_id}")

    elif event.event_type == "tool_start":
        session["status"] = f"running: {event.tool_name}"

    elif event.event_type == "tool_complete":
        session["status"] = "active"

    # Store event
    event_data = event.model_dump()
    event_data["received_at"] = datetime.utcnow().isoformat()
    session["events"].append(event_data)

    # Limit events per session (keep last 500)
    if len(session["events"]) > 500:
        session["events"] = session["events"][-500:]

    # Notify SSE subscribers
    await broadcast_event(session_id, event_data)

    return {"status": "received", "session_id": session_id}


async def broadcast_event(session_id: str, event: Dict[str, Any]):
    """Broadcast event to all SSE subscribers for this session."""

    # Broadcast to session-specific subscribers
    for queue in subscribers.get(session_id, []):
        try:
            await queue.put(event)
        except Exception as e:
            logger.warning(f"Failed to broadcast to subscriber: {e}")

    # Also broadcast to "all" subscribers
    for queue in subscribers.get("__all__", []):
        try:
            await queue.put(event)
        except Exception as e:
            logger.warning(f"Failed to broadcast to all-subscriber: {e}")


@router.get("/stream")
async def stream_events(session_id: Optional[str] = None):
    """
    SSE endpoint for real-time agent activity streaming.

    Args:
        session_id: Optional session to filter events.
                   If not provided, streams all events.
    """
    import json

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        # Subscribe to events
        sub_key = session_id or "__all__"
        subscribers[sub_key].append(queue)

        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'session_filter': session_id})}\n\n"

            # Send existing sessions summary
            active_sessions = [
                {
                    "session_id": sid,
                    "status": data["status"],
                    "event_count": len(data["events"]),
                    "last_activity": data["last_activity"],
                }
                for sid, data in sessions.items()
                if data["status"] in ("active", "running")
            ]
            yield f"data: {json.dumps({'type': 'sessions', 'active': active_sessions})}\n\n"

            # Stream events as they arrive
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps({'type': 'event', 'data': event})}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            # Unsubscribe
            try:
                subscribers[sub_key].remove(queue)
            except ValueError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
async def list_sessions():
    """List all tracked sessions with their status."""
    return {
        "sessions": [
            {
                "session_id": session_id,
                "status": data["status"],
                "started_at": data["started_at"],
                "last_activity": data["last_activity"],
                "event_count": len(data["events"]),
                "cwd": data["cwd"],
            }
            for session_id, data in sessions.items()
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, limit: int = 100, offset: int = 0):
    """Get events for a specific session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    events = session["events"]

    return {
        "session_id": session_id,
        "status": session["status"],
        "started_at": session["started_at"],
        "last_activity": session["last_activity"],
        "cwd": session["cwd"],
        "total_events": len(events),
        "events": events[offset : offset + limit],
    }


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear events for a session."""
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "cleared", "session_id": session_id}


@router.get("/stats")
async def get_stats():
    """Get overall statistics about agent activity."""
    total_events = sum(len(s["events"]) for s in sessions.values())
    active_sessions = sum(
        1 for s in sessions.values() if s["status"] in ("active", "running")
    )

    # Tool usage stats
    tool_counts: Dict[str, int] = defaultdict(int)
    for session in sessions.values():
        for event in session["events"]:
            if event.get("tool_name"):
                tool_counts[event["tool_name"]] += 1

    return {
        "total_sessions": len(sessions),
        "active_sessions": active_sessions,
        "total_events": total_events,
        "tool_usage": dict(tool_counts),
    }

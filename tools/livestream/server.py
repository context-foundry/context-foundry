#!/usr/bin/env python3
"""
Context Foundry Livestream Server
Real-time monitoring for overnight coding sessions
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

app = FastAPI(title="Context Foundry Livestream")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections per session
connections: Dict[str, Set[WebSocket]] = {}

# Base paths
CHECKPOINTS_DIR = Path("checkpoints/ralph")
LOGS_DIR = Path("logs")
DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"


class SessionMonitor:
    """Monitor active sessions and broadcast updates."""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.last_update: Dict[str, float] = {}

    def discover_sessions(self) -> List[Dict]:
        """Discover all sessions from checkpoints."""
        sessions = []

        if not CHECKPOINTS_DIR.exists():
            return sessions

        for session_dir in CHECKPOINTS_DIR.iterdir():
            if not session_dir.is_dir():
                continue

            state_file = session_dir / "state.json"
            progress_file = session_dir / "progress.json"

            if not state_file.exists():
                continue

            try:
                with open(state_file) as f:
                    state = json.load(f)

                progress = {}
                if progress_file.exists():
                    with open(progress_file) as f:
                        progress = json.load(f)

                session_info = {
                    "id": session_dir.name,
                    "project": state.get("project_name", "Unknown"),
                    "task": state.get("task_description", ""),
                    "phase": state.get("current_phase", "unknown"),
                    "iterations": state.get("iterations", 0),
                    "start_time": state.get("start_time"),
                    "last_update": state.get("last_iteration_time"),
                    "completed_tasks": len(progress.get("completed", [])),
                    "total_tasks": len(progress.get("completed", []))
                    + len(progress.get("remaining", [])),
                    "is_complete": (session_dir / "COMPLETE").exists(),
                }

                sessions.append(session_info)

            except Exception as e:
                print(f"Error reading session {session_dir.name}: {e}")

        return sorted(sessions, key=lambda x: x.get("last_update", ""), reverse=True)

    def get_session_status(self, session_id: str) -> Dict:
        """Get detailed status for a session."""
        session_dir = CHECKPOINTS_DIR / session_id

        if not session_dir.exists():
            return {"error": "Session not found"}

        state_file = session_dir / "state.json"
        progress_file = session_dir / "progress.json"

        try:
            # Load state
            with open(state_file) as f:
                state = json.load(f)

            # Load progress
            progress = {}
            if progress_file.exists():
                with open(progress_file) as f:
                    progress = json.load(f)

            # Calculate stats
            start_time = datetime.fromisoformat(state.get("start_time", datetime.now().isoformat()))
            elapsed_seconds = (datetime.now() - start_time).total_seconds()

            completed = len(progress.get("completed", []))
            total = completed + len(progress.get("remaining", []))

            # Estimate remaining time
            if completed > 0 and state.get("iterations", 0) > 0:
                avg_time_per_task = elapsed_seconds / completed
                remaining_tasks = total - completed
                estimated_seconds = avg_time_per_task * remaining_tasks
            else:
                estimated_seconds = 0

            return {
                "id": session_id,
                "project": state.get("project_name"),
                "task": state.get("task_description"),
                "phase": state.get("current_phase"),
                "iterations": state.get("iterations", 0),
                "start_time": state.get("start_time"),
                "elapsed_seconds": int(elapsed_seconds),
                "estimated_remaining_seconds": int(estimated_seconds),
                "tasks": {
                    "completed": progress.get("completed", []),
                    "remaining": progress.get("remaining", []),
                    "total": total,
                    "progress_percent": int((completed / total * 100)) if total > 0 else 0,
                },
                "context": {
                    "percentage": 0,  # Would need to read from Claude logs
                    "tokens_used": 0,
                },
                "artifacts": state.get("artifacts", {}),
                "is_complete": (session_dir / "COMPLETE").exists(),
                "notes": progress.get("notes", []),
            }

        except Exception as e:
            return {"error": str(e)}

    def get_session_logs(self, session_id: str, tail_lines: int = 50) -> List[str]:
        """Get recent logs for a session."""
        log_dir = LOGS_DIR / f"ralph_{session_id}"

        if not log_dir.exists():
            # Try overnight logs
            overnight_logs = list(LOGS_DIR.glob("overnight_*.log"))
            if overnight_logs:
                log_file = overnight_logs[0]
            else:
                return []
        else:
            log_file = log_dir / "session.jsonl"
            if not log_file.exists():
                return []

        try:
            with open(log_file) as f:
                lines = f.readlines()
                return lines[-tail_lines:]
        except Exception as e:
            return [f"Error reading logs: {e}"]


# Global monitor
monitor = SessionMonitor()


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML."""
    if DASHBOARD_FILE.exists():
        return FileResponse(DASHBOARD_FILE)
    return HTMLResponse("<h1>Dashboard not found</h1><p>Create dashboard.html</p>")


@app.get("/api/sessions")
async def get_sessions():
    """Get list of all sessions."""
    sessions = monitor.discover_sessions()
    return JSONResponse({"sessions": sessions, "count": len(sessions)})


@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    """Get detailed status for a session."""
    status = monitor.get_session_status(session_id)
    return JSONResponse(status)


@app.get("/api/logs/{session_id}")
async def get_logs(session_id: str, lines: int = 50):
    """Get recent logs for a session."""
    logs = monitor.get_session_logs(session_id, lines)
    return JSONResponse({"session_id": session_id, "logs": logs})


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket for real-time updates."""
    await websocket.accept()

    # Add to connections
    if session_id not in connections:
        connections[session_id] = set()
    connections[session_id].add(websocket)

    try:
        # Send initial status
        status = monitor.get_session_status(session_id)
        await websocket.send_json({"type": "status", "data": status})

        # Keep connection alive and send updates
        while True:
            # Poll for updates every second
            await asyncio.sleep(1)

            # Get latest status
            status = monitor.get_session_status(session_id)
            await websocket.send_json({"type": "status", "data": status})

            # Check if session is complete
            if status.get("is_complete"):
                await websocket.send_json(
                    {"type": "complete", "message": "Session completed!"}
                )

    except WebSocketDisconnect:
        connections[session_id].remove(websocket)
        if not connections[session_id]:
            del connections[session_id]


@app.post("/api/broadcast/{session_id}")
async def broadcast_event(session_id: str, event: Dict):
    """
    Broadcast event to all connected clients for a session.
    Called by broadcaster.py during execution.
    """
    if session_id in connections:
        for connection in connections[session_id]:
            try:
                await connection.send_json(event)
            except:
                pass

    return {"broadcasted": len(connections.get(session_id, []))}


@app.get("/api/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "sessions": len(monitor.discover_sessions()),
        "connections": sum(len(conns) for conns in connections.values()),
    }


def main():
    """Start the livestream server."""
    port = int(os.getenv("LIVESTREAM_PORT", "8080"))
    host = os.getenv("LIVESTREAM_HOST", "0.0.0.0")

    print(f"🎥 Context Foundry Livestream")
    print(f"📡 Starting server on http://{host}:{port}")
    print(f"🌐 Dashboard: http://localhost:{port}")
    print(f"📊 API Docs: http://localhost:{port}/docs")
    print(f"\nPress Ctrl+C to stop")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

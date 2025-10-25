#!/usr/bin/env python3
"""
Context Foundry Livestream Server
Real-time monitoring for overnight coding sessions
"""

import os
import sys
import json
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Any
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

# Change detection: store last sent data hashes per connection
last_sent_hashes: Dict[str, str] = {}

# Base paths
CHECKPOINTS_DIR = Path("checkpoints/ralph")
LOGS_DIR = Path("logs")
DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"


def hash_data(data: Dict) -> str:
    """
    Create SHA256 hash of data for change detection.

    Args:
        data: Dictionary to hash

    Returns:
        Hex digest of SHA256 hash
    """
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()


class SessionMonitor:
    """Monitor active sessions and broadcast updates."""

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.last_update: Dict[str, float] = {}

    def discover_sessions(self) -> List[Dict]:
        """Discover all sessions from checkpoints and live phase updates."""
        sessions = []

        # First, add live sessions from phase-update API
        for session_id, session_data in self.sessions.items():
            session_info = {
                "id": session_id,
                "project": session_id,
                "task": session_data.get("progress_detail", ""),
                "phase": session_data.get("current_phase", "unknown"),
                "phase_number": session_data.get("phase_number", "?/7"),
                "status": session_data.get("status", "unknown"),
                "iterations": session_data.get("test_iteration", 0),
                "start_time": session_data.get("started_at"),
                "last_update": session_data.get("last_updated"),
                "phases_completed": session_data.get("phases_completed", []),
                "is_complete": session_data.get("status") == "completed",
                "source": "live"
            }
            sessions.append(session_info)

        # Then, add checkpoint-based sessions
        if CHECKPOINTS_DIR.exists():
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
                        "source": "checkpoint"
                    }

                    sessions.append(session_info)

                except Exception as e:
                    print(f"Error reading session {session_dir.name}: {e}")

        return sorted(sessions, key=lambda x: x.get("last_update", ""), reverse=True)

    def get_session_status(self, session_id: str) -> Dict:
        """Get detailed status for a session (live or checkpoint-based)."""

        # First, check if this is a live session from phase-update API
        if session_id in self.sessions:
            live_data = self.sessions[session_id]

            # Calculate elapsed time
            elapsed_seconds = 0
            if live_data.get("started_at"):
                try:
                    # Handle ISO format with Z timezone suffix
                    started_at_str = live_data["started_at"].replace("Z", "+00:00")
                    start_time = datetime.fromisoformat(started_at_str)
                    # Make datetime.now() timezone-aware for comparison
                    from datetime import timezone
                    elapsed_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
                except Exception as e:
                    print(f"Error parsing started_at: {e}", file=sys.stderr)
                    pass

            # Count completed phases for progress
            phases_completed = live_data.get("phases_completed", [])
            total_phases = 7  # Scout, Architect, Builder, Test, Screenshot, Documentation, Deploy

            return {
                "id": session_id,
                "project": session_id,
                "task": live_data.get("progress_detail", "In progress..."),
                "phase": live_data.get("current_phase", "Unknown"),
                "phase_number": live_data.get("phase_number", "?/7"),
                "iterations": live_data.get("test_iteration", 0),
                "start_time": live_data.get("started_at"),
                "elapsed_seconds": int(elapsed_seconds),
                "estimated_remaining_seconds": 0,  # TODO: Could estimate based on phase
                "tasks": {
                    "completed": phases_completed,
                    "remaining": [],
                    "total": total_phases,
                    "progress_percent": int((len(phases_completed) / total_phases * 100)),
                },
                "context": {
                    "percentage": 0,  # Live data doesn't have token info yet
                    "tokens_used": 0,
                },
                "artifacts": {},
                "is_complete": live_data.get("status") == "completed",
                "notes": [],
                "source": "live"
            }

        # Fall back to checkpoint-based session lookup
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
                "source": "checkpoint"
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
    """WebSocket for real-time updates with change detection."""
    await websocket.accept()

    # Add to connections
    if session_id not in connections:
        connections[session_id] = set()
    connections[session_id].add(websocket)

    # Track last hash for this connection (use id() for unique key)
    connection_key = f"{session_id}_{id(websocket)}"
    last_hash = None

    try:
        # Send initial status
        status = monitor.get_session_status(session_id)
        current_hash = hash_data(status)
        await websocket.send_json({"type": "status", "data": status})
        last_hash = current_hash

        # Keep connection alive and send updates ONLY if changed
        while True:
            # Poll for updates every second
            await asyncio.sleep(1)

            # Get latest status
            status = monitor.get_session_status(session_id)
            current_hash = hash_data(status)

            # CHANGE DETECTION: Only send if data changed
            if current_hash != last_hash:
                await websocket.send_json({"type": "status", "data": status})
                last_hash = current_hash

            # Check if session is complete
            if status.get("is_complete"):
                await websocket.send_json(
                    {"type": "complete", "message": "Session completed!"}
                )
                break

    except WebSocketDisconnect:
        connections[session_id].remove(websocket)
        if not connections[session_id]:
            del connections[session_id]
        # Clean up hash tracking
        if connection_key in last_sent_hashes:
            del last_sent_hashes[connection_key]


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


@app.post("/api/phase-update")
async def phase_update(phase_data: Dict):
    """
    Receive phase update from autonomous orchestrator.
    Accepts current-phase.json data and broadcasts to connected clients.
    """
    # Extract session info from phase data or use working directory
    session_id = phase_data.get("session_id", "autonomous-build")

    # Update session monitor (preserve started_at if it exists)
    existing_session = monitor.sessions.get(session_id, {})
    monitor.sessions[session_id] = {
        "session_id": session_id,
        "current_phase": phase_data.get("current_phase", "Unknown"),
        "phase_number": phase_data.get("phase_number", "?/7"),
        "status": phase_data.get("status", "unknown"),
        "progress_detail": phase_data.get("progress_detail", ""),
        "test_iteration": phase_data.get("test_iteration", 0),
        "phases_completed": phase_data.get("phases_completed", []),
        "started_at": phase_data.get("started_at") or existing_session.get("started_at") or datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }

    # Broadcast to connected clients
    broadcast_count = 0
    if session_id in connections:
        for connection in connections[session_id]:
            try:
                await connection.send_json({
                    "type": "phase_update",
                    "data": monitor.sessions[session_id]
                })
                broadcast_count += 1
            except:
                pass

    return {
        "status": "received",
        "session_id": session_id,
        "phase": phase_data.get("current_phase"),
        "broadcasted_to": broadcast_count
    }


@app.get("/api/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "sessions": len(monitor.discover_sessions()),
        "connections": sum(len(conns) for conns in connections.values()),
    }


# ============================================================================
# Multi-Agent Monitoring Endpoints (NEW)
# ============================================================================

@app.get("/api/agents/{session_id}")
async def get_session_agents(session_id: str):
    """Get all agent instances for a session."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "Multi-agent features require MCP enhancement"}, status_code=503)

    try:
        db = get_db()
        agents = db.get_session_agents(session_id)
        active_agents = [a for a in agents if a['status'] in ['spawning', 'active', 'idle']]

        return JSONResponse({
            "session_id": session_id,
            "agents": agents,
            "total_agents": len(agents),
            "active_agents": len(active_agents)
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/agent/{agent_id}")
async def get_agent_detail(agent_id: str):
    """Get detailed status for a specific agent."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "Multi-agent features require MCP enhancement"}, status_code=503)

    try:
        db = get_db()
        agent = db.get_agent_instance(agent_id)

        if not agent:
            return JSONResponse({"error": "Agent not found"}, status_code=404)

        # Calculate elapsed seconds if agent is still running
        if agent['start_time'] and not agent['end_time']:
            from datetime import datetime, timezone
            start_time = datetime.fromisoformat(agent['start_time'].replace('Z', '+00:00'))
            elapsed_seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())
            agent['elapsed_seconds'] = elapsed_seconds

            # Estimate remaining time based on progress
            if agent['progress_percent'] > 0:
                estimated_total = elapsed_seconds / (agent['progress_percent'] / 100.0)
                agent['estimated_remaining_seconds'] = int(estimated_total - elapsed_seconds)
            else:
                agent['estimated_remaining_seconds'] = 0

        return JSONResponse(agent)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/instances")
async def get_all_instances():
    """Get all running Context Foundry instances with summary stats."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "Multi-agent features require MCP enhancement"}, status_code=503)

    try:
        db = get_db()
        instances = db.get_all_instances()

        return JSONResponse({
            "instances": instances,
            "total_instances": len(instances)
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/agent-update")
async def agent_update(agent_data: Dict):
    """
    Receive agent status updates from orchestrator/builders.
    Creates or updates agent instance and broadcasts to connected clients.
    """
    if not MCP_ENHANCED:
        return JSONResponse({"error": "Multi-agent features require MCP enhancement"}, status_code=503)

    try:
        db = get_db()
        session_id = agent_data.get("session_id")
        agent_id = agent_data.get("agent_id")

        if not session_id or not agent_id:
            return JSONResponse({"error": "session_id and agent_id required"}, status_code=400)

        # Check if agent exists
        existing_agent = db.get_agent_instance(agent_id)

        if existing_agent:
            # Update existing agent
            updates = {}
            for key in ['status', 'phase', 'progress_percent', 'tokens_used', 'token_percentage', 'error_message']:
                if key in agent_data:
                    updates[key] = agent_data[key]

            # Calculate token percentage if tokens_used provided
            if 'tokens_used' in updates and existing_agent.get('tokens_limit'):
                updates['token_percentage'] = (updates['tokens_used'] / existing_agent['tokens_limit']) * 100

            # Set end_time if status is completed or failed
            if updates.get('status') in ['completed', 'failed']:
                updates['end_time'] = datetime.now().isoformat()
                if existing_agent.get('start_time'):
                    from datetime import datetime as dt
                    start = dt.fromisoformat(existing_agent['start_time'].replace('Z', '+00:00'))
                    end = dt.now(timezone.utc)
                    updates['duration_seconds'] = int((end - start).total_seconds())

            db.update_agent_instance(agent_id, updates)
        else:
            # Create new agent instance
            db.create_agent_instance(agent_data)

        # Broadcast agent update to connected clients
        broadcast_count = 0
        if session_id in connections:
            event = {
                "type": "agent_progress",
                "session_id": session_id,
                "data": agent_data
            }
            for connection in connections[session_id]:
                try:
                    await connection.send_json(event)
                    broadcast_count += 1
                except:
                    pass

        return JSONResponse({
            "status": "updated",
            "agent_id": agent_id,
            "broadcasted_to": broadcast_count
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================================
# Enhanced MCP Integration Endpoints
# ============================================================================

# Import enhanced modules
try:
    # Try relative imports first (when used as module)
    from .mcp_client import get_client
    from .metrics_db import get_db
    from .config import TOKEN_BUDGET_LIMIT, get_token_status
    MCP_ENHANCED = True
except ImportError:
    try:
        # Fall back to direct imports (when run as script)
        from mcp_client import get_client
        from metrics_db import get_db
        from config import TOKEN_BUDGET_LIMIT, get_token_status
        MCP_ENHANCED = True
    except ImportError:
        print("⚠️  Enhanced MCP modules not available", file=sys.stderr)
        MCP_ENHANCED = False


@app.get("/api/mcp/tasks")
async def get_mcp_tasks():
    """Get all active MCP delegation tasks."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "MCP enhanced features not available"}, status_code=503)

    try:
        mcp_client = get_client()
        tasks = mcp_client.list_active_tasks()
        return JSONResponse({"tasks": tasks, "count": len(tasks)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/mcp/task/{task_id}")
async def get_mcp_task(task_id: str):
    """Get detailed status for an MCP delegation task."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "MCP enhanced features not available"}, status_code=503)

    try:
        mcp_client = get_client()
        task = mcp_client.get_task_status(task_id)
        return JSONResponse(task)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/metrics/{task_id}")
async def get_task_metrics(task_id: str):
    """Get comprehensive metrics for a task."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "MCP enhanced features not available"}, status_code=503)

    try:
        db = get_db()
        mcp_client = get_client()

        # Get task data
        task_data = db.get_task(task_id)
        if not task_data:
            return JSONResponse({"error": "Task not found"}, status_code=404)

        # Get metrics
        metrics = db.get_metrics(task_id)
        latest_metric = db.get_latest_metric(task_id)

        # Get decisions
        decisions = db.get_decisions(task_id)
        decision_analytics = db.get_decision_analytics(task_id)

        # Get agent performance
        agent_performance = db.get_agent_performance(task_id)

        # Get test iterations
        test_iterations = db.get_test_iterations(task_id)

        # Get pattern effectiveness
        pattern_effectiveness = db.get_pattern_effectiveness(task_id)

        # Get token estimate
        token_estimate = mcp_client.estimate_token_usage(task_id)
        token_status = get_token_status(token_estimate['estimated_tokens'])

        return JSONResponse({
            "task": task_data,
            "metrics": {
                "latest": latest_metric,
                "history": metrics[-20:] if len(metrics) > 20 else metrics,  # Last 20
                "token_usage": token_status,
            },
            "decisions": {
                "recent": decisions[-10:] if len(decisions) > 10 else decisions,  # Last 10
                "analytics": decision_analytics
            },
            "agent_performance": agent_performance,
            "test_iterations": test_iterations,
            "pattern_effectiveness": pattern_effectiveness
        })
    except Exception as e:
        import traceback
        return JSONResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)


@app.get("/api/metrics/historical")
async def get_historical_metrics(limit: int = 100):
    """Get historical metrics across all tasks."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "MCP enhanced features not available"}, status_code=503)

    try:
        db = get_db()

        # Get all tasks
        tasks = db.get_all_tasks(limit)

        # Get summary stats
        stats = db.get_summary_stats()

        return JSONResponse({
            "tasks": tasks,
            "summary": stats,
            "total_tasks": len(tasks)
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/analytics/decisions")
async def get_decision_analytics(task_id: Optional[str] = None):
    """Get decision quality analytics."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "MCP enhanced features not available"}, status_code=503)

    try:
        db = get_db()

        analytics = db.get_decision_analytics(task_id)

        return JSONResponse({
            "analytics": analytics,
            "task_id": task_id
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/analytics/agents")
async def get_agent_analytics(agent_type: Optional[str] = None):
    """Get agent performance analytics."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "MCP enhanced features not available"}, status_code=503)

    try:
        db = get_db()

        analytics = db.get_agent_analytics(agent_type)

        return JSONResponse({
            "analytics": analytics,
            "agent_type": agent_type
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/token/status/{task_id}")
async def get_token_usage_status(task_id: str):
    """Get detailed token usage status for a task."""
    if not MCP_ENHANCED:
        return JSONResponse({"error": "MCP enhanced features not available"}, status_code=503)

    try:
        mcp_client = get_client()

        token_estimate = mcp_client.estimate_token_usage(task_id)
        token_status = get_token_status(token_estimate['estimated_tokens'])

        return JSONResponse(token_status)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================================
# Background Metrics Collector
# ============================================================================

# Global metrics collector instance
metrics_collector_task = None

@app.on_event("startup")
async def startup_event():
    """Start background services on server startup."""
    global metrics_collector_task

    if MCP_ENHANCED:
        print("🔄 Starting metrics collector...", file=sys.stderr)
        try:
            try:
                from .metrics_collector import MetricsCollector
            except ImportError:
                from metrics_collector import MetricsCollector
            collector = MetricsCollector()
            metrics_collector_task = asyncio.create_task(collector.start())
            print("✅ Metrics collector started", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Failed to start metrics collector: {e}", file=sys.stderr)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background services on server shutdown."""
    global metrics_collector_task

    if metrics_collector_task:
        print("🛑 Stopping metrics collector...", file=sys.stderr)
        metrics_collector_task.cancel()
        try:
            await metrics_collector_task
        except asyncio.CancelledError:
            pass


def main():
    """Start the livestream server."""
    port = int(os.getenv("LIVESTREAM_PORT", "8080"))
    host = os.getenv("LIVESTREAM_HOST", "0.0.0.0")

    print(f"🎥 Context Foundry Livestream")
    print(f"📡 Starting server on http://{host}:{port}")
    print(f"🌐 Dashboard: http://localhost:{port}")
    print(f"📊 API Docs: http://localhost:{port}/docs")
    if MCP_ENHANCED:
        print(f"🔄 Enhanced MCP metrics: Enabled")
    else:
        print(f"⚠️  Enhanced MCP metrics: Disabled")
    print(f"\nPress Ctrl+C to stop")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

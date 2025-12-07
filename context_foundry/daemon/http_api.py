"""
HTTP/JSON Status API for Context Foundry Daemon.

Provides read-only REST endpoints for job/task/gate introspection.
Uses Python stdlib http.server for minimal dependencies.

Endpoints:
    GET /health                   - Health check
    GET /jobs                     - List jobs
    GET /jobs/{job_id}           - Job details
    GET /jobs/{job_id}/timeline  - Job event timeline
    GET /jobs/{job_id}/gates     - Job gate status
    GET /jobs/{job_id}/tree      - Job tree view (phases + tasks)
    GET /events/recent           - Recent events across all jobs
    GET /metrics                 - Metrics snapshot (if enabled)
"""

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .gates import GateManager
from .metrics import get_metrics, log_structured
from .models import JobStatus, Task, TaskStatus
from .store import Store

logger = logging.getLogger(__name__)


# =============================================================================
# API CONTEXT
# =============================================================================


@dataclass
class APIContext:
    """Shared context for API requests."""

    store: Store
    start_time: datetime = field(default_factory=datetime.now)
    stop_event: threading.Event = field(default_factory=threading.Event)


# =============================================================================
# JOB TREE HELPER
# =============================================================================


def get_job_tree(store: Store, job_id: str) -> Dict[str, Any]:
    """
    Build a hierarchical tree view of a job's phases and tasks.

    Returns:
        {
            "job_id": "...",
            "status": "RUNNING",
            "created_at": "...",
            "phases": [
                {
                    "phase": "Scout",
                    "status": "SUCCEEDED",
                    "sequence": 0,
                    "tasks": [
                        {"task_id": "...", "status": "SUCCEEDED", ...}
                    ]
                },
                ...
            ]
        }
    """
    job = store.get_job(job_id)
    if not job:
        return {"error": f"Job not found: {job_id}"}

    # Get all tasks for this job
    tasks = store.get_tasks_for_job(job_id)

    # Group tasks by phase
    tasks_by_phase: Dict[str, List[Task]] = {}
    for task in tasks:
        phase = task.name  # Task name is the phase name
        if phase not in tasks_by_phase:
            tasks_by_phase[phase] = []
        tasks_by_phase[phase].append(task)

    # Define standard phase order (for sorting known phases)
    standard_phase_order = [
        "Scout",
        "Architect",
        "Builder",
        "Test",
        "Feedback",
        "Deploy",
    ]

    # Get all phases that actually have tasks
    all_phases = set(tasks_by_phase.keys())

    # Sort phases: standard phases first (in order), then custom phases alphabetically
    def phase_sort_key(phase_name: str) -> tuple:
        if phase_name in standard_phase_order:
            return (0, standard_phase_order.index(phase_name))
        return (1, phase_name)

    sorted_phases = sorted(all_phases, key=phase_sort_key)

    # Build phases list - only include phases that have tasks
    phases = []
    for seq, phase_name in enumerate(sorted_phases):
        phase_tasks = tasks_by_phase.get(phase_name, [])

        # Skip phases with no tasks (dynamic discovery means we only show actual phases)
        if not phase_tasks:
            continue

        # Determine phase status from tasks
        if all(t.status == TaskStatus.SUCCEEDED for t in phase_tasks):
            phase_status = "succeeded"
        elif any(
            t.status in (TaskStatus.FAILED, TaskStatus.TIMED_OUT) for t in phase_tasks
        ):
            phase_status = "failed"
        elif any(t.status == TaskStatus.RUNNING for t in phase_tasks):
            phase_status = "running"
        else:
            phase_status = "pending"

        # Serialize tasks
        serialized_tasks = []
        for task in sorted(phase_tasks, key=lambda t: t.created_at):
            task_data = {
                "task_id": task.id,
                "status": task.status.value,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat()
                if task.completed_at
                else None,
                "last_heartbeat": task.last_heartbeat.isoformat()
                if task.last_heartbeat
                else None,
            }
            # Include model/provider info from task metadata
            if task.metadata:
                if task.metadata.get("provider"):
                    task_data["provider"] = task.metadata["provider"]
                if task.metadata.get("model"):
                    task_data["model"] = task.metadata["model"]
            serialized_tasks.append(task_data)

        # Get model/provider from first task (they should all be the same for a phase)
        phase_model = None
        phase_provider = None
        if phase_tasks:
            first_task = phase_tasks[0]
            if first_task.metadata:
                phase_model = first_task.metadata.get("model")
                phase_provider = first_task.metadata.get("provider")

        phase_data = {
            "phase": phase_name,
            "status": phase_status,
            "sequence": seq,
            "tasks": serialized_tasks,
        }
        if phase_model:
            phase_data["model"] = phase_model
        if phase_provider:
            phase_data["provider"] = phase_provider

        phases.append(phase_data)

    return {
        "job_id": job.id,
        "status": job.status.value,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "phases": phases,
    }


def format_job_tree_ascii(tree: Dict[str, Any]) -> str:
    """
    Format a job tree as ASCII art for CLI display.

    Example output:
        Job e0fc0679 (SUCCEEDED)
        +-- Phase: Scout (SUCCEEDED)
        |   +-- Task b916d083 (SUCCEEDED)
        +-- Phase: Builder (RUNNING)
        |   +-- Task a1b2c3d4 (RUNNING)
        +-- Phase: Feedback (PENDING)
    """
    if "error" in tree:
        return f"Error: {tree['error']}"

    lines = []

    # Job header
    job_id = tree["job_id"][:8]
    status = tree["status"].upper()
    lines.append(f"Job {job_id} ({status})")

    phases = tree.get("phases", [])
    total_phases = len(phases)

    for i, phase in enumerate(phases):
        is_last_phase = i == total_phases - 1
        phase_prefix = "+-- " if not is_last_phase else "+-- "
        child_prefix = "|   " if not is_last_phase else "    "

        phase_name = phase["phase"]
        phase_status = phase["status"].upper()
        lines.append(f"{phase_prefix}Phase: {phase_name} ({phase_status})")

        tasks = phase.get("tasks", [])
        total_tasks = len(tasks)

        for j, task in enumerate(tasks):
            is_last_task = j == total_tasks - 1
            task_prefix = "+-- " if not is_last_task else "+-- "

            task_id = task["task_id"][:8]
            task_status = task["status"].upper()
            lines.append(f"{child_prefix}{task_prefix}Task {task_id} ({task_status})")

    return "\n".join(lines)


# =============================================================================
# HTTP REQUEST HANDLER
# =============================================================================


class APIRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the status API."""

    # Suppress default logging
    def log_message(self, format: str, *args) -> None:
        logger.debug("HTTP: %s", format % args)

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send a JSON response."""
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        """Send a JSON error response."""
        self._send_json({"error": message}, status)

    def _get_context(self) -> APIContext:
        """Get the shared API context."""
        return self.server.api_context  # type: ignore

    def _parse_query_params(self) -> Dict[str, str]:
        """Parse query string parameters."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        # Convert list values to single values
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS preflight requests for CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Authorization, X-CF-Auth"
        )
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Strip /api prefix if present (support both /api/jobs and /jobs)
        if path.startswith("/api/"):
            path = path[4:]  # Remove "/api" prefix

        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}

            # Route to appropriate handler
            if path == "/tools/execute":
                self._handle_execute_tool(data)
            elif path == "/agents":
                self._handle_agents_update(data)
            elif path == "/sidekick-chat":
                self._handle_sidekick_chat(data)
            else:
                self._send_error(404, f"Not found: {path}")

        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON body")
        except Exception as e:
            logger.exception("Error handling POST request: %s", path)
            self._send_error(500, f"Internal server error: {str(e)}")

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Strip /api prefix if present (support both /api/jobs and /jobs)
        if path.startswith("/api/"):
            path = path[4:]  # Remove "/api" prefix

        try:
            # Route to appropriate handler
            if path == "/health":
                self._handle_health()
            elif path == "/jobs":
                self._handle_list_jobs()
            elif path == "/events/recent":
                self._handle_recent_events()
            elif path == "/metrics":
                self._handle_metrics()
            elif path == "/config":
                self._handle_config()
            elif re.match(r"^/jobs/[^/]+$", path):
                job_id = path.split("/")[2]
                self._handle_get_job(job_id)
            elif re.match(r"^/jobs/[^/]+/timeline$", path):
                job_id = path.split("/")[2]
                self._handle_job_timeline(job_id)
            elif re.match(r"^/jobs/[^/]+/gates$", path):
                job_id = path.split("/")[2]
                self._handle_job_gates(job_id)
            elif re.match(r"^/jobs/[^/]+/tree$", path):
                job_id = path.split("/")[2]
                self._handle_job_tree(job_id)
            elif path == "/agents":
                self._handle_agents()
            elif path == "/pending-approvals":
                self._handle_pending_approvals()
            elif re.match(r"^/jobs/[^/]+/conversation$", path):
                job_id = path.split("/")[2]
                self._handle_job_conversation(job_id)
            elif re.match(r"^/jobs/[^/]+/artifacts$", path):
                job_id = path.split("/")[2]
                self._handle_job_artifacts(job_id)
            else:
                self._send_error(404, f"Not found: {path}")

        except Exception as e:
            logger.exception("Error handling request: %s", path)
            self._send_error(500, f"Internal server error: {str(e)}")

    # =========================================================================
    # ENDPOINT HANDLERS
    # =========================================================================

    def _handle_health(self) -> None:
        """GET /health - Health check."""
        ctx = self._get_context()

        # Calculate uptime
        uptime = (datetime.now() - ctx.start_time).total_seconds()

        # Get job counts
        try:
            stats = ctx.store.get_job_stats()
            active_jobs = stats.get("running", 0)
            queued_jobs = stats.get("queued", 0)
        except Exception:
            active_jobs = 0
            queued_jobs = 0

        self._send_json(
            {
                "status": "ok",
                "uptime_seconds": round(uptime, 2),
                "active_jobs": active_jobs,
                "queued_jobs": queued_jobs,
                "timestamp": datetime.now().isoformat(),
            }
        )

        log_structured(
            logger,
            logging.DEBUG,
            "Health check",
            event="api_health_check",
            uptime_seconds=uptime,
        )

    def _handle_list_jobs(self) -> None:
        """GET /jobs - List jobs with optional filters."""
        ctx = self._get_context()
        params = self._parse_query_params()

        # Parse filters
        status_filter = None
        if "status" in params:
            try:
                status_filter = JobStatus(params["status"])
            except ValueError:
                self._send_error(400, f"Invalid status: {params['status']}")
                return

        limit = int(params.get("limit", 50))
        offset = int(params.get("offset", 0))

        # Get gate manager for current_phase
        gate_mgr = GateManager(ctx.store)

        # Get jobs
        jobs = ctx.store.list_jobs(status=status_filter, limit=limit, offset=offset)

        # Serialize
        serialized = []
        for job in jobs:
            current_phase = gate_mgr.get_current_phase(job.id)
            # Extract task from params for display
            task = None
            if job.params:
                task = job.params.get("task")
            serialized.append(
                {
                    "job_id": job.id,
                    "type": job.type.value,
                    "status": job.status.value,
                    "priority": job.priority,
                    "current_phase": current_phase,
                    "task": task,  # Include task for job list display
                    "params": job.params,  # Include full params
                    "created_at": job.created_at.isoformat()
                    if job.created_at
                    else None,
                    "started_at": job.started_at.isoformat()
                    if job.started_at
                    else None,
                    "completed_at": job.completed_at.isoformat()
                    if job.completed_at
                    else None,
                }
            )

        self._send_json(
            {
                "jobs": serialized,
                "count": len(serialized),
                "limit": limit,
                "offset": offset,
            }
        )

    def _handle_get_job(self, job_id: str) -> None:
        """GET /jobs/{job_id} - Get job details."""
        ctx = self._get_context()

        job = ctx.store.get_job(job_id)
        if not job:
            self._send_error(404, f"Job not found: {job_id}")
            return

        # Get gate info
        gate_mgr = GateManager(ctx.store)
        current_phase = gate_mgr.get_current_phase(job_id)
        next_phase = gate_mgr.get_next_phase(job_id)

        # Get phase summary
        phase_summary = ctx.store.get_job_phase_summary(job_id)

        self._send_json(
            {
                "job_id": job.id,
                "type": job.type.value,
                "status": job.status.value,
                "priority": job.priority,
                "current_phase": current_phase,
                "next_phase": next_phase,
                "params": job.params,
                "result": job.result,
                "error": job.error,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat()
                if job.completed_at
                else None,
                "retry_count": job.retry_count,
                "max_retries": job.max_retries,
                "phase_summary": phase_summary,
            }
        )

    def _handle_job_timeline(self, job_id: str) -> None:
        """GET /jobs/{job_id}/timeline - Get job event timeline."""
        ctx = self._get_context()
        params = self._parse_query_params()

        # Verify job exists
        job = ctx.store.get_job(job_id)
        if not job:
            self._send_error(404, f"Job not found: {job_id}")
            return

        include_heartbeats = params.get("heartbeats", "false").lower() == "true"
        limit = int(params.get("limit", 100))

        events = ctx.store.get_job_timeline(
            job_id,
            include_heartbeats=include_heartbeats,
            limit=limit,
        )

        self._send_json(
            {
                "job_id": job_id,
                "events": events,
                "count": len(events),
            }
        )

    def _handle_job_gates(self, job_id: str) -> None:
        """GET /jobs/{job_id}/gates - Get job gate status."""
        ctx = self._get_context()

        # Verify job exists
        job = ctx.store.get_job(job_id)
        if not job:
            self._send_error(404, f"Job not found: {job_id}")
            return

        gate_mgr = GateManager(ctx.store)
        report = gate_mgr.get_gate_report(job_id)

        # Serialize gate report
        gates = []
        for gate in report.gates:
            gates.append(
                {
                    "phase": gate.phase,
                    "status": gate.status.value,
                    "duration_seconds": gate.duration_seconds,
                    "error": gate.error,
                }
            )

        self._send_json(
            {
                "job_id": job_id,
                "job_status": job.status.value,
                "gates": gates,
                "current_gate": report.current_gate,
                "next_gate": report.next_gate,
                "highest_passed_gate": report.highest_passed_gate,
                "all_required_passed": report.all_required_passed,
                "has_failures": report.has_failures,
            }
        )

    def _handle_job_tree(self, job_id: str) -> None:
        """GET /jobs/{job_id}/tree - Get job tree view."""
        ctx = self._get_context()

        tree = get_job_tree(ctx.store, job_id)

        if "error" in tree:
            self._send_error(404, tree["error"])
            return

        self._send_json(tree)

    def _handle_recent_events(self) -> None:
        """GET /events/recent - Get recent events across all jobs."""
        ctx = self._get_context()
        params = self._parse_query_params()

        limit = int(params.get("limit", 50))
        event_type = params.get("type")

        event_types = [event_type] if event_type else None

        events = ctx.store.get_recent_events(limit=limit, event_types=event_types)

        self._send_json(
            {
                "events": events,
                "count": len(events),
            }
        )

    def _handle_metrics(self) -> None:
        """GET /metrics - Get metrics snapshot."""
        metrics = get_metrics()
        stats = metrics.get_stats()

        self._send_json(
            {
                "metrics": stats,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _handle_config(self) -> None:
        """GET /config - Get provider configuration."""
        from pathlib import Path

        config_path = Path.home() / ".context-foundry" / "provider_config.json"

        config = {}
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                config = {"error": str(e)}

        self._send_json(config)

    def _handle_execute_tool(self, data: Dict[str, Any]) -> None:
        """POST /tools/execute - Execute a tool."""
        # Check Authentication
        import os

        api_key = os.environ.get("EVOLUTION_API_KEY")

        # CRITICAL SECURITY: Do not allow tool execution without an API key
        if not api_key:
            self._send_error(
                500,
                "Server misconfiguration: EVOLUTION_API_KEY not set. Tool execution disabled.",
            )
            return

        auth_header = self.headers.get("Authorization", "")
        if (
            not auth_header.startswith("Bearer ")
            or auth_header.split(" ")[1] != api_key
        ):
            self._send_error(401, "Unauthorized: Invalid or missing API Key")
            return

        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {})
        working_directory = data.get("working_directory")

        if not tool_name:
            self._send_error(400, "Missing tool_name")
            return

        if not working_directory:
            self._send_error(400, "Missing working_directory")
            return

        try:
            # Import here to avoid circular imports if any
            from tools.evolution.communication.tool_executor import ToolExecutor
            from pathlib import Path

            executor = ToolExecutor(Path(working_directory))
            result = executor.execute(tool_name, arguments)

            self._send_json(result)

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            self._send_error(500, str(e))

    def _handle_agents(self) -> None:
        """GET /agents - Get agent configuration."""
        try:
            from tools.evolution.framework.agent_registry import AgentRegistry

            registry = AgentRegistry()
            agents = registry.list_agents()
            self._send_json({"agents": agents})
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            self._send_error(500, str(e))

    def _handle_agents_update(self, data: Dict[str, Any]) -> None:
        """POST /agents - Update agent configuration."""
        try:
            from tools.evolution.framework.agent_registry import AgentRegistry

            agent_name = data.get("name")
            provider = data.get("provider")

            if not agent_name or not provider:
                self._send_error(400, "Missing name or provider")
                return

            registry = AgentRegistry()

            # Extract optional IDs if provided
            agent_id = data.get("agent_id")
            alias_id = data.get("alias_id")

            # Update provider
            # If switching to local, agent_id/alias_id will be cleared by registry if we pass None
            # If switching to bedrock, we need to pass them if they are in the request

            kwargs = {}
            if agent_id is not None:
                kwargs["agent_id"] = agent_id
            if alias_id is not None:
                kwargs["alias_id"] = alias_id

            registry.update_provider(agent_name, provider, **kwargs)

            # Return updated list
            agents = registry.list_agents()
            self._send_json({"status": "ok", "agents": agents})

        except ValueError as e:
            self._send_error(400, str(e))
        except Exception as e:
            logger.error(f"Failed to update agent: {e}")
            self._send_error(500, str(e))

    def _handle_pending_approvals(self) -> None:
        """GET /pending-approvals - Get pending approvals."""
        # For now, return empty list - approvals are not yet implemented
        self._send_json([])

    def _handle_sidekick_chat(self, data: Dict[str, Any]) -> None:
        """POST /sidekick-chat - Handle chat message from sidekick."""
        job_id = data.get("job_id")
        message = data.get("message")

        if not job_id:
            self._send_error(400, "Missing job_id")
            return

        if not message:
            self._send_error(400, "Missing message")
            return

        # For now, return a placeholder response
        # TODO: Integrate with actual chat/LLM system
        self._send_json(
            {
                "response": f"Chat received for job {job_id}: {message}. (Chat functionality coming soon!)",
                "job_id": job_id,
            }
        )

    def _handle_job_conversation(self, job_id: str) -> None:
        """GET /jobs/{job_id}/conversation - Get conversation for a job phase."""
        ctx = self._get_context()
        params = self._parse_query_params()

        # Verify job exists
        job = ctx.store.get_job(job_id)
        if not job:
            self._send_error(404, f"Job not found: {job_id}")
            return

        phase = params.get("phase", "")

        # Try to load conversation from build output files
        conversation = self._load_conversation_for_phase(job_id, phase)

        self._send_json(
            {
                "job_id": job_id,
                "phase": phase,
                "messages": conversation,
            }
        )

    def _handle_job_artifacts(self, job_id: str) -> None:
        """GET /jobs/{job_id}/artifacts - Get artifacts for a job phase."""
        ctx = self._get_context()
        params = self._parse_query_params()

        # Verify job exists
        job = ctx.store.get_job(job_id)
        if not job:
            self._send_error(404, f"Job not found: {job_id}")
            return

        phase = params.get("phase", "")

        # Try to load artifacts from build output files
        artifacts = self._load_artifacts_for_phase(job_id, phase, job.params)

        self._send_json(
            {
                "job_id": job_id,
                "phase": phase,
                "artifacts": artifacts,
            }
        )

    def _load_conversation_for_phase(
        self, job_id: str, phase: str
    ) -> List[Dict[str, Any]]:
        """Load conversation messages for a job phase from build outputs."""
        from pathlib import Path

        messages = []

        # Try to find conversation logs in .context-foundry/conversations/
        cf_dir = Path.home() / ".context-foundry" / "conversations"
        conversation_file = cf_dir / f"conversation-{job_id}.log"

        if conversation_file.exists():
            try:
                content = conversation_file.read_text()
                # Parse the conversation log - it's a text format with messages
                current_role = None
                current_content = []

                for line in content.split("\n"):
                    if line.startswith("[ASSISTANT]"):
                        if current_role and current_content:
                            messages.append(
                                {
                                    "role": current_role,
                                    "content": "\n".join(current_content),
                                }
                            )
                        current_role = "assistant"
                        current_content = [line.replace("[ASSISTANT] ", "")]
                    elif line.startswith("[TOOL_USE]"):
                        if current_role and current_content:
                            messages.append(
                                {
                                    "role": current_role,
                                    "content": "\n".join(current_content),
                                }
                            )
                        current_role = "tool"
                        current_content = [line.replace("[TOOL_USE] ", "")]
                    elif line.startswith("[TOOL_RESULT]"):
                        current_role = "tool_result"
                        current_content = [line.replace("[TOOL_RESULT] ", "")]
                    elif current_role:
                        current_content.append(line)

                if current_role and current_content:
                    messages.append(
                        {"role": current_role, "content": "\n".join(current_content)}
                    )

            except Exception as e:
                logger.error(f"Failed to load conversation for {job_id}: {e}")

        return messages

    def _load_artifacts_for_phase(
        self, job_id: str, phase: str, params: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Load artifacts for a job phase from the working directory."""
        from pathlib import Path

        artifacts = []

        # Get working directory from job params
        working_dir = None
        if params:
            working_dir = params.get("working_directory")

        if not working_dir:
            return artifacts

        working_path = Path(working_dir)
        if not working_path.exists():
            return artifacts

        # Look for common artifact files based on phase
        phase_artifacts = {
            "scout": ["SCOUT_REPORT.md", "analysis.md"],
            "architect": ["ARCHITECT_PLAN.md", "architecture.md", "design.md"],
            "builder": ["*.py", "*.ts", "*.js", "*.tsx", "*.jsx"],
            "test": ["test_*.py", "*_test.py", "*.test.ts", "*.test.js"],
            "documentation": ["README.md", "DOCS.md", "*.md"],
            "deploy": ["Dockerfile", "docker-compose.yml", ".github/workflows/*.yml"],
        }

        patterns = phase_artifacts.get(phase.lower(), [])

        for pattern in patterns:
            try:
                if "*" in pattern:
                    # Glob pattern
                    for file_path in working_path.glob(pattern):
                        if file_path.is_file() and file_path.stat().st_size < 100000:
                            try:
                                content = file_path.read_text()
                                artifacts.append(
                                    {
                                        "name": file_path.name,
                                        "path": str(
                                            file_path.relative_to(working_path)
                                        ),
                                        "type": self._get_artifact_type(file_path.name),
                                        "content": content[
                                            :10000
                                        ],  # Limit content size
                                        "size": file_path.stat().st_size,
                                    }
                                )
                            except Exception:
                                pass
                else:
                    file_path = working_path / pattern
                    if file_path.exists() and file_path.is_file():
                        try:
                            content = file_path.read_text()
                            artifacts.append(
                                {
                                    "name": file_path.name,
                                    "path": pattern,
                                    "type": self._get_artifact_type(file_path.name),
                                    "content": content[:10000],
                                    "size": file_path.stat().st_size,
                                }
                            )
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error loading artifacts for pattern {pattern}: {e}")

        return artifacts

    def _get_artifact_type(self, filename: str) -> str:
        """Determine artifact type from filename."""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext in ("py", "js", "ts", "tsx", "jsx", "rs", "go", "java"):
            return "code"
        elif ext in ("md", "txt", "rst"):
            return "document"
        elif ext in ("json", "yaml", "yml", "toml"):
            return "config"
        elif filename in ("Dockerfile", "Makefile"):
            return "config"
        else:
            return "other"


# =============================================================================
# API SERVER
# =============================================================================


class APIServer:
    """
    HTTP API server for the CF daemon.

    Runs in a separate thread and provides REST endpoints for introspection.
    """

    def __init__(self, store: Store, host: str = "localhost", port: int = 8420):
        self.store = store
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._context = APIContext(store=store)

    def start(self) -> bool:
        """Start the API server in a background thread."""
        if self._server is not None:
            logger.warning("API server already running")
            return False

        try:
            self._server = ThreadingHTTPServer(
                (self.host, self.port),
                APIRequestHandler,
            )
            self._server.api_context = self._context  # type: ignore
            # Set socket timeout so handle_request() doesn't block forever
            self._server.socket.settimeout(1.0)

            self._thread = threading.Thread(
                target=self._run,
                name="http-api-server",
                daemon=True,
            )
            self._thread.start()

            logger.info(f"HTTP API server started at http://{self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start HTTP API server: {e}")
            return False

    def _run(self) -> None:
        """Server main loop."""
        if self._server is None:
            return

        while not self._context.stop_event.is_set():
            try:
                self._server.handle_request()
            except Exception:
                # Socket timeout or other error - just continue if not stopping
                pass

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the API server."""
        if self._server is None:
            return

        logger.info("Stopping HTTP API server...")
        self._context.stop_event.set()

        # Wait for thread to exit (will happen after socket timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        # Close the server socket
        try:
            self._server.server_close()
        except Exception as e:
            logger.warning(f"Error closing server: {e}")

        self._server = None
        self._thread = None
        logger.info("HTTP API server stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return (
            self._server is not None
            and self._thread is not None
            and self._thread.is_alive()
        )

    @property
    def url(self) -> str:
        """Get the server URL."""
        return f"http://{self.host}:{self.port}"

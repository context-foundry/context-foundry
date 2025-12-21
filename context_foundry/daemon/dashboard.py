"""
Lightweight dashboard server for the CF daemon.

Serves a single-page HTML dashboard and streams daemon status via SSE.
The goal is minimal dependencies (stdlib only) and fast startup.
"""

import json
import logging
import mimetypes
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .jobs import JobManager
from .models import Job, JobStatus, PhaseEvent
from .store import Store
from .events import get_event_bus
from . import utils

logger = logging.getLogger(__name__)


@dataclass
class DashboardContext:
    """Shared context for dashboard requests."""

    job_manager: JobManager
    store: Store
    refresh_interval: float = 2.0
    stop_event: threading.Event = field(default_factory=threading.Event)
    # Auth token for destructive operations (generated at startup)
    auth_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))


def _build_phase_snapshot(event: Optional[PhaseEvent]) -> Optional[Dict[str, Any]]:
    """Serialize the latest phase event if present."""
    return utils.build_phase_snapshot(event)


def _read_conversation_preview(
    job: Job, max_lines: int = 12
) -> Optional[Dict[str, Any]]:
    """
    Read the tail of the most recent conversation log for a job.

    Returns None if no log is available (e.g., streaming disabled).
    """
    return utils.read_conversation_preview(job, max_lines)


def _get_file_info(fpath: Path) -> Optional[Dict[str, Any]]:
    """Get file info dict for an artifact, or None if file doesn't exist."""
    return utils.get_file_info(fpath)


def _read_artifact_manifest(
    cf_dir: Path, working_path: Path
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Read artifact manifest from .context-foundry/artifacts.json.
    """
    return utils.read_artifact_manifest(cf_dir, working_path)


def _get_phase_artifacts(job: Job) -> Dict[str, Any]:
    """
    Get phase artifact files for a job.
    """
    return utils.get_phase_artifacts(job)


def _get_job_phases(job: Job) -> List[str]:
    """
    Derive expected phases for a job from its parameters.
    """
    return utils.get_job_phases(job)


def _serialize_job(context: DashboardContext, job: Job) -> Dict[str, Any]:
    """Serialize a job plus lightweight runtime metadata for the dashboard."""
    return utils.serialize_job(context.job_manager, context.store, job)


def build_status_payload(context: DashboardContext) -> Dict[str, Any]:
    """Create a status snapshot for JSON + SSE responses."""
    return utils.build_status_payload(context.job_manager, context.store)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Serve the dashboard HTML, JSON status, and SSE stream."""

    server: "DashboardHTTPServer"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.debug("Dashboard HTTP %s - %s", self.address_string(), format % args)

    def _validate_artifact_path(self, file_path: str) -> Optional[Path]:
        """
        Validate and normalize an artifact file path.
        """
        return utils.validate_artifact_path(file_path)

    def _check_auth(self) -> bool:
        """
        Check if the request has a valid auth token.

        Token must be provided in X-CF-Auth header.
        Returns True if authorized, False otherwise.
        """
        provided_token = self.headers.get("X-CF-Auth", "")
        expected_token = self.server.context.auth_token
        return secrets.compare_digest(provided_token, expected_token)

    def _add_cors_headers(self) -> None:
        """Add CORS headers for localhost origins (dashboard UI on different ports)."""
        origin = self.headers.get("Origin", "")
        if origin and ("localhost" in origin or "127.0.0.1" in origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CF-Auth")

    def _send_json_error(self, status_code: int, message: str) -> None:
        """Send a JSON-formatted error response for API endpoints."""
        body = json.dumps({"error": message, "status": status_code}).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self._add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/dashboard"):
            self._serve_dashboard_asset("/")
        elif parsed.path == "/status":
            self._serve_status()
        elif parsed.path == "/events":
            self._serve_events()
        elif parsed.path == "/artifact":
            self._serve_artifact(parsed.query)
        elif parsed.path == "/job-prompt":
            self._serve_job_prompt(parsed.query)
        elif parsed.path == "/pending-approvals":
            self._serve_pending_approvals()
        elif parsed.path == "/auth-token":
            self._serve_auth_token()
        elif parsed.path == "/phase-prompts":
            self._serve_phase_prompts(parsed.query)
        elif parsed.path == "/phase-state":
            self._serve_phase_state(parsed.query)
        elif parsed.path == "/transaction-stats":
            self._serve_transaction_stats(parsed.query)
        elif parsed.path == "/agent-activity":
            self._serve_agent_activity(parsed.query)
        elif parsed.path == "/job-conversation":
            self._serve_legacy_job_conversation(parsed.query)
        elif parsed.path == "/config":
            self._serve_config()
        elif parsed.path == "/agents":
            self._serve_agents()
        elif parsed.path == "/health":
            self._serve_health()
        # API routes for Vite dashboard
        elif parsed.path == "/api/jobs":
            self._serve_status()
        elif parsed.path.startswith("/api/jobs/"):
            # Parse /api/jobs/{id} or /api/jobs/{id}/artifacts or /api/jobs/{id}/conversation
            path_parts = parsed.path.split("/api/jobs/")[1].split("/")
            job_id = path_parts[0]
            sub_path = path_parts[1] if len(path_parts) > 1 else None
            if sub_path == "artifacts":
                self._serve_job_artifacts(job_id, parsed.query)
            elif sub_path == "conversation":
                self._serve_job_conversation(job_id, parsed.query)
            else:
                self._serve_job_detail(job_id, parsed.query)
        elif parsed.path == "/api/approvals":
            self._serve_pending_approvals()
        elif parsed.path == "/api/settings/team":
            self._serve_team_settings()
        elif parsed.path == "/api/settings/daemon":
            self._serve_config()
        # NEW: Phase Selection API endpoints (Issue #191)
        elif parsed.path == "/api/phases":
            self._serve_phases()
        elif parsed.path == "/api/profiles":
            self._serve_profiles()
        else:
            # Fallback to serving static files (Vite app)
            self._serve_dashboard_asset(parsed.path)

    def _get_recent_file_context(self) -> str:
        """
        Scan for recently modified files to provide context to the agent.
        """
        return utils.get_recent_file_context(self.server.context.store)

    def _serve_dashboard_asset(self, path: str) -> None:
        """Serve static assets for the Vite dashboard."""
        # Locate the dist directory relative to this file
        # context_foundry/daemon/dashboard.py -> .../tools/dashboard/dist
        root_dir = Path(__file__).resolve().parent.parent.parent
        dist_dir = root_dir / "tools" / "dashboard" / "dist"

        if not dist_dir.exists():
            self.send_error(
                404,
                "Dashboard build not found. Run 'npm run build' in tools/dashboard.",
            )
            return

        # Normalize path
        if path.startswith("/"):
            path = path[1:]

        # Default to index.html
        if not path or path == "dashboard":
            path = "index.html"

        target_path = (dist_dir / path).resolve()

        # Security check: ensure we stay within dist_dir
        try:
            target_path.relative_to(dist_dir)
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        # If file exists, serve it
        if target_path.is_file():
            self._serve_file(target_path)
            return

        # Fallback for SPA routing: serve index.html if it's not a found file
        # But we should be careful not to fallback for missing assets (e.g. missing .js)
        if path.startswith("assets/"):
            self.send_error(404, "Asset not found")
            return

        index_path = dist_dir / "index.html"
        if index_path.exists():
            self._serve_file(index_path)
        else:
            self.send_error(404, "index.html not found")

    def _serve_file(self, path: Path) -> None:
        try:
            with open(path, "rb") as f:
                content = f.read()

            ctype, _ = mimetypes.guess_type(path)
            if not ctype:
                ctype = "application/octet-stream"

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error(f"Failed to serve file {path}: {e}")
            self.send_error(500, str(e))

    def do_PUT(self) -> None:  # noqa: N802
        """Handle PUT requests."""
        parsed = urlparse(self.path)

        if parsed.path == "/api/settings/team":
            self._update_team_settings()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/artifact":
            self._save_artifact()
        elif parsed.path == "/approve":
            self._approve_phase()
        elif parsed.path == "/deny":
            self._deny_phase()
        elif parsed.path == "/phase-prompts":
            self._save_phase_prompt()
        elif parsed.path == "/phase-inject":
            self._inject_phase_prompt()
        elif parsed.path == "/phase-start-review":
            self._start_phase_review()
        elif parsed.path == "/phase-acknowledge":
            self._acknowledge_phase()
        elif parsed.path == "/save-system-prompt-to-disk":
            self._save_system_prompt_to_disk()
        elif parsed.path == "/save-input-instruction-to-disk":
            self._save_input_instruction_to_disk()
        elif parsed.path == "/resume-pipeline":
            self._resume_pipeline()
        elif parsed.path in ("/sidekick-chat", "/api/sidekick-chat"):
            self._handle_sidekick_chat()
        elif parsed.path == "/agents":
            self._update_agents()
        elif parsed.path == "/api/settings/test-s3":
            self._test_s3_connection()
        elif parsed.path.startswith("/api/jobs/"):
            # /api/jobs/:id/action
            parts = parsed.path.split("/")
            if len(parts) >= 5:
                job_id = parts[3]
                action = parts[4]
                if action == "cancel":
                    self._cancel_job(job_id)
                elif action == "pause":
                    self._pause_job(job_id)
                elif action == "resume":
                    self._resume_job(job_id)
                else:
                    self.send_error(404, "Unknown job action")
            else:
                self.send_error(404, "Invalid job route")
        else:
            self.send_error(404, "Not Found")

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS preflight requests for cross-origin requests."""
        origin = self.headers.get("Origin", "")
        # Allow CORS from localhost (any port) for the dashboard UI
        if origin and ("localhost" in origin or "127.0.0.1" in origin):
            self.send_response(204)  # No Content
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CF-Auth")
            self.send_header(
                "Access-Control-Max-Age", "86400"
            )  # Cache preflight for 24h
            self.end_headers()
        else:
            self.send_error(403, "CORS not allowed from this origin")

    def _serve_config(self) -> None:
        """Serve provider configuration from ~/.context-foundry/provider_config.json"""
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

        body = json.dumps(config).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_agents(self) -> None:
        """Serve agent configuration from AgentRegistry."""
        try:
            from tools.llm_core.agent_registry import AgentRegistry

            registry = AgentRegistry()
            agents = registry.list_agents()
            body = json.dumps({"agents": agents}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve agents: {e}")
            self._send_json_error(500, str(e))

    def _serve_phases(self) -> None:
        """Serve available phases from PhaseRegistry (Issue #191)."""
        try:
            from tools.mcp_utils.phase_registry import get_registry

            registry = get_registry()
            phases = []
            for phase_def in registry.list_phases():
                phases.append(
                    {
                        "id": phase_def.id,
                        "name": phase_def.name,
                        "description": phase_def.description,
                        "depends_on": phase_def.depends_on,
                        "timeout_seconds": phase_def.timeout_seconds,
                        "can_skip": phase_def.can_skip,
                        "approval_required": phase_def.approval_required,
                    }
                )

            body = json.dumps({"phases": phases}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve phases: {e}")
            self._send_json_error(500, str(e))

    def _serve_profiles(self) -> None:
        """Serve available build profiles from PhaseRegistry (Issue #191)."""
        try:
            from tools.mcp_utils.phase_registry import get_registry

            registry = get_registry()
            profiles = []
            for profile in registry.list_profiles():
                profiles.append(
                    {
                        "name": profile.name,
                        "description": profile.description,
                        "phases": profile.phases,
                    }
                )

            body = json.dumps({"profiles": profiles}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve profiles: {e}")
            self._send_json_error(500, str(e))

    def _serve_health(self) -> None:
        """Serve health check (compatible with API /health)."""
        try:
            # Get job counts
            stats = self.server.context.store.get_job_stats()
            active_jobs = stats.get("running", 0)
            queued_jobs = stats.get("queued", 0)

            body = json.dumps(
                {
                    "status": "ok",
                    "active_jobs": active_jobs,
                    "queued_jobs": queued_jobs,
                    "timestamp": datetime.now().isoformat(),
                    "service": "dashboard",
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve health: {e}")
            self._send_json_error(500, str(e))

    def _serve_job_detail(self, job_id: str, query: str) -> None:
        """Serve details for a specific job."""
        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self._send_json_error(404, f"Job {job_id} not found")
                return

            # Get phases and logs
            phases = self.server.context.store.get_job_phases(job_id)
            logs = self.server.context.store.get_job_logs(job_id, limit=100)

            body = json.dumps({"job": job, "phases": phases, "logs": logs}).encode(
                "utf-8"
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve job detail: {e}")
            self._send_json_error(500, str(e))

    def _serve_job_artifacts(self, job_id: str, query: str) -> None:
        """Serve artifacts for a specific job phase.

        Artifacts are stored in {working_directory}/.context-foundry/:
        - scout-report.md, scout_report.json (Scout)
        - architecture.md, architecture.json (Architect)
        - build-log.md, build-tasks.json (Builder)
        - test-report.md (Test)
        - screenshot-capture-log.md (Screenshot)
        - deploy-log.md (Deploy)
        - session-summary.json (Feedback)
        """
        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self._send_json_error(404, f"Job {job_id} not found")
                return

            # Parse query params for phase
            params = {}
            if query:
                for part in query.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        params[k] = v
            phase = params.get("phase", "").lower()

            # Get working directory
            working_dir = None
            if hasattr(job, "params") and job.params:
                working_dir = job.params.get("working_directory")

            artifacts = []
            if working_dir:
                working_path = Path(working_dir).expanduser().resolve()
                if working_path.exists():
                    # Phase-specific artifact files
                    phase_artifacts = {
                        "scout": [
                            ".context-foundry/scout-report.md",
                            ".context-foundry/scout_report.json",
                        ],
                        "architect": [
                            ".context-foundry/architecture.md",
                            ".context-foundry/architecture.json",
                        ],
                        "builder": [
                            ".context-foundry/build-log.md",
                            ".context-foundry/build-tasks.json",
                        ],
                        "test": [
                            ".context-foundry/test-report.md",
                        ],
                        "screenshot": [
                            ".context-foundry/screenshot-capture-log.md",
                        ],
                        "documentation": [
                            "README.md",
                        ],
                        "deploy": [
                            ".context-foundry/deploy-log.md",
                        ],
                        "feedback": [
                            ".context-foundry/session-summary.json",
                            ".context-foundry/current-phase.json",
                        ],
                    }

                    # Also check docs/ directory for documentation phase
                    if phase == "documentation":
                        docs_dir = working_path / "docs"
                        if docs_dir.exists():
                            for md_file in docs_dir.glob("*.md"):
                                try:
                                    content = md_file.read_text()
                                    artifacts.append(
                                        {
                                            "name": md_file.name,
                                            "path": f"docs/{md_file.name}",
                                            "type": "document",
                                            "content": content,
                                            "size": len(content),
                                        }
                                    )
                                except Exception:
                                    pass

                    patterns = phase_artifacts.get(phase, [])
                    for pattern in patterns:
                        file_path = working_path / pattern
                        if file_path.exists() and file_path.is_file():
                            try:
                                content = file_path.read_text()
                                ext = file_path.suffix.lower()
                                file_type = (
                                    "document" if ext in (".md", ".txt") else "config"
                                )
                                artifacts.append(
                                    {
                                        "name": file_path.name,
                                        "path": pattern,
                                        "type": file_type,
                                        "content": content,
                                        "size": len(content),
                                    }
                                )
                            except Exception:
                                pass

            body = json.dumps(
                {
                    "job_id": job_id,
                    "phase": phase,
                    "artifacts": artifacts,
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve job artifacts: {e}")
            self._send_json_error(500, str(e))

    def _serve_job_conversation(self, job_id: str, query: str) -> None:
        """Serve conversation for a specific job.

        Conversations are stored in {working_directory}/.context-foundry/conversations/
        as both .jsonl (structured) and .log (human-readable) files.
        """
        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self._send_json_error(404, f"Job {job_id} not found")
                return

            # Parse query params for phase
            params = {}
            if query:
                for part in query.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        params[k] = v
            phase = params.get("phase", "").lower()

            # Get working directory
            working_dir = None
            if hasattr(job, "params") and job.params:
                working_dir = job.params.get("working_directory")

            messages = []
            if working_dir:
                working_path = Path(working_dir).expanduser().resolve()
                conversations_dir = working_path / ".context-foundry" / "conversations"
                jsonl_file = conversations_dir / f"conversation-{job_id}.jsonl"
                log_file = conversations_dir / f"conversation-{job_id}.log"

                # Prefer .jsonl for structured data
                if jsonl_file.exists():
                    try:
                        MAX_MESSAGES = 500  # Limit to prevent memory issues
                        with open(jsonl_file, "r") as f:
                            for line_num, line in enumerate(f):
                                if len(messages) >= MAX_MESSAGES:
                                    break
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    event = json.loads(line)
                                    event_type = event.get("event_type", "")

                                    if event_type == "assistant":
                                        text = event.get("text", "")
                                        # Truncate very long messages
                                        if len(text) > 5000:
                                            text = text[:5000] + "... (truncated)"
                                        messages.append(
                                            {
                                                "role": "assistant",
                                                "content": text,
                                                "timestamp": event.get("timestamp", ""),
                                            }
                                        )
                                    elif event_type == "tool_use":
                                        tool_name = event.get("tool_name", "unknown")
                                        # Don't include full tool input to reduce size
                                        messages.append(
                                            {
                                                "role": "assistant",
                                                "content": f"Using tool: {tool_name}",
                                                "timestamp": event.get("timestamp", ""),
                                            }
                                        )
                                    elif event_type == "tool_result":
                                        result_text = event.get("text", "")[:200]
                                        messages.append(
                                            {
                                                "role": "system",
                                                "content": f"Result: {result_text}",
                                                "timestamp": event.get("timestamp", ""),
                                            }
                                        )
                                except json.JSONDecodeError:
                                    continue
                    except Exception as e:
                        logger.error(f"Failed to load jsonl conversation: {e}")

                # Fallback to .log file
                elif log_file.exists():
                    try:
                        content = log_file.read_text()
                        for line in content.split("\n"):
                            line = line.strip()
                            if not line:
                                continue

                            if "] 💬 AGENT:" in line:
                                parts = line.split("] 💬 AGENT:", 1)
                                timestamp = parts[0].lstrip("[") if parts else ""
                                msg_content = parts[1].strip() if len(parts) > 1 else ""
                                messages.append(
                                    {
                                        "role": "assistant",
                                        "content": msg_content,
                                        "timestamp": timestamp,
                                    }
                                )
                            elif "] 🔧 TOOL:" in line:
                                parts = line.split("] 🔧 TOOL:", 1)
                                timestamp = parts[0].lstrip("[") if parts else ""
                                msg_content = parts[1].strip() if len(parts) > 1 else ""
                                messages.append(
                                    {
                                        "role": "assistant",
                                        "content": f"Tool call: {msg_content}",
                                        "timestamp": timestamp,
                                    }
                                )
                            elif "] ✅ RESULT:" in line:
                                parts = line.split("] ✅ RESULT:", 1)
                                timestamp = parts[0].lstrip("[") if parts else ""
                                msg_content = parts[1].strip() if len(parts) > 1 else ""
                                messages.append(
                                    {
                                        "role": "system",
                                        "content": f"Result: {msg_content}",
                                        "timestamp": timestamp,
                                    }
                                )
                    except Exception as e:
                        logger.error(f"Failed to load log conversation: {e}")

            body = json.dumps(
                {
                    "job_id": job_id,
                    "phase": phase,
                    "messages": messages,
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve job conversation: {e}")
            self._send_json_error(500, str(e))

    def _serve_team_settings(self) -> None:
        """Serve team sync settings."""
        try:
            # Read from config file or return defaults
            config_path = Path.home() / ".context-foundry" / "team_settings.json"
            if config_path.exists():
                settings = json.loads(config_path.read_text())
            else:
                settings = {
                    "sync_mode": "local-only",
                    "s3_bucket": "",
                    "s3_prefix": "patterns/",
                    "aws_region": "us-east-1",
                }

            body = json.dumps(settings).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error(f"Failed to serve team settings: {e}")
            self._send_json_error(500, str(e))

    def _update_agents(self) -> None:
        """Update agent configuration."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}

            from tools.llm_core.agent_registry import AgentRegistry

            agent_name = data.get("name")
            provider = data.get("provider")

            if not agent_name or not provider:
                self._send_json_error(400, "Missing name or provider")
                return

            registry = AgentRegistry()

            # Extract optional IDs if provided
            agent_id = data.get("agent_id")
            alias_id = data.get("alias_id")

            kwargs = {}
            if agent_id is not None:
                kwargs["agent_id"] = agent_id
            if alias_id is not None:
                kwargs["alias_id"] = alias_id

            registry.update_provider(agent_name, provider, **kwargs)

            # Return updated list
            agents = registry.list_agents()
            response_body = json.dumps({"status": "ok", "agents": agents}).encode(
                "utf-8"
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        except Exception as e:
            logger.error(f"Failed to update agent: {e}")
            self._send_json_error(500, str(e))

    def _serve_status(self) -> None:
        payload = build_status_payload(self.server.context)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_events(self) -> None:
        """
        Stream events via SSE using the event bus.

        Uses a hybrid approach:
        - Subscribes to event bus for real-time job updates
        - Sends heartbeats every 15 seconds to keep connection alive
        - Falls back to full status updates every 30 seconds for sync
        """
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
            payload = build_status_payload(self.server.context)
            initial_message = f"data: {json.dumps(payload)}\n\n"
            self.wfile.write(initial_message.encode("utf-8"))
            self.wfile.flush()

            last_heartbeat = time.time()
            last_full_sync = time.time()
            heartbeat_interval = 15.0  # seconds
            full_sync_interval = 30.0  # seconds

            while not self.server.context.stop_event.is_set():
                try:
                    # Try to get an event from the queue (with timeout)
                    from queue import Empty

                    try:
                        event = event_queue.get(timeout=1.0)

                        # Convert event to SSE format
                        event_data = event.to_dict()
                        message = f"data: {json.dumps(event_data)}\n\n"
                        self.wfile.write(message.encode("utf-8"))
                        self.wfile.flush()

                    except Empty:
                        pass  # No event, check heartbeat

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

                    # Send full sync periodically (for clients that may have missed events)
                    if now - last_full_sync >= full_sync_interval:
                        payload = build_status_payload(self.server.context)
                        sync_message = f"data: {json.dumps(payload)}\n\n"
                        self.wfile.write(sync_message.encode("utf-8"))
                        self.wfile.flush()
                        last_full_sync = now

                except Exception as e:
                    logger.debug(f"SSE event loop error: {e}")
                    break

        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected; ignore.
            pass
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Dashboard SSE loop error: %s", exc)
        finally:
            # Unsubscribe from event bus
            event_bus.unsubscribe(subscriber_id)

    def _serve_auth_token(self) -> None:
        """Serve the auth token for the UI to use in subsequent requests."""
        # Only allow from localhost for security
        client_host = self.client_address[0]
        if client_host not in ("127.0.0.1", "::1", "localhost"):
            self.send_error(403, "Auth token only available from localhost")
            return

        body = json.dumps(
            {
                "token": self.server.context.auth_token,
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self._add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_artifact(self, query: str) -> None:
        """Serve artifact file content. Query: path=<filepath>"""
        # Require auth for reading artifacts (contains potentially sensitive build data)
        if not self._check_auth():
            self._send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        from urllib.parse import parse_qs

        params = parse_qs(query)
        file_path = params.get("path", [None])[0]

        if not file_path:
            self._send_json_error(400, "Missing 'path' parameter")
            return

        # Security: validate and normalize path to prevent traversal
        path = self._validate_artifact_path(file_path)
        if path is None:
            self._send_json_error(
                403,
                f"Invalid path: must be inside a project with .context-foundry (got: {file_path})",
            )
            return

        try:
            if not path.exists():
                self._send_json_error(404, f"File not found: {file_path}")
                return

            # Limit file size to 1MB
            if path.stat().st_size > 1_000_000:
                self._send_json_error(413, "File too large (max 1MB)")
                return

            content = path.read_text(encoding="utf-8", errors="replace")

            # Determine content type
            suffix = path.suffix.lower()
            content_type = {
                ".md": "text/markdown",
                ".json": "application/json",
                ".txt": "text/plain",
                ".log": "text/plain",
            }.get(suffix, "text/plain")

            body = json.dumps(
                {
                    "path": str(path),
                    "name": path.name,
                    "content": content,
                    "size": len(content),
                    "content_type": content_type,
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        except Exception as exc:
            logger.warning("Error serving artifact %s: %s", file_path, exc)
            self._send_json_error(500, str(exc))

    def _serve_job_prompt(self, query: str) -> None:
        """Serve the original prompt/task that started a job. Query: job_id=<id>"""
        from urllib.parse import parse_qs

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_error(400, "Missing 'job_id' parameter")
            return

        job = self.server.context.store.get_job(job_id)
        if not job:
            self.send_error(404, f"Job not found: {job_id}")
            return

        # Extract prompt/task info from job params
        prompt_info = {
            "job_id": job.id,
            "task": job.params.get("task"),
            "working_directory": job.params.get("working_directory"),
            "mode": job.params.get("mode"),
            "project_type": job.params.get("project_type"),
            "github_repo": job.params.get("github_repo_name"),
            "metadata": job.metadata,
            "created_at": job.created_at.isoformat(),
        }

        body = json.dumps(prompt_info).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_pending_approvals(self) -> None:
        """List all pending approval requests and paused HITL pipelines."""
        try:
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.approval_gates import ApprovalManager

            manager = ApprovalManager()
            pending = manager.list_pending_requests()

            approvals = [req.to_dict() for req in pending]

            # Also check for paused HITL pipelines (not in ApprovalManager)
            # These are jobs that completed a phase and are waiting to resume
            # Cross-check: pipeline job_id must match job.id AND job must not be running
            from .models import JobStatus

            try:
                seen_dirs = set()  # Avoid duplicates
                for job in self.server.context.store.list_jobs():
                    working_dir = job.params.get("working_directory")
                    if working_dir and working_dir not in seen_dirs:
                        seen_dirs.add(working_dir)
                        pipeline_state_file = (
                            Path(working_dir)
                            / ".context-foundry"
                            / "pipeline-state.json"
                        )
                        if pipeline_state_file.exists():
                            try:
                                state = json.loads(pipeline_state_file.read_text())
                                if state.get("state") == "paused":
                                    # Cross-check: verify pipeline belongs to this job
                                    pipeline_job_id = state.get("task_config", {}).get(
                                        "job_id"
                                    )
                                    if pipeline_job_id and pipeline_job_id != job.id:
                                        logger.debug(
                                            f"Pipeline job_id {pipeline_job_id} doesn't match job {job.id}, skipping"
                                        )
                                        continue

                                    # Race condition prevention: don't show paused pipeline if job is in active state
                                    active_states = {
                                        JobStatus.RUNNING,
                                        JobStatus.QUEUED,
                                        JobStatus.WAITING_APPROVAL,
                                    }
                                    if job.status in active_states:
                                        logger.debug(
                                            f"Job {job.id} is in {job.status.value} state, not showing as paused"
                                        )
                                        continue

                                    phases_remaining = state.get("phases_remaining", [])
                                    next_phase = (
                                        phases_remaining[0]
                                        if phases_remaining
                                        else "Unknown"
                                    )
                                    approvals.append(
                                        {
                                            "request_id": f"resume-{job.id}",
                                            "pipeline_id": job.id,
                                            "job_id": job.id,
                                            "working_directory": working_dir,
                                            "phase": next_phase,
                                            "type": "phase_resume",
                                            "status": "pending",
                                            "paused_at": state.get("paused_at"),
                                            "phases_completed": state.get(
                                                "phases_completed", []
                                            ),
                                            "phases_remaining": phases_remaining,
                                        }
                                    )
                            except (json.JSONDecodeError, KeyError) as e:
                                logger.debug(
                                    f"Could not parse pipeline state for {job.id}: {e}"
                                )
            except Exception as e:
                logger.warning(f"Error checking paused pipelines: {e}")

            body = json.dumps({"approvals": approvals}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except ImportError as exc:
            # Module not available - return empty list with warning
            logger.warning("approval_gates module not available: %s", exc)
            body = json.dumps(
                {
                    "approvals": [],
                    "warning": "Approval system not available",
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            logger.warning("Error listing pending approvals: %s", exc)
            self._send_json_error(500, str(exc))

    def _resume_pipeline(self) -> None:
        """Resume a paused HITL pipeline from the next phase."""
        # Auth check - require valid token for destructive operations
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8")) if body else {}

            job_id = data.get("job_id")
            from_phase = data.get("from_phase")

            if not job_id:
                self._send_json_error(400, "Missing 'job_id' in request body")
                return

            # Get the job
            job = self.server.context.store.get_job(job_id)
            if not job:
                self._send_json_error(404, f"Job not found: {job_id}")
                return

            # Race condition prevention: don't resume if job is in an active state
            from .models import JobStatus

            active_states = {
                JobStatus.RUNNING,
                JobStatus.QUEUED,
                JobStatus.WAITING_APPROVAL,
            }
            if job.status in active_states:
                self._send_json_error(
                    409,  # Conflict
                    f"Job {job_id} is in {job.status.value} state. Wait for it to complete before resuming.",
                )
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self._send_json_error(400, "Job has no working directory")
                return

            # Read pipeline state to get next phase
            pipeline_state_file = (
                Path(working_dir) / ".context-foundry" / "pipeline-state.json"
            )
            if not pipeline_state_file.exists():
                self._send_json_error(404, "No pipeline state found")
                return

            try:
                state = json.loads(pipeline_state_file.read_text())
            except json.JSONDecodeError:
                self._send_json_error(500, "Invalid pipeline state JSON")
                return

            if state.get("state") != "paused":
                self._send_json_error(
                    400, f"Pipeline is not paused (state: {state.get('state')})"
                )
                return

            # Verify this is a HITL-enabled pipeline (has pause_after_phases configured)
            # Check both top-level and task_config for pause_after_phases (top-level takes precedence)
            task_config = state.get("task_config", {})
            pause_after_phases = state.get("pause_after_phases") or task_config.get(
                "pause_after_phases"
            )
            execution_mode = state.get("execution_mode") or task_config.get(
                "execution_mode"
            )

            # Allow resume if either: has pause_after_phases OR is in hitl execution mode
            if not pause_after_phases and execution_mode != "hitl":
                self._send_json_error(
                    400,
                    "Pipeline is not in HITL mode (no pause_after_phases configured)",
                )
                return

            # Verify job_id matches the pipeline's job_id
            pipeline_job_id = task_config.get("job_id")
            if pipeline_job_id and pipeline_job_id != job_id:
                self._send_json_error(
                    400,
                    f"Job ID mismatch: pipeline belongs to {pipeline_job_id}, not {job_id}",
                )
                return

            # Determine the phase to resume from
            phases_remaining = state.get("phases_remaining", [])
            if not from_phase and phases_remaining:
                from_phase = phases_remaining[0]
            elif not from_phase:
                self._send_json_error(400, "No phases remaining to resume")
                return

            # Import pipeline state management
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))

            # Resume the job
            # 1. Update status to QUEUED
            # 2. Submit a new job with resume parameters OR update existing job
            # For simplicity, we'll submit a new job that resumes the pipeline

            # Create resume params
            resume_params = job.params.copy()
            resume_params["mode"] = "resume"
            resume_params["resume_from_phase"] = from_phase
            resume_params["job_id"] = job_id  # Reuse ID

            # Submit new job (which will pick up the pipeline state)
            # We need to use a new ID if we want to keep history, but user wants to "resume" this job.
            # However, JobManager.submit_job creates a new job.
            # If we pass job_id, it might overwrite? JobManager.submit_job takes job_id.

            # Check if job is already running (we did this above, but double check)
            if self.server.context.job_manager.get_job(job_id).status in active_states:
                self._send_json_error(409, "Job is already active")
                return

            # Re-submit with same ID
            try:
                self.server.context.job_manager.submit_job(
                    job_type=job.type,
                    params=resume_params,
                    job_id=job_id,
                    priority=10,  # High priority for resume
                )

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._add_cors_headers()
                self.end_headers()
                self.wfile.write(
                    json.dumps({"status": "ok", "job_id": job_id}).encode("utf-8")
                )

            except Exception as e:
                logger.error(f"Failed to resume job: {e}")
                self._send_json_error(500, str(e))

        except Exception as e:
            logger.error(f"Failed to resume pipeline: {e}")
            self._send_json_error(500, str(e))

    def _cancel_job(self, job_id: str) -> None:
        """Cancel a job."""
        try:
            success = self.server.context.job_manager.cancel_job(job_id)
            if success:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._add_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            else:
                self._send_json_error(
                    400, "Failed to cancel job (not found or not running)"
                )
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            self._send_json_error(500, str(e))

    def _pause_job(self, job_id: str) -> None:
        """Pause a job."""
        # Currently not supported by JobManager, but we can try to cancel it and mark as paused?
        # For now, return 501 Not Implemented
        self._send_json_error(501, "Pause not yet implemented")

    def _resume_job(self, job_id: str) -> None:
        """Resume a job."""
        # Reuse _resume_pipeline logic but adapt for no body
        # We need to find the next phase automatically
        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self._send_json_error(404, "Job not found")
                return

            # Call _resume_pipeline logic internally
            # We can mock the request body or refactor.
            # Refactoring is better but risky for "audit".
            # Let's just implement the logic here directly.

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self._send_json_error(400, "Job has no working directory")
                return

            pipeline_state_file = (
                Path(working_dir) / ".context-foundry" / "pipeline-state.json"
            )
            if not pipeline_state_file.exists():
                self._send_json_error(404, "No pipeline state found")
                return

            state = json.loads(pipeline_state_file.read_text())
            phases_remaining = state.get("phases_remaining", [])
            from_phase = phases_remaining[0] if phases_remaining else None

            if not from_phase:
                self._send_json_error(400, "No phases remaining to resume")
                return

            # Re-submit job
            resume_params = job.params.copy()
            resume_params["mode"] = "resume"
            resume_params["resume_from_phase"] = from_phase
            resume_params["job_id"] = job_id

            self.server.context.job_manager.submit_job(
                job_type=job.type, params=resume_params, job_id=job_id, priority=10
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.end_headers()
            self.wfile.write(
                json.dumps({"status": "ok", "job_id": job_id}).encode("utf-8")
            )

        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            self._send_json_error(500, str(e))

    def _update_team_settings(self) -> None:
        """Update team settings."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            settings = json.loads(body) if body else {}

            config_path = Path.home() / ".context-foundry" / "team_settings.json"
            config_path.parent.mkdir(exist_ok=True)
            config_path.write_text(json.dumps(settings, indent=2))

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to update team settings: {e}")
            self._send_json_error(500, str(e))

    def _test_s3_connection(self) -> None:
        """Test S3 connection."""
        try:
            # Mock success for now
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"status": "ok", "message": "Connection successful (mock)"}
                ).encode("utf-8")
            )
        except Exception as e:
            self._send_json_error(500, str(e))

    def _serve_legacy_job_conversation(self, query: str) -> None:
        """Serve full conversation history for a job, grouped by phase. Query: job_id=<id>

        This is the legacy endpoint for /job-conversation. The new API endpoint is
        /api/jobs/{id}/conversation which uses _serve_job_conversation.
        """
        from urllib.parse import parse_qs

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self._send_json_error(400, "Missing 'job_id' parameter")
            return

        try:
            job = self.server.context.store.get_job(job_id)
        except Exception as exc:
            logger.warning(f"Error getting job {job_id}: {exc}")
            self._send_json_error(500, f"Error retrieving job: {exc}")
            return

        if not job:
            self._send_json_error(404, f"Job not found: {job_id}")
            return

        # Locate conversation files
        working_dir = job.params.get("working_directory")
        if not working_dir:
            self._send_json_error(404, "Job has no working directory")
            return

        conversations_dir = Path(working_dir) / ".context-foundry" / "conversations"
        if not conversations_dir.exists():
            self._send_json_error(404, "Conversation logs not found")
            return

        # Read ALL conversation files in the directory (for resumed jobs, phases may be in different files)
        # This ensures Scout phase from original job is included when viewing resumed job
        all_conv_files = sorted(conversations_dir.glob("conversation-*.jsonl"))
        if not all_conv_files:
            self._send_json_error(404, "Conversation logs not found")
            return

        try:
            messages = []
            for conv_file in all_conv_files:
                with open(conv_file, "r") as f:
                    for line in f:
                        if line.strip():
                            try:
                                messages.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
        except Exception as exc:
            self._send_json_error(500, f"Error reading conversation logs: {exc}")
            return

        # Group by phase
        # We need phase timing info. Try PhaseEvents first.
        try:
            phase_events = self.server.context.store.get_phase_events(job.id)
        except Exception as exc:
            logger.warning(f"Error getting phase events for job {job.id}: {exc}")
            phase_events = []

        # If PhaseEvents are missing (e.g. resumed job issue), try to infer from Logs
        phase_timings = []
        if phase_events:
            for p in phase_events:
                # Skip events with None timestamps
                # Note: PhaseEvent has 'timestamp' not 'started_at'
                if p.timestamp is None:
                    continue
                # Skip job-level events (like job_stalled, job_running, etc.)
                # These have phase="_job" and are not actual phase executions
                if p.phase == "_job":
                    continue
                phase_timings.append(
                    {
                        "phase": p.phase,
                        "start": p.timestamp,
                        # Use next phase start as end, or completed_at if last
                        "end": None,
                    }
                )
            # Sort only if we have valid entries
            if phase_timings:
                try:
                    phase_timings.sort(key=lambda x: x["start"])
                except TypeError as e:
                    logger.warning(f"Error sorting phase timings: {e}")
                    phase_timings = []
        else:
            # Fallback: Infer from logs
            logs = self.server.context.store.get_logs(job.id, limit=10000)
            # Group logs by phase to find start/end
            phase_map = {}
            for log in logs:
                if log.phase:
                    if log.phase not in phase_map:
                        phase_map[log.phase] = {
                            "start": log.timestamp,
                            "end": log.timestamp,
                        }
                    else:
                        if log.timestamp < phase_map[log.phase]["start"]:
                            phase_map[log.phase]["start"] = log.timestamp
                        if log.timestamp > phase_map[log.phase]["end"]:
                            phase_map[log.phase]["end"] = log.timestamp

            # Convert to list
            for phase, times in phase_map.items():
                if times.get("start") is not None:
                    phase_timings.append(
                        {"phase": phase, "start": times["start"], "end": times["end"]}
                    )
            # Sort only if we have valid entries
            if phase_timings:
                try:
                    phase_timings.sort(key=lambda x: x["start"])
                except TypeError as e:
                    logger.warning(f"Error sorting fallback phase timings: {e}")
                    phase_timings = []

        # ALWAYS check pipeline-state.json to add active/failed phase even if we have some timings from logs
        # This is critical because logs may only contain completed phases but not the current/running one
        if working_dir:
            pipeline_state_path = (
                Path(working_dir) / ".context-foundry" / "pipeline-state.json"
            )
            if pipeline_state_path.exists():
                try:
                    with open(pipeline_state_path) as f:
                        pipeline_state = json.load(f)

                    # Get phases_completed from pipeline state
                    phases_completed = pipeline_state.get("phases_completed", [])
                    started_at = pipeline_state.get("started_at")
                    resumed_at = pipeline_state.get("resumed_at")

                    # Also get current/running phase from phases_remaining or current_phase
                    current_phase = pipeline_state.get("current_phase")
                    phases_remaining = pipeline_state.get("phases_remaining", [])
                    failed_phase = pipeline_state.get("failed_phase")

                    # Determine the active phase FIRST (before timestamp-dependent logic)
                    # This is critical: the active phase should be added regardless of started_at
                    active_phase = (
                        current_phase
                        or failed_phase
                        or (phases_remaining[0] if phases_remaining else None)
                    )

                    # Parse timestamps with fallbacks
                    first_phase_start = datetime.now(timezone.utc)  # Default fallback
                    active_phase_start = first_phase_start

                    if started_at:
                        try:
                            first_phase_start = datetime.fromisoformat(
                                started_at.replace("Z", "+00:00")
                            )
                            active_phase_start = first_phase_start
                        except (ValueError, TypeError):
                            pass

                    if resumed_at:
                        try:
                            active_phase_start = datetime.fromisoformat(
                                resumed_at.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    # If we have no phase timings at all, add completed phases
                    if not phase_timings:
                        for i, phase in enumerate(phases_completed):
                            phase_timings.append(
                                {
                                    "phase": phase,
                                    "start": first_phase_start,
                                    "end": None,
                                }
                            )

                    # Get existing phases in phase_timings to avoid duplicates
                    existing_phases = {pt["phase"] for pt in phase_timings}

                    # IMPORTANT: Also add the current/running/failed phase so its messages are grouped
                    # This ensures Builder (or any active phase) shows up in the conversation UI
                    # Use resumed_at for the active phase if available (for HITL resumed jobs)
                    if active_phase and active_phase not in existing_phases:
                        phase_timings.append(
                            {
                                "phase": active_phase,
                                "start": active_phase_start,
                                "end": None,
                            }
                        )
                        logger.debug(
                            f"Added active phase {active_phase} to phase timings"
                        )

                except Exception as e:
                    logger.warning(f"Error reading pipeline-state.json: {e}")

        # Sort phase_timings by known PHASE_ORDER to ensure proper ordering
        # This is critical when multiple phases have the same start time (e.g., from pipeline-state.json)
        PHASE_ORDER = [
            "Scout",
            "Architect",
            "Builder",
            "Test",
            "Screenshot",
            "Documentation",
            "Deploy",
            "Feedback",
        ]

        def phase_sort_key(pt):
            phase = pt["phase"]
            try:
                return (PHASE_ORDER.index(phase), pt["start"])
            except ValueError:
                return (len(PHASE_ORDER), pt["start"])  # Unknown phases go last

        phase_timings.sort(key=phase_sort_key)

        # Ensure start times are monotonically increasing after sorting by phase order
        # This fixes issues where:
        # 1. Phases have identical start times (window becomes [start, start) = empty)
        # 2. Later phases have earlier start times (window becomes invalid with end < start)
        from datetime import timedelta

        for i in range(1, len(phase_timings)):
            if phase_timings[i]["start"] <= phase_timings[i - 1]["start"]:
                # Ensure this phase starts after the previous one
                # Add 1 hour offset to create proper windows
                phase_timings[i]["start"] = phase_timings[i - 1]["start"] + timedelta(
                    hours=1
                )

        grouped_conversations = {}

        # Helper to parse timestamp from message
        def parse_msg_time(msg):
            ts = msg.get("timestamp")
            if not ts:
                return None
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return None

        # Assign messages to phases
        for msg in messages:
            msg_time = parse_msg_time(msg)
            if not msg_time:
                continue

            assigned_phase = "Unknown"

            # Find which phase this message belongs to
            for i, pt in enumerate(phase_timings):
                phase_start = pt["start"]
                # Determine end of this phase window
                # If we have a next phase, use its start as the boundary
                if i + 1 < len(phase_timings):
                    phase_end = phase_timings[i + 1]["start"]
                else:
                    # For the last phase, use its inferred end + buffer, or just open-ended
                    phase_end = datetime.max

                if phase_start <= msg_time < phase_end:
                    assigned_phase = pt["phase"]
                    break

            # Handle messages before first phase (e.g. Scout)
            if assigned_phase == "Unknown" and phase_timings:
                if msg_time < phase_timings[0]["start"]:
                    assigned_phase = phase_timings[0][
                        "phase"
                    ]  # Attribute pre-start messages to first phase

            if assigned_phase not in grouped_conversations:
                grouped_conversations[assigned_phase] = []

            grouped_conversations[assigned_phase].append(msg)

        try:
            body = json.dumps({"phases": grouped_conversations}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            logger.warning(f"Error serializing conversation response: {exc}")
            self._send_json_error(500, f"Error generating response: {exc}")

    def _save_artifact(self) -> None:
        """Save edited artifact file content. POST body: {path, content}"""
        # Require auth for destructive operations
        if not self._check_auth():
            self._send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 2_000_000:  # 2MB limit
                self._send_json_error(413, "Request body too large (max 2MB)")
                return

            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            file_path = data.get("path")
            content = data.get("content")

            if not file_path or content is None:
                self._send_json_error(
                    400, "Missing 'path' or 'content' in request body"
                )
                return

            # Security: validate and normalize path to prevent traversal
            path = self._validate_artifact_path(file_path)
            if path is None:
                self._send_json_error(
                    403,
                    f"Invalid path: must be inside a project with .context-foundry (got: {file_path})",
                )
                return

            if not path.parent.exists():
                self._send_json_error(
                    404, f"Parent directory does not exist: {path.parent}"
                )
                return

            # Write the file
            path.write_text(content, encoding="utf-8")
            logger.info("Artifact saved: %s (%d bytes)", path, len(content))

            response = json.dumps(
                {
                    "success": True,
                    "path": str(path),
                    "size": len(content),
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except json.JSONDecodeError as exc:
            self._send_json_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error saving artifact: %s", exc)
            self._send_json_error(500, str(exc))

    def _approve_phase(self) -> None:
        """Approve a pending phase request. POST body: {request_id, approved_by?, reason?}"""
        # Require auth for destructive operations
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            request_id = data.get("request_id")
            if not request_id:
                self.send_error(400, "Missing 'request_id' in request body")
                return

            approved_by = data.get("approved_by", "dashboard_user")
            reason = data.get("reason")

            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.approval_gates import approve_phase

            result = approve_phase(request_id, approved_by, reason)

            if result:
                response = json.dumps(
                    {
                        "success": True,
                        "request_id": request_id,
                        "status": result.status.value,
                    }
                ).encode("utf-8")
                self.send_response(200)
            else:
                response = json.dumps(
                    {
                        "success": False,
                        "error": "Request not found",
                    }
                ).encode("utf-8")
                self.send_response(404)

            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except ImportError as exc:
            logger.warning("approval_gates module not available: %s", exc)
            self.send_error(503, "Approval system not available")
        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error approving phase: %s", exc)
            self.send_error(500, str(exc))

    def _deny_phase(self) -> None:
        """Deny a pending phase request. POST body: {request_id, denied_by?, reason?}"""
        # Require auth for destructive operations
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            request_id = data.get("request_id")
            if not request_id:
                self.send_error(400, "Missing 'request_id' in request body")
                return

            denied_by = data.get("denied_by", "dashboard_user")
            reason = data.get("reason")

            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.approval_gates import deny_phase

            result = deny_phase(request_id, denied_by, reason)

            if result:
                response = json.dumps(
                    {
                        "success": True,
                        "request_id": request_id,
                        "status": result.status.value,
                    }
                ).encode("utf-8")
                self.send_response(200)
            else:
                response = json.dumps(
                    {
                        "success": False,
                        "error": "Request not found",
                    }
                ).encode("utf-8")
                self.send_response(404)

            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except ImportError as exc:
            logger.warning("approval_gates module not available: %s", exc)
            self.send_error(503, "Approval system not available")
        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error denying phase: %s", exc)
            self.send_error(500, str(exc))

    def _serve_phase_prompts(self, query: str) -> None:
        """Get phase handoffs for a job. Query: job_id=<id>

        Returns the actual .md handoff files that humans should review,
        along with phase status for HITL approval flow.
        """
        # Require auth (handoffs may contain sensitive build details)
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        from urllib.parse import parse_qs

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_error(400, "Missing 'job_id' parameter")
            return

        try:
            # Find the job's working directory
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                body = json.dumps(
                    {
                        "handoffs": {},
                        "status": {},
                        "warning": "No working directory for job",
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._add_cors_headers()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Use new lightweight status system
            from tools.mcp_utils.phase_status import get_all_handoffs, get_phase_status

            handoffs = get_all_handoffs(Path(working_dir))
            status = get_phase_status(Path(working_dir))

            body = json.dumps(
                {
                    "handoffs": handoffs,
                    "status": status,
                    "execution_mode": status.get("execution_mode", "autonomous"),
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        except Exception as exc:
            logger.warning("Error serving phase handoffs: %s", exc)
            self.send_error(500, str(exc))

    def _save_phase_prompt(self) -> None:
        """DEPRECATED: Prompt editing is no longer supported.

        In the new HITL workflow, humans review the .md handoff files
        (scout-report.md, architecture.md, etc.) directly instead of
        editing JSON prompt blobs.

        Use GET /phase-prompts to see handoff files and POST /phase-acknowledge
        to approve phases.
        """
        self.send_error(
            410,
            "Prompt editing is deprecated. Review handoff files (.md) directly "
            "and use /phase-acknowledge to approve phases.",
        )

    def _inject_phase_prompt(self) -> None:
        """DEPRECATED: Use /phase-acknowledge instead.

        This legacy endpoint is no longer supported. Use POST /phase-acknowledge
        with {job_id, phase} to approve phases in the new HITL workflow.
        """
        self.send_error(
            410, "This endpoint is deprecated. Use POST /phase-acknowledge instead."
        )

    def _start_phase_review(self) -> None:
        """DEPRECATED: Phase review state is no longer tracked separately.

        In the new HITL workflow, phases are either pending_approval or approved.
        Use GET /phase-prompts to see handoff files and their status.
        """
        self.send_error(
            410,
            "This endpoint is deprecated. Use GET /phase-prompts to view handoff status.",
        )

    def _acknowledge_phase(self) -> None:
        """
        Approve a phase, allowing the next phase to start (HITL mode).
        POST body: {job_id, phase, approved_by?}

        In HITL mode, the agent waits for approval of the previous phase's
        handoff file before starting the next phase.
        """
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            job_id = data.get("job_id")
            phase = data.get("phase")

            if not job_id or not phase:
                self.send_error(400, "Missing 'job_id' or 'phase' in request body")
                return

            # Find job
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_error(400, "Job has no working directory")
                return

            # Use new lightweight status system
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_status import approve_phase, get_phase_status

            approved_by = data.get("approved_by", "dashboard_user")
            success = approve_phase(Path(working_dir), phase, approved_by)

            if not success:
                # Check current status for better error message
                status = get_phase_status(Path(working_dir))
                phase_data = status.get("phases", {}).get(phase, {})
                current_status = phase_data.get("status", "unknown")
                self.send_error(
                    409,
                    f"Cannot approve phase '{phase}' - current status is '{current_status}' "
                    f"(must be 'pending_approval')",
                )
                return

            logger.info(
                "Phase approved: %s/%s by %s - next phase will start",
                job_id[:8],
                phase,
                approved_by,
            )

            response = json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "status": "approved",
                    "approved_by": approved_by,
                    "message": f"Phase {phase} approved. Next phase will start.",
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

            # Auto-resume pipeline if paused
            self._resume_pipeline_if_paused(job_id, working_dir)

        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error approving phase: %s", exc)
            self.send_error(500, str(exc))

    def _resume_pipeline_if_paused(self, job_id: str, working_dir: str) -> None:
        """Resume pipeline if it's in a paused state"""
        try:
            # Import pipeline state
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.pipeline_state import get_pipeline_state
            from .models import JobStatus, JobType

            project_dir = Path(working_dir)
            state = get_pipeline_state(project_dir)

            if not state or not state.phases_remaining:
                return

            # Check if job is already running
            job = self.server.context.store.get_job(job_id)
            if job and job.status == JobStatus.RUNNING:
                logger.info(f"Job {job_id} is still running, not resuming")
                return

            # Submit resume job
            resume_from = state.phases_remaining[0]

            # FIX: Inherit execution_mode from original job to preserve HITL mode
            # Without this, resume jobs default to "autonomous" even if original was "hitl"
            execution_mode = "autonomous"
            if job:
                execution_mode = job.params.get("execution_mode", "autonomous")

            task_config = {
                "task": f"Resume build from {resume_from}",
                "working_directory": str(project_dir),
                "mode": "resume",
                "resume_from_phase": resume_from,
                "timeout_minutes": 90,
                "execution_mode": execution_mode,  # Inherit from original job
            }

            logger.info(
                f"Auto-resuming job {job_id} from phase {resume_from} (mode: {execution_mode})"
            )

            self.server.context.job_manager.submit_job(
                job_type=JobType.AUTONOMOUS_BUILD,
                params=task_config,
                priority=10,
                metadata={
                    "source": "dashboard",
                    "build_type": f"resume_{resume_from.lower()}",
                    "project_name": project_dir.name,
                },
                job_id=job_id,  # Reuse ID to maintain history
            )

        except Exception as e:
            logger.error(f"Failed to auto-resume pipeline: {e}")

    def _save_system_prompt_to_disk(self) -> None:
        """
        Save system prompt edits back to the source file on disk.
        POST body: {job_id, phase, content}
        Writes to: tools/prompts/phases/phase_{phase}.txt
        """
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            job_id = data.get("job_id")
            phase = data.get("phase")
            content = data.get("content")

            if not job_id or not phase or content is None:
                self.send_error(400, "Missing required fields: job_id, phase, content")
                return

            # Validate phase name (prevent path traversal)
            # Allow alphanumeric, underscore, hyphen only
            phase_lower = phase.lower()
            if not re.match(r"^[a-z0-9_-]+$", phase_lower):
                self.send_error(
                    400,
                    f"Invalid phase name '{phase}'. Phase names must contain only "
                    "letters, numbers, underscores, and hyphens.",
                )
                return

            if len(phase_lower) > 50:
                self.send_error(400, "Phase name too long (max 50 characters)")
                return

            # Find the Context Foundry installation root
            # Dashboard is at: context_foundry/daemon/dashboard.py
            # Prompts are at: tools/prompts/phases/phase_*.txt
            cf_root = Path(__file__).parent.parent.parent
            prompts_dir = cf_root / "tools" / "prompts" / "phases"

            # Validate directory exists and is writable
            if not prompts_dir.exists():
                self.send_error(
                    404,
                    f"Prompts directory not found at expected location: {prompts_dir}. "
                    "This may indicate a non-standard installation layout.",
                )
                return

            if not os.access(prompts_dir, os.W_OK):
                self.send_error(
                    403,
                    f"No write permission to prompts directory: {prompts_dir}. "
                    "Check file system permissions.",
                )
                return

            prompt_file = prompts_dir / f"phase_{phase_lower}.txt"

            # Create backup if file exists
            if prompt_file.exists():
                backup_file = prompts_dir / f"phase_{phase_lower}.txt.bak"
                try:
                    import shutil

                    shutil.copy2(prompt_file, backup_file)
                except Exception as backup_err:
                    logger.warning("Could not create backup: %s", backup_err)

            # Write the content to disk
            prompt_file.write_text(content, encoding="utf-8")

            logger.info(
                "System prompt saved to disk: %s/%s -> %s (%d bytes)",
                job_id[:8],
                phase,
                prompt_file,
                len(content),
            )

            response = json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "file_path": str(prompt_file),
                    "bytes_written": len(content),
                    "message": f"System prompt saved to {prompt_file.name}",
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
        except PermissionError as exc:
            self.send_error(
                403,
                f"Permission denied writing to file. Check that the process has write "
                f"access to tools/prompts/phases/. Error: {exc}",
            )
        except OSError as exc:
            self.send_error(
                500,
                f"File system error while saving: {exc}. "
                "Check disk space and file system state.",
            )
        except Exception as exc:
            logger.warning("Error saving system prompt to disk: %s", exc)
            self.send_error(500, str(exc))

    def _save_input_instruction_to_disk(self) -> None:
        """
        Save input instruction to disk in the project's .context-foundry directory.
        Only allowed for HITL (Human-in-the-Loop) jobs.
        POST body: {job_id, phase, content}
        Writes to: {working_dir}/.context-foundry/input-instructions/{phase}-input.txt
        """
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            job_id = data.get("job_id")
            phase = data.get("phase")
            content = data.get("content")

            if not job_id or not phase or content is None:
                self.send_error(400, "Missing required fields: job_id, phase, content")
                return

            # Validate phase name (prevent path traversal)
            # Allow alphanumeric, underscore, hyphen only
            phase_lower = phase.lower()
            if not re.match(r"^[a-z0-9_-]+$", phase_lower):
                self.send_error(
                    400,
                    f"Invalid phase name '{phase}'. Phase names must contain only "
                    "letters, numbers, underscores, and hyphens.",
                )
                return

            if len(phase_lower) > 50:
                self.send_error(400, "Phase name too long (max 50 characters)")
                return

            # Find job to get working directory and execution mode
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_error(404, f"Job not found: {job_id}")
                return

            # HITL mode guard: only allow saving input instructions for HITL jobs
            # Accept various HITL aliases (case-insensitive)
            execution_mode = job.params.get("execution_mode", "autonomous")
            hitl_aliases = {
                "hitl",
                "human_in_the_loop",
                "human-in-the-loop",
                "manual",
                "interactive",
            }
            is_hitl_mode = execution_mode.lower() in hitl_aliases
            if not is_hitl_mode:
                self.send_error(
                    403,
                    f"Input instruction saving is only allowed for HITL jobs. "
                    f"This job has execution_mode='{execution_mode}'. "
                    f"Valid HITL modes: {', '.join(sorted(hitl_aliases))}. "
                    "Autonomous jobs do not support persisting input instructions.",
                )
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_error(
                    400,
                    "Job has no working directory configured. "
                    "Cannot determine where to save input instruction.",
                )
                return

            working_path = Path(working_dir)
            if not working_path.exists():
                self.send_error(
                    404,
                    f"Working directory does not exist: {working_dir}. "
                    "The project may have been moved or deleted.",
                )
                return

            if not os.access(working_path, os.W_OK):
                self.send_error(
                    403,
                    f"No write permission to working directory: {working_dir}. "
                    "Check file system permissions.",
                )
                return

            # Create input-instructions directory if needed
            input_dir = working_path / ".context-foundry" / "input-instructions"
            try:
                input_dir.mkdir(parents=True, exist_ok=True)
            except OSError as mkdir_err:
                self.send_error(
                    500,
                    f"Could not create input-instructions directory: {mkdir_err}",
                )
                return

            # Write the input instruction to disk
            input_file = input_dir / f"{phase_lower}-input.txt"
            input_file.write_text(content, encoding="utf-8")

            logger.info(
                "Input instruction saved to disk: %s/%s -> %s (%d bytes, HITL mode)",
                job_id[:8],
                phase,
                input_file,
                len(content),
            )

            response = json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "file_path": str(input_file),
                    "bytes_written": len(content),
                    "execution_mode": execution_mode,
                    "message": f"Input instruction saved to {input_file.name}",
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
        except PermissionError as exc:
            self.send_error(
                403,
                f"Permission denied writing to file. Check that the process has write "
                f"access to the project's .context-foundry directory. Error: {exc}",
            )
        except OSError as exc:
            self.send_error(
                500,
                f"File system error while saving: {exc}. "
                "Check disk space and file system state.",
            )
        except Exception as exc:
            logger.warning("Error saving input instruction to disk: %s", exc)
            self.send_error(500, str(exc))

    def _serve_phase_state(self, query: str) -> None:
        """
        Get phase states for a job. Query: job_id=<id>&phase=<phase>?
        If phase is omitted, returns all phases.
        """
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        from urllib.parse import parse_qs

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]
        phase = params.get("phase", [None])[0]

        if not job_id:
            self.send_error(400, "Missing 'job_id' parameter")
            return

        try:
            # Find job
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                body = json.dumps(
                    {"phases": {}, "warning": "No working directory for job"}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._add_cors_headers()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Use new lightweight status system
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_status import get_phase_status

            status_data = get_phase_status(Path(working_dir))
            phases_status = status_data.get("phases", {})

            if phase:
                # Single phase
                phase_data = phases_status.get(phase, {})
                result = {
                    "phase": phase,
                    "state": phase_data.get("status", "waiting"),
                    "timestamps": {
                        "running_at": phase_data.get("running_at"),
                        "pending_approval_at": phase_data.get("pending_approval_at"),
                        "approved_at": phase_data.get("approved_at"),
                        "complete_at": phase_data.get("complete_at"),
                    },
                    "approved_by": phase_data.get("approved_by"),
                }
            else:
                # All phases
                result = {
                    "phases": {
                        name: {
                            "state": data.get("status", "waiting"),
                            "approved_at": data.get("approved_at"),
                            "approved_by": data.get("approved_by"),
                        }
                        for name, data in phases_status.items()
                    }
                }

            body = json.dumps(result).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        except Exception as exc:
            logger.warning("Error serving phase state: %s", exc)
            self.send_error(500, str(exc))

    def _serve_transaction_stats(self, query: str) -> None:
        """
        Get overall transaction statistics for a job. Query: job_id=<id>
        """
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        from urllib.parse import parse_qs

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_error(400, "Missing 'job_id' parameter")
            return

        try:
            # Find job
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                body = json.dumps(
                    {"stats": {}, "warning": "No working directory for job"}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._add_cors_headers()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Use new lightweight status system (transaction stats simplified)
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_status import get_phase_status

            status_data = get_phase_status(Path(working_dir))
            phases = status_data.get("phases", {})

            # Compute simplified stats from status
            stats = {
                "total_phases": len(phases),
                "completed_phases": sum(
                    1 for p in phases.values() if p.get("status") == "complete"
                ),
                "pending_phases": sum(
                    1 for p in phases.values() if p.get("status") == "pending_approval"
                ),
                "running_phases": sum(
                    1 for p in phases.values() if p.get("status") == "running"
                ),
                "waiting_phases": sum(
                    1 for p in phases.values() if p.get("status") == "waiting"
                ),
                "failed_phases": sum(
                    1 for p in phases.values() if p.get("status") == "failed"
                ),
                "execution_mode": status_data.get("execution_mode", "autonomous"),
            }

            # Add job-level info
            stats["job_id"] = job_id
            stats["job_status"] = job.status.value
            stats["job_created_at"] = job.created_at.isoformat()
            if job.started_at:
                stats["job_started_at"] = job.started_at.isoformat()
            if job.completed_at:
                stats["job_completed_at"] = job.completed_at.isoformat()
            stats["job_duration_seconds"] = job.duration()

            body = json.dumps(stats).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            logger.warning("Error serving transaction stats: %s", exc)
            self.send_error(500, str(exc))

    def _handle_sidekick_chat(self) -> None:
        """Handle chat messages for the sidekick interface using Claude CLI."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))
            message = data.get("message", "").strip()

            logger.info(f"Sidekick received message: {message[:50]}...")

            if not message:
                self.send_error(400, "Empty message")
                return

            # Try to use Claude CLI for response
            import subprocess
            import shutil
            import os

            claude_path = shutil.which("claude")
            if not claude_path and os.path.exists("/opt/homebrew/bin/claude"):
                claude_path = "/opt/homebrew/bin/claude"

            logger.info(f"Sidekick: Claude path = {claude_path}")

            response_text = None

            if claude_path:
                try:
                    # Simple, direct Claude call
                    simple_prompt = (
                        f"You are a helpful assistant. Respond briefly to: {message}"
                    )
                    logger.info("Sidekick: Running Claude subprocess...")

                    # Ensure node is in PATH for the claude CLI (which is a node script)
                    import platform

                    env = os.environ.copy()
                    if platform.system() == "Windows":
                        # Windows: add common Node.js locations
                        programfiles = os.environ.get(
                            "ProgramFiles", r"C:\Program Files"
                        )
                        appdata = os.environ.get("APPDATA", "")
                        extra_paths = (
                            f"{programfiles}\\nodejs;{appdata}\\npm"
                            if appdata
                            else f"{programfiles}\\nodejs"
                        )
                        env["PATH"] = f"{extra_paths};{env.get('PATH', '')}"
                    else:
                        # macOS/Linux: add homebrew and common locations
                        env["PATH"] = (
                            f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '/usr/bin:/bin')}"
                        )

                    result = subprocess.run(
                        [
                            claude_path,
                            "-p",
                            "--print",
                            "--dangerously-skip-permissions",
                            "--model",
                            "haiku",
                        ],
                        input=simple_prompt,
                        capture_output=True,
                        text=True,
                        timeout=90,
                        env=env,
                    )

                    logger.info(f"Sidekick: Claude returned code {result.returncode}")

                    if result.returncode == 0 and result.stdout:
                        response_text = result.stdout.strip()
                        logger.info(
                            f"Sidekick: Got response of {len(response_text)} chars"
                        )
                    else:
                        logger.warning(
                            f"Sidekick: Claude failed - stderr: {result.stderr[:200] if result.stderr else 'none'}"
                        )

                except subprocess.TimeoutExpired:
                    logger.warning("Sidekick: Claude timed out after 90s")
                except Exception as e:
                    logger.warning(f"Sidekick: Claude error - {e}")

            if not response_text:
                response_text = (
                    "I'm having trouble connecting right now. Please try again."
                )

            response = json.dumps({"response": response_text}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return

            # OLD CODE BELOW - keeping for reference but bypassed
            if claude_path:
                try:
                    logger.info(f"Attempting to use Claude CLI at: {claude_path}")
                    # Get current job context - prioritized by importance
                    store = self.server.context.store

                    context_parts = []

                    # 1. PERSONA & SYSTEM INSTRUCTIONS (The "Brain" of the operation)
                    system_preamble = (
                        "You are the Context Foundry Agent. You are empathetic, jovial, happy, fun, relaxed, and calculated, "
                        "but always professional. You are the 'Sidekick' to the user in this enterprise environment.\n\n"
                        "YOUR CAPABILITIES:\n"
                        "1. You can guide the user to run Context Foundry commands.\n"
                        "2. You can explain what's happening in their project.\n"
                        "3. You are AWARE of the files they are working on (see 'Context' section below).\n\n"
                        "COMMAND MAPPING:\n"
                        "If the user asks to build something, run a phase, or start a project, you should suggest the appropriate 'cf' command.\n"
                        "- 'cf scout': To research or plan.\n"
                        "- 'cf architect': To design architecture.\n"
                        "- 'cf build': To run the full pipeline.\n\n"
                        "If proposing a command, format it clearly like: `Run: cf command ...` and ask if they want to proceed.\n"
                    )
                    context_parts.append(system_preamble)

                    # 2. FILE CONTEXT (The "Eyes" of the operation)
                    try:
                        file_context = self._get_recent_file_context()
                        context_parts.append(file_context)
                    except Exception as e:
                        logger.warning(f"Failed to get file context: {e}")

                    # 3. JOB STATUS CONTEXT (The "Ears" of the operation)
                    # PRIORITY 1: Check for pending HITL approvals (most urgent)
                    try:
                        from tools.mcp_utils.approval_gates import ApprovalManager

                        approval_manager = ApprovalManager()
                        pending_approvals = approval_manager.list_pending_requests()
                        if pending_approvals:
                            context_parts.append(
                                f"⚠️ JOBS WAITING FOR YOUR APPROVAL ({len(pending_approvals)}):"
                            )
                            for req in pending_approvals[:3]:  # Show top 3
                                context_parts.append(
                                    f"  - {req.request_id[:8]}: Phase '{req.phase}' for {Path(req.working_directory).name}"
                                )
                            if len(pending_approvals) > 3:
                                context_parts.append(
                                    f"  ... and {len(pending_approvals) - 3} more"
                                )
                    except Exception as e:
                        logger.debug(f"Could not check pending approvals: {e}")

                    # PRIORITY 2: Currently RUNNING jobs
                    try:
                        from .models import JobStatus

                        running_jobs = store.list_jobs(
                            status=JobStatus.RUNNING, limit=10
                        )
                        if running_jobs:
                            context_parts.append(
                                f"\n🔄 CURRENTLY RUNNING ({len(running_jobs)}):"
                            )
                            for job in running_jobs[:3]:
                                task_name = job.params.get(
                                    "task", job.params.get("initial_prompt", "Unknown")
                                )[:40]
                                context_parts.append(f"  - {job.id[:8]}: {task_name}")
                            if len(running_jobs) > 3:
                                context_parts.append(
                                    f"  ... and {len(running_jobs) - 3} more"
                                )
                    except Exception as e:
                        logger.debug(f"Could not check running jobs: {e}")

                    # PRIORITY 3: Jobs waiting for approval (WAITING_APPROVAL status)
                    try:
                        waiting_jobs = store.list_jobs(
                            status=JobStatus.WAITING_APPROVAL, limit=10
                        )
                        if waiting_jobs:
                            context_parts.append(
                                f"\n⏸️ PAUSED - WAITING FOR APPROVAL ({len(waiting_jobs)}):"
                            )
                            for job in waiting_jobs[:3]:
                                task_name = job.params.get(
                                    "task", job.params.get("initial_prompt", "Unknown")
                                )[:40]
                                context_parts.append(f"  - {job.id[:8]}: {task_name}")
                    except Exception as e:
                        logger.debug(f"Could not check waiting jobs: {e}")

                    # PRIORITY 4: Recently failed jobs (informational, not urgent)
                    try:
                        failed_jobs = store.list_jobs(status=JobStatus.FAILED, limit=5)
                        if (
                            failed_jobs and not context_parts
                        ):  # Only show if nothing more important
                            context_parts.append(
                                f"\n❌ RECENT FAILURES ({len(failed_jobs)}):"
                            )
                            for job in failed_jobs[:2]:
                                task_name = job.params.get(
                                    "task", job.params.get("initial_prompt", "Unknown")
                                )[:40]
                                context_parts.append(f"  - {job.id[:8]}: {task_name}")
                        elif failed_jobs:
                            # Just mention count if there are more important things
                            context_parts.append(
                                f"\n(Also {len(failed_jobs)} recent failures)"
                            )
                    except Exception as e:
                        logger.debug(f"Could not check failed jobs: {e}")

                    # Build the complete system prompt from context_parts + instructions
                    build_instructions = (
                        "\n\nBUILD INSTRUCTIONS:\n"
                        "- If the user wants to build something, confirm you are starting it.\n"
                        "- To trigger the build, append this tag to the end of your response:\n"
                        "  [[START_BUILD: <short_description_of_project>]]\n"
                        "- Assume the default directory (~/homelab/) unless specified."
                    )
                    context_parts.append(build_instructions)
                    system_prompt = "\n".join(context_parts)

                    # Get history from context (initialize if needed)
                    if not hasattr(self.server.context, "sidekick_history"):
                        self.server.context.sidekick_history = []

                    # Format history for prompt
                    history_text = ""
                    for entry in self.server.context.sidekick_history[
                        -5:
                    ]:  # Keep last 5 turns
                        history_text += f"User: {entry['user']}\nYou: {entry['ai']}\n"

                    full_prompt = f"{system_prompt}\n\nConversation History:\n{history_text}\nUser says: {message}\n\nYour response:"

                    # Call claude CLI with haiku for fast responses
                    logger.info("Running claude subprocess with haiku...")
                    result = subprocess.run(
                        [
                            claude_path,
                            "-p",
                            "--print",
                            "--dangerously-skip-permissions",
                            "--model",
                            "haiku",
                        ],
                        input=full_prompt,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    response_text = None
                    if result.returncode == 0 and result.stdout:
                        response_text = result.stdout.strip()
                        logger.info(
                            f"Claude CLI success. Response length: {len(response_text)}"
                        )
                    elif result.returncode != 0:
                        logger.warning(
                            f"Claude CLI returned code {result.returncode}. "
                            f"Stdout: {result.stdout[:200] if result.stdout else 'empty'}... "
                            f"Stderr: {result.stderr[:500] if result.stderr else 'empty'}"
                        )
                    else:
                        logger.warning(
                            f"Claude CLI failed. Code: {result.returncode}, Stderr: {result.stderr}"
                        )

                    if response_text:
                        # Clean up any quotes if Claude adds them
                        if response_text.startswith('"') and response_text.endswith(
                            '"'
                        ):
                            response_text = response_text[1:-1]

                        # Check for build trigger
                        import re

                        build_match = re.search(
                            r"\[\[START_BUILD:\s*(.*?)\]\]", response_text
                        )
                        if build_match:
                            description = build_match.group(1).strip()
                            # Remove tag from response
                            response_text = response_text.replace(
                                build_match.group(0), ""
                            ).strip()

                            # Trigger build
                            try:
                                from datetime import datetime
                                import os
                                from .models import JobType

                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                # Create a safe directory name from description (first few words)
                                safe_desc = "".join(
                                    c if c.isalnum() else "_" for c in description[:20]
                                ).strip("_")
                                project_dir = (
                                    Path.home() / "homelab" / f"{safe_desc}_{timestamp}"
                                )
                                # NOTE: Don't mkdir here - runner.py will append random suffix
                                # and create the final directory to avoid duplicates

                                job_params = {
                                    "working_directory": str(project_dir),
                                    "initial_prompt": description,
                                }

                                job = self.server.context.job_manager.submit_job(
                                    job_type=JobType.AUTONOMOUS_BUILD,
                                    params=job_params,
                                    priority=10,
                                )
                                logger.info(
                                    f"Sidekick triggered build job {job.id} for: {description}"
                                )

                            except Exception as e:
                                logger.error(f"Failed to trigger sidekick build: {e}")
                                response_text += f"\n(Oops, I tried to start the build but tripped over a wire: {e})"

                except Exception as e:
                    logger.warning("Sidekick Claude CLI failed: %s", e)
                    response_text = None
            else:
                response_text = None

            # Fallback if Claude failed
            if not response_text:
                response_text = "I'm having trouble connecting to my brain right now. Please try again in a moment."

            if not response_text:
                response_text = "I'm speechless! (Internal error)"

            # Save to history if we have a valid response
            if hasattr(self.server.context, "sidekick_history"):
                self.server.context.sidekick_history.append(
                    {"user": message, "ai": response_text}
                )

            response = json.dumps({"response": response_text}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except Exception as exc:
            logger.error("Error in sidekick chat: %s", exc, exc_info=True)
            self.send_error(500, str(exc))

    def _serve_agent_activity(self, query: str) -> None:
        """
        SSE endpoint for real-time agent activity during phase execution.
        Streams tool calls, token updates, and summaries.
        Query: job_id=<id>&auth=<token>
        """
        from urllib.parse import parse_qs

        params = parse_qs(query)

        # Require auth - conversation logs may contain sensitive data
        # Accept token from header OR query param (EventSource doesn't support headers)
        query_auth = params.get("auth", [None])[0]
        header_auth = self.headers.get("X-CF-Auth", "")
        expected_token = self.server.context.auth_token

        auth_valid = False
        if header_auth and secrets.compare_digest(header_auth, expected_token):
            auth_valid = True
        elif query_auth and secrets.compare_digest(query_auth, expected_token):
            auth_valid = True

        if not auth_valid:
            self.send_error(401, "Unauthorized: missing or invalid auth token")
            return

        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_error(400, "Missing 'job_id' parameter")
            return

        # Find job
        job = self.server.context.store.get_job(job_id)
        if not job:
            self.send_error(404, f"Job not found: {job_id}")
            return

        working_dir = job.params.get("working_directory")
        if not working_dir:
            self.send_error(400, "No working directory for job")
            return

        # Set up SSE response
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self._add_cors_headers()
        self.end_headers()

        # Find conversation log file
        conversations_dir = Path(working_dir) / ".context-foundry" / "conversations"
        jsonl_pattern = "conversation-*.jsonl"

        last_position = 0
        last_event_count = 0
        input_tokens = 0
        output_tokens = 0

        # Pre-scan logs to get initial token counts
        if conversations_dir.exists():
            jsonl_files = list(conversations_dir.glob(jsonl_pattern))
            if jsonl_files:
                latest_jsonl = max(jsonl_files, key=lambda p: p.stat().st_mtime)
                try:
                    with open(latest_jsonl, "r") as f:
                        for line in f:
                            try:
                                data = json.loads(line)
                                if (
                                    data.get("type") == "usage"
                                    or data.get("event_type") == "usage"
                                ):
                                    input_tokens = data.get(
                                        "input_tokens", input_tokens
                                    )
                                    output_tokens = data.get(
                                        "output_tokens", output_tokens
                                    )
                            except Exception:
                                pass
                except Exception:
                    pass

        try:
            job_completed_detected = False

            while not self.server.context.stop_event.is_set():
                # Check if job is still running
                job = self.server.context.store.get_job(job_id)
                if job and job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                    job_completed_detected = True
                    # We don't break yet - we want to process any remaining logs first

                # Find latest JSONL file
                if conversations_dir.exists():
                    jsonl_files = list(conversations_dir.glob(jsonl_pattern))
                    if jsonl_files:
                        latest_jsonl = max(jsonl_files, key=lambda p: p.stat().st_mtime)

                        try:
                            with open(latest_jsonl, "r") as f:
                                f.seek(last_position)
                                new_content = f.read()
                                last_position = f.tell()

                            if new_content:
                                # Process each line (JSONL format)
                                for line in new_content.strip().split("\n"):
                                    if not line.strip():
                                        continue
                                    try:
                                        event_data = json.loads(line)
                                        # Transform to activity event format
                                        activity_event = (
                                            self._transform_conversation_event(
                                                event_data, input_tokens, output_tokens
                                            )
                                        )
                                        if activity_event:
                                            # Update token counts from event
                                            if (
                                                activity_event.get("type")
                                                == "token_update"
                                            ):
                                                input_tokens = activity_event.get(
                                                    "input_tokens", input_tokens
                                                )
                                                output_tokens = activity_event.get(
                                                    "output_tokens", output_tokens
                                                )

                                            self.wfile.write(
                                                f"data: {json.dumps(activity_event)}\n\n".encode()
                                            )
                                            self.wfile.flush()
                                            last_event_count += 1
                                    except json.JSONDecodeError:
                                        continue

                        except Exception as exc:
                            logger.debug("Error reading conversation log: %s", exc)

                # Send periodic token update even without new events
                # OR if we have initial tokens but haven't sent any events yet
                if last_event_count > 0 or (input_tokens > 0 and last_event_count == 0):
                    token_event = {
                        "type": "token_update",
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "context_percent": (input_tokens / 200000) * 100
                        if input_tokens
                        else 0,
                    }
                    self.wfile.write(f"data: {json.dumps(token_event)}\n\n".encode())
                    self.wfile.flush()

                    # If we just sent the initial update, mark as having sent events
                    if last_event_count == 0:
                        last_event_count = 1

                # If job is complete and we've done a pass, exit
                if job_completed_detected:
                    # Send completion event
                    event = {
                        "type": "phase_complete",
                        "status": job.status.value if job else "unknown",
                    }
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()
                    break

                time.sleep(0.5)  # Poll every 500ms for lower latency

        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected
            return
        except Exception as exc:
            logger.warning("Agent activity SSE error: %s", exc)

    def _transform_conversation_event(
        self, event_data: Dict[str, Any], input_tokens: int, output_tokens: int
    ) -> Optional[Dict[str, Any]]:
        """
        Transform a conversation log event to an activity event for the dashboard.
        """
        # Support both "type" and "event_type" keys (conversation logs use "event_type")
        event_type = event_data.get("type") or event_data.get("event_type", "")

        if event_type == "tool_use":
            # ConversationEvent uses 'tool_name' and 'tool_input'
            tool_name = event_data.get("tool_name") or event_data.get("tool", "unknown")
            tool_input = event_data.get("tool_input") or event_data.get("input", {})

            # Create a preview of the input
            input_preview = ""
            if isinstance(tool_input, dict):
                if "file_path" in tool_input:
                    input_preview = tool_input["file_path"]
                elif "pattern" in tool_input:
                    input_preview = tool_input["pattern"]
                elif "command" in tool_input:
                    cmd = tool_input["command"]
                    input_preview = cmd[:100] + "..." if len(cmd) > 100 else cmd
                elif "query" in tool_input:
                    input_preview = tool_input["query"]
                else:
                    # Take first key-value as preview
                    for k, v in tool_input.items():
                        if isinstance(v, str) and len(v) < 100:
                            input_preview = f"{k}: {v}"
                            break
            elif isinstance(tool_input, str):
                input_preview = tool_input[:100]

            return {
                "type": "tool_start",
                "tool_name": tool_name,
                "input_preview": input_preview[:200] if input_preview else "",
            }

        elif event_type == "tool_result":
            # ConversationEvent uses 'tool_name' and 'text' (for content)
            tool_name = event_data.get("tool_name") or event_data.get("tool", "unknown")
            is_error = event_data.get("is_error", False)
            content = event_data.get("text") or event_data.get("content", "")

            # Create output preview
            output_preview = ""
            if isinstance(content, str):
                output_preview = (
                    content[:100] + "..." if len(content) > 100 else content
                )

            return {
                "type": "tool_complete",
                "tool_name": tool_name,
                "success": not is_error,
                "error": content[:200] if is_error else None,
                "input_preview": output_preview,
            }

        elif event_type == "assistant":
            # Assistant message - extract any summary/thinking
            text = event_data.get("text", "")
            if text:
                # Take first paragraph as summary
                summary = text.split("\n\n")[0][:500]
                return {
                    "type": "summary_update",
                    "summary": summary,
                }

        elif event_type == "usage":
            # Token usage update (from ConversationEvent.USAGE)
            current_input = event_data.get("input_tokens", input_tokens)
            return {
                "type": "token_update",
                "input_tokens": current_input,
                "output_tokens": event_data.get("output_tokens", output_tokens),
                "context_percent": (current_input / 200000) * 100,
            }

        return None


class DashboardHTTPServer(ThreadingHTTPServer):
    """HTTP server with attached dashboard context."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, context: DashboardContext):
        super().__init__(server_address, RequestHandlerClass)
        self.context = context


class DashboardServer:
    """Wrapper to manage the dashboard HTTP server lifecycle."""

    def __init__(
        self,
        host: str,
        port: int,
        job_manager: JobManager,
        store: Store,
        refresh_interval: float = 2.0,
    ):
        self.host = host
        self.port = port
        self._thread: Optional[threading.Thread] = None
        self.context = DashboardContext(
            job_manager=job_manager,
            store=store,
            refresh_interval=refresh_interval,
        )
        handler = DashboardRequestHandler
        self.httpd = DashboardHTTPServer(
            (self.host, self.port), handler, context=self.context
        )

    def start(self) -> None:
        """Start the HTTP server in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        def _serve() -> None:
            logger.info(
                "Dashboard server listening on http://%s:%s", self.host, self.port
            )
            try:
                self.httpd.serve_forever()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Dashboard server stopped unexpectedly: %s", exc)

        self._thread = threading.Thread(
            target=_serve, name="DashboardServer", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Shutdown the HTTP server."""
        self.context.stop_event.set()
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error shutting down dashboard server: %s", exc)

        if self._thread:
            self._thread.join(timeout=5.0)

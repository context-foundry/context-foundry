"""
Lightweight dashboard server for the CF daemon.

Serves a single-page HTML dashboard and streams daemon status via SSE.
The goal is minimal dependencies (stdlib only) and fast startup.

This module has been refactored to use modular handlers from the api/ package.
"""

import json
import logging
import mimetypes
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .jobs import JobManager
from .models import Job, PhaseEvent
from .store import Store
from . import utils

# Import handler mixins
from .api.handlers import (
    JobHandlersMixin,
    ArtifactHandlersMixin,
    ApprovalHandlersMixin,
    PhaseHandlersMixin,
    SidekickHandlersMixin,
    SettingsHandlersMixin,
    StatusHandlersMixin,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MODULE-LEVEL FUNCTIONS (kept for backward compatibility with tests)
# =============================================================================


@dataclass
class DashboardContext:
    """Shared context for dashboard requests."""

    job_manager: JobManager
    store: Store
    refresh_interval: float = 2.0
    stop_event: threading.Event = field(default_factory=threading.Event)
    auth_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))


def _build_phase_snapshot(event: Optional[PhaseEvent]) -> Optional[Dict[str, Any]]:
    """Serialize the latest phase event if present."""
    return utils.build_phase_snapshot(event)


def _read_conversation_preview(
    job: Job, max_lines: int = 12
) -> Optional[Dict[str, Any]]:
    """Read the tail of the most recent conversation log for a job."""
    return utils.read_conversation_preview(job, max_lines)


def _get_file_info(fpath: Path) -> Optional[Dict[str, Any]]:
    """Get file info dict for an artifact, or None if file doesn't exist."""
    return utils.get_file_info(fpath)


def _read_artifact_manifest(
    cf_dir: Path, working_path: Path
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Read artifact manifest from .context-foundry/artifacts.json."""
    return utils.read_artifact_manifest(cf_dir, working_path)


def _get_phase_artifacts(job: Job) -> Dict[str, Any]:
    """Get phase artifact files for a job."""
    return utils.get_phase_artifacts(job)


def _get_job_phases(job: Job) -> list:
    """Derive expected phases for a job from its parameters."""
    return utils.get_job_phases(job)


def _serialize_job(context: DashboardContext, job: Job) -> Dict[str, Any]:
    """Serialize a job plus lightweight runtime metadata for the dashboard."""
    return utils.serialize_job(context.job_manager, context.store, job)


def build_status_payload(context: DashboardContext) -> Dict[str, Any]:
    """Create a status snapshot for JSON + SSE responses."""
    return utils.build_status_payload(context.job_manager, context.store)


# =============================================================================
# REQUEST HANDLER
# =============================================================================


class DashboardRequestHandler(
    JobHandlersMixin,
    ArtifactHandlersMixin,
    ApprovalHandlersMixin,
    PhaseHandlersMixin,
    SidekickHandlersMixin,
    SettingsHandlersMixin,
    StatusHandlersMixin,
    BaseHTTPRequestHandler,
):
    """
    Serve the dashboard HTML, JSON status, and SSE stream.

    This handler uses mixins to organize functionality by domain.
    Each mixin provides handlers for a specific area (jobs, artifacts, etc.).
    """

    server: "DashboardHTTPServer"

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("Dashboard HTTP %s - %s", self.address_string(), format % args)

    # Legacy method wrappers for backward compatibility
    def _validate_artifact_path(self, file_path: str) -> Optional[Path]:
        return utils.validate_artifact_path(file_path)

    def _check_auth(self) -> bool:
        return self.check_auth()

    def _add_cors_headers(self) -> None:
        self.add_cors_headers()

    def _send_json_error(self, status_code: int, message: str) -> None:
        self.send_json_error(status_code, message)

    # =========================================================================
    # HTTP METHOD HANDLERS (Routing)
    # =========================================================================

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parsed.query

        # Route to appropriate handler
        routes = {
            "/": lambda: self._serve_dashboard_asset("/"),
            "/dashboard": lambda: self._serve_dashboard_asset("/"),
            "/status": self.handle_status,
            "/events": self.handle_events,
            "/artifact": lambda: self.handle_serve_artifact(query),
            "/job-prompt": lambda: self.handle_job_prompt(query),
            "/pending-approvals": self.handle_pending_approvals,
            "/auth-token": self.handle_auth_token,
            "/phase-prompts": lambda: self.handle_phase_prompts(query),
            "/phase-state": lambda: self.handle_phase_state(query),
            "/transaction-stats": lambda: self.handle_transaction_stats(query),
            "/agent-activity": lambda: self._serve_agent_activity(query),
            "/job-conversation": lambda: self._serve_legacy_job_conversation(query),
            "/config": self.handle_config,
            "/agents": self.handle_agents,
            "/health": self.handle_health,
            # API routes for Vite dashboard
            "/api/jobs": self.handle_status,
            "/api/approvals": self.handle_pending_approvals,
            "/api/settings/team": self.handle_team_settings,
            "/api/settings/daemon": self.handle_config,
            "/api/phases": self.handle_phases,
            "/api/profiles": self.handle_profiles,
        }

        if path in routes:
            routes[path]()
        elif path.startswith("/api/jobs/"):
            self._route_api_jobs_get(path, query)
        else:
            self._serve_dashboard_asset(path)

    def _route_api_jobs_get(self, path: str, query: str) -> None:
        """Route /api/jobs/{id}/* requests."""
        path_parts = path.split("/api/jobs/")[1].split("/")
        job_id = path_parts[0]
        sub_path = path_parts[1] if len(path_parts) > 1 else None

        if sub_path == "artifacts":
            self.handle_job_artifacts(job_id, query)
        elif sub_path == "conversation":
            self.handle_job_conversation(job_id, query)
        else:
            self.handle_job_detail(job_id, query)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/settings/team":
            self.handle_update_team_settings()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        routes = {
            "/artifact": self.handle_save_artifact,
            "/approve": self.handle_approve_phase,
            "/deny": self.handle_deny_phase,
            "/phase-prompts": self.handle_save_phase_prompt,
            "/phase-inject": self.handle_inject_phase_prompt,
            "/phase-start-review": self.handle_start_phase_review,
            "/phase-acknowledge": self.handle_acknowledge_phase,
            "/save-system-prompt-to-disk": self._save_system_prompt_to_disk,
            "/save-input-instruction-to-disk": self._save_input_instruction_to_disk,
            "/resume-pipeline": self.handle_resume_pipeline,
            "/sidekick-chat": self.handle_sidekick_chat,
            "/api/sidekick-chat": self.handle_sidekick_chat,
            "/agents": self.handle_update_agents,
            "/api/settings/test-s3": self.handle_test_s3_connection,
        }

        if path in routes:
            routes[path]()
        elif path.startswith("/api/jobs/"):
            self._route_api_jobs_post(path)
        else:
            self.send_error(404, "Not Found")

    def _route_api_jobs_post(self, path: str) -> None:
        """Route /api/jobs/{id}/{action} POST requests."""
        parts = path.split("/")
        if len(parts) >= 5:
            job_id = parts[3]
            action = parts[4]
            if action == "cancel":
                self.handle_cancel_job(job_id)
            elif action == "pause":
                self.handle_pause_job(job_id)
            elif action == "resume":
                self.handle_resume_job(job_id)
            else:
                self.send_error(404, "Unknown job action")
        else:
            self.send_error(404, "Invalid job route")

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        origin = self.headers.get("Origin", "")
        if origin and ("localhost" in origin or "127.0.0.1" in origin):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CF-Auth")
            self.send_header("Access-Control-Max-Age", "86400")
            self.end_headers()
        else:
            self.send_error(403, "CORS not allowed from this origin")

    # =========================================================================
    # STATIC FILE SERVING
    # =========================================================================

    def _serve_dashboard_asset(self, path: str) -> None:
        """Serve static assets for the Vite dashboard."""
        root_dir = Path(__file__).resolve().parent.parent.parent
        dist_dir = root_dir / "tools" / "dashboard" / "dist"

        if not dist_dir.exists():
            self.send_error(
                404,
                "Dashboard build not found. Run 'npm run build' in tools/dashboard.",
            )
            return

        if path.startswith("/"):
            path = path[1:]
        if not path or path == "dashboard":
            path = "index.html"

        target_path = (dist_dir / path).resolve()

        try:
            target_path.relative_to(dist_dir)
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        if target_path.is_file():
            self._serve_file(target_path)
            return

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

    # =========================================================================
    # LEGACY ENDPOINTS (complex, not yet extracted to mixins)
    # =========================================================================

    def _serve_legacy_job_conversation(self, query: str) -> None:
        """Legacy endpoint for /job-conversation - delegates to imported function."""
        from urllib.parse import parse_qs

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_json_error(400, "Missing 'job_id' parameter")
            return

        try:
            job = self.server.context.store.get_job(job_id)
        except Exception as exc:
            logger.warning(f"Error getting job {job_id}: {exc}")
            self.send_json_error(500, f"Error retrieving job: {exc}")
            return

        if not job:
            self.send_json_error(404, f"Job not found: {job_id}")
            return

        working_dir = job.params.get("working_directory")
        if not working_dir:
            self.send_json_response(
                {
                    "phases": [],
                    "warning": "No working directory for job",
                }
            )
            return

        from tools.mcp_utils.phase_status import get_phase_status

        status_data = get_phase_status(Path(working_dir))
        self.send_json_response(
            {
                "job_id": job_id,
                "status": status_data,
                "working_directory": working_dir,
            }
        )

    def _serve_agent_activity(self, query: str) -> None:
        """SSE endpoint for real-time agent activity during phase execution."""
        from urllib.parse import parse_qs
        from .models import JobStatus
        import time

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

    def _save_system_prompt_to_disk(self) -> None:
        """Save system prompt edits back to the source file on disk."""
        if not self.check_auth():
            self.send_json_error(401, "Unauthorized")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            phase = data.get("phase")
            content = data.get("content")

            if not phase or content is None:
                self.send_json_error(400, "Missing 'phase' or 'content'")
                return

            root_dir = Path(__file__).resolve().parent.parent.parent
            prompt_file = (
                root_dir / "tools" / "prompts" / "phases" / f"phase_{phase}.txt"
            )

            if not prompt_file.parent.exists():
                prompt_file.parent.mkdir(parents=True, exist_ok=True)

            prompt_file.write_text(content, encoding="utf-8")
            logger.info(f"System prompt saved: {prompt_file}")

            self.send_json_response({"success": True, "path": str(prompt_file)})

        except Exception as exc:
            logger.warning(f"Error saving system prompt: {exc}")
            self.send_json_error(500, str(exc))

    def _save_input_instruction_to_disk(self) -> None:
        """Save input instruction edits back to disk."""
        if not self.check_auth():
            self.send_json_error(401, "Unauthorized")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            job_id = data.get("job_id")
            phase = data.get("phase")
            content = data.get("content")

            if not job_id or not phase or content is None:
                self.send_json_error(400, "Missing 'job_id', 'phase', or 'content'")
                return

            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_json_error(400, "Job has no working directory")
                return

            cf_dir = Path(working_dir) / ".context-foundry"
            instruction_file = cf_dir / f"{phase}-input.md"

            cf_dir.mkdir(parents=True, exist_ok=True)
            instruction_file.write_text(content, encoding="utf-8")

            logger.info(f"Input instruction saved: {instruction_file}")
            self.send_json_response({"success": True, "path": str(instruction_file)})

        except Exception as exc:
            logger.warning(f"Error saving input instruction: {exc}")
            self.send_json_error(500, str(exc))


# =============================================================================
# SERVER CLASSES
# =============================================================================


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
            except Exception as exc:
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
        except Exception as exc:
            logger.warning("Error shutting down dashboard server: %s", exc)

        if self._thread:
            self._thread.join(timeout=5.0)

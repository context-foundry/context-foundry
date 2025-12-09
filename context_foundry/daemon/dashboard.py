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
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .jobs import JobManager
from .models import Job, JobStatus, PhaseEvent
from .store import Store
from .events import get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class DashboardContext:
    """Shared context for dashboard requests."""

    job_manager: JobManager
    store: Store
    html: str
    refresh_interval: float = 2.0
    stop_event: threading.Event = field(default_factory=threading.Event)
    # Auth token for destructive operations (generated at startup)
    auth_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))


def _build_phase_snapshot(event: Optional[PhaseEvent]) -> Optional[Dict[str, Any]]:
    """Serialize the latest phase event if present."""
    if not event:
        return None
    return {
        "phase": event.phase,
        "status": event.status,
        "timestamp": event.timestamp.isoformat(),
        "details": event.details,
        "duration_seconds": event.duration_seconds,
        "tokens_used": event.tokens_used,
        "context_percent": event.context_percent,
    }


def _read_conversation_preview(
    job: Job, max_lines: int = 12
) -> Optional[Dict[str, Any]]:
    """
    Read the tail of the most recent conversation log for a job.

    Returns None if no log is available (e.g., streaming disabled).
    """
    working_dir = job.params.get("working_directory") or job.params.get("project_path")
    if not working_dir:
        return None

    conversations_dir = Path(working_dir) / ".context-foundry" / "conversations"
    if not conversations_dir.exists():
        return None

    log_files = list(conversations_dir.glob("conversation-*.log"))
    if not log_files:
        return None

    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)

    try:
        lines = latest_log.read_text(errors="ignore").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to read conversation log %s: %s", latest_log, exc)
        return None

    tail = [line[:400] for line in lines[-max_lines:]]
    return {
        "file": latest_log.name,
        "path": str(latest_log),
        "lines": tail,
    }


def _get_file_info(fpath: Path) -> Optional[Dict[str, Any]]:
    """Get file info dict for an artifact, or None if file doesn't exist."""
    if not fpath.exists():
        return None
    try:
        stat = fpath.stat()
        return {
            "path": str(fpath),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
    except Exception:
        return None


def _read_artifact_manifest(
    cf_dir: Path, working_path: Path
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Read artifact manifest from .context-foundry/artifacts.json.

    Manifest schema:
    {
        "artifacts": [
            {
                "phase": "Screenshot",
                "name": "hero.png",
                "path": "docs/screenshots/hero.png",
                "type": "image/png"
            },
            ...
        ]
    }

    Returns dict keyed by phase, with outputs dict for each phase.
    Returns None if manifest doesn't exist or is invalid.
    """
    manifest_path = cf_dir / "artifacts.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path) as f:
            data = json.load(f)

        artifacts_list = data.get("artifacts", [])
        if not isinstance(artifacts_list, list):
            return None

        # Group by phase
        by_phase: Dict[str, Dict[str, Any]] = {}
        for entry in artifacts_list:
            if not isinstance(entry, dict):
                continue

            phase = entry.get("phase")
            name = entry.get("name")
            rel_path = entry.get("path")

            if not phase or not name or not rel_path:
                continue

            # Security: validate path (no traversal, no absolute paths)
            try:
                # Reject absolute paths in manifest
                if os.path.isabs(rel_path):
                    logger.warning(
                        f"Manifest contains absolute path (rejected): {rel_path}"
                    )
                    continue

                # Resolve the path relative to working directory
                working_resolved = working_path.resolve()
                full_path = (working_path / rel_path).resolve()

                # Use relative_to() - raises ValueError if not actually within base
                # This is safer than string prefix checking which has collision issues
                # (e.g., /tmp/project-evil starts with /tmp/project)
                try:
                    full_path.relative_to(working_resolved)
                except ValueError:
                    logger.warning(f"Manifest path traversal attempt: {rel_path}")
                    continue
            except Exception:
                continue

            # Get file info (skip if missing)
            info = _get_file_info(full_path)
            if not info:
                # File declared in manifest but missing - still record it
                # so frontend knows it was expected
                info = {
                    "path": str(full_path),
                    "size": 0,
                    "modified": None,
                    "missing": True,
                }

            # Add optional metadata from manifest
            if entry.get("type"):
                info["type"] = entry["type"]

            # Determine the key for this artifact
            # Frontend PHASE_FILE_MAP expects specific keys per phase:
            # - Scout: scout-report.md, scout_report.json (filename only)
            # - Architect: architecture.md, architecture.json (filename only)
            # - Test: test-report.md (filename only)
            # - Screenshot: docs/screenshots/hero.png (with path)
            # - Documentation: README.md (filename only)
            # - Deploy: session-summary.json (filename only)
            #
            # Agents may put files in various locations (docs/, .context-foundry/, root).
            # We normalize to match frontend expectations.
            if phase == "Screenshot" and entry.get("hero"):
                # Hero screenshot uses standard key
                artifact_key = "docs/screenshots/hero.png"
            else:
                # Normalize path: convert backslashes to forward slashes, strip leading ./
                normalized = rel_path.replace("\\", "/")
                while normalized.startswith("./"):
                    normalized = normalized[2:]

                # Extract filename for comparison
                filename = (
                    normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized
                )
                filename_lower = filename.lower()

                # Phase-specific normalization to match PHASE_FILE_MAP
                # These phases expect filename-only keys (case-insensitive match)
                filename_only_artifacts = {
                    # Scout phase
                    "scout-report.md": "scout-report.md",
                    "scout_report.json": "scout_report.json",
                    # Architect phase
                    "architecture.md": "architecture.md",
                    "architecture.json": "architecture.json",
                    # Test phase
                    "test-report.md": "test-report.md",
                    # Documentation phase
                    "readme.md": "README.md",
                    # Deploy phase
                    "session-summary.json": "session-summary.json",
                }

                if filename_lower in filename_only_artifacts:
                    # Use the canonical key (properly cased)
                    artifact_key = filename_only_artifacts[filename_lower]
                elif normalized.startswith(".context-foundry/"):
                    # Strip .context-foundry/ prefix for other files
                    artifact_key = normalized[len(".context-foundry/") :]
                else:
                    # Keep full path for non-standard artifacts
                    artifact_key = normalized

            # Group by phase
            if phase not in by_phase:
                by_phase[phase] = {"outputs": {}}
            by_phase[phase]["outputs"][artifact_key] = info

        return by_phase if by_phase else None

    except Exception as e:
        logger.debug(f"Failed to read artifact manifest: {e}")
        return None


def _get_phase_artifacts(job: Job) -> Dict[str, Any]:
    """
    Get phase artifact files for a job.

    First checks .context-foundry/artifacts.json manifest (if present).
    Falls back to directory scanning for backwards compatibility.

    Returns dict with artifact info for each phase:
    - Scout: scout-report.md, scout_report.json
    - Architect: architecture.md, architecture.json
    - Builder: (project files)
    - Test: test-report.md
    - Screenshot: docs/screenshots/hero.png and other screenshots
    - Documentation: README.md at project root
    - Deploy: session-summary.json
    """
    working_dir = job.params.get("working_directory") or job.params.get("project_path")
    if not working_dir:
        return {}

    working_path = Path(working_dir)
    cf_dir = working_path / ".context-foundry"
    if not cf_dir.exists():
        return {}

    # Try manifest first (agent-declared artifacts)
    manifest_artifacts = _read_artifact_manifest(cf_dir, working_path)

    # Start with manifest artifacts if available
    artifacts = manifest_artifacts.copy() if manifest_artifacts else {}

    # Fall back to / supplement with directory scanning
    # (scanning fills in gaps not covered by manifest)

    # Scout artifacts (skip if manifest already has them)
    # Only look for markdown files - JSON files are deprecated
    if "Scout" not in artifacts:
        scout_files = {}
        for fname in ["scout-report.md"]:
            info = _get_file_info(cf_dir / fname)
            if info:
                scout_files[fname] = info
        if scout_files:
            artifacts["Scout"] = {"outputs": scout_files}

    # Architect artifacts (skip if manifest already has them)
    # Check .context-foundry/, docs/, and project root - markdown only (JSON deprecated)
    if "Architect" not in artifacts:
        architect_files = {}
        # Check .context-foundry/ first (exact match)
        for fname in ["architecture.md"]:
            info = _get_file_info(cf_dir / fname)
            if info:
                architect_files[fname] = info

        # For files not found, check docs/ and project root (case-insensitive)
        docs_dir = working_path / "docs"
        for target_name, target_lower in [
            ("architecture.md", "architecture.md"),
            ("architecture.json", "architecture.json"),
        ]:
            if target_name in architect_files:
                continue
            # Check docs/ directory
            if docs_dir.exists():
                for fpath in docs_dir.iterdir():
                    if fpath.is_file() and fpath.name.lower() == target_lower:
                        info = _get_file_info(fpath)
                        if info:
                            architect_files[target_name] = info
                        break
            # Check project root if still not found
            if target_name not in architect_files:
                for fpath in working_path.iterdir():
                    if fpath.is_file() and fpath.name.lower() == target_lower:
                        info = _get_file_info(fpath)
                        if info:
                            architect_files[target_name] = info
                        break

        if architect_files:
            artifacts["Architect"] = {"outputs": architect_files}

    # Test artifacts (skip if manifest already has them)
    # Also search nested .context-foundry directories (agents sometimes create files in subdirs)
    if "Test" not in artifacts:
        test_files = {}
        # First check root .context-foundry
        for fpath in cf_dir.glob("test-report*.md"):
            info = _get_file_info(fpath)
            if info:
                test_files[fpath.name] = info
        # Also check nested .context-foundry directories (fallback for agent behavior)
        if not test_files:
            for nested_cf in working_path.glob("**/.context-foundry"):
                if nested_cf == cf_dir:
                    continue  # Skip root, already checked
                for fpath in nested_cf.glob("test-report*.md"):
                    info = _get_file_info(fpath)
                    if info:
                        # Include relative path in name to distinguish nested files
                        rel_path = fpath.relative_to(working_path)
                        test_files[str(rel_path)] = info
        if test_files:
            artifacts["Test"] = {"outputs": test_files}

    # Screenshot artifacts (skip if manifest already has them)
    # Check multiple possible locations, case-insensitive, multiple formats
    if "Screenshot" not in artifacts:
        screenshot_files = {}
        # Supported image formats
        image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        # Locations where agents might put screenshots (in priority order)
        screenshot_dirs = [
            working_path / "docs" / "screenshots",
            working_path / "screenshots",
            working_path / "assets" / "screenshots",
            working_path / "images",
        ]
        for screenshots_dir in screenshot_dirs:
            if not screenshots_dir.exists():
                continue
            # Look for hero image (case-insensitive, any supported format)
            # Frontend expects key "docs/screenshots/hero.png"
            if "docs/screenshots/hero.png" not in screenshot_files:
                for fpath in screenshots_dir.iterdir():
                    if not fpath.is_file():
                        continue
                    stem_lower = fpath.stem.lower()
                    ext_lower = fpath.suffix.lower()
                    if stem_lower == "hero" and ext_lower in image_extensions:
                        info = _get_file_info(fpath)
                        if info:
                            # Use the key frontend expects
                            screenshot_files["docs/screenshots/hero.png"] = info
                        break
            # Collect other screenshots (all supported formats)
            for fpath in screenshots_dir.iterdir():
                if not fpath.is_file():
                    continue
                ext_lower = fpath.suffix.lower()
                stem_lower = fpath.stem.lower()
                if ext_lower not in image_extensions:
                    continue
                if stem_lower == "hero":
                    continue  # Already handled above
                rel_path = fpath.relative_to(working_path)
                key = str(rel_path)
                if key not in screenshot_files:
                    info = _get_file_info(fpath)
                    if info:
                        screenshot_files[key] = info
        if screenshot_files:
            artifacts["Screenshot"] = {"outputs": screenshot_files}

    # Documentation artifacts (skip if manifest already has them)
    # Check README.md at project root
    if "Documentation" not in artifacts:
        doc_files = {}
        readme_path = working_path / "README.md"
        info = _get_file_info(readme_path)
        if info:
            doc_files["README.md"] = info
        # Also check for other common doc files
        for fname in ["CHANGELOG.md", "CONTRIBUTING.md", "LICENSE"]:
            info = _get_file_info(working_path / fname)
            if info:
                doc_files[fname] = info
        if doc_files:
            artifacts["Documentation"] = {"outputs": doc_files}

    # Deploy artifacts (skip if manifest already has them)
    # Check .context-foundry/ and project root
    # Track where we find session-summary.json for _session parsing
    found_session_path: Optional[Path] = None

    if "Deploy" not in artifacts:
        deploy_files = {}
        # Check .context-foundry/ first (preferred location)
        session_file = cf_dir / "session-summary.json"
        info = _get_file_info(session_file)
        if info:
            deploy_files["session-summary.json"] = info
            found_session_path = session_file
        else:
            # Fallback: check project root
            root_session = working_path / "session-summary.json"
            info = _get_file_info(root_session)
            if info:
                deploy_files["session-summary.json"] = info
                found_session_path = root_session
        # Check for deploy-log.md in both locations
        deploy_log = cf_dir / "deploy-log.md"
        info = _get_file_info(deploy_log)
        if info:
            deploy_files["deploy-log.md"] = info
        else:
            info = _get_file_info(working_path / "deploy-log.md")
            if info:
                deploy_files["deploy-log.md"] = info
        if deploy_files:
            artifacts["Deploy"] = {"outputs": deploy_files}
    else:
        # Manifest provided Deploy artifacts - check if session-summary exists there
        deploy_outputs = artifacts.get("Deploy", {}).get("outputs", {})
        if "session-summary.json" in deploy_outputs:
            path_str = deploy_outputs["session-summary.json"].get("path")
            if path_str:
                found_session_path = Path(path_str)

    # Session summary (overall build info) - parsed for phase status
    # Use the session file we actually found (could be .context-foundry/ or root)
    if found_session_path is None:
        # Last fallback: check standard location
        found_session_path = cf_dir / "session-summary.json"

    if found_session_path.exists():
        try:
            with open(found_session_path) as f:
                session = json.load(f)
                artifacts["_session"] = {
                    "phases": session.get("phases", {}),
                    "configuration": session.get("configuration", {}),
                }
        except Exception:
            pass

    return artifacts


def _serialize_job(context: DashboardContext, job: Job) -> Dict[str, Any]:
    """Serialize a job plus lightweight runtime metadata for the dashboard."""
    tracker = context.job_manager.get_agent_tracker(job.id)
    phase_events = context.store.get_phase_events(job.id)
    last_phase = phase_events[-1] if phase_events else None
    logs = context.store.get_logs(job.id, limit=40)
    log_tail = logs[-10:] if logs else []

    preview = _read_conversation_preview(job)

    # Get agent stats: prefer live tracker, fallback to persisted metadata
    if tracker:
        agent_stats = tracker.to_dict()
    else:
        agent_stats = job.metadata.get("agent_stats")

    # Build phase artifacts info
    phase_artifacts = _get_phase_artifacts(job)

    return {
        "id": job.id,
        "type": job.type.value,
        "status": job.status.value,
        "priority": job.priority,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "result": job.result,
        "error": job.error,
        "metadata": job.metadata,
        "params": job.params,  # Include params for working_directory, etc.
        "duration_seconds": job.duration(),
        "agents": agent_stats,
        "phase": last_phase.phase if last_phase else None,
        "latest_phase": _build_phase_snapshot(last_phase),
        "all_phases": [_build_phase_snapshot(e) for e in phase_events],
        "phase_artifacts": phase_artifacts,
        "recent_logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message,
                "phase": log.phase,
                "source": log.source,
            }
            for log in log_tail
        ],
        "context_preview": preview,
    }


def build_status_payload(context: DashboardContext) -> Dict[str, Any]:
    """Create a status snapshot for JSON + SSE responses."""
    jobs = context.store.list_jobs(limit=50)
    serialized_jobs = [_serialize_job(context, job) for job in jobs]

    counts: Dict[str, int] = {}
    for job in jobs:
        counts[job.status.value] = counts.get(job.status.value, 0) + 1

    running_agents = 0
    for job in jobs:
        tracker = context.job_manager.get_agent_tracker(job.id)
        if tracker:
            running_agents += tracker.active_count

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_jobs": len(jobs),
            "by_status": counts,
            "running_agents": running_agents,
            "running_jobs": counts.get(JobStatus.RUNNING.value, 0),
        },
        "jobs": serialized_jobs,
    }


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Serve the dashboard HTML, JSON status, and SSE stream."""

    server: "DashboardHTTPServer"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.debug("Dashboard HTTP %s - %s", self.address_string(), format % args)

    def _validate_artifact_path(self, file_path: str) -> Optional[Path]:
        """
        Validate and normalize an artifact file path.

        Returns the resolved Path if valid, None if invalid.
        Security: Prevents path traversal by requiring the resolved path
        to be either:
        1. Inside a .context-foundry directory, OR
        2. Inside a project directory that contains a .context-foundry folder
        """
        try:
            # Resolve to absolute path, following symlinks
            resolved = Path(os.path.realpath(file_path))
            parts = resolved.parts

            # Case 1: Path is inside a .context-foundry directory
            if ".context-foundry" in parts:
                cf_idx = parts.index(".context-foundry")
                # Ensure there's at least one component after .context-foundry
                if cf_idx < len(parts) - 1:
                    return resolved

            # Case 2: Path is within a project that has a .context-foundry folder
            # Walk up parent directories to find a project root with .context-foundry
            for parent in resolved.parents:
                cf_dir = parent / ".context-foundry"
                if cf_dir.is_dir():
                    # Verify resolved path is actually under this parent (no escaping)
                    try:
                        resolved.relative_to(parent)
                        return resolved
                    except ValueError:
                        continue

            return None
        except (ValueError, OSError):
            return None

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
        else:
            # Fallback to serving static files (Vite app)
            self._serve_dashboard_asset(parsed.path)

    def _get_recent_file_context(self) -> str:
        """
        Scan for recently modified files to provide context to the agent.
        Returns a formatted string of recent file contents found in the current workspace.
        """
        try:
            # Determine scanning root - prefer active job's working dir, else fallback to current dir
            store = self.server.context.store
            # Try to find a recently active job to get a relevant working directory
            from .models import JobStatus

            scan_dir = Path.cwd()  # Default fallback

            # Check running jobs first
            active_jobs = store.list_jobs(status=JobStatus.RUNNING, limit=1)
            if active_jobs:
                wd = active_jobs[0].params.get("working_directory")
                if wd and os.path.isdir(wd):
                    scan_dir = Path(wd)
            else:
                # Check recent jobs
                recent_jobs = store.list_jobs(limit=1)
                if recent_jobs:
                    wd = recent_jobs[0].params.get("working_directory")
                    if wd and os.path.isdir(wd):
                        scan_dir = Path(wd)

            logger.info(f"Scanning for context in: {scan_dir}")

            # Find files modified in the last 24 hours (or just take top N most recent)
            # Exclude hidden files, git, and python cache
            exclude_dirs = {
                ".git",
                "__pycache__",
                "node_modules",
                "dist",
                "build",
                ".context-foundry",
            }
            exclude_exts = {
                ".pyc",
                ".o",
                ".obj",
                ".so",
                ".dll",
                ".class",
                ".log",
                ".lock",
                ".zip",
                ".tar",
                ".gz",
            }

            candidates = []
            try:
                # Walk the directory
                for root, dirs, files in os.walk(scan_dir):
                    # Prune excluded dirs
                    dirs[:] = [
                        d
                        for d in dirs
                        if d not in exclude_dirs and not d.startswith(".")
                    ]

                    for file in files:
                        if file.startswith("."):
                            continue

                        file_path = Path(root) / file
                        if file_path.suffix in exclude_exts:
                            continue

                        try:
                            stat = file_path.stat()
                            candidates.append((file_path, stat.st_mtime))
                        except (OSError, ValueError):
                            continue
            except Exception as e:
                logger.warning(f"Error walking directory {scan_dir}: {e}")

            # Sort by modification time (descending) and take top 5
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_files = candidates[:5]

            context_str = "RECENTLY MODIFIED FILES IN WORKSPACE:\n"
            if not top_files:
                return context_str + "(No recent files found)\n"

            for fpath, mtime in top_files:
                try:
                    rel_path = fpath.relative_to(scan_dir)
                    mtime_str = datetime.fromtimestamp(mtime).isoformat()

                    # Read head of file
                    content_snippet = ""
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            # Read first 50 lines or 2000 chars
                            lines = []
                            for _ in range(50):
                                line = f.readline()
                                if not line:
                                    break
                                lines.append(line)
                            content_snippet = "".join(lines)
                            if len(content_snippet) > 2000:
                                content_snippet = (
                                    content_snippet[:2000] + "\n...(truncated)..."
                                )
                    except Exception:
                        content_snippet = "(binary or unreadable content)"

                    context_str += (
                        f"\n--- FILE: {rel_path} (Last modified: {mtime_str}) ---\n"
                    )
                    context_str += content_snippet + "\n"

                except Exception as e:
                    logger.debug(f"Error reading file context for {fpath}: {e}")
                    continue

            return context_str

        except Exception as e:
            logger.warning(f"Failed to generate file context: {e}")
            return "CONTEXT_SCAN_ERROR: Could not scan local files."

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
        elif parsed.path == "/sidekick-chat":
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

    def _serve_html(self) -> None:
        html = self.server.context.html
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

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
        """Get phase prompts for a job. Query: job_id=<id>"""
        # Require auth (prompts may contain sensitive build instructions)
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
                    {"prompts": [], "warning": "No working directory for job"}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._add_cors_headers()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Look for phase prompt files in .context-foundry/phase-prompts/
            prompts_dir = Path(working_dir) / ".context-foundry" / "phase-prompts"
            prompts = []

            if prompts_dir.exists():
                for prompt_file in prompts_dir.glob("*.json"):
                    try:
                        prompt_data = json.loads(prompt_file.read_text())
                        prompts.append(prompt_data)
                    except (json.JSONDecodeError, IOError) as e:
                        logger.warning(
                            "Failed to read prompt file %s: %s", prompt_file, e
                        )

            # Sort by phase order
            phase_order = {
                "Scout": 0,
                "Architect": 1,
                "Builder": 2,
                "Test": 3,
                "Deploy": 4,
            }
            prompts.sort(key=lambda p: phase_order.get(p.get("phase", ""), 99))

            body = json.dumps({"prompts": prompts}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        except Exception as exc:
            logger.warning("Error serving phase prompts: %s", exc)
            self.send_error(500, str(exc))

    def _save_phase_prompt(self) -> None:
        """Save edited phase prompt. POST body: {job_id, phase, system_prompt?, input_instruction?}"""
        if not self._check_auth():
            self.send_error(401, "Unauthorized: missing or invalid X-CF-Auth header")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            # Size limit: 500KB max for prompt edits
            if content_length > 500_000:
                self.send_error(413, "Request body too large (max 500KB for prompts)")
                return

            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            job_id = data.get("job_id")
            phase = data.get("phase")

            if not job_id or not phase:
                self.send_error(400, "Missing 'job_id' or 'phase' in request body")
                return

            # Find job and validate
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_error(400, "Job has no working directory")
                return

            # Load existing prompt or create new
            prompts_dir = Path(working_dir) / ".context-foundry" / "phase-prompts"
            prompts_dir.mkdir(parents=True, exist_ok=True)
            prompt_file = prompts_dir / f"{phase.lower()}-prompt.json"

            if prompt_file.exists():
                prompt_data = json.loads(prompt_file.read_text())
            else:
                self.send_error(404, f"No prompt found for phase: {phase}")
                return

            # State guard: block edits after processing/completion
            current_state = prompt_data.get("state", "ready")
            # New states: processing, complete, failed are terminal for editing
            terminal_states = {"processing", "complete", "failed"}
            if current_state in terminal_states:
                self.send_error(
                    409,
                    f"Cannot edit prompt in state '{current_state}'. Phase is already being executed or complete.",
                )
                return

            # Update with edits
            if "system_prompt" in data:
                prompt_data["system_prompt_edited"] = data["system_prompt"]
            if "input_instruction" in data:
                prompt_data["input_instruction_edited"] = data["input_instruction"]

            prompt_data["edited_at"] = datetime.now().isoformat()
            prompt_data["edited_by"] = data.get("edited_by", "dashboard_user")
            # Transition to ready_edit state (user has made edits)
            prompt_data["state"] = "ready_edit"

            # Save
            prompt_file.write_text(json.dumps(prompt_data, indent=2))
            logger.info("Phase prompt saved: %s/%s", job_id[:8], phase)

            response = json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "prompt": prompt_data,
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error saving phase prompt: %s", exc)
            self.send_error(500, str(exc))

    def _inject_phase_prompt(self) -> None:
        """Approve and mark phase prompt for injection. POST body: {job_id, phase}

        NOTE: This is the legacy approval endpoint. For the new HITL workflow,
        use /phase-acknowledge instead. Both endpoints now use consistent state constants.
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

            # Load prompt
            prompt_file = (
                Path(working_dir)
                / ".context-foundry"
                / "phase-prompts"
                / f"{phase.lower()}-prompt.json"
            )
            if not prompt_file.exists():
                self.send_error(404, f"No prompt found for phase: {phase}")
                return

            prompt_data = json.loads(prompt_file.read_text())

            # Import state constants for consistency with new state machine
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_prompts import (
                STATE_READY,
                STATE_PROCESSING,
                STATE_COMPLETE,
                STATE_FAILED,
            )

            # State guard: block approval if already processing or in terminal state
            current_state = prompt_data.get("state", STATE_READY)
            if current_state == STATE_PROCESSING:
                self.send_error(409, "Prompt is already approved and being processed")
                return
            if current_state in {STATE_COMPLETE, STATE_FAILED}:
                self.send_error(
                    409,
                    f"Cannot approve prompt in state '{current_state}'. Phase has already been processed.",
                )
                return

            # Mark as processing (approved) - consistent with new state machine
            prompt_data["state"] = STATE_PROCESSING
            prompt_data["approved_at"] = datetime.now().isoformat()
            prompt_data["approved_by"] = data.get("approved_by", "dashboard_user")

            # Save
            prompt_file.write_text(json.dumps(prompt_data, indent=2))
            logger.info("Phase prompt approved: %s/%s", job_id[:8], phase)

            # The runner will detect the processing state and proceed with injection

            response = json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "state": STATE_PROCESSING,
                    "message": f"Phase {phase} prompt approved for injection",
                }
            ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error injecting phase prompt: %s", exc)
            self.send_error(500, str(exc))

    def _start_phase_review(self) -> None:
        """
        Start reviewing a phase prompt. POST body: {job_id, phase, reviewed_by?}
        Transitions state: ready -> under_review
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

            # Import phase_prompts module
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_prompts import (
                read_phase_prompt,
                update_prompt_state,
                STATE_READY,
                STATE_UNDER_REVIEW,
            )

            # Read current prompt
            prompt_data = read_phase_prompt(Path(working_dir), phase)
            if not prompt_data:
                self.send_error(404, f"No prompt found for phase: {phase}")
                return

            current_state = prompt_data.get("state", STATE_READY)

            # Only allow transition from ready state
            if current_state != STATE_READY:
                self.send_error(
                    409,
                    f"Cannot start review from state '{current_state}'. Must be in 'ready' state.",
                )
                return

            # Transition to under_review
            success = update_prompt_state(
                Path(working_dir),
                phase,
                STATE_UNDER_REVIEW,
                reviewed_by=data.get("reviewed_by", "dashboard_user"),
            )

            if not success:
                self.send_error(500, "Failed to update prompt state")
                return

            # Re-read to get updated data
            prompt_data = read_phase_prompt(Path(working_dir), phase)

            response = json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "state": STATE_UNDER_REVIEW,
                    "prompt": prompt_data,
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
        except Exception as exc:
            logger.warning("Error starting phase review: %s", exc)
            self.send_error(500, str(exc))

    def _acknowledge_phase(self) -> None:
        """
        Acknowledge a phase prompt, allowing the agent to start execution.
        POST body: {job_id, phase, acknowledged_by?, was_edited?}
        Transitions state: draft/under_review -> acknowledged_edited/acknowledged_unedited -> processing

        This is the "clean plate" mechanism - the agent is blocked waiting
        for this state transition before it can start.

        The was_edited flag creates a permanent record of whether the human
        edited the prompts before submission.
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
            was_edited = data.get("was_edited", False)

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

            # Import phase_prompts module
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_prompts import (
                read_phase_prompt,
                update_prompt_state,
                STATE_DRAFT,
                STATE_READY,
                STATE_UNDER_REVIEW,
                STATE_READY_EDIT,
                STATE_ACKNOWLEDGED_EDITED,
                STATE_ACKNOWLEDGED_UNEDITED,
            )

            # Read current prompt
            prompt_data = read_phase_prompt(Path(working_dir), phase)
            if not prompt_data:
                self.send_error(404, f"No prompt found for phase: {phase}")
                return

            current_state = prompt_data.get("state", STATE_DRAFT)

            # Allow acknowledge from draft, ready, under_review, or ready_edit states
            # Note: Include both constant values AND literal "ready_edit" string
            # because the save endpoint uses literal "ready_edit" but STATE_READY_EDIT = "under_review"
            valid_states = {
                STATE_DRAFT,
                STATE_READY,
                STATE_UNDER_REVIEW,
                STATE_READY_EDIT,
                "ready_edit",  # Literal string used by save endpoint
            }
            if current_state not in valid_states:
                self.send_error(
                    409,
                    f"Cannot acknowledge from state '{current_state}'. "
                    f"Must be in one of: {', '.join(valid_states)}",
                )
                return

            # Transition to acknowledged state (records edit status permanently)
            # The agent is waiting for this state - it will transition to processing when it starts
            acknowledged_state = (
                STATE_ACKNOWLEDGED_EDITED if was_edited else STATE_ACKNOWLEDGED_UNEDITED
            )

            # Pass explicit edit flags from request (handles temp edits that aren't in file yet)
            # These override the file-derived values in update_prompt_state
            system_prompt_was_edited = data.get("system_prompt_was_edited", False)
            input_instruction_was_edited = data.get(
                "input_instruction_was_edited", False
            )

            success = update_prompt_state(
                Path(working_dir),
                phase,
                acknowledged_state,
                validate_transition=False,  # Allow direct transition for user acknowledgment
                acknowledged_by=data.get("acknowledged_by", "dashboard_user"),
                system_prompt_was_edited=system_prompt_was_edited,
                input_instruction_was_edited=input_instruction_was_edited,
            )

            if not success:
                self.send_error(500, "Failed to update prompt state to acknowledged")
                return

            # NOTE: We do NOT transition to processing here.
            # The agent is polling for acknowledged_edited/acknowledged_unedited states.
            # When the agent sees the acknowledged state, IT will transition to processing
            # when it actually starts execution. This makes the acknowledged state observable.

            edit_status = "with edits" if was_edited else "unedited"
            logger.info(
                "Phase prompt acknowledged (%s): %s/%s - agent will wake up and start",
                edit_status,
                job_id[:8],
                phase,
            )

            response = json.dumps(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "state": acknowledged_state,
                    "was_edited": was_edited,
                    "message": f"Phase {phase} acknowledged ({edit_status}). Agent will start execution.",
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
            logger.warning("Error acknowledging phase: %s", exc)
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

            # Import phase_prompts module
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_prompts import (
                read_phase_prompt,
                read_all_phase_prompts,
            )

            if phase:
                # Single phase
                prompt_data = read_phase_prompt(Path(working_dir), phase)
                if not prompt_data:
                    self.send_error(404, f"No prompt found for phase: {phase}")
                    return

                result = {
                    "phase": phase,
                    "state": prompt_data.get("state", "sleeping"),
                    "token_metrics": prompt_data.get("token_metrics", {}),
                    "timestamps": {
                        "created_at": prompt_data.get("created_at"),
                        "ready_at": prompt_data.get("ready_at"),
                        "review_started_at": prompt_data.get("review_started_at"),
                        "edited_at": prompt_data.get("edited_at"),
                        "acknowledged_at": prompt_data.get("acknowledged_at"),
                        "processing_started_at": prompt_data.get(
                            "processing_started_at"
                        ),
                        "completed_at": prompt_data.get("completed_at"),
                    },
                    "has_edits": bool(
                        prompt_data.get("system_prompt_edited")
                        or prompt_data.get("input_instruction_edited")
                    ),
                }
            else:
                # All phases
                all_prompts = read_all_phase_prompts(Path(working_dir))
                result = {
                    "phases": {
                        name: {
                            "state": data.get("state", "sleeping"),
                            "token_metrics": data.get("token_metrics", {}),
                            "has_edits": bool(
                                data.get("system_prompt_edited")
                                or data.get("input_instruction_edited")
                            ),
                        }
                        for name, data in all_prompts.items()
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

            # Import phase_prompts module
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from tools.mcp_utils.phase_prompts import get_transaction_stats

            stats = get_transaction_stats(Path(working_dir))

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

            if not message:
                self.send_error(400, "Empty message")
                return

            # Try to use Claude CLI for a "bigger brain" response
            import subprocess
            import shutil
            import os

            claude_path = shutil.which("claude")
            if not claude_path and os.path.exists("/opt/homebrew/bin/claude"):
                claude_path = "/opt/homebrew/bin/claude"

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
        html: str,
        refresh_interval: float = 2.0,
    ):
        self.host = host
        self.port = port
        self._thread: Optional[threading.Thread] = None
        self.context = DashboardContext(
            job_manager=job_manager,
            store=store,
            html=html,
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


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Context Foundry Dashboard</title>
  <style>
    :root {
      --bg: #0f1115;
      --panel: #161922;
      --card: #1d2130;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #7dd3fc;
      --accent-2: #a5b4fc;
      --danger: #fca5a5;
      --success: #86efac;
      --warn: #fcd34d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "SFMono-Regular", "Input Mono", Menlo, Consolas, monospace;
      background: radial-gradient(120% 120% at 10% 20%, #111827, #0b0d12 65%, #06070b);
      color: var(--text);
    }
    header {
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #1f2937;
      background: linear-gradient(135deg, rgba(125,211,252,0.08), rgba(165,180,252,0.08));
    }
    .title { font-size: 18px; letter-spacing: 0.4px; }
    .pill {
      padding: 6px 12px;
      border-radius: 999px;
      background: #111827;
      border: 1px solid #1f2937;
      color: var(--muted);
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
    }
    main { padding: 20px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
    }
    .card {
      background: var(--card);
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 12px 14px;
      transition: border-color 0.2s ease, transform 0.2s ease;
    }
    .card:hover { border-color: var(--accent); transform: translateY(-1px); }
    .label { color: var(--muted); font-size: 12px; letter-spacing: 0.2px; }
    .value { font-size: 20px; margin-top: 4px; }
    .layout {
      display: grid;
      grid-template-columns: 1.3fr 1fr;
      gap: 16px;
      margin-top: 16px;
    }
    @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
    .job-list { display: grid; gap: 10px; }
    .job-card {
      background: var(--panel);
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 12px;
      cursor: pointer;
      transition: border-color 0.2s ease, transform 0.2s ease;
    }
    .job-card:hover { border-color: var(--accent-2); transform: translateY(-1px); }
    .job-card.selected { border-color: var(--accent); box-shadow: 0 0 0 1px rgba(125,211,252,0.25); }
    .job-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .job-meta { color: var(--muted); font-size: 12px; }
    .status {
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border: 1px solid #1f2937;
    }
    .status.running { background: rgba(125,211,252,0.15); color: var(--accent); border-color: rgba(125,211,252,0.4); }
    .status.queued { background: rgba(252,211,77,0.12); color: var(--warn); border-color: rgba(252,211,77,0.35); }
    .status.failed { background: rgba(252,165,165,0.15); color: var(--danger); border-color: rgba(252,165,165,0.35); }
    .status.succeeded { background: rgba(134,239,172,0.15); color: var(--success); border-color: rgba(134,239,172,0.35); }
    .status.timed_out { background: rgba(252,165,165,0.15); color: var(--danger); border-color: rgba(252,165,165,0.35); }
    .pill-mini { padding: 3px 8px; border-radius: 999px; background: #0b0d12; border: 1px solid #1f2937; color: var(--muted); font-size: 11px; }
    .context-panel {
      background: var(--panel);
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 14px;
      min-height: 340px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .monospace {
      font-family: "SFMono-Regular", "Input Mono", Menlo, Consolas, monospace;
      white-space: pre-wrap;
      background: #0b0d12;
      border: 1px solid #1f2937;
      border-radius: 10px;
      padding: 10px;
      color: var(--text);
      min-height: 180px;
    }
    .muted { color: var(--muted); }
    .agent-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .log-line { display: flex; justify-content: space-between; gap: 8px; padding: 6px 0; border-bottom: 1px solid #1f2937; }
    .log-line:last-child { border-bottom: none; }
    .badge { padding: 2px 6px; border-radius: 6px; font-size: 11px; background: #0b0d12; border: 1px solid #1f2937; }
    /* Gate pipeline visualization */
    .gate-pipeline {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    .gate-node {
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border: 1px solid #1f2937;
      background: #111827;
      color: var(--muted);
      transition: all 0.3s ease;
    }
    .gate-node.passed { background: rgba(134,239,172,0.15); color: var(--success); border-color: rgba(134,239,172,0.4); }
    .gate-node.running { background: rgba(125,211,252,0.15); color: var(--accent); border-color: rgba(125,211,252,0.4); animation: pulse 2s infinite; }
    .gate-node.failed { background: rgba(252,165,165,0.15); color: var(--danger); border-color: rgba(252,165,165,0.4); }
    .gate-node.pending { background: #111827; color: var(--muted); }
    .gate-arrow { color: var(--muted); font-size: 14px; }
    .gate-info { font-size: 12px; color: var(--muted); margin-top: 8px; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
    /* Timeline visualization */
    .timeline-view {
      background: #0b0d12;
      border: 1px solid #1f2937;
      border-radius: 10px;
      padding: 12px;
      max-height: 300px;
      overflow-y: auto;
    }
    .timeline-event {
      display: flex;
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid #1f2937;
    }
    .timeline-event:last-child { border-bottom: none; }
    .timeline-time {
      font-size: 11px;
      color: var(--muted);
      white-space: nowrap;
      min-width: 70px;
    }
    .timeline-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      margin-top: 4px;
      flex-shrink: 0;
    }
    .timeline-dot.job { background: var(--accent-2); }
    .timeline-dot.task { background: var(--accent); }
    .timeline-dot.gate { background: var(--success); }
    .timeline-dot.error { background: var(--danger); }
    .timeline-content { flex: 1; }
    .timeline-type { font-size: 10px; color: var(--muted); text-transform: uppercase; }
    .timeline-message { font-size: 12px; color: var(--text); margin-top: 2px; }
    /* Metrics panel */
    .metrics-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .metric-chip {
      padding: 4px 10px;
      border-radius: 6px;
      background: #111827;
      border: 1px solid #1f2937;
      font-size: 11px;
      color: var(--muted);
    }
    .metric-chip .value { color: var(--accent); margin-left: 4px; }
  </style>
</head>
<body>
  <header>
    <div class="title">Context Foundry — Agent Dashboard</div>
    <div class="pill" id="connection-state">
      <span>Connecting…</span>
    </div>
  </header>
  <main>
    <div class="grid" id="summary-cards"></div>
    <div class="layout">
      <div>
        <div class="job-list" id="job-list"></div>
      </div>
      <div>
        <div class="context-panel">
          <div class="job-header">
            <div>
              <div class="label">Focused Agent</div>
              <div id="focus-title" class="value" style="font-size:16px;">Select a running job</div>
            </div>
            <div id="focus-status" class="status queued">--</div>
          </div>
          <div class="muted" id="phase-line">Phase: --</div>
          <div class="tab-bar">
            <button class="tab-btn active" data-tab="context">Context</button>
            <button class="tab-btn" data-tab="tree">Tree</button>
            <button class="tab-btn" data-tab="gates">Gates</button>
            <button class="tab-btn" data-tab="timeline">Timeline</button>
            <button class="tab-btn" data-tab="logs">Logs</button>
            <button class="tab-btn" data-tab="config">Config</button>
          </div>
          <div id="tab-context" class="tab-content active">
            <div class="monospace" id="context-window">Waiting for data…</div>
          </div>
          <div id="tab-tree" class="tab-content">
            <div class="tree-view" id="tree-view">Select a job to view tree…</div>
          </div>
          <div id="tab-gates" class="tab-content">
            <div class="gates-view" id="gates-view">Select a job to view gates…</div>
          </div>
          <div id="tab-timeline" class="tab-content">
            <div class="timeline-view" id="timeline-view">Select a job to view timeline…</div>
          </div>
          <div id="tab-logs" class="tab-content">
            <div class="label">Recent logs</div>
            <div id="log-list"></div>
          </div>
          <div id="tab-config" class="tab-content">
            <div class="label">Provider Configuration</div>
            <div class="monospace" id="config-view" style="margin-top:8px;font-size:12px;">Loading config...</div>
            <div style="margin-top:12px;font-size:12px;color:var(--muted);">
              <p>To update configuration manually:</p>
              <code style="background:#0b0d12;padding:4px 8px;border-radius:4px;display:block;margin:4px 0;">cat ~/.context-foundry/provider_config.json</code>
              <p style="margin-top:4px;">Edit the file and restart the daemon.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
  <script>
    const summaryEl = document.getElementById('summary-cards');
    const jobListEl = document.getElementById('job-list');
    const connectionEl = document.getElementById('connection-state');
    const contextEl = document.getElementById('context-window');
    const focusTitleEl = document.getElementById('focus-title');
    const focusStatusEl = document.getElementById('focus-status');
    const phaseLineEl = document.getElementById('phase-line');
    const logListEl = document.getElementById('log-list');
    const treeViewEl = document.getElementById('tree-view');
    const gatesViewEl = document.getElementById('gates-view');
    const timelineViewEl = document.getElementById('timeline-view');

    let state = { selectedJobId: null, activeTab: 'context' };
    let evtSource = null;
    let cachedTree = null;

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const tab = btn.dataset.tab;
        state.activeTab = tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + tab).classList.add('active');
        if (state.selectedJobId) {
          if (tab === 'tree') fetchAndRenderTree(state.selectedJobId);
          if (tab === 'gates') fetchAndRenderGates(state.selectedJobId);
          if (tab === 'timeline') fetchAndRenderTimeline(state.selectedJobId);
        }
        if (tab === 'config') fetchAndRenderConfig();
      });
    });

    async function fetchAndRenderConfig() {
      const configViewEl = document.getElementById('config-view');
      configViewEl.innerHTML = 'Loading config...';
      try {
        const res = await fetch('/config');
        if (!res.ok) {
          configViewEl.innerHTML = 'Failed to load config';
          return;
        }
        const config = await res.json();
        renderConfig(config);
      } catch (err) {
        console.error('Failed to fetch config', err);
        configViewEl.innerHTML = 'Error loading config';
      }
    }

    function renderConfig(config) {
      const configViewEl = document.getElementById('config-view');
      if (!config || config.error) {
        configViewEl.innerHTML = config?.error || 'No config data';
        return;
      }

      let html = '<div style="display:grid;grid-template-columns:100px 100px 1fr;gap:8px;border-bottom:1px solid #1f2937;padding-bottom:8px;margin-bottom:8px;font-weight:bold;">';
      html += '<div>Phase</div><div>Provider</div><div>Model/Agent</div></div>';

      const phases = config.phases || {};
      const order = ["Scout", "Architect", "Builder", "Test", "Screenshot", "Documentation", "Deploy", "Feedback"];

      order.forEach(phase => {
        const cfg = phases[phase] || {};
        const provider = cfg.provider || 'local';
        let model = '';

        if (provider === 'bedrock') {
           model = cfg.model ? formatModelName(cfg.model) : '(default)';
        } else if (provider === 'bedrock-agent') {
           model = `Agent: ${cfg.agent_id} (${cfg.alias_id || '?'})`;
        } else {
           model = '(Claude CLI)';
        }

        html += `<div style="display:grid;grid-template-columns:100px 100px 1fr;gap:8px;padding:4px 0;">`;
        html += `<div>${phase}</div>`;
        html += `<div style="color:var(--accent);">${provider}</div>`;
        html += `<div style="color:var(--muted);">${model}</div>`;
        html += `</div>`;
      });

      configViewEl.innerHTML = html;
    }

    async function fetchAndRenderTree(jobId) {
      if (!jobId) {
        treeViewEl.innerHTML = 'Select a job to view tree…';
        return;
      }
      treeViewEl.innerHTML = 'Loading tree…';
      try {
        const res = await fetch('/job-tree?job_id=' + jobId);
        if (!res.ok) {
          treeViewEl.innerHTML = 'Failed to load tree';
          return;
        }
        const tree = await res.json();
        cachedTree = tree;
        renderTree(tree);
      } catch (err) {
        console.error('Failed to fetch tree', err);
        treeViewEl.innerHTML = 'Error loading tree';
      }
    }

    function renderTree(tree) {
      if (!tree || tree.error) {
        treeViewEl.innerHTML = tree?.error || 'No tree data';
        return;
      }
      const statusBadge = (s) => `<span class="tree-status ${s.toLowerCase()}">${s}</span>`;
      let html = `<div class="tree-node"><span class="tree-label">Job ${tree.job_id.slice(0,8)}</span>${statusBadge(tree.status)}</div>`;

      (tree.phases || []).forEach((phase, i) => {
        const isLast = i === tree.phases.length - 1;
        const prefix = isLast ? '└── ' : '├── ';
        // Include model info in phase display
        const modelInfo = phase.model ? ` <span class="muted" style="font-size:11px;">[${formatModelName(phase.model)}]</span>` :
                         (phase.provider === 'local' ? ' <span class="muted" style="font-size:11px;">[Local CLI]</span>' : '');
        html += `<div class="tree-phase"><span class="tree-prefix">${prefix}</span><span class="tree-label">Phase: ${phase.phase}</span>${modelInfo}${statusBadge(phase.status)}</div>`;

        (phase.tasks || []).forEach((task, j) => {
          const taskPrefix = isLast ? '    ' : '│   ';
          const taskBranch = j === phase.tasks.length - 1 ? '└── ' : '├── ';
          html += `<div class="tree-task"><span class="tree-prefix">${taskPrefix}${taskBranch}</span><span class="tree-label">Task ${task.task_id.slice(0,8)}</span>${statusBadge(task.status)}</div>`;
        });
      });

      treeViewEl.innerHTML = html;
    }

    // Gates functions
    async function fetchAndRenderGates(jobId) {
      if (!jobId) {
        gatesViewEl.innerHTML = 'Select a job to view gates…';
        return;
      }
      gatesViewEl.innerHTML = 'Loading gates…';
      try {
        const res = await fetch('/job-gates?job_id=' + jobId);
        if (!res.ok) {
          gatesViewEl.innerHTML = 'Failed to load gates';
          return;
        }
        const data = await res.json();
        renderGates(data);
      } catch (err) {
        console.error('Failed to fetch gates', err);
        gatesViewEl.innerHTML = 'Error loading gates';
      }
    }

    function renderGates(data) {
      if (!data || data.error) {
        gatesViewEl.innerHTML = data?.error || 'No gate data';
        return;
      }
      const gates = data.gates || [];
      if (!gates.length) {
        gatesViewEl.innerHTML = '<div class="gate-info">No phases started yet</div>';
        return;
      }

      let html = '<div class="gate-pipeline">';
      gates.forEach((gate, i) => {
        // Map 'active' status to 'running' for CSS styling
        let status = gate.status.toLowerCase();
        if (status === 'active') status = 'running';
        const duration = gate.duration_seconds ? `${Math.round(gate.duration_seconds)}s` : '--';
        html += `<div class="gate-node ${status}">
          <div style="font-weight:600;">${gate.phase}</div>
          <div style="font-size:11px;margin-top:4px;">${gate.status}</div>
          <div style="font-size:10px;color:var(--muted);">${duration}</div>
        </div>`;
        if (i < gates.length - 1) {
          html += '<span class="gate-arrow">→</span>';
        }
      });
      html += '</div>';

      // Gate summary info
      html += '<div class="gate-info">';
      if (data.current_gate) html += `Current: <strong>${data.current_gate}</strong> · `;
      if (data.next_gate) html += `Next: <strong>${data.next_gate}</strong> · `;
      html += data.all_required_passed ? '<span style="color:var(--success)">✓ All required passed</span>' : '<span style="color:var(--muted)">In progress</span>';
      if (data.has_failures) html += ' · <span style="color:var(--danger)">Has failures</span>';
      html += '</div>';

      gatesViewEl.innerHTML = html;
    }

    // Timeline functions
    async function fetchAndRenderTimeline(jobId) {
      if (!jobId) {
        timelineViewEl.innerHTML = 'Select a job to view timeline…';
        return;
      }
      timelineViewEl.innerHTML = 'Loading timeline…';
      try {
        const res = await fetch('/job-timeline?job_id=' + jobId + '&limit=100');
        if (!res.ok) {
          timelineViewEl.innerHTML = 'Failed to load timeline';
          return;
        }
        const data = await res.json();
        renderTimeline(data);
      } catch (err) {
        console.error('Failed to fetch timeline', err);
        timelineViewEl.innerHTML = 'Error loading timeline';
      }
    }

    function renderTimeline(data) {
      if (!data || data.error) {
        timelineViewEl.innerHTML = data?.error || 'No timeline data';
        return;
      }
      const events = data.events || [];
      if (!events.length) {
        timelineViewEl.innerHTML = '<div style="color:var(--muted);padding:16px;">No events yet</div>';
        return;
      }

      // Color map for status-based coloring
      const statusColors = {
        'started': 'var(--accent)',
        'running': 'var(--accent)',
        'completed': 'var(--success)',
        'succeeded': 'var(--success)',
        'passed': 'var(--success)',
        'failed': 'var(--danger)',
        'timed_out': 'var(--danger)',
        'created': 'var(--muted)',
        'queued': 'var(--muted)',
        'pending': 'var(--muted)',
      };

      let html = '';
      events.forEach(event => {
        // Build event_type from type + status (e.g., "phase_event" + "started" -> "phase started")
        const eventType = event.event_type || (event.type ? `${event.type.replace('_event', '')} ${event.status || ''}`.trim() : event.status || 'event');
        const status = event.status || '';
        const color = statusColors[status.toLowerCase()] || 'var(--muted)';
        const ts = event.timestamp ? event.timestamp.slice(11, 19) : '--:--:--';
        const phase = event.phase ? ` · ${event.phase}` : '';
        const details = event.details && Object.keys(event.details).length ? ` — ${JSON.stringify(event.details).slice(0,80)}` : '';

        html += `<div class="timeline-event">
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;"></span>
            <span style="color:var(--muted);font-size:11px;min-width:60px;">${ts}</span>
            <span style="font-weight:500;">${eventType.replace(/_/g, ' ')}</span>
            <span style="color:var(--muted);font-size:12px;">${phase}${details}</span>
          </div>
        </div>`;
      });

      timelineViewEl.innerHTML = html;
    }

    function setConnection(status, detail) {
      const map = {
        live: { text: 'Live', color: 'var(--success)' },
        connecting: { text: 'Connecting…', color: 'var(--warn)' },
        lost: { text: 'Disconnected', color: 'var(--danger)' }
      };
      const info = map[status] || map.connecting;
      connectionEl.style.borderColor = info.color;
      connectionEl.style.color = info.color;
      connectionEl.innerHTML = `<span style="width:10px;height:10px;border-radius:50%;display:inline-block;background:${info.color};"></span>${info.text}${detail ? ' · ' + detail : ''}`;
    }

    let metricsCache = null;

    async function fetchMetrics() {
      try {
        const res = await fetch('/metrics');
        if (res.ok) {
          metricsCache = await res.json();
        }
      } catch (err) {
        console.error('Failed to fetch metrics', err);
      }
    }

    function renderSummary(payload) {
      const byStatus = payload.summary.by_status || {};
      const cards = [
        { label: 'Running Jobs', value: byStatus['running'] || 0 },
        { label: 'Queued', value: byStatus['queued'] || 0 },
        { label: 'Active Agents', value: payload.summary.running_agents || 0 },
        { label: 'Total Jobs (last 50)', value: payload.summary.total_jobs || 0 }
      ];

      // Add metrics data if available (metrics are nested in counters/gauges/timings)
      if (metricsCache && metricsCache.metrics && metricsCache.metrics.counters) {
        const counters = metricsCache.metrics.counters;
        const succeeded = counters['daemon.jobs.succeeded'] || 0;
        // Aggregate all failed counters (may have tags like daemon.jobs.failed{reason=...})
        let failed = 0;
        for (const [key, value] of Object.entries(counters)) {
          if (key === 'daemon.jobs.failed' || key.startsWith('daemon.jobs.failed{')) {
            failed += value;
          }
        }
        if (succeeded > 0 || failed > 0) {
          cards.push({ label: 'Succeeded', value: succeeded });
          cards.push({ label: 'Failed', value: failed });
        }
      }

      summaryEl.innerHTML = cards.map(card => `
        <div class="card">
          <div class="label">${card.label}</div>
          <div class="value">${card.value}</div>
        </div>
      `).join('');
    }

    function statusClass(status) {
      return ['running','queued','failed','succeeded','timed_out'].includes(status) ? status : 'queued';
    }

    // Format model name for display (shorten long Bedrock IDs)
    function formatModelName(modelId) {
      if (!modelId) return '';
      // Map common model IDs to short names
      const modelMap = {
        'anthropic.claude-opus-4-5-20251101-v1:0': 'Opus 4.5',
        'anthropic.claude-opus-4-20250514-v1:0': 'Opus 4',
        'anthropic.claude-sonnet-4-20250514-v1:0': 'Sonnet 4',
        'anthropic.claude-3-5-sonnet-20240620-v1:0': 'Sonnet 3.5',
        'anthropic.claude-3-opus-20240229-v1:0': 'Opus 3',
      };
      if (modelMap[modelId]) return modelMap[modelId];
      // For unknown models, try to extract a readable name
      if (modelId.includes('qwen')) return 'Qwen';
      if (modelId.includes('llama')) return 'Llama';
      if (modelId.includes('mistral')) return 'Mistral';
      // Fallback: show last part of model ID
      const parts = modelId.split('.');
      return parts[parts.length - 1].split('-')[0];
    }

    function renderJobs(payload) {
      const jobs = payload.jobs || [];
      if (!state.selectedJobId && jobs.length) {
        const running = jobs.find(j => j.status === 'running');
        state.selectedJobId = (running || jobs[0]).id;
      }
      jobListEl.innerHTML = jobs.map(job => {
        const selected = job.id === state.selectedJobId ? 'selected' : '';
        const agents = job.agents || { active_count: 0, total_spawned: 0 };
        // Build phase display with model info
        let phaseDisplay = 'No phase yet';
        let modelDisplay = '';
        if (job.latest_phase) {
          const lp = job.latest_phase;
          phaseDisplay = `${lp.phase} · ${lp.status}`;
          if (lp.details?.model) {
            modelDisplay = formatModelName(lp.details.model);
          } else if (lp.details?.provider === 'local') {
            modelDisplay = 'Local CLI';
          }
        }
        return `
          <div class="job-card ${selected}" data-id="${job.id}">
            <div class="job-header">
              <div>
                <div class="job-meta">${job.id.slice(0, 8)} · ${job.type}</div>
                <div class="label">${phaseDisplay}</div>
                ${modelDisplay ? `<div class="muted" style="font-size:11px;">Model: ${modelDisplay}</div>` : ''}
              </div>
              <div class="status ${statusClass(job.status)}">${job.status}</div>
            </div>
            <div class="agent-row" style="margin-top:8px;">
              <div class="pill-mini">Agents: ${agents.active_count || 0} active / ${agents.total_spawned || 0} spawned</div>
              <div class="pill-mini">Priority: ${job.priority}</div>
            </div>
          </div>
        `;
      }).join('');

      Array.from(document.querySelectorAll('.job-card')).forEach(el => {
        el.onclick = () => {
          state.selectedJobId = el.dataset.id;
          renderJobs(payload);
          renderFocus(payload);
          // Auto-fetch data based on active tab
          if (state.activeTab === 'tree') fetchAndRenderTree(state.selectedJobId);
          if (state.activeTab === 'gates') fetchAndRenderGates(state.selectedJobId);
          if (state.activeTab === 'timeline') fetchAndRenderTimeline(state.selectedJobId);
        };
      });
    }

    function renderFocus(payload) {
      const job = (payload.jobs || []).find(j => j.id === state.selectedJobId);
      if (!job) {
        focusTitleEl.textContent = 'Select a running job';
        focusStatusEl.textContent = '--';
        focusStatusEl.className = 'status queued';
        contextEl.textContent = 'Waiting for data…';
        phaseLineEl.textContent = 'Phase: --';
        logListEl.innerHTML = '';
        treeViewEl.innerHTML = 'Select a job to view tree…';
        gatesViewEl.innerHTML = 'Select a job to view gates…';
        timelineViewEl.innerHTML = 'Select a job to view timeline…';
        return;
      }

      focusTitleEl.textContent = `${job.type} · ${job.id.slice(0,8)}`;
      focusStatusEl.textContent = job.status;
      focusStatusEl.className = `status ${statusClass(job.status)}`;
      // Display phase with model info if available
      if (job.latest_phase) {
        const phase = job.latest_phase;
        const modelInfo = phase.details?.model ? ` · ${formatModelName(phase.details.model)}` : '';
        const providerInfo = phase.details?.provider === 'local' ? ' · Local CLI' : '';
        phaseLineEl.textContent = `Phase: ${phase.phase} (${phase.status})${modelInfo}${providerInfo}`;
      } else {
        phaseLineEl.textContent = 'Phase: --';
      }

      if (job.context_preview && job.context_preview.lines && job.context_preview.lines.length) {
        contextEl.textContent = job.context_preview.lines.join('\\n');
      } else {
        contextEl.textContent = 'No context window yet. Waiting for conversation logs...';
      }

      const logs = job.recent_logs || [];
      logListEl.innerHTML = logs.map(log => `
        <div class="log-line">
          <div>
            <div class="muted" style="font-size:11px;">${log.timestamp.slice(11,19)} · ${log.phase || log.source || 'daemon'}</div>
            <div>${log.message}</div>
          </div>
          <div class="badge">${log.level}</div>
        </div>
      `).join('');
    }

    function render(payload) {
      renderSummary(payload);
      renderJobs(payload);
      renderFocus(payload);
    }

    function connect() {
      setConnection('connecting');
      evtSource = new EventSource('/events');
      evtSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          render(payload);
          setConnection('live');
        } catch (err) {
          console.error('Failed to parse payload', err);
        }
      };
      evtSource.onerror = () => {
        setConnection('lost', 'retrying');
        evtSource.close();
        setTimeout(connect, 2000);
      };
    }

    async function fallbackPoll() {
      try {
        const res = await fetch('/status');
        const payload = await res.json();
        render(payload);
      } catch (err) {
        console.error('Status poll failed', err);
      }
    }

    connect();
    fetchMetrics();  // Initial metrics fetch
    setInterval(fallbackPoll, 10000);
    setInterval(fetchMetrics, 30000);  // Refresh metrics every 30s
  </script>
</body>
</html>
"""

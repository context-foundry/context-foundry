import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Job, JobStatus, PhaseEvent

logger = logging.getLogger(__name__)


def get_file_info(fpath: Path) -> Optional[Dict[str, Any]]:
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


def validate_artifact_path(file_path: str) -> Optional[Path]:
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


def read_artifact_manifest(
    cf_dir: Path, working_path: Path
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Read artifact manifest from .context-foundry/artifacts.json.
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

                try:
                    full_path.relative_to(working_resolved)
                except ValueError:
                    logger.warning(f"Manifest path traversal attempt: {rel_path}")
                    continue
            except Exception:
                continue

            # Get file info (skip if missing)
            info = get_file_info(full_path)
            if not info:
                # File declared in manifest but missing - still record it
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
            if phase == "Screenshot" and entry.get("hero"):
                artifact_key = "docs/screenshots/hero.png"
            else:
                normalized = rel_path.replace("\\", "/")
                while normalized.startswith("./"):
                    normalized = normalized[2:]

                filename = (
                    normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized
                )
                filename_lower = filename.lower()

                filename_only_artifacts = {
                    "scout-report.md": "scout-report.md",
                    "scout_report.json": "scout_report.json",
                    "architecture.md": "architecture.md",
                    "architecture.json": "architecture.json",
                    "test-report.md": "test-report.md",
                    "readme.md": "README.md",
                    "session-summary.json": "session-summary.json",
                }

                if filename_lower in filename_only_artifacts:
                    artifact_key = filename_only_artifacts[filename_lower]
                elif normalized.startswith(".context-foundry/"):
                    artifact_key = normalized[len(".context-foundry/") :]
                else:
                    artifact_key = normalized

            if phase not in by_phase:
                by_phase[phase] = {"outputs": {}}
            by_phase[phase]["outputs"][artifact_key] = info

        return by_phase if by_phase else None

    except Exception as e:
        logger.debug(f"Failed to read artifact manifest: {e}")
        return None


def get_job_phases(job: Job) -> List[str]:
    """Derive expected phases for a job from its parameters."""
    params = job.params or {}

    # Priority 1: Explicit target_phases
    target_phases = params.get("target_phases")
    if target_phases:
        return [p.lower() for p in target_phases]

    # Priority 2: Build profile
    build_profile = params.get("build_profile")
    if build_profile:
        try:
            from tools.mcp_utils.phase_registry import get_registry

            registry = get_registry()
            profile = registry.get_profile(build_profile)
            if profile:
                return profile.phases
        except Exception:
            pass

    # Priority 3: simple_mode (legacy)
    if params.get("simple_mode"):
        return ["scout", "architect", "builder", "test", "documentation"]

    # Default: all phases
    return [
        "scout",
        "architect",
        "builder",
        "test",
        "screenshot",
        "documentation",
        "deploy",
        "feedback",
    ]


def get_phase_artifacts(job: Job) -> Dict[str, Any]:
    """Get phase artifact files for a job."""
    working_dir = job.params.get("working_directory") or job.params.get("project_path")
    if not working_dir:
        return {}

    working_path = Path(working_dir)
    cf_dir = working_path / ".context-foundry"
    if not cf_dir.exists():
        return {}

    manifest_artifacts = read_artifact_manifest(cf_dir, working_path)
    artifacts = manifest_artifacts.copy() if manifest_artifacts else {}

    # Scout
    if "Scout" not in artifacts:
        scout_files = {}
        for fname in ["scout-report.md"]:
            info = get_file_info(cf_dir / fname)
            if info:
                scout_files[fname] = info
        if scout_files:
            artifacts["Scout"] = {"outputs": scout_files}

    # Architect
    if "Architect" not in artifacts:
        architect_files = {}
        for fname in ["architecture.md"]:
            info = get_file_info(cf_dir / fname)
            if info:
                architect_files[fname] = info

        docs_dir = working_path / "docs"
        for target_name, target_lower in [
            ("architecture.md", "architecture.md"),
            ("architecture.json", "architecture.json"),
        ]:
            if target_name in architect_files:
                continue
            if docs_dir.exists():
                for fpath in docs_dir.iterdir():
                    if fpath.is_file() and fpath.name.lower() == target_lower:
                        info = get_file_info(fpath)
                        if info:
                            architect_files[target_name] = info
                        break
            if target_name not in architect_files:
                for fpath in working_path.iterdir():
                    if fpath.is_file() and fpath.name.lower() == target_lower:
                        info = get_file_info(fpath)
                        if info:
                            architect_files[target_name] = info
                        break
        if architect_files:
            artifacts["Architect"] = {"outputs": architect_files}

    # Test
    if "Test" not in artifacts:
        test_files = {}
        for fpath in cf_dir.glob("test-report*.md"):
            info = get_file_info(fpath)
            if info:
                test_files[fpath.name] = info
        if not test_files:
            for nested_cf in working_path.glob("**/.context-foundry"):
                if nested_cf == cf_dir:
                    continue
                for fpath in nested_cf.glob("test-report*.md"):
                    info = get_file_info(fpath)
                    if info:
                        rel_path = fpath.relative_to(working_path)
                        test_files[str(rel_path)] = info
        if test_files:
            artifacts["Test"] = {"outputs": test_files}

    # Screenshot
    if "Screenshot" not in artifacts:
        screenshot_files = {}
        image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        screenshot_dirs = [
            working_path / "docs" / "screenshots",
            working_path / "screenshots",
            working_path / "assets" / "screenshots",
            working_path / "images",
        ]
        for screenshots_dir in screenshot_dirs:
            if not screenshots_dir.exists():
                continue
            if "docs/screenshots/hero.png" not in screenshot_files:
                for fpath in screenshots_dir.iterdir():
                    if not fpath.is_file():
                        continue
                    if (
                        fpath.stem.lower() == "hero"
                        and fpath.suffix.lower() in image_extensions
                    ):
                        info = get_file_info(fpath)
                        if info:
                            screenshot_files["docs/screenshots/hero.png"] = info
                        break
            for fpath in screenshots_dir.iterdir():
                if not fpath.is_file():
                    continue
                if fpath.suffix.lower() not in image_extensions:
                    continue
                if fpath.stem.lower() == "hero":
                    continue
                rel_path = fpath.relative_to(working_path)
                key = str(rel_path)
                if key not in screenshot_files:
                    info = get_file_info(fpath)
                    if info:
                        screenshot_files[key] = info
        if screenshot_files:
            artifacts["Screenshot"] = {"outputs": screenshot_files}

    # Documentation
    if "Documentation" not in artifacts:
        doc_files = {}
        info = get_file_info(working_path / "README.md")
        if info:
            doc_files["README.md"] = info
        for fname in ["CHANGELOG.md", "CONTRIBUTING.md", "LICENSE"]:
            info = get_file_info(working_path / fname)
            if info:
                doc_files[fname] = info
        if doc_files:
            artifacts["Documentation"] = {"outputs": doc_files}

    # Deploy
    found_session_path: Optional[Path] = None
    if "Deploy" not in artifacts:
        deploy_files = {}
        session_file = cf_dir / "session-summary.json"
        info = get_file_info(session_file)
        if info:
            deploy_files["session-summary.json"] = info
            found_session_path = session_file
        else:
            root_session = working_path / "session-summary.json"
            info = get_file_info(root_session)
            if info:
                deploy_files["session-summary.json"] = info
                found_session_path = root_session

        deploy_log = cf_dir / "deploy-log.md"
        info = get_file_info(deploy_log)
        if info:
            deploy_files["deploy-log.md"] = info
        else:
            info = get_file_info(working_path / "deploy-log.md")
            if info:
                deploy_files["deploy-log.md"] = info

        if deploy_files:
            artifacts["Deploy"] = {"outputs": deploy_files}
    else:
        deploy_outputs = artifacts.get("Deploy", {}).get("outputs", {})
        if "session-summary.json" in deploy_outputs:
            path_str = deploy_outputs["session-summary.json"].get("path")
            if path_str:
                found_session_path = Path(path_str)

    if found_session_path is None:
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


def read_conversation_preview(
    job: Job, max_lines: int = 12
) -> Optional[Dict[str, Any]]:
    """Read the tail of the most recent conversation log for a job."""
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
    except Exception as exc:
        logger.debug("Failed to read conversation log %s: %s", latest_log, exc)
        return None

    tail = [line[:400] for line in lines[-max_lines:]]
    return {
        "file": latest_log.name,
        "path": str(latest_log),
        "lines": tail,
    }


def build_phase_snapshot(event: Optional[PhaseEvent]) -> Optional[Dict[str, Any]]:
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


def get_recent_file_context(store: Any, scan_dir: Optional[Path] = None) -> str:
    """
    Scan for recently modified files to provide context to the agent.
    Needs store to find active jobs if scan_dir not provided.
    """
    try:
        if not scan_dir:
            scan_dir = Path.cwd()
            # Check running jobs first
            active_jobs = store.list_jobs(status=JobStatus.RUNNING, limit=1)
            if active_jobs:
                wd = active_jobs[0].params.get("working_directory")
                if wd and os.path.isdir(wd):
                    scan_dir = Path(wd)
            else:
                recent_jobs = store.list_jobs(limit=1)
                if recent_jobs:
                    wd = recent_jobs[0].params.get("working_directory")
                    if wd and os.path.isdir(wd):
                        scan_dir = Path(wd)

        logger.info(f"Scanning for context in: {scan_dir}")

        exclude_dirs = {
            ".git",
            "node_modules",
            "dist",
            "build",
            ".context-foundry",
            "__pycache__",
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
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [
                    d for d in dirs if d not in exclude_dirs and not d.startswith(".")
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

        candidates.sort(key=lambda x: x[1], reverse=True)
        top_files = candidates[:5]

        context_str = "RECENTLY MODIFIED FILES IN WORKSPACE:\\n"
        if not top_files:
            return context_str + "(No recent files found)\\n"

        for fpath, mtime in top_files:
            try:
                rel_path = fpath.relative_to(scan_dir)
                mtime_str = datetime.fromtimestamp(mtime).isoformat()
                content_snippet = ""
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = []
                        for _ in range(50):
                            line = f.readline()
                            if not line:
                                break
                            lines.append(line)
                        content_snippet = "".join(lines)
                        if len(content_snippet) > 2000:
                            content_snippet = (
                                content_snippet[:2000] + "\\n...(truncated)..."
                            )
                except Exception:
                    content_snippet = "(binary or unreadable content)"

                context_str += (
                    f"\\n--- FILE: {rel_path} (Last modified: {mtime_str}) ---\\n"
                )
                context_str += content_snippet + "\\n"
            except Exception as e:
                logger.debug(f"Error reading file context for {fpath}: {e}")

        return context_str
    except Exception as e:
        logger.warning(f"Failed to generate file context: {e}")
        return "CONTEXT_SCAN_ERROR: Could not scan local files."


def serialize_job(job_manager: Any, store: Any, job: Job) -> Dict[str, Any]:
    """Serialize a job plus lightweight runtime metadata for the dashboard."""
    tracker = job_manager.get_agent_tracker(job.id)
    phase_events = store.get_phase_events(job.id)
    last_phase = phase_events[-1] if phase_events else None
    logs = store.get_logs(job.id, limit=40)
    log_tail = logs[-10:] if logs else []

    preview = read_conversation_preview(job)

    if tracker:
        agent_stats = tracker.to_dict()
    else:
        agent_stats = job.metadata.get("agent_stats")

    phase_artifacts = get_phase_artifacts(job)
    expected_phases = get_job_phases(job)

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
        "params": job.params,
        "duration_seconds": job.duration(),
        "agents": agent_stats,
        "phase": last_phase.phase if last_phase else None,
        "latest_phase": build_phase_snapshot(last_phase),
        "all_phases": [build_phase_snapshot(e) for e in phase_events],
        "phase_artifacts": phase_artifacts,
        "expected_phases": expected_phases,
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


def build_status_payload(job_manager: Any, store: Any) -> Dict[str, Any]:
    """Create a status snapshot for JSON + SSE responses."""
    jobs = store.list_jobs(limit=50)
    serialized_jobs = [serialize_job(job_manager, store, job) for job in jobs]

    counts: Dict[str, int] = {}
    for job in jobs:
        counts[job.status.value] = counts.get(job.status.value, 0) + 1

    running_agents = 0
    for job in jobs:
        tracker = job_manager.get_agent_tracker(job.id)
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

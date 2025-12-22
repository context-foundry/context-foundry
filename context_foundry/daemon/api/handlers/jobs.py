"""
Job-related API handlers.

Handles job listing, details, artifacts, conversations, and actions.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

from .base import HandlerMixin, parse_query_params

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class JobHandlersMixin(HandlerMixin):
    """Mixin providing job-related handler methods."""

    def handle_job_detail(self, job_id: str, query: str) -> None:
        """Serve details for a specific job."""
        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job {job_id} not found")
                return

            phases = self.server.context.store.get_job_phases(job_id)
            logs = self.server.context.store.get_job_logs(job_id, limit=100)

            self.send_json_response({"job": job, "phases": phases, "logs": logs})
        except Exception as e:
            logger.error(f"Failed to serve job detail: {e}")
            self.send_json_error(500, str(e))

    def handle_job_artifacts(self, job_id: str, query: str) -> None:
        """
        Serve artifacts for a specific job phase.

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
                self.send_json_error(404, f"Job {job_id} not found")
                return

            params = parse_query_params(query)
            phase = params.get("phase", "").lower()

            working_dir = None
            if hasattr(job, "params") and job.params:
                working_dir = job.params.get("working_directory")

            artifacts = []
            if working_dir:
                working_path = Path(working_dir).expanduser().resolve()
                if working_path.exists():
                    artifacts = self._collect_phase_artifacts(working_path, phase)

            self.send_json_response(
                {
                    "job_id": job_id,
                    "phase": phase,
                    "artifacts": artifacts,
                }
            )
        except Exception as e:
            logger.error(f"Failed to serve job artifacts: {e}")
            self.send_json_error(500, str(e))

    def _collect_phase_artifacts(
        self, working_path: Path, phase: str
    ) -> List[Dict[str, Any]]:
        """Collect artifacts for a specific phase."""
        artifacts = []

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

        # Check docs/ directory for documentation phase
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
                    file_type = "document" if ext in (".md", ".txt") else "config"
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

        return artifacts

    def handle_job_conversation(self, job_id: str, query: str) -> None:
        """
        Serve conversation for a specific job.

        Conversations are stored in {working_directory}/.context-foundry/conversations/
        as both .jsonl (structured) and .log (human-readable) files.
        """
        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job {job_id} not found")
                return

            params = parse_query_params(query)
            phase = params.get("phase", "").lower()

            working_dir = None
            if hasattr(job, "params") and job.params:
                working_dir = job.params.get("working_directory")

            messages = []
            if working_dir:
                working_path = Path(working_dir).expanduser().resolve()
                messages = self._load_conversation_messages(working_path, job_id)

            self.send_json_response(
                {
                    "job_id": job_id,
                    "phase": phase,
                    "messages": messages,
                }
            )
        except Exception as e:
            logger.error(f"Failed to serve job conversation: {e}")
            self.send_json_error(500, str(e))

    def _load_conversation_messages(
        self, working_path: Path, job_id: str, max_messages: int = 500
    ) -> List[Dict[str, Any]]:
        """Load conversation messages from JSONL or log file."""
        messages = []
        conversations_dir = working_path / ".context-foundry" / "conversations"
        jsonl_file = conversations_dir / f"conversation-{job_id}.jsonl"
        log_file = conversations_dir / f"conversation-{job_id}.log"

        # Prefer .jsonl for structured data
        if jsonl_file.exists():
            messages = self._parse_jsonl_conversation(jsonl_file, max_messages)
        elif log_file.exists():
            messages = self._parse_log_conversation(log_file)

        return messages

    def _parse_jsonl_conversation(
        self, jsonl_file: Path, max_messages: int
    ) -> List[Dict[str, Any]]:
        """Parse JSONL conversation file."""
        messages = []
        try:
            with open(jsonl_file, "r") as f:
                for line in f:
                    if len(messages) >= max_messages:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        event_type = event.get("event_type", "")

                        if event_type == "assistant":
                            text = event.get("text", "")
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

        return messages

    def _parse_log_conversation(self, log_file: Path) -> List[Dict[str, Any]]:
        """Parse log-format conversation file."""
        messages = []
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

        return messages

    def handle_legacy_job_conversation(self, query: str) -> None:
        """Legacy endpoint for /job-conversation - returns phase status data."""
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

    def handle_cancel_job(self, job_id: str) -> None:
        """Cancel a job."""
        try:
            success = self.server.context.job_manager.cancel_job(job_id)
            if success:
                self.send_json_response({"status": "ok"})
            else:
                self.send_json_error(
                    400, "Failed to cancel job (not found or not running)"
                )
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            self.send_json_error(500, str(e))

    def handle_pause_job(self, job_id: str) -> None:
        """Pause a job."""
        # Currently not supported by JobManager
        self.send_json_error(501, "Pause not yet implemented")

    def handle_resume_job(self, job_id: str) -> None:
        """Resume a paused job."""
        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, "Job not found")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_json_error(400, "Job has no working directory")
                return

            pipeline_state_file = (
                Path(working_dir) / ".context-foundry" / "pipeline-state.json"
            )
            if not pipeline_state_file.exists():
                self.send_json_error(404, "No pipeline state found")
                return

            state = json.loads(pipeline_state_file.read_text())
            phases_remaining = state.get("phases_remaining", [])
            from_phase = phases_remaining[0] if phases_remaining else None

            if not from_phase:
                self.send_json_error(400, "No phases remaining to resume")
                return

            # Re-submit job
            resume_params = job.params.copy()
            resume_params["mode"] = "resume"
            resume_params["resume_from_phase"] = from_phase
            resume_params["job_id"] = job_id

            self.server.context.job_manager.submit_job(
                job_type=job.type, params=resume_params, job_id=job_id, priority=10
            )

            self.send_json_response({"status": "ok", "job_id": job_id})
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            self.send_json_error(500, str(e))

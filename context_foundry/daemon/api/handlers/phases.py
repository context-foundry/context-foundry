"""
Phase-related API handlers.

Handles phase prompts, state, transaction stats, and phase acknowledgement.
"""

import json
import logging
from pathlib import Path
from urllib.parse import parse_qs

from .base import HandlerMixin

logger = logging.getLogger(__name__)


class PhaseHandlersMixin(HandlerMixin):
    """Mixin providing phase-related handler methods."""

    # Reference to rfile for reading request body
    rfile: any

    def handle_phase_prompts(self, query: str) -> None:
        """
        Get phase handoffs for a job. Query: job_id=<id>

        Returns the actual .md handoff files that humans should review,
        along with phase status for HITL approval flow.
        """
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_json_error(400, "Missing 'job_id' parameter")
            return

        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_json_response(
                    {
                        "handoffs": {},
                        "status": {},
                        "warning": "No working directory for job",
                    }
                )
                return

            from tools.mcp_utils.phase_status import get_all_handoffs, get_phase_status

            handoffs = get_all_handoffs(Path(working_dir))
            status = get_phase_status(Path(working_dir))

            self.send_json_response(
                {
                    "handoffs": handoffs,
                    "status": status,
                    "execution_mode": status.get("execution_mode", "autonomous"),
                }
            )

        except Exception as exc:
            logger.warning("Error serving phase handoffs: %s", exc)
            self.send_json_error(500, str(exc))

    def handle_save_phase_prompt(self) -> None:
        """DEPRECATED: Prompt editing is no longer supported."""
        self.send_json_error(
            410,
            "Prompt editing is deprecated. Review handoff files (.md) directly "
            "and use /phase-acknowledge to approve phases.",
        )

    def handle_inject_phase_prompt(self) -> None:
        """DEPRECATED: Use /phase-acknowledge instead."""
        self.send_json_error(
            410, "This endpoint is deprecated. Use POST /phase-acknowledge instead."
        )

    def handle_start_phase_review(self) -> None:
        """DEPRECATED: Phase review state is no longer tracked separately."""
        self.send_json_error(
            410,
            "This endpoint is deprecated. Use GET /phase-prompts to view handoff status.",
        )

    def handle_acknowledge_phase(self) -> None:
        """
        Approve a phase, allowing the next phase to start (HITL mode).
        POST body: {job_id, phase, approved_by?}
        """
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            job_id = data.get("job_id")
            phase = data.get("phase")

            if not job_id or not phase:
                self.send_json_error(400, "Missing 'job_id' or 'phase' in request body")
                return

            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_json_error(400, "Job has no working directory")
                return

            from tools.mcp_utils.phase_status import approve_phase, get_phase_status

            approved_by = data.get("approved_by", "dashboard_user")
            success = approve_phase(Path(working_dir), phase, approved_by)

            if not success:
                status = get_phase_status(Path(working_dir))
                phase_data = status.get("phases", {}).get(phase, {})
                current_status = phase_data.get("status", "unknown")
                self.send_json_error(
                    409,
                    f"Cannot approve phase '{phase}' - current status is '{current_status}' (must be 'pending_approval')",
                )
                return

            logger.info(
                "Phase approved: %s/%s by %s - next phase will start",
                job_id[:8],
                phase,
                approved_by,
            )

            self.send_json_response(
                {
                    "success": True,
                    "job_id": job_id,
                    "phase": phase,
                    "status": "approved",
                    "approved_by": approved_by,
                    "message": f"Phase {phase} approved. Next phase will start.",
                }
            )

            # Auto-resume pipeline if paused
            self._resume_pipeline_if_paused(job_id, working_dir)

        except json.JSONDecodeError as exc:
            self.send_json_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error approving phase: %s", exc)
            self.send_json_error(500, str(exc))

    def _resume_pipeline_if_paused(self, job_id: str, working_dir: str) -> None:
        """Resume pipeline if it's in a paused state."""
        try:
            from tools.mcp_utils.pipeline_state import get_pipeline_state
            from ..models import JobStatus, JobType

            project_dir = Path(working_dir)
            state = get_pipeline_state(project_dir)

            if not state or not state.phases_remaining:
                return

            job = self.server.context.store.get_job(job_id)
            if job and job.status == JobStatus.RUNNING:
                logger.info(f"Job {job_id} is still running, not resuming")
                return

            resume_from = state.phases_remaining[0]

            # Inherit execution_mode from original job to preserve HITL mode
            execution_mode = "autonomous"
            if job:
                execution_mode = job.params.get("execution_mode", "autonomous")

            task_config = {
                "task": f"Resume build from {resume_from}",
                "working_directory": str(project_dir),
                "mode": "resume",
                "resume_from_phase": resume_from,
                "timeout_minutes": 90,
                "execution_mode": execution_mode,
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
                job_id=job_id,
            )

        except Exception as e:
            logger.error(f"Failed to auto-resume pipeline: {e}")

    def handle_phase_state(self, query: str) -> None:
        """
        Get phase states for a job. Query: job_id=<id>&phase=<phase>?
        If phase is omitted, returns all phases.
        """
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]
        phase = params.get("phase", [None])[0]

        if not job_id:
            self.send_json_error(400, "Missing 'job_id' parameter")
            return

        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_json_response(
                    {"phases": {}, "warning": "No working directory for job"}
                )
                return

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

            self.send_json_response(result)

        except Exception as exc:
            logger.warning("Error serving phase state: %s", exc)
            self.send_json_error(500, str(exc))

    def handle_transaction_stats(self, query: str) -> None:
        """Get overall transaction statistics for a job. Query: job_id=<id>"""
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_json_error(400, "Missing 'job_id' parameter")
            return

        try:
            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job not found: {job_id}")
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_json_response(
                    {"stats": {}, "warning": "No working directory for job"}
                )
                return

            from tools.mcp_utils.phase_status import get_phase_status

            status_data = get_phase_status(Path(working_dir))
            phases = status_data.get("phases", {})

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
                "job_id": job_id,
                "job_status": job.status.value,
                "job_created_at": job.created_at.isoformat(),
                "job_duration_seconds": job.duration(),
            }

            if job.started_at:
                stats["job_started_at"] = job.started_at.isoformat()
            if job.completed_at:
                stats["job_completed_at"] = job.completed_at.isoformat()

            self.send_json_response(stats)

        except Exception as exc:
            logger.warning("Error serving transaction stats: %s", exc)
            self.send_json_error(500, str(exc))

"""
Approval-related API handlers.

Handles approval gates, phase approvals, and pipeline resume functionality.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from .base import HandlerMixin

logger = logging.getLogger(__name__)


class ApprovalHandlersMixin(HandlerMixin):
    """Mixin providing approval-related handler methods."""

    # Reference to rfile for reading request body
    rfile: any

    def handle_pending_approvals(self) -> None:
        """List all pending approval requests and paused HITL pipelines."""
        try:
            from tools.mcp_utils.approval_gates import ApprovalManager

            manager = ApprovalManager()
            pending = manager.list_pending_requests()

            approvals = [req.to_dict() for req in pending]

            # Also check for paused HITL pipelines
            approvals.extend(self._get_paused_pipelines())

            self.send_json_response({"approvals": approvals})

        except ImportError as exc:
            logger.warning("approval_gates module not available: %s", exc)
            self.send_json_response(
                {
                    "approvals": [],
                    "warning": "Approval system not available",
                }
            )
        except Exception as exc:
            logger.warning("Error listing pending approvals: %s", exc)
            self.send_json_error(500, str(exc))

    def _get_paused_pipelines(self) -> List[Dict[str, Any]]:
        """Get list of paused HITL pipelines as approval-like entries."""
        from ..models import JobStatus

        approvals = []
        seen_dirs = set()

        try:
            for job in self.server.context.store.list_jobs():
                working_dir = job.params.get("working_directory")
                if working_dir and working_dir not in seen_dirs:
                    seen_dirs.add(working_dir)
                    pipeline_state_file = (
                        Path(working_dir) / ".context-foundry" / "pipeline-state.json"
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

                                # Race condition prevention
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

        return approvals

    def handle_approve_phase(self) -> None:
        """Approve a pending phase request. POST body: {request_id, approved_by?, reason?}"""
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            request_id = data.get("request_id")
            if not request_id:
                self.send_json_error(400, "Missing 'request_id' in request body")
                return

            approved_by = data.get("approved_by", "dashboard_user")
            reason = data.get("reason")

            from tools.mcp_utils.approval_gates import approve_phase

            result = approve_phase(request_id, approved_by, reason)

            if result:
                self.send_json_response(
                    {
                        "success": True,
                        "request_id": request_id,
                        "status": result.status.value,
                    }
                )
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header(
                    "Content-Length",
                    str(len(b'{"success":false,"error":"Request not found"}')),
                )
                self.end_headers()
                self.wfile.write(b'{"success":false,"error":"Request not found"}')

        except ImportError as exc:
            logger.warning("approval_gates module not available: %s", exc)
            self.send_json_error(503, "Approval system not available")
        except json.JSONDecodeError as exc:
            self.send_json_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error approving phase: %s", exc)
            self.send_json_error(500, str(exc))

    def handle_deny_phase(self) -> None:
        """Deny a pending phase request. POST body: {request_id, denied_by?, reason?}"""
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            request_id = data.get("request_id")
            if not request_id:
                self.send_json_error(400, "Missing 'request_id' in request body")
                return

            denied_by = data.get("denied_by", "dashboard_user")
            reason = data.get("reason")

            from tools.mcp_utils.approval_gates import deny_phase

            result = deny_phase(request_id, denied_by, reason)

            if result:
                self.send_json_response(
                    {
                        "success": True,
                        "request_id": request_id,
                        "status": result.status.value,
                    }
                )
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header(
                    "Content-Length",
                    str(len(b'{"success":false,"error":"Request not found"}')),
                )
                self.end_headers()
                self.wfile.write(b'{"success":false,"error":"Request not found"}')

        except ImportError as exc:
            logger.warning("approval_gates module not available: %s", exc)
            self.send_json_error(503, "Approval system not available")
        except json.JSONDecodeError as exc:
            self.send_json_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error denying phase: %s", exc)
            self.send_json_error(500, str(exc))

    def handle_resume_pipeline(self) -> None:
        """Resume a paused HITL pipeline from the next phase."""
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8")) if body else {}

            job_id = data.get("job_id")
            from_phase = data.get("from_phase")

            if not job_id:
                self.send_json_error(400, "Missing 'job_id' in request body")
                return

            job = self.server.context.store.get_job(job_id)
            if not job:
                self.send_json_error(404, f"Job not found: {job_id}")
                return

            # Race condition prevention
            from ..models import JobStatus

            active_states = {
                JobStatus.RUNNING,
                JobStatus.QUEUED,
                JobStatus.WAITING_APPROVAL,
            }
            if job.status in active_states:
                self.send_json_error(
                    409,
                    f"Job {job_id} is in {job.status.value} state. Wait for it to complete before resuming.",
                )
                return

            working_dir = job.params.get("working_directory")
            if not working_dir:
                self.send_json_error(400, "Job has no working directory")
                return

            # Read and validate pipeline state
            pipeline_state_file = (
                Path(working_dir) / ".context-foundry" / "pipeline-state.json"
            )
            if not pipeline_state_file.exists():
                self.send_json_error(404, "No pipeline state found")
                return

            try:
                state = json.loads(pipeline_state_file.read_text())
            except json.JSONDecodeError:
                self.send_json_error(500, "Invalid pipeline state JSON")
                return

            if state.get("state") != "paused":
                self.send_json_error(
                    400, f"Pipeline is not paused (state: {state.get('state')})"
                )
                return

            # Validate HITL mode
            task_config = state.get("task_config", {})
            pause_after_phases = state.get("pause_after_phases") or task_config.get(
                "pause_after_phases"
            )
            execution_mode = state.get("execution_mode") or task_config.get(
                "execution_mode"
            )

            if not pause_after_phases and execution_mode != "hitl":
                self.send_json_error(400, "Pipeline is not in HITL mode")
                return

            # Verify job_id matches
            pipeline_job_id = task_config.get("job_id")
            if pipeline_job_id and pipeline_job_id != job_id:
                self.send_json_error(
                    400, f"Job ID mismatch: pipeline belongs to {pipeline_job_id}"
                )
                return

            # Determine next phase
            phases_remaining = state.get("phases_remaining", [])
            if from_phase:
                resume_from = from_phase
            elif phases_remaining:
                resume_from = phases_remaining[0]
            else:
                self.send_json_error(400, "No phases remaining to resume")
                return

            # Submit resume job
            resume_params = job.params.copy()
            resume_params["mode"] = "resume"
            resume_params["resume_from_phase"] = resume_from
            resume_params["job_id"] = job_id

            self.server.context.job_manager.submit_job(
                job_type=job.type, params=resume_params, job_id=job_id, priority=10
            )

            self.send_json_response({"status": "ok", "job_id": job_id})

        except Exception as e:
            logger.error(f"Failed to resume pipeline: {e}")
            self.send_json_error(500, str(e))

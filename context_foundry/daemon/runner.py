"""
Job Runner for Context Foundry Daemon

Executes jobs by delegating to CF orchestrator and tracking progress.
Emits phase events and logs to Store for visibility.
"""

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .models import Job, PhaseEvent, LogEntry
from .store import Store

# Import delegation utilities
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))
from mcp_utils.delegation import (
    delegate_to_claude_code_async_impl,
    get_delegation_result_impl,
)
from mcp_utils.phase_tracking import read_phase_info
from mcp_utils.output_utils import create_output_summary


logger = logging.getLogger(__name__)


class Runner:
    """
    Executes CF Daemon jobs via delegation to CF orchestrator

    Responsibilities:
    - Start async delegation for job
    - Poll for completion and progress
    - Track phase transitions (Scout → Architect → Builder → Test)
    - Emit PhaseEvents to Store
    - Emit LogEntries to Store
    - Trigger pattern merge on success
    """

    def __init__(self, store: Store):
        """
        Initialize Runner

        Args:
            store: Store instance for persistence
        """
        self.store = store
        self.active_tasks: Dict[str, Dict[str, Any]] = {}

    def run(self, job: Job) -> Dict[str, Any]:
        """
        Execute a job

        Args:
            job: Job instance to execute

        Returns:
            Dict with execution results

        Raises:
            RuntimeError: If job execution fails
        """
        logger.info(f"Starting job execution: {job.id}")

        # Emit start log
        self._emit_log(job.id, "INFO", f"Starting {job.type.value} job", None)

        # Determine working directory from job params
        working_dir = job.params.get("working_directory")
        if not working_dir:
            working_dir = job.params.get("project_path", str(Path.cwd()))

        # Extract task description
        task = job.params.get("task", job.params.get("description", "Build project"))

        # Extract timeout
        timeout_minutes = job.params.get("timeout_minutes", 120)

        # Extract additional flags
        additional_flags = job.params.get("additional_flags", None)

        try:
            # Handle autonomous builds differently from simple delegations
            from context_foundry.daemon.models import JobType

            if job.type == JobType.AUTONOMOUS_BUILD:
                # Full Scout→Architect→Builder→Test flow
                self._emit_log(job.id, "INFO", "Starting autonomous build", None)
                logger.info(
                    f"[TRACE] run() calling _run_autonomous_build for job {job.id}"
                )

                result = self._run_autonomous_build(job, working_dir, timeout_minutes)

                logger.info(
                    f"[TRACE] run() received result from _run_autonomous_build: status={result.get('status')}"
                )

                # If successful, trigger pattern merge and update job status
                if result.get("status") == "completed":
                    self._emit_log(job.id, "INFO", "Autonomous build completed", None)
                    logger.info(
                        f"[TRACE] run() calling _merge_patterns for job {job.id}"
                    )

                    self._merge_patterns(job.id, working_dir)

                    logger.info(
                        "[TRACE] run() pattern merge complete, updating job status to SUCCEEDED"
                    )

                    # Update job status directly in store
                    from context_foundry.daemon.models import JobStatus
                    from datetime import datetime

                    self.store.update_job_status(
                        job.id,
                        JobStatus.SUCCEEDED,
                        completed_at=datetime.now(),
                        result={
                            "success": True,
                            "exit_code": 0,
                            "phases_completed": result.get("phases_completed", []),
                            "test_iterations": result.get("test_iterations", 0),
                            "duration_seconds": result.get("duration_seconds", 0),
                        },
                    )

                    logger.info(f"[TRACE] Job {job.id} marked as SUCCEEDED")

                    return {
                        "success": True,
                        "exit_code": 0,
                        "phases_completed": result.get("phases_completed", []),
                        "test_iterations": result.get("test_iterations", 0),
                        "duration_seconds": result.get("duration_seconds", 0),
                    }
                else:
                    error_msg = result.get("error", "Autonomous build failed")
                    self._emit_log(job.id, "ERROR", error_msg, None)

                    logger.info(
                        f"[TRACE] run() updating job status to FAILED: {error_msg}"
                    )

                    # Update job status directly in store
                    from context_foundry.daemon.models import JobStatus
                    from datetime import datetime

                    self.store.update_job_status(
                        job.id,
                        JobStatus.FAILED,
                        completed_at=datetime.now(),
                        result={"error": error_msg},
                    )

                    logger.info(f"[TRACE] Job {job.id} marked as FAILED")

                    raise RuntimeError(error_msg)
            else:
                # Standard delegation flow (for DELEGATION, ENHANCEMENT, etc.)
                delegation_result = self._start_delegation(
                    task=task,
                    working_directory=working_dir,
                    timeout_minutes=timeout_minutes,
                    additional_flags=additional_flags,
                )

                task_id = delegation_result.get("task_id")
                if not task_id:
                    raise RuntimeError(
                        f"Failed to start delegation: {delegation_result.get('error')}"
                    )

                self._emit_log(job.id, "INFO", f"Delegation started: {task_id}", None)

                # Poll for completion and track progress
                result = self._poll_for_completion(
                    job.id, task_id, working_dir, timeout_minutes
                )

                # If successful, trigger pattern merge
                if result.get("exit_code") == 0:
                    self._emit_log(job.id, "INFO", "Job completed successfully", None)
                    self._merge_patterns(job.id, working_dir)

                    return {
                        "success": True,
                        "task_id": task_id,
                        "exit_code": 0,
                        "output_summary": result.get("output_summary", ""),
                    }
                else:
                    error_msg = result.get(
                        "error", f"Job failed with exit code {result.get('exit_code')}"
                    )
                    self._emit_log(job.id, "ERROR", error_msg, None)
                    raise RuntimeError(error_msg)

        except Exception as e:
            logger.error(f"Job {job.id} execution failed: {e}", exc_info=True)
            self._emit_log(job.id, "ERROR", f"Job execution failed: {str(e)}", None)
            raise

    def _start_delegation(
        self,
        task: str,
        working_directory: str,
        timeout_minutes: float,
        additional_flags: Optional[str],
    ) -> Dict[str, Any]:
        """Start async delegation"""
        result_json = delegate_to_claude_code_async_impl(
            task=task,
            working_directory=working_directory,
            timeout_minutes=timeout_minutes,
            additional_flags=additional_flags,
            active_tasks=self.active_tasks,
        )

        return json.loads(result_json)

    def _poll_for_completion(
        self,
        job_id: str,
        task_id: str,
        working_dir: str,
        timeout_minutes: float = 120,
    ) -> Dict[str, Any]:
        """
        Poll for delegation completion and track phase progress

        Args:
            job_id: Job ID
            task_id: Delegation task ID
            working_dir: Working directory
            timeout_minutes: Maximum time to wait (default: 120 minutes)

        Returns:
            Dict with final results
        """
        last_phase = None
        poll_interval = 5  # seconds

        start_time = datetime.now()
        timeout_seconds = timeout_minutes * 60

        while True:
            # Check timeout
            elapsed_seconds = (datetime.now() - start_time).total_seconds()
            if elapsed_seconds > timeout_seconds:
                # Timeout exceeded - kill the process
                logger.warning(
                    f"Job {job_id} exceeded timeout of {timeout_minutes} minutes"
                )

                if task_id in self.active_tasks:
                    task_info = self.active_tasks[task_id]
                    process = task_info.get("process")
                    if process and process.poll() is None:
                        # Process still running - kill it
                        logger.warning(f"Killing hung process for job {job_id}")
                        try:
                            process.kill()
                            process.wait(timeout=10)
                        except Exception as e:
                            logger.error(f"Failed to kill process: {e}")

                    # Remove from active tasks
                    del self.active_tasks[task_id]

                self._emit_log(
                    job_id,
                    "ERROR",
                    f"Job exceeded timeout of {timeout_minutes} minutes and was terminated",
                    None,
                )

                raise RuntimeError(f"Job exceeded timeout of {timeout_minutes} minutes")

            # Check if task is still active
            if task_id not in self.active_tasks:
                # Task completed or failed
                break

            task_info = self.active_tasks[task_id]

            # Check phase transitions
            phase_info = read_phase_info(working_dir, start_time)
            current_phase = phase_info.get("phase")

            if current_phase and current_phase != last_phase:
                # Phase transition detected
                self._emit_phase_event(
                    job_id=job_id,
                    phase=current_phase,
                    status="in_progress",
                    details=phase_info,
                )

                self._emit_log(
                    job_id,
                    "INFO",
                    f"Phase transition: {last_phase or 'Start'} → {current_phase}",
                    current_phase,
                )

                last_phase = current_phase

            # Check if process has completed
            process = task_info.get("process")
            if process and process.poll() is not None:
                # Process finished, get final results
                break

            # Sleep before next poll
            time.sleep(poll_interval)

        # Get final delegation results
        result_json = get_delegation_result_impl(
            task_id=task_id,
            include_full_output=False,  # Use summary to avoid token overhead
            active_tasks=self.active_tasks,
            read_phase_info_func=lambda wd, ts=None: read_phase_info(wd, ts),
            create_output_summary_func=create_output_summary,
            merge_project_patterns_func=None,  # We'll handle pattern merge separately
        )

        result = json.loads(result_json)

        # Emit final phase event if we tracked phases
        if last_phase:
            final_status = "completed" if result.get("exit_code") == 0 else "failed"
            self._emit_phase_event(
                job_id=job_id,
                phase=last_phase,
                status=final_status,
                details=result.get("phase_info", {}),
            )

        # Clean up task from active_tasks
        self.active_tasks.pop(task_id, None)

        return result

    def _emit_phase_event(
        self,
        job_id: str,
        phase: str,
        status: str,
        details: Dict[str, Any],
    ):
        """Emit a phase event to Store"""
        try:
            event = PhaseEvent.create(
                job_id=job_id,
                phase=phase,
                status=status,
                details=details,
                tokens_used=details.get("tokens_used"),
                context_percent=details.get("context_percent"),
            )

            self.store.save_phase_event(event)
            logger.debug(f"Emitted phase event: {phase} ({status})")

        except Exception as e:
            logger.error(f"Failed to emit phase event: {e}", exc_info=True)

    def _emit_log(
        self,
        job_id: str,
        level: str,
        message: str,
        phase: Optional[str],
    ):
        """Emit a log entry to Store"""
        try:
            log = LogEntry.create(
                job_id=job_id,
                level=level,
                message=message,
                phase=phase,
                source="runner",
            )

            self.store.save_log(log)

        except Exception as e:
            logger.error(f"Failed to emit log: {e}", exc_info=True)

    def _run_autonomous_build(
        self, job: Job, working_dir: str, timeout_minutes: float
    ) -> Dict[str, Any]:
        """
        Execute full autonomous build with Scout→Architect→Builder→Test flow.

        This is called for AUTONOMOUS_BUILD job types and runs the complete
        build pipeline synchronously in the worker thread.

        Args:
            job: Job instance with autonomous build parameters
            working_dir: Working directory for the build
            timeout_minutes: Maximum execution time in minutes

        Returns:
            Build result dict with status, phases_completed, etc.
        """
        import sys
        from pathlib import Path

        # Add context-foundry to path to import autonomous_build module
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        from tools.mcp_utils.autonomous_build import execute_build_with_phase_spawning
        from tools.mcp_utils.project_detection import detect_existing_codebase
        from tools.mcp_utils.task_classification import detect_task_intent

        # Extract parameters from job
        task = job.params.get("task", "Build project")
        mode = job.params.get("mode", "new_project")
        max_test_iterations = job.params.get("max_test_iterations", 3)
        incremental = job.params.get("incremental", False)
        force_rebuild = job.params.get("force_rebuild", False)

        # Detect project info
        working_path = Path(working_dir)
        codebase_info = detect_existing_codebase(working_path)

        # Auto-adjust mode based on task intent
        if mode == "new_project" and codebase_info["has_code"]:
            detected_intent = detect_task_intent(task)
            mode = detected_intent
            self._emit_log(
                job.id, "INFO", f"Auto-adjusted mode: new_project → {mode}", None
            )

        # Check for Flowise mode
        flowise_mode = codebase_info.get("flowise_flow", False)
        if not flowise_mode:
            task_lower = task.lower()
            flowise_keywords = ["flowise", "agent flow", "chatflow"]
            if any(kw in task_lower for kw in flowise_keywords):
                flowise_mode = True
                self._emit_log(job.id, "INFO", "Flowise mode enabled", None)

        project_type = codebase_info.get("project_type", "unknown")
        has_code = codebase_info.get("has_code", True)
        # For new projects, always enable test loop since we'll generate code
        # For existing projects, only enable if code already exists
        enable_test_loop = (mode == "new_project") or has_code

        # Build task config
        task_config = {
            "task": task,
            "working_directory": working_dir,
            "github_repo_name": job.params.get("github_repo_name"),
            "mode": mode,
            "enable_test_loop": enable_test_loop,
            "max_test_iterations": max_test_iterations,
            "incremental": incremental and not force_rebuild,
            "flowise_flow": flowise_mode,
            "project_type": project_type,
            "codebase_detection": codebase_info,
        }

        # Emit phases info
        self._emit_log(
            job.id,
            "INFO",
            f"Build config: mode={mode}, project_type={project_type}, test_loop={enable_test_loop}",
            None,
        )

        # Execute build
        logger.info(
            f"[TRACE] Calling execute_build_with_phase_spawning for job {job.id} at {datetime.now().isoformat()}"
        )

        result = execute_build_with_phase_spawning(
            task=task,
            working_directory=working_path,
            task_config=task_config,
            enable_test_loop=enable_test_loop,
            max_test_iterations=max_test_iterations,
            flowise_mode=flowise_mode,
            project_type=project_type,
            incremental=incremental and not force_rebuild,
            timeout_minutes=timeout_minutes,
        )

        logger.info(
            f"[TRACE] execute_build_with_phase_spawning RETURNED for job {job.id} at {datetime.now().isoformat()}"
        )
        logger.info(
            f"[TRACE] Result status: {result.get('status')}, phases: {result.get('phases_completed')}"
        )

        return result

    def _merge_patterns(self, job_id: str, working_dir: str):
        """
        Push learned patterns directly to Context Codex database

        This implements self-improvement by extracting learnings from test failures
        and pushing them to the searchable knowledge base.
        """
        try:
            self._emit_log(
                job_id,
                "INFO",
                "Pushing learned patterns to Context Codex",
                None,
            )

            # Check if project has patterns to merge
            pattern_file = (
                Path(working_dir)
                / ".context-foundry"
                / "patterns"
                / "common-issues.json"
            )

            if not pattern_file.exists():
                logger.info(f"No patterns found for job {job_id}, skipping codex push")
                return

            # Load patterns from file
            import json

            with open(pattern_file) as f:
                patterns_data = json.load(f)

            patterns = patterns_data.get("patterns", [])
            if not patterns:
                logger.info(f"No patterns in file for job {job_id}")
                return

            # Import codex integration
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))
            from mcp_utils.codex_integration import push_issue_to_codex

            # Push each pattern to Context Codex database
            patterns_pushed = 0
            for pattern in patterns:
                try:
                    # Extract pattern data
                    title = pattern.get("title", "Unknown issue")
                    description = pattern.get(
                        "description", pattern.get("error_message", "")
                    )
                    severity = pattern.get("severity", "MEDIUM")
                    tech_stack = pattern.get("tech_stack", [])
                    project_types = pattern.get("project_types", [])
                    tags = tech_stack + project_types
                    solution = pattern.get("solution", {})
                    solution_desc = (
                        solution.get("description")
                        if isinstance(solution, dict)
                        else str(solution)
                    )

                    # Push to codex database
                    entry_id = push_issue_to_codex(
                        title=title,
                        description=description,
                        severity=severity,
                        tags=tags,
                        project_types=project_types,
                        solution_description=solution_desc if solution_desc else None,
                    )

                    patterns_pushed += 1
                    logger.debug(f"Pushed pattern to codex: {title} ({entry_id})")

                except Exception as e:
                    logger.warning(
                        f"Failed to push pattern '{pattern.get('title')}' to codex: {e}"
                    )
                    continue

            self._emit_log(
                job_id,
                "INFO",
                f"Successfully pushed {patterns_pushed}/{len(patterns)} patterns to Context Codex",
                None,
            )

        except Exception as e:
            logger.error(
                f"Failed to push patterns to codex for job {job_id}: {e}", exc_info=True
            )
            self._emit_log(
                job_id,
                "WARNING",
                f"Codex push failed: {str(e)}",
                None,
            )

    def cleanup_active_tasks(self):
        """
        Kill all active subprocess tasks

        Called during daemon shutdown to prevent orphaned processes.
        Iterates through all tracked tasks and terminates their subprocesses.
        """
        if not self.active_tasks:
            return

        logger.info(f"Cleaning up {len(self.active_tasks)} active tasks...")

        for task_id, task_info in list(self.active_tasks.items()):
            process = task_info.get("process")
            if process and process.poll() is None:
                # Process still running - kill it
                logger.info(
                    f"Terminating subprocess for task {task_id} (PID {process.pid})"
                )
                try:
                    process.terminate()
                    # Give it 5 seconds to terminate gracefully
                    try:
                        process.wait(timeout=5)
                        logger.info(f"Task {task_id} terminated gracefully")
                    except subprocess.TimeoutExpired:
                        # Still running after SIGTERM - force kill
                        logger.warning(
                            f"Task {task_id} did not terminate, sending SIGKILL"
                        )
                        process.kill()
                        process.wait(timeout=2)
                except Exception as e:
                    logger.error(f"Failed to kill process for task {task_id}: {e}")

        # Clear all active tasks
        self.active_tasks.clear()
        logger.info("Active task cleanup complete")


def create_runner(store: Store) -> Runner:
    """
    Factory function to create Runner instance

    Args:
        store: Store instance

    Returns:
        Configured Runner instance
    """
    return Runner(store)

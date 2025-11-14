"""
Job Runner for Context Foundry Daemon

Executes jobs by delegating to CF orchestrator and tracking progress.
Emits phase events and logs to Store for visibility.
"""

import json
import logging
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
from mcp_utils.pattern_management import merge_project_patterns_impl


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
                result = self._run_autonomous_build(job, working_dir)

                # If successful, trigger pattern merge
                if result.get("status") == "completed":
                    self._emit_log(job.id, "INFO", "Autonomous build completed", None)
                    self._merge_patterns(job.id, working_dir)

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
                result = self._poll_for_completion(job.id, task_id, working_dir)

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
    ) -> Dict[str, Any]:
        """
        Poll for delegation completion and track phase progress

        Args:
            job_id: Job ID
            task_id: Delegation task ID
            working_dir: Working directory

        Returns:
            Dict with final results
        """
        last_phase = None
        poll_interval = 5  # seconds

        start_time = datetime.now()

        while True:
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

    def _run_autonomous_build(self, job: Job, working_dir: str) -> Dict[str, Any]:
        """
        Execute full autonomous build with Scout→Architect→Builder→Test flow.

        This is called for AUTONOMOUS_BUILD job types and runs the complete
        build pipeline synchronously in the worker thread.

        Args:
            job: Job instance with autonomous build parameters
            working_dir: Working directory for the build

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
        enable_test_loop = has_code  # Auto-detect testing

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
        result = execute_build_with_phase_spawning(
            task=task,
            working_directory=working_path,
            task_config=task_config,
            enable_test_loop=enable_test_loop,
            max_test_iterations=max_test_iterations,
            flowise_mode=flowise_mode,
            project_type=project_type,
            incremental=incremental and not force_rebuild,
        )

        return result

    def _merge_patterns(self, job_id: str, working_dir: str):
        """
        Trigger pattern merge after successful job completion

        This implements self-improvement by extracting learnings and
        writing them back to the pattern library.
        """
        try:
            self._emit_log(
                job_id,
                "INFO",
                "Merging learned patterns to pattern library",
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
                logger.info(f"No patterns found for job {job_id}, skipping merge")
                return

            # Merge patterns
            result = merge_project_patterns_impl(
                project_pattern_file=str(pattern_file),
                pattern_type="common-issues",
                increment_build_count=True,
            )

            if result.get("status") == "success":
                patterns_merged = result.get("patterns_merged", 0)
                self._emit_log(
                    job_id,
                    "INFO",
                    f"Successfully merged {patterns_merged} patterns to global library",
                    None,
                )
            else:
                logger.warning(f"Pattern merge had issues: {result}")

        except Exception as e:
            logger.error(
                f"Failed to merge patterns for job {job_id}: {e}", exc_info=True
            )
            self._emit_log(
                job_id,
                "WARNING",
                f"Pattern merge failed: {str(e)}",
                None,
            )


def create_runner(store: Store) -> Runner:
    """
    Factory function to create Runner instance

    Args:
        store: Store instance

    Returns:
        Configured Runner instance
    """
    return Runner(store)

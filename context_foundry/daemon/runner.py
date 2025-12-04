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

# Import build notifications
from build_notifications import notify_build_started, notify_build_complete


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
            working_dir = job.params.get("project_path")

        # If still no working_dir, generate from prompt/task
        if not working_dir:
            import re
            from tools.mcp_utils.path_utils import get_projects_root

            prompt = job.params.get("prompt", job.params.get("task", "project"))

            # Extract project name from prompt
            # Try common patterns: "build a X", "create X", "make X"
            project_name_pattern = r"(?:build|create|make|develop)\s+(?:a|an)?\s+([a-z0-9\s-]+?)(?:\s+(?:app|application|project|website|game|tool|calculator|using|with|for))"
            match = re.search(project_name_pattern, prompt.lower())

            if match:
                raw_name = match.group(1).strip()
            else:
                # Fallback: use first few meaningful words
                words = prompt.split()[:5]
                raw_name = " ".join(words)

            # Convert to kebab-case directory name
            project_name = re.sub(r"[^a-zA-Z0-9]+", "-", raw_name.lower()).strip("-")
            if len(project_name) > 50:
                project_name = project_name[:50].rsplit("-", 1)[0]

            # Get projects root and create path
            projects_root = get_projects_root()
            working_dir = str(projects_root / project_name)

            logger.info(f"Generated working_dir from prompt: {working_dir}")

        # Import needed modules for random ID and codebase detection
        import random
        import re
        from pathlib import Path
        from context_foundry.daemon.models import JobType

        mode = job.params.get("mode", "new_project")

        # Save the ORIGINAL base path (before any random ID suffix) for safety checks
        base_path_for_detection = working_dir

        # Append random ID for new projects BEFORE checking for existing code
        # This ensures every new build gets a unique directory, avoiding conflicts
        # with previous builds or existing projects
        #
        # ONLY append random ID for:
        # 1. AUTONOMOUS_BUILD jobs (not delegation/enhancement/testing jobs)
        # 2. In new_project mode (user's explicit intent)
        # 3. When directory name doesn't already have a random ID suffix
        # 4. NOT for resume jobs (they must use the exact paused directory)
        resume_from_phase = job.params.get("resume_from_phase")
        is_resume_job = resume_from_phase is not None

        if (
            job.type == JobType.AUTONOMOUS_BUILD
            and mode == "new_project"
            and not is_resume_job
        ):
            working_path = Path(working_dir)
            original_name = working_path.name

            # Check if the path already has a random ID suffix (avoid double-suffixing)
            # Pattern: ends with "-CDC" where C=consonant, D=digit (strict match for our generator)
            already_has_suffix = bool(
                re.search(
                    r"-[bcdfghjklmnpqrstvwxz][0-9][bcdfghjklmnpqrstvwxz]$",
                    original_name,
                )
            )

            if already_has_suffix:
                logger.info(
                    f"Path already has random ID suffix, skipping: {original_name}"
                )
            else:
                # Generate 3-character cute random ID (e.g., "c4r", "n3r", "b0w")
                # Format: consonant + digit + consonant for memorable, pronounceable names
                consonants = "bcdfghjklmnpqrstvwxz"

                # Keep trying until we find a unique ID (max 20 attempts)
                # With 4,000 possible IDs (20 consonants × 10 digits × 20 consonants),
                # collision is extremely unlikely
                max_attempts = 20
                for attempt in range(max_attempts):
                    c1 = random.choice(consonants)
                    digit = random.choice("0123456789")
                    c2 = random.choice(consonants)
                    random_id = f"{c1}{digit}{c2}"

                    new_name = f"{original_name}-{random_id}"
                    new_path = working_path.parent / new_name

                    if not new_path.exists():
                        # Found unique directory name
                        working_dir = str(new_path)
                        # Create the directory immediately to ensure it exists for the build script
                        new_path.mkdir(parents=True, exist_ok=True)
                        logger.info(
                            f"Appending random ID for new project: {original_name} → {new_name}"
                        )

                        # Update job params with the ACTUAL working directory
                        # This ensures metadata, logs, and user-facing messages show the correct path
                        job.params["working_directory"] = working_dir

                        # IMPORTANT: Save job to persist the updated working directory
                        self.store.save_job(job)
                        break
                else:
                    # All attempts failed (very unlikely with 4,000 possible IDs)
                    logger.warning(
                        f"Could not find unique random ID after {max_attempts} attempts, "
                        f"using original path: {working_dir}"
                    )

        # Check the BASE path (before random ID) for existing code
        # This provides a safety warning if user might want enhancement instead
        #
        # Example: User runs "build weather app" and /homelab/weather-app exists
        # - We create /homelab/weather-app-c4r (honors user's new_project intent)
        # - We log a warning about the existing /homelab/weather-app (safety net)
        existing_repo_path = job.params.get("existing_repo")
        if existing_repo_path:
            # User explicitly specified an existing repo - use that for detection
            detection_path = Path(existing_repo_path)
        else:
            # Check the BASE path (before any random ID we just appended)
            detection_path = Path(base_path_for_detection)

        has_existing_code = detection_path.exists() and any(
            detection_path.iterdir()
        )  # Directory exists and is non-empty

        # Safety warning: If base path exists with code, warn but proceed with new build
        # This preserves the testing workflow while still alerting to potential mistakes
        if mode == "new_project" and has_existing_code and not existing_repo_path:
            logger.warning(
                f"WARNING: Existing project detected at {detection_path}, but mode=new_project. "
                f"Creating new build at {working_dir}. "
                f"If you meant to enhance the existing project, use mode=enhancement or existing_repo={detection_path}"
            )
            self._emit_log(
                job.id,
                "WARNING",
                f"Existing project detected at {detection_path} - creating new build anyway (mode=new_project)",
                None,
            )

        # Auto-switch to enhancement ONLY if user explicitly provided existing_repo
        # This is the legitimate use case: user knows they have an existing repo and wants to enhance it
        if existing_repo_path and has_existing_code and mode == "new_project":
            mode = "enhancement"
            logger.info(
                f"Auto-adjusted mode: new_project → enhancement (existing_repo={existing_repo_path} has code)"
            )
            job.params["mode"] = mode
            self.store.save_job(job)

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

                # Send Discord notification: Build started
                try:
                    project_name = Path(working_dir).name
                    notify_build_started(project=project_name, task=task, job_id=job.id)
                except Exception as e:
                    logger.warning(f"Failed to send Discord start notification: {e}")

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

                    # Send Discord notification: Build succeeded
                    try:
                        project_name = Path(working_dir).name
                        notify_build_complete(
                            project=project_name,
                            status="success",
                            duration_seconds=result.get("duration_seconds", 0),
                            job_id=job.id,
                            phases_completed=result.get("phases_completed", []),
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to send Discord success notification: {e}"
                        )

                    return {
                        "success": True,
                        "exit_code": 0,
                        "phases_completed": result.get("phases_completed", []),
                        "test_iterations": result.get("test_iterations", 0),
                        "duration_seconds": result.get("duration_seconds", 0),
                    }
                elif result.get("status") == "paused":
                    # HITL mode: Build paused after a phase, waiting for approval
                    paused_after = result.get("paused_after", "unknown")
                    self._emit_log(
                        job.id,
                        "INFO",
                        f"Build paused after {paused_after} phase, waiting for approval",
                        paused_after,
                    )
                    logger.info(
                        f"[TRACE] Job {job.id} paused after {paused_after}, returning paused result"
                    )

                    # Return paused status - job stays in running state
                    # The approval system will handle resuming
                    return {
                        "success": True,
                        "paused": True,
                        "paused_after": paused_after,
                        "phases_completed": result.get("phases_completed", []),
                        "phases_remaining": result.get("phases_remaining", []),
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

                    # Cleanup phase prompts to prevent stale UI state
                    self._cleanup_phase_prompts_on_failure(working_dir, error_msg)

                    # Send Discord notification: Build failed
                    try:
                        project_name = Path(working_dir).name
                        notify_build_complete(
                            project=project_name,
                            status="failed",
                            duration_seconds=result.get("duration_seconds", 0),
                            job_id=job.id,
                            error_message=error_msg,
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to send Discord failure notification: {e}"
                        )

                    raise RuntimeError(error_msg)
            else:
                # Standard delegation flow (for DELEGATION, ENHANCEMENT, etc.)
                delegation_result = self._start_delegation(
                    task=task,
                    working_directory=working_dir,
                    timeout_minutes=timeout_minutes,
                    additional_flags=additional_flags,
                    job_id=job.id,
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
        job_id: str,
    ) -> Dict[str, Any]:
        """Start async delegation"""
        result_json = delegate_to_claude_code_async_impl(
            task=task,
            working_directory=working_directory,
            timeout_minutes=timeout_minutes,
            additional_flags=additional_flags,
            active_tasks=self.active_tasks,
        )

        result = json.loads(result_json)
        task_id = result.get("task_id")
        if task_id and task_id in self.active_tasks:
            self.active_tasks[task_id]["job_id"] = job_id

        return result

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

        # Wrap entire polling loop in try/except to catch ANY unhandled exceptions
        try:
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

                    raise RuntimeError(
                        f"Job exceeded timeout of {timeout_minutes} minutes"
                    )

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

        except Exception as e:
            # CRITICAL FIX: Catch ANY unhandled exceptions in polling loop
            logger.critical(
                f"[CRITICAL] Unhandled exception in polling loop for job {job_id}: {e}",
                exc_info=True,
            )
            self._emit_log(
                job_id,
                "ERROR",
                f"Polling loop crashed with unhandled exception: {str(e)}",
                None,
            )
            # Clean up
            self.active_tasks.pop(task_id, None)
            raise  # Re-raise so job manager marks as failed

    def _emit_phase_event(
        self,
        job_id: str,
        phase: str,
        status: str,
        details: Dict[str, Any],
    ):
        """Emit a phase event to Store"""
        try:
            # Enrich details with model info if available in job params or config
            # This is a best-effort attempt for runner-emitted events
            job = self.store.get_job(job_id)
            if job:
                # 1. Try explicit job params first (CLI overrides)
                if job.params:
                    if "model" in job.params and "model" not in details:
                        details["model"] = job.params["model"]
                    if "provider" in job.params and "provider" not in details:
                        details["provider"] = job.params["provider"]
                
                # 2. If still missing, try to resolve from provider_config
                if "model" not in details or "provider" not in details:
                    try:
                        from tools.evolution.framework.provider_config import get_provider_for_phase
                        # Map phase name from event (e.g. "Builder") to config
                        # Note: phase names in events might be "Scout", "Architect", etc.
                        config_provider, config_model = get_provider_for_phase(phase)
                        
                        if "provider" not in details:
                            details["provider"] = config_provider
                        if "model" not in details and config_model:
                            details["model"] = config_model
                    except ImportError:
                        pass # provider_config might not be available in daemon context
                    
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

        Uses background delegation with subprocess tracking for proper timeout enforcement.

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

        from tools.mcp_utils.project_detection import detect_existing_codebase

        # Extract parameters from job
        # NOTE: Mode has already been adjusted in run() method based on codebase detection
        # Support both "task" and "description" parameter names for flexibility
        task = job.params.get("task") or job.params.get("description", "Build project")
        mode = job.params.get("mode", "new_project")
        max_test_iterations = job.params.get("max_test_iterations", 3)
        incremental = job.params.get("incremental", False)
        force_rebuild = job.params.get("force_rebuild", False)
        use_parallel = job.params.get("use_parallel", None)

        # Pause/resume parameters
        pause_after_phases = job.params.get("pause_after_phases", [])
        execution_mode = job.params.get("execution_mode", "autonomous")
        resume_from_phase = job.params.get("resume_from_phase", None)

        # Detect project info at the ACTUAL working directory
        # (which may have random ID appended for new projects)
        working_path = Path(working_dir)
        codebase_info = detect_existing_codebase(working_path)

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

        # Emit phases info
        self._emit_log(
            job.id,
            "INFO",
            f"Build config: mode={mode}, project_type={project_type}, test_loop={enable_test_loop}, parallel={use_parallel}",
            None,
        )

        # Build Python command to run autonomous build in background
        # This enables proper subprocess tracking and timeout enforcement
        build_script = f"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from tools.mcp_utils.autonomous_build import execute_build_with_phase_spawning

result = execute_build_with_phase_spawning(
    task={repr(task)},
    working_directory=Path({repr(str(working_path))}),
    task_config={{
        "task": {repr(task)},
        "working_directory": {repr(working_dir)},
        "github_repo_name": {repr(job.params.get("github_repo_name"))},
        "mode": {repr(mode)},
        "enable_test_loop": {enable_test_loop},
        "max_test_iterations": {max_test_iterations},
        "incremental": {incremental and not force_rebuild},
        "flowise_flow": {flowise_mode},
        "project_type": {repr(project_type)},
        "use_parallel": {use_parallel},
        "codebase_detection": {repr(codebase_info)},
        "pause_after_phases": {repr(pause_after_phases)},
        "execution_mode": {repr(execution_mode)},
        "timeout_minutes": {timeout_minutes},
        "job_id": {repr(str(job.id))},
    }},
    enable_test_loop={enable_test_loop},
    max_test_iterations={max_test_iterations},
    flowise_mode={flowise_mode},
    project_type={repr(project_type)},
    incremental={incremental and not force_rebuild},
    use_parallel={use_parallel},
    timeout_minutes={timeout_minutes},
    resume_from_phase={repr(resume_from_phase)},
)

# Print result as JSON for parent to parse
import json
print("__BUILD_RESULT__")
print(json.dumps(result))
"""

        # Start autonomous build as tracked subprocess
        logger.info(
            f"[TRACE] Starting autonomous build subprocess for job {job.id} at {datetime.now().isoformat()}"
        )

        import tempfile
        import uuid

        task_id = str(uuid.uuid4())

        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(build_script)
            script_path = f.name

        try:
            # Start subprocess in new session to isolate from daemon's process group
            # This prevents signal propagation from child to parent
            process = subprocess.Popen(
                [sys.executable, script_path],
                cwd=str(Path(__file__).parent.parent.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,  # Isolate subprocess from daemon
            )

            # Track in active_tasks for timeout enforcement
            self.active_tasks[task_id] = {
                "process": process,
                "job_id": job.id,
                "start_time": datetime.now(),
                "working_directory": working_dir,
            }

            logger.info(
                f"[TRACE] Autonomous build subprocess started (PID: {process.pid}, task_id: {task_id})"
            )

            # Use existing poll_for_completion with timeout enforcement
            result = self._poll_for_autonomous_build(
                job.id, task_id, working_dir, timeout_minutes, script_path
            )

            logger.info(
                f"[TRACE] Autonomous build completed for job {job.id} at {datetime.now().isoformat()}"
            )

            return result

        finally:
            # Clean up temp script
            try:
                Path(script_path).unlink()
            except (FileNotFoundError, PermissionError):
                pass

    def _poll_for_autonomous_build(
        self,
        job_id: str,
        task_id: str,
        working_dir: str,
        timeout_minutes: float,
        script_path: str,
    ) -> Dict[str, Any]:
        """
        Poll for autonomous build completion with timeout enforcement.

        Similar to _poll_for_completion but parses build result from stdout.

        Args:
            job_id: Job ID
            task_id: Task ID
            working_dir: Working directory
            timeout_minutes: Maximum time to wait
            script_path: Path to temp script (for cleanup)

        Returns:
            Dict with build results
        """
        last_phase = None
        logged_phases = set()  # Track which iteration phases we've already logged
        poll_interval = 5  # seconds

        start_time = datetime.now()
        timeout_seconds = timeout_minutes * 60

        # Wrap entire polling loop in try/except to catch ANY unhandled exceptions
        # This prevents daemon threads from dying silently and leaving jobs stuck
        try:
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
                            logger.warning(
                                f"Killing autonomous build process for job {job_id}"
                            )
                            self._kill_process_tree(
                                process, f"autonomous build for job {job_id}"
                            )

                        # Remove from active tasks
                        del self.active_tasks[task_id]

                    self._emit_log(
                        job_id,
                        "ERROR",
                        f"Build exceeded timeout of {timeout_minutes} minutes and was terminated",
                        None,
                    )

                    return {
                        "status": "failed",
                        "error": f"Build exceeded timeout of {timeout_minutes} minutes",
                        "phases_completed": [],
                        "test_iterations": 0,
                        "duration_seconds": elapsed_seconds,
                    }

                # Check if task is still active
                if task_id not in self.active_tasks:
                    # Task completed or failed
                    break

                task_info = self.active_tasks[task_id]

                # Check phase transitions from current-phase.json (initial phases)
                phase_info = read_phase_info(working_dir, start_time)
                current_phase = phase_info.get("currentPhase")

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

                # ALSO check session-summary.json for iteration phases (visibility fix)
                try:
                    summary_file = (
                        Path(working_dir) / ".context-foundry" / "session-summary.json"
                    )
                    if summary_file.exists():
                        with open(summary_file) as f:
                            summary = json.load(f)

                        # Get all completed phases from summary
                        phases = summary.get("phases", {})
                        for phase_key, phase_data in phases.items():
                            # Check if this is a new phase we haven't logged yet
                            if (
                                phase_data.get("status") == "completed"
                                and phase_key not in logged_phases
                            ):
                                # Emit completed phase event (for Glass Pane visibility)
                                phase_name = (
                                    phase_key.replace("phase_", "")
                                    .replace("_", " ")
                                    .title()
                                )
                                self._emit_log(
                                    job_id,
                                    "INFO",
                                    f"[{phase_name}] Completed ({phase_data.get('duration_seconds', 0):.1f}s)",
                                    phase_name,
                                )
                                logged_phases.add(phase_key)  # Mark as logged
                except Exception as e:
                    # Don't let phase tracking errors kill the polling loop
                    logger.debug(f"Error reading session-summary.json: {e}")

                # Check if process has completed
                process = task_info.get("process")
                if process and process.poll() is not None:
                    # Process finished
                    stdout, stderr = process.communicate(timeout=5)

                    logger.info(
                        f"[TRACE] Autonomous build subprocess exited with code {process.returncode}"
                    )

                    # Parse result from stdout
                    result = self._parse_build_result(
                        stdout, stderr, process.returncode
                    )

                    # Emit final phase event
                    if last_phase:
                        final_status = (
                            "completed"
                            if result.get("status") == "completed"
                            else "failed"
                        )
                        self._emit_phase_event(
                            job_id=job_id,
                            phase=last_phase,
                            status=final_status,
                            details={},
                        )

                    # Clean up task from active_tasks
                    self.active_tasks.pop(task_id, None)

                    return result

                # Sleep before next poll
                time.sleep(poll_interval)

            # If we exited the loop without returning, task was removed unexpectedly
            logger.error(
                f"[TRACE] Autonomous build polling exited unexpectedly for job {job_id}, task {task_id} not in active_tasks"
            )
            return {
                "status": "failed",
                "error": "Build task was unexpectedly terminated or cancelled",
                "phases_completed": [],
                "test_iterations": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }

        except Exception as e:
            # CRITICAL FIX: Catch ANY unhandled exceptions in polling loop
            # This prevents daemon threads from dying silently
            logger.critical(
                f"[CRITICAL] Unhandled exception in autonomous build polling loop for job {job_id}: {e}",
                exc_info=True,
            )
            self._emit_log(
                job_id,
                "ERROR",
                f"Polling loop crashed with unhandled exception: {str(e)}",
                None,
            )
            # Clean up
            self.active_tasks.pop(task_id, None)
            return {
                "status": "failed",
                "error": f"Polling loop crashed: {str(e)}",
                "phases_completed": [],
                "test_iterations": 0,
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
            }

    def _parse_build_result(
        self, stdout: str, stderr: str, exit_code: int
    ) -> Dict[str, Any]:
        """
        Parse build result from subprocess output.

        Looks for __BUILD_RESULT__ marker in stdout and parses JSON.

        Args:
            stdout: Process stdout
            stderr: Process stderr
            exit_code: Process exit code

        Returns:
            Build result dict
        """
        import json

        # Look for result marker in stdout
        if "__BUILD_RESULT__" in stdout:
            try:
                # Split on marker and get everything after it
                result_json = stdout.split("__BUILD_RESULT__")[1].strip()
                result = json.loads(result_json)
                return result
            except (json.JSONDecodeError, IndexError) as e:
                logger.error(f"Failed to parse build result: {e}")
                logger.debug(f"Stdout: {stdout[:1000]}")

        # Fallback: infer from exit code
        if exit_code == 0:
            return {
                "status": "completed",
                "phases_completed": [],
                "test_iterations": 0,
                "duration_seconds": 0,
            }
        else:
            # Try to extract error from stderr
            error_msg = "Build failed"
            if stderr:
                # Get last few lines of stderr
                error_lines = stderr.strip().split("\n")[-10:]
                error_msg = "\n".join(error_lines)

            return {
                "status": "failed",
                "error": error_msg,
                "phases_completed": [],
                "test_iterations": 0,
                "duration_seconds": 0,
            }

    def _cleanup_phase_prompts_on_failure(self, working_dir: str, error_message: str):
        """
        Mark all phase-prompt files as failed when a job fails.

        This prevents stale "processing" state from showing in the dashboard
        after a job fails unexpectedly (e.g., subprocess killed by signal).
        """
        try:
            phase_prompts_dir = Path(working_dir) / ".context-foundry" / "phase-prompts"
            if not phase_prompts_dir.exists():
                return

            import json

            for prompt_file in phase_prompts_dir.glob("*-prompt.json"):
                try:
                    with open(prompt_file) as f:
                        data = json.load(f)

                    current_state = data.get("state", "ready")

                    # Only update if in a non-terminal state
                    if current_state not in ("complete", "failed"):
                        data["state"] = "failed"
                        data["error"] = error_message
                        data["failed_at"] = datetime.now().isoformat()

                        with open(prompt_file, "w") as f:
                            json.dump(data, f, indent=2)

                        logger.info(
                            f"Marked phase prompt {prompt_file.name} as failed (was: {current_state})"
                        )
                except Exception as e:
                    logger.warning(f"Failed to update phase prompt {prompt_file}: {e}")
        except Exception as e:
            logger.warning(f"Failed to cleanup phase prompts: {e}")

    def _merge_patterns(self, job_id: str, working_dir: str):
        """
        Merge learned patterns into global pattern storage.

        This implements self-improvement by extracting learnings from test failures
        and merging them into the global JSON pattern files for git-trackable storage.

        PATTERN ISOLATION MODEL:
        - Extension builds (Flowise, Roblox) DO NOT merge into global storage
        - Only general builds merge into global patterns
        - This prevents cross-contamination
        """
        from datetime import datetime
        import json
        import uuid

        # Track feedback for UI visibility
        feedback_data = {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "phase": "Feedback",
            "state": "complete",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "pattern_merge": {
                "attempted": False,
                "skipped_reason": None,
                "patterns_checked": False,
                "patterns_found": False,
                "patterns_added": 0,
                "patterns_updated": 0,
                "s3_sync": None,
            },
            "summary": [],
        }

        try:
            # Check session configuration for extension mode (PATTERN ISOLATION)
            session_file = (
                Path(working_dir) / ".context-foundry" / "session-summary.json"
            )
            is_extension_build = False
            extension_name = None

            if session_file.exists():
                try:
                    with open(session_file) as f:
                        session = json.load(f)
                        config = session.get("configuration", {})
                        # Check for extension marker or flowise_flow flag
                        extension_name = config.get("extension")
                        is_flowise = config.get("flowise_flow", False)

                        if extension_name or is_flowise:
                            is_extension_build = True
                            extension_name = extension_name or "flowise"
                except Exception as e:
                    logger.warning(
                        f"Failed to parse session config for pattern isolation: {e}"
                    )

            # PATTERN ISOLATION: Skip merge for extension builds
            if is_extension_build:
                self._emit_log(
                    job_id,
                    "INFO",
                    f"Skipping global pattern merge for {extension_name} build (pattern isolation enforced)",
                    None,
                )
                logger.info(
                    f"Pattern isolation: {extension_name} build will not contaminate global patterns"
                )
                feedback_data["pattern_merge"]["skipped_reason"] = (
                    f"Extension build ({extension_name}) - pattern isolation enforced"
                )
                feedback_data["summary"].append(
                    f"⏭️ Skipped: {extension_name} extension build (pattern isolation)"
                )
                self._write_feedback_prompt(working_dir, feedback_data)
                return

            self._emit_log(
                job_id,
                "INFO",
                "Merging learned patterns to global storage (general build)",
                None,
            )
            feedback_data["pattern_merge"]["attempted"] = True
            feedback_data["pattern_merge"]["patterns_checked"] = True

            # Check if project has patterns to merge
            pattern_file = (
                Path(working_dir)
                / ".context-foundry"
                / "patterns"
                / "common-issues.json"
            )

            if not pattern_file.exists():
                logger.info(f"No patterns found for job {job_id}, skipping merge")
                feedback_data["pattern_merge"]["patterns_found"] = False
                feedback_data["pattern_merge"]["skipped_reason"] = (
                    "No project patterns file found (tests passed without failures to learn from)"
                )
                feedback_data["summary"].append(
                    "✅ Build succeeded with no test failures"
                )
                feedback_data["summary"].append(
                    "📝 No new patterns to merge (clean build)"
                )
                self._write_feedback_prompt(working_dir, feedback_data)
                return

            feedback_data["pattern_merge"]["patterns_found"] = True

            # Import pattern management
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))
            from mcp_utils.pattern_management import merge_project_patterns_impl

            # Merge project patterns into global storage (GENERAL BUILDS ONLY)
            merge_result = merge_project_patterns_impl(
                str(pattern_file),
                pattern_type="common-issues",
                increment_build_count=True,
            )

            if merge_result.get("status") == "success":
                added = merge_result.get("patterns_added", 0)
                updated = merge_result.get("patterns_updated", 0)
                feedback_data["pattern_merge"]["patterns_added"] = added
                feedback_data["pattern_merge"]["patterns_updated"] = updated

                self._emit_log(
                    job_id,
                    "INFO",
                    f"Merged patterns to global storage: {added} added, {updated} updated",
                    None,
                )

                if added > 0 or updated > 0:
                    feedback_data["summary"].append(
                        f"🔄 Merged to global: {added} new patterns, {updated} updated"
                    )
                else:
                    feedback_data["summary"].append(
                        "📝 Patterns checked - no new learnings to merge"
                    )

                # Sync to S3 if available
                try:
                    from context_foundry.storage import S3PatternClient

                    client = S3PatternClient()
                    if client.enabled:
                        s3_result = client.upload_pattern("common-issues", force=True)
                        if s3_result.get("success"):
                            s3_uri = s3_result.get("s3_uri", "unknown")
                            self._emit_log(
                                job_id,
                                "INFO",
                                f"Synced patterns to S3: {s3_uri}",
                                None,
                            )
                            feedback_data["pattern_merge"]["s3_sync"] = {
                                "success": True,
                                "uri": s3_uri,
                            }
                            feedback_data["summary"].append(f"☁️ Synced to S3: {s3_uri}")
                        else:
                            error = s3_result.get("error", "Unknown error")
                            self._emit_log(
                                job_id,
                                "WARNING",
                                f"S3 sync failed: {error}",
                                None,
                            )
                            feedback_data["pattern_merge"]["s3_sync"] = {
                                "success": False,
                                "error": error,
                            }
                    else:
                        feedback_data["pattern_merge"]["s3_sync"] = {
                            "success": False,
                            "error": "S3 not configured",
                        }
                except Exception as s3_error:
                    logger.debug(f"S3 sync not available: {s3_error}")
                    feedback_data["pattern_merge"]["s3_sync"] = {
                        "success": False,
                        "error": str(s3_error),
                    }
            else:
                error = merge_result.get("error", "Unknown error")
                self._emit_log(
                    job_id,
                    "WARNING",
                    f"Pattern merge failed: {error}",
                    None,
                )
                feedback_data["summary"].append(f"⚠️ Pattern merge failed: {error}")

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
            feedback_data["summary"].append(f"❌ Error: {str(e)}")

        # Always write feedback prompt for visibility
        feedback_data["completed_at"] = datetime.now().isoformat()
        self._write_feedback_prompt(working_dir, feedback_data)

    def _write_feedback_prompt(self, working_dir: str, feedback_data: dict):
        """Write feedback-prompt.json for UI visibility."""
        import json

        try:
            prompt_dir = Path(working_dir) / ".context-foundry" / "phase-prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)

            prompt_file = prompt_dir / "feedback-prompt.json"
            with open(prompt_file, "w") as f:
                json.dump(feedback_data, f, indent=2)

            logger.info(f"Wrote feedback prompt to {prompt_file}")
        except Exception as e:
            logger.warning(f"Failed to write feedback prompt: {e}")

    def terminate_job_processes(self, job_id: str):
        """
        Force-terminate any tracked subprocess associated with a job.

        Called when a job times out or is cancelled so we do not leave
        rogue claude/runner processes lingering in the background.
        """
        tasks_for_job = [
            (task_id, task_info)
            for task_id, task_info in list(self.active_tasks.items())
            if task_info.get("job_id") == job_id
        ]

        if not tasks_for_job:
            logger.debug(f"No active tasks found for job {job_id} to terminate")
            return

        logger.info(
            f"Terminating {len(tasks_for_job)} active task(s) associated with job {job_id}"
        )

        for task_id, task_info in tasks_for_job:
            process = task_info.get("process")
            if process and process.poll() is None:
                self._kill_process_tree(process, f"job {job_id} task {task_id}")

            self.active_tasks.pop(task_id, None)

    def _kill_process_tree(self, process: subprocess.Popen, description: str):
        """
        Terminate a subprocess and any children to avoid orphans.
        """
        if process.poll() is not None:
            return

        logger.info(f"Terminating subprocess for {description} (PID {process.pid})")

        # Kill child processes first so claude sessions do not linger
        try:
            import psutil

            try:
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    logger.info(
                        f"Terminating child process {child.pid} for {description}"
                    )
                    child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        except ImportError:
            logger.debug("psutil not available, skipping child process termination")
        except Exception as e:
            logger.warning(f"Failed to enumerate child processes: {e}")

        try:
            process.terminate()
            process.wait(timeout=5)
            logger.info(f"{description} terminated gracefully")
        except subprocess.TimeoutExpired:
            logger.warning(
                f"{description} did not terminate after SIGTERM, sending SIGKILL"
            )
            process.kill()
            process.wait(timeout=2)
        except Exception as e:
            logger.error(f"Failed to terminate {description}: {e}")

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
                self._kill_process_tree(process, f"task {task_id}")

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

"""Delegation Mode - Monitor and manage user-initiated builds"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from .base_mode import BaseEvolutionMode, TaskResult
from ..sandboxes import SandboxManager

logger = logging.getLogger(__name__)


class DelegationMode(BaseEvolutionMode):
    """
    Monitor user-initiated delegations from ~/.context-foundry/delegations/

    Unlike self_improvement mode which creates new delegations,
    this mode monitors existing delegations started by users via
    Mission Control TUI or direct MCP calls.
    """

    def __init__(self, config: Dict = None, watchdog=None):
        super().__init__(config)
        self.delegations_dir = Path.home() / ".context-foundry" / "delegations"
        self.watchdog = watchdog  # ProcessWatchdog instance (optional)
        self.mcp_wrapper_path = Path(__file__).parent.parent.parent / "mcp_wrapper.py"

    def _check_and_update_process_status(self, task_id: str, metadata: dict) -> dict:
        """
        Check if build process is still running and update metadata if completed

        Uses PID from metadata to check process status directly.
        If process finished, reads phase info and updates metadata file.

        Args:
            task_id: The delegation task ID
            metadata: Current delegation metadata dict

        Returns:
            Updated metadata dict
        """
        try:
            pid = metadata.get("pid")

            if not pid:
                # No PID means process info wasn't captured
                # Check if build artifacts exist to infer completion
                working_dir = metadata.get("working_directory", "")
                if working_dir:
                    phase_file = (
                        Path(working_dir) / ".context-foundry" / "current-phase.json"
                    )
                    if phase_file.exists():
                        try:
                            phase_info = json.loads(phase_file.read_text())
                            phase_status = phase_info.get("status", "")
                            current_phase = phase_info.get("current_phase", "")

                            # Determine final status based on phase info
                            final_status = None
                            if phase_status == "completed":
                                # Check if Deploy is in completed phases (full success)
                                phases_completed = phase_info.get(
                                    "phases_completed", []
                                )
                                if "Deploy" in phases_completed or current_phase in [
                                    "Deploy",
                                    "Feedback",
                                ]:
                                    # Deploy completed (with or without Feedback phase)
                                    final_status = "completed"
                                else:
                                    # Completed some phase but not Deploy - partial success, mark as failed
                                    final_status = "failed"
                            elif phase_status == "failed":
                                final_status = "failed"
                            else:
                                # Unknown/partial status - mark as failed
                                final_status = "failed"

                            if final_status:
                                # Update metadata
                                metadata["status"] = final_status
                                metadata["end_time"] = datetime.now().isoformat()
                                metadata["current_phase"] = phase_info.get(
                                    "current_phase", "Unknown"
                                )
                                metadata["phase_status"] = phase_status
                                metadata["phases_completed"] = phase_info.get(
                                    "phases_completed", []
                                )
                                metadata["progress_detail"] = phase_info.get(
                                    "progress_detail", ""
                                )

                                # Clear stale error message if marking as completed
                                if final_status == "completed" and "error" in metadata:
                                    del metadata["error"]

                                # Calculate duration
                                start_time_str = metadata.get(
                                    "start_time"
                                ) or metadata.get("started")
                                if start_time_str:
                                    try:
                                        start_time = datetime.fromisoformat(
                                            start_time_str
                                        )
                                        duration = (
                                            datetime.now() - start_time
                                        ).total_seconds()
                                        metadata["duration"] = round(duration, 2)
                                    except:
                                        pass

                                # Write updated metadata
                                task_file = (
                                    self.delegations_dir / f"task-{task_id}.json"
                                )
                                task_file.write_text(json.dumps(metadata, indent=2))
                                logger.info(
                                    f"{'✅' if final_status == 'completed' else '❌'} Delegation {task_id[:8]} marked as {final_status} (no PID, inferred from phase)"
                                )

                                # Cleanup sandbox if this was a sandboxed build
                                sandbox_path = metadata.get("sandbox_path")
                                sandbox_task_id = metadata.get("sandbox_task_id")
                                if sandbox_path and sandbox_task_id:
                                    try:
                                        logger.info(f"🧹 Cleaning up sandbox: {sandbox_path}")
                                        manager = SandboxManager()
                                        manager.cleanup_sandbox(sandbox_task_id)
                                        logger.info(f"✅ Sandbox cleanup complete for task {task_id[:8]}")
                                    except Exception as e:
                                        logger.error(f"❌ Failed to cleanup sandbox for {task_id[:8]}: {e}")

                        except Exception as e:
                            logger.debug(
                                f"Could not read phase info for {task_id[:8]}: {e}"
                            )
                    else:
                        # No phase file - mark as failed
                        metadata["status"] = "failed"
                        metadata["end_time"] = datetime.now().isoformat()
                        metadata["error"] = "Build failed (no PID, no phase file)"

                        task_file = self.delegations_dir / f"task-{task_id}.json"
                        task_file.write_text(json.dumps(metadata, indent=2))
                        logger.warning(
                            f"❌ Delegation {task_id[:8]} marked as failed (no PID, no phase file)"
                        )

                return metadata

            # Check if process is still running using PID
            try:
                # os.kill(pid, 0) doesn't kill, just checks if process exists
                os.kill(pid, 0)
                # Process still running
                logger.debug(
                    f"Process {pid} for delegation {task_id[:8]} is still running"
                )
                return metadata

            except OSError:
                # Process not running - it finished!
                logger.info(f"Process {pid} for delegation {task_id[:8]} has finished")

                # Read phase information to determine success/failure
                working_dir = metadata.get("working_directory", "")
                phase_file = (
                    Path(working_dir) / ".context-foundry" / "current-phase.json"
                )

                final_status = "completed"  # Assume success unless we find otherwise
                phase_data = {}

                if phase_file.exists():
                    try:
                        phase_data = json.loads(phase_file.read_text())
                        phase_status = phase_data.get("status", "")
                        current_phase = phase_data.get("current_phase", "")
                        phases_completed = phase_data.get("phases_completed", [])

                        # Check if Deploy is in completed phases (matches no-PID logic)
                        if phase_status == "completed":
                            if "Deploy" in phases_completed or current_phase in [
                                "Deploy",
                                "Feedback",
                            ]:
                                # Deploy completed (with or without Feedback phase)
                                final_status = "completed"
                            else:
                                # Completed some phase but not Deploy - partial success, mark as failed
                                final_status = "failed"
                        elif phase_status == "failed":
                            final_status = "failed"
                        else:
                            # Unknown/partial status
                            final_status = "failed"

                    except Exception as e:
                        logger.warning(
                            f"Could not read phase info for {task_id[:8]}: {e}"
                        )
                        final_status = "failed"
                else:
                    # No phase file - likely failed early
                    final_status = "failed"

                # Update metadata
                metadata["status"] = final_status
                metadata["end_time"] = datetime.now().isoformat()

                # Clear stale error message if marking as completed
                if final_status == "completed" and "error" in metadata:
                    del metadata["error"]

                # Add phase information if available
                if phase_data:
                    metadata["current_phase"] = phase_data.get(
                        "current_phase", "Unknown"
                    )
                    metadata["phase_status"] = phase_data.get("status", "unknown")
                    metadata["phases_completed"] = phase_data.get(
                        "phases_completed", []
                    )
                    metadata["progress_detail"] = phase_data.get("progress_detail", "")

                # Calculate duration
                start_time_str = metadata.get("start_time") or metadata.get("started")
                if start_time_str:
                    try:
                        start_time = datetime.fromisoformat(start_time_str)
                        duration = (datetime.now() - start_time).total_seconds()
                        metadata["duration"] = round(duration, 2)
                    except:
                        pass

                # Write updated metadata
                task_file = self.delegations_dir / f"task-{task_id}.json"
                task_file.write_text(json.dumps(metadata, indent=2))

                logger.info(f"✅ Delegation {task_id[:8]} marked as {final_status}")

                # Cleanup sandbox if this was a sandboxed build
                sandbox_path = metadata.get("sandbox_path")
                sandbox_task_id = metadata.get("sandbox_task_id")
                if sandbox_path and sandbox_task_id:
                    try:
                        logger.info(f"🧹 Cleaning up sandbox: {sandbox_path}")
                        manager = SandboxManager()
                        manager.cleanup_sandbox(sandbox_task_id)
                        logger.info(f"✅ Sandbox cleanup complete for task {task_id[:8]}")
                    except Exception as e:
                        logger.error(f"❌ Failed to cleanup sandbox for {task_id[:8]}: {e}")

                return metadata

        except Exception as e:
            logger.error(f"Error checking process status for {task_id[:8]}: {e}")
            return metadata

    def generate_tasks(self) -> List[Dict]:
        """
        Scan delegation files and generate monitoring tasks

        This is called by the daemon to discover new delegations
        that aren't yet in the task queue.
        """
        tasks = []

        if not self.delegations_dir.exists():
            return tasks

        for task_file in self.delegations_dir.glob("task-*.json"):
            try:
                metadata = json.loads(task_file.read_text())
                task_id = metadata.get("task_id")
                status = metadata.get("status")

                # Only create tasks for running delegations
                # (pending delegations haven't started yet)
                if status in ["running", "pending"]:
                    working_dir = metadata.get("working_directory", "")
                    project = metadata.get("github_repo_name") or metadata.get(
                        "project", ""
                    )

                    if not project:
                        project = Path(working_dir).name if working_dir else "unknown"

                    tasks.append(
                        {
                            "type": "delegation_build",
                            "params": {
                                "mcp_task_id": task_id,
                                "project": project,
                                "working_directory": working_dir,
                                "started": metadata.get("started")
                                or metadata.get("start_time"),
                                "user_initiated": True,
                            },
                            "priority": 7,  # Higher priority than evolution tasks
                        }
                    )
            except Exception:
                continue

        return tasks

    def execute_task(self, task) -> TaskResult:
        """
        Monitor a delegation and update its status

        This doesn't execute anything - the delegation is already running.
        We just monitor it and keep the task queue in sync.
        """
        try:
            params = task.params
            mcp_task_id = params.get("mcp_task_id")

            if not mcp_task_id:
                return TaskResult(
                    success=False, output=None, error="No mcp_task_id in task params"
                )

            # Read delegation metadata
            task_file = self.delegations_dir / f"task-{mcp_task_id}.json"

            if not task_file.exists():
                return TaskResult(
                    success=False,
                    output=None,
                    error=f"Delegation file not found: {task_file}",
                )

            # Read current metadata
            metadata = json.loads(task_file.read_text())

            # CRITICAL FIX: Check if process finished and update status
            # This uses PID to check process status directly
            metadata = self._check_and_update_process_status(mcp_task_id, metadata)
            status = metadata.get("status", "unknown")

            # Check if delegation completed
            if status in ["completed", "failed", "cancelled", "timeout"]:
                # Unregister from watchdog if we were monitoring
                pid = metadata.get("pid")
                if pid and self.watchdog:
                    self.watchdog.unregister_process(pid)
                    logger.info(f"Unregistered delegation PID {pid} from watchdog")

                # Delegation finished
                return TaskResult(
                    success=(status == "completed"),
                    output={
                        "status": status,
                        "mcp_task_id": mcp_task_id,
                        "project": params.get("project"),
                        "working_directory": params.get("working_directory"),
                        "duration": metadata.get("duration"),
                        "exit_code": metadata.get("exit_code"),
                    },
                    error=None if status == "completed" else f"Build {status}",
                )

            # Still running - register with watchdog if we have PID
            pid = metadata.get("pid")
            if pid and self.watchdog:
                # Check if already registered
                if pid not in self.watchdog.processes:
                    # Determine log file path
                    working_dir = params.get("working_directory", "")
                    log_file = str(
                        Path(working_dir) / ".context-foundry" / "build-output.txt"
                    )

                    self.watchdog.register_process(
                        pid=pid, task_id=mcp_task_id, log_file=log_file
                    )
                    logger.info(
                        f"Registered delegation PID {pid} with watchdog (task: {mcp_task_id[:8]})"
                    )

            return TaskResult(
                success=True,
                output={
                    "status": "running",
                    "mcp_task_id": mcp_task_id,
                    "project": params.get("project"),
                    "current_phase": metadata.get("current_phase"),
                    "phase_status": metadata.get("phase_status"),
                    "pid": pid,
                },
            )

        except Exception as e:
            return TaskResult(
                success=False,
                output=None,
                error=f"Error monitoring delegation: {str(e)}",
            )

    def validate_result(self, result: TaskResult) -> bool:
        """
        Validate delegation monitoring result

        For delegations, we consider it valid if:
        - Status was successfully retrieved
        - If completed, exit_code is 0
        - If running, we have progress info
        """
        if not result.success:
            return False

        if not result.output:
            return False

        status = result.output.get("status")

        # Running is valid (still in progress)
        if status == "running":
            return True

        # Completed is valid if exit_code is 0
        if status == "completed":
            exit_code = result.output.get("exit_code", -1)
            return exit_code == 0

        # Failed/cancelled/timeout are invalid
        return False

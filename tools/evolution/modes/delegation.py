"""Delegation Mode - Monitor and manage user-initiated builds"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base_mode import BaseEvolutionMode, TaskResult

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
                    project = metadata.get("github_repo_name") or metadata.get("project", "")

                    if not project:
                        project = Path(working_dir).name if working_dir else "unknown"

                    tasks.append({
                        "type": "delegation_build",
                        "params": {
                            "mcp_task_id": task_id,
                            "project": project,
                            "working_directory": working_dir,
                            "started": metadata.get("started") or metadata.get("start_time"),
                            "user_initiated": True
                        },
                        "priority": 7  # Higher priority than evolution tasks
                    })
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
                    success=False,
                    output=None,
                    error="No mcp_task_id in task params"
                )

            # Read delegation metadata
            task_file = self.delegations_dir / f"task-{mcp_task_id}.json"

            if not task_file.exists():
                return TaskResult(
                    success=False,
                    output=None,
                    error=f"Delegation file not found: {task_file}"
                )

            metadata = json.loads(task_file.read_text())
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
                        "exit_code": metadata.get("exit_code")
                    },
                    error=None if status == "completed" else f"Build {status}"
                )

            # Still running - register with watchdog if we have PID
            pid = metadata.get("pid")
            if pid and self.watchdog:
                # Check if already registered
                if pid not in self.watchdog.processes:
                    # Determine log file path
                    working_dir = params.get("working_directory", "")
                    log_file = str(Path(working_dir) / ".context-foundry" / "build-output.txt")

                    self.watchdog.register_process(
                        pid=pid,
                        task_id=mcp_task_id,
                        log_file=log_file
                    )
                    logger.info(f"Registered delegation PID {pid} with watchdog (task: {mcp_task_id[:8]})")

            return TaskResult(
                success=True,
                output={
                    "status": "running",
                    "mcp_task_id": mcp_task_id,
                    "project": params.get("project"),
                    "current_phase": metadata.get("current_phase"),
                    "phase_status": metadata.get("phase_status"),
                    "pid": pid
                }
            )

        except Exception as e:
            return TaskResult(
                success=False,
                output=None,
                error=f"Error monitoring delegation: {str(e)}"
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

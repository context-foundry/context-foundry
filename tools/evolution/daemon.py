#!/usr/bin/env python3
"""
Evolution Daemon for CFES
Main service orchestrator running continuously
"""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .task_queue import TaskQueueManager, Task, TaskStatus, TaskType
from .resource_manager import ResourceManager
from .process_watchdog import ProcessWatchdog
from .modes.self_improvement import SelfImprovementMode
from .modes.chaos_creative import ChaosCreativeMode
from .modes.research_discovery import ResearchDiscoveryMode
from .modes.delegation import DelegationMode
from .backlog_generator import BacklogGenerator
from .mcp_support import get_mcp_capabilities


# Setup logging
def setup_logging(log_dir: Path):
    """Setup rotating file logging"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"

    # Set up rotating file handler (10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Console handler for stdout/stderr
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Configure root logger
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

    return logging.getLogger(__name__)


class EvolutionDaemon:
    """Main daemon service orchestrator"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize daemon

        Args:
            config_path: Path to config file
        """
        # Load configuration
        self.config = self._load_config(config_path)

        # Setup logging
        log_dir = Path.home() / ".context-foundry" / "evolution" / "logs"
        self.logger = setup_logging(log_dir)

        # Detect MCP capability (FastMCP + Python 3.10)
        mcp_status = get_mcp_capabilities()
        self.mcp_available = mcp_status["available"]
        self.mcp_unavailable_reason = mcp_status.get("reason", "")
        self.last_mcp_warning = 0.0
        if not self.mcp_available:
            self.logger.warning(
                "MCP-dependent tasks disabled: %s",
                self.mcp_unavailable_reason or "dependency check failed",
            )
            self.logger.info(
                "Upgrade to Python 3.10+ and run `pip install -r requirements-mcp.txt` to re-enable MCP tasks."
            )

        # Initialize components
        self.task_queue = TaskQueueManager()
        self.resource_manager = ResourceManager(self.config.get("resources", {}))
        self.watchdog = ProcessWatchdog(
            max_duration_minutes=60,
            max_tokens_per_task=100_000,
            check_interval_seconds=30,
        )

        # Initialize backlog generator
        cf_root = Path(__file__).parent.parent.parent
        self.backlog_generator = BacklogGenerator(
            project_root=cf_root, target_backlog_size=5
        )

        # Initialize evolution modes (pass watchdog to delegation modes)
        self.modes = {
            TaskType.SELF_IMPROVEMENT.value: SelfImprovementMode(),
            TaskType.CHAOS_CREATIVE.value: ChaosCreativeMode(),
            TaskType.RESEARCH.value: ResearchDiscoveryMode(),
            TaskType.DELEGATION_BUILD.value: DelegationMode(watchdog=self.watchdog),
            TaskType.DELEGATION_DEPLOY.value: DelegationMode(watchdog=self.watchdog),
            TaskType.DELEGATION_TEST.value: DelegationMode(watchdog=self.watchdog),
        }

        # State
        self.running = False
        self.stop_requested = False
        self.active_tasks = {}
        self.poll_count = 0  # Track polling iterations for periodic logging
        self.pid = None
        self.was_paused_for_pr = False  # Track if we were paused for PR review
        self.last_watchdog_check = time.time()  # Track last watchdog check time
        self.last_backlog_check = 0  # Track last backlog maintenance time

        # PID file path
        self.pid_file = Path.home() / ".context-foundry" / "evolution" / "daemon.pid"

    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from file"""
        if config_path is None:
            config_path = Path.home() / ".context-foundry" / "evolution" / "config.json"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            # Return default config
            return {
                "daemon": {
                    "enabled": True,
                    "poll_interval_seconds": 60,
                    "max_concurrent_tasks": 1,
                    "log_level": "INFO",
                    "github_issues_only": False,  # If True, only work on approved GitHub issues
                },
                "modes": {
                    "self_improvement": {"enabled": True, "priority": 8},
                    "chaos_creative": {"enabled": True, "priority": 5},
                    "research_discovery": {"enabled": False, "priority": 9},
                },
                "resources": {
                    "max_cpu_percent": 80,
                    "max_memory_gb": 16,
                    "active_hours": [6, 22],
                },
            }

        with open(config_path) as f:
            return json.load(f)

    def _write_pid(self):
        """Write PID to file"""
        self.pid = os.getpid()
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, "w") as f:
            f.write(str(self.pid))

    def _remove_pid(self):
        """Remove PID file"""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def get_pid(self) -> Optional[int]:
        """Get daemon PID from file"""
        if self.pid_file.exists():
            with open(self.pid_file) as f:
                return int(f.read().strip())
        return None

    def is_running(self) -> bool:
        """Check if daemon is running"""
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            # Check if process exists
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigint)
        try:
            signal.signal(signal.SIGHUP, self._handle_sighup)
        except AttributeError:
            # SIGHUP not available on Windows
            pass

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM signal"""
        self.logger.info("Received SIGTERM, initiating graceful shutdown...")
        self.stop_requested = True

    def _handle_sigint(self, signum, frame):
        """Handle SIGINT (Ctrl+C)"""
        self.logger.info("Received SIGINT, initiating graceful shutdown...")
        self.stop_requested = True

    def _handle_sighup(self, signum, frame):
        """Handle SIGHUP - reload configuration"""
        self.logger.info("Received SIGHUP, reloading configuration...")
        self.config = self._load_config(None)
        self.resource_manager = ResourceManager(self.config.get("resources", {}))
        status = get_mcp_capabilities(force_refresh=True)
        self.mcp_available = status["available"]
        self.mcp_unavailable_reason = status.get("reason", "")
        if self.mcp_available:
            self.logger.info(
                "MCP dependencies detected; self-improvement tasks are enabled."
            )
        else:
            self.logger.warning(
                "MCP dependencies still unavailable after reload: %s",
                self.mcp_unavailable_reason or "unknown reason",
            )

    def _maybe_log_mcp_disabled(self, context: str):
        """
        Throttled warning helper so we don't spam logs when MCP is unavailable.
        """
        if self.mcp_available:
            return

        now = time.time()
        if now - self.last_mcp_warning < 300:
            return

        self.last_mcp_warning = now
        prefix = f"{context.strip()} - " if context else ""
        reason = self.mcp_unavailable_reason or "see install docs"
        self.logger.warning("%sMCP features unavailable: %s", prefix, reason)
        self.logger.info(
            "Install MCP deps with Python 3.10+ and `pip install -r requirements-mcp.txt`, or keep backlog-only mode."
        )

    def _cleanup_stuck_tasks(self):
        """
        Cleanup any tasks stuck in RUNNING state from previous daemon crash

        This is called on daemon startup to ensure no stuck tasks block the queue.
        Tasks can get stuck in RUNNING state if:
        - Daemon crashed while task was executing
        - Process was killed without cleanup
        - System reboot
        """
        running_tasks = self.task_queue.list_tasks(
            status=TaskStatus.RUNNING.value, limit=100
        )

        if running_tasks:
            self.logger.warning(
                f"Found {len(running_tasks)} stuck RUNNING tasks from previous session - cancelling them"
            )

            for task in running_tasks:
                self.logger.info(
                    f"  Cancelling stuck task: {task.id[:8]} ({task.type}) - started {task.started_at}"
                )
                self.task_queue.update_task_status(
                    task.id,
                    TaskStatus.CANCELLED.value,
                    error="Task was stuck in RUNNING state when daemon restarted",
                )
        else:
            self.logger.debug("No stuck RUNNING tasks found")

    def _recover_delegations(self):
        """
        Recover orphaned delegations on daemon startup

        Scans delegation files and creates monitoring tasks for any
        delegations that are still marked as "running" but don't have
        active monitoring tasks in the queue.
        """
        try:
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            if not delegations_dir.exists():
                return

            recovered_count = 0

            for task_file in delegations_dir.glob("task-*.json"):
                try:
                    metadata = json.loads(task_file.read_text())
                    task_id = metadata.get("task_id")
                    status = metadata.get("status")
                    pid = metadata.get("pid")

                    # Only recover running delegations
                    if status != "running":
                        continue

                    # Check if process is actually still running
                    if pid:
                        try:
                            import psutil

                            psutil.Process(pid)
                            # Process exists - check if we're monitoring it
                            existing_tasks = self.task_queue.list_tasks(
                                status=TaskStatus.PENDING.value
                            )
                            existing_tasks += self.task_queue.list_tasks(
                                status=TaskStatus.RUNNING.value
                            )

                            already_monitoring = any(
                                t.params.get("mcp_task_id") == task_id
                                for t in existing_tasks
                            )

                            if not already_monitoring:
                                # Create monitoring task
                                working_dir = metadata.get("working_directory", "")
                                project = metadata.get(
                                    "github_repo_name"
                                ) or metadata.get("project", "")

                                if not project:
                                    project = (
                                        Path(working_dir).name
                                        if working_dir
                                        else "unknown"
                                    )

                                self.task_queue.create_task(
                                    task_type=TaskType.DELEGATION_BUILD.value,
                                    params={
                                        "mcp_task_id": task_id,
                                        "project": project,
                                        "working_directory": working_dir,
                                        "started": metadata.get("started")
                                        or metadata.get("start_time"),
                                        "user_initiated": True,
                                        "recovered": True,
                                    },
                                    priority=7,
                                )

                                recovered_count += 1
                                self.logger.info(
                                    f"Recovered orphaned delegation: {project} ({task_id[:8]}, PID: {pid})"
                                )

                        except psutil.NoSuchProcess:
                            # Process is dead - update delegation metadata
                            metadata["status"] = "failed"
                            metadata["error"] = (
                                "Process died (recovered on daemon startup)"
                            )
                            task_file.write_text(json.dumps(metadata, indent=2))
                            self.logger.warning(
                                f"Delegation {task_id[:8]} marked as failed (process not running)"
                            )

                            # Cleanup sandbox if this was a sandboxed build
                            sandbox_path = metadata.get("sandbox_path")
                            if sandbox_path:
                                try:
                                    from .sandboxes import SandboxManager

                                    self.logger.info(
                                        f"🧹 Cleaning up sandbox: {sandbox_path}"
                                    )
                                    manager = SandboxManager()
                                    manager.cleanup_sandbox(
                                        sandbox_path=Path(sandbox_path)
                                    )
                                    self.logger.info(
                                        f"✅ Sandbox cleanup complete for task {task_id[:8]}"
                                    )
                                except Exception as e:
                                    self.logger.error(
                                        f"❌ Failed to cleanup sandbox for {task_id[:8]}: {e}"
                                    )
                    else:
                        # No PID recorded - check if build actually completed by reading phase file
                        working_dir = metadata.get("working_directory", "")
                        phase_file = (
                            Path(working_dir)
                            / ".context-foundry"
                            / "current-phase.json"
                        )

                        if phase_file.exists():
                            try:
                                phase_info = json.loads(phase_file.read_text())
                                phase_status = phase_info.get("status", "")
                                current_phase = phase_info.get("current_phase", "")

                                # Check if Deploy is in completed phases
                                phases_completed = phase_info.get(
                                    "phases_completed", []
                                )
                                if phase_status == "completed" and (
                                    "Deploy" in phases_completed
                                    or current_phase in ["Deploy", "Feedback"]
                                ):
                                    # Build completed successfully!
                                    metadata["status"] = "completed"
                                    metadata["end_time"] = datetime.now().isoformat()
                                    metadata["current_phase"] = (
                                        current_phase  # Preserve actual phase (Deploy or Feedback)
                                    )
                                    metadata["phase_status"] = "completed"
                                    metadata["phases_completed"] = phase_info.get(
                                        "phases_completed", []
                                    )
                                    metadata["progress_detail"] = phase_info.get(
                                        "progress_detail", ""
                                    )

                                    # Clear stale error message when marking as completed
                                    if "error" in metadata:
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
                                        except (ValueError, TypeError):
                                            pass

                                    task_file.write_text(json.dumps(metadata, indent=2))
                                    self.logger.info(
                                        f"✅ Delegation {task_id[:8]} recovered as completed (inferred from phase)"
                                    )
                                else:
                                    # Build did not complete successfully
                                    metadata["status"] = "failed"
                                    metadata["error"] = (
                                        "Build incomplete (no PID recorded, phase not completed)"
                                    )
                                    task_file.write_text(json.dumps(metadata, indent=2))
                                    self.logger.warning(
                                        f"Delegation {task_id[:8]} marked as failed (incomplete)"
                                    )
                            except Exception:
                                # Could not read phase file
                                metadata["status"] = "failed"
                                metadata["error"] = (
                                    "Orphaned delegation (no PID recorded, could not verify completion)"
                                )
                                task_file.write_text(json.dumps(metadata, indent=2))
                                self.logger.warning(
                                    f"Delegation {task_id[:8]} marked as failed (no PID, phase unreadable)"
                                )
                        else:
                            # No phase file - mark as failed (orphaned)
                            metadata["status"] = "failed"
                            metadata["error"] = (
                                "Orphaned delegation (no PID recorded, no phase file)"
                            )
                            task_file.write_text(json.dumps(metadata, indent=2))
                            self.logger.warning(
                                f"Delegation {task_id[:8]} marked as failed (no PID, no phase file)"
                            )

                except Exception as e:
                    self.logger.warning(
                        f"Error recovering delegation from {task_file.name}: {e}"
                    )
                    continue

            if recovered_count > 0:
                self.logger.info(
                    f"Build recovery complete: {recovered_count} delegation(s) recovered"
                )

        except Exception as e:
            self.logger.error(f"Error during delegation recovery: {e}", exc_info=True)

    def start(self, daemonize: bool = False):
        """
        Start daemon

        Args:
            daemonize: If True, fork and run in background
        """
        if self.is_running():
            self.logger.error("Daemon is already running")
            return False

        self._write_pid()
        self.setup_signal_handlers()

        # Clean up any stuck tasks from previous crashes
        self._cleanup_stuck_tasks()

        # Recover any orphaned delegations
        self._recover_delegations()

        self.logger.info(f"Starting Evolution Daemon (PID: {self.pid})")
        self.running = True

        try:
            self.main_loop()
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        finally:
            self.cleanup()

        return True

    def _check_watchdog(self):
        """
        Check watchdog for stuck/timeout processes and handle actions

        Actions can include:
        - killed_timeout: Process exceeded max duration (60 min)
        - killed_stuck: Process has no log activity (10+ min)
        - process_died: Process terminated unexpectedly
        - warning_tokens: Process exceeding token budget
        """
        actions = self.watchdog.check_processes()

        for action in actions:
            action_type = action.get("action")
            task_id = action.get("task_id")
            pid = action.get("pid")

            if action_type in ["killed_timeout", "killed_stuck"]:
                # Process was killed by watchdog - mark task as failed
                reason = (
                    "timeout"
                    if action_type == "killed_timeout"
                    else "stuck (no log activity)"
                )
                duration = action.get("duration_minutes", 0)

                self.logger.error(
                    f"⚠️  Watchdog killed process {pid} (task {task_id[:8]}) - {reason} after {duration:.1f} min"
                )

                # Update task status to FAILED
                self.task_queue.update_task_status(
                    task_id,
                    TaskStatus.FAILED.value,
                    error=f"Process killed by watchdog: {reason} ({duration:.1f} min)",
                )

            elif action_type == "process_died":
                # Process terminated unexpectedly
                duration = action.get("duration_minutes", 0)
                self.logger.warning(
                    f"Process {pid} (task {task_id[:8]}) died unexpectedly after {duration:.1f} min"
                )
                # Don't update task status - let PR detection handle it (might have succeeded)

            elif action_type == "warning_tokens":
                # Process using lots of tokens
                estimated = action.get("estimated_tokens", 0)
                self.logger.warning(
                    f"⚠️  Process {pid} (task {task_id[:8]}) estimated {estimated} tokens (high usage)"
                )

    def _interruptible_sleep(self, seconds: int):
        """
        Sleep for specified seconds, but check stop_requested every second
        This makes Ctrl+C responsive instead of blocking for full duration
        """
        for _ in range(seconds):
            if self.stop_requested:
                break
            time.sleep(1)

    def main_loop(self):
        """Main daemon loop - polls queue every 60 seconds"""
        poll_interval = self.config.get("daemon", {}).get("poll_interval_seconds", 60)
        max_concurrent = self.config.get("daemon", {}).get("max_concurrent_tasks", 3)

        # Log polling loop initialization
        self.logger.info(
            f"Entering main polling loop (interval: {poll_interval}s, max_concurrent: {max_concurrent})"
        )

        while not self.stop_requested:
            try:
                # Check watchdog for stuck/timeout processes (every 30 seconds)
                current_time = time.time()
                if current_time - self.last_watchdog_check >= 30:
                    self._check_watchdog()
                    self.last_watchdog_check = current_time

                # BACKLOG MAINTENANCE: Run Scout and create GitHub issues (every 5 minutes)
                # Uses lightweight Scout + Claude CLI (no MCP needed)
                self._maintain_backlog()

                # SANDBOX CLEANUP: Remove orphaned sandboxes (hourly)
                self._cleanup_orphaned_sandboxes()

                # HUMAN-IN-THE-LOOP: Check for open PRs FIRST
                open_prs = self._check_open_prs()

                if open_prs:
                    pr_numbers = [pr["number"] for pr in open_prs]
                    self.logger.info(
                        f"⏸️  PAUSED: Waiting for PR(s) {pr_numbers} to be merged. "
                        f"System will resume when PRs are closed."
                    )
                    self.was_paused_for_pr = True
                    self._interruptible_sleep(poll_interval)
                    continue  # Skip everything - don't pick up tasks!

                # PRs are now closed! Queue next task if we were paused
                if self.was_paused_for_pr:
                    self.logger.info("✅ PRs merged! Queuing next improvement task...")
                    self._queue_next_improvement_task()
                    self.was_paused_for_pr = False

                # GITHUB ISSUE POLLING: Check for new approved issues every cycle
                # This ensures human-approved tasks get added to queue proactively
                self._poll_github_issues()

                # Check resources
                can_accept, resource_status = self.resource_manager.can_accept_task()

                if not can_accept:
                    self.logger.debug(f"Cannot accept tasks: {resource_status}")
                    self._interruptible_sleep(poll_interval)
                    continue

                # Check if we can accept more tasks
                if len(self.active_tasks) >= max_concurrent:
                    self.logger.debug(
                        f"Max concurrent tasks reached ({max_concurrent})"
                    )
                    self._interruptible_sleep(poll_interval)
                    continue

                # MCP STATUS MONITORING: Check progress of MCP delegations
                self._check_mcp_status()

                # DELEGATION MONITORING: Poll delegation files and create monitoring tasks
                self._poll_delegations()

                # RACE CONDITION FIX: Detect PRs created by Claude and mark tasks as COMPLETED
                # This allows daemon to pick up next task after PR is created
                self._detect_prs_and_complete_tasks()

                # STUCK TASK PROTECTION: Mark tasks as FAILED if running > 2 hours with no PR
                self._check_stuck_running_tasks()

                # Log queue status before checking for tasks
                pending_count = self.task_queue.count_pending()
                running_count = self.task_queue.count_running()
                self.logger.info(
                    f"Queue status: {pending_count} pending, {running_count} running, {len(self.active_tasks)}/{max_concurrent} active"
                )

                # RACE CONDITION FIX: Don't pick up new tasks if there are RUNNING tasks
                # Running tasks are being executed by background Claude processes
                # We must wait for them to complete (PR created) before starting new ones
                #
                # EXCEPTION: Allow delegation monitoring tasks (delegation_build, delegation_deploy,
                # delegation_test) to run concurrently since they just monitor and cleanup
                delegation_task = None
                if running_count > 0:
                    # When there are RUNNING tasks, only pick up delegation monitoring tasks
                    # These are lightweight tasks that just monitor process status and cleanup
                    pending_tasks = self.task_queue.list_tasks(
                        status=TaskStatus.PENDING.value
                    )
                    delegation_tasks = [
                        t
                        for t in pending_tasks
                        if t.type
                        in [
                            TaskType.DELEGATION_BUILD.value,
                            TaskType.DELEGATION_DEPLOY.value,
                            TaskType.DELEGATION_TEST.value,
                        ]
                    ]

                    if not delegation_tasks:
                        # No delegation tasks - wait for running tasks to complete
                        self.logger.info(
                            f"⏸️  Waiting for {running_count} running task(s) to complete before picking up new work"
                        )
                        self._interruptible_sleep(poll_interval)
                        continue
                    else:
                        # Pick the highest priority delegation task
                        delegation_task = max(
                            delegation_tasks, key=lambda t: t.priority
                        )
                        self.logger.info(
                            f"📋 Picking up delegation task {delegation_task.id} (type: {delegation_task.type}) "
                            f"despite {running_count} running task(s)"
                        )
                        # Mark it as running
                        self.task_queue.update_task_status(
                            delegation_task.id, TaskStatus.RUNNING.value
                        )
                        task = delegation_task
                else:
                    # No running tasks - pick up next task normally
                    task = self.task_queue.get_next_task()

                if task:
                    # Only log if it wasn't already logged above (for delegation tasks)
                    if not delegation_task:
                        self.logger.info(
                            f"Picked up task: {task.id} (type: {task.type})"
                        )
                    self._execute_task(task)
                else:
                    # Queue is empty - generate a new improvement task to keep the loop going
                    self.logger.info(
                        "No pending tasks in queue - generating new improvement task..."
                    )
                    self._queue_next_improvement_task()

                # Sleep before next poll (interruptible for responsive shutdown)
                self._interruptible_sleep(poll_interval)

                # Periodic resource usage logging (every 10 iterations)
                self.poll_count += 1
                if self.poll_count % 10 == 0:
                    usage = self.resource_manager.get_resource_usage()
                    self.logger.info(
                        f"Resource usage [poll #{self.poll_count}] - "
                        f"CPU: {usage['cpu_percent']:.1f}%, "
                        f"Memory: {usage['memory_gb']:.1f}GB ({usage['memory_percent']:.1f}%), "
                        f"Disk: {usage['disk_percent']:.1f}%"
                    )

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                self._interruptible_sleep(poll_interval)

    def _execute_task(self, task: Task):
        """
        Execute task by delegating to appropriate mode

        Args:
            task: Task to execute
        """
        try:
            self.logger.info(f"Executing task {task.id} of type {task.type}")

            # Track active task
            self.active_tasks[task.id] = task

            # Get the appropriate mode for this task type
            mode = self.modes.get(task.type)
            if not mode:
                raise ValueError(f"Unknown task type: {task.type}")

            if task.type == TaskType.SELF_IMPROVEMENT.value and not self.mcp_available:
                message = (
                    f"Skipping self-improvement task {task.id}: "
                    f"MCP unavailable ({self.mcp_unavailable_reason or 'missing dependencies'})"
                )
                self._maybe_log_mcp_disabled("Self-improvement task skipped")
                self.logger.warning(message)
                self.task_queue.update_task_status(
                    task.id, TaskStatus.CANCELLED.value, error=message
                )
                return

            # Execute task via mode
            self.logger.info(f"Delegating to {task.type} mode")
            task_result = mode.execute_task(task)

            # Validate result
            if mode.validate_result(task_result):
                result = {
                    "status": "success",
                    "message": f"Task {task.type} executed successfully",
                    "output": task_result.output,
                }

                # RACE CONDITION FIX: For self_improvement tasks that spawn Claude or MCP,
                # keep them in RUNNING state until PR is created (don't mark COMPLETED)
                # This prevents daemon from picking up another task before PR is created
                task_status = result.get("output", {}).get("status")
                if task.type == "self_improvement" and task_status in [
                    "claude_spawned",
                    "mcp_running",
                ]:
                    if task_status == "mcp_running":
                        mcp_task_id = result["output"].get("mcp_task_id")
                        self.logger.info(
                            f"✅ Task {task.id} delegated to Context Foundry MCP - keeping in RUNNING state until PR detected"
                        )
                        self.logger.info(f"   MCP Task ID: {mcp_task_id}")
                        self.logger.info(
                            f"   Monitor: get_delegation_result('{mcp_task_id}')"
                        )
                        # Store MCP task_id in task result for monitoring
                        self.task_queue.update_task_status(
                            task.id,
                            TaskStatus.RUNNING.value,
                            result={
                                "mcp_task_id": mcp_task_id,
                                "branch": result["output"].get("branch"),
                            },
                        )
                    else:
                        self.logger.info(
                            f"✅ Task {task.id} delegated to Claude CLI - keeping in RUNNING state until PR detected"
                        )
                        self.logger.info(f"   PID: {result['output'].get('pid')}")
                        self.logger.info(f"   Log: {result['output'].get('log_file')}")
                    # Task stays in RUNNING state - will be marked COMPLETED when PR is detected
                else:
                    # For non-delegated tasks, mark as completed immediately
                    self.task_queue.update_task_status(
                        task.id, TaskStatus.COMPLETED.value, result=result
                    )
                    self.logger.info(f"Task {task.id} completed successfully")
            else:
                raise ValueError(f"Task validation failed: {task_result.error}")

        except Exception as e:
            self.logger.error(f"Task {task.id} failed: {e}", exc_info=True)

            # Check if should retry
            if self.task_queue.should_retry(task):
                self.task_queue.retry_task(task.id)
                self.logger.info(
                    f"Task {task.id} will be retried (attempt {task.retry_count + 1}/{task.max_retries})"
                )
            else:
                self.task_queue.update_task_status(
                    task.id, TaskStatus.FAILED.value, error=str(e)
                )

        finally:
            # Remove from active tasks
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]

    def stop(self, graceful: bool = True):
        """
        Stop daemon

        Args:
            graceful: If True, wait for active tasks to complete
        """
        self.logger.info(f"Stopping daemon (graceful={graceful})")

        if graceful:
            # Wait for active tasks
            while self.active_tasks:
                self.logger.info(
                    f"Waiting for {len(self.active_tasks)} active tasks to complete..."
                )
                time.sleep(5)

        self.stop_requested = True
        self.running = False

    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up daemon resources")

        # Close database
        self.task_queue.close()

        # Remove PID file
        self._remove_pid()

        self.logger.info("Daemon stopped")

    def get_uptime(self) -> float:
        """Get daemon uptime in seconds"""
        # Simplified - would track start time
        return 0.0

    def _check_open_prs(self):
        """
        Check for open PRs in the context-foundry repo

        Returns list of open PRs created by the Evolution System
        """
        try:
            # Get git remote to determine GitHub repo
            cf_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=str(cf_root),
                timeout=5,
            )

            if result.returncode != 0:
                self.logger.warning("Could not get git remote URL")
                return []

            remote_url = result.stdout.strip()

            # Parse GitHub owner/repo from remote URL
            # Handle both HTTPS and SSH formats
            if "github.com" in remote_url:
                if remote_url.startswith("git@github.com:"):
                    # SSH format: git@github.com:owner/repo.git
                    repo_path = remote_url.replace("git@github.com:", "").replace(
                        ".git", ""
                    )
                elif "https://github.com/" in remote_url:
                    # HTTPS format: https://github.com/owner/repo.git
                    repo_path = remote_url.replace("https://github.com/", "").replace(
                        ".git", ""
                    )
                else:
                    self.logger.warning(f"Unrecognized GitHub URL format: {remote_url}")
                    return []

                owner, repo = repo_path.split("/")
            else:
                self.logger.warning("Not a GitHub repository")
                return []

            # Call GitHub API to get open PRs
            api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            params = {"state": "open"}

            try:
                import requests

                # Try to get GitHub token for authentication (avoids rate limiting)
                # Priority: environment variable > gh CLI > config file
                github_token = os.environ.get("GITHUB_TOKEN")

                if not github_token:
                    # Try to get token from gh CLI (likely already authenticated)
                    try:
                        result = subprocess.run(
                            ["gh", "auth", "token"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if result.returncode == 0:
                            github_token = result.stdout.strip()
                            self.logger.debug("Using GitHub token from gh CLI")
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        pass

                if not github_token:
                    github_token = self.config.get("github", {}).get("token")

                headers = {}
                if github_token:
                    headers["Authorization"] = f"token {github_token}"
                else:
                    self.logger.warning(
                        "No GitHub authentication found. Rate limited to 60 requests/hour. "
                        "Run 'gh auth login' to authenticate."
                    )

                response = requests.get(
                    api_url, params=params, headers=headers, timeout=10
                )

                # Check for rate limiting
                if (
                    response.status_code == 403
                    and "rate limit" in response.text.lower()
                ):
                    self.logger.warning(
                        "GitHub API rate limit exceeded. "
                        "Set GITHUB_TOKEN environment variable to increase limit to 5000/hour. "
                        "Skipping PR check for this poll cycle."
                    )
                    return []

                response.raise_for_status()
                prs = response.json()

                # Filter for Evolution System PRs
                # Match branches created by Evolution System:
                # - self-improvement/* (primary pattern)
                # - enhancement/* (legacy pattern)
                # - fix/* when created by automation
                evolution_branch_patterns = [
                    "self-improvement/",
                    "enhancement/",
                    "fix/",
                ]

                evolution_prs = []
                for pr in prs:
                    branch = pr.get("head", {}).get("ref", "")
                    pr_number = pr.get("number", "?")
                    pr_title = pr.get("title", "")[:50]

                    # Check if branch matches any Evolution System pattern
                    is_evolution_pr = any(
                        pattern in branch for pattern in evolution_branch_patterns
                    )

                    if is_evolution_pr:
                        evolution_prs.append(pr)
                        self.logger.debug(
                            f"Found Evolution PR #{pr_number}: {pr_title} (branch: {branch})"
                        )
                    else:
                        self.logger.debug(
                            f"Ignoring non-Evolution PR #{pr_number}: {pr_title} (branch: {branch})"
                        )

                if evolution_prs:
                    self.logger.info(
                        f"Found {len(evolution_prs)} Evolution System PR(s) to wait for"
                    )

                return evolution_prs

            except ImportError:
                self.logger.warning("requests library not available - cannot check PRs")
                return []
            except Exception as e:
                self.logger.warning(f"Error calling GitHub API: {e}")
                return []

        except Exception as e:
            self.logger.error(f"Error checking open PRs: {e}", exc_info=True)
            return []

    def _poll_github_issues(self) -> int:
        """
        Poll GitHub for approved issues and create tasks for them

        Returns:
            Number of tasks created from approved issues
        """
        try:
            # Get git remote to determine GitHub repo
            cf_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=str(cf_root),
                timeout=5,
            )

            if result.returncode != 0:
                self.logger.debug("Could not get git remote URL")
                return 0

            remote_url = result.stdout.strip()

            # Parse GitHub owner/repo from remote URL
            if "github.com" in remote_url:
                if remote_url.startswith("git@github.com:"):
                    repo_path = remote_url.replace("git@github.com:", "").replace(
                        ".git", ""
                    )
                elif "https://github.com/" in remote_url:
                    repo_path = remote_url.replace("https://github.com/", "").replace(
                        ".git", ""
                    )
                else:
                    self.logger.debug(f"Unrecognized GitHub URL format: {remote_url}")
                    return 0

                owner, repo = repo_path.split("/")
            else:
                self.logger.debug("Not a GitHub repository")
                return 0

            # Call GitHub API to get issues with "approved" label
            api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
            params = {"state": "open", "labels": "approved"}

            try:
                import requests

                # Get GitHub token for authentication
                github_token = os.environ.get("GITHUB_TOKEN")

                if not github_token:
                    try:
                        result = subprocess.run(
                            ["gh", "auth", "token"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if result.returncode == 0:
                            github_token = result.stdout.strip()
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        pass

                if not github_token:
                    github_token = self.config.get("github", {}).get("token")

                headers = {}
                if github_token:
                    headers["Authorization"] = f"token {github_token}"

                response = requests.get(
                    api_url, params=params, headers=headers, timeout=10
                )

                if (
                    response.status_code == 403
                    and "rate limit" in response.text.lower()
                ):
                    self.logger.warning(
                        "GitHub API rate limit exceeded. Skipping issue poll."
                    )
                    return 0

                response.raise_for_status()
                issues = response.json()

                if not issues:
                    return 0

                # Check which issues already have tasks in the queue
                existing_tasks = self.task_queue.list_tasks(
                    status=TaskStatus.PENDING.value, limit=100
                )
                existing_tasks.extend(
                    self.task_queue.list_tasks(
                        status=TaskStatus.RUNNING.value, limit=100
                    )
                )

                existing_issue_nums = set()
                for task in existing_tasks:
                    if "github_issue" in task.params:
                        existing_issue_nums.add(task.params["github_issue"])

                # Create tasks for new approved issues
                tasks_created = 0
                for issue in issues:
                    issue_number = issue.get("number")
                    issue_title = issue.get("title", "N/A")
                    issue_body = issue.get("body", "")

                    # Skip if we already have a task for this issue
                    if issue_number in existing_issue_nums:
                        continue

                    # Create task for this approved issue
                    self.task_queue.create_task(
                        task_type=TaskType.SELF_IMPROVEMENT.value,
                        params={
                            "action": "implement_github_issue",
                            "github_issue": issue_number,
                            "description": issue_title,
                            "details": issue_body,
                            "priority": 10,  # GitHub-approved issues get highest priority
                            "category": "github_approved",
                        },
                        priority=10,
                    )

                    self.logger.info(
                        f"📋 Created task for approved GitHub issue #{issue_number}: {issue_title}"
                    )
                    tasks_created += 1

                if tasks_created > 0:
                    self.logger.info(
                        f"✅ Created {tasks_created} task(s) from approved GitHub issues"
                    )

                return tasks_created

            except ImportError:
                self.logger.debug(
                    "requests library not available - cannot check issues"
                )
                return 0
            except Exception as e:
                self.logger.debug(f"Error calling GitHub API for issues: {e}")
                return 0

        except Exception as e:
            self.logger.debug(f"Error polling GitHub issues: {e}")
            return 0

    def _maintain_backlog(self):
        """
        Maintain GitHub issue backlog at target size using Scout + Backlog Generator

        This runs periodically (every 5 minutes) to ensure there's always a healthy
        backlog of issues for humans to review and approve.

        Uses lightweight Scout agent + Claude CLI (no MCP needed).
        """
        try:
            current_time = time.time()
            # Check backlog every 5 minutes (300 seconds)
            if current_time - self.last_backlog_check < 300:
                return

            self.last_backlog_check = current_time

            self.logger.info("🔍 GitHub backlog maintenance starting...")

            # Run backlog maintenance (Scout + issue creation)
            self.backlog_generator.maintain_backlog()

            self.logger.info("✅ GitHub backlog maintenance complete")

        except Exception as e:
            self.logger.warning(f"Error maintaining backlog: {e}", exc_info=True)

    def _cleanup_orphaned_sandboxes(self):
        """
        Clean up old sandboxes that haven't been used recently (24+ hours old).

        This prevents /tmp from filling up with abandoned sandboxes from:
        - Daemon crashes
        - Process kills
        - Failed cleanups

        Runs hourly (3600 seconds).
        """
        try:
            from .sandboxes import SandboxManager

            current_time = time.time()
            # Check hourly (3600 seconds)
            if not hasattr(self, "last_sandbox_cleanup"):
                self.last_sandbox_cleanup = 0

            if current_time - self.last_sandbox_cleanup < 3600:
                return

            self.last_sandbox_cleanup = current_time

            self.logger.info("🧹 Running orphaned sandbox cleanup...")

            manager = SandboxManager()
            cleaned = manager.cleanup_old_sandboxes(max_age_hours=24)

            if cleaned > 0:
                self.logger.info(f"✅ Cleaned up {cleaned} orphaned sandbox(es)")
            else:
                self.logger.debug("No orphaned sandboxes found")

        except Exception as e:
            self.logger.warning(f"Error cleaning up sandboxes: {e}", exc_info=True)

    def _check_recently_closed_prs(self):
        """
        Check for recently closed/merged Evolution PRs (last 2 hours)

        This prevents stuck RUNNING tasks when a PR is merged between poll cycles.
        Returns list of closed Evolution PRs.
        """
        try:
            import subprocess
            import json
            from datetime import datetime, timedelta

            # Use gh CLI to get recently closed PRs
            # gh pr list --state closed --limit 20 gives us recent closed PRs
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--state",
                    "closed",
                    "--limit",
                    "20",
                    "--json",
                    "number,headRefName,closedAt,mergedAt,title,url",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path(__file__).parent.parent.parent),
            )

            if result.returncode != 0:
                return []

            prs = json.loads(result.stdout)
            evolution_prs = []

            # Filter for Evolution PRs closed in last 2 hours
            cutoff_time = datetime.now() - timedelta(hours=2)

            evolution_branch_patterns = ["self-improvement/", "enhancement/", "fix/"]

            for pr in prs:
                branch = pr.get("headRefName", "")
                closed_at = pr.get("closedAt", "")

                # Check if Evolution PR
                is_evolution_pr = any(
                    pattern in branch for pattern in evolution_branch_patterns
                )

                if not is_evolution_pr:
                    continue

                # Check if closed recently (last 2 hours)
                if closed_at:
                    try:
                        # Parse ISO timestamp
                        closed_time = datetime.fromisoformat(
                            closed_at.replace("Z", "+00:00")
                        )
                        if closed_time.replace(tzinfo=None) < cutoff_time:
                            continue  # Too old, skip
                    except (ValueError, TypeError):
                        pass  # If parsing fails, include it anyway

                # Add to list (will be used to mark RUNNING tasks as COMPLETED)
                pr_dict = {
                    "number": pr.get("number"),
                    "head": {"ref": branch},
                    "html_url": pr.get("url"),
                    "state": "closed",
                    "merged": pr.get("mergedAt") is not None,
                }
                evolution_prs.append(pr_dict)

                self.logger.debug(
                    f"Found recently closed Evolution PR #{pr_dict['number']}: {branch}"
                )

            return evolution_prs

        except Exception as e:
            self.logger.error(f"Error checking recently closed PRs: {e}", exc_info=True)
            return []

    def _check_mcp_status(self):
        """
        Check MCP delegation status for running tasks and log progress

        Monitors MCP tasks via get_delegation_result() and logs phase/status updates
        """
        if not self.mcp_available:
            self._maybe_log_mcp_disabled("Skipping MCP status check")
            return

        try:
            from tools.mcp_server import get_delegation_result
            import json

            running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value)

            for task in running_tasks:
                if not task.result:
                    continue

                mcp_task_id = task.result.get("mcp_task_id")
                if not mcp_task_id:
                    continue

                # Get MCP status
                try:
                    status_json = get_delegation_result(
                        mcp_task_id, include_full_output=False
                    )
                    status = json.loads(status_json)

                    task_status = status.get("status", "unknown")
                    current_phase = status.get("current_phase", "N/A")
                    progress = status.get("progress", "N/A")

                    # Log MCP progress (only if changed)
                    status_key = f"mcp_{mcp_task_id}_status"
                    last_status = getattr(self, status_key, None)
                    current_status_str = f"{task_status}:{current_phase}"

                    if last_status != current_status_str:
                        self.logger.info(
                            f"🔍 MCP Task {mcp_task_id[:8]} ({task.id[:8]}):"
                        )
                        self.logger.info(f"   Status: {task_status}")
                        self.logger.info(f"   Phase: {current_phase}")
                        self.logger.info(f"   Progress: {progress}")
                        setattr(self, status_key, current_status_str)

                except Exception as e:
                    self.logger.debug(
                        f"Could not get MCP status for {mcp_task_id}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Error checking MCP status: {e}", exc_info=True)

    def _poll_delegations(self):
        """
        Poll delegation files and create tasks for user-initiated builds

        Scans ~/.context-foundry/delegations/*.json and creates monitoring
        tasks for any delegations that aren't already in the task queue.
        """
        try:
            delegations_dir = Path.home() / ".context-foundry" / "delegations"

            if not delegations_dir.exists():
                return

            # Use DelegationMode to generate tasks from delegation files
            delegation_mode = self.modes.get(TaskType.DELEGATION_BUILD.value)
            if not delegation_mode:
                return

            # Get list of tasks we should be monitoring
            delegation_tasks = delegation_mode.generate_tasks()

            for task_params in delegation_tasks:
                mcp_task_id = task_params["params"].get("mcp_task_id")

                if not mcp_task_id:
                    continue

                # Check if we already have a pending/running task for this delegation
                # (Completed tasks should not prevent re-monitoring)
                pending_tasks = self.task_queue.list_tasks(
                    status=TaskStatus.PENDING.value
                )
                running_tasks = self.task_queue.list_tasks(
                    status=TaskStatus.RUNNING.value
                )
                active_tasks = pending_tasks + running_tasks

                already_monitoring = any(
                    t.params.get("mcp_task_id") == mcp_task_id for t in active_tasks
                )

                if not already_monitoring:
                    # Create new monitoring task
                    task_type = task_params["type"]
                    params = task_params["params"]
                    priority = task_params.get("priority", 7)

                    self.task_queue.create_task(
                        task_type=task_type, params=params, priority=priority
                    )

                    project = params.get("project", "unknown")
                    self.logger.info(
                        f"📋 Started monitoring delegation: {project} ({mcp_task_id[:8]})"
                    )

        except Exception as e:
            self.logger.error(f"Error polling delegations: {e}", exc_info=True)

    def _detect_prs_and_complete_tasks(self):
        """
        Detect PRs created by Claude and mark corresponding tasks as COMPLETED

        This is the second half of the race condition fix:
        1. Tasks are kept in RUNNING state when Claude is spawned
        2. This method detects when PRs are created and marks tasks COMPLETED
        3. Only then can daemon pick up next task

        Branch naming pattern: self-improvement/task-{task_id[:8]}

        BUG FIX: Also checks recently CLOSED/MERGED PRs to handle the case where
        a PR was merged between poll cycles, preventing stuck RUNNING tasks.
        """
        try:
            # Get all RUNNING tasks first
            running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value)
            if not running_tasks:
                return

            # Get all open Evolution PRs
            open_prs = self._check_open_prs()

            # ALSO get recently closed PRs (last 2 hours) to catch merged PRs
            closed_prs = self._check_recently_closed_prs()

            # Combine both lists
            all_prs = open_prs + closed_prs

            if not all_prs:
                return

            # Match PRs to tasks by extracting task ID from branch name
            for pr in all_prs:
                branch = pr.get("head", {}).get("ref", "")
                pr_number = pr.get("number", "?")
                pr_url = pr.get("html_url", "")
                pr_state = pr.get("state", "unknown")

                # Extract task ID from branch name (e.g., "self-improvement/task-af23b3bd")
                # Branch pattern: {prefix}/task-{task_id[:8]}
                for task in running_tasks:
                    task_id_short = task.id[:8]
                    expected_branch = task.params.get(
                        "expected_branch", f"self-improvement/task-{task_id_short}"
                    )

                    # EXACT branch match (not substring!) to prevent mismatches
                    if branch != expected_branch:
                        # Log mismatch if task ID appears in branch but doesn't match exactly
                        if f"task-{task_id_short}" in branch:
                            self.logger.warning(
                                f"⚠️  Branch mismatch for task {task.id}:"
                            )
                            self.logger.warning(f"   Expected: {expected_branch}")
                            self.logger.warning(f"   Got: {branch}")
                            self.logger.warning(
                                "   Skipping task completion - wrong branch!"
                            )
                        continue

                    # Found matching PR for this task!
                    if pr_state == "closed":
                        self.logger.info(
                            f"✅ Detected MERGED PR #{pr_number} for task {task.id}"
                        )
                        self.logger.info(f"   Branch: {branch}")
                        self.logger.info(
                            "   Status: Merged (cleaning up stuck RUNNING task)"
                        )

                        # Auto-close the GitHub issue if it exists
                        github_issue = task.params.get("github_issue")
                        if github_issue:
                            self._close_github_issue(github_issue, pr_number)
                    else:
                        self.logger.info(
                            f"✅ Detected PR #{pr_number} for task {task.id}"
                        )
                        self.logger.info(f"   Branch: {branch}")
                        self.logger.info(f"   URL: {pr_url}")

                    # Mark task as COMPLETED (for both merged and open PRs)
                    result = {
                        "status": "pr_merged" if pr_state == "closed" else "pr_created",
                        "pr_number": pr_number,
                        "pr_url": pr_url,
                        "branch": branch,
                    }
                    self.task_queue.update_task_status(
                        task.id, TaskStatus.COMPLETED.value, result=result
                    )

                    self.logger.info(
                        f"🎉 Task {task.id} marked COMPLETED - PR #{pr_number} created!"
                    )
                    self.logger.info(
                        "   Daemon can now pick up next task after PR merge"
                    )
                    break

        except Exception as e:
            self.logger.error(
                f"Error detecting PRs and completing tasks: {e}", exc_info=True
            )

    def _check_stuck_running_tasks(self):
        """
        Check for tasks stuck in RUNNING state for > 2 hours

        Tasks can get stuck if:
        - Claude crashes without creating PR
        - PR is created on wrong branch
        - Daemon misses PR detection
        - MCP delegation fails to start (null task_id)

        Mark stuck tasks as FAILED to unblock the queue
        """
        try:
            from datetime import datetime, timedelta
            import json

            running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value)
            if not running_tasks:
                return

            timeout_hours = 2
            quick_fail_minutes = 5  # Fail fast for null mcp_task_id
            cutoff_time = datetime.now() - timedelta(hours=timeout_hours)
            quick_fail_cutoff = datetime.now() - timedelta(minutes=quick_fail_minutes)

            for task in running_tasks:
                # Parse task started_at timestamp
                if not task.started_at:
                    continue

                try:
                    started_time = datetime.fromisoformat(task.started_at)

                    # Check 1: Tasks with null mcp_task_id (MCP delegation failed)
                    # These should fail FAST (5 minutes) since they'll never complete
                    if task.result_json:
                        try:
                            result = json.loads(task.result_json)
                            mcp_task_id = result.get("mcp_task_id")

                            if mcp_task_id is None and started_time < quick_fail_cutoff:
                                duration_minutes = (
                                    datetime.now() - started_time
                                ).total_seconds() / 60

                                self.logger.error(
                                    f"⚠️  STUCK TASK: {task.id} has null mcp_task_id (MCP delegation failed)"
                                )
                                self.logger.error(
                                    f"   Running for {duration_minutes:.1f} minutes with no valid MCP task"
                                )
                                self.logger.error(
                                    "   MCP delegation never started - marking as FAILED"
                                )

                                # Mark as FAILED
                                self.task_queue.update_task_status(
                                    task.id,
                                    TaskStatus.FAILED.value,
                                    error=f"MCP delegation failed (null task_id). Task stuck for {duration_minutes:.1f} minutes.",
                                )

                                self.logger.info(
                                    f"✅ Marked stuck task {task.id} as FAILED - queue unblocked"
                                )
                                continue
                        except json.JSONDecodeError:
                            pass  # result_json might not be valid JSON yet

                    # Check 2: Tasks running for > 2 hours (original check)
                    if started_time < cutoff_time:
                        # Task has been RUNNING for > 2 hours
                        duration_hours = (
                            datetime.now() - started_time
                        ).total_seconds() / 3600

                        self.logger.error(
                            f"⚠️  STUCK TASK: {task.id} has been RUNNING for {duration_hours:.1f} hours"
                        )
                        self.logger.error(
                            f"   Expected branch: {task.params.get('expected_branch', 'unknown')}"
                        )
                        self.logger.error(
                            "   No matching PR detected - marking as FAILED"
                        )

                        # Mark as FAILED
                        self.task_queue.update_task_status(
                            task.id,
                            TaskStatus.FAILED.value,
                            error=f"Task stuck in RUNNING state for {duration_hours:.1f} hours with no matching PR",
                        )

                        self.logger.info(
                            f"✅ Marked stuck task {task.id} as FAILED - queue unblocked"
                        )

                except Exception as e:
                    self.logger.warning(
                        f"Error parsing started_at for task {task.id}: {e}"
                    )
                    continue

        except Exception as e:
            self.logger.error(f"Error checking stuck running tasks: {e}", exc_info=True)

    def _close_github_issue(self, issue_number: int, pr_number: int) -> bool:
        """
        Close a GitHub issue when its PR is merged

        Args:
            issue_number: GitHub issue number to close
            pr_number: PR number that fixed the issue

        Returns:
            True if issue was closed successfully, False otherwise
        """
        try:
            import subprocess

            self.logger.info(
                f"🔒 Closing GitHub issue #{issue_number} (fixed by PR #{pr_number})"
            )

            # Close the issue with a comment linking to the PR
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "close",
                    str(issue_number),
                    "--comment",
                    f"Fixed by PR #{pr_number} 🤖",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path(__file__).parent.parent.parent),
            )

            if result.returncode == 0:
                self.logger.info(f"✅ Successfully closed issue #{issue_number}")
                return True
            else:
                self.logger.warning(
                    f"Failed to close issue #{issue_number}: {result.stderr}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error closing issue #{issue_number}: {e}")
            return False

    def _queue_next_improvement_task(self):
        """
        Queue the next self-improvement task

        Priority order:
        1. Check GitHub for approved issues first (human-approved tasks)
        2. Fall back to TODOs in codebase
        3. Fall back to self-generated improvement tasks

        Called when PRs are merged to continue the perpetual loop
        """
        try:
            if not self.mcp_available:
                self._maybe_log_mcp_disabled(
                    "Skipping self-improvement task generation"
                )
                return

            self.logger.info("Generating next improvement task...")

            # PRIORITY 1: Check GitHub for approved issues FIRST
            github_tasks_created = self._poll_github_issues()
            if github_tasks_created > 0:
                self.logger.info(
                    f"✅ Queued {github_tasks_created} GitHub-approved issue(s)"
                )
                return  # GitHub tasks created, we're done

            # Check if we should only work on GitHub issues
            github_issues_only = self.config.get("daemon", {}).get(
                "github_issues_only", False
            )
            if github_issues_only:
                self.logger.info(
                    "⏸️  No approved GitHub issues found - daemon configured for GitHub issues only"
                )
                self.logger.info(
                    "   Add 'approved' label to GitHub issues to queue tasks"
                )
                return

            # PRIORITY 2 & 3: Fall back to TODO/self-generated tasks
            # Use self-improvement mode to find next task
            mode = self.modes.get(TaskType.SELF_IMPROVEMENT.value)
            if not mode:
                self.logger.error("Self-improvement mode not found!")
                return

            # Find next TODO or generate improvement task
            todos = mode._find_todos()

            if todos:
                next_todo = todos[0]  # Get highest priority TODO

                task_id = self.task_queue.create_task(
                    task_type=TaskType.SELF_IMPROVEMENT.value,
                    params={
                        "action": next_todo.get("action", "implement_todo"),
                        "file": next_todo.get("file"),
                        "line": next_todo.get("line"),
                        "description": next_todo.get("text"),
                        "priority": next_todo.get("priority", 7),
                        "category": next_todo.get("category", "general"),
                    },
                    priority=next_todo.get("priority", 7),
                )

                self.logger.info(f"✅ PERPETUAL LOOP: Queued task {task_id}")
                self.logger.info(
                    f"   📋 Next: {next_todo.get('text', 'Unknown')[:80]}..."
                )
                self.logger.info(
                    f"   🏷️  Category: {next_todo.get('category')} | Priority: {next_todo.get('priority')}"
                )

            else:
                self.logger.warning("⚠️  No more tasks found - perpetual loop paused")
                self.logger.info(
                    "   Add TODOs/FIXMEs to Context Foundry code to resume"
                )

        except Exception as e:
            self.logger.error(f"❌ Failed to queue next task: {e}", exc_info=True)


def check_daemon_status(
    verbose: bool = False,
) -> tuple[bool, Optional[int], Optional[str]]:
    """
    Check daemon status without initializing logging (avoids PermissionError)

    Args:
        verbose: If True, return error details

    Returns:
        Tuple of (is_running, pid, error_message)

    Note:
        In some shell environments (e.g., Homebrew-managed shells with restrictive
        shellenv.sh), you may see "/bin/ps: Operation not permitted" errors printed
        to stderr during shell initialization, even before Python runs. This is a
        shell environment limitation, not a failure of this function.

        Additionally, macOS security restrictions may cause os.kill(pid, 0) to
        return errno 1 (EPERM) even for processes owned by the same user. This
        function treats EPERM as "process exists" since the permission denial
        itself confirms the process is running.
    """
    pid_file = Path.home() / ".context-foundry" / "evolution" / "daemon.pid"

    if not pid_file.exists():
        return False, None, "PID file not found"

    try:
        with open(pid_file) as f:
            pid_str = f.read().strip()
            pid = int(pid_str)

        # Check if process exists
        os.kill(pid, 0)
        return True, pid, None
    except ValueError as e:
        return False, None, f"Invalid PID in file: {e}"
    except OSError as e:
        # errno 3 = ESRCH (No such process)
        # errno 1 = EPERM (Operation not permitted)
        if e.errno == 3:
            return False, None, f"Process {pid} not found"
        elif e.errno == 1:
            # Process exists but we don't have permission - still running
            # This is common on macOS with security restrictions
            return (
                True,
                pid,
                "Process running (macOS denied signal permission - this is normal)",
            )
        else:
            return False, None, f"os.kill error: {e} (errno {e.errno})"
    except Exception as e:
        return False, None, f"Unexpected error: {e}"


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Context Foundry Evolution Daemon")
    parser.add_argument(
        "command", choices=["start", "stop", "status"], help="Command to execute"
    )
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument(
        "--foreground", action="store_true", help="Run in foreground (no daemonize)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (for status command). Note: In Homebrew-managed shells, "
        "you may see '/bin/ps: Operation not permitted' errors from shellenv.sh - "
        "these are harmless shell environment warnings, not daemon failures.",
    )

    args = parser.parse_args()

    # For status and stop commands, avoid initializing the full daemon (prevents log file conflicts)
    if args.command == "status":
        is_running, pid, error = check_daemon_status(verbose=args.verbose)
        if is_running:
            print(f"Daemon is running (PID: {pid})")
            if args.verbose and error:
                print(f"  Note: {error}")
        else:
            print("Daemon is not running")
            if args.verbose and error:
                print(f"  Reason: {error}")
        return

    elif args.command == "stop":
        is_running, pid, error = check_daemon_status()
        if is_running:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent stop signal to daemon (PID: {pid})")
        else:
            print("Daemon is not running")
        return

    # Only instantiate full daemon for "start" command
    daemon = EvolutionDaemon(config_path=args.config)

    if args.command == "start":
        daemon.start(daemonize=not args.foreground)


if __name__ == "__main__":
    main()

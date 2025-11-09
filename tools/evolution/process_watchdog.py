#!/usr/bin/env python3
"""
Process Watchdog for Evolution System
Monitors spawned Claude processes for timeouts, hangs, and budget overruns
"""

import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class ProcessInfo:
    """Track information about a spawned Claude process"""

    def __init__(self, pid: int, task_id: str, started_at: datetime, log_file: str):
        self.pid = pid
        self.task_id = task_id
        self.started_at = started_at
        self.log_file = log_file
        self.estimated_tokens = 0
        self.last_check = datetime.now()

    def duration_minutes(self) -> float:
        """Get process duration in minutes"""
        return (datetime.now() - self.started_at).total_seconds() / 60

    def is_alive(self) -> bool:
        """Check if process is still running"""
        try:
            return psutil.pid_exists(self.pid)
        except:
            return False


class ProcessWatchdog:
    """
    Monitor spawned Claude processes and kill stuck/runaway instances

    Safety Features:
    - Timeout detection (max 60 minutes per task)
    - Token budget tracking (estimated)
    - Memory usage monitoring
    - Stuck process detection (no log activity)
    """

    def __init__(
        self,
        max_duration_minutes: int = 60,
        max_tokens_per_task: int = 100_000,
        check_interval_seconds: int = 30,
    ):
        """
        Initialize watchdog

        Args:
            max_duration_minutes: Max time before killing a process
            max_tokens_per_task: Max estimated tokens before alerting
            check_interval_seconds: How often to check processes
        """
        self.max_duration_minutes = max_duration_minutes
        self.max_tokens_per_task = max_tokens_per_task
        self.check_interval_seconds = check_interval_seconds

        # Track active processes
        self.processes: Dict[int, ProcessInfo] = {}

        logger.info(
            f"Watchdog initialized (max_duration: {max_duration_minutes}min, "
            f"max_tokens: {max_tokens_per_task})"
        )

    def register_process(self, pid: int, task_id: str, log_file: str):
        """
        Register a new Claude process for monitoring

        Args:
            pid: Process ID
            task_id: Associated task ID
            log_file: Path to Claude CLI log file
        """
        proc_info = ProcessInfo(
            pid=pid, task_id=task_id, started_at=datetime.now(), log_file=log_file
        )
        self.processes[pid] = proc_info
        logger.info(f"Registered process {pid} for task {task_id[:8]}")

    def unregister_process(self, pid: int):
        """Remove process from monitoring (completed normally)"""
        if pid in self.processes:
            proc_info = self.processes[pid]
            logger.info(
                f"Unregistered process {pid} for task {proc_info.task_id[:8]} "
                f"(duration: {proc_info.duration_minutes():.1f}min)"
            )
            del self.processes[pid]

    def check_processes(self) -> List[Dict]:
        """
        Check all monitored processes for issues

        Returns:
            List of actions taken (killed processes, warnings, etc.)
        """
        actions = []

        for pid, proc_info in list(self.processes.items()):
            # Check if process still exists
            if not proc_info.is_alive():
                logger.warning(
                    f"Process {pid} (task {proc_info.task_id[:8]}) "
                    f"no longer running (duration: {proc_info.duration_minutes():.1f}min)"
                )
                actions.append(
                    {
                        "action": "process_died",
                        "pid": pid,
                        "task_id": proc_info.task_id,
                        "duration_minutes": proc_info.duration_minutes(),
                    }
                )
                self.unregister_process(pid)
                continue

            # Check timeout
            if proc_info.duration_minutes() > self.max_duration_minutes:
                logger.error(
                    f"⚠️  TIMEOUT: Process {pid} (task {proc_info.task_id[:8]}) "
                    f"exceeded max duration ({proc_info.duration_minutes():.1f} > "
                    f"{self.max_duration_minutes} minutes)"
                )

                killed = self._kill_process(pid)
                actions.append(
                    {
                        "action": "killed_timeout",
                        "pid": pid,
                        "task_id": proc_info.task_id,
                        "duration_minutes": proc_info.duration_minutes(),
                        "killed": killed,
                    }
                )
                self.unregister_process(pid)
                continue

            # Check log file activity (detect stuck processes)
            stuck = self._check_if_stuck(proc_info)
            if stuck:
                logger.warning(
                    f"⚠️  STUCK: Process {pid} (task {proc_info.task_id[:8]}) "
                    f"has no log activity for 10+ minutes"
                )

                killed = self._kill_process(pid)
                actions.append(
                    {
                        "action": "killed_stuck",
                        "pid": pid,
                        "task_id": proc_info.task_id,
                        "reason": "no log activity",
                        "killed": killed,
                    }
                )
                self.unregister_process(pid)
                continue

            # Estimate token usage from log file
            estimated_tokens = self._estimate_tokens(proc_info)
            if estimated_tokens > self.max_tokens_per_task:
                logger.warning(
                    f"⚠️  TOKEN BUDGET: Process {pid} (task {proc_info.task_id[:8]}) "
                    f"estimated {estimated_tokens} tokens (>{self.max_tokens_per_task})"
                )
                actions.append(
                    {
                        "action": "warning_tokens",
                        "pid": pid,
                        "task_id": proc_info.task_id,
                        "estimated_tokens": estimated_tokens,
                    }
                )

            # Log periodic status
            if (
                proc_info.duration_minutes() > 0
                and int(proc_info.duration_minutes()) % 5 == 0
            ):
                logger.info(
                    f"Process {pid} (task {proc_info.task_id[:8]}) running for "
                    f"{proc_info.duration_minutes():.1f} minutes"
                )

        return actions

    def _kill_process(self, pid: int) -> bool:
        """
        Kill a process (and all its children)

        Args:
            pid: Process ID to kill

        Returns:
            True if killed successfully
        """
        try:
            process = psutil.Process(pid)

            # Kill all children first
            children = process.children(recursive=True)
            for child in children:
                logger.info(f"Killing child process {child.pid}")
                child.kill()

            # Kill parent
            logger.info(f"Killing process {pid}")
            process.kill()

            # Wait for termination
            process.wait(timeout=5)

            logger.info(f"✅ Successfully killed process {pid}")
            return True

        except psutil.NoSuchProcess:
            logger.info(f"Process {pid} already terminated")
            return True
        except Exception as e:
            logger.error(f"Failed to kill process {pid}: {e}")
            return False

    def _check_if_stuck(self, proc_info: ProcessInfo) -> bool:
        """
        Check if process appears stuck (no log activity)

        Args:
            proc_info: Process info to check

        Returns:
            True if process appears stuck
        """
        try:
            log_path = Path(proc_info.log_file)
            if not log_path.exists():
                return False

            # Get last modification time
            last_modified = datetime.fromtimestamp(log_path.stat().st_mtime)

            # If log hasn't been updated in 10 minutes, consider stuck
            inactive_minutes = (datetime.now() - last_modified).total_seconds() / 60

            # Only consider stuck if process has been running for at least 5 minutes
            # (avoid false positives during startup)
            if proc_info.duration_minutes() > 5 and inactive_minutes > 10:
                return True

            return False

        except Exception as e:
            logger.warning(f"Error checking if process stuck: {e}")
            return False

    def _estimate_tokens(self, proc_info: ProcessInfo) -> int:
        """
        Estimate tokens used by reading log file size

        Rough estimate: 1 KB log ≈ 200 tokens

        Args:
            proc_info: Process info

        Returns:
            Estimated token count
        """
        try:
            log_path = Path(proc_info.log_file)
            if not log_path.exists():
                return 0

            # Get file size in KB
            size_kb = log_path.stat().st_size / 1024

            # Rough estimation
            estimated = int(size_kb * 200)

            return estimated

        except Exception as e:
            logger.warning(f"Error estimating tokens: {e}")
            return 0

    def get_active_processes(self) -> List[Dict]:
        """
        Get list of active monitored processes

        Returns:
            List of process info dicts
        """
        result = []
        for pid, proc_info in self.processes.items():
            result.append(
                {
                    "pid": pid,
                    "task_id": proc_info.task_id,
                    "started_at": proc_info.started_at.isoformat(),
                    "duration_minutes": proc_info.duration_minutes(),
                    "is_alive": proc_info.is_alive(),
                    "log_file": proc_info.log_file,
                }
            )
        return result

    def kill_all(self):
        """Emergency: kill all monitored processes"""
        logger.warning(
            f"EMERGENCY: Killing all {len(self.processes)} monitored processes"
        )
        for pid in list(self.processes.keys()):
            self._kill_process(pid)
            self.unregister_process(pid)

"""
Parser for Context Foundry session files.

Reads and parses .context-foundry/*.json files to extract build information.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionParser:
    """
    Parser for Context Foundry session metadata files.

    Handles reading and parsing:
    - current-phase.json
    - session-summary.json
    - Other session metadata
    """

    def __init__(self, watch_path: Path):
        """
        Initialize session parser.

        Args:
            watch_path: Path to .context-foundry directory
        """
        self.watch_path = watch_path

    def _normalize_phase_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize phase data to consistent field names.

        Handles both:
        - snake_case (current_phase, progress_detail)
        - camelCase (currentPhase, progressDetail)

        Args:
            data: Raw phase data dict

        Returns:
            Normalized dict with consistent field names
        """
        normalized = {}

        # Phase field (current_phase, currentPhase -> phase)
        normalized["phase"] = (
            data.get("phase") or data.get("current_phase") or data.get("currentPhase")
        )

        # Status field
        normalized["status"] = data.get("status")

        # Description field (progress_detail, progressDetail -> description)
        normalized["description"] = (
            data.get("description")
            or data.get("progress_detail")
            or data.get("progressDetail")
            or ""
        )

        # Session ID
        normalized["session_id"] = data.get("session_id") or data.get("sessionId")

        # Test iteration
        normalized["test_iteration"] = data.get("test_iteration") or data.get(
            "testIteration"
        )

        # Phase number
        normalized["phase_number"] = data.get("phase_number") or data.get("phaseNumber")

        return normalized

    def read_current_phase(
        self, job_id: str, started_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Read current-phase.json with stale file validation.

        Args:
            job_id: Job UUID for logging
            started_at: Job start time for stale validation

        Returns:
            Phase data dict or None if file doesn't exist or is stale
        """
        file_path = self.watch_path / "current-phase.json"

        if not file_path.exists():
            logger.debug(f"current-phase.json not found at {file_path}")
            return None

        # Check if file is stale
        if started_at:
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            # Handle started_at as string (ISO format from DB) or datetime object
            if isinstance(started_at, str):
                started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            if file_mtime < started_at:
                logger.warning(
                    f"Stale current-phase.json detected for job {job_id}. "
                    f"File mtime: {file_mtime}, job started: {started_at}"
                )
                return None

        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Try to parse as JSON directly first
            try:
                data = json.loads(content)
                # Unwrap PhaseInfo if present
                if "PhaseInfo" in data:
                    data = data["PhaseInfo"]

                # Normalize field names (support both snake_case and camelCase)
                normalized = self._normalize_phase_data(data)

                logger.debug(
                    f"Read current phase: {normalized.get('phase')} - {normalized.get('status')}"
                )
                return normalized
            except json.JSONDecodeError:
                # File might have BAML debug output - find the last valid JSON object
                lines = content.strip().split("\n")
                # Start from the end and find lines that look like JSON
                json_lines = []
                in_json = False
                brace_count = 0

                for line in reversed(lines):
                    if not in_json:
                        # Look for closing brace
                        if line.strip() == "}":
                            in_json = True
                            brace_count = 1
                            json_lines.insert(0, line)
                    else:
                        json_lines.insert(0, line)
                        # Count braces to find start of JSON (backwards iteration)
                        brace_count += line.count("}") - line.count("{")
                        if brace_count == 0:
                            # Found complete JSON object
                            break

                if json_lines:
                    try:
                        json_str = "\n".join(json_lines)
                        data = json.loads(json_str)

                        # Unwrap PhaseInfo if present
                        if "PhaseInfo" in data:
                            data = data["PhaseInfo"]

                        # Normalize field names
                        normalized = self._normalize_phase_data(data)

                        logger.debug(
                            f"Read current phase (from BAML output): {normalized.get('phase')} - {normalized.get('status')}"
                        )
                        return normalized
                    except json.JSONDecodeError as e:
                        logger.error(
                            f"Failed to parse extracted JSON from BAML output: {e}"
                        )
                        return None
                else:
                    logger.error("Could not find valid JSON in current-phase.json")
                    return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse current-phase.json: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading current-phase.json: {e}")
            return None

    def read_session_summary(self) -> Optional[Dict[str, Any]]:
        """
        Read session-summary.json.

        Returns:
            Session summary dict or None if file doesn't exist
        """
        file_path = self.watch_path / "session-summary.json"

        if not file_path.exists():
            logger.debug(f"session-summary.json not found at {file_path}")
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            logger.debug(
                f"Read session summary: {len(data.get('files_created', []))} files"
            )
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse session-summary.json: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading session-summary.json: {e}")
            return None

    def get_files_created(self) -> List[str]:
        """
        Get list of files created in current session.

        Returns:
            List of file paths
        """
        summary = self.read_session_summary()
        if not summary:
            return []

        return summary.get("files_created", [])

    def get_deployment_info(self) -> Optional[Dict[str, Any]]:
        """
        Get deployment information from session summary.

        Returns:
            Deployment info dict with status, reason, commit_sha, etc.
        """
        summary = self.read_session_summary()
        if not summary:
            return None

        deployment = summary.get("deployment", {})
        if not deployment:
            return None

        return {
            "status": deployment.get("status"),  # "success", "skipped", "failed"
            "reason": deployment.get("reason"),  # Error/skip reason
            "commit_sha": deployment.get("commit_sha"),
            "repository_url": deployment.get("repository_url"),
            "local_commit_created": deployment.get("local_commit_created", False),
            "attempted_at": deployment.get("attempted_at"),
        }

    def compare_file_lists(
        self, old_files: List[str], new_files: List[str]
    ) -> List[str]:
        """
        Compare two file lists to detect new files.

        Args:
            old_files: Previous file list
            new_files: Current file list

        Returns:
            List of newly created files
        """
        old_set = set(old_files)
        new_set = set(new_files)

        created = list(new_set - old_set)

        if created:
            logger.info(f"Detected {len(created)} new files: {created}")

        return created

    def read_build_tasks(self) -> Optional[Dict[str, Any]]:
        """
        Read build-tasks.json to get parallel build information.

        Returns:
            Build tasks dict with parallel_mode and task info, or None if not found
        """
        file_path = self.watch_path / "build-tasks.json"

        if not file_path.exists():
            logger.debug(f"build-tasks.json not found at {file_path}")
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            parallel_mode = data.get("parallel_mode", False)
            tasks = data.get("tasks", [])
            total_tasks = data.get("total_tasks", len(tasks))

            logger.debug(
                f"Read build tasks: parallel_mode={parallel_mode}, total_tasks={total_tasks}"
            )
            return {
                "parallel_mode": parallel_mode,
                "total_tasks": total_tasks,
                "tasks": tasks,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse build-tasks.json: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading build-tasks.json: {e}")
            return None

    def get_parallel_build_info(self) -> Optional[Dict[str, Any]]:
        """
        Get parallel build information including task progress.

        Returns:
            Dict with parallel build metrics or None if not in parallel mode
        """
        build_tasks = self.read_build_tasks()
        if not build_tasks or not build_tasks.get("parallel_mode"):
            return None

        tasks = build_tasks.get("tasks", [])
        total_tasks = build_tasks.get("total_tasks", 0)

        # Calculate wave structure based on dependencies
        tasks_by_wave = self._calculate_waves(tasks)
        current_wave = self._estimate_current_wave(tasks_by_wave)
        max_wave = len(tasks_by_wave)

        return {
            "parallel_mode": True,
            "total_tasks": total_tasks,
            "current_wave": current_wave,
            "max_wave": max_wave,
            "tasks_per_wave": {
                f"wave_{i+1}": len(wave) for i, wave in enumerate(tasks_by_wave)
            },
            "max_concurrent_agents": max(len(wave) for wave in tasks_by_wave)
            if tasks_by_wave
            else 0,
        }

    def _calculate_waves(self, tasks: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Calculate task waves based on dependency graph.

        Args:
            tasks: List of task dictionaries with id and dependencies

        Returns:
            List of waves, where each wave is a list of task IDs
        """
        waves = []
        completed = set()
        remaining = {task["id"]: task.get("dependencies", []) for task in tasks}

        while remaining:
            # Find tasks with no unmet dependencies
            ready = [
                task_id
                for task_id, deps in remaining.items()
                if all(dep in completed for dep in deps)
            ]

            if not ready:
                # Cyclic dependency or error
                break

            waves.append(ready)
            for task_id in ready:
                completed.add(task_id)
                del remaining[task_id]

        return waves

    def _estimate_current_wave(self, tasks_by_wave: List[List[str]]) -> int:
        """
        Estimate which wave is currently running based on file creation.

        Args:
            tasks_by_wave: List of waves with task IDs

        Returns:
            Current wave number (1-indexed)
        """
        # Simple heuristic: assume we're in the last wave if build is active
        # Could be enhanced by tracking task completion markers
        return len(tasks_by_wave) if tasks_by_wave else 0

    def validate_file_mtime(self, file_path: Path, started_at: datetime) -> bool:
        """
        Check if a file's modification time is after a job's start time.

        Args:
            file_path: File to check
            started_at: Job start timestamp

        Returns:
            True if file is newer than started_at, False otherwise
        """
        if not file_path.exists():
            return False

        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return file_mtime >= started_at

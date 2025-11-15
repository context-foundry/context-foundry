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
            if file_mtime < started_at:
                logger.warning(
                    f"Stale current-phase.json detected for job {job_id}. "
                    f"File mtime: {file_mtime}, job started: {started_at}"
                )
                return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            logger.debug(
                f"Read current phase: {data.get('phase')} - {data.get('status')}"
            )
            return data

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

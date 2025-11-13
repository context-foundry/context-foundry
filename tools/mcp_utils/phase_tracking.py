"""
Phase Tracking Utilities

Functions for reading and managing phase tracking information.
Extracted from tools/mcp_server.py for better code organization.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


def read_phase_info(
    working_directory: str, task_start_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Read phase tracking information from .context-foundry/current-phase.json with staleness validation.

    Args:
        working_directory: Path to project working directory
        task_start_time: Optional datetime when task started (for staleness check)

    Returns:
        Dict with phase info, or empty dict if file doesn't exist, is invalid, or is stale.
    """
    try:
        phase_file = Path(working_directory) / ".context-foundry" / "current-phase.json"
        if not phase_file.exists():
            return {}

        # Validate file isn't stale from previous build
        if task_start_time:
            file_mtime = datetime.fromtimestamp(phase_file.stat().st_mtime)
            if file_mtime < task_start_time:
                # File was modified before this task started - it's stale!
                # Return empty dict to avoid showing old phase data
                return {}

        with open(phase_file, "r") as f:
            phase_data = json.load(f)

        return phase_data
    except (json.JSONDecodeError, FileNotFoundError, PermissionError):
        # File doesn't exist yet, is invalid JSON, or can't be read
        return {}
    except Exception:
        # Any other error - return empty dict
        return {}

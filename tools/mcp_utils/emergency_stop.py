"""
Emergency Stop for Context Foundry Pipeline

Global kill switch that halts all agent activity.
Part of Milestone 6: Emergency Stop.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import os

# Emergency stop file location
EMERGENCY_STOP_DIR = Path.home() / ".context-foundry"
EMERGENCY_STOP_FILE = EMERGENCY_STOP_DIR / "EMERGENCY_STOP"


@dataclass
class EmergencyStopStatus:
    """Status of the emergency stop"""

    active: bool
    activated_at: Optional[str] = None
    reason: Optional[str] = None
    activated_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "activated_at": self.activated_at,
            "reason": self.reason,
            "activated_by": self.activated_by,
        }


def is_emergency_stop_active() -> bool:
    """
    Check if emergency stop is currently active.

    This is designed to be called frequently (every loop iteration)
    so it's kept as lightweight as possible - just a file existence check.

    Returns:
        True if emergency stop file exists, False otherwise
    """
    return EMERGENCY_STOP_FILE.exists()


def get_emergency_stop_status() -> EmergencyStopStatus:
    """
    Get detailed status of the emergency stop.

    Returns:
        EmergencyStopStatus with activation details if active
    """
    if not EMERGENCY_STOP_FILE.exists():
        return EmergencyStopStatus(active=False)

    try:
        content = EMERGENCY_STOP_FILE.read_text().strip()
        if content:
            data = json.loads(content)
            return EmergencyStopStatus(
                active=True,
                activated_at=data.get("activated_at"),
                reason=data.get("reason"),
                activated_by=data.get("activated_by"),
            )
        else:
            # File exists but is empty - still counts as active
            return EmergencyStopStatus(active=True)
    except (json.JSONDecodeError, OSError):
        # File exists but can't be read - still counts as active
        return EmergencyStopStatus(active=True)


def activate_emergency_stop(reason: Optional[str] = None) -> EmergencyStopStatus:
    """
    Activate the emergency stop.

    Creates the EMERGENCY_STOP file with metadata about when and why
    it was activated. All agents check for this file and will halt
    immediately when it exists.

    Args:
        reason: Optional reason for activating emergency stop

    Returns:
        EmergencyStopStatus confirming activation
    """
    # Ensure directory exists
    EMERGENCY_STOP_DIR.mkdir(parents=True, exist_ok=True)

    # Create stop file with metadata
    metadata = {
        "activated_at": datetime.utcnow().isoformat(),
        "reason": reason or "Manual emergency stop",
        "activated_by": os.environ.get("USER", "unknown"),
    }

    EMERGENCY_STOP_FILE.write_text(json.dumps(metadata, indent=2))

    return EmergencyStopStatus(
        active=True,
        activated_at=metadata["activated_at"],
        reason=metadata["reason"],
        activated_by=metadata["activated_by"],
    )


def deactivate_emergency_stop() -> EmergencyStopStatus:
    """
    Deactivate the emergency stop.

    Removes the EMERGENCY_STOP file, allowing agents to resume operation.

    Returns:
        EmergencyStopStatus confirming deactivation
    """
    if EMERGENCY_STOP_FILE.exists():
        EMERGENCY_STOP_FILE.unlink()

    return EmergencyStopStatus(active=False)


def check_emergency_stop_or_raise(context: str = "operation") -> None:
    """
    Check if emergency stop is active and raise an exception if so.

    Use this at the start of operations that should be halted by
    emergency stop.

    Args:
        context: Description of what was being attempted (for error message)

    Raises:
        EmergencyStopError: If emergency stop is active
    """
    if is_emergency_stop_active():
        status = get_emergency_stop_status()
        raise EmergencyStopError(
            f"Emergency stop is active - cannot proceed with {context}. "
            f"Reason: {status.reason or 'Not specified'}. "
            f"Run 'cfd emergency-resume' to clear."
        )


class EmergencyStopError(Exception):
    """Raised when an operation is blocked by emergency stop"""

    pass

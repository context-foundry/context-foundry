"""
Lightweight Phase Status Tracker for HITL Builds.

Replaces the complex phase_prompts.py system with simple status tracking.
Humans review the actual .md handoff files (scout-report.md, architecture.md, etc.)
instead of JSON blobs.

Status flow:
  waiting → running → pending_approval → approved → complete
                   ↘ failed
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Simple status values
STATUS_WAITING = "waiting"
STATUS_RUNNING = "running"
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"

# Phase order for determining what to approve before each phase
PHASE_ORDER = [
    "Scout",
    "Architect",
    "Builder",
    "Test",
    "Screenshot",
    "Documentation",
    "Deploy",
    "Feedback",
]

# Map each phase to its output handoff file
PHASE_OUTPUTS = {
    "Scout": "scout-report.md",
    "Architect": "architecture.md",
    "Builder": "build-tasks.md",  # Or could be the source files themselves
    "Test": "test-report.md",
    "Screenshot": None,  # No handoff file
    "Documentation": None,  # Creates README.md but not in .context-foundry
    "Deploy": None,
    "Feedback": "learnings.json",
}


def _get_status_file(working_dir: Path) -> Path:
    """Get path to phase-status.json."""
    return working_dir / ".context-foundry" / "phase-status.json"


def get_phase_status(working_dir: Path) -> Dict[str, Any]:
    """
    Read phase status from phase-status.json.

    Returns:
        Dict with execution_mode and phases status, or empty dict if not found.
    """
    status_file = _get_status_file(working_dir)

    if not status_file.exists():
        return {}

    try:
        return json.loads(status_file.read_text())
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to read phase status: {e}")
        return {}


def init_phase_status(
    working_dir: Path, execution_mode: str = "autonomous"
) -> Dict[str, Any]:
    """
    Initialize phase status for a new build.

    Args:
        working_dir: Project directory
        execution_mode: "autonomous" or "hitl"

    Returns:
        Initial status dict
    """
    status = {
        "execution_mode": execution_mode,
        "created_at": datetime.now().isoformat(),
        "phases": {
            phase: {
                "status": STATUS_WAITING,
                "output": PHASE_OUTPUTS.get(phase),
            }
            for phase in PHASE_ORDER
        },
    }

    _save_status(working_dir, status)
    return status


def _save_status(working_dir: Path, status: Dict[str, Any]) -> None:
    """Save status to file."""
    status_file = _get_status_file(working_dir)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(status, indent=2))


def set_phase_status(
    working_dir: Path, phase: str, status: str, error: Optional[str] = None
) -> None:
    """
    Update status for a single phase.

    Args:
        working_dir: Project directory
        phase: Phase name (e.g., "Scout", "Architect")
        status: New status value
        error: Optional error message if status is "failed"
    """
    current = get_phase_status(working_dir)

    if not current:
        current = init_phase_status(working_dir)

    if phase not in current.get("phases", {}):
        current.setdefault("phases", {})[phase] = {
            "status": STATUS_WAITING,
            "output": PHASE_OUTPUTS.get(phase),
        }

    current["phases"][phase]["status"] = status
    current["phases"][phase][f"{status}_at"] = datetime.now().isoformat()

    if error:
        current["phases"][phase]["error"] = error

    _save_status(working_dir, current)
    logger.info(f"Phase {phase} status: {status}")


def mark_phase_running(working_dir: Path, phase: str) -> None:
    """Mark a phase as currently running."""
    set_phase_status(working_dir, phase, STATUS_RUNNING)


def mark_phase_pending_approval(working_dir: Path, phase: str) -> None:
    """Mark a phase as complete and awaiting human approval (HITL mode)."""
    set_phase_status(working_dir, phase, STATUS_PENDING_APPROVAL)


def mark_phase_complete(working_dir: Path, phase: str) -> None:
    """Mark a phase as fully complete."""
    set_phase_status(working_dir, phase, STATUS_COMPLETE)


def mark_phase_failed(working_dir: Path, phase: str, error: str) -> None:
    """Mark a phase as failed with error message."""
    set_phase_status(working_dir, phase, STATUS_FAILED, error=error)


def approve_phase(working_dir: Path, phase: str, approved_by: str = "user") -> bool:
    """
    Approve a phase to proceed (HITL trigger).

    Args:
        working_dir: Project directory
        phase: Phase to approve
        approved_by: Who approved (for audit)

    Returns:
        True if approved, False if phase wasn't pending approval
    """
    current = get_phase_status(working_dir)

    if not current:
        logger.warning(f"No status file found for {working_dir}")
        return False

    phase_data = current.get("phases", {}).get(phase, {})

    if phase_data.get("status") != STATUS_PENDING_APPROVAL:
        logger.warning(
            f"Phase {phase} is not pending approval (status: {phase_data.get('status')})"
        )
        return False

    current["phases"][phase]["status"] = STATUS_APPROVED
    current["phases"][phase]["approved_at"] = datetime.now().isoformat()
    current["phases"][phase]["approved_by"] = approved_by

    _save_status(working_dir, current)
    logger.info(f"Phase {phase} approved by {approved_by}")
    return True


def is_phase_approved(working_dir: Path, phase: str) -> bool:
    """Check if a phase has been approved."""
    current = get_phase_status(working_dir)
    phase_data = current.get("phases", {}).get(phase, {})
    return phase_data.get("status") in [STATUS_APPROVED, STATUS_COMPLETE]


def get_previous_phase(phase: str) -> Optional[str]:
    """Get the phase that runs before this one."""
    try:
        idx = PHASE_ORDER.index(phase)
        if idx > 0:
            return PHASE_ORDER[idx - 1]
    except ValueError:
        pass
    return None


def get_next_phase(phase: str) -> Optional[str]:
    """Get the phase that runs after this one."""
    try:
        idx = PHASE_ORDER.index(phase)
        if idx < len(PHASE_ORDER) - 1:
            return PHASE_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def wait_for_approval(
    working_dir: Path, phase: str, timeout: int = 3600, poll_interval: float = 2.0
) -> bool:
    """
    Block until a phase is approved (HITL mode).

    Args:
        working_dir: Project directory
        phase: Phase to wait for approval
        timeout: Maximum wait time in seconds (default 1 hour)
        poll_interval: How often to check (default 2 seconds)

    Returns:
        True if approved, False if timed out
    """
    import sys

    start_time = time.time()
    last_log = 0

    while time.time() - start_time < timeout:
        if is_phase_approved(working_dir, phase):
            return True

        # Log waiting status every 30 seconds
        elapsed = time.time() - start_time
        if elapsed - last_log >= 30:
            print(
                f"⏳ Waiting for {phase} approval... ({int(elapsed)}s)", file=sys.stderr
            )
            last_log = elapsed

        time.sleep(poll_interval)

    logger.warning(f"Timeout waiting for {phase} approval after {timeout}s")
    return False


def get_phases_pending_approval(working_dir: Path) -> List[str]:
    """Get list of phases currently awaiting approval."""
    current = get_phase_status(working_dir)
    pending = []

    for phase, data in current.get("phases", {}).items():
        if data.get("status") == STATUS_PENDING_APPROVAL:
            pending.append(phase)

    return pending


def get_handoff_content(working_dir: Path, phase: str) -> Optional[str]:
    """
    Read the handoff file content for a phase.

    This is what the human reviews before approving.

    Args:
        working_dir: Project directory
        phase: Phase whose output to read

    Returns:
        File content or None if no handoff file
    """
    output_file = PHASE_OUTPUTS.get(phase)
    if not output_file:
        return None

    handoff_path = working_dir / ".context-foundry" / output_file

    if not handoff_path.exists():
        return None

    try:
        return handoff_path.read_text()
    except IOError as e:
        logger.warning(f"Failed to read handoff file {handoff_path}: {e}")
        return None


def get_all_handoffs(working_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Get all handoff files and their status for dashboard display.

    Returns:
        Dict mapping phase name to {output, content, status}
    """
    current = get_phase_status(working_dir)
    handoffs = {}

    for phase in PHASE_ORDER:
        phase_data = current.get("phases", {}).get(phase, {})
        output_file = PHASE_OUTPUTS.get(phase)

        handoffs[phase] = {
            "output": output_file,
            "content": get_handoff_content(working_dir, phase) if output_file else None,
            "status": phase_data.get("status", STATUS_WAITING),
            "approved_at": phase_data.get("approved_at"),
            "approved_by": phase_data.get("approved_by"),
        }

    return handoffs

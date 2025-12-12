"""
Pipeline State Machine for Modular Agent Pipeline.

Provides state management for pause/resume functionality:
- PipelineState enum for pipeline lifecycle
- PipelineStateSnapshot for persistence
- Helpers for reading/writing state
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List


class PipelineState(str, Enum):
    """Pipeline lifecycle states"""

    IDLE = "idle"  # Not started
    RUNNING = "running"  # Currently executing a phase
    PAUSED = "paused"  # Paused for inspection
    WAITING_APPROVAL = "waiting_approval"  # Waiting for human approval
    COMPLETED = "completed"  # All phases complete
    FAILED = "failed"  # A phase failed
    CANCELLED = "cancelled"  # User cancelled

    @classmethod
    def terminal_states(cls) -> set:
        """Return set of terminal states"""
        return {cls.COMPLETED, cls.FAILED, cls.CANCELLED}

    @classmethod
    def resumable_states(cls) -> set:
        """Return set of states that can be resumed"""
        return {cls.PAUSED, cls.WAITING_APPROVAL}


# Default phase order
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


@dataclass
class PipelineStateSnapshot:
    """
    Serializable state for pause/resume.

    Persisted to .context-foundry/pipeline-state.json
    """

    pipeline_id: str
    state: PipelineState

    # Progress tracking
    phases_completed: List[str] = field(default_factory=list)
    phases_skipped: List[str] = field(
        default_factory=list
    )  # Phases skipped (e.g., simple_mode)
    current_phase: Optional[str] = None
    phases_remaining: List[str] = field(default_factory=list)

    # Execution config
    execution_mode: str = "autonomous"  # "autonomous", "interactive", "selective"
    pause_after_phases: List[str] = field(default_factory=list)
    target_phases: List[str] = field(default_factory=list)  # For selective mode

    # Timing
    started_at: Optional[str] = None
    paused_at: Optional[str] = None
    resumed_at: Optional[str] = None

    # Task config (preserved for resume)
    task_config: Dict[str, Any] = field(default_factory=dict)

    # Error info
    error: Optional[str] = None
    failed_phase: Optional[str] = None

    @classmethod
    def create(
        cls,
        task_config: Dict[str, Any],
        execution_mode: str = "autonomous",
        pause_after_phases: Optional[List[str]] = None,
        target_phases: Optional[List[str]] = None,
    ) -> "PipelineStateSnapshot":
        """
        Create a new pipeline state.

        Args:
            task_config: Build configuration (task, working_directory, etc.)
            execution_mode: "autonomous", "interactive", or "selective"
            pause_after_phases: Phases to pause after (e.g., ["Scout", "Architect"])
            target_phases: For selective mode, phases to run

        Returns:
            New PipelineStateSnapshot
        """
        # Determine phases to run
        if target_phases:
            phases_remaining = [p for p in PHASE_ORDER if p in target_phases]
        else:
            phases_remaining = list(PHASE_ORDER)

        return cls(
            pipeline_id=str(uuid.uuid4()),
            state=PipelineState.IDLE,
            phases_remaining=phases_remaining,
            execution_mode=execution_mode,
            pause_after_phases=pause_after_phases or [],
            target_phases=target_phases or [],
            started_at=datetime.now().isoformat(),
            task_config=task_config,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "pipeline_id": self.pipeline_id,
            "state": self.state.value
            if isinstance(self.state, PipelineState)
            else self.state,
            "phases_completed": self.phases_completed,
            "phases_skipped": self.phases_skipped,
            "current_phase": self.current_phase,
            "phases_remaining": self.phases_remaining,
            "execution_mode": self.execution_mode,
            "pause_after_phases": self.pause_after_phases,
            "target_phases": self.target_phases,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "resumed_at": self.resumed_at,
            "task_config": self.task_config,
            "error": self.error,
            "failed_phase": self.failed_phase,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineStateSnapshot":
        """Create from dictionary"""
        state_value = data.get("state", "idle")
        if isinstance(state_value, str):
            state = PipelineState(state_value)
        else:
            state = state_value

        return cls(
            pipeline_id=data.get("pipeline_id", str(uuid.uuid4())),
            state=state,
            phases_completed=data.get("phases_completed", []),
            phases_skipped=data.get("phases_skipped", []),
            current_phase=data.get("current_phase"),
            phases_remaining=data.get("phases_remaining", list(PHASE_ORDER)),
            execution_mode=data.get("execution_mode", "autonomous"),
            pause_after_phases=data.get("pause_after_phases", []),
            target_phases=data.get("target_phases", []),
            started_at=data.get("started_at"),
            paused_at=data.get("paused_at"),
            resumed_at=data.get("resumed_at"),
            task_config=data.get("task_config", {}),
            error=data.get("error"),
            failed_phase=data.get("failed_phase"),
        )

    def save(self, working_directory: Path) -> Path:
        """
        Save state to .context-foundry/pipeline-state.json

        Args:
            working_directory: Project directory

        Returns:
            Path to saved state file
        """
        cf_dir = working_directory / ".context-foundry"
        cf_dir.mkdir(parents=True, exist_ok=True)

        state_file = cf_dir / "pipeline-state.json"
        state_file.write_text(json.dumps(self.to_dict(), indent=2))

        return state_file

    @classmethod
    def load(cls, working_directory: Path) -> Optional["PipelineStateSnapshot"]:
        """
        Load state from .context-foundry/pipeline-state.json

        Args:
            working_directory: Project directory

        Returns:
            PipelineStateSnapshot or None if not found
        """
        state_file = working_directory / ".context-foundry" / "pipeline-state.json"

        if not state_file.exists():
            return None

        try:
            data = json.loads(state_file.read_text())
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Failed to load pipeline state: {e}")
            return None

    def should_pause_after(self, phase_name: str) -> bool:
        """
        Check if pipeline should pause after this phase.

        Args:
            phase_name: Phase that just completed

        Returns:
            True if should pause
        """
        # Interactive mode: pause after every phase
        if self.execution_mode == "interactive":
            return True

        # Check explicit pause list
        if phase_name in self.pause_after_phases:
            return True

        return False

    def mark_phase_started(self, phase_name: str) -> None:
        """Mark a phase as started"""
        self.state = PipelineState.RUNNING
        self.current_phase = phase_name

    def mark_phase_completed(self, phase_name: str) -> None:
        """Mark a phase as completed"""
        if phase_name not in self.phases_completed:
            self.phases_completed.append(phase_name)
        if phase_name in self.phases_remaining:
            self.phases_remaining.remove(phase_name)
        self.current_phase = None

        # Check if all phases done
        if not self.phases_remaining:
            self.state = PipelineState.COMPLETED

    def mark_phase_skipped(self, phase_name: str, reason: str = "") -> None:
        """
        Mark a phase as skipped (e.g., due to simple_mode).

        Removes from phases_remaining but adds to phases_skipped instead of phases_completed.

        Args:
            phase_name: Phase to skip
            reason: Optional reason for skipping (e.g., "simple_mode")
        """
        if phase_name not in self.phases_skipped:
            self.phases_skipped.append(phase_name)
        if phase_name in self.phases_remaining:
            self.phases_remaining.remove(phase_name)

        # Check if all phases done (completed + skipped)
        if not self.phases_remaining:
            self.state = PipelineState.COMPLETED

    def mark_paused(self, after_phase: str) -> None:
        """Mark pipeline as paused"""
        self.state = PipelineState.PAUSED
        self.paused_at = datetime.now().isoformat()
        self.current_phase = None

    def mark_resumed(self) -> None:
        """Mark pipeline as resumed"""
        self.state = PipelineState.RUNNING
        self.resumed_at = datetime.now().isoformat()
        self.paused_at = None

    def mark_failed(self, phase_name: str, error: str) -> None:
        """Mark pipeline as failed"""
        self.state = PipelineState.FAILED
        self.failed_phase = phase_name
        self.error = error
        self.current_phase = None

    def get_next_phase(self) -> Optional[str]:
        """Get the next phase to run"""
        if self.phases_remaining:
            return self.phases_remaining[0]
        return None

    def get_resume_command(self, working_directory: Path) -> str:
        """Generate the CLI command to resume this pipeline"""
        next_phase = self.get_next_phase()
        if next_phase:
            return f"cfd resume --from {next_phase} --dir {working_directory}"
        return f"cfd resume --dir {working_directory}"

    def get_status_summary(self) -> str:
        """Get a human-readable status summary"""
        lines = [
            f"Pipeline: {self.pipeline_id[:8]}",
            f"State: {self.state.value.upper()}",
            f"Mode: {self.execution_mode}",
            f"Completed: {', '.join(self.phases_completed) or 'None'}",
        ]

        if self.phases_skipped:
            lines.append(f"Skipped: {', '.join(self.phases_skipped)}")

        if self.current_phase:
            lines.append(f"Current: {self.current_phase}")

        if self.phases_remaining:
            lines.append(f"Remaining: {', '.join(self.phases_remaining)}")

        if self.paused_at:
            lines.append(f"Paused at: {self.paused_at}")

        if self.error:
            lines.append(f"Error: {self.error}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_pipeline_state(working_directory: Path) -> Optional[PipelineStateSnapshot]:
    """
    Get current pipeline state for a project.

    Args:
        working_directory: Project directory

    Returns:
        PipelineStateSnapshot or None
    """
    return PipelineStateSnapshot.load(working_directory)


def save_pipeline_state(state: PipelineStateSnapshot, working_directory: Path) -> Path:
    """
    Save pipeline state for a project.

    Args:
        state: Pipeline state to save
        working_directory: Project directory

    Returns:
        Path to state file
    """
    return state.save(working_directory)


def is_pipeline_paused(working_directory: Path) -> bool:
    """
    Check if a pipeline is currently paused.

    Args:
        working_directory: Project directory

    Returns:
        True if paused
    """
    state = get_pipeline_state(working_directory)
    return state is not None and state.state in PipelineState.resumable_states()


def can_resume_pipeline(working_directory: Path) -> tuple:
    """
    Check if a pipeline can be resumed.

    Args:
        working_directory: Project directory

    Returns:
        (can_resume: bool, reason: str)
    """
    state = get_pipeline_state(working_directory)

    if state is None:
        return False, "No pipeline state found"

    if state.state in PipelineState.terminal_states():
        return False, f"Pipeline is in terminal state: {state.state.value}"

    if state.state not in PipelineState.resumable_states():
        return False, f"Pipeline state {state.state.value} is not resumable"

    return True, "Pipeline can be resumed"


def get_phase_index(phase_name: str) -> int:
    """
    Get the index of a phase in the default order.

    Args:
        phase_name: Phase name

    Returns:
        Index (or -1 if not found)
    """
    try:
        return PHASE_ORDER.index(phase_name)
    except ValueError:
        return -1


def get_phases_from(start_phase: str) -> List[str]:
    """
    Get list of phases starting from a specific phase.

    Args:
        start_phase: Phase to start from

    Returns:
        List of phases from start_phase onward
    """
    idx = get_phase_index(start_phase)
    if idx == -1:
        return list(PHASE_ORDER)
    return PHASE_ORDER[idx:]

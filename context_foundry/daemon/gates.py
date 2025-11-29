"""
Phase Gate Manager for Context Foundry Daemon

Provides gate-based evaluation of job progress through phases using:
- PHASE_SEQUENCE from phase_execution.py
- Task states from the database
- Event emission for gate transitions

Gates represent checkpoints in the pipeline that must be passed sequentially.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .models import TaskStatus, PhaseEvent
from .store import Store
from .metrics import get_metrics, log_structured

logger = logging.getLogger(__name__)


# =============================================================================
# PHASE SEQUENCE (canonical ordering)
# =============================================================================

# This matches PHASE_SEQUENCE from tools/mcp_utils/phase_execution.py
PHASE_SEQUENCE: Dict[str, int] = {
    "Scout": 0,
    "Architect": 1,
    "Builder": 2,
    "Test": 3,
    "Screenshot": 4,
    "Documentation": 5,
    "Deploy": 6,
    "Feedback": 7,
}

# Reverse mapping for convenience
SEQUENCE_TO_PHASE: Dict[int, str] = {v: k for k, v in PHASE_SEQUENCE.items()}

# Default required phases for a successful build
DEFAULT_REQUIRED_PHASES = ["Scout", "Architect", "Builder", "Test"]


class GateStatus(str, Enum):
    """Status of a phase gate"""

    PENDING = "pending"  # Not yet reached
    ACTIVE = "active"  # Currently executing
    PASSED = "passed"  # Successfully completed
    FAILED = "failed"  # Failed to pass
    SKIPPED = "skipped"  # Intentionally skipped


@dataclass
class GateState:
    """State of a single phase gate"""

    phase: str
    sequence: int
    status: GateStatus
    task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "sequence": self.sequence,
            "status": self.status.value,
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class JobGateReport:
    """Complete gate status report for a job"""

    job_id: str
    gates: List[GateState]
    current_gate: Optional[str]
    next_gate: Optional[str]
    highest_passed_gate: Optional[str]
    all_required_passed: bool
    has_failures: bool

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "gates": [g.to_dict() for g in self.gates],
            "current_gate": self.current_gate,
            "next_gate": self.next_gate,
            "highest_passed_gate": self.highest_passed_gate,
            "all_required_passed": self.all_required_passed,
            "has_failures": self.has_failures,
        }


class GateManager:
    """
    Manages phase gates for jobs.

    Provides:
    - Gate state evaluation based on task states
    - Queries for current/next/completed gates
    - Gate transition event emission
    """

    def __init__(self, store: Store):
        """
        Initialize gate manager.

        Args:
            store: Store instance for persistence
        """
        self.store = store

    def _task_status_to_gate_status(self, task_status: TaskStatus) -> GateStatus:
        """Convert task status to gate status"""
        if task_status == TaskStatus.SUCCEEDED:
            return GateStatus.PASSED
        elif task_status in (
            TaskStatus.FAILED,
            TaskStatus.TIMED_OUT,
            TaskStatus.CANCELLED,
        ):
            return GateStatus.FAILED
        elif task_status == TaskStatus.RUNNING:
            return GateStatus.ACTIVE
        elif task_status == TaskStatus.SKIPPED:
            return GateStatus.SKIPPED
        else:
            return GateStatus.PENDING

    def get_gate_state(self, job_id: str, phase: str) -> GateState:
        """
        Get the state of a specific gate for a job.

        Args:
            job_id: Job ID
            phase: Phase name

        Returns:
            GateState for the specified phase
        """
        sequence = PHASE_SEQUENCE.get(phase, 99)
        task = self.store.get_task_by_name(job_id, phase)

        if not task:
            return GateState(
                phase=phase,
                sequence=sequence,
                status=GateStatus.PENDING,
            )

        # Calculate duration if completed
        duration = None
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()

        return GateState(
            phase=phase,
            sequence=sequence,
            status=self._task_status_to_gate_status(task.status),
            task_id=task.id,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error=task.error,
            duration_seconds=duration,
        )

    def get_all_gates(
        self,
        job_id: str,
        phases: Optional[List[str]] = None,
    ) -> List[GateState]:
        """
        Get state of all gates for a job.

        Args:
            job_id: Job ID
            phases: List of phases to check (default: all in PHASE_SEQUENCE)

        Returns:
            List of GateState in sequence order
        """
        if phases is None:
            phases = list(PHASE_SEQUENCE.keys())

        gates = []
        for phase in sorted(phases, key=lambda p: PHASE_SEQUENCE.get(p, 99)):
            gates.append(self.get_gate_state(job_id, phase))

        return gates

    def get_gate_report(
        self,
        job_id: str,
        required_phases: Optional[List[str]] = None,
    ) -> JobGateReport:
        """
        Generate a complete gate status report for a job.

        Args:
            job_id: Job ID
            required_phases: Phases that must pass for success

        Returns:
            JobGateReport with full gate analysis
        """
        if required_phases is None:
            required_phases = DEFAULT_REQUIRED_PHASES

        gates = self.get_all_gates(job_id)

        # Find current, next, and highest passed gates
        current_gate = None
        next_gate = None
        highest_passed_gate = None
        highest_passed_seq = -1
        has_failures = False

        for gate in gates:
            if gate.status == GateStatus.ACTIVE:
                current_gate = gate.phase
            elif gate.status == GateStatus.PASSED:
                if gate.sequence > highest_passed_seq:
                    highest_passed_seq = gate.sequence
                    highest_passed_gate = gate.phase
            elif gate.status == GateStatus.FAILED:
                has_failures = True

        # Determine next gate (first pending after highest passed)
        for gate in gates:
            if gate.status == GateStatus.PENDING:
                if current_gate is None or gate.sequence > PHASE_SEQUENCE.get(
                    current_gate, 0
                ):
                    next_gate = gate.phase
                    break

        # Check if all required phases passed
        all_required_passed = True
        for phase in required_phases:
            gate = next((g for g in gates if g.phase == phase), None)
            if not gate or gate.status != GateStatus.PASSED:
                all_required_passed = False
                break

        return JobGateReport(
            job_id=job_id,
            gates=gates,
            current_gate=current_gate,
            next_gate=next_gate,
            highest_passed_gate=highest_passed_gate,
            all_required_passed=all_required_passed,
            has_failures=has_failures,
        )

    # =========================================================================
    # GATE QUERIES
    # =========================================================================

    def has_phase_completed(self, job_id: str, phase: str) -> bool:
        """Check if a specific phase has completed successfully."""
        gate = self.get_gate_state(job_id, phase)
        return gate.status == GateStatus.PASSED

    def has_phase_failed(self, job_id: str, phase: str) -> bool:
        """Check if a specific phase has failed."""
        gate = self.get_gate_state(job_id, phase)
        return gate.status == GateStatus.FAILED

    def is_phase_active(self, job_id: str, phase: str) -> bool:
        """Check if a specific phase is currently running."""
        gate = self.get_gate_state(job_id, phase)
        return gate.status == GateStatus.ACTIVE

    def get_current_phase(self, job_id: str) -> Optional[str]:
        """Get the currently active phase for a job."""
        report = self.get_gate_report(job_id)
        return report.current_gate

    def get_next_phase(self, job_id: str) -> Optional[str]:
        """Get the next phase that should run for a job."""
        report = self.get_gate_report(job_id)
        return report.next_gate

    def get_highest_completed_phase(self, job_id: str) -> Optional[str]:
        """Get the highest phase that has completed successfully."""
        report = self.get_gate_report(job_id)
        return report.highest_passed_gate

    def get_completed_phases(self, job_id: str) -> List[str]:
        """Get list of all completed phases in order."""
        gates = self.get_all_gates(job_id)
        return [g.phase for g in gates if g.status == GateStatus.PASSED]

    def get_failed_phases(self, job_id: str) -> List[str]:
        """Get list of all failed phases."""
        gates = self.get_all_gates(job_id)
        return [g.phase for g in gates if g.status == GateStatus.FAILED]

    # =========================================================================
    # GATE EVENTS
    # =========================================================================

    def emit_gate_passed_event(
        self,
        job_id: str,
        phase: str,
        duration_seconds: Optional[float] = None,
    ) -> PhaseEvent:
        """
        Emit an event when a gate is passed.

        Args:
            job_id: Job ID
            phase: Phase that passed
            duration_seconds: How long the phase took

        Returns:
            Created PhaseEvent
        """
        sequence = PHASE_SEQUENCE.get(phase, 99)
        next_phase = SEQUENCE_TO_PHASE.get(sequence + 1)

        event = PhaseEvent.create(
            job_id=job_id,
            phase=phase,
            status="gate_passed",
            details={
                "sequence": sequence,
                "next_phase": next_phase,
            },
            duration_seconds=duration_seconds,
        )
        self.store.save_phase_event(event)

        # Structured logging
        log_structured(
            logger,
            logging.INFO,
            f"Gate passed: {phase} (job: {job_id[:8]})",
            event="gate_passed",
            job_id=job_id,
            phase=phase,
            gate_name=phase,
            sequence=sequence,
            next_phase=next_phase,
            duration_seconds=duration_seconds,
        )

        # Metrics
        get_metrics().inc_gates_passed(phase)

        return event

    def emit_gate_failed_event(
        self,
        job_id: str,
        phase: str,
        error: Optional[str] = None,
    ) -> PhaseEvent:
        """
        Emit an event when a gate fails.

        Args:
            job_id: Job ID
            phase: Phase that failed
            error: Error message

        Returns:
            Created PhaseEvent
        """
        sequence = PHASE_SEQUENCE.get(phase, 99)

        event = PhaseEvent.create(
            job_id=job_id,
            phase=phase,
            status="gate_failed",
            details={
                "sequence": sequence,
                "error": error,
            },
        )
        self.store.save_phase_event(event)

        # Structured logging
        log_structured(
            logger,
            logging.WARNING,
            f"Gate failed: {phase} (job: {job_id[:8]})",
            event="gate_failed",
            job_id=job_id,
            phase=phase,
            gate_name=phase,
            sequence=sequence,
            reason=error,
        )

        # Metrics
        get_metrics().inc_gates_failed(phase)

        return event

    # =========================================================================
    # GATE PROGRESSION HELPERS
    # =========================================================================

    def can_start_phase(
        self,
        job_id: str,
        phase: str,
        required_predecessors: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a phase can be started based on predecessor completion.

        Args:
            job_id: Job ID
            phase: Phase to check
            required_predecessors: Phases that must complete first.
                                 If None, uses sequence order.

        Returns:
            Tuple of (can_start, reason_if_not)
        """
        sequence = PHASE_SEQUENCE.get(phase, 99)

        # Determine required predecessors
        if required_predecessors is None:
            # All phases before this one in sequence
            required_predecessors = [
                p for p, s in PHASE_SEQUENCE.items() if s < sequence
            ]

        # Check if phase is already running or completed
        gate = self.get_gate_state(job_id, phase)
        if gate.status == GateStatus.ACTIVE:
            return False, f"{phase} is already running"
        if gate.status == GateStatus.PASSED:
            return False, f"{phase} has already completed"
        if gate.status == GateStatus.FAILED:
            return False, f"{phase} has already failed"

        # Check all predecessors have passed
        for pred in required_predecessors:
            pred_gate = self.get_gate_state(job_id, pred)
            if pred_gate.status != GateStatus.PASSED:
                return (
                    False,
                    f"Predecessor {pred} has not completed (status: {pred_gate.status.value})",
                )

        return True, None

    def get_phase_sequence_position(self, phase: str) -> int:
        """Get the sequence position of a phase (0-indexed)."""
        return PHASE_SEQUENCE.get(phase, -1)

    def get_phase_by_sequence(self, sequence: int) -> Optional[str]:
        """Get phase name by sequence position."""
        return SEQUENCE_TO_PHASE.get(sequence)


# =============================================================================
# MODULE-LEVEL HELPERS
# =============================================================================


def get_gate_manager(store: Store) -> GateManager:
    """Factory function to create a GateManager."""
    return GateManager(store)

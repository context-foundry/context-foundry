"""
Centralized State Machine for Context Foundry Daemon

Provides unified state transition logic for Jobs and Tasks with:
- Validated state transitions
- Event emission on all transitions
- Thread-safe updates with per-job locking
- Audit trail via phase_events table

This module centralizes all status updates to ensure consistency,
prevent race conditions, and maintain a complete audit trail.
"""

import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, Set

from .models import (
    Job,
    JobStatus,
    Task,
    TaskStatus,
    PhaseEvent,
)
from .store import Store
from .metrics import get_metrics, log_structured
from .gates import GateManager

logger = logging.getLogger(__name__)


# =============================================================================
# VALID STATE TRANSITIONS
# =============================================================================

# Job state transitions (what states can transition to what)
JOB_TRANSITIONS: Dict[JobStatus, Set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.TIMED_OUT,
        JobStatus.WAITING_APPROVAL,
        JobStatus.STALLED,  # No progress/heartbeats beyond threshold
    },
    JobStatus.WAITING_APPROVAL: {
        JobStatus.RUNNING,  # Resume after approval
        JobStatus.CANCELLED,
        JobStatus.TIMED_OUT,
        JobStatus.STALLED,  # Can stall while waiting
    },
    JobStatus.STALLED: {
        JobStatus.RUNNING,  # Can be resumed/retried
        JobStatus.CANCELLED,
        JobStatus.FAILED,  # Manual failure after review
    },
    # Terminal states - no outbound transitions
    JobStatus.SUCCEEDED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
    JobStatus.TIMED_OUT: set(),
}

# Task state transitions
TASK_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.SKIPPED},
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.SKIPPED},
    TaskStatus.RUNNING: {
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.TIMED_OUT,
        TaskStatus.WAITING_APPROVAL,
    },
    TaskStatus.WAITING_APPROVAL: {
        TaskStatus.RUNNING,  # Resume after approval
        TaskStatus.CANCELLED,
        TaskStatus.TIMED_OUT,
    },
    # Terminal states
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.TIMED_OUT: set(),
    TaskStatus.SKIPPED: set(),
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""

    def __init__(
        self, entity_type: str, entity_id: str, from_status: str, to_status: str
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid {entity_type} transition: {from_status} -> {to_status} "
            f"(id: {entity_id})"
        )


class StateMachine:
    """
    Centralized state machine for Job and Task lifecycle management.

    Provides:
    - Thread-safe state transitions with per-job locking
    - Validation of allowed transitions
    - Automatic event emission for audit trail
    - Heartbeat tracking for liveness detection
    """

    def __init__(self, store: Store):
        """
        Initialize state machine.

        Args:
            store: Store instance for persistence
        """
        self.store = store

        # Per-job locks for thread-safe state updates
        # This prevents race conditions when multiple workers update the same job
        self._job_locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()  # Lock for accessing _job_locks

    def _get_job_lock(self, job_id: str) -> threading.Lock:
        """Get or create a lock for a specific job"""
        with self._locks_lock:
            if job_id not in self._job_locks:
                self._job_locks[job_id] = threading.Lock()
            return self._job_locks[job_id]

    def _cleanup_job_lock(self, job_id: str) -> None:
        """Remove lock for a completed job to prevent memory leak"""
        with self._locks_lock:
            self._job_locks.pop(job_id, None)

    # =========================================================================
    # JOB STATE TRANSITIONS
    # =========================================================================

    def can_transition_job(self, from_status: JobStatus, to_status: JobStatus) -> bool:
        """Check if a job state transition is valid"""
        allowed = JOB_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    def transition_job(
        self,
        job_id: str,
        to_status: JobStatus,
        reason: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Job:
        """
        Transition a job to a new status with validation and event emission.

        Args:
            job_id: Job ID to transition
            to_status: Target status
            reason: Human-readable reason for transition
            error: Error message (for FAILED status)
            result: Job result data (for SUCCEEDED status)
            metadata: Additional metadata to store in event
            force: If True, skip transition validation (use carefully!)

        Returns:
            Updated Job instance

        Raises:
            InvalidTransitionError: If transition is not allowed
            ValueError: If job not found
        """
        lock = self._get_job_lock(job_id)

        with lock:
            # Get current job state
            job = self.store.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            from_status = job.status

            # Validate transition (unless forced)
            if not force and not self.can_transition_job(from_status, to_status):
                raise InvalidTransitionError(
                    "job", job_id, from_status.value, to_status.value
                )

            # Prepare timestamps
            now = datetime.now()
            started_at = (
                now if to_status == JobStatus.RUNNING and not job.started_at else None
            )
            completed_at = now if to_status in JobStatus.terminal_states() else None

            # Update job in database
            self.store.update_job_status(
                job_id=job_id,
                status=to_status,
                started_at=started_at,
                completed_at=completed_at,
                result=result,
                error=error,
            )

            # Emit phase event for audit trail
            event_details = {
                "from_status": from_status.value,
                "to_status": to_status.value,
                "reason": reason,
            }
            if metadata:
                event_details.update(metadata)
            if error:
                event_details["error"] = error

            event = PhaseEvent.create(
                job_id=job_id,
                phase="_job",  # Special phase name for job-level events
                status=f"job_{to_status.value}",
                details=event_details,
            )
            self.store.save_phase_event(event)

            # Structured logging for observability
            log_structured(
                logger,
                logging.INFO,
                f"Job {job_id[:8]} transitioned: {from_status.value} -> {to_status.value}",
                event="job_transition",
                job_id=job_id,
                old_status=from_status.value,
                new_status=to_status.value,
                reason=reason,
            )

            # Record metrics
            metrics = get_metrics()
            if to_status == JobStatus.RUNNING and from_status == JobStatus.QUEUED:
                metrics.inc_jobs_started()
            elif to_status == JobStatus.SUCCEEDED:
                metrics.inc_jobs_succeeded()
            elif to_status == JobStatus.FAILED:
                metrics.inc_jobs_failed(reason=reason)
            elif to_status == JobStatus.STALLED:
                metrics.inc_jobs_stalled()
            elif to_status == JobStatus.TIMED_OUT:
                metrics.inc_jobs_timed_out()
            elif to_status == JobStatus.CANCELLED:
                metrics.inc_jobs_cancelled()

            # Record job duration when reaching terminal state
            if to_status in JobStatus.terminal_states():
                updated_job = self.store.get_job(job_id)
                if updated_job and updated_job.started_at and updated_job.completed_at:
                    duration = (
                        updated_job.completed_at - updated_job.started_at
                    ).total_seconds()
                    metrics.record_job_duration(duration)

            # Update gauge metrics for active/queued jobs
            active_count = len(
                self.store.list_jobs(status=JobStatus.RUNNING, limit=1000)
            )
            queued_count = len(
                self.store.list_jobs(status=JobStatus.QUEUED, limit=1000)
            )
            metrics.set_jobs_active(active_count)
            metrics.set_jobs_queued(queued_count)

            # Cleanup lock if job is terminal
            if to_status in JobStatus.terminal_states():
                self._cleanup_job_lock(job_id)

            # Return updated job
            return self.store.get_job(job_id)

    def start_job(self, job_id: str) -> Job:
        """Convenience method to start a job (QUEUED -> RUNNING)"""
        return self.transition_job(job_id, JobStatus.RUNNING, reason="Job started")

    def complete_job(self, job_id: str, result: Optional[Dict[str, Any]] = None) -> Job:
        """Convenience method to complete a job successfully"""
        return self.transition_job(
            job_id, JobStatus.SUCCEEDED, reason="Job completed", result=result
        )

    def fail_job(self, job_id: str, error: str) -> Job:
        """Convenience method to fail a job"""
        return self.transition_job(
            job_id, JobStatus.FAILED, reason="Job failed", error=error
        )

    def timeout_job(self, job_id: str) -> Job:
        """Convenience method to timeout a job"""
        return self.transition_job(
            job_id, JobStatus.TIMED_OUT, reason="Job exceeded timeout"
        )

    def cancel_job(self, job_id: str, reason: str = "Cancelled by user") -> Job:
        """Convenience method to cancel a job"""
        return self.transition_job(job_id, JobStatus.CANCELLED, reason=reason)

    def pause_job_for_approval(self, job_id: str, phase: str) -> Job:
        """Pause job for human approval (HITL mode)"""
        return self.transition_job(
            job_id,
            JobStatus.WAITING_APPROVAL,
            reason=f"Waiting for approval after {phase}",
            metadata={"awaiting_phase": phase},
        )

    def resume_job_from_approval(self, job_id: str) -> Job:
        """Resume job after approval"""
        return self.transition_job(
            job_id, JobStatus.RUNNING, reason="Resumed after approval"
        )

    def stall_job(self, job_id: str, reason: str = "No recent activity") -> Job:
        """Mark job as stalled due to lack of progress"""
        return self.transition_job(
            job_id,
            JobStatus.STALLED,
            reason=reason,
            metadata={"stalled_at": datetime.now().isoformat()},
        )

    def resume_stalled_job(self, job_id: str) -> Job:
        """Resume a stalled job"""
        return self.transition_job(
            job_id, JobStatus.RUNNING, reason="Resumed from stalled state"
        )

    # =========================================================================
    # JOB COMPLETION DETECTION
    # =========================================================================

    def evaluate_job_completion(
        self,
        job_id: str,
        required_phases: Optional[list] = None,
    ) -> Optional[JobStatus]:
        """
        Evaluate if a job should transition to a terminal state based on task states.

        This examines all tasks for a job and determines:
        - SUCCEEDED: All required phases completed successfully
        - FAILED: Any required phase failed (non-retriable)
        - None: Job still in progress

        Args:
            job_id: Job ID to evaluate
            required_phases: List of phase names that must succeed.
                           If None, uses default: ["Scout", "Architect", "Builder", "Test"]

        Returns:
            Suggested JobStatus or None if job should continue
        """
        if required_phases is None:
            required_phases = ["Scout", "Architect", "Builder", "Test"]

        tasks = self.store.get_tasks_for_job(job_id)
        if not tasks:
            return None  # No tasks yet

        # Build task status map
        task_map = {task.name: task for task in tasks}

        # Check for failures in required phases
        for phase in required_phases:
            task = task_map.get(phase)
            if task:
                if task.status == TaskStatus.FAILED:
                    return JobStatus.FAILED
                if task.status == TaskStatus.TIMED_OUT:
                    return JobStatus.TIMED_OUT

        # Check if all required phases succeeded
        all_succeeded = True
        for phase in required_phases:
            task = task_map.get(phase)
            if not task or task.status != TaskStatus.SUCCEEDED:
                all_succeeded = False
                break

        if all_succeeded:
            return JobStatus.SUCCEEDED

        return None  # Still in progress

    def try_complete_job(
        self,
        job_id: str,
        required_phases: Optional[list] = None,
    ) -> Optional[Job]:
        """
        Attempt to complete a job if all required phases are done.

        This is a safe operation - it only transitions if appropriate.

        Args:
            job_id: Job ID
            required_phases: Phases that must complete successfully

        Returns:
            Updated Job if transitioned, None otherwise
        """
        suggested_status = self.evaluate_job_completion(job_id, required_phases)

        if suggested_status is None:
            return None  # Job still in progress

        job = self.store.get_job(job_id)
        if not job:
            return None

        # Only transition from RUNNING state
        if job.status != JobStatus.RUNNING:
            return None

        try:
            if suggested_status == JobStatus.SUCCEEDED:
                return self.complete_job(job_id)
            elif suggested_status == JobStatus.FAILED:
                return self.fail_job(job_id, "Required phase failed")
            elif suggested_status == JobStatus.TIMED_OUT:
                return self.timeout_job(job_id)
        except InvalidTransitionError:
            logger.warning(
                f"Could not transition job {job_id[:8]} to {suggested_status}"
            )
            return None

        return None

    # =========================================================================
    # TASK STATE TRANSITIONS
    # =========================================================================

    def can_transition_task(
        self, from_status: TaskStatus, to_status: TaskStatus
    ) -> bool:
        """Check if a task state transition is valid"""
        allowed = TASK_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    def transition_task(
        self,
        task_id: str,
        to_status: TaskStatus,
        reason: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Task:
        """
        Transition a task to a new status with validation and event emission.

        Args:
            task_id: Task ID to transition
            to_status: Target status
            reason: Human-readable reason for transition
            error: Error message (for FAILED status)
            result: Task result data (for SUCCEEDED status)
            metadata: Additional metadata to store in event
            force: If True, skip transition validation

        Returns:
            Updated Task instance

        Raises:
            InvalidTransitionError: If transition is not allowed
            ValueError: If task not found
        """
        # Get current task state
        task = self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Use job lock for task operations (tasks belong to jobs)
        lock = self._get_job_lock(task.job_id)

        with lock:
            # Re-fetch under lock to ensure consistency
            task = self.store.get_task(task_id)
            from_status = task.status

            # Validate transition (unless forced)
            if not force and not self.can_transition_task(from_status, to_status):
                raise InvalidTransitionError(
                    "task", task_id, from_status.value, to_status.value
                )

            # Prepare timestamps
            now = datetime.now()
            started_at = (
                now if to_status == TaskStatus.RUNNING and not task.started_at else None
            )
            completed_at = now if to_status in TaskStatus.terminal_states() else None

            # Update task in database
            self.store.update_task_status(
                task_id=task_id,
                status=to_status,
                started_at=started_at,
                completed_at=completed_at,
                result=result,
                error=error,
            )

            # Also update heartbeat when starting
            if to_status == TaskStatus.RUNNING:
                self.store.update_task_heartbeat(task_id)

            # Emit phase event for audit trail
            event_details = {
                "task_id": task_id,
                "from_status": from_status.value,
                "to_status": to_status.value,
                "reason": reason,
            }
            if metadata:
                event_details.update(metadata)
            if error:
                event_details["error"] = error

            # Propagate provider/model from task metadata to event details
            # This ensures the dashboard always has visibility into the model used
            if task.metadata:
                if task.metadata.get("provider"):
                    event_details["provider"] = task.metadata["provider"]
                if task.metadata.get("model"):
                    event_details["model"] = task.metadata["model"]

            event = PhaseEvent.create(
                job_id=task.job_id,
                phase=task.name,
                status=f"task_{to_status.value}",
                details=event_details,
            )
            self.store.save_phase_event(event)

            # Structured logging for observability
            log_structured(
                logger,
                logging.INFO,
                f"Task {task.name} ({task_id[:8]}) transitioned: {from_status.value} -> {to_status.value}",
                event="task_transition",
                job_id=task.job_id,
                task_id=task_id,
                phase=task.name,
                old_status=from_status.value,
                new_status=to_status.value,
                reason=reason,
            )

            # Record metrics
            metrics = get_metrics()
            if to_status == TaskStatus.RUNNING and from_status != TaskStatus.RUNNING:
                metrics.inc_tasks_started(task.name)
            elif to_status == TaskStatus.SUCCEEDED:
                metrics.inc_tasks_succeeded(task.name)
                # Record duration if available
                duration = None
                if task.started_at and completed_at:
                    duration = (completed_at - task.started_at).total_seconds()
                    metrics.record_phase_duration(task.name, duration)
                # Emit gate passed event
                gate_mgr = GateManager(self.store)
                gate_mgr.emit_gate_passed_event(task.job_id, task.name, duration)
            elif to_status == TaskStatus.FAILED:
                metrics.inc_tasks_failed(task.name, reason=reason)
                # Emit gate failed event
                gate_mgr = GateManager(self.store)
                gate_mgr.emit_gate_failed_event(task.job_id, task.name, error=error)
            elif to_status == TaskStatus.TIMED_OUT:
                metrics.inc_tasks_timed_out(task.name)
                # Emit gate failed event for timeout
                gate_mgr = GateManager(self.store)
                gate_mgr.emit_gate_failed_event(
                    task.job_id, task.name, error="Task timed out"
                )

            # Return updated task
            return self.store.get_task(task_id)

    def create_task_for_phase(
        self,
        job_id: str,
        phase_name: str,
        sequence: int,
        timeout_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Create a new task for a phase.

        Args:
            job_id: Parent job ID
            phase_name: Phase name (Scout, Architect, etc.)
            sequence: Order in pipeline
            timeout_seconds: Per-task timeout
            metadata: Additional metadata

        Returns:
            Created Task instance
        """
        # Check if task already exists for this phase
        existing = self.store.get_task_by_name(job_id, phase_name)
        if existing:
            logger.debug(f"Task for phase {phase_name} already exists: {existing.id}")
            return existing

        task = Task.create(
            job_id=job_id,
            name=phase_name,
            sequence=sequence,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
        )
        self.store.save_task(task)

        # Emit creation event - include model/provider info from metadata
        event_details = {"task_id": task.id, "sequence": sequence}
        if metadata:
            if metadata.get("provider"):
                event_details["provider"] = metadata["provider"]
            if metadata.get("model"):
                event_details["model"] = metadata["model"]

        event = PhaseEvent.create(
            job_id=job_id,
            phase=phase_name,
            status="task_created",
            details=event_details,
        )
        self.store.save_phase_event(event)

        logger.info(f"Created task for phase {phase_name} (job: {job_id[:8]})")
        return task

    def start_task(self, task_id: str) -> Task:
        """Convenience method to start a task"""
        return self.transition_task(task_id, TaskStatus.RUNNING, reason="Task started")

    def complete_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
        context_percent: Optional[float] = None,
    ) -> Task:
        """Convenience method to complete a task successfully"""
        task = self.transition_task(
            task_id, TaskStatus.SUCCEEDED, reason="Task completed", result=result
        )

        # Update metrics if provided
        if tokens_used is not None or context_percent is not None:
            task_obj = self.store.get_task(task_id)
            if task_obj:
                if tokens_used is not None:
                    task_obj.tokens_used = tokens_used
                if context_percent is not None:
                    task_obj.context_percent = context_percent
                self.store.save_task(task_obj)

        return task

    def fail_task(self, task_id: str, error: str) -> Task:
        """Convenience method to fail a task"""
        return self.transition_task(
            task_id, TaskStatus.FAILED, reason="Task failed", error=error
        )

    def timeout_task(self, task_id: str) -> Task:
        """Convenience method to timeout a task"""
        return self.transition_task(
            task_id, TaskStatus.TIMED_OUT, reason="Task exceeded timeout"
        )

    def skip_task(self, task_id: str, reason: str = "Skipped") -> Task:
        """Convenience method to skip a task"""
        return self.transition_task(task_id, TaskStatus.SKIPPED, reason=reason)

    # =========================================================================
    # HEARTBEAT OPERATIONS
    # =========================================================================

    def record_task_heartbeat(
        self,
        task_id: str,
        progress: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record a heartbeat for a running task.

        This should be called periodically during long-running phases
        to indicate the task is still alive.

        Args:
            task_id: Task ID
            progress: Optional progress description
            metadata: Optional additional metadata

        Returns:
            True if heartbeat was recorded
        """
        # Update heartbeat timestamp
        updated = self.store.update_task_heartbeat(task_id)

        if updated:
            # Get task for job_id
            task = self.store.get_task(task_id)
            if task:
                # Emit heartbeat event
                event_details = {"task_id": task_id}
                if progress:
                    event_details["progress"] = progress
                if metadata:
                    event_details.update(metadata)

                # Propagate provider/model from task metadata to event details
                if task.metadata:
                    if task.metadata.get("provider"):
                        event_details["provider"] = task.metadata["provider"]
                    if task.metadata.get("model"):
                        event_details["model"] = task.metadata["model"]

                event = PhaseEvent.create(
                    job_id=task.job_id,
                    phase=task.name,
                    status="heartbeat",
                    details=event_details,
                )
                self.store.save_phase_event(event)

                logger.debug(f"Heartbeat recorded for task {task.name} ({task_id[:8]})")

        return updated

    def record_job_heartbeat(
        self,
        job_id: str,
        phase: Optional[str] = None,
        progress: Optional[str] = None,
    ) -> None:
        """
        Record a heartbeat event for a job.

        This is a simpler heartbeat that doesn't update task timestamps,
        just emits an event for monitoring.

        Args:
            job_id: Job ID
            phase: Current phase name
            progress: Progress description
        """
        event_details = {}
        if phase:
            event_details["phase"] = phase
        if progress:
            event_details["progress"] = progress

        event = PhaseEvent.create(
            job_id=job_id,
            phase=phase or "_job",
            status="heartbeat",
            details=event_details,
        )
        self.store.save_phase_event(event)

    # =========================================================================
    # STALE DETECTION
    # =========================================================================

    def get_stale_tasks(self, timeout_seconds: float = 300) -> list:
        """Get tasks with stale heartbeats"""
        return self.store.get_stale_tasks(timeout_seconds)

    def get_stale_jobs(self, timeout_seconds: float = 3600) -> list:
        """
        Get jobs that appear stale (running too long without progress).

        Args:
            timeout_seconds: Time without activity to consider stale

        Returns:
            List of stale Job instances
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
        jobs = self.store.list_jobs(status=JobStatus.RUNNING)

        stale_jobs = []
        for job in jobs:
            if job.started_at and job.started_at < cutoff:
                # Check if any tasks have recent heartbeats
                tasks = self.store.get_tasks_for_job(job.id)
                has_recent_activity = False
                for task in tasks:
                    if task.last_heartbeat and task.last_heartbeat > cutoff:
                        has_recent_activity = True
                        break

                if not has_recent_activity:
                    stale_jobs.append(job)

        return stale_jobs


# Module-level singleton for convenient access
_state_machine: Optional[StateMachine] = None


def get_state_machine(store: Store) -> StateMachine:
    """Get or create the state machine singleton"""
    global _state_machine
    if _state_machine is None:
        _state_machine = StateMachine(store)
    return _state_machine

"""
Domain models for Context Foundry Daemon

Core entities: Job, JobStatus, JobType, PhaseEvent, LogEntry
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class JobStatus(str, Enum):
    """Job lifecycle states"""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @classmethod
    def terminal_states(cls) -> set:
        """Return set of terminal states that release locks/capacity"""
        return {cls.SUCCEEDED, cls.FAILED, cls.CANCELLED, cls.TIMED_OUT}


class JobType(str, Enum):
    """Types of jobs CF Daemon can run"""

    NEW_PROJECT = "new_project"  # Build new project from scratch
    ENHANCEMENT = "enhancement"  # Evolution-style improvement task
    TESTING = "testing"  # Run tests only
    PATTERN_APPLICATION = "pattern_application"  # Apply learned patterns
    VALIDATION = "validation"  # Validate existing code
    DELEGATION = "delegation"  # Monitor external delegation task
    AUTONOMOUS_BUILD = "autonomous_build"  # Full Scout→Architect→Builder→Test flow


@dataclass
class Job:
    """
    A Context Foundry Daemon job

    Represents a unit of work to be executed by the daemon.
    Jobs have a lifecycle: queued → running → succeeded/failed
    """

    id: str
    type: JobType
    status: JobStatus
    priority: int  # 1-10 (10 = highest)
    params: Dict[str, Any]  # Job-specific parameters
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra metadata

    @classmethod
    def create(
        cls,
        job_type: JobType,
        params: Dict[str, Any],
        priority: int = 5,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Job":
        """
        Factory method to create a new job

        Args:
            job_type: Type of job to create
            params: Job-specific parameters
            priority: Job priority (1-10, default 5)
            max_retries: Maximum retry attempts (default 3)
            metadata: Optional metadata dictionary

        Returns:
            New Job instance
        """
        return cls(
            id=str(uuid.uuid4()),
            type=job_type,
            status=JobStatus.QUEUED,
            priority=max(1, min(10, priority)),  # Clamp to [1, 10]
            params=params,
            created_at=datetime.now(),
            max_retries=max_retries,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        data = asdict(self)
        # Convert enums to strings
        data["type"] = self.type.value
        data["status"] = self.status.value
        # Convert datetimes to ISO format
        data["created_at"] = self.created_at.isoformat()
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create job from dictionary"""
        # Convert string enums back to enum types
        data["type"] = JobType(data["type"])
        data["status"] = JobStatus(data["status"])
        # Convert ISO strings back to datetime
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)

    def duration(self) -> Optional[float]:
        """Get job duration in seconds (if started)"""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()


@dataclass
class PhaseEvent:
    """
    Phase transition event

    Tracks when jobs move through build phases:
    Scout → Architect → Builder → Test → Deploy
    """

    id: str
    job_id: str
    phase: str  # Scout, Architect, Builder, Test, Deploy, etc.
    status: str  # started, in_progress, completed, failed
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)  # Phase-specific details
    duration_seconds: Optional[float] = None  # Duration if phase completed
    tokens_used: Optional[int] = None  # LLM tokens consumed
    context_percent: Optional[float] = None  # % of context window used

    @classmethod
    def create(
        cls,
        job_id: str,
        phase: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        duration_seconds: Optional[float] = None,
        tokens_used: Optional[int] = None,
        context_percent: Optional[float] = None,
    ) -> "PhaseEvent":
        """Factory method to create a phase event"""
        return cls(
            id=str(uuid.uuid4()),
            job_id=job_id,
            phase=phase,
            status=status,
            timestamp=datetime.now(),
            details=details or {},
            duration_seconds=duration_seconds,
            tokens_used=tokens_used,
            context_percent=context_percent,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseEvent":
        """Create from dictionary"""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class LogEntry:
    """
    Structured log entry for a job

    Captures logs during job execution for later querying/streaming
    """

    id: str
    job_id: str
    timestamp: datetime
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra context
    phase: Optional[str] = None  # Which phase emitted this log
    source: Optional[str] = None  # Source component (runner, monitor, etc.)

    @classmethod
    def create(
        cls,
        job_id: str,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        phase: Optional[str] = None,
        source: Optional[str] = None,
    ) -> "LogEntry":
        """Factory method to create a log entry"""
        return cls(
            id=str(uuid.uuid4()),
            job_id=job_id,
            timestamp=datetime.now(),
            level=level.upper(),
            message=message,
            metadata=metadata or {},
            phase=phase,
            source=source,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Create from dictionary"""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


@dataclass
class AgentTracker:
    """
    Tracks active agents/tasks for a job.

    Implements the agent counter pattern: increment when agent spawns,
    decrement when agent completes. Job is complete when counter reaches zero.
    """

    job_id: str
    active_count: int = 0
    total_spawned: int = 0
    total_completed: int = 0
    total_failed: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    agent_ids: list = field(default_factory=list)  # Track individual agent IDs

    def register_agent(self, agent_id: str) -> int:
        """
        Register a new agent as active.

        Args:
            agent_id: Unique identifier for the agent

        Returns:
            New active count
        """
        self.active_count += 1
        self.total_spawned += 1
        self.agent_ids.append(agent_id)
        self.last_activity = datetime.now()
        return self.active_count

    def complete_agent(self, agent_id: str, success: bool = True) -> int:
        """
        Mark an agent as completed.

        Args:
            agent_id: Agent identifier
            success: Whether agent completed successfully

        Returns:
            New active count
        """
        self.active_count = max(0, self.active_count - 1)
        if success:
            self.total_completed += 1
        else:
            self.total_failed += 1

        if agent_id in self.agent_ids:
            self.agent_ids.remove(agent_id)

        self.last_activity = datetime.now()
        return self.active_count

    def is_complete(self) -> bool:
        """Check if all agents have completed (counter is zero)"""
        return self.active_count == 0 and self.total_spawned > 0

    def is_stalled(self, stall_threshold_seconds: float = 300) -> bool:
        """
        Check if job appears stalled (no activity for threshold).

        Args:
            stall_threshold_seconds: Time without activity to consider stalled

        Returns:
            True if stalled
        """
        if self.active_count == 0:
            return False

        elapsed = (datetime.now() - self.last_activity).total_seconds()
        return elapsed > stall_threshold_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "job_id": self.job_id,
            "active_count": self.active_count,
            "total_spawned": self.total_spawned,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "last_activity": self.last_activity.isoformat(),
            "agent_ids": self.agent_ids.copy(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTracker":
        """Create from dictionary"""
        data = data.copy()
        if "last_activity" in data:
            data["last_activity"] = datetime.fromisoformat(data["last_activity"])
        return cls(**data)


class PromptInjectionState(str, Enum):
    """States for phase prompt injection tracking"""

    PENDING = "pending"  # Prompt prepared, awaiting approval
    EDITING = "editing"  # User is actively editing
    APPROVED = "approved"  # User approved, ready for injection
    INJECTED = "injected"  # Prompt has been sent to agent
    COMPLETED = "completed"  # Agent finished processing
    FAILED = "failed"  # Agent or phase failed
    SKIPPED = "skipped"  # Phase was skipped (cache hit, etc.)


@dataclass
class PhasePrompt:
    """
    Tracks a phase's prompt content and injection state.

    For human-in-the-loop mode, prompts go through:
    pending → editing → approved → injected → completed

    For autonomous mode:
    pending → injected → completed
    """

    id: str
    job_id: str
    phase: str  # Scout, Architect, Builder, Test, Deploy
    state: PromptInjectionState
    system_prompt: str  # The system prompt (from phase_*.txt)
    input_instruction: str  # The user instruction/task
    system_prompt_edited: Optional[str] = None  # User-edited version
    input_instruction_edited: Optional[str] = None  # User-edited version
    created_at: datetime = field(default_factory=datetime.now)
    edited_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    injected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    edited_by: Optional[str] = None  # Who edited (dashboard_user, etc.)
    approved_by: Optional[str] = None

    @classmethod
    def create(
        cls,
        job_id: str,
        phase: str,
        system_prompt: str,
        input_instruction: str,
    ) -> "PhasePrompt":
        """Factory to create a new pending phase prompt"""
        return cls(
            id=str(uuid.uuid4()),
            job_id=job_id,
            phase=phase,
            state=PromptInjectionState.PENDING,
            system_prompt=system_prompt,
            input_instruction=input_instruction,
        )

    def get_effective_system_prompt(self) -> str:
        """Get the prompt that will be/was injected (edited or original)"""
        return self.system_prompt_edited or self.system_prompt

    def get_effective_input_instruction(self) -> str:
        """Get the instruction that will be/was injected (edited or original)"""
        return self.input_instruction_edited or self.input_instruction

    def mark_editing(self, edited_by: str = "dashboard_user") -> None:
        """Mark prompt as being edited"""
        self.state = PromptInjectionState.EDITING
        self.edited_by = edited_by

    def save_edits(
        self,
        system_prompt: Optional[str] = None,
        input_instruction: Optional[str] = None,
    ) -> None:
        """Save edited prompt content"""
        if system_prompt is not None:
            self.system_prompt_edited = system_prompt
        if input_instruction is not None:
            self.input_instruction_edited = input_instruction
        self.edited_at = datetime.now()
        self.state = PromptInjectionState.PENDING

    def approve(self, approved_by: str = "dashboard_user") -> None:
        """Approve prompt for injection"""
        self.state = PromptInjectionState.APPROVED
        self.approved_by = approved_by
        self.approved_at = datetime.now()

    def mark_injected(self) -> None:
        """Mark prompt as injected into agent context"""
        self.state = PromptInjectionState.INJECTED
        self.injected_at = datetime.now()

    def mark_completed(self) -> None:
        """Mark prompt/phase as completed"""
        self.state = PromptInjectionState.COMPLETED
        self.completed_at = datetime.now()

    def mark_failed(self) -> None:
        """Mark prompt/phase as failed"""
        self.state = PromptInjectionState.FAILED
        self.completed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data["state"] = self.state.value
        data["created_at"] = self.created_at.isoformat()
        for dt_field in ["edited_at", "approved_at", "injected_at", "completed_at"]:
            if data.get(dt_field):
                data[dt_field] = data[dt_field].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhasePrompt":
        """Create from dictionary"""
        data = data.copy()
        data["state"] = PromptInjectionState(data["state"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        for dt_field in ["edited_at", "approved_at", "injected_at", "completed_at"]:
            if data.get(dt_field):
                data[dt_field] = datetime.fromisoformat(data[dt_field])
        return cls(**data)


# Type aliases for convenience
JobID = str
PhaseEventID = str
LogEntryID = str
PhasePromptID = str

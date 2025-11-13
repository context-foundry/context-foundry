"""
Domain models for Context Foundry Daemon

Core entities: Job, JobStatus, JobType, PhaseEvent, LogEntry
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class JobStatus(str, Enum):
    """Job lifecycle states"""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Types of jobs CF Daemon can run"""

    NEW_PROJECT = "new_project"  # Build new project from scratch
    ENHANCEMENT = "enhancement"  # Evolution-style improvement task
    TESTING = "testing"  # Run tests only
    PATTERN_APPLICATION = "pattern_application"  # Apply learned patterns
    VALIDATION = "validation"  # Validate existing code
    DELEGATION = "delegation"  # Monitor external delegation task


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


# Type aliases for convenience
JobID = str
PhaseEventID = str
LogEntryID = str

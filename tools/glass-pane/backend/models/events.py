"""
Server-Sent Events (SSE) data models.
"""

from pydantic import BaseModel
from typing import Literal


class PhaseUpdateEvent(BaseModel):
    """Phase change event."""

    type: Literal["phase_update"] = "phase_update"
    data: dict  # {phase: str, status: str, description: str}


class FileCreatedEvent(BaseModel):
    """File creation event."""

    type: Literal["file_created"] = "file_created"
    data: dict  # {path: str, timestamp: str}


class LogBatchEvent(BaseModel):
    """Batch of new log entries."""

    type: Literal["log_batch"] = "log_batch"
    data: dict  # {logs: List[Log]}


class MetricsUpdateEvent(BaseModel):
    """Build metrics update."""

    type: Literal["metrics_update"] = "metrics_update"
    data: dict  # {tokens_used: int, duration: int, files: int}


class JobStatusChangeEvent(BaseModel):
    """Job status change event."""

    type: Literal["job_status_change"] = "job_status_change"
    data: dict  # {status: str}


class HeartbeatEvent(BaseModel):
    """Keep-alive heartbeat."""

    type: Literal["heartbeat"] = "heartbeat"
    data: dict  # {timestamp: str}


# Union type for all SSE events
SSEEvent = (
    PhaseUpdateEvent
    | FileCreatedEvent
    | LogBatchEvent
    | MetricsUpdateEvent
    | JobStatusChangeEvent
    | HeartbeatEvent
)

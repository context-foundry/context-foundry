"""
Log-related data models.
"""

from enum import Enum
from pydantic import BaseModel
from typing import List


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Log(BaseModel):
    """Represents a log entry."""

    id: str  # UUID string
    job_id: str
    timestamp: str  # ISO 8601
    level: LogLevel
    message: str

    class Config:
        use_enum_values = True


class LogListResponse(BaseModel):
    """Response model for listing logs."""

    logs: List[Log]
    total: int
    limit: int
    offset: int

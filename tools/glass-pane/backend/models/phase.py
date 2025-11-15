"""
Phase-related data models.
"""

from enum import Enum
from pydantic import BaseModel
from typing import Optional


class Phase(str, Enum):
    """Build phases in Context Foundry."""

    SCOUT = "Scout"
    ARCHITECT = "Architect"
    BUILDER = "Builder"
    TEST = "Test"
    DEPLOY = "Deploy"


class PhaseStatus(str, Enum):
    """Status of a build phase."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseInfo(BaseModel):
    """Information about a specific phase execution."""

    phase: Phase
    status: PhaseStatus
    description: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    iteration: int = 0

    class Config:
        use_enum_values = True

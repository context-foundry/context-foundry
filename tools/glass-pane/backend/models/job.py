"""
Job-related data models.
"""

from pydantic import BaseModel
from typing import Optional, List
from .phase import Phase, PhaseInfo


class Job(BaseModel):
    """Represents a Context Foundry build job."""

    id: str
    status: str  # 'running', 'completed', 'failed'
    started_at: str  # ISO 8601 timestamp
    completed_at: Optional[str] = None
    project_name: str
    current_phase: Optional[Phase] = None
    tokens_used: int = 0
    total_files: int = 0

    class Config:
        use_enum_values = True


class JobListResponse(BaseModel):
    """Response model for listing jobs."""

    jobs: List[Job]
    total: int
    limit: int
    offset: int


class JobDetailResponse(BaseModel):
    """Detailed job information including phase history."""

    id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    project_name: str
    current_phase: Optional[Phase] = None
    tokens_used: int = 0
    total_files: int = 0
    phases: List[PhaseInfo] = []

    class Config:
        use_enum_values = True

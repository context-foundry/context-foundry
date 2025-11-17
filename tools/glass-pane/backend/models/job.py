"""
Job-related data models.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from .phase import Phase, PhaseInfo


class Job(BaseModel):
    """Represents a Context Foundry build job."""

    id: str
    type: str  # 'autonomous_build', etc.
    status: str  # 'running', 'completed', 'failed', 'queued', 'cancelled'
    started_at: Optional[str] = None  # ISO 8601 timestamp
    completed_at: Optional[str] = None
    created_at: str  # ISO 8601 timestamp
    project_name: Optional[str] = None
    current_phase: Optional[Phase] = None
    tokens_used: int = 0
    total_files: int = 0
    params: Optional[Dict[str, Any]] = None  # Deserialized from params_json

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

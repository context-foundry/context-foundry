"""Data models for TUI"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class PhaseStatus(Enum):
    """Build phase status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BuildStatus:
    """Represents current build status from current-phase.json"""
    session_id: str
    current_phase: str
    phase_number: str
    status: str
    progress_detail: str
    test_iteration: int
    phases_completed: List[str]
    started_at: datetime
    last_updated: datetime
    parallel_execution: bool = False
    tasks_completed: int = 0

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'BuildStatus':
        """Parse from JSON file data"""
        return cls(
            session_id=data.get('session_id', 'unknown'),
            current_phase=data.get('current_phase', 'Unknown'),
            phase_number=data.get('phase_number', '0/7'),
            status=data.get('status', 'unknown'),
            progress_detail=data.get('progress_detail', ''),
            test_iteration=data.get('test_iteration', 0),
            phases_completed=data.get('phases_completed', []),
            started_at=cls._parse_datetime(data.get('started_at')),
            last_updated=cls._parse_datetime(data.get('last_updated')),
            parallel_execution=data.get('parallel_execution', False),
            tasks_completed=data.get('tasks_completed', 0)
        )

    @staticmethod
    def _parse_datetime(dt_str: Optional[str]) -> datetime:
        """Parse datetime from string"""
        if not dt_str:
            return datetime.now()
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return datetime.now()

    def get_progress_percentage(self) -> float:
        """Calculate progress percentage based on phase"""
        try:
            current, total = self.phase_number.split('/')
            return (int(current) / int(total)) * 100
        except (ValueError, ZeroDivisionError):
            return 0.0


@dataclass
class AgentMetrics:
    """Agent activity metrics"""
    agent_name: str
    total_calls: int
    tokens_used: int
    cost_usd: float
    avg_latency_ms: float
    last_active: datetime


@dataclass
class SystemStats:
    """Overall system statistics"""
    total_builds: int
    active_builds: int
    completed_builds: int
    failed_builds: int
    total_tokens_used: int
    total_cost_usd: float
    avg_build_duration_minutes: float
    last_updated: datetime


@dataclass
class BuildSummary:
    """Summary info for build list"""
    session_id: str
    status: str
    current_phase: str
    started_at: datetime
    duration_minutes: Optional[float] = None
    test_iterations: int = 0

    def get_duration_display(self) -> str:
        """Get formatted duration string"""
        if self.duration_minutes is None:
            return "-"
        if self.duration_minutes < 1:
            return f"{self.duration_minutes * 60:.0f}s"
        return f"{self.duration_minutes:.1f}m"

    def get_status_icon(self) -> str:
        """Get status icon"""
        icons = {
            "completed": "✓",
            "failed": "✗",
            "in_progress": "⋯",
            "pending": "○"
        }
        return icons.get(self.status.lower(), "•")

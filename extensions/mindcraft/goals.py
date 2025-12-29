"""
Mindcraft Goal Models

Data structures for goal planning and tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime


class GoalType(Enum):
    """Types of agent goals."""

    BUILD = "build"  # Construct structures
    GATHER = "gather"  # Collect resources
    EXPLORE = "explore"  # Map new areas
    DEFEND = "defend"  # Protect self or area
    CRAFT = "craft"  # Create items
    SURVIVE = "survive"  # Critical self-preservation
    IDLE = "idle"  # No active goal


class GoalStatus(Enum):
    """Lifecycle status of a goal."""

    PENDING = "pending"  # In queue, waiting
    ACTIVE = "active"  # Currently being executed
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Execution failed
    BLOCKED = "blocked"  # Dependencies not met


@dataclass
class Goal:
    """Represents a high-level objective for an agent."""

    description: str
    type: GoalType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 50  # 0-100, higher is more important

    # Success criteria (e.g. {"inventory": {"oak_log": 64}})
    criteria: Dict[str, Any] = field(default_factory=dict)

    # Context/Params (e.g. target location, item types)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Other goals that must complete first
    dependencies: List[str] = field(default_factory=list)

    status: GoalStatus = GoalStatus.PENDING
    assigned_agent: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "priority": self.priority,
            "criteria": self.criteria,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        goal = cls(
            id=data.get("id", str(uuid.uuid4())),
            type=GoalType(data.get("type", "idle")),
            description=data.get("description", ""),
            priority=data.get("priority", 50),
            criteria=data.get("criteria", {}),
            parameters=data.get("parameters", {}),
            dependencies=data.get("dependencies", []),
            status=GoalStatus(data.get("status", "pending")),
            assigned_agent=data.get("assigned_agent"),
            failure_reason=data.get("failure_reason"),
        )

        if data.get("created_at"):
            goal.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            goal.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            goal.completed_at = datetime.fromisoformat(data["completed_at"])

        return goal

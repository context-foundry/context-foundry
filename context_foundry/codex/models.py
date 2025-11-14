"""
Data models for Context Codex knowledge entries.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class KnowledgeType(Enum):
    """Type of knowledge entry."""

    ISSUE = "issue"
    PATTERN = "pattern"
    LEARNING = "learning"
    METRIC = "metric"
    ARCHITECTURE = "architecture"


class Severity(Enum):
    """Severity level for issues."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EntryStatus(Enum):
    """Lifecycle status of knowledge entry."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


@dataclass
class KnowledgeEntry:
    """
    A knowledge entry in the Context Codex.

    Represents issues, patterns, learnings, metrics, or architectural knowledge.
    """

    id: str
    type: KnowledgeType
    category: str
    title: str
    description: Optional[str] = None

    # Priority/importance
    severity: Optional[Severity] = None
    confidence: float = 1.0  # 0.0-1.0
    frequency: int = 1

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_seen_at: Optional[datetime] = None

    # Flexible metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Search/filtering
    tags: List[str] = field(default_factory=list)
    project_types: List[str] = field(default_factory=list)

    # Lifecycle
    status: EntryStatus = EntryStatus.ACTIVE
    superseded_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "type": self.type.value,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value if self.severity else None,
            "confidence": self.confidence,
            "frequency": self.frequency,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat()
            if self.last_seen_at
            else None,
            "metadata_json": json.dumps(self.metadata),
            "tags": ",".join(self.tags),
            "project_types": ",".join(self.project_types),
            "status": self.status.value,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        """Create from dictionary loaded from database."""
        return cls(
            id=data["id"],
            type=KnowledgeType(data["type"]),
            category=data["category"],
            title=data["title"],
            description=data.get("description"),
            severity=Severity(data["severity"]) if data.get("severity") else None,
            confidence=data.get("confidence", 1.0),
            frequency=data.get("frequency", 1),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_seen_at=datetime.fromisoformat(data["last_seen_at"])
            if data.get("last_seen_at")
            else None,
            metadata=json.loads(data.get("metadata_json", "{}")),
            tags=data.get("tags", "").split(",") if data.get("tags") else [],
            project_types=data.get("project_types", "").split(",")
            if data.get("project_types")
            else [],
            status=EntryStatus(data.get("status", "active")),
            superseded_by=data.get("superseded_by"),
        )


@dataclass
class Solution:
    """
    A solution or fix for a knowledge entry (typically an issue).
    """

    id: str
    entry_id: str

    phase: Optional[str] = None  # scout, architect, builder, test
    solution_type: str = "fix"  # fix, workaround, prevention
    description: str = ""
    code_example: Optional[str] = None

    auto_apply: bool = False
    success_rate: Optional[float] = None  # 0.0-1.0

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "phase": self.phase,
            "solution_type": self.solution_type,
            "description": self.description,
            "code_example": self.code_example,
            "auto_apply": self.auto_apply,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Solution":
        """Create from dictionary loaded from database."""
        return cls(
            id=data["id"],
            entry_id=data["entry_id"],
            phase=data.get("phase"),
            solution_type=data.get("solution_type", "fix"),
            description=data.get("description", ""),
            code_example=data.get("code_example"),
            auto_apply=bool(data.get("auto_apply", False)),
            success_rate=data.get("success_rate"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class Evidence:
    """
    Evidence or examples that support a knowledge entry.
    """

    id: str
    entry_id: str

    evidence_type: str  # symptom, root_cause, example, counter_example
    description: str
    code_snippet: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "evidence_type": self.evidence_type,
            "description": self.description,
            "code_snippet": self.code_snippet,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evidence":
        """Create from dictionary loaded from database."""
        return cls(
            id=data["id"],
            entry_id=data["entry_id"],
            evidence_type=data["evidence_type"],
            description=data["description"],
            code_snippet=data.get("code_snippet"),
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class KnowledgeRelationship:
    """Relationship between two knowledge entries."""

    id: str
    from_entry_id: str
    to_entry_id: str

    relationship_type: str  # causes, prevents, related_to, supersedes, contradicts
    strength: float = 1.0  # 0.0-1.0
    description: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "from_entry_id": self.from_entry_id,
            "to_entry_id": self.to_entry_id,
            "relationship_type": self.relationship_type,
            "strength": self.strength,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeRelationship":
        """Create from dictionary loaded from database."""
        return cls(
            id=data["id"],
            from_entry_id=data["from_entry_id"],
            to_entry_id=data["to_entry_id"],
            relationship_type=data["relationship_type"],
            strength=data.get("strength", 1.0),
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class KnowledgeProject:
    """Track which projects encountered which knowledge entries."""

    id: str
    entry_id: str

    project_path: str
    project_type: Optional[str] = None

    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    occurrence_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "project_path": self.project_path,
            "project_type": self.project_type,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "occurrence_count": self.occurrence_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeProject":
        """Create from dictionary loaded from database."""
        return cls(
            id=data["id"],
            entry_id=data["entry_id"],
            project_path=data["project_path"],
            project_type=data.get("project_type"),
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            occurrence_count=data.get("occurrence_count", 1),
        )


@dataclass
class BuildMetric:
    """Track build performance and knowledge application."""

    id: str
    job_id: Optional[str] = None

    project_path: str = ""
    project_type: Optional[str] = None

    duration_seconds: Optional[float] = None
    phase_durations: Dict[str, float] = field(default_factory=dict)

    success: bool = True
    exit_code: int = 0

    # Knowledge tracking
    patterns_applied: List[str] = field(default_factory=list)
    issues_encountered: List[str] = field(default_factory=list)
    new_learnings: List[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "project_path": self.project_path,
            "project_type": self.project_type,
            "duration_seconds": self.duration_seconds,
            "phase_durations_json": json.dumps(self.phase_durations),
            "success": self.success,
            "exit_code": self.exit_code,
            "patterns_applied": ",".join(self.patterns_applied),
            "issues_encountered": ",".join(self.issues_encountered),
            "new_learnings": ",".join(self.new_learnings),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BuildMetric":
        """Create from dictionary loaded from database."""
        return cls(
            id=data["id"],
            job_id=data.get("job_id"),
            project_path=data.get("project_path", ""),
            project_type=data.get("project_type"),
            duration_seconds=data.get("duration_seconds"),
            phase_durations=json.loads(data.get("phase_durations_json", "{}")),
            success=bool(data.get("success", True)),
            exit_code=data.get("exit_code", 0),
            patterns_applied=data.get("patterns_applied", "").split(",")
            if data.get("patterns_applied")
            else [],
            issues_encountered=data.get("issues_encountered", "").split(",")
            if data.get("issues_encountered")
            else [],
            new_learnings=data.get("new_learnings", "").split(",")
            if data.get("new_learnings")
            else [],
            created_at=datetime.fromisoformat(data["created_at"]),
        )

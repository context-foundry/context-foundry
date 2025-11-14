"""
Context Codex - Knowledge Management System for Context Foundry

The Context Codex is a database-backed knowledge repository that stores:
- Issues and their solutions
- Architectural patterns
- Scout learnings
- Test patterns
- Build metrics
- Relationships between knowledge entries

Replaces the file-based pattern storage with a relational database
for better performance, reliability, and advanced querying.
"""

from .models import (
    KnowledgeEntry,
    Solution,
    Evidence,
    KnowledgeRelationship,
    KnowledgeProject,
    BuildMetric,
    KnowledgeType,
    Severity,
    EntryStatus,
)
from .store import KnowledgeStore, generate_entry_id

__all__ = [
    "KnowledgeEntry",
    "Solution",
    "Evidence",
    "KnowledgeRelationship",
    "KnowledgeProject",
    "BuildMetric",
    "KnowledgeType",
    "Severity",
    "EntryStatus",
    "KnowledgeStore",
    "generate_entry_id",
]

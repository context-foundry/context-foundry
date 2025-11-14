"""
KnowledgeStore - Main API for Context Codex database operations.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import (
    KnowledgeEntry,
    Solution,
    Evidence,
)
from .schema import initialize_database


class KnowledgeStore:
    """
    Main API for Context Codex knowledge management.

    Provides CRUD operations, search, relationships, and metrics tracking
    for the knowledge database.
    """

    def __init__(self, db_path: Path):
        """
        Initialize KnowledgeStore.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL;")

        # Initialize schema
        initialize_database(self.conn)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    # ========== CRUD Operations ==========

    def add_entry(self, entry: KnowledgeEntry) -> str:
        """
        Add a knowledge entry to the database.

        Args:
            entry: KnowledgeEntry object to add

        Returns:
            Entry ID if successful

        Raises:
            sqlite3.IntegrityError if entry already exists
        """
        data = entry.to_dict()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO knowledge_entries (
                id, type, category, title, description,
                severity, confidence, frequency,
                created_at, updated_at, last_seen_at,
                metadata_json, tags, project_types,
                status, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["type"],
                data["category"],
                data["title"],
                data["description"],
                data["severity"],
                data["confidence"],
                data["frequency"],
                data["created_at"],
                data["updated_at"],
                data["last_seen_at"],
                data["metadata_json"],
                data["tags"],
                data["project_types"],
                data["status"],
                data["superseded_by"],
            ),
        )
        self.conn.commit()

        return entry.id

    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """
        Get a knowledge entry by ID.

        Args:
            entry_id: Entry ID to retrieve

        Returns:
            KnowledgeEntry object if found, None otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM knowledge_entries WHERE id = ?
            """,
            (entry_id,),
        )

        row = cursor.fetchone()
        if row:
            return KnowledgeEntry.from_dict(dict(row))
        return None

    def update_entry(self, entry_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a knowledge entry.

        Args:
            entry_id: Entry ID to update
            updates: Dictionary of fields to update

        Returns:
            True if successful, False if entry not found
        """
        if not self.get_entry(entry_id):
            return False

        # Always update updated_at timestamp
        updates["updated_at"] = datetime.now().isoformat()

        # Build SET clause dynamically
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [entry_id]

        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            UPDATE knowledge_entries
            SET {set_clause}
            WHERE id = ?
            """,
            values,
        )
        self.conn.commit()

        return True

    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete a knowledge entry (cascades to solutions and evidence).

        Args:
            entry_id: Entry ID to delete

        Returns:
            True if successful, False if entry not found
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM knowledge_entries WHERE id = ?", (entry_id,))
        self.conn.commit()

        return cursor.rowcount > 0

    def increment_frequency(self, entry_id: str) -> bool:
        """
        Increment frequency counter for an entry.

        Args:
            entry_id: Entry ID

        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE knowledge_entries
            SET frequency = frequency + 1,
                last_seen_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(), datetime.now().isoformat(), entry_id),
        )
        self.conn.commit()

        return cursor.rowcount > 0

    # ========== Search Operations ==========

    def search(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeEntry]:
        """
        Full-text search across knowledge entries.

        Args:
            query: Search query string
            filters: Optional filters (type, category, severity, status, tags)

        Returns:
            List of matching KnowledgeEntry objects
        """
        cursor = self.conn.cursor()

        # Build query with FTS5 and filters
        sql_parts = [
            """
            SELECT ke.*
            FROM knowledge_entries ke
            JOIN knowledge_fts fts ON fts.entry_id = ke.id
            WHERE fts MATCH ?
            """
        ]
        params = [query]

        # Add filters
        if filters:
            if "type" in filters:
                sql_parts.append("AND ke.type = ?")
                params.append(filters["type"])

            if "category" in filters:
                sql_parts.append("AND ke.category = ?")
                params.append(filters["category"])

            if "severity" in filters:
                sql_parts.append("AND ke.severity = ?")
                params.append(filters["severity"])

            if "status" in filters:
                sql_parts.append("AND ke.status = ?")
                params.append(filters["status"])

            if "tags" in filters:
                # Tag search (contains any of the tags)
                tag_conditions = " OR ".join(
                    ["ke.tags LIKE ?" for _ in filters["tags"]]
                )
                sql_parts.append(f"AND ({tag_conditions})")
                params.extend([f"%{tag}%" for tag in filters["tags"]])

        sql_parts.append("ORDER BY ke.frequency DESC, ke.updated_at DESC")

        cursor.execute(" ".join(sql_parts), params)

        results = []
        for row in cursor.fetchall():
            results.append(KnowledgeEntry.from_dict(dict(row)))

        return results

    def search_by_type(
        self, entry_type: str, category: Optional[str] = None, limit: int = 100
    ) -> List[KnowledgeEntry]:
        """
        Search entries by type and optional category.

        Args:
            entry_type: Type of entry (issue, pattern, learning, etc.)
            category: Optional category filter
            limit: Maximum results to return

        Returns:
            List of KnowledgeEntry objects
        """
        cursor = self.conn.cursor()

        if category:
            cursor.execute(
                """
                SELECT * FROM knowledge_entries
                WHERE type = ? AND category = ? AND status = 'active'
                ORDER BY frequency DESC, updated_at DESC
                LIMIT ?
                """,
                (entry_type, category, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM knowledge_entries
                WHERE type = ? AND status = 'active'
                ORDER BY frequency DESC, updated_at DESC
                LIMIT ?
                """,
                (entry_type, limit),
            )

        results = []
        for row in cursor.fetchall():
            results.append(KnowledgeEntry.from_dict(dict(row)))

        return results

    def search_by_tags(
        self, tags: List[str], match_all: bool = False
    ) -> List[KnowledgeEntry]:
        """
        Search entries by tags.

        Args:
            tags: List of tags to search for
            match_all: If True, entry must have all tags. If False, any tag matches.

        Returns:
            List of KnowledgeEntry objects
        """
        cursor = self.conn.cursor()

        if match_all:
            # Entry must contain all tags
            conditions = " AND ".join(["tags LIKE ?" for _ in tags])
            params = [f"%{tag}%" for tag in tags]
        else:
            # Entry can contain any tag
            conditions = " OR ".join(["tags LIKE ?" for _ in tags])
            params = [f"%{tag}%" for tag in tags]

        cursor.execute(
            f"""
            SELECT * FROM knowledge_entries
            WHERE ({conditions}) AND status = 'active'
            ORDER BY frequency DESC
            """,
            params,
        )

        results = []
        for row in cursor.fetchall():
            results.append(KnowledgeEntry.from_dict(dict(row)))

        return results

    # ========== Solutions ==========

    def add_solution(self, solution: Solution) -> str:
        """
        Add a solution for a knowledge entry.

        Args:
            solution: Solution object to add

        Returns:
            Solution ID
        """
        data = solution.to_dict()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO solutions (
                id, entry_id, phase, solution_type, description,
                code_example, auto_apply, success_rate, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["entry_id"],
                data["phase"],
                data["solution_type"],
                data["description"],
                data["code_example"],
                data["auto_apply"],
                data["success_rate"],
                data["created_at"],
            ),
        )
        self.conn.commit()

        return solution.id

    def get_solutions(
        self, entry_id: str, auto_apply_only: bool = False
    ) -> List[Solution]:
        """
        Get solutions for a knowledge entry.

        Args:
            entry_id: Entry ID
            auto_apply_only: If True, only return auto-applicable solutions

        Returns:
            List of Solution objects
        """
        cursor = self.conn.cursor()

        if auto_apply_only:
            cursor.execute(
                """
                SELECT * FROM solutions
                WHERE entry_id = ? AND auto_apply = TRUE
                ORDER BY success_rate DESC NULLS LAST
                """,
                (entry_id,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM solutions
                WHERE entry_id = ?
                ORDER BY phase, solution_type
                """,
                (entry_id,),
            )

        results = []
        for row in cursor.fetchall():
            results.append(Solution.from_dict(dict(row)))

        return results

    # ========== Evidence ==========

    def add_evidence(self, evidence: Evidence) -> str:
        """
        Add evidence for a knowledge entry.

        Args:
            evidence: Evidence object to add

        Returns:
            Evidence ID
        """
        data = evidence.to_dict()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO evidence (
                id, entry_id, evidence_type, description,
                code_snippet, file_path, line_number, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["entry_id"],
                data["evidence_type"],
                data["description"],
                data["code_snippet"],
                data["file_path"],
                data["line_number"],
                data["created_at"],
            ),
        )
        self.conn.commit()

        return evidence.id

    def get_evidence(self, entry_id: str) -> List[Evidence]:
        """
        Get evidence for a knowledge entry.

        Args:
            entry_id: Entry ID

        Returns:
            List of Evidence objects
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM evidence
            WHERE entry_id = ?
            ORDER BY evidence_type, created_at
            """,
            (entry_id,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(Evidence.from_dict(dict(row)))

        return results

    # ========== Relationships ==========

    def add_relationship(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str,
        strength: float = 1.0,
        description: Optional[str] = None,
    ) -> str:
        """
        Add a relationship between two knowledge entries.

        Args:
            from_id: Source entry ID
            to_id: Target entry ID
            relationship_type: Type of relationship (causes, prevents, related_to, etc.)
            strength: Strength of relationship (0.0-1.0)
            description: Optional description

        Returns:
            Relationship ID
        """
        rel_id = str(uuid.uuid4())

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO knowledge_relationships (
                    id, from_entry_id, to_entry_id, relationship_type,
                    strength, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rel_id,
                    from_id,
                    to_id,
                    relationship_type,
                    strength,
                    description,
                    datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
            return rel_id
        except sqlite3.IntegrityError:
            # Relationship already exists (UNIQUE constraint)
            return ""

    def get_related(
        self, entry_id: str, relationship_type: Optional[str] = None
    ) -> List[KnowledgeEntry]:
        """
        Get related knowledge entries.

        Args:
            entry_id: Entry ID
            relationship_type: Optional filter by relationship type

        Returns:
            List of related KnowledgeEntry objects
        """
        cursor = self.conn.cursor()

        if relationship_type:
            cursor.execute(
                """
                SELECT ke.*
                FROM knowledge_entries ke
                JOIN knowledge_relationships kr ON kr.to_entry_id = ke.id
                WHERE kr.from_entry_id = ? AND kr.relationship_type = ?
                ORDER BY kr.strength DESC
                """,
                (entry_id, relationship_type),
            )
        else:
            cursor.execute(
                """
                SELECT ke.*, kr.relationship_type, kr.strength
                FROM knowledge_entries ke
                JOIN knowledge_relationships kr ON kr.to_entry_id = ke.id
                WHERE kr.from_entry_id = ?
                ORDER BY kr.strength DESC
                """,
                (entry_id,),
            )

        results = []
        for row in cursor.fetchall():
            results.append(KnowledgeEntry.from_dict(dict(row)))

        return results

    # ========== Statistics ==========

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Context Codex statistics.

        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()

        # Total entries by type
        cursor.execute(
            """
            SELECT type, COUNT(*) as count
            FROM knowledge_entries
            WHERE status = 'active'
            GROUP BY type
            """
        )
        entries_by_type = {row["type"]: row["count"] for row in cursor.fetchall()}

        # Total solutions
        cursor.execute("SELECT COUNT(*) as count FROM solutions")
        total_solutions = cursor.fetchone()["count"]

        # Most frequent issues
        cursor.execute(
            """
            SELECT id, title, frequency
            FROM knowledge_entries
            WHERE type = 'issue' AND status = 'active'
            ORDER BY frequency DESC
            LIMIT 10
            """
        )
        top_issues = [
            {"id": row["id"], "title": row["title"], "frequency": row["frequency"]}
            for row in cursor.fetchall()
        ]

        return {
            "total_entries": sum(entries_by_type.values()),
            "entries_by_type": entries_by_type,
            "total_solutions": total_solutions,
            "top_issues": top_issues,
        }


def generate_entry_id(entry_type: str) -> str:
    """
    Generate a unique entry ID.

    Args:
        entry_type: Type of entry (issue, pattern, learning, etc.)

    Returns:
        Unique ID string
    """
    prefix_map = {
        "issue": "iss",
        "pattern": "pat",
        "learning": "lrn",
        "metric": "met",
        "architecture": "arch",
    }

    prefix = prefix_map.get(entry_type, "ent")
    unique_id = str(uuid.uuid4())[:8]

    return f"{prefix}-{unique_id}"

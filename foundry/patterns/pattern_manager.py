#!/usr/bin/env python3
"""
Pattern Library Manager
Central pattern library management with semantic search and tracking.
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Suppress HuggingFace tokenizers parallelism warning
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import numpy as np
from sentence_transformers import SentenceTransformer


class PatternLibrary:
    """Central pattern library with semantic search and effectiveness tracking."""

    def __init__(self, db_path: str = "foundry/patterns/patterns.db"):
        """Initialize pattern library.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db = sqlite3.connect(str(self.db_path))
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            language TEXT,
            framework TEXT,
            usage_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            avg_rating REAL DEFAULT 0.0,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pattern_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id INTEGER,
            session_id TEXT,
            task_id TEXT,
            rating INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pattern_id) REFERENCES patterns(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            project_name TEXT,
            completion_rate REAL,
            metrics_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_patterns_language ON patterns(language);
        CREATE INDEX IF NOT EXISTS idx_patterns_framework ON patterns(framework);
        CREATE INDEX IF NOT EXISTS idx_pattern_usage_session ON pattern_usage(session_id);
        """

        self.db.executescript(schema_sql)
        self.db.commit()

    def extract_pattern(self, code: str, metadata: Dict) -> int:
        """Extract and store a new pattern.

        Args:
            code: Source code for the pattern
            metadata: Pattern metadata (description, tags, language, framework)

        Returns:
            Pattern ID
        """
        # Generate embedding
        embedding = self.model.encode(code)

        # Store in database
        cursor = self.db.execute(
            """INSERT INTO patterns
               (code, description, tags, language, framework, embedding)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                code,
                metadata.get('description', ''),
                json.dumps(metadata.get('tags', [])),
                metadata.get('language', ''),
                metadata.get('framework', ''),
                embedding.tobytes()
            )
        )

        self.db.commit()
        return cursor.lastrowid

    def search_patterns(
        self,
        query: str,
        limit: int = 5,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        min_relevance: float = 0.0
    ) -> List[Tuple[int, str, str, float]]:
        """Semantic search for relevant patterns.

        Args:
            query: Search query
            limit: Maximum number of results
            language: Filter by programming language
            framework: Filter by framework
            min_relevance: Minimum similarity threshold (0-1)

        Returns:
            List of (pattern_id, code, description, similarity) tuples
        """
        # Encode query
        query_embedding = self.model.encode(query)

        # Build SQL query with filters
        sql = "SELECT id, code, description, embedding FROM patterns WHERE 1=1"
        params = []

        if language:
            sql += " AND language = ?"
            params.append(language)

        if framework:
            sql += " AND framework = ?"
            params.append(framework)

        # Get all matching patterns with embeddings
        patterns = self.db.execute(sql, params).fetchall()

        # Calculate cosine similarity
        similarities = []
        for p_id, code, desc, emb_bytes in patterns:
            p_embedding = np.frombuffer(emb_bytes, dtype=np.float32)

            # Cosine similarity
            similarity = np.dot(query_embedding, p_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(p_embedding)
            )

            if similarity >= min_relevance:
                similarities.append((p_id, code, desc, float(similarity)))

        # Return top N
        similarities.sort(key=lambda x: x[3], reverse=True)
        return similarities[:limit]

    def apply_pattern(self, pattern_id: int, context: str = "") -> Optional[Dict]:
        """Get pattern details for injection into prompt.

        Args:
            pattern_id: Pattern ID to retrieve
            context: Optional context for customization

        Returns:
            Pattern data with stats, or None if not found
        """
        pattern = self.db.execute(
            """SELECT code, description, usage_count, success_count, avg_rating
               FROM patterns WHERE id=?""",
            (pattern_id,)
        ).fetchone()

        if not pattern:
            return None

        code, desc, usage, success, rating = pattern
        success_rate = (success / usage * 100) if usage > 0 else 0

        return {
            'id': pattern_id,
            'code': code,
            'description': desc,
            'success_rate': success_rate,
            'usage_count': usage,
            'avg_rating': rating
        }

    def rate_pattern(self, pattern_id: int, rating: int, session_id: str, task_id: str = ""):
        """Track pattern effectiveness.

        Args:
            pattern_id: Pattern ID
            rating: Rating (1-5)
            session_id: Session identifier
            task_id: Optional task identifier
        """
        # Get current stats
        current = self.db.execute(
            "SELECT usage_count, avg_rating FROM patterns WHERE id = ?",
            (pattern_id,)
        ).fetchone()

        if not current:
            return

        usage_count, avg_rating = current

        # Update pattern stats
        new_usage = usage_count + 1
        new_avg_rating = (avg_rating * usage_count + rating) / new_usage
        new_success = 1 if rating >= 4 else 0

        self.db.execute(
            """UPDATE patterns
               SET usage_count = usage_count + 1,
                   success_count = success_count + ?,
                   avg_rating = ?
               WHERE id = ?""",
            (new_success, new_avg_rating, pattern_id)
        )

        # Record usage
        self.db.execute(
            """INSERT INTO pattern_usage (pattern_id, session_id, task_id, rating)
               VALUES (?, ?, ?, ?)""",
            (pattern_id, session_id, task_id, rating)
        )

        self.db.commit()

    def get_top_patterns(self, limit: int = 10, min_usage: int = 2) -> List[Dict]:
        """Get top-rated patterns.

        Args:
            limit: Maximum number of patterns
            min_usage: Minimum usage count threshold

        Returns:
            List of pattern data dictionaries
        """
        patterns = self.db.execute(
            """SELECT id, code, description, usage_count, success_count, avg_rating
               FROM patterns
               WHERE usage_count >= ?
               ORDER BY avg_rating DESC, success_count DESC
               LIMIT ?""",
            (min_usage, limit)
        ).fetchall()

        result = []
        for p_id, code, desc, usage, success, rating in patterns:
            success_rate = (success / usage * 100) if usage > 0 else 0
            result.append({
                'id': p_id,
                'code': code,
                'description': desc,
                'usage_count': usage,
                'success_rate': success_rate,
                'avg_rating': rating
            })

        return result

    def get_pattern_stats(self) -> Dict:
        """Get library statistics.

        Returns:
            Statistics dictionary
        """
        total_patterns = self.db.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
        total_usage = self.db.execute("SELECT COUNT(*) FROM pattern_usage").fetchone()[0]

        avg_rating = self.db.execute(
            "SELECT AVG(avg_rating) FROM patterns WHERE usage_count > 0"
        ).fetchone()[0] or 0.0

        by_language = self.db.execute(
            """SELECT language, COUNT(*) as count
               FROM patterns
               GROUP BY language
               ORDER BY count DESC"""
        ).fetchall()

        return {
            'total_patterns': total_patterns,
            'total_usage': total_usage,
            'avg_rating': avg_rating,
            'by_language': dict(by_language)
        }

    def close(self):
        """Close database connection."""
        self.db.close()


if __name__ == "__main__":
    # Test pattern library
    print("Initializing Pattern Library...")
    lib = PatternLibrary()

    # Add sample pattern
    sample_code = """
def validate_email(email: str) -> bool:
    \"\"\"Validate email address format.\"\"\"
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
"""

    pattern_id = lib.extract_pattern(sample_code, {
        'description': 'Email validation function',
        'tags': ['validation', 'regex', 'email'],
        'language': 'python',
        'framework': ''
    })

    print(f"✓ Added pattern #{pattern_id}")

    # Search for patterns
    results = lib.search_patterns("validate email address")
    print(f"\n✓ Search results: {len(results)}")
    for p_id, code, desc, similarity in results:
        print(f"  Pattern #{p_id}: {desc} (similarity: {similarity:.2f})")

    # Rate pattern
    lib.rate_pattern(pattern_id, rating=5, session_id="test_session")
    print(f"\n✓ Rated pattern #{pattern_id}")

    # Get stats
    stats = lib.get_pattern_stats()
    print(f"\n✓ Library stats:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Total usage: {stats['total_usage']}")
    print(f"  Avg rating: {stats['avg_rating']:.2f}")

    lib.close()
    print("\n✅ Pattern Library test complete!")

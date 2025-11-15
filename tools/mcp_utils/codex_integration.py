"""
Codex Integration - Direct database access for pushing learnings

This module provides functions for the daemon to push learnings
directly to the Context Codex database without going through MCP.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import hashlib


def get_codex_db_path() -> Path:
    """Get the path to the Context Codex database"""
    codex_db = Path.home() / ".context-foundry" / "codex" / "knowledge.db"
    codex_db.parent.mkdir(parents=True, exist_ok=True)
    return codex_db


def init_codex_db():
    """Initialize Context Codex database schema if it doesn't exist"""
    db_path = get_codex_db_path()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Create knowledge entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                severity TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                times_prevented INTEGER DEFAULT 0
            )
        """)

        # Create tags table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entry_tags (
                entry_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (entry_id, tag),
                FOREIGN KEY (entry_id) REFERENCES knowledge_entries(id)
            )
        """)

        # Create project types table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entry_project_types (
                entry_id TEXT NOT NULL,
                project_type TEXT NOT NULL,
                PRIMARY KEY (entry_id, project_type),
                FOREIGN KEY (entry_id) REFERENCES knowledge_entries(id)
            )
        """)

        # Create solutions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entry_solutions (
                entry_id TEXT NOT NULL,
                solution_description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES knowledge_entries(id)
            )
        """)

        conn.commit()


def push_issue_to_codex(
    title: str,
    description: str,
    severity: str = "MEDIUM",
    tags: list = None,
    project_types: list = None,
    solution_description: str = None,
) -> str:
    """
    Push an issue/pattern to the Context Codex database

    Args:
        title: Issue title
        description: Detailed description
        severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
        tags: List of tags (tech stack, keywords)
        project_types: List of applicable project types
        solution_description: Optional solution description

    Returns:
        Entry ID
    """
    init_codex_db()
    db_path = get_codex_db_path()

    # Generate entry ID from title
    entry_id = "iss-" + hashlib.md5(title.encode()).hexdigest()[:12]
    now = datetime.now().isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check if entry exists
        cursor.execute(
            "SELECT id, frequency FROM knowledge_entries WHERE id = ?", (entry_id,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update frequency and timestamp
            cursor.execute(
                "UPDATE knowledge_entries SET frequency = frequency + 1, updated_at = ? WHERE id = ?",
                (now, entry_id),
            )
        else:
            # Insert new entry
            cursor.execute(
                """
                INSERT INTO knowledge_entries
                (id, entry_type, title, description, severity, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (entry_id, "issue", title, description, severity, now, now),
            )

            # Insert tags
            if tags:
                for tag in tags:
                    cursor.execute(
                        "INSERT OR IGNORE INTO entry_tags (entry_id, tag) VALUES (?, ?)",
                        (entry_id, tag),
                    )

            # Insert project types
            if project_types:
                for pt in project_types:
                    cursor.execute(
                        "INSERT OR IGNORE INTO entry_project_types (entry_id, project_type) VALUES (?, ?)",
                        (entry_id, pt),
                    )

            # Insert solution if provided
            if solution_description:
                cursor.execute(
                    "INSERT INTO entry_solutions (entry_id, solution_description, created_at) VALUES (?, ?, ?)",
                    (entry_id, solution_description, now),
                )

        conn.commit()

    return entry_id

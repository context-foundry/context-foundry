"""
SQL schema for Context Codex database.
"""

# Main knowledge entries table
KNOWLEDGE_ENTRIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    category TEXT,
    title TEXT NOT NULL,
    description TEXT,

    -- Priority/importance
    severity TEXT,
    confidence REAL DEFAULT 1.0,
    frequency INTEGER DEFAULT 1,

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_seen_at TEXT,

    -- Flexible metadata
    metadata_json TEXT,

    -- Search/filtering
    tags TEXT,
    project_types TEXT,

    -- Lifecycle management
    status TEXT DEFAULT 'active',
    superseded_by TEXT,

    FOREIGN KEY(superseded_by) REFERENCES knowledge_entries(id)
);
"""

# Indexes for knowledge_entries
KNOWLEDGE_ENTRIES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_entries(type);
CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_entries(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_severity ON knowledge_entries(severity);
CREATE INDEX IF NOT EXISTS idx_knowledge_frequency ON knowledge_entries(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_entries(status);
CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge_entries(created_at DESC);
"""

# Solutions table
SOLUTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS solutions (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,

    phase TEXT,
    solution_type TEXT,
    description TEXT NOT NULL,
    code_example TEXT,

    auto_apply BOOLEAN DEFAULT FALSE,
    success_rate REAL,

    created_at TEXT NOT NULL,

    FOREIGN KEY(entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE
);
"""

SOLUTIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_solutions_entry ON solutions(entry_id);
CREATE INDEX IF NOT EXISTS idx_solutions_auto_apply ON solutions(auto_apply);
CREATE INDEX IF NOT EXISTS idx_solutions_phase ON solutions(phase);
"""

# Evidence table
EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,

    evidence_type TEXT,
    description TEXT NOT NULL,
    code_snippet TEXT,
    file_path TEXT,
    line_number INTEGER,

    created_at TEXT NOT NULL,

    FOREIGN KEY(entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE
);
"""

EVIDENCE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_evidence_entry ON evidence(entry_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence(evidence_type);
"""

# Knowledge projects table
KNOWLEDGE_PROJECTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_projects (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,

    project_path TEXT NOT NULL,
    project_type TEXT,

    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    occurrence_count INTEGER DEFAULT 1,

    FOREIGN KEY(entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE
);
"""

KNOWLEDGE_PROJECTS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_projects_entry ON knowledge_projects(entry_id);
CREATE INDEX IF NOT EXISTS idx_projects_path ON knowledge_projects(project_path);
CREATE INDEX IF NOT EXISTS idx_projects_last_seen ON knowledge_projects(last_seen DESC);
"""

# Knowledge relationships table
KNOWLEDGE_RELATIONSHIPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_relationships (
    id TEXT PRIMARY KEY,
    from_entry_id TEXT NOT NULL,
    to_entry_id TEXT NOT NULL,

    relationship_type TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    description TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY(from_entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE,
    FOREIGN KEY(to_entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE,

    UNIQUE(from_entry_id, to_entry_id, relationship_type)
);
"""

KNOWLEDGE_RELATIONSHIPS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_relationships_from ON knowledge_relationships(from_entry_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON knowledge_relationships(to_entry_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON knowledge_relationships(relationship_type);
"""

# Build metrics table
BUILD_METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS build_metrics (
    id TEXT PRIMARY KEY,
    job_id TEXT,

    project_path TEXT NOT NULL,
    project_type TEXT,

    duration_seconds REAL,
    phase_durations_json TEXT,

    success BOOLEAN,
    exit_code INTEGER,

    -- Knowledge tracking
    patterns_applied TEXT,
    issues_encountered TEXT,
    new_learnings TEXT,

    created_at TEXT NOT NULL
);
"""

BUILD_METRICS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_metrics_project ON build_metrics(project_path);
CREATE INDEX IF NOT EXISTS idx_metrics_success ON build_metrics(success);
CREATE INDEX IF NOT EXISTS idx_metrics_created ON build_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_job ON build_metrics(job_id);
"""

# Full-text search table
KNOWLEDGE_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    entry_id UNINDEXED,
    title,
    description,
    tags,
    content='knowledge_entries',
    content_rowid='rowid'
);
"""

# FTS triggers to keep in sync
KNOWLEDGE_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS knowledge_fts_insert AFTER INSERT ON knowledge_entries BEGIN
  INSERT INTO knowledge_fts(rowid, entry_id, title, description, tags)
  VALUES (new.rowid, new.id, new.title, new.description, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_fts_delete AFTER DELETE ON knowledge_entries BEGIN
  DELETE FROM knowledge_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS knowledge_fts_update AFTER UPDATE ON knowledge_entries BEGIN
  DELETE FROM knowledge_fts WHERE rowid = old.rowid;
  INSERT INTO knowledge_fts(rowid, entry_id, title, description, tags)
  VALUES (new.rowid, new.id, new.title, new.description, new.tags);
END;
"""

# Combined schema for initialization
ALL_SCHEMAS = [
    KNOWLEDGE_ENTRIES_SCHEMA,
    KNOWLEDGE_ENTRIES_INDEXES,
    SOLUTIONS_SCHEMA,
    SOLUTIONS_INDEXES,
    EVIDENCE_SCHEMA,
    EVIDENCE_INDEXES,
    KNOWLEDGE_PROJECTS_SCHEMA,
    KNOWLEDGE_PROJECTS_INDEXES,
    KNOWLEDGE_RELATIONSHIPS_SCHEMA,
    KNOWLEDGE_RELATIONSHIPS_INDEXES,
    BUILD_METRICS_SCHEMA,
    BUILD_METRICS_INDEXES,
    KNOWLEDGE_FTS_SCHEMA,
    KNOWLEDGE_FTS_TRIGGERS,
]


def initialize_database(conn):
    """
    Initialize Context Codex database with all tables and indexes.

    Args:
        conn: sqlite3 connection object

    Returns:
        True if successful, False otherwise
    """
    try:
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Execute all schema statements
        for schema in ALL_SCHEMAS:
            # Split multiple statements if present
            for statement in schema.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)

        conn.commit()
        return True

    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
        return False

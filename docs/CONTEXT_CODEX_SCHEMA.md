# Context Codex: Database Schema Design

## Overview

**Context Codex** replaces the file-based pattern storage with a relational database for better querying, relationships, and scalability.

**Database:** SQLite (same as jobs.db)
**Location:** `~/.context-foundry/codex.db`

---

## Core Tables

### 1. knowledge_entries

Primary table for all knowledge types (issues, patterns, learnings, metrics).

```sql
CREATE TABLE knowledge_entries (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'issue', 'pattern', 'learning', 'metric', 'architecture'
    category TEXT,  -- 'common-issue', 'scout-learning', 'test-pattern', 'flowise-pattern', etc.
    title TEXT NOT NULL,
    description TEXT,

    -- Priority/importance
    severity TEXT,  -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL' (for issues)
    confidence REAL DEFAULT 1.0,  -- 0.0-1.0: how confident are we?
    frequency INTEGER DEFAULT 1,  -- how many times seen

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_seen_at TEXT,

    -- Flexible metadata (type-specific fields)
    metadata_json TEXT,  -- JSON for custom fields per type

    -- Search/filtering
    tags TEXT,  -- comma-separated: 'docker,python,flask'
    project_types TEXT,  -- 'python,nodejs,docker-compose'

    -- Lifecycle management
    status TEXT DEFAULT 'active',  -- 'active', 'deprecated', 'superseded'
    superseded_by TEXT,  -- ID of entry that replaces this one

    FOREIGN KEY(superseded_by) REFERENCES knowledge_entries(id)
);

CREATE INDEX idx_knowledge_type ON knowledge_entries(type);
CREATE INDEX idx_knowledge_category ON knowledge_entries(category);
CREATE INDEX idx_knowledge_severity ON knowledge_entries(severity);
CREATE INDEX idx_knowledge_frequency ON knowledge_entries(frequency DESC);
CREATE INDEX idx_knowledge_status ON knowledge_entries(status);
```

**Example Entry (Issue):**
```json
{
  "id": "issue-001",
  "type": "issue",
  "category": "common-issue",
  "title": "Docker volume persists old database config",
  "description": "Changed POSTGRES_DB env var but database still uses old name",
  "severity": "MEDIUM",
  "confidence": 0.95,
  "frequency": 12,
  "tags": "docker,postgres,volumes",
  "project_types": "docker-compose,python",
  "status": "active"
}
```

---

### 2. solutions

Solutions/fixes for issues. One issue can have multiple solutions.

```sql
CREATE TABLE solutions (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,

    phase TEXT,  -- 'scout', 'architect', 'builder', 'test'
    solution_type TEXT,  -- 'fix', 'workaround', 'prevention'
    description TEXT NOT NULL,
    code_example TEXT,

    auto_apply BOOLEAN DEFAULT FALSE,
    success_rate REAL,  -- 0.0-1.0: how often does this work?

    created_at TEXT NOT NULL,

    FOREIGN KEY(entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE
);

CREATE INDEX idx_solutions_entry ON solutions(entry_id);
CREATE INDEX idx_solutions_auto_apply ON solutions(auto_apply);
```

**Example Solution:**
```json
{
  "id": "sol-001-a",
  "entry_id": "issue-001",
  "phase": "builder",
  "solution_type": "fix",
  "description": "Remove Docker volumes before recreating with new config",
  "code_example": "docker-compose down -v\ndocker-compose up -d",
  "auto_apply": false,
  "success_rate": 0.98
}
```

---

### 3. evidence

Evidence/examples that support knowledge entries.

```sql
CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,

    evidence_type TEXT,  -- 'symptom', 'root_cause', 'example', 'counter_example'
    description TEXT NOT NULL,
    code_snippet TEXT,
    file_path TEXT,
    line_number INTEGER,

    created_at TEXT NOT NULL,

    FOREIGN KEY(entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE
);

CREATE INDEX idx_evidence_entry ON evidence(entry_id);
```

**Example Evidence:**
```json
{
  "id": "ev-001-a",
  "entry_id": "issue-001",
  "evidence_type": "symptom",
  "description": "Changed POSTGRES_DB env var but database still tries to connect to old name",
  "code_snippet": "Error: database \"old_db\" does not exist"
}
```

---

### 4. knowledge_projects

Track which projects encountered which knowledge.

```sql
CREATE TABLE knowledge_projects (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,

    project_path TEXT NOT NULL,
    project_type TEXT,

    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    occurrence_count INTEGER DEFAULT 1,

    FOREIGN KEY(entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE
);

CREATE INDEX idx_projects_entry ON knowledge_projects(entry_id);
CREATE INDEX idx_projects_path ON knowledge_projects(project_path);
```

**Use Case:** "Which projects have encountered the Docker volume issue?"

---

### 5. knowledge_relationships

Relationships between knowledge entries.

```sql
CREATE TABLE knowledge_relationships (
    id TEXT PRIMARY KEY,
    from_entry_id TEXT NOT NULL,
    to_entry_id TEXT NOT NULL,

    relationship_type TEXT NOT NULL,  -- 'causes', 'prevents', 'related_to', 'supersedes', 'contradicts'
    strength REAL DEFAULT 1.0,  -- 0.0-1.0: confidence in relationship
    description TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY(from_entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE,
    FOREIGN KEY(to_entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE,

    UNIQUE(from_entry_id, to_entry_id, relationship_type)
);

CREATE INDEX idx_relationships_from ON knowledge_relationships(from_entry_id);
CREATE INDEX idx_relationships_to ON knowledge_relationships(to_entry_id);
```

**Example Relationship:**
```json
{
  "from_entry_id": "pattern-docker-volumes",
  "to_entry_id": "issue-001",
  "relationship_type": "prevents",
  "strength": 0.95,
  "description": "Using named volumes prevents this config issue"
}
```

**Use Case:** "What patterns prevent Docker volume issues?"

---

### 6. build_metrics

Track build performance and knowledge application.

```sql
CREATE TABLE build_metrics (
    id TEXT PRIMARY KEY,
    job_id TEXT,  -- Link to jobs.db if applicable

    project_path TEXT NOT NULL,
    project_type TEXT,

    duration_seconds REAL,
    phase_durations_json TEXT,  -- JSON: {"scout": 30, "architect": 20, ...}

    success BOOLEAN,
    exit_code INTEGER,

    -- Knowledge tracking
    patterns_applied TEXT,  -- Comma-separated IDs of patterns applied
    issues_encountered TEXT,  -- Comma-separated IDs of issues encountered
    new_learnings TEXT,  -- Comma-separated IDs of new knowledge generated

    created_at TEXT NOT NULL
);

CREATE INDEX idx_metrics_project ON build_metrics(project_path);
CREATE INDEX idx_metrics_success ON build_metrics(success);
CREATE INDEX idx_metrics_created ON build_metrics(created_at);
```

**Use Case:** "What's the average build time for Flask projects?" or "How often is pattern X applied?"

---

### 7. knowledge_fts (Full-Text Search)

```sql
CREATE VIRTUAL TABLE knowledge_fts USING fts5(
    entry_id UNINDEXED,
    title,
    description,
    tags,
    content='knowledge_entries',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER knowledge_fts_insert AFTER INSERT ON knowledge_entries BEGIN
  INSERT INTO knowledge_fts(rowid, entry_id, title, description, tags)
  VALUES (new.rowid, new.id, new.title, new.description, new.tags);
END;

CREATE TRIGGER knowledge_fts_delete AFTER DELETE ON knowledge_entries BEGIN
  DELETE FROM knowledge_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER knowledge_fts_update AFTER UPDATE ON knowledge_entries BEGIN
  DELETE FROM knowledge_fts WHERE rowid = old.rowid;
  INSERT INTO knowledge_fts(rowid, entry_id, title, description, tags)
  VALUES (new.rowid, new.id, new.title, new.description, new.tags);
END;
```

**Use Case:** Fast text search across all knowledge: `SELECT * FROM knowledge_fts WHERE knowledge_fts MATCH 'docker volumes'`

---

## API Layer

### KnowledgeStore Class

```python
class KnowledgeStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

    # CRUD
    def add_entry(self, entry: KnowledgeEntry) -> str
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]
    def update_entry(self, entry_id: str, updates: dict) -> bool
    def delete_entry(self, entry_id: str) -> bool

    # Search
    def search(self, query: str, filters: dict = None) -> List[KnowledgeEntry]
    def search_by_tags(self, tags: List[str]) -> List[KnowledgeEntry]
    def search_by_type(self, type: str, category: str = None) -> List[KnowledgeEntry]

    # Relationships
    def get_related(self, entry_id: str, relationship_type: str = None) -> List[KnowledgeEntry]
    def add_relationship(self, from_id: str, to_id: str, rel_type: str) -> str

    # Solutions
    def add_solution(self, entry_id: str, solution: Solution) -> str
    def get_solutions(self, entry_id: str, auto_apply_only: bool = False) -> List[Solution]

    # Metrics
    def track_build(self, metrics: BuildMetrics) -> str
    def get_metrics(self, filters: dict = None) -> List[BuildMetrics]

    # Lifecycle
    def increment_frequency(self, entry_id: str) -> bool
    def mark_superseded(self, old_id: str, new_id: str) -> bool
```

---

## Migration from JSON

### Migration Script

```python
def migrate_patterns_to_codex():
    """
    Migrate existing JSON patterns to Context Codex database.

    Converts:
    - common-issues.json → knowledge_entries (type='issue') + solutions + evidence
    - scout-learnings.json → knowledge_entries (type='learning')
    - architecture-patterns.json → knowledge_entries (type='architecture')
    - test-patterns.json → knowledge_entries (type='pattern', category='test')
    - mcp-server-patterns.json → knowledge_entries (type='pattern', category='mcp')
    """

    # 1. Parse common-issues.json
    for pattern in common_issues['patterns']:
        entry = KnowledgeEntry(
            type='issue',
            category='common-issue',
            title=pattern['issue'],
            severity=pattern['severity'],
            tags=','.join(pattern.get('project_types', [])),
            metadata_json=json.dumps(pattern.get('evidence', {}))
        )
        store.add_entry(entry)

        # Add solutions
        for phase in ['scout', 'architect', 'builder']:
            if phase in pattern.get('solution', {}):
                store.add_solution(entry.id, Solution(
                    phase=phase,
                    description=pattern['solution'][phase],
                    auto_apply=pattern.get('auto_apply', False)
                ))

    # 2. Parse scout-learnings.json
    # ...

    # 3. Create relationships
    # ...
```

---

## Benefits Over File-Based System

### Performance
- ✅ **Indexed queries:** 100x faster for searches
- ✅ **Full-text search:** SQLite FTS5 is optimized
- ✅ **Pagination:** Efficient for large datasets
- ✅ **Joins:** Query relationships in single operation

### Reliability
- ✅ **Atomic transactions:** No partial writes
- ✅ **Concurrent access:** Multiple readers, queued writers
- ✅ **Data integrity:** Foreign key constraints
- ✅ **Backup/restore:** Single file, WAL mode

### Features
- ✅ **Relationships:** "What patterns prevent issue X?"
- ✅ **Trends:** Frequency over time
- ✅ **Confidence scoring:** How reliable is this knowledge?
- ✅ **Deprecation:** Mark old patterns as superseded
- ✅ **Cross-referencing:** Link related knowledge

### Scalability
- ✅ **No file size limits:** SQLite handles GBs
- ✅ **Efficient filtering:** WHERE clauses vs full scans
- ✅ **Indexing:** Add indexes as needed
- ✅ **Future-proof:** Can migrate to PostgreSQL later

---

## Backward Compatibility

### JSON Export/Import

Keep JSON support for:
- Git-based knowledge sharing
- Human-readable backups
- Community pattern libraries
- Version control of knowledge

```bash
# Export to JSON (for sharing/backups)
cfd codex export --type common-issues --output common-issues.json

# Import from JSON (for seeding/merging)
cfd codex import --file community-patterns.json
```

This allows:
- Sharing knowledge repos on GitHub
- Reviewing changes in pull requests
- Manual editing in text editor
- Community contributions

---

## File Layout

```
~/.context-foundry/
├── cfd/
│   ├── jobs.db          # Job queue database (existing)
│   └── logs/            # Daemon logs
├── codex.db             # NEW: Context Codex database
└── patterns/            # DEPRECATED: Old JSON files (keep for migration)
    ├── common-issues.json
    ├── scout-learnings.json
    └── ...
```

---

## Implementation Timeline

| Phase | Time | Description |
|-------|------|-------------|
| **1. Schema Creation** | 4h | Write SQL schema, test with sample data |
| **2. KnowledgeStore API** | 12h | Python API layer with CRUD, search, relationships |
| **3. Migration Script** | 8h | Parse JSON → populate database |
| **4. Update Daemon** | 4h | Replace pattern merge with Codex API calls |
| **5. Testing** | 8h | Unit tests, integration tests, benchmarks |
| **6. CLI Commands** | 4h | `cfd codex search`, `cfd codex export`, etc. |
| **7. Documentation** | 4h | Schema docs, API docs, migration guide |

**Total: ~44 hours (~1 week)**

---

## Example Queries

### "Find all Docker-related issues with HIGH severity"
```sql
SELECT * FROM knowledge_entries
WHERE type = 'issue'
  AND severity = 'HIGH'
  AND tags LIKE '%docker%'
ORDER BY frequency DESC;
```

### "What patterns prevent authentication issues?"
```sql
SELECT ke.*
FROM knowledge_entries ke
JOIN knowledge_relationships kr ON kr.from_entry_id = ke.id
JOIN knowledge_entries target ON target.id = kr.to_entry_id
WHERE target.title LIKE '%authentication%'
  AND kr.relationship_type = 'prevents'
  AND ke.type = 'pattern';
```

### "Average build time for Flask projects that applied pattern X"
```sql
SELECT AVG(duration_seconds)
FROM build_metrics
WHERE project_type LIKE '%flask%'
  AND patterns_applied LIKE '%pattern-xyz%';
```

---

## Next Steps

1. Review schema and provide feedback
2. Choose final name: "Context Codex" vs "Foundry Memory"
3. Approve migration plan
4. Implement schema + KnowledgeStore class
5. Run migration script
6. Update daemon to use Codex
7. Test and validate

**Decision needed:** Proceed with "Context Codex" name? ✅

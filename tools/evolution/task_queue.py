#!/usr/bin/env python3
"""
Task Queue Manager for CFES
SQLite-based persistent task storage with ACID guarantees
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Task type enumeration"""
    SELF_IMPROVEMENT = "self_improvement"
    CHAOS_CREATIVE = "chaos_creative"
    RESEARCH = "research"
    APPLY_PATTERN = "apply_pattern"
    VALIDATE = "validate"
    DELEGATION_BUILD = "delegation_build"
    DELEGATION_DEPLOY = "delegation_deploy"
    DELEGATION_TEST = "delegation_test"


@dataclass
class Task:
    """Task data model"""
    id: str
    type: str
    status: str
    priority: int
    params: Dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create from dictionary"""
        return cls(**data)


class TaskQueueManager:
    """SQLite-based task queue with ACID guarantees"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize task queue manager
        
        Args:
            db_path: Path to SQLite database (default: ~/.context-foundry/evolution/task_queue.db)
        """
        if db_path is None:
            home = Path.home()
            db_dir = home / ".context-foundry" / "evolution"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "task_queue.db")
        
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _migrate_schema(self):
        """Migrate existing database schema if needed"""
        try:
            # Check if tasks table exists
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
            )
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                # New database, no migration needed
                return

            # Get current schema
            cursor = self.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'")
            schema = cursor.fetchone()

            if schema and schema[0]:
                schema_sql = schema[0]

                # Check if schema has old CHECK constraint (only 5 types)
                if "delegation_build" not in schema_sql:
                    # Need to migrate - recreate table with new constraint
                    print("Migrating task_queue schema to support delegation tasks...")

                    self.conn.executescript("""
                        -- Create new table with updated schema
                        CREATE TABLE tasks_new (
                            id TEXT PRIMARY KEY,
                            type TEXT NOT NULL CHECK(type IN ('self_improvement', 'chaos_creative', 'research', 'apply_pattern', 'validate', 'delegation_build', 'delegation_deploy', 'delegation_test')),
                            status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
                            priority INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
                            params_json TEXT,
                            created_at TEXT NOT NULL,
                            started_at TEXT,
                            completed_at TEXT,
                            result_json TEXT,
                            error_message TEXT,
                            retry_count INTEGER DEFAULT 0,
                            max_retries INTEGER DEFAULT 3
                        );

                        -- Copy existing data
                        INSERT INTO tasks_new SELECT * FROM tasks;

                        -- Drop old table
                        DROP TABLE tasks;

                        -- Rename new table
                        ALTER TABLE tasks_new RENAME TO tasks;
                    """)

                    self.conn.commit()
                    print("✅ Schema migration complete")

        except Exception as e:
            print(f"Warning: Schema migration check failed: {e}")
            # Continue anyway - CREATE TABLE IF NOT EXISTS will handle new databases

    def _init_db(self):
        """Initialize database with schema"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")

        # Check if we need to migrate the schema
        self._migrate_schema()

        # Create tables
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL CHECK(type IN ('self_improvement', 'chaos_creative', 'research', 'apply_pattern', 'validate', 'delegation_build', 'delegation_deploy', 'delegation_test')),
                status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
                priority INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
                params_json TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3
            );
            
            CREATE INDEX IF NOT EXISTS idx_tasks_status_priority 
            ON tasks(status, priority DESC, created_at);
            
            CREATE INDEX IF NOT EXISTS idx_tasks_type 
            ON tasks(type);
            
            CREATE TABLE IF NOT EXISTS task_history (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                params_json TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                error_message TEXT,
                archived_at TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_history_created 
            ON task_history(created_at DESC);
            
            CREATE TABLE IF NOT EXISTS project_registry (
                path TEXT PRIMARY KEY,
                project_type TEXT NOT NULL,
                metadata_json TEXT,
                last_updated TEXT NOT NULL,
                patterns_applied TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_projects_type 
            ON project_registry(project_type);
            
            CREATE TABLE IF NOT EXISTS agent_network (
                agent_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                agent_url TEXT,
                capabilities_json TEXT,
                connection_weight REAL DEFAULT 1.0 CHECK(connection_weight BETWEEN 0 AND 10),
                last_seen TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_agents_last_seen 
            ON agent_network(last_seen DESC);
        """)
        
        self.conn.commit()
    
    def create_task(self, task_type: str, params: Dict[str, Any], priority: int = 5) -> str:
        """
        Create new task
        
        Args:
            task_type: Type of task
            params: Task parameters
            priority: Priority 1-10 (default 5)
        
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        
        self.conn.execute("""
            INSERT INTO tasks (id, type, status, priority, params_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task_id, task_type, TaskStatus.PENDING.value, priority, json.dumps(params), created_at))
        
        self.conn.commit()
        return task_id
    
    def get_next_task(self) -> Optional[Task]:
        """
        Get next pending task with locking

        Priority order:
        1. Tasks with github_issue (approved GitHub issues) - highest priority
        2. Self-generated improvement tasks (autonomous mode) - fallback

        Returns:
            Task object or None if no pending tasks
        """
        # Use transaction for atomic read-and-update
        cursor = self.conn.execute("BEGIN IMMEDIATE")

        try:
            # First, try to get GitHub-approved tasks (highest priority)
            row = self.conn.execute("""
                SELECT * FROM tasks
                WHERE status = ?
                AND params_json LIKE '%"github_issue":%'
                ORDER BY priority DESC, created_at
                LIMIT 1
            """, (TaskStatus.PENDING.value,)).fetchone()

            # If no GitHub-approved tasks, fall back to self-generated tasks
            if not row:
                row = self.conn.execute("""
                    SELECT * FROM tasks
                    WHERE status = ?
                    ORDER BY priority DESC, created_at
                    LIMIT 1
                """, (TaskStatus.PENDING.value,)).fetchone()

            if not row:
                self.conn.rollback()
                return None
            
            # Update status to running
            task_id = row['id']
            started_at = datetime.utcnow().isoformat()
            
            self.conn.execute("""
                UPDATE tasks 
                SET status = ?, started_at = ? 
                WHERE id = ?
            """, (TaskStatus.RUNNING.value, started_at, task_id))
            
            self.conn.commit()
            
            # Return task object
            return Task(
                id=row['id'],
                type=row['type'],
                status=TaskStatus.RUNNING.value,
                priority=row['priority'],
                params=json.loads(row['params_json']) if row['params_json'] else {},
                created_at=row['created_at'],
                started_at=started_at,
                completed_at=row['completed_at'],
                result=json.loads(row['result_json']) if row['result_json'] else None,
                error_message=row['error_message'],
                retry_count=row['retry_count'],
                max_retries=row['max_retries']
            )
        except Exception as e:
            self.conn.rollback()
            raise e
    
    def update_task_status(self, task_id: str, status: str, result: Optional[Dict] = None, error: Optional[str] = None):
        """
        Update task status atomically
        
        Args:
            task_id: Task ID
            status: New status
            result: Optional result data
            error: Optional error message
        """
        completed_at = datetime.utcnow().isoformat() if status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value] else None
        
        self.conn.execute("""
            UPDATE tasks 
            SET status = ?, completed_at = ?, result_json = ?, error_message = ?
            WHERE id = ?
        """, (status, completed_at, json.dumps(result) if result else None, error, task_id))
        
        self.conn.commit()
    
    def retry_task(self, task_id: str):
        """
        Increment retry count and reset to pending
        
        Args:
            task_id: Task ID
        """
        self.conn.execute("""
            UPDATE tasks 
            SET status = ?, retry_count = retry_count + 1, started_at = NULL
            WHERE id = ?
        """, (TaskStatus.PENDING.value, task_id))
        
        self.conn.commit()
    
    def should_retry(self, task: Task) -> bool:
        """Check if task should be retried"""
        return task.retry_count < task.max_retries
    
    def calculate_backoff(self, retry_count: int) -> int:
        """Calculate exponential backoff in seconds"""
        return 2 ** retry_count
    
    def archive_old_tasks(self, days: int = 30) -> int:
        """
        Move completed/failed tasks to history

        Args:
            days: Archive tasks older than this many days

        Returns:
            Number of tasks archived
        """
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Copy to history
        self.conn.execute("""
            INSERT INTO task_history
            SELECT id, type, status, priority, params_json, created_at, started_at, completed_at, result_json, error_message, ?
            FROM tasks
            WHERE status IN (?, ?) AND completed_at < ?
        """, (datetime.utcnow().isoformat(), TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, cutoff_date))

        # Delete from tasks and get count
        cursor = self.conn.execute("""
            DELETE FROM tasks
            WHERE status IN (?, ?) AND completed_at < ?
        """, (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, cutoff_date))

        archived_count = cursor.rowcount
        self.conn.commit()

        return archived_count
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        
        if not row:
            return None
        
        return Task(
            id=row['id'],
            type=row['type'],
            status=row['status'],
            priority=row['priority'],
            params=json.loads(row['params_json']) if row['params_json'] else {},
            created_at=row['created_at'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            result=json.loads(row['result_json']) if row['result_json'] else None,
            error_message=row['error_message'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries']
        )
    
    def list_tasks(self, status: Optional[str] = None, task_type: Optional[str] = None, limit: int = 50) -> List[Task]:
        """List tasks with optional filters"""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if task_type:
            query += " AND type = ?"
            params.append(task_type)
        
        query += " ORDER BY priority DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = self.conn.execute(query, params).fetchall()
        
        tasks = []
        for row in rows:
            tasks.append(Task(
                id=row['id'],
                type=row['type'],
                status=row['status'],
                priority=row['priority'],
                params=json.loads(row['params_json']) if row['params_json'] else {},
                created_at=row['created_at'],
                started_at=row['started_at'],
                completed_at=row['completed_at'],
                result=json.loads(row['result_json']) if row['result_json'] else None,
                error_message=row['error_message'],
                retry_count=row['retry_count'],
                max_retries=row['max_retries']
            ))
        
        return tasks
    
    def count_pending(self) -> int:
        """Count pending tasks"""
        return self.conn.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (TaskStatus.PENDING.value,)).fetchone()[0]
    
    def count_completed(self) -> int:
        """Count completed tasks"""
        return self.conn.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (TaskStatus.COMPLETED.value,)).fetchone()[0]
    
    def count_failed(self) -> int:
        """Count failed tasks"""
        return self.conn.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (TaskStatus.FAILED.value,)).fetchone()[0]

    def count_running(self) -> int:
        """Count running tasks"""
        return self.conn.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (TaskStatus.RUNNING.value,)).fetchone()[0]

    def cancel_task(self, task_id: str) -> bool:
        """Cancel pending task"""
        cursor = self.conn.execute("""
            UPDATE tasks 
            SET status = ? 
            WHERE id = ? AND status = ?
        """, (TaskStatus.CANCELLED.value, task_id, TaskStatus.PENDING.value))
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Project registry methods
    
    def register_project(self, path: str, project_type: str, metadata: Dict[str, Any]):
        """Register project in registry"""
        last_updated = datetime.utcnow().isoformat()
        
        self.conn.execute("""
            INSERT OR REPLACE INTO project_registry (path, project_type, metadata_json, last_updated, patterns_applied)
            VALUES (?, ?, ?, ?, ?)
        """, (path, project_type, json.dumps(metadata), last_updated, json.dumps([])))
        
        self.conn.commit()
    
    def list_projects(self, project_type: Optional[str] = None) -> List[Dict]:
        """List projects"""
        if project_type:
            rows = self.conn.execute("SELECT * FROM project_registry WHERE project_type = ?", (project_type,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM project_registry").fetchall()
        
        projects = []
        for row in rows:
            projects.append({
                'path': row['path'],
                'project_type': row['project_type'],
                'metadata': json.loads(row['metadata_json']) if row['metadata_json'] else {},
                'last_updated': row['last_updated'],
                'patterns_applied': json.loads(row['patterns_applied']) if row['patterns_applied'] else []
            })
        
        return projects
    
    # Agent network methods
    
    def register_agent(self, name: str, url: Optional[str] = None, capabilities: Optional[List[str]] = None) -> str:
        """Register agent in network"""
        agent_id = str(uuid.uuid4())
        last_seen = datetime.utcnow().isoformat()
        
        self.conn.execute("""
            INSERT OR REPLACE INTO agent_network (agent_id, agent_name, agent_url, capabilities_json, last_seen)
            VALUES (?, ?, ?, ?, ?)
        """, (agent_id, name, url, json.dumps(capabilities or []), last_seen))
        
        self.conn.commit()
        return agent_id
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get agent info"""
        row = self.conn.execute("SELECT * FROM agent_network WHERE agent_id = ?", (agent_id,)).fetchone()
        
        if not row:
            return None
        
        return {
            'id': row['agent_id'],
            'name': row['agent_name'],
            'url': row['agent_url'],
            'capabilities': json.loads(row['capabilities_json']) if row['capabilities_json'] else [],
            'weight': row['connection_weight'],
            'last_seen': row['last_seen']
        }
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

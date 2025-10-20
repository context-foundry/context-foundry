#!/usr/bin/env python3
"""
Context Foundry Metrics Database
SQLite storage for comprehensive metrics tracking and self-improvement
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import contextmanager


class MetricsDatabase:
    """
    Persistent storage for Context Foundry metrics.

    Tracks:
    - Task execution metrics
    - Token usage
    - Latency data
    - Agent performance
    - Decision quality
    - Test iterations
    - Self-improvement indicators
    """

    def __init__(self, db_path: str = "~/.context-foundry/metrics.db"):
        """Initialize database connection."""
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tasks table - Main task tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    project_name TEXT,
                    task_description TEXT,
                    working_directory TEXT,
                    status TEXT,
                    phases_completed TEXT,
                    current_phase TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds INTEGER,
                    github_url TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Metrics table - Time-series metrics per task
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    timestamp TEXT,
                    phase TEXT,
                    token_usage INTEGER,
                    token_percentage REAL,
                    latency_ms REAL,
                    context_resets INTEGER,
                    elapsed_seconds INTEGER,
                    estimated_remaining_seconds INTEGER,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

            # Decisions table - Autonomous decision tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    timestamp TEXT,
                    phase TEXT,
                    decision_type TEXT,
                    decision_description TEXT,
                    quality_rating INTEGER,
                    difficulty_rating INTEGER,
                    is_regrettable BOOLEAN,
                    used_lessons_learned BOOLEAN,
                    pattern_ids TEXT,
                    reasoning TEXT,
                    outcome TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

            # Agent performance table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    agent_type TEXT,
                    phase TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds INTEGER,
                    success BOOLEAN,
                    issues_found INTEGER,
                    issues_fixed INTEGER,
                    files_created INTEGER,
                    files_modified INTEGER,
                    lines_of_code INTEGER,
                    tokens_used INTEGER,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

            # Test iterations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_iterations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    iteration_number INTEGER,
                    timestamp TEXT,
                    tests_run INTEGER,
                    tests_passed INTEGER,
                    tests_failed INTEGER,
                    test_output TEXT,
                    fixes_applied TEXT,
                    duration_seconds INTEGER,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

            # Pattern effectiveness table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_effectiveness (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    pattern_id TEXT,
                    pattern_type TEXT,
                    was_applied BOOLEAN,
                    prevented_issue BOOLEAN,
                    issue_description TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_task_id
                ON metrics(task_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_task_id
                ON decisions(task_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_perf_task_id
                ON agent_performance(task_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_test_iter_task_id
                ON test_iterations(task_id)
            """)

    # ============================================================================
    # Task Operations
    # ============================================================================

    def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create a new task record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (
                    task_id, project_name, task_description, working_directory,
                    status, phases_completed, current_phase, start_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_data['task_id'],
                task_data.get('project_name'),
                task_data.get('task_description'),
                task_data.get('working_directory'),
                task_data.get('status', 'running'),
                json.dumps(task_data.get('phases_completed', [])),
                task_data.get('current_phase'),
                task_data.get('start_time', datetime.now().isoformat())
            ))
        return task_data['task_id']

    def update_task(self, task_id: str, updates: Dict[str, Any]):
        """Update task record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build dynamic UPDATE query
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [task_id]

            cursor.execute(f"""
                UPDATE tasks SET {set_clause}
                WHERE task_id = ?
            """, values)

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_tasks(self, limit: int = 100) -> List[Dict]:
        """Get all tasks, most recent first."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tasks
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ============================================================================
    # Metrics Operations
    # ============================================================================

    def add_metric(self, task_id: str, metric_data: Dict[str, Any]):
        """Add a metrics data point."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metrics (
                    task_id, timestamp, phase, token_usage, token_percentage,
                    latency_ms, context_resets, elapsed_seconds, estimated_remaining_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                metric_data.get('timestamp', datetime.now().isoformat()),
                metric_data.get('phase'),
                metric_data.get('token_usage'),
                metric_data.get('token_percentage'),
                metric_data.get('latency_ms'),
                metric_data.get('context_resets', 0),
                metric_data.get('elapsed_seconds'),
                metric_data.get('estimated_remaining_seconds')
            ))

    def get_metrics(self, task_id: str) -> List[Dict]:
        """Get all metrics for a task."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM metrics
                WHERE task_id = ?
                ORDER BY timestamp ASC
            """, (task_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_metric(self, task_id: str) -> Optional[Dict]:
        """Get most recent metric for a task."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM metrics
                WHERE task_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ============================================================================
    # Decision Tracking
    # ============================================================================

    def add_decision(self, task_id: str, decision_data: Dict[str, Any]):
        """Add a decision record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decisions (
                    task_id, timestamp, phase, decision_type, decision_description,
                    quality_rating, difficulty_rating, is_regrettable,
                    used_lessons_learned, pattern_ids, reasoning, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                decision_data.get('timestamp', datetime.now().isoformat()),
                decision_data.get('phase'),
                decision_data.get('decision_type'),
                decision_data.get('decision_description'),
                decision_data.get('quality_rating'),
                decision_data.get('difficulty_rating'),
                decision_data.get('is_regrettable', False),
                decision_data.get('used_lessons_learned', False),
                json.dumps(decision_data.get('pattern_ids', [])),
                decision_data.get('reasoning'),
                decision_data.get('outcome')
            ))

    def get_decisions(self, task_id: str) -> List[Dict]:
        """Get all decisions for a task."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM decisions
                WHERE task_id = ?
                ORDER BY timestamp ASC
            """, (task_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_decision_analytics(self, task_id: Optional[str] = None) -> Dict:
        """Get decision analytics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clause = "WHERE task_id = ?" if task_id else ""
            params = (task_id,) if task_id else ()

            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_decisions,
                    AVG(quality_rating) as avg_quality,
                    AVG(difficulty_rating) as avg_difficulty,
                    SUM(CASE WHEN is_regrettable = 1 THEN 1 ELSE 0 END) as regrettable_count,
                    SUM(CASE WHEN used_lessons_learned = 1 THEN 1 ELSE 0 END) as lessons_used_count
                FROM decisions
                {where_clause}
            """, params)

            row = cursor.fetchone()
            return dict(row) if row else {}

    # ============================================================================
    # Agent Performance
    # ============================================================================

    def add_agent_performance(self, task_id: str, agent_data: Dict[str, Any]):
        """Add agent performance record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_performance (
                    task_id, agent_type, phase, start_time, end_time,
                    duration_seconds, success, issues_found, issues_fixed,
                    files_created, files_modified, lines_of_code, tokens_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                agent_data.get('agent_type'),
                agent_data.get('phase'),
                agent_data.get('start_time'),
                agent_data.get('end_time'),
                agent_data.get('duration_seconds'),
                agent_data.get('success', True),
                agent_data.get('issues_found', 0),
                agent_data.get('issues_fixed', 0),
                agent_data.get('files_created', 0),
                agent_data.get('files_modified', 0),
                agent_data.get('lines_of_code', 0),
                agent_data.get('tokens_used', 0)
            ))

    def get_agent_performance(self, task_id: str) -> List[Dict]:
        """Get agent performance records for a task."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM agent_performance
                WHERE task_id = ?
                ORDER BY start_time ASC
            """, (task_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_agent_analytics(self, agent_type: Optional[str] = None) -> Dict:
        """Get agent performance analytics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            where_clause = "WHERE agent_type = ?" if agent_type else ""
            params = (agent_type,) if agent_type else ()

            cursor.execute(f"""
                SELECT
                    agent_type,
                    COUNT(*) as total_executions,
                    AVG(duration_seconds) as avg_duration,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                    AVG(issues_found) as avg_issues_found,
                    AVG(issues_fixed) as avg_issues_fixed,
                    AVG(tokens_used) as avg_tokens_used
                FROM agent_performance
                {where_clause}
                GROUP BY agent_type
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    # ============================================================================
    # Test Iterations
    # ============================================================================

    def add_test_iteration(self, task_id: str, test_data: Dict[str, Any]):
        """Add test iteration record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO test_iterations (
                    task_id, iteration_number, timestamp, tests_run,
                    tests_passed, tests_failed, test_output, fixes_applied,
                    duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                test_data.get('iteration_number'),
                test_data.get('timestamp', datetime.now().isoformat()),
                test_data.get('tests_run', 0),
                test_data.get('tests_passed', 0),
                test_data.get('tests_failed', 0),
                test_data.get('test_output'),
                json.dumps(test_data.get('fixes_applied', [])),
                test_data.get('duration_seconds')
            ))

    def get_test_iterations(self, task_id: str) -> List[Dict]:
        """Get test iterations for a task."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM test_iterations
                WHERE task_id = ?
                ORDER BY iteration_number ASC
            """, (task_id,))
            return [dict(row) for row in cursor.fetchall()]

    # ============================================================================
    # Pattern Effectiveness
    # ============================================================================

    def add_pattern_effectiveness(self, task_id: str, pattern_data: Dict[str, Any]):
        """Add pattern effectiveness record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pattern_effectiveness (
                    task_id, pattern_id, pattern_type, was_applied,
                    prevented_issue, issue_description, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                pattern_data.get('pattern_id'),
                pattern_data.get('pattern_type'),
                pattern_data.get('was_applied', False),
                pattern_data.get('prevented_issue', False),
                pattern_data.get('issue_description'),
                pattern_data.get('timestamp', datetime.now().isoformat())
            ))

    def get_pattern_effectiveness(self, task_id: Optional[str] = None) -> List[Dict]:
        """Get pattern effectiveness records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if task_id:
                cursor.execute("""
                    SELECT * FROM pattern_effectiveness
                    WHERE task_id = ?
                    ORDER BY timestamp ASC
                """, (task_id,))
            else:
                cursor.execute("""
                    SELECT * FROM pattern_effectiveness
                    ORDER BY timestamp DESC
                    LIMIT 100
                """)

            return [dict(row) for row in cursor.fetchall()]

    # ============================================================================
    # Analytics & Reporting
    # ============================================================================

    def get_summary_stats(self) -> Dict:
        """Get overall summary statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Task stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                    AVG(duration_seconds) as avg_duration
                FROM tasks
            """)
            stats['tasks'] = dict(cursor.fetchone())

            # Token stats
            cursor.execute("""
                SELECT
                    AVG(token_usage) as avg_tokens,
                    MAX(token_usage) as max_tokens,
                    AVG(token_percentage) as avg_percentage
                FROM metrics
            """)
            stats['tokens'] = dict(cursor.fetchone())

            # Decision stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_decisions,
                    AVG(quality_rating) as avg_quality,
                    SUM(CASE WHEN used_lessons_learned = 1 THEN 1 ELSE 0 END) as lessons_used
                FROM decisions
            """)
            stats['decisions'] = dict(cursor.fetchone())

            return stats


# Singleton instance
_db_instance = None


def get_db() -> MetricsDatabase:
    """Get singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = MetricsDatabase()
    return _db_instance


if __name__ == "__main__":
    # Test the database
    db = MetricsDatabase()
    print("✅ Database initialized successfully")
    print(f"📁 Location: {db.db_path}")

    # Test creating a task
    test_task_id = "test_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    db.create_task({
        'task_id': test_task_id,
        'project_name': 'test-project',
        'task_description': 'Test task',
        'working_directory': '/tmp/test',
        'status': 'running',
        'current_phase': 'Scout'
    })
    print(f"✅ Created test task: {test_task_id}")

    # Test adding metrics
    db.add_metric(test_task_id, {
        'phase': 'Scout',
        'token_usage': 15000,
        'token_percentage': 7.5,
        'latency_ms': 150.5,
        'elapsed_seconds': 120
    })
    print("✅ Added test metric")

    # Get summary stats
    stats = db.get_summary_stats()
    print(f"✅ Summary stats: {stats}")

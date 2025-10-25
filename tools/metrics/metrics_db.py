#!/usr/bin/env python3
"""
Metrics Database Module
Thread-safe SQLite database for metrics storage with schema migrations
"""

import sqlite3
import threading
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager


# Database schema version
SCHEMA_VERSION = 1

# Thread-local storage for connections
_thread_local = threading.local()


class MetricsDatabase:
    """Thread-safe SQLite database for metrics storage"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize metrics database.

        Args:
            db_path: Path to database file (default: ~/.context-foundry/metrics.db)
        """
        if db_path is None:
            db_path = str(Path.home() / '.context-foundry' / 'metrics.db')

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(_thread_local, 'connection') or not hasattr(_thread_local, 'db_path') or _thread_local.db_path != str(self.db_path):
            # Close old connection if it exists and path changed
            if hasattr(_thread_local, 'connection'):
                try:
                    _thread_local.connection.close()
                except:
                    pass

            _thread_local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            _thread_local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            _thread_local.connection.execute("PRAGMA foreign_keys = ON")
            _thread_local.db_path = str(self.db_path)
        return _thread_local.connection

    def close(self):
        """Close database connection"""
        if hasattr(_thread_local, 'connection'):
            try:
                _thread_local.connection.close()
                delattr(_thread_local, 'connection')
                if hasattr(_thread_local, 'db_path'):
                    delattr(_thread_local, 'db_path')
            except:
                pass

    @contextmanager
    def _transaction(self):
        """Context manager for database transactions"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _initialize_schema(self):
        """Initialize database schema with migrations"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create schema_version table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check current version
        cursor.execute("SELECT MAX(version) as version FROM schema_version")
        row = cursor.fetchone()
        current_version = row['version'] if row['version'] is not None else 0

        # Apply migrations
        if current_version < 1:
            self._migrate_to_v1(conn)

        conn.commit()

    def _migrate_to_v1(self, conn: sqlite3.Connection):
        """Migrate to schema version 1"""
        cursor = conn.cursor()

        # builds table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS builds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                task TEXT,
                mode TEXT,
                status TEXT,
                total_tokens_input INTEGER DEFAULT 0,
                total_tokens_output INTEGER DEFAULT 0,
                total_tokens_cached INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                duration_seconds INTEGER,
                working_directory TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_builds_session ON builds(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_builds_created ON builds(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_builds_status ON builds(status)")

        # phases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                build_id INTEGER NOT NULL,
                phase_name TEXT NOT NULL,
                phase_number TEXT,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                tokens_cached INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                duration_seconds INTEGER,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_phases_build ON phases(build_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_phases_name ON phases(phase_name)")

        # api_calls table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                tokens_input INTEGER,
                tokens_output INTEGER,
                tokens_cached INTEGER DEFAULT 0,
                cost REAL,
                latency_ms INTEGER,
                request_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (phase_id) REFERENCES phases(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_calls_phase ON api_calls(phase_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_calls_model ON api_calls(model)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp ON api_calls(timestamp)")

        # budget_snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budget_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_type TEXT,
                period_start DATE,
                total_cost REAL,
                build_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_budget_period ON budget_snapshots(period_type, period_start)")

        # Mark version as applied
        cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))

    def create_build(self, session_id: str, **kwargs) -> int:
        """
        Create new build record.

        Args:
            session_id: Unique session identifier
            **kwargs: Additional build attributes

        Returns:
            Build ID
        """
        with self._transaction() as conn:
            cursor = conn.cursor()

            fields = ['session_id']
            values = [session_id]

            for key, value in kwargs.items():
                if key in ['task', 'mode', 'status', 'working_directory']:
                    fields.append(key)
                    values.append(value)

            placeholders = ','.join(['?'] * len(values))
            sql = f"INSERT INTO builds ({','.join(fields)}) VALUES ({placeholders})"

            cursor.execute(sql, values)
            return cursor.lastrowid

    def update_build(self, session_id: str, **kwargs):
        """
        Update build record.

        Args:
            session_id: Session identifier
            **kwargs: Fields to update
        """
        if not kwargs:
            return

        with self._transaction() as conn:
            cursor = conn.cursor()

            # Build SET clause
            set_clauses = []
            values = []

            for key, value in kwargs.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)

            values.append(session_id)

            sql = f"UPDATE builds SET {', '.join(set_clauses)} WHERE session_id = ?"
            cursor.execute(sql, values)

    def get_build(self, session_id: str) -> Optional[Dict]:
        """Get build record by session ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM builds WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def create_phase(self, build_id: int, phase_name: str, **kwargs) -> int:
        """
        Create phase record.

        Args:
            build_id: Build ID
            phase_name: Phase name (Scout, Architect, etc.)
            **kwargs: Additional phase attributes

        Returns:
            Phase ID
        """
        with self._transaction() as conn:
            cursor = conn.cursor()

            fields = ['build_id', 'phase_name']
            values = [build_id, phase_name]

            for key, value in kwargs.items():
                if key in ['phase_number', 'tokens_input', 'tokens_output', 'tokens_cached',
                          'cost', 'duration_seconds', 'started_at', 'completed_at']:
                    fields.append(key)
                    values.append(value)

            placeholders = ','.join(['?'] * len(values))
            sql = f"INSERT INTO phases ({','.join(fields)}) VALUES ({placeholders})"

            cursor.execute(sql, values)
            return cursor.lastrowid

    def update_phase(self, phase_id: int, **kwargs):
        """Update phase record"""
        if not kwargs:
            return

        with self._transaction() as conn:
            cursor = conn.cursor()

            set_clauses = []
            values = []

            for key, value in kwargs.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)

            values.append(phase_id)

            sql = f"UPDATE phases SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(sql, values)

    def record_api_call(self, phase_id: int, model: str, tokens_input: int,
                       tokens_output: int, tokens_cached: int, cost: float,
                       latency_ms: Optional[int] = None, request_id: Optional[str] = None):
        """
        Record individual API call.

        Args:
            phase_id: Phase ID
            model: Model name
            tokens_input: Input tokens
            tokens_output: Output tokens
            tokens_cached: Cached tokens
            cost: Call cost in USD
            latency_ms: Latency in milliseconds
            request_id: API request ID
        """
        with self._transaction() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO api_calls (
                    phase_id, model, tokens_input, tokens_output, tokens_cached,
                    cost, latency_ms, request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (phase_id, model, tokens_input, tokens_output, tokens_cached,
                  cost, latency_ms, request_id))

    def get_build_metrics(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive metrics for a build.

        Args:
            session_id: Session identifier

        Returns:
            Dict with build metrics including phase breakdown
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get build info
        cursor.execute("SELECT * FROM builds WHERE session_id = ?", (session_id,))
        build_row = cursor.fetchone()

        if not build_row:
            return {}

        build = dict(build_row)

        # Get phase metrics
        cursor.execute("""
            SELECT
                phase_name,
                phase_number,
                tokens_input,
                tokens_output,
                tokens_cached,
                cost,
                duration_seconds,
                started_at,
                completed_at
            FROM phases
            WHERE build_id = ?
            ORDER BY id
        """, (build['id'],))

        phases = [dict(row) for row in cursor.fetchall()]

        # Calculate totals from phases (more accurate than build-level aggregates)
        total_tokens_input = sum(p['tokens_input'] or 0 for p in phases)
        total_tokens_output = sum(p['tokens_output'] or 0 for p in phases)
        total_tokens_cached = sum(p['tokens_cached'] or 0 for p in phases)
        total_cost = sum(p['cost'] or 0.0 for p in phases)

        return {
            'session_id': build['session_id'],
            'task': build['task'],
            'mode': build['mode'],
            'status': build['status'],
            'total_tokens': total_tokens_input + total_tokens_output,
            'total_tokens_input': total_tokens_input,
            'total_tokens_output': total_tokens_output,
            'total_tokens_cached': total_tokens_cached,
            'total_cost': total_cost,
            'duration_seconds': build['duration_seconds'],
            'working_directory': build['working_directory'],
            'created_at': build['created_at'],
            'completed_at': build['completed_at'],
            'phases': phases
        }

    def get_phase_totals(self, phase_name: str, days: int = 30) -> Dict[str, Any]:
        """
        Get aggregated totals for a phase across all builds in time period.

        Args:
            phase_name: Phase name
            days: Number of days to look back

        Returns:
            Dict with aggregated metrics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT
                COUNT(*) as total_runs,
                SUM(tokens_input) as total_tokens_input,
                SUM(tokens_output) as total_tokens_output,
                SUM(tokens_cached) as total_tokens_cached,
                SUM(cost) as total_cost,
                AVG(duration_seconds) as avg_duration_seconds
            FROM phases
            WHERE phase_name = ? AND started_at >= ?
        """, (phase_name, since_date))

        row = cursor.fetchone()

        if row:
            result = dict(row)
            result['total_tokens'] = (result['total_tokens_input'] or 0) + (result['total_tokens_output'] or 0)

            # Get average latency from API calls
            cursor.execute("""
                SELECT AVG(latency_ms) as avg_latency_ms
                FROM api_calls
                INNER JOIN phases ON api_calls.phase_id = phases.id
                WHERE phases.phase_name = ? AND phases.started_at >= ?
            """, (phase_name, since_date))

            latency_row = cursor.fetchone()
            result['avg_latency_ms'] = latency_row['avg_latency_ms'] if latency_row else 0

            return result

        return {
            'total_runs': 0,
            'total_tokens': 0,
            'total_tokens_input': 0,
            'total_tokens_output': 0,
            'total_tokens_cached': 0,
            'total_cost': 0.0,
            'avg_duration_seconds': 0,
            'avg_latency_ms': 0
        }

    def get_total_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get total metrics across all builds in time period.

        Args:
            days: Number of days to look back

        Returns:
            Dict with total metrics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT
                COUNT(*) as total_builds,
                SUM(total_tokens_input) as total_tokens_input,
                SUM(total_tokens_output) as total_tokens_output,
                SUM(total_tokens_cached) as total_tokens_cached,
                SUM(total_cost) as total_cost
            FROM builds
            WHERE created_at >= ?
        """, (since_date,))

        row = cursor.fetchone()

        if row:
            result = dict(row)
            result['total_tokens'] = (result['total_tokens_input'] or 0) + (result['total_tokens_output'] or 0)
            return result

        return {
            'total_builds': 0,
            'total_tokens': 0,
            'total_tokens_input': 0,
            'total_tokens_output': 0,
            'total_tokens_cached': 0,
            'total_cost': 0.0
        }

    def get_cost_summary(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Get cost summary for date range.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            Dict with cost summary
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as build_count,
                SUM(total_tokens_input + total_tokens_output) as total_tokens,
                SUM(total_cost) as total_cost,
                AVG(total_cost) as avg_cost_per_build,
                MIN(total_cost) as min_cost,
                MAX(total_cost) as max_cost
            FROM builds
            WHERE created_at >= ? AND created_at <= ?
        """, (start_date, end_date))

        row = cursor.fetchone()

        if row:
            return dict(row)

        return {
            'build_count': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'avg_cost_per_build': 0.0,
            'min_cost': 0.0,
            'max_cost': 0.0
        }

    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Delete records older than specified days.

        Args:
            days: Retention period in days

        Returns:
            Number of builds deleted
        """
        with self._transaction() as conn:
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            # Delete old builds (cascades to phases and api_calls)
            cursor.execute("""
                DELETE FROM builds
                WHERE created_at < ? AND status IN ('completed', 'failed')
            """, (cutoff_date,))

            deleted_count = cursor.rowcount

            return deleted_count

    def export_all_metrics(self) -> Dict[str, List[Dict]]:
        """Export all metrics for backup/analysis"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Export builds
        cursor.execute("SELECT * FROM builds ORDER BY created_at DESC")
        builds = [dict(row) for row in cursor.fetchall()]

        # Export phases
        cursor.execute("SELECT * FROM phases ORDER BY started_at")
        phases = [dict(row) for row in cursor.fetchall()]

        # Export API calls
        cursor.execute("SELECT * FROM api_calls ORDER BY timestamp")
        api_calls = [dict(row) for row in cursor.fetchall()]

        return {
            'builds': builds,
            'phases': phases,
            'api_calls': api_calls,
            'exported_at': datetime.now().isoformat()
        }


# Singleton instance
_db_instance = None
_db_lock = threading.Lock()


def get_metrics_db(db_path: Optional[str] = None) -> MetricsDatabase:
    """Get singleton metrics database instance"""
    global _db_instance

    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = MetricsDatabase(db_path)

    return _db_instance

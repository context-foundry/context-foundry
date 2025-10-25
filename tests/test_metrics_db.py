#!/usr/bin/env python3
"""
Test suite for MetricsDatabase module
Database operations and thread safety tests
"""

import pytest
import tempfile
import threading
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from tools.metrics.metrics_db import MetricsDatabase


class TestMetricsDatabase:
    """Test MetricsDatabase functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        # Create temporary database with proper permissions
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = Path(self.temp_dir) / 'test_metrics.db'

        self.db = MetricsDatabase(str(self.temp_db_path))

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'db'):
            self.db.close()
        if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_create_build(self):
        """Test creating a build record"""
        build_id = self.db.create_build(
            session_id="test-session-1",
            task="Build a test project",
            mode="new_project",
            status="running"
        )

        assert build_id > 0

        # Verify it was created
        build = self.db.get_build("test-session-1")
        assert build is not None
        assert build['session_id'] == "test-session-1"
        assert build['task'] == "Build a test project"
        assert build['mode'] == "new_project"
        assert build['status'] == "running"

    def test_update_build(self):
        """Test updating a build record"""
        build_id = self.db.create_build(session_id="test-session-2", status="running")

        self.db.update_build(
            "test-session-2",
            status="completed",
            total_tokens_input=10000,
            total_tokens_output=5000,
            total_cost=0.105
        )

        build = self.db.get_build("test-session-2")
        assert build['status'] == "completed"
        assert build['total_tokens_input'] == 10000
        assert build['total_tokens_output'] == 5000
        assert build['total_cost'] == 0.105

    def test_create_phase(self):
        """Test creating a phase record"""
        build_id = self.db.create_build(session_id="test-session-3")

        phase_id = self.db.create_phase(
            build_id=build_id,
            phase_name="Scout",
            phase_number="1/7",
            tokens_input=1000,
            tokens_output=500,
            cost=0.0105
        )

        assert phase_id > 0

    def test_record_api_call(self):
        """Test recording an API call"""
        build_id = self.db.create_build(session_id="test-session-4")
        phase_id = self.db.create_phase(build_id=build_id, phase_name="Scout")

        self.db.record_api_call(
            phase_id=phase_id,
            model="claude-sonnet-4",
            tokens_input=1000,
            tokens_output=500,
            tokens_cached=200,
            cost=0.0105,
            latency_ms=2500,
            request_id="msg_123"
        )

        # Verify by getting build metrics
        metrics = self.db.get_build_metrics("test-session-4")
        assert len(metrics['phases']) == 1

    def test_get_build_metrics(self):
        """Test getting comprehensive build metrics"""
        # Create build with multiple phases and API calls
        build_id = self.db.create_build(session_id="test-session-5")

        # Scout phase
        scout_id = self.db.create_phase(build_id, "Scout", tokens_input=1000, tokens_output=500, cost=0.0105)
        self.db.record_api_call(scout_id, "claude-sonnet-4", 1000, 500, 0, 0.0105, 2500, "msg_1")

        # Architect phase
        architect_id = self.db.create_phase(build_id, "Architect", tokens_input=2000, tokens_output=800, cost=0.018)
        self.db.record_api_call(architect_id, "claude-sonnet-4", 2000, 800, 0, 0.018, 3000, "msg_2")

        # Get metrics
        metrics = self.db.get_build_metrics("test-session-5")

        assert metrics['total_tokens_input'] == 3000
        assert metrics['total_tokens_output'] == 1300
        assert metrics['total_cost'] == pytest.approx(0.0285, abs=0.0001)
        assert len(metrics['phases']) == 2

    def test_get_phase_totals(self):
        """Test getting aggregated phase totals"""
        # Create multiple builds with Scout phases
        for i in range(3):
            build_id = self.db.create_build(session_id=f"test-build-{i}")
            scout_id = self.db.create_phase(build_id, "Scout", tokens_input=1000, tokens_output=500, cost=0.0105)
            self.db.record_api_call(scout_id, "claude-sonnet-4", 1000, 500, 0, 0.0105, 2500)

        totals = self.db.get_phase_totals("Scout", days=30)

        assert totals['total_runs'] == 3
        assert totals['total_tokens_input'] == 3000
        assert totals['total_tokens_output'] == 1500
        assert totals['total_cost'] == pytest.approx(0.0315, abs=0.0001)
        assert totals['avg_latency_ms'] == 2500

    def test_get_total_metrics(self):
        """Test getting total metrics across all builds"""
        # Create multiple builds
        for i in range(3):
            build_id = self.db.create_build(session_id=f"test-total-{i}")
            phase_id = self.db.create_phase(build_id, "Scout", tokens_input=1000, tokens_output=500, cost=0.0105)

        # Update build totals (normally done by collector)
        for i in range(3):
            self.db.update_build(
                f"test-total-{i}",
                total_tokens_input=1000,
                total_tokens_output=500,
                total_cost=0.0105
            )

        totals = self.db.get_total_metrics(days=30)

        assert totals['total_builds'] == 3
        assert totals['total_tokens_input'] == 3000
        assert totals['total_tokens_output'] == 1500
        assert totals['total_cost'] == pytest.approx(0.0315, abs=0.0001)

    def test_get_cost_summary(self):
        """Test getting cost summary for date range"""
        # Create builds
        build_id1 = self.db.create_build(session_id="cost-test-1")
        build_id2 = self.db.create_build(session_id="cost-test-2")

        self.db.update_build("cost-test-1", total_cost=0.50, total_tokens_input=10000, total_tokens_output=5000)
        self.db.update_build("cost-test-2", total_cost=0.75, total_tokens_input=15000, total_tokens_output=7500)

        # Get summary
        now = datetime.now()
        start = (now - timedelta(days=1)).isoformat()
        end = now.isoformat()

        summary = self.db.get_cost_summary(start, end)

        assert summary['build_count'] == 2
        assert summary['total_cost'] == 1.25
        assert summary['avg_cost_per_build'] == 0.625
        assert summary['min_cost'] == 0.50
        assert summary['max_cost'] == 0.75

    def test_cleanup_old_data(self):
        """Test data retention cleanup"""
        # Create old build
        old_build_id = self.db.create_build(session_id="old-build")

        # Manually set created_at to 100 days ago
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        self.db.update_build("old-build", status="completed", completed_at=old_date)

        # Manually update timestamp (direct SQL)
        conn = self.db._get_connection()
        conn.execute("UPDATE builds SET created_at = ? WHERE session_id = ?", (old_date, "old-build"))
        conn.commit()

        # Create recent build
        recent_build_id = self.db.create_build(session_id="recent-build")

        # Cleanup data older than 90 days
        deleted = self.db.cleanup_old_data(days=90)

        assert deleted == 1

        # Verify old build was deleted
        old_build = self.db.get_build("old-build")
        assert old_build is None

        # Verify recent build still exists
        recent_build = self.db.get_build("recent-build")
        assert recent_build is not None

    def test_foreign_key_cascade(self):
        """Test foreign key cascade deletion"""
        build_id = self.db.create_build(session_id="cascade-test")
        phase_id = self.db.create_phase(build_id, "Scout")
        self.db.record_api_call(phase_id, "claude-sonnet-4", 1000, 500, 0, 0.0105)

        # Delete build (should cascade to phases and api_calls)
        conn = self.db._get_connection()
        conn.execute("DELETE FROM builds WHERE id = ?", (build_id,))
        conn.commit()

        # Verify phases were deleted
        cursor = conn.execute("SELECT COUNT(*) FROM phases WHERE build_id = ?", (build_id,))
        phase_count = cursor.fetchone()[0]
        assert phase_count == 0

        # Verify API calls were deleted
        cursor = conn.execute("SELECT COUNT(*) FROM api_calls WHERE phase_id = ?", (phase_id,))
        call_count = cursor.fetchone()[0]
        assert call_count == 0

    def test_thread_safe_writes(self):
        """Test concurrent writes from multiple threads"""
        def create_builds(thread_num, count):
            for i in range(count):
                session_id = f"thread-{thread_num}-build-{i}"
                build_id = self.db.create_build(session_id=session_id)
                phase_id = self.db.create_phase(build_id, "Scout", tokens_input=1000, tokens_output=500)
                self.db.record_api_call(phase_id, "claude-sonnet-4", 1000, 500, 0, 0.0105)

        # Create 5 threads, each creating 10 builds
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_builds, args=(i, 10))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all builds were created
        totals = self.db.get_total_metrics(days=30)
        assert totals['total_builds'] == 50

    def test_export_all_metrics(self):
        """Test exporting all metrics"""
        # Create sample data
        build_id = self.db.create_build(session_id="export-test", task="Test export")
        phase_id = self.db.create_phase(build_id, "Scout", tokens_input=1000, tokens_output=500)
        self.db.record_api_call(phase_id, "claude-sonnet-4", 1000, 500, 0, 0.0105)

        # Export
        data = self.db.export_all_metrics()

        assert 'builds' in data
        assert 'phases' in data
        assert 'api_calls' in data
        assert 'exported_at' in data

        assert len(data['builds']) == 1
        assert len(data['phases']) == 1
        assert len(data['api_calls']) == 1

    def test_schema_migration(self):
        """Test schema migration system"""
        # Create new database
        temp_dir2 = tempfile.mkdtemp()
        temp_db_path2 = Path(temp_dir2) / 'test_migration.db'

        # Initialize (should run migration)
        db2 = MetricsDatabase(str(temp_db_path2))

        # Verify schema version
        conn = db2._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) FROM schema_version")
        version = cursor.fetchone()[0]

        assert version == 1

        # Cleanup
        shutil.rmtree(temp_dir2)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

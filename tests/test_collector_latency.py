#!/usr/bin/env python3
"""
Test suite for MetricsCollector latency calculation
Tests the TODO implementation for calculating latency from timestamps
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from tools.metrics.collector import MetricsCollector
from tools.metrics.log_parser import TokenUsage
from tools.metrics.metrics_db import MetricsDatabase


class TestCollectorLatency:
    """Test latency calculation in MetricsCollector"""

    def setup_method(self):
        """Setup test fixtures"""
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = Path(self.temp_dir) / 'test_metrics.db'
        self.db = MetricsDatabase(str(self.temp_db_path))
        self.collector = MetricsCollector(db=self.db)

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'db'):
            self.db.close()
        if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_latency_calculation_with_timestamps(self):
        """Test that latency is calculated from consecutive timestamps"""
        # Create build and phase
        build_id = self.db.create_build(session_id="test-latency-1")
        phase_id = self.db.create_phase(
            build_id,
            phase_name="test",
            started_at=datetime.now().isoformat()
        )

        # Create usage objects with timestamps
        usages = [
            TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                timestamp="2025-01-13T10:00:00"
            ),
            TokenUsage(
                input_tokens=1200,
                output_tokens=600,
                timestamp="2025-01-13T10:00:02.500"  # 2.5 seconds later
            ),
            TokenUsage(
                input_tokens=800,
                output_tokens=400,
                timestamp="2025-01-13T10:00:05"  # 2.5 seconds later
            ),
        ]

        # Write batch
        self.collector._write_batch(phase_id, usages, "claude-sonnet-4")

        # Verify latency was calculated
        # First call should have None (no previous timestamp)
        # Second call should have ~2500ms
        # Third call should have ~2500ms
        with self.db._transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT latency_ms, tokens_input
                FROM api_calls
                ORDER BY id
            """)
            results = cursor.fetchall()

        assert len(results) == 3

        # First call: no latency (no previous timestamp)
        assert results[0]['tokens_input'] == 1000
        assert results[0]['latency_ms'] is None

        # Second call: 2500ms from first
        assert results[1]['tokens_input'] == 1200
        assert results[1]['latency_ms'] == 2500

        # Third call: 2500ms from second
        assert results[2]['tokens_input'] == 800
        assert results[2]['latency_ms'] == 2500

    def test_latency_without_timestamps(self):
        """Test that latency is None when no timestamps available"""
        # Create build and phase
        build_id = self.db.create_build(session_id="test-latency-2")
        phase_id = self.db.create_phase(
            build_id,
            phase_name="test",
            started_at=datetime.now().isoformat()
        )

        # Create usage objects WITHOUT timestamps
        usages = [
            TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                timestamp=None
            ),
            TokenUsage(
                input_tokens=1200,
                output_tokens=600,
                timestamp=None
            ),
        ]

        # Write batch
        self.collector._write_batch(phase_id, usages, "claude-sonnet-4")

        # Verify latency is None
        with self.db._transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT latency_ms FROM api_calls ORDER BY id")
            results = cursor.fetchall()

        assert len(results) == 2
        assert results[0]['latency_ms'] is None
        assert results[1]['latency_ms'] is None

    def test_latency_with_partial_timestamps(self):
        """Test latency calculation with some timestamps missing"""
        # Create build and phase
        build_id = self.db.create_build(session_id="test-latency-3")
        phase_id = self.db.create_phase(
            build_id,
            phase_name="test",
            started_at=datetime.now().isoformat()
        )

        # Create usage objects with partial timestamps
        usages = [
            TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                timestamp="2025-01-13T10:00:00"
            ),
            TokenUsage(
                input_tokens=1200,
                output_tokens=600,
                timestamp=None  # Missing timestamp
            ),
            TokenUsage(
                input_tokens=800,
                output_tokens=400,
                timestamp="2025-01-13T10:00:05"
            ),
        ]

        # Write batch
        self.collector._write_batch(phase_id, usages, "claude-sonnet-4")

        # Verify latency handling
        with self.db._transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT latency_ms, tokens_input
                FROM api_calls
                ORDER BY id
            """)
            results = cursor.fetchall()

        assert len(results) == 3

        # First: None (no previous)
        assert results[0]['latency_ms'] is None

        # Second: None (missing timestamp)
        assert results[1]['latency_ms'] is None

        # Third: calculated from first timestamp (skipping the None)
        # 5 seconds from first = 5000ms
        assert results[2]['latency_ms'] == 5000

    def test_latency_state_reset_between_batches(self):
        """Test that latency state is maintained across batches"""
        # Create build and phase
        build_id = self.db.create_build(session_id="test-latency-4")
        phase_id = self.db.create_phase(
            build_id,
            phase_name="test",
            started_at=datetime.now().isoformat()
        )

        # First batch
        batch1 = [
            TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                timestamp="2025-01-13T10:00:00"
            ),
        ]
        self.collector._write_batch(phase_id, batch1, "claude-sonnet-4")

        # Second batch (should continue from first)
        batch2 = [
            TokenUsage(
                input_tokens=1200,
                output_tokens=600,
                timestamp="2025-01-13T10:00:03"  # 3 seconds after first
            ),
        ]
        self.collector._write_batch(phase_id, batch2, "claude-sonnet-4")

        # Verify latency spans batches
        with self.db._transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT latency_ms
                FROM api_calls
                ORDER BY id
            """)
            results = cursor.fetchall()

        assert len(results) == 2
        assert results[0]['latency_ms'] is None  # First call
        assert results[1]['latency_ms'] == 3000  # 3s from first


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

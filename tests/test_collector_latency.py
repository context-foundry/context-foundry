#!/usr/bin/env python3
"""
Tests for latency calculation in MetricsCollector
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime, timedelta
import tempfile

from tools.metrics.collector import MetricsCollector
from tools.metrics.log_parser import TokenUsage


class TestCollectorLatency(unittest.TestCase):
    """Test latency calculation in MetricsCollector"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock database and calculator
        self.mock_db = Mock()
        self.mock_calculator = Mock()
        self.mock_calculator.calculate_cost.return_value = 0.01

        # Create collector with mocks
        self.collector = MetricsCollector(
            db=self.mock_db, calculator=self.mock_calculator
        )

    def test_latency_calculation_with_consecutive_timestamps(self):
        """Test latency is calculated between consecutive API responses"""
        # Set up phase
        self.mock_db.get_build.return_value = {"id": 1}
        self.mock_db.create_phase.return_value = 100

        # Create test usages with timestamps
        base_time = datetime.now()
        usages = [
            TokenUsage(
                input_tokens=100,
                output_tokens=50,
                timestamp=(base_time + timedelta(seconds=i)).isoformat(),
            )
            for i in range(3)
        ]

        # Write batch
        self.collector._write_batch(100, usages, "claude-sonnet-4")

        # Check that API calls were recorded
        self.assertEqual(self.mock_db.record_api_call.call_count, 3)

        # First call should have latency_ms=None (no previous timestamp)
        first_call = self.mock_db.record_api_call.call_args_list[0]
        self.assertIsNone(first_call[1]["latency_ms"])

        # Second and third calls should have latency calculated
        second_call = self.mock_db.record_api_call.call_args_list[1]
        third_call = self.mock_db.record_api_call.call_args_list[2]

        # Should be approximately 1000ms between each
        self.assertIsNotNone(second_call[1]["latency_ms"])
        self.assertIsNotNone(third_call[1]["latency_ms"])
        self.assertGreater(second_call[1]["latency_ms"], 900)
        self.assertLess(second_call[1]["latency_ms"], 1100)

    def test_latency_with_missing_timestamps(self):
        """Test that missing timestamps are handled gracefully"""
        self.mock_db.get_build.return_value = {"id": 1}
        self.mock_db.create_phase.return_value = 100

        # Create usages with some missing timestamps
        usages = [
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:00"
            ),
            TokenUsage(input_tokens=100, output_tokens=50, timestamp=None),
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:02"
            ),
        ]

        # Write batch
        self.collector._write_batch(100, usages, "claude-sonnet-4")

        # All calls should succeed
        self.assertEqual(self.mock_db.record_api_call.call_count, 3)

        # Check latency values
        calls = self.mock_db.record_api_call.call_args_list
        self.assertIsNone(calls[0][1]["latency_ms"])  # First has no previous
        self.assertIsNone(calls[1][1]["latency_ms"])  # No timestamp
        self.assertIsNotNone(calls[2][1]["latency_ms"])  # Has timestamp and previous

    def test_latency_persists_across_batches(self):
        """Test that latency tracking continues across multiple batches"""
        self.mock_db.get_build.return_value = {"id": 1}
        self.mock_db.create_phase.return_value = 100

        # First batch
        batch1 = [
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:00"
            ),
        ]
        self.collector._write_batch(100, batch1, "claude-sonnet-4")

        # Second batch (should calculate latency from last timestamp in batch1)
        batch2 = [
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:01"
            ),
        ]
        self.collector._write_batch(100, batch2, "claude-sonnet-4")

        # Check that second batch has latency calculated
        self.assertEqual(self.mock_db.record_api_call.call_count, 2)
        second_batch_call = self.mock_db.record_api_call.call_args_list[1]
        self.assertIsNotNone(second_batch_call[1]["latency_ms"])
        self.assertGreater(second_batch_call[1]["latency_ms"], 900)

    def test_collect_from_log_file_with_timestamps(self):
        """Test latency calculation when parsing log files"""
        # Create temporary log file with timestamps
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_file = Path(f.name)
            # Write log entries with timestamps
            f.write(
                '2025-11-07T10:00:00 {"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
            )
            f.write(
                '2025-11-07T10:00:01 {"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
            )
            f.write(
                '2025-11-07T10:00:02 {"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
            )

        try:
            self.mock_db.get_build.return_value = None
            self.mock_db.create_build.return_value = 1
            self.mock_db.create_phase.return_value = 100

            # Collect from log file
            self.collector.collect_from_log_file(log_file, "test-session", "test-phase")

            # Should have recorded 3 API calls
            self.assertEqual(self.mock_db.record_api_call.call_count, 3)

            # Check latency values
            calls = self.mock_db.record_api_call.call_args_list
            self.assertIsNone(calls[0][1].get("latency_ms"))  # First has no previous
            self.assertIsNotNone(calls[1][1].get("latency_ms"))  # Should have latency
            self.assertIsNotNone(calls[2][1].get("latency_ms"))  # Should have latency

        finally:
            log_file.unlink()

    def test_latency_calculation_uses_parser_method(self):
        """Test that latency calculation delegates to LogParser.calculate_latency"""
        self.mock_db.get_build.return_value = {"id": 1}
        self.mock_db.create_phase.return_value = 100

        # Create usages with timestamps
        usages = [
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:00"
            ),
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:01"
            ),
        ]

        # Spy on parser.calculate_latency
        with patch.object(
            self.collector.parser,
            "calculate_latency",
            wraps=self.collector.parser.calculate_latency,
        ) as mock_calc:
            self.collector._write_batch(100, usages, "claude-sonnet-4")

            # Should have called calculate_latency once (for second usage)
            self.assertEqual(mock_calc.call_count, 1)
            mock_calc.assert_called_with("2025-11-07T10:00:00", "2025-11-07T10:00:01")

    def test_latency_with_zero_time_difference(self):
        """Test latency calculation when timestamps are identical"""
        self.mock_db.get_build.return_value = {"id": 1}
        self.mock_db.create_phase.return_value = 100

        # Create usages with same timestamp
        usages = [
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:00"
            ),
            TokenUsage(
                input_tokens=100, output_tokens=50, timestamp="2025-11-07T10:00:00"
            ),
        ]

        self.collector._write_batch(100, usages, "claude-sonnet-4")

        # Should succeed and return 0ms latency
        self.assertEqual(self.mock_db.record_api_call.call_count, 2)
        second_call = self.mock_db.record_api_call.call_args_list[1]
        self.assertEqual(second_call[1]["latency_ms"], 0)


if __name__ == "__main__":
    unittest.main()

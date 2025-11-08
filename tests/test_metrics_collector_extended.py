#!/usr/bin/env python3
"""
Extended tests for MetricsCollector covering critical paths
Tests for subprocess collection, batch writing, and phase monitoring
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from pathlib import Path
import tempfile
import json
import subprocess
import queue
import threading
import time
from datetime import datetime

from tools.metrics.collector import MetricsCollector
from tools.metrics.log_parser import TokenUsage


class TestCollectorSubprocessCollection(unittest.TestCase):
    """Test collect_from_subprocess critical path"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_calculator = Mock()
        self.mock_calculator.calculate_cost.return_value = 0.01
        self.collector = MetricsCollector(
            db=self.mock_db,
            calculator=self.mock_calculator
        )

    def test_collect_from_subprocess_creates_build_if_not_exists(self):
        """Test that collect_from_subprocess creates build if it doesn't exist"""
        # Mock process
        mock_process = Mock(spec=subprocess.Popen)

        # Mock database responses
        self.mock_db.get_build.return_value = None
        self.mock_db.create_build.return_value = 1
        self.mock_db.create_phase.return_value = 100

        # Mock parser to return no usages (empty iteration)
        with patch.object(self.collector.parser, 'parse_subprocess_output', return_value=iter([])):
            self.collector.collect_from_subprocess(
                mock_process,
                'test-session',
                'test-phase'
            )

        # Verify build was created
        self.mock_db.create_build.assert_called_once_with('test-session')
        self.mock_db.create_phase.assert_called_once()

    def test_collect_from_subprocess_uses_existing_build(self):
        """Test that collect_from_subprocess uses existing build if available"""
        mock_process = Mock(spec=subprocess.Popen)

        # Mock existing build
        self.mock_db.get_build.return_value = {'id': 42, 'session_id': 'test-session'}
        self.mock_db.create_phase.return_value = 100

        with patch.object(self.collector.parser, 'parse_subprocess_output', return_value=iter([])):
            self.collector.collect_from_subprocess(
                mock_process,
                'test-session',
                'test-phase'
            )

        # Verify build was not created, only phase
        self.mock_db.create_build.assert_not_called()
        self.mock_db.create_phase.assert_called_once()

    def test_collect_from_subprocess_handles_parser_exception(self):
        """Test that collect_from_subprocess handles parser exceptions gracefully"""
        mock_process = Mock(spec=subprocess.Popen)

        self.mock_db.get_build.return_value = {'id': 1}
        self.mock_db.create_phase.return_value = 100

        # Mock parser to raise exception
        def failing_parser():
            yield TokenUsage(100, 50, None)
            raise RuntimeError("Parser error")

        with patch.object(self.collector.parser, 'parse_subprocess_output', return_value=failing_parser()):
            # Should not raise exception
            self.collector.collect_from_subprocess(
                mock_process,
                'test-session',
                'test-phase'
            )

        # Phase should still be updated
        self.mock_db.update_phase.assert_called_once()

    def test_collect_from_subprocess_updates_phase_on_completion(self):
        """Test that phase is marked completed after collection"""
        mock_process = Mock(spec=subprocess.Popen)

        self.mock_db.get_build.return_value = {'id': 1}
        self.mock_db.create_phase.return_value = 100

        with patch.object(self.collector.parser, 'parse_subprocess_output', return_value=iter([])):
            self.collector.collect_from_subprocess(
                mock_process,
                'test-session',
                'test-phase'
            )

        # Verify phase was updated with completion time
        self.mock_db.update_phase.assert_called_once()
        args = self.mock_db.update_phase.call_args
        self.assertEqual(args[0][0], 100)
        self.assertIn('completed_at', args[1])

    def test_collect_from_subprocess_queues_usages_for_batch_writing(self):
        """Test that usages are queued for batch writing"""
        mock_process = Mock(spec=subprocess.Popen)

        self.mock_db.get_build.return_value = {'id': 1}
        self.mock_db.create_phase.return_value = 100

        # Create test usages
        usages = [
            TokenUsage(100, 50, "2025-11-07T10:00:00"),
            TokenUsage(150, 75, "2025-11-07T10:00:01"),
        ]

        with patch.object(self.collector.parser, 'parse_subprocess_output', return_value=iter(usages)):
            # Mock _update_phase_totals to avoid side effects
            with patch.object(self.collector, '_update_phase_totals'):
                self.collector.collect_from_subprocess(
                    mock_process,
                    'test-session',
                    'test-phase',
                    batch_size=10,
                    batch_timeout=1.0
                )

        # Give background thread time to process
        time.sleep(0.2)

        # Verify API calls were recorded
        self.assertGreater(self.mock_db.record_api_call.call_count, 0)


class TestBatchWriter(unittest.TestCase):
    """Test _batch_writer background thread"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_calculator = Mock()
        self.mock_calculator.calculate_cost.return_value = 0.01
        self.collector = MetricsCollector(
            db=self.mock_db,
            calculator=self.mock_calculator
        )

    def test_batch_writer_flushes_on_batch_size(self):
        """Test that batch writer flushes when batch size is reached"""
        # Queue some usages
        for i in range(5):
            self.collector._usage_queue.put(
                TokenUsage(100, 50, f"2025-11-07T10:00:{i:02d}")
            )

        # Start batch writer thread
        thread = threading.Thread(
            target=self.collector._batch_writer,
            args=(100, 'claude-sonnet-4', 3, 10.0),
            daemon=True
        )
        thread.start()

        # Wait for processing
        time.sleep(0.3)

        # Stop thread
        self.collector._shutdown.set()
        thread.join(timeout=2)

        # Should have written at least one batch
        self.assertGreater(self.mock_db.record_api_call.call_count, 0)

    def test_batch_writer_flushes_on_timeout(self):
        """Test that batch writer flushes on timeout even with partial batch"""
        # Queue one usage
        self.collector._usage_queue.put(
            TokenUsage(100, 50, "2025-11-07T10:00:00")
        )

        # Start batch writer with short timeout
        thread = threading.Thread(
            target=self.collector._batch_writer,
            args=(100, 'claude-sonnet-4', 10, 0.2),
            daemon=True
        )
        thread.start()

        # Wait for timeout to trigger
        time.sleep(0.5)

        # Stop thread
        self.collector._shutdown.set()
        thread.join(timeout=2)

        # Should have written the partial batch
        self.assertGreater(self.mock_db.record_api_call.call_count, 0)

    def test_batch_writer_writes_remaining_on_shutdown(self):
        """Test that batch writer writes remaining items on shutdown"""
        # Queue usages
        for i in range(2):
            self.collector._usage_queue.put(
                TokenUsage(100, 50, f"2025-11-07T10:00:{i:02d}")
            )

        # Start and immediately stop
        thread = threading.Thread(
            target=self.collector._batch_writer,
            args=(100, 'claude-sonnet-4', 10, 10.0),
            daemon=True
        )
        thread.start()

        # Give it a moment to read from queue
        time.sleep(0.1)

        # Signal shutdown
        self.collector._shutdown.set()
        thread.join(timeout=2)

        # Should have written remaining items
        self.assertGreater(self.mock_db.record_api_call.call_count, 0)


class TestUpdatePhaseTotals(unittest.TestCase):
    """Test _update_phase_totals method"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_calculator = Mock()
        self.mock_calculator.calculate_cost.return_value = 0.015
        self.collector = MetricsCollector(
            db=self.mock_db,
            calculator=self.mock_calculator
        )

    def test_update_phase_totals_calculates_cost(self):
        """Test that phase totals include cost calculation"""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            timestamp="2025-11-07T10:00:00"
        )

        self.collector._update_phase_totals(100, usage, 'claude-sonnet-4')

        # Verify cost was calculated with the usage object
        self.mock_calculator.calculate_cost.assert_called_once_with(
            usage, 'claude-sonnet-4'
        )

        # Note: _update_phase_totals actually does a pass (no-op) in the current implementation
        # The database totals are calculated dynamically from api_calls table
        # So we just verify the cost calculation was called


class TestCollectFromPhaseFile(unittest.TestCase):
    """Test collect_from_phase_file method"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_calculator = Mock()
        self.collector = MetricsCollector(
            db=self.mock_db,
            calculator=self.mock_calculator
        )

    @patch('builtins.open', new_callable=mock_open, read_data='{"current_phase": "scout", "phase_number": "1/7", "status": "running"}')
    def test_collect_from_phase_file_reads_phase_file(self, mock_file):
        """Test that collect_from_phase_file reads and parses phase file"""
        self.mock_db.get_build.return_value = None
        self.mock_db.create_build.return_value = 1

        result = self.collector.collect_from_phase_file(Path('/fake/phase.json'), 'test-session')

        # Verify file was opened
        mock_file.assert_called_once_with(Path('/fake/phase.json'), 'r')

        # Verify result contains phase data
        self.assertEqual(result['phase_name'], 'scout')
        self.assertEqual(result['phase_number'], '1/7')
        self.assertEqual(result['status'], 'running')

    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    def test_collect_from_phase_file_handles_missing_file(self, mock_file):
        """Test that collect_from_phase_file handles missing phase file"""
        result = self.collector.collect_from_phase_file(Path('/fake/missing.json'), 'test-session')

        # Should return error info
        self.assertIn('error', result)
        self.assertEqual(result['session_id'], 'test-session')

    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_collect_from_phase_file_handles_invalid_json(self, mock_file):
        """Test that collect_from_phase_file handles invalid JSON"""
        result = self.collector.collect_from_phase_file(Path('/fake/invalid.json'), 'test-session')

        # Should return error info
        self.assertIn('error', result)
        self.assertEqual(result['session_id'], 'test-session')

    @patch('builtins.open', new_callable=mock_open, read_data='{"current_phase": "test", "status": "completed"}')
    def test_collect_from_phase_file_creates_build_if_not_exists(self, mock_file):
        """Test that collect_from_phase_file creates build if it doesn't exist"""
        self.mock_db.get_build.return_value = None
        self.mock_db.create_build.return_value = 42

        result = self.collector.collect_from_phase_file(Path('/fake/phase.json'), 'new-session')

        # Verify build was created
        self.mock_db.create_build.assert_called_once_with('new-session', status='completed')
        self.assertEqual(result['build_id'], 42)

    @patch('builtins.open', new_callable=mock_open, read_data='{"current_phase": "test", "status": "failed"}')
    def test_collect_from_phase_file_updates_existing_build_status(self, mock_file):
        """Test that collect_from_phase_file updates existing build status"""
        self.mock_db.get_build.return_value = {'id': 10, 'session_id': 'existing-session'}

        result = self.collector.collect_from_phase_file(Path('/fake/phase.json'), 'existing-session')

        # Verify build status was updated
        self.mock_db.update_build.assert_called_once_with('existing-session', status='failed')
        self.assertEqual(result['build_id'], 10)
        self.assertEqual(result['status'], 'failed')


class TestCollectFromLogFile(unittest.TestCase):
    """Test collect_from_log_file method"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_calculator = Mock()
        self.mock_calculator.calculate_cost.return_value = 0.01
        self.collector = MetricsCollector(
            db=self.mock_db,
            calculator=self.mock_calculator
        )

    def test_collect_from_log_file_processes_all_entries(self):
        """Test that collect_from_log_file processes all log entries"""
        # Create temporary log file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            log_file = Path(f.name)
            # Write valid log entries
            f.write('{"usage": {"input_tokens": 100, "output_tokens": 50}}\n')
            f.write('{"usage": {"input_tokens": 150, "output_tokens": 75}}\n')
            f.write('{"usage": {"input_tokens": 200, "output_tokens": 100}}\n')

        try:
            self.mock_db.get_build.return_value = None
            self.mock_db.create_build.return_value = 1
            self.mock_db.create_phase.return_value = 100

            self.collector.collect_from_log_file(log_file, 'test-session', 'test-phase')

            # Should have recorded 3 API calls
            self.assertEqual(self.mock_db.record_api_call.call_count, 3)

            # Verify API calls were made (checking specific args varies by implementation)
            # The important thing is that all entries were processed
        finally:
            log_file.unlink()

    def test_collect_from_log_file_handles_empty_file(self):
        """Test that collect_from_log_file handles empty files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            log_file = Path(f.name)
            # Leave file empty

        try:
            self.mock_db.get_build.return_value = None
            self.mock_db.create_build.return_value = 1
            self.mock_db.create_phase.return_value = 100

            # Should not raise exception
            self.collector.collect_from_log_file(log_file, 'test-session', 'test-phase')

            # No API calls should be recorded
            self.mock_db.record_api_call.assert_not_called()
        finally:
            log_file.unlink()


if __name__ == '__main__':
    unittest.main()

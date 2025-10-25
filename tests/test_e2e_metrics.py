#!/usr/bin/env python3
"""
End-to-end test for metrics collection
Validates complete workflow from log parsing to database storage
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from tools.metrics.log_parser import LogParser
from tools.metrics.metrics_db import MetricsDatabase
from tools.metrics.cost_calculator import CostCalculator
from tools.metrics.collector import MetricsCollector


class TestE2EMetrics:
    """End-to-end integration tests"""

    def setup_method(self):
        """Setup test fixtures"""
        # Create temporary database with proper permissions
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = Path(self.temp_dir) / 'test_e2e_metrics.db'

        self.db = MetricsDatabase(str(self.temp_db_path))

        # Create temporary config
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_config.write('''{
            "models": {
                "claude-sonnet-4": {
                    "input_per_mtok": 3.00,
                    "output_per_mtok": 15.00,
                    "cache_write_per_mtok": 3.75,
                    "cache_read_per_mtok": 0.30
                }
            },
            "budget": {
                "daily_limit_usd": 50.0,
                "monthly_limit_usd": 500.0,
                "alert_threshold_pct": 80,
                "warning_threshold_pct": 90
            }
        }''')
        self.temp_config.close()

        self.calculator = CostCalculator(self.temp_config.name)
        self.collector = MetricsCollector(self.db, self.calculator)

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'db'):
            self.db.close()
        if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        if hasattr(self, 'temp_config') and Path(self.temp_config.name).exists():
            Path(self.temp_config.name).unlink(missing_ok=True)

    def test_collect_from_log_file(self):
        """Test collecting metrics from a log file"""
        # Create sample log file
        log_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
        log_file.write('{"id": "msg_1", "usage": {"input_tokens": 1000, "output_tokens": 500}}\n')
        log_file.write('{"id": "msg_2", "usage": {"input_tokens": 2000, "output_tokens": 800}}\n')
        log_file.write('{"id": "msg_3", "usage": {"input_tokens": 1500, "output_tokens": 600, "cache_read_input_tokens": 500}}\n')
        log_file.close()

        # Collect metrics
        self.collector.collect_from_log_file(
            Path(log_file.name),
            session_id="e2e-test-1",
            phase_name="Scout",
            model="claude-sonnet-4"
        )

        # Verify metrics were stored
        metrics = self.db.get_build_metrics("e2e-test-1")

        assert metrics is not None
        assert len(metrics['phases']) == 1
        assert metrics['phases'][0]['phase_name'] == "Scout"

        # Verify totals
        assert metrics['total_tokens_input'] == 4500  # 1000 + 2000 + 1500
        assert metrics['total_tokens_output'] == 1900  # 500 + 800 + 600
        assert metrics['total_tokens_cached'] == 500

        # Verify costs
        expected_cost = (
            (1000 / 1_000_000 * 3.00) + (500 / 1_000_000 * 15.00) +  # Call 1
            (2000 / 1_000_000 * 3.00) + (800 / 1_000_000 * 15.00) +  # Call 2
            (1500 / 1_000_000 * 3.00) + (600 / 1_000_000 * 15.00) + (500 / 1_000_000 * 0.30)  # Call 3
        )
        assert metrics['total_cost'] == pytest.approx(expected_cost, abs=0.0001)

        # Cleanup
        Path(log_file.name).unlink()

    def test_finalize_build(self):
        """Test build finalization"""
        # Create build with metrics
        build_id = self.db.create_build(session_id="e2e-finalize", status="running")
        phase_id = self.db.create_phase(build_id, "Scout", tokens_input=10000, tokens_output=5000, cost=0.105)

        # Finalize
        self.collector.finalize_build("e2e-finalize", status="completed")

        # Verify build was updated
        build = self.db.get_build("e2e-finalize")
        assert build['status'] == "completed"
        assert build['total_tokens_input'] == 10000
        assert build['total_tokens_output'] == 5000
        assert build['total_cost'] == 0.105

    def test_multi_phase_collection(self):
        """Test collecting metrics across multiple phases"""
        # Create log files for different phases
        scout_log = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
        scout_log.write('{"usage": {"input_tokens": 1000, "output_tokens": 500}}\n')
        scout_log.close()

        architect_log = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
        architect_log.write('{"usage": {"input_tokens": 2000, "output_tokens": 800}}\n')
        architect_log.close()

        builder_log = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
        builder_log.write('{"usage": {"input_tokens": 5000, "output_tokens": 2000}}\n')
        builder_log.close()

        # Collect from each phase
        session_id = "e2e-multi-phase"

        self.collector.collect_from_log_file(Path(scout_log.name), session_id, "Scout", "claude-sonnet-4")
        self.collector.collect_from_log_file(Path(architect_log.name), session_id, "Architect", "claude-sonnet-4")
        self.collector.collect_from_log_file(Path(builder_log.name), session_id, "Builder", "claude-sonnet-4")

        # Finalize
        self.collector.finalize_build(session_id, status="completed")

        # Verify aggregated metrics
        metrics = self.db.get_build_metrics(session_id)

        assert len(metrics['phases']) == 3
        assert metrics['total_tokens_input'] == 8000  # 1000 + 2000 + 5000
        assert metrics['total_tokens_output'] == 3300  # 500 + 800 + 2000

        # Cleanup
        for log_file in [scout_log.name, architect_log.name, builder_log.name]:
            Path(log_file).unlink()

    def test_budget_alerts(self):
        """Test budget alert generation"""
        # Create expensive build (triggers warning)
        build_id = self.db.create_build(session_id="expensive-build")
        phase_id = self.db.create_phase(build_id, "Scout", cost=42.0)  # 84% of $50 daily limit
        self.db.update_build("expensive-build", total_cost=42.0)

        # Get budget status
        budget_status = self.calculator.get_budget_status(self.db)

        assert len(budget_status['alerts']) > 0
        assert budget_status['daily']['status'] in ['warning', 'critical']

    def test_phase_aggregation(self):
        """Test phase aggregation across builds"""
        # Create multiple builds with Scout phases
        for i in range(5):
            build_id = self.db.create_build(session_id=f"scout-build-{i}")
            phase_id = self.db.create_phase(
                build_id,
                "Scout",
                tokens_input=1000,
                tokens_output=500,
                cost=0.0105
            )
            self.db.record_api_call(
                phase_id,
                "claude-sonnet-4",
                1000, 500, 0,
                0.0105,
                latency_ms=2500
            )

        # Get Scout phase totals
        totals = self.db.get_phase_totals("Scout", days=30)

        assert totals['total_runs'] == 5
        assert totals['total_tokens_input'] == 5000
        assert totals['total_tokens_output'] == 2500
        assert totals['total_cost'] == pytest.approx(0.0525, abs=0.0001)
        assert totals['avg_latency_ms'] == 2500

    def test_real_world_scenario(self):
        """Test realistic build scenario with multiple phases and API calls"""
        session_id = "real-world-test"

        # Scout phase - 3 API calls
        build_id = self.db.create_build(session_id=session_id, task="Build metrics system", mode="add_feature")
        scout_id = self.db.create_phase(build_id, "Scout", phase_number="1/7")

        self.db.record_api_call(scout_id, "claude-sonnet-4", 5000, 2000, 0, 0.045, 3200)
        self.db.record_api_call(scout_id, "claude-sonnet-4", 3000, 1500, 2000, 0.033, 2800)
        self.db.record_api_call(scout_id, "claude-sonnet-4", 2000, 1000, 1500, 0.0195, 2500)

        # Update phase totals
        self.db.update_phase(scout_id, tokens_input=10000, tokens_output=4500, tokens_cached=3500, cost=0.0975)

        # Architect phase - 2 API calls
        architect_id = self.db.create_phase(build_id, "Architect", phase_number="2/7")

        self.db.record_api_call(architect_id, "claude-sonnet-4", 8000, 3500, 5000, 0.0915, 4100)
        self.db.record_api_call(architect_id, "claude-sonnet-4", 6000, 2800, 3000, 0.069, 3600)

        self.db.update_phase(architect_id, tokens_input=14000, tokens_output=6300, tokens_cached=8000, cost=0.1605)

        # Finalize
        self.collector.finalize_build(session_id, status="completed")

        # Verify complete metrics
        metrics = self.db.get_build_metrics(session_id)

        assert metrics['session_id'] == session_id
        assert metrics['total_tokens_input'] == 24000
        assert metrics['total_tokens_output'] == 10800
        assert metrics['total_tokens_cached'] == 11500
        assert metrics['total_cost'] == pytest.approx(0.258, abs=0.001)
        assert len(metrics['phases']) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

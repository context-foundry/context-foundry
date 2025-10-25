#!/usr/bin/env python3
"""
Test suite for CostCalculator module
Pricing accuracy and budget tracking tests
"""

import pytest
import json
import tempfile
from pathlib import Path
from tools.metrics.cost_calculator import CostCalculator
from tools.metrics.log_parser import TokenUsage


class TestCostCalculator:
    """Test CostCalculator functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        config = {
            "models": {
                "claude-sonnet-4": {
                    "input_per_mtok": 3.00,
                    "output_per_mtok": 15.00,
                    "cache_write_per_mtok": 3.75,
                    "cache_read_per_mtok": 0.30
                },
                "claude-opus-4": {
                    "input_per_mtok": 15.00,
                    "output_per_mtok": 75.00,
                    "cache_write_per_mtok": 18.75,
                    "cache_read_per_mtok": 1.50
                },
                "default": {
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
        }
        json.dump(config, self.temp_config)
        self.temp_config.close()

        self.calculator = CostCalculator(self.temp_config.name)

    def teardown_method(self):
        """Cleanup"""
        Path(self.temp_config.name).unlink()

    def test_calculate_cost_sonnet_basic(self):
        """Test basic cost calculation for Sonnet"""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=0,
            cache_write_tokens=0
        )

        cost = self.calculator.calculate_cost(usage, "claude-sonnet-4")

        # (1000/1M * $3) + (500/1M * $15) = $0.003 + $0.0075 = $0.0105
        assert cost == pytest.approx(0.0105, abs=0.000001)

    def test_calculate_cost_opus_basic(self):
        """Test basic cost calculation for Opus"""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=0,
            cache_write_tokens=0
        )

        cost = self.calculator.calculate_cost(usage, "claude-opus-4")

        # (1000/1M * $15) + (500/1M * $75) = $0.015 + $0.0375 = $0.0525
        assert cost == pytest.approx(0.0525, abs=0.000001)

    def test_calculate_cost_with_cache_read(self):
        """Test cost calculation with cache read (90% discount)"""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=2000,
            cache_write_tokens=0
        )

        cost = self.calculator.calculate_cost(usage, "claude-sonnet-4")

        # Input: 1000/1M * $3 = $0.003
        # Output: 500/1M * $15 = $0.0075
        # Cache read: 2000/1M * $0.30 = $0.0006
        # Total = $0.0111
        assert cost == pytest.approx(0.0111, abs=0.000001)

    def test_calculate_cost_with_cache_write(self):
        """Test cost calculation with cache write tokens"""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=0,
            cache_write_tokens=500
        )

        cost = self.calculator.calculate_cost(usage, "claude-sonnet-4")

        # Input: 1000/1M * $3 = $0.003
        # Output: 500/1M * $15 = $0.0075
        # Cache write: 500/1M * $3.75 = $0.001875
        # Total = $0.012375
        assert cost == pytest.approx(0.012375, abs=0.000001)

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens"""
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0
        )

        cost = self.calculator.calculate_cost(usage, "claude-sonnet-4")

        assert cost == 0.0

    def test_calculate_cost_large_tokens(self):
        """Test cost calculation with large token counts"""
        usage = TokenUsage(
            input_tokens=195000,
            output_tokens=4500,
            cache_read_tokens=10000,
            cache_write_tokens=0
        )

        cost = self.calculator.calculate_cost(usage, "claude-sonnet-4")

        # Input: 195000/1M * $3 = $0.585
        # Output: 4500/1M * $15 = $0.0675
        # Cache read: 10000/1M * $0.30 = $0.003
        # Total = $0.6555
        assert cost == pytest.approx(0.6555, abs=0.000001)

    def test_calculate_batch_cost(self):
        """Test batch cost calculation"""
        usages = [
            TokenUsage(input_tokens=1000, output_tokens=500),
            TokenUsage(input_tokens=2000, output_tokens=800),
            TokenUsage(input_tokens=1500, output_tokens=600)
        ]

        result = self.calculator.calculate_batch_cost(usages, "claude-sonnet-4")

        assert result['call_count'] == 3
        assert result['total_input_tokens'] == 4500
        assert result['total_output_tokens'] == 1900
        assert result['total_tokens'] == 6400
        # Total cost = (4500/1M * $3) + (1900/1M * $15) = $0.0135 + $0.0285 = $0.042
        assert result['total_cost'] == pytest.approx(0.042, abs=0.000001)

    def test_estimate_remaining_budget_daily_ok(self):
        """Test budget estimation - daily OK status"""
        current_cost = 10.0

        budget = self.calculator.estimate_remaining_budget(current_cost, "daily")

        assert budget['limit'] == 50.0
        assert budget['current'] == 10.0
        assert budget['remaining'] == 40.0
        assert budget['percent_used'] == 20.0
        assert budget['status'] == 'ok'

    def test_estimate_remaining_budget_daily_warning(self):
        """Test budget estimation - daily warning status"""
        current_cost = 42.0  # 84% of $50 limit

        budget = self.calculator.estimate_remaining_budget(current_cost, "daily")

        assert budget['status'] == 'warning'
        assert budget['percent_used'] == 84.0

    def test_estimate_remaining_budget_daily_critical(self):
        """Test budget estimation - daily critical status"""
        current_cost = 46.0  # 92% of $50 limit

        budget = self.calculator.estimate_remaining_budget(current_cost, "daily")

        assert budget['status'] == 'critical'
        assert budget['percent_used'] == 92.0

    def test_estimate_remaining_budget_monthly(self):
        """Test budget estimation - monthly"""
        current_cost = 250.0

        budget = self.calculator.estimate_remaining_budget(current_cost, "monthly")

        assert budget['limit'] == 500.0
        assert budget['current'] == 250.0
        assert budget['remaining'] == 250.0
        assert budget['percent_used'] == 50.0
        assert budget['status'] == 'ok'

    def test_check_budget_alert_ok(self):
        """Test budget alert - OK status (no alert)"""
        alert = self.calculator.check_budget_alert(30.0, "daily")

        assert alert is None

    def test_check_budget_alert_warning(self):
        """Test budget alert - warning threshold"""
        alert = self.calculator.check_budget_alert(42.0, "daily")

        assert alert is not None
        assert "WARNING" in alert
        assert "84.0%" in alert

    def test_check_budget_alert_critical(self):
        """Test budget alert - critical threshold"""
        alert = self.calculator.check_budget_alert(46.0, "daily")

        assert alert is not None
        assert "CRITICAL" in alert
        assert "92.0%" in alert

    def test_estimate_cost_for_tokens(self):
        """Test token count to cost estimation"""
        cost = self.calculator.estimate_cost_for_tokens(10000, 5000, "claude-sonnet-4")

        # (10000/1M * $3) + (5000/1M * $15) = $0.03 + $0.075 = $0.105
        assert cost == pytest.approx(0.105, abs=0.000001)

    def test_get_cost_breakdown(self):
        """Test detailed cost breakdown"""
        usage = TokenUsage(
            input_tokens=10000,
            output_tokens=5000,
            cache_read_tokens=3000,
            cache_write_tokens=1000
        )

        breakdown = self.calculator.get_cost_breakdown(usage, "claude-sonnet-4")

        assert breakdown['model'] == "claude-sonnet-4"
        assert breakdown['input_tokens'] == 10000
        assert breakdown['output_tokens'] == 5000
        assert breakdown['cache_read_tokens'] == 3000
        assert breakdown['cache_write_tokens'] == 1000

        # Check individual costs
        assert breakdown['input_cost'] == pytest.approx(0.03, abs=0.000001)
        assert breakdown['output_cost'] == pytest.approx(0.075, abs=0.000001)
        assert breakdown['cache_read_cost'] == pytest.approx(0.0009, abs=0.000001)
        assert breakdown['cache_write_cost'] == pytest.approx(0.00375, abs=0.000001)

        # Check total
        total_expected = 0.03 + 0.075 + 0.0009 + 0.00375
        assert breakdown['total_cost'] == pytest.approx(total_expected, abs=0.000001)

        # Check cache savings (3000 tokens * ($3 - $0.30) / 1M = $0.0081)
        assert breakdown['cache_savings'] == pytest.approx(0.0081, abs=0.000001)

    def test_get_model_pricing_exact_match(self):
        """Test getting model pricing with exact match"""
        pricing = self.calculator.get_model_pricing("claude-sonnet-4")

        assert pricing['input_per_mtok'] == 3.00
        assert pricing['output_per_mtok'] == 15.00

    def test_get_model_pricing_fallback(self):
        """Test getting model pricing with fallback to default"""
        pricing = self.calculator.get_model_pricing("unknown-model")

        assert pricing['input_per_mtok'] == 3.00  # Default
        assert pricing['output_per_mtok'] == 15.00

    def test_cache_read_discount_accuracy(self):
        """Test cache read discount is exactly 90%"""
        pricing = self.calculator.get_model_pricing("claude-sonnet-4")

        input_price = pricing['input_per_mtok']
        cache_price = pricing['cache_read_per_mtok']

        # Cache read should be 10% of input (90% discount)
        assert cache_price == pytest.approx(input_price * 0.1, abs=0.01)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

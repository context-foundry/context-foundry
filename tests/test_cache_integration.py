#!/usr/bin/env python3
"""
Integration Tests for Prompt Caching
Test integration with mcp_server and cost calculation
"""

import unittest
import json
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.metrics.cost_calculator import CostCalculator
from tools.metrics.log_parser import TokenUsage


class TestCacheIntegration(unittest.TestCase):
    """Integration tests for prompt caching"""

    def test_cost_calculation_with_cached_tokens(self):
        """Test that cost calculator correctly handles cached tokens"""
        # Create token usage with cache hits
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=8500,  # Large cached section
            cache_write_tokens=0
        )

        calc = CostCalculator()
        cost = calc.calculate_cost(usage, "claude-sonnet-4")

        # Calculate expected cost
        # Input: 100 tokens × $3.00/MTok = $0.0003
        # Output: 200 tokens × $15.00/MTok = $0.003
        # Cache read: 8500 tokens × $0.30/MTok = $0.00255
        # Total: $0.00585

        expected_cost = (
            (100 / 1_000_000) * 3.00 +      # Input
            (200 / 1_000_000) * 15.00 +     # Output
            (8500 / 1_000_000) * 0.30       # Cache read
        )

        self.assertAlmostEqual(cost, expected_cost, places=6)

    def test_cost_calculation_with_cache_write(self):
        """Test cost calculation for cache creation"""
        # First request creates cache
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=0,
            cache_write_tokens=8500  # Cache creation
        )

        calc = CostCalculator()
        cost = calc.calculate_cost(usage, "claude-sonnet-4")

        # Calculate expected cost
        # Input: 100 tokens × $3.00/MTok = $0.0003
        # Output: 200 tokens × $15.00/MTok = $0.003
        # Cache write: 8500 tokens × $3.75/MTok = $0.031875
        # Total: $0.035175

        expected_cost = (
            (100 / 1_000_000) * 3.00 +      # Input
            (200 / 1_000_000) * 15.00 +     # Output
            (8500 / 1_000_000) * 3.75       # Cache write
        )

        self.assertAlmostEqual(cost, expected_cost, places=6)

    def test_cache_savings_calculation(self):
        """Test calculation of savings from caching"""
        calc = CostCalculator()

        # Usage with cache (subsequent request)
        cached_usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=8500,
            cache_write_tokens=0
        )

        # Usage without cache (first request)
        uncached_usage = TokenUsage(
            input_tokens=8600,  # 100 + 8500 (no caching)
            output_tokens=200,
            cache_read_tokens=0,
            cache_write_tokens=0
        )

        cached_cost = calc.calculate_cost(cached_usage, "claude-sonnet-4")
        uncached_cost = calc.calculate_cost(uncached_usage, "claude-sonnet-4")

        # Cached should be significantly cheaper
        self.assertLess(cached_cost, uncached_cost)

        # Calculate savings percentage
        savings_pct = ((uncached_cost - cached_cost) / uncached_cost) * 100

        # Should be around 75-90% savings
        self.assertGreater(savings_pct, 75)
        self.assertLess(savings_pct, 95)

    def test_get_cost_breakdown_with_cache(self):
        """Test detailed cost breakdown with cache tokens"""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=8500,
            cache_write_tokens=0
        )

        calc = CostCalculator()
        breakdown = calc.get_cost_breakdown(usage, "claude-sonnet-4")

        # Verify breakdown includes all components
        self.assertIn('input_tokens', breakdown)
        self.assertIn('input_cost', breakdown)
        self.assertIn('output_tokens', breakdown)
        self.assertIn('output_cost', breakdown)
        self.assertIn('cache_read_tokens', breakdown)
        self.assertIn('cache_read_cost', breakdown)
        self.assertIn('cache_savings', breakdown)
        self.assertIn('total_cost', breakdown)

        # Verify cache savings is calculated
        self.assertGreater(breakdown['cache_savings'], 0)

    def test_batch_cost_with_mixed_cache_usage(self):
        """Test batch cost calculation with mixed cache hits/misses"""
        calc = CostCalculator()

        # Build 1: Cache miss (creates cache)
        usage1 = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=0,
            cache_write_tokens=8500
        )

        # Builds 2-5: Cache hits
        usage2 = TokenUsage(input_tokens=100, output_tokens=200, cache_read_tokens=8500)
        usage3 = TokenUsage(input_tokens=100, output_tokens=200, cache_read_tokens=8500)
        usage4 = TokenUsage(input_tokens=100, output_tokens=200, cache_read_tokens=8500)
        usage5 = TokenUsage(input_tokens=100, output_tokens=200, cache_read_tokens=8500)

        # Calculate batch cost
        result = calc.calculate_batch_cost([usage1, usage2, usage3, usage4, usage5], "claude-sonnet-4")

        # Verify aggregation
        self.assertEqual(result['call_count'], 5)
        self.assertEqual(result['total_cache_write_tokens'], 8500)
        self.assertEqual(result['total_cache_read_tokens'], 8500 * 4)

        # Total cost should be significantly less than 5× non-cached requests
        no_cache_cost = 5 * ((8600 / 1_000_000) * 3.00 + (200 / 1_000_000) * 15.00)
        self.assertLess(result['total_cost'], no_cache_cost * 0.5)  # At least 50% savings

    @unittest.skip("Requires fastmcp package - tested manually in E2E")
    @patch('subprocess.Popen')
    def test_mcp_server_uses_cached_prompts(self, mock_popen):
        """Test that autonomous_build_and_deploy uses cached prompt builder"""
        # Mock the subprocess
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        # Import after mocking - requires fastmcp
        from tools.mcp_server import autonomous_build_and_deploy

        # Call autonomous build
        result = autonomous_build_and_deploy(
            task="Test build",
            working_directory="/tmp/test-cache",
            mode="new_project"
        )

        # Verify subprocess was called
        self.assertTrue(mock_popen.called)

        # Get the command that was executed
        call_args = mock_popen.call_args
        cmd = call_args[0][0]

        # Verify command structure
        self.assertIn("claude", cmd[0])
        self.assertIn("--system-prompt", cmd)

        # Get system prompt
        system_prompt_idx = cmd.index("--system-prompt") + 1
        system_prompt = cmd[system_prompt_idx]

        # Verify system prompt contains task configuration
        # (either in cached or fallback format)
        self.assertIn("CONFIGURATION", system_prompt)

    def test_cache_hit_rate_tracking(self):
        """Test tracking of cache hit rates"""
        calc = CostCalculator()

        # Simulate 10 builds: 1 cache miss, 9 cache hits
        usages = []

        # Build 1: Cache miss
        usages.append(TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_write_tokens=8500
        ))

        # Builds 2-10: Cache hits
        for _ in range(9):
            usages.append(TokenUsage(
                input_tokens=100,
                output_tokens=200,
                cache_read_tokens=8500
            ))

        # Count cache hits/misses
        cache_hits = sum(1 for u in usages if u.cache_read_tokens > 0)
        cache_misses = sum(1 for u in usages if u.cache_write_tokens > 0)
        hit_rate = cache_hits / len(usages) * 100

        self.assertEqual(cache_hits, 9)
        self.assertEqual(cache_misses, 1)
        self.assertEqual(hit_rate, 90.0)

    def test_extended_ttl_cost_comparison(self):
        """Test cost comparison between 5m and 1h cache TTL"""
        calc = CostCalculator()

        # 5m cache write
        usage_5m = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_write_tokens=8500  # $3.75/MTok
        )

        # 1h cache write (2× cost)
        # Note: Currently not distinguished in TokenUsage, but would be in future
        usage_1h = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_write_tokens=8500  # Would be $7.50/MTok for 1h
        )

        cost_5m = calc.calculate_cost(usage_5m, "claude-sonnet-4")

        # For 1h cache, cost would be approximately 2× the 5m cache write cost
        # (not yet implemented in pricing, but would be:)
        # expected_cost_1h = cost_5m + (8500 / 1_000_000) * 3.75

        # This test documents the expected behavior once extended TTL pricing is added
        self.assertGreater(cost_5m, 0)


class TestCacheMetrics(unittest.TestCase):
    """Test cache metrics and tracking"""

    def test_cache_metrics_in_token_usage(self):
        """Test that TokenUsage properly stores cache metrics"""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=8500,
            cache_write_tokens=0,
            model="claude-sonnet-4"
        )

        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 200)
        self.assertEqual(usage.cache_read_tokens, 8500)
        self.assertEqual(usage.cache_write_tokens, 0)

    def test_token_usage_defaults(self):
        """Test TokenUsage default values"""
        # TokenUsage requires input_tokens and output_tokens
        usage = TokenUsage(input_tokens=0, output_tokens=0)

        self.assertEqual(usage.input_tokens, 0)
        self.assertEqual(usage.output_tokens, 0)
        self.assertEqual(usage.cache_read_tokens, 0)
        self.assertEqual(usage.cache_write_tokens, 0)


if __name__ == '__main__':
    unittest.main()

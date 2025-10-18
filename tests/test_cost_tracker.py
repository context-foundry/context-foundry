#!/usr/bin/env python3
"""
Comprehensive unit tests for CostTracker.

Tests cover:
- Cost calculation across multiple providers
- Phase-based usage tracking
- Token aggregation
- Pricing database integration
- Fallback pricing mechanisms
- Summary and reporting
- JSON export functionality
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from ace.cost_tracker import CostTracker, PhaseUsage
from ace.providers.base_provider import ModelPricing


# ============================================================================
# PHASE USAGE TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestPhaseUsage:
    """Test PhaseUsage dataclass."""

    def test_phase_usage_creation(self):
        """Test creating PhaseUsage instance."""
        # Arrange & Act
        usage = PhaseUsage(
            phase="scout",
            provider="anthropic",
            model="claude-3-5-haiku-20241022",
            input_tokens=1000,
            output_tokens=500,
            cost=0.05
        )

        # Assert
        assert usage.phase == "scout"
        assert usage.provider == "anthropic"
        assert usage.model == "claude-3-5-haiku-20241022"
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.cost == 0.05

    def test_phase_usage_total_tokens(self):
        """Test total_tokens property calculation."""
        # Arrange
        usage = PhaseUsage(
            phase="builder",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=2000,
            output_tokens=1500
        )

        # Act
        total = usage.total_tokens

        # Assert
        assert total == 3500  # 2000 + 1500

    def test_phase_usage_defaults(self):
        """Test PhaseUsage with default values."""
        # Arrange & Act
        usage = PhaseUsage(
            phase="test",
            provider="test_provider",
            model="test_model"
        )

        # Assert
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cost == 0.0


# ============================================================================
# COST TRACKER INITIALIZATION TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestCostTrackerInit:
    """Test CostTracker initialization."""

    def test_init_with_default_db(self):
        """Test initialization with default database."""
        # Arrange & Act
        tracker = CostTracker()

        # Assert
        assert tracker.db is not None
        assert isinstance(tracker.phase_usage, dict)
        assert len(tracker.phase_usage) == 0
        assert isinstance(tracker.call_history, list)
        assert len(tracker.call_history) == 0

    def test_init_with_custom_db(self):
        """Test initialization with custom database."""
        # Arrange
        mock_db = Mock()

        # Act
        tracker = CostTracker(db=mock_db)

        # Assert
        assert tracker.db is mock_db


# ============================================================================
# TRACK USAGE TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestTrackUsage:
    """Test usage tracking functionality."""

    def test_track_usage_basic(self, sample_pricing):
        """Test basic usage tracking."""
        # Arrange
        mock_db = Mock()
        mock_db.get_pricing.return_value = sample_pricing
        tracker = CostTracker(db=mock_db)

        # Act
        tracker.track_usage(
            phase="scout",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=500
        )

        # Assert
        assert "scout" in tracker.phase_usage
        usage = tracker.phase_usage["scout"]
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.cost > 0  # Should have calculated cost

        # Verify database was queried
        mock_db.get_pricing.assert_called_once_with("anthropic", "claude-3-5-sonnet-20241022")

    def test_track_usage_cost_calculation(self):
        """Test correct cost calculation."""
        # Arrange
        mock_db = Mock()
        pricing = ModelPricing(
            model="claude-3-5-sonnet-20241022",
            input_cost_per_1m=3.00,  # $3 per 1M input tokens
            output_cost_per_1m=15.00,  # $15 per 1M output tokens
            context_window=200000,
            updated_at=datetime.now()
        )
        mock_db.get_pricing.return_value = pricing
        tracker = CostTracker(db=mock_db)

        # Act
        tracker.track_usage(
            phase="builder",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=100_000,  # 0.1M tokens
            output_tokens=50_000   # 0.05M tokens
        )

        # Assert
        usage = tracker.phase_usage["builder"]
        # Expected cost: (100k/1M * $3) + (50k/1M * $15) = $0.30 + $0.75 = $1.05
        expected_cost = (100_000 / 1_000_000 * 3.00) + (50_000 / 1_000_000 * 15.00)
        assert abs(usage.cost - expected_cost) < 0.01  # Allow small floating point difference

    def test_track_usage_accumulation(self):
        """Test that multiple calls to same phase accumulate."""
        # Arrange
        mock_db = Mock()
        pricing = ModelPricing(
            model="gpt-4o-mini",
            input_cost_per_1m=0.15,
            output_cost_per_1m=0.60,
            context_window=128000,
            updated_at=datetime.now()
        )
        mock_db.get_pricing.return_value = pricing
        tracker = CostTracker(db=mock_db)

        # Act
        tracker.track_usage("scout", "openai", "gpt-4o-mini", 1000, 500)
        tracker.track_usage("scout", "openai", "gpt-4o-mini", 2000, 1000)
        tracker.track_usage("scout", "openai", "gpt-4o-mini", 1500, 750)

        # Assert
        usage = tracker.phase_usage["scout"]
        assert usage.input_tokens == 4500  # 1000 + 2000 + 1500
        assert usage.output_tokens == 2250  # 500 + 1000 + 750
        # Cost should accumulate as well

    def test_track_usage_multiple_phases(self):
        """Test tracking across multiple phases."""
        # Arrange
        mock_db = Mock()
        pricing = ModelPricing(
            model="test-model",
            input_cost_per_1m=1.00,
            output_cost_per_1m=2.00,
            context_window=100000,
            updated_at=datetime.now()
        )
        mock_db.get_pricing.return_value = pricing
        tracker = CostTracker(db=mock_db)

        # Act
        tracker.track_usage("scout", "anthropic", "test-model", 1000, 500)
        tracker.track_usage("architect", "anthropic", "test-model", 2000, 1000)
        tracker.track_usage("builder", "anthropic", "test-model", 3000, 1500)

        # Assert
        assert len(tracker.phase_usage) == 3
        assert "scout" in tracker.phase_usage
        assert "architect" in tracker.phase_usage
        assert "builder" in tracker.phase_usage

    def test_track_usage_no_pricing_available(self):
        """Test handling when pricing is not available."""
        # Arrange
        mock_db = Mock()
        mock_db.get_pricing.return_value = None  # No pricing in DB
        tracker = CostTracker(db=mock_db)

        # Patch at the correct location where it's imported
        with patch('ace.provider_registry.get_registry') as mock_registry:
            # Mock provider fallback also fails
            mock_registry.return_value.get.side_effect = Exception("Provider not found")

            tracker = CostTracker(db=mock_db)

            # Act
            tracker.track_usage("test", "unknown_provider", "unknown_model", 1000, 500)

            # Assert
            usage = tracker.phase_usage["test"]
            assert usage.cost == 0.0  # Should default to 0 when no pricing available
            assert usage.input_tokens == 1000
            assert usage.output_tokens == 500

    def test_track_usage_with_fallback_pricing(self):
        """Test fallback to provider pricing when DB doesn't have it."""
        # Arrange
        mock_db = Mock()
        mock_db.get_pricing.return_value = None  # Not in DB

        # Mock provider registry fallback
        fallback_pricing = ModelPricing(
            model="test-model",
            input_cost_per_1m=2.00,
            output_cost_per_1m=4.00,
            context_window=100000,
            updated_at=datetime.now()
        )

        mock_provider = Mock()
        mock_provider._get_fallback_pricing.return_value = {
            "test-model": fallback_pricing
        }

        # Patch at the correct location where it's imported
        with patch('ace.provider_registry.get_registry') as mock_registry:
            mock_registry.return_value.get.return_value = mock_provider

            tracker = CostTracker(db=mock_db)

            # Act
            tracker.track_usage("test", "test", "test-model", 1_000_000, 500_000)

            # Assert
            usage = tracker.phase_usage["test"]
            # Cost: (1M/1M * $2) + (0.5M/1M * $4) = $2 + $2 = $4
            assert abs(usage.cost - 4.0) < 0.01

    def test_track_usage_call_history(self):
        """Test that call history is recorded correctly."""
        # Arrange
        mock_db = Mock()
        pricing = ModelPricing(
            model="test-model",
            input_cost_per_1m=1.0,
            output_cost_per_1m=1.0,
            context_window=100000,
            updated_at=datetime.now()
        )
        mock_db.get_pricing.return_value = pricing
        tracker = CostTracker(db=mock_db)

        # Act
        tracker.track_usage("scout", "test", "test-model", 1000, 500)
        tracker.track_usage("builder", "test", "test-model", 2000, 1000)

        # Assert
        assert len(tracker.call_history) == 2
        assert tracker.call_history[0]['phase'] == "scout"
        assert tracker.call_history[1]['phase'] == "builder"
        assert tracker.call_history[0]['input_tokens'] == 1000
        assert tracker.call_history[1]['input_tokens'] == 2000


# ============================================================================
# COST RETRIEVAL TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestCostRetrieval:
    """Test cost retrieval methods."""

    def test_get_phase_cost_existing(self):
        """Test getting cost for existing phase."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            phase="scout",
            provider="test",
            model="test-model",
            cost=1.25
        )

        # Act
        cost = tracker.get_phase_cost("scout")

        # Assert
        assert cost == 1.25

    def test_get_phase_cost_nonexistent(self):
        """Test getting cost for non-existent phase returns 0."""
        # Arrange
        tracker = CostTracker()

        # Act
        cost = tracker.get_phase_cost("nonexistent")

        # Assert
        assert cost == 0.0

    def test_get_total_cost_single_phase(self):
        """Test total cost with single phase."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            phase="scout",
            provider="test",
            model="test",
            cost=2.50
        )

        # Act
        total = tracker.get_total_cost()

        # Assert
        assert total == 2.50

    def test_get_total_cost_multiple_phases(self):
        """Test total cost across multiple phases."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage("scout", "test", "test", cost=1.00)
        tracker.phase_usage["architect"] = PhaseUsage("architect", "test", "test", cost=2.50)
        tracker.phase_usage["builder"] = PhaseUsage("builder", "test", "test", cost=3.75)

        # Act
        total = tracker.get_total_cost()

        # Assert
        assert abs(total - 7.25) < 0.01  # 1.00 + 2.50 + 3.75

    def test_get_total_cost_empty(self):
        """Test total cost with no phases."""
        # Arrange
        tracker = CostTracker()

        # Act
        total = tracker.get_total_cost()

        # Assert
        assert total == 0.0


# ============================================================================
# TOKEN RETRIEVAL TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestTokenRetrieval:
    """Test token retrieval methods."""

    def test_get_total_tokens_single_phase(self):
        """Test total tokens with single phase."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            phase="scout",
            provider="test",
            model="test",
            input_tokens=1000,
            output_tokens=500
        )

        # Act
        total = tracker.get_total_tokens()

        # Assert
        assert total == 1500  # 1000 + 500

    def test_get_total_tokens_multiple_phases(self):
        """Test total tokens across multiple phases."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            "scout", "test", "test",
            input_tokens=1000, output_tokens=500
        )
        tracker.phase_usage["architect"] = PhaseUsage(
            "architect", "test", "test",
            input_tokens=2000, output_tokens=1000
        )
        tracker.phase_usage["builder"] = PhaseUsage(
            "builder", "test", "test",
            input_tokens=3000, output_tokens=1500
        )

        # Act
        total = tracker.get_total_tokens()

        # Assert
        # (1000+500) + (2000+1000) + (3000+1500) = 1500 + 3000 + 4500 = 9000
        assert total == 9000


# ============================================================================
# SUMMARY TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestGetSummary:
    """Test summary generation."""

    def test_get_summary_structure(self):
        """Test summary has correct structure."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            "scout", "anthropic", "claude-3-5-haiku-20241022",
            input_tokens=1000, output_tokens=500, cost=0.10
        )

        # Act
        summary = tracker.get_summary()

        # Assert
        assert 'phases' in summary
        assert 'total_cost' in summary
        assert 'total_tokens' in summary
        assert 'total_input_tokens' in summary
        assert 'total_output_tokens' in summary
        assert 'calls' in summary

    def test_get_summary_phase_details(self):
        """Test summary includes phase details."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["builder"] = PhaseUsage(
            "builder", "openai", "gpt-4o-mini",
            input_tokens=2000, output_tokens=1000, cost=0.25
        )

        # Act
        summary = tracker.get_summary()

        # Assert
        assert "builder" in summary['phases']
        phase = summary['phases']['builder']
        assert phase['provider'] == "openai"
        assert phase['model'] == "gpt-4o-mini"
        assert phase['input_tokens'] == 2000
        assert phase['output_tokens'] == 1000
        assert phase['total_tokens'] == 3000
        assert phase['cost'] == 0.25

    def test_get_summary_multiple_phases(self):
        """Test summary with multiple phases."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            "scout", "anthropic", "haiku", input_tokens=1000, output_tokens=500, cost=0.10
        )
        tracker.phase_usage["architect"] = PhaseUsage(
            "architect", "anthropic", "sonnet", input_tokens=2000, output_tokens=1000, cost=0.50
        )
        tracker.call_history = [{"test": 1}, {"test": 2}, {"test": 3}]

        # Act
        summary = tracker.get_summary()

        # Assert
        assert len(summary['phases']) == 2
        assert summary['total_cost'] == 0.60  # 0.10 + 0.50
        assert summary['total_tokens'] == 4500  # (1000+500) + (2000+1000)
        assert summary['total_input_tokens'] == 3000
        assert summary['total_output_tokens'] == 1500
        assert summary['calls'] == 3


# ============================================================================
# FORMAT SUMMARY TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestFormatSummary:
    """Test summary formatting."""

    def test_format_summary_verbose(self):
        """Test verbose summary formatting."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            "scout", "anthropic", "claude-haiku",
            input_tokens=1000, output_tokens=500, cost=0.10
        )
        tracker.phase_usage["builder"] = PhaseUsage(
            "builder", "openai", "gpt-4o-mini",
            input_tokens=2000, output_tokens=1000, cost=0.25
        )

        # Act
        formatted = tracker.format_summary(verbose=True)

        # Assert
        assert "COST SUMMARY" in formatted
        assert "Scout Phase" in formatted
        assert "Builder Phase" in formatted
        assert "TOTAL COST" in formatted
        assert "$0.35" in formatted  # 0.10 + 0.25

    def test_format_summary_compact(self):
        """Test compact summary formatting."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["test"] = PhaseUsage(
            "test", "test", "test",
            input_tokens=1000, output_tokens=500, cost=1.50
        )

        # Act
        formatted = tracker.format_summary(verbose=False)

        # Assert
        assert "Total Cost: $1.50" in formatted
        assert "1,500 tokens" in formatted
        assert "COST SUMMARY" not in formatted  # Should be compact

    def test_format_summary_empty(self):
        """Test formatting empty summary."""
        # Arrange
        tracker = CostTracker()

        # Act
        formatted = tracker.format_summary(verbose=False)

        # Assert
        assert "$0.00" in formatted


# ============================================================================
# EXPORT JSON TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestExportJson:
    """Test JSON export functionality."""

    def test_export_json_structure(self):
        """Test JSON export has correct structure."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["scout"] = PhaseUsage(
            "scout", "anthropic", "test",
            input_tokens=1000, output_tokens=500, cost=0.10
        )
        tracker.call_history = [{"phase": "scout", "cost": 0.10}]

        # Act
        exported = tracker.export_json()

        # Assert
        assert 'summary' in exported
        assert 'call_history' in exported
        assert 'phase_usage' in exported

    def test_export_json_phase_usage(self):
        """Test JSON export includes phase usage details."""
        # Arrange
        tracker = CostTracker()
        tracker.phase_usage["builder"] = PhaseUsage(
            "builder", "openai", "gpt-4o",
            input_tokens=5000, output_tokens=2500, cost=2.75
        )

        # Act
        exported = tracker.export_json()

        # Assert
        assert "builder" in exported['phase_usage']
        phase = exported['phase_usage']['builder']
        assert phase['provider'] == "openai"
        assert phase['model'] == "gpt-4o"
        assert phase['input_tokens'] == 5000
        assert phase['output_tokens'] == 2500
        assert phase['cost'] == 2.75

    def test_export_json_call_history(self):
        """Test JSON export includes call history."""
        # Arrange
        tracker = CostTracker()
        tracker.call_history = [
            {"phase": "scout", "cost": 0.10},
            {"phase": "builder", "cost": 0.25}
        ]

        # Act
        exported = tracker.export_json()

        # Assert
        assert len(exported['call_history']) == 2
        assert exported['call_history'][0]['phase'] == "scout"
        assert exported['call_history'][1]['phase'] == "builder"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.integration
@pytest.mark.tier1
class TestCostTrackerIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow_multiple_providers(self):
        """Test complete workflow with multiple providers."""
        # Arrange
        mock_db = Mock()

        # Different pricing for different models
        anthropic_pricing = ModelPricing(
            model="claude",
            input_cost_per_1m=3.00,
            output_cost_per_1m=15.00,
            context_window=200000,
            updated_at=datetime.now()
        )
        openai_pricing = ModelPricing(
            model="gpt-4o-mini",
            input_cost_per_1m=0.15,
            output_cost_per_1m=0.60,
            context_window=128000,
            updated_at=datetime.now()
        )

        def get_pricing_side_effect(provider, model):
            if provider == "anthropic":
                return anthropic_pricing
            elif provider == "openai":
                return openai_pricing
            return None

        mock_db.get_pricing.side_effect = get_pricing_side_effect
        tracker = CostTracker(db=mock_db)

        # Act - Track usage across multiple phases and providers
        tracker.track_usage("scout", "openai", "gpt-4o-mini", 10_000, 5_000)
        tracker.track_usage("architect", "anthropic", "claude", 20_000, 10_000)
        tracker.track_usage("builder", "anthropic", "claude", 50_000, 25_000)

        # Assert
        summary = tracker.get_summary()
        assert len(summary['phases']) == 3
        assert summary['total_cost'] > 0
        assert summary['calls'] == 3

        # Verify Scout phase (OpenAI)
        scout = summary['phases']['scout']
        assert scout['provider'] == "openai"

        # Verify total tokens
        total_tokens = 10_000 + 5_000 + 20_000 + 10_000 + 50_000 + 25_000
        assert summary['total_tokens'] == total_tokens


# ============================================================================
# EDGE CASES
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_tokens(self):
        """Test tracking with zero tokens."""
        # Arrange
        mock_db = Mock()
        pricing = ModelPricing(
            model="test",
            input_cost_per_1m=1.0,
            output_cost_per_1m=1.0,
            context_window=100000,
            updated_at=datetime.now()
        )
        mock_db.get_pricing.return_value = pricing
        tracker = CostTracker(db=mock_db)

        # Act
        tracker.track_usage("test", "test", "test", 0, 0)

        # Assert
        usage = tracker.phase_usage["test"]
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cost == 0.0

    def test_large_token_counts(self):
        """Test with very large token counts."""
        # Arrange
        mock_db = Mock()
        pricing = ModelPricing(
            model="test",
            input_cost_per_1m=3.0,
            output_cost_per_1m=15.0,
            context_window=100000,
            updated_at=datetime.now()
        )
        mock_db.get_pricing.return_value = pricing
        tracker = CostTracker(db=mock_db)

        # Act - 10 million tokens
        tracker.track_usage("test", "test", "test", 10_000_000, 5_000_000)

        # Assert
        usage = tracker.phase_usage["test"]
        # Cost: (10M/1M * 3) + (5M/1M * 15) = 30 + 75 = 105
        expected_cost = 105.0
        assert abs(usage.cost - expected_cost) < 0.01

    def test_precision_with_small_costs(self):
        """Test cost precision with very small costs."""
        # Arrange
        mock_db = Mock()
        pricing = ModelPricing(
            model="test",
            input_cost_per_1m=0.001,
            output_cost_per_1m=0.002,
            context_window=100000,
            updated_at=datetime.now()
        )
        mock_db.get_pricing.return_value = pricing
        tracker = CostTracker(db=mock_db)

        # Act - Small number of tokens
        tracker.track_usage("test", "test", "test", 100, 50)

        # Assert
        usage = tracker.phase_usage["test"]
        # Cost should be very small but non-zero
        assert usage.cost > 0
        assert usage.cost < 0.01

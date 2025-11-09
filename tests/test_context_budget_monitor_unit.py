#!/usr/bin/env python3
"""
Unit Tests for Context Budget Monitor

Tests the ContextBudgetMonitor class which monitors context window usage,
enforces budgets, and detects performance zones (SMART/DUMB/CRITICAL).

Test Coverage:
- Initialization
- Budget calculations
- Zone detection
- Phase analysis
- Historical tracking
- Overall statistics
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.context_budget.monitor import (
    ContextBudgetMonitor,
    ContextZone,
    PhaseAnalysis
)


class TestContextBudgetMonitorInitialization:
    """Test ContextBudgetMonitor initialization"""

    def test_default_initialization(self):
        """Test monitor initializes with default 200K context window"""
        monitor = ContextBudgetMonitor()

        assert monitor.context_window_size == 200000
        assert monitor.model == 'claude-sonnet-4'
        assert isinstance(monitor._phase_history, dict)
        assert len(monitor._phase_history) == 0

    def test_custom_context_window(self):
        """Test monitor initializes with custom context window size"""
        monitor = ContextBudgetMonitor(context_window_size=128000)

        assert monitor.context_window_size == 128000

    def test_custom_model(self):
        """Test monitor initializes with custom model name"""
        monitor = ContextBudgetMonitor(model='gpt-4')

        assert monitor.model == 'gpt-4'


class TestBudgetCalculations:
    """Test budget allocation calculations"""

    def test_get_budget_for_scout_phase(self):
        """Test Scout phase gets 7% budget allocation"""
        monitor = ContextBudgetMonitor(context_window_size=200000)
        budget = monitor.get_budget_for_phase('scout')

        assert budget == 14000  # 7% of 200K

    def test_get_budget_for_builder_phase(self):
        """Test Builder phase gets 20% budget allocation"""
        monitor = ContextBudgetMonitor(context_window_size=200000)
        budget = monitor.get_budget_for_phase('builder')

        assert budget == 40000  # 20% of 200K

    def test_normalized_phase_names(self):
        """Test phase name normalization (spaces, hyphens, underscores)"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # All these should map to the same phase
        budget1 = monitor.get_budget_for_phase('scout')
        budget2 = monitor.get_budget_for_phase('Scout')
        budget3 = monitor.get_budget_for_phase('SCOUT')

        assert budget1 == budget2 == budget3

    def test_unknown_phase_defaults(self):
        """Test unknown phase defaults to 5% budget"""
        monitor = ContextBudgetMonitor(context_window_size=200000)
        budget = monitor.get_budget_for_phase('unknown_phase')

        assert budget == 10000  # 5% of 200K

    def test_budget_with_zero_context_window(self):
        """Test budget calculation handles 0 context window gracefully"""
        monitor = ContextBudgetMonitor(context_window_size=0)
        budget = monitor.get_budget_for_phase('scout')

        assert budget == 0


class TestZoneDetection:
    """Test context usage zone detection"""

    def test_smart_zone_detection(self):
        """Test SMART zone detection (0-40%)"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Test various percentages in SMART zone
        assert monitor.get_zone(0) == ContextZone.SMART
        assert monitor.get_zone(10000) == ContextZone.SMART  # 5%
        assert monitor.get_zone(40000) == ContextZone.SMART  # 20%
        assert monitor.get_zone(80000) == ContextZone.SMART  # 40%

    def test_dumb_zone_detection(self):
        """Test DUMB zone detection (40-80%)"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Just above 40%
        assert monitor.get_zone(80001) == ContextZone.DUMB
        assert monitor.get_zone(100000) == ContextZone.DUMB  # 50%
        assert monitor.get_zone(120000) == ContextZone.DUMB  # 60%

    def test_critical_zone_detection(self):
        """Test CRITICAL zone detection (80-100%)"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # 80% and above
        assert monitor.get_zone(160000) == ContextZone.CRITICAL  # 80%
        assert monitor.get_zone(180000) == ContextZone.CRITICAL  # 90%
        assert monitor.get_zone(200000) == ContextZone.CRITICAL  # 100%

    def test_zone_boundary_at_40_percent(self):
        """Test zone boundary exactly at 40%"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Exactly 40% should be SMART
        assert monitor.get_zone(80000) == ContextZone.SMART

    def test_zone_boundary_at_80_percent(self):
        """Test zone boundary exactly at 80%"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Exactly 80% should be CRITICAL
        assert monitor.get_zone(160000) == ContextZone.CRITICAL

    def test_is_in_smart_zone(self):
        """Test is_in_smart_zone() helper method"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        assert monitor.is_in_smart_zone(40000) is True
        assert monitor.is_in_smart_zone(80000) is True
        assert monitor.is_in_smart_zone(80001) is False


class TestPhaseAnalysis:
    """Test phase analysis functionality"""

    def test_check_phase_typical_usage(self):
        """Test check_phase() with typical usage"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        analysis = monitor.check_phase('Scout', 12000)

        assert analysis.phase_name == 'Scout'
        assert analysis.tokens_used == 12000
        assert analysis.percentage == pytest.approx(6.0, abs=0.1)
        assert analysis.zone == ContextZone.SMART
        assert analysis.budget_allocated == 14000
        assert analysis.budget_remaining == 2000
        assert analysis.budget_exceeded_by == 0

    def test_phase_analysis_warnings_for_exceeded_budget(self):
        """Test warnings generation when budget exceeded"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Scout phase: budget is 14K, use 20K (exceeded)
        analysis = monitor.check_phase('Scout', 20000)

        assert analysis.budget_exceeded_by == 6000
        assert len(analysis.warnings) > 0
        assert any('exceeded budget' in w.lower() for w in analysis.warnings)

    def test_phase_analysis_warnings_for_critical_zone(self):
        """Test warnings generation for CRITICAL zone"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Use 170K tokens (85%)
        analysis = monitor.check_phase('Builder', 170000)

        assert analysis.zone == ContextZone.CRITICAL
        assert len(analysis.warnings) > 0
        assert any('CRITICAL' in w for w in analysis.warnings)

    def test_phase_analysis_recommendations_for_exceeded_budget(self):
        """Test recommendations generation for exceeded budget"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Exceed budget significantly
        analysis = monitor.check_phase('Scout', 30000)

        assert len(analysis.recommendations) > 0

    def test_budget_remaining_calculation(self):
        """Test budget_remaining is calculated correctly"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Use 10K out of 14K budget
        analysis = monitor.check_phase('Scout', 10000)

        assert analysis.budget_remaining == 4000

    def test_phase_history_tracking(self):
        """Test phase analyses are stored in history"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        monitor.check_phase('Scout', 12000)
        monitor.check_phase('Scout', 15000)

        history = monitor.get_phase_history('Scout')
        assert len(history) == 2
        assert history[0].tokens_used == 12000
        assert history[1].tokens_used == 15000

    def test_percentage_calculation_accuracy(self):
        """Test percentage calculation is accurate"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # 50% usage
        analysis = monitor.check_phase('Builder', 100000)

        assert analysis.percentage == pytest.approx(50.0, abs=0.1)

    def test_phase_analysis_to_dict_serialization(self):
        """Test PhaseAnalysis.to_dict() produces valid structure"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        analysis = monitor.check_phase('Scout', 12000)
        result = analysis.to_dict()

        assert isinstance(result, dict)
        assert 'phase_name' in result
        assert 'tokens_used' in result
        assert 'percentage' in result
        assert 'zone' in result
        assert result['phase_name'] == 'Scout'
        assert result['tokens_used'] == 12000
        assert result['zone'] == 'smart'


class TestHistoricalTracking:
    """Test historical analysis tracking"""

    def test_get_phase_history_returns_correct_analyses(self):
        """Test get_phase_history() returns analyses for specific phase"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        monitor.check_phase('Scout', 12000)
        monitor.check_phase('Architect', 10000)
        monitor.check_phase('Scout', 15000)

        scout_history = monitor.get_phase_history('Scout')
        assert len(scout_history) == 2

        architect_history = monitor.get_phase_history('Architect')
        assert len(architect_history) == 1

    def test_multiple_analyses_for_same_phase(self):
        """Test multiple analyses for the same phase are tracked"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        for i in range(5):
            monitor.check_phase('Builder', 10000 + i * 1000)

        history = monitor.get_phase_history('Builder')
        assert len(history) == 5

    def test_empty_history_for_new_phase(self):
        """Test get_phase_history() returns empty list for untracked phase"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        history = monitor.get_phase_history('NonExistent')
        assert history == []


class TestOverallStatistics:
    """Test overall statistics calculation"""

    def test_get_overall_stats_with_multiple_phases(self):
        """Test get_overall_stats() aggregates across all phases"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        monitor.check_phase('Scout', 12000)
        monitor.check_phase('Architect', 10000)
        monitor.check_phase('Builder', 40000)

        stats = monitor.get_overall_stats()

        assert stats['total_phases'] == 3
        assert stats['peak_phase'] == 'Builder'
        assert stats['peak_usage_tokens'] == 40000

    def test_peak_usage_detection(self):
        """Test peak usage is correctly identified"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        monitor.check_phase('Scout', 12000)
        monitor.check_phase('Builder', 50000)  # Peak
        monitor.check_phase('Test', 30000)

        stats = monitor.get_overall_stats()

        assert stats['peak_usage_tokens'] == 50000
        assert stats['peak_phase'] == 'Builder'

    def test_smart_zone_percentage_calculation(self):
        """Test smart zone percentage is calculated correctly"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # 2 in SMART, 1 in DUMB
        monitor.check_phase('Scout', 12000)    # SMART (6%)
        monitor.check_phase('Builder', 40000)  # SMART (20%)
        monitor.check_phase('Test', 100000)    # DUMB (50%)

        stats = monitor.get_overall_stats()

        # 2 out of 3 = 66.67%
        assert stats['smart_zone_percentage'] == pytest.approx(66.67, abs=0.1)


class TestExportToSessionSummary:
    """Test export to session-summary.json format"""

    def test_export_to_session_summary_structure(self):
        """Test export_to_session_summary() produces correct structure"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        monitor.check_phase('Scout', 12000)
        monitor.check_phase('Builder', 40000)

        export = monitor.export_to_session_summary()

        assert 'max_context_window' in export
        assert 'model' in export
        assert 'by_phase' in export
        assert 'overall' in export
        assert export['max_context_window'] == 200000
        assert export['model'] == 'claude-sonnet-4'

    def test_export_includes_latest_phase_analysis(self):
        """Test export uses most recent analysis for each phase"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        monitor.check_phase('Scout', 10000)
        monitor.check_phase('Scout', 15000)  # Latest

        export = monitor.export_to_session_summary()

        # Should use latest analysis (15000)
        assert export['by_phase']['phase_scout']['tokens_used'] == 15000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

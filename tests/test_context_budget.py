#!/usr/bin/env python3
"""
Comprehensive tests for context budget monitoring system
"""

import pytest
from pathlib import Path
import tempfile
import json

from tools.context_budget import (
    ContextBudgetMonitor,
    PhaseAnalysis,
    ContextZone,
    TokenCounter,
    estimate_tokens,
    ContextBudgetReporter,
)


class TestTokenCounter:
    """Test token counting functionality"""

    def test_estimate_tokens_basic(self):
        """Test basic token estimation"""
        counter = TokenCounter()

        # Empty string
        assert counter.estimate_tokens("") == 0

        # Simple text
        text = "Hello, world!"
        tokens = counter.estimate_tokens(text)
        assert tokens > 0
        assert tokens < len(text)  # Tokens should be less than character count

    def test_estimate_tokens_long_text(self):
        """Test token estimation on longer text"""
        counter = TokenCounter()

        text = "This is a longer piece of text. " * 100
        tokens = counter.estimate_tokens(text)

        # Rough validation: should be approximately text_length / 4
        expected_range = (len(text) // 5, len(text) // 3)
        assert expected_range[0] <= tokens <= expected_range[1]

    def test_count_file_tokens(self):
        """Test counting tokens in a file"""
        counter = TokenCounter()

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("def hello():\n    print('Hello, world!')\n")
            temp_path = Path(f.name)

        try:
            tokens = counter.count_file_tokens(temp_path)
            assert tokens > 0
            assert tokens < 100  # Should be small for this simple file
        finally:
            temp_path.unlink()

    def test_count_file_tokens_nonexistent(self):
        """Test counting tokens in nonexistent file"""
        counter = TokenCounter()
        tokens = counter.count_file_tokens(Path('/nonexistent/file.txt'))
        assert tokens == 0

    def test_count_message_tokens(self):
        """Test counting tokens in message array"""
        counter = TokenCounter()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        tokens = counter.count_message_tokens(messages)
        assert tokens > 0
        # Should include role tokens, content tokens, and overhead
        assert tokens > len("Hello") // 4  # At minimum

    def test_count_message_tokens_multipart(self):
        """Test counting tokens with multi-part content"""
        counter = TokenCounter()

        messages = [
            {
                "role": "user",
                "content": [
                    {"text": "What's in this image?"},
                    {"type": "image"}  # Images not counted in text tokens
                ]
            }
        ]

        tokens = counter.count_message_tokens(messages)
        assert tokens > 0

    def test_get_context_window_size(self):
        """Test getting context window size for models"""
        counter = TokenCounter('claude-sonnet-4')
        assert counter.get_context_window_size() == 200000

        counter_gpt = TokenCounter('gpt-4')
        assert counter_gpt.get_context_window_size() == 128000

    def test_estimate_tokens_convenience_function(self):
        """Test convenience function"""
        tokens = estimate_tokens("Hello, world!")
        assert tokens > 0


class TestContextBudgetMonitor:
    """Test context budget monitoring"""

    def test_initialization(self):
        """Test monitor initialization"""
        monitor = ContextBudgetMonitor(context_window_size=200000, model='claude-sonnet-4')
        assert monitor.context_window_size == 200000
        assert monitor.model == 'claude-sonnet-4'

    def test_get_budget_for_phase(self):
        """Test budget allocation for phases"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Scout: 7% of 200K = 14K
        assert monitor.get_budget_for_phase('scout') == 14000

        # Architect: 7% of 200K = 14K
        assert monitor.get_budget_for_phase('architect') == 14000

        # Builder: 20% of 200K = 40K
        assert monitor.get_budget_for_phase('builder') == 40000

        # Unknown phase: 5% default
        assert monitor.get_budget_for_phase('unknown_phase') == 10000

    def test_is_in_smart_zone(self):
        """Test smart zone detection"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # 0-40% is smart zone
        assert monitor.is_in_smart_zone(0)
        assert monitor.is_in_smart_zone(40000)  # 20%
        assert monitor.is_in_smart_zone(80000)  # 40%

        # >40% is not smart zone
        assert not monitor.is_in_smart_zone(85000)  # 42.5%
        assert not monitor.is_in_smart_zone(160000)  # 80%

    def test_get_zone(self):
        """Test zone detection"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Smart zone: 0-40%
        assert monitor.get_zone(0) == ContextZone.SMART
        assert monitor.get_zone(40000) == ContextZone.SMART
        assert monitor.get_zone(80000) == ContextZone.SMART

        # Dumb zone: 40-80%
        assert monitor.get_zone(85000) == ContextZone.DUMB
        assert monitor.get_zone(120000) == ContextZone.DUMB

        # Critical zone: 80-100%
        assert monitor.get_zone(160000) == ContextZone.CRITICAL
        assert monitor.get_zone(180000) == ContextZone.CRITICAL

    def test_check_phase_within_budget(self):
        """Test phase analysis within budget"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        analysis = monitor.check_phase('scout', tokens_used=12000)

        assert analysis.phase_name == 'scout'
        assert analysis.tokens_used == 12000
        assert analysis.zone == ContextZone.SMART
        assert analysis.budget_allocated == 14000
        assert analysis.budget_remaining == 2000
        assert analysis.budget_exceeded_by == 0
        assert len(analysis.warnings) == 0

    def test_check_phase_exceeded_budget(self):
        """Test phase analysis with budget exceeded"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        analysis = monitor.check_phase('scout', tokens_used=20000)

        assert analysis.budget_exceeded_by == 6000  # 20K - 14K
        assert analysis.budget_remaining == 0
        assert len(analysis.warnings) > 0
        assert any('exceeded budget' in w.lower() for w in analysis.warnings)

    def test_check_phase_dumb_zone(self):
        """Test phase analysis in dumb zone"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        analysis = monitor.check_phase('architect', tokens_used=85000)

        assert analysis.zone == ContextZone.DUMB
        assert len(analysis.warnings) > 0
        assert any('dumb zone' in w.lower() for w in analysis.warnings)
        assert len(analysis.recommendations) > 0

    def test_check_phase_critical_zone(self):
        """Test phase analysis in critical zone"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        analysis = monitor.check_phase('builder', tokens_used=170000)

        assert analysis.zone == ContextZone.CRITICAL
        assert len(analysis.warnings) > 0
        assert any('critical' in w.lower() for w in analysis.warnings)

    def test_phase_history(self):
        """Test phase history tracking"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Run multiple checks
        monitor.check_phase('scout', 12000)
        monitor.check_phase('scout', 15000)
        monitor.check_phase('architect', 20000)

        # Get history
        scout_history = monitor.get_phase_history('scout')
        assert len(scout_history) == 2
        assert scout_history[0].tokens_used == 12000
        assert scout_history[1].tokens_used == 15000

        architect_history = monitor.get_phase_history('architect')
        assert len(architect_history) == 1

    def test_get_overall_stats(self):
        """Test overall statistics"""
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Run checks
        monitor.check_phase('scout', 12000)
        monitor.check_phase('architect', 85000)
        monitor.check_phase('builder', 40000)

        stats = monitor.get_overall_stats()

        assert stats['peak_usage_tokens'] == 85000
        assert stats['peak_phase'] == 'architect'
        assert stats['total_phases'] == 3
        assert 0 <= stats['smart_zone_percentage'] <= 100

    def test_export_to_session_summary(self):
        """Test export to session summary format"""
        monitor = ContextBudgetMonitor(context_window_size=200000, model='claude-sonnet-4')

        monitor.check_phase('scout', 12000)
        monitor.check_phase('architect', 85000)

        export = monitor.export_to_session_summary()

        assert export['max_context_window'] == 200000
        assert export['model'] == 'claude-sonnet-4'
        assert 'by_phase' in export
        assert 'overall' in export
        assert 'phase_scout' in export['by_phase']
        assert 'phase_architect' in export['by_phase']


class TestPhaseAnalysis:
    """Test PhaseAnalysis dataclass"""

    def test_to_dict(self):
        """Test conversion to dictionary"""
        analysis = PhaseAnalysis(
            phase_name='scout',
            tokens_used=12000,
            percentage=6.0,
            zone=ContextZone.SMART,
            budget_allocated=14000,
            budget_remaining=2000,
            warnings=[],
            recommendations=[]
        )

        data = analysis.to_dict()

        assert data['phase_name'] == 'scout'
        assert data['tokens_used'] == 12000
        assert data['zone'] == 'smart'
        assert isinstance(data['percentage'], (int, float))


class TestContextBudgetReporter:
    """Test reporting functionality"""

    def test_generate_context_report(self):
        """Test context report generation"""
        reporter = ContextBudgetReporter()

        context_metrics = {
            'max_context_window': 200000,
            'model': 'claude-sonnet-4',
            'by_phase': {
                'phase_scout': {
                    'phase_name': 'Scout',
                    'tokens_used': 12000,
                    'percentage': 6.0,
                    'zone': 'smart',
                    'budget_allocated': 14000,
                    'budget_remaining': 2000,
                }
            },
            'overall': {
                'peak_usage_tokens': 12000,
                'peak_usage_percentage': 6.0,
                'peak_phase': 'Scout',
                'avg_usage_percentage': 6.0,
                'smart_zone_percentage': 100.0,
            }
        }

        report = reporter.generate_context_report(context_metrics)

        assert 'Context Window Budget Report' in report
        assert 'claude-sonnet-4' in report
        assert 'Scout' in report

    def test_generate_context_report_empty(self):
        """Test report generation with no data"""
        reporter = ContextBudgetReporter()
        report = reporter.generate_context_report({})
        assert 'No context metrics available' in report

    def test_generate_phase_table(self):
        """Test phase table generation"""
        reporter = ContextBudgetReporter()

        by_phase = {
            'phase_scout': {
                'phase_name': 'Scout',
                'tokens_used': 12000,
                'percentage': 6.0,
                'zone': 'smart',
                'budget_allocated': 14000,
            }
        }

        table = reporter.generate_phase_table(by_phase)

        assert '┌' in table  # Table border
        assert 'Scout' in table
        assert '✅' in table  # Smart zone indicator

    def test_visualize_context_usage(self):
        """Test visualization generation"""
        reporter = ContextBudgetReporter()

        context_metrics = {
            'by_phase': {
                'phase_scout': {
                    'phase_name': 'Scout',
                    'percentage': 6.0,
                    'zone': 'smart',
                }
            }
        }

        viz = reporter.visualize_context_usage(context_metrics)

        assert 'Scout' in viz
        assert '█' in viz or '░' in viz  # Bar chart characters

    def test_get_optimization_suggestions(self):
        """Test optimization suggestions"""
        reporter = ContextBudgetReporter()

        context_metrics = {
            'by_phase': {
                'phase_scout': {
                    'phase_name': 'Scout',
                    'tokens_used': 12000,
                    'budget_allocated': 14000,
                    'zone': 'smart',
                }
            },
            'overall': {
                'avg_usage_percentage': 10.0,
                'smart_zone_percentage': 100.0,
            }
        }

        suggestions = reporter.get_optimization_suggestions(context_metrics)

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

    def test_format_zone_indicator(self):
        """Test zone indicator formatting"""
        reporter = ContextBudgetReporter()

        assert '✅' in reporter.format_zone_indicator('smart')
        assert '⚠️' in reporter.format_zone_indicator('dumb')
        assert '🚨' in reporter.format_zone_indicator('critical')

    def test_generate_summary_json(self):
        """Test JSON summary generation"""
        reporter = ContextBudgetReporter()

        context_metrics = {
            'overall': {
                'peak_usage_percentage': 6.0,
                'smart_zone_percentage': 100.0,
                'total_phases': 1,
            },
            'by_phase': {}
        }

        summary = reporter.generate_summary_json(context_metrics)

        assert 'status' in summary
        assert summary['status'] == 'optimal'
        assert 'recommendations' in summary

    def test_export_markdown_report(self):
        """Test markdown report export"""
        reporter = ContextBudgetReporter()

        context_metrics = {
            'max_context_window': 200000,
            'model': 'claude-sonnet-4',
            'by_phase': {},
            'overall': {
                'peak_usage_tokens': 0,
                'smart_zone_percentage': 100.0,
                'total_phases': 0,
            }
        }

        markdown = reporter.export_markdown_report(context_metrics)

        assert '# Context Window Budget Analysis' in markdown
        assert '## Summary' in markdown
        assert '## Optimization Suggestions' in markdown


class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self):
        """Test complete workflow from monitoring to reporting"""
        # Initialize monitor
        monitor = ContextBudgetMonitor(context_window_size=200000)

        # Simulate build phases
        monitor.check_phase('scout', 12000)
        monitor.check_phase('architect', 85000)
        monitor.check_phase('builder', 40000)
        monitor.check_phase('test', 30000)

        # Export metrics
        metrics = monitor.export_to_session_summary()

        # Generate report
        reporter = ContextBudgetReporter()
        report = reporter.generate_context_report(metrics)

        assert 'scout' in report or 'Scout' in report
        assert 'architect' in report or 'Architect' in report
        assert len(report) > 100  # Should be substantial report

    def test_session_summary_compatibility(self):
        """Test that export is compatible with session-summary.json format"""
        monitor = ContextBudgetMonitor()
        monitor.check_phase('scout', 12000)

        export = monitor.export_to_session_summary()

        # Verify structure matches expected schema
        assert 'max_context_window' in export
        assert 'model' in export
        assert 'by_phase' in export
        assert 'overall' in export

        # Should be JSON serializable
        json_str = json.dumps(export)
        assert len(json_str) > 0


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_zero_tokens(self):
        """Test handling of zero tokens"""
        monitor = ContextBudgetMonitor()
        analysis = monitor.check_phase('scout', 0)

        assert analysis.tokens_used == 0
        assert analysis.zone == ContextZone.SMART

    def test_massive_tokens(self):
        """Test handling of tokens exceeding context window"""
        monitor = ContextBudgetMonitor(context_window_size=200000)
        analysis = monitor.check_phase('architect', 250000)

        assert analysis.tokens_used == 250000
        assert analysis.zone == ContextZone.CRITICAL
        assert len(analysis.warnings) > 0

    def test_unknown_phase_name(self):
        """Test handling of unknown phase names"""
        monitor = ContextBudgetMonitor()
        analysis = monitor.check_phase('unknown_phase_xyz', 10000)

        assert analysis.phase_name == 'unknown_phase_xyz'
        # Should use default budget (5%)
        assert analysis.budget_allocated == 10000

    def test_empty_history(self):
        """Test stats with no phase history"""
        monitor = ContextBudgetMonitor()
        stats = monitor.get_overall_stats()

        assert stats['peak_usage_tokens'] == 0
        assert stats['total_phases'] == 0

    def test_reporter_with_malformed_data(self):
        """Test reporter handles malformed data gracefully"""
        reporter = ContextBudgetReporter()

        # Missing fields
        metrics = {'by_phase': {}}
        report = reporter.generate_context_report(metrics)
        assert isinstance(report, str)

        # Empty metrics
        viz = reporter.visualize_context_usage({})
        assert isinstance(viz, str)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

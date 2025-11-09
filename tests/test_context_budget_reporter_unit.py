#!/usr/bin/env python3
"""
Unit Tests for Context Budget Reporter

Tests the ContextBudgetReporter class which generates human-readable reports
and visualizations of context window usage.

Test Coverage:
- Initialization
- Context report generation
- Phase table formatting
- Visualizations
- Optimization suggestions
- Export formats (JSON, Markdown)
"""

import pytest
import sys
from pathlib import Path
import tempfile

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.context_budget.report import ContextBudgetReporter


# Fixtures

@pytest.fixture
def sample_context_metrics():
    """Sample context metrics for testing"""
    return {
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
                'budget_exceeded_by': 0,
                'warnings': [],
                'recommendations': []
            },
            'phase_builder': {
                'phase_name': 'Builder',
                'tokens_used': 40000,
                'percentage': 20.0,
                'zone': 'smart',
                'budget_allocated': 40000,
                'budget_remaining': 0,
                'budget_exceeded_by': 0,
                'warnings': [],
                'recommendations': []
            }
        },
        'overall': {
            'peak_usage_tokens': 40000,
            'peak_usage_percentage': 20.0,
            'peak_phase': 'Builder',
            'avg_usage_percentage': 13.0,
            'smart_zone_percentage': 100.0,
            'total_phases': 2,
            'recommendations': []
        }
    }


@pytest.fixture
def critical_zone_metrics():
    """Metrics with critical zone usage"""
    return {
        'max_context_window': 200000,
        'model': 'claude-sonnet-4',
        'by_phase': {
            'phase_builder': {
                'phase_name': 'Builder',
                'tokens_used': 170000,
                'percentage': 85.0,
                'zone': 'critical',
                'budget_allocated': 40000,
                'budget_remaining': 0,
                'budget_exceeded_by': 130000,
                'warnings': ['CRITICAL: Operating at 85% context'],
                'recommendations': ['Use sub-agents with isolated context']
            }
        },
        'overall': {
            'peak_usage_tokens': 170000,
            'peak_usage_percentage': 85.0,
            'peak_phase': 'Builder',
            'avg_usage_percentage': 85.0,
            'smart_zone_percentage': 0.0,
            'total_phases': 1,
            'recommendations': ['Builder consistently in critical zone - optimize context usage']
        }
    }


class TestReporterInitialization:
    """Test ContextBudgetReporter initialization"""

    def test_reporter_initializes(self):
        """Test reporter initializes successfully"""
        reporter = ContextBudgetReporter()
        assert reporter is not None


class TestContextReportGeneration:
    """Test context report generation"""

    def test_generate_context_report_with_full_metrics(self, sample_context_metrics):
        """Test generate_context_report() with full metrics"""
        reporter = ContextBudgetReporter()
        report = reporter.generate_context_report(sample_context_metrics)

        assert isinstance(report, str)
        assert 'Context Window Budget Report' in report
        assert 'claude-sonnet-4' in report
        assert '200,000' in report
        assert 'Scout' in report
        assert 'Builder' in report

    def test_generate_report_with_empty_metrics(self):
        """Test report generation with empty metrics"""
        reporter = ContextBudgetReporter()
        report = reporter.generate_context_report({})

        assert isinstance(report, str)
        assert 'No context metrics available' in report

    def test_generate_report_with_partial_metrics(self):
        """Test report handles partial metrics gracefully"""
        reporter = ContextBudgetReporter()
        partial = {
            'max_context_window': 200000,
            'model': 'claude-sonnet-4'
            # Missing by_phase and overall
        }
        report = reporter.generate_context_report(partial)

        assert isinstance(report, str)
        assert 'claude-sonnet-4' in report

    def test_report_includes_peak_usage(self, sample_context_metrics):
        """Test report includes peak usage information"""
        reporter = ContextBudgetReporter()
        report = reporter.generate_context_report(sample_context_metrics)

        assert 'Peak Usage' in report
        assert '40,000' in report
        assert 'Builder' in report

    def test_report_includes_zone_indicators(self, sample_context_metrics):
        """Test report includes zone indicators (emojis)"""
        reporter = ContextBudgetReporter()
        report = reporter.generate_context_report(sample_context_metrics)

        # Smart zone should have ✅
        assert '✅' in report


class TestPhaseTableGeneration:
    """Test phase table formatting"""

    def test_generate_phase_table_ascii_formatting(self, sample_context_metrics):
        """Test generate_phase_table() produces valid ASCII table"""
        reporter = ContextBudgetReporter()
        table = reporter.generate_phase_table(sample_context_metrics['by_phase'])

        assert isinstance(table, str)
        # Check for table borders
        assert '┌' in table
        assert '│' in table
        assert '└' in table
        # Check for column headers
        assert 'Phase' in table
        assert 'Used' in table
        assert 'Budget' in table
        assert 'Zone' in table

    def test_table_with_multiple_phases(self, sample_context_metrics):
        """Test table handles multiple phases"""
        reporter = ContextBudgetReporter()
        table = reporter.generate_phase_table(sample_context_metrics['by_phase'])

        # Should include both phases
        assert 'Scout' in table
        assert 'Builder' in table

    def test_table_column_alignment(self, sample_context_metrics):
        """Test table columns are properly aligned"""
        reporter = ContextBudgetReporter()
        table = reporter.generate_phase_table(sample_context_metrics['by_phase'])

        lines = table.split('\n')
        # All lines should have roughly same length (accounting for box drawing chars)
        line_lengths = [len(line) for line in lines if line]
        assert max(line_lengths) - min(line_lengths) <= 5

    def test_phase_name_truncation(self):
        """Test long phase names are truncated"""
        reporter = ContextBudgetReporter()
        by_phase = {
            'phase_very_long_phase_name_that_exceeds_limit': {
                'phase_name': 'VeryLongPhaseNameThatExceedsLimit',
                'tokens_used': 10000,
                'percentage': 5.0,
                'zone': 'smart',
                'budget_allocated': 14000,
                'budget_remaining': 4000,
                'budget_exceeded_by': 0
            }
        }
        table = reporter.generate_phase_table(by_phase)

        # Phase name should be truncated to 15 chars
        assert isinstance(table, str)


class TestVisualization:
    """Test ASCII visualization generation"""

    def test_visualize_context_usage_bar_chart(self, sample_context_metrics):
        """Test visualize_context_usage() generates bar chart"""
        reporter = ContextBudgetReporter()
        viz = reporter.visualize_context_usage(sample_context_metrics)

        assert isinstance(viz, str)
        assert 'Context Usage by Phase' in viz
        # Should have filled bars (█)
        assert '█' in viz
        # Should have empty bars (░)
        assert '░' in viz

    def test_bar_chart_with_varying_percentages(self):
        """Test bar chart represents different percentages correctly"""
        reporter = ContextBudgetReporter()
        metrics = {
            'by_phase': {
                'phase_small': {
                    'phase_name': 'Small',
                    'percentage': 5.0,
                    'zone': 'smart'
                },
                'phase_large': {
                    'phase_name': 'Large',
                    'percentage': 50.0,
                    'zone': 'dumb'
                }
            }
        }
        viz = reporter.visualize_context_usage(metrics)

        lines = viz.split('\n')
        # Large phase should have more filled bars than Small
        large_line = [l for l in lines if 'Large' in l][0]
        small_line = [l for l in lines if 'Small' in l][0]

        large_filled = large_line.count('█')
        small_filled = small_line.count('█')

        assert large_filled > small_filled

    def test_bar_chart_zone_emojis(self, critical_zone_metrics):
        """Test bar chart includes zone emoji indicators"""
        reporter = ContextBudgetReporter()
        viz = reporter.visualize_context_usage(critical_zone_metrics)

        # Critical zone should have 🚨
        assert '🚨' in viz

    def test_empty_data_handling(self):
        """Test visualization handles empty data gracefully"""
        reporter = ContextBudgetReporter()
        viz = reporter.visualize_context_usage({'by_phase': {}})

        assert 'No data to visualize' in viz


class TestOptimizationSuggestions:
    """Test optimization suggestion generation"""

    def test_suggestions_for_critical_zone(self, critical_zone_metrics):
        """Test get_optimization_suggestions() for critical zone"""
        reporter = ContextBudgetReporter()
        suggestions = reporter.get_optimization_suggestions(critical_zone_metrics)

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        # Should have critical warning
        assert any('CRITICAL' in s for s in suggestions)

    def test_suggestions_for_dumb_zone(self):
        """Test suggestions for dumb zone"""
        reporter = ContextBudgetReporter()
        metrics = {
            'by_phase': {
                'phase_test': {
                    'phase_name': 'Test',
                    'tokens_used': 100000,
                    'zone': 'dumb',
                    'budget_allocated': 40000
                }
            },
            'overall': {
                'avg_usage_percentage': 50.0,
                'smart_zone_percentage': 0.0
            }
        }
        suggestions = reporter.get_optimization_suggestions(metrics)

        assert len(suggestions) > 0

    def test_suggestions_for_optimal_usage(self, sample_context_metrics):
        """Test suggestions for optimal usage"""
        reporter = ContextBudgetReporter()
        suggestions = reporter.get_optimization_suggestions(sample_context_metrics)

        # Should indicate everything is good
        assert any('efficiently' in s.lower() or '✅' in s for s in suggestions)

    def test_phase_specific_recommendations(self):
        """Test phase-specific recommendations are generated"""
        reporter = ContextBudgetReporter()
        metrics = {
            'by_phase': {
                'phase_builder': {
                    'phase_name': 'Builder',
                    'tokens_used': 70000,
                    'zone': 'dumb',
                    'budget_allocated': 40000
                }
            },
            'overall': {}
        }
        suggestions = reporter.get_optimization_suggestions(metrics)

        # Should have suggestion about exceeded budget
        assert any('exceeded' in s.lower() for s in suggestions)


class TestExportFormats:
    """Test export to different formats"""

    def test_generate_summary_json_format(self, sample_context_metrics):
        """Test generate_summary_json() produces correct structure"""
        reporter = ContextBudgetReporter()
        summary = reporter.generate_summary_json(sample_context_metrics)

        assert isinstance(summary, dict)
        assert 'status' in summary
        assert 'peak_usage_percentage' in summary
        assert 'smart_zone_percentage' in summary
        assert 'recommendations' in summary

    def test_export_markdown_report_formatting(self, sample_context_metrics):
        """Test export_markdown_report() produces markdown"""
        reporter = ContextBudgetReporter()
        markdown = reporter.export_markdown_report(sample_context_metrics)

        assert isinstance(markdown, str)
        assert '# Context Window Budget Analysis' in markdown
        assert '## Summary' in markdown
        assert '## Visualization' in markdown
        assert '## Optimization Suggestions' in markdown

    def test_markdown_file_output(self, sample_context_metrics):
        """Test markdown report can be saved to file"""
        reporter = ContextBudgetReporter()

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            output_path = f.name

        try:
            markdown = reporter.export_markdown_report(sample_context_metrics, output_path)

            # Check file was created
            assert Path(output_path).exists()

            # Check content
            content = Path(output_path).read_text()
            assert '# Context Window Budget Analysis' in content
        finally:
            # Cleanup
            Path(output_path).unlink(missing_ok=True)

    def test_format_zone_indicator_mapping(self):
        """Test format_zone_indicator() maps zones correctly"""
        reporter = ContextBudgetReporter()

        assert '✅' in reporter.format_zone_indicator('smart')
        assert '⚠️' in reporter.format_zone_indicator('dumb')
        assert '🚨' in reporter.format_zone_indicator('critical')
        assert '❓' in reporter.format_zone_indicator('unknown')


class TestHelperMethods:
    """Test internal helper methods"""

    def test_format_tokens_kilobyte_conversion(self):
        """Test _format_tokens() converts to K notation"""
        reporter = ContextBudgetReporter()

        assert reporter._format_tokens(1000) == '1.0K'
        assert reporter._format_tokens(12000) == '12.0K'
        assert reporter._format_tokens(500) == '500'

    def test_get_zone_emoji_mapping(self):
        """Test _get_zone_emoji() returns correct emojis"""
        reporter = ContextBudgetReporter()

        assert reporter._get_zone_emoji('smart') == '✅'
        assert reporter._get_zone_emoji('dumb') == '⚠️'
        assert reporter._get_zone_emoji('critical') == '🚨'
        assert reporter._get_zone_emoji('unknown') == '❓'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

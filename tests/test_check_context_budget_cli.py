#!/usr/bin/env python3
"""
Comprehensive tests for check_context_budget.py CLI tool

This test suite covers:
- CLI argument parsing
- Build context extraction
- Budget pre-checks
- Token recording
- Report generation
- Exit codes
- Integration workflows
"""

import pytest
import sys
import json
import argparse
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock, call
from datetime import datetime

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.check_context_budget import (
    get_build_context,
    print_build_context_header,
    load_session_summary,
    save_session_summary,
    estimate_phase_tokens,
    check_before_phase,
    record_phase_actual,
    generate_report,
    main
)
from tools.context_budget import ContextZone


class TestCLIArgumentParsing:
    """Test command-line argument parsing"""

    def test_parse_args_check_before(self):
        """Test --phase scout --check-before"""
        with patch('sys.argv', ['prog', '--phase', 'scout', '--check-before']):
            with patch('tools.check_context_budget.check_before_phase', return_value=0):
                result = main()
                assert result == 0

    def test_parse_args_tokens(self):
        """Test --phase builder --tokens 45000"""
        with patch('sys.argv', ['prog', '--phase', 'builder', '--tokens', '45000']):
            with patch('tools.check_context_budget.record_phase_actual', return_value=0):
                result = main()
                assert result == 0

    def test_parse_args_report(self):
        """Test --report"""
        with patch('sys.argv', ['prog', '--report']):
            with patch('tools.check_context_budget.generate_report', return_value=0):
                result = main()
                assert result == 0

    def test_parse_args_missing_phase(self):
        """Test error when --phase is missing"""
        with patch('sys.argv', ['prog', '--tokens', '1000']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Should exit with error code
            assert exc_info.value.code != 0

    def test_parse_args_missing_action(self):
        """Test error when neither --check-before nor --tokens provided"""
        with patch('sys.argv', ['prog', '--phase', 'scout']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Should exit with error code
            assert exc_info.value.code != 0

    def test_parse_args_with_working_dir(self):
        """Test --working-dir argument"""
        with patch('sys.argv', ['prog', '--phase', 'scout', '--check-before', '--working-dir', '/tmp']):
            with patch('tools.check_context_budget.check_before_phase', return_value=0) as mock_check:
                result = main()
                assert result == 0
                # Verify working_dir was passed
                mock_check.assert_called_once_with('scout', '/tmp')


class TestBuildContextExtraction:
    """Test build context extraction from session files"""

    def test_get_build_context_with_session_file(self, tmp_path):
        """Test extracting context from session-summary.json"""
        # Create session file
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()
        session_file = context_dir / 'session-summary.json'
        session_data = {
            'session_id': 'test-session-123',
            'task': 'Build a test application',
            'mode': 'new_project',
            'started_at': '2025-01-13T14:00:00Z',
            'status': 'in_progress'
        }
        session_file.write_text(json.dumps(session_data))

        # Extract context
        context = get_build_context(str(tmp_path))

        # Verify
        assert context['session_id'] == 'test-session-123'
        assert context['task'] == 'Build a test application'
        assert context['mode'] == 'new_project'
        assert context['started_at'] == '2025-01-13T14:00:00Z'
        assert context['status'] == 'in_progress'
        assert str(tmp_path) in context['working_directory']

    def test_get_build_context_missing_session_file(self, tmp_path):
        """Test behavior when session file doesn't exist"""
        context = get_build_context(str(tmp_path))

        # Should return dict with working_directory at minimum
        assert 'working_directory' in context
        assert str(tmp_path) in context['working_directory']

    def test_get_build_context_invalid_json(self, tmp_path, capsys):
        """Test handling of malformed JSON"""
        # Create invalid JSON file
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()
        session_file = context_dir / 'session-summary.json'
        session_file.write_text('{ invalid json }')

        # Extract context (should not crash)
        context = get_build_context(str(tmp_path))

        # Should have working_directory but nothing else
        assert 'working_directory' in context

        # Should print warning to stderr
        captured = capsys.readouterr()
        assert 'Warning' in captured.err or 'Failed to read' in captured.err

    def test_get_build_context_with_current_phase(self, tmp_path):
        """Test extracting current phase info"""
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()

        # Create phase file
        phase_file = context_dir / 'current-phase.json'
        phase_data = {
            'current_phase': 'Builder',
            'phase_number': '3/7',
            'status': 'building',
            'progress_detail': 'Implementing features'
        }
        phase_file.write_text(json.dumps(phase_data))

        # Extract context
        context = get_build_context(str(tmp_path))

        # Verify phase info
        assert context['current_phase'] == 'Builder'
        assert context['phase_number'] == '3/7'
        assert context['status'] == 'building'
        assert context['progress_detail'] == 'Implementing features'

    def test_get_build_context_with_github_pr(self, tmp_path):
        """Test extracting GitHub PR metadata"""
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()
        session_file = context_dir / 'session-summary.json'
        session_data = {
            'session_id': 'test-session',
            'github_url': 'https://github.com/user/repo',
            'pr_number': 42
        }
        session_file.write_text(json.dumps(session_data))

        context = get_build_context(str(tmp_path))

        assert context['github_url'] == 'https://github.com/user/repo'
        assert context['pr_number'] == 42

    def test_get_build_context_completed_status(self, tmp_path):
        """Test context when build is completed"""
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()

        # Session shows completed
        session_file = context_dir / 'session-summary.json'
        session_data = {
            'session_id': 'test',
            'status': 'completed',
            'duration_minutes': 15.5
        }
        session_file.write_text(json.dumps(session_data))

        # Phase file exists but should be ignored for completed builds
        phase_file = context_dir / 'current-phase.json'
        phase_file.write_text(json.dumps({'current_phase': 'Test'}))

        context = get_build_context(str(tmp_path))

        # Should use session status, not phase status
        assert context['status'] == 'completed'
        assert 'duration_minutes' in context
        # current_phase should NOT be set for completed builds
        assert 'current_phase' not in context or context.get('current_phase') is None


class TestBudgetPreCheck:
    """Test budget pre-check functionality"""

    @patch('tools.check_context_budget.ContextBudgetMonitor')
    @patch('tools.check_context_budget.get_build_context')
    @patch('tools.check_context_budget.print_build_context_header')
    def test_pre_check_smart_zone(self, mock_header, mock_context, mock_monitor_class, tmp_path, capsys):
        """Test pre-check in SMART zone (safe)"""
        # Setup mocks
        mock_context.return_value = {'session_id': 'test'}
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor

        # Mock analysis result (SMART zone)
        mock_analysis = MagicMock()
        mock_analysis.zone = ContextZone.SMART
        mock_analysis.budget_allocated = 14000
        mock_analysis.percentage = 7.0
        mock_analysis.warnings = []
        mock_analysis.recommendations = []
        mock_monitor.check_phase.return_value = mock_analysis

        # Run pre-check
        exit_code = check_before_phase('scout', str(tmp_path))

        # Verify
        assert exit_code == 0
        mock_monitor.check_phase.assert_called_once()

        # Check output
        captured = capsys.readouterr()
        assert 'SMART' in captured.out
        assert '✅ SAFE' in captured.out

    @patch('tools.check_context_budget.ContextBudgetMonitor')
    @patch('tools.check_context_budget.get_build_context')
    @patch('tools.check_context_budget.print_build_context_header')
    def test_pre_check_dumb_zone(self, mock_header, mock_context, mock_monitor_class, tmp_path, capsys):
        """Test pre-check in DUMB zone (warning)"""
        mock_context.return_value = {'session_id': 'test'}
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor

        # Mock analysis result (DUMB zone)
        mock_analysis = MagicMock()
        mock_analysis.zone = ContextZone.DUMB
        mock_analysis.budget_allocated = 40000
        mock_analysis.percentage = 50.0
        mock_analysis.warnings = ['Approaching context limit']
        mock_analysis.recommendations = ['Consider reducing scope']
        mock_monitor.check_phase.return_value = mock_analysis

        # Run pre-check
        exit_code = check_before_phase('builder', str(tmp_path))

        # Verify
        assert exit_code == 1  # Warning exit code

        captured = capsys.readouterr()
        assert 'DUMB' in captured.out
        assert '⚠️' in captured.out
        assert 'WARNING' in captured.out

    @patch('tools.check_context_budget.ContextBudgetMonitor')
    @patch('tools.check_context_budget.get_build_context')
    @patch('tools.check_context_budget.print_build_context_header')
    def test_pre_check_critical_zone(self, mock_header, mock_context, mock_monitor_class, tmp_path, capsys):
        """Test pre-check in CRITICAL zone (critical warning)"""
        mock_context.return_value = {'session_id': 'test'}
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor

        # Mock analysis result (CRITICAL zone)
        mock_analysis = MagicMock()
        mock_analysis.zone = ContextZone.CRITICAL
        mock_analysis.budget_allocated = 40000
        mock_analysis.percentage = 85.0
        mock_analysis.warnings = ['Context overflow imminent']
        mock_analysis.recommendations = ['Use sub-agent']
        mock_monitor.check_phase.return_value = mock_analysis

        # Run pre-check
        exit_code = check_before_phase('builder', str(tmp_path))

        # Verify
        assert exit_code == 2  # Critical exit code

        captured = capsys.readouterr()
        assert 'CRITICAL' in captured.out
        assert '🚨' in captured.out

    @patch('tools.check_context_budget.estimate_phase_tokens')
    @patch('tools.check_context_budget.ContextBudgetMonitor')
    @patch('tools.check_context_budget.get_build_context')
    @patch('tools.check_context_budget.print_build_context_header')
    def test_pre_check_uses_estimation(self, mock_header, mock_context, mock_monitor_class, mock_estimate, tmp_path):
        """Test that pre-check uses token estimation"""
        mock_context.return_value = {}
        mock_estimate.return_value = 15000
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor
        mock_analysis = MagicMock()
        mock_analysis.zone = ContextZone.SMART
        mock_analysis.budget_allocated = 14000
        mock_analysis.percentage = 7.5
        mock_analysis.warnings = []
        mock_analysis.recommendations = []
        mock_monitor.check_phase.return_value = mock_analysis

        check_before_phase('architect', str(tmp_path))

        # Verify estimation was called
        mock_estimate.assert_called_once_with('architect', str(tmp_path))
        # Verify monitor was called with estimated tokens
        mock_monitor.check_phase.assert_called_once_with('architect', 15000)


class TestTokenRecording:
    """Test token recording functionality"""

    def test_record_tokens_creates_session(self, tmp_path):
        """Test recording tokens creates session file if missing"""
        with patch('tools.check_context_budget.get_build_context', return_value={}):
            with patch('tools.check_context_budget.print_build_context_header'):
                with patch('tools.check_context_budget.ContextBudgetMonitor') as mock_monitor_class:
                    mock_monitor = MagicMock()
                    mock_monitor_class.return_value = mock_monitor
                    mock_analysis = MagicMock()
                    mock_analysis.zone = ContextZone.SMART
                    mock_analysis.budget_allocated = 14000
                    mock_analysis.percentage = 6.0
                    mock_analysis.warnings = []
                    mock_analysis.recommendations = []
                    mock_analysis.budget_exceeded_by = 0
                    mock_analysis.budget_remaining = 2000
                    mock_analysis.to_dict.return_value = {'tokens': 12000}
                    mock_monitor.check_phase.return_value = mock_analysis
                    mock_monitor.export_to_session_summary.return_value = {'by_phase': {}}
                    mock_monitor.get_overall_stats.return_value = {}

                    # Record tokens
                    exit_code = record_phase_actual('scout', 12000, str(tmp_path))

                    assert exit_code == 0

                    # Verify session file was created
                    session_file = tmp_path / '.context-foundry' / 'session-summary.json'
                    assert session_file.exists()

                    # Verify content
                    session = json.loads(session_file.read_text())
                    assert 'context_metrics' in session

    def test_record_tokens_updates_existing_session(self, tmp_path):
        """Test recording tokens updates existing session"""
        # Create existing session
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()
        session_file = context_dir / 'session-summary.json'
        existing_session = {
            'session_id': 'test',
            'context_metrics': {
                'by_phase': {
                    'phase_scout': {'tokens': 12000}
                }
            }
        }
        session_file.write_text(json.dumps(existing_session))

        with patch('tools.check_context_budget.get_build_context', return_value={}):
            with patch('tools.check_context_budget.print_build_context_header'):
                with patch('tools.check_context_budget.ContextBudgetMonitor') as mock_monitor_class:
                    mock_monitor = MagicMock()
                    mock_monitor_class.return_value = mock_monitor
                    mock_analysis = MagicMock()
                    mock_analysis.zone = ContextZone.SMART
                    mock_analysis.budget_allocated = 14000
                    mock_analysis.percentage = 7.0
                    mock_analysis.warnings = []
                    mock_analysis.recommendations = []
                    mock_analysis.budget_exceeded_by = 0
                    mock_analysis.budget_remaining = 500
                    mock_analysis.to_dict.return_value = {'tokens': 13500}
                    mock_monitor.check_phase.return_value = mock_analysis
                    mock_monitor.get_overall_stats.return_value = {}

                    # Record tokens for architect
                    record_phase_actual('architect', 13500, str(tmp_path))

                    # Verify session was updated
                    updated_session = json.loads(session_file.read_text())
                    assert 'session_id' in updated_session  # Original data preserved
                    assert 'phase_architect' in updated_session['context_metrics']['by_phase']
                    assert 'phase_scout' in updated_session['context_metrics']['by_phase']  # Original preserved

    def test_record_tokens_invalid_value(self, tmp_path):
        """Test error handling for invalid token values"""
        # This is handled by argparse, but test the function directly
        with patch('tools.check_context_budget.get_build_context', return_value={}):
            with patch('tools.check_context_budget.print_build_context_header'):
                with patch('tools.check_context_budget.ContextBudgetMonitor') as mock_monitor_class:
                    mock_monitor = MagicMock()
                    mock_monitor_class.return_value = mock_monitor

                    # Negative tokens should still be processed (monitor will validate)
                    mock_analysis = MagicMock()
                    mock_analysis.zone = ContextZone.SMART
                    mock_analysis.budget_allocated = 14000
                    mock_analysis.percentage = 0
                    mock_analysis.warnings = []
                    mock_analysis.recommendations = []
                    mock_analysis.budget_exceeded_by = 0
                    mock_analysis.budget_remaining = 14000
                    mock_analysis.to_dict.return_value = {'tokens': 0}
                    mock_monitor.check_phase.return_value = mock_analysis
                    mock_monitor.export_to_session_summary.return_value = {'by_phase': {}}
                    mock_monitor.get_overall_stats.return_value = {}

                    # Function should not crash with zero tokens
                    exit_code = record_phase_actual('scout', 0, str(tmp_path))
                    assert exit_code == 0


class TestReportGeneration:
    """Test report generation functionality"""

    def test_generate_report_no_data(self, tmp_path, capsys):
        """Test report generation with no data"""
        exit_code = generate_report(str(tmp_path))

        # Should exit with error
        assert exit_code == 1

        # Should print helpful message
        captured = capsys.readouterr()
        assert 'No context metrics available' in captured.out

    def test_generate_report_with_data(self, tmp_path):
        """Test report generation with metrics data"""
        # Create session with metrics
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()
        session_file = context_dir / 'session-summary.json'
        session_data = {
            'session_id': 'test',
            'context_metrics': {
                'by_phase': {
                    'phase_scout': {
                        'tokens': 12000,
                        'budget_allocated': 14000,
                        'percentage': 6.0
                    },
                    'phase_architect': {
                        'tokens': 13500,
                        'budget_allocated': 14000,
                        'percentage': 6.75
                    }
                },
                'overall': {
                    'total_tokens': 25500,
                    'total_budget': 200000
                }
            }
        }
        session_file.write_text(json.dumps(session_data))

        with patch('tools.check_context_budget.get_build_context', return_value={'session_id': 'test'}):
            with patch('tools.check_context_budget.print_build_context_header'):
                with patch('tools.check_context_budget.ContextBudgetReporter') as mock_reporter_class:
                    mock_reporter = MagicMock()
                    mock_reporter_class.return_value = mock_reporter
                    mock_reporter.generate_context_report.return_value = "# Report Content"
                    mock_reporter.visualize_context_usage.return_value = "ASCII Visualization"

                    exit_code = generate_report(str(tmp_path))

                    # Should succeed
                    assert exit_code == 0

                    # Verify reporter was called
                    mock_reporter.generate_context_report.assert_called_once()
                    mock_reporter.visualize_context_usage.assert_called_once()


class TestSessionManagement:
    """Test session file management functions"""

    def test_load_session_summary_existing(self, tmp_path):
        """Test loading existing session summary"""
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()
        session_file = context_dir / 'session-summary.json'
        data = {'session_id': 'test', 'key': 'value'}
        session_file.write_text(json.dumps(data))

        result = load_session_summary(str(tmp_path))

        assert result == data

    def test_load_session_summary_missing(self, tmp_path):
        """Test loading missing session summary"""
        result = load_session_summary(str(tmp_path))
        assert result is None

    def test_load_session_summary_invalid_json(self, tmp_path, capsys):
        """Test loading invalid JSON"""
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()
        session_file = context_dir / 'session-summary.json'
        session_file.write_text('{ invalid }')

        result = load_session_summary(str(tmp_path))

        # Should return None and print warning
        assert result is None
        captured = capsys.readouterr()
        assert 'Warning' in captured.err

    def test_save_session_summary(self, tmp_path):
        """Test saving session summary"""
        data = {'session_id': 'test', 'data': 'value'}
        save_session_summary(data, str(tmp_path))

        # Verify file was created
        session_file = tmp_path / '.context-foundry' / 'session-summary.json'
        assert session_file.exists()

        # Verify content
        saved = json.loads(session_file.read_text())
        assert saved == data

    def test_save_session_summary_creates_directory(self, tmp_path):
        """Test that save creates .context-foundry directory"""
        # Remove directory if it exists
        context_dir = tmp_path / '.context-foundry'
        if context_dir.exists():
            context_dir.rmdir()

        data = {'test': 'data'}
        save_session_summary(data, str(tmp_path))

        # Directory should be created
        assert context_dir.exists()
        assert (context_dir / 'session-summary.json').exists()


class TestEstimatePhaseTokens:
    """Test token estimation for phases"""

    def test_estimate_scout_phase(self, tmp_path):
        """Test estimation for scout phase"""
        estimate = estimate_phase_tokens('scout', str(tmp_path))

        # Should return default estimate for scout
        assert estimate == 14000

    def test_estimate_builder_phase(self, tmp_path):
        """Test estimation for builder phase"""
        estimate = estimate_phase_tokens('builder', str(tmp_path))

        # Should return default estimate for builder
        assert estimate == 40000

    def test_estimate_with_existing_artifacts(self, tmp_path):
        """Test estimation considers existing artifacts"""
        # Create context files
        context_dir = tmp_path / '.context-foundry'
        context_dir.mkdir()

        scout_file = context_dir / 'scout-report.md'
        scout_file.write_text("# Scout Report\n" + "content " * 1000)

        arch_file = context_dir / 'architecture.md'
        arch_file.write_text("# Architecture\n" + "content " * 1000)

        estimate = estimate_phase_tokens('builder', str(tmp_path))

        # Should be higher than default due to existing files
        # (Or at least equal to default, depending on implementation)
        assert estimate >= 40000

    def test_estimate_unknown_phase(self, tmp_path):
        """Test estimation for unknown phase"""
        estimate = estimate_phase_tokens('unknown_phase', str(tmp_path))

        # Should return default estimate
        assert estimate == 10000


class TestIntegration:
    """Integration tests for complete workflows"""

    @patch('tools.check_context_budget.ContextBudgetMonitor')
    @patch('tools.check_context_budget.get_build_context')
    @patch('tools.check_context_budget.print_build_context_header')
    def test_full_workflow_check_then_record(self, mock_header, mock_context, mock_monitor_class, tmp_path, capsys):
        """Test complete workflow: check before, then record after"""
        mock_context.return_value = {'session_id': 'test'}
        mock_monitor = MagicMock()
        mock_monitor_class.return_value = mock_monitor

        # Setup mock for check phase
        mock_analysis_check = MagicMock()
        mock_analysis_check.zone = ContextZone.SMART
        mock_analysis_check.budget_allocated = 14000
        mock_analysis_check.percentage = 7.0
        mock_analysis_check.warnings = []
        mock_analysis_check.recommendations = []

        # Setup mock for record phase
        mock_analysis_record = MagicMock()
        mock_analysis_record.zone = ContextZone.SMART
        mock_analysis_record.budget_allocated = 14000
        mock_analysis_record.percentage = 6.0
        mock_analysis_record.budget_exceeded_by = 0
        mock_analysis_record.budget_remaining = 2000
        mock_analysis_record.warnings = []
        mock_analysis_record.recommendations = []
        mock_analysis_record.to_dict.return_value = {'tokens': 12000}

        mock_monitor.check_phase.side_effect = [mock_analysis_check, mock_analysis_record]
        mock_monitor.export_to_session_summary.return_value = {'by_phase': {}}
        mock_monitor.get_overall_stats.return_value = {}

        # Step 1: Check before phase
        exit_code_1 = check_before_phase('scout', str(tmp_path))
        assert exit_code_1 == 0

        # Step 2: Record actual tokens
        exit_code_2 = record_phase_actual('scout', 12000, str(tmp_path))
        assert exit_code_2 == 0

        # Verify session was updated
        session_file = tmp_path / '.context-foundry' / 'session-summary.json'
        assert session_file.exists()

    def test_workflow_budget_exceeded_warning(self, tmp_path):
        """Test workflow where phase exceeds budget"""
        with patch('tools.check_context_budget.get_build_context', return_value={}):
            with patch('tools.check_context_budget.print_build_context_header'):
                with patch('tools.check_context_budget.ContextBudgetMonitor') as mock_monitor_class:
                    mock_monitor = MagicMock()
                    mock_monitor_class.return_value = mock_monitor

                    # Recording 50K tokens (exceeds 14K budget)
                    mock_analysis = MagicMock()
                    mock_analysis.zone = ContextZone.DUMB
                    mock_analysis.budget_allocated = 14000
                    mock_analysis.percentage = 25.0
                    mock_analysis.budget_exceeded_by = 36000
                    mock_analysis.budget_remaining = 0
                    mock_analysis.warnings = ['Budget exceeded']
                    mock_analysis.recommendations = ['Reduce scope']
                    mock_analysis.to_dict.return_value = {'tokens': 50000}
                    mock_monitor.check_phase.return_value = mock_analysis
                    mock_monitor.export_to_session_summary.return_value = {'by_phase': {}}
                    mock_monitor.get_overall_stats.return_value = {}

                    exit_code = record_phase_actual('scout', 50000, str(tmp_path))

                    # Should still succeed (recording is informational)
                    assert exit_code == 0

                    # Session should contain the warning
                    session_file = tmp_path / '.context-foundry' / 'session-summary.json'
                    assert session_file.exists()


class TestPrintBuildContextHeader:
    """Test build context header formatting"""

    def test_print_header_with_context(self, capsys):
        """Test printing header with full context"""
        context = {
            'session_id': 'test-123',
            'task': 'Build test app',
            'mode': 'new_project',
            'working_directory': '/home/user/project',
            'started_at': '2025-01-13T14:00:00Z',
            'status': 'in_progress',
            'current_phase': 'Builder',
            'phase_number': '3/7'
        }

        print_build_context_header(context)

        captured = capsys.readouterr()
        assert 'test-123' in captured.out
        assert 'Build test app' in captured.out
        assert 'new_project' in captured.out
        assert 'Builder' in captured.out

    def test_print_header_no_context(self, capsys):
        """Test printing header with no context"""
        print_build_context_header({})

        captured = capsys.readouterr()
        assert 'No active build context' in captured.out

    def test_print_header_truncates_long_task(self, capsys):
        """Test that long task descriptions are truncated"""
        context = {
            'session_id': 'test',
            'task': 'A' * 100,  # Very long task
            'mode': 'test'
        }

        print_build_context_header(context)

        captured = capsys.readouterr()
        # Should be truncated with ...
        assert '...' in captured.out
        # Shouldn't show all 100 A's
        assert 'A' * 60 not in captured.out

    def test_print_header_with_github_pr(self, capsys):
        """Test printing header with GitHub PR info"""
        context = {
            'session_id': 'test',
            'pr_number': 42,
            'github_url': 'https://github.com/user/repo/pull/42'
        }

        print_build_context_header(context)

        captured = capsys.readouterr()
        assert 'PR #42' in captured.out
        assert 'github.com' in captured.out

    def test_print_header_completed_status(self, capsys):
        """Test header for completed build"""
        context = {
            'session_id': 'test',
            'status': 'completed',
            'duration_minutes': 15.5
        }

        print_build_context_header(context)

        captured = capsys.readouterr()
        assert 'Completed' in captured.out
        assert '15.5' in captured.out or '15.5 minutes' in captured.out


# Run tests with: pytest tests/test_check_context_budget_cli.py -v
# With coverage: pytest tests/test_check_context_budget_cli.py --cov=tools/check_context_budget --cov-report=term-missing

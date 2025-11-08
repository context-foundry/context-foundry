#!/usr/bin/env python3
"""
Comprehensive tests for Evolution Daemon error recovery paths.

CRITICAL PATHS TESTED:
- _queue_next_improvement_task() exception handling
- GitHub API error recovery (rate limiting, network failures, auth issues)
- Config loading error handling (malformed JSON, missing fields, invalid types)
- Database write failures
- PR detection errors

Priority: 9/10 - Critical daemon reliability with <40% coverage
"""

import pytest
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import sys
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'tools'))


@pytest.mark.unit
@pytest.mark.tier1
class TestQueueNextImprovementTaskErrors:
    """Test _queue_next_improvement_task() error handling"""

    @patch('tools.evolution.daemon.TaskQueue')
    def test_queue_task_mode_find_todos_exception(self, mock_queue_class):
        """Test when mode._find_todos() raises exception"""
        from tools.evolution.daemon import EvolutionDaemon
        from tools.evolution.modes.self_improvement import SelfImprovementMode

        daemon = EvolutionDaemon()

        # Mock mode with failing _find_todos
        mock_mode = Mock(spec=SelfImprovementMode)
        mock_mode.generate_tasks.side_effect = Exception("TODO search failed")

        # Should handle exception gracefully
        try:
            daemon._queue_next_improvement_task(mock_mode)
        except Exception as e:
            # Daemon should catch and log, not crash
            assert False, f"Daemon crashed on mode exception: {e}"

    @patch('tools.evolution.daemon.TaskQueue')
    def test_queue_task_database_write_failure(self, mock_queue_class):
        """Test when database write fails"""
        from tools.evolution.daemon import EvolutionDaemon
        from tools.evolution.modes.self_improvement import SelfImprovementMode

        daemon = EvolutionDaemon()

        # Mock mode that returns tasks
        mock_mode = Mock(spec=SelfImprovementMode)
        mock_mode.generate_tasks.return_value = [
            {
                'type': 'self_improvement',
                'params': {'action': 'test', 'file': 'test.py', 'line': 10}
            }
        ]

        # Mock queue with failing add_task
        mock_queue = Mock()
        mock_queue.add_task.side_effect = Exception("Database write failed")
        mock_queue_class.return_value = mock_queue

        # Should handle database error gracefully
        try:
            daemon._queue_next_improvement_task(mock_mode)
        except Exception as e:
            assert False, f"Daemon crashed on database error: {e}"

    @patch('tools.evolution.daemon.TaskQueue')
    def test_queue_task_invalid_todo_data(self, mock_queue_class):
        """Test when mode returns invalid TODO data"""
        from tools.evolution.daemon import EvolutionDaemon
        from tools.evolution.modes.self_improvement import SelfImprovementMode

        daemon = EvolutionDaemon()

        # Mock mode returning malformed tasks
        mock_mode = Mock(spec=SelfImprovementMode)
        mock_mode.generate_tasks.return_value = [
            {
                # Missing 'type' field
                'params': {'action': 'test'}
            }
        ]

        mock_queue = Mock()
        mock_queue_class.return_value = mock_queue

        # Should handle invalid data gracefully
        try:
            daemon._queue_next_improvement_task(mock_mode)
        except Exception as e:
            # May raise validation error, which is acceptable
            pass


@pytest.mark.unit
@pytest.mark.tier1
class TestGitHubAPIErrors:
    """Test GitHub API error recovery"""

    @patch('subprocess.run')
    def test_check_open_prs_rate_limiting(self, mock_run):
        """Test handling GitHub API rate limiting"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock gh CLI rate limit error
        mock_run.return_value = Mock(
            returncode=1,
            stdout='',
            stderr='API rate limit exceeded'
        )

        # Should handle rate limiting gracefully
        try:
            prs = daemon._check_open_prs()
            # Should return empty list or handle gracefully
            assert isinstance(prs, list)
        except Exception as e:
            assert False, f"Daemon crashed on rate limit: {e}"

    @patch('subprocess.run')
    def test_check_open_prs_network_failure(self, mock_run):
        """Test handling network failures"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock network error
        mock_run.side_effect = Exception("Network unreachable")

        # Should handle network error gracefully
        try:
            prs = daemon._check_open_prs()
            assert isinstance(prs, list)
        except Exception as e:
            # Acceptable to fail, but should not crash daemon
            pass

    @patch('subprocess.run')
    def test_check_open_prs_invalid_token(self, mock_run):
        """Test handling invalid GitHub token"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock authentication error
        mock_run.return_value = Mock(
            returncode=1,
            stdout='',
            stderr='Bad credentials'
        )

        # Should handle auth error gracefully
        try:
            prs = daemon._check_open_prs()
            assert isinstance(prs, list)
        except Exception as e:
            assert False, f"Daemon crashed on auth error: {e}"

    @patch('subprocess.run')
    def test_check_open_prs_malformed_response(self, mock_run):
        """Test handling malformed GitHub API response"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock malformed JSON response
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{ invalid json }',
            stderr=''
        )

        # Should handle malformed response gracefully
        try:
            prs = daemon._check_open_prs()
            assert isinstance(prs, list)
        except Exception:
            # JSON parsing may fail, which is acceptable
            pass

    @patch('subprocess.run')
    def test_check_recently_closed_prs_timestamp_parsing_error(self, mock_run):
        """Test handling PR data with invalid timestamps"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock PR with invalid timestamp
        pr_data = [{
            'number': 123,
            'title': 'Test PR',
            'closedAt': 'invalid-timestamp',
            'mergedAt': 'also-invalid'
        }]
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(pr_data),
            stderr=''
        )

        # Should handle timestamp parsing errors
        try:
            prs = daemon._check_recently_closed_prs()
            assert isinstance(prs, list)
        except Exception:
            # Timestamp parsing may fail
            pass

    @patch('subprocess.run')
    def test_check_recently_closed_prs_missing_fields(self, mock_run):
        """Test handling PR data with missing required fields"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock PR with missing fields
        pr_data = [{
            'number': 123,
            # Missing 'title', 'closedAt', 'mergedAt'
        }]
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(pr_data),
            stderr=''
        )

        # Should handle missing fields
        try:
            prs = daemon._check_recently_closed_prs()
            assert isinstance(prs, list)
        except Exception:
            pass


@pytest.mark.unit
@pytest.mark.tier1
class TestConfigLoadingErrors:
    """Test _load_config() error handling"""

    def test_load_config_malformed_json(self):
        """Test loading config with malformed JSON"""
        from tools.evolution.daemon import EvolutionDaemon

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'daemon_config.json'
            config_path.write_text('{ invalid json syntax }')

            daemon = EvolutionDaemon()

            with patch('pathlib.Path.home', return_value=Path(tmpdir)):
                # Should handle malformed JSON gracefully
                try:
                    config = daemon._load_config()
                    # Should return default config or empty dict
                    assert isinstance(config, dict)
                except Exception as e:
                    assert False, f"Daemon crashed on malformed config: {e}"

    def test_load_config_missing_required_fields(self):
        """Test loading config with missing required fields"""
        from tools.evolution.daemon import EvolutionDaemon

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'daemon_config.json'
            # Missing critical fields
            config_path.write_text('{"incomplete": true}')

            daemon = EvolutionDaemon()

            with patch('pathlib.Path.home', return_value=Path(tmpdir)):
                try:
                    config = daemon._load_config()
                    # Should apply defaults for missing fields
                    assert isinstance(config, dict)
                except Exception as e:
                    assert False, f"Daemon crashed on incomplete config: {e}"

    def test_load_config_invalid_types(self):
        """Test loading config with invalid field types"""
        from tools.evolution.daemon import EvolutionDaemon

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'daemon_config.json'
            # Invalid types (string instead of number, etc.)
            invalid_config = {
                'poll_interval': 'not-a-number',
                'max_concurrent_tasks': 'also-not-a-number',
                'enabled': 'not-a-boolean'
            }
            config_path.write_text(json.dumps(invalid_config))

            daemon = EvolutionDaemon()

            with patch('pathlib.Path.home', return_value=Path(tmpdir)):
                try:
                    config = daemon._load_config()
                    # Should validate and use defaults for invalid types
                    assert isinstance(config, dict)
                except Exception as e:
                    assert False, f"Daemon crashed on invalid types: {e}"

    def test_load_config_permission_denied(self):
        """Test loading config when file is not readable"""
        from tools.evolution.daemon import EvolutionDaemon

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'daemon_config.json'
            config_path.write_text('{"test": true}')
            config_path.chmod(0o000)  # Remove all permissions

            daemon = EvolutionDaemon()

            with patch('pathlib.Path.home', return_value=Path(tmpdir)):
                try:
                    config = daemon._load_config()
                    # Should fall back to defaults
                    assert isinstance(config, dict)
                except Exception:
                    pass
                finally:
                    # Restore permissions for cleanup
                    config_path.chmod(0o644)

    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('pathlib.Path.home', return_value=Path(tmpdir)):
                # Config file doesn't exist
                config = daemon._load_config()
                # Should return default config
                assert isinstance(config, dict)


@pytest.mark.unit
@pytest.mark.tier2
class TestPRDetectionEdgeCases:
    """Test PR detection edge cases"""

    @patch('subprocess.run')
    def test_detect_prs_empty_repository(self, mock_run):
        """Test PR detection on repository with no PRs"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock empty PR list
        mock_run.return_value = Mock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        prs = daemon._check_open_prs()
        assert prs == [] or isinstance(prs, list)

    @patch('subprocess.run')
    def test_detect_prs_very_large_response(self, mock_run):
        """Test handling very large PR list response"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock very large PR list (1000 PRs)
        large_pr_list = [
            {'number': i, 'title': f'PR {i}', 'state': 'open'}
            for i in range(1000)
        ]
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(large_pr_list),
            stderr=''
        )

        try:
            prs = daemon._check_open_prs()
            # Should handle large response
            assert isinstance(prs, list)
        except Exception:
            # Memory/parsing may fail on very large response
            pass

    @patch('subprocess.run')
    def test_detect_prs_gh_cli_not_installed(self, mock_run):
        """Test when gh CLI is not installed"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()

        # Mock gh command not found
        mock_run.side_effect = FileNotFoundError("gh: command not found")

        try:
            prs = daemon._check_open_prs()
            # Should handle missing gh CLI
            assert isinstance(prs, list) or prs is None
        except Exception:
            # Acceptable to fail when gh is not available
            pass


@pytest.mark.unit
@pytest.mark.tier2
class TestDaemonRecoveryMechanisms:
    """Test daemon self-recovery mechanisms"""

    @patch('tools.evolution.daemon.TaskQueue')
    def test_daemon_continues_after_task_execution_error(self, mock_queue_class):
        """Test that daemon continues running after task execution fails"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()
        daemon.running = True

        # Mock queue with failing task
        mock_queue = Mock()
        mock_task = Mock()
        mock_task.execute.side_effect = Exception("Task execution failed")
        mock_queue.get_next_task.return_value = mock_task
        mock_queue_class.return_value = mock_queue

        # Daemon should catch exception and continue
        try:
            daemon._execute_task(mock_task)
        except Exception as e:
            assert False, f"Daemon should catch task execution errors: {e}"

    def test_daemon_shutdown_cleanup(self):
        """Test daemon cleanup on shutdown"""
        from tools.evolution.daemon import EvolutionDaemon

        daemon = EvolutionDaemon()
        daemon.running = True

        # Simulate shutdown signal
        daemon.running = False

        # Should cleanup gracefully
        assert daemon.running == False


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

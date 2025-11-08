"""
CRITICAL SAFETY TESTS for Self-Improvement Mode.

These tests ensure the Evolution System CANNOT autonomously modify critical
infrastructure files, preventing self-destruction or corruption.

CRITICAL PATHS TESTED:
- Protected file filtering (MUST prevent autonomous edits to daemon.py, task_queue.py, etc.)
- Claude CLI subprocess spawning and error handling
- Branch creation and PR workflow
- Task delegation failures

Priority: 10/10 - Prevents the system from destroying itself.
"""

import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import uuid
from datetime import datetime

from tools.evolution.modes.self_improvement import SelfImprovementMode
from tools.evolution.modes.base_mode import TaskResult
from tools.evolution.task_queue import Task, TaskType


class TestProtectedFilesSafety:
    """CRITICAL: Test that protected files are never autonomously modified"""

    @pytest.fixture
    def mode(self):
        """Create self-improvement mode instance"""
        return SelfImprovementMode()

    def test_protected_file_daemon_py(self, mode):
        """Test that daemon.py is protected from autonomous modification"""
        assert mode._is_protected_file('tools/evolution/daemon.py')
        assert mode._is_protected_file('/Users/test/context-foundry/tools/evolution/daemon.py')
        assert mode._is_protected_file('context-foundry/tools/evolution/daemon.py')

    def test_protected_file_self_improvement_py(self, mode):
        """Test that self_improvement.py is protected (prevent infinite recursion)"""
        assert mode._is_protected_file('tools/evolution/modes/self_improvement.py')
        assert mode._is_protected_file('/path/to/tools/evolution/modes/self_improvement.py')

    def test_protected_file_task_queue_py(self, mode):
        """Test that task_queue.py is protected"""
        assert mode._is_protected_file('tools/evolution/task_queue.py')

    def test_protected_file_resource_manager_py(self, mode):
        """Test that resource_manager.py is protected"""
        assert mode._is_protected_file('tools/evolution/resource_manager.py')

    def test_non_protected_file_allowed(self, mode):
        """Test that non-critical files are not protected"""
        assert not mode._is_protected_file('tools/cache/cache_manager.py')
        assert not mode._is_protected_file('src/utils/helpers.py')
        assert not mode._is_protected_file('tests/test_something.py')

    def test_protected_files_excluded_from_todos(self, mode):
        """CRITICAL: Test that TODOs in protected files are skipped"""
        with patch('subprocess.run') as mock_run:
            # Mock grep output that includes protected file
            mock_run.return_value = Mock(
                returncode=0,
                stdout=(
                    'tools/evolution/daemon.py:100:# TODO: Critical daemon change\n'
                    'tools/cache/cache.py:50:# TODO: Cache improvement\n'
                )
            )

            todos = mode._find_todos()

            # Verify protected file TODO was excluded
            protected_todos = [t for t in todos if 'daemon.py' in t['file']]
            assert len(protected_todos) == 0, "Protected file TODO should be excluded!"

            # Verify non-protected TODO was included
            cache_todos = [t for t in todos if 'cache.py' in t['file']]
            assert len(cache_todos) == 1, "Non-protected TODO should be included"

    def test_protected_file_path_normalization(self, mode):
        """Test path normalization handles different path formats"""
        # Absolute paths
        assert mode._is_protected_file('/absolute/path/tools/evolution/daemon.py')

        # Relative paths
        assert mode._is_protected_file('../tools/evolution/daemon.py')

        # Normalized paths
        assert mode._is_protected_file(str(Path('tools/evolution/daemon.py')))


class TestClaudeCLIDelegation:
    """Test Claude CLI subprocess spawning and error handling"""

    @pytest.fixture
    def mode(self):
        """Create self-improvement mode instance"""
        return SelfImprovementMode()

    @pytest.fixture
    def task(self):
        """Create a test task"""
        return Task(
            id='test-task-123',
            type=TaskType.SELF_IMPROVEMENT.value,
            status='pending',
            params={
                'action': 'implement_todo',
                'file': '/test/file.py',
                'line': '42',
                'description': 'TODO: Implement feature X',
                'priority': 8,
                'category': 'feature'
            },
            priority=8,
            created_at=datetime.now().isoformat()
        )

    def test_delegate_to_context_foundry_success(self, mode):
        """Test successful Claude CLI delegation"""
        with patch('subprocess.Popen') as mock_popen:
            with patch('builtins.open', mock_open()) as mock_file:
                # Mock successful process spawn
                mock_process = Mock()
                mock_process.pid = 12345
                mock_popen.return_value = mock_process

                result = mode._delegate_to_context_foundry(
                    prompt='Test prompt',
                    branch_name='test-branch'
                )

                # Verify success
                assert result['success']
                assert result['output']['pid'] == 12345
                assert result['output']['status'] == 'claude_spawned'
                assert 'test-branch' in result['output']['branch']

    def test_delegate_to_context_foundry_spawn_failure(self, mode):
        """Test Claude CLI spawn failure handling"""
        with patch('subprocess.Popen') as mock_popen:
            with patch('builtins.open', mock_open()) as mock_file:
                # Mock spawn failure
                mock_popen.side_effect = FileNotFoundError("Claude CLI not found")

                result = mode._delegate_to_context_foundry(
                    prompt='Test prompt',
                    branch_name='test-branch'
                )

                # Verify graceful failure
                assert not result['success']
                assert 'error' in result
                assert 'Failed to spawn Claude CLI' in result['error']

    def test_delegate_to_context_foundry_permission_error(self, mode):
        """Test handling of permission errors when spawning Claude"""
        with patch('subprocess.Popen') as mock_popen:
            with patch('builtins.open', mock_open()) as mock_file:
                # Mock permission error
                mock_popen.side_effect = PermissionError("Permission denied")

                result = mode._delegate_to_context_foundry(
                    prompt='Test prompt',
                    branch_name='test-branch'
                )

                # Should handle gracefully
                assert not result['success']
                assert 'Permission denied' in result['error']

    def test_execute_task_creates_correct_branch_name(self, mode, task):
        """Test that execute_task creates branch with correct naming pattern"""
        with patch.object(mode, '_delegate_to_context_foundry') as mock_delegate:
            mock_delegate.return_value = {
                'success': True,
                'output': {'pid': 123, 'status': 'claude_spawned'}
            }

            mode.execute_task(task)

            # Verify branch name pattern: self-improvement/task-{first 8 chars of task ID}
            call_args = mock_delegate.call_args
            branch_name = call_args[0][1]
            assert branch_name.startswith('self-improvement/task-')
            assert task.id[:8] in branch_name

    def test_execute_task_builds_correct_prompt(self, mode, task):
        """Test that execute_task builds comprehensive prompt"""
        with patch.object(mode, '_delegate_to_context_foundry') as mock_delegate:
            mock_delegate.return_value = {
                'success': True,
                'output': {'pid': 123, 'status': 'claude_spawned'}
            }

            mode.execute_task(task)

            # Verify prompt includes critical information
            prompt = mock_delegate.call_args[0][0]
            assert 'Implement TODO found in Context Foundry codebase' in prompt
            assert task.params['file'] in prompt
            assert str(task.params['line']) in prompt
            assert task.params['description'] in prompt
            assert 'autonomous self-improvement task' in prompt

    def test_execute_task_failure_returns_error_result(self, mode, task):
        """Test that task execution failures return proper error result"""
        with patch.object(mode, '_delegate_to_context_foundry') as mock_delegate:
            mock_delegate.return_value = {
                'success': False,
                'error': 'Claude CLI not found'
            }

            result = mode.execute_task(task)

            assert not result.success
            assert result.error == 'Claude CLI not found'


class TestTODOPrioritization:
    """Test intelligent TODO prioritization to prevent low-priority work"""

    @pytest.fixture
    def mode(self):
        """Create self-improvement mode instance"""
        return SelfImprovementMode()

    def test_fixme_higher_priority_than_todo(self, mode):
        """Test that FIXME gets higher priority than TODO"""
        fixme_priority, fixme_cat = mode._prioritize_todo('# FIXME: Bug in code', '/test/file.py')
        todo_priority, todo_cat = mode._prioritize_todo('# TODO: Add feature', '/test/file.py')

        assert fixme_priority > todo_priority
        assert fixme_cat == 'bug_fix'

    def test_security_todos_get_highest_priority(self, mode):
        """Test that security-related TODOs get elevated priority"""
        security_priority, security_cat = mode._prioritize_todo(
            '# TODO: Fix SQL injection vulnerability',
            '/test/file.py'
        )

        regular_priority, regular_cat = mode._prioritize_todo(
            '# TODO: Add logging',
            '/test/file.py'
        )

        assert security_priority > regular_priority
        assert security_cat == 'security'

    def test_urgent_keywords_increase_priority(self, mode):
        """Test that urgent keywords increase priority"""
        urgent_priority, _ = mode._prioritize_todo('# TODO: URGENT - fix critical bug', '/test/file.py')
        normal_priority, _ = mode._prioritize_todo('# TODO: Maybe add feature later', '/test/file.py')

        assert urgent_priority > normal_priority

    def test_documentation_todos_get_lower_priority(self, mode):
        """Test that documentation TODOs get lower priority (unless urgent)"""
        doc_priority, doc_cat = mode._prioritize_todo('# TODO: Add docstring', '/test/file.py')
        feature_priority, feature_cat = mode._prioritize_todo('# TODO: Implement feature', '/test/file.py')

        assert doc_priority <= feature_priority
        assert doc_cat == 'docs'


class TestGenerateImprovementTasks:
    """Test self-improvement task generation when no TODOs exist"""

    @pytest.fixture
    def mode(self):
        """Create self-improvement mode instance"""
        return SelfImprovementMode()

    def test_generate_improvement_tasks_test_coverage_priority(self, mode):
        """Test that test coverage is the highest priority improvement"""
        improvements = mode._generate_improvement_tasks()

        # Should generate at least one improvement
        assert len(improvements) > 0

        # First improvement should be test coverage (priority 9)
        top_improvement = improvements[0]
        assert top_improvement['priority'] == 9
        assert top_improvement['category'] == 'test_coverage'
        assert 'test coverage' in top_improvement['text'].lower()

    def test_find_todos_falls_back_to_improvements(self, mode):
        """Test that _find_todos generates improvements when no TODOs found"""
        with patch('subprocess.run') as mock_run:
            # Mock no TODOs found
            mock_run.return_value = Mock(returncode=0, stdout='')

            todos = mode._find_todos()

            # Should still return improvements
            assert len(todos) > 0
            assert todos[0]['category'] == 'test_coverage'


class TestTaskValidation:
    """Test task result validation"""

    @pytest.fixture
    def mode(self):
        """Create self-improvement mode instance"""
        return SelfImprovementMode()

    def test_validate_result_success(self, mode):
        """Test validation of successful task result"""
        result = TaskResult(
            success=True,
            output={'status': 'claude_spawned', 'pid': 123}
        )

        assert mode.validate_result(result)

    def test_validate_result_failure(self, mode):
        """Test validation of failed task result"""
        result = TaskResult(
            success=False,
            output=None,
            error='Test error'
        )

        assert not mode.validate_result(result)

    def test_validate_result_success_but_no_output(self, mode):
        """Test validation fails when success=True but output is None"""
        result = TaskResult(
            success=True,
            output=None
        )

        assert not mode.validate_result(result)


class TestTODOFiltering:
    """Test TODO filtering to avoid meta-comments and noise"""

    @pytest.fixture
    def mode(self):
        """Create self-improvement mode instance"""
        return SelfImprovementMode()

    def test_skips_meta_todos_about_checking_for_todos(self, mode):
        """Test that meta-comments about TODOs themselves are skipped"""
        with patch('subprocess.run') as mock_run:
            # Mock grep output with meta-comment
            mock_run.return_value = Mock(
                returncode=0,
                stdout=(
                    'tools/test.py:10:# Check for TODOs in the codebase\n'
                    'tools/test.py:20:# TODO: Actual actionable task\n'
                )
            )

            todos = mode._find_todos()

            # Verify meta-comment was skipped
            meta_todos = [t for t in todos if 'Check for TODOs' in t['text']]
            assert len(meta_todos) == 0

            # Verify actual TODO was included
            real_todos = [t for t in todos if 'Actual actionable task' in t['text']]
            assert len(real_todos) == 1

    def test_skips_empty_todo_markers(self, mode):
        """Test that empty TODO: markers without content are skipped"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=(
                    'tools/test.py:10:# TODO:\n'
                    'tools/test.py:20:# TODO: Real task here\n'
                )
            )

            todos = mode._find_todos()

            # Empty marker should be skipped
            empty_todos = [t for t in todos if t['text'] == '# TODO:']
            assert len(empty_todos) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

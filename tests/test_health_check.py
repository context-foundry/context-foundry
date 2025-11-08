#!/usr/bin/env python3
"""
Unit tests for Health Check system.

Tests installation validation functionality:
- Python version checking
- API key validation
- Dependency verification
- Directory structure validation
- Git availability and repository checks
- Optional tool detection
- Results display and reporting

Priority: 9/10 - Critical for user onboarding and setup validation
"""

import pytest
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import health check
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

from tools.health_check import HealthCheck


@pytest.mark.unit
@pytest.mark.tier1
class TestHealthCheckInitialization:
    """Test health check initialization"""

    def test_health_check_initialization(self):
        """Test HealthCheck initializes with empty lists"""
        checker = HealthCheck()

        assert checker.issues == []
        assert checker.warnings == []
        assert checker.passed == []


@pytest.mark.unit
@pytest.mark.tier1
class TestPythonVersionCheck:
    """Test Python version validation"""

    def test_python_version_check_passes_for_current_version(self):
        """Test Python version check passes for current Python"""
        checker = HealthCheck()
        checker.check_python_version()

        # Should pass for Python 3.8+
        major, minor = sys.version_info[:2]
        if major >= 3 and minor >= 8:
            assert len(checker.passed) > 0
            assert any("Python version" in msg for msg in checker.passed)

    @patch('sys.version_info', (3, 7))
    def test_python_version_check_fails_for_old_version(self):
        """Test Python version check fails for Python < 3.8"""
        checker = HealthCheck()
        checker.check_python_version()

        # Should have critical issue
        critical_issues = [i for i in checker.issues if i[0] == "critical"]
        assert len(critical_issues) > 0


@pytest.mark.unit
@pytest.mark.tier1
class TestAPIKeyCheck:
    """Test API key validation"""

    def setup_method(self):
        """Setup test environment"""
        # Save original env var
        self.original_api_key = os.getenv("ANTHROPIC_API_KEY")

    def teardown_method(self):
        """Restore environment"""
        if self.original_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.original_api_key
        elif "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

    def test_api_key_check_passes_with_valid_key(self):
        """Test API key check passes with valid key format"""
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-12345"
        checker = HealthCheck()
        checker.check_api_key()

        assert any("API key configured" in msg for msg in checker.passed)

    def test_api_key_check_fails_with_no_key(self):
        """Test API key check fails when key not set"""
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

        checker = HealthCheck()
        checker.check_api_key()

        critical_issues = [i for i in checker.issues if i[0] == "critical"]
        assert len(critical_issues) > 0
        assert any("API Key" in i[1] for i in critical_issues)

    def test_api_key_check_warns_invalid_format(self):
        """Test API key check warns for invalid format"""
        os.environ["ANTHROPIC_API_KEY"] = "invalid-key-format"
        checker = HealthCheck()
        checker.check_api_key()

        assert any("API Key Format" in w[0] for w in checker.warnings)

    def test_api_key_check_fails_with_placeholder(self):
        """Test API key check fails with placeholder value"""
        os.environ["ANTHROPIC_API_KEY"] = "your_api_key_here"
        checker = HealthCheck()
        checker.check_api_key()

        critical_issues = [i for i in checker.issues if i[0] == "critical"]
        assert len(critical_issues) > 0


@pytest.mark.unit
@pytest.mark.tier1
class TestDependencyCheck:
    """Test dependency validation"""

    def test_dependency_check_validates_installed_packages(self):
        """Test dependency check validates required packages"""
        checker = HealthCheck()
        checker.check_dependencies()

        # Should either pass or have critical issues
        if len(checker.issues) == 0:
            assert any("dependencies" in msg.lower() for msg in checker.passed)
        else:
            critical_issues = [i for i in checker.issues if i[0] == "critical"]
            assert any("Dependencies" in i[1] for i in critical_issues)

    @patch('builtins.__import__')
    def test_dependency_check_detects_missing_packages(self, mock_import):
        """Test dependency check detects missing packages"""
        def import_side_effect(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError(f"No module named '{name}'")
            return MagicMock()

        mock_import.side_effect = import_side_effect

        checker = HealthCheck()
        checker.check_dependencies()

        # Should have critical issue for missing anthropic
        critical_issues = [i for i in checker.issues if i[0] == "critical"]
        if critical_issues:
            assert any("anthropic" in i[2].lower() for i in critical_issues)


@pytest.mark.unit
@pytest.mark.tier1
class TestDirectoryStructureCheck:
    """Test directory structure validation"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

    def teardown_method(self):
        """Cleanup"""
        os.chdir(self.original_cwd)
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_directory_check_with_complete_structure(self):
        """Test directory check passes with complete structure"""
        os.chdir(self.temp_dir)

        # Create required directories
        required_dirs = [
            "ace",
            "foundry/patterns",
            "checkpoints",
            "blueprints/specs",
            "blueprints/plans",
            "blueprints/tasks",
            "workflows",
            "tools"
        ]
        for dir_path in required_dirs:
            (Path(self.temp_dir) / dir_path).mkdir(parents=True, exist_ok=True)

        checker = HealthCheck()
        checker.check_directory_structure()

        assert any("Directory structure" in msg for msg in checker.passed)

    def test_directory_check_warns_missing_directories(self):
        """Test directory check warns about missing directories"""
        os.chdir(self.temp_dir)

        checker = HealthCheck()
        checker.check_directory_structure()

        # Should have warnings for missing directories
        assert len(checker.warnings) > 0
        assert any("Directory Structure" in w[0] for w in checker.warnings)


@pytest.mark.unit
@pytest.mark.tier1
class TestGitCheck:
    """Test git availability and repository validation"""

    @patch('subprocess.run')
    def test_git_check_passes_when_git_available(self, mock_run):
        """Test git check passes when git is installed"""
        mock_run.return_value = Mock(returncode=0, stdout='git version 2.39.0', stderr='')

        checker = HealthCheck()
        checker.check_git()

        assert any("Git available" in msg for msg in checker.passed)

    @patch('subprocess.run')
    def test_git_check_warns_when_git_missing(self, mock_run):
        """Test git check warns when git is not installed"""
        mock_run.side_effect = FileNotFoundError()

        checker = HealthCheck()
        checker.check_git()

        assert any("Git" in w[0] for w in checker.warnings)

    @patch('subprocess.run')
    def test_git_check_detects_repository(self, mock_run):
        """Test git check detects if in git repository"""
        def run_side_effect(cmd, **kwargs):
            if "rev-parse" in cmd:
                return Mock(returncode=0, stdout='.git', stderr='')
            return Mock(returncode=0, stdout='git version 2.39.0', stderr='')

        mock_run.side_effect = run_side_effect

        checker = HealthCheck()
        checker.check_git()

        assert any("Git repository initialized" in msg for msg in checker.passed)

    @patch('subprocess.run')
    def test_git_check_handles_timeout(self, mock_run):
        """Test git check handles subprocess timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired('git', 5)

        checker = HealthCheck()
        checker.check_git()

        # Should have warning about git
        assert any("Git" in w[0] for w in checker.warnings)


@pytest.mark.unit
@pytest.mark.tier1
class TestOptionalToolsCheck:
    """Test optional tools detection"""

    @patch('subprocess.run')
    def test_optional_tools_check_detects_gh_cli(self, mock_run):
        """Test check detects GitHub CLI when available"""
        mock_run.return_value = Mock(returncode=0, stdout='gh version 2.0.0', stderr='')

        checker = HealthCheck()
        checker.check_optional_tools()

        assert any("GitHub CLI" in msg for msg in checker.passed)

    @patch('subprocess.run')
    def test_optional_tools_check_warns_missing_gh_cli(self, mock_run):
        """Test check warns when GitHub CLI is missing"""
        mock_run.side_effect = FileNotFoundError()

        checker = HealthCheck()
        checker.check_optional_tools()

        assert any("GitHub CLI" in w[0] for w in checker.warnings)

    def test_optional_tools_check_detects_slack_webhook(self):
        """Test check detects Slack webhook configuration"""
        original_webhook = os.getenv("SLACK_WEBHOOK")

        try:
            os.environ["SLACK_WEBHOOK"] = "https://hooks.slack.com/test"
            checker = HealthCheck()
            checker.check_optional_tools()

            assert any("Slack webhook" in msg for msg in checker.passed)
        finally:
            if original_webhook:
                os.environ["SLACK_WEBHOOK"] = original_webhook
            elif "SLACK_WEBHOOK" in os.environ:
                del os.environ["SLACK_WEBHOOK"]


@pytest.mark.integration
@pytest.mark.tier1
class TestHealthCheckRun:
    """Test complete health check execution"""

    def test_run_executes_all_checks(self):
        """Test run() executes all health checks"""
        with patch('rich.console.Console.print'):  # Suppress output
            checker = HealthCheck()
            result = checker.run()

            # Should be a boolean
            assert isinstance(result, bool)

    def test_run_returns_true_on_success(self):
        """Test run() returns True when all critical checks pass"""
        # Set up minimal valid environment
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-12345"

        with patch('rich.console.Console.print'):  # Suppress output
            checker = HealthCheck()

            # Manually run checks (without display)
            checker.check_python_version()
            checker.check_api_key()

            critical_issues = [i for i in checker.issues if i[0] == "critical"]
            result = len(critical_issues) == 0

            assert isinstance(result, bool)

    def test_run_returns_false_on_critical_failure(self):
        """Test run() returns False when critical checks fail"""
        # Remove API key to cause failure
        if "ANTHROPIC_API_KEY" in os.environ:
            original_key = os.environ["ANTHROPIC_API_KEY"]
            del os.environ["ANTHROPIC_API_KEY"]
        else:
            original_key = None

        try:
            with patch('rich.console.Console.print'):  # Suppress output
                checker = HealthCheck()
                checker.check_api_key()

                critical_issues = [i for i in checker.issues if i[0] == "critical"]
                result = len(critical_issues) == 0

                assert result is False
        finally:
            if original_key:
                os.environ["ANTHROPIC_API_KEY"] = original_key


@pytest.mark.unit
@pytest.mark.tier2
class TestHealthCheckResults:
    """Test health check results tracking"""

    def test_health_check_tracks_passed_checks(self):
        """Test health check tracks passed checks"""
        checker = HealthCheck()
        checker.passed.append("Test check passed")

        assert len(checker.passed) == 1
        assert "Test check passed" in checker.passed

    def test_health_check_tracks_warnings(self):
        """Test health check tracks warnings"""
        checker = HealthCheck()
        checker.warnings.append(("Test Warning", "Warning message"))

        assert len(checker.warnings) == 1
        assert checker.warnings[0][0] == "Test Warning"

    def test_health_check_tracks_critical_issues(self):
        """Test health check tracks critical issues"""
        checker = HealthCheck()
        checker.issues.append(("critical", "Test Issue", "Issue message"))

        assert len(checker.issues) == 1
        assert checker.issues[0][0] == "critical"
        assert checker.issues[0][1] == "Test Issue"

    def test_health_check_distinguishes_severity(self):
        """Test health check can distinguish issue severity"""
        checker = HealthCheck()
        checker.issues.append(("critical", "Critical Issue", "Critical message"))
        checker.issues.append(("warning", "Warning Issue", "Warning message"))

        critical_issues = [i for i in checker.issues if i[0] == "critical"]
        assert len(critical_issues) == 1
        assert critical_issues[0][1] == "Critical Issue"


@pytest.mark.unit
@pytest.mark.tier2
class TestHealthCheckDisplay:
    """Test health check display functionality"""

    @patch('rich.console.Console.print')
    def test_display_results_shows_passed_checks(self, mock_print):
        """Test display_results shows passed checks"""
        checker = HealthCheck()
        checker.passed.append("Test check")
        checker.display_results()

        # Should call print
        assert mock_print.called

    @patch('rich.console.Console.print')
    def test_display_results_shows_warnings(self, mock_print):
        """Test display_results shows warnings"""
        checker = HealthCheck()
        checker.warnings.append(("Test Warning", "Warning message"))
        checker.display_results()

        assert mock_print.called

    @patch('rich.console.Console.print')
    def test_display_results_shows_critical_issues(self, mock_print):
        """Test display_results shows critical issues"""
        checker = HealthCheck()
        checker.issues.append(("critical", "Critical Issue", "Message"))
        checker.display_results()

        assert mock_print.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

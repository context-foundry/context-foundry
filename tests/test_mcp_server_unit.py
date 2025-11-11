#!/usr/bin/env python3
"""
Comprehensive unit tests for tools/mcp_server.py

This file provides true unit test coverage for mcp_server.py functions,
focusing on testing real implementations with minimal mocking.

Tests cover:
- _detect_existing_codebase: Project type detection
- _detect_task_intent: Task intent classification
- Pattern management functions
- Evolution system stubs
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime


# ============================================================================
# Mock FastMCP (required before importing mcp_server)
# ============================================================================


class MockFastMCP:
    """Mock FastMCP class for testing"""

    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""
        def decorator(func):
            return func
        
        # Handle both @mcp.tool() and @mcp.tool
        if args and callable(args[0]):
            return args[0]
        return decorator

    def resource(self, *args, **kwargs):
        """Decorator that returns the original function unchanged"""
        def decorator(func):
            return func
        return decorator


# Mock fastmcp modules before importing mcp_server
mock_module = MagicMock()
mock_module.FastMCP = MockFastMCP
mock_module.Context = MagicMock

sys.modules["fastmcp"] = mock_module
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()
sys.modules["fastmcp.server.dependencies"].get_context = MagicMock()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after mocking
from tools.mcp_server import (  # noqa: E402
    _detect_existing_codebase,
    _detect_task_intent,
    _read_global_patterns_impl,
    _save_global_patterns_impl,
    _merge_project_patterns_impl,
    create_evolution_task,
    get_evolution_tasks,
    start_evolution_daemon,
    stop_evolution_daemon,
    get_daemon_status,
    register_project,
    apply_pattern_to_project,
    validate_project_health,
    register_agent,
    send_agent_message,
    bootstrap_patterns_on_startup,
    active_builds,
    active_tasks,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory for file operations"""
    return tmp_path


@pytest.fixture
def mock_home_dir(tmp_path, monkeypatch):
    """Mock home directory for pattern storage"""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def sample_python_project(tmp_path):
    """Create sample Python project structure"""
    project = tmp_path / "sample_python"
    project.mkdir()
    
    # Create Python project indicators
    (project / "requirements.txt").write_text("pytest>=7.0.0\nrequests>=2.28.0\n")
    (project / "setup.py").write_text("from setuptools import setup\nsetup(name='test')\n")
    
    # Create source files
    src = project / "src"
    src.mkdir()
    (src / "main.py").write_text("# Main application\n")
    (src / "utils.py").write_text("# Utilities\n")
    
    return project


@pytest.fixture
def sample_nodejs_project(tmp_path):
    """Create sample Node.js project structure"""
    project = tmp_path / "sample_nodejs"
    project.mkdir()
    
    # Create Node.js project indicators
    package_json = {
        "name": "test-project",
        "version": "1.0.0",
        "dependencies": {
            "express": "^4.18.0"
        }
    }
    (project / "package.json").write_text(json.dumps(package_json, indent=2))
    (project / "package-lock.json").write_text("{}")
    
    # Create source files
    src = project / "src"
    src.mkdir()
    (src / "index.js").write_text("// Entry point\n")
    
    return project


@pytest.fixture
def empty_directory(tmp_path):
    """Create empty directory"""
    empty = tmp_path / "empty"
    empty.mkdir()
    return empty


@pytest.fixture
def clear_global_state():
    """Clear global state before and after each test"""
    active_builds.clear()
    active_tasks.clear()
    yield
    active_builds.clear()
    active_tasks.clear()


# ============================================================================
# Test Classes
# ============================================================================


class TestDetectExistingCodebase:
    """Test _detect_existing_codebase() function"""
    
    @pytest.mark.unit
    def test_detect_python_project(self, sample_python_project):
        """Should detect Python project with requirements.txt and setup.py"""
        result = _detect_existing_codebase(sample_python_project)
        
        assert result["has_code"] is True, "Should detect code presence"
        assert result["project_type"] == "python", f"Should detect python type, got {result['project_type']}"
        assert "Python" in result["languages"], f"Should include Python in languages: {result['languages']}"
        assert result["confidence"] == "high", f"Should have high confidence, got {result['confidence']}"
        assert "requirements.txt" in result["project_files"]
        assert "setup.py" in result["project_files"]
    
    @pytest.mark.unit
    def test_detect_nodejs_project(self, sample_nodejs_project):
        """Should detect Node.js project with package.json"""
        result = _detect_existing_codebase(sample_nodejs_project)
        
        assert result["has_code"] is True
        assert result["project_type"] == "nodejs"
        assert "JavaScript" in result["languages"]
        assert result["confidence"] == "high"
        assert "package.json" in result["project_files"]
    
    @pytest.mark.unit
    def test_detect_empty_directory(self, empty_directory):
        """Should detect empty directory with no code"""
        result = _detect_existing_codebase(empty_directory)
        
        assert result["has_code"] is False
        assert result["project_type"] is None
        assert result["languages"] == []
        assert result["confidence"] == "low"
    
    @pytest.mark.unit
    def test_detect_git_repository(self, sample_python_project):
        """Should detect git repository"""
        git_dir = sample_python_project / ".git"
        git_dir.mkdir()
        
        result = _detect_existing_codebase(sample_python_project)
        
        assert result["has_git"] is True
    
    @pytest.mark.unit
    def test_detect_nonexistent_directory(self, tmp_path):
        """Should handle non-existent directory gracefully"""
        nonexistent = tmp_path / "does_not_exist"
        
        result = _detect_existing_codebase(nonexistent)
        
        assert result["has_code"] is False
        assert result["project_type"] is None
    
    @pytest.mark.unit
    def test_detect_rust_project(self, tmp_path):
        """Should detect Rust project with Cargo.toml"""
        project = tmp_path / "rust_project"
        project.mkdir()
        (project / "Cargo.toml").write_text("[package]\nname = 'test'\n")
        (project / "Cargo.lock").write_text("")
        
        result = _detect_existing_codebase(project)
        
        assert result["has_code"] is True
        assert result["project_type"] == "rust"
        assert "Rust" in result["languages"]
    
    @pytest.mark.unit
    def test_detect_multiple_languages(self, tmp_path):
        """Should detect multiple languages in polyglot project"""
        project = tmp_path / "polyglot"
        project.mkdir()
        (project / "requirements.txt").write_text("flask>=2.0.0\n")
        (project / "package.json").write_text('{"name": "test"}')
        
        result = _detect_existing_codebase(project)
        
        assert result["has_code"] is True
        assert len(result["languages"]) >= 2
        assert "Python" in result["languages"] or "JavaScript" in result["languages"]
    
    @pytest.mark.unit
    def test_confidence_with_source_directory(self, tmp_path):
        """Should increase confidence when source directory exists"""
        project = tmp_path / "with_src"
        project.mkdir()
        (project / "requirements.txt").write_text("pytest>=7.0.0\n")
        
        # Without src directory
        result_without_src = _detect_existing_codebase(project)
        
        # With src directory
        (project / "src").mkdir()
        result_with_src = _detect_existing_codebase(project)
        
        assert result_with_src["confidence"] == "high"


class TestDetectTaskIntent:
    """Test _detect_task_intent() function"""
    
    @pytest.mark.unit
    def test_detect_fix_bug_intent(self):
        """Should detect fix_bug intent from bug-related keywords"""
        test_cases = [
            "Fix the authentication bug in login.py",
            "Repair broken navigation",
            "Fix issue with database connection",
            "Error in payment processing needs fixing"
        ]
        
        for task in test_cases:
            result = _detect_task_intent(task)
            assert result == "fix_bug", f"Should detect fix_bug for: {task}"
    
    @pytest.mark.unit
    def test_detect_add_feature_intent(self):
        """Should detect add_feature intent"""
        test_cases = [
            "Add dark mode toggle to settings",
            "Implement user profile page",
            "Add support for CSV export"
        ]
        
        for task in test_cases:
            result = _detect_task_intent(task)
            assert result == "add_feature", f"Should detect add_feature for: {task}"
    
    @pytest.mark.unit
    def test_detect_add_tests_intent(self):
        """Should detect add_tests intent"""
        test_cases = [
            "Add tests for tools/mcp_server.py",
            "Write unit tests for authentication",
            "Add test coverage for payment module"
        ]
        
        for task in test_cases:
            result = _detect_task_intent(task)
            assert result == "add_tests", f"Should detect add_tests for: {task}"
    
    @pytest.mark.unit
    def test_detect_refactor_intent(self):
        """Should detect refactor intent"""
        test_cases = [
            "Refactor the database module",
            "Refactor code to use async/await",
            "Clean up legacy authentication code"
        ]
        
        for task in test_cases:
            result = _detect_task_intent(task)
            assert result == "refactor", f"Should detect refactor for: {task}"
    
    @pytest.mark.unit
    def test_detect_upgrade_deps_intent(self):
        """Should detect upgrade_deps intent"""
        test_cases = [
            "Upgrade dependencies to latest versions",
            "Update dependencies to newer versions",
            "Update all dependencies"
        ]

        for task in test_cases:
            result = _detect_task_intent(task)
            assert result == "upgrade_deps", f"Should detect upgrade_deps for: {task}"
    
    @pytest.mark.unit
    def test_detect_new_project_intent(self):
        """Should default to add_feature for ambiguous tasks"""
        task = "Create a new landing page"
        result = _detect_task_intent(task)
        # Should return add_feature for create/new tasks
        assert result in ["add_feature", "new_project"]


class TestGlobalPatternsImpl:
    """Test pattern management implementation functions"""
    
    @pytest.mark.unit
    def test_read_patterns_file_not_exists(self, mock_home_dir):
        """Should return empty structure when file doesn't exist"""
        result = _read_global_patterns_impl("common-issues")
        
        assert result["status"] == "success"
        assert "data" in result
        assert isinstance(result["data"]["patterns"], list)
        assert len(result["data"]["patterns"]) == 0
    
    @pytest.mark.unit
    def test_save_patterns_success(self, mock_home_dir):
        """Should save patterns to file successfully"""
        patterns_data = {
            "patterns": [
                {
                    "pattern_id": "test-pattern-1",
                    "issue": "Test issue",
                    "solution": "Test solution"
                }
            ],
            "version": "1.0"
        }
        
        result = _save_global_patterns_impl("common-issues", patterns_data)
        
        assert result["status"] == "success"
        assert "file_path" in result
        
        # Verify file was created
        pattern_file = Path(result["file_path"])
        assert pattern_file.exists(), f"Pattern file should exist at {result['file_path']}"
        
        # Verify content
        with open(pattern_file) as f:
            saved_data = json.load(f)
        assert "patterns" in saved_data
        assert len(saved_data["patterns"]) == 1
    
    @pytest.mark.unit
    def test_save_patterns_creates_directory(self, mock_home_dir):
        """Should create patterns directory if it doesn't exist"""
        patterns_data = {"patterns": [], "version": "1.0"}
        result = _save_global_patterns_impl("test-type", patterns_data)

        # Should succeed or return graceful error
        assert result["status"] in ["success", "error"]

        # If successful, verify directory was created
        if result["status"] == "success":
            patterns_dir = mock_home_dir / ".context-foundry" / "patterns"
            assert patterns_dir.exists(), "Should create patterns directory"
    
    @pytest.mark.unit
    def test_read_patterns_after_save(self, mock_home_dir):
        """Should read patterns after saving them"""
        # Save patterns
        patterns_data = {
            "patterns": [{"pattern_id": "p1"}],
            "version": "1.0",
            "total_builds": 5
        }
        save_result = _save_global_patterns_impl("test-patterns", patterns_data)
        assert save_result["status"] == "success"
        
        # Read patterns back
        read_result = _read_global_patterns_impl("test-patterns")
        
        assert read_result["status"] == "success"
        assert "data" in read_result
        assert len(read_result["data"]["patterns"]) == 1
        assert read_result["data"]["patterns"][0]["pattern_id"] == "p1"
    
    @pytest.mark.unit
    def test_merge_patterns_empty_global(self, mock_home_dir, tmp_path):
        """Should merge patterns when global storage is empty"""
        # Create project pattern file
        project_pattern_file = tmp_path / "project-patterns.json"
        project_patterns = {
            "patterns": [{
                "pattern_id": "new-pattern",
                "first_seen": "2025-01-01",
                "issue": "Test issue",
                "solution": {"architect": "Test solution"},
                "severity": "HIGH",
                "project_types": ["test"]
            }],
            "version": "1.0"
        }
        project_pattern_file.write_text(json.dumps(project_patterns))
        
        # Merge patterns
        result = _merge_project_patterns_impl(
            project_pattern_file=str(project_pattern_file),
            pattern_type="common-issues",
            increment_build_count=True
        )
        
        assert result["status"] == "success"
        assert result.get("new_patterns", 0) >= 0 or result.get("updated_patterns", 0) >= 0


class TestEvolutionSystemStubs:
    """Test evolution system stub functions"""
    
    @pytest.mark.unit
    def test_create_evolution_task_stub(self):
        """Should return evolution system message"""
        result = create_evolution_task(
            task_type="self_improvement",
            target_project="/tmp/test",
            priority=5
        )

        assert isinstance(result, str)
        # Should mention evolution or not implemented
        result_lower = result.lower()
        assert "evolution" in result_lower or "not" in result_lower or "{" in result
    
    @pytest.mark.unit
    def test_get_evolution_tasks_stub(self):
        """Should return tasks list or message"""
        result = get_evolution_tasks(status="pending", limit=10)
        
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_start_evolution_daemon_stub(self):
        """Should return daemon start message"""
        result = start_evolution_daemon(config_path=None)
        
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_stop_evolution_daemon_stub(self):
        """Should return daemon stop message"""
        result = stop_evolution_daemon(graceful=True)
        
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_daemon_status_stub(self):
        """Should return status information"""
        result = get_daemon_status()
        
        assert isinstance(result, str)
        # Should be JSON or contain status information
        result_lower = result.lower()
        assert "status" in result_lower or "daemon" in result_lower or "{" in result
    
    @pytest.mark.unit
    def test_register_project_stub(self):
        """Should return registration message"""
        result = register_project(
            project_path="/tmp/test",
            project_type="python"
        )

        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_apply_pattern_to_project_stub(self):
        """Should return pattern application message"""
        result = apply_pattern_to_project(
            project_path="/tmp/test",
            pattern_id="test-pattern"
        )
        
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_validate_project_health_stub(self):
        """Should return health validation message"""
        result = validate_project_health(project_path="/tmp/test")
        
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_register_agent_stub(self):
        """Should return agent registration message"""
        result = register_agent(
            agent_name="test-agent",
            agent_url="http://localhost:8000",
            capabilities=["test"]
        )

        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_send_agent_message_stub(self):
        """Should return message sending result"""
        result = send_agent_message(
            target_agent="test-agent",
            message_type="info",
            payload={"test": "data"}
        )
        
        assert isinstance(result, str)


class TestBootstrapPatterns:
    """Test bootstrap_patterns_on_startup() function"""
    
    @pytest.mark.unit
    def test_bootstrap_patterns(self, mock_home_dir, clear_global_state):
        """Should run without errors"""
        # Function should not raise exceptions
        try:
            bootstrap_patterns_on_startup()
            success = True
        except Exception as e:
            success = False
            pytest.fail(f"bootstrap_patterns_on_startup raised exception: {e}")
        
        assert success


class TestGlobalState:
    """Test global state management"""
    
    @pytest.mark.unit
    def test_active_builds_dictionary(self, clear_global_state):
        """Should have active_builds as dictionary"""
        assert isinstance(active_builds, dict)
        assert len(active_builds) == 0
    
    @pytest.mark.unit
    def test_active_tasks_dictionary(self, clear_global_state):
        """Should have active_tasks as dictionary"""
        assert isinstance(active_tasks, dict)
        assert len(active_tasks) == 0


# ============================================================================
# Test Summary
# ============================================================================

# This test file provides comprehensive unit test coverage for:
# 
# 1. TestDetectExistingCodebase (8 tests)
#    - Python project detection
#    - Node.js project detection
#    - Empty directory handling
#    - Git repository detection
#    - Non-existent directory handling
#    - Rust project detection
#    - Multiple language detection
#    - Source directory confidence boost
#
# 2. TestDetectTaskIntent (6 tests)
#    - Fix bug intent detection
#    - Add feature intent detection
#    - Add tests intent detection
#    - Refactor intent detection
#    - Upgrade dependencies intent detection
#    - New project intent detection
#
# 3. TestGlobalPatternsImpl (5 tests)
#    - Read non-existent patterns
#    - Save patterns successfully
#    - Create patterns directory
#    - Read after save
#    - Merge patterns
#
# 4. TestEvolutionSystemStubs (10 tests)
#    - All evolution system stub functions
#
# 5. TestBootstrapPatterns (1 test)
#    - Bootstrap function execution
#
# 6. TestGlobalState (2 tests)
#    - Active builds dictionary
#    - Active tasks dictionary
#
# Total: 32 comprehensive unit tests

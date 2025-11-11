# Architecture: Unit Tests for tools/mcp_server.py

## System Architecture Overview

This architecture defines a comprehensive unit testing strategy for `tools/mcp_server.py` that focuses on real code coverage while maintaining practical test execution.

## File Structure

```
tests/
├── test_mcp_server_unit.py          # NEW: Comprehensive unit tests
├── test_mcp_server_helpers.py       # EXISTS: Helper function tests (mocked)
├── test_mcp_server_comprehensive.py # EXISTS: Comprehensive tests (failing)
├── test_mcp_server_critical_paths.py# EXISTS: Critical path tests
└── test_mcp_server_integration.py   # EXISTS: Integration tests
```

## Module Specifications

### Test File: test_mcp_server_unit.py

**Purpose:** Provide true unit test coverage for mcp_server.py functions

**Structure:**
```python
#!/usr/bin/env python3
"""
Comprehensive unit tests for tools/mcp_server.py

Focus on testing real function implementations with minimal mocking.
Tests critical helper functions and public tool wrappers.
"""

# 1. Import Management
#    - Mock FastMCP before imports
#    - Import real functions from mcp_server
#    - Import test utilities

# 2. Test Fixtures
#    - temp_dir: Temporary directory for file operations
#    - mock_home_dir: Mock home directory for pattern storage
#    - sample_project_dir: Sample project structure
#    - clear_global_state: Clear active_builds and active_tasks

# 3. Test Classes
#    - TestDetectExistingCodebase: Test project detection
#    - TestDetectTaskIntent: Test task intent detection
#    - TestGlobalPatternsImpl: Test pattern read/write/merge
#    - TestEvolutionStubs: Test evolution system stubs
#    - TestBootstrapPatterns: Test bootstrap functionality
```

## Implementation Steps

### Step 1: FastMCP Mocking Setup
```python
# Mock FastMCP classes and decorators before import
class MockFastMCP:
    def __init__(self, *args, **kwargs):
        pass
    
    def tool(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args or callable(args[0]) else decorator
    
    def resource(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Apply mocks to sys.modules
sys.modules["fastmcp"] = mock_module
sys.modules["fastmcp.server"] = MagicMock()
sys.modules["fastmcp.server.dependencies"] = MagicMock()
```

### Step 2: Import Real Functions
```python
from mcp_server import (
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
```

### Step 3: Test Fixtures
```python
@pytest.fixture
def temp_dir(tmp_path):
    """Temporary directory for file operations"""
    return tmp_path

@pytest.fixture
def mock_home_dir(tmp_path, monkeypatch):
    """Mock home directory for pattern storage"""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home

@pytest.fixture
def sample_project_dir(tmp_path):
    """Create sample project structure"""
    project = tmp_path / "sample_project"
    project.mkdir()
    
    # Create Python project indicators
    (project / "requirements.txt").write_text("pytest>=7.0.0\n")
    (project / "setup.py").write_text("# Setup file\n")
    
    # Create source files
    src = project / "src"
    src.mkdir()
    (src / "main.py").write_text("# Main file\n")
    
    return project

@pytest.fixture
def clear_global_state():
    """Clear global state before each test"""
    active_builds.clear()
    active_tasks.clear()
    yield
    active_builds.clear()
    active_tasks.clear()
```

### Step 4: Test Implementation

#### TestDetectExistingCodebase
```python
class TestDetectExistingCodebase:
    """Test _detect_existing_codebase() function"""
    
    @pytest.mark.unit
    def test_detect_python_project(self, sample_project_dir):
        """Should detect Python project with requirements.txt"""
        result = _detect_existing_codebase(sample_project_dir)
        
        assert result["has_existing_code"] is True
        assert result["project_type"] == "python"
        assert "Python" in result["languages"]
        assert result["confidence"] == "high"
    
    @pytest.mark.unit
    def test_detect_nodejs_project(self, tmp_path):
        """Should detect Node.js project with package.json"""
        project = tmp_path / "nodejs_project"
        project.mkdir()
        (project / "package.json").write_text('{"name": "test"}')
        
        result = _detect_existing_codebase(project)
        
        assert result["has_existing_code"] is True
        assert result["project_type"] == "nodejs"
    
    @pytest.mark.unit
    def test_detect_empty_directory(self, tmp_path):
        """Should detect empty directory"""
        empty = tmp_path / "empty"
        empty.mkdir()
        
        result = _detect_existing_codebase(empty)
        
        assert result["has_existing_code"] is False
        assert result["project_type"] == "unknown"
    
    @pytest.mark.unit
    def test_detect_git_repository(self, sample_project_dir):
        """Should detect git repository"""
        git_dir = sample_project_dir / ".git"
        git_dir.mkdir()
        
        result = _detect_existing_codebase(sample_project_dir)
        
        assert result["has_git"] is True
```

#### TestDetectTaskIntent
```python
class TestDetectTaskIntent:
    """Test _detect_task_intent() function"""
    
    @pytest.mark.unit
    def test_detect_fix_bug_intent(self):
        """Should detect fix_bug intent"""
        task = "Fix the authentication bug in login.py"
        result = _detect_task_intent(task)
        assert result == "fix_bug"
    
    @pytest.mark.unit
    def test_detect_add_feature_intent(self):
        """Should detect add_feature intent"""
        task = "Add dark mode toggle to settings"
        result = _detect_task_intent(task)
        assert result == "add_feature"
    
    @pytest.mark.unit
    def test_detect_add_tests_intent(self):
        """Should detect add_tests intent"""
        task = "Add tests for tools/mcp_server.py"
        result = _detect_task_intent(task)
        assert result == "add_tests"
```

#### TestGlobalPatternsImpl
```python
class TestGlobalPatternsImpl:
    """Test pattern management implementation functions"""
    
    @pytest.mark.unit
    def test_read_patterns_file_not_exists(self, mock_home_dir):
        """Should return empty structure when file doesn't exist"""
        result = _read_global_patterns_impl("common-issues")
        
        assert result["status"] == "success"
        assert "data" in result
        assert result["data"]["patterns"] == []
    
    @pytest.mark.unit
    def test_save_patterns_success(self, mock_home_dir):
        """Should save patterns to file"""
        patterns_data = {
            "patterns": [{"id": "test-pattern"}],
            "version": "1.0"
        }
        
        result = _save_global_patterns_impl("common-issues", patterns_data)
        
        assert result["status"] == "success"
        assert "file_path" in result
        
        # Verify file was created
        pattern_file = Path(result["file_path"])
        assert pattern_file.exists()
    
    @pytest.mark.unit
    def test_merge_patterns_new_pattern(self, mock_home_dir):
        """Should add new pattern when merging"""
        # Create project pattern file
        project_pattern = {
            "patterns": [{
                "pattern_id": "new-pattern",
                "issue": "Test issue",
                "solution": "Test solution"
            }]
        }
        
        result = _merge_project_patterns_impl(
            project_pattern_file=None,  # Will use data directly
            pattern_type="common-issues",
            increment_build_count=False
        )
        
        assert result["status"] == "success"
        assert result["new_patterns"] >= 0
```

#### TestEvolutionStubs
```python
class TestEvolutionStubs:
    """Test evolution system stub functions"""
    
    @pytest.mark.unit
    def test_create_evolution_task(self):
        """Should return not implemented message"""
        result = create_evolution_task(
            task_type="test",
            description="Test task"
        )
        assert "not implemented" in result.lower() or "evolution" in result.lower()
    
    @pytest.mark.unit
    def test_get_daemon_status(self):
        """Should return status information"""
        result = get_daemon_status()
        assert isinstance(result, str)
        # Should contain JSON or status message
        assert "status" in result.lower() or "daemon" in result.lower()
```

### Step 5: Test Execution Plan
1. Run new tests: `pytest tests/test_mcp_server_unit.py -v`
2. Check coverage: `pytest --cov=tools.mcp_server --cov-report=term tests/test_mcp_server_unit.py`
3. Run all tests: `pytest tests/test_mcp_server*.py -v`
4. Generate coverage report: `pytest --cov=tools.mcp_server --cov-report=html`

## Testing Requirements

### Success Criteria
1. All new unit tests pass
2. Coverage for tested functions > 70%
3. No regression in existing tests
4. Tests follow project patterns

### Test Markers
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.tier1` - Critical functionality (for key functions)

### Edge Cases to Test
- Empty directories
- Missing files
- Invalid JSON
- Permission errors
- Non-existent paths
- Various project types

## Preventive Measures

### Known Risks and Mitigations

**Risk 1: FastMCP Import Errors**
- **Mitigation**: Mock FastMCP before any imports
- **Pattern**: Use MockFastMCP class from existing tests

**Risk 2: Global State Pollution**
- **Mitigation**: Clear active_builds and active_tasks in fixtures
- **Pattern**: Use clear_global_state fixture

**Risk 3: File System Dependencies**
- **Mitigation**: Use pytest's tmp_path fixture
- **Pattern**: Mock home directory with monkeypatch

**Risk 4: Subprocess Calls**
- **Mitigation**: Mock subprocess.run where needed
- **Pattern**: Use unittest.mock.patch

## Implementation Order

1. **Setup (10 min)**
   - Create test file structure
   - Add FastMCP mocking
   - Create fixtures

2. **Tier 1 Tests (30 min)**
   - TestDetectExistingCodebase (15 min)
   - TestDetectTaskIntent (5 min)
   - TestGlobalPatternsImpl (10 min)

3. **Tier 2 Tests (15 min)**
   - TestEvolutionStubs (10 min)
   - TestBootstrapPatterns (5 min)

4. **Validation (15 min)**
   - Run all tests
   - Check coverage
   - Fix any failures
   - Document gaps

## Files to Create/Modify

1. **CREATE**: `tests/test_mcp_server_unit.py` (new comprehensive unit tests)

## Expected Outcomes

- New test file with 40+ unit tests
- Coverage increase from 0% to 70%+ for tested functions
- All tests passing
- PR ready for review

# Test Coverage Enhancement Architecture

## Overview

This architecture defines a comprehensive test suite to increase coverage of `tools/evolution/modes/self_improvement.py` from **9.8% to >80%**, focusing on critical untested paths.

## Current Coverage Analysis

### Existing Tests (test_self_improvement_safety.py)
✅ Protected file filtering (100% covered)
✅ Basic TODO prioritization (partial coverage)
✅ Task execution with MCP delegation (basic paths)
✅ Generate improvement tasks fallback (covered)

### Missing Coverage (166 lines uncovered)

#### 1. _find_todos() - Lines 195-297 (partial coverage)
**Missing**:
- Search directory configuration loading
- Subprocess timeout and error handling
- TODO parsing edge cases (malformed lines)
- Duplicate removal logic
- Meta-comment filtering edge cases

#### 2. _load_search_config() - Lines 171-193 (0% coverage)
**Missing**:
- Reading JSON config from ~/.context-foundry/evolution/todo_search.json
- Error handling for malformed config
- Default fallback behavior

#### 3. _prioritize_todo() - Lines 371-477 (partial coverage)
**Missing**:
- All keyword categories (test, docs, refactor, performance, security)
- File path context priority adjustments
- Priority capping logic (min 1, max 10)
- Edge case combinations

#### 4. generate_tasks() - Lines 54-81 (partial coverage)
**Missing**:
- Priority sorting logic
- Task limit enforcement (5 max)
- Different action types (implement_github_issue)

#### 5. execute_task() - Lines 83-165 (partial coverage)
**Missing**:
- MCP status check and error handling
- implement_github_issue action path
- Branch name generation
- Prompt building for different actions
- Sandbox creation integration (new delegation method)

#### 6. _delegate_to_context_foundry() - Lines 495-585 (NEW - 0% coverage)
**CRITICAL NEW METHOD - NOT IN OLD TESTS**:
- MCP availability check
- Sandbox creation and safety enforcement
- MCP _autonomous_build_and_deploy_impl() call
- Result parsing and task ID extraction
- Error handling for MCP failures
- Sandbox path tracking

## New Test File Architecture

### File: tests/evolution/test_self_improvement_comprehensive.py

**Purpose**: Complete coverage of all untested paths in SelfImprovementMode

### Test Class Structure

```python
# Test Class 1: TodoDiscoveryComprehensive
- test_load_search_config_with_valid_json()
- test_load_search_config_with_malformed_json()
- test_load_search_config_file_not_exists()
- test_load_search_config_io_error()
- test_find_todos_subprocess_timeout()
- test_find_todos_file_not_found_error()
- test_find_todos_malformed_grep_output()
- test_find_todos_duplicate_removal()
- test_find_todos_meta_comment_filtering()

# Test Class 2: TodoPrioritizationComprehensive  
- test_prioritize_todo_test_keywords()
- test_prioritize_todo_docs_keywords()
- test_prioritize_todo_refactor_keywords()
- test_prioritize_todo_performance_keywords()
- test_prioritize_todo_file_path_core_boost()
- test_prioritize_todo_file_path_tests_penalty()
- test_prioritize_todo_priority_capping_max()
- test_prioritize_todo_priority_capping_min()
- test_prioritize_todo_keyword_combinations()

# Test Class 3: TaskGenerationComprehensive
- test_generate_tasks_priority_sorting()
- test_generate_tasks_limit_enforcement()
- test_generate_tasks_multiple_todos()
- test_generate_tasks_with_duplicates()
- test_generate_tasks_empty_todos_fallback()

# Test Class 4: TaskExecutionComprehensive
- test_execute_task_implement_github_issue_action()
- test_execute_task_mcp_unavailable()
- test_execute_task_mcp_status_check()
- test_execute_task_branch_name_pattern()
- test_execute_task_prompt_building_todo()
- test_execute_task_prompt_building_github_issue()
- test_execute_task_exception_handling()

# Test Class 5: MCPDelegationComprehensive (NEW - CRITICAL)
- test_delegate_mcp_available_success()
- test_delegate_mcp_unavailable_error()
- test_delegate_sandbox_creation()
- test_delegate_sandbox_safety_enforcement()
- test_delegate_autonomous_build_call()
- test_delegate_result_parsing()
- test_delegate_task_id_extraction()
- test_delegate_exception_handling()
- test_delegate_sandbox_path_tracking()

# Test Class 6: WrapperMethodsCoverage
- test_calculate_todo_priority()
- test_categorize_todo()
- test_mcp_status()

# Test Class 7: IntegrationTests
- test_end_to_end_todo_to_task_generation()
- test_end_to_end_task_execution_with_mcp()
- test_end_to_end_sandbox_lifecycle()
```

## Implementation Details

### Mocking Strategy

**Mock SandboxManager** (tools/evolution/sandboxes.py):
```python
@patch('tools.evolution.modes.self_improvement.SandboxManager')
def test_delegate_sandbox_creation(mock_sandbox_manager):
    mock_manager = mock_sandbox_manager.return_value
    mock_manager.create_sandbox.return_value = Path('/tmp/sandbox-abc123')
    # Test sandbox creation flow
```

**Mock enforce_sandbox_mode** (tools/evolution/safety.py):
```python
@patch('tools.evolution.modes.self_improvement.enforce_sandbox_mode')
@patch('tools.evolution.modes.self_improvement.set_sandbox_mode')
def test_delegate_sandbox_safety_enforcement(mock_set, mock_enforce):
    # Test safety checks are called
```

**Mock _autonomous_build_and_deploy_impl** (tools/mcp_server.py):
```python
@patch('tools.evolution.modes.self_improvement._autonomous_build_and_deploy_impl')
def test_delegate_autonomous_build_call(mock_build):
    mock_build.return_value = json.dumps({
        "task_id": "mcp-task-123",
        "status": "running",
        "message": "Build started"
    })
    # Test MCP call and result parsing
```

**Mock get_mcp_capabilities**:
```python
@patch('tools.evolution.modes.self_improvement.get_mcp_capabilities')
def test_execute_task_mcp_unavailable(mock_mcp):
    mock_mcp.return_value = {"available": False, "reason": "Missing dependencies"}
    # Test MCP unavailability error path
```

### Config File Mocking

For `_load_search_config()` tests:
```python
@patch('pathlib.Path.exists', return_value=True)
@patch('builtins.open', mock_open(read_data='{"search_dirs": ["custom/dir"]}'))
def test_load_search_config_with_valid_json(mock_file, mock_exists):
    # Test successful config loading
```

### Subprocess Mocking

For grep timeout and error handling:
```python
@patch('subprocess.run', side_effect=subprocess.TimeoutExpired('grep', 10))
def test_find_todos_subprocess_timeout(mock_run):
    # Test timeout handling
```

## Testing Patterns from Existing Tests

### Pattern 1: Fixture-based Setup
```python
@pytest.fixture
def mode():
    return SelfImprovementMode()
```

### Pattern 2: Mock with Return Values
```python
with patch('subprocess.run') as mock_run:
    mock_run.return_value = Mock(returncode=0, stdout="...")
```

### Pattern 3: Assertion with Detailed Messages
```python
assert len(todos) == 1, "Non-protected TODO should be included"
```

## File Structure

```
tests/evolution/
├── test_self_improvement_safety.py (existing - keep unchanged)
└── test_self_improvement_comprehensive.py (new - add complete coverage)
```

## Success Metrics

1. **Coverage Target**: >80% (from 9.8%)
2. **Line Coverage**: 166 missing lines → <30 missing lines
3. **Critical Paths**: 100% coverage of:
   - MCP delegation (_delegate_to_context_foundry)
   - Sandbox creation and safety
   - Config loading edge cases
4. **Test Count**: +35 new tests
5. **No Regressions**: All existing tests pass

## Dependencies

**Imports Required**:
```python
import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock
from pathlib import Path
import uuid
from datetime import datetime
import json
import subprocess

from tools.evolution.modes.self_improvement import SelfImprovementMode
from tools.evolution.modes.base_mode import TaskResult
from tools.evolution.task_queue import Task, TaskType
```

**Mock Targets**:
- `subprocess.run` (for grep)
- `pathlib.Path.exists` (for config file)
- `builtins.open` (for config reading)
- `tools.evolution.modes.self_improvement.SandboxManager`
- `tools.evolution.modes.self_improvement.enforce_sandbox_mode`
- `tools.evolution.modes.self_improvement.set_sandbox_mode`
- `tools.evolution.modes.self_improvement._autonomous_build_and_deploy_impl`
- `tools.evolution.modes.self_improvement.get_mcp_capabilities`

## Risk Mitigation

### Risk 1: Breaking Existing Tests
**Mitigation**: Run existing tests first, ensure no changes to test_self_improvement_safety.py

### Risk 2: Real Sandbox Creation
**Mitigation**: Always mock SandboxManager.create_sandbox()

### Risk 3: Real MCP Calls
**Mitigation**: Always mock _autonomous_build_and_deploy_impl()

### Risk 4: Real File System Access
**Mitigation**: Mock Path.exists() and open() for config loading

## Implementation Steps

1. **Create test file** with proper structure
2. **Implement TodoDiscoveryComprehensive** (9 tests)
3. **Implement TodoPrioritizationComprehensive** (9 tests)
4. **Implement TaskGenerationComprehensive** (5 tests)
5. **Implement TaskExecutionComprehensive** (7 tests)
6. **Implement MCPDelegationComprehensive** (9 tests) - CRITICAL NEW
7. **Implement WrapperMethodsCoverage** (3 tests)
8. **Implement IntegrationTests** (3 tests)
9. **Run pytest with coverage** to verify >80%
10. **Fix any failures** and iterate

## Expected Coverage Improvement

**Before**: 9.8% (166 missing lines)
**After**: >80% (<30 missing lines)
**Gain**: +70.2% coverage

**Critical Paths Covered**:
- ✅ MCP delegation and sandbox safety (100%)
- ✅ TODO discovery and parsing (100%)
- ✅ Prioritization logic (100%)
- ✅ Task generation (100%)
- ✅ Config loading (100%)
- ✅ Error handling (100%)

# Architecture: Unit Tests for tools/mcp_server.py Helper Functions

## System Overview

Create comprehensive unit tests for 6 untested helper functions in `tools/mcp_server.py`. These functions are critical for MCP server operation but lack direct test coverage.

## File Structure

```
tests/
├── test_mcp_server_helpers.py     (NEW - 400-500 lines)
│   ├── FastMCP mock setup
│   ├── Test fixtures
│   ├── _read_phase_info tests (6 tests)
│   ├── _truncate_output tests (5 tests)
│   ├── _get_context_foundry_parent_dir tests (2 tests)
│   ├── _write_delegation_metadata tests (3 tests)
│   ├── _write_full_output_to_file tests (4 tests)
│   └── _create_output_summary tests (4 tests)
```

## Module Specifications

### test_mcp_server_helpers.py

**Purpose**: Unit tests for private helper functions in mcp_server.py

**Key Components**:

1. **Mock Setup** (lines 1-60)
   - MockFastMCP class (tool and resource decorators)
   - sys.modules mocking for fastmcp imports
   - Import mcp_server after mocking

2. **Fixtures** (lines 61-100)
   - `temp_dir(tmp_path)` - Temporary directory for file operations
   - `mock_phase_file(temp_dir)` - Creates test phase JSON file
   - `sample_output()` - Returns sample output strings for truncation tests

3. **_read_phase_info Tests** (lines 101-250)
   ```python
   def test_read_phase_info_file_exists_fresh()
   def test_read_phase_info_file_not_exists()
   def test_read_phase_info_invalid_json()
   def test_read_phase_info_stale_file()
   def test_read_phase_info_permission_error()
   def test_read_phase_info_no_task_start_time()
   ```

4. **_truncate_output Tests** (lines 251-350)
   ```python
   def test_truncate_output_small_output()
   def test_truncate_output_large_output()
   def test_truncate_output_empty_string()
   def test_truncate_output_at_boundary()
   def test_truncate_output_custom_max_tokens()
   ```

5. **_get_context_foundry_parent_dir Tests** (lines 351-400)
   ```python
   def test_get_context_foundry_parent_dir_returns_parent()
   def test_get_context_foundry_parent_dir_resolution()
   ```

6. **_write_delegation_metadata Tests** (lines 401-480)
   ```python
   def test_write_delegation_metadata_success()
   def test_write_delegation_metadata_creates_directory()
   def test_write_delegation_metadata_handles_errors()
   ```

7. **_write_full_output_to_file Tests** (lines 481-580)
   ```python
   def test_write_full_output_to_file_success()
   def test_write_full_output_to_file_creates_directory()
   def test_write_full_output_to_file_encoding()
   def test_write_full_output_to_file_handles_errors()
   ```

8. **_create_output_summary Tests** (lines 581-680)
   ```python
   def test_create_output_summary_under_max_lines()
   def test_create_output_summary_over_max_lines()
   def test_create_output_summary_empty_output()
   def test_create_output_summary_custom_max_lines()
   ```

## Implementation Steps

### Step 1: Mock Setup and Imports
- Create MockFastMCP class with tool() and resource() decorators
- Mock sys.modules entries for fastmcp
- Import functions from tools.mcp_server after mocking

### Step 2: Test Fixtures
- Create pytest fixtures for temporary directories
- Create fixture for mock phase files
- Create fixture for sample output strings

### Step 3: Implement _read_phase_info Tests
- Test successful read with fresh file
- Test file not exists (returns empty dict)
- Test invalid JSON (returns empty dict)
- Test stale file detection (modified before task start)
- Test permission errors (returns empty dict)
- Test without task_start_time parameter

### Step 4: Implement _truncate_output Tests
- Test small output (no truncation)
- Test large output (truncation occurs)
- Test empty string handling
- Test boundary case (exactly at limit)
- Test custom max_tokens parameter

### Step 5: Implement _get_context_foundry_parent_dir Tests
- Test returns correct parent directory
- Test path resolution works correctly

### Step 6: Implement _write_delegation_metadata Tests
- Test successful metadata write
- Test directory creation
- Test error handling

### Step 7: Implement _write_full_output_to_file Tests
- Test successful file write
- Test directory creation
- Test UTF-8 encoding
- Test error handling

### Step 8: Implement _create_output_summary Tests
- Test output under max_lines (no truncation)
- Test output over max_lines (truncation)
- Test empty output
- Test custom max_lines parameter

## Testing Strategy

### Unit Test Principles
1. **Isolation**: Each function tested independently
2. **Mocking**: Use unittest.mock for file I/O, datetime
3. **Coverage**: Test happy path + error paths + edge cases
4. **Speed**: All tests should complete in <2 seconds

### Test Patterns

**File I/O Testing**:
```python
def test_function_with_file_io(tmp_path):
    test_file = tmp_path / "test.json"
    # Test logic here
```

**Error Handling Testing**:
```python
@patch('builtins.open', side_effect=PermissionError)
def test_function_handles_permission_error(mock_open):
    result = function_under_test()
    assert result == expected_error_result
```

**Staleness Testing**:
```python
@patch('tools.mcp_server.datetime')
def test_stale_file_detection(mock_datetime, tmp_path):
    # Set up stale file
    # Verify it's detected as stale
```

### Success Criteria

**Code Coverage**:
- ✅ >80% coverage for helper functions
- ✅ All branches tested (if/else, try/except)

**Test Quality**:
- ✅ All tests pass with pytest
- ✅ No test interdependencies
- ✅ Fast execution (<2 seconds total)
- ✅ Clear test names and assertions

**Code Quality**:
- ✅ Follow existing test file patterns
- ✅ Proper docstrings for test functions
- ✅ Type hints where appropriate
- ✅ Clear arrange-act-assert structure

## Edge Cases to Test

1. **_read_phase_info**:
   - Empty JSON file
   - Malformed JSON
   - File deleted mid-operation
   - Unicode characters in phase names

2. **_truncate_output**:
   - Zero-length output
   - Exactly at token boundary
   - Multi-byte Unicode characters
   - Very large output (100k+ lines)

3. **_write_delegation_metadata**:
   - Read-only filesystem
   - Disk full scenarios
   - Invalid metadata structure

4. **_write_full_output_to_file**:
   - Binary data in output
   - Very large files (>100MB)
   - Concurrent writes

## Dependencies

- pytest >= 7.0
- unittest.mock (standard library)
- pathlib (standard library)
- json (standard library)
- datetime (standard library)

## Testing Commands

```bash
# Run new tests only
pytest tests/test_mcp_server_helpers.py -v

# Run with coverage
pytest tests/test_mcp_server_helpers.py --cov=tools.mcp_server --cov-report=term-missing

# Run all mcp_server tests
pytest tests/test_mcp_server*.py -v
```

## Preventive Measures

**Known Risk**: FastMCP import failure
- **Prevention**: Mock FastMCP before any imports
- **Pattern**: Use established MockFastMCP class from existing tests

**Known Risk**: File I/O test flakiness
- **Prevention**: Use pytest's tmp_path fixture
- **Pattern**: Never write to actual directories, always use temp

**Known Risk**: Datetime mocking complexity
- **Prevention**: Use patch decorator for datetime
- **Pattern**: Mock at function call site, not module level

## Success Validation

After implementation:
1. Run `pytest tests/test_mcp_server_helpers.py -v` - all pass
2. Run coverage: `pytest tests/test_mcp_server_helpers.py --cov=tools.mcp_server --cov-branch`
3. Verify >80% coverage for helper functions
4. Ensure no test takes >1 second individually
5. Verify all edge cases covered

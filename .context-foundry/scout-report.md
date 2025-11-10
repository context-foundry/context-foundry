# Scout Report: Add Tests for tools/mcp_server.py

## Executive Summary

The task is to add comprehensive unit tests for `tools/mcp_server.py`, a critical MCP server component with 3,752 lines of code containing 35+ functions. Current test coverage shows 0% actual code coverage because existing tests heavily mock the implementation. The file is well-structured but lacks true unit tests that verify actual function behavior.

## Key Requirements

### Primary Goal
Add unit tests for `tools/mcp_server.py` to:
1. Increase actual code coverage (currently 0%)
2. Test individual function behavior with real implementations
3. Cover error handling and edge cases
4. Ensure reliability for this critical integration component

### Critical Functions Needing Tests

**Helper Functions (High Priority):**
- `_detect_existing_codebase()` - Detects project type and structure
- `_detect_task_intent()` - Determines task intent from description
- `_read_global_patterns_impl()` - Reads global pattern files
- `_save_global_patterns_impl()` - Saves global patterns
- `_merge_project_patterns_impl()` - Merges project patterns

**Public Tool Functions:**
- Pattern management wrappers (need integration with real implementations)
- Evolution system stubs (need basic functionality tests)

**Already Tested (But With Mocks):**
- `_read_phase_info()` - Helper function tests exist
- `_truncate_output()` - Helper function tests exist
- `_write_delegation_metadata()` - Helper function tests exist

## Technology Stack Decision

**Testing Framework:** pytest (already in use)
**Mocking Strategy:** Selective mocking (mock external I/O, test real logic)
**Coverage Tool:** pytest-cov

**Justification:**
- Project already uses pytest with established patterns
- Need to balance real coverage with practical test execution
- Mock only external dependencies (filesystem, subprocess, network)
- Test actual business logic and data transformations

## Architecture Recommendations

### Test Structure
1. Create focused test file: `tests/test_mcp_server_unit.py`
2. Test real function implementations with minimal mocking
3. Use fixtures for file system operations (tmp_path)
4. Mock only true external dependencies (subprocess, network calls)

### Testing Strategy

**Tier 1 (Critical - Must Test):**
- `_detect_existing_codebase()` - Critical for build system
- `_detect_task_intent()` - Critical for task routing
- `_read_global_patterns_impl()` - Pattern system core
- `_save_global_patterns_impl()` - Pattern persistence
- `_merge_project_patterns_impl()` - Pattern merging logic

**Tier 2 (Important):**
- Evolution system tool stubs
- Bootstrap functions
- Error handling paths

**Tier 3 (Nice to Have):**
- Edge cases in already-tested functions
- Performance testing
- Integration scenarios

## Main Challenges

### Technical Challenges
1. **FastMCP Import Dependencies**: Must mock FastMCP before import
2. **Global State**: `active_builds` and `active_tasks` dictionaries need cleanup
3. **File System Operations**: Many functions read/write files
4. **Subprocess Calls**: Delegation functions call external processes

### Mitigation Strategies
1. Use existing MockFastMCP pattern from test_mcp_server_helpers.py
2. Create fixtures for temporary directories
3. Mock subprocess.run for delegation tests
4. Use pytest's tmp_path fixture for file operations
5. Clear global state in setup/teardown

## Testing Approach

### Phase 1: Setup Test Infrastructure
- Create test file with proper FastMCP mocking
- Set up fixtures for file operations
- Import real functions (not mocks)

### Phase 2: Test Core Helper Functions
- Test `_detect_existing_codebase()` with various project types
- Test `_detect_task_intent()` with different task descriptions
- Test pattern management functions with real file I/O

### Phase 3: Test Public Wrappers
- Test evolution system stubs return appropriate responses
- Verify error handling

### Phase 4: Coverage Verification
- Run pytest with coverage reporting
- Verify coverage increase
- Document remaining gaps

## GitHub Deployment Readiness

Checking deployment environment...

- [✅] GitHub CLI (gh) installed: PASS (already in sandbox)
- [✅] GitHub authentication: PASS (already authenticated)
- [✅] Git user configured: PASS (configured)

**Deployment Status:** ✅ Ready for GitHub deployment (PR creation)

## Timeline Estimate

- Test infrastructure setup: 15 minutes
- Core function tests: 30 minutes
- Public wrapper tests: 15 minutes
- Coverage verification and fixes: 15 minutes
- **Total:** ~75 minutes

## Success Criteria

1. ✅ Test coverage for critical helper functions > 70%
2. ✅ All new tests pass
3. ✅ Existing tests still pass (no regression)
4. ✅ Tests follow project patterns (MockFastMCP, fixtures, markers)
5. ✅ PR created linking to issue #151

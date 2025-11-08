# Scout Report: Add Missing Tests for Critical Paths

## Executive Summary

Context Foundry is missing comprehensive test coverage for 8 critical modules totaling ~3000 lines of code. These modules handle core functionality including incremental builds, caching, path utilities, and back pressure validation. Adding thorough unit and integration tests will significantly improve code reliability and maintainability.

**Critical Gaps Identified:**
- Incremental build system (3 modules, 1255 lines) - NO TESTS
- Cache system (2 modules) - NO TESTS (ironic for cache modules!)
- Tool helpers (2 modules, 813 lines) - PARTIAL COVERAGE
- Back pressure validation (369 lines) - NO TESTS

## Key Requirements

1. **Create comprehensive test suite** covering:
   - Unit tests for all public functions
   - Integration tests for module interactions
   - Edge case and error handling validation
   - Mock external dependencies appropriately

2. **Follow existing patterns**:
   - Use pytest framework (already configured)
   - Apply pytest markers: @pytest.mark.unit, @pytest.mark.integration, @pytest.mark.tier1
   - Use tempfile.TemporaryDirectory() for file system tests
   - Match naming: `test_{module_name}.py`

3. **Test files to create**:
   - `tests/test_incremental_builder.py`
   - `tests/test_change_detector.py`
   - `tests/test_global_scout_cache.py`
   - `tests/test_integration_pre_check.py`
   - `tests/test_truncation.py`
   - `tests/test_path_utils.py`
   - `tests/test_scout_cache_unit.py`
   - `tests/test_test_cache_unit.py`

4. **Maintain 100% backward compatibility**:
   - All existing 45+ test files must continue to pass
   - No changes to production code (tests only)
   - No breaking changes to public APIs

## Technology Stack

- **Framework**: pytest 8.4.2
- **Python**: 3.13+
- **Test utilities**: 
  - tempfile for filesystem isolation
  - unittest.mock for mocking
  - pytest markers for organization
- **Coverage tool**: pytest-cov (configured but not required)

## Critical Architecture Recommendations

### 1. Test Organization Pattern

Match existing test structure:
```python
"""
Unit tests for {module_name}

Tests:
- {functionality_1}
- {functionality_2}
- {edge_cases}
"""

import pytest
import tempfile
from pathlib import Path

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.{module_path} import {functions}

class Test{ModuleName}:
    """Test {module} functionality."""
    
    @pytest.mark.unit
    @pytest.mark.tier1
    def test_basic_functionality(self):
        """Test basic use case."""
        # Arrange, Act, Assert pattern
```

### 2. Focus on Critical Paths

**Highest Priority (Tier 1 - MUST PASS):**
1. `scout_cache.py`: Cache hit/miss logic, TTL validation
2. `path_utils.py`: Absolute/relative conversion (token savings critical)
3. `incremental_builder.py`: Build plan generation, dependency graphs
4. `change_detector.py`: Change detection accuracy

**Medium Priority (Tier 2):**
5. `test_cache.py`: Test result caching
6. `truncation.py`: Output truncation with recovery
7. `integration_pre_check.py`: Pre-flight validation

**Lower Priority (Tier 3):**
8. `global_scout_cache.py`: Global caching (advanced feature)

### 3. Mocking Strategy

- **File system operations**: Use `tempfile.TemporaryDirectory()`
- **External APIs**: Use `unittest.mock.patch`
- **Time-dependent tests**: Mock `datetime.now()`
- **Environment variables**: Use `monkeypatch` fixture

### 4. Coverage Goals

- **Minimum**: 70% line coverage for each module
- **Target**: 85% line coverage for tier 1 modules
- **Focus**: Critical paths over 100% coverage

## Main Challenges and Mitigations

### Challenge 1: Large, Complex Modules
- **Issue**: Some modules are 400+ lines with many functions
- **Mitigation**: Break tests into multiple test classes by functionality area
- **Example**: `TestIncrementalBuilderDependencyGraph`, `TestIncrementalBuilderBuildPlan`

### Challenge 2: File System Dependencies
- **Issue**: Many modules interact with file system
- **Mitigation**: Use `tempfile.TemporaryDirectory()` for isolation (proven pattern in existing tests)
- **Pattern**: Create temp dir → populate test files → run function → assert results → cleanup

### Challenge 3: Cache TTL Testing
- **Issue**: Time-dependent cache expiration logic
- **Mitigation**: Mock `datetime.now()` to simulate time passage
- **Example**: From `test_cache_system.py` - create file, mock time +25 hours, assert expired

### Challenge 4: Integration Points
- **Issue**: Modules depend on each other (e.g., incremental_builder imports change_detector)
- **Mitigation**: Test in isolation first (mock dependencies), then add integration tests
- **Markers**: Use `@pytest.mark.unit` and `@pytest.mark.integration` to separate

### Challenge 5: No Breaking Changes Allowed
- **Issue**: Cannot modify production code to make it more testable
- **Mitigation**: Test public interfaces as-is, use mocking for hard-to-test areas
- **Constraint**: Tests must work with existing code unchanged

## Testing Approach

### Phase 1: Unit Tests (Highest Priority)
Create isolated unit tests for each module's public functions:
- Test normal operation (happy path)
- Test error conditions (exceptions, invalid inputs)
- Test edge cases (empty inputs, None values, boundary conditions)
- Test return types and data structures

### Phase 2: Integration Tests
Test module interactions:
- `incremental_builder` + `change_detector` integration
- Cache modules with file system
- `path_utils` with real project structures

### Phase 3: Validation
- Run full pytest suite: `pytest tests/`
- Verify all new tests pass
- Verify all existing tests still pass
- Check for test isolation (no interference between tests)

## Success Criteria

✅ **Code Quality**:
- 8 new test files created
- Minimum 70% coverage for each tested module
- All tests use appropriate pytest markers

✅ **Test Quality**:
- Tests are deterministic (no flaky tests)
- Tests are fast (< 1 second each for unit tests)
- Tests are isolated (can run in any order)
- Clear test names describe what is being tested

✅ **Backward Compatibility**:
- All existing tests pass: `pytest tests/`
- No changes to production code
- No new dependencies added

✅ **Documentation**:
- Each test file has module docstring describing what's tested
- Complex tests have inline comments explaining logic
- Test functions have descriptive docstrings

## Timeline Estimate

- **Module analysis & test design**: 15 minutes
- **Test implementation (8 modules)**: 45-60 minutes
- **Validation & debugging**: 15-20 minutes
- **Total**: 75-95 minutes

## Key Learnings Applied

- Follow existing test patterns (consistency is key)
- Use pytest markers for organization and selective running
- Isolate file system tests with tempfile
- Mock time-dependent operations
- Test public interfaces, not implementation details
- Prioritize critical paths over exhaustive coverage

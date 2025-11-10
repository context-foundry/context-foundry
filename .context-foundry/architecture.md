# Test Architecture: test_cache_manager_unit.py

## Overview

Design comprehensive unit tests for `tools/cache/cache_manager.py` following established patterns from existing test files (`test_scout_cache_unit.py`, `test_test_cache_unit.py`).

**File**: `tests/test_cache_manager_unit.py`
**Lines**: ~550-650 (similar to existing cache test files)
**Test Count**: 40 tests (20 tier1, 15 tier2, 5 integration)

## File Structure

```
tests/test_cache_manager_unit.py
├── Module Docstring (Purpose, Test List)
├── Imports (pytest, tempfile, pathlib, sys.path setup)
├── Helper Functions
│   ├── _create_scout_cache_files(tmpdir, count, size_kb)
│   ├── _create_test_cache_files(tmpdir, count, size_kb)
│   └── _create_expired_cache_files(tmpdir, count)
├── Test Classes
│   ├── TestCacheManagerInit (3 tests)
│   ├── TestGetStats (6 tests)
│   ├── TestCleanExpired (5 tests)
│   ├── TestClearAll (3 tests)
│   ├── TestClearByType (5 tests)
│   ├── TestEnforceSizeLimit (8 tests)
│   ├── TestPrintStats (2 tests)
│   └── TestCacheManagerIntegration (5 tests)
└── Total: 40 tests
```

## Module Dependencies

### Imports Required
```python
import pytest
import tempfile
import time
import os
from pathlib import Path
from io import StringIO
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cache.cache_manager import CacheManager
from tools.cache.scout_cache import save_scout_report_to_cache
from tools.cache.test_cache import save_test_results_to_cache
from tools.cache import DEFAULT_CACHE_TTL_HOURS, DEFAULT_MAX_CACHE_SIZE_MB
```

## Helper Functions

### 1. _create_scout_cache_files
**Purpose**: Create scout cache files for testing
```python
def _create_scout_cache_files(tmpdir: str, count: int = 3, size_kb: float = 1.0) -> None:
    """Create scout cache files with known size."""
    content = "# Scout Report\n" + ("x" * int(size_kb * 1024))
    for i in range(count):
        save_scout_report_to_cache(
            f"Task {i}",
            "new_project",
            tmpdir,
            content
        )
```

### 2. _create_test_cache_files
**Purpose**: Create test cache files for testing
```python
def _create_test_cache_files(tmpdir: str, count: int = 3) -> None:
    """Create test cache files."""
    for i in range(count):
        # Create a dummy source file
        (Path(tmpdir) / f"test{i}.py").write_text(f"# Test {i}")
        # Save test results
        save_test_results_to_cache(
            tmpdir,
            {"success": True, "passed": i+1, "total": i+1}
        )
```

### 3. _create_expired_cache_files
**Purpose**: Create expired cache files for TTL testing
```python
def _create_expired_cache_files(tmpdir: str, count: int = 2) -> None:
    """Create expired cache files by backdating timestamps."""
    cache_dir = Path(tmpdir) / ".context-foundry" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Create old files
    old_time = time.time() - (48 * 3600)  # 48 hours ago
    for i in range(count):
        file_path = cache_dir / f"scout-old-{i}.md"
        file_path.write_text(f"# Old Report {i}")
        os.utime(file_path, (old_time, old_time))
```

## Test Class Specifications

### TestCacheManagerInit (3 tests)

**Purpose**: Test CacheManager initialization

#### Test 1: test_init_creates_cache_manager
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Verify CacheManager initializes correctly
- **Setup**: Create temp directory
- **Action**: `manager = CacheManager(tmpdir)`
- **Assert**: 
  - `manager.working_directory == tmpdir`
  - `manager.cache_dir.exists()`
  - `".context-foundry/cache" in str(manager.cache_dir)`

#### Test 2: test_init_creates_cache_directory
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Verify cache directory is created
- **Setup**: Create temp directory (no cache dir exists)
- **Action**: `CacheManager(tmpdir)`
- **Assert**: Cache directory exists at expected path

#### Test 3: test_init_with_existing_cache_directory
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Verify initialization with existing cache works
- **Setup**: Create temp directory, create cache dir manually
- **Action**: `CacheManager(tmpdir)`
- **Assert**: No errors, cache_dir correct

### TestGetStats (6 tests)

**Purpose**: Test cache statistics gathering

#### Test 1: test_get_stats_empty_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Stats work with no cache files
- **Setup**: CacheManager with empty cache
- **Action**: `stats = manager.get_stats()`
- **Assert**:
  - `stats["total_files"] == 0`
  - `stats["total_size_mb"] == 0`
  - `stats["scout_cache"]["total_entries"] == 0`
  - `stats["test_cache"]["has_cached_results"] == False`

#### Test 2: test_get_stats_with_scout_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Stats count scout cache files
- **Setup**: Create 3 scout cache files
- **Action**: `stats = manager.get_stats()`
- **Assert**:
  - `stats["total_files"] > 0`
  - `stats["scout_cache"]["total_entries"] == 3`
  - `stats["total_size_mb"] > 0`

#### Test 3: test_get_stats_with_test_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Stats detect test cache
- **Setup**: Create test cache files
- **Action**: `stats = manager.get_stats()`
- **Assert**:
  - `stats["test_cache"]["has_cached_results"] == True`

#### Test 4: test_get_stats_with_mixed_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Stats handle both cache types
- **Setup**: Create scout + test cache files
- **Action**: `stats = manager.get_stats()`
- **Assert**: Both cache types counted correctly

#### Test 5: test_get_stats_calculates_total_size
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Total size calculation is accurate
- **Setup**: Create files with known sizes (10KB each × 3 = 30KB)
- **Action**: `stats = manager.get_stats()`
- **Assert**: `stats["total_size_mb"] >= 0.029` (allowing for overhead)

#### Test 6: test_get_stats_returns_correct_structure
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Stats dict has expected keys
- **Setup**: Any cache state
- **Action**: `stats = manager.get_stats()`
- **Assert**: All expected keys present (cache_dir, scout_cache, test_cache, total_size_mb, total_files, created_at)

### TestCleanExpired (5 tests)

**Purpose**: Test TTL-based cache cleanup

#### Test 1: test_clean_expired_removes_old_files
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Expired files are deleted
- **Setup**: Create expired cache files (48 hours old)
- **Action**: `result = manager.clean_expired(ttl_hours=24)`
- **Assert**:
  - `result["total"] > 0`
  - Old files no longer exist

#### Test 2: test_clean_expired_preserves_recent_files
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Valid files are kept
- **Setup**: Create recent cache files
- **Action**: `result = manager.clean_expired(ttl_hours=24)`
- **Assert**:
  - `result["total"] == 0`
  - Recent files still exist

#### Test 3: test_clean_expired_empty_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Handles empty cache gracefully
- **Setup**: No cache files
- **Action**: `result = manager.clean_expired()`
- **Assert**: `result["total"] == 0`

#### Test 4: test_clean_expired_categorizes_deletions
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Tracks deletions by type
- **Setup**: Create expired scout and test files
- **Action**: `result = manager.clean_expired(ttl_hours=0)`
- **Assert**: 
  - `result["scout_cache"] > 0`
  - `result["test_cache"] > 0`
  - `result["total"] == scout + test`

#### Test 5: test_clean_expired_custom_ttl
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Custom TTL works
- **Setup**: Create files with specific ages
- **Action**: Test with various TTL values
- **Assert**: Correct files deleted based on TTL

### TestClearAll (3 tests)

**Purpose**: Test full cache clearing

#### Test 1: test_clear_all_removes_all_cache_files
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: All cache files deleted
- **Setup**: Create scout + test cache files
- **Action**: `result = manager.clear_all()`
- **Assert**:
  - `result["total"] > 0`
  - No cache files remain
  - `manager.get_stats()["total_files"] == 0`

#### Test 2: test_clear_all_returns_correct_counts
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Returns accurate deletion counts
- **Setup**: Create 3 scout + 2 test files
- **Action**: `result = manager.clear_all()`
- **Assert**:
  - `result["scout_cache"] == 3`
  - `result["test_cache"] >= 1`
  - `result["total"] >= 4`

#### Test 3: test_clear_all_empty_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Handles empty cache
- **Setup**: No cache files
- **Action**: `result = manager.clear_all()`
- **Assert**: `result["total"] == 0`

### TestClearByType (5 tests)

**Purpose**: Test selective cache clearing

#### Test 1: test_clear_by_type_scout
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Clears only scout cache
- **Setup**: Create scout + test files
- **Action**: `count = manager.clear_by_type('scout')`
- **Assert**:
  - Scout files deleted
  - Test files remain
  - `count > 0`

#### Test 2: test_clear_by_type_test
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Clears only test cache
- **Setup**: Create scout + test files
- **Action**: `count = manager.clear_by_type('test')`
- **Assert**:
  - Test files deleted
  - Scout files remain
  - `count >= 0`

#### Test 3: test_clear_by_type_all
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: 'all' type clears everything
- **Setup**: Create scout + test files
- **Action**: `count = manager.clear_by_type('all')`
- **Assert**:
  - All files deleted
  - `count > 0`

#### Test 4: test_clear_by_type_invalid_raises_error
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Invalid type raises ValueError
- **Setup**: Any cache state
- **Action**: `manager.clear_by_type('invalid')`
- **Assert**: `pytest.raises(ValueError)` with message containing "Unknown cache type"

#### Test 5: test_clear_by_type_empty_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Handles empty cache for any type
- **Setup**: No cache files
- **Action**: Try all valid types
- **Assert**: All return 0, no errors

### TestEnforceSizeLimit (8 tests)

**Purpose**: Test cache size limit enforcement

#### Test 1: test_enforce_size_limit_under_limit
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: No deletion when under limit
- **Setup**: Create 0.5MB cache
- **Action**: `result = manager.enforce_size_limit(max_size_mb=1)`
- **Assert**:
  - `result["deleted_files"] == 0`
  - `result["freed_mb"] == 0`
  - All files remain

#### Test 2: test_enforce_size_limit_over_limit
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Deletes files when over limit
- **Setup**: Create 2MB cache
- **Action**: `result = manager.enforce_size_limit(max_size_mb=1)`
- **Assert**:
  - `result["deleted_files"] > 0`
  - `result["freed_mb"] > 0`
  - `result["current_size_mb"] <= 1`

#### Test 3: test_enforce_size_limit_deletes_oldest_first
- **Marker**: `@pytest.mark.unit @pytest.mark.tier1`
- **Purpose**: Oldest files deleted first
- **Setup**: Create files with staggered timestamps
- **Action**: Enforce limit requiring deletion
- **Assert**: Oldest files deleted, newest remain

#### Test 4: test_enforce_size_limit_exact_limit
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Handles exact limit boundary
- **Setup**: Create cache exactly at limit
- **Action**: `manager.enforce_size_limit()`
- **Assert**: No deletions (`deleted_files == 0`)

#### Test 5: test_enforce_size_limit_empty_cache
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Handles empty cache
- **Setup**: No cache files
- **Action**: `result = manager.enforce_size_limit()`
- **Assert**:
  - `result["deleted_files"] == 0`
  - `result["current_size_mb"] == 0`

#### Test 6: test_enforce_size_limit_deletes_correct_count
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Deletes minimum necessary files
- **Setup**: Create 10 files (1MB each), limit 5MB
- **Action**: `result = manager.enforce_size_limit(max_size_mb=5)`
- **Assert**: Approximately 5 files deleted, size under limit

#### Test 7: test_enforce_size_limit_zero_limit
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Zero limit deletes all files
- **Setup**: Create cache files
- **Action**: `result = manager.enforce_size_limit(max_size_mb=0)`
- **Assert**: All files deleted

#### Test 8: test_enforce_size_limit_returns_correct_structure
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Result dict has expected keys
- **Setup**: Any cache state
- **Action**: `result = manager.enforce_size_limit()`
- **Assert**: Keys present: deleted_files, freed_mb, current_size_mb

### TestPrintStats (2 tests)

**Purpose**: Test human-readable stats output

#### Test 1: test_print_stats_runs_without_error
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Smoke test - doesn't crash
- **Setup**: Create cache files
- **Action**: Redirect stdout, call `manager.print_stats()`
- **Assert**: No exceptions raised

#### Test 2: test_print_stats_output_contains_expected_sections
- **Marker**: `@pytest.mark.unit @pytest.mark.tier2`
- **Purpose**: Output has expected content
- **Setup**: Create cache files, redirect stdout
- **Action**: `manager.print_stats()`
- **Assert**: Output contains: "Cache Statistics", "Scout Cache", "Test Cache", "Total size", "Total files"

### TestCacheManagerIntegration (5 tests)

**Purpose**: End-to-end workflow testing

#### Test 1: test_full_workflow_create_stats_clear
- **Marker**: `@pytest.mark.integration @pytest.mark.tier2`
- **Purpose**: Complete workflow test
- **Setup**: Empty cache
- **Action**:
  1. Create cache files
  2. Get stats (verify counts)
  3. Clear all
  4. Get stats (verify empty)
- **Assert**: Each step produces expected results

#### Test 2: test_workflow_with_size_limit_enforcement
- **Marker**: `@pytest.mark.integration @pytest.mark.tier2`
- **Purpose**: Size limit workflow
- **Action**:
  1. Create large cache
  2. Enforce size limit
  3. Verify size reduced
  4. Stats show correct size
- **Assert**: Cache size managed correctly

#### Test 3: test_workflow_with_ttl_cleanup
- **Marker**: `@pytest.mark.integration @pytest.mark.tier2`
- **Purpose**: TTL cleanup workflow
- **Action**:
  1. Create old + new files
  2. Clean expired
  3. Verify only new remain
  4. Stats show reduced count
- **Assert**: TTL enforcement works end-to-end

#### Test 4: test_mixed_cache_operations
- **Marker**: `@pytest.mark.integration @pytest.mark.tier2`
- **Purpose**: Mixed operations work together
- **Action**:
  1. Create scout + test files
  2. Clear scout only
  3. Get stats (test files remain)
  4. Clear test only
  5. Get stats (all gone)
- **Assert**: Selective clearing works correctly

#### Test 5: test_repeated_operations_stable
- **Marker**: `@pytest.mark.integration @pytest.mark.tier2`
- **Purpose**: Repeated operations don't cause issues
- **Action**:
  - Repeatedly create, clear, get stats (10 iterations)
- **Assert**: No errors, stats remain consistent

## Implementation Steps

### Step 1: Create Test File Skeleton
1. Create `tests/test_cache_manager_unit.py`
2. Add module docstring
3. Add imports
4. Set up sys.path

### Step 2: Implement Helper Functions
1. `_create_scout_cache_files()`
2. `_create_test_cache_files()`
3. `_create_expired_cache_files()`

### Step 3: Implement Tier 1 Tests (Critical)
1. TestCacheManagerInit (3 tests)
2. TestGetStats - core tests (3 tests)
3. TestClearAll - core tests (2 tests)
4. TestClearByType - core tests (4 tests)
5. TestEnforceSizeLimit - core tests (3 tests)
6. TestCleanExpired - core tests (2 tests)

### Step 4: Implement Tier 2 Tests (Important)
1. TestGetStats - advanced tests (3 tests)
2. TestClearAll - edge cases (1 test)
3. TestClearByType - edge cases (1 test)
4. TestEnforceSizeLimit - advanced tests (5 tests)
5. TestCleanExpired - advanced tests (3 tests)
6. TestPrintStats (2 tests)

### Step 5: Implement Integration Tests
1. TestCacheManagerIntegration (5 tests)

### Step 6: Test Execution & Validation
1. Run all tests: `pytest tests/test_cache_manager_unit.py -v`
2. Run tier1 only: `pytest tests/test_cache_manager_unit.py -m tier1 -v`
3. Verify all pass
4. Check test count (should be ~40)

## Testing Strategy

### Test Execution Order
1. **Tier 1 first**: Critical functionality must pass
2. **Tier 2 next**: Important features validated
3. **Integration last**: Full workflows tested

### Assertion Strategy
- Use descriptive assertion messages
- Test both positive and negative cases
- Verify return values AND side effects (files deleted, etc.)
- Check dict structure (keys present, types correct)

### Isolation Strategy
- Each test uses `tempfile.TemporaryDirectory()`
- No shared state between tests
- No test order dependencies
- Automatic cleanup on test completion

## Success Criteria

1. ✅ All 40 tests pass
2. ✅ Test execution < 10 seconds
3. ✅ No pytest warnings
4. ✅ 100% coverage of CacheManager public methods
5. ✅ Follows existing test patterns (markers, structure, docstrings)
6. ✅ Tests are isolated and repeatable
7. ✅ Clear, descriptive test names
8. ✅ Comprehensive docstrings

## Risk Mitigation

### Risk 1: TTL Tests Flaky
**Mitigation**: Use `os.utime()` to backdate files, test with TTL=0 for expired files

### Risk 2: File Size Calculations Vary
**Mitigation**: Test relative sizes, use `round()`, focus on behavior not exact bytes

### Risk 3: Cross-Platform Issues
**Mitigation**: Use `pathlib` exclusively, test on Unix-like system (macOS/Linux)

### Risk 4: Integration Test Complexity
**Mitigation**: Keep integration tests simple, test one workflow per test

## Preventive Measures

1. **Use helper functions**: Consistent test data creation
2. **Explicit assertions**: Clear failure messages
3. **Comprehensive docstrings**: Document what each test verifies
4. **Appropriate markers**: Enable selective test execution
5. **Isolated environments**: No test pollution

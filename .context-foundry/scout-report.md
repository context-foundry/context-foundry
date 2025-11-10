# Scout Report: Add Tests for tools/cache/cache_manager.py

## Executive Summary

**Task**: Implement comprehensive unit tests for `tools/cache/cache_manager.py` as requested in GitHub Issue #148 (approved, P1 priority).

**Scope**: Create `tests/test_cache_manager_unit.py` with ~35-45 tests covering all 7 public methods of the `CacheManager` class, following established testing patterns in the codebase.

**Approach**: Follow the existing test patterns from `test_scout_cache_unit.py` and `test_test_cache_unit.py`, using pytest with appropriate markers, isolated temporary directories, and comprehensive coverage of success/failure paths.

## Key Requirements

### Functional Requirements
1. Test all 7 public methods of `CacheManager` class
2. Cover both success and failure scenarios
3. Test edge cases (empty cache, expired entries, size limits, invalid inputs)
4. Verify integration with scout_cache and test_cache modules
5. Ensure tests are isolated and repeatable

### Testing Requirements
- Use pytest framework with standard markers (`@pytest.mark.unit`, tier1/tier2)
- Use `tempfile.TemporaryDirectory()` for test isolation
- Follow existing test organization patterns (descriptive test classes)
- Include comprehensive docstrings
- No external dependencies or network calls
- All tests must be deterministic and fast

### Quality Requirements
- 100% coverage of CacheManager public methods
- Clear, descriptive test names
- Proper assertions with meaningful error messages
- No test interdependencies
- Clean up resources automatically

## Technology Stack

### Core Technologies
- **Python 3.x**: Primary language
- **pytest**: Testing framework
- **tempfile**: Temporary directory management
- **pathlib**: Cross-platform path operations

### Project Dependencies
- `tools.cache.cache_manager`: Module under test
- `tools.cache.scout_cache`: Scout cache operations
- `tools.cache.test_cache`: Test cache operations
- `tools.cache.__init__`: Cache utilities (get_cache_dir, is_cache_valid, etc.)

## Critical Architecture Recommendations

### 1. Test Organization
Organize tests into logical classes matching the structure of existing test files:
- `TestCacheManagerInit`: Initialization tests
- `TestGetStats`: Statistics gathering tests
- `TestCleanExpired`: TTL-based cleanup tests
- `TestClearAll`: Full cache clearing tests
- `TestClearByType`: Selective cache clearing tests
- `TestEnforceSizeLimit`: Size limit enforcement tests
- `TestPrintStats`: Output formatting tests
- `TestCacheManagerIntegration`: End-to-end workflow tests

### 2. Test Isolation Pattern
```python
with tempfile.TemporaryDirectory() as tmpdir:
    manager = CacheManager(tmpdir)
    # Test logic here
    # Automatic cleanup on exit
```

### 3. Setup Helpers
Create helper functions to populate cache with test data:
- `_create_scout_cache_files()`: Add scout cache entries
- `_create_test_cache_files()`: Add test cache entries
- `_create_old_cache_files()`: Add expired cache entries

### 4. Test Data Strategy
- Use realistic but minimal test data
- Create files with known sizes for size limit testing
- Use predictable timestamps for TTL testing
- Test with various cache type combinations

## Main Challenges and Mitigations

### Challenge 1: TTL (Time-To-Live) Testing
**Issue**: Testing time-based expiration without making tests slow or flaky

**Mitigation**:
- Test TTL logic, not actual time passage
- Use small TTL values (0 hours) to force expiration
- Modify file timestamps if needed using `os.utime()`
- Focus on the `is_cache_valid()` function behavior

### Challenge 2: File System Timing
**Issue**: File modification times may have limited precision on some systems

**Mitigation**:
- Use `time.sleep(0.1)` between file operations if needed
- Test expiration logic with clear boundaries (expired vs valid)
- Use large enough time differences to avoid edge cases

### Challenge 3: Cross-Platform Compatibility
**Issue**: Path separators and file operations differ across OS

**Mitigation**:
- Use `pathlib.Path` exclusively (no string paths)
- Use `Path.glob()` and `Path.rglob()` for file discovery
- No assumptions about path separators or drive letters

### Challenge 4: Integration Dependencies
**Issue**: CacheManager depends on scout_cache and test_cache modules

**Mitigation**:
- Use real dependencies (not mocks) for integration testing
- Create actual cache files using the same APIs CacheManager uses
- Test the full integration stack to catch real issues

### Challenge 5: Size Calculations
**Issue**: File sizes may include metadata, vary by filesystem

**Mitigation**:
- Test relative sizes (bigger/smaller) not exact bytes
- Use `round()` for MB calculations like the implementation
- Test behavior (files deleted when over limit) not exact math

## Testing Approach

### Tier 1 Tests (Critical - Must Pass)
**Priority**: Highest | **Count**: ~20 tests

1. **Initialization**: CacheManager creates correct cache_dir
2. **Empty Stats**: get_stats() works with no cache files
3. **Stats with Files**: get_stats() counts all cache types correctly
4. **Clear All**: clear_all() removes both scout and test caches
5. **Clear Scout**: clear_by_type('scout') removes only scout cache
6. **Clear Test**: clear_by_type('test') removes only test cache
7. **Clear All Type**: clear_by_type('all') same as clear_all()
8. **Invalid Type**: clear_by_type('invalid') raises ValueError
9. **Size Limit Under**: enforce_size_limit() does nothing when under limit
10. **Size Limit Over**: enforce_size_limit() deletes oldest files when over

### Tier 2 Tests (Important)
**Priority**: Medium | **Count**: ~12 tests

1. **Clean Expired**: clean_expired() removes expired entries
2. **Clean Preserves Valid**: clean_expired() keeps valid entries
3. **Clean Empty**: clean_expired() handles empty cache
4. **Stats Total Size**: get_stats() calculates total_size_mb correctly
5. **Stats File Count**: get_stats() counts total_files correctly
6. **Print Stats**: print_stats() runs without errors (smoke test)
7. **Enforce Size Deletes Correct Count**: Deletes exactly enough files
8. **Enforce Size Oldest First**: Deletes oldest files first

### Integration Tests
**Priority**: Medium | **Count**: ~3 tests

1. **Full Workflow**: Create cache → get stats → clean → verify
2. **Mixed Cache Types**: Scout + test cache operations together
3. **Size Limit Enforcement**: Fill cache → exceed limit → verify cleanup

### Edge Cases
**Priority**: Low | **Count**: ~5 tests

1. **Nonexistent Directory**: CacheManager with non-existent working_dir
2. **Empty String Type**: clear_by_type('') behavior
3. **Negative TTL**: clean_expired(ttl_hours=-1) behavior
4. **Zero Size Limit**: enforce_size_limit(max_size_mb=0) behavior
5. **Very Large Cache**: Stress test with many files

## Timeline Estimate

**Total Effort**: 2-3 hours

- **Analysis & Setup**: 20 minutes (completed in Scout phase)
- **Tier 1 Tests**: 60-80 minutes (20 tests × 3-4 min each)
- **Tier 2 Tests**: 40-50 minutes (12 tests × 3-4 min each)
- **Integration Tests**: 15-20 minutes (3 tests × 5-7 min each)
- **Edge Cases**: 15-20 minutes (5 tests × 3-4 min each)
- **Test Execution & Fixes**: 20-30 minutes

**Sequential Build**: 150-200 minutes
**Parallel Build** (recommended): Not applicable (single test file)

## Deployment Readiness

### GitHub Deployment Checklist

- [✅] GitHub CLI (gh) installed and authenticated
- [✅] Git user configured
- [✅] Repository is existing: context-foundry/context-foundry
- [✅] Working on issue #148 (approved)

**Deployment Strategy**: 
1. Create feature branch: `enhancement/add-cache-manager-tests`
2. Commit tests with descriptive message
3. Push branch to origin
4. Create PR linking to issue #148
5. Request review

**Status**: ✅ Ready for GitHub deployment

## Success Criteria

### Must Have ✅
1. All tests pass with `pytest tests/test_cache_manager_unit.py -v`
2. All 7 CacheManager methods have test coverage
3. Tests follow existing patterns (markers, structure, style)
4. Tests are isolated (use temp directories)
5. No test interdependencies
6. Clear docstrings for all test classes and methods

### Should Have 📋
1. ~35-45 total tests (comprehensive coverage)
2. Mix of tier1 and tier2 markers
3. Integration tests for full workflows
4. Edge case coverage
5. Fast execution (< 10 seconds total)

### Nice to Have 🎯
1. Helper functions for test setup
2. Comprehensive assertions with descriptive messages
3. Test comments explaining non-obvious logic
4. Coverage report showing 100% for cache_manager.py

## Risk Assessment

**Overall Risk**: LOW

- ✅ Clear requirements from GitHub issue
- ✅ Existing test patterns to follow
- ✅ Well-documented code under test
- ✅ Stable dependencies (no external APIs)
- ✅ Isolated test environment
- ⚠️ Minor: TTL testing may need careful handling
- ⚠️ Minor: Cross-platform file operations

**Confidence Level**: HIGH - This is straightforward unit testing with clear patterns to follow.

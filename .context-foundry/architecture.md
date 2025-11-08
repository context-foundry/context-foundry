# Test Suite Architecture for Critical Paths

## System Architecture Overview

This test suite adds comprehensive coverage for 8 critical modules using pytest framework with proper isolation, mocking, and organization.

**Architecture Pattern**: Follow existing test patterns
- Use pytest with markers (@pytest.mark.unit, @pytest.mark.tier1)
- Isolate file system tests with tempfile.TemporaryDirectory()
- Mock time-dependent and external dependencies
- Organize tests by module with multiple test classes per file

## Complete File Structure

```
tests/
├── test_incremental_builder.py          # NEW - 200-250 lines
├── test_change_detector.py              # NEW - 150-200 lines
├── test_global_scout_cache.py           # NEW - 150-200 lines
├── test_integration_pre_check.py        # NEW - 150-200 lines
├── test_truncation.py                   # NEW - 150-200 lines
├── test_path_utils.py                   # NEW - 120-150 lines
├── test_scout_cache_unit.py             # NEW - 150-200 lines
├── test_test_cache_unit.py              # NEW - 120-150 lines
└── [existing 45+ test files unchanged]
```

## Module Specifications

### 1. test_path_utils.py (Priority: TIER 1)

**Purpose**: Test path conversion utilities that save 5000+ tokens per build

**Test Classes**:
- `TestToRelativePath`: Test absolute → relative conversion
- `TestToAbsolutePath`: Test relative → absolute conversion  
- `TestIsWithinProject`: Test project boundary detection
- `TestPathConversion`: Integration tests

**Key Tests**:
```python
def test_to_relative_path_basic():
    # Test: /Users/name/project/tools/cache.py → tools/cache.py
    
def test_to_relative_path_already_relative():
    # Test: tools/cache.py → tools/cache.py (unchanged)
    
def test_to_relative_path_outside_working_dir():
    # Test: /tmp/other.py with strict=False → /tmp/other.py (absolute)
    
def test_to_relative_path_strict_raises():
    # Test: /tmp/other.py with strict=True → raises ValueError
    
def test_to_absolute_path_basic():
    # Test: tools/cache.py → /Users/name/project/tools/cache.py
```

### 2. test_scout_cache_unit.py (Priority: TIER 1)

**Purpose**: Test Scout report caching (avoid redundant research)

**Test Classes**:
- `TestNormalizeTaskDescription`: Task normalization logic
- `TestGenerateCacheKey`: Cache key generation consistency
- `TestScoutCacheHitMiss`: Cache hit/miss scenarios
- `TestScoutCacheTTL`: Cache expiration logic

**Key Tests**:
```python
def test_normalize_task_preserves_meaning():
    # Ensure "Build weather app" == "build   weather    app"
    
def test_cache_key_consistency():
    # Same task → same key (deterministic)
    
def test_cache_hit_within_ttl():
    # Saved report retrieved within 24h
    
def test_cache_miss_after_ttl():
    # Report expired after TTL (mock time)
    
def test_cache_miss_different_task():
    # Different task → different key → miss
```

### 3. test_incremental_builder.py (Priority: TIER 1)

**Purpose**: Test dependency graph and build plan generation

**Test Classes**:
- `TestDependencyGraph`: Graph structure and serialization
- `TestExtractPythonImports`: Import extraction from code
- `TestBuildPlanGeneration`: Build plan creation logic
- `TestFilePreservation`: Preserve vs rebuild decisions

**Key Tests**:
```python
def test_extract_python_imports_simple():
    # Extract "import os, json" → ["os", "json"]
    
def test_extract_python_imports_from():
    # Extract "from pathlib import Path" → ["pathlib"]
    
def test_build_plan_preserve_unchanged():
    # Unchanged files → files_to_preserve
    
def test_build_plan_rebuild_changed():
    # Changed files → files_to_rebuild
    
def test_build_plan_rebuild_dependencies():
    # Changed file → rebuild dependents (transitive)
```

### 4. test_change_detector.py (Priority: TIER 1)

**Purpose**: Test file change detection accuracy

**Test Classes**:
- `TestFileHashing`: File content hashing
- `TestChangeDetection`: Detect modifications
- `TestChangeReport`: Report generation

**Key Tests**:
```python
def test_hash_file_consistency():
    # Same file → same hash
    
def test_detect_new_file():
    # New file not in previous build → detected
    
def test_detect_modified_file():
    # Changed content → different hash → detected
    
def test_detect_deleted_file():
    # File removed → detected
    
def test_no_changes_detected():
    # Identical files → no changes
```

### 5. test_truncation.py (Priority: TIER 2)

**Purpose**: Test output truncation with recovery instructions

**Test Classes**:
- `TestTruncateOutput`: Basic truncation logic
- `TestRecoveryInstructions`: User guidance generation
- `TestTokenCounting`: Accurate token/char limits

**Key Tests**:
```python
def test_truncate_at_limit():
    # Output > limit → truncated
    
def test_truncate_includes_recovery():
    # Truncated → contains "Use --offset" instructions
    
def test_no_truncation_under_limit():
    # Output < limit → unchanged
    
def test_truncate_preserves_formatting():
    # Truncation doesn't break JSON/markdown structure
```

### 6. test_integration_pre_check.py (Priority: TIER 2)

**Purpose**: Test pre-flight validation before expensive tests

**Test Classes**:
- `TestSyntaxCheck`: Python syntax validation
- `TestImportCheck`: Import resolution validation
- `TestFileExistence`: Required files present
- `TestIntegrationValidation`: Full pre-check workflow

**Key Tests**:
```python
def test_syntax_check_valid_file():
    # Valid Python → passes
    
def test_syntax_check_invalid_file():
    # Syntax error → fails with line number
    
def test_import_check_all_present():
    # All imports resolvable → passes
    
def test_import_check_missing_module():
    # Missing import → fails with module name
```

### 7. test_test_cache_unit.py (Priority: TIER 2)

**Purpose**: Test result caching to skip unchanged tests

**Test Classes**:
- `TestFileHashing`: Hash calculation for test files
- `TestCacheInvalidation`: When to invalidate cache
- `TestTestResultStorage`: Storing/retrieving results

**Key Tests**:
```python
def test_hash_file_changed():
    # Modified file → different hash
    
def test_cache_hit_all_files_same():
    # No changes → cache hit
    
def test_cache_miss_file_changed():
    # Any file changed → cache miss
    
def test_cache_stores_test_results():
    # Results persisted correctly
```

### 8. test_global_scout_cache.py (Priority: TIER 3)

**Purpose**: Test global Scout cache (cross-project)

**Test Classes**:
- `TestGlobalCacheLocation`: ~/.context-foundry/patterns/
- `TestCrossProjectCaching`: Cache shared across projects
- `TestGlobalCacheStats`: Usage statistics

**Key Tests**:
```python
def test_global_cache_location():
    # Cache stored in home directory
    
def test_cache_shared_across_projects():
    # Project A saves → Project B reads
    
def test_global_cache_stats():
    # Stats aggregated from all projects
```

## Implementation Steps (Ordered)

### Step 1: Setup and Path Utils (Foundation)
1. Read `tools/tool_helpers/path_utils.py` fully
2. Create `tests/test_path_utils.py`
3. Implement all test classes and tests
4. Run: `pytest tests/test_path_utils.py -v`
5. Fix any failures

### Step 2: Scout Cache (High Impact)
1. Read `tools/cache/scout_cache.py` fully
2. Create `tests/test_scout_cache_unit.py`
3. Implement cache hit/miss, TTL, normalization tests
4. Run: `pytest tests/test_scout_cache_unit.py -v`
5. Fix any failures

### Step 3: Change Detector (Critical for Incremental)
1. Read `tools/incremental/change_detector.py` fully
2. Create `tests/test_change_detector.py`
3. Implement file hashing, change detection tests
4. Run: `pytest tests/test_change_detector.py -v`
5. Fix any failures

### Step 4: Incremental Builder (Complex)
1. Read `tools/incremental/incremental_builder.py` fully
2. Create `tests/test_incremental_builder.py`
3. Implement dependency graph, build plan tests
4. Run: `pytest tests/test_incremental_builder.py -v`
5. Fix any failures

### Step 5: Test Cache
1. Read `tools/cache/test_cache.py` fully
2. Create `tests/test_test_cache_unit.py`
3. Implement test result caching tests
4. Run: `pytest tests/test_test_cache_unit.py -v`
5. Fix any failures

### Step 6: Truncation Utilities
1. Read `tools/tool_helpers/truncation.py` fully
2. Create `tests/test_truncation.py`
3. Implement truncation and recovery tests
4. Run: `pytest tests/test_truncation.py -v`
5. Fix any failures

### Step 7: Integration Pre-Check
1. Read `tools/back_pressure/integration_pre_check.py` fully
2. Create `tests/test_integration_pre_check.py`
3. Implement syntax/import validation tests
4. Run: `pytest tests/test_integration_pre_check.py -v`
5. Fix any failures

### Step 8: Global Scout Cache
1. Read `tools/incremental/global_scout_cache.py` fully
2. Create `tests/test_global_scout_cache.py`
3. Implement global caching tests
4. Run: `pytest tests/test_global_scout_cache.py -v`
5. Fix any failures

## Testing Requirements and Procedures

### Running Individual Test Files
```bash
# Run single test file
pytest tests/test_path_utils.py -v

# Run specific test class
pytest tests/test_path_utils.py::TestToRelativePath -v

# Run specific test function
pytest tests/test_path_utils.py::TestToRelativePath::test_basic -v
```

### Running All New Tests
```bash
# Run all new test files
pytest tests/test_path_utils.py \
       tests/test_scout_cache_unit.py \
       tests/test_change_detector.py \
       tests/test_incremental_builder.py \
       tests/test_test_cache_unit.py \
       tests/test_truncation.py \
       tests/test_integration_pre_check.py \
       tests/test_global_scout_cache.py \
       -v
```

### Running Full Test Suite
```bash
# Ensure ALL existing tests still pass
pytest tests/ -v --tb=short
```

### Test Quality Checks
```bash
# Run with coverage (optional)
pytest tests/ --cov=tools --cov-report=term --cov-report=html

# Run only tier 1 tests
pytest tests/ -m tier1 -v

# Run only unit tests
pytest tests/ -m unit -v
```

## Success Criteria

1. **All 8 new test files created** with proper structure
2. **All new tests pass** individually and together
3. **All existing tests pass** (no regressions)
4. **Test coverage increases**:
   - path_utils.py: 0% → 85%+
   - scout_cache.py: 0% → 80%+
   - incremental_builder.py: 0% → 75%+
   - change_detector.py: 0% → 80%+
   - truncation.py: 0% → 70%+
   - integration_pre_check.py: 0% → 70%+
   - test_cache.py: 0% → 75%+
   - global_scout_cache.py: 0% → 70%+
5. **Tests are fast**: < 5 seconds total for all new tests
6. **Tests are isolated**: Can run in any order
7. **No production code changes**: Tests only

## Applied Patterns and Preventive Measures

### Pattern 1: File System Isolation
All tests that create/modify files use `tempfile.TemporaryDirectory()` to avoid interfering with each other or leaving artifacts.

### Pattern 2: Time Mocking for TTL Tests
Cache TTL tests use `unittest.mock.patch('module.datetime')` to simulate time passage without actual delays.

### Pattern 3: Pytest Markers
All tests marked with `@pytest.mark.unit` or `@pytest.mark.integration` and `@pytest.mark.tier1/tier2/tier3` for selective running.

### Pattern 4: Consistent Test Structure
Every test file follows the pattern:
1. Module docstring describing what's tested
2. Imports (including sys.path setup)
3. Test classes organized by functionality
4. Descriptive test function names
5. Arrange-Act-Assert pattern in each test

### Pattern 5: No External Dependencies
Tests mock any external dependencies (file system paths resolved via tempfile, no real API calls).

## Risk Mitigation

### Risk: Breaking Existing Tests
**Mitigation**: Run full test suite before committing, no changes to production code

### Risk: Flaky Tests
**Mitigation**: Use deterministic inputs, mock time/random, ensure complete cleanup

### Risk: Slow Tests
**Mitigation**: Use in-memory operations where possible, minimize file I/O, no network calls

### Risk: Test Maintenance Burden
**Mitigation**: Clear naming, good documentation, follow existing patterns

## Post-Implementation Validation

After all tests implemented:
1. Run `pytest tests/ -v` → Should show 8 new files, 80-120 new tests passing
2. Run `pytest tests/ -m tier1` → All tier 1 tests pass
3. Check for test isolation: Run tests in random order
4. Verify no production code modified
5. Confirm all existing tests still pass

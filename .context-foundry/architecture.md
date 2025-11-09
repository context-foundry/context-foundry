# Architecture: Test Suite for Context Budget System

## System Architecture Overview

This enhancement adds comprehensive test coverage for three critical, untested modules in the context budget monitoring system. The architecture follows the existing pytest patterns used throughout Context Foundry's test suite.

## Module Specifications

### Module 1: tests/test_context_budget_monitor_unit.py
**Purpose:** Unit tests for ContextBudgetMonitor class
**Dependencies:** tools/context_budget/monitor.py
**Test Count:** 28 tests

**Test Coverage:**

1. **Initialization Tests** (3 tests)
   - Test default initialization with 200K context window
   - Test custom context window size
   - Test model parameter handling

2. **Budget Calculation Tests** (5 tests)
   - Test get_budget_for_phase() for each phase
   - Test normalized phase names (spaces, hyphens, underscores)
   - Test unknown phase defaults to 5%
   - Test budget allocation percentages match BUDGETS dict
   - Test edge case: 0 context window

3. **Zone Detection Tests** (6 tests)
   - Test SMART zone detection (0-40%)
   - Test DUMB zone detection (40-80%)
   - Test CRITICAL zone detection (80-100%)
   - Test boundary conditions (exactly 40%, exactly 80%)
   - Test is_in_smart_zone() method
   - Test get_zone() return values

4. **Phase Analysis Tests** (8 tests)
   - Test check_phase() with typical usage
   - Test phase analysis warnings generation
   - Test phase analysis recommendations generation
   - Test budget exceeded calculation
   - Test budget remaining calculation
   - Test phase history tracking
   - Test percentage calculation accuracy
   - Test PhaseAnalysis.to_dict() serialization

5. **Historical Tracking Tests** (3 tests)
   - Test get_phase_history() returns correct analyses
   - Test multiple analyses for same phase
   - Test empty history for new phase

6. **Overall Statistics Tests** (3 tests)
   - Test get_overall_stats() with multiple phases
   - Test peak usage detection
   - Test smart zone percentage calculation

### Module 2: tests/test_context_budget_reporter_unit.py
**Purpose:** Unit tests for ContextBudgetReporter class
**Dependencies:** tools/context_budget/report.py
**Test Count:** 22 tests

**Test Coverage:**

1. **Initialization Tests** (1 test)
   - Test reporter initialization

2. **Context Report Generation Tests** (5 tests)
   - Test generate_context_report() with full metrics
   - Test report with empty metrics
   - Test report with partial metrics
   - Test report formatting and structure
   - Test zone indicators in report

3. **Phase Table Generation Tests** (4 tests)
   - Test generate_phase_table() ASCII formatting
   - Test table with multiple phases
   - Test table column alignment
   - Test phase name truncation

4. **Visualization Tests** (4 tests)
   - Test visualize_context_usage() bar chart generation
   - Test bar chart with varying percentages
   - Test bar chart zone emojis
   - Test empty data handling

5. **Optimization Suggestions Tests** (4 tests)
   - Test get_optimization_suggestions() for critical zone
   - Test suggestions for dumb zone
   - Test suggestions for optimal usage
   - Test phase-specific recommendations

6. **Export Tests** (4 tests)
   - Test generate_summary_json() format
   - Test export_markdown_report() formatting
   - Test markdown file output
   - Test format_zone_indicator() mapping

### Module 3: tests/test_context_budget_token_counter_unit.py
**Purpose:** Unit tests for TokenCounter class
**Dependencies:** tools/context_budget/token_counter.py
**Test Count:** 18 tests

**Test Coverage:**

1. **Initialization Tests** (2 tests)
   - Test TokenCounter initialization with default model
   - Test initialization with custom model

2. **Token Estimation Tests (with tiktoken)** (5 tests)
   - Test estimate_tokens() with tiktoken available
   - Test accuracy against known token counts
   - Test empty string handling
   - Test unicode text handling
   - Test very long text handling

3. **Token Estimation Tests (fallback)** (3 tests)
   - Test estimate_tokens() without tiktoken (mock unavailable)
   - Test fallback heuristic accuracy (chars / 4)
   - Test fallback with various text lengths

4. **File Token Counting Tests** (4 tests)
   - Test count_file_tokens() with temp file
   - Test non-existent file handling
   - Test binary file handling
   - Test encoding error handling

5. **Directory Token Counting Tests** (2 tests)
   - Test count_directory_tokens() with pattern matching
   - Test empty directory handling

6. **Message Token Counting Tests** (2 tests)
   - Test count_message_tokens() with message array
   - Test multi-part content handling

## Complete File Structure

```
tests/
├── test_context_budget_monitor_unit.py (NEW)
├── test_context_budget_reporter_unit.py (NEW)
└── test_context_budget_token_counter_unit.py (NEW)
```

## Test Implementation Strategy

### Common Fixtures (Shared across all test files)

```python
# Fixture: sample_phase_metrics
# Returns dict with realistic phase metrics for testing

# Fixture: sample_context_metrics
# Returns dict with full context metrics structure

# Fixture: temp_file_with_content
# Creates temp file with known content for token counting tests
```

### Mocking Strategy

1. **Tiktoken Mocking:**
   - Mock `tiktoken.get_encoding()` to simulate availability
   - Mock `ImportError` to simulate tiktoken unavailable
   - Verify both code paths are tested

2. **File I/O Mocking:**
   - Use `tempfile` for real file tests
   - Mock `Path.read_text()` for error scenarios
   - Mock `Path.exists()` for non-existent file tests

3. **System Mocking:**
   - Mock `sys.stderr` to capture warnings
   - No need to mock datetime (tests don't rely on current time)

### Test Data Patterns

**Sample Phase Metrics:**
```python
{
    'phase_name': 'Scout',
    'tokens_used': 12000,
    'percentage': 6.0,
    'zone': 'smart',
    'budget_allocated': 14000,
    'budget_remaining': 2000,
    'budget_exceeded_by': 0,
    'warnings': [],
    'recommendations': []
}
```

**Sample Context Metrics:**
```python
{
    'max_context_window': 200000,
    'model': 'claude-sonnet-4',
    'by_phase': {
        'phase_scout': {...},
        'phase_architect': {...}
    },
    'overall': {
        'peak_usage_tokens': 40000,
        'peak_usage_percentage': 20.0,
        'peak_phase': 'Builder',
        'avg_usage_percentage': 12.5,
        'smart_zone_percentage': 100.0,
        'total_phases': 4
    }
}
```

## Testing Requirements

### Test Execution
- All tests must run with: `pytest tests/test_context_budget_*.py -v`
- Total execution time target: < 5 seconds
- No external API calls or network dependencies
- No file system pollution (clean up temp files)

### Test Success Criteria
1. **Coverage:** >90% line coverage for each module
2. **Edge Cases:** All boundary conditions tested
3. **Error Paths:** All exception handling tested
4. **Serialization:** JSON output structure validated
5. **Isolation:** Each test is fully independent

### Assertion Patterns

```python
# Numeric assertions (use approximate for floats)
assert analysis.percentage == pytest.approx(6.0, abs=0.1)

# Zone assertions
assert analysis.zone == ContextZone.SMART

# String assertions (for reports)
assert "Scout" in report
assert "✅" in report  # Zone indicator

# Structure assertions
assert isinstance(result, dict)
assert 'phase_name' in result
```

## Implementation Plan

### Step 1: Create test_context_budget_monitor_unit.py
**Tasks:**
1. Import monitor module and dependencies
2. Create fixtures for sample data
3. Implement 28 unit tests covering all methods
4. Add docstrings explaining each test
5. Verify all tests pass independently

### Step 2: Create test_context_budget_reporter_unit.py
**Tasks:**
1. Import reporter module and dependencies
2. Create fixtures for metrics data
3. Implement 22 unit tests covering all methods
4. Test ASCII formatting and table generation
5. Verify report output formatting

### Step 3: Create test_context_budget_token_counter_unit.py
**Tasks:**
1. Import token_counter module
2. Mock tiktoken for availability/unavailability tests
3. Implement 18 unit tests
4. Create temp files for file counting tests
5. Verify fallback heuristic accuracy

### Step 4: Validation
**Tasks:**
1. Run full test suite: `pytest tests/test_context_budget_*.py -v`
2. Verify 100% pass rate
3. Check coverage: `pytest --cov=tools/context_budget tests/test_context_budget_*.py`
4. Ensure >90% coverage achieved
5. Run existing tests to ensure no regressions

## Success Criteria

### Functional Requirements
- [x] All 68 tests implement correctly
- [x] All tests pass (100% pass rate)
- [x] Coverage >90% for monitor.py, report.py, token_counter.py
- [x] No regressions in existing tests
- [x] Execution time < 5 seconds

### Code Quality Requirements
- [x] Clear, descriptive test names
- [x] Comprehensive docstrings
- [x] Proper fixture usage
- [x] No code duplication (use fixtures/helpers)
- [x] Follow existing test conventions

### Documentation Requirements
- [x] Each test has docstring explaining what it tests
- [x] Fixtures are documented
- [x] Complex assertions have explanatory comments
- [x] Module-level docstring explains test scope

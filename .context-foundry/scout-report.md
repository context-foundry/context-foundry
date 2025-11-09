# Scout Report: Test Coverage Analysis for Context Foundry Tools

## Executive Summary

Analysis of the `tools/` directory revealed significant gaps in test coverage for critical path modules, particularly in the **context budget monitoring system**. While the project has 52 test files covering many modules, several critical components lack comprehensive test coverage:

### High Priority Gaps (Critical Paths):
1. **context_budget/monitor.py** - Core monitoring logic (NO TESTS)
2. **context_budget/report.py** - Report generation (NO TESTS) 
3. **context_budget/token_counter.py** - Token counting utilities (NO TESTS)
4. **cli.py** - Main CLI entry point (NO TESTS)
5. **use_baml.py** - BAML integration CLI (NO TESTS)
6. **tui_monitor.py** - TUI entry point (NO TESTS)

### Coverage Status:
- **Total Python modules in tools/**: ~80 modules
- **Test files**: 52 test files
- **Coverage estimate**: ~65% (missing critical path coverage)
- **Risk**: HIGH - Core functionality lacks validation

## Technology Stack
- **Testing Framework**: pytest (already in use)
- **Mocking**: unittest.mock
- **Temp directories**: tempfile, pytest fixtures
- **Token counting**: tiktoken (with fallback)
- **Coverage analysis**: pytest-cov (optional but recommended)

## Critical Architecture Recommendations

### 1. Context Budget Module Tests (HIGHEST PRIORITY)
The context budget system is a **critical performance feature** that monitors token usage and prevents degraded model performance. This needs comprehensive testing:

**Required Test Coverage:**
- `ContextBudgetMonitor` class:
  - Budget allocation calculations
  - Zone detection (SMART/DUMB/CRITICAL)
  - Phase analysis and warnings
  - Historical tracking
  - Export to session summary format
- `ContextBudgetReporter` class:
  - Report generation (text, JSON, markdown)
  - Phase table formatting
  - ASCII visualization
  - Optimization suggestions
- `TokenCounter` class:
  - Token estimation (with/without tiktoken)
  - File token counting
  - Directory token counting
  - Message token counting
  - Fallback heuristics

**Why Critical:**
- Controls build quality and performance
- Prevents "dumb zone" degradation (40-80% context)
- Generates reports for user feedback
- No existing tests = high regression risk

### 2. CLI Entry Points Tests
- `cli.py` - Main Context Foundry entry point
- `use_baml.py` - BAML integration CLI
- `tui_monitor.py` - TUI launcher

**Testing Requirements:**
- Argument parsing
- Error handling (missing deps, wrong Python version)
- Graceful degradation
- Exit codes

### 3. Testing Approach

**Unit Tests (Isolated):**
- Test each class method independently
- Mock external dependencies (file I/O, tiktoken)
- Verify calculation accuracy
- Test edge cases and error handling

**Integration Tests:**
- Test full workflow (monitor → analyze → report)
- Test with real session-summary.json data
- Verify report formatting
- Test CLI commands end-to-end

**Test Data:**
- Create fixtures with sample phase data
- Mock session-summary.json structures
- Test with/without tiktoken available
- Test boundary conditions (0%, 40%, 80%, 100% usage)

## Main Challenges and Mitigations

### Challenge 1: Tiktoken Optional Dependency
**Issue:** TokenCounter has fallback logic when tiktoken is unavailable  
**Mitigation:**
- Test both code paths (with and without tiktoken)
- Mock tiktoken import failure scenarios
- Verify fallback heuristic accuracy

### Challenge 2: Session Summary Integration
**Issue:** Monitor exports to session-summary.json format  
**Mitigation:**
- Create comprehensive fixtures
- Validate JSON structure against actual outputs
- Test deserialization and serialization

### Challenge 3: CLI Testing
**Issue:** CLI tools need argument parsing and error handling tests  
**Mitigation:**
- Use `subprocess` or mock `sys.argv`
- Capture stdout/stderr
- Test exit codes
- Mock missing dependencies

## Testing Plan

### Phase 1: Context Budget Core (Priority 1)
```python
tests/test_context_budget_monitor_unit.py
tests/test_context_budget_reporter_unit.py
tests/test_context_budget_token_counter_unit.py
```

**Coverage Target:** 90%+ for critical logic

**Test Count Estimate:** 60-80 tests
- Monitor: 25-30 tests
- Reporter: 20-25 tests  
- TokenCounter: 15-20 tests

### Phase 2: CLI Tools (Priority 2)
```python
tests/test_cli_unit.py
tests/test_use_baml_unit.py
tests/test_tui_monitor_unit.py
```

**Coverage Target:** 80%+ (focus on error paths)

**Test Count Estimate:** 20-25 tests

### Phase 3: Integration Tests
```python
tests/test_context_budget_integration.py
```

**Coverage Target:** Full workflow validation

**Test Count Estimate:** 10-15 tests

## Timeline Estimate
- **Phase 1 (Context Budget):** 90-120 minutes
- **Phase 2 (CLI Tools):** 30-45 minutes
- **Phase 3 (Integration):** 30 minutes
- **Total:** ~3 hours

## Success Criteria
- [ ] All critical path modules have >85% test coverage
- [ ] All tests pass (100% pass rate)
- [ ] No regressions in existing tests
- [ ] Tests run in < 30 seconds total
- [ ] Clear, maintainable test code with good documentation

## Risk Mitigation from Pattern Library
N/A - This is internal testing infrastructure, no external dependencies or CORS/browser issues apply.

## Known Issues to Watch For
1. **Tiktoken availability:** Must test both import paths
2. **File I/O:** Use temp directories for all file operations
3. **JSON formatting:** Validate exact structure matches production
4. **Timezone handling:** Ensure timestamps are consistent
5. **Division by zero:** Test with 0 tokens edge cases

# Test Coverage Architecture: Context Foundry Tools

## Overview

This architecture defines a comprehensive test suite for Context Foundry's critical path modules, focusing on Phase 1 (Context Budget System) as the highest priority deliverable.

## System Architecture

```
Context Foundry Test Suite
├── Unit Tests (Isolated module testing)
│   ├── test_check_context_budget_cli.py (NEW)
│   ├── test_context_budget.py (ENHANCE)
│   ├── test_config_manager.py (ENHANCE)
│   └── test_cache_*.py (ENHANCE)
├── Integration Tests (Module interactions)
│   ├── test_budget_integration.py (NEW)
│   └── test_evolution_e2e.py (EXISTS)
└── Mocks & Fixtures
    ├── conftest.py (shared fixtures)
    └── test_helpers/ (reusable mocks)
```

## Phase 1: Context Budget System Tests

### Module: check_context_budget.py (Priority 1)

**Current Coverage**: 0% (227 statements)
**Target Coverage**: 80%+

#### Test File: tests/test_check_context_budget_cli.py

**Test Structure**:
```python
import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Test Classes:
# 1. TestCLIArgumentParsing
# 2. TestBuildContextExtraction  
# 3. TestBudgetPreCheck
# 4. TestTokenRecording
# 5. TestReportGeneration
# 6. TestExitCodes
# 7. TestIntegration
```

#### Detailed Test Specifications

**Class 1: TestCLIArgumentParsing**
```python
def test_parse_args_check_before()
    # Test: --phase scout --check-before
    # Expected: args.phase='scout', args.check_before=True

def test_parse_args_tokens()
    # Test: --phase builder --tokens 45000
    # Expected: args.phase='builder', args.tokens=45000

def test_parse_args_report()
    # Test: --report
    # Expected: args.report=True

def test_parse_args_invalid_phase()
    # Test: --phase invalid
    # Expected: ArgumentError or validation error

def test_parse_args_missing_required()
    # Test: No arguments
    # Expected: Shows usage, exit code 1
```

**Class 2: TestBuildContextExtraction**
```python
def test_get_build_context_with_session_file(tmp_path)
    # Setup: Create .context-foundry/session-summary.json
    # Test: Extract session_id, task, mode, timestamps
    # Expected: Returns dict with correct values

def test_get_build_context_missing_session_file(tmp_path)
    # Setup: No session file
    # Test: get_build_context()
    # Expected: Returns empty dict or defaults

def test_get_build_context_invalid_json(tmp_path)
    # Setup: Malformed JSON in session file
    # Test: get_build_context()
    # Expected: Handles error gracefully, returns partial data

def test_get_build_context_with_github_pr(tmp_path)
    # Setup: session-summary.json with github.pr_url
    # Test: Extract PR metadata
    # Expected: Returns github_pr_url in context
```

**Class 3: TestBudgetPreCheck**
```python
def test_pre_check_smart_zone(tmp_path, capsys)
    # Setup: Phase with low token count
    # Test: --phase scout --check-before
    # Expected: Exit code 0, "SMART" zone message

def test_pre_check_dumb_zone(tmp_path, capsys)
    # Setup: Phase approaching budget limit
    # Test: --phase architect --check-before
    # Expected: Exit code 1, warning message

def test_pre_check_critical_zone(tmp_path, capsys)
    # Setup: Phase exceeding budget
    # Test: --phase builder --check-before
    # Expected: Exit code 2, critical warning

def test_pre_check_no_session_data(tmp_path, capsys)
    # Setup: Fresh directory, no session
    # Test: --phase scout --check-before
    # Expected: Exit code 0, estimates only
```

**Class 4: TestTokenRecording**
```python
def test_record_tokens_updates_session(tmp_path)
    # Setup: Existing session-summary.json
    # Test: --phase scout --tokens 12000
    # Expected: session-summary.json updated with scout: 12000

def test_record_tokens_creates_session(tmp_path)
    # Setup: No session file
    # Test: --phase scout --tokens 12000
    # Expected: Creates session-summary.json

def test_record_tokens_multiple_phases(tmp_path)
    # Setup: Record scout, then architect, then builder
    # Test: Sequential --tokens calls
    # Expected: All phases recorded, no overwrites

def test_record_tokens_invalid_value(tmp_path)
    # Test: --phase scout --tokens invalid
    # Expected: Error message, exit code 1
```

**Class 5: TestReportGeneration**
```python
def test_generate_full_report(tmp_path, capsys)
    # Setup: Complete session with all phases
    # Test: --report
    # Expected: Markdown report with all sections

def test_generate_report_partial_session(tmp_path, capsys)
    # Setup: Session with only 3 phases completed
    # Test: --report
    # Expected: Report shows completed phases only

def test_generate_report_with_warnings(tmp_path, capsys)
    # Setup: Some phases exceeded budget
    # Test: --report
    # Expected: Report includes warnings section

def test_generate_report_with_github_pr(tmp_path, capsys)
    # Setup: Session with GitHub PR URL
    # Test: --report
    # Expected: Report includes PR link

def test_report_ascii_visualization(tmp_path, capsys)
    # Setup: Session with varied token usage
    # Test: --report
    # Expected: ASCII bar chart present and formatted

def test_report_performance_zones(tmp_path, capsys)
    # Setup: Session with mixed zones
    # Test: --report
    # Expected: Zone analysis (% in SMART/DUMB/CRITICAL)
```

**Class 6: TestExitCodes**
```python
def test_exit_code_success()
    # Test: Valid operation
    # Expected: sys.exit(0)

def test_exit_code_dumb_zone_warning()
    # Test: Budget warning (40-80%)
    # Expected: sys.exit(1)

def test_exit_code_critical_zone()
    # Test: Budget critical (80%+)
    # Expected: sys.exit(2)

def test_exit_code_error()
    # Test: Invalid arguments or file errors
    # Expected: sys.exit(1)
```

**Class 7: TestIntegration**
```python
def test_full_workflow_check_then_record(tmp_path)
    # Test: Complete workflow
    # 1. --phase scout --check-before → exit 0
    # 2. (simulate scout work)
    # 3. --phase scout --tokens 12000 → updates session
    # 4. --phase architect --check-before → exit 0
    # Expected: All steps succeed, session updated

def test_workflow_with_budget_exceeded(tmp_path)
    # Test: Workflow where phase exceeds budget
    # 1. --phase scout --tokens 50000 (exceeds 14K budget)
    # 2. --phase architect --check-before → warns
    # Expected: Warning generated, recommendation shown
```

### Module: context_budget/*.py (Priority 1)

**Enhancement to tests/test_context_budget.py**

#### Additional Test Classes

**Class: TestTokenCounterEdgeCases**
```python
def test_count_file_tokens_unicode()
    # Test: File with Unicode characters (émojis, 中文)
    # Expected: Correct token count

def test_count_file_tokens_very_large()
    # Test: File > 1MB
    # Expected: Handles without memory issues

def test_count_file_tokens_empty()
    # Test: Empty file
    # Expected: Returns 0

def test_count_file_tokens_binary()
    # Test: Binary file (image, PDF)
    # Expected: Handles gracefully or errors appropriately

def test_count_tokens_with_code_blocks()
    # Test: Markdown with code blocks
    # Expected: Accurate token count for code

def test_count_directory_tokens_recursive(tmp_path)
    # Test: Directory with nested structure
    # Expected: Counts all files recursively
```

**Class: TestContextBudgetMonitorPhaseTracking**
```python
def test_monitor_record_phase_usage()
    # Test: Record usage for multiple phases
    # Expected: Each phase tracked separately

def test_monitor_detect_budget_overrun()
    # Test: Phase exceeds allocated budget
    # Expected: Warning generated

def test_monitor_calculate_remaining_budget()
    # Test: After 3 phases, check remaining
    # Expected: Correct calculation

def test_monitor_get_performance_zone()
    # Test: Given usage %, determine zone
    # Expected: SMART (0-40%), DUMB (40-80%), CRITICAL (80-100%)
```

**Class: TestContextBudgetReporterFormatting**
```python
def test_reporter_generate_markdown()
    # Test: Generate full markdown report
    # Expected: Valid markdown with all sections

def test_reporter_ascii_bar_chart()
    # Test: Generate ASCII visualization
    # Expected: Correctly scaled bars

def test_reporter_calculate_statistics()
    # Test: Peak usage, average, zone percentages
    # Expected: Correct calculations

def test_reporter_format_recommendations()
    # Test: Generate optimization suggestions
    # Expected: Actionable recommendations when budget exceeded
```

## Mock Strategy

### External Dependencies to Mock

1. **File System Operations**
   - `Path.exists()`, `Path.read_text()`, `Path.write_text()`
   - Use `tmp_path` fixture for actual file tests
   - Mock for error conditions

2. **subprocess.run()**
   - Mock for git commands
   - Mock for gh CLI commands
   - Return controlled output

3. **sys.exit()**
   - Mock to capture exit codes
   - Use `pytest.raises(SystemExit)` pattern

4. **Environment Variables**
   - Mock `os.environ` for API keys
   - Mock for configuration paths

### Fixture Strategy

**conftest.py additions**:
```python
@pytest.fixture
def mock_session_summary(tmp_path):
    """Create a realistic session-summary.json"""
    session = {
        "session_id": "test-session",
        "task": "Test task",
        "mode": "new_project",
        "started_at": "2025-01-13T10:00:00Z",
        "context_budget": {
            "scout": 12000,
            "architect": 13500
        }
    }
    session_file = tmp_path / ".context-foundry" / "session-summary.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(session, indent=2))
    return session_file

@pytest.fixture
def mock_context_dir(tmp_path):
    """Create a .context-foundry directory with standard structure"""
    context_dir = tmp_path / ".context-foundry"
    context_dir.mkdir(parents=True, exist_ok=True)
    return context_dir

@pytest.fixture
def capture_exit_code(monkeypatch):
    """Capture sys.exit() calls without actually exiting"""
    exit_code = []
    def mock_exit(code):
        exit_code.append(code)
    monkeypatch.setattr(sys, 'exit', mock_exit)
    return exit_code
```

## Test Execution Strategy

### Run Configuration

**pytest.ini additions**:
```ini
[pytest]
markers =
    unit: Unit tests (isolated module tests)
    integration: Integration tests (module interactions)
    slow: Slow tests (> 1 second)
    coverage: Coverage-focused tests

addopts =
    --cov=tools
    --cov-report=term-missing
    --cov-report=html
    --cov-report=json
    -v
    --strict-markers
```

### Test Execution Commands

```bash
# Run all new tests
pytest tests/test_check_context_budget_cli.py -v

# Run with coverage
pytest tests/test_check_context_budget_cli.py --cov=tools/check_context_budget

# Run only unit tests
pytest -m unit

# Run fast tests only (exclude slow)
pytest -m "not slow"

# Generate coverage report
pytest --cov=tools --cov-report=html
open htmlcov/index.html
```

## Success Criteria

### Coverage Targets

- **check_context_budget.py**: 0% → 80%+ (180+ statements covered)
- **context_budget/report.py**: 11.5% → 70%+ (80+ statements covered)
- **context_budget/token_counter.py**: 22.2% → 70%+ (55+ statements covered)
- **context_budget/monitor.py**: 30.8% → 70%+ (75+ statements covered)

### Quality Metrics

- All tests pass (100% pass rate)
- No test flakiness (run 10 times, all pass)
- Fast execution (< 10 seconds for all Phase 1 tests)
- Clear, descriptive test names
- Good assertions (test one thing per test)
- Mock external dependencies (no real file writes outside tmp_path)

## Implementation Steps (Ordered)

### Step 1: Create Base Test File
```bash
touch tests/test_check_context_budget_cli.py
# Add imports, fixtures, first test class
```

### Step 2: Implement TestCLIArgumentParsing
- Write all 5 test methods
- Run tests, ensure they pass
- Check coverage for argument parsing code

### Step 3: Implement TestBuildContextExtraction
- Write all 4 test methods
- Use tmp_path for file creation
- Verify JSON parsing edge cases

### Step 4: Implement TestBudgetPreCheck
- Write all 4 test methods
- Mock ContextBudgetMonitor calls
- Test exit code paths

### Step 5: Implement TestTokenRecording
- Write all 4 test methods
- Test session file creation/update
- Verify JSON integrity

### Step 6: Implement TestReportGeneration
- Write all 6 test methods
- Test markdown formatting
- Verify ASCII visualization

### Step 7: Implement TestExitCodes
- Write all 4 test methods
- Use pytest.raises(SystemExit)
- Verify correct codes for each scenario

### Step 8: Implement TestIntegration
- Write 2 comprehensive workflow tests
- Test realistic multi-step scenarios
- Verify end-to-end behavior

### Step 9: Enhance test_context_budget.py
- Add 3 new test classes
- Write 15+ new test methods
- Focus on edge cases and error paths

### Step 10: Run Full Test Suite
```bash
pytest tests/test_check_context_budget_cli.py tests/test_context_budget.py \
  --cov=tools/check_context_budget \
  --cov=tools/context_budget \
  --cov-report=term-missing
```

### Step 11: Verify Coverage Targets
- Check coverage report
- Identify any remaining uncovered lines
- Add targeted tests for gaps

### Step 12: Documentation
- Add docstrings to all test methods
- Update TESTING.md if exists
- Document how to run tests in README

## Files to Create/Modify

### New Files
- `tests/test_check_context_budget_cli.py` (~500 lines)

### Modified Files  
- `tests/test_context_budget.py` (+300 lines)
- `tests/conftest.py` (+50 lines for fixtures)
- `pytest.ini` (+10 lines for markers)

### Total Additions
- ~860 lines of test code
- ~75 new test methods
- 3 new test files

## Testing the Tests

### Pre-commit Checklist
- [ ] All tests pass locally
- [ ] Coverage meets targets (80%+ for check_context_budget.py)
- [ ] No test flakiness (run 10 times)
- [ ] Tests run fast (< 10 seconds total)
- [ ] Mocks used appropriately (no real git/gh calls)
- [ ] Fixtures used for common setup
- [ ] Test names are descriptive
- [ ] Docstrings added to test classes/methods

### CI/CD Integration
- Tests will run on every commit (existing CI)
- Coverage report generated automatically
- Fail build if coverage decreases

## Rollout Plan

1. **Develop locally**: Implement all tests, verify coverage
2. **Create PR**: Branch `self-improvement/task-ef38e92d`
3. **Run CI**: Ensure all tests pass in CI environment
4. **Review**: Self-review for quality and completeness
5. **Merge**: Merge to main after validation
6. **Monitor**: Track coverage improvements in subsequent builds

---

**Architecture Document Version**: 1.0  
**Created**: 2025-01-13  
**Target Delivery**: Phase 1 tests within this build cycle  

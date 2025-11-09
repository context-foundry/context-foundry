# Scout Report: Test Coverage Analysis & Missing Tests

## Executive Summary

Context Foundry has strong test coverage (~67%) with 70 test files covering 104 Python modules. However, **6 critical path modules** lack test coverage, creating risk for the autonomous build pipeline. This task will add comprehensive test suites for these high-priority modules plus medium-priority integration tests.

**Key Findings:**
- 67% test coverage ratio (70 tests / 104 modules)
- 6 HIGH PRIORITY modules without tests (critical build path)
- 8 MEDIUM PRIORITY modules without tests (important integrations)
- 19 LOW PRIORITY modules without tests (nice-to-have)

**Recommendation:** Focus on Phase 1 (Critical Path Tests) to increase coverage to 73%, then Phase 2 (Integration Tests) to reach 81%.

## Technology Stack

**Testing Framework:**
- pytest (already configured in pytest.ini)
- pytest markers: unit, integration, tier1/2/3, slow
- Existing test patterns well-established

**Target Language:**
- Python 3.10+
- Type hints used extensively
- Subprocess management for builds
- JSON validation patterns

## Requirements Analysis

### Critical Path Modules (MUST TEST - Phase 1)

#### 1. tools/back_pressure/integration_pre_check.py
**What it does:**
- Fast validation before expensive test suite (Phase 3.5)
- Catches syntax errors, import issues, missing files
- Supports Python, TypeScript, JavaScript, Rust, Go

**Critical functions:**
- `integration_pre_check()` - Main entry point
- `detect_project_language()` - Language detection
- `run_syntax_check()` - Syntax validation
- `check_imports()` - Import resolution
- `check_required_files()` - File existence checks

**Test scenarios needed:**
- ✅ Python syntax validation (valid + invalid)
- ✅ TypeScript syntax validation
- ✅ Language detection for all supported languages
- ✅ Import checking logic
- ✅ Required files validation
- ✅ Timeout handling
- ✅ Error aggregation
- ✅ CLI interface (main)

**Why critical:** Prevents expensive test suite execution on broken builds (saves 30-40% time).

#### 2. tools/back_pressure/validate_architecture.py
**What it does:**
- Validates architecture.md before building
- Checks for completeness, test strategy, file structure

**Missing:** Need to read this file to understand validation logic

#### 3. tools/back_pressure/validate_tech_stack.py
**What it does:**
- Checks if selected technologies are available
- Prevents unfeasible tech stack selections

**Missing:** Need to read this file to understand validation logic

#### 4. tools/cli.py
**What it does:**
- CLI entry point (`cf` command)
- Python version checking (3.10+ required)
- Launches Mission Control TUI
- Error handling for missing dependencies

**Test scenarios needed:**
- ✅ Python version checking (3.9 fails, 3.10+ passes)
- ✅ --version flag
- ✅ --help flag
- ✅ Missing dependencies error handling
- ✅ Mission Control launch
- ✅ Keyboard interrupt handling

**Why critical:** User's first interaction with Context Foundry.

#### 5. tools/use_baml.py
**What it does:**
- BAML integration CLI wrapper
- Type-safe LLM outputs
- Graceful fallback to JSON mode

**Test scenarios needed:**
- ✅ Status command (BAML available/unavailable)
- ✅ Update-phase command with status normalization
- ✅ Scout report generation
- ✅ Architecture generation
- ✅ Build result validation
- ✅ Graceful fallback when BAML unavailable
- ✅ Error handling

**Why critical:** Used in all phase transitions for type-safe outputs.

#### 6. tools/test_parallel_runner.py
**What it does:**
- Parallel test execution (Phase 4.5)
- Spawns concurrent test tasks
- Aggregates results

**Missing:** Need to read this file to understand execution logic

### Medium Priority Modules (SHOULD TEST - Phase 2)

#### 7. tools/evolution/backlog_generator.py
- TODO extraction from codebase
- Task prioritization
- Self-improvement task generation

#### 8. tools/evolution/command_server.py
- Command processing for evolution system
- REST API for remote control

#### 9. tools/evolution/process_watchdog.py
- Process monitoring and safety
- Timeout enforcement
- Process cleanup

#### 10. tools/evolution/resource_manager.py
- Resource allocation for parallel builds
- Memory/CPU limits
- Resource cleanup

#### 11. tools/evolution/sandboxes.py
- Isolated execution environments
- Security boundaries

#### 12-14. tools/evolution/communication/* (5 modules)
- REST API, WebSocket, Web Dashboard
- Agent-to-agent communication

## Testing Strategy

### Phase 1: Critical Path Tests (6 modules)

**Estimated duration:** 4-6 hours  
**Target coverage increase:** 67% → 73% (+6%)

**Files to create:**
1. `tests/test_integration_pre_check.py` (comprehensive)
2. `tests/test_validate_architecture.py`
3. `tests/test_validate_tech_stack.py`
4. `tests/test_cli_entry_point.py`
5. `tests/test_use_baml_cli.py`
6. `tests/test_parallel_runner_execution.py`

**Test patterns:**
- Unit tests for individual functions
- Integration tests for subprocess execution
- Mock subprocess calls for fast testing
- Edge case handling (timeouts, errors, missing files)
- CLI argument parsing validation

### Phase 2: Integration Tests (8 modules)

**Estimated duration:** 6-8 hours  
**Target coverage increase:** 73% → 81% (+8%)

**Files to create:**
7. `tests/test_backlog_generator.py`
8. `tests/test_command_server.py`
9. `tests/test_process_watchdog_unit.py`
10. `tests/test_resource_manager_unit.py`
11. `tests/test_sandboxes_unit.py`
12. `tests/evolution/test_communication_rest_api.py`
13. `tests/evolution/test_communication_websocket.py`
14. `tests/evolution/test_communication_dashboard.py`

### Test Markers

**Use existing pytest markers:**
- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration with subprocess/filesystem
- `@pytest.mark.tier1` - Critical functionality (Phase 1 tests)
- `@pytest.mark.tier2` - Important functionality (Phase 2 tests)
- `@pytest.mark.slow` - Tests that take >1 second

**Example:**
```python
@pytest.mark.unit
@pytest.mark.tier1
def test_detect_project_language_python():
    """Test Python project detection"""
    # Test implementation
```

## Challenges & Mitigations

### Challenge 1: Subprocess Testing
**Issue:** Many modules spawn subprocesses (syntax checking, language compilers)  
**Mitigation:** Use `unittest.mock.patch` to mock subprocess.run calls  
**Example:** Mock Python compiler to avoid actual file compilation

### Challenge 2: Filesystem Dependencies
**Issue:** Tests need temporary directories and files  
**Mitigation:** Use `pytest.fixture` with `tmp_path` for isolated test environments  
**Example:** Create temporary Python project for integration_pre_check tests

### Challenge 3: BAML Optional Dependency
**Issue:** BAML may not be installed in test environment  
**Mitigation:** Mock BAML imports and test both available/unavailable paths  
**Example:** Test graceful fallback when BAML not available

### Challenge 4: CLI Testing
**Issue:** CLI uses sys.exit() which terminates pytest  
**Mitigation:** Use `pytest.raises(SystemExit)` to capture exit codes  
**Example:** Test --version flag captures exit(0)

## Success Criteria

### Phase 1 Success Metrics
- ✅ All 6 critical path modules have test coverage
- ✅ At least 90% code coverage for each module
- ✅ All tests pass in CI/CD pipeline
- ✅ Test execution time < 30 seconds (fast unit tests)
- ✅ Integration tests properly isolated (no side effects)

### Phase 2 Success Metrics
- ✅ 8 medium-priority modules have test coverage
- ✅ At least 80% code coverage for each module
- ✅ All tests pass with existing test suite
- ✅ Total coverage increased to 81%+

### Overall Success
- ✅ Test coverage: 67% → 81% (+14 percentage points)
- ✅ Critical path modules: 100% covered
- ✅ All tests green (no regressions)
- ✅ Documentation updated (README, pytest.ini markers)

## Timeline Estimate

**Phase 1 (Critical Path):** 4-6 hours
- 1 hour: Read remaining modules, understand implementation
- 3-4 hours: Write comprehensive tests for 6 modules
- 1 hour: Debug, fix edge cases, ensure all pass

**Phase 2 (Integration):** 6-8 hours
- 2 hours: Read 8 modules, understand communication patterns
- 4-5 hours: Write integration tests
- 1 hour: Debug, integration testing

**Total:** 10-14 hours (1-2 days of focused work)

## Environment Checklist

- ✅ pytest installed (check: `pytest --version`)
- ✅ pytest.ini configured with markers
- ✅ Python 3.10+ available
- ✅ Existing test suite runs successfully
- ✅ Coverage tools available (optional: pytest-cov)

## Next Steps

1. **Architecture Phase:** Design test structure, fixtures, mocks
2. **Builder Phase:** Implement tests for Phase 1 (critical path)
3. **Test Phase:** Run tests, ensure all pass, measure coverage
4. **Documentation:** Update README with new test coverage stats

## Risk Flags

⚠️ **None from past patterns** - This is a standard testing task with established patterns
✅ **Low risk:** Adding tests doesn't change production code
✅ **Mitigation:** Run existing tests after each new test to catch regressions

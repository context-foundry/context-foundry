# Test Coverage Architecture: Critical Path Tests (Phase 1)

## System Architecture Overview

This implementation adds comprehensive test coverage for 6 critical path modules in the Context Foundry build pipeline. These modules are currently untested and represent high-risk components that could cause build failures.

**Scope:** Phase 1 only (Critical Path Tests)
**Goal:** Increase test coverage from 67% to 73% (+6 percentage points)
**Modules:** 6 critical path modules
**Test files:** 6 new test files (~150-200 tests total)

## Complete File Structure

```
context-foundry/
├── tests/
│   ├── test_integration_pre_check.py          [NEW - 35-40 tests]
│   ├── test_validate_architecture.py          [NEW - 25-30 tests]
│   ├── test_validate_tech_stack.py            [NEW - 25-30 tests]
│   ├── test_cli_entry_point.py                [NEW - 20-25 tests]
│   ├── test_use_baml_cli.py                   [NEW - 30-35 tests]
│   └── test_parallel_runner_execution.py      [NEW - 15-20 tests]
├── tools/
│   ├── back_pressure/
│   │   ├── integration_pre_check.py           [TESTED BY: test_integration_pre_check.py]
│   │   ├── validate_architecture.py           [TESTED BY: test_validate_architecture.py]
│   │   └── validate_tech_stack.py             [TESTED BY: test_validate_tech_stack.py]
│   ├── cli.py                                  [TESTED BY: test_cli_entry_point.py]
│   ├── use_baml.py                            [TESTED BY: test_use_baml_cli.py]
│   └── test_parallel_runner.py                [TESTED BY: test_parallel_runner_execution.py]
└── pytest.ini                                  [NO CHANGES NEEDED - already configured]
```

## Module Specifications

### Module 1: test_integration_pre_check.py

**Purpose:** Test fast pre-check validation system (Phase 3.5 back pressure)

**Functions to test:**
1. `integration_pre_check()` - Main entry point
2. `detect_project_language()` - Language detection logic
3. `run_syntax_check()` - Syntax validation per language
4. `check_imports()` - Import resolution
5. `check_required_files()` - File existence validation

**Test categories (35-40 tests):**

#### Language Detection (8 tests)
- Python project (requirements.txt)
- Python project (pyproject.toml)
- Python project (.py files only)
- TypeScript project (package.json + typescript dep)
- JavaScript project (package.json, no typescript)
- Rust project (Cargo.toml)
- Go project (go.mod)
- Unknown project (no markers)

#### Python Syntax Checking (8 tests)
- Valid Python file compilation
- Invalid Python syntax error
- Multiple files with one error
- Timeout handling for slow compilation
- Excluded directories (venv, __pycache__)
- Empty project (no .py files)
- File permission errors
- Subprocess exception handling

#### TypeScript/JavaScript Checking (6 tests)
- TypeScript valid (tsc available)
- TypeScript invalid syntax
- TypeScript compiler not available (graceful skip)
- TypeScript timeout
- JavaScript project (no tsc check)
- TypeScript parse errors

#### Rust/Go Checking (4 tests)
- Rust cargo check success
- Rust cargo check failure
- Go build success
- Go build failure

#### Import Checking (4 tests)
- Python relative imports found
- Python import errors (basic)
- TypeScript imports (skipped for now)
- Import check duration

#### Required Files Checking (5 tests)
- Python project missing .py files
- TypeScript missing tsconfig.json
- Rust missing Cargo.toml
- Go missing go.mod
- Valid projects pass

#### CLI Integration (3 tests)
- CLI with valid project
- CLI with invalid project
- CLI exit codes

#### Edge Cases (2 tests)
- Very large project (100+ files)
- Unicode filenames

**Fixtures:**
```python
@pytest.fixture
def tmp_python_project(tmp_path):
    """Create temporary Python project"""
    (tmp_path / "main.py").write_text("print('hello')")
    return tmp_path

@pytest.fixture
def tmp_invalid_python_project(tmp_path):
    """Create Python project with syntax errors"""
    (tmp_path / "bad.py").write_text("def broken(\nprint('unclosed')")
    return tmp_path
```

**Mocking strategy:**
- Mock `subprocess.run` for language compilers
- Use real file creation (tmp_path)
- Mock timeouts for speed

---

### Module 2: test_validate_architecture.py

**Purpose:** Test architecture validation (Architect phase back pressure)

**Functions to test:**
1. `validate_architecture()` - Main validator
2. `check_test_strategy_exists()` - Test section detection
3. `check_file_structure_specified()` - File tree detection
4. `find_duplicate_file_paths()` - Duplicate detection
5. `check_implementation_steps_exist()` - Steps detection

**Test categories (25-30 tests):**

#### Main Validation (5 tests)
- Valid complete architecture
- Missing architecture file
- Empty architecture file
- Malformed architecture (not markdown)
- Architecture with all checks passing

#### Test Strategy Checking (6 tests)
- Architecture with "Testing Requirements" section
- Architecture with "Test Plan" section
- Architecture with "Test Strategy" section
- Architecture missing test section (error)
- Test framework mentioned (pytest, jest)
- Test approach specified

#### File Structure Checking (6 tests)
- Architecture with "File Structure" section
- Architecture with "Directory Structure" section
- Architecture with "Project Structure" section
- Architecture missing structure (error)
- Valid file tree format
- Missing structure section (error)

#### Duplicate File Detection (5 tests)
- No duplicates (pass)
- Duplicate file paths (error)
- Case-sensitive duplicates
- Path normalization
- Multiple duplicates reported

#### Implementation Steps (4 tests)
- Architecture with "Implementation Steps"
- Architecture with "Build Plan"
- Missing steps (warning, not error)
- Steps with ordering

#### Edge Cases (3 tests)
- Very large architecture (10KB+)
- Unicode in architecture
- Performance (< 100ms for typical file)

**Fixtures:**
```python
@pytest.fixture
def valid_architecture(tmp_path):
    """Create valid architecture.md"""
    arch = """
# Architecture

## Testing Requirements
- Use pytest
- 90% coverage

## File Structure
```
project/
├── main.py
└── tests/
```

## Implementation Steps
1. Create main.py
2. Write tests
"""
    path = tmp_path / "architecture.md"
    path.write_text(arch)
    return str(path)
```

---

### Module 3: test_validate_tech_stack.py

**Purpose:** Test technology stack validation (Scout phase back pressure)

**Functions to test:**
1. `validate_tech_stack()` - Main validator
2. `extract_tech_stack()` - Parse scout report for tech
3. `check_language_available()` - Check language availability
4. (Additional helper functions from file)

**Test categories (25-30 tests):**

#### Main Validation (5 tests)
- Valid scout report with available tech
- Missing scout report file
- Scout report with unavailable tech
- Scout report with no tech section
- Multiple technologies validated

#### Tech Stack Extraction (8 tests)
- Extract from "Technology Stack" section
- Extract language (Python 3.11+)
- Extract framework (FastAPI)
- Extract database (PostgreSQL)
- Extract runtime (Node.js 18+)
- Multiple technologies in list
- No tech section (skip validation)
- Malformed tech section

#### Language Availability Checking (8 tests)
- Python available (subprocess check)
- Python unavailable (error)
- Python version mismatch (warning)
- Node.js available
- Node.js unavailable
- Rust available (cargo --version)
- Go available (go version)
- Unknown language (skip)

#### Error Handling (4 tests)
- Subprocess timeout
- Subprocess exception
- Permission errors
- Command not found

#### Edge Cases (3 tests)
- Empty scout report
- Very long tech list (20+ items)
- Performance (< 200ms)

**Mocking:**
```python
@pytest.fixture
def mock_subprocess_python_available(monkeypatch):
    """Mock subprocess to return Python as available"""
    def mock_run(cmd, **kwargs):
        result = Mock()
        if 'python' in cmd[0]:
            result.returncode = 0
            result.stdout = "Python 3.11.0"
        return result
    monkeypatch.setattr(subprocess, 'run', mock_run)
```

---

### Module 4: test_cli_entry_point.py

**Purpose:** Test CLI entry point (`cf` command)

**Functions to test:**
1. `main()` - CLI entry point
2. `launch_context_foundry()` - TUI launcher
3. Python version checking (inline in main)
4. Argument parsing

**Test categories (20-25 tests):**

#### Python Version Checking (5 tests)
- Python 3.10 (pass)
- Python 3.11 (pass)
- Python 3.9 (fail with error message)
- Python 3.8 (fail)
- Version check message format

#### Argument Parsing (6 tests)
- --version flag
- --help flag
- No arguments (default: launch TUI)
- Invalid arguments
- Version output format
- Help output format

#### TUI Launch (5 tests)
- Successful TUI launch (mocked)
- Missing dependencies (ImportError)
- Keyboard interrupt handling
- General exception handling
- Error message format

#### Error Messages (4 tests)
- Python version error message
- Missing dependencies error message
- General error message
- Error message includes help URL

#### Edge Cases (3 tests)
- Multiple flags
- Unknown flags
- sys.exit() codes captured

**Mocking:**
```python
@pytest.fixture
def mock_python_39(monkeypatch):
    """Mock Python 3.9 version"""
    import sys
    monkeypatch.setattr(sys, 'version_info', (3, 9, 0))

@pytest.fixture
def mock_missing_tui(monkeypatch):
    """Mock missing TUI dependencies"""
    def mock_import(*args, **kwargs):
        raise ImportError("No module named 'tools.evolution.mission_control'")
    monkeypatch.setitem(__builtins__, '__import__', mock_import)
```

**Special considerations:**
- Use `pytest.raises(SystemExit)` to capture exit codes
- Mock `sys.version_info` for version testing
- Mock TUI import to avoid actual launch

---

### Module 5: test_use_baml_cli.py

**Purpose:** Test BAML integration CLI wrapper

**Functions to test:**
1. `main()` - CLI entry point with subcommands
2. Status command
3. Update-phase command
4. Scout-report command
5. Architecture command
6. Validate-build command

**Test categories (30-35 tests):**

#### Status Command (5 tests)
- BAML available (success)
- BAML unavailable (error with message)
- API key set (reported in output)
- API key not set (reported in output)
- Exit codes (0 for success, 1 for unavailable)

#### Update-Phase Command (8 tests)
- Valid phase update
- Status normalization (lowercase → Capitalized)
- All status values mapped correctly
- Session ID parameter
- Iteration parameter
- JSON output format
- Error handling
- Cache clearing

#### Scout-Report Command (5 tests)
- Successful report generation
- BAML unavailable (graceful fallback message)
- Required arguments
- JSON output
- Error handling

#### Architecture Command (5 tests)
- Successful architecture generation
- JSON parsing for risks array
- BAML unavailable fallback
- Error handling
- Output format

#### Validate-Build Command (4 tests)
- Successful validation
- BAML unavailable fallback
- JSON input parsing
- Error handling

#### Argument Parsing (5 tests)
- No command (shows help)
- Invalid command
- Missing required arguments
- Help flag
- All commands listed

#### Edge Cases (3 tests)
- Unicode in arguments
- Very long task descriptions
- Special characters in session ID

**Mocking:**
```python
@pytest.fixture
def mock_baml_available(monkeypatch):
    """Mock BAML as available"""
    from tools import baml_integration
    monkeypatch.setattr(baml_integration, 'is_baml_available', lambda: True)

@pytest.fixture
def mock_baml_unavailable(monkeypatch):
    """Mock BAML as unavailable"""
    from tools import baml_integration
    monkeypatch.setattr(baml_integration, 'is_baml_available', lambda: False)
    monkeypatch.setattr(baml_integration, 'get_baml_error', lambda: "BAML not installed")
```

---

### Module 6: test_parallel_runner_execution.py

**Purpose:** Test parallel build runner

**Functions to test:**
1. `test_runner()` - Main test function
2. Subprocess spawning
3. Config passing via stdin
4. Output capture
5. Timeout handling

**Test categories (15-20 tests):**

#### Main Runner Function (5 tests)
- Successful run with valid config
- Runner exits with 0 on success
- Runner captures stdout
- Runner captures stderr
- Exit code propagation

#### Config Handling (4 tests)
- Config serialization to JSON
- Config passed via stdin
- Config deserialization in runner
- Invalid config handling

#### Subprocess Management (5 tests)
- Subprocess spawned successfully
- Working directory set correctly
- stdin/stdout/stderr pipes configured
- Timeout handling (30s default)
- Process termination on timeout

#### Output Validation (3 tests)
- stdout captured correctly
- stderr captured correctly
- Output format validation

#### Edge Cases (3 tests)
- Missing runner script
- Permission errors
- Very long output

**Fixtures:**
```python
@pytest.fixture
def test_build_config():
    """Sample build configuration"""
    return {
        "task": "Create a simple Hello World",
        "working_directory": "/tmp/cf-test",
        "project_name": "test-hello",
        "github_repo_name": None,
        "enable_test_loop": False,
        "max_test_iterations": 1
    }
```

---

## Testing Requirements

### Framework & Tools
- **pytest** (already configured)
- **pytest markers:**
  - `@pytest.mark.unit` - Fast unit tests
  - `@pytest.mark.integration` - Tests with filesystem/subprocess
  - `@pytest.mark.tier1` - Critical tests (all Phase 1 tests)
  - `@pytest.mark.slow` - Tests > 1 second

### Test Execution
```bash
# Run all Phase 1 tests
pytest tests/test_integration_pre_check.py tests/test_validate_architecture.py \
       tests/test_validate_tech_stack.py tests/test_cli_entry_point.py \
       tests/test_use_baml_cli.py tests/test_parallel_runner_execution.py

# Run only tier1 critical tests
pytest -m tier1

# Run with coverage
pytest --cov=tools/back_pressure --cov=tools --cov-report=term
```

### Success Criteria
- ✅ All 150-200 tests pass
- ✅ Test execution time < 30 seconds (all tests)
- ✅ Code coverage > 90% for each module
- ✅ No test failures on existing test suite
- ✅ All tests properly marked with pytest markers

## Implementation Steps

### Step 1: Setup Test Infrastructure (15 min)
- Verify pytest installed and working
- Create test file stubs
- Add pytest markers to new tests

### Step 2: Implement test_integration_pre_check.py (60-90 min)
- Create fixtures for temp projects (Python, TypeScript, etc.)
- Test language detection (8 tests)
- Test Python syntax checking (8 tests)
- Test other language checks (10 tests)
- Test import/file checks (9 tests)
- Test CLI and edge cases (5 tests)

### Step 3: Implement test_validate_architecture.py (45-60 min)
- Create fixtures for architecture.md files
- Test main validation (5 tests)
- Test test strategy checking (6 tests)
- Test file structure checking (6 tests)
- Test duplicate detection (5 tests)
- Test implementation steps (4 tests)
- Edge cases (3 tests)

### Step 4: Implement test_validate_tech_stack.py (45-60 min)
- Create fixtures for scout reports
- Mock subprocess for language checks
- Test main validation (5 tests)
- Test tech extraction (8 tests)
- Test language availability (8 tests)
- Error handling + edge cases (7 tests)

### Step 5: Implement test_cli_entry_point.py (30-45 min)
- Mock Python version
- Mock TUI import
- Test version checking (5 tests)
- Test argument parsing (6 tests)
- Test TUI launch (5 tests)
- Test error messages (4 tests)
- Edge cases (3 tests)

### Step 6: Implement test_use_baml_cli.py (45-60 min)
- Mock BAML availability
- Test status command (5 tests)
- Test update-phase (8 tests)
- Test scout-report (5 tests)
- Test architecture (5 tests)
- Test validate-build (4 tests)
- Test argument parsing + edge cases (8 tests)

### Step 7: Implement test_parallel_runner_execution.py (30-45 min)
- Create test config fixtures
- Test main runner (5 tests)
- Test config handling (4 tests)
- Test subprocess management (5 tests)
- Test output validation (3 tests)
- Edge cases (3 tests)

### Step 8: Run All Tests & Verify (15-30 min)
- Execute full test suite
- Check coverage reports
- Fix any failures
- Verify no regressions in existing tests

### Step 9: Create PR (15 min)
- Create feature branch: `self-improvement/test-coverage-critical-paths`
- Commit changes with message template
- Create PR with test results

**Total estimated time:** 4-6 hours

## Edge Cases & Error Handling

### Subprocess Errors
- Timeout: Mock with `subprocess.TimeoutExpired`
- Command not found: Mock with `FileNotFoundError`
- Permission denied: Create test files with no read permission

### Filesystem Errors
- Missing files: `FileNotFoundError`
- Permission errors: Create unreadable files
- Large files: Create files > 1MB

### BAML Availability
- BAML installed: Mock `is_baml_available() → True`
- BAML not installed: Mock `is_baml_available() → False`
- API key set/unset: Mock environment variables

### CLI Testing
- sys.exit(): Use `pytest.raises(SystemExit)`
- stdin/stdout capture: Use `capsys` fixture
- KeyboardInterrupt: Raise in mocked function

## Preventive Measures

### Known Risks (from pattern library)
None applicable - This is a standard testing task.

### Test Isolation
- Use `tmp_path` fixture for all file operations
- Mock subprocess calls to avoid external dependencies
- Clean up after each test (pytest handles automatically with tmp_path)
- No shared state between tests

### Performance
- Target: < 30 seconds for all 150-200 tests
- Mock all subprocess calls
- Use in-memory fixtures where possible
- Mark slow tests (> 1s) with `@pytest.mark.slow`

## Success Metrics

- **Coverage increase:** 67% → 73% (+6 percentage points)
- **Tests created:** 150-200 comprehensive tests
- **Modules covered:** 6 critical path modules
- **Test execution:** < 30 seconds total
- **Code coverage:** > 90% per module
- **Regressions:** 0 (all existing tests still pass)

## Files Modified Summary

**New test files (6):**
1. tests/test_integration_pre_check.py
2. tests/test_validate_architecture.py
3. tests/test_validate_tech_stack.py
4. tests/test_cli_entry_point.py
5. tests/test_use_baml_cli.py
6. tests/test_parallel_runner_execution.py

**No changes to production code** - Tests only!

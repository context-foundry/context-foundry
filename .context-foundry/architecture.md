# Test Architecture Design

## System Architecture Overview

This test suite adds comprehensive coverage for 4 critical untested modules:
1. CLI interface for BAML integration (`use_baml.py`)
2. Modular prompt loading system (`phase_loader.py`)
3. Orchestrator prompt builder (`build_orchestrator_prompt.py`)
4. Prompt cache analyzer (`cache_analysis.py`)

## Complete File Structure

```
tests/
├── test_use_baml_cli.py           # NEW - CLI integration tests
├── prompts/                        # NEW - Prompt system tests
│   ├── __init__.py                # NEW - Empty init
│   ├── test_phase_loader.py       # NEW - Phase loading tests
│   ├── test_build_orchestrator_prompt.py  # NEW - Prompt builder tests
│   └── test_cache_analysis.py     # NEW - Cache analysis tests
└── [existing 58 test files]
```

## Module Specifications

### 1. test_use_baml_cli.py

**Purpose**: Test CLI interface for BAML integration wrapper

**Test Classes**:
- `TestCLIStatus`: Test status command
- `TestCLIUpdatePhase`: Test phase tracking updates
- `TestCLIScoutReport`: Test scout report generation
- `TestCLIArchitecture`: Test architecture generation
- `TestCLIValidateBuild`: Test build validation
- `TestCLIErrorHandling`: Test error cases

**Key Test Cases**:
```python
# Status command
def test_status_baml_available()
def test_status_baml_unavailable()
def test_status_no_api_key()

# Update phase command
def test_update_phase_success()
def test_update_phase_status_normalization()
def test_update_phase_with_iteration()

# Error handling
def test_no_command_shows_help()
def test_invalid_command()
def test_missing_required_args()
```

**Fixtures**:
- `mock_baml_available`: Mock BAML availability checks
- `mock_env_vars`: Mock environment variables
- `cli_runner`: Helper to run CLI commands

**Coverage Target**: >85% of use_baml.py

### 2. test_phase_loader.py

**Purpose**: Test modular phase prompt loading

**Test Classes**:
- `TestPhasePromptLoading`: Test individual phase loading
- `TestPhasePromptCombined`: Test all phases loading
- `TestPhasePromptFlowise`: Test Flowise mode
- `TestPhasePromptErrors`: Test error handling

**Key Test Cases**:
```python
# Basic loading
def test_get_phase_prompt_valid_phase()
def test_get_phase_prompt_all_phases()
def test_list_available_phases()

# Flowise mode
def test_get_phase_prompt_with_flowise()
def test_get_phase_prompt_flowise_unavailable()

# Error cases
def test_get_phase_prompt_invalid_phase()
def test_get_phase_prompt_missing_file()
```

**Fixtures**:
- `phase_files_exist`: Verify phase files present
- `mock_flowise_available`: Mock Flowise extension
- `temp_phase_dir`: Temporary phase files for testing

**Coverage Target**: >90% of phase_loader.py

### 3. test_build_orchestrator_prompt.py

**Purpose**: Test orchestrator prompt building and assembly

**Test Classes**:
- `TestPromptBuilder`: Test prompt construction
- `TestPromptIntegration`: Test full prompt assembly
- `TestPromptCaching`: Test cache directives

**Key Test Cases**:
```python
def test_build_prompt_with_all_phases()
def test_build_prompt_without_flowise()
def test_build_prompt_with_flowise()
def test_prompt_contains_critical_sections()
def test_prompt_length_reasonable()
```

**Fixtures**:
- `expected_sections`: List of required prompt sections
- `prompt_builder`: Builder instance for tests

**Coverage Target**: >80% of build_orchestrator_prompt.py

### 4. test_cache_analysis.py

**Purpose**: Test prompt cache analysis and reporting

**Test Classes**:
- `TestCacheAnalysis`: Test cache analysis functions
- `TestCacheReporting`: Test cache report generation

**Key Test Cases**:
```python
def test_analyze_prompt_cache_usage()
def test_generate_cache_report()
def test_identify_cacheable_sections()
```

**Fixtures**:
- `sample_prompt`: Sample prompt for analysis
- `cache_config`: Cache configuration for testing

**Coverage Target**: >75% of cache_analysis.py

## Testing Strategy

### Unit Testing Approach
1. **Isolated function tests**: Test pure functions independently
2. **Mock external dependencies**: BAML, file I/O, subprocess
3. **Fixture-based setup**: Reusable test data and configurations
4. **Parameterized tests**: Test multiple inputs efficiently

### Integration Testing Approach
1. **Real file loading**: Test actual prompt files exist and load
2. **CLI subprocess tests**: Test actual CLI execution
3. **End-to-end workflows**: Test complete command flows

### Error Handling Tests
1. **Missing files**: Test graceful handling
2. **Invalid inputs**: Test argument validation
3. **BAML unavailable**: Test fallback behavior
4. **Permission errors**: Test file access issues

## Implementation Steps

### Step 1: Create Directory Structure
```bash
mkdir -p tests/prompts
touch tests/prompts/__init__.py
```

### Step 2: Implement test_use_baml_cli.py
1. Import use_baml module
2. Create mock fixtures
3. Write status command tests
4. Write update-phase command tests
5. Write other command tests
6. Write error handling tests

### Step 3: Implement test_phase_loader.py
1. Import phase_loader module
2. Create test fixtures
3. Write basic loading tests
4. Write Flowise mode tests
5. Write error handling tests

### Step 4: Implement test_build_orchestrator_prompt.py
1. Import build_orchestrator_prompt module
2. Write prompt building tests
3. Write integration tests

### Step 5: Implement test_cache_analysis.py
1. Import cache_analysis module
2. Write cache analysis tests
3. Write reporting tests

## Test Execution Plan

### Run Individual Test Files
```bash
pytest tests/test_use_baml_cli.py -v
pytest tests/prompts/test_phase_loader.py -v
pytest tests/prompts/test_build_orchestrator_prompt.py -v
pytest tests/prompts/test_cache_analysis.py -v
```

### Run All New Tests
```bash
pytest tests/test_use_baml_cli.py tests/prompts/ -v
```

### Run With Coverage
```bash
pytest tests/test_use_baml_cli.py tests/prompts/ \
  --cov=tools.use_baml \
  --cov=tools.prompts.phase_loader \
  --cov=tools.prompts.build_orchestrator_prompt \
  --cov=tools.prompts.cache_analysis \
  --cov-report=term-missing
```

### Run All Tests (Verify No Regressions)
```bash
pytest tests/ -v
```

## Success Criteria

### Must Pass
- ✅ All new tests pass
- ✅ All existing tests still pass
- ✅ No import errors
- ✅ No syntax errors

### Coverage Goals
- ✅ use_baml.py: >85% coverage
- ✅ phase_loader.py: >90% coverage
- ✅ build_orchestrator_prompt.py: >80% coverage
- ✅ cache_analysis.py: >75% coverage

### Code Quality
- ✅ Follow existing test patterns
- ✅ Use pytest fixtures appropriately
- ✅ Mock external dependencies
- ✅ Clear, descriptive test names
- ✅ Docstrings for test classes

## Git Workflow

### Branch Creation
```bash
git checkout -b self-improvement/task-995b8dba
```

### Commit Strategy
1. Commit after each test file is complete and passing
2. Descriptive commit messages
3. Final commit with all tests passing

### PR Creation
```bash
git push -u origin self-improvement/task-995b8dba
gh pr create --base main \
  --title "Add comprehensive tests for critical untested paths" \
  --body "Adds test coverage for use_baml.py, phase_loader.py, build_orchestrator_prompt.py, and cache_analysis.py. Improves overall coverage from 25.3% to target >30%."
```

## Risk Mitigation

### Risk 1: Existing Tests Break
**Mitigation**: Run full test suite before committing  
**Rollback**: Easy - just delete new test files

### Risk 2: BAML Integration Issues
**Mitigation**: Mock all BAML calls, test fallback  
**Verification**: Test with and without BAML available

### Risk 3: File Path Issues
**Mitigation**: Use Path objects, test from multiple directories  
**Verification**: Run tests from project root and tests/ directory

### Risk 4: Coverage Not Improving
**Mitigation**: Check coverage after each test file  
**Adjustment**: Add more test cases as needed

## Next Steps

Proceed to Builder phase to implement all test files according to this architecture.

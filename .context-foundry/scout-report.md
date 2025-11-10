# Scout Report: Add Tests for Critical Paths

## Executive Summary

This task focuses on improving test coverage for critical, untested code paths in Context Foundry. Current overall coverage is 25.3%, with several critical files having 0% coverage despite being essential to core functionality. We'll add comprehensive tests for 4 high-priority files that are CLI entry points and prompt building infrastructure.

## Key Requirements

### Primary Objectives
1. **Add CLI tests for tools/use_baml.py** - Critical BAML integration entry point
2. **Add tests for tools/prompts/phase_loader.py** - Modular prompt loading system
3. **Add tests for tools/prompts/build_orchestrator_prompt.py** - Main prompt builder
4. **Add tests for tools/prompts/cache_analysis.py** - Prompt cache analysis

### Success Criteria
- All new tests pass
- Existing tests continue to pass
- Coverage for target files reaches >80%
- Tests follow existing patterns (pytest, mocking, fixtures)

## Technology Stack

**Language**: Python 3.8+  
**Testing Framework**: pytest with pytest-asyncio  
**Mocking**: unittest.mock  
**Coverage**: pytest-cov  

**Dependencies**:
- BAML integration (optional, graceful fallback)
- File I/O for prompt loading
- argparse for CLI testing
- subprocess for integration tests

## Critical Architecture Recommendations

### 1. Test Structure
- Create `tests/test_use_baml_cli.py` for CLI testing
- Create `tests/prompts/` directory for prompt-related tests
- Follow existing test naming: `test_<module>_<aspect>.py`

### 2. Testing Patterns (From Existing Codebase)
```python
# Pattern 1: Path handling with sys.path manipulation
sys.path.insert(0, str(Path(__file__).parent.parent))

# Pattern 2: Mocking BAML availability
@patch('tools.baml_integration.is_baml_available')
def test_with_baml_unavailable(mock_baml):
    mock_baml.return_value = False
    # Test fallback behavior

# Pattern 3: Temporary directories for file tests
@pytest.fixture
def temp_prompt_dir(tmp_path):
    # Create test prompt files
    return tmp_path

# Pattern 4: Subprocess testing for CLI
import subprocess
result = subprocess.run(['python3', 'tools/use_baml.py', 'status'], 
                       capture_output=True, text=True)
assert result.returncode == 0
```

### 3. Mock Strategy
- **Mock BAML**: Test both available and unavailable states
- **Mock file I/O**: Use tmp_path fixture for prompt files
- **Mock subprocess**: For CLI integration tests
- **Real integration**: Test actual file loading where safe

### 4. Coverage Strategy
Focus on:
- ✅ Argument parsing and validation
- ✅ Error handling (missing files, invalid inputs)
- ✅ BAML integration paths (both success and fallback)
- ✅ File loading and path resolution
- ✅ CLI command execution

## Main Challenges and Mitigations

### Challenge 1: BAML Dependency
**Issue**: BAML requires OpenAI API key, may not be available in CI  
**Mitigation**: Mock BAML calls, test fallback behavior  
**Pattern**: Follow test_baml_integration.py patterns

### Challenge 2: File System Dependencies
**Issue**: Prompt loaders read from filesystem  
**Mitigation**: Use pytest tmp_path fixture, create test files  
**Pattern**: Create minimal test prompt files in fixtures

### Challenge 3: CLI Testing Complexity
**Issue**: Testing argparse and subprocess interactions  
**Mitigation**: Unit test argparse separately, integration test with subprocess  
**Pattern**: Test main() function with mocked sys.argv

### Challenge 4: Path Resolution
**Issue**: Relative path handling across different execution contexts  
**Mitigation**: Use Path objects consistently, test from multiple directories  
**Pattern**: Follow existing path resolution in test files

## Testing Approach

### Phase 1: Unit Tests (Core Functions)
1. Test `get_phase_prompt()` with various inputs
2. Test `list_available_phases()`
3. Test argument parsing in main()
4. Test status normalization logic

### Phase 2: Integration Tests (CLI Commands)
1. Test `python3 tools/use_baml.py status`
2. Test `python3 tools/use_baml.py update-phase`
3. Test prompt loading with real files
4. Test error cases (missing files, invalid args)

### Phase 3: Edge Cases
1. Invalid phase identifiers
2. Missing prompt files
3. Flowise mode toggling
4. BAML unavailable scenarios

### Phase 4: Coverage Validation
1. Run pytest with coverage
2. Verify >80% coverage on target files
3. Check for any missed branches

## Timeline Estimate

**Total**: ~45 minutes

- Scout phase: 10 min ✓
- Architect phase: 10 min
- Builder phase: 20 min (write tests)
- Test phase: 5 min (run tests, verify)

## Files to Create

1. `tests/test_use_baml_cli.py` (~200 lines)
2. `tests/prompts/__init__.py` (empty)
3. `tests/prompts/test_phase_loader.py` (~150 lines)
4. `tests/prompts/test_build_orchestrator_prompt.py` (~100 lines)
5. `tests/prompts/test_cache_analysis.py` (~100 lines)

**Total**: ~550 lines of test code

## Risk Assessment

**LOW RISK** - This is a test-only change:
- No production code modifications
- All changes are additive (new test files)
- Existing tests must continue to pass
- Easy to rollback if needed

## Next Steps

Proceed to Architect phase to design the detailed test structure and fixtures.

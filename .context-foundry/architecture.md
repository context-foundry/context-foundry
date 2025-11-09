# Test Coverage Improvement - Architecture

## System Architecture Overview

This enhancement adds comprehensive test coverage for critical paths in Context Foundry, focusing on the MCP server, prompt building system, and utility modules. The architecture follows existing pytest patterns and extends them systematically.

## File Structure

```
tests/
├── test_mcp_server_comprehensive.py     # NEW: 500+ lines
├── test_banner.py                       # NEW: 60 lines
├── test_parallel_runner_unit.py         # NEW: 140 lines
└── prompts/                             # NEW directory
    ├── __init__.py                      # NEW
    ├── test_orchestrator_builder.py     # NEW: 280 lines
    ├── test_phase_loader.py             # NEW: 200 lines
    └── test_cache_analysis.py           # NEW: 220 lines
```

**Total**: ~1,400 lines of new test code across 7 files

## Module Specifications

### 1. test_mcp_server_comprehensive.py (Priority 1 - CRITICAL)

**Purpose**: Comprehensive testing of MCP server functions (947 statements → 70% coverage)

**Structure**:

```python
"""
Comprehensive tests for MCP Server critical paths.

Coverage target: 70% (665 of 947 statements)
Priority: 10/10 - Core MCP functionality
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Mock FastMCP (using existing pattern from test_mcp_server_critical_paths.py)

@pytest.mark.tier1
@pytest.mark.integration
class TestMCPServerStatus:
    """Test context_foundry_status() - lines 299-337"""
    
@pytest.mark.tier1
@pytest.mark.integration  
class TestDelegationSync:
    """Test delegate_to_claude_code() - lines 339-524"""
    
@pytest.mark.tier1
@pytest.mark.integration
class TestDelegationAsync:
    """Test delegate_to_claude_code_async() - lines 526-640"""
    
@pytest.mark.tier1
class TestDelegationResults:
    """Test get_delegation_result() - lines 642-896"""
    
@pytest.mark.tier2
class TestDelegationList:
    """Test list_delegations() - lines 898-995"""
    
@pytest.mark.tier2
class TestDelegationCancel:
    """Test cancel_delegation() - lines 997-1245"""
    
@pytest.mark.tier1
@pytest.mark.slow
class TestDelegationStreaming:
    """Test stream_delegation_output() - lines 1247-1470"""
    
@pytest.mark.tier1
class TestCodebaseDetection:
    """Test _detect_existing_codebase() - lines 1472-1702"""
    
@pytest.mark.tier2
class TestTaskIntent:
    """Test _detect_task_intent() - lines 1704-1734"""
    
@pytest.mark.tier1
@pytest.mark.integration
class TestAutonomousBuild:
    """Test autonomous_build_and_deploy() - lines 2202-2239"""
    
@pytest.mark.tier1
class TestPatternManagement:
    """Test pattern functions - lines 2241-2726"""
    
@pytest.mark.tier2
class TestEvolutionIntegration:
    """Test evolution system integration - lines 2914-3010"""
```

**Test Count**: ~40 test methods
**Mocking Strategy**:
- Mock FastMCP decorators (existing pattern)
- Mock subprocess for delegation
- Mock file I/O for metadata
- Use tempfile for working directories

**Key Test Cases**:
1. **autonomous_build_and_deploy()**: 
   - Test with valid task
   - Test with invalid directory
   - Test with existing codebase detection
   - Test error handling
   
2. **delegate_to_claude_code()**: 
   - Test successful delegation
   - Test timeout handling
   - Test process cleanup
   - Test metadata creation
   
3. **Streaming functions**:
   - Test async iteration
   - Test cancellation
   - Test error conditions

4. **Pattern management**:
   - Test read_global_patterns()
   - Test save_global_patterns()
   - Test merge_project_patterns()
   - Test validation

### 2. tests/prompts/ (Priority 2)

#### test_orchestrator_builder.py

**Purpose**: Test modular orchestrator prompt building

```python
"""
Tests for orchestrator prompt builder.

Coverage target: 60% of build_orchestrator_prompt.py
Priority: 8/10 - Core prompt generation
"""

@pytest.mark.tier2
class TestPromptBuilder:
    """Test build_orchestrator_prompt()"""
    
    def test_build_basic_prompt()
    def test_build_with_flowise()
    def test_build_without_flowise()
    def test_missing_header_fallback()
    def test_missing_phase_files()
    def test_output_file_creation()
    def test_version_injection()
    
@pytest.mark.tier2
class TestPromptValidation:
    """Test prompt content validation"""
    
    def test_all_phases_included()
    def test_phase_order_correct()
    def test_no_duplicate_sections()
```

**Test Count**: ~12 test methods
**Coverage**: 60% of 82 statements (~50 statements)

#### test_phase_loader.py

**Purpose**: Test phase file loading and caching

```python
"""
Tests for phase loader module.

Coverage target: 65% of phase_loader.py
Priority: 7/10 - Prompt assembly
"""

@pytest.mark.tier2
class TestPhaseLoading:
    def test_load_single_phase()
    def test_load_all_phases()
    def test_missing_phase_file()
    def test_malformed_phase_file()
    def test_phase_ordering()
    
@pytest.mark.tier3
class TestPhaseCaching:
    def test_cache_hit()
    def test_cache_invalidation()
```

**Test Count**: ~10 test methods
**Coverage**: 65% of 58 statements (~38 statements)

#### test_cache_analysis.py

**Purpose**: Test coverage cache analysis

```python
"""
Tests for cache analysis module.

Coverage target: 55% of cache_analysis.py
Priority: 6/10 - Analysis tooling
"""

@pytest.mark.tier2
class TestCoverageAnalysis:
    def test_parse_coverage_json()
    def test_identify_gaps()
    def test_prioritize_files()
    def test_generate_report()
    
@pytest.mark.tier3
class TestCacheValidation:
    def test_validate_cache_format()
    def test_detect_stale_cache()
```

**Test Count**: ~8 test methods
**Coverage**: 55% of 133 statements (~73 statements)

### 3. test_banner.py (Priority 3)

**Purpose**: Test banner display utility

```python
"""
Tests for banner display module.

Coverage target: 100% of banner.py
Priority: 5/10 - Simple utility
"""

@pytest.mark.unit
@pytest.mark.tier3
class TestBanner:
    def test_print_banner_default()
    def test_print_banner_custom_version()
    def test_banner_width()
    def test_banner_content()
    def test_banner_no_errors()
```

**Test Count**: ~5 test methods
**Coverage**: 100% of 11 statements

### 4. test_parallel_runner_unit.py (Priority 3)

**Purpose**: Test parallel test execution runner

```python
"""
Tests for parallel test runner.

Coverage target: 80% of test_parallel_runner.py
Priority: 6/10 - Testing infrastructure
"""

@pytest.mark.tier2
@pytest.mark.integration
class TestParallelRunner:
    def test_runner_initialization()
    def test_collect_tests()
    def test_distribute_tests()
    def test_parallel_execution()
    def test_result_aggregation()
    def test_failure_handling()
    def test_timeout_handling()
```

**Test Count**: ~7 test methods
**Coverage**: 80% of 39 statements (~31 statements)

## Implementation Steps

### Phase 1: Setup and Infrastructure (30 min)
1. Create `tests/prompts/` directory
2. Add `__init__.py` files
3. Install pytest-asyncio if needed
4. Verify existing pytest configuration

### Phase 2: MCP Server Tests (3-4 hours)
1. Create test file skeleton with all test classes
2. Implement mock FastMCP pattern
3. Write tier1 tests (autonomous_build, delegation)
4. Write tier2 tests (listing, cancellation)
5. Write integration tests
6. Run coverage, iterate to 70%

### Phase 3: Prompt Building Tests (1.5 hours)
1. Create orchestrator_builder tests
2. Create phase_loader tests
3. Create cache_analysis tests
4. Verify 60% coverage target

### Phase 4: Utility Tests (1 hour)
1. Implement banner tests (simple, 100%)
2. Implement parallel_runner tests
3. Verify coverage targets

### Phase 5: Integration and Validation (1 hour)
1. Run full test suite
2. Generate coverage report
3. Fix any failures
4. Document results

## Testing Requirements

### Test Markers (Use Existing)
- `@pytest.mark.tier1`: Critical paths (MUST PASS)
- `@pytest.mark.tier2`: Important functionality
- `@pytest.mark.tier3`: Nice-to-have coverage
- `@pytest.mark.integration`: Cross-module tests
- `@pytest.mark.unit`: Isolated function tests
- `@pytest.mark.slow`: Tests > 1 second

### Mocking Strategy

**FastMCP Mocking** (from existing pattern):
```python
class MockFastMCP:
    def tool(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
```

**File System Mocking**:
```python
@pytest.fixture
def temp_working_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
```

**Subprocess Mocking**:
```python
@patch('subprocess.Popen')
def test_delegation(mock_popen):
    mock_process = Mock()
    mock_process.poll.return_value = 0
    mock_popen.return_value = mock_process
```

## Success Criteria

### Minimum Acceptance Criteria
- [ ] All 72+ new test methods pass
- [ ] No existing tests broken
- [ ] Overall coverage: 25.3% → 45%
- [ ] MCP server: 0% → 50%
- [ ] Prompt building: 0% → 40%
- [ ] All tier1 tests pass

### Target Criteria
- [ ] Overall coverage: 25.3% → 60%
- [ ] MCP server: 0% → 70%
- [ ] Prompt building: 0% → 60%
- [ ] Banner: 0% → 100%
- [ ] Parallel runner: 0% → 80%
- [ ] Test execution time < 30 seconds (excluding slow tests)

### Documentation Deliverables
- [ ] Coverage report: `.context-foundry/coverage-analysis-report.md`
- [ ] Test results: `.context-foundry/test-final-report.md`
- [ ] Architecture doc (this file)
- [ ] Updated pytest.ini if needed

## Risk Mitigation

### Risk 1: Tests Reveal Bugs
**Mitigation**: Document bugs in `.context-foundry/bugs-found.md`, fix critical ones only

### Risk 2: Async Test Complexity
**Mitigation**: Use existing async patterns from evolution tests, install pytest-asyncio

### Risk 3: Mocking Challenges
**Mitigation**: Follow existing mock patterns, use MagicMock for complex objects

### Risk 4: Time Overrun
**Mitigation**: Prioritize MCP server (tier1), skip TUI/livestream if time constrained

## Dependencies

### Required Packages
- pytest (already installed)
- pytest-cov (already installed)
- pytest-asyncio (check/install)
- pytest-mock (check/install)

### Installation Check
```bash
source .venv-test/bin/activate
pip list | grep pytest
# If missing: pip install pytest-asyncio pytest-mock
```

## Test Execution Plan

### Run New Tests Only
```bash
pytest tests/test_mcp_server_comprehensive.py -v
pytest tests/prompts/ -v
pytest tests/test_banner.py -v
pytest tests/test_parallel_runner_unit.py -v
```

### Run with Coverage
```bash
pytest tests/test_mcp_server_comprehensive.py \
  --cov=tools/mcp_server \
  --cov-report=term \
  --cov-report=html
```

### Run All Tests
```bash
pytest tests/ -v --tb=short --maxfail=5
```

### Generate Final Coverage
```bash
pytest --cov=tools --cov-report=json --cov-report=html --cov-report=term
```

## Validation Checklist

- [ ] All test files created
- [ ] All tests pass locally
- [ ] Coverage report generated
- [ ] Coverage targets met
- [ ] No existing tests broken
- [ ] Test execution time acceptable
- [ ] Documentation complete
- [ ] Code follows existing patterns
- [ ] Markers applied correctly
- [ ] Async tests use pytest-asyncio

## Next Steps After Implementation

1. Create PR with branch: `self-improvement/task-a75b50cb`
2. Include coverage before/after metrics
3. Document any bugs found
4. Update evolution system with learnings
5. Celebrate improved test coverage! 🎉

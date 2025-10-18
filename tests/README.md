# Context Foundry - Test Suite Documentation

## Overview

This directory contains comprehensive unit tests for the Context Foundry project, focusing on critical functionality with high code coverage and thorough edge case testing.

## Test Organization

### Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and test configuration
├── test_context_manager.py        # Context management tests (42 tests)
├── test_cost_tracker.py          # Cost tracking tests (32 tests)
├── test_code_extraction_fix.py   # Code extraction regex tests (existing)
├── test_github_provider.py       # GitHub provider tests (existing)
└── test_zai_provider.py          # Z.ai provider tests (existing)
```

### Test Markers

Tests are organized with pytest markers for selective execution:

- `@pytest.mark.unit` - Unit tests for individual functions/classes
- `@pytest.mark.integration` - Integration tests across modules
- `@pytest.mark.tier1` - **Critical functionality tests (MUST PASS)**
- `@pytest.mark.tier2` - Important functionality tests
- `@pytest.mark.tier3` - Nice-to-have tests
- `@pytest.mark.slow` - Tests that take significant time
- `@pytest.mark.requires_api` - Tests requiring external API calls (skipped by default)
- `@pytest.mark.requires_db` - Tests requiring database setup

## Running Tests

### Run All Tests

```bash
python3 -m pytest tests/ -v
```

### Run Specific Test Modules

```bash
# Run only ContextManager tests
python3 -m pytest tests/test_context_manager.py -v

# Run only CostTracker tests
python3 -m pytest tests/test_cost_tracker.py -v
```

### Run by Marker

```bash
# Run only Tier 1 critical tests
python3 -m pytest -m tier1

# Run only unit tests
python3 -m pytest -m unit

# Run integration tests
python3 -m pytest -m integration
```

### Run with Coverage (requires pytest-cov)

```bash
# Install pytest-cov first
pip install pytest-cov

# Run with coverage
python3 -m pytest --cov=ace --cov=foundry --cov=workflows \
  --cov-report=html --cov-report=term-missing tests/
```

## Test Coverage Summary

### ContextManager Tests (test_context_manager.py)

**Total Tests: 42** | **Status: ✅ All Passing**

#### Test Classes:
1. **TestContextManagerInit** (3 tests)
   - Initialization with checkpoint directory
   - Default checkpoint paths
   - Loading existing checkpoints

2. **TestTrackInteraction** (4 tests)
   - Basic interaction tracking
   - Multiple interaction accumulation
   - Content importance by type
   - Metadata preservation

3. **TestGetUsage** (3 tests)
   - Empty context metrics
   - Percentage calculation
   - Threshold detection

4. **TestShouldCompact** (4 tests)
   - Below threshold (no compaction)
   - Standard threshold (40%)
   - Critical threshold (70%)
   - Exact threshold boundaries

5. **TestEmergencyStop** (3 tests)
   - Below emergency limit
   - Hard limit at 80%
   - Failing compaction detection

6. **TestBasicCompaction** (3 tests)
   - High-priority content retention
   - 25% target achievement
   - Critical content preservation

7. **TestCompact** (5 tests)
   - Compaction without smart compactor
   - Compaction with smart compactor
   - Fallback to basic compaction
   - Skipping below threshold
   - Exception handling

8. **TestCalculateImportance** (4 tests)
   - Content type scoring
   - Keyword boost
   - Length penalty
   - Maximum score of 1.0

9. **TestCheckpointRestore** (4 tests)
   - Checkpoint save state
   - Restore from checkpoint
   - Nonexistent checkpoint handling
   - Auto-checkpoint every 5 messages

10. **TestGetInsights** (3 tests)
    - Insights structure
    - Content breakdown by type
    - Health status calculation

11. **TestContextManagerIntegration** (2 tests)
    - Full workflow: track → compact → checkpoint
    - Checkpoint/restore state preservation

12. **TestEdgeCases** (4 tests)
    - Empty tracked content
    - Zero tokens
    - Invalid content types
    - Corrupted checkpoint files

### CostTracker Tests (test_cost_tracker.py)

**Total Tests: 32** | **Status: ✅ All Passing**

#### Test Classes:
1. **TestPhaseUsage** (3 tests)
   - Dataclass creation
   - Total tokens property
   - Default values

2. **TestCostTrackerInit** (2 tests)
   - Default database initialization
   - Custom database injection

3. **TestTrackUsage** (7 tests)
   - Basic usage tracking
   - Cost calculation accuracy
   - Multi-call accumulation
   - Multiple phase tracking
   - Missing pricing handling
   - Fallback pricing mechanism
   - Call history recording

4. **TestCostRetrieval** (5 tests)
   - Get phase cost (existing)
   - Get phase cost (nonexistent)
   - Total cost single phase
   - Total cost multiple phases
   - Empty cost

5. **TestTokenRetrieval** (2 tests)
   - Total tokens single phase
   - Total tokens multiple phases

6. **TestGetSummary** (3 tests)
   - Summary structure
   - Phase details
   - Multiple phases

7. **TestFormatSummary** (3 tests)
   - Verbose formatting
   - Compact formatting
   - Empty summary

8. **TestExportJson** (3 tests)
   - Export structure
   - Phase usage details
   - Call history

9. **TestCostTrackerIntegration** (1 test)
   - Full workflow with multiple providers

10. **TestEdgeCases** (3 tests)
    - Zero tokens
    - Large token counts (10M+)
    - Precision with small costs

## Test Fixtures (conftest.py)

### Environment Fixtures
- `clean_env` - Clean environment with test API keys
- `temp_project_dir` - Temporary project directory structure

### Database Fixtures
- `in_memory_db` - In-memory SQLite database for testing

### Model & Pricing Fixtures
- `sample_model` - Single Model instance
- `sample_models` - Multiple Model instances
- `sample_pricing` - Single ModelPricing instance
- `sample_pricing_dict` - Multiple ModelPricing instances
- `sample_provider_response` - Sample ProviderResponse

### Context Manager Fixtures
- `sample_content_item` - Single ContentItem
- `sample_content_items` - Multiple ContentItem instances
- `sample_context_metrics` - ContextMetrics instance

### Mock Provider Fixtures
- `mock_anthropic_client` - Mocked Anthropic API client
- `mock_openai_client` - Mocked OpenAI API client

### File System Fixtures
- `sample_python_file` - Sample .py file for testing
- `sample_test_file` - Sample test file

### Checkpoint Fixtures
- `sample_checkpoint_data` - Sample checkpoint data structure

### Utility Functions
- `assert_valid_cost(cost, min_val, max_val)` - Validate cost values
- `assert_valid_percentage(pct, min_val, max_val)` - Validate percentages

## Testing Best Practices Used

### 1. AAA Pattern (Arrange, Act, Assert)
Every test follows the Arrange-Act-Assert pattern for clarity:

```python
def test_example(self):
    # Arrange
    manager = ContextManager("test_session", tmp_path / "checkpoints")

    # Act
    result = manager.track_interaction(...)

    # Assert
    assert result.total_tokens == expected_value
```

### 2. Descriptive Test Names
Test names clearly describe what they test:

```python
def test_compact_smart_fails_fallback_to_basic(self):
    """Test fallback to basic compaction when smart compactor fails."""
```

### 3. Comprehensive Edge Cases
- **Empty inputs**: Zero tokens, empty lists, etc.
- **Boundary values**: Exact threshold values (39.9% vs 40.0%)
- **Large inputs**: 10M+ tokens
- **Error conditions**: Missing pricing, corrupted files
- **Precision**: Floating-point arithmetic validation

### 4. Isolation with Mocking
- Mock external dependencies (API clients, databases)
- Use temporary directories for file operations
- Avoid side effects between tests

### 5. Fixtures for Reusability
- Shared test data via fixtures
- Consistent test setup
- Reduced code duplication

## Key Testing Achievements

### ✅ Comprehensive Coverage
- **74 unit tests** covering critical functionality
- **10+ edge cases** per module
- **Multiple integration scenarios**

### ✅ Real-World Scenarios
- Multi-provider cost tracking
- Context compaction workflows
- Checkpoint/restore cycles
- Fallback mechanisms

### ✅ Error Handling
- API failures
- Missing pricing data
- Corrupted checkpoint files
- Provider registry errors

### ✅ Precision Validation
- Cost calculations validated to 0.01 precision
- Token counting accuracy
- Percentage calculations
- Floating-point edge cases

## Test Statistics

| Module | Test Classes | Total Tests | Status |
|--------|-------------|-------------|---------|
| ContextManager | 12 | 42 | ✅ Passing |
| CostTracker | 10 | 32 | ✅ Passing |
| **TOTAL** | **22** | **74** | **✅ 100%** |

## Adding New Tests

### Template for New Test File

```python
#!/usr/bin/env python3
"""
Comprehensive unit tests for [ModuleName].

Tests cover:
- [Feature 1]
- [Feature 2]
- Edge cases and error handling
"""

import pytest
from unittest.mock import Mock, MagicMock

from ace.module_name import ClassName


@pytest.mark.unit
@pytest.mark.tier1
class TestClassName:
    """Test [ClassName] functionality."""

    def test_feature_name(self, tmp_path):
        """Test [specific feature]."""
        # Arrange
        instance = ClassName(param="value")

        # Act
        result = instance.method()

        # Assert
        assert result == expected_value
```

### Adding New Fixtures

Add to `tests/conftest.py`:

```python
@pytest.fixture
def my_fixture():
    """Provide [description]."""
    return SomeObject(...)
```

## Continuous Integration

For CI/CD pipelines, use:

```bash
# Run all tests with strict mode
python3 -m pytest tests/ -v --strict-markers --maxfail=5

# Run only Tier 1 critical tests
python3 -m pytest -m tier1 --strict-markers
```

## Future Test Additions

### Tier 1 Priority (Critical)
- ✅ ContextManager (42 tests)
- ✅ CostTracker (32 tests)
- 🔲 PricingDatabase (planned: 25+ tests)
- 🔲 BaseProvider & AnthropicProvider (planned: 20+ tests)
- 🔲 ParallelScoutCoordinator (planned: 15+ tests)
- 🔲 ParallelBuilderCoordinator (planned: 15+ tests)

### Tier 2 Priority (Important)
- 🔲 SmartCompactor (planned: 30+ tests)
- 🔲 PatternLibrary (planned: 35+ tests)
- 🔲 AIClient (planned: 15+ tests)
- 🔲 BlueprintManager (planned: 20+ tests)
- 🔲 CheckpointManager (planned: 15+ tests)

### Tier 3 Priority (Nice-to-have)
- 🔲 LeadOrchestrator
- 🔲 PatternExtractor
- 🔲 ConfigManager
- 🔲 FileMapper
- 🔲 ProviderRegistry

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError`
```bash
# Solution: Ensure you're running from project root
cd /path/to/context-foundry
python3 -m pytest tests/
```

**Issue**: `NameError: name 'datetime' is not defined`
```python
# Solution: Add import in conftest.py
from datetime import datetime
```

**Issue**: Marker not found error
```ini
# Solution: Ensure pytest.ini has markers section
[pytest]
markers =
    unit: Unit tests
    tier1: Critical tests
```

## Contributing

When adding new tests:

1. **Follow the AAA pattern** (Arrange, Act, Assert)
2. **Use descriptive names** that explain what's being tested
3. **Add appropriate markers** (@pytest.mark.unit, @pytest.mark.tier1, etc.)
4. **Test edge cases** and error conditions
5. **Use fixtures** from conftest.py when possible
6. **Add docstrings** explaining what the test validates
7. **Ensure tests are isolated** and don't depend on external state

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest markers](https://docs.pytest.org/en/stable/mark.html)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)

---

**Last Updated**: 2024-10-18
**Test Suite Version**: 1.0.0
**Total Tests**: 74
**Pass Rate**: 100%
**Coverage**: ~85% (ContextManager, CostTracker)

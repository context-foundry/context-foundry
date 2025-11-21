# Testing Documentation

> Comprehensive guide to testing the Flowise Extension for Context Foundry

---

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Test Categories](#test-categories)
- [Adding New Tests](#adding-new-tests)
- [Test Fixtures](#test-fixtures)
- [Workflow Validation](#workflow-validation)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Flowise Extension maintains 100% test coverage with 74 comprehensive tests across 5 test modules. Tests are written using Python's built-in `unittest` framework with `pytest` as the recommended test runner.

### Quick Stats

| Metric | Value |
|--------|-------|
| Total Tests | 74 |
| Test Modules | 5 |
| Coverage | 100% |
| Execution Time | ~0.32s |
| Framework | unittest / pytest |

---

## Test Structure

```
tests/
├── __init__.py
├── test_analyzer.py          # Template analysis tests (15 tests)
├── test_bootstrap_integration.py  # Pattern bootstrap tests (14 tests)
├── test_detector.py          # Flow detection tests (14 tests)
├── test_loader.py            # Extension loading tests (17 tests)
├── test_patterns.py          # Pattern validation tests (14 tests)
└── fixtures/
    ├── supervisor_multi_agent.json    # Multi-agent flow fixture
    ├── basic_rag_flow.json            # RAG flow fixture
    ├── simple_chatbot.json            # Chatbot fixture
    ├── workflow_with_tools.json       # Tool-enabled workflow
    └── invalid_json.json              # Invalid JSON for error testing
```

---

## Running Tests

### Basic Test Execution

```bash
# Run all tests with unittest
python3 -m unittest discover tests/

# Run with verbose output
python3 -m unittest discover tests/ -v
```

### Using pytest (Recommended)

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run with short traceback
python3 -m pytest tests/ -v --tb=short

# Run specific test file
python3 -m pytest tests/test_detector.py -v

# Run specific test class
python3 -m pytest tests/test_detector.py::TestFlowiseDetector -v

# Run specific test method
python3 -m pytest tests/test_detector.py::TestFlowiseDetector::test_detect_valid_multi_agent_flow -v

# Run tests matching a pattern
python3 -m pytest tests/ -v -k "agent"
```

### Advanced Options

```bash
# Run with coverage report
python3 -m pytest tests/ -v --cov=. --cov-report=html

# Run only failing tests from last run
python3 -m pytest tests/ --lf

# Stop on first failure
python3 -m pytest tests/ -x

# Run tests in parallel (requires pytest-xdist)
python3 -m pytest tests/ -n auto
```

---

## Test Coverage

### Coverage by Module

| Test File | Module Tested | Tests | Coverage |
|-----------|---------------|-------|----------|
| test_analyzer.py | analyzer.py | 15 | 100% |
| test_bootstrap_integration.py | Pattern bootstrap | 14 | 100% |
| test_detector.py | detector.py | 14 | 100% |
| test_loader.py | extensions_loader.py | 17 | 100% |
| test_patterns.py | patterns/*.json | 14 | 100% |

### Coverage Report

To generate a detailed coverage report:

```bash
python3 -m pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

---

## Test Categories

### 1. Unit Tests (`test_detector.py`)

Test individual detection functions in isolation.

**Test Cases**:

```python
class TestFlowiseDetector(unittest.TestCase):
    def test_detect_valid_multi_agent_flow(self):
        """Verify detection of multi-agent Flowise flow"""

    def test_detect_valid_rag_flow(self):
        """Verify detection of RAG flow type"""

    def test_detect_valid_chatbot(self):
        """Verify detection of chatbot flow"""

    def test_reject_invalid_json(self):
        """Verify rejection of non-Flowise JSON"""

    def test_reject_missing_nodes(self):
        """Verify rejection of JSON without nodes array"""

    def test_calculate_complexity_simple(self):
        """Test complexity calculation for simple flows"""

    def test_calculate_complexity_complex(self):
        """Test complexity calculation for complex flows"""

    def test_classify_flow_type_multi_agent(self):
        """Test flow type classification"""

    def test_scan_directory_finds_json(self):
        """Test directory scanning for JSON files"""

    def test_scan_directory_empty(self):
        """Test scanning empty directory"""
```

### 2. Analyzer Tests (`test_analyzer.py`)

Test template analysis functionality.

**Test Cases**:

```python
class TestTemplateAnalyzer(unittest.TestCase):
    def test_analyze_template_basic(self):
        """Analyze basic template structure"""

    def test_analyze_template_with_tools(self):
        """Analyze template with tool configurations"""

    def test_extract_node_patterns(self):
        """Extract patterns from nodes"""

    def test_extract_connection_patterns(self):
        """Extract connection patterns from edges"""

    def test_analyze_directory(self):
        """Analyze entire directory of templates"""

    def test_export_patterns_json(self):
        """Export patterns to JSON file"""

    def test_handle_invalid_template(self):
        """Handle malformed template gracefully"""
```

### 3. Loader Tests (`test_loader.py`)

Test extension loading and graceful degradation.

**Test Cases**:

```python
class TestExtensionsLoader(unittest.TestCase):
    def test_load_extension_detectors_success(self):
        """Load detectors when extension exists"""

    def test_load_extension_detectors_missing(self):
        """Return None when extension missing"""

    def test_load_extension_patterns_success(self):
        """Load patterns from extension"""

    def test_load_extension_patterns_missing(self):
        """Return None when patterns missing"""

    def test_get_extension_prompt_scout(self):
        """Get Scout phase prompt"""

    def test_get_extension_prompt_architect(self):
        """Get Architect phase prompt"""

    def test_extension_exists_true(self):
        """Check extension existence - positive"""

    def test_extension_exists_false(self):
        """Check extension existence - negative"""
```

### 4. Pattern Tests (`test_patterns.py`)

Validate pattern library structure and content.

**Test Cases**:

```python
class TestPatternLibrary(unittest.TestCase):
    def test_patterns_json_valid(self):
        """Verify pattern JSON is valid"""

    def test_all_patterns_have_required_fields(self):
        """Each pattern has id, category, description"""

    def test_pattern_ids_unique(self):
        """All pattern IDs are unique"""

    def test_workflow_patterns_count(self):
        """Correct number of workflow patterns"""

    def test_issue_patterns_count(self):
        """Correct number of issue patterns"""

    def test_pattern_categories_valid(self):
        """All patterns have valid categories"""

    def test_issue_severity_levels(self):
        """Issues have valid severity levels"""
```

### 5. Bootstrap Integration Tests (`test_bootstrap_integration.py`)

Test pattern loading into Context Codex.

**Test Cases**:

```python
class TestBootstrapIntegration(unittest.TestCase):
    def test_bootstrap_patterns_load(self):
        """Patterns load into Codex successfully"""

    def test_bootstrap_idempotent(self):
        """Bootstrap can run multiple times safely"""

    def test_patterns_searchable(self):
        """Patterns are searchable in Codex"""

    def test_pattern_retrieval_by_id(self):
        """Retrieve specific pattern by ID"""

    def test_issues_searchable(self):
        """Issues are searchable in Codex"""
```

---

## Adding New Tests

### Step 1: Create Test File

```python
# tests/test_new_feature.py
import unittest
from pathlib import Path

class TestNewFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.fixtures_dir = Path(__file__).parent / 'fixtures'

    def setUp(self):
        """Set up before each test"""
        pass

    def tearDown(self):
        """Clean up after each test"""
        pass

    def test_feature_basic(self):
        """Test basic functionality"""
        # Arrange
        input_data = {'key': 'value'}

        # Act
        result = new_feature(input_data)

        # Assert
        self.assertEqual(result, expected_value)

    def test_feature_edge_case(self):
        """Test edge case handling"""
        pass

    def test_feature_error_handling(self):
        """Test error conditions"""
        with self.assertRaises(ValueError):
            new_feature(invalid_input)

if __name__ == '__main__':
    unittest.main()
```

### Step 2: Add Test Fixtures

```bash
# Create fixture file
echo '{"nodes": [], "edges": []}' > tests/fixtures/new_fixture.json
```

### Step 3: Run New Tests

```bash
python3 -m pytest tests/test_new_feature.py -v
```

### Test Naming Conventions

- Test files: `test_<module>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<functionality>_<scenario>`

---

## Test Fixtures

### Available Fixtures

| Fixture | Description | Use Case |
|---------|-------------|----------|
| `supervisor_multi_agent.json` | Complex multi-agent flow | Multi-agent detection |
| `basic_rag_flow.json` | RAG workflow | RAG detection |
| `simple_chatbot.json` | Basic chatbot | Chatbot detection |
| `workflow_with_tools.json` | Tool-enabled flow | Tool detection |
| `invalid_json.json` | Malformed JSON | Error handling |

### Creating New Fixtures

1. Export workflow from Flowise
2. Minimize JSON (remove unnecessary fields)
3. Place in `tests/fixtures/`
4. Reference in test setup

```python
def setUp(self):
    self.fixture_path = self.fixtures_dir / 'new_fixture.json'
    with open(self.fixture_path) as f:
        self.fixture_data = json.load(f)
```

---

## Workflow Validation

### Running Workflow Validation

```bash
python3 validate_workflow.py path/to/workflow.json
```

### Validation Output

```
Validating Flowise workflow: workflow.json
   Nodes: 8, Edges: 7

======================================================================
VALIDATION SUMMARY
======================================================================

CRITICAL FAILURES (0):
  (none)

WARNINGS (1):
  Some nodes missing optional fields

BUILD READY - Workflow passed all critical checks
```

### Validation Patterns Checked

| Pattern # | Name | Severity |
|-----------|------|----------|
| 1 | Meta-descriptions | CRITICAL |
| 2 | Missing agent nodes | CRITICAL |
| 3 | Separate config files | CRITICAL |
| 4 | Disconnected nodes | HIGH |
| 5 | Phantom tool references | HIGH |
| 6 | Incorrect tool structure | CRITICAL |
| 7 | Missing router scenarios | HIGH |
| 8 | Missing inputParams | CRITICAL |
| 9 | Missing Mermaid diagram | MEDIUM |
| 10 | HIL gate invalid inputParams | CRITICAL |
| 11 | HIL gate blank screen | CRITICAL |
| 12 | agentMessages array | HIGH |
| 13 | agentModel missing nested field | CRITICAL |
| 14 | Node type mismatch | CRITICAL |

---

## Continuous Integration

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running tests..."
python3 -m pytest tests/ -v --tb=short

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

### CI Configuration (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install pytest
      - name: Run tests
        run: python -m pytest tests/ -v --tb=short
```

---

## Troubleshooting

### Common Issues

#### Tests Can't Find Modules

**Symptom**: `ModuleNotFoundError: No module named 'detector'`

**Solution**: Run tests from the extension root directory:
```bash
cd /path/to/flowise-extension
python3 -m pytest tests/ -v
```

#### Fixture Not Found

**Symptom**: `FileNotFoundError: fixture.json`

**Solution**: Verify fixture path in test:
```python
fixtures_dir = Path(__file__).parent / 'fixtures'
fixture_path = fixtures_dir / 'fixture.json'
```

#### Python Version Mismatch

**Symptom**: Syntax errors or missing features

**Solution**: Ensure Python 3.10+:
```bash
python3 --version
# Python 3.10.0 or higher
```

#### Test Isolation Issues

**Symptom**: Tests pass individually but fail together

**Solution**: Use `setUp` and `tearDown` properly:
```python
def setUp(self):
    self.temp_dir = tempfile.mkdtemp()

def tearDown(self):
    shutil.rmtree(self.temp_dir)
```

### Debug Mode

Run tests with verbose debugging:

```bash
# Maximum verbosity
python3 -m pytest tests/ -vvv

# Show local variables on failure
python3 -m pytest tests/ --showlocals

# Drop into debugger on failure
python3 -m pytest tests/ --pdb
```

---

## Test Metrics Goals

### Current Status

- **74/74 tests passing** (100%)
- **0.32s execution time**
- **100% code coverage**

### Quality Targets

- All new features require tests
- Test execution under 1 second
- Maintain 100% coverage
- Zero flaky tests

---

## References

- [pytest documentation](https://docs.pytest.org/)
- [unittest documentation](https://docs.python.org/3/library/unittest.html)
- [FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) - Validation patterns
- [README.md](../README.md) - Project overview

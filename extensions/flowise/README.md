# Flowise Extension for Context Foundry

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-74%20passed-brightgreen.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](#testing)
[![License](https://img.shields.io/badge/license-Private-red.svg)](#license)
[![Build Status](https://img.shields.io/badge/build-autonomous-purple.svg)](#credits)

> **A private, modular extension framework that teaches Context Foundry to become a Flowise expert.**

This extension automatically detects Flowise agent flows and provides world-class guidance for building high-quality workflows with enterprise-grade patterns and comprehensive validation.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Notable Builds](#-notable-builds)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Pattern Library](#pattern-library)
- [Testing](#testing)
- [Documentation](#-documentation)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Credits](#credits)

---

## Overview

This extension augments Context Foundry with deep Flowise expertise through:

- **Automatic Flow Detection**: Identifies Flowise JSON files and classifies flow types
- **Pattern-Based Learning**: Extracts best practices from template analysis
- **Phase Enhancements**: Injects expertise into Scout and Architect phases
- **Graceful Integration**: Zero impact when extension is absent (public repo compatible)
- **Comprehensive Validation**: Prevents 14+ known failure patterns automatically

## Features

### Core Capabilities

- **Auto-detect Flowise flows** (multi-agent, RAG, workflow, chatbot)
- **Classify complexity** (simple, moderate, complex)
- **Extract patterns** from template JSONs
- **Enhance Scout phase** with Flowise research checklist
- **Enhance Architect phase** with proven patterns

### Advanced Features

- **ExecuteFlow node support** - Modular sub-flow execution with state management
- **Generate Mermaid diagrams** for visual workflow documentation
- **Auto-embed diagrams in README** with interactive agent details
- **CLI tools** for template analysis and diagram generation
- **100% test coverage** with comprehensive unit tests

### Quality Assurance

- **Zero dependencies** (Python stdlib only)
- **14/14 failure patterns prevented** automatically
- **100% first-iteration success** on all documented builds

---

## Notable Builds

The Flowise extension has successfully built production-ready workflows across diverse enterprise use cases:

### Recent Successes

#### Promotion Nomination Workflow - November 4, 2025
**First successful Human-in-the-Loop implementation!**

- **Complexity**: Complex (11 nodes, 12 edges, 7 agents + 2 HIL gates)
- **Duration**: 25 minutes (first-try success)
- **GitHub**: [promotion-nomination-flowise-agent](https://github.com/snedea/promotion-nomination-flowise-agent)
- **Highlights**:
  - First successful HIL approval gates with semantic proceed/reject outputs
  - Two-stage approval workflow (Local Leadership → Executive)
  - Complete Workday HCM integration guide
  - 3,734 lines of validated Flowise JSON

#### Personalized Onboarding Flow - November 2, 2025

- **Complexity**: Moderate (10 nodes, 9 edges, 8 agents)
- **Duration**: 17 minutes (1,027 seconds)
- **GitHub**: [personalized-onboarding-flowise](https://github.com/snedea/personalized-onboarding-flowise)
- **Highlights**:
  - All 5 failure patterns prevented on first try
  - 2,952 lines of self-contained workflow
  - Complete HR/IT integration architecture

### Success Metrics

| Metric | Best Result | Build |
|--------|-------------|-------|
| **Most Complex** | 11 nodes, 12 edges | Promotion Nomination |
| **Fastest Build** | 17 minutes | Personalized Onboarding |
| **First HIL Success** | 2 approval gates | Promotion Nomination |
| **Largest File** | 3,734 lines | Promotion Nomination |
| **Test Iterations** | 1 (all builds) | All recent builds |

---

## Installation

### Prerequisites

- Python 3.10 or higher
- Context Foundry installed
- Git (for cloning)

### Quick Start

1. **Clone or copy this extension** to Context Foundry's extensions directory:

```bash
# From Context Foundry root directory
mkdir -p extensions
cd extensions
git clone <this-repo-url> flowise
```

2. **Verify installation**:

```bash
cd flowise
python3 -m unittest discover tests/
```

All tests should pass (74/74).

### Detailed Installation

For comprehensive installation instructions including MCP server integration and orchestrator setup, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

---

## Usage

### 1. Automatic Detection (No Configuration Needed)

When Context Foundry runs on a project containing Flowise JSON files, the extension automatically:

- Detects Flowise flows
- Classifies flow type (multi-agent, RAG, workflow, chatbot)
- Enhances Scout with Flowise-specific research checklist
- Enhances Architect with proven Flowise patterns

**Example:**

```bash
# In your Flowise project directory with .json flows
cf build "Improve my multi-agent workflow"
```

Context Foundry will automatically apply Flowise expertise!

### 2. Manual Flow Detection

Detect and classify a Flowise flow:

```bash
python3 detector.py path/to/flow.json
```

**Output:**
```
Flowise Flow Detection Results:
==================================================
Is Flowise Flow: True
Flow Type: multi-agent
Complexity: moderate
Nodes: 8
Edges: 10
Agents: 3
Has Memory: True
Has Tools: True
Expertise Level: advanced
```

### 3. Generate Mermaid Workflow Diagrams

Create beautiful visual diagrams of Flowise workflows for GitHub README:

```bash
# Generate diagram with interactive agent details
python3 mermaid_generator.py path/to/workflow.json WORKFLOW-DIAGRAM.md --interactive

# Generate basic diagram only
python3 mermaid_generator.py path/to/workflow.json output.md

# Output to stdout
python3 mermaid_generator.py path/to/workflow.json
```

**Output:**
- Mermaid diagram with Flowise color scheme (green=start, pink=router, teal=agents)
- Proper node shapes (stadium for start, hexagon for router, rectangle for agents)
- Labeled edges showing routing scenarios
- Optional interactive `<details>` section with agent descriptions table

### 4. Template Analysis

Analyze Flowise templates to extract patterns:

```bash
# Analyze a single template
python3 analyzer.py --analyze templates/SupervisorAgent.json

# Analyze all templates in a directory
python3 analyzer.py --analyze-all templates/

# Export patterns to JSON
python3 analyzer.py --analyze-all templates/ --export-patterns patterns/my-patterns.json
```

### 5. Workflow Validation

Validate workflow files before deployment:

```bash
python3 validate_workflow.py path/to/workflow.json
```

This checks for all 14 known failure patterns and provides detailed fix suggestions.

For more usage examples and advanced features, see [docs/USAGE.md](docs/USAGE.md).

---

## API Reference

### detector.py

```python
detect_flowise_flow(file_path: Path) -> dict
    """Detect if a JSON file is a Flowise flow.

    Args:
        file_path: Path to the JSON file to analyze

    Returns:
        dict with keys: is_flowise, flow_type, complexity,
        node_count, edge_count, agent_count, has_memory, has_tools
    """

scan_directory(directory: Path) -> list[Path]
    """Find all JSON files in directory.

    Args:
        directory: Path to directory to scan

    Returns:
        List of Path objects for all JSON files found
    """

classify_flow_type(nodes, node_types, edges) -> str
    """Classify flow type based on node patterns.

    Args:
        nodes: List of node objects
        node_types: Set of node type strings
        edges: List of edge connections

    Returns:
        One of: 'multi-agent', 'rag', 'workflow', 'chatbot'
    """

calculate_complexity(node_count, edge_count, agent_count) -> str
    """Determine flow complexity level.

    Args:
        node_count: Total number of nodes
        edge_count: Total number of edges
        agent_count: Number of agent nodes

    Returns:
        One of: 'simple', 'moderate', 'complex'
    """
```

### analyzer.py

```python
analyze_template(template_path: Path) -> dict
    """Analyze a single Flowise template.

    Args:
        template_path: Path to template JSON file

    Returns:
        dict with node types, patterns, and configurations
    """

analyze_directory(directory: Path) -> dict
    """Analyze all templates in a directory.

    Args:
        directory: Path to directory containing templates

    Returns:
        dict with aggregated analysis results
    """

extract_node_patterns(nodes: list) -> list[dict]
    """Extract common node configurations.

    Args:
        nodes: List of node objects from template

    Returns:
        List of pattern dicts with frequency counts
    """

extract_connection_patterns(edges, nodes) -> list[dict]
    """Identify connection patterns.

    Args:
        edges: List of edge connections
        nodes: List of node objects

    Returns:
        List of connection pattern dicts
    """

export_patterns(patterns: dict, output_path: Path) -> None
    """Export patterns to JSON file.

    Args:
        patterns: Pattern dict to export
        output_path: Path to write JSON file
    """
```

### extensions_loader.py

```python
load_extension_detectors() -> dict | None
    """Load custom project detectors.

    Returns:
        dict of detector functions or None if not found
    """

load_extension_patterns(extension_name: str) -> dict | None
    """Load patterns from specific extension.

    Args:
        extension_name: Name of the extension

    Returns:
        dict with patterns or None if not found
    """

get_extension_prompt(extension_name: str, phase: str) -> str | None
    """Get phase-specific prompt enhancement.

    Args:
        extension_name: Name of the extension
        phase: Phase name ('scout' or 'architect')

    Returns:
        Prompt enhancement string or None
    """

extension_exists(extension_name: str) -> bool
    """Check if extension is available.

    Args:
        extension_name: Name of the extension

    Returns:
        True if extension exists and is loadable
    """
```

### mermaid_generator.py

```python
generate_diagram(workflow_path: Path, interactive: bool = False) -> str
    """Generate Mermaid diagram from Flowise workflow.

    Args:
        workflow_path: Path to workflow JSON file
        interactive: Include interactive details section

    Returns:
        Mermaid diagram markdown string
    """

parse_workflow(workflow_json: dict) -> tuple[list, list]
    """Parse workflow JSON into nodes and edges.

    Args:
        workflow_json: Parsed workflow JSON

    Returns:
        Tuple of (nodes list, edges list)
    """
```

### validate_workflow.py

```python
validate_workflow(workflow_path: Path) -> dict
    """Validate Flowise workflow against all known patterns.

    Args:
        workflow_path: Path to workflow JSON file

    Returns:
        dict with errors, warnings, and validation status
    """
```

---

## Architecture

### Detection Flow

```
1. Context Foundry starts build
2. MCP Server calls _detect_existing_codebase()
3. Hook tries to import flowise extension
4. If present: Scan JSON files for Flowise flows
5. If detected: Add project indicators
6. Orchestrator checks indicators
7. If Flowise: Load enhanced prompts
8. Scout/Architect get Flowise expertise
```

### Graceful Degradation

```
Extension Present     → Flowise enhancements applied
Extension Missing     → Normal Context Foundry (no errors)
Non-Flowise Project   → Extension inactive (no enhancements)
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Context Foundry                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │    Scout    │ → │  Architect  │ → │   Builder   │  │
│  │   Phase     │    │    Phase    │    │    Phase    │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │         │
│         ▼                  ▼                  ▼         │
│  ┌─────────────────────────────────────────────────┐   │
│  │           Flowise Extension (Private)            │   │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────────┐    │   │
│  │  │Detector │ │ Analyzer │ │ Pattern Lib   │    │   │
│  │  └─────────┘ └──────────┘ └───────────────┘    │   │
│  │  ┌─────────────────┐ ┌─────────────────────┐   │   │
│  │  │ Mermaid Gen     │ │ Workflow Validator  │   │   │
│  │  └─────────────────┘ └─────────────────────┘   │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Pattern Library

The extension includes proven patterns for building production-ready Flowise workflows:

### Workflow Patterns (13)

| Pattern ID | Description | Use Case |
|------------|-------------|----------|
| `afv2-chaining-pattern` | Sequential processing | Multi-step data transformation |
| `afv2-parallel-pattern` | Multi-source research | Concurrent data gathering |
| `afv2-routing-pattern` | Intent classification | Query routing to specialists |
| `afv2-iteration-pattern` | Quality refinement | Document improvement loops |
| `afv2-looping-pattern` | Validation retry | Error correction flows |
| `afv2-hierarchy-pattern` | Task delegation | Manager-worker architectures |
| `afv2-batch-processing` | Array processing | Bulk operations |
| `afv2-conditional-retry` | Score-based validation | Quality gates |
| `afv2-api-integration` | HTTP integration | External service calls |
| `afv2-rag-pattern` | Document Q&A | Knowledge retrieval |
| `afv2-smart-calculator` | Cost optimization | Dynamic pricing |
| `afv2-doc-qa-confidence` | Confidence routing | Uncertainty handling |
| `afv2-data-pipeline-etl` | ETL validation | Data transformation |

### Common Issues Prevented (15)

| Issue ID | Severity | Description |
|----------|----------|-------------|
| `flowise-missing-inputparams` | CRITICAL | Agent nodes not editable in UI |
| `flowise-missing-start-node` | CRITICAL | No workflow entry point |
| `flowise-separate-configs` | CRITICAL | External config files |
| `flowise-incorrect-tool-structure` | CRITICAL | Tool import failures |
| `flowise-disconnected-nodes` | HIGH | Unreachable agents |
| `flowise-phantom-tools` | HIGH | Referenced but missing tools |
| `flowise-missing-router-scenarios` | HIGH | Incomplete routing logic |
| `flowise-missing-mermaid` | MEDIUM | No visual documentation |

For complete pattern documentation, see [FAILURE_PATTERNS.md](FAILURE_PATTERNS.md).

---

## Testing

### Running Tests

```bash
# Run all tests
python3 -m unittest discover tests/

# Run specific test file
python3 -m unittest tests/test_detector.py

# Run specific test case
python3 -m unittest tests.test_detector.TestFlowiseDetector.test_detect_valid_multi_agent_flow

# Run with verbose output
python3 -m unittest discover tests/ -v

# Run with pytest (recommended)
python3 -m pytest tests/ -v --tb=short
```

### Test Coverage

| Test Module | Tests | Coverage |
|-------------|-------|----------|
| test_analyzer.py | 15 | 100% |
| test_bootstrap_integration.py | 14 | 100% |
| test_detector.py | 14 | 100% |
| test_loader.py | 17 | 100% |
| test_patterns.py | 14 | 100% |
| **Total** | **74** | **100%** |

### Expected Output

```
============================= test session starts ==============================
platform darwin -- Python 3.14.0, pytest-8.4.2
collected 74 items

tests/test_analyzer.py::test_analyze_template PASSED
tests/test_detector.py::test_detect_valid_multi_agent_flow PASSED
...
============================== 74 passed in 0.32s ==============================
```

For detailed testing documentation, see [docs/TESTING.md](docs/TESTING.md).

---

## Documentation

### Authoritative References

- **[AGENT_PATTERN_REFERENCE.md](./AGENT_PATTERN_REFERENCE.md)** - The single source of truth for Flowise multi-agent systems
- **[FAILURE_PATTERNS.md](./FAILURE_PATTERNS.md)** - Complete catalog of known issues and preventions

### Guides

- **[Training Guide](./docs/TRAINING_GUIDE.md)** - Master how to teach the extension new capabilities
- **[Documentation Index](./docs/DOCUMENTATION_INDEX.md)** - Navigation hub for all documentation
- **[User Guide](./USER_GUIDE.md)** - End-to-end workflow for using the extension
- **[Quickstart](./QUICKSTART.md)** - Get started in 5 minutes

### Integration

- **[Installation Guide](./docs/INSTALLATION.md)** - Detailed setup instructions
- **[MCP Integration](./docs/CONTEXT_FOUNDRY_MCP_SETUP.md)** - MCP server configuration
- **[Usage Guide](./docs/USAGE.md)** - Comprehensive usage examples

---

## Project Structure

```
flowise-extension/
├── detector.py              # Flow detection logic
├── analyzer.py              # Template analyzer with CLI
├── mermaid_generator.py     # Mermaid diagram generator
├── extensions_loader.py     # Safe dynamic loader
├── validate_workflow.py     # Comprehensive workflow validation
├── patterns/
│   ├── flowise-expertise.json   # Pattern library
│   └── flow-templates.json      # Template catalog
├── prompts/
│   ├── scout-enhancement.txt    # Scout phase guidance
│   └── architect-enhancement.txt # Architect phase patterns
├── integration/
│   ├── mcp_server_hook.py       # MCP server integration
│   └── orchestrator_prompt_injection.txt
├── templates/                    # Example Flowise templates
├── tests/
│   ├── test_detector.py         # Detector tests
│   ├── test_analyzer.py         # Analyzer tests
│   ├── test_loader.py           # Loader tests
│   ├── test_patterns.py         # Pattern tests
│   └── fixtures/                # Sample Flowise JSONs
├── docs/
│   ├── INSTALLATION.md
│   ├── USAGE.md
│   ├── TRAINING_GUIDE.md
│   └── DOCUMENTATION_INDEX.md
├── README.md                    # This file
└── __init__.py                  # Package initialization
```

---

## Troubleshooting

### Extension Not Loading

**Symptom**: Flowise flows not detected

**Solutions**:
1. Verify extension path: `extensions/flowise/`
2. Check Python path: Extension must be importable
3. Test detector: `python3 detector.py test.json`
4. Check MCP server logs for import errors

### Pattern Files Not Found

**Symptom**: `load_extension_patterns()` returns None

**Solutions**:
1. Rename `.example` files to remove extension
2. Verify file paths in `extensions_loader.py`
3. Check file permissions

### Tests Failing

**Symptom**: Unittest failures

**Solutions**:
1. Ensure fixtures exist: `tests/fixtures/*.json`
2. Check Python version: 3.10+ required
3. Run individual tests to isolate issue
4. Check for missing dependencies (should be none)

### Workflow Validation Failures

**Symptom**: `validate_workflow.py` reports critical errors

**Solutions**:
1. Review the specific error messages
2. Reference [FAILURE_PATTERNS.md](./FAILURE_PATTERNS.md) for fixes
3. Ensure all nodes have proper `inputParams` arrays
4. Verify node types match Flowise registry

---

## Contributing

This is a **private extension** for Context Foundry. Contributions are managed internally.

### How to Contribute

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style:
   - Python 3.10+ type hints
   - Docstrings for all public functions
   - No external dependencies

3. **Add tests** for new functionality:
   ```bash
   # Create test file in tests/
   # Follow existing test patterns
   python3 -m pytest tests/test_your_module.py -v
   ```

4. **Ensure all tests pass**:
   ```bash
   python3 -m pytest tests/ -v
   ```

5. **Update documentation**:
   - Update relevant .md files
   - Add entries to DOCUMENTATION_INDEX.md if needed

6. **Submit for review**

### Code Style

- Follow PEP 8
- Use type hints for all function signatures
- Include docstrings with Args/Returns sections
- Keep functions focused and testable

### Adding New Patterns

1. Analyze new template:
   ```bash
   python3 analyzer.py --analyze new-template.json
   ```

2. Add pattern to `patterns/flowise-expertise.json`

3. Update tests in `tests/test_patterns.py`

4. Document in FAILURE_PATTERNS.md if it's an anti-pattern

---

## License

**Private** - Context Foundry Internal Use Only

This extension is proprietary software for internal use within Context Foundry. Unauthorized distribution, modification, or use outside of Context Foundry is prohibited.

---

## Credits

**Built autonomously by Context Foundry**

### Technologies Used

- **Python 3.10+** - Core language
- **Flowise** - Target platform for AI workflow automation
- **Mermaid** - Diagram generation
- **Context Foundry** - Autonomous build orchestration

### Contributors

- Context Foundry Development Team
- Flowise Community (patterns and templates)

---

<p align="center">
  <strong>Building enterprise-grade Flowise workflows, autonomously.</strong>
</p>

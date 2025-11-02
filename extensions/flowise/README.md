# Flowise Extension for Context Foundry

A **private, modular extension framework** that teaches Context Foundry to become a Flowise expert. This extension automatically detects Flowise agent flows and provides world-class guidance for building high-quality workflows.

## Overview

This extension augments Context Foundry with deep Flowise expertise through:
- **Automatic Flow Detection**: Identifies Flowise JSON files and classifies flow types
- **Pattern-Based Learning**: Extracts best practices from template analysis
- **Phase Enhancements**: Injects expertise into Scout and Architect phases
- **Graceful Integration**: Zero impact when extension is absent (public repo compatible)

## 📚 Documentation

### Authoritative Pattern Reference

**[AGENT_PATTERN_REFERENCE.md](./AGENT_PATTERN_REFERENCE.md)** - The single source of truth for Flowise multi-agent systems

This comprehensive reference defines the canonical way to structure Flowise agent flows:
- ✅ Complete node type definitions (agentAgentflow, conditionAgentAgentflow)
- ✅ All input parameters with descriptions and examples
- ✅ Agent persona patterns and configuration guidelines
- ✅ Edge structure and connection patterns
- ✅ Critical design patterns (intent detection, agent specialization, knowledge integration)
- ✅ Complete implementation checklist
- ✅ Common pitfalls and how to avoid them

**When to use**: Reference this document when designing or validating Flowise multi-agent architectures.

### Supplementary Documentation

- **[SELF-CONTAINED-AGENTS-FIX.md](./SELF-CONTAINED-AGENTS-FIX.md)** - Critical fix for self-contained agent architecture
- **[prompts/FLOWISE-STRUCTURE-AUTHORITY.md](./prompts/FLOWISE-STRUCTURE-AUTHORITY.md)** - Detailed structural validation checklist
- **[prompts/flowise-json-structure-guide.md](./prompts/flowise-json-structure-guide.md)** - JSON structure guide

## Features

- ✅ **Auto-detect Flowise flows** (multi-agent, RAG, workflow, chatbot)
- ✅ **Classify complexity** (simple, moderate, complex)
- ✅ **Extract patterns** from template JSONs
- ✅ **Enhance Scout phase** with Flowise research checklist
- ✅ **Enhance Architect phase** with proven patterns
- ✅ **CLI tools** for template analysis
- ✅ **Zero dependencies** (Python stdlib only)
- ✅ **100% test coverage** (comprehensive unit tests)

## Installation

### Prerequisites

- Python 3.10 or higher
- Context Foundry installed

### Setup

1. Clone or copy this extension to Context Foundry's extensions directory:

```bash
# From Context Foundry root directory
mkdir -p extensions
cd extensions
git clone <this-repo-url> flowise
```

2. Verify installation:

```bash
cd flowise
python3 -m unittest discover tests/
```

All tests should pass.

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

### 3. Template Analysis

Analyze Flowise templates to extract patterns:

```bash
# Analyze a single template
python3 analyzer.py --analyze templates/SupervisorAgent.json

# Analyze all templates in a directory
python3 analyzer.py --analyze-all templates/

# Export patterns to JSON
python3 analyzer.py --analyze-all templates/ --export-patterns patterns/my-patterns.json
```

**Output:**
```
✅ Analyzed 12/15 files

Most Common Node Types:
  - AgentExecutor: 45 occurrences
  - LLMChain: 32 occurrences
  - VectorStoreRetriever: 18 occurrences

Most Common Connection Patterns:
  - supervisor-to-worker: 23 occurrences
  - retrieval-to-llm: 18 occurrences
  - agent-to-tool: 15 occurrences
```

### 4. Pattern Library

Load and use pattern library:

```python
from flowise import extensions_loader

# Load patterns
patterns = extensions_loader.load_extension_patterns('flowise')

if patterns:
    for pattern in patterns['patterns']:
        print(f"{pattern['pattern_id']}: {pattern['description']}")
```

## Project Structure

```
flowise-extension/
├── detector.py              # Flow detection logic
├── analyzer.py              # Template analyzer with CLI
├── extensions_loader.py     # Safe dynamic loader
├── patterns/
│   ├── flowise-expertise.json.example   # Pattern library
│   └── flow-templates.json.example      # Template catalog
├── prompts/
│   ├── scout-enhancement.txt            # Scout phase guidance
│   └── architect-enhancement.txt        # Architect phase patterns
├── integration/
│   ├── mcp_server_hook.py              # MCP server integration
│   └── orchestrator_prompt_injection.txt # Orchestrator enhancements
├── tests/
│   ├── test_detector.py                # Detector tests
│   ├── test_analyzer.py                # Analyzer tests
│   ├── test_loader.py                  # Loader tests
│   └── fixtures/                        # Sample Flowise JSONs
├── README.md                           # This file
└── __init__.py                         # Package initialization
```

## Integration with Context Foundry

### Step 1: MCP Server Integration

Add the code from `integration/mcp_server_hook.py` to `mcp_server.py`:

1. Open `context-foundry/mcp_server.py`
2. Locate the `_detect_existing_codebase()` method
3. Add the hook code after existing project detectors (~line 250-300)
4. Save and test with a Flowise project

### Step 2: Orchestrator Prompt Integration

Add enhancements from `integration/orchestrator_prompt_injection.txt`:

1. Open `context-foundry/orchestrator_prompt.txt`
2. Add Scout enhancement after Scout phase intro (~line 470)
3. Add Architect enhancement after Architect phase intro (~line 636)
4. Save and test with a Flowise project

### Step 3: Verify Integration

Test with a Flowise project:

```bash
# 1. Create test project with Flowise JSON
mkdir test-flowise-project
cd test-flowise-project
cp path/to/flowise-extension/tests/fixtures/supervisor_multi_agent.json ./

# 2. Run Context Foundry
cf build "Analyze this Flowise flow"

# 3. Verify Scout report mentions Flowise flow type
cat .context-foundry/scout-report.md | grep -i flowise
```

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

## Pattern Library

The extension includes proven patterns for:

### Multi-Agent Patterns
- **Supervisor-Worker**: Coordinator + specialized workers
- **Hierarchical**: Multi-level supervision
- **Collaborative**: Peer-based cooperation

### RAG Patterns
- **Basic RAG**: Simple vector search + LLM
- **RAG with Reranking**: Improved relevance
- **Hybrid RAG**: Semantic + keyword search
- **Agentic RAG**: Intelligent retrieval strategy

### Workflow Patterns
- **Sequential**: Linear processing
- **Branching**: Conditional logic
- **Parallel**: Concurrent execution

### Chatbot Patterns
- **Simple Chatbot**: Basic conversation
- **Tool-Enabled**: Actions beyond text
- **Multi-Modal**: Text + images
- **Domain Expert**: Specialized knowledge

### Quality Patterns
- **Error Handling**: Retry with exponential backoff
- **Self-Healing**: Automatic error recovery
- **Human-in-the-Loop**: Approval gates
- **Feedback Loop**: Continuous improvement

## Testing

Run the full test suite:

```bash
# Run all tests
python3 -m unittest discover tests/

# Run specific test file
python3 -m unittest tests/test_detector.py

# Run specific test case
python3 -m unittest tests.test_detector.TestFlowiseDetector.test_detect_valid_multi_agent_flow

# Run with verbose output
python3 -m unittest discover tests/ -v
```

**Expected output:**
```
test_detect_valid_multi_agent_flow ... ok
test_detect_valid_rag_flow ... ok
test_detect_valid_chatbot ... ok
test_reject_invalid_json ... ok
...
----------------------------------------------------------------------
Ran 35 tests in 0.123s

OK
```

## Development

### Adding New Patterns

1. Analyze new template:
```bash
python3 analyzer.py --analyze new-template.json
```

2. Add pattern to `patterns/flowise-expertise.json.example`:
```json
{
  "pattern_id": "new-pattern",
  "category": "architecture",
  "description": "...",
  "applies_to": ["flow-type"],
  "best_practices": [...],
  "anti_patterns": [...]
}
```

3. Update tests in `tests/test_analyzer.py`

### Adding New Flow Types

1. Update `detector.py::classify_flow_type()` with new heuristics
2. Add test case in `tests/test_detector.py`
3. Create fixture in `tests/fixtures/`
4. Update pattern library with new flow type guidance

## API Reference

### detector.py

```python
detect_flowise_flow(file_path: Path) -> dict
    """Detect if a JSON file is a Flowise flow."""

scan_directory(directory: Path) -> list[Path]
    """Find all JSON files in directory."""

classify_flow_type(nodes, node_types, edges) -> str
    """Classify flow type based on node patterns."""

calculate_complexity(node_count, edge_count, agent_count) -> str
    """Determine flow complexity level."""
```

### analyzer.py

```python
analyze_template(template_path: Path) -> dict
    """Analyze a single Flowise template."""

analyze_directory(directory: Path) -> dict
    """Analyze all templates in a directory."""

extract_node_patterns(nodes: list) -> list[dict]
    """Extract common node configurations."""

extract_connection_patterns(edges, nodes) -> list[dict]
    """Identify connection patterns."""

export_patterns(patterns: dict, output_path: Path) -> None
    """Export patterns to JSON file."""
```

### extensions_loader.py

```python
load_extension_detectors() -> dict | None
    """Load custom project detectors."""

load_extension_patterns(extension_name: str) -> dict | None
    """Load patterns from specific extension."""

get_extension_prompt(extension_name: str, phase: str) -> str | None
    """Get phase-specific prompt enhancement."""

extension_exists(extension_name: str) -> bool
    """Check if extension is available."""
```

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

## Contributing

This is a **private extension** for Context Foundry. Contributions are managed internally.

To propose improvements:
1. Create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Submit for review

## License

Private - Context Foundry Internal Use Only

## Credits

🤖 Built autonomously by Context Foundry

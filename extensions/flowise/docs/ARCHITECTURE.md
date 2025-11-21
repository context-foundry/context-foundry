# Architecture Documentation

> System architecture overview for the Flowise Extension for Context Foundry

---

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Detection Pipeline](#detection-pipeline)
- [Data Flow](#data-flow)
- [Integration Points](#integration-points)
- [Module Descriptions](#module-descriptions)
- [Design Decisions](#design-decisions)

---

## System Overview

The Flowise Extension is a modular enhancement layer for Context Foundry that provides specialized expertise for building Flowise AI workflows. It operates as an optional, gracefully-degrading extension that automatically activates when Flowise-related projects are detected.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Context Foundry Core                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌─────────┐ │
│  │  Scout   │ → │  Architect  │ → │  Builder │ → │  Test   │ │
│  │  Phase   │    │    Phase    │    │  Phase   │    │  Phase  │ │
│  └────┬─────┘    └──────┬──────┘    └────┬─────┘    └────┬────┘ │
│       │                 │                │               │      │
│       ▼                 ▼                ▼               ▼      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            Flowise Extension Layer (Optional)             │  │
│  │                                                           │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────────────┐     │  │
│  │  │  Flow     │  │  Pattern  │  │  Workflow         │     │  │
│  │  │  Detector │  │  Library  │  │  Validator        │     │  │
│  │  └─────┬─────┘  └─────┬─────┘  └─────────┬─────────┘     │  │
│  │        │              │                  │                │  │
│  │        ▼              ▼                  ▼                │  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────────────┐     │  │
│  │  │  Template │  │  Mermaid  │  │  Phase Prompt     │     │  │
│  │  │  Analyzer │  │  Generator│  │  Enhancements     │     │  │
│  │  └───────────┘  └───────────┘  └───────────────────┘     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### Core Components

#### 1. Flow Detector (`detector.py`)

**Purpose**: Identify and classify Flowise workflow files

**Responsibilities**:
- Scan directories for JSON files
- Analyze JSON structure for Flowise patterns
- Classify flow type (multi-agent, RAG, workflow, chatbot)
- Calculate complexity metrics

**Interface**:
```python
class FlowiseDetector:
    def detect_flowise_flow(file_path: Path) -> DetectionResult
    def scan_directory(directory: Path) -> list[Path]
    def classify_flow_type(nodes, node_types, edges) -> str
    def calculate_complexity(node_count, edge_count, agent_count) -> str
```

#### 2. Template Analyzer (`analyzer.py`)

**Purpose**: Extract patterns and best practices from templates

**Responsibilities**:
- Parse Flowise template structure
- Extract node configurations
- Identify connection patterns
- Export patterns for reuse

**Interface**:
```python
class TemplateAnalyzer:
    def analyze_template(template_path: Path) -> AnalysisResult
    def analyze_directory(directory: Path) -> AggregatedResult
    def extract_node_patterns(nodes: list) -> list[dict]
    def extract_connection_patterns(edges, nodes) -> list[dict]
```

#### 3. Workflow Validator (`validate_workflow.py`)

**Purpose**: Validate workflows against known failure patterns

**Responsibilities**:
- Check for all 14+ known failure patterns
- Generate detailed error reports
- Provide fix suggestions
- Block deployment for critical errors

**Interface**:
```python
class WorkflowValidator:
    def validate_workflow(workflow_path: Path) -> ValidationResult
    def check_pattern(pattern_id: str, workflow: dict) -> bool
    def generate_report(results: list) -> str
```

#### 4. Mermaid Generator (`mermaid_generator.py`)

**Purpose**: Create visual diagrams from workflows

**Responsibilities**:
- Parse workflow structure
- Generate Mermaid diagram syntax
- Apply Flowise color scheme
- Create interactive detail sections

**Interface**:
```python
class MermaidGenerator:
    def generate_diagram(workflow_path: Path, interactive: bool) -> str
    def parse_workflow(workflow_json: dict) -> tuple[list, list]
    def apply_styling(nodes: list) -> dict
```

#### 5. Extensions Loader (`extensions_loader.py`)

**Purpose**: Safe dynamic loading of extension components

**Responsibilities**:
- Load detectors, patterns, prompts
- Handle missing extensions gracefully
- Provide fallbacks for missing components

**Interface**:
```python
def load_extension_detectors() -> dict | None
def load_extension_patterns(extension_name: str) -> dict | None
def get_extension_prompt(extension_name: str, phase: str) -> str | None
def extension_exists(extension_name: str) -> bool
```

---

## Detection Pipeline

The detection pipeline runs automatically when Context Foundry analyzes a project:

```
Project Directory
       │
       ▼
┌─────────────────┐
│  Scan for JSON  │
│     Files       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Parse JSON     │
│  Structure      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  Check for      │ No  │   Skip       │
│  Flowise Markers├────►│   File       │
└────────┬────────┘     └──────────────┘
         │ Yes
         ▼
┌─────────────────┐
│  Extract Nodes  │
│  and Edges      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Classify Flow  │
│  Type           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Calculate      │
│  Complexity     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Return         │
│  Detection      │
│  Result         │
└─────────────────┘
```

### Detection Heuristics

**Flowise Flow Markers**:
- Contains `nodes` and `edges` arrays
- Node objects have `id`, `type`, and `data` fields
- Edge objects have `source`, `target`, and `sourceHandle`
- Contains Flowise-specific node types

**Flow Type Classification**:

| Type | Indicators |
|------|------------|
| Multi-Agent | Multiple `agent` nodes, supervisor patterns |
| RAG | `retriever` nodes, vector store connections |
| Workflow | Sequential processing, conditional branching |
| Chatbot | Single LLM, memory nodes, simple I/O |

---

## Data Flow

### Phase Enhancement Flow

```
                    Scout Phase
                         │
                         ▼
              ┌─────────────────────┐
              │  Load Scout         │
              │  Enhancement Prompt │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Inject Flowise     │
              │  Research Checklist │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Scout Generates    │
              │  Enhanced Report    │
              └──────────┬──────────┘
                         │
                         ▼
                  Architect Phase
                         │
                         ▼
              ┌─────────────────────┐
              │  Load Architect     │
              │  Enhancement Prompt │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Query Pattern      │
              │  Library            │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Generate Flowise   │
              │  Architecture       │
              └──────────┬──────────┘
                         │
                         ▼
                   Builder Phase
                         │
                         ▼
              ┌─────────────────────┐
              │  Generate Workflow  │
              │  JSON               │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Generate Mermaid   │
              │  Diagram            │
              └──────────┬──────────┘
                         │
                         ▼
                    Test Phase
                         │
                         ▼
              ┌─────────────────────┐
              │  Run Unit Tests     │
              │  (74 tests)         │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Validate Workflow  │
              │  (14 patterns)      │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Generate Test      │
              │  Report             │
              └─────────────────────┘
```

---

## Integration Points

### MCP Server Integration

The extension hooks into Context Foundry's MCP server through the detection hook:

```python
# In mcp_server.py, after existing project detectors

def _detect_existing_codebase():
    # ... existing detection code ...

    # Flowise extension hook
    try:
        from extensions.flowise import detector
        flowise_flows = detector.scan_directory(project_path)
        if flowise_flows:
            for flow_path in flowise_flows:
                result = detector.detect_flowise_flow(flow_path)
                if result['is_flowise']:
                    project_indicators['flowise'] = {
                        'flow_type': result['flow_type'],
                        'complexity': result['complexity'],
                        'detected_flows': len(flowise_flows)
                    }
                    break
    except ImportError:
        pass  # Extension not available, graceful degradation
```

### Orchestrator Integration

Phase prompts are enhanced through prompt injection:

```
Scout Phase Injection Point: After Scout phase intro (~line 470)
Architect Phase Injection Point: After Architect phase intro (~line 636)
```

### Pattern Library Integration (Context Codex)

```
flowise-expertise.json → Bootstrap → Context Codex → Phase queries
                                          ↓
                                   S3 Community Patterns
```

---

## Module Descriptions

### Pattern Library (`patterns/`)

**flowise-expertise.json**: Core pattern definitions
- 13 workflow patterns
- 15 common issues
- Pattern metadata (ID, category, severity)

**flow-templates.json**: Template catalog
- Example workflows by category
- Node configurations
- Edge patterns

### Prompts (`prompts/`)

**scout-enhancement.txt**: Scout phase guidance
- Flowise-specific research checklist
- Flow type identification questions
- Complexity assessment criteria

**architect-enhancement.txt**: Architect phase patterns
- Pattern selection guidance
- Node configuration templates
- Anti-pattern warnings

### Integration (`integration/`)

**mcp_server_hook.py**: MCP server integration code
**orchestrator_prompt_injection.txt**: Phase prompt enhancements

---

## Design Decisions

### 1. Zero Dependencies

**Decision**: Use only Python standard library

**Rationale**:
- Simplifies installation
- Reduces compatibility issues
- Ensures portability
- Minimizes attack surface

**Trade-offs**:
- Some features require more code
- Limited to stdlib JSON parsing

### 2. Graceful Degradation

**Decision**: Extension silently deactivates when not needed

**Rationale**:
- Non-Flowise projects unaffected
- Public repo compatibility
- No breaking changes to core

**Implementation**:
```python
try:
    from extensions.flowise import detector
    # Use extension
except ImportError:
    # Continue without extension
    pass
```

### 3. Pattern-Driven Development

**Decision**: Centralize knowledge in pattern library

**Rationale**:
- Single source of truth
- Easy to update and extend
- Enables automated validation
- Supports learning from templates

### 4. Comprehensive Validation

**Decision**: Validate against all known failure patterns

**Rationale**:
- Prevent common errors before deployment
- Reduce iteration cycles
- Document institutional knowledge
- Enable autonomous building

### 5. Visual Documentation Generation

**Decision**: Auto-generate Mermaid diagrams

**Rationale**:
- Visual understanding of workflows
- GitHub native rendering
- Interactive documentation
- Reduces manual documentation burden

---

## Future Architecture Considerations

### Potential Enhancements

1. **Real-time Validation**: Validate during build, not just at test phase
2. **Pattern Recommendation**: Suggest patterns based on user intent
3. **Template Generation**: Generate starter templates from patterns
4. **Version Compatibility**: Check Flowise version compatibility
5. **Performance Metrics**: Track build times and success rates

### Scalability Considerations

- Pattern library can grow with community contributions
- Modular design allows adding new validators
- Extension loader supports multiple extensions
- Test suite scales with new test cases

---

## References

- [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - Node type definitions
- [FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) - Complete pattern catalog
- [Context Foundry Architecture](../../README.md) - Core system architecture

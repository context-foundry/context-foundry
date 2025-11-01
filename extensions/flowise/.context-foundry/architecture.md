# Architecture: Flowise Extension for Context Foundry

## System Overview

A **plugin-style extension framework** that augments Context Foundry with Flowise expertise. The system uses **dynamic detection + pattern-based learning + conditional integration** to teach Context Foundry how to build world-class Flowise workflows.

```
┌─────────────────────────────────────────────────────────────┐
│                   Context Foundry (Core)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            MCP Server (mcp_server.py)                  │ │
│  │  ┌────────────────────────────────────────────────┐   │ │
│  │  │  _detect_existing_codebase()                   │   │ │
│  │  │    ├─ Load extensions_loader (optional)        │   │ │
│  │  │    ├─ Check for Flowise flows                  │   │ │
│  │  │    └─ Add to project_indicators                │   │ │
│  │  └────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │     Orchestrator (orchestrator_prompt.txt)            │ │
│  │  ┌────────────────────────────────────────────────┐   │ │
│  │  │  Scout Phase Enhancement (conditional)         │   │ │
│  │  │    └─ Inject Flowise research checklist        │   │ │
│  │  └────────────────────────────────────────────────┘   │ │
│  │  ┌────────────────────────────────────────────────┐   │ │
│  │  │  Architect Phase Enhancement (conditional)     │   │ │
│  │  │    └─ Inject Flowise pattern library           │   │ │
│  │  └────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ imports (conditional)
                              ▼
        ┌─────────────────────────────────────────┐
        │   extensions/flowise/ (OPTIONAL)        │
        │  ┌───────────────────────────────────┐  │
        │  │  detector.py                      │  │
        │  │   ├─ detect_flowise_flow()        │  │
        │  │   └─ classify_flow_type()         │  │
        │  └───────────────────────────────────┘  │
        │  ┌───────────────────────────────────┐  │
        │  │  analyzer.py                      │  │
        │  │   ├─ analyze_template()           │  │
        │  │   ├─ extract_patterns()           │  │
        │  │   └─ CLI interface                │  │
        │  └───────────────────────────────────┘  │
        │  ┌───────────────────────────────────┐  │
        │  │  extensions_loader.py             │  │
        │  │   ├─ load_extension_detectors()   │  │
        │  │   ├─ load_extension_patterns()    │  │
        │  │   └─ get_extension_prompt()       │  │
        │  └───────────────────────────────────┘  │
        │  ┌───────────────────────────────────┐  │
        │  │  patterns/ (examples)             │  │
        │  │   ├─ flowise-expertise.json       │  │
        │  │   └─ flow-templates.json          │  │
        │  └───────────────────────────────────┘  │
        │  ┌───────────────────────────────────┐  │
        │  │  prompts/                         │  │
        │  │   ├─ scout-enhancement.txt        │  │
        │  │   └─ architect-enhancement.txt    │  │
        │  └───────────────────────────────────┘  │
        └─────────────────────────────────────────┘
```

## Directory Structure

```
flowise-extension/
├── detector.py                          # Core detection logic
├── analyzer.py                          # Template analyzer with CLI
├── extensions_loader.py                 # Safe dynamic loader
├── patterns/
│   ├── flowise-expertise.json.example   # Pattern library (supervisor, RAG, etc.)
│   └── flow-templates.json.example      # Categorized template examples
├── prompts/
│   ├── scout-enhancement.txt            # Flowise Scout guidance
│   └── architect-enhancement.txt        # Flowise Architect patterns
├── integration/
│   ├── mcp_server_hook.py              # Code to add to mcp_server.py
│   └── orchestrator_prompt_injection.txt # Prompt enhancements
├── tests/
│   ├── test_detector.py                # Detector tests (8-10 cases)
│   ├── test_analyzer.py                # Analyzer tests (6-8 cases)
│   ├── test_loader.py                  # Loader tests (5-6 cases)
│   └── fixtures/
│       ├── supervisor_multi_agent.json  # Sample Flowise flow
│       ├── rag_workflow.json           # RAG pattern example
│       ├── simple_chatbot.json         # Basic chatbot
│       └── invalid_file.json           # Non-Flowise JSON
├── README.md                           # Complete documentation
└── .gitignore                          # Python patterns
```

## Module Specifications

### 1. detector.py

**Purpose**: Analyze JSON files to detect Flowise flows and classify them.

**API**:
```python
def detect_flowise_flow(file_path: Path) -> dict[str, Any]:
    """
    Detect if a JSON file is a Flowise flow.

    Returns:
        {
            "is_flowise": bool,
            "flow_type": "multi-agent" | "rag" | "workflow" | "chatbot" | "unknown",
            "complexity": "simple" | "moderate" | "complex",
            "node_count": int,
            "agent_count": int,
            "has_memory": bool,
            "has_tools": bool,
            "expertise_level": "beginner" | "advanced" | "expert"
        }
    """

def scan_directory(directory: Path) -> list[Path]:
    """Find all JSON files in directory (non-recursive)."""

def classify_flow_type(nodes: list[dict]) -> str:
    """Classify flow based on node patterns."""

def calculate_complexity(node_count: int, edge_count: int, agent_count: int) -> str:
    """Determine flow complexity."""
```

**Detection Logic**:
1. **Structure check**: Verify required keys (nodes, edges)
2. **Node type analysis**: Identify LLM, Agent, Tool, Memory nodes
3. **Pattern matching**:
   - Multi-agent: Multiple AgentExecutor nodes
   - RAG: VectorStore + Retriever + LLM chain
   - Workflow: Sequential LLMChain nodes
   - Chatbot: ConversationChain with memory
4. **Complexity scoring**:
   - Simple: <5 nodes, 0-1 agents
   - Moderate: 5-15 nodes, 2-3 agents
   - Complex: >15 nodes or >3 agents

**Error Handling**:
- FileNotFoundError → return {"is_flowise": False}
- JSONDecodeError → return {"is_flowise": False}
- Missing keys → check alternative structures

---

### 2. analyzer.py

**Purpose**: Analyze Flowise templates to extract patterns and best practices.

**API**:
```python
def analyze_template(template_path: Path) -> dict[str, Any]:
    """Analyze a single Flowise template and extract patterns."""

def analyze_directory(directory: Path) -> dict[str, Any]:
    """Analyze all templates in a directory."""

def extract_node_patterns(nodes: list[dict]) -> list[dict]:
    """Extract common node configurations."""

def extract_connection_patterns(edges: list[dict], nodes: list[dict]) -> list[dict]:
    """Identify connection patterns (supervisor→worker, sequential, parallel)."""

def export_patterns(patterns: dict, output_path: Path) -> None:
    """Export patterns to JSON file."""

def main() -> None:
    """CLI entry point with argparse."""
```

**CLI Interface**:
```bash
python analyzer.py --analyze templates/SupervisorAgent.json
python analyzer.py --analyze-all templates/
python analyzer.py --export-patterns patterns/flowise-expertise.json
```

**Pattern Extraction Logic**:
1. **Node configurations**: Group by node type, extract common settings
2. **Connection patterns**: Analyze edge sequences (supervisor→worker, branching)
3. **Best practices**: Identify error handling, retry logic, prompt patterns
4. **Quality markers**: High-star flows (production-ready indicators)
5. **Anti-patterns**: Common mistakes to avoid

**Output Format**:
```json
{
  "patterns": [
    {
      "pattern_id": "supervisor-worker-multi-agent",
      "category": "architecture",
      "description": "...",
      "applies_to": ["multi-agent", "workflow-orchestration"],
      "node_types": ["AgentExecutor", "LLMChain"],
      "best_practices": [...],
      "anti_patterns": [...]
    }
  ],
  "version": "1.0",
  "analyzed_files": 15,
  "last_updated": "2025-01-13T..."
}
```

---

### 3. extensions_loader.py

**Purpose**: Safely load extension modules with graceful fallback.

**API**:
```python
def load_extension_detectors() -> dict[str, Any] | None:
    """
    Load custom project detectors from extensions/.
    Returns None if extensions directory doesn't exist.
    """

def load_extension_patterns(extension_name: str) -> dict[str, Any] | None:
    """
    Load patterns from specific extension.
    Returns None if extension doesn't exist.
    """

def get_extension_prompt(extension_name: str, phase: str) -> str | None:
    """
    Get phase-specific prompt enhancement.
    Returns None if prompt file doesn't exist.
    """

def extension_exists(extension_name: str) -> bool:
    """Check if an extension is available."""
```

**Implementation Strategy**:
- **Defensive checks**: Path.exists() before any file operations
- **Try/except**: Wrap imports and file reads
- **Return None**: Never raise exceptions
- **No assumptions**: Don't assume any paths exist

**Example Usage**:
```python
# In mcp_server.py
detectors = load_extension_detectors()
if detectors and 'flowise' in detectors:
    result = detectors['flowise'].detect_flowise_flow(path)
    # Handle result
```

---

### 4. Prompt Templates

#### scout-enhancement.txt

```
**FLOWISE FLOW DETECTED**

Flow Type: {flow_type}
Complexity: {complexity}
Nodes: {node_count}
Agents: {agent_count}

**Enhanced Research Checklist**:
1. Node Architecture Analysis
   - Identify all node types (LLM, Agent, Tool, Memory)
   - Map data flow between nodes
   - Check for proper error handling

2. Flow Quality Benchmarks (1000-star criteria)
   - Production-ready error handling
   - Retry logic implemented
   - Memory management patterns
   - Tool integration best practices

3. Anti-Patterns to Identify
   - Circular dependencies
   - Missing error handlers
   - Hardcoded values in prompts
   - Inefficient token usage

4. Architecture Recommendations
   - [Pattern-specific guidance based on flow type]
```

#### architect-enhancement.txt

```
**FLOWISE ARCHITECTURE PATTERNS**

Apply proven patterns for: {flow_type}

**Node Architecture**:
- LLM Chain: [best practices]
- Agent Executor: [configuration patterns]
- Memory Systems: [optimal settings]
- Tool Integration: [proper setup]

**Testing Strategy**:
- Unit tests: Test each node in isolation
- Integration tests: Test node chains
- E2E tests: Test complete flow with real LLM
- Validation: Check output quality, error handling

**Deployment Checklist**:
- [ ] Environment variables configured
- [ ] API keys management strategy
- [ ] Rate limiting implemented
- [ ] Logging and monitoring
- [ ] Graceful degradation paths
```

---

### 5. Integration Hooks

#### mcp_server_hook.py

**Code to add to mcp_server.py** (in `_detect_existing_codebase` method):

```python
# FLOWISE EXTENSION HOOK (add after existing detectors)
try:
    from extensions.flowise.extensions_loader import load_extension_detectors
    flowise_detectors = load_extension_detectors()

    if flowise_detectors and 'flowise' in flowise_detectors:
        # Check for Flowise JSON files
        json_files = list(directory.glob("*.json"))
        for json_file in json_files[:10]:  # Sample first 10
            detection = flowise_detectors['flowise'].detect_flowise_flow(json_file)
            if detection.get('is_flowise'):
                project_indicators['flowise_flow'] = True
                project_type = 'flowise-extension'
                confidence = 'high'
                languages.append('flowise')
                project_files.append(str(json_file))
                break
except ImportError:
    # Extension not installed, continue without Flowise detection
    pass
```

#### orchestrator_prompt_injection.txt

**Text to inject into orchestrator_prompt.txt**:

```markdown
## FLOWISE EXTENSION ENHANCEMENT (Scout Phase - Line ~470)

**IF Flowise flow detected** (check project_indicators['flowise_flow']):

Load enhancement prompt:
```python
from extensions.flowise.extensions_loader import get_extension_prompt
enhancement = get_extension_prompt('flowise', 'scout')
if enhancement:
    # Append enhancement to Scout guidance
```

---

## FLOWISE EXTENSION ENHANCEMENT (Architect Phase - Line ~636)

**IF Flowise flow detected**:

Load architecture patterns:
```python
from extensions.flowise.extensions_loader import load_extension_patterns
patterns = load_extension_patterns('flowise')
if patterns:
    # Apply patterns to architecture design
```
```

---

## Pattern File Schemas

### flowise-expertise.json.example

```json
{
  "patterns": [
    {
      "pattern_id": "supervisor-worker-multi-agent",
      "category": "architecture",
      "description": "Multi-agent system with supervisor coordinating worker agents",
      "applies_to": ["multi-agent", "complex-workflow"],
      "node_types": ["AgentExecutor", "LLMChain", "LLMRouterChain"],
      "best_practices": [
        "Supervisor agent routes tasks to specialized workers",
        "Each worker has narrow, well-defined responsibility",
        "Shared memory for context passing",
        "Error handling at supervisor level"
      ],
      "anti_patterns": [
        "Too many workers (>5) leads to routing confusion",
        "Workers with overlapping responsibilities",
        "No error recovery at worker level"
      ],
      "quality_markers": [
        "Clear task decomposition",
        "Robust error handling",
        "Efficient token usage",
        "Proper memory management"
      ]
    },
    {
      "pattern_id": "rag-retrieval-augmented",
      "category": "architecture",
      "description": "RAG pattern with vector store and semantic retrieval",
      "applies_to": ["rag", "knowledge-retrieval"],
      "node_types": ["VectorStoreRetriever", "EmbeddingsNode", "LLMChain"],
      "best_practices": [
        "Use hybrid search (semantic + keyword)",
        "Implement reranking for better relevance",
        "Cache embeddings for performance",
        "Set appropriate chunk size (512-1024 tokens)"
      ],
      "anti_patterns": [
        "Single-pass retrieval without reranking",
        "Too large chunks (>2048 tokens)",
        "No fallback when no results found"
      ]
    }
  ],
  "version": "1.0",
  "last_updated": "2025-01-13T..."
}
```

### flow-templates.json.example

```json
{
  "templates": {
    "multi-agent": [
      {
        "name": "Supervisor-Worker Pattern",
        "file": "templates/supervisor_agent.json",
        "description": "...",
        "use_cases": ["..."]
      }
    ],
    "rag": [
      {
        "name": "RAG with Reranking",
        "file": "templates/rag_rerank.json",
        "description": "..."
      }
    ],
    "workflow": [
      {
        "name": "Sequential Processing",
        "file": "templates/sequential_workflow.json"
      }
    ],
    "chatbot": [
      {
        "name": "Conversational Agent",
        "file": "templates/simple_chatbot.json"
      }
    ]
  }
}
```

---

## Testing Strategy

### Test Coverage Plan

**test_detector.py** (8-10 test cases):
1. `test_detect_valid_multi_agent_flow()` - Supervisor pattern
2. `test_detect_valid_rag_flow()` - RAG pattern
3. `test_detect_valid_workflow()` - Sequential workflow
4. `test_detect_valid_chatbot()` - Simple chatbot
5. `test_reject_invalid_json()` - Non-Flowise JSON
6. `test_reject_malformed_json()` - Syntax errors
7. `test_classify_complexity_simple()` - <5 nodes
8. `test_classify_complexity_complex()` - >15 nodes
9. `test_missing_file_handling()` - FileNotFoundError
10. `test_scan_directory()` - Find all JSON files

**test_analyzer.py** (6-8 test cases):
1. `test_analyze_template_valid()` - Extract patterns from valid template
2. `test_analyze_directory()` - Analyze multiple templates
3. `test_extract_node_patterns()` - Group node configurations
4. `test_extract_connection_patterns()` - Identify supervisor→worker
5. `test_export_patterns()` - Write JSON output
6. `test_cli_analyze()` - CLI --analyze command
7. `test_cli_analyze_all()` - CLI --analyze-all command
8. `test_empty_template_handling()` - Empty/invalid templates

**test_loader.py** (5-6 test cases):
1. `test_load_detectors_success()` - Load when extensions/ exists
2. `test_load_detectors_missing_dir()` - Return None gracefully
3. `test_load_patterns_success()` - Load flowise patterns
4. `test_load_patterns_missing()` - Return None
5. `test_get_extension_prompt()` - Load prompt enhancement
6. `test_extension_exists()` - Check availability

### Test Fixtures

**fixtures/supervisor_multi_agent.json**:
```json
{
  "nodes": [
    {"id": "supervisor", "type": "AgentExecutor", "data": {"name": "Supervisor"}},
    {"id": "worker1", "type": "AgentExecutor", "data": {"name": "Worker1"}},
    {"id": "worker2", "type": "AgentExecutor", "data": {"name": "Worker2"}}
  ],
  "edges": [
    {"source": "supervisor", "target": "worker1"},
    {"source": "supervisor", "target": "worker2"}
  ],
  "chatflowid": "test-123"
}
```

**fixtures/rag_workflow.json**:
```json
{
  "nodes": [
    {"id": "retriever", "type": "VectorStoreRetriever"},
    {"id": "embeddings", "type": "OpenAIEmbeddings"},
    {"id": "llm", "type": "LLMChain"}
  ],
  "edges": [
    {"source": "retriever", "target": "llm"}
  ]
}
```

**fixtures/simple_chatbot.json**:
```json
{
  "nodes": [
    {"id": "chat", "type": "ConversationChain"},
    {"id": "memory", "type": "BufferMemory"}
  ],
  "edges": [
    {"source": "memory", "target": "chat"}
  ]
}
```

**fixtures/invalid_file.json**:
```json
{
  "not_a_flowise": "file",
  "random_data": [1, 2, 3]
}
```

---

## Implementation Steps (Ordered for Parallel Execution)

### Level 0 (Independent - Execute in Parallel):
1. **Task: Core detector module**
   - Files: `detector.py`
   - No dependencies

2. **Task: Analyzer module with CLI**
   - Files: `analyzer.py`
   - No dependencies

3. **Task: Loader module**
   - Files: `extensions_loader.py`
   - No dependencies

4. **Task: Prompt templates**
   - Files: `prompts/scout-enhancement.txt`, `prompts/architect-enhancement.txt`
   - No dependencies

5. **Task: Integration hooks**
   - Files: `integration/mcp_server_hook.py`, `integration/orchestrator_prompt_injection.txt`
   - No dependencies

6. **Task: Pattern examples**
   - Files: `patterns/flowise-expertise.json.example`, `patterns/flow-templates.json.example`
   - No dependencies

### Level 1 (Depends on Level 0):
7. **Task: Test suite**
   - Files: `tests/test_detector.py`, `tests/test_analyzer.py`, `tests/test_loader.py`
   - Depends on: detector.py, analyzer.py, extensions_loader.py

8. **Task: Test fixtures**
   - Files: `tests/fixtures/*.json`
   - No dependencies (can run in parallel with Level 0)

### Level 2 (Final):
9. **Task: Documentation**
   - Files: `README.md`, `.gitignore`
   - Depends on: All modules complete

---

## Success Criteria

### Functional Requirements:
- ✅ Detector accurately identifies Flowise flows (>95% precision)
- ✅ Analyzer extracts meaningful patterns from templates
- ✅ Loader works with and without extensions/ directory
- ✅ All tests pass with >80% coverage
- ✅ Integration hooks provided with clear instructions

### Code Quality Requirements:
- ✅ Type hints on all functions
- ✅ Docstrings with examples
- ✅ Error handling for all edge cases
- ✅ Logging where appropriate
- ✅ Clean, readable code structure

### Documentation Requirements:
- ✅ README.md with installation, usage, integration guide
- ✅ API documentation for all modules
- ✅ Architecture explanation
- ✅ Example usage scenarios

### Integration Requirements:
- ✅ Non-invasive integration (conditional checks only)
- ✅ Zero impact when extension absent
- ✅ Clear instructions for Context Foundry integration
- ✅ Tested with and without extensions/ present

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| False positives in detection | Multi-criteria heuristics with strict thresholds |
| Pattern extraction noise | Frequency analysis, exclude one-off occurrences |
| Breaking public repo | All integrations conditional, defensive programming |
| Missing dependencies | Stdlib only, no external packages |
| Integration complexity | Clear documentation, code examples provided |

---

## Deployment Notes

- **Repository**: Private GitHub repo (flowise-extension is proprietary)
- **Installation**: Manual copy to `extensions/flowise/` in Context Foundry
- **Dependencies**: None (Python 3.10+ stdlib only)
- **Testing**: Run `python -m unittest discover tests/` before integration
- **Integration**: Follow README.md integration guide step-by-step

---

## Future Enhancements (Out of Scope)

- Real-time Flowise flow validation
- Auto-generation of Flowise flows from prompts
- Integration with Flowise API for deployment
- Pattern marketplace for sharing expertise
- Machine learning-based pattern extraction

# BAML Integration Architecture

## System Architecture Overview

Context Foundry will integrate BAML as an **optional reliability layer** for structured LLM outputs, focusing on high-impact areas where type safety eliminates parsing errors. This is NOT a full rewrite—BAML augments existing functionality.

```
┌─────────────────────────────────────────────────────────────┐
│                    Context Foundry MCP Server                │
│                     (tools/mcp_server.py)                    │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Spawns Claude instances with
                  │ orchestrator_prompt.txt
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Autonomous Build Orchestrator                   │
│         Scout → Architect → Builder → Test → Deploy         │
└──────┬──────────────────────────────────────────────────────┘
       │
       │ NEW: Optional BAML layer for structured outputs
       ▼
┌─────────────────────────────────────────────────────────────┐
│                  BAML Integration Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Phase        │  │ Scout Report │  │ Architect    │      │
│  │ Tracking     │  │ Schema       │  │ Blueprint    │      │
│  │ (PhaseInfo)  │  │              │  │ Schema       │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  Compiled from: tools/baml_schemas/*.baml                    │
│  Generated to: tools/baml_client/                            │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
context-foundry/
├── tools/
│   ├── baml_schemas/                    # NEW: BAML definitions
│   │   ├── phase_tracking.baml          # Phase tracking types
│   │   ├── scout.baml                   # Scout report schema
│   │   ├── architect.baml               # Architecture blueprint schema
│   │   ├── builder.baml                 # Builder task results
│   │   └── clients.baml                 # LLM client configurations
│   │
│   ├── baml_client/                     # NEW: Generated Python client (auto-compiled)
│   │   ├── __init__.py
│   │   ├── types.py                     # Generated type classes
│   │   └── sync_client.py               # Generated sync client
│   │
│   ├── baml_integration.py              # NEW: BAML helper functions
│   ├── mcp_server.py                    # MODIFIED: Add BAML support
│   ├── orchestrator_prompt.txt          # MODIFIED: Optional BAML usage
│   └── ...
│
├── requirements.txt                     # MODIFIED: Add baml-py
├── requirements-baml.txt                # NEW: Optional BAML deps
├── docs/
│   ├── BAML_INTEGRATION.md             # NEW: BAML usage guide
│   └── ...
├── tests/
│   ├── test_baml_integration.py        # NEW: BAML tests
│   └── ...
└── examples/
    └── baml-example-project/            # NEW: Example using BAML
```

## Module Specifications

### 1. BAML Schemas (`tools/baml_schemas/`)

**phase_tracking.baml**
```baml
// Type-safe phase tracking to replace JSON strings

class PhaseInfo {
  session_id string
  current_phase PhaseType
  phase_number string
  status PhaseStatus
  progress_detail string
  test_iteration int
  phases_completed PhaseType[]
  started_at string
  last_updated string
}

enum PhaseType {
  CodebaseAnalysis
  Scout
  Architect
  Builder
  Test
  Screenshot
  Documentation
  Deploy
  Feedback
  GitHub
}

enum PhaseStatus {
  analyzing
  researching
  designing
  building
  testing
  self_healing
  capturing
  documenting
  deploying
  completed
  failed
}

function CreatePhaseInfo(
  phase: PhaseType,
  status: PhaseStatus,
  detail: string,
  iteration: int
) -> PhaseInfo {
  client GPT4
  prompt #"
    Create phase tracking info:
    Phase: {{ phase }}
    Status: {{ status }}
    Detail: {{ detail }}
    Test iteration: {{ iteration }}
    
    Return structured phase information.
  "#
}

function ValidatePhaseInfo(json_string: string) -> PhaseInfo {
  client GPT4
  prompt #"
    Validate and parse this phase info JSON:
    {{ json_string }}
    
    Return as structured PhaseInfo object.
  "#
}
```

**scout.baml**
```baml
// Structured Scout reports with guaranteed schema

class ScoutReport {
  executive_summary string @description("2-3 paragraphs max")
  past_learnings_applied string[] @description("Bullet points")
  known_risks string[] @description("Flagged from pattern library")
  key_requirements string[] @description("Bulleted list, not essay")
  tech_stack TechStack
  architecture_recommendations string[] @description("Top 3-5 critical items")
  main_challenges Challenge[] @description("Top 3-5 challenges")
  testing_approach string @description("Brief outline")
  timeline_estimate string @description("Single line estimate")
}

class TechStack {
  languages string[]
  frameworks string[]
  dependencies string[]
  justification string @description("Brief, 2-3 sentences")
}

class Challenge {
  description string
  severity Severity
  mitigation string
}

enum Severity {
  LOW
  MEDIUM
  HIGH
  CRITICAL
}

function GenerateScoutReport(
  task_description: string,
  codebase_analysis: string,
  past_patterns: string
) -> ScoutReport {
  client Claude35Sonnet
  prompt #"
    You are the Scout agent researching this task:
    
    {{ task_description }}
    
    Codebase analysis:
    {{ codebase_analysis }}
    
    Past patterns to consider:
    {{ past_patterns }}
    
    Provide comprehensive yet concise research findings.
  "#
}
```

**architect.baml**
```baml
// Architecture blueprint with validated structure

class ArchitectureBlueprint {
  system_overview string
  file_structure FileStructure[]
  modules ModuleSpec[]
  applied_patterns AppliedPattern[]
  preventive_measures string[]
  implementation_steps string[]
  test_plan TestPlan
  success_criteria string[]
}

class FileStructure {
  path string
  purpose string
  dependencies string[]
}

class ModuleSpec {
  name string
  responsibility string
  interfaces string[]
  dependencies string[]
}

class AppliedPattern {
  pattern_id string
  pattern_name string
  reason string
}

class TestPlan {
  unit_tests string[]
  integration_tests string[]
  e2e_tests string[]
  test_framework string
  success_criteria string[]
}

function GenerateArchitecture(
  scout_report: ScoutReport,
  flagged_risks: string[]
) -> ArchitectureBlueprint {
  client Claude35Sonnet
  prompt #"
    You are the Architect agent designing the system.
    
    Scout findings:
    Executive summary: {{ scout_report.executive_summary }}
    Tech stack: {{ scout_report.tech_stack }}
    Challenges: {{ scout_report.main_challenges }}
    
    Flagged risks to address:
    {% for risk in flagged_risks %}
    - {{ risk }}
    {% endfor %}
    
    Create detailed technical architecture.
  "#
}
```

**builder.baml**
```baml
// Builder task results with error tracking

class BuildTaskResult {
  task_id string
  description string
  status BuildStatus
  files_created string[]
  files_modified string[]
  errors BuildError[]
  warnings string[]
  success bool
  next_steps string[]
}

enum BuildStatus {
  success
  partial
  failed
}

class BuildError {
  file string
  line int?
  message string
  severity ErrorSeverity
}

enum ErrorSeverity {
  error
  warning
  info
}

function ExecuteBuildTask(
  task_id: string,
  task_description: string,
  files_to_create: string[],
  architecture: string
) -> BuildTaskResult {
  client Claude35Sonnet
  prompt #"
    Execute build task: {{ task_id }}
    
    Task: {{ task_description }}
    
    Files to create:
    {% for file in files_to_create %}
    - {{ file }}
    {% endfor %}
    
    Architecture context:
    {{ architecture }}
    
    Return structured result with files created and any errors.
  "#
}
```

**clients.baml**
```baml
// LLM client configurations

client<llm> GPT4 {
  provider openai
  options {
    model "gpt-4o"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> Claude35Sonnet {
  provider anthropic
  options {
    model "claude-3-5-sonnet-20241022"
    api_key env.ANTHROPIC_API_KEY
  }
}

client<llm> Claude35Haiku {
  provider anthropic
  options {
    model "claude-3-5-haiku-20241022"
    api_key env.ANTHROPIC_API_KEY
  }
}
```

### 2. BAML Integration Helper (`tools/baml_integration.py`)

**Purpose**: Bridge between Context Foundry and BAML, handle compilation, fallbacks

**Key Functions**:
- `compile_baml_schemas()`: Compile .baml files to Python client
- `get_baml_client()`: Get compiled BAML client (cached)
- `update_phase_with_baml()`: Update phase tracking using BAML types
- `generate_scout_report_baml()`: Generate structured Scout report
- `generate_architecture_baml()`: Generate structured architecture
- `validate_with_baml()`: Validate JSON against BAML schema
- `fallback_to_json()`: Graceful fallback if BAML unavailable

**Responsibilities**:
- BAML compilation management
- Type validation and error handling
- Backward compatibility with JSON mode
- Client caching for performance

### 3. MCP Server Updates (`tools/mcp_server.py`)

**Modifications**:
- Add `baml_integration` import
- Update `_read_phase_info()`: Try BAML validation first, fallback to JSON
- Add new MCP tool: `update_phase_baml(phase, status, detail)`
- Add new MCP tool: `validate_phase_tracking()`
- Initialize BAML client on server startup (optional, non-blocking)

**New MCP Tools**:
```python
@mcp.tool()
def update_phase_baml(
    phase: str,
    status: str, 
    detail: str,
    iteration: int = 0
) -> dict:
    """Update phase tracking using BAML type-safe schema"""
    
@mcp.tool()
def validate_phase_tracking() -> dict:
    """Validate current phase tracking with BAML"""
```

### 4. Orchestrator Prompt Updates (`tools/orchestrator_prompt.txt`)

**Modifications**:
- Add section on optional BAML usage
- Update phase tracking instructions to mention BAML validation
- Add note that BAML is internal optimization (transparent to users)
- Keep JSON fallback instructions for backward compatibility

**Integration Points**:
- Phase tracking: "If BAML is available, use update_phase_baml()"
- Scout phase: "Generate structured report using BAML schema if available"
- Architect phase: "Validate architecture blueprint with BAML"

## Applied Patterns and Preventive Measures

**Pattern 1: Gradual Adoption**
- BAML is optional dependency
- All features work without BAML (JSON fallback)
- No breaking changes to existing workflows
- Users don't need to learn BAML

**Pattern 2: Compilation Caching**
- Compile BAML schemas once at startup
- Cache compiled client in memory
- Recompile only if .baml files change
- Pre-compile during installation for faster startup

**Pattern 3: Type-Safe Validation**
- Use BAML to validate existing JSON files
- Catch schema mismatches early
- Better error messages than JSON parsing
- Compile-time guarantees for new code

**Pattern 4: Observability**
- Optional Boundary Studio integration
- Track BAML function calls
- Monitor parsing success rates
- A/B test BAML vs JSON modes

**Preventive Measures**:
1. **No breaking changes**: JSON mode always available as fallback
2. **Graceful degradation**: If BAML compilation fails, continue with JSON
3. **Clear migration path**: Dual mode for 2-3 releases before deprecating JSON
4. **Comprehensive tests**: Test both BAML and JSON modes
5. **Performance monitoring**: Ensure BAML doesn't slow down builds

## Implementation Steps

### Phase 1: Foundation (Priority: HIGH)
1. Add `baml-py==0.211.2` to requirements.txt
2. Create `tools/baml_schemas/` directory
3. Implement `phase_tracking.baml` schema
4. Create `tools/baml_integration.py` helper module
5. Implement BAML compilation and caching
6. Add unit tests for BAML compilation

### Phase 2: Phase Tracking (Priority: HIGH)
7. Implement PhaseInfo BAML validation
8. Update `_read_phase_info()` with BAML validation
9. Add `update_phase_baml()` MCP tool
10. Test phase tracking with BAML vs JSON
11. Verify backward compatibility

### Phase 3: Scout Integration (Priority: HIGH)
12. Implement `scout.baml` schema
13. Add Scout report generation with BAML
14. Update orchestrator prompt with Scout BAML usage
15. Test Scout report parsing
16. Validate structured output quality

### Phase 4: Architect Integration (Priority: MEDIUM)
17. Implement `architect.baml` schema
18. Add architecture generation with BAML
19. Update orchestrator prompt with Architect BAML usage
20. Test architecture blueprint parsing

### Phase 5: Builder Integration (Priority: MEDIUM)
21. Implement `builder.baml` schema
22. Add build task result validation
23. Update parallel builder prompts
24. Test builder output validation

### Phase 6: Testing (Priority: HIGH)
25. Comprehensive unit tests for all BAML schemas
26. Integration tests: Scout → Architect → Builder with BAML
27. Backward compatibility tests: JSON fallback
28. Performance tests: BAML vs JSON overhead
29. E2E test: Full build with BAML enabled

### Phase 7: Documentation (Priority: HIGH)
30. Create `docs/BAML_INTEGRATION.md`
31. Update README.md with BAML benefits
32. Add code examples to documentation
33. Document migration path (JSON → BAML)
34. Update CHANGELOG.md

### Phase 8: Example Project (Priority: MEDIUM)
35. Create `examples/baml-example-project/`
36. Show BAML usage in generated projects
37. Demonstrate type-safe LLM integration
38. Include in Context Foundry showcase

## Testing Requirements and Procedures

### Unit Tests (`tests/test_baml_integration.py`)

```python
def test_baml_compilation():
    """Test BAML schemas compile successfully"""

def test_phase_info_validation():
    """Test PhaseInfo BAML validation"""

def test_scout_report_generation():
    """Test structured Scout report"""

def test_architecture_blueprint():
    """Test architecture blueprint schema"""

def test_builder_task_result():
    """Test builder task result validation"""

def test_fallback_to_json():
    """Test graceful fallback if BAML unavailable"""

def test_caching():
    """Test BAML client caching"""
```

### Integration Tests

```python
def test_full_workflow_with_baml():
    """Test Scout → Architect → Builder with BAML"""

def test_backward_compatibility():
    """Test JSON mode still works"""

def test_phase_tracking_accuracy():
    """Test BAML phase tracking vs JSON"""

def test_multi_model_support():
    """Test BAML with different LLM providers"""
```

### Performance Tests

```python
def test_compilation_overhead():
    """Measure BAML compilation time"""

def test_parsing_performance():
    """Compare BAML vs JSON parsing speed"""

def test_memory_usage():
    """Measure BAML client memory footprint"""
```

### Success Criteria

**Must Pass:**
- ✅ All unit tests pass (100% coverage for new code)
- ✅ All integration tests pass
- ✅ Backward compatibility maintained (JSON mode works)
- ✅ No performance regression (< 5% overhead)
- ✅ Documentation complete and accurate

**Should Pass:**
- ✅ Phase tracking parsing errors reduced to <1% (from 5%)
- ✅ Scout report structure validation 100% successful
- ✅ Architecture blueprint validation 100% successful
- ✅ Compilation caching works (< 100ms cached client access)

**Nice to Have:**
- ✅ Example project demonstrates BAML value
- ✅ Boundary Studio observability working
- ✅ Migration guide clear and actionable

## Deployment Strategy

**Version**: v1.3.0 (feature release)

**Branch Strategy**:
1. Create feature branch: `enhancement/baml-integration`
2. Implement all phases on feature branch
3. Pass all tests (including self-healing loop)
4. Create PR to main with comprehensive description
5. Merge after review
6. Tag release: `v1.3.0`

**Release Notes Highlights**:
- 🎯 BAML Integration for Type-Safe LLM Outputs
- 📊 Improved Phase Tracking Reliability (5% → <1% errors)
- 🔧 Structured Scout/Architect/Builder Outputs
- 🔄 Backward Compatible (JSON fallback)
- 📖 Comprehensive Documentation
- ✅ Example Project Included

**Migration Path**:
- v1.3.0: BAML optional, JSON default (this release)
- v1.4.0: BAML default, JSON fallback
- v2.0.0: BAML required, JSON deprecated

## Risk Mitigation

**Risk 1: BAML Compilation Fails**
- **Mitigation**: Catch compilation errors, fallback to JSON mode gracefully
- **Detection**: Unit tests verify compilation, CI/CD catches failures

**Risk 2: Breaking Changes**
- **Mitigation**: Dual mode (BAML + JSON) for 2-3 releases
- **Detection**: Comprehensive backward compatibility tests

**Risk 3: Performance Regression**
- **Mitigation**: Client caching, pre-compilation during install
- **Detection**: Performance benchmarks in CI/CD

**Risk 4: User Confusion**
- **Mitigation**: BAML is internal implementation detail, transparent to users
- **Detection**: Documentation review, user feedback

**Risk 5: Dependency Issues**
- **Mitigation**: Pin baml-py version, test on multiple Python versions
- **Detection**: CI/CD matrix testing (Python 3.8, 3.9, 3.10, 3.11, 3.12)


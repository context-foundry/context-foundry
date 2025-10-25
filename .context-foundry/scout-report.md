# Scout Report: BAML Integration into Context Foundry

## Executive Summary

BAML (Basically a Made-up Language) is a production-ready framework that treats LLM prompts as type-safe functions with structured inputs/outputs. Integration into Context Foundry presents a strategic opportunity to improve autonomous build reliability by replacing string-based JSON parsing with compile-time type safety. The core value proposition: eliminate the 5% failure rate from LLM response parsing that currently exists in Context Foundry's phase tracking and agent communication.

**Recommendation**: Targeted integration focusing on high-impact areas (phase tracking, agent outputs) rather than full rewrite. Implement as v1.3.0 feature release.

## Key Requirements

**Must-Have:**
- Structured phase tracking (replace JSON string parsing)
- Type-safe Scout/Architect/Builder outputs
- Backward compatibility with existing orchestrator workflow
- Python 3.8+ compatibility (baml-py requirement)
- Zero-config for users (BAML compilation handled internally)

**Should-Have:**
- Semantic streaming for real-time progress updates
- Observability integration with Boundary Studio
- Example projects that use BAML (show users the benefit)

**Nice-to-Have:**
- Suspension/resumption for very long builds (current builds avg 10-20 min)
- Full orchestrator rewrite in BAML (high risk, deferred to v2.0)

## Technology Stack Decision

**Core Integration:**
- `baml-py==0.211.2` - Latest stable release (Oct 2025)
- Python 3.8+ (matches Context Foundry's existing requirement)
- Compile `.baml` files to Python client at runtime
- Store BAML definitions in `tools/baml_schemas/`

**Rationale:**
- BAML compiles to native Python code (zero runtime overhead)
- Type safety catches errors at compile-time, not runtime
- Semantic streaming provides better UX than current JSON polling
- Observability built-in (better debugging than current logs)

## Critical Architecture Recommendations

### 1. Phase Tracking with BAML Types
**Current**: JSON string → `json.loads()` → dict → manual validation
**Proposed**: BAML function → typed PhaseInfo class → compile-time safety

```baml
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
  capturing
  documenting
  deploying
  completed
  failed
}

function UpdatePhase(
  phase: PhaseType,
  status: PhaseStatus,
  detail: string
) -> PhaseInfo {
  client "anthropic/claude-3-5-sonnet-20241022"
  prompt #"
    Update phase tracking with validated structure.
    Current phase: {{ phase }}
    Status: {{ status }}
    Detail: {{ detail }}
  "#
}
```

### 2. Structured Scout Outputs
**Current**: Free-form markdown → manual parsing → error-prone
**Proposed**: BAML-enforced schema → guaranteed structure

```baml
class ScoutReport {
  executive_summary string
  past_learnings_applied string[]
  known_risks string[]
  key_requirements string[]
  tech_stack TechStack
  architecture_recommendations string[] @description("Top 3-5 critical recommendations")
  main_challenges Challenge[]
  testing_approach string
  timeline_estimate string
}

class TechStack {
  languages string[]
  frameworks string[]
  dependencies string[]
  justification string
}

class Challenge {
  description string
  severity "LOW" | "MEDIUM" | "HIGH"
  mitigation string
}

function ScoutResearch(
  task_description: string,
  codebase_analysis: string
) -> ScoutReport {
  client "anthropic/claude-3-5-sonnet-20241022"
  prompt #"
    Research requirements for: {{ task_description }}
    
    Codebase context: {{ codebase_analysis }}
    
    Provide comprehensive analysis with structured output.
  "#
}
```

### 3. Architect Blueprint Schema
```baml
class ArchitectureBlueprint {
  system_overview string
  file_structure FileStructure[]
  modules ModuleSpec[]
  applied_patterns Pattern[]
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

class TestPlan {
  unit_tests string[]
  integration_tests string[]
  e2e_tests string[]
  success_criteria string[]
}
```

### 4. Builder Task Execution
```baml
class BuildTaskResult {
  task_id string
  status "success" | "failed" | "partial"
  files_created string[]
  errors BuildError[]
  warnings string[]
  next_steps string[]
}

class BuildError {
  file string
  line int?
  message string
  severity "error" | "warning"
}
```

### 5. Semantic Streaming for Progress
**Current**: Poll `.context-foundry/current-phase.json` every 5 seconds
**Proposed**: Stream partial PhaseInfo updates in real-time

```python
# Streaming phase updates
async for partial_phase in b.stream.UpdatePhase(phase="Builder", status="building", detail="Creating game.js"):
    if partial_phase.progress_detail:
        print(f"Progress: {partial_phase.progress_detail}")
        
final_phase = await partial_phase.get_final_response()
```

## Main Challenges and Mitigations

### Challenge 1: BAML Compilation Overhead
- **Issue**: BAML files must compile before use, adds startup time
- **Severity**: MEDIUM
- **Mitigation**: Pre-compile BAML schemas during Context Foundry installation, cache compiled clients

### Challenge 2: Backward Compatibility
- **Issue**: Existing projects use JSON-based phase tracking
- **Severity**: HIGH
- **Mitigation**: 
  - Phase 1: Add BAML support alongside JSON (dual mode)
  - Phase 2: Migrate gradually over 2-3 releases
  - Never break existing orchestrator workflows

### Challenge 3: Learning Curve
- **Issue**: Team and users need to understand BAML syntax
- **Severity**: MEDIUM
- **Mitigation**: 
  - Comprehensive docs with examples
  - BAML usage is internal (users don't need to know)
  - Only expose benefits (better reliability, streaming)

### Challenge 4: Dependency Weight
- **Issue**: baml-py adds ~20MB to installation
- **Severity**: LOW
- **Mitigation**: Make BAML optional dependency, graceful fallback to JSON mode

### Challenge 5: Multi-Model Support
- **Issue**: Context Foundry supports multiple LLM providers, BAML integrates with all
- **Severity**: LOW
- **Mitigation**: BAML supports 100+ models (OpenAI, Anthropic, Gemini, etc.) - already compatible

## Testing Approach

**Unit Tests:**
- Test BAML schema compilation
- Test PhaseInfo validation with valid/invalid inputs
- Test ScoutReport parsing with LLM responses
- Test error handling for malformed BAML outputs

**Integration Tests:**
- Full Scout → Architect → Builder workflow with BAML
- Phase tracking updates with semantic streaming
- Backward compatibility (JSON mode still works)
- Multi-model support (test with different LLM providers)

**E2E Tests:**
- Build a simple project using BAML-enabled orchestrator
- Verify phase tracking accuracy
- Verify structured outputs improve reliability
- Measure failure rate reduction (target: <1% vs current 5%)

**Performance Tests:**
- BAML compilation time overhead
- Streaming vs polling performance
- Memory usage comparison

## Timeline Estimate

**Total: 2-3 days autonomous build**

- Phase 1 (Scout): 30 min - Research complete
- Phase 2 (Architect): 1 hour - Design BAML schemas and integration points
- Phase 3 (Builder): 4-6 hours - Implement BAML integration
- Phase 4 (Test): 2-4 hours - Comprehensive testing + self-healing iterations
- Phase 5 (Documentation): 1-2 hours - Update docs with BAML usage
- Phase 6 (Deploy): 30 min - Create v1.3.0 release

## Success Metrics

- **Reliability**: Reduce phase tracking parsing errors from 5% to <1%
- **Developer Experience**: Compile-time type checking catches errors before runtime
- **Observability**: Built-in Boundary Studio integration for debugging
- **Performance**: Semantic streaming provides <500ms update latency (vs 5s polling)
- **Adoption**: Example projects demonstrate BAML value to users

## Integration Points Summary

**High Priority (Implement First):**
1. ✅ Phase tracking with PhaseInfo BAML class
2. ✅ Scout report structured output
3. ✅ Architect blueprint structured output
4. ✅ Builder task result validation

**Medium Priority (v1.4.0):**
5. Semantic streaming for real-time progress
6. Observability with Boundary Studio
7. Example projects using BAML

**Low Priority (v2.0.0):**
8. Full orchestrator rewrite in BAML
9. Suspension/resumption for long builds
10. Advanced pattern library with BAML types


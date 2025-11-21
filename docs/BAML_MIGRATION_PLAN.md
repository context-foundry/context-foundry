# BAML Migration Plan: Structured Output for Context Foundry

## Executive Summary

Migrate agent-created JSON files from manual Write tool instructions to BAML structured output generation. This will improve reliability, reduce prompt tokens, and ensure schema compliance.

## Problem Statement

Currently, agents manually create JSON files using the Write tool following prompt instructions:
- Agents sometimes forget to create files (fallback code exists in `phase_execution.py`)
- Prompts contain verbose JSON format instructions (~150 tokens per phase)
- No automatic schema validation
- Manual validation code required in Python

## Solution: BAML Structured Output

Use BAML to generate validated JSON automatically:
- Guaranteed creation (no forgotten files)
- Schema enforcement at generation time
- Smaller prompts (remove JSON format instructions)
- Type-safe Python integration

---

## Migration Phases

### Phase 1: `current-phase.json` ✅ START HERE
**Priority:** CRITICAL
**Impact:** ALL 7 phases
**Risk:** LOW (fallback exists)
**Token Savings:** ~1,050 tokens/build

#### Current State
- Created manually by every phase using Write tool
- Python fallback in `phase_execution.py:320-322` if missing
- Prompts contain "REQUIRED FIRST STEP" instructions (~150 tokens each)

#### Target State
```baml
class ParallelBuildInfo {
  parallel_mode bool
  total_tasks int
  current_wave int
  max_wave int
  tasks_per_wave map<string, int>
  max_concurrent_agents int
}

class PhaseStatus {
  current_phase string
  phase_number int
  status string  // "in_progress" | "completed" | "failed"
  description string?
  timestamp string
  test_iteration int?
  parallel_build_info ParallelBuildInfo?
}

function UpdatePhaseStatus(
  phase_name: string,
  phase_number: int,
  status: string,
  description: string
) -> PhaseStatus {
  client GPT4
  prompt #"
    You are tracking the current phase of a multi-phase build system.

    Phase: {{ phase_name }}
    Phase Number: {{ phase_number }}
    Status: {{ status }}
    Description: {{ description }}

    Generate a phase status update with the current timestamp.
  "#
}
```

#### Implementation Steps
1. Create BAML schema file: `baml_src/phase_tracking.baml`
2. Update `phase_execution.py` to use BAML instead of fallback
3. Remove "REQUIRED FIRST STEP" from all 7 phase prompts
4. Test with 3-5 builds across different project types
5. Verify Glass Pane displays phases correctly

#### Success Criteria
- ✅ `current-phase.json` created in every phase
- ✅ Glass Pane shows phases correctly
- ✅ No "Warning: current-phase.json not created" messages
- ✅ Measured token reduction of ~1,000+ tokens/build

#### Rollback Plan
- Keep fallback code in `phase_execution.py` for 1 month
- If issues found, revert prompt changes
- BAML schema remains for future use

---

### Phase 2: `build-tasks.json`
**Priority:** HIGH
**Impact:** Architect phase only
**Risk:** MODERATE (complex dependencies)
**Token Savings:** ~200 tokens/build

#### Current State
- Created by Architect phase if Scout recommends parallel build
- Contains tasks with dependencies
- Manual validation in `phase_execution.py:770` for cyclic dependencies

#### Target State
```baml
class BuildTask {
  task_id string
  description string
  file_paths string[]
  dependencies string[]
  estimated_complexity string  // "low" | "medium" | "high"
}

class BuildPlan {
  parallel_build_enabled bool
  tasks BuildTask[]
  max_parallel_agents int?
  task_groups map<string, string[]>?
}

function CreateBuildPlan(
  architecture_summary: string,
  scout_parallel_recommendation: string,
  scout_reasoning: string
) -> BuildPlan {
  client GPT4
  prompt #"
    You are the Architect agent creating a build execution plan.

    Architecture:
    {{ architecture_summary }}

    Scout Recommendation: {{ scout_parallel_recommendation }}
    Reasoning: {{ scout_reasoning }}

    Create a build plan with tasks. If parallel build is recommended,
    define independent tasks with dependencies. Ensure no cyclic dependencies.
  "#
}
```

#### Implementation Steps
1. Create BAML schema: `baml_src/build_planning.baml`
2. Add cyclic dependency validation in BAML (or post-generation)
3. Update Architect prompt to use BAML function
4. Test with parallel and sequential builds
5. Verify parallel builds execute correctly

#### Success Criteria
- ✅ Valid `build-tasks.json` created when needed
- ✅ Dependency validation works
- ✅ Parallel builds complete successfully

---

### Phase 3: Feedback Phase JSONs
**Priority:** MEDIUM
**Impact:** Feedback phase only
**Risk:** LOW (non-critical to build)
**Token Savings:** ~300 tokens/build

#### Files to Migrate
1. `build-feedback-{timestamp}.json` - Build analysis
2. `common-issues.json` - Pattern learning

#### Target State
```baml
class Issue {
  title string
  description string
  severity string  // "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  phase_detected string
  phase_should_have_caught string?
  category string
  tags string[]
  solution_description string?
  prevention_strategy string?
}

class CommonIssuesPatterns {
  version string
  timestamp string
  patterns Issue[]
  total_builds int
  project_types string[]
}

function AnalyzeBuildFeedback(
  build_log: string,
  test_iterations: int,
  issues_encountered: string
) -> CommonIssuesPatterns {
  client GPT4
  prompt #"
    Analyze this build and extract patterns for future prevention.

    Build Log Summary:
    {{ build_log }}

    Test Iterations: {{ test_iterations }}

    Issues:
    {{ issues_encountered }}

    Extract common patterns and create preventive knowledge.
  "#
}
```

#### Implementation Steps
1. Create BAML schema: `baml_src/feedback_analysis.baml`
2. Update Feedback phase to use BAML
3. Ensure compatibility with pattern merging
4. Test feedback generation

---

### Phase 4: `session-summary.json`
**Priority:** LOW
**Impact:** Multiple phases
**Risk:** HIGH (complex, multi-phase updates)
**Token Savings:** Minimal (already uses `jq`)

#### Current State
- Updated incrementally by Deploy and Feedback phases
- Uses `jq` commands for updates (not pure agent creation)
- Complex nested structure

#### Recommendation
**DEFER** - This file is updated incrementally, not created from scratch. BAML is better suited for one-shot generation. Keep using `jq` for incremental updates.

---

## Implementation Timeline

### Week 1: Phase 1 Implementation
- Day 1-2: Create BAML schema, update phase_execution.py
- Day 3-4: Update all phase prompts
- Day 5: Testing and validation

### Week 2: Phase 1 Validation
- Run 10+ builds across different project types
- Monitor for issues
- Measure token savings
- Document results

### Week 3: Phase 2 (if Phase 1 successful)
- Implement build-tasks.json BAML migration
- Test parallel builds

### Week 4: Phase 3 (if Phase 2 successful)
- Implement feedback JSONs
- Validate pattern merging

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| BAML generation fails | Build fails | Keep Python fallback for 1 month |
| Schema mismatch with Glass Pane | Dashboard breaks | Extensive testing before rollout |
| Token usage doesn't decrease | No benefit | Measure before/after, rollback if needed |
| BAML adds latency | Slower builds | Benchmark, optimize prompts |

---

## Metrics to Track

### Before Migration
- Average prompt tokens per phase
- Build failure rate
- "current-phase.json not created" warnings

### After Migration
- Token reduction per phase
- Build failure rate (should stay same or improve)
- BAML generation latency
- Schema validation errors

---

## Rollback Procedures

### Phase 1 Rollback
1. Revert phase prompt changes (restore "REQUIRED FIRST STEP")
2. Keep BAML fallback in phase_execution.py
3. Remove BAML function calls
4. Test 3 builds to ensure stability

### Phase 2 Rollback
1. Revert Architect prompt
2. Remove BAML build plan function
3. Restore manual build-tasks.json creation

---

## Decision Points

After each phase:
1. **Measure token savings** - Is it ≥80% of projected?
2. **Check reliability** - Are builds more reliable?
3. **Assess complexity** - Is maintenance easier?

**GO/NO-GO Decision:** If any metric regresses significantly, stop and reassess.

---

## Appendix: Current vs. BAML Comparison

### Current Approach (current-phase.json)
```
Prompt: "Update .context-foundry/current-phase.json with..."
        + JSON structure example (150 tokens)
        + Field descriptions (50 tokens)
        = 200 tokens

Agent: Uses Write tool, manually constructs JSON
Risk: May forget, may malform JSON
```

### BAML Approach
```
Prompt: Removed (handled by BAML schema)
        = 0 tokens in phase prompt

BAML: Auto-generates from schema
Risk: Schema errors (caught at generation)
```

**Net Savings:** 200 tokens × 7 phases = 1,400 tokens/build

---

## Status

- [x] Phase 1: `current-phase.json` - **✅ COMPLETE** (2025-11-16)
  - ✅ BAML schema exists: `tools/baml_schemas/phase_tracking.baml`
  - ✅ Python integration exists: `tools/baml_integration.py`
  - ✅ Python already calls BAML: `phase_execution.py:311-322`
  - ✅ Removed redundant manual JSON instructions from all 7 phase prompts
    - `phase_4_test.md` (3 instances removed)
    - `phase_6_deployment.md` (2 instances removed)
    - `phase_7_feedback.md` (2 instances removed)
    - `phase_7_5_github.md` (2 instances removed)
    - `phase_4_5_screenshot.md` (2 instances removed)
    - `phase_5_documentation.md` (2 instances removed)
    - `phase_2_5_parallel_build.md` (1 instance removed)
  - ✅ Added BAML tracking notes to all phase prompts
  - **Result:** ~4,038 characters removed, estimated ~2,000 tokens saved per build
- [ ] Phase 2: `build-tasks.json` - READY TO START
- [ ] Phase 3: Feedback JSONs - BLOCKED (waiting for Phase 2)
- [ ] Phase 4: `session-summary.json` - DEFERRED

**Last Updated:** 2025-11-16
**Owner:** Context Foundry Team

## Discovery: Phase 1 Already Implemented!

During implementation, discovered that BAML phase tracking is **already active**:
- `tools/baml_integration.py:244-396` - `update_phase_with_baml()` function
- `tools/baml_schemas/phase_tracking.baml` - BAML schema
- `phase_execution.py:311-322` - Already calls BAML before each phase

**What's left:** Remove redundant prompt instructions telling agents to manually create `current-phase.json`

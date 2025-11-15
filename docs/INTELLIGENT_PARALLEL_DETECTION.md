# Intelligent Parallel Build Detection

**Status**: Proposed Enhancement
**Version**: 1.0
**Last Updated**: 2025-11-14

## Overview

Context Foundry currently requires users or AI agents to manually set `use_parallel=true` to enable parallel Builder execution. This enhancement proposes **automatic parallel detection** where the Scout phase analyzes project complexity and intelligently recommends whether to use parallel building.

## Current Limitations

### Manual Parallel Control

**Current Behavior**:
```python
# User must explicitly set use_parallel
autonomous_build_and_deploy(
    task="Build a full-stack app",
    use_parallel=False  # ← Defaults to false, no intelligence
)
```

**Problems**:
- ❌ `use_parallel` defaults to `false` (conservative, but slow)
- ❌ No automatic detection of project complexity
- ❌ Users/AI must guess when parallel would help
- ❌ Leads to slower builds for projects that would clearly benefit
- ❌ No analysis of whether parallel overhead is worth it

**Example Impact**:
- Glass Pane Dashboard: Could be 40% faster with parallel (8 min vs 13 min)
- But was built sequentially because `use_parallel` wasn't set
- Lost time: ~5 minutes per build

## Proposed Enhancement: Scout-Driven Parallel Detection

### Decision Flow

```
┌─────────────────────────────────────────────┐
│  User/AI submits build                      │
│  use_parallel=false (or not set)            │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  Scout Phase                                │
│  1. Analyzes task description               │
│  2. Estimates project structure             │
│  3. Detects module separation               │
│  4. Calculates complexity score             │
│  5. Recommends: parallel=true/false         │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  Scout writes recommendation                │
│  scout-report.md:                           │
│    parallel_recommended: true               │
│    parallel_reason: "React + FastAPI"       │
│    estimated_workers: 3                     │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  Architect Phase                            │
│  1. Reads Scout's recommendation            │
│  2. Overrides use_parallel if needed        │
│  3. Logs decision                           │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  Builder Phase                              │
│  Executes with appropriate parallelism      │
│  - use_parallel=true → 2-8 workers          │
│  - use_parallel=false → 1 worker            │
└─────────────────────────────────────────────┘
```

### Complexity Analysis Criteria

#### When Scout Recommends `use_parallel=true`

**High-Confidence Indicators**:
- ✅ **Frontend + Backend separation**
  - React + Express, Vue + FastAPI, Next.js + Django
  - Clear separation of concerns
- ✅ **Multiple microservices**
  - Auth service, Payment service, Notification service
  - Independent deployments
- ✅ **15+ files to create**
  - Large enough to justify coordination overhead
- ✅ **Clear module boundaries**
  - `frontend/`, `backend/`, `database/`, `deployment/`
  - Independent modules with minimal cross-dependencies
- ✅ **Independent components**
  - Authentication module, Payment processing, Email service
  - Can be built without waiting for each other
- ✅ **Full-stack applications**
  - Web app with API + Database + Deployment
- ✅ **Monorepo with multiple packages**
  - `packages/ui`, `packages/api`, `packages/shared`

**Complexity Score Formula**:
```python
score = 0
score += 30 if "frontend" and "backend" detected
score += 20 if microservices_count >= 2
score += 10 if estimated_files >= 15
score += 15 if has_clear_module_boundaries
score += 10 if has_deployment_files
score += 5 for each independent_component

# Recommend parallel if score >= 50
```

#### When Scout Keeps `use_parallel=false`

**Low-Complexity Indicators**:
- ✅ **Single-file utilities**
  - CLI tool in one Python/JS file
- ✅ **Simple scripts**
  - Automation scripts, data processing
- ✅ **<10 files total**
  - Too small for parallel overhead
- ✅ **Tightly coupled code**
  - Everything depends on everything
- ✅ **Single module/package**
  - No clear separation

**Example Tasks That Stay Sequential**:
```
"Create a Python script to parse CSV files"          → sequential
"Build a simple CLI todo app"                        → sequential
"Write a bash script to backup files"                → sequential
"Create a single-page calculator in HTML/JS"         → sequential
```

### Implementation Details

#### Scout Phase Changes

**New Analysis Step**:
```python
# In scout_agent_prompt.txt
"""
After analyzing the requirements, assess project complexity:

1. Detect module separation (frontend/backend/deployment)
2. Estimate file count based on similar projects
3. Identify independent components
4. Calculate complexity score

Output your recommendation in scout-report.md:

## Parallel Execution Recommendation

- **Parallel Recommended**: Yes/No
- **Reason**: [Brief explanation]
- **Estimated Workers**: 2-8
- **Complexity Score**: 65/100
- **Modules Detected**: Frontend (React), Backend (FastAPI), Deployment (NGINX)
"""
```

**Scout Report Format**:
```markdown
# Scout Report

## Project Analysis
...

## Parallel Execution Recommendation

- **Parallel Recommended**: ✅ Yes
- **Reason**: Detected React frontend + FastAPI backend with clear separation. Estimated 25+ files across 3 independent modules.
- **Estimated Workers**: 3
- **Complexity Score**: 65/100
- **Modules Detected**:
  - Frontend: React + Vite + TypeScript (~12 files)
  - Backend: FastAPI + SQLite (~8 files)
  - Deployment: NGINX + systemd (~5 files)
- **Time Savings Estimate**: 40% faster (8 min vs 13 min)
```

#### Architect Phase Changes

**Read Scout's Recommendation**:
```python
# In phase_execution.py - Architect phase
def execute_architect_phase(job_id, task, working_dir):
    # ... existing code ...

    # Read Scout's parallel recommendation
    scout_report = read_file(f"{working_dir}/.context-foundry/scout-report.md")
    parallel_recommended = parse_parallel_recommendation(scout_report)

    if parallel_recommended and not job.params.get("use_parallel"):
        logger.info(f"Scout recommended parallel execution, enabling for Builder phase")
        # Override job params
        job.params["use_parallel"] = True
        job.params["estimated_workers"] = parallel_recommended.get("workers", 3)

    # ... continue with architecture design ...
```

**Architect Logs Decision**:
```
[INFO] Scout analysis complete
[INFO] Complexity score: 65/100
[INFO] Recommendation: Enable parallel execution (3 workers)
[INFO] Reason: React frontend + FastAPI backend separation
[INFO] Updating Builder phase parameters: use_parallel=true
```

#### Build Submission Changes

**New Parameter: `auto_parallel`**:
```python
def autonomous_build_and_deploy(
    task: str,
    working_directory: str,
    use_parallel: bool = False,       # Manual override
    auto_parallel: bool = True,        # NEW: Let Scout decide
    max_workers: int = 8,
    **kwargs
):
    """
    Args:
        use_parallel: Force parallel execution (overrides Scout)
        auto_parallel: Let Scout analyze and recommend (default: True)
        max_workers: Maximum parallel workers (default: 8)
    """
```

**Decision Matrix**:
```python
if use_parallel == True:
    # User explicitly wants parallel → force it
    final_parallel = True
    reason = "User override"

elif auto_parallel == True:
    # Let Scout decide → analyze complexity
    final_parallel = scout_recommendation
    reason = f"Scout recommendation (score: {complexity_score})"

else:
    # Both disabled → stay sequential
    final_parallel = False
    reason = "Sequential mode (auto_parallel=False)"
```

## Additional Enhancements

### 1. Dynamic Worker Count

**Problem**: Currently spawns 2-8 workers without intelligence.

**Enhancement**: Scout estimates optimal worker count based on:
- Number of independent modules
- Estimated file count per module
- Project size (small/medium/large)

**Formula**:
```python
workers = min(
    max_workers,
    max(2, num_modules),  # At least 2, one per module
    max(2, estimated_files // 8)  # 1 worker per ~8 files
)

# Examples:
# 2 modules, 16 files → 2 workers
# 3 modules, 30 files → 3 workers
# 5 modules, 50 files → 6 workers (capped at max_workers)
```

### 2. Parallel Safety Checks

**Problem**: Parallel builds can fail if modules have hidden dependencies.

**Enhancement**: Scout identifies shared dependencies and warns:
```markdown
## Parallel Safety Analysis

⚠️ **Potential Conflicts Detected**:
- `shared/types.ts` used by both frontend and backend
- Recommendation: Build `shared/` first, then parallel build frontend + backend

**Execution Order**:
1. Sequential: Build shared types
2. Parallel: Frontend + Backend (depend on shared types)
3. Sequential: Deployment (depends on both)
```

**Build Strategy**:
- Phase 1 (sequential): Shared dependencies
- Phase 2 (parallel): Independent modules
- Phase 3 (sequential): Integration & deployment

### 3. Cost-Benefit Analysis

**Problem**: Parallel execution has overhead (spawning agents, coordination).

**Enhancement**: Scout estimates whether parallel is worth it:
```python
sequential_time = estimated_files * 30  # ~30s per file
parallel_time = (estimated_files / workers) * 30 + overhead
overhead = 60  # 1 min to spawn workers, coordinate

if (sequential_time - parallel_time) / sequential_time > 0.20:
    recommend_parallel = True  # >20% time savings
else:
    recommend_parallel = False  # Not worth overhead
```

**Example Calculation**:
```
Project: 30 files, 3 workers

Sequential: 30 files * 30s = 900s (15 min)
Parallel:   (30/3) * 30s + 60s = 360s (6 min)
Savings:    (900-360)/900 = 60% ✅ Recommend parallel

Project: 8 files, 2 workers

Sequential: 8 files * 30s = 240s (4 min)
Parallel:   (8/2) * 30s + 60s = 180s (3 min)
Savings:    (240-180)/240 = 25% ✅ Recommend parallel

Project: 5 files, 2 workers

Sequential: 5 files * 30s = 150s (2.5 min)
Parallel:   (5/2) * 30s + 60s = 135s (2.25 min)
Savings:    (150-135)/150 = 10% ❌ Not worth it (< 20% threshold)
```

### 4. Learning from History

**Problem**: Same types of projects are built repeatedly without learning.

**Enhancement**: Track parallel effectiveness in Context Codex:
```json
{
  "pattern_id": "pat-react-fastapi-001",
  "project_type": ["react", "fastapi", "full-stack"],
  "parallel_effectiveness": {
    "builds_with_parallel": 15,
    "builds_sequential": 3,
    "avg_time_parallel": "8.2 min",
    "avg_time_sequential": "13.5 min",
    "time_savings": "39%",
    "recommendation": "Always use parallel for React + FastAPI"
  }
}
```

**Scout Uses History**:
```markdown
## Historical Analysis

Found 15 similar projects (React + FastAPI):
- Average time with parallel: 8.2 min
- Average time sequential: 13.5 min
- **Recommendation**: ✅ Use parallel (proven 39% faster)
```

### 5. Test Phase Parallelism

**Current**: Test phase runs all tests sequentially.

**Enhancement**: Extend parallel concept to Test phase:
```markdown
## Test Strategy (Parallel)

**Independent Test Suites**:
- Worker 1: Unit tests (frontend)
- Worker 2: Unit tests (backend)
- Worker 3: Integration tests
- Worker 4: E2E tests

**Execution Time**:
- Sequential: 8 min (unit + integration + e2e)
- Parallel: 3 min (longest suite determines duration)
- Savings: 62%
```

**Scout Recommendation**:
```markdown
## Test Parallelization

- **Parallel Tests**: ✅ Yes
- **Test Suites**: 4 independent suites detected
- **Estimated Workers**: 4
- **Time Savings**: ~60%
```

### 6. Incremental Builds

**Problem**: Rebuilding entire project when only one module changed.

**Enhancement**: Detect which modules changed, only rebuild those:
```markdown
## Change Detection (Git Diff)

**Changed Modules**:
- ✅ `backend/routes.py` (modified)
- ✅ `backend/models.py` (modified)
- ⏭️ `frontend/` (unchanged - skip)
- ⏭️ `deployment/` (unchanged - skip)

**Build Strategy**:
- Only rebuild: Backend module
- Skip: Frontend, Deployment
- Estimated time: 2 min (vs 8 min full rebuild)
```

**Incremental Parallel**:
```python
# tools/mcp_utils/phase_execution.py
def detect_changed_modules(working_dir):
    """
    Use git diff to detect which modules changed since last build.
    Only rebuild changed modules.
    """
    changed_files = subprocess.check_output([
        "git", "diff", "--name-only", "HEAD~1"
    ]).decode().splitlines()

    modules = detect_modules(working_dir)  # frontend, backend, etc
    changed_modules = [m for m in modules if any(f.startswith(m) for f in changed_files)]

    return changed_modules
```

## Configuration

### Project-Level Configuration

```yaml
# .context-foundry/config.yaml
parallel_detection:
  # Enable Scout-driven parallel detection
  enabled: true

  # Minimum complexity thresholds
  min_files_for_parallel: 15
  min_modules_for_parallel: 2
  min_complexity_score: 50  # 0-100 scale

  # Worker limits
  max_workers: 8
  min_workers: 2

  # Cost-benefit threshold
  time_savings_threshold: 0.20  # 20% improvement required

  # Safety
  detect_shared_dependencies: true
  warn_on_conflicts: true

  # Learning
  use_historical_data: true
  save_build_metrics: true
```

### Global Defaults

```yaml
# ~/.context-foundry/config.yaml
defaults:
  auto_parallel: true  # Let Scout decide by default
  max_workers: 8
  parallel_threshold_score: 50
```

## Example Scenarios

### Scenario 1: Glass Pane Dashboard (Full-Stack)

**Task**: "Build a real-time dashboard with React frontend and FastAPI backend"

**Scout Analysis**:
```markdown
## Complexity Analysis

- **Modules Detected**: 3 (Frontend, Backend, Deployment)
- **Estimated Files**: 28
- **Complexity Score**: 75/100

**Module Breakdown**:
- Frontend: React + Vite + TypeScript (~15 files)
- Backend: FastAPI + SSE + SQLite (~10 files)
- Deployment: NGINX + systemd + Docker (~3 files)

**Parallel Recommendation**: ✅ Yes
- **Workers**: 3
- **Strategy**: Parallel build all modules
- **Time Estimate**: 8 min (vs 13 min sequential)
- **Savings**: 38%
```

**Result**: Build runs with `use_parallel=true, workers=3`

### Scenario 2: Simple CLI Tool

**Task**: "Create a Python CLI tool to parse CSV files"

**Scout Analysis**:
```markdown
## Complexity Analysis

- **Modules Detected**: 1 (Single Python file)
- **Estimated Files**: 3 (main.py, requirements.txt, README.md)
- **Complexity Score**: 15/100

**Parallel Recommendation**: ❌ No
- **Reason**: Too small for parallel overhead
- **Time Estimate**: 2 min (sequential)
- **Parallel Would Take**: 2.5 min (overhead not worth it)
```

**Result**: Build runs with `use_parallel=false`

### Scenario 3: Microservices Platform

**Task**: "Build a microservices platform with auth, payment, and notification services"

**Scout Analysis**:
```markdown
## Complexity Analysis

- **Modules Detected**: 5 (Auth, Payment, Notification, Gateway, Shared)
- **Estimated Files**: 45
- **Complexity Score**: 90/100

**Module Breakdown**:
- Auth Service: Node.js + JWT (~12 files)
- Payment Service: Python + Stripe (~10 files)
- Notification Service: Python + SendGrid (~8 files)
- API Gateway: NGINX + routing (~5 files)
- Shared: TypeScript types (~10 files)

**Dependency Analysis**:
⚠️ All services depend on `shared/types`

**Execution Strategy**:
1. **Phase 1 (Sequential)**: Build Shared types (2 min)
2. **Phase 2 (Parallel)**: Build Auth + Payment + Notification (5 min with 4 workers)
3. **Phase 3 (Sequential)**: Build API Gateway (2 min)

**Total Time**: 9 min (vs 25 min sequential)
**Savings**: 64%
```

**Result**: Build runs with phased parallel strategy

### Scenario 4: Documentation Update

**Task**: "Update the README.md and add API documentation"

**Scout Analysis**:
```markdown
## Complexity Analysis

- **Modules Detected**: 0 (Documentation only)
- **Estimated Files**: 2 (README.md, API.md)
- **Complexity Score**: 5/100

**Parallel Recommendation**: ❌ No
- **Reason**: Documentation-only change, no code build needed
- **Time Estimate**: 1 min
```

**Result**: Build runs with `use_parallel=false`

## Migration Guide

### For Users

**Before** (Manual):
```python
# You had to guess
autonomous_build_and_deploy(
    task="Build a full-stack app",
    use_parallel=True  # ← Manual guess
)
```

**After** (Automatic):
```python
# Scout decides for you
autonomous_build_and_deploy(
    task="Build a full-stack app"
    # auto_parallel=True by default → Scout will analyze
)
```

**Force Parallel** (Override):
```python
# You know better than Scout
autonomous_build_and_deploy(
    task="Build something",
    use_parallel=True  # ← Overrides Scout
)
```

**Disable Detection**:
```python
# Opt out of Scout analysis
autonomous_build_and_deploy(
    task="Build something",
    auto_parallel=False  # ← Scout won't analyze
)
```

### For Context Foundry Developers

**Phase Changes Required**:

1. **Scout Phase** (`tools/scout_agent_prompt.txt`):
   - Add complexity analysis section
   - Output parallel recommendation in scout-report.md

2. **Architect Phase** (`tools/mcp_utils/phase_execution.py`):
   - Read Scout's recommendation
   - Override `use_parallel` parameter if Scout recommends it

3. **MCP Server** (`tools/mcp_server.py`):
   - Add `auto_parallel` parameter (default: true)
   - Pass to build execution

4. **Complexity Analyzer** (NEW: `tools/mcp_utils/complexity_analyzer.py`):
   - Implement complexity scoring algorithm
   - Module detection logic
   - Dependency analysis

**Testing**:
```bash
# Test with auto-detection
cfd build "Create a React + FastAPI dashboard" ~/test-parallel

# Check Scout's recommendation
cat ~/test-parallel/.context-foundry/scout-report.md | grep "Parallel"

# Verify Architect used it
cfd logs <job-id> | grep "parallel"
```

## Benefits

### For Users
- ✅ **Faster builds automatically** - No need to guess when to use parallel
- ✅ **Better defaults** - Smart recommendations based on project complexity
- ✅ **Time savings** - 20-60% faster for complex projects
- ✅ **Still have control** - Can override Scout's recommendation

### For Context Foundry
- ✅ **Better UX** - "It just works" without configuration
- ✅ **Performance** - Automatically optimizes build time
- ✅ **Learning** - Builds pattern database of what works
- ✅ **Transparency** - Scout explains why it recommended parallel

### For The Ecosystem
- ✅ **Best practices** - Encourages modular architecture
- ✅ **Pattern sharing** - Successful strategies saved to Context Codex
- ✅ **Continuous improvement** - Gets smarter with every build

## Open Questions

1. **Should Scout recommendation be mandatory?**
   - Or should Architect have final say?
   - Current: Architect can override

2. **What's the right complexity threshold?**
   - Current proposal: 50/100
   - Should it be configurable per user?

3. **How to handle edge cases?**
   - Project has modules but they're tightly coupled
   - Should Scout detect coupling via import analysis?

4. **Should we support hybrid parallel?**
   - Some phases parallel, others sequential
   - Example: Parallel build, sequential test

5. **How to visualize this to users?**
   - Show Scout's reasoning in Glass Pane?
   - Real-time complexity score?

## Future Enhancements

1. **ML-Based Complexity Scoring**
   - Train model on historical builds
   - Predict optimal worker count

2. **Real-Time Worker Scaling**
   - Start with 2 workers
   - Scale up to 8 if tasks queue up

3. **Cross-Project Learning**
   - Share patterns across users (anonymized)
   - "90% of React+FastAPI projects benefit from 3 workers"

4. **Cost-Aware Parallelism**
   - Consider API costs (Claude API)
   - Balance speed vs cost

5. **Intelligent Retries**
   - If parallel fails, retry sequentially
   - Learn which projects have issues with parallel

## References

- [BUILD_MODES.md](BUILD_MODES.md) - Context Foundry build modes
- [PHASE_PROCESS_SPAWNING_DESIGN.md](PHASE_PROCESS_SPAWNING_DESIGN.md) - Phase execution design
- [GETTING_STARTED.md](GETTING_STARTED.md) - User guide

## Changelog

**v1.0 (2025-11-14)**:
- Initial proposal
- Core Scout-driven detection
- 6 additional enhancements
- Configuration design
- Migration guide

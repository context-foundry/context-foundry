# Context Foundry Workflow with BAML Integration

**Visual guide to Context Foundry's BAML-powered JSON-first architecture**

---

## Table of Contents

1. [Overview](#overview)
2. [Complete Pipeline Flow](#complete-pipeline-flow)
3. [Phase-by-Phase Breakdown](#phase-by-phase-breakdown)
4. [Architecture Parsing: Dual-Mode System](#architecture-parsing-dual-mode-system)
5. [Data Flow Diagrams](#data-flow-diagrams)
6. [BAML Schema Hierarchy](#baml-schema-hierarchy)
7. [Error Handling & Graceful Degradation](#error-handling--graceful-degradation)

---

## Overview

Context Foundry uses a **JSON-first architecture** powered by [BAML (Boundary ML)](https://github.com/BoundaryML/baml) to ensure type-safe, validated outputs across all build phases. This eliminates the fragility of markdown parsing and provides compile-time guarantees for data structure.

### Key Concepts

**Markdown = Human-Readable Documentation**
- Scout creates `scout-report.md` (5-20KB of analysis)
- Architect creates `architecture.md` (30-90KB of design)
- These are preserved for human review and debugging

**JSON = Machine-Readable Data**
- BAML parses markdown → validated JSON
- Phases consume JSON for precise understanding
- Type-safe schemas guarantee structure

**Dual Output Strategy**
- Markdown for humans (readable, versionable)
- JSON for agents (structured, validated)

---

## Complete Pipeline Flow

```mermaid
graph TD
    START[User Request: Build X] --> DAEMON[CF Daemon Job Queue]
    DAEMON --> PHASE1[Phase 1: Scout Agent]

    PHASE1 --> SCOUT_MD[scout-report.md]
    SCOUT_MD --> BAML_SCOUT[BAML Parse Scout]
    BAML_SCOUT --> SCOUT_JSON[scout_report.json]

    SCOUT_JSON --> PHASE2[Phase 2: Architect Agent]
    PHASE2 --> ARCH_MD[architecture.md]
    ARCH_MD --> DUAL_PARSE{Dual-Mode Parse}

    DUAL_PARSE -->|Priority 1| CLI_PARSE[Claude CLI Parse]
    CLI_PARSE -->|Success| ARCH_JSON[architecture.json]
    CLI_PARSE -->|Timeout/Fail| BAML_ARCH[BAML Fallback Parse]
    BAML_ARCH --> ARCH_JSON
    DUAL_PARSE -->|Both Fail| FALLBACK[Graceful Degradation]
    FALLBACK --> PHASE3_MD[Builder uses .md]

    ARCH_JSON --> BAML_PLAN[BAML CreateBuildPlan]
    BAML_PLAN --> BUILD_TASKS[build-tasks.json]
    BUILD_TASKS --> PHASE3[Phase 3: Builder Agent]

    PHASE3 --> PARALLEL{Parallel Recommended?}
    PARALLEL -->|Yes| MULTI_BUILDERS[Phase 2.5: Parallel Builders]
    PARALLEL -->|No| SINGLE_BUILDER[Sequential Build]

    MULTI_BUILDERS --> INTEGRATION[Phase 3: Integration]
    SINGLE_BUILDER --> INTEGRATION
    PHASE3_MD --> INTEGRATION

    INTEGRATION --> PHASE4[Phase 4: Test Agent]
    PHASE4 --> TEST_PASS{Tests Pass?}

    TEST_PASS -->|No, Iter < 3| HEAL[Self-Healing Loop]
    HEAL --> PHASE2
    TEST_PASS -->|Yes| PHASE5[Phase 5: Screenshot]
    TEST_PASS -->|No, Max Iter| FAIL[Report Failure]

    PHASE5 --> PHASE6[Phase 6: Documentation]
    PHASE6 --> PHASE7[Phase 7: Deploy]
    PHASE7 --> PHASE8[Phase 8: Feedback]
    PHASE8 --> DONE[Build Complete]

    style BAML_SCOUT fill:#e3f2fd
    style BAML_ARCH fill:#e3f2fd
    style BAML_PLAN fill:#e3f2fd
    style SCOUT_JSON fill:#c8e6c9
    style ARCH_JSON fill:#c8e6c9
    style BUILD_TASKS fill:#c8e6c9
    style DUAL_PARSE fill:#fff3e0
    style HEAL fill:#ffebee
    style DONE fill:#c8e6c9
```

**Legend:**
- 🔵 Blue boxes = BAML processing
- 🟢 Green boxes = JSON outputs
- 🟡 Yellow diamonds = Decision points
- 🔴 Red boxes = Error handling

---

## Phase-by-Phase Breakdown

### Phase 1: Scout Research

**Purpose:** Analyze requirements, research codebase, identify risks

```mermaid
sequenceDiagram
    participant User
    participant ScoutAgent
    participant BAML
    participant FileSystem

    User->>ScoutAgent: Task description
    ScoutAgent->>ScoutAgent: Research requirements
    ScoutAgent->>ScoutAgent: Analyze codebase (if exists)
    ScoutAgent->>ScoutAgent: Check global patterns
    ScoutAgent->>FileSystem: Write scout-report.md

    Note over ScoutAgent,BAML: BAML Validation Step
    ScoutAgent->>BAML: parse_scout_markdown_baml(md_content)
    BAML->>BAML: Validate against ScoutReport schema
    BAML->>FileSystem: Write scout_report.json

    FileSystem-->>ScoutAgent: scout_report.json ready
    ScoutAgent->>User: Scout phase complete
```

**Outputs:**
- `scout-report.md` - Human-readable analysis (5-20KB)
- `scout_report.json` - Type-safe structured data (ScoutReport schema)

**JSON Structure:**
```json
{
  "executive_summary": "string",
  "past_learnings_applied": ["string"],
  "known_risks": ["string"],
  "key_requirements": ["string"],
  "tech_stack": {
    "languages": ["python", "typescript"],
    "frameworks": ["fastapi", "react"],
    "databases": ["postgresql"]
  },
  "architecture_recommendations": ["string"],
  "main_challenges": [
    {
      "challenge": "CORS with external API",
      "severity": "MEDIUM",
      "mitigation": "Backend proxy pattern"
    }
  ],
  "testing_approach": "string",
  "timeline_estimate": "7-10 minutes"
}
```

---

### Phase 2: Architect Design

**Purpose:** Design system architecture, plan implementation

```mermaid
sequenceDiagram
    participant FileSystem
    participant ArchitectAgent
    participant ClaudeCLI
    participant BAML

    FileSystem->>ArchitectAgent: Read scout_report.json
    ArchitectAgent->>ArchitectAgent: Design architecture
    ArchitectAgent->>ArchitectAgent: Plan modules & files
    ArchitectAgent->>ArchitectAgent: Apply patterns
    ArchitectAgent->>FileSystem: Write architecture.md

    Note over ArchitectAgent,BAML: Dual-Mode Parsing
    ArchitectAgent->>ClaudeCLI: Try: claude --print parse

    alt Claude CLI Success
        ClaudeCLI->>FileSystem: Write architecture.json
        ClaudeCLI-->>ArchitectAgent: Success ($0 cost)
    else Claude CLI Timeout/Fail
        ClaudeCLI->>BAML: Fallback to BAML
        BAML->>BAML: parse_architecture_markdown_baml()
        BAML->>FileSystem: Write architecture.json
        BAML-->>ArchitectAgent: Success (~$0.03 cost)
    else Both Fail
        ArchitectAgent->>ArchitectAgent: Warn: JSON unavailable
        ArchitectAgent-->>ArchitectAgent: Builder will use .md
    end

    ArchitectAgent->>User: Architect phase complete
```

**Outputs:**
- `architecture.md` - Human-readable design (30-90KB)
- `architecture.json` - Type-safe blueprint (ArchitectureBlueprint schema)

**JSON Structure:**
```json
{
  "system_overview": "string",
  "file_structure": [
    {
      "path": "src/main.py",
      "purpose": "Application entry point",
      "dependencies": ["config", "routes"]
    }
  ],
  "modules": [
    {
      "name": "authentication",
      "purpose": "JWT-based user auth",
      "files": ["auth/jwt_handler.py", "auth/middleware.py"],
      "dependencies": ["database", "config"]
    }
  ],
  "applied_patterns": [
    {
      "pattern_id": "cors-external-api-backend-proxy",
      "reason": "External API requires CORS handling"
    }
  ],
  "preventive_measures": ["string"],
  "implementation_steps": ["string"],
  "test_plan": {
    "unit_tests": ["string"],
    "integration_tests": ["string"],
    "e2e_tests": ["string"]
  },
  "success_criteria": ["string"]
}
```

---

### Phase 2.5: Build Planning (Parallel Decision)

**Purpose:** Analyze architecture and create parallel execution plan

```mermaid
sequenceDiagram
    participant FileSystem
    participant Orchestrator
    participant BAML

    FileSystem->>Orchestrator: Read architecture.json
    Orchestrator->>BAML: create_build_plan(architecture)
    BAML->>BAML: Analyze module dependencies
    BAML->>BAML: Detect parallel opportunities
    BAML->>BAML: Estimate task durations
    BAML->>FileSystem: Write build-tasks.json

    FileSystem-->>Orchestrator: build-tasks.json ready

    alt Parallel Recommended
        Orchestrator->>Orchestrator: Spawn 2-8 Builder agents
        Orchestrator->>Orchestrator: Assign tasks by dependency graph
    else Sequential Build
        Orchestrator->>Orchestrator: Spawn single Builder agent
    end
```

**Outputs:**
- `build-tasks.json` - Parallel execution plan (BuildPlan schema)

**JSON Structure:**
```json
{
  "parallel_build_enabled": true,
  "tasks": [
    {
      "task_id": "task_001",
      "description": "Implement authentication module",
      "files": ["auth/jwt_handler.py", "auth/middleware.py"],
      "dependencies": ["task_000"],
      "estimated_duration_minutes": 2
    }
  ],
  "total_estimated_sequential": 10,
  "total_estimated_parallel": 4,
  "time_savings_percent": 60
}
```

---

### Phase 3: Builder Implementation

**Purpose:** Write code, create tests, implement design

```mermaid
sequenceDiagram
    participant FileSystem
    participant BuilderAgent

    FileSystem->>BuilderAgent: Read architecture.json (preferred)
    alt architecture.json available
        BuilderAgent->>BuilderAgent: Parse structured blueprint
        BuilderAgent->>BuilderAgent: Precise implementation
    else architecture.json missing
        FileSystem->>BuilderAgent: Fallback to architecture.md
        BuilderAgent->>BuilderAgent: Parse markdown (less precise)
    end

    FileSystem->>BuilderAgent: Read build-tasks.json
    BuilderAgent->>BuilderAgent: Implement assigned tasks
    BuilderAgent->>FileSystem: Write source files
    BuilderAgent->>FileSystem: Write test files
    BuilderAgent->>BuilderAgent: Log progress

    BuilderAgent->>User: Builder phase complete
```

---

## Architecture Parsing: Dual-Mode System

Context Foundry uses a **dual-mode parsing strategy** to maximize reliability while minimizing cost.

### Mode 1: Claude CLI (Priority 1)

```mermaid
graph LR
    A[architecture.md] --> B{Claude CLI Available?}
    B -->|Yes| C[claude --print parse]
    C --> D{Success?}
    D -->|Yes| E[architecture.json]
    D -->|Timeout 5min| F[Fallback to BAML]
    D -->|Error| F
    B -->|No| F

    style C fill:#c8e6c9
    style E fill:#4caf50
    style F fill:#fff3e0
```

**Advantages:**
- ✅ Fast: Uses subscription, no API delay
- ✅ Free: $0 additional cost
- ✅ 5-minute timeout (sufficient for most)

**Command:**
```bash
claude --print --dangerously-skip-permissions << 'EOF'
Read architecture.md and extract structured JSON matching ArchitectureBlueprint schema.

Output only valid JSON, no markdown fences.
EOF
```

### Mode 2: BAML Fallback (Priority 2)

```mermaid
graph LR
    A[Claude CLI Failed] --> B[BAML parse_architecture_markdown_baml]
    B --> C{Validation}
    C -->|Schema Valid| D[architecture.json]
    C -->|Timeout 10min| E[Graceful Degradation]
    C -->|Invalid| E

    style B fill:#e3f2fd
    style D fill:#4caf50
    style E fill:#ffebee
```

**Advantages:**
- ✅ Reliable: Type-safe schema validation
- ✅ 10-minute timeout (handles complex architectures)
- ✅ Guaranteed structure

**Cost:** ~$0.03 per parse (10K tokens)

**Code:**
```python
from tools.baml_integration import parse_architecture_markdown_baml

architecture_json = parse_architecture_markdown_baml(
    markdown_content=arch_md_content,
    timeout=600  # 10 minutes
)
```

### Mode 3: Graceful Degradation

If both modes fail, the system continues with markdown:

```python
if architecture_json is None:
    logger.warning("⚠️  Architecture JSON unavailable, using .md fallback")
    # Builder reads architecture.md directly
    # Warns but doesn't fail the build
```

---

## Data Flow Diagrams

### Scout → Architect Data Flow

```mermaid
graph LR
    A[User Task] --> B[Scout Agent]
    B --> C[scout-report.md]
    C --> D[BAML Parse]
    D --> E[scout_report.json]
    E --> F[Architect Agent]

    E -.-> G[tech_stack]
    E -.-> H[known_risks]
    E -.-> I[key_requirements]
    E -.-> J[architecture_recommendations]

    G --> F
    H --> F
    I --> F
    J --> F

    F --> K[architecture.md]

    style E fill:#c8e6c9
    style F fill:#fff3e0
```

### Architect → Builder Data Flow

```mermaid
graph LR
    A[Architect Agent] --> B[architecture.md]
    B --> C{Dual Parse}

    C -->|CLI| D1[Claude CLI]
    C -->|Fallback| D2[BAML]

    D1 --> E[architecture.json]
    D2 --> E
    C -->|Both Fail| F[.md fallback]

    E --> G[BAML CreateBuildPlan]
    G --> H[build-tasks.json]

    H -.-> I[Task Graph]
    H -.-> J[Dependencies]
    H -.-> K[Parallel Strategy]

    E --> L[Builder Agent]
    H --> L
    F -.-> L

    style E fill:#c8e6c9
    style H fill:#c8e6c9
    style L fill:#fff3e0
```

### Phase Tracking Data Flow

```mermaid
sequenceDiagram
    participant Phase
    participant BAML
    participant FileSystem
    participant Dashboard

    Phase->>BAML: update_phase_with_baml("Scout", "researching", "...")
    BAML->>BAML: Create PhaseInfo object
    BAML->>BAML: Inject real timestamps
    BAML->>FileSystem: Write current-phase.json
    FileSystem-->>Dashboard: Read current-phase.json
    Dashboard->>Dashboard: Display live status

    Note over Phase,Dashboard: Real-time progress updates
```

---

## BAML Schema Hierarchy

```mermaid
graph TD
    A[BAML Schemas] --> B[scout.baml]
    A --> C[architect.baml]
    A --> D[builder.baml]
    A --> E[build_planning.baml]
    A --> F[phase_tracking.baml]
    A --> G[clients.baml]

    B --> B1[ScoutReport]
    B --> B2[TechStack]
    B --> B3[Challenge]

    C --> C1[ArchitectureBlueprint]
    C --> C2[ModuleSpec]
    C --> C3[TestPlan]

    D --> D1[BuildTaskResult]
    D --> D2[BuildError]

    E --> E1[BuildPlan]
    E --> E2[BuildTask]

    F --> F1[PhaseInfo]
    F --> F2[PhaseType enum]
    F --> F3[PhaseStatus enum]

    G --> G1[GPT4oMini client]
    G --> G2[Claude client]
    G --> G3[O4 client]

    style A fill:#e3f2fd
    style B fill:#c8e6c9
    style C fill:#c8e6c9
    style D fill:#c8e6c9
    style E fill:#c8e6c9
    style F fill:#c8e6c9
    style G fill:#fff3e0
```

**Schema Compilation:**
```bash
# BAML compiles .baml files → Python client code
tools/baml_src/
├── scout.baml
├── architect.baml
├── builder.baml
├── build_planning.baml
├── phase_tracking.baml
└── clients.baml

# Generated Python client
tools/baml_client/
├── types.py               # All schema classes
├── sync_client.py         # Generated sync client
└── async_client.py        # Generated async client
```

---

## Error Handling & Graceful Degradation

### Parsing Error Flow

```mermaid
graph TD
    A[Markdown Generated] --> B{BAML Parse}
    B -->|Success| C[JSON Available]
    B -->|Timeout| D{Retry?}
    B -->|Validation Error| D

    D -->|No| E[Graceful Degradation]
    D -->|Yes| F[BAML Fallback]
    F --> B

    E --> G[Warn User]
    E --> H[Use Markdown Fallback]
    E --> I[Build Continues]

    C --> J[Type-Safe Operations]
    H --> K[Best-Effort Parsing]

    style C fill:#c8e6c9
    style E fill:#fff3e0
    style J fill:#4caf50
    style K fill:#ff9800
```

### Error Types & Handling

| Error Type | BAML Response | Fallback Behavior |
|-----------|---------------|-------------------|
| **Timeout** | BamlClientTimeoutError | Retry with BAML (if Claude CLI), then .md fallback |
| **Validation** | BamlValidationError | Log schema mismatch, use .md fallback |
| **Missing Fields** | Partial validation | Use available fields, warn about missing |
| **API Failure** | BamlClientError | Skip JSON, use .md fallback |
| **Both Modes Fail** | None | Graceful degradation to markdown parsing |

**Code Example:**
```python
try:
    architecture_json = parse_architecture_with_claude_cli(md_content)
except (TimeoutError, subprocess.CalledProcessError):
    logger.warning("Claude CLI failed, falling back to BAML...")
    try:
        architecture_json = parse_architecture_baml_with_timeout(md_content)
    except BamlValidationError as e:
        logger.error(f"BAML validation failed: {e}")
        architecture_json = None

if architecture_json is None:
    logger.warning("⚠️  JSON unavailable, using markdown fallback")
    # Builder reads architecture.md directly
```

---

## Performance Metrics

### JSON vs Markdown Comparison

| Metric | Markdown-Only | JSON-First (BAML) |
|--------|---------------|-------------------|
| **Parsing Errors** | ~5% | <1% |
| **Type Safety** | Runtime only | Compile-time + runtime |
| **Field Guarantees** | None | Schema-enforced |
| **IDE Support** | Limited | Full autocomplete |
| **Queryability** | grep/awk | jq/JSON tools |
| **Validation** | Manual | Automatic |
| **First-Try Success** | Variable | Significantly improved |

### Cost Analysis

| Component | Cost per Build | Notes |
|-----------|---------------|-------|
| **Scout Parsing** | ~$0.06 | 1 BAML call, 5K tokens |
| **Architecture Parsing (CLI)** | $0.00 | Uses subscription |
| **Architecture Parsing (BAML)** | ~$0.03 | Fallback only, 10K tokens |
| **Build Planning** | ~$0.02 | 1 BAML call, 2K tokens |
| **Phase Tracking (15 calls)** | ~$0.003 | 200 tokens each |
| **Total BAML Cost** | **~$0.11-$0.20** | Depending on fallback usage |
| **Main Build System** | **$0.00** | Runs on subscription |

**Bottom Line:** BAML adds ~$0.20/build for type safety while the entire build system ($200K+ tokens) runs free on your Claude Code subscription.

---

## BAML Integration Benefits

### Before BAML (Markdown-Only)

```python
# Fragile string parsing
response = agent.complete("Generate architecture")
# Hope it's valid JSON
architecture = json.loads(response)  # May fail!
# Hope it has the fields we need
file_structure = architecture.get("file_structure", [])  # May be missing!
```

**Problems:**
- ❌ ~5% parsing failures
- ❌ No schema guarantees
- ❌ Runtime errors only
- ❌ Manual validation needed

### After BAML (JSON-First)

```python
# Type-safe structured output
from tools.baml_client import b

architecture = b.CreateArchitectureBlueprint(
    task=task_description,
    scout_findings=scout_json
)

# Guaranteed to have all fields
file_structure = architecture.file_structure  # Type-safe!
modules = architecture.modules  # Guaranteed list!
test_plan = architecture.test_plan  # Validated TestPlan object!
```

**Benefits:**
- ✅ <1% parsing failures
- ✅ Compile-time schema validation
- ✅ IDE autocomplete
- ✅ Type hints and documentation

---

## Visual Summary

```mermaid
graph TB
    subgraph "Context Foundry with BAML"
        A[User Request] --> B[Scout Agent]
        B --> C[scout-report.md + scout_report.json]
        C --> D[Architect Agent]
        D --> E[architecture.md + architecture.json]
        E --> F[Builder Agent]
        F --> G[build-tasks.json]
        G --> H[Code Implementation]
        H --> I[Test → Deploy]
    end

    subgraph "BAML Type Safety Layer"
        J[ScoutReport schema]
        K[ArchitectureBlueprint schema]
        L[BuildPlan schema]
        M[PhaseInfo schema]
    end

    C -.validates.-> J
    E -.validates.-> K
    G -.validates.-> L

    style C fill:#c8e6c9
    style E fill:#c8e6c9
    style G fill:#c8e6c9
    style J fill:#e3f2fd
    style K fill:#e3f2fd
    style L fill:#e3f2fd
```

---

## References

- **BAML Documentation:** https://docs.boundaryml.com
- **BAML GitHub:** https://github.com/BoundaryML/baml
- **Context Foundry BAML Integration:** [docs/BAML_INTEGRATION.md](BAML_INTEGRATION.md)
- **Schema Definitions:** `tools/baml_src/`
- **Generated Client:** `tools/baml_client/`

---

**Last Updated:** November 23, 2025 (v2.4.0)

**Credits:**
- BAML framework by Boundary ML
- Visual diagrams created with Mermaid.js

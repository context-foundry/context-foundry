# Context Foundry - Agent Orchestration Flow

```mermaid
sequenceDiagram
    autonumber

    box rgb(230, 240, 250) User Environment
        participant User
    end

    box rgb(240, 248, 255) Context Foundry
        participant MCP as MCP Server
        participant Orch as Orchestrator
    end

    box rgb(245, 255, 245) AI Agents
        participant Scout
        participant Arch as Architect
        participant Build as Builder
        participant Test as Tester
    end

    box rgb(255, 245, 238) Knowledge Layer
        participant Patterns as Pattern<br/>Learning
        participant S3 as S3 Community<br/>Patterns
    end

    User->>MCP: Task Request via MCP Protocol
    activate MCP
    MCP->>Orch: Route to Orchestrator
    activate Orch

    Note over Orch: Load phase prompts<br/>tools/prompts/phases/

    Orch->>Scout: Spawn fresh context (200K)
    activate Scout
    Scout-->>Scout: Analyze task & codebase
    Scout->>Orch: scout-report.md
    deactivate Scout

    Note over Orch: Context: 2,022 tokens (1%)

    Orch->>Arch: Spawn fresh context (200K)
    activate Arch
    Arch-->>Arch: Design architecture (BAML)
    Arch->>Orch: architecture.json + .md
    deactivate Arch

    Note over Arch: Decision: parallel_build_enabled?

    alt Parallel Build Enabled
        Orch->>Build: Spawn main + worker threads
        activate Build
        Build-->>Build: ThreadPoolExecutor (max 5)
        par Worker 1
            Build-->>Build: Build modules 1-3
        and Worker 2
            Build-->>Build: Build modules 4-6
        and Worker 3
            Build-->>Build: Build modules 7-9
        end
        Build->>Orch: Source files + build-tasks.json
        deactivate Build
    else Sequential Build
        Orch->>Build: Spawn single builder
        activate Build
        Build-->>Build: Build all modules
        Build->>Orch: Source files
        deactivate Build
    end

    Orch->>Test: Spawn fresh context (200K)
    activate Test
    Test-->>Test: Run pytest/Jest/Playwright

    alt Tests Pass
        Test->>Orch: test-report.md (PASSED)
        deactivate Test
    else Tests Fail (max 3 iterations)
        Test->>Arch: test-report.md (FAILED)
        activate Arch
        Arch->>Build: architecture-fix.md
        activate Build
        Build->>Test: Fixed source files
        deactivate Build
        deactivate Arch
        Test->>Orch: test-report.md (PASSED)
        deactivate Test
    end

    Orch->>Patterns: Extract learned patterns
    activate Patterns
    Patterns->>S3: Sync to community repository
    activate S3
    S3-->>Patterns: Confirmation
    deactivate S3
    Patterns->>Orch: Pattern metrics updated
    deactivate Patterns

    Orch->>MCP: Build complete + artifacts
    deactivate Orch
    MCP->>User: Success response + GitHub URL
    deactivate MCP
```

## Key Architecture Points

| Component | Role | Fresh Context |
|-----------|------|---------------|
| MCP Server | Protocol handler, routes requests | N/A |
| Orchestrator | Coordinates phases, manages handoffs | Persistent |
| Scout | Analyzes task, identifies patterns | Yes (200K) |
| Architect | Designs system, BAML validation | Yes (200K) |
| Builder | Implements code, parallel workers | Yes (200K each) |
| Tester | Validates, triggers feedback loop | Yes (200K) |
| Pattern Learning | Extracts skills, syncs to S3 | N/A |

## Context Window Zones

```
Green  (0-40%)  : SMART - All phases target this
Yellow (40-70%) : ACCEPTABLE
Orange (70-90%) : DUMB - Avoided
Red    (90-100%): CRITICAL - Build fails
```

## Typical Token Usage

- Scout: 2,022 tokens (1%)
- Architect: 6,670 tokens (3.3%)
- Builder: 5,094 tokens (2.5%)
- Tester: 3,510 tokens (1.8%)

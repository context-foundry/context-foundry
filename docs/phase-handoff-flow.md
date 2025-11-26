# Context Foundry Inter-Phase Data Contract

> *"Generate probabilistically, validate deterministically."*

This document illustrates how Context Foundry enforces strict adherence to rules through structured JSON handoffs between phases.

## Phase Handoff Table

| Phase | Input Source | Primary Input | Fallback Input | Output Produced | Key Fields |
|-------|--------------|---------------|----------------|-----------------|------------|
| **Scout** | User task | Task description | - | `scout-report.md` → parsed to `SCOUT_JSON` | `executive_summary`, `key_requirements`, `tech_stack`, `architecture_recommendations`, `main_challenges`, `testing_approach` |
| **Architect** | Scout | `SCOUT_JSON` (injected) | `.context-foundry/scout-report.md` | `architecture.json` / `architecture.md` → `ARCHITECTURE_JSON` | `system_overview`, `file_structure`, `modules`, `implementation_steps`, `test_plan` |
| **Builder** | Architect | `ARCHITECTURE_JSON` (injected) | `.context-foundry/architecture.md` | Source code + `build-tasks.json` | `tasks[]`, `dependencies`, `status` |
| **Test** | Architect + Builder | `ARCHITECTURE_JSON.test_plan` | `.context-foundry/architecture.md` | `test-report-{N}.md` | `PASSED`/`FAILED`, iteration count |

---

## Phase Flow Diagram

```mermaid
flowchart TB
    subgraph ORCHESTRATOR["Orchestrator (autonomous_build.py)"]
        direction TB
        PARSE1[/"Parse MD -> JSON"/]
        PARSE2[/"Parse MD -> JSON"/]
        INJECT1[/"Inject into instruction"/]
        INJECT2[/"Inject into instruction"/]
    end

    subgraph SCOUT["Scout Phase"]
        S_IN[Task Description]
        S_AGENT[Scout Agent<br/>phase_scout.txt]
        S_OUT1[scout-report.md]
        S_OUT2[.context-foundry/<br/>scout_report.json]
    end

    subgraph ARCHITECT["Architect Phase"]
        A_IN[SCOUT_JSON]
        A_AGENT[Architect Agent<br/>phase_architect.txt]
        A_OUT1[architecture.md]
        A_OUT2[.context-foundry/<br/>architecture.json]
    end

    subgraph BUILDER["Builder Phase"]
        B_IN[ARCHITECTURE_JSON]
        B_AGENT[Builder Agent<br/>phase_builder.txt]
        B_OUT1[Source Code]
        B_OUT2[.context-foundry/<br/>build-tasks.json]
    end

    subgraph TEST["Test Phase"]
        T_IN[ARCHITECTURE_JSON.test_plan]
        T_AGENT[Test Agent<br/>phase_test.txt]
        T_OUT[test-report-N.md]
    end

    subgraph ARTIFACTS[".context-foundry/"]
        ART1[(scout_report.json)]
        ART2[(architecture.json)]
        ART3[(build-tasks.json)]
        ART4[(current-phase.json)]
        ART5[(session-summary.json)]
    end

    %% Scout Flow
    S_IN --> S_AGENT
    S_AGENT --> S_OUT1
    S_AGENT --> S_OUT2
    S_OUT1 --> PARSE1
    S_OUT2 --> ART1

    %% Scout to Architect
    PARSE1 --> INJECT1
    INJECT1 -->|"--system-prompt + SCOUT_JSON"| A_IN
    A_IN --> A_AGENT
    A_AGENT --> A_OUT1
    A_AGENT --> A_OUT2
    A_OUT1 --> PARSE2
    A_OUT2 --> ART2

    %% Architect to Builder
    PARSE2 --> INJECT2
    INJECT2 -->|"--system-prompt + ARCHITECTURE_JSON"| B_IN
    B_IN --> B_AGENT
    B_AGENT --> B_OUT1
    B_AGENT --> B_OUT2
    B_OUT2 --> ART3

    %% Architect to Test
    A_OUT2 -.->|test_plan field| T_IN
    T_IN --> T_AGENT
    T_AGENT --> T_OUT

    %% BAML Tracking
    S_AGENT -.-> ART4
    A_AGENT -.-> ART4
    B_AGENT -.-> ART4
    T_AGENT -.-> ART4
    T_AGENT -.-> ART5

    %% Styling
    classDef phase fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef artifact fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef orchestrator fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px

    class SCOUT,ARCHITECT,BUILDER,TEST phase
    class ARTIFACTS artifact
    class ORCHESTRATOR orchestrator
```

---

## Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant S as Scout Agent
    participant A as Architect Agent
    participant B as Builder Agent
    participant T as Test Agent
    participant FS as .context-foundry/

    U->>O: Task Description

    rect rgb(225, 245, 254)
        Note over O,S: Scout Phase
        O->>S: spawn claude --system-prompt phase_scout.txt
        S->>FS: Write scout_report.json
        S->>O: Return scout-report.md
        O->>O: Parse MD -> SCOUT_JSON
    end

    rect rgb(232, 245, 233)
        Note over O,A: Architect Phase
        O->>A: spawn claude --system-prompt phase_architect.txt<br/>+ SCOUT_JSON injected
        A->>FS: Write architecture.json
        A->>O: Return architecture.md
        O->>O: Parse MD -> ARCHITECTURE_JSON
    end

    rect rgb(255, 243, 224)
        Note over O,B: Builder Phase
        O->>B: spawn claude --system-prompt phase_builder.txt<br/>+ ARCHITECTURE_JSON injected
        B->>FS: Write build-tasks.json
        B->>FS: Write source code files
        B->>O: Return completion status
    end

    rect rgb(252, 228, 236)
        Note over O,T: Test Phase
        O->>T: spawn claude --system-prompt phase_test.txt<br/>+ ARCHITECTURE_JSON.test_plan
        T->>FS: Write test-report-N.md
        T->>O: Return PASSED/FAILED
    end

    alt Tests PASSED
        O->>U: Build Complete
    else Tests FAILED
        O->>A: Re-run with failure context
        Note over A,T: Loop: Architect Fix -> Builder Fix -> Test
    end
```

---

## Key Enforcement Points

| Checkpoint | Mechanism | Location |
|------------|-----------|----------|
| Scout output validation | Must be >100 bytes, contain required sections | `PhaseValidator` |
| JSON injection | Orchestrator parses MD, injects as `SCOUT_JSON`/`ARCHITECTURE_JSON` | `autonomous_build.py:1537-2169` |
| Phase isolation | Each agent spawned as fresh subprocess with `--system-prompt` | `phase_execution.py:633-970` |
| Read-only contract | Builder reads `ARCHITECTURE_JSON`, NOT Scout outputs directly | `phase_builder.txt:26` |
| BAML tracking | `current-phase.json` updated at each transition | `baml_integration.py` |

---

## File Locations

### Phase System Prompt Files

| Phase | Full Path |
|-------|-----------|
| Scout | `/Users/name/homelab/context-foundry/tools/prompts/phases/phase_scout.txt` |
| Architect | `/Users/name/homelab/context-foundry/tools/prompts/phases/phase_architect.txt` |
| Builder | `/Users/name/homelab/context-foundry/tools/prompts/phases/phase_builder.txt` |
| Test | `/Users/name/homelab/context-foundry/tools/prompts/phases/phase_test.txt` |
| Deploy | `/Users/name/homelab/context-foundry/tools/prompts/phases/phase_deploy.txt` |
| Documentation | `/Users/name/homelab/context-foundry/tools/prompts/phases/phase_documentation.txt` |
| Task Builder | `/Users/name/homelab/context-foundry/tools/prompts/phases/phase_task_builder.txt` |

### Orchestration & Execution Code

| Component | Full Path |
|-----------|-----------|
| Autonomous Build Orchestrator | `/Users/name/homelab/context-foundry/tools/mcp_utils/autonomous_build.py` |
| Phase Execution (run_phase, PhaseValidator) | `/Users/name/homelab/context-foundry/tools/mcp_utils/phase_execution.py` |
| BAML Integration | `/Users/name/homelab/context-foundry/tools/baml_integration.py` |

### Build Artifact Locations (per project)

| Artifact | Path Pattern |
|----------|--------------|
| Scout Report (JSON) | `{project_dir}/.context-foundry/scout_report.json` |
| Architecture (JSON) | `{project_dir}/.context-foundry/architecture.json` |
| Build Tasks | `{project_dir}/.context-foundry/build-tasks.json` |
| Current Phase (BAML) | `{project_dir}/.context-foundry/current-phase.json` |
| Session Summary | `{project_dir}/.context-foundry/session-summary.json` |
| Test Report | `{project_dir}/.context-foundry/test-report-{N}.md` |

### Global Pattern Storage

| Pattern Type | Full Path |
|--------------|-----------|
| Common Issues | `~/.context-foundry/patterns/common-issues.json` |
| Scout Learnings | `~/.context-foundry/patterns/scout-learnings.json` |
| Architecture Patterns | `~/.context-foundry/patterns/architecture-patterns.json` |
| MCP Server Patterns | `~/.context-foundry/patterns/mcp-server-patterns.json` |

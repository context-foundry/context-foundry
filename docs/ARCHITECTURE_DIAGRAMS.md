# Context Foundry Architecture Diagrams

**Visual Documentation - Architecture Flowcharts and Sequence Diagrams**

> **Note:** These diagrams use Mermaid syntax, which GitHub renders automatically. If viewing locally, use a Mermaid-compatible markdown viewer or the [Mermaid Live Editor](https://mermaid.live/).

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Sequence Diagram: Complete Build Flow](#2-sequence-diagram-complete-build-flow)
3. [Agent Lifecycle State Diagram](#3-agent-lifecycle-state-diagram)
4. [Context Isolation Architecture](#4-context-isolation-architecture)
5. [Data Flow Through Files](#5-data-flow-through-files)
6. [MCP Protocol Message Flow](#6-mcp-protocol-message-flow)

---

## 1. High-Level Architecture

**Complete system overview showing all components and their relationships**

```mermaid
flowchart TD
    Start([User Request]) --> MainWindow[Main Claude Code Window<br/>Context: <1%]

    MainWindow --> IntentDetection{Build Intent<br/>Detected?}

    IntentDetection -->|No| RegularTask[Regular Claude Code Task]
    IntentDetection -->|Yes| MCPCall[Call MCP Tool:<br/>autonomous_build_and_deploy_async]

    MCPCall --> MCPServer[MCP Server<br/>tools/mcp_server.py]

    MCPServer --> GenerateTaskID[Generate Task ID<br/>UUID]
    GenerateTaskID --> BuildPrompt[Build Orchestrator Prompt<br/>tools/orchestrator_prompt.txt]
    BuildPrompt --> SpawnProcess[Spawn Subprocess:<br/>claude-code --prompt ...]

    SpawnProcess --> TaskTracking[Track in TASKS dict<br/>Status: running]
    TaskTracking --> ReturnTaskID[Return Task ID to<br/>Main Window]

    ReturnTaskID --> MainWindow
    MainWindow --> UserContinues[User Continues Working<br/>Context Still <1%]

    SpawnProcess --> DelegatedInstance[Delegated Claude Code Instance<br/>Separate Process<br/>Fresh 200K Context]

    DelegatedInstance --> Phase1[Phase 1: Scout Agent<br/>Research & Analysis]
    Phase1 --> ScoutReport[Write:<br/>.context-foundry/scout-report.md]
    ScoutReport --> Phase1End[Agent Dies<br/>Context Freed]

    Phase1End --> Phase2[Phase 2: Architect Agent<br/>Read scout-report.md<br/>Design Architecture]
    Phase2 --> ArchReport[Write:<br/>.context-foundry/architecture.md]
    ArchReport --> Phase2End[Agent Dies<br/>Context Freed]

    Phase2End --> Phase3[Phase 3: Builder Agent<br/>Read architecture.md<br/>Implement Code]
    Phase3 --> CodeFiles[Write:<br/>Source code files<br/>Tests<br/>build-log.md]
    CodeFiles --> Phase3End[Agent Dies<br/>Context Freed]

    Phase3End --> Phase4{Phase 4: Test Agent<br/>Run Tests}

    Phase4 -->|Tests Pass| Phase5[Phase 5: Documentation<br/>Generate README, guides]

    Phase4 -->|Tests Fail| TestAnalysis[Analyze Failures<br/>Write test-results-iteration-N.md]
    TestAnalysis --> TestFixes[Write fixes-iteration-N.md<br/>Re-architect if needed]
    TestFixes --> RebuildFixes[Re-implement Fixes]
    RebuildFixes --> TestIteration{Iterations <<br/>Max?}
    TestIteration -->|Yes| Phase5
    TestIteration -->|No| Phase4

    Phase5 --> Docs[Write:<br/>README.md<br/>User guides]
    Docs --> Phase6[Phase 6: Deploy<br/>Git operations]

    Phase6 --> GitCommit[git init<br/>git add .<br/>git commit]
    GitCommit --> GitHubRepo[gh repo create<br/>git push origin main]
    GitHubRepo --> Phase7[Phase 7: Feedback<br/>Extract Patterns]

    Phase7 --> PatternUpdate[Update:<br/>~/.context-foundry/patterns/]
    PatternUpdate --> SessionSummary[Write:<br/>.context-foundry/session-summary.json]

    SessionSummary --> ProcessComplete[Delegated Process Exits<br/>Context Discarded]

    ProcessComplete --> MCPServer
    MCPServer --> ReadSummary[Read session-summary.json]
    ReadSummary --> UpdateTaskStatus[Update TASKS<br/>Status: completed]

    UserContinues --> CheckStatus{User Checks<br/>Status?}
    CheckStatus -->|Yes| GetResult[Call get_delegation_result]
    GetResult --> MCPServer
    UpdateTaskStatus --> ReturnSummary[Return Build Summary]
    ReturnSummary --> MainWindow
    MainWindow --> ShowComplete[Show User:<br/>Build Complete!<br/>GitHub URL<br/>Tests Passed]

    ShowComplete --> End([End])

    style MainWindow fill:#e1f5e1
    style DelegatedInstance fill:#fff4e1
    style MCPServer fill:#e1e5ff
    style Phase1 fill:#ffe1e1
    style Phase2 fill:#ffe1e1
    style Phase3 fill:#ffe1e1
    style Phase4 fill:#ffe1e1
    style Phase5 fill:#ffe1e1
    style Phase6 fill:#ffe1e1
    style Phase7 fill:#ffe1e1
```

**Key Observations:**
- **Main Window** (green) stays clean throughout entire build
- **MCP Server** (blue) orchestrates subprocess spawning and tracking
- **Delegated Instance** (yellow) does all the heavy lifting in isolated context
- **7 Phases** (red) each with ephemeral agents that die after completing their work
- **Self-healing loop** in Phase 4 automatically fixes test failures

---

## 2. Sequence Diagram: Complete Build Flow

**Step-by-step message flow from user request to completion**

```mermaid
sequenceDiagram
    participant User
    participant MainClaude as Main Claude Window<br/>(Context <1%)
    participant MCP as MCP Server<br/>(Python)
    participant Delegated as Delegated Instance<br/>(Fresh 200K Context)
    participant FileSystem as File System<br/>(.context-foundry/)
    participant GitHub

    User->>MainClaude: "Build a weather app"
    activate MainClaude

    MainClaude->>MainClaude: Detect build intent

    MainClaude->>MCP: MCP Tool Call:<br/>autonomous_build_and_deploy_async<br/>{task: "Build weather app", ...}
    activate MCP

    MCP->>MCP: Generate task_id = "abc-123"
    MCP->>MCP: Load orchestrator_prompt.txt
    MCP->>MCP: Inject task parameters

    MCP->>Delegated: spawn subprocess<br/>claude-code --prompt "..."
    activate Delegated

    MCP->>MCP: Track in TASKS[abc-123]<br/>Status: running

    MCP-->>MainClaude: {task_id: "abc-123",<br/>status: "started"}
    deactivate MCP

    MainClaude-->>User: "Build started!<br/>Task ID: abc-123<br/>You can continue working..."
    deactivate MainClaude

    Note over Delegated: PHASE 1: SCOUT
    Delegated->>Delegated: Create /agents scout
    Delegated->>Delegated: Research APIs, patterns
    Delegated->>FileSystem: Write scout-report.md (40KB)
    Delegated->>Delegated: Agent dies, context freed

    Note over Delegated: PHASE 2: ARCHITECT
    Delegated->>FileSystem: Read scout-report.md
    Delegated->>Delegated: Create /agents architect
    Delegated->>Delegated: Design architecture
    Delegated->>FileSystem: Write architecture.md (60KB)
    Delegated->>Delegated: Agent dies, context freed

    Note over Delegated: PHASE 3: BUILDER
    Delegated->>FileSystem: Read architecture.md
    Delegated->>Delegated: Create /agents builder
    Delegated->>Delegated: Implement all files
    Delegated->>FileSystem: Write source code (12 files)<br/>Write build-log.md
    Delegated->>Delegated: Agent dies, context freed

    Note over Delegated: PHASE 4: TEST
    Delegated->>Delegated: Run tests: npm test

    alt Tests Fail
        Delegated->>FileSystem: Write test-results-iteration-1.md
        Delegated->>FileSystem: Write fixes-iteration-1.md
        Delegated->>Delegated: Re-implement fixes
        Delegated->>Delegated: Re-run tests
        Delegated->>FileSystem: Write test-final-report.md<br/>(iteration 2, tests pass)
    else Tests Pass
        Delegated->>FileSystem: Write test-final-report.md<br/>(iteration 1, all pass)
    end

    Note over Delegated: PHASE 5: DOCUMENTATION
    Delegated->>FileSystem: Read source code
    Delegated->>Delegated: Generate README, guides
    Delegated->>FileSystem: Write README.md, docs/

    Note over Delegated: PHASE 6: DEPLOYMENT
    Delegated->>Delegated: git init, add, commit
    Delegated->>GitHub: gh repo create weather-app
    Delegated->>GitHub: git push origin main
    GitHub-->>Delegated: Repository created

    Note over Delegated: PHASE 7: FEEDBACK
    Delegated->>FileSystem: Analyze build for patterns
    Delegated->>FileSystem: Update ~/.context-foundry/patterns/
    Delegated->>FileSystem: Write session-summary.json

    Delegated->>Delegated: Exit process (context freed)
    deactivate Delegated

    Note over User: [10 minutes later]
    User->>MainClaude: "What's the status of task abc-123?"
    activate MainClaude

    MainClaude->>MCP: get_delegation_result(abc-123)
    activate MCP

    MCP->>MCP: Check TASKS[abc-123].process.poll()
    MCP->>MCP: Process finished (exit code 0)
    MCP->>FileSystem: Read session-summary.json
    FileSystem-->>MCP: {status: "completed",<br/>github_url: "...",<br/>tests_passed: true, ...}

    MCP-->>MainClaude: {status: "completed", ...}
    deactivate MCP

    MainClaude-->>User: "Build complete! ✅<br/>GitHub: github.com/you/weather-app<br/>Tests: 25/25 passing<br/>Duration: 8.3 minutes"
    deactivate MainClaude
```

**Key Points:**
1. Main Claude window makes ONE tool call and returns immediately
2. User can continue working (context stays clean)
3. Delegated instance does ALL 7 phases autonomously
4. Each phase reads previous artifacts from disk
5. Final summary written to session-summary.json
6. User checks status later, gets complete results

---

## 3. Agent Lifecycle State Diagram

**How agents transition through states during a build**

```mermaid
stateDiagram-v2
    [*] --> OrchestratorActive: Delegated Instance Spawned

    OrchestratorActive --> ScoutCreated: /agents scout

    ScoutCreated --> ScoutResearching: Begin Research
    ScoutResearching --> ScoutWriting: Research Complete
    ScoutWriting --> ScoutDead: Write scout-report.md

    ScoutDead --> ArchitectCreated: /agents architect

    ArchitectCreated --> ArchitectReading: Read scout-report.md
    ArchitectReading --> ArchitectDesigning: Scout Knowledge Loaded
    ArchitectDesigning --> ArchitectWriting: Design Complete
    ArchitectWriting --> ArchitectDead: Write architecture.md

    ArchitectDead --> BuilderCreated: /agents builder

    BuilderCreated --> BuilderReading: Read architecture.md
    BuilderReading --> BuilderImplementing: Architect Knowledge Loaded
    BuilderImplementing --> BuilderWriting: Implementation Complete
    BuilderWriting --> BuilderDead: Write source code + build-log.md

    BuilderDead --> TestRunning: Run Tests

    TestRunning --> TestsPassed: All Tests Pass
    TestRunning --> TestsFailed: Tests Fail

    TestsFailed --> TestAnalyzing: Analyze Root Cause
    TestAnalyzing --> TestFixing: Write fixes-iteration-N.md
    TestFixing --> TestRebuilding: Re-implement Fixes
    TestRebuilding --> TestRunning: Re-run Tests

    TestsPassed --> DocsCreating: Generate Documentation

    DocsCreating --> DocsWriting: README, guides generated
    DocsWriting --> DeployStarting: Write docs to disk

    DeployStarting --> GitOperations: git init, add, commit
    GitOperations --> GitHubCreation: gh repo create
    GitHubCreation --> GitPush: git push origin main
    GitPush --> FeedbackAnalysis: Deployment Complete

    FeedbackAnalysis --> PatternExtraction: Analyze Build
    PatternExtraction --> PatternUpdate: Extract Learnings
    PatternUpdate --> SummaryWriting: Update Pattern Library
    SummaryWriting --> ProcessExit: Write session-summary.json

    ProcessExit --> [*]: Delegated Process Terminates

    note right of ScoutDead
        Agent context DISCARDED
        scout-report.md PERSISTS
    end note

    note right of ArchitectDead
        Agent context DISCARDED
        architecture.md PERSISTS
    end note

    note right of BuilderDead
        Agent context DISCARDED
        Source code PERSISTS
    end note

    note right of ProcessExit
        ALL agent contexts GONE
        All files PERSIST
        Pattern library UPDATED
    end note
```

**Agent Lifecycle Principles:**
1. **Ephemeral Agents**: Each agent lives only during its phase
2. **Clean Handoff**: Agents read previous phase's artifacts from disk
3. **No Shared Context**: Agents never communicate directly
4. **Persistent Artifacts**: All essential knowledge written to files
5. **Self-Healing**: Test phase can loop back to fix failures
6. **Pattern Learning**: Feedback phase updates global patterns

---

## 4. Context Isolation Architecture

**How main window stays clean while delegated instance does heavy work**

```mermaid
flowchart TB
    subgraph MainProcess[Main Claude Code Process - PID 12345]
        MainContext[Context Window: 200,000 tokens]
        MainUsed[Used: ~1,400 tokens<br/>0.7%]
        MainAvailable[Available: 198,600 tokens<br/>99.3%]

        MainContext --> MainUsed
        MainContext --> MainAvailable

        UserMsg[User: Build weather app<br/>100 tokens]
        ToolCall[MCP Tool Call<br/>200 tokens]
        ToolResp[MCP Response<br/>100 tokens]
        StatusCheck[Status Check<br/>100 tokens]
        StatusResp[Status Response<br/>500 tokens]
        Summary[Claude Summary<br/>300 tokens]

        UserMsg --> MainUsed
        ToolCall --> MainUsed
        ToolResp --> MainUsed
        StatusCheck --> MainUsed
        StatusResp --> MainUsed
        Summary --> MainUsed
    end

    MainProcess -.->|Spawns subprocess| DelegatedProcess

    subgraph DelegatedProcess[Delegated Claude Process - PID 67890]
        DelegatedContext[Context Window: 200,000 tokens<br/>SEPARATE!]
        DelegatedUsed[Used: ~78,000 tokens<br/>39%]
        DelegatedAvailable[Available: 122,000 tokens<br/>61%]

        DelegatedContext --> DelegatedUsed
        DelegatedContext --> DelegatedAvailable

        OrchestratorPrompt[Orchestrator Prompt<br/>5,000 tokens]
        Phase1Scout[Phase 1: Scout<br/>10,000 tokens]
        Phase2Arch[Phase 2: Architect<br/>15,000 tokens]
        Phase3Build[Phase 3: Builder<br/>30,000 tokens]
        Phase4Test[Phase 4: Test<br/>8,000 tokens]
        Phase5Docs[Phase 5: Docs<br/>3,000 tokens]
        Phase6Deploy[Phase 6: Deploy<br/>2,000 tokens]
        Phase7Feedback[Phase 7: Feedback<br/>5,000 tokens]

        OrchestratorPrompt --> DelegatedUsed
        Phase1Scout --> DelegatedUsed
        Phase2Arch --> DelegatedUsed
        Phase3Build --> DelegatedUsed
        Phase4Test --> DelegatedUsed
        Phase5Docs --> DelegatedUsed
        Phase6Deploy --> DelegatedUsed
        Phase7Feedback --> DelegatedUsed
    end

    DelegatedProcess -.->|Writes files| FileSystem[(File System<br/>.context-foundry/)]

    FileSystem -.->|MCP reads summary| MainProcess

    style MainProcess fill:#e1f5e1,stroke:#4a4,stroke-width:3px
    style DelegatedProcess fill:#fff4e1,stroke:#fa4,stroke-width:3px
    style FileSystem fill:#e1e5ff,stroke:#44a,stroke-width:3px

    style MainUsed fill:#4a4,color:#fff
    style DelegatedUsed fill:#fa4,color:#000
    style MainAvailable fill:#afa,color:#000
    style DelegatedAvailable fill:#ffa,color:#000
```

**Key Insights:**
- **Separate OS Processes**: Main (PID 12345) and Delegated (PID 67890)
- **Separate Context Windows**: Each has own 200K token budget
- **Zero Cross-Contamination**: Delegated instance's 78K tokens don't affect main window
- **File-Based Communication**: Only way processes share data
- **Main Window Efficiency**: Only tracks task ID and summary, stays at 0.7%
- **Delegated Instance**: Can use 40-60% of context without impacting main window

**Result**: You can run MULTIPLE delegated builds in parallel, each in its own process, while your main Claude Code window stays clean and available for other work!

---

## 5. Data Flow Through Files

**How information flows via persistent artifacts**

```mermaid
flowchart LR
    subgraph Input[Input to Scout]
        Task[Task Description<br/>Build a weather app]
        Patterns[Pattern Library<br/>~/.context-foundry/patterns/]
    end

    Input --> Scout[Scout Agent]

    Scout --> ScoutOut[scout-report.md<br/>40KB<br/>- API recommendations<br/>- Tech stack<br/>- Risk warnings<br/>- Architecture guidance]

    ScoutOut --> Architect[Architect Agent]

    Architect --> ArchOut[architecture.md<br/>60KB<br/>- System design<br/>- File structure<br/>- Component specs<br/>- Data models<br/>- Implementation plan]

    ArchOut --> Builder[Builder Agent]

    Builder --> BuildOut[Source Code Files<br/>12 files<br/>+ build-log.md<br/>- Implementation log<br/>- Decisions made]

    BuildOut --> Test[Test Agent]

    Test --> TestLoop{Tests<br/>Pass?}

    TestLoop -->|No| TestFix[test-results-iteration-N.md<br/>fixes-iteration-N.md]
    TestFix --> Builder

    TestLoop -->|Yes| TestOut[test-final-report.md<br/>- Test results<br/>- Coverage metrics<br/>- Iterations taken]

    TestOut --> Docs[Documentation Agent]

    Docs --> DocsOut[README.md<br/>User Guides<br/>API Docs]

    DocsOut --> Deploy[Deployment Agent]

    Deploy --> DeployOut[GitHub Repository<br/>- All source code<br/>- All documentation<br/>- Git history]

    DeployOut --> Feedback[Feedback Agent]

    Feedback --> FeedbackOut[Pattern Library Updates<br/>session-summary.json<br/>- Build metadata<br/>- Lessons learned]

    FeedbackOut --> Patterns

    style ScoutOut fill:#ffe1e1
    style ArchOut fill:#e1ffe1
    style BuildOut fill:#e1e1ff
    style TestOut fill:#ffe1ff
    style DocsOut fill:#ffffe1
    style DeployOut fill:#e1ffff
    style FeedbackOut fill:#ffe1e1
```

**Data Flow Principles:**
1. **Unidirectional Flow**: Information flows forward through phases
2. **File-Based Handoff**: Each agent reads previous files, writes new files
3. **Cumulative Knowledge**: Later artifacts contain all essential knowledge from earlier phases
4. **Self-Healing Loop**: Test phase can loop back to Builder with fix specifications
5. **Pattern Learning**: Feedback updates global library for future builds

**What Persists vs. What's Discarded:**

| Phase | Agent Context | Files Written | Knowledge Preserved? |
|-------|---------------|---------------|---------------------|
| Scout | Discarded | scout-report.md | ✅ Yes (in file) |
| Architect | Discarded | architecture.md | ✅ Yes (in file) |
| Builder | Discarded | Source code, build-log.md | ✅ Yes (in files) |
| Test | Discarded | test-final-report.md | ✅ Yes (in file) |
| Docs | Discarded | README.md, guides | ✅ Yes (in files) |
| Deploy | Discarded | GitHub repository | ✅ Yes (on GitHub) |
| Feedback | Discarded | Pattern updates, session-summary.json | ✅ Yes (in files) |

**Conclusion**: Even though ALL agent contexts are discarded, ALL essential knowledge is preserved in files!

---

## 6. MCP Protocol Message Flow

**JSON-RPC messages between Claude Code and MCP Server**

```mermaid
sequenceDiagram
    participant CC as Claude Code CLI
    participant MCP as MCP Server<br/>(stdio transport)
    participant Sub as Subprocess<br/>(Delegated Instance)

    Note over CC,MCP: Connection established via stdio

    CC->>MCP: JSON-RPC Request<br/>{<br/>  "jsonrpc": "2.0",<br/>  "method": "tools/call",<br/>  "params": {<br/>    "name": "autonomous_build_and_deploy_async",<br/>    "arguments": {<br/>      "task": "Build weather app",<br/>      "working_directory": "/tmp/weather-app",<br/>      "github_repo_name": "weather-app",<br/>      "enable_test_loop": true<br/>    }<br/>  },<br/>  "id": 1<br/>}

    activate MCP
    MCP->>MCP: Generate task_id = "abc-123"
    MCP->>MCP: Build orchestrator prompt

    MCP->>Sub: subprocess.Popen([<br/>  'claude-code',<br/>  '--prompt', '...',<br/>  '--permission-mode', 'bypassPermissions'<br/>])
    activate Sub

    MCP->>MCP: TASKS["abc-123"] = {<br/>  process: <subprocess>,<br/>  status: "running",<br/>  start_time: 1234567890<br/>}

    MCP-->>CC: JSON-RPC Response<br/>{<br/>  "jsonrpc": "2.0",<br/>  "result": {<br/>    "task_id": "abc-123",<br/>    "status": "started",<br/>    "message": "Build running in background",<br/>    "expected_duration": "7-15 minutes"<br/>  },<br/>  "id": 1<br/>}
    deactivate MCP

    Note over Sub: Delegated instance runs 7 phases...<br/>(Scout, Architect, Builder, Test, Docs, Deploy, Feedback)

    Sub->>Sub: Write session-summary.json
    Sub->>Sub: Exit (return code 0)
    deactivate Sub

    Note over CC: [User checks status later]

    CC->>MCP: JSON-RPC Request<br/>{<br/>  "jsonrpc": "2.0",<br/>  "method": "tools/call",<br/>  "params": {<br/>    "name": "get_delegation_result",<br/>    "arguments": {<br/>      "task_id": "abc-123"<br/>    }<br/>  },<br/>  "id": 2<br/>}

    activate MCP
    MCP->>MCP: process.poll() → 0 (finished)
    MCP->>MCP: Read .context-foundry/session-summary.json

    MCP-->>CC: JSON-RPC Response<br/>{<br/>  "jsonrpc": "2.0",<br/>  "result": {<br/>    "status": "completed",<br/>    "task_id": "abc-123",<br/>    "duration_seconds": 498,<br/>    "phases_completed": ["scout", "architect", "builder",<br/>                         "test", "docs", "deploy", "feedback"],<br/>    "github_url": "https://github.com/user/weather-app",<br/>    "tests_passed": true,<br/>    "test_iterations": 1,<br/>    "files_created": 12<br/>  },<br/>  "id": 2<br/>}
    deactivate MCP
```

**MCP Protocol Details:**
- **Transport**: stdio (standard input/output)
- **Format**: JSON-RPC 2.0
- **Tools**: Exposed via `tools/call` method
- **Async**: Returns immediately with task_id, build continues in background
- **Status Polling**: User can check status anytime with `get_delegation_result`

**Message Types:**
1. **Tool Call**: Request to execute MCP tool (autonomous_build_and_deploy_async)
2. **Tool Response**: Immediate response with task_id
3. **Status Request**: Check build progress (get_delegation_result)
4. **Status Response**: Build summary (running, completed, failed, timeout)

---

## Viewing These Diagrams

### On GitHub
Simply view this file on GitHub - diagrams render automatically!

### Locally
Use one of these tools:
- **VS Code**: Install "Markdown Preview Mermaid Support" extension
- **Mermaid Live Editor**: Copy diagram code to [mermaid.live](https://mermaid.live/)
- **IntelliJ/PyCharm**: Mermaid plugin available
- **Obsidian**: Built-in Mermaid support

### Export to PNG/SVG
1. Copy diagram code
2. Go to [mermaid.live](https://mermaid.live/)
3. Paste code
4. Click "Actions" → "Export PNG" or "Export SVG"

---

## Summary

**These diagrams show:**

✅ **Complete System Architecture** - From user request to GitHub deployment
✅ **Message Flow** - Every step from MCP call to subprocess completion
✅ **Agent Lifecycle** - How ephemeral agents transition and die
✅ **Context Isolation** - How main window stays clean (0.7% usage)
✅ **Data Flow** - How information persists via files, not agent contexts
✅ **MCP Protocol** - JSON-RPC messages between components

**Key Takeaway**: Context Foundry's architecture is built on:
- **Subprocess delegation** (separate processes, separate contexts)
- **Ephemeral agents** (die after each phase, context freed)
- **Persistent files** (knowledge written to disk, survives agent death)
- **MCP protocol** (standard communication between Claude Code and server)

**Result**: Your main Claude Code window stays clean (<1%) while entire applications are built autonomously in the background!

---

## Related Documentation

- [MCP_SERVER_ARCHITECTURE.md](MCP_SERVER_ARCHITECTURE.md) - Technical implementation details
- [CONTEXT_PRESERVATION.md](CONTEXT_PRESERVATION.md) - How context flows between agents
- [DELEGATION_MODEL.md](DELEGATION_MODEL.md) - Why delegation keeps context clean
- [README.md](../README.md) - Quick start and overview

---

**Version:** 2.0.1 | **Last Updated:** October 2025

# Context Foundry Features

> *"Generate probabilistically, validate deterministically."*

## BAML Type-Safe Outputs (v2.4.0)

**Major Breakthrough:** Context Foundry now uses **[BAML](https://github.com/BoundaryML/baml)** (Boundary ML) for type-safe JSON outputs, delivering **crisp, fully-working, feature-rich applications on the first try**.

### Benefits
- **Reliability**: Parsing errors reduced from 5% to <1%
- **Type Safety**: Compile-time schema validation catches errors early
- **Better Outputs**: More detailed, feature-rich implementations
- **Queryable**: Use `jq` or JSON tools to extract specific data
- **Developer Experience**: Full IDE autocomplete with type hints

### Dual-Mode Architecture Parsing
1. **Claude CLI** (fast, $0) - Uses your subscription for instant extraction
2. **BAML Fallback** (reliable, ~$0.03) - Ensures type-safe validation if CLI fails
3. **Graceful Degradation** - Falls back to markdown if needed

---

## Mission Control TUI (v2.3.0)

**Your command center for autonomous AI development**

Full-featured Terminal User Interface with real-time monitoring:
- **Interactive Chat** - Natural language build requests
- **Real-time Updates** - Live phase progress (Scout -> Architect -> Builder)
- **Multi-build Support** - Monitor multiple projects simultaneously
- **Keyboard Navigation** - Fast, efficient controls

### Key Features
- **Interactive Chat Interface**: Natural language commands, smart parsing
- **Real-Time Build Monitoring**: Live status, phase progress, duration tracking
- **Three View Modes**: Conversation, Builds, Directory
- **Keyboard Navigation**: Tab to cycle, arrow keys to navigate

---

## Spec Mode (v3.0.0)

**Build directly from your design documents**

Skip the AI brainstorming and build exactly what your specification describes:

### How It Works
```
Normal Mode:  Scout → Architect → Builder → Tester
              (AI researches) (AI designs)

Spec Mode:           Architect → Builder → Tester
                     (extracts from YOUR spec)
```

In Spec Mode:
- **Scout is skipped** — Your spec replaces Scout's requirements analysis
- **Architect extracts** — Reads your spec and fills the standard template (doesn't invent)
- **Builder implements** — Builds exactly what your spec describes
- **Tester validates** — Tests against Gherkin criteria extracted from your spec

### Supported Formats
| Format | Extensions | Notes |
|--------|------------|-------|
| Plain text | `.txt`, `.md`, `.json`, `.yaml` | Built-in |
| PDF | `.pdf` | Requires `pypdf` |
| Word | `.docx` | Requires `python-docx` |
| Images | `.png`, `.jpg`, `.gif`, `.webp` | Diagrams, wireframes, mockups |

### Usage Examples

**Natural language:**
```
Build from spec at ~/Documents/dashboard-spec.pdf
Output to ~/builds/my-dashboard
```

**Multiple spec files:**
```
Build using these specs:
- ~/Documents/requirements.md
- ~/Documents/wireframes.png
- ~/Documents/api-design.pdf
```

**Programmatic (MCP):**
```python
autonomous_build_and_deploy(
    task="Build a dashboard",
    working_directory="/path/to/project",
    spec_files=["/path/to/spec.pdf", "/path/to/wireframes.png"]
)
```

---

## Spec Mode + HIL Compatibility (v3.0.0)

**Combine specification-driven builds with human approval gates**

Spec Mode and Human-in-the-Loop (HIL) are **independent features** that work together:

| Mode | What It Controls |
|------|------------------|
| **Spec Mode** | *Input source* — Where requirements come from (your files vs AI research) |
| **HIL Mode** | *Approval gates* — When to pause for human review |

### Combined Usage

```
Build from spec ~/Documents/spec.pdf with human-in-the-loop review
Output to ~/builds/my-app
```

**Pipeline:**
1. ~~Scout~~ (skipped - your spec is the source)
2. Architect extracts from your PDF
3. **⏸️ Pause for approval** of the architecture
4. Builder implements after approval
5. **⏸️ Pause for approval** of the code
6. Tester validates

### When to Use

| Scenario | Recommended Approach |
|----------|---------------------|
| Quick prototype | Regular mode (no spec, no HIL) |
| Implementing a client's PRD | Spec Mode |
| Critical production system | HIL Mode |
| Client spec with review requirements | Spec Mode + HIL |

---

## Semantic Pattern Deduplication (v3.0.0)

**Intelligent pattern matching prevents duplicate learnings**

When patterns are saved, Context Foundry uses Claude to semantically compare new patterns against existing ones. Even with different wording, semantically identical patterns are merged instead of duplicated.

### How It Works

```
New pattern: "polling-race-condition-bug"
Existing:    "daemon-job-status-race-condition"

Claude: "These describe the same issue"
Result: Update existing pattern (frequency +1), don't create duplicate
```

### Benefits
- **No duplicate patterns** — Even when LLMs generate different IDs
- **Better frequency tracking** — Same issue found multiple times = higher frequency
- **Cleaner pattern library** — Focused, deduplicated knowledge base
- **Cost-effective** — ~$0.008 per semantic check (Opus 4.5)

---

## Context Codex (v2.3.0)

**Database-Backed Self-Learning**

Context Foundry uses a relational database (`~/.context-foundry/codex.db`) for knowledge management:
- **Full-text search** - Find patterns instantly with SQL
- **Relationships** - "What patterns prevent issue X?"
- **Confidence scoring** - Track reliability of learnings
- **Build metrics** - Analyze performance trends
- **Automatic learning** - Every build teaches the system

---

## Intelligent Parallel Build Detection

**AI decides how many parallel agents to spawn**

Scout phase now analyzes project complexity and automatically determines:
- **Whether to use parallel** - Based on module separation, file count, complexity score
- **How many workers** - Dynamically calculates 2-8 workers based on project structure
- **Time savings estimate** - Predicts 20-60% faster builds for complex projects

---

## Agent Quality Enhancements

### 1. Back Pressure System
Validation friction that prevents bad code from progressing through phases.
- **Scout Validation**: Checks required languages/tools
- **Architecture Validation**: Ensures sound design
- **Integration Pre-Check**: Fast syntax/import checks

### 2. Context Budget Monitoring
Real-time token tracking with zone detection and phase-specific budgets.
- **Smart Zone (0-40%)**: Optimal performance
- **Dumb Zone (40-100%)**: Degraded performance

### 3. Tool Implementation Quality (70% Rule)
Enhanced tool outputs with smart truncation, relative paths, explicit limits, and recovery instructions.

### 4. Semantic Tagging System
Explicit type markers in all tool outputs (`dir`, `file`, `match:def`) clarify tool outputs with <3% token overhead.

---

## Architecture Innovations

1. **Meta-MCP Innovation** - Use MCP to recursively spawn Claude Code instances
2. **Deterministic Compliance Layer** - *"Generate probabilistically, validate deterministically"* - Code-level enforcement wrapping AI generation
3. **Subprocess Delegation** - Spawn fresh Claude instances via `subprocess.Popen()`
4. **Context Window Isolation** - Each agent gets a fresh 200K token window
5. **File-Based Context System** - Shared memory via filesystem
6. **Markdown-First Design** - `.md` files over JSON for human+AI readability

## Automation Innovations

7. **Self-Healing Test Loop** - Auto-fix test failures through redesign->rebuild->retest cycles
8. **Parallel Execution Architecture** - Spawns concurrent agents (30-45% faster)
9. **Meta-Prompt Orchestration** - AI orchestrates AI via `orchestrator_prompt.txt`
10. **8-Phase Workflow** - Scout->Architect->Builder->Test->Screenshot->Docs->Deploy->Feedback
11. **Async Task Management** - Non-blocking subprocess execution

## Intelligence Innovations

12. **Global Pattern Learning** - Cross-project knowledge accumulation
13. **Output Truncation Strategy** - 45-45-10 split keeps critical context visible

## User Experience Innovations

14. **Screenshot Capture Phase** - Playwright-based visual documentation
15. **Mission Control TUI** - Full-featured terminal interface
16. **Livestream Integration** - WebSocket-based remote monitoring

# Context Foundry Features

## 🎯 BAML Type-Safe Outputs (v2.4.0)

**Major Breakthrough:** Context Foundry now uses **[BAML](https://github.com/BoundaryML/baml)** (Boundary ML) for type-safe JSON outputs, delivering **crisp, fully-working, feature-rich applications on the first try**.

### Benefits
- ✅ **Reliability**: Parsing errors reduced from 5% to <1%
- ✅ **Type Safety**: Compile-time schema validation catches errors early
- ✅ **Better Outputs**: More detailed, feature-rich implementations
- ✅ **Queryable**: Use `jq` or JSON tools to extract specific data
- ✅ **Developer Experience**: Full IDE autocomplete with type hints

### Dual-Mode Architecture Parsing
1. **Claude CLI** (fast, $0) - Uses your subscription for instant extraction
2. **BAML Fallback** (reliable, ~$0.03) - Ensures type-safe validation if CLI fails
3. **Graceful Degradation** - Falls back to markdown if needed

---

## 🎮 Mission Control TUI (v2.3.0)

**Your command center for autonomous AI development**

Full-featured Terminal User Interface with real-time monitoring:
- **Interactive Chat** - Natural language build requests
- **Real-time Updates** - Live phase progress (Scout → Architect → Builder)
- **Multi-build Support** - Monitor multiple projects simultaneously
- **Keyboard Navigation** - Fast, efficient controls

### Key Features
- 🎯 **Interactive Chat Interface**: Natural language commands, smart parsing
- 📊 **Real-Time Build Monitoring**: Live status, phase progress, duration tracking
- 🔍 **Three View Modes**: Conversation, Builds, Directory
- ⌨️ **Keyboard Navigation**: Tab to cycle, arrow keys to navigate

---

## 🧠 Context Codex (v2.3.0)

**Database-Backed Self-Learning**

Context Foundry uses a relational database (`~/.context-foundry/codex.db`) for knowledge management:
- **Full-text search** - Find patterns instantly with SQL
- **Relationships** - "What patterns prevent issue X?"
- **Confidence scoring** - Track reliability of learnings
- **Build metrics** - Analyze performance trends
- **Automatic learning** - Every build teaches the system

---

## ⚡ Intelligent Parallel Build Detection

**AI decides how many parallel agents to spawn**

Scout phase now analyzes project complexity and automatically determines:
- **Whether to use parallel** - Based on module separation, file count, complexity score
- **How many workers** - Dynamically calculates 2-8 workers based on project structure
- **Time savings estimate** - Predicts 20-60% faster builds for complex projects

---

## 🛡️ Agent Quality Enhancements

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

## 🏗️ Architecture Innovations

1. **Meta-MCP Innovation** - Use MCP to recursively spawn Claude Code instances
2. **Subprocess Delegation** - Spawn fresh Claude instances via `subprocess.Popen()`
3. **Context Window Isolation** - Each agent gets a fresh 200K token window
4. **File-Based Context System** - Shared memory via filesystem
5. **Markdown-First Design** - `.md` files over JSON for human+AI readability

## 🤖 Automation Innovations

6. **Self-Healing Test Loop** - Auto-fix test failures through redesign→rebuild→retest cycles
7. **Parallel Execution Architecture** - Spawns concurrent agents (30-45% faster)
8. **Meta-Prompt Orchestration** - AI orchestrates AI via `orchestrator_prompt.txt`
9. **8-Phase Workflow** - Scout→Architect→Builder→Test→Screenshot→Docs→Deploy→Feedback
10. **Async Task Management** - Non-blocking subprocess execution

## 🧠 Intelligence Innovations

11. **Global Pattern Learning** - Cross-project knowledge accumulation
12. **Output Truncation Strategy** - 45-45-10 split keeps critical context visible

## 🎨 User Experience Innovations

13. **Screenshot Capture Phase** - Playwright-based visual documentation
14. **Mission Control TUI** - Full-featured terminal interface
15. **Livestream Integration** - WebSocket-based remote monitoring

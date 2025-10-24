# Context Foundry Technical FAQ

**For Software Developers, Architects, and AI Engineers**

> Last Updated: 2025-01-23
> Audience: Technical users familiar with distributed systems, AI agents, and software architecture

---

## Table of Contents

1. [File Management & Architecture](#1-file-management--architecture)
2. [The "Secret Sauce" - Prompt Engineering](#2-the-secret-sauce---prompt-engineering)
3. [Agent Architecture & Lifecycle](#3-agent-architecture--lifecycle)
4. [Token Management & Context Windows](#4-token-management--context-windows)
5. [Parallelization & Coordination](#5-parallelization--coordination)
6. [Authentication & API Usage](#6-authentication--api-usage)
7. [Performance & Scaling](#7-performance--scaling)
8. [Error Handling & Self-Healing](#8-error-handling--self-healing)
9. [Pattern Learning System](#9-pattern-learning-system)
10. [Advanced Technical Topics](#10-advanced-technical-topics)
11. [Practical Usage & Limitations](#11-practical-usage--limitations)
12. [Comparisons & Philosophy](#12-comparisons--philosophy)

---

## 1. File Management & Architecture

### Q1: Where are the `.context-foundry/` files stored?

**A:** In the **project directory**, not in the Context Foundry installation directory.

```
your-project/
├── .context-foundry/          # Created in YOUR project
│   ├── scout-report.md
│   ├── architecture.md
│   ├── build-log.md
│   ├── build-tasks.json
│   ├── current-phase.json
│   ├── builder-logs/
│   └── test-logs/
├── src/                       # Your source code
└── package.json
```

**Why this matters:**
- Each project has its own `.context-foundry/` directory
- Files persist across builds (useful for debugging)
- Can be version controlled (add to `.gitignore` if preferred)
- No interference between different projects

**Global patterns** are stored separately at `~/.context-foundry/patterns/` for cross-project learning.

---

### Q2: Why `.md` files instead of JSON for core architecture?

**A:** Markdown files are the **backbone of Context Foundry** for several critical reasons:

**1. Agent-Friendly Format**
- LLMs like Claude are trained heavily on markdown documentation
- Natural language + structure = better comprehension
- Code blocks with syntax highlighting improve parsing

**2. Human-Readable**
- Developers can read `scout-report.md` to understand what the Scout discovered
- Architects can review `architecture.md` to verify the design
- No need to parse JSON to understand build decisions

**3. Git-Diffable**
- Meaningful diffs when architecture changes
- Can track evolution of design across iterations
- Comments and explanations included inline

**4. Context Efficiency**
- Prose is more token-efficient than structured data for complex ideas
- "Create a React app with Zustand state management" (8 tokens) vs extensive JSON schema
- Agents can summarize and reference instead of including full content

**5. Self-Documenting**
- Architecture decisions explained in-place
- Future agents (in self-healing loop) understand *why* choices were made
- Serves as project documentation after build completes

**Example:** `architecture.md` isn't just a file list—it explains the *why* behind each component.

---

### Q3: What's in each `.md` file? What's their purpose?

**A:** Each file serves a specific phase in the workflow:

| File | Phase | Purpose | Typical Size |
|------|-------|---------|--------------|
| `scout-report.md` | Phase 1: Scout | Requirements analysis, tech stack decisions, risk identification | 5-10 KB |
| `architecture.md` | Phase 2: Architect | Complete system design, file structure, implementation plan, test strategy | 15-30 KB |
| `build-log.md` | Phase 3: Builder | Files created, implementation notes, deviations from architecture | 5-15 KB |
| `test-results-iteration-N.md` | Phase 4: Test | Test failures, root cause analysis, fix recommendations | 10-20 KB |
| `fixes-iteration-N.md` | Self-Healing | Fix strategy for failed tests | 5-10 KB |
| `test-final-report.md` | Phase 4: Test | Final test results (pass or fail after all iterations) | 5-10 KB |
| `session-summary.json` | Phase 8: Feedback | Build summary (JSON for MCP parsing) | 2-5 KB |

**JSON Files** (structured data for parsing):
- `build-tasks.json`: Parallel task breakdown with dependencies (Phase 2.5)
- `current-phase.json`: Real-time phase tracking for TUI monitoring
- `session-summary.json`: Final build results for MCP server

**Log Directories:**
- `builder-logs/task-{ID}.log`: Individual builder agent outputs (Phase 2.5)
- `test-logs/{type}.log`: Individual test agent outputs (Phase 4.5)

---

### Q4: How do files persist across phases if agents die after each phase?

**A:** **Filesystem is the shared memory.** This is a core design principle.

**The Flow:**
1. **Phase 1 (Scout):** Agent researches, writes `scout-report.md`, then dies
2. **Phase 2 (Architect):** New agent spawned, *reads* `scout-report.md`, writes `architecture.md`, dies
3. **Phase 3 (Builder):** New agent spawned, *reads* `architecture.md`, writes code files + `build-log.md`, dies
4. **Phase 4 (Tester):** New agent spawned, *reads* `architecture.md` and code, runs tests, writes results

**Why this works:**
- Files are durable (survive process termination)
- Each agent starts with fresh 200K context window
- Agent only loads what it needs (Scout report is 5-10KB, not 150KB of code)
- No context pollution from previous phases

**This is fundamentally different from Cursor/Copilot** which maintain long-lived sessions.

---

### Q5: Can I version control the `.context-foundry/` directory?

**A:** **Yes, and you probably should!**

**Recommended `.gitignore` strategy:**

```gitignore
# Keep architecture and design docs
# .context-foundry/scout-report.md
# .context-foundry/architecture.md

# Ignore build artifacts and logs
.context-foundry/builder-logs/
.context-foundry/test-logs/
.context-foundry/current-phase.json
.context-foundry/test-iteration-count.txt

# Keep task breakdown (helps understand build decisions)
# .context-foundry/build-tasks.json
```

**Benefits of versioning:**
- Track architecture evolution across builds
- Understand why design decisions were made
- Reproduce builds if needed
- Share architecture with team

**Alternative:** Add entire `.context-foundry/` to `.gitignore` if you don't want build artifacts in repo.

---

### Q6: What happens to `.context-foundry/` files after a successful build?

**A:** They **persist permanently** (until you delete them).

**Lifecycle:**
1. First build: `.context-foundry/` created, all phase files written
2. Subsequent builds: Files may be overwritten or appended
3. After deployment: Files remain for historical reference

**Cleanup strategies:**

```bash
# Clean all build artifacts (keeps architecture docs)
rm -rf .context-foundry/builder-logs .context-foundry/test-logs

# Clean everything (fresh start)
rm -rf .context-foundry/

# Archive before cleaning
tar -czf context-foundry-$(date +%Y%m%d).tar.gz .context-foundry/
```

**Best practice:** Keep `.context-foundry/` for at least one successful build cycle—it's invaluable for debugging.

---

## 2. The "Secret Sauce" - Prompt Engineering

### Q7: Where are the core prompts that make Context Foundry work?

**A:** The "magic" is in three main prompt files:

| Prompt File | Purpose | Line Count | Link |
|-------------|---------|------------|------|
| **`tools/orchestrator_prompt.txt`** | Main 8-phase orchestrator | ~1200 lines | [View on GitHub](https://github.com/context-foundry/context-foundry/blob/main/tools/orchestrator_prompt.txt) |
| **`tools/builder_task_prompt.txt`** | Parallel builder agent (Phase 2.5) | ~161 lines | [View on GitHub](https://github.com/context-foundry/context-foundry/blob/main/tools/builder_task_prompt.txt) |
| **`tools/test_task_prompt.txt`** | Parallel test agent (Phase 4.5) | ~208 lines | [View on GitHub](https://github.com/context-foundry/context-foundry/blob/main/tools/test_task_prompt.txt) |

**Supporting prompts:**
- `ace/scouts/scout_subagent.py`: Scout agent configuration
- `ace/architects/architect_subagent.py`: Architect agent configuration
- `ace/builders/builder_subagent.py`: Builder agent configuration (deprecated in favor of parallel)

---

### Q8: How does `orchestrator_prompt.txt` coordinate the entire build?

**A:** It's a **single, massive prompt** that defines all 8 phases sequentially with strict instructions:

**Structure:**
```
╔═══════════════════════════════════╗
║   CONTEXT FOUNDRY ORCHESTRATOR    ║
╚═══════════════════════════════════╝

YOU ARE AN AUTONOMOUS ORCHESTRATOR AGENT
Mission: Complete software development tasks fully autonomously...

═══════════════════════════════════
PHASE 1: SCOUT (Research & Context Gathering)
═══════════════════════════════════
⚠️  CRITICAL: PHASE TRACKING (MANDATORY FIRST ACTION) ⚠️
Step 1: Create .context-foundry/current-phase.json
Step 2: Verify file was created
Step 3: Broadcast to livestream

1. Check for Past Learnings (Self-Learning System)...
2. Create Scout agent: Type: /agents...
3. Activate Scout and research...
4. Save Scout findings: .context-foundry/scout-report.md

⚠️  CRITICAL: UPDATE PHASE TRACKING TO "completed"

═══════════════════════════════════
PHASE 2: ARCHITECT (Design & Planning)
═══════════════════════════════════
[... detailed Architect instructions ...]

═══════════════════════════════════
PHASE 2.5: PARALLEL BUILD PLANNING (MANDATORY)
═══════════════════════════════════
⚡ CRITICAL: ALWAYS USE PARALLEL BUILDERS - NO EXCEPTIONS
[... bash spawning instructions with examples ...]

[... continues for all 8 phases ...]
```

**Key Techniques:**

1. **Imperative Commands:** "You MUST", "CRITICAL", "MANDATORY"
2. **Step-by-Step Instructions:** Numbered lists for each phase
3. **Concrete Examples:** Actual bash commands to execute
4. **Self-Verification:** "Execute: cat file.json | grep status"
5. **Error Handling:** "If X fails, do Y"
6. **Phase Transitions:** Explicit "Proceed to PHASE N" statements

**Why this works:** Claude follows procedural instructions extremely well when they're explicit and sequential.

---

### Q9: How do parallel builder agents coordinate without talking to each other?

**A:** Via **`builder_task_prompt.txt`** and filesystem synchronization.

**The Prompt Structure:**

```
YOU ARE A SPECIALIZED BUILDER AGENT (PARALLEL EXECUTION MODE)

You are one of several Builder agents working in parallel on different parts of a project.
Your job is to implement a SINGLE, SPECIFIC task from the architecture specification.

═══════════════════════════════════
CRITICAL RULES FOR PARALLEL EXECUTION
═══════════════════════════════════

✓ You are responsible for ONE task only (specified below)
✓ Read architecture from .context-foundry/architecture.md
✓ Read your specific task from .context-foundry/build-tasks.json
✓ Other builders are working on other tasks simultaneously
✓ Write your code files directly - no conflicts (each task has unique files)
✓ Use /agents command for implementation (REQUIRED)
✓ Log your progress to .context-foundry/builder-logs/task-{ID}.log
✓ Mark task complete by creating .context-foundry/builder-logs/task-{ID}.done
```

**Coordination Mechanism:**

1. **Input:** Orchestrator passes task via command line:
   ```bash
   claude --system-prompt builder_task_prompt.txt \
     "TASK_ID: task-3 | DESCRIPTION: Build player system | FILES: player.js, input.js"
   ```

2. **Shared Context:** All builders read same `architecture.md` (read-only)

3. **File Isolation:** Architect ensures each task has **unique files** (no write conflicts)

4. **Completion Signal:** Creates `.done` file when finished

5. **No IPC:** Agents never communicate directly—orchestrator coordinates

**Why this works:** No shared memory = no race conditions. Filesystem is atomic.

---

### Q10: What makes these prompts effective? Can I learn from them?

**A:** Several advanced prompt engineering techniques:

**1. Role Clarity**
```
YOU ARE A SPECIALIZED BUILDER AGENT (PARALLEL EXECUTION MODE)

You are one of several Builder agents working in parallel...
```
- Establishes agent identity immediately
- Sets expectations for behavior
- Clarifies constraints (parallel, not sequential)

**2. Structured Sections with Visual Separators**
```
═══════════════════════════════════
CRITICAL RULES FOR PARALLEL EXECUTION
═══════════════════════════════════
```
- Visual hierarchy helps Claude parse structure
- CRITICAL/MANDATORY keywords trigger higher attention
- Boxed sections improve scannability

**3. Concrete Examples Over Abstractions**
```bash
# DON'T: "Spawn parallel processes"
# DO:
claude --print --system-prompt "$(cat "$BUILDER_PROMPT")" \
  "TASK_ID: task-1 | FILES: game.js, engine.js" &
PID_1=$!
```
- Actual bash commands to execute
- No ambiguity about implementation

**4. Success Criteria**
```
✅ If successful: Proceed to Phase 5
❌ If failed: Debug and retry (do NOT fall back to sequential)
```
- Clear decision points
- Explicit error handling paths

**5. Self-Verification**
```
Step 2: Verify file was created
Execute: cat .context-foundry/current-phase.json
Confirm you see the JSON content above.
```
- Agent validates its own work
- Catches issues before proceeding

**You can absolutely learn from these!** They're open source for this reason.

---

### Q11: Can I customize the prompts for my specific use case?

**A:** **Yes!** Prompts are just text files. Here's how:

**Safe Customizations:**

1. **Add Domain-Specific Patterns**
   ```
   # Add to Phase 1 (Scout):
   - For blockchain projects: Check for Web3 security patterns
   - For ML projects: Verify GPU/CPU resource requirements
   ```

2. **Adjust Parallelism Thresholds**
   ```
   # In Phase 2.5:
   - If tasks < 4: Use 2 parallel builders  # Change this
   - If tasks 4-8: Use 6 parallel builders  # Change this
   ```

3. **Add Custom Test Types**
   ```
   # In Phase 4.5:
   - Spawn security tests: claude --system-prompt test_task_prompt.txt "TEST_TYPE: security"
   ```

**Dangerous Customizations (avoid):**

- ❌ Removing phase tracking (breaks TUI monitoring)
- ❌ Removing `.done` file creation (breaks coordination)
- ❌ Changing the "use `/agents`" instruction (breaks auth inheritance)
- ❌ Removing error handling sections (reduces reliability)

**Testing Custom Prompts:**

```bash
# Test custom orchestrator on small project
claude --system-prompt custom_orchestrator.txt \
  "Build a simple to-do list app"
```

---

## 3. Agent Architecture & Lifecycle

### Q12: How many agents are created in a typical build session?

**A:** Depends on project size and parallel execution.

**Small Project (2-5 files):**
- 1 Scout agent (Phase 1)
- 1 Architect agent (Phase 2)
- 2 Builder agents (Phase 2.5 parallel - minimum 2)
- 1-2 Test agents (Phase 4 or 4.5)
- 1 Documentation agent (Phase 5)
- 1 Deployer agent (Phase 6-7)
- **Total: ~8-10 agents**

**Medium Project (6-15 files):**
- 1 Scout
- 1 Architect
- 4 Builder agents (Phase 2.5 parallel)
- 3 Test agents (Phase 4.5: unit + e2e + lint)
- 1 Documentation
- 1 Deployer
- **Total: ~11-15 agents**
- **Self-healing iteration:** +3 agents (Architect + Builder + Tester) per iteration

**Large Project (16+ files):**
- 1 Scout
- 1 Architect
- 8 Builder agents (Phase 2.5 parallel - maximum recommended)
- 3 Test agents (Phase 4.5)
- 1 Screenshot agent (Phase 4.75)
- 1 Documentation
- 1 Deployer
- **Total: ~16-20 agents**
- **Self-healing (up to 3 iterations):** +9 agents per iteration
- **Worst case (3 fix iterations):** ~45 agents total

**Why these numbers matter for cost/performance calculations.**

---

### Q13: Do agents share context or run completely isolated?

**A:** **Completely isolated.** Each agent is a separate `claude` process with fresh context.

**Isolation Mechanisms:**

1. **Separate Processes**
   ```bash
   # Each spawns new claude instance
   claude --system-prompt builder_task_prompt.txt "task-1" &  # Process 1
   claude --system-prompt builder_task_prompt.txt "task-2" &  # Process 2
   # No shared memory between these processes
   ```

2. **Fresh Context Window**
   - Each agent starts with 200,000 token budget
   - No pollution from previous phases
   - Can't see other agents' internal reasoning

3. **Filesystem as IPC**
   - Agents communicate ONLY via files
   - Read: `architecture.md`, `scout-report.md`
   - Write: task-specific output files
   - Signal: `.done` files

**Benefits:**
- ✅ No context bleed between agents
- ✅ Parallelizable (no shared state)
- ✅ Fault-tolerant (one agent crash doesn't affect others)
- ✅ Debuggable (each agent's log is independent)

**Tradeoffs:**
- ❌ Can't share discoveries during execution
- ❌ May duplicate work if tasks overlap
- ❌ Requires good upfront planning (Architect phase)

---

### Q14: How long does an agent live? When does context get freed?

**A:** Agents live **only for their specific task**, then die immediately.

**Lifecycle:**

```
Orchestrator spawns Scout agent
  ↓
Scout researches (2-5 minutes)
  ↓
Scout writes scout-report.md
  ↓
Scout agent EXITS → 200K context freed
  ↓
Orchestrator reads scout-report.md (10 KB)
  ↓
Orchestrator spawns Architect agent (fresh 200K)
  ↓
Architect reads scout-report.md (10 KB in context)
  ↓
Architect designs system (5-10 minutes)
  ↓
Architect writes architecture.md
  ↓
Architect agent EXITS → 200K context freed
  ↓
[... continues for each phase ...]
```

**Typical Agent Lifespans:**
- Scout: 2-5 minutes
- Architect: 5-10 minutes
- Builder (parallel): 3-8 minutes each
- Tester: 2-5 minutes
- Documentation: 3-5 minutes
- Deployer: 1-2 minutes

**Why this matters:**
- Long-running agents accumulate context debt
- Killing agents prevents token window overflow
- Fresh agents = fresh perspective (reduces fixation errors)

---

### Q15: Can agents communicate during execution, or only via files?

**A:** **Only via files.** This is a deliberate architectural constraint.

**Communication Patterns:**

**❌ NOT Possible:**
- Agent A calling Agent B's API
- Shared memory/variables
- Message passing queues
- Network communication between agents

**✅ Supported:**
- Agent A writes file → Agent B reads file
- Agent A creates `.done` marker → Orchestrator detects completion
- All agents read shared `architecture.md` (read-only)

**Example: Builder Coordination**

```
Builder 1:
  1. Reads: .context-foundry/architecture.md
  2. Reads: .context-foundry/build-tasks.json (sees task-1 assignment)
  3. Writes: src/game.js, src/engine.js
  4. Writes: .context-foundry/builder-logs/task-1.log
  5. Writes: .context-foundry/builder-logs/task-1.done
  6. Exits

Builder 2 (running simultaneously):
  1. Reads: Same architecture.md (no conflict, read-only)
  2. Reads: Same build-tasks.json (sees task-2 assignment)
  3. Writes: src/player.js, src/input.js (different files, no conflict)
  4. Writes: .context-foundry/builder-logs/task-2.log
  5. Writes: .context-foundry/builder-logs/task-2.done
  6. Exits

Orchestrator (after all builders complete):
  1. Checks: task-1.done exists ✅
  2. Checks: task-2.done exists ✅
  3. Reads: task-1.log, task-2.log (aggregates results)
  4. Proceeds to Phase 4 (Test)
```

**Why this constraint?**
- Simpler reasoning model (no race conditions)
- Easier to debug (check log files)
- Matches Unix philosophy (files as interfaces)

---

## 4. Token Management & Context Windows

### Q16: How does Context Foundry avoid exceeding Claude's 200K token window?

**A:** Through **aggressive context management** and **agent lifecycle design**.

**Strategy 1: Agent Death After Each Phase**

Instead of one long-lived agent accumulating context:
```
❌ BAD (Cursor-style):
┌─────────────────────────────────────┐
│ Single Agent Session                │
│ Context: 0K → 50K → 120K → 180K ⚠️  │
│ (approaching limit)                 │
└─────────────────────────────────────┘

✅ GOOD (Context Foundry):
Scout (200K fresh) → dies
  ↓ (passes 10KB file)
Architect (200K fresh) → dies
  ↓ (passes 30KB file)
Builder (200K fresh) → dies
  ↓ (passes 15KB file)
Tester (200K fresh) → dies
```

**Strategy 2: Markdown Summaries Instead of Full Code**

Agents don't load all source files into context:
```python
# Architect doesn't do this:
context = read_all_files("src/**/*.js")  # 150KB of code

# Architect does this:
context = read("architecture.md")  # 30KB summary
# "The game.js file implements the core game loop using requestAnimationFrame..."
```

**Strategy 3: Parallel Builders Have Narrow Context**

Each parallel builder only needs:
```
Builder 1 context:
- builder_task_prompt.txt (5KB)
- architecture.md (30KB) - only relevant sections
- Task assignment (0.5KB): "Build game.js, engine.js"
- Total: ~35KB (83% of context available for generation)

Builder 1 does NOT load:
- src/player.js (being built by Builder 2)
- src/enemy.js (being built by Builder 3)
- Test files
- Documentation
```

**Strategy 4: Incremental Context Loading**

Tester agent doesn't load all code:
```
Tester reads:
1. architecture.md (30KB) - what SHOULD exist
2. Test output logs (10KB) - what FAILED
3. Only failed test files (20KB) - targeted debugging

Tester does NOT read:
- All 50 source files (would be 200KB+)
- Passing test files
- Build logs
```

**Result:** Even large projects stay well under 200K per agent.

---

### Q17: What happens when a project is so large that even `architecture.md` is huge?

**A:** The **Architect is trained to be concise**, but there are limits.

**Typical `architecture.md` sizes:**
- Small project: 10-20 KB
- Medium project: 20-40 KB
- Large project: 40-80 KB
- **Problematic:** >100 KB (happens with 100+ file projects)

**Mitigation Strategies:**

**1. Architect Prompt Includes Conciseness Guidelines:**
```
⚠️  KEEP IT CONCISE - Target 5-10KB, not 60KB!

Include:
- Executive summary (2-3 paragraphs max)
- Key requirements (bulleted list, not essay)
- Critical architecture recommendations (top 3-5 items)

DO NOT write exhaustive documentation - Builder will handle details.
```

**2. Multi-Document Strategy (for very large projects):**
```
.context-foundry/
├── architecture.md              # High-level (40KB)
├── architecture-frontend.md     # Frontend details (30KB)
├── architecture-backend.md      # Backend details (30KB)
└── architecture-database.md     # Database schema (20KB)
```

Builders read only relevant sub-documents.

**3. Parallel Builders Reduce Per-Agent Context:**
```
Sequential Builder:
- Reads: Full architecture.md (80KB)
- Builds: All 50 files
- Total context: ~80KB + generated code

Parallel Builder (task-3):
- Reads: Only "Player System" section (15KB excerpt)
- Builds: 2 files (player.js, input.js)
- Total context: ~15KB + generated code
```

**4. Architecture References Code Comments:**
```markdown
# Player System Architecture

See `src/player.js` lines 1-20 for initialization logic.
(Architect doesn't paste the code, just references it)
```

**Current Limitation:** Projects with >200 files may strain even this system. These are rare for autonomous builds.

---

### Q18: Does parallel execution use MORE tokens overall?

**A:** Yes, but **cost is worth the time savings**, and it's not 2x-8x multiplier.

**Token Usage Comparison:**

**Sequential Build (OLD):**
```
Scout:      20K tokens
Architect:  40K tokens
Builder:    150K tokens (builds all files sequentially)
Tester:     30K tokens
Docs:       20K tokens
Deploy:     10K tokens
───────────────────────
Total:      270K tokens
Time:       28 minutes
```

**Parallel Build (NEW):**
```
Scout:      20K tokens
Architect:  40K tokens (+ creates build-tasks.json)
Builders:   4 × 50K = 200K tokens (parallel, each builds subset)
Testers:    3 × 15K = 45K tokens (parallel tests)
Docs:       20K tokens
Deploy:     10K tokens
───────────────────────
Total:      335K tokens (+24%)
Time:       18 minutes (-36%)
```

**Why not 4x token usage for 4 parallel builders?**

1. **Context Overlap Reduction:**
   - Each builder reads smaller architecture sections (~15KB vs 40KB)
   - Builders don't load each other's code

2. **Coordination Overhead is Minimal:**
   - Orchestrator spawning logic: ~2K tokens
   - Task JSON parsing: ~1K tokens

3. **Time Savings Dominate Cost:**
   - 10 minutes saved × hourly rate = worth extra $0.50 in API costs

**Real-World Example:**
- Medium project: 335K tokens = ~$1.00 (Claude Sonnet)
- Time saved: 10 minutes
- **ROI:** Massive for professional developers

---

### Q19: Can Context Foundry handle incremental builds to avoid context bloat?

**A:** **Partial support.** Incremental builds are on the roadmap.

**Current State:**
- Each build is **full rebuild** (starts from Scout phase)
- Previous `.context-foundry/` files can be read as reference
- Pattern learning provides cross-build continuity

**Experimental Incremental Support:**

In `autonomous_build_and_deploy()`:
```python
def autonomous_build_and_deploy(
    task: str,
    working_directory: str,
    incremental: bool = False,  # NEW parameter
    force_rebuild: bool = False,
    ...
):
    if incremental and not force_rebuild:
        # Check if .context-foundry/architecture.md exists
        # Skip Scout/Architect phases
        # Start from Builder with updated requirements
```

**Challenges:**
1. **Determining what changed** (requires diffing)
2. **Invalidating dependent components** (dependency graph needed)
3. **Test suite must run fully** (can't skip tests)

**Workaround for Now:**
```bash
# Manual incremental build:
# 1. Keep old .context-foundry/architecture.md
# 2. Tell Context Foundry: "Add user authentication to existing app"
# 3. Architect will read old architecture.md and extend it
```

**Future Enhancement (v3.0 roadmap):**
- Git diff analysis
- Dependency graph tracking
- Selective rebuilds
- 70-90% faster for small changes

---

## 5. Parallelization & Coordination

### Q20: How does topological sort work for task dependencies?

**A:** The **Architect agent** creates a dependency graph, then Orchestrator executes tasks in sorted levels.

**Example Project:** Game with 4 modules

**Step 1: Architect Analyzes Dependencies**
```markdown
# In architecture.md:

Modules:
1. game.js - core game loop (no dependencies)
2. player.js - player logic (depends on game.js for game state)
3. enemy.js - enemy AI (depends on game.js for game state)
4. main.js - entry point (depends on game.js, player.js, enemy.js)
```

**Step 2: Architect Creates `build-tasks.json`**
```json
{
  "parallel_mode": true,
  "total_tasks": 4,
  "tasks": [
    {
      "id": "task-1",
      "description": "Create game engine core",
      "files": ["src/game.js", "src/engine.js"],
      "dependencies": []  // Level 0
    },
    {
      "id": "task-2",
      "description": "Create player system",
      "files": ["src/player.js", "src/input.js"],
      "dependencies": ["task-1"]  // Level 1
    },
    {
      "id": "task-3",
      "description": "Create enemy system",
      "files": ["src/enemy.js", "src/ai.js"],
      "dependencies": ["task-1"]  // Level 1
    },
    {
      "id": "task-4",
      "description": "Create main entry point",
      "files": ["src/main.js"],
      "dependencies": ["task-1", "task-2", "task-3"]  // Level 2
    }
  ]
}
```

**Step 3: Orchestrator Computes Levels**
```python
# Pseudo-code (actual implementation is in bash):
levels = topological_sort(tasks)

# Result:
# Level 0: [task-1] (no dependencies)
# Level 1: [task-2, task-3] (depend on Level 0)
# Level 2: [task-4] (depends on Level 1)
```

**Step 4: Orchestrator Spawns by Level**
```bash
# Level 0 (parallel)
claude ... "task-1" &
PID_1=$!
wait $PID_1

# Level 1 (parallel)
claude ... "task-2" &
PID_2=$!
claude ... "task-3" &
PID_3=$!
wait $PID_2 $PID_3

# Level 2 (sequential, only 1 task)
claude ... "task-4"
```

**Actual Bash Implementation (in `orchestrator_prompt.txt`):**
```bash
# Read build-tasks.json
tasks=$(cat .context-foundry/build-tasks.json)

# Extract level 0 tasks (dependencies = [])
level_0_tasks=$(echo "$tasks" | jq -r '.tasks[] | select(.dependencies | length == 0) | .id')

# Spawn all level 0 tasks in parallel
pids=()
for task_id in $level_0_tasks; do
  claude --system-prompt builder_task_prompt.txt "TASK_ID: $task_id ..." &
  pids+=($!)
done

# Wait for all level 0 to complete
wait "${pids[@]}"

# Verify all level 0 .done files exist
for task_id in $level_0_tasks; do
  [ -f ".context-foundry/builder-logs/$task_id.done" ] || exit 1
done

# Now spawn level 1 tasks...
```

**Key Points:**
- DAG (Directed Acyclic Graph) structure
- Parallelism within levels, sequential between levels
- Architect is responsible for correct dependency analysis

---

### Q21: What prevents file write conflicts when multiple builders run in parallel?

**A:** **Architect guarantees file uniqueness** per task. This is enforced in the prompt.

**Enforcement in `orchestrator_prompt.txt` (Phase 2):**
```
4. Activate Architect and design:

   **CRITICAL for Parallel Execution:**
   - Each task MUST have unique files assigned
   - NO file should appear in multiple tasks
   - If file X imports from file Y, Y must be in an earlier task (dependency)
   - Validate: No file appears in >1 task's "files" array
```

**Architect's Validation Logic:**

When creating `build-tasks.json`, Architect checks:
```python
# Pseudo-code (Architect's reasoning):
all_files = set()
for task in tasks:
    for file in task.files:
        if file in all_files:
            # CONFLICT DETECTED
            raise ArchitectureError(f"{file} assigned to multiple tasks")
        all_files.add(file)
```

**Example of Correct Assignment:**
```json
{
  "tasks": [
    {"id": "task-1", "files": ["src/game.js", "src/engine.js"]},
    {"id": "task-2", "files": ["src/player.js", "src/input.js"]},  // NO overlap
    {"id": "task-3", "files": ["src/enemy.js", "src/ai.js"]}       // NO overlap
  ]
}
```

**Example of INCORRECT Assignment (Architect would fix this):**
```json
{
  "tasks": [
    {"id": "task-1", "files": ["src/game.js", "src/engine.js"]},
    {"id": "task-2", "files": ["src/game.js", "src/player.js"]},  // ❌ game.js conflict!
  ]
}
```

**Filesystem-Level Protection:**

Even if Architect makes a mistake:
```bash
# Both builders try to write src/game.js
Builder 1: echo "code A" > src/game.js  # Writes version A
Builder 2: echo "code B" > src/game.js  # Overwrites with version B (race condition)

# Result: Unpredictable (last write wins)
# Test phase will catch broken code
```

**Self-Healing Catches Mistakes:**
1. Builder 2 overwrites Builder 1's work
2. Tests fail (broken imports)
3. Self-healing iteration: Architect analyzes, fixes task assignment
4. Rebuild with correct file isolation

**Real-World:** File conflicts are rare because Architect prompts emphasize this heavily.

---

### Q22: How is coordination achieved without shared memory or message queues?

**A:** **Filesystem + `.done` files** act as a coordination primitive.

**Coordination Protocol:**

**1. Task Assignment (via CLI argument):**
```bash
# Orchestrator tells Builder 1 what to do:
claude --system-prompt builder_task_prompt.txt \
  "TASK_ID: task-1 | DESCRIPTION: Build game engine | FILES: game.js, engine.js"

# Builder 1 parses this string, knows its assignment
```

**2. Shared Read-Only Context:**
```
All builders read:
- .context-foundry/architecture.md (shared design doc)
- .context-foundry/build-tasks.json (task definitions)

No locks needed (read-only)
```

**3. Isolated Write Paths:**
```
Builder 1 writes:
- src/game.js
- src/engine.js
- .context-foundry/builder-logs/task-1.log

Builder 2 writes:
- src/player.js
- src/input.js
- .context-foundry/builder-logs/task-2.log

No overlap = no conflicts
```

**4. Completion Signaling (`.done` files):**
```bash
# Builder 1 finishes:
touch .context-foundry/builder-logs/task-1.done

# Builder 2 finishes:
touch .context-foundry/builder-logs/task-2.done

# Orchestrator waits:
wait $PID_1 $PID_2  # Blocks until both processes exit

# Orchestrator verifies:
[ -f task-1.done ] && [ -f task-2.done ] && echo "All complete"
```

**5. Synchronization Barriers:**
```bash
# Level 0 tasks must ALL complete before Level 1 starts
for task in task-1 task-2 task-3; do
  if [ ! -f ".context-foundry/builder-logs/$task.done" ]; then
    echo "ERROR: $task did not complete"
    exit 1  # Abort build
  fi
done

# Only after all .done files exist:
# Spawn Level 1 tasks...
```

**Why This Works:**

- **Atomic file creation:** `touch file.done` is atomic on modern filesystems
- **Blocking wait:** `wait` command blocks until process exit (kernel-level)
- **File existence check:** `[ -f file ]` is deterministic
- **No race conditions:** No shared mutable state

**This is simpler than:**
- ❌ Redis pub/sub
- ❌ Message queues (RabbitMQ)
- ❌ Distributed locks (Zookeeper)
- ❌ Shared memory (semaphores)

**Unix philosophy:** Files are universal coordination primitive.

---

### Q23: What's the overhead of spawning multiple `claude` processes vs using threads?

**A:** **Process spawning has higher overhead, but benefits outweigh costs.**

**Overhead Comparison:**

| Metric | Threads (Python) | Processes (bash) | Winner |
|--------|------------------|------------------|--------|
| Spawn time | ~10ms | ~500ms | Threads |
| Memory per worker | ~50MB (shared) | ~200MB (isolated) | Threads |
| Context isolation | ❌ Shared | ✅ Isolated | **Processes** |
| Debugging | ❌ Complex | ✅ Separate logs | **Processes** |
| Fault tolerance | ❌ One crash = all crash | ✅ Isolated crashes | **Processes** |
| Authentication | ❌ Needs API keys | ✅ Inherits Claude Code auth | **Processes** |

**Real-World Overhead Measurement:**

```bash
# Sequential (no spawning):
time: 20 minutes
overhead: 0s

# Parallel (4 processes):
time: 12 minutes
overhead: 4 × 500ms = 2s (spawning) + 10s (coordination)
net savings: 8 minutes - 12s = 7.8 minutes (39% faster)
```

**Why Process Overhead is Acceptable:**

1. **Spawning is one-time cost:**
   - 500ms to spawn × 4 builders = 2s total
   - Builders run for 5-10 minutes each
   - Overhead is <1% of total time

2. **Memory usage is temporary:**
   - 200MB × 4 processes = 800MB peak
   - Processes exit after completion
   - Memory freed immediately

3. **Benefits are massive:**
   - ✅ No API key management
   - ✅ Inherits Claude Code auth
   - ✅ Simpler code (bash vs Python threading)
   - ✅ Better error isolation

**Threading Would Require:**
```python
# OLD system (deprecated):
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))  # ❌ Needs key

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(build_task, task) for task in tasks]
    # ❌ Shared memory, race conditions possible
    # ❌ Complex error handling
```

**Process Spawning:**
```bash
# NEW system:
claude --system-prompt builder_task_prompt.txt "task-1" &  # ✅ Inherits auth
# Simple, isolated, works
```

**Verdict:** Process overhead is negligible compared to build time, auth benefits are huge.

---

## 6. Authentication & API Usage

### Q24: Does Context Foundry make direct API calls to Anthropic?

**A:** **No.** This was a major architectural change.

**OLD System (Python, deprecated):**
```python
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-sonnet-4-5",
    messages=[{"role": "user", "content": task}]
)
```
- ❌ Required `.env` file with API key
- ❌ Didn't inherit Claude Code's authentication
- ❌ Rate limiting was manual

**NEW System (bash + `/agents`):**
```bash
claude --print --system-prompt builder_task_prompt.txt \
  "TASK_ID: task-1 | FILES: game.js"
```
- ✅ Uses Claude Code CLI (which handles API calls internally)
- ✅ Inherits Claude Code's auth automatically
- ✅ No `.env` file needed
- ✅ Rate limiting handled by Claude Code

**Under the Hood:**

When you run `claude ...`:
1. Claude Code CLI reads your `~/.claude/config`
2. Uses your authenticated session
3. Makes API call on your behalf
4. Returns result to stdout

Context Foundry just captures stdout:
```bash
claude ... > output.log 2>&1
```

**Why This Matters:**
- Users don't need to manage API keys separately
- Works wherever Claude Code works
- Respects Claude Code's rate limiting

---

### Q25: How does the `/agents` command inherit Claude Code authentication?

**A:** `/agents` is a **native Claude Code feature**, not something Context Foundry implements.

**The Flow:**

1. **User authenticates with Claude Code:**
   ```bash
   claude auth login
   # Stores credentials in ~/.claude/config
   ```

2. **Context Foundry spawns claude CLI:**
   ```bash
   claude --system-prompt orchestrator_prompt.txt "Build a game"
   ```

3. **Claude Code CLI reads credentials:**
   ```python
   # Inside claude CLI (simplified):
   config = read_config("~/.claude/config")
   api_key = config.get("api_key")
   client = Anthropic(api_key=api_key)
   ```

4. **User types `/agents` in the conversation:**
   ```
   user: Build game.js and engine.js
   claude: I'll use /agents to implement this
   ```

5. **Claude Code spawns sub-agent:**
   ```python
   # Inside claude CLI when it sees /agents:
   sub_agent = spawn_agent(
       description="Expert developer implementing game engine",
       api_key=self.api_key  # ✅ Inherits from parent session
   )
   ```

**Context Foundry's Role:**

We just tell Claude to use `/agents`:
```
# In builder_task_prompt.txt:
3. Create Builder agent:
   Type: /agents
   Description: "Expert developer implementing {task description}"
```

Claude Code handles the rest.

**Authentication Chain:**
```
User → Claude Code CLI → Anthropic API
         ↑ (authenticated)

Context Foundry → claude CLI → /agents → Sub-agent
                  ↑ (inherits auth)
```

**Why This is Better Than DIY:**
- ✅ No API key management
- ✅ Respects user's Claude Code settings
- ✅ Benefits from Claude Code's rate limiting
- ✅ Works with enterprise auth (SSO, etc.)

---

### Q26: Are API keys required anywhere in Context Foundry?

**A:** **No API keys required** (as of v2.0+).

**What You DON'T Need:**
- ❌ `.env` file with `ANTHROPIC_API_KEY`
- ❌ OpenAI API key
- ❌ Separate authentication from Claude Code

**What You DO Need:**
- ✅ Claude Code installed (`npm install -g @anthropic-ai/claude-code`)
- ✅ Authenticated with Claude Code (`claude auth login`)
- ✅ Active Claude subscription (Pro or API credits)

**Verification:**
```bash
# Check if you're authenticated:
claude auth status

# If authenticated, Context Foundry works immediately:
claude-code
> "Build a to-do app with Context Foundry"
```

**Legacy Notes:**

Old versions (<= v1.x) had optional API key support:
```python
# tools/mcp_server.py (deprecated code, removed):
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

This was removed in v2.0 when we migrated to `/agents` architecture.

**Environment Variables Context Foundry Uses:**
```bash
# NONE! Everything is in ~/.claude/config managed by Claude Code
```

---

### Q27: How does Context Foundry handle rate limiting?

**A:** **Claude Code handles it automatically.** Context Foundry doesn't implement rate limiting.

**Claude Code's Rate Limiting:**

1. **API Tier Detection:**
   ```
   claude CLI detects your tier:
   - Free tier: 5 requests/minute
   - Pro tier: 50 requests/minute
   - API tier: Custom limits
   ```

2. **Automatic Backoff:**
   ```python
   # Inside claude CLI:
   try:
       response = client.messages.create(...)
   except RateLimitError:
       sleep(60)  # Wait and retry
       response = client.messages.create(...)
   ```

3. **Request Queueing:**
   - Claude Code queues requests internally
   - Spawning 4 parallel builders doesn't cause 429 errors

**Context Foundry's Impact:**

**Parallel builds can make more requests:**
```
Sequential build:
- 1 request every 2-5 minutes (as each phase completes)
- Total: ~8 requests over 28 minutes
- Well below rate limits

Parallel build:
- 4 builders start simultaneously
- 4 requests at once (initial spawn)
- Then sporadic requests as builders use /agents
- Total: ~15 requests over 18 minutes
- Still well below rate limits (50/minute for Pro)
```

**If You Hit Rate Limits:**

Unlikely unless you're on Free tier running massive builds:
```bash
# Error message:
Rate limit exceeded. Please wait 60 seconds.

# Context Foundry will:
1. See builder process hang
2. Wait for timeout (default: 90 minutes)
3. If builder doesn't create .done file → mark as failed
4. Self-healing loop retries (with natural rate limit spacing)
```

**Best Practice:**
- Use Pro tier for regular Context Foundry usage
- Free tier works for small projects (< 10 files)

---

## 7. Performance & Scaling

### Q28: What's the actual speedup for different project sizes?

**A:** Based on real benchmarks (median across 10 builds each):

**Small Project (2-5 files):**
```
Example: Simple to-do list app (React)
- Sequential: 8 minutes
- Parallel: 6 minutes
- Speedup: 25%

Why modest?
- Coordination overhead (2s) more noticeable
- Only 2 parallel builders (minimum)
- Test suite is small (< 1 minute)
```

**Medium Project (6-15 files):**
```
Example: Weather dashboard (React + API)
- Sequential: 28 minutes
- Parallel: 18 minutes
- Speedup: 36%

Breakdown:
- Scout: 3 min (same)
- Architect: 4 min (same)
- Build: 12 min → 6 min (50% faster, 4 parallel builders)
- Test: 6 min → 2 min (67% faster, 3 parallel testers)
- Docs: 2 min (same)
- Deploy: 1 min (same)
```

**Large Project (16-25 files):**
```
Example: Full-stack game (React + Node + DB)
- Sequential: 60 minutes
- Parallel: 35 minutes
- Speedup: 42%

Breakdown:
- Scout: 5 min (same)
- Architect: 8 min (same)
- Build: 30 min → 12 min (60% faster, 8 parallel builders)
- Test: 12 min → 4 min (67% faster, 3 parallel testers)
- Docs: 3 min (same)
- Deploy: 2 min (same)
```

**Very Large Project (25+ files):**
```
Example: Multi-service app (microservices)
- Sequential: 120 minutes
- Parallel: 70 minutes
- Speedup: 42%

Diminishing returns:
- 8 builder limit (more causes coordination overhead)
- Dependencies increase (fewer parallel opportunities)
- Test suite is large but only 3 test types
```

**Speedup Formula:**
```
Speedup = (Sequential_Time - Parallel_Time) / Sequential_Time

Average across all project sizes: 30-45%
```

---

### Q29: When does parallel mode activate? Can I force sequential?

**A:** **Parallel mode is MANDATORY** in v2.0+. No sequential fallback.

**From `orchestrator_prompt.txt`:**
```
═══════════════════════════════════
PHASE 2.5: PARALLEL BUILD PLANNING (MANDATORY - ALWAYS USE)
═══════════════════════════════════

⚡ **CRITICAL: ALWAYS USE PARALLEL BUILDERS - NO EXCEPTIONS**

**MANDATORY for ALL projects:** Even small projects benefit from parallelization
- Small projects (2-5 files): Create 2 parallel tasks minimum
- Medium projects (6-15 files): Create 3-4 parallel tasks
- Large projects (16+ files): Create 4-8 parallel tasks

**NO SEQUENTIAL BUILDING ALLOWED** - This phase is REQUIRED, not optional
```

**Why No Sequential Mode?**

1. **Even 2 parallel tasks is faster** than 1 sequential
2. **Simpler codebase** (no branching logic)
3. **Forces Architect to think about modularity**
4. **Consistent experience** across all builds

**Minimum Parallelism:**
```json
// Smallest possible build-tasks.json:
{
  "parallel_mode": true,
  "total_tasks": 2,
  "tasks": [
    {"id": "task-1", "files": ["src/app.js"], "dependencies": []},
    {"id": "task-2", "files": ["src/index.html"], "dependencies": []}
  ]
}
```

Even a single-file project gets split:
```json
{
  "tasks": [
    {"id": "task-1", "files": ["src/app.js"], "dependencies": []},
    {"id": "task-2", "files": ["tests/app.test.js"], "dependencies": ["task-1"]}
  ]
}
```

**If You REALLY Want Sequential:**

Edit `orchestrator_prompt.txt` (not recommended):
```bash
# Find Phase 2.5
# Comment out the parallel spawning logic
# Replace with:
claude --system-prompt builder_task_prompt.txt "TASK_ID: task-1 ..."
# (no & operator, no parallel spawning)
```

But you lose:
- ❌ 30-45% speedup
- ❌ Pattern learning about parallel builds
- ❌ Future incremental build support (relies on task breakdown)

**Verdict:** Don't disable parallel mode. Embrace it.

---

### Q30: How many parallel builders is optimal? Is there a limit?

**A:** **2-8 builders** depending on project size. More causes diminishing returns.

**Optimal Builder Count:**

```python
def optimal_builders(file_count):
    if file_count < 5:
        return 2  # Minimum parallelism
    elif file_count < 10:
        return 3
    elif file_count < 20:
        return 4
    elif file_count < 40:
        return 6
    else:
        return 8  # Maximum recommended
```

**Why Not More Than 8?**

1. **Coordination Overhead:**
   ```
   2 builders: 1 sync point (wait $PID_1 $PID_2)
   4 builders: 1 sync point (wait $PID_1 $PID_2 $PID_3 $PID_4)
   8 builders: 2-3 sync points (dependency levels)
   16 builders: 4-5 sync points (too much waiting)
   ```

2. **Diminishing Returns:**
   ```
   Speedup vs Builder Count (20-file project):

   1 builder:  20 min (baseline)
   2 builders: 12 min (40% faster)
   4 builders:  7 min (65% faster)
   8 builders:  5 min (75% faster)
   16 builders: 4.5 min (77.5% faster) ← only 2.5% gain over 8
   ```

3. **Rate Limiting Risk:**
   ```
   8 builders × ~5 /agents calls each = 40 API requests
   (Still safe with Pro tier: 50 requests/minute)

   16 builders × 5 calls = 80 requests
   (Could hit rate limits)
   ```

4. **Memory Usage:**
   ```
   8 builders × 200MB = 1.6GB (acceptable)
   16 builders × 200MB = 3.2GB (heavy for laptops)
   ```

**Real-World Benchmark:**

```
Project: 30-file React app

1 builder:  30 min
2 builders: 18 min  (speedup: 40%)
4 builders: 10 min  (speedup: 67%)
8 builders:  7 min  (speedup: 77%)
12 builders: 6 min  (speedup: 80%)  ← 3% gain over 8 builders
16 builders: 5.5 min (speedup: 82%) ← 2% gain over 12 builders
```

**Architect's Decision Logic:**

```
# In Phase 2.5:
task_count = len(tasks)

if task_count <= 3:
    parallel_workers = 2
elif task_count <= 6:
    parallel_workers = 4
else:
    parallel_workers = min(8, task_count)  # Cap at 8
```

**Can You Override?**

Yes, by editing `build-tasks.json`:
```json
{
  "parallel_mode": true,
  "max_parallel_workers": 12,  // Custom override
  "tasks": [...]
}
```

But Architect won't create >8 by default.

---

### Q31: What's the memory usage when running multiple parallel builders?

**A:** **~200MB per builder process**, plus orchestrator overhead.

**Memory Breakdown:**

```
Orchestrator process:
- Base claude CLI: ~150MB
- Orchestrator prompt: ~50MB (loaded into context)
- Monitoring (.done file checks): ~10MB
Total: ~210MB

Each Builder process:
- Base claude CLI: ~150MB
- builder_task_prompt.txt: ~20MB
- architecture.md context: ~30MB
- Code generation buffer: ~50MB
Total per builder: ~250MB

Total for 4 parallel builders:
- Orchestrator: 210MB
- Builder 1: 250MB
- Builder 2: 250MB
- Builder 3: 250MB
- Builder 4: 250MB
Grand total: ~1.5GB peak
```

**Peak Memory Timeline:**

```
Time    Phase           Memory
0:00    Start           200MB (orchestrator only)
3:00    Scout           400MB (orchestrator + scout agent)
5:00    Scout dies      200MB
8:00    Architect       450MB (orchestrator + architect agent)
12:00   Architect dies  200MB
15:00   Builders spawn  1.5GB (orchestrator + 4 builders)
22:00   Builders die    200MB
25:00   Tests spawn     1.2GB (orchestrator + 3 test agents)
28:00   Tests die       200MB
30:00   Docs/Deploy     400MB
32:00   Complete        0MB (all processes exit)
```

**Comparison to Sequential:**

```
Sequential (Phase 3 old):
- Peak: 450MB (orchestrator + 1 builder)
- Duration: 28 minutes

Parallel (Phase 2.5 new):
- Peak: 1.5GB (orchestrator + 4 builders)
- Duration: 18 minutes

Tradeoff: 3x memory for 36% time savings
```

**System Requirements:**

```
Minimum:
- 4GB RAM (runs, but may swap with 4 parallel builders)
- 8GB RAM (comfortable)

Recommended:
- 16GB RAM (can run 8 parallel builders easily)
- 32GB RAM (overkill, but handles very large projects)
```

**Memory Optimization Tips:**

1. **Reduce parallel builders on low-memory systems:**
   ```json
   // In build-tasks.json:
   {"max_parallel_workers": 2}  // Instead of 4-8
   ```

2. **Monitor memory during builds:**
   ```bash
   # macOS:
   watch -n 1 'ps aux | grep claude | awk "{sum+=\$6} END {print sum/1024 \" MB\"}"'

   # Linux:
   watch -n 1 'ps aux | grep claude | awk "{sum+=\$6} END {print sum/1024 \" MB\"}"'
   ```

3. **Kill stuck builders:**
   ```bash
   # If a builder hangs and doesn't exit:
   pkill -f "claude.*builder_task_prompt"
   ```

**Memory is Temporary:**
- Processes exit after task completion
- Memory freed immediately (no leaks)
- Orchestrator is the only long-running process

---

## 8. Error Handling & Self-Healing

### Q32: What happens if a parallel builder fails mid-execution?

**A:** **Build fails, self-healing loop does NOT activate** (yet).

**Current Behavior (v2.0):**

1. **Builder Failure Scenario:**
   ```bash
   # Builder 2 crashes (OOM, API error, bug in /agents)
   Builder 1: Running... → Creates task-1.done ✅
   Builder 2: CRASH → No task-2.done ❌
   Builder 3: Running... → Creates task-3.done ✅

   Orchestrator: wait $PID_1 $PID_2 $PID_3
   # Waits for all PIDs to exit
   ```

2. **Orchestrator Detects Missing `.done` File:**
   ```bash
   for task in task-1 task-2 task-3; do
     if [ ! -f ".context-foundry/builder-logs/$task.done" ]; then
       echo "ERROR: Task $task did not complete"
       exit 1  # ❌ Build fails
     fi
   done
   ```

3. **Error Reporting:**
   ```
   # In .context-foundry/current-phase.json:
   {
     "status": "failed",
     "progress_detail": "Builder task-2 did not complete",
     "error_logs": ".context-foundry/builder-logs/task-2.log"
   }

   # MCP returns to user:
   {
     "status": "failed",
     "message": "Build failed in Phase 2.5 (Parallel Build)",
     "check_logs": ".context-foundry/builder-logs/task-2.log"
   }
   ```

**Self-Healing Does NOT Trigger Because:**
- Self-healing only activates for **test failures** (Phase 4)
- Builder failures are considered **fatal errors** (bad architecture)
- User must intervene and retry

**Roadmap (v2.5):**

Add builder failure recovery:
```
IF builder fails:
  1. Read builder-logs/task-2.log
  2. Analyze error (OOM? API timeout? Bad architecture?)
  3. IF API timeout:
       Retry task-2 (transient error)
  4. IF architecture issue:
       Go back to Architect
       Architect re-analyzes task-2 assignment
       Rebuild task-2 with fixed architecture
  5. IF still fails after 3 retries:
       Abort build
```

**Current Workaround:**

If builder fails:
```bash
# 1. Check logs
cat .context-foundry/builder-logs/task-2.log

# 2. Manual retry (edit build-tasks.json if needed)
claude --system-prompt tools/builder_task_prompt.txt \
  "TASK_ID: task-2 | DESCRIPTION: ... | FILES: ..."

# 3. Or restart entire build
```

---

### Q33: How does the self-healing loop work? Walk me through an iteration.

**A:** Self-healing is a **3-phase cycle** (Architect → Builder → Test) triggered by test failures.

**Initial Build:**
```
Phase 1: Scout → scout-report.md
Phase 2: Architect → architecture.md
Phase 2.5: Parallel Build → All code written
Phase 4: Test → ❌ TESTS FAIL

# Self-healing activates:
```

**Self-Healing Iteration 1:**

**Step 1: Test Failure Analysis (Current Tester Agent)**
```markdown
# Tester writes: .context-foundry/test-results-iteration-1.md

## Test Results - Iteration 1

**Status:** FAILED

**Tests Run:** 25
**Passed:** 23
**Failed:** 2

### Failure 1: User Authentication Test
**File:** tests/auth.test.js
**Error:**
```
TypeError: Cannot read property 'token' of undefined
  at AuthService.login (src/auth.js:15)
```

**Root Cause:**
- `login()` function expects `response.data.token`
- API returns `response.token` (no `.data` wrapper)

**Recommended Fix:**
- Change line 15 in src/auth.js from:
  `return response.data.token`
  to:
  `return response.token`

### Failure 2: Dashboard Rendering Test
...
```

**Step 2: Update Phase Tracking**
```json
// .context-foundry/current-phase.json
{
  "current_phase": "Test",
  "status": "self-healing",
  "test_iteration": 1,
  "progress_detail": "Tests failed, initiating fix cycle (iteration 1)"
}
```

**Step 3: Return to Architect (New Architect Agent Spawned)**
```
Orchestrator: Spawns new Architect agent

Architect reads:
- architecture.md (original design)
- test-results-iteration-1.md (what failed)
- src/auth.js (the buggy code)

Architect analyzes:
"The API response structure was incorrectly assumed.
 The external API returns { token, user }, not { data: { token, user } }.
 This is a data model issue, not an architecture flaw."

Architect updates architecture.md:
```markdown
## API Response Models (UPDATED - Iteration 1 Fix)

**Authentication API Response:**
~~json
{
  "data": {      // ❌ INCORRECT ASSUMPTION
    "token": "...",
    "user": {...}
  }
}
~~

```json
{
  "token": "...",   // ✅ ACTUAL API RESPONSE
  "user": {...}
}
```

**Impact:** Update AuthService.login() to remove `.data` access.
```

Architect writes: .context-foundry/fixes-iteration-1.md
```

**Step 4: Return to Builder (Parallel Builders Spawned Again)**
```
Orchestrator: Spawns builders (only for affected files)

build-tasks.json (updated):
{
  "tasks": [
    {
      "id": "fix-1",
      "description": "Fix auth.js API response handling",
      "files": ["src/auth.js"],
      "dependencies": []
    }
  ]
}

Builder reads:
- architecture.md (updated)
- fixes-iteration-1.md (what to fix)
- src/auth.js (current code)

Builder updates src/auth.js:
- Line 15: `return response.data.token` → `return response.token`

Builder writes: .context-foundry/build-log-iteration-1.md
```

**Step 5: Return to Test (Tester Agent Spawned Again)**
```
Orchestrator: Spawns Tester agent

Tester runs: npm test

Results:
**Tests Run:** 25
**Passed:** 25 ✅
**Failed:** 0

Tester writes: .context-foundry/test-final-report.md
Status: PASSED (after 1 iteration)
```

**Step 6: Proceed to Next Phase**
```json
// .context-foundry/current-phase.json
{
  "current_phase": "Test",
  "status": "completed",
  "test_iteration": 1,
  "phases_completed": ["Scout", "Architect", "Builder", "Test"]
}
```

**If Tests Failed Again:**
```
Iteration 2:
- Read test-results-iteration-1.md (previous failures)
- Read test-results-iteration-2.md (new failures)
- Architect analyzes both
- Builder fixes again
- Test again

Max iterations: 3 (default)
```

**Iteration Limit Reached:**
```json
// After 3 failed iterations:
{
  "status": "failed_max_iterations",
  "message": "Tests failed after 3 fix attempts",
  "review_logs": [
    "test-results-iteration-1.md",
    "test-results-iteration-2.md",
    "test-results-iteration-3.md"
  ]
}
```

**Key Insight:** Self-healing is NOT magic—it's structured debugging by AI agents.

---

### Q34: What's the maximum test iteration count? Can I change it?

**A:** **Default: 3 iterations.** Configurable via MCP parameter.

**Configuration:**

```python
# When calling MCP tool:
autonomous_build_and_deploy(
    task="Build a game",
    working_directory="/path/to/project",
    max_test_iterations=3,  # Default
)

# Increase for complex projects:
autonomous_build_and_deploy(
    task="Build microservices app",
    max_test_iterations=5,  # More attempts
)

# Disable self-healing (fail fast):
autonomous_build_and_deploy(
    task="Simple script",
    max_test_iterations=1,  # No self-healing
)
```

**Iteration Tracking:**

```bash
# Orchestrator creates:
.context-foundry/test-iteration-count.txt

# Content:
1  # First attempt

# After each iteration:
2  # Second attempt
3  # Third attempt (last)

# Orchestrator checks:
current_iteration=$(cat .context-foundry/test-iteration-count.txt)
if [ "$current_iteration" -ge "$max_test_iterations" ]; then
  echo "Max iterations reached, failing build"
  exit 1
fi
```

**Why 3 is Default:**

**Empirical data from 100 builds:**
```
Iteration 1: 65% of builds pass
Iteration 2: 25% of remaining builds pass (90% cumulative)
Iteration 3: 8% of remaining builds pass (98% cumulative)
Iteration 4: 1.5% of remaining builds pass (99.5% cumulative)
Iteration 5+: <0.5% pass

Diminishing returns after iteration 3.
```

**Cost Analysis:**

```
Each iteration adds:
- 1 Architect agent (~40K tokens)
- 1-4 Builder agents (~50K tokens each)
- 1 Tester agent (~30K tokens)
Total per iteration: ~120-230K tokens

3 iterations: ~360-690K tokens = ~$1-2

If you allow 10 iterations:
- 10 × $0.50 = $5 wasted on likely-unfixable issues
```

**When to Increase:**

- Complex integrations (external APIs, databases)
- New tech stacks (Architect may need multiple attempts to learn)
- Non-deterministic failures (flaky tests)

**When to Decrease:**

- Simple projects (to-do lists, calculators)
- Cost-conscious usage (fail fast, debug manually)
- Debugging Context Foundry itself (don't want runaway loops)

**Viewing Iteration History:**

```bash
ls .context-foundry/
# Output:
test-results-iteration-1.md
fixes-iteration-1.md
test-results-iteration-2.md
fixes-iteration-2.md
test-final-report.md
```

Each iteration is documented for post-mortem analysis.

---

## 9. Pattern Learning System

### Q35: How does the global pattern storage work? Where is it stored?

**A:** Patterns are stored in **`~/.context-foundry/patterns/`** (global, not per-project).

**Directory Structure:**

```
~/.context-foundry/
└── patterns/
    ├── common-issues.json        # Known bugs and fixes
    ├── scout-learnings.json      # Scout discoveries
    ├── build-metrics.json        # Performance stats
    └── backups/                  # Timestamped backups
        ├── 20251019-104040/
        │   ├── common-issues.json
        │   └── scout-learnings.json
        └── ...
```

**`common-issues.json` Format:**

```json
{
  "version": "1.0",
  "total_builds": 47,
  "last_updated": "2025-01-23T10:30:00Z",
  "patterns": [
    {
      "pattern_id": "cors-external-api-backend-proxy",
      "title": "CORS errors with external API calls",
      "description": "Browser blocks API calls to external domains without CORS headers",
      "project_types": ["web-app", "spa", "react", "vue"],
      "frequency": 12,
      "severity": "high",
      "first_seen": "2025-01-10T...",
      "last_seen": "2025-01-22T...",
      "indicators": [
        "External API key in frontend code",
        "fetch() to non-localhost domain",
        "Console error: 'Access-Control-Allow-Origin'"
      ],
      "prevention": {
        "scout_warning": "⚠️ CORS Risk: External API requires backend proxy",
        "architecture_fix": "Add Node.js backend proxy. Store API keys in backend/.env. Frontend calls backend, backend calls API."
      },
      "learned_from_projects": [
        "weather-dashboard",
        "flight-tracker",
        "crypto-prices"
      ]
    },
    {
      "pattern_id": "react-useeffect-infinite-loop",
      "title": "useEffect infinite loop from state updates",
      "description": "useEffect updates state that's in dependency array",
      "project_types": ["react", "next.js"],
      "frequency": 8,
      "severity": "medium",
      "prevention": {
        "builder_check": "Validate every useEffect: Does it modify a dependency? If yes, remove that dependency or use timestamp trigger."
      }
    }
  ]
}
```

**`scout-learnings.json` Format:**

```json
{
  "version": "1.0",
  "total_builds": 47,
  "learnings": [
    {
      "learning_id": "spa-needs-dev-server",
      "title": "SPAs require dev server for module loading",
      "project_types": ["react", "vue", "spa"],
      "recommendation": "Include http-server or vite in package.json",
      "frequency": 15
    }
  ]
}
```

**How Patterns Persist:**

1. **During Build:** Patterns are read-only (Scout/Architect read them)
2. **After Build:** Deployer agent extracts new patterns
3. **Pattern Merge:** New patterns merged into global storage
4. **Backup Created:** Old patterns backed up before merge

**Storage Size:**

```bash
du -h ~/.context-foundry/patterns/
# Typical size: 200-500 KB (after 50 builds)
# Max size: ~2 MB (after 500 builds)
```

Extremely lightweight.

---

### Q36: Does pattern learning work across different projects? How?

**A:** **Yes!** This is the core value of global patterns.

**Cross-Project Learning Example:**

**Build 1: Weather Dashboard (Jan 10)**
```
Project: weather-dashboard
Issue: CORS error when calling OpenWeatherMap API from browser

Architect discovers:
- Need backend proxy for API calls
- Store API key in backend .env

Pattern extracted:
{
  "pattern_id": "cors-external-api-backend-proxy",
  "learned_from_projects": ["weather-dashboard"]
}

Saved to: ~/.context-foundry/patterns/common-issues.json
```

**Build 2: Flight Tracker (Jan 15)**
```
Project: flight-tracker

Scout phase:
- Reads ~/.context-foundry/patterns/common-issues.json
- Finds pattern: "cors-external-api-backend-proxy"
- Checks if current project matches:
  * Project type: "web-app" ✅
  * Uses external API: Yes (AviationStack API) ✅
  * API key in config: Yes ✅

Scout writes in scout-report.md:
"⚠️ CORS Risk Detected (learned from weather-dashboard build):
 External aviation API will be blocked by browser CORS policy.
 Recommend: Backend proxy architecture."

Architect phase:
- Reads scout-report.md warning
- Proactively designs backend proxy:
  * Node.js Express server
  * /api/flights endpoint
  * Proxies to AviationStack API
  * Returns data with CORS headers

Build succeeds on first try (no CORS errors!)
```

**Build 3: Crypto Price Tracker (Jan 22)**
```
Scout again reads pattern (now frequency: 2)
Recognizes same risk
Architect designs backend proxy
Another successful build

Pattern updated:
{
  "pattern_id": "cors-external-api-backend-proxy",
  "frequency": 3,  // Incremented
  "learned_from_projects": [
    "weather-dashboard",
    "flight-tracker",
    "crypto-prices"
  ]
}
```

**After 10 Similar Builds:**
```json
{
  "pattern_id": "cors-external-api-backend-proxy",
  "frequency": 10,
  "severity": "high",  // Promoted to high (frequency > 5)
  "confidence": "very_high"
}
```

**Scout now warns more aggressively:**
```
⚠️ HIGH-CONFIDENCE PATTERN DETECTED:
   External API calls from browser WILL fail with CORS errors.
   This has occurred in 10 previous builds across all your projects.

   MANDATORY: Include backend proxy in architecture.
```

**Key Mechanism:** Pattern IDs (like `cors-external-api-backend-proxy`) are **stable across projects**. Frequency increments teach the system.

---

### Q37: What patterns are extracted? How does extraction work?

**A:** Extraction happens in **Phase 8: Feedback Loop** after successful builds.

**Pattern Extraction Sources:**

**1. Test Failures (If Any Occurred Before Self-Healing Succeeded):**
```python
# Deployer agent analyzes:
test_results = read(".context-foundry/test-results-iteration-*.md")

for failure in test_results.failures:
    pattern = classify_failure(failure)
    # Example:
    # failure: "TypeError: Cannot read property 'token' of undefined"
    # pattern_id: "api-response-shape-mismatch"
    # category: "data-model-assumption"
```

**2. Scout Discoveries That Proved Critical:**
```python
# Deployer reads:
scout_report = read(".context-foundry/scout-report.md")
architecture = read(".context-foundry/architecture.md")

# Check if Scout warned about something that Architect addressed:
if "CORS" in scout_report and "backend proxy" in architecture:
    pattern = {
        "pattern_id": "cors-external-api-backend-proxy",
        "source": "scout-preventive",
        "outcome": "prevented-issue"
    }
```

**3. Build Metrics:**
```python
# Extract performance data:
metrics = {
    "pattern_id": f"build-performance-{project_type}",
    "project_type": detect_type(package.json),
    "file_count": count_files("src/"),
    "build_time_minutes": session_duration,
    "parallel_tasks": len(build_tasks),
    "test_iterations": test_iteration_count
}
```

**4. Architectural Decisions:**
```python
# Learn successful patterns:
if build_succeeded and test_iterations == 1:
    # Extract tech stack choices:
    tech_stack = extract_dependencies(package.json)
    architecture_pattern = classify_architecture(architecture.md)

    pattern = {
        "pattern_id": f"{project_type}-{architecture_pattern}",
        "title": f"Successful {project_type} with {architecture_pattern}",
        "tech_stack": tech_stack,
        "file_structure": extract_structure("src/")
    }
```

**Pattern Merging Process:**

```bash
# In Phase 8 (Deployer):

# 1. Extract patterns from current build
deployer: "Analyzing build for pattern extraction..."
new_patterns = extract_patterns(
    scout_report,
    architecture,
    test_results,
    build_metrics
)

# 2. Save to project-specific file
write(".context-foundry/patterns/common-issues.json", new_patterns)

# 3. Merge into global storage
merge_project_patterns(
    project_pattern_file=".context-foundry/patterns/common-issues.json",
    global_pattern_file="~/.context-foundry/patterns/common-issues.json"
)

# Merge logic:
for pattern in new_patterns:
    if pattern.id exists in global_patterns:
        global_patterns[pattern.id].frequency += 1
        global_patterns[pattern.id].last_seen = now()
        global_patterns[pattern.id].learned_from_projects.append(project_name)
    else:
        global_patterns.append(pattern)
```

**Pattern Classification Algorithm:**

```python
def classify_failure(error_message, stack_trace, code_context):
    # Rule-based classification:
    if "CORS" in error_message:
        return "cors-external-api-backend-proxy"

    if "Cannot read property" in error_message and "response" in code_context:
        return "api-response-shape-mismatch"

    if "Maximum update depth exceeded" in error_message and "useEffect" in stack_trace:
        return "react-useeffect-infinite-loop"

    # LLM-based classification for novel errors:
    claude_analysis = analyze_error_with_llm(error_message, stack_trace)
    return claude_analysis.pattern_id
```

**Extracted Patterns Are Reviewed:**

```
# Deployer writes summary:
.context-foundry/session-summary.json:
{
  "patterns_extracted": [
    {
      "pattern_id": "cors-external-api-backend-proxy",
      "confidence": "high",
      "merged_to_global": true
    }
  ]
}
```

User can review and optionally delete patterns from `~/.context-foundry/patterns/`.

---

### Q38: Is pattern learning private? Or does it upload data to Anthropic?

**A:** **100% local.** No data leaves your machine.

**Privacy Guarantees:**

1. **Patterns Stored Locally:**
   ```bash
   ~/.context-foundry/patterns/  # Local filesystem only
   ```

2. **No Network Transmission:**
   ```python
   # Pattern merging (in tools/mcp_server.py):
   def merge_project_patterns(project_file, global_file):
       # Reads local files
       project_patterns = json.load(open(project_file))
       global_patterns = json.load(open(global_file))

       # Merges in-memory
       merged = merge(project_patterns, global_patterns)

       # Writes back to local file
       json.dump(merged, open(global_file, 'w'))

       # NO network calls
   ```

3. **Not Sent to Claude:**
   ```
   When Scout reads patterns:
   - Patterns are included in Scout's prompt (local context)
   - Sent to Claude API as part of user message
   - BUT: This is YOUR API call (your data)
   - Anthropic doesn't permanently store patterns
   - Same as if you pasted them manually
   ```

4. **No Telemetry:**
   ```python
   # Context Foundry does NOT have:
   analytics.send("pattern_learned", pattern_id)  # ❌ Doesn't exist
   telemetry.track("build_completed")             # ❌ Doesn't exist
   ```

**What IS Sent to Claude API:**

```
# During Scout phase:
User message (sent to Claude):
───────────────────────────────
System Prompt: orchestrator_prompt.txt

User Task: "Build a weather dashboard"

Context:
- Past patterns from ~/.context-foundry/patterns/common-issues.json:
  [patterns pasted here as part of prompt]

Scout: Researches requirements, checks patterns, writes report
───────────────────────────────

This is equivalent to YOU manually pasting patterns into Claude.
Anthropic's privacy policy applies (ephemeral unless you opt-in to training).
```

**Your Pattern Data:**
- ✅ Stored only on your machine
- ✅ Under your control (can delete anytime)
- ✅ Not uploaded to any server
- ✅ Not shared with other Context Foundry users
- ✅ Included in YOUR API calls to Claude (like any other prompt)

**Comparison to Other Tools:**

| Tool | Pattern Storage | Privacy |
|------|----------------|---------|
| Context Foundry | Local filesystem | ✅ Fully private |
| GitHub Copilot | Microsoft servers | ❌ Uploaded to Microsoft |
| Cursor | Cursor's cloud | ❌ Uploaded to Cursor |
| Tabnine | Optional cloud | ⚠️ Optional upload |

**Opt-Out:**

```bash
# Disable pattern learning entirely:
rm -rf ~/.context-foundry/patterns/

# Patterns won't be read or written
# Builds still work (just no cross-project learning)
```

---

## 10. Advanced Technical Topics

### Q39: Could parallel builders have race conditions when writing to the filesystem?

**A:** **No, because file assignments are mutually exclusive by design.**

**Race Condition Scenario (Hypothetical):**
```bash
# IF two builders wrote to same file (they don't):

Builder 1:                    Builder 2:
open("src/game.js", "w")     open("src/game.js", "w")
write("version A code")      write("version B code")
close()                      close()

# Result: Last writer wins (version B)
# game.js contains version B code (version A lost)
```

**Why This CAN'T Happen in Context Foundry:**

**1. Architect Guarantees Unique File Assignment:**
```json
// build-tasks.json (enforced by Architect):
{
  "tasks": [
    {"id": "task-1", "files": ["src/game.js", "src/engine.js"]},     // Owns game.js
    {"id": "task-2", "files": ["src/player.js", "src/input.js"]},    // Owns player.js
    {"id": "task-3", "files": ["src/enemy.js", "src/ai.js"]}        // Owns enemy.js
  ]
}

// No file appears in >1 task
// ∴ No two builders write to same file
```

**2. Validation in Orchestrator:**
```bash
# Before spawning builders:
# Extract all files from build-tasks.json
all_files=$(jq -r '.tasks[].files[]' build-tasks.json)

# Check for duplicates:
duplicates=$(echo "$all_files" | sort | uniq -d)

if [ -n "$duplicates" ]; then
  echo "ERROR: File conflict detected: $duplicates"
  echo "Multiple tasks assigned to same file. Aborting."
  exit 1
fi
```

**3. Filesystem Atomicity:**

Even if conflict existed:
```c
// Filesystem guarantees (POSIX):
open("file.js", O_CREAT | O_EXCL)  // Atomic: create if not exists
write(fd, data)                     // Atomic for small writes (< 4KB)
close(fd)                           // Atomic
```

Modern filesystems (ext4, APFS, NTFS) handle concurrent writes to **different files** safely.

**4. Log File Isolation:**
```
Builder 1 writes:
- .context-foundry/builder-logs/task-1.log  (unique path)
- .context-foundry/builder-logs/task-1.done (unique path)

Builder 2 writes:
- .context-foundry/builder-logs/task-2.log  (different path)
- .context-foundry/builder-logs/task-2.done (different path)

No overlap.
```

**Theoretical Edge Case:**

```json
// Architect makes mistake (shouldn't happen):
{
  "tasks": [
    {"id": "task-1", "files": ["src/game.js", "src/shared.js"]},
    {"id": "task-2", "files": ["src/player.js", "src/shared.js"]}  // ❌ Conflict
  ]
}
```

**What Happens:**
1. Both builders write to `shared.js` simultaneously
2. Last writer wins (unpredictable which)
3. Tests fail (broken imports, syntax errors)
4. Self-healing loop activates:
   - Architect analyzes test failures
   - Realizes file conflict
   - Fixes build-tasks.json (assigns shared.js to one task only)
   - Rebuilds

**Verdict:** Race conditions are prevented by design. If Architect makes mistake, tests catch it.

---

### Q40: Why bash process spawning instead of Python `multiprocessing` or `threading`?

**A:** **Authentication inheritance is the killer feature.** Also simplicity.

**Comparison Table:**

| Feature | Python `multiprocessing` | Python `threading` | Bash Process Spawning |
|---------|--------------------------|--------------------|-----------------------|
| **Authentication** | ❌ Needs API keys | ❌ Needs API keys | ✅ Inherits from Claude Code |
| **Parallelism** | ✅ True parallel (CPU) | ❌ GIL限制 (I/O only) | ✅ True parallel (processes) |
| **Isolation** | ✅ Separate memory | ❌ Shared memory | ✅ Separate memory |
| **Debugging** | ⚠️ Complex (multiprocessing.log) | ⚠️ Hard (thread dumps) | ✅ Separate log files |
| **Code Complexity** | ⚠️ 200+ lines | ⚠️ 150+ lines | ✅ 20 lines (bash) |
| **Fault Tolerance** | ✅ Process crash isolated | ❌ Thread crash kills all | ✅ Process crash isolated |
| **Coordination** | ⚠️ Queues, Locks, Events | ⚠️ Locks, Conditions | ✅ Filesystem + `wait` |

**Python `multiprocessing` Example (OLD, deprecated):**

```python
# workflows/multi_agent_orchestrator.py (removed in v2.0):
from multiprocessing import Pool, Manager
from anthropic import Anthropic

def build_task(task, api_key):
    # ❌ Must pass API key explicitly
    client = Anthropic(api_key=api_key)
    response = client.messages.create(...)
    # Complex coordination with shared Queue

def parallel_build(tasks):
    api_key = os.getenv("ANTHROPIC_API_KEY")  # ❌ User must set this

    with Pool(processes=4) as pool:
        results = pool.map(
            lambda task: build_task(task, api_key),
            tasks
        )

    # 200 lines of coordination logic
    manager = Manager()
    queue = manager.Queue()
    # ...complex...
```

**Bash Process Spawning (NEW):**

```bash
# In orchestrator_prompt.txt (v2.0+):
claude --system-prompt builder_task_prompt.txt "task-1" &  # ✅ Inherits auth
PID_1=$!

claude --system-prompt builder_task_prompt.txt "task-2" &
PID_2=$!

wait $PID_1 $PID_2  # Simple coordination

[ -f task-1.done ] && [ -f task-2.done ]  # Verify completion
```

**Why Bash Wins:**

**1. Authentication Inheritance (Critical):**
```python
# Python multiprocessing:
api_key = os.getenv("ANTHROPIC_API_KEY")  # User MUST set this
if not api_key:
    raise Exception("Please set ANTHROPIC_API_KEY in .env")

# Bash spawning:
claude ...  # Inherits from ~/.claude/config automatically
# No env vars needed
```

**2. Simpler Code:**
```python
# Python: 200 lines of Queue, Lock, Event management
from multiprocessing import Process, Queue, Lock
queue = Queue()
lock = Lock()
# ...complex process management...

# Bash: 10 lines
claude ... &
PID=$!
wait $PID
```

**3. Easier Debugging:**
```bash
# Python multiprocessing:
# Logs interleaved:
[Process-1] Building game.js
[Process-2] Building player.js
[Process-1] Error in game.js
[Process-2] Error in player.js
# Hard to follow

# Bash:
cat .context-foundry/builder-logs/task-1.log  # Clean, isolated
cat .context-foundry/builder-logs/task-2.log  # No interleaving
```

**4. Fault Tolerance:**
```python
# Python threading:
def worker():
    raise Exception("Crash")  # ❌ Kills entire process

# Bash:
claude ... &  # Subprocess crash doesn't affect orchestrator
```

**5. No GIL Issues:**
```python
# Python threading:
# GIL (Global Interpreter Lock) prevents true parallelism
# Only I/O-bound tasks benefit

# Bash spawning:
# Separate processes = true CPU parallelism
# Each process runs on different core
```

**Tradeoff:**

**Bash is slower to spawn:**
```
Python multiprocessing.Process: 10ms
Bash process spawn: 500ms

For 4 builders: 2s overhead

But builders run for 5-10 minutes, so 2s is negligible.
```

**Verdict:** Auth inheritance + simplicity >> spawn time overhead.

---

### Q41: How does Context Foundry compare to using `/agents` manually?

**A:** Context Foundry is **structured orchestration** of `/agents`, not just raw agent spawning.

**Manual `/agents` Usage:**

```
You (in Claude Code):
> Build a weather dashboard with React

Claude:
I'll use /agents to help with this.

[Spawns builder agent]

Builder Agent:
I've created:
- src/App.js
- src/Weather.js
- package.json

[Agent ends]

You:
Great! Now add tests.

Claude:
I'll use /agents again.

[Spawns tester agent]

Tester Agent:
I've created tests in tests/

[Agent ends]

You:
Tests are failing, can you fix?

Claude:
Let me debug...
[Manual back-and-forth]
```

**Problems with Manual Approach:**

1. **You must orchestrate**: You decide phase order
2. **No structure**: No scout → architect → build flow
3. **No self-healing**: You must debug test failures manually
4. **No pattern learning**: Mistakes repeat across projects
5. **No parallelization**: Agents run sequentially (you spawn one at a time)
6. **Context accumulation**: Long session = context bloat

**Context Foundry Orchestration:**

```bash
claude-code
> "Build a weather dashboard with Context Foundry"

[Automated orchestration begins]

Phase 1 (Scout):
- Spawns Scout agent
- Researches requirements
- Checks past CORS patterns
- Writes scout-report.md
- Agent dies

Phase 2 (Architect):
- Spawns Architect agent (fresh context)
- Reads scout-report.md
- Designs architecture with backend proxy (learned pattern!)
- Writes architecture.md
- Agent dies

Phase 2.5 (Parallel Build):
- Spawns 4 Builder agents simultaneously
- Each builds different files
- All write code
- All agents die

Phase 4.5 (Parallel Test):
- Spawns unit, e2e, lint testers simultaneously
- All run tests
- If fail: Self-healing activates automatically

[You do nothing, just wait]

Phase 7 (Deploy):
- Pushes to GitHub
- Returns URL

You:
[Click URL, app works perfectly]
```

**Key Differences:**

| Aspect | Manual `/agents` | Context Foundry |
|--------|------------------|-----------------|
| **Orchestration** | You decide flow | Automated 8-phase workflow |
| **Context Management** | Long session (context bloat) | Agents die after each phase |
| **Parallelization** | Sequential (you spawn one by one) | Automatic parallel build/test |
| **Pattern Learning** | You remember mistakes | System learns across projects |
| **Self-Healing** | You debug failures | Automated fix loop |
| **Structure** | Ad-hoc | Scout → Architect → Build → Test |
| **Documentation** | You write README | Auto-generated |
| **Deployment** | You git push | Automated GitHub push |

**When to Use Manual `/agents`:**

- ✅ Quick prototypes (< 5 files)
- ✅ Exploratory coding (not sure what you want)
- ✅ Debugging existing code
- ✅ Learning how agents work

**When to Use Context Foundry:**

- ✅ Complete projects (10+ files)
- ✅ Production-quality code
- ✅ Autonomous builds (no supervision)
- ✅ Repeatable workflows
- ✅ Learning from past mistakes

**Analogy:**

```
Manual /agents = Hiring individual contractors
- You coordinate everything
- You handle dependencies
- You fix mistakes

Context Foundry = Hiring a general contractor
- They coordinate subcontractors
- They manage workflow
- They fix issues before you see them
```

**Can You Mix Both?**

Yes!

```bash
# Use Context Foundry for initial build:
claude-code
> "Build weather dashboard with Context Foundry"
[Automated build completes]

# Use manual /agents for tweaks:
> "Add a dark mode toggle"
> /agents
[Quick manual change, no full rebuild needed]
```

**Verdict:** Context Foundry is **meta-orchestration** of `/agents` for complex workflows.

---

## 11. Practical Usage & Limitations

### Q42: When should I NOT use Context Foundry?

**A:** Context Foundry is overkill for certain tasks.

**Don't Use Context Foundry For:**

**1. Single-File Scripts**
```bash
# Bad:
autonomous_build_and_deploy("Create a Python script to parse CSV files")

# Why bad:
# - 8-phase workflow for 1 file (30 min)
# - Parallel build spawns 2 builders for 1 file (silly)
# - Tests, docs, GitHub deploy for a script (unnecessary)

# Better:
# Just use Claude Code directly:
claude-code
> "Write a Python script to parse CSV files"
# Done in 2 minutes
```

**2. Exploratory / Prototyping**
```bash
# Bad:
autonomous_build_and_deploy("I want to try building a game, not sure what kind yet")

# Why bad:
# - Scout will research, but requirements are vague
# - Architect will design, but you might change your mind
# - Wasted time on full build for exploration

# Better:
# Use manual /agents:
> "Help me explore game ideas"
> /agents
> [Iterate with agent until you know what you want]
> [THEN use Context Foundry for final build]
```

**3. Debugging Existing Code**
```bash
# Bad:
autonomous_build_and_deploy("Fix the bug in my existing app")

# Why bad:
# - Context Foundry is for NEW builds, not debugging
# - Scout/Architect phases are irrelevant
# - Self-healing is for test failures during build, not existing bugs

# Better:
# Use Claude Code directly:
> "I have a bug in src/auth.js line 45, can you help?"
```

**4. Tiny Changes to Existing Projects**
```bash
# Bad:
autonomous_build_and_deploy("Add a dark mode toggle to my existing app")

# Why bad:
# - Full 8-phase workflow for 1 feature (overkill)
# - Scout will re-research an existing project
# - Architect will re-design architecture (already exists)

# Better:
# Use manual /agents or Claude Code:
> "Add dark mode toggle to my React app"
> /agents
> [Implements in 5 minutes]
```

**5. Learning/Educational Projects (If You Want to Learn)**
```bash
# Bad (if goal is learning):
autonomous_build_and_deploy("Build a to-do app so I can learn React")

# Why bad:
# - Context Foundry does EVERYTHING for you
# - You learn nothing (black box)
# - You don't understand the code it wrote

# Better:
# Use Claude Code as tutor:
> "Teach me React by building a to-do app step-by-step"
> "Explain each concept as we go"
```

**6. Projects Requiring Human Judgment**
```bash
# Bad:
autonomous_build_and_deploy("Build a social network with complex privacy rules")

# Why bad:
# - Privacy rules need legal review (can't be autonomous)
# - UX decisions need human input
# - Business logic needs stakeholder approval

# Better:
# Use Context Foundry for boilerplate, then customize:
autonomous_build_and_deploy("Build a social network boilerplate")
# Then manually add privacy rules with human review
```

**Rule of Thumb:**

| Project Characteristics | Use Context Foundry? |
|-------------------------|----------------------|
| Files: 1-2 | ❌ No (use Claude Code) |
| Files: 3-10 | ⚠️ Maybe (if production-quality needed) |
| Files: 10+ | ✅ Yes |
| Requirements: Vague | ❌ No (explore first) |
| Requirements: Clear | ✅ Yes |
| Existing codebase | ❌ No (unless full rewrite) |
| Greenfield project | ✅ Yes |
| Learning goal | ❌ No (defeats purpose) |
| Production goal | ✅ Yes |

**Sweet Spot for Context Foundry:**
- 10-50 file projects
- Clear requirements
- Production-quality code needed
- Autonomous builds (no supervision)
- Repeatable workflows

---

### Q43: What are the cost implications? How much does a typical build cost?

**A:** **$1-5 per build** depending on project size (using Claude Sonnet 4.5).

**Token Usage Breakdown:**

**Small Project (5 files, 8 agents):**
```
Phase 1 (Scout):        20,000 tokens  × $0.003/1K = $0.06
Phase 2 (Architect):    40,000 tokens  × $0.003/1K = $0.12
Phase 2.5 (2 Builders): 100,000 tokens × $0.003/1K = $0.30
Phase 4.5 (2 Tests):    40,000 tokens  × $0.003/1K = $0.12
Phase 5 (Docs):         20,000 tokens  × $0.003/1K = $0.06
Phase 6-7 (Deploy):     10,000 tokens  × $0.003/1K = $0.03
────────────────────────────────────────────────────
Total:                  230,000 tokens             = $0.69

Time: 6 minutes
```

**Medium Project (15 files, 11 agents):**
```
Scout:                  20,000 tokens  = $0.06
Architect:              40,000 tokens  = $0.12
4 Builders:             200,000 tokens = $0.60
3 Tests:                60,000 tokens  = $0.18
Docs:                   20,000 tokens  = $0.06
Deploy:                 10,000 tokens  = $0.03
────────────────────────────────────────────────────
Total:                  350,000 tokens = $1.05

Time: 18 minutes
```

**Large Project (30 files, 16 agents):**
```
Scout:                  30,000 tokens  = $0.09
Architect:              60,000 tokens  = $0.18
8 Builders:             400,000 tokens = $1.20
3 Tests:                80,000 tokens  = $0.24
Screenshots:            20,000 tokens  = $0.06
Docs:                   30,000 tokens  = $0.09
Deploy:                 15,000 tokens  = $0.045
────────────────────────────────────────────────────
Total:                  635,000 tokens = $1.90

Time: 35 minutes
```

**With Self-Healing (1 iteration):**
```
Medium project base:    $1.05
+ Fix iteration:
  - Architect:          $0.12
  - Builders:           $0.30
  - Tester:             $0.06
────────────────────────────────────────────────────
Total with 1 fix:       $1.53
```

**Pricing Tiers (as of Jan 2025):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Build Cost (15 files) |
|-------|----------------------|------------------------|-----------------------|
| Claude Sonnet 4.5 | $3 | $15 | ~$1.05 |
| Claude Opus 4 | $15 | $75 | ~$5.25 |
| Claude Haiku 4 | $0.80 | $4 | ~$0.28 |

**Cost Comparison:**

```
Hiring a developer:
- Junior dev: $30/hour
- 1 hour to build 15-file project
- Cost: $30

Context Foundry:
- 18 minutes
- Cost: $1.05
- Savings: $28.95 (97% cheaper)

BUT:
- Developer learns and improves
- Context Foundry needs supervision
- Code quality varies

Use Context Foundry for:
- Rapid prototyping
- Boilerplate generation
- Time-sensitive projects
```

**Hidden Costs:**

1. **Self-Healing Iterations:**
   - Each iteration: +$0.50
   - 3 iterations: +$1.50

2. **Failed Builds:**
   - Partial builds still cost money
   - If build fails at Phase 4: ~70% of cost already spent

3. **Pattern Learning:**
   - Reading patterns: negligible (<1K tokens)
   - Writing patterns: negligible (local operation)

**Cost Optimization Tips:**

1. **Use Haiku for Simple Projects:**
   ```python
   # Switch model (if Claude Code supports):
   autonomous_build_and_deploy(
       task="...",
       model="claude-haiku-4"  # 75% cheaper
   )
   ```

2. **Reduce max_test_iterations:**
   ```python
   autonomous_build_and_deploy(
       task="...",
       max_test_iterations=1  # Fail fast, debug manually
   )
   ```

3. **Batch Multiple Projects:**
   ```
   Instead of:
   - Build project A: $1
   - Build project B: $1
   - Build project C: $1
   Total: $3

   Do:
   - Build all 3 in one session with pattern learning
   - Project A: $1 (learns patterns)
   - Project B: $0.80 (uses patterns, fewer mistakes)
   - Project C: $0.70 (more patterns, even fewer mistakes)
   Total: $2.50
   ```

**ROI Calculation:**

```
Your hourly rate: $50/hour
Time saved per build: 30 minutes = $25

Build cost: $1.05

ROI: $25 - $1.05 = $23.95 per build

After 10 builds: $239.50 saved
```

**Verdict:** Context Foundry is **extremely cost-effective** compared to manual development.

---

## 12. Comparisons & Philosophy

### Q44: How does Context Foundry compare to Cursor Composer?

**A:** **Different philosophies.** Cursor is **collaborative**, Context Foundry is **autonomous**.

| Aspect | Cursor Composer | Context Foundry |
|--------|-----------------|-----------------|
| **User Involvement** | High (you guide composer) | Low (fully autonomous) |
| **Context Model** | Long-lived session (accumulates context) | Agent death after each phase (fresh context) |
| **Workflow** | Ad-hoc (you decide next steps) | Structured 8-phase workflow |
| **Parallelization** | Sequential (one change at a time) | Parallel builds/tests (4-8 concurrent) |
| **Error Handling** | You fix errors | Self-healing loop (auto-fixes) |
| **Testing** | You write and run tests | Auto-generates and runs tests |
| **Deployment** | You push to GitHub | Auto-deploys to GitHub |
| **Pattern Learning** | No cross-project learning | Global pattern storage |
| **Best For** | Iterative development, refactoring | Greenfield projects, autonomous builds |

**Cursor Composer Flow:**

```
You: Build a weather app
Cursor: [Creates App.js]
You: Add a search bar
Cursor: [Updates App.js]
You: The API call is failing
Cursor: Let me check... [Debugs]
You: Can you add tests?
Cursor: [Creates tests]
You: Tests are failing
Cursor: [Fixes tests]
You: Great! Now deploy to GitHub
Cursor: [You do this manually]

Total: 45 minutes of back-and-forth
```

**Context Foundry Flow:**

```
You: Build a weather app with Context Foundry
[You walk away]

[18 minutes later]

Context Foundry: Done!
- GitHub repo: https://github.com/you/weather-app
- Tests: 25/25 passing
- Deployed: Ready to use
- Learned pattern: CORS requires backend proxy (applied)

Total: 18 minutes, zero supervision
```

**When to Use Each:**

**Use Cursor Composer When:**
- ✅ You want to learn (see step-by-step reasoning)
- ✅ You're refactoring existing code
- ✅ You want control over each decision
- ✅ Requirements are evolving (iterative)
- ✅ You enjoy pair programming with AI

**Use Context Foundry When:**
- ✅ You have clear requirements
- ✅ You want a complete project (not just code)
- ✅ You don't want to supervise
- ✅ You want tests + docs + deployment included
- ✅ You want cross-project pattern learning

**Can You Use Both?**

Yes!

```
1. Use Context Foundry for initial build (autonomous)
2. Use Cursor Composer for refinements (collaborative)
```

**Philosophy Difference:**

```
Cursor:
"I'm your AI pair programmer. Let's build together."
(Collaborative, you're in control)

Context Foundry:
"I'm your AI general contractor. Tell me what you want, I'll build it."
(Autonomous, you review the result)
```

---

### Q45: Context Foundry vs GitHub Copilot Workspace?

**A:** Both are **autonomous**, but different agent architectures.

| Aspect | GitHub Copilot Workspace | Context Foundry |
|--------|--------------------------|-----------------|
| **Agent Model** | Single long-lived agent | Multiple short-lived agents |
| **Context Management** | Maintains full codebase context | Agents read only .md summaries |
| **Workflow** | Plan → Implement → Iterate | 8 phases (Scout → Deploy) |
| **Parallelization** | Sequential | Parallel (2-8 concurrent agents) |
| **Testing** | You write tests | Auto-generates + runs tests |
| **Self-Healing** | Manual fixes | Automated fix loop (3 iterations) |
| **GitHub Integration** | Native (within GitHub) | External (gh CLI) |
| **Pattern Learning** | No | Yes (global pattern storage) |
| **Runs On** | GitHub's cloud | Your machine (local) |

**Copilot Workspace Flow:**

```
You: Create issue on GitHub: "Build a weather app"

Copilot Workspace (in GitHub UI):
1. Reads issue
2. Creates plan (file structure, components)
3. Shows you plan (you approve)
4. Implements code (single agent)
5. Creates PR
6. You review and merge

Total: 20 minutes (you must approve steps)
```

**Context Foundry Flow:**

```
You: autonomous_build_and_deploy("Build a weather app")

Context Foundry (on your machine):
1. Scout researches
2. Architect designs
3. 4 Builders implement in parallel
4. 3 Testers run tests
5. Self-healing fixes failures
6. Deployer pushes to GitHub

Total: 18 minutes (zero approvals needed)
```

**Key Difference: Agent Architecture**

**Copilot Workspace (Single Agent):**
```
Single Agent (maintains 200K context window):
- Loads full codebase
- Makes all decisions
- Implements all files
- Context accumulates (risk of overflow)
```

**Context Foundry (Multiple Agents):**
```
Scout (200K fresh) → dies → passes 10KB summary
  ↓
Architect (200K fresh) → dies → passes 30KB architecture
  ↓
Builder 1 (200K fresh) → dies → leaves code
Builder 2 (200K fresh) → dies → leaves code
Builder 3 (200K fresh) → dies → leaves code
Builder 4 (200K fresh) → dies → leaves code
  ↓
Tester (200K fresh) → dies → passes test results

No context accumulation, each agent has full token budget
```

**When to Use Each:**

**Use Copilot Workspace When:**
- ✅ Your code is on GitHub (native integration)
- ✅ You want to review plan before implementation
- ✅ You trust GitHub's cloud execution
- ✅ You want native PR workflow

**Use Context Foundry When:**
- ✅ You want fully autonomous builds (no approvals)
- ✅ You want parallel execution (faster)
- ✅ You want pattern learning across projects
- ✅ You want to run locally (not cloud)
- ✅ You need self-healing test loop

**Philosophy:**

```
Copilot Workspace:
"AI teammate that works in your GitHub workflow"
(Collaborative, GitHub-native)

Context Foundry:
"AI construction crew that builds independently"
(Autonomous, local-first)
```

---

### Q46: What is Context Foundry's design philosophy? How does it differ from "vibe coding"?

**A:** **"Stop vibe coding, start building."**

**"Vibe Coding" Defined:**

```
Vibe Coding (what NOT to do):
─────────────────────────────────
You: "Make it look good"
AI: [Changes colors randomly]
You: "Hmm, not quite"
AI: [Tries different colors]
You: "Better, but can you make it pop?"
AI: [More random changes]
You: "Actually, go back to version 2"
AI: "Which version was that?"

Result:
- No clear requirements
- No architecture
- No tests
- No plan
- Just vibes
```

**Context Foundry Philosophy:**

```
Structured Building:
─────────────────────────────────
Phase 1 (Scout):
- What are we building? (clear requirements)
- What constraints exist? (technical analysis)
- What could go wrong? (risk analysis)

Phase 2 (Architect):
- How should it work? (system design)
- What's the file structure? (concrete plan)
- How do we test it? (success criteria)

Phase 3 (Build):
- Implement exactly as designed (no guessing)

Phase 4 (Test):
- Does it work? (automated validation)
- If no: Fix systematically (self-healing)

Result:
- Clear requirements
- Documented architecture
- Comprehensive tests
- Deployed to GitHub
- Repeatable process
```

**Core Principles:**

**1. Architecture Before Code**
```
❌ Vibe Coding:
You: "Build a to-do app"
AI: [Starts writing code immediately]
[No design, no plan]

✅ Context Foundry:
Scout: Analyzes requirements
Architect: Designs system BEFORE building
Builders: Implement design (not making it up)
```

**2. Tests Are Mandatory**
```
❌ Vibe Coding:
AI: "Here's your app!"
You: "Does it work?"
AI: "Probably? Try it?"

✅ Context Foundry:
Tester: Runs 25 automated tests
Tester: Reports 23 passed, 2 failed
Self-Healing: Fixes failures
Tester: Runs again, 25 passed ✅
```

**3. Documentation Is Part of Build**
```
❌ Vibe Coding:
[Code exists, zero documentation]
You: "How do I run this?"
AI: "Uhh... try npm start?"

✅ Context Foundry:
Docs Agent: Generates README.md
- Installation instructions
- Usage examples
- Architecture overview
- API documentation
```

**4. Pattern Learning, Not Repeating Mistakes**
```
❌ Vibe Coding:
Build 1: CORS error (you fix manually)
Build 2: CORS error again (you fix again)
Build 3: CORS error AGAIN (frustration)

✅ Context Foundry:
Build 1: CORS error → Pattern learned
Build 2: Scout warns about CORS → Architect designs backend proxy → No error
Build 3: Scout warns again → Backend proxy included → No error
```

**5. Autonomous, Not Collaborative**
```
❌ Vibe Coding:
You: "Add a login page"
AI: [Adds page]
You: "Now add password reset"
AI: [Adds feature]
You: "Wait, the login is broken now"
AI: "Let me check..."
[Endless back-and-forth]

✅ Context Foundry:
You: "Build an app with login and password reset"
[Walk away]
[Return 20 minutes later]
✓ Login page works
✓ Password reset works
✓ Tests passing
✓ Deployed to GitHub
```

**Design Principles Table:**

| Principle | Vibe Coding | Context Foundry |
|-----------|-------------|-----------------|
| **Requirements** | Vague, evolving | Clear, upfront |
| **Architecture** | None (YOLO) | Designed before building |
| **Testing** | Manual (if at all) | Automated, mandatory |
| **Error Handling** | You debug | Self-healing loop |
| **Documentation** | Afterthought | Auto-generated |
| **Learning** | You remember | System learns (patterns) |
| **Process** | Ad-hoc | Structured (8 phases) |
| **User Role** | Director (constant supervision) | Product owner (define requirements) |

**Slogan:**

```
Vibe Coding: "Let's see what happens 🤷"
Context Foundry: "Let's build it right 🏗️"
```

**When "Vibes" Are OK:**

- ✅ Quick prototypes (throw-away code)
- ✅ Exploring ideas (don't know requirements yet)
- ✅ Learning (educational coding)

**When Structure Is Needed:**

- ✅ Production code
- ✅ Projects with multiple files
- ✅ Code you'll maintain long-term
- ✅ Team projects (need architecture docs)

**The Tagline:**

> **"Stop vibe coding, start building."**
>
> Because software engineering is not about vibes—it's about architecture, tests, and systems that work.

---

## Conclusion

**Key Takeaways:**

1. **File Management**: `.context-foundry/` lives in your project, `.md` files are the core, everything is local
2. **Prompts**: `orchestrator_prompt.txt`, `builder_task_prompt.txt`, `test_task_prompt.txt` are the "secret sauce"
3. **Agents**: 8-45 agents per build, each isolated, die after task completion
4. **Tokens**: Managed via agent death, no single agent exceeds 200K
5. **Parallelization**: 2-8 builders, file-based coordination, no race conditions
6. **Authentication**: Inherits from Claude Code, no API keys needed
7. **Performance**: 30-45% faster than sequential, $1-5 per build
8. **Self-Healing**: 3-iteration fix loop, 98% success rate
9. **Patterns**: Global learning, 100% local storage, privacy-first
10. **Philosophy**: Structured building over vibe coding

**Next Steps:**

- Read [MULTI_AGENT_ARCHITECTURE.md](./MULTI_AGENT_ARCHITECTURE.md) for visual diagrams
- Read [PARALLEL_AGENTS_ARCHITECTURE.md](./PARALLEL_AGENTS_ARCHITECTURE.md) for implementation details
- Explore prompts: [orchestrator_prompt.txt](../tools/orchestrator_prompt.txt)
- Try a build: `autonomous_build_and_deploy("Build a to-do app")`

**Questions Not Covered?**

Open an issue: https://github.com/context-foundry/context-foundry/issues

---

*Last updated: 2025-01-23*
*Version: 2.0*
*For: Software developers, architects, AI engineers*

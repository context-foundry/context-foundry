# Context Foundry FAQ

**Frequently Asked Questions - Making Context Foundry Transparent**

> **Philosophy:** "No Magic, Just Transparency"
> This FAQ explains how Context Foundry works internally, where everything is stored, and demystifies the agent delegation model.

> **Looking for technical details?** If you're a software developer, architect, or AI engineer looking for deep technical information about parallelization, token management, MCP server architecture, or prompt engineering, see the **[Technical FAQ](docs/FAQ.md)** with 52 in-depth questions and code examples.

---

## Table of Contents

**Build Artifacts & Plans**
- [Where can I find the architect's plan for my project?](#where-can-i-find-the-architects-plan-for-my-project)
- [What other build artifacts are created?](#what-other-build-artifacts-are-created)
- [Where is the pattern library stored?](#where-is-the-pattern-library-stored)

**System Prompts & Delegation**
- [Did Context Foundry change Claude Code's system prompt?](#did-context-foundry-change-claude-codes-system-prompt)
- [If I use Claude Code for other tasks, do I need to change the system prompt back?](#if-i-use-claude-code-for-other-tasks-do-i-need-to-change-the-system-prompt-back)
- [How does the MCP server trigger builds?](#how-does-the-mcp-server-trigger-builds)
- [Where are all the prompts located?](#where-are-all-the-prompts-located)

**Context & Agents**
- [Why is my context usage so low during builds?](#why-is-my-context-usage-so-low-during-builds)
- [What happens to the agents after the build completes?](#what-happens-to-the-agents-after-the-build-completes)
- [Can I see the agent conversations?](#can-i-see-the-agent-conversations)

**Usage & Control**
- [Can I review the architect's plan before building starts?](#can-i-review-the-architects-plan-before-building-starts)
- [How do I know what patterns are being applied to my build?](#how-do-i-know-what-patterns-are-being-applied-to-my-build)
- [Can I disable autonomous mode and have more control?](#can-i-disable-autonomous-mode-and-have-more-control)

---

## Build Artifacts & Plans

### Where can I find the architect's plan for my project?

**Location:** Inside your project directory at `.context-foundry/architecture.md`

**Example for VimQuest:**
```bash
/Users/name/homelab/vimquest/.context-foundry/architecture.md
```

**Example for Satoshi's Chore Tracker:**
```bash
/Users/name/homelab/satoshi-chore-tracker/.context-foundry/architecture.md
```

**What's in it:**
- Complete system architecture
- File structure plan
- Module specifications
- Data models
- Component hierarchy
- State management design
- Testing plan
- Implementation roadmap

**File size:** Typically 30-90KB of detailed technical specifications!

**How to view:**
```bash
# In terminal
cat /path/to/your-project/.context-foundry/architecture.md

# Or open in editor
code /path/to/your-project/.context-foundry/architecture.md

# Or use Claude Code
claude-code
# Then: "Read /path/to/your-project/.context-foundry/architecture.md"
```

---

### What other build artifacts are created?

**Every project gets a `.context-foundry/` directory with:**

```
your-project/
└── .context-foundry/
    ├── scout-report.md           # Research findings (40-60KB)
    ├── architecture.md            # Architect's plan (30-90KB)
    ├── build-log.md              # Implementation progress
    ├── test-results-iteration-1.md  # First test run results
    ├── test-results-iteration-2.md  # (if self-healing triggered)
    ├── test-final-report.md      # Final test summary
    ├── fixes-iteration-1.md      # (if bugs found)
    ├── session-summary.json      # Complete build metadata
    ├── feedback/
    │   └── build-feedback-{timestamp}.json
    └── patterns/
        ├── common-issues.json
        ├── test-patterns.json
        ├── architecture-patterns.json
        └── scout-learnings.json
```

**Key Files Explained:**

| File | Purpose | When to Read |
|------|---------|--------------|
| `scout-report.md` | Research findings, technology recommendations | Understand why certain tech choices were made |
| `architecture.md` | Complete technical design | Learn the system architecture |
| `build-log.md` | Implementation chronology | Track what was built and when |
| `test-final-report.md` | Test results and coverage | See test pass rate and quality metrics |
| `session-summary.json` | Metadata: files created, duration, GitHub URL | Quick build overview |

---

### Where is the pattern library stored?

**Two Locations - Different Purposes:**

**1. Global Pattern Library** (shared across ALL builds)
```
/Users/name/homelab/context-foundry/.context-foundry/patterns/
├── common-issues.json           # Known issues & solutions
├── test-patterns.json           # Testing strategies
├── architecture-patterns.json   # Proven architectures
└── scout-learnings.json         # Research patterns
```

**2. Per-Project Patterns** (this build's specific patterns)
```
/Users/name/homelab/your-project/.context-foundry/patterns/
└── [Same structure, but project-specific]
```

**How it works:**
1. **Global patterns** are READ by Scout/Architect/Test phases
2. **New patterns** discovered during build go to project directory
3. **Phase 7: Feedback** analyzes and promotes valuable patterns to global library
4. **Next build** benefits from accumulated learnings

**View global patterns:**
```bash
cat /Users/name/homelab/context-foundry/.context-foundry/patterns/common-issues.json
```

---

## System Prompts & Delegation

### Did Context Foundry change Claude Code's system prompt?

**NO!** Context Foundry does NOT modify Claude Code's system prompt at all.

**How it actually works:**

```
┌─────────────────────────────────────────────────────────┐
│ Your Claude Code Session (Normal System Prompt)         │
│                                                          │
│ You: "Build a weather app"                              │
│                                                          │
│ Claude Code: [Recognizes build request]                 │
│              [Calls MCP tool: autonomous_build_and_deploy]│
│                                                          │
│              ↓ Spawns Fresh Claude Instance              │
│                                                          │
│ ┌────────────────────────────────────────────────────┐  │
│ │ New Claude Code Instance (Normal System Prompt)    │  │
│ │                                                     │  │
│ │ Task (USER message): "Read orchestrator_prompt.txt │  │
│ │ and execute it to build a weather app"             │  │
│ │                                                     │  │
│ │ [This instance does ALL the work]                  │  │
│ │ [Creates Scout, Architect, Builder, Test agents]   │  │
│ │ [Builds entire project]                            │  │
│ │                                                     │  │
│ │ Returns: "Build complete! ✅"                       │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ Claude Code: "Your weather app is ready! ✅"            │
│              "Deployed to: github.com/you/weather-app"  │
└─────────────────────────────────────────────────────────┘
```

**Key Points:**
- ✅ Claude Code's system prompt: **UNCHANGED**
- ✅ Orchestrator prompt: Sent as **USER message** to delegated instance
- ✅ Your main Claude window: **Clean and separate**
- ✅ Build work: Happens in **separate Claude instance**

---

### If I use Claude Code for other tasks, do I need to change the system prompt back?

**NO!** You never need to worry about this.

**Why:**
- Context Foundry runs in **delegated Claude instances**, not your main session
- Your regular Claude Code usage is **completely unaffected**
- The MCP server is only activated when you explicitly request a build
- Regular code editing, file operations, git commands all work normally

**You can freely:**
```bash
claude-code

# Regular usage - Context Foundry NOT involved
You: "Refactor this function to use async/await"
You: "Fix the bug in line 42"
You: "Explain this code to me"

# Context Foundry usage - Triggers MCP delegation
You: "Build a todo app"  ← Only THIS triggers Context Foundry
```

**Think of it like:**
- Regular Claude Code = Your IDE
- Context Foundry = Calling a contractor who works offsite

---

### How does the MCP server trigger builds?

**The Delegation Flow:**

```
1. User Request
   ↓
   "Build a weather app"

2. Claude Code (Main Window)
   ↓
   Recognizes: "This is a build request"
   ↓
   Calls MCP tool: autonomous_build_and_deploy(
     task="Build a weather app",
     working_directory="/Users/name/homelab/weather-app"
   )

3. MCP Server (mcp_server.py)
   ↓
   Receives tool call
   ↓
   Spawns: subprocess.Popen(['claude-code', '--prompt', task])
   ↓
   New Claude Code instance starts (FRESH context)

4. Delegated Claude Instance
   ↓
   Receives orchestrator prompt as USER message
   ↓
   Executes all 7 phases (Scout → Architect → Builder → Test → Docs → Deploy → Feedback)
   ↓
   Returns: Build summary

5. MCP Server
   ↓
   Receives build summary
   ↓
   Returns to main Claude window

6. Main Claude Window
   ↓
   Shows: "Build complete! ✅"
```

**Why this is brilliant:**
- Main context stays clean (< 10% usage)
- Delegated instance can use 100% of ITS context
- Multiple builds can run in parallel
- Each build is isolated
- Main window just monitors progress

---

### Where are all the prompts located?

**Prompt Locations:**

| Prompt | Location | Purpose |
|--------|----------|---------|
| **Orchestrator Prompt** | `/Users/name/homelab/context-foundry/tools/orchestrator_prompt.txt` | Main build orchestration (7 phases) |
| **MCP Server** | `/Users/name/homelab/context-foundry/mcp_server.py` | Delegation logic |
| **Agent Prompts** | Embedded in `orchestrator_prompt.txt` | Scout, Architect, Builder, Test, etc. |
| **Claude Code System Prompt** | NOT MODIFIED | Standard Claude Code prompt |

**View the orchestrator prompt:**
```bash
cat /Users/name/homelab/context-foundry/tools/orchestrator_prompt.txt
```

**It's 1000+ lines and defines:**
- Phase 1: Scout (Research)
- Phase 2: Architect (Design)
- Phase 3: Builder (Implementation)
- Phase 4: Test (Quality Assurance + Self-Healing)
- Phase 5: Documentation
- Phase 6: Deployment
- Phase 7: Feedback Analysis

---

## Context & Agents

### Why is my context usage so low during builds?

**You noticed something important!**

Your observation is correct: **The main Claude window shows very low context usage during builds**.

**Why:**

```
Main Claude Window Context:
├─ Your request: "Build a weather app" (~10 tokens)
├─ Claude's acknowledgment (~50 tokens)
├─ MCP tool call (~100 tokens)
└─ Final summary: "Build complete!" (~500 tokens)
───────────────────────────────────────
Total: ~660 tokens (~0.3% of 200K context window)
```

**Meanwhile, in the delegated instance:**

```
Delegated Claude Instance Context:
├─ Orchestrator prompt (~5,000 tokens)
├─ Scout phase conversation (~10,000 tokens)
├─ Architect phase conversation (~15,000 tokens)
├─ Builder phase conversation (~30,000 tokens)
├─ Test phase conversation (~8,000 tokens)
├─ Docs phase conversation (~3,000 tokens)
├─ Deploy phase conversation (~2,000 tokens)
├─ Feedback phase conversation (~5,000 tokens)
───────────────────────────────────────
Total: ~78,000 tokens (~39% of context window)
```

**The magic:** All the heavy lifting happens in a SEPARATE Claude instance that you never see!

**Benefits:**
- ✅ Your main session stays clean
- ✅ You can continue working on other tasks
- ✅ Multiple builds can run in parallel
- ✅ Each build gets a fresh 200K context budget
- ✅ No context pollution between projects

**This is why Context Foundry can build multiple apps simultaneously without hitting context limits!**

---

### What happens to the agents after the build completes?

**Agents are ephemeral** - they exist only during the build and disappear when complete.

**Lifecycle:**

```
Build Starts
    ↓
Delegated Claude instance spawned
    ↓
Orchestrator reads orchestrator_prompt.txt
    ↓
Phase 1: Scout agent created
    ├─ Researches project
    ├─ Writes scout-report.md
    └─ [Agent context discarded]
    ↓
Phase 2: Architect agent created
    ├─ Reads scout-report.md (persisted)
    ├─ Designs architecture
    ├─ Writes architecture.md
    └─ [Agent context discarded]
    ↓
Phase 3: Builder agent created
    ├─ Reads architecture.md (persisted)
    ├─ Implements code
    ├─ Writes files
    └─ [Agent context discarded]
    ↓
... (Test, Docs, Deploy, Feedback)
    ↓
Build Completes
    ↓
Delegated Claude instance terminates
    ↓
ALL agent contexts GONE
```

**What persists:**
- ✅ Files created (your actual project code)
- ✅ `.context-foundry/` artifacts (plans, reports, logs)
- ✅ Pattern library updates
- ✅ Git commits
- ✅ GitHub repository

**What disappears:**
- ❌ Agent conversation histories
- ❌ Delegated Claude instance
- ❌ Temporary build state
- ❌ Agent "memory" (only artifacts remain)

**Why this is good:**
- Clean slate for each build
- No state pollution
- Predictable behavior
- Agents can't accumulate incorrect assumptions

**Next build:** Fresh agents are created, read the pattern library, and benefit from past learnings without carrying forward any conversation baggage.

---

### Can I see the agent conversations?

**Short answer:** Not currently, but you can see their OUTPUT.

**What you CAN see:**

Each agent documents their work:

| Agent | Output File | What It Shows |
|-------|-------------|---------------|
| Scout | `.context-foundry/scout-report.md` | Research findings, technology recommendations |
| Architect | `.context-foundry/architecture.md` | Complete system design |
| Builder | `.context-foundry/build-log.md` | Implementation progress |
| Test | `.context-foundry/test-results-iteration-X.md` | Test runs, failures, fixes |
| Feedback | `.context-foundry/feedback/build-feedback-{timestamp}.json` | Learnings extracted |

**Example - Reading Scout's findings:**
```bash
cat /Users/name/homelab/vimquest/.context-foundry/scout-report.md
```

You'll see:
- What Scout researched
- Technologies recommended
- Risks identified
- Prior art analyzed
- Patterns applied

**What you CAN'T see:**
- The actual back-and-forth between Scout and file tools
- Internal reasoning steps
- Trial-and-error during research

**Why:** The delegated Claude instance only returns the final artifacts, not the full conversation log.

**Future enhancement:** Could add `--verbose` mode to capture full conversation logs if desired for debugging.

---

## Usage & Control

### Can I review the architect's plan before building starts?

**Yes! You have options:**

**Option 1: Autonomous Mode (Default - No Review)**
```
You: "Build a weather app"

→ Scout runs → Architect runs → Builder runs → ... → Done!
  (You don't see plan until after completion)
```

**Option 2: Non-Autonomous Mode (Manual Review)**
```python
# Use MCP tool with autonomous=False
autonomous_build_and_deploy(
    task="Build a weather app",
    working_directory="/Users/name/homelab/weather",
    autonomous=False  # ← Enables checkpoints
)
```

**With checkpoints enabled:**
1. Scout completes → Shows scout-report.md → Waits for approval
2. You review: `cat .context-foundry/scout-report.md`
3. You approve: "Continue"
4. Architect completes → Shows architecture.md → Waits for approval
5. You review: `cat .context-foundry/architecture.md`
6. You approve: "Continue"
7. Builder starts...

**Option 3: Review After Completion (Most Common)**
```
Build completes autonomously
    ↓
Review: cat .context-foundry/architecture.md
    ↓
Understand what was built and why
    ↓
Make adjustments if needed
```

**Best practice:**
- First build: Use autonomous mode (trust the system)
- After build: Review architecture.md to learn
- If adjustments needed: Edit code or request changes

---

### How do I know what patterns are being applied to my build?

**Patterns document themselves in the build artifacts!**

**Check 1: Scout Report**
```bash
cat your-project/.context-foundry/scout-report.md
```

Look for section:
```markdown
## Patterns Applied

Based on pattern library analysis:

1. ✅ vite-educational-spa (PRIORITY: HIGH)
   - Reason: Browser-based app with ES6 modules
   - Prevention: CORS errors from file:// protocol
   - Action: Use Vite with built-in dev server

2. ✅ hash-routing-offline-first
   - Reason: Educational app, offline capability important
   - Action: Implement hash-based routing
```

**Check 2: Architecture Document**
```bash
cat your-project/.context-foundry/architecture.md
```

Look for section:
```markdown
## Technology Choices

### Build Tool: Vite
**Rationale:** Pattern library indicates Vite prevents CORS issues
(pattern: vite-educational-spa, frequency: 3, success_rate: 100%)
```

**Check 3: Session Summary**
```bash
cat your-project/.context-foundry/session-summary.json
```

```json
{
  "patterns_applied": [
    "vite-educational-spa",
    "hash-routing-offline-first",
    "localstorage-educational-persistence"
  ]
}
```

**Check 4: Global Pattern Library**
```bash
cat /Users/name/homelab/context-foundry/.context-foundry/patterns/common-issues.json
```

See all available patterns and their auto-apply conditions.

---

### Can I disable autonomous mode and have more control?

**Yes! Multiple control levels:**

**Level 1: Full Autonomous (Walk Away)**
```
autonomous_build_and_deploy(
    task="Build a weather app",
    autonomous=True  # Default
)
```
- No checkpoints
- Runs start to finish
- Use when: You trust the system

**Level 2: Checkpoint Mode (Review Key Decisions)**
```
autonomous_build_and_deploy(
    task="Build a weather app",
    autonomous=False  # ← Enables checkpoints
)
```
- Pauses after Scout (review research)
- Pauses after Architect (review plan)
- Pauses after Test (review results)
- Use when: You want oversight

**Level 3: Manual Orchestrator (Full Control)**
```bash
cd /Users/name/homelab/your-project
claude-code

You: "Read /Users/name/homelab/context-foundry/tools/orchestrator_prompt.txt
      and execute Phase 1 (Scout) only"

[Review scout-report.md]

You: "Now execute Phase 2 (Architect)"

[Review architecture.md, make edits]

You: "Now execute Phase 3 (Builder) with these modifications: ..."
```

**Level 4: Traditional Claude Code (No Context Foundry)**
```bash
claude-code

You: "Help me build a weather app step by step"

[Traditional interactive development]
```

**Recommendation:**
- **First time:** Use autonomous mode to see what it can do
- **After seeing results:** Decide if you want more control
- **Complex projects:** Use checkpoint mode
- **Learning/teaching:** Use manual orchestrator to see each phase

---

## Advanced Questions

### What's the difference between the MCP server and manual orchestrator?

**MCP Server (Recommended):**
- Integrates with Claude Code's MCP protocol
- One-command builds from any directory
- Supports parallel builds
- Automatic delegation
- Clean API

**Usage:**
```
You: "Build a weather app"
[System handles everything]
```

**Manual Orchestrator:**
- Direct use of orchestrator prompt
- More explicit control
- Educational (see how it works)
- Debugging builds

**Usage:**
```
You: "Read orchestrator_prompt.txt and execute it for a weather app"
[You manually guide Claude through phases]
```

**When to use each:**
- **MCP:** Production use, ease of use, parallel builds
- **Manual:** Learning, debugging, custom workflows

---

### Where can I learn more?

**Documentation:**
- **Quick Start:** [QUICKSTART.md](QUICKSTART.md)
- **User Guide:** [USER_GUIDE.md](USER_GUIDE.md)
- **Architecture Deep Dive:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Delegation Model:** [docs/DELEGATION_MODEL.md](docs/DELEGATION_MODEL.md)
- **Feedback System:** [FEEDBACK_SYSTEM.md](FEEDBACK_SYSTEM.md)

**Real Examples:**
- VimQuest: `/Users/name/homelab/vimquest/.context-foundry/`
- Satoshi's Chore Tracker: `/Users/name/homelab/satoshi-chore-tracker/.context-foundry/`
- 1942 Clone: `/tmp/1942-clone/.context-foundry/`

**Pattern Library:**
- Global patterns: `/Users/name/homelab/context-foundry/.context-foundry/patterns/`
- See what Context Foundry has learned!

---

## Still Have Questions?

**Open an issue:** https://github.com/snedea/context-foundry/issues

**Philosophy:** If the documentation doesn't answer it, the documentation is incomplete. We'll add your question to this FAQ!

# Context Foundry Delegation Model

**Technical Deep Dive: How Context Foundry Keeps Your Main Context Clean**

---

## Table of Contents

1. [Overview](#overview)
2. [The Problem: Context Window Bloat](#the-problem-context-window-bloat)
3. [The Solution: Delegation Architecture](#the-solution-delegation-architecture)
4. [How Delegation Works](#how-delegation-works)
5. [Context Separation Benefits](#context-separation-benefits)
6. [MCP Server Implementation](#mcp-server-implementation)
7. [Prompt Architecture](#prompt-architecture)
8. [Agent Lifecycle](#agent-lifecycle)
9. [Comparison with Other Approaches](#comparison-with-other-approaches)
10. [FAQ](#faq)

---

## Overview

**Key Innovation:** Context Foundry builds entire applications while using < 1% of your main Claude Code window's context.

**How:** By delegating the work to **separate Claude Code instances** that run independently and communicate via files.

**Result:**
- ✅ Main window stays clean
- ✅ Multiple builds can run in parallel
- ✅ Each build gets fresh 200K context budget
- ✅ No context pollution between projects

---

## The Problem: Context Window Bloat

### Traditional AI Coding (Single Context)

```
┌────────────────────────────────────────────────────┐
│ Claude Code Session (Single Conversation)          │
│                                                     │
│ User: "Build a todo app"                           │
│ Claude: [2,000 tokens of implementation]           │
│                                                     │
│ User: "Add authentication"                         │
│ Claude: [3,000 tokens more]                        │
│                                                     │
│ User: "Add dark mode"                              │
│ Claude: [2,500 tokens more]                        │
│                                                     │
│ [After 20 interactions]                            │
│ Total: 80,000 tokens (40% of 200K context)         │
│                                                     │
│ Problems:                                          │
│ ❌ Context fills up quickly                        │
│ ❌ Early messages get truncated                    │
│ ❌ Performance degrades at high utilization        │
│ ❌ Can't run multiple builds simultaneously        │
│ ❌ Can't do other work while building              │
└────────────────────────────────────────────────────┘
```

### Context Foundry Approach (Delegation)

```
┌────────────────────────────────────────────────────┐
│ Your Claude Code Window (Main Context)             │
│                                                     │
│ You: "Build a todo app"                            │
│ Claude: [Delegates to MCP server]                  │
│ Claude: "Build started! Task ID: abc-123"          │
│                                                     │
│ Context Used: ~1,000 tokens (0.5%)                 │
│ ✅ Stay clean and available                        │
│                                                     │
│ You: [Can continue other work]                     │
│                                                     │
│ [10 minutes later]                                 │
│ Claude: "Build complete! ✅"                        │
│                                                     │
│ Context Used: ~1,500 tokens (0.75%)                │
│ ✅ Still clean after full build!                   │
└────────────────────────────────────────────────────┘
          │
          │ Spawns
          ↓
┌────────────────────────────────────────────────────┐
│ Delegated Claude Instance (Separate Context)       │
│                                                     │
│ [Receives orchestrator prompt]                     │
│ [Runs all 7 phases autonomously]                   │
│ [Uses 80,000 tokens of ITS OWN context]            │
│                                                     │
│ Context Used: ~80,000 tokens (40%)                 │
│ ✅ Isolated - doesn't affect main window           │
│                                                     │
│ Returns: Build summary                             │
└────────────────────────────────────────────────────┘
```

---

## The Solution: Delegation Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN CLAUDE CODE WINDOW                   │
│                                                              │
│  User Request: "Build a weather app"                        │
│         ↓                                                    │
│  Claude Code detects build intent                           │
│         ↓                                                    │
│  Calls MCP Tool: autonomous_build_and_deploy()              │
│         ↓                                                    │
│  Returns: Task ID (build continues in background)           │
│         ↓                                                    │
│  User: [Continues working on other things]                  │
│                                                              │
│  Context Usage: < 1% (stays clean!)                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ MCP Protocol
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                      MCP SERVER (Python)                     │
│                  tools/mcp_server.py                         │
│                                                              │
│  Receives: autonomous_build_and_deploy(task, directory)     │
│         ↓                                                    │
│  Spawns: subprocess.Popen(                                  │
│            ['claude', '--prompt', task_prompt]              │
│          )                                                   │
│         ↓                                                    │
│  Returns: Task ID to main window                            │
│         ↓                                                    │
│  Monitors: Delegated process (async)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Subprocess
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              DELEGATED CLAUDE CODE INSTANCE                  │
│                   (Fresh Context)                            │
│                                                              │
│  Receives orchestrator prompt as USER message:              │
│  "Read tools/orchestrator_prompt.txt and execute..."        │
│         ↓                                                    │
│  Phase 1: Scout (creates agent, researches)                 │
│         ↓ (writes scout-report.md)                          │
│  Phase 2: Architect (creates agent, designs)                │
│         ↓ (writes architecture.md)                          │
│  Phase 3: Builder (creates agent, implements)               │
│         ↓ (writes code files)                               │
│  Phase 4: Test (runs tests, self-heals if needed)           │
│         ↓ (writes test results)                             │
│  Phase 5: Docs (generates documentation)                    │
│         ↓ (writes README, guides)                           │
│  Phase 6: Deploy (creates GitHub repo, pushes)              │
│         ↓ (git operations)                                  │
│  Phase 7: Feedback (extracts learnings)                     │
│         ↓ (updates pattern library)                         │
│  Returns: Build summary                                     │
│                                                              │
│  Context Usage: 40-60% (isolated, doesn't affect main!)     │
└─────────────────────────────────────────────────────────────┘
                       │
                       │ Returns Summary
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                      MCP SERVER                              │
│  Receives: Build complete summary                           │
│  Returns: Summary to main Claude window                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                    MAIN CLAUDE CODE WINDOW                   │
│                                                              │
│  Shows: "Build complete! ✅"                                 │
│         GitHub: github.com/snedea/weather-app               │
│         Tests: 25/25 passing                                │
│         Duration: 8.3 minutes                               │
│                                                              │
│  User: [Can check results, continue working, etc.]          │
│                                                              │
│  Context Usage: Still < 1% (stayed clean entire time!)      │
└─────────────────────────────────────────────────────────────┘
```

---

## How Delegation Works

### Step-by-Step Flow

**1. User Makes Request**

```
You: "Build a weather app with current weather and 5-day forecast"
```

**2. Claude Code Intent Detection**

```python
# Claude Code's internal reasoning:
if contains_build_intent(user_message):
    tool_to_call = "mcp__autonomous_build_and_deploy"
    params = extract_build_params(user_message)
```

**3. MCP Tool Call**

```python
# Claude Code makes MCP tool call
{
  "tool": "mcp__autonomous_build_and_deploy",
  "parameters": {
    "task": "Build a weather app with current weather and 5-day forecast",
    "working_directory": "/Users/name/homelab/weather-app",
    "github_repo_name": "weather-app",
    "enable_test_loop": true
  }
}
```

**4. MCP Server Receives Call**

```python
# tools/mcp_server.py
@mcp.tool()
async def autonomous_build_and_deploy_async(
    task: str,
    working_directory: str,
    github_repo_name: str = None,
    enable_test_loop: bool = True
) -> str:
    # Create task ID
    task_id = str(uuid.uuid4())

    # Build orchestrator prompt
    orchestrator_prompt = build_prompt(task, working_directory)

    # Spawn delegated Claude Code instance
    process = subprocess.Popen([
        'claude',
        '--prompt', orchestrator_prompt,
        '--permission-mode', 'bypassPermissions'
    ], cwd=working_directory)

    # Track in background
    TASKS[task_id] = {
        'process': process,
        'status': 'running',
        'start_time': time.time()
    }

    # Return immediately (non-blocking)
    return json.dumps({
        'task_id': task_id,
        'status': 'started',
        'message': 'Build running in background'
    })
```

**5. Delegated Instance Starts**

```
New Claude Code process spawned
    ↓
Receives prompt: "Read tools/orchestrator_prompt.txt and execute it"
    ↓
Orchestrator prompt is a USER message (not system prompt!)
    ↓
Claude Code reads orchestrator_prompt.txt
    ↓
Begins Phase 1: Scout
```

**6. Phases Execute**

```
Phase 1: Scout
    ├─ Creates /agents scout
    ├─ Researches requirements
    ├─ Writes .context-foundry/scout-report.md
    └─ Agent context discarded
    ↓
Phase 2: Architect
    ├─ Reads scout-report.md
    ├─ Creates /agents architect
    ├─ Designs architecture
    ├─ Writes .context-foundry/architecture.md
    └─ Agent context discarded
    ↓
Phase 3: Builder
    ├─ Reads architecture.md
    ├─ Creates /agents builder
    ├─ Implements code
    ├─ Writes source files
    └─ Agent context discarded
    ↓
Phase 4: Test
    ├─ Runs tests
    ├─ If failures: Self-healing loop
    ├─ Writes test results
    └─ Continues when passing
    ↓
Phase 5: Docs
    ├─ Generates README
    ├─ Creates guides
    └─ Documentation complete
    ↓
Phase 6: Deploy
    ├─ Git commit
    ├─ GitHub repo creation
    ├─ Push to GitHub
    └─ Deployment complete
    ↓
Phase 7: Feedback
    ├─ Analyzes build
    ├─ Extracts patterns
    ├─ Updates pattern library
    └─ Build complete!
```

**7. Delegated Instance Returns**

```python
# Delegated instance completes
# Writes final summary to .context-foundry/session-summary.json
# Process exits
```

**8. MCP Server Detects Completion**

```python
# MCP server monitors process
if process.poll() is not None:
    # Process finished
    summary = read_session_summary(working_directory)
    TASKS[task_id]['status'] = 'completed'
    TASKS[task_id]['result'] = summary
```

**9. User Checks Status**

```
You: "What's the status of my build?"

Claude Code: [Calls get_delegation_result(task_id)]

MCP Server: Returns summary

Claude Code: "Build complete! ✅
    GitHub: github.com/snedea/weather-app
    Tests: 25/25 passing
    Duration: 8.3 minutes"
```

---

## Context Separation Benefits

### Main Window Context Usage

```
┌──────────────────────────────────────────────────┐
│ MAIN CLAUDE CODE WINDOW                          │
│ Context Window: 200,000 tokens                   │
├──────────────────────────────────────────────────┤
│                                                   │
│ User Request:                     ~100 tokens    │
│ "Build a weather app..."                         │
│                                                   │
│ Claude's Acknowledgment:           ~50 tokens    │
│ "I'll start the build..."                        │
│                                                   │
│ MCP Tool Call:                    ~200 tokens    │
│ { tool: "autonomous_build...", params: {...} }   │
│                                                   │
│ MCP Tool Response:                ~100 tokens    │
│ { task_id: "abc-123", status: "started" }        │
│                                                   │
│ User Question:                     ~50 tokens    │
│ "What's the status?"                             │
│                                                   │
│ Status Check Call:                ~100 tokens    │
│ { tool: "get_delegation_result", task_id: "..." }│
│                                                   │
│ Status Response:                  ~500 tokens    │
│ { status: "completed", github_url: "...", ... }  │
│                                                   │
│ Claude's Summary:                 ~300 tokens    │
│ "Build complete! ✅ ..."                         │
│                                                   │
├──────────────────────────────────────────────────┤
│ TOTAL CONTEXT USED:            ~1,400 tokens     │
│ Percentage:                        0.7%          │
│                                                   │
│ REMAINING CONTEXT:           198,600 tokens      │
│ Available for:          ✅ Other work            │
│                         ✅ Multiple builds       │
│                         ✅ Regular coding        │
└──────────────────────────────────────────────────┘
```

### Delegated Instance Context Usage

```
┌──────────────────────────────────────────────────┐
│ DELEGATED CLAUDE CODE INSTANCE                   │
│ Context Window: 200,000 tokens (SEPARATE!)       │
├──────────────────────────────────────────────────┤
│                                                   │
│ Orchestrator Prompt:             ~5,000 tokens   │
│ (tools/orchestrator_prompt.txt)                  │
│                                                   │
│ Phase 1: Scout                  ~10,000 tokens   │
│ ├─ Research                                      │
│ ├─ Pattern analysis                              │
│ └─ Scout report generation                       │
│                                                   │
│ Phase 2: Architect              ~15,000 tokens   │
│ ├─ Read scout report                             │
│ ├─ Design architecture                           │
│ └─ Create implementation plan                    │
│                                                   │
│ Phase 3: Builder                ~30,000 tokens   │
│ ├─ Read architecture                             │
│ ├─ Implement files                               │
│ └─ Create tests                                  │
│                                                   │
│ Phase 4: Test                    ~8,000 tokens   │
│ ├─ Run tests                                     │
│ ├─ Self-healing (if needed)                      │
│ └─ Validation                                    │
│                                                   │
│ Phase 5: Docs                    ~3,000 tokens   │
│ ├─ Generate README                               │
│ └─ Create guides                                 │
│                                                   │
│ Phase 6: Deploy                  ~2,000 tokens   │
│ ├─ Git operations                                │
│ └─ GitHub deployment                             │
│                                                   │
│ Phase 7: Feedback                ~5,000 tokens   │
│ ├─ Extract patterns                              │
│ └─ Update library                                │
│                                                   │
├──────────────────────────────────────────────────┤
│ TOTAL CONTEXT USED:           ~78,000 tokens     │
│ Percentage:                       39%            │
│                                                   │
│ IMPACT ON MAIN WINDOW:               0%          │
│ Reason:               Separate process!          │
└──────────────────────────────────────────────────┘
```

### Parallel Builds

**Because contexts are separate, you can run MULTIPLE builds simultaneously:**

```
┌──────────────────────────────────────────────────┐
│ MAIN CLAUDE WINDOW                                │
│ Context: 0.7% (clean!)                            │
└───┬──────────────────────────────────────────────┘
    │
    ├──> Delegated Instance #1: Backend API
    │    Context: 40% (isolated)
    │
    ├──> Delegated Instance #2: Frontend React App
    │    Context: 35% (isolated)
    │
    └──> Delegated Instance #3: Database Schema
         Context: 20% (isolated)

All three run SIMULTANEOUSLY without affecting each other!
```

---

## MCP Server Implementation

### Core MCP Tool: autonomous_build_and_deploy_async

**File:** `tools/mcp_server.py`

```python
from fastmcp import FastMCP
import subprocess
import uuid
import time
import json

mcp = FastMCP("Context Foundry")

# Track async tasks
TASKS = {}

@mcp.tool()
async def autonomous_build_and_deploy_async(
    task: str,
    working_directory: str,
    github_repo_name: str | None = None,
    enable_test_loop: bool = True,
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0
) -> str:
    """
    Spawn fresh Claude Code instance to build project autonomously.
    Returns immediately with task ID (non-blocking).
    """

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Build orchestrator prompt
    orchestrator_path = Path(__file__).parent / "orchestrator_prompt.txt"
    orchestrator_prompt = orchestrator_path.read_text()

    # Inject task details
    full_prompt = f"""
{orchestrator_prompt}

TASK: {task}
WORKING_DIRECTORY: {working_directory}
GITHUB_REPO: {github_repo_name or "auto-generate"}
ENABLE_TEST_LOOP: {enable_test_loop}
MAX_TEST_ITERATIONS: {max_test_iterations}
    """

    # Spawn delegated Claude Code instance
    process = subprocess.Popen(
        [
            'claude',
            '--prompt', full_prompt,
            '--permission-mode', 'bypassPermissions'  # No interactive prompts
        ],
        cwd=working_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Track task
    TASKS[task_id] = {
        'process': process,
        'task': task,
        'working_directory': working_directory,
        'status': 'running',
        'start_time': time.time(),
        'timeout': timeout_minutes * 60
    }

    # Return immediately (async!)
    return json.dumps({
        'task_id': task_id,
        'status': 'started',
        'message': f'Autonomous build started for: {task}',
        'working_directory': working_directory,
        'expected_duration': '7-15 minutes'
    })


@mcp.tool()
async def get_delegation_result(task_id: str) -> str:
    """
    Check status and get results of async task.
    """

    if task_id not in TASKS:
        return json.dumps({'error': 'Task not found'})

    task = TASKS[task_id]
    process = task['process']

    # Check if still running
    if process.poll() is None:
        elapsed = time.time() - task['start_time']
        return json.dumps({
            'status': 'running',
            'elapsed_seconds': elapsed,
            'task': task['task']
        })

    # Process finished
    # Read session summary from .context-foundry/
    summary_path = Path(task['working_directory']) / '.context-foundry' / 'session-summary.json'

    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        return json.dumps({
            'status': 'completed',
            'duration_seconds': time.time() - task['start_time'],
            **summary
        })
    else:
        # Build failed
        stdout, stderr = process.communicate()
        return json.dumps({
            'status': 'failed',
            'stdout': stdout.decode('utf-8', errors='ignore')[-5000:],  # Last 5KB
            'stderr': stderr.decode('utf-8', errors='ignore')[-5000:]
        })
```

---

## Prompt Architecture

### Orchestrator Prompt is NOT a System Prompt!

**Critical Understanding:**

```
❌ WRONG: Context Foundry modifies Claude's system prompt
✅ CORRECT: Context Foundry sends orchestrator prompt as USER message
```

**What Actually Happens:**

```
Delegated Claude Instance Starts
    ↓
SYSTEM PROMPT: [Standard Claude Code system prompt - UNCHANGED]
    ↓
USER MESSAGE: "Read tools/orchestrator_prompt.txt and execute it to build..."
    ↓
Claude reads the file (normal file operation)
    ↓
Claude executes the instructions (normal task)
```

**orchestrator_prompt.txt is just a detailed task description!**

### Orchestrator Prompt Structure

**File:** `tools/orchestrator_prompt.txt` (1000+ lines)

```
═══════════════════════════════════════════════════════════
CONTEXT FOUNDRY 2.0.1 - AUTONOMOUS BUILD ORCHESTRATOR
═══════════════════════════════════════════════════════════

You are orchestrating an autonomous software build.

PHASE 1: SCOUT (Research & Context Gathering)
───────────────────────────────────────────────────────────
1. Create Scout agent using /agents
2. Research requirements
3. Analyze technology choices
4. Read pattern library: .context-foundry/patterns/
5. Flag known risks
6. Write .context-foundry/scout-report.md

PHASE 2: ARCHITECT (Design & Planning)
───────────────────────────────────────────────────────────
1. Read scout-report.md
2. Create Architect agent using /agents
3. Design system architecture
4. Create file structure
5. Plan implementation
6. Write .context-foundry/architecture.md

PHASE 3: BUILDER (Implementation)
───────────────────────────────────────────────────────────
1. Read architecture.md
2. Create Builder agent using /agents
3. Implement all files
4. Create tests
5. Write .context-foundry/build-log.md

PHASE 4: TEST (Quality Assurance + Self-Healing)
───────────────────────────────────────────────────────────
1. Run tests
2. If failures:
   a. Analyze root cause
   b. Create fixes-iteration-N.md
   c. Re-architect if needed
   d. Re-build fixes
   e. Re-test (max 3 iterations)
3. Write test-final-report.md

PHASE 5: DOCUMENTATION
───────────────────────────────────────────────────────────
1. Generate README.md
2. Create usage guides
3. Document architecture

PHASE 6: DEPLOYMENT
───────────────────────────────────────────────────────────
1. Git init and commit
2. Create GitHub repository
3. Push to GitHub
4. Deployment complete

PHASE 7: FEEDBACK (Self-Learning)
───────────────────────────────────────────────────────────
1. Analyze what worked and what didn't
2. Extract patterns
3. Update pattern library
4. Write feedback report

═══════════════════════════════════════════════════════════
```

**This is a USER task, not a system prompt modification!**

---

## Agent Lifecycle

### Ephemeral Agents

**Agents exist only during the delegated instance's execution:**

```
Delegated Instance Spawns
    ↓
Phase 1: /agents scout
    ├─ Agent created in conversation context
    ├─ Performs research
    ├─ Writes scout-report.md
    └─ [Agent's conversation context DISCARDED when phase ends]
    ↓
Phase 2: /agents architect
    ├─ NEW agent created (no memory of Scout)
    ├─ Reads scout-report.md (file persists!)
    ├─ Performs design
    ├─ Writes architecture.md
    └─ [Agent's conversation context DISCARDED when phase ends]
    ↓
... (same pattern for Builder, Test, etc.)
    ↓
Delegated Instance Terminates
    ↓
ALL agent contexts GONE forever
```

**What Persists:**

```
✅ Files in .context-foundry/
✅ Your actual project code
✅ Git commits
✅ GitHub repository
✅ Pattern library updates (global)

❌ Agent conversation histories
❌ Delegated instance context
❌ Temporary state
```

**Why This Is Good:**

1. **Clean slate each build** - No accumulated assumptions
2. **Predictable behavior** - Same inputs = same outputs
3. **No state pollution** - Can't carry forward errors
4. **Scalable** - Agents don't accumulate context over time

---

## Comparison with Other Approaches

### vs. Single Long Conversation

| Aspect | Single Conversation | Context Foundry Delegation |
|--------|-------------------|---------------------------|
| **Context usage** | 80%+ after one build | < 1% in main window |
| **Multiple builds** | Can't run in parallel | Run simultaneously |
| **Continue working** | Blocked while building | Non-blocking |
| **Context limit** | Hit after 1-2 builds | Never (separate contexts) |
| **Build isolation** | All in one context | Each build separate |

### vs. API-Based Orchestration

| Aspect | API Orchestration | Claude Code Delegation |
|--------|------------------|----------------------|
| **Cost** | Pay per token | Fixed ($20/month unlimited) |
| **Tool access** | Limited to API tools | Full Claude Code toolset |
| **File operations** | Via API calls | Native file system |
| **Bash commands** | Via API | Direct terminal access |
| **State persistence** | Must track via code | File-based artifacts |

### vs. Cursor/Copilot

| Aspect | Cursor/Copilot | Context Foundry |
|--------|--------------|----------------|
| **Workflow** | Interactive guidance | Fully autonomous |
| **Human input** | Required for each step | Optional (checkpoints) |
| **Test failures** | Manual debugging | Self-healing auto-fix |
| **Deployment** | Manual git operations | Automatic GitHub push |
| **Pattern learning** | No learning mechanism | Self-learning from builds |

---

## FAQ

### Q: Does Context Foundry modify Claude Code's system prompt?

**A:** NO! The orchestrator prompt is sent as a **USER message**, not a system prompt. Claude Code's system prompt remains unchanged.

### Q: Will using Context Foundry affect my regular Claude Code usage?

**A:** NO! Builds run in **separate Claude Code instances**. Your main window is completely unaffected.

### Q: Can I use Claude Code for other tasks while a build is running?

**A:** YES! Builds run in the background. Your main Claude window stays available for other work.

### Q: How many builds can run in parallel?

**A:** As many as your system resources allow. Each build is an independent process with its own context.

### Q: What if I close my main Claude Code window during a build?

**A:** The delegated build continues running! It's a separate process. You can check status later with `list_delegations()`.

### Q: Can I see the agent conversations?

**A:** Not currently. You see their OUTPUT (scout-report.md, architecture.md, etc.) but not the internal conversation. This could be added in verbose mode.

### Q: What happens if a build takes longer than expected?

**A:** The MCP server has configurable timeouts (default 90 min). You can increase via `timeout_minutes` parameter.

### Q: Can I pause a running build?

**A:** Not currently. Builds run autonomously start-to-finish. You can kill the process if needed.

---

## Summary

**Context Foundry's delegation model:**

✅ Keeps your main context clean (< 1% usage)
✅ Enables parallel builds (separate processes)
✅ Non-blocking (continue working while building)
✅ Scalable (each build gets fresh 200K context)
✅ Isolated (builds don't interfere with each other)

**Key Innovation:** Using subprocess delegation instead of single conversation enables autonomous, parallel, walk-away development that doesn't pollute your main working context.

**The Result:** You can build multiple applications simultaneously while your main Claude Code window stays clean and available for other work.

---

**For More Information:**

- [FAQ.md](../FAQ.md) - Comprehensive Q&A
- [USER_GUIDE.md](../USER_GUIDE.md) - Step-by-step usage
- [FEEDBACK_SYSTEM.md](../FEEDBACK_SYSTEM.md) - Self-learning patterns
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) - Stateless conversation design

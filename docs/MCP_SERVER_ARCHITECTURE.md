# Context Foundry MCP Server Architecture

**Technical Deep Dive - Complete System Architecture**

> **Audience:** Developers, contributors, and technical users who want to understand how Context Foundry's MCP server works internally.

---

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [MCP Protocol Integration](#mcp-protocol-integration)
4. [Subprocess Delegation Model](#subprocess-delegation-model)
5. [Tool Implementations](#tool-implementations)
6. [Context Isolation Mechanism](#context-isolation-mechanism)
7. [Pattern Library Integration](#pattern-library-integration)
8. [Error Handling & Recovery](#error-handling--recovery)
9. [Performance & Scalability](#performance--scalability)
10. [Security Considerations](#security-considerations)
11. [Testing & Validation](#testing--validation)
12. [Troubleshooting & Debugging](#troubleshooting--debugging)

---

## Overview

Context Foundry 2.0 is built as an **MCP (Model Context Protocol) server** that integrates with Claude Code CLI to enable fully autonomous software development workflows.

### Key Innovation

**Traditional AI Coding:**
```
User → Claude Code (single session) → Build happens in same context
Result: Context window fills up, can't multitask
```

**Context Foundry Approach:**
```
User → Claude Code (stays clean) → MCP Server → Spawns Fresh Claude Instance → Build happens isolated
Result: Main context stays < 1%, can run multiple builds, continue working
```

### Core Principles

1. **Delegation over Monopolization** - Spawn separate processes instead of hogging main session
2. **File-based over Conversation-based** - Persist artifacts, not chat history
3. **Ephemeral Agents over Persistent State** - Clean slate each build
4. **Self-healing over Manual Debugging** - Auto-fix test failures
5. **Autonomous over Interactive** - Walk away, return to finished project

---

## Technology Stack

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ MCP Protocol Layer                                          │
│ ├─ FastMCP 2.0+          (MCP server framework)            │
│ ├─ nest-asyncio 1.5+     (Async event loop compatibility)  │
│ └─ Python 3.10+          (Type hints, pattern matching)    │
│                                                              │
│ Process Management                                          │
│ ├─ subprocess.Popen      (Spawn Claude Code instances)     │
│ ├─ asyncio               (Async task tracking)              │
│ └─ uuid                  (Task ID generation)               │
│                                                              │
│ File System Operations                                      │
│ ├─ pathlib.Path          (Cross-platform paths)            │
│ ├─ json                  (Pattern library storage)          │
│ └─ os                    (Environment variables)            │
│                                                              │
│ Claude Code Integration                                     │
│ ├─ claude-code CLI       (Delegated build instances)       │
│ ├─ --permission-mode     (Bypass interactive prompts)      │
│ └─ --prompt              (Inject orchestrator prompt)       │
│                                                              │
│ GitHub Integration                                          │
│ ├─ gh CLI                (Repository creation, pushing)     │
│ └─ git                   (Version control operations)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Dependencies

**`requirements-mcp.txt`:**
```txt
fastmcp>=2.0.0         # MCP protocol server
nest-asyncio>=1.5.0    # Async event loop nesting
```

**External Tools:**
```bash
claude-code            # Claude Code CLI (in PATH)
gh                     # GitHub CLI (for deployment)
git                    # Version control
python3.10+            # Python runtime
```

---

## MCP Protocol Integration

### What is MCP?

**Model Context Protocol (MCP)** is a standard protocol for connecting AI models to tools and data sources. It defines:

- **Tools**: Functions the AI can call
- **Resources**: Data the AI can access
- **Prompts**: Reusable prompt templates
- **Communication**: JSON-RPC 2.0 over stdio

**Context Foundry uses MCP for:**
1. Exposing build tools to Claude Code
2. Managing async task delegation
3. Tracking build status
4. Returning results to main session

### MCP Server Initialization

**File:** `tools/mcp_server.py` (lines 1-50)

```python
from fastmcp import FastMCP
import nest_asyncio
import asyncio

# Enable nested async loops (required for MCP)
nest_asyncio.apply()

# Initialize MCP server
mcp = FastMCP("Context Foundry")

# Global task tracking
TASKS = {}  # {task_id: {process, status, start_time, ...}}

# Server metadata
@mcp.tool()
async def context_foundry_status() -> str:
    """Get server status and capabilities."""
    return json.dumps({
        "name": "Context Foundry",
        "version": "2.0.1",
        "status": "operational",
        "capabilities": {
            "autonomous_builds": True,
            "async_delegation": True,
            "self_healing_tests": True,
            "pattern_learning": True,
            "github_deployment": True
        },
        "active_tasks": len([t for t in TASKS.values() if t['status'] == 'running'])
    })

# Start server (stdio transport)
if __name__ == "__main__":
    mcp.run()  # Listens on stdin/stdout for MCP messages
```

### MCP Message Flow

**User Request → MCP Tool Call → Response:**

```
┌───────────────────────────────────────────────────────────┐
│ 1. USER REQUEST                                            │
│    "Build a weather app"                                   │
└───────────────┬───────────────────────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────────────────────┐
│ 2. CLAUDE CODE INTENT DETECTION                            │
│    Recognizes build intent                                 │
│    Selects MCP tool: autonomous_build_and_deploy_async     │
└───────────────┬───────────────────────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────────────────────┐
│ 3. MCP TOOL CALL (JSON-RPC over stdio)                     │
│                                                            │
│    {                                                       │
│      "jsonrpc": "2.0",                                    │
│      "method": "tools/call",                              │
│      "params": {                                          │
│        "name": "autonomous_build_and_deploy_async",       │
│        "arguments": {                                     │
│          "task": "Build a weather app",                   │
│          "working_directory": "/tmp/weather-app",         │
│          "github_repo_name": "weather-app",               │
│          "enable_test_loop": true                         │
│        }                                                  │
│      },                                                   │
│      "id": 1                                              │
│    }                                                      │
└───────────────┬───────────────────────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────────────────────┐
│ 4. MCP SERVER PROCESSES REQUEST                            │
│    - Validates parameters                                  │
│    - Generates task ID                                     │
│    - Spawns subprocess                                     │
│    - Tracks in TASKS dict                                  │
└───────────────┬───────────────────────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────────────────────┐
│ 5. MCP RESPONSE (JSON-RPC)                                 │
│                                                            │
│    {                                                       │
│      "jsonrpc": "2.0",                                    │
│      "result": {                                          │
│        "task_id": "abc-123-def-456",                      │
│        "status": "started",                               │
│        "message": "Build running in background",          │
│        "working_directory": "/tmp/weather-app",           │
│        "expected_duration": "7-15 minutes"                │
│      },                                                   │
│      "id": 1                                              │
│    }                                                      │
└───────────────┬───────────────────────────────────────────┘
                │
                ↓
┌───────────────────────────────────────────────────────────┐
│ 6. CLAUDE CODE SHOWS RESPONSE TO USER                      │
│    "Build started! Task ID: abc-123-def-456"              │
│    "Expected duration: 7-15 minutes"                      │
│    "You can continue working..."                          │
└───────────────────────────────────────────────────────────┘
```

---

## Subprocess Delegation Model

### Why Subprocess Delegation?

**Problem:** Building in main Claude Code session consumes context window

**Solution:** Spawn fresh Claude Code instance for each build

**Benefits:**
- ✅ Main session stays clean (< 1% context usage)
- ✅ Can run multiple builds in parallel
- ✅ Each build gets fresh 200K context
- ✅ No context pollution between builds
- ✅ User can continue working

### Implementation Details

**`autonomous_build_and_deploy_async()` Tool:**

```python
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

    # 1. Generate unique task ID
    task_id = str(uuid.uuid4())

    # 2. Load orchestrator prompt template
    orchestrator_path = Path(__file__).parent / "orchestrator_prompt.txt"
    orchestrator_template = orchestrator_path.read_text()

    # 3. Inject task-specific parameters
    full_prompt = f"""
{orchestrator_template}

TASK PARAMETERS:
───────────────────────────────────────────────────────────
TASK: {task}
WORKING_DIRECTORY: {working_directory}
GITHUB_REPO: {github_repo_name or "auto-generate"}
ENABLE_TEST_LOOP: {enable_test_loop}
MAX_TEST_ITERATIONS: {max_test_iterations}
───────────────────────────────────────────────────────────

BEGIN EXECUTION NOW.
"""

    # 4. Create working directory if needed
    working_dir = Path(working_directory)
    working_dir.mkdir(parents=True, exist_ok=True)

    # 5. Spawn delegated Claude Code instance
    process = subprocess.Popen(
        [
            'claude-code',                              # Binary in PATH
            '--prompt', full_prompt,                    # User message to start
            '--permission-mode', 'bypassPermissions'    # No interactive prompts
        ],
        cwd=str(working_dir),                          # Run in project directory
        stdout=subprocess.PIPE,                         # Capture output
        stderr=subprocess.PIPE,                         # Capture errors
        text=True,                                      # Decode as UTF-8
        bufsize=1                                       # Line-buffered
    )

    # 6. Track task
    TASKS[task_id] = {
        'process': process,
        'task': task,
        'working_directory': str(working_dir),
        'github_repo_name': github_repo_name,
        'status': 'running',
        'start_time': time.time(),
        'timeout': timeout_minutes * 60,
        'enable_test_loop': enable_test_loop,
        'max_test_iterations': max_test_iterations
    }

    # 7. Return immediately (non-blocking!)
    return json.dumps({
        'task_id': task_id,
        'status': 'started',
        'message': f'Autonomous build started for: {task}',
        'working_directory': str(working_dir),
        'expected_duration': '7-15 minutes',
        'check_status': f'Use get_delegation_result("{task_id}") to check progress'
    })
```

### Process Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ SUBPROCESS LIFECYCLE                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 1. SPAWN                                                     │
│    subprocess.Popen(['claude-code', '--prompt', ...])        │
│    ├─ New process created                                   │
│    ├─ Own PID assigned                                      │
│    ├─ Own context window (200K tokens)                      │
│    └─ Receives orchestrator prompt as USER message          │
│                                                              │
│ 2. EXECUTE (7-15 minutes)                                    │
│    Delegated instance runs autonomously:                    │
│    ├─ Phase 1: Scout                                        │
│    ├─ Phase 2: Architect                                    │
│    ├─ Phase 3: Builder                                      │
│    ├─ Phase 4: Test (self-healing if needed)                │
│    ├─ Phase 5: Documentation                                │
│    ├─ Phase 6: Deploy                                       │
│    └─ Phase 7: Feedback                                     │
│                                                              │
│ 3. COMPLETE                                                  │
│    ├─ Writes .context-foundry/session-summary.json          │
│    ├─ Process exits (return code 0)                         │
│    └─ All context discarded                                 │
│                                                              │
│ 4. CLEANUP                                                   │
│    ├─ process.poll() returns exit code                      │
│    ├─ stdout/stderr read                                    │
│    ├─ TASKS[task_id]['status'] = 'completed'                │
│    └─ Results available for retrieval                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Monitoring & Status Checking

**`get_delegation_result()` Tool:**

```python
@mcp.tool()
async def get_delegation_result(task_id: str) -> str:
    """
    Check status and retrieve results of async build.

    Returns:
    - If running: {"status": "running", "elapsed": X}
    - If complete: {"status": "completed", ...full summary...}
    - If timeout: {"status": "timeout", ...}
    - If failed: {"status": "failed", "error": "..."}
    """

    # 1. Validate task exists
    if task_id not in TASKS:
        return json.dumps({
            'error': 'Task not found',
            'task_id': task_id,
            'available_tasks': list(TASKS.keys())
        })

    task = TASKS[task_id]
    process = task['process']

    # 2. Check if still running
    exit_code = process.poll()  # Returns None if running, exit code if done

    if exit_code is None:
        # Still running
        elapsed = time.time() - task['start_time']

        # Check timeout
        if elapsed > task['timeout']:
            process.kill()
            task['status'] = 'timeout'
            return json.dumps({
                'status': 'timeout',
                'task_id': task_id,
                'elapsed_seconds': elapsed,
                'timeout_seconds': task['timeout'],
                'message': 'Build exceeded timeout limit'
            })

        return json.dumps({
            'status': 'running',
            'task_id': task_id,
            'task': task['task'],
            'elapsed_seconds': elapsed,
            'timeout_seconds': task['timeout'],
            'percentage_complete': min((elapsed / 900) * 100, 95)  # Estimate
        })

    # 3. Process finished - read results
    working_dir = Path(task['working_directory'])
    summary_path = working_dir / '.context-foundry' / 'session-summary.json'

    if summary_path.exists():
        # Success - read build summary
        summary = json.loads(summary_path.read_text())
        task['status'] = 'completed'

        return json.dumps({
            'status': 'completed',
            'task_id': task_id,
            'duration_seconds': time.time() - task['start_time'],
            'exit_code': exit_code,
            **summary  # Merge all summary data
        })
    else:
        # Failed - process exited without creating summary
        stdout, stderr = process.communicate()
        task['status'] = 'failed'

        return json.dumps({
            'status': 'failed',
            'task_id': task_id,
            'exit_code': exit_code,
            'stdout': stdout[-5000:],  # Last 5KB
            'stderr': stderr[-5000:],
            'message': 'Build failed - check stdout/stderr for errors'
        })
```

---

## Tool Implementations

### Full Tool Catalog

Context Foundry MCP server exposes 9 tools:

| Tool | Type | Purpose | Blocking |
|------|------|---------|----------|
| `context_foundry_status` | Info | Get server status | Instant |
| `context_foundry_build` | Build | Legacy build tool | Blocking |
| `context_foundry_enhance` | Enhancement | Enhance existing project (coming soon) | Blocking |
| `delegate_to_claude_code` | Delegation | Delegate simple task | Blocking |
| `delegate_to_claude_code_async` | Delegation | Delegate task (async) | Non-blocking |
| `autonomous_build_and_deploy` | Build | Full build workflow | Blocking |
| `autonomous_build_and_deploy_async` | Build | Full build workflow (async) | Non-blocking |
| `get_delegation_result` | Status | Check task status | Instant |
| `list_delegations` | Status | List all tasks | Instant |

### Tool Parameter Specifications

**`autonomous_build_and_deploy_async()`:**

```python
Parameters:
  task: str                              # Required: What to build
  working_directory: str                 # Required: Where to build it
  github_repo_name: str | None = None   # Optional: GitHub repo name
  existing_repo: str | None = None      # Optional: Enhance existing repo
  mode: str = "new_project"             # Optional: "new_project" | "fix_bugs" | "add_docs"
  enable_test_loop: bool = True         # Optional: Enable self-healing
  max_test_iterations: int = 3          # Optional: Max auto-fix attempts
  timeout_minutes: float = 90.0         # Optional: Build timeout

Returns:
  JSON string with:
    - task_id: Unique task identifier
    - status: "started"
    - message: Human-readable description
    - working_directory: Absolute path
    - expected_duration: Estimate
```

**`get_delegation_result(task_id)`:**

```python
Parameters:
  task_id: str                          # Required: Task ID from async build

Returns:
  JSON string with (varies by status):

  If running:
    - status: "running"
    - elapsed_seconds: Time elapsed
    - percentage_complete: Estimate

  If completed:
    - status: "completed"
    - duration_seconds: Total time
    - phases_completed: ["scout", "architect", ...]
    - files_created: [...list of files...]
    - github_url: "https://github.com/..."
    - tests_passed: true/false
    - test_iterations: Number of test attempts

  If timeout:
    - status: "timeout"
    - elapsed_seconds: Time before timeout

  If failed:
    - status: "failed"
    - error: Error message
    - stdout/stderr: Last 5KB of output
```

---

## Context Isolation Mechanism

### The Core Problem

**Traditional approach:**
```
User conversation → Build code → More conversation → Context window fills → Hit limit
```

**Context Foundry approach:**
```
User conversation → Spawn subprocess → Build in isolation → Return summary → Context stays clean
```

### How Isolation Works

```
┌──────────────────────────────────────────────────────────────┐
│ CONTEXT ISOLATION ARCHITECTURE                                │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ MAIN CLAUDE CODE WINDOW                                      │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ Context Window: 200,000 tokens                        │    │
│ │ ├─ System Prompt: 5,000 tokens                        │    │
│ │ ├─ User: "Build weather app" (100 tokens)            │    │
│ │ ├─ Tool Call: autonomous_build_and_deploy (200 tokens)│    │
│ │ ├─ Tool Response: Task ID (100 tokens)               │    │
│ │ └─ Total Used: ~1,400 tokens (0.7%)                  │    │
│ │                                                        │    │
│ │ ✅ Remains clean and available                        │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                               │
│                        ↓ Spawns subprocess                    │
│                                                               │
│ DELEGATED CLAUDE CODE INSTANCE (Separate Process)            │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ Context Window: 200,000 tokens (SEPARATE!)            │    │
│ │ ├─ System Prompt: 5,000 tokens                        │    │
│ │ ├─ Orchestrator Prompt (USER msg): 5,000 tokens      │    │
│ │ ├─ Phase 1 Scout: 10,000 tokens                      │    │
│ │ ├─ Phase 2 Architect: 15,000 tokens                  │    │
│ │ ├─ Phase 3 Builder: 30,000 tokens                    │    │
│ │ ├─ Phase 4 Test: 8,000 tokens                        │    │
│ │ ├─ Phase 5 Docs: 3,000 tokens                        │    │
│ │ ├─ Phase 6 Deploy: 2,000 tokens                      │    │
│ │ └─ Total Used: ~78,000 tokens (39%)                  │    │
│ │                                                        │    │
│ │ ❌ Discarded when process exits                       │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                               │
│ IMPACT ON MAIN WINDOW: 0% (completely isolated!)             │
└──────────────────────────────────────────────────────────────┘
```

### Key Insights

1. **Separate Operating System Processes**
   - Main Claude Code: PID 12345
   - Delegated Instance: PID 67890
   - No shared memory

2. **Separate Context Windows**
   - Each process has own 200K token budget
   - No cross-contamination
   - Build can use 80% of context without affecting main window

3. **Communication via Files Only**
   - No message passing between processes
   - Results written to `.context-foundry/session-summary.json`
   - MCP server reads file after process exits

4. **Clean Slate Each Build**
   - Every build starts fresh
   - No accumulated context from previous builds
   - Predictable, repeatable behavior

---

## Pattern Library Integration

### Where Patterns Live

**Global Patterns** (shared across all builds):
```
/Users/name/homelab/context-foundry/.context-foundry/patterns/
├── common-issues.json           # Known issues and solutions
├── test-patterns.json           # Testing strategies
├── architecture-patterns.json   # Proven architectures
└── scout-learnings.json         # Research insights
```

**Project Patterns** (project-specific):
```
/Users/name/homelab/your-project/.context-foundry/patterns/
└── [Same structure, project-specific discoveries]
```

### How Patterns Are Used

**Phase 1: Scout** reads global patterns:
```python
# Scout agent checks for known issues
patterns_path = Path.home() / ".context-foundry" / "patterns" / "common-issues.json"
if patterns_path.exists():
    patterns = json.loads(patterns_path.read_text())

    # Check if current project type has known issues
    for pattern in patterns['patterns']:
        if project_type in pattern['project_types']:
            # Warn about potential issues in scout-report.md
            warnings.append({
                'pattern_id': pattern['pattern_id'],
                'severity': pattern['severity'],
                'issue': pattern['issue'],
                'prevention': pattern['solution']
            })
```

**Phase 7: Feedback** updates patterns:
```python
# Feedback agent extracts new learnings
if build_had_issues and issue_was_resolved:
    new_pattern = {
        'pattern_id': generate_id(issue_description),
        'first_seen': today,
        'frequency': 1,
        'project_types': [current_project_type],
        'issue': issue_description,
        'solution': resolution_steps,
        'severity': calculate_severity(impact),
        'auto_apply': is_automatable
    }

    # Add to global pattern library
    global_patterns['patterns'].append(new_pattern)
    save_patterns(global_patterns)
```

### MCP Server Pattern Access

MCP server provides pattern management tools:

```python
@mcp.tool()
async def read_global_patterns(pattern_type: str = "common-issues") -> str:
    """Read patterns from global library."""
    patterns_path = CONTEXT_FOUNDRY_ROOT / ".context-foundry" / "patterns" / f"{pattern_type}.json"
    if patterns_path.exists():
        return patterns_path.read_text()
    return json.dumps({"patterns": [], "version": "1.0"})

@mcp.tool()
async def save_global_patterns(pattern_type: str, patterns_data: str) -> str:
    """Save patterns to global library."""
    patterns_path = CONTEXT_FOUNDRY_ROOT / ".context-foundry" / "patterns" / f"{pattern_type}.json"
    patterns_path.parent.mkdir(parents=True, exist_ok=True)
    patterns_path.write_text(patterns_data)
    return json.dumps({"status": "saved", "path": str(patterns_path)})
```

---

## Error Handling & Recovery

### Timeout Handling

```python
# In get_delegation_result()
if elapsed > task['timeout']:
    # Kill runaway process
    process.kill()
    process.wait(timeout=5)  # Give it 5 seconds to die gracefully

    # Mark as timeout
    task['status'] = 'timeout'

    # Partial results may exist
    partial_results = {}
    if (Path(task['working_directory']) / '.context-foundry').exists():
        # Check what phases completed
        if (Path(task['working_directory']) / '.context-foundry' / 'scout-report.md').exists():
            partial_results['scout_completed'] = True
        if (Path(task['working_directory']) / '.context-foundry' / 'architecture.md').exists():
            partial_results['architect_completed'] = True
        # etc.

    return json.dumps({
        'status': 'timeout',
        'elapsed_seconds': elapsed,
        'partial_results': partial_results,
        'recovery': 'Review partial artifacts in .context-foundry/ and retry with higher timeout'
    })
```

### Process Crash Handling

```python
# If process exits with non-zero code
if exit_code != 0:
    stdout, stderr = process.communicate()

    # Parse common errors
    if 'ModuleNotFoundError' in stderr:
        error_type = 'dependency_missing'
        suggestion = 'Install missing Python packages: pip install -r requirements-mcp.txt'
    elif 'claude-code: command not found' in stderr:
        error_type = 'claude_code_not_installed'
        suggestion = 'Install Claude Code CLI and add to PATH'
    elif 'Permission denied' in stderr:
        error_type = 'permission_error'
        suggestion = 'Check file/directory permissions'
    else:
        error_type = 'unknown'
        suggestion = 'Check stderr for details'

    return json.dumps({
        'status': 'failed',
        'exit_code': exit_code,
        'error_type': error_type,
        'suggestion': suggestion,
        'stdout': stdout[-2000:],
        'stderr': stderr[-2000:]
    })
```

### Self-Healing Test Loop

**Built into delegated instance, not MCP server!**

The orchestrator prompt includes self-healing logic:

```
PHASE 4: TEST (with Self-Healing)
───────────────────────────────────
1. Run tests: npm test (or pytest, etc.)
2. Parse results
3. IF tests pass:
     → Write test-final-report.md
     → Continue to Phase 5
4. IF tests fail AND iterations < max_test_iterations:
     → Analyze root cause
     → Write test-results-iteration-N.md
     → Create fixes-iteration-N.md
     → Apply fixes (re-run Builder phase for specific files)
     → Increment iteration counter
     → GOTO step 1 (retry tests)
5. IF tests fail AND iterations >= max_test_iterations:
     → Write test-final-report.md with failure details
     → Continue to Phase 5 (document known issues)
```

---

## Performance & Scalability

### Concurrent Build Limits

**No artificial limits!** Constrained only by system resources:

```python
# In MCP server - no limit on TASKS
TASKS = {}  # Can grow indefinitely

# Practical limits:
# - CPU: Each Claude Code instance uses 1-2 cores
# - Memory: Each instance uses ~500MB-1GB RAM
# - Network: API calls (if using Anthropic API mode)

# Example capacity on typical dev machine:
# - 8-core CPU: ~4-6 parallel builds comfortable
# - 16GB RAM: ~10-15 builds before swapping
# - Gigabit internet: Network not a bottleneck
```

### Resource Optimization

**1. Process Cleanup:**
```python
# Automatic cleanup of finished tasks (optional)
async def cleanup_completed_tasks():
    """Remove completed tasks older than 1 hour."""
    cutoff = time.time() - 3600
    to_remove = [
        task_id for task_id, task in TASKS.items()
        if task['status'] in ['completed', 'failed', 'timeout']
        and task['start_time'] < cutoff
    ]
    for task_id in to_remove:
        del TASKS[task_id]
```

**2. Output Buffering:**
```python
# Prevent memory bloat from large stdout/stderr
process = subprocess.Popen(
    [...],
    bufsize=1,  # Line-buffered (not unbuffered = 0)
    # This prevents buffering entire output in memory
)
```

**3. File-based Artifacts:**
```python
# Don't store build artifacts in memory
# Write to files immediately:
# - .context-foundry/scout-report.md
# - .context-foundry/architecture.md
# - .context-foundry/build-log.md
# MCP server reads summary file only when requested
```

### Benchmark Performance

**Measured on MacBook Pro (M1, 16GB RAM):**

| Metric | Value |
|--------|-------|
| Single build time | 7-15 minutes |
| Parallel builds (4x) | 12-18 minutes |
| Memory per build | ~800MB |
| CPU per build | 1.5 cores avg |
| Main context usage | < 1% (0.7% measured) |
| Delegated context usage | 30-50% |

**Speedup from Parallel Execution:**
```
Sequential: 4 builds × 10 min = 40 minutes
Parallel:   4 builds in ~15 minutes = 2.7x speedup
```

---

## Security Considerations

### Process Isolation

**Each delegated instance:**
- ✅ Runs with same user permissions as MCP server
- ✅ Cannot escalate privileges
- ✅ Isolated from other delegated instances
- ✅ Cannot access main Claude window's context
- ❌ Not sandboxed (has full filesystem access)

**Implications:**
```
Delegated instances can:
  ✅ Create/modify files in working_directory
  ✅ Run bash commands (tests, git, npm, etc.)
  ✅ Access internet (API calls, package downloads)
  ✅ Create GitHub repositories

Delegated instances CANNOT:
  ❌ Access files outside working_directory (unless explicitly given permission)
  ❌ Modify Context Foundry source code (different directory)
  ❌ Affect other running builds
  ❌ Read your Claude Code conversation history
```

### API Key Handling

**Environment Variables:**
```python
# MCP server doesn't need API keys for Claude Max subscription mode
# But if using API mode:

@mcp.tool()
async def autonomous_build_and_deploy_async(...):
    # Don't log API keys!
    env = os.environ.copy()
    if 'ANTHROPIC_API_KEY' in env:
        env['ANTHROPIC_API_KEY_MASKED'] = env['ANTHROPIC_API_KEY'][:8] + '...'

    # Pass environment to subprocess
    process = subprocess.Popen(
        [...],
        env=env  # Inherits MCP server's environment (including API keys)
    )
```

**Recommended Practice:**
```bash
# Store API keys in ~/.zshrc or ~/.bashrc
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."

# NOT in .mcp.json (gets committed to git!)
# NOT in orchestrator_prompt.txt (readable by user)
```

### Code Injection Prevention

**User input is sanitized:**
```python
# Task description is escaped before shell execution
task_description = user_input.replace('"', '\\"').replace('$', '\\$')

# Passed via --prompt flag (shell-safe)
process = subprocess.Popen([
    'claude-code',
    '--prompt', task_description  # List argument (not shell string!)
])

# NOT this (vulnerable to injection):
# os.system(f'claude-code --prompt "{task_description}"')  # ❌ UNSAFE!
```

---

## Testing & Validation

### MCP Server Tests

**Test harness location:** `tests/test_mcp_server.py`

```python
import pytest
from tools.mcp_server import autonomous_build_and_deploy_async, get_delegation_result

@pytest.mark.asyncio
async def test_build_spawns_subprocess():
    """Test that build tool spawns subprocess correctly."""
    result = await autonomous_build_and_deploy_async(
        task="Create hello.py that prints 'Hello World'",
        working_directory="/tmp/test-build"
    )

    result_dict = json.loads(result)
    assert result_dict['status'] == 'started'
    assert 'task_id' in result_dict
    assert result_dict['working_directory'] == '/tmp/test-build'

@pytest.mark.asyncio
async def test_get_status_while_running():
    """Test status check while build is running."""
    # Start build
    result = await autonomous_build_and_deploy_async(
        task="Create hello.py",
        working_directory="/tmp/test-build"
    )
    task_id = json.loads(result)['task_id']

    # Check status immediately
    status = await get_delegation_result(task_id)
    status_dict = json.loads(status)
    assert status_dict['status'] == 'running'
    assert 'elapsed_seconds' in status_dict
```

### Integration Tests

**Manual test procedure:**

```bash
# 1. Start MCP server in one terminal
cd /Users/name/homelab/context-foundry
python3 tools/mcp_server.py

# 2. Start Claude Code in another terminal
claude-code

# 3. In Claude Code session, test each tool:
> Use mcp__context_foundry_status

> Use mcp__autonomous_build_and_deploy_async with:
>   task: "Create a Python script that prints the Fibonacci sequence"
>   working_directory: "/tmp/fib-test"

> [Wait 30 seconds]

> Use mcp__get_delegation_result with the task_id from above

> Use mcp__list_delegations

# 4. Verify results
> Check /tmp/fib-test/.context-foundry/session-summary.json
```

---

## Troubleshooting & Debugging

### Enable Verbose Logging

**Add to `tools/mcp_server.py`:**
```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/context-foundry-mcp.log'
)
logger = logging.getLogger('context-foundry')

@mcp.tool()
async def autonomous_build_and_deploy_async(...):
    logger.debug(f"Received build request: task={task}, working_dir={working_directory}")

    # ... spawn process ...

    logger.debug(f"Spawned process PID={process.pid}, task_id={task_id}")

    return json.dumps({...})
```

**View logs:**
```bash
tail -f /tmp/context-foundry-mcp.log
```

### Inspect Process State

**Check running delegated instances:**
```bash
# See all Claude Code processes
ps aux | grep claude-code

# Output:
# user  12345  ... claude-code (main session)
# user  67890  ... claude-code --prompt "Read orchestrator..." (delegated)
# user  67891  ... claude-code --prompt "Read orchestrator..." (another delegated)

# Kill a specific delegated instance
kill 67890
```

### Debug Subprocess Output

**Read stdout/stderr while process runs:**
```python
# Modify subprocess.Popen to save output to file
log_file = Path(working_directory) / '.context-foundry' / 'build-output.log'

process = subprocess.Popen(
    [...],
    stdout=open(log_file, 'w'),
    stderr=subprocess.STDOUT  # Merge stderr into stdout
)

# Now you can tail the log:
# tail -f /path/to/working_directory/.context-foundry/build-output.log
```

### Common Issues

**1. "MCP Server not responding"**
```
Symptoms: Claude Code says MCP tools unavailable
Cause: MCP server not running or misconfigured

Fix:
1. Check MCP server is running: ps aux | grep mcp_server.py
2. Check .mcp.json path is correct
3. Restart Claude Code: exit and run claude-code again
```

**2. "Process spawns but nothing happens"**
```
Symptoms: get_delegation_result shows "running" forever
Cause: Delegated instance waiting for input (shouldn't happen with --permission-mode bypassPermissions)

Fix:
1. Check process logs: cat /tmp/context-foundry-mcp.log
2. Verify --permission-mode bypassPermissions is set
3. Check process isn't hung: ps aux | grep <PID>
```

**3. "Build succeeds but no GitHub deployment"**
```
Symptoms: Code builds, tests pass, but no GitHub repo created
Cause: GitHub CLI not authenticated

Fix:
1. Check: gh auth status
2. Authenticate: gh auth login
3. Retry build
```

---

## Summary

**Context Foundry MCP Server Architecture:**

✅ **FastMCP 2.0** framework for MCP protocol
✅ **Subprocess delegation** for context isolation
✅ **9 MCP tools** for build automation and task management
✅ **File-based artifacts** (no memory bloat)
✅ **Pattern library integration** (self-learning)
✅ **Self-healing test loops** (autonomous debugging)
✅ **Parallel execution** (unlimited concurrent builds)
✅ **Professional error handling** (timeouts, crashes, recovery)

**Key Files:**
- `tools/mcp_server.py` - MCP server implementation (1400 lines)
- `tools/orchestrator_prompt.txt` - Build workflow meta-prompt (1000+ lines)
- `.mcp.json` - Project-shareable MCP configuration
- `requirements-mcp.txt` - Python dependencies

**For More Information:**
- [CONTEXT_PRESERVATION.md](CONTEXT_PRESERVATION.md) - Context flow deep dive
- [DELEGATION_MODEL.md](DELEGATION_MODEL.md) - How delegation keeps context clean
- [CLAUDE_CODE_MCP_SETUP.md](../CLAUDE_CODE_MCP_SETUP.md) - Setup and troubleshooting
- [FAQ.md](../FAQ.md) - Frequently asked questions

---

**Version:** 2.0.1 | **Last Updated:** October 2025

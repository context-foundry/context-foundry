# Context Foundry Architectural Failure Analysis

**Date:** 2025-11-11
**Build Task:** 62a13aae-8631-4edc-bb35-47d65b388861 (Workday EIB Builder)
**Status:** 🚨 CATASTROPHIC FAILURE CONFIRMED
**Impact:** CRITICAL - Violates core design principle

---

## Executive Summary

Context Foundry has a fundamental architectural flaw where **it runs a single orchestrator agent with accumulated context** instead of **spawning separate fresh agents per phase** that read handoff `.md` files. This violates the core design principle that makes Context Foundry scalable and efficient.

### Evidence

**Build Monitoring Results:**
- **Process Count:** 1 process (PID 58910) for entire 66-minute build
- **Child Processes:** 0 spawned
- **Context Accumulation:** Estimated 4K → 100K+ tokens across all phases
- **Exit Code:** -9 (SIGKILL) - likely due to timeout or resource exhaustion

**What Should Have Happened:**
```
autonomous_build.py
  ├─ Spawns Scout agent (fresh context)
  │  └─ Reads: task description
  │  └─ Writes: scout-report.md
  │  └─ Exits (releases context)
  │
  ├─ Spawns Architect agent (fresh context)
  │  └─ Reads: scout-report.md ONLY
  │  └─ Writes: architecture.md
  │  └─ Exits (releases context)
  │
  ├─ Spawns Builder agent (fresh context)
  │  └─ Reads: architecture.md ONLY
  │  └─ Writes: source files
  │  └─ Exits (releases context)
  │
  └─ Spawns Test agent (fresh context)
     └─ Reads: source files
     └─ Writes: test-final-report.md
     └─ Exits (releases context)
```

**What Actually Happened:**
```
autonomous_build.py
  └─ Spawns ONE orchestrator agent
     └─ Reads: task description (4K tokens)
     └─ Phase 1 Scout: Creates scout-report.md (context: 4K + 16K = 20K)
     └─ Phase 2 Architect: Reads scout-report.md (context: 20K + 55K = 75K)
     └─ Phase 3 Builder: Reads architecture.md (context: 75K + code = 100K+)
     └─ Phase 4 Test: Sees EVERYTHING (context: 100K+ → timeout/kill)
     └─ NEVER EXITS - accumulates context until failure
```

---

## The Design Violation

### Core Principle (FROM DESIGN INTENT)

**Each phase should:**
1. Start with a **FRESH context window** (<20K tokens)
2. Read **ONLY** the previous phase's `.md` handoff file
3. Execute its work
4. Write its `.md` handoff file
5. **Exit and release all context**

**Benefits:**
- 🚀 Scalable to unlimited complexity (each phase stays <20K tokens)
- 🎯 Better quality (agents in "SMART ZONE" 0-40% context)
- 💾 Memory efficient (no accumulation)
- 🔄 Parallelizable (phases can spawn multiple fresh agents)
- 🧹 Clean handoffs (explicit contracts via .md files)

### Current Implementation

**What happens:**
1. `autonomous_build.py` spawns ONE `claude` process
2. That process loads `orchestrator_prompt.txt` (30K tokens)
3. That SAME process runs ALL phases sequentially
4. Context accumulates: 30K → 50K → 75K → 100K+
5. By Phase 4, agent is in "DUMB ZONE" (40-80%) or "CRITICAL ZONE" (80-100%)
6. Quality degrades, memory grows, eventually timeout/kill

**The code claims:**
```python
# From autonomous_build.py line 4:
"""Spawns fresh Claude instances that run in the background with Scout/Architect/Builder/Tester agents."""

# From autonomous_build.py line 65:
Spawns fresh Claude instance that runs in the BACKGROUND
```

**But it actually does:**
```python
# Line 515-523: Spawns ONE process
process = subprocess.Popen(
    cmd,  # Single 'claude' command with orchestrator_prompt.txt
    cwd=final_working_dir_str,
    ...
)
```

No loop. No per-phase spawning. No fresh contexts.

---

## Evidence From The Failed Build

### Files Created (Handoff Files Exist!)
```
.context-foundry/
├── scout-report.md          (16KB) ✅ Created
├── architecture.md          (55KB) ✅ Created
├── test-final-report.md     (12KB) ✅ Created
├── test-summary.md          (4.5KB) ✅ Created
└── build-tasks.json         (7.2KB) ✅ Created
```

These ARE the handoff files! They were created correctly.

**BUT:** They were all created by the SAME orchestrator agent in ONE accumulated context.

### Context Metrics (From session-summary.json)

```json
{
  "context_metrics": {
    "max_context_window": 200000,
    "model": "claude-sonnet-4",
    "by_phase": {
      "phase_scout": {
        "tokens_used": 4092,
        "percentage": 2.05,
        "zone": "smart"
      }
      // No other phases recorded!
    }
  }
}
```

**Only Scout phase was tracked.** Why? Because the orchestrator never spawned separate processes for other phases, so the context tracking system couldn't measure them independently.

### Process Evidence

**From `ps aux` monitoring:**
- PID 58910: Main orchestrator process
- Child processes: NONE
- Duration: 66 minutes
- Exit code: -9 (SIGKILL)

**Expected:** 4+ separate `claude` processes (Scout → Architect → Builder → Test)
**Actual:** 1 orchestrator process doing everything

---

## Comparison: Intended vs Actual Architecture

### Intended (Fresh Agents Per Phase)

| Phase | Process | Context Size | Reads | Writes | Context Fate |
|-------|---------|-------------|-------|--------|-------------|
| Scout | NEW process | 4K tokens | Task desc | scout-report.md | ✅ Released on exit |
| Architect | NEW process | 16K tokens | scout-report.md | architecture.md | ✅ Released on exit |
| Builder | NEW process | 55K tokens | architecture.md | Source files | ✅ Released on exit |
| Test | NEW process | 10K tokens | Source files | test-report.md | ✅ Released on exit |

**Total peak memory:** ~55K tokens (Architect phase)
**Each agent quality:** SMART ZONE (2-28% context)

### Actual (Accumulated Context)

| Phase | Process | Context Size | Reads | Writes | Context Fate |
|-------|---------|-------------|-------|--------|-------------|
| Scout | PID 58910 | 4K tokens | Task desc | scout-report.md | ⚠️ ACCUMULATES |
| Architect | SAME 58910 | 20K tokens | EVERYTHING | architecture.md | ⚠️ ACCUMULATES |
| Builder | SAME 58910 | 75K tokens | EVERYTHING | Source files | ⚠️ ACCUMULATES |
| Test | SAME 58910 | 100K+ tokens | EVERYTHING | test-report.md | 🚨 TIMEOUT/KILL |

**Total peak memory:** 100K+ tokens (approaching limit)
**Agent quality:** SMART → DUMB → CRITICAL (2% → 50%+ context)

---

## Why This Is Catastrophic

### 1. Performance Degradation
From the orchestrator_prompt.txt's own documentation:

```
Based on empirical research (Jeff Huntley, Ralph Wiggum technique):
- SMART ZONE (0-40% context): Optimal model performance ✅
- DUMB ZONE (40-80% context): Degraded reasoning and quality ⚠️
- CRITICAL ZONE (80-100% context): Severe performance issues 🚨

"You get better results if you use less context because
 the attention is spread over less noise."
```

**By Phase 4 (Test), the orchestrator is in DUMB or CRITICAL zone.**

### 2. Scalability Failure
- **Intended:** Can handle arbitrarily complex projects (each phase <20K tokens)
- **Actual:** Limited to projects that fit in 200K cumulative context
- **Impact:** Large projects (like Workday EIB Builder) hit timeout/kill

### 3. Context Pollution
- **Intended:** Architect reads ONLY scout-report.md (focused input)
- **Actual:** Architect sees task description + scout phase execution + full scout report
- **Impact:** Noise reduces signal, decisions degraded

### 4. Memory Inefficiency
- **Intended:** Peak 55K tokens (Architect phase), released after each phase
- **Actual:** Grows to 100K+ tokens, never released until process dies
- **Impact:** Wastes resources, slower execution

### 5. No True Parallelization
The PARALLEL_AGENTS_ARCHITECTURE.md describes parallel builders via bash spawning:

```bash
claude --print --system-prompt "$(cat builder_task_prompt.txt)" "TASK_ID: task-1" &
claude --print --system-prompt "$(cat builder_task_prompt.txt)" "TASK_ID: task-2" &
wait
```

**This is WITHIN-PHASE parallelization** (multiple builders in parallel).

**Missing:** BETWEEN-PHASE fresh agent spawning (Scout → new Architect → new Builder)

---

## Root Cause Analysis

### The `/agents` Confusion

The `orchestrator_prompt.txt` says:
```
2. Create a Scout agent:
   Type: /agents
```

This uses Claude Code's native `/agents` command, which creates sub-agents **within the same context**.

**This is NOT the same as spawning a new `claude` process with fresh context.**

### What Should Happen (Process-Level Spawning)

```python
# In autonomous_build.py (FIXED VERSION)

# Phase 1: Scout
scout_cmd = [
    "claude", "--print",
    "--system-prompt", scout_prompt,
    task_description
]
scout_process = subprocess.run(scout_cmd, capture_output=True)
# scout_process exits → context released

# Phase 2: Architect
architect_cmd = [
    "claude", "--print",
    "--system-prompt", architect_prompt,
    "Read .context-foundry/scout-report.md and create architecture.md"
]
architect_process = subprocess.run(architect_cmd, capture_output=True)
# architect_process exits → context released

# Phase 3: Builder
builder_cmd = [
    "claude", "--print",
    "--system-prompt", builder_prompt,
    "Read .context-foundry/architecture.md and implement"
]
builder_process = subprocess.run(builder_cmd, capture_output=True)
# builder_process exits → context released

# etc.
```

**Each `subprocess.run()` creates a NEW process that EXITS when done.**

### What Actually Happens (Single Orchestrator)

```python
# In autonomous_build.py (CURRENT BROKEN VERSION)

# One-time process spawn
cmd = ["claude", "--print", "--system-prompt", orchestrator_prompt, task]
process = subprocess.Popen(cmd, ...)

# This ONE process does EVERYTHING
# Context accumulates
# Never exits until timeout/kill
```

---

## Impact on Workday EIB Builder Build

### Build Timeline
- **Start:** 20:58 (Phase: Scout)
- **Scout Complete:** 21:01 (3 minutes, 4K tokens)
- **Architect Complete:** 21:14 (13 minutes, estimated 20K tokens accumulated)
- **Builder Complete:** 21:41 (27 minutes, estimated 75K tokens accumulated)
- **Test Phase:** 21:41 - 22:04 (23 minutes, estimated 100K+ tokens)
- **Documentation:** 22:04 - 22:06 (2 minutes, partial)
- **KILLED:** 22:06 (exit code -9)

### Symptoms
1. ✅ Scout worked fine (SMART ZONE, 2% context)
2. ✅ Architect worked but slower (approaching DUMB ZONE)
3. ⚠️ Builder worked but very slow (DUMB ZONE, 40-50% context)
4. 🚨 Test phase extremely slow (CRITICAL ZONE, 50%+ context)
5. ❌ Documentation incomplete (process killed)
6. ❌ No deployment (never reached)

### Files Created But Build Failed
- **192 files created** (1.3MB)
- **Test suite generated** (23 test files, 215+ tests)
- **Documentation started** (30% complete)
- **BUT:** Process killed before completion
- **Root cause:** Context accumulation → timeout

---

## The Fix Required

### Phase-Level Process Spawning

Modify `autonomous_build.py` to spawn separate processes per phase:

```python
def run_phase_with_fresh_context(phase_name, phase_prompt, input_files, output_file):
    """Spawn a NEW claude process with FRESH context for this phase."""
    cmd = [
        "claude", "--print",
        "--permission-mode", "bypassPermissions",
        "--system-prompt", phase_prompt,
        f"Execute {phase_name} phase. Read {input_files}, write {output_file}"
    ]

    result = subprocess.run(
        cmd,
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=phase_timeout
    )

    # Process EXITS here → context released
    return result

# Run phases sequentially with fresh contexts
run_phase_with_fresh_context("Scout", scout_prompt, "task.txt", "scout-report.md")
run_phase_with_fresh_context("Architect", architect_prompt, "scout-report.md", "architecture.md")
run_phase_with_fresh_context("Builder", builder_prompt, "architecture.md", "source files")
run_phase_with_fresh_context("Test", test_prompt, "source files", "test-report.md")
# etc.
```

### Specialized Phase Prompts

Instead of one mega `orchestrator_prompt.txt`, create:
- `tools/prompts/scout_phase_prompt.txt` - Just Scout instructions
- `tools/prompts/architect_phase_prompt.txt` - Just Architect instructions
- `tools/prompts/builder_phase_prompt.txt` - Just Builder instructions
- `tools/prompts/test_phase_prompt.txt` - Just Test instructions

Each is ~5-10KB (not 30KB+).

### Handoff Contract

Each phase:
1. Receives path to previous .md file as input
2. Reads that file FIRST
3. Executes work
4. Writes its .md file
5. Exits (subprocess.run returns)

---

## Validation

### How to Verify the Fix Works

1. **Process monitoring:**
   ```bash
   watch -n 1 'ps aux | grep claude | grep -v grep'
   ```
   Should see:
   - Scout process appears → exits
   - Architect process appears → exits
   - Builder process appears → exits
   - etc.

2. **Context measurement:**
   ```json
   {
     "by_phase": {
       "phase_scout": {"tokens_used": 4092, "zone": "smart"},
       "phase_architect": {"tokens_used": 16234, "zone": "smart"},
       "phase_builder": {"tokens_used": 52811, "zone": "smart"},
       "phase_test": {"tokens_used": 9102, "zone": "smart"}
     }
   }
   ```
   All phases in SMART ZONE!

3. **Memory profile:**
   - Peak memory: ~55K tokens (not 100K+)
   - Each phase releases context on exit

4. **Build completion:**
   - No timeouts on large projects
   - All phases complete successfully
   - Quality maintained throughout

---

## Conclusion

This is a **catastrophic architectural failure** that violates Context Foundry's core design principle. The system claims to spawn fresh agents per phase but actually runs a single orchestrator with accumulated context.

**Impact:**
- 🚨 Scalability limited (large projects timeout)
- 🚨 Quality degradation (agents enter DUMB/CRITICAL zones)
- 🚨 Memory inefficiency (100K+ tokens vs <20K per phase)
- 🚨 False documentation (code comments claim fresh agents)

**Fix Required:**
- Implement true per-phase process spawning in `autonomous_build.py`
- Create specialized phase prompts (not mega orchestrator)
- Each phase: fresh process → read .md → work → write .md → exit

**Priority:** CRITICAL - This must be fixed before Context Foundry can reliably handle complex projects.

---

**Discovered by:** User observation during Workday EIB Builder build monitoring
**Confirmed by:** Process monitoring, context analysis, file examination
**Status:** Documented, awaiting fix implementation

# Phase Process Spawning - Architecture Redesign

**Date:** 2025-11-11
**Status:** 🚧 Design Phase
**Goal:** Implement true per-phase process spawning with fresh contexts

---

## Design Overview

Replace the single orchestrator process with **sequential phase execution** where each phase:
1. Spawns as a NEW `claude` process with FRESH context
2. Reads ONLY the previous phase's `.md` handoff file
3. Executes its specific work
4. Writes its `.md` handoff file
5. EXITS (releases context completely)

---

## Architecture Diagram

### Current (Broken)
```
autonomous_build.py
  └─ Spawns ONE claude process with orchestrator_prompt.txt (30K tokens)
     ├─ Phase 1: Scout (context: 30K + 4K = 34K)
     ├─ Phase 2: Architect (context: 34K + 16K = 50K)
     ├─ Phase 2.5: Builder (context: 50K + 55K = 105K) ← DUMB ZONE
     ├─ Phase 4: Test (context: 105K + 10K = 115K) ← CRITICAL ZONE
     └─ EXIT (after 60+ minutes or timeout/kill)
```

### New (Fixed)
```
autonomous_build.py
  ├─ run_scout_phase()
  │  └─ subprocess.run(["claude", scout_prompt.txt, task])
  │     → writes scout-report.md
  │     → EXITS (releases 4K context)
  │
  ├─ run_architect_phase()
  │  └─ subprocess.run(["claude", architect_prompt.txt, "read scout-report.md"])
  │     → writes architecture.md
  │     → EXITS (releases 16K context)
  │
  ├─ run_builder_phase()
  │  └─ subprocess.run(["claude", builder_prompt.txt, "read architecture.md"])
  │     → writes source files
  │     → EXITS (releases 55K context)
  │
  ├─ run_test_phase()
  │  └─ subprocess.run(["claude", test_prompt.txt, "test project"])
  │     → writes test-report.md
  │     → EXITS (releases 10K context)
  │
  └─ run_deploy_phase()
     └─ subprocess.run(["claude", deploy_prompt.txt, "deploy to github"])
        → creates GitHub repo/PR
        → EXITS (releases 6K context)
```

**Peak context:** 55K tokens (Builder phase only)
**All phases:** SMART ZONE (0-40% of 200K)

---

## Phase Breakdown

### Phase 0: Codebase Analysis (Enhancement modes only)
**Input:** Working directory
**Output:** `.context-foundry/codebase-analysis.md`
**Process:** NEW process
**Context:** ~5K tokens
**Prompt:** `tools/prompts/phase_codebase_analysis.txt`

### Phase 1: Scout (Research & Requirements)
**Input:** Task description + codebase-analysis.md (if exists)
**Output:** `.context-foundry/scout-report.md`
**Process:** NEW process
**Context:** ~4K tokens
**Prompt:** `tools/prompts/phase_scout.txt`

### Phase 2: Architect (Design)
**Input:** `scout-report.md`
**Output:** `.context-foundry/architecture.md`
**Process:** NEW process
**Context:** ~16K tokens
**Prompt:** `tools/prompts/phase_architect.txt`

### Phase 2.5: Builder (Implementation)
**Input:** `architecture.md`
**Output:** Source code files + `.context-foundry/build-tasks.json`
**Process:** NEW process (with optional parallel sub-builders)
**Context:** ~55K tokens (main) + N × 20K (parallel builders)
**Prompt:** `tools/prompts/phase_builder.txt`
**Parallel:** Uses `builder_task_prompt.txt` for sub-tasks

### Phase 3.5: Integration Pre-Check (Optional fast validation)
**Input:** Source files
**Output:** `.context-foundry/precheck-results.txt`
**Process:** NEW process
**Context:** ~5K tokens
**Prompt:** `tools/prompts/phase_precheck.txt`

### Phase 4: Test (Validation)
**Input:** Source files + architecture.md
**Output:** `.context-foundry/test-report.md`
**Process:** NEW process
**Context:** ~10K tokens
**Prompt:** `tools/prompts/phase_test.txt`
**Self-healing:** If tests fail, loops back to Phase 2 (Architect) up to N times

### Phase 4.5: Screenshot (Visual documentation)
**Input:** Running application
**Output:** `docs/screenshots/*.png`
**Process:** NEW process
**Context:** ~3K tokens
**Prompt:** `tools/prompts/phase_screenshot.txt`

### Phase 5: Documentation
**Input:** Source files + architecture.md
**Output:** `README.md`, `docs/*.md`
**Process:** NEW process
**Context:** ~10K tokens
**Prompt:** `tools/prompts/phase_documentation.txt`

### Phase 6: Deployment (GitHub)
**Input:** All project files
**Output:** GitHub repo + remote push
**Process:** NEW process
**Context:** ~6K tokens
**Prompt:** `tools/prompts/phase_deploy.txt`

### Phase 7: Feedback Analysis
**Input:** Test results, build metrics
**Output:** `.context-foundry/learnings.json`
**Process:** NEW process
**Context:** ~10K tokens
**Prompt:** `tools/prompts/phase_feedback.txt`

### Phase 7.5: GitHub Integration (Issues, Actions, etc.)
**Input:** GitHub repo
**Output:** GitHub issues, Actions workflows
**Process:** NEW process
**Context:** ~8K tokens
**Prompt:** `tools/prompts/phase_github_integration.txt`

---

## Handoff Contract

Each phase follows this pattern:

```python
def run_phase(phase_name, phase_prompt_path, input_instruction, output_files):
    """
    Run a single phase with fresh context.

    Args:
        phase_name: e.g., "Scout", "Architect", "Builder"
        phase_prompt_path: Path to phase-specific prompt file
        input_instruction: What to tell the agent (e.g., "Read scout-report.md and create architecture")
        output_files: Expected output files to verify

    Returns:
        dict with status, duration, context_tokens, exit_code
    """

    # Load phase-specific prompt
    with open(phase_prompt_path) as f:
        phase_prompt = f.read()

    # Build command
    cmd = [
        "claude",
        "--print",
        "--permission-mode", "bypassPermissions",
        "--strict-mcp-config",
        "--settings", '{"thinkingMode": "off"}',
        "--system-prompt", phase_prompt,
        input_instruction
    ]

    # Track start time
    start = datetime.now()

    # Run phase (BLOCKS until complete)
    result = subprocess.run(
        cmd,
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=phase_timeout,
        env=process_env
    )

    # Track end time
    duration = (datetime.now() - start).total_seconds()

    # Verify output files exist
    for file_path in output_files:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Phase {phase_name} failed to create {file_path}")

    # Estimate context usage from output
    context_tokens = estimate_context_tokens(result.stdout, result.stderr)

    # Log metrics
    log_phase_metrics(phase_name, duration, context_tokens)

    # Process EXITS here → context released
    return {
        "phase": phase_name,
        "status": "completed" if result.returncode == 0 else "failed",
        "duration_seconds": duration,
        "context_tokens": context_tokens,
        "exit_code": result.returncode,
        "stdout_lines": len(result.stdout.splitlines()),
        "stderr_lines": len(result.stderr.splitlines())
    }
```

---

## Sequential Phase Execution

```python
def autonomous_build_with_phase_processes(task, working_directory, config):
    """
    Execute autonomous build with per-phase process spawning.

    Each phase gets a fresh context window.
    """

    results = {}

    # Phase 0: Codebase Analysis (if enhancement mode)
    if config.mode != "new_project":
        results["codebase_analysis"] = run_phase(
            "Codebase Analysis",
            "tools/prompts/phase_codebase_analysis.txt",
            f"Analyze existing codebase in {working_directory}",
            [".context-foundry/codebase-analysis.md"]
        )

    # Phase 1: Scout
    scout_input = task
    if "codebase_analysis" in results:
        scout_input += "\n\nRead .context-foundry/codebase-analysis.md for context."

    results["scout"] = run_phase(
        "Scout",
        "tools/prompts/phase_scout.txt",
        scout_input,
        [".context-foundry/scout-report.md"]
    )

    # Phase 2: Architect
    results["architect"] = run_phase(
        "Architect",
        "tools/prompts/phase_architect.txt",
        "Read .context-foundry/scout-report.md and create architecture.md",
        [".context-foundry/architecture.md"]
    )

    # Phase 2.5: Builder (with optional parallel sub-builders)
    results["builder"] = run_builder_phase(
        "tools/prompts/phase_builder.txt",
        "Read .context-foundry/architecture.md and implement the project",
        config.use_parallel_builders
    )

    # Phase 3.5: Integration Pre-Check (optional fast validation)
    if config.enable_precheck:
        results["precheck"] = run_phase(
            "Integration Pre-Check",
            "tools/prompts/phase_precheck.txt",
            "Run fast integration validation checks",
            [".context-foundry/precheck-results.txt"]
        )

    # Phase 4: Test (with self-healing loop)
    test_iteration = 0
    while test_iteration < config.max_test_iterations:
        results[f"test_{test_iteration}"] = run_phase(
            "Test",
            "tools/prompts/phase_test.txt",
            "Run all tests and report results",
            [".context-foundry/test-report.md"]
        )

        if tests_passed(results[f"test_{test_iteration}"]):
            break

        # Tests failed - go back to Architect to fix
        test_iteration += 1
        if test_iteration < config.max_test_iterations:
            results[f"architect_fix_{test_iteration}"] = run_phase(
                "Architect",
                "tools/prompts/phase_architect.txt",
                f"Read test-report.md and architecture.md. Fix failing tests. Iteration {test_iteration}",
                [".context-foundry/architecture-fix.md"]
            )

            results[f"builder_fix_{test_iteration}"] = run_builder_phase(
                "tools/prompts/phase_builder.txt",
                f"Read architecture-fix.md and fix the implementation. Iteration {test_iteration}",
                use_parallel=False  # Fixes are usually small, no need for parallel
            )

    # Phase 4.5: Screenshot (if web app)
    if config.capture_screenshots:
        results["screenshot"] = run_phase(
            "Screenshot",
            "tools/prompts/phase_screenshot.txt",
            "Start app and capture screenshots",
            ["docs/screenshots/"]
        )

    # Phase 5: Documentation
    results["documentation"] = run_phase(
        "Documentation",
        "tools/prompts/phase_documentation.txt",
        "Create comprehensive documentation",
        ["README.md", "docs/"]
    )

    # Phase 6: Deployment
    if config.deploy_to_github:
        results["deploy"] = run_phase(
            "Deployment",
            "tools/prompts/phase_deploy.txt",
            f"Deploy to GitHub as {config.github_repo_name}",
            []  # No local files, just GitHub operations
        )

    # Phase 7: Feedback Analysis
    results["feedback"] = run_phase(
        "Feedback",
        "tools/prompts/phase_feedback.txt",
        "Analyze build results and extract learnings",
        [".context-foundry/learnings.json"]
    )

    # Phase 7.5: GitHub Integration
    if config.deploy_to_github and config.setup_github_features:
        results["github_integration"] = run_phase(
            "GitHub Integration",
            "tools/prompts/phase_github_integration.txt",
            "Set up GitHub issues, Actions, etc.",
            []
        )

    return results
```

---

## Parallel Builder Implementation

Phase 2.5 (Builder) can optionally spawn parallel sub-builders:

```python
def run_builder_phase(prompt_path, instruction, use_parallel):
    """
    Run builder phase with optional parallel sub-builders.

    This is WITHIN-phase parallelization.
    The main builder process spawns sub-builders for independent tasks.
    """

    if not use_parallel:
        # Simple sequential build
        return run_phase(
            "Builder",
            prompt_path,
            instruction,
            []  # Source files vary, validated differently
        )

    # Parallel build:
    # 1. Main builder creates build-tasks.json
    main_builder_cmd = [
        "claude", "--print",
        "--system-prompt", load_prompt(prompt_path),
        instruction + "\n\nCreate .context-foundry/build-tasks.json with parallel task breakdown."
    ]

    subprocess.run(main_builder_cmd, cwd=working_directory)

    # 2. Load build tasks
    with open(".context-foundry/build-tasks.json") as f:
        build_plan = json.load(f)

    if not build_plan.get("parallel_mode"):
        # Architect decided parallel not beneficial
        return run_phase("Builder", prompt_path, instruction, [])

    # 3. Group tasks by dependency level
    task_levels = topological_sort(build_plan["tasks"])

    # 4. Execute each level in parallel
    for level_num, level_tasks in enumerate(task_levels):
        processes = []

        for task in level_tasks:
            # Spawn a NEW builder for this task
            builder_task_cmd = [
                "claude", "--print",
                "--system-prompt", load_prompt("tools/prompts/builder_task_prompt.txt"),
                f"TASK_ID: {task['id']} | FILES: {', '.join(task['files'])} | "
                f"DESCRIPTION: {task['description']}"
            ]

            log_file = f".context-foundry/builder-logs/task-{task['id']}.log"
            proc = subprocess.Popen(
                builder_task_cmd,
                cwd=working_directory,
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT
            )
            processes.append((task['id'], proc))

        # Wait for all tasks in this level
        for task_id, proc in processes:
            proc.wait()

            # Verify task completed
            done_file = f".context-foundry/builder-logs/task-{task_id}.done"
            if not Path(done_file).exists():
                raise RuntimeError(f"Task {task_id} failed to complete")

    return {
        "phase": "Builder",
        "status": "completed",
        "parallel_mode": True,
        "total_tasks": len(build_plan["tasks"]),
        "levels": len(task_levels)
    }
```

---

## Prompt Structure

Each phase prompt should have this structure:

```
═══════════════════════════════════════════════
PHASE: {PHASE_NAME}
═══════════════════════════════════════════════

YOU ARE A SPECIALIZED {PHASE_NAME} AGENT

Mission: {specific phase mission}

═══════════════════════════════════════════════
HANDOFF CONTRACT
═══════════════════════════════════════════════

**INPUT:**
- Read: {specific .md file from previous phase}
- Parse: {what to extract from input}

**OUTPUT:**
- Write: {specific .md file for next phase}
- Format: {expected structure}

**CONSTRAINTS:**
- Context budget: {X}K tokens (stay in SMART ZONE 0-40%)
- Duration: {Y} minutes typical
- Focus: {narrow scope, no other phases' work}

═══════════════════════════════════════════════
PHASE INSTRUCTIONS
═══════════════════════════════════════════════

{Phase-specific instructions here}

═══════════════════════════════════════════════
BAML PHASE TRACKING
═══════════════════════════════════════════════

**START of phase:**
```bash
python3 tools/use_baml.py update-phase \
  "{PHASE_NAME}" \
  "{starting_status}" \
  "Starting {PHASE_NAME} phase" \
  --session-id "{project_name}" \
  > .context-foundry/current-phase.json
```

**END of phase:**
```bash
python3 tools/use_baml.py update-phase \
  "{PHASE_NAME}" \
  "completed" \
  "Completed {PHASE_NAME} phase" \
  --session-id "{project_name}" \
  > .context-foundry/current-phase.json
```

═══════════════════════════════════════════════
COMPLETION CRITERIA
═══════════════════════════════════════════════

1. {criterion 1}
2. {criterion 2}
3. Write {output_file}
4. Update phase tracking to "completed"
5. EXIT (your process will terminate, releasing context)

```

---

## Benefits of This Architecture

### 1. Scalability
- **Unlimited project complexity:** Each phase stays <55K tokens
- **No accumulation:** Context released after each phase
- **All agents in SMART ZONE:** 0-40% context (optimal quality)

### 2. Quality
- **Focused agents:** Each phase sees ONLY relevant input
- **No noise:** Previous phases' execution not visible
- **Clean contracts:** Explicit .md handoff files

### 3. Performance
- **No context bloat:** 55K peak vs 100K+ accumulated
- **Faster execution:** Less token processing per phase
- **Parallelization works:** Can spawn sub-builders without parent context

### 4. Observability
- **Per-phase metrics:** Track each phase independently
- **Clear failure points:** Know exactly which phase failed
- **Context budgets:** Measure actual vs expected per phase

### 5. Maintainability
- **Modular prompts:** Edit one phase without affecting others
- **Testable:** Can test individual phases in isolation
- **Debuggable:** Clear separation of concerns

---

## Migration Path

### Step 1: Create Phase Prompts
Extract phase instructions from `orchestrator_prompt.txt` into separate files:
- `tools/prompts/phase_codebase_analysis.txt`
- `tools/prompts/phase_scout.txt`
- `tools/prompts/phase_architect.txt`
- `tools/prompts/phase_builder.txt`
- `tools/prompts/phase_precheck.txt`
- `tools/prompts/phase_test.txt`
- `tools/prompts/phase_screenshot.txt`
- `tools/prompts/phase_documentation.txt`
- `tools/prompts/phase_deploy.txt`
- `tools/prompts/phase_feedback.txt`
- `tools/prompts/phase_github_integration.txt`

### Step 2: Rewrite autonomous_build.py
Replace single `subprocess.Popen()` with sequential `run_phase()` calls.

### Step 3: Add Phase Execution Function
Implement `run_phase()` helper that spawns process, waits, tracks metrics.

### Step 4: Preserve Existing Features
- BAML integration (each phase calls `update-phase`)
- Incremental builds (cache scout reports, reuse test results)
- Self-healing test loop (if tests fail, loop Architect → Builder → Test)
- Pattern learning (Feedback phase extracts learnings)
- Flowise extension (Builder phase checks flowise_flow flag)

### Step 5: Update Documentation
- Update `PARALLEL_AGENTS_ARCHITECTURE.md` to describe new system
- Update `BAML_INTEGRATION.md` with per-phase tracking
- Update `CONTRIBUTING.md` with phase prompt editing guide

### Step 6: Test
- Small project (2-5 files): Verify all phases complete, context <10K each
- Medium project (10-20 files): Verify parallel builders work, context <55K peak
- Large project (30+ files): Verify no timeout, all phases in SMART ZONE

---

## Success Criteria

✅ Each phase spawns as NEW process (verify with `ps aux` monitoring)
✅ Each phase exits (no accumulation, verify process count returns to 1)
✅ All phases stay in SMART ZONE (0-40% of 200K context)
✅ Peak context: ~55K tokens (Builder phase only)
✅ Handoff files created and consumed correctly
✅ Parallel builders still work (within-phase parallelization)
✅ Self-healing test loop still works
✅ Large projects complete without timeout
✅ Build quality improves (agents not in DUMB/CRITICAL zones)

---

## Next Steps

1. **Create specialized phase prompts** - Extract from orchestrator_prompt.txt
2. **Implement run_phase() function** - Core subprocess.run() wrapper
3. **Rewrite autonomous_build.py** - Sequential phase execution
4. **Test with small project** - Validate architecture
5. **Test with large project** - Verify scalability
6. **Update documentation** - Reflect new architecture

---

**Status:** Ready for implementation
**Priority:** CRITICAL - Fixes catastrophic architectural failure
**Estimated effort:** 4-6 hours implementation + 2-4 hours testing

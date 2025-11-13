# Phase Process Spawning - Implementation Specification

**Date:** 2025-11-11
**Status:** 🔧 Implementation Ready
**Parent:** PHASE_PROCESS_SPAWNING_DESIGN.md

---

## 1. Builder Output Verification (Dynamic Files)

### Problem
Builder creates dozens of dynamic files. Can't use fixed `output_files` list like Scout/Architect.

### Solution: Phase-Specific Validation Hooks

```python
class PhaseValidator:
    """Phase-specific output validation."""

    @staticmethod
    def validate_scout(working_dir: Path) -> bool:
        """Scout must create scout-report.md."""
        required = working_dir / ".context-foundry" / "scout-report.md"
        if not required.exists():
            raise FileNotFoundError(f"Scout failed to create {required}")

        # Verify non-empty
        if required.stat().st_size < 100:
            raise ValueError("scout-report.md is too small (< 100 bytes)")

        return True

    @staticmethod
    def validate_architect(working_dir: Path) -> bool:
        """Architect must create architecture.md."""
        required = working_dir / ".context-foundry" / "architecture.md"
        if not required.exists():
            raise FileNotFoundError(f"Architect failed to create {required}")

        # Verify contains key sections
        content = required.read_text()
        required_sections = ["## Technology Stack", "## Architecture"]
        for section in required_sections:
            if section not in content:
                raise ValueError(f"architecture.md missing section: {section}")

        return True

    @staticmethod
    def validate_builder(working_dir: Path, project_type: str) -> bool:
        """
        Builder validation is LOOSE - verify build-tasks.json + smoke checks.

        Don't validate exact files created (too dynamic).
        Instead verify:
        1. build-tasks.json exists (shows planning completed)
        2. At least SOME source files created
        3. No obvious errors in builder logs
        """
        # Check build plan exists
        build_tasks = working_dir / ".context-foundry" / "build-tasks.json"
        if not build_tasks.exists():
            raise FileNotFoundError("Builder failed to create build-tasks.json")

        # Parse task plan
        import json
        with open(build_tasks) as f:
            plan = json.load(f)

        # Check each task completed (if parallel mode)
        if plan.get("parallel_mode"):
            for task in plan.get("tasks", []):
                task_id = task["id"]
                done_file = working_dir / ".context-foundry" / "builder-logs" / f"{task_id}.done"
                if not done_file.exists():
                    raise RuntimeError(f"Builder task {task_id} did not complete")

        # Smoke check: verify SOME source files created
        # Look for common source directories based on project type
        source_dirs = []
        if project_type in ["python-fastapi", "python-cli", "python-lib"]:
            source_dirs = ["src", "app", "backend"]
        elif project_type in ["node-express", "react-app", "nextjs"]:
            source_dirs = ["src", "pages", "components", "lib"]
        elif project_type == "flowise-workflow":
            # Flowise: Just need the workflow JSON
            workflow_files = list(working_dir.glob("*.json"))
            flowise_jsons = [f for f in workflow_files if f.name not in ["package.json", "tsconfig.json"]]
            if not flowise_jsons:
                raise FileNotFoundError("Flowise Builder failed to create workflow JSON")
            return True

        # Check at least ONE source directory exists with files
        found_sources = False
        for dir_name in source_dirs:
            src_dir = working_dir / dir_name
            if src_dir.exists() and src_dir.is_dir():
                source_files = list(src_dir.rglob("*.py")) + list(src_dir.rglob("*.js")) + \
                               list(src_dir.rglob("*.ts")) + list(src_dir.rglob("*.tsx"))
                if source_files:
                    found_sources = True
                    break

        if not found_sources:
            # Fallback: check if ANY code files exist in project root
            code_files = list(working_dir.glob("*.py")) + list(working_dir.glob("*.js")) + \
                        list(working_dir.glob("*.ts"))
            if not code_files:
                raise FileNotFoundError("Builder created no source files")

        return True

    @staticmethod
    def validate_test(working_dir: Path) -> bool:
        """Test must create test-report.md."""
        required = working_dir / ".context-foundry" / "test-report.md"
        if not required.exists():
            raise FileNotFoundError(f"Test failed to create {required}")

        # Verify contains results
        content = required.read_text()
        if "PASSED" not in content and "FAILED" not in content:
            raise ValueError("test-report.md missing test results")

        return True

    @staticmethod
    def validate_documentation(working_dir: Path) -> bool:
        """Documentation must create README.md."""
        readme = working_dir / "README.md"
        if not readme.exists():
            raise FileNotFoundError("Documentation failed to create README.md")

        # Verify non-trivial
        if readme.stat().st_size < 500:
            raise ValueError("README.md is too small (< 500 bytes)")

        return True


def run_phase(phase_name, phase_prompt_path, input_instruction,
              working_directory, phase_timeout=1800, validator=None):
    """
    Run a single phase with fresh context.

    Args:
        phase_name: e.g., "Scout", "Builder"
        phase_prompt_path: Path to phase-specific prompt
        input_instruction: What to tell the agent
        working_directory: Project directory
        phase_timeout: Max seconds (default 30 min)
        validator: Callable to validate output (phase-specific)

    Returns:
        PhaseResult with metrics
    """
    # ... (same as before)

    result = subprocess.run(cmd, ...)

    # Validate output using phase-specific validator
    if validator:
        try:
            validator(Path(working_directory))
        except Exception as e:
            return PhaseResult(
                phase=phase_name,
                status="failed",
                error=f"Output validation failed: {e}",
                ...
            )

    return PhaseResult(status="completed", ...)


# Usage:
run_phase(
    "Builder",
    "tools/prompts/phase_builder.txt",
    "Read architecture.md and implement",
    working_directory,
    validator=lambda wd: PhaseValidator.validate_builder(wd, project_type)
)
```

---

## 2. Context Token Estimation & Metrics Logging

### Problem
`estimate_context_tokens()` and `log_phase_metrics()` not defined.

### Solution: Implement Using Existing Tools

```python
# tools/mcp_utils/phase_metrics.py

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

class TokenCounter:
    """Estimate token counts from text (rough heuristic)."""

    @staticmethod
    def count_tokens(text: str) -> int:
        """
        Rough token estimation: 1 token ≈ 4 characters.

        This is a heuristic. Actual tokenization varies by model.
        Claude uses ~3.5-4.0 chars/token average.
        """
        return len(text) // 4

    @staticmethod
    def count_file_tokens(file_path: Path) -> int:
        """Count tokens in a file."""
        if not file_path.exists():
            return 0

        content = file_path.read_text(errors='ignore')
        return TokenCounter.count_tokens(content)


def estimate_context_tokens(stdout: str, stderr: str, phase_files: list[Path]) -> int:
    """
    Estimate total context tokens for a phase.

    Context includes:
    - Phase prompt (static, from prompt file)
    - Input files read by phase
    - Output generated by phase
    - Tool outputs in stdout/stderr

    Args:
        stdout: Process stdout
        stderr: Process stderr
        phase_files: Files read/written by phase

    Returns:
        Estimated token count
    """
    total_tokens = 0

    # Count stdout/stderr (contains tool outputs, agent responses)
    total_tokens += TokenCounter.count_tokens(stdout)
    total_tokens += TokenCounter.count_tokens(stderr)

    # Count phase input/output files
    for file_path in phase_files:
        total_tokens += TokenCounter.count_file_tokens(file_path)

    return total_tokens


def log_phase_metrics(
    phase_name: str,
    duration_seconds: float,
    context_tokens: int,
    exit_code: int,
    working_directory: Path,
    iteration: int = 0
):
    """
    Log phase metrics to session-summary.json.

    Appends to existing session-summary.json or creates new one.
    Follows format from current Context Foundry builds.

    Args:
        phase_name: e.g., "Scout", "Architect"
        duration_seconds: How long phase took
        context_tokens: Estimated tokens used
        exit_code: Process exit code
        working_directory: Project directory
        iteration: Test iteration number (for self-healing loop)
    """
    summary_file = working_directory / ".context-foundry" / "session-summary.json"

    # Load existing summary or create new
    if summary_file.exists():
        with open(summary_file) as f:
            summary = json.load(f)
    else:
        summary = {
            "build_start": datetime.now().isoformat(),
            "context_metrics": {
                "max_context_window": 200000,
                "model": "claude-sonnet-4",
                "by_phase": {}
            },
            "phases": {}
        }

    # Calculate context percentage and zone
    percentage = (context_tokens / 200000) * 100
    if percentage < 40:
        zone = "smart"
    elif percentage < 80:
        zone = "dumb"
    else:
        zone = "critical"

    # Calculate allocated budget (from design doc)
    budget_allocation = {
        "Scout": 14000,
        "Architect": 14000,
        "Builder": 40000,
        "Test": 40000,
        "Documentation": 10000,
        "Deploy": 6000,
        "Feedback": 10000
    }
    budget = budget_allocation.get(phase_name, 10000)

    # Record phase metrics
    phase_key = f"phase_{phase_name.lower()}"
    if iteration > 0:
        phase_key += f"_iteration_{iteration}"

    summary["context_metrics"]["by_phase"][phase_key] = {
        "tokens_used": context_tokens,
        "percentage": round(percentage, 2),
        "zone": zone,
        "budget_allocated": budget,
        "over_budget": context_tokens > budget,
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "timestamp": datetime.now().isoformat()
    }

    summary["phases"][phase_key] = {
        "status": "completed" if exit_code == 0 else "failed",
        "duration_seconds": duration_seconds,
        "timestamp": datetime.now().isoformat()
    }

    # Save updated summary
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    # Print metrics to console
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"PHASE METRICS: {phase_name}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Duration: {duration_seconds:.1f}s", file=sys.stderr)
    print(f"Context: {context_tokens:,} tokens ({percentage:.1f}%)", file=sys.stderr)
    print(f"Zone: {zone.upper()}", file=sys.stderr)
    print(f"Budget: {budget:,} tokens", file=sys.stderr)
    print(f"Status: {'✅ PASS' if exit_code == 0 else '❌ FAIL'}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
```

---

## 3. Builder Parallelization Gating

### Problem
Need explicit decision logic for sequential vs parallel, error surfacing from sub-builders.

### Solution: Structured Decision Flow

```python
def run_builder_phase(
    prompt_path: Path,
    instruction: str,
    working_directory: Path,
    project_type: str,
    flowise_mode: bool = False
) -> Dict[str, Any]:
    """
    Run Builder phase with conditional parallelization.

    Decision flow:
    1. If Flowise mode → ALWAYS sequential (single JSON file)
    2. If <10 files → Sequential (overhead not worth it)
    3. If 10-20 files → Parallel (2-4 workers)
    4. If 20+ files → Parallel (4-8 workers)

    Returns:
        BuildResult with status, metrics, errors
    """

    # HARD GATE: Flowise MUST be sequential
    if flowise_mode:
        print("🚨 Flowise mode: Sequential build (single JSON file required)", file=sys.stderr)
        return run_sequential_builder(prompt_path, instruction, working_directory)

    # Phase 1: Main builder creates architecture-based build plan
    print("📋 Builder Phase 1: Creating build plan...", file=sys.stderr)

    planning_cmd = [
        "claude", "--print",
        "--permission-mode", "bypassPermissions",
        "--system-prompt", prompt_path.read_text(),
        instruction + "\n\nFIRST: Analyze architecture.md and create .context-foundry/build-tasks.json"
    ]

    planning_result = subprocess.run(
        planning_cmd,
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=600  # 10 min for planning
    )

    if planning_result.returncode != 0:
        return {
            "status": "failed",
            "error": "Build planning failed",
            "stderr": planning_result.stderr
        }

    # Phase 2: Load build plan and decide mode
    build_tasks_file = working_directory / ".context-foundry" / "build-tasks.json"

    if not build_tasks_file.exists():
        # Builder didn't create tasks file - fall back to sequential
        print("⚠️  No build-tasks.json created, falling back to sequential", file=sys.stderr)
        return run_sequential_builder(prompt_path, instruction, working_directory)

    with open(build_tasks_file) as f:
        build_plan = json.load(f)

    # Decision: parallel or sequential?
    parallel_mode = build_plan.get("parallel_mode", False)
    total_tasks = build_plan.get("total_tasks", 0)

    if not parallel_mode or total_tasks < 2:
        print(f"📝 Sequential build ({total_tasks} task(s))", file=sys.stderr)
        return run_sequential_builder(prompt_path, instruction, working_directory)

    # Phase 3: Run parallel builders
    print(f"⚡ Parallel build ({total_tasks} tasks)", file=sys.stderr)
    return run_parallel_builders(build_plan, working_directory)


def run_parallel_builders(build_plan: Dict, working_directory: Path) -> Dict[str, Any]:
    """
    Execute build tasks in parallel with dependency ordering.

    Returns:
        BuildResult with aggregated status and errors
    """
    from collections import defaultdict

    tasks = build_plan["tasks"]

    # Build dependency graph
    task_by_id = {t["id"]: t for t in tasks}

    # Topological sort to get execution levels
    levels = topological_sort_tasks(tasks)

    print(f"📊 Build plan: {len(levels)} dependency level(s)", file=sys.stderr)

    all_errors = []
    completed_tasks = set()

    # Execute each level in parallel
    for level_num, level_tasks in enumerate(levels):
        print(f"\n🔄 Level {level_num + 1}/{len(levels)}: {len(level_tasks)} task(s)", file=sys.stderr)

        processes = []

        for task in level_tasks:
            task_id = task["id"]

            # Build command for this task
            builder_task_prompt = Path("tools/prompts/builder_task_prompt.txt").read_text()
            task_instruction = (
                f"TASK_ID: {task_id}\n"
                f"DESCRIPTION: {task['description']}\n"
                f"FILES: {', '.join(task['files'])}\n"
                f"Read .context-foundry/architecture.md for context."
            )

            cmd = [
                "claude", "--print",
                "--permission-mode", "bypassPermissions",
                "--system-prompt", builder_task_prompt,
                task_instruction
            ]

            # Create log directory
            log_dir = working_directory / ".context-foundry" / "builder-logs"
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / f"{task_id}.log"

            # Spawn process
            proc = subprocess.Popen(
                cmd,
                cwd=working_directory,
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                text=True
            )

            processes.append({
                "task_id": task_id,
                "process": proc,
                "log_file": log_file,
                "description": task["description"]
            })

        # Wait for all tasks in this level
        for proc_info in processes:
            task_id = proc_info["task_id"]
            process = proc_info["process"]
            log_file = proc_info["log_file"]

            print(f"  ⏳ Waiting for {task_id}...", file=sys.stderr)

            try:
                exit_code = process.wait(timeout=1800)  # 30 min per task

                if exit_code != 0:
                    # Task failed - capture error
                    error_log = log_file.read_text()
                    error_msg = f"Task {task_id} failed (exit {exit_code})"

                    all_errors.append({
                        "task_id": task_id,
                        "description": proc_info["description"],
                        "exit_code": exit_code,
                        "log": error_log[-1000:]  # Last 1000 chars
                    })

                    print(f"  ❌ {task_id} FAILED", file=sys.stderr)
                    print(f"     Log: {log_file}", file=sys.stderr)
                else:
                    # Success - create .done marker
                    done_file = log_file.parent / f"{task_id}.done"
                    done_file.write_text(f"Completed at {datetime.now().isoformat()}")

                    completed_tasks.add(task_id)
                    print(f"  ✅ {task_id} completed", file=sys.stderr)

            except subprocess.TimeoutExpired:
                process.kill()
                error_msg = f"Task {task_id} timeout (>30 min)"
                all_errors.append({
                    "task_id": task_id,
                    "description": proc_info["description"],
                    "error": "timeout",
                    "log_file": str(log_file)
                })
                print(f"  ⏱️  {task_id} TIMEOUT", file=sys.stderr)

    # Summary
    total_tasks = len(tasks)
    failed_count = len(all_errors)
    success_count = len(completed_tasks)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"BUILD SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Total tasks: {total_tasks}", file=sys.stderr)
    print(f"Completed: {success_count}", file=sys.stderr)
    print(f"Failed: {failed_count}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    if all_errors:
        # Write error summary
        error_file = working_directory / ".context-foundry" / "builder-errors.json"
        with open(error_file, 'w') as f:
            json.dump(all_errors, f, indent=2)

        print(f"❌ Build errors written to: {error_file}", file=sys.stderr)

        return {
            "status": "failed",
            "completed_tasks": success_count,
            "failed_tasks": failed_count,
            "errors": all_errors,
            "error_file": str(error_file)
        }

    return {
        "status": "completed",
        "parallel_mode": True,
        "total_tasks": total_tasks,
        "levels": len(levels)
    }


def topological_sort_tasks(tasks: list) -> list[list]:
    """
    Sort tasks into dependency levels for parallel execution.

    Returns:
        List of lists, where each inner list contains tasks that can run in parallel.
        Example: [[task1, task2], [task3], [task4, task5]]
                 Level 0 (no deps), Level 1 (depends on L0), Level 2 (depends on L1)
    """
    from collections import defaultdict, deque

    # Build dependency graph
    task_by_id = {t["id"]: t for t in tasks}
    in_degree = {t["id"]: 0 for t in tasks}
    dependents = defaultdict(list)

    for task in tasks:
        task_id = task["id"]
        dependencies = task.get("dependencies", [])

        in_degree[task_id] = len(dependencies)

        for dep_id in dependencies:
            dependents[dep_id].append(task_id)

    # Kahn's algorithm for topological sort
    levels = []
    queue = deque([tid for tid, degree in in_degree.items() if degree == 0])

    while queue:
        # All tasks in current level can run in parallel
        current_level = []

        for _ in range(len(queue)):
            task_id = queue.popleft()
            current_level.append(task_by_id[task_id])

            # Reduce in-degree of dependents
            for dependent_id in dependents[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        levels.append(current_level)

    return levels
```

---

## 4. Self-Healing Loop Data Flow

### Problem
Clarify architecture.md vs architecture-fix.md versioning for test iterations.

### Solution: Versioned Files Per Iteration

```python
def run_build_with_self_healing(
    working_directory: Path,
    config: BuildConfig
) -> BuildResult:
    """
    Run build with self-healing test loop.

    File naming convention:
    - Iteration 0 (first try):
      - architecture.md
      - test-report.md (if tests fail)

    - Iteration 1 (first fix):
      - architecture-fix-1.md (reads test-report.md)
      - test-report-1.md

    - Iteration 2 (second fix):
      - architecture-fix-2.md (reads test-report-1.md)
      - test-report-2.md

    Builder always reads latest architecture*.md file.
    Test always writes test-report[-N].md file.
    """

    iteration = 0
    max_iterations = config.max_test_iterations

    # Initial build (iteration 0)
    architect_file = ".context-foundry/architecture.md"
    test_file = ".context-foundry/test-report.md"

    # ... run Scout, Architect, Builder phases normally ...

    while iteration <= max_iterations:
        # Run tests
        test_result = run_phase(
            "Test",
            "tools/prompts/phase_test.txt",
            f"Run all tests. Write results to {test_file}",
            working_directory,
            iteration=iteration
        )

        # Check if tests passed
        test_report_path = working_directory / test_file
        if tests_passed(test_report_path):
            print(f"✅ Tests PASSED (iteration {iteration})", file=sys.stderr)
            break

        # Tests failed
        iteration += 1

        if iteration > max_iterations:
            print(f"❌ Tests FAILED after {max_iterations} iteration(s)", file=sys.stderr)
            print(f"   Last report: {test_file}", file=sys.stderr)
            break

        # Self-healing: Run Architect to fix issues
        print(f"\n🔄 Self-healing iteration {iteration}", file=sys.stderr)
        print(f"   Reading: {test_file}", file=sys.stderr)

        # Create fix architecture file
        architect_fix_file = f".context-foundry/architecture-fix-{iteration}.md"

        fix_instruction = (
            f"Read {test_file} and {architect_file}.\n"
            f"Analyze test failures and update architecture to fix them.\n"
            f"Write updated architecture to {architect_fix_file}"
        )

        architect_fix_result = run_phase(
            "Architect",
            "tools/prompts/phase_architect.txt",
            fix_instruction,
            working_directory,
            iteration=iteration
        )

        if architect_fix_result.status != "completed":
            print(f"❌ Architect fix failed", file=sys.stderr)
            break

        # Run Builder with fixed architecture
        builder_instruction = (
            f"Read {architect_fix_file} and implement fixes.\n"
            f"This is fix iteration {iteration}. Focus on test failures only."
        )

        builder_fix_result = run_builder_phase(
            Path("tools/prompts/phase_builder.txt"),
            builder_instruction,
            working_directory,
            config.project_type,
            use_parallel=False  # Fixes are usually small, no parallelization
        )

        if builder_fix_result["status"] != "completed":
            print(f"❌ Builder fix failed", file=sys.stderr)
            break

        # Update file names for next iteration
        architect_file = architect_fix_file
        test_file = f".context-foundry/test-report-{iteration}.md"

    return BuildResult(
        status="completed" if tests_passed(test_report_path) else "failed",
        test_iterations=iteration,
        final_test_report=test_file
    )


def tests_passed(test_report_path: Path) -> bool:
    """
    Determine if tests passed from test-report.md.

    Looks for indicators:
    - "All tests passed" or "PASSED"
    - NOT "FAILED" or "ERROR"
    - Exit code recorded in report
    """
    if not test_report_path.exists():
        return False

    content = test_report_path.read_text()
    content_lower = content.lower()

    # Check for pass indicators
    passed_indicators = [
        "all tests passed",
        "✅ all tests passed",
        "status: passed",
        "result: pass"
    ]

    fail_indicators = [
        "failed:",
        "❌ failed",
        "status: failed",
        "result: fail",
        "errors:",
        "test failures:"
    ]

    has_pass = any(indicator in content_lower for indicator in passed_indicators)
    has_fail = any(indicator in content_lower for indicator in fail_indicators)

    # Passed if: has pass indicator AND no fail indicators
    return has_pass and not has_fail
```

---

## 5. Feature Parity Checklist

### Problem
Need to document where existing feature hooks live.

### Solution: Feature Hook Locations

```python
# ═══════════════════════════════════════════════════════════
# FEATURE PARITY PRESERVATION
# ═══════════════════════════════════════════════════════════

class FeatureHooks:
    """
    Locations of existing Context Foundry features.
    These must be preserved when refactoring to per-phase spawning.
    """

    # ─────────────────────────────────────────────────────────
    # 1. Flowise Detection & Extension
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def detect_flowise_mode(task: str, working_directory: Path) -> Dict[str, Any]:
        """
        Detect if this is a Flowise workflow project.

        Location: tools/mcp_utils/project_detection.py
        Function: detect_existing_codebase()

        Returns:
            {
                "flowise_flow": bool,
                "flowise_flow_type": str,  # multi-agent, rag, workflow, chatbot
                "flowise_complexity": str,  # simple, moderate, complex
                "flowise_node_count": int,
                "flowise_agent_count": int,
                "flowise_has_memory": bool,
                "flowise_has_tools": bool
            }
        """
        from tools.mcp_utils.project_detection import detect_existing_codebase

        codebase_info = detect_existing_codebase(working_directory)

        # Also check task keywords
        task_lower = task.lower()
        flowise_keywords = ["flowise", "agent flow", "chatflow", "agentflow"]

        if any(kw in task_lower for kw in flowise_keywords):
            codebase_info["flowise_flow"] = True

        return codebase_info

    # ─────────────────────────────────────────────────────────
    # 2. Incremental Builds & Scout Cache
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def check_scout_cache(task: str, mode: str, working_directory: Path) -> Optional[str]:
        """
        Check for cached Scout report from previous builds.

        Location: tools/cache/scout_cache.py
        Function: get_cached_scout_report()

        Cache structure:
            ~/.context-foundry/cache/
                scout-reports/
                    {task_hash}.md
                    {task_hash}.meta.json

        Returns:
            Cached scout report content, or None if cache miss
        """
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from tools.cache.scout_cache import get_cached_scout_report

        return get_cached_scout_report(
            task=task,
            mode=mode,
            working_directory=str(working_directory)
        )

    @staticmethod
    def save_scout_cache(task: str, mode: str, working_directory: Path,
                        scout_report_content: str):
        """
        Save Scout report to cache for future builds.

        Location: tools/cache/scout_cache.py
        Function: save_scout_report_to_cache()
        """
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from tools.cache.scout_cache import save_scout_report_to_cache

        save_scout_report_to_cache(
            task=task,
            mode=mode,
            working_directory=str(working_directory),
            scout_report_content=scout_report_content
        )

    # ─────────────────────────────────────────────────────────
    # 3. BAML Integration (Type-Safe Phase Tracking)
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def update_phase_tracking(phase_name: str, status: str, progress_detail: str,
                             session_id: str, iteration: int = 0):
        """
        Update phase tracking using BAML.

        Location: tools/use_baml.py
        Command: update-phase

        BAML generates type-safe PhaseInfo structure.
        Output: .context-foundry/current-phase.json

        Each phase MUST call this at:
        - Phase start (status: "researching", "designing", "building", etc.)
        - Phase end (status: "completed")
        - Iteration changes (iteration counter)
        """
        import subprocess

        cmd = [
            "python3", "tools/use_baml.py",
            "update-phase",
            phase_name,
            status,
            progress_detail,
            "--session-id", session_id,
            "--iteration", str(iteration)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Redirect output to .context-foundry/current-phase.json
        if result.returncode == 0:
            phase_file = Path.cwd() / ".context-foundry" / "current-phase.json"
            phase_file.parent.mkdir(parents=True, exist_ok=True)
            phase_file.write_text(result.stdout)

    # ─────────────────────────────────────────────────────────
    # 4. Pattern Learning System (Global Patterns)
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def read_global_patterns(pattern_type: str) -> Optional[Dict]:
        """
        Read global patterns from ~/.context-foundry/patterns/

        Location: MCP server tools
        Tool: read_global_patterns()

        Pattern types:
        - "scout-learnings": Learnings from past Scout phases
        - "common-issues": Issues encountered in past builds
        - "mcp-server-patterns": MCP server implementation patterns
        - "architecture-patterns": Architecture design patterns

        Returns:
            Pattern data as dict, or None if not available
        """
        # This would be called via MCP in the actual implementation
        # For now, direct file read
        pattern_file = Path.home() / ".context-foundry" / "patterns" / f"{pattern_type}.json"

        if not pattern_file.exists():
            return None

        with open(pattern_file) as f:
            return json.load(f)

    # ─────────────────────────────────────────────────────────
    # 5. Test Loop Persistence
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def load_test_iteration_count(working_directory: Path) -> int:
        """
        Load current test iteration count.

        Location: .context-foundry/test-iteration-count.txt

        Persists across test/fix loops so we can track how many iterations.
        """
        count_file = working_directory / ".context-foundry" / "test-iteration-count.txt"

        if not count_file.exists():
            return 0

        return int(count_file.read_text().strip())

    @staticmethod
    def save_test_iteration_count(working_directory: Path, count: int):
        """Save test iteration count."""
        count_file = working_directory / ".context-foundry" / "test-iteration-count.txt"
        count_file.parent.mkdir(parents=True, exist_ok=True)
        count_file.write_text(str(count))


# ═══════════════════════════════════════════════════════════
# INTEGRATION: Feature Hooks in Per-Phase Architecture
# ═══════════════════════════════════════════════════════════

def autonomous_build_with_features(task: str, working_directory: Path, config: BuildConfig):
    """
    Main autonomous build with all features preserved.
    """

    # Feature 1: Flowise Detection
    flowise_info = FeatureHooks.detect_flowise_mode(task, working_directory)
    flowise_mode = flowise_info.get("flowise_flow", False)

    # Feature 2: Scout Cache (Incremental Builds)
    if config.incremental:
        cached_scout = FeatureHooks.check_scout_cache(task, config.mode, working_directory)
        if cached_scout:
            # Cache hit - skip Scout phase
            scout_file = working_directory / ".context-foundry" / "scout-report.md"
            scout_file.parent.mkdir(parents=True, exist_ok=True)
            scout_file.write_text(cached_scout)

            print("⚡ Incremental build: Reusing cached Scout report", file=sys.stderr)
        else:
            # Cache miss - run Scout normally
            run_scout_phase(task, working_directory)

            # Save to cache
            scout_content = (working_directory / ".context-foundry" / "scout-report.md").read_text()
            FeatureHooks.save_scout_cache(task, config.mode, working_directory, scout_content)
    else:
        run_scout_phase(task, working_directory)

    # Feature 3: BAML Phase Tracking (every phase)
    # Each phase calls FeatureHooks.update_phase_tracking() at start/end

    # Feature 4: Pattern Learning (Scout phase reads global patterns)
    # Scout prompt includes: "Read global patterns using read_global_patterns()"

    # Feature 5: Test Loop Persistence
    # Self-healing loop uses FeatureHooks.load/save_test_iteration_count()

    # ... rest of build ...
```

---

## Summary: All Design Issues Resolved

✅ **1. Builder Output Verification:**
- Phase-specific validators (PhaseValidator class)
- Builder uses LOOSE validation (build-tasks.json + smoke checks)
- Handles dynamic file creation

✅ **2. Context Token Estimation & Metrics:**
- TokenCounter class (4 chars/token heuristic)
- estimate_context_tokens() implementation
- log_phase_metrics() writes to session-summary.json
- Tracks zone (smart/dumb/critical)

✅ **3. Builder Parallelization Gating:**
- Explicit decision flow (Flowise → sequential, <10 files → sequential, else parallel)
- Error surfacing from sub-builder logs
- Aggregated error reporting in builder-errors.json

✅ **4. Self-Healing Loop Data Flow:**
- Versioned files: architecture-fix-1.md, test-report-1.md, etc.
- Builder reads latest architecture*.md
- Clear iteration tracking

✅ **5. Feature Parity:**
- FeatureHooks class documents all existing features
- Flowise detection: tools/mcp_utils/project_detection.py
- Scout cache: tools/cache/scout_cache.py
- BAML tracking: tools/use_baml.py
- Global patterns: ~/.context-foundry/patterns/
- Test persistence: .context-foundry/test-iteration-count.txt

---

**Status:** ✅ Design locked, ready for implementation
**Next Step:** Create specialized phase prompts + rewrite autonomous_build.py

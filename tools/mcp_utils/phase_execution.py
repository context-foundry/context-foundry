"""
Phase Execution - Per-phase process spawning with fresh contexts.

Implements:
- PhaseValidator: Phase-specific output validation
- run_phase(): Core phase runner with subprocess.run()
- run_builder_phase(): Builder with parallelization support
- tests_passed(): Test result parser
- BAML-enforced phase tracking
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from tools.mcp_utils.phase_metrics import estimate_context_tokens, log_phase_metrics

# Import BAML integration
from tools.baml_integration import (
    is_baml_available,
    update_phase_with_baml,
    get_baml_error,
)


@dataclass
class PhaseResult:
    """Result from running a phase."""

    phase: str
    status: str  # "completed" or "failed"
    duration_seconds: float
    context_tokens: int
    exit_code: int
    error: Optional[str] = None
    stdout_lines: int = 0
    stderr_lines: int = 0


class PhaseValidator:
    """Phase-specific output validation."""

    @staticmethod
    def validate_baml_tracking(working_dir: Path, phase_name: str) -> bool:
        """
        Verify BAML phase tracking occurred.

        Checks that current-phase.json exists and contains expected phase.
        This is a soft validation - warns but doesn't fail the build.

        Args:
            working_dir: Project directory
            phase_name: Expected phase name

        Returns:
            True if tracking exists, False otherwise
        """
        phase_file = working_dir / ".context-foundry" / "current-phase.json"

        if not phase_file.exists():
            print(
                "⚠️  BAML tracking missing: current-phase.json not found",
                file=sys.stderr,
            )
            return False

        try:
            with open(phase_file) as f:
                phase_data = json.load(f)

            if phase_data.get("phase") != phase_name:
                print(
                    f"⚠️  BAML tracking mismatch: expected {phase_name}, got {phase_data.get('phase')}",
                    file=sys.stderr,
                )
                return False

            print(
                f"✅ BAML tracking verified: {phase_name} tracked correctly",
                file=sys.stderr,
            )
            return True

        except Exception as e:
            print(f"⚠️  BAML tracking verification failed: {e}", file=sys.stderr)
            return False

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

        # Check for Technology Stack (required)
        if "## Technology Stack" not in content:
            raise ValueError("architecture.md missing section: ## Technology Stack")

        # Check for Architecture section (accept variations)
        if "## Architecture" not in content and "## System Architecture" not in content:
            raise ValueError(
                "architecture.md missing section: ## Architecture or ## System Architecture"
            )

        return True

    @staticmethod
    def validate_builder(working_dir: Path, project_type: str = "unknown") -> bool:
        """
        Builder validation is LOOSE - verify build-tasks.json + smoke checks.

        Don't validate exact files (too dynamic). Instead:
        1. build-tasks.json exists
        2. At least SOME source files created
        3. No obvious errors in builder logs
        """
        # Check build plan exists
        build_tasks = working_dir / ".context-foundry" / "build-tasks.json"
        if not build_tasks.exists():
            raise FileNotFoundError("Builder failed to create build-tasks.json")

        # Parse task plan
        with open(build_tasks) as f:
            plan = json.load(f)

        # Check each task completed (if parallel mode)
        if plan.get("parallel_mode"):
            for task in plan.get("tasks", []):
                task_id = task["id"]
                done_file = (
                    working_dir
                    / ".context-foundry"
                    / "builder-logs"
                    / f"{task_id}.done"
                )
                if not done_file.exists():
                    raise RuntimeError(f"Builder task {task_id} did not complete")

        # Smoke check: verify SOME source files created
        # Handle None project_type
        if project_type is None:
            project_type = "unknown"

        source_dirs = []
        if "python" in project_type.lower():
            source_dirs = ["src", "app", "backend"]
        elif "node" in project_type.lower() or "react" in project_type.lower():
            source_dirs = ["src", "pages", "components", "lib"]
        elif "flowise" in project_type.lower():
            # Flowise: Just need the workflow JSON
            workflow_files = list(working_dir.glob("*.json"))
            flowise_jsons = [
                f
                for f in workflow_files
                if f.name not in ["package.json", "tsconfig.json"]
            ]
            if not flowise_jsons:
                raise FileNotFoundError(
                    "Flowise Builder failed to create workflow JSON"
                )
            return True

        # Check at least ONE source directory exists with files
        found_sources = False
        for dir_name in source_dirs:
            src_dir = working_dir / dir_name
            if src_dir.exists() and src_dir.is_dir():
                source_files = (
                    list(src_dir.rglob("*.py"))
                    + list(src_dir.rglob("*.js"))
                    + list(src_dir.rglob("*.ts"))
                    + list(src_dir.rglob("*.tsx"))
                )
                if source_files:
                    found_sources = True
                    break

        if not found_sources:
            # Fallback: recursively check ENTIRE project for code files
            code_files = (
                list(working_dir.rglob("*.py"))
                + list(working_dir.rglob("*.js"))
                + list(working_dir.rglob("*.ts"))
                + list(working_dir.rglob("*.tsx"))
            )
            # Exclude common non-source directories
            code_files = [
                f
                for f in code_files
                if not any(
                    part in f.parts
                    for part in [
                        ".context-foundry",
                        "__pycache__",
                        "node_modules",
                        ".git",
                        "venv",
                        ".venv",
                    ]
                )
            ]
            if not code_files:
                raise FileNotFoundError("Builder created no source files")

        return True

    @staticmethod
    def validate_test(working_dir: Path, iteration: int = 0) -> bool:
        """
        Test must create test-report.md (or test-report-N.md for iterations).

        NOTE: For self-healing loops, use _validate_test_with_filename() instead,
        which takes the exact filename. This method is for backwards compatibility.

        Args:
            working_dir: Project directory
            iteration: Test iteration number (0 = test-report.md, N = test-report-N.md)
        """
        # Iteration-aware filename
        test_filename = f"test-report{'-' + str(iteration) if iteration > 0 else ''}.md"
        required = working_dir / ".context-foundry" / test_filename

        if not required.exists():
            raise FileNotFoundError(f"Test failed to create {required}")

        # Verify contains results
        content = required.read_text()
        if "PASSED" not in content and "FAILED" not in content:
            raise ValueError(f"{test_filename} missing test results")

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


def run_phase(
    phase_name: str,
    phase_prompt_path: Path,
    input_instruction: str,
    working_directory: Path,
    phase_timeout: int = 1800,
    validator: Optional[Callable[[Path], bool]] = None,
    iteration: int = 0,
    project_type: str = "unknown",
) -> PhaseResult:
    """
    Run a single phase with fresh context.

    Args:
        phase_name: e.g., "Scout", "Architect", "Builder"
        phase_prompt_path: Path to phase-specific prompt file
        input_instruction: What to tell the agent
        working_directory: Project directory
        phase_timeout: Max seconds (default 30 min)
        validator: Callable to validate output (phase-specific)
        iteration: Test iteration number (for self-healing loop)
        project_type: Project type for validation

    Returns:
        PhaseResult with metrics
    """
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"🚀 STARTING PHASE: {phase_name} (Fresh Context)", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    # BAML: Track phase start
    session_id = working_directory.name
    if is_baml_available():
        try:
            # BAML PhaseStatus enum values (capitalized)
            status_map = {
                "Scout": "Researching",
                "Architect": "Designing",
                "Builder": "Building",
                "Test": "Testing",
            }
            phase_status = status_map.get(phase_name, "Analyzing")

            phase_info = update_phase_with_baml(
                phase=phase_name,
                status=phase_status,
                detail=f"Starting {phase_name} phase",
                session_id=session_id,
                iteration=iteration,
            )

            # Save to current-phase.json
            phase_file = working_directory / ".context-foundry" / "current-phase.json"
            phase_file.parent.mkdir(parents=True, exist_ok=True)
            phase_file.write_text(json.dumps(phase_info, indent=2))

            print(
                f"✅ BAML phase tracking: {phase_name} → {phase_status}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"⚠️  BAML phase tracking failed: {e}", file=sys.stderr)
    else:
        print(f"⚠️  BAML not available: {get_baml_error()}", file=sys.stderr)

    # Load phase-specific prompt
    if not phase_prompt_path.exists():
        return PhaseResult(
            phase=phase_name,
            status="failed",
            duration_seconds=0,
            context_tokens=0,
            exit_code=1,
            error=f"Phase prompt not found: {phase_prompt_path}",
        )

    phase_prompt = phase_prompt_path.read_text()

    # Build command
    cmd = [
        "claude",
        "--print",
        "--permission-mode",
        "bypassPermissions",
        "--strict-mcp-config",
        "--settings",
        '{"thinkingMode": "off"}',
        "--system-prompt",
        phase_prompt,
        input_instruction,
    ]

    # Track start time
    start = datetime.now()

    # Run phase (BLOCKS until complete)
    print(f"⏳ Running {phase_name} phase...", file=sys.stderr)
    print(f"   Timeout: {phase_timeout}s", file=sys.stderr)
    print(f"   Working directory: {working_directory}", file=sys.stderr)

    try:
        result = subprocess.run(
            cmd,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=phase_timeout,
            env={**dict(os.environ), "PYTHONUNBUFFERED": "1"},
        )

        duration = (datetime.now() - start).total_seconds()

        print(
            f"✅ {phase_name} process completed (exit code: {result.returncode})",
            file=sys.stderr,
        )

        # Estimate context usage
        phase_files = []
        if phase_name == "Scout":
            phase_files = [working_directory / ".context-foundry" / "scout-report.md"]
        elif phase_name == "Architect":
            phase_files = [
                working_directory / ".context-foundry" / "scout-report.md",
                working_directory / ".context-foundry" / "architecture.md",
            ]
        elif phase_name == "Builder":
            phase_files = [working_directory / ".context-foundry" / "architecture.md"]
        elif phase_name == "Test":
            # FIX #3: Use iteration-aware filename for test reports
            test_filename = (
                f"test-report{'-' + str(iteration) if iteration > 0 else ''}.md"
            )
            phase_files = [working_directory / ".context-foundry" / test_filename]

        context_tokens = estimate_context_tokens(
            result.stdout, result.stderr, phase_files
        )

        # Validate output using phase-specific validator
        if validator:
            try:
                if phase_name == "Builder":
                    validator(working_directory, project_type)
                else:
                    validator(working_directory)
                print(f"✅ {phase_name} output validation PASSED", file=sys.stderr)
            except Exception as e:
                print(f"❌ {phase_name} output validation FAILED: {e}", file=sys.stderr)
                return PhaseResult(
                    phase=phase_name,
                    status="failed",
                    duration_seconds=duration,
                    context_tokens=context_tokens,
                    exit_code=1,
                    error=f"Output validation failed: {e}",
                    stdout_lines=len(result.stdout.splitlines()),
                    stderr_lines=len(result.stderr.splitlines()),
                )

        # Verify BAML tracking (soft validation - doesn't fail build)
        if is_baml_available():
            PhaseValidator.validate_baml_tracking(working_directory, phase_name)

        # Log metrics
        log_phase_metrics(
            phase_name,
            duration,
            context_tokens,
            result.returncode,
            working_directory,
            iteration,
        )

        # BAML: Track phase completion
        final_status = "Completed" if result.returncode == 0 else "Failed"
        if is_baml_available():
            try:
                phase_info = update_phase_with_baml(
                    phase=phase_name,
                    status=final_status,
                    detail=f"{phase_name} phase {final_status} in {duration:.1f}s",
                    session_id=session_id,
                    iteration=iteration,
                )

                # Update current-phase.json
                phase_file = (
                    working_directory / ".context-foundry" / "current-phase.json"
                )
                phase_file.write_text(json.dumps(phase_info, indent=2))

                print(
                    f"✅ BAML phase tracking: {phase_name} → {final_status}",
                    file=sys.stderr,
                )

                # Verify BAML tracking file exists
                if not phase_file.exists():
                    print(
                        "⚠️  Warning: current-phase.json not created by BAML",
                        file=sys.stderr,
                    )

            except Exception as e:
                print(f"⚠️  BAML phase completion tracking failed: {e}", file=sys.stderr)

        # Process EXITS here → context released
        # Convert BAML status back to lowercase for PhaseResult
        phase_result_status = "completed" if result.returncode == 0 else "failed"
        return PhaseResult(
            phase=phase_name,
            status=phase_result_status,
            duration_seconds=duration,
            context_tokens=context_tokens,
            exit_code=result.returncode,
            stdout_lines=len(result.stdout.splitlines()),
            stderr_lines=len(result.stderr.splitlines()),
        )

    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start).total_seconds()
        print(f"⏱️  {phase_name} TIMEOUT after {duration:.1f}s", file=sys.stderr)

        # BAML: Track timeout
        if is_baml_available():
            try:
                phase_info = update_phase_with_baml(
                    phase=phase_name,
                    status="Failed",
                    detail=f"Timeout after {duration:.1f}s",
                    session_id=session_id,
                    iteration=iteration,
                )
                phase_file = (
                    working_directory / ".context-foundry" / "current-phase.json"
                )
                phase_file.parent.mkdir(parents=True, exist_ok=True)
                phase_file.write_text(json.dumps(phase_info, indent=2))
            except Exception as baml_error:
                print(f"⚠️  BAML timeout tracking failed: {baml_error}", file=sys.stderr)

        return PhaseResult(
            phase=phase_name,
            status="failed",
            duration_seconds=duration,
            context_tokens=0,
            exit_code=-1,
            error=f"Phase timeout after {phase_timeout}s",
        )

    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        print(f"❌ {phase_name} ERROR: {e}", file=sys.stderr)

        # BAML: Track error
        if is_baml_available():
            try:
                phase_info = update_phase_with_baml(
                    phase=phase_name,
                    status="Failed",
                    detail=f"Error: {str(e)[:100]}",
                    session_id=session_id,
                    iteration=iteration,
                )
                phase_file = (
                    working_directory / ".context-foundry" / "current-phase.json"
                )
                phase_file.parent.mkdir(parents=True, exist_ok=True)
                phase_file.write_text(json.dumps(phase_info, indent=2))
            except Exception as baml_error:
                print(f"⚠️  BAML error tracking failed: {baml_error}", file=sys.stderr)

        return PhaseResult(
            phase=phase_name,
            status="failed",
            duration_seconds=duration,
            context_tokens=0,
            exit_code=1,
            error=str(e),
        )


def _run_parallel_builders(
    build_tasks: dict,
    working_directory: Path,
    project_type: str,
) -> PhaseResult:
    """
    Execute build tasks in parallel based on dependency graph.

    Args:
        build_tasks: Parsed build-tasks.json content
        working_directory: Project directory
        project_type: Project type for validation

    Returns:
        PhaseResult with aggregated metrics
    """
    import concurrent.futures
    import threading

    tasks = build_tasks.get("tasks", [])
    if not tasks:
        raise ValueError("build-tasks.json contains no tasks")

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"🚀 PARALLEL BUILD: {len(tasks)} tasks", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Track task execution state
    completed_tasks = set()
    failed_tasks = set()
    task_results = {}
    results_lock = threading.Lock()

    start_time = datetime.now()

    def execute_task(task: dict) -> tuple[str, bool, dict]:
        """Execute a single build task."""
        task_id = task["task_id"]
        task_name = task["name"]
        task_dir = working_directory / task["working_directory"]

        print(f"\n🔨 Starting task: {task_name} ({task_id})", file=sys.stderr)
        print(f"   Working directory: {task_dir}", file=sys.stderr)

        task_start = datetime.now()

        try:
            # Execute build commands sequentially for this task
            for cmd in task["build_commands"]:
                print(f"   Running: {cmd}", file=sys.stderr)
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=task_dir,
                    capture_output=True,
                    text=True,
                    timeout=900,  # 15 min per command
                )

                if result.returncode != 0:
                    print(f"❌ Task {task_name} failed: {cmd}", file=sys.stderr)
                    print(f"   stderr: {result.stderr[:500]}", file=sys.stderr)
                    return (
                        task_id,
                        False,
                        {
                            "error": f"Command failed: {cmd}",
                            "stderr": result.stderr,
                            "duration": (datetime.now() - task_start).total_seconds(),
                        },
                    )

            duration = (datetime.now() - task_start).total_seconds()
            print(f"✅ Task {task_name} completed in {duration:.1f}s", file=sys.stderr)

            return (
                task_id,
                True,
                {
                    "duration": duration,
                    "commands_executed": len(task["build_commands"]),
                },
            )

        except subprocess.TimeoutExpired:
            return (
                task_id,
                False,
                {
                    "error": "Task timeout (15 minutes)",
                    "duration": 900,
                },
            )
        except Exception as e:
            return (
                task_id,
                False,
                {
                    "error": str(e),
                    "duration": (datetime.now() - task_start).total_seconds(),
                },
            )

    def get_ready_tasks() -> list[dict]:
        """Get tasks whose dependencies are all completed."""
        ready = []
        for task in tasks:
            task_id = task["task_id"]
            if task_id in completed_tasks or task_id in failed_tasks:
                continue

            dependencies = task.get("dependencies", [])
            if all(dep in completed_tasks for dep in dependencies):
                ready.append(task)

        return ready

    # Execute tasks in waves (by dependency level)
    wave_num = 0
    total_tokens = 0

    while len(completed_tasks) + len(failed_tasks) < len(tasks):
        wave_num += 1
        ready_tasks = get_ready_tasks()

        if not ready_tasks:
            # Check if we're stuck (cyclic dependency or all remaining failed)
            if failed_tasks:
                break
            else:
                raise ValueError("Cyclic dependency detected in build-tasks.json")

        print(
            f"\n🌊 Wave {wave_num}: {len(ready_tasks)} parallel tasks", file=sys.stderr
        )

        # Execute ready tasks in parallel
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(ready_tasks)
        ) as executor:
            futures = {
                executor.submit(execute_task, task): task for task in ready_tasks
            }

            for future in concurrent.futures.as_completed(futures):
                task_id, success, result_data = future.result()

                with results_lock:
                    task_results[task_id] = result_data

                    if success:
                        completed_tasks.add(task_id)
                    else:
                        failed_tasks.add(task_id)
                        print(
                            f"\n❌ Task {task_id} failed: {result_data.get('error')}",
                            file=sys.stderr,
                        )

    total_duration = (datetime.now() - start_time).total_seconds()

    print(f"\n{'='*60}", file=sys.stderr)
    print("📊 PARALLEL BUILD SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Total duration: {total_duration:.1f}s", file=sys.stderr)
    print(f"Completed tasks: {len(completed_tasks)}/{len(tasks)}", file=sys.stderr)
    print(f"Failed tasks: {len(failed_tasks)}/{len(tasks)}", file=sys.stderr)
    print(f"Waves executed: {wave_num}", file=sys.stderr)

    # Calculate time savings
    estimated_sequential = build_tasks.get("total_estimated_sequential", 0) * 60
    if estimated_sequential > 0:
        savings_percent = (
            (estimated_sequential - total_duration) / estimated_sequential
        ) * 100
        print(
            f"Time savings: {savings_percent:.1f}% ({estimated_sequential:.0f}s → {total_duration:.0f}s)",
            file=sys.stderr,
        )

    # Return aggregated result
    if failed_tasks:
        return PhaseResult(
            phase="Builder (Parallel)",
            status="failed",
            duration_seconds=total_duration,
            context_tokens=total_tokens,
            exit_code=1,
            error=f"{len(failed_tasks)} tasks failed: {', '.join(failed_tasks)}",
        )
    else:
        return PhaseResult(
            phase="Builder (Parallel)",
            status="completed",
            duration_seconds=total_duration,
            context_tokens=total_tokens,
            exit_code=0,
        )


def run_builder_phase(
    prompt_path: Path,
    instruction: str,
    working_directory: Path,
    project_type: str,
    flowise_mode: bool = False,
    use_parallel: bool = True,
) -> PhaseResult:
    """
    Run Builder phase with conditional parallelization.

    Decision flow:
    1. If Flowise mode → ALWAYS sequential (single JSON file)
    2. Run main builder to create build-tasks.json
    3. Check parallel_mode flag in tasks file
    4. If parallel: spawn sub-builders per task level
    5. If sequential: builder already did everything

    Args:
        prompt_path: Path to builder phase prompt
        instruction: Instruction for builder
        working_directory: Project directory
        project_type: Project type for validation
        flowise_mode: True if Flowise workflow project
        use_parallel: Allow parallelization (can be disabled)

    Returns:
        PhaseResult with metrics
    """
    # HARD GATE: Flowise MUST be sequential
    if flowise_mode:
        print(
            "🚨 Flowise mode: Sequential build (single JSON file required)",
            file=sys.stderr,
        )
        # Note: use_parallel parameter is for future parallelization support

    # Check if parallel build is enabled and feasible
    build_tasks_file = working_directory / ".context-foundry" / "build-tasks.json"

    if use_parallel and build_tasks_file.exists():
        print(
            "📋 Found build-tasks.json - checking for parallel build configuration",
            file=sys.stderr,
        )

        try:
            with open(build_tasks_file) as f:
                build_tasks = json.load(f)

            if build_tasks.get("parallel_build_enabled", False):
                print(
                    "🚀 Parallel build enabled - spawning task builders",
                    file=sys.stderr,
                )
                return _run_parallel_builders(
                    build_tasks,
                    working_directory,
                    project_type,
                )
            else:
                print(
                    "⚠️  build-tasks.json found but parallel_build_enabled=false - using sequential build",
                    file=sys.stderr,
                )

        except (json.JSONDecodeError, KeyError) as e:
            print(
                f"⚠️  Failed to parse build-tasks.json: {e} - falling back to sequential build",
                file=sys.stderr,
            )

    elif use_parallel:
        print("📝 No build-tasks.json found - using sequential build", file=sys.stderr)
    else:
        print("⚠️  Parallel builds disabled (use_parallel=False)", file=sys.stderr)

    # Run sequential builder (original behavior)
    result = run_phase(
        "Builder",
        prompt_path,
        instruction,
        working_directory,
        phase_timeout=1800,
        validator=lambda wd, pt=project_type: PhaseValidator.validate_builder(wd, pt),
        project_type=project_type,
    )

    return result


def tests_passed(test_report_path: Path) -> bool:
    """
    Determine if tests passed from test-report.md.

    Looks for indicators:
    - "All tests passed" or "PASSED"
    - NOT "FAILED" or "ERROR"

    Args:
        test_report_path: Path to test-report.md

    Returns:
        True if tests passed, False otherwise
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
        "result: pass",
        "**status**: passed",
    ]

    fail_indicators = [
        "failed:",
        "❌ failed",
        "status: failed",
        "result: fail",
        "errors:",
        "test failures:",
        "**status**: failed",
    ]

    has_pass = any(indicator in content_lower for indicator in passed_indicators)
    has_fail = any(indicator in content_lower for indicator in fail_indicators)

    # Passed if: has pass indicator AND no fail indicators
    return has_pass and not has_fail

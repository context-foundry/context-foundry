"""Autonomous build with per-phase process spawning (FIXED ARCHITECTURE).

This is the NEW implementation that spawns separate processes per phase.
Each phase gets a FRESH context window and reads only the previous phase's .md file.

Key differences from OLD autonomous_build.py:
- ONE orchestrator → SEPARATE processes per phase
- Accumulated context → FRESH context per phase (released on exit)
- 100K+ tokens → Peak 55K tokens (Builder only)
- DUMB/CRITICAL zones → ALL phases in SMART ZONE (0-40%)

See docs/PHASE_PROCESS_SPAWNING_DESIGN.md for architecture details.
"""

import json
import os
import subprocess
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import BAML integration
from tools.baml_integration import is_baml_available, get_baml_error

# Import safety mechanisms
from tools.evolution.safety import enforce_sandbox_mode

# Import helper functions
from tools.mcp_utils.project_detection import detect_existing_codebase
from tools.mcp_utils.task_classification import detect_task_intent
from tools.mcp_utils.delegation import _write_delegation_metadata
from tools.mcp_utils.phase_execution import (
    run_phase,
    run_builder_phase,
    PhaseValidator,
    tests_passed,
)

# Get module directory for path resolution
MODULE_DIR = Path(__file__).parent.parent  # tools/ directory


def autonomous_build_and_deploy_impl(
    task: str,
    working_directory: str,
    github_repo_name: Optional[str] = None,
    existing_repo: Optional[str] = None,
    mode: str = "new_project",
    max_test_iterations: int = 3,
    timeout_minutes: float = 90.0,
    use_parallel: Optional[
        bool
    ] = None,  # None = let Scout decide; True/False = user override
    incremental: bool = False,
    force_rebuild: bool = False,
    sandbox_path: Optional[str] = None,
    sandbox_task_id: Optional[str] = None,
    active_tasks: Optional[Dict[str, Dict[str, Any]]] = None,
    # REMOVED: enable_test_loop - testing is now automatic based on project detection
) -> str:
    """
    Autonomous build with per-phase process spawning.

    **NEW ARCHITECTURE (v3.0):**
    - Spawns background Python process that executes phases sequentially
    - Each phase within that process spawns separate `claude` subprocess
    - Returns immediately with task_id (NON-BLOCKING)
    - Background process tracked in active_tasks for monitoring

    **Phase Flow (in background process):**
    Scout (NEW process) → scout-report.md → EXITS
    Architect (NEW process) → reads scout-report.md → architecture.md → EXITS
    Builder (NEW process) → reads architecture.md → source files → EXITS
    Test (NEW process) → runs tests → test-report.md → EXITS

    Args:
        Same as OLD autonomous_build.py
        active_tasks: REQUIRED - Dictionary to track background processes

    Returns:
        JSON with task_id, status, message (returns IMMEDIATELY)
    """
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # BAML VERIFICATION
        # ═══════════════════════════════════════════════════════════════════════
        if not is_baml_available():
            error_msg = (
                "❌ BAML is required but not available.\n"
                f"Error: {get_baml_error()}\n\n"
                "Install with: pip install baml-py\n"
            )
            return json.dumps({"error": error_msg}, indent=2)

        print("✅ BAML is available", file=sys.stderr)

        # Determine final working directory
        # Smart defaults: relative paths use projects root (sibling to context-foundry)
        # Absolute paths are used as-is (explicit override)
        #
        # Examples:
        #   "weather-app" → /Users/name/homelab/weather-app (recommended)
        #   "/tmp/test" → /tmp/test (explicit override)
        working_dir_input = Path(working_directory)
        if working_dir_input.is_absolute():
            final_working_dir = working_dir_input
            print(
                f"📍 Using explicit working directory: {working_dir_input}",
                file=sys.stderr,
            )
        else:
            from tools.mcp_utils.path_utils import get_projects_root

            projects_root = get_projects_root()
            final_working_dir = projects_root / working_directory
            print(
                f"📍 Creating project in: {final_working_dir} (sibling to context-foundry)",
                file=sys.stderr,
            )

        final_working_dir_str = str(final_working_dir)

        # ═══════════════════════════════════════════════════════════════════════
        # SANDBOX SAFETY
        # ═══════════════════════════════════════════════════════════════════════
        if sandbox_path:
            try:
                enforce_sandbox_mode(final_working_dir, "autonomous build")
                print("✅ Sandbox safety check passed", file=sys.stderr)
            except (PermissionError, RuntimeError) as e:
                return json.dumps({"error": str(e)}, indent=2)

        # Create working directory
        if not final_working_dir.exists():
            final_working_dir.mkdir(parents=True, exist_ok=True)

        # ═══════════════════════════════════════════════════════════════════════
        # PROJECT DETECTION & MODE ADJUSTMENT
        # ═══════════════════════════════════════════════════════════════════════
        print("🔍 Analyzing workspace...", file=sys.stderr)

        codebase_info = detect_existing_codebase(final_working_dir)
        detected_intent = detect_task_intent(task)

        # Flowise keyword detection
        if not codebase_info.get("flowise_flow", False):
            task_lower = task.lower()
            flowise_keywords = ["flowise", "agent flow", "chatflow"]
            if any(kw in task_lower for kw in flowise_keywords):
                codebase_info["flowise_flow"] = True
                print(
                    "🔍 Flowise Extension: Keyword detection triggered!",
                    file=sys.stderr,
                )

        # Auto-adjust mode
        if mode == "new_project" and codebase_info["has_code"]:
            mode = detected_intent
            print(f"🔄 Auto-adjusted mode: new_project → {mode}", file=sys.stderr)

        flowise_mode = codebase_info.get("flowise_flow", False)
        project_type = codebase_info.get("project_type", "unknown")

        print(f"✨ Final mode: {mode}", file=sys.stderr)
        if flowise_mode:
            print("🚨 Flowise mode: ENABLED", file=sys.stderr)

        # ═══════════════════════════════════════════════════════════════════════
        # TASK CONFIGURATION
        # ═══════════════════════════════════════════════════════════════════════
        # Auto-detect if tests should run based on project type
        # Tests run automatically unless it's a docs-only or config-only project
        has_code = codebase_info.get("has_code", True)
        enable_test_loop = has_code  # Automatic decision

        task_config = {
            "task": task,
            "working_directory": final_working_dir_str,
            "github_repo_name": github_repo_name,
            "mode": mode,
            "enable_test_loop": enable_test_loop,  # Auto-detected, not user-controlled
            "max_test_iterations": max_test_iterations,
            "incremental": incremental and not force_rebuild,
            "flowise_flow": flowise_mode,
            "project_type": project_type,
            "codebase_detection": codebase_info,
        }

        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # ═══════════════════════════════════════════════════════════════════════
        # SPAWN BACKGROUND PROCESS FOR PHASE EXECUTION
        # ═══════════════════════════════════════════════════════════════════════

        # Create Python script to run phase execution in background
        # Serialize task_config as JSON string, parse at runtime
        # Write task config to JSON file instead of embedding in Python code
        # This avoids JSON escaping issues with newlines and special characters
        config_file = final_working_dir / ".context-foundry" / "task_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(task_config, indent=2))

        build_script = f"""
import sys
import json
from pathlib import Path

# Add context-foundry to path
sys.path.insert(0, '{str(MODULE_DIR.parent)}')

from tools.mcp_utils.autonomous_build import execute_build_with_phase_spawning

# Load task config from JSON file
config_file = Path(__file__).parent / "task_config.json"
with open(config_file) as f:
    task_config = json.load(f)

# Execute build with phase spawning
result = execute_build_with_phase_spawning(
    task=task_config["task"],
    working_directory=Path(task_config["working_directory"]),
    task_config=task_config,
    enable_test_loop=task_config["enable_test_loop"],
    max_test_iterations=task_config["max_test_iterations"],
    flowise_mode=task_config["flowise_flow"],
    project_type=task_config["project_type"],
    incremental=task_config["incremental"]
)

print(json.dumps(result))
"""

        # Write script to temp file
        script_file = final_working_dir / ".context-foundry" / "build_runner.py"
        script_file.parent.mkdir(parents=True, exist_ok=True)
        script_file.write_text(build_script)

        # Spawn background process
        cmd = [sys.executable, str(script_file)]

        process_env = {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
        }

        if sandbox_path:
            process_env["CF_SANDBOX_MODE"] = "1"
            process_env["CF_SANDBOX_PATH"] = str(sandbox_path)

        # Start process (NON-BLOCKING)
        process = subprocess.Popen(
            cmd,
            cwd=final_working_dir_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            env=process_env,
        )

        print(
            f"🚀 Background build process started (PID: {process.pid})", file=sys.stderr
        )

        # Store task info in active_tasks (REQUIRED for delegation monitoring)
        if active_tasks is not None:
            active_tasks[task_id] = {
                "process": process,
                "cmd": cmd,
                "cwd": final_working_dir_str,
                "task": task,
                "start_time": datetime.now(),
                "timeout_minutes": timeout_minutes,
                "status": "running",
                "result": None,
                "stdout": None,
                "stderr": None,
                "duration": None,
                "task_config": task_config,
                "build_type": "autonomous",
                "sandbox_path": sandbox_path,
                "sandbox_task_id": sandbox_task_id,
            }

        # Write delegation metadata
        _write_delegation_metadata(
            task_id,
            {
                "task_id": task_id,
                "status": "running",
                "task": task,
                "working_directory": final_working_dir_str,
                "start_time": datetime.now().isoformat(),
                "timeout_minutes": timeout_minutes,
                "pid": process.pid,
                "sandbox_path": sandbox_path,
                "sandbox_task_id": sandbox_task_id,
            },
        )

        project_name = github_repo_name or final_working_dir.name

        # Return immediately (NON-BLOCKING)
        return json.dumps(
            {
                "task_id": task_id,
                "status": "started",
                "project": project_name,
                "working_directory": final_working_dir_str,
                "timeout_minutes": timeout_minutes,
                "message": f"""
🚀 Autonomous build started!

Project: {project_name}
Task ID: {task_id}
Location: {final_working_dir_str}
Expected duration: 7-15 minutes

You can continue working - the build runs in the background.

Check status anytime:
  • Ask: "What's the status of task {task_id}?"
  • Or use: get_delegation_result("{task_id}")

List all builds:
  • Ask: "Show all my builds"
  • Or use: list_delegations()

I'll notify you when it's complete!
""".strip(),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "traceback": traceback.format_exc()},
            indent=2,
        )


def execute_build_with_phase_spawning(
    task: str,
    working_directory: Path,
    task_config: dict,
    enable_test_loop: bool,
    max_test_iterations: int,
    flowise_mode: bool,
    project_type: str,
    incremental: bool,
    use_parallel: Optional[
        bool
    ] = None,  # None = let Scout decide; True/False = user override
    timeout_minutes: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Execute autonomous build with per-phase process spawning.

    This runs in a BACKGROUND process. Each phase spawns as NEW subprocess.

    Args:
        timeout_minutes: Maximum execution time in minutes. Build will terminate if exceeded.

    Returns:
        Build result dict with status, phases_completed, etc.
    """
    # Import here (in background process)

    start_time = datetime.now()
    phases_completed = []
    results = {}
    test_iteration = 0  # FIX #2: Initialize before conditional

    def check_timeout(phase_name: str) -> Optional[Dict[str, Any]]:
        """Check if timeout has been exceeded. Returns error dict if timed out, None otherwise."""
        if timeout_minutes is not None:
            elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60
            if elapsed_minutes > timeout_minutes:
                error_msg = f"Build exceeded timeout of {timeout_minutes} minutes (elapsed: {elapsed_minutes:.1f} min)"
                print(f"\n⏱️  TIMEOUT: {error_msg}", file=sys.stderr)
                return {
                    "status": "failed",
                    "phase_failed": phase_name,
                    "error": error_msg,
                    "start_time": start_time.isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "phases_completed": phases_completed,
                    "test_iterations": test_iteration,
                }
        return None

    try:
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 1: SCOUT
        # ═══════════════════════════════════════════════════════════════════════
        # Check timeout before starting phase
        timeout_result = check_timeout("Scout")
        if timeout_result:
            return timeout_result

        print("\n" + "=" * 60, file=sys.stderr)
        print("PHASE 1: SCOUT", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        # Check Scout cache (if incremental)
        scout_cached = False
        if incremental:
            scout_cached = _check_scout_cache(
                task, task_config["mode"], working_directory
            )

        if not scout_cached:
            # FIX #4: Use module-relative path
            scout_prompt = MODULE_DIR / "prompts" / "phases" / "phase_scout.txt"

            scout_result = run_phase(
                "Scout",
                scout_prompt,
                task,
                working_directory,
                phase_timeout=600,  # 10 min
                validator=PhaseValidator.validate_scout,
                project_type=project_type,
            )

            results["scout"] = scout_result

            if scout_result.status != "completed":
                return {
                    "status": "failed",
                    "phase_failed": "Scout",
                    "error": scout_result.error,
                    "start_time": start_time.isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "phases_completed": phases_completed,
                    "test_iterations": test_iteration,
                }

            # Save to cache
            if incremental:
                _save_scout_cache(task, task_config["mode"], working_directory)

        phases_completed.append("Scout")

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 2: ARCHITECT
        # ═══════════════════════════════════════════════════════════════════════
        # Check timeout before starting phase
        timeout_result = check_timeout("Architect")
        if timeout_result:
            return timeout_result

        print("\n" + "=" * 60, file=sys.stderr)
        print("PHASE 2: ARCHITECT", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        # FIX #4: Use module-relative path
        architect_prompt = MODULE_DIR / "prompts" / "phases" / "phase_architect.txt"

        architect_result = run_phase(
            "Architect",
            architect_prompt,
            "Read .context-foundry/scout-report.md and create architecture.md",
            working_directory,
            phase_timeout=900,  # 15 min
            validator=PhaseValidator.validate_architect,
            project_type=project_type,
        )

        results["architect"] = architect_result

        if architect_result.status != "completed":
            return {
                "status": "failed",
                "phase_failed": "Architect",
                "error": architect_result.error,
                "start_time": start_time.isoformat(),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "phases_completed": phases_completed,
                "test_iterations": test_iteration,
            }

        phases_completed.append("Architect")

        # AUTO-DETECT PARALLEL BUILDS from Scout recommendation
        # Only override if user didn't explicitly specify True or False
        if use_parallel is None:  # User didn't specify - let Scout decide
            scout_report_path = (
                working_directory / ".context-foundry" / "scout-report.md"
            )
            if scout_report_path.exists():
                scout_content = scout_report_path.read_text()
                if (
                    "Parallel Build Recommendation: YES" in scout_content
                    or "Parallel Build Recommendation:** YES" in scout_content
                ):
                    use_parallel = True
                    print(
                        "\n🚀 Auto-enabling parallel builds (Scout recommended)",
                        file=sys.stderr,
                    )
                    print(
                        "   Scout detected independent modules suitable for parallel execution",
                        file=sys.stderr,
                    )
                else:
                    # Scout didn't recommend parallel, default to False
                    use_parallel = False
            else:
                # No Scout report, default to False
                use_parallel = False
        else:
            # User explicitly set use_parallel to True or False - respect their choice
            if use_parallel:
                print(
                    "\n🚀 Parallel builds ENABLED (user override)",
                    file=sys.stderr,
                )
            else:
                print(
                    "\n📦 Sequential build (user override - ignoring Scout recommendation)",
                    file=sys.stderr,
                )

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 3: BUILDER
        # ═══════════════════════════════════════════════════════════════════════
        # Check timeout before starting phase
        timeout_result = check_timeout("Builder")
        if timeout_result:
            return timeout_result

        print("\n" + "=" * 60, file=sys.stderr)
        print("PHASE 3: BUILDER", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        # FIX #4: Use module-relative path
        builder_prompt = MODULE_DIR / "prompts" / "phases" / "phase_builder.txt"

        builder_result = run_builder_phase(
            builder_prompt,
            "Read .context-foundry/architecture.md and implement the project",
            working_directory,
            project_type,
            flowise_mode=flowise_mode,
            use_parallel=use_parallel,
        )

        results["builder"] = builder_result

        if builder_result.status != "completed":
            return {
                "status": "failed",
                "phase_failed": "Builder",
                "error": builder_result.error,
                "start_time": start_time.isoformat(),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "phases_completed": phases_completed,
                "test_iterations": test_iteration,
            }

        phases_completed.append("Builder")

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 4: TEST (with self-healing loop)
        # ═══════════════════════════════════════════════════════════════════════
        # Check timeout before starting test phase
        timeout_result = check_timeout("Test")
        if timeout_result:
            return timeout_result

        if enable_test_loop:
            test_passed = False
            architect_file = ".context-foundry/architecture.md"

            # FIX #4: Use module-relative path
            test_prompt = MODULE_DIR / "prompts" / "phases" / "phase_test.txt"

            while test_iteration <= max_test_iterations:
                # Check timeout at start of each test iteration
                timeout_result = check_timeout(f"Test-Iteration-{test_iteration}")
                if timeout_result:
                    return timeout_result

                print("\n" + "=" * 60, file=sys.stderr)
                print(f"PHASE 4: TEST (Iteration {test_iteration})", file=sys.stderr)
                print("=" * 60, file=sys.stderr)

                test_file = f".context-foundry/test-report{'-' + str(test_iteration) if test_iteration > 0 else ''}.md"

                # FIX #3: Pass expected test file to run_phase for validation
                test_result = run_phase(
                    "Test",
                    test_prompt,
                    f"Run all tests and write results to {test_file}",
                    working_directory,
                    phase_timeout=1200,  # 20 min
                    validator=lambda wd: _validate_test_with_filename(wd, test_file),
                    iteration=test_iteration,
                    project_type=project_type,
                )

                results[f"test_{test_iteration}"] = test_result

                # Check if tests passed
                test_report_path = working_directory / test_file
                if tests_passed(test_report_path):
                    print(
                        f"✅ Tests PASSED (iteration {test_iteration})", file=sys.stderr
                    )
                    test_passed = True
                    break

                # Tests failed
                print(f"❌ Tests FAILED (iteration {test_iteration})", file=sys.stderr)

                test_iteration += 1
                if test_iteration > max_test_iterations:
                    print(
                        f"❌ Max iterations ({max_test_iterations}) reached",
                        file=sys.stderr,
                    )
                    break

                # Self-healing: Run Architect to fix
                print(f"\n🔄 Self-healing iteration {test_iteration}", file=sys.stderr)

                architect_fix_file = (
                    f".context-foundry/architecture-fix-{test_iteration}.md"
                )

                fix_instruction = (
                    f"Read {test_file} and {architect_file}.\n"
                    f"Analyze test failures and update architecture to fix them.\n"
                    f"Write updated architecture to {architect_fix_file}"
                )

                architect_fix_result = run_phase(
                    "Architect",
                    architect_prompt,
                    fix_instruction,
                    working_directory,
                    phase_timeout=900,
                    iteration=test_iteration,
                    project_type=project_type,
                )

                if architect_fix_result.status != "completed":
                    print("❌ Architect fix failed", file=sys.stderr)
                    break

                # Run Builder with fixed architecture
                builder_fix_instruction = (
                    f"Read {architect_fix_file} and implement fixes.\n"
                    f"This is fix iteration {test_iteration}. Focus on test failures only."
                )

                builder_fix_result = run_builder_phase(
                    builder_prompt,
                    builder_fix_instruction,
                    working_directory,
                    project_type,
                    flowise_mode=flowise_mode,
                    use_parallel=False,  # Fixes are small
                )

                if builder_fix_result.status != "completed":
                    print("❌ Builder fix failed", file=sys.stderr)
                    break

                # Update file names for next iteration
                architect_file = architect_fix_file

            phases_completed.append("Test")

            if not test_passed:
                return {
                    "status": "failed",
                    "phase_failed": "Test",
                    "error": f"Tests failed after {test_iteration} iteration(s)",
                    "test_iterations": test_iteration,
                    "start_time": start_time.isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "phases_completed": phases_completed,
                }

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 4.5: SCREENSHOT (Visual Documentation)
        # ═══════════════════════════════════════════════════════════════════════
        # Screenshot phase ALWAYS runs after Test completes (has its own 10-min timeout)
        print("\n🖼️  Running Screenshot phase...", file=sys.stderr)
        screenshot_timeout_result = check_timeout("Screenshot")
        if screenshot_timeout_result:
            print(
                "⚠️  Build timeout exceeded, but running Screenshot anyway (max 10 min)",
                file=sys.stderr,
            )

        screenshot_prompt = MODULE_DIR / "prompts" / "phase_4_5_screenshot.md"
        screenshot_instruction = (
            "Capture screenshots of the application for documentation.\n"
            "Install Playwright, start the app, capture hero + feature screenshots.\n"
            "Save to docs/screenshots/ directory. Gracefully skip if not applicable."
        )

        screenshot_result = run_phase(
            "Screenshot",
            screenshot_prompt,
            screenshot_instruction,
            working_directory,
            phase_timeout=600,  # 10 min
            project_type=project_type,
        )

        # Screenshot is optional - don't fail build if it doesn't work
        if screenshot_result.status == "completed":
            phases_completed.append("Screenshot")
            print("✅ Screenshots captured", file=sys.stderr)
        else:
            print(
                f"⚠️  Screenshot capture skipped: {screenshot_result.error or 'N/A'}",
                file=sys.stderr,
            )
            # Continue anyway - screenshots are optional

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 5: DOCUMENTATION (README Generation)
        # ═══════════════════════════════════════════════════════════════════════
        # Documentation phase ALWAYS runs after Screenshot completes (has its own 10-min timeout)
        print("\n📝 Running Documentation phase...", file=sys.stderr)
        doc_timeout_result = check_timeout("Documentation")
        if doc_timeout_result:
            print(
                "⚠️  Build timeout exceeded, but running Documentation anyway (max 10 min)",
                file=sys.stderr,
            )

        docs_prompt = MODULE_DIR / "prompts" / "phase_5_documentation.md"
        docs_instruction = (
            "Generate comprehensive README.md with:\n"
            "- Project overview and features\n"
            "- Installation instructions\n"
            "- Usage examples\n"
            "- Screenshots (from docs/screenshots/ if available)\n"
            "- API documentation\n"
            "- Contributing guidelines\n"
            "- License and badges"
        )

        docs_result = run_phase(
            "Documentation",
            docs_prompt,
            docs_instruction,
            working_directory,
            phase_timeout=600,  # 10 min
            project_type=project_type,
        )

        if docs_result.status == "completed":
            phases_completed.append("Documentation")
            print("✅ Documentation generated", file=sys.stderr)
        else:
            print(
                f"⚠️  Documentation generation failed: {docs_result.error}",
                file=sys.stderr,
            )
            # Continue to deployment even if docs fail

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 6: DEPLOY (GitHub)
        # ═══════════════════════════════════════════════════════════════════════
        # Deploy phase ALWAYS runs after Documentation completes (has its own 15-min timeout)
        print("\n🚀 Running Deploy phase...", file=sys.stderr)
        deploy_timeout_result = check_timeout("Deploy")
        if deploy_timeout_result:
            print(
                "⚠️  Build timeout exceeded, but running Deploy anyway (max 10 min)",
                file=sys.stderr,
            )

        deploy_prompt = MODULE_DIR / "prompts" / "phase_6_deployment.md"

        # Determine repository name
        github_repo_name = task_config.get("github_repo_name")
        repo_name = github_repo_name or working_directory.name

        deploy_instruction = (
            f"Deploy to GitHub:\n"
            f"1. Check if gh CLI is available and authenticated\n"
            f"2. Initialize git repo (if not already)\n"
            f"3. Stage all files: git add .\n"
            f"4. Commit: git commit -m 'feat: {task[:60]}'\n"
            f"5. Create GitHub repo: gh repo create {repo_name} --public --source=. --push\n"
            f"6. Push to main branch\n"
            f"7. Update session-summary.json with repo URL\n\n"
            f"If gh CLI not available, print instructions and exit with code 10 (build success, deploy skipped)."
        )

        deploy_result = run_phase(
            "Deploy",
            deploy_prompt,
            deploy_instruction,
            working_directory,
            phase_timeout=600,  # 10 min
            project_type=project_type,
        )

        # Deploy is optional - don't fail build if GitHub unavailable
        if deploy_result.status == "completed":
            phases_completed.append("Deploy")
            print("✅ Deployed to GitHub", file=sys.stderr)
        elif deploy_result.exit_code == 10:
            # Exit code 10 = build success, deployment skipped
            print("⚠️  Deployment skipped (GitHub CLI not available)", file=sys.stderr)
        else:
            print(
                f"⚠️  Deployment failed: {deploy_result.error or 'Unknown error'}",
                file=sys.stderr,
            )
            # Continue anyway - deployment is optional

        # ═══════════════════════════════════════════════════════════════════════
        # SUCCESS
        # ═══════════════════════════════════════════════════════════════════════
        duration = (datetime.now() - start_time).total_seconds()

        print(f"\n{'=' * 60}", file=sys.stderr)
        print("[TRACE] execute_build_with_phase_spawning COMPLETING", file=sys.stderr)
        print(f"[TRACE] Timestamp: {datetime.now().isoformat()}", file=sys.stderr)
        print(f"[TRACE] Duration: {duration:.1f}s", file=sys.stderr)
        print(f"[TRACE] Phases: {phases_completed}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)

        result = {
            "status": "completed",
            "phases_completed": phases_completed,
            "test_iterations": test_iteration,  # Now always defined
            "start_time": start_time.isoformat(),
            "duration_seconds": duration,
            "message": f"Build completed successfully in {duration:.1f}s",
        }

        print(
            "[TRACE] About to RETURN from execute_build_with_phase_spawning",
            file=sys.stderr,
        )
        print(f"[TRACE] Returning at: {datetime.now().isoformat()}", file=sys.stderr)
        sys.stderr.flush()  # Force flush before return

        return result

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "phases_completed": phases_completed,
            "test_iterations": test_iteration,
            "start_time": start_time.isoformat(),
            "duration_seconds": duration,
        }


def _validate_test_with_filename(working_dir: Path, test_filename: str) -> bool:
    """FIX #3: Validate test with iteration-aware filename."""
    required = working_dir / test_filename
    if not required.exists():
        raise FileNotFoundError(f"Test failed to create {required}")

    # Verify contains results
    content = required.read_text()
    if "PASSED" not in content and "FAILED" not in content:
        raise ValueError(f"{test_filename} missing test results")

    return True


def _check_scout_cache(task: str, mode: str, working_directory: Path) -> bool:
    """Check for cached Scout report. Returns True if cache hit."""
    try:
        sys.path.insert(0, str(MODULE_DIR.parent))
        from tools.cache.scout_cache import get_cached_scout_report

        cached = get_cached_scout_report(
            task=task, mode=mode, working_directory=str(working_directory)
        )

        if cached:
            # Save cached report
            scout_file = working_directory / ".context-foundry" / "scout-report.md"
            scout_file.parent.mkdir(parents=True, exist_ok=True)
            scout_file.write_text(cached)

            print("⚡ Incremental build: Reusing cached Scout report", file=sys.stderr)
            return True

        return False

    except Exception as e:
        print(f"⚠️  Scout cache check failed: {e}", file=sys.stderr)
        return False


def _save_scout_cache(task: str, mode: str, working_directory: Path):
    """Save Scout report to cache."""
    try:
        sys.path.insert(0, str(MODULE_DIR.parent))
        from tools.cache.scout_cache import save_scout_report_to_cache

        scout_file = working_directory / ".context-foundry" / "scout-report.md"
        if scout_file.exists():
            save_scout_report_to_cache(
                task=task,
                mode=mode,
                working_directory=str(working_directory),
                scout_report_content=scout_file.read_text(),
            )
            print("💾 Scout report saved to cache", file=sys.stderr)

    except Exception as e:
        print(f"⚠️  Scout cache save failed: {e}", file=sys.stderr)

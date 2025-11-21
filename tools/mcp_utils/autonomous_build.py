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

import copy
import json
import os
import subprocess
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

# Import BAML integration
from tools.baml_integration import (
    is_baml_available,
    get_baml_error,
    create_build_plan,
    parse_scout_markdown_baml,
    parse_architecture_markdown_baml,
)

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
    # tests_passed - REMOVED: Now using exit codes instead of parsing natural language
)

# Get module directory for path resolution
MODULE_DIR = Path(__file__).parent.parent  # tools/ directory


def _post_process_build_plan(
    build_plan: Dict[str, Any],
) -> tuple[Dict[str, Any], List[str]]:
    """
    Normalize and harden build plan outputs before saving to disk.

    - Ensure required task fields exist (task_id, agent_instruction, provider)
    - Fill sensible defaults to avoid empty fields reaching Builder
    - Add provenance metadata for traceability
    """
    warnings: List[str] = []
    normalized = copy.deepcopy(build_plan) if isinstance(build_plan, dict) else {}

    # Provenance metadata
    normalized.setdefault("schema_version", "1.0")
    normalized.setdefault("generated_by", "autonomous_build.py:create_build_plan")
    normalized.setdefault("generated_at", datetime.utcnow().isoformat() + "Z")

    tasks = normalized.get("tasks", [])
    if not isinstance(tasks, list):
        warnings.append("build_plan.tasks not a list; resetting to empty list")
        normalized["tasks"] = []
        return normalized, warnings

    for idx, task in enumerate(tasks):
        t = copy.deepcopy(task)

        # task_id fallback
        if not t.get("task_id"):
            fallback_id = t.get("id") or f"task-{idx + 1}"
            warnings.append(f"Task missing task_id; using fallback '{fallback_id}'")
            t["task_id"] = fallback_id

        # working_directory default
        t.setdefault("working_directory", ".")

        # dependencies normalization
        deps = t.get("dependencies", [])
        if deps is None:
            deps = []
        if not isinstance(deps, list):
            warnings.append(
                f"Task {t['task_id']}: dependencies not a list; coerced to []"
            )
            deps = []
        t["dependencies"] = deps

        # build_commands normalization
        build_commands = t.get("build_commands", [])
        if build_commands is None:
            build_commands = []
        if not isinstance(build_commands, list):
            warnings.append(
                f"Task {t['task_id']}: build_commands not a list; coerced to []"
            )
            build_commands = []
        t["build_commands"] = build_commands

        # provider default
        if not t.get("provider"):
            warnings.append(
                f"Task {t['task_id']}: missing provider; defaulting to Claude"
            )
            t["provider"] = "Claude"

        # agent_instruction default
        if not t.get("agent_instruction"):
            name = t.get("name") or t.get("description") or t["task_id"]
            desc = t.get("description") or ""
            t["agent_instruction"] = f"Implement {name}. {desc}".strip()
            warnings.append(
                f"Task {t['task_id']}: missing agent_instruction; synthesized fallback"
            )

        tasks[idx] = t

    normalized["tasks"] = tasks
    return normalized, warnings


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
            # Check if this is an extension directory (should create project in homelab, not inside extension)
            from tools.mcp_utils.path_utils import get_projects_root

            projects_root = get_projects_root()

            # Detect if working_dir is inside context-foundry/extensions/
            # In that case, we should create a NEW project in homelab, not inside the extension
            cf_extensions = projects_root / "context-foundry" / "extensions"
            is_extension_dir = str(working_dir_input).startswith(str(cf_extensions))

            if is_extension_dir and mode == "new_project":
                # Extract project name from task description
                # Look for common patterns like "FDM Worktag Coach" or project names
                import re

                # Try to extract a project name from the task
                # Look for quoted names or capitalized phrases
                project_name_match = re.search(r'"([^"]+)"', task) or re.search(
                    r"'([^']+)'", task
                )
                if project_name_match:
                    raw_name = project_name_match.group(1)
                else:
                    # Fallback: use first few words
                    words = task.split()[:5]
                    raw_name = " ".join(words)

                # Convert to kebab-case directory name
                project_name = re.sub(r"[^a-zA-Z0-9]+", "-", raw_name.lower()).strip(
                    "-"
                )
                if len(project_name) > 50:
                    project_name = project_name[:50].rsplit("-", 1)[0]

                final_working_dir = projects_root / project_name
                print(
                    f"📍 Extension directory detected - creating project in: {final_working_dir}",
                    file=sys.stderr,
                )
                print(
                    f"   (Extension source: {working_dir_input})",
                    file=sys.stderr,
                )
            else:
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
            # FLOWISE BOOTSTRAP - Auto-load patterns into Codex
            # ═══════════════════════════════════════════════════════════════════════
            print("📚 Auto-loading Flowise patterns into Codex...", file=sys.stderr)
            bootstrap_script = (
                MODULE_DIR.parent / "scripts" / "bootstrap_flowise_patterns.py"
            )
            if bootstrap_script.exists():
                try:
                    result = subprocess.run(
                        [sys.executable, str(bootstrap_script)],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if result.returncode == 0:
                        print("✅ Flowise patterns loaded into Codex", file=sys.stderr)
                    else:
                        print(
                            f"⚠️ Bootstrap warning: {result.stderr[:200]}",
                            file=sys.stderr,
                        )
                except subprocess.TimeoutExpired:
                    print("⚠️ Bootstrap timed out (continuing anyway)", file=sys.stderr)
                except Exception as e:
                    print(
                        f"⚠️ Bootstrap error: {e} (continuing anyway)", file=sys.stderr
                    )
            else:
                print(
                    f"⚠️ Bootstrap script not found: {bootstrap_script}", file=sys.stderr
                )

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
    import re

    # ═══════════════════════════════════════════════════════════════════════
    # PATH REDIRECTION FOR EXTENSION DIRECTORIES
    # ═══════════════════════════════════════════════════════════════════════
    # When working_directory is inside context-foundry/extensions/, create
    # project under homelab/<project-name>/ instead
    from tools.mcp_utils.path_utils import get_projects_root

    projects_root = get_projects_root()
    cf_extensions = projects_root / "context-foundry" / "extensions"

    mode = task_config.get("mode", "new_project")
    is_extension_dir = str(working_directory).startswith(str(cf_extensions))

    if is_extension_dir and mode == "new_project":
        # Extract project name from task description
        project_name_match = re.search(r'"([^"]+)"', task) or re.search(
            r"'([^']+)'", task
        )
        if project_name_match:
            raw_name = project_name_match.group(1)
        else:
            # Fallback: use first few words
            words = task.split()[:5]
            raw_name = " ".join(words)

        # Convert to kebab-case directory name
        project_name = re.sub(r"[^a-zA-Z0-9]+", "-", raw_name.lower()).strip("-")
        if len(project_name) > 50:
            project_name = project_name[:50].rsplit("-", 1)[0]

        working_directory = projects_root / project_name
        print(
            f"📍 Extension directory detected - creating project in: {working_directory}",
            file=sys.stderr,
        )
        print(
            f"   (Extension source: {cf_extensions})",
            file=sys.stderr,
        )

        # Create the directory if it doesn't exist
        if not working_directory.exists():
            working_directory.mkdir(parents=True, exist_ok=True)

        # Update task_config with new working directory
        task_config["working_directory"] = str(working_directory)
    # ═══════════════════════════════════════════════════════════════════════
    # END PATH REDIRECTION
    # ═══════════════════════════════════════════════════════════════════════

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

            # ═══════════════════════════════════════════════════════════════════════
            # PRE-QUERY CODEX FOR FLOWISE BUILDS
            # ═══════════════════════════════════════════════════════════════════════
            # Scout spawns as a separate claude CLI without MCP access, so we must
            # pre-query Codex and inject results into the task description
            scout_task = task
            if flowise_mode:
                codex_results = _pre_query_codex_for_flowise()
                if codex_results:
                    scout_task = f"{task}\n\n{codex_results}"
                    print("📚 Injected Codex patterns into Scout task", file=sys.stderr)

            scout_result = run_phase(
                "Scout",
                scout_prompt,
                scout_task,
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

        # Structured Scout JSON (BAML parse)
        scout_md_path = working_directory / ".context-foundry" / "scout-report.md"
        scout_json_path = working_directory / ".context-foundry" / "scout_report.json"
        if scout_md_path.exists():
            try:
                scout_md = scout_md_path.read_text()
                scout_json = parse_scout_markdown_baml(scout_md)
                scout_json_path.write_text(json.dumps(scout_json, indent=2))
                print(
                    f"✅ Parsed Scout markdown to JSON: {scout_json_path}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"⚠️  Failed to parse Scout markdown to JSON: {e}", file=sys.stderr
                )

        # ═══════════════════════════════════════════════════════════════════════
        # FLOWISE CODEX VALIDATION - Enforce pattern queries
        # ═══════════════════════════════════════════════════════════════════════
        if flowise_mode:
            print("🔍 Validating Flowise codex queries...", file=sys.stderr)
            try:
                PhaseValidator.validate_flowise_codex_queries(working_directory)
            except ValueError as e:
                return {
                    "status": "failed",
                    "phase_failed": "Scout",
                    "error": str(e),
                    "start_time": start_time.isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "phases_completed": phases_completed,
                    "test_iterations": test_iteration,
                }

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

        # Structured Architecture JSON (BAML parse)
        architecture_md_path = (
            working_directory / ".context-foundry" / "architecture.md"
        )
        architecture_json_path = (
            working_directory / ".context-foundry" / "architecture.json"
        )
        if architecture_md_path.exists():
            try:
                architecture_md = architecture_md_path.read_text()
                architecture_json = parse_architecture_markdown_baml(architecture_md)
                architecture_json_path.write_text(
                    json.dumps(architecture_json, indent=2)
                )
                print(
                    f"✅ Parsed architecture markdown to JSON: {architecture_json_path}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"⚠️  Failed to parse architecture markdown to JSON: {e}",
                    file=sys.stderr,
                )

        # ═══════════════════════════════════════════════════════════════════════
        # BAML BUILD PLAN GENERATION (Phase 2 of BAML Migration)
        # ═══════════════════════════════════════════════════════════════════════
        print("\n📋 Generating build plan using BAML...", file=sys.stderr)

        try:
            # Read Scout report to get parallel build recommendation
            scout_report_path = (
                working_directory / ".context-foundry" / "scout-report.md"
            )
            scout_content = (
                scout_report_path.read_text() if scout_report_path.exists() else ""
            )

            # Detect Scout's parallel build recommendation
            scout_parallel_recommendation = False
            scout_reasoning = "No Scout report found"

            if scout_content:
                if (
                    "Parallel Build Recommendation: YES" in scout_content
                    or "Parallel Build Recommendation:** YES" in scout_content
                ):
                    scout_parallel_recommendation = True
                    # Extract reasoning (look for "Build Strategy" section)
                    if "## Build Strategy" in scout_content:
                        strategy_section = scout_content.split("## Build Strategy")[
                            1
                        ].split("##")[0]
                        scout_reasoning = strategy_section.strip()
                    else:
                        scout_reasoning = "Scout recommended parallel build"
                else:
                    scout_reasoning = "Scout recommended sequential build"

            # Read architecture summary
            architecture_path = (
                working_directory / ".context-foundry" / "architecture.md"
            )
            architecture_summary = (
                architecture_path.read_text() if architecture_path.exists() else ""
            )

            # DETERMINE FINAL PARALLEL DECISION BEFORE CALLING BAML
            # If user explicitly passed use_parallel, respect it and override Scout
            if use_parallel is not None:
                # User explicitly set use_parallel to True or False - respect their choice
                if use_parallel:
                    scout_parallel_recommendation = True
                    scout_reasoning = "User override: parallel build requested"
                    print(
                        "\n🚀 Parallel builds ENABLED (user override)",
                        file=sys.stderr,
                    )
                else:
                    scout_parallel_recommendation = False
                    scout_reasoning = "User override: sequential build requested"
                    print(
                        "\n📦 Sequential build (user override - ignoring Scout recommendation)",
                        file=sys.stderr,
                    )
            # Otherwise scout_parallel_recommendation already set from Scout report above

            # Call BAML to generate build plan
            build_plan = create_build_plan(
                architecture_summary=architecture_summary,
                scout_parallel_recommendation=scout_parallel_recommendation,
                scout_reasoning=scout_reasoning,
                project_type=project_type,
            )

            # Post-process for required defaults and provenance
            build_plan, plan_warnings = _post_process_build_plan(build_plan)
            for w in plan_warnings:
                print(f"⚠️  Build plan warning: {w}", file=sys.stderr)

            # Save build-tasks.json
            build_tasks_path = (
                working_directory / ".context-foundry" / "build-tasks.json"
            )
            with open(build_tasks_path, "w") as f:
                json.dump(build_plan, f, indent=2)

            print(f"✅ Build plan generated: {build_tasks_path}", file=sys.stderr)
            if build_plan.get("parallel_build_enabled"):
                task_count = len(build_plan.get("tasks", []))
                print(f"   Parallel build with {task_count} tasks", file=sys.stderr)
            else:
                print("   Sequential build (no parallel tasks)", file=sys.stderr)

        except Exception as e:
            print(f"⚠️  BAML build plan generation failed: {e}", file=sys.stderr)
            print("   Continuing without build-tasks.json", file=sys.stderr)
            traceback.print_exc()

        # SET FINAL use_parallel FROM BAML OUTPUT
        # If user didn't specify, use the parallel_build_enabled from BAML output
        if use_parallel is None:
            try:
                use_parallel = build_plan.get("parallel_build_enabled", False)
                if use_parallel:
                    print(
                        "\n🚀 Auto-enabling parallel builds (Scout recommended)",
                        file=sys.stderr,
                    )
                    print(
                        "   Scout detected independent modules suitable for parallel execution",
                        file=sys.stderr,
                    )
            except Exception:
                use_parallel = False

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

                # Check if tests passed using exit code (RELIABLE - not language parsing!)
                # Exit code 0 = success (UNIX standard), non-zero = failure
                if test_result.exit_code == 0:
                    print(
                        f"✅ Tests PASSED (iteration {test_iteration}) - exit code: 0",
                        file=sys.stderr,
                    )
                    test_passed = True
                    break

                # Tests failed
                print(
                    f"❌ Tests FAILED (iteration {test_iteration}) - exit code: {test_result.exit_code}",
                    file=sys.stderr,
                )

                test_iteration += 1
                if test_iteration > max_test_iterations:
                    print(
                        f"❌ Max iterations ({max_test_iterations}) reached",
                        file=sys.stderr,
                    )
                    break

                # Self-healing: Run Architect to fix
                print(f"\n🔄 Self-healing iteration {test_iteration}", file=sys.stderr)

                # test_file already points to the report that just failed (correct!)
                # Don't recalculate - the next test iteration hasn't run yet

                architect_fix_file = (
                    f".context-foundry/architecture-fix-{test_iteration}.md"
                )

                fix_instruction = (
                    f"FIX ITERATION MODE (see prompt section '🔄 FIX ITERATION MODE')\n\n"
                    f"Read {test_file} and {architect_file}.\n"
                    f"Analyze test failures and create a fix plan.\n"
                    f"Write fix plan to {architect_fix_file}.\n\n"
                    f"CRITICAL: You are an ARCHITECT, not a BUILDER!\n"
                    f"- DO NOT implement code changes yourself\n"
                    f"- ONLY create {architect_fix_file} with the fix specification\n"
                    f"- Builder will implement your plan in the next phase"
                )

                # Take snapshot of source files before Architect runs
                source_files_before = _get_source_file_checksums(working_directory)

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

                # ENFORCEMENT: Validate Architect fix phase output
                fix_file_path = working_directory / architect_fix_file
                validation_errors = []

                # 1. Check architecture-fix-{N}.md exists
                if not fix_file_path.exists():
                    validation_errors.append(
                        f"Architect did not create {architect_fix_file}"
                    )

                # 2. Check it's not empty
                elif fix_file_path.stat().st_size < 100:
                    validation_errors.append(
                        f"{architect_fix_file} is suspiciously small ({fix_file_path.stat().st_size} bytes)"
                    )

                # 3. Check Architect didn't modify or delete source files
                source_files_after = _get_source_file_checksums(working_directory)

                # Check for modifications
                modified_files = [
                    f
                    for f, checksum in source_files_after.items()
                    if source_files_before.get(f) != checksum
                ]

                # Check for deletions
                deleted_files = [
                    f for f in source_files_before.keys() if f not in source_files_after
                ]

                if modified_files:
                    validation_errors.append(
                        f"Architect modified source files (should only create fix plan): {', '.join(modified_files[:5])}"
                    )

                if deleted_files:
                    validation_errors.append(
                        f"Architect deleted source files (should only create fix plan): {', '.join(deleted_files[:5])}"
                    )

                if validation_errors:
                    print("\n❌ ARCHITECT FIX VALIDATION FAILED:", file=sys.stderr)
                    for error in validation_errors:
                        print(f"   - {error}", file=sys.stderr)
                    print(
                        "\n💡 Architect should ONLY create a fix plan document, not implement code!",
                        file=sys.stderr,
                    )
                    # Return explicit error instead of generic "Test failed"
                    return {
                        "status": "failed",
                        "phase_failed": "Architect (fix validation)",
                        "error": f"Architect fix validation failed: {'; '.join(validation_errors)}",
                        "start_time": start_time.isoformat(),
                        "duration_seconds": (
                            datetime.now() - start_time
                        ).total_seconds(),
                        "phases_completed": phases_completed,
                        "test_iterations": test_iteration,
                    }

                # ENFORCEMENT: Check Architect stayed within budget (14K tokens)
                architect_budget = 14000
                if architect_fix_result.context_tokens > architect_budget:
                    print(
                        f"\n⚠️  WARNING: Architect fix used {architect_fix_result.context_tokens:,} tokens "
                        f"(budget: {architect_budget:,})",
                        file=sys.stderr,
                    )
                    print(
                        "   Architect should analyze failures briefly, not deeply implement solutions.",
                        file=sys.stderr,
                    )
                    # Don't fail build, but log the violation
                else:
                    print(
                        f"✅ Architect fix stayed within budget: {architect_fix_result.context_tokens:,}/{architect_budget:,} tokens",
                        file=sys.stderr,
                    )

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
                    iteration=test_iteration,
                )

                if builder_fix_result.status != "completed":
                    print("❌ Builder fix failed", file=sys.stderr)
                    break

                # ENFORCEMENT: Check Builder fix stayed within budget (40K tokens)
                builder_budget = 40000
                if builder_fix_result.context_tokens > builder_budget:
                    print(
                        f"\n⚠️  WARNING: Builder fix used {builder_fix_result.context_tokens:,} tokens "
                        f"(budget: {builder_budget:,})",
                        file=sys.stderr,
                    )
                    print(
                        "   Builder should make surgical fixes, not rebuild entire project.",
                        file=sys.stderr,
                    )
                    # Don't fail build, but log the violation
                else:
                    print(
                        f"✅ Builder fix stayed within budget: {builder_fix_result.context_tokens:,}/{builder_budget:,} tokens",
                        file=sys.stderr,
                    )

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


def _pre_query_codex_for_flowise() -> str:
    """
    Pre-query Codex for Flowise patterns and format for injection into Scout task.

    Scout runs as a separate claude CLI process without MCP access, so we must
    query Codex before spawning and include results in the task description.

    Returns:
        Formatted string with Codex research results, or empty string if unavailable.
    """
    import sqlite3
    from pathlib import Path

    codex_db = Path.home() / ".context-foundry" / "codex.db"
    if not codex_db.exists():
        print("⚠️  Codex database not found, skipping pre-query", file=sys.stderr)
        return ""

    try:
        conn = sqlite3.connect(str(codex_db))
        cursor = conn.cursor()

        # Query for Flowise patterns
        pattern_queries = [
            ("flowise routing", "routing"),
            ("flowise agentflow", "agentflow"),
            ("flowise conditionagent", "conditionagent"),
            ("flowise start node", "start"),
            ("flowise inputparams", "inputparams"),
        ]

        patterns_found = []
        issues_found = []

        for query_term, _ in pattern_queries:
            cursor.execute(
                """
                SELECT id, title, type, description
                FROM knowledge_entries
                WHERE (title LIKE ? OR description LIKE ? OR tags LIKE ?)
                AND type IN ('pattern', 'issue')
                LIMIT 5
            """,
                (f"%{query_term}%", f"%{query_term}%", f"%{query_term}%"),
            )

            for row in cursor.fetchall():
                entry_id, title, entry_type, description = row
                if entry_type == "pattern":
                    patterns_found.append(f"- **{entry_id}**: {title}")
                else:
                    issues_found.append(f"- **{entry_id}**: {title}")

        conn.close()

        if not patterns_found and not issues_found:
            return ""

        # Format results for injection
        result = "\n## Context Codex Research Results (Pre-queried)\n\n"

        if patterns_found:
            result += "### Patterns Found:\n"
            result += "\n".join(sorted(set(patterns_found))) + "\n\n"

        if issues_found:
            result += "### Issues/Anti-patterns Found:\n"
            result += "\n".join(sorted(set(issues_found))) + "\n\n"

        result += "**IMPORTANT**: Use these patterns when designing the architecture. Reference the pattern IDs in your Context Codex Research section.\n"

        return result

    except Exception as e:
        print(f"⚠️  Codex pre-query failed: {e}", file=sys.stderr)
        return ""


def _get_source_file_checksums(working_dir: Path) -> dict[str, str]:
    """
    Get MD5 checksums of all source files (excluding .context-foundry).
    Used to detect if Architect modified files during fix iteration.
    """
    import hashlib

    checksums = {}
    exclude_dirs = {".context-foundry", ".git", "node_modules", "venv", "__pycache__"}

    for file_path in working_dir.rglob("*"):
        if file_path.is_file():
            # Skip ONLY the specific excluded directories
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            # Include ALL other files (including .github, .vscode, .env, etc.)
            try:
                relative_path = file_path.relative_to(working_dir)
                with open(file_path, "rb") as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                checksums[str(relative_path)] = file_hash
            except (OSError, ValueError):
                # Skip files we can't read
                continue

    return checksums


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

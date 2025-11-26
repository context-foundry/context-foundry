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
import random
import subprocess
import sys
import traceback
import uuid
import time
import signal
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from multiprocessing import Process, Queue

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
from tools.mcp_utils.pipeline_state import (
    PipelineState,
    PipelineStateSnapshot,
    get_pipeline_state,
    save_pipeline_state,
    get_phases_from,
)

# Get module directory for path resolution
MODULE_DIR = Path(__file__).parent.parent  # tools/ directory


# ═══════════════════════════════════════════════════════════════════════
# DIRECTORY NAMING HELPER
# ═══════════════════════════════════════════════════════════════════════


def generate_random_id(length: int = 4) -> str:
    """
    Generate a random numeric ID for directory naming.

    Args:
        length: Number of digits (default: 4)

    Returns:
        Random numeric string (e.g., "4817")
    """
    return str(random.randint(10 ** (length - 1), 10**length - 1))


# ═══════════════════════════════════════════════════════════════════════
# LOGGING HELPER
# ═══════════════════════════════════════════════════════════════════════


def log_debug(message: str, working_directory: Optional[Path] = None):
    """Append debug message to .context-foundry/build_debug.log"""
    try:
        if working_directory:
            log_file = working_directory / ".context-foundry" / "build_debug.log"
            if not log_file.parent.exists():
                log_file.parent.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().isoformat()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass  # Fail silently to not disrupt build


# ═══════════════════════════════════════════════════════════════════════
# PIPELINE PAUSE/RESUME HELPERS
# ═══════════════════════════════════════════════════════════════════════


def _check_and_handle_pause(
    phase_name: str,
    working_directory: Path,
    pipeline_state: Optional[PipelineStateSnapshot],
    phases_completed: List[str],
    start_time: datetime,
    test_iteration: int,
    task_config: dict,
) -> Optional[Dict[str, Any]]:
    """
    Check if pipeline should pause after a phase and return pause result if so.

    Args:
        phase_name: Phase that just completed
        working_directory: Project directory
        pipeline_state: Current pipeline state (or None for autonomous mode)
        phases_completed: List of completed phases
        start_time: Build start time
        test_iteration: Current test iteration
        task_config: Task configuration

    Returns:
        Pause result dict if should pause, None otherwise
    """
    if pipeline_state is None:
        return None

    if not pipeline_state.should_pause_after(phase_name):
        return None

    # Mark as paused and save state
    pipeline_state.mark_phase_completed(phase_name)
    pipeline_state.mark_paused(phase_name)
    pipeline_state.task_config = task_config
    save_pipeline_state(pipeline_state, working_directory)

    duration = (datetime.now() - start_time).total_seconds()

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"⏸️  PIPELINE PAUSED after {phase_name}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)
    print(f"Phases completed: {', '.join(phases_completed)}", file=sys.stderr)
    print(f"Duration so far: {duration:.1f}s", file=sys.stderr)
    print(f"\nTo resume: cfd resume --dir {working_directory}", file=sys.stderr)
    if pipeline_state.phases_remaining:
        next_phase = pipeline_state.phases_remaining[0]
        print(f"Next phase: {next_phase}", file=sys.stderr)
        print(
            f"Or resume from specific phase: cfd resume --from {next_phase} --dir {working_directory}",
            file=sys.stderr,
        )
    print(f"{'=' * 60}\n", file=sys.stderr)

    return {
        "status": "paused",
        "paused_after": phase_name,
        "phases_completed": phases_completed,
        "phases_remaining": pipeline_state.phases_remaining,
        "start_time": start_time.isoformat(),
        "duration_seconds": duration,
        "test_iterations": test_iteration,
        "pipeline_id": pipeline_state.pipeline_id,
        "resume_command": pipeline_state.get_resume_command(working_directory),
        "message": f"Build paused after {phase_name}. Use 'cfd resume' to continue.",
    }


def _initialize_pipeline_state(
    task_config: dict,
    working_directory: Path,
    resume_from_phase: Optional[str] = None,
) -> Optional[PipelineStateSnapshot]:
    """
    Initialize or load pipeline state based on task config.

    Args:
        task_config: Task configuration with execution_mode, pause_after_phases, etc.
        working_directory: Project directory
        resume_from_phase: If resuming, the phase to resume from

    Returns:
        PipelineStateSnapshot if pipeline mode enabled, None for autonomous mode
    """
    execution_mode = task_config.get("execution_mode", "autonomous")
    pause_after_phases = task_config.get("pause_after_phases", [])
    target_phases = task_config.get("target_phases", [])

    # Check for resume
    if resume_from_phase:
        existing_state = get_pipeline_state(working_directory)
        if existing_state:
            # Resuming from pause - update remaining phases
            existing_state.mark_resumed()
            existing_state.phases_remaining = get_phases_from(resume_from_phase)
            save_pipeline_state(existing_state, working_directory)
            print(f"📍 Resuming pipeline from {resume_from_phase}", file=sys.stderr)
            return existing_state

    # For autonomous mode without any pause points, skip pipeline state overhead
    if execution_mode == "autonomous" and not pause_after_phases:
        return None

    # Create new pipeline state
    state = PipelineStateSnapshot.create(
        task_config=task_config,
        execution_mode=execution_mode,
        pause_after_phases=pause_after_phases,
        target_phases=target_phases,
    )
    # Mark pipeline as RUNNING immediately
    state.state = PipelineState.RUNNING
    save_pipeline_state(state, working_directory)

    mode_desc = {
        "autonomous": "Full autonomous mode",
        "interactive": "Interactive mode (pause after each phase)",
        "selective": f"Selective mode (phases: {', '.join(target_phases)})",
    }.get(execution_mode, execution_mode)

    print(f"📋 Pipeline initialized: {mode_desc}", file=sys.stderr)
    if pause_after_phases:
        print(f"   Pause after: {', '.join(pause_after_phases)}", file=sys.stderr)

    return state


def _should_skip_phase(
    phase_name: str,
    pipeline_state: Optional[PipelineStateSnapshot],
    resume_from_phase: Optional[str],
) -> bool:
    """
    Check if a phase should be skipped (already completed or before resume point).

    Args:
        phase_name: Phase to check
        pipeline_state: Current pipeline state
        resume_from_phase: Phase to resume from (if resuming)

    Returns:
        True if phase should be skipped
    """
    # If resuming from a specific phase, skip all phases before it
    if resume_from_phase:
        from tools.mcp_utils.pipeline_state import PHASE_ORDER

        try:
            resume_idx = PHASE_ORDER.index(resume_from_phase)
            current_idx = PHASE_ORDER.index(phase_name)
            if current_idx < resume_idx:
                return True
        except ValueError:
            pass  # Phase not in order, don't skip

    if pipeline_state is None:
        return False

    # Skip if already completed
    if phase_name in pipeline_state.phases_completed:
        return True

    # Skip if not in target phases (selective mode)
    if pipeline_state.target_phases and phase_name not in pipeline_state.target_phases:
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════
# BAML TIMEOUT & TIMING HELPERS
# ═══════════════════════════════════════════════════════════════════════


class TimeoutException(Exception):
    """Raised when BAML call exceeds timeout"""

    pass


def _timeout_handler(signum, frame):
    """Signal handler for timeouts"""
    raise TimeoutException("BAML call exceeded timeout")


@contextmanager
def baml_timeout(seconds: int, operation_name: str):
    """
    Context manager that enforces a timeout on BAML calls.

    Args:
        seconds: Timeout in seconds
        operation_name: Name of operation for logging

    Raises:
        TimeoutException: If operation exceeds timeout
    """
    # Set up signal handler (Unix only)
    if hasattr(signal, "SIGALRM"):
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(seconds)
        start_time = time.time()

        try:
            print(
                f"⏱️  [{operation_name}] Starting (timeout: {seconds}s)...",
                file=sys.stderr,
            )
            yield
            duration = time.time() - start_time
            print(
                f"✅ [{operation_name}] Completed in {duration:.1f}s", file=sys.stderr
            )
        except TimeoutException:
            print(f"⏰ [{operation_name}] TIMEOUT after {seconds}s", file=sys.stderr)
            raise
        finally:
            signal.alarm(0)  # Cancel alarm
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows fallback - no timeout enforcement, just timing
        start_time = time.time()
        print(
            f"⏱️  [{operation_name}] Starting (no timeout on Windows)...",
            file=sys.stderr,
        )
        try:
            yield
            duration = time.time() - start_time
            print(
                f"✅ [{operation_name}] Completed in {duration:.1f}s", file=sys.stderr
            )
        except Exception:
            duration = time.time() - start_time
            print(
                f"❌ [{operation_name}] Failed after {duration:.1f}s", file=sys.stderr
            )
            raise


def baml_breathing_buffer(seconds: float = 2.0):
    """
    Add a delay between BAML calls to avoid overwhelming GPT-4o-mini.

    Args:
        seconds: Delay in seconds (default: 2.0)
    """
    print(
        f"😮‍💨 Breathing buffer ({seconds}s) before next BAML call...", file=sys.stderr
    )
    time.sleep(seconds)


def _parse_architecture_with_claude_cli(md_content: str) -> Dict[str, Any]:
    """
    Parse architecture markdown using Claude CLI (desktop subscription).

    This bypasses BAML and API requirements by using the local claude command.
    Falls back to BAML if Claude CLI is unavailable or fails.

    Args:
        md_content: Architecture markdown to parse

    Returns:
        Dict with parsed architecture structure

    Raises:
        FileNotFoundError: If claude CLI is not installed
        subprocess.TimeoutExpired: If parsing exceeds timeout
        RuntimeError: If Claude CLI fails or returns invalid JSON
    """
    import subprocess
    import tempfile
    import shutil

    # Check if claude CLI is available
    if not shutil.which("claude"):
        raise FileNotFoundError(
            "claude CLI not found in PATH - install from https://claude.com/download"
        )

    # Create prompt for Claude to parse the architecture
    prompt = f"""Parse this architecture markdown document and extract it into a structured JSON format.

Return ONLY valid JSON (no markdown, no explanations) with this exact structure:
{{
  "system_overview": "string - complete system architecture overview",
  "file_structure": [
    {{
      "path": "string - file/directory path",
      "purpose": "string - purpose of this file",
      "dependencies": ["string - list of dependencies"]
    }}
  ],
  "modules": [
    {{
      "name": "string - module name",
      "responsibility": "string - module responsibility",
      "interfaces": ["string - public APIs"],
      "dependencies": ["string - module dependencies"]
    }}
  ],
  "applied_patterns": [
    {{
      "pattern_id": "string - pattern ID",
      "pattern_name": "string - pattern name",
      "reason": "string - why this pattern"
    }}
  ],
  "preventive_measures": ["string - list of preventive measures"],
  "implementation_steps": ["string - ordered implementation steps"],
  "test_plan": {{
    "unit_tests": ["string - unit tests"],
    "integration_tests": ["string - integration tests"],
    "e2e_tests": ["string - e2e tests"],
    "test_framework": "string - framework to use",
    "success_criteria": ["string - success criteria"]
  }},
  "success_criteria": ["string - overall success criteria"]
}}

ARCHITECTURE MARKDOWN:
{md_content}

Return ONLY the JSON object, nothing else."""

    # Write prompt to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        prompt_file = f.name
        f.write(prompt)

    try:
        # Call claude CLI with --print flag for non-interactive output
        # --dangerously-skip-permissions is required for subprocess execution
        result = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", prompt_file],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Claude CLI exited with code {result.returncode}: {result.stderr}"
            )

        # Parse JSON from output
        output = result.stdout.strip()

        if not output:
            raise RuntimeError("Claude CLI returned empty output")

        # Extract JSON if wrapped in markdown code blocks
        if "```json" in output:
            output = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            output = output.split("```")[1].split("```")[0].strip()

        parsed = json.loads(output)
        return parsed

    finally:
        # Clean up temp file
        Path(prompt_file).unlink(missing_ok=True)


def _architecture_baml_worker(md: str, q: Queue):
    """Worker function for parsing architecture BAML in separate process."""
    try:
        parsed = parse_architecture_markdown_baml(md)
        q.put(("ok", parsed))
    except Exception as exc:  # pragma: no cover - defensive
        q.put(("error", str(exc)))


def _parse_architecture_baml_with_timeout(md_content: str, timeout_seconds: int = 120):
    """
    Parse architecture markdown via BAML in a separate process with a hard timeout.

    This prevents the main orchestrator from hanging if the BAML call blocks.
    """
    q: Queue = Queue()
    proc = Process(target=_architecture_baml_worker, args=(md_content, q))
    proc.start()
    proc.join(timeout_seconds)

    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        raise TimeoutException(
            f"Architecture BAML parse exceeded {timeout_seconds}s (process killed)"
        )

    if q.empty():
        raise RuntimeError("Architecture BAML parse returned no result")

    status, payload = q.get()
    if status == "ok":
        return payload
    raise RuntimeError(f"Architecture BAML parse failed: {payload}")


def parse_and_save_architecture_json(
    working_directory: Path,
) -> Optional[Dict[str, Any]]:
    """
    Parse architecture.md to architecture.json using Claude CLI with BAML fallback.

    This is the production code path that:
    1. Reads .context-foundry/architecture.md
    2. Tries to parse with Claude CLI (free, uses desktop subscription)
    3. Falls back to BAML if Claude CLI fails/unavailable
    4. Saves result to .context-foundry/architecture.json
    5. Handles timeouts and errors gracefully

    Returns:
        Dict with parsed architecture if successful, None if parsing failed or file missing
    """
    architecture_md_path = working_directory / ".context-foundry" / "architecture.md"
    architecture_json_path = (
        working_directory / ".context-foundry" / "architecture.json"
    )
    architecture_md = None
    architecture_json = None

    if not architecture_md_path.exists():
        log_debug(
            "⚠️ Architecture markdown missing, skipping BAML parse",
            working_directory,
        )
        return None

    print(
        f"[TRACE] Reading architecture.md from {architecture_md_path}",
        file=sys.stderr,
    )

    try:
        architecture_md = architecture_md_path.read_text()
        print(
            f"[TRACE] architecture.md loaded ({len(architecture_md)} bytes); starting parse",
            file=sys.stderr,
        )

        # Try Claude CLI first (free, uses desktop subscription)
        # Falls back to BAML if CLI unavailable or fails
        try:
            log_debug(
                f"Attempting to parse Architecture with Claude CLI ({len(architecture_md)} bytes)",
                working_directory,
            )
            architecture_json = _parse_architecture_with_claude_cli(architecture_md)
            log_debug("✅ Architecture parsed with Claude CLI", working_directory)
            print(
                "✅ Architecture parsed with Claude CLI",
                file=sys.stderr,
            )
        except (
            FileNotFoundError,
            subprocess.TimeoutExpired,
            RuntimeError,
            json.JSONDecodeError,
        ) as cli_error:
            # Claude CLI unavailable or failed - fall back to BAML
            log_debug(
                f"⚠️ Claude CLI parse failed ({type(cli_error).__name__}), falling back to BAML",
                working_directory,
            )
            print(
                f"⚠️  Claude CLI unavailable ({type(cli_error).__name__}), using BAML fallback...",
                file=sys.stderr,
            )

            # BAML fallback with timeout
            try:
                architecture_json = _parse_architecture_baml_with_timeout(
                    architecture_md, timeout_seconds=600
                )
                log_debug("✅ Architecture parsed with BAML", working_directory)
                print(
                    "✅ Architecture parsed with BAML (fallback)",
                    file=sys.stderr,
                )
            except TimeoutException:
                log_debug("⚠️ BAML parse also timed out after 600s", working_directory)
                print(
                    "⚠️  BAML parse also timed out - continuing without architecture.json",
                    file=sys.stderr,
                )
                raise  # Re-raise to outer handler
            except Exception as baml_error:
                log_debug(
                    f"⚠️ BAML parse also failed: {str(baml_error)}",
                    working_directory,
                )
                print(
                    f"⚠️  BAML parse also failed: {baml_error}",
                    file=sys.stderr,
                )
                raise  # Re-raise to outer handler

        # Save architecture.json (from either Claude CLI or BAML)
        architecture_json_path.write_text(json.dumps(architecture_json, indent=2))
        print(
            f"✅ Saved architecture.json: {architecture_json_path}",
            file=sys.stderr,
        )
        return architecture_json

    except TimeoutException:
        log_debug("⚠️ Architecture parse TIMED OUT after 600s", working_directory)
        print(
            "⚠️  Architecture parse timed out after 600s - continuing without architecture.json",
            file=sys.stderr,
        )
        return None
    except Exception as e:
        log_debug(f"⚠️ Architecture parse FAILED: {str(e)}", working_directory)
        print(
            f"⚠️  Failed to parse architecture markdown to JSON: {e}",
            file=sys.stderr,
        )
        return None


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

        # ═══════════════════════════════════════════════════════════════════════
        # APPEND RANDOM ID FOR NEW PROJECTS
        # ═══════════════════════════════════════════════════════════════════════
        # For new projects, ALWAYS append a random ID to prevent overwriting existing builds
        # Example: weather-app → weather-app-4817
        # IMPORTANT: Do this BEFORE creating the directory to ensure uniqueness
        if mode == "new_project":
            random_id = generate_random_id()
            original_name = final_working_dir.name
            new_name = f"{original_name}-{random_id}"
            final_working_dir = final_working_dir.parent / new_name
            print(
                f"📍 Appending random ID for new project: {original_name} → {new_name}",
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
    resume_from_phase: Optional[str] = None,  # Resume from specific phase
) -> Dict[str, Any]:
    """
    Execute autonomous build with per-phase process spawning.

    This runs in a BACKGROUND process. Each phase spawns as NEW subprocess.

    Args:
        timeout_minutes: Maximum execution time in minutes. Build will terminate if exceeded.
        resume_from_phase: If set, resume from this phase (skip earlier phases).

    Returns:
        Build result dict with status, phases_completed, etc.
        Status can be: "completed", "failed", "paused", "error"
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

    # ═══════════════════════════════════════════════════════════════════════
    # PIPELINE STATE INITIALIZATION (for pause/resume support)
    # ═══════════════════════════════════════════════════════════════════════
    pipeline_state = _initialize_pipeline_state(
        task_config=task_config,
        working_directory=working_directory,
        resume_from_phase=resume_from_phase,
    )

    # If resuming, populate phases_completed from saved state
    if pipeline_state and pipeline_state.phases_completed:
        phases_completed = list(pipeline_state.phases_completed)
        print(
            f"📍 Resuming with completed phases: {', '.join(phases_completed)}",
            file=sys.stderr,
        )

    # Log start of build process
    log_debug(f"Build process started. Task: {task[:50]}...", working_directory)
    log_debug(
        f"Configuration: flowise={flowise_mode}, incremental={incremental}, parallel={use_parallel}",
        working_directory,
    )

    def check_timeout(phase_name: str) -> Optional[Dict[str, Any]]:
        """Check if timeout has been exceeded. Returns error dict if timed out, None otherwise."""
        if timeout_minutes is not None:
            elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60
            if elapsed_minutes > timeout_minutes:
                error_msg = f"Build exceeded timeout of {timeout_minutes} minutes (elapsed: {elapsed_minutes:.1f} min)"
                print(f"\n⏱️  TIMEOUT: {error_msg}", file=sys.stderr)
                # Persist timeout failure state
                if pipeline_state:
                    pipeline_state.mark_failed(phase_name, error_msg)
                    save_pipeline_state(pipeline_state, working_directory)
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
        # Check if phase should be skipped (already completed or resuming from later phase)
        scout_skipped = _should_skip_phase("Scout", pipeline_state, resume_from_phase)

        if scout_skipped:
            print("⏭️  Skipping Scout phase (already completed)", file=sys.stderr)
            # Still need scout_json for Architect - try to load from existing file
            scout_json = None
            scout_json_path = (
                working_directory / ".context-foundry" / "scout_report.json"
            )
            if scout_json_path.exists():
                try:
                    scout_json = json.loads(scout_json_path.read_text())
                except Exception:
                    pass
        else:
            # Check timeout before starting phase
            timeout_result = check_timeout("Scout")
            if timeout_result:
                return timeout_result

            print("\n" + "=" * 60, file=sys.stderr)
            print("PHASE 1: SCOUT", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

            # Mark phase as started for visibility
            if pipeline_state:
                pipeline_state.mark_phase_started("Scout")
                save_pipeline_state(pipeline_state, working_directory)

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
                        print(
                            "📚 Injected Codex patterns into Scout task",
                            file=sys.stderr,
                        )

                scout_instruction = (
                    "Read .context-foundry/scout-report.md (or scout_report.json if present) "
                    "and produce scout-report.md with findings."
                )
                scout_result = run_phase(
                    "Scout",
                    scout_prompt,
                    f"{scout_instruction}\n\n{scout_task}",
                    working_directory,
                    phase_timeout=600,  # 10 min
                    validator=PhaseValidator.validate_scout,
                    project_type=project_type,
                )

                results["scout"] = scout_result

                if scout_result.status != "completed":
                    # Persist failure state
                    if pipeline_state:
                        pipeline_state.mark_failed(
                            "Scout", scout_result.error or "Scout phase failed"
                        )
                        save_pipeline_state(pipeline_state, working_directory)
                    return {
                        "status": "failed",
                        "phase_failed": "Scout",
                        "error": scout_result.error,
                        "start_time": start_time.isoformat(),
                        "duration_seconds": (
                            datetime.now() - start_time
                        ).total_seconds(),
                        "phases_completed": phases_completed,
                        "test_iterations": test_iteration,
                    }

                # Save to cache
                if incremental:
                    _save_scout_cache(task, task_config["mode"], working_directory)

            # Mark Scout complete (not already in list when skipped)
            if "Scout" not in phases_completed:
                phases_completed.append("Scout")
                # Persist phase completion
                if pipeline_state:
                    pipeline_state.mark_phase_completed("Scout")
                    save_pipeline_state(pipeline_state, working_directory)

            # Check if we should pause after Scout
            pause_result = _check_and_handle_pause(
                "Scout",
                working_directory,
                pipeline_state,
                phases_completed,
                start_time,
                test_iteration,
                task_config,
            )
            if pause_result:
                return pause_result

        # Structured Scout JSON (BAML parse) - only if Scout was not skipped
        # (when skipped, we already loaded scout_json from the existing file above)
        if not scout_skipped:
            scout_md_path = working_directory / ".context-foundry" / "scout-report.md"
            scout_json_path = (
                working_directory / ".context-foundry" / "scout_report.json"
            )
            scout_json = None
            if scout_md_path.exists():
                try:
                    scout_md = scout_md_path.read_text()
                    log_debug(
                        f"Attempting to parse Scout markdown ({len(scout_md)} bytes) with BAML",
                        working_directory,
                    )

                    # BAML parse with timeout (90 seconds max)
                    with baml_timeout(90, "Scout BAML Parse"):
                        scout_json = parse_scout_markdown_baml(scout_md)

                    scout_json_path.write_text(json.dumps(scout_json, indent=2))
                    log_debug("✅ Scout BAML parse successful", working_directory)
                    print(
                        f"✅ Parsed Scout markdown to JSON: {scout_json_path}",
                        file=sys.stderr,
                    )
                except TimeoutException:
                    log_debug(
                        "⚠️ Scout BAML parse TIMED OUT after 90s", working_directory
                    )
                    print(
                        "⚠️  Scout BAML parse timed out after 90s - continuing without scout_report.json",
                        file=sys.stderr,
                    )
                except Exception as e:
                    log_debug(f"⚠️ Scout BAML parse FAILED: {str(e)}", working_directory)
                    print(
                        f"⚠️  Failed to parse Scout markdown to JSON: {e}",
                        file=sys.stderr,
                    )
            else:
                log_debug(
                    "⚠️ Scout markdown missing, skipping BAML parse", working_directory
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
        # Check if phase should be skipped (already completed or resuming from later phase)
        architect_skipped = _should_skip_phase(
            "Architect", pipeline_state, resume_from_phase
        )

        if architect_skipped:
            print("⏭️  Skipping Architect phase (already completed)", file=sys.stderr)
            # Load architecture_json from existing file for Builder
            architecture_json = None
            arch_json_path = (
                working_directory / ".context-foundry" / "architecture.json"
            )
            if arch_json_path.exists():
                try:
                    architecture_json = json.loads(arch_json_path.read_text())
                except Exception:
                    pass
        else:
            # Check timeout before starting phase
            timeout_result = check_timeout("Architect")
            if timeout_result:
                return timeout_result

            print("\n" + "=" * 60, file=sys.stderr)
            print("PHASE 2: ARCHITECT", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

            # Mark phase as started for visibility
            if pipeline_state:
                pipeline_state.mark_phase_started("Architect")
                save_pipeline_state(pipeline_state, working_directory)

            # FIX #4: Use module-relative path
            architect_prompt = MODULE_DIR / "prompts" / "phases" / "phase_architect.txt"

            architect_instruction = (
                "Use the provided structured Scout JSON (ignore markdown unless JSON is missing). "
                "Create architecture.md.\n\n"
            )
            if scout_json:
                architect_instruction += "SCOUT_JSON:\n" + json.dumps(
                    scout_json, indent=2
                )
            else:
                architect_instruction = (
                    "Read .context-foundry/scout-report.md (scout_report.json missing). "
                    "Create architecture.md."
                )

            architect_result = run_phase(
                "Architect",
                architect_prompt,
                architect_instruction,
                working_directory,
                phase_timeout=900,  # 15 min
                validator=PhaseValidator.validate_architect,
                project_type=project_type,
            )

            results["architect"] = architect_result

            print(
                f"[TRACE] Architect phase result: status={architect_result.status}, "
                f"exit_code={architect_result.exit_code}, duration={architect_result.duration_seconds:.1f}s",
                file=sys.stderr,
            )

            if architect_result.status != "completed":
                # Persist failure state
                if pipeline_state:
                    pipeline_state.mark_failed(
                        "Architect", architect_result.error or "Architect phase failed"
                    )
                    save_pipeline_state(pipeline_state, working_directory)
                return {
                    "status": "failed",
                    "phase_failed": "Architect",
                    "error": architect_result.error,
                    "start_time": start_time.isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "phases_completed": phases_completed,
                    "test_iterations": test_iteration,
                }

            # Mark Architect complete
            if "Architect" not in phases_completed:
                phases_completed.append("Architect")
                # Persist phase completion
                if pipeline_state:
                    pipeline_state.mark_phase_completed("Architect")
                    save_pipeline_state(pipeline_state, working_directory)

            print(
                "[TRACE] Architect phase marked completed, entering post-processing",
                file=sys.stderr,
            )

            # Check if we should pause after Architect
            pause_result = _check_and_handle_pause(
                "Architect",
                working_directory,
                pipeline_state,
                phases_completed,
                start_time,
                test_iteration,
                task_config,
            )
            if pause_result:
                return pause_result

        # Post-processing only when Architect was not skipped
        if not architect_skipped:
            # Breathing buffer before next BAML call
            if scout_json is not None:  # Only add buffer if Scout BAML succeeded
                baml_breathing_buffer(3.0)

            # Structured Architecture JSON (BAML parse) - extracted to testable function
            architecture_json = parse_and_save_architecture_json(working_directory)

        # ═══════════════════════════════════════════════════════════════════════
        # BAML BUILD PLAN GENERATION (Phase 2 of BAML Migration)
        # ═══════════════════════════════════════════════════════════════════════

        # Breathing buffer before build plan generation
        if (
            architecture_json is not None
        ):  # Only add buffer if Architecture BAML succeeded
            baml_breathing_buffer(3.0)

        print("\n📋 Generating build plan using BAML...", file=sys.stderr)

        build_plan_generated = False
        try:
            # Read Scout report (prefer JSON) to get parallel build recommendation
            scout_report_path = (
                working_directory / ".context-foundry" / "scout-report.md"
            )
            scout_content = (
                scout_report_path.read_text() if scout_report_path.exists() else ""
            )
            scout_parallel_recommendation = None
            scout_reasoning = "No Scout report found"

            if scout_json:
                # If JSON has a parallel flag, prefer it; otherwise fall back to markdown heuristics
                json_parallel = None
                for key in ["parallel_build_recommendation", "parallel_build"]:
                    if key in scout_json:
                        json_parallel = scout_json.get(key)
                        break
                if isinstance(json_parallel, bool):
                    scout_parallel_recommendation = json_parallel
                    scout_reasoning = "Scout JSON parallel flag"
                else:
                    print(
                        "⚠️  Scout JSON present but missing parallel flag — falling back to markdown",
                        file=sys.stderr,
                    )

            if scout_content and scout_parallel_recommendation is None:
                if (
                    "Parallel Build Recommendation: YES" in scout_content
                    or "Parallel Build Recommendation:** YES" in scout_content
                ):
                    scout_parallel_recommendation = True
                    if "## Build Strategy" in scout_content:
                        strategy_section = scout_content.split("## Build Strategy")[
                            1
                        ].split("##")[0]
                        scout_reasoning = strategy_section.strip()
                    else:
                        scout_reasoning = "Scout recommended parallel build"
                else:
                    scout_parallel_recommendation = False
                    scout_reasoning = "Scout recommended sequential build"

            # Final default if still None
            if scout_parallel_recommendation is None:
                scout_parallel_recommendation = False

            # Read architecture summary (prefer JSON)
            architecture_path = (
                working_directory / ".context-foundry" / "architecture.md"
            )
            if architecture_json:
                architecture_summary = json.dumps(architecture_json, indent=2)
                log_debug("Using architecture.json for build plan", working_directory)
                print(
                    "ℹ️  Using architecture.json for build plan input", file=sys.stderr
                )
            else:
                architecture_summary = (
                    architecture_path.read_text() if architecture_path.exists() else ""
                )
                if architecture_summary:
                    log_debug(
                        "⚠️ architecture.json missing; falling back to architecture.md for build plan",
                        working_directory,
                    )
                    print(
                        "⚠️  architecture.json missing; using architecture.md",
                        file=sys.stderr,
                    )
                else:
                    log_debug(
                        "⚠️ No architecture context found for build plan",
                        working_directory,
                    )
                    print(
                        "⚠️  No architecture context found; build plan may be incomplete",
                        file=sys.stderr,
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

            # Call BAML to generate build plan with strict timeout (180 seconds = 3 minutes)
            # This is the call that hung in the weather app build
            with baml_timeout(180, "Build Plan Generation"):
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

            build_plan_generated = True

        except TimeoutException:
            print("⚠️  Build plan generation TIMED OUT after 180s", file=sys.stderr)
            print(
                "   Falling back to sequential build (no parallel tasks)",
                file=sys.stderr,
            )
            print("   Builder will proceed without build-tasks.json", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  BAML build plan generation failed: {e}", file=sys.stderr)
            print(
                "   Falling back to sequential build (no parallel tasks)",
                file=sys.stderr,
            )
            traceback.print_exc()

        # SET FINAL use_parallel FROM BAML OUTPUT
        # If user didn't specify, use the parallel_build_enabled from BAML output
        if use_parallel is None:
            if build_plan_generated:
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
            else:
                # Build plan generation failed/timed out - default to sequential
                use_parallel = False
                print(
                    "\n📦 Sequential build (build plan generation failed)",
                    file=sys.stderr,
                )

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 3: BUILDER
        # ═══════════════════════════════════════════════════════════════════════
        # Check if phase should be skipped (already completed or resuming from later phase)
        builder_skipped = _should_skip_phase(
            "Builder", pipeline_state, resume_from_phase
        )

        if builder_skipped:
            print("⏭️  Skipping Builder phase (already completed)", file=sys.stderr)
        else:
            # Check timeout before starting phase
            timeout_result = check_timeout("Builder")
            if timeout_result:
                return timeout_result

            print("\n" + "=" * 60, file=sys.stderr)
            print("PHASE 3: BUILDER", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

            # Mark phase as started for visibility
            if pipeline_state:
                pipeline_state.mark_phase_started("Builder")
                save_pipeline_state(pipeline_state, working_directory)

            # FIX #4: Use module-relative path
            builder_prompt = MODULE_DIR / "prompts" / "phases" / "phase_builder.txt"

            builder_instruction = (
                "Use the provided structured architecture JSON (ignore markdown unless JSON is missing). "
                "Implement the project accordingly.\n\n"
            )
            if architecture_json:
                log_debug("Providing architecture.json to Builder", working_directory)
                builder_instruction += "ARCHITECTURE_JSON:\n" + json.dumps(
                    architecture_json, indent=2
                )
            else:
                log_debug(
                    "Providing architecture.md to Builder (JSON missing)",
                    working_directory,
                )
                builder_instruction = (
                    "Read .context-foundry/architecture.md (architecture.json missing). "
                    "Implement the project accordingly."
                )

            builder_result = run_builder_phase(
                builder_prompt,
                builder_instruction,
                working_directory,
                project_type,
                flowise_mode=flowise_mode,
                use_parallel=use_parallel,
            )

            results["builder"] = builder_result

            if builder_result.status != "completed":
                # Persist failure state
                if pipeline_state:
                    pipeline_state.mark_failed(
                        "Builder", builder_result.error or "Builder phase failed"
                    )
                    save_pipeline_state(pipeline_state, working_directory)
                return {
                    "status": "failed",
                    "phase_failed": "Builder",
                    "error": builder_result.error,
                    "start_time": start_time.isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "phases_completed": phases_completed,
                    "test_iterations": test_iteration,
                }

            # Mark Builder complete
            if "Builder" not in phases_completed:
                phases_completed.append("Builder")
                # Persist phase completion
                if pipeline_state:
                    pipeline_state.mark_phase_completed("Builder")
                    save_pipeline_state(pipeline_state, working_directory)

            # Check if we should pause after Builder
            pause_result = _check_and_handle_pause(
                "Builder",
                working_directory,
                pipeline_state,
                phases_completed,
                start_time,
                test_iteration,
                task_config,
            )
            if pause_result:
                return pause_result

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 4: TEST (with self-healing loop)
        # ═══════════════════════════════════════════════════════════════════════
        # Check if phase should be skipped (already completed or resuming from later phase)
        test_skipped = _should_skip_phase("Test", pipeline_state, resume_from_phase)

        if test_skipped:
            print("⏭️  Skipping Test phase (already completed)", file=sys.stderr)
        elif enable_test_loop:
            # Check timeout before starting test phase
            timeout_result = check_timeout("Test")
            if timeout_result:
                return timeout_result

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

                # Mark phase as started for visibility (only on first iteration)
                if test_iteration == 0 and pipeline_state:
                    pipeline_state.mark_phase_started("Test")
                    save_pipeline_state(pipeline_state, working_directory)

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
                    # Persist failure state
                    error_msg = f"Architect fix validation failed: {'; '.join(validation_errors)}"
                    if pipeline_state:
                        pipeline_state.mark_failed(
                            "Architect (fix validation)", error_msg
                        )
                        save_pipeline_state(pipeline_state, working_directory)
                    # Return explicit error instead of generic "Test failed"
                    return {
                        "status": "failed",
                        "phase_failed": "Architect (fix validation)",
                        "error": error_msg,
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

            # Mark Test complete
            if "Test" not in phases_completed:
                phases_completed.append("Test")
                # Persist phase completion
                if pipeline_state:
                    pipeline_state.mark_phase_completed("Test")
                    save_pipeline_state(pipeline_state, working_directory)

            if not test_passed:
                # Persist failure state
                if pipeline_state:
                    pipeline_state.mark_failed(
                        "Test", f"Tests failed after {test_iteration} iteration(s)"
                    )
                    save_pipeline_state(pipeline_state, working_directory)
                return {
                    "status": "failed",
                    "phase_failed": "Test",
                    "error": f"Tests failed after {test_iteration} iteration(s)",
                    "test_iterations": test_iteration,
                    "start_time": start_time.isoformat(),
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "phases_completed": phases_completed,
                }

            # Check if we should pause after Test
            pause_result = _check_and_handle_pause(
                "Test",
                working_directory,
                pipeline_state,
                phases_completed,
                start_time,
                test_iteration,
                task_config,
            )
            if pause_result:
                return pause_result

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 4.5: SCREENSHOT (Visual Documentation)
        # ═══════════════════════════════════════════════════════════════════════
        # Check if phase should be skipped
        screenshot_skipped = _should_skip_phase(
            "Screenshot", pipeline_state, resume_from_phase
        )

        if screenshot_skipped:
            print("⏭️  Skipping Screenshot phase (already completed)", file=sys.stderr)
        else:
            # Screenshot phase ALWAYS runs after Test completes (has its own 10-min timeout)
            print("\n🖼️  Running Screenshot phase...", file=sys.stderr)

            # Mark phase as started for visibility
            if pipeline_state:
                pipeline_state.mark_phase_started("Screenshot")
                save_pipeline_state(pipeline_state, working_directory)

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
                if "Screenshot" not in phases_completed:
                    phases_completed.append("Screenshot")
                    # Persist phase completion
                    if pipeline_state:
                        pipeline_state.mark_phase_completed("Screenshot")
                        save_pipeline_state(pipeline_state, working_directory)
                print("✅ Screenshots captured", file=sys.stderr)

                # Check if we should pause after Screenshot
                pause_result = _check_and_handle_pause(
                    "Screenshot",
                    working_directory,
                    pipeline_state,
                    phases_completed,
                    start_time,
                    test_iteration,
                    task_config,
                )
                if pause_result:
                    return pause_result
            else:
                print(
                    f"⚠️  Screenshot capture skipped: {screenshot_result.error or 'N/A'}",
                    file=sys.stderr,
                )
                # Continue anyway - screenshots are optional

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 5: DOCUMENTATION (README Generation)
        # ═══════════════════════════════════════════════════════════════════════
        # Check if phase should be skipped
        docs_skipped = _should_skip_phase(
            "Documentation", pipeline_state, resume_from_phase
        )

        if docs_skipped:
            print(
                "⏭️  Skipping Documentation phase (already completed)", file=sys.stderr
            )
        else:
            # Documentation phase ALWAYS runs after Screenshot completes (has its own 10-min timeout)
            print("\n📝 Running Documentation phase...", file=sys.stderr)

            # Mark phase as started for visibility
            if pipeline_state:
                pipeline_state.mark_phase_started("Documentation")
                save_pipeline_state(pipeline_state, working_directory)

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
                if "Documentation" not in phases_completed:
                    phases_completed.append("Documentation")
                    # Persist phase completion
                    if pipeline_state:
                        pipeline_state.mark_phase_completed("Documentation")
                        save_pipeline_state(pipeline_state, working_directory)
                print("✅ Documentation generated", file=sys.stderr)

                # Check if we should pause after Documentation
                pause_result = _check_and_handle_pause(
                    "Documentation",
                    working_directory,
                    pipeline_state,
                    phases_completed,
                    start_time,
                    test_iteration,
                    task_config,
                )
                if pause_result:
                    return pause_result
            else:
                print(
                    f"⚠️  Documentation generation failed: {docs_result.error}",
                    file=sys.stderr,
                )
                # Continue to deployment even if docs fail

        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 6: DEPLOY (GitHub)
        # ═══════════════════════════════════════════════════════════════════════
        deploy_skipped = _should_skip_phase("Deploy", pipeline_state, resume_from_phase)
        if deploy_skipped:
            print(
                "⏭️  Skipping Deploy phase (resuming from later phase)", file=sys.stderr
            )
            phases_completed.append("Deploy")
        else:
            # Deploy phase ALWAYS runs after Documentation completes (has its own 15-min timeout)
            print("\n🚀 Running Deploy phase...", file=sys.stderr)
            if pipeline_state:
                pipeline_state.mark_phase_started("Deploy")
                save_pipeline_state(pipeline_state, working_directory)

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
                if pipeline_state:
                    pipeline_state.mark_phase_completed("Deploy")
                    save_pipeline_state(pipeline_state, working_directory)
                print("✅ Deployed to GitHub", file=sys.stderr)

                # Check for pause after Deploy
                pause_result = _check_and_handle_pause(
                    "Deploy",
                    working_directory,
                    pipeline_state,
                    phases_completed,
                    start_time,
                    test_iteration,
                    task_config,
                )
                if pause_result:
                    return pause_result
            elif deploy_result.exit_code == 10:
                # Exit code 10 = build success, deployment skipped
                print(
                    "⚠️  Deployment skipped (GitHub CLI not available)", file=sys.stderr
                )
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

        # Mark pipeline as completed
        if pipeline_state:
            pipeline_state.state = PipelineState.COMPLETED
            save_pipeline_state(pipeline_state, working_directory)

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
            "pipeline_id": pipeline_state.pipeline_id if pipeline_state else None,
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
        # Persist failure state
        if pipeline_state:
            current_phase = pipeline_state.current_phase or "Unknown"
            pipeline_state.mark_failed(current_phase, str(e))
            save_pipeline_state(pipeline_state, working_directory)
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

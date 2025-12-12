"""Autonomous build with per-phase process spawning.

Each phase spawns as a separate subprocess with fresh context,
reading only the previous phase's .md handoff file.
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
    parse_architecture_markdown_baml,
)

# Import safety mechanisms
from tools.security.safety import enforce_sandbox_mode

# Import helper functions
from tools.mcp_utils.project_detection import detect_existing_codebase
from tools.mcp_utils.task_classification import detect_task_intent
from tools.mcp_utils.delegation import _write_delegation_metadata
from tools.mcp_utils.phase_execution import (
    run_phase,
    run_builder_phase,
    PhaseValidator,
    tests_passed,  # Re-enabled: Exit codes only indicate process success, not test results
)
from tools.mcp_utils.pipeline_state import (
    PipelineState,
    PipelineStateSnapshot,
    get_pipeline_state,
    save_pipeline_state,
    get_phases_from,
)

# Import safety mechanisms (Milestone 3)
from tools.mcp_utils.audit import (
    audit_pipeline_started,
    audit_pipeline_completed,
    audit_pipeline_failed,
    audit_phase_started,
    audit_phase_completed,
    audit_phase_failed,
    audit_preflight_started,
    audit_preflight_passed,
    audit_preflight_failed,
    audit_emergency_stop,
)
from tools.mcp_utils.preflight import (
    run_phase_preflight,
    get_phase_preflight_config,
)
from tools.mcp_utils.emergency_stop import (
    is_emergency_stop_active,
    get_emergency_stop_status,
)
from tools.mcp_utils.approval_gates import (
    ApprovalGateConfig,
    ApprovalStatus,
    check_approval_required,
    request_approval_for_phase,
    check_approval_status,
    get_default_risk_description,
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

    # HITL mode: AUTO-HANDOFF between phases
    # Human approval happens BEFORE each phase (via wait_for_acknowledgment)
    # but phases auto-trigger after the previous phase completes
    # pause_after_phases is NOT set - no pausing AFTER phases
    if execution_mode == "hitl" and not pause_after_phases:
        print(
            "🔧 HITL mode: auto-handoff enabled (approve prompts BEFORE each phase)",
            file=sys.stderr,
        )

    # Check for resume
    if resume_from_phase:
        existing_state = get_pipeline_state(working_directory)
        if existing_state:
            # Resuming from pause - update remaining phases
            # IMPORTANT: Filter out already-completed phases to prevent state corruption
            existing_state.mark_resumed()
            all_phases = get_phases_from(resume_from_phase)
            existing_state.phases_remaining = [
                p for p in all_phases if p not in existing_state.phases_completed
            ]
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
        "hitl": "Human-in-the-Loop mode (approve prompts before each phase, auto-handoff between phases)",
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
    working_directory: Optional[Path] = None,
) -> bool:
    """
    Check if a phase should be skipped (already completed or before resume point).

    Args:
        phase_name: Phase to check
        pipeline_state: Current pipeline state
        resume_from_phase: Phase to resume from (if resuming)
        working_directory: Working directory to check for existing outputs

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

    # Safety net: Check for existing phase outputs to avoid re-running completed work
    # This runs BEFORE pipeline_state check so it works even on fresh restarts
    # This handles cases where pipeline_state doesn't reflect reality (e.g., after crash/resume)
    if working_directory:
        cf_dir = working_directory / ".context-foundry"
        if phase_name == "Scout":
            # Scout is complete if scout-report.md exists with content
            scout_md = cf_dir / "scout-report.md"
            if scout_md.exists() and scout_md.stat().st_size > 100:
                print(
                    "⏭️ Skipping Scout: scout-report.md already exists", file=sys.stderr
                )
                return True
        elif phase_name == "Architect":
            # Architect is complete if architecture.md exists with content
            arch_md = cf_dir / "architecture.md"
            if arch_md.exists() and arch_md.stat().st_size > 100:
                print(
                    "⏭️ Skipping Architect: architecture.md already exists",
                    file=sys.stderr,
                )
                return True

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
    Load architecture.json - prefer existing JSON, fallback to parsing architecture.md.

    This is the production code path that:
    1. PREFER: Checks if .context-foundry/architecture.json already exists (Architect may create it directly)
    2. FALLBACK: Reads .context-foundry/architecture.md and parses it
       - Tries to parse with Claude CLI (free, uses desktop subscription)
       - Falls back to BAML if Claude CLI fails/unavailable
    3. Saves result to .context-foundry/architecture.json
    4. Handles timeouts and errors gracefully

    Returns:
        Dict with parsed architecture if successful, None if parsing failed or file missing
    """
    architecture_md_path = working_directory / ".context-foundry" / "architecture.md"
    architecture_json_path = (
        working_directory / ".context-foundry" / "architecture.json"
    )
    architecture_md = None
    architecture_json = None

    # PREFER: Check if architecture.json already exists (Architect agent may create it directly)
    if architecture_json_path.exists() and architecture_json_path.stat().st_size > 100:
        try:
            architecture_json = json.loads(architecture_json_path.read_text())
            log_debug(
                "✅ Loaded existing architecture.json (preferred)", working_directory
            )
            print(
                "✅ Using existing architecture.json (preferred over .md)",
                file=sys.stderr,
            )
            return architecture_json
        except Exception as e:
            log_debug(f"⚠️ Failed to load architecture.json: {e}", working_directory)
            # Fall through to BAML parse

    # FALLBACK: Parse architecture.md to JSON
    if not architecture_md_path.exists():
        log_debug(
            "⚠️ Architecture outputs missing (no .json or .md), skipping parse",
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

    Spawns a background process that executes phases sequentially.
    Each phase runs as a separate subprocess, releases context on exit.
    Returns immediately with task_id (non-blocking).

    Args:
        task: Build task description
        working_directory: Project directory path
        github_repo_name: Optional GitHub repo name
        existing_repo: Optional existing repo to enhance
        mode: "new_project", "enhance", or "bugfix"
        max_test_iterations: Max test/fix cycles (default 3)
        timeout_minutes: Build timeout (default 90)
        use_parallel: Override parallel builder detection
        incremental: Skip completed phases
        force_rebuild: Ignore cached results
        sandbox_path: Sandbox directory path
        sandbox_task_id: Sandbox task identifier
        active_tasks: Dictionary to track background processes

    Returns:
        JSON with task_id, status, message
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
        #   "weather-app" → ~/projects/weather-app (recommended)
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
    # AUTO-DETECT RESUME PHASE (when mode=resume but resume_from_phase not set)
    # ═══════════════════════════════════════════════════════════════════════
    if mode == "resume" and not resume_from_phase:
        # Try to load existing pipeline state to determine resume point
        existing_state = get_pipeline_state(working_directory)
        if existing_state and existing_state.phases_remaining:
            resume_from_phase = existing_state.phases_remaining[0]
            print(
                f"📍 Auto-detected resume point: {resume_from_phase}",
                file=sys.stderr,
            )
        elif existing_state and existing_state.phases_completed:
            # If no remaining phases but some completed, find next phase
            from tools.mcp_utils.pipeline_state import PHASE_ORDER

            last_completed = existing_state.phases_completed[-1]
            try:
                last_idx = PHASE_ORDER.index(last_completed)
                if last_idx + 1 < len(PHASE_ORDER):
                    resume_from_phase = PHASE_ORDER[last_idx + 1]
                    print(
                        f"📍 Auto-detected resume point (from completed): {resume_from_phase}",
                        file=sys.stderr,
                    )
            except ValueError:
                pass  # Phase not in order, fall through

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

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT: Pipeline started
    # ═══════════════════════════════════════════════════════════════════════
    audit_pipeline_started(
        working_directory=str(working_directory),
        task=task,
    )

    def run_preflight_for_phase(phase_name: str) -> Optional[Dict[str, Any]]:
        """Run preflight checks for a phase. Returns error dict if failed, None if passed."""
        config = get_phase_preflight_config(phase_name)
        if not config:
            return None  # No preflight config for this phase

        audit_preflight_started(phase_name, str(working_directory))

        result = run_phase_preflight(
            phase_name=phase_name,
            working_directory=working_directory,
            required_inputs=config.get("required_inputs"),
            json_inputs=config.get("json_inputs"),
            required_tools=config.get("required_tools"),
            custom_check=config.get("custom_check"),
        )

        if result.passed:
            audit_preflight_passed(phase_name, str(working_directory))
            if result.warnings:
                for warning in result.warnings:
                    print(f"⚠️  Preflight warning: {warning.message}", file=sys.stderr)
            return None
        else:
            failures = [{"name": f.name, "message": f.message} for f in result.failures]
            error_msg = f"Preflight checks failed: {result.failures[0].message}"
            audit_preflight_failed(phase_name, str(working_directory), failures)
            audit_phase_failed(phase_name, str(working_directory), error_msg)
            audit_pipeline_failed(str(working_directory), error_msg, phase_name)
            print(f"❌ Preflight failed for {phase_name}:", file=sys.stderr)
            for failure in result.failures:
                print(f"   - {failure.message}", file=sys.stderr)
            return {
                "status": "failed",
                "phase_failed": phase_name,
                "error": error_msg,
                "preflight_failures": failures,
            }

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
                # Audit: Phase and pipeline failed due to timeout
                audit_phase_failed(phase_name, str(working_directory), error_msg)
                audit_pipeline_failed(str(working_directory), error_msg, phase_name)
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

    def is_timeout_exceeded() -> bool:
        """Check if timeout exceeded (for optional phases that continue anyway)."""
        if timeout_minutes is not None:
            elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60
            return elapsed_minutes > timeout_minutes
        return False

    def run_optional_preflight(phase_name: str) -> bool:
        """Run preflight for optional phase. Returns True if passed, False if failed (but continues)."""
        config = get_phase_preflight_config(phase_name)
        if not config:
            return True
        audit_preflight_started(phase_name, str(working_directory))
        result = run_phase_preflight(
            phase_name=phase_name,
            working_directory=working_directory,
            required_inputs=config.get("required_inputs"),
            json_inputs=config.get("json_inputs"),
            required_tools=config.get("required_tools"),
            custom_check=config.get("custom_check"),
        )
        if result.passed:
            audit_preflight_passed(phase_name, str(working_directory))
            if result.warnings:
                for warning in result.warnings:
                    print(f"⚠️  Preflight warning: {warning.message}", file=sys.stderr)
            return True
        else:
            # Optional phase - warn but don't fail pipeline
            failures = [{"name": f.name, "message": f.message} for f in result.failures]
            audit_preflight_failed(phase_name, str(working_directory), failures)
            # Note: No audit_pipeline_failed for optional phases
            print(
                f"⚠️  Preflight issues for {phase_name} (continuing anyway):",
                file=sys.stderr,
            )
            for failure in result.failures:
                print(f"   - {failure.message}", file=sys.stderr)
            return False

    def check_emergency_stop(phase_name: str) -> Optional[Dict[str, Any]]:
        """Check if emergency stop is active. Returns error dict if stopped, None otherwise."""
        if is_emergency_stop_active():
            status = get_emergency_stop_status()
            reason = status.reason or "Emergency stop activated"
            error_msg = f"Emergency stop: {reason}"
            print(f"\n🛑 EMERGENCY STOP: {reason}", file=sys.stderr)
            print(
                f"   Activated by: {status.activated_by or 'unknown'}", file=sys.stderr
            )
            print(
                f"   Activated at: {status.activated_at or 'unknown'}", file=sys.stderr
            )
            print("\n   To resume: cfd emergency-resume", file=sys.stderr)
            # Persist cancelled state
            if pipeline_state:
                pipeline_state.mark_cancelled(reason)
                save_pipeline_state(pipeline_state, working_directory)
            # Audit: Emergency stop
            audit_emergency_stop(reason, str(working_directory), phase_name)
            return {
                "status": "cancelled",
                "phase_cancelled": phase_name,
                "error": error_msg,
                "emergency_stop": status.to_dict(),
                "start_time": start_time.isoformat(),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "phases_completed": phases_completed,
                "test_iterations": test_iteration,
            }
        return None

    def check_approval_gate(phase_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if approval is required for a phase.
        Returns waiting_approval dict if paused, None to proceed.
        Handles expired requests by re-requesting approval.

        NOTE: In HITL mode, approval is handled via wait_for_acknowledgment()
        in the phase prompts, so this gate is skipped.
        """
        # In HITL mode, approval happens via prompt acknowledgment, not this gate
        execution_mode = task_config.get("execution_mode", "autonomous")
        if execution_mode == "hitl":
            print(
                f"📝 {phase_name} approval handled via HITL prompt mechanism",
                file=sys.stderr,
            )
            return None  # Skip approval gate, HITL uses prompt acknowledgment

        skip_approval = task_config.get("skip_approval", False)
        if skip_approval:
            return None

        require_approval_phases = task_config.get("require_approval_phases", ["Deploy"])
        approval_config = ApprovalGateConfig(
            require_approval_phases=require_approval_phases
        )

        if not check_approval_required(phase_name, config=approval_config):
            return None

        # Check if approval already granted
        existing_approval = None
        if pipeline_state:
            existing_approval = check_approval_status(
                pipeline_state.pipeline_id, phase_name
            )

        if existing_approval:
            # Check for expiration first
            if existing_approval.is_expired():
                print(
                    "⏰ Previous approval request expired, requesting new approval...",
                    file=sys.stderr,
                )
                existing_approval = None  # Force re-request

            elif existing_approval.status == ApprovalStatus.APPROVED:
                print(
                    f"✅ {phase_name} approval granted, proceeding...", file=sys.stderr
                )
                return None  # Proceed

            elif existing_approval.status == ApprovalStatus.DENIED:
                # Approval was denied - skip phase
                print(
                    f"❌ {phase_name} approval denied, skipping phase", file=sys.stderr
                )
                phases_completed.append(phase_name)
                if pipeline_state:
                    pipeline_state.mark_phase_completed(phase_name)
                    save_pipeline_state(pipeline_state, working_directory)
                return {"skip_phase": True}  # Special marker to skip

        # No valid approval yet - request it and pause
        print(f"\n🔐 {phase_name} phase requires approval...", file=sys.stderr)

        if pipeline_state:
            # Create approval request
            approval_request = request_approval_for_phase(
                phase=phase_name,
                pipeline_state=pipeline_state,
                task_summary=task[:200],
                risk_description=get_default_risk_description(phase_name),
                changes_summary=f"Phases completed: {', '.join(phases_completed)}",
            )
            save_pipeline_state(pipeline_state, working_directory)

            elapsed = (datetime.now() - start_time).total_seconds()
            return {
                "status": "paused",  # Use "paused" so runner.py handles it correctly
                "paused_after": phases_completed[-1] if phases_completed else "none",
                "phases_completed": phases_completed,
                "waiting_phase": phase_name,
                "approval_request_id": approval_request.request_id,
                "message": f"{phase_name} phase requires approval. Run: cfd approve {approval_request.request_id[:8]}",
                "resume_command": pipeline_state.get_resume_command(working_directory),
                "working_directory": str(working_directory),
                "elapsed_seconds": elapsed,
            }
        else:
            # No pipeline state - skip approval in autonomous mode
            print("⚠️  No pipeline state, skipping approval check", file=sys.stderr)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # EMERGENCY STOP CHECK: Before any phases run
    # ═══════════════════════════════════════════════════════════════════════
    emergency_result = check_emergency_stop("Pipeline Start")
    if emergency_result:
        return emergency_result

    try:
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 1: SCOUT
        # ═══════════════════════════════════════════════════════════════════════
        # Check if spec mode is enabled (user provided spec files)
        spec_files = task_config.get("spec_files", [])
        is_spec_mode = bool(spec_files)

        # Check if phase should be skipped (already completed or resuming from later phase)
        scout_skipped = _should_skip_phase(
            "Scout", pipeline_state, resume_from_phase, working_directory
        )

        # In spec mode, always skip Scout - user's spec replaces Scout's job
        if is_spec_mode and not scout_skipped:
            print(
                "📋 SPEC MODE: Skipping Scout phase (building from spec files)",
                file=sys.stderr,
            )
            print(f"   Spec files: {spec_files}", file=sys.stderr)
            scout_skipped = True
            # Mark Scout as completed even though we skipped it
            if "Scout" not in phases_completed:
                phases_completed.append("Scout")
                if pipeline_state:
                    pipeline_state.mark_phase_completed("Scout")
                    save_pipeline_state(pipeline_state, working_directory)

        if scout_skipped:
            print("⏭️  Skipping Scout phase (already completed)", file=sys.stderr)
            # Scout report is in scout-report.md - no JSON needed
        else:
            # Check emergency stop before starting phase
            emergency_result = check_emergency_stop("Scout")
            if emergency_result:
                return emergency_result

            # Check approval gate (configurable via require_approval_phases)
            approval_result = check_approval_gate("Scout")
            if approval_result:
                if approval_result.get("skip_phase"):
                    pass  # Phase skipped due to denial, continue to next
                else:
                    return approval_result  # Waiting for approval

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

            # Run preflight checks
            preflight_error = run_preflight_for_phase("Scout")
            if preflight_error:
                return preflight_error

            # Audit: Phase started
            audit_phase_started("Scout", str(working_directory))

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
                    "Analyze the project requirements and create a scout report. "
                    "Output: .context-foundry/scout-report.md"
                )
                scout_result = run_phase(
                    "Scout",
                    scout_prompt,
                    f"{scout_instruction}\n\n{scout_task}",
                    working_directory,
                    phase_timeout=600,  # 10 min
                    validator=PhaseValidator.validate_scout,
                    project_type=project_type,
                    task_config=task_config,
                )

                results["scout"] = scout_result

                if scout_result.status != "completed":
                    error_msg = scout_result.error or "Scout phase failed"
                    # Persist failure state
                    if pipeline_state:
                        pipeline_state.mark_failed("Scout", error_msg)
                        save_pipeline_state(pipeline_state, working_directory)
                    # Audit: Phase and pipeline failed
                    audit_phase_failed("Scout", str(working_directory), error_msg)
                    audit_pipeline_failed(str(working_directory), error_msg, "Scout")
                    return {
                        "status": "failed",
                        "phase_failed": "Scout",
                        "error": error_msg,
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
                # Audit: Phase completed
                audit_phase_completed("Scout", str(working_directory))

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

        # Scout phase creates scout-report.md - no JSON parsing needed
        # Agents communicate via markdown files only
        if not scout_skipped:
            scout_md_path = working_directory / ".context-foundry" / "scout-report.md"
            if scout_md_path.exists():
                log_debug("✅ Scout report exists: scout-report.md", working_directory)
                print("✅ Scout phase complete: scout-report.md", file=sys.stderr)
            else:
                log_debug("⚠️ Scout report missing: scout-report.md", working_directory)

        # ═══════════════════════════════════════════════════════════════════════
        # FLOWISE CODEX VALIDATION - Enforce pattern queries
        # ═══════════════════════════════════════════════════════════════════════
        if flowise_mode:
            print("🔍 Validating Flowise codex queries...", file=sys.stderr)
            try:
                PhaseValidator.validate_flowise_codex_queries(working_directory)
            except ValueError as e:
                error_msg = str(e)
                # Audit: Phase and pipeline failed
                audit_phase_failed("Scout", str(working_directory), error_msg)
                audit_pipeline_failed(str(working_directory), error_msg, "Scout")
                return {
                    "status": "failed",
                    "phase_failed": "Scout",
                    "error": error_msg,
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
            "Architect", pipeline_state, resume_from_phase, working_directory
        )

        if architect_skipped:
            print("⏭️  Skipping Architect phase (already completed)", file=sys.stderr)
            # Architecture is in architecture.md - no JSON needed
        else:
            # Check emergency stop before starting phase
            emergency_result = check_emergency_stop("Architect")
            if emergency_result:
                return emergency_result

            # Check approval gate (configurable via require_approval_phases)
            approval_result = check_approval_gate("Architect")
            if approval_result:
                if approval_result.get("skip_phase"):
                    pass  # Phase skipped due to denial, continue to next
                else:
                    return approval_result  # Waiting for approval

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

            # Run preflight checks
            preflight_error = run_preflight_for_phase("Architect")
            if preflight_error:
                return preflight_error

            # Audit: Phase started
            audit_phase_started("Architect", str(working_directory))

            # Choose prompt based on spec mode
            if is_spec_mode:
                # SPEC MODE: Use extraction prompt instead of design prompt
                architect_prompt = (
                    MODULE_DIR / "prompts" / "phases" / "phase_architect_spec_mode.txt"
                )
                print(
                    "📋 SPEC MODE: Using extraction prompt for Architect",
                    file=sys.stderr,
                )

                # Read spec files and inject their contents
                spec_contents = []
                for spec_file in spec_files:
                    spec_path = Path(spec_file)
                    if spec_path.exists():
                        try:
                            content = spec_path.read_text()
                            spec_contents.append(
                                f"### File: {spec_path.name}\n"
                                f"Path: {spec_file}\n\n"
                                f"```\n{content}\n```"
                            )
                            print(f"   ✓ Loaded spec: {spec_file}", file=sys.stderr)
                        except Exception as e:
                            print(
                                f"   ⚠ Failed to read spec {spec_file}: {e}",
                                file=sys.stderr,
                            )
                    else:
                        print(f"   ⚠ Spec file not found: {spec_file}", file=sys.stderr)

                if spec_contents:
                    architect_instruction = (
                        "EXTRACT (do not invent) from the following specification file(s).\n"
                        "Create architecture.md with Gherkin acceptance criteria.\n\n"
                        "SPECIFICATION FILES:\n\n" + "\n\n".join(spec_contents)
                    )
                else:
                    architect_instruction = (
                        "ERROR: No spec files could be loaded. "
                        f"Attempted to read: {spec_files}"
                    )
                log_debug("SPEC MODE: Injecting spec file contents", working_directory)
            else:
                # NORMAL MODE: Use standard design prompt
                architect_prompt = (
                    MODULE_DIR / "prompts" / "phases" / "phase_architect.txt"
                )

                # Inject scout report as markdown (more token-efficient for LLM consumption)
                scout_md_path = (
                    working_directory / ".context-foundry" / "scout-report.md"
                )
                if scout_md_path.exists() and scout_md_path.stat().st_size > 100:
                    scout_content = scout_md_path.read_text()
                    architect_instruction = (
                        "Create architecture.md based on the following scout report.\n\n"
                        "SCOUT_REPORT:\n" + scout_content
                    )
                    log_debug("Injecting scout-report.md (markdown)", working_directory)
                else:
                    architect_instruction = "Read .context-foundry/scout-report.md and create architecture.md."
                    log_debug(
                        "Scout report not found, architect will read directly",
                        working_directory,
                    )

            architect_result = run_phase(
                "Architect",
                architect_prompt,
                architect_instruction,
                working_directory,
                phase_timeout=900,  # 15 min
                validator=PhaseValidator.validate_architect,
                project_type=project_type,
                task_config=task_config,
            )

            results["architect"] = architect_result

            print(
                f"[TRACE] Architect phase result: status={architect_result.status}, "
                f"exit_code={architect_result.exit_code}, duration={architect_result.duration_seconds:.1f}s",
                file=sys.stderr,
            )

            if architect_result.status != "completed":
                error_msg = architect_result.error or "Architect phase failed"
                # Persist failure state
                if pipeline_state:
                    pipeline_state.mark_failed("Architect", error_msg)
                    save_pipeline_state(pipeline_state, working_directory)
                # Audit: Phase and pipeline failed
                audit_phase_failed("Architect", str(working_directory), error_msg)
                audit_pipeline_failed(str(working_directory), error_msg, "Architect")
                return {
                    "status": "failed",
                    "phase_failed": "Architect",
                    "error": error_msg,
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
                # Audit: Phase completed
                audit_phase_completed("Architect", str(working_directory))

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

        # Verify architecture.md exists (no JSON parsing needed - agents communicate via MD files)
        arch_md_path = working_directory / ".context-foundry" / "architecture.md"
        if arch_md_path.exists():
            log_debug("✅ Architecture exists: architecture.md", working_directory)
            print("✅ Architect phase complete: architecture.md", file=sys.stderr)
        else:
            log_debug("⚠️ Architecture missing: architecture.md", working_directory)

        # ═══════════════════════════════════════════════════════════════════════
        # PARALLEL BUILD DECISION (based on Scout markdown)
        # ═══════════════════════════════════════════════════════════════════════
        # Builder agent will create build-tasks.md - no BAML build plan generation needed
        # Agents communicate via markdown files only

        if use_parallel is None:
            # Check Scout report for parallel build recommendation
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
                        "\n🚀 Parallel builds ENABLED (Scout recommendation)",
                        file=sys.stderr,
                    )
                else:
                    use_parallel = False
            else:
                use_parallel = False

        if use_parallel:
            print(
                "ℹ️  Builder will create build-tasks.md for parallel execution",
                file=sys.stderr,
            )
        else:
            print("📦 Sequential build mode", file=sys.stderr)

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
            # Check emergency stop before starting phase
            emergency_result = check_emergency_stop("Builder")
            if emergency_result:
                return emergency_result

            # Check approval gate (configurable via require_approval_phases)
            approval_result = check_approval_gate("Builder")
            if approval_result:
                if approval_result.get("skip_phase"):
                    pass  # Phase skipped due to denial, continue to next
                else:
                    return approval_result  # Waiting for approval

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

            # Run preflight checks
            preflight_error = run_preflight_for_phase("Builder")
            if preflight_error:
                return preflight_error

            # Audit: Phase started
            audit_phase_started("Builder", str(working_directory))

            # FIX #4: Use module-relative path
            builder_prompt = MODULE_DIR / "prompts" / "phases" / "phase_builder.txt"

            # Inject architecture as markdown (more token-efficient for LLM consumption)
            arch_md_path = working_directory / ".context-foundry" / "architecture.md"
            if arch_md_path.exists() and arch_md_path.stat().st_size > 100:
                arch_content = arch_md_path.read_text()
                builder_instruction = (
                    "Implement the project according to the following architecture.\n\n"
                    "ARCHITECTURE:\n" + arch_content
                )
                log_debug("Injecting architecture.md (markdown)", working_directory)
            else:
                builder_instruction = (
                    "Read .context-foundry/architecture.md and implement the project."
                )
                log_debug(
                    "Architecture not found, builder will read directly",
                    working_directory,
                )

            builder_result = run_builder_phase(
                builder_prompt,
                builder_instruction,
                working_directory,
                project_type,
                flowise_mode=flowise_mode,
                use_parallel=use_parallel,
                task_config=task_config,
            )

            results["builder"] = builder_result

            if builder_result.status != "completed":
                error_msg = builder_result.error or "Builder phase failed"
                # Persist failure state
                if pipeline_state:
                    pipeline_state.mark_failed("Builder", error_msg)
                    save_pipeline_state(pipeline_state, working_directory)
                # Audit: Phase and pipeline failed
                audit_phase_failed("Builder", str(working_directory), error_msg)
                audit_pipeline_failed(str(working_directory), error_msg, "Builder")
                return {
                    "status": "failed",
                    "phase_failed": "Builder",
                    "error": error_msg,
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
                # Audit: Phase completed
                audit_phase_completed("Builder", str(working_directory))

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
            # Check emergency stop before starting test phase
            emergency_result = check_emergency_stop("Test")
            if emergency_result:
                return emergency_result

            # Check approval gate (configurable via require_approval_phases)
            approval_result = check_approval_gate("Test")
            if approval_result:
                if approval_result.get("skip_phase"):
                    pass  # Phase skipped due to denial, continue to next
                else:
                    return approval_result  # Waiting for approval

            # Check timeout before starting test phase
            timeout_result = check_timeout("Test")
            if timeout_result:
                return timeout_result

            test_passed = False
            architect_file = ".context-foundry/architecture.md"

            # FIX #4: Use module-relative path
            test_prompt = MODULE_DIR / "prompts" / "phases" / "phase_test.txt"

            # FIX: Define architect_prompt here so it's available for self-healing loop
            # (When resuming from Builder/Test, Architect phase is skipped, so architect_prompt
            # wasn't defined. But the self-healing loop needs it to run Architect fixes.)
            architect_prompt = MODULE_DIR / "prompts" / "phases" / "phase_architect.txt"

            while test_iteration <= max_test_iterations:
                # Check emergency stop at start of each test iteration
                emergency_result = check_emergency_stop(
                    f"Test-Iteration-{test_iteration}"
                )
                if emergency_result:
                    return emergency_result

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

                    # Run preflight checks (only on first iteration)
                    preflight_error = run_preflight_for_phase("Test")
                    if preflight_error:
                        return preflight_error

                    # Audit: Phase started
                    audit_phase_started("Test", str(working_directory))

                test_file = f".context-foundry/test-report{'-' + str(test_iteration) if test_iteration > 0 else ''}.md"

                # Inject architecture for test context
                arch_md_path = (
                    working_directory / ".context-foundry" / "architecture.md"
                )
                if arch_md_path.exists() and arch_md_path.stat().st_size > 100:
                    arch_content = arch_md_path.read_text()
                    test_instruction = (
                        f"Run all tests and write results to {test_file}.\n\n"
                        f"ARCHITECTURE:\n{arch_content}"
                    )
                else:
                    test_instruction = f"Run all tests and write results to {test_file}"

                # FIX #3: Pass expected test file to run_phase for validation
                test_result = run_phase(
                    "Test",
                    test_prompt,
                    test_instruction,
                    working_directory,
                    phase_timeout=1200,  # 20 min
                    validator=lambda wd: _validate_test_with_filename(wd, test_file),
                    iteration=test_iteration,
                    project_type=project_type,
                    task_config=task_config,
                )

                results[f"test_{test_iteration}"] = test_result

                # Check if tests passed by parsing the test report
                # NOTE: Exit codes only indicate process success, not test results!
                # Claude exits with code 0 even when it writes "FAILED" in the report.
                test_report_path = working_directory / test_file
                if test_report_path.exists() and tests_passed(test_report_path):
                    print(
                        f"✅ Tests PASSED (iteration {test_iteration}) - verified from {test_file}",
                        file=sys.stderr,
                    )
                    test_passed = True
                    break

                # Tests failed (report says FAILED or file doesn't exist)
                print(
                    f"❌ Tests FAILED (iteration {test_iteration}) - verified from {test_file}",
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

                # Read test report and architecture for context injection
                test_report_path = working_directory / test_file
                arch_path = working_directory / architect_file

                test_content = (
                    test_report_path.read_text() if test_report_path.exists() else ""
                )
                arch_content = arch_path.read_text() if arch_path.exists() else ""

                fix_instruction = (
                    f"FIX ITERATION MODE\n\n"
                    f"Analyze test failures and create a fix plan.\n"
                    f"Write fix plan to {architect_fix_file}.\n\n"
                    f"CRITICAL: You are an ARCHITECT, not a BUILDER!\n"
                    f"- DO NOT implement code changes yourself\n"
                    f"- ONLY create {architect_fix_file} with the fix specification\n"
                    f"- Builder will implement your plan in the next phase\n\n"
                    f"TEST_REPORT ({test_file}):\n{test_content}\n\n"
                    f"ARCHITECTURE:\n{arch_content}"
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
                    task_config=task_config,
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
                    # Audit: Phase and pipeline failed
                    audit_phase_failed(
                        "Architect (fix validation)", str(working_directory), error_msg
                    )
                    audit_pipeline_failed(
                        str(working_directory), error_msg, "Architect (fix validation)"
                    )
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
                        # Report 1-based count of iterations run
                        "test_iterations": test_iteration + 1,
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

                # Run Builder with fixed architecture - inject fix plan content
                fix_file_path = working_directory / architect_fix_file
                fix_content = (
                    fix_file_path.read_text() if fix_file_path.exists() else ""
                )

                builder_fix_instruction = (
                    f"FIX ITERATION MODE\n\n"
                    f"Implement the fixes specified below. Focus on test failures only.\n\n"
                    f"FIX_PLAN ({architect_fix_file}):\n{fix_content}"
                )

                builder_fix_result = run_builder_phase(
                    builder_prompt,
                    builder_fix_instruction,
                    working_directory,
                    project_type,
                    flowise_mode=flowise_mode,
                    use_parallel=False,  # Fixes are small
                    iteration=test_iteration,
                    task_config=task_config,
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
                # Audit: Phase completed
                audit_phase_completed("Test", str(working_directory))

            if not test_passed:
                error_msg = f"Tests failed after {test_iteration} iteration(s)"
                # Audit: Phase and pipeline failed
                audit_phase_failed("Test", str(working_directory), error_msg)
                audit_pipeline_failed(str(working_directory), error_msg, "Test")
                # Persist failure state
                if pipeline_state:
                    pipeline_state.mark_failed("Test", error_msg)
                    save_pipeline_state(pipeline_state, working_directory)
                return {
                    "status": "failed",
                    "phase_failed": "Test",
                    "error": error_msg,
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
            # Check emergency stop before starting phase
            emergency_result = check_emergency_stop("Screenshot")
            if emergency_result:
                return emergency_result

            # Check approval gate (configurable via require_approval_phases)
            approval_result = check_approval_gate("Screenshot")
            if approval_result:
                if approval_result.get("skip_phase"):
                    pass  # Phase skipped due to denial, continue to next
                else:
                    return approval_result  # Waiting for approval

            # Screenshot phase ALWAYS runs after Test completes (has its own 10-min timeout)
            print("\n🖼️  Running Screenshot phase...", file=sys.stderr)

            # Mark phase as started for visibility
            if pipeline_state:
                pipeline_state.mark_phase_started("Screenshot")
                save_pipeline_state(pipeline_state, working_directory)
            # Audit: Phase started
            audit_phase_started("Screenshot", str(working_directory))

            # Run preflight for optional phase (warns but doesn't fail)
            run_optional_preflight("Screenshot")

            # Use is_timeout_exceeded for optional phases (no audit_pipeline_failed)
            if is_timeout_exceeded():
                print(
                    "⚠️  Build timeout exceeded, but running Screenshot anyway (max 10 min)",
                    file=sys.stderr,
                )

            screenshot_prompt = (
                MODULE_DIR / "prompts" / "phases" / "phase_screenshot.txt"
            )
            screenshot_instruction = (
                "Follow the SCREENSHOT PHASE INSTRUCTIONS in the prompt.\n"
                "Capture screenshots of key pages and save to .context-foundry/screenshots/."
            )

            screenshot_result = run_phase(
                "Screenshot",
                screenshot_prompt,
                screenshot_instruction,
                working_directory,
                phase_timeout=600,  # 10 min
                project_type=project_type,
                task_config=task_config,
            )

            # Screenshot is optional - don't fail build if it doesn't work
            if screenshot_result.status == "completed":
                if "Screenshot" not in phases_completed:
                    phases_completed.append("Screenshot")
                    # Persist phase completion
                    if pipeline_state:
                        pipeline_state.mark_phase_completed("Screenshot")
                        save_pipeline_state(pipeline_state, working_directory)
                    # Audit: Phase completed
                    audit_phase_completed("Screenshot", str(working_directory))
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
                # Audit: Phase failed (but not pipeline - optional phase)
                audit_phase_failed(
                    "Screenshot",
                    str(working_directory),
                    screenshot_result.error or "Screenshot capture failed",
                )
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
            # Check emergency stop before starting phase
            emergency_result = check_emergency_stop("Documentation")
            if emergency_result:
                return emergency_result

            # Check approval gate (configurable via require_approval_phases)
            approval_result = check_approval_gate("Documentation")
            if approval_result:
                if approval_result.get("skip_phase"):
                    pass  # Phase skipped due to denial, continue to next
                else:
                    return approval_result  # Waiting for approval

            # Documentation phase ALWAYS runs after Screenshot completes (has its own 10-min timeout)
            print("\n📝 Running Documentation phase...", file=sys.stderr)

            # Mark phase as started for visibility
            if pipeline_state:
                pipeline_state.mark_phase_started("Documentation")
                save_pipeline_state(pipeline_state, working_directory)
            # Audit: Phase started
            audit_phase_started("Documentation", str(working_directory))

            # Run preflight for optional phase (warns but doesn't fail)
            run_optional_preflight("Documentation")

            # Use is_timeout_exceeded for optional phases (no audit_pipeline_failed)
            if is_timeout_exceeded():
                print(
                    "⚠️  Build timeout exceeded, but running Documentation anyway (max 10 min)",
                    file=sys.stderr,
                )

            docs_prompt = MODULE_DIR / "prompts" / "phases" / "phase_documentation.txt"
            docs_instruction = (
                "Follow the DOCUMENTATION PHASE INSTRUCTIONS in the prompt.\n"
                "Generate comprehensive README.md with project overview, installation, and usage."
            )

            docs_result = run_phase(
                "Documentation",
                docs_prompt,
                docs_instruction,
                working_directory,
                phase_timeout=600,  # 10 min
                project_type=project_type,
                task_config=task_config,
            )

            if docs_result.status == "completed":
                if "Documentation" not in phases_completed:
                    phases_completed.append("Documentation")
                    # Persist phase completion
                    if pipeline_state:
                        pipeline_state.mark_phase_completed("Documentation")
                        save_pipeline_state(pipeline_state, working_directory)
                    # Audit: Phase completed
                    audit_phase_completed("Documentation", str(working_directory))
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
                # Audit: Phase failed (but not pipeline - optional phase)
                audit_phase_failed(
                    "Documentation",
                    str(working_directory),
                    docs_result.error or "Documentation generation failed",
                )
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
            # Check emergency stop before starting phase
            emergency_result = check_emergency_stop("Deploy")
            if emergency_result:
                return emergency_result

            # Check approval gate (configurable via require_approval_phases)
            approval_result = check_approval_gate("Deploy")
            if approval_result:
                if approval_result.get("skip_phase"):
                    pass  # Phase skipped due to denial, continue to next
                else:
                    return approval_result  # Waiting for approval

            # Deploy phase ALWAYS runs after Documentation completes (has its own 15-min timeout)
            print("\n🚀 Running Deploy phase...", file=sys.stderr)
            if pipeline_state:
                pipeline_state.mark_phase_started("Deploy")
                save_pipeline_state(pipeline_state, working_directory)
            # Audit: Phase started
            audit_phase_started("Deploy", str(working_directory))

            # Run preflight for optional phase (warns but doesn't fail)
            run_optional_preflight("Deploy")

            # Use is_timeout_exceeded for optional phases (no audit_pipeline_failed)
            if is_timeout_exceeded():
                print(
                    "⚠️  Build timeout exceeded, but running Deploy anyway (max 10 min)",
                    file=sys.stderr,
                )

            deploy_prompt = MODULE_DIR / "prompts" / "phases" / "phase_deploy.txt"

            # Determine repository name
            github_repo_name = task_config.get("github_repo_name")
            repo_name = github_repo_name or working_directory.name

            deploy_instruction = (
                f"Follow the DEPLOY PHASE INSTRUCTIONS in the prompt.\n"
                f"Deploy to GitHub as repo: {repo_name}\n"
                f"Use gh repo create if needed."
            )

            deploy_result = run_phase(
                "Deploy",
                deploy_prompt,
                deploy_instruction,
                working_directory,
                phase_timeout=600,  # 10 min
                project_type=project_type,
                task_config=task_config,
            )

            # Deploy is optional - don't fail build if GitHub unavailable
            if deploy_result.status == "completed":
                phases_completed.append("Deploy")
                if pipeline_state:
                    pipeline_state.mark_phase_completed("Deploy")
                    save_pipeline_state(pipeline_state, working_directory)
                # Audit: Phase completed
                audit_phase_completed("Deploy", str(working_directory))
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
                # Audit: Phase failed (but not pipeline - optional phase)
                audit_phase_failed(
                    "Deploy",
                    str(working_directory),
                    deploy_result.error or "Deployment failed",
                )
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

        # Audit: Pipeline completed
        audit_pipeline_completed(str(working_directory), phases_completed)

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
        current_phase = None
        # Persist failure state
        if pipeline_state:
            current_phase = pipeline_state.current_phase or "Unknown"
            pipeline_state.mark_failed(current_phase, str(e))
            save_pipeline_state(pipeline_state, working_directory)
        # Audit: Pipeline failed
        audit_pipeline_failed(str(working_directory), str(e), current_phase)
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

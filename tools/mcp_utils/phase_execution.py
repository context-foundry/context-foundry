"""
Phase Execution - Per-phase process spawning with fresh contexts.

Implements:
- PhaseValidator: Phase-specific output validation
- run_phase(): Core phase runner with subprocess.run()
- run_builder_phase(): Builder with parallelization support
- tests_passed(): Test result parser
- BAML-enforced phase tracking
"""

import copy
import json
import logging
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from tools.baml_integration import (
    get_baml_error,
    is_baml_available,
    update_phase_with_baml,
)
from tools.mcp_utils.phase_metrics import estimate_context_tokens, log_phase_metrics

# Module logger
logger = logging.getLogger(__name__)

CF_ROOT = Path(__file__).resolve().parents[2]


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
    def get_extension_patterns_dir(extension_name: str) -> Path:
        """
        Return the pattern directory for a given extension relative to the Context Foundry root.
        """
        return CF_ROOT / "extensions" / extension_name / "patterns"

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

            if "PhaseInfo" in phase_data and isinstance(phase_data["PhaseInfo"], dict):
                phase_data = phase_data["PhaseInfo"]

            if "phase" not in phase_data:
                camel_phase = phase_data.get("currentPhase") or phase_data.get(
                    "current_phase"
                )
                if camel_phase:
                    phase_data["phase"] = camel_phase

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
    def validate_flowise_codex_queries(working_dir: Path) -> bool:
        """
        Validate Scout performed mandatory Codex queries for Flowise projects.

        Returns True if validation passes, raises ValueError if queries missing.
        Returns True (pass) for non-Flowise projects.
        """
        scout_report = working_dir / ".context-foundry" / "scout-report.md"
        if not scout_report.exists():
            return True  # Let validate_scout handle missing file

        content = scout_report.read_text()

        # Check if this is a Flowise project
        flowise_indicators = [
            "flowise",
            "agentflow",
            "workflow json",
            "conditionagent",
        ]
        is_flowise = any(
            indicator in content.lower() for indicator in flowise_indicators
        )

        if not is_flowise:
            return True  # Not a Flowise project, skip validation

        # For Flowise projects, check for evidence of codex queries
        # Validation accepts any 2 matches from this list (case-insensitive partial match)
        codex_evidence = [
            # Actual Codex pattern IDs (partial matches work)
            "pat-agentflow-v22-routing-pattern",
            "pat-flowise-conditionagent",
            "pat-routing-pattern-synthesizer",
            "pat-use-executeflow-nodes",
            # Actual Codex issue IDs
            "iss-flowise-agentflow-v22",
            "iss-directreply-variable-syntax",
            # Legacy pattern IDs from flowise-expertise.json
            "afv2-routing-pattern",
            "afv2-rag-pattern",
            "flowise-missing-inputparams",
            "flowise-missing-start-node",
            # Pattern numbers that Scout references
            "Pattern #8",
            "Pattern #6",
            "Pattern #10",
            "Pattern #11",
            "Pattern #3",
            "Pattern #13",
            "Pattern #14",
            "Pattern #15",
            # Template file references (from Scout's Context Codex Research section)
            "CONDITIONAGENT-NODE-TEMPLATE",
            "AGENT-NODE-TEMPLATE",
            "03-routing.json",
            # General codex mentions
            "codex_search",
            "codex_get_entry",
            "Context Codex",
            "queried codex",
            "from codex",
            "Pre-queried",
            "Patterns Applied",
        ]

        found_evidence = [e for e in codex_evidence if e.lower() in content.lower()]

        if len(found_evidence) < 2:  # Require at least 2 pieces of evidence
            raise ValueError(
                f"⚠️ Flowise Scout MUST query Context Codex for patterns!\n"
                f"Found only {len(found_evidence)} codex references: {found_evidence}\n"
                f"Scout should have called:\n"
                f"  - codex_search('flowise routing pattern')\n"
                f"  - codex_search('flowise missing start node')\n"
                f"  - codex_get_entry('afv2-routing-pattern')\n"
                f"Re-run Scout with proper codex queries."
            )

        print(
            f"✅ Flowise codex validation passed: {len(found_evidence)} references found",
            file=sys.stderr,
        )
        return True

    @staticmethod
    def validate_flowise_reference_exists() -> bool:
        """
        Verify the Flowise pattern directory exists before building.

        Returns True whether or not the directory exists (missing directories are allowed but logged).
        """
        patterns_dir = PhaseValidator.get_extension_patterns_dir("flowise")
        if not patterns_dir.exists():
            print(
                f"⚠️ Flowise pattern directory not found: {patterns_dir} (continuing without reference)",
                file=sys.stderr,
            )
            return True

        pattern_files = list(patterns_dir.glob("*.json"))
        if not pattern_files:
            print(
                f"⚠️ Flowise pattern directory is empty: {patterns_dir} (continuing without reference files)",
                file=sys.stderr,
            )
            return True

        print(
            f"✅ Flowise pattern directory loaded: {patterns_dir} ({len(pattern_files)} files)",
            file=sys.stderr,
        )
        return True

    @staticmethod
    def validate_flowise_flow_quality(working_dir: Path) -> bool:
        """
        Validate generated Flowise flow meets quality standards.

        Checks:
        1. Line count >= 1500 (not abbreviated)
        2. Agent nodes have inputParams arrays
        3. agentMessages is array with role/content (not string)
        4. agentToolConfig exists in tools
        5. Nodes have required metadata (color, baseClasses, category)

        Returns True if quality passes, raises ValueError with specific failures.
        """
        # Find Flowise workflow JSON - scan root AND subdirectories (e.g., flows/)
        workflow_files = list(working_dir.glob("*.json")) + list(
            working_dir.rglob("flows/*.json")
        )
        flowise_jsons = [
            f
            for f in workflow_files
            if f.name not in ["package.json", "tsconfig.json", "build-tasks.json"]
        ]

        if not flowise_jsons:
            raise FileNotFoundError(
                "No Flowise workflow JSON found for quality validation.\n"
                "Checked: root directory and flows/ subdirectory"
            )

        errors = []
        warnings = []

        for json_file in flowise_jsons:
            try:
                content = json_file.read_text()
                line_count = len(content.splitlines())
                flow_data = json.load(open(json_file))

                # Check 1: Line count
                if line_count < 1500:
                    errors.append(
                        f"❌ {json_file.name}: Only {line_count} lines (minimum 1500).\n"
                        f"   Flow is abbreviated - missing complete node structures."
                    )
                elif line_count < 2000:
                    warnings.append(
                        f"⚠️ {json_file.name}: {line_count} lines (reference has 2299)."
                    )
                else:
                    print(
                        f"✅ {json_file.name}: {line_count} lines - good",
                        file=sys.stderr,
                    )

                nodes = flow_data.get("nodes", [])
                agent_nodes = [
                    n for n in nodes if n.get("data", {}).get("type") == "Agent"
                ]

                for node in agent_nodes:
                    node_id = node.get("id", "unknown")
                    data = node.get("data", {})

                    # Check 2: Per-node size validation (should be 100+ lines when formatted)
                    node_json = json.dumps(node, indent=2)
                    node_lines = len(node_json.splitlines())
                    if node_lines < 100:
                        errors.append(
                            f"❌ Node {node_id}: Only {node_lines} lines (minimum 100 per agent).\n"
                            f"   Agent nodes need complete inputParams, tools, and metadata.\n"
                            f"   Reference agents are 150-200+ lines each."
                        )

                    # Check 3: inputParams exists and is substantial
                    input_params = data.get("inputParams", [])
                    if not input_params:
                        errors.append(
                            f"❌ Node {node_id}: Missing inputParams array.\n"
                            f"   This causes UI rendering failures in Flowise."
                        )
                    elif len(input_params) < 3:
                        errors.append(
                            f"❌ Node {node_id}: inputParams has only {len(input_params)} items.\n"
                            f"   Complete agents need 5+ params (Model, Messages, Tools, Memory, State)."
                        )

                    inputs = data.get("inputs", {})

                    # Check 4: agentMessages is array with role/content
                    agent_messages = inputs.get("agentMessages")
                    if agent_messages is not None:
                        if isinstance(agent_messages, str):
                            errors.append(
                                f"❌ Node {node_id}: agentMessages is a string, not array.\n"
                                f"   Must be: [{{'role': 'system', 'content': '...'}}]"
                            )
                        elif isinstance(agent_messages, list):
                            for i, msg in enumerate(agent_messages):
                                if isinstance(msg, dict):
                                    if "role" not in msg or "content" not in msg:
                                        errors.append(
                                            f"❌ Node {node_id}: agentMessages[{i}] missing role/content."
                                        )

                    # Check 5: agentToolConfig in tools
                    agent_tools = inputs.get("agentTools", [])
                    if agent_tools:
                        for i, tool in enumerate(agent_tools):
                            if isinstance(tool, dict):
                                if "agentSelectedToolConfig" not in tool:
                                    errors.append(
                                        f"❌ Node {node_id}: agentTools[{i}] missing agentSelectedToolConfig.\n"
                                        f"   Each tool needs nested config structure."
                                    )

                    # Check 6: Node metadata
                    missing_meta = []
                    if "color" not in data:
                        missing_meta.append("color")
                    if "baseClasses" not in data:
                        missing_meta.append("baseClasses")
                    if "category" not in data:
                        missing_meta.append("category")
                    if "description" not in data:
                        missing_meta.append("description")

                    if missing_meta:
                        errors.append(
                            f"❌ Node {node_id}: Missing metadata: {', '.join(missing_meta)}.\n"
                            f"   Required for proper UI rendering."
                        )

                    # Check node dimensions
                    if "width" not in node or "height" not in node:
                        warnings.append(
                            f"⚠️ Node {node_id}: Missing width/height dimensions."
                        )

            except json.JSONDecodeError as e:
                errors.append(f"❌ {json_file.name}: Invalid JSON - {e}")
            except Exception as e:
                errors.append(f"❌ {json_file.name}: Validation error - {e}")

        # Report warnings
        for warning in warnings:
            print(warning, file=sys.stderr)

        # Fail on errors
        if errors:
            error_summary = "\n\n".join(errors)
            raise ValueError(
                f"⚠️ Flowise flow quality validation FAILED:\n\n{error_summary}\n\n"
                f"Builder must produce flows matching the patterns in "
                f"{PhaseValidator.get_extension_patterns_dir('flowise')}.\n"
                f"Re-run with templates from extensions/flowise/prompts/*.json"
            )

        print("✅ Flowise flow quality validation passed", file=sys.stderr)
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

        NOTE (Gap #4): This validator reads session-summary.json to detect Flowise mode,
        but earlier enforcement in run_builder_phase() depends on the flowise_mode flag
        passed at runtime. A misconfigured session could bypass those guards even though
        this validator detects the flow later. Consider centralizing Flowise detection.
        """
        # Check build plan exists
        build_tasks = working_dir / ".context-foundry" / "build-tasks.json"
        if not build_tasks.exists():
            raise FileNotFoundError("Builder failed to create build-tasks.json")

        # Parse task plan to check for parallel mode
        with open(build_tasks) as f:
            plan = json.load(f)

        # Normalize schema to support legacy builds and avoid KeyErrors downstream
        plan, _, warnings = _normalize_build_tasks_schema(plan)
        for warning in warnings:
            logger.warning(f"Build plan warning: {warning}")

        # Check each task completed (if parallel mode enabled)
        # The parallel builder now writes .done markers for persistent tracking
        if plan.get("parallel_mode") or plan.get("parallel_build_enabled"):
            for task in plan.get("tasks", []):
                # Support both old schema (id) and new schema (task_id)
                task_id = task.get("task_id") or task.get("id")
                if not task_id:
                    raise ValueError(f"Task missing required 'task_id' field: {task}")

                done_file = (
                    working_dir
                    / ".context-foundry"
                    / "builder-logs"
                    / f"{task_id}.done"
                )
                if not done_file.exists():
                    raise RuntimeError(
                        f"Builder task {task_id} did not complete.\n"
                        f"Expected completion marker at: {done_file}"
                    )

        # Smoke check: verify SOME source files created
        # Check session config for Flowise mode (more reliable than project_type)
        session_file = working_dir / ".context-foundry" / "session-summary.json"
        is_flowise = False
        if session_file.exists():
            try:
                with open(session_file) as f:
                    session = json.load(f)
                    config = session.get("configuration", {})
                    # Check for flowise_flow flag OR general extension marker
                    is_flowise = (
                        config.get("flowise_flow", False)
                        or config.get("extension") == "flowise"
                    )
            except Exception as e:
                # Log session parsing errors (Gap #2: silent error swallowing)
                logger.warning(
                    f"Failed to parse session-summary.json, falling back to project_type detection: {e}"
                )

        # Handle None project_type
        if project_type is None:
            project_type = "unknown"

        # Check if it's a Flowise project (from session config OR project_type)
        if is_flowise or "flowise" in project_type.lower():
            # Flowise: Need workflow JSON AND quality validation
            # Gap #1: General recursive search with exclusions (more robust than hardcoded directories)
            all_json_files = list(working_dir.rglob("*.json"))

            # Exclude common non-workflow files and directories
            excluded_names = {
                "package.json",
                "tsconfig.json",
                "build-tasks.json",
                "current-phase.json",
                "session-summary.json",
            }
            excluded_dirs = {
                ".context-foundry",
                "node_modules",
                ".git",
                "__pycache__",
                ".venv",
                "venv",
                ".pytest_cache",
            }

            flowise_jsons = [
                f
                for f in all_json_files
                if f.name not in excluded_names
                and not any(excluded_dir in f.parts for excluded_dir in excluded_dirs)
            ]

            if not flowise_jsons:
                raise FileNotFoundError(
                    "Flowise Builder failed to create workflow JSON (searched all directories except exclusions)"
                )

            # Run quality validation on the generated flow
            PhaseValidator.validate_flowise_flow_quality(working_dir)
            return True

        # For non-Flowise projects, check for traditional source files
        source_dirs = []
        if "python" in project_type.lower():
            source_dirs = ["src", "app", "backend"]
        elif "node" in project_type.lower() or "react" in project_type.lower():
            source_dirs = ["src", "pages", "components", "lib"]

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
    phase_timeout: int = 600,
    validator: Callable[[Path, str], bool] = None,
    iteration: int = 0,
    project_type: str = "unknown",
    provider: str = "claude",
) -> PhaseResult:
    """
    Execute a build phase using an AI agent (Claude or Gemini).

    Args:
        phase_name: Name of the phase (e.g., "Architect")
        phase_prompt_path: Path to the system prompt file
        input_instruction: User instruction for this phase
        working_directory: Directory to execute in
        phase_timeout: Timeout in seconds
        validator: Optional validation function
        iteration: Current iteration number
        project_type: Project type
        provider: AI provider to use ("claude" or "gemini")

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

    # Build command based on provider
    if provider.lower() == "gemini":
        # Gemini CLI Command
        # We prepend the system prompt to the user instruction because Gemini CLI
        # doesn't have a dedicated --system-prompt flag in the version we checked.
        full_prompt = f"SYSTEM INSTRUCTIONS:\n{phase_prompt}\n\nUSER INSTRUCTION:\n{input_instruction}"

        cmd = [
            "gemini",
            "--yolo",  # Auto-approve tools (equivalent to bypassPermissions)
            "--output-format",
            "text",
            full_prompt,
        ]
    else:
        # Claude CLI Command (Default)
        cmd = [
            "claude",
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",  # Prevents loading user MCP servers
            # Note: DO NOT add --print here - it prevents tool execution!
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
            if iteration > 0:
                # Fix iteration N: reads test report from PREVIOUS iteration (N-1)
                # Test file naming: iteration 0="test-report.md", 1="test-report-1.md"
                previous_iteration = iteration - 1
                test_filename = f"test-report{'-' + str(previous_iteration) if previous_iteration > 0 else ''}.md"

                # Reads: test-report from previous iteration, architecture.md
                # Writes: architecture-fix-{iteration}.md
                phase_files = [
                    working_directory / ".context-foundry" / "architecture.md",
                    working_directory / ".context-foundry" / test_filename,
                    working_directory
                    / ".context-foundry"
                    / f"architecture-fix-{iteration}.md",
                ]
            else:
                # Initial architecture: reads scout-report.md, writes architecture.md
                phase_files = [
                    working_directory / ".context-foundry" / "scout-report.md",
                    working_directory / ".context-foundry" / "architecture.md",
                ]
        elif phase_name == "Builder":
            if iteration > 0:
                # Fix iteration: reads architecture-fix-{N}.md
                phase_files = [
                    working_directory
                    / ".context-foundry"
                    / f"architecture-fix-{iteration}.md"
                ]
            else:
                # Initial build: reads architecture.md
                phase_files = [
                    working_directory / ".context-foundry" / "architecture.md"
                ]
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


def _normalize_build_tasks_schema(plan: dict) -> tuple[dict, bool, list[str]]:
    """
    Normalize build-tasks schema and check if it's safe for parallel execution.

    Returns:
        (normalized_plan, parallel_ready, warnings)
    """
    normalized = copy.deepcopy(plan)
    warnings: list[str] = []

    tasks = normalized.get("tasks", [])
    normalized_tasks = []
    parallel_ready = True

    for task in tasks:
        t = copy.deepcopy(task)

        # Support legacy "id" field
        task_id = t.get("task_id") or t.get("id")
        if not task_id:
            warnings.append(f"Task missing task_id: {t}")
            parallel_ready = False
            continue

        t["task_id"] = task_id

        # Default name/working_directory if missing
        t.setdefault("name", t.get("description", task_id))
        t.setdefault("working_directory", ".")

        # Dependencies normalization
        deps = t.get("dependencies", [])
        if deps is None:
            deps = []
        if not isinstance(deps, list):
            warnings.append(
                f"Task {task_id} dependencies must be a list, got {type(deps)}"
            )
            deps = []
            parallel_ready = False
        t["dependencies"] = deps

        build_commands = t.get("build_commands")
        if build_commands is None:
            warnings.append(
                f"Task {task_id} missing build_commands — plan not compatible with parallel runner"
            )
            t["build_commands"] = []
            parallel_ready = False
        elif not isinstance(build_commands, list):
            warnings.append(
                f"Task {task_id} build_commands must be a list, got {type(build_commands)}"
            )
            t["build_commands"] = []
            parallel_ready = False

        # Provider normalization
        provider = t.get("provider")
        if not provider:
            warnings.append(f"Task {task_id} missing provider — defaulting to Claude")
            t["provider"] = "Claude"
            parallel_ready = False

        # Agent instruction normalization
        instruction = t.get("agent_instruction")
        if not instruction:
            fallback = t.get("name") or t.get("description") or task_id
            warnings.append(
                f"Task {task_id} missing agent_instruction — synthesized fallback"
            )
            t["agent_instruction"] = f"Implement {fallback}"
            parallel_ready = False

        normalized_tasks.append(t)

    normalized["tasks"] = normalized_tasks

    return normalized, parallel_ready, warnings

    return normalized, parallel_ready, warnings


def _execute_agentic_tasks(
    build_tasks: dict,
    working_directory: Path,
    project_type: str,
) -> PhaseResult:
    """
    Execute build tasks using intelligent Agents (Unified Architecture).

    Args:
        build_tasks: Parsed build-tasks.json content
        working_directory: Project directory
        project_type: Project type for validation

    Returns:
        PhaseResult with aggregated metrics
    """
    import concurrent.futures

    tasks = build_tasks.get("tasks", [])
    if not tasks:
        raise ValueError("build-tasks.json contains no tasks")

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"🚀 AGENTIC BUILD: {len(tasks)} tasks", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Task Prompt Path
    task_prompt_path = (
        CF_ROOT / "tools" / "prompts" / "phases" / "phase_task_builder.txt"
    )
    if not task_prompt_path.exists():
        raise FileNotFoundError(f"Task prompt not found: {task_prompt_path}")

    # Track execution
    completed_tasks = []
    failed_tasks = []
    total_tokens = 0
    start_time = datetime.now()

    def execute_single_task(task: dict) -> dict:
        """Run a single Agent for a task."""
        task_id = task.get("task_id") or task.get("id")
        task_name = task.get("name", "Unknown Task")
        instruction = task.get("agent_instruction") or f"Implement task: {task_name}"
        provider = task.get("provider", "claude")

        # OVERRIDE: Force Claude Code for all tasks (ignore BAML provider selection)
        provider = "claude"

        # Add file context to instruction
        files = task.get("files", [])
        if files:
            instruction += "\n\nFiles to create/modify:\n" + "\n".join(
                f"- {f}" for f in files
            )

        print(
            f"\n🤖 Spawning Agent ({provider}) for: {task_name} ({task_id})",
            file=sys.stderr,
        )

        # Reuse run_phase to spawn the agent
        # We use a unique phase name for logging/tracking
        result = run_phase(
            phase_name=f"Task-{task_id}",
            phase_prompt_path=task_prompt_path,
            input_instruction=instruction,
            working_directory=working_directory,
            phase_timeout=1200,  # 20 mins per task
            validator=None,  # Sub-tasks don't need strict validation, the main build does
            project_type=project_type,
            provider=provider,
        )

        return {"task_id": task_id, "success": result.exit_code == 0, "result": result}

    # Execute Tasks
    # If 1 task -> Run in main thread (easier debugging)
    # If >1 task -> Run in parallel
    results = []
    if len(tasks) == 1:
        results.append(execute_single_task(tasks[0]))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {executor.submit(execute_single_task, t): t for t in tasks}
            for future in concurrent.futures.as_completed(future_to_task):
                results.append(future.result())

    # Aggregate Results
    for res in results:
        r = res["result"]
        total_tokens += r.context_tokens
        if res["success"]:
            completed_tasks.append(res["task_id"])
        else:
            failed_tasks.append(res["task_id"])

    duration = (datetime.now() - start_time).total_seconds()
    success = len(failed_tasks) == 0

    print(f"\n{'='*60}", file=sys.stderr)
    print(
        f"🏁 BUILD COMPLETE: {len(completed_tasks)}/{len(tasks)} tasks successful",
        file=sys.stderr,
    )
    print(f"{'='*60}\n", file=sys.stderr)

    return PhaseResult(
        phase="Builder",
        status="completed" if success else "failed",
        duration_seconds=duration,
        context_tokens=total_tokens,
        exit_code=0 if success else 1,
        error=None if success else f"Failed tasks: {failed_tasks}",
    )


def run_builder_phase(
    prompt_path: Path,
    instruction: str,
    working_directory: Path,
    project_type: str,
    flowise_mode: bool = False,
    use_parallel: bool = True,
    iteration: int = 0,
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
        iteration: Fix iteration number (0 for initial build, >0 for fixes)

    Returns:
        PhaseResult with metrics
    """
    # Prefer structured architecture JSON if available; append to instruction once
    arch_json_path = working_directory / ".context-foundry" / "architecture.json"
    if arch_json_path.exists() and "ARCHITECTURE_JSON:" not in instruction:
        try:
            arch_json = arch_json_path.read_text()
            instruction = instruction + "\n\nARCHITECTURE_JSON:\n" + arch_json
            print(
                "ℹ️  Injected architecture.json into Builder instruction",
                file=sys.stderr,
            )
        except Exception as e:
            print(
                f"⚠️  Failed to read architecture.json; continuing without JSON ({e})",
                file=sys.stderr,
            )

    # HARD GATE: Flowise MUST be sequential
    if flowise_mode:
        print(
            "🚨 Flowise mode: Sequential build (single JSON file required)",
            file=sys.stderr,
        )
        # Verify reference file exists before building
        try:
            PhaseValidator.validate_flowise_reference_exists()
        except FileNotFoundError as e:
            return PhaseResult(
                phase="Builder",
                status="failed",
                duration_seconds=0,
                context_tokens=0,
                exit_code=1,
                error=str(e),
            )
        # Note: use_parallel parameter is for future parallelization support

    # Check if build plan exists (Unified Architecture)
    build_tasks_file = working_directory / ".context-foundry" / "build-tasks.json"

    if build_tasks_file.exists():
        print(
            "📋 Found build-tasks.json - executing Unified Agentic Build",
            file=sys.stderr,
        )

        try:
            with open(build_tasks_file) as f:
                build_tasks = json.load(f)

            # Normalize schema
            build_tasks, parallel_ready, plan_warnings = _normalize_build_tasks_schema(
                build_tasks
            )

            for warning in plan_warnings:
                print(f"⚠️  Build plan warning: {warning}", file=sys.stderr)

            parallel_flag = build_tasks.get("parallel_mode") or build_tasks.get(
                "parallel_build_enabled"
            )
            tasks = build_tasks.get("tasks", [])

            if not use_parallel:
                print(
                    "ℹ️  Parallel execution disabled by flag; running legacy Builder",
                    file=sys.stderr,
                )
            elif not parallel_flag:
                print(
                    "ℹ️  Build plan indicates sequential mode; running legacy Builder",
                    file=sys.stderr,
                )
            elif not parallel_ready:
                print(
                    "⚠️  Build plan not parallel-ready; running legacy Builder",
                    file=sys.stderr,
                )
                for warning in plan_warnings:
                    print(f"   - {warning}", file=sys.stderr)
            elif len(tasks) <= 1:
                print(
                    "ℹ️  Single task in plan; running legacy Builder",
                    file=sys.stderr,
                )
            else:
                # EXECUTE AGENTS (parallel path)
                return _execute_agentic_tasks(
                    build_tasks,
                    working_directory,
                    project_type,
                )

        except Exception as e:
            print(
                f"⚠️  Failed to execute agentic build: {e} - falling back to legacy sequential",
                file=sys.stderr,
            )
            traceback.print_exc()

    else:
        print(
            "📝 No build-tasks.json found - using legacy sequential build",
            file=sys.stderr,
        )

    # Fallback / Legacy Sequential
    return run_phase(
        "Builder",
        prompt_path,
        instruction,
        working_directory,
        phase_timeout=1800,
        validator=lambda wd, pt=project_type: PhaseValidator.validate_builder(wd, pt),
        iteration=iteration,
        project_type=project_type,
    )


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
    # EXPANDED: Include all variations that Test phase actually produces
    passed_indicators = [
        "all tests passed",
        "all tests passing",  # "All tests passing (153/153)"
        "tests passing",  # "All tests passing"
        "✅ all tests passed",
        "✅ all tests passing",
        "status: passed",
        "status: ✅ passed",  # "**Status**: ✅ **PASSED**"
        "status**: ✅ **passed",  # Bold formatting variation
        "status**: passed",  # "**Status**: PASSED"
        "result: pass",
        "**status**: passed",
        "all tests executed successfully",  # From test-report-2.md
        "production ready",  # "PASSED - Production Ready"
        "production-ready",  # Hyphenated variation
    ]

    fail_indicators = [
        "failed:",
        "❌ failed",
        "status: failed",
        "result: fail",
        "errors:",
        "test failures:",
        "**status**: failed",
        "tests failed",  # Explicit failures
        "failing",  # Tests are failing
    ]

    has_pass = any(indicator in content_lower for indicator in passed_indicators)
    has_fail = any(indicator in content_lower for indicator in fail_indicators)

    # Passed if: has pass indicator AND no fail indicators
    return has_pass and not has_fail

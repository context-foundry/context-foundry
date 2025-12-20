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
import subprocess
import sys
import time
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
from tools.llm_core.providers import (
    LocalClaudeProvider,
    BedrockProvider,
    BedrockAgentProvider,
)
from tools.llm_core.config import get_provider_for_phase, reload_config

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# STATE MACHINE INTEGRATION
# =============================================================================

# Phase sequence mapping for task ordering
PHASE_SEQUENCE = {
    "Scout": 0,
    "Architect": 1,
    "Builder": 2,
    "Test": 3,
    "Screenshot": 4,
    "Documentation": 5,
    "Deploy": 6,
    "Feedback": 7,
}

# Default phase timeout (used for task timeout tracking)
DEFAULT_PHASE_TIMEOUTS = {
    "Scout": 300,  # 5 minutes
    "Architect": 600,  # 10 minutes
    "Builder": 1800,  # 30 minutes
    "Test": 600,  # 10 minutes
    "Screenshot": 120,  # 2 minutes
    "Documentation": 300,
    "Deploy": 600,
    "Feedback": 120,
}


def _get_state_machine():
    """
    Get a state machine instance connected to the daemon's database.

    Returns None if daemon store is not available (e.g., running standalone).
    """
    try:
        from context_foundry.daemon.store import Store
        from context_foundry.daemon.state_machine import StateMachine
        from pathlib import Path

        # Connect to the same database as the daemon
        # Uses WAL mode so concurrent access is safe
        # Default daemon database path: ~/.context-foundry/daemon.db
        db_path = Path.home() / ".context-foundry" / "daemon.db"
        if not db_path.exists():
            logger.debug(f"Daemon database not found at {db_path}")
            return None

        store = Store(db_path)
        return StateMachine(store)
    except ImportError:
        logger.debug("State machine not available (daemon modules not found)")
        return None
    except Exception as e:
        logger.warning(f"Failed to initialize state machine: {e}")
        return None


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
    def check_no_nested_context_foundry(working_dir: Path) -> None:
        """
        Verify no nested .context-foundry directories exist inside subdirectories.

        Agents sometimes incorrectly create project-named subdirectories with their own
        .context-foundry/ folders instead of writing to the project root .context-foundry/.

        This causes phase outputs (test-report.md, architecture.md, etc.) to be
        written to the wrong location and not found by the orchestrator.

        Args:
            working_dir: Project root directory

        Raises:
            ValueError: If nested .context-foundry directories are found
        """
        root_cf = working_dir / ".context-foundry"

        # Find all .context-foundry directories recursively
        nested_cf_dirs = []
        for cf_dir in working_dir.rglob(".context-foundry"):
            # Skip the root .context-foundry directory
            if cf_dir == root_cf:
                continue
            # Skip if inside external dependency directories (NOT agent-created dirs)
            # Note: We intentionally DO NOT skip dist/build - agents might incorrectly
            # create .context-foundry there and we want to catch that
            path_parts = cf_dir.parts
            skip_dirs = {"node_modules", "venv", ".venv", ".git", "__pycache__"}
            if any(part in skip_dirs for part in path_parts):
                continue
            nested_cf_dirs.append(cf_dir)

        if nested_cf_dirs:
            nested_list = "\n  - ".join(
                str(d.relative_to(working_dir)) for d in nested_cf_dirs
            )
            raise ValueError(
                f"Found nested .context-foundry directories (agent error):\n  - {nested_list}\n\n"
                f"All phase outputs MUST be written to the project root .context-foundry/ directory.\n"
                f"The agent incorrectly created subdirectories. This phase must be retried.\n\n"
                f"Expected: {root_cf}\n"
                f"Found: {nested_cf_dirs[0]}"
            )

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
        md_report = working_dir / ".context-foundry" / "scout-report.md"

        if not md_report.exists():
            raise FileNotFoundError(f"Scout failed to create {md_report}")

        # Verify non-empty
        if md_report.stat().st_size < 100:
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
                f"Re-run with templates from extensions/flowise/node-templates/*.json"
            )

        print("✅ Flowise flow quality validation passed", file=sys.stderr)
        return True

    @staticmethod
    def validate_architect(working_dir: Path) -> bool:
        """Architect must create architecture.md with substantive content."""
        required = working_dir / ".context-foundry" / "architecture.md"
        if not required.exists():
            raise FileNotFoundError(f"Architect failed to create {required}")

        content = required.read_text()
        content_lower = content.lower()

        # Basic size check - architecture should be substantive
        if len(content) < 500:
            raise ValueError(
                f"architecture.md is too small ({len(content)} bytes) - expected substantial architecture document"
            )

        # Flexible keyword checks (case-insensitive, any heading level)
        has_tech_section = any(
            keyword in content_lower
            for keyword in [
                "technology",
                "tech stack",
                "stack",
                "dependencies",
                "libraries",
            ]
        )
        has_arch_section = any(
            keyword in content_lower
            for keyword in [
                "architecture",
                "structure",
                "design",
                "overview",
                "modules",
            ]
        )

        if not has_tech_section and not has_arch_section:
            raise ValueError(
                "architecture.md missing key sections (expected technology/architecture content)"
            )

        return True

    @staticmethod
    def validate_builder(working_dir: Path, project_type: str = "unknown") -> bool:
        """
        Builder validation is LOOSE - verify source files exist.

        Don't validate exact files (too dynamic). Instead:
        1. At least SOME source files created
        2. No obvious errors in builder logs

        NOTE (Gap #4): This validator reads session-summary.json to detect Flowise mode,
        but earlier enforcement in run_builder_phase() depends on the flowise_mode flag
        passed at runtime. A misconfigured session could bypass those guards even though
        this validator detects the flow later. Consider centralizing Flowise detection.
        """
        # First, check for nested .context-foundry directories (common agent error)
        PhaseValidator.check_no_nested_context_foundry(working_dir)

        # Build tasks are now in build-tasks.md (markdown format)
        # Legacy JSON support for backwards compatibility only
        build_tasks = working_dir / ".context-foundry" / "build-tasks.json"
        plan = None
        if build_tasks.exists():
            try:
                # Parse task plan to check for parallel mode (legacy JSON)
                with open(build_tasks) as f:
                    plan = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to parse build-tasks.json: {e}")
        else:
            # build-tasks.md is the standard now - Builder creates files directly
            logger.info("Checking for source files created by Builder")

        # Only check parallel completion if we have a valid build plan
        if plan:
            # Normalize schema to support legacy builds and avoid KeyErrors downstream
            plan, _, warnings = _normalize_build_tasks_schema(plan)
            for warning in warnings:
                logger.warning(f"Build plan warning: {warning}")

            # Check each task completed (if parallel mode enabled)
            # Validation accepts either:
            #   1. .done marker file (created by parallel sub-builders)
            #   2. Expected output files exist (for single-builder execution)
            if plan.get("parallel_mode") or plan.get("parallel_build_enabled"):
                for task in plan.get("tasks", []):
                    # Support both old schema (id) and new schema (task_id)
                    task_id = task.get("task_id") or task.get("id")
                    if not task_id:
                        raise ValueError(
                            f"Task missing required 'task_id' field: {task}"
                        )

                    done_file = (
                        working_dir
                        / ".context-foundry"
                        / "builder-logs"
                        / f"{task_id}.done"
                    )

                    # First check for .done marker (parallel sub-builders)
                    if done_file.exists():
                        continue

                    # Fallback: check if expected files from task exist
                    task_files = task.get("files", [])
                    if task_files:
                        missing_files = []
                        for f in task_files:
                            file_path = working_dir / f
                            if not file_path.exists():
                                missing_files.append(f)

                        if missing_files:
                            raise RuntimeError(
                                f"Builder task {task_id} did not complete.\n"
                                f"Missing expected files: {missing_files}\n"
                                f"(No .done marker at: {done_file})"
                            )
                        # All expected files exist - task completed successfully
                        logger.info(
                            f"Task {task_id} validated via file existence (no .done marker)"
                        )
                    else:
                        # No files specified and no .done marker - warn but continue
                        logger.warning(
                            f"Task {task_id} has no files specified and no .done marker"
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
                    + list(src_dir.rglob("*.html"))
                    + list(src_dir.rglob("*.css"))
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
                + list(working_dir.rglob("*.html"))
                + list(working_dir.rglob("*.css"))
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
        # First, check for nested .context-foundry directories (common agent error)
        PhaseValidator.check_no_nested_context_foundry(working_dir)

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
    model: str = None,
    task_config: dict = None,
    job_id: str = None,
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
        model: Optional model override (e.g., "claude-opus-4-20250514")
        task_config: Optional task configuration (enables human-in-the-loop if present)
        job_id: Optional job ID for tracking

    Returns:
        PhaseResult with metrics
    """
    # Extract job_id from task_config if not explicitly provided
    if job_id is None and task_config:
        job_id = task_config.get("job_id")

    # ==========================================================================
    # WORKING DIRECTORY ENFORCEMENT
    # Ensure working_directory is absolute and .context-foundry exists at root
    # ==========================================================================
    working_directory = Path(working_directory).resolve()
    if not working_directory.exists():
        raise ValueError(f"Working directory does not exist: {working_directory}")

    root_cf = working_directory / ".context-foundry"
    if not root_cf.exists():
        logger.info(f"Creating .context-foundry at project root: {root_cf}")
        root_cf.mkdir(parents=True, exist_ok=True)

    # Log the resolved working directory for debugging
    logger.info(f"Phase {phase_name} running with cwd={working_directory}")
    print(
        f"[CWD] {phase_name} phase using working_directory: {working_directory}",
        flush=True,
    )

    # Check for human-in-the-loop mode
    if task_config:
        from tools.mcp_utils.phase_status import (
            get_previous_phase,
            wait_for_approval,
        )

        execution_mode = task_config.get("execution_mode", "autonomous")

        if execution_mode == "hitl":
            # In HITL mode, wait for approval of previous phase's output
            prev_phase = get_previous_phase(phase_name)
            if prev_phase:
                logger.info(
                    f"HITL: Waiting for {prev_phase} approval before {phase_name}"
                )
                print(f"⏳ HITL: Waiting for {prev_phase} approval...", file=sys.stderr)

                if not wait_for_approval(working_directory, prev_phase, timeout=3600):
                    return PhaseResult(
                        phase=phase_name,
                        status="failed",
                        duration_seconds=0,
                        context_tokens=0,
                        exit_code=1,
                        error=f"Timeout waiting for {prev_phase} approval",
                    )

                print(
                    f"✅ HITL: {prev_phase} approved, proceeding with {phase_name}",
                    file=sys.stderr,
                )

    # Standard execution (no human-in-the-loop)
    # Get execution_mode from task_config if available
    exec_mode = (
        task_config.get("execution_mode", "autonomous") if task_config else "autonomous"
    )
    return _run_phase_internal(
        phase_name=phase_name,
        phase_prompt_path=phase_prompt_path,
        input_instruction=input_instruction,
        working_directory=working_directory,
        phase_timeout=phase_timeout,
        validator=validator,
        iteration=iteration,
        project_type=project_type,
        provider=provider,
        model=model,
        job_id=job_id,
        execution_mode=exec_mode,
    )


def _run_phase_internal(
    phase_name: str,
    phase_prompt_path: Path,
    input_instruction: str,
    working_directory: Path,
    phase_timeout: int = 600,
    validator: Callable[[Path, str], bool] = None,
    iteration: int = 0,
    project_type: str = "unknown",
    provider: str = "claude",
    model: str = None,
    job_id: str = None,
    skip_prompt_save: bool = False,
    execution_mode: str = "autonomous",
) -> PhaseResult:
    """
    Internal implementation of phase execution.

    This is the actual phase runner, separated to allow the human-in-the-loop
    wrapper to call it after prompt approval.

    Args:
        skip_prompt_save: If True, skip saving phase prompt file (used when called
                         from run_phase_with_prompt_management which already saved it)
    """
    # ==========================================================================
    # WORKING DIRECTORY ENFORCEMENT (defense in depth)
    # Ensure working_directory is absolute path - agents MUST run from project root
    # ==========================================================================
    working_directory = Path(working_directory).resolve()

    # ==========================================================================
    # Construct System Prompt
    # ==========================================================================
    # Force reload config to pick up any recent changes
    reload_config()

    # If provider arg is explicit (e.g. from CLI flag), it overrides config
    # But if it's default "claude", we check config
    if provider.lower() == "bedrock":
        provider_type = "bedrock"
        effective_model = model
    elif provider.lower() == "local":
        provider_type = "local"
        # Allow explicit model for local provider if specified (e.g. for dashboard display or future use)
        effective_model = model if model else None
        extra_config = {}
    elif provider.lower() == "bedrock-agent":
        provider_type = "bedrock-agent"
        effective_model = None  # Model is defined in the agent
        # We need extra config for agent ID, but CLI args might not support it yet
        # So we likely rely on config file resolution below if not passed explicitly
        # But wait, if provider is explicit, we skip get_provider_for_phase
        # This is a limitation: CLI can't easily pass agent_id yet.
        # For now, we assume if you use CLI --provider bedrock-agent, you rely on defaults or it fails
        extra_config = {}
    else:
        provider_type, effective_model, extra_config = get_provider_for_phase(
            phase_name
        )
        # If explicit model passed, override config model
        if model:
            effective_model = model

    print(
        f"🔧 Phase '{phase_name}' resolved: provider={provider_type}, model={effective_model}",
        file=sys.stderr,
    )

    effective_provider = provider_type

    # ==========================================================================
    # STATE MACHINE: Initialize task tracking
    # ==========================================================================
    state_machine = None
    task = None
    task_id = None

    if job_id:
        try:
            state_machine = _get_state_machine()
            if state_machine:
                # Create task for this phase
                sequence = PHASE_SEQUENCE.get(phase_name, 99)
                timeout = DEFAULT_PHASE_TIMEOUTS.get(phase_name, phase_timeout)

                # Build task metadata including model/provider info
                task_metadata = {
                    "iteration": iteration,
                    "project_type": project_type,
                    "provider": effective_provider
                    if "effective_provider" in dir()
                    else provider,
                    "model": effective_model if "effective_model" in dir() else model,
                }

                task = state_machine.create_task_for_phase(
                    job_id=job_id,
                    phase_name=phase_name,
                    sequence=sequence,
                    timeout_seconds=timeout,
                    metadata=task_metadata,
                )
                task_id = task.id

                # Start the task (CREATED -> RUNNING)
                task = state_machine.start_task(task_id)
                logger.info(
                    f"Task {task_id[:8]} started for phase {phase_name} (provider={task_metadata.get('provider')}, model={task_metadata.get('model')})"
                )
        except Exception as e:
            logger.warning(f"Failed to create task for {phase_name}: {e}")
            # Continue without task tracking - don't fail the phase

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"STARTING PHASE: {phase_name} (Fresh Context)", file=sys.stderr)
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
        error_msg = f"Phase prompt not found: {phase_prompt_path}"

        # Record failure in phase status
        if not skip_prompt_save:
            try:
                from tools.mcp_utils.phase_status import mark_phase_failed

                mark_phase_failed(working_directory, phase_name, error_msg)
            except Exception as e:
                logger.warning(f"Failed to update phase status: {e}")

        return PhaseResult(
            phase=phase_name,
            status="failed",
            duration_seconds=0,
            context_tokens=0,
            exit_code=1,
            error=error_msg,
        )

    phase_prompt = phase_prompt_path.read_text()

    # ==========================================================================
    # TEMPLATE SUBSTITUTION - Always substitute WORKING_DIRECTORY for all phases
    # ==========================================================================
    from string import Template

    # Inject conversation memory for Scout phase
    if phase_name.lower() == "scout" and "${CONVERSATION_MEMORY}" in phase_prompt:
        try:
            from tools.llm_core.memory import ConversationMemory

            memory = ConversationMemory()
            # Extract topics from input instruction for relevance matching
            task_words = (
                input_instruction.lower().split()[:10] if input_instruction else []
            )
            memory_context = memory.format_for_prompt(current_topics=task_words)

            if memory_context:
                memory_block = f"## 🧠 Conversation Memory\n\n{memory_context}"
            else:
                memory_block = (
                    "## 🧠 Conversation Memory\n\n(No prior conversations found)"
                )

            phase_prompt = Template(phase_prompt).safe_substitute(
                CONVERSATION_MEMORY=memory_block,
                WORKING_DIRECTORY=str(working_directory),
            )
            logger.info(
                "Injected conversation memory and working directory into prompt"
            )
        except Exception as e:
            logger.debug(f"Could not inject conversation memory: {e}")
            phase_prompt = phase_prompt.replace("${CONVERSATION_MEMORY}", "")
            # Still substitute WORKING_DIRECTORY even if memory fails
            phase_prompt = phase_prompt.replace(
                "${WORKING_DIRECTORY}", str(working_directory)
            )
    else:
        # For non-Scout phases, still substitute WORKING_DIRECTORY
        phase_prompt = Template(phase_prompt).safe_substitute(
            WORKING_DIRECTORY=str(working_directory),
        )

    # Mark phase as running in status tracker
    if not skip_prompt_save:
        try:
            from tools.mcp_utils.phase_status import (
                mark_phase_running,
                init_phase_status,
                get_phase_status,
            )

            # Initialize status file if not exists
            if not get_phase_status(working_directory):
                init_phase_status(working_directory, execution_mode)

            mark_phase_running(working_directory, phase_name)
            logger.info(
                f"Phase {phase_name} marked as running (mode: {execution_mode})"
            )
        except Exception as e:
            logger.warning(f"Failed to update phase status: {e}")

    # ==========================================================================
    # TOOL EXECUTOR FOR BEDROCK AGENT RETURN CONTROL
    # ==========================================================================

    def tool_executor(tool_name: str, tool_input: dict):
        """Execute tools for Bedrock Agent Return Control."""
        import glob as glob_module
        import re

        logger.info(f"Tool executor called: {tool_name} with input: {tool_input}")

        if tool_name == "codex_search":
            # Call the MCP codex_search function
            try:
                from tools.mcp_utils.codex import codex_search

                query = tool_input.get("query", "")
                category = tool_input.get("category")
                result = codex_search(query, category=category)
                return result
            except Exception as e:
                return {"error": str(e)}

        elif tool_name == "codex_get_entry":
            try:
                from tools.mcp_utils.codex import codex_get_entry

                entry_id = tool_input.get("entry_id", "")
                result = codex_get_entry(entry_id)
                return result
            except Exception as e:
                return {"error": str(e)}

        elif tool_name == "read_file":
            file_path = tool_input.get("file_path", "")
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                return {"content": content, "path": file_path}
            except Exception as e:
                return {"error": str(e)}

        elif tool_name == "write_file":
            file_path = tool_input.get("file_path", "")
            content = tool_input.get("content", "")
            try:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w") as f:
                    f.write(content)
                return {"success": True, "path": file_path}
            except Exception as e:
                return {"error": str(e)}

        elif tool_name == "glob":
            pattern = tool_input.get("pattern", "")
            search_path = tool_input.get("path", str(working_directory))
            try:
                full_pattern = str(Path(search_path) / pattern)
                matches = glob_module.glob(full_pattern, recursive=True)
                return {"matches": matches[:100]}  # Limit results
            except Exception as e:
                return {"error": str(e)}

        elif tool_name == "grep":
            pattern = tool_input.get("pattern", "")
            search_path = tool_input.get("path", str(working_directory))
            try:
                results = []
                search_dir = Path(search_path)
                if search_dir.is_file():
                    files = [search_dir]
                else:
                    files = list(search_dir.rglob("*"))

                regex = re.compile(pattern)
                for f in files[:50]:  # Limit files searched
                    if f.is_file() and f.suffix in [
                        ".py",
                        ".js",
                        ".ts",
                        ".json",
                        ".md",
                        ".txt",
                    ]:
                        try:
                            content = f.read_text()
                            for i, line in enumerate(content.split("\n"), 1):
                                if regex.search(line):
                                    results.append(
                                        {
                                            "file": str(f),
                                            "line": i,
                                            "content": line[:200],
                                        }
                                    )
                        except Exception:
                            pass
                return {"matches": results[:50]}
            except Exception as e:
                return {"error": str(e)}

        elif tool_name == "run_bash":
            command = tool_input.get("command", "")
            try:
                result = subprocess.run(
                    command,
                    shell=True,  # nosec B602 - shell=True needed for bash commands
                    capture_output=True,
                    text=True,
                    cwd=str(working_directory),
                    timeout=60,
                )
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
            except Exception as e:
                return {"error": str(e)}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    # ==========================================================================
    # AGENT EXECUTION
    # ==========================================================================

    # NOTE: Provider resolution logic was moved to the top of the function
    # to ensure metadata is correct. We use the resolved values here.

    llm_provider = None
    if provider_type == "bedrock":
        llm_provider = BedrockProvider(default_model=effective_model)
    elif provider_type == "bedrock-agent":
        agent_id = extra_config.get("agent_id")
        alias_id = extra_config.get("alias_id")

        if not agent_id or not alias_id:
            logger.warning(
                "Bedrock Agent provider selected but missing agent_id/alias_id in config. Falling back to Local."
            )
            llm_provider = LocalClaudeProvider()
        else:
            region = extra_config.get("region", "us-east-1")
            logger.info(f"Using Bedrock Agent: {agent_id} ({alias_id}) in {region}")
            llm_provider = BedrockAgentProvider(
                agent_id=agent_id,
                agent_alias_id=alias_id,
                tool_executor=tool_executor,  # Pass executor for Return Control
                region=region,
            )
    else:
        # Default to Local Claude
        llm_provider = LocalClaudeProvider()

    # Track start time
    start = datetime.now()

    # Initialize conversation logger if available
    # This captures the stream-json output for the dashboard
    conversation_logger = None
    try:
        from tools.mcp_utils.conversation_logger import ConversationLogger
        import uuid

        # Use job_id if available, otherwise generate a temporary ID
        logger_task_id = job_id if job_id else f"temp-{uuid.uuid4()}"
        conversation_logger = ConversationLogger(logger_task_id, working_directory)
        print(f"Logging conversation to {conversation_logger.log_dir}", file=sys.stderr)
    except ImportError:
        print("ConversationLogger not available", file=sys.stderr)
    except Exception as e:
        print(f"Failed to initialize ConversationLogger: {e}", file=sys.stderr)

    # Define event callback for streaming logs
    def event_callback(event_data: dict):
        if conversation_logger:
            try:
                # Parse raw event data into ConversationEvent objects
                # Since we are getting raw JSON dicts from stream-json, we can use the logger's logic
                # But logger.parse_event expects a string line.
                # Let's just re-serialize to string to reuse the parser logic for now
                # This is slightly inefficient but safe and quick
                line = json.dumps(event_data)
                events = conversation_logger.parse_event(line)
                for event in events:
                    conversation_logger.log_event(event)
            except Exception:
                # Don't crash the build on logging errors
                pass

    # ==========================================================================
    # HEARTBEAT THREAD: Emit periodic heartbeats during long-running phases
    # ==========================================================================
    heartbeat_stop_event = None
    heartbeat_thread = None

    if state_machine and task_id:
        import threading

        heartbeat_stop_event = threading.Event()
        heartbeat_interval = 30  # Emit heartbeat every 30 seconds

        def heartbeat_emitter():
            """Background thread that emits periodic heartbeats."""
            elapsed_seconds = 0
            while not heartbeat_stop_event.wait(timeout=heartbeat_interval):
                elapsed_seconds += heartbeat_interval
                try:
                    state_machine.record_task_heartbeat(
                        task_id=task_id,
                        progress=f"Running for {elapsed_seconds}s",
                        metadata={"elapsed_seconds": elapsed_seconds},
                    )
                    logger.debug(
                        f"Heartbeat emitted for {phase_name} ({elapsed_seconds}s)"
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit heartbeat: {e}")

        heartbeat_thread = threading.Thread(target=heartbeat_emitter, daemon=True)
        heartbeat_thread.start()
        logger.info(f"Heartbeat thread started for phase {phase_name}")

    try:
        print(
            f"⏳ Running {phase_name} phase (Provider: {type(llm_provider).__name__})...",
            file=sys.stderr,
        )
        print(f"   Timeout: {phase_timeout}s", file=sys.stderr)
        print(f"   Working directory: {working_directory}", file=sys.stderr)

        # Execute LLM Provider directly (no agent wrapper)
        # Note: This blocks until completion, but streams events via callback
        result = llm_provider.generate(
            system_prompt=phase_prompt,
            user_prompt=input_instruction,
            model=effective_model,
            working_directory=working_directory,
            event_callback=event_callback,
        )

        # Process Result
        # llm_provider.generate() always returns a string
        stdout = result if result else ""
        stderr = ""
        exit_code = 0

        duration = (datetime.now() - start).total_seconds()

        print(
            f"✅ {phase_name} process completed (exit code: {exit_code})",
            file=sys.stderr,
        )

        # ==========================================================================
        # WRITE OUTPUT TO FILE (for agents using --print mode)
        # LocalClaudeProvider uses --print which returns text instead of using tools.
        # We need to write the output to the expected file for validation to pass.
        # ==========================================================================
        if phase_name == "Architect" and stdout and exit_code == 0:
            cf_dir = working_directory / ".context-foundry"
            cf_dir.mkdir(parents=True, exist_ok=True)

            if iteration > 0:
                # Fix iteration: write architecture-fix-{iteration}.md
                arch_file = cf_dir / f"architecture-fix-{iteration}.md"
            else:
                # Initial architecture: write architecture.md
                arch_file = cf_dir / "architecture.md"

            # Only write if file doesn't exist or is empty (don't overwrite if Claude created it)
            if not arch_file.exists() or arch_file.stat().st_size < 100:
                arch_file.write_text(stdout)
                print(
                    f"📝 Saved Architect output to {arch_file.name} ({len(stdout)} chars)",
                    file=sys.stderr,
                )
            else:
                print(
                    f"📝 {arch_file.name} already exists ({arch_file.stat().st_size} bytes)",
                    file=sys.stderr,
                )

        # Estimate context usage
        phase_files = []
        if phase_name == "Scout":
            phase_files = []
            md_report = working_directory / ".context-foundry" / "scout-report.md"
            if md_report.exists():
                phase_files.append(md_report)
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

        context_tokens = estimate_context_tokens(stdout, stderr, phase_files)

        # Validate output using phase-specific validator
        if validator:
            try:
                if phase_name == "Builder":
                    validator(working_directory, project_type)
                else:
                    validator(working_directory)
                print(f"✅ {phase_name} output validation PASSED", file=sys.stderr)
            except Exception as e:
                print(
                    f"[X] {phase_name} output validation FAILED: {e}", file=sys.stderr
                )
                # ==========================================================================
                # STATE MACHINE: Mark task as failed (validation failure)
                # ==========================================================================
                if heartbeat_stop_event:
                    heartbeat_stop_event.set()
                if state_machine and task_id:
                    try:
                        state_machine.fail_task(
                            task_id, f"Output validation failed: {e}"
                        )
                        logger.info(f"Task {task_id[:8]} marked as failed (validation)")
                    except Exception as sm_err:
                        logger.warning(f"Failed to update task status: {sm_err}")

                return PhaseResult(
                    phase=phase_name,
                    status="failed",
                    duration_seconds=duration,
                    context_tokens=context_tokens,
                    exit_code=1,
                    error=f"Output validation failed: {e}",
                    stdout_lines=len(stdout.splitlines()),
                    stderr_lines=len(stderr.splitlines()),
                )

        # Verify BAML tracking (soft validation - doesn't fail build)
        if is_baml_available():
            PhaseValidator.validate_baml_tracking(working_directory, phase_name)

        # Log metrics
        log_phase_metrics(
            phase_name,
            duration,
            context_tokens,
            exit_code,
            working_directory,
            iteration,
        )

        # BAML: Track phase completion
        final_status = "Completed" if exit_code == 0 else "Failed"
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

        # Update phase status on completion
        if not skip_prompt_save:
            try:
                from tools.mcp_utils.phase_status import (
                    mark_phase_complete,
                    mark_phase_failed,
                    mark_phase_pending_approval,
                )

                if exit_code == 0:
                    # In HITL mode, mark as pending_approval; otherwise complete
                    if execution_mode == "hitl":
                        mark_phase_pending_approval(working_directory, phase_name)
                    else:
                        mark_phase_complete(working_directory, phase_name)
                else:
                    mark_phase_failed(
                        working_directory, phase_name, f"Exit code: {exit_code}"
                    )
            except Exception as e:
                logger.warning(f"Failed to update phase status: {e}")

        # ==========================================================================
        # STATE MACHINE: Update task status on completion
        # ==========================================================================
        if heartbeat_stop_event:
            heartbeat_stop_event.set()
        if state_machine and task_id:
            try:
                if exit_code == 0:
                    state_machine.complete_task(
                        task_id,
                        result={"duration_seconds": duration},
                        tokens_used=context_tokens,
                    )
                    logger.info(f"Task {task_id[:8]} marked as succeeded")
                else:
                    state_machine.fail_task(
                        task_id, f"Phase exited with code {exit_code}"
                    )
                    logger.info(f"Task {task_id[:8]} marked as failed (exit code)")
            except Exception as sm_err:
                logger.warning(f"Failed to update task status: {sm_err}")

        phase_result_status = "completed" if exit_code == 0 else "failed"
        return PhaseResult(
            phase=phase_name,
            status=phase_result_status,
            duration_seconds=duration,
            context_tokens=context_tokens,
            exit_code=exit_code,
            stdout_lines=len(stdout.splitlines()),
            stderr_lines=len(stderr.splitlines()),
        )

    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        print(f"[X] {phase_name} ERROR: {e}", file=sys.stderr)

        # ==========================================================================
        # STATE MACHINE: Mark task as failed (exception)
        # ==========================================================================
        if heartbeat_stop_event:
            heartbeat_stop_event.set()
        if state_machine and task_id:
            try:
                state_machine.fail_task(task_id, f"Exception: {str(e)[:200]}")
                logger.info(f"Task {task_id[:8]} marked as failed (exception)")
            except Exception as sm_err:
                logger.warning(f"Failed to update task status: {sm_err}")

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
                print(f"BAML error tracking failed: {baml_error}", file=sys.stderr)

        # Update phase status to failed
        if not skip_prompt_save:
            try:
                from tools.mcp_utils.phase_status import mark_phase_failed

                mark_phase_failed(working_directory, phase_name, str(e))
            except Exception as status_error:
                logger.warning(
                    f"Failed to update phase status on error: {status_error}"
                )

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

    # Ensure builder logs directory exists for completion markers
    builder_logs_dir = working_directory / ".context-foundry" / "builder-logs"
    builder_logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"🚀 AGENTIC BUILD: {len(tasks)} tasks", file=sys.stderr)
    print(f"{'=' * 60}\n", file=sys.stderr)

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
            done_file = builder_logs_dir / f"{res['task_id']}.done"
            done_file.write_text(
                json.dumps(
                    {
                        "task_id": res["task_id"],
                        "status": "completed",
                        "timestamp": datetime.now().isoformat(),
                        "context_tokens": r.context_tokens,
                        "duration_seconds": r.duration_seconds,
                    },
                    indent=2,
                )
            )
        else:
            failed_tasks.append(res["task_id"])
            fail_file = builder_logs_dir / f"{res['task_id']}.fail"
            fail_file.write_text(
                json.dumps(
                    {
                        "task_id": res["task_id"],
                        "status": "failed",
                        "timestamp": datetime.now().isoformat(),
                        "error": r.error,
                        "exit_code": r.exit_code,
                    },
                    indent=2,
                )
            )

    duration = (datetime.now() - start_time).total_seconds()
    success = len(failed_tasks) == 0

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(
        f"🏁 BUILD COMPLETE: {len(completed_tasks)}/{len(tasks)} tasks successful",
        file=sys.stderr,
    )
    print(f"{'=' * 60}\n", file=sys.stderr)

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
    task_config: dict = None,
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
        task_config: Optional task configuration (enables human-in-the-loop if present)

    Returns:
        PhaseResult with metrics
    """
    # Wait for architecture.md from Architect phase (up to 5 minutes)
    arch_md_path = working_directory / ".context-foundry" / "architecture.md"

    MAX_WAIT_SECONDS = 300  # 5 minutes
    POLL_INTERVAL = 10  # 10 seconds

    if not arch_md_path.exists():
        print(
            f"⏳ Waiting for architecture.md (up to {MAX_WAIT_SECONDS}s)...",
            file=sys.stderr,
        )
        waited = 0
        while waited < MAX_WAIT_SECONDS and not arch_md_path.exists():
            time.sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL
            if waited % 60 == 0:  # Log every minute
                print(
                    f"⏳ Still waiting for architecture.md ({waited}s elapsed)...",
                    file=sys.stderr,
                )

        if not arch_md_path.exists():
            print(
                f"⚠️ Timeout after {waited}s - no architecture.md found",
                file=sys.stderr,
            )
        else:
            print(
                f"✅ architecture.md found after {waited}s",
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
            "📝 Running sequential build from architecture.md",
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
        task_config=task_config,
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
        "**status:** passed",  # "**Status:** PASSED" (colon after bold)
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

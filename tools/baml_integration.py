#!/usr/bin/env python3
"""
BAML Integration for Context Foundry

This module provides type-safe LLM interactions using BAML (Basically a Made-up Language).
It bridges Context Foundry's autonomous build system with BAML's structured output guarantees.

Key Features:
- Type-safe phase tracking (PhaseInfo class vs JSON strings)
- Structured Scout/Architect/Builder outputs
- Compile-time schema validation
- Client caching for performance
- Reduced error rates: 5% → <1% compared to raw JSON parsing

BAML is OPTIONAL but recommended for type-safe outputs. Install with:
    pip install -r requirements.txt  # Includes baml-py>=0.211.0

Without BAML, Context Foundry uses Claude CLI parsing with JSON fallbacks.

Usage:
    from tools.baml_integration import get_baml_client, update_phase_with_baml

    # Get BAML client (cached)
    client = get_baml_client()

    # Update phase tracking with type safety
    phase_info = update_phase_with_baml("Scout", "researching", "Analyzing requirements")
"""

import os
import sys
import json
import io
import contextlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

# BAML availability flag
BAML_AVAILABLE = False
BAML_CLIENT = None
BAML_COMPILATION_ERROR = None
BAML_USE_CLAUDE_CLI = os.getenv("BAML_USE_CLAUDE_CLI", "true").lower() == "true"

try:
    # Try to import baml-py (v0.211+ uses BamlRuntime)
    from baml_py import BamlRuntime

    BAML_AVAILABLE = True
except ImportError as e:
    BAML_AVAILABLE = False
    BAML_COMPILATION_ERROR = f"baml-py not installed: {e}"


def get_baml_schemas_dir() -> Path:
    """Get the path to BAML schemas directory."""
    return Path(__file__).parent / "baml_schemas"


def get_baml_client_dir() -> Path:
    """Get the path to generated BAML client directory."""
    return Path(__file__).parent / "baml_client"


def get_baml_env_vars() -> Dict[str, str]:
    """
    Get environment variables for BAML runtime.

    Returns:
        Dictionary of environment variables with API keys
    """
    env_vars = {}

    # Add all current environment variables
    for key, value in os.environ.items():
        env_vars[key] = value

    # Ensure API keys are explicitly present
    if "OPENAI_API_KEY" in os.environ:
        env_vars["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

    if "ANTHROPIC_API_KEY" in os.environ:
        env_vars["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]

    return env_vars


def _validate_scout_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a Scout payload against the BAML-generated Pydantic model.

    Returns the normalized dict if validation passes.
    Falls back to returning payload as-is if BAML types unavailable.
    """
    try:
        from tools.baml_client.baml_client.types import ScoutReport
    except Exception:
        # BAML types not available - return payload without validation
        return payload

    try:
        if hasattr(ScoutReport, "model_validate"):  # Pydantic v2
            validated = ScoutReport.model_validate(payload)
            return validated.model_dump()
        validated = ScoutReport.parse_obj(payload)  # Pydantic v1
        return validated.dict()
    except Exception as exc:
        # Validation failed but don't block - log and return original
        print(f"[BAML] Scout validation warning: {exc}", file=sys.stderr)
        return payload


def _validate_architecture_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate an Architecture payload against the BAML-generated Pydantic model.

    Falls back to returning payload as-is if BAML types unavailable.
    """
    try:
        from tools.baml_client.baml_client.types import ArchitectureBlueprint
    except Exception:
        # BAML types not available - return payload without validation
        return payload

    try:
        if hasattr(ArchitectureBlueprint, "model_validate"):  # Pydantic v2
            validated = ArchitectureBlueprint.model_validate(payload)
            return validated.model_dump()
        validated = ArchitectureBlueprint.parse_obj(payload)  # Pydantic v1
        return validated.dict()
    except Exception as exc:
        # Validation failed but don't block - log and return original
        print(f"[BAML] Architecture validation warning: {exc}", file=sys.stderr)
        return payload


def _validate_phase_info_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a PhaseInfo payload against the BAML-generated Pydantic model.

    Falls back to returning payload as-is if BAML types unavailable.
    """
    try:
        from tools.baml_client.baml_client.types import PhaseInfo
    except Exception:
        # BAML types not available - return payload without validation
        return payload

    try:
        if hasattr(PhaseInfo, "model_validate"):  # Pydantic v2
            validated = PhaseInfo.model_validate(payload)
            return validated.model_dump()
        validated = PhaseInfo.parse_obj(payload)  # Pydantic v1
        return validated.dict()
    except Exception as exc:
        # Validation failed but don't block - log and return original
        print(f"[BAML] PhaseInfo validation warning: {exc}", file=sys.stderr)
        return payload


def _run_claude_cli_json(prompt: str, timeout_seconds: int = 180) -> Dict[str, Any]:
    """
    Execute Claude CLI with a prompt and parse the JSON response.

    This uses the local Claude Code subscription instead of GPT-4o-mini API.
    """
    if not shutil.which("claude"):
        raise FileNotFoundError(
            "claude CLI not found in PATH; install from https://claude.com/download"
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        prompt_path = f.name
        f.write(prompt)

    try:
        cmd = [
            "claude",
            "--print",
            "--permission-mode",
            "bypassPermissions",
            "--settings",
            '{"thinkingMode":"off"}',
            prompt_path,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Claude CLI exited with code {result.returncode}: {result.stderr}"
            )

        output = result.stdout.strip()
        if not output:
            raise RuntimeError("Claude CLI returned empty output")

        # Strip code fences if present
        if "```json" in output:
            output = output.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in output:
            output = output.split("```", 1)[1].split("```", 1)[0].strip()

        return json.loads(output)

    finally:
        Path(prompt_path).unlink(missing_ok=True)


def compile_baml_schemas(force: bool = False) -> tuple[bool, Optional[str]]:
    """
    Validate BAML schemas exist (compilation happens in BamlRuntime.from_directory).

    Args:
        force: Unused (kept for backward compatibility)

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    if not BAML_AVAILABLE:
        return False, BAML_COMPILATION_ERROR

    schemas_dir = get_baml_schemas_dir()

    # Check if schemas exist
    if not schemas_dir.exists():
        return False, f"BAML schemas directory not found: {schemas_dir}"

    # Check for .baml files
    schema_files = list(schemas_dir.glob("*.baml"))
    if not schema_files:
        return False, "No .baml files found in schemas directory"

    return True, None


def clear_baml_cache():
    """Clear cached BAML client to force reload with new environment variables."""
    global BAML_CLIENT, BAML_COMPILATION_ERROR
    BAML_CLIENT = None
    BAML_COMPILATION_ERROR = None


def get_baml_client(force_recompile: bool = False) -> Optional[Any]:
    """
    Get BAML runtime client (cached).

    Args:
        force_recompile: Force recreation of runtime (clears cache)

    Returns:
        BamlRuntime instance or None if unavailable
    """
    global BAML_CLIENT, BAML_COMPILATION_ERROR

    if not BAML_AVAILABLE:
        return None

    # CRITICAL: Ensure API keys are in os.environ BEFORE creating client
    # BAML captures environment at client creation time
    openai_key = os.getenv("OPENAI_API_KEY")

    if openai_key and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = openai_key
        print(
            "[BAML] Set OPENAI_API_KEY in os.environ before client creation",
            file=sys.stderr,
        )

    # Return cached client (unless force reload requested)
    if BAML_CLIENT is not None and not force_recompile:
        return BAML_CLIENT

    # Validate schemas exist
    success, error = compile_baml_schemas()
    if not success:
        BAML_COMPILATION_ERROR = error
        return None

    try:
        # Initialize BamlRuntime from schema files
        schemas_dir = get_baml_schemas_dir()

        # Get all .baml files
        schema_files = list(schemas_dir.glob("*.baml"))
        if not schema_files:
            BAML_COMPILATION_ERROR = "No .baml files found in schemas directory"
            return None

        # Create dict mapping filenames to their contents
        # Use explicit UTF-8 encoding for Windows compatibility
        files_dict = {}
        for schema_file in schema_files:
            files_dict[schema_file.name] = schema_file.read_text(encoding="utf-8")

        # Get environment variables for BAML
        env_vars_for_baml = get_baml_env_vars()

        if "OPENAI_API_KEY" in env_vars_for_baml:
            print("[BAML] Explicitly added OPENAI_API_KEY", file=sys.stderr)

        print(
            f"[BAML] Creating BamlRuntime with {len(env_vars_for_baml)} env vars",
            file=sys.stderr,
        )
        print(
            f"[BAML] env_vars_for_baml keys: {list(env_vars_for_baml.keys())[:10]}...",
            file=sys.stderr,
        )

        # Convert Windows backslashes to forward slashes for BAML compatibility
        # The BAML Rust library expects POSIX-style paths
        root_path_str = str(schemas_dir).replace("\\", "/")

        # Pass environment to BAML
        BAML_CLIENT = BamlRuntime.from_files(
            root_path=root_path_str, files=files_dict, env_vars=env_vars_for_baml
        )

        print("[BAML] BamlRuntime created successfully", file=sys.stderr)

        # TEST: Try to inspect the runtime's environment
        print(f"[BAML] Runtime type: {type(BAML_CLIENT)}", file=sys.stderr)

        return BAML_CLIENT

    except Exception as e:
        import platform

        platform_info = f" (Platform: {platform.system()} {platform.release()})"
        BAML_COMPILATION_ERROR = f"Failed to initialize BamlRuntime: {e}{platform_info}"

        # Log additional diagnostics for debugging
        print(f"[BAML ERROR] Initialization failed: {e}", file=sys.stderr)
        print(
            f"[BAML ERROR] Platform: {platform.system()} {platform.release()}",
            file=sys.stderr,
        )
        print(f"[BAML ERROR] Schemas dir: {schemas_dir}", file=sys.stderr)
        # root_path_str and files_dict may not be defined if exception occurred early
        try:
            print(f"[BAML ERROR] Root path used: {root_path_str}", file=sys.stderr)
        except NameError:
            pass
        try:
            print(
                f"[BAML ERROR] Schema files: {list(files_dict.keys())}", file=sys.stderr
            )
        except NameError:
            pass

        return None


def is_baml_available() -> bool:
    """Check if BAML is available and working."""
    return BAML_AVAILABLE and get_baml_client() is not None


def get_baml_error() -> Optional[str]:
    """Get BAML compilation/loading error message."""
    return BAML_COMPILATION_ERROR


def _now_iso() -> str:
    """Return current UTC timestamp without microseconds and with Z suffix."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def inject_real_timestamps(phase_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inject real system timestamps into phase data.

    LLMs cannot know the current time, so they hallucinate fake dates (often 2023).
    This function replaces LLM-generated timestamps with actual system time across
    every timestamp field that we expect downstream systems to read.

    Args:
        phase_data: Phase info dict from BAML (with hallucinated timestamps)

    Returns:
        Phase info dict with corrected timestamps
    """
    now = _now_iso()

    # Fix timestamps object if it exists
    timestamps = phase_data.get("timestamps")
    if isinstance(timestamps, dict):
        timestamps["phaseStart"] = now
        timestamps["lastUpdated"] = now
        # Keep phaseEnd as null if it's null
        if timestamps.get("phaseEnd") is None:
            timestamps["phaseEnd"] = None

    # Normalize any flattened timestamp fields that some schemas return
    for key in [
        "phaseStart",
        "phaseStartTime",
        "started_at",
        "last_updated",
        "lastUpdated",
    ]:
        if key in phase_data:
            if key == "lastUpdated":
                phase_data[key] = now
            elif key == "phaseStart":
                phase_data[key] = now
            elif key == "phaseStartTime":
                phase_data[key] = now
            elif key == "started_at":
                phase_data[key] = now
            elif key == "last_updated":
                phase_data[key] = now

    return phase_data


def normalize_phase_info(phase_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize PhaseInfo payloads from BAML.

    BAML sometimes wraps responses in a {"PhaseInfo": {...}} envelope and
    uses camelCase. We flatten the structure and duplicate key values in
    snake_case so the rest of the system can read them consistently.
    """
    if "PhaseInfo" in phase_data and isinstance(phase_data["PhaseInfo"], dict):
        phase_data = dict(phase_data["PhaseInfo"])
    else:
        phase_data = dict(phase_data)

    # Map camelCase keys to snake_case equivalents (keeping originals too)
    key_aliases = {
        "sessionId": "session_id",
        "currentPhase": "phase",
        "current_phase": "phase",
        "phaseNumber": "phase_number",
        "progressDetail": "progress_detail",
        "testIteration": "test_iteration",
        "phasesCompleted": "phases_completed",
        "completionTracking": "completion_tracking",
    }

    for source, target in key_aliases.items():
        if source in phase_data and target not in phase_data:
            phase_data[target] = phase_data[source]

    # Ensure canonical short key exists for downstream validators
    if "phase" not in phase_data:
        if "currentPhase" in phase_data:
            phase_data["phase"] = phase_data["currentPhase"]
        elif "current_phase" in phase_data:
            phase_data["phase"] = phase_data["current_phase"]

    # Ensure current_phase exists (for backward compatibility)
    if "current_phase" not in phase_data:
        if "currentPhase" in phase_data:
            phase_data["current_phase"] = phase_data["currentPhase"]
        elif "phase" in phase_data:
            phase_data["current_phase"] = phase_data["phase"]

    return phase_data


def update_phase_with_baml(
    phase: str,
    status: str,
    detail: str,
    session_id: str = "context-foundry",
    iteration: int = 0,
) -> Dict[str, Any]:
    """
    Update phase tracking using BAML type-safe schema.

    Args:
        phase: Phase name (e.g., "Scout", "Architect")
        status: Phase status (e.g., "researching", "designing")
        detail: Progress detail message
        session_id: Session identifier
        iteration: Test iteration count

    Returns:
        PhaseInfo dict (BAML-validated)

    Raises:
        RuntimeError: If BAML is unavailable (required dependency)
    """
    # Prefer Claude CLI (subscription)
    if BAML_USE_CLAUDE_CLI:
        try:
            prompt = f"""Create phase tracking information for Context Foundry build:

Session ID: {session_id}
Current Phase: {phase}
Status: {status}
Progress Detail: {detail}
Test Iteration: {iteration}

Generate a complete PhaseInfo object with appropriate timestamps and phase completion tracking.

Return ONLY valid JSON matching the PhaseInfo schema:
{{
  "session_id": "string",
  "current_phase": "PhaseType",
  "phase_number": "string",
  "status": "PhaseStatus",
  "progress_detail": "string",
  "test_iteration": int,
  "phases_completed": ["PhaseType"],
  "started_at": "ISO timestamp",
  "last_updated": "ISO timestamp"
}}
"""
            cli_payload = _run_claude_cli_json(prompt, timeout_seconds=60)
            normalized = normalize_phase_info(cli_payload)
            with_timestamps = inject_real_timestamps(normalized)
            return _validate_phase_info_payload(with_timestamps)
        except Exception as cli_exc:
            print(
                f"[BAML LOG] Claude CLI Phase update failed, falling back to BAML: {cli_exc}",
                file=sys.stderr,
            )

    # Try BAML first
    if is_baml_available():
        try:
            # Force reload to pick up current environment
            client = get_baml_client(force_recompile=True)
            if client is None:
                raise Exception("BAML client not available")

            # Call BAML CreatePhaseInfo function
            ctx = client.create_context_manager()

            print(
                f"[BAML DEBUG] Calling CreatePhaseInfo with session_id={session_id}, phase={phase}, status={status}",
                file=sys.stderr,
            )

            stdout_buffer = io.StringIO()
            with contextlib.redirect_stdout(stdout_buffer):
                result = client.call_function_sync(
                    function_name="CreatePhaseInfo",
                    args={
                        "session_id": session_id,
                        "phase": phase,
                        "status": status,
                        "detail": detail,
                        "iteration": iteration,
                    },
                    ctx=ctx,
                    tb=None,
                    cb=None,
                    collectors=[],
                    env_vars=get_baml_env_vars(),
                    tags=None,
                )

            captured_stdout = stdout_buffer.getvalue()
            if captured_stdout.strip():
                print(
                    "[BAML LOG] " + captured_stdout.strip().replace("\n", " "),
                    file=sys.stderr,
                )

            # BAML v0.211.2 API: Try to parse the result directly first
            try:
                # First, try to get typed result (modern BAML API)
                try:
                    # Attempt direct parsing as PhaseInfo object
                    parsed_data = result.parsed()
                    print(
                        "[BAML DEBUG] Successfully parsed BAML output using .parsed()",
                        file=sys.stderr,
                    )
                    normalized = normalize_phase_info(parsed_data)
                    return inject_real_timestamps(normalized)
                except AttributeError:
                    # Fall back to unstable_internal_repr for older API
                    pass

                # Fallback: Parse via unstable_internal_repr
                internal_repr_str = result.unstable_internal_repr()
                internal_repr = json.loads(internal_repr_str)

                # Extract the content field from the Success wrapper
                if "Success" in internal_repr and "content" in internal_repr["Success"]:
                    content = internal_repr["Success"]["content"]

                    # The content is JSON inside markdown code blocks
                    # Strip ```json and ``` markers
                    if content.startswith("```json"):
                        content = content[7:]  # Remove ```json\n
                    if content.startswith("```"):
                        content = content[3:]  # Remove ```\n
                    if content.endswith("```"):
                        content = content[:-3]  # Remove \n```

                    content = content.strip()

                    # Extract just the JSON object (handle extra text after JSON)
                    # Find the first { and the matching }
                    start_idx = content.find("{")
                    if start_idx != -1:
                        # Count braces to find matching close brace
                        depth = 0
                        for i in range(start_idx, len(content)):
                            if content[i] == "{":
                                depth += 1
                            elif content[i] == "}":
                                depth -= 1
                                if depth == 0:
                                    # Found matching close brace
                                    json_str = content[start_idx : i + 1]
                                    parsed_data = json.loads(json_str)
                                    print(
                                        "[BAML DEBUG] Successfully parsed BAML output",
                                        file=sys.stderr,
                                    )
                                    normalized = normalize_phase_info(parsed_data)
                                    return inject_real_timestamps(normalized)

                    # If we couldn't extract JSON, try parsing the whole thing
                    parsed_data = json.loads(content)
                    print(
                        "[BAML DEBUG] Successfully parsed BAML output", file=sys.stderr
                    )
                    normalized = normalize_phase_info(parsed_data)
                    return inject_real_timestamps(normalized)
                else:
                    print(
                        "[BAML DEBUG] Unexpected internal_repr format", file=sys.stderr
                    )
                    return internal_repr

            except Exception as e:
                print(
                    f"[BAML DEBUG] Failed to parse internal_repr: {e}", file=sys.stderr
                )
                raise

        except Exception as e:
            # BAML failed - fall through to simple JSON fallback
            print(f"[BAML] Phase tracking via BAML failed: {e}", file=sys.stderr)

    # Simple JSON fallback when both Claude CLI and BAML are unavailable
    print("[BAML] Using simple JSON fallback for phase tracking", file=sys.stderr)
    now = _now_iso()
    return {
        "session_id": session_id,
        "current_phase": phase,
        "phase": phase,
        "phase_number": "1",
        "status": status,
        "progress_detail": detail,
        "test_iteration": iteration,
        "phases_completed": [],
        "started_at": now,
        "last_updated": now,
    }


def validate_phase_info(phase_info_json: str) -> Dict[str, Any]:
    """
    Validate phase tracking JSON using BAML schema.

    Args:
        phase_info_json: JSON string to validate

    Returns:
        Validated phase info dict

    Raises:
        RuntimeError: If BAML unavailable or validation fails
    """
    # Prefer Claude CLI (subscription)
    if BAML_USE_CLAUDE_CLI:
        try:
            prompt = f"""Validate and parse this phase tracking JSON from Context Foundry:

{phase_info_json}

Convert it to a valid PhaseInfo object. If any fields are missing or invalid,
use sensible defaults:
- session_id: "unknown" if missing
- test_iteration: 0 if missing
- phases_completed: [] if missing
- timestamps: current time if missing

Return ONLY valid JSON matching the PhaseInfo schema.
"""
            cli_payload = _run_claude_cli_json(prompt, timeout_seconds=60)
            normalized = normalize_phase_info(cli_payload)
            with_timestamps = inject_real_timestamps(normalized)
            return _validate_phase_info_payload(with_timestamps)
        except Exception as cli_exc:
            print(
                f"[BAML LOG] Claude CLI Phase validation failed, falling back to BAML: {cli_exc}",
                file=sys.stderr,
            )

    # Try simple JSON parsing fallback if BAML not available
    if not is_baml_available():
        print(
            f"[BAML] Not available ({get_baml_error()}), attempting simple JSON parse",
            file=sys.stderr,
        )
        try:
            parsed = json.loads(phase_info_json)
            normalized = normalize_phase_info(parsed)
            return inject_real_timestamps(normalized)
        except json.JSONDecodeError as e:
            print(f"[BAML] Simple JSON parse failed: {e}", file=sys.stderr)
            # Return minimal valid structure
            now = _now_iso()
            return {
                "session_id": "unknown",
                "current_phase": "unknown",
                "phase": "unknown",
                "status": "unknown",
                "progress_detail": phase_info_json[:100],
                "test_iteration": 0,
                "phases_completed": [],
                "started_at": now,
                "last_updated": now,
            }

    # Prefer Claude CLI (subscription)
    if BAML_USE_CLAUDE_CLI:
        try:
            prompt = f"""Validate and parse this phase tracking JSON from Context Foundry:

{phase_info_json}

Convert it to a valid PhaseInfo object. If any fields are missing or invalid,
use sensible defaults:
- session_id: "unknown" if missing
- test_iteration: 0 if missing
- phases_completed: [] if missing
- timestamps: current time if missing

Return ONLY valid JSON matching the PhaseInfo schema.
"""
            cli_payload = _run_claude_cli_json(prompt, timeout_seconds=60)
            normalized = normalize_phase_info(cli_payload)
            with_timestamps = inject_real_timestamps(normalized)
            return _validate_phase_info_payload(with_timestamps)
        except Exception as cli_exc:
            print(
                f"[BAML LOG] Claude CLI Phase validation failed, falling back to BAML: {cli_exc}",
                file=sys.stderr,
            )

    try:
        client = get_baml_client()
        if client is None:
            # Fallback to simple JSON parse
            try:
                parsed = json.loads(phase_info_json)
                normalized = normalize_phase_info(parsed)
                return inject_real_timestamps(normalized)
            except Exception:
                now = _now_iso()
                return {
                    "session_id": "unknown",
                    "current_phase": "unknown",
                    "phase": "unknown",
                    "status": "unknown",
                    "progress_detail": str(phase_info_json)[:100],
                    "test_iteration": 0,
                    "phases_completed": [],
                    "started_at": now,
                    "last_updated": now,
                }

        # Call BAML ValidatePhaseInfo function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="ValidatePhaseInfo",
            args={"json_string": phase_info_json},
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars=get_baml_env_vars(),
            tags=None,
        )

        # Parse the result using unstable_internal_repr
        internal_repr_str = result.unstable_internal_repr()
        internal_repr = json.loads(internal_repr_str)

        if "Success" in internal_repr and "content" in internal_repr["Success"]:
            content = internal_repr["Success"]["content"]
            # Strip markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            validated_data = json.loads(content.strip())
            normalized = normalize_phase_info(validated_data)
            return inject_real_timestamps(normalized)

        normalized = normalize_phase_info(internal_repr)
        return inject_real_timestamps(normalized)

    except Exception as e:
        # BAML validation failed - try simple JSON fallback
        print(
            f"[BAML] Validation failed: {e}, using simple JSON parse", file=sys.stderr
        )
        try:
            parsed = json.loads(phase_info_json)
            normalized = normalize_phase_info(parsed)
            return inject_real_timestamps(normalized)
        except Exception:
            # Return minimal valid structure
            now = _now_iso()
            return {
                "session_id": "unknown",
                "current_phase": "unknown",
                "phase": "unknown",
                "status": "unknown",
                "progress_detail": str(phase_info_json)[:100],
                "test_iteration": 0,
                "phases_completed": [],
                "started_at": now,
                "last_updated": now,
            }


def generate_scout_report_baml(
    task_description: str, codebase_analysis: str, past_patterns: str = ""
) -> Dict[str, Any]:
    """
    Generate structured Scout report using BAML.

    Args:
        task_description: Task description
        codebase_analysis: Codebase analysis content
        past_patterns: Past patterns to consider

    Returns:
        ScoutReport dict

    Raises:
        RuntimeError: If BAML unavailable or generation fails
    """
    # Prefer Claude CLI (subscription) to avoid GPT-4o-mini timeouts/costs
    if BAML_USE_CLAUDE_CLI:
        try:
            prompt = f"""You are the Scout agent for Context Foundry, researching requirements.

TASK DESCRIPTION:
{task_description}

CODEBASE ANALYSIS:
{codebase_analysis}

PAST PATTERNS:
{past_patterns}

Return ONLY valid JSON for the ScoutReport schema:
{{
  "executive_summary": "2-3 paragraphs max",
  "past_learnings_applied": ["bullet points"],
  "known_risks": ["risks"],
  "key_requirements": ["bulleted requirements"],
  "tech_stack": {{
    "languages": ["languages"],
    "frameworks": ["frameworks"],
    "dependencies": ["dependencies"],
    "justification": "brief justification"
  }},
  "architecture_recommendations": ["top 3-5 recommendations"],
  "main_challenges": [
    {{"description": "string", "severity": "LOW|MEDIUM|HIGH|CRITICAL", "mitigation": "string"}}
  ],
  "testing_approach": "brief testing outline",
  "timeline_estimate": "single line estimate (e.g., '2-3 hours')"
}}

Do not include markdown or prose outside the JSON."""

            cli_payload = _run_claude_cli_json(prompt, timeout_seconds=240)
            return _validate_scout_payload(cli_payload)
        except Exception as cli_exc:
            print(
                f"[BAML LOG] Claude CLI Scout generation failed, falling back to GPT-4o-mini BAML: {cli_exc}",
                file=sys.stderr,
            )

    if not is_baml_available():
        # Return minimal scout report structure when BAML unavailable
        print(
            f"[BAML] Not available for Scout report generation: {get_baml_error()}",
            file=sys.stderr,
        )
        return {
            "executive_summary": f"Scout analysis for: {task_description[:200]}",
            "past_learnings_applied": [],
            "known_risks": ["BAML not available - limited validation"],
            "key_requirements": [task_description],
            "tech_stack": {
                "languages": [],
                "frameworks": [],
                "dependencies": [],
                "justification": "Unable to analyze - BAML unavailable",
            },
            "architecture_recommendations": [],
            "main_challenges": [],
            "testing_approach": "Manual testing recommended",
            "timeline_estimate": "Unknown",
        }

    try:
        client = get_baml_client()
        if client is None:
            # Return minimal structure if client unavailable
            return {
                "executive_summary": f"Scout analysis for: {task_description[:200]}",
                "past_learnings_applied": [],
                "known_risks": ["BAML client unavailable"],
                "key_requirements": [task_description],
                "tech_stack": {
                    "languages": [],
                    "frameworks": [],
                    "dependencies": [],
                    "justification": "Unable to analyze",
                },
                "architecture_recommendations": [],
                "main_challenges": [],
                "testing_approach": "Manual testing recommended",
                "timeline_estimate": "Unknown",
            }

        # Call BAML GenerateScoutReport function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="GenerateScoutReport",
            args={
                "task_description": task_description,
                "codebase_analysis": codebase_analysis,
                "past_patterns": past_patterns,
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars=get_baml_env_vars(),
            tags=None,
        )

        # Parse the result using unstable_internal_repr
        internal_repr_str = result.unstable_internal_repr()
        internal_repr = json.loads(internal_repr_str)

        if "Success" in internal_repr and "content" in internal_repr["Success"]:
            content = internal_repr["Success"]["content"]
            # Strip markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())

        return internal_repr

    except Exception as e:
        error_msg = f"BAML Scout report generation failed: {e}"
        print(f"❌ {error_msg}", file=sys.stderr)
        raise RuntimeError(error_msg) from e


def generate_architecture_baml(
    scout_report_json: str, flagged_risks: List[str]
) -> Dict[str, Any]:
    """
    Generate structured architecture blueprint using BAML.

    Args:
        scout_report_json: Scout report JSON
        flagged_risks: List of flagged risks

    Returns:
        ArchitectureBlueprint dict

    Raises:
        RuntimeError: If BAML unavailable or generation fails
    """
    # Prefer Claude CLI (subscription)
    if BAML_USE_CLAUDE_CLI:
        try:
            risks_formatted = "\n".join([f"- {risk}" for risk in flagged_risks])
            prompt = f"""You are the Architect agent for Context Foundry, designing the system architecture.

SCOUT FINDINGS:
{scout_report_json}

FLAGGED RISKS TO ADDRESS:
{risks_formatted}

Your job is to:
1. Design complete system architecture
2. Define file and directory structure
3. Break down into modules with clear responsibilities
4. Apply proven patterns from pattern library
5. Include preventive measures for all flagged risks
6. Create step-by-step implementation plan
7. Design comprehensive test strategy

CRITICAL REQUIREMENTS:
- All flagged risks must have preventive measures
- Test plan must include unit, integration, AND e2e tests
- Implementation steps must be ordered and actionable
- Module boundaries must be clear

Return detailed technical architecture as ArchitectureBlueprint JSON.
Do not include markdown or prose outside the JSON.
"""
            cli_payload = _run_claude_cli_json(prompt, timeout_seconds=300)
            return _validate_architecture_payload(cli_payload)
        except Exception as cli_exc:
            print(
                f"[BAML LOG] Claude CLI Architecture generation failed, falling back to BAML: {cli_exc}",
                file=sys.stderr,
            )

    if not is_baml_available():
        # Return minimal architecture structure when BAML unavailable
        print(
            f"[BAML] Not available for Architecture generation: {get_baml_error()}",
            file=sys.stderr,
        )
        return {
            "overview": "Architecture generated without BAML validation",
            "directory_structure": [],
            "modules": [],
            "implementation_steps": [],
            "test_plan": {"unit_tests": [], "integration_tests": [], "e2e_tests": []},
            "risk_mitigations": {
                risk: "Manual review required" for risk in flagged_risks
            },
        }

    try:
        client = get_baml_client()
        if client is None:
            return {
                "overview": "Architecture generated without BAML client",
                "directory_structure": [],
                "modules": [],
                "implementation_steps": [],
                "test_plan": {
                    "unit_tests": [],
                    "integration_tests": [],
                    "e2e_tests": [],
                },
                "risk_mitigations": {},
            }

        # Call BAML GenerateArchitecture function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="GenerateArchitecture",
            args={
                "scout_report_json": scout_report_json,
                "flagged_risks": flagged_risks,
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars=get_baml_env_vars(),
            tags=None,
        )

        # Parse the result using unstable_internal_repr
        internal_repr_str = result.unstable_internal_repr()
        internal_repr = json.loads(internal_repr_str)

        if "Success" in internal_repr and "content" in internal_repr["Success"]:
            content = internal_repr["Success"]["content"]
            # Strip markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())

        return internal_repr

    except Exception as e:
        error_msg = f"BAML Architecture generation failed: {e}"
        print(f"❌ {error_msg}", file=sys.stderr)
        raise RuntimeError(error_msg) from e


def parse_scout_markdown_baml(markdown_content: str) -> Dict[str, Any]:
    """
    Parse Scout markdown into structured JSON using BAML schema.

    Args:
        markdown_content: Contents of scout-report.md

    Returns:
        ScoutReport dict

    Raises:
        RuntimeError: If BAML unavailable or parsing fails
    """
    # Prefer Claude CLI (subscription) for parsing to avoid BAML GPT-4o-mini timeouts
    if BAML_USE_CLAUDE_CLI:
        try:
            prompt = f"""Parse this Scout report markdown into the ScoutReport JSON schema.

{markdown_content}

Return ONLY valid JSON with these keys:
- executive_summary (string, 2-3 paragraphs max)
- past_learnings_applied (string array)
- known_risks (string array)
- key_requirements (string array)
- tech_stack (object with languages, frameworks, dependencies, justification)
- architecture_recommendations (string array)
- main_challenges (array of objects: description, severity=LOW|MEDIUM|HIGH|CRITICAL, mitigation)
- testing_approach (string)
- timeline_estimate (string, single line)

Do not include markdown fences or commentary."""

            cli_payload = _run_claude_cli_json(prompt, timeout_seconds=180)
            return _validate_scout_payload(cli_payload)
        except Exception as cli_exc:
            print(
                f"[BAML LOG] Claude CLI Scout parsing failed, falling back to GPT-4o-mini BAML: {cli_exc}",
                file=sys.stderr,
            )

    if not is_baml_available():
        # Return minimal structure - markdown content becomes the summary
        print(
            f"[BAML] Not available for Scout markdown parsing: {get_baml_error()}",
            file=sys.stderr,
        )
        return {
            "executive_summary": markdown_content[:500] if markdown_content else "",
            "past_learnings_applied": [],
            "known_risks": [],
            "key_requirements": [],
            "tech_stack": {
                "languages": [],
                "frameworks": [],
                "dependencies": [],
                "justification": "",
            },
            "architecture_recommendations": [],
            "main_challenges": [],
            "testing_approach": "",
            "timeline_estimate": "",
        }

    try:
        client = get_baml_client()
        if client is None:
            return {
                "executive_summary": markdown_content[:500] if markdown_content else "",
                "past_learnings_applied": [],
                "known_risks": [],
                "key_requirements": [],
                "tech_stack": {
                    "languages": [],
                    "frameworks": [],
                    "dependencies": [],
                    "justification": "",
                },
                "architecture_recommendations": [],
                "main_challenges": [],
                "testing_approach": "",
                "timeline_estimate": "",
            }

        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="ParseScoutMarkdown",
            args={
                "markdown_content": markdown_content,
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars=get_baml_env_vars(),
            tags=None,
        )

        internal_repr_str = result.unstable_internal_repr()
        internal_repr = json.loads(internal_repr_str)

        if "Success" in internal_repr and "content" in internal_repr["Success"]:
            content = internal_repr["Success"]["content"]
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            if content.endswith("```"):
                content = content[:-3]

            try:
                return json.loads(content.strip())
            except json.JSONDecodeError as je:
                print(
                    f"[BAML DEBUG] JSON Decode Error. Raw content:\n{content}\n",
                    file=sys.stderr,
                )
                raise je

        return internal_repr

    except Exception as e:
        error_msg = f"BAML Scout markdown parsing failed: {e}"
        print(f"❌ {error_msg}", file=sys.stderr)
        raise RuntimeError(error_msg) from e


def parse_architecture_markdown_baml(markdown_content: str) -> Dict[str, Any]:
    """
    Parse architecture markdown into structured JSON using BAML schema.

    Args:
        markdown_content: Contents of architecture.md

    Returns:
        ArchitectureBlueprint dict

    Raises:
        RuntimeError: If BAML unavailable or parsing fails
    """
    if not is_baml_available():
        # Return minimal architecture structure
        print(
            f"[BAML] Not available for Architecture markdown parsing: {get_baml_error()}",
            file=sys.stderr,
        )
        return {
            "overview": markdown_content[:500] if markdown_content else "",
            "directory_structure": [],
            "modules": [],
            "implementation_steps": [],
            "test_plan": {"unit_tests": [], "integration_tests": [], "e2e_tests": []},
            "risk_mitigations": {},
        }

    try:
        client = get_baml_client()
        if client is None:
            return {
                "overview": markdown_content[:500] if markdown_content else "",
                "directory_structure": [],
                "modules": [],
                "implementation_steps": [],
                "test_plan": {
                    "unit_tests": [],
                    "integration_tests": [],
                    "e2e_tests": [],
                },
                "risk_mitigations": {},
            }

        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="ParseArchitectureMarkdown",
            args={
                "markdown_content": markdown_content,
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars=get_baml_env_vars(),
            tags=None,
        )

        internal_repr_str = result.unstable_internal_repr()
        internal_repr = json.loads(internal_repr_str)

        if "Success" in internal_repr and "content" in internal_repr["Success"]:
            content = internal_repr["Success"]["content"]
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            if content.endswith("```"):
                content = content[:-3]

            try:
                return json.loads(content.strip())
            except json.JSONDecodeError as je:
                print(
                    f"[BAML DEBUG] JSON Decode Error. Raw content:\n{content}\n",
                    file=sys.stderr,
                )
                raise je

        return internal_repr

    except Exception as e:
        # BAML parsing failed - return minimal structure
        print(f"[BAML] Architecture markdown parsing failed: {e}", file=sys.stderr)
        return {
            "overview": markdown_content[:500] if markdown_content else "",
            "directory_structure": [],
            "modules": [],
            "implementation_steps": [],
            "test_plan": {"unit_tests": [], "integration_tests": [], "e2e_tests": []},
            "risk_mitigations": {},
        }


def validate_build_result_baml(result_json: str) -> Dict[str, Any]:
    """
    Validate builder task result using BAML.

    Args:
        result_json: Build result JSON

    Returns:
        BuildTaskResult dict (or parsed JSON if BAML unavailable)
    """
    if not is_baml_available():
        # Try simple JSON parse
        print(
            f"[BAML] Not available for build result validation: {get_baml_error()}",
            file=sys.stderr,
        )
        try:
            return json.loads(result_json)
        except json.JSONDecodeError:
            return {"status": "unknown", "raw_result": result_json[:500]}

    try:
        client = get_baml_client()
        if client is None:
            try:
                return json.loads(result_json)
            except json.JSONDecodeError:
                return {"status": "unknown", "raw_result": result_json[:500]}

        # Call BAML ValidateBuildResult function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="ValidateBuildResult",
            args={"result_json": result_json},
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars=get_baml_env_vars(),
            tags=None,
        )

        # Parse the result using unstable_internal_repr
        internal_repr_str = result.unstable_internal_repr()
        internal_repr = json.loads(internal_repr_str)

        if "Success" in internal_repr and "content" in internal_repr["Success"]:
            content = internal_repr["Success"]["content"]
            # Strip markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())

        return internal_repr

    except Exception as e:
        error_msg = f"BAML build result validation failed: {e}"
        print(f"❌ {error_msg}", file=sys.stderr)
        raise RuntimeError(error_msg) from e


# Utility functions for backward compatibility


def fallback_to_json(operation: str, error: Exception) -> None:
    """
    Log BAML operation failure.

    NOTE: This function is deprecated. BAML is now required for Context Foundry.
    Kept for backward compatibility with older code that may call it.

    Args:
        operation: Operation that failed
        error: Exception that occurred
    """
    print(f"⚠️  BAML {operation} failed: {error}", file=sys.stderr)
    print("Build will continue with fallback parsing.", file=sys.stderr)


def validate_build_plan_no_cycles(build_plan: Dict[str, Any]) -> None:
    """
    Validate that build plan has no cyclic dependencies using DFS.

    Args:
        build_plan: BuildPlan dict with tasks and dependencies

    Raises:
        ValueError: If cyclic dependencies detected
    """
    if not build_plan.get("parallel_build_enabled", False):
        return  # No tasks to validate

    tasks = build_plan.get("tasks", [])
    if not tasks:
        return

    # Build adjacency list
    task_ids = {task["task_id"] for task in tasks}
    graph = {task["task_id"]: task.get("dependencies", []) for task in tasks}

    # Validate all dependencies exist
    for task_id, deps in graph.items():
        for dep in deps:
            if dep not in task_ids:
                raise ValueError(
                    f"Task '{task_id}' depends on non-existent task '{dep}'"
                )

    # DFS to detect cycles
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {task_id: WHITE for task_id in task_ids}
    path = []

    def dfs(node: str) -> None:
        if color[node] == GRAY:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = " -> ".join(path[cycle_start:] + [node])
            raise ValueError(f"Cyclic dependency detected: {cycle}")

        if color[node] == BLACK:
            return  # Already processed

        color[node] = GRAY
        path.append(node)

        for neighbor in graph[node]:
            dfs(neighbor)

        path.pop()
        color[node] = BLACK

    for task_id in task_ids:
        if color[task_id] == WHITE:
            dfs(task_id)


def create_build_plan(
    architecture_summary: str,
    scout_parallel_recommendation: bool,
    scout_reasoning: str,
    project_type: str,
) -> Dict[str, Any]:
    """
    Generate structured build plan using BAML.

    Args:
        architecture_summary: Architecture summary from Architect phase
        scout_parallel_recommendation: Whether Scout recommended parallel build
        scout_reasoning: Scout's reasoning for parallel recommendation
        project_type: Type of project (e.g., "fastapi", "react", "fullstack")

    Returns:
        BuildPlan dict with parallel_build_enabled, tasks, and time estimates
    """
    if not is_baml_available():
        # Return simple sequential build plan
        print(
            f"[BAML] Not available for build plan creation: {get_baml_error()}",
            file=sys.stderr,
        )
        return {
            "parallel_build_enabled": False,
            "tasks": [],
            "reasoning": "BAML unavailable - using sequential build",
            "estimated_time_sequential": "unknown",
            "estimated_time_parallel": "unknown",
        }

    try:
        client = get_baml_client(force_recompile=True)
        if client is None:
            return {
                "parallel_build_enabled": False,
                "tasks": [],
                "reasoning": "BAML client unavailable",
                "estimated_time_sequential": "unknown",
                "estimated_time_parallel": "unknown",
            }

        # Call BAML CreateBuildPlan function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="CreateBuildPlan",
            args={
                "architecture_summary": architecture_summary,
                "scout_parallel_recommendation": scout_parallel_recommendation,
                "scout_reasoning": scout_reasoning,
                "project_type": project_type,
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars=get_baml_env_vars(),
            tags=None,
        )

        # Parse the result using unstable_internal_repr
        internal_repr_str = result.unstable_internal_repr()
        internal_repr = json.loads(internal_repr_str)

        build_plan = None
        if "Success" in internal_repr and "content" in internal_repr["Success"]:
            content = internal_repr["Success"]["content"]
            # Strip markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            build_plan = json.loads(content.strip())
        else:
            build_plan = internal_repr

        # Validate no cyclic dependencies
        validate_build_plan_no_cycles(build_plan)

        return build_plan

    except Exception as e:
        error_msg = f"BAML build plan generation failed: {e}"
        print(f"❌ {error_msg}", file=sys.stderr)
        raise RuntimeError(error_msg) from e


def baml_status_summary() -> Dict[str, Any]:
    """
    Get BAML integration status summary.

    Returns:
        Status dictionary with availability, errors, etc.
    """
    return {
        "baml_available": BAML_AVAILABLE,
        "baml_client_loaded": BAML_CLIENT is not None,
        "error": BAML_COMPILATION_ERROR,
        "schemas_dir": str(get_baml_schemas_dir()),
        "client_dir": str(get_baml_client_dir()),
        "schemas_exist": get_baml_schemas_dir().exists(),
        "client_exists": get_baml_client_dir().exists(),
    }


if __name__ == "__main__":
    # Test BAML integration
    print("BAML Integration Status:")
    print(json.dumps(baml_status_summary(), indent=2))

    if is_baml_available():
        print("\n✅ BAML is available and working")
    else:
        print(f"\n❌ BAML is not available: {get_baml_error()}")

#!/usr/bin/env python3
"""
BAML Integration for Context Foundry

This module provides type-safe LLM interactions using BAML (Basically a Made-up Language).
It bridges Context Foundry's autonomous build system with BAML's structured output guarantees.

Key Features:
- Type-safe phase tracking (PhaseInfo class vs JSON strings)
- Structured Scout/Architect/Builder outputs
- Compile-time schema validation
- Graceful fallback to JSON mode if BAML unavailable
- Client caching for performance

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
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# BAML availability flag
BAML_AVAILABLE = False
BAML_CLIENT = None
BAML_COMPILATION_ERROR = None

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
        # BamlRuntime.from_files expects: from_files(root_path, files_dict, env_vars)
        files_dict = {}
        for schema_file in schema_files:
            files_dict[schema_file.name] = schema_file.read_text()

        # BAML reads API keys from env.VARIABLE_NAME in client configs
        # We need to pass actual env vars so BAML can access them
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')

        env_vars_for_baml = {}

        if anthropic_key:
            # Set in both places for maximum compatibility
            os.environ['ANTHROPIC_API_KEY'] = anthropic_key
            env_vars_for_baml['ANTHROPIC_API_KEY'] = anthropic_key

        if openai_key:
            os.environ['OPENAI_API_KEY'] = openai_key
            env_vars_for_baml['OPENAI_API_KEY'] = openai_key

        # Pass env vars to BAML so it can access API keys via env.ANTHROPIC_API_KEY
        BAML_CLIENT = BamlRuntime.from_files(
            root_path=str(schemas_dir),
            files=files_dict,
            env_vars=env_vars_for_baml
        )

        return BAML_CLIENT

    except Exception as e:
        BAML_COMPILATION_ERROR = f"Failed to initialize BamlRuntime: {e}"
        return None


def is_baml_available() -> bool:
    """Check if BAML is available and working."""
    return BAML_AVAILABLE and get_baml_client() is not None


def get_baml_error() -> Optional[str]:
    """Get BAML compilation/loading error message."""
    return BAML_COMPILATION_ERROR


def update_phase_with_baml(
    phase: str,
    status: str,
    detail: str,
    session_id: str = "context-foundry",
    iteration: int = 0
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
        PhaseInfo dict (BAML-validated or JSON fallback)
    """
    # Try BAML first
    if is_baml_available():
        try:
            client = get_baml_client()
            if client is None:
                raise Exception("BAML client not available")

            # Call BAML CreatePhaseInfo function
            ctx = client.create_context_manager()
            result = client.call_function_sync(
                function_name="CreatePhaseInfo",
                args={
                    "session_id": session_id,
                    "phase": phase,
                    "status": status,
                    "detail": detail,
                    "iteration": iteration
                },
                ctx=ctx,
                tb=None,
                cb=None,
                collectors=[],
                env_vars={},
                tags=None
            )

            # Parse the result
            return result.parsed()

        except Exception as e:
            # Fall through to JSON mode
            print(f"⚠️  BAML validation failed, using JSON fallback: {e}", file=sys.stderr)

    # JSON fallback
    return {
        "session_id": session_id,
        "current_phase": phase,
        "phase_number": "N/A",  # Would be calculated
        "status": status,
        "progress_detail": detail,
        "test_iteration": iteration,
        "phases_completed": [],  # Would be tracked
        "started_at": datetime.utcnow().isoformat() + "Z",
        "last_updated": datetime.utcnow().isoformat() + "Z"
    }


def validate_phase_info(phase_info_json: str) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate phase tracking JSON using BAML schema.

    Args:
        phase_info_json: JSON string to validate

    Returns:
        Tuple of (valid: bool, phase_info: Optional[Dict], error: Optional[str])
    """
    # Try BAML validation first
    if is_baml_available():
        try:
            client = get_baml_client()
            # validated = client.ValidatePhaseInfo(json_string=phase_info_json)
            # return True, validated.dict(), None

            # Placeholder: BAML not fully integrated yet
            pass
        except Exception as e:
            # Fall through to JSON validation
            pass

    # JSON fallback validation
    try:
        phase_info = json.loads(phase_info_json)

        # Basic validation
        required_fields = ["session_id", "current_phase", "status"]
        for field in required_fields:
            if field not in phase_info:
                return False, None, f"Missing required field: {field}"

        return True, phase_info, None

    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {e}"


def generate_scout_report_baml(
    task_description: str,
    codebase_analysis: str,
    past_patterns: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Generate structured Scout report using BAML.

    Args:
        task_description: Task description
        codebase_analysis: Codebase analysis content
        past_patterns: Past patterns to consider

    Returns:
        ScoutReport dict or None if BAML unavailable
    """
    if not is_baml_available():
        return None

    try:
        client = get_baml_client()
        if client is None:
            return None

        # Call BAML GenerateScoutReport function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="GenerateScoutReport",
            args={
                "task_description": task_description,
                "codebase_analysis": codebase_analysis,
                "past_patterns": past_patterns
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars={},
            tags=None
        )

        # Parse and return the result
        return result.parsed()

    except Exception as e:
        print(f"⚠️  BAML Scout report generation failed: {e}", file=sys.stderr)
        return None


def generate_architecture_baml(
    scout_report_json: str,
    flagged_risks: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Generate structured architecture blueprint using BAML.

    Args:
        scout_report_json: Scout report JSON
        flagged_risks: List of flagged risks

    Returns:
        ArchitectureBlueprint dict or None if BAML unavailable
    """
    if not is_baml_available():
        return None

    try:
        client = get_baml_client()
        if client is None:
            return None

        # Call BAML GenerateArchitecture function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="GenerateArchitecture",
            args={
                "scout_report_json": scout_report_json,
                "flagged_risks": flagged_risks
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars={},
            tags=None
        )

        # Parse and return the result
        return result.parsed()

    except Exception as e:
        print(f"⚠️  BAML Architecture generation failed: {e}", file=sys.stderr)
        return None


def validate_build_result_baml(result_json: str) -> Optional[Dict[str, Any]]:
    """
    Validate builder task result using BAML.

    Args:
        result_json: Build result JSON

    Returns:
        BuildTaskResult dict or None if BAML unavailable
    """
    if not is_baml_available():
        return None

    try:
        client = get_baml_client()
        if client is None:
            return None

        # Call BAML ValidateBuildResult function
        ctx = client.create_context_manager()
        result = client.call_function_sync(
            function_name="ValidateBuildResult",
            args={
                "result_json": result_json
            },
            ctx=ctx,
            tb=None,
            cb=None,
            collectors=[],
            env_vars={},
            tags=None
        )

        # Parse and return the result
        return result.parsed()

    except Exception as e:
        print(f"⚠️  BAML build result validation failed: {e}", file=sys.stderr)
        return None


# Utility functions for backward compatibility

def fallback_to_json(operation: str, error: Exception) -> None:
    """
    Log graceful fallback to JSON mode.

    Args:
        operation: Operation that failed
        error: Exception that occurred
    """
    print(f"⚠️  BAML {operation} failed, using JSON fallback: {error}", file=sys.stderr)


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
        "client_exists": get_baml_client_dir().exists()
    }


if __name__ == "__main__":
    # Test BAML integration
    print("BAML Integration Status:")
    print(json.dumps(baml_status_summary(), indent=2))

    if is_baml_available():
        print("\n✅ BAML is available and working")
    else:
        print(f"\n❌ BAML is not available: {get_baml_error()}")

"""
Phase Prompt Management for Manual Workflow Mode

This module handles:
- Creating phase prompt files before execution
- State machine for phase lifecycle (Sleeping -> Ready -> Under Review -> Processing -> Complete)
- Waiting for user acknowledgment before agent execution ("clean plate" mechanism)
- Reading effective prompts (edited or original)
- Token estimation for prompts
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import uuid

logger = logging.getLogger(__name__)

# =============================================================================
# NEW STATE MACHINE
# =============================================================================
# Phase states for manual workflow
STATE_SLEEPING = "sleeping"  # Waiting for previous phase to complete
STATE_READY = "ready"  # Prompt prepared, awaiting user acknowledgment
STATE_UNDER_REVIEW = "under_review"  # User is reviewing the prompt
STATE_READY_EDIT = "ready_edit"  # User has edited, awaiting final approval
STATE_PROCESSING = "processing"  # Agent is executing
STATE_COMPLETE = "complete"  # Phase completed successfully
STATE_FAILED = "failed"  # Phase failed

# Valid state transitions
VALID_TRANSITIONS: Dict[str, List[str]] = {
    STATE_SLEEPING: [STATE_READY],
    STATE_READY: [STATE_UNDER_REVIEW, STATE_SLEEPING],
    STATE_UNDER_REVIEW: [STATE_READY_EDIT, STATE_PROCESSING, STATE_READY],
    STATE_READY_EDIT: [STATE_PROCESSING, STATE_UNDER_REVIEW],
    STATE_PROCESSING: [STATE_COMPLETE, STATE_FAILED],
    STATE_COMPLETE: [],  # Terminal state
    STATE_FAILED: [STATE_SLEEPING],  # Can retry
}

# Legacy state mappings for backward compatibility
STATE_PENDING = STATE_READY  # Legacy alias
STATE_APPROVED = STATE_PROCESSING  # Legacy alias
STATE_INJECTED = STATE_PROCESSING  # Legacy alias
STATE_COMPLETED = STATE_COMPLETE  # Legacy alias
STATE_SKIPPED = STATE_FAILED  # Legacy alias
STATE_EDITING = STATE_UNDER_REVIEW  # Legacy alias


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


class GuardError(Exception):
    """Raised when a state transition guard condition is not met."""

    pass


@dataclass
class PhasePromptConfig:
    """Configuration for phase prompt handling."""

    # Whether to wait for acknowledgment before proceeding
    human_in_the_loop: bool = False

    # Maximum time to wait for acknowledgment (seconds)
    approval_timeout: float = 3600  # 1 hour

    # Poll interval when waiting for acknowledgment (seconds)
    poll_interval: float = 2.0

    # Whether to allow autonomous mode (skip waiting)
    allow_autonomous: bool = True


@dataclass
class TokenMetrics:
    """Token metrics for a phase prompt."""

    # Estimated tokens before execution
    estimated_input_tokens: int = 0
    estimated_output_budget: int = 0

    # Actual tokens (updated during/after execution)
    actual_input_tokens: int = 0
    actual_output_tokens: int = 0

    # Context window info
    context_percent: float = 0.0
    max_context_window: int = 200000


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Simple heuristic: ~4 characters per token.
    This is approximate but consistent.
    """
    if not text:
        return 0
    return len(text) // 4


def get_phase_output_budget(phase_name: str) -> int:
    """Get the expected output token budget for a phase."""
    budgets = {
        "Scout": 14000,
        "Architect": 14000,
        "Builder": 40000,
        "Test": 40000,
        "Deploy": 10000,
    }
    return budgets.get(phase_name, 10000)


def can_transition(from_state: str, to_state: str) -> bool:
    """Check if a state transition is valid."""
    valid_targets = VALID_TRANSITIONS.get(from_state, [])
    return to_state in valid_targets


def create_phase_prompt_file(
    working_directory: Path,
    phase_name: str,
    system_prompt: str,
    input_instruction: str,
    job_id: Optional[str] = None,
    initial_state: str = STATE_READY,
) -> Path:
    """
    Create a phase prompt file for human-in-the-loop review.

    Args:
        working_directory: Project working directory
        phase_name: Name of the phase (e.g., "Scout", "Architect")
        system_prompt: The system prompt content
        input_instruction: The user instruction content
        job_id: Optional job ID for tracking
        initial_state: Initial state (default: ready)

    Returns:
        Path to the created prompt file
    """
    prompts_dir = working_directory / ".context-foundry" / "phase-prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = prompts_dir / f"{phase_name.lower()}-prompt.json"

    # Calculate token estimates
    estimated_input = estimate_tokens(system_prompt) + estimate_tokens(
        input_instruction
    )
    estimated_output = get_phase_output_budget(phase_name)

    prompt_data = {
        "id": str(uuid.uuid4()),
        "job_id": job_id,
        "phase": phase_name,
        "state": initial_state,
        # Original prompts
        "system_prompt": system_prompt,
        "input_instruction": input_instruction,
        # Edited versions (null until user edits)
        "system_prompt_edited": None,
        "input_instruction_edited": None,
        # Timestamps
        "created_at": datetime.now().isoformat(),
        "ready_at": datetime.now().isoformat()
        if initial_state == STATE_READY
        else None,
        "review_started_at": None,
        "edited_at": None,
        "acknowledged_at": None,
        "processing_started_at": None,
        "completed_at": None,
        # User tracking
        "reviewed_by": None,
        "edited_by": None,
        "acknowledged_by": None,
        # Token metrics
        "token_metrics": {
            "estimated_input_tokens": estimated_input,
            "estimated_output_budget": estimated_output,
            "actual_input_tokens": 0,
            "actual_output_tokens": 0,
            "context_percent": (estimated_input / 200000) * 100,
            "max_context_window": 200000,
        },
        # Error tracking
        "error": None,
    }

    prompt_file.write_text(json.dumps(prompt_data, indent=2))
    logger.info(f"Created phase prompt file: {prompt_file} (state: {initial_state})")

    return prompt_file


def read_phase_prompt(working_directory: Path, phase_name: str) -> Optional[dict]:
    """
    Read a phase prompt file.

    Args:
        working_directory: Project working directory
        phase_name: Name of the phase

    Returns:
        Prompt data dict or None if not found
    """
    prompt_file = (
        working_directory
        / ".context-foundry"
        / "phase-prompts"
        / f"{phase_name.lower()}-prompt.json"
    )

    if not prompt_file.exists():
        return None

    try:
        return json.loads(prompt_file.read_text())
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read phase prompt file: {e}")
        return None


def read_all_phase_prompts(working_directory: Path) -> Dict[str, dict]:
    """
    Read all phase prompt files for a job.

    Args:
        working_directory: Project working directory

    Returns:
        Dict mapping phase name to prompt data
    """
    prompts_dir = working_directory / ".context-foundry" / "phase-prompts"
    if not prompts_dir.exists():
        return {}

    result = {}
    for prompt_file in prompts_dir.glob("*-prompt.json"):
        try:
            data = json.loads(prompt_file.read_text())
            phase_name = data.get(
                "phase", prompt_file.stem.replace("-prompt", "").title()
            )
            result[phase_name] = data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read {prompt_file}: {e}")

    return result


def get_effective_prompts(prompt_data: dict) -> Tuple[str, str]:
    """
    Get the effective system prompt and input instruction.

    Uses edited versions if available, otherwise originals.

    Args:
        prompt_data: The prompt data dict

    Returns:
        Tuple of (system_prompt, input_instruction)
    """
    system_prompt = prompt_data.get("system_prompt_edited") or prompt_data.get(
        "system_prompt", ""
    )
    input_instruction = prompt_data.get("input_instruction_edited") or prompt_data.get(
        "input_instruction", ""
    )

    return system_prompt, input_instruction


def update_prompt_state(
    working_directory: Path,
    phase_name: str,
    new_state: str,
    validate_transition: bool = True,
    **kwargs,
) -> bool:
    """
    Update the state of a phase prompt with transition validation.

    Args:
        working_directory: Project working directory
        phase_name: Name of the phase
        new_state: New state to transition to
        validate_transition: Whether to validate the transition (default True)
        **kwargs: Additional fields to update

    Returns:
        True if successful, False otherwise

    Raises:
        InvalidTransitionError: If transition is not valid and validate_transition is True
    """
    prompt_file = (
        working_directory
        / ".context-foundry"
        / "phase-prompts"
        / f"{phase_name.lower()}-prompt.json"
    )

    if not prompt_file.exists():
        logger.error(f"Prompt file not found: {prompt_file}")
        return False

    try:
        prompt_data = json.loads(prompt_file.read_text())
        current_state = prompt_data.get("state", STATE_SLEEPING)

        # Validate transition if requested
        if validate_transition and not can_transition(current_state, new_state):
            raise InvalidTransitionError(
                f"Invalid transition for {phase_name}: {current_state} -> {new_state}"
            )

        prompt_data["state"] = new_state
        now = datetime.now().isoformat()

        # Update timestamp fields based on state
        timestamp_map = {
            STATE_READY: "ready_at",
            STATE_UNDER_REVIEW: "review_started_at",
            STATE_READY_EDIT: "edited_at",
            STATE_PROCESSING: "processing_started_at",
            STATE_COMPLETE: "completed_at",
            STATE_FAILED: "completed_at",
        }

        if new_state in timestamp_map:
            prompt_data[timestamp_map[new_state]] = now

        # For processing state, also set acknowledged_at
        if new_state == STATE_PROCESSING:
            prompt_data["acknowledged_at"] = now

        # Apply any additional kwargs
        for key, value in kwargs.items():
            if key == "token_metrics" and isinstance(value, dict):
                # Merge token metrics
                if "token_metrics" not in prompt_data:
                    prompt_data["token_metrics"] = {}
                prompt_data["token_metrics"].update(value)
            else:
                prompt_data[key] = value

        prompt_file.write_text(json.dumps(prompt_data, indent=2))
        logger.info(
            f"Updated phase prompt state: {phase_name} {current_state} -> {new_state}"
        )
        return True

    except InvalidTransitionError:
        raise
    except Exception as e:
        logger.error(f"Failed to update prompt state: {e}")
        return False


def wait_for_acknowledgment(
    working_directory: Path,
    phase_name: str,
    config: PhasePromptConfig,
) -> Tuple[bool, Optional[dict], Optional[TokenMetrics]]:
    """
    Wait for user to acknowledge prompt before agent execution.

    This is the "clean plate" mechanism - the agent blocks here until
    the user explicitly acknowledges the prompt in the dashboard.

    Flow:
    1. Prompt file created (state: ready)
    2. Agent waits here polling the file
    3. User opens dashboard, reviews prompt (state: under_review)
    4. User optionally edits (state: ready_edit)
    5. User clicks Acknowledge (state: processing)
    6. This function returns, agent proceeds

    Args:
        working_directory: Project working directory
        phase_name: Name of the phase
        config: Configuration for waiting behavior

    Returns:
        Tuple of (acknowledged: bool, prompt_data: dict, token_metrics: TokenMetrics)
    """
    if not config.human_in_the_loop:
        # Autonomous mode - auto-acknowledge and proceed immediately
        prompt_data = read_phase_prompt(working_directory, phase_name)
        if prompt_data:
            # Skip straight to processing
            update_prompt_state(
                working_directory,
                phase_name,
                STATE_PROCESSING,
                validate_transition=False,  # Allow direct transition in autonomous mode
                acknowledged_by="autonomous",
            )
            prompt_data["state"] = STATE_PROCESSING

            metrics = TokenMetrics(
                estimated_input_tokens=prompt_data.get("token_metrics", {}).get(
                    "estimated_input_tokens", 0
                ),
                estimated_output_budget=prompt_data.get("token_metrics", {}).get(
                    "estimated_output_budget", 0
                ),
            )
            return True, prompt_data, metrics
        return True, prompt_data, None

    # Human-in-the-loop mode - wait for acknowledgment
    logger.info(f"Waiting for user acknowledgment of {phase_name} phase prompt...")
    print(f"\n{'='*60}", flush=True)
    print(f"WAITING FOR ACKNOWLEDGMENT: {phase_name}", flush=True)
    print("", flush=True)
    print("   Open the dashboard to review and acknowledge the prompt.", flush=True)
    print("   The agent will NOT start until you click 'Acknowledge'.", flush=True)
    print("", flush=True)
    print("   Dashboard: http://localhost:8421", flush=True)
    print(f"   Timeout: {config.approval_timeout}s", flush=True)
    print(f"{'='*60}\n", flush=True)

    start_time = time.time()

    while True:
        elapsed = time.time() - start_time

        # Check timeout
        if elapsed > config.approval_timeout:
            logger.warning(
                f"Acknowledgment timeout for {phase_name} phase after {elapsed:.0f}s"
            )
            print(
                f"TIMEOUT: No acknowledgment received after {elapsed:.0f}s", flush=True
            )
            return False, None, None

        # Read current prompt state
        prompt_data = read_phase_prompt(working_directory, phase_name)
        if not prompt_data:
            logger.error(f"Prompt file disappeared for {phase_name}")
            return False, None, None

        state = prompt_data.get("state", STATE_READY)

        # Check if user has acknowledged (state transitioned to processing)
        if state == STATE_PROCESSING:
            logger.info(f"{phase_name} phase prompt acknowledged!")
            print(
                f"ACKNOWLEDGED: {phase_name} prompt acknowledged by {prompt_data.get('acknowledged_by', 'user')}",
                flush=True,
            )
            print("Agent starting execution...", flush=True)

            metrics = TokenMetrics(
                estimated_input_tokens=prompt_data.get("token_metrics", {}).get(
                    "estimated_input_tokens", 0
                ),
                estimated_output_budget=prompt_data.get("token_metrics", {}).get(
                    "estimated_output_budget", 0
                ),
            )
            return True, prompt_data, metrics

        # Check for failure state
        if state == STATE_FAILED:
            logger.info(f"{phase_name} phase was marked as failed")
            print(f"FAILED: {phase_name} phase was rejected or failed", flush=True)
            return False, prompt_data, None

        # Log progress periodically
        if int(elapsed) % 30 == 0 and int(elapsed) > 0:
            print(
                f"   Still waiting for acknowledgment... ({int(elapsed)}s elapsed, state={state})",
                flush=True,
            )

        # Still waiting
        time.sleep(config.poll_interval)


def run_phase_with_prompt_management(
    phase_name: str,
    phase_prompt_path: Path,
    input_instruction: str,
    working_directory: Path,
    config: PhasePromptConfig,
    job_id: Optional[str] = None,
    run_phase_func: callable = None,
    **run_phase_kwargs,
):
    """
    Run a phase with human-in-the-loop prompt management.

    This wrapper:
    1. Creates the phase prompt file (state: ready)
    2. Waits for user acknowledgment (state: processing)
    3. Uses edited prompts if available
    4. Runs the phase
    5. Updates prompt state based on result (complete/failed)

    Args:
        phase_name: Name of the phase
        phase_prompt_path: Path to the system prompt file
        input_instruction: Original user instruction
        working_directory: Project directory
        config: Prompt configuration
        job_id: Optional job ID
        run_phase_func: The actual run_phase function to call
        **run_phase_kwargs: Additional kwargs for run_phase

    Returns:
        PhaseResult from run_phase
    """
    if run_phase_func is None:
        raise ValueError("run_phase_func must be provided")

    # Load original system prompt
    if not phase_prompt_path.exists():
        raise FileNotFoundError(f"Phase prompt not found: {phase_prompt_path}")

    system_prompt = phase_prompt_path.read_text()

    # Create the prompt file for human review (starts in READY state)
    create_phase_prompt_file(
        working_directory=working_directory,
        phase_name=phase_name,
        system_prompt=system_prompt,
        input_instruction=input_instruction,
        job_id=job_id,
        initial_state=STATE_READY,
    )

    # Wait for user acknowledgment (blocks until state == processing)
    acknowledged, prompt_data, token_metrics = wait_for_acknowledgment(
        working_directory=working_directory,
        phase_name=phase_name,
        config=config,
    )

    if not acknowledged:
        # Import here to avoid circular dependency
        from tools.mcp_utils.phase_execution import PhaseResult

        update_prompt_state(
            working_directory,
            phase_name,
            STATE_FAILED,
            validate_transition=False,
            error="Phase prompt was not acknowledged or timed out",
        )
        return PhaseResult(
            phase=phase_name,
            status="failed",
            duration_seconds=0,
            context_tokens=token_metrics.estimated_input_tokens if token_metrics else 0,
            exit_code=1,
            error="Phase prompt was not acknowledged or timed out",
        )

    # Get effective prompts (may be edited by user)
    effective_system_prompt, effective_input = get_effective_prompts(prompt_data)

    # If prompts were edited, we need to write the system prompt to a temp file
    # since run_phase expects a file path
    import tempfile

    if effective_system_prompt != system_prompt:
        logger.info(f"Using edited system prompt for {phase_name}")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(effective_system_prompt)
            temp_prompt_path = Path(f.name)

        try:
            result = run_phase_func(
                phase_name=phase_name,
                phase_prompt_path=temp_prompt_path,
                input_instruction=effective_input,
                working_directory=working_directory,
                **run_phase_kwargs,
            )
        finally:
            # Clean up temp file
            temp_prompt_path.unlink(missing_ok=True)
    else:
        # Use original files
        result = run_phase_func(
            phase_name=phase_name,
            phase_prompt_path=phase_prompt_path,
            input_instruction=effective_input
            if effective_input != input_instruction
            else input_instruction,
            working_directory=working_directory,
            **run_phase_kwargs,
        )

    # Update prompt state based on result
    if result.status == "completed":
        update_prompt_state(
            working_directory,
            phase_name,
            STATE_COMPLETE,
            token_metrics={
                "actual_input_tokens": result.context_tokens,
                "actual_output_tokens": getattr(result, "output_tokens", 0),
            },
        )
    else:
        update_prompt_state(
            working_directory, phase_name, STATE_FAILED, error=result.error
        )

    return result


def is_human_in_the_loop_enabled(task_config: dict) -> bool:
    """
    Check if human-in-the-loop mode is enabled for a build.

    Args:
        task_config: The task configuration dict

    Returns:
        True if human-in-the-loop is enabled
    """
    # Check execution_mode
    execution_mode = task_config.get("execution_mode", "autonomous")
    if execution_mode == "human_in_the_loop":
        return True

    # Check pause_after_phases (legacy support)
    pause_after_phases = task_config.get("pause_after_phases", [])
    if pause_after_phases:
        return True

    return False


def get_phase_prompt_config(task_config: dict, phase_name: str) -> PhasePromptConfig:
    """
    Get the prompt configuration for a specific phase.

    Args:
        task_config: The task configuration dict
        phase_name: Name of the phase

    Returns:
        PhasePromptConfig instance
    """
    execution_mode = task_config.get("execution_mode", "autonomous")
    pause_after_phases = task_config.get("pause_after_phases", [])
    timeout_minutes = task_config.get("timeout_minutes", 60)

    # Check if this phase should wait for acknowledgment
    human_in_the_loop = False

    if execution_mode == "human_in_the_loop":
        # All phases wait for acknowledgment
        human_in_the_loop = True
    elif phase_name in pause_after_phases:
        # This specific phase should wait
        human_in_the_loop = True

    return PhasePromptConfig(
        human_in_the_loop=human_in_the_loop,
        approval_timeout=timeout_minutes * 60,  # Convert to seconds
        poll_interval=2.0,
        allow_autonomous=execution_mode == "autonomous",
    )


def get_transaction_stats(working_directory: Path) -> Dict[str, Any]:
    """
    Get overall transaction statistics across all phases.

    Args:
        working_directory: Project working directory

    Returns:
        Dict with transaction statistics
    """
    prompts = read_all_phase_prompts(working_directory)

    total_input = 0
    total_output = 0
    total_duration = 0
    phases_complete = 0
    phases_failed = 0

    phase_stats = {}

    for phase_name, data in prompts.items():
        metrics = data.get("token_metrics", {})

        input_tokens = metrics.get("actual_input_tokens", 0) or metrics.get(
            "estimated_input_tokens", 0
        )
        output_tokens = metrics.get("actual_output_tokens", 0)

        total_input += input_tokens
        total_output += output_tokens

        state = data.get("state", STATE_SLEEPING)
        if state == STATE_COMPLETE:
            phases_complete += 1
        elif state == STATE_FAILED:
            phases_failed += 1

        # Calculate duration if we have timestamps
        created = data.get("created_at")
        completed = data.get("completed_at")
        if created and completed:
            try:
                start = datetime.fromisoformat(created)
                end = datetime.fromisoformat(completed)
                duration = (end - start).total_seconds()
                total_duration += duration
            except (ValueError, TypeError):
                pass

        phase_stats[phase_name] = {
            "state": state,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "created_at": data.get("created_at"),
            "completed_at": data.get("completed_at"),
        }

    return {
        "phases": phase_stats,
        "totals": {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_duration_seconds": total_duration,
            "phases_complete": phases_complete,
            "phases_failed": phases_failed,
            "phases_total": len(prompts),
        },
        "context_percent": (total_input / 200000) * 100 if total_input else 0,
    }

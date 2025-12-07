"""
Context Handoff Management

Handles persistence of agent context ("Context Crystallization") across phases.
"""

from pathlib import Path
from typing import Optional

HANDOFF_DIR_NAME = "memory"
HANDOFF_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "handoff.txt"


def get_memory_dir(working_dir: Path) -> Path:
    """Get the memory directory for the current project."""
    return working_dir / ".context-foundry" / HANDOFF_DIR_NAME


def get_latest_handoff(working_dir: Path) -> Optional[str]:
    """
    Read the content of the most recent handoff file.

    Args:
        working_dir: Project root directory

    Returns:
        Content of the latest handoff file, or None if no handoff exists.
    """
    memory_dir = get_memory_dir(working_dir)
    if not memory_dir.exists():
        return None

    # Find all handoff files matching pattern handoff_*.md
    handoff_files = list(memory_dir.glob("handoff_*.md"))

    if not handoff_files:
        return None

    # Sort by filename (timestamps make this chronological)
    # handoff_20251207_120000.md
    latest_file = sorted(handoff_files)[-1]

    try:
        return latest_file.read_text()
    except Exception:
        return None


def get_handoff_instructions() -> str:
    """
    Get the instructions for creating a context handoff.

    Returns:
        The prompt text instructing the agent how to crystallize context.
    """
    if not HANDOFF_PROMPT_PATH.exists():
        return "Error: Context handoff prompt not found."

    return HANDOFF_PROMPT_PATH.read_text()


def format_context_for_prompt(working_dir: Path) -> str:
    """
    Format previous context to be injected into the system prompt.
    """
    latest_handoff = get_latest_handoff(working_dir)
    if not latest_handoff:
        return ""

    return f"""
═══════════════════════════════════════════════════════════
📜 PREVIOUS SESSION CONTEXT (RESTORE POINT)
═══════════════════════════════════════════════════════════
The following is the state left by the previous agent.
USE THIS TO RESUME WORK IMMEDIATELY.

{latest_handoff}
═══════════════════════════════════════════════════════════
"""

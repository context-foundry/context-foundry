"""
Phase Prompt Loader

Loads phase-specific instructions modularly from separate files.
This reduces the base orchestrator prompt size while preserving all functionality.
"""

from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from extensions.flowise import extensions_loader

    FLOWISE_AVAILABLE = True
except ImportError:
    FLOWISE_AVAILABLE = False


# Phase file mapping
PHASE_FILES = {
    "0": "phase_0_codebase_analysis.md",
    "1": "phase_1_scout.md",
    "2": "phase_2_architect.md",
    "2.5": "phase_2_5_parallel_build.md",
    "3.5": "phase_3_5_integration_precheck.md",
    "4": "phase_4_test.md",
    "4.5": "phase_4_5_screenshot.md",
    "5": "phase_5_documentation.md",
    "6": "phase_6_deployment.md",
    "7": "phase_7_feedback.md",
    "7.5": "phase_7_5_github.md",
}

# Phase name mapping for Flowise extensions
PHASE_NAME_MAP = {
    "0": "codebase_analysis",
    "1": "scout",
    "2": "architect",
    "2.5": "parallel_build",
    "3.5": "integration_precheck",
    "4": "test",
    "4.5": "screenshot",
    "5": "documentation",
    "6": "deployment",
    "7": "feedback",
    "7.5": "github",
}


def get_phase_prompt(phase: str, flowise_mode: bool = False) -> str:
    """
    Load phase-specific instructions from modular files.

    Args:
        phase: Phase identifier (e.g., "1", "2.5", "7.5")
        flowise_mode: Whether to include Flowise-specific enhancements

    Returns:
        Complete phase instructions including base + Flowise enhancements if applicable

    Example:
        >>> prompt = get_phase_prompt("1", flowise_mode=True)
        >>> print(prompt[:50])
        PHASE 1: SCOUT (Research & Context Gathering...
    """
    prompts_dir = Path(__file__).parent

    # Get base phase file
    phase_file = PHASE_FILES.get(phase)
    if not phase_file:
        raise ValueError(f"Unknown phase: {phase}")

    phase_path = prompts_dir / phase_file
    if not phase_path.exists():
        raise FileNotFoundError(f"Phase file not found: {phase_path}")

    # Read base phase instructions
    with open(phase_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    # Add Flowise enhancements if applicable
    if flowise_mode and FLOWISE_AVAILABLE:
        phase_name = PHASE_NAME_MAP.get(phase, "")
        flowise_enhancement = extensions_loader.get_extension_prompt(
            "flowise", phase_name
        )

        if flowise_enhancement:
            # Append Flowise-specific instructions
            base_prompt += f"\n\n{'═' * 63}\n"
            base_prompt += f"FLOWISE EXTENSION - {phase_name.upper()} ENHANCEMENTS\n"
            base_prompt += f"{'═' * 63}\n\n"
            base_prompt += flowise_enhancement

    return base_prompt


def get_all_phases(flowise_mode: bool = False) -> str:
    """
    Load all phase instructions in sequence.

    Args:
        flowise_mode: Whether to include Flowise-specific enhancements

    Returns:
        All phase instructions concatenated
    """
    all_prompts = []

    for phase in ["0", "1", "2", "2.5", "3.5", "4", "4.5", "5", "6", "7", "7.5"]:
        phase_prompt = get_phase_prompt(phase, flowise_mode=flowise_mode)
        all_prompts.append(phase_prompt)
        all_prompts.append("\n")  # Add spacing between phases

    return "\n".join(all_prompts)


def list_available_phases() -> list:
    """
    List all available phases.

    Returns:
        List of phase identifiers
    """
    return list(PHASE_FILES.keys())


if __name__ == "__main__":
    # Test the loader
    print("Phase Prompt Loader - Test\n")
    print(f"Flowise available: {FLOWISE_AVAILABLE}")
    print(f"Available phases: {list_available_phases()}\n")

    # Test loading a single phase
    try:
        scout_prompt = get_phase_prompt("1", flowise_mode=False)
        print(f"✅ Phase 1 (Scout) loaded: {len(scout_prompt)} chars")

        # Test with Flowise mode
        if FLOWISE_AVAILABLE:
            scout_flowise = get_phase_prompt("1", flowise_mode=True)
            print(f"✅ Phase 1 with Flowise: {len(scout_flowise)} chars")
            print(f"   Enhancement added: {len(scout_flowise) > len(scout_prompt)}")
    except Exception as e:
        print(f"❌ Error loading phase: {e}")

    # Test loading all phases
    try:
        all_phases = get_all_phases(flowise_mode=False)
        print(f"\n✅ All phases loaded: {len(all_phases)} chars")
        print(f"   Approximate tokens: {len(all_phases) // 4}")
    except Exception as e:
        print(f"❌ Error loading all phases: {e}")

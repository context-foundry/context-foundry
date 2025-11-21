"""
Roblox Extension Loader

Provides safe loading interface for the Roblox extension.
Handles ImportErrors gracefully to prevent extension from crashing Context Foundry.

Functions:
- load_extension_detectors() - Load detector modules
- load_extension_patterns(pattern_name) - Load pattern JSON files
- get_extension_prompt(phase) - Get phase-specific prompts
- extension_exists() - Check if extension is available
"""

from pathlib import Path
from typing import Dict, Optional, Any
import json


def load_extension_detectors() -> Dict[str, Any]:
    """
    Load detector modules for Roblox extension.

    Returns:
        Dict mapping extension name to detector module
        Example: {"roblox": <detector module>}
        Returns {} if import fails
    """
    try:
        from . import detector

        return {"roblox": detector}
    except ImportError as e:
        print(f"Warning: Failed to load Roblox detector: {e}")
        return {}


def load_extension_patterns(pattern_name: str = "roblox-expertise") -> Optional[Dict]:
    """
    Load pattern JSON files from the patterns directory.

    Args:
        pattern_name: Name of pattern file (without .json extension)
                     Default: "roblox-expertise"

    Returns:
        Dict containing parsed JSON pattern data
        None if file doesn't exist or parsing fails

    Example:
        patterns = load_extension_patterns("roblox-expertise")
        obby_pattern = patterns["patterns"][0]
    """
    try:
        patterns_dir = Path(__file__).parent / "patterns"
        pattern_file = patterns_dir / f"{pattern_name}.json"

        if not pattern_file.exists():
            print(f"Warning: Pattern file not found: {pattern_file}")
            return None

        with open(pattern_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse pattern JSON {pattern_name}: {e}")
        return None
    except Exception as e:
        print(f"Error: Failed to load pattern {pattern_name}: {e}")
        return None


def get_extension_prompt(phase: str) -> Optional[str]:
    """
    Get phase-specific prompt content.

    Args:
        phase: Phase name ("scout", "architect", "builder", "tester", "docs")

    Returns:
        String containing prompt content
        None if prompt file doesn't exist

    Example:
        scout_prompt = get_extension_prompt("scout")
    """
    phase_to_file = {
        "scout": "SCOUT-PROJECT-ASSESSMENT.md",
        "architect": "ARCHITECT-GAME-SYSTEMS.md",
        "builder": "BUILDER-LUAU-BEST-PRACTICES.md",
        "tester": "TESTER-TEST-STRATEGY.md",
        "docs": "DOCS-README-GUIDE.md",
    }

    if phase.lower() not in phase_to_file:
        print(
            f"Warning: Unknown phase '{phase}'. Valid phases: {list(phase_to_file.keys())}"
        )
        return None

    try:
        prompts_dir = Path(__file__).parent / "prompts"
        prompt_file = prompts_dir / phase_to_file[phase.lower()]

        if not prompt_file.exists():
            print(f"Warning: Prompt file not found: {prompt_file}")
            return None

        return prompt_file.read_text(encoding="utf-8")

    except Exception as e:
        print(f"Error: Failed to load prompt for phase '{phase}': {e}")
        return None


def extension_exists(extension_name: str = "roblox") -> bool:
    """
    Check if extension is available.

    Args:
        extension_name: Name of extension to check (default: "roblox")

    Returns:
        True if extension directory exists and has required files
        False otherwise
    """
    ext_dir = Path(__file__).parent

    # Check directory exists
    if not ext_dir.exists():
        return False

    # Check required files exist
    required_files = [
        "detector.py",
        "extensions_loader.py",  # This file
    ]

    for file in required_files:
        if not (ext_dir / file).exists():
            return False

    return True


def get_extension_info() -> Dict[str, Any]:
    """
    Get extension metadata and info.

    Returns:
        Dict containing extension version, capabilities, etc.
    """
    return {
        "name": "roblox",
        "version": "1.0.0",
        "description": "Roblox game development extension with Rojo workflow support",
        "supported_project_types": ["roblox-game", "roblox-plugin", "roblox-library"],
        "supported_subtypes": ["rojo", "placefile"],
        "capabilities": [
            "project_detection",
            "pattern_library",
            "code_templates",
            "static_analysis",
            "test_generation",
        ],
        "required_tools": {
            "rojo": {
                "version": ">=7.0.0",
                "required": True,
                "install_url": "https://rojo.space",
            },
            "stylua": {
                "version": ">=0.20.0",
                "required": False,
                "install_command": "cargo install stylua",
            },
            "selene": {
                "version": ">=0.27.0",
                "required": False,
                "install_command": "cargo install selene",
            },
        },
        "patterns_available": _list_available_patterns(),
        "prompts_available": _list_available_prompts(),
    }


def _list_available_patterns() -> list:
    """List all available pattern files."""
    try:
        patterns_dir = Path(__file__).parent / "patterns"
        if not patterns_dir.exists():
            return []

        pattern_files = list(patterns_dir.glob("*.json"))
        return [f.stem for f in pattern_files]
    except Exception:
        return []


def _list_available_prompts() -> list:
    """List all available prompt files."""
    try:
        prompts_dir = Path(__file__).parent / "prompts"
        if not prompts_dir.exists():
            return []

        prompt_files = list(prompts_dir.glob("*.md"))
        return [f.stem for f in prompt_files]
    except Exception:
        return []


def load_template_project(template_name: str = "basic-obby") -> Optional[Path]:
    """
    Get path to template project.

    Args:
        template_name: Name of template (default: "basic-obby")

    Returns:
        Path to template directory
        None if template doesn't exist
    """
    templates_dir = Path(__file__).parent / "templates"
    template_path = templates_dir / template_name

    if not template_path.exists():
        print(f"Warning: Template not found: {template_path}")
        return None

    return template_path


def get_code_template(template_name: str) -> Optional[str]:
    """
    Load a code template by name.

    Args:
        template_name: Name of template file (e.g., "CheckpointManager.lua")

    Returns:
        String containing template code
        None if template doesn't exist

    Example:
        checkpoint_code = get_code_template("CheckpointManager.lua")
    """
    # Check in basic-obby template first
    template_path = Path(__file__).parent / "templates" / "basic-obby" / "src"

    # Search for the template file
    matches = list(template_path.glob(f"**/{template_name}"))

    if not matches:
        print(f"Warning: Code template not found: {template_name}")
        return None

    try:
        return matches[0].read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error: Failed to load code template {template_name}: {e}")
        return None


# =============================================================================
# TESTING & DIAGNOSTICS
# =============================================================================


def run_diagnostics() -> Dict[str, Any]:
    """
    Run extension diagnostics.

    Returns:
        Dict with diagnostic results
    """
    diagnostics = {
        "extension_exists": extension_exists(),
        "detector_loadable": False,
        "patterns_loadable": False,
        "prompts_loadable": 0,
        "templates_available": 0,
        "errors": [],
    }

    # Test detector loading
    try:
        detectors = load_extension_detectors()
        diagnostics["detector_loadable"] = "roblox" in detectors
    except Exception as e:
        diagnostics["errors"].append(f"Detector load failed: {e}")

    # Test pattern loading
    try:
        patterns = load_extension_patterns()
        diagnostics["patterns_loadable"] = patterns is not None
    except Exception as e:
        diagnostics["errors"].append(f"Pattern load failed: {e}")

    # Count prompts
    for phase in ["scout", "architect", "builder", "tester", "docs"]:
        try:
            prompt = get_extension_prompt(phase)
            if prompt:
                diagnostics["prompts_loadable"] += 1
        except Exception:
            pass

    # Count templates
    templates_dir = Path(__file__).parent / "templates"
    if templates_dir.exists():
        diagnostics["templates_available"] = len(list(templates_dir.iterdir()))

    return diagnostics


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("Roblox Extension Loader - Diagnostics\n")

    # Run diagnostics
    diag = run_diagnostics()

    print("Extension Status:")
    print(f"  Exists: {diag['extension_exists']}")
    print(f"  Detector Loadable: {diag['detector_loadable']}")
    print(f"  Patterns Loadable: {diag['patterns_loadable']}")
    print(f"  Prompts Available: {diag['prompts_loadable']}/5")
    print(f"  Templates Available: {diag['templates_available']}")

    if diag["errors"]:
        print("\nErrors:")
        for error in diag["errors"]:
            print(f"  - {error}")

    # Show extension info
    print("\nExtension Info:")
    info = get_extension_info()
    print(f"  Name: {info['name']}")
    print(f"  Version: {info['version']}")
    print(f"  Description: {info['description']}")
    print(f"  Supported Types: {', '.join(info['supported_project_types'])}")
    print(f"  Patterns: {', '.join(info['patterns_available'])}")
    print(f"  Prompts: {', '.join(info['prompts_available'])}")

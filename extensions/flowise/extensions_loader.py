"""
Extensions Loader

Safely loads extension modules with graceful fallback when extensions are not present.
"""

import importlib.util
import json
from pathlib import Path
from typing import Any, Optional, Dict


def load_extension_detectors() -> Optional[Dict[str, Any]]:
    """
    Load custom project detectors from extensions/.

    Returns:
        Dictionary of extension detectors, or None if extensions directory doesn't exist.

    Example:
        >>> detectors = load_extension_detectors()
        >>> if detectors and 'flowise' in detectors:
        ...     result = detectors['flowise'].detect_flowise_flow(path)
    """
    try:
        # Try to import detector module
        from . import detector

        return {
            'flowise': detector
        }
    except ImportError:
        # Extension not installed, return None gracefully
        return None


def load_extension_patterns(extension_name: str) -> Optional[Dict[str, Any]]:
    """
    Load patterns from specific extension.

    Args:
        extension_name: Name of the extension (e.g., "flowise")

    Returns:
        Dictionary of patterns, or None if extension doesn't exist.

    Example:
        >>> patterns = load_extension_patterns("flowise")
        >>> if patterns:
        ...     for pattern in patterns.get('patterns', []):
        ...         print(pattern['pattern_id'])
    """
    if extension_name != 'flowise':
        return None

    # Try to load patterns from the patterns directory
    patterns_dir = Path(__file__).parent / 'patterns'

    # Try both .example and regular files
    pattern_files = [
        patterns_dir / 'flowise-expertise.json',
        patterns_dir / 'flowise-expertise.json.example'
    ]

    for pattern_file in pattern_files:
        if pattern_file.exists():
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

    return None


def get_extension_prompt(extension_name: str, phase: str) -> Optional[str]:
    """
    Get phase-specific prompt enhancement.

    Args:
        extension_name: Name of the extension (e.g., "flowise")
        phase: Phase name (e.g., "scout", "architect")

    Returns:
        Prompt text, or None if prompt file doesn't exist.

    Example:
        >>> prompt = get_extension_prompt("flowise", "scout")
        >>> if prompt:
        ...     print("Using Flowise-enhanced Scout prompt")
    """
    if extension_name != 'flowise':
        return None

    prompts_dir = Path(__file__).parent / 'prompts'
    prompt_file = prompts_dir / f'{phase}-enhancement.txt'

    if not prompt_file.exists():
        return None

    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except IOError:
        return None


def extension_exists(extension_name: str) -> bool:
    """
    Check if an extension is available.

    Args:
        extension_name: Name of the extension to check

    Returns:
        True if extension exists and can be loaded, False otherwise.

    Example:
        >>> if extension_exists("flowise"):
        ...     print("Flowise extension is available")
    """
    if extension_name != 'flowise':
        return False

    # Check if we can load the detector module
    try:
        from . import detector
        return True
    except ImportError:
        return False


def get_available_extensions() -> list[str]:
    """
    Get list of available extensions.

    Returns:
        List of extension names.

    Example:
        >>> extensions = get_available_extensions()
        >>> print(f"Available: {', '.join(extensions)}")
    """
    available = []

    if extension_exists('flowise'):
        available.append('flowise')

    return available


def load_flow_templates() -> Optional[Dict[str, Any]]:
    """
    Load flow template catalog.

    Returns:
        Dictionary of categorized flow templates, or None if not available.

    Example:
        >>> templates = load_flow_templates()
        >>> if templates:
        ...     multi_agent_templates = templates.get('templates', {}).get('multi-agent', [])
    """
    patterns_dir = Path(__file__).parent / 'patterns'

    # Try both .example and regular files
    template_files = [
        patterns_dir / 'flow-templates.json',
        patterns_dir / 'flow-templates.json.example'
    ]

    for template_file in template_files:
        if template_file.exists():
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

    return None


if __name__ == "__main__":
    # Test the loader
    print("Testing Extensions Loader\n")

    print("Available extensions:", get_available_extensions())

    detectors = load_extension_detectors()
    print(f"Detectors loaded: {detectors is not None}")

    if detectors:
        print(f"Available detector modules: {list(detectors.keys())}")

    patterns = load_extension_patterns('flowise')
    print(f"Patterns loaded: {patterns is not None}")

    scout_prompt = get_extension_prompt('flowise', 'scout')
    print(f"Scout prompt loaded: {scout_prompt is not None}")

    architect_prompt = get_extension_prompt('flowise', 'architect')
    print(f"Architect prompt loaded: {architect_prompt is not None}")

    templates = load_flow_templates()
    print(f"Templates loaded: {templates is not None}")

"""
Workday Canvas Kit Extensions Loader

Safely loads Canvas Kit extension modules with graceful fallback.
"""

import json
from pathlib import Path
from typing import Any, Optional, Dict


def load_extension_detectors() -> Optional[Dict[str, Any]]:
    """
    Load Canvas Kit project detector.

    Returns:
        Dictionary of extension detectors, or None if extension not available.

    Example:
        >>> detectors = load_extension_detectors()
        >>> if detectors and 'workday-canvas' in detectors:
        ...     result = detectors['workday-canvas'].detect_canvas_kit_project(path)
    """
    try:
        # Try to import detector module
        from . import detector

        return {"workday-canvas": detector}
    except ImportError:
        # Extension not installed, return None gracefully
        return None


def load_extension_patterns(extension_name: str) -> Optional[Dict[str, Any]]:
    """
    Load patterns from Canvas Kit extension.

    Args:
        extension_name: Name of the extension (e.g., "workday-canvas")

    Returns:
        Dictionary of patterns, or None if extension doesn't exist.

    Example:
        >>> patterns = load_extension_patterns("workday-canvas")
        >>> if patterns:
        ...     for category in patterns.get('component_library', {}).get('categories', {}):
        ...         print(category)
    """
    if extension_name != "workday-canvas":
        return None

    # Try to load patterns from the patterns directory
    patterns_dir = Path(__file__).parent / "patterns"
    pattern_file = patterns_dir / "canvas-kit-expertise.json"

    if pattern_file.exists():
        try:
            with open(pattern_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    return None


def get_extension_prompt(extension_name: str, phase: str) -> Optional[str]:
    """
    Get phase-specific prompt enhancement for Canvas Kit projects.

    Args:
        extension_name: Name of the extension (e.g., "workday-canvas")
        phase: Phase name (e.g., "scout", "architect", "builder")

    Returns:
        Prompt enhancement text or None

    Example:
        >>> prompt = get_extension_prompt("workday-canvas", "builder")
        >>> if prompt:
        ...     print(prompt)
    """
    if extension_name != "workday-canvas":
        return None

    prompts = {
        "scout": """
**WORKDAY CANVAS KIT PROJECT DETECTED**

This project uses Workday Canvas Kit. Key considerations:

1. **Component Library**: Use Canvas Kit components instead of generic React components
2. **Design System**: Follow Workday's design principles for enterprise UI
3. **Dependencies**: Ensure @workday/canvas-kit-react and @emotion/react are installed
4. **TypeScript**: Canvas Kit works best with TypeScript for type safety
5. **Examples**: Check /extensions/workday-canvas/examples/ for reference implementations

Read patterns from: /extensions/workday-canvas/patterns/canvas-kit-expertise.json
""",
        "architect": """
**WORKDAY CANVAS KIT ARCHITECTURE**

When designing this application:

1. **Use Canvas Kit Components**: Reference component_library in canvas-kit-expertise.json
2. **Compound Components**: Canvas Kit uses compound component pattern (e.g., Modal.Card, Modal.Heading)
3. **Layout**: Use Box, Flex, Grid, Stack for layouts (not custom CSS)
4. **Forms**: Use FormField wrapper for all form inputs
5. **Theme**: Plan for CanvasProvider wrapper at app root
6. **Patterns**: Reference common_patterns in expertise file for workflows, tables, validation

For branching workflows: See /extensions/workday-canvas/components/workflows/README.md
For COI apps: See /extensions/workday-canvas/examples/conflict-of-interest/README.md
""",
        "builder": """
**WORKDAY CANVAS KIT IMPLEMENTATION**

Build using Canvas Kit components:

1. **Import from Canvas Kit packages**: @workday/canvas-kit-react/{component}
2. **Wrap app in CanvasProvider**: Required at root level
3. **Import CSS variables**: @workday/canvas-tokens-web/css/base/_variables.css
4. **Use compound components correctly**: Check v2.2_agent_structure in patterns
5. **Follow TypeScript types**: Import types from Canvas Kit packages
6. **Accessibility**: Canvas Kit components are WCAG 2.1 AA compliant by default

Component reference: /extensions/workday-canvas/patterns/canvas-kit-expertise.json
Workflow patterns: /extensions/workday-canvas/components/workflows/
Example apps: /extensions/workday-canvas/examples/
""",
        "test": """
**TESTING WORKDAY CANVAS KIT APPLICATIONS**

1. **Use @testing-library/react**: Canvas Kit components work well with RTL
2. **Test accessibility**: Use jest-axe for a11y testing
3. **Test keyboard navigation**: Ensure all interactions work with keyboard
4. **Mock Canvas Kit components**: May need to mock complex compound components
5. **Test form validation**: Verify FormField error states and validation logic

See test examples in extension files.
""",
    }

    return prompts.get(phase)

"""
Workday Canvas Kit Project Detector

Analyzes projects to detect use of Workday Canvas Kit component library.
"""

import json
from pathlib import Path
from typing import Any, Dict


def detect_canvas_kit_project(directory: Path) -> Dict[str, Any]:
    """
    Detect if a project uses Workday Canvas Kit.

    Args:
        directory: Path to project directory to analyze

    Returns:
        Dictionary with detection results:
        {
            "is_canvas_kit": bool,
            "canvas_kit_version": str or None,
            "has_typescript": bool,
            "has_preview_components": bool,
            "has_labs_components": bool,
            "component_count_estimate": int,
            "uses_emotion": bool,
            "confidence": "high" | "medium" | "low"
        }

    Example:
        >>> result = detect_canvas_kit_project(Path("/path/to/project"))
        >>> if result["is_canvas_kit"]:
        ...     print(f"Canvas Kit v{result['canvas_kit_version']} detected")
    """
    result = {
        "is_canvas_kit": False,
        "canvas_kit_version": None,
        "has_typescript": False,
        "has_preview_components": False,
        "has_labs_components": False,
        "component_count_estimate": 0,
        "uses_emotion": False,
        "confidence": "low",
    }

    # Check for package.json
    package_json = directory / "package.json"
    if not package_json.exists():
        return result

    try:
        with open(package_json, "r", encoding="utf-8") as f:
            package_data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, IOError):
        return result

    # Check dependencies and devDependencies for Canvas Kit packages
    dependencies = package_data.get("dependencies", {})
    dev_dependencies = package_data.get("devDependencies", {})
    all_deps = {**dependencies, **dev_dependencies}

    # Look for Canvas Kit packages
    canvas_kit_packages = {
        "@workday/canvas-kit-react": "main",
        "@workday/canvas-kit-preview-react": "preview",
        "@workday/canvas-kit-labs-react": "labs",
        "@workday/canvas-tokens-web": "tokens",
        "@workday/canvas-kit-styling": "styling",
    }

    found_packages = []
    for package_name, package_type in canvas_kit_packages.items():
        if package_name in all_deps:
            found_packages.append((package_name, package_type, all_deps[package_name]))

    # If we found Canvas Kit packages, it's a Canvas Kit project
    if found_packages:
        result["is_canvas_kit"] = True

        # Get version from main package
        for pkg_name, pkg_type, version in found_packages:
            if pkg_name == "@workday/canvas-kit-react":
                result["canvas_kit_version"] = version.lstrip("^~")
                result["confidence"] = "high"

        # Check for preview/labs components
        for pkg_name, pkg_type, _ in found_packages:
            if pkg_type == "preview":
                result["has_preview_components"] = True
            elif pkg_type == "labs":
                result["has_labs_components"] = True

        # Check for TypeScript
        if "typescript" in all_deps:
            result["has_typescript"] = True

        # Check for Emotion (required peer dependency)
        if "@emotion/react" in all_deps or "@emotion/styled" in all_deps:
            result["uses_emotion"] = True

        # Estimate component usage by checking import statements in src/
        src_dir = directory / "src"
        if src_dir.exists():
            result["component_count_estimate"] = _estimate_canvas_kit_usage(src_dir)

        # Higher confidence if we found TypeScript + Emotion + main package
        if (
            result["has_typescript"]
            and result["uses_emotion"]
            and result["canvas_kit_version"]
        ):
            result["confidence"] = "high"
        elif result["canvas_kit_version"]:
            result["confidence"] = "medium"

    return result


def _estimate_canvas_kit_usage(src_dir: Path) -> int:
    """
    Estimate Canvas Kit usage by counting import statements.

    Args:
        src_dir: Source directory to scan

    Returns:
        Estimated number of Canvas Kit component imports
    """
    import_count = 0
    canvas_kit_import_patterns = [
        "from '@workday/canvas-kit-react",
        'from "@workday/canvas-kit-react',
        "import { ",  # Generic React imports that might include Canvas Kit
    ]

    # Scan .ts, .tsx, .js, .jsx files
    for file_ext in ["*.ts", "*.tsx", "*.js", "*.jsx"]:
        for file_path in src_dir.rglob(file_ext):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    for pattern in canvas_kit_import_patterns[
                        :2
                    ]:  # Only Canvas Kit specific
                        import_count += content.count(pattern)
            except (UnicodeDecodeError, IOError):
                continue

    return import_count


def detect_canvas_kit_from_prompt(prompt: str) -> bool:
    """
    Detect if user prompt mentions Workday Canvas Kit.

    Args:
        prompt: User's project description or prompt

    Returns:
        True if Canvas Kit keywords detected, False otherwise

    Example:
        >>> detect_canvas_kit_from_prompt("Create a COI app using Canvas Kit")
        True
    """
    # Keywords from canvas-kit-expertise.json project_detection section
    keywords = [
        "workday",
        "canvas kit",
        "canvas-kit",
        "workday-style",
        "workday canvas",
        "@workday/canvas-kit",
        "workday design system",
    ]

    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in keywords)

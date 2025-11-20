"""Project detection utilities for Context Foundry MCP server."""

import subprocess
from pathlib import Path
from typing import Any, Dict


def detect_existing_codebase(directory: Path) -> Dict[str, Any]:
    """
    Detect if a directory contains an existing codebase and identify its characteristics.

    Args:
        directory: Path to the directory to analyze

    Returns:
        Dict with detection results:
        {
            "has_code": bool,
            "project_type": str or None,
            "languages": list[str],
            "has_git": bool,
            "git_clean": bool or None,
            "project_files": list[str],
            "confidence": str ("high", "medium", "low")
        }
    """
    result = {
        "has_code": False,
        "project_type": None,
        "languages": [],
        "has_git": False,
        "git_clean": None,
        "project_files": [],
        "confidence": "low",
    }

    if not directory.exists():
        return result

    # Check for git repository
    git_dir = directory / ".git"
    if git_dir.exists():
        result["has_git"] = True
        # Check if git repo is clean
        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(directory),
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Empty output means clean repo
            result["git_clean"] = len(status_result.stdout.strip()) == 0
        except Exception:
            result["git_clean"] = None

    # Define project indicator files
    project_indicators = {
        # JavaScript/TypeScript
        "package.json": {
            "type": "nodejs",
            "language": "JavaScript",
            "confidence": "high",
        },
        "package-lock.json": {
            "type": "nodejs",
            "language": "JavaScript",
            "confidence": "medium",
        },
        "yarn.lock": {
            "type": "nodejs",
            "language": "JavaScript",
            "confidence": "medium",
        },
        "tsconfig.json": {
            "type": "nodejs",
            "language": "TypeScript",
            "confidence": "high",
        },
        # Python
        "requirements.txt": {
            "type": "python",
            "language": "Python",
            "confidence": "high",
        },
        "setup.py": {"type": "python", "language": "Python", "confidence": "high"},
        "pyproject.toml": {
            "type": "python",
            "language": "Python",
            "confidence": "high",
        },
        "Pipfile": {"type": "python", "language": "Python", "confidence": "high"},
        "poetry.lock": {"type": "python", "language": "Python", "confidence": "medium"},
        # Rust
        "Cargo.toml": {"type": "rust", "language": "Rust", "confidence": "high"},
        "Cargo.lock": {"type": "rust", "language": "Rust", "confidence": "medium"},
        # Go
        "go.mod": {"type": "golang", "language": "Go", "confidence": "high"},
        "go.sum": {"type": "golang", "language": "Go", "confidence": "medium"},
        # Java
        "pom.xml": {"type": "maven", "language": "Java", "confidence": "high"},
        "build.gradle": {"type": "gradle", "language": "Java", "confidence": "high"},
        "build.gradle.kts": {
            "type": "gradle",
            "language": "Kotlin",
            "confidence": "high",
        },
        # Ruby
        "Gemfile": {"type": "ruby", "language": "Ruby", "confidence": "high"},
        "Gemfile.lock": {"type": "ruby", "language": "Ruby", "confidence": "medium"},
        # PHP
        "composer.json": {"type": "php", "language": "PHP", "confidence": "high"},
        # C/C++
        "CMakeLists.txt": {"type": "cmake", "language": "C/C++", "confidence": "high"},
        "Makefile": {"type": "make", "language": "C/C++", "confidence": "medium"},
        # .NET
        ".csproj": {"type": "dotnet", "language": "C#", "confidence": "high"},
        ".sln": {"type": "dotnet", "language": "C#", "confidence": "high"},
    }

    # Check for project files
    found_indicators = []
    confidence_scores = []

    for file_pattern, info in project_indicators.items():
        # Handle glob patterns (like .csproj)
        if file_pattern.startswith("."):
            matches = list(directory.glob(f"*{file_pattern}"))
            if matches:
                found_indicators.append((file_pattern, info))
                result["project_files"].extend([m.name for m in matches])
        else:
            file_path = directory / file_pattern
            if file_path.exists():
                found_indicators.append((file_pattern, info))
                result["project_files"].append(file_pattern)

    if found_indicators:
        result["has_code"] = True

        # Determine primary project type and languages
        types = {}
        languages = set()

        for _, info in found_indicators:
            proj_type = info["type"]
            language = info["language"]
            confidence = info["confidence"]

            types[proj_type] = types.get(proj_type, 0) + (
                2 if confidence == "high" else 1
            )
            languages.add(language)
            confidence_scores.append(confidence)

        # Primary type is the one with highest score
        if types:
            result["project_type"] = max(types.items(), key=lambda x: x[1])[0]

        result["languages"] = sorted(list(languages))

        # Overall confidence
        if "high" in confidence_scores:
            result["confidence"] = "high"
        elif "medium" in confidence_scores:
            result["confidence"] = "medium"

    # Check for common source directories (increases confidence if project files found)
    if result["has_code"]:
        source_dirs = ["src", "lib", "app", "pkg", "cmd", "internal"]
        for dir_name in source_dirs:
            if (directory / dir_name).is_dir():
                result["confidence"] = "high"
                break

    # ═══════════════════════════════════════════════════════════════════
    # FLOWISE EXTENSION HOOK
    # ═══════════════════════════════════════════════════════════════════
    try:
        # Try to import Flowise extension loader
        import sys
        from pathlib import Path

        # Get Context Foundry installation path (repo root)
        # __file__ is tools/mcp/project_detection.py
        # parent = tools/mcp/, parent.parent = tools/, parent.parent.parent = repo root
        cf_base = Path(__file__).parent.parent.parent

        # Check if extensions/flowise exists
        flowise_ext_path = cf_base / "extensions" / "flowise"

        if flowise_ext_path.exists():
            # Add to sys.path if not already there
            ext_parent = str(flowise_ext_path.parent)
            if ext_parent not in sys.path:
                sys.path.insert(0, ext_parent)

            # Import the extension
            from flowise import extensions_loader

            # Load Flowise detectors
            flowise_detectors = extensions_loader.load_extension_detectors()

            if flowise_detectors and "flowise" in flowise_detectors:
                # Check for Flowise JSON files in project directory
                json_files = list(directory.glob("*.json"))

                # Sample first 10 JSON files to avoid performance issues
                for json_file in json_files[:10]:
                    try:
                        detection = flowise_detectors["flowise"].detect_flowise_flow(
                            json_file
                        )

                        if detection.get("is_flowise"):
                            # Flowise flow detected!
                            print(
                                f"🔍 Flowise Extension: Detected {detection.get('flow_type')} flow in {json_file}"
                            )
                            print(f"   - Complexity: {detection.get('complexity')}")
                            print(f"   - Nodes: {detection.get('node_count', 0)}")
                            print(f"   - Agents: {detection.get('agent_count', 0)}")
                            print(
                                f"   - Has Memory: {detection.get('has_memory', False)}"
                            )
                            print(
                                f"   - Has Tools: {detection.get('has_tools', False)}"
                            )

                            result["flowise_flow"] = True
                            result["flowise_flow_type"] = detection.get("flow_type")
                            result["flowise_complexity"] = detection.get("complexity")
                            result["flowise_node_count"] = detection.get(
                                "node_count", 0
                            )
                            result["flowise_agent_count"] = detection.get(
                                "agent_count", 0
                            )
                            result["flowise_has_memory"] = detection.get(
                                "has_memory", False
                            )
                            result["flowise_has_tools"] = detection.get(
                                "has_tools", False
                            )

                            # Update project classification
                            if (
                                result["project_type"] is None
                                or result["confidence"] != "high"
                            ):
                                result["project_type"] = "flowise-workflow"
                                result["confidence"] = "high"

                            # Add to languages list
                            if "flowise" not in result["languages"]:
                                result["languages"].append("flowise")

                            # Add the detected flow file
                            result["project_files"].append(str(json_file))

                            print(
                                "✅ Flowise Extension: Setting flowise_flow=True in CONFIGURATION"
                            )

                            # Stop after first detection (optimization)
                            break

                    except Exception as e:
                        # Don't fail entire detection if one file has issues
                        print(f"⚠️  Flowise Extension: Error checking {json_file}: {e}")
                        continue

    except (ImportError, Exception):
        # Flowise extension not installed or error - continue without it
        pass
    # ═══════════════════════════════════════════════════════════════════
    # END FLOWISE EXTENSION HOOK
    # ═══════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════
    # ROBLOX EXTENSION HOOK
    # ═══════════════════════════════════════════════════════════════════
    try:
        cf_base = Path(__file__).parent.parent.parent
        roblox_ext_path = cf_base / "extensions" / "roblox"

        if roblox_ext_path.exists():
            ext_parent = str(roblox_ext_path.parent)
            if ext_parent not in sys.path:
                sys.path.insert(0, ext_parent)

            from roblox import extensions_loader

            roblox_detectors = extensions_loader.load_extension_detectors()

            if roblox_detectors and "roblox" in roblox_detectors:
                detection = roblox_detectors["roblox"].detect_roblox_project(directory)

                if detection.get("is_roblox"):
                    # Roblox project detected!
                    print(
                        f"🎮 Roblox Extension: Detected {detection.get('project_type')} project"
                    )
                    print(f"   - Subtype: {detection.get('project_subtype')}")
                    print(f"   - Complexity: {detection.get('complexity')}")
                    print(f"   - Has Tests: {detection.get('has_tests', False)}")

                    result["roblox_project"] = True
                    result["roblox_project_type"] = detection["project_type"]
                    result["project_subtype"] = detection.get("project_subtype", "rojo")
                    result["has_tests"] = detection.get("has_tests", False)
                    result["complexity"] = detection.get("complexity", "moderate")

                    # Update project classification
                    if result["project_type"] is None or result["confidence"] != "high":
                        result["project_type"] = detection["project_type"]
                        result["confidence"] = detection.get("confidence", "high")

                    # Add Lua to languages
                    if "lua" not in result["languages"]:
                        result["languages"].append("lua")

                    # Add metadata
                    if "metadata" in detection:
                        result["roblox_metadata"] = detection["metadata"]

                    print(
                        "✅ Roblox Extension: Setting roblox_project=True in CONFIGURATION"
                    )

    except (ImportError, Exception):
        # Roblox extension not installed or error - continue without it
        pass
    # ═══════════════════════════════════════════════════════════════════
    # END ROBLOX EXTENSION HOOK
    # ═══════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════
    # WORKDAY CANVAS KIT EXTENSION HOOK
    # ═══════════════════════════════════════════════════════════════════
    try:
        cf_base = Path(__file__).parent.parent.parent
        canvas_kit_ext_path = cf_base / "extensions" / "workday-canvas"

        if canvas_kit_ext_path.exists():
            ext_parent = str(canvas_kit_ext_path.parent)
            if ext_parent not in sys.path:
                sys.path.insert(0, ext_parent)

            # Import workday-canvas extension
            try:
                # Import as workday_canvas (Python module name)
                import importlib

                workday_canvas = importlib.import_module("workday-canvas")
                extensions_loader = workday_canvas.extensions_loader
            except ImportError:
                # Try alternative import
                from workday_canvas import extensions_loader

            # Load Canvas Kit detectors
            canvas_kit_detectors = extensions_loader.load_extension_detectors()

            if canvas_kit_detectors and "workday-canvas" in canvas_kit_detectors:
                # Detect Canvas Kit project
                detection = canvas_kit_detectors[
                    "workday-canvas"
                ].detect_canvas_kit_project(directory)

                if detection.get("is_canvas_kit"):
                    # Canvas Kit project detected!
                    print(
                        "🔍 Workday Canvas Kit Extension: Detected Canvas Kit project"
                    )
                    print(
                        f"   - Version: {detection.get('canvas_kit_version', 'unknown')}"
                    )
                    print(f"   - TypeScript: {detection.get('has_typescript', False)}")
                    print(f"   - Uses Emotion: {detection.get('uses_emotion', False)}")
                    print(
                        f"   - Preview Components: {detection.get('has_preview_components', False)}"
                    )
                    print(
                        f"   - Labs Components: {detection.get('has_labs_components', False)}"
                    )
                    print(
                        f"   - Component Imports: ~{detection.get('component_count_estimate', 0)}"
                    )

                    result["canvas_kit_project"] = True
                    result["canvas_kit_version"] = detection.get("canvas_kit_version")
                    result["canvas_kit_typescript"] = detection.get(
                        "has_typescript", False
                    )
                    result["canvas_kit_emotion"] = detection.get("uses_emotion", False)
                    result["canvas_kit_preview"] = detection.get(
                        "has_preview_components", False
                    )
                    result["canvas_kit_labs"] = detection.get(
                        "has_labs_components", False
                    )

                    # Update project classification
                    if (
                        result["project_type"] == "nodejs"
                        or result["confidence"] != "high"
                    ):
                        result["project_type"] = "workday-canvas"
                        result["confidence"] = "high"

                    # Add to languages list
                    if "Canvas Kit" not in result["languages"]:
                        result["languages"].append("Canvas Kit")

                    print(
                        "✅ Workday Canvas Kit Extension: Setting canvas_kit_project=True in CONFIGURATION"
                    )

    except (ImportError, Exception):
        # Canvas Kit extension not installed or error - continue without it
        pass
    # ═══════════════════════════════════════════════════════════════════
    # END WORKDAY CANVAS KIT EXTENSION HOOK
    # ═══════════════════════════════════════════════════════════════════

    return result

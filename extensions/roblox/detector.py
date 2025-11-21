"""
Roblox Project Detector

Detects Roblox game projects and classifies them by type and complexity.

Detection Priority:
1. Primary: Rojo projects (default.project.json or *.project.json)
2. Secondary: Placefile projects (*.rbxl or *.rbxlx in root)
3. Conflict Resolution: If both exist, prefer Rojo

Metadata Computed:
- is_roblox: bool
- project_type: "roblox-game" | "roblox-plugin" | None
- project_subtype: "rojo" | "placefile" | None
- has_tests: bool (True if src/ServerScriptService/Tests/*.lua exists)
- complexity: "simple" | "moderate" | "complex"
    - simple: ≤20 Luau files, no DataStore, no RemoteEvents
    - moderate: uses RemoteEvents/Functions OR DataStore
    - complex: >50 files OR multiple systems (shop+checkpoints+datastores)
- confidence: "high" | "medium" | "low"
"""

from pathlib import Path
from typing import Dict, Any, List
import json


def detect_roblox_project(directory: Path) -> Dict[str, Any]:
    """
    Detect Roblox game projects.

    Args:
        directory: Path to project directory

    Returns:
        Dict containing:
            is_roblox: bool - Whether this is a Roblox project
            project_type: str | None - Type of Roblox project
            project_subtype: str | None - "rojo" or "placefile"
            has_tests: bool - Whether Tests directory exists
            complexity: str - "simple", "moderate", or "complex"
            confidence: str - "high", "medium", or "low"
            metadata: dict - Additional detection metadata
    """
    # Initialize result
    result = {
        "is_roblox": False,
        "project_type": None,
        "project_subtype": None,
        "has_tests": False,
        "complexity": "moderate",
        "confidence": "low",
        "metadata": {},
    }

    # Convert to Path if string
    if isinstance(directory, str):
        directory = Path(directory)

    # =========================================================================
    # STEP 1: Check for Rojo project (PRIMARY DETECTION)
    # =========================================================================
    has_default_project_json = (directory / "default.project.json").exists()
    has_any_project_json = len(list(directory.glob("*.project.json"))) > 0
    has_rojo = has_default_project_json or has_any_project_json

    # =========================================================================
    # STEP 2: Check for placefile project (SECONDARY DETECTION)
    # =========================================================================
    has_rbxl = len(list(directory.glob("*.rbxl"))) > 0
    has_rbxlx = len(list(directory.glob("*.rbxlx"))) > 0
    has_placefile = has_rbxl or has_rbxlx

    # =========================================================================
    # STEP 3: Determine if this is a Roblox project
    # =========================================================================
    if not (has_rojo or has_placefile):
        return result  # Not a Roblox project

    # =========================================================================
    # STEP 4: Determine project subtype (CONFLICT RESOLUTION)
    # =========================================================================
    if has_rojo:
        # Rojo takes precedence
        result["project_subtype"] = "rojo"
        result["confidence"] = "high"
        result["metadata"]["rojo_config"] = (
            "default.project.json" if has_default_project_json else "custom"
        )

        # Check if placefile also exists (warn case)
        if has_placefile:
            result["metadata"]["warning"] = (
                "Both Rojo and placefile detected - using Rojo"
            )

    elif has_placefile:
        # Placefile only (no Rojo)
        result["project_subtype"] = "placefile"
        result["confidence"] = "medium"
        result["metadata"]["warning"] = "Placefile detected - Rojo workflow recommended"
        result["metadata"]["placefile_type"] = "rbxl" if has_rbxl else "rbxlx"

    # =========================================================================
    # STEP 5: Classify project type (game vs plugin vs library)
    # =========================================================================
    result["project_type"] = _classify_project_type(directory)

    # =========================================================================
    # STEP 6: Check for tests
    # =========================================================================
    result["has_tests"] = _has_tests(directory)

    # =========================================================================
    # STEP 7: Calculate complexity
    # =========================================================================
    result["complexity"] = _calculate_complexity(directory)

    # Mark as detected
    result["is_roblox"] = True

    return result


def _classify_project_type(directory: Path) -> str:
    """
    Classify Roblox project type.

    Detection rules:
    - plugin.lua in root → "roblox-plugin"
    - game.lua OR typical game structure → "roblox-game"
    - Pure ModuleScript structure → "roblox-library"

    Default: "roblox-game"
    """
    # Check for plugin
    if (directory / "plugin.lua").exists():
        return "roblox-plugin"

    # Check for explicit game marker
    if (directory / "game.lua").exists():
        return "roblox-game"

    # Check for typical game structure
    src_dir = directory / "src"
    if src_dir.exists():
        has_server_script_service = (src_dir / "ServerScriptService").exists()
        has_starter_player = (src_dir / "StarterPlayer").exists()
        has_workspace = (src_dir / "Workspace").exists()

        if has_server_script_service or has_starter_player or has_workspace:
            return "roblox-game"

    # Check for library structure (just ModuleScripts)
    module_files = list(directory.glob("**/*.lua"))
    if len(module_files) > 0 and all("Module" in f.stem for f in module_files[:5]):
        return "roblox-library"

    # Default to game
    return "roblox-game"


def _has_tests(directory: Path) -> bool:
    """
    Check if project has tests.

    Returns True if:
    - src/ServerScriptService/Tests/ exists AND contains .lua files
    - Any file matching *.spec.lua or *.test.lua exists
    """
    # Check standard test location
    tests_dir = directory / "src" / "ServerScriptService" / "Tests"
    if tests_dir.exists():
        test_files = list(tests_dir.glob("*.lua"))
        if len(test_files) > 0:
            return True

    # Check for TestEZ-style spec files
    spec_files = list(directory.glob("**/*.spec.lua"))
    test_files_pattern = list(directory.glob("**/*.test.lua"))

    return len(spec_files) > 0 or len(test_files_pattern) > 0


def _calculate_complexity(directory: Path) -> str:
    """
    Calculate project complexity.

    Complexity Levels:
    - simple: ≤20 Luau files, no DataStore, no RemoteEvents
    - moderate: uses RemoteEvents/Functions OR DataStore
    - complex: >50 files OR multiple systems (shop+checkpoints+datastores)

    Returns:
        "simple" | "moderate" | "complex"
    """
    # Count Luau files
    lua_files = list(directory.glob("**/*.lua"))
    file_count = len(lua_files)

    # Check for advanced features
    has_datastore = _check_for_datastore(lua_files)
    has_remote_events = _check_for_remote_events(lua_files)
    has_multiple_systems = _check_for_multiple_systems(directory)

    # Complexity rules
    if file_count > 50 or has_multiple_systems:
        return "complex"
    elif has_datastore or has_remote_events or file_count > 20:
        return "moderate"
    else:
        return "simple"


def _check_for_datastore(lua_files: List[Path]) -> bool:
    """Check if any files use DataStoreService."""
    for lua_file in lua_files[:20]:  # Sample first 20 files
        try:
            content = lua_file.read_text(encoding="utf-8", errors="ignore")
            if "DataStoreService" in content or "DataStore" in content:
                return True
        except Exception:
            continue
    return False


def _check_for_remote_events(lua_files: List[Path]) -> bool:
    """Check if any files use RemoteEvent or RemoteFunction."""
    for lua_file in lua_files[:20]:  # Sample first 20 files
        try:
            content = lua_file.read_text(encoding="utf-8", errors="ignore")
            if "RemoteEvent" in content or "RemoteFunction" in content:
                return True
        except Exception:
            continue
    return False


def _check_for_multiple_systems(directory: Path) -> bool:
    """
    Check if project has multiple game systems.

    Indicators of multiple systems:
    - 3+ manager/service files (e.g., CheckpointManager, CoinManager, ShopService)
    - Multiple UI folders
    - Complex directory structure
    """
    systems_dir = directory / "src" / "ServerScriptService" / "GameSystems"
    if systems_dir.exists():
        system_files = list(systems_dir.glob("*.lua"))
        if len(system_files) >= 3:
            return True

    # Check for multiple UI elements
    gui_dir = directory / "src" / "StarterGui"
    if gui_dir.exists():
        ui_folders = [d for d in gui_dir.iterdir() if d.is_dir()]
        if len(ui_folders) >= 2:
            return True

    return False


# =============================================================================
# ADDITIONAL HELPER FUNCTIONS
# =============================================================================


def get_rojo_config(directory: Path) -> Dict[str, Any]:
    """
    Read and parse Rojo project config.

    Returns:
        Parsed JSON config or empty dict if not found/invalid
    """
    # Try default.project.json first
    config_path = directory / "default.project.json"
    if not config_path.exists():
        # Try any *.project.json
        project_jsons = list(directory.glob("*.project.json"))
        if project_jsons:
            config_path = project_jsons[0]
        else:
            return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_project_metadata(directory: Path) -> Dict[str, Any]:
    """
    Get detailed project metadata.

    Returns:
        Dict with file counts, structure info, etc.
    """
    metadata = {
        "lua_file_count": 0,
        "has_rojo_config": False,
        "rojo_config_name": None,
        "directory_structure": {},
        "has_tests": False,
        "has_datastore": False,
        "has_remote_events": False,
    }

    # Count files
    lua_files = list(directory.glob("**/*.lua"))
    metadata["lua_file_count"] = len(lua_files)

    # Check Rojo config
    if (directory / "default.project.json").exists():
        metadata["has_rojo_config"] = True
        metadata["rojo_config_name"] = "default.project.json"
    else:
        project_jsons = list(directory.glob("*.project.json"))
        if project_jsons:
            metadata["has_rojo_config"] = True
            metadata["rojo_config_name"] = project_jsons[0].name

    # Check features
    metadata["has_tests"] = _has_tests(directory)
    metadata["has_datastore"] = _check_for_datastore(lua_files)
    metadata["has_remote_events"] = _check_for_remote_events(lua_files)

    # Directory structure
    src_dir = directory / "src"
    if src_dir.exists():
        structure = {}
        for subdir in src_dir.iterdir():
            if subdir.is_dir():
                file_count = len(list(subdir.glob("**/*.lua")))
                structure[subdir.name] = file_count
        metadata["directory_structure"] = structure

    return metadata


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_dir = Path(sys.argv[1])
        result = detect_roblox_project(test_dir)

        print("Roblox Project Detection Result:")
        print(f"  Is Roblox: {result['is_roblox']}")
        print(f"  Project Type: {result['project_type']}")
        print(f"  Subtype: {result['project_subtype']}")
        print(f"  Has Tests: {result['has_tests']}")
        print(f"  Complexity: {result['complexity']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Metadata: {result['metadata']}")

        # Get detailed metadata
        metadata = get_project_metadata(test_dir)
        print("\nDetailed Metadata:")
        print(f"  Lua Files: {metadata['lua_file_count']}")
        print(f"  Has Rojo: {metadata['has_rojo_config']}")
        print(f"  Directory Structure: {metadata['directory_structure']}")
    else:
        print("Usage: python detector.py <directory>")
        print("Example: python detector.py /path/to/roblox/game")

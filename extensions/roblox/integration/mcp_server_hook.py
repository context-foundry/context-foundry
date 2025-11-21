"""
Roblox Extension - MCP Server Detection Hook

This file contains the code to add to tools/mcp_utils/project_detection.py
to enable Roblox project detection.

Add this code after the existing extension hooks (e.g., after Flowise hook).
"""

from pathlib import Path
import sys
from typing import Any, Dict

# Placeholder defaults so linting passes; in real usage, `directory` and `result`
# come from detect_existing_codebase.
directory: Path = Path.cwd()
result: Dict[str, Any] = {}

# =============================================================================
# INSTALLATION INSTRUCTIONS
# =============================================================================
#
# 1. Open: tools/mcp_utils/project_detection.py
# 2. Find the section with extension hooks (search for "EXTENSION HOOK")
# 3. Add the code below after existing extension hooks
# 4. Ensure proper indentation (should be inside the detect_existing_codebase function)
#
# =============================================================================

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
                result["roblox_project"] = True
                result["roblox_project_type"] = detection["project_type"]
                result["project_subtype"] = detection.get("project_subtype", "rojo")
                result["project_type"] = detection["project_type"]
                result["confidence"] = detection.get("confidence", "high")
                result["has_tests"] = detection.get("has_tests", False)
                result["complexity"] = detection.get("complexity", "moderate")

                # Add metadata
                if "metadata" in detection:
                    result["roblox_metadata"] = detection["metadata"]

                # Add Lua to languages if not present
                if "lua" not in result.get("languages", []):
                    if "languages" not in result:
                        result["languages"] = []
                    result["languages"].append("lua")

                # Log detection
                print(
                    f"✓ Roblox project detected: {detection['project_type']} ({detection.get('project_subtype', 'unknown')})"
                )

except ImportError:
    # Graceful degradation - extension not installed
    pass
except Exception as e:
    # Log error but don't crash detection
    print(f"Warning: Roblox extension error: {e}")
# ═══════════════════════════════════════════════════════════════════

# =============================================================================
# VERIFICATION
# =============================================================================
#
# After adding the hook, verify it works:
#
# 1. Create a test Roblox project:
#    mkdir test-roblox-project
#    cd test-roblox-project
#    echo '{"name": "Test"}' > default.project.json
#
# 2. Run detection:
#    python -c "from tools.mcp_utils.project_detection import detect_existing_codebase; \
#               from pathlib import Path; \
#               result = detect_existing_codebase(Path('test-roblox-project')); \
#               print(result)"
#
# 3. Expected output should include:
#    {
#      "roblox_project": True,
#      "roblox_project_type": "roblox-game",
#      "project_subtype": "rojo",
#      ...
#    }
#
# =============================================================================

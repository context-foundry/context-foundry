"""
MCP Server Integration Hook

Code to add to mcp_server.py _detect_existing_codebase() method.

INTEGRATION INSTRUCTIONS:
Add this code block inside the _detect_existing_codebase() function (search for `# ANCHOR: detect_existing_codebase`).
"""

# ruff: noqa
# This file contains template code meant to be inserted into mcp_server.py
# Variables like 'directory', 'project_indicators', etc. exist in that context

# ═══════════════════════════════════════════════════════════════════
# FLOWISE EXTENSION HOOK
# ═══════════════════════════════════════════════════════════════════
# Add this code block in _detect_existing_codebase() method

try:
    # Try to import Flowise extension loader
    import sys
    from pathlib import Path

    # Get Context Foundry installation path
    cf_base = Path(__file__).parent.parent

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
                        project_indicators["flowise_flow"] = True
                        project_indicators["flowise_flow_type"] = detection.get(
                            "flow_type"
                        )
                        project_indicators["flowise_complexity"] = detection.get(
                            "complexity"
                        )

                        # Update project classification
                        if project_type is None or confidence != "high":
                            project_type = "flowise-workflow"
                            confidence = "high"

                        # Add to languages list
                        if "flowise" not in languages:
                            languages.append("flowise")

                        # Add the detected flow file
                        project_files.append(str(json_file))

                        # Log detection for debugging
                        # logger.info(f"Detected Flowise {detection['flow_type']} flow: {json_file}")

                        # Stop after first detection (optimization)
                        break

                except Exception:
                    # Don't fail entire detection if one file has issues
                    # logger.debug(f"Error analyzing {json_file} for Flowise: {e}")
                    continue

except ImportError:
    # Flowise extension not installed, continue without it
    # This is expected behavior for public Context Foundry installations
    pass
except Exception:
    # Any other error - log but don't break detection
    # logger.debug(f"Flowise extension error: {e}")
    pass

# ═══════════════════════════════════════════════════════════════════
# END FLOWISE EXTENSION HOOK
# ═══════════════════════════════════════════════════════════════════


"""
EXPECTED BEHAVIOR:

1. If extensions/flowise/ exists:
   - Scan JSON files in project directory
   - Detect Flowise flows using detector module
   - Add project indicators for Orchestrator to use
   - Set project_type to 'flowise-workflow' if detected

2. If extensions/flowise/ does NOT exist:
   - ImportError caught gracefully
   - No impact on normal Context Foundry operation
   - Public repo users never see errors

3. Result in project_indicators:
   {
       "flowise_flow": True,
       "flowise_flow_type": "multi-agent",
       "flowise_complexity": "moderate"
   }

4. Orchestrator can then conditionally load Flowise enhancements:
   - Scout phase gets Flowise research checklist
   - Architect phase gets Flowise patterns
   - Builder/Tester phases get Flowise-specific guidance
"""

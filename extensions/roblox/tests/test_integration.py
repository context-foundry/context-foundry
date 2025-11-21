"""
Integration tests for Roblox extension orchestration flow

Tests that the extension properly integrates with:
- Project detection system (MCP server hooks)
- Pattern loading and Context Codex
- Orchestrator prompt injection

Author: Context Foundry Roblox Extension
"""

import sys
from pathlib import Path
import json

# Add context-foundry root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def test_detection_integration():
    """Test that Roblox detection integrates with project_detection.py"""
    from extensions.roblox.detector import detect_roblox_project

    # Test with test_roblox_project
    test_project_path = (
        Path(__file__).parent.parent.parent.parent / "test_roblox_project"
    )
    assert test_project_path.exists(), "test_roblox_project must exist"

    # Direct detection should work
    result = detect_roblox_project(test_project_path)
    assert result["is_roblox"] is True, "Direct detection failed"
    assert result["project_type"] == "roblox-game"
    assert result["project_subtype"] == "rojo"

    print("✓ Direct detection works")

    # MCP server integration should work
    # (This would require running the actual MCP server, which is complex for unit tests)
    # For now, we verify the hook code exists in project_detection.py
    project_detection_path = (
        Path(__file__).parent.parent.parent.parent
        / "tools"
        / "mcp_utils"
        / "project_detection.py"
    )
    with open(project_detection_path) as f:
        content = f.read()
        assert (
            "roblox" in content.lower()
        ), "Roblox hook not found in project_detection.py"
        assert "detect_roblox_project" in content, "detect_roblox_project not imported"

    print("✓ MCP server hook exists in project_detection.py")


def test_pattern_loading():
    """Test that Roblox patterns load correctly"""
    from extensions.roblox.extensions_loader import load_extension_patterns

    # Use default pattern name (roblox-expertise)
    patterns = load_extension_patterns()

    assert patterns is not None, "Failed to load patterns"
    assert "patterns" in patterns, "Missing patterns key"

    pattern_list = patterns["patterns"]
    assert len(pattern_list) > 0, "No patterns loaded"

    # Check for expected patterns
    pattern_ids = [p["pattern_id"] for p in pattern_list]
    expected_patterns = [
        "obby-checkpoints-coin-shop",
        "roblox-module-structure",
        "roblox-datastore-best-practices",
        "roblox-remote-events-security",
    ]

    for expected in expected_patterns:
        assert expected in pattern_ids, f"Missing expected pattern: {expected}"

    print(f"✓ Loaded {len(pattern_list)} patterns")

    # Verify pattern structure (using actual schema)
    for pattern in pattern_list:
        assert "pattern_id" in pattern, "Pattern missing pattern_id"
        assert "category" in pattern, "Pattern missing category"
        assert "description" in pattern, "Pattern missing description"
        # Patterns have various optional fields, just check core ones exist

    print("✓ All patterns have valid structure")


def test_orchestrator_injection():
    """Test that Roblox prompts are injected into orchestrator"""
    orchestrator_path = (
        Path(__file__).parent.parent.parent.parent / "tools" / "orchestrator_prompt.txt"
    )

    with open(orchestrator_path) as f:
        content = f.read()

    # Check for anchor markers
    assert "=== ROBLOX-SCOUT-START ===" in content, "Scout anchor not found"
    assert "=== ROBLOX-ARCHITECT-START ===" in content, "Architect anchor not found"
    assert "=== ROBLOX-BUILDER-START ===" in content, "Builder anchor not found"
    assert "=== ROBLOX-TESTER-START ===" in content, "Tester anchor not found"
    assert "=== ROBLOX-DOCS-START ===" in content, "Docs anchor not found"

    print("✓ All phase anchors exist")

    # Check that phases use reference docs pattern (not embedded content)
    # Scout phase should reference the prompt file
    scout_start = content.find("=== ROBLOX-SCOUT-START ===")
    scout_end = content.find("=== ROBLOX-SCOUT-END ===")
    scout_content = content[scout_start:scout_end]

    assert (
        "Read extensions/roblox/prompts/SCOUT-PROJECT-ASSESSMENT.md" in scout_content
    ), "Scout doesn't reference prompt file"
    assert "Luau" in scout_content, "Scout language reminder missing"
    assert (
        "DataStore" in scout_content or "DO research" in scout_content
    ), "Scout critical reminders missing"

    print("✓ Scout phase uses reference docs pattern")

    # Architect phase should reference the prompt file
    arch_start = content.find("=== ROBLOX-ARCHITECT-START ===")
    arch_end = content.find("=== ROBLOX-ARCHITECT-END ===")
    arch_content = content[arch_start:arch_end]

    assert (
        "Read extensions/roblox/prompts/ARCHITECT-GAME-SYSTEMS.md" in arch_content
    ), "Architect doesn't reference prompt file"
    assert (
        "Server-authoritative" in arch_content or "server" in arch_content.lower()
    ), "Architect architecture reminder missing"

    print("✓ Architect phase uses reference docs pattern")

    # Builder phase should reference the prompt file
    builder_start = content.find("=== ROBLOX-BUILDER-START ===")
    builder_end = content.find("=== ROBLOX-BUILDER-END ===")
    builder_content = content[builder_start:builder_end]

    assert (
        "Read extensions/roblox/prompts/BUILDER-LUAU-BEST-PRACTICES.md"
        in builder_content
    ), "Builder doesn't reference prompt file"
    assert "RemoteEvent" in builder_content, "Builder validation reminder missing"
    assert "Luau" in builder_content, "Builder language not specified"

    print("✓ Builder phase uses reference docs pattern")

    # Tester phase should reference the prompt file
    tester_start = content.find("=== ROBLOX-TESTER-START ===")
    tester_end = content.find("=== ROBLOX-TESTER-END ===")
    tester_content = content[tester_start:tester_end]

    assert (
        "Read extensions/roblox/prompts/TESTER-TEST-STRATEGY.md" in tester_content
    ), "Tester doesn't reference prompt file"
    assert (
        "TestEZ" in tester_content or "test" in tester_content.lower()
    ), "Tester strategy reminder missing"

    print("✓ Tester phase uses reference docs pattern")

    # Docs phase should reference the prompt file
    docs_start = content.find("=== ROBLOX-DOCS-START ===")
    docs_end = content.find("=== ROBLOX-DOCS-END ===")
    docs_content = content[docs_start:docs_end]

    assert (
        "Read extensions/roblox/prompts/DOCS-README-GUIDE.md" in docs_content
    ), "Docs doesn't reference prompt file"
    assert "Rojo" in docs_content, "Docs build tool not mentioned"

    print("✓ Docs phase uses reference docs pattern")


def test_prompt_files_exist():
    """Test that all phase-specific prompt files exist"""
    prompts_dir = Path(__file__).parent.parent / "prompts"

    expected_prompts = [
        "SCOUT-PROJECT-ASSESSMENT.md",
        "ARCHITECT-GAME-SYSTEMS.md",
        "BUILDER-LUAU-BEST-PRACTICES.md",
        "TESTER-TEST-STRATEGY.md",
        "DOCS-README-GUIDE.md",
    ]

    for prompt_file in expected_prompts:
        prompt_path = prompts_dir / prompt_file
        assert prompt_path.exists(), f"Missing prompt file: {prompt_file}"

        # Verify file has content
        assert prompt_path.stat().st_size > 100, f"Prompt file too small: {prompt_file}"

    print(f"✓ All {len(expected_prompts)} prompt files exist")


def test_template_completeness():
    """Test that basic-obby template has all required components"""
    template_dir = Path(__file__).parent.parent / "templates" / "basic-obby"

    # Required files
    required_files = [
        "default.project.json",
        "README_ROBLOX.md",
        ".luaurc",
        "src/ServerScriptService/GameSystems/PlayerDataManager.lua",
        "src/ServerScriptService/GameSystems/CheckpointManager.lua",
        "src/ServerScriptService/GameSystems/CoinManager.lua",
        "src/ServerScriptService/GameSystems/ShopService.lua",
        "src/ServerScriptService/Tests/CheckpointManager.spec.lua",
        "src/ServerScriptService/Tests/CoinManager.spec.lua",
        "src/ServerScriptService/Tests/ShopService.spec.lua",
        "src/ReplicatedStorage/Modules/PlayerData.lua",
        "src/ReplicatedStorage/Modules/ShopConfig.lua",
        "src/ReplicatedStorage/Modules/GameConfig.lua",
        "src/StarterGui/CoinDisplay/CoinLabel.lua",
        "src/StarterGui/StageCounter/StageLabel.lua",
        "src/StarterGui/ShopUI/ShopFrame.lua",
    ]

    missing_files = []
    for file_path in required_files:
        full_path = template_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)

    assert len(missing_files) == 0, f"Template missing files: {missing_files}"

    print(f"✓ Template has all {len(required_files)} required files")

    # Verify default.project.json has RemoteEvents
    with open(template_dir / "default.project.json") as f:
        rojo_config = json.load(f)

    remotes = rojo_config["tree"]["ReplicatedStorage"]["Remotes"]
    assert "UpdateCheckpoint" in remotes, "Missing UpdateCheckpoint RemoteEvent"
    assert "UpdateCoins" in remotes, "Missing UpdateCoins RemoteEvent"
    assert "CoinCollected" in remotes, "Missing CoinCollected RemoteEvent"
    assert "PurchaseItem" in remotes, "Missing PurchaseItem RemoteEvent"

    print("✓ Template has all required RemoteEvents")


def test_isolation():
    """Test that Roblox extension doesn't contaminate non-Roblox projects"""
    from extensions.roblox.detector import detect_roblox_project

    # Test with a Python project (test_python_project)
    python_project_path = (
        Path(__file__).parent.parent.parent.parent / "test_python_project"
    )

    if python_project_path.exists():
        result = detect_roblox_project(python_project_path)
        assert result["is_roblox"] is False, "False positive on Python project"
        print("✓ Python project correctly not detected as Roblox")
    else:
        print("⚠ test_python_project not found, skipping isolation test")


if __name__ == "__main__":
    print("=" * 70)
    print("ROBLOX EXTENSION - INTEGRATION TESTS")
    print("=" * 70)
    print()

    tests = [
        ("Detection Integration", test_detection_integration),
        ("Pattern Loading", test_pattern_loading),
        ("Orchestrator Injection", test_orchestrator_injection),
        ("Prompt Files Exist", test_prompt_files_exist),
        ("Template Completeness", test_template_completeness),
        ("Isolation", test_isolation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"Running: {test_name}")
        print("-" * 70)
        try:
            test_func()
            print(f"✅ {test_name} PASSED\n")
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_name} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"💥 {test_name} ERROR: {e}\n")
            failed += 1

    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)

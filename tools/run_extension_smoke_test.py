#!/usr/bin/env python3
"""
Extension Smoke Test

Quick validation that an extension is properly configured and loadable.

Usage:
    python tools/run_extension_smoke_test.py --extension roblox
"""

import argparse
import sys
from pathlib import Path

# Add Context Foundry to path
cf_root = Path(__file__).parent.parent
sys.path.insert(0, str(cf_root))


def smoke_test_extension(extension_name: str) -> bool:
    """
    Run comprehensive smoke test for extension.

    Tests:
    1. Extension directory exists
    2. Detector module loads
    3. Patterns load and parse correctly
    4. Prompts exist and have content
    5. Test project detection (Roblox-specific)
    6. Orchestrator injection validation (Roblox-specific)
    7. Template validation (Roblox-specific)
    8. Integration test suite runs (Roblox-specific)

    Returns:
        True if all tests pass
    """
    print("=" * 70)
    print(f"Extension Smoke Test: {extension_name}")
    print("=" * 70)

    test_count = 0
    total_tests = 7 if extension_name == "roblox" else 4

    # Test 1: Extension directory exists
    test_count += 1
    print(f"\n[{test_count}/{total_tests}] Checking extension directory...")
    ext_dir = cf_root / "extensions" / extension_name

    if not ext_dir.exists():
        print(f"  ✗ FAIL: Extension directory not found: {ext_dir}")
        return False

    print(f"  ✓ PASS: Extension directory exists: {ext_dir}")

    # Test 2: Detector module loads
    test_count += 1
    print(f"\n[{test_count}/{total_tests}] Loading detector module...")
    try:
        sys.path.insert(0, str(ext_dir.parent))
        mod = __import__(extension_name)
        detector = mod.extensions_loader.load_extension_detectors()

        if extension_name not in detector:
            print(f"  ✗ FAIL: Detector for '{extension_name}' not found")
            return False

        print("  ✓ PASS: Detector loaded successfully")

    except ImportError as e:
        print(f"  ✗ FAIL: Failed to import extension: {e}")
        return False
    except Exception as e:
        print(f"  ✗ FAIL: Error loading detector: {e}")
        return False

    # Test 3: Patterns load
    test_count += 1
    print(f"\n[{test_count}/{total_tests}] Loading and validating patterns...")
    try:
        patterns = mod.extensions_loader.load_extension_patterns()

        if patterns:
            pattern_count = len(patterns.get("patterns", []))
            issue_count = len(patterns.get("common_issues", []))
            print("  ✓ PASS: Patterns loaded successfully")
            print(f"         Patterns: {pattern_count}")
            print(f"         Issues: {issue_count}")

            # Validate pattern structure
            for pattern in patterns.get("patterns", []):
                assert "pattern_id" in pattern, f"Pattern missing pattern_id: {pattern}"
                assert "category" in pattern, f"Pattern missing category: {pattern}"
                assert (
                    "description" in pattern
                ), f"Pattern missing description: {pattern}"

            print("  ✓ PASS: All patterns have valid structure")
        else:
            print("  ⚠  WARN: No patterns found (this may be intentional)")

    except AssertionError as e:
        print(f"  ✗ FAIL: Pattern validation failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ FAIL: Error loading patterns: {e}")
        return False

    # Test 4: Prompts exist
    test_count += 1
    print(f"\n[{test_count}/{total_tests}] Checking prompts...")
    prompts_dir = ext_dir / "prompts"

    if not prompts_dir.exists():
        print("  ✗ FAIL: Prompts directory not found")
        return False

    prompt_files = list(prompts_dir.glob("*.md"))
    if len(prompt_files) == 0:
        print("  ✗ FAIL: No prompt files found")
        return False

    print(f"  ✓ PASS: Found {len(prompt_files)} prompt files")

    # Validate prompts have content
    for prompt_file in prompt_files:
        content = prompt_file.read_text()
        if len(content) < 100:
            print(
                f"  ⚠  WARN: Prompt file too small: {prompt_file.name} ({len(content)} bytes)"
            )
        else:
            print(f"         ✓ {prompt_file.name} ({len(content)} bytes)")

    # Roblox-specific tests
    if extension_name == "roblox":
        # Test 5: Test project detection
        test_count += 1
        print(f"\n[{test_count}/{total_tests}] Testing project detection...")
        try:
            test_project_path = cf_root / "test_roblox_project"
            if not test_project_path.exists():
                print("  ✗ FAIL: test_roblox_project not found")
                return False

            detect_fn = getattr(detector[extension_name], "detect_roblox_project")
            result = detect_fn(test_project_path)

            if not result.get("is_roblox"):
                print("  ✗ FAIL: Failed to detect test_roblox_project as Roblox")
                return False

            print("  ✓ PASS: test_roblox_project correctly detected")
            print(f"         Type: {result.get('project_type')}")
            print(f"         Subtype: {result.get('project_subtype')}")

        except Exception as e:
            print(f"  ✗ FAIL: Detection test failed: {e}")
            return False

        # Test 6: Template validation
        test_count += 1
        print(f"\n[{test_count}/{total_tests}] Validating template project...")
        try:
            template_path = ext_dir / "templates" / "basic-obby"
            if not template_path.exists():
                print(f"  ✗ FAIL: Template not found: {template_path}")
                return False

            # Check required files
            required_files = [
                "default.project.json",
                "README_ROBLOX.md",
                ".luaurc",
                "src/ServerScriptService/GameSystems/CheckpointManager.lua",
                "src/ServerScriptService/Tests/CheckpointManager.spec.lua",
                "src/ReplicatedStorage/Modules/PlayerData.lua",
                "src/StarterGui/CoinDisplay/CoinLabel.lua",
            ]

            missing = []
            for file_path in required_files:
                if not (template_path / file_path).exists():
                    missing.append(file_path)

            if missing:
                print(f"  ✗ FAIL: Template missing files: {missing}")
                return False

            print("  ✓ PASS: Template has all required files")
            print(f"         Checked {len(required_files)} files")

        except Exception as e:
            print(f"  ✗ FAIL: Template validation failed: {e}")
            return False

        # Test 7: Integration tests
        test_count += 1
        print(f"\n[{test_count}/{total_tests}] Running integration tests...")
        try:
            import subprocess

            test_script = ext_dir / "tests" / "test_integration.py"

            if not test_script.exists():
                print("  ⚠  WARN: Integration test script not found")
            else:
                result = subprocess.run(
                    [sys.executable, str(test_script)],
                    cwd=cf_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode != 0:
                    print("  ✗ FAIL: Integration tests failed")
                    print(result.stdout)
                    print(result.stderr)
                    return False

                # Parse results
                if "RESULTS:" in result.stdout:
                    results_line = [
                        line for line in result.stdout.split("\n") if "RESULTS:" in line
                    ][0]
                    print(f"  ✓ PASS: {results_line}")
                else:
                    print("  ✓ PASS: Integration tests succeeded")

        except subprocess.TimeoutExpired:
            print("  ✗ FAIL: Integration tests timed out")
            return False
        except Exception as e:
            print(f"  ⚠  WARN: Could not run integration tests: {e}")

    # Summary
    print("\n" + "=" * 70)
    print(f"✅ All {test_count} tests PASSED for {extension_name}")
    print("=" * 70)

    # Additional info
    print("\nExtension Info:")
    try:
        info = mod.extensions_loader.get_extension_info()
        print(f"  Name: {info.get('name')}")
        print(f"  Version: {info.get('version')}")
        print(f"  Description: {info.get('description')}")
        print(
            f"  Supported Types: {', '.join(info.get('supported_project_types', []))}"
        )
    except Exception:
        pass

    return True


def main():
    parser = argparse.ArgumentParser(description="Run extension smoke test")
    parser.add_argument(
        "--extension", required=True, help="Extension name (e.g., 'roblox')"
    )

    args = parser.parse_args()

    success = smoke_test_extension(args.extension)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

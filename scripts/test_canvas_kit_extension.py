#!/usr/bin/env python3
"""
Test Workday Canvas Kit Extension

Verifies that the Canvas Kit extension is properly installed and can detect
Canvas Kit projects.
"""

import json
import sys
from pathlib import Path


def test_extension_structure():
    """Test that extension files exist."""
    print("🔍 Testing Canvas Kit extension structure...")

    cf_root = Path(__file__).parent.parent
    extension_dir = cf_root / "extensions" / "workday-canvas"

    required_files = [
        extension_dir / "__init__.py",
        extension_dir / "detector.py",
        extension_dir / "extensions_loader.py",
        extension_dir / "patterns" / "canvas-kit-expertise.json",
        extension_dir / "examples" / "conflict-of-interest" / "README.md",
        extension_dir / "components" / "workflows" / "README.md",
        extension_dir / "README.md",
    ]

    missing_files = []
    for file_path in required_files:
        if not file_path.exists():
            missing_files.append(str(file_path))
            print(f"  ❌ Missing: {file_path}")
        else:
            print(f"  ✅ Found: {file_path.name}")

    if missing_files:
        print(
            f"\n❌ Extension structure test FAILED. Missing {len(missing_files)} files."
        )
        return False

    print("\n✅ Extension structure test PASSED")
    return True


def test_pattern_file():
    """Test that pattern file is valid JSON."""
    print("\n🔍 Testing canvas-kit-expertise.json...")

    cf_root = Path(__file__).parent.parent
    pattern_file = (
        cf_root
        / "extensions"
        / "workday-canvas"
        / "patterns"
        / "canvas-kit-expertise.json"
    )

    try:
        with open(pattern_file, "r", encoding="utf-8") as f:
            patterns = json.load(f)

        print("  ✅ Valid JSON")
        print(f"  ✅ Version: {patterns.get('version')}")
        print(f"  ✅ Last updated: {patterns.get('last_updated')}")

        # Check required sections
        required_sections = [
            "installation",
            "setup",
            "design_principles",
            "component_library",
            "common_patterns",
            "best_practices",
        ]

        for section in required_sections:
            if section in patterns:
                print(f"  ✅ Section: {section}")
            else:
                print(f"  ❌ Missing section: {section}")
                return False

        # Count components
        categories = patterns.get("component_library", {}).get("categories", {})
        total_components = sum(
            len(cat.get("components", [])) for cat in categories.values()
        )
        print(f"  ✅ Total components documented: {total_components}")

        print("\n✅ Pattern file test PASSED")
        return True

    except json.JSONDecodeError as e:
        print(f"  ❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_detector_import():
    """Test that detector module can be imported."""
    print("\n🔍 Testing detector module import...")

    try:
        # Add extensions to path
        cf_root = Path(__file__).parent.parent
        extensions_dir = cf_root / "extensions"
        if str(extensions_dir) not in sys.path:
            sys.path.insert(0, str(extensions_dir))

        # Try to import (with dash)
        try:
            import importlib

            workday_canvas = importlib.import_module("workday-canvas")
            detector = workday_canvas.detector
            print("  ✅ Imported with dash: workday-canvas")
        except ImportError:
            # Try underscore
            from workday_canvas import detector

            print("  ✅ Imported with underscore: workday_canvas")

        # Test detector function exists
        if hasattr(detector, "detect_canvas_kit_project"):
            print("  ✅ detect_canvas_kit_project() found")
        else:
            print("  ❌ detect_canvas_kit_project() not found")
            return False

        if hasattr(detector, "detect_canvas_kit_from_prompt"):
            print("  ✅ detect_canvas_kit_from_prompt() found")
        else:
            print("  ❌ detect_canvas_kit_from_prompt() not found")
            return False

        print("\n✅ Detector import test PASSED")
        return True

    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_prompt_detection():
    """Test prompt keyword detection."""
    print("\n🔍 Testing prompt keyword detection...")

    try:
        cf_root = Path(__file__).parent.parent
        extensions_dir = cf_root / "extensions"
        if str(extensions_dir) not in sys.path:
            sys.path.insert(0, str(extensions_dir))

        import importlib

        workday_canvas = importlib.import_module("workday-canvas")
        detector = workday_canvas.detector

        test_cases = [
            ("Create a COI app with Workday Canvas Kit", True),
            ("Build a React app using Canvas Kit", True),
            ("Workday-style form application", True),
            ("Create a simple React app", False),
            ("Build a Vue.js application", False),
        ]

        all_passed = True
        for prompt, expected in test_cases:
            result = detector.detect_canvas_kit_from_prompt(prompt)
            status = "✅" if result == expected else "❌"
            print(f"  {status} '{prompt[:40]}...' -> {result} (expected {expected})")
            if result != expected:
                all_passed = False

        if all_passed:
            print("\n✅ Prompt detection test PASSED")
        else:
            print("\n❌ Prompt detection test FAILED")

        return all_passed

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Workday Canvas Kit Extension - Test Suite")
    print("=" * 60)

    tests = [
        test_extension_structure,
        test_pattern_file,
        test_detector_import,
        test_prompt_detection,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if all(results):
        print("\n🎉 All tests PASSED! Canvas Kit extension is ready.")
        return 0
    else:
        print("\n❌ Some tests FAILED. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

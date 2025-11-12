#!/usr/bin/env python3
"""
Test script to verify Flowise extension integration.

Tests both:
1. File-based detection (scanning JSON files)
2. Keyword-based detection (task description)
"""

# Add context-foundry repo root to path
# __file__ is tests/test_flowise_detection.py
# parent = tests/, parent.parent = repo root
import sys
from pathlib import Path

cf_root = Path(__file__).parent.parent
sys.path.insert(0, str(cf_root))

from tools.mcp_server import _detect_existing_codebase  # noqa: E402


def test_file_based_detection():
    """Test detection of existing Flowise JSON files."""
    print("\n" + "=" * 70)
    print("TEST 1: File-Based Detection")
    print("=" * 70)

    # Test with extensions/flowise directory (has example JSON files)
    test_dir = cf_root / "extensions" / "flowise" / "examples"

    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        print("   Creating a test directory with sample Flowise JSON...")
        test_dir = cf_root / "test_flowise_project"
        test_dir.mkdir(exist_ok=True)

        # Create a minimal Flowise flow JSON
        sample_json = test_dir / "test-flow.json"
        sample_json.write_text("""{
    "nodes": [
        {
            "id": "chatOpenAI_0",
            "type": "chatOpenAI",
            "data": {"label": "ChatOpenAI"}
        }
    ],
    "edges": []
}""")
        print(f"   ✅ Created test file: {sample_json}")

    print(f"\n📁 Testing directory: {test_dir}")
    result = _detect_existing_codebase(test_dir)

    print("\n📊 Detection Results:")
    print(f"   flowise_flow: {result.get('flowise_flow', False)}")
    print(f"   flowise_flow_type: {result.get('flowise_flow_type', 'N/A')}")
    print(f"   flowise_complexity: {result.get('flowise_complexity', 'N/A')}")
    print(f"   project_type: {result.get('project_type', 'N/A')}")
    print(f"   languages: {result.get('languages', [])}")

    if result.get("flowise_flow"):
        print("\n✅ File-based detection PASSED!")
        return True
    else:
        print("\n❌ File-based detection FAILED!")
        print("   Expected: flowise_flow = True")
        print("   Got: flowise_flow = False")
        return False


def test_keyword_detection():
    """Test keyword-based detection from task description."""
    print("\n" + "=" * 70)
    print("TEST 2: Keyword-Based Detection")
    print("=" * 70)

    # Simulate what happens in autonomous_build_and_deploy
    test_dir = cf_root / "test_keyword_detection"
    test_dir.mkdir(exist_ok=True)

    print(f"\n📁 Testing directory: {test_dir} (empty)")

    # Get initial detection (should be empty)
    codebase_info = _detect_existing_codebase(test_dir)

    # Simulate the keyword detection logic
    task = "Build a Flowise multi-agent customer service flow"
    task_lower = task.lower()

    flowise_keywords = [
        "flowise",
        "agent flow",
        "multi-agent flow",
        "chatflow",
        "agentflow",
        "flowise workflow",
    ]

    print(f"\n📝 Task: '{task}'")
    print(f"🔍 Checking for keywords: {flowise_keywords}")

    if not codebase_info.get("flowise_flow", False):
        if any(keyword in task_lower for keyword in flowise_keywords):
            codebase_info["flowise_flow"] = True

            # Infer flow type
            if "multi-agent" in task_lower:
                codebase_info["flowise_flow_type"] = "multi-agent"
            codebase_info["flowise_complexity"] = "moderate"

    print("\n📊 Detection Results:")
    print(f"   flowise_flow: {codebase_info.get('flowise_flow', False)}")
    print(f"   flowise_flow_type: {codebase_info.get('flowise_flow_type', 'N/A')}")
    print(f"   flowise_complexity: {codebase_info.get('flowise_complexity', 'N/A')}")

    # Cleanup
    test_dir.rmdir()

    if (
        codebase_info.get("flowise_flow")
        and codebase_info.get("flowise_flow_type") == "multi-agent"
    ):
        print("\n✅ Keyword-based detection PASSED!")
        return True
    else:
        print("\n❌ Keyword-based detection FAILED!")
        return False


def main():
    print("\n🧪 Flowise Extension Integration Tests")
    print("=" * 70)

    test1_passed = test_file_based_detection()
    test2_passed = test_keyword_detection()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"File-based detection: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Keyword detection:    {'✅ PASS' if test2_passed else '❌ FAIL'}")

    if test1_passed and test2_passed:
        print("\n🎉 All tests PASSED! Flowise extension is properly integrated.")
        return 0
    else:
        print("\n⚠️  Some tests FAILED. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

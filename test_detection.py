#!/usr/bin/env python3
"""
Test script for codebase detection and task intent recognition.

Usage:
    python test_detection.py [directory_path]

If no directory is provided, tests several sample directories.
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any


# ============================================================================
# Detection Functions (copied from mcp_server.py for standalone testing)
# ============================================================================

def _detect_existing_codebase(directory: Path) -> Dict[str, Any]:
    """
    Detect if a directory contains an existing codebase and identify its characteristics.
    """
    result = {
        "has_code": False,
        "project_type": None,
        "languages": [],
        "has_git": False,
        "git_clean": None,
        "project_files": [],
        "confidence": "low"
    }

    if not directory.exists():
        return result

    # Check for git repository
    git_dir = directory / ".git"
    if git_dir.exists():
        result["has_git"] = True
        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(directory),
                capture_output=True,
                text=True,
                timeout=5
            )
            result["git_clean"] = len(status_result.stdout.strip()) == 0
        except:
            result["git_clean"] = None

    # Define project indicator files
    project_indicators = {
        "package.json": {"type": "nodejs", "language": "JavaScript", "confidence": "high"},
        "package-lock.json": {"type": "nodejs", "language": "JavaScript", "confidence": "medium"},
        "tsconfig.json": {"type": "nodejs", "language": "TypeScript", "confidence": "high"},
        "requirements.txt": {"type": "python", "language": "Python", "confidence": "high"},
        "setup.py": {"type": "python", "language": "Python", "confidence": "high"},
        "pyproject.toml": {"type": "python", "language": "Python", "confidence": "high"},
        "Cargo.toml": {"type": "rust", "language": "Rust", "confidence": "high"},
        "go.mod": {"type": "golang", "language": "Go", "confidence": "high"},
        "pom.xml": {"type": "maven", "language": "Java", "confidence": "high"},
        "Gemfile": {"type": "ruby", "language": "Ruby", "confidence": "high"},
    }

    found_indicators = []
    confidence_scores = []

    for file_pattern, info in project_indicators.items():
        file_path = directory / file_pattern
        if file_path.exists():
            found_indicators.append((file_pattern, info))
            result["project_files"].append(file_pattern)

    if found_indicators:
        result["has_code"] = True
        types = {}
        languages = set()

        for _, info in found_indicators:
            proj_type = info["type"]
            language = info["language"]
            confidence = info["confidence"]
            types[proj_type] = types.get(proj_type, 0) + (2 if confidence == "high" else 1)
            languages.add(language)
            confidence_scores.append(confidence)

        if types:
            result["project_type"] = max(types.items(), key=lambda x: x[1])[0]
        result["languages"] = sorted(list(languages))

        if "high" in confidence_scores:
            result["confidence"] = "high"
        elif "medium" in confidence_scores:
            result["confidence"] = "medium"

    if result["has_code"]:
        source_dirs = ["src", "lib", "app", "pkg", "cmd", "internal"]
        for dir_name in source_dirs:
            if (directory / dir_name).is_dir():
                result["confidence"] = "high"
                break

    return result


def _detect_task_intent(task: str) -> str:
    """
    Detect the user's intent from the task description.
    """
    task_lower = task.lower()

    if any(word in task_lower for word in ["fix", "bug", "issue", "error", "broken", "repair"]):
        return "fix_bug"
    if any(word in task_lower for word in ["upgrade", "update dependencies", "update deps", "migrate to"]):
        return "upgrade_deps"
    if any(word in task_lower for word in ["refactor", "restructure", "reorganize", "clean up"]):
        return "refactor"
    if any(word in task_lower for word in ["add tests", "write tests", "test coverage", "unit test"]):
        return "add_tests"
    if any(word in task_lower for word in ["add", "enhance", "improve", "implement", "create feature", "new feature"]):
        return "add_feature"

    return "new_project"


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)


def test_codebase_detection(directory: str):
    """Test codebase detection on a directory."""
    dir_path = Path(directory).expanduser().resolve()

    print(f"\n📁 Analyzing: {dir_path}")
    print(f"   Exists: {dir_path.exists()}")

    if not dir_path.exists():
        print("   ❌ Directory does not exist, skipping...\n")
        return

    # Run detection
    result = _detect_existing_codebase(dir_path)

    # Pretty print results
    print(f"\n   Has Code: {'✅ YES' if result['has_code'] else '❌ NO'}")

    if result['has_code']:
        print(f"   Project Type: {result['project_type']}")
        print(f"   Languages: {', '.join(result['languages'])}")
        print(f"   Confidence: {result['confidence'].upper()}")
        print(f"   Project Files: {', '.join(result['project_files'][:5])}")
        if len(result['project_files']) > 5:
            print(f"                  ... and {len(result['project_files']) - 5} more")

    if result['has_git']:
        git_status = "✅ Clean" if result['git_clean'] else "⚠️  Dirty" if result['git_clean'] is False else "❓ Unknown"
        print(f"   Git Repo: ✅ YES ({git_status})")
    else:
        print(f"   Git Repo: ❌ NO")

    # Full JSON for debugging
    print(f"\n   Full Result:")
    print(f"   {json.dumps(result, indent=6)}")


def test_intent_detection():
    """Test task intent detection on various task descriptions."""

    test_cases = [
        "Build a new weather app with React",
        "Fix the authentication bug in the login page",
        "Add dark mode feature to the UI",
        "Upgrade dependencies to latest versions",
        "Refactor the database layer to use SQLAlchemy",
        "Add unit tests for the payment module",
        "The user registration form is broken, please repair it",
        "Enhance the search functionality with fuzzy matching",
        "Update all npm packages",
        "Implement a new dashboard feature",
    ]

    print(f"\n{'Task Description':<55} → Mode")
    print('-'*70)

    for task in test_cases:
        mode = _detect_task_intent(task)
        # Format mode nicely
        mode_display = mode.replace('_', ' ').title()
        task_display = task[:52] + "..." if len(task) > 52 else task
        print(f"{task_display:<55} → {mode_display}")


def main():
    """Main test function."""
    print("\n" + "🔍 Context Foundry - Detection System Test".center(70))

    # Test 1: Task Intent Detection
    print_section("TEST 1: Task Intent Detection")
    test_intent_detection()

    # Test 2: Codebase Detection
    print_section("TEST 2: Codebase Detection")

    if len(sys.argv) > 1:
        # Test the directory provided as argument
        test_codebase_detection(sys.argv[1])
    else:
        # Test several sample directories
        sample_dirs = [
            "/tmp/youtube-transcript-summarizer",  # Python FastAPI project
            "/Users/name/homelab/context-foundry",  # This repo (Python)
            "/tmp/nonexistent-directory",  # Doesn't exist
            ".",  # Current directory
        ]

        for directory in sample_dirs:
            test_codebase_detection(directory)

    print_section("✅ Tests Complete")
    print()


if __name__ == "__main__":
    main()

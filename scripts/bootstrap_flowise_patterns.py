#!/usr/bin/env python3
# ruff: noqa: E402
"""
[DEPRECATED] Bootstrap Flowise Patterns into Global Pattern Storage

⚠️  WARNING: PATTERN ISOLATION MODEL - DO NOT RUN THIS SCRIPT
⚠️
⚠️  Extension patterns (Flowise, Roblox, etc.) should stay ISOLATED in their
⚠️  own directories and NOT be merged into global patterns.
⚠️
⚠️  WHY: Prevents context bloat and cross-contamination
⚠️  - Flowise builds read ONLY extensions/flowise/patterns/
⚠️  - Roblox builds read ONLY extensions/roblox/patterns/
⚠️  - General builds read ONLY ~/.context-foundry/patterns/
⚠️
⚠️  This script exists for backward compatibility only.
⚠️  Use it ONLY if you explicitly want to merge extension patterns into
⚠️  global storage (not recommended).

ORIGINAL PURPOSE:
This script loads patterns from extensions/flowise/patterns/flowise-expertise.json
and merges them into the global pattern files at ~/.context-foundry/patterns/

Idempotent: Safe to re-run after pattern updates. Also normalizes existing entries.

Usage:
    python scripts/bootstrap_flowise_patterns.py --force-merge

    (Requires --force-merge flag to acknowledge pattern isolation model)
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add Context Foundry to path
cf_root = Path(__file__).parent.parent
sys.path.insert(0, str(cf_root))
sys.path.insert(0, str(cf_root / "tools"))

from mcp_utils.pattern_management import (  # ruff: noqa: E402
    read_global_patterns_impl,
    save_global_patterns_impl,
)


def normalize_pattern_entry(entry: dict) -> dict:
    """Normalize a pattern entry to ensure consistent schema.

    Ensures:
    - 'id' field exists (copied from 'pattern_id' if needed)
    - 'category' field exists
    """
    # Ensure 'id' field exists
    if "id" not in entry and "pattern_id" in entry:
        entry["id"] = entry["pattern_id"]

    # Ensure 'category' field exists
    if "category" not in entry:
        entry["category"] = "flowise"

    return entry


def normalize_issue_entry(entry: dict) -> dict:
    """Normalize an issue entry to ensure consistent schema.

    Ensures:
    - 'id' field exists (copied from 'issue_id' if needed)
    - 'category' field exists
    - 'severity' is uppercase
    """
    # Ensure 'id' field exists
    if "id" not in entry and "issue_id" in entry:
        entry["id"] = entry["issue_id"]

    # Ensure 'category' field exists
    if "category" not in entry:
        entry["category"] = "flowise"

    # Ensure 'severity' is uppercase
    if "severity" in entry and isinstance(entry["severity"], str):
        entry["severity"] = entry["severity"].upper()

    return entry


def bootstrap_flowise_patterns():
    """Bootstrap Flowise patterns into global pattern files"""

    print("=" * 70)
    print("Bootstrap Flowise Patterns")
    print("=" * 70)

    # Load pattern file
    patterns_file = (
        cf_root / "extensions" / "flowise" / "patterns" / "flowise-expertise.json"
    )

    if not patterns_file.exists():
        print(f"Error: Pattern file not found: {patterns_file}")
        return False

    print(f"\nLoading patterns from: {patterns_file}")

    try:
        with open(patterns_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in pattern file: {e}")
        return False

    # Load existing global patterns
    global_pattern_dir = Path.home() / ".context-foundry" / "patterns"
    global_pattern_dir.mkdir(parents=True, exist_ok=True)

    print(f"Pattern directory: {global_pattern_dir}")

    new_count = 0
    updated_count = 0
    # Bootstrap patterns -> architecture-patterns.json
    print("\nImporting patterns...")

    # Load existing architecture patterns
    arch_result = read_global_patterns_impl("architecture-patterns")
    if arch_result.get("status") == "success":
        arch_patterns = arch_result.get("data", {})
    else:
        arch_patterns = {
            "patterns": [],
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
        }

    # Normalize all existing entries and build index
    # Use both 'id' and 'pattern_id' to find existing entries
    existing_by_id = {}
    for i, p in enumerate(arch_patterns.get("patterns", [])):
        # Normalize the entry
        arch_patterns["patterns"][i] = normalize_pattern_entry(p)

        # Index by id (which may have come from pattern_id)
        entry_id = arch_patterns["patterns"][i].get("id")
        if entry_id:
            existing_by_id[entry_id] = i

    for pattern in data.get("patterns", []):
        pattern_id = pattern.get("pattern_id")
        if not pattern_id:
            print("Warning: Pattern missing pattern_id, skipping")
            continue

        # Convert to global pattern format
        global_pattern = {
            "id": pattern_id,
            "pattern_id": pattern_id,  # Keep for backward compatibility
            "title": pattern.get("description", pattern_id),
            "description": pattern.get("description", ""),
            "category": "flowise",
            "project_types": pattern.get("applies_to", ["flowise-agentflow"]),
            "tags": ["flowise"] + pattern.get("category", "").split(),
            "confidence": pattern.get("confidence", 0.9),
            "frequency": pattern.get("frequency", 1),
            "last_seen": datetime.now().isoformat(),
            "metadata": pattern,
        }

        if pattern_id in existing_by_id:
            # Update existing - also normalize schema
            idx = existing_by_id[pattern_id]
            existing = arch_patterns["patterns"][idx]

            # Merge: keep existing frequency, update schema
            global_pattern["frequency"] = existing.get("frequency", 0) + 1
            arch_patterns["patterns"][idx] = global_pattern

            updated_count += 1
            print(f"  ✓ Updated: {pattern_id}")
        else:
            # Add new
            arch_patterns["patterns"].append(global_pattern)
            new_count += 1
            print(f"  + Added: {pattern_id}")

    # Save architecture patterns
    arch_patterns["last_updated"] = datetime.now().isoformat()
    save_global_patterns_impl("architecture-patterns", arch_patterns)

    # Bootstrap common issues -> common-issues.json
    print("\nImporting common issues...")

    # Load existing common issues
    issues_result = read_global_patterns_impl("common-issues")
    if issues_result.get("status") == "success":
        common_issues = issues_result.get("data", {})
    else:
        common_issues = {
            "patterns": [],
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "total_builds": 0,
        }

    # Normalize all existing entries and build index
    existing_by_id = {}
    for i, p in enumerate(common_issues.get("patterns", [])):
        # Normalize the entry
        common_issues["patterns"][i] = normalize_issue_entry(p)

        # Index by id (which may have come from issue_id or title)
        entry_id = common_issues["patterns"][i].get("id")
        if entry_id:
            existing_by_id[entry_id] = i

    for issue in data.get("common_issues", []):
        issue_id = issue.get("issue_id")
        if not issue_id:
            print("Warning: Issue missing issue_id, skipping")
            continue

        # Convert to global issue format
        global_issue = {
            "id": issue_id,
            "issue_id": issue_id,  # Keep for backward compatibility
            "title": issue.get("description", issue_id),
            "description": issue.get("description", ""),
            "error_message": issue.get("description", ""),
            "severity": issue.get("severity", "MEDIUM").upper(),
            "category": "flowise",
            "project_types": ["flowise-agentflow"],
            "tech_stack": ["flowise"],
            "tags": ["flowise", issue.get("category", "")],
            "confidence": issue.get("confidence", 0.9),
            "frequency": issue.get("frequency", 1),
            "last_seen": datetime.now().isoformat(),
            "solution": issue.get("solution", {}),
            "metadata": issue,
        }

        if issue_id in existing_by_id:
            # Update existing - also normalize schema
            idx = existing_by_id[issue_id]
            existing = common_issues["patterns"][idx]

            # Merge: keep existing frequency, update schema
            global_issue["frequency"] = existing.get("frequency", 0) + 1
            common_issues["patterns"][idx] = global_issue

            updated_count += 1
            print(f"  ✓ Updated: {issue_id}")
        else:
            # Add new
            common_issues["patterns"].append(global_issue)
            new_count += 1
            print(f"  + Added: {issue_id}")

    # Save common issues
    common_issues["last_updated"] = datetime.now().isoformat()
    save_global_patterns_impl("common-issues", common_issues)

    # Summary
    print("\n" + "=" * 70)
    print("✅ Bootstrap complete!")
    print(f"   New entries: {new_count}")
    print(f"   Updated entries: {updated_count}")
    print(f"   Pattern files: {global_pattern_dir}")
    print("=" * 70)

    return True


if __name__ == "__main__":
    # Check for --force-merge flag
    if "--force-merge" not in sys.argv:
        print("\n" + "=" * 70)
        print("⚠️  WARNING: PATTERN ISOLATION MODEL")
        print("=" * 70)
        print("\nExtension patterns should stay ISOLATED in their own directories.")
        print("Merging extension patterns into global storage causes:")
        print("  - Context bloat (140KB+ of irrelevant patterns)")
        print("  - Cross-contamination (Flowise patterns in Python builds)")
        print("  - Token waste (99%+ bloat in some cases)")
        print("\nNew pattern model:")
        print("  ✅ Flowise builds → read extensions/flowise/patterns/")
        print("  ✅ Roblox builds → read extensions/roblox/patterns/")
        print("  ✅ General builds → read ~/.context-foundry/patterns/")
        print("\nIf you REALLY want to merge (not recommended), run:")
        print("  python scripts/bootstrap_flowise_patterns.py --force-merge")
        print("=" * 70)
        sys.exit(1)

    success = bootstrap_flowise_patterns()
    sys.exit(0 if success else 1)

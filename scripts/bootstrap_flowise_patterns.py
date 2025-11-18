#!/usr/bin/env python3
"""
Bootstrap Flowise Patterns into Global Codex

This script loads patterns from extensions/flowise/patterns/flowise-expertise.json
and imports them into the global Context Foundry codex database.

Idempotent: Safe to re-run after pattern updates.

Usage:
    python scripts/bootstrap_flowise_patterns.py
"""

import sys
import json
from pathlib import Path

# Add Context Foundry to path
cf_root = Path(__file__).parent.parent
sys.path.insert(0, str(cf_root))

try:
    from context_foundry.codex import (
        KnowledgeStore,
        KnowledgeEntry,
        KnowledgeType,
        Severity,
    )
except ImportError:
    print("Error: Could not import context_foundry.codex")
    print("Make sure Context Foundry is properly installed")
    sys.exit(1)


def bootstrap_flowise_patterns():
    """Bootstrap Flowise patterns into global codex"""

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

    # Initialize codex store
    codex_path = Path.home() / ".context-foundry" / "patterns" / "codex.db"
    print(f"Codex database: {codex_path}")

    try:
        store = KnowledgeStore(str(codex_path))
    except Exception as e:
        print(f"Error: Could not open codex database: {e}")
        return False

    new_count = 0
    updated_count = 0

    # Bootstrap patterns
    print("\nImporting patterns...")
    for pattern in data.get("patterns", []):
        pattern_id = pattern.get("pattern_id")
        if not pattern_id:
            print("Warning: Pattern missing pattern_id, skipping")
            continue

        # Check if exists
        existing = None
        try:
            existing = store.get_entry(pattern_id)
        except Exception:
            pass

        try:
            if existing:
                # Update existing
                store.update_entry(pattern_id, metadata=pattern)
                updated_count += 1
                print(f"  ✓ Updated: {pattern_id}")
            else:
                # Create new
                entry = KnowledgeEntry(
                    id=pattern_id,
                    type=KnowledgeType.PATTERN,
                    category="flowise",
                    title=pattern.get("description", pattern_id),
                    description=pattern.get("description", ""),
                    project_types=pattern.get("applies_to", ["flowise-agentflow"]),
                    tags=["flowise"] + pattern.get("category", "").split(),
                    confidence=pattern.get("confidence", 0.9),
                    frequency=pattern.get("frequency", 1),
                    metadata=pattern,
                )
                store.add_entry(entry)
                new_count += 1
                print(f"  + Added: {pattern_id}")
        except Exception as e:
            print(f"  ✗ Error with {pattern_id}: {e}")

    # Bootstrap common issues
    print("\nImporting common issues...")
    for issue in data.get("common_issues", []):
        issue_id = issue.get("issue_id")
        if not issue_id:
            print("Warning: Issue missing issue_id, skipping")
            continue

        # Check if exists
        existing = None
        try:
            existing = store.get_entry(issue_id)
        except Exception:
            pass

        try:
            if existing:
                # Update existing
                store.update_entry(issue_id, metadata=issue)
                updated_count += 1
                print(f"  ✓ Updated: {issue_id}")
            else:
                # Create new
                severity_map = {
                    "LOW": Severity.LOW,
                    "MEDIUM": Severity.MEDIUM,
                    "HIGH": Severity.HIGH,
                    "CRITICAL": Severity.CRITICAL,
                }
                severity = severity_map.get(
                    issue.get("severity", "MEDIUM"), Severity.MEDIUM
                )

                entry = KnowledgeEntry(
                    id=issue_id,
                    type=KnowledgeType.ISSUE,
                    category="flowise",
                    title=issue.get("description", issue_id),
                    description=issue.get("description", ""),
                    severity=severity,
                    project_types=["flowise-agentflow"],
                    tags=["flowise"] + [issue.get("category", "")],
                    confidence=issue.get("confidence", 0.9),
                    frequency=issue.get("frequency", 1),
                    metadata=issue,
                )
                store.add_entry(entry)
                new_count += 1
                print(f"  + Added: {issue_id}")
        except Exception as e:
            print(f"  ✗ Error with {issue_id}: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("✅ Bootstrap complete!")
    print(f"   New entries: {new_count}")
    print(f"   Updated entries: {updated_count}")
    print("   Category: flowise")
    print("=" * 70)

    return True


if __name__ == "__main__":
    success = bootstrap_flowise_patterns()
    sys.exit(0 if success else 1)

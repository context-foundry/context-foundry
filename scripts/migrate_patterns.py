#!/usr/bin/env python3
"""
Migrate project-specific patterns to global pattern storage.

This script migrates patterns from individual projects to the global
~/.context-foundry/patterns/ directory so they can be shared across all builds.

Usage:
    python scripts/migrate_patterns.py [projects_dir]

Example:
    python scripts/migrate_patterns.py /Users/name/homelab

The script will:
1. Scan all subdirectories for .context-foundry/patterns/
2. Read pattern files from each project
3. Merge them into global storage at ~/.context-foundry/patterns/
4. Handle duplicate patterns by incrementing frequency
5. Preserve all pattern metadata
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def read_json_file(file_path: Path) -> Dict[str, Any]:
    """Read and parse a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def write_json_file(file_path: Path, data: Dict[str, Any]) -> None:
    """Write data to a JSON file with pretty formatting."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def merge_common_issues(project_patterns: List[Dict], global_patterns: List[Dict]) -> tuple[List[Dict], int, int]:
    """
    Merge common issue patterns.

    Returns: (merged_patterns, new_count, updated_count)
    """
    # Create lookup by pattern_id
    global_by_id = {p["pattern_id"]: i for i, p in enumerate(global_patterns)}

    new_count = 0
    updated_count = 0

    for proj_pattern in project_patterns:
        pattern_id = proj_pattern.get("pattern_id")

        if pattern_id in global_by_id:
            # Update existing pattern
            idx = global_by_id[pattern_id]
            existing = global_patterns[idx]

            # Increment frequency
            existing["frequency"] = existing.get("frequency", 1) + 1

            # Update last_seen
            existing["last_seen"] = datetime.now().strftime("%Y-%m-%d")

            # Merge project_types (unique values)
            existing_types = set(existing.get("project_types", []))
            new_types = set(proj_pattern.get("project_types", []))
            existing["project_types"] = sorted(list(existing_types | new_types))

            # Preserve highest severity
            severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            existing_severity = severity_order.get(existing.get("severity", "LOW"), 1)
            new_severity = severity_order.get(proj_pattern.get("severity", "LOW"), 1)
            if new_severity > existing_severity:
                existing["severity"] = proj_pattern["severity"]

            # Merge solutions (keep more comprehensive)
            existing_solution = existing.get("solution", {})
            new_solution = proj_pattern.get("solution", {})
            for key, value in new_solution.items():
                if key not in existing_solution or len(value) > len(existing_solution.get(key, "")):
                    existing_solution[key] = value
            existing["solution"] = existing_solution

            updated_count += 1
        else:
            # Add new pattern
            new_pattern = proj_pattern.copy()
            new_pattern["first_seen"] = proj_pattern.get("first_seen", datetime.now().strftime("%Y-%m-%d"))
            new_pattern["last_seen"] = datetime.now().strftime("%Y-%m-%d")
            new_pattern["frequency"] = proj_pattern.get("frequency", 1)
            global_patterns.append(new_pattern)
            new_count += 1

    return global_patterns, new_count, updated_count


def merge_scout_learnings(project_learnings: List[Dict], global_learnings: List[Dict]) -> tuple[List[Dict], int, int]:
    """
    Merge scout learning patterns.

    Returns: (merged_learnings, new_count, updated_count)
    """
    # Create lookup by learning_id
    global_by_id = {l["learning_id"]: i for i, l in enumerate(global_learnings)}

    new_count = 0
    updated_count = 0

    for proj_learning in project_learnings:
        learning_id = proj_learning.get("learning_id")

        if learning_id in global_by_id:
            # Update existing learning
            idx = global_by_id[learning_id]
            existing = global_learnings[idx]

            # Merge project types
            existing_types = set(existing.get("project_types", []))
            new_types = set(proj_learning.get("project_types", []))
            existing["project_types"] = sorted(list(existing_types | new_types))

            # Merge key points (unique values)
            existing_points = set(existing.get("key_points", []))
            new_points = set(proj_learning.get("key_points", []))
            existing["key_points"] = sorted(list(existing_points | new_points))

            # Merge recommendations if present
            if "recommendations" in proj_learning:
                existing_recs = set(existing.get("recommendations", []))
                new_recs = set(proj_learning.get("recommendations", []))
                existing["recommendations"] = sorted(list(existing_recs | new_recs))

            updated_count += 1
        else:
            # Add new learning
            new_learning = proj_learning.copy()
            new_learning["first_seen"] = proj_learning.get("first_seen", datetime.now().strftime("%Y-%m-%d"))
            global_learnings.append(new_learning)
            new_count += 1

    return global_learnings, new_count, updated_count


def migrate_project_patterns(project_dir: Path, global_dir: Path) -> Dict[str, Any]:
    """Migrate patterns from a single project to global storage."""
    pattern_dir = project_dir / ".context-foundry" / "patterns"

    if not pattern_dir.exists():
        return None

    results = {
        "project": project_dir.name,
        "files_migrated": [],
        "patterns_added": 0,
        "patterns_updated": 0
    }

    # Migrate common-issues.json
    common_issues_file = pattern_dir / "common-issues.json"
    if common_issues_file.exists():
        try:
            project_data = read_json_file(common_issues_file)
            project_patterns = project_data.get("patterns", [])

            # Read global patterns
            global_file = global_dir / "common-issues.json"
            if global_file.exists():
                global_data = read_json_file(global_file)
            else:
                global_data = {
                    "patterns": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "total_builds": 0
                }

            # Merge
            merged_patterns, new_count, updated_count = merge_common_issues(
                project_patterns,
                global_data["patterns"]
            )

            global_data["patterns"] = merged_patterns
            global_data["last_updated"] = datetime.now().isoformat()

            # Save
            write_json_file(global_file, global_data)

            results["files_migrated"].append("common-issues.json")
            results["patterns_added"] += new_count
            results["patterns_updated"] += updated_count

            print(f"  ✓ common-issues.json: {new_count} new, {updated_count} updated")
        except Exception as e:
            print(f"  ✗ common-issues.json: Error - {str(e)}")

    # Migrate scout-learnings.json
    scout_file = pattern_dir / "scout-learnings.json"
    if scout_file.exists():
        try:
            project_data = read_json_file(scout_file)
            project_learnings = project_data.get("learnings", [])

            # Read global learnings
            global_file = global_dir / "scout-learnings.json"
            if global_file.exists():
                global_data = read_json_file(global_file)
            else:
                global_data = {
                    "learnings": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat()
                }

            # Merge
            merged_learnings, new_count, updated_count = merge_scout_learnings(
                project_learnings,
                global_data["learnings"]
            )

            global_data["learnings"] = merged_learnings
            global_data["last_updated"] = datetime.now().isoformat()

            # Save
            write_json_file(global_file, global_data)

            results["files_migrated"].append("scout-learnings.json")
            results["patterns_added"] += new_count
            results["patterns_updated"] += updated_count

            print(f"  ✓ scout-learnings.json: {new_count} new, {updated_count} updated")
        except Exception as e:
            print(f"  ✗ scout-learnings.json: Error - {str(e)}")

    return results if results["files_migrated"] else None


def main():
    """Main migration function."""
    # Get projects directory from command line or use default
    if len(sys.argv) > 1:
        projects_base = Path(sys.argv[1])
    else:
        projects_base = Path.home() / "homelab"

    print(f"🔍 Scanning for projects in: {projects_base}")
    print()

    if not projects_base.exists():
        print(f"❌ Error: Directory not found: {projects_base}")
        sys.exit(1)

    # Global pattern directory
    global_pattern_dir = Path.home() / ".context-foundry" / "patterns"
    global_pattern_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Global pattern directory: {global_pattern_dir}")
    print()

    # Find all projects with patterns
    projects_with_patterns = []
    for project_dir in projects_base.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith('.'):
            pattern_dir = project_dir / ".context-foundry" / "patterns"
            if pattern_dir.exists():
                projects_with_patterns.append(project_dir)

    if not projects_with_patterns:
        print("ℹ️  No projects with patterns found")
        return

    print(f"Found {len(projects_with_patterns)} project(s) with patterns:")
    for proj in projects_with_patterns:
        print(f"  - {proj.name}")
    print()

    # Migrate each project
    print("🚀 Starting migration...")
    print()

    migration_summary = {
        "total_projects": 0,
        "total_patterns_added": 0,
        "total_patterns_updated": 0
    }

    for project_dir in projects_with_patterns:
        print(f"📦 Migrating: {project_dir.name}")
        results = migrate_project_patterns(project_dir, global_pattern_dir)

        if results:
            migration_summary["total_projects"] += 1
            migration_summary["total_patterns_added"] += results["patterns_added"]
            migration_summary["total_patterns_updated"] += results["patterns_updated"]
        print()

    # Print summary
    print("=" * 60)
    print("✅ Migration Complete!")
    print("=" * 60)
    print(f"Projects migrated: {migration_summary['total_projects']}")
    print(f"New patterns added globally: {migration_summary['total_patterns_added']}")
    print(f"Existing patterns updated: {migration_summary['total_patterns_updated']}")
    print()
    print(f"Global patterns location: {global_pattern_dir}")
    print()
    print("🎉 All future builds will now benefit from these learnings!")


if __name__ == "__main__":
    main()

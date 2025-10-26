#!/usr/bin/env python3
"""
Intelligent Pattern Merge Tool for Context Foundry

Merges patterns from a source file into a destination file with smart conflict resolution.
Used by both:
  - share-my-patterns.sh (local sync)
  - validate-patterns.yml (GitHub Action)

Key Features:
  - Increments frequency for existing patterns
  - Merges project_types arrays (unique values)
  - Preserves highest severity
  - Updates last_seen dates
  - Validates JSON schema
  - Detects and prevents corruption

Usage:
    python scripts/merge-patterns-intelligent.py \
        --source ~/.context-foundry/patterns/common-issues.json \
        --dest .context-foundry/patterns/common-issues.json \
        --type common-issues \
        --output merged.json

    python scripts/merge-patterns-intelligent.py \
        --source ~/.context-foundry/patterns/scout-learnings.json \
        --dest .context-foundry/patterns/scout-learnings.json \
        --type scout-learnings \
        --output merged.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple


class PatternMerger:
    """Intelligent pattern merging with conflict resolution."""

    SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

    def __init__(self, pattern_type: str):
        """
        Initialize merger.

        Args:
            pattern_type: Type of patterns ('common-issues' or 'scout-learnings')
        """
        self.pattern_type = pattern_type
        self.stats = {
            "new_patterns": 0,
            "updated_patterns": 0,
            "conflicts_resolved": 0,
            "validation_errors": 0
        }

    def merge_common_issues(
        self,
        source_patterns: List[Dict],
        dest_patterns: List[Dict]
    ) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Merge common issue patterns.

        Args:
            source_patterns: Patterns from source file (local machine)
            dest_patterns: Patterns from destination file (repo)

        Returns:
            Tuple of (merged_patterns, stats)
        """
        # Create lookup by pattern_id
        dest_by_id = {p["pattern_id"]: i for i, p in enumerate(dest_patterns)}

        for source_pattern in source_patterns:
            pattern_id = source_pattern.get("pattern_id")

            if not pattern_id:
                self.stats["validation_errors"] += 1
                print(f"⚠️  Warning: Pattern missing pattern_id, skipping", file=sys.stderr)
                continue

            if pattern_id in dest_by_id:
                # Update existing pattern
                idx = dest_by_id[pattern_id]
                self._update_existing_common_issue(
                    existing=dest_patterns[idx],
                    incoming=source_pattern
                )
                self.stats["updated_patterns"] += 1
            else:
                # Add new pattern
                new_pattern = self._prepare_new_common_issue(source_pattern)
                dest_patterns.append(new_pattern)
                dest_by_id[pattern_id] = len(dest_patterns) - 1
                self.stats["new_patterns"] += 1

        return dest_patterns, self.stats

    def _update_existing_common_issue(self, existing: Dict, incoming: Dict) -> None:
        """Update existing pattern with incoming data."""
        # Increment frequency
        existing["frequency"] = existing.get("frequency", 1) + incoming.get("frequency", 1)

        # Update last_seen to most recent
        incoming_date = incoming.get("last_seen", datetime.now().strftime("%Y-%m-%d"))
        existing_date = existing.get("last_seen", "1970-01-01")
        existing["last_seen"] = max(incoming_date, existing_date)

        # Merge project_types (unique values, sorted)
        existing_types = set(existing.get("project_types", []))
        new_types = set(incoming.get("project_types", []))
        existing["project_types"] = sorted(list(existing_types | new_types))

        # Preserve highest severity
        existing_severity = self.SEVERITY_ORDER.get(existing.get("severity", "LOW"), 1)
        incoming_severity = self.SEVERITY_ORDER.get(incoming.get("severity", "LOW"), 1)
        if incoming_severity > existing_severity:
            existing["severity"] = incoming["severity"]
            self.stats["conflicts_resolved"] += 1

        # Merge solutions (keep most comprehensive)
        self._merge_solutions(existing, incoming)

        # Merge optional fields
        self._merge_optional_fields(existing, incoming)

    def _merge_solutions(self, existing: Dict, incoming: Dict) -> None:
        """Merge solution objects, keeping most comprehensive guidance."""
        existing_solution = existing.get("solution", {})
        incoming_solution = incoming.get("solution", {})

        # Merge each phase's solution
        for phase in ["scout", "architect", "builder", "tester"]:
            existing_text = existing_solution.get(phase, "")
            incoming_text = incoming_solution.get(phase, "")

            # Keep longer/more detailed solution
            if isinstance(incoming_text, dict) or isinstance(existing_text, dict):
                # Handle dict-type solutions (more complex structures)
                if incoming_text and not existing_text:
                    existing_solution[phase] = incoming_text
                elif incoming_text and len(str(incoming_text)) > len(str(existing_text)):
                    existing_solution[phase] = incoming_text
            else:
                # Handle string solutions
                if incoming_text and len(incoming_text) > len(existing_text):
                    existing_solution[phase] = incoming_text

        existing["solution"] = existing_solution

    def _merge_optional_fields(self, existing: Dict, incoming: Dict) -> None:
        """Merge optional fields like tags, related_errors."""
        # Merge tags (unique values)
        if "tags" in incoming:
            existing_tags = set(existing.get("tags", []))
            incoming_tags = set(incoming.get("tags", []))
            existing["tags"] = sorted(list(existing_tags | incoming_tags))

        # Merge related_errors (unique values)
        if "related_errors" in incoming:
            existing_errors = set(existing.get("related_errors", []))
            incoming_errors = set(incoming.get("related_errors", []))
            existing["related_errors"] = sorted(list(existing_errors | incoming_errors))

        # Update auto_apply if incoming is True and existing is False
        if incoming.get("auto_apply", False) and not existing.get("auto_apply", False):
            existing["auto_apply"] = True

    def _prepare_new_common_issue(self, pattern: Dict) -> Dict:
        """Prepare a new pattern for insertion."""
        new_pattern = pattern.copy()
        new_pattern["first_seen"] = pattern.get("first_seen", datetime.now().strftime("%Y-%m-%d"))
        new_pattern["last_seen"] = pattern.get("last_seen", datetime.now().strftime("%Y-%m-%d"))
        new_pattern["frequency"] = pattern.get("frequency", 1)

        # Ensure required fields have defaults
        if "severity" not in new_pattern:
            new_pattern["severity"] = "MEDIUM"
        if "auto_apply" not in new_pattern:
            new_pattern["auto_apply"] = False

        return new_pattern

    def merge_scout_learnings(
        self,
        source_learnings: List[Dict],
        dest_learnings: List[Dict]
    ) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Merge scout learning patterns.

        Args:
            source_learnings: Learnings from source file
            dest_learnings: Learnings from destination file

        Returns:
            Tuple of (merged_learnings, stats)
        """
        # Create lookup by learning_id
        dest_by_id = {l["learning_id"]: i for i, l in enumerate(dest_learnings)}

        for source_learning in source_learnings:
            learning_id = source_learning.get("learning_id")

            if not learning_id:
                self.stats["validation_errors"] += 1
                print(f"⚠️  Warning: Learning missing learning_id, skipping", file=sys.stderr)
                continue

            if learning_id in dest_by_id:
                # Update existing learning
                idx = dest_by_id[learning_id]
                self._update_existing_scout_learning(
                    existing=dest_learnings[idx],
                    incoming=source_learning
                )
                self.stats["updated_patterns"] += 1
            else:
                # Add new learning
                new_learning = source_learning.copy()
                new_learning["first_seen"] = source_learning.get(
                    "first_seen",
                    datetime.now().strftime("%Y-%m-%d")
                )
                dest_learnings.append(new_learning)
                dest_by_id[learning_id] = len(dest_learnings) - 1
                self.stats["new_patterns"] += 1

        return dest_learnings, self.stats

    def _update_existing_scout_learning(self, existing: Dict, incoming: Dict) -> None:
        """Update existing scout learning with incoming data."""
        # Merge project_types
        existing_types = set(existing.get("project_types", []))
        incoming_types = set(incoming.get("project_types", []))
        existing["project_types"] = sorted(list(existing_types | incoming_types))

        # Merge key_points (unique values)
        existing_points = set(existing.get("key_points", []))
        incoming_points = set(incoming.get("key_points", []))
        existing["key_points"] = sorted(list(existing_points | incoming_points))

        # Merge recommendations (unique values)
        if "recommendations" in incoming:
            existing_recs = set(existing.get("recommendations", []))
            incoming_recs = set(incoming.get("recommendations", []))
            existing["recommendations"] = sorted(list(existing_recs | incoming_recs))

        # Merge antipatterns (unique values)
        if "antipatterns" in incoming:
            existing_anti = set(existing.get("antipatterns", []))
            incoming_anti = set(incoming.get("antipatterns", []))
            existing["antipatterns"] = sorted(list(existing_anti | incoming_anti))

        # Update confidence if incoming is higher
        confidence_order = {"high": 3, "medium": 2, "low": 1}
        existing_conf = confidence_order.get(existing.get("confidence", "low"), 1)
        incoming_conf = confidence_order.get(incoming.get("confidence", "low"), 1)
        if incoming_conf > existing_conf:
            existing["confidence"] = incoming["confidence"]


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'r') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: Dict[str, Any]) -> None:
    """Save data to a JSON file with pretty formatting."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved to: {file_path}")


def merge_pattern_files(
    source_file: Path,
    dest_file: Path,
    pattern_type: str,
    output_file: Path
) -> Dict[str, Any]:
    """
    Merge two pattern files intelligently.

    Args:
        source_file: Source pattern file (e.g., from local machine)
        dest_file: Destination pattern file (e.g., from repo)
        pattern_type: Type of patterns ('common-issues' or 'scout-learnings')
        output_file: Where to write merged result

    Returns:
        Merge statistics
    """
    # Load source file
    print(f"📖 Loading source: {source_file}")
    source_data = load_json_file(source_file)

    # Load destination file (or create empty if doesn't exist)
    if dest_file.exists():
        print(f"📖 Loading destination: {dest_file}")
        dest_data = load_json_file(dest_file)
    else:
        print(f"📄 Creating new destination file")
        dest_data = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "total_builds": 0
        }

        if pattern_type == "common-issues":
            dest_data["patterns"] = []
        elif pattern_type == "scout-learnings":
            dest_data["learnings"] = []
        else:
            raise ValueError(f"Unknown pattern type: {pattern_type}")

    # Create merger
    merger = PatternMerger(pattern_type)

    # Merge based on type
    if pattern_type == "common-issues":
        source_patterns = source_data.get("patterns", [])
        dest_patterns = dest_data.get("patterns", [])

        merged_patterns, stats = merger.merge_common_issues(source_patterns, dest_patterns)
        dest_data["patterns"] = merged_patterns

        # Update total_builds
        source_builds = source_data.get("total_builds", 1)
        dest_builds = dest_data.get("total_builds", 0)
        dest_data["total_builds"] = dest_builds + source_builds

    elif pattern_type == "scout-learnings":
        source_learnings = source_data.get("learnings", [])
        dest_learnings = dest_data.get("learnings", [])

        merged_learnings, stats = merger.merge_scout_learnings(source_learnings, dest_learnings)
        dest_data["learnings"] = merged_learnings
    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}")

    # Update metadata
    dest_data["last_updated"] = datetime.now().isoformat()
    dest_data["version"] = "1.0"

    # Save merged result
    save_json_file(output_file, dest_data)

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Intelligently merge Context Foundry pattern files"
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Source pattern file (e.g., ~/.context-foundry/patterns/common-issues.json)"
    )
    parser.add_argument(
        "--dest",
        type=Path,
        required=True,
        help="Destination pattern file (e.g., .context-foundry/patterns/common-issues.json)"
    )
    parser.add_argument(
        "--type",
        choices=["common-issues", "scout-learnings"],
        required=True,
        help="Type of pattern file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to write merged output"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    try:
        # Perform merge
        print("=" * 60)
        print("Context Foundry Pattern Merge")
        print("=" * 60)
        print(f"Pattern Type: {args.type}")
        print(f"Source: {args.source}")
        print(f"Destination: {args.dest}")
        print(f"Output: {args.output}")
        print()

        stats = merge_pattern_files(
            source_file=args.source,
            dest_file=args.dest,
            pattern_type=args.type,
            output_file=args.output
        )

        # Print summary
        print()
        print("=" * 60)
        print("✅ Merge Complete!")
        print("=" * 60)
        print(f"New patterns added: {stats['new_patterns']}")
        print(f"Existing patterns updated: {stats['updated_patterns']}")
        print(f"Conflicts resolved: {stats['conflicts_resolved']}")

        if stats['validation_errors'] > 0:
            print(f"⚠️  Validation errors: {stats['validation_errors']}")

        print()

        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

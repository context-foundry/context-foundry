"""Pattern management utilities for Context Foundry MCP server.

Handles reading, writing, and merging of global pattern storage across builds.
"""

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def read_global_patterns_impl(pattern_type: str = "common-issues") -> Dict[str, Any]:
    """
    Read global patterns from ~/.context-foundry/patterns/.

    Args:
        pattern_type: Type of patterns to read (common-issues, scout-learnings,
                     build-metrics, architecture-patterns, test-patterns,
                     mcp-server-patterns)

    Returns:
        Dictionary with status, data, file_path, and last_updated
    """
    try:
        # Global pattern directory
        global_pattern_dir = Path.home() / ".context-foundry" / "patterns"

        # Pattern file mapping
        pattern_files = {
            "common-issues": "common-issues.json",
            "scout-learnings": "scout-learnings.json",
            "build-metrics": "build-metrics.json",
            "architecture-patterns": "architecture-patterns.json",
            "test-patterns": "test-patterns.json",
            "mcp-server-patterns": "mcp-server-patterns.json",
        }

        if pattern_type not in pattern_files:
            return {
                "status": "error",
                "error": f"Invalid pattern_type: {pattern_type}",
                "valid_types": list(pattern_files.keys()),
            }

        pattern_file = global_pattern_dir / pattern_files[pattern_type]

        # Create directory if it doesn't exist
        if not global_pattern_dir.exists():
            global_pattern_dir.mkdir(parents=True, exist_ok=True)

        # If file doesn't exist, return empty structure
        if not pattern_file.exists():
            if pattern_type == "common-issues":
                default_data = {
                    "patterns": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "total_builds": 0,
                }
            elif pattern_type == "scout-learnings":
                default_data = {
                    "learnings": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                }
            elif pattern_type == "build-metrics":
                default_data = {
                    "metrics": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                }
            else:
                default_data = {
                    "patterns": [],
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                }

            return {
                "status": "success",
                "message": f"No existing {pattern_type} found, returning empty structure",
                "data": default_data,
                "file_path": str(pattern_file),
            }

        # Read existing patterns
        with open(pattern_file, "r") as f:
            data = json.load(f)

        return {
            "status": "success",
            "data": data,
            "file_path": str(pattern_file),
            "last_updated": data.get("last_updated", "unknown"),
        }

    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "error": f"Invalid JSON in pattern file: {str(e)}",
            "file_path": str(pattern_file),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


def save_global_patterns_impl(
    pattern_type: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Save global patterns to ~/.context-foundry/patterns/.

    Args:
        pattern_type: Type of patterns (common-issues, scout-learnings, etc.)
        data: Pattern data as dictionary

    Returns:
        Dictionary with status, message, file_path, and last_updated
    """
    try:
        # Global pattern directory
        global_pattern_dir = Path.home() / ".context-foundry" / "patterns"
        global_pattern_dir.mkdir(parents=True, exist_ok=True)

        # Pattern file mapping
        pattern_files = {
            "common-issues": "common-issues.json",
            "scout-learnings": "scout-learnings.json",
            "build-metrics": "build-metrics.json",
            "architecture-patterns": "architecture-patterns.json",
            "test-patterns": "test-patterns.json",
            "mcp-server-patterns": "mcp-server-patterns.json",
        }

        if pattern_type not in pattern_files:
            return {
                "status": "error",
                "error": f"Invalid pattern_type: {pattern_type}",
                "valid_types": list(pattern_files.keys()),
            }

        pattern_file = global_pattern_dir / pattern_files[pattern_type]

        # Update last_updated timestamp
        data["last_updated"] = datetime.now().isoformat()

        # Write to file
        with open(pattern_file, "w") as f:
            json.dump(data, f, indent=2)

        # Get count of items
        if pattern_type == "common-issues":
            count = len(data.get("patterns", []))
        elif pattern_type == "scout-learnings":
            count = len(data.get("learnings", []))
        elif pattern_type == "build-metrics":
            count = len(data.get("metrics", []))
        else:
            count = 0

        return {
            "status": "success",
            "message": f"Saved {count} {pattern_type} to global storage",
            "pattern_file": str(pattern_file),  # Match expected test schema
            "last_updated": data["last_updated"],
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


def merge_project_patterns_impl(
    project_pattern_file: str,
    pattern_type: str = "common-issues",
    increment_build_count: bool = True,
) -> Dict[str, Any]:
    """
    Merge project-specific patterns into global storage.

    Args:
        project_pattern_file: Path to project-specific pattern file
        pattern_type: Type of patterns (common-issues, scout-learnings, etc.)
        increment_build_count: Whether to increment total_builds counter

    Returns:
        Dictionary with status, message, merge_stats, global_file, and project_file
    """
    try:
        # Read project patterns
        project_file_path = Path(project_pattern_file)
        if not project_file_path.exists():
            return {
                "status": "error",
                "error": f"Project pattern file not found: {project_pattern_file}",
            }

        with open(project_file_path, "r") as f:
            project_data = json.load(f)

        # Read global patterns
        global_response = read_global_patterns_impl(pattern_type)

        if global_response["status"] != "success":
            return {
                "status": "error",
                "error": "Failed to read global patterns",
                "details": global_response,
            }

        global_data = global_response["data"]

        # Merge logic
        merge_stats = {
            "new_patterns": 0,
            "updated_patterns": 0,
            "total_project_patterns": 0,
        }

        if pattern_type == "common-issues":
            # Get patterns arrays
            project_patterns = project_data.get("patterns", [])
            global_patterns = global_data.get("patterns", [])
            merge_stats["total_project_patterns"] = len(project_patterns)

            # Create lookup by pattern_id or id
            global_by_id = {}
            for i, p in enumerate(global_patterns):
                pid = p.get("pattern_id") or p.get("id")
                if pid:
                    global_by_id[pid] = i

            # Merge each project pattern
            for proj_pattern in project_patterns:
                pattern_id = proj_pattern.get("pattern_id") or proj_pattern.get("id")
                if not pattern_id:
                    continue

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
                    severity_order = {
                        "CRITICAL": 4,
                        "HIGH": 3,
                        "MEDIUM": 2,
                        "LOW": 1,
                        "critical": 4,
                        "high": 3,
                        "medium": 2,
                        "low": 1,
                    }
                    existing_severity = severity_order.get(
                        existing.get("severity", "LOW"), 1
                    )
                    new_severity = severity_order.get(
                        proj_pattern.get("severity", "LOW"), 1
                    )
                    if new_severity > existing_severity:
                        existing["severity"] = proj_pattern["severity"]

                    merge_stats["updated_patterns"] += 1
                else:
                    # Add new pattern
                    new_pattern = proj_pattern.copy()
                    new_pattern["first_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_pattern["last_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_pattern["frequency"] = new_pattern.get("frequency", 1)
                    global_patterns.append(new_pattern)
                    merge_stats["new_patterns"] += 1

            global_data["patterns"] = global_patterns

            # Increment build count
            if increment_build_count:
                global_data["total_builds"] = global_data.get("total_builds", 0) + 1

        elif pattern_type == "scout-learnings":
            # Similar logic for scout learnings
            project_learnings = project_data.get("learnings", [])
            global_learnings = global_data.get("learnings", [])
            merge_stats["total_project_patterns"] = len(project_learnings)

            # Create lookup by learning_id
            global_by_id = {
                learning.get("learning_id"): i
                for i, learning in enumerate(global_learnings)
                if learning.get("learning_id")
            }

            for proj_learning in project_learnings:
                learning_id = proj_learning.get("learning_id")
                if not learning_id:
                    continue

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

                    merge_stats["updated_patterns"] += 1
                else:
                    # Add new learning
                    new_learning = proj_learning.copy()
                    new_learning["first_seen"] = datetime.now().strftime("%Y-%m-%d")
                    global_learnings.append(new_learning)
                    merge_stats["new_patterns"] += 1

            global_data["learnings"] = global_learnings

        elif pattern_type == "build-metrics":
            # Build metrics use a "metrics" array instead of "patterns"
            project_metrics = project_data.get("metrics", [])
            global_metrics = global_data.get("metrics", [])
            merge_stats["total_project_patterns"] = len(project_metrics)

            # Create lookup by metric_id
            global_by_id = {}
            for i, m in enumerate(global_metrics):
                mid = m.get("metric_id")
                if mid:
                    global_by_id[mid] = i

            # Merge each project metric
            for proj_metric in project_metrics:
                metric_id = proj_metric.get("metric_id")
                if not metric_id:
                    continue

                if metric_id in global_by_id:
                    # Update existing metric (could increment counters, update averages, etc.)
                    idx = global_by_id[metric_id]
                    existing = global_metrics[idx]

                    # Simple merge: update timestamp and increment occurrence count
                    existing["last_seen"] = datetime.now().strftime("%Y-%m-%d")
                    existing["occurrence_count"] = (
                        existing.get("occurrence_count", 1) + 1
                    )

                    # Merge project_types
                    existing_types = set(existing.get("project_types", []))
                    new_types = set(proj_metric.get("project_types", []))
                    existing["project_types"] = sorted(list(existing_types | new_types))

                    merge_stats["updated_patterns"] += 1
                else:
                    # Add new metric
                    new_metric = proj_metric.copy()
                    new_metric["first_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_metric["last_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_metric["occurrence_count"] = new_metric.get(
                        "occurrence_count", 1
                    )
                    global_metrics.append(new_metric)
                    merge_stats["new_patterns"] += 1

            global_data["metrics"] = global_metrics

        elif pattern_type in [
            "architecture-patterns",
            "test-patterns",
            "mcp-server-patterns",
        ]:
            # These pattern types use the same structure as common-issues
            project_patterns = project_data.get("patterns", [])
            global_patterns = global_data.get("patterns", [])
            merge_stats["total_project_patterns"] = len(project_patterns)

            # Create lookup by pattern_id
            global_by_id = {}
            for i, p in enumerate(global_patterns):
                pid = p.get("pattern_id")
                if pid:
                    global_by_id[pid] = i

            # Merge each project pattern
            for proj_pattern in project_patterns:
                pattern_id = proj_pattern.get("pattern_id")
                if not pattern_id:
                    continue

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

                    # Preserve highest severity if present
                    if "severity" in existing or "severity" in proj_pattern:
                        severity_order = {
                            "CRITICAL": 4,
                            "HIGH": 3,
                            "MEDIUM": 2,
                            "LOW": 1,
                            "critical": 4,
                            "high": 3,
                            "medium": 2,
                            "low": 1,
                        }
                        existing_severity = severity_order.get(
                            existing.get("severity", "LOW"), 1
                        )
                        new_severity = severity_order.get(
                            proj_pattern.get("severity", "LOW"), 1
                        )
                        if new_severity > existing_severity:
                            existing["severity"] = proj_pattern["severity"]

                    merge_stats["updated_patterns"] += 1
                else:
                    # Add new pattern
                    new_pattern = proj_pattern.copy()
                    new_pattern["first_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_pattern["last_seen"] = datetime.now().strftime("%Y-%m-%d")
                    new_pattern["frequency"] = new_pattern.get("frequency", 1)
                    global_patterns.append(new_pattern)
                    merge_stats["new_patterns"] += 1

            global_data["patterns"] = global_patterns

        # Save merged patterns
        save_response = save_global_patterns_impl(pattern_type, global_data)

        if save_response["status"] != "success":
            return {
                "status": "error",
                "error": "Failed to save merged patterns",
                "details": save_response,
            }

        return {
            "status": "success",
            "message": f"Successfully merged {pattern_type} from project",
            "merge_stats": merge_stats,  # Keep nested for backward compatibility
            "global_file": save_response["pattern_file"],
            "project_file": str(project_file_path),
        }

    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "error": f"Invalid JSON in pattern file: {str(e)}",
            "file_path": project_pattern_file,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

"""Pattern management utilities for Context Foundry MCP server.

Handles reading, writing, and merging of global pattern storage across builds.
"""

import json
import logging
import os
import shutil
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_foundry.daemon.config import Config

logger = logging.getLogger(__name__)


def find_semantic_duplicate(
    new_pattern: Dict[str, Any],
    existing_patterns: List[Dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> Optional[int]:
    """
    Use Claude to find if a semantically equivalent pattern already exists.

    Instead of relying on exact ID matching (which fails because LLMs generate
    different IDs for the same concept), we ask Claude to compare the new pattern
    against existing ones and identify semantic duplicates.

    Args:
        new_pattern: The pattern being added
        existing_patterns: List of existing global patterns
        similarity_threshold: Not used directly, but kept for API compatibility

    Returns:
        Index of the matching pattern in existing_patterns, or None if no match
    """
    # Skip if no existing patterns to compare against
    if not existing_patterns:
        return None

    # Skip if Claude CLI not available
    if not shutil.which("claude"):
        logger.warning("Claude CLI not found, falling back to ID-only matching")
        return None

    # Extract key info from new pattern
    new_title = new_pattern.get("title", "")
    new_desc = new_pattern.get("description", "")
    new_problem = new_pattern.get("root_cause", "") or new_pattern.get("issue", {}).get(
        "description", ""
    )

    # Build a summary of existing patterns for Claude to compare against
    existing_summaries = []
    for i, p in enumerate(existing_patterns):
        title = p.get("title", "")
        desc = p.get("description", "")[:200]  # Truncate to save tokens
        pid = p.get("pattern_id") or p.get("id", f"pattern_{i}")
        existing_summaries.append(
            f"[{i}] ID: {pid}\n    Title: {title}\n    Description: {desc}..."
        )

    # Limit to 20 patterns to avoid context overflow
    if len(existing_summaries) > 20:
        existing_summaries = existing_summaries[:20]
        logger.info("Truncated to first 20 patterns for semantic comparison")

    existing_text = "\n\n".join(existing_summaries)

    prompt = f"""You are a pattern deduplication system. Determine if the NEW PATTERN below is semantically equivalent to any EXISTING PATTERN.

Two patterns are semantically equivalent if they describe the SAME underlying issue/solution, even if worded differently.

NEW PATTERN:
Title: {new_title}
Description: {new_desc}
Root Cause: {new_problem}

EXISTING PATTERNS:
{existing_text}

RESPOND WITH ONLY ONE OF:
- The index number (e.g., "3") if the new pattern matches an existing one
- "NONE" if the new pattern is genuinely new

Your response (just the number or NONE):"""

    try:
        # Call Claude CLI using the user's logged-in model
        # (No --model flag = uses default model for the subscription)
        cmd = ["claude", "--print", "--dangerously-skip-permissions", prompt]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        if result.returncode != 0:
            logger.warning(f"Claude semantic check failed: {result.stderr}")
            return None

        response = result.stdout.strip().upper()

        if response == "NONE":
            return None

        # Try to parse as integer index
        try:
            idx = int(response.strip())
            if 0 <= idx < len(existing_patterns):
                matched_id = existing_patterns[idx].get(
                    "pattern_id"
                ) or existing_patterns[idx].get("id")
                logger.info(
                    f"Semantic match found: new pattern matches existing '{matched_id}'"
                )
                return idx
        except ValueError:
            logger.warning(f"Unexpected response from semantic check: {response}")
            return None

    except subprocess.TimeoutExpired:
        logger.warning("Claude semantic check timed out")
        return None
    except Exception as e:
        logger.warning(f"Claude semantic check error: {e}")
        return None

    return None


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
            merge_stats["semantic_matches"] = 0  # Track semantic dedup hits

            # Create lookup by pattern_id or id
            global_by_id = {}
            for i, p in enumerate(global_patterns):
                pid = p.get("pattern_id") or p.get("id")
                if pid:
                    global_by_id[pid] = i

            # Helper to update an existing pattern
            def update_existing_pattern(
                existing: Dict, proj_pattern: Dict, is_semantic_match: bool = False
            ):
                """Update an existing pattern with new data."""
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

                # If semantic match, also merge any additional fields
                if is_semantic_match:
                    # Add alias ID to track that this pattern has multiple names
                    aliases = existing.get("aliases", [])
                    new_id = proj_pattern.get("pattern_id") or proj_pattern.get("id")
                    if new_id and new_id not in aliases:
                        aliases.append(new_id)
                        existing["aliases"] = aliases

            # Merge each project pattern
            for proj_pattern in project_patterns:
                pattern_id = proj_pattern.get("pattern_id") or proj_pattern.get("id")
                if not pattern_id:
                    continue

                # Step 1: Check for exact ID match (fast, no API call)
                if pattern_id in global_by_id:
                    idx = global_by_id[pattern_id]
                    update_existing_pattern(global_patterns[idx], proj_pattern)
                    merge_stats["updated_patterns"] += 1
                    continue

                # Step 2: Check for semantic duplicate (uses Claude Haiku)
                semantic_idx = find_semantic_duplicate(proj_pattern, global_patterns)
                if semantic_idx is not None:
                    # Found a semantic match - update that pattern instead of adding new
                    update_existing_pattern(
                        global_patterns[semantic_idx],
                        proj_pattern,
                        is_semantic_match=True,
                    )
                    merge_stats["updated_patterns"] += 1
                    merge_stats["semantic_matches"] += 1
                    logger.info(
                        f"Semantic dedup: '{pattern_id}' matched existing pattern "
                        f"'{global_patterns[semantic_idx].get('pattern_id') or global_patterns[semantic_idx].get('id')}'"
                    )
                    continue

                # Step 3: Truly new pattern - add it
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
            merge_stats["semantic_matches"] = 0  # Track semantic dedup hits

            # Create lookup by pattern_id
            global_by_id = {}
            for i, p in enumerate(global_patterns):
                pid = p.get("pattern_id") or p.get("id")
                if pid:
                    global_by_id[pid] = i

            # Helper to update an existing pattern
            def update_pattern(
                existing: Dict, proj_pattern: Dict, is_semantic_match: bool = False
            ):
                """Update an existing pattern with new data."""
                existing["frequency"] = existing.get("frequency", 1) + 1
                existing["last_seen"] = datetime.now().strftime("%Y-%m-%d")

                # Merge project_types
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

                # Track aliases for semantic matches
                if is_semantic_match:
                    aliases = existing.get("aliases", [])
                    new_id = proj_pattern.get("pattern_id") or proj_pattern.get("id")
                    if new_id and new_id not in aliases:
                        aliases.append(new_id)
                        existing["aliases"] = aliases

            # Merge each project pattern
            for proj_pattern in project_patterns:
                pattern_id = proj_pattern.get("pattern_id") or proj_pattern.get("id")
                if not pattern_id:
                    continue

                # Step 1: Check for exact ID match (fast)
                if pattern_id in global_by_id:
                    idx = global_by_id[pattern_id]
                    update_pattern(global_patterns[idx], proj_pattern)
                    merge_stats["updated_patterns"] += 1
                    continue

                # Step 2: Check for semantic duplicate (uses Claude Haiku)
                semantic_idx = find_semantic_duplicate(proj_pattern, global_patterns)
                if semantic_idx is not None:
                    update_pattern(
                        global_patterns[semantic_idx],
                        proj_pattern,
                        is_semantic_match=True,
                    )
                    merge_stats["updated_patterns"] += 1
                    merge_stats["semantic_matches"] += 1
                    logger.info(
                        f"Semantic dedup ({pattern_type}): '{pattern_id}' matched "
                        f"'{global_patterns[semantic_idx].get('pattern_id') or global_patterns[semantic_idx].get('id')}'"
                    )
                    continue

                # Step 3: Truly new pattern
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

        # Auto-sync to S3 (if enabled)
        s3_sync_result = None
        try:
            from context_foundry.storage import S3PatternClient

            config = Config.load()
            client = S3PatternClient(
                bucket_name=config.s3_bucket_name,
                prefix=config.s3_prefix,
                aws_region=config.s3_region,
            )
            if client.enabled:
                s3_sync_result = client.upload_pattern(pattern_type, force=False)
                if not s3_sync_result.get("success"):
                    # Log warning but don't fail the merge
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"S3 auto-sync failed for {pattern_type}: {s3_sync_result.get('error')}"
                    )
        except Exception as e:
            # Silently ignore S3 sync errors - don't break merge workflow
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"S3 auto-sync error for {pattern_type}: {e}")

        result = {
            "status": "success",
            "message": f"Successfully merged {pattern_type} from project",
            "merge_stats": merge_stats,  # Keep nested for backward compatibility
            "global_file": save_response["pattern_file"],
            "project_file": str(project_file_path),
        }

        # Add S3 sync status if available
        if s3_sync_result:
            result["s3_sync"] = s3_sync_result

        return result

    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "error": f"Invalid JSON in pattern file: {str(e)}",
            "file_path": project_pattern_file,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


def migrate_all_project_patterns_impl(
    projects_base_dir: str = None,
    projects_dir: str = None,  # Support both names
) -> str:
    """
    Migrate patterns from all projects in a directory to global storage.

    Scans all subdirectories for .context-foundry/patterns/ and merges them.

    Args:
        projects_base_dir: Base directory containing project subdirectories
        projects_dir: Backward compatible alias for projects_base_dir

    Returns:
        JSON string with migration results
    """
    # Handle backward compatibility
    base_dir = projects_base_dir or projects_dir
    if not base_dir:
        return json.dumps(
            {
                "status": "error",
                "error": "Either projects_base_dir or projects_dir must be provided",
            },
            indent=2,
        )

    try:
        base_path = Path(base_dir)
        if not base_path.exists():
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Directory not found: {base_dir}",
                },
                indent=2,
            )

        # Find all project pattern directories
        pattern_dirs = []
        for project_dir in base_path.iterdir():
            if project_dir.is_dir():
                pattern_dir = project_dir / ".context-foundry" / "patterns"
                if pattern_dir.exists():
                    pattern_dirs.append(
                        {"project": project_dir.name, "path": pattern_dir}
                    )

        if not pattern_dirs:
            return json.dumps(
                {
                    "status": "success",
                    "message": "No project patterns found to migrate",
                    "projects_scanned": len(list(base_path.iterdir())),
                },
                indent=2,
            )

        # Migrate each project
        migration_results = {
            "projects_migrated": 0,
            "total_patterns_merged": 0,
            "errors": [],
        }

        for proj_info in pattern_dirs:
            project_name = proj_info["project"]
            pattern_dir = proj_info["path"]

            # Migrate common-issues.json if it exists
            common_issues_file = pattern_dir / "common-issues.json"
            if common_issues_file.exists():
                result_data = merge_project_patterns_impl(
                    str(common_issues_file),
                    "common-issues",
                    increment_build_count=False,  # Don't increment for migration
                )
                if result_data["status"] == "success":
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["new_patterns"]
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["updated_patterns"]
                else:
                    migration_results["errors"].append(
                        {
                            "project": project_name,
                            "file": "common-issues.json",
                            "error": result_data.get("error", "Unknown error"),
                        }
                    )

            # Migrate scout-learnings.json if it exists
            scout_learnings_file = pattern_dir / "scout-learnings.json"
            if scout_learnings_file.exists():
                result_data = merge_project_patterns_impl(
                    str(scout_learnings_file),
                    "scout-learnings",
                    increment_build_count=False,
                )
                if result_data["status"] == "success":
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["new_patterns"]
                    migration_results["total_patterns_merged"] += result_data[
                        "merge_stats"
                    ]["updated_patterns"]
                else:
                    migration_results["errors"].append(
                        {
                            "project": project_name,
                            "file": "scout-learnings.json",
                            "error": result_data.get("error", "Unknown error"),
                        }
                    )

            migration_results["projects_migrated"] += 1

        return json.dumps(
            {
                "status": "success",
                "message": f"Migrated patterns from {migration_results['projects_migrated']} projects",
                "migration_results": migration_results,
                "projects_found": len(pattern_dirs),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "traceback": traceback.format_exc()},
            indent=2,
        )


def share_patterns_to_community_impl(
    auto_confirm: bool = True,
    skip_if_no_changes: bool = True,
    project_path: str = None,  # Legacy parameter for test compatibility
    pattern_ids: list = None,  # Legacy parameter for test compatibility
    description: str = None,  # Legacy parameter for test compatibility
) -> str:
    """
    Automatically share locally-learned patterns with the Context Foundry community.

    This creates a PR with your patterns which will be automatically validated and merged.
    Runs after successful builds to contribute learnings back to the community.

    Args:
        auto_confirm: If True, automatically confirms sharing without prompting
        skip_if_no_changes: If True, skips sharing if no new patterns since last share
        project_path: Legacy parameter for backward compatibility
        pattern_ids: Legacy parameter for backward compatibility
        description: Legacy parameter for backward compatibility

    Returns:
        JSON string with share result
    """
    import os
    import subprocess
    import sys

    try:
        # Legacy parameter validation (for backward compatibility)
        # Validate pattern_ids before proceeding to gh auth check
        if pattern_ids is not None:
            if not project_path:
                return json.dumps(
                    {
                        "status": "error",
                        "error": "project_path required when pattern_ids is provided",
                        "shared": False,
                    },
                    indent=2,
                )

            # Load patterns from project
            project_patterns_dir = Path(project_path) / ".context-foundry" / "patterns"
            if not project_patterns_dir.exists():
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Pattern directory not found: {project_patterns_dir}",
                        "shared": False,
                    },
                    indent=2,
                )

            # Load all pattern files to check if pattern_ids exist
            all_pattern_ids = set()
            for pattern_file in project_patterns_dir.glob("*.json"):
                try:
                    with open(pattern_file, "r") as f:
                        pattern_data = json.load(f)
                        # Check for patterns array
                        if "patterns" in pattern_data:
                            for pattern in pattern_data["patterns"]:
                                pid = pattern.get("id") or pattern.get("pattern_id")
                                if pid:
                                    all_pattern_ids.add(pid)
                except Exception:
                    continue

            # Verify all requested pattern_ids exist
            missing_ids = [pid for pid in pattern_ids if pid not in all_pattern_ids]
            if missing_ids:
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Pattern IDs not found: {', '.join(missing_ids)}",
                        "missing_ids": missing_ids,
                        "shared": False,
                    },
                    indent=2,
                )

        # Get repository root (traverse up from this file's location)
        current_file = Path(__file__)
        repo_root = current_file.parent.parent.parent
        share_script = repo_root / "scripts" / "share-my-patterns.sh"

        if not share_script.exists():
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Pattern sharing script not found: {share_script}",
                    "shared": False,
                },
                indent=2,
            )

        # Check if gh CLI is available and authenticated
        try:
            result = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return json.dumps(
                    {
                        "status": "skipped",
                        "reason": "GitHub CLI not authenticated",
                        "message": "Run 'gh auth login' to enable automatic pattern sharing",
                        "shared": False,
                        "setup_instructions": "https://cli.github.com/manual/gh_auth_login",
                    },
                    indent=2,
                )
        except FileNotFoundError:
            return json.dumps(
                {
                    "status": "skipped",
                    "reason": "GitHub CLI not installed",
                    "message": "Install gh CLI to enable automatic pattern sharing",
                    "shared": False,
                    "setup_instructions": "https://cli.github.com/",
                },
                indent=2,
            )
        except subprocess.TimeoutExpired:
            return json.dumps(
                {
                    "status": "error",
                    "error": "gh auth status check timed out",
                    "shared": False,
                },
                indent=2,
            )

        # Check if local patterns exist
        local_patterns_dir = Path.home() / ".context-foundry" / "patterns"
        if not local_patterns_dir.exists():
            return json.dumps(
                {
                    "status": "skipped",
                    "reason": "No local patterns found",
                    "message": "No patterns to share yet",
                    "shared": False,
                },
                indent=2,
            )

        # Count pattern files
        pattern_files = list(local_patterns_dir.glob("*.json"))
        if not pattern_files:
            return json.dumps(
                {
                    "status": "skipped",
                    "reason": "No pattern files found",
                    "message": "No patterns to share yet",
                    "shared": False,
                },
                indent=2,
            )

        # Check if there are changes since last share (if skip_if_no_changes=True)
        if skip_if_no_changes:
            # Check if .last-pattern-share file exists
            last_share_file = local_patterns_dir / ".last-pattern-share"
            if last_share_file.exists():
                last_share_time = datetime.fromtimestamp(
                    last_share_file.stat().st_mtime
                )

                # Check if any pattern files were modified after last share
                any_newer = False
                for pf in pattern_files:
                    if datetime.fromtimestamp(pf.stat().st_mtime) > last_share_time:
                        any_newer = True
                        break

                if not any_newer:
                    return json.dumps(
                        {
                            "status": "skipped",
                            "reason": "No new patterns since last share",
                            "message": f"Last shared: {last_share_time.isoformat()}",
                            "shared": False,
                        },
                        indent=2,
                    )

        # Run the share script with auto-confirmation
        print("\n🔄 Automatically sharing patterns to community...", file=sys.stderr)

        # Prepare environment with auto-confirm
        env = os.environ.copy()
        if auto_confirm:
            # The script will need to be modified to support auto-confirm env var
            # For now, we'll use 'yes' to pipe confirmation
            process = subprocess.Popen(
                ["bash", str(share_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(repo_root),
                env=env,
            )
            stdout, stderr = process.communicate(input="y\n", timeout=120)
        else:
            process = subprocess.run(
                ["bash", str(share_script)],
                capture_output=True,
                text=True,
                cwd=str(repo_root),
                timeout=120,
            )
            stdout = process.stdout
            stderr = process.stderr

        # Update last share timestamp
        last_share_file = local_patterns_dir / ".last-pattern-share"
        last_share_file.touch()

        if process.returncode == 0:
            # Extract PR URL from output if present
            pr_url = None
            for line in stdout.split("\n"):
                if "https://github.com" in line and "/pull/" in line:
                    pr_url = line.strip()
                    break

            return json.dumps(
                {
                    "status": "success",
                    "message": "Patterns shared successfully",
                    "shared": True,
                    "pr_url": pr_url,
                    "timestamp": datetime.now().isoformat(),
                    "output_summary": stdout[-500:] if len(stdout) > 500 else stdout,
                },
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Share script failed with code {process.returncode}",
                    "shared": False,
                    "stderr": stderr[-500:] if len(stderr) > 500 else stderr,
                },
                indent=2,
            )

    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "status": "error",
                "error": "Pattern sharing timed out after 120 seconds",
                "shared": False,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "error": str(e),
                "shared": False,
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )


def bootstrap_patterns_on_startup_impl():
    """
    Bootstrap patterns from project directory into global storage on first run.

    This function checks if the current directory contains a Context Foundry project
    with pattern files in `.context-foundry/patterns/`. If found and not previously
    bootstrapped, it merges all project patterns into global storage.

    This ensures new users automatically benefit from community-contributed patterns
    when they clone and run Context Foundry.
    """
    import logging
    import sys

    try:
        logger = logging.getLogger(__name__)

        # Check if running from a Context Foundry project directory
        project_pattern_dir = Path.cwd() / ".context-foundry" / "patterns"
        if not project_pattern_dir.exists():
            return  # Not a CF project, skip bootstrap

        # Global pattern directory
        global_pattern_dir = Path.home() / ".context-foundry" / "patterns"
        global_pattern_dir.mkdir(parents=True, exist_ok=True)

        # Check if bootstrap already done
        bootstrap_marker = global_pattern_dir / ".bootstrap-done"
        if bootstrap_marker.exists():
            return  # Already bootstrapped, skip

        logger.info(f"🔄 Bootstrapping patterns from {project_pattern_dir}")
        print(f"🔄 Bootstrapping patterns from {project_pattern_dir}", file=sys.stderr)

        # Merge all pattern files
        pattern_files_merged = 0
        total_patterns_added = 0

        for pattern_file in project_pattern_dir.glob("*.json"):
            pattern_type = pattern_file.stem  # e.g., "common-issues"

            try:
                result = merge_project_patterns_impl(
                    str(pattern_file), pattern_type, increment_build_count=False
                )

                if result["status"] == "success":
                    pattern_files_merged += 1
                    total_patterns_added += result["merge_stats"]["new_patterns"]
                    logger.info(
                        f"✓ Merged {pattern_file.name}: {result['merge_stats']}"
                    )
                    print(
                        f"  ✓ Merged {pattern_file.name}: +{result['merge_stats']['new_patterns']} new patterns",
                        file=sys.stderr,
                    )
                else:
                    logger.warning(
                        f"✗ Failed to merge {pattern_file.name}: {result.get('error')}"
                    )
                    print(f"  ✗ Failed to merge {pattern_file.name}", file=sys.stderr)

            except Exception as e:
                logger.error(f"✗ Error merging {pattern_file}: {e}")
                print(f"  ✗ Error merging {pattern_file}: {e}", file=sys.stderr)

        # Mark as bootstrapped
        bootstrap_marker.write_text(
            f"Bootstrapped on {datetime.now().isoformat()}\n"
            f"Files merged: {pattern_files_merged}\n"
            f"New patterns added: {total_patterns_added}\n"
        )

        logger.info(
            f"✅ Bootstrap complete: {pattern_files_merged} files, {total_patterns_added} new patterns"
        )
        print(
            f"✅ Bootstrap complete: {pattern_files_merged} pattern files merged, {total_patterns_added} new patterns added\n",
            file=sys.stderr,
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Bootstrap failed: {e}", exc_info=True)
        print(f"⚠️  Bootstrap warning: {e}", file=sys.stderr)
        # Don't fail startup, just log the error

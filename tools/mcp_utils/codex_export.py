"""
Export Context Codex entries to legacy JSON pattern files.

This module bridges the gap between the modern codex.db database and the legacy
JSON pattern files that are synced to S3 and read by agents during builds.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from context_foundry.codex.store import KnowledgeStore
from context_foundry.codex.models import KnowledgeType

logger = logging.getLogger(__name__)


class CodexExporter:
    """Export codex entries to JSON pattern files."""

    def __init__(self, patterns_dir: Optional[Path] = None):
        """Initialize exporter.

        Args:
            patterns_dir: Directory containing pattern JSON files.
                         Defaults to ~/.context-foundry/patterns/
        """
        if patterns_dir is None:
            patterns_dir = Path.home() / ".context-foundry" / "patterns"

        self.patterns_dir = Path(patterns_dir)
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

        # Initialize codex with default database path
        codex_db_path = Path.home() / ".context-foundry" / "codex.db"
        self.codex = KnowledgeStore(codex_db_path)

    def export_issues_to_common_issues(self) -> Dict[str, Any]:
        """Export codex issues to common-issues.json.

        Returns:
            Result dict with export stats
        """
        common_issues_path = self.patterns_dir / "common-issues.json"

        # Load existing patterns
        if common_issues_path.exists():
            with open(common_issues_path, "r") as f:
                data = json.load(f)
        else:
            data = {
                "version": "2.0",
                "timestamp": datetime.utcnow().isoformat(),
                "source": "Context Codex Export",
                "patterns": [],
                "total_patterns": 0,
                "total_builds": 0,
                "last_updated": datetime.utcnow().isoformat(),
            }

        # Get all issues from codex by querying database directly
        # (FTS search doesn't support empty/wildcard queries well)
        conn = self.codex.conn
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM knowledge_entries WHERE type = ?",
            (KnowledgeType.ISSUE.value,),
        )

        entries = []
        for row in cursor.fetchall():
            # Convert row to dict
            entry_dict = dict(zip([d[0] for d in cursor.description], row))
            entries.append(entry_dict)

        existing_ids = {p.get("id") for p in data.get("patterns", [])}
        added_count = 0
        updated_count = 0

        for entry_dict in entries:
            # Create a simple object from dict for consistency
            class SimpleEntry:
                def __init__(self, d):
                    for k, v in d.items():
                        setattr(self, k, v)

            entry = SimpleEntry(entry_dict)
            # Convert codex entry to JSON pattern format
            pattern = self._codex_issue_to_json_pattern(entry)

            # Check if pattern already exists
            if pattern["id"] in existing_ids:
                # Update existing pattern (increment frequency, update last_seen)
                for i, existing_pattern in enumerate(data["patterns"]):
                    if existing_pattern.get("id") == pattern["id"]:
                        # Increment frequency
                        existing_pattern["frequency"] = (
                            existing_pattern.get("frequency", 1) + 1
                        )
                        # Update last_seen
                        existing_pattern["last_seen"] = pattern["last_seen"]
                        # Update solution if it changed
                        if pattern.get("solution"):
                            existing_pattern["solution"] = pattern["solution"]
                        # Merge project_types
                        existing_types = set(existing_pattern.get("project_types", []))
                        new_types = set(pattern.get("project_types", []))
                        existing_pattern["project_types"] = sorted(
                            existing_types | new_types
                        )
                        # Preserve highest severity
                        if self._severity_rank(
                            pattern["severity"]
                        ) > self._severity_rank(
                            existing_pattern.get("severity", "low")
                        ):
                            existing_pattern["severity"] = pattern["severity"]

                        updated_count += 1
                        break
            else:
                # Add new pattern
                data["patterns"].append(pattern)
                added_count += 1

        # Update metadata
        data["total_patterns"] = len(data["patterns"])
        data["last_updated"] = datetime.utcnow().isoformat()

        # Save back to file with error handling
        try:
            with open(common_issues_path, "w") as f:
                json.dump(data, f, indent=2)
        except PermissionError as e:
            logger.error(f"Permission denied writing to {common_issues_path}: {e}")
            return {
                "success": False,
                "error": f"Permission denied: {e}",
                "file": str(common_issues_path),
                "message": f"Failed to export: Permission denied writing to {common_issues_path}",
            }
        except OSError as e:
            logger.error(f"OS error writing to {common_issues_path}: {e}")
            return {
                "success": False,
                "error": f"OS error: {e}",
                "file": str(common_issues_path),
                "message": f"Failed to export: {e}",
            }

        return {
            "success": True,
            "file": str(common_issues_path),
            "total_patterns": len(data["patterns"]),
            "added": added_count,
            "updated": updated_count,
            "message": f"Exported {added_count} new and updated {updated_count} existing issues to common-issues.json",
        }

    def export_patterns_to_architecture(self) -> Dict[str, Any]:
        """Export codex patterns to architecture-patterns.json.

        Returns:
            Result dict with export stats
        """
        arch_patterns_path = self.patterns_dir / "architecture-patterns.json"

        # Load existing patterns
        if arch_patterns_path.exists():
            with open(arch_patterns_path, "r") as f:
                data = json.load(f)
        else:
            data = {"patterns": []}

        # Get all patterns from codex by querying database directly
        conn = self.codex.conn
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM knowledge_entries WHERE type = ?",
            (KnowledgeType.PATTERN.value,),
        )

        entries = []
        for row in cursor.fetchall():
            entry_dict = dict(zip([d[0] for d in cursor.description], row))
            entries.append(entry_dict)

        existing_ids = {p.get("pattern_id") for p in data.get("patterns", [])}
        added_count = 0
        updated_count = 0

        for entry_dict in entries:
            # Create a simple object from dict for consistency
            class SimpleEntry:
                def __init__(self, d):
                    for k, v in d.items():
                        setattr(self, k, v)

            entry = SimpleEntry(entry_dict)
            # Convert codex entry to JSON architecture pattern format
            pattern = self._codex_pattern_to_json_pattern(entry)

            # Check if pattern already exists
            if pattern["pattern_id"] in existing_ids:
                # Update existing pattern
                for i, existing_pattern in enumerate(data["patterns"]):
                    if existing_pattern.get("pattern_id") == pattern["pattern_id"]:
                        # Update fields
                        existing_pattern["last_seen"] = pattern["last_seen"]
                        existing_pattern["frequency"] = (
                            existing_pattern.get("frequency", 1) + 1
                        )
                        existing_pattern["description"] = pattern["description"]
                        # Merge project_types
                        existing_types = set(existing_pattern.get("project_types", []))
                        new_types = set(pattern.get("project_types", []))
                        existing_pattern["project_types"] = sorted(
                            existing_types | new_types
                        )

                        updated_count += 1
                        break
            else:
                # Add new pattern
                data["patterns"].append(pattern)
                added_count += 1

        # Save back to file with error handling
        try:
            with open(arch_patterns_path, "w") as f:
                json.dump(data, f, indent=2)
        except PermissionError as e:
            logger.error(f"Permission denied writing to {arch_patterns_path}: {e}")
            return {
                "success": False,
                "error": f"Permission denied: {e}",
                "file": str(arch_patterns_path),
                "message": f"Failed to export: Permission denied writing to {arch_patterns_path}",
            }
        except OSError as e:
            logger.error(f"OS error writing to {arch_patterns_path}: {e}")
            return {
                "success": False,
                "error": f"OS error: {e}",
                "file": str(arch_patterns_path),
                "message": f"Failed to export: {e}",
            }

        return {
            "success": True,
            "file": str(arch_patterns_path),
            "total_patterns": len(data["patterns"]),
            "added": added_count,
            "updated": updated_count,
            "message": f"Exported {added_count} new and updated {updated_count} existing patterns to architecture-patterns.json",
        }

    def export_all(self) -> Dict[str, Any]:
        """Export all codex entries to appropriate JSON files and sync to S3.

        Returns:
            Result dict with stats for all exports and S3 sync status
        """
        results = {"success": True, "exports": []}

        # Export issues
        issues_result = self.export_issues_to_common_issues()
        results["exports"].append(issues_result)

        # Export patterns
        patterns_result = self.export_patterns_to_architecture()
        results["exports"].append(patterns_result)

        # Check if any exports failed
        failed_exports = [r for r in results["exports"] if not r.get("success", False)]
        if failed_exports:
            results["success"] = False
            error_messages = [r.get("error", "Unknown error") for r in failed_exports]
            results["error"] = "; ".join(error_messages)

        # Calculate totals (only from successful exports)
        successful_exports = [r for r in results["exports"] if r.get("success", False)]
        results["total_added"] = sum(r.get("added", 0) for r in successful_exports)
        results["total_updated"] = sum(r.get("updated", 0) for r in successful_exports)

        if failed_exports:
            results["message"] = (
                f"Partial export: {len(successful_exports)}/{len(results['exports'])} succeeded. Errors: {results['error']}"
            )
        else:
            results["message"] = (
                f"Exported {results['total_added']} new entries and updated {results['total_updated']} existing entries"
            )

        # Sync to S3 if available
        s3_sync_result = {"attempted": False, "success": False, "files_synced": 0}
        try:
            from context_foundry.storage import S3PatternClient

            s3_client = S3PatternClient()
            if s3_client.enabled:
                s3_sync_result["attempted"] = True
                files_synced = 0

                # Sync each pattern type that was exported
                pattern_types = ["common-issues", "architecture-patterns"]
                for pattern_type in pattern_types:
                    try:
                        upload_result = s3_client.upload_pattern(
                            pattern_type, force=True
                        )
                        if upload_result.get("success"):
                            files_synced += 1
                    except Exception as e:
                        logger.warning(f"Failed to upload {pattern_type} to S3: {e}")

                s3_sync_result["success"] = files_synced > 0
                s3_sync_result["files_synced"] = files_synced

                if files_synced > 0:
                    logger.info(f"Synced {files_synced} pattern files to S3")
            else:
                logger.debug("S3 sync not enabled (boto3 not available)")

        except ImportError:
            logger.debug("S3PatternClient not available, skipping S3 sync")
        except Exception as e:
            s3_sync_result["error"] = str(e)
            logger.warning(f"S3 sync failed: {e}")

        results["s3_sync"] = s3_sync_result

        return results

    def _codex_issue_to_json_pattern(self, entry) -> Dict[str, Any]:
        """Convert codex issue entry to JSON pattern format.

        Args:
            entry: Codex KnowledgeEntry or dict-like object

        Returns:
            Pattern dict in JSON format
        """
        # Get solution if available
        solution = ""
        try:
            # Try to get solutions from database
            solutions = self.codex.get_solutions(entry.id)
            if solutions:
                solution = solutions[0].description
        except Exception:
            pass

        return {
            "id": self._codex_id_to_json_id(entry.id),
            "issue": entry.title,
            "frequency": entry.frequency if entry.frequency else 1,
            "severity": entry.severity.lower() if entry.severity else "medium",
            "solution": solution or entry.description,  # Use description as fallback
            "project_types": self._parse_comma_list(entry.project_types),
            "last_seen": entry.last_seen_at or entry.updated_at or entry.created_at,
            # Additional fields from codex
            "codex_id": entry.id,
            "tags": self._parse_comma_list(entry.tags) if entry.tags else [],
        }

    def _codex_pattern_to_json_pattern(self, entry) -> Dict[str, Any]:
        """Convert codex pattern entry to JSON architecture pattern format.

        Args:
            entry: Codex KnowledgeEntry or dict-like object

        Returns:
            Pattern dict in JSON format
        """
        return {
            "pattern_id": self._codex_id_to_json_id(entry.id),
            "title": entry.title,
            "first_seen": entry.created_at,
            "last_seen": entry.last_seen_at or entry.updated_at or entry.created_at,
            "frequency": entry.frequency if entry.frequency else 1,
            "success_rate": "100%",  # Default, can be improved
            "project_types": self._parse_comma_list(entry.project_types),
            "description": entry.description,
            "category": entry.category or "general",
            # Additional fields from codex
            "codex_id": entry.id,
            "tags": self._parse_comma_list(entry.tags) if entry.tags else [],
        }

    def _codex_id_to_json_id(self, codex_id: str) -> str:
        """Convert codex ID to JSON pattern ID.

        Codex IDs: iss-aws-boto3-forced-as-118
        JSON IDs: aws-boto3-forced-dependency

        Args:
            codex_id: Codex entry ID

        Returns:
            JSON-friendly ID
        """
        # Remove iss- or pat- prefix
        if codex_id.startswith("iss-"):
            json_id = codex_id[4:]
        elif codex_id.startswith("pat-"):
            json_id = codex_id[4:]
        else:
            json_id = codex_id

        # Remove trailing number
        parts = json_id.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            json_id = parts[0]

        return json_id

    def _parse_comma_list(self, value: Optional[str]) -> List[str]:
        """Parse comma-separated string to list.

        Args:
            value: Comma-separated string

        Returns:
            List of strings
        """
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    def _severity_rank(self, severity: str) -> int:
        """Get numeric rank for severity level.

        Args:
            severity: Severity string

        Returns:
            Numeric rank (higher = more severe)
        """
        severity_map = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }
        return severity_map.get(severity.lower(), 0)


def export_codex_to_patterns_impl(pattern_type: str = "all") -> Dict[str, Any]:
    """Export codex entries to JSON pattern files.

    Args:
        pattern_type: Type of patterns to export ("all", "issues", "patterns")

    Returns:
        Result dict with export stats
    """
    try:
        exporter = CodexExporter()

        if pattern_type == "all":
            return exporter.export_all()
        elif pattern_type == "issues":
            return exporter.export_issues_to_common_issues()
        elif pattern_type == "patterns":
            return exporter.export_patterns_to_architecture()
        else:
            return {
                "success": False,
                "error": f"Unknown pattern_type: {pattern_type}. Use 'all', 'issues', or 'patterns'",
            }

    except Exception as e:
        logger.error(f"Failed to export codex to patterns: {e}", exc_info=True)
        return {"success": False, "error": f"Export failed: {str(e)}"}

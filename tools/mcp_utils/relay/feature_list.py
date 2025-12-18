"""
Feature List Management for Relay

Handles reading, writing, and updating the feature-list.json state file.
Based on Anthropic's recommendation to use JSON format for structured state
that agents should not arbitrarily modify.
"""

import json
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Feature:
    """A single feature to be implemented."""

    id: str
    description: str
    category: str = "functional"
    priority: int = 1
    dependencies: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    passes: bool = False
    last_tested: Optional[str] = None
    implemented_in_commit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Feature":
        """Create Feature from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            category=data.get("category", "functional"),
            priority=data.get("priority", 1),
            dependencies=data.get("dependencies", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            passes=data.get("passes", False),
            last_tested=data.get("last_tested"),
            implemented_in_commit=data.get("implemented_in_commit"),
        )


@dataclass
class FeatureList:
    """
    Manages the feature list state file.

    The feature list is the central state artifact for Relay builds.
    It tracks which features have been implemented and which still need work.
    """

    project_name: str
    features: List[Feature]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_features: int = 0

    def __post_init__(self):
        """Calculate total features after initialization."""
        self.total_features = len(self.features)

    @property
    def completed_count(self) -> int:
        """Number of features where passes=True."""
        return sum(1 for f in self.features if f.passes)

    @property
    def pending_count(self) -> int:
        """Number of features where passes=False."""
        return sum(1 for f in self.features if not f.passes)

    @property
    def completion_percentage(self) -> float:
        """Percentage of features completed."""
        if self.total_features == 0:
            return 0.0
        return (self.completed_count / self.total_features) * 100

    @property
    def is_complete(self) -> bool:
        """True if all features pass."""
        return all(f.passes for f in self.features)

    def get_next_feature(self) -> Optional[Feature]:
        """
        Get the highest-priority feature where passes=False.

        Returns None if all features are complete.
        """
        pending = [f for f in self.features if not f.passes]
        if not pending:
            return None
        # Sort by priority (lower = higher priority)
        pending.sort(key=lambda f: f.priority)
        return pending[0]

    def get_completed_features(self) -> List[Feature]:
        """Get all features where passes=True."""
        return [f for f in self.features if f.passes]

    def get_random_completed_features(self, count: int = 2) -> List[Feature]:
        """
        Get random sample of completed features for regression testing.

        Args:
            count: Number of features to sample

        Returns:
            List of randomly selected completed features (may be fewer than count)
        """
        completed = self.get_completed_features()
        if len(completed) <= count:
            return completed
        return random.sample(completed, count)

    def mark_feature_complete(
        self, feature_id: str, commit_sha: Optional[str] = None
    ) -> bool:
        """
        Mark a feature as passing.

        Args:
            feature_id: ID of the feature to mark complete
            commit_sha: Git commit SHA where this was implemented

        Returns:
            True if feature was found and updated, False otherwise
        """
        for feature in self.features:
            if feature.id == feature_id:
                feature.passes = True
                feature.last_tested = datetime.now().isoformat()
                if commit_sha:
                    feature.implemented_in_commit = commit_sha
                return True
        return False

    def mark_feature_failed(self, feature_id: str) -> bool:
        """
        Mark a feature as failing (regression detected).

        Args:
            feature_id: ID of the feature to mark as failed

        Returns:
            True if feature was found and updated, False otherwise
        """
        for feature in self.features:
            if feature.id == feature_id:
                feature.passes = False
                feature.last_tested = datetime.now().isoformat()
                return True
        return False

    def get_feature_by_id(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by its ID."""
        for feature in self.features:
            if feature.id == feature_id:
                return feature
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_name": self.project_name,
            "created_at": self.created_at,
            "total_features": self.total_features,
            "features": [f.to_dict() for f in self.features],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureList":
        """Create FeatureList from dictionary."""
        features = [Feature.from_dict(f) for f in data.get("features", [])]
        return cls(
            project_name=data["project_name"],
            features=features,
            created_at=data.get("created_at", datetime.now().isoformat()),
        )

    def save(self, path: Path) -> None:
        """
        Save feature list to JSON file.

        Args:
            path: Path to save the JSON file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "FeatureList":
        """
        Load feature list from JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            FeatureList instance

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def get_path(cls, working_directory: Path) -> Path:
        """Get the standard path for feature-list.json."""
        return working_directory / ".relay" / "feature-list.json"

    def get_progress_summary(self) -> str:
        """Get human-readable progress summary."""
        return (
            f"Progress: {self.completed_count}/{self.total_features} features "
            f"({self.completion_percentage:.1f}%)"
        )


def parse_feature_list_from_output(
    output: str, project_name: str
) -> Optional[FeatureList]:
    """
    Parse feature list JSON from agent output.

    The initialization agent outputs JSON that we need to extract.
    This function finds and parses that JSON.

    Args:
        output: Raw output from the initialization agent
        project_name: Name of the project

    Returns:
        FeatureList if valid JSON found, None otherwise
    """
    import re

    # Try to find JSON block in the output
    # Look for content between ```json and ``` or just raw JSON
    json_patterns = [
        r"```json\s*(.*?)\s*```",  # Markdown code block
        r"```\s*(.*?)\s*```",  # Generic code block
        r"(\{[^{}]*\"features\"[^{}]*\[.*?\]\s*\})",  # Raw JSON with features array
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, output, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if "features" in data:
                    # Ensure project_name is set
                    data["project_name"] = project_name
                    return FeatureList.from_dict(data)
            except json.JSONDecodeError:
                continue

    # Try parsing the entire output as JSON
    try:
        data = json.loads(output.strip())
        if "features" in data:
            data["project_name"] = project_name
            return FeatureList.from_dict(data)
    except json.JSONDecodeError:
        pass

    return None

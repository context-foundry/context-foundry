"""
Artifact manifest utilities for Context Foundry builds.

Agents use this to declare artifacts they create during builds.
The manifest is read by the dashboard to display artifact status.

Manifest location: .context-foundry/artifacts.json
Schema:
{
    "artifacts": [
        {
            "phase": "Screenshot",
            "name": "hero.png",
            "path": "docs/screenshots/hero.png",
            "type": "image/png"
        },
        ...
    ]
}
"""

import json
import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_manifest_path(working_dir: str) -> Path:
    """Get the path to the artifact manifest file."""
    return Path(working_dir) / ".context-foundry" / "artifacts.json"


def read_manifest(working_dir: str) -> dict:
    """
    Read the current artifact manifest.

    Returns empty manifest structure if file doesn't exist.
    """
    manifest_path = get_manifest_path(working_dir)

    if not manifest_path.exists():
        return {"artifacts": [], "updated_at": None}

    try:
        with open(manifest_path) as f:
            data = json.load(f)
            # Ensure artifacts key exists
            if "artifacts" not in data:
                data["artifacts"] = []
            return data
    except Exception as e:
        logger.warning(f"Failed to read manifest: {e}")
        return {"artifacts": [], "updated_at": None}


def write_manifest(working_dir: str, manifest: dict) -> bool:
    """
    Write the artifact manifest to disk.

    Returns True on success, False on failure.
    """
    manifest_path = get_manifest_path(working_dir)

    try:
        # Ensure .context-foundry directory exists
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        manifest["updated_at"] = datetime.utcnow().isoformat() + "Z"

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        return True
    except Exception as e:
        logger.error(f"Failed to write manifest: {e}")
        return False


def add_artifact(
    working_dir: str,
    phase: str,
    name: str,
    path: str,
    file_type: Optional[str] = None,
    hero: bool = False,
) -> bool:
    """
    Add an artifact to the manifest.

    Args:
        working_dir: The project working directory
        phase: Phase that created this artifact (Scout, Architect, Builder, Test, Screenshot, Documentation, Deploy)
        name: Display name for the artifact (e.g., "hero.png", "README.md")
        path: Relative path from working_dir to the artifact (e.g., "docs/screenshots/hero.png")
        file_type: Optional MIME type (auto-detected if not provided)
        hero: For Screenshot phase only - if True, this artifact will be mapped to the
              standard hero key (docs/screenshots/hero.png) that the dashboard expects,
              regardless of actual file location.

    Returns:
        True on success, False on failure

    Example:
        # Standard artifact
        add_artifact(
            "/path/to/project",
            "Screenshot",
            "hero.png",
            "docs/screenshots/hero.png",
            "image/png"
        )

        # Hero screenshot in custom location
        add_artifact(
            "/path/to/project",
            "Screenshot",
            "main-screenshot.png",
            "images/main-screenshot.png",
            "image/png",
            hero=True  # Dashboard will show this as the hero screenshot
        )
    """
    # Validate phase
    valid_phases = [
        "Scout",
        "Architect",
        "Builder",
        "Test",
        "Screenshot",
        "Documentation",
        "Deploy",
    ]
    if phase not in valid_phases:
        logger.warning(f"Invalid phase '{phase}', expected one of {valid_phases}")
        # Allow it anyway for flexibility

    # Auto-detect MIME type if not provided
    if not file_type:
        file_type, _ = mimetypes.guess_type(path)
        if not file_type:
            file_type = "application/octet-stream"

    # Read current manifest
    manifest = read_manifest(working_dir)

    # Build artifact entry
    entry = {
        "phase": phase,
        "name": name,
        "path": path,
        "type": file_type,
    }
    # Add hero flag for Screenshot phase if specified
    if hero and phase == "Screenshot":
        entry["hero"] = True

    # Check for duplicates (same phase + name)
    artifacts = manifest["artifacts"]
    for i, artifact in enumerate(artifacts):
        if artifact.get("phase") == phase and artifact.get("name") == name:
            # Update existing entry
            artifacts[i] = entry
            return write_manifest(working_dir, manifest)

    # Add new entry
    artifacts.append(entry)

    return write_manifest(working_dir, manifest)


def add_artifacts_batch(
    working_dir: str,
    artifacts_list: list,
) -> bool:
    """
    Add multiple artifacts to the manifest at once.

    Args:
        working_dir: The project working directory
        artifacts_list: List of dicts with keys: phase, name, path, type (optional), hero (optional)
            - hero: For Screenshot phase, if True maps to standard hero key in dashboard

    Returns:
        True on success, False on failure

    Example:
        add_artifacts_batch("/path/to/project", [
            {"phase": "Screenshot", "name": "hero.png", "path": "images/hero.png", "hero": True},
            {"phase": "Screenshot", "name": "feature-1.png", "path": "docs/screenshots/feature-1.png"},
            {"phase": "Documentation", "name": "README.md", "path": "README.md"},
        ])
    """
    manifest = read_manifest(working_dir)
    existing = manifest["artifacts"]

    # Build lookup for existing artifacts
    existing_lookup = {
        (a.get("phase"), a.get("name")): i for i, a in enumerate(existing)
    }

    for item in artifacts_list:
        phase = item.get("phase")
        name = item.get("name")
        path = item.get("path")
        file_type = item.get("type")
        hero = item.get("hero", False)

        if not phase or not name or not path:
            logger.warning(f"Skipping invalid artifact entry: {item}")
            continue

        # Auto-detect MIME type if not provided
        if not file_type:
            file_type, _ = mimetypes.guess_type(path)
            if not file_type:
                file_type = "application/octet-stream"

        entry = {
            "phase": phase,
            "name": name,
            "path": path,
            "type": file_type,
        }

        # Add hero flag for Screenshot phase if specified
        if hero and phase == "Screenshot":
            entry["hero"] = True

        key = (phase, name)
        if key in existing_lookup:
            # Update existing
            existing[existing_lookup[key]] = entry
        else:
            # Add new
            existing.append(entry)
            existing_lookup[key] = len(existing) - 1

    return write_manifest(working_dir, manifest)


def get_phase_artifacts(working_dir: str, phase: str) -> list:
    """
    Get all artifacts for a specific phase.

    Args:
        working_dir: The project working directory
        phase: Phase name (Scout, Architect, etc.)

    Returns:
        List of artifact dicts for the phase
    """
    manifest = read_manifest(working_dir)
    return [a for a in manifest["artifacts"] if a.get("phase") == phase]


def clear_phase_artifacts(working_dir: str, phase: str) -> bool:
    """
    Remove all artifacts for a specific phase.

    Useful when re-running a phase that regenerates all its artifacts.

    Args:
        working_dir: The project working directory
        phase: Phase name to clear

    Returns:
        True on success, False on failure
    """
    manifest = read_manifest(working_dir)
    manifest["artifacts"] = [
        a for a in manifest["artifacts"] if a.get("phase") != phase
    ]
    return write_manifest(working_dir, manifest)

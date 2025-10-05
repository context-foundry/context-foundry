"""
Project Detection Utility
Detects and resolves project sources (GitHub URLs, local paths, project names)
"""

import os
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse


class ProjectDetector:
    """Detect and resolve project location from various input formats."""

    def __init__(self, examples_dir: str = "examples"):
        self.examples_dir = Path(examples_dir)

    def detect(self, project_input: str) -> Tuple[Path, str]:
        """
        Detect project type and return resolved path and source type.

        Args:
            project_input: GitHub URL, local path, or project name

        Returns:
            Tuple of (resolved_path, source_type)
            source_type can be: 'github', 'local', 'examples', 'not_found'

        Raises:
            ValueError: If project cannot be resolved
        """
        # Check if it's a GitHub URL
        if self._is_github_url(project_input):
            return self._handle_github_url(project_input)

        # Check if it's a local path
        path = Path(project_input)
        if path.exists() and path.is_dir():
            return (path.absolute(), 'local')

        # Check if it's a project name in examples/
        examples_path = self.examples_dir / project_input
        if examples_path.exists() and examples_path.is_dir():
            return (examples_path.absolute(), 'examples')

        # Not found
        raise ValueError(
            f"Project not found: {project_input}\n"
            f"  Tried:\n"
            f"  - GitHub URL\n"
            f"  - Local path: {path.absolute()}\n"
            f"  - Examples: {examples_path.absolute()}\n"
            f"  \n"
            f"  Provide a valid GitHub URL, local directory path, or project name in examples/"
        )

    def _is_github_url(self, url: str) -> bool:
        """Check if input is a GitHub URL."""
        patterns = [
            r'github\.com',
            r'git@github\.com',
            r'https?://.*github',
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns)

    def _handle_github_url(self, url: str) -> Tuple[Path, str]:
        """
        Clone GitHub repository to temp location or use existing clone.

        Args:
            url: GitHub repository URL

        Returns:
            Tuple of (local_path, 'github')
        """
        # Extract repo name from URL
        repo_name = self._extract_repo_name(url)

        # Clone to examples/ directory
        clone_path = self.examples_dir / repo_name

        if clone_path.exists():
            print(f"📁 Using existing clone: {clone_path}")
            # Pull latest changes
            try:
                subprocess.run(
                    ["git", "-C", str(clone_path), "pull"],
                    capture_output=True,
                    timeout=30
                )
                print(f"   ✓ Updated to latest")
            except Exception as e:
                print(f"   ⚠️  Could not pull latest: {e}")
        else:
            print(f"📥 Cloning repository: {url}")
            try:
                result = subprocess.run(
                    ["git", "clone", url, str(clone_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    raise RuntimeError(f"Git clone failed: {result.stderr}")

                print(f"   ✓ Cloned to: {clone_path}")
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Git clone timed out. Check your connection.")
            except Exception as e:
                raise RuntimeError(f"Failed to clone repository: {e}")

        return (clone_path.absolute(), 'github')

    def _extract_repo_name(self, url: str) -> str:
        """Extract repository name from GitHub URL."""
        # Handle different URL formats:
        # - https://github.com/user/repo.git
        # - https://github.com/user/repo
        # - git@github.com:user/repo.git

        # Remove .git suffix if present
        url = url.rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]

        # Extract the last path component
        if 'github.com/' in url:
            # HTTPS URL
            parts = url.split('github.com/')[-1].split('/')
            if len(parts) >= 2:
                return parts[-1]  # Just the repo name
        elif 'github.com:' in url:
            # SSH URL
            parts = url.split('github.com:')[-1].split('/')
            if len(parts) >= 2:
                return parts[-1]

        # Fallback: use the last path component
        return Path(url).name

    def find_session(self, project_name: str, session_id: Optional[str] = None) -> Optional[Path]:
        """
        Find a foundry session for a project.

        Args:
            project_name: Name of the project
            session_id: Optional specific session ID (timestamp)

        Returns:
            Path to session directory if found, None otherwise
        """
        checkpoints_dir = Path("checkpoints/sessions")

        if not checkpoints_dir.exists():
            return None

        if session_id:
            # Look for specific session
            session_file = checkpoints_dir / f"{project_name}_{session_id}.json"
            if session_file.exists():
                return checkpoints_dir
        else:
            # Find most recent session for this project
            sessions = list(checkpoints_dir.glob(f"{project_name}_*.json"))
            if sessions:
                # Sort by modification time, get most recent
                latest = max(sessions, key=lambda p: p.stat().st_mtime)
                # Extract session ID from filename
                return checkpoints_dir

        return None

    def get_latest_session_id(self, project_name: str) -> Optional[str]:
        """Get the most recent session ID for a project."""
        checkpoints_dir = Path("checkpoints/sessions")

        if not checkpoints_dir.exists():
            return None

        sessions = list(checkpoints_dir.glob(f"{project_name}_*.json"))
        if not sessions:
            return None

        # Sort by modification time
        latest = max(sessions, key=lambda p: p.stat().st_mtime)

        # Extract session ID from filename: project_name_TIMESTAMP.json
        filename = latest.stem  # Remove .json
        parts = filename.split('_')
        if len(parts) >= 2:
            # Session ID is everything after project_name_
            session_id = '_'.join(parts[1:])
            return session_id

        return None

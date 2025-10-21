#!/usr/bin/env python3
"""
Git Manager for Context Foundry
Handles git operations including commits and GitHub pushes
"""

import subprocess
from pathlib import Path
from typing import Optional


class GitManager:
    """Manages git operations for a project directory."""

    def __init__(self, project_dir: Path, project_name: str = ""):
        """Initialize GitManager.

        Args:
            project_dir: Path to the project directory
            project_name: Optional project name for display purposes
        """
        self.project_dir = Path(project_dir)
        self.project_name = project_name

    def git_available(self) -> bool:
        """Check if git is available and initialized.

        Returns:
            bool: True if git is available and initialized, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.project_dir,
            )
            return result.returncode == 0
        except:
            return False

    def create_git_commit(self, message: str):
        """Create a git commit for current changes.

        Args:
            message: Commit message
        """
        try:
            subprocess.run(
                ["git", "add", "."],
                check=True,
                timeout=10,
                cwd=self.project_dir,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                check=True,
                timeout=10,
                cwd=self.project_dir,
            )
            print(f"   📍 Git commit created")
        except Exception as e:
            print(f"   ⚠️  Git commit failed: {e}")

    def push_to_github(self) -> bool:
        """Push commits to GitHub remote.

        Returns:
            bool: True if push succeeded, False otherwise
        """
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
                cwd=self.project_dir,
            )
            current_branch = result.stdout.strip()

            # Check if remote exists
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self.project_dir,
            )

            if result.returncode != 0:
                print(f"\n⚠️  No 'origin' remote configured. Skipping push.")
                print(f"   Configure with: git remote add origin <url>")
                return False

            remote_url = result.stdout.strip()
            print(f"\n📤 Pushing to GitHub...")
            print(f"   Remote: {remote_url}")
            print(f"   Branch: {current_branch}")

            # Push to remote
            result = subprocess.run(
                ["git", "push", "origin", current_branch],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_dir,
            )

            if result.returncode == 0:
                print(f"✅ Successfully pushed to GitHub!")
                return True
            else:
                print(f"⚠️  Push failed: {result.stderr}")
                if "rejected" in result.stderr.lower():
                    print(f"   💡 Tip: Pull changes first with: git pull origin {current_branch}")
                elif "authentication" in result.stderr.lower() or "permission" in result.stderr.lower():
                    print(f"   💡 Tip: Check your GitHub authentication (SSH key or token)")
                return False

        except subprocess.TimeoutExpired:
            print(f"\n⚠️  Push timed out. Check your network connection.")
            return False
        except Exception as e:
            print(f"\n⚠️  Push failed: {e}")
            return False

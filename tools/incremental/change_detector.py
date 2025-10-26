"""
Change Detector - Phase 2

File-level change detection using git diff + SHA256 hashing for 70-90% faster builds.

Strategy:
- Primary: Git diff against last build commit SHA
- Fallback: SHA256 hash comparison if no git
- Snapshot: Store file hashes + git SHA in .context-foundry/last-build-snapshot.json
"""

import json
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class ChangeReport:
    """Report of changes detected between builds."""
    changed_files: List[str]      # Files modified
    added_files: List[str]         # New files
    deleted_files: List[str]       # Removed files
    unchanged_files: List[str]     # Same as before
    change_percentage: float       # % of files changed
    git_available: bool            # Whether git was used
    git_diff_sha: Optional[str]    # Git commit SHA
    total_files: int               # Total files tracked
    detection_method: str          # 'git' or 'hash'


def get_last_build_snapshot_path(working_directory: str) -> Path:
    """
    Get path to last build snapshot file.

    Args:
        working_directory: Project working directory

    Returns:
        Path to .context-foundry/last-build-snapshot.json
    """
    project_root = Path(working_directory)
    snapshot_path = project_root / ".context-foundry" / "last-build-snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    return snapshot_path


def hash_file(file_path: Path) -> str:
    """
    Generate SHA256 hash of a file's contents.

    Args:
        file_path: Path to file

    Returns:
        SHA256 hex digest
    """
    try:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    except OSError:
        return ""


def get_git_commit_sha(working_directory: str) -> Optional[str]:
    """
    Get current git commit SHA.

    Args:
        working_directory: Project working directory

    Returns:
        Git commit SHA or None if git unavailable
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.strip()

        return None

    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def get_git_changed_files(working_directory: str, base_sha: str) -> Optional[List[str]]:
    """
    Get list of files changed since base_sha using git diff.

    Args:
        working_directory: Project working directory
        base_sha: Base git commit SHA

    Returns:
        List of changed file paths (relative to repo root) or None if git unavailable
    """
    try:
        # Get changed files (modified + added)
        result = subprocess.run(
            ['git', 'diff', '--name-only', base_sha, 'HEAD'],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        changed = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]

        # Get deleted files
        result_deleted = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=D', base_sha, 'HEAD'],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=10
        )

        deleted = []
        if result_deleted.returncode == 0:
            deleted = [f.strip() for f in result_deleted.stdout.strip().split('\n') if f.strip()]

        return changed + deleted

    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def get_source_files(working_directory: str) -> List[Path]:
    """
    Get all source files in a project.

    Args:
        working_directory: Project working directory

    Returns:
        List of source file paths
    """
    project_root = Path(working_directory)

    # Patterns to ignore
    ignore_patterns = {
        '.git', 'node_modules', '__pycache__', '.pytest_cache',
        'venv', 'env', '.venv', 'dist', 'build', '.context-foundry',
        'coverage', '.nyc_output'
    }

    # Common source file extensions
    source_extensions = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp',
        '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.cs', '.swift',
        '.md', '.json', '.yaml', '.yml', '.toml', '.txt'
    }

    source_files = []

    for file in project_root.rglob('*'):
        # Skip ignored paths
        if any(ignore in file.parts for ignore in ignore_patterns):
            continue

        # Only include source files
        if file.is_file() and file.suffix in source_extensions:
            source_files.append(file)

    return source_files


def compute_file_hashes(working_directory: str) -> Dict[str, str]:
    """
    Compute SHA256 hashes for all source files.

    Args:
        working_directory: Project working directory

    Returns:
        Dict mapping relative file path to SHA256 hash
    """
    project_root = Path(working_directory)
    source_files = get_source_files(working_directory)

    file_hashes = {}
    for file in source_files:
        rel_path = str(file.relative_to(project_root))
        file_hashes[rel_path] = hash_file(file)

    return file_hashes


def capture_build_snapshot(working_directory: str) -> Dict[str, Any]:
    """
    Capture current build snapshot (git SHA + file hashes).

    Args:
        working_directory: Project working directory

    Returns:
        Snapshot dict with git_sha and file_hashes
    """
    git_sha = get_git_commit_sha(working_directory)
    file_hashes = compute_file_hashes(working_directory)

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "git_sha": git_sha,
        "git_available": git_sha is not None,
        "file_hashes": file_hashes,
        "total_files": len(file_hashes)
    }

    # Save snapshot
    snapshot_path = get_last_build_snapshot_path(working_directory)
    try:
        snapshot_path.write_text(json.dumps(snapshot, indent=2))
        print(f"📸 Build snapshot captured: {len(file_hashes)} files")
        if git_sha:
            print(f"   Git SHA: {git_sha}")
    except OSError as e:
        print(f"⚠️  Failed to save build snapshot: {e}")

    return snapshot


def detect_changes(
    working_directory: str,
    previous_snapshot: Optional[Dict[str, Any]] = None
) -> ChangeReport:
    """
    Detect changes between current state and previous snapshot.

    Args:
        working_directory: Project working directory
        previous_snapshot: Previous build snapshot (or None to load from file)

    Returns:
        ChangeReport with detected changes
    """
    # Load previous snapshot if not provided
    if previous_snapshot is None:
        snapshot_path = get_last_build_snapshot_path(working_directory)
        if not snapshot_path.exists():
            # No previous snapshot - treat all files as changed
            current_hashes = compute_file_hashes(working_directory)
            return ChangeReport(
                changed_files=list(current_hashes.keys()),
                added_files=[],
                deleted_files=[],
                unchanged_files=[],
                change_percentage=100.0,
                git_available=False,
                git_diff_sha=None,
                total_files=len(current_hashes),
                detection_method='none'
            )

        try:
            previous_snapshot = json.loads(snapshot_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  Failed to load previous snapshot: {e}")
            # Treat all files as changed
            current_hashes = compute_file_hashes(working_directory)
            return ChangeReport(
                changed_files=list(current_hashes.keys()),
                added_files=[],
                deleted_files=[],
                unchanged_files=[],
                change_percentage=100.0,
                git_available=False,
                git_diff_sha=None,
                total_files=len(current_hashes),
                detection_method='error'
            )

    # Try git-based detection first (faster)
    git_sha = previous_snapshot.get('git_sha')
    current_git_sha = get_git_commit_sha(working_directory)

    if git_sha and current_git_sha:
        changed_files_git = get_git_changed_files(working_directory, git_sha)

        if changed_files_git is not None:
            # Git detection successful
            previous_hashes = previous_snapshot.get('file_hashes', {})
            all_files = set(previous_hashes.keys())
            changed_set = set(changed_files_git)

            # Categorize changes
            changed_files = [f for f in changed_files_git if f in previous_hashes]
            added_files = [f for f in changed_files_git if f not in previous_hashes]
            deleted_files = []  # Git diff already includes deleted files
            unchanged_files = list(all_files - changed_set)

            total_files = len(all_files) + len(added_files)
            change_percentage = (len(changed_set) / total_files * 100) if total_files > 0 else 0

            print(f"🔍 Change detection (git): {len(changed_set)} changes detected")
            print(f"   Modified: {len(changed_files)}")
            print(f"   Added: {len(added_files)}")
            print(f"   Unchanged: {len(unchanged_files)}")
            print(f"   Change percentage: {change_percentage:.1f}%")

            return ChangeReport(
                changed_files=changed_files,
                added_files=added_files,
                deleted_files=deleted_files,
                unchanged_files=unchanged_files,
                change_percentage=change_percentage,
                git_available=True,
                git_diff_sha=current_git_sha,
                total_files=total_files,
                detection_method='git'
            )

    # Fallback to hash-based detection
    print("🔍 Git unavailable, using hash-based detection...")

    previous_hashes = previous_snapshot.get('file_hashes', {})
    current_hashes = compute_file_hashes(working_directory)

    # Find changes
    changed_files = []
    added_files = []
    deleted_files = []
    unchanged_files = []

    all_files = set(previous_hashes.keys()).union(set(current_hashes.keys()))

    for file in all_files:
        if file not in previous_hashes:
            added_files.append(file)
        elif file not in current_hashes:
            deleted_files.append(file)
        elif previous_hashes[file] != current_hashes[file]:
            changed_files.append(file)
        else:
            unchanged_files.append(file)

    total_files = len(all_files)
    total_changes = len(changed_files) + len(added_files) + len(deleted_files)
    change_percentage = (total_changes / total_files * 100) if total_files > 0 else 0

    print(f"🔍 Change detection (hash): {total_changes} changes detected")
    print(f"   Modified: {len(changed_files)}")
    print(f"   Added: {len(added_files)}")
    print(f"   Deleted: {len(deleted_files)}")
    print(f"   Unchanged: {len(unchanged_files)}")
    print(f"   Change percentage: {change_percentage:.1f}%")

    return ChangeReport(
        changed_files=changed_files,
        added_files=added_files,
        deleted_files=deleted_files,
        unchanged_files=unchanged_files,
        change_percentage=change_percentage,
        git_available=False,
        git_diff_sha=current_git_sha,
        total_files=total_files,
        detection_method='hash'
    )


__all__ = [
    'ChangeReport',
    'capture_build_snapshot',
    'detect_changes',
    'get_last_build_snapshot_path',
    'get_git_commit_sha',
    'compute_file_hashes'
]

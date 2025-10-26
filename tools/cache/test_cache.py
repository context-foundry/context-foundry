"""
Test Result Cache System

Caches test results based on file hashes to skip testing when code hasn't changed.

Strategy:
- Track SHA256 hash of every source file
- Store test results with file hash snapshot
- Cache HIT: All file hashes match → skip tests, reuse results
- Cache MISS: Any file changed → run tests again

Benefits:
- Skip test phase entirely when no code changed
- Especially useful for:
  - Documentation-only updates
  - Configuration changes
  - Running builds in sequence without code changes
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from . import (
    get_cache_dir,
    is_cache_valid,
    save_cache_metadata,
    load_cache_metadata,
    DEFAULT_CACHE_TTL_HOURS
)

def hash_file(file_path: Path) -> str:
    """Generate SHA256 hash of a file's contents."""
    try:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    except OSError:
        return ""

def get_source_files(working_directory: str) -> List[Path]:
    """
    Get all source files in a project (excluding common ignore patterns).

    Returns files that should be considered for change detection.
    """
    project_root = Path(working_directory)

    # Patterns to ignore
    ignore_patterns = {
        '.git', 'node_modules', '__pycache__', '.pytest_cache',
        'venv', 'env', '.venv', 'dist', 'build', '.context-foundry',
        'coverage', '.nyc_output', '*.pyc', '*.log'
    }

    source_files = []

    # Common source file extensions
    source_extensions = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp',
        '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.cs', '.swift'
    }

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
    Compute hashes for all source files in a project.

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

def get_test_cache_path(working_directory: str) -> Path:
    """Get the file path for test results cache."""
    cache_dir = get_cache_dir(working_directory)
    return cache_dir / "test-results.json"

def get_file_hashes_path(working_directory: str) -> Path:
    """Get the file path for file hashes snapshot."""
    cache_dir = get_cache_dir(working_directory)
    return cache_dir / "file-hashes.json"

def get_cached_test_results(
    working_directory: str,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS
) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached test results if code hasn't changed.

    Args:
        working_directory: Project working directory
        ttl_hours: Cache TTL in hours (default: 24)

    Returns:
        Test results dict if cache hit, None if cache miss
    """
    test_cache_file = get_test_cache_path(working_directory)
    hash_cache_file = get_file_hashes_path(working_directory)

    # Check if cache files exist and are valid
    if not is_cache_valid(test_cache_file, ttl_hours):
        print("⚠️ Test cache miss: No cached results or cache expired")
        return None

    if not hash_cache_file.exists():
        print("⚠️ Test cache miss: No file hash snapshot")
        return None

    # Load cached file hashes
    try:
        cached_hashes = json.loads(hash_cache_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ Test cache miss: Failed to load cached hashes: {e}")
        return None

    # Compute current file hashes
    current_hashes = compute_file_hashes(working_directory)

    # Compare hashes
    if cached_hashes != current_hashes:
        # Find what changed
        added_files = set(current_hashes.keys()) - set(cached_hashes.keys())
        removed_files = set(cached_hashes.keys()) - set(current_hashes.keys())
        modified_files = {
            f for f in current_hashes
            if f in cached_hashes and current_hashes[f] != cached_hashes[f]
        }

        print("⚠️ Test cache miss: Code changes detected")
        if added_files:
            print(f"   Added files: {len(added_files)}")
        if removed_files:
            print(f"   Removed files: {len(removed_files)}")
        if modified_files:
            print(f"   Modified files: {len(modified_files)}")
            # Show first few modified files
            for f in list(modified_files)[:5]:
                print(f"     - {f}")

        return None

    # Load and return cached test results
    try:
        test_results = json.loads(test_cache_file.read_text())

        # Load metadata
        metadata = load_cache_metadata(test_cache_file)

        print(f"✅ Test cache HIT! No code changes detected")
        print(f"   Cached results from: {metadata.get('created_at', 'unknown') if metadata else 'unknown'}")
        print(f"   Files tracked: {len(current_hashes)}")
        print(f"   Tests passed: {test_results.get('passed', 'unknown')}/{test_results.get('total', 'unknown')}")

        return test_results

    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ Test cache miss: Failed to load test results: {e}")
        return None

def save_test_results_to_cache(
    working_directory: str,
    test_results: Dict[str, Any]
) -> None:
    """
    Save test results to cache along with file hash snapshot.

    Args:
        working_directory: Project working directory
        test_results: Test results dictionary with keys:
            - passed: number of passing tests
            - total: total number of tests
            - duration: test duration in seconds
            - test_command: command used to run tests
            - success: boolean indicating all tests passed
    """
    test_cache_file = get_test_cache_path(working_directory)
    hash_cache_file = get_file_hashes_path(working_directory)

    try:
        # Compute and save file hashes
        file_hashes = compute_file_hashes(working_directory)
        hash_cache_file.write_text(json.dumps(file_hashes, indent=2))

        # Save test results
        test_cache_file.write_text(json.dumps(test_results, indent=2))

        # Save metadata
        metadata = {
            "files_tracked": len(file_hashes),
            "tests_passed": test_results.get('passed', 0),
            "tests_total": test_results.get('total', 0),
            "test_success": test_results.get('success', False)
        }
        save_cache_metadata(test_cache_file, metadata)

        print(f"💾 Test results cached successfully")
        print(f"   Tests: {test_results.get('passed', 0)}/{test_results.get('total', 0)} passed")
        print(f"   Files tracked: {len(file_hashes)}")

    except OSError as e:
        print(f"⚠️ Failed to save test results to cache: {e}")

def clear_test_cache(working_directory: str) -> int:
    """
    Clear test cache.

    Args:
        working_directory: Project working directory

    Returns:
        Number of cache files deleted
    """
    cache_dir = get_cache_dir(working_directory)
    deleted_count = 0

    for pattern in ["test-results.json", "file-hashes.json"]:
        file = cache_dir / pattern
        if file.exists():
            try:
                file.unlink()
                # Also delete metadata
                meta_file = file.with_suffix('.meta.json')
                if meta_file.exists():
                    meta_file.unlink()
                deleted_count += 1
            except OSError:
                pass

    return deleted_count

def get_test_cache_stats(working_directory: str) -> Dict[str, Any]:
    """Get statistics about test cache."""
    test_cache_file = get_test_cache_path(working_directory)
    hash_cache_file = get_file_hashes_path(working_directory)

    if not test_cache_file.exists():
        return {
            "has_cached_results": False,
            "cache_valid": False,
            "files_tracked": 0
        }

    # Load cached data
    try:
        test_results = json.loads(test_cache_file.read_text())
        file_hashes = json.loads(hash_cache_file.read_text()) if hash_cache_file.exists() else {}

        return {
            "has_cached_results": True,
            "cache_valid": is_cache_valid(test_cache_file),
            "files_tracked": len(file_hashes),
            "last_test_passed": test_results.get('passed', 0),
            "last_test_total": test_results.get('total', 0),
            "last_test_success": test_results.get('success', False)
        }
    except (json.JSONDecodeError, OSError):
        return {
            "has_cached_results": False,
            "cache_valid": False,
            "files_tracked": 0
        }

__all__ = [
    'hash_file',
    'get_source_files',
    'compute_file_hashes',
    'get_cached_test_results',
    'save_test_results_to_cache',
    'clear_test_cache',
    'get_test_cache_stats'
]

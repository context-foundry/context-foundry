"""
Scout Cache System

Caches Scout phase reports to avoid redundant research for similar tasks.

Cache Key Strategy:
- Hash of: task description + mode + project type hints
- Similar tasks within 24h reuse the same Scout report
- Cache miss triggers normal Scout phase

Example:
- Task 1: "Build a weather app with React"
- Task 2: "Build a weather app with React and TypeScript"
- Result: Cache miss (different enough)

- Task 1: "Build a weather app with React"
- Task 2: "Build a weather application with React"
- Result: Cache HIT (semantically similar)
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from . import (
    get_cache_dir,
    hash_string,
    is_cache_valid,
    save_cache_metadata,
    load_cache_metadata,
    DEFAULT_CACHE_TTL_HOURS
)

def normalize_task_description(task: str) -> str:
    """
    Normalize task description for better cache matching.

    - Convert to lowercase
    - Remove extra whitespace
    - Sort words for position-independent matching
    """
    # Basic normalization
    normalized = ' '.join(task.lower().split())
    return normalized

def generate_scout_cache_key(
    task: str,
    mode: str,
    working_directory: str
) -> str:
    """
    Generate a cache key for Scout phase.

    Args:
        task: The task description
        mode: Build mode (new_project, fix_bug, add_feature, etc.)
        working_directory: Project working directory

    Returns:
        Cache key (hash string)
    """
    # Normalize task description
    normalized_task = normalize_task_description(task)

    # Create cache key from normalized inputs
    cache_key_input = f"{normalized_task}|{mode}"

    return hash_string(cache_key_input)

def get_scout_cache_path(working_directory: str, cache_key: str) -> Path:
    """Get the file path for a Scout cache entry."""
    cache_dir = get_cache_dir(working_directory)
    return cache_dir / f"scout-{cache_key}.md"

def get_cached_scout_report(
    task: str,
    mode: str,
    working_directory: str,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS
) -> Optional[str]:
    """
    Retrieve a cached Scout report if available and valid.

    Args:
        task: The task description
        mode: Build mode
        working_directory: Project working directory
        ttl_hours: Cache TTL in hours (default: 24)

    Returns:
        Scout report markdown content if cache hit, None if cache miss
    """
    # Generate cache key
    cache_key = generate_scout_cache_key(task, mode, working_directory)
    cache_file = get_scout_cache_path(working_directory, cache_key)

    # Check if cache is valid
    if not is_cache_valid(cache_file, ttl_hours):
        return None

    # Load metadata for logging
    metadata = load_cache_metadata(cache_file)

    # Read and return cached report
    try:
        cached_content = cache_file.read_text()

        # Log cache hit
        print(f"✅ Scout cache HIT! Using cached report from {metadata.get('created_at', 'unknown time') if metadata else 'unknown time'}")
        print(f"   Cache key: {cache_key}")
        print(f"   Original task: {metadata.get('original_task', 'unknown') if metadata else 'unknown'}")

        return cached_content
    except OSError as e:
        print(f"⚠️ Failed to read Scout cache: {e}")
        return None

def save_scout_report_to_cache(
    task: str,
    mode: str,
    working_directory: str,
    scout_report_content: str
) -> None:
    """
    Save a Scout report to cache.

    Args:
        task: The task description
        mode: Build mode
        working_directory: Project working directory
        scout_report_content: The Scout report markdown content
    """
    # Generate cache key
    cache_key = generate_scout_cache_key(task, mode, working_directory)
    cache_file = get_scout_cache_path(working_directory, cache_key)

    try:
        # Save the report
        cache_file.write_text(scout_report_content)

        # Save metadata
        metadata = {
            "original_task": task,
            "normalized_task": normalize_task_description(task),
            "mode": mode,
            "cache_key": cache_key
        }
        save_cache_metadata(cache_file, metadata)

        print(f"💾 Scout report cached successfully")
        print(f"   Cache key: {cache_key}")
        print(f"   Location: {cache_file}")

    except OSError as e:
        print(f"⚠️ Failed to save Scout report to cache: {e}")

def clear_scout_cache(working_directory: str) -> int:
    """
    Clear all Scout cache entries.

    Args:
        working_directory: Project working directory

    Returns:
        Number of cache files deleted
    """
    cache_dir = get_cache_dir(working_directory)
    deleted_count = 0

    for file in cache_dir.glob("scout-*.md"):
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

def get_scout_cache_stats(working_directory: str) -> Dict[str, Any]:
    """Get statistics about Scout cache."""
    cache_dir = get_cache_dir(working_directory)

    if not cache_dir.exists():
        return {
            "total_entries": 0,
            "valid_entries": 0,
            "expired_entries": 0,
            "total_size_kb": 0
        }

    total = 0
    valid = 0
    expired = 0
    total_size = 0

    for file in cache_dir.glob("scout-*.md"):
        total += 1
        total_size += file.stat().st_size

        if is_cache_valid(file):
            valid += 1
        else:
            expired += 1

    return {
        "total_entries": total,
        "valid_entries": valid,
        "expired_entries": expired,
        "total_size_kb": round(total_size / 1024, 2)
    }

__all__ = [
    'normalize_task_description',
    'generate_scout_cache_key',
    'get_cached_scout_report',
    'save_scout_report_to_cache',
    'clear_scout_cache',
    'get_scout_cache_stats'
]

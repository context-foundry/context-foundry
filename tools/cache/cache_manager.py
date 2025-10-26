"""
Cache Manager

Centralized cache operations including cleanup, statistics, and configuration.

Features:
- Clean up expired cache entries
- Get comprehensive cache statistics
- Manual cache clearing
- Cache configuration management
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from . import (
    get_cache_dir,
    is_cache_valid,
    DEFAULT_CACHE_TTL_HOURS,
    DEFAULT_MAX_CACHE_SIZE_MB
)
from .scout_cache import clear_scout_cache, get_scout_cache_stats
from .test_cache import clear_test_cache, get_test_cache_stats

class CacheManager:
    """Manages all caching operations for Context Foundry."""

    def __init__(self, working_directory: str):
        """
        Initialize cache manager.

        Args:
            working_directory: Project working directory
        """
        self.working_directory = working_directory
        self.cache_dir = get_cache_dir(working_directory)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dict with cache statistics including:
            - scout_cache: Scout cache stats
            - test_cache: Test cache stats
            - total_size_mb: Total cache size in MB
            - total_files: Total number of cache files
        """
        scout_stats = get_scout_cache_stats(self.working_directory)
        test_stats = get_test_cache_stats(self.working_directory)

        # Calculate total size
        total_size = 0
        total_files = 0

        if self.cache_dir.exists():
            for file in self.cache_dir.rglob("*"):
                if file.is_file():
                    total_files += 1
                    total_size += file.stat().st_size

        return {
            "cache_dir": str(self.cache_dir),
            "scout_cache": scout_stats,
            "test_cache": test_stats,
            "total_size_mb": round(total_size / (1024 * 1024), 3),
            "total_files": total_files,
            "created_at": datetime.now().isoformat()
        }

    def clean_expired(self, ttl_hours: int = DEFAULT_CACHE_TTL_HOURS) -> Dict[str, int]:
        """
        Remove expired cache entries.

        Args:
            ttl_hours: Cache TTL in hours

        Returns:
            Dict with deletion counts per cache type
        """
        deleted_scout = 0
        deleted_test = 0
        deleted_other = 0

        if not self.cache_dir.exists():
            return {
                "scout_cache": 0,
                "test_cache": 0,
                "other": 0,
                "total": 0
            }

        for file in self.cache_dir.rglob("*"):
            if not file.is_file() or file.suffix == '.meta.json':
                continue

            if not is_cache_valid(file, ttl_hours):
                try:
                    # Delete cache file
                    file.unlink()

                    # Delete metadata
                    meta_file = file.with_suffix('.meta.json')
                    if meta_file.exists():
                        meta_file.unlink()

                    # Track deletion type
                    if file.name.startswith('scout-'):
                        deleted_scout += 1
                    elif file.name.startswith('test-'):
                        deleted_test += 1
                    else:
                        deleted_other += 1

                except OSError:
                    pass

        total = deleted_scout + deleted_test + deleted_other

        return {
            "scout_cache": deleted_scout,
            "test_cache": deleted_test,
            "other": deleted_other,
            "total": total
        }

    def clear_all(self) -> Dict[str, int]:
        """
        Clear all cache entries.

        Returns:
            Dict with deletion counts per cache type
        """
        deleted_scout = clear_scout_cache(self.working_directory)
        deleted_test = clear_test_cache(self.working_directory)

        return {
            "scout_cache": deleted_scout,
            "test_cache": deleted_test,
            "total": deleted_scout + deleted_test
        }

    def clear_by_type(self, cache_type: str) -> int:
        """
        Clear cache entries of a specific type.

        Args:
            cache_type: Type of cache to clear ('scout', 'test', or 'all')

        Returns:
            Number of files deleted
        """
        if cache_type == 'scout':
            return clear_scout_cache(self.working_directory)
        elif cache_type == 'test':
            return clear_test_cache(self.working_directory)
        elif cache_type == 'all':
            result = self.clear_all()
            return result['total']
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")

    def enforce_size_limit(self, max_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB) -> Dict[str, Any]:
        """
        Enforce maximum cache size by deleting oldest entries.

        Args:
            max_size_mb: Maximum cache size in MB

        Returns:
            Dict with deletion statistics
        """
        if not self.cache_dir.exists():
            return {
                "deleted_files": 0,
                "freed_mb": 0,
                "current_size_mb": 0
            }

        # Get all cache files with sizes and timestamps
        cache_files = []
        total_size = 0

        for file in self.cache_dir.rglob("*"):
            if file.is_file() and file.suffix != '.meta.json':
                size = file.stat().st_size
                mtime = file.stat().st_mtime
                cache_files.append((file, size, mtime))
                total_size += size

        current_size_mb = total_size / (1024 * 1024)

        # If under limit, nothing to do
        if current_size_mb <= max_size_mb:
            return {
                "deleted_files": 0,
                "freed_mb": 0,
                "current_size_mb": round(current_size_mb, 2)
            }

        # Sort by modification time (oldest first)
        cache_files.sort(key=lambda x: x[2])

        # Delete oldest files until under limit
        deleted_count = 0
        freed_size = 0

        for file, size, _ in cache_files:
            if current_size_mb <= max_size_mb:
                break

            try:
                file.unlink()

                # Delete metadata
                meta_file = file.with_suffix('.meta.json')
                if meta_file.exists():
                    meta_file.unlink()

                current_size_mb -= size / (1024 * 1024)
                freed_size += size
                deleted_count += 1

            except OSError:
                pass

        return {
            "deleted_files": deleted_count,
            "freed_mb": round(freed_size / (1024 * 1024), 2),
            "current_size_mb": round(current_size_mb, 2)
        }

    def print_stats(self) -> None:
        """Print cache statistics in a human-readable format."""
        stats = self.get_stats()

        print("📊 Context Foundry Cache Statistics")
        print("=" * 50)
        print(f"Cache directory: {stats['cache_dir']}")
        print(f"Total size: {stats['total_size_mb']:.2f} MB")
        print(f"Total files: {stats['total_files']}")
        print()

        print("Scout Cache:")
        scout = stats['scout_cache']
        print(f"  Total entries: {scout['total_entries']}")
        print(f"  Valid entries: {scout['valid_entries']}")
        print(f"  Expired entries: {scout['expired_entries']}")
        print(f"  Size: {scout['total_size_kb']:.2f} KB")
        print()

        print("Test Cache:")
        test = stats['test_cache']
        print(f"  Has cached results: {test['has_cached_results']}")
        print(f"  Cache valid: {test['cache_valid']}")
        print(f"  Files tracked: {test['files_tracked']}")
        if test['has_cached_results']:
            print(f"  Last test: {test.get('last_test_passed', 0)}/{test.get('last_test_total', 0)} passed")

__all__ = ['CacheManager']

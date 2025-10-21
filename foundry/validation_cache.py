#!/usr/bin/env python3
"""
Validation Cache
Cache validation results based on file hashes to skip redundant validations during retries.
"""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


class ValidationCache:
    """
    Cache validation results to skip redundant checks during retries.

    How it works:
    1. Hash all source files in project
    2. Check cache for validation result with same hash
    3. If cache hit → return cached result
    4. If cache miss → validation runs, result cached

    This can save 50-80% of retry time when Builder only changes a few files.
    """

    def __init__(self, project_dir: Path, cache_dir: Optional[Path] = None):
        """Initialize validation cache.

        Args:
            project_dir: Project directory to cache validations for
            cache_dir: Optional cache directory (defaults to .context-foundry/.validation-cache)
        """
        self.project_dir = Path(project_dir)

        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = self.project_dir / ".context-foundry" / ".validation-cache"

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Directories/files to exclude from hashing
        self.exclude_patterns = [
            'node_modules',
            '.git',
            '.context-foundry',
            '__pycache__',
            '.pytest_cache',
            '.venv',
            'venv',
            'dist',
            'build',
            '.next',
            '.cache',
            'coverage',
            '*.pyc',
            '*.pyo',
            '*.log',
            '.DS_Store',
            'package-lock.json',  # Don't hash lock files
            'yarn.lock',
            'pnpm-lock.yaml'
        ]

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from hashing.

        Args:
            path: Path to check

        Returns:
            True if should exclude
        """
        path_str = str(path)

        # Check exclusion patterns
        for pattern in self.exclude_patterns:
            if pattern.startswith('*'):
                # Wildcard pattern (e.g., *.pyc)
                if path_str.endswith(pattern[1:]):
                    return True
            else:
                # Directory or exact match
                if pattern in path_str.split('/'):
                    return True

        return False

    def _hash_files(self, include_patterns: Optional[List[str]] = None) -> str:
        """Generate hash of all source files in project.

        Args:
            include_patterns: Optional list of glob patterns to include (e.g., ['src/**/*.ts'])

        Returns:
            SHA256 hash of all file contents
        """
        hasher = hashlib.sha256()

        # If no include patterns, hash everything (excluding excludes)
        if not include_patterns:
            files = sorted(self.project_dir.rglob('*'))
        else:
            # Use specific patterns
            files = []
            for pattern in include_patterns:
                files.extend(self.project_dir.glob(pattern))
            files = sorted(set(files))  # Remove duplicates

        # Hash each file
        hashed_count = 0
        for file_path in files:
            # Skip if not a file
            if not file_path.is_file():
                continue

            # Skip excluded paths
            if self._should_exclude(file_path):
                continue

            try:
                # Read and hash file contents
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()

                # Include relative path in hash (so renaming files invalidates cache)
                rel_path = file_path.relative_to(self.project_dir)
                hasher.update(str(rel_path).encode())
                hasher.update(file_hash.encode())

                hashed_count += 1

            except Exception as e:
                # Skip files we can't read (binary, permissions, etc.)
                continue

        return hasher.hexdigest()

    def _get_cache_file(self, validation_type: str) -> Path:
        """Get cache file path for validation type.

        Args:
            validation_type: Type of validation (build, static, runtime, browser)

        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{validation_type}.json"

    def get_cached_result(
        self,
        validation_type: str,
        max_age_seconds: int = 3600
    ) -> Optional[Tuple[bool, Dict[str, Any]]]:
        """Get cached validation result if available.

        Args:
            validation_type: Type of validation (build, static, runtime, browser)
            max_age_seconds: Maximum age of cache entry in seconds (default 1 hour)

        Returns:
            Tuple of (success, error_details) if cache hit, None if cache miss
        """
        try:
            # Calculate current file hash
            current_hash = self._hash_files()

            # Load cache file
            cache_file = self._get_cache_file(validation_type)
            if not cache_file.exists():
                return None

            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            # Check if hash matches
            if cache_data.get('file_hash') != current_hash:
                return None

            # Check if cache is too old
            timestamp = cache_data.get('timestamp', 0)
            age = time.time() - timestamp

            if age > max_age_seconds:
                return None

            # Cache hit!
            success = cache_data.get('success', False)
            error_details = cache_data.get('error_details', {})

            return (success, error_details)

        except Exception as e:
            # On any error, return cache miss
            return None

    def store_result(
        self,
        validation_type: str,
        success: bool,
        error_details: Dict[str, Any]
    ):
        """Store validation result in cache.

        Args:
            validation_type: Type of validation (build, static, runtime, browser)
            success: Whether validation succeeded
            error_details: Error details if validation failed
        """
        try:
            # Calculate current file hash
            current_hash = self._hash_files()

            # Prepare cache entry
            cache_entry = {
                'file_hash': current_hash,
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'validation_type': validation_type,
                'success': success,
                'error_details': error_details
            }

            # Write to cache file
            cache_file = self._get_cache_file(validation_type)
            with open(cache_file, 'w') as f:
                json.dump(cache_entry, f, indent=2)

        except Exception as e:
            # Silently fail - caching is an optimization, not critical
            pass

    def invalidate(self, validation_type: Optional[str] = None):
        """Invalidate cache entries.

        Args:
            validation_type: Specific validation type to invalidate, or None for all
        """
        try:
            if validation_type:
                # Invalidate specific type
                cache_file = self._get_cache_file(validation_type)
                if cache_file.exists():
                    cache_file.unlink()
            else:
                # Invalidate all
                for cache_file in self.cache_dir.glob('*.json'):
                    cache_file.unlink()

        except Exception as e:
            # Silently fail
            pass

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        stats = {
            'cache_dir': str(self.cache_dir),
            'entries': {}
        }

        for validation_type in ['build', 'static', 'runtime', 'browser']:
            cache_file = self._get_cache_file(validation_type)

            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)

                    timestamp = cache_data.get('timestamp', 0)
                    age = time.time() - timestamp

                    stats['entries'][validation_type] = {
                        'exists': True,
                        'age_seconds': int(age),
                        'age_minutes': int(age / 60),
                        'success': cache_data.get('success', False),
                        'datetime': cache_data.get('datetime', 'Unknown')
                    }
                except Exception:
                    stats['entries'][validation_type] = {'exists': True, 'error': 'Failed to read'}
            else:
                stats['entries'][validation_type] = {'exists': False}

        return stats

    def print_stats(self):
        """Print cache statistics."""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("📦 VALIDATION CACHE STATS")
        print("="*60)
        print(f"Cache directory: {stats['cache_dir']}")
        print()

        for validation_type, entry in stats['entries'].items():
            if entry.get('exists'):
                if 'error' in entry:
                    print(f"  ❌ {validation_type}: {entry['error']}")
                else:
                    success_icon = "✅" if entry.get('success') else "❌"
                    age_str = f"{entry.get('age_minutes', 0)}m ago"
                    print(f"  {success_icon} {validation_type}: {age_str} ({entry.get('datetime', 'Unknown')})")
            else:
                print(f"  ⚪ {validation_type}: No cache entry")

        print("="*60)


def main():
    """Test validation cache."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validation_cache.py <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])

    print(f"Testing ValidationCache for: {project_dir}\n")

    # Initialize cache
    cache = ValidationCache(project_dir)

    # Show current stats
    cache.print_stats()

    # Test caching
    print("\n🧪 Testing cache operations...\n")

    # Store a test result
    print("1. Storing test validation result...")
    cache.store_result(
        validation_type='build',
        success=True,
        error_details={}
    )

    # Retrieve it
    print("2. Retrieving cached result...")
    result = cache.get_cached_result('build')

    if result:
        success, error_details = result
        print(f"   ✅ Cache hit! Success: {success}")
    else:
        print("   ❌ Cache miss")

    # Show updated stats
    print("\n3. Updated stats:")
    cache.print_stats()

    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()

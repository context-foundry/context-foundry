"""
Context Foundry Cache System

Provides intelligent caching for Scout reports, Architect plans, and test results
to enable 30-50% faster builds on repeated/similar tasks.

Features:
- Scout cache: Reuse research for similar tasks
- Architect cache: Skip re-planning for small changes
- Test cache: Skip tests when no code changed
- TTL-based expiration
- Automatic cleanup
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# Default cache configuration
DEFAULT_CACHE_TTL_HOURS = 24
DEFAULT_MAX_CACHE_SIZE_MB = 100

def get_cache_dir(working_directory: str) -> Path:
    """Get the cache directory for a project."""
    cache_dir = Path(working_directory) / ".context-foundry" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def hash_string(text: str) -> str:
    """Generate a SHA256 hash of a string."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

def is_cache_valid(cache_file: Path, ttl_hours: int = DEFAULT_CACHE_TTL_HOURS) -> bool:
    """Check if a cache file exists and is within TTL."""
    if not cache_file.exists():
        return False

    # Check file age
    file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
    return file_age < timedelta(hours=ttl_hours)

def save_cache_metadata(cache_file: Path, metadata: Dict[str, Any]) -> None:
    """Save metadata alongside a cache file."""
    meta_file = cache_file.with_suffix('.meta.json')
    meta_data = {
        **metadata,
        "created_at": datetime.now().isoformat(),
        "cache_file": cache_file.name
    }
    meta_file.write_text(json.dumps(meta_data, indent=2))

def load_cache_metadata(cache_file: Path) -> Optional[Dict[str, Any]]:
    """Load metadata for a cache file."""
    meta_file = cache_file.with_suffix('.meta.json')
    if not meta_file.exists():
        return None

    try:
        return json.loads(meta_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None

def get_cache_stats(working_directory: str) -> Dict[str, Any]:
    """Get cache statistics for a project."""
    cache_dir = get_cache_dir(working_directory)

    if not cache_dir.exists():
        return {
            "cache_dir": str(cache_dir),
            "total_files": 0,
            "total_size_mb": 0,
            "scout_cache_files": 0,
            "test_cache_files": 0,
            "expired_files": 0
        }

    total_files = 0
    total_size = 0
    scout_files = 0
    test_files = 0
    expired_files = 0

    for file in cache_dir.rglob("*"):
        if file.is_file() and not file.name.endswith('.meta.json'):
            total_files += 1
            total_size += file.stat().st_size

            if file.name.startswith('scout-'):
                scout_files += 1
            elif file.name.startswith('test-'):
                test_files += 1

            if not is_cache_valid(file):
                expired_files += 1

    return {
        "cache_dir": str(cache_dir),
        "total_files": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "scout_cache_files": scout_files,
        "test_cache_files": test_files,
        "expired_files": expired_files
    }

__all__ = [
    'get_cache_dir',
    'hash_string',
    'is_cache_valid',
    'save_cache_metadata',
    'load_cache_metadata',
    'get_cache_stats',
    'DEFAULT_CACHE_TTL_HOURS',
    'DEFAULT_MAX_CACHE_SIZE_MB'
]

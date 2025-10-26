"""
Context Foundry Cache System

Phase 1: Local caching for 10-40% speedup
Phase 2: Global caching + incremental builds for 70-90% speedup

Features:
- Scout cache (Phase 1): Reuse research for similar tasks (local)
- Global Scout cache (Phase 2): Cross-project Scout sharing
- Test cache (Phase 1): Skip tests when no code changed
- Change detection (Phase 2): File-level change tracking
- Incremental Builder (Phase 2): Smart file preservation
- Test impact analysis (Phase 2): Selective test execution
- Incremental docs (Phase 2): Selective documentation updates
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

# Re-export Phase 2 incremental modules
from ..incremental import (
    # Global Scout Cache
    get_global_cache_dir,
    generate_global_scout_key,
    get_cached_scout_report_global,
    save_scout_report_to_global_cache,
    find_similar_cached_reports,
    clear_global_scout_cache,
    get_global_scout_cache_stats,
    # Change Detector
    ChangeReport,
    capture_build_snapshot,
    detect_changes,
    get_last_build_snapshot_path,
    # Incremental Builder
    BuildPlan,
    DependencyGraph,
    build_dependency_graph,
    find_affected_files,
    create_incremental_build_plan,
    preserve_unchanged_files,
    # Test Impact Analyzer
    TestPlan,
    TestCoverageMap,
    build_test_coverage_map,
    find_affected_tests,
    create_test_plan,
    # Incremental Docs
    DocsPlan,
    DocsManifest,
    build_docs_manifest,
    find_affected_docs,
    create_docs_plan,
)

__all__ = [
    # Phase 1 - Local cache utilities
    'get_cache_dir',
    'hash_string',
    'is_cache_valid',
    'save_cache_metadata',
    'load_cache_metadata',
    'get_cache_stats',
    'DEFAULT_CACHE_TTL_HOURS',
    'DEFAULT_MAX_CACHE_SIZE_MB',
    # Phase 2 - Global Scout Cache
    'get_global_cache_dir',
    'generate_global_scout_key',
    'get_cached_scout_report_global',
    'save_scout_report_to_global_cache',
    'find_similar_cached_reports',
    'clear_global_scout_cache',
    'get_global_scout_cache_stats',
    # Phase 2 - Change Detection
    'ChangeReport',
    'capture_build_snapshot',
    'detect_changes',
    'get_last_build_snapshot_path',
    # Phase 2 - Incremental Builder
    'BuildPlan',
    'DependencyGraph',
    'build_dependency_graph',
    'find_affected_files',
    'create_incremental_build_plan',
    'preserve_unchanged_files',
    # Phase 2 - Test Impact Analysis
    'TestPlan',
    'TestCoverageMap',
    'build_test_coverage_map',
    'find_affected_tests',
    'create_test_plan',
    # Phase 2 - Incremental Docs
    'DocsPlan',
    'DocsManifest',
    'build_docs_manifest',
    'find_affected_docs',
    'create_docs_plan',
]

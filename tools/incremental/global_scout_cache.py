"""
Global Scout Cache - Phase 2

Share Scout analysis cache across ALL projects for 80-95% faster Scout phase.

Strategy:
- Global cache location: ~/.context-foundry/global-cache/scout/
- Cache key: hash(normalized_task + project_type + tech_stack)
- 7-day TTL (longer than local cache)
- Semantic similarity matching for cache hits
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

DEFAULT_GLOBAL_CACHE_TTL_HOURS = 168  # 7 days


def hash_string(text: str) -> str:
    """Generate a SHA256 hash of a string."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def get_global_cache_dir() -> Path:
    """
    Get global cache directory (shared across all projects).

    Returns:
        Path to ~/.context-foundry/global-cache/scout/
    """
    home = Path.home()
    cache_dir = home / ".context-foundry" / "global-cache" / "scout"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def normalize_task_description(task: str) -> str:
    """
    Normalize task description for better cache matching.

    Args:
        task: Raw task description

    Returns:
        Normalized task string (lowercase, sorted words)
    """
    # Convert to lowercase and remove extra whitespace
    normalized = ' '.join(task.lower().split())
    return normalized


def extract_tech_keywords(text: str) -> List[str]:
    """
    Extract technology keywords from text.

    Args:
        text: Task description or text

    Returns:
        List of technology keywords
    """
    # Common tech keywords
    tech_keywords = {
        'react', 'vue', 'angular', 'svelte', 'next', 'nuxt',
        'python', 'javascript', 'typescript', 'rust', 'go', 'java',
        'flask', 'django', 'fastapi', 'express', 'koa',
        'postgresql', 'mysql', 'mongodb', 'redis', 'sqlite',
        'docker', 'kubernetes', 'aws', 'gcp', 'azure',
        'es6', 'es5', 'html5', 'css3', 'sass', 'tailwind',
        'webpack', 'vite', 'rollup', 'parcel',
        'jest', 'pytest', 'mocha', 'chai'
    }

    text_lower = text.lower()
    found_keywords = []

    for keyword in tech_keywords:
        if keyword in text_lower:
            found_keywords.append(keyword)

    return sorted(set(found_keywords))


def generate_global_scout_key(
    task: str,
    project_type: str,
    tech_stack: List[str]
) -> str:
    """
    Generate global cache key from semantic components.

    Args:
        task: Task description
        project_type: Type of project (web-app, cli-tool, api, etc.)
        tech_stack: List of technologies

    Returns:
        Cache key (hash string)
    """
    # Normalize inputs
    normalized_task = normalize_task_description(task)
    normalized_project_type = project_type.lower().strip()
    normalized_tech = sorted([t.lower().strip() for t in tech_stack])

    # Create cache key input
    cache_key_input = f"{normalized_task}|{normalized_project_type}|{','.join(normalized_tech)}"

    return hash_string(cache_key_input)


def get_cache_entry_path(cache_key: str) -> Path:
    """Get file path for a cache entry."""
    cache_dir = get_global_cache_dir()
    return cache_dir / f"cache-{cache_key}.json"


def is_cache_entry_valid(cache_file: Path, ttl_hours: int) -> bool:
    """Check if cache entry exists and is within TTL."""
    if not cache_file.exists():
        return False

    # Check TTL
    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
    age = datetime.now() - mtime
    return age < timedelta(hours=ttl_hours)


def get_cached_scout_report_global(
    task: str,
    project_type: str,
    tech_stack: List[str],
    ttl_hours: int = DEFAULT_GLOBAL_CACHE_TTL_HOURS
) -> Optional[str]:
    """
    Retrieve cached Scout report from global cache.

    Args:
        task: Task description
        project_type: Project type
        tech_stack: List of technologies
        ttl_hours: Cache TTL in hours (default: 168 = 7 days)

    Returns:
        Scout report markdown if cache hit, None if cache miss
    """
    # Generate cache key
    cache_key = generate_global_scout_key(task, project_type, tech_stack)
    cache_file = get_cache_entry_path(cache_key)

    # Check if valid
    if not is_cache_entry_valid(cache_file, ttl_hours):
        return None

    # Load cache entry
    try:
        entry = json.loads(cache_file.read_text())

        # Update access stats
        entry['accessed_count'] = entry.get('accessed_count', 0) + 1
        entry['last_accessed'] = datetime.now().isoformat()
        cache_file.write_text(json.dumps(entry, indent=2))

        # Log cache hit
        print(f"✅ Global Scout cache HIT! Reusing report from {entry.get('created_at', 'unknown')}")
        print(f"   Cache key: {cache_key}")
        print(f"   Original task: {entry.get('task', 'unknown')}")
        print(f"   Project type: {entry.get('project_type', 'unknown')}")
        print(f"   Tech stack: {', '.join(entry.get('tech_stack', []))}")
        print(f"   Access count: {entry['accessed_count']}")

        return entry['scout_report']

    except (json.JSONDecodeError, OSError, KeyError) as e:
        print(f"⚠️  Failed to read global Scout cache: {e}")
        return None


def save_scout_report_to_global_cache(
    task: str,
    project_type: str,
    tech_stack: List[str],
    scout_report: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Save Scout report to global cache.

    Args:
        task: Task description
        project_type: Project type
        tech_stack: List of technologies
        scout_report: Scout report markdown content
        metadata: Optional metadata about the build
    """
    # Generate cache key
    cache_key = generate_global_scout_key(task, project_type, tech_stack)
    cache_file = get_cache_entry_path(cache_key)

    # Extract additional tech keywords from task
    detected_tech = extract_tech_keywords(task)
    full_tech_stack = sorted(set(tech_stack + detected_tech))

    # Create cache entry
    entry = {
        "cache_key": cache_key,
        "task": task,
        "normalized_task": normalize_task_description(task),
        "project_type": project_type,
        "tech_stack": full_tech_stack,
        "created_at": datetime.now().isoformat(),
        "accessed_count": 0,
        "last_accessed": datetime.now().isoformat(),
        "scout_report": scout_report,
        "metadata": metadata or {}
    }

    try:
        # Save entry
        cache_file.write_text(json.dumps(entry, indent=2))

        print(f"💾 Scout report saved to global cache")
        print(f"   Cache key: {cache_key}")
        print(f"   Location: {cache_file}")
        print(f"   Project type: {project_type}")
        print(f"   Tech stack: {', '.join(full_tech_stack)}")

    except OSError as e:
        print(f"⚠️  Failed to save to global Scout cache: {e}")


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two texts (simple word overlap).

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0.0 to 1.0)
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    return len(intersection) / len(union) if union else 0.0


def find_similar_cached_reports(
    task: str,
    project_type: str,
    tech_stack: List[str],
    similarity_threshold: float = 0.85,
    ttl_hours: int = DEFAULT_GLOBAL_CACHE_TTL_HOURS
) -> List[Tuple[str, float, Dict[str, Any]]]:
    """
    Find similar cached reports by semantic similarity.

    Args:
        task: Task description
        project_type: Project type
        tech_stack: List of technologies
        similarity_threshold: Minimum similarity score (0.0 to 1.0)
        ttl_hours: Cache TTL in hours

    Returns:
        List of (cache_key, similarity_score, entry_data) tuples
    """
    cache_dir = get_global_cache_dir()
    normalized_task = normalize_task_description(task)
    similar_reports = []

    # Iterate through all cache entries
    for cache_file in cache_dir.glob("cache-*.json"):
        if not is_cache_entry_valid(cache_file, ttl_hours):
            continue

        try:
            entry = json.loads(cache_file.read_text())

            # Check project type match
            if entry.get('project_type') != project_type:
                continue

            # Calculate task similarity
            cached_task = entry.get('normalized_task', '')
            similarity = calculate_similarity(normalized_task, cached_task)

            # Check tech stack overlap
            cached_tech = set(entry.get('tech_stack', []))
            query_tech = set(tech_stack)
            tech_overlap = len(cached_tech.intersection(query_tech)) / len(query_tech) if query_tech else 0

            # Combined score (70% task similarity + 30% tech overlap)
            combined_score = (similarity * 0.7) + (tech_overlap * 0.3)

            if combined_score >= similarity_threshold:
                similar_reports.append((
                    entry['cache_key'],
                    combined_score,
                    entry
                ))

        except (json.JSONDecodeError, KeyError):
            continue

    # Sort by similarity score (descending)
    similar_reports.sort(key=lambda x: x[1], reverse=True)

    return similar_reports


def clear_global_scout_cache() -> int:
    """
    Clear all global Scout cache entries.

    Returns:
        Number of cache files deleted
    """
    cache_dir = get_global_cache_dir()
    deleted_count = 0

    for cache_file in cache_dir.glob("cache-*.json"):
        try:
            cache_file.unlink()
            deleted_count += 1
        except OSError:
            pass

    return deleted_count


def get_global_scout_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about global Scout cache.

    Returns:
        Dict with cache statistics
    """
    cache_dir = get_global_cache_dir()

    if not cache_dir.exists():
        return {
            "total_entries": 0,
            "valid_entries": 0,
            "expired_entries": 0,
            "total_size_mb": 0,
            "project_types": {},
            "most_popular_tech": []
        }

    total = 0
    valid = 0
    expired = 0
    total_size = 0
    project_types = {}
    tech_counter = {}

    for cache_file in cache_dir.glob("cache-*.json"):
        total += 1
        total_size += cache_file.stat().st_size

        if is_cache_entry_valid(cache_file, DEFAULT_GLOBAL_CACHE_TTL_HOURS):
            valid += 1

            # Parse entry for stats
            try:
                entry = json.loads(cache_file.read_text())
                proj_type = entry.get('project_type', 'unknown')
                project_types[proj_type] = project_types.get(proj_type, 0) + 1

                for tech in entry.get('tech_stack', []):
                    tech_counter[tech] = tech_counter.get(tech, 0) + 1
            except (json.JSONDecodeError, OSError):
                pass
        else:
            expired += 1

    # Get most popular technologies
    most_popular_tech = sorted(tech_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_entries": total,
        "valid_entries": valid,
        "expired_entries": expired,
        "total_size_mb": round(total_size / (1024 * 1024), 3),
        "project_types": project_types,
        "most_popular_tech": [{"tech": tech, "count": count} for tech, count in most_popular_tech]
    }


__all__ = [
    'get_global_cache_dir',
    'generate_global_scout_key',
    'get_cached_scout_report_global',
    'save_scout_report_to_global_cache',
    'find_similar_cached_reports',
    'clear_global_scout_cache',
    'get_global_scout_cache_stats'
]

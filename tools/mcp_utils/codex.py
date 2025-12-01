"""
Codex: The Knowledge Retrieval Module for Context Foundry.

This module provides an interface to search and retrieve patterns, issues, and learnings
from the Context Foundry Codex.

Data Sources:
1. Local JSON files in ~/.context-foundry/patterns/ (Default)
2. SQLite Database (Future)
3. AWS S3 (Future)
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Define the base path for local patterns
PATTERNS_DIR = Path.home() / ".context-foundry" / "patterns"


def _load_local_patterns(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load patterns from local JSON files."""
    all_patterns = []

    if not PATTERNS_DIR.exists():
        return []

    files_to_read = []
    if category:
        # Try to find specific file (exact match or with .json extension)
        candidates = [PATTERNS_DIR / category, PATTERNS_DIR / f"{category}.json"]
        for f in candidates:
            if f.exists():
                files_to_read.append(f)
                break
    else:
        # Read all json files
        files_to_read = list(PATTERNS_DIR.glob("*.json"))

    for fpath in files_to_read:
        try:
            content = fpath.read_text()
            if not content.strip():
                continue

            data = json.loads(content)

            # Handle different schemas
            # Schema 1: {"patterns": [...]}
            if (
                isinstance(data, dict)
                and "patterns" in data
                and isinstance(data["patterns"], list)
            ):
                all_patterns.extend(data["patterns"])
            # Schema 2: {"entries": [...]}
            elif (
                isinstance(data, dict)
                and "entries" in data
                and isinstance(data["entries"], list)
            ):
                all_patterns.extend(data["entries"])
            # Schema 3: List at root
            elif isinstance(data, list):
                all_patterns.extend(data)

        except Exception:
            # print(f"Error reading {fpath}: {e}", file=sys.stderr)
            continue

    return all_patterns


def codex_search(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Search the Codex for patterns matching the query.

    Args:
        query: Search terms
        category: Optional category (filename base) to filter by

    Returns:
        Dict with 'entries' list containing matching items
    """
    # TODO: Add S3 and SQLite support here
    # For now, we implement the Local JSON provider as the primary source

    patterns = _load_local_patterns(category)
    results = []

    query_lower = query.lower()
    terms = query_lower.split()

    for p in patterns:
        # Construct searchable text from relevant fields
        searchable_text = []
        if p.get("title"):
            searchable_text.append(p["title"])
        if p.get("description"):
            searchable_text.append(p["description"])
        if p.get("symptoms"):
            searchable_text.extend(p["symptoms"])
        if p.get("tags"):
            searchable_text.extend(p["tags"])

        text = " ".join(searchable_text).lower()

        score = 0
        matches = 0
        for term in terms:
            if term in text:
                matches += 1
                # Higher weight for title matches
                if p.get("title") and term in p["title"].lower():
                    score += 3
                else:
                    score += 1

        # Require at least one term match
        if matches > 0:
            p["_score"] = score
            results.append(p)

    # Sort by score descending
    results.sort(key=lambda x: x.get("_score", 0), reverse=True)

    # Remove internal score field from output
    final_results = []
    for r in results:
        r_copy = r.copy()
        r_copy.pop("_score", None)
        final_results.append(r_copy)

    return {"entries": final_results}


def codex_get_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific entry by ID.

    Args:
        entry_id: The unique identifier of the entry

    Returns:
        The entry dict or None if not found
    """
    patterns = _load_local_patterns()
    for p in patterns:
        if p.get("id") == entry_id:
            return p
    return None

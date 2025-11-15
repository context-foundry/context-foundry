# Context Codex Export Tool

## Overview

Context Foundry has **two pattern storage systems**:

1. **Context Codex** (`~/.context-foundry/codex.db`) - Modern SQLite database with full-text search
2. **Pattern JSON Files** (`~/.context-foundry/patterns/*.json`) - Legacy files that sync to S3

This document explains how to export entries from the Codex database to the JSON files, making them available to agents during builds and syncing them to S3 for community sharing.

---

## Why Export?

**The Problem:**
- Entries added via `codex_add_issue()` and `codex_add_pattern()` go into the **Codex database**
- Scout/Architect/Builder agents read from **JSON files** during builds
- S3 community sync only uploads **JSON files**
- **The two systems don't talk to each other**

**The Solution:**
- Use `export_codex_to_patterns()` to bridge the gap
- Export from Codex → JSON → S3
- Makes your lessons available to future builds and the community

---

## Quick Start

### Via MCP Tool (Claude Code)

```python
# Export all codex entries and sync to S3
export_codex_to_patterns()

# Export only issues
export_codex_to_patterns(pattern_type="issues")

# Export without S3 sync
export_codex_to_patterns(sync_to_s3=False)
```

### Via Python

```python
from tools.mcp_utils.codex_export import export_codex_to_patterns_impl

# Export and get detailed results
result = export_codex_to_patterns_impl("all")
print(result["message"])
# Output: Exported 41 new entries and updated 0 existing entries
```

---

## How It Works

### 1. Export Process

The exporter:
1. Queries Codex database for all entries of specified type
2. Converts Codex schema → JSON pattern schema
3. Merges into existing JSON files (preserves existing patterns)
4. Handles duplicates by incrementing frequency
5. Optionally syncs to S3 with versioning

### 2. Schema Mapping

**Codex Issue → JSON Pattern:**
```python
{
  "id": "aws-boto3-forced-as",              # Cleaned from iss-aws-boto3-forced-as-118
  "issue": "AWS boto3 forced as required...", # From codex title
  "frequency": 1,                            # From codex frequency
  "severity": "medium",                      # From codex severity
  "solution": "Create separate requirements-aws.txt...", # From codex solutions table
  "project_types": ["python", "aws"],        # From codex project_types
  "last_seen": "2025-11-15T10:55:46",       # From codex timestamps
  "codex_id": "iss-aws-boto3-forced-as-118", # Reference to original
  "tags": ["aws", "dependencies"]            # From codex tags
}
```

**Codex Pattern → Architecture Pattern:**
```python
{
  "pattern_id": "optional-aws-integration-with", # Cleaned ID
  "title": "Optional AWS Integration...",      # From codex title
  "description": "Pattern for integrating...", # From codex description
  "category": "aws-integration",               # From codex category
  "project_types": ["python", "aws"],          # From codex project_types
  "frequency": 1,                              # From codex frequency
  "success_rate": "100%",                      # Default
  "first_seen": "2025-11-15T10:56:15",        # From codex created_at
  "last_seen": "2025-11-15T10:56:15",         # From codex updated_at
  "codex_id": "pat-optional-aws-integration-with-561"
}
```

### 3. Deduplication

When a pattern already exists in the JSON file:
- **Frequency**: Incremented
- **Last Seen**: Updated to latest timestamp
- **Project Types**: Merged (union of both)
- **Severity**: Highest severity preserved
- **Solution**: Updated from codex

---

## What Gets Exported

### Current Codex → JSON Mapping

| Codex Entry Type | Exports To | Use Case |
|------------------|------------|----------|
| `ISSUE` | `common-issues.json` | Problems encountered during builds |
| `PATTERN` | `architecture-patterns.json` | Best practices and solutions |

### Export Results (Example)

```json
{
  "success": true,
  "exports": [
    {
      "file": "/Users/name/.context-foundry/patterns/common-issues.json",
      "total_patterns": 58,
      "added": 31,
      "updated": 0
    },
    {
      "file": "/Users/name/.context-foundry/patterns/architecture-patterns.json",
      "total_patterns": 14,
      "added": 10,
      "updated": 0
    }
  ],
  "total_added": 41,
  "total_updated": 0,
  "s3_sync": [
    {
      "pattern_type": "common-issues",
      "success": true,
      "version_id": "4_iWv6qtfNul5UPed.RT...",
      "s3_uri": "s3://bedrock-builder-kb-898587418237/community-patterns/common-issues.json"
    }
  ]
}
```

---

## S3 Sync

### Automatic Sync

By default, `export_codex_to_patterns()` automatically syncs to S3:

```python
export_codex_to_patterns()  # Auto-syncs to S3
```

### Manual Sync

If you want to export without S3 sync:

```python
export_codex_to_patterns(sync_to_s3=False)

# Later, manually sync
from context_foundry.storage import S3PatternClient
client = S3PatternClient()
client.upload_pattern("common-issues", force=True)
```

### Verification

Check what's in S3:

```python
from context_foundry.storage import S3PatternClient
client = S3PatternClient()

# List all patterns
result = client.list_community_patterns()
print(f"Found {result['count']} pattern types in S3")

# Download and inspect
result = client.download_pattern("common-issues")
print(f"Total patterns: {result['item_count']}")
```

---

## Use Cases

### 1. After Adding Lessons to Codex

```python
# Add lessons learned during a project
codex_add_issue(
    "AWS boto3 forced as required dependency",
    "Description...",
    severity="MEDIUM",
    tags=["aws", "dependencies"],
    solution_description="Create separate requirements-aws.txt..."
)

# Export to make available for future builds
export_codex_to_patterns()
```

### 2. Periodic Codex → S3 Sync

```bash
# Cron job or manual run
source venv/bin/activate
python3 -c "from tools.mcp_utils.codex_export import export_codex_to_patterns_impl; \
  result = export_codex_to_patterns_impl('all'); \
  print(result['message'])"
```

### 3. Before Sharing Patterns with Community

```python
# Export your local codex learnings
export_codex_to_patterns()

# Patterns are now in S3 for community to download
```

---

## Implementation Details

### Files Created

1. **`tools/mcp_utils/codex_export.py`**
   - `CodexExporter` class
   - Export logic and schema mapping
   - Deduplication and merging

2. **`tools/mcp_server.py`** (modified)
   - `export_codex_to_patterns()` MCP tool
   - Integration with S3 sync

### Key Functions

```python
class CodexExporter:
    def export_issues_to_common_issues() -> Dict
    def export_patterns_to_architecture() -> Dict
    def export_all() -> Dict

    def _codex_issue_to_json_pattern(entry) -> Dict
    def _codex_pattern_to_json_pattern(entry) -> Dict
    def _codex_id_to_json_id(codex_id: str) -> str
```

---

## Troubleshooting

### Export Fails with "No such table"

**Problem**: Codex database not initialized

**Solution**:
```python
from context_foundry.codex.store import KnowledgeStore
from pathlib import Path

# Initialize codex
db_path = Path.home() / ".context-foundry" / "codex.db"
store = KnowledgeStore(db_path)
```

### S3 Sync Disabled

**Problem**: `boto3` not installed

**Solution**:
```bash
pip install -r requirements-aws.txt
```

### Patterns Not Appearing in Builds

**Problem**: Agents cache pattern files

**Solution**: Restart the build or clear cache:
```bash
rm -rf ~/.context-foundry/cache/*
```

---

## Future Enhancements

### Potential Improvements

1. **Bi-directional Sync**
   - Import JSON patterns → Codex
   - Keep both systems in sync automatically

2. **Incremental Export**
   - Only export entries modified since last export
   - Track sync timestamps

3. **Additional Pattern Types**
   - Export skills to `skills.json`
   - Export build metrics to `build-metrics.json`

4. **Auto-Export Hook**
   - Automatically export when new codex entries added
   - Background sync after builds complete

---

## Related Documentation

- [AWS Migration Guide](AWS_MIGRATION.md) - S3 integration overview
- [Testing Guide](TESTING.md) - Test coverage for export functionality
- [Pattern Management](../tools/mcp_utils/pattern_management.py) - Pattern merging logic

---

*Last Updated: 2025-11-15*
*Export Tool Version: 1.0.0*

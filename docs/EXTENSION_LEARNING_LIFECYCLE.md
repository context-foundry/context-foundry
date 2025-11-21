# Extension Learning Lifecycle

**How new learnings flow through Context Foundry's knowledge system**

Context Foundry uses a **three-tier knowledge architecture** with multiple pathways for capturing, sharing, and distributing learnings.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE FLOW ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────┘

   LOCAL LEARNING          EXTENSION PATTERNS       GLOBAL CODEX        COMMUNITY
   (During Builds)         (JSON Files)             (SQLite)            (S3 Bucket)

┌──────────────┐         ┌──────────────────┐    ┌──────────────┐    ┌────────────┐
│              │         │  roblox-         │    │              │    │            │
│  Project     │────1───>│  expertise.json  │───2>│  codex.db    │───3>│  S3 Repo   │
│  Builds      │         │                  │    │              │    │            │
│              │         │  flowise-        │    │  (Centralized│    │ Community  │
│              │         │  expertise.json  │    │   Knowledge) │    │  Patterns  │
└──────────────┘         └──────────────────┘    └──────────────┘    └────────────┘
                                  ^                      │                   │
                                  │                      │                   │
                                  └──────────4───────────┘                   │
                                      (Export)                               │
                                                                              │
                                  ┌───────────5────────────────────────────┘
                                  │ (Pull patterns from community)
                                  v
                        ┌──────────────────┐
                        │  Other Developers│
                        │  Download &      │
                        │  Contribute Back │
                        └──────────────────┘
```

## Tier 1: Extension Pattern Files (JSON)

**Location:** `extensions/{extension_name}/patterns/*.json`

**Examples:**
- `extensions/roblox/patterns/roblox-expertise.json`
- `extensions/flowise/patterns/flowise-expertise.json`

**Purpose:** Extension-specific knowledge repository

### How to Add New Learnings to Extension Patterns

#### Method 1: Manual Edit (Simplest)

1. **Open the pattern file:**
   ```bash
   # For Roblox
   code extensions/roblox/patterns/roblox-expertise.json

   # For Flowise
   code extensions/flowise/patterns/flowise-expertise.json
   ```

2. **Add new pattern:**
   ```json
   {
     "pattern_id": "roblox-new-learning-example",
     "title": "New Roblox Pattern Discovered",
     "category": "performance",
     "description": "Detailed description of what was learned",
     "severity": "MEDIUM",
     "project_types": ["roblox-game"],
     "tags": ["performance", "optimization"],
     "code_example": "-- Your example code here",
     "solution": "How to solve this issue",
     "frequency": 1,
     "last_seen": "2025-11-17T10:00:00Z"
   }
   ```

3. **Add new issue (if it's a problem to avoid):**
   ```json
   {
     "issue_id": "roblox-new-issue-001",
     "title": "DataStore throttling in loops",
     "description": "Calling DataStore too frequently causes throttling",
     "severity": "HIGH",
     "project_types": ["roblox-game"],
     "tags": ["datastore", "throttling"],
     "symptoms": [
       "502 errors from DataStore",
       "Players lose data on rejoin"
     ],
     "solution": {
       "description": "Batch updates and use rate limiting",
       "code_example": "-- Use UpdateAsync with batched data"
     },
     "frequency": 3,
     "last_seen": "2025-11-17T10:00:00Z"
   }
   ```

4. **Validate JSON syntax:**
   ```bash
   python3 -m json.tool extensions/roblox/patterns/roblox-expertise.json > /dev/null
   # No output = valid JSON
   ```

#### Method 2: Using MCP Tools (Programmatic)

From within a build or Glass Pane session:

```python
# Add a new pattern
mcp__context-foundry__codex_add_pattern(
    title="Roblox Memory Leak Pattern",
    description="Disconnecting events prevents memory leaks in Roblox",
    category="performance",
    tags=["roblox", "memory", "events"],
    project_types=["roblox-game"]
)

# Add a new issue
mcp__context-foundry__codex_add_issue(
    title="Infinite loop without task.wait()",
    description="Loops without task.wait() crash Roblox servers",
    severity="CRITICAL",
    tags=["roblox", "crash", "beginner"],
    project_types=["roblox-game"],
    solution_description="Always add task.wait() in while true loops"
)
```

## Tier 2: Context Codex (SQLite Database)

**Location:** `~/.context-foundry/codex.db`

**Purpose:** Centralized, queryable knowledge base that aggregates all extensions

### How Extension Patterns → Codex

Currently, this happens **manually** via bootstrap scripts:

```bash
# Bootstrap Roblox patterns into Codex
python3 scripts/bootstrap_roblox_patterns.py

# This script:
# 1. Reads extensions/roblox/patterns/roblox-expertise.json
# 2. Calls codex_add_pattern() for each pattern
# 3. Calls codex_add_issue() for each issue
# 4. Creates searchable entries in codex.db
```

### How Codex → Extension Patterns (Export)

After adding patterns to Codex via MCP tools, export back to JSON:

```python
# Export Codex entries to legacy JSON pattern files
mcp__context-foundry__export_codex_to_patterns(
    pattern_type="all",  # or "issues", "patterns"
    sync_to_s3=True  # Also upload to S3
)

# This creates/updates:
# - ~/.context-foundry/patterns/common-issues.json
# - ~/.context-foundry/patterns/scout-learnings.json
# - And syncs to S3 community repo
```

### Querying the Codex

During builds, agents query the Codex:

```python
# Search for Roblox patterns
mcp__context-foundry__codex_search(
    query="roblox checkpoint",
    category="roblox"
)

# Get specific pattern details
mcp__context-foundry__codex_get_entry(
    entry_id="roblox-checkpoint-pattern-001"
)
```

## Tier 3: S3 Community Repository

**Location:** `s3://bedrock-builder-kb-898587418237/community-patterns/`

**Purpose:** Share patterns across all Context Foundry users globally

### Upload Patterns to S3

```python
# Upload local patterns to S3 community repo
mcp__context-foundry__sync_patterns_to_s3(
    pattern_type="common-issues",  # or "scout-learnings", etc.
    force=False  # Set True to overwrite newer S3 version
)

# This uploads:
# ~/.context-foundry/patterns/common-issues.json
# → s3://bedrock-builder-kb-898587418237/community-patterns/common-issues.json
```

### Download Community Patterns from S3

```python
# Pull latest community patterns
mcp__context-foundry__pull_patterns_from_s3(
    pattern_type="common-issues",
    force=False  # Set True to overwrite newer local version
)

# This downloads:
# s3://bedrock-builder-kb-898587418237/community-patterns/common-issues.json
# → ~/.context-foundry/patterns/common-issues.json
```

### List Available Community Patterns

```python
# See what's available in S3
mcp__context-foundry__list_s3_community_patterns(
    pattern_type="common-issues"  # Optional filter
)
```

## Complete Learning Workflow Examples

### Scenario 1: You Discover a New Roblox Pattern

**During a build, you learn something new about Roblox development.**

```bash
# Option A: Quick manual edit (recommended for 1-2 learnings)
1. Edit extensions/roblox/patterns/roblox-expertise.json
2. Add pattern/issue JSON entry
3. python3 scripts/bootstrap_roblox_patterns.py  # Sync to Codex
4. Test with smoke test

# Option B: Use MCP tools (recommended for many learnings)
1. Use codex_add_pattern() or codex_add_issue() during build
2. export_codex_to_patterns() to save to JSON
3. Test with smoke test
```

### Scenario 2: Share Your Learnings with Community

**You've accumulated valuable patterns and want to share globally.**

```python
# Step 1: Export Codex to JSON (if you used MCP tools)
mcp__context-foundry__export_codex_to_patterns(
    pattern_type="all",
    sync_to_s3=False  # Don't sync yet
)

# Step 2: Review exported patterns
# Check ~/.context-foundry/patterns/*.json
# Make sure no sensitive/project-specific info leaked

# Step 3: Upload to S3
mcp__context-foundry__sync_patterns_to_s3(
    pattern_type="all"
)

# Now your patterns are available to all Context Foundry users!
```

### Scenario 3: Pull Latest Community Patterns

**You want the latest patterns learned by the community.**

```python
# Step 1: Pull from S3
mcp__context-foundry__pull_patterns_from_s3(
    pattern_type="all"
)

# Step 2: Bootstrap into your extension (if Roblox)
# Edit scripts/bootstrap_roblox_patterns.py to also read
# from ~/.context-foundry/patterns/*.json

# Or manually merge patterns:
mcp__context-foundry__merge_project_patterns(
    project_pattern_file="~/.context-foundry/patterns/common-issues.json",
    pattern_type="common-issues"
)
```

### Scenario 4: Project-Specific Learning → Global Patterns

**A project discovered a new issue, now share it globally.**

```python
# During/after build, project has:
# /path/to/project/.context-foundry/patterns/common-issues.json

# Step 1: Merge project patterns into global Codex
mcp__context-foundry__merge_project_patterns(
    project_path="/path/to/project",
    pattern_type="common-issues",
    increment_build_count=True
)

# Step 2: Export Codex to JSON
mcp__context-foundry__export_codex_to_patterns(
    pattern_type="common-issues",
    sync_to_s3=True  # Auto-upload to S3
)

# Step 3 (optional): Update extension pattern file
# Copy relevant patterns to extensions/roblox/patterns/roblox-expertise.json
```

## Extension-Specific Bootstrap Scripts

### Roblox Bootstrap

**File:** `scripts/bootstrap_roblox_patterns.py` (needs to be created)

```python
#!/usr/bin/env python3
"""
Bootstrap Roblox patterns into Context Codex.

This script:
1. Reads extensions/roblox/patterns/roblox-expertise.json
2. Adds each pattern/issue to codex.db
3. Makes patterns searchable via MCP tools
"""
import json
import sys
from pathlib import Path

# Add context-foundry to path
cf_root = Path(__file__).parent.parent
sys.path.insert(0, str(cf_root))

def bootstrap_roblox_patterns():
    """Load Roblox patterns into Codex"""
    pattern_file = cf_root / "extensions/roblox/patterns/roblox-expertise.json"

    with open(pattern_file) as f:
        data = json.load(f)

    # Import MCP tools
    from tools.mcp_server.codex import add_pattern, add_issue

    # Add patterns
    for pattern in data.get("patterns", []):
        add_pattern(
            pattern_id=pattern["pattern_id"],
            title=pattern.get("title", pattern["pattern_id"]),
            description=pattern["description"],
            category=pattern["category"],
            tags=pattern.get("tags", []),
            project_types=pattern.get("project_types", [])
        )
        print(f"✓ Added pattern: {pattern['pattern_id']}")

    # Add issues
    for issue in data.get("common_issues", []):
        add_issue(
            issue_id=issue["issue_id"],
            title=issue["title"],
            description=issue["description"],
            severity=issue.get("severity", "MEDIUM"),
            tags=issue.get("tags", []),
            project_types=issue.get("project_types", []),
            solution=issue.get("solution", {}).get("description", "")
        )
        print(f"✓ Added issue: {issue['issue_id']}")

    print(f"\n✅ Bootstrap complete!")
    print(f"   Patterns: {len(data.get('patterns', []))}")
    print(f"   Issues: {len(data.get('common_issues', []))}")

if __name__ == "__main__":
    bootstrap_roblox_patterns()
```

**Usage:**
```bash
python3 scripts/bootstrap_roblox_patterns.py
```

### Flowise Bootstrap

Same pattern, but reads from `extensions/flowise/patterns/flowise-expertise.json`.

## Pattern File Schema

### Pattern Entry

```json
{
  "pattern_id": "unique-pattern-id",
  "title": "Human-readable title",
  "category": "architecture|performance|security|education",
  "description": "What this pattern does",
  "project_types": ["roblox-game", "flowise-workflow"],
  "tags": ["tag1", "tag2"],
  "code_example": "-- Example code",
  "solution": "How to implement",
  "frequency": 5,  // How many times seen
  "last_seen": "2025-11-17T10:00:00Z"
}
```

### Issue Entry

```json
{
  "issue_id": "unique-issue-id",
  "title": "Problem title",
  "description": "What goes wrong",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "project_types": ["roblox-game"],
  "tags": ["tag1", "tag2"],
  "symptoms": ["symptom1", "symptom2"],
  "solution": {
    "description": "How to fix",
    "code_example": "-- Fixed code"
  },
  "frequency": 3,
  "last_seen": "2025-11-17T10:00:00Z"
}
```

## Best Practices

### 1. Incremental Learning

✅ **Do:** Add patterns as you discover them during builds
```json
// After each build, add 1-3 new learnings
```

❌ **Don't:** Wait weeks and try to remember everything
```json
// You'll forget details and context
```

### 2. Clear Pattern IDs

✅ **Do:** Use descriptive, namespaced IDs
```json
"pattern_id": "roblox-datastore-retry-logic"
"issue_id": "roblox-remote-security-001"
```

❌ **Don't:** Use generic or numbered-only IDs
```json
"pattern_id": "pattern-42"
"issue_id": "issue-001"
```

### 3. Include Project Types

✅ **Do:** Tag with specific project types
```json
"project_types": ["roblox-game", "roblox-plugin"]
```

❌ **Don't:** Omit or use generic types
```json
"project_types": ["all"]  // Not queryable
```

### 4. Validate Before Sharing

✅ **Do:** Review patterns before S3 upload
```bash
# Check for sensitive data
grep -r "password\|secret\|key" ~/.context-foundry/patterns/
```

❌ **Don't:** Auto-upload without review
```python
# This could leak project secrets!
sync_patterns_to_s3(pattern_type="all")
```

## Troubleshooting

### Pattern Not Showing Up in Codex

```bash
# 1. Check pattern file is valid JSON
python3 -m json.tool extensions/roblox/patterns/roblox-expertise.json

# 2. Re-bootstrap
python3 scripts/bootstrap_roblox_patterns.py

# 3. Query Codex to verify
python3 -c "
from tools.mcp_server import codex
result = codex.search('roblox')
print(result)
"
```

### S3 Upload Fails

```bash
# Check AWS credentials
aws s3 ls s3://bedrock-builder-kb-898587418237/community-patterns/

# Check pattern file exists
ls -la ~/.context-foundry/patterns/

# Try with force flag
# (Use MCP tool with force=True)
```

### Pattern Conflicts

If multiple people edit the same pattern:

```python
# Pull latest from S3 first
pull_patterns_from_s3(pattern_type="all", force=True)

# Manually merge conflicts in JSON file

# Then upload
sync_patterns_to_s3(pattern_type="all", force=True)
```

## Future Enhancements

**Planned features:**

1. **Auto-Learning:** Agents automatically detect patterns during builds
2. **Pattern Voting:** Community upvotes/downvotes patterns
3. **Version Control:** Git-like branching for pattern evolution
4. **Pattern Analytics:** See which patterns are most effective
5. **Auto-Sync:** Background sync between Codex ↔ S3

## Summary

**The Complete Flow:**

1. **Learn** → Add to extension JSON or use MCP `codex_add_pattern()`
2. **Centralize** → Bootstrap extension patterns into Codex
3. **Export** → `export_codex_to_patterns()` creates JSON files
4. **Share** → `sync_patterns_to_s3()` uploads to community
5. **Download** → `pull_patterns_from_s3()` gets community patterns
6. **Apply** → Next build uses updated patterns automatically

**Key Files:**
- Extension patterns: `extensions/{name}/patterns/*.json`
- Global Codex: `~/.context-foundry/codex.db`
- Global patterns: `~/.context-foundry/patterns/*.json`
- Community: `s3://bedrock-builder-kb-898587418237/community-patterns/`

**Key Tools:**
- `codex_add_pattern()` - Add new pattern
- `codex_add_issue()` - Add new issue
- `codex_search()` - Query patterns
- `export_codex_to_patterns()` - Codex → JSON
- `sync_patterns_to_s3()` - JSON → S3
- `pull_patterns_from_s3()` - S3 → JSON
- `merge_project_patterns()` - Project → Global

---

**For more details:**
- See MCP tool documentation: `mcp__context-foundry__search_tools("codex")`
- Check extension README files
- Review existing pattern files for examples

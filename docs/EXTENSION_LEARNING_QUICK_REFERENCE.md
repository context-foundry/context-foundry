# Extension Learning - Quick Reference

**TL;DR: How to teach Context Foundry new things**

## 3 Knowledge Tiers

```
Extension JSON → Codex SQLite → S3 Community
    (Local)    →   (Centralized) →  (Global)
```

## Quick Workflows

### 1. Add a New Learning (Roblox Example)

**Option A: Manual Edit (Fastest)**
```bash
# 1. Edit pattern file
code extensions/roblox/patterns/roblox-expertise.json

# 2. Add pattern entry:
{
  "pattern_id": "roblox-new-pattern-2025",
  "title": "What I learned",
  "category": "performance",
  "description": "Detailed explanation...",
  "project_types": ["roblox-game"],
  "tags": ["optimization", "datastore"],
  "code_example": "-- Example code",
  "frequency": 1,
  "last_seen": "2025-11-17T10:00:00Z"
}

# 3. Validate JSON
python3 -m json.tool extensions/roblox/patterns/roblox-expertise.json > /dev/null

# 4. Bootstrap into Codex
python3 scripts/bootstrap_roblox_patterns.py

# 5. Test
python3 tools/run_extension_smoke_test.py --extension roblox
```

**Option B: Use MCP Tools (From Glass Pane or build)**
```python
# Add directly to Codex
mcp__context-foundry__codex_add_pattern(
    title="Roblox Memory Leak Pattern",
    description="Events need cleanup with :Disconnect()",
    category="performance",
    tags=["roblox", "memory", "events"],
    project_types=["roblox-game"]
)

# Export Codex → JSON
mcp__context-foundry__export_codex_to_patterns(
    pattern_type="all"
)
```

### 2. Share with Community

```bash
# Step 1: Export Codex to JSON (if using MCP tools)
# Use: export_codex_to_patterns()

# Step 2: Upload to S3
# Use: sync_patterns_to_s3(pattern_type="all")

# Now available globally!
```

### 3. Get Community Patterns

```bash
# Download latest from S3
# Use: pull_patterns_from_s3(pattern_type="all")

# Bootstrap into your extension
python3 scripts/bootstrap_roblox_patterns.py
```

### 4. Flowise Example (Same Process)

```bash
# 1. Edit flowise patterns
code extensions/flowise/patterns/flowise-expertise.json

# 2. Add pattern (same JSON schema as Roblox)
{
  "pattern_id": "flowise-parallel-agents-pattern",
  "title": "Parallel Agent Pattern",
  "category": "architecture",
  ...
}

# 3. Bootstrap (need to create script)
python3 scripts/bootstrap_flowise_patterns.py

# 4. Test
python3 tools/run_extension_smoke_test.py --extension flowise
```

## Pattern JSON Schema

### Pattern Entry
```json
{
  "pattern_id": "extension-descriptive-name",
  "title": "Human readable title",
  "category": "architecture|performance|security|education",
  "description": "What this pattern does and why",
  "project_types": ["roblox-game", "flowise-workflow"],
  "tags": ["tag1", "tag2"],
  "code_example": "-- Code snippet",
  "solution": "How to implement",
  "frequency": 1,
  "last_seen": "2025-11-17T10:00:00Z"
}
```

### Issue Entry
```json
{
  "issue_id": "extension-issue-001",
  "title": "Problem description",
  "description": "What goes wrong and why",
  "severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "project_types": ["roblox-game"],
  "tags": ["tag1", "tag2"],
  "symptoms": ["symptom1", "symptom2"],
  "solution": {
    "description": "How to fix",
    "code_example": "-- Fixed code"
  },
  "frequency": 1,
  "last_seen": "2025-11-17T10:00:00Z"
}
```

## Key MCP Tools

| Tool | Purpose |
|------|---------|
| `codex_add_pattern()` | Add pattern to Codex |
| `codex_add_issue()` | Add issue to Codex |
| `codex_search()` | Query patterns |
| `codex_get_entry()` | Get details |
| `export_codex_to_patterns()` | Codex → JSON |
| `sync_patterns_to_s3()` | Upload to S3 |
| `pull_patterns_from_s3()` | Download from S3 |

## File Locations

```
# Extension patterns (local)
extensions/roblox/patterns/roblox-expertise.json
extensions/flowise/patterns/flowise-expertise.json

# Global Codex database
~/.context-foundry/codex.db

# Global pattern exports
~/.context-foundry/patterns/common-issues.json
~/.context-foundry/patterns/scout-learnings.json

# Community (S3)
s3://bedrock-builder-kb-898587418237/community-patterns/
```

## When to Use Each Method

**Manual Edit (JSON file):**
- ✅ Adding 1-5 patterns at once
- ✅ Need to see all patterns in one file
- ✅ Offline development

**MCP Tools:**
- ✅ Adding patterns during a build
- ✅ Programmatic pattern capture
- ✅ Auto-learning workflows

**S3 Sync:**
- ✅ Share with community
- ✅ Pull community learnings
- ✅ Backup patterns

## Common Tasks

### Add Beginner Pattern (Roblox)
```json
// Edit: extensions/roblox/patterns/roblox-expertise.json
{
  "pattern_id": "roblox-beginner-kill-brick",
  "title": "Kill Brick Pattern",
  "category": "education",
  "description": "Simple kill brick for beginner developers",
  "project_types": ["roblox-game"],
  "tags": ["beginner", "tutorial", "touched-event"],
  "code_example": "local killBrick = script.Parent\nkillBrick.Touched:Connect(function(hit)\n    local humanoid = hit.Parent:FindFirstChild(\"Humanoid\")\n    if humanoid then\n        humanoid.Health = 0\n    end\nend)",
  "teaching_points": [
    "Variable binding with local",
    "Event handling with .Touched:Connect",
    "Finding child objects",
    "Property modification"
  ],
  "frequency": 1,
  "last_seen": "2025-11-17T10:00:00Z"
}
```

### Add Security Issue (Roblox)
```json
// Edit: extensions/roblox/patterns/roblox-expertise.json
// Under "common_issues":
{
  "issue_id": "roblox-remote-no-validation-001",
  "title": "RemoteEvent accepts client-supplied amounts without validation",
  "description": "Client can send arbitrary coin amounts to server, enabling exploits",
  "severity": "CRITICAL",
  "project_types": ["roblox-game"],
  "tags": ["security", "remote-events", "exploit"],
  "symptoms": [
    "Players have impossible coin amounts",
    "Exploit reports from community",
    "Economy breaking"
  ],
  "solution": {
    "description": "Validate all RemoteEvent payloads: type → range → business logic → rate limit",
    "code_example": "RemoteEvent.OnServerEvent:Connect(function(player, amount)\n    -- Type check\n    if type(amount) ~= \"number\" then return end\n    -- Range check\n    if amount < 0 or amount > 1000 then return end\n    -- Business logic (did player actually collect this?)\n    if not isValidCoinCollection(player, amount) then return end\n    -- Award coins\n    awardCoins(player, amount)\nend)"
  },
  "frequency": 8,
  "last_seen": "2025-11-17T10:00:00Z"
}
```

### Add Workflow Pattern (Flowise)
```json
// Edit: extensions/flowise/patterns/flowise-expertise.json
{
  "pattern_id": "flowise-parallel-agents-2025",
  "title": "Parallel Agent Execution Pattern",
  "category": "architecture",
  "description": "Multiple agents run concurrently for faster workflow completion",
  "project_types": ["flowise-workflow"],
  "tags": ["performance", "parallel", "agents"],
  "implementation": {
    "nodes": [
      {
        "type": "ifelse",
        "name": "Split Work"
      },
      {
        "type": "agent",
        "name": "Agent 1 (runs in parallel)"
      },
      {
        "type": "agent",
        "name": "Agent 2 (runs in parallel)"
      },
      {
        "type": "merge",
        "name": "Combine Results"
      }
    ]
  },
  "benefits": [
    "2-5x faster execution",
    "Better resource utilization",
    "Independent task processing"
  ],
  "frequency": 12,
  "last_seen": "2025-11-17T10:00:00Z"
}
```

## Troubleshooting

### Pattern not appearing in builds
```bash
# 1. Verify JSON is valid
python3 -m json.tool extensions/roblox/patterns/roblox-expertise.json

# 2. Re-bootstrap
python3 scripts/bootstrap_roblox_patterns.py

# 3. Check Codex
# Use: codex_search("your-pattern-name")
```

### S3 upload fails
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check file exists
ls -la ~/.context-foundry/patterns/

# Force upload
# Use: sync_patterns_to_s3(pattern_type="all", force=True)
```

### Bootstrap script missing for extension
```bash
# Copy Roblox bootstrap as template
cp scripts/bootstrap_roblox_patterns.py scripts/bootstrap_flowise_patterns.py

# Edit to point to flowise patterns
sed -i 's/roblox/flowise/g' scripts/bootstrap_flowise_patterns.py

# Run it
python3 scripts/bootstrap_flowise_patterns.py
```

## Best Practices

1. **Clear IDs:** Use `extension-category-name-YYYY` format
2. **Project Types:** Always specify which project types pattern applies to
3. **Tags:** Include searchable keywords
4. **Frequency:** Update when you see pattern again (helps prioritization)
5. **Validate:** Always validate JSON before committing
6. **Share:** Upload valuable patterns to S3 for community

## Next Steps

- See full details: `docs/EXTENSION_LEARNING_LIFECYCLE.md`
- MCP tool reference: `mcp__context-foundry__search_tools("codex")`
- Extension examples: `extensions/{roblox,flowise}/patterns/`

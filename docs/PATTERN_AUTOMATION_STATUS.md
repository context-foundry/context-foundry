# Pattern Learning Automation Status

**What's Automatic vs What You Need to Run Manually**

## TL;DR Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATION STATUS                            │
└─────────────────────────────────────────────────────────────────┘

AUTOMATED (Happens during every build):
  ✅ Project patterns → Global Codex (~/.context-foundry/codex.db)
  ✅ Global Codex → Community (via GitHub PR)
  ✅ Pattern merging and frequency tracking

MANUAL (You must run these):
  ❌ Extension JSON → Codex (bootstrap scripts)
  ❌ S3 direct sync (use MCP tools)
  ❌ Community pattern downloads (use MCP tools)
```

## The Complete Automation Flow

### What Happens AUTOMATICALLY During a Build

```
BUILD STARTS
     │
     ├─ PHASE 1-6: Scout, Architect, Build, Test, Screenshots, Docs
     │
     ├─ PHASE 7: FEEDBACK ANALYSIS ⭐ (Automatic Learning)
     │    │
     │    ├─ Step 1: Analyzer identifies patterns/issues from build
     │    │   Output: .context-foundry/feedback/build-feedback-{date}.json
     │    │
     │    ├─ Step 2: merge_project_patterns() AUTOMATICALLY called
     │    │   - Reads feedback file
     │    │   - Merges patterns → ~/.context-foundry/patterns/common-issues.json
     │    │   - Updates Codex database
     │    │   - Increments frequency counters
     │    │   - Tracks last_seen dates
     │    │
     │    └─ Step 3: share_patterns_to_community() AUTOMATICALLY called
     │        - Creates GitHub branch: patterns/{username}/{timestamp}
     │        - Opens PR to Context Foundry repo
     │        - PR auto-validated and auto-merged
     │        - Patterns available to community!
     │
     └─ BUILD COMPLETE ✅
```

### From Orchestrator (Phase 7):

**Lines 2856-2877: Automatic Global Merge**
```python
# AUTOMATICALLY EXECUTED by agents at end of every build
merge_project_patterns(
    project_pattern_file="{path}/.context-foundry/feedback/build-feedback-{timestamp}.json",
    pattern_type="common-issues",
    increment_build_count=true
)
```

**Lines 2992-2995: Automatic Community Share**
```python
# AUTOMATICALLY EXECUTED after pattern merge
share_patterns_to_community(
    auto_confirm=true,
    skip_if_no_changes=true
)
```

**Result:** Every successful build automatically contributes learnings back to the community!

## What's NOT Automated (Manual Steps)

### 1. Extension Pattern Bootstrap (MANUAL)

**Problem:** Extension JSON files don't auto-import to Codex

**Extension Pattern Files:**
- `extensions/roblox/patterns/roblox-expertise.json`
- `extensions/flowise/patterns/flowise-expertise.json`

**These contain curated patterns but DON'T auto-load into Codex.**

**Manual Steps Required:**
```bash
# For Roblox
python3 scripts/bootstrap_roblox_patterns.py

# For Flowise
python3 scripts/bootstrap_flowise_patterns.py
```

**When to run:**
- After installing Context Foundry (first time setup)
- After editing extension JSON files manually
- After pulling updates to extension patterns from git
- After adding new patterns to the JSON manually

**Frequency:** Only when extension JSON files change (not every build)

### 2. Community Pattern Downloads (MANUAL)

**Problem:** Community patterns in S3 don't auto-download

**Manual Steps Required:**
```python
# Download latest community patterns from S3
mcp__context-foundry__pull_patterns_from_s3(
    pattern_type="all"
)

# Then bootstrap if needed (for extensions)
# Run: python3 scripts/bootstrap_roblox_patterns.py
```

**When to run:**
- Weekly/monthly to get latest community learnings
- Before starting a new project type you haven't built before
- After major Context Foundry releases

**Frequency:** Recommended weekly or on-demand

### 3. Direct S3 Sync (MANUAL - Optional)

**Note:** Usually not needed because `share_patterns_to_community()` handles this via GitHub PR workflow.

**Manual Steps Required:**
```python
# Export Codex to JSON
mcp__context-foundry__export_codex_to_patterns(
    pattern_type="all"
)

# Upload to S3 directly
mcp__context-foundry__sync_patterns_to_s3(
    pattern_type="all"
)
```

**When to use:**
- If you want to bypass GitHub PR workflow
- If you have direct S3 write access
- For testing or emergency updates

**Frequency:** Usually not needed - use GitHub PR workflow instead

## Detailed Automation Breakdown

### Project Patterns (Per-Build Learning)

```
STATUS: ✅ FULLY AUTOMATED

TRIGGER: Every build completion (Phase 7: Feedback Analysis)

FLOW:
  Build completes
    → Feedback analyzer extracts patterns
    → Saves to .context-foundry/feedback/build-feedback-{date}.json
    → merge_project_patterns() auto-called
    → Patterns merged to ~/.context-foundry/patterns/common-issues.json
    → Codex database auto-updated
    → share_patterns_to_community() auto-called
    → GitHub PR auto-created
    → Community benefits from your learnings

YOU DO: Nothing! It just works.

EXAMPLE:
  You build a FastAPI app
  → Discovers "Use pydantic BaseSettings for env vars"
  → Pattern auto-saved
  → Pattern auto-shared with community
  → Next developer building FastAPI app gets this tip
```

### Extension Patterns (Curated Knowledge)

```
STATUS: ⚠️ MANUAL BOOTSTRAP REQUIRED

TRIGGER: Manual - you run bootstrap script

FLOW:
  Edit extensions/roblox/patterns/roblox-expertise.json
    → Add new pattern manually
    → Validate JSON
    → Run: python3 scripts/bootstrap_roblox_patterns.py
    → Pattern imported to Codex
    → Now searchable via codex_search()

YOU DO:
  1. Edit JSON file (or use codex_add_pattern() MCP tool)
  2. Run bootstrap script
  3. Verify with smoke test

FREQUENCY: Only when extension patterns change

WHY NOT AUTOMATED:
  - Extension patterns are curated, not auto-discovered
  - Changes infrequently (weeks/months)
  - Requires validation and review
  - Not every build needs this
```

### Community Pattern Downloads

```
STATUS: ⚠️ MANUAL PULL REQUIRED

TRIGGER: Manual - you run MCP tool

FLOW:
  Community uploads patterns to S3
    → You run: pull_patterns_from_s3()
    → Downloads to ~/.context-foundry/patterns/
    → You run bootstrap scripts (if needed)
    → Patterns available in your Codex

YOU DO:
  1. pull_patterns_from_s3(pattern_type="all")
  2. Optional: Re-run bootstrap scripts to update Codex
  3. Verify with: codex_search("pattern-name")

FREQUENCY: Weekly recommended, or before new project types

WHY NOT AUTOMATED:
  - Respects user control over what patterns they use
  - Avoids constant network calls
  - Allows review before applying community patterns
  - User may have customized local patterns
```

## Automation Triggers

| Event | What Happens | Automatic? |
|-------|-------------|------------|
| **Build completes** | Project patterns → Codex → GitHub PR | ✅ Auto |
| **MCP server starts** | Project patterns bootstrap (if in project dir) | ✅ Auto |
| **Extension JSON edited** | Nothing (must run bootstrap) | ❌ Manual |
| **Community patterns updated** | Nothing (must pull from S3) | ❌ Manual |
| **Install Context Foundry** | Nothing (must bootstrap extensions) | ❌ Manual |
| **Git pull extension updates** | Nothing (must re-bootstrap) | ❌ Manual |

## Recommended Workflow

### First-Time Setup (One-Time)

```bash
# 1. Install Context Foundry
git clone https://github.com/your-org/context-foundry
cd context-foundry

# 2. Bootstrap extension patterns (Roblox)
python3 scripts/bootstrap_roblox_patterns.py

# 3. Bootstrap extension patterns (Flowise)
python3 scripts/bootstrap_flowise_patterns.py

# 4. Pull community patterns
# Use MCP tool: pull_patterns_from_s3(pattern_type="all")

# Done! Now builds will auto-learn and auto-share
```

### Weekly Maintenance (Optional)

```bash
# Pull latest community patterns
# Use MCP tool: pull_patterns_from_s3(pattern_type="all")

# Check stats
# Use MCP tool: codex_stats()
```

### After Editing Extension Patterns

```bash
# You manually added patterns to extensions/roblox/patterns/roblox-expertise.json

# 1. Validate JSON
python3 -m json.tool extensions/roblox/patterns/roblox-expertise.json > /dev/null

# 2. Bootstrap into Codex
python3 scripts/bootstrap_roblox_patterns.py

# 3. Verify
python3 tools/run_extension_smoke_test.py --extension roblox

# 4. Commit changes
git add extensions/roblox/patterns/roblox-expertise.json
git commit -m "Add new Roblox pattern: {description}"
```

## Future Automation Plans

**Planned improvements:**

1. **Auto-Bootstrap on Extension Update**
   - Git hook to auto-run bootstrap when extension JSON changes
   - Status: Planned for v2.4.0

2. **Scheduled Community Pattern Sync**
   - Cron job to auto-pull community patterns weekly
   - Status: Under consideration

3. **Auto-Discovery of Extension Patterns**
   - Builder phase auto-detects new patterns during builds
   - Auto-adds to extension JSON files
   - Status: Research phase

4. **S3 Direct Sync** (bypass GitHub)
   - After every build, auto-sync to S3
   - Status: Deprecated in favor of GitHub PR workflow

## Checking Automation Status

### Is My Build Auto-Sharing?

```bash
# After a build, check:
cat .context-foundry/session-summary.json | grep -A 5 "pattern_sharing"

# Should show:
{
  "pattern_sharing": {
    "enabled": true,
    "pr_created": true,
    "pr_url": "https://github.com/...",
    "patterns_shared": 3
  }
}
```

### Are Extension Patterns in Codex?

```python
# Use MCP tool
codex_search(query="roblox", category="roblox")

# If empty: Run bootstrap script
# python3 scripts/bootstrap_roblox_patterns.py
```

### When Was Community Last Synced?

```bash
# Check pattern file timestamps
ls -lah ~/.context-foundry/patterns/

# Old timestamps = need to pull from S3
# Use: pull_patterns_from_s3(pattern_type="all")
```

## Summary Table

| Pattern Source | Auto-Import to Codex | Auto-Share to Community | Frequency |
|----------------|---------------------|------------------------|-----------|
| **Project builds** | ✅ Yes (Phase 7) | ✅ Yes (Phase 7) | Every build |
| **Extension JSON** | ❌ No (run bootstrap) | ⚠️ Via git commit | When edited |
| **Community S3** | ❌ No (pull manually) | N/A (download only) | On-demand |
| **Manual MCP calls** | ✅ Yes (immediate) | ⚠️ Via export → GitHub | Real-time |

## Key Takeaways

✅ **What's Automatic:**
- Every build learns patterns and shares to community
- Project-specific learnings merge to global Codex
- GitHub PR workflow handles community distribution
- Pattern frequency tracking happens automatically

❌ **What's Manual:**
- Bootstrap extension patterns (Roblox/Flowise) - **Once per install + when JSON changes**
- Pull community patterns from S3 - **Weekly recommended**
- Direct S3 sync (if not using GitHub PR workflow)

🎯 **Bottom Line:**
**You rarely need to think about patterns.** Builds auto-learn and auto-share. Only run bootstrap scripts when:
1. First install
2. After editing extension JSON manually
3. After git pull updates extension patterns

Everything else happens automatically! 🚀

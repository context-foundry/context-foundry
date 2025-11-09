# CRITICAL BUG: Pattern Library Bootstrap Failure

**Severity:** CRITICAL
**Impact:** Defeats entire knowledge-sharing architecture
**Discovered:** 2025-11-09
**Reporter:** User testing Context Foundry

## Problem Statement

When users clone Context Foundry from GitHub, they receive curated pattern libraries in `.context-foundry/patterns/common-issues.json`. However, the MCP server creates a NEW file at `~/.context-foundry/patterns/common-issues.json` and ONLY reads/writes to this global location, completely ignoring the project patterns.

**Result:** New users encounter all the same issues the community has already solved.

## Evidence

### Project Patterns (IGNORED)
**Location:** `/Users/name/homelab/context-foundry/.context-foundry/patterns/common-issues.json`
**Last Updated:** 2025-10-28
**Patterns:** 5 detailed, battle-tested patterns:
1. X-Frame-Options iframe blocking (webcam aggregators)
2. CORS ES6 modules from file://
3. AWS Lambda inline handler mismatch
4. API Gateway path routing precedence
5. Bedrock agent collaboration mode defaults

Each pattern includes:
- Detection history
- Prevention strategies
- Fix time estimates
- Affected project types
- Code examples
- AWS documentation links

### Global Patterns (USED)
**Location:** `~/.context-foundry/patterns/common-issues.json`
**Last Updated:** 2025-11-09
**Patterns:** 14 patterns (mostly Flowise + recent Docker/Vite issues)

**ZERO overlap** with project patterns → Knowledge loss

## Root Cause

The MCP server's pattern storage system:
1. Uses `~/.context-foundry/` as global storage (correct design)
2. Creates new pattern files on first run (correct behavior)
3. **FAILS to bootstrap** by merging project patterns into global storage

## Impact

- New Context Foundry users get ZERO benefit from community learnings
- Users re-encounter iframe blocking, CORS errors, Lambda misconfigurations, etc.
- The 5 detailed patterns in the project are completely wasted
- Pattern library appears empty to new users
- Defeats the "self-improving AI" value proposition

## Expected Behavior

On MCP server initialization:
1. Check if running from a Context Foundry project directory
2. Detect `.context-foundry/patterns/` directory
3. Call `merge_project_patterns()` for each pattern file
4. Merge project patterns into global storage with proper frequency counting
5. Log: "Bootstrapped X patterns from project library"

## Solution

### Option 1: Automatic Bootstrap (RECOMMENDED)
Add initialization code to MCP server startup:

```python
def bootstrap_patterns_on_startup():
    """Merge project patterns into global storage on first run"""
    project_pattern_dir = Path.cwd() / ".context-foundry" / "patterns"
    global_pattern_dir = Path.home() / ".context-foundry" / "patterns"

    if not project_pattern_dir.exists():
        return  # Not a CF project, skip

    # Check if bootstrap already done
    bootstrap_marker = global_pattern_dir / ".bootstrap-done"
    if bootstrap_marker.exists():
        return  # Already bootstrapped

    # Merge all pattern files
    for pattern_file in project_pattern_dir.glob("*.json"):
        pattern_type = pattern_file.stem  # e.g., "common-issues"
        merge_project_patterns(
            str(pattern_file),
            pattern_type,
            increment_build_count=False
        )

    # Mark as bootstrapped
    bootstrap_marker.write_text(f"Bootstrapped on {datetime.now()}")
    logger.info(f"Bootstrapped patterns from {project_pattern_dir}")
```

### Option 2: Manual Migration Command
Provide CLI command:
```bash
context-foundry migrate-patterns
```

But this requires user awareness → Not acceptable for critical infrastructure

### Option 3: Smart Merge on Every Read
Check both locations and merge on-the-fly, but this adds latency.

## Testing the Fix

1. Delete `~/.context-foundry/` to simulate new user
2. Start MCP server from Context Foundry project directory
3. Call `mcp__context-foundry__read_global_patterns("common-issues")`
4. Verify 5+ patterns present (project patterns merged)
5. Verify patterns include iframe blocking, CORS, Lambda handler patterns

## Files Involved

- `src/context_foundry/pattern_storage.py` - Pattern merge logic
- `src/context_foundry/mcp_server.py` - Server initialization
- `.context-foundry/patterns/common-issues.json` - Source patterns
- `~/.context-foundry/patterns/common-issues.json` - Destination patterns

## Workaround (Manual)

Users can manually merge patterns:
```python
from mcp__context_foundry import merge_project_patterns

merge_project_patterns(
    "/path/to/context-foundry/.context-foundry/patterns/common-issues.json",
    "common-issues",
    increment_build_count=False
)
```

But this defeats the "zero-configuration" goal.

## Priority Justification

This is CRITICAL because:
1. Breaks core value proposition (self-improving AI)
2. Affects ALL new users
3. Silent failure (no error, just missing knowledge)
4. Easy fix but devastating impact if not addressed
5. Pattern library is Context Foundry's competitive advantage

## Related Issues

- Pattern sharing to community (share_patterns_to_community) - also affected
- Global pattern evolution - built on broken foundation
- MCP server documentation - doesn't mention bootstrap requirement

---

**Status:** OPEN
**Assigned:** Context Foundry Core Team
**Milestone:** v2.2.0 (URGENT)
**Labels:** bug, critical, knowledge-sharing, p0

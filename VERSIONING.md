# Version Management

**Single Source of Truth:** `/VERSION` file

## How Versioning Works

Context Foundry uses semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR:** Breaking changes (e.g., 1.x → 2.x)
- **MINOR:** New features, non-breaking changes (e.g., 2.1 → 2.2)
- **PATCH:** Bug fixes, small improvements (e.g., 2.1.0 → 2.1.1)

## Updating the Version

**To update Context Foundry's version, you MUST update these files in order:**

### 1. Update VERSION file (Required)
```bash
echo "2.2.0" > VERSION
```

### 2. Update orchestrator_prompt.txt (Required)
```bash
# Line 2 in tools/orchestrator_prompt.txt
Version: v2.2.0
```

### 3. Test the change
```bash
# Verify version is correct everywhere
python3 tools/version.py

# Should output:
# Context Foundry v2.2.0
# Major: 2
# Minor: 2
# Patch: 0
```

### 4. Update README.md (Optional but recommended)
Update the version banner at the top:
```markdown
**Version 2.2.0 - [Month Year]**
```

## Files That Auto-Update

These files **automatically** read from `VERSION` file:

- ✅ `tools/mcp_server.py` - MCP status message
- ✅ `tools/version.py` - Version helper module

## Files That Need Manual Updates

These files **must be manually updated**:

- ⚠️ `tools/orchestrator_prompt.txt` (line 2)
- ⚠️ `README.md` (top banner)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.1.0 | Oct 2025 | Prompt caching, stale phase fix, sibling directory docs |
| 2.0.0 | Sep 2025 | MCP server integration, Claude Code support |
| 1.4.0 | Aug 2025 | BAML integration |
| 1.3.0 | Jul 2025 | Pattern library |
| 1.0.0 | Jun 2025 | Initial Python CLI release |

## Checking Current Version

```bash
# Method 1: Read VERSION file
cat VERSION

# Method 2: Run version module
python3 tools/version.py

# Method 3: Query MCP server (when running)
# Ask Claude: "What version of Context Foundry is this?"
```

## Pre-Release Versions

For pre-releases, append suffix:
- Alpha: `2.2.0-alpha.1`
- Beta: `2.2.0-beta.1`
- RC: `2.2.0-rc.1`

## Release Checklist

Before releasing a new version:

- [ ] Update `VERSION` file
- [ ] Update `tools/orchestrator_prompt.txt` (line 2)
- [ ] Update `README.md` version banner
- [ ] Run `python3 tools/version.py` to verify
- [ ] Run smoke tests
- [ ] Update `VERSIONING.md` history table
- [ ] Commit with message: `chore: Bump version to X.Y.Z`
- [ ] Tag release: `git tag vX.Y.Z`
- [ ] Push: `git push && git push --tags`

## Why Centralized Versioning?

**Before:** Version chaos!
- README said: "2.1.0"
- Orchestrator said: "v1.2.1"
- MCP status said: "1.0.0"
- Git tags said: "v1.4.0"

**After:** Single source of truth
- ONE file to update: `VERSION`
- Auto-updates most places
- Clear process for manual updates
- Consistent version everywhere

---

**Last Updated:** October 25, 2025
**Current Version:** 2.1.0

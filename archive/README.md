# Context Foundry Archive

This directory contains archived documentation that has been retired from the main repository to keep the public GitHub repo clean and focused on current v2.0 content.

**Date Archived:** October 19, 2025
**Archive Reason:** Repository cleanup - remove internal development artifacts and outdated v1.x documentation from public view

---

## Archive Structure

### `archive/docs/` - Internal/Blog Content
**1 file**

Documentation that was written for internal purposes or blog posts that are not relevant for public GitHub visitors.

- **BLOG_GENESIS.md** - Blog post about Context Foundry's creation story (internal content)

### `archive/legacy/` - Outdated v1.x Integration Docs
**6 files**

Documentation for Context Foundry 1.x integrations and features that are no longer relevant in v2.0 (which uses MCP server architecture instead of direct API integrations).

- **CLAUDE_API_INTEGRATION.md** - v1.x Anthropic API integration (replaced by MCP in v2.0)
- **GITHUB_COPILOT_INTEGRATION.md** - Copilot integration exploration (not implemented)
- **GITHUB_MODELS_INTEGRATION.md** - GitHub Models integration (not implemented)
- **ZAI_INTEGRATION.md** - ZAI integration exploration (not implemented)
- **COMPREHENSIVE_ARCHITECTURE_ANALYSIS.md** - v1.x Python architecture analysis (outdated - references ace/, workflows/, etc. which don't exist in v2.0)
- **INSTALL.md** - v1.x installation instructions (outdated - v2.0 uses QUICKSTART.md and CLAUDE_CODE_MCP_SETUP.md instead)

### `archive/development/` - Development Artifacts
**16 files**

Implementation notes, completion summaries, and development plans that were useful during development but are not needed for end users.

**Implementation Notes:**
- **FIXES_IMPLEMENTED.md** - Bug fixes during development
- **IMPLEMENTATION_COMPLETE.md** - v1.x implementation completion summary
- **LIVESTREAM_IMPLEMENTATION.md** - Livestream feature development notes
- **LIVESTREAM_INTEGRATION_COMPLETE.md** - Livestream completion summary
- **MULTI_PROVIDER_FEATURE.md** - Multi-provider feature development
- **PATTERN_INTEGRATION_COMPLETE.md** - Pattern library integration completion
- **PATTERN_LIBRARY_IMPLEMENTATION.md** - Pattern library development notes
- **PATTERN_LIBRARY_PLAN.md** - Pattern library planning document
- **RALPH_WIGGUM_IMPLEMENTATION.md** - Ralph Wiggum error handling implementation
- **multi_agent_implementation.md** - Multi-agent system development notes
- **verification_implementation_plan.md** - Verification system plan

**Analysis/Planning:**
- **WEATHER_APP_BUILD_ANALYSIS.md** - Weather app build test analysis
- **MULTI_AGENT_SYSTEM.md** - Multi-agent system design notes
- **TEST_SUMMARY.md** - Test execution summaries
- **QUICK_START_EXAMPLES.md** - Development quick start examples
- **SETUP.md** - Development setup notes

---

## Why Archive Instead of Delete?

These files are preserved with full Git history (using `git mv`) to:

1. **Preserve Context** - Future developers can reference implementation decisions and lessons learned
2. **Maintain Git History** - All commits remain intact and searchable
3. **Enable Restoration** - Files can be moved back if needed (completely reversible)
4. **Document Evolution** - Shows the project's journey from v1.x to v2.0

---

## Current (Active) Documentation

For current documentation, see the main [README.md](../README.md) which includes:

**Getting Started:**
- [QUICKSTART.md](../QUICKSTART.md) - 5-minute quick start
- [CLAUDE_CODE_MCP_SETUP.md](../CLAUDE_CODE_MCP_SETUP.md) - Complete MCP setup

**Architecture:**
- [docs/ARCHITECTURE_DIAGRAMS.md](../docs/ARCHITECTURE_DIAGRAMS.md) - Visual flowcharts
- [docs/MCP_SERVER_ARCHITECTURE.md](../docs/MCP_SERVER_ARCHITECTURE.md) - Technical deep dive
- [docs/CONTEXT_PRESERVATION.md](../docs/CONTEXT_PRESERVATION.md) - How context flows

**v2.0 Transition:**
- [CONTEXT_FOUNDRY_2.0.md](../CONTEXT_FOUNDRY_2.0.md) - What changed in v2.0
- [ARCHITECTURE_DECISIONS.md](../ARCHITECTURE_DECISIONS.md) - Why v2.0 architecture

**v1.x Users:**
- [LEGACY_README.md](../LEGACY_README.md) - Original v1.x documentation (still functional)

---

## Backup Branch

A complete backup of the repository before this cleanup was created:

**Branch:** `backup-before-cleanup-2025-10-19`
**GitHub:** https://github.com/snedea/context-foundry/tree/backup-before-cleanup-2025-10-19

This backup preserves the exact state of the repository before any files were moved to the archive.

---

## Restoring Archived Files

If you need to restore any archived file:

```bash
# Restore a single file to its original location
git mv archive/legacy/INSTALL.md ./

# Restore entire category
git mv archive/development/* ./

# Or checkout from backup branch
git checkout backup-before-cleanup-2025-10-19 -- INSTALL.md
```

All archived files retain their full Git history and can be restored at any time.

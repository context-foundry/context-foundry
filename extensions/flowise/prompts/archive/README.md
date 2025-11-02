# Archived Flowise Documentation

These files are not currently used by the orchestrator but preserved for historical reference.

---

## Archived Files

### architect-enhancement.txt
**Original Purpose**: Architect phase enhancement prompt
**Why Archived**: Never referenced in orchestrator_prompt.txt. Content integrated into AGENT_PATTERN_REFERENCE.md.
**Status**: Superseded

### scout-enhancement.txt
**Original Purpose**: Scout phase enhancement prompt
**Why Archived**: Never referenced in orchestrator_prompt.txt. Content integrated into AGENT_PATTERN_REFERENCE.md and FAILURE_PATTERNS.md.
**Status**: Superseded

### flowise-json-structure-guide.md
**Original Purpose**: Early JSON structure guide
**Why Archived**: Never referenced in orchestrator_prompt.txt. Contains old patterns (supervisor/worker instead of agentAgentflow). Superseded by AGENT_PATTERN_REFERENCE.md.
**Status**: Deprecated (contains outdated patterns)

---

## Why These Files Were Archived

**Orchestrator Analysis** (2025-11-02):
- Searched orchestrator_prompt.txt for all `Read` commands
- Found 9 files actually read by Scout/Architect/Builder
- These 3 files had 0 references
- Content was already integrated into primary documentation

**Primary Documentation** (actively used):
- AGENT_PATTERN_REFERENCE.md (read 2x)
- FAILURE_PATTERNS.md (read 3x)
- BEST_PRACTICES.md (read 1x)
- STANDARD_TOOLS.md (read 1x)
- FLOWISE-STRUCTURE-AUTHORITY.md (read 1x)
- AGENT-NODE-TEMPLATE.json (read 1x)

---

## Accessing Archived Files

Files are preserved in this archive directory and available via git history.

To view:
```bash
ls /Users/name/homelab/context-foundry/extensions/flowise/prompts/archive/
```

To restore (if needed):
```bash
cd /Users/name/homelab/context-foundry/extensions/flowise/prompts/archive
mv <filename> ..
```

---

**Archived**: 2025-11-02
**Version**: v2.1.6 - Documentation cleanup

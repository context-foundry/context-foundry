# Flowise Extension - Development Workflow

**Last Updated**: November 1, 2025
**Working Directory**: `/Users/name/homelab/context-foundry/extensions/flowise/`

---

## ✅ CORRECT Working Directory

**ALWAYS work in this directory**:
```bash
cd /Users/name/homelab/context-foundry/extensions/flowise/
```

This is where Context Foundry builds actually READ files from during autonomous builds.

---

## ❌ DO NOT Use

**DO NOT work in these locations**:
- ❌ `/Users/name/homelab/context-foundry-flowise-extension/` (archived standalone repo)
- ❌ Any other flowise-related directory

**Why**: Context Foundry reads from `/context-foundry/extensions/flowise/` only. Changes elsewhere won't affect builds.

---

## 📁 Directory Structure

```
/Users/name/homelab/context-foundry/
├── tools/
│   └── orchestrator_prompt.txt          # Main orchestrator (loads FAILURE_PATTERNS.md)
└── extensions/
    └── flowise/                          # ← YOU ARE HERE
        ├── AGENT_PATTERN_REFERENCE.md    # Authority document (loaded by Architect)
        ├── FAILURE_PATTERNS.md           # Learning patterns (loaded by Architect)
        ├── SUCCESS_WORKFORCE_ALLOCATION.md
        ├── QUICKSTART.md
        ├── USER_GUIDE.md
        ├── BEST_PRACTICES.md
        ├── extensions_loader.py          # Extension loader logic
        ├── detector.py                   # Flowise project detection
        ├── analyzer.py                   # Template analysis
        ├── prompts/                      # Phase-specific prompts
        │   ├── FLOWISE-STRUCTURE-AUTHORITY.md
        │   ├── START-NODE-TEMPLATE.json
        │   ├── AGENT-NODE-TEMPLATE.json
        │   └── CONDITION-NODE-TEMPLATE.json
        ├── templates/                    # Real Flowise exports
        ├── patterns/                     # Pattern storage
        ├── integration/                  # Orchestrator injection points
        └── tests/                        # Unit tests
```

---

## 🔄 Development Workflow

### 1. Making Changes

```bash
# Navigate to correct directory
cd /Users/name/homelab/context-foundry/extensions/flowise/

# Make your edits
# Example: Update failure patterns
vim FAILURE_PATTERNS.md

# Test changes if needed
python3 tests/test_detector.py
```

### 2. Committing Changes

```bash
# Stage changes
git add FAILURE_PATTERNS.md

# Commit with clear message
git commit -m "learn: Add Pattern #5 - Missing Memory Configuration

Documented new failure pattern where agents generated without memory
config, causing context loss in multi-turn conversations.

Root cause: Builder didn't include agentEnableMemory/agentMemoryType
Prevention: Validation rule in Architect phase
"

# Push to Context Foundry repo
git push origin main
```

### 3. Verifying Integration

**Check if Orchestrator references your files**:
```bash
# Check Architect phase loads FAILURE_PATTERNS.md
grep -n "FAILURE_PATTERNS.md" /Users/name/homelab/context-foundry/tools/orchestrator_prompt.txt

# Expected output:
# 705:/Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md
```

**Check if Test phase updates patterns**:
```bash
# Check Test phase documents new patterns
grep -n "FLOWISE PROJECTS ONLY.*FAILURE_PATTERNS" /Users/name/homelab/context-foundry/tools/orchestrator_prompt.txt

# Expected output:
# 1508:   a3. **FLOWISE PROJECTS ONLY**: Update FAILURE_PATTERNS.md with new learnings:
```

---

## 🧪 Testing a Change

### Test Pattern Learning Loop

1. **Make a change to FAILURE_PATTERNS.md**:
```bash
cd /Users/name/homelab/context-foundry/extensions/flowise/
vim FAILURE_PATTERNS.md
# Add Pattern #5 or update existing pattern
```

2. **Launch a test build**:
```bash
# Context Foundry will:
# - Detect Flowise project
# - Load FAILURE_PATTERNS.md in Architect phase (line 704)
# - Builder avoids documented mistakes
# - Test phase adds new patterns if failures found (line 1508)
```

3. **Verify pattern was loaded**:
```bash
# Check build output for pattern references
grep -i "failure.*pattern\|pattern.*failure" /path/to/build/.context-foundry/scout-report.md
```

---

## 📊 File Ownership

| File | Who Reads It | When |
|------|-------------|------|
| `AGENT_PATTERN_REFERENCE.md` | Architect agent | Phase 2 (Architect) |
| `FAILURE_PATTERNS.md` | Architect agent | Phase 2 (Architect) |
| `FLOWISE-STRUCTURE-AUTHORITY.md` | Architect agent | Phase 2 (Architect) |
| `START-NODE-TEMPLATE.json` | Builder agent | Phase 2.5/3 (Builder) |
| `AGENT-NODE-TEMPLATE.json` | Builder agent | Phase 2.5/3 (Builder) |
| `detector.py` | Extension loader | Phase 0 (Detection) |
| `extensions_loader.py` | Orchestrator | Phase 0 (Detection) |

---

## 🎯 Quick Reference

### Where to Edit Common Files

**Adding a new failure pattern**:
```bash
vim /Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md
```

**Updating agent templates**:
```bash
vim /Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json
```

**Changing detection logic**:
```bash
vim /Users/name/homelab/context-foundry/extensions/flowise/detector.py
```

**Updating orchestrator integration**:
```bash
vim /Users/name/homelab/context-foundry/tools/orchestrator_prompt.txt
```

---

## ⚠️ Common Mistakes

### ❌ WRONG: Editing standalone repo
```bash
cd /Users/name/homelab/context-foundry-flowise-extension/  # ❌ WRONG
vim FAILURE_PATTERNS.md
# This change won't affect builds!
```

### ✅ CORRECT: Editing Context Foundry extension
```bash
cd /Users/name/homelab/context-foundry/extensions/flowise/  # ✅ CORRECT
vim FAILURE_PATTERNS.md
# This change WILL affect builds!
```

---

## 🔍 Debugging

### "My changes aren't being used in builds"

**Check 1**: Are you in the right directory?
```bash
pwd
# Expected: /Users/name/homelab/context-foundry/extensions/flowise
```

**Check 2**: Did you commit to the right repo?
```bash
cd /Users/name/homelab/context-foundry
git log --oneline -5
# Should show your recent commits
```

**Check 3**: Is orchestrator loading your file?
```bash
grep -n "FAILURE_PATTERNS.md" /Users/name/homelab/context-foundry/tools/orchestrator_prompt.txt
# Should show line 705
```

---

## 📝 Commit Message Guidelines

### Pattern Updates
```
learn: Add Pattern #{N} - {Pattern Name}

{Brief description of symptom}

Root cause: {What caused it}
Prevention: {How to avoid}
Detected in: {Build ID or project name}
```

### Bug Fixes
```
fix: {What was broken}

{Why it was broken}
{How you fixed it}
{Tests added/updated}
```

### Documentation
```
docs: {What documentation changed}

{Why this helps users/builders}
```

---

## 🎉 Success Criteria

You know you're in the right place when:
- ✅ `pwd` shows `/context-foundry/extensions/flowise/`
- ✅ `git remote -v` shows `context-foundry/context-foundry`
- ✅ Your changes appear in builds immediately
- ✅ Commits go to Context Foundry main repo

---

## 🗂️ Archived Locations

These locations are **archived** and should NOT be used for active development:

- `/Users/name/homelab/context-foundry-flowise-extension/`
  - Purpose: Original standalone development repo
  - Status: Archived for reference
  - Remote: `snedea/context-foundry-flowise-extension`

---

**Remember**: ONE SOURCE OF TRUTH = `/Users/name/homelab/context-foundry/extensions/flowise/`

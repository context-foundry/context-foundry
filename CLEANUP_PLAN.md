# Context Foundry Cleanup & Optimization Plan
**Generated:** 2025-11-09
**Based on:** Full Diagnostic Report

---

## 🎯 CLEANUP STRATEGY

### Philosophy
Remove or fix code that:
1. Doesn't work and never has
2. Isn't being used but consuming resources
3. Has working alternatives already in use
4. Adds confusion without value

### DON'T Remove
- Code that works but is untested
- Optional features that might be used
- Experimental features under development
- Properly documented "dormant" features

---

## 📋 IMMEDIATE ACTIONS (5-10 minutes)

### 1. Fix Health Check Tool ⏳
**Issue:** Can't run due to Python version mismatch
**Root Cause:** `health_check.py` uses `#!/usr/bin/env python3` which resolves to 3.9, but rich installed for 3.13
**Options:**
- A. Add rich to requirements and install in all Python envs
- B. Update shebang to use specific Python version
- C. Remove health check tool (already have diagnostic reports)

**Recommendation:** Option A - Add to requirements

### 2. Decision on BAML ⏳
**Current:** Code exists, package not installed
**Options:**
- A. Install BAML: `pip install baml-py`
- B. Remove BAML integration code (5 files in `integrations/baml/`)
- C. Document as optional, leave dormant

**Files:**
- `integrations/baml/` - 3 Python files
- `tools/baml_integration.py` - Integration layer
- `requirements-baml.txt` - Dependencies

**Recommendation:** Option C - Document as optional (costs $0.20/build, not needed)

### 3. Update Requirements Files ⏳
**Issue:** Multiple requirements files, unclear which to use
**Files:**
- `requirements.txt` - Main (legacy?)
- `requirements-mcp.txt` - MCP server (current)
- `requirements-baml.txt` - BAML (optional)
- `integrations/baml/python/requirements.txt` - BAML Python client

**Recommendation:** Consolidate and document:
- `requirements-core.txt` - Core functionality
- `requirements-optional.txt` - Optional features (BAML, livestream, etc.)
- `requirements-dev.txt` - Development tools

---

## 🔧 QUICK WINS (15-30 minutes)

### 4. Remove Empty/Unused Database Tables ⏳
**Tables to evaluate:**
- `project_registry` (0 rows)
- `agent_network` (0 rows)
- `task_history` (0 rows, archiving not implemented)

**Recommendation:**
- Keep structure, document as "not yet implemented"
- OR implement archiving for task_history

### 5. Clean Up Log Files ⏳
**Issue:** Multiple log files, unclear purpose
**Files:**
- `daemon.log` (1.8 MB) - Main daemon log
- `launchd-stdout.log` (8.3 KB) - Launchd stdout
- `launchd-stderr.log` (97 KB) - Launchd stderr

**Recommendation:**
- Document purpose of each
- Add log rotation (keep last 7 days)
- Consolidate to single log file?

### 6. Document Unused Features ⏳
Create `FEATURES.md` documenting:
- ✅ Active features (MCP, Evolution, Patterns)
- ⏸️ Paused features (waiting for completion)
- ❓ Experimental features (untested)
- 🗑️ Deprecated features (to be removed)

---

## 🏗️ MEDIUM EFFORT (1-2 hours)

### 7. Connect or Remove Metrics System ⏳
**Current:** 13-table database, all empty
**Decision needed:**
- A. Connect metrics to autonomous builds (add collection code)
- B. Remove entire metrics system (save ~500KB DB space)
- C. Keep dormant, document as "future feature"

**Files to evaluate if removing:**
- `tools/metrics/` (4 files)
- `~/.context-foundry/metrics.db`
- References in test files

**Recommendation:** Connect it OR remove it (don't leave half-done)

### 8. Evaluate Cache System ⏳
**Current:** Code exists, cache directory empty
**Decision needed:**
- A. Test incremental builds, ensure cache works
- B. Remove cache code if not functional
- C. Document known issues

**Files:**
- `tools/cache/` (4 files)
- `tools/incremental/` (6 files)
- `~/.context-foundry/cache/`

**Recommendation:** Run incremental build test first

### 9. Audit Optional Systems ⏳
**For each system, decide: Active / Dormant / Remove**

| System | LOC | Files | Status | Keep? |
|--------|-----|-------|--------|-------|
| **Mission Control TUI** | ~2000 | 1 | ❓ Untested | ✅ Test first |
| **Web Dashboard** | ~500 | 1 | ❓ Untested | ✅ Test first |
| **REST API** | ~300 | 1 | ❓ Untested | ✅ Test first |
| **WebSocket Streaming** | ~200 | 1 | ❓ Untested | ✅ Test first |
| **Livestream** | ~1000 | 6 | ❓ Untested | ❓ Evaluate |
| **Back Pressure** | ~800 | 4 | ❓ Untested | ✅ Keep (documented) |
| **Context Budget** | ~600 | 4 | ❓ Untested | ✅ Keep (documented) |

**Recommendation:** Test each before removing

---

## 🔍 DEEP CLEANUP (2-4 hours)

### 10. Remove Truly Unused Code ⏳

#### Candidates for Removal:
Search for:
- Commented-out code blocks
- Unused imports
- Dead functions (never called)
- Duplicate implementations
- Test fixtures for deleted features

**Tools:**
```bash
# Find unused imports
ruff check . --select F401

# Find unused variables
ruff check . --select F841

# Find commented code
grep -r "^#.*def\|^#.*class" --include="*.py"
```

### 11. Consolidate Documentation ⏳

**Current state:** Docs scattered across:
- `docs/` (23 files)
- `README.md`
- `tools/*/README.md`
- Inline comments

**Recommendation:**
- Create `docs/index.md` with clear structure
- Link all related docs
- Remove duplicate content
- Update outdated info

### 12. Standardize Naming ⏳

**Issues identified:**
- Inconsistent function names (`get_version` vs `check_baml_available`)
- Mixed conventions (snake_case vs camelCase in JS)
- Unclear variable names

**Recommendation:** Define style guide, apply gradually

---

## 📊 ESTIMATED IMPACT

### Storage Savings
| Action | Savings | Effort |
|--------|---------|--------|
| Remove unused logs | ~1-2 GB | 5 min |
| Remove empty DB tables | ~500 KB | 10 min |
| Remove unused dependencies | ~50-100 MB | 15 min |
| Remove commented code | ~10-20 KB | 1 hour |

### Performance Impact
| Action | Improvement | Effort |
|--------|-------------|--------|
| Connect metrics | +Observability | 2 hours |
| Fix cache system | +Build speed (10-40%) | 1 hour |
| Remove unused imports | -Startup time (5%) | 30 min |

### Developer Experience
| Action | Impact | Effort |
|--------|--------|--------|
| Document features | +Clarity | 1 hour |
| Consolidate requirements | +Setup ease | 30 min |
| Add health check | +Debugging | 15 min |
| Create FEATURES.md | +Understanding | 30 min |

---

## 🚀 RECOMMENDED EXECUTION ORDER

### Phase 1: Quick Wins (30 minutes)
1. ✅ Fix VERSION file (DONE)
2. ✅ Fix version.py (DONE)
3. ⏳ Install missing deps (rich to all Python envs)
4. ⏳ Run Ruff to find/fix obvious issues
5. ⏳ Document BAML as optional

### Phase 2: Critical Decisions (1 hour)
6. ⏳ Test incremental builds → Keep or remove cache
7. ⏳ Test metrics collection → Connect or remove
8. ⏳ Test optional systems → Document status
9. ⏳ Create FEATURES.md

### Phase 3: Cleanup Execution (2 hours)
10. ⏳ Remove confirmed unused code
11. ⏳ Consolidate documentation
12. ⏳ Update requirements files
13. ⏳ Add log rotation

### Phase 4: Polish (1 hour)
14. ⏳ Run full test suite
15. ⏳ Update README with current state
16. ⏳ Create upgrade guide
17. ⏳ Document known issues

---

## ⚠️ RISKS & MITIGATION

### Risk #1: Breaking Working Features
**Mitigation:**
- Create git branch for cleanup
- Test after each major change
- Keep full backup before cleanup

### Risk #2: Removing Code That's Actually Used
**Mitigation:**
- Grep for function calls before removing
- Check test files for usage
- Ask maintainers before deleting large chunks

### Risk #3: Time Sink (Over-optimization)
**Mitigation:**
- Set time box for each phase
- Focus on high-impact changes first
- Document "won't fix" items for later

---

## 📝 CLEANUP CHECKLIST

### Prerequisites
- [ ] Create cleanup branch: `git checkout -b cleanup/system-optimization`
- [ ] Back up databases: `cp -r ~/.context-foundry ~/.context-foundry.backup`
- [ ] Document current state: (DONE - diagnostic reports)

### Quick Wins
- [x] Fix MCP server crash
- [x] Fix version.py
- [ ] Install rich for all Python versions
- [ ] Run Ruff cleanup
- [ ] Document BAML status

### Medium Tasks
- [ ] Test and document cache system
- [ ] Test and document metrics system
- [ ] Test optional features (Mission Control, etc.)
- [ ] Create FEATURES.md
- [ ] Consolidate requirements files

### Deep Cleanup
- [ ] Remove unused imports (Ruff F401)
- [ ] Remove unused variables (Ruff F841)
- [ ] Remove commented code
- [ ] Consolidate documentation
- [ ] Add log rotation

### Verification
- [ ] Run full test suite
- [ ] Test end-to-end build
- [ ] Verify MCP tools work
- [ ] Check daemon still runs
- [ ] Review diff before committing

---

## 🎯 SUCCESS CRITERIA

### System Health Target: 90/100
**Current:** 75/100

**Required improvements:**
- Core Functionality: 95 → 98 (+3)
- Dependencies: 80 → 100 (+20)
- Databases: 60 → 80 (+20)
- Optional Features: 30 → 70 (+40)
- Observability: 40 → 80 (+40)

**How to achieve:**
1. ✅ Fix all critical issues (DONE)
2. Install all required dependencies (+20)
3. Document feature status (+30)
4. Test and fix optional features (+40)
5. Connect metrics system (+20)

### Code Quality Target
- [ ] Zero Ruff errors
- [ ] <10 Ruff warnings
- [ ] All tests passing
- [ ] Documentation up-to-date
- [ ] Clear feature status

### Documentation Target
- [ ] FEATURES.md created
- [ ] All optional features documented
- [ ] Setup guide updated
- [ ] Troubleshooting guide created
- [ ] Architecture diagrams current

---

## 📅 TIMELINE

### Today (2025-11-09) - Quick Wins
- [x] Diagnostic complete
- [x] MCP server fixed
- [ ] Dependencies installed
- [ ] Ruff cleanup run
- [ ] FEATURES.md started

### Tomorrow - Critical Decisions
- [ ] Test all optional systems
- [ ] Document feature status
- [ ] Decide on metrics/cache
- [ ] Update requirements

### Next Week - Deep Cleanup
- [ ] Remove confirmed unused code
- [ ] Consolidate documentation
- [ ] Polish and test
- [ ] Create PR with changes

---

## 🔗 RELATED DOCUMENTS

- [FULL_DIAGNOSTIC_REPORT.md](FULL_DIAGNOSTIC_REPORT.md) - Complete system analysis
- [SYSTEM_HEALTH_REPORT.md](SYSTEM_HEALTH_REPORT.md) - Initial findings
- [INNOVATIONS.md](docs/INNOVATIONS.md) - Feature documentation
- [ROADMAP.md](docs/ROADMAP.md) - Future plans

---

**Next Step:** Start Phase 1 quick wins!

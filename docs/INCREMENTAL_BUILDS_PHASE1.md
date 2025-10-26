# Smart Incremental Builds - Phase 1 Implementation

**Status**: ✅ Implemented
**Date**: 2025-10-25
**Expected Impact**: 30-50% speedup on repeated/similar builds

---

## Overview

Phase 1 of Smart Incremental Builds implements intelligent phase skipping and caching to significantly reduce build times for repeated or similar tasks. Instead of rebuilding everything from scratch, the system now:

- **Reuses Scout reports** for similar tasks (within 24h)
- **Skips test execution** when no code has changed
- **Intelligently decides** which phases can be skipped

---

## What Was Implemented

### 1. Cache Infrastructure (`tools/cache/`)

**New Files Created:**
- `__init__.py` - Base utilities (hashing, TTL, metadata)
- `scout_cache.py` - Scout report caching system
- `test_cache.py` - Test result caching with file change detection
- `cache_manager.py` - Centralized cache operations

**Features:**
- SHA256 file and task hashing
- 24-hour TTL (configurable)
- Automatic metadata tracking
- Cache statistics and cleanup

### 2. Scout Cache System

**How It Works:**
```python
# Hash task description to create cache key
task: "Build a weather app with React"
mode: "new_project"
→ cache_key: "a1b2c3d4e5f67890"

# Check cache before Scout phase
cached_report = get_cached_scout_report(task, mode, working_dir)
if cached_report:
    # Cache HIT - reuse report, skip Scout phase
    save_to_file(cached_report)
    skip_to_architect()
else:
    # Cache MISS - run normal Scout phase
    run_scout()
    save_scout_report_to_cache(report)
```

**Benefits:**
- Repeated similar tasks skip Scout entirely
- Task normalization catches minor wording differences
- 24-hour cache window for iterative development

### 3. Test Result Cache

**How It Works:**
```python
# Compute hashes of all source files
file_hashes = {
    "src/main.js": "sha256_hash_1",
    "src/utils.js": "sha256_hash_2",
    ...
}

# Before running tests
cached_results = get_cached_test_results(working_dir)
if cached_results and all_files_unchanged:
    # Cache HIT - reuse test results, skip testing
    reuse_cached_results()
else:
    # Cache MISS - run tests
    run_tests()
    save_test_results_to_cache(results)
```

**Benefits:**
- Skips expensive test execution when code unchanged
- Perfect for documentation-only updates
- Detects even single-character code changes

### 4. Smart Phase Skip Logic (orchestrator_prompt.txt)

**Added Sections:**

**Scout Phase (Line 239-274):**
```
⚡ SMART CACHE CHECK - INCREMENTAL BUILDS:
IF incremental mode enabled:
  1. Check for cached Scout report
  2. If CACHE_HIT: Skip to Architect
  3. If CACHE_MISS: Run Scout, save to cache
```

**Test Phase (Line 623-666):**
```
⚡ SMART CACHE CHECK - INCREMENTAL BUILDS:
IF incremental mode enabled:
  1. Check for cached test results
  2. If CACHE_HIT and tests PASSED: Skip to Documentation
  3. If CACHE_MISS: Run tests, save to cache
```

### 5. MCP Server Integration (mcp_server.py)

**Changes Made:**
- Line 1282-1283: Added `incremental` and `force_rebuild` to task_config
- Line 1399: Added `incremental_mode` to return JSON
- Line 1407: Added status message for incremental mode

**Usage:**
```python
autonomous_build_and_deploy(
    task="Build weather app",
    working_directory="weather-app",
    incremental=True,  # Enable smart caching
    force_rebuild=False  # Set True to bypass cache
)
```

### 6. Unit Tests (tests/test_cache_system.py)

**Test Coverage:**
- ✅ 16 tests created
- ✅ 16 tests passing (100%)
- ✅ Scout cache: task hashing, cache hit/miss, TTL
- ✅ Test cache: file hashing, change detection
- ✅ Cache manager: stats, cleanup, size limits

---

## How To Use

### Enable Incremental Mode

**Option 1: Natural Language**
```
Build a weather app with React. Use incremental mode.
```

**Option 2: Direct MCP Call**
```python
autonomous_build_and_deploy(
    task="Build weather app",
    working_directory="/tmp/weather-app",
    incremental=True
)
```

### Force Full Rebuild

```python
autonomous_build_and_deploy(
    task="Build weather app",
    working_directory="/tmp/weather-app",
    incremental=True,
    force_rebuild=True  # Bypass all caches
)
```

### Check Cache Status

```python
from tools.cache.cache_manager import CacheManager

manager = CacheManager("/tmp/weather-app")
manager.print_stats()
```

**Output:**
```
📊 Context Foundry Cache Statistics
==================================================
Cache directory: /tmp/weather-app/.context-foundry/cache
Total size: 0.05 MB
Total files: 3

Scout Cache:
  Total entries: 1
  Valid entries: 1
  Expired entries: 0
  Size: 12.34 KB

Test Cache:
  Has cached results: True
  Cache valid: True
  Files tracked: 15
  Last test: 25/25 passed
```

---

## Expected Performance Impact

### Scenario 1: Repeated Build (Same Task)

**Without Incremental:**
- Scout: 2 min
- Architect: 2 min
- Builder: 5 min
- Test: 3 min
- **Total: 12 minutes**

**With Incremental (Cache Hit):**
- Scout: **SKIPPED** (reused cache)
- Architect: 2 min
- Builder: 5 min
- Test: **SKIPPED** (no code changes)
- **Total: 7 minutes (42% faster)**

### Scenario 2: Documentation-Only Update

**Without Incremental:**
- All phases run: 12 minutes

**With Incremental:**
- Scout: SKIPPED
- Architect: Maybe skipped
- Builder: Minimal (only README change)
- Test: **SKIPPED** (no code changes)
- **Total: ~3 minutes (75% faster)**

### Scenario 3: Iterative Feature Development

**Building 4 similar features sequentially:**

**Without Incremental:**
- Build 1: 12 min
- Build 2: 12 min
- Build 3: 12 min
- Build 4: 12 min
- **Total: 48 minutes**

**With Incremental:**
- Build 1: 12 min (cache miss)
- Build 2: 7 min (Scout cached)
- Build 3: 7 min (Scout cached)
- Build 4: 7 min (Scout cached)
- **Total: 33 minutes (31% faster)**

---

## Cache Locations

### Per-Project Cache
```
your-project/
└── .context-foundry/
    └── cache/
        ├── scout-{hash}.md           # Cached Scout reports
        ├── scout-{hash}.meta.json    # Scout metadata
        ├── test-results.json         # Cached test results
        ├── test-results.meta.json    # Test metadata
        └── file-hashes.json          # Source file hashes
```

### Cache Metadata Example
```json
{
  "created_at": "2025-10-25T10:30:00",
  "cache_file": "scout-a1b2c3d4.md",
  "original_task": "Build a weather app with React",
  "normalized_task": "build a weather app with react",
  "mode": "new_project",
  "cache_key": "a1b2c3d4"
}
```

---

## Configuration

### Default Settings
- **Scout cache TTL**: 24 hours
- **Test cache TTL**: 24 hours
- **Max cache size**: 100 MB (not enforced yet)

### Customization (Future)
```python
# In tools/cache/__init__.py
DEFAULT_CACHE_TTL_HOURS = 24  # Change to 48 for longer cache
DEFAULT_MAX_CACHE_SIZE_MB = 100  # Increase for larger projects
```

---

## Limitations & Future Work

### Current Limitations

1. **No Architect caching** - Architect phase always runs
2. **No builder caching** - Builder phase always runs
3. **Simple task normalization** - Could be smarter with NLP
4. **No partial test caching** - All-or-nothing for test results

### Phase 2 Planned Features (Next 1-2 Weeks)

1. **File-Level Change Detection**
   - Build dependency graph
   - Only rebuild changed modules
   - Expected: 70-90% speedup on rebuilds

2. **Incremental Builder**
   - Preserve unchanged files
   - Smart dependency resolution
   - Artifact caching

3. **Incremental Test Runner**
   - Test impact analysis
   - Only run affected tests
   - Cache individual test results

4. **Architect Diff Detection**
   - Detect scope of changes (small/medium/large)
   - Skip re-architecting for small changes
   - Reuse architecture for similar projects

---

## Testing

### Run Unit Tests
```bash
python3 -m pytest tests/test_cache_system.py -v
```

### Integration Testing (Manual)

**Test 1: Scout Cache Hit**
```bash
# Build 1 (cache miss)
autonomous_build_and_deploy(
    task="Build a simple todo app",
    working_directory="/tmp/todo-app",
    incremental=True
)
# Expected: Normal 12-minute build

# Build 2 (cache hit)
autonomous_build_and_deploy(
    task="Build a simple todo application",  # Similar task
    working_directory="/tmp/todo-app-2",
    incremental=True
)
# Expected: Scout phase skipped, ~10-minute build
```

**Test 2: Test Cache Hit**
```bash
# Build 1
autonomous_build_and_deploy(
    task="Build todo app",
    working_directory="/tmp/todo",
    incremental=True
)
# Expected: Normal build, tests run

# Build 2 (no code changes)
autonomous_build_and_deploy(
    task="Update README",
    working_directory="/tmp/todo",
    mode="add_docs",
    incremental=True
)
# Expected: Test phase skipped
```

---

## Troubleshooting

### Cache Not Working

**Symptom**: Phases not being skipped, no "Cache HIT" messages

**Solutions:**
1. Verify incremental mode enabled:
   ```python
   # Check task config in mcp_server output
   "incremental": true
   ```

2. Check cache files exist:
   ```bash
   ls -la /tmp/project/.context-foundry/cache/
   ```

3. Check TTL expiration:
   ```bash
   # Files older than 24 hours are expired
   find .context-foundry/cache -name "*.md" -mtime +1
   ```

### Cache Too Large

**Symptom**: Cache directory using too much space

**Solution:**
```python
from tools.cache.cache_manager import CacheManager

manager = CacheManager("/tmp/project")

# Clear expired entries
deleted = manager.clean_expired()
print(f"Deleted {deleted['total']} expired entries")

# Clear all cache
manager.clear_all()

# Clear specific type
manager.clear_by_type("scout")
```

### Force Cache Bypass

**Temporary bypass:**
```python
autonomous_build_and_deploy(
    task="Build app",
    working_directory="/tmp/app",
    incremental=False  # Disable incremental mode
)
```

**Or force rebuild:**
```python
autonomous_build_and_deploy(
    task="Build app",
    working_directory="/tmp/app",
    incremental=True,
    force_rebuild=True  # Bypass cache even in incremental mode
)
```

---

## Success Metrics

### Implementation Metrics
- ✅ **Files Created**: 5 new cache modules
- ✅ **Lines of Code**: ~800 LOC
- ✅ **Test Coverage**: 16/16 tests passing (100%)
- ✅ **Documentation**: Complete
- ✅ **Integration**: Fully wired into orchestrator

### Performance Targets (To Be Validated)
- 🎯 **30-50% speedup** on repeated builds
- 🎯 **Scout cache hit rate**: 60%+ in iterative development
- 🎯 **Test cache hit rate**: 80%+ for documentation updates
- 🎯 **Cache overhead**: <100ms per phase check

---

## Next Steps

1. **Integration Testing** (Pending)
   - Run real builds with incremental mode
   - Measure actual speedup
   - Validate 30-50% improvement

2. **Phase 2 Planning** (1-2 weeks)
   - Design file-level change detection
   - Implement incremental builder
   - Add test impact analysis

3. **Documentation Updates**
   - Update README.md with incremental mode
   - Add to USER_GUIDE.md
   - Create video demo

---

## Credits

**Feature**: Smart Incremental Builds - Phase 1
**Implementation Date**: October 25, 2025
**Developed By**: Context Foundry Team
**Timeline**: 2-3 days (as planned)

---

## Appendix: File Structure

```
context-foundry/
├── tools/
│   ├── cache/                          # NEW: Cache system
│   │   ├── __init__.py                 # Base utilities
│   │   ├── scout_cache.py              # Scout caching
│   │   ├── test_cache.py               # Test caching
│   │   └── cache_manager.py            # Cache management
│   ├── mcp_server.py                   # MODIFIED: Wire up incremental flag
│   └── orchestrator_prompt.txt         # MODIFIED: Smart phase skip logic
├── tests/
│   └── test_cache_system.py            # NEW: 16 unit tests
└── docs/
    └── INCREMENTAL_BUILDS_PHASE1.md    # NEW: This document
```

---

**Status**: ✅ Phase 1 Complete - Ready for Integration Testing

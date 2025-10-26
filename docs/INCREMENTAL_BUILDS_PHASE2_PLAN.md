# Smart Incremental Builds - Phase 2 Plan

**Version**: 2.2.0 (Next Release)
**Target Completion**: 1-2 weeks
**Expected Impact**: 70-90% speedup on rebuild scenarios

---

## Executive Summary

Phase 1 delivered **10-40% speedup** (best case 37%) through Scout cache and intelligent phase skipping. Phase 2 will achieve **70-90% speedup** through file-level change detection, incremental building, and global cache sharing.

### Phase 1 vs Phase 2

| Feature | Phase 1 (Current) | Phase 2 (Planned) |
|---------|------------------|-------------------|
| **Scout Cache** | ✅ Per-project | ✅ Global (cross-project) |
| **Test Cache** | ⚠️ Not working | ✅ Fully functional |
| **Change Detection** | ❌ None | ✅ File-level SHA256 tracking |
| **Incremental Builder** | ❌ None | ✅ Only rebuild changed modules |
| **Test Impact Analysis** | ❌ None | ✅ Only run affected tests |
| **Best Case Speedup** | 37% | **70-90%** |
| **Rebuild Speedup** | N/A | **80-95%** |
| **Documentation Updates** | 13% | **95%** |

---

## Goals & Success Criteria

### Primary Goals

1. **File-Level Change Detection** - Know exactly what changed since last build
2. **Incremental Builder** - Only rebuild changed files and their dependencies
3. **Global Scout Cache** - Share Scout reports across all projects
4. **Test Impact Analysis** - Only run tests for changed code
5. **Fix Test Cache** - Complete Phase 1 unfinished work

### Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Small Code Changes** | 70-90% faster | 5-file change in 50-file project |
| **Documentation Only** | 95% faster | README-only update |
| **Similar Projects** | 50-70% faster | Second todo app after first |
| **Rebuild (no changes)** | 95% faster | Re-run without any changes |
| **Cache Hit Rate** | 80%+ | Across 10 test builds |

### Non-Goals (Future Phases)

- Distributed caching across machines
- Cloud-based cache storage
- Build artifact compression
- Incremental documentation (Phase 3)

---

## Phase 2 Features

### 1. Global Scout Cache

**Current State**: Scout cache is per-project (`.context-foundry/cache/`)

**Phase 2 Design**: Global cache shared across all projects

```
~/.context-foundry/
└── cache/
    └── global/
        ├── scout/
        │   ├── {hash}.md           # Cached Scout reports
        │   ├── {hash}.meta.json    # Metadata
        │   └── index.json          # Cache index
        └── stats.json              # Global cache statistics
```

**Implementation**:

1. **Create global cache directory** (`~/.context-foundry/cache/global/`)
2. **Modify scout_cache.py** to check global cache before local
3. **Add cache sharing logic**:
   ```python
   def get_cached_scout_report(task, mode, working_dir, ttl_hours=24):
       # 1. Check project-local cache first
       local_cache = check_local_cache(working_dir, task, mode)
       if local_cache:
           return local_cache

       # 2. Check global cache
       global_cache = check_global_cache(task, mode)
       if global_cache:
           # Copy to local cache for faster future access
           copy_to_local(global_cache, working_dir)
           return global_cache

       return None
   ```

4. **Add cache index** for fast lookups
5. **Implement cache statistics** tracking

**Expected Impact**:
- ✅ 90%+ cache hit rate for similar projects
- ✅ 5-7 minutes saved per build (Scout phase skip)
- ✅ Cross-project learning

**Estimated Time**: 1-2 days

---

### 2. File-Level Change Detection

**Concept**: Track which files changed since last build

**Design**:

```python
# tools/cache/change_detector.py

class ChangeDetector:
    """Detect file-level changes between builds."""

    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.baseline_file = Path(working_dir) / ".context-foundry/cache/file-baseline.json"

    def create_baseline(self) -> Dict[str, str]:
        """Hash all source files and save baseline."""
        hashes = {}
        for file in self.get_source_files():
            hashes[str(file)] = hash_file(file)

        self.baseline_file.write_text(json.dumps({
            "created_at": datetime.now().isoformat(),
            "files": hashes
        }))
        return hashes

    def detect_changes(self) -> ChangeSet:
        """Compare current state to baseline."""
        baseline = self.load_baseline()
        current = self.compute_current_hashes()

        return ChangeSet(
            added=[f for f in current if f not in baseline],
            modified=[f for f in current if f in baseline and current[f] != baseline[f]],
            deleted=[f for f in baseline if f not in current],
            unchanged=[f for f in current if f in baseline and current[f] == baseline[f]]
        )
```

**File Categories**:
- **Source files**: `*.js, *.ts, *.py, *.java, etc.`
- **Config files**: `package.json, requirements.txt, etc.`
- **Documentation**: `*.md, docs/**`
- **Tests**: `tests/**, *.test.*, *.spec.*`

**Expected Impact**:
- ✅ Know exactly what changed
- ✅ Enable targeted rebuilding
- ✅ Enable test impact analysis

**Estimated Time**: 1 day

---

### 3. Incremental Builder

**Current State**: Builder always rebuilds everything from scratch

**Phase 2 Design**: Only rebuild changed files and dependencies

```python
# tools/incremental/builder.py

class IncrementalBuilder:
    """Build only what changed."""

    def plan_build(self, changes: ChangeSet, architecture: Architecture) -> BuildPlan:
        """Create build plan based on changes."""

        # 1. Determine affected modules
        affected = self.compute_affected_modules(changes, architecture)

        # 2. Resolve dependencies
        to_rebuild = self.resolve_dependencies(affected, architecture)

        # 3. Create build plan
        return BuildPlan(
            files_to_rebuild=to_rebuild,
            files_to_preserve=[f for f in self.all_files if f not in to_rebuild],
            estimated_time=self.estimate_build_time(to_rebuild)
        )

    def execute_build(self, plan: BuildPlan):
        """Execute incremental build."""
        # Preserve unchanged files
        for file in plan.files_to_preserve:
            self.mark_as_preserved(file)

        # Rebuild only affected files
        for file in plan.files_to_rebuild:
            self.rebuild_file(file)
```

**Dependency Resolution**:
```python
def compute_affected_modules(self, changes: ChangeSet, arch: Architecture):
    """Compute which modules are affected by changes."""
    affected = set(changes.modified + changes.added)

    # Add modules that depend on changed files
    for changed_file in changes.modified:
        dependents = arch.get_dependents(changed_file)
        affected.update(dependents)

    return list(affected)
```

**Expected Impact**:
- ✅ 70-90% faster on small changes (5 files in 50-file project)
- ✅ 95% faster on config-only changes
- ✅ Preserve validated code

**Estimated Time**: 2-3 days

---

### 4. Test Impact Analysis

**Concept**: Only run tests for changed code

```python
# tools/incremental/test_selector.py

class TestSelector:
    """Select which tests to run based on changes."""

    def select_tests(self, changes: ChangeSet, test_map: TestMap) -> List[str]:
        """Select tests affected by changes."""

        if not changes.modified and not changes.added:
            # No code changes = skip all tests (reuse cache)
            return []

        tests_to_run = set()

        # 1. Direct test file changes
        for file in changes.modified + changes.added:
            if self.is_test_file(file):
                tests_to_run.add(file)

        # 2. Tests that cover changed source files
        for file in changes.modified + changes.added:
            if self.is_source_file(file):
                covering_tests = test_map.get_tests_for_file(file)
                tests_to_run.update(covering_tests)

        # 3. Always run critical tests (e.g., integration tests)
        tests_to_run.update(self.get_critical_tests())

        return list(tests_to_run)
```

**Test Map Creation**:
```python
def create_test_map(self, working_dir: str) -> TestMap:
    """Create mapping of source files to tests."""
    # Analyze imports/requires in test files
    # Build graph of what each test covers
    # Save to .context-foundry/cache/test-map.json
```

**Expected Impact**:
- ✅ 80-95% faster test execution
- ✅ Run only relevant tests
- ✅ Catch regressions quickly

**Estimated Time**: 2-3 days

---

### 5. Fix Test Cache (Phase 1.1)

**Issue**: Test cache not saving in Phase 1

**Investigation Plan**:

1. **Check orchestrator_prompt.txt** - Verify test cache save commands exist
2. **Add debug logging** - Track when cache save is attempted
3. **Verify file permissions** - Ensure cache directory is writable
4. **Test manually** - Run cache save logic directly

**Likely Cause**:
- Orchestrator may skip cache save step
- Test phase may complete before cache save runs
- Permissions issue on cache directory

**Fix**:
```text
# In orchestrator_prompt.txt, after tests pass:

**STEP 4.3: Save test results to cache (if incremental mode)**

```bash
python3 -c "
import sys
sys.path.insert(0, '/path/to/context-foundry')
from tools.cache.test_cache import save_test_results_to_cache

test_results = {
    'success': True,
    'passed': 25,
    'total': 25,
    'duration': 10.5,
    'test_command': 'npm test'
}

save_test_results_to_cache('/path/to/working/dir', test_results)
print('✅ Test cache saved successfully')
"
```
```

**Estimated Time**: 0.5-1 day

---

## Implementation Timeline

### Week 1

**Days 1-2**: Global Scout Cache
- Create global cache directory structure
- Modify scout_cache.py for global lookups
- Add cache index and statistics
- Test with 5 similar builds

**Days 3-4**: File-Level Change Detection
- Implement ChangeDetector class
- Add baseline creation/comparison
- Test with various file change scenarios

**Day 5**: Fix Test Cache (Phase 1.1)
- Investigate test cache issue
- Implement fix
- Validate with real builds

### Week 2

**Days 6-8**: Incremental Builder
- Implement BuildPlan and dependency resolution
- Add file preservation logic
- Test with small/medium/large projects

**Days 9-10**: Test Impact Analysis
- Implement TestSelector and TestMap
- Add test coverage analysis
- Validate test selection accuracy

**Days 11-12**: Integration & Testing
- Wire all components together
- End-to-end testing (10+ builds)
- Performance validation

**Days 13-14**: Documentation & Release
- Update docs
- Create migration guide
- Release v2.2.0

---

## Technical Architecture

### Component Diagram

```
┌─────────────────────────────────────────────┐
│         Incremental Build System            │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐      ┌──────────────┐   │
│  │ Global Cache │◄─────┤ Scout Cache  │   │
│  │  ~/.context- │      │   Manager    │   │
│  │  foundry/    │      └──────────────┘   │
│  └──────────────┘                          │
│                                             │
│  ┌──────────────┐      ┌──────────────┐   │
│  │   Change     │─────►│  Incremental │   │
│  │  Detector    │      │   Builder    │   │
│  └──────────────┘      └──────────────┘   │
│         │                      │            │
│         ▼                      ▼            │
│  ┌──────────────┐      ┌──────────────┐   │
│  │    Test      │─────►│  Test Cache  │   │
│  │  Selector    │      │   Manager    │   │
│  └──────────────┘      └──────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

### Data Flow

```
Build Request (incremental=True)
    │
    ├─► Check Global Scout Cache
    │       ├─ HIT → Reuse report, skip Scout
    │       └─ MISS → Run Scout, save to global cache
    │
    ├─► Compute File Changes (ChangeDetector)
    │       └─► Generate ChangeSet (added, modified, deleted)
    │
    ├─► Plan Incremental Build (IncrementalBuilder)
    │       ├─► Resolve dependencies
    │       ├─► Determine files to rebuild
    │       └─► Create BuildPlan
    │
    ├─► Execute Build
    │       ├─► Preserve unchanged files
    │       └─► Rebuild only affected files
    │
    ├─► Select Tests (TestSelector)
    │       ├─► Analyze changes
    │       ├─► Map to affected tests
    │       └─► Create test run plan
    │
    └─► Run Tests & Cache Results
            ├─► Run selected tests only
            └─► Save results to test cache
```

---

## Testing Strategy

### Unit Tests

**New Test Files**:
- `tests/test_change_detector.py` (15 tests)
- `tests/test_incremental_builder.py` (20 tests)
- `tests/test_test_selector.py` (15 tests)
- `tests/test_global_cache.py` (10 tests)

**Total New Tests**: 60 tests

### Integration Tests

**Scenarios**:
1. **Small change**: Modify 1 file, verify only dependencies rebuild
2. **Medium change**: Modify 5 files, verify correct rebuild set
3. **Config change**: Update package.json, verify full rebuild
4. **Doc change**: Update README, verify skip all code/tests
5. **Test change**: Modify test file, verify only that test runs
6. **No change**: Re-run build, verify 95% skip
7. **Similar project**: Build second todo app, verify Scout cache hit
8. **Cross-project**: Build weather app after todo app, verify global cache

### Performance Validation

**Benchmark Suite** (20 builds):
- 5 builds: No changes (expect 95% speedup)
- 5 builds: Small changes (expect 70-90% speedup)
- 5 builds: Medium changes (expect 40-60% speedup)
- 5 builds: Similar projects (expect 50-70% speedup)

**Success Criteria**: Average speedup ≥ 60%

---

## Migration Guide (Phase 1 → Phase 2)

### For Users

**No action required!** Phase 2 is backwards compatible.

Existing Phase 1 caches will continue to work. Phase 2 adds:
- Global cache (automatically used)
- Change detection (automatically enabled)
- Incremental building (automatically applied)

### For Developers

**Cache directory changes**:
```bash
# Phase 1 (per-project only)
your-project/.context-foundry/cache/

# Phase 2 (per-project + global)
your-project/.context-foundry/cache/      # Local cache
~/.context-foundry/cache/global/          # Global cache (NEW)
```

**New cache files**:
```
.context-foundry/cache/
├── file-baseline.json        # File hashes baseline (NEW)
├── test-map.json              # Test coverage map (NEW)
└── build-plan.json            # Last build plan (NEW)
```

---

## Risks & Mitigations

### Risk 1: Incorrect Dependency Resolution

**Risk**: Builder misses dependencies, causes build failures

**Mitigation**:
- Conservative dependency resolution (rebuild more than less)
- Add `--force-full-rebuild` flag for safety
- Extensive testing with real projects

### Risk 2: Test Selection Errors

**Risk**: Skip tests that should run, miss regressions

**Mitigation**:
- Always run critical/integration tests
- Add `--run-all-tests` flag for safety
- Log which tests were skipped and why

### Risk 3: Global Cache Conflicts

**Risk**: Different projects interfere with each other's cache

**Mitigation**:
- Unique cache keys per task description
- Version cache format (invalidate on schema change)
- Add cache validation before use

### Risk 4: Performance Regression

**Risk**: Change detection overhead > savings

**Mitigation**:
- Benchmark all operations (< 100ms overhead acceptable)
- Cache file hashes (don't re-compute every time)
- Make change detection opt-in if needed

---

## Success Metrics

### Phase 2 Launch Criteria

All must be true before release:

- [ ] ✅ Global Scout cache: 90%+ hit rate in testing
- [ ] ✅ File change detection: 100% accuracy
- [ ] ✅ Incremental builder: 70%+ speedup on small changes
- [ ] ✅ Test selection: 80%+ test reduction
- [ ] ✅ Test cache fixed and working
- [ ] ✅ All 60 new tests passing
- [ ] ✅ 20-build benchmark: ≥60% average speedup
- [ ] ✅ Zero regressions on existing builds
- [ ] ✅ Documentation complete
- [ ] ✅ Migration guide ready

### Post-Launch Metrics (30 days)

- Average speedup ≥ 50% across all users
- Cache hit rate ≥ 70%
- Zero build failures due to incremental issues
- User satisfaction ≥ 4/5 stars

---

## Future Enhancements (Phase 3+)

Not included in Phase 2, but on the roadmap:

### Phase 3: Advanced Optimization (2-3 weeks)
- Incremental documentation (only update changed sections)
- Parallel test execution (run tests concurrently)
- Build artifact caching (cache compiled outputs)
- Smart Scout pruning (remove outdated cache entries)

### Phase 4: Distributed Caching (3-4 weeks)
- Cloud-based cache storage (S3, GCS)
- Team cache sharing (across developers)
- Cache analytics dashboard
- Cache compression (reduce storage)

### Phase 5: ML-Powered Optimization (4-6 weeks)
- Predict rebuild times
- Optimize dependency resolution with ML
- Auto-tune cache TTL based on usage
- Anomaly detection (unusual build patterns)

---

## Appendix A: File Structure Changes

### New Files

```
context-foundry/
├── tools/
│   ├── incremental/                  # NEW: Incremental build system
│   │   ├── __init__.py
│   │   ├── change_detector.py        # File change detection
│   │   ├── builder.py                # Incremental builder
│   │   ├── test_selector.py          # Test impact analysis
│   │   └── global_cache.py           # Global cache manager
│   └── cache/
│       └── global_cache.py           # MODIFIED: Add global cache support
├── tests/
│   ├── test_change_detector.py       # NEW
│   ├── test_incremental_builder.py   # NEW
│   ├── test_test_selector.py         # NEW
│   └── test_global_cache.py          # NEW
└── docs/
    ├── INCREMENTAL_BUILDS_PHASE2.md  # NEW: This document
    └── INCREMENTAL_BUILDS_MIGRATION.md # NEW: Migration guide
```

### Modified Files

```
tools/
├── orchestrator_prompt.txt           # Add incremental build logic
├── mcp_server.py                     # Wire up new features
└── cache/
    ├── scout_cache.py                # Add global cache support
    └── test_cache.py                 # Fix test cache save logic
```

---

## Appendix B: API Reference

### New Classes

```python
class ChangeDetector:
    def create_baseline() -> Dict[str, str]
    def detect_changes() -> ChangeSet
    def get_source_files() -> List[Path]

class ChangeSet:
    added: List[str]
    modified: List[str]
    deleted: List[str]
    unchanged: List[str]

class IncrementalBuilder:
    def plan_build(changes: ChangeSet, arch: Architecture) -> BuildPlan
    def execute_build(plan: BuildPlan) -> BuildResult
    def compute_affected_modules(changes: ChangeSet) -> List[str]

class BuildPlan:
    files_to_rebuild: List[str]
    files_to_preserve: List[str]
    estimated_time: float

class TestSelector:
    def select_tests(changes: ChangeSet, test_map: TestMap) -> List[str]
    def create_test_map(working_dir: str) -> TestMap
    def is_test_file(file: str) -> bool

class TestMap:
    def get_tests_for_file(file: str) -> List[str]
    def get_files_for_test(test: str) -> List[str]
    def update(file: str, tests: List[str])

class GlobalCacheManager:
    def get_cached_report(task: str, mode: str) -> Optional[str]
    def save_report(task: str, mode: str, content: str)
    def get_stats() -> Dict[str, Any]
    def cleanup_expired()
```

---

**Phase 2 Status**: 📋 Planning Complete - Ready for Implementation

**Target Release**: Context Foundry v2.2.0

**Expected Date**: 2-3 weeks from start

---

**🤖 Generated by Context Foundry Team**
**Document Version**: 1.0
**Last Updated**: January 21, 2025

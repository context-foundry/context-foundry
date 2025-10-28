# Scout Report: Smart Incremental Builds Phase 2

## Executive Summary
Phase 2 of Smart Incremental Builds will deliver 70-90% performance improvements on rebuilds by implementing:
1. Global Scout cache (cross-project sharing)
2. File-level change detection (git + hashing)
3. Incremental Builder (dependency-aware preservation)
4. Test impact analysis (selective test execution)
5. Incremental documentation (selective regeneration)

GitHub Issue: #11

## Key Requirements
- **Backward compatibility**: Must work alongside existing Phase 1 cache
- **Cross-project cache**: Scout cache shared at `~/.context-foundry/global-cache/`
- **Git independence**: Change detection must work without git (fallback to hashing)
- **Dependency tracking**: Build dependency graph for accurate incremental builds
- **Test mapping**: Map tests to source files for impact analysis
- **Graceful degradation**: Phase 2 features are optimizations, not requirements

## Technology Stack Decision
- **Language**: Python 3.10+ (existing Context Foundry standard)
- **Cache location**: `~/.context-foundry/global-cache/` (global) + `.context-foundry/cache/` (local)
- **Hashing**: SHA256 for file integrity (consistent with existing test_cache.py)
- **Graph library**: Built-in (using dict/set for dependency tracking - lightweight)
- **Git integration**: Optional via subprocess (graceful fallback if unavailable)

## Critical Architecture Recommendations

### 1. Global Scout Cache Architecture
- **Location**: `~/.context-foundry/global-cache/scout/`
- **Cache key**: `hash(normalized_task + project_type + main_technologies)`
- **Metadata**: Store project_type, tech_stack, task_type for better matching
- **TTL**: 7 days (longer than local cache, validated by semantic similarity)
- **Fallback**: If global cache miss → check local cache → run Scout

### 2. File-Level Change Detection
- **Primary**: Git diff against last build commit SHA
- **Fallback**: SHA256 hash comparison if no git
- **Tracking**: Store `.context-foundry/last-build-snapshot.json` with file hashes + git SHA
- **Granularity**: File-level (not line-level to keep simple)

### 3. Incremental Builder with Dependency Graph
- **Graph storage**: `.context-foundry/build-graph.json`
- **Nodes**: Files/modules created by Builder
- **Edges**: Dependencies (imports, includes, requires)
- **Algorithm**: Mark changed files + transitive dependencies as "needs rebuild"
- **Preservation**: Copy unchanged files from previous build

### 4. Test Impact Analysis
- **Mapping**: `.context-foundry/test-coverage-map.json`
- **Collection**: Parse test framework output or use static analysis
- **Strategy**: Run all tests if > 30% files changed, else selective
- **Fallback**: Run all tests if mapping unavailable

### 5. Incremental Documentation
- **Tracking**: `.context-foundry/docs-manifest.json` (file → source mapping)
- **Screenshots**: Preserve if UI code unchanged
- **README sections**: Update only affected sections
- **Strategy**: Regenerate docs for changed modules only

## Main Challenges and Mitigations

### Challenge 1: Cache Invalidation Complexity
- **Issue**: Global cache could serve stale results for "similar but different" tasks
- **Mitigation**: Strict cache key generation + semantic similarity threshold
- **Solution**: Include project_type and main_tech in cache key

### Challenge 2: Dependency Graph Accuracy
- **Issue**: Missing dependencies could cause incomplete rebuilds
- **Mitigation**: Conservative approach - mark uncertain files for rebuild
- **Solution**: Static analysis for imports + runtime dependency detection

### Challenge 3: Git Dependency
- **Issue**: Not all users have git or clean git state
- **Mitigation**: Graceful fallback to pure hash-based detection
- **Solution**: Try git first, catch exceptions, fall back to hashing

### Challenge 4: Test Coverage Mapping
- **Issue**: Different test frameworks have different output formats
- **Mitigation**: Start with Python (pytest + coverage.py), expand later
- **Solution**: Framework-specific parsers with fallback to "run all tests"

### Challenge 5: Backward Compatibility
- **Issue**: Phase 2 might break existing Phase 1 cache
- **Mitigation**: Separate cache namespaces + version markers
- **Solution**: Phase 1 uses `cache/scout-*.md`, Phase 2 uses `global-cache/scout/*.json`

## Testing Approach
1. **Unit tests**: Each Phase 2 module independently tested
2. **Integration tests**: Test Phase 1+2 working together
3. **Performance benchmarks**: Measure actual speedup vs claims
4. **Regression tests**: Ensure Phase 1 cache still works
5. **Failure modes**: Test graceful degradation (no git, no test coverage, etc.)

**Test files needed**:
- `tests/test_global_scout_cache.py`
- `tests/test_change_detector.py`
- `tests/test_incremental_builder.py`
- `tests/test_test_impact_analyzer.py`
- `tests/test_incremental_docs.py`
- `tests/test_phase2_integration.py`
- `tests/test_phase2_benchmarks.py`

## Timeline Estimate
- **Global Scout Cache**: 2-3 hours (build on existing scout_cache.py)
- **Change Detector**: 2-3 hours (git + hashing logic)
- **Incremental Builder**: 4-5 hours (dependency graph + preservation)
- **Test Impact Analyzer**: 3-4 hours (coverage parsing + mapping)
- **Incremental Docs**: 2-3 hours (manifest + selective regen)
- **Integration + Tests**: 4-5 hours (comprehensive testing)
- **Documentation**: 2 hours (merge Phase 1+2, add benchmarks)
- **Total**: 19-25 hours

## Success Criteria
✅ Global Scout cache reduces Scout time by 80%+ for similar projects  
✅ Incremental Builder preserves 70%+ files on small changes  
✅ Test impact analysis runs 60% fewer tests on targeted changes  
✅ Docs regeneration skips 90%+ unchanged content  
✅ All existing tests pass (backward compatibility)  
✅ New tests achieve 90%+ coverage of Phase 2 code  
✅ Performance benchmarks validate claims  
✅ Works with and without git  
✅ No breaking changes to Phase 1 functionality

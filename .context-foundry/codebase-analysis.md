# Codebase Analysis Report

## Project Overview
- Type: Python project - Software development automation framework
- Languages: Python 3.9+
- Architecture: MCP-based autonomous build system with multi-phase workflow

## Key Files
- Entry point: tools/mcp_server.py (MCP server implementation)
- Config: requirements.txt, setup.py
- Tests: test_detection.py, tools/test_parallel_runner.py
- Cache system: tools/cache/ (scout_cache.py, test_cache.py, cache_manager.py)

## Dependencies
- fastmcp>=2.0.0 (MCP server framework)
- nest-asyncio>=1.5.0 (async compatibility)
- Minimal installation (~50MB)

## Code to Modify
**Task**: Create GitHub issue and implement Phase 2 of Smart Incremental Builds

**Files to change**:
1. Create new files in tools/incremental/:
   - global_scout_cache.py (cross-project Scout cache)
   - change_detector.py (file-level change detection)
   - incremental_builder.py (smart Builder preservation)
   - test_impact_analyzer.py (test selection logic)
   - incremental_docs.py (documentation updates)

2. Modify existing files:
   - tools/orchestrator_prompt.txt (integrate Phase 2 features)
   - .env.example (add Phase 2 configuration)
   - ROADMAP.md (update with Phase 2 status)
   - README.md (mention Phase 2 capabilities)

3. Create tests for all Phase 2 components

4. Update documentation:
   - docs/INCREMENTAL_BUILDS_PHASE1.md → INCREMENTAL_BUILDS.md (merge Phase 1+2)
   - Add performance benchmarks

**Approach**: 
- First: Create GitHub issue with full Phase 2 specification
- Then: Implement Phase 2 features following existing patterns (Phase 1 cache implementation)
- Extend existing cache infrastructure with cross-project capabilities
- Add file-level change detection using git diff + SHA256 hashing
- Build dependency graph for incremental Builder
- Map tests to source files for test impact analysis
- Make documentation updates selective and incremental

## Risks
- Breaking existing Phase 1 cache functionality
- Performance overhead from dependency graph analysis
- Cache invalidation complexity for cross-project cache
- Git dependency for change detection (must work without git too)
- Need to preserve backward compatibility with existing builds

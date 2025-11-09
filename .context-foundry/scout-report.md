# Scout Report: Test Coverage Improvement

## Executive Summary

This task addresses a critical gap in the Context Foundry codebase: **test coverage at 25.3%**, with several core modules having **0% coverage**. The most critical issue is the MCP server (`tools/mcp_server.py`) with 947 untested statements, representing the primary integration point for Claude Desktop users.

**Target**: Improve coverage from 25.3% to minimum 60% for critical paths
**Priority**: HIGH - Core functionality reliability
**Estimated Timeline**: 6-8 hours of implementation

## Key Requirements

### Critical Paths Requiring Tests

1. **MCP Server** (tools/mcp_server.py) - 0% → 70%
   - 947 statements currently uncovered
   - Core tools: `autonomous_build`, `delegate_to_agent`, `context_foundry_status`
   - Pattern management functions
   - Async streaming and delegation
   
2. **Prompt Building System** (tools/prompts/) - 0% → 60%
   - `build_orchestrator_prompt.py` (82 statements)
   - `phase_loader.py` (58 statements)
   - `cache_analysis.py` (133 statements)
   
3. **CLI Entry Points** (tools/cli.py) - Low → 50%
   - Command parsing and validation
   - Argument handling
   
4. **Utilities**
   - `banner.py` (11 statements) - 0% → 100%
   - `test_parallel_runner.py` (39 statements) - 0% → 80%

### Lower Priority (Time Permitting)

5. **TUI Components** (tools/tui/) - 0% → 40%
   - Requires Textual testing framework
   - UI interactions are harder to test
   
6. **Livestream** (tools/livestream/) - 0% → 30%
   - 604 statements
   - Lower priority (experimental feature)

## Technology Stack

**Testing Framework**: pytest (already in use)
**Coverage Tool**: pytest-cov
**Mocking**: unittest.mock (standard library)
**Additional Dependencies Needed**:
- pytest-asyncio (for async MCP server tests)
- pytest-mock (enhanced mocking)

**Existing Test Patterns to Follow**:
- Tier markers: `@pytest.mark.tier1` (critical), `tier2`, `tier3`
- Mock FastMCP for MCP server tests (pattern in `test_mcp_server_critical_paths.py`)
- Integration tests for end-to-end flows
- Unit tests for individual functions

## Architecture Recommendations

### Test File Structure

```
tests/
├── test_mcp_server_comprehensive.py      # NEW: 400+ lines, 70% MCP coverage
├── test_prompt_building_system.py        # NEW: 250+ lines
├── test_cli_entry_points.py              # NEW: 150+ lines  
├── test_banner.py                        # NEW: 50 lines
├── test_parallel_runner_unit.py          # NEW: 120 lines
└── prompts/                              # NEW directory
    ├── test_orchestrator_builder.py
    ├── test_phase_loader.py
    └── test_cache_analysis.py
```

### Testing Strategy

**1. MCP Server Tests** (Highest Priority)
- Mock FastMCP decorators (existing pattern works well)
- Test each tool function independently
- Integration tests for delegation workflow
- Test error handling and edge cases
- Coverage target: 70% (665 of 947 statements)

**2. Prompt Building Tests**
- Test modular prompt assembly
- Validate phase file loading
- Test Flowise integration toggle
- Test cache analysis logic
- Coverage target: 60%

**3. CLI Tests**
- Argument parsing validation
- Command execution paths
- Error message clarity
- Coverage target: 50%

**4. Utility Tests**
- Banner display (simple, aim for 100%)
- Parallel runner orchestration
- Coverage target: 80%+

## Critical Challenges

### 1. MCP Server Complexity
**Issue**: 947 statements is substantial
**Mitigation**: 
- Focus on critical paths first (autonomous_build, delegate_to_agent)
- Use existing mock patterns from `test_mcp_server_critical_paths.py`
- Break into multiple test classes by function group

### 2. Async Testing
**Issue**: MCP server uses async/await extensively
**Mitigation**:
- Install pytest-asyncio
- Use `@pytest.mark.asyncio` decorator
- Existing evolution tests show async patterns

### 3. Integration Dependencies
**Issue**: Some functions require external file system state
**Mitigation**:
- Use tempfile for isolated test directories
- Mock file I/O where appropriate
- Clean up in teardown

### 4. Maintaining Test Quality
**Issue**: Easy to write shallow tests that inflate coverage
**Mitigation**:
- Test actual logic paths, not just function calls
- Include edge cases and error conditions
- Validate outputs, not just execution

## Success Criteria

**Minimum Acceptable**:
- Overall coverage: 25.3% → 45%
- MCP server: 0% → 50%
- Prompt building: 0% → 40%
- All new tests pass
- No existing tests broken

**Target Goal**:
- Overall coverage: 25.3% → 60%
- MCP server: 0% → 70%
- Prompt building: 0% → 60%
- CLI: → 50%
- Utilities: → 80%

**Stretch Goal**:
- Overall coverage: 60%+
- MCP server: 80%+
- Include TUI tests (40%+)

## Test Plan Summary

### Phase 1: Core MCP Server (Priority 1)
- Test `autonomous_build()` function
- Test `delegate_to_agent()` function
- Test `context_foundry_status()` function
- Test pattern management functions
- Test streaming and cancellation

### Phase 2: Prompt Building (Priority 2)
- Test `build_orchestrator_prompt()` function
- Test phase file loading
- Test Flowise extension integration
- Test cache analysis

### Phase 3: CLI & Utilities (Priority 3)
- Test CLI argument parsing
- Test banner display
- Test parallel runner

### Phase 4: Coverage Validation
- Run full test suite
- Generate coverage report
- Identify remaining gaps
- Document results

## Timeline Estimate

- **MCP Server Tests**: 3-4 hours (comprehensive)
- **Prompt Building Tests**: 1.5 hours
- **CLI & Utility Tests**: 1 hour
- **Coverage Analysis & Documentation**: 0.5 hours
- **Buffer for debugging**: 1 hour

**Total**: 6-8 hours

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Tests reveal existing bugs | Medium | Medium | Document bugs, fix if critical |
| Async testing complexity | Low | Medium | Use pytest-asyncio patterns |
| Coverage tools inaccurate | Low | Low | Manual validation of critical paths |
| Time overrun | Medium | Low | Prioritize MCP server first |

## References

**Existing Test Patterns**:
- `tests/test_mcp_server_critical_paths.py` - MCP mocking patterns
- `tests/evolution/test_daemon_comprehensive.py` - Async test patterns
- `tests/test_baml_integration.py` - Integration test patterns

**Coverage Data**:
- Current report: `coverage.json` (25.3% overall)
- 106 files tracked
- 11,095 total statements
- 8,288 missing lines

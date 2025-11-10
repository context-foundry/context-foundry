# Codebase Analysis Report

## Project Overview
- Type: Python automation framework
- Languages: Python (primary), Shell scripts
- Architecture: Multi-agent autonomous build system with MCP integration

## Key Files
- Entry point: claude (CLI wrapper)
- Config: requirements.txt, setup.py, pytest.ini
- Tests: tests/ directory (58 test files)
- Coverage data: coverage.json (25.3% overall coverage)

## Dependencies
- Core: Python 3.8+
- BAML integration: baml-py (optional, type-safe LLM outputs)
- MCP: Model Context Protocol server implementation
- Testing: pytest, pytest-asyncio
- Others: anthropic, openai (for BAML), various utilities

## Current Test Coverage Analysis

### Overall Statistics
- Total files: 106
- Overall coverage: 25.3%
- Test files: 58 in tests/ directory

### Critical Gaps Identified

#### High Priority (0% coverage, significant code)
1. **tools/use_baml.py** (70 statements, 0% coverage)
   - CLI wrapper for BAML integration
   - Entry point for orchestrator phase tracking
   - Critical for type-safe LLM outputs
   - Has related tests but use_baml.py CLI itself not tested

2. **tools/prompts/cache_analysis.py** (133 statements, 0% coverage)
   - Prompt cache analysis tooling
   - No existing tests found

3. **tools/prompts/build_orchestrator_prompt.py** (82 statements, 0% coverage)
   - Builds the main orchestrator prompt
   - Critical for system functionality
   - No existing tests found

4. **tools/prompts/phase_loader.py** (58 statements, 0% coverage)
   - Loads phase-specific prompts
   - No existing tests found

#### Medium Priority (partial coverage or less critical)
5. **tools/livestream/** (broadcaster.py, server.py - 0% coverage)
   - Livestream functionality (604 statements total)
   - Feature-specific, not core critical path

6. **tools/tui/** widgets and screens (0% coverage)
   - UI components (less critical for core automation)

### Existing Test Coverage
- BAML integration: Good coverage (test_baml_*.py files)
- MCP server: Multiple test files exist
- Context budget: Well tested
- Cache system: Well tested
- Evolution system: Multiple test files

## Code to Modify
**Task**: Add tests for critical paths with missing coverage

**Files to change/create**:
1. Create `tests/test_use_baml_cli.py` - Test CLI interface
2. Create `tests/prompts/test_cache_analysis.py` - Test cache analysis
3. Create `tests/prompts/test_build_orchestrator_prompt.py` - Test prompt building
4. Create `tests/prompts/test_phase_loader.py` - Test phase loading

**Approach**: 
- Focus on critical paths first (use_baml.py CLI, prompt builders)
- Write unit tests for pure functions
- Write integration tests for CLI commands
- Mock external dependencies (BAML, file I/O where appropriate)
- Aim for >80% coverage on critical files

## Risks
1. **BAML dependency**: Tests need to handle BAML unavailable gracefully
2. **File I/O**: Prompt builders read from filesystem - need temp dirs
3. **CLI testing**: Need to test argparse interface and subprocess calls
4. **Integration**: Some functions may require full integration testing

## Testing Strategy
1. **Unit tests**: Pure functions, argument parsing, validation
2. **Integration tests**: Full CLI commands with mocked BAML
3. **Edge cases**: Missing files, invalid inputs, BAML errors
4. **Coverage goal**: Increase from 25.3% to >40% overall (focus on critical paths)

## Branch Strategy
- Create branch: `self-improvement/task-995b8dba`
- Make targeted additions (tests only)
- Ensure all existing tests still pass
- Create PR for review

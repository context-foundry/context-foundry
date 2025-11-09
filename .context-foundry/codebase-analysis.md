# Codebase Analysis Report

## Project Overview
- **Type**: Python development tooling/framework
- **Languages**: Python (primary), Bash, JavaScript
- **Architecture**: Multi-agent orchestrator system with modular tools

## Key Files and Structure

### Entry Points
- `tools/cli.py` - Command-line interface
- `tools/mcp_server.py` - MCP server (947 statements, 0% coverage!)
- `create_task.py` - Task creation

### Test Infrastructure
- **Test Framework**: pytest
- **Test Files**: 61 test files
- **Coverage Tool**: pytest-cov
- **Current Coverage**: 25.3% overall
  - Total Statements: 11,095
  - Missing Lines: 8,288
  - Files Covered: 106

### Critical Modules with Low Coverage

#### 1. **MCP Server** (`tools/mcp_server.py`)
- **Coverage**: 0% (947 statements uncovered!)
- **Priority**: CRITICAL
- **Issue**: Core server functionality completely untested

#### 2. **Prompt Building** (`tools/prompts/`)
- `build_orchestrator_prompt.py`: 0% (82 statements)
- `cache_analysis.py`: 0% (133 statements)
- `phase_loader.py`: 0% (58 statements)

#### 3. **TUI Components** (`tools/tui/`)
- `app.py`: 0% (31 statements)
- `screens/dashboard.py`: 0% (55 statements)
- `screens/new_project.py`: 0% (88 statements)
- `screens/metrics.py`: 0% (54 statements)

#### 4. **Livestream** (`tools/livestream/`)
- `server.py`: 0% (469 statements)
- `broadcaster.py`: 0% (135 statements)

#### 5. **Utilities**
- `banner.py`: 0% (11 statements)
- `test_parallel_runner.py`: 0% (39 statements)

### Existing Test Coverage

**Well-tested modules** (from test file names):
- ✅ Evolution system (multiple test files)
- ✅ BAML integration (comprehensive tests)
- ✅ Context budget system
- ✅ Cache system (scout_cache, test_cache)
- ✅ Metrics collection
- ✅ Config manager
- ✅ Incremental build system

**Missing or inadequate tests**:
- ❌ MCP server (critical path!)
- ❌ Prompt building system
- ❌ TUI application
- ❌ Livestream functionality
- ❌ CLI entry points
- ❌ Banner display
- ❌ Parallel test runner

## Code to Modify/Create

**Task**: Analyze test coverage and add missing tests for critical paths

**Files to create/modify**:
1. `tests/test_mcp_server_extended.py` - Comprehensive MCP server tests
2. `tests/test_prompt_building.py` - Prompt building system tests
3. `tests/tui/test_app.py` - TUI application tests
4. `tests/tui/test_screens.py` - TUI screen component tests
5. `tests/test_cli.py` - CLI entry point tests
6. `tests/test_parallel_runner.py` - Parallel test runner tests
7. `.context-foundry/coverage-analysis-report.md` - Detailed coverage report

**Approach**:
- Focus on critical paths first (MCP server, prompt building)
- Use existing test patterns from well-tested modules
- Add integration tests for end-to-end flows
- Target minimum 70% coverage for critical modules
- Use pytest markers (tier1, tier2, tier3) to prioritize tests

## Risks

1. **High Complexity**: MCP server has 947 statements - will need substantial test effort
2. **TUI Testing**: UI components may require mocking frameworks (Textual testing)
3. **Integration Dependencies**: Some modules may require external dependencies
4. **Time Investment**: Achieving 70% coverage could require 15-20 test files
5. **Breaking Changes**: Adding tests may reveal existing bugs

## Dependencies

**Test dependencies** (from pytest.ini):
- pytest
- pytest-cov
- Existing markers: unit, integration, tier1, tier2, tier3, slow

**May need to add**:
- pytest-mock (if not present)
- pytest-asyncio (for async MCP server tests)

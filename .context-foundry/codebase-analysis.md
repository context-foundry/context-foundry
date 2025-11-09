# Codebase Analysis Report

## Project Overview
- Type: python
- Languages: Python
- Architecture: MCP server with autonomous build system, testing framework, and evolution modules

## Key Files
- Entry point: tools/mcp_server.py
- Config: pytest.ini, setup.py, requirements*.txt
- Tests: tests/ (70 test files)

## Dependencies
- MCP (Model Context Protocol) server
- FastMCP framework
- BAML (optional type-safe LLM outputs)
- Testing: pytest
- Various tools for autonomous builds

## Code to Modify
**Task**: Analyze test coverage and add missing tests for critical paths

**Approach**: 
1. Map all Python modules in tools/
2. Identify modules without test coverage
3. Analyze critical paths that need testing
4. Create comprehensive test suite for gaps

## Analysis Results

### Total Counts
- Python modules in tools/: 104
- Test files in tests/: 70
- Coverage ratio: ~67% of modules have tests

### Modules WITH Test Coverage (Verified)
✅ back_pressure (system-level tests)
✅ baml_integration (4 test files: integration, real_integration, schemas, temperature)
✅ banner
✅ cache (3 test files: cache_integration, cache_system, scout_cache_unit, test_cache_unit)
✅ check_context_budget (CLI tests)
✅ config_manager
✅ context_budget (4 test files: general, monitor, reporter, token_counter)
✅ evolution (22 test files covering agent_protocol, daemon, modes, task_queue, etc.)
✅ health_check
✅ incremental (change_detector, integration tests)
✅ metrics (cost_calculator, collector, log_parser, metrics_db, e2e)
✅ mcp_server (3 test files: comprehensive, critical_paths, integration)
✅ schedule_overnight
✅ tool_helpers (path_utils, semantic_tags)
✅ tui (provider tests)
✅ version

### Critical Modules WITHOUT Test Coverage

**HIGH PRIORITY** (Core functionality, used in build pipeline):

1. **tools/back_pressure/integration_pre_check.py**
   - Critical: Validates builds before expensive test execution
   - Risk: Missing validation could allow broken builds through
   - Missing tests: Integration pre-check execution, error handling, validation logic

2. **tools/back_pressure/validate_architecture.py**
   - Critical: Architecture validation before building
   - Risk: Bad architecture designs proceed to builder
   - Missing tests: Validation rules, architecture parsing, error reporting

3. **tools/back_pressure/validate_tech_stack.py**
   - Critical: Technology stack feasibility checking
   - Risk: Unfeasible tech stacks selected by Scout
   - Missing tests: Tech availability checks, validation logic

4. **tools/cli.py**
   - Critical: Command-line interface entry point
   - Risk: CLI commands fail silently
   - Missing tests: Command parsing, argument validation, error handling

5. **tools/use_baml.py**
   - Critical: BAML integration for type-safe outputs
   - Risk: Type validation failures
   - Missing tests: BAML function calls, error handling, fallback logic

6. **tools/test_parallel_runner.py**
   - Critical: Parallel test execution (Phase 4.5)
   - Risk: Parallel execution failures
   - Missing tests: Parallel task spawning, result aggregation, error handling

**MEDIUM PRIORITY** (Important but not critical path):

7. **tools/evolution/backlog_generator.py**
   - Impact: Self-improvement task generation
   - Missing tests: Task extraction, prioritization, TODO parsing

8. **tools/evolution/command_server.py**
   - Impact: Command processing for evolution system
   - Missing tests: Command parsing, execution, error handling

9. **tools/evolution/communication/** modules
   - local_exchange.py
   - rest_api.py
   - web_dashboard.py
   - web_dashboard_server.py
   - websocket_stream.py
   - Impact: Communication between agents
   - Missing tests: REST API endpoints, WebSocket connections, dashboard rendering

10. **tools/evolution/process_watchdog.py**
    - Impact: Process monitoring and safety
    - Missing tests: Watchdog behavior, process killing, timeout handling

11. **tools/evolution/resource_manager.py**
    - Impact: Resource allocation for parallel builds
    - Missing tests: Resource limits, allocation, cleanup

12. **tools/evolution/sandboxes.py**
    - Impact: Isolated execution environments
    - Missing tests: Sandbox creation, isolation, cleanup

13. **tools/evolution/mcp_support.py**
    - Impact: MCP integration helpers
    - Missing tests: MCP tool wrapping, error handling

14. **tools/evolution/mcp_wrapper.py**
    - Impact: MCP client wrapper
    - Missing tests: Wrapper functionality, error handling

**LOW PRIORITY** (Nice to have):

15. **tools/incremental/** modules
    - incremental_builder.py
    - incremental_docs.py
    - test_impact_analyzer.py
    - global_scout_cache.py (partial coverage)
    - Impact: Incremental build optimizations
    - Missing tests: Builder logic, doc regeneration, test impact analysis

16. **tools/livestream/** modules
    - broadcaster.py
    - config.py
    - mcp_client.py
    - server.py
    - Impact: Live build monitoring
    - Missing tests: Broadcast logic, WebSocket handling, server endpoints

17. **tools/prompts/** modules
    - build_orchestrator_prompt.py
    - cache_analysis.py
    - phase_loader.py
    - Impact: Prompt generation and caching
    - Missing tests: Prompt building logic, cache logic, phase loading

18. **tools/tui/** modules (many without tests)
    - app.py
    - screens/* (build_detail, dashboard, help, metrics, new_project)
    - widgets/* (build_table, log_viewer, phase_pipeline, phase_progress, token_gauge)
    - Impact: Terminal UI
    - Missing tests: UI rendering, event handling, state management

19. **tools/tool_helpers/** modules
    - config.py
    - limits.py
    - response_formatter.py
    - truncation.py
    - Impact: Tool helper utilities
    - Missing tests: Configuration loading, limit enforcement, formatting, truncation

## Risks
- **Critical path gaps**: Back pressure validation, CLI, BAML integration, parallel runner
- **Integration gaps**: Communication modules, MCP wrappers
- **UI gaps**: TUI modules mostly untested
- **Incremental system gaps**: Builder, docs, test impact analyzer

## Test Coverage Improvement Plan

### Phase 1: Critical Path Tests (MUST HAVE)
1. tools/back_pressure/integration_pre_check.py
2. tools/back_pressure/validate_architecture.py
3. tools/back_pressure/validate_tech_stack.py
4. tools/cli.py
5. tools/use_baml.py
6. tools/test_parallel_runner.py

### Phase 2: Important Integration Tests (SHOULD HAVE)
7. tools/evolution/backlog_generator.py
8. tools/evolution/command_server.py
9. tools/evolution/process_watchdog.py
10. tools/evolution/resource_manager.py
11. tools/evolution/sandboxes.py
12. tools/evolution/communication/* modules

### Phase 3: Nice-to-Have Tests (COULD HAVE)
13. tools/incremental/* modules
14. tools/livestream/* modules
15. tools/prompts/* modules
16. tools/tui/* modules
17. tools/tool_helpers/* modules

## Success Criteria
- All critical path modules have test coverage (Phase 1)
- Test coverage ratio increases from 67% to 85%+
- All tests pass with existing test suite

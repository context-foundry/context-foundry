# Codebase Analysis Report

## Project Overview
- **Type**: Python CLI/MCP Server Framework
- **Languages**: Python 3.10+
- **Architecture**: FastMCP-based server with delegation capabilities

## Key Files
- **Target file**: `tools/mcp_server.py` (3,752 lines)
- **Entry point**: MCP server with FastMCP framework
- **Config**: pytest.ini, requirements-mcp.txt
- **Tests**: tests/ directory (60 test files)

## Dependencies
- fastmcp (MCP server framework)
- pytest (testing framework)
- unittest.mock (mocking)
- psutil (process utilities)

## Target File: tools/mcp_server.py

### File Structure
The file contains approximately 35+ functions including:

**Helper Functions (Private):**
- `_read_phase_info()` - Read phase tracking info
- `_get_context_foundry_parent_dir()` - Get parent directory
- `_truncate_output()` - Truncate large outputs
- `_write_delegation_metadata()` - Write delegation metadata
- `_write_full_output_to_file()` - Write output to file
- `_create_output_summary()` - Create output summary
- `_detect_existing_codebase()` - Detect codebase
- `_detect_task_intent()` - Detect task intent
- `_autonomous_build_and_deploy_impl()` - Implementation of build/deploy
- `_read_global_patterns_impl()` - Read global patterns
- `_save_global_patterns_impl()` - Save global patterns
- `_merge_project_patterns_impl()` - Merge patterns

**Public MCP Tools (Decorated with @mcp.tool()):**
- `context_foundry_status()` - Get status
- `delegate_to_claude_code()` - Synchronous delegation
- `delegate_to_claude_code_async()` - Async delegation
- `get_delegation_result()` - Get delegation result
- `list_delegations()` - List active delegations
- `cancel_delegation()` - Cancel delegation
- `stream_delegation_output()` - Stream output
- `autonomous_build_and_deploy()` - Build and deploy
- `read_global_patterns()` - Read patterns (public wrapper)
- `save_global_patterns()` - Save patterns (public wrapper)
- `merge_project_patterns()` - Merge patterns (public wrapper)
- `migrate_all_project_patterns()` - Migrate patterns
- `share_patterns_to_community()` - Share patterns
- `get_latest_logs()` - Get logs
- `create_evolution_task()` - Create evolution task
- `get_evolution_tasks()` - Get evolution tasks
- `start_evolution_daemon()` - Start daemon
- `stop_evolution_daemon()` - Stop daemon
- `get_daemon_status()` - Get daemon status
- `register_project()` - Register project
- `apply_pattern_to_project()` - Apply pattern
- `validate_project_health()` - Validate health
- `register_agent()` - Register agent
- `send_agent_message()` - Send message
- `bootstrap_patterns_on_startup()` - Bootstrap patterns

## Existing Test Coverage

### Current Tests for mcp_server.py:
- `test_mcp_server_helpers.py` - Tests helper functions
- `test_mcp_server_comprehensive.py` - Comprehensive tests
- `test_mcp_server_critical_paths.py` - Critical path tests
- `test_mcp_server_integration.py` - Integration tests
- `test_mcp_autonomous_build_coverage.py` - Autonomous build tests
- `test_mcp_pattern_management_coverage.py` - Pattern management tests

### Testing Patterns Used:
- **Pytest framework** with markers (unit, integration, tier1, tier2, tier3)
- **MockFastMCP** class to mock FastMCP imports
- **sys.modules mocking** for fastmcp dependencies
- **Fixtures** for temp directories and mock data
- **unittest.mock** for patching and MagicMock

## Task: Add Tests for tools/mcp_server.py

### Approach:
1. Run coverage analysis to identify gaps
2. Create targeted tests for uncovered functions
3. Follow existing test patterns and conventions
4. Use appropriate pytest markers (unit, tier1/tier2)
5. Mock FastMCP and dependencies properly

## Risks

- **Complex mocking required**: FastMCP framework must be mocked before import
- **Large file**: 3,752 lines with many interdependent functions
- **External dependencies**: psutil, subprocess, file I/O operations
- **Async code**: Some functions use async patterns

## Testing Strategy

1. Run coverage analysis to find gaps
2. Add tests for uncovered functions
3. Verify all tests pass

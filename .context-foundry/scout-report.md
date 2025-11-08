# Scout Report: Test Coverage Analysis & Implementation

## Executive Summary

This task implements the TODO at line 281 of `tools/evolution/modes/self_improvement.py`: "Analyze test coverage and add missing tests for critical paths".

**Current Coverage**: 78% overall (coverage.json shows 798/1017 lines covered)

**Critical Finding**: While many modules have excellent coverage (>90%), the **web dashboard and REST API modules** have 0% coverage, representing a significant gap in testing critical user-facing functionality.

## Key Requirements

1. Analyze coverage.json to identify gaps
2. Prioritize critical paths for testing
3. Write comprehensive tests for uncovered modules
4. Ensure all tests pass
5. Create PR for review

## Technology Stack

- **Testing Framework**: pytest (already in use)
- **Coverage Tool**: pytest-cov (installed)
- **Mocking**: unittest.mock, pytest-mock
- **Language**: Python 3.9+

## Critical Gaps Identified

### ✅ Well-Covered (No action needed)
- tools/evolution core modules (87-100% coverage)
- tools/back_pressure system (37 tests, all passing)
- tools/mcp_server critical paths (14 tests, all passing)

### ❌ Critical Gaps (Action Required)

#### 1. **Web Dashboard Server** (PRIORITY 1 - 0% coverage)
   - File: `tools/evolution/communication/web_dashboard_server.py`
   - Lines: 657 total, 0 covered
   - **Impact**: User-facing Flask web app for monitoring evolution daemon
   - **Critical Paths**:
     - GitHub PR integration (`get_open_prs`, `check_pr_merged`)
     - Database queries (`get_daemon_status`, `get_task_stats`)
     - Flask routes (`/api/status`, `/api/pr_check`)
     - Error handling for API calls

#### 2. **REST API Endpoints** (PRIORITY 2 - 56% coverage)
   - File: `tools/evolution/communication/rest_api.py`
   - Missing: All FastAPI endpoint handlers
   - **Critical Paths**:
     - POST /tasks (create_task)
     - GET /tasks (list_tasks)
     - GET /tasks/{id} (get_task)
     - GET /health (health_check)

#### 3. **WebSocket Streaming** (PRIORITY 3 - 0% coverage)
   - File: `tools/evolution/communication/websocket_stream.py`
   - Lines: 2 total, 0 covered
   - **Impact**: Real-time task output streaming
   - **Critical Path**: WebSocket handler function

## Testing Approach

### Test Structure
```
tests/evolution/
├── test_web_dashboard_server.py (NEW)
├── test_rest_api_endpoints.py (NEW)
├── test_websocket_streaming.py (NEW)
```

### Test Strategy

**1. Web Dashboard Tests** (~150 lines of tests):
   - Mock GitHub API responses
   - Mock database connections
   - Test Flask routes with test client
   - Test error handling (API failures, DB errors)
   - Test PR detection logic
   - Test status aggregation

**2. REST API Tests** (~100 lines of tests):
   - Mock FastAPI dependencies
   - Test each endpoint with valid/invalid inputs
   - Test authentication/validation
   - Test error responses

**3. WebSocket Tests** (~50 lines of tests):
   - Mock WebSocket connections
   - Test message streaming
   - Test connection errors

### Coverage Target
- Aim for >80% coverage on new tests
- Focus on critical paths (error handling, API integration, data validation)

## Challenges & Mitigations

**Challenge 1**: Web dashboard requires Flask test client
- **Mitigation**: Use Flask's built-in test_client() fixture

**Challenge 2**: GitHub API calls need mocking
- **Mitigation**: Use `unittest.mock.patch` for requests library

**Challenge 3**: Database queries need isolation
- **Mitigation**: Use temporary SQLite databases in tests

**Challenge 4**: WebSocket testing complexity
- **Mitigation**: Use pytest-asyncio for async testing

## Timeline Estimate

- Web dashboard tests: ~30 minutes
- REST API tests: ~20 minutes
- WebSocket tests: ~15 minutes
- Test fixes/debugging: ~15 minutes
- **Total**: ~80 minutes

## Success Criteria

✅ Web dashboard server has >80% test coverage
✅ REST API endpoints have >80% test coverage
✅ WebSocket handler has >80% test coverage
✅ All new tests pass
✅ All existing tests still pass
✅ PR created on branch `self-improvement/task-e11816f5`

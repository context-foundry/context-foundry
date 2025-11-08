# Test Architecture: Evolution Communication Module Coverage

## System Overview

We're adding comprehensive tests for the Evolution System's communication layer, which currently has 0-56% test coverage. These modules provide critical functionality for daemon monitoring, REST API access, and real-time WebSocket updates.

## File Structure

```
tests/evolution/
├── __init__.py (exists)
├── test_web_dashboard_server.py (NEW - ~200 lines)
├── test_rest_api_endpoints.py (NEW - ~150 lines)
└── test_websocket_streaming.py (NEW - ~100 lines)
```

## Module 1: test_web_dashboard_server.py

**Target**: `tools/evolution/communication/web_dashboard_server.py` (657 lines, 0% covered)

### Architecture
```python
# Test Class Structure:
class TestGitHubIntegration:
    """Tests for GitHub API functions"""
    - test_get_github_owner_from_https_url()
    - test_get_github_owner_from_ssh_url()
    - test_get_github_owner_no_git_remote()
    - test_get_open_prs_success()
    - test_get_open_prs_api_failure()
    - test_get_open_prs_no_token()
    - test_check_pr_merged_true()
    - test_check_pr_merged_false()

class TestDatabaseQueries:
    """Tests for SQLite database queries"""
    - test_get_daemon_status_running()
    - test_get_daemon_status_no_db()
    - test_get_task_stats()
    - test_get_recent_tasks()

class TestFlaskRoutes:
    """Tests for Flask endpoints"""
    - test_dashboard_route_renders()
    - test_api_status_route()
    - test_api_pr_check_route()
```

### Dependencies & Mocking
- **Mock**: `subprocess.run` (for git commands)
- **Mock**: `requests.get` (for GitHub API)
- **Mock**: `sqlite3.connect` (for database)
- **Fixture**: Flask test_client for route testing
- **Fixture**: Temporary directories for database files

### Critical Paths
1. GitHub API error handling (rate limits, network failures)
2. Database connection failures
3. PR detection logic for self-improvement branches
4. JSON response formatting

## Module 2: test_rest_api_endpoints.py

**Target**: `tools/evolution/communication/rest_api.py` (missing endpoint coverage)

### Architecture
```python
# Test Class Structure:
class TestCreateTask:
    """Tests for POST /tasks"""
    - test_create_task_valid_payload()
    - test_create_task_missing_fields()
    - test_create_task_invalid_type()
    - test_create_task_database_error()

class TestListTasks:
    """Tests for GET /tasks"""
    - test_list_tasks_empty()
    - test_list_tasks_with_filters()
    - test_list_tasks_pagination()

class TestGetTask:
    """Tests for GET /tasks/{id}"""
    - test_get_task_exists()
    - test_get_task_not_found()

class TestHealthCheck:
    """Tests for GET /health"""
    - test_health_check_healthy()
    - test_health_check_degraded()
```

### Dependencies & Mocking
- **Framework**: FastAPI TestClient
- **Mock**: TaskQueueManager database operations
- **Fixture**: Test FastAPI app instance

### Critical Paths
1. Request validation
2. Database transaction handling
3. Error response formatting
4. Authentication/authorization (if implemented)

## Module 3: test_websocket_streaming.py

**Target**: `tools/evolution/communication/websocket_stream.py` (2 lines, 0% covered)

### Architecture
```python
# Test Class Structure:
class TestWebSocketStreaming:
    """Tests for WebSocket handler"""
    - test_stream_handler_accepts_connection()
    - test_stream_handler_sends_messages()
    - test_stream_handler_handles_disconnection()
    - test_stream_handler_error_recovery()
```

### Dependencies & Mocking
- **Framework**: pytest-asyncio
- **Mock**: WebSocket connection object
- **Mock**: Message queue/stream source

### Critical Paths
1. Connection establishment
2. Message serialization
3. Connection cleanup on error
4. Async error handling

## Testing Strategy

### Setup & Fixtures

**conftest.py additions** (if needed):
```python
@pytest.fixture
def temp_db():
    """Temporary SQLite database for testing"""
    db_path = tempfile.mktemp(suffix='.db')
    yield db_path
    if Path(db_path).exists():
        Path(db_path).unlink()

@pytest.fixture
def flask_test_client():
    """Flask test client with app context"""
    from tools.evolution.communication.web_dashboard_server import app
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses"""
    with patch('requests.get') as mock:
        yield mock
```

### Mocking Strategy

**Level 1 - External Dependencies:**
- GitHub API calls → Mock with sample PR data
- Git commands → Mock subprocess with fake remotes
- Database connections → Use temporary SQLite files or mock entirely

**Level 2 - Internal Dependencies:**
- TaskQueueManager → Mock database queries
- Evolution daemon → Mock PID files and status

**Level 3 - Network:**
- HTTP requests → Use requests_mock library
- WebSocket connections → Mock socket objects

### Coverage Measurement

Run tests with coverage:
```bash
pytest tests/evolution/test_web_dashboard_server.py -v --cov=tools/evolution/communication/web_dashboard_server --cov-report=term-missing
pytest tests/evolution/test_rest_api_endpoints.py -v --cov=tools/evolution/communication/rest_api --cov-report=term-missing
pytest tests/evolution/test_websocket_streaming.py -v --cov=tools/evolution/communication/websocket_stream --cov-report=term-missing
```

Target: >80% line coverage for each module

## Implementation Steps

### Step 1: Create test files
1. Create `tests/evolution/test_web_dashboard_server.py`
2. Create `tests/evolution/test_rest_api_endpoints.py`
3. Create `tests/evolution/test_websocket_streaming.py`

### Step 2: Write tests (priority order)
1. **Priority 1**: Web dashboard (most complex, 657 lines)
2. **Priority 2**: REST API (critical infrastructure)
3. **Priority 3**: WebSocket (smallest, 2 lines)

### Step 3: Validate
- Run each test file independently
- Measure coverage for each target module
- Fix any failing tests
- Ensure all existing tests still pass

### Step 4: Integration
- Run full test suite
- Verify no regressions
- Check total coverage improvement

## Success Criteria

✅ Web dashboard server: >80% coverage (currently 0%)
✅ REST API endpoints: >80% coverage (currently 56%)
✅ WebSocket handler: >80% coverage (currently 0%)
✅ All 3 new test files pass
✅ All existing tests still pass
✅ No code changes to source files (only tests)
✅ PR ready for review

## Risk Mitigation

**Risk 1**: Flask app may require complex setup
- **Mitigation**: Use app.test_client() which handles context automatically

**Risk 2**: GitHub API mocking may be incomplete
- **Mitigation**: Start with simple mock, add edge cases incrementally

**Risk 3**: WebSocket testing may require async complexity
- **Mitigation**: Keep tests focused on handler logic, mock connection layer

**Risk 4**: Database tests may have isolation issues
- **Mitigation**: Use unique temporary databases per test, cleanup in fixtures

## Timeline

- Web dashboard tests: 30-40 minutes
- REST API tests: 20-30 minutes
- WebSocket tests: 15-20 minutes
- Debug/fixes: 15-20 minutes
- **Total**: ~90 minutes

## Documentation

Each test file will include:
- Module docstring explaining purpose
- Test class docstrings explaining what's being tested
- Individual test docstrings with expected behavior
- Comments explaining complex mocking scenarios

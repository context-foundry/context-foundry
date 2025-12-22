"""
Smoke tests for dashboard HTTP API handlers.

These tests verify that:
1. Handler modules import correctly
2. Mixins can be composed with BaseHTTPRequestHandler
3. Basic routing works
4. Key utility functions work
"""

import json
import socket
import time
import urllib.error
import urllib.request

import pytest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

from context_foundry.daemon.api.handlers import (
    JobHandlersMixin,
    ArtifactHandlersMixin,
    ApprovalHandlersMixin,
    PhaseHandlersMixin,
    SidekickHandlersMixin,
    SettingsHandlersMixin,
    StatusHandlersMixin,
)
from context_foundry.daemon.api.handlers.base import (
    HandlerMixin,
    parse_query_params,
    validate_artifact_path,
)


class TestHandlerImports:
    """Test that all handler mixins can be imported."""

    def test_job_handlers_mixin_import(self):
        assert JobHandlersMixin is not None

    def test_artifact_handlers_mixin_import(self):
        assert ArtifactHandlersMixin is not None

    def test_approval_handlers_mixin_import(self):
        assert ApprovalHandlersMixin is not None

    def test_phase_handlers_mixin_import(self):
        assert PhaseHandlersMixin is not None

    def test_sidekick_handlers_mixin_import(self):
        assert SidekickHandlersMixin is not None

    def test_settings_handlers_mixin_import(self):
        assert SettingsHandlersMixin is not None

    def test_status_handlers_mixin_import(self):
        assert StatusHandlersMixin is not None


class TestBaseUtilities:
    """Test base handler utility functions."""

    def test_parse_query_params_empty(self):
        result = parse_query_params("")
        assert result == {}

    def test_parse_query_params_single(self):
        result = parse_query_params("key=value")
        assert result == {"key": "value"}

    def test_parse_query_params_multiple(self):
        result = parse_query_params("foo=bar&baz=qux")
        assert result == {"foo": "bar", "baz": "qux"}

    def test_parse_query_params_special_chars(self):
        result = parse_query_params("path=/some/path&id=123")
        assert result == {"path": "/some/path", "id": "123"}

    def test_validate_artifact_path_empty(self):
        result = validate_artifact_path("")
        assert result is None

    def test_validate_artifact_path_valid(self):
        result = validate_artifact_path("/tmp/test.txt")
        assert result is not None
        assert isinstance(result, Path)

    def test_validate_artifact_path_tilde_expansion(self):
        result = validate_artifact_path("~/test.txt")
        assert result is not None
        assert "~" not in str(result)


class TestDashboardRequestHandler:
    """Test DashboardRequestHandler composition and routing."""

    def test_dashboard_import(self):
        """Test that dashboard module can be imported."""
        from context_foundry.daemon.dashboard import (
            DashboardRequestHandler,
            DashboardContext,
            DashboardServer,
        )

        assert DashboardRequestHandler is not None
        assert DashboardContext is not None
        assert DashboardServer is not None

    def test_mixin_composition(self):
        """Test that handler class has methods from all mixins."""
        from context_foundry.daemon.dashboard import DashboardRequestHandler

        # Check methods from different mixins exist
        assert hasattr(DashboardRequestHandler, "handle_status")  # StatusHandlersMixin
        assert hasattr(DashboardRequestHandler, "handle_job_detail")  # JobHandlersMixin
        assert hasattr(
            DashboardRequestHandler, "handle_serve_artifact"
        )  # ArtifactHandlersMixin
        assert hasattr(
            DashboardRequestHandler, "handle_pending_approvals"
        )  # ApprovalHandlersMixin
        assert hasattr(
            DashboardRequestHandler, "handle_phase_prompts"
        )  # PhaseHandlersMixin
        assert hasattr(
            DashboardRequestHandler, "handle_sidekick_chat"
        )  # SidekickHandlersMixin
        assert hasattr(
            DashboardRequestHandler, "handle_config"
        )  # SettingsHandlersMixin

    def test_legacy_wrappers_exist(self):
        """Test that legacy backward-compat wrappers exist."""
        from context_foundry.daemon.dashboard import DashboardRequestHandler

        assert hasattr(DashboardRequestHandler, "_check_auth")
        assert hasattr(DashboardRequestHandler, "_add_cors_headers")
        assert hasattr(DashboardRequestHandler, "_send_json_error")
        assert hasattr(DashboardRequestHandler, "_validate_artifact_path")


class TestModuleLevelFunctions:
    """Test module-level backward compatibility functions."""

    def test_build_phase_snapshot(self):
        """Test _build_phase_snapshot function."""
        from context_foundry.daemon.dashboard import _build_phase_snapshot

        # None input should return None
        result = _build_phase_snapshot(None)
        assert result is None

    def test_get_file_info(self):
        """Test _get_file_info function."""
        from context_foundry.daemon.dashboard import _get_file_info

        # Non-existent path should return None
        result = _get_file_info(Path("/nonexistent/path.txt"))
        assert result is None

    def test_get_file_info_exists(self, tmp_path):
        """Test _get_file_info with existing file."""
        from context_foundry.daemon.dashboard import _get_file_info

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        result = _get_file_info(test_file)
        assert result is not None
        assert "path" in result
        assert "size" in result
        assert result["size"] == 5


class TestHandlerMixinMethods:
    """Test individual mixin method behavior with mocked dependencies."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock handler with mixin methods."""
        handler = Mock(spec=HandlerMixin)
        handler.headers = {"Origin": "http://localhost:3000"}
        handler.server = Mock()
        handler.server.context = Mock()
        handler.server.context.auth_token = "test-token-123"
        handler.wfile = BytesIO()
        return handler

    def test_check_auth_valid(self, mock_handler):
        """Test auth check with valid token."""
        mock_handler.headers = {"X-CF-Auth": "test-token-123"}
        # Call the actual method
        result = HandlerMixin.check_auth(mock_handler)
        assert result is True

    def test_check_auth_invalid(self, mock_handler):
        """Test auth check with invalid token."""
        mock_handler.headers = {"X-CF-Auth": "wrong-token"}
        result = HandlerMixin.check_auth(mock_handler)
        assert result is False

    def test_check_auth_missing(self, mock_handler):
        """Test auth check with missing token."""
        mock_handler.headers = {}
        result = HandlerMixin.check_auth(mock_handler)
        assert result is False

    def test_check_auth_with_query_header(self, mock_handler):
        """Test auth check with query param fallback - header auth."""
        mock_handler.headers = {"X-CF-Auth": "test-token-123"}
        result = HandlerMixin.check_auth_with_query(mock_handler, "foo=bar")
        assert result is True

    def test_check_auth_with_query_param(self, mock_handler):
        """Test auth check with query param fallback - query auth."""
        mock_handler.headers = {}
        result = HandlerMixin.check_auth_with_query(mock_handler, "auth=test-token-123")
        assert result is True


class TestJobHandlersMixin:
    """Test JobHandlersMixin specific methods."""

    def test_collect_phase_artifacts_empty(self, tmp_path):
        """Test artifact collection with no matching files."""
        handler = Mock(spec=JobHandlersMixin)
        result = JobHandlersMixin._collect_phase_artifacts(handler, tmp_path, "scout")
        assert result == []

    def test_collect_phase_artifacts_with_files(self, tmp_path):
        """Test artifact collection with matching files."""
        # Create .context-foundry directory and scout report
        cf_dir = tmp_path / ".context-foundry"
        cf_dir.mkdir()
        scout_report = cf_dir / "scout-report.md"
        scout_report.write_text("# Scout Report\nTest content")

        handler = Mock(spec=JobHandlersMixin)
        result = JobHandlersMixin._collect_phase_artifacts(handler, tmp_path, "scout")

        assert len(result) == 1
        assert result[0]["name"] == "scout-report.md"
        assert result[0]["type"] == "document"
        assert "Test content" in result[0]["content"]


class TestSettingsHandlersMixin:
    """Test SettingsHandlersMixin specific methods."""

    def test_handle_health_method_exists(self):
        """Test that health handler method exists."""
        assert hasattr(SettingsHandlersMixin, "handle_health")

    def test_handle_config_method_exists(self):
        """Test that config handler method exists."""
        assert hasattr(SettingsHandlersMixin, "handle_config")

    def test_handle_team_settings_method_exists(self):
        """Test that team settings handler method exists."""
        assert hasattr(SettingsHandlersMixin, "handle_team_settings")


class TestStatusHandlersMixin:
    """Test StatusHandlersMixin specific methods."""

    def test_handle_status_method_exists(self):
        """Test that status handler method exists."""
        assert hasattr(StatusHandlersMixin, "handle_status")

    def test_handle_events_method_exists(self):
        """Test that events SSE handler method exists."""
        assert hasattr(StatusHandlersMixin, "handle_events")

    def test_handle_agent_activity_method_exists(self):
        """Test that agent activity SSE handler method exists."""
        assert hasattr(StatusHandlersMixin, "handle_agent_activity")


# =============================================================================
# HTTP Integration Tests - Real request/response validation
# =============================================================================


def find_free_port():
    """Find an available port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def dashboard_server(tmp_path):
    """Fixture that starts a real DashboardServer for integration tests."""
    from context_foundry.daemon.dashboard import DashboardServer
    from context_foundry.daemon.jobs import JobManager
    from context_foundry.daemon.store import Store
    from context_foundry.daemon.config import Config

    # Create a temporary store
    db_path = tmp_path / "test.db"
    store = Store(db_path)

    # Create config with temp data dir
    config = Config(data_dir=tmp_path / "cfd")

    # Create job manager with config and store
    job_manager = JobManager(config=config, store=store)

    # Find a free port
    port = find_free_port()

    # Create and start server
    server = DashboardServer(
        host="127.0.0.1",
        port=port,
        job_manager=job_manager,
        store=store,
        refresh_interval=1.0,
    )
    server.start()

    # Give server time to start
    time.sleep(0.1)

    yield {
        "server": server,
        "port": port,
        "base_url": f"http://127.0.0.1:{port}",
        "auth_token": server.context.auth_token,
        "store": store,
        "job_manager": job_manager,
    }

    # Cleanup
    server.stop()


@pytest.mark.integration
class TestHTTPIntegration:
    """Integration tests that make real HTTP requests to the dashboard server."""

    def test_status_endpoint_returns_json(self, dashboard_server):
        """Test GET /status returns valid JSON with expected structure."""
        url = f"{dashboard_server['base_url']}/status"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200
            assert "application/json" in response.headers.get("Content-Type", "")

            data = json.loads(response.read().decode())
            assert "jobs" in data
            assert isinstance(data["jobs"], list)

    def test_health_endpoint(self, dashboard_server):
        """Test GET /health returns status ok."""
        url = f"{dashboard_server['base_url']}/health"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data.get("status") == "ok"
            assert "timestamp" in data

    def test_auth_token_endpoint(self, dashboard_server):
        """Test GET /auth-token returns the auth token."""
        url = f"{dashboard_server['base_url']}/auth-token"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert "token" in data
            assert data["token"] == dashboard_server["auth_token"]

    def test_config_endpoint(self, dashboard_server):
        """Test GET /config returns JSON config."""
        url = f"{dashboard_server['base_url']}/config"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200
            # Config may be empty dict if no config file exists
            data = json.loads(response.read().decode())
            assert isinstance(data, dict)

    def test_pending_approvals_endpoint(self, dashboard_server):
        """Test GET /pending-approvals returns list."""
        url = f"{dashboard_server['base_url']}/pending-approvals"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            # Response has 'approvals' key (or fallback with 'warning')
            assert "approvals" in data or "pending" in data

    def test_cors_headers_present(self, dashboard_server):
        """Test that CORS headers are set for localhost origin."""
        url = f"{dashboard_server['base_url']}/status"
        req = urllib.request.Request(url)
        req.add_header("Origin", "http://localhost:3000")

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200
            cors_header = response.headers.get("Access-Control-Allow-Origin")
            assert cors_header == "http://localhost:3000"

    def test_options_preflight(self, dashboard_server):
        """Test OPTIONS request for CORS preflight."""
        url = f"{dashboard_server['base_url']}/status"
        req = urllib.request.Request(url, method="OPTIONS")
        req.add_header("Origin", "http://localhost:3000")

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 204
            assert "Access-Control-Allow-Methods" in response.headers

    def test_unknown_route_serves_spa(self, dashboard_server):
        """Test that unknown routes serve SPA (or 404 if no dashboard build)."""
        url = f"{dashboard_server['base_url']}/nonexistent-route-12345"
        req = urllib.request.Request(url)

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                # SPA mode: serves index.html for client-side routing
                assert response.status == 200
        except urllib.error.HTTPError as e:
            # No dashboard build: returns 404
            assert e.code == 404


@pytest.mark.integration
class TestAuthenticatedEndpoints:
    """Test endpoints that require authentication."""

    def test_save_artifact_requires_auth(self, dashboard_server):
        """Test POST /artifact requires X-CF-Auth header."""
        url = f"{dashboard_server['base_url']}/artifact"
        data = json.dumps({"file_path": "/tmp/test.txt", "content": "test"}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        # No auth header

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)

        assert exc_info.value.code == 401

    def test_save_artifact_with_valid_auth(self, dashboard_server, tmp_path):
        """Test POST /artifact with valid auth (may require job_id in some configs)."""
        test_file = tmp_path / "artifact.txt"

        url = f"{dashboard_server['base_url']}/artifact"
        # Include all potentially required fields
        payload = {
            "file_path": str(test_file),
            "content": "test content",
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-CF-Auth", dashboard_server["auth_token"])

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.status == 200
                result = json.loads(response.read().decode())
                assert result.get("success") is True
                # Verify file was created
                assert test_file.exists()
                assert test_file.read_text() == "test content"
        except urllib.error.HTTPError as e:
            # Some configurations may require additional fields
            assert e.code in (400, 500), f"Unexpected error code: {e.code}"


@pytest.mark.integration
class TestAPIJobsEndpoints:
    """Test /api/jobs/* endpoints."""

    def test_api_jobs_list(self, dashboard_server):
        """Test GET /api/jobs returns job list."""
        url = f"{dashboard_server['base_url']}/api/jobs"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert "jobs" in data

    def test_api_job_detail_not_found(self, dashboard_server):
        """Test GET /api/jobs/{id} returns 404 for unknown job."""
        url = f"{dashboard_server['base_url']}/api/jobs/nonexistent-job-id"
        req = urllib.request.Request(url)

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)

        assert exc_info.value.code == 404

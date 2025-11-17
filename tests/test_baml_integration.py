#!/usr/bin/env python3
"""
Unit tests for BAML integration in Context Foundry

Tests cover:
- BAML schema compilation
- Phase tracking validation
- Scout report generation
- Architecture blueprint generation
- Builder task result validation
- Fallback to JSON mode
- Client caching
- Error handling
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.baml_integration import (
    get_baml_schemas_dir,
    get_baml_client_dir,
    compile_baml_schemas,
    get_baml_client,
    is_baml_available,
    get_baml_error,
    update_phase_with_baml,
    validate_phase_info,
    generate_scout_report_baml,
    generate_architecture_baml,
    validate_build_result_baml,
    baml_status_summary,
    fallback_to_json,
)


class TestBAMLPaths:
    """Test BAML directory path helpers"""

    def test_get_baml_schemas_dir(self):
        """Test getting BAML schemas directory path"""
        schemas_dir = get_baml_schemas_dir()
        assert schemas_dir.name == "baml_schemas"
        assert "tools" in str(schemas_dir)

    def test_get_baml_client_dir(self):
        """Test getting BAML client directory path"""
        client_dir = get_baml_client_dir()
        assert client_dir.name == "baml_client"
        assert "tools" in str(client_dir)


class TestBAMLSchemas:
    """Test BAML schema compilation"""

    def test_schemas_directory_exists(self):
        """Test that BAML schemas directory was created"""
        schemas_dir = get_baml_schemas_dir()
        assert schemas_dir.exists(), f"Schemas directory not found: {schemas_dir}"

    def test_schema_files_exist(self):
        """Test that all required schema files exist"""
        schemas_dir = get_baml_schemas_dir()

        required_schemas = [
            "phase_tracking.baml",
            "scout.baml",
            "architect.baml",
            "builder.baml",
            "clients.baml",
        ]

        for schema in required_schemas:
            schema_path = schemas_dir / schema
            assert schema_path.exists(), f"Schema file not found: {schema}"

    def test_schema_content_valid(self):
        """Test that schema files contain valid BAML syntax"""
        schemas_dir = get_baml_schemas_dir()

        # Check phase_tracking.baml
        phase_tracking = schemas_dir / "phase_tracking.baml"
        content = phase_tracking.read_text()

        # Basic syntax checks
        assert "class PhaseInfo" in content
        assert "enum PhaseType" in content
        assert "enum PhaseStatus" in content
        assert "function CreatePhaseInfo" in content
        assert "function ValidatePhaseInfo" in content

    def test_compile_baml_schemas(self):
        """Test BAML schema compilation"""
        # BAML is now required, so compilation should succeed
        success, error = compile_baml_schemas()

        # Should succeed since BAML is a required dependency
        assert success, f"BAML schema compilation should succeed: {error}"
        assert error is None


class TestBAMLClient:
    """Test BAML client management"""

    def test_get_baml_client(self):
        """Test getting BAML client"""
        client = get_baml_client()

        # Client may be None if baml-py not installed
        if client is not None:
            # Client should be cached
            client2 = get_baml_client()
            assert client is client2

    def test_is_baml_available(self):
        """Test BAML availability check"""
        available = is_baml_available()
        assert isinstance(available, bool)

        # If not available, error should be set
        if not available:
            error = get_baml_error()
            assert error is not None

    def test_baml_status_summary(self):
        """Test BAML status summary"""
        status = baml_status_summary()

        # Check all expected fields
        assert "baml_available" in status
        assert "baml_client_loaded" in status
        assert "error" in status
        assert "schemas_dir" in status
        assert "client_dir" in status
        assert "schemas_exist" in status
        assert "client_exists" in status

        # Schemas should exist
        assert status["schemas_exist"] is True


class TestPhaseTracking:
    """Test phase tracking with BAML"""

    def test_update_phase_with_baml(self):
        """Test updating phase with BAML (mocked)"""
        # Mock BAML client to avoid real API calls
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock the BAML response
            mock_response = {
                "session_id": "test-session",
                "current_phase": "Scout",
                "phase_number": "1/7",
                "status": "researching",
                "progress_detail": "Analyzing requirements",
                "test_iteration": 0,
                "phases_completed": [],
                "started_at": "2025-01-13T00:00:00Z",
                "last_updated": "2025-01-13T00:00:00Z",
            }

            mock_result = MagicMock()
            # Mock .parsed() to return the dict directly (modern BAML API)
            mock_result.parsed.return_value = mock_response
            # Also mock unstable_internal_repr as fallback
            mock_result.unstable_internal_repr.return_value = json.dumps(
                {"Success": {"content": json.dumps(mock_response)}}
            )
            mock_client.call_function_sync.return_value = mock_result
            mock_client.create_context_manager.return_value = MagicMock()

            phase_info = update_phase_with_baml(
                phase="Scout",
                status="researching",
                detail="Analyzing requirements",
                session_id="test-session",
                iteration=0,
            )

            # Should return a dict with expected fields
            assert isinstance(phase_info, dict)
            assert phase_info["session_id"] == "test-session"
            assert phase_info["current_phase"] == "Scout"
            assert phase_info["status"] == "researching"
            assert phase_info["progress_detail"] == "Analyzing requirements"
            assert phase_info["test_iteration"] == 0
            assert "started_at" in phase_info
            assert "last_updated" in phase_info

    def test_update_phase_with_baml_normalizes_and_injects_timestamps(self):
        """Ensure PhaseInfo payloads are flattened with real timestamps"""
        with patch("tools.baml_integration.get_baml_client") as mock_get_client, patch(
            "tools.baml_integration._now_iso", return_value="2025-01-02T03:04:05Z"
        ):
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            mock_response = {
                "PhaseInfo": {
                    "sessionId": "simple-claude-chat",
                    "currentPhase": "Architect",
                    "status": "designing",
                    "progressDetail": "Starting Architect phase",
                    "testIteration": 0,
                    "timestamps": {
                        "phaseStart": "2023-10-01T10:00:00Z",
                        "lastUpdated": "2023-10-01T10:00:00Z",
                        "phaseEnd": None,
                    },
                    "phaseStartTime": "2023-10-01T10:00:00Z",
                    "lastUpdated": "2023-10-01T10:00:00Z",
                }
            }

            mock_result = MagicMock()
            mock_result.parsed.return_value = mock_response
            mock_result.unstable_internal_repr.return_value = json.dumps(
                {"Success": {"content": json.dumps(mock_response)}}
            )
            mock_client.call_function_sync.return_value = mock_result
            mock_client.create_context_manager.return_value = MagicMock()

            phase_info = update_phase_with_baml(
                phase="Architect",
                status="designing",
                detail="Starting Architect phase",
                session_id="simple-claude-chat",
                iteration=0,
            )

            assert "PhaseInfo" not in phase_info
            assert phase_info["phase"] == "Architect"
            assert phase_info["session_id"] == "simple-claude-chat"
            assert phase_info["phaseStartTime"] == "2025-01-02T03:04:05Z"
            assert phase_info["timestamps"]["phaseStart"] == "2025-01-02T03:04:05Z"
            assert phase_info["timestamps"]["lastUpdated"] == "2025-01-02T03:04:05Z"

    def test_update_phase_with_baml_redirects_stdout(self, capsys):
        """Ensure stdout noise from BAML is redirected to stderr"""
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            mock_response = {
                "session_id": "test-session",
                "current_phase": "Builder",
                "phase_number": "3/7",
                "status": "building",
                "progress_detail": "Planning parallel build tasks",
                "test_iteration": 0,
                "phases_completed": ["Scout", "Architect"],
                "started_at": "2025-01-13T00:00:00Z",
                "last_updated": "2025-01-13T00:00:00Z",
            }

            mock_result = MagicMock()
            mock_result.parsed.return_value = mock_response
            mock_result.unstable_internal_repr.return_value = json.dumps(
                {"Success": {"content": json.dumps(mock_response)}}
            )
            mock_client.create_context_manager.return_value = MagicMock()

            def _mock_call_function_sync(*args, **kwargs):
                print("2025-11-11T21:15:33.558 [BAML WARN] Something noisy")
                return mock_result

            mock_client.call_function_sync.side_effect = _mock_call_function_sync

            phase_info = update_phase_with_baml(
                phase="Builder",
                status="building",
                detail="Planning parallel build tasks",
                session_id="test-session",
                iteration=0,
            )

            captured = capsys.readouterr()
            assert captured.out.strip() == ""
            assert (
                "[BAML LOG] 2025-11-11T21:15:33.558 [BAML WARN] Something noisy"
                in captured.err
            )
            assert phase_info["current_phase"] == "Builder"

    def test_validate_phase_info_valid(self):
        """Test validating valid phase info JSON with BAML"""
        valid_json = json.dumps(
            {
                "session_id": "test",
                "current_phase": "Scout",
                "phase_number": "1/7",
                "status": "researching",
                "progress_detail": "Test",
                "test_iteration": 0,
                "phases_completed": [],
                "started_at": "2025-01-13T00:00:00Z",
                "last_updated": "2025-01-13T00:00:00Z",
            }
        )

        # Mock BAML client to avoid real API calls
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock the BAML response
            mock_result = MagicMock()
            mock_result.unstable_internal_repr.return_value = json.dumps(
                {"Success": {"content": valid_json}}
            )
            mock_client.call_function_sync.return_value = mock_result
            mock_client.create_context_manager.return_value = MagicMock()

            # Now validate_phase_info returns dict directly, not tuple
            phase_info = validate_phase_info(valid_json)

            assert isinstance(phase_info, dict)
            assert phase_info["session_id"] == "test"

    def test_validate_phase_info_invalid_json(self):
        """Test validating invalid JSON - should raise RuntimeError"""
        invalid_json = "{ invalid json }"

        # Mock BAML client
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.create_context_manager.return_value = MagicMock()

            # Mock BAML to fail on invalid JSON
            mock_client.call_function_sync.side_effect = Exception("Invalid JSON")

            # Should raise RuntimeError, not return tuple
            with pytest.raises(RuntimeError, match="BAML validation failed"):
                validate_phase_info(invalid_json)

    def test_validate_phase_info_missing_fields(self):
        """Test validating JSON with missing required fields"""
        incomplete_json = json.dumps(
            {
                "session_id": "test"
                # Missing required fields
            }
        )

        # Mock BAML client
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_client.create_context_manager.return_value = MagicMock()

            # Mock BAML to fail on missing fields
            mock_client.call_function_sync.side_effect = Exception(
                "Missing required fields"
            )

            # Should raise RuntimeError, not return tuple
            with pytest.raises(RuntimeError, match="BAML validation failed"):
                validate_phase_info(incomplete_json)


class TestScoutReport:
    """Test Scout report generation with BAML"""

    def test_generate_scout_report_baml(self):
        """Test generating Scout report with BAML (mocked)"""
        # Mock BAML client to avoid real API calls
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock the BAML response
            mock_result = MagicMock()
            mock_result.unstable_internal_repr.return_value = json.dumps(
                {"Success": {"content": json.dumps({"summary": "Test report"})}}
            )
            mock_client.call_function_sync.return_value = mock_result
            mock_client.create_context_manager.return_value = MagicMock()

            # Now generate_scout_report_baml returns dict, not None
            report = generate_scout_report_baml(
                task_description="Build a web app",
                codebase_analysis="Python project",
                past_patterns="No patterns",
            )

            assert isinstance(report, dict)
            assert "summary" in report

    def test_generate_scout_report_fails_without_baml(self):
        """Test Scout report fails when BAML unavailable"""
        with patch("tools.baml_integration.is_baml_available", return_value=False):
            with patch(
                "tools.baml_integration.get_baml_error",
                return_value="BAML not installed",
            ):
                with pytest.raises(RuntimeError, match="BAML is required"):
                    generate_scout_report_baml(
                        task_description="Build a web app",
                        codebase_analysis="Python project",
                    )


class TestArchitectureBlueprint:
    """Test architecture blueprint generation with BAML"""

    def test_generate_architecture_baml(self):
        """Test generating architecture with BAML (mocked)"""
        scout_json = json.dumps({"summary": "Test scout report"})
        risks = ["Risk 1", "Risk 2"]

        # Mock BAML client to avoid real API calls
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock the BAML response
            mock_result = MagicMock()
            mock_result.unstable_internal_repr.return_value = json.dumps(
                {"Success": {"content": json.dumps({"components": []})}}
            )
            mock_client.call_function_sync.return_value = mock_result
            mock_client.create_context_manager.return_value = MagicMock()

            # Now generate_architecture_baml returns dict, not None
            architecture = generate_architecture_baml(scout_json, risks)

            assert isinstance(architecture, dict)

    def test_generate_architecture_fails_without_baml(self):
        """Test architecture generation fails when BAML unavailable"""
        with patch("tools.baml_integration.is_baml_available", return_value=False):
            with patch(
                "tools.baml_integration.get_baml_error",
                return_value="BAML not installed",
            ):
                with pytest.raises(RuntimeError, match="BAML is required"):
                    generate_architecture_baml(json.dumps({"summary": "test"}), [])


class TestBuilderTaskResult:
    """Test builder task result validation with BAML"""

    def test_validate_build_result_baml(self):
        """Test validating build result with BAML (mocked)"""
        result_json = json.dumps(
            {"task_id": "task-1", "status": "success", "files_created": ["file1.py"]}
        )

        # Mock BAML client to avoid real API calls
        with patch("tools.baml_integration.get_baml_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock the BAML response
            mock_result = MagicMock()
            mock_result.unstable_internal_repr.return_value = json.dumps(
                {"Success": {"content": result_json}}
            )
            mock_client.call_function_sync.return_value = mock_result
            mock_client.create_context_manager.return_value = MagicMock()

            # Now validate_build_result_baml returns dict, not None
            validated = validate_build_result_baml(result_json)

            assert isinstance(validated, dict)
            assert validated["status"] == "success"

    def test_validate_build_result_fails_without_baml(self):
        """Test build validation fails when BAML unavailable"""
        with patch("tools.baml_integration.is_baml_available", return_value=False):
            with patch(
                "tools.baml_integration.get_baml_error",
                return_value="BAML not installed",
            ):
                with pytest.raises(RuntimeError, match="BAML is required"):
                    validate_build_result_baml(json.dumps({"task_id": "test"}))


class TestFallbackBehavior:
    """Test graceful fallback to JSON mode"""

    def test_fallback_to_json(self, capsys):
        """Test fallback logging"""
        error = Exception("Test error")
        fallback_to_json("test_operation", error)

        captured = capsys.readouterr()
        assert "BAML test_operation failed" in captured.err
        assert "JSON fallback" in captured.err


class TestBAMLRequired:
    """Test that BAML is required and fails hard when unavailable"""

    def test_baml_must_be_available(self):
        """Test that BAML is available (required dependency)"""
        # BAML is now a required dependency - it must be available
        assert is_baml_available(), (
            "BAML must be available. Install with: pip install baml-py\n"
            f"Error: {get_baml_error()}"
        )

    def test_update_phase_fails_without_baml(self):
        """Test that phase tracking fails hard without BAML"""
        # Mock BAML as unavailable
        with patch("tools.baml_integration.is_baml_available", return_value=False):
            with patch(
                "tools.baml_integration.get_baml_error",
                return_value="BAML not installed",
            ):
                # Should raise RuntimeError, not return JSON fallback
                with pytest.raises(RuntimeError, match="BAML is required"):
                    update_phase_with_baml(
                        phase="Test",
                        status="testing",
                        detail="Testing BAML requirement",
                    )

    def test_validate_fails_without_baml(self):
        """Test that validation fails hard without BAML"""
        valid_json = json.dumps(
            {"session_id": "test", "current_phase": "Test", "status": "testing"}
        )

        # Mock BAML as unavailable
        with patch("tools.baml_integration.is_baml_available", return_value=False):
            with patch(
                "tools.baml_integration.get_baml_error",
                return_value="BAML not installed",
            ):
                # Should raise RuntimeError, not return tuple
                with pytest.raises(RuntimeError, match="BAML is required"):
                    validate_phase_info(valid_json)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

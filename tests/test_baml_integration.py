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

import os
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
    fallback_to_json
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
            "clients.baml"
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
        # Note: This may fail if baml-py is not installed, which is expected
        success, error = compile_baml_schemas()

        if success:
            assert error is None
            # Client directory should exist
            client_dir = get_baml_client_dir()
            assert client_dir.exists()
        else:
            # If compilation failed, error should be set
            assert error is not None
            assert "baml" in error.lower() or "not installed" in error.lower()


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
        """Test updating phase with BAML (or JSON fallback)"""
        phase_info = update_phase_with_baml(
            phase="Scout",
            status="researching",
            detail="Analyzing requirements",
            session_id="test-session",
            iteration=0
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

    def test_validate_phase_info_valid(self):
        """Test validating valid phase info JSON"""
        valid_json = json.dumps({
            "session_id": "test",
            "current_phase": "Scout",
            "phase_number": "1/7",
            "status": "researching",
            "progress_detail": "Test",
            "test_iteration": 0,
            "phases_completed": [],
            "started_at": "2025-01-13T00:00:00Z",
            "last_updated": "2025-01-13T00:00:00Z"
        })

        valid, phase_info, error = validate_phase_info(valid_json)

        assert valid is True
        assert phase_info is not None
        assert error is None
        assert phase_info["session_id"] == "test"

    def test_validate_phase_info_invalid_json(self):
        """Test validating invalid JSON"""
        invalid_json = "{ invalid json }"

        valid, phase_info, error = validate_phase_info(invalid_json)

        assert valid is False
        assert phase_info is None
        assert error is not None
        assert "json" in error.lower()

    def test_validate_phase_info_missing_fields(self):
        """Test validating JSON with missing required fields"""
        incomplete_json = json.dumps({
            "session_id": "test"
            # Missing required fields
        })

        valid, phase_info, error = validate_phase_info(incomplete_json)

        assert valid is False
        assert error is not None
        assert "missing" in error.lower()


class TestScoutReport:
    """Test Scout report generation with BAML"""

    def test_generate_scout_report_baml(self):
        """Test generating Scout report with BAML"""
        # This will likely return None if BAML not installed
        report = generate_scout_report_baml(
            task_description="Build a web app",
            codebase_analysis="Python project",
            past_patterns="No patterns"
        )

        # If BAML is available, report should be a dict
        if report is not None:
            assert isinstance(report, dict)
            # Would check for ScoutReport fields here
        else:
            # BAML not available, which is acceptable
            assert not is_baml_available()


class TestArchitectureBlueprint:
    """Test architecture blueprint generation with BAML"""

    def test_generate_architecture_baml(self):
        """Test generating architecture with BAML"""
        scout_json = json.dumps({"summary": "Test scout report"})
        risks = ["Risk 1", "Risk 2"]

        # This will likely return None if BAML not installed
        architecture = generate_architecture_baml(scout_json, risks)

        # If BAML is available, architecture should be a dict
        if architecture is not None:
            assert isinstance(architecture, dict)
        else:
            # BAML not available, which is acceptable
            assert not is_baml_available()


class TestBuilderTaskResult:
    """Test builder task result validation with BAML"""

    def test_validate_build_result_baml(self):
        """Test validating build result with BAML"""
        result_json = json.dumps({
            "task_id": "task-1",
            "status": "success",
            "files_created": ["file1.py"]
        })

        # This will likely return None if BAML not installed
        validated = validate_build_result_baml(result_json)

        # If BAML is available, validated should be a dict
        if validated is not None:
            assert isinstance(validated, dict)
        else:
            # BAML not available, which is acceptable
            assert not is_baml_available()


class TestFallbackBehavior:
    """Test graceful fallback to JSON mode"""

    def test_fallback_to_json(self, capsys):
        """Test fallback logging"""
        error = Exception("Test error")
        fallback_to_json("test_operation", error)

        captured = capsys.readouterr()
        assert "BAML test_operation failed" in captured.err
        assert "JSON fallback" in captured.err


class TestBackwardCompatibility:
    """Test backward compatibility with JSON mode"""

    def test_json_mode_works_without_baml(self):
        """Test that JSON mode works even if BAML is unavailable"""
        # update_phase_with_baml should always return a valid dict
        phase_info = update_phase_with_baml(
            phase="Test",
            status="testing",
            detail="Testing backward compatibility"
        )

        assert isinstance(phase_info, dict)
        assert "session_id" in phase_info
        assert "current_phase" in phase_info
        assert "status" in phase_info

    def test_validate_works_without_baml(self):
        """Test that validation works in JSON mode"""
        valid_json = json.dumps({
            "session_id": "test",
            "current_phase": "Test",
            "status": "testing"
        })

        valid, phase_info, error = validate_phase_info(valid_json)

        # Should validate successfully in JSON mode
        assert valid is True
        assert phase_info is not None
        assert error is None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

#!/usr/bin/env python3
"""
Schema validation tests for BAML files

Tests verify that all BAML schema files:
- Exist in the correct location
- Have valid BAML syntax
- Define required types and functions
- Include proper documentation
"""

import sys
import pytest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.baml_integration import get_baml_schemas_dir


class TestPhaseTrackingSchema:
    """Test phase_tracking.baml schema"""

    def test_file_exists(self):
        """Test that phase_tracking.baml exists"""
        schema = get_baml_schemas_dir() / "phase_tracking.baml"
        assert schema.exists(), "phase_tracking.baml not found"

    def test_defines_phase_info_class(self):
        """Test that PhaseInfo class is defined"""
        schema = get_baml_schemas_dir() / "phase_tracking.baml"
        content = schema.read_text()

        assert "class PhaseInfo" in content
        assert "session_id" in content
        assert "current_phase" in content
        assert "status" in content
        assert "test_iteration" in content

    def test_defines_phase_type_enum(self):
        """Test that PhaseType enum is defined"""
        schema = get_baml_schemas_dir() / "phase_tracking.baml"
        content = schema.read_text()

        assert "enum PhaseType" in content
        assert "Scout" in content
        assert "Architect" in content
        assert "Builder" in content
        assert "Test" in content

    def test_defines_phase_status_enum(self):
        """Test that PhaseStatus enum is defined"""
        schema = get_baml_schemas_dir() / "phase_tracking.baml"
        content = schema.read_text()

        assert "enum PhaseStatus" in content
        assert "researching" in content
        assert "designing" in content
        assert "building" in content
        assert "testing" in content

    def test_defines_functions(self):
        """Test that required functions are defined"""
        schema = get_baml_schemas_dir() / "phase_tracking.baml"
        content = schema.read_text()

        assert "function CreatePhaseInfo" in content
        assert "function ValidatePhaseInfo" in content


class TestScoutSchema:
    """Test scout.baml schema"""

    def test_file_exists(self):
        """Test that scout.baml exists"""
        schema = get_baml_schemas_dir() / "scout.baml"
        assert schema.exists(), "scout.baml not found"

    def test_defines_scout_report_class(self):
        """Test that ScoutReport class is defined"""
        schema = get_baml_schemas_dir() / "scout.baml"
        content = schema.read_text()

        assert "class ScoutReport" in content
        assert "executive_summary" in content
        assert "key_requirements" in content
        assert "tech_stack" in content
        assert "architecture_recommendations" in content

    def test_defines_tech_stack_class(self):
        """Test that TechStack class is defined"""
        schema = get_baml_schemas_dir() / "scout.baml"
        content = schema.read_text()

        assert "class TechStack" in content
        assert "languages" in content
        assert "frameworks" in content
        assert "dependencies" in content

    def test_defines_challenge_class(self):
        """Test that Challenge class is defined"""
        schema = get_baml_schemas_dir() / "scout.baml"
        content = schema.read_text()

        assert "class Challenge" in content
        assert "description" in content
        assert "severity" in content
        assert "mitigation" in content

    def test_defines_functions(self):
        """Test that required functions are defined"""
        schema = get_baml_schemas_dir() / "scout.baml"
        content = schema.read_text()

        assert "function GenerateScoutReport" in content


class TestArchitectSchema:
    """Test architect.baml schema"""

    def test_file_exists(self):
        """Test that architect.baml exists"""
        schema = get_baml_schemas_dir() / "architect.baml"
        assert schema.exists(), "architect.baml not found"

    def test_defines_architecture_blueprint_class(self):
        """Test that ArchitectureBlueprint class is defined"""
        schema = get_baml_schemas_dir() / "architect.baml"
        content = schema.read_text()

        assert "class ArchitectureBlueprint" in content
        assert "system_overview" in content
        assert "file_structure" in content
        assert "modules" in content
        assert "test_plan" in content

    def test_defines_test_plan_class(self):
        """Test that TestPlan class is defined"""
        schema = get_baml_schemas_dir() / "architect.baml"
        content = schema.read_text()

        assert "class TestPlan" in content
        assert "unit_tests" in content
        assert "integration_tests" in content
        assert "e2e_tests" in content

    def test_defines_functions(self):
        """Test that required functions are defined"""
        schema = get_baml_schemas_dir() / "architect.baml"
        content = schema.read_text()

        assert "function GenerateArchitecture" in content


class TestBuilderSchema:
    """Test builder.baml schema"""

    def test_file_exists(self):
        """Test that builder.baml exists"""
        schema = get_baml_schemas_dir() / "builder.baml"
        assert schema.exists(), "builder.baml not found"

    def test_defines_build_task_result_class(self):
        """Test that BuildTaskResult class is defined"""
        schema = get_baml_schemas_dir() / "builder.baml"
        content = schema.read_text()

        assert "class BuildTaskResult" in content
        assert "task_id" in content
        assert "status" in content
        assert "files_created" in content
        assert "errors" in content

    def test_defines_build_error_class(self):
        """Test that BuildError class is defined"""
        schema = get_baml_schemas_dir() / "builder.baml"
        content = schema.read_text()

        assert "class BuildError" in content
        assert "file" in content
        assert "message" in content
        assert "severity" in content

    def test_defines_functions(self):
        """Test that required functions are defined"""
        schema = get_baml_schemas_dir() / "builder.baml"
        content = schema.read_text()

        assert "function ExecuteBuildTask" in content


class TestClientsSchema:
    """Test clients.baml schema"""

    def test_file_exists(self):
        """Test that clients.baml exists"""
        schema = get_baml_schemas_dir() / "clients.baml"
        assert schema.exists(), "clients.baml not found"

    def test_defines_claude_clients(self):
        """Test that Claude clients are defined"""
        schema = get_baml_schemas_dir() / "clients.baml"
        content = schema.read_text()

        assert "client<llm> Claude35Sonnet" in content
        assert "client<llm> Claude35Haiku" in content
        assert "provider anthropic" in content

    def test_defines_openai_clients(self):
        """Test that OpenAI clients are defined"""
        schema = get_baml_schemas_dir() / "clients.baml"
        content = schema.read_text()

        assert "client<llm> GPT4" in content
        assert "provider openai" in content

    def test_defines_retry_policies(self):
        """Test that retry policies are defined"""
        schema = get_baml_schemas_dir() / "clients.baml"
        content = schema.read_text()

        assert "retry_policy" in content


class TestSchemaDocumentation:
    """Test that schemas include proper documentation"""

    def test_phase_tracking_has_descriptions(self):
        """Test that phase_tracking.baml includes @description attributes"""
        schema = get_baml_schemas_dir() / "phase_tracking.baml"
        content = schema.read_text()

        assert "@description" in content

    def test_scout_has_descriptions(self):
        """Test that scout.baml includes @description attributes"""
        schema = get_baml_schemas_dir() / "scout.baml"
        content = schema.read_text()

        assert "@description" in content

    def test_architect_has_descriptions(self):
        """Test that architect.baml includes @description attributes"""
        schema = get_baml_schemas_dir() / "architect.baml"
        content = schema.read_text()

        assert "@description" in content

    def test_builder_has_descriptions(self):
        """Test that builder.baml includes @description attributes"""
        schema = get_baml_schemas_dir() / "builder.baml"
        content = schema.read_text()

        assert "@description" in content


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

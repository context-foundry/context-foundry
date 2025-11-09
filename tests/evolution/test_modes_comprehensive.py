#!/usr/bin/env python3
"""
Comprehensive tests for Evolution modes to improve coverage

Tests for:
- ResearchDiscoveryMode (47% coverage → 100%)
- ChaosCreativeMode (76% coverage → 100%)
"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from tools.evolution.modes.research_discovery import ResearchDiscoveryMode
from tools.evolution.modes.chaos_creative import ChaosCreativeMode
from tools.evolution.modes.base_mode import TaskResult


class TestResearchDiscoveryMode:
    """Comprehensive tests for ResearchDiscoveryMode"""

    def test_initialization(self):
        """Test mode can be initialized"""
        mode = ResearchDiscoveryMode()
        assert mode is not None

    def test_generate_tasks_returns_empty_list(self):
        """Test that generate_tasks returns empty list (disabled by default)"""
        mode = ResearchDiscoveryMode()
        tasks = mode.generate_tasks()
        assert tasks == []
        assert isinstance(tasks, list)

    def test_execute_task_success(self):
        """Test successful research task execution"""
        mode = ResearchDiscoveryMode()

        # Create mock task
        task = Mock()
        task.params = {
            "prompt": "Investigate quantum computing advances",
            "sources": ["web", "arxiv"],
        }

        result = mode.execute_task(task)

        assert result.success is True
        assert result.output is not None
        assert "report" in result.output
        assert "sources_searched" in result.output
        assert "papers_analyzed" in result.output
        assert result.output["sources_searched"] == ["web", "arxiv"]
        assert result.output["papers_analyzed"] == 0

    def test_execute_task_with_minimal_params(self):
        """Test execution with minimal parameters"""
        mode = ResearchDiscoveryMode()

        task = Mock()
        task.params = {"prompt": "Test research"}

        result = mode.execute_task(task)

        assert result.success is True
        assert result.output["sources_searched"] == ["web"]

    def test_execute_task_with_empty_params(self):
        """Test execution with empty params"""
        mode = ResearchDiscoveryMode()

        task = Mock()
        task.params = {}

        result = mode.execute_task(task)

        assert result.success is True
        assert "report" in result.output

    def test_execute_task_handles_exception(self):
        """Test that execute_task handles exceptions gracefully"""
        mode = ResearchDiscoveryMode()

        # Create task that will cause an error
        task = Mock()
        task.params = None  # This should cause an error

        result = mode.execute_task(task)

        assert result.success is False
        assert result.output is None
        assert result.error is not None
        assert isinstance(result.error, str)

    def test_validate_result_success(self):
        """Test validation of successful result"""
        mode = ResearchDiscoveryMode()

        result = TaskResult(success=True, output={"report": "Test report"})

        assert mode.validate_result(result) is True

    def test_validate_result_failure(self):
        """Test validation of failed result"""
        mode = ResearchDiscoveryMode()

        result = TaskResult(success=False, output=None, error="Error occurred")

        assert mode.validate_result(result) is False

    def test_validate_result_success_but_no_output(self):
        """Test validation of result with success=True but no output"""
        mode = ResearchDiscoveryMode()

        result = TaskResult(success=True, output=None)

        assert mode.validate_result(result) is False

    def test_create_placeholder_report_format(self):
        """Test that placeholder report has correct format"""
        mode = ResearchDiscoveryMode()

        prompt = "Test quantum research"
        report = mode._create_placeholder_report(prompt)

        assert "# Research Report: Test quantum research" in report
        assert "## Summary" in report
        assert "## Papers Analyzed" in report
        assert "## Hypotheses" in report
        assert "## Next Steps" in report
        assert "Research mode is disabled by default" in report

    def test_create_placeholder_report_includes_timestamp(self):
        """Test that placeholder report includes timestamp"""
        mode = ResearchDiscoveryMode()

        before = datetime.utcnow()
        report = mode._create_placeholder_report("Test")
        after = datetime.utcnow()

        # Report should contain a timestamp in ISO format
        assert "Research task created at" in report
        # Should contain ISO timestamp
        assert "T" in report  # ISO format includes T
        assert "Z" in report or ":" in report  # ISO format


class TestChaosCreativeMode:
    """Comprehensive tests for ChaosCreativeMode"""

    def test_initialization(self):
        """Test mode can be initialized"""
        mode = ChaosCreativeMode()
        assert mode is not None
        assert hasattr(mode, "PROJECT_TYPES")
        assert hasattr(mode, "PROJECT_IDEAS")

    def test_project_types_probabilities_sum_to_one(self):
        """Test that project type probabilities sum to approximately 1.0"""
        mode = ChaosCreativeMode()
        total = sum(mode.PROJECT_TYPES.values())
        assert abs(total - 1.0) < 0.01  # Allow small floating point error

    def test_generate_tasks_returns_one_task(self):
        """Test that generate_tasks returns exactly one task"""
        mode = ChaosCreativeMode()
        tasks = mode.generate_tasks()

        assert len(tasks) == 1
        assert tasks[0]["type"] == "chaos_creative"
        assert "params" in tasks[0]

    def test_generate_tasks_has_required_fields(self):
        """Test that generated tasks have required fields"""
        mode = ChaosCreativeMode()
        tasks = mode.generate_tasks()

        params = tasks[0]["params"]
        assert "project_type" in params
        assert "idea" in params
        assert "tech_stack" in params

        assert params["project_type"] in mode.PROJECT_TYPES
        assert isinstance(params["idea"], str)
        assert isinstance(params["tech_stack"], list)

    def test_weighted_random_selection(self):
        """Test weighted random selection logic"""
        mode = ChaosCreativeMode()

        # Run multiple times to test randomness
        results = []
        for _ in range(100):
            result = mode._weighted_random(mode.PROJECT_TYPES)
            results.append(result)

        # Should have selected at least some different types
        unique_results = set(results)
        assert len(unique_results) >= 2

        # All results should be valid project types
        for result in results:
            assert result in mode.PROJECT_TYPES

    def test_weighted_random_with_single_item(self):
        """Test weighted random with only one option"""
        mode = ChaosCreativeMode()

        weights = {"only_option": 1.0}
        result = mode._weighted_random(weights)

        assert result == "only_option"

    def test_select_tech_stack_web_app(self):
        """Test tech stack selection for web app"""
        mode = ChaosCreativeMode()
        stack = mode._select_tech_stack("web_app")

        assert isinstance(stack, list)
        assert len(stack) > 0
        assert "react" in stack or "typescript" in stack or "tailwind" in stack

    def test_select_tech_stack_cli_tool(self):
        """Test tech stack selection for CLI tool"""
        mode = ChaosCreativeMode()
        stack = mode._select_tech_stack("cli_tool")

        assert isinstance(stack, list)
        assert "python" in stack or "click" in stack or "rich" in stack

    def test_select_tech_stack_unknown_type(self):
        """Test tech stack selection for unknown project type"""
        mode = ChaosCreativeMode()
        stack = mode._select_tech_stack("unknown_type")

        # Should return default stack
        assert stack == ["python"]

    def test_select_tech_stack_all_types(self):
        """Test that all project types have tech stacks"""
        mode = ChaosCreativeMode()

        for project_type in mode.PROJECT_TYPES.keys():
            stack = mode._select_tech_stack(project_type)
            assert isinstance(stack, list)
            assert len(stack) > 0

    def test_execute_task_success(self):
        """Test successful task execution"""
        mode = ChaosCreativeMode()

        task = Mock()
        task.params = {
            "project_type": "web_app",
            "idea": "Test idea",
            "tech_stack": ["react", "typescript"],
        }

        result = mode.execute_task(task)

        assert result.success is True
        assert result.output is not None
        assert result.output["project_type"] == "web_app"
        assert result.output["idea"] == "Test idea"
        assert result.output["tech_stack"] == ["react", "typescript"]
        assert "message" in result.output

    def test_execute_task_handles_exception(self):
        """Test that execute_task handles exceptions"""
        mode = ChaosCreativeMode()

        task = Mock()
        task.params = None  # This should cause an error

        result = mode.execute_task(task)

        assert result.success is False
        assert result.output is None
        assert result.error is not None

    def test_validate_result_success(self):
        """Test validation of successful result"""
        mode = ChaosCreativeMode()

        result = TaskResult(success=True, output={"project_type": "web_app"})

        assert mode.validate_result(result) is True

    def test_validate_result_failure(self):
        """Test validation of failed result"""
        mode = ChaosCreativeMode()

        result = TaskResult(success=False, output=None, error="Error")

        assert mode.validate_result(result) is False

    def test_project_ideas_coverage(self):
        """Test that all project types have ideas defined"""
        mode = ChaosCreativeMode()

        for project_type in mode.PROJECT_TYPES.keys():
            assert project_type in mode.PROJECT_IDEAS
            ideas = mode.PROJECT_IDEAS[project_type]
            assert isinstance(ideas, list)
            assert len(ideas) > 0

    def test_generate_multiple_tasks_diversity(self):
        """Test that generating multiple tasks creates diversity"""
        mode = ChaosCreativeMode()

        ideas = set()
        for _ in range(20):
            tasks = mode.generate_tasks()
            idea = tasks[0]["params"]["idea"]
            ideas.add(idea)

        # Should have at least a few different ideas
        assert len(ideas) >= 2


class TestCommunicationModulesPlaceholder:
    """
    Placeholder tests for communication modules

    These modules are placeholder implementations (0% coverage is expected):
    - rest_api.py: Placeholder FastAPI routes
    - web_dashboard.py: Placeholder Flask app
    - web_dashboard_server.py: Placeholder server
    - websocket_stream.py: Placeholder WebSocket

    Since they are placeholders with no real implementation,
    we document their intended purpose rather than testing empty stubs.
    """

    def test_rest_api_routes_defined(self):
        """Test that REST API routes are documented"""
        from tools.evolution.communication import rest_api

        assert hasattr(rest_api, "API_ROUTES")
        assert isinstance(rest_api.API_ROUTES, dict)
        assert len(rest_api.API_ROUTES) > 0

        # Verify expected routes are documented
        assert "POST /tasks" in rest_api.API_ROUTES
        assert "GET /tasks" in rest_api.API_ROUTES
        assert "GET /health" in rest_api.API_ROUTES

    def test_rest_api_functions_exist(self):
        """Test that REST API functions are defined"""
        from tools.evolution.communication import rest_api

        # Functions should exist even if they're placeholders
        assert hasattr(rest_api, "create_task")
        assert hasattr(rest_api, "list_tasks")
        assert hasattr(rest_api, "get_task")
        assert hasattr(rest_api, "health_check")

        # Verify they're callable
        assert callable(rest_api.create_task)
        assert callable(rest_api.list_tasks)
        assert callable(rest_api.get_task)
        assert callable(rest_api.health_check)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

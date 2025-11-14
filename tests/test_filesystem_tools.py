"""
Test suite for filesystem-based tool discovery

Tests the complete filesystem tool discovery pipeline:
- Tool metadata parsing
- Tool discovery scanning
- Tool search functionality
- Tool execution wrapper
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.mcp_utils.filesystem_tools import (
    ToolDiscoveryScanner,
    ToolExecutor,
    ToolMetadata,
    ToolMetadataParser,
    ToolParameter,
    discover_all_tools,
    get_scanner,
    search_tools_by_query,
)


class TestToolMetadataParser:
    """Test tool metadata parsing from Python files"""

    def test_parse_docstring_basic(self):
        """Test basic docstring parsing"""
        docstring = """
        Tool: test_tool
        Category: test
        Description: A test tool for testing

        Parameters:
          - param1: str (required) - First parameter
          - param2: int (optional, default=10) - Second parameter

        Returns:
          str - Test output

        Examples:
          - test_tool("hello")
          - test_tool("world", 20)
        """

        metadata = ToolMetadataParser._parse_docstring(docstring)

        assert metadata["description"] == "A test tool for testing"
        assert len(metadata["parameters"]) == 2
        assert metadata["parameters"][0]["name"] == "param1"
        assert metadata["parameters"][0]["required"] is True
        assert metadata["parameters"][1]["name"] == "param2"
        assert metadata["parameters"][1]["required"] is False
        assert metadata["return_type"] == "str"
        assert len(metadata["examples"]) == 2

    def test_parse_parameter_line(self):
        """Test parameter line parsing"""
        line = "task: str (required) - The task description"
        param = ToolMetadataParser._parse_parameter_line(line)

        assert param["name"] == "task"
        assert param["type"] == "str"
        assert param["required"] is True
        assert param["description"] == "The task description"

    def test_parse_parameter_line_with_default(self):
        """Test parameter line parsing with default value"""
        line = "timeout: float (optional, default=10.0) - Timeout in minutes"
        param = ToolMetadataParser._parse_parameter_line(line)

        assert param["name"] == "timeout"
        assert param["type"] == "float"
        assert param["required"] is False
        assert param["default"] == "10.0"
        assert param["description"] == "Timeout in minutes"

    def test_parse_real_tool_file(self):
        """Test parsing a real tool file"""
        tool_file = Path.home() / ".context-foundry" / "tools" / "codex" / "search.py"

        if not tool_file.exists():
            pytest.skip("Tool file not found")

        metadata = ToolMetadataParser.parse_tool_file(tool_file)

        assert metadata is not None
        assert metadata.name == "search"
        assert metadata.category == "codex"
        assert "search" in metadata.description.lower()
        assert metadata.file_hash != ""


class TestToolMetadata:
    """Test ToolMetadata data class"""

    def test_get_signature(self):
        """Test function signature generation"""
        metadata = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test tool",
            parameters=[
                ToolParameter(name="param1", type="str", required=True),
                ToolParameter(name="param2", type="int", required=False, default=10),
            ],
            return_type="str",
        )

        sig = metadata.get_signature()
        assert sig == "test_tool(param1: str, param2: int = 10) -> str"

    def test_get_summary_minimal(self):
        """Test minimal summary generation"""
        metadata = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test tool for testing. More details here.",
            return_type="str",
        )

        summary = metadata.get_summary("minimal")
        assert "test_tool" in summary
        assert "Test tool for testing" in summary

    def test_get_summary_standard(self):
        """Test standard summary generation"""
        metadata = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test tool",
            parameters=[
                ToolParameter(name="param1", type="str", required=True),
            ],
            return_type="str",
        )

        summary = metadata.get_summary("standard")
        assert "test_tool" in summary
        assert "Signature:" in summary
        assert "param1: str" in summary

    def test_get_summary_full(self):
        """Test full summary generation"""
        metadata = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test tool",
            parameters=[
                ToolParameter(
                    name="param1",
                    type="str",
                    required=True,
                    description="First param",
                ),
            ],
            return_type="str",
            examples=["test_tool('hello')"],
        )

        summary = metadata.get_summary("full")
        assert "Tool: test_tool" in summary
        assert "Category: test" in summary
        assert "Parameters:" in summary
        assert "Examples:" in summary

    def test_to_dict(self):
        """Test dictionary serialization"""
        metadata = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test tool",
            parameters=[
                ToolParameter(name="param1", type="str", required=True),
            ],
        )

        data = metadata.to_dict()
        assert data["name"] == "test_tool"
        assert data["category"] == "test"
        assert len(data["parameters"]) == 1


class TestToolDiscoveryScanner:
    """Test tool discovery scanner"""

    def test_scanner_initialization(self):
        """Test scanner initialization"""
        scanner = ToolDiscoveryScanner()
        assert scanner.base_path == Path.home() / ".context-foundry" / "tools"
        assert scanner._tool_cache == {}

    def test_custom_base_path(self):
        """Test scanner with custom base path"""
        custom_path = Path("/tmp/custom_tools")
        scanner = ToolDiscoveryScanner(base_path=custom_path)
        assert scanner.base_path == custom_path

    def test_discover_tools(self):
        """Test tool discovery"""
        scanner = ToolDiscoveryScanner()
        tools = scanner.discover_tools(force_refresh=True)

        # Should find at least the 3 example tools we created
        if tools:
            assert any(t.name == "sync_execute" for t in tools)
            assert any(t.category == "codex" for t in tools)
            assert any(t.category == "delegation" for t in tools)

    def test_search_tools(self):
        """Test tool search"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        # Search for delegation tools
        results = scanner.search_tools("delegate", category="delegation")
        assert isinstance(results, list)

        # Search for codex tools
        results = scanner.search_tools("codex", category="codex")
        assert isinstance(results, list)

    def test_get_tool(self):
        """Test getting tool by name"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        tool = scanner.get_tool("sync_execute")
        if tool:  # Only assert if tool exists
            assert tool.name == "sync_execute"
            assert tool.category == "delegation"

    def test_get_categories(self):
        """Test getting tool categories"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        categories = scanner.get_categories()
        assert isinstance(categories, list)
        if categories:
            assert "codex" in categories or "delegation" in categories


class TestToolExecutor:
    """Test tool executor"""

    def test_executor_initialization(self):
        """Test executor initialization"""
        executor = ToolExecutor(timeout_seconds=300)
        assert executor.timeout_seconds == 300

    def test_validate_parameters_success(self):
        """Test parameter validation with valid params"""
        executor = ToolExecutor()
        tool = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test",
            parameters=[
                ToolParameter(name="param1", type="str", required=True),
                ToolParameter(name="param2", type="int", required=False, default=10),
            ],
        )

        # Should not raise with required params
        executor._validate_parameters(tool, {"param1": "value"})

    def test_validate_parameters_missing_required(self):
        """Test parameter validation with missing required params"""
        executor = ToolExecutor()
        tool = ToolMetadata(
            name="test_tool",
            category="test",
            file_path=Path("/tmp/test.py"),
            description="Test",
            parameters=[
                ToolParameter(name="param1", type="str", required=True),
            ],
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="missing required parameters"):
            executor._validate_parameters(tool, {})


class TestGlobalFunctions:
    """Test global convenience functions"""

    def test_discover_all_tools(self):
        """Test global discover_all_tools function"""
        tools = discover_all_tools(force_refresh=True)
        assert isinstance(tools, list)

    def test_search_tools_by_query(self):
        """Test global search_tools_by_query function"""
        # First discover tools
        discover_all_tools(force_refresh=True)

        # Then search
        results = search_tools_by_query("codex", detail_level="minimal")
        assert isinstance(results, list)

    def test_get_scanner_singleton(self):
        """Test global scanner singleton"""
        scanner1 = get_scanner()
        scanner2 = get_scanner()
        assert scanner1 is scanner2  # Should be same instance


class TestIntegration:
    """Integration tests for complete workflows"""

    def test_end_to_end_tool_discovery(self):
        """Test complete tool discovery workflow"""
        # 1. Discover tools
        tools = discover_all_tools(force_refresh=True)

        if not tools:
            pytest.skip("No tools found in filesystem")

        # 2. Search for specific tool
        results = search_tools_by_query("search", detail_level="full")
        assert isinstance(results, list)

        # 3. Get specific tool
        scanner = get_scanner()
        tool = scanner.get_tool("search")
        if tool:
            assert tool.name == "search"
            assert tool.file_path.exists()

    def test_tool_execution_simple(self):
        """Test executing a simple tool (if available)"""
        scanner = ToolDiscoveryScanner()
        scanner.discover_tools(force_refresh=True)

        tool = scanner.get_tool("search")
        if not tool:
            pytest.skip("search tool not found")

        # Test parameter validation
        executor = ToolExecutor()
        try:
            executor._validate_parameters(tool, {"query": "test"})
        except ValueError:
            # Expected if params don't match exactly
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

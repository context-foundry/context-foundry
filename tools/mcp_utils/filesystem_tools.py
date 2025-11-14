"""
Filesystem-Based Tool Discovery for Context Foundry MCP Server

Implements progressive tool discovery by treating MCP tools as filesystem trees.
Tools are stored as standalone Python scripts that can be discovered, loaded,
and executed on-demand, dramatically reducing context token usage.

Based on: https://www.anthropic.com/engineering/code-execution-with-mcp
"""

import ast
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """Represents a single tool parameter"""

    name: str
    type: str
    required: bool = True
    default: Optional[Any] = None
    description: str = ""


@dataclass
class ToolMetadata:
    """Metadata extracted from a filesystem-based tool file"""

    name: str
    category: str
    file_path: Path
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    return_type: str = "str"
    examples: List[str] = field(default_factory=list)
    file_hash: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "category": self.category,
            "file_path": str(self.file_path),
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "description": p.description,
                }
                for p in self.parameters
            ],
            "return_type": self.return_type,
            "examples": self.examples,
            "file_hash": self.file_hash,
        }

    def get_signature(self) -> str:
        """Get function signature string"""
        params = []
        for p in self.parameters:
            param_str = f"{p.name}: {p.type}"
            if not p.required:
                param_str += f" = {repr(p.default)}"
            params.append(param_str)
        return f"{self.name}({', '.join(params)}) -> {self.return_type}"

    def get_summary(self, detail_level: str = "standard") -> str:
        """
        Get formatted summary for different detail levels

        Args:
            detail_level: "minimal", "standard", or "full"
        """
        if detail_level == "minimal":
            return f"{self.name} - {self.description.split('.')[0]}"

        elif detail_level == "standard":
            sig = self.get_signature()
            return f"{self.name}\n  Signature: {sig}\n  Description: {self.description}"

        else:  # full
            lines = [
                f"Tool: {self.name}",
                f"Category: {self.category}",
                f"Signature: {self.get_signature()}",
                f"Description: {self.description}",
                "",
                "Parameters:",
            ]
            for p in self.parameters:
                req = "required" if p.required else "optional"
                lines.append(f"  - {p.name}: {p.type} ({req})")
                if p.description:
                    lines.append(f"    {p.description}")
            if self.examples:
                lines.append("")
                lines.append("Examples:")
                for ex in self.examples:
                    lines.append(f"  {ex}")
            return "\n".join(lines)


class ToolMetadataParser:
    """Parses tool metadata from Python source files"""

    @staticmethod
    def parse_tool_file(file_path: Path) -> Optional[ToolMetadata]:
        """
        Parse a tool file and extract metadata

        Args:
            file_path: Path to Python tool file

        Returns:
            ToolMetadata if valid tool, None otherwise
        """
        try:
            source = file_path.read_text()
            file_hash = hashlib.sha256(source.encode()).hexdigest()[:16]

            # Parse AST
            tree = ast.parse(source)

            # Extract module docstring
            module_doc = ast.get_docstring(tree)
            if not module_doc:
                logger.debug(f"No docstring in {file_path}, skipping")
                return None

            # Parse docstring for metadata
            metadata = ToolMetadataParser._parse_docstring(module_doc)
            if not metadata:
                return None

            # Get tool name from filename (without .py)
            name = file_path.stem

            # Get category from parent directory
            category = file_path.parent.name
            if category == "tools":  # Root level
                category = "core"

            # Convert docstring parameters to ToolParameter objects
            # Use docstring params as source of truth (not main() signature)
            parameters = [
                ToolParameter(
                    name=p["name"],
                    type=p["type"],
                    required=p["required"],
                    default=p.get("default"),
                    description=p.get("description", ""),
                )
                for p in metadata.get("parameters", [])
            ]

            return ToolMetadata(
                name=name,
                category=category,
                file_path=file_path,
                description=metadata.get("description", ""),
                parameters=parameters,
                return_type=metadata.get("return_type", "str"),
                examples=metadata.get("examples", []),
                file_hash=file_hash,
            )

        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return None

    @staticmethod
    def _parse_docstring(docstring: str) -> Dict[str, Any]:
        """
        Parse structured docstring in tool file

        Expected format:
        '''
        Tool: tool_name
        Category: category_name
        Description: Tool description

        Parameters:
          param1: type (required/optional, default=value) - Description
          param2: type (required) - Description

        Returns:
          return_type - Description

        Examples:
          - example1
          - example2
        '''
        """
        metadata = {"description": "", "examples": [], "parameters": []}

        lines = docstring.strip().split("\n")
        current_section = None
        description_lines = []

        for line in lines:
            line = line.strip()

            # Section headers
            if line.startswith("Tool:"):
                metadata["tool_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("Category:"):
                metadata["category"] = line.split(":", 1)[1].strip()
            elif line.startswith("Description:"):
                desc = line.split(":", 1)[1].strip()
                if desc:
                    description_lines.append(desc)
                current_section = "description"
            elif line.startswith("Parameters:"):
                current_section = "parameters"
            elif line.startswith("Returns:"):
                current_section = "returns"
            elif line.startswith("Examples:"):
                current_section = "examples"
            elif line and current_section:
                if current_section == "description":
                    description_lines.append(line)
                elif current_section == "parameters":
                    # Parameters can be indented with or without leading dash/asterisk
                    # Strip leading dash/asterisk if present
                    param_line = line.lstrip("- *")
                    # Try to parse as parameter (has format: name: type (...) - description)
                    param_info = ToolMetadataParser._parse_parameter_line(param_line)
                    if param_info:
                        metadata["parameters"].append(param_info)
                elif current_section == "returns":
                    metadata["return_type"] = line.split("-")[0].strip()
                elif current_section == "examples":
                    if line.startswith("-"):
                        metadata["examples"].append(line.lstrip("- ").strip())

        metadata["description"] = " ".join(description_lines)
        return metadata

    @staticmethod
    def _parse_parameter_line(line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a parameter line like:
        task: str (required) - The task description
        timeout: float (optional, default=10.0) - Timeout in minutes
        """
        # Pattern: name: type (required/optional, default=value) - description
        pattern = (
            r"(\w+):\s*(\w+)\s*\((required|optional)(?:,\s*default=(.+?))?\)\s*-\s*(.+)"
        )
        match = re.match(pattern, line)

        if match:
            name, type_str, req_opt, default, desc = match.groups()
            return {
                "name": name,
                "type": type_str,
                "required": req_opt == "required",
                "default": default,
                "description": desc.strip(),
            }
        return None

    @staticmethod
    def _extract_parameters(tree: ast.AST, source: str) -> List[ToolParameter]:
        """
        Extract parameters from main() function signature

        Falls back to docstring parsing if main() doesn't exist
        """
        parameters = []

        # Find main() function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                # Parse function parameters
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue

                    param = ToolParameter(
                        name=arg.arg,
                        type=ToolMetadataParser._get_type_annotation(arg),
                        required=True,  # Will be updated based on defaults
                    )
                    parameters.append(param)

                # Check for defaults
                defaults = node.args.defaults
                if defaults:
                    num_defaults = len(defaults)
                    for i, default in enumerate(defaults):
                        param_idx = len(parameters) - num_defaults + i
                        if param_idx >= 0:
                            parameters[param_idx].required = False
                            try:
                                parameters[param_idx].default = ast.literal_eval(
                                    default
                                )
                            except (ValueError, SyntaxError):
                                # Default value couldn't be evaluated, leave as None
                                pass

        return parameters

    @staticmethod
    def _get_type_annotation(arg: ast.arg) -> str:
        """Get type annotation from AST argument"""
        if arg.annotation:
            if isinstance(arg.annotation, ast.Name):
                return arg.annotation.id
            elif isinstance(arg.annotation, ast.Constant):
                return str(arg.annotation.value)
            else:
                return "Any"
        return "Any"


class ToolDiscoveryScanner:
    """Scans filesystem for tool files and maintains discovery cache"""

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize tool discovery scanner

        Args:
            base_path: Base directory for tools (default: ~/.context-foundry/tools/)
        """
        if base_path is None:
            base_path = Path.home() / ".context-foundry" / "tools"

        self.base_path = base_path
        self._tool_cache: Dict[str, ToolMetadata] = {}
        self._cache_file = base_path.parent / "tool_discovery_cache.json"

    def discover_tools(self, force_refresh: bool = False) -> List[ToolMetadata]:
        """
        Discover all tools in filesystem

        Args:
            force_refresh: Bypass cache and re-scan filesystem

        Returns:
            List of discovered ToolMetadata objects
        """
        # Load cache if available (skip if force_refresh)
        if not force_refresh and self._load_cache():
            logger.info(f"Loaded {len(self._tool_cache)} tools from cache")
            return list(self._tool_cache.values())

        # Clear cache before repopulating (handles deleted/renamed files)
        # Do this even if base_path doesn't exist to remove stale entries
        self._tool_cache.clear()

        if not self.base_path.exists():
            logger.info(f"Tools directory {self.base_path} does not exist")
            return []

        # Scan filesystem
        logger.info(f"Scanning {self.base_path} for tools...")
        discovered = []

        for tool_file in self.base_path.rglob("*.py"):
            # Skip __init__.py and other special files
            if tool_file.name.startswith("_"):
                continue

            metadata = ToolMetadataParser.parse_tool_file(tool_file)
            if metadata:
                discovered.append(metadata)
                # Use category/name as key to prevent collisions
                cache_key = f"{metadata.category}/{metadata.name}"
                self._tool_cache[cache_key] = metadata
                logger.debug(f"Discovered tool: {metadata.name} ({metadata.category})")

        logger.info(
            f"Discovered {len(discovered)} tools in {len(self._get_categories())} categories"
        )

        # Save cache
        self._save_cache()

        return discovered

    def search_tools(
        self, query: str, category: Optional[str] = None, detail_level: str = "standard"
    ) -> List[str]:
        """
        Search for tools by query string

        Args:
            query: Search query (matches name, description)
            category: Optional category filter
            detail_level: "minimal", "standard", or "full"

        Returns:
            List of formatted tool summaries
        """
        query_lower = query.lower()
        results = []

        for tool in self._tool_cache.values():
            # Filter by category if specified
            if category and tool.category != category:
                continue

            # Search in name and description
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
            ):
                results.append(tool.get_summary(detail_level))

        return results

    def get_tool(
        self, name: str, category: Optional[str] = None
    ) -> Optional[ToolMetadata]:
        """
        Get tool metadata by name

        Args:
            name: Tool name
            category: Optional category to narrow search

        Returns:
            ToolMetadata if found, None otherwise
        """
        if category:
            # Direct lookup with category
            cache_key = f"{category}/{name}"
            return self._tool_cache.get(cache_key)
        else:
            # Search across all categories
            for cache_key, tool in self._tool_cache.items():
                if tool.name == name:
                    return tool
            return None

    def get_categories(self) -> List[str]:
        """Get list of all tool categories"""
        return sorted(self._get_categories())

    def _get_categories(self) -> set:
        """Get set of unique categories"""
        return {tool.category for tool in self._tool_cache.values()}

    def _load_cache(self) -> bool:
        """Load tool cache from file"""
        if not self._cache_file.exists():
            return False

        try:
            cache_data = json.loads(self._cache_file.read_text())
            for cache_key, data in cache_data.items():
                # Reconstruct ToolMetadata
                params = [ToolParameter(**p) for p in data.get("parameters", [])]
                metadata = ToolMetadata(
                    name=data["name"],
                    category=data["category"],
                    file_path=Path(data["file_path"]),
                    description=data["description"],
                    parameters=params,
                    return_type=data.get("return_type", "str"),
                    examples=data.get("examples", []),
                    file_hash=data.get("file_hash", ""),
                )
                # Use same cache_key format as when saving
                self._tool_cache[cache_key] = metadata
            return True
        except Exception as e:
            logger.warning(f"Failed to load tool cache: {e}")
            return False

    def _save_cache(self):
        """Save tool cache to file"""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                name: tool.to_dict() for name, tool in self._tool_cache.items()
            }
            self._cache_file.write_text(json.dumps(cache_data, indent=2))
            logger.debug(f"Saved tool cache to {self._cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save tool cache: {e}")


class ToolExecutor:
    """Executes filesystem-based tools in isolated subprocesses"""

    def __init__(self, timeout_seconds: int = 300):
        """
        Initialize tool executor

        Args:
            timeout_seconds: Default timeout for tool execution
        """
        self.timeout_seconds = timeout_seconds

    def execute_tool(
        self, tool: ToolMetadata, params: Dict[str, Any], timeout: Optional[int] = None
    ) -> str:
        """
        Execute a filesystem-based tool

        Args:
            tool: Tool metadata
            params: Parameters to pass to tool
            timeout: Optional timeout override

        Returns:
            Tool output as string

        Raises:
            subprocess.TimeoutExpired: If execution exceeds timeout
            subprocess.CalledProcessError: If tool exits with non-zero status
        """
        timeout = timeout or self.timeout_seconds

        # Validate parameters
        self._validate_parameters(tool, params)

        # Execute tool
        logger.info(f"Executing tool: {tool.name} with params: {list(params.keys())}")

        try:
            result = subprocess.run(
                [sys.executable, str(tool.file_path)],
                input=json.dumps(params),
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.PIPE,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

            if result.returncode != 0:
                error_msg = (
                    f"Tool {tool.name} failed with exit code {result.returncode}"
                )
                if result.stderr:
                    error_msg += f"\nStderr: {result.stderr}"
                logger.error(error_msg)
                raise subprocess.CalledProcessError(
                    result.returncode, result.args, result.stdout, result.stderr
                )

            return result.stdout

        except subprocess.TimeoutExpired:
            logger.error(f"Tool {tool.name} timed out after {timeout}s")
            raise

    def _validate_parameters(self, tool: ToolMetadata, params: Dict[str, Any]):
        """
        Validate parameters against tool metadata

        Raises:
            ValueError: If required parameters are missing
        """
        required_params = {p.name for p in tool.parameters if p.required}
        provided_params = set(params.keys())
        missing = required_params - provided_params

        if missing:
            raise ValueError(
                f"Tool {tool.name} missing required parameters: {', '.join(missing)}"
            )


# Global scanner instance (lazy initialized)
_scanner: Optional[ToolDiscoveryScanner] = None


def get_scanner() -> ToolDiscoveryScanner:
    """Get or create global tool scanner instance"""
    global _scanner
    if _scanner is None:
        _scanner = ToolDiscoveryScanner()
    return _scanner


def discover_all_tools(force_refresh: bool = False) -> List[ToolMetadata]:
    """Discover all filesystem-based tools"""
    scanner = get_scanner()
    return scanner.discover_tools(force_refresh=force_refresh)


def search_tools_by_query(
    query: str, category: Optional[str] = None, detail_level: str = "standard"
) -> List[str]:
    """Search for tools matching query"""
    scanner = get_scanner()
    return scanner.search_tools(query, category, detail_level)


def execute_tool_by_name(
    tool_name: str, params: Dict[str, Any], timeout: Optional[int] = None
) -> str:
    """Execute a tool by name"""
    scanner = get_scanner()
    tool = scanner.get_tool(tool_name)

    if not tool:
        raise ValueError(f"Tool not found: {tool_name}")

    executor = ToolExecutor(timeout_seconds=timeout or 300)
    return executor.execute_tool(tool, params, timeout)

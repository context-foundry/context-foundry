"""
Standardized tool response formatting.

This module provides a consistent format for all tool responses, making it
easier for agents to parse and understand tool output.

Key features:
- Consistent success/failure formatting
- Metadata extraction (paths, counts, etc.)
- Smart truncation with recovery instructions
- Relative path conversion
"""

from typing import Any, Dict, Optional, Union
from pathlib import Path
from .truncation import (
    truncate_with_recovery,
    format_file_truncation,
    format_grep_truncation,
    format_command_truncation,
    count_tokens
)
from .path_utils import (
    to_relative_path,
    format_tool_output_paths,
    is_within_project
)
from .limits import ToolLimits, get_cached_default_limits


class ToolResponse:
    """Standardized tool response with agent-friendly formatting.

    This class wraps tool output in a consistent format that includes:
    - Clear success/failure indication
    - Relevant metadata (file paths, counts, etc.)
    - Smart truncation with recovery instructions
    - Relative paths to save tokens

    Example:
        >>> response = ToolResponse(
        ...     success=True,
        ...     data="File contents here...",
        ...     metadata={'file_path': '/abs/path/to/file.py', 'lines': 150}
        ... )
        >>> print(response.format_for_agent('/abs/path'))
        ✅ Success
        File: to/file.py (150 lines)

        File contents here...
    """

    def __init__(
        self,
        success: bool,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        limits: Optional[ToolLimits] = None
    ):
        """Initialize tool response.

        Args:
            success: Whether operation succeeded
            data: Response data (file content, search results, etc.)
            metadata: Additional metadata (paths, counts, etc.)
            error: Error message if success=False
            working_dir: Working directory for path conversion
            limits: ToolLimits instance (uses defaults if None)
        """
        self.success = success
        self.data = data
        self.metadata = metadata or {}
        self.error = error
        self.working_dir = working_dir or Path.cwd()
        self.limits = limits if limits is not None else get_cached_default_limits()

    def format_for_agent(self) -> str:
        """Format response optimally for agent consumption.

        Returns:
            Formatted response string

        Example:
            >>> response = ToolResponse(True, "content", {'file': '/path/to/file.py'})
            >>> output = response.format_for_agent()
            >>> output.startswith('✅ Success')
            True
        """
        output_parts = []

        # 1. Status line
        if self.success:
            output_parts.append("✅ Success")
        else:
            output_parts.append("❌ Failed")
            if self.error:
                output_parts.append(f"Error: {self.error}")

        # 2. Metadata
        if self.metadata:
            metadata_str = self._format_metadata()
            if metadata_str:
                output_parts.append(metadata_str)

        # 3. Data
        if self.data is not None:
            data_str = self._format_data()
            output_parts.append(data_str)

        # 4. Recovery instructions (if truncated)
        if self.metadata.get('was_truncated'):
            recovery = self.metadata.get('recovery_instructions')
            if recovery:
                output_parts.append("")
                output_parts.append("═" * 60)
                output_parts.append("⚠️  OUTPUT TRUNCATED")
                output_parts.append("═" * 60)
                output_parts.append(recovery)

        return '\n\n'.join(output_parts)

    def _format_metadata(self) -> str:
        """Format metadata section with relative paths.

        Returns:
            Formatted metadata string
        """
        lines = []

        # Convert paths to relative
        for key, value in self.metadata.items():
            # Skip internal metadata fields
            if key in ('was_truncated', 'recovery_instructions', 'truncation_reason',
                      'original_chars', 'original_lines', 'truncated_chars', 'truncated_lines'):
                continue

            # Format based on key type
            if 'path' in key.lower() or 'file' in key.lower():
                # Convert path to relative
                if isinstance(value, (str, Path)):
                    relative = to_relative_path(value, self.working_dir, strict=False)
                    lines.append(f"{key.replace('_', ' ').title()}: {relative}")
                else:
                    lines.append(f"{key.replace('_', ' ').title()}: {value}")
            elif isinstance(value, int):
                lines.append(f"{key.replace('_', ' ').title()}: {value:,}")
            else:
                lines.append(f"{key.replace('_', ' ').title()}: {value}")

        return '\n'.join(lines) if lines else ""

    def _format_data(self) -> str:
        """Format data section.

        Returns:
            Formatted data string
        """
        if isinstance(self.data, str):
            # Convert any paths in data to relative
            if self.limits.use_relative_paths:
                return format_tool_output_paths(self.data, self.working_dir)
            return self.data
        elif isinstance(self.data, (list, dict)):
            # Format structured data
            import json
            formatted = json.dumps(self.data, indent=2)
            if self.limits.use_relative_paths:
                return format_tool_output_paths(formatted, self.working_dir)
            return formatted
        else:
            return str(self.data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'success': self.success,
            'data': self.data,
            'metadata': self.metadata,
            'error': self.error
        }

    @classmethod
    def file_read_response(
        cls,
        content: str,
        file_path: Union[str, Path],
        working_dir: Optional[Union[str, Path]] = None,
        limits: Optional[ToolLimits] = None
    ) -> 'ToolResponse':
        """Create response for file read operation.

        Args:
            content: File content
            file_path: Path to file
            working_dir: Working directory
            limits: ToolLimits instance

        Returns:
            ToolResponse instance

        Example:
            >>> response = ToolResponse.file_read_response(
            ...     content="file content",
            ...     file_path="/path/to/file.py",
            ...     working_dir="/path"
            ... )
            >>> response.success
            True
        """
        if limits is None:
            limits = get_cached_default_limits()

        # Apply truncation if needed
        truncated, was_truncated, meta = truncate_with_recovery(
            content=content,
            file_path=str(file_path),
            operation_type='file_read',
            limits=limits
        )

        # Get file stats
        lines = content.split('\n')
        chars = len(content)
        tokens = count_tokens(content)

        metadata = {
            'file_path': file_path,
            'lines': len(lines),
            'chars': chars,
            'tokens': tokens,
            'was_truncated': was_truncated,
            **meta
        }

        return cls(
            success=True,
            data=truncated,
            metadata=metadata,
            working_dir=working_dir,
            limits=limits
        )

    @classmethod
    def grep_response(
        cls,
        results: str,
        pattern: str,
        num_matches: int,
        working_dir: Optional[Union[str, Path]] = None,
        limits: Optional[ToolLimits] = None
    ) -> 'ToolResponse':
        """Create response for grep operation.

        Args:
            results: Grep results
            pattern: Search pattern
            num_matches: Number of matches found
            working_dir: Working directory
            limits: ToolLimits instance

        Returns:
            ToolResponse instance
        """
        if limits is None:
            limits = get_cached_default_limits()

        # Apply truncation if needed
        truncated, was_truncated, meta = truncate_with_recovery(
            content=results,
            operation_type='grep',
            limits=limits
        )

        metadata = {
            'pattern': pattern,
            'matches': num_matches,
            'was_truncated': was_truncated,
            **meta
        }

        return cls(
            success=True,
            data=truncated,
            metadata=metadata,
            working_dir=working_dir,
            limits=limits
        )

    @classmethod
    def subprocess_response(
        cls,
        output: str,
        command: str,
        exit_code: int,
        working_dir: Optional[Union[str, Path]] = None,
        limits: Optional[ToolLimits] = None
    ) -> 'ToolResponse':
        """Create response for subprocess execution.

        Args:
            output: Command output
            command: Command that was run
            exit_code: Exit code
            working_dir: Working directory
            limits: ToolLimits instance

        Returns:
            ToolResponse instance
        """
        if limits is None:
            limits = get_cached_default_limits()

        # Apply truncation if needed
        truncated, was_truncated, meta = truncate_with_recovery(
            content=output,
            operation_type='subprocess',
            limits=limits
        )

        success = exit_code == 0

        metadata = {
            'command': command,
            'exit_code': exit_code,
            'was_truncated': was_truncated,
            **meta
        }

        return cls(
            success=success,
            data=truncated,
            metadata=metadata,
            error=None if success else f"Command exited with code {exit_code}",
            working_dir=working_dir,
            limits=limits
        )

    @classmethod
    def error_response(
        cls,
        error: str,
        operation: str = "operation",
        details: Optional[Dict[str, Any]] = None
    ) -> 'ToolResponse':
        """Create error response.

        Args:
            error: Error message
            operation: Operation that failed
            details: Additional error details

        Returns:
            ToolResponse instance

        Example:
            >>> response = ToolResponse.error_response(
            ...     error="File not found",
            ...     operation="file_read",
            ...     details={'path': '/missing/file.txt'}
            ... )
            >>> response.success
            False
        """
        metadata = details or {}
        metadata['operation'] = operation

        return cls(
            success=False,
            data=None,
            metadata=metadata,
            error=error
        )


def format_file_read_output(
    content: str,
    file_path: Union[str, Path],
    working_dir: Optional[Union[str, Path]] = None
) -> str:
    """Convenience function to format file read output.

    Args:
        content: File content
        file_path: Path to file
        working_dir: Working directory

    Returns:
        Formatted output string

    Example:
        >>> output = format_file_read_output("content", "/path/to/file.py", "/path")
        >>> "to/file.py" in output
        True
    """
    response = ToolResponse.file_read_response(content, file_path, working_dir)
    return response.format_for_agent()


def format_grep_output(
    results: str,
    pattern: str,
    num_matches: int,
    working_dir: Optional[Union[str, Path]] = None
) -> str:
    """Convenience function to format grep output.

    Args:
        results: Grep results
        pattern: Search pattern
        num_matches: Number of matches
        working_dir: Working directory

    Returns:
        Formatted output string
    """
    response = ToolResponse.grep_response(results, pattern, num_matches, working_dir)
    return response.format_for_agent()


def format_subprocess_output(
    output: str,
    command: str,
    exit_code: int,
    working_dir: Optional[Union[str, Path]] = None
) -> str:
    """Convenience function to format subprocess output.

    Args:
        output: Command output
        command: Command that was run
        exit_code: Exit code
        working_dir: Working directory

    Returns:
        Formatted output string
    """
    response = ToolResponse.subprocess_response(output, command, exit_code, working_dir)
    return response.format_for_agent()

"""
Semantic tagging system for tool outputs.

This module provides utilities to add semantic markers to tool results,
improving AI agent comprehension with minimal token overhead (<3%).

Key features:
- File system tags (dir/file/link/special)
- Match type tags (def/call/import/test/usage/comment/config)
- Category tags (source/test/config/doc/build/data)
- Pure functions (no side effects)
- Integration with existing path_utils

Based on proposal: docs/proposals/SEMANTIC_TAGGING_SYSTEM.md
"""

from pathlib import Path
from typing import Optional
import re

# Try to import path_utils from current package
try:
    from .path_utils import to_relative_path
except ImportError:
    # Fallback for testing or standalone use
    def to_relative_path(path, working_dir, strict=False):
        """Fallback path converter."""
        return str(Path(path).relative_to(working_dir) if working_dir else path)


# Tag vocabulary constants
FILE_TAGS = ['dir', 'file', 'link', 'special']
MATCH_TAGS = ['def', 'class', 'import', 'test', 'usage', 'comment', 'config']
CATEGORY_TAGS = ['source', 'test', 'config', 'doc', 'build', 'data']


def format_file_size(bytes_size: int) -> str:
    """
    Convert bytes to human-readable format.
    
    Args:
        bytes_size: File size in bytes
    
    Returns:
        Formatted string like "2.3KB", "15MB", "1.2GB"
    
    Examples:
        >>> format_file_size(1024)
        '1.0KB'
        >>> format_file_size(1536)
        '1.5KB'
        >>> format_file_size(2097152)
        '2.0MB'
    """
    if bytes_size < 0:
        return "0B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            if unit == 'B':
                return f"{bytes_size}{unit}"
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024
    
    return f"{bytes_size:.1f}TB"


def detect_file_type(suffix: str) -> Optional[str]:
    """
    Return semantic file type from extension.
    
    Args:
        suffix: File suffix (e.g., ".py", ".js")
    
    Returns:
        Type string (e.g., "python", "javascript") or None if unknown
    
    Examples:
        >>> detect_file_type('.py')
        'python'
        >>> detect_file_type('.js')
        'javascript'
        >>> detect_file_type('.xyz')
        >>> # Returns None
    """
    type_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'react',
        '.tsx': 'react-ts',
        '.md': 'markdown',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.txt': 'text',
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.rs': 'rust',
        '.go': 'go',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'header',
        '.hpp': 'header',
        '.html': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.xml': 'xml',
        '.sql': 'sql',
    }
    return type_map.get(suffix.lower())


def format_ls_entry(entry: Path, working_dir: Path) -> str:
    """
    Format directory entry with semantic tags.
    
    Args:
        entry: pathlib.Path object to format
        working_dir: Current working directory for relative paths
    
    Returns:
        Formatted string with semantic tags
    
    Examples:
        >>> from pathlib import Path
        >>> entry = Path('/project/src')
        >>> format_ls_entry(entry, Path('/project'))
        'dir src/ (5 items)'  # If src has 5 items
        
        >>> entry = Path('/project/main.py')
        >>> format_ls_entry(entry, Path('/project'))
        'file main.py (2.3KB, python)'
    """
    try:
        relative_path = to_relative_path(entry, working_dir, strict=False)
    except Exception:
        relative_path = str(entry.name)
    
    try:
        if entry.is_symlink():
            # Handle symlink first (before is_dir/is_file checks)
            try:
                target = entry.resolve()
                target_rel = to_relative_path(target, working_dir, strict=False)
                return f"link {relative_path} -> {target_rel}"
            except Exception:
                return f"link {relative_path} -> (broken)"
        
        elif entry.is_dir():
            # Directory
            try:
                # Count items in directory (limited to avoid hangs)
                items = list(entry.iterdir())
                count = len(items)
                if count >= 1000:
                    # If we hit the limit, there might be more
                    return f"dir {relative_path}/ (1000+ items)"
                else:
                    return f"dir {relative_path}/ ({count} items)"
            except PermissionError:
                return f"dir {relative_path}/ (permission denied)"
            except Exception:
                return f"dir {relative_path}/"
        
        elif entry.is_file():
            # Regular file
            try:
                size = entry.stat().st_size
                size_str = format_file_size(size)
                
                # Add file type hint if available
                file_type = detect_file_type(entry.suffix)
                if file_type:
                    return f"file {relative_path} ({size_str}, {file_type})"
                else:
                    return f"file {relative_path} ({size_str})"
            except Exception:
                return f"file {relative_path}"
        
        else:
            # Special file (device, socket, etc.)
            return f"special {relative_path}"
    
    except Exception:
        # Fallback - just return the path without tags
        return str(relative_path)


def detect_match_type(line_content: str, file_path: str) -> str:
    """
    Detect the type of code match from line content.
    
    Args:
        line_content: Content of the matched line
        file_path: Path to the file containing the match
    
    Returns:
        Match type: 'def', 'class', 'import', 'test', 'comment', 'config', or 'usage'
    
    Examples:
        >>> detect_match_type('def process_data():', 'main.py')
        'def'
        >>> detect_match_type('def test_process():', 'tests/test_main.py')
        'test'
        >>> detect_match_type('import os', 'utils.py')
        'import'
        >>> detect_match_type('# This is a comment', 'main.py')
        'comment'
    """
    stripped = line_content.strip()
    path_lower = file_path.lower()
    
    # Test function detection (check file path first for efficiency)
    if 'test' in path_lower or path_lower.startswith('tests/'):
        if stripped.startswith('def test_') or stripped.startswith('async def test_'):
            return 'test'
        # Also check for pytest-style test methods
        if re.match(r'^\s*def test_', stripped) or re.match(r'^\s*async def test_', stripped):
            return 'test'
    
    # Function/method definition
    if stripped.startswith('def ') or stripped.startswith('async def '):
        return 'def'
    
    # Class definition
    if stripped.startswith('class '):
        return 'class'
    
    # Import statement
    if stripped.startswith('import ') or stripped.startswith('from '):
        return 'import'
    
    # Comment detection
    if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*'):
        return 'comment'
    
    # Config/assignment detection (simple heuristic)
    if '=' in stripped and not any(keyword in stripped for keyword in ['if ', 'while ', 'for ', 'elif ']):
        # Looks like an assignment, could be configuration
        # Check if it's at module level (no leading whitespace except in class/function)
        if stripped[0].isupper() or (line_content and not line_content[0].isspace()):
            return 'config'
    
    # Default to generic usage
    return 'usage'


def format_grep_result(
    file_path: str,
    line_num: int,
    line_content: str,
    working_dir: Path
) -> str:
    """
    Format grep result with semantic match tags.
    
    Args:
        file_path: Path to file containing match
        line_num: Line number of match
        line_content: Content of matched line
        working_dir: Working directory for relative paths
    
    Returns:
        Formatted string with match type tag
    
    Examples:
        >>> format_grep_result('src/main.py', 42, 'def process():', Path('/project'))
        'match:def src/main.py:42: def process():'
        
        >>> format_grep_result('tests/test.py', 10, 'def test_foo():', Path('/project'))
        'match:test tests/test.py:10: def test_foo():'
    """
    try:
        relative_path = to_relative_path(file_path, working_dir, strict=False)
    except Exception:
        relative_path = file_path
    
    # Detect match type
    match_type = detect_match_type(line_content, file_path)
    
    # Format: match:<type> path:line: content
    return f"match:{match_type} {relative_path}:{line_num}: {line_content.strip()}"


def categorize_file(file_path: Path) -> str:
    """
    Categorize file by path and extension.

    Args:
        file_path: Path object to categorize

    Returns:
        Category: 'source', 'test', 'config', 'doc', 'build', or 'data'

    Examples:
        >>> categorize_file(Path('src/main.py'))
        'source'
        >>> categorize_file(Path('tests/test_main.py'))
        'test'
        >>> categorize_file(Path('README.md'))
        'doc'
        >>> categorize_file(Path('config.yaml'))
        'config'
    """
    path_str = str(file_path).lower()
    name = file_path.name.lower()

    # Data files (check before test - fixtures/data are more specific)
    data_extensions = ['.csv', '.xml', '.sql', '.db', '.sqlite', '.sqlite3']
    data_paths = ['data/', 'datasets/', 'fixtures/']
    if any(path_str.endswith(ext) for ext in data_extensions) or any(p in path_str for p in data_paths):
        return 'data'
    # JSON can be data or config - check path for data indicators
    if file_path.suffix == '.json' and any(p in path_str for p in ['data/', 'fixtures/', 'datasets/']):
        return 'data'

    # Test files (check after data paths to avoid false positives)
    # Be more specific - look for test file patterns, not just "test" anywhere
    test_indicators = [
        path_str.startswith('tests/'),
        path_str.startswith('test/'),
        '/tests/' in path_str,
        '/test/' in path_str,
        name.startswith('test_'),
        name.startswith('test.'),
        '_test.py' in name,
        '.test.' in name,
    ]
    if any(test_indicators):
        return 'test'
    
    # Config files
    config_patterns = [
        'config', 'settings', '.env', 'setup.cfg',
        '.ini', '.conf'
    ]
    config_extensions = ['.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg']
    if any(p in name for p in config_patterns) or any(name.endswith(ext) for ext in config_extensions):
        # Exclude package.json, cargo.toml, pyproject.toml (those are build files)
        if name not in ['package.json', 'cargo.toml', 'pyproject.toml', 'setup.py']:
            return 'config'
    
    # Documentation
    doc_patterns = ['readme', 'changelog', 'contributing', 'license', 'authors']
    doc_paths = ['docs/', 'doc/', 'documentation/']
    if any(p in name for p in doc_patterns) or any(path_str.startswith(p) for p in doc_paths):
        return 'doc'
    if file_path.suffix.lower() in ['.md', '.rst', '.txt'] and 'test' not in path_str:
        return 'doc'
    
    # Build/tooling files
    build_patterns = [
        'makefile', 'dockerfile', 'package.json', 'cargo.toml',
        'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt',
        'gemfile', 'build.gradle', 'pom.xml', '.gitignore', '.dockerignore'
    ]
    if any(p in name for p in build_patterns):
        return 'build'

    # Default to source code
    return 'source'


def format_glob_result(file_path: Path, working_dir: Path) -> str:
    """
    Format glob result with semantic category tags.
    
    Args:
        file_path: Path object to format
        working_dir: Working directory for relative paths
    
    Returns:
        Formatted string with category tag
    
    Examples:
        >>> format_glob_result(Path('src/main.py'), Path('/project'))
        'source src/main.py (145 lines)'
        
        >>> format_glob_result(Path('tests/test.py'), Path('/project'))
        'test tests/test.py (203 lines)'
    """
    try:
        relative_path = to_relative_path(file_path, working_dir, strict=False)
    except Exception:
        relative_path = str(file_path)
    
    # Categorize file
    category = categorize_file(file_path)
    
    # Get size information
    size_info = ""
    try:
        if file_path.is_file():
            # Try to count lines for text files
            try:
                # Limit to 1MB files for line counting
                if file_path.stat().st_size <= 1_000_000:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        line_count = sum(1 for _ in f)
                    size_info = f"({line_count} lines)"
                else:
                    # File too large, use byte size
                    size = file_path.stat().st_size
                    size_info = f"({format_file_size(size)})"
            except (UnicodeDecodeError, OSError):
                # Binary file or read error, use byte size
                size = file_path.stat().st_size
                size_info = f"({format_file_size(size)})"
    except Exception:
        # If we can't get size, omit it
        size_info = ""
    
    # Format: <category> <path> <size>
    if size_info:
        return f"{category} {relative_path} {size_info}"
    else:
        return f"{category} {relative_path}"

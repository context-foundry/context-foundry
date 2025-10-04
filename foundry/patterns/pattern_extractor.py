#!/usr/bin/env python3
"""
Pattern Extractor
Automatically extract reusable patterns from successful builds.
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional

from .pattern_manager import PatternLibrary


class PatternExtractor:
    """Extract patterns from completed sessions."""

    def __init__(self, pattern_library: PatternLibrary, config: Optional[Dict] = None):
        """Initialize pattern extractor.

        Args:
            pattern_library: PatternLibrary instance
            config: Optional configuration dictionary
        """
        self.library = pattern_library
        self.config = config or self._default_config()

    def _default_config(self) -> Dict:
        """Default extraction configuration."""
        return {
            'min_complexity': 3,
            'min_lines': 5,
            'max_similarity': 0.9,
            'languages': ['python'],
            'frameworks': ['fastapi', 'flask', 'django']
        }

    def extract_from_session(self, session_dir: Path) -> int:
        """Extract patterns from completed session.

        Args:
            session_dir: Path to session directory

        Returns:
            Number of patterns extracted
        """
        patterns_found = []

        # Find all code files
        code_files = self._discover_code_files(session_dir)

        # Parse and analyze each file
        for file_path in code_files:
            if file_path.suffix == '.py':
                patterns = self._extract_python_patterns(file_path)
                patterns_found.extend(patterns)

        # Extract test patterns
        test_files = self._discover_test_files(session_dir)
        for file_path in test_files:
            test_patterns = self._extract_test_patterns(file_path)
            patterns_found.extend(test_patterns)

        # Store unique patterns
        stored = 0
        for pattern in patterns_found:
            # Check if similar pattern exists
            similar = self.library.search_patterns(
                pattern['code'],
                limit=1,
                min_relevance=self.config['max_similarity']
            )

            # Only store if not too similar to existing pattern
            if not similar or similar[0][3] < self.config['max_similarity']:
                self.library.extract_pattern(pattern['code'], pattern)
                stored += 1

        return stored

    def _discover_code_files(self, session_dir: Path) -> List[Path]:
        """Discover code files in session directory.

        Args:
            session_dir: Path to session directory

        Returns:
            List of code file paths
        """
        code_files = []

        # Python files
        if 'python' in self.config['languages']:
            code_files.extend(session_dir.rglob("*.py"))

        # JavaScript/TypeScript files
        if 'javascript' in self.config['languages']:
            code_files.extend(session_dir.rglob("*.js"))
            code_files.extend(session_dir.rglob("*.ts"))

        # Filter out test files and __init__.py
        code_files = [
            f for f in code_files
            if not f.name.startswith('test_')
            and f.name != '__init__.py'
            and 'test' not in f.parts
        ]

        return code_files

    def _discover_test_files(self, session_dir: Path) -> List[Path]:
        """Discover test files in session directory.

        Args:
            session_dir: Path to session directory

        Returns:
            List of test file paths
        """
        test_files = []
        test_files.extend(session_dir.rglob("test_*.py"))
        test_files.extend(session_dir.rglob("*_test.py"))

        return test_files

    def _extract_python_patterns(self, file_path: Path) -> List[Dict]:
        """Extract patterns from Python file using AST.

        Args:
            file_path: Path to Python file

        Returns:
            List of pattern dictionaries
        """
        try:
            with open(file_path) as f:
                source = f.read()
                tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return []

        patterns = []

        for node in ast.walk(tree):
            # Extract class definitions
            if isinstance(node, ast.ClassDef):
                pattern = self._extract_class_pattern(node, source, file_path)
                if pattern:
                    patterns.append(pattern)

            # Extract reusable functions
            if isinstance(node, ast.FunctionDef):
                pattern = self._extract_function_pattern(node, source, file_path)
                if pattern:
                    patterns.append(pattern)

        return patterns

    def _extract_class_pattern(self, node: ast.ClassDef, source: str, file_path: Path) -> Optional[Dict]:
        """Extract class pattern from AST node.

        Args:
            node: AST ClassDef node
            source: Full source code
            file_path: Source file path

        Returns:
            Pattern dictionary or None
        """
        # Get source code for this class
        try:
            code = ast.get_source_segment(source, node)
        except Exception:
            return None

        if not code:
            return None

        # Check minimum lines
        if len(code.split('\n')) < self.config['min_lines']:
            return None

        # Extract docstring
        docstring = ast.get_docstring(node) or f"Class: {node.name}"

        return {
            'code': code,
            'description': docstring,
            'tags': ['class', 'python', node.name.lower()],
            'language': 'python',
            'framework': self._detect_framework(source)
        }

    def _extract_function_pattern(self, node: ast.FunctionDef, source: str, file_path: Path) -> Optional[Dict]:
        """Extract function pattern from AST node.

        Args:
            node: AST FunctionDef node
            source: Full source code
            file_path: Source file path

        Returns:
            Pattern dictionary or None
        """
        # Skip private/test functions
        if node.name.startswith('_') or node.name.startswith('test_'):
            return None

        # Check complexity
        complexity = self._calculate_complexity(node)
        if complexity < self.config['min_complexity']:
            return None

        # Get source code
        try:
            code = ast.get_source_segment(source, node)
        except Exception:
            return None

        if not code:
            return None

        # Check minimum lines
        if len(code.split('\n')) < self.config['min_lines']:
            return None

        # Extract docstring
        docstring = ast.get_docstring(node) or f"Function: {node.name}"

        return {
            'code': code,
            'description': docstring,
            'tags': ['function', 'python', node.name.lower()],
            'language': 'python',
            'framework': self._detect_framework(source)
        }

    def _extract_test_patterns(self, file_path: Path) -> List[Dict]:
        """Extract successful test patterns.

        Args:
            file_path: Path to test file

        Returns:
            List of pattern dictionaries
        """
        try:
            with open(file_path) as f:
                source = f.read()
                tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return []

        patterns = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                try:
                    code = ast.get_source_segment(source, node)
                    if code and len(code.split('\n')) >= self.config['min_lines']:
                        docstring = ast.get_docstring(node) or f"Test: {node.name}"
                        patterns.append({
                            'code': code,
                            'description': docstring,
                            'tags': ['test', 'pytest', 'python'],
                            'language': 'python',
                            'framework': self._detect_framework(source)
                        })
                except Exception:
                    continue

        return patterns

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of function.

        Args:
            node: AST FunctionDef node

        Returns:
            Complexity score
        """
        complexity = 1

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _detect_framework(self, source: str) -> str:
        """Detect framework from source code.

        Args:
            source: Source code

        Returns:
            Framework name or empty string
        """
        # Check imports for common frameworks
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ""

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, 'module', None)
                if not module and isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                    module = names[0] if names else ""

                if module:
                    module_lower = module.lower()
                    for framework in self.config['frameworks']:
                        if framework in module_lower:
                            return framework

        return ""


def main():
    """CLI for pattern extraction."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract patterns from session")
    parser.add_argument("--session", required=True, help="Session directory path")
    parser.add_argument("--db", default="foundry/patterns/patterns.db", help="Database path")

    args = parser.parse_args()

    session_dir = Path(args.session)
    if not session_dir.exists():
        print(f"❌ Session directory not found: {session_dir}")
        return 1

    print(f"🔍 Extracting patterns from: {session_dir}")

    lib = PatternLibrary(db_path=args.db)
    extractor = PatternExtractor(lib)

    count = extractor.extract_from_session(session_dir)

    print(f"✅ Extracted {count} patterns")

    # Show stats
    stats = lib.get_pattern_stats()
    print(f"\n📊 Library stats:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  By language: {stats['by_language']}")

    lib.close()
    return 0


if __name__ == "__main__":
    exit(main())

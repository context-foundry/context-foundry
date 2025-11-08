#!/usr/bin/env python3
"""
Scout Agent - Autonomous code analyzer for Context Foundry Evolution System

Scans codebase to discover:
- Security vulnerabilities
- Performance bottlenecks
- Missing tests
- Best practice violations
- Outdated dependencies
- Architectural debt
"""

import subprocess
import re
from pathlib import Path
from typing import List, Dict
import json


class Finding:
    """Represents a discovered issue or enhancement"""

    def __init__(self,
                 title: str,
                 finding_type: str,  # 'bug', 'security', 'performance', 'enhancement', 'debt'
                 priority: str,  # 'P0', 'P1', 'P2', 'P3', 'P4'
                 category: List[str],
                 description: str,
                 file_path: str = None,
                 line_number: int = None,
                 evidence: str = None,
                 effort: str = 'medium'):  # 'small', 'medium', 'large'

        self.title = title
        self.finding_type = finding_type
        self.priority = priority
        self.category = category
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.evidence = evidence
        self.effort = effort
        self.research = None  # Will be populated by research phase
        self.architectural_analysis = None  # Will be populated by architect if needed

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'type': self.finding_type,
            'priority': self.priority,
            'category': self.category,
            'description': self.description,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'evidence': self.evidence,
            'effort': self.effort,
            'research': self.research,
            'architectural_analysis': self.architectural_analysis
        }


class ScoutAgent:
    """
    Autonomous code analysis agent

    Philosophy: Simple heuristics + pattern matching = 90% of issues found
    Complex ML = 10% improvement at 1000x cost
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.findings: List[Finding] = []

    def scan(self) -> List[Finding]:
        """Run all scans and return findings"""

        print("🔍 Scout Agent starting autonomous scan...")
        print()

        # Run all analysis passes
        self._scan_missing_tests()
        self._scan_security_patterns()
        self._scan_performance_issues()
        self._scan_error_handling()
        self._scan_dependencies()
        self._scan_code_quality()
        self._scan_architectural_debt()

        print(f"✅ Scout found {len(self.findings)} issues")
        print()

        # Deduplicate and prioritize
        self._deduplicate()
        self._sort_by_priority()

        return self.findings

    def _scan_missing_tests(self):
        """Find files without test coverage"""

        print("  📋 Scanning for missing tests...")

        # Find all Python files
        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            # Skip test files themselves
            if 'test_' in py_file.name or py_file.name.startswith('test'):
                continue

            # Skip __init__.py
            if py_file.name == '__init__.py':
                continue

            # Check if corresponding test exists
            test_file = self._get_test_file_path(py_file)

            if not test_file.exists():
                # Check if file has meaningful code (>20 lines, has functions)
                if self._has_testable_code(py_file):
                    self.findings.append(Finding(
                        title=f"Add tests for {py_file.relative_to(self.project_root)}",
                        finding_type='enhancement',
                        priority='P2',
                        category=['testing', 'quality'],
                        description=f"No test coverage found for {py_file.name}. File contains testable functions but lacks unit tests.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='medium'
                    ))

    def _scan_security_patterns(self):
        """Detect common security anti-patterns"""

        print("  🔒 Scanning for security vulnerabilities...")

        py_files = list(self.project_root.glob("**/*.py"))

        security_patterns = [
            (r'eval\s*\(', 'Dangerous use of eval() - code injection risk'),
            (r'exec\s*\(', 'Dangerous use of exec() - code injection risk'),
            (r'pickle\.loads?\s*\(', 'Unsafe pickle usage - arbitrary code execution risk'),
            (r'subprocess\.(call|run|Popen).*shell\s*=\s*True', 'Shell injection risk with shell=True'),
            (r'os\.system\s*\(', 'Command injection risk with os.system()'),
            (r'\.format\([^)]*\%', 'SQL injection risk - use parameterized queries'),
        ]

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                for pattern, warning in security_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1

                        # Skip false positives
                        should_skip = False

                        # Get the full line for context checking
                        if 0 < line_num <= len(lines):
                            full_line = lines[line_num - 1].strip()

                            # Skip false positives: comments and string literals in pattern definitions
                            if full_line.startswith('#'):
                                should_skip = True
                            elif full_line.startswith('"""') or full_line.startswith("'''"):
                                should_skip = True
                            # Skip if it's in a regex pattern string (common in security scanners)
                            # This includes patterns like: (r'os\.system\s*\(', 'description')
                            elif full_line.startswith('(') and ("r'" in full_line or 'r"' in full_line):
                                should_skip = True
                            # Skip documentation examples showing unsafe patterns (lines with # ❌ UNSAFE)
                            elif '# ❌ UNSAFE' in full_line or '# UNSAFE' in full_line:
                                should_skip = True

                        if should_skip:
                            continue

                        self.findings.append(Finding(
                            title=f"Security: {warning} in {py_file.name}",
                            finding_type='security',
                            priority='P0',  # Security is always high priority
                            category=['security', 'vulnerability'],
                            description=f"{warning}\n\nFound at line {line_num} in {py_file.relative_to(self.project_root)}",
                            file_path=str(py_file.relative_to(self.project_root)),
                            line_number=line_num,
                            evidence=match.group(0),
                            effort='small'
                        ))
            except:
                pass

    def _scan_performance_issues(self):
        """Detect performance anti-patterns"""

        print("  ⚡ Scanning for performance issues...")

        # Check database usage
        db_files = list(self.project_root.glob("**/task_queue.py"))

        for db_file in db_files:
            try:
                content = db_file.read_text()

                # Check for missing indexes
                if 'CREATE TABLE' in content and 'CREATE INDEX' not in content:
                    self.findings.append(Finding(
                        title=f"Performance: Missing database indexes in {db_file.name}",
                        finding_type='performance',
                        priority='P2',
                        category=['performance', 'database'],
                        description="Database tables created without indexes. This will cause slow queries as data grows.",
                        file_path=str(db_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Check for N+1 query patterns
                if content.count('execute(') > 10:
                    self.findings.append(Finding(
                        title=f"Performance: Potential N+1 query pattern in {db_file.name}",
                        finding_type='performance',
                        priority='P3',
                        category=['performance', 'database'],
                        description="Multiple database execute() calls detected. Consider batch operations or joins to reduce query count.",
                        file_path=str(db_file.relative_to(self.project_root)),
                        effort='medium'
                    ))
            except:
                pass

    def _scan_error_handling(self):
        """Find missing error handling"""

        print("  ⚠️  Scanning for error handling gaps...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for functions without try/except
                has_functions = 'def ' in content
                has_try_except = 'try:' in content

                # Count subprocess calls without error handling
                subprocess_calls = len(re.findall(r'subprocess\.(run|call|Popen)', content))
                try_blocks = len(re.findall(r'try:', content))

                if subprocess_calls > try_blocks:
                    self.findings.append(Finding(
                        title=f"Reliability: Add error handling for subprocess calls in {py_file.name}",
                        finding_type='bug',
                        priority='P2',
                        category=['reliability', 'error-handling'],
                        description=f"Found {subprocess_calls} subprocess calls but only {try_blocks} try/except blocks. Subprocess failures will crash the program.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))
            except:
                pass

    def _scan_dependencies(self):
        """Check for outdated or vulnerable dependencies"""

        print("  📦 Scanning dependencies...")

        # Check if requirements.txt exists
        req_file = self.project_root / "requirements.txt"

        if req_file.exists():
            try:
                # Run pip-audit if available (would need to be installed)
                # For now, just check for old Python version requirement
                content = req_file.read_text()

                # Simple heuristic: check for unpinned versions
                unpinned = []
                for line in content.splitlines():
                    if line.strip() and not line.startswith('#'):
                        if '==' not in line and '>=' not in line:
                            unpinned.append(line.strip())

                if unpinned:
                    self.findings.append(Finding(
                        title="Dependencies: Pin package versions for reproducibility",
                        finding_type='enhancement',
                        priority='P3',
                        category=['dependencies', 'reliability'],
                        description=f"Found {len(unpinned)} unpinned dependencies: {', '.join(unpinned[:3])}. Pin versions to ensure reproducible builds.",
                        file_path="requirements.txt",
                        effort='small'
                    ))
            except:
                pass

    def _scan_code_quality(self):
        """Detect code quality issues"""

        print("  ✨ Scanning code quality...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Check for very long files (>500 lines)
                if len(lines) > 500:
                    self.findings.append(Finding(
                        title=f"Code Quality: Refactor large file {py_file.name} ({len(lines)} lines)",
                        finding_type='debt',
                        priority='P4',
                        category=['code-quality', 'maintainability'],
                        description=f"File has {len(lines)} lines. Consider breaking into smaller, focused modules for better maintainability.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='large'
                    ))

                # Check for missing docstrings
                func_count = content.count('def ')
                docstring_count = content.count('"""')

                if func_count > 3 and docstring_count < func_count * 0.3:
                    self.findings.append(Finding(
                        title=f"Documentation: Add docstrings to {py_file.name}",
                        finding_type='enhancement',
                        priority='P4',
                        category=['documentation', 'maintainability'],
                        description=f"Only {docstring_count}/{func_count} functions have docstrings. Add documentation for better maintainability.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))
            except:
                pass

    def _scan_architectural_debt(self):
        """Identify architectural issues that need architect input"""

        print("  🏗️  Scanning for architectural debt...")

        # Check for SQLite usage in high-concurrency scenarios
        db_files = list(self.project_root.glob("**/task_queue.py"))

        for db_file in db_files:
            try:
                content = db_file.read_text()

                if 'sqlite3' in content and 'check_same_thread=False' in content:
                    finding = Finding(
                        title="Architecture: Evaluate database alternatives to SQLite",
                        finding_type='enhancement',
                        priority='P2',
                        category=['architecture', 'performance', 'scalability'],
                        description="SQLite is used with threading disabled (check_same_thread=False). This indicates concurrency concerns. Consider PostgreSQL or Supabase for better concurrent access.",
                        file_path=str(db_file.relative_to(self.project_root)),
                        effort='large'
                    )
                    # Mark for architect review
                    finding.needs_architect = True
                    self.findings.append(finding)
            except:
                pass

    def _get_test_file_path(self, source_file: Path) -> Path:
        """Get expected test file path for a source file"""
        test_name = f"test_{source_file.stem}.py"
        return self.project_root / "tests" / test_name

    def _has_testable_code(self, py_file: Path) -> bool:
        """Check if file has code worth testing"""
        try:
            content = py_file.read_text()

            # Must have at least one function
            if 'def ' not in content:
                return False

            # Must have >20 lines
            if len(content.splitlines()) < 20:
                return False

            return True
        except:
            return False

    def _deduplicate(self):
        """Remove duplicate findings"""
        seen = set()
        unique = []

        for finding in self.findings:
            key = (finding.title, finding.file_path)
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        self.findings = unique

    def _sort_by_priority(self):
        """Sort findings by priority (P0 > P1 > P2 > P3 > P4)"""
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4}
        self.findings.sort(key=lambda f: priority_order.get(f.priority, 5))


def main():
    """CLI entry point for testing"""
    import sys

    project_root = Path(__file__).parent.parent.parent.parent

    scout = ScoutAgent(project_root)
    findings = scout.scan()

    print()
    print(f"📊 SUMMARY")
    print("=" * 80)
    print()

    for finding in findings[:10]:  # Show top 10
        print(f"{finding.priority} | {finding.finding_type.upper()}: {finding.title}")
        print(f"   {finding.description[:100]}")
        print()


if __name__ == '__main__':
    main()

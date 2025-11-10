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

    def __init__(
        self,
        title: str,
        finding_type: str,  # 'bug', 'security', 'performance', 'enhancement', 'debt'
        priority: str,  # 'P0', 'P1', 'P2', 'P3', 'P4'
        category: List[str],
        description: str,
        file_path: str = None,
        line_number: int = None,
        evidence: str = None,
        effort: str = "medium",
    ):  # 'small', 'medium', 'large'
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
            "title": self.title,
            "type": self.finding_type,
            "priority": self.priority,
            "category": self.category,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "effort": self.effort,
            "research": self.research,
            "architectural_analysis": self.architectural_analysis,
        }


class ScoutAgent:
    """
    Autonomous code analysis agent

    Philosophy: Simple heuristics + pattern matching = 90% of issues found
    Complex ML = 10% improvement at 1000x cost
    """

    TEST_PATH_KEYWORDS = {
        "test",
        "tests",
        "__tests__",
        "testdata",
        "test_data",
        "fixtures",
        "fixture",
        "samples",
        "sample_data",
        "mocks",
        "stubs",
        "snapshots",
    }

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.findings: List[Finding] = []

    def scan(self) -> List[Finding]:
        """Run all scans and return findings"""

        print("🔍 Scout Agent starting autonomous scan...")
        print()

        # Run all analysis passes (original scanners)
        self._scan_missing_tests()
        self._scan_security_patterns()
        self._scan_performance_issues()
        self._scan_error_handling()
        self._scan_dependencies()
        self._scan_code_quality()
        self._scan_architectural_debt()

        # Run new balanced opportunity scanners
        self._scan_feature_opportunities()
        self._scan_api_enhancements()
        self._scan_developer_experience()
        self._scan_modern_language_features()
        self._scan_observability()
        self._scan_user_experience()
        self._scan_configuration()
        self._scan_extensibility()

        print(f"✅ Scout found {len(self.findings)} issues")
        print()

        # Deduplicate and prioritize
        self._deduplicate()
        self._sort_by_priority()

        # AI-powered multi-perspective filtering
        print("🤖 Analyzing findings through AI expert lenses...")
        prioritized_findings = self._ai_analyze_findings(self.findings)

        return prioritized_findings

    def _scan_missing_tests(self):
        """Find files without test coverage"""

        print("  📋 Scanning for missing tests...")

        # Find all Python files
        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            # Skip test files themselves
            if self._is_test_path(py_file):
                continue

            # Skip __init__.py
            if py_file.name == "__init__.py":
                continue

            # Check if corresponding test exists
            test_file = self._get_test_file_path(py_file)

            if not test_file.exists():
                # Check if file has meaningful code (>20 lines, has functions)
                if self._has_testable_code(py_file):
                    self.findings.append(
                        Finding(
                            title=f"Add tests for {py_file.relative_to(self.project_root)}",
                            finding_type="enhancement",
                            priority="P2",
                            category=["testing", "quality"],
                            description=f"No test coverage found for {py_file.name}. File contains testable functions but lacks unit tests.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )

    def _scan_security_patterns(self):
        """Detect common security anti-patterns"""

        print("  🔒 Scanning for security vulnerabilities...")

        # Get all Python files but exclude test files (which contain intentional bad code for testing)
        all_py_files = list(self.project_root.glob("**/*.py"))
        py_files = [f for f in all_py_files if not self._is_test_path(f)]

        security_patterns = [
            (r"eval\s*\(", "Dangerous use of eval() - code injection risk"),
            (r"exec\s*\(", "Dangerous use of exec() - code injection risk"),
            (
                r"pickle\.loads?\s*\(",
                "Unsafe pickle usage - arbitrary code execution risk",
            ),
            (
                r"subprocess\.(call|run|Popen).*shell\s*=\s*True",
                "Shell injection risk with shell=True",
            ),
            (r"os\.system\s*\(", "Command injection risk with os.system()"),
            (r"\.format\([^)]*\%", "SQL injection risk - use parameterized queries"),
        ]

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                for pattern, warning in security_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[: match.start()].count("\n") + 1

                        # Skip false positives
                        should_skip = False

                        # Get the full line for context checking
                        if 0 < line_num <= len(lines):
                            full_line = lines[line_num - 1].strip()

                            # Skip false positives: comments and string literals in pattern definitions
                            if full_line.startswith("#"):
                                should_skip = True
                            elif full_line.startswith('"""') or full_line.startswith(
                                "'''"
                            ):
                                should_skip = True
                            # Skip if it's in a regex pattern string (common in security scanners)
                            # This includes patterns like: (r'os\.system\s*\(', 'description')
                            elif full_line.startswith("(") and (
                                "r'" in full_line or 'r"' in full_line
                            ):
                                should_skip = True
                            # Skip documentation examples showing unsafe patterns (lines with # ❌ UNSAFE)
                            elif "# ❌ UNSAFE" in full_line or "# UNSAFE" in full_line:
                                should_skip = True

                        if should_skip:
                            continue

                        self.findings.append(
                            Finding(
                                title=f"Security: {warning} in {py_file.name}",
                                finding_type="security",
                                priority="P0",  # Security is always high priority
                                category=["security", "vulnerability"],
                                description=f"{warning}\n\nFound at line {line_num} in {py_file.relative_to(self.project_root)}",
                                file_path=str(py_file.relative_to(self.project_root)),
                                line_number=line_num,
                                evidence=match.group(0),
                                effort="small",
                            )
                        )
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
                if "CREATE TABLE" in content and "CREATE INDEX" not in content:
                    self.findings.append(
                        Finding(
                            title=f"Performance: Missing database indexes in {db_file.name}",
                            finding_type="performance",
                            priority="P2",
                            category=["performance", "database"],
                            description="Database tables created without indexes. This will cause slow queries as data grows.",
                            file_path=str(db_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for N+1 query patterns
                if content.count("execute(") > 10:
                    self.findings.append(
                        Finding(
                            title=f"Performance: Potential N+1 query pattern in {db_file.name}",
                            finding_type="performance",
                            priority="P3",
                            category=["performance", "database"],
                            description="Multiple database execute() calls detected. Consider batch operations or joins to reduce query count.",
                            file_path=str(db_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )
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
                has_functions = "def " in content
                has_try_except = "try:" in content

                # Count subprocess calls without error handling
                subprocess_calls = len(
                    re.findall(r"subprocess\.(run|call|Popen)", content)
                )
                try_blocks = len(re.findall(r"try:", content))

                if subprocess_calls > try_blocks:
                    self.findings.append(
                        Finding(
                            title=f"Reliability: Add error handling for subprocess calls in {py_file.name}",
                            finding_type="bug",
                            priority="P2",
                            category=["reliability", "error-handling"],
                            description=f"Found {subprocess_calls} subprocess calls but only {try_blocks} try/except blocks. Subprocess failures will crash the program.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
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
                    if line.strip() and not line.startswith("#"):
                        if "==" not in line and ">=" not in line:
                            unpinned.append(line.strip())

                if unpinned:
                    self.findings.append(
                        Finding(
                            title="Dependencies: Pin package versions for reproducibility",
                            finding_type="enhancement",
                            priority="P3",
                            category=["dependencies", "reliability"],
                            description=f"Found {len(unpinned)} unpinned dependencies: {', '.join(unpinned[:3])}. Pin versions to ensure reproducible builds.",
                            file_path="requirements.txt",
                            effort="small",
                        )
                    )
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
                    self.findings.append(
                        Finding(
                            title=f"Code Quality: Refactor large file {py_file.name} ({len(lines)} lines)",
                            finding_type="debt",
                            priority="P4",
                            category=["code-quality", "maintainability"],
                            description=f"File has {len(lines)} lines. Consider breaking into smaller, focused modules for better maintainability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="large",
                        )
                    )

                # Check for missing docstrings
                func_count = content.count("def ")
                docstring_count = content.count('"""')

                if func_count > 3 and docstring_count < func_count * 0.3:
                    self.findings.append(
                        Finding(
                            title=f"Documentation: Add docstrings to {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["documentation", "maintainability"],
                            description=f"Only {docstring_count}/{func_count} functions have docstrings. Add documentation for better maintainability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
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

                if "sqlite3" in content and "check_same_thread=False" in content:
                    finding = Finding(
                        title="Architecture: Evaluate database alternatives to SQLite",
                        finding_type="enhancement",
                        priority="P2",
                        category=["architecture", "performance", "scalability"],
                        description="SQLite is used with threading disabled (check_same_thread=False). This indicates concurrency concerns. Consider PostgreSQL or Supabase for better concurrent access.",
                        file_path=str(db_file.relative_to(self.project_root)),
                        effort="large",
                    )
                    # Mark for architect review
                    finding.needs_architect = True
                    self.findings.append(finding)
            except:
                pass

    def _scan_feature_opportunities(self):
        """Find opportunities for new features (commented code, TODOs, stubs)"""

        print("  🌱 Scanning for feature opportunities...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                for i, line in enumerate(lines, 1):
                    line_stripped = line.strip()

                    # Find TODO comments for features
                    if "TODO" in line_stripped and any(
                        keyword in line_stripped.lower()
                        for keyword in ["add", "implement", "feature", "support"]
                    ):
                        self.findings.append(
                            Finding(
                                title=f"Feature: {line_stripped.replace('# TODO:', '').replace('# TODO', '').strip()[:80]}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["feature", "opportunity"],
                                description=f"TODO comment suggests new feature: {line_stripped}",
                                file_path=str(py_file.relative_to(self.project_root)),
                                line_number=i,
                                evidence=line_stripped,
                                effort="medium",
                            )
                        )

                    # Find stub methods (pass or raise NotImplementedError)
                    if "def " in line:
                        # Check next few lines for stub indicators
                        func_name = re.search(r"def\s+(\w+)", line)
                        if func_name and i < len(lines):
                            next_lines = "\n".join(lines[i : min(i + 5, len(lines))])
                            if (
                                "pass" in next_lines
                                and "NotImplementedError" not in next_lines
                            ):
                                if not any(
                                    x in next_lines
                                    for x in ["try:", "except:", "finally:"]
                                ):
                                    self.findings.append(
                                        Finding(
                                            title=f"Feature: Implement stub method {func_name.group(1)} in {py_file.name}",
                                            finding_type="enhancement",
                                            priority="P3",
                                            category=["feature", "stub"],
                                            description=f"Method {func_name.group(1)} is a stub (only contains 'pass'). Consider implementing or removing.",
                                            file_path=str(
                                                py_file.relative_to(self.project_root)
                                            ),
                                            line_number=i,
                                            effort="medium",
                                        )
                                    )
                            elif "NotImplementedError" in next_lines:
                                self.findings.append(
                                    Finding(
                                        title=f"Feature: Implement {func_name.group(1)} in {py_file.name}",
                                        finding_type="enhancement",
                                        priority="P3",
                                        category=["feature", "stub"],
                                        description=f"Method {func_name.group(1)} raises NotImplementedError. Feature is planned but not implemented.",
                                        file_path=str(
                                            py_file.relative_to(self.project_root)
                                        ),
                                        line_number=i,
                                        effort="medium",
                                    )
                                )

                # Find large commented-out code blocks (potential features)
                commented_blocks = re.findall(r"(#.*\n){5,}", content)
                if commented_blocks:
                    self.findings.append(
                        Finding(
                            title=f"Feature: Review commented code in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["feature", "cleanup"],
                            description=f"Found {len(commented_blocks)} large commented-out code blocks. These may be features waiting to be implemented or dead code to remove.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
            except:
                pass

    def _scan_api_enhancements(self):
        """Find opportunities to improve API completeness"""

        print("  🔌 Scanning for API enhancements...")

        # Look for API/endpoint files
        api_files = (
            list(self.project_root.glob("**/api*.py"))
            + list(self.project_root.glob("**/routes*.py"))
            + list(self.project_root.glob("**/endpoints*.py"))
        )

        for api_file in api_files:
            try:
                content = api_file.read_text()

                # Check for missing pagination on list endpoints
                if "def list" in content.lower() or "get_all" in content.lower():
                    if (
                        "limit" not in content.lower()
                        and "offset" not in content.lower()
                        and "page" not in content.lower()
                    ):
                        self.findings.append(
                            Finding(
                                title=f"API: Add pagination to list endpoint in {api_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["api", "scalability"],
                                description="List endpoint doesn't implement pagination. This will cause performance issues with large datasets.",
                                file_path=str(api_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )

                # Check for incomplete CRUD operations
                has_get = bool(re.search(r"def\s+get", content, re.IGNORECASE))
                has_post = bool(
                    re.search(r"def\s+(post|create)", content, re.IGNORECASE)
                )
                has_put = bool(re.search(r"def\s+(put|update)", content, re.IGNORECASE))
                has_delete = bool(re.search(r"def\s+delete", content, re.IGNORECASE))

                crud_ops = {
                    "GET": has_get,
                    "POST": has_post,
                    "PUT": has_put,
                    "DELETE": has_delete,
                }
                missing_ops = [op for op, exists in crud_ops.items() if not exists]

                if len(missing_ops) > 0 and len(missing_ops) < 4:
                    self.findings.append(
                        Finding(
                            title=f"API: Complete CRUD operations in {api_file.name}",
                            finding_type="enhancement",
                            priority="P3",
                            category=["api", "completeness"],
                            description=f"API has partial CRUD implementation. Missing: {', '.join(missing_ops)}. Consider adding for completeness.",
                            file_path=str(api_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )

                # Check for missing rate limiting
                if "app.route" in content or "@router" in content:
                    if (
                        "rate_limit" not in content.lower()
                        and "ratelimit" not in content.lower()
                        and "throttle" not in content.lower()
                    ):
                        self.findings.append(
                            Finding(
                                title=f"API: Add rate limiting to {api_file.name}",
                                finding_type="enhancement",
                                priority="P2",
                                category=["api", "security", "reliability"],
                                description="API endpoints lack rate limiting. This leaves the service vulnerable to abuse and DoS attacks.",
                                file_path=str(api_file.relative_to(self.project_root)),
                                effort="medium",
                            )
                        )
            except:
                pass

    def _scan_developer_experience(self):
        """Find opportunities to improve code maintainability"""

        print("  👨‍💻 Scanning for developer experience improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Check for magic numbers
                magic_numbers = []
                for i, line in enumerate(lines, 1):
                    # Skip comments and strings
                    if "#" in line:
                        line = line[: line.index("#")]

                    # Find numeric literals that aren't 0, 1, -1
                    numbers = re.findall(r"\b([2-9]\d+)\b", line)
                    if numbers and "def " not in line:
                        magic_numbers.extend([(i, num) for num in numbers])

                if len(magic_numbers) > 5:
                    self.findings.append(
                        Finding(
                            title=f"DX: Replace magic numbers with named constants in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["dx", "maintainability"],
                            description=f"Found {len(magic_numbers)} magic numbers. Use named constants for better readability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for unclear variable names
                unclear_vars = []
                for match in re.finditer(
                    r"\b(x|y|z|tmp|temp|data|val|var|foo|bar)\s*=", content
                ):
                    line_num = content[: match.start()].count("\n") + 1
                    unclear_vars.append((line_num, match.group(1)))

                if len(unclear_vars) > 3:
                    self.findings.append(
                        Finding(
                            title=f"DX: Use descriptive variable names in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["dx", "readability"],
                            description=f"Found {len(unclear_vars)} unclear variable names (x, tmp, data, etc). Use descriptive names for better readability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for complex functions (>50 lines)
                func_pattern = re.compile(r"^( *)def\s+(\w+)", re.MULTILINE)
                func_matches = list(func_pattern.finditer(content))

                for i, match in enumerate(func_matches):
                    func_start = content[: match.start()].count("\n") + 1
                    func_indent = len(match.group(1))

                    # Find end of function (next function at same or lower indent, or EOF)
                    func_end = len(lines)
                    if i + 1 < len(func_matches):
                        next_indent = len(func_matches[i + 1].group(1))
                        if next_indent <= func_indent:
                            func_end = (
                                content[: func_matches[i + 1].start()].count("\n") + 1
                            )

                    func_length = func_end - func_start

                    if func_length > 50:
                        self.findings.append(
                            Finding(
                                title=f"DX: Refactor complex function {match.group(2)} in {py_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["dx", "maintainability"],
                                description=f"Function {match.group(2)} is {func_length} lines long. Consider breaking into smaller functions.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                line_number=func_start,
                                effort="medium",
                            )
                        )

                # Check for missing type hints (Python 3.5+)
                func_count = content.count("def ")
                type_hint_count = content.count(" -> ")

                if func_count > 5 and type_hint_count < func_count * 0.2:
                    self.findings.append(
                        Finding(
                            title=f"DX: Add type hints to {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["dx", "type-safety"],
                            description=f"Only {type_hint_count}/{func_count} functions have return type hints. Add type hints for better IDE support and error detection.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="medium",
                        )
                    )
            except:
                pass

    def _scan_modern_language_features(self):
        """Find opportunities to use modern Python features"""

        print("  🚀 Scanning for modern language feature opportunities...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for old-style string formatting
                old_format_count = len(re.findall(r"%[sd]", content))
                format_count = len(re.findall(r"\.format\(", content))
                fstring_count = len(re.findall(r'f["\']', content))

                if (old_format_count > 3 or format_count > 5) and fstring_count < (
                    old_format_count + format_count
                ) * 0.3:
                    self.findings.append(
                        Finding(
                            title=f"Modernize: Use f-strings in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["modernization", "readability"],
                            description="Found old-style string formatting (%s, .format()). Consider using f-strings for better readability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for dict() instead of dict literal
                dict_constructor = len(re.findall(r"\bdict\(\s*\w+\s*=", content))
                if dict_constructor > 3:
                    self.findings.append(
                        Finding(
                            title=f"Modernize: Use dict literals in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["modernization", "performance"],
                            description=f"Found {dict_constructor} dict() constructor calls. Use dict literals {{}} for better performance.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for potential dataclass usage (lots of __init__ boilerplate)
                if "__init__" in content and "self." in content:
                    init_assignments = len(re.findall(r"self\.\w+\s*=\s*\w+", content))
                    if init_assignments > 5 and "dataclass" not in content:
                        self.findings.append(
                            Finding(
                                title=f"Modernize: Consider using dataclass in {py_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["modernization", "boilerplate"],
                                description=f"Found class with {init_assignments} __init__ assignments. Consider using @dataclass to reduce boilerplate.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )

                # Check for missing context managers (open() without with)
                opens = re.findall(r"(\w+)\s*=\s*open\(", content)
                with_opens = re.findall(r"with\s+open\(", content)

                if len(opens) > len(with_opens):
                    self.findings.append(
                        Finding(
                            title=f"Modernize: Use context managers (with statement) in {py_file.name}",
                            finding_type="bug",
                            priority="P3",
                            category=["modernization", "reliability"],
                            description="Found open() calls without 'with' statement. Use context managers to ensure files are properly closed.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )
            except:
                pass

    def _scan_observability(self):
        """Find opportunities to add logging and monitoring"""

        print("  📊 Scanning for observability improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for error handlers that don't log
                except_blocks = re.findall(r"except\s+\w+.*?:", content)
                has_logging = (
                    "logging" in content or "logger" in content or "print" in content
                )

                if len(except_blocks) > 0 and not has_logging:
                    self.findings.append(
                        Finding(
                            title=f"Observability: Add logging to error handlers in {py_file.name}",
                            finding_type="enhancement",
                            priority="P3",
                            category=["observability", "debugging"],
                            description=f"Found {len(except_blocks)} exception handlers but no logging. Add logging for better debugging in production.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="small",
                        )
                    )

                # Check for long-running operations without progress tracking
                if "for " in content or "while " in content:
                    has_progress = "tqdm" in content or "progress" in content.lower()
                    has_subprocess = "subprocess" in content

                    if has_subprocess and not has_progress:
                        self.findings.append(
                            Finding(
                                title=f"Observability: Add progress tracking to {py_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["observability", "ux"],
                                description="Found long-running operations without progress tracking. Consider adding progress indicators for better user experience.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )

                # Check for missing function entry/exit logging in critical paths
                if py_file.name in [
                    "builder_agent.py",
                    "architect_agent.py",
                    "scout_agent.py",
                ]:
                    func_count = content.count("def ")
                    log_count = content.count("print(") + content.count("logger.")

                    if func_count > 5 and log_count < func_count:
                        self.findings.append(
                            Finding(
                                title=f"Observability: Add detailed logging to {py_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["observability", "debugging"],
                                description=f"Critical path file with {func_count} functions but only {log_count} log statements. Add more logging for better observability.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="medium",
                            )
                        )
            except:
                pass

    def _scan_user_experience(self):
        """Find opportunities to improve user-facing features"""

        print("  😊 Scanning for user experience improvements...")

        # Check CLI files
        cli_files = (
            list(self.project_root.glob("**/cli*.py"))
            + list(self.project_root.glob("**/main.py"))
            + [self.project_root / "foundry"]
        )

        for cli_file in cli_files:
            if not cli_file.exists():
                continue

            try:
                content = cli_file.read_text()

                # Check for missing --help text
                if "argparse" in content or "click" in content:
                    help_count = content.count("help=")
                    arg_count = content.count("add_argument") + content.count(
                        "@click.option"
                    )

                    if arg_count > 0 and help_count < arg_count * 0.5:
                        self.findings.append(
                            Finding(
                                title=f"UX: Add help text to CLI arguments in {cli_file.name}",
                                finding_type="enhancement",
                                priority="P4",
                                category=["ux", "documentation"],
                                description=f"Only {help_count}/{arg_count} CLI arguments have help text. Add --help documentation for better UX.",
                                file_path=str(cli_file.relative_to(self.project_root))
                                if cli_file.is_relative_to(self.project_root)
                                else cli_file.name,
                                effort="small",
                            )
                        )

                # Check for destructive operations without confirmation
                destructive_patterns = [r"delete", r"remove", r"drop", r"truncate"]
                for pattern in destructive_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        if "input(" not in content and "confirm" not in content.lower():
                            self.findings.append(
                                Finding(
                                    title=f"UX: Add confirmation prompts for destructive operations in {cli_file.name}",
                                    finding_type="enhancement",
                                    priority="P2",
                                    category=["ux", "safety"],
                                    description="Found destructive operations (delete/remove) without confirmation prompts. Add user confirmation to prevent accidents.",
                                    file_path=str(
                                        cli_file.relative_to(self.project_root)
                                    )
                                    if cli_file.is_relative_to(self.project_root)
                                    else cli_file.name,
                                    effort="small",
                                )
                            )
                            break

                # Check for missing error messages (silent failures)
                if "except" in content:
                    except_pass = len(re.findall(r"except.*:\s*pass", content))
                    if except_pass > 0:
                        self.findings.append(
                            Finding(
                                title=f"UX: Replace silent failures with error messages in {cli_file.name}",
                                finding_type="bug",
                                priority="P2",
                                category=["ux", "reliability"],
                                description=f"Found {except_pass} silent failure(s) (except: pass). Users won't know when operations fail.",
                                file_path=str(cli_file.relative_to(self.project_root))
                                if cli_file.is_relative_to(self.project_root)
                                else cli_file.name,
                                effort="small",
                            )
                        )
            except:
                pass

    def _scan_configuration(self):
        """Find opportunities to improve configuration management"""

        print("  ⚙️  Scanning for configuration improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for hardcoded values that should be env vars
                hardcoded_patterns = [
                    (r"https?://localhost:\d+", "URL"),
                    (
                        r'(api_key|password|secret)\s*=\s*["\'](?!env|get)[^"\']+["\']',
                        "Secret",
                    ),
                    (r"/tmp/[\w-]+", "Path"),
                    (r"timeout\s*=\s*\d+", "Timeout"),
                ]

                for pattern, config_type in hardcoded_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        # Don't flag if already using env vars
                        if "os.getenv" in content or "os.environ" in content:
                            continue

                        self.findings.append(
                            Finding(
                                title=f"Config: Move hardcoded {config_type.lower()} to environment variables in {py_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["config", "deployment"],
                                description=f"Found hardcoded {config_type.lower()}. Use environment variables for better configurability across environments.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )
                        break

                # Check for missing config validation
                if "os.getenv" in content or "os.environ" in content:
                    has_validation = (
                        "required" in content.lower()
                        or "assert" in content
                        or "raise" in content
                    )

                    if not has_validation:
                        self.findings.append(
                            Finding(
                                title=f"Config: Add validation for environment variables in {py_file.name}",
                                finding_type="enhancement",
                                priority="P3",
                                category=["config", "reliability"],
                                description="Environment variables are used but not validated. Add validation to fail fast with clear error messages.",
                                file_path=str(py_file.relative_to(self.project_root)),
                                effort="small",
                            )
                        )
            except:
                pass

        # Check for .env.example
        if (self.project_root / ".env").exists() and not (
            self.project_root / ".env.example"
        ).exists():
            self.findings.append(
                Finding(
                    title="Config: Add .env.example file",
                    finding_type="enhancement",
                    priority="P3",
                    category=["config", "documentation"],
                    description="Found .env file but no .env.example. Create an example file to document required environment variables.",
                    file_path=".env",
                    effort="small",
                )
            )

    def _scan_extensibility(self):
        """Find opportunities to make the codebase more extensible"""

        print("  🔌 Scanning for extensibility improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for classes that could be abstract base classes
                if "class " in content:
                    classes = re.findall(r"class\s+(\w+)", content)
                    has_abc = "ABC" in content or "abstractmethod" in content

                    # Look for class hierarchies (inheritance)
                    if len(classes) > 2 and not has_abc:
                        # Check if classes have common method names
                        methods = re.findall(r"def\s+(\w+)", content)
                        method_counts = {}
                        for method in methods:
                            method_counts[method] = method_counts.get(method, 0) + 1

                        repeated_methods = [
                            m for m, count in method_counts.items() if count > 2
                        ]

                        if repeated_methods:
                            self.findings.append(
                                Finding(
                                    title=f"Extensibility: Consider abstract base class in {py_file.name}",
                                    finding_type="enhancement",
                                    priority="P4",
                                    category=["extensibility", "architecture"],
                                    description=f"Found {len(classes)} classes with repeated method names ({', '.join(repeated_methods[:3])}). Consider using ABC for better extensibility.",
                                    file_path=str(
                                        py_file.relative_to(self.project_root)
                                    ),
                                    effort="medium",
                                )
                            )

                # Check for hardcoded logic that could be plugins
                if py_file.name in [
                    "scout_agent.py",
                    "builder_agent.py",
                    "architect_agent.py",
                ]:
                    scan_methods = len(re.findall(r"def\s+_scan_\w+", content))

                    if scan_methods > 5:
                        # Check if plugin system exists
                        has_plugin_system = (
                            "plugin" in content.lower() or "register" in content.lower()
                        )

                        if not has_plugin_system:
                            self.findings.append(
                                Finding(
                                    title=f"Extensibility: Add plugin system to {py_file.name}",
                                    finding_type="enhancement",
                                    priority="P3",
                                    category=["extensibility", "architecture"],
                                    description=f"Found {scan_methods} scan methods. Consider a plugin system to allow users to add custom scanners without modifying core code.",
                                    file_path=str(
                                        py_file.relative_to(self.project_root)
                                    ),
                                    effort="large",
                                )
                            )

                # Check for tightly coupled code
                import_count = len(
                    re.findall(r"^from\s+[\w.]+\s+import", content, re.MULTILINE)
                )
                if import_count > 15:
                    self.findings.append(
                        Finding(
                            title=f"Extensibility: Reduce tight coupling in {py_file.name}",
                            finding_type="enhancement",
                            priority="P4",
                            category=["extensibility", "maintainability"],
                            description=f"Found {import_count} imports. High coupling makes testing and reuse difficult. Consider dependency injection or interfaces.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort="large",
                        )
                    )
            except:
                pass

    def _get_test_file_path(self, source_file: Path) -> Path:
        """Get expected test file path for a source file"""
        test_name = f"test_{source_file.stem}.py"
        return self.project_root / "tests" / test_name

    def _is_test_path(self, path: Path) -> bool:
        """Return True if the path points to a test/fixture file that should be ignored"""

        try:
            relative_path = path.relative_to(self.project_root)
        except ValueError:
            relative_path = path

        parts = [part.lower() for part in relative_path.parts]
        filename = path.name.lower()

        if filename.startswith("test") or filename.endswith("_test.py") or filename.endswith("_tests.py"):
            return True

        for part in parts:
            if part.startswith("test"):
                return True
            if part in self.TEST_PATH_KEYWORDS:
                return True

        return False

    def _has_testable_code(self, py_file: Path) -> bool:
        """Check if file has code worth testing"""
        try:
            content = py_file.read_text()

            # Must have at least one function
            if "def " not in content:
                return False

            # Must have >20 lines
            if len(content.splitlines()) < 20:
                return False

            return True
        except:
            return False

    def _ai_analyze_findings(self, findings: List[Finding]) -> List[Finding]:
        """
        Use Claude CLI to analyze findings through multiple expert perspectives

        Returns filtered list of high-priority findings worthy of GitHub issues
        """
        if not findings:
            return []

        # Limit to top 30 findings to avoid overwhelming Claude
        findings_to_analyze = findings[:30]

        # Format findings as structured data for Claude
        findings_json = []
        for i, finding in enumerate(findings_to_analyze, 1):
            findings_json.append(
                {
                    "id": i,
                    "title": finding.title,
                    "type": finding.finding_type,
                    "priority": finding.priority,
                    "category": finding.category,
                    "description": finding.description,
                    "file": finding.file_path,
                    "line": finding.line_number,
                    "evidence": finding.evidence,
                    "effort": finding.effort,
                }
            )

        # Create the multi-perspective analysis prompt
        prompt = f"""You are analyzing {len(findings_to_analyze)} code findings from a static analysis tool for the Context Foundry project.

Your task: Evaluate each finding through 6 expert lenses and select the top 5-10 findings that should become GitHub issues.

## Expert Perspectives:

🔒 **Security Analyst**: Critical vulnerabilities, attack vectors, data exposure risks
⚙️ **DevOps Engineer**: Deployment risks, operational concerns, reliability issues
📊 **Functional Consultant**: User impact, business value, feature gaps
💼 **Business SME**: ROI, strategic alignment, competitive advantage
👨‍💻 **Developer**: Technical debt, maintainability, developer experience
🏗️ **Architect**: System design, scalability, architectural coherence

## Findings to Analyze:

```json
{json.dumps(findings_json, indent=2)}
```

## Instructions:

1. Analyze each finding through ALL 6 perspectives
2. Score each finding 0-10 for overall priority (considering all perspectives)
3. Select the top 5-10 findings that should become GitHub issues
4. For each selected finding, provide:
   - Overall priority score (0-10)
   - Which expert perspectives rated it highly (and why)
   - Recommended GitHub labels
   - Updated priority (P0-P4)

## Output Format:

Return ONLY valid JSON in this exact format:

```json
{{
  "prioritized_findings": [
    {{
      "id": 1,
      "score": 9,
      "expert_perspectives": {{
        "security": "Critical SQL injection risk - HIGH",
        "devops": "Could cause production outages - HIGH",
        "developer": "Easy fix, high impact - MEDIUM"
      }},
      "github_labels": ["security", "p0", "bug"],
      "priority": "P0",
      "reasoning": "Multi-perspective summary of why this is important"
    }}
  ]
}}
```

Return ONLY the JSON, no other text."""

        try:
            # Call Claude CLI with prompt via stdin
            result = subprocess.run(
                ["claude", "--print", "--output-format", "text"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                print(f"  ⚠️  Claude CLI failed: {result.stderr}")
                print(f"  Falling back to original {len(findings)} findings")
                return findings

            # Parse Claude's response
            response_text = result.stdout.strip()

            # Extract JSON from response (Claude might wrap it in markdown)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            analysis = json.loads(response_text)

            # Map AI-prioritized findings back to Finding objects
            prioritized = []
            for item in analysis.get("prioritized_findings", []):
                finding_id = item["id"] - 1  # Convert 1-indexed to 0-indexed
                if 0 <= finding_id < len(findings_to_analyze):
                    original_finding = findings_to_analyze[finding_id]

                    # Update finding with AI insights
                    original_finding.priority = item.get(
                        "priority", original_finding.priority
                    )
                    original_finding.research = {
                        "ai_score": item.get("score"),
                        "expert_perspectives": item.get("expert_perspectives", {}),
                        "reasoning": item.get("reasoning", ""),
                        "github_labels": item.get("github_labels", []),
                    }

                    prioritized.append(original_finding)

            print(
                f"  ✅ AI filtered {len(findings_to_analyze)} findings → {len(prioritized)} high-priority issues"
            )
            print("  📊 Top issues by expert consensus:")
            for i, finding in enumerate(prioritized[:5], 1):
                score = finding.research.get("ai_score", 0) if finding.research else 0
                print(
                    f"     {i}. [{finding.priority}] {finding.title[:60]} (score: {score}/10)"
                )

            return prioritized if prioritized else findings

        except subprocess.TimeoutExpired:
            print("  ⚠️  Claude CLI timed out")
            print(f"  Falling back to original {len(findings)} findings")
            return findings
        except json.JSONDecodeError as e:
            print(f"  ⚠️  Failed to parse Claude's JSON response: {e}")
            print(f"  Falling back to original {len(findings)} findings")
            return findings
        except Exception as e:
            print(f"  ⚠️  AI analysis failed: {e}")
            print(f"  Falling back to original {len(findings)} findings")
            return findings

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
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
        self.findings.sort(key=lambda f: priority_order.get(f.priority, 5))


def main():
    """CLI entry point for testing"""

    project_root = Path(__file__).parent.parent.parent.parent

    scout = ScoutAgent(project_root)
    findings = scout.scan()

    print()
    print("📊 SUMMARY")
    print("=" * 80)
    print()

    for finding in findings[:10]:  # Show top 10
        print(f"{finding.priority} | {finding.finding_type.upper()}: {finding.title}")
        print(f"   {finding.description[:100]}")
        print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Scout Agent - Autonomous code analyzer for Context Foundry Evolution System

Scans codebase to discover opportunities across multiple dimensions:

REACTIVE (Bug/Debt):
- Security vulnerabilities
- Performance bottlenecks
- Missing tests
- Best practice violations
- Outdated dependencies
- Architectural debt

PROACTIVE (Feature/Growth):
- Feature opportunities (TODOs, stubs, commented code)
- Developer experience improvements (type hints, docstrings, magic numbers)
- Modern language features (f-strings, pathlib, walrus operator)
- API enhancements (CRUD completeness, pagination, rate limiting)
- Observability gaps (logging, metrics, health checks)
- User experience issues (help text, error messages, progress bars)
- Configuration problems (hardcoded values, missing validation)
- Extensibility needs (tight coupling, missing interfaces)

This balanced approach ensures Scout generates a diverse backlog,
not just security fixes and bug reports!
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

        # Run all analysis passes (existing scanners)
        self._scan_missing_tests()
        self._scan_security_patterns()
        self._scan_performance_issues()
        self._scan_error_handling()
        self._scan_dependencies()
        self._scan_code_quality()
        self._scan_architectural_debt()

        # Phase 1: Quick Wins - Proactive Opportunity Scanners
        self._scan_feature_opportunities()
        self._scan_developer_experience()
        self._scan_modern_language_features()

        # Phase 2: High Value - Growth & Enhancement Scanners
        self._scan_api_enhancements()
        self._scan_observability()
        self._scan_user_experience()

        # Phase 3: Advanced - Strategic Improvement Scanners
        self._scan_configuration_issues()
        self._scan_extensibility()

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
                            # Check for raw strings containing escaped regex patterns
                            elif ("r'" in full_line or 'r"' in full_line) and '\\s*\\(' in full_line:
                                should_skip = True
                            # This includes patterns like: (r'os\.system\s*\(', 'description')
                            elif full_line.startswith('(') and ("r'" in full_line or 'r"' in full_line):
                                should_skip = True
                            # Skip documentation examples showing unsafe patterns (lines with # ❌ UNSAFE)
                            elif '# ❌ UNSAFE' in full_line or '# UNSAFE' in full_line:
                                should_skip = True
                            # Skip if it's part of a security_patterns definition (pattern tuples)
                            elif 'security_patterns' in content[:match.start()]:
                                # Check if we're within the security_patterns list definition
                                lines_before = content[:match.start()].splitlines()
                                # Look for security_patterns definition in recent lines
                                for prev_line in lines_before[-20:]:
                                    if 'security_patterns' in prev_line and '=' in prev_line:
                                        # Check if we're still in that list (no other assignment after it)
                                        after_patterns = content[match.start():]
                                        next_assignment = re.search(r'\n\s*\w+\s*=', after_patterns[:500])
                                        if not next_assignment or next_assignment.start() > 100:
                                            should_skip = True
                                            break

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

    # ==================== PHASE 1: QUICK WINS ====================

    def _scan_feature_opportunities(self):
        """Find TODOs, stub methods, commented code - quick feature wins"""

        print("  💡 Scanning for feature opportunities...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Find TODOs
                todos = []
                for i, line in enumerate(lines, 1):
                    if 'TODO' in line or 'FIXME' in line or 'XXX' in line:
                        todos.append((i, line.strip()))

                if todos:
                    # Group by file and create a single finding
                    todo_summary = '; '.join([f"L{num}: {txt[:50]}" for num, txt in todos[:3]])
                    self.findings.append(Finding(
                        title=f"Feature Opportunity: Implement {len(todos)} TODOs in {py_file.name}",
                        finding_type='enhancement',
                        priority='P3',
                        category=['feature', 'enhancement', 'technical-debt'],
                        description=f"Found {len(todos)} TODO/FIXME markers indicating incomplete features: {todo_summary}",
                        file_path=str(py_file.relative_to(self.project_root)),
                        line_number=todos[0][0],
                        effort='small' if len(todos) <= 3 else 'medium'
                    ))

                # Find stub methods (pass-only functions)
                stub_methods = re.findall(r'def\s+(\w+)\([^)]*\):[^\n]*\n\s+pass\s*(?:\n|$)', content)
                if stub_methods:
                    self.findings.append(Finding(
                        title=f"Feature Opportunity: Implement {len(stub_methods)} stub methods in {py_file.name}",
                        finding_type='enhancement',
                        priority='P3',
                        category=['feature', 'enhancement'],
                        description=f"Found {len(stub_methods)} stub methods (pass-only): {', '.join(stub_methods[:3])}. These indicate planned but unimplemented features.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='medium'
                    ))

                # Find large blocks of commented code (>5 consecutive lines)
                comment_blocks = 0
                consecutive_comments = 0
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith('#') and len(stripped) > 5:
                        consecutive_comments += 1
                    else:
                        if consecutive_comments >= 5:
                            comment_blocks += 1
                        consecutive_comments = 0

                if comment_blocks > 0:
                    self.findings.append(Finding(
                        title=f"Code Quality: Remove or implement {comment_blocks} blocks of commented code in {py_file.name}",
                        finding_type='debt',
                        priority='P4',
                        category=['code-quality', 'maintainability'],
                        description=f"Found {comment_blocks} large blocks of commented code. Either implement the features or remove the dead code.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

            except:
                pass

    def _scan_developer_experience(self):
        """Find missing docstrings, type hints, magic numbers - DX improvements"""

        print("  🎯 Scanning for developer experience improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Find functions missing type hints
                # Pattern: def func_name(...) without -> return type
                functions_without_return_types = re.findall(
                    r'def\s+\w+\([^)]*\):\s*(?!\s*->)',
                    content
                )

                # Filter out __init__ and properties which often don't need return types
                functions_without_return_types = [
                    f for f in functions_without_return_types
                    if '__init__' not in f and '@property' not in content[:content.index(f)]
                ]

                if len(functions_without_return_types) >= 5:
                    self.findings.append(Finding(
                        title=f"DX: Add type hints to {len(functions_without_return_types)} functions in {py_file.name}",
                        finding_type='enhancement',
                        priority='P3',
                        category=['developer-experience', 'code-quality', 'maintainability'],
                        description=f"Found {len(functions_without_return_types)} functions without return type hints. Type hints improve IDE support, catch bugs early, and serve as documentation.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Find magic numbers (hardcoded numbers not in obvious contexts)
                # Skip common numbers like 0, 1, 2, 100
                magic_numbers = []
                for i, line in enumerate(lines, 1):
                    # Skip comments, strings, and obvious contexts
                    if line.strip().startswith('#') or '"""' in line or "'''" in line:
                        continue

                    # Find numbers that aren't 0, 1, 2, or in variable assignments
                    numbers = re.findall(r'\b([3-9]|[1-9]\d{2,})\b', line)
                    for num in numbers:
                        # Skip if it's clearly a default/constant
                        if '=' not in line or 'DEFAULT' in line.upper() or 'CONSTANT' in line.upper():
                            continue
                        magic_numbers.append((i, num, line.strip()[:60]))

                if len(magic_numbers) >= 5:
                    examples = ', '.join([f"{num}" for _, num, _ in magic_numbers[:3]])
                    self.findings.append(Finding(
                        title=f"DX: Extract {len(magic_numbers)} magic numbers to named constants in {py_file.name}",
                        finding_type='enhancement',
                        priority='P4',
                        category=['developer-experience', 'maintainability'],
                        description=f"Found {len(magic_numbers)} magic numbers ({examples}...). Extract to named constants for better maintainability and clarity.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

            except:
                pass

    def _scan_modern_language_features(self):
        """Find old-style formatting, dict comprehensions opportunities"""

        print("  🚀 Scanning for modern Python feature opportunities...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Find old-style % formatting
                old_format_count = len(re.findall(r'"%[sd]"', content))
                if old_format_count >= 3:
                    self.findings.append(Finding(
                        title=f"Modernization: Replace {old_format_count} old-style string formats in {py_file.name}",
                        finding_type='enhancement',
                        priority='P4',
                        category=['modernization', 'code-quality'],
                        description=f"Found {old_format_count} old-style % string formatting. Use f-strings for better readability and performance.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Find opportunities for walrus operator (Python 3.8+)
                # Pattern: if x = func(): ... becomes if (x := func()):
                walrus_opportunities = len(re.findall(
                    r'(\w+)\s*=\s*([^=\n]+)\n\s+if\s+\1',
                    content
                ))
                if walrus_opportunities >= 3:
                    self.findings.append(Finding(
                        title=f"Modernization: Use walrus operator in {walrus_opportunities} places in {py_file.name}",
                        finding_type='enhancement',
                        priority='P4',
                        category=['modernization', 'code-quality'],
                        description=f"Found {walrus_opportunities} opportunities to use the walrus operator (:=) for more concise code.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Find opportunities for pathlib over os.path
                ospath_usage = len(re.findall(r'os\.path\.(join|exists|dirname|basename)', content))
                has_pathlib = 'from pathlib import Path' in content or 'import pathlib' in content

                if ospath_usage >= 3 and not has_pathlib:
                    self.findings.append(Finding(
                        title=f"Modernization: Replace os.path with pathlib in {py_file.name}",
                        finding_type='enhancement',
                        priority='P4',
                        category=['modernization', 'code-quality'],
                        description=f"Found {ospath_usage} os.path operations. Use pathlib.Path for more pythonic and readable path handling.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

            except:
                pass

    # ==================== PHASE 2: HIGH VALUE ====================

    def _scan_api_enhancements(self):
        """Find missing CRUD operations, pagination, rate limiting in APIs"""

        print("  🔌 Scanning for API enhancement opportunities...")

        # Look for FastAPI/Flask API files
        api_files = list(self.project_root.glob("**/*api*.py")) + \
                   list(self.project_root.glob("**/routes/*.py")) + \
                   list(self.project_root.glob("**/endpoints/*.py"))

        for api_file in api_files:
            try:
                content = api_file.read_text()

                # Check for incomplete CRUD operations
                has_get = 'def get' in content.lower() or '@app.get' in content or '@router.get' in content
                has_post = 'def post' in content.lower() or '@app.post' in content or '@router.post' in content
                has_put = 'def put' in content.lower() or '@app.put' in content or '@router.put' in content
                has_delete = 'def delete' in content.lower() or '@app.delete' in content or '@router.delete' in content

                crud_ops = [has_get, has_post, has_put, has_delete]
                if any(crud_ops) and not all(crud_ops):
                    missing = []
                    if not has_get: missing.append('GET')
                    if not has_post: missing.append('POST')
                    if not has_put: missing.append('PUT/PATCH')
                    if not has_delete: missing.append('DELETE')

                    self.findings.append(Finding(
                        title=f"API: Complete CRUD operations in {api_file.name} (missing {', '.join(missing)})",
                        finding_type='enhancement',
                        priority='P3',
                        category=['api', 'feature', 'completeness'],
                        description=f"API has incomplete CRUD operations. Missing: {', '.join(missing)}. Complete the API surface for better usability.",
                        file_path=str(api_file.relative_to(self.project_root)),
                        effort='medium'
                    ))

                # Check for missing pagination
                if has_get and 'limit' not in content.lower() and 'page' not in content.lower():
                    self.findings.append(Finding(
                        title=f"API: Add pagination to GET endpoints in {api_file.name}",
                        finding_type='enhancement',
                        priority='P3',
                        category=['api', 'scalability', 'performance'],
                        description="GET endpoints lack pagination. Add limit/offset or page/per_page parameters to prevent performance issues with large datasets.",
                        file_path=str(api_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Check for missing rate limiting
                if '@app.' in content or '@router.' in content:
                    if 'rate_limit' not in content.lower() and 'ratelimit' not in content.lower() and 'limiter' not in content.lower():
                        self.findings.append(Finding(
                            title=f"API: Add rate limiting to {api_file.name}",
                            finding_type='enhancement',
                            priority='P2',
                            category=['api', 'security', 'reliability'],
                            description="API endpoints lack rate limiting. Add rate limiting to prevent abuse and ensure fair resource usage.",
                            file_path=str(api_file.relative_to(self.project_root)),
                            effort='medium'
                        ))

            except:
                pass

    def _scan_observability(self):
        """Find missing logging, metrics, health checks"""

        print("  📊 Scanning for observability gaps...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for functions without logging
                func_count = content.count('def ')
                log_count = content.count('logging.') + content.count('logger.') + content.count('log.')

                # Skip test files and small files
                if 'test_' in py_file.name or func_count < 3:
                    continue

                if func_count >= 5 and log_count < 2:
                    self.findings.append(Finding(
                        title=f"Observability: Add logging to {py_file.name}",
                        finding_type='enhancement',
                        priority='P3',
                        category=['observability', 'debugging', 'operations'],
                        description=f"File has {func_count} functions but minimal logging. Add debug/info logging for easier troubleshooting and monitoring.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Check for long-running operations without progress tracking
                if 'for ' in content and ('time.sleep' in content or 'subprocess' in content):
                    if 'progress' not in content.lower() and 'tqdm' not in content:
                        self.findings.append(Finding(
                            title=f"UX/Observability: Add progress tracking to {py_file.name}",
                            finding_type='enhancement',
                            priority='P4',
                            category=['observability', 'user-experience'],
                            description="Long-running operations detected without progress tracking. Add progress bars or status updates for better user experience.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort='small'
                        ))

            except:
                pass

        # Check for missing health check endpoint in API files
        api_files = list(self.project_root.glob("**/*api*.py")) + \
                   list(self.project_root.glob("**/main.py"))

        for api_file in api_files:
            try:
                content = api_file.read_text()

                if '@app.' in content or 'FastAPI' in content or 'Flask' in content:
                    if '/health' not in content and '/ping' not in content and '/status' not in content:
                        self.findings.append(Finding(
                            title=f"Observability: Add health check endpoint to {api_file.name}",
                            finding_type='enhancement',
                            priority='P3',
                            category=['observability', 'reliability', 'operations'],
                            description="API lacks a health check endpoint. Add /health or /ping endpoint for monitoring and load balancer integration.",
                            file_path=str(api_file.relative_to(self.project_root)),
                            effort='small'
                        ))
            except:
                pass

    def _scan_user_experience(self):
        """Find missing help text, progress bars, error messages"""

        print("  👤 Scanning for user experience improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Check for CLI scripts without argparse help
                if 'argparse' in content or 'ArgumentParser' in content:
                    if '.add_argument' in content and 'help=' not in content:
                        self.findings.append(Finding(
                            title=f"UX: Add help text to CLI arguments in {py_file.name}",
                            finding_type='enhancement',
                            priority='P4',
                            category=['user-experience', 'documentation'],
                            description="CLI arguments lack help text. Add help= parameter to all arguments for better usability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort='small'
                        ))

                # Check for bare exception handlers (poor error messages)
                bare_excepts = len(re.findall(r'except\s*:\s*\n\s+pass', content))
                if bare_excepts > 0:
                    self.findings.append(Finding(
                        title=f"UX: Improve error messages in {py_file.name} ({bare_excepts} bare excepts)",
                        finding_type='enhancement',
                        priority='P3',
                        category=['user-experience', 'debugging', 'reliability'],
                        description=f"Found {bare_excepts} bare except blocks that silently fail. Add specific exception handling with helpful error messages.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Check for print() instead of proper logging in libraries
                if 'def ' in content and py_file.name not in ['main.py', '__main__.py']:
                    print_count = len(re.findall(r'\bprint\s*\(', content))
                    if print_count >= 5:
                        self.findings.append(Finding(
                            title=f"UX/Observability: Replace print() with logging in {py_file.name}",
                            finding_type='enhancement',
                            priority='P4',
                            category=['user-experience', 'observability'],
                            description=f"Found {print_count} print() calls in library code. Use logging instead for better control and configurability.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort='small'
                        ))

            except:
                pass

    # ==================== PHASE 3: ADVANCED ====================

    def _scan_configuration_issues(self):
        """Find hardcoded configs, missing validation"""

        print("  ⚙️  Scanning for configuration improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()

                # Find hardcoded URLs, paths, credentials patterns
                hardcoded_urls = len(re.findall(r'https?://[^\s\'"]+', content))
                hardcoded_paths = len(re.findall(r'["\']/(home|usr|opt|var)/[^"\']+["\']', content))

                if hardcoded_urls >= 3 or hardcoded_paths >= 3:
                    self.findings.append(Finding(
                        title=f"Configuration: Extract hardcoded values to config in {py_file.name}",
                        finding_type='enhancement',
                        priority='P3',
                        category=['configuration', 'maintainability', 'flexibility'],
                        description=f"Found {hardcoded_urls} hardcoded URLs and {hardcoded_paths} hardcoded paths. Extract to configuration file or environment variables.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

                # Check for environment variable usage without defaults or validation
                env_gets = re.findall(r'os\.environ\[(["\'][^"\']+["\']\])', content)
                env_get_with_default = re.findall(r'os\.environ\.get\(', content)

                if len(env_gets) >= 3 and len(env_get_with_default) < len(env_gets) * 0.5:
                    self.findings.append(Finding(
                        title=f"Configuration: Add defaults to environment variables in {py_file.name}",
                        finding_type='bug',
                        priority='P2',
                        category=['configuration', 'reliability'],
                        description=f"Found {len(env_gets)} environment variables accessed without defaults using os.environ[]. Use os.environ.get() with defaults to prevent KeyError crashes.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='small'
                    ))

            except:
                pass

        # Check for missing .env.example file
        env_file = self.project_root / ".env"
        env_example = self.project_root / ".env.example"

        if env_file.exists() and not env_example.exists():
            self.findings.append(Finding(
                title="Configuration: Create .env.example template",
                finding_type='enhancement',
                priority='P4',
                category=['configuration', 'documentation', 'developer-experience'],
                description="Found .env file but no .env.example template. Create .env.example to document required environment variables.",
                effort='small'
            ))

    def _scan_extensibility(self):
        """Find tightly coupled code, missing interfaces"""

        print("  🔌 Scanning for extensibility improvements...")

        py_files = list(self.project_root.glob("tools/**/*.py"))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.splitlines()

                # Find classes with many concrete dependencies (tight coupling)
                # Look for lots of direct imports of specific classes
                import_count = len(re.findall(r'^from .+ import \w+', content, re.MULTILINE))
                class_count = content.count('class ')

                if class_count >= 3 and import_count >= 10:
                    self.findings.append(Finding(
                        title=f"Architecture: Reduce coupling in {py_file.name} ({import_count} imports)",
                        finding_type='debt',
                        priority='P4',
                        category=['architecture', 'extensibility', 'maintainability'],
                        description=f"File has {class_count} classes with {import_count} imports, indicating tight coupling. Consider dependency injection or interfaces.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='large'
                    ))

                # Find large if/elif chains that could be polymorphism or strategy pattern
                elif_chains = re.findall(r'if .+:\n(?:\s+.+\n)+(?:elif .+:\n(?:\s+.+\n)+){3,}', content)

                if len(elif_chains) >= 2:
                    self.findings.append(Finding(
                        title=f"Extensibility: Replace if/elif chains with polymorphism in {py_file.name}",
                        finding_type='enhancement',
                        priority='P4',
                        category=['extensibility', 'code-quality', 'maintainability'],
                        description=f"Found {len(elif_chains)} large if/elif chains. Consider using polymorphism, strategy pattern, or dict dispatch for better extensibility.",
                        file_path=str(py_file.relative_to(self.project_root)),
                        effort='medium'
                    ))

                # Find classes that could benefit from abstract base classes
                # Look for multiple classes with same method names (duck typing -> interface)
                method_names = re.findall(r'def (\w+)\(self', content)
                if len(set(method_names)) != len(method_names) and class_count >= 2:
                    # Multiple classes with same method names - could use ABC
                    if 'ABC' not in content and 'abstractmethod' not in content:
                        self.findings.append(Finding(
                            title=f"Extensibility: Add abstract base classes to {py_file.name}",
                            finding_type='enhancement',
                            priority='P4',
                            category=['extensibility', 'architecture', 'code-quality'],
                            description=f"Multiple classes with similar method signatures detected. Consider using Abstract Base Classes (ABC) to formalize interfaces.",
                            file_path=str(py_file.relative_to(self.project_root)),
                            effort='medium'
                        ))

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

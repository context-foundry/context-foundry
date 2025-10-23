#!/usr/bin/env python3
"""
Parallel Test Runner - Runs unit tests, E2E tests, and lint checks concurrently.

Reduces total test time by ~40% by running independent test suites in parallel.
"""

import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
import json


class ParallelTestRunner:
    """Runs multiple test suites in parallel with optional test sharding."""

    def __init__(self, project_dir: Path, enable_sharding: bool = True, max_shards: int = 4):
        """Initialize test runner.

        Args:
            project_dir: Project directory containing tests
            enable_sharding: Enable test sharding for large test suites
            max_shards: Maximum number of shards to create
        """
        self.project_dir = project_dir
        self.enable_sharding = enable_sharding
        self.max_shards = max_shards

    def run_all_tests_parallel(self, timeout_seconds: int = 300) -> Dict[str, Any]:
        """
        Run all test suites in parallel (unit, E2E, lint).

        Args:
            timeout_seconds: Timeout for each test suite

        Returns:
            Dict with combined results from all test suites
        """
        print(f"\n🧪 Running tests in parallel...")

        test_tasks = [
            ("unit", self._run_sharded_unit_tests if self.enable_sharding else self._run_unit_tests),
            ("e2e", self._run_e2e_tests),
            ("lint", self._run_lint_checks)
        ]

        results = {}
        total_duration = 0
        longest_suite = None
        longest_duration = 0

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_suite = {
                executor.submit(test_func, timeout_seconds): suite_name
                for suite_name, test_func in test_tasks
            }

            for future in as_completed(future_to_suite):
                suite_name = future_to_suite[future]
                try:
                    result = future.result()
                    results[suite_name] = result

                    # Track longest-running suite (bottleneck)
                    duration = result.get('duration_seconds', 0)
                    if duration > longest_duration:
                        longest_duration = duration
                        longest_suite = suite_name

                    status_icon = "✅" if result.get('success') else "❌"
                    print(f"   {status_icon} {suite_name}: {result.get('message', 'completed')}")

                except Exception as e:
                    print(f"   ❌ {suite_name} failed with exception: {e}")
                    results[suite_name] = {
                        'success': False,
                        'error': str(e),
                        'test_type': suite_name
                    }

        # Aggregate results
        all_passed = all(r.get('success', False) for r in results.values())
        total_tests = sum(r.get('tests_run', 0) for r in results.values())
        total_failures = sum(r.get('tests_failed', 0) for r in results.values())

        print(f"\n📊 Parallel test summary:")
        print(f"   Total time: {longest_duration:.1f}s (limited by {longest_suite})")
        print(f"   Tests run: {total_tests}")
        print(f"   Failures: {total_failures}")
        print(f"   Overall: {'✅ PASSED' if all_passed else '❌ FAILED'}")

        return {
            'success': all_passed,
            'duration_seconds': longest_duration,
            'bottleneck_suite': longest_suite,
            'total_tests': total_tests,
            'total_failures': total_failures,
            'results': results
        }

    def _discover_test_files(self, test_type: str) -> List[Path]:
        """
        Discover test files for a given test type.

        Args:
            test_type: Type of tests ('unit', 'e2e')

        Returns:
            List of test file paths
        """
        test_files = []

        if test_type == 'unit':
            # JavaScript/TypeScript unit tests
            test_files.extend(self.project_dir.glob('**/*.test.js'))
            test_files.extend(self.project_dir.glob('**/*.test.ts'))
            test_files.extend(self.project_dir.glob('**/*.spec.js'))
            test_files.extend(self.project_dir.glob('**/*.spec.ts'))

            # Python unit tests
            test_files.extend(self.project_dir.glob('**/test_*.py'))
            test_files.extend(self.project_dir.glob('**/*_test.py'))

            # Exclude e2e directories
            test_files = [f for f in test_files if 'e2e' not in f.parts and 'integration' not in f.parts]

        elif test_type == 'e2e':
            # E2E test files
            e2e_dir = self.project_dir / 'e2e'
            if e2e_dir.exists():
                test_files.extend(e2e_dir.glob('**/*.test.js'))
                test_files.extend(e2e_dir.glob('**/*.test.ts'))
                test_files.extend(e2e_dir.glob('**/*.spec.js'))
                test_files.extend(e2e_dir.glob('**/*.spec.ts'))

        return test_files

    def _create_test_shards(self, test_files: List[Path], num_shards: int) -> List[List[Path]]:
        """
        Split test files into balanced shards.

        Args:
            test_files: List of test files to shard
            num_shards: Number of shards to create

        Returns:
            List of shards, where each shard is a list of test file paths
        """
        if not test_files or num_shards <= 1:
            return [test_files] if test_files else []

        # Simple round-robin distribution for now
        # TODO: Could be enhanced with file size or estimated duration
        shards = [[] for _ in range(num_shards)]
        for i, test_file in enumerate(sorted(test_files)):
            shard_idx = i % num_shards
            shards[shard_idx].append(test_file)

        # Remove empty shards
        return [shard for shard in shards if shard]

    def _run_test_shard(self, shard_files: List[Path], test_type: str, shard_num: int, timeout: int) -> Dict[str, Any]:
        """
        Run tests for a specific shard.

        Args:
            shard_files: List of test files in this shard
            test_type: Type of tests ('jest', 'pytest', 'playwright')
            shard_num: Shard number (for logging)
            timeout: Timeout in seconds

        Returns:
            Dict with shard test results
        """
        import time
        start = time.time()

        if not shard_files:
            return {
                'success': True,
                'shard_num': shard_num,
                'tests_run': 0,
                'duration_seconds': 0
            }

        try:
            # Convert paths to strings relative to project dir
            file_patterns = [str(f.relative_to(self.project_dir)) for f in shard_files]

            if test_type == 'jest':
                # Run Jest with specific files
                result = subprocess.run(
                    ['npm', 'test', '--'] + file_patterns,
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                tests_run = self._parse_jest_output(result.stdout)

                return {
                    'success': result.returncode == 0,
                    'shard_num': shard_num,
                    'files': file_patterns,
                    'output': result.stdout,
                    'error': result.stderr,
                    'duration_seconds': time.time() - start,
                    **tests_run
                }

            elif test_type == 'pytest':
                # Run pytest with specific files
                result = subprocess.run(
                    ['pytest', '-v'] + file_patterns,
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                tests_run = self._parse_pytest_output(result.stdout)

                return {
                    'success': result.returncode == 0,
                    'shard_num': shard_num,
                    'files': file_patterns,
                    'output': result.stdout,
                    'error': result.stderr,
                    'duration_seconds': time.time() - start,
                    **tests_run
                }

            elif test_type == 'playwright':
                # Run Playwright with specific files
                result = subprocess.run(
                    ['npx', 'playwright', 'test'] + file_patterns,
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                tests_run = self._parse_playwright_output(result.stdout)

                return {
                    'success': result.returncode == 0,
                    'shard_num': shard_num,
                    'files': file_patterns,
                    'output': result.stdout,
                    'error': result.stderr,
                    'duration_seconds': time.time() - start,
                    **tests_run
                }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'shard_num': shard_num,
                'error': f'Shard {shard_num} timed out',
                'duration_seconds': timeout
            }
        except Exception as e:
            return {
                'success': False,
                'shard_num': shard_num,
                'error': str(e),
                'duration_seconds': time.time() - start
            }

    def _run_sharded_unit_tests(self, timeout: int) -> Dict[str, Any]:
        """Run unit tests with sharding for large test suites."""
        import time
        start = time.time()

        # Discover test files
        test_files = self._discover_test_files('unit')

        if not test_files:
            return {
                'success': True,
                'message': 'No unit tests found (skipped)',
                'test_type': 'none',
                'duration_seconds': time.time() - start,
                'tests_run': 0
            }

        # Check if sharding is needed (20+ test files)
        if not self.enable_sharding or len(test_files) < 20:
            # Fall back to normal execution
            return self._run_unit_tests(timeout)

        # Determine test type (Jest or pytest)
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            test_type = 'jest'
        else:
            test_type = 'pytest'

        # Create shards
        num_shards = min(self.max_shards, len(test_files))
        shards = self._create_test_shards(test_files, num_shards)

        print(f"   🧩 Sharding {len(test_files)} unit tests into {len(shards)} shards...")

        # Run shards in parallel
        shard_results = []
        with ThreadPoolExecutor(max_workers=len(shards)) as executor:
            futures = {
                executor.submit(self._run_test_shard, shard, test_type, i+1, timeout): i
                for i, shard in enumerate(shards)
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    shard_results.append(result)
                    status = "✅" if result.get('success') else "❌"
                    print(f"      {status} Shard {result.get('shard_num')}: {result.get('tests_run', 0)} tests in {result.get('duration_seconds', 0):.1f}s")
                except Exception as e:
                    print(f"      ❌ Shard failed: {e}")

        # Aggregate results
        all_success = all(r.get('success', False) for r in shard_results)
        total_tests = sum(r.get('tests_run', 0) for r in shard_results)
        total_passed = sum(r.get('tests_passed', 0) for r in shard_results)
        total_failed = sum(r.get('tests_failed', 0) for r in shard_results)
        max_duration = max((r.get('duration_seconds', 0) for r in shard_results), default=0)

        return {
            'success': all_success,
            'test_type': f'{test_type}_sharded',
            'shards': len(shards),
            'shard_results': shard_results,
            'tests_run': total_tests,
            'tests_passed': total_passed,
            'tests_failed': total_failed,
            'duration_seconds': max_duration,  # Limited by slowest shard
            'message': f"{total_tests} unit tests across {len(shards)} shards"
        }

    def _run_unit_tests(self, timeout: int) -> Dict[str, Any]:
        """Run unit tests (Jest or pytest)."""
        import time
        start = time.time()

        # Check for package.json (Node/JavaScript project)
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r') as f:
                    pkg_data = json.load(f)
                    if 'scripts' in pkg_data and 'test' in pkg_data['scripts']:
                        result = subprocess.run(
                            ['npm', 'test', '--', '--testPathIgnorePatterns=e2e'],
                            cwd=self.project_dir,
                            capture_output=True,
                            text=True,
                            timeout=timeout
                        )

                        # Parse Jest output for test counts
                        tests_run = self._parse_jest_output(result.stdout)

                        return {
                            'success': result.returncode == 0,
                            'output': result.stdout,
                            'error': result.stderr,
                            'test_type': 'jest',
                            'duration_seconds': time.time() - start,
                            'message': f"{tests_run} unit tests",
                            **tests_run
                        }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': 'Unit tests timed out', 'test_type': 'jest', 'duration_seconds': timeout}
            except Exception as e:
                return {'success': False, 'error': str(e), 'test_type': 'jest', 'duration_seconds': time.time() - start}

        # Check for Python tests (pytest)
        test_files = list(self.project_dir.glob('**/test_*.py')) + list(self.project_dir.glob('**/*_test.py'))
        if test_files or (self.project_dir / 'tests').exists():
            try:
                result = subprocess.run(
                    ['pytest', '-v', '--ignore=e2e'],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                tests_run = self._parse_pytest_output(result.stdout)

                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr,
                    'test_type': 'pytest',
                    'duration_seconds': time.time() - start,
                    'message': f"{tests_run['tests_run']} unit tests",
                    **tests_run
                }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': 'Unit tests timed out', 'test_type': 'pytest', 'duration_seconds': timeout}
            except Exception as e:
                return {'success': False, 'error': str(e), 'test_type': 'pytest', 'duration_seconds': time.time() - start}

        return {
            'success': True,
            'message': 'No unit tests found (skipped)',
            'test_type': 'none',
            'duration_seconds': time.time() - start,
            'tests_run': 0
        }

    def _run_e2e_tests(self, timeout: int) -> Dict[str, Any]:
        """Run E2E tests (Playwright or Cypress)."""
        import time
        start = time.time()

        # Check for Playwright
        if (self.project_dir / 'playwright.config.js').exists() or (self.project_dir / 'playwright.config.ts').exists():
            try:
                result = subprocess.run(
                    ['npx', 'playwright', 'test'],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                tests_run = self._parse_playwright_output(result.stdout)

                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr,
                    'test_type': 'playwright',
                    'duration_seconds': time.time() - start,
                    'message': f"{tests_run['tests_run']} E2E tests",
                    **tests_run
                }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': 'E2E tests timed out', 'test_type': 'playwright', 'duration_seconds': timeout}
            except Exception as e:
                return {'success': False, 'error': str(e), 'test_type': 'playwright', 'duration_seconds': time.time() - start}

        # Check for Cypress
        if (self.project_dir / 'cypress.config.js').exists():
            try:
                result = subprocess.run(
                    ['npx', 'cypress', 'run'],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr,
                    'test_type': 'cypress',
                    'duration_seconds': time.time() - start,
                    'message': 'E2E tests (Cypress)'
                }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': 'E2E tests timed out', 'test_type': 'cypress', 'duration_seconds': timeout}
            except Exception as e:
                return {'success': False, 'error': str(e), 'test_type': 'cypress', 'duration_seconds': time.time() - start}

        return {
            'success': True,
            'message': 'No E2E tests found (skipped)',
            'test_type': 'none',
            'duration_seconds': time.time() - start,
            'tests_run': 0
        }

    def _run_lint_checks(self, timeout: int) -> Dict[str, Any]:
        """Run linting and formatting checks."""
        import time
        start = time.time()

        # Check for ESLint
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                with open(package_json, 'r') as f:
                    pkg_data = json.load(f)
                    if 'scripts' in pkg_data and 'lint' in pkg_data['scripts']:
                        result = subprocess.run(
                            ['npm', 'run', 'lint'],
                            cwd=self.project_dir,
                            capture_output=True,
                            text=True,
                            timeout=timeout
                        )

                        return {
                            'success': result.returncode == 0,
                            'output': result.stdout,
                            'error': result.stderr,
                            'test_type': 'eslint',
                            'duration_seconds': time.time() - start,
                            'message': 'Lint checks'
                        }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': 'Lint checks timed out', 'test_type': 'eslint', 'duration_seconds': timeout}
            except Exception as e:
                return {'success': False, 'error': str(e), 'test_type': 'eslint', 'duration_seconds': time.time() - start}

        # Check for Python linting (flake8, black, etc.)
        if (self.project_dir / '.flake8').exists() or (self.project_dir / 'pyproject.toml').exists():
            try:
                result = subprocess.run(
                    ['flake8', '.'],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr,
                    'test_type': 'flake8',
                    'duration_seconds': time.time() - start,
                    'message': 'Lint checks'
                }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': 'Lint checks timed out', 'test_type': 'flake8', 'duration_seconds': timeout}
            except Exception as e:
                return {'success': False, 'error': str(e), 'test_type': 'flake8', 'duration_seconds': time.time() - start}

        return {
            'success': True,
            'message': 'No lint checks configured (skipped)',
            'test_type': 'none',
            'duration_seconds': time.time() - start
        }

    def _parse_jest_output(self, output: str) -> Dict[str, int]:
        """Parse Jest output to extract test counts."""
        import re
        tests_run = 0
        tests_failed = 0
        tests_passed = 0

        # Look for "Tests: X passed, Y total"
        match = re.search(r'Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total', output)
        if match:
            tests_passed = int(match.group(1))
            tests_run = int(match.group(2))
            tests_failed = tests_run - tests_passed

        return {
            'tests_run': tests_run,
            'tests_passed': tests_passed,
            'tests_failed': tests_failed
        }

    def _parse_pytest_output(self, output: str) -> Dict[str, int]:
        """Parse pytest output to extract test counts."""
        import re
        tests_run = 0
        tests_failed = 0
        tests_passed = 0

        # Look for "X passed in Ys" or "X failed, Y passed in Zs"
        match = re.search(r'(\d+)\s+passed', output)
        if match:
            tests_passed = int(match.group(1))

        match = re.search(r'(\d+)\s+failed', output)
        if match:
            tests_failed = int(match.group(1))

        tests_run = tests_passed + tests_failed

        return {
            'tests_run': tests_run,
            'tests_passed': tests_passed,
            'tests_failed': tests_failed
        }

    def _parse_playwright_output(self, output: str) -> Dict[str, int]:
        """Parse Playwright output to extract test counts."""
        import re
        tests_run = 0
        tests_failed = 0
        tests_passed = 0

        # Look for "X passed (Ys)"
        match = re.search(r'(\d+)\s+passed', output)
        if match:
            tests_passed = int(match.group(1))

        match = re.search(r'(\d+)\s+failed', output)
        if match:
            tests_failed = int(match.group(1))

        tests_run = tests_passed + tests_failed

        return {
            'tests_run': tests_run,
            'tests_passed': tests_passed,
            'tests_failed': tests_failed
        }

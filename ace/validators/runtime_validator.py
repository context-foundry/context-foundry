#!/usr/bin/env python3
"""
Runtime Validator
Validates projects at runtime through smoke tests and integration tests.
"""

import os
import sys
import json
import subprocess
import http.server
import socketserver
import threading
import time
import signal
import socket
import urllib.request
import urllib.error
import re
from pathlib import Path
from typing import Dict, Any


class RuntimeValidator:
    """
    Runtime validation for projects.

    Provides smoke testing and integration testing capabilities:
    - Static HTML smoke tests (validates file references)
    - Node.js integration tests (build, contract tests, server sanity)
    - Contract test execution
    - Quick server sanity tests
    """

    def __init__(self, project_dir: Path):
        """
        Initialize the RuntimeValidator.

        Args:
            project_dir: Path to the project directory to validate
        """
        self.project_dir = Path(project_dir)

    def run_smoke_test(self) -> Dict[str, Any]:
        """Run optional smoke test to catch build errors.

        Returns:
            dict with 'success' bool, 'output' string, and 'errors' list
        """
        package_json_path = self.project_dir / "package.json"

        # Check if this is a static HTML project (no package.json)
        if not package_json_path.exists():
            return self.run_static_html_smoke_test()

        # For Node.js projects, run runtime integration tests
        return self.run_nodejs_integration_test()

    def run_smoke_test_wrapper(self) -> tuple:
        """Wrapper for smoke test that returns format expected by retry mechanisms.

        Returns:
            (success: bool, error_details: dict)
        """
        result = self.run_smoke_test()

        # Handle None success (test skipped)
        if result['success'] is None:
            return (True, {})  # Skip means no failure

        # Convert to expected format
        if result['success']:
            return (True, {})
        else:
            error_details = {
                'message': result.get('output', 'Smoke test failed'),
                'errors': result.get('errors', []),
                'stderr': '\n'.join(result.get('errors', []))
            }
            return (False, error_details)

    def run_nodejs_integration_test(self) -> Dict[str, Any]:
        """Run integration tests for Node.js projects.

        Includes:
        - Contract test execution
        - Runtime server testing
        - Endpoint validation

        Returns:
            dict with 'success' bool, 'output' string, and 'errors' list
        """
        package_json_path = self.project_dir / "package.json"

        try:
            package_data = json.loads(package_json_path.read_text())
            scripts = package_data.get('scripts', {})

            errors = []
            outputs = []

            # Step 1: Check if contract tests exist
            contract_test_dir = self.project_dir / "tests" / "contract"
            if contract_test_dir.exists():
                print(f"   Running contract tests...")
                contract_result = self.run_contract_tests()

                if contract_result["success"] is False:
                    errors.extend(contract_result["errors"])
                    outputs.append(f"Contract tests failed: {len(contract_result['errors'])} error(s)")
                elif contract_result["success"] is True:
                    outputs.append(f"Contract tests passed")

            # Step 2: Check if build script exists (for React/Vue/etc)
            if 'build' in scripts:
                print(f"   Running build test: npm run build")
                print(f"   (This may take a minute...)")

                # Run build with timeout
                result = subprocess.run(
                    ['npm', 'run', 'build'],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout
                )

                if result.returncode == 0:
                    outputs.append("Build succeeded")
                else:
                    # Parse common errors
                    stderr = result.stderr

                    if "Module not found" in stderr:
                        module_errors = re.findall(r"Module not found: Error: Can't resolve '([^']+)'", stderr)
                        for module in module_errors:
                            errors.append(f"Build error: Missing module {module}")

                    if "index.html" in stderr and "public" in stderr:
                        errors.append("Build error: Missing public/index.html (required for CRA)")

                    if not errors:
                        error_lines = stderr.strip().split('\n')[:3]
                        errors.extend([f"Build error: {line}" for line in error_lines if line])

            # Step 3: Run quick sanity test (start server and test endpoints)
            print(f"   Running server sanity test...")
            sanity_result = self.run_quick_sanity_test()

            if sanity_result["success"] is False:
                errors.extend(sanity_result["errors"])
                outputs.append(f"Server sanity test failed")
            elif sanity_result["success"] is True:
                outputs.append(f"Server sanity test passed")

            # Determine overall success
            if errors:
                return {
                    "success": False,
                    "output": "; ".join(outputs) if outputs else "Integration tests failed",
                    "errors": errors
                }
            else:
                return {
                    "success": True,
                    "output": "; ".join(outputs) if outputs else "All integration tests passed",
                    "errors": []
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "Build timeout (exceeded 2 minutes)",
                "errors": ["Build took too long - possible infinite loop or large project"]
            }
        except FileNotFoundError:
            return {
                "success": None,
                "output": "npm not found - skipping smoke test",
                "errors": []
            }
        except Exception as e:
            return {
                "success": False,
                "output": str(e),
                "errors": [f"Integration test failed: {e}"]
            }

    def run_static_html_smoke_test(self) -> Dict[str, Any]:
        """Run smoke test for static HTML projects.

        Starts a simple HTTP server and validates HTML files load without 404s.

        Returns:
            dict with 'success' bool, 'output' string, and 'errors' list
        """
        # Find HTML files in public/ directory
        public_dir = self.project_dir / "public"
        if not public_dir.exists():
            return {
                "success": None,
                "output": "No public/ directory found - skipping static HTML smoke test",
                "errors": []
            }

        html_files = list(public_dir.glob("**/*.html"))
        if not html_files:
            return {
                "success": None,
                "output": "No HTML files found in public/ - skipping static HTML smoke test",
                "errors": []
            }

        print(f"   Starting HTTP server on port 8888...")
        print(f"   Checking {len(html_files)} HTML file(s) for broken references...")

        errors = []
        server = None
        server_thread = None

        try:
            # Start simple HTTP server
            os.chdir(public_dir)
            handler = http.server.SimpleHTTPRequestHandler

            # Suppress server logs
            handler.log_message = lambda *args: None

            server = socketserver.TCPServer(("", 8888), handler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            # Give server time to start
            time.sleep(0.5)

            # Test each HTML file
            for html_file in html_files:
                relative_path = html_file.relative_to(public_dir)
                url = f"http://localhost:8888/{relative_path}"

                try:
                    # Fetch the HTML page
                    response = urllib.request.urlopen(url, timeout=5)
                    html_content = response.read().decode('utf-8')

                    # Parse and check for common broken references

                    # Check CSS links
                    css_links = re.findall(r'<link[^>]*href=["\']([^"\']+\.css)["\']', html_content)
                    for css_link in css_links:
                        if not css_link.startswith(('http://', 'https://', '//')):
                            css_url = f"http://localhost:8888/{css_link}" if not css_link.startswith('/') else f"http://localhost:8888{css_link}"
                            try:
                                urllib.request.urlopen(css_url, timeout=2)
                            except urllib.error.HTTPError as e:
                                if e.code == 404:
                                    errors.append(f"{relative_path}: CSS file not found: {css_link}")
                            except Exception as e:
                                errors.append(f"{relative_path}: Could not load CSS {css_link}: {str(e)}")

                    # Check JS scripts
                    js_links = re.findall(r'<script[^>]*src=["\']([^"\']+\.js)["\']', html_content)
                    for js_link in js_links:
                        if not js_link.startswith(('http://', 'https://', '//')):
                            js_url = f"http://localhost:8888/{js_link}" if not js_link.startswith('/') else f"http://localhost:8888{js_link}"
                            try:
                                urllib.request.urlopen(js_url, timeout=2)
                            except urllib.error.HTTPError as e:
                                if e.code == 404:
                                    errors.append(f"{relative_path}: JS file not found: {js_link}")
                            except Exception as e:
                                errors.append(f"{relative_path}: Could not load JS {js_link}: {str(e)}")

                except Exception as e:
                    errors.append(f"Could not load {relative_path}: {str(e)}")

            # Shutdown server
            if server:
                server.shutdown()

            os.chdir(self.project_dir)

            if errors:
                return {
                    "success": False,
                    "output": f"Found {len(errors)} broken file reference(s)",
                    "errors": errors
                }
            else:
                return {
                    "success": True,
                    "output": f"All {len(html_files)} HTML file(s) loaded successfully",
                    "errors": []
                }

        except Exception as e:
            if server:
                server.shutdown()
            os.chdir(self.project_dir)
            return {
                "success": False,
                "output": "Static HTML smoke test failed",
                "errors": [f"Test error: {str(e)}"]
            }

    def run_contract_tests(self) -> Dict[str, Any]:
        """Run contract tests if they exist.

        Returns:
            dict with 'success' bool, 'output' string, and 'errors' list
        """
        contract_test_dir = self.project_dir / "tests" / "contract"

        if not contract_test_dir.exists():
            return {"success": None, "output": "No contract tests found", "errors": []}

        # Check for test files
        test_files = list(contract_test_dir.glob("*.test.js")) + list(contract_test_dir.glob("*.test.py"))

        if not test_files:
            return {"success": None, "output": "No contract test files found", "errors": []}

        # Install dependencies if needed
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            # Check if jest and supertest are installed
            try:
                package_data = json.loads(package_json.read_text())
                deps = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}

                if 'jest' not in deps or 'supertest' not in deps:
                    print(f"      Installing test dependencies...")
                    subprocess.run(
                        ['npm', 'install', '--save-dev', 'jest', 'supertest'],
                        cwd=self.project_dir,
                        capture_output=True,
                        timeout=60
                    )
            except Exception:
                pass  # Continue even if installation fails

        # Try to run tests
        try:
            # Try Jest (JavaScript)
            result = subprocess.run(
                ['npx', 'jest', 'tests/contract', '--json'],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse Jest output
            try:
                test_output = json.loads(result.stdout)
                if test_output.get('success'):
                    num_tests = test_output.get('numPassedTests', 0)
                    return {
                        "success": True,
                        "output": f"{num_tests} contract test(s) passed",
                        "errors": []
                    }
                else:
                    # Extract failures
                    errors = []
                    for test_result in test_output.get('testResults', []):
                        for assertion in test_result.get('assertionResults', []):
                            if assertion.get('status') == 'failed':
                                title = assertion.get('title', 'Unknown test')
                                errors.append(f"Contract test failed: {title}")

                    if not errors:
                        errors = ["Contract tests failed (see logs for details)"]

                    return {
                        "success": False,
                        "output": "Contract tests failed",
                        "errors": errors
                    }
            except json.JSONDecodeError:
                # Fallback: parse stderr for common errors
                if result.returncode != 0:
                    return {
                        "success": False,
                        "output": "Contract tests failed",
                        "errors": [f"Test execution error: {result.stderr[:200]}"]
                    }

        except FileNotFoundError:
            return {
                "success": None,
                "output": "Jest not available - skipping contract tests",
                "errors": []
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "Contract tests timeout",
                "errors": ["Tests took too long (>30s)"]
            }
        except Exception as e:
            return {
                "success": False,
                "output": "Contract test error",
                "errors": [f"Error running tests: {str(e)}"]
            }

        return {"success": None, "output": "Could not run contract tests", "errors": []}

    def run_quick_sanity_test(self) -> Dict[str, Any]:
        """Quick sanity test: Start server and test basic endpoints.

        Returns:
            dict with 'success' bool, 'output' string, and 'errors' list
        """
        # Check if this is a React app (CRA, Vite, etc.)
        package_json_path = self.project_dir / "package.json"
        is_react_app = False
        is_vite_app = False
        use_npm_start = False

        if package_json_path.exists():
            try:
                package_data = json.loads(package_json_path.read_text())
                deps = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
                scripts = package_data.get('scripts', {})

                is_react_app = 'react-scripts' in deps
                is_vite_app = 'vite' in deps

                # Use npm start for React apps or if start script exists
                use_npm_start = is_react_app or (is_vite_app and 'dev' in scripts) or 'start' in scripts
            except Exception:
                pass

        # Find server entry point
        server_file = None
        if not use_npm_start:
            for candidate in ['server.js', 'app.js', 'index.js', 'src/server.js', 'src/app.js']:
                if (self.project_dir / candidate).exists():
                    server_file = candidate
                    break

            if not server_file:
                return {
                    "success": None,
                    "output": "No server file found (server.js, app.js, etc.) and not a React/Vite app",
                    "errors": []
                }

        # Find an available port
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port

        test_port = find_free_port()
        errors = []
        server_process = None

        try:
            # Start server on test port
            env = os.environ.copy()
            env['PORT'] = str(test_port)
            env['NODE_ENV'] = 'test'
            env['BROWSER'] = 'none'  # Don't open browser for React apps

            # Choose command based on app type
            if use_npm_start:
                if is_react_app:
                    start_command = ['npm', 'start']
                elif is_vite_app:
                    start_command = ['npm', 'run', 'dev']
                else:
                    start_command = ['npm', 'start']
            else:
                start_command = ['node', server_file]

            server_process = subprocess.Popen(
                start_command,
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )

            # Wait for server to start (max 15 seconds for React/Vite, 5 for Node)
            max_wait_time = 15 if use_npm_start else 5
            server_ready = False
            for i in range(max_wait_time * 10):  # Check every 0.1 seconds
                time.sleep(0.1)
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.5)
                        s.connect(('localhost', test_port))
                        server_ready = True
                        break
                except (socket.error, ConnectionRefusedError):
                    # Check if process died
                    if server_process.poll() is not None:
                        stdout, stderr = server_process.communicate()
                        return {
                            "success": False,
                            "output": "Server failed to start",
                            "errors": [f"Server crashed: {stderr.decode()[:200]}"]
                        }
                    continue

            if not server_ready:
                server_process.terminate()
                return {
                    "success": False,
                    "output": "Server did not start in time",
                    "errors": [f"Server took too long to start (>{max_wait_time}s)"]
                }

            # Test root endpoint
            try:
                response = urllib.request.urlopen(f"http://localhost:{test_port}/", timeout=2)
                status = response.getcode()

                if status == 404:
                    errors.append("Root route (/) returns 404 - server needs to serve static files or add root route")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    errors.append("Root route (/) returns 404 - server needs to serve static files or add root route")
                # Other HTTP errors are acceptable (redirect, auth, etc.)
            except Exception as e:
                errors.append(f"Root route test error: {str(e)}")

            # Load SPEC.yaml and test contract endpoints
            spec_yaml_path = self.project_dir / ".context-foundry" / "SPEC.yaml"
            if spec_yaml_path.exists():
                import yaml
                try:
                    with open(spec_yaml_path) as f:
                        spec = yaml.safe_load(f)

                    contract = spec.get('contract', {})
                    endpoints = contract.get('endpoints', [])

                    for endpoint in endpoints[:3]:  # Test up to 3 endpoints
                        path = endpoint.get('path', '/')
                        method = endpoint.get('method', 'GET')

                        if method == 'GET':
                            try:
                                response = urllib.request.urlopen(f"http://localhost:{test_port}{path}?city=test", timeout=2)
                                # Success - endpoint exists
                            except urllib.error.HTTPError as e:
                                if e.code == 404:
                                    errors.append(f"Contract endpoint {method} {path} returns 404 - not implemented")
                                # Other errors (400, 500) are acceptable - endpoint exists
                            except Exception as e:
                                # Ignore other errors
                                pass

                except Exception:
                    pass  # Ignore SPEC.yaml parsing errors

            # Shutdown server
            server_process.terminate()
            try:
                server_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                server_process.kill()

            if errors:
                return {
                    "success": False,
                    "output": f"Found {len(errors)} issue(s)",
                    "errors": errors
                }
            else:
                return {
                    "success": True,
                    "output": "Server started and responded correctly",
                    "errors": []
                }

        except Exception as e:
            if server_process:
                server_process.terminate()
            return {
                "success": False,
                "output": "Sanity test failed",
                "errors": [f"Test error: {str(e)}"]
            }

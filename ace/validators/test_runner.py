#!/usr/bin/env python3
"""
Test Runner for Context Foundry
Extracted test execution methods for reusability across workflows.
"""

import os
import sys
import json
import subprocess
import time
import signal
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
FOUNDRY_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(FOUNDRY_ROOT))

from ace.ai_client import AIClient


class TestRunner:
    """
    Test runner for validating Context Foundry projects.
    Handles contract tests, sanity tests, and functional test generation.
    """

    def __init__(self, project_dir: Path, ai_client: AIClient = None, task_description: str = ""):
        """
        Initialize the test runner.

        Args:
            project_dir: Path to the project directory
            ai_client: Optional AIClient instance for test generation
            task_description: Optional task description for context-aware test generation
        """
        self.project_dir = project_dir
        self.ai_client = ai_client
        self.task_description = task_description

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

    def generate_functional_tests(self, test_port: int) -> str:
        """
        Generate app-specific Playwright functional tests by analyzing project context.

        Args:
            test_port: Port where test server is running

        Returns:
            JavaScript code snippet with functional tests, or empty string if generation fails
        """
        if not self.ai_client:
            print(f"      Warning: AIClient not provided, cannot generate functional tests")
            return ""

        try:
            print(f"      Generating context-aware functional tests...")

            # Gather project context
            context_parts = []

            # 1. Task description
            context_parts.append(f"TASK DESCRIPTION:\n{self.task_description}\n")

            # 2. Read SPEC.yaml if exists
            spec_path = self.project_dir / ".context-foundry" / "SPEC.yaml"
            if spec_path.exists():
                spec_content = spec_path.read_text()
                context_parts.append(f"SPEC.YAML:\n{spec_content[:1000]}\n")  # First 1000 chars

            # 3. Read main UI files to understand structure
            ui_files_read = 0
            for pattern in ['index.html', 'public/index.html', 'src/App.js', 'src/app.js', 'public/script.js']:
                file_path = self.project_dir / pattern
                if file_path.exists() and ui_files_read < 2:
                    content = file_path.read_text()[:1500]  # First 1500 chars
                    context_parts.append(f"FILE {pattern}:\n{content}\n")
                    ui_files_read += 1

            if ui_files_read == 0:
                return ""  # No UI files found, skip functional test generation

            full_context = "\n".join(context_parts)

            # Build prompt for Builder
            prompt = f"""Generate Playwright functional test code for this app.

PROJECT CONTEXT:
{full_context}

REQUIREMENTS:
1. Analyze the project context to understand what the app does
2. Generate JavaScript code (NOT a complete test file, just the test logic)
3. The code should test the ACTUAL FUNCTIONALITY of the app (e.g., for a weather app, test searching for a city)
4. Use Playwright API: page.fill(), page.click(), page.waitForSelector(), etc.
5. The server is already running on localhost:{test_port}
6. Return ONLY the JavaScript test code, no explanations
7. If the app has buttons/forms, test that they work
8. If the app fetches data, verify the data appears in the DOM

EXAMPLE OUTPUT FORMAT (for a todo app):
```javascript
// Test adding a todo item
const input = await page.$('#todo-input');
if (input) {{
    await input.fill('Buy groceries');
    await page.click('#add-button');
    await page.waitForTimeout(500);
    const todos = await page.$$('.todo-item');
    if (todos.length === 0) {{
        throw new Error('Todo item was not added to the list');
    }}
}}
```

Generate functional tests for THIS app:"""

            # Call Builder to generate tests
            response = self.ai_client.builder(
                prompt=prompt,
                max_tokens=1000
            )

            # Extract JavaScript code from response
            import re
            code_match = re.search(r'```(?:javascript|js)?\s*\n?(.*?)```', response.content, re.DOTALL)
            if code_match:
                test_code = code_match.group(1).strip()
                print(f"      Generated {len(test_code)} chars of functional test code")
                return test_code
            else:
                # Fallback: use the whole response if no code block found
                test_code = response.content.strip()
                if len(test_code) < 2000 and 'await page' in test_code:
                    print(f"      Generated functional test code (no code block)")
                    return test_code
                else:
                    print(f"      Could not extract test code from Builder response")
                    return ""

        except Exception as e:
            print(f"      Functional test generation failed: {str(e)}")
            return ""

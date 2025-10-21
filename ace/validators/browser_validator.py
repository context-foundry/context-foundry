#!/usr/bin/env python3
"""
Browser-based validation using Playwright.
Catches client-side errors like "Cannot GET /", React mounting errors, etc.
"""

import os
import json
import socket
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, Tuple


class BrowserValidator:
    """
    Browser-based validation using Playwright to catch client-side errors.
    """

    def __init__(self, project_dir: Path, ai_client=None, task_description: str = ""):
        """
        Initialize the browser validator.

        Args:
            project_dir: Path to the project directory to validate
            ai_client: Optional AIClient instance for generating functional tests
            task_description: Optional task description for context-aware testing
        """
        self.project_dir = Path(project_dir)
        self.ai_client = ai_client
        self.task_description = task_description

    def _generate_functional_tests(self, test_port: int) -> str:
        """
        Generate app-specific Playwright functional tests by analyzing project context.

        Args:
            test_port: Port where test server is running

        Returns:
            JavaScript code snippet with functional tests, or empty string if generation fails
        """
        if not self.ai_client or not self.task_description:
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
                print(f"      ✅ Generated {len(test_code)} chars of functional test code")
                return test_code
            else:
                # Fallback: use the whole response if no code block found
                test_code = response.content.strip()
                if len(test_code) < 2000 and 'await page' in test_code:
                    print(f"      ✅ Generated functional test code (no code block)")
                    return test_code
                else:
                    print(f"      ⚠️  Could not extract test code from Builder response")
                    return ""

        except Exception as e:
            print(f"      ⚠️  Functional test generation failed: {str(e)}")
            return ""

    def run_browser_validation(self) -> Tuple[bool, Dict]:
        """
        Run browser-based validation using Playwright to catch client-side errors.
        This catches issues like "Cannot GET /", React mounting errors, etc.

        Returns:
            (success: bool, error_details: dict)
        """
        # Check if Playwright is available
        package_json_path = self.project_dir / "package.json"
        if not package_json_path.exists():
            return (True, {})  # Skip for non-Node projects

        # Check if this is a web app that needs browser validation
        try:
            package_data = json.loads(package_json_path.read_text())
            deps = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
            scripts = package_data.get('scripts', {})

            is_react_app = 'react-scripts' in deps or 'react' in deps
            is_vite_app = 'vite' in deps
            has_start_script = 'start' in scripts or 'dev' in scripts

            # Only run browser validation for web apps
            if not (is_react_app or is_vite_app or has_start_script):
                return (True, {})  # Skip for non-web apps

        except Exception:
            return (True, {})

        # Find an available port
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port

        test_port = find_free_port()
        server_process = None

        try:
            print(f"      Starting dev server for browser validation...")

            # Install Playwright if not present
            playwright_check = subprocess.run(
                ['npm', 'list', 'playwright'],
                cwd=self.project_dir,
                capture_output=True,
                timeout=10
            )

            if playwright_check.returncode != 0:
                print(f"      Installing Playwright for browser validation...")
                install_result = subprocess.run(
                    ['npm', 'install', '--save-dev', '--no-save', 'playwright'],
                    cwd=self.project_dir,
                    capture_output=True,
                    timeout=120
                )
                if install_result.returncode != 0:
                    return (True, {})  # Skip if can't install

                # Install Playwright browsers (Chromium only for speed)
                print(f"      Installing Playwright browsers...")
                browser_install = subprocess.run(
                    ['npx', 'playwright', 'install', 'chromium', '--with-deps'],
                    cwd=self.project_dir,
                    capture_output=True,
                    timeout=180
                )
                if browser_install.returncode != 0:
                    return (True, {})  # Skip if can't install browsers

            # Start dev server
            env = os.environ.copy()
            env['PORT'] = str(test_port)
            env['BROWSER'] = 'none'
            env['CI'] = 'true'

            if is_react_app:
                start_command = ['npm', 'start']
            elif is_vite_app:
                start_command = ['npm', 'run', 'dev']
            else:
                start_command = ['npm', 'start']

            server_process = subprocess.Popen(
                start_command,
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )

            # Wait for server to start
            server_ready = False
            for i in range(200):  # 20 seconds max
                time.sleep(0.1)
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.5)
                        s.connect(('localhost', test_port))
                        server_ready = True
                        break
                except (socket.error, ConnectionRefusedError):
                    if server_process.poll() is not None:
                        stdout, stderr = server_process.communicate()
                        return (False, {
                            'message': 'Dev server failed to start',
                            'stderr': stderr.decode()[:500]
                        })
                    continue

            if not server_ready:
                server_process.terminate()
                return (False, {
                    'message': 'Dev server timeout',
                    'stderr': 'Server did not start within 20 seconds'
                })

            # Give server a moment to fully initialize
            time.sleep(2)

            # Generate context-aware functional tests
            functional_tests = self._generate_functional_tests(test_port)

            # Create Playwright test script
            test_script = f"""
const {{ chromium }} = require('playwright');

(async () => {{
    const browser = await chromium.launch({{
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }});

    try {{
        const page = await browser.newPage();

        // Collect console errors and failed requests
        const errors = [];
        const failedResources = [];

        page.on('console', msg => {{
            if (msg.type() === 'error') {{
                errors.push(msg.text());
            }}
        }});

        page.on('pageerror', error => {{
            errors.push(error.message);
        }});

        page.on('requestfailed', request => {{
            failedResources.push({{
                url: request.url(),
                failure: request.failure().errorText
            }});
        }});

        // Navigate to app
        const response = await page.goto('http://localhost:{test_port}', {{
            waitUntil: 'networkidle',
            timeout: 15000
        }});

        // Check response status
        if (response.status() === 404) {{
            console.error('ERROR: Page returned 404 - Cannot GET /');
            await browser.close();
            process.exit(1);
        }}

        // Wait for content to render
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);

        // Check for root element content
        const bodyText = await page.textContent('body');
        if (!bodyText || bodyText.trim().length === 0) {{
            console.error('ERROR: Page loaded but has no visible content');
            await browser.close();
            process.exit(1);
        }}

        // Check for failed resource loads (CSS, JS, etc.)
        if (failedResources.length > 0) {{
            console.error('ERROR: Failed to load resources:');
            failedResources.forEach(r => console.error('  - ' + r.url + ': ' + r.failure));
            await browser.close();
            process.exit(1);
        }}

        // Test basic user interactions (if buttons/forms exist)
        const buttons = await page.$$('button');
        const inputs = await page.$$('input[type="text"], input:not([type])');

        if (buttons.length > 0 && inputs.length > 0) {{
            // Try clicking first button to see if event listeners are attached
            try {{
                // Fill first input if it exists
                if (inputs.length > 0) {{
                    await inputs[0].fill('test');
                }}

                // Click first button
                await buttons[0].click();

                // Wait a moment for any async operations
                await page.waitForTimeout(500);

                // Check if any errors occurred from the interaction
                if (errors.length > 0) {{
                    console.error('JavaScript errors detected after user interaction:');
                    errors.forEach(err => console.error('  - ' + err));
                    await browser.close();
                    process.exit(1);
                }}
            }} catch (e) {{
                // Non-fatal: interaction test failed but page might still be valid
                console.log('Note: User interaction test encountered error (non-fatal): ' + e.message);
            }}
        }}

        // Check for JavaScript errors from page load
        if (errors.length > 0) {{
            console.error('JavaScript errors detected:');
            errors.forEach(err => console.error('  - ' + err));
            await browser.close();
            process.exit(1);
        }}

        // Run context-aware functional tests (if generated)
        {functional_tests if functional_tests else '// No functional tests generated'}

        console.log('SUCCESS: Page loaded and rendered correctly');
        await browser.close();
        process.exit(0);

    }} catch (error) {{
        console.error('ERROR: ' + error.message);
        try {{
            await browser.close();
        }} catch (e) {{
            // Ignore close errors
        }}
        process.exit(1);
    }}
}})();
"""

            # Write test script
            test_script_path = self.project_dir / 'playwright-test-temp.js'
            test_script_path.write_text(test_script)

            try:
                # Run Playwright test
                print(f"      Running browser validation...")
                result = subprocess.run(
                    ['node', 'playwright-test-temp.js'],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                # Clean up test script
                test_script_path.unlink()

                if result.returncode == 0:
                    print(f"      ✅ Browser validation (HTTP) passed")

                    # For static HTML apps, also test file:// protocol
                    # This catches issues with absolute vs relative paths
                    package_json = self.project_dir / "package.json"
                    if not package_json.exists() or not is_react_app and not is_vite_app:
                        print(f"      Testing file:// protocol for static HTML app...")

                        # Find index.html
                        index_html = None
                        for candidate in [self.project_dir / 'index.html', self.project_dir / 'public' / 'index.html']:
                            if candidate.exists():
                                index_html = candidate
                                break

                        if index_html:
                            file_test_script = f"""
const {{ chromium }} = require('playwright');

(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    try {{
        const page = await browser.newPage();
        const errors = [];

        page.on('console', msg => {{
            if (msg.type() === 'error') {{
                errors.push(msg.text());
            }}
        }});

        page.on('pageerror', error => {{
            errors.push(error.message);
        }});

        // Open via file:// protocol
        await page.goto('file://{index_html.absolute()}', {{ timeout: 10000 }});
        await page.waitForTimeout(1000);

        // Check for errors that indicate path issues
        const pathErrors = errors.filter(e =>
            e.includes('Not allowed to load local resource') ||
            e.includes('Failed to load resource') ||
            e.includes('net::ERR_FILE_NOT_FOUND')
        );

        if (pathErrors.length > 0) {{
            console.error('ERROR: Resource loading failed (likely absolute path issue):');
            pathErrors.forEach(err => console.error('  - ' + err));
            await browser.close();
            process.exit(1);
        }}

        console.log('SUCCESS: file:// protocol test passed');
        await browser.close();
        process.exit(0);
    }} catch (error) {{
        console.error('ERROR: ' + error.message);
        await browser.close();
        process.exit(1);
    }}
}})();
"""
                            file_test_path = self.project_dir / 'playwright-file-test-temp.js'
                            file_test_path.write_text(file_test_script)

                            try:
                                file_result = subprocess.run(
                                    ['node', 'playwright-file-test-temp.js'],
                                    cwd=self.project_dir,
                                    capture_output=True,
                                    text=True,
                                    timeout=15
                                )

                                file_test_path.unlink()

                                if file_result.returncode != 0:
                                    return (False, {
                                        'message': 'file:// protocol validation failed - likely absolute path issue',
                                        'stderr': file_result.stderr,
                                        'stdout': file_result.stdout
                                    })

                                print(f"      ✅ Browser validation (file://) passed")
                            except Exception as e:
                                if file_test_path.exists():
                                    file_test_path.unlink()
                                # Non-fatal: file:// test failed but HTTP works
                                print(f"      ⚠️  file:// protocol test error (non-fatal): {str(e)}")

                    return (True, {})
                else:
                    return (False, {
                        'message': 'Browser validation failed',
                        'stderr': result.stderr,
                        'stdout': result.stdout
                    })

            finally:
                # Clean up test script if it still exists
                if test_script_path.exists():
                    test_script_path.unlink()

        except subprocess.TimeoutExpired:
            return (False, {
                'message': 'Browser validation timeout',
                'stderr': 'Playwright test exceeded 30 seconds'
            })
        except Exception as e:
            return (False, {
                'message': f'Browser validation error: {str(e)}',
                'stderr': str(e)
            })
        finally:
            # Always kill server
            if server_process:
                server_process.terminate()
                try:
                    server_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    server_process.kill()

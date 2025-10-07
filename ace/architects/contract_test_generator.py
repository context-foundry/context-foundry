"""Generate contract tests from SPEC.yaml"""
import yaml
import json
from pathlib import Path
from typing import Dict, Any


class ContractTestGenerator:
    """Generate executable contract tests from SPEC.yaml"""

    API_TEST_TEMPLATE = """// Generated contract tests from SPEC.yaml
const request = require('supertest');

describe('contract:{service_name}', () => {{
  const base = process.env.BASE_URL || '{base_url}';

{test_cases}
}});
"""

    API_TEST_CASE = """  test('{test_name}', async () => {{
    const res = await request(base)
      .{method_lower}('{path}'){request_body}
      .redirects(0);

    expect({expect_status}).toContain(res.status);{expect_body}
  }});
"""

    CLI_TEST_TEMPLATE = """# Generated contract tests from SPEC.yaml
import subprocess
import pytest


def run_cli(*args):
    \"\"\"Execute CLI command and return result\"\"\"
    result = subprocess.run(
        ['{binary}'] + list(args),
        capture_output=True,
        text=True
    )
    return result


{test_cases}
"""

    CLI_TEST_CASE = """def test_{test_name}():
    \"\"\"Test {test_description}\"\"\"
    result = run_cli({args})
    assert result.returncode == {expected_exit}{stdout_check}
"""

    WEB_TEST_TEMPLATE = """// Generated contract tests from SPEC.yaml
const request = require('supertest');

describe('contract:web', () => {{
{test_cases}
}});
"""

    WEB_TEST_CASE = """  test('{test_name}', async () => {{
    const res = await request('{base_url}').get('{path}');
    expect(res.status).toBe({status});{title_check}
  }});
"""

    def __init__(self):
        """Initialize contract test generator."""
        pass

    def generate_from_yaml(self, spec_yaml_path: Path) -> Dict[str, str]:
        """Generate contract tests from SPEC.yaml.

        Args:
            spec_yaml_path: Path to SPEC.yaml file

        Returns:
            Dict mapping test filename to test content

        Raises:
            FileNotFoundError: If SPEC.yaml doesn't exist
            ValueError: If SPEC.yaml has unknown kind
        """
        if not spec_yaml_path.exists():
            raise FileNotFoundError(f"SPEC.yaml not found: {spec_yaml_path}")

        with open(spec_yaml_path) as f:
            spec = yaml.safe_load(f)

        kind = spec.get('kind', 'api')

        if kind == 'api':
            return self._generate_api_tests(spec)
        elif kind == 'cli':
            return self._generate_cli_tests(spec)
        elif kind == 'web':
            return self._generate_web_tests(spec)
        else:
            raise ValueError(f"Unknown project kind: {kind}")

    def _generate_api_tests(self, spec: Dict) -> Dict[str, str]:
        """Generate Jest tests for API projects.

        Args:
            spec: Parsed SPEC.yaml dictionary

        Returns:
            Dict with single entry: test filename -> test content
        """
        service = spec.get('service', 'service')
        contract = spec.get('contract', {})
        base_url = contract.get('base_url', 'http://localhost:3000')
        endpoints = contract.get('endpoints', [])

        if not endpoints:
            # No endpoints defined, create minimal test
            test_content = self.API_TEST_TEMPLATE.format(
                service_name=service,
                base_url=base_url,
                test_cases="  // No endpoints defined in SPEC.yaml"
            )
            return {f"tests/contract/{service}.contract.test.js": test_content}

        test_cases = []

        for endpoint in endpoints:
            name = endpoint.get('name', 'unnamed')
            method = endpoint.get('method', 'GET').upper()
            path = endpoint.get('path', '/')
            response = endpoint.get('response', {})
            request_data = endpoint.get('request', {})
            example = endpoint.get('example', {})

            # Build test name
            test_name = f"{method} {path} - {name}"

            # Build request body (for POST/PUT/PATCH)
            request_body = ""
            if method in ['POST', 'PUT', 'PATCH']:
                if example and 'request' in example:
                    # Use example request from SPEC.yaml
                    request_json = json.dumps(example['request'])
                    request_body = f"\n      .send({request_json})"
                elif request_data:
                    # Generic request body if no example provided
                    request_body = "\n      .send({})"

            # Build status code expectation
            status = response.get('status', 200)
            if isinstance(status, list):
                expect_status = f"[{', '.join(map(str, status))}]"
            else:
                expect_status = f"[{status}]"

            # Build response body expectations
            expect_body = ""
            response_schema = response.get('json', {})
            if response_schema:
                checks = []
                for key in response_schema.keys():
                    checks.append(f"    expect(res.body).toHaveProperty('{key}');")
                if checks:
                    expect_body = "\n" + "\n".join(checks)

            # Generate test case
            test_case = self.API_TEST_CASE.format(
                test_name=test_name,
                method_lower=method.lower(),
                path=path,
                request_body=request_body,
                expect_status=expect_status,
                expect_body=expect_body
            )
            test_cases.append(test_case)

        # Combine into full test file
        content = self.API_TEST_TEMPLATE.format(
            service_name=service,
            base_url=base_url,
            test_cases="\n".join(test_cases)
        )

        return {f"tests/contract/{service}.contract.test.js": content}

    def _generate_cli_tests(self, spec: Dict) -> Dict[str, str]:
        """Generate Pytest tests for CLI projects.

        Args:
            spec: Parsed SPEC.yaml dictionary

        Returns:
            Dict with single entry: test filename -> test content
        """
        binary = spec.get('binary', 'app')
        commands = spec.get('commands', [])

        if not commands:
            # No commands defined, create minimal test
            test_content = self.CLI_TEST_TEMPLATE.format(
                binary=binary,
                test_cases="# No commands defined in SPEC.yaml"
            )
            return {f"tests/contract/test_{binary}_contract.py": test_content}

        test_cases = []

        for cmd in commands:
            name = cmd.get('name', 'unnamed')
            args = cmd.get('args', [])
            exit_codes = cmd.get('exit_codes', {0: 'success'})
            description = cmd.get('description', name)

            # Get expected exit code (use first one)
            expected_exit = list(exit_codes.keys())[0] if exit_codes else 0

            # Build args list for test
            if args:
                args_str = ', '.join([f"'{arg}'" for arg in args])
            else:
                args_str = ""

            # Build stdout check (optional for now)
            stdout_check = ""
            # Could add: if 'expect_stdout' in cmd:
            #     stdout_check = f"\n    assert '{cmd['expect_stdout']}' in result.stdout"

            # Generate test case
            test_name = name.replace('-', '_').replace(' ', '_')
            test_case = self.CLI_TEST_CASE.format(
                test_name=test_name,
                test_description=description,
                args=args_str,
                expected_exit=expected_exit,
                stdout_check=stdout_check
            )
            test_cases.append(test_case)

        # Combine into full test file
        content = self.CLI_TEST_TEMPLATE.format(
            binary=binary,
            test_cases="\n\n".join(test_cases)
        )

        return {f"tests/contract/test_{binary}_contract.py": content}

    def _generate_web_tests(self, spec: Dict) -> Dict[str, str]:
        """Generate basic web tests.

        Args:
            spec: Parsed SPEC.yaml dictionary

        Returns:
            Dict with single entry: test filename -> test content
        """
        base_url = spec.get('base_url', 'http://localhost:3000')
        pages = spec.get('pages', [])

        if not pages:
            # No pages defined, create minimal test
            test_content = self.WEB_TEST_TEMPLATE.format(
                test_cases="  // No pages defined in SPEC.yaml"
            )
            return {"tests/contract/web.contract.test.js": test_content}

        test_cases = []

        for page in pages:
            path = page.get('path', '/')
            title = page.get('title_contains', '')
            status = page.get('status', 200)

            # Build test name
            test_name = f"GET {path}"

            # Build title check
            title_check = ""
            if title:
                title_check = f"\n    expect(res.text).toContain('{title}');"

            # Generate test case
            test_case = self.WEB_TEST_CASE.format(
                test_name=test_name,
                base_url=base_url,
                path=path,
                status=status,
                title_check=title_check
            )
            test_cases.append(test_case)

        # Combine into full test file
        content = self.WEB_TEST_TEMPLATE.format(
            test_cases="\n".join(test_cases)
        )

        return {"tests/contract/web.contract.test.js": content}

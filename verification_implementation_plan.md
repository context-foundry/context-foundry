# Context Foundry Verification Implementation Plan

**Objective:** Transform Context Foundry from generating plausible code to shipping provably working software by adding deterministic verification.

**Repository:** https://github.com/snedea/context-foundry

**Timeline:** 5 phases over 4-6 weeks  
**Success Metric:** 90%+ of generated projects pass verification on first run

---

## Phase 0: Infrastructure & Setup (Week 1, Days 1-2)

### Objectives
- Create verification harness foundation
- Add verify command to CLI
- Set up artifact collection structure

### Files to Create

#### 1. `ace/verifiers/__init__.py`
```python
"""
Verification harness for Context Foundry generated projects.
Executes verify.yml and determines pass/fail deterministically.
"""
from .harness import VerificationHarness, VerificationResult, StepResult
from .primitives import RunStep, HttpStep, FileExistsStep, PortOpenStep, EnvVarSetStep

__all__ = [
    'VerificationHarness',
    'VerificationResult', 
    'StepResult',
    'RunStep',
    'HttpStep',
    'FileExistsStep',
    'PortOpenStep',
    'EnvVarSetStep'
]
```

#### 2. `ace/verifiers/harness.py`
```python
"""Core verification harness that executes verify.yml"""
import yaml
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from .primitives import get_step_executor

@dataclass
class StepResult:
    step_name: str
    step_type: str
    passed: bool
    duration_ms: int
    error_code: Optional[str] = None
    message: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None

@dataclass
class VerificationResult:
    passed: bool
    steps: List[StepResult]
    total_duration_ms: int
    artifacts_path: Path
    
    @property
    def failed_step(self) -> Optional[StepResult]:
        """Return first failed step if any"""
        for step in self.steps:
            if not step.passed:
                return step
        return None

class VerificationHarness:
    """Executes verify.yml deterministically"""
    
    def __init__(self, project_path: Path, artifacts_dir: Optional[Path] = None):
        self.project_path = Path(project_path)
        self.artifacts_dir = artifacts_dir or (self.project_path / 'artifacts')
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
    def run(self, verify_file: str = 'verify.yml') -> VerificationResult:
        """Execute verification workflow"""
        verify_path = self.project_path / verify_file
        
        if not verify_path.exists():
            return VerificationResult(
                passed=False,
                steps=[StepResult(
                    step_name="load_verify_yml",
                    step_type="setup",
                    passed=False,
                    duration_ms=0,
                    error_code="E101",
                    message=f"verify.yml not found at {verify_path}"
                )],
                total_duration_ms=0,
                artifacts_path=self.artifacts_dir
            )
        
        with open(verify_path) as f:
            config = yaml.safe_load(f)
        
        start_time = time.time()
        steps_results = []
        
        # Execute phases in order: setup, build, start, checks, tests, teardown
        phases = ['setup', 'build', 'start', 'checks', 'tests', 'teardown']
        
        for phase in phases:
            if phase not in config:
                continue
                
            phase_steps = config[phase]
            if not isinstance(phase_steps, list):
                phase_steps = [phase_steps]
            
            for idx, step in enumerate(phase_steps):
                step_name = f"{phase}_{idx}"
                result = self._execute_step(step_name, step, phase)
                steps_results.append(result)
                
                # Fail fast (except for teardown which is best-effort)
                if not result.passed and phase != 'teardown':
                    # Run teardown even if main steps fail
                    self._run_teardown(config.get('teardown', []), steps_results)
                    break
            
            # Stop processing phases if any step failed
            if steps_results and not steps_results[-1].passed and phase != 'teardown':
                break
        
        total_duration = int((time.time() - start_time) * 1000)
        all_passed = all(s.passed for s in steps_results if s.step_name.split('_')[0] != 'teardown')
        
        return VerificationResult(
            passed=all_passed,
            steps=steps_results,
            total_duration_ms=total_duration,
            artifacts_path=self.artifacts_dir
        )
    
    def _execute_step(self, name: str, step: Dict[str, Any], phase: str) -> StepResult:
        """Execute a single verification step"""
        step_executor = get_step_executor(step)
        
        step_start = time.time()
        try:
            result = step_executor.execute(
                step=step,
                project_path=self.project_path,
                artifacts_dir=self.artifacts_dir
            )
            duration = int((time.time() - step_start) * 1000)
            
            return StepResult(
                step_name=name,
                step_type=step_executor.step_type,
                passed=result.passed,
                duration_ms=duration,
                error_code=result.error_code,
                message=result.message,
                stdout=result.stdout,
                stderr=result.stderr
            )
        except Exception as e:
            duration = int((time.time() - step_start) * 1000)
            return StepResult(
                step_name=name,
                step_type="unknown",
                passed=False,
                duration_ms=duration,
                error_code="E999",
                message=f"Unexpected error: {str(e)}"
            )
    
    def _run_teardown(self, teardown_steps: List[Dict], results: List[StepResult]):
        """Best-effort teardown execution"""
        if not teardown_steps:
            return
            
        for idx, step in enumerate(teardown_steps):
            result = self._execute_step(f"teardown_{idx}", step, "teardown")
            results.append(result)
```

#### 3. `ace/verifiers/primitives.py`
```python
"""Verification step primitives (run, http, file_exists, port_open, env_var_set)"""
import subprocess
import socket
import time
import os
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

@dataclass
class ExecutionResult:
    passed: bool
    error_code: Optional[str] = None
    message: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None

class StepExecutor(ABC):
    step_type: str
    
    @abstractmethod
    def execute(self, step: Dict[str, Any], project_path: Path, artifacts_dir: Path) -> ExecutionResult:
        pass

class RunStep(StepExecutor):
    step_type = "run"
    
    def execute(self, step: Dict[str, Any], project_path: Path, artifacts_dir: Path) -> ExecutionResult:
        command = step.get('run')
        timeout = step.get('timeoutSeconds', 300)
        expect_exit = step.get('expect_exit', 0)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=project_path,
                timeout=timeout,
                capture_output=True,
                text=True
            )
            
            # Save output to artifacts
            step_artifact = artifacts_dir / f"run_{hash(command)}.log"
            with open(step_artifact, 'w') as f:
                f.write(f"COMMAND: {command}\n")
                f.write(f"EXIT CODE: {result.returncode}\n")
                f.write(f"STDOUT:\n{result.stdout}\n")
                f.write(f"STDERR:\n{result.stderr}\n")
            
            if result.returncode != expect_exit:
                return ExecutionResult(
                    passed=False,
                    error_code="E201" if result.returncode != 0 else "E202",
                    message=f"Command exited {result.returncode}, expected {expect_exit}",
                    stdout=result.stdout,
                    stderr=result.stderr
                )
            
            return ExecutionResult(passed=True, stdout=result.stdout, stderr=result.stderr)
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                passed=False,
                error_code="E203",
                message=f"Command timeout after {timeout}s"
            )
        except Exception as e:
            return ExecutionResult(
                passed=False,
                error_code="E204",
                message=f"Command execution error: {str(e)}"
            )

class HttpStep(StepExecutor):
    step_type = "http"
    
    def execute(self, step: Dict[str, Any], project_path: Path, artifacts_dir: Path) -> ExecutionResult:
        http_config = step.get('http', {})
        url = http_config.get('url')
        method = http_config.get('method', 'GET')
        headers = http_config.get('headers', {})
        body = http_config.get('body')
        expect_status = http_config.get('expect_status', 200)
        expect_body_contains = http_config.get('expect_body_contains', [])
        timeout = http_config.get('timeoutSeconds', 30)
        retry_count = http_config.get('retries', 3)
        
        if isinstance(expect_status, int):
            expect_status = [expect_status]
        
        # Retry logic with exponential backoff
        backoff = 1
        last_error = None
        
        for attempt in range(retry_count):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if body else None,
                    timeout=5,
                    allow_redirects=False
                )
                
                # Check status code
                if response.status_code not in expect_status:
                    return ExecutionResult(
                        passed=False,
                        error_code="E301",
                        message=f"HTTP {response.status_code}, expected {expect_status}",
                        stdout=response.text[:500]
                    )
                
                # Check body contains
                for substring in expect_body_contains:
                    if substring not in response.text:
                        return ExecutionResult(
                            passed=False,
                            error_code="E302",
                            message=f"Response missing expected substring: {substring}",
                            stdout=response.text[:500]
                        )
                
                return ExecutionResult(passed=True, stdout=response.text[:500])
                
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if attempt < retry_count - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 1.5, 5)
        
        return ExecutionResult(
            passed=False,
            error_code="E303",
            message=f"HTTP request failed after {retry_count} attempts: {last_error}"
        )

class FileExistsStep(StepExecutor):
    step_type = "file_exists"
    
    def execute(self, step: Dict[str, Any], project_path: Path, artifacts_dir: Path) -> ExecutionResult:
        files = step.get('file_exists', [])
        if isinstance(files, str):
            files = [files]
        
        missing = []
        for file_path in files:
            full_path = project_path / file_path
            if not full_path.exists():
                missing.append(file_path)
        
        if missing:
            return ExecutionResult(
                passed=False,
                error_code="E101",
                message=f"Missing required files: {', '.join(missing)}"
            )
        
        return ExecutionResult(passed=True)

class PortOpenStep(StepExecutor):
    step_type = "port_open"
    
    def execute(self, step: Dict[str, Any], project_path: Path, artifacts_dir: Path) -> ExecutionResult:
        port_config = step.get('port_open')
        
        if isinstance(port_config, int):
            port = port_config
            host = 'localhost'
            timeout = 30
        else:
            port = port_config.get('port')
            host = port_config.get('host', 'localhost')
            timeout = port_config.get('timeoutSeconds', 30)
        
        start = time.time()
        backoff = 1
        
        while time.time() - start < timeout:
            try:
                sock = socket.create_connection((host, port), timeout=2)
                sock.close()
                return ExecutionResult(passed=True)
            except (socket.timeout, ConnectionRefusedError, OSError):
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 5)
        
        return ExecutionResult(
            passed=False,
            error_code="E304",
            message=f"Port {port} not open after {timeout}s"
        )

class EnvVarSetStep(StepExecutor):
    step_type = "env_var_set"
    
    def execute(self, step: Dict[str, Any], project_path: Path, artifacts_dir: Path) -> ExecutionResult:
        vars_required = step.get('env_var_set', [])
        if isinstance(vars_required, str):
            vars_required = [vars_required]
        
        missing = []
        for var in vars_required:
            if var not in os.environ:
                missing.append(var)
        
        if missing:
            return ExecutionResult(
                passed=False,
                error_code="E102",
                message=f"Missing required environment variables: {', '.join(missing)}"
            )
        
        return ExecutionResult(passed=True)

# Registry
STEP_EXECUTORS = {
    'run': RunStep(),
    'http': HttpStep(),
    'file_exists': FileExistsStep(),
    'port_open': PortOpenStep(),
    'env_var_set': EnvVarSetStep()
}

def get_step_executor(step: Dict[str, Any]) -> StepExecutor:
    """Get the appropriate executor for a step"""
    for step_type, executor in STEP_EXECUTORS.items():
        if step_type in step:
            return executor
    
    raise ValueError(f"Unknown step type in: {step}")
```

#### 4. `cli/commands/verify.py`
```python
"""CLI command for verification"""
import click
from pathlib import Path
from ace.verifiers import VerificationHarness

@click.command()
@click.argument('project_path', type=click.Path(exists=True))
@click.option('--verify-file', default='verify.yml', help='Verification config file')
@click.option('--artifacts-dir', type=click.Path(), help='Artifacts output directory')
@click.option('--fail-fast/--no-fail-fast', default=True, help='Stop on first failure')
def verify(project_path, verify_file, artifacts_dir, fail_fast):
    """
    Run verification on a generated project.
    
    Executes verify.yml and reports pass/fail deterministically.
    """
    project = Path(project_path)
    artifacts = Path(artifacts_dir) if artifacts_dir else None
    
    click.echo(f"🔍 Running verification on {project.name}...")
    click.echo()
    
    harness = VerificationHarness(project, artifacts)
    result = harness.run(verify_file)
    
    # Print results
    for step in result.steps:
        status = "✅" if step.passed else "❌"
        click.echo(f"{status} {step.step_name} ({step.duration_ms}ms)")
        
        if not step.passed:
            click.echo(f"   Error {step.error_code}: {step.message}")
            if step.stderr:
                click.echo(f"   stderr: {step.stderr[:200]}")
    
    click.echo()
    click.echo(f"Total duration: {result.total_duration_ms}ms")
    click.echo(f"Artifacts saved to: {result.artifacts_path}")
    
    if result.passed:
        click.echo("✅ Verification PASSED")
        return 0
    else:
        click.echo("❌ Verification FAILED")
        if result.failed_step:
            click.echo(f"Failed at: {result.failed_step.step_name}")
            click.echo(f"Error: {result.failed_step.error_code} - {result.failed_step.message}")
        return 1
```

#### 5. Register command in `cli/__init__.py`
```python
# Add to existing imports
from cli.commands.verify import verify

# Add to CLI group
cli.add_command(verify)
```

### Files to Modify

#### 6. `requirements.txt`
```text
# Add these dependencies
PyYAML>=6.0
requests>=2.31.0
```

### Testing Instructions

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create a test verify.yml in a test project
mkdir -p test_project
cat > test_project/verify.yml << 'EOF'
version: 1
checks:
  - file_exists: [README.md]
  - run: echo "Hello World"
EOF

touch test_project/README.md

# 3. Run verification
foundry verify test_project

# Expected output:
# 🔍 Running verification on test_project...
# ✅ checks_0 (5ms)
# ✅ checks_1 (10ms)
# 
# Total duration: 15ms
# Artifacts saved to: test_project/artifacts
# ✅ Verification PASSED
```

### Success Criteria
- [ ] `foundry verify` command exists and runs
- [ ] Can execute basic verify.yml with run/file_exists steps
- [ ] Artifacts directory created with logs
- [ ] Error codes returned correctly
- [ ] Pass/fail status clear

---

## Phase 1: Complete Verification Primitives (Week 1, Days 3-5)

### Objectives
- Implement all five primitives fully
- Add retry/timeout logic
- Test with real project scenarios

### Files to Modify

#### 1. Enhance `ace/verifiers/primitives.py`
Add comprehensive error handling, artifact capture, and retry logic (already included in Phase 0 code above, but test thoroughly).

### Testing Instructions

Create comprehensive test suite:

```bash
# Create test fixtures
mkdir -p test_fixtures/api_server
cat > test_fixtures/api_server/verify.yml << 'EOF'
version: 1
setup:
  - run: python -m venv venv
  - run: source venv/bin/activate && pip install flask
start:
  - run: python app.py &
  - port_open: 5000
checks:
  - http:
      url: http://localhost:5000/health
      expect_status: 200
  - env_var_set: [PATH, HOME]
tests:
  - run: curl http://localhost:5000/health
teardown:
  - run: pkill -f "python app.py" || true
EOF

cat > test_fixtures/api_server/app.py << 'EOF'
from flask import Flask
app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'ok'}, 200

if __name__ == '__main__':
    app.run(port=5000)
EOF

# Test verification
export PATH=$PATH
export HOME=$HOME
foundry verify test_fixtures/api_server
```

### Success Criteria
- [ ] All 5 primitives work correctly (run, http, file_exists, port_open, env_var_set)
- [ ] HTTP retry with exponential backoff functions
- [ ] Port open waits for app to start
- [ ] Artifacts captured on failure
- [ ] Teardown runs even on failure

---

## Phase 2: SPEC.yaml Generation in Architect (Week 2)

### Objectives
- Add SPEC.yaml output to Architect agent
- Support API, CLI, and Web kinds
- Generate machine-readable contracts

### Files to Create

#### 1. `foundry/schemas/spec_schema.py`
```python
"""SPEC.yaml schema definitions and validation"""
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

class EndpointSpec(BaseModel):
    name: str
    method: str = "GET"
    path: str
    request: Optional[Dict] = None
    response: Dict
    example: Optional[Dict] = None

class ApiSpec(BaseModel):
    kind: Literal["api"] = "api"
    service: str
    env: Dict[str, List[str]] = Field(default_factory=lambda: {"required": []})
    contract: Dict = Field(default_factory=dict)

class CommandSpec(BaseModel):
    name: str
    args: List[str] = Field(default_factory=list)
    flags: List[Dict] = Field(default_factory=list)
    exit_codes: Dict[int, str] = Field(default_factory=lambda: {0: "success"})

class CliSpec(BaseModel):
    kind: Literal["cli"] = "cli"
    binary: str
    env: Dict[str, List[str]] = Field(default_factory=lambda: {"required": []})
    commands: List[CommandSpec]

class PageSpec(BaseModel):
    path: str
    title_contains: Optional[str] = None
    status: int = 200

class WebSpec(BaseModel):
    kind: Literal["web"] = "web"
    base_url: str = "http://localhost:3000"
    env: Dict[str, List[str]] = Field(default_factory=lambda: {"required": []})
    pages: List[PageSpec]
```

#### 2. `ace/architects/spec_generator.py`
```python
"""Generate SPEC.yaml from SPEC.md"""
import yaml
from pathlib import Path
from typing import Dict, Any

class SpecYamlGenerator:
    """Generate machine-readable SPEC.yaml from specification"""
    
    SPEC_YAML_PROMPT = """
You have written a detailed specification (SPEC.md). Now generate a machine-readable SPEC.yaml.

SPEC.md CONTENT:
{spec_content}

PROJECT TYPE: {project_type}

Generate a SPEC.yaml that captures the essential contract:

FOR API PROJECTS:
- List all endpoints (name, method, path, request schema, response schema)
- Include expected status codes
- List required environment variables
- Add example request/response for key endpoints

FOR CLI PROJECTS:
- List all commands (name, args, flags)
- Specify expected exit codes
- List required environment variables

FOR WEB PROJECTS:
- List key pages to verify (path, title_contains)
- Specify base_url
- List required environment variables

Keep it minimal - only what's needed to generate contract tests.
Include concrete examples in the 'example' field where helpful.

Output ONLY the YAML content, no markdown fences or explanations.
"""
    
    def __init__(self, client):
        self.client = client
    
    def generate(self, spec_md_content: str, project_type: str = "api") -> str:
        """Generate SPEC.yaml from SPEC.md"""
        
        prompt = self.SPEC_YAML_PROMPT.format(
            spec_content=spec_md_content,
            project_type=project_type
        )
        
        response = self.client.messages.create(
            model="claude-sonnet-4",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        spec_yaml = response.content[0].text.strip()
        
        # Validate it's proper YAML
        try:
            yaml.safe_load(spec_yaml)
        except yaml.YAMLError as e:
            raise ValueError(f"Generated invalid YAML: {e}")
        
        return spec_yaml
```

### Files to Modify

#### 3. `ace/architects/architect_agent.py`
```python
# Add to imports
from ace.architects.spec_generator import SpecYamlGenerator

# In the Architect class run method, after generating SPEC.md:
class ArchitectAgent:
    def run(self, research, project_info):
        # ... existing code to generate SPEC.md ...
        
        # NEW: Generate SPEC.yaml
        spec_generator = SpecYamlGenerator(self.client)
        
        # Detect project type from SPEC.md
        project_type = self._detect_project_type(spec_content)
        
        spec_yaml = spec_generator.generate(
            spec_md_content=spec_content,
            project_type=project_type
        )
        
        # Save SPEC.yaml alongside SPEC.md
        spec_yaml_path = self.blueprint_path / "SPEC.yaml"
        with open(spec_yaml_path, 'w') as f:
            f.write(spec_yaml)
        
        self.logger.info(f"Generated SPEC.yaml at {spec_yaml_path}")
        
        # ... continue with existing PLAN.md and TASKS.json generation ...
    
    def _detect_project_type(self, spec_content: str) -> str:
        """Detect project type from spec content"""
        spec_lower = spec_content.lower()
        
        if any(word in spec_lower for word in ['api', 'endpoint', 'rest', 'http', 'route']):
            return 'api'
        elif any(word in spec_lower for word in ['cli', 'command', 'terminal', 'shell']):
            return 'cli'
        elif any(word in spec_lower for word in ['web', 'page', 'website', 'frontend']):
            return 'web'
        
        # Default to API
        return 'api'
```

### Testing Instructions

```bash
# Run full build with SPEC.yaml generation
foundry build test-api "Build a simple REST API with GET /health endpoint"

# Check that SPEC.yaml was generated
cat examples/test-api/.foundry/blueprints/specs/SPEC.yaml

# Expected output should include:
# kind: api
# service: test-api
# contract:
#   endpoints:
#     - name: health
#       method: GET
#       path: /health
#       response:
#         status: [200]
```

### Success Criteria
- [ ] Architect generates SPEC.yaml alongside SPEC.md
- [ ] SPEC.yaml contains machine-readable contract
- [ ] Proper kind detection (api/cli/web)
- [ ] Environment variables listed
- [ ] Endpoints/commands properly structured
- [ ] Valid YAML syntax

---

## Phase 3: Contract Test Generation (Week 3)

### Objectives
- Generate contract tests from SPEC.yaml
- Support Jest (API), Pytest (CLI), basic web tests
- Freeze tests as artifacts

### Files to Create

#### 1. `ace/architects/contract_test_generator.py`
```python
"""Generate contract tests from SPEC.yaml"""
import yaml
from pathlib import Path
from typing import Dict, Any

class ContractTestGenerator:
    """Generate executable contract tests from SPEC.yaml"""
    
    API_TEST_TEMPLATE = """
// Generated contract tests from SPEC.yaml
const request = require('supertest');

describe('contract:{service_name}', () => {{
  const base = process.env.BASE_URL || '{base_url}';

{test_cases}
}});
"""
    
    API_TEST_CASE = """
  test('{test_name}', async () => {{
    const res = await request(base)
      .{method_lower}('{path}')
      {request_body}
      .redirects(0);
    
    expect({expect_status}).toContain(res.status);
    {expect_body}
  }});
"""
    
    CLI_TEST_TEMPLATE = """
# Generated contract tests from SPEC.yaml
import subprocess
import pytest

def run_cli(*args):
    result = subprocess.run(
        ['{binary}'] + list(args),
        capture_output=True,
        text=True
    )
    return result

{test_cases}
"""
    
    CLI_TEST_CASE = """
def test_{test_name}():
    result = run_cli({args})
    assert result.returncode == {expected_exit}
    {stdout_check}
"""
    
    def __init__(self, client=None):
        self.client = client
    
    def generate_from_yaml(self, spec_yaml_path: Path) -> Dict[str, str]:
        """
        Generate contract tests from SPEC.yaml
        
        Returns:
            Dict mapping filename to test content
        """
        with open(spec_yaml_path) as f:
            spec = yaml.safe_load(f)
        
        kind = spec.get('kind', 'api')
        
        if kind == 'api':
            return self._generate_api_tests(spec)
        elif kind == 'cli':
            return self._generate_cli_tests(spec)
        elif kind == 'web':
            return self._generate_web_tests(spec)
        
        raise ValueError(f"Unknown project kind: {kind}")
    
    def _generate_api_tests(self, spec: Dict) -> Dict[str, str]:
        """Generate Jest tests for API"""
        service = spec.get('service', 'service')
        base_url = spec.get('contract', {}).get('base_url', 'http://localhost:3000')
        endpoints = spec.get('contract', {}).get('endpoints', [])
        
        test_cases = []
        
        for endpoint in endpoints:
            name = endpoint.get('name', 'unnamed')
            method = endpoint.get('method', 'GET')
            path = endpoint.get('path', '/')
            response = endpoint.get('response', {})
            request_data = endpoint.get('request', {})
            
            # Build test case
            test_name = f"{method.upper()} {path} - {name}"
            
            # Request body
            request_body = ""
            if request_data and method.upper() in ['POST', 'PUT', 'PATCH']:
                example = endpoint.get('example', {}).get('request', {})
                if example:
                    request_body = f".send({example})"
            
            # Expect status
            status = response.get('status', 200)
            if isinstance(status, list):
                expect_status = f"[{','.join(map(str, status))}]"
            else:
                expect_status = f"[{status}]"
            
            # Expect body
            expect_body = ""
            response_schema = response.get('json', {})
            if response_schema:
                checks = []
                for key in response_schema.keys():
                    checks.append(f"expect(res.body).toHaveProperty('{key}');")
                expect_body = "\n    ".join(checks)
            
            test_case = self.API_TEST_CASE.format(
                test_name=test_name,
                method_lower=method.lower(),
                path=path,
                request_body=request_body,
                expect_status=expect_status,
                expect_body=expect_body
            )
            test_cases.append(test_case)
        
        content = self.API_TEST_TEMPLATE.format(
            service_name=service,
            base_url=base_url,
            test_cases="\n".join(test_cases)
        )
        
        return {f"tests/contract/{service}.contract.test.js": content}
    
    def _generate_cli_tests(self, spec: Dict) -> Dict[str, str]:
        """Generate pytest tests for CLI"""
        binary = spec.get('binary', 'app')
        commands = spec.get('commands', [])
        
        test_cases = []
        
        for cmd in commands:
            name = cmd.get('name', 'unnamed')
            args = cmd.get('args', [])
            exit_codes = cmd.get('exit_codes', {0: 'success'})
            
            # Get expected exit code (default to 0)
            expected_exit = 0
            for code in exit_codes.keys():
                expected_exit = code
                break
            
            # Build args list
            args_str = ', '.join([f"'{arg}'" for arg in args])
            
            test_case = self.CLI_TEST_CASE.format(
                test_name=name.replace('-', '_'),
                args=args_str,
                expected_exit=expected_exit,
                stdout_check=""  # Can add stdout assertions later
            )
            test_cases.append(test_case)
        
        content = self.CLI_TEST_TEMPLATE.format(
            binary=binary,
            test_cases="\n".join(test_cases)
        )
        
        return {f"tests/contract/test_{binary}_contract.py": content}
    
    def _generate_web_tests(self, spec: Dict) -> Dict[str, str]:
        """Generate basic web tests"""
        # For v1, just check pages load
        base_url = spec.get('base_url', 'http://localhost:3000')
        pages = spec.get('pages', [])
        
        test_cases = []
        for page in pages:
            path = page.get('path', '/')
            title = page.get('title_contains', '')
            status = page.get('status', 200)
            
            test_name = f"GET {path}"
            test_case = f"""
  test('{test_name}', async () => {{
    const res = await request('{base_url}').get('{path}');
    expect(res.status).toBe({status});
    {f"expect(res.text).toContain('{title}');" if title else ""}
  }});
"""
            test_cases.append(test_case)
        
        content = f"""
const request = require('supertest');

describe('contract:web', () => {{
{''.join(test_cases)}
}});
"""
        return {"tests/contract/web.contract.test.js": content}
```

### Files to Modify

#### 2. `ace/architects/architect_agent.py`
```python
# Add to imports
from ace.architects.contract_test_generator import ContractTestGenerator

# In run method, after generating SPEC.yaml:
class ArchitectAgent:
    def run(self, research, project_info):
        # ... existing SPEC.md and SPEC.yaml generation ...
        
        # NEW: Generate contract tests from SPEC.yaml
        test_generator = ContractTestGenerator()
        
        try:
            contract_tests = test_generator.generate_from_yaml(spec_yaml_path)
            
            # Write contract tests to project
            for test_file, test_content in contract_tests.items():
                test_path = self.project_path / test_file
                test_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(test_path, 'w') as f:
                    f.write(test_content)
                
                self.logger.info(f"Generated contract test: {test_file}")
            
        except Exception as e:
            self.logger.warning(f"Could not generate contract tests: {e}")
        
        # ... continue with existing workflow ...
```

### Testing Instructions

```bash
# Build a test API project
foundry build test-shortener "Build a URL shortener API with POST /shorten and GET /{code} redirect"

# Check generated files
ls examples/test-shortener/tests/contract/
# Should see: test-shortener.contract.test.js

# View the generated test
cat examples/test-shortener/tests/contract/test-shortener.contract.test.js

# Expected: Jest test with cases for POST /shorten and GET /{code}
```

### Success Criteria
- [ ] Contract tests generated from SPEC.yaml
- [ ] Tests saved to `tests/contract/` directory
- [ ] Jest tests for API projects
- [ ] Pytest tests for CLI projects
- [ ] Tests are syntactically valid
- [ ] Tests include basic assertions (status codes, required fields)

---

## Phase 4: Generate verify.yml & Make Verification Available (Week 4)

### Objectives
- Generate verify.yml during Architect phase
- Add verify step to build workflow
- Make verification non-blocking but visible

### Files to Create

#### 1. `ace/architects/verify_yml_generator.py`
```python
"""Generate verify.yml for projects"""
import yaml
from pathlib import Path
from typing import Dict, Any

class VerifyYmlGenerator:
    """Generate verify.yml based on project type and SPEC.yaml"""
    
    API_VERIFY_TEMPLATE = {
        'version': 1,
        'setup': [],
        'build': [],
        'start': [],
        'checks': [],
        'tests': [],
        'teardown': []
    }
    
    def generate(self, spec: Dict[str, Any], project_path: Path) -> str:
        """Generate verify.yml from SPEC.yaml"""
        kind = spec.get('kind', 'api')
        
        if kind == 'api':
            return self._generate_api_verify(spec, project_path)
        elif kind == 'cli':
            return self._generate_cli_verify(spec, project_path)
        elif kind == 'web':
            return self._generate_web_verify(spec, project_path)
        
        raise ValueError(f"Unknown kind: {kind}")
    
    def _generate_api_verify(self, spec: Dict, project_path: Path) -> str:
        """Generate verify.yml for API project"""
        verify = self.API_VERIFY_TEMPLATE.copy()
        
        # Detect package manager
        has_package_json = (project_path / 'package.json').exists()
        has_requirements = (project_path / 'requirements.txt').exists()
        
        # Setup phase
        if has_package_json:
            verify['setup'] = [
                {'run': 'npm ci'}
            ]
        elif has_requirements:
            verify['setup'] = [
                {'run': 'pip install -r requirements.txt'}
            ]
        
        # Build phase (if needed)
        if (project_path / 'tsconfig.json').exists():
            verify['build'] = [
                {'run': 'npm run build'}
            ]
        
        # Start phase
        port = 3000  # Default
        health_path = '/health'
        
        # Try to detect from spec
        contract = spec.get('contract', {})
        if 'health' in contract:
            health_path = contract['health'].get('path', '/health')
        
        if has_package_json:
            verify['start'] = [
                {'run': 'npm start &'},
                {'port_open': port}
            ]
        else:
            verify['start'] = [
                {'run': 'python app.py &'},
                {'port_open': port}
            ]
        
        # Checks phase
        verify['checks'] = [
            {'file_exists': ['README.md', '.env.example']},
            {
                'http': {
                    'url': f'http://localhost:{port}{health_path}',
                    'expect_status': 200
                }
            }
        ]
        
        # Check for required env vars
        env_required = spec.get('env', {}).get('required', [])
        if env_required:
            verify['checks'].insert(0, {'env_var_set': env_required})
        
        # Tests phase
        if has_package_json:
            verify['tests'] = [
                {'run': 'npm test -- tests/contract/'}
            ]
        else:
            verify['tests'] = [
                {'run': 'pytest tests/contract/ -v'}
            ]
        
        # Teardown phase
        if has_package_json:
            verify['teardown'] = [
                {'run': 'pkill -f "npm start" || true'}
            ]
        else:
            verify['teardown'] = [
                {'run': 'pkill -f "python app.py" || true'}
            ]
        
        return yaml.dump(verify, default_flow_style=False, sort_keys=False)
    
    def _generate_cli_verify(self, spec: Dict, project_path: Path) -> str:
        """Generate verify.yml for CLI project"""
        binary = spec.get('binary', 'app')
        
        verify = {
            'version': 1,
            'setup': [],
            'build': [],
            'checks': [
                {'file_exists': ['README.md', f'{binary}.py']},
            ],
            'tests': [
                {'run': 'pytest tests/contract/ -v'}
            ]
        }
        
        if (project_path / 'requirements.txt').exists():
            verify['setup'] = [{'run': 'pip install -r requirements.txt'}]
        
        return yaml.dump(verify, default_flow_style=False, sort_keys=False)
    
    def _generate_web_verify(self, spec: Dict, project_path: Path) -> str:
        """Generate verify.yml for web project"""
        base_url = spec.get('base_url', 'http://localhost:3000')
        port = 3000
        
        verify = {
            'version': 1,
            'setup': [
                {'run': 'npm ci'}
            ],
            'build': [
                {'run': 'npm run build'}
            ],
            'start': [
                {'run': 'npm start &'},
                {'port_open': port}
            ],
            'checks': [
                {
                    'http': {
                        'url': base_url,
                        'expect_status': 200
                    }
                }
            ],
            'tests': [
                {'run': 'npm test -- tests/contract/'}
            ],
            'teardown': [
                {'run': 'pkill -f "npm start" || true'}
            ]
        }
        
        return yaml.dump(verify, default_flow_style=False, sort_keys=False)
```

### Files to Modify

#### 2. `ace/architects/architect_agent.py`
```python
# Add to imports
from ace.architects.verify_yml_generator import VerifyYmlGenerator

# In run method, after generating contract tests:
class ArchitectAgent:
    def run(self, research, project_info):
        # ... existing SPEC.yaml and contract test generation ...
        
        # NEW: Generate verify.yml
        verify_generator = VerifyYmlGenerator()
        
        # Load SPEC.yaml
        with open(spec_yaml_path) as f:
            spec = yaml.safe_load(f)
        
        verify_yml = verify_generator.generate(spec, self.project_path)
        
        # Write verify.yml to project root
        verify_path = self.project_path / 'verify.yml'
        with open(verify_path, 'w') as f:
            f.write(verify_yml)
        
        self.logger.info(f"Generated verify.yml at {verify_path}")
        
        # ... continue with existing workflow ...
```

#### 3. `workflows/orchestrate.py`
```python
# Add verification step after Builder completes

# After builder finishes all tasks:
def orchestrate_build(project_name, description, autonomous=False):
    # ... existing Scout, Architect, Builder phases ...
    
    # NEW: Run verification (non-blocking in v1)
    logger.info("Running verification...")
    
    from ace.verifiers import VerificationHarness
    
    try:
        harness = VerificationHarness(project_path)
        result = harness.run()
        
        if result.passed:
            logger.info("✅ Verification PASSED")
        else:
            logger.warning("⚠️  Verification FAILED (non-blocking)")
            logger.warning(f"Failed at: {result.failed_step.step_name}")
            logger.warning(f"Error: {result.failed_step.message}")
            logger.warning(f"Run 'foundry verify {project_path}' for details")
        
        # Save result to session
        session['verification'] = {
            'passed': result.passed,
            'duration_ms': result.total_duration_ms,
            'artifacts_path': str(result.artifacts_path)
        }
        
    except Exception as e:
        logger.warning(f"Verification error (non-blocking): {e}")
    
    logger.info(f"Build complete. Project: {project_path}")
```

### Testing Instructions

```bash
# Build a full project with verification
foundry build url-short "Build URL shortener with POST /shorten and GET /{code}"

# Check generated files
ls examples/url-short/
# Should see: verify.yml, tests/contract/, .env.example, etc.

# View verify.yml
cat examples/url-short/verify.yml

# Expected: Complete verify.yml with setup/build/start/checks/tests/teardown

# Run verification manually
cd examples/url-short
foundry verify .

# Should execute the workflow and report results
```

### Success Criteria
- [ ] verify.yml generated for all projects
- [ ] Appropriate phases based on project type
- [ ] Verification runs at end of build (non-blocking)
- [ ] Results logged and saved to session
- [ ] Users can run `foundry verify` manually

---

## Phase 5: Make Verification Blocking & CI Integration (Week 5-6)

### Objectives
- Make verification blocking on build
- Add retry loop for Builder on verification failure
- Generate GitHub Actions workflow
- Add `--skip-verify` flag for development

### Files to Create

#### 1. `.github/workflows/verify.yml` (template generated by Architect)
```yaml
name: Verify

on:
  pull_request:
  push:
    branches: [main, master]

jobs:
  verify:
    strategy:
      matrix:
        os: [ubuntu-latest]
        # Add more matrix dimensions based on project type
    
    runs-on: ${{ matrix.os }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup environment
        run: |
          # Install dependencies based on project type
          # This will be generated per-project
      
      - name: Load environment
        run: |
          cp .env.example .env || true
      
      - name: Run verification
        run: |
          # Install foundry (or use Docker)
          pip install -r requirements.txt || npm ci || true
          
          # Run verify
          python -m ace.verifiers.cli .
      
      - name: Upload artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: verify-artifacts-${{ matrix.os }}
          path: |
            artifacts/
            logs/
            *.log
```

#### 2. `ace/architects/ci_workflow_generator.py`
```python
"""Generate GitHub Actions workflow for verification"""
from pathlib import Path
from typing import Dict

class CIWorkflowGenerator:
    """Generate .github/workflows/verify.yml"""
    
    def generate(self, spec: Dict, project_path: Path) -> str:
        """Generate CI workflow based on project type"""
        kind = spec.get('kind', 'api')
        
        # Detect language/runtime
        has_package_json = (project_path / 'package.json').exists()
        has_requirements = (project_path / 'requirements.txt').exists()
        
        setup_steps = []
        
        if has_package_json:
            setup_steps.append("npm ci")
        elif has_requirements:
            setup_steps.append("pip install -r requirements.txt")
        
        workflow = f"""name: Verify

on:
  pull_request:
  push:
    branches: [main, master]

jobs:
  verify:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        if: ${{{{ hashFiles('package.json') }}}}
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Setup Python
        if: ${{{{ hashFiles('requirements.txt') }}}}
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
{chr(10).join(f'          {step}' for step in setup_steps)}
      
      - name: Copy environment template
        run: cp .env.example .env || true
      
      - name: Run verification
        run: |
          pip install PyYAML requests
          python -c "
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd()))
from ace.verifiers import VerificationHarness
result = VerificationHarness(Path('.')).run()
sys.exit(0 if result.passed else 1)
"
      
      - name: Upload artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: verify-artifacts
          path: |
            artifacts/
            logs/
            *.log
"""
        return workflow
```

### Files to Modify

#### 3. `ace/architects/architect_agent.py`
```python
# Add to imports
from ace.architects.ci_workflow_generator import CIWorkflowGenerator

# In run method, after generating verify.yml:
class ArchitectAgent:
    def run(self, research, project_info):
        # ... existing generation ...
        
        # NEW: Generate GitHub Actions workflow
        ci_generator = CIWorkflowGenerator()
        workflow_content = ci_generator.generate(spec, self.project_path)
        
        workflow_path = self.project_path / '.github' / 'workflows' / 'verify.yml'
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(workflow_path, 'w') as f:
            f.write(workflow_content)
        
        self.logger.info(f"Generated CI workflow at {workflow_path}")
```

#### 4. `workflows/orchestrate.py` - Make verification blocking
```python
def orchestrate_build(project_name, description, autonomous=False, skip_verify=False):
    # ... existing Scout, Architect, Builder phases ...
    
    if skip_verify:
        logger.info("Skipping verification (--skip-verify)")
        return session
    
    # Run verification (NOW BLOCKING)
    logger.info("Running verification (blocking)...")
    
    max_verify_attempts = 3
    verify_attempt = 0
    
    while verify_attempt < max_verify_attempts:
        verify_attempt += 1
        
        harness = VerificationHarness(project_path)
        result = harness.run()
        
        if result.passed:
            logger.info("✅ Verification PASSED")
            break
        
        logger.warning(f"❌ Verification FAILED (attempt {verify_attempt}/{max_verify_attempts})")
        logger.warning(f"Failed at: {result.failed_step.step_name}")
        logger.warning(f"Error: {result.failed_step.error_code} - {result.failed_step.message}")
        
        if verify_attempt < max_verify_attempts:
            logger.info("Asking Builder to fix verification failure...")
            
            # Feed error back to Builder
            fix_task = {
                'id': f'fix_verification_{verify_attempt}',
                'description': f'Fix verification failure: {result.failed_step.message}',
                'context': {
                    'failed_step': result.failed_step.step_name,
                    'error_code': result.failed_step.error_code,
                    'error_message': result.failed_step.message,
                    'stderr': result.failed_step.stderr,
                    'artifacts': str(result.artifacts_path)
                }
            }
            
            builder.execute_task(fix_task)
        else:
            logger.error("❌ Verification failed after max attempts")
            logger.error(f"Manual intervention required. Run: foundry verify {project_path}")
            
            if not autonomous:
                # Ask user if they want to continue anyway
                response = input("Verification failed. Continue anyway? [y/N]: ")
                if response.lower() != 'y':
                    raise Exception("Build failed verification")
    
    # Save verification result
    session['verification'] = {
        'passed': result.passed,
        'attempts': verify_attempt,
        'duration_ms': result.total_duration_ms
    }
    
    return session
```

#### 5. `cli/commands/build.py`
```python
# Add --skip-verify flag
@click.option('--skip-verify', is_flag=True, help='Skip verification step')
def build(name, description, autonomous, overnight, livestream, push, skip_verify):
    """Build a new project"""
    
    session = orchestrate_build(
        project_name=name,
        description=description,
        autonomous=autonomous,
        skip_verify=skip_verify
    )
    
    # ... rest of build command ...
```

### Testing Instructions

```bash
# Test full blocking verification
foundry build test-blocking "Simple API with health endpoint"

# Should see verification run and pass/fail

# Test verification retry on failure
# (Inject a failure in verify.yml to test)

# Test skip-verify flag
foundry build test-skip "Another API" --skip-verify

# Should skip verification entirely

# Test CI workflow
cd examples/test-blocking
git init
git add .
git commit -m "Initial commit"
# Push to GitHub and check Actions tab
```

### Success Criteria
- [ ] Verification blocks build by default
- [ ] Builder retries on verification failure (up to 3x)
- [ ] `--skip-verify` flag works
- [ ] GitHub Actions workflow generated
- [ ] CI runs verification automatically
- [ ] Artifacts uploaded on failure
- [ ] Clear error messages guide fixes

---

## Phase 6: Polish & Documentation (Week 6)

### Objectives
- Document verification system
- Add tutorial for URL shortener example
- Create troubleshooting guide
- Add metrics/telemetry

### Files to Create

#### 1. `docs/VERIFICATION.md`
```markdown
# Verification System

Context Foundry includes deterministic verification to ensure generated code actually works.

## How It Works

1. **SPEC.yaml**: Machine-readable contract generated from SPEC.md
2. **Contract Tests**: Generated from SPEC.yaml, frozen as artifacts
3. **verify.yml**: Defines verification steps (setup/build/start/checks/tests/teardown)
4. **Verification Harness**: Executes verify.yml deterministically

## verify.yml Format

[Document the DSL with examples]

## Error Codes

- E10x: Environment/structural errors
- E20x: Build/install errors
- E30x: Start/health errors
- E40x: Contract test failures
- E50x: Teardown errors

## Debugging Failures

[Step-by-step debugging guide]

## Customizing Verification

[How to edit verify.yml and contract tests]
```

#### 2. `docs/TUTORIAL_VERIFICATION.md`
```markdown
# Verification Tutorial: URL Shortener

Walk through the verification system using the URL shortener example.

[Complete tutorial with expected outputs at each step]
```

#### 3. `examples/url-shortener/README.md`
```markdown
# URL Shortener - Reference Implementation

This project demonstrates Context Foundry's verification system.

## Quick Start

```bash
# Install dependencies
npm ci

# Run verification
foundry verify .

# Start the app
npm start
```

## What Gets Verified

- All dependencies install correctly
- App starts and binds to port 3000
- Health endpoint returns 200
- POST /shorten creates short URLs
- GET /{code} redirects correctly

## Files Generated

- `SPEC.yaml`: Machine-readable contract
- `verify.yml`: Verification steps
- `tests/contract/`: Contract tests
- `.github/workflows/verify.yml`: CI workflow
```

### Files to Modify

#### 4. Main `README.md`
Add verification section:

```markdown
## Verification System ✅

Context Foundry ensures generated code actually works through deterministic verification:

- **Machine-readable specs** (SPEC.yaml)
- **Contract tests** generated from specs
- **Automated verification** (setup → build → start → test)
- **CI integration** (GitHub Actions)

Every generated project includes `verify.yml` that proves it works in a clean environment.

See [Verification Guide](docs/VERIFICATION.md) for details.
```

### Testing Instructions

```bash
# Build the reference URL shortener
foundry build url-shortener "URL shortener REST API"

# Should generate complete, verified project

# Run through tutorial
# Follow docs/TUTORIAL_VERIFICATION.md step-by-step

# Verify all examples work
for dir in examples/*/; do
    echo "Verifying $dir"
    foundry verify "$dir" || echo "FAILED: $dir"
done
```

### Success Criteria
- [ ] Complete verification documentation
- [ ] Tutorial with URL shortener
- [ ] All examples have working verification
- [ ] Troubleshooting guide covers common errors
- [ ] README updated with verification info
- [ ] Error messages are actionable

---

## Rollout Plan

### Week 1
- Phase 0: Infrastructure (Days 1-2)
- Phase 1: Complete primitives (Days 3-5)

### Week 2
- Phase 2: SPEC.yaml generation

### Week 3
- Phase 3: Contract test generation

### Week 4
- Phase 4: verify.yml generation
- Start Phase 5: Blocking verification

### Week 5
- Complete Phase 5: CI integration
- Begin Phase 6: Polish

### Week 6
- Complete Phase 6: Documentation
- User testing & bug fixes

---

## Success Metrics

After full implementation:

- [ ] **90%+ projects pass verification on first run**
- [ ] **Verification completes in <90 seconds**
- [ ] **Zero manual intervention for clean environment**
- [ ] **All examples in repo verify successfully**
- [ ] **CI integration works on GitHub**
- [ ] **Error messages are actionable**
- [ ] **Documentation complete and tested**

---

## Notes for Claude Code

### Key Implementation Principles

1. **Incremental**: Each phase builds on previous, all testable independently
2. **Backward compatible**: Existing projects continue to work
3. **Fail gracefully**: Verification errors should be clear and actionable
4. **Frozen artifacts**: Contract tests are committed, not regenerated
5. **Deterministic**: Same project should verify identically every time

### Testing Strategy

- Test each phase independently before moving to next
- Use URL shortener as reference implementation
- Keep test fixtures in `test_fixtures/`
- Run full verification suite before marking phase complete

### Common Pitfalls to Avoid

- Don't regenerate tests on every run (breaks reproducibility)
- Don't make SPEC.yaml too rigid (allow flexibility)
- Don't skip retry logic (apps take time to start)
- Don't forget teardown (cleanup is critical)
- Don't make errors cryptic (be specific and actionable)

### Getting Help

If stuck on any phase:
1. Review the document that inspired this (in context)
2. Check existing Context Foundry patterns
3. Test with minimal examples first
4. Ask for clarification before proceeding

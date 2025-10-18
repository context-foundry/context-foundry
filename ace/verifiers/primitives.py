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

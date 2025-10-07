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

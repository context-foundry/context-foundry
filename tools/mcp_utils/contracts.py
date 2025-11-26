"""
Phase Contracts for Context Foundry Pipeline

Validates inputs and outputs for each pipeline phase.
Part of Milestone 2: Selective Phase Execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
import json
import glob


class ValidationResult(str, Enum):
    """Result of a contract validation"""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"  # Non-blocking issue
    SKIPPED = "skipped"  # Validation not applicable


@dataclass
class ContractViolation:
    """Details of a contract violation"""

    rule: str
    message: str
    severity: ValidationResult
    path: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ContractValidationResult:
    """Result of validating a contract"""

    phase: str
    contract_type: str  # "input" or "output"
    result: ValidationResult
    violations: List[ContractViolation] = field(default_factory=list)
    warnings: List[ContractViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.result in (ValidationResult.PASSED, ValidationResult.WARNING)

    def add_violation(self, violation: ContractViolation):
        if violation.severity == ValidationResult.WARNING:
            self.warnings.append(violation)
        else:
            self.violations.append(violation)
            self.result = ValidationResult.FAILED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "contract_type": self.contract_type,
            "result": self.result.value,
            "violations": [
                {
                    "rule": v.rule,
                    "message": v.message,
                    "severity": v.severity.value,
                    "path": v.path,
                    "suggestion": v.suggestion,
                }
                for v in self.violations
            ],
            "warnings": [
                {
                    "rule": w.rule,
                    "message": w.message,
                    "severity": w.severity.value,
                    "path": w.path,
                    "suggestion": w.suggestion,
                }
                for w in self.warnings
            ],
        }


class ContractValidator:
    """
    Validates phase contracts (inputs and outputs).

    Supports:
    - File existence checks
    - File content validation
    - Custom validation rules
    - Warning vs. blocking modes
    """

    def __init__(self, working_directory: Path, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            working_directory: Project working directory
            strict_mode: If True, warnings become blocking errors
        """
        self.working_directory = Path(working_directory)
        self.strict_mode = strict_mode

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to working directory"""
        if path.startswith("/"):
            return Path(path)
        return self.working_directory / path

    def _check_file_exists(self, path: str) -> tuple:
        """
        Check if a file exists.

        Returns:
            Tuple of (exists: bool, resolved_path: Path)
        """
        resolved = self._resolve_path(path)

        # Handle glob patterns
        if "*" in path:
            matches = list(glob.glob(str(resolved)))
            return (len(matches) > 0, resolved)

        return (resolved.exists(), resolved)

    def _check_file_not_empty(self, path: str) -> tuple:
        """
        Check if a file exists and is not empty.

        Returns:
            Tuple of (valid: bool, size: int)
        """
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return (False, 0)
        size = resolved.stat().st_size
        return (size > 0, size)

    def _check_json_valid(self, path: str) -> tuple:
        """
        Check if a file contains valid JSON.

        Returns:
            Tuple of (valid: bool, error: Optional[str])
        """
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return (False, "File does not exist")
        try:
            with open(resolved) as f:
                json.load(f)
            return (True, None)
        except json.JSONDecodeError as e:
            return (False, str(e))

    def validate_input_contract(
        self, phase_name: str, required_inputs: List[str]
    ) -> ContractValidationResult:
        """
        Validate that all required inputs exist before a phase starts.

        Args:
            phase_name: Name of the phase
            required_inputs: List of required input paths

        Returns:
            ContractValidationResult
        """
        result = ContractValidationResult(
            phase=phase_name,
            contract_type="input",
            result=ValidationResult.PASSED,
        )

        if not required_inputs:
            return result

        for input_path in required_inputs:
            exists, resolved = self._check_file_exists(input_path)

            if not exists:
                result.add_violation(
                    ContractViolation(
                        rule="required_input",
                        message=f"Required input not found: {input_path}",
                        severity=ValidationResult.FAILED,
                        path=str(resolved),
                        suggestion=f"Run the previous phase to generate {input_path}",
                    )
                )
            else:
                # Check file is not empty
                not_empty, size = self._check_file_not_empty(input_path)
                if not not_empty:
                    result.add_violation(
                        ContractViolation(
                            rule="non_empty_input",
                            message=f"Required input is empty: {input_path}",
                            severity=ValidationResult.WARNING
                            if not self.strict_mode
                            else ValidationResult.FAILED,
                            path=str(resolved),
                            suggestion="Regenerate this file by re-running the previous phase",
                        )
                    )

        return result

    def validate_output_contract(
        self, phase_name: str, required_outputs: List[str]
    ) -> ContractValidationResult:
        """
        Validate that all required outputs exist after a phase completes.

        Args:
            phase_name: Name of the phase
            required_outputs: List of required output paths

        Returns:
            ContractValidationResult
        """
        result = ContractValidationResult(
            phase=phase_name,
            contract_type="output",
            result=ValidationResult.PASSED,
        )

        if not required_outputs:
            return result

        for output_path in required_outputs:
            exists, resolved = self._check_file_exists(output_path)

            if not exists:
                result.add_violation(
                    ContractViolation(
                        rule="required_output",
                        message=f"Required output not created: {output_path}",
                        severity=ValidationResult.FAILED,
                        path=str(resolved),
                        suggestion=f"Phase {phase_name} should create {output_path}",
                    )
                )
            else:
                # Check file is not empty
                not_empty, size = self._check_file_not_empty(output_path)
                if not not_empty:
                    result.add_violation(
                        ContractViolation(
                            rule="non_empty_output",
                            message=f"Required output is empty: {output_path}",
                            severity=ValidationResult.WARNING
                            if not self.strict_mode
                            else ValidationResult.FAILED,
                            path=str(resolved),
                            suggestion="Check phase execution logs for errors",
                        )
                    )

        return result


# Phase-specific validators
def validate_scout_output(working_dir: Path) -> ContractValidationResult:
    """Validate Scout phase output"""
    result = ContractValidationResult(
        phase="Scout",
        contract_type="output",
        result=ValidationResult.PASSED,
    )

    # Check for scout-report.md (required)
    scout_md = working_dir / ".context-foundry" / "scout-report.md"
    scout_json = working_dir / ".context-foundry" / "scout_report.json"

    if not scout_md.exists():
        result.add_violation(
            ContractViolation(
                rule="required_output",
                message="Scout report not created: scout-report.md",
                severity=ValidationResult.FAILED,
                path=str(scout_md),
                suggestion="Scout phase should create .context-foundry/scout-report.md",
            )
        )
    else:
        content = scout_md.read_text()
        # Check for key sections
        required_sections = ["## Key Requirements", "## Technology Stack"]
        for section in required_sections:
            if section not in content:
                result.add_violation(
                    ContractViolation(
                        rule="scout_section_missing",
                        message=f"Scout report missing section: {section}",
                        severity=ValidationResult.WARNING,
                        path=str(scout_md),
                        suggestion=f"Scout report should include {section}",
                    )
                )

    # scout_report.json is optional but good to have
    if not scout_json.exists():
        result.add_violation(
            ContractViolation(
                rule="scout_json_missing",
                message="Scout BAML output not created: scout_report.json (optional)",
                severity=ValidationResult.WARNING,
                path=str(scout_json),
                suggestion="BAML parsing may have timed out - scout-report.md will be used",
            )
        )

    return result


def validate_architect_output(working_dir: Path) -> ContractValidationResult:
    """Validate Architect phase output"""
    result = ContractValidationResult(
        phase="Architect",
        contract_type="output",
        result=ValidationResult.PASSED,
    )

    # Check for architecture files - JSON is the primary contract
    arch_json = working_dir / ".context-foundry" / "architecture.json"
    arch_md = working_dir / ".context-foundry" / "architecture.md"

    if not arch_json.exists():
        if arch_md.exists():
            # MD exists but JSON doesn't - warn but don't fail
            result.add_violation(
                ContractViolation(
                    rule="architect_json_missing",
                    message="architecture.json not created (architecture.md exists as fallback)",
                    severity=ValidationResult.WARNING,
                    path=str(arch_json),
                    suggestion="BAML parsing may have timed out - architecture.md will be used",
                )
            )
        else:
            # Neither exists - fail
            result.add_violation(
                ContractViolation(
                    rule="required_output",
                    message="Architecture not created: neither architecture.json nor architecture.md",
                    severity=ValidationResult.FAILED,
                    path=str(arch_json),
                    suggestion="Architect phase should create architecture files",
                )
            )
    else:
        # Validate JSON is parseable
        try:
            with open(arch_json) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            result.add_violation(
                ContractViolation(
                    rule="architect_json_invalid",
                    message=f"architecture.json is invalid JSON: {e}",
                    severity=ValidationResult.FAILED,
                    path=str(arch_json),
                    suggestion="Check BAML parsing logs for errors",
                )
            )

    return result


def validate_builder_output(working_dir: Path) -> ContractValidationResult:
    """Validate Builder phase output"""
    result = ContractValidationResult(
        phase="Builder",
        contract_type="output",
        result=ValidationResult.PASSED,
    )

    # Check for source files (any code files)
    code_extensions = [
        "*.py",
        "*.js",
        "*.ts",
        "*.tsx",
        "*.jsx",
        "*.go",
        "*.rs",
        "*.java",
    ]
    has_code = False

    for ext in code_extensions:
        matches = list(working_dir.glob(f"**/{ext}"))
        # Exclude node_modules, .venv, etc.
        matches = [
            m
            for m in matches
            if "node_modules" not in str(m)
            and ".venv" not in str(m)
            and ".context-foundry" not in str(m)
        ]
        if matches:
            has_code = True
            break

    if not has_code:
        result.add_violation(
            ContractViolation(
                rule="builder_code_created",
                message="Builder phase did not create any source files",
                severity=ValidationResult.FAILED,
                suggestion="Check Builder phase logs for errors",
            )
        )

    return result


def validate_test_output(working_dir: Path) -> ContractValidationResult:
    """Validate Test phase output"""
    validator = ContractValidator(working_dir)
    result = validator.validate_output_contract(
        "Test", [".context-foundry/test-report.md"]
    )

    # Check test report for PASSED status
    test_report = working_dir / ".context-foundry" / "test-report.md"
    if test_report.exists():
        content = test_report.read_text().lower()
        if "failed" in content and "passed" not in content:
            result.add_violation(
                ContractViolation(
                    rule="test_passed",
                    message="Test report indicates failures",
                    severity=ValidationResult.WARNING,
                    path=str(test_report),
                    suggestion="Review test failures and fix issues",
                )
            )

    return result


# Mapping of phase names to their output validators
PHASE_OUTPUT_VALIDATORS: Dict[str, Callable[[Path], ContractValidationResult]] = {
    "Scout": validate_scout_output,
    "Architect": validate_architect_output,
    "Builder": validate_builder_output,
    "Test": validate_test_output,
}


def validate_phase_inputs(
    phase_name: str, working_dir: Path, required_inputs: List[str]
) -> ContractValidationResult:
    """
    Validate inputs for a phase.

    Args:
        phase_name: Name of the phase
        working_dir: Working directory
        required_inputs: List of required input paths

    Returns:
        ContractValidationResult
    """
    validator = ContractValidator(working_dir)
    return validator.validate_input_contract(phase_name, required_inputs)


def validate_phase_outputs(
    phase_name: str, working_dir: Path, required_outputs: Optional[List[str]] = None
) -> ContractValidationResult:
    """
    Validate outputs for a phase.

    Uses phase-specific validators if available, otherwise does generic validation.

    Args:
        phase_name: Name of the phase
        working_dir: Working directory
        required_outputs: Optional list of required output paths (uses defaults if None)

    Returns:
        ContractValidationResult
    """
    # Use phase-specific validator if available
    if phase_name in PHASE_OUTPUT_VALIDATORS:
        return PHASE_OUTPUT_VALIDATORS[phase_name](working_dir)

    # Fall back to generic validation
    if required_outputs:
        validator = ContractValidator(working_dir)
        return validator.validate_output_contract(phase_name, required_outputs)

    # No validation needed
    return ContractValidationResult(
        phase=phase_name,
        contract_type="output",
        result=ValidationResult.PASSED,
    )

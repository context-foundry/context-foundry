"""
Pre-flight Checks for Context Foundry Pipeline

Validates inputs, environment, and preconditions before phase execution.
Part of Milestone 3: Safety Mechanisms.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import shutil


class PreflightStatus(str, Enum):
    """Result of a pre-flight check"""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class PreflightCheck:
    """Result of a single pre-flight check"""

    name: str
    status: PreflightStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    blocking: bool = True  # If True, failure blocks execution


@dataclass
class PreflightResult:
    """Aggregated result of all pre-flight checks"""

    phase: str
    passed: bool
    checks: List[PreflightCheck] = field(default_factory=list)
    warnings: List[PreflightCheck] = field(default_factory=list)
    failures: List[PreflightCheck] = field(default_factory=list)

    def add_check(self, check: PreflightCheck):
        """Add a check result"""
        self.checks.append(check)
        if check.status == PreflightStatus.WARNING:
            self.warnings.append(check)
        elif check.status == PreflightStatus.FAILED and check.blocking:
            self.failures.append(check)
            self.passed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "passed": self.passed,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                    "blocking": c.blocking,
                }
                for c in self.checks
            ],
            "warning_count": len(self.warnings),
            "failure_count": len(self.failures),
        }


class PreflightValidator:
    """
    Validates preconditions before phase execution.

    Checks include:
    - Required input files exist
    - Working directory is valid and writable
    - Disk space is sufficient
    - Required tools are available
    - Environment variables are set
    """

    def __init__(
        self,
        working_directory: Path,
        min_disk_space_mb: int = 100,
        required_tools: Optional[List[str]] = None,
    ):
        self.working_directory = Path(working_directory)
        self.min_disk_space_mb = min_disk_space_mb
        self.required_tools = required_tools or []

    def check_working_directory(self) -> PreflightCheck:
        """Verify working directory exists and is writable"""
        if not self.working_directory.exists():
            return PreflightCheck(
                name="working_directory_exists",
                status=PreflightStatus.FAILED,
                message=f"Working directory does not exist: {self.working_directory}",
                blocking=True,
            )

        if not self.working_directory.is_dir():
            return PreflightCheck(
                name="working_directory_is_dir",
                status=PreflightStatus.FAILED,
                message=f"Path is not a directory: {self.working_directory}",
                blocking=True,
            )

        # Check writable
        test_file = self.working_directory / ".preflight_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return PreflightCheck(
                name="working_directory_writable",
                status=PreflightStatus.PASSED,
                message=f"Working directory is writable: {self.working_directory}",
            )
        except (OSError, PermissionError) as e:
            return PreflightCheck(
                name="working_directory_writable",
                status=PreflightStatus.FAILED,
                message=f"Working directory is not writable: {e}",
                blocking=True,
            )

    def check_disk_space(self) -> PreflightCheck:
        """Verify sufficient disk space is available"""
        try:
            usage = shutil.disk_usage(self.working_directory)
            free_mb = usage.free / (1024 * 1024)

            if free_mb < self.min_disk_space_mb:
                return PreflightCheck(
                    name="disk_space",
                    status=PreflightStatus.FAILED,
                    message=f"Insufficient disk space: {free_mb:.0f}MB free, need {self.min_disk_space_mb}MB",
                    details={"free_mb": free_mb, "required_mb": self.min_disk_space_mb},
                    blocking=True,
                )

            return PreflightCheck(
                name="disk_space",
                status=PreflightStatus.PASSED,
                message=f"Sufficient disk space: {free_mb:.0f}MB free",
                details={"free_mb": free_mb},
            )
        except OSError as e:
            return PreflightCheck(
                name="disk_space",
                status=PreflightStatus.WARNING,
                message=f"Could not check disk space: {e}",
                blocking=False,
            )

    def check_required_inputs(self, required_inputs: List[str]) -> List[PreflightCheck]:
        """Verify all required input files exist"""
        checks = []
        for input_path in required_inputs:
            full_path = self.working_directory / input_path
            if full_path.exists():
                # Check file is not empty
                if full_path.stat().st_size == 0:
                    checks.append(
                        PreflightCheck(
                            name=f"input_{input_path}",
                            status=PreflightStatus.WARNING,
                            message=f"Required input exists but is empty: {input_path}",
                            blocking=False,
                        )
                    )
                else:
                    checks.append(
                        PreflightCheck(
                            name=f"input_{input_path}",
                            status=PreflightStatus.PASSED,
                            message=f"Required input exists: {input_path}",
                        )
                    )
            else:
                checks.append(
                    PreflightCheck(
                        name=f"input_{input_path}",
                        status=PreflightStatus.FAILED,
                        message=f"Required input missing: {input_path}",
                        blocking=True,
                    )
                )
        return checks

    def check_required_tools(self) -> List[PreflightCheck]:
        """Verify required command-line tools are available"""
        checks = []
        for tool in self.required_tools:
            if shutil.which(tool):
                checks.append(
                    PreflightCheck(
                        name=f"tool_{tool}",
                        status=PreflightStatus.PASSED,
                        message=f"Required tool available: {tool}",
                    )
                )
            else:
                checks.append(
                    PreflightCheck(
                        name=f"tool_{tool}",
                        status=PreflightStatus.FAILED,
                        message=f"Required tool not found: {tool}",
                        blocking=True,
                    )
                )
        return checks

    def check_json_valid(self, json_files: List[str]) -> List[PreflightCheck]:
        """Verify JSON files are valid and parseable"""
        checks = []
        for json_path in json_files:
            full_path = self.working_directory / json_path
            if not full_path.exists():
                continue  # Skip non-existent files (handled by input check)

            try:
                with open(full_path) as f:
                    json.load(f)
                checks.append(
                    PreflightCheck(
                        name=f"json_valid_{json_path}",
                        status=PreflightStatus.PASSED,
                        message=f"JSON file is valid: {json_path}",
                    )
                )
            except json.JSONDecodeError as e:
                checks.append(
                    PreflightCheck(
                        name=f"json_valid_{json_path}",
                        status=PreflightStatus.FAILED,
                        message=f"Invalid JSON in {json_path}: {e}",
                        blocking=True,
                    )
                )
        return checks

    def check_architecture_exists(self) -> PreflightCheck:
        """Check that either architecture.json or architecture.md exists."""
        json_path = self.working_directory / ".context-foundry" / "architecture.json"
        md_path = self.working_directory / ".context-foundry" / "architecture.md"

        if json_path.exists():
            return PreflightCheck(
                name="architecture_exists",
                status=PreflightStatus.PASSED,
                message=f"Architecture JSON found: {json_path}",
                blocking=False,
            )
        elif md_path.exists():
            return PreflightCheck(
                name="architecture_exists",
                status=PreflightStatus.PASSED,
                message=f"Architecture MD found (JSON fallback): {md_path}",
                blocking=False,
            )
        else:
            return PreflightCheck(
                name="architecture_exists",
                status=PreflightStatus.FAILED,
                message="Neither architecture.json nor architecture.md found",
                blocking=True,
            )

    def run_preflight(
        self,
        phase_name: str,
        required_inputs: Optional[List[str]] = None,
        json_inputs: Optional[List[str]] = None,
        custom_check: Optional[str] = None,
    ) -> PreflightResult:
        """
        Run all pre-flight checks for a phase.

        Args:
            phase_name: Name of the phase being validated
            required_inputs: List of required input file paths
            json_inputs: List of JSON files to validate

        Returns:
            PreflightResult with all check results
        """
        result = PreflightResult(phase=phase_name, passed=True)

        # Core checks
        result.add_check(self.check_working_directory())
        result.add_check(self.check_disk_space())

        # Required inputs
        if required_inputs:
            for check in self.check_required_inputs(required_inputs):
                result.add_check(check)

        # JSON validation
        if json_inputs:
            for check in self.check_json_valid(json_inputs):
                result.add_check(check)

        # Required tools
        for check in self.check_required_tools():
            result.add_check(check)

        # Custom checks
        if custom_check == "architecture_exists":
            result.add_check(self.check_architecture_exists())

        return result


def run_phase_preflight(
    phase_name: str,
    working_directory: Path,
    required_inputs: Optional[List[str]] = None,
    json_inputs: Optional[List[str]] = None,
    required_tools: Optional[List[str]] = None,
    custom_check: Optional[str] = None,
) -> PreflightResult:
    """
    Convenience function to run pre-flight checks for a phase.

    Args:
        phase_name: Name of the phase
        working_directory: Project working directory
        required_inputs: Required input files
        json_inputs: JSON files to validate
        required_tools: Required CLI tools
        custom_check: Optional custom check name (e.g., "architecture_exists")

    Returns:
        PreflightResult
    """
    validator = PreflightValidator(
        working_directory=working_directory,
        required_tools=required_tools or [],
    )
    return validator.run_preflight(
        phase_name=phase_name,
        required_inputs=required_inputs,
        json_inputs=json_inputs,
        custom_check=custom_check,
    )


# Phase-specific preflight configurations
PHASE_PREFLIGHT_CONFIG: Dict[str, Dict[str, Any]] = {
    "Scout": {
        "required_inputs": [],
        "json_inputs": [],
        "required_tools": ["claude"],
    },
    "Architect": {
        "required_inputs": [".context-foundry/scout_report.json"],
        "json_inputs": [".context-foundry/scout_report.json"],
        "required_tools": ["claude"],
    },
    "Builder": {
        # architecture.json OR architecture.md - preflight accepts either
        # JSON is preferred but MD is valid fallback when BAML parsing fails
        "required_inputs": [],  # Handled by custom check below
        "json_inputs": [],  # Don't require JSON validation
        "required_tools": ["claude"],
        "custom_check": "architecture_exists",  # Check for .json OR .md
    },
    "Test": {
        "required_inputs": [],
        "json_inputs": [],
        "required_tools": [],  # Varies by project type
    },
    "Screenshot": {
        "required_inputs": [],  # Optional phase - no hard requirements
        "json_inputs": [],
        "required_tools": [],  # Playwright installed at runtime
    },
    "Documentation": {
        "required_inputs": [],  # Optional phase - no hard requirements
        "json_inputs": [],
        "required_tools": ["claude"],
    },
    "Deploy": {
        "required_inputs": ["README.md"],
        "json_inputs": [],
        "required_tools": ["git", "gh"],
    },
}


def get_phase_preflight_config(phase_name: str) -> Dict[str, Any]:
    """Get pre-flight configuration for a phase"""
    return PHASE_PREFLIGHT_CONFIG.get(phase_name, {})

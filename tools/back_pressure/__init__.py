"""
Back Pressure System - Validation friction for early error detection

This package provides validation checkpoints at different phases of the build pipeline
to catch errors before expensive test execution.

Modules:
    validate_tech_stack: Scout phase tech stack feasibility validation
    validate_architecture: Architect phase design soundness validation
    integration_pre_check: Phase 3.5 fast syntax/import validation
    back_pressure_config: Language-specific validation configurations
"""

from .validate_tech_stack import validate_tech_stack, extract_tech_stack
from .validate_architecture import validate_architecture
from .integration_pre_check import integration_pre_check
from .back_pressure_config import get_back_pressure_config, LANGUAGE_PROFILES

__version__ = "1.0.0"

__all__ = [
    "validate_tech_stack",
    "extract_tech_stack",
    "validate_architecture",
    "integration_pre_check",
    "get_back_pressure_config",
    "LANGUAGE_PROFILES",
]

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

"""
Architect agent components for Context Foundry.
Responsible for generating specifications and machine-readable contracts.
"""
from .spec_generator import SpecYamlGenerator
from .contract_test_generator import ContractTestGenerator

__all__ = ['SpecYamlGenerator', 'ContractTestGenerator']

"""
Phase Registry for Context Foundry Pipeline

Defines all pipeline phases, their dependencies, and metadata.
Part of Milestone 2: Selective Phase Execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PhaseId(str, Enum):
    """Canonical phase identifiers"""

    SCOUT = "Scout"
    ARCHITECT = "Architect"
    BUILDER = "Builder"
    TEST = "Test"
    SCREENSHOT = "Screenshot"
    DOCUMENTATION = "Documentation"
    DEPLOY = "Deploy"
    FEEDBACK = "Feedback"


@dataclass
class PhaseDefinition:
    """
    Definition of a pipeline phase including dependencies and constraints.

    Attributes:
        id: Unique phase identifier
        name: Human-readable name
        description: What this phase does
        depends_on: List of phases that must complete before this one
        timeout_seconds: Maximum execution time (default: 600s = 10min)
        required_inputs: Files/artifacts that must exist before phase starts
        required_outputs: Files/artifacts that must exist after phase completes
        approval_required: Whether human approval is needed before this phase
        can_skip: Whether this phase can be skipped if inputs suggest it's unnecessary
        retry_count: Number of retries on failure (default: 0)
    """

    id: PhaseId
    name: str
    description: str
    depends_on: List[PhaseId] = field(default_factory=list)
    timeout_seconds: int = 600
    required_inputs: List[str] = field(default_factory=list)
    required_outputs: List[str] = field(default_factory=list)
    approval_required: bool = False
    can_skip: bool = False
    retry_count: int = 0


# Default phase definitions
# NOTE: The system uses both .md (human-readable) and .json (machine/BAML) files:
# - Scout: outputs scout-report.md + scout_report.json (BAML) - JSON is the contract
# - Architect: reads scout_report.json, outputs architecture.md + architecture.json (BAML)
# - Builder: reads architecture.json (preferred) or architecture.md (fallback)
DEFAULT_PHASES: Dict[PhaseId, PhaseDefinition] = {
    PhaseId.SCOUT: PhaseDefinition(
        id=PhaseId.SCOUT,
        name="Scout",
        description="Research and analyze the task, existing codebase, and requirements",
        depends_on=[],
        timeout_seconds=600,
        required_inputs=[],
        required_outputs=[
            ".context-foundry/scout_report.json"
        ],  # BAML-parsed JSON is the contract
        can_skip=False,
    ),
    PhaseId.ARCHITECT: PhaseDefinition(
        id=PhaseId.ARCHITECT,
        name="Architect",
        description="Design the solution architecture and implementation plan",
        depends_on=[PhaseId.SCOUT],
        timeout_seconds=900,
        required_inputs=[".context-foundry/scout_report.json"],  # BAML JSON contract
        required_outputs=[
            ".context-foundry/architecture.json"
        ],  # BAML-parsed JSON is the contract
        can_skip=False,
    ),
    PhaseId.BUILDER: PhaseDefinition(
        id=PhaseId.BUILDER,
        name="Builder",
        description="Implement the solution based on the architecture",
        depends_on=[PhaseId.ARCHITECT],
        timeout_seconds=1800,
        required_inputs=[
            ".context-foundry/architecture.json"
        ],  # Uses JSON, falls back to .md
        required_outputs=[],  # Source files - validated by presence of any code files
        can_skip=False,
    ),
    PhaseId.TEST: PhaseDefinition(
        id=PhaseId.TEST,
        name="Test",
        description="Run tests and fix any failures (self-healing loop)",
        depends_on=[PhaseId.BUILDER],
        timeout_seconds=1200,
        required_inputs=[],  # Source files must exist
        required_outputs=[".context-foundry/test-report.md"],
        can_skip=True,  # Can skip if no testable code
    ),
    PhaseId.SCREENSHOT: PhaseDefinition(
        id=PhaseId.SCREENSHOT,
        name="Screenshot",
        description="Capture visual documentation of the application",
        depends_on=[PhaseId.TEST],
        timeout_seconds=300,
        required_inputs=[],
        required_outputs=[],  # Screenshots in docs/ or .context-foundry/
        can_skip=True,  # Can skip for non-UI projects
    ),
    PhaseId.DOCUMENTATION: PhaseDefinition(
        id=PhaseId.DOCUMENTATION,
        name="Documentation",
        description="Generate README and documentation",
        depends_on=[PhaseId.SCREENSHOT],
        timeout_seconds=600,
        required_inputs=[],
        required_outputs=["README.md"],
        can_skip=True,
    ),
    PhaseId.DEPLOY: PhaseDefinition(
        id=PhaseId.DEPLOY,
        name="Deploy",
        description="Deploy to GitHub or target environment",
        depends_on=[PhaseId.DOCUMENTATION],
        timeout_seconds=900,
        required_inputs=["README.md"],
        required_outputs=[],  # .git directory or deployment manifest
        approval_required=True,  # Requires human approval by default
        can_skip=True,
    ),
    PhaseId.FEEDBACK: PhaseDefinition(
        id=PhaseId.FEEDBACK,
        name="Feedback",
        description="Capture learnings and update patterns",
        depends_on=[PhaseId.DEPLOY],
        timeout_seconds=300,
        required_inputs=[],
        required_outputs=[],
        can_skip=True,
    ),
}

# Ordered list of phases for sequential execution
PHASE_ORDER: List[PhaseId] = [
    PhaseId.SCOUT,
    PhaseId.ARCHITECT,
    PhaseId.BUILDER,
    PhaseId.TEST,
    PhaseId.SCREENSHOT,
    PhaseId.DOCUMENTATION,
    PhaseId.DEPLOY,
    PhaseId.FEEDBACK,
]


class PhaseRegistry:
    """
    Registry for pipeline phases with dependency resolution.

    Supports:
    - Default phase definitions
    - Custom phase configurations from YAML
    - Dependency graph resolution
    - Phase chain computation
    """

    def __init__(self, phases: Optional[Dict[PhaseId, PhaseDefinition]] = None):
        """
        Initialize registry with phase definitions.

        Args:
            phases: Custom phase definitions (uses DEFAULT_PHASES if None)
        """
        self.phases = phases or DEFAULT_PHASES.copy()

    def get_phase(self, phase_id: PhaseId) -> Optional[PhaseDefinition]:
        """Get phase definition by ID"""
        return self.phases.get(phase_id)

    def get_phase_by_name(self, name: str) -> Optional[PhaseDefinition]:
        """Get phase definition by name (case-insensitive)"""
        name_lower = name.lower()
        for phase_id, phase_def in self.phases.items():
            if (
                phase_def.name.lower() == name_lower
                or phase_id.value.lower() == name_lower
            ):
                return phase_def
        return None

    def get_phase_id_by_name(self, name: str) -> Optional[PhaseId]:
        """Get phase ID by name (case-insensitive)"""
        name_lower = name.lower()
        for phase_id in self.phases.keys():
            if phase_id.value.lower() == name_lower:
                return phase_id
        return None

    def get_dependencies(self, phase_id: PhaseId) -> List[PhaseId]:
        """Get direct dependencies for a phase"""
        phase = self.get_phase(phase_id)
        return phase.depends_on if phase else []

    def get_all_dependencies(self, phase_id: PhaseId) -> List[PhaseId]:
        """
        Get all transitive dependencies for a phase (in execution order).

        Returns phases in the order they should be executed.
        """
        phase = self.get_phase(phase_id)
        if not phase:
            return []

        # Collect all dependencies recursively
        all_deps = set()
        to_process = list(phase.depends_on)

        while to_process:
            dep_id = to_process.pop(0)
            if dep_id not in all_deps:
                all_deps.add(dep_id)
                dep_phase = self.get_phase(dep_id)
                if dep_phase:
                    to_process.extend(dep_phase.depends_on)

        # Return in execution order
        return [p for p in PHASE_ORDER if p in all_deps]

    def get_phase_chain(
        self, start_phase: PhaseId, end_phase: PhaseId
    ) -> List[PhaseId]:
        """
        Get the chain of phases from start to end (inclusive).

        Args:
            start_phase: First phase in the chain
            end_phase: Last phase in the chain

        Returns:
            List of phases in execution order, or empty if invalid range
        """
        try:
            start_idx = PHASE_ORDER.index(start_phase)
            end_idx = PHASE_ORDER.index(end_phase)

            if start_idx > end_idx:
                return []  # Invalid range

            return PHASE_ORDER[start_idx : end_idx + 1]
        except ValueError:
            return []

    def get_phases_from(self, start_phase: PhaseId) -> List[PhaseId]:
        """Get all phases from start_phase to the end"""
        try:
            start_idx = PHASE_ORDER.index(start_phase)
            return PHASE_ORDER[start_idx:]
        except ValueError:
            return []

    def get_phases_until(self, end_phase: PhaseId) -> List[PhaseId]:
        """Get all phases from the beginning until end_phase (inclusive)"""
        try:
            end_idx = PHASE_ORDER.index(end_phase)
            return PHASE_ORDER[: end_idx + 1]
        except ValueError:
            return []

    def validate_phase_sequence(self, phases: List[PhaseId]) -> tuple:
        """
        Validate that a sequence of phases respects dependencies.

        Args:
            phases: List of phases to validate

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        completed = set()

        for phase_id in phases:
            phase = self.get_phase(phase_id)
            if not phase:
                return (False, f"Unknown phase: {phase_id}")

            # Check all dependencies are satisfied
            for dep_id in phase.depends_on:
                if dep_id not in completed and dep_id not in phases:
                    return (
                        False,
                        f"Phase {phase_id.value} requires {dep_id.value} to complete first",
                    )

            completed.add(phase_id)

        return (True, None)

    def resolve_phase_list(self, phase_names: List[str]) -> tuple:
        """
        Resolve a list of phase names to PhaseIds with dependency resolution.

        Args:
            phase_names: List of phase names (case-insensitive)

        Returns:
            Tuple of (phases: List[PhaseId], error: Optional[str])
        """
        phases = []
        for name in phase_names:
            phase_id = self.get_phase_id_by_name(name)
            if not phase_id:
                return ([], f"Unknown phase: {name}")
            phases.append(phase_id)

        # Validate the sequence
        is_valid, error = self.validate_phase_sequence(phases)
        if not is_valid:
            return ([], error)

        return (phases, None)

    def get_required_phases_for(self, target_phases: List[PhaseId]) -> List[PhaseId]:
        """
        Get all phases required to run the target phases (including dependencies).

        Args:
            target_phases: The phases the user wants to run

        Returns:
            Complete list of phases to run in order (dependencies + targets)
        """
        required = set()

        for phase_id in target_phases:
            # Add the phase itself
            required.add(phase_id)
            # Add all its dependencies
            required.update(self.get_all_dependencies(phase_id))

        # Return in execution order
        return [p for p in PHASE_ORDER if p in required]


# Global registry instance
_registry: Optional[PhaseRegistry] = None


def get_registry() -> PhaseRegistry:
    """Get the global phase registry instance"""
    global _registry
    if _registry is None:
        _registry = PhaseRegistry()
    return _registry


def reset_registry():
    """Reset the global registry (mainly for testing)"""
    global _registry
    _registry = None

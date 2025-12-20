"""
Phase Registry for Context Foundry Pipeline

Defines all pipeline phases, their dependencies, and metadata.
Supports loading from YAML configuration for dynamic phase management.

Design Document: docs/design/PHASE_SELECTION_DESIGN.md
GitHub Issue: #191
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PhaseId(str, Enum):
    """
    Canonical phase identifiers.

    BACKWARDS COMPATIBILITY: This enum is preserved for existing code that
    uses PhaseId.SCOUT, etc. New code should use string IDs directly.
    """

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
        id: Unique phase identifier (string, lowercase)
        name: Human-readable name
        description: What this phase does
        depends_on: List of phase IDs that must complete before this one
        timeout_seconds: Maximum execution time (default: 600s = 10min)
        prompt_file: Name of the prompt template file
        inputs: Files/artifacts that must exist before phase starts
        outputs: Files/artifacts that should exist after phase completes
        approval_required: Whether human approval is needed before this phase
        can_skip: Whether this phase can be skipped
        retry_count: Number of retries on failure (default: 0)
    """

    id: str
    name: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    timeout_seconds: int = 600
    prompt_file: str = ""
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    approval_required: bool = False
    can_skip: bool = False
    retry_count: int = 0


@dataclass
class BuildProfile:
    """
    A preset build profile defining which phases to run.

    Attributes:
        name: Profile identifier (e.g., "minimal", "standard", "full")
        description: Human-readable description
        phases: List of phase IDs to run
    """

    name: str
    description: str
    phases: List[str]


@dataclass
class ValidationResult:
    """
    Result of phase selection validation.

    Attributes:
        valid: Whether the selection is valid (no hard errors)
        warnings: List of warning messages (missing dependencies)
        errors: List of error messages (unknown phases, missing inputs)
        resolved_order: Topologically sorted list of phases to execute
    """

    valid: bool
    warnings: List[str]
    errors: List[str]
    resolved_order: List[str]


# =============================================================================
# Default Phase Definitions (for backwards compatibility when YAML not found)
# =============================================================================

DEFAULT_PHASES: Dict[str, PhaseDefinition] = {
    "scout": PhaseDefinition(
        id="scout",
        name="Scout",
        description="Research and analyze the task, existing codebase, and requirements",
        depends_on=[],
        timeout_seconds=600,
        prompt_file="phase_scout.txt",
        inputs=[],
        outputs=[".context-foundry/scout-report.md"],
        can_skip=False,
    ),
    "architect": PhaseDefinition(
        id="architect",
        name="Architect",
        description="Design the solution architecture and implementation plan",
        depends_on=["scout"],
        timeout_seconds=900,
        prompt_file="phase_architect.txt",
        inputs=[".context-foundry/scout-report.md"],
        outputs=[".context-foundry/architecture.md"],
        can_skip=False,
    ),
    "builder": PhaseDefinition(
        id="builder",
        name="Builder",
        description="Implement the solution based on the architecture",
        depends_on=["architect"],
        timeout_seconds=1800,
        prompt_file="phase_builder.txt",
        inputs=[".context-foundry/architecture.md"],
        outputs=[],
        can_skip=False,
    ),
    "test": PhaseDefinition(
        id="test",
        name="Test",
        description="Run tests and fix any failures (self-healing loop)",
        depends_on=["builder"],
        timeout_seconds=1200,
        prompt_file="phase_test.txt",
        inputs=[],
        outputs=[".context-foundry/test-report.md"],
        can_skip=True,
    ),
    "screenshot": PhaseDefinition(
        id="screenshot",
        name="Screenshot",
        description="Capture visual documentation of the application",
        depends_on=["test"],
        timeout_seconds=300,
        prompt_file="phase_screenshot.txt",
        inputs=[],
        outputs=[],
        can_skip=True,
    ),
    "documentation": PhaseDefinition(
        id="documentation",
        name="Documentation",
        description="Generate README and documentation",
        depends_on=["builder"],
        timeout_seconds=600,
        prompt_file="phase_documentation.txt",
        inputs=[],
        outputs=["README.md"],
        can_skip=True,
    ),
    "deploy": PhaseDefinition(
        id="deploy",
        name="Deploy",
        description="Deploy to GitHub or target environment",
        depends_on=["documentation"],
        timeout_seconds=900,
        prompt_file="phase_deploy.txt",
        inputs=["README.md"],
        outputs=[],
        approval_required=True,
        can_skip=True,
    ),
    "feedback": PhaseDefinition(
        id="feedback",
        name="Feedback",
        description="Capture learnings and update patterns",
        depends_on=["deploy"],
        timeout_seconds=300,
        prompt_file="phase_feedback.txt",
        inputs=[],
        outputs=[],
        can_skip=True,
    ),
}

DEFAULT_ORDER: List[str] = [
    "scout",
    "architect",
    "builder",
    "test",
    "screenshot",
    "documentation",
    "deploy",
    "feedback",
]

DEFAULT_PROFILES: Dict[str, BuildProfile] = {
    "minimal": BuildProfile(
        name="minimal",
        description="Fast prototype - just research, design, and build",
        phases=["scout", "architect", "builder"],
    ),
    "standard": BuildProfile(
        name="standard",
        description="Balanced build with tests and documentation",
        phases=["scout", "architect", "builder", "test", "documentation"],
    ),
    "full": BuildProfile(
        name="full",
        description="Complete pipeline - all phases",
        phases=DEFAULT_ORDER.copy(),
    ),
}

# Legacy: Map for backwards compatibility with PhaseId enum
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
    - Loading from YAML configuration
    - Fallback to default definitions
    - Dependency graph resolution via topological sort
    - Build profile management
    - Input file validation
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        phases: Optional[Dict[str, PhaseDefinition]] = None,
    ):
        """
        Initialize registry with phase definitions.

        Args:
            config_path: Path to phases.yaml (auto-detected if None)
            phases: Custom phase definitions (uses YAML or defaults if None)
        """
        self.phases: Dict[str, PhaseDefinition] = {}
        self.profiles: Dict[str, BuildProfile] = {}
        self.default_order: List[str] = []

        if phases:
            # Use provided phases directly
            self.phases = phases
            self.default_order = list(phases.keys())
            self.profiles = DEFAULT_PROFILES.copy()
        else:
            # Try to load from YAML
            if config_path is None:
                config_path = self._find_config_path()

            if config_path and config_path.exists():
                self._load_from_yaml(config_path)
            else:
                # Fallback to defaults
                self.phases = DEFAULT_PHASES.copy()
                self.default_order = DEFAULT_ORDER.copy()
                self.profiles = DEFAULT_PROFILES.copy()

    def _find_config_path(self) -> Optional[Path]:
        """Find the phases.yaml config file."""
        # Try relative to this file
        this_dir = Path(__file__).parent
        candidates = [
            this_dir.parent / "phases" / "phases.yaml",  # tools/phases/phases.yaml
            this_dir / "phases.yaml",  # tools/mcp_utils/phases.yaml
            Path.cwd() / "tools" / "phases" / "phases.yaml",  # From project root
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_from_yaml(self, path: Path) -> None:
        """Load phase definitions from YAML configuration."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not installed, using default phases")
            self.phases = DEFAULT_PHASES.copy()
            self.default_order = DEFAULT_ORDER.copy()
            self.profiles = DEFAULT_PROFILES.copy()
            return

        try:
            with open(path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Load phases
            for phase_id, phase_data in config.get("phases", {}).items():
                phase_id_lower = phase_id.lower()
                self.phases[phase_id_lower] = PhaseDefinition(
                    id=phase_id_lower,
                    name=phase_data.get("name", phase_id.title()),
                    description=phase_data.get("description", ""),
                    depends_on=[d.lower() for d in phase_data.get("depends_on", [])],
                    timeout_seconds=phase_data.get("timeout_seconds", 600),
                    prompt_file=phase_data.get("prompt_file", f"phase_{phase_id}.txt"),
                    inputs=phase_data.get("inputs", []),
                    outputs=phase_data.get("outputs", []),
                    approval_required=phase_data.get("approval_required", False),
                    can_skip=phase_data.get("can_skip", True),
                    retry_count=phase_data.get("retry_count", 0),
                )

            # Load default order
            self.default_order = [
                p.lower() for p in config.get("default_order", list(self.phases.keys()))
            ]

            # Load profiles
            for profile_name, profile_data in config.get("profiles", {}).items():
                self.profiles[profile_name.lower()] = BuildProfile(
                    name=profile_name.lower(),
                    description=profile_data.get("description", ""),
                    phases=[p.lower() for p in profile_data.get("phases", [])],
                )

            logger.info(f"Loaded {len(self.phases)} phases from {path}")

        except Exception as e:
            logger.error(f"Failed to load phases from {path}: {e}")
            # Fallback to defaults
            self.phases = DEFAULT_PHASES.copy()
            self.default_order = DEFAULT_ORDER.copy()
            self.profiles = DEFAULT_PROFILES.copy()

    # =========================================================================
    # Phase Lookup Methods
    # =========================================================================

    def get_phase(self, phase_id: str) -> Optional[PhaseDefinition]:
        """Get phase definition by ID (case-insensitive)."""
        return self.phases.get(phase_id.lower())

    def get_phase_by_enum(self, phase_id: PhaseId) -> Optional[PhaseDefinition]:
        """Get phase definition by PhaseId enum (backwards compatibility)."""
        return self.phases.get(phase_id.value.lower())

    def get_phase_by_name(self, name: str) -> Optional[PhaseDefinition]:
        """Get phase definition by name (case-insensitive)."""
        name_lower = name.lower()
        for phase_def in self.phases.values():
            if phase_def.name.lower() == name_lower or phase_def.id == name_lower:
                return phase_def
        return None

    def list_phases(self) -> List[PhaseDefinition]:
        """List all available phases in default order."""
        return [self.phases[p] for p in self.default_order if p in self.phases]

    # =========================================================================
    # Profile Methods
    # =========================================================================

    def get_profile(self, name: str) -> Optional[BuildProfile]:
        """Get a preset build profile by name."""
        return self.profiles.get(name.lower())

    def list_profiles(self) -> List[BuildProfile]:
        """List all available build profiles."""
        return list(self.profiles.values())

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def validate_phase_selection(
        self,
        selected: List[str],
        working_directory: Optional[Path] = None,
    ) -> ValidationResult:
        """
        Validate phase selection, check inputs exist, and resolve execution order.

        Args:
            selected: List of phase IDs to run
            working_directory: Project directory (for input file validation)

        Returns:
            ValidationResult with valid flag, warnings, errors, and resolved order
        """
        warnings: List[str] = []
        errors: List[str] = []

        # Normalize to lowercase
        selected = [p.lower() for p in selected]
        selected_set = set(selected)

        # Check for unknown phases
        for phase_id in selected:
            if phase_id not in self.phases:
                errors.append(f"Unknown phase: '{phase_id}'")

        if errors:
            return ValidationResult(
                valid=False, warnings=warnings, errors=errors, resolved_order=[]
            )

        # Check for missing dependencies (warn, don't block)
        for phase_id in selected:
            phase = self.phases[phase_id]
            for dep in phase.depends_on:
                if dep not in selected_set:
                    warnings.append(
                        f"Phase '{phase_id}' depends on '{dep}' which is not selected. "
                        f"This may cause issues."
                    )

        # INPUT VALIDATION: Check required input files exist
        if working_directory:
            working_directory = Path(working_directory)
            for phase_id in selected:
                phase = self.phases[phase_id]
                for input_file in phase.inputs:
                    input_path = working_directory / input_file

                    # Check if a selected dependency will create this file
                    deps_will_create = False
                    for dep in phase.depends_on:
                        if dep in selected_set:
                            dep_phase = self.phases.get(dep)
                            if dep_phase and input_file in dep_phase.outputs:
                                deps_will_create = True
                                break

                    if not deps_will_create and not input_path.exists():
                        # Find which phase creates this input
                        creator = None
                        for p in self.phases.values():
                            if input_file in p.outputs:
                                creator = p.id
                                break

                        if creator:
                            errors.append(
                                f"Phase '{phase_id}' requires '{input_file}' which doesn't exist. "
                                f"Did you mean to include the '{creator}' phase?"
                            )
                        else:
                            errors.append(
                                f"Phase '{phase_id}' requires '{input_file}' which doesn't exist."
                            )

        if errors:
            return ValidationResult(
                valid=False, warnings=warnings, errors=errors, resolved_order=[]
            )

        # TOPOLOGICAL SORT: Resolve execution order based on depends_on
        resolved_order = self._topological_sort(selected_set)

        return ValidationResult(
            valid=True,
            warnings=warnings,
            errors=errors,
            resolved_order=resolved_order,
        )

    def _topological_sort(self, selected: Set[str]) -> List[str]:
        """
        Topologically sort selected phases based on depends_on.

        Uses Kahn's algorithm with default_order as tie-breaker for
        phases with no dependency relationship.
        """
        # Build in-degree map (only for selected phases)
        in_degree: Dict[str, int] = {p: 0 for p in selected}
        for phase_id in selected:
            phase = self.phases[phase_id]
            for dep in phase.depends_on:
                if dep in selected:
                    in_degree[phase_id] += 1

        # Sort key: use default_order position as tie-breaker
        def sort_key(p: str) -> int:
            try:
                return self.default_order.index(p)
            except ValueError:
                return len(self.default_order)  # Unknown phases go last

        # Start with phases that have no dependencies (in selected set)
        ready = sorted([p for p, d in in_degree.items() if d == 0], key=sort_key)
        result: List[str] = []

        while ready:
            # Take first ready phase (respects default_order due to sorting)
            current = ready.pop(0)
            result.append(current)

            # Reduce in-degree of dependents
            for phase_id in selected:
                phase = self.phases[phase_id]
                if current in phase.depends_on:
                    in_degree[phase_id] -= 1
                    if in_degree[phase_id] == 0:
                        # Insert maintaining sort order
                        ready.append(phase_id)
                        ready.sort(key=sort_key)

        return result

    # =========================================================================
    # Legacy Methods (Backwards Compatibility)
    # =========================================================================

    def get_phase_id_by_name(self, name: str) -> Optional[PhaseId]:
        """Get PhaseId enum by name (case-insensitive). LEGACY."""
        name_lower = name.lower()
        for phase_id in PhaseId:
            if phase_id.value.lower() == name_lower:
                return phase_id
        return None

    def get_dependencies(self, phase_id: PhaseId) -> List[PhaseId]:
        """Get direct dependencies for a phase. LEGACY."""
        phase = self.get_phase_by_enum(phase_id)
        if not phase:
            return []
        result = []
        for dep_str in phase.depends_on:
            dep_enum = self.get_phase_id_by_name(dep_str)
            if dep_enum:
                result.append(dep_enum)
        return result

    def get_all_dependencies(self, phase_id: PhaseId) -> List[PhaseId]:
        """Get all transitive dependencies for a phase. LEGACY."""
        phase = self.get_phase_by_enum(phase_id)
        if not phase:
            return []

        all_deps: Set[str] = set()
        to_process = list(phase.depends_on)

        while to_process:
            dep_id = to_process.pop(0)
            if dep_id not in all_deps:
                all_deps.add(dep_id)
                dep_phase = self.phases.get(dep_id)
                if dep_phase:
                    to_process.extend(dep_phase.depends_on)

        # Return in execution order as PhaseId enums
        result = []
        for p in self.default_order:
            if p in all_deps:
                phase_enum = self.get_phase_id_by_name(p)
                if phase_enum:
                    result.append(phase_enum)
        return result

    def get_phase_chain(
        self, start_phase: PhaseId, end_phase: PhaseId
    ) -> List[PhaseId]:
        """Get the chain of phases from start to end. LEGACY."""
        try:
            start_idx = PHASE_ORDER.index(start_phase)
            end_idx = PHASE_ORDER.index(end_phase)
            if start_idx > end_idx:
                return []
            return PHASE_ORDER[start_idx : end_idx + 1]
        except ValueError:
            return []

    def get_phases_from(self, start_phase: PhaseId) -> List[PhaseId]:
        """Get all phases from start_phase to the end. LEGACY."""
        try:
            start_idx = PHASE_ORDER.index(start_phase)
            return PHASE_ORDER[start_idx:]
        except ValueError:
            return []

    def get_phases_until(self, end_phase: PhaseId) -> List[PhaseId]:
        """Get all phases from the beginning until end_phase. LEGACY."""
        try:
            end_idx = PHASE_ORDER.index(end_phase)
            return PHASE_ORDER[: end_idx + 1]
        except ValueError:
            return []

    def validate_phase_sequence(self, phases: List[PhaseId]) -> tuple:
        """Validate that a sequence of phases respects dependencies. LEGACY."""
        completed: Set[PhaseId] = set()
        phases_set = set(phases)

        for phase_id in phases:
            phase = self.get_phase_by_enum(phase_id)
            if not phase:
                return (False, f"Unknown phase: {phase_id}")

            for dep_str in phase.depends_on:
                dep_enum = self.get_phase_id_by_name(dep_str)
                if (
                    dep_enum
                    and dep_enum not in completed
                    and dep_enum not in phases_set
                ):
                    return (
                        False,
                        f"Phase {phase_id.value} requires {dep_enum.value} to complete first",
                    )

            completed.add(phase_id)

        return (True, None)

    def resolve_phase_list(self, phase_names: List[str]) -> tuple:
        """Resolve a list of phase names to PhaseIds. LEGACY."""
        phases = []
        for name in phase_names:
            phase_id = self.get_phase_id_by_name(name)
            if not phase_id:
                return ([], f"Unknown phase: {name}")
            phases.append(phase_id)

        is_valid, error = self.validate_phase_sequence(phases)
        if not is_valid:
            return ([], error)

        return (phases, None)

    def get_required_phases_for(self, target_phases: List[PhaseId]) -> List[PhaseId]:
        """Get all phases required to run the targets. LEGACY."""
        required: Set[PhaseId] = set()

        for phase_id in target_phases:
            required.add(phase_id)
            required.update(self.get_all_dependencies(phase_id))

        return [p for p in PHASE_ORDER if p in required]


# =============================================================================
# Global Registry Instance
# =============================================================================

_registry: Optional[PhaseRegistry] = None


def get_registry() -> PhaseRegistry:
    """Get the global phase registry instance."""
    global _registry
    if _registry is None:
        _registry = PhaseRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (mainly for testing)."""
    global _registry
    _registry = None

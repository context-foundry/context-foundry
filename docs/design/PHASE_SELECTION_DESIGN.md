# Phase Selection & Dynamic Pipeline Design

**Status:** Draft
**Issue:** #191
**Author:** Claude + Human
**Date:** 2025-12-20

## Overview

Context Foundry needs a flexible, extensible phase system that:
1. Lets users select which phases to run (any combination)
2. Works identically on macOS, Windows, and Linux
3. Allows adding new phases without modifying core Python code
4. Provides clear warnings when skipping dependencies
5. Reflects dynamic phase selection in the UI

## Design Principles

1. **Configuration over code** - Phase definitions in YAML, not Python enums
2. **Warn, don't block** - Let users make risky choices with clear warnings
3. **Cross-platform first** - No OS-specific assumptions in core logic
4. **Backwards compatible** - Existing builds continue to work
5. **UI reflects reality** - Dashboard shows actual phases, not hardcoded list

---

## Current Architecture

```
tools/mcp_utils/
├── phase_registry.py      # Hardcoded PhaseId enum + DEFAULT_PHASES dict
├── autonomous_build.py    # Orchestration, calls run_phase()
├── phase_execution.py     # run_phase() implementation
└── pipeline_state.py      # State tracking

tools/prompts/phases/
├── phase_scout.txt        # External prompt templates (good!)
├── phase_architect.txt
├── phase_builder.txt
└── ...

context_foundry/daemon/
├── dashboard.py           # Hardcoded phase display in HTML/JS
└── models.py              # Job/Task models
```

### Problems with Current Design

| Component | Problem |
|-----------|---------|
| `PhaseId` enum | Adding phase requires code change |
| `DEFAULT_PHASES` dict | Hardcoded in Python |
| `PHASE_ORDER` list | Hardcoded execution order |
| Dashboard HTML | Phases hardcoded in JavaScript |
| No phase selection | All-or-nothing (except `simple_mode`) |

---

## Proposed Architecture

### 1. Phase Definition Files (YAML)

Move phase definitions to external YAML files:

```
tools/phases/
├── phases.yaml            # Master phase registry
├── scout.yaml             # Individual phase configs (optional)
├── architect.yaml
└── ...
```

**phases.yaml:**
```yaml
version: "1.0"

phases:
  scout:
    name: "Scout"
    description: "Research and analyze the task, existing codebase, and requirements"
    depends_on: []
    timeout_seconds: 600
    prompt_file: "phase_scout.txt"
    outputs:
      - ".context-foundry/scout-report.md"
    can_skip: false

  architect:
    name: "Architect"
    description: "Design the solution architecture and implementation plan"
    depends_on: ["scout"]
    timeout_seconds: 900
    prompt_file: "phase_architect.txt"
    inputs:
      - ".context-foundry/scout-report.md"
    outputs:
      - ".context-foundry/architecture.md"
    can_skip: false

  builder:
    name: "Builder"
    description: "Implement the solution based on the architecture"
    depends_on: ["architect"]
    timeout_seconds: 1800
    prompt_file: "phase_builder.txt"
    inputs:
      - ".context-foundry/architecture.md"
    can_skip: false

  test:
    name: "Test"
    description: "Run tests and fix any failures"
    depends_on: ["builder"]
    timeout_seconds: 1200
    prompt_file: "phase_test.txt"
    can_skip: true

  screenshot:
    name: "Screenshot"
    description: "Capture visual screenshots of the application"
    depends_on: ["test"]
    timeout_seconds: 300
    prompt_file: "phase_screenshot.txt"
    can_skip: true

  documentation:
    name: "Documentation"
    description: "Generate project documentation"
    depends_on: ["screenshot"]
    timeout_seconds: 600
    prompt_file: "phase_documentation.txt"
    can_skip: true

  deploy:
    name: "Deploy"
    description: "Deploy the application"
    depends_on: ["documentation"]
    timeout_seconds: 900
    prompt_file: "phase_deploy.txt"
    can_skip: true
    approval_required: true

  feedback:
    name: "Feedback"
    description: "Collect learnings and update patterns"
    depends_on: ["deploy"]
    timeout_seconds: 300
    prompt_file: "phase_feedback.txt"
    can_skip: true

# Default execution order (when running all phases)
default_order:
  - scout
  - architect
  - builder
  - test
  - screenshot
  - documentation
  - deploy
  - feedback

# Preset profiles
profiles:
  minimal:
    phases: ["scout", "architect", "builder"]
    description: "Fast prototype - no tests, docs, or deployment"

  standard:
    phases: ["scout", "architect", "builder", "test", "documentation"]
    description: "Balanced - includes tests and docs, no deployment"

  full:
    phases: ["scout", "architect", "builder", "test", "screenshot", "documentation", "deploy", "feedback"]
    description: "Complete pipeline - all phases"
```

### 2. Phase Registry Refactor

Replace hardcoded enum with dynamic loader:

```python
# tools/mcp_utils/phase_registry.py

from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml

@dataclass
class PhaseDefinition:
    id: str  # String, not enum
    name: str
    description: str
    depends_on: List[str]
    timeout_seconds: int
    prompt_file: str
    inputs: List[str]
    outputs: List[str]
    can_skip: bool
    approval_required: bool

@dataclass
class BuildProfile:
    name: str
    phases: List[str]
    description: str

class PhaseRegistry:
    """Dynamic phase registry loaded from YAML configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self.phases: Dict[str, PhaseDefinition] = {}
        self.profiles: Dict[str, BuildProfile] = {}
        self.default_order: List[str] = []

        if config_path is None:
            config_path = Path(__file__).parent.parent / "phases" / "phases.yaml"

        self._load_config(config_path)

    def _load_config(self, path: Path) -> None:
        """Load phase definitions from YAML."""
        with open(path) as f:
            config = yaml.safe_load(f)

        for phase_id, phase_data in config.get("phases", {}).items():
            self.phases[phase_id] = PhaseDefinition(
                id=phase_id,
                name=phase_data.get("name", phase_id.title()),
                description=phase_data.get("description", ""),
                depends_on=phase_data.get("depends_on", []),
                timeout_seconds=phase_data.get("timeout_seconds", 600),
                prompt_file=phase_data.get("prompt_file", f"phase_{phase_id}.txt"),
                inputs=phase_data.get("inputs", []),
                outputs=phase_data.get("outputs", []),
                can_skip=phase_data.get("can_skip", True),
                approval_required=phase_data.get("approval_required", False),
            )

        self.default_order = config.get("default_order", list(self.phases.keys()))

        for profile_name, profile_data in config.get("profiles", {}).items():
            self.profiles[profile_name] = BuildProfile(
                name=profile_name,
                phases=profile_data.get("phases", []),
                description=profile_data.get("description", ""),
            )

    def get_phase(self, phase_id: str) -> Optional[PhaseDefinition]:
        """Get phase by ID (case-insensitive)."""
        return self.phases.get(phase_id.lower())

    def validate_phase_selection(
        self,
        selected: List[str],
        working_directory: Optional[Path] = None,
    ) -> Dict[str, any]:
        """
        Validate phase selection, check inputs exist, and resolve execution order.

        Args:
            selected: List of phase IDs to run
            working_directory: Project directory (for input file validation)

        Returns:
            {
                "valid": True/False,
                "warnings": ["Skipping 'architect' may cause..."],
                "errors": ["Unknown phase: 'foo'", "Missing input: architecture.md"],
                "resolved_order": ["scout", "builder"]  # Topologically sorted
            }
        """
        result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "resolved_order": [],
        }

        # Normalize to lowercase
        selected = [p.lower() for p in selected]
        selected_set = set(selected)

        # Check for unknown phases
        for phase_id in selected:
            if phase_id not in self.phases:
                result["errors"].append(f"Unknown phase: '{phase_id}'")
                result["valid"] = False

        if not result["valid"]:
            return result

        # Check for missing dependencies (warn, don't error)
        for phase_id in selected:
            phase = self.phases[phase_id]
            for dep in phase.depends_on:
                if dep not in selected_set:
                    result["warnings"].append(
                        f"Phase '{phase_id}' depends on '{dep}' which is not selected. "
                        f"This may cause issues."
                    )

        # INPUT VALIDATION: Check required input files exist
        # Only validate if working_directory provided and phase deps are skipped
        if working_directory:
            for phase_id in selected:
                phase = self.phases[phase_id]
                for input_file in phase.inputs:
                    input_path = working_directory / input_file
                    # Only error if the dependency phase is NOT in selection
                    # (if dep is selected, it will create the file)
                    deps_will_create = any(
                        input_file in self.phases.get(dep, PhaseDefinition()).outputs
                        for dep in phase.depends_on
                        if dep in selected_set
                    )
                    if not deps_will_create and not input_path.exists():
                        result["errors"].append(
                            f"Phase '{phase_id}' requires '{input_file}' which doesn't exist. "
                            f"Did you mean to include '{phase.depends_on[0]}' phase?"
                        )
                        result["valid"] = False

        # TOPOLOGICAL SORT: Resolve execution order based on depends_on
        # Use Kahn's algorithm with default_order as tie-breaker
        result["resolved_order"] = self._topological_sort(selected_set)

        return result

    def _topological_sort(self, selected: Set[str]) -> List[str]:
        """
        Topologically sort selected phases based on depends_on.

        Uses Kahn's algorithm with default_order as tie-breaker for
        phases with no dependency relationship.
        """
        # Build in-degree map (only for selected phases)
        in_degree = {p: 0 for p in selected}
        for phase_id in selected:
            phase = self.phases[phase_id]
            for dep in phase.depends_on:
                if dep in selected:
                    in_degree[phase_id] += 1

        # Start with phases that have no dependencies (in selected set)
        # Use default_order position as tie-breaker
        def sort_key(p):
            try:
                return self.default_order.index(p)
            except ValueError:
                return len(self.default_order)  # Unknown phases go last

        ready = sorted([p for p, d in in_degree.items() if d == 0], key=sort_key)
        result = []

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
                        # Insert in sorted position (tie-breaker)
                        ready.append(phase_id)
                        ready.sort(key=sort_key)

        return result

    def get_profile(self, name: str) -> Optional[BuildProfile]:
        """Get a preset build profile."""
        return self.profiles.get(name.lower())

    def list_phases(self) -> List[PhaseDefinition]:
        """List all available phases in default order."""
        return [self.phases[p] for p in self.default_order if p in self.phases]

    def list_profiles(self) -> List[BuildProfile]:
        """List all available profiles."""
        return list(self.profiles.values())
```

### 3. Build Parameters Update

Update `autonomous_build_and_deploy` to accept phase selection:

```python
def autonomous_build_and_deploy(
    task: str,
    working_directory: str,
    # NEW: Phase selection (mutually exclusive)
    target_phases: Optional[List[str]] = None,  # ["scout", "builder"]
    build_profile: Optional[str] = None,         # "minimal", "standard", "full"
    # Existing parameters...
    simple_mode: bool = False,  # DEPRECATED, use build_profile="standard"
    # ...
) -> Dict:
    """
    Run autonomous build with optional phase selection.

    Phase Selection Priority:
    1. target_phases - explicit list of phases
    2. build_profile - preset profile name
    3. simple_mode - legacy (maps to "standard")
    4. Default - all phases (build_profile="full")
    """
    registry = PhaseRegistry()
    working_path = Path(working_directory)

    # === EARLY NORMALIZATION ===
    # Convert all selection methods to a single phases list upfront.
    # Rest of the system only deals with List[str] of phase IDs.

    if target_phases:
        # Explicit phase list - use as-is
        phases_to_run = target_phases
    elif build_profile:
        # Preset profile
        profile = registry.get_profile(build_profile)
        if not profile:
            raise ValueError(f"Unknown build profile: {build_profile}")
        phases_to_run = profile.phases
    elif simple_mode:
        # LEGACY: Map simple_mode to "standard" profile
        # Log deprecation warning
        logger.warning(
            "simple_mode is deprecated. Use build_profile='standard' instead."
        )
        profile = registry.get_profile("standard")
        phases_to_run = profile.phases
    else:
        # Default: full pipeline
        phases_to_run = registry.default_order

    # === VALIDATION (with input file checks) ===
    validation = registry.validate_phase_selection(
        phases_to_run,
        working_directory=working_path,
    )

    # Hard errors (unknown phases, missing required inputs)
    if not validation["valid"]:
        error_msg = "\n".join(validation["errors"])
        raise ValueError(f"Invalid phase selection:\n{error_msg}")

    # Soft warnings (missing dependencies) - log and proceed
    for warning in validation["warnings"]:
        logger.warning(f"Phase selection: {warning}")

    # === EXECUTE IN TOPOLOGICALLY SORTED ORDER ===
    for phase_id in validation["resolved_order"]:
        phase = registry.get_phase(phase_id)
        run_phase(phase, working_directory, ...)
```

**Key principle:** Normalize to `List[str]` at the entry point. The rest of the pipeline only sees phase ID strings, never `simple_mode`, `build_profile`, or enums.

### 4. Dashboard UI Updates

Make the dashboard read phases dynamically:

```python
# context_foundry/daemon/dashboard.py

def _get_job_phases(self, job: Job) -> List[Dict]:
    """Get phases for a job from its config, not hardcoded."""

    # Read from job params
    target_phases = job.params.get("target_phases")
    build_profile = job.params.get("build_profile")

    registry = PhaseRegistry()

    if target_phases:
        phase_ids = target_phases
    elif build_profile:
        profile = registry.get_profile(build_profile)
        phase_ids = profile.phases if profile else registry.default_order
    else:
        phase_ids = registry.default_order

    # Return phase info for UI
    return [
        {
            "id": p,
            "name": registry.get_phase(p).name,
            "status": self._get_phase_status(job, p),
        }
        for p in phase_ids
    ]
```

**JavaScript changes:**
```javascript
// Instead of hardcoded:
const PHASES = ['Scout', 'Architect', 'Builder', ...];

// Dynamic from job data:
function renderPhases(job) {
    const phases = job.phases || [];  // From API
    return phases.map(p => `
        <div class="phase ${p.status}">
            ${p.name}
        </div>
    `).join('');
}
```

### 5. API Endpoints

Add endpoints for phase/profile discovery:

```
GET /api/phases
    Returns: List of all available phases with metadata

GET /api/profiles
    Returns: List of preset build profiles

POST /api/jobs
    Body: {
        "task": "Build weather app",
        "working_directory": "/path/to/project",
        "target_phases": ["scout", "architect", "builder"]
        // OR
        "build_profile": "minimal"
    }
```

---

## Migration Plan

### Phase 1: Add YAML Config (Non-Breaking)
1. Create `tools/phases/phases.yaml` with current phase definitions
2. Update `PhaseRegistry` to load from YAML
3. Keep `PhaseId` enum for backwards compatibility
4. Add `target_phases` parameter (optional)
5. All existing code continues to work

### Phase 2: Dashboard Updates
1. Add `/api/phases` and `/api/profiles` endpoints
2. Update dashboard JS to read phases from job data
3. Add phase selection UI for new builds
4. Add profile dropdown (Minimal/Standard/Full/Custom)

### Phase 3: Deprecation
1. Deprecate `PhaseId` enum (keep for 2 versions)
2. Deprecate `simple_mode` parameter
3. Update all internal code to use string phase IDs
4. Remove hardcoded phase lists from dashboard

### Phase 4: Polish
1. Add phase selection to CLI (`cfd build --phases scout,builder`)
2. Add cost/duration estimates per profile
3. Add "Custom" profile builder in UI
4. Add phase dependency visualization

---

## Cross-Platform Considerations

| Concern | Solution |
|---------|----------|
| File paths | Use `pathlib.Path` everywhere |
| YAML loading | `pyyaml` works on all platforms |
| Path separators in YAML | Use forward slashes, normalize at runtime |
| Prompt file loading | Use `Path` for cross-platform paths |

---

## Testing Strategy

1. **Unit tests for PhaseRegistry**
   - Load from YAML
   - Validate phase selection
   - Resolve execution order
   - Handle missing dependencies

2. **Integration tests**
   - Run build with `target_phases=["scout"]`
   - Run build with `build_profile="minimal"`
   - Verify only selected phases execute

3. **UI tests**
   - Dashboard shows correct phases for job
   - Phase selection UI works
   - Profile dropdown works

---

## Design Decisions (Resolved)

1. **Should we allow running phases out of order?**
   - **Decision: No.** Always topologically sort based on `depends_on`.
   - User specifies WHICH phases, system determines ORDER.
   - `default_order` is tie-breaker for independent phases only.

2. **How to handle missing dependencies?**
   - **Decision: Warn, don't block** for missing dependency phases.
   - **Error immediately** if required input FILES don't exist.
   - Example: `--phases builder` without `architecture.md` → error before agent spawns.

3. **Profile inheritance?**
   - **Decision: Defer to v2.** Simple phase lists are sufficient for v1.
   - Future: `standard: { extends: minimal, add: [test, documentation] }`

4. **Legacy `simple_mode` handling?**
   - **Decision: Normalize early.** Map to `build_profile="standard"` at entry point.
   - Log deprecation warning. Rest of system only sees phase lists.

## Open Questions (For Future)

1. **Per-project phase preferences?**
   - Store in `.context-foundry/preferences.yaml`?
   - Remember "last used profile" for project?
   - Out of scope for v1.

2. **Custom phases from plugins?**
   - Allow adding phases via plugin directories?
   - Phases defined in `~/.context-foundry/phases/` merged with built-in?
   - Out of scope for v1.

---

## Appendix: Example Usage

```python
# Just research
autonomous_build_and_deploy(
    task="Analyze this codebase",
    target_phases=["scout"]
)

# Quick prototype
autonomous_build_and_deploy(
    task="Build weather app",
    build_profile="minimal"
)

# Custom selection with warning
autonomous_build_and_deploy(
    task="Build app",
    target_phases=["scout", "builder"]  # Skipping architect - will warn
)

# Test existing code
autonomous_build_and_deploy(
    task="Run tests on my app",
    target_phases=["test"]
)

# Just deploy
autonomous_build_and_deploy(
    task="Deploy to production",
    target_phases=["deploy"]
)
```

```bash
# CLI usage
cfd build "Weather app" --profile minimal
cfd build "Weather app" --phases scout,architect,builder
cfd build "My app" --phases test  # Just run tests
```

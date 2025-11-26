"""
Scope Guard for Context Foundry Pipeline

Restricts agents to write only to permitted directories.
Part of Milestone 3: Safety Mechanisms.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Set


class ScopeViolationType(str, Enum):
    """Types of scope violations"""

    PATH_OUTSIDE_ALLOWED = "path_outside_allowed"
    PATH_IN_DENIED = "path_in_denied"
    SYMLINK_ESCAPE = "symlink_escape"
    PARENT_TRAVERSAL = "parent_traversal"


@dataclass
class ScopeViolation:
    """Details of a scope violation"""

    violation_type: ScopeViolationType
    attempted_path: str
    resolved_path: str
    message: str
    allowed_paths: List[str]


@dataclass
class ScopeConfig:
    """
    Configuration for scope restrictions.

    Attributes:
        working_directory: Primary working directory (always allowed)
        allowed_paths: Additional paths agents can write to
        denied_paths: Paths that are never allowed (takes precedence)
        allow_symlinks: Whether to allow symlinks (default: False for safety)
        allow_parent_traversal: Whether to allow .. in paths (default: False)
    """

    working_directory: Path
    allowed_paths: List[Path] = field(default_factory=list)
    denied_paths: List[Path] = field(default_factory=list)
    allow_symlinks: bool = False
    allow_parent_traversal: bool = False

    def __post_init__(self):
        # Convert to absolute paths
        self.working_directory = Path(self.working_directory).resolve()
        self.allowed_paths = [Path(p).resolve() for p in self.allowed_paths]
        self.denied_paths = [Path(p).resolve() for p in self.denied_paths]

        # Add common denied paths for safety
        self._add_default_denied_paths()

    def _add_default_denied_paths(self):
        """Add commonly sensitive paths to denied list"""
        home = Path.home()
        default_denied = [
            home / ".ssh",
            home / ".gnupg",
            home / ".aws" / "credentials",
            home / ".config" / "gh",
            Path("/etc"),
            Path("/var"),
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
        ]
        for path in default_denied:
            if path.exists() and path not in self.denied_paths:
                self.denied_paths.append(path)


class ScopeGuard:
    """
    Guards against unauthorized file system access.

    Validates paths before allowing write operations.
    """

    def __init__(self, config: ScopeConfig):
        self.config = config
        self._all_allowed: Set[Path] = set()
        self._compute_allowed_paths()

    def _compute_allowed_paths(self):
        """Compute the full set of allowed paths"""
        self._all_allowed.add(self.config.working_directory)
        self._all_allowed.update(self.config.allowed_paths)

        # Add .context-foundry within working directory
        cf_dir = self.config.working_directory / ".context-foundry"
        self._all_allowed.add(cf_dir)

    def _is_path_under(self, path: Path, parent: Path) -> bool:
        """Check if path is under parent directory"""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def _check_symlink_escape(self, path: Path) -> Optional[ScopeViolation]:
        """Check if path involves symlink that escapes allowed directories"""
        if not self.config.allow_symlinks and path.is_symlink():
            resolved = path.resolve()
            if not self._is_within_allowed(resolved):
                return ScopeViolation(
                    violation_type=ScopeViolationType.SYMLINK_ESCAPE,
                    attempted_path=str(path),
                    resolved_path=str(resolved),
                    message=f"Symlink escapes allowed directories: {path} -> {resolved}",
                    allowed_paths=[str(p) for p in self._all_allowed],
                )
        return None

    def _check_parent_traversal(self, path_str: str) -> Optional[ScopeViolation]:
        """Check for parent directory traversal attempts"""
        if not self.config.allow_parent_traversal and ".." in path_str:
            return ScopeViolation(
                violation_type=ScopeViolationType.PARENT_TRAVERSAL,
                attempted_path=path_str,
                resolved_path=str(Path(path_str).resolve()),
                message=f"Parent traversal not allowed: {path_str}",
                allowed_paths=[str(p) for p in self._all_allowed],
            )
        return None

    def _is_within_allowed(self, path: Path) -> bool:
        """Check if resolved path is within any allowed directory"""
        resolved = path.resolve()
        for allowed in self._all_allowed:
            if self._is_path_under(resolved, allowed):
                return True
        return False

    def _is_within_denied(self, path: Path) -> bool:
        """Check if resolved path is within any denied directory"""
        resolved = path.resolve()
        for denied in self.config.denied_paths:
            if self._is_path_under(resolved, denied):
                return True
        return False

    def validate_path(self, path_str: str) -> Optional[ScopeViolation]:
        """
        Validate that a path is within scope.

        Args:
            path_str: Path string to validate

        Returns:
            ScopeViolation if path is out of scope, None if valid
        """
        # Check for parent traversal
        violation = self._check_parent_traversal(path_str)
        if violation:
            return violation

        # Resolve path
        path = Path(path_str)
        if not path.is_absolute():
            path = self.config.working_directory / path
        resolved = path.resolve()

        # Check symlink escape
        if path.exists():
            violation = self._check_symlink_escape(path)
            if violation:
                return violation

        # Check denied paths first (takes precedence)
        if self._is_within_denied(resolved):
            return ScopeViolation(
                violation_type=ScopeViolationType.PATH_IN_DENIED,
                attempted_path=path_str,
                resolved_path=str(resolved),
                message=f"Path is in denied directory: {resolved}",
                allowed_paths=[str(p) for p in self._all_allowed],
            )

        # Check if within allowed paths
        if not self._is_within_allowed(resolved):
            return ScopeViolation(
                violation_type=ScopeViolationType.PATH_OUTSIDE_ALLOWED,
                attempted_path=path_str,
                resolved_path=str(resolved),
                message=f"Path is outside allowed directories: {resolved}",
                allowed_paths=[str(p) for p in self._all_allowed],
            )

        return None

    def is_path_allowed(self, path_str: str) -> bool:
        """Check if a path is allowed (convenience method)"""
        return self.validate_path(path_str) is None

    def get_scope_prompt_addition(self) -> str:
        """
        Generate prompt text to inject into agent prompts for scope enforcement.

        Returns:
            String to add to agent system prompts
        """
        allowed_list = "\n".join(f"  - {p}" for p in self._all_allowed)
        denied_list = "\n".join(f"  - {p}" for p in self.config.denied_paths[:5])

        return f"""
## File System Scope Restrictions

You are restricted to the following directories for all file operations:

**Allowed directories:**
{allowed_list}

**Explicitly denied (never write to these):**
{denied_list}

**Rules:**
1. Only create, modify, or delete files within allowed directories
2. Do not use symlinks to escape scope restrictions
3. Do not use parent traversal (..) to access directories outside scope
4. If you need to access files outside scope, request permission first

Attempting to write outside these boundaries will be blocked and logged.
"""


def create_scope_guard(
    working_directory: Path,
    additional_allowed: Optional[List[Path]] = None,
    additional_denied: Optional[List[Path]] = None,
) -> ScopeGuard:
    """
    Create a ScopeGuard with standard configuration.

    Args:
        working_directory: Project working directory
        additional_allowed: Extra paths to allow
        additional_denied: Extra paths to deny

    Returns:
        Configured ScopeGuard
    """
    config = ScopeConfig(
        working_directory=working_directory,
        allowed_paths=additional_allowed or [],
        denied_paths=additional_denied or [],
    )
    return ScopeGuard(config)


def get_scope_restrictions_for_phase(
    phase_name: str, working_directory: Path
) -> ScopeGuard:
    """
    Get phase-specific scope restrictions.

    Different phases may have different scope requirements.

    Args:
        phase_name: Name of the phase
        working_directory: Project working directory

    Returns:
        ScopeGuard configured for the phase
    """
    # Most phases only need working directory access
    additional_allowed = []

    # Deploy phase needs access to .git
    if phase_name == "Deploy":
        git_dir = working_directory / ".git"
        if git_dir.exists():
            additional_allowed.append(git_dir)

    # Test phase may need access to temp directories
    if phase_name == "Test":
        import tempfile

        additional_allowed.append(Path(tempfile.gettempdir()))

    return create_scope_guard(
        working_directory=working_directory,
        additional_allowed=additional_allowed,
    )

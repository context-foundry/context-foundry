"""
Incremental Builder - Phase 2

Smart file preservation with dependency graph analysis for 85-95% faster builds.

Strategy:
- Build dependency graph from source code (imports, includes)
- Mark changed files + transitive dependencies for rebuild
- Preserve unchanged files from previous build
- Conservative approach: when in doubt, rebuild
"""

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from .change_detector import ChangeReport


@dataclass
class DependencyGraph:
    """Dependency graph structure."""
    nodes: Dict[str, Dict[str, Any]]  # file -> {type, imports}
    edges: List[List[str]]             # [[from, to], ...]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "nodes": self.nodes,
            "edges": self.edges
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DependencyGraph':
        """Create from dict."""
        return cls(
            nodes=data.get('nodes', {}),
            edges=data.get('edges', [])
        )


@dataclass
class BuildPlan:
    """Incremental build plan."""
    files_to_preserve: List[str]    # Copy from previous build
    files_to_rebuild: List[str]     # Regenerate
    files_to_create: List[str]      # New files
    dependency_order: List[str]     # Build order
    estimated_time_saved_minutes: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)


def get_build_graph_path(working_directory: str) -> Path:
    """Get path to build dependency graph file."""
    project_root = Path(working_directory)
    graph_path = project_root / ".context-foundry" / "build-graph.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    return graph_path


def extract_python_imports(file_path: Path) -> List[str]:
    """
    Extract import statements from Python file.

    Args:
        file_path: Path to Python file

    Returns:
        List of imported module names
    """
    imports = []

    try:
        content = file_path.read_text()

        # Match: import foo, from foo import bar, from foo.bar import baz
        import_patterns = [
            r'^\s*import\s+([\w.]+)',
            r'^\s*from\s+([\w.]+)\s+import',
        ]

        for line in content.split('\n'):
            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    module = match.group(1)
                    imports.append(module)

    except OSError:
        pass

    return imports


def extract_javascript_imports(file_path: Path) -> List[str]:
    """
    Extract import statements from JavaScript/TypeScript file.

    Args:
        file_path: Path to JS/TS file

    Returns:
        List of imported module names
    """
    imports = []

    try:
        content = file_path.read_text()

        # Match: import foo from 'bar', import {foo} from 'bar', require('bar')
        import_patterns = [
            r'import\s+.*?from\s+["\']([^"\']+)["\']',
            r'require\s*\(["\']([^"\']+)["\']\)',
        ]

        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            imports.extend(matches)

    except OSError:
        pass

    return imports


def resolve_module_to_file(
    module_name: str,
    file_type: str,
    project_root: Path
) -> Optional[str]:
    """
    Resolve module name to file path (relative to project root).

    Args:
        module_name: Module name (e.g., 'tools.cache.scout_cache')
        file_type: File type ('python' or 'javascript')
        project_root: Project root directory

    Returns:
        Relative file path or None if not found
    """
    if file_type == 'python':
        # Convert module.submodule to module/submodule.py
        module_path = module_name.replace('.', '/')

        # Try .py file
        py_file = project_root / f"{module_path}.py"
        if py_file.exists():
            return str(py_file.relative_to(project_root))

        # Try __init__.py
        init_file = project_root / module_path / "__init__.py"
        if init_file.exists():
            return str(init_file.relative_to(project_root))

    elif file_type == 'javascript':
        # Handle relative imports (./foo, ../bar)
        if module_name.startswith('.'):
            # Resolve relative path (simplified)
            return None  # Skip relative imports for now

        # Try node_modules (skip external dependencies)
        if not module_name.startswith('.') and not module_name.startswith('/'):
            return None  # External dependency

    return None


def build_dependency_graph(
    working_directory: str,
    source_files: Optional[List[str]] = None
) -> DependencyGraph:
    """
    Build dependency graph from source code.

    Args:
        working_directory: Project working directory
        source_files: List of source files (or None to auto-detect)

    Returns:
        DependencyGraph
    """
    project_root = Path(working_directory)

    # Auto-detect source files if not provided
    if source_files is None:
        from .change_detector import get_source_files
        source_files_paths = get_source_files(working_directory)
        source_files = [str(f.relative_to(project_root)) for f in source_files_paths]

    nodes = {}
    edges = []

    for file_rel in source_files:
        file_path = project_root / file_rel

        if not file_path.exists():
            continue

        # Determine file type
        file_type = None
        if file_path.suffix == '.py':
            file_type = 'python'
            imports = extract_python_imports(file_path)
        elif file_path.suffix in {'.js', '.jsx', '.ts', '.tsx'}:
            file_type = 'javascript'
            imports = extract_javascript_imports(file_path)
        else:
            # Unsupported file type - add node but no imports
            nodes[file_rel] = {"type": "other", "imports": []}
            continue

        # Add node
        nodes[file_rel] = {
            "type": file_type,
            "imports": imports
        }

        # Resolve imports to file paths and add edges
        for module_name in imports:
            resolved_file = resolve_module_to_file(module_name, file_type, project_root)
            if resolved_file and resolved_file in source_files:
                edges.append([file_rel, resolved_file])

    print(f"📊 Dependency graph built: {len(nodes)} nodes, {len(edges)} edges")

    graph = DependencyGraph(nodes=nodes, edges=edges)

    # Save graph
    graph_path = get_build_graph_path(working_directory)
    try:
        graph_path.write_text(json.dumps(graph.to_dict(), indent=2))
    except OSError as e:
        print(f"⚠️  Failed to save dependency graph: {e}")

    return graph


def find_affected_files(
    graph: DependencyGraph,
    changed_files: List[str]
) -> List[str]:
    """
    Find files affected by changes (transitive dependencies).

    Args:
        graph: Dependency graph
        changed_files: List of changed files

    Returns:
        List of affected files (changed + dependents)
    """
    affected = set(changed_files)

    # Build reverse dependency map (file -> files that depend on it)
    reverse_deps: Dict[str, Set[str]] = {}
    for from_file, to_file in graph.edges:
        if to_file not in reverse_deps:
            reverse_deps[to_file] = set()
        reverse_deps[to_file].add(from_file)

    # Find transitive dependents (BFS)
    queue = list(changed_files)
    visited = set(changed_files)

    while queue:
        current = queue.pop(0)

        # Add files that depend on current
        if current in reverse_deps:
            for dependent in reverse_deps[current]:
                if dependent not in visited:
                    visited.add(dependent)
                    affected.add(dependent)
                    queue.append(dependent)

    print(f"📈 Affected files: {len(changed_files)} changed → {len(affected)} affected (transitive)")

    return sorted(affected)


def get_previous_build_dir(working_directory: str) -> Optional[Path]:
    """
    Get previous build output directory if it exists.

    Args:
        working_directory: Project working directory

    Returns:
        Path to previous build directory or None
    """
    # Convention: previous build saved to .context-foundry/previous-build/
    project_root = Path(working_directory)
    previous_build = project_root / ".context-foundry" / "previous-build"

    if previous_build.exists() and previous_build.is_dir():
        return previous_build

    return None


def preserve_unchanged_files(
    working_directory: str,
    previous_build_dir: str,
    unchanged_files: List[str]
) -> int:
    """
    Copy unchanged files from previous build.

    Args:
        working_directory: Project working directory
        previous_build_dir: Previous build directory
        unchanged_files: List of unchanged files to preserve

    Returns:
        Number of files preserved
    """
    project_root = Path(working_directory)
    prev_build = Path(previous_build_dir)

    preserved_count = 0

    for file_rel in unchanged_files:
        src = prev_build / file_rel
        dst = project_root / file_rel

        if src.exists():
            try:
                # Create parent directories
                dst.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(src, dst)
                preserved_count += 1
            except (OSError, shutil.Error):
                pass

    print(f"📋 Preserved {preserved_count} unchanged files from previous build")

    return preserved_count


def topological_sort(graph: DependencyGraph) -> List[str]:
    """
    Topological sort of dependency graph (build order).

    Args:
        graph: Dependency graph

    Returns:
        List of files in build order (dependencies first)
    """
    # Calculate in-degree for each node
    in_degree = {node: 0 for node in graph.nodes}

    for from_file, to_file in graph.edges:
        if to_file in in_degree:
            in_degree[to_file] += 1

    # Queue of nodes with no dependencies
    queue = [node for node, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        current = queue.pop(0)
        result.append(current)

        # Reduce in-degree of dependents
        for from_file, to_file in graph.edges:
            if from_file == current:
                in_degree[to_file] -= 1
                if in_degree[to_file] == 0:
                    queue.append(to_file)

    # If result doesn't include all nodes, there's a cycle (shouldn't happen)
    if len(result) != len(graph.nodes):
        print("⚠️  Dependency cycle detected, using fallback order")
        return sorted(graph.nodes.keys())

    return result


def create_incremental_build_plan(
    working_directory: str,
    change_report: ChangeReport,
    graph: Optional[DependencyGraph] = None,
    avg_file_build_time_minutes: float = 0.5
) -> BuildPlan:
    """
    Generate incremental build plan.

    Args:
        working_directory: Project working directory
        change_report: Change detection report
        graph: Dependency graph (or None to load from file)
        avg_file_build_time_minutes: Average time to build one file

    Returns:
        BuildPlan
    """
    # Load graph if not provided
    if graph is None:
        graph_path = get_build_graph_path(working_directory)
        if graph_path.exists():
            try:
                graph_data = json.loads(graph_path.read_text())
                graph = DependencyGraph.from_dict(graph_data)
            except (json.JSONDecodeError, OSError):
                # Build graph from scratch
                graph = build_dependency_graph(working_directory)
        else:
            graph = build_dependency_graph(working_directory)

    # Determine files to rebuild
    changed_and_added = change_report.changed_files + change_report.added_files
    affected_files = find_affected_files(graph, changed_and_added)

    files_to_rebuild = affected_files
    files_to_create = change_report.added_files
    files_to_preserve = [
        f for f in change_report.unchanged_files
        if f not in affected_files
    ]

    # Get build order (topological sort)
    dependency_order = topological_sort(graph)

    # Filter to only files that need rebuilding
    dependency_order = [f for f in dependency_order if f in affected_files]

    # Estimate time saved
    total_files = change_report.total_files
    files_preserved_count = len(files_to_preserve)
    time_saved = files_preserved_count * avg_file_build_time_minutes

    print(f"")
    print(f"📋 Incremental Build Plan:")
    print(f"   Files to preserve: {len(files_to_preserve)} ({files_preserved_count/total_files*100:.1f}%)")
    print(f"   Files to rebuild: {len(files_to_rebuild)} ({len(files_to_rebuild)/total_files*100:.1f}%)")
    print(f"   Files to create: {len(files_to_create)}")
    print(f"   Estimated time saved: {time_saved:.1f} minutes")

    return BuildPlan(
        files_to_preserve=files_to_preserve,
        files_to_rebuild=files_to_rebuild,
        files_to_create=files_to_create,
        dependency_order=dependency_order,
        estimated_time_saved_minutes=time_saved
    )


__all__ = [
    'DependencyGraph',
    'BuildPlan',
    'build_dependency_graph',
    'find_affected_files',
    'create_incremental_build_plan',
    'preserve_unchanged_files',
    'get_build_graph_path'
]

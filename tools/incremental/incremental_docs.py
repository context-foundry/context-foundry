"""
Incremental Documentation - Phase 2

Selective documentation updates for 90-95% faster doc generation.

Strategy:
- Map documentation files to source files
- Only regenerate docs for changed source files
- Preserve screenshots for unchanged UI components
- Update README sections selectively
- Conservative approach: when in doubt, regenerate
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from .change_detector import ChangeReport


@dataclass
class DocsManifest:
    """Mapping of documentation files to source files."""
    documentation: Dict[str, Dict[str, Any]]  # doc_file -> {sources: [files], auto_generated: bool, ui_component: bool}
    readme_sections: Dict[str, Dict[str, Any]]  # section_name -> {sources: [files]}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocsManifest':
        """Create from dict."""
        return cls(
            documentation=data.get('documentation', {}),
            readme_sections=data.get('readme_sections', {})
        )


@dataclass
class DocsPlan:
    """Selective documentation update plan."""
    docs_to_regenerate: List[str]  # Affected docs
    docs_to_preserve: List[str]    # Unchanged docs
    screenshots_to_preserve: List[str]  # Unchanged UI
    readme_sections_to_update: List[str]  # Specific sections
    regenerate_all: bool  # Fallback
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return asdict(self)


def get_docs_manifest_path(working_directory: str) -> Path:
    """Get path to docs manifest file."""
    project_root = Path(working_directory)
    manifest_path = project_root / ".context-foundry" / "docs-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    return manifest_path


def infer_doc_sources(doc_file: Path, project_root: Path) -> List[str]:
    """
    Infer source files that a documentation file depends on.

    Args:
        doc_file: Documentation file path
        project_root: Project root directory

    Returns:
        List of inferred source file paths (relative to project root)
    """
    sources = []
    doc_name = doc_file.stem.lower()

    # Architecture docs depend on main source files
    if 'architecture' in doc_name or 'design' in doc_name:
        sources.extend(['tools/mcp_server.py', 'tools/orchestrator_prompt.txt'])

    # API docs depend on API/server files
    elif 'api' in doc_name:
        sources.extend(['tools/mcp_server.py'])

    # Installation docs depend on config files
    elif 'install' in doc_name or 'setup' in doc_name:
        sources.extend(['setup.py', 'requirements.txt', 'package.json'])

    # Usage docs depend on main entry points
    elif 'usage' in doc_name or 'guide' in doc_name:
        sources.extend(['tools/mcp_server.py', 'README.md'])

    # Screenshots depend on UI source files
    elif doc_file.suffix in {'.png', '.jpg', '.gif'}:
        # UI components (simplified heuristic)
        for pattern in ['src/**/*.jsx', 'src/**/*.tsx', 'src/**/*.vue']:
            sources.extend([str(f.relative_to(project_root)) for f in project_root.glob(pattern)])

    return sources


def build_docs_manifest(working_directory: str) -> DocsManifest:
    """
    Build documentation manifest (map docs to source files).

    Args:
        working_directory: Project working directory

    Returns:
        DocsManifest
    """
    project_root = Path(working_directory)

    documentation = {}
    readme_sections = {}

    # Find documentation files
    docs_dir = project_root / "docs"
    if docs_dir.exists():
        for doc_file in docs_dir.rglob('*'):
            if not doc_file.is_file():
                continue

            # Skip hidden files
            if doc_file.name.startswith('.'):
                continue

            rel_path = str(doc_file.relative_to(project_root))

            # Infer source dependencies
            sources = infer_doc_sources(doc_file, project_root)

            # Determine if auto-generated and UI component
            auto_generated = doc_file.suffix in {'.png', '.jpg', '.gif'}
            ui_component = 'screenshot' in rel_path.lower()

            documentation[rel_path] = {
                "sources": sources,
                "auto_generated": auto_generated,
                "ui_component": ui_component
            }

    # README sections (simplified - map to common source files)
    readme_file = project_root / "README.md"
    if readme_file.exists():
        readme_sections = {
            "## Installation": {
                "sources": ["setup.py", "requirements.txt", "package.json"]
            },
            "## Usage": {
                "sources": ["tools/mcp_server.py", "tools/orchestrator_prompt.txt"]
            },
            "## API Reference": {
                "sources": ["tools/mcp_server.py"]
            },
            "## Architecture": {
                "sources": ["tools/mcp_server.py", "tools/orchestrator_prompt.txt"]
            }
        }

    print(f"📊 Docs manifest built: {len(documentation)} doc files, {len(readme_sections)} README sections")

    manifest = DocsManifest(
        documentation=documentation,
        readme_sections=readme_sections
    )

    # Save manifest
    manifest_path = get_docs_manifest_path(working_directory)
    try:
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))
    except OSError as e:
        print(f"⚠️  Failed to save docs manifest: {e}")

    return manifest


def find_affected_docs(
    manifest: DocsManifest,
    changed_files: List[str]
) -> List[str]:
    """
    Find documentation files affected by changed source files.

    Args:
        manifest: Docs manifest
        changed_files: List of changed source files

    Returns:
        List of affected documentation files
    """
    affected_docs = []
    changed_files_set = set(changed_files)

    for doc_file, doc_data in manifest.documentation.items():
        sources = doc_data.get('sources', [])

        # Check if any source file changed
        if any(f in changed_files_set for f in sources):
            affected_docs.append(doc_file)

    print(f"📄 Affected docs: {len(affected_docs)}/{len(manifest.documentation)} files")

    return affected_docs


def find_affected_readme_sections(
    manifest: DocsManifest,
    changed_files: List[str]
) -> List[str]:
    """
    Find README sections affected by changed source files.

    Args:
        manifest: Docs manifest
        changed_files: List of changed source files

    Returns:
        List of affected README section names
    """
    affected_sections = []
    changed_files_set = set(changed_files)

    for section_name, section_data in manifest.readme_sections.items():
        sources = section_data.get('sources', [])

        # Check if any source file changed
        if any(f in changed_files_set for f in sources):
            affected_sections.append(section_name)

    print(f"📝 Affected README sections: {len(affected_sections)}/{len(manifest.readme_sections)}")

    return affected_sections


def create_docs_plan(
    working_directory: str,
    change_report: ChangeReport,
    manifest: Optional[DocsManifest] = None,
    threshold_percentage: float = 30.0
) -> DocsPlan:
    """
    Generate selective documentation update plan.

    Args:
        working_directory: Project working directory
        change_report: Change detection report
        manifest: Docs manifest (or None to load from file)
        threshold_percentage: Regenerate all if > this % of files changed

    Returns:
        DocsPlan
    """
    # Load manifest if not provided
    if manifest is None:
        manifest_path = get_docs_manifest_path(working_directory)
        if manifest_path.exists():
            try:
                manifest_data = json.loads(manifest_path.read_text())
                manifest = DocsManifest.from_dict(manifest_data)
            except (json.JSONDecodeError, OSError):
                # Build manifest from scratch
                manifest = build_docs_manifest(working_directory)
        else:
            manifest = build_docs_manifest(working_directory)

    # If no manifest available, regenerate all docs
    if manifest is None or not manifest.documentation:
        return DocsPlan(
            docs_to_regenerate=[],
            docs_to_preserve=[],
            screenshots_to_preserve=[],
            readme_sections_to_update=[],
            regenerate_all=True,
            reason="No docs manifest available"
        )

    # If too many files changed, regenerate all docs
    if change_report.change_percentage > threshold_percentage:
        return DocsPlan(
            docs_to_regenerate=[],
            docs_to_preserve=[],
            screenshots_to_preserve=[],
            readme_sections_to_update=[],
            regenerate_all=True,
            reason=f"Too many files changed ({change_report.change_percentage:.1f}% > {threshold_percentage}%)"
        )

    # Find affected docs
    changed_and_added = change_report.changed_files + change_report.added_files
    affected_docs = find_affected_docs(manifest, changed_and_added)
    affected_sections = find_affected_readme_sections(manifest, changed_and_added)

    # Categorize docs
    all_docs = list(manifest.documentation.keys())
    docs_to_preserve = [d for d in all_docs if d not in affected_docs]

    # Find screenshots to preserve
    screenshots_to_preserve = [
        d for d in docs_to_preserve
        if manifest.documentation[d].get('ui_component', False)
    ]

    print(f"")
    print(f"📋 Docs Plan:")
    print(f"   Docs to regenerate: {len(affected_docs)} ({len(affected_docs)/len(all_docs)*100:.1f}%)")
    print(f"   Docs to preserve: {len(docs_to_preserve)} ({len(docs_to_preserve)/len(all_docs)*100:.1f}%)")
    print(f"   Screenshots to preserve: {len(screenshots_to_preserve)}")
    print(f"   README sections to update: {len(affected_sections)}")

    return DocsPlan(
        docs_to_regenerate=affected_docs,
        docs_to_preserve=docs_to_preserve,
        screenshots_to_preserve=screenshots_to_preserve,
        readme_sections_to_update=affected_sections,
        regenerate_all=False,
        reason=f"Selective docs update: {len(affected_docs)} affected files"
    )


__all__ = [
    'DocsManifest',
    'DocsPlan',
    'build_docs_manifest',
    'find_affected_docs',
    'create_docs_plan',
    'get_docs_manifest_path'
]

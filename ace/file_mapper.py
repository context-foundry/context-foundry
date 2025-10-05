#!/usr/bin/env python3
"""
File Structure Mapper

Utility to map project structure and identify entry points,
preventing duplicate file creation and respecting existing architecture.
"""

from pathlib import Path
from typing import Dict, List, Set
import re


class FileMapper:
    """Maps project file structure and identifies dependencies."""

    def __init__(self, project_dir: Path):
        """Initialize file mapper.

        Args:
            project_dir: Path to project directory
        """
        self.project_dir = Path(project_dir)
        self.files: List[Path] = []
        self.entry_points: List[Path] = []

    def scan_project(self, exclude_patterns: List[str] = None) -> List[Path]:
        """Scan project directory for all files.

        Args:
            exclude_patterns: Patterns to exclude (e.g., node_modules, .git)

        Returns:
            List of file paths relative to project directory
        """
        if exclude_patterns is None:
            exclude_patterns = [
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                ".pytest_cache", ".DS_Store", "*.pyc", "dist", "build"
            ]

        all_files = []

        for file_path in self.project_dir.rglob("*"):
            if file_path.is_file():
                # Check if file matches exclusion patterns
                relative_path = file_path.relative_to(self.project_dir)
                if not any(pattern in str(relative_path) for pattern in exclude_patterns):
                    all_files.append(relative_path)

        self.files = sorted(all_files)
        return self.files

    def identify_entry_points(self) -> List[Path]:
        """Identify project entry points.

        Returns:
            List of entry point file paths
        """
        entry_point_patterns = {
            # Web projects
            "index.html": 100,
            "index.htm": 90,
            "main.html": 80,

            # Python projects
            "main.py": 100,
            "__main__.py": 100,
            "app.py": 90,
            "server.py": 80,

            # JavaScript/Node projects
            "index.js": 100,
            "main.js": 100,
            "app.js": 90,
            "server.js": 80,
            "package.json": 70,

            # Other
            "Cargo.toml": 100,  # Rust
            "go.mod": 100,      # Go
            "pom.xml": 100,     # Java Maven
        }

        candidates = []

        for file_path in self.files:
            file_name = file_path.name.lower()
            if file_name in entry_point_patterns:
                priority = entry_point_patterns[file_name]
                # Prefer root-level entry points
                depth = len(file_path.parts)
                score = priority - (depth * 5)
                candidates.append((score, file_path))

        # Sort by score (highest first)
        candidates.sort(reverse=True, key=lambda x: x[0])
        self.entry_points = [path for score, path in candidates[:3]]

        return self.entry_points

    def find_dependencies(self, entry_point: Path) -> Dict[str, List[str]]:
        """Find dependencies from an entry point file.

        Args:
            entry_point: Entry point file path

        Returns:
            Dictionary mapping dependency types to file paths
        """
        full_path = self.project_dir / entry_point
        if not full_path.exists():
            return {}

        content = full_path.read_text(errors='ignore')
        dependencies = {
            'scripts': [],
            'stylesheets': [],
            'imports': [],
            'requires': []
        }

        # HTML script tags
        script_pattern = r'<script[^>]+src=["\'](.*?)["\']'
        for match in re.finditer(script_pattern, content):
            dependencies['scripts'].append(match.group(1))

        # HTML link/stylesheet tags
        link_pattern = r'<link[^>]+href=["\'](.*?\.css)["\']'
        for match in re.finditer(link_pattern, content):
            dependencies['stylesheets'].append(match.group(1))

        # Python imports
        import_pattern = r'(?:from|import)\s+([\w.]+)'
        for match in re.finditer(import_pattern, content):
            dependencies['imports'].append(match.group(1))

        # JavaScript require/import
        require_pattern = r'require\(["\'](.+?)["\']\)'
        for match in re.finditer(require_pattern, content):
            dependencies['requires'].append(match.group(1))

        import_es6_pattern = r'import.*from\s+["\'](.+?)["\']'
        for match in re.finditer(import_es6_pattern, content):
            dependencies['requires'].append(match.group(1))

        return dependencies

    def find_similar_files(self, filename: str, max_distance: int = 2) -> List[Path]:
        """Find files with similar names.

        Args:
            filename: Base filename to search for
            max_distance: Maximum Levenshtein distance for similarity

        Returns:
            List of similar file paths
        """
        similar = []
        base_name = Path(filename).stem.lower()

        for file_path in self.files:
            file_stem = file_path.stem.lower()

            # Exact match (different extension or location)
            if file_stem == base_name:
                similar.append(file_path)
                continue

            # Similar name (basic string similarity)
            if base_name in file_stem or file_stem in base_name:
                similar.append(file_path)

        return similar

    def suggest_file_location(self, filename: str, file_type: str = None) -> Path:
        """Suggest appropriate location for a new file based on project structure.

        Args:
            filename: Name of file to create
            file_type: Type of file (js, css, py, test, etc.)

        Returns:
            Suggested file path relative to project directory
        """
        # Detect file type from extension if not provided
        if file_type is None:
            ext = Path(filename).suffix.lower()
            type_map = {
                '.js': 'js',
                '.css': 'css',
                '.py': 'py',
                '.html': 'html',
                '.test.js': 'test',
                '.spec.js': 'test',
                '_test.py': 'test',
            }
            file_type = type_map.get(ext, 'other')

        # Find common directories for this file type
        type_dirs = {
            'js': ['js', 'src', 'lib', 'scripts'],
            'css': ['css', 'styles', 'stylesheets', 'assets'],
            'py': ['src', 'lib', ''],
            'test': ['tests', 'test', '__tests__', 'spec'],
            'html': ['', 'public', 'templates'],
        }

        candidate_dirs = type_dirs.get(file_type, [''])

        # Check which directories exist in project
        existing_dirs = []
        for dir_name in candidate_dirs:
            if dir_name == '':
                existing_dirs.append(Path('.'))
            else:
                dir_path = self.project_dir / dir_name
                if dir_path.exists() and dir_path.is_dir():
                    existing_dirs.append(Path(dir_name))

        # Use first existing directory, or root if none exist
        if existing_dirs:
            return existing_dirs[0] / filename
        else:
            return Path(filename)

    def generate_structure_report(self) -> str:
        """Generate a text report of project structure.

        Returns:
            Formatted text report
        """
        if not self.files:
            self.scan_project()

        if not self.entry_points:
            self.identify_entry_points()

        report = f"""# Project Structure: {self.project_dir.name}

## File Count
Total files: {len(self.files)}

## Entry Points
"""
        if self.entry_points:
            for ep in self.entry_points:
                report += f"- {ep}\n"

                # Show dependencies
                deps = self.find_dependencies(ep)
                if any(deps.values()):
                    report += f"  Dependencies:\n"
                    for dep_type, dep_list in deps.items():
                        if dep_list:
                            report += f"    {dep_type}: {', '.join(dep_list[:5])}\n"
        else:
            report += "No entry points detected\n"

        report += f"""
## Directory Structure
"""
        # Group files by directory
        dirs: Dict[str, List[str]] = {}
        for file_path in self.files:
            parent = str(file_path.parent) if file_path.parent != Path('.') else "root"
            if parent not in dirs:
                dirs[parent] = []
            dirs[parent].append(file_path.name)

        for dir_name, file_list in sorted(dirs.items()):
            report += f"\n{dir_name}/\n"
            for fname in sorted(file_list)[:10]:  # Limit to 10 files per dir
                report += f"  - {fname}\n"
            if len(file_list) > 10:
                report += f"  ... and {len(file_list) - 10} more files\n"

        return report


def main():
    """CLI for file mapping."""
    import argparse

    parser = argparse.ArgumentParser(description="Map project file structure")
    parser.add_argument("project_dir", help="Project directory to scan")
    parser.add_argument("--find-similar", help="Find files similar to given name")
    parser.add_argument("--suggest-location", help="Suggest location for new file")
    parser.add_argument("--file-type", help="Type of file (js, css, py, test)")

    args = parser.parse_args()

    mapper = FileMapper(Path(args.project_dir))
    mapper.scan_project()
    mapper.identify_entry_points()

    if args.find_similar:
        similar = mapper.find_similar_files(args.find_similar)
        print(f"Files similar to '{args.find_similar}':")
        for file in similar:
            print(f"  - {file}")

    elif args.suggest_location:
        location = mapper.suggest_file_location(args.suggest_location, args.file_type)
        print(f"Suggested location: {location}")

    else:
        print(mapper.generate_structure_report())


if __name__ == "__main__":
    main()

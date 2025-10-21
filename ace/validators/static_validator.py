#!/usr/bin/env python3
"""
Static Validator
Validates file references and project structure.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List


class StaticValidator:
    """Validates file references and project structure without executing code."""

    def __init__(self, project_dir: Path):
        """Initialize validator with project directory.

        Args:
            project_dir: Path to the project root directory
        """
        self.project_dir = Path(project_dir)

    def validate_build_files(self, all_files: List[str]) -> Dict[str, List[str]]:
        """Validate that all file references in the code actually exist.

        Returns:
            dict with 'issues' list and 'warnings' list
        """
        import re

        issues = []
        warnings = []

        # Get all created files as Path objects
        created_files = {Path(f) for f in all_files}
        created_filenames = {p.name for p in created_files}
        created_paths_str = {str(p) for p in created_files}

        # Check HTML files for broken links
        html_files = [f for f in all_files if f.endswith('.html')]
        for html_file in html_files:
            html_path = self.project_dir / html_file
            if not html_path.exists():
                continue

            try:
                content = html_path.read_text()

                # Check CSS links: <link rel="stylesheet" href="...">
                css_links = re.findall(r'<link[^>]*href=["\']([^"\']+\.css)["\']', content)
                for css_link in css_links:
                    # Resolve relative path
                    if not css_link.startswith(('http://', 'https://', '//')):
                        expected_path = (html_path.parent / css_link).resolve()
                        relative_to_project = expected_path.relative_to(self.project_dir)
                        if str(relative_to_project) not in created_paths_str:
                            issues.append(f"{html_file} links to '{css_link}' but file not found at {relative_to_project}")

                # Check JS scripts: <script src="...">
                js_links = re.findall(r'<script[^>]*src=["\']([^"\']+\.js)["\']', content)
                for js_link in js_links:
                    if not js_link.startswith(('http://', 'https://', '//')):
                        expected_path = (html_path.parent / js_link).resolve()
                        relative_to_project = expected_path.relative_to(self.project_dir)
                        if str(relative_to_project) not in created_paths_str:
                            issues.append(f"{html_file} links to '{js_link}' but file not found at {relative_to_project}")

            except Exception as e:
                warnings.append(f"Could not validate {html_file}: {e}")

        # Check JS files for imports
        js_files = [f for f in all_files if f.endswith('.js') and not f.endswith('.test.js')]
        for js_file in js_files:
            js_path = self.project_dir / js_file
            if not js_path.exists():
                continue

            try:
                content = js_path.read_text()

                # Check ES6 imports: import ... from '...'
                imports = re.findall(r'import\s+.*?from\s+["\']([^"\']+)["\']', content)
                for import_path in imports:
                    # Skip node_modules and external packages
                    if not import_path.startswith('.'):
                        continue

                    # Resolve relative import
                    # Only add .js extension if no extension is present
                    _, ext = os.path.splitext(import_path)
                    if not ext:  # No extension, assume .js
                        import_path += '.js'

                    expected_path = (js_path.parent / import_path).resolve()
                    try:
                        relative_to_project = expected_path.relative_to(self.project_dir)
                        if str(relative_to_project) not in created_paths_str:
                            issues.append(f"{js_file} imports '{import_path}' but file not found at {relative_to_project}")
                    except ValueError:
                        # Path is outside project directory, skip
                        pass

                # Check CSS imports: import './styles.css'
                css_imports = re.findall(r'import\s+["\']([^"\']+\.css)["\']', content)
                for css_import in css_imports:
                    # Only check relative imports
                    if css_import.startswith('.'):
                        expected_path = (js_path.parent / css_import).resolve()
                        try:
                            relative_to_project = expected_path.relative_to(self.project_dir)
                            if str(relative_to_project) not in created_paths_str:
                                issues.append(f"{js_file} imports '{css_import}' but file not found at {relative_to_project}")
                        except ValueError:
                            # Path is outside project directory, skip
                            pass

            except Exception as e:
                warnings.append(f"Could not validate {js_file}: {e}")

        return {"issues": issues, "warnings": warnings}

    def validate_project_structure(self) -> Dict[str, List[str]]:
        """Validate project structure matches detected type (CRA, Vite, etc.).

        Returns:
            dict with 'issues' list and 'warnings' list
        """
        issues = []
        warnings = []

        package_json_path = self.project_dir / "package.json"

        if not package_json_path.exists():
            return {"issues": issues, "warnings": warnings}

        try:
            package_data = json.loads(package_json_path.read_text())
            dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}

            # Check for Create React App
            if 'react-scripts' in dependencies:
                # CRA requires specific structure
                public_index = self.project_dir / "public" / "index.html"
                src_index_js = self.project_dir / "src" / "index.js"
                src_index_html = self.project_dir / "src" / "index.html"

                if not public_index.exists():
                    issues.append("Create React App detected but public/index.html is missing (required by react-scripts)")

                if src_index_html.exists():
                    issues.append("Found src/index.html but CRA requires public/index.html - move it to public/ directory")

                if not src_index_js.exists():
                    warnings.append("Create React App detected but src/index.js entry point not found")

            # Check for Vite
            elif 'vite' in dependencies:
                # Vite typically uses index.html in root
                root_index = self.project_dir / "index.html"
                if not root_index.exists():
                    warnings.append("Vite detected but index.html not found in project root")

            # Check for TailwindCSS without config
            if 'tailwindcss' in dependencies:
                tailwind_config = self.project_dir / "tailwind.config.js"
                postcss_config = self.project_dir / "postcss.config.js"

                if not tailwind_config.exists():
                    warnings.append("TailwindCSS installed but tailwind.config.js not found")
                if not postcss_config.exists():
                    warnings.append("TailwindCSS installed but postcss.config.js not found")

        except Exception as e:
            warnings.append(f"Could not validate project structure: {e}")

        return {"issues": issues, "warnings": warnings}

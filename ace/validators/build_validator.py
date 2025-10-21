#!/usr/bin/env python3
"""
Build Validator
Validates that npm install + npm build work correctly.
"""

import json
import subprocess
import re
from pathlib import Path
from typing import Tuple, Dict, Any


class BuildValidator:
    """
    Validates that the project builds successfully.

    Checks:
    - package.json exists
    - npm install succeeds
    - npm build succeeds (if build script exists)
    """

    def __init__(self, project_dir: Path):
        """Initialize build validator.

        Args:
            project_dir: Path to project directory
        """
        self.project_dir = Path(project_dir)

    def validate(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate that npm install + npm build work.

        Returns:
            (success: bool, error_details: dict)
        """
        package_json_path = self.project_dir / "package.json"

        if not package_json_path.exists():
            return (True, {})  # No package.json, skip

        try:
            package_data = json.loads(package_json_path.read_text())
            scripts = package_data.get('scripts', {})
            deps = package_data.get('dependencies', {})

            # Detect React app
            is_react_app = 'react-scripts' in deps

            # Step 1: npm install
            print(f"      Installing dependencies...")
            install_result = subprocess.run(
                ['npm', 'install'],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout for install
            )

            if install_result.returncode != 0:
                return (False, {
                    'message': 'Dependency installation failed',
                    'stderr': install_result.stderr,
                    'stdout': install_result.stdout,
                    'command': 'npm install',
                    'exit_code': install_result.returncode
                })

            print(f"      ✅ Dependencies installed")

            # Step 2: npm build (if build script exists)
            if 'build' not in scripts:
                return (True, {})  # No build script, that's okay

            print(f"      Running build: npm run build...")

            build_result = subprocess.run(
                ['npm', 'run', 'build'],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout for build
            )

            if build_result.returncode == 0:
                print(f"      ✅ Build succeeded")
                return (True, {})
            else:
                # Parse common errors
                stderr = build_result.stderr
                errors = []

                if "Module not found" in stderr:
                    module_errors = re.findall(r"Module not found: Error: Can't resolve '([^']+)'", stderr)
                    errors.extend([f"Missing module: {m}" for m in module_errors])

                if "Cannot find module" in stderr:
                    module_errors = re.findall(r"Cannot find module '([^']+)'", stderr)
                    errors.extend([f"Cannot find module: {m}" for m in module_errors])

                if "SyntaxError" in stderr:
                    errors.append("Syntax error in code - check stderr for details")

                error_message = '; '.join(errors) if errors else 'Build failed - see stderr'

                return (False, {
                    'message': error_message,
                    'stderr': stderr,
                    'stdout': build_result.stdout,
                    'command': 'npm run build',
                    'exit_code': build_result.returncode
                })

        except subprocess.TimeoutExpired as e:
            return (False, {
                'message': 'Build timeout (exceeded 3 minutes)',
                'stderr': str(e),
                'command': e.cmd
            })
        except FileNotFoundError:
            return (False, {
                'message': 'npm not found - ensure Node.js is installed',
                'command': 'npm'
            })
        except Exception as e:
            return (False, {
                'message': f'Build validation exception: {str(e)}',
                'stack_trace': str(e)
            })

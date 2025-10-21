#!/usr/bin/env python3
"""
Code Extractor - Extract and save code blocks from LLM responses.

Extracted from autonomous_orchestrator.py to provide reusable code extraction
functionality across different workflows.
"""

import os
import re
from pathlib import Path
from typing import Dict, List


class CodeExtractor:
    """Extract code blocks from LLM responses and save to files."""

    def __init__(self, project_dir: Path, project_name: str = None):
        """
        Initialize CodeExtractor.

        Args:
            project_dir: Root directory of the project
            project_name: Optional project name for path cleanup
        """
        self.project_dir = Path(project_dir)
        self.project_name = project_name or self.project_dir.name

    def parse_architect_response(self, response: str) -> Dict[str, str]:
        """Parse architect response to extract SPEC, PLAN, TASKS.

        Args:
            response: The architect's response text

        Returns:
            Dictionary with 'spec', 'plan', and 'tasks' keys
        """
        files = {}

        # Simple parsing - look for markdown code blocks or headers
        # This is a simplified version - production would be more robust
        if "# Specification:" in response:
            spec_start = response.find("# Specification:")
            spec_end = response.find("# Implementation Plan:", spec_start)
            if spec_end > spec_start:
                files["spec"] = response[spec_start:spec_end].strip()

        if "# Implementation Plan:" in response:
            plan_start = response.find("# Implementation Plan:")
            plan_end = response.find("# Task Breakdown:", plan_start)
            if plan_end > plan_start:
                files["plan"] = response[plan_start:plan_end].strip()

        if "# Task Breakdown:" in response:
            tasks_start = response.find("# Task Breakdown:")
            files["tasks"] = response[tasks_start:].strip()

        # Fallback: if parsing failed, use whole response
        if not files:
            files = {"spec": response, "plan": response, "tasks": response}

        return files

    def parse_tasks(self, tasks_content: str) -> List[Dict]:
        """Parse TASKS.md to extract individual tasks.

        Args:
            tasks_content: The tasks content to parse

        Returns:
            List of task dictionaries with 'name', 'description', and 'files' keys
        """
        tasks = []

        # Simple parsing: look for ### Task headers
        lines = tasks_content.split("\n")
        current_task = None

        for line in lines:
            if line.startswith("### Task"):
                if current_task:
                    tasks.append(current_task)

                # Extract task name
                task_name = line.replace("### Task", "").strip()
                current_task = {"name": task_name, "description": "", "files": []}

            elif current_task and line.startswith("- **Files**:"):
                # Extract files
                files_str = line.replace("- **Files**:", "").strip()
                current_task["files"] = [f.strip() for f in files_str.split(",")]

            elif current_task and line.startswith("- **Changes**:"):
                current_task["description"] = line.replace("- **Changes**:", "").strip()

        if current_task:
            tasks.append(current_task)

        # Fallback: if no tasks parsed, create a single task
        if not tasks:
            tasks = [
                {
                    "name": "Implement project",
                    "description": "Complete implementation",
                    "files": [],
                }
            ]

        return tasks

    def extract_and_save_code(self, response: str, project_dir: Path = None) -> dict:
        """Extract code blocks from response and save to files.

        Args:
            response: The LLM response containing code blocks
            project_dir: Optional override for project directory

        Returns:
            dict with 'total', 'implementation', 'test' counts, and 'files_list' with paths
        """
        if project_dir is None:
            project_dir = self.project_dir

        # Try multiple patterns to be flexible
        # Fixed: Allow optional whitespace/newline after language identifier
        patterns = [
            # Pattern 1: "File: path" followed by code block
            r"File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 2: "file: path" (lowercase)
            r"file:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 3: "File path: path"
            r"File path:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 4: "## File: path" (markdown h2 header)
            r"##\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 5: "### File: path" (markdown h3 header)
            r"###\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 6: "# File: path" (any markdown header)
            r"#+\s+File:\s*([^\n]+)\n```(?:\w+)?[ \t]*\n?(.*?)```",
            # Pattern 7: Just a path in backticks before code block
            r"`([^`\n]+\.[a-z]{2,4})`\n```(?:\w+)?[ \t]*\n?(.*?)```",
        ]

        files_created = 0
        test_files = 0
        impl_files = 0
        files_list = []  # Track all created file paths

        for pattern in patterns:
            matches = re.finditer(pattern, response, re.DOTALL | re.IGNORECASE)

            for match in matches:
                filepath = match.group(1).strip()
                code = match.group(2).strip()

                # Clean up filepath
                filepath = filepath.replace("`", "").strip()

                # Skip if filepath looks like description text
                if len(filepath) > 100 or '\n' in filepath:
                    continue

                # Strip leading slashes to ensure relative path
                # (Python's Path treats "/file.txt" as absolute, ignoring project_dir)
                filepath = filepath.lstrip('/')

                # Fix: Remove duplicate project path prefixes
                # LLM sometimes outputs "examples/weather-app/src/..." when we're already in examples/weather-app/
                if filepath.startswith(f'examples/{self.project_name}/'):
                    filepath = filepath.replace(f'examples/{self.project_name}/', '', 1)
                elif filepath.startswith(f'{self.project_name}/'):
                    filepath = filepath.replace(f'{self.project_name}/', '', 1)

                # Save file
                full_path = (project_dir / filepath).resolve()

                # Security check: ensure file is within project directory
                if not str(full_path).startswith(str(project_dir.resolve())):
                    print(f"   ⚠️  WARNING: Skipping file outside project directory: {filepath}")
                    continue

                full_path.parent.mkdir(parents=True, exist_ok=True)

                # Post-process CRA template variables before writing
                if '%PUBLIC_URL%' in code or '%REACT_APP_' in code:
                    # Replace CRA template variables
                    code = code.replace('%PUBLIC_URL%', '')  # Empty string for local dev
                    # Replace environment variables if available
                    env_vars = re.findall(r'%REACT_APP_([A-Z_]+)%', code)
                    for var_name in env_vars:
                        env_value = os.getenv(f'REACT_APP_{var_name}', '')
                        code = code.replace(f'%REACT_APP_{var_name}%', env_value)

                full_path.write_text(code)

                print(f"   📁 Created: {full_path}")
                files_created += 1
                files_list.append(filepath)  # Track the relative path

                # Track test vs implementation files
                if 'test' in filepath.lower() or filepath.startswith('tests/'):
                    test_files += 1
                else:
                    impl_files += 1

        # Enhanced validation: Detect extraction failures
        if files_created == 0:
            # Check if code blocks exist in response
            code_blocks_found = len(re.findall(r'```\w+', response))
            file_markers_found = len(re.findall(r'(?:File|file):\s*\S+', response))

            print(f"   ⚠️  WARNING: No code files were extracted from Builder output!")

            if code_blocks_found > 0 or file_markers_found > 0:
                print(f"   🔍 Debug: Found {code_blocks_found} code blocks and {file_markers_found} file markers")
                print(f"   ⚠️  This may indicate a regex extraction failure!")
                print(f"   💡 Check the output format - language identifier may not have newline")
            else:
                print(f"   💡 The LLM may have described files instead of generating code.")

        elif impl_files == 0 and test_files > 0:
            print(f"   ⚠️  WARNING: Only test files were created ({test_files} tests, 0 implementation files)")
            print(f"   💡 The LLM may have misunderstood the task - implementation files are missing!")

        return {
            'total': files_created,
            'implementation': impl_files,
            'test': test_files,
            'files_list': files_list
        }

#!/usr/bin/env python3
"""
Documentation Generator for Context Foundry
Generates README.md and .env files for projects
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


class DocsGenerator:
    """
    Generates project documentation including README.md and .env files.

    Extracted from AutonomousOrchestrator to provide standalone documentation
    generation capabilities.
    """

    def __init__(
        self,
        project_dir: Path,
        ai_client: Optional[Any] = None,
        task_description: str = "",
        project_name: Optional[str] = None
    ):
        """
        Initialize DocsGenerator.

        Args:
            project_dir: Path to the project directory
            ai_client: Optional AI client for enhanced README generation
            task_description: Description of the project/task
            project_name: Name of the project (defaults to directory name)
        """
        self.project_dir = Path(project_dir)
        self.ai_client = ai_client
        self.task_description = task_description
        self.project_name = project_name or self.project_dir.name

    def generate_readme(self, files_created: List) -> Optional[Path]:
        """Generate README.md with project info and run instructions.

        Args:
            files_created: List of (task_num, files_list) tuples or simple file list

        Returns:
            Path to README.md if created, None otherwise
        """
        # Collect all files (use set to deduplicate)
        all_files_set = set()

        # Handle both list formats: [(task_num, files_list), ...] or [file1, file2, ...]
        for item in files_created:
            if isinstance(item, tuple) and len(item) == 2:
                # Format: (task_num, files_list)
                task_num, files_list = item
                all_files_set.update(files_list)
            elif isinstance(item, str):
                # Format: simple file list
                all_files_set.add(item)
            elif isinstance(item, list):
                # Format: nested list
                all_files_set.update(item)

        if not all_files_set:
            return None

        # Convert to sorted list for consistent ordering
        all_files = sorted(all_files_set)

        # Detect project type
        has_package_json = (self.project_dir / "package.json").exists()
        has_requirements_txt = (self.project_dir / "requirements.txt").exists()
        has_index_html = any('index.html' in f for f in all_files)

        # Determine run instructions
        if has_package_json:
            # Check which npm script to use
            try:
                package_data = json.loads((self.project_dir / "package.json").read_text())
                scripts = package_data.get('scripts', {})

                # Prefer 'start' for CRA, fall back to 'dev' for Vite/Next
                if 'start' in scripts:
                    npm_command = "npm start"
                elif 'dev' in scripts:
                    npm_command = "npm run dev"
                else:
                    npm_command = "npm start"  # default

                project_type = "Node.js"
            except:
                npm_command = "npm start"  # fallback
                project_type = "Node.js"

            run_instructions = f"""## Quick Start

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   {npm_command}
   ```

3. Open your browser to the URL shown in the terminal (usually http://localhost:3000)"""

        elif has_index_html and not has_package_json:
            project_type = "Static HTML"

            # Check if app makes API calls (likely needs local server for CORS)
            has_api_calls = any('api' in f.lower() or 'fetch' in str(all_files).lower() for f in all_files)

            if has_api_calls:
                run_instructions = """## Quick Start

⚠️  **Important**: This app makes API calls and MUST be run through a local server (not by opening the file directly).

**Option 1 - Python (simplest)**:
```bash
python3 -m http.server 8000
```
Then open http://localhost:8000

**Option 2 - Node.js**:
```bash
npx serve .
```

**Option 3 - VS Code**:
Install "Live Server" extension, then right-click index.html → "Open with Live Server"

**Why?** Opening the HTML file directly (`file:///`) causes CORS errors when making API requests."""
            else:
                run_instructions = """## Quick Start

This is a static HTML/CSS/JavaScript app. No build step needed!

1. Simply open `index.html` in your web browser
2. Or use a local server:
   ```bash
   python3 -m http.server 8000
   ```
   Then open http://localhost:8000"""

        elif has_requirements_txt:
            project_type = "Python"
            main_file = next((f for f in all_files if 'main.py' in f or 'app.py' in f), 'main.py')
            run_instructions = f"""## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python {main_file}
   ```"""

        else:
            project_type = "Application"
            run_instructions = """## Quick Start

See the project files to determine how to run this application."""

        # Extract API keys from task description
        api_key_section = ""
        if 'api' in self.task_description.lower() and 'key' in self.task_description.lower():
            # Try to extract key from description
            key_match = re.search(r'key[=:\s]+([a-zA-Z0-9]+)', self.task_description, re.IGNORECASE)
            if key_match:
                api_key_section = f"""
## API Configuration

This app uses an API key that's already configured in the code:
- API Key: `{key_match.group(1)}`

To use your own API key, update the relevant configuration file."""

        # Build file structure
        file_structure = "\n".join(f"- `{f}`" for f in sorted(all_files) if not f.startswith('tests/'))

        # Generate README content
        readme_content = f"""# {self.project_name.replace('-', ' ').replace('_', ' ').title()}

{self.task_description}

{run_instructions}{api_key_section}

## Project Structure

{file_structure}

## Built With

- **Type**: {project_type}
- **Generated**: {datetime.now().strftime('%Y-%m-%d')}
- **Tool**: [Context Foundry](https://github.com/your-repo/context-foundry)

---

*This README was automatically generated by Context Foundry*
"""

        # Save README
        readme_path = self.project_dir / "README.md"
        readme_path.write_text(readme_content)

        return readme_path

    def generate_env_file(self) -> Optional[Path]:
        """Generate .env file with API keys extracted from task description.

        Returns:
            Path to .env if created, None otherwise
        """
        # Check if task description mentions API keys
        if 'api' not in self.task_description.lower() or 'key' not in self.task_description.lower():
            return None

        # Don't create .env for static HTML apps (they can't use it - no build process)
        package_json_path = self.project_dir / "package.json"
        if not package_json_path.exists():
            # Static HTML app - builder should hard-code keys directly in JS
            return None

        # Extract API key name and value
        # Common patterns:
        # - "key=abc123" or "key: abc123"
        # - "api key abc123" or "API_KEY=abc123"
        # - "openweathermap api key c4b27..."

        env_vars = {}

        # Pattern 1: key=value or key:value
        key_match = re.search(r'key[=:\s]+([a-zA-Z0-9_-]+)', self.task_description, re.IGNORECASE)
        if key_match:
            key_value = key_match.group(1)

            # Detect project type for proper env var naming
            package_json_path = self.project_dir / "package.json"
            if package_json_path.exists():
                try:
                    package_data = json.loads(package_json_path.read_text())
                    dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}

                    # Create React App uses REACT_APP_ prefix
                    if 'react-scripts' in dependencies:
                        env_vars['REACT_APP_WEATHER_API_KEY'] = key_value
                        env_vars['REACT_APP_API_KEY'] = key_value
                    # Vite uses VITE_ prefix
                    elif 'vite' in dependencies:
                        env_vars['VITE_WEATHER_API_KEY'] = key_value
                        env_vars['VITE_API_KEY'] = key_value
                    else:
                        env_vars['API_KEY'] = key_value
                        env_vars['WEATHER_API_KEY'] = key_value
                except:
                    env_vars['API_KEY'] = key_value
            else:
                env_vars['API_KEY'] = key_value

        if not env_vars:
            return None

        # Generate .env content
        env_content = "# Auto-generated by Context Foundry\n"
        env_content += "# API Keys extracted from task description\n\n"
        for key, value in env_vars.items():
            env_content += f"{key}={value}\n"

        # Save .env file
        env_path = self.project_dir / ".env"
        env_path.write_text(env_content)

        return env_path
